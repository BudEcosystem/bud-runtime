---
date: 2026-02-10
topic: usecase-access-modes
---

# Use Case Access Modes: UI + API

## What We're Building

Use case deployments need two access modes, declared in the template YAML:

1. **UI Access** — The deployed service's web interface (e.g., RAGFlow dashboard) is shown inside budadmin via an iframe. Traffic routes: `budadmin -> budapp (internal proxy) -> Envoy Gateway on target cluster -> service`. No public exposure needed.

2. **API Access** — The deployed service's API endpoints are exposed through budgateway for external consumption. Traffic routes: `external client -> budgateway -> Envoy Gateway on target cluster -> service`. Users get a gateway-managed base URL with project-scoped auth (same as model endpoints).

Both modes require an **HTTPRoute on the target cluster** (Kubernetes Gateway API standard, via the Envoy Gateway already deployed by AIBrix). budcluster creates the HTTPRoute + ReferenceGrant after helm deploy completes.

## Architecture: Why Envoy Gateway (not Traefik)

AIBrix deployment already installs **Envoy Gateway** (`aibrix-eg` in `aibrix-system` namespace) on every onboarded cluster. This is used for model endpoint routing via HTTPRoute CRDs. Benefits of reusing it for use cases:

- **Already deployed** — no additional infrastructure
- **Standard Kubernetes Gateway API** — portable, vendor-neutral (HTTPRoute, ReferenceGrant)
- **Single gateway endpoint** — both model endpoints and use case services share the same external IP
- **WebSocket support** — Envoy natively supports WebSocket upgrades
- **Future benefit** — AIBrix ext-proc can provide smart routing for LLM components in use cases

Traefik remains for the control plane's own ingress but is NOT used for use case routing on target clusters.

## Key Decisions

### 1. Template declares access modes

Templates specify what access types are supported via an `access` section:

```yaml
access:
  ui:
    enabled: true
    port: 80          # Which container port serves the UI
    path: /           # Root path of the UI
  api:
    enabled: true
    port: 9380        # Which container port serves the API
    base_path: /api   # API base path on the service
    spec:             # OpenAPI-style spec for UI documentation only
      - path: /v1/chat/completions
        method: POST
        description: "Chat completion endpoint"
        request_body:
          content_type: application/json
          schema:
            model: { type: string, description: "Model name" }
            messages: { type: array, description: "Chat messages" }
        response:
          content_type: application/json
          schema:
            choices: { type: array, description: "Completion choices" }
      - path: /v1/documents
        method: POST
        description: "Upload documents for RAG"
        request_body:
          content_type: multipart/form-data
```

### 2. UI access routes through budapp (internal proxy)

- budapp adds a proxy endpoint: `GET /usecases/{deployment_id}/ui/**`
- budapp looks up the deployment's cluster_id, gets the cluster's gateway endpoint
- Proxies to: `{envoy_gateway_url}/usecases/{deployment_id}/ui/**`
- budadmin renders the UI in an iframe pointing to this budapp endpoint
- Authentication is inherited from the budapp session (user is already logged in)
- WebSocket upgrade headers are passed through for interactive UIs

### 3. API access routes through budgateway

- After deployment completes, budgateway is configured with a new route
- External users hit: `{gateway_url}/usecases/{deployment_id}/api/**`
- budgateway proxies to: `{envoy_gateway_url}/usecases/{deployment_id}/api/**`
- Gateway does simple path-based proxying (no request validation)
- Gateway provides its standard features: rate limiting, logging, project-scoped auth (same as model endpoints)

### 4. OpenAPI spec is for documentation only

- The `spec` section in the template is NOT used for gateway validation
- It is rendered in the budadmin UI (after deployment success) so users can see:
  - Available endpoints with methods
  - Request/response schemas
  - Example payloads
- This serves as inline API documentation, eliminating the need to find external docs

### 5. Routing on target cluster via Envoy Gateway (HTTPRoute)

budcluster creates Kubernetes Gateway API resources after helm deploy completes:

**HTTPRoute** (path-based, single route with two rules for UI and API ports):

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: usecase-{deployment_id}
  namespace: usecase-{deployment_id_prefix}
spec:
  parentRefs:
    - name: aibrix-eg
      namespace: aibrix-system
  rules:
    # UI route
    - matches:
        - path:
            type: PathPrefix
            value: /usecases/{deployment_id}/ui
      filters:
        - type: URLRewrite
          urlRewrite:
            path:
              type: ReplacePrefixMatch
              replacePrefixMatch: /
      backendRefs:
        - name: {service_name}
          port: 80
    # API route
    - matches:
        - path:
            type: PathPrefix
            value: /usecases/{deployment_id}/api
      filters:
        - type: URLRewrite
          urlRewrite:
            path:
              type: ReplacePrefixMatch
              replacePrefixMatch: /api
      backendRefs:
        - name: {service_name}
          port: 9380
```

**ReferenceGrant** (allows cross-namespace routing from aibrix-system gateway):

```yaml
apiVersion: gateway.networking.k8s.io/v1beta1
kind: ReferenceGrant
metadata:
  name: allow-aibrix-gateway
  namespace: usecase-{deployment_id_prefix}
spec:
  from:
    - group: gateway.networking.k8s.io
      kind: HTTPRoute
      namespace: aibrix-system
  to:
    - group: ""
      kind: Service
```

Envoy Gateway (`aibrix-eg`) dynamically discovers these HTTPRoute resources and serves them.

### 6. budcluster creates the routing resources

- budcluster already manages cluster lifecycle and has kubeconfig access
- After a use case helm chart is deployed, budcluster creates the HTTPRoute + ReferenceGrant
- On deletion, budcluster cleans up these resources
- The gateway endpoint (Envoy Gateway's external IP) is discoverable from the `aibrix-eg` gateway service in `aibrix-system` namespace
- budcluster stores/caches this endpoint alongside the existing `ingress_url`

## Template Examples

### RAGFlow (UI + API)
```yaml
access:
  ui:
    enabled: true
    port: 80
    path: /
  api:
    enabled: true
    port: 9380
    base_path: /api
    spec:
      - path: /v1/api/new_conversation
        method: POST
        description: "Create a new conversation"
      - path: /v1/api/completion
        method: POST
        description: "Get RAG completion"
        request_body:
          content_type: application/json
          schema:
            conversation_id: { type: string }
            messages: { type: array }
```

### Agent RAG (API only)
```yaml
access:
  ui:
    enabled: false
  api:
    enabled: true
    port: 8080
    base_path: /
    spec:
      - path: /v1/chat
        method: POST
        description: "Chat with the RAG agent"
```

### Simple RAG (No direct access — models only)
```yaml
access:
  ui:
    enabled: false
  api:
    enabled: false
# Components are accessed individually via their model endpoints
```

## Traffic Flow Summary

```
                                        Target Cluster
                                       +-------------------+
  budadmin (iframe)                    |                   |
       |                               | Envoy Gateway     |
       v                               | (aibrix-eg)       |
  budapp /usecases/{id}/ui/** -------->| aibrix-system ns  |
                                       |                   |
                                       | HTTPRoute:        |
                                       | /usecases/{id}/ui |---> Service UI (:80)
  External API client                  | /usecases/{id}/api|---> Service API (:9380)
       |                               |                   |
       v                               | (same gateway as  |
  budgateway /usecases/{id}/api/** --->|  model endpoints) |
                                       +-------------------+
```

## Post-Deployment UX in budadmin

After a deployment completes successfully, the Success step (Step 4) shows:

- **"Open UI" button** (if `access.ui.enabled`) — Opens iframe drawer or new tab
- **"API Endpoint" section** (if `access.api.enabled`) — Shows:
  - Base URL: `https://gateway.bud.studio/usecases/{deployment_id}/api`
  - API key / auth instructions (project-scoped, same as model endpoints)
  - Expandable API reference generated from the `spec` section
  - Copy-paste curl examples for each endpoint

## Resolved Questions

1. **Ingress path conflicts**: deployment_id in the path guarantees uniqueness
2. **WebSocket support**: Envoy natively supports WebSocket upgrades; budapp proxy must pass upgrade headers
3. **Multiple ports**: Single HTTPRoute with two rules (path differentiation to different backend ports)
4. **Auth for API via gateway**: Same project-scoped auth as model endpoints
5. **Who creates routing resources**: budcluster (has kubeconfig access, manages cluster lifecycle)
6. **Which gateway**: Envoy Gateway (aibrix-eg) — already deployed by AIBrix, standard Gateway API

## Next Steps

-> `/plan` for implementation details across:
  - Template schema changes (access section)
  - budcluster: HTTPRoute/ReferenceGrant creation after helm deploy
  - budapp: proxy endpoint for UI access
  - budgateway: route configuration for API access
  - budadmin: Success step UI (Open UI button, API reference)
  - budusecases: template sync to parse and store access config
