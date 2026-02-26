# Use Case API Access Proxy — Design Document

> **Document Version:** 1.3
> **Date:** February 9, 2026
> **Status:** Brainstorm / Design
> **Authors:** Engineering Team
> **Changelog:**
> - v1.3 — Ingress-based routing: deploy Traefik/Envoy on each cluster, create per-deployment Ingress resources. budgateway proxies to the ingress URL directly. No K8s API server proxy, no tokens, no cluster credentials in Redis.
> - v1.2 — Direct gateway-to-cluster via K8s API server proxy + bearer tokens (rejected — API server is control-plane, not data-plane).
> - v1.1 — Route through budcluster via Dapr (rejected — extra hop, unnecessary coupling).
> - v1.0 — Initial design with kube-rs in budgateway (over-engineered).

---

## 1. Problem Statement

When a user deploys a use case (e.g., RAGFlow, a vLLM-backed chatbot, or an agent pipeline) via BudUseCases, the deployed services run inside a Kubernetes namespace on a remote cluster. Today there is **no way for external consumers** (applications, scripts, integrations) to call those deployed service APIs.

Example: A user deploys the `ragflow` template to cluster `pnap-01`. RAGFlow exposes a REST API at `http://ragflow-server:9380` inside namespace `usecase-ca770191`. That API is only reachable from within the cluster. The user has no authenticated, external path to call it.

### Goals

1. **External API access** — Let users call deployed use-case service APIs from outside the cluster, through a single stable gateway URL.
2. **Project-scoped auth** — Reuse the existing budgateway API key system. A project API key grants access to deployments owned by that project.
3. **Zero config for users** — Routing is registered automatically when a deployment completes. No manual ingress setup required.
4. **Multi-cluster** — Works across all registered clusters (AWS EKS, Azure AKS, on-prem).

### Non-Goals (v1)

- WebSocket or gRPC passthrough (HTTP only in v1)
- Per-deployment rate limiting (use project-level rate limiting)
- Custom domain names per deployment
- Deployment-level API key scoping (project-level is sufficient for v1)

---

## 2. Gaps Discovered

### Gap 1: No `project_id` on UseCaseDeployment

API keys are project-scoped (`APIKeyCredential.project_id`), but `UseCaseDeployment` has no `project_id`. This breaks the access-control chain:

```
API key → project_id → ? → deployment
                        ↑ missing link
```

**Current model** (`budusecases/deployments/models.py`):
```python
class UseCaseDeployment(PSQLBase):
    id, name, template_id, cluster_id, user_id, status, ...
    # NO project_id
```

**Fix**: Add `project_id` column (UUID, NOT NULL, indexed). Requires Alembic migration and schema updates.

### Gap 2: `user_id` not forwarded from budapp to budusecases

`budapp/workflow_ops/budusecases_service.py` calls `DaprService.invoke_service()` but never passes the `headers` parameter. The budusecases service reads `x-user-id` from request headers (via `get_current_user_id` dependency), defaulting to a nil UUID when absent.

**Fix**: Forward `x-user-id` (and `x-project-id` when added) in all Dapr invocations from budapp.

### Gap 3: `endpoint_url` not populated after deployment

`ComponentDeployment.endpoint_url` exists in the model (nullable `String(500)`) but is never written during deployment orchestration. The helm-component-orchestration plan describes it as a pipeline step output, but the implementation doesn't populate it yet.

**Fix**: After helm chart deploys successfully, write the internal service URL (e.g., `http://ragflow-server.usecase-{id}.svc.cluster.local:9380`) to `endpoint_url`.

---

## 3. Architecture Overview

Each registered cluster runs an **ingress controller** (Traefik or Envoy). When a use case deploys, an `Ingress` resource is created that routes traffic to the deployed service. budgateway resolves the deployment's ingress URL from in-memory state and proxies the request there — a plain HTTPS call, no K8s API knowledge required.

```
                           ┌─────────────────┐
  External Consumer ──────>│   budgateway     │
  (Bearer API key)         │ (Rust / Axum)    │
                           │                  │
                           │  Auth + Route    │
                           │  Resolution      │
                           │  (in-memory)     │
                           │                  │
                           │  Plain HTTPS     │
                           │  to ingress URL  │
                           │  (via reqwest)   │
                           └───────┬──────────┘
                                   │ HTTPS
                    ┌──────────────┼──────────────┐
                    │              │               │
              ┌─────▼─────┐ ┌─────▼─────┐  ┌─────▼─────┐
              │  Cluster A │ │ Cluster B  │  │ Cluster C │
              │  Traefik   │ │  Traefik   │  │  Traefik  │
              │  Ingress   │ │  Ingress   │  │  Ingress  │
              │     │      │ │     │      │  │     │     │
              │     ▼      │ │     ▼      │  │     ▼     │
              │  Service   │ │  Service   │  │  Service  │
              │  Pods      │ │  Pods      │  │  Pods     │
              └────────────┘ └───────────┘  └───────────┘
```

**Why ingress instead of K8s API server proxy?**

- **Purpose-built** — Ingress controllers are designed for data-plane traffic (connection pooling, retries, timeouts, streaming, WebSockets)
- **No cluster credentials in budgateway** — no bearer tokens, no CA certs, no `cluster_connection:` Redis keys. budgateway just calls a URL.
- **No K8s API server load** — the control plane stays untouched
- **Horizontally scalable** — ingress controller can scale independently
- **Observability** — built-in access logs, metrics, tracing
- **Future-proof** — supports WebSockets, gRPC, HTTP/2 when needed

**Setup cost (one-time per cluster):**
- Deploy ingress controller (Traefik/Envoy) during cluster onboarding
- Get external IP or DNS for the ingress (LoadBalancer service)
- Optionally: cert-manager for TLS

**Per-deployment cost (automated):**
- Create an `Ingress` resource as part of the helm chart deployment

### Data Flow (Happy Path)

```
1. Consumer sends:
   POST /v1/usecases/{deployment_id}/api/v1/chat
   Authorization: Bearer bud_client_xxx

2. budgateway auth middleware:
   - SHA256("bud-" + key) → lookup in api_keys store
   - Extract project_id from AuthMetadata.api_key_project_id
   - Inject x-tensorzero-api-key-project-id header

3. Use-case proxy handler:
   - Lookup deployment_id in deployment_routes store (in-memory)
   - Verify route.project_id == request.api_key_project_id
   - Forward to route.ingress_url + /{path}

4. budgateway sends HTTPS request to ingress URL:
   - Plain HTTP(S) — no K8s tokens, no special auth
   - Forwards original method, headers, body

5. Ingress controller on remote cluster:
   - Routes by path prefix to the correct service
   - e.g., /usecase-ca770191/* → ragflow-server:9380

6. Response streams back to consumer
```

---

## 4. Redis Schema

### 4.1 Deployment Route Key (only new key type)

```
Key:    deployment_route:{deployment_id}
Value:  JSON
TTL:    None (persistent, removed on deployment delete)
```

```json
{
  "deployment_id": "ca770191-...",
  "project_id": "proj-456-...",
  "ingress_url": "http://10.0.0.50/usecase-ca770191",
  "status": "active",
  "created_at": "2026-02-09T10:00:00Z"
}
```

**Who writes it**: budusecases after deployment completes and the Ingress resource is confirmed ready.

**Who reads it**: budgateway — loaded on startup, hot-reloaded via Redis keyspace notifications.

The key is intentionally minimal. budgateway doesn't need to know about clusters, namespaces, or services — just the ingress URL to forward to. All K8s-internal routing is handled by the ingress controller on the remote cluster.

**No `cluster_connection:` key needed** — budgateway has no direct relationship with K8s clusters. It only knows about URLs.

### 4.2 API Key (no new keys — existing pattern)

The existing `api_key:{hash}` Redis keys already contain `__metadata__` with `api_key_project_id`. No new Redis keys are needed for auth — the proxy handler reads `api_key_project_id` from the request headers injected by the existing auth middleware.

---

## 5. budgateway Rust Implementation

### 5.1 New Route Group

Add to `gateway/src/main.rs` alongside existing OpenAI routes:

```rust
// Use-case proxy routes (authenticated, same API key auth as inference)
let usecase_proxy_routes = Router::new()
    .route(
        "/v1/usecases/{deployment_id}/{*path}",
        any(usecase_proxy_handler),
    )
    .layer(middleware::from_fn_with_state(auth.clone(), require_api_key));

// Merge into main router
let app = Router::new()
    .merge(openai_routes)
    .merge(usecase_proxy_routes)  // NEW
    .merge(public_routes)
    ...
```

The `any()` handler accepts all HTTP methods (GET, POST, PUT, DELETE, PATCH) — the proxy passes them through transparently.

### 5.2 In-Memory State

Add to `AppStateData`:

```rust
pub struct UseCaseProxyState {
    /// deployment_id → DeploymentRoute (from Redis)
    pub deployment_routes: Arc<RwLock<HashMap<String, DeploymentRoute>>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeploymentRoute {
    pub deployment_id: String,
    pub project_id: String,
    pub ingress_url: String,
    pub status: String,
}
```

That's it. No `ClusterConnection`, no tokens, no certs. budgateway only knows deployment IDs and ingress URLs.

### 5.3 Proxy Handler

```rust
async fn usecase_proxy_handler(
    State(state): State<Arc<AppStateData>>,
    Path((deployment_id, path)): Path<(String, String)>,
    headers: HeaderMap,
    method: Method,
    body: Body,
) -> Result<Response<Body>, ProxyError> {
    // 1. Auth: project_id already injected by require_api_key middleware
    let api_key_project_id = headers
        .get("x-tensorzero-api-key-project-id")
        .and_then(|v| v.to_str().ok())
        .ok_or(ProxyError::Unauthorized("Missing project context"))?;

    // 2. Route lookup (O(1) in-memory)
    let route = {
        let routes = state.proxy.deployment_routes.read().unwrap();
        routes.get(&deployment_id).cloned()
            .ok_or(ProxyError::NoRouteFound(deployment_id.clone()))?
    };

    // 3. Project access check
    if route.project_id != api_key_project_id {
        return Err(ProxyError::Unauthorized(
            "API key does not have access to this deployment"
        ));
    }

    // 4. Check deployment is active
    if route.status != "active" {
        return Err(ProxyError::DeploymentUnavailable(deployment_id));
    }

    // 5. Build upstream URL (just append path to ingress URL)
    let upstream_url = format!(
        "{}/{}",
        route.ingress_url.trim_end_matches('/'),
        path.trim_start_matches('/')
    );

    // 6. Forward request via reqwest (already available)
    let body_bytes = to_bytes(body, 10 * 1024 * 1024).await?; // 10MB limit
    let mut upstream_req = state.http_client
        .request(method, &upstream_url);

    // Forward safe headers (strip hop-by-hop + internal headers)
    for (name, value) in filter_proxy_headers(&headers) {
        upstream_req = upstream_req.header(name, value);
    }

    let upstream_resp = upstream_req
        .body(body_bytes)
        .send()
        .await
        .map_err(|e| ProxyError::UpstreamConnectionFailed(e.to_string()))?;

    // 7. Stream response back
    let status = upstream_resp.status();
    let resp_headers = upstream_resp.headers().clone();
    let body_stream = upstream_resp.bytes_stream();

    let mut response = Response::builder().status(status);
    for (name, value) in filter_response_headers(&resp_headers) {
        response = response.header(name, value);
    }

    Ok(response.body(Body::from_stream(body_stream))?)
}
```

The handler is now trivial — auth check, one HashMap lookup, one `reqwest` call. No K8s knowledge, no tokens, no TLS complexity.

### 5.4 Redis Integration

Extend existing `redis_client.rs` with **one** new key prefix:

```rust
const DEPLOYMENT_ROUTE_PREFIX: &str = "deployment_route:";
```

**In `handle_set_key_event()`** (add match arm):
```rust
k if k.starts_with(DEPLOYMENT_ROUTE_PREFIX) => {
    let value: String = get_with_retry(conn, key, 3).await?;
    let route: DeploymentRoute = serde_json::from_str(&value)?;
    let id = k.strip_prefix(DEPLOYMENT_ROUTE_PREFIX).unwrap();
    state.proxy.deployment_routes.write().unwrap()
        .insert(id.to_string(), route);
    tracing::info!(deployment_id = id, "Updated deployment route");
}
```

**In `handle_del_key_event()`** (add match arm):
```rust
k if k.starts_with(DEPLOYMENT_ROUTE_PREFIX) => {
    let id = k.strip_prefix(DEPLOYMENT_ROUTE_PREFIX).unwrap();
    state.proxy.deployment_routes.write().unwrap().remove(id);
    tracing::info!(deployment_id = id, "Removed deployment route");
}
```

**Initial load** (in `start()` function): Scan `deployment_route:*` on startup, populate in-memory store. No decryption needed — ingress URLs are not secrets.

### 5.5 Header Filtering

```rust
const HOP_BY_HOP_HEADERS: &[&str] = &[
    "connection", "keep-alive", "proxy-authenticate",
    "proxy-authorization", "te", "trailers",
    "transfer-encoding", "upgrade",
];

fn filter_proxy_headers(headers: &HeaderMap) -> impl Iterator<Item = (&HeaderName, &HeaderValue)> {
    headers.iter().filter(|(name, _)| {
        let n = name.as_str();
        !HOP_BY_HOP_HEADERS.contains(&n)
            && !n.starts_with("x-tensorzero-")  // strip internal headers
            && n != "host"  // upstream sets its own Host
    })
}
```

---

## 6. Ingress Controller Setup

### 6.1 Cluster Onboarding (One-Time)

During cluster registration/onboarding (`register_cluster` workflow), deploy an ingress controller:

```python
# budcluster/cluster_ops/services.py (in register_cluster flow)
async def deploy_ingress_controller(cluster_id: str, k8s_handler):
    """Deploy Traefik ingress controller for use-case API access."""
    # Deploy Traefik via Helm (same pattern as GPU Operator, HAMI)
    await k8s_handler.helm_install(
        release_name="bud-ingress",
        chart="traefik/traefik",
        namespace="bud-ingress",
        values={
            "service": {"type": "LoadBalancer"},
            "ports": {
                "web": {"port": 80},
                "websecure": {"port": 443},
            },
            # Allow routing to any namespace
            "providers": {
                "kubernetesIngress": {
                    "allowExternalNameServices": True,
                },
            },
        },
    )

    # Wait for LoadBalancer to get an external IP
    ingress_ip = await wait_for_loadbalancer_ip(
        k8s_handler, "bud-ingress", "bud-ingress"
    )

    # Store the ingress base URL on the cluster record
    await update_cluster_ingress_url(cluster_id, f"http://{ingress_ip}")
    logger.info(f"Ingress controller ready at {ingress_ip} for cluster {cluster_id}")
```

The ingress base URL (e.g., `http://10.0.0.50`) is stored on the cluster record in budcluster's database. This is used when constructing the deployment route's `ingress_url`.

### 6.2 Per-Deployment Ingress Resource (Automated)

When a use case helm chart is deployed, an `Ingress` resource is created in the deployment namespace. This can be either:

**Option A (Preferred): Part of the helm chart** — Each use-case helm chart includes an Ingress template:

```yaml
# templates/ingress.yaml (inside the use-case helm chart)
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {{ .Release.Name }}-ingress
  namespace: {{ .Release.Namespace }}
  annotations:
    traefik.ingress.kubernetes.io/router.entrypoints: web
spec:
  rules:
    - http:
        paths:
          - path: /{{ .Release.Namespace }}
            pathType: Prefix
            backend:
              service:
                name: {{ .Values.serviceName }}
                port:
                  number: {{ .Values.servicePort }}
```

For RAGFlow in namespace `usecase-ca770191`, this creates a route:
```
http://{ingress_ip}/usecase-ca770191/* → ragflow-server:9380
```

**Option B: Created by budusecases after helm deploy** — If the helm chart doesn't include an Ingress, budusecases creates one via the K8s API after the deployment completes.

### 6.3 Ingress Controller Choice

| Controller | Pros | Cons |
|-----------|------|------|
| **Traefik** (recommended for v1) | Lightweight, auto-discovers Ingress resources, built-in dashboard, easy Helm install | Less advanced traffic features than Envoy |
| **Envoy Gateway** | K8s Gateway API native, powerful routing, used by Istio | More complex setup, heavier |
| **NGINX Ingress** | Most popular, battle-tested | Legacy Ingress API only, less modern |

For v1, **Traefik** is recommended — it's lightweight, deploys easily via Helm, and auto-discovers Ingress resources without extra configuration.

### 6.4 Network Requirements

The ingress controller's LoadBalancer must be reachable from where budgateway runs:

| Scenario | Solution |
|----------|----------|
| Same private network (typical for on-prem) | Direct IP, no extra config |
| Different networks (cloud clusters) | VPN, VPC peering, or public IP with firewall rules |
| Public internet | TLS via cert-manager + Let's Encrypt |

For v1, most deployments are on-prem or same-network, so HTTP with private IPs is sufficient.

---

## 7. Database Changes

### 7.1 Add `project_id` to UseCaseDeployment

**Migration** (`budusecases/alembic/versions/xxxx_add_project_id.py`):

```python
def upgrade():
    op.add_column(
        "usecase_deployments",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
    )

def downgrade():
    op.drop_column("usecase_deployments", "project_id")
```

**Model change** (`budusecases/deployments/models.py`):
```python
project_id: Mapped[Optional[UUID]] = mapped_column(
    UUID(as_uuid=True), nullable=True, index=True
)
```

Nullable for backwards compatibility with existing deployments. New deployments require it (enforced at the route/service level).

**Schema change** (`budusecases/deployments/schemas.py`):
```python
class DeploymentCreateSchema(BaseModel):
    ...
    project_id: Optional[str] = Field(None, description="Project ID for access control")

class DeploymentResponseSchema(BaseModel):
    ...
    project_id: Optional[str] = Field(None, description="Project ID")
```

### 7.2 Forward user_id and project_id from budapp

**Modify** `budapp/workflow_ops/budusecases_service.py` — add headers to all `DaprService.invoke_service()` calls:

```python
async def create_deployment(self, data: Dict[str, Any], user_id: str, project_id: str) -> Dict[str, Any]:
    result = await DaprService.invoke_service(
        app_id=BUDUSECASES_APP_ID,
        method_path="api/v1/deployments",
        method="POST",
        data=data,
        headers={"x-user-id": user_id, "x-project-id": project_id},
    )
    return result
```

**Modify** `budapp/workflow_ops/budusecases_routes.py` — pass current user's ID:

```python
@budusecases_router.post("/deployments")
async def create_deployment(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    body = await request.json()
    service = BudUseCasesService()
    result = await service.create_deployment(
        data=body,
        user_id=str(current_user.id),
        project_id=body.get("project_id", ""),
    )
    return result
```

---

## 8. Service Discovery — Populating `endpoint_url`

When a component deployment completes (Helm chart installed, pod running), the system must record the in-cluster service URL.

### 8.1 Convention

```
http://{release_name}.{namespace}.svc.cluster.local:{port}
```

Example for RAGFlow in deployment `ca770191`:
```
http://ragflow-server.usecase-ca770191.svc.cluster.local:9380
```

### 8.2 Where to populate

**Option A (Preferred)**: In the BudPipeline helm_deploy action callback — when the step reports `COMPLETED`, write `endpoint_url` as a step output:

```python
# budpipeline/actions/deployment/helm_deploy.py
outputs = {
    "endpoint_url": f"http://{release_name}.{namespace}.svc.cluster.local:{port}",
    "release_name": release_name,
}
```

The budusecases deployment orchestrator reads step outputs and updates `ComponentDeployment.endpoint_url`.

**Option B**: In the budusecases sync endpoint — when syncing status from BudCluster, also resolve the service URL from the Helm release metadata.

### 8.3 Writing the Redis route key

After ALL components of a deployment reach `COMPLETED` status (overall deployment = `RUNNING`), budusecases writes the route to Redis:

```python
# budusecases/deployments/services.py
async def register_deployment_route(self, deployment: UseCaseDeployment):
    """Register deployment route in Redis for budgateway proxy."""
    # Get the cluster's ingress base URL (set during onboarding)
    cluster = await self.get_cluster_info(deployment.cluster_id)
    if not cluster.get("ingress_url"):
        logger.warning(f"Cluster {deployment.cluster_id} has no ingress URL, skipping route registration")
        return

    # The ingress routes by namespace path prefix
    # e.g., http://10.0.0.50/usecase-ca770191
    namespace = f"usecase-{deployment.id}"
    ingress_url = f"{cluster['ingress_url'].rstrip('/')}/{namespace}"

    route = {
        "deployment_id": str(deployment.id),
        "project_id": str(deployment.project_id),
        "ingress_url": ingress_url,
        "status": "active",
        "created_at": datetime.utcnow().isoformat() + "Z",
    }

    redis_key = f"deployment_route:{deployment.id}"
    await redis_client.set(redis_key, json.dumps(route))
    logger.info(f"Registered deployment route: {redis_key} → {ingress_url}")
```

On deployment **delete** or **stop**:
```python
await redis_client.delete(f"deployment_route:{deployment.id}")
```

---

## 9. End-to-End Data Flow

### 9.1 Deployment Creation (budadmin UI)

```
budadmin                     budapp                  budusecases
   │                           │                         │
   │ POST /budusecases/        │                         │
   │   deployments             │                         │
   │ { name, template_name,    │                         │
   │   cluster_id, project_id, │                         │
   │   components }            │                         │
   ├──────────────────────────>│                         │
   │                           │ Dapr invoke             │
   │                           │ x-user-id: <jwt user>   │
   │                           │ x-project-id: <proj>    │
   │                           ├────────────────────────>│
   │                           │                         │ Create deployment
   │                           │                         │ with project_id
   │                           │                         │ Start pipeline
   │                           │<────────────────────────│
   │<──────────────────────────│                         │
```

### 9.2 Deployment Completes → Route Registration

```
budpipeline                budusecases              Redis
   │                           │                      │
   │ step "helm_deploy"        │                      │
   │ completed (Ingress        │                      │
   │ resource created by       │                      │
   │ helm chart)               │                      │
   ├──────────────────────────>│                      │
   │                           │ All components done   │
   │                           │ Build ingress URL:    │
   │                           │ {cluster.ingress_url} │
   │                           │ /usecase-{id}         │
   │                           │                      │
   │                           │ SET deployment_route: │
   │                           ├─────────────────────>│
   │                           │                      │ keyspace
   │                           │                      │ notification
   │                           │                      │      │
                                                      │      ▼
                                                 budgateway
                                                 (subscribes to
                                                  __keyevent__:set)
                                                 Updates in-memory
                                                 deployment_routes map
```

### 9.3 API Request from External Consumer

```
Consumer           budgateway              Ingress (Traefik)    Service Pod
   │                   │                        │                   │
   │ POST /v1/usecases │                        │                   │
   │ /{deploy_id}/     │                        │                   │
   │ api/v1/chat       │                        │                   │
   │ Auth: Bearer xxx  │                        │                   │
   ├──────────────────>│                        │                   │
   │                   │ 1. Auth: hash key      │                   │
   │                   │    verify project      │                   │
   │                   │                        │                   │
   │                   │ 2. Route lookup        │                   │
   │                   │    → ingress_url       │                   │
   │                   │                        │                   │
   │                   │ 3. HTTP(S) to ingress  │                   │
   │                   │    {ingress_url}/{path} │                   │
   │                   ├───────────────────────>│                   │
   │                   │                        │  path-based route │
   │                   │                        ├──────────────────>│
   │                   │                        │<──────────────────│
   │                   │<───────────────────────│                   │
   │<──────────────────│                        │                   │
   │ (streamed response)                        │                   │
```

### 9.4 Deployment Deletion → Route Removal

```
budusecases              Redis                 budgateway
   │                       │                       │
   │ DELETE deployment     │                       │
   │ DEL deployment_route: │                       │
   ├──────────────────────>│                       │
   │                       │ keyspace notification  │
   │                       ├──────────────────────>│
   │                       │                       │ Remove from
   │                       │                       │ deployment_routes
```

---

## 10. API Surface

### External-facing (budgateway)

| Method | Path | Description |
|--------|------|-------------|
| `ANY` | `/v1/usecases/{deployment_id}/{*path}` | Proxy to deployed service |

All standard HTTP methods are passed through. The `{*path}` captures everything after the deployment ID, including nested paths and query strings.

**Example requests:**

```bash
# RAGFlow: List knowledge bases
curl -H "Authorization: Bearer bud_client_xxx" \
  https://gateway.bud.ai/v1/usecases/ca770191/api/v1/kb/list

# RAGFlow: Chat completion
curl -X POST -H "Authorization: Bearer bud_client_xxx" \
  -H "Content-Type: application/json" \
  https://gateway.bud.ai/v1/usecases/ca770191/api/v1/chat \
  -d '{"question": "What is RAG?", "stream": true}'

# vLLM: OpenAI-compatible inference
curl -X POST -H "Authorization: Bearer bud_client_xxx" \
  -H "Content-Type: application/json" \
  https://gateway.bud.ai/v1/usecases/abc12345/v1/chat/completions \
  -d '{"model": "llama-3-8b", "messages": [...]}'
```

### Internal — budadmin → budapp → budusecases

No new routes. The existing budapp proxy routes for budusecases handle deployment CRUD. The only change is adding `project_id` to the create/response schemas.

---

## 11. Security Considerations

### 11.1 Authentication

- Reuses existing budgateway API key auth (`require_api_key` middleware)
- SHA256("bud-" + key) hash lookup — same as inference routes
- No new auth mechanism needed

### 11.2 Authorization (Project Scope)

- API key's `api_key_project_id` must match deployment's `project_id`
- Enforced in the budgateway proxy handler before any upstream call
- A user with a project API key can access ALL deployments in that project (not deployment-level granularity in v1)

### 11.3 Ingress Security

- No cluster credentials in budgateway or Redis — only ingress URLs (not secrets)
- Ingress controller is on the cluster's internal/private network (not exposed to public internet in default setup)
- Traffic between budgateway and ingress can be TLS-encrypted (cert-manager + Let's Encrypt for public, self-signed for private)
- Ingress controller does NOT perform auth — all auth is handled by budgateway before the proxy call
- Defense in depth (optional): add a shared secret header (`X-Gateway-Token`) that Traefik validates via middleware, ensuring only budgateway can reach the ingress

### 11.4 Ingress Isolation

- Each deployment gets its own namespace (`usecase-{id}`) and Ingress resource
- Traefik routes by path prefix — deployments cannot access each other's services
- Network policies can further restrict ingress-to-service traffic per namespace

### 11.5 Header Stripping

- Internal headers (`x-tensorzero-*`) are stripped before forwarding to upstream service
- Hop-by-hop headers stripped per RFC 9110
- `Host` header replaced to match upstream

---

## 12. Performance Considerations

### 12.1 Latency Budget

| Component | Target |
|-----------|--------|
| Auth middleware (in-memory lookup) | < 0.01ms |
| Route resolution (in-memory HashMap) | < 0.01ms |
| HTTP to ingress (network hop) | ~1-20ms (same network) |
| Ingress → service pod (cluster internal) | < 1ms |
| **Total gateway overhead** | **< 25ms** |

Fastest possible path. The ingress controller is purpose-built for proxying — connection pooling, keep-alive, and efficient routing are built in.

### 12.2 Connection Pooling

budgateway's `reqwest::Client` handles HTTP connection pooling natively. Connections to ingress IPs are kept alive, avoiding TCP/TLS handshake on every request. No special per-cluster client needed — ingress endpoints are plain HTTP(S) URLs.

### 12.3 Ingress Controller Scaling

If a single ingress controller becomes a bottleneck (unlikely for v1):
- Traefik supports horizontal scaling via multiple replicas
- LoadBalancer distributes across ingress pods
- Each ingress pod handles thousands of concurrent connections

### 12.4 Body Handling

- Request bodies: Read into memory (10MB limit for v1)
- Response bodies: Stream back to consumer (zero-copy via `Body::from_stream`)
- For v2: Stream request bodies too (needed for large file uploads)

---

## 13. Implementation Phases

### Phase 1: Foundation (Backend)

1. **budusecases**: Add `project_id` to model + migration + schemas
2. **budapp**: Forward `x-user-id` and `x-project-id` headers in Dapr calls
3. **budapp**: Accept `project_id` in deployment create route, pass to budusecases
4. **budusecases**: Populate `endpoint_url` on ComponentDeployment after helm deploy completes

### Phase 2: Ingress + Route Registration

5. **budcluster**: Deploy Traefik ingress controller during cluster onboarding
6. **budcluster**: Store `ingress_url` (LoadBalancer IP) on cluster record
7. **Use-case helm charts**: Add `Ingress` resource template (path-based routing)
8. **budusecases**: Write `deployment_route:{id}` to Redis when deployment reaches RUNNING
9. **budusecases**: Delete `deployment_route:{id}` on deployment delete/stop

### Phase 3: Gateway Proxy (Rust)

10. **budgateway**: Add `UseCaseProxyState` (deployment_routes) to AppStateData
11. **budgateway**: Add `deployment_route:*` to Redis client (initial load + keyspace events)
12. **budgateway**: Implement `usecase_proxy_handler` (auth check + HTTP proxy to ingress URL)
13. **budgateway**: Register `/v1/usecases/{deployment_id}/{*path}` route with auth middleware

### Phase 4: Frontend & Polish

14. **budadmin**: Add project selector to deployment creation flow
15. **budadmin**: Show endpoint URL and access instructions on deployment detail page
16. **budadmin**: Generate API key flow scoped to project (may already exist)
17. **Documentation**: API usage examples, architecture update

### Phase 5: Hardening (v2, optional)

18. **budcluster**: TLS for ingress (cert-manager + Let's Encrypt or self-signed)
19. **budgateway**: Streaming request body support (large file uploads)
20. **budgateway**: Per-deployment rate limiting
21. **Traefik**: Shared secret header middleware (defense-in-depth auth)
22. **budcluster**: Ingress controller health monitoring + alerting

---

## 14. Key Files Reference

| File | Purpose |
|------|---------|
| `services/budgateway/gateway/src/main.rs` | Route registration, middleware layers |
| `services/budgateway/tensorzero-internal/src/auth.rs` | API key auth middleware, AuthMetadata |
| `services/budgateway/tensorzero-internal/src/redis_client.rs` | Redis keyspace notifications (add `deployment_route:*`) |
| `services/budcluster/budcluster/cluster_ops/services.py` | Cluster registration (add ingress controller deploy + store ingress_url) |
| `services/budcluster/budcluster/cluster_ops/kubernetes.py` | Existing K8s client management, Helm operations |
| `services/budusecases/budusecases/deployments/models.py` | UseCaseDeployment model (add project_id) |
| `services/budusecases/budusecases/deployments/schemas.py` | Pydantic schemas (add project_id) |
| `services/budusecases/templates/*.yaml` | Use-case helm chart templates (add Ingress resource) |
| `services/budapp/budapp/workflow_ops/budusecases_service.py` | Dapr proxy service (add headers) |
| `services/budapp/budapp/workflow_ops/budusecases_routes.py` | budapp proxy routes (pass project_id) |
| `services/budapp/budapp/credential_ops/models.py` | APIKeyCredential with project_id (reference) |

---

## 15. Open Questions

1. **Primary component selection**: For multi-component deployments (e.g., RAG = LLM + embedder + vector_db + RAGFlow), which component's `endpoint_url` becomes the Ingress target? Proposal: Use the template's metadata to designate a `primary_component` field, or infer from component type (e.g., the `helm` type component is always the primary entrypoint).

2. **Multiple exposed ports**: Some services expose multiple ports (e.g., RAGFlow has 9380 for API and 80 for UI). Should we create multiple Ingress paths per deployment, or always proxy to a single designated port?

3. **Request body size limit**: 10MB for v1 is reasonable for API calls, but may be insufficient for file uploads (e.g., RAG document ingestion). Traefik supports configurable body size limits per-route — should we increase for specific deployment types?

4. **Existing deployments backfill**: Deployments created before `project_id` was added will have `project_id = NULL`. Should these be inaccessible via the proxy (safe default) or should we provide a migration tool to associate them with projects?

5. **Existing clusters backfill**: Clusters registered before this feature exists won't have an ingress controller. Should we add a migration path that deploys Traefik to existing clusters, or require manual re-onboarding?

6. **Ingress path stripping**: When Traefik routes `/usecase-ca770191/api/v1/chat` to `ragflow-server:9380`, should it strip the `/usecase-ca770191` prefix (so the service sees `/api/v1/chat`) or forward the full path? Most services expect requests at their root — stripping is likely needed. Traefik supports this via `StripPrefix` middleware.

7. **Ingress controller per cluster vs shared**: Should every cluster get its own Traefik instance, or should clusters in the same network share one? Per-cluster is simpler (no cross-cluster routing) and is the default.

8. **Health checking**: Should budgateway verify the ingress URL is reachable before adding it to the in-memory store? Or handle failures gracefully at proxy time (return 502 to consumer)?
