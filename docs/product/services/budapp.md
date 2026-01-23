# budapp Service Documentation

---

## Overview

budapp is the core API service for Bud AI Foundry, handling user authentication, project management, model endpoints, audit logging, and coordination with other platform services.

---

## Service Identity

| Property | Value |
|----------|-------|
| **App ID** | budapp |
| **Port** | 9081 |
| **Database** | budapp_db (PostgreSQL) |
| **Language** | Python 3.11 |
| **Framework** | FastAPI |
| **API Docs** | `/docs` (Swagger UI) |

---

## Responsibilities

- User authentication and session management via Keycloak
- Multi-tenant project and organization management
- Model endpoint lifecycle (create, configure, delete)
- Credential storage and provider configuration
- Audit trail with tamper-proof hash chain
- Proxy requests to other services (budcluster, budpipeline, etc.)
- Billing and usage tracking
- Notification dispatch via budnotify

---

## Module Structure

```
budapp/
├── auth/                 # Authentication and authorization
│   ├── auth_routes.py    # Login, logout, session management
│   ├── oauth_routes.py   # OAuth 2.0 / OIDC flows
│   ├── token.py          # JWT token handling
│   └── services.py       # User authentication logic
│
├── audit_ops/            # Audit logging
│   ├── audit_routes.py   # Audit record retrieval
│   ├── audit_logger.py   # Logging service
│   ├── hash_utils.py     # Hash chain integrity
│   └── models.py         # AuditRecord model
│
├── billing_ops/          # Usage and billing
│   ├── routes.py         # Billing endpoints
│   ├── usage_sync.py     # Metrics sync from budmetrics
│   └── services.py       # Billing calculations
│
├── cluster_ops/          # Cluster management proxy
│   ├── cluster_settings_routes.py
│   ├── workflows.py      # Dapr workflow triggers
│   └── services.py       # Cluster operations
│
├── credential_ops/       # Provider credentials
│   ├── credential_routes.py
│   ├── services.py       # Credential encryption
│   └── models.py         # Credential storage
│
├── endpoint_ops/         # Model endpoints
│   ├── endpoint_routes.py
│   ├── models.py         # Endpoint configuration
│   └── schemas.py        # API schemas
│
├── eval_ops/             # Evaluation proxy
│   ├── eval_routes.py
│   └── workflows.py      # Evaluation orchestration
│
├── model_ops/            # Model management
│   ├── model_routes.py
│   └── services.py       # Model lifecycle
│
├── project_ops/          # Project management
│   ├── project_routes.py
│   └── services.py       # Project CRUD
│
├── user_ops/             # User management
│   ├── user_routes.py
│   └── services.py       # User CRUD, roles
│
├── commons/              # Shared utilities
│   ├── database.py       # SQLAlchemy session
│   ├── keycloak.py       # Keycloak client
│   ├── security.py       # Auth dependencies
│   └── logging.py        # Structured logging
│
└── core/                 # Core models and utilities
    ├── models.py         # Base models
    └── schemas.py        # Common schemas
```

---

## API Endpoints

### Authentication (`/auth`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/login` | User login |
| POST | `/auth/logout` | User logout |
| GET | `/auth/me` | Get current user |
| POST | `/auth/refresh` | Refresh access token |
| GET | `/auth/oauth/callback` | OAuth callback handler |

### Users (`/users`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/users` | List users |
| POST | `/users` | Create user |
| GET | `/users/{id}` | Get user by ID |
| PUT | `/users/{id}` | Update user |
| DELETE | `/users/{id}` | Delete user |
| GET | `/users/{id}/roles` | Get user roles |

### Projects (`/projects`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/projects` | List projects |
| POST | `/projects` | Create project |
| GET | `/projects/{id}` | Get project |
| PUT | `/projects/{id}` | Update project |
| DELETE | `/projects/{id}` | Delete project |
| GET | `/projects/{id}/members` | List project members |

### Models (`/models`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/models` | List available models |
| GET | `/models/{id}` | Get model details |
| POST | `/models/custom` | Register custom model |
| GET | `/models/leaderboard` | Model performance leaderboard |

### Endpoints (`/endpoints`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/endpoints` | List endpoints |
| POST | `/endpoints` | Create endpoint |
| GET | `/endpoints/{id}` | Get endpoint |
| PUT | `/endpoints/{id}` | Update endpoint |
| DELETE | `/endpoints/{id}` | Delete endpoint |
| POST | `/endpoints/{id}/deploy` | Deploy endpoint |
| POST | `/endpoints/{id}/undeploy` | Undeploy endpoint |

### Clusters (Proxy to budcluster)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/clusters` | List clusters |
| POST | `/clusters` | Create cluster |
| GET | `/clusters/{id}` | Get cluster |
| DELETE | `/clusters/{id}` | Delete cluster |
| POST | `/clusters/{id}/onboard` | Onboard existing cluster |

### Audit (`/audit`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/audit` | List audit records |
| GET | `/audit/{id}` | Get audit record |
| GET | `/audit/export` | Export audit log |
| POST | `/audit/verify` | Verify hash chain integrity |

### Credentials (`/credentials`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/credentials` | List credentials |
| POST | `/credentials` | Create credential |
| DELETE | `/credentials/{id}` | Delete credential |

---

## Data Models

### User

```python
class User(Base):
    id: UUID
    email: str
    keycloak_id: str
    organization_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
```

### Project

```python
class Project(Base):
    id: UUID
    name: str
    description: str
    organization_id: UUID
    owner_id: UUID
    settings: dict
    created_at: datetime
```

### Endpoint

```python
class Endpoint(Base):
    id: UUID
    name: str
    project_id: UUID
    model_id: UUID
    cluster_id: UUID
    status: EndpointStatus  # PENDING, DEPLOYING, RUNNING, ERROR, STOPPED
    config: dict  # Deployment configuration
    created_at: datetime
```

### AuditRecord

```python
class AuditRecord(Base):
    id: UUID
    action: AuditActionEnum
    resource_type: AuditResourceTypeEnum
    resource_id: UUID
    user_id: UUID
    details: dict
    previous_hash: str  # Hash chain for integrity
    current_hash: str
    created_at: datetime
```

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `KEYCLOAK_URL` | Keycloak server URL | Required |
| `KEYCLOAK_REALM` | Keycloak realm name | `bud` |
| `KEYCLOAK_CLIENT_ID` | OAuth client ID | Required |
| `KEYCLOAK_CLIENT_SECRET` | OAuth client secret | Required |
| `DAPR_HTTP_ENDPOINT` | Dapr sidecar endpoint | `http://localhost:3500` |
| `APP_API_TOKEN` | Internal API token | Required |
| `LOG_LEVEL` | Logging level | `INFO` |

### Dapr Components

| Component | Type | Purpose |
|-----------|------|---------|
| `budapp-statestore` | State | Session caching |
| `budapp-pubsub` | Pub/Sub | Event publishing |

---

## Service Dependencies

```
budapp
├── Keycloak (authentication)
├── PostgreSQL (data storage)
├── Valkey (session cache, via Dapr)
├── budcluster (cluster operations)
├── budsim (optimization requests)
├── budpipeline (workflow execution)
├── budmodel (model metadata)
├── budmetrics (usage data)
└── budnotify (notifications)
```

---

## Development

### Running Locally

```bash
cd services/budapp

# Copy environment file
cp .env.sample .env

# Start with Docker Compose (includes Dapr, PostgreSQL)
./deploy/start_dev.sh --build

# Or run directly with Dapr
dapr run --app-id budapp --app-port 9081 -- uvicorn budapp.main:app --reload
```

### Running Tests

```bash
# All tests
pytest

# Specific test file
pytest tests/test_auth.py

# With coverage
pytest --cov=budapp
```

### Database Migrations

```bash
# Generate migration
alembic -c ./budapp/alembic.ini revision --autogenerate -m "description"

# Apply migrations
alembic -c ./budapp/alembic.ini upgrade head

# Rollback
alembic -c ./budapp/alembic.ini downgrade -1
```

---

## Security Considerations

- All endpoints require authentication except `/health` and `/auth/login`
- JWT tokens validated against Keycloak public keys
- Audit records use hash chain for tamper detection
- Credentials encrypted with RSA before storage
- Rate limiting applied to authentication endpoints

---

## Related Documents

- [High-Level Architecture](../architecture/high-level-architecture.md)
- [API Reference](../api/api-reference.md)
- [IAM Architecture](../security/iam-architecture.md)
