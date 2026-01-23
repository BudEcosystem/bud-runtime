# budapp - Low-Level Design
---

## 1. Document Overview

### 1.1 Purpose

This LLD provides build-ready technical specifications for budapp, the core API service of Bud AI Foundry. Developers should be able to implement new features, debug issues, and extend functionality directly from this document with minimal assumptions.

### 1.2 Scope

**In Scope:**
- User authentication and session management via Keycloak
- Multi-tenant organization and project management
- Model endpoint lifecycle (create, configure, deploy, delete)
- Credential storage for cloud and proprietary providers
- Audit trail with tamper-proof hash chain
- Billing plan management and usage tracking
- Guardrail profile configuration and deployment
- Prompt versioning and management
- Request routing configuration
- Proxy routes to specialized services (budcluster, budpipeline, budeval)

**Out of Scope:**
- Actual model inference (handled by budgateway)
- Cluster provisioning logic (handled by budcluster)
- Performance optimization algorithms (handled by budsim)
- Time-series metrics storage (handled by budmetrics)

### 1.3 Intended Audience

| Audience | What They Need |
|----------|----------------|
| Developers | Implementation details, API contracts, database schemas |
| Reviewers | Architecture decisions, trade-offs, security model |
| Security | Auth flows, encryption mechanisms, audit trail design |
| Operations | Deployment config, monitoring hooks, runbooks |

### 1.4 References

| Document | Description |
|----------|-------------|
| [High-Level Architecture](../architecture/high-level-architecture.md) | System overview |
| [Main LLD Index](../architecture/low-level-design.md) | Cross-cutting concerns |
| [IAM Architecture](../security/iam-architecture.md) | Identity management |

---

## 2. System Context & Assumptions

### 2.1 Business Assumptions

- Users operate within multi-tenant organizations with project-based isolation
- Each user belongs to one primary tenant but may have access to multiple
- Billing is user-centric with plan-based quotas (tokens, cost limits)
- Audit records must be immutable and verifiable for compliance

### 2.2 Technical Assumptions

- Keycloak is always available for authentication (critical dependency)
- PostgreSQL provides ACID guarantees for all transactional data
- Dapr sidecar is co-located with every budapp instance
- Redis/Valkey is available for session caching and pub/sub
- All inter-service communication uses Dapr service invocation

### 2.3 Constraints

| Constraint Type | Description | Impact |
|-----------------|-------------|--------|
| Latency | API responses < 500ms for CRUD operations | Use caching for frequently accessed data |
| Memory | Service runs in 256MB-1GB pods | Limit in-memory caching, stream large responses |
| Security | Credentials must be encrypted at rest | RSA/AES encryption for all sensitive data |
| Compliance | Audit records must be tamper-evident | SHA256 hash chain for audit trail |

### 2.4 External Dependencies

| Dependency | Type | Failure Impact | Fallback Strategy |
|------------|------|----------------|-------------------|
| Keycloak | Required | No authentication, all requests fail | Return 503, queue requests |
| PostgreSQL | Required | No data persistence | Return 503, no fallback |
| Redis/Valkey | Optional | No session cache, slower auth | Fall back to DB for sessions |
| budcluster | Optional | Cannot deploy/manage clusters | Return partial data, queue operations |
| budsim | Optional | Cannot optimize deployments | Use default configurations |
| budpipeline | Optional | Cannot execute workflows | Return error, manual retry |
| budmodel | Optional | Cannot fetch model metadata | Use cached data |
| budmetrics | Optional | No usage sync | Queue sync operations |
| budnotify | Optional | No notifications sent | Queue notifications |

---

## 3. Detailed Architecture

### 3.1 Component Overview

![Budapp component overview](./images/buapp-comp-overview.png)

### 3.2 Component Breakdown

#### 3.2.1 Authentication Module (`auth/`)

| Property | Value |
|----------|-------|
| **Responsibility** | Handle user authentication, OAuth flows, and JWT token management |
| **Owner Module** | `budapp/auth/` |

**Inputs:**
| Input | Source | Format | Validation |
|-------|--------|--------|------------|
| Login credentials | HTTP POST `/auth/login` | `{email, password}` | Email format, password min length |
| OAuth callback | HTTP GET `/auth/oauth/callback` | Query params `code`, `state` | State token verification |
| Refresh token | HTTP POST `/auth/refresh` | `{refresh_token}` | Token signature, expiry |

**Outputs:**
| Output | Destination | Format | Guarantees |
|--------|-------------|--------|------------|
| Access token | HTTP response | JWT | Valid for 15 minutes |
| Refresh token | HTTP response | JWT | Valid for 7 days |
| User session | Redis via Dapr | JSON | TTL matches token expiry |

**Internal Sub-modules:**
- `auth_routes.py` - Login, logout, session endpoints
- `oauth_routes.py` - OAuth 2.0 / OIDC flows
- `token.py` - JWT creation and validation
- `services.py` - User authentication logic

**Error Handling:**
| Error Condition | Response | Recovery |
|-----------------|----------|----------|
| Invalid credentials | 401 Unauthorized | User retries with correct credentials |
| Expired token | 401 Unauthorized | Client uses refresh token |
| Keycloak unavailable | 503 Service Unavailable | Retry with exponential backoff |

**Scalability:**
- Horizontal: Yes, stateless with Redis session store
- Vertical: Low memory footprint, CPU-bound during token validation
- Bottlenecks: Keycloak JWKS endpoint calls (mitigated by caching public keys)

#### 3.2.2 Audit Module (`audit_ops/`)

| Property | Value |
|----------|-------|
| **Responsibility** | Create immutable audit records with hash chain for tamper detection |
| **Owner Module** | `budapp/audit_ops/` |

**Inputs:**
| Input | Source | Format | Validation |
|-------|--------|--------|------------|
| Audit event | Internal service calls | `AuditRecordCreate` schema | Required fields present |
| Query filters | HTTP GET `/audit` | Query params | Date range, resource type |

**Outputs:**
| Output | Destination | Format | Guarantees |
|--------|-------------|--------|------------|
| Audit record | PostgreSQL | `audit_trail` table | Immutable, hash-chained |
| Verification result | HTTP response | Boolean + details | Cryptographic verification |

**Internal Sub-modules:**
- `audit_routes.py` - Audit record retrieval, export, verify
- `audit_logger.py` - Async audit logging service
- `hash_utils.py` - SHA256 hash chain implementation
- `models.py` - AuditTrail SQLAlchemy model

**Error Handling:**
| Error Condition | Response | Recovery |
|-----------------|----------|----------|
| Hash chain broken | Verification returns tampered records | Manual investigation required |
| Write failure | 500 Internal Error | Retry with same record |

**Scalability:**
- Horizontal: Yes, audit writes are append-only
- Vertical: Memory increases with batch verification
- Bottlenecks: Hash verification of large audit ranges

#### 3.2.3 Billing Module (`billing_ops/`)

| Property | Value |
|----------|-------|
| **Responsibility** | Manage billing plans, track usage, enforce quotas, trigger alerts |
| **Owner Module** | `budapp/billing_ops/` |

**Inputs:**
| Input | Source | Format | Validation |
|-------|--------|--------|------------|
| Usage data | budmetrics via Dapr | Token counts | Positive integers |
| Plan assignment | HTTP POST `/billing/assign` | `{user_id, plan_id}` | Valid UUIDs |
| Alert thresholds | HTTP POST `/billing/alerts` | Percentage values | 0-100 range |

**Outputs:**
| Output | Destination | Format | Guarantees |
|--------|-------------|--------|------------|
| Usage summary | HTTP response | JSON with totals | Eventually consistent |
| Alert notifications | budnotify via Dapr | Event payload | At-least-once delivery |
| Suspension status | User record | Boolean flag | Immediate enforcement |

**Internal Sub-modules:**
- `routes.py` - Billing endpoints
- `usage_sync.py` - Periodic sync from budmetrics
- `services.py` - Quota enforcement, alert triggering

**Error Handling:**
| Error Condition | Response | Recovery |
|-----------------|----------|----------|
| Usage sync failure | Log warning, retry | Background job retries |
| Over-quota request | 429 Too Many Requests | User upgrades plan or waits |

**Scalability:**
- Horizontal: Yes, usage counters in Redis
- Vertical: Memory for batch usage aggregation
- Bottlenecks: High-frequency usage updates

### 3.3 Component Interaction Diagrams

#### 3.3.1 User Authentication - Happy Path

![User Authentication - Happy Path](./images/budapp-auth-happy-path.png)

#### 3.3.2 User Authentication - Failure Path

![User Authentication - Failure Path](./images/budapp-auth-failure-path.png)

#### 3.3.3 Endpoint Deployment Flow

![Endpoint Deployment Flow](./images/budapp-endpoint-deployment.png)

#### 3.3.4 Endpoint State Diagram

![Endpoint State Diagram](./images/budapp-endpoint-states.png)

---

## 4. Data Design

### 4.1 Data Models

#### 4.1.1 Tenant

**Table:** `tenant`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, NOT NULL | Primary identifier |
| `name` | VARCHAR(255) | NOT NULL | Tenant display name |
| `alias` | VARCHAR(100) | UNIQUE, NOT NULL | URL-safe alias |
| `type` | ENUM | NOT NULL | ENTERPRISE, TEAM, INDIVIDUAL |
| `status` | ENUM | NOT NULL | ACTIVE, INACTIVE |
| `settings` | JSONB | NULL | Configuration options |
| `created_at` | TIMESTAMP(tz) | NOT NULL | Creation timestamp |
| `updated_at` | TIMESTAMP(tz) | NOT NULL | Last modification |

**Indexes:**
| Index Name | Columns | Type | Purpose |
|------------|---------|------|---------|
| `ix_tenant_alias` | `alias` | B-tree | Fast lookup by alias |
| `ix_tenant_status` | `status` | B-tree | Filter active tenants |

#### 4.1.2 User

**Table:** `user`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, NOT NULL | Primary identifier |
| `auth_id` | UUID | UNIQUE, NOT NULL | Keycloak user ID |
| `tenant_id` | UUID | FK, NOT NULL | Parent tenant |
| `client_id` | UUID | FK, NOT NULL | OAuth client |
| `name` | VARCHAR(255) | NOT NULL | Display name |
| `email` | VARCHAR(255) | UNIQUE, NOT NULL | Email address |
| `status` | ENUM | NOT NULL | ACTIVE, PENDING, INACTIVE |
| `is_admin` | BOOLEAN | NOT NULL, DEFAULT FALSE | Admin flag |
| `email_verified` | BOOLEAN | NOT NULL | Email verified |
| `created_at` | TIMESTAMP(tz) | NOT NULL | Creation timestamp |
| `updated_at` | TIMESTAMP(tz) | NOT NULL | Last modification |

**Indexes:**
| Index Name | Columns | Type | Purpose |
|------------|---------|------|---------|
| `ix_user_email` | `email` | B-tree | Fast lookup by email |
| `ix_user_auth_id` | `auth_id` | B-tree | Keycloak ID lookup |
| `ix_user_tenant_id` | `tenant_id` | B-tree | List users by tenant |

#### 4.1.3 Project

**Table:** `project`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, NOT NULL | Primary identifier |
| `name` | VARCHAR(255) | NOT NULL | Project name |
| `tenant_id` | UUID | FK, NOT NULL | Parent tenant |
| `description` | TEXT | NULL | Project description |
| `status` | ENUM | NOT NULL | ACTIVE, DELETED |
| `tags` | JSONB | NULL | Metadata tags |
| `created_at` | TIMESTAMP(tz) | NOT NULL | Creation timestamp |
| `updated_at` | TIMESTAMP(tz) | NOT NULL | Last modification |

**Indexes:**
| Index Name | Columns | Type | Purpose |
|------------|---------|------|---------|
| `ix_project_tenant_id` | `tenant_id` | B-tree | List projects by tenant |
| `ix_project_status` | `status` | B-tree | Filter active projects |

#### 4.1.4 Endpoint

**Table:** `endpoint`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, NOT NULL | Primary identifier |
| `name` | VARCHAR(255) | NOT NULL | Endpoint name |
| `project_id` | UUID | FK, NOT NULL | Parent project |
| `model_id` | UUID | FK, NOT NULL | Model reference |
| `cloud_model_id` | UUID | FK, NULL | Cloud model (if cloud-hosted) |
| `cluster_id` | UUID | FK, NULL | Target cluster (if self-hosted) |
| `credential_id` | UUID | FK, NULL | Provider credential |
| `user_id` | UUID | FK, NOT NULL | Creator |
| `status` | ENUM | NOT NULL | PENDING, DEPLOYING, RUNNING, ERROR, STOPPED |
| `endpoint_type` | ENUM | NOT NULL | SELF_HOSTED, CLOUD_HOSTED |
| `inference_config` | JSONB | NULL | Runtime config (TP, PP, batch) |
| `pricing` | JSONB | NULL | Pricing configuration |
| `tags` | JSONB | NULL | Metadata tags |
| `created_at` | TIMESTAMP(tz) | NOT NULL | Creation timestamp |
| `updated_at` | TIMESTAMP(tz) | NOT NULL | Last modification |

**Indexes:**
| Index Name | Columns | Type | Purpose |
|------------|---------|------|---------|
| `ix_endpoint_project_id` | `project_id` | B-tree | List endpoints by project |
| `ix_endpoint_status` | `status` | B-tree | Filter by status |
| `ix_endpoint_user_id` | `user_id` | B-tree | List user's endpoints |

#### 4.1.5 AuditTrail

**Table:** `audit_trail`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, NOT NULL | Primary identifier |
| `user_id` | UUID | FK, NULL | Acting user (null for system) |
| `actioned_by` | UUID | FK, NULL | Admin acting on behalf |
| `action` | VARCHAR(50) | NOT NULL | CREATE, UPDATE, DELETE, etc. |
| `resource_type` | VARCHAR(50) | NOT NULL | PROJECT, ENDPOINT, USER, etc. |
| `resource_id` | UUID | NOT NULL | Affected resource ID |
| `resource_name` | VARCHAR(255) | NULL | Human-readable name |
| `timestamp` | TIMESTAMP(tz) | NOT NULL | Event timestamp |
| `details` | JSONB | NULL | Additional context |
| `ip_address` | VARCHAR(45) | NULL | Client IP |
| `previous_state` | JSONB | NULL | State before change |
| `new_state` | JSONB | NULL | State after change |
| `record_hash` | VARCHAR(64) | NOT NULL | SHA256 hash for integrity |
| `created_at` | TIMESTAMP(tz) | NOT NULL | Record creation time |

**Indexes:**
| Index Name | Columns | Type | Purpose |
|------------|---------|------|---------|
| `ix_audit_user_id` | `user_id` | B-tree | Filter by user |
| `ix_audit_resource` | `resource_type, resource_id` | B-tree | Filter by resource |
| `ix_audit_timestamp` | `timestamp` | B-tree | Time-based queries |

**Note:** SQLAlchemy event listener prevents UPDATE/DELETE operations on this table.

#### 4.1.6 Entity Relationship Diagram

![ER Diagram](./images/budapp-er-diagram.png)

### 4.2 Data Flow

#### 4.2.1 Data Lifecycle

| Stage | Location | Retention | Transition Trigger |
|-------|----------|-----------|-------------------|
| Created | PostgreSQL | Indefinite | User/system action |
| Active | PostgreSQL | While in use | Status change |
| Soft-deleted | PostgreSQL (status=DELETED) | 30 days | User deletion |
| Archived | PostgreSQL | Per compliance policy | Age > retention period |
| Purged | Removed | N/A | Retention policy expiry |

#### 4.2.2 Read/Write Paths

**Write Path:**
```
1. Request received by FastAPI route
2. Pydantic schema validates input
3. Service layer applies business logic
4. CRUD layer constructs SQLAlchemy query
5. PostgreSQL executes transaction
6. Audit record created (async)
7. Cache invalidated (if applicable)
8. Response returned
```

**Read Path:**
```
1. Request received by FastAPI route
2. Check cache (Redis) for recent data
3. If cache miss, query PostgreSQL
4. Transform to Pydantic response schema
5. Update cache (if cacheable)
6. Return response
```

#### 4.2.3 Caching Strategy

| Cache Layer | Technology | TTL | Invalidation Strategy |
|-------------|------------|-----|----------------------|
| Session cache | Redis (via Dapr) | Token lifetime | On logout, token refresh |
| User profile | Redis | 5 minutes | On user update |
| Model metadata | Redis | 1 hour | On model registry sync |
| Billing quotas | Redis | 1 minute | On usage update |

---

## 5. API & Interface Design

### 5.1 Internal APIs

#### 5.1.1 Authentication

**`POST /auth/login`**

| Property | Value |
|----------|-------|
| **Description** | Authenticate user with email and password |
| **Authentication** | None (public endpoint) |
| **Rate Limit** | 10 requests/minute per IP |
| **Timeout** | 10 seconds |

**Request:**
```json
{
  "email": "string - user email address",
  "password": "string - user password"
}
```

**Response (Success):**
```json
{
  "success": true,
  "data": {
    "access_token": "string - JWT access token",
    "refresh_token": "string - JWT refresh token",
    "user": {
      "id": "uuid",
      "email": "string",
      "name": "string"
    }
  }
}
```

**Response (Error):**
| Status Code | Error Code | Description | Retry? |
|-------------|------------|-------------|--------|
| 400 | `VALIDATION_ERROR` | Invalid email format | No |
| 401 | `INVALID_CREDENTIALS` | Wrong email or password | No |
| 429 | `RATE_LIMITED` | Too many attempts | Yes, after cooldown |
| 503 | `SERVICE_UNAVAILABLE` | Keycloak unavailable | Yes |

#### 5.1.2 Endpoints

**`POST /endpoints`**

| Property | Value |
|----------|-------|
| **Description** | Create and deploy a new model endpoint |
| **Authentication** | JWT Bearer token |
| **Rate Limit** | 10 requests/minute per user |
| **Timeout** | 30 seconds |

**Request:**
```json
{
  "name": "string - endpoint name",
  "project_id": "uuid - parent project",
  "model_id": "uuid - model to deploy",
  "cluster_id": "uuid - target cluster (for self-hosted)",
  "endpoint_type": "SELF_HOSTED | CLOUD_HOSTED",
  "inference_config": {
    "tensor_parallel": "integer - TP degree",
    "pipeline_parallel": "integer - PP degree",
    "max_batch_size": "integer - batch size"
  }
}
```

**Response (Success):**
```json
{
  "success": true,
  "data": {
    "id": "uuid - endpoint ID",
    "name": "string",
    "status": "DEPLOYING",
    "workflow_id": "uuid - deployment workflow"
  }
}
```

**Response (Error):**
| Status Code | Error Code | Description | Retry? |
|-------------|------------|-------------|--------|
| 400 | `VALIDATION_ERROR` | Invalid configuration | No |
| 404 | `NOT_FOUND` | Project, model, or cluster not found | No |
| 409 | `CONFLICT` | Endpoint name already exists | No |
| 500 | `INTERNAL_ERROR` | Deployment failed to start | Yes |

### 5.2 External Integrations

#### 5.2.1 Keycloak

| Property | Value |
|----------|-------|
| **Purpose** | User authentication, token validation, SSO |
| **Auth Mechanism** | OIDC / OAuth 2.0 |
| **Rate Limits** | 100 requests/second |
| **SLA** | 99.9% availability |

**Failure Fallback:**
- Cache JWKS public keys for up to 1 hour
- Return 503 for login attempts
- Existing sessions remain valid until token expiry

#### 5.2.2 budcluster

| Property | Value |
|----------|-------|
| **Purpose** | Cluster management, model deployment |
| **Auth Mechanism** | Dapr API token |
| **Rate Limits** | No limit (internal service) |
| **SLA** | Best effort |

**Failure Fallback:**
- Queue deployment requests
- Return partial endpoint data
- Poll for status recovery

---

## 6. Logic & Algorithm Details

### 6.1 Audit Hash Chain

**Purpose:** Ensure audit records are tamper-evident by linking each record to the previous via cryptographic hash.

**Inputs:**
- `current_record`: Audit record data (action, resource, timestamp, etc.)
- `previous_hash`: Hash of the previous audit record (or seed for first record)

**Outputs:**
- `record_hash`: SHA256 hash that becomes `previous_hash` for next record

**Algorithm (Step-by-Step):**

1. Serialize record fields to canonical JSON (sorted keys, no whitespace)
2. Concatenate: `previous_hash + serialized_record`
3. Compute SHA256 hash of concatenated string
4. Store hash with record

**Pseudocode:**
```python
def compute_audit_hash(record: AuditRecord, previous_hash: str) -> str:
    # Canonical serialization
    fields = {
        "user_id": str(record.user_id),
        "action": record.action,
        "resource_type": record.resource_type,
        "resource_id": str(record.resource_id),
        "timestamp": record.timestamp.isoformat(),
        "details": json.dumps(record.details, sort_keys=True)
    }
    serialized = json.dumps(fields, sort_keys=True, separators=(',', ':'))

    # Chain with previous hash
    data = previous_hash + serialized

    # Compute hash
    return hashlib.sha256(data.encode()).hexdigest()
```

**Decision Tree:**
```
Is this the first audit record?
├── Yes → Use seed hash "0" * 64
└── No → Fetch previous record's hash
         └── Compute hash with previous_hash
```

**Edge Cases:**
| Edge Case | Behavior | Rationale |
|-----------|----------|-----------|
| First record in database | Use zero-filled 64-char string as seed | Deterministic starting point |
| Null user_id (system action) | Serialize as "null" | Consistent serialization |
| Unicode in details | UTF-8 encode before hashing | Byte-level consistency |
| Concurrent writes | Database transaction ensures ordering | SERIALIZABLE isolation |

### 6.2 Billing Quota Enforcement

**Purpose:** Prevent users from exceeding their token/cost quotas.

**Inputs:**
- `user_id`: User making the request
- `requested_tokens`: Tokens for current request

**Outputs:**
- `allowed`: Boolean indicating if request can proceed
- `remaining`: Tokens remaining in quota

**Algorithm (Step-by-Step):**

1. Fetch user's current billing period from `user_billing`
2. Get usage from Redis or sync from budmetrics
3. Calculate remaining = quota - used
4. If requested > remaining, return denied
5. If within 10% of quota, trigger warning alert
6. Return allowed with remaining tokens

**Pseudocode:**
```python
async def check_quota(user_id: UUID, requested_tokens: int) -> QuotaResult:
    billing = await get_user_billing(user_id)

    if billing.is_suspended:
        return QuotaResult(allowed=False, reason="Account suspended")

    usage = await get_usage_from_cache(user_id)
    if usage is None:
        usage = await sync_usage_from_budmetrics(user_id)

    quota = billing.custom_token_quota or billing.plan.monthly_token_quota
    remaining = quota - usage.total_tokens

    if requested_tokens > remaining:
        return QuotaResult(allowed=False, remaining=remaining)

    # Check alert thresholds
    usage_percent = (usage.total_tokens / quota) * 100
    for alert in billing.alerts:
        if usage_percent >= alert.threshold and not alert.triggered:
            await trigger_alert(alert)

    return QuotaResult(allowed=True, remaining=remaining - requested_tokens)
```

---

## 7. GenAI/ML-Specific Design

> *budapp primarily handles API management. GenAI-specific logic is delegated to specialized services.*

### 7.1 Model Deployment Flow

#### 7.1.1 Deployment Pipeline

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   budapp    │───▶│   budsim    │───▶│ budcluster  │───▶│   Runtime   │
│  (create)   │    │ (optimize)  │    │  (deploy)   │    │  (verify)   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

| Stage | Duration | Rollback Point | Validation |
|-------|----------|----------------|------------|
| Create endpoint record | < 1s | Yes | Schema validation |
| Request optimization | 5-30s | Yes | Config feasibility |
| Deploy to cluster | 1-10min | Yes | Deployment healthy |
| Verify runtime | 30s | Yes | Health check passes |

#### 7.1.2 Model Configuration

| Parameter | Source | Default | Constraints |
|-----------|--------|---------|-------------|
| `max_model_len` | Calculated | (input + output) * 1.1 | Min: 128, Max: model limit |
| `tensor_parallel` | budsim | 1 | Must divide GPU count |
| `pipeline_parallel` | budsim | 1 | TP * PP ≤ total GPUs |
| `max_batch_size` | budsim | 32 | Memory constrained |

### 7.2 Inference Request Handling

> *Inference is handled by budgateway. budapp manages endpoint configuration.*

#### 7.2.1 Request Routing Logic

| Condition | Route To | Rationale |
|-----------|----------|-----------|
| Cloud-hosted endpoint | Provider API via budgateway | No cluster management |
| Self-hosted endpoint | Cluster runtime via budgateway | Direct to deployed model |
| Router configured | Multiple endpoints with weights | Load balancing |

#### 7.2.2 Token Budget Management

| Metric | Calculation | Limit Enforcement |
|--------|-------------|-------------------|
| Input tokens | Counted by budgateway | Reject if over budget |
| Output tokens | Counted by budgateway | Stop generation at limit |
| Total usage | Synced to budapp periodically | Billing quota enforcement |

### 7.3 Safety & Guardrails

#### 7.3.1 Guardrail Configuration (budapp responsibility)

| Entity | Purpose | Managed By |
|--------|---------|------------|
| GuardrailProbe | Detection types (jailbreak, PII, etc.) | Seeded from provider |
| GuardrailProfile | User-configured detection settings | User via API |
| GuardrailDeployment | Active guardrail on endpoint | Linked to endpoint |

#### 7.3.2 Guardrail Enforcement (budgateway responsibility)

| Check | Configured In | Enforced By |
|-------|---------------|-------------|
| Input validation | GuardrailProfile | budgateway pre-processing |
| Output filtering | GuardrailProfile | budgateway post-processing |
| Severity threshold | GuardrailDeployment | budgateway decision |

---

## 8. Configuration & Environment Design

### 8.1 Environment Variables

| Variable | Required | Default | Description | Sensitive |
|----------|----------|---------|-------------|-----------|
| `DATABASE_URL` | Yes | - | PostgreSQL connection string | Yes |
| `KEYCLOAK_URL` | Yes | - | Keycloak server URL | No |
| `KEYCLOAK_REALM` | Yes | `bud` | Keycloak realm name | No |
| `KEYCLOAK_CLIENT_ID` | Yes | - | OAuth client ID | No |
| `KEYCLOAK_CLIENT_SECRET` | Yes | - | OAuth client secret | Yes |
| `DAPR_HTTP_ENDPOINT` | No | `http://localhost:3500` | Dapr sidecar endpoint | No |
| `APP_API_TOKEN` | Yes | - | Internal service auth token | Yes |
| `LOG_LEVEL` | No | `INFO` | Logging verbosity | No |
| `MAX_SYNC_INTERVAL` | No | `300` | Config sync interval (seconds) | No |

### 8.2 Feature Flags

| Flag | Default | Description | Rollout Strategy |
|------|---------|-------------|------------------|
| `enable_billing_enforcement` | on | Enforce token quotas | Gradual per tenant |
| `enable_audit_hash_chain` | on | Hash chain for audits | All or nothing |
| `enable_guardrail_sync` | on | Sync guardrail definitions | Per environment |

### 8.3 Secrets Management

| Secret | Storage | Rotation | Access |
|--------|---------|----------|--------|
| Database password | Kubernetes Secret | 90 days | budapp pods only |
| Keycloak client secret | Kubernetes Secret | 90 days | budapp pods only |
| APP_API_TOKEN | Kubernetes Secret | On demand | All platform services |
| RSA encryption keys | Dapr secret store | Annually | budcluster only |

### 8.4 Environment Differences

| Aspect | Development | Staging | Production |
|--------|-------------|---------|------------|
| Database | Local PostgreSQL | Shared PostgreSQL | HA PostgreSQL |
| Keycloak | Local instance | Shared instance | HA cluster |
| Replicas | 1 | 2 | 3+ |
| Log level | DEBUG | INFO | INFO |
| Rate limits | Disabled | Relaxed | Enforced |

---

## 9. Security Design

### 9.1 Authentication

| Flow | Mechanism | Token Lifetime | Refresh Strategy |
|------|-----------|----------------|------------------|
| User login | JWT via Keycloak | 15 minutes | Refresh token (7 days) |
| Service-to-service | Dapr API token | Indefinite | Manual rotation |
| Internal API | APP_API_TOKEN header | Indefinite | Manual rotation |

### 9.2 Authorization

| Resource | Permission Model | Enforcement Point |
|----------|------------------|-------------------|
| Projects | RBAC (owner, member) | Route middleware |
| Endpoints | Project membership | Route middleware |
| Audit records | Admin only | Route middleware |
| Billing | Self + admin | Route middleware |

### 9.3 Encryption

| Data Type | At Rest | In Transit | Key Management |
|-----------|---------|------------|----------------|
| Passwords | Keycloak managed (bcrypt) | TLS 1.3 | Keycloak internal |
| API credentials | AES-256-GCM | TLS 1.3 | Dapr secret store |
| Cloud credentials | RSA + AES hybrid | TLS 1.3 | budcluster crypto-keys |
| Session data | Plaintext in Redis | TLS 1.3 | N/A |

### 9.4 Input Validation

| Input | Validation Rules | Sanitization |
|-------|------------------|--------------|
| Email | RFC 5322 format | Lowercase, trim |
| UUID | UUID v4 format | None |
| Names | 1-255 chars, no special chars | Trim whitespace |
| JSON config | Schema validation | None |

### 9.5 Threat Model (Basic)

| Threat | Likelihood | Impact | Mitigation |
|--------|------------|--------|------------|
| Credential stuffing | High | High | Rate limiting, MFA via Keycloak |
| SQL injection | Low | Critical | Parameterized queries (SQLAlchemy) |
| XSS | Medium | Medium | JSON-only responses, no HTML |
| Audit tampering | Low | High | Hash chain, immutable records |
| Token theft | Medium | High | Short-lived tokens, HTTPS only |

---

## 10. Performance & Scalability

### 10.1 Expected Load

| Metric | Normal | Peak | Burst |
|--------|--------|------|-------|
| Requests/sec | 50 | 200 | 500 |
| Concurrent users | 100 | 500 | 1000 |
| Database connections | 10 | 50 | 100 |

### 10.2 Bottlenecks

| Bottleneck | Trigger Condition | Symptom | Mitigation |
|------------|-------------------|---------|------------|
| Database connections | > 80% pool used | Slow queries, timeouts | Increase pool, add replicas |
| Keycloak latency | Token validation spike | Auth delays | Cache JWKS, reduce validation |
| Audit writes | High activity burst | Write queue grows | Batch inserts, async processing |

### 10.3 Caching Strategy

| Cache | Hit Rate Target | Eviction Policy | Warming Strategy |
|-------|-----------------|-----------------|------------------|
| Session | 99% | TTL (token expiry) | On login |
| User profile | 90% | TTL (5 min) | On first access |
| JWKS public keys | 99% | TTL (1 hour) | On startup |

### 10.4 Concurrency Handling

| Resource | Concurrency Model | Lock Strategy | Deadlock Prevention |
|----------|-------------------|---------------|---------------------|
| Database | Connection pool | Row-level locks | Timeout + retry |
| Redis | Single-threaded | Atomic operations | N/A |
| Audit chain | Sequential writes | Advisory lock | Single writer |

### 10.5 Scaling Strategy

| Dimension | Trigger | Target | Cooldown |
|-----------|---------|--------|----------|
| Horizontal (pods) | CPU > 70% for 2 min | 2-10 replicas | 5 minutes |
| Database read replicas | Read latency > 100ms | 1-3 replicas | Manual |

---

## 11. Error Handling & Logging

### 11.1 Error Classification

| Category | Severity | Retry | Alert |
|----------|----------|-------|-------|
| Validation errors | Low | No | No |
| Auth failures | Low | No | After 10 failures/min |
| Database errors | High | Yes (3x) | Immediately |
| External service errors | Medium | Yes (3x) | After 5 failures |

### 11.2 Retry Strategy

| Error Type | Max Retries | Backoff | Circuit Breaker |
|------------|-------------|---------|-----------------|
| Database timeout | 3 | Exponential (100ms base) | 5 failures in 30s |
| Keycloak timeout | 2 | Linear (500ms) | 3 failures in 10s |
| Dapr invoke failure | 3 | Exponential (200ms base) | 10 failures in 60s |

### 11.3 Logging Standards

| Level | Usage | Example |
|-------|-------|---------|
| DEBUG | Request/response details | `Received request: POST /endpoints {...}` |
| INFO | Business events | `Endpoint created: {id} by user {user_id}` |
| WARNING | Recoverable issues | `Keycloak slow response: 2.5s` |
| ERROR | Failures requiring attention | `Database connection failed: timeout` |

### 11.4 Observability

| Signal | Tool | Retention | Alert Threshold |
|--------|------|-----------|-----------------|
| Metrics | Prometheus | 30 days | Error rate > 1% |
| Traces | Tempo | 7 days | P99 latency > 2s |
| Logs | Loki | 14 days | ERROR count > 10/min |

---

## 12. Deployment & Infrastructure

### 12.1 Deployment Topology

```
┌─────────────────────────────────────────────────────────────────┐
│                        Kubernetes Cluster                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐                │
│  │  budapp    │  │  budapp    │  │  budapp    │   (3 replicas) │
│  │  + Dapr    │  │  + Dapr    │  │  + Dapr    │                │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘                │
│        │               │               │                        │
│        └───────────────┼───────────────┘                        │
│                        │                                         │
│                        ▼                                         │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Service Mesh (Dapr)                    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                        │                                         │
│        ┌───────────────┼───────────────┐                        │
│        ▼               ▼               ▼                        │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐                    │
│  │PostgreSQL│   │  Redis   │   │ Keycloak │                    │
│  └──────────┘   └──────────┘   └──────────┘                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 12.2 Container Specification

| Property | Value |
|----------|-------|
| Base Image | `python:3.11-slim` |
| Resource Requests | CPU: 100m, Memory: 256Mi |
| Resource Limits | CPU: 500m, Memory: 512Mi |
| Health Checks | Liveness: `/health`, Readiness: `/ready` |

### 12.3 CI/CD Pipeline

| Stage | Trigger | Actions | Rollback |
|-------|---------|---------|----------|
| Build | Push to branch | Lint, test, build image | N/A |
| Test | PR created | Integration tests | N/A |
| Deploy (staging) | Merge to main | Helm upgrade | `helm rollback` |
| Deploy (prod) | Manual approval | Blue-green deploy | Switch to blue |

### 12.4 Rollback Strategy

| Scenario | Detection | Rollback Method | Recovery Time |
|----------|-----------|-----------------|---------------|
| Failed deployment | Health checks fail | Kubernetes rollback | < 2 minutes |
| Performance degradation | P99 > threshold | Manual rollback | < 5 minutes |
| Data corruption | Monitoring alerts | Restore from backup | < 30 minutes |

---

## 13. Testing Strategy

### 13.1 Unit Tests

| Module | Coverage Target | Mocking Strategy |
|--------|-----------------|------------------|
| `auth/` | 90% | Mock Keycloak client |
| `audit_ops/` | 95% | Mock database session |
| `billing_ops/` | 90% | Mock Redis, budmetrics |
| `services.py` | 85% | Mock CRUD layer |

### 13.2 Integration Tests

| Integration | Test Approach | Environment |
|-------------|---------------|-------------|
| Database | Real PostgreSQL | Docker Compose |
| Keycloak | Real Keycloak | Docker Compose |
| Dapr | Dapr sidecar | Docker Compose |
| Other services | Mock via Dapr | Unit test mocks |

### 13.3 Edge Case Coverage

| Edge Case | Test | Expected Behavior |
|-----------|------|-------------------|
| First audit record | `test_audit_first_record` | Uses seed hash |
| Concurrent audit writes | `test_audit_concurrent` | Sequential ordering |
| Expired token | `test_auth_expired_token` | 401, refresh hint |
| Over quota | `test_billing_over_quota` | 429, quota info |

### 13.4 Performance Tests

| Test | Metric | Threshold | Frequency |
|------|--------|-----------|-----------|
| Login latency | P95 response time | < 500ms | Weekly |
| Endpoint CRUD | P95 response time | < 200ms | Weekly |
| Audit write | Throughput | > 100 writes/sec | Monthly |

---

## 14. Limitations & Future Enhancements

### 14.1 Known Limitations

| Limitation | Impact | Workaround |
|------------|--------|------------|
| Single region deployment | No geo-redundancy | Manual failover |
| Audit hash chain is sequential | Write bottleneck under high load | Batch audit events |
| No offline token support | Users must re-login frequently | Longer token lifetime |

### 14.2 Technical Debt

| Item | Priority | Effort | Tracking |
|------|----------|--------|----------|
| Migrate to async SQLAlchemy | Medium | 2 weeks | TBD |
| Add OpenTelemetry tracing | Low | 1 week | TBD |
| Refactor billing to event-driven | High | 3 weeks | TBD |

### 14.3 Planned Improvements

| Enhancement | Rationale | Target Version |
|-------------|-----------|----------------|
| Multi-region support | Disaster recovery | v2.0 |
| GraphQL API | Better client flexibility | v2.0 |
| Webhook notifications | Real-time integrations | v1.5 |

---

## 15. Appendix

### 15.1 Glossary

| Term | Definition |
|------|------------|
| TTFT | Time to first token - latency before model starts generating |
| TPOT | Time per output token - generation speed |
| TP | Tensor Parallelism - splitting model across GPUs |
| PP | Pipeline Parallelism - splitting layers across GPUs |
| NFD | Node Feature Discovery - hardware detection in Kubernetes |

### 15.2 Design Alternatives Considered

| Alternative | Pros | Cons | Why Not Chosen |
|-------------|------|------|----------------|
| Session-based auth | Simpler implementation | Stateful, harder to scale | JWT is industry standard |
| MongoDB for audit | Flexible schema | No relational integrity | Need joins for reporting |
| gRPC for internal APIs | Better performance | More complex client code | REST + Dapr sufficient |
