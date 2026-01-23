# Bud AI Foundry - Low-Level Design

---

## Overview

This document provides detailed technical design specifications for the Bud AI Foundry platform. It covers cross-cutting concerns, shared patterns, and links to service-specific low-level designs.

For high-level architecture and component interactions, see [High-Level Architecture](./high-level-architecture.md).

---

## Document Structure

| Document | Description |
|----------|-------------|
| **This Document** | Cross-cutting concerns, shared patterns, conventions |
| [budapp](../services/budapp.md) | Core API, users, projects, authentication |
| [budcluster](../services/budcluster.md) | Cluster lifecycle, Terraform/Ansible |
| [budsim](../services/budsim.md) | Performance optimization, XGBoost |
| [budmodel](../services/budmodel.md) | Model registry, metadata |
| [budmetrics](../services/budmetrics.md) | Observability, ClickHouse |
| [budpipeline](../services/budpipeline.md) | Workflow orchestration |
| [budgateway](../services/budgateway.md) | Inference routing (Rust) |
| [budeval](../services/budeval.md) | Model evaluation |
| [budnotify](../services/budnotify.md) | Notifications |
| [ask-bud](../services/ask-bud.md) | AI assistant |
| [budadmin](../services/budadmin.md) | Main dashboard (Next.js) |
| [budplayground](../services/budplayground.md) | Model testing interface |
| [budCustomer](../services/budCustomer.md) | Customer portal |

---

## Service Dependency Graph


![Service dependency overview](../diagrams/lld-overview.png)


---

## Cross-Cutting Technical Concerns

### 1. Authentication & Authorization

#### External Authentication (Keycloak)

All user-facing requests authenticate via Keycloak:

```
┌────────┐     ┌──────────┐     ┌──────────┐     ┌─────────┐
│ Client │────►│ Keycloak │────►│ budapp   │────►│ Service │
│        │     │  (JWT)   │     │(validate)│     │         │
└────────┘     └──────────┘     └──────────┘     └─────────┘
```

**JWT Token Structure:**
```json
{
  "sub": "user-uuid",
  "realm_access": {
    "roles": ["admin", "user"]
  },
  "resource_access": {
    "budapp": {
      "roles": ["project-admin"]
    }
  },
  "org_id": "organization-uuid",
  "preferred_username": "user@example.com"
}
```

**Role Hierarchy:**
| Role | Permissions |
|------|-------------|
| `super_admin` | Full platform access, all organizations |
| `org_admin` | Organization management, all projects |
| `project_admin` | Project management, deployments |
| `user` | Read access, limited deployments |

#### Inter-Service Authentication (Dapr)

Services communicate via Dapr sidecars with API token authentication:

```python
# Environment variable
DAPR_API_TOKEN = "secret-token"

# Dapr sidecar validates token on every request
headers = {"dapr-api-token": os.environ["DAPR_API_TOKEN"]}
```

#### Application-Level Authentication

Internal endpoints use `APP_API_TOKEN` for service-to-service calls:

```python
@router.get("/internal/health")
async def internal_health(
    x_api_token: str = Header(..., alias="X-API-Token")
):
    if x_api_token != settings.APP_API_TOKEN:
        raise HTTPException(status_code=401)
```

---

### 2. Database Conventions

#### PostgreSQL Standards

All Python services using PostgreSQL follow these conventions:

**Table Naming:**
- Snake_case for table names: `user_projects`, `model_endpoints`
- Plural form for collections: `users`, `clusters`, `deployments`

**Column Standards:**
```sql
-- Every table includes:
id            UUID PRIMARY KEY DEFAULT gen_random_uuid()
created_at    TIMESTAMP WITH TIME ZONE DEFAULT NOW()
updated_at    TIMESTAMP WITH TIME ZONE DEFAULT NOW()

-- Foreign keys follow pattern:
{entity}_id   UUID REFERENCES {entity}s(id)

-- Soft delete (where applicable):
deleted_at    TIMESTAMP WITH TIME ZONE NULL
```

**Index Conventions:**
```sql
-- Primary key (automatic)
ix_{table}_pkey

-- Foreign key indexes
ix_{table}_{column}_fkey

-- Composite indexes for common queries
ix_{table}_{col1}_{col2}
```

**SQLAlchemy Base Model:**
```python
class BaseModel(Base):
    __abstract__ = True

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )
```

#### ClickHouse Standards (budmetrics)

Time-series data uses MergeTree engine with partitioning:

```sql
CREATE TABLE inference_metrics (
    timestamp DateTime64(3),
    endpoint_id UUID,
    request_id UUID,
    tokens_in UInt32,
    tokens_out UInt32,
    latency_ms Float32,
    ttft_ms Float32
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (endpoint_id, timestamp)
TTL timestamp + INTERVAL 90 DAY;
```

---

### 3. API Design Standards

#### REST Conventions

All FastAPI services follow consistent patterns:

**URL Structure:**
```
/api/v1/{resource}              # Collection
/api/v1/{resource}/{id}         # Single item
/api/v1/{resource}/{id}/{sub}   # Sub-resource
```

**HTTP Methods:**
| Method | Purpose | Idempotent |
|--------|---------|------------|
| GET | Retrieve resource(s) | Yes |
| POST | Create resource | No |
| PUT | Full update | Yes |
| PATCH | Partial update | Yes |
| DELETE | Remove resource | Yes |

**Response Envelope:**
```json
{
  "data": { },
  "meta": {
    "total": 100,
    "page": 1,
    "per_page": 20
  }
}
```

**Error Response:**
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input",
    "details": [
      {"field": "name", "message": "Required"}
    ]
  }
}
```

#### Pydantic Schema Conventions

```python
# Request schemas (Create/Update)
class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None

class ProjectUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None

# Response schemas
class ProjectResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

# List response with pagination
class ProjectListResponse(BaseModel):
    data: list[ProjectResponse]
    meta: PaginationMeta
```

---

### 4. Dapr Integration Patterns

#### Service Invocation

```python
from dapr.clients import DaprClient

async def invoke_service(app_id: str, method: str, data: dict) -> dict:
    """Invoke another service via Dapr."""
    async with DaprClient() as client:
        response = await client.invoke_method(
            app_id=app_id,
            method_name=method,
            data=json.dumps(data),
            content_type="application/json"
        )
        return json.loads(response.data)

# Usage
result = await invoke_service(
    app_id="budcluster",
    method="clusters/status",
    data={"cluster_id": str(cluster_id)}
)
```

#### Pub/Sub Events

**Publisher:**
```python
async def publish_event(topic: str, data: dict):
    async with DaprClient() as client:
        await client.publish_event(
            pubsub_name="pubsub",
            topic_name=topic,
            data=json.dumps(data),
            data_content_type="application/json"
        )

# Publish deployment completed event
await publish_event("workflow-events", {
    "event_type": "deployment_completed",
    "deployment_id": str(deployment_id),
    "status": "success"
})
```

**Subscriber:**
```python
@router.post("/events/workflow")
async def handle_workflow_event(event: CloudEvent):
    """Handle workflow completion events."""
    data = event.data
    if data["event_type"] == "deployment_completed":
        await process_deployment_completed(data)
```

#### State Management

```python
async def save_state(key: str, value: dict, ttl_seconds: int = None):
    async with DaprClient() as client:
        await client.save_state(
            store_name="statestore",
            key=key,
            value=json.dumps(value),
            state_metadata={"ttlInSeconds": str(ttl_seconds)} if ttl_seconds else None
        )

async def get_state(key: str) -> dict | None:
    async with DaprClient() as client:
        state = await client.get_state(store_name="statestore", key=key)
        return json.loads(state.data) if state.data else None
```

#### Workflows (Long-Running Operations)

```python
from dapr.ext.workflow import WorkflowRuntime, DaprWorkflowContext

@workflow
def cluster_provisioning_workflow(ctx: DaprWorkflowContext, input: dict):
    """Long-running cluster provisioning workflow."""

    # Step 1: Validate configuration
    config = yield ctx.call_activity(validate_config, input=input)

    # Step 2: Provision infrastructure (may take 10-30 minutes)
    infra = yield ctx.call_activity(
        provision_infrastructure,
        input=config,
        retry_policy=RetryPolicy(max_attempts=3)
    )

    # Step 3: Configure cluster
    yield ctx.call_activity(configure_cluster, input=infra)

    # Step 4: Publish completion event
    yield ctx.call_activity(publish_completion, input={
        "cluster_id": input["cluster_id"],
        "status": "completed"
    })

    return {"status": "completed"}
```

---

### 5. Error Handling

#### Exception Hierarchy

```python
class BudException(Exception):
    """Base exception for all Bud services."""
    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"

class NotFoundError(BudException):
    status_code = 404
    error_code = "NOT_FOUND"

class ValidationError(BudException):
    status_code = 422
    error_code = "VALIDATION_ERROR"

class ConflictError(BudException):
    status_code = 409
    error_code = "CONFLICT"

class AuthorizationError(BudException):
    status_code = 403
    error_code = "FORBIDDEN"
```

#### Global Exception Handler

```python
@app.exception_handler(BudException)
async def bud_exception_handler(request: Request, exc: BudException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.error_code,
                "message": str(exc),
                "details": getattr(exc, "details", None)
            }
        }
    )
```

---

### 6. Logging Standards

#### Structured Logging (structlog)

```python
import structlog

logger = structlog.get_logger()

# Log with context
logger.info(
    "deployment_started",
    deployment_id=str(deployment_id),
    cluster_id=str(cluster_id),
    model_name=model.name
)

# Log with bound context
log = logger.bind(request_id=request_id, user_id=user_id)
log.info("processing_request")
log.info("request_completed", duration_ms=duration)
```

#### Log Levels

| Level | Usage |
|-------|-------|
| `DEBUG` | Detailed diagnostic information |
| `INFO` | General operational events |
| `WARNING` | Unexpected but handled situations |
| `ERROR` | Errors that need attention |
| `CRITICAL` | System failures requiring immediate action |

#### Required Log Fields

Every log entry includes:
- `timestamp`: ISO 8601 format
- `level`: Log level
- `service`: Service name (e.g., `budapp`)
- `request_id`: Correlation ID for request tracing
- `message`: Human-readable message

---

### 7. Configuration Management

#### Environment Variables

All services use environment variables with consistent naming:

```bash
# Database
DATABASE_URL=postgresql://user:pass@host:5432/db
DATABASE_POOL_SIZE=10

# Dapr
DAPR_HTTP_PORT=3500
DAPR_GRPC_PORT=50001
DAPR_API_TOKEN=secret

# Service-specific
APP_API_TOKEN=internal-token
LOG_LEVEL=INFO
```

#### Pydantic Settings

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Database
    database_url: str
    database_pool_size: int = 10

    # Dapr
    dapr_http_port: int = 3500
    dapr_api_token: str

    # Application
    app_api_token: str
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )

settings = Settings()
```

---

### 8. Testing Patterns

#### Unit Tests

```python
import pytest
from unittest.mock import Mock, AsyncMock

@pytest.fixture
def mock_data_manager():
    """Mock database operations."""
    manager = Mock()
    manager.get_by_id = AsyncMock(return_value=sample_entity)
    manager.create = AsyncMock(return_value=sample_entity)
    return manager

async def test_create_project(mock_data_manager):
    service = ProjectService(data_manager=mock_data_manager)
    result = await service.create(ProjectCreate(name="Test"))
    assert result.name == "Test"
```

#### Integration Tests

```python
@pytest.fixture
async def test_client(test_db):
    """Create test client with database."""
    app.dependency_overrides[get_db] = lambda: test_db
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

async def test_create_project_api(test_client, auth_headers):
    response = await test_client.post(
        "/api/v1/projects",
        json={"name": "Test Project"},
        headers=auth_headers
    )
    assert response.status_code == 201
```

---

### 9. Security Patterns

#### Input Validation

All inputs are validated at API boundary:

```python
class EndpointCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, pattern=r"^[a-z0-9-]+$")
    model_id: UUID
    cluster_id: UUID

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        if v.startswith("-") or v.endswith("-"):
            raise ValueError("Name cannot start or end with hyphen")
        return v
```

#### Credential Encryption

Sensitive data (cloud credentials, API keys) is encrypted at rest:

```python
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

class CredentialEncryption:
    def __init__(self, rsa_key_path: str, symmetric_key_path: str):
        self.rsa_key = load_rsa_key(rsa_key_path)
        self.symmetric_key = load_symmetric_key(symmetric_key_path)

    def encrypt(self, plaintext: str) -> str:
        """Encrypt with AES-256-GCM."""
        iv = os.urandom(12)
        cipher = Cipher(algorithms.AES(self.symmetric_key), modes.GCM(iv))
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(plaintext.encode()) + encryptor.finalize()
        return base64.b64encode(iv + encryptor.tag + ciphertext).decode()
```

#### SQL Injection Prevention

All database queries use parameterized statements via SQLAlchemy:

```python
# Correct - parameterized query
stmt = select(User).where(User.email == email)

# NEVER do this - SQL injection vulnerable
# stmt = text(f"SELECT * FROM users WHERE email = '{email}'")
```

---

### 10. Deployment Patterns

#### Container Standards

All services follow consistent container practices:

```dockerfile
FROM python:3.11-slim

# Non-root user
RUN useradd -m -u 1000 appuser
USER appuser

# Read-only filesystem where possible
# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s \
  CMD curl -f http://localhost:8080/health || exit 1

# Graceful shutdown
STOPSIGNAL SIGTERM
```

#### Kubernetes Resources

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: budapp
spec:
  replicas: 2
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  template:
    spec:
      containers:
      - name: budapp
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
```

---

## Service-Specific LLDs

Each service has a dedicated LLD document with:
- Database schema (tables, relationships, indexes)
- API endpoint specifications
- Internal architecture (modules, classes)
- Integration details
- Configuration reference

See the [Document Structure](#document-structure) section for links to each service LLD.

---

## Related Documents

- [High-Level Architecture](./high-level-architecture.md)
- [Component Catalog](./component-catalog.md)
- [Technology Stack Reference](./technology-stack-reference.md)
- [Deployment Architecture](./deployment-architecture.md)
