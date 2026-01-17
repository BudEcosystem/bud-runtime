# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture Overview

Bud Serve App is a FastAPI-based microservice for the Bud Runtime ecosystem that manages AI/ML model deployments, clusters, and endpoints. The application uses:
- **Dapr** for microservice communication and workflow orchestration
- **PostgreSQL** for data persistence with Alembic migrations
- **Redis** for caching and session management
- **MinIO** for model/dataset storage
- **Keycloak** for authentication and multi-tenant support
- **Prometheus/Grafana** for metrics and monitoring

### Module Structure
Each module in `budapp/` follows a consistent pattern:
- `models.py` - SQLAlchemy models
- `schemas.py` - Pydantic schemas for API validation
- `crud.py` - Database operations
- `services.py` - Business logic
- `*_routes.py` - FastAPI route definitions

Key modules:
- `auth/` - Authentication with Keycloak integration
- `cluster_ops/` - Cluster management and workflows
- `model_ops/` - Model management (cloud and local)
- `endpoint_ops/` - Endpoint deployments
- `workflow_ops/` - Dapr workflow definitions and BudPipeline proxy routes
- `commons/` - Shared utilities, config, and dependencies

## Development Commands

### Start Development Environment
```bash
# Start all services (PostgreSQL, Redis, Keycloak, MinIO, Dapr)
./deploy/start_dev.sh

# Stop all services
./deploy/stop_dev.sh
```

### Database Operations
```bash
# Apply migrations
alembic -c ./budapp/alembic.ini upgrade head

# Create new migration
alembic -c ./budapp/alembic.ini revision --autogenerate -m "description"
```

### Manual Migration Creation Best Practices
When creating migrations manually (due to environment issues), follow these steps:

1. **Find the latest revision:**
```bash
alembic -c budapp/alembic.ini heads
```

2. **Check migration history to choose the correct parent:**
```bash
alembic -c budapp/alembic.ini history --verbose | head -20
```

3. **Follow proper naming convention:**
   - Use format: `{short_hex_id}_{description}.py`
   - Examples: `a1b2c3d4e5f6_add_user_table.py`, `f93ff02dff8_add_publication_fields.py`
   - NOT: `20250906_164620_description.py` (avoid timestamp format)

4. **Use the correct revision structure:**
```python
"""Migration description

Revision ID: a1b2c3d4e5f6
Revises: {latest_revision_from_heads_command}
Create Date: 2025-XX-XX XX:XX:XX.XXXXXX

"""
```

5. **Handle multiple heads:**
   - If `alembic heads` shows multiple heads, choose the most relevant parent
   - Consider creating a merge migration if both branches need to be merged
   - For billing-related changes, prefer billing-related parent migrations

6. **Migration content guidelines:**
   - Always include both `upgrade()` and `downgrade()` functions
   - Use proper SQLAlchemy types (e.g., `postgresql.UUID(as_uuid=True)`)
   - Include data migration logic when changing foreign keys
   - Test both upgrade and downgrade paths

### Testing
```bash
# Run all tests with Dapr
pytest --dapr-http-port 3510 --dapr-api-token <TOKEN>

# Run specific test file
pytest tests/test_cluster_metrics.py --dapr-http-port 3510 --dapr-api-token <TOKEN>
```

### Code Quality
```bash
# Format code with Ruff
ruff format .

# Lint code
ruff check .

# Type checking
mypy budapp/
```

## Key Development Patterns

### API Endpoints
All endpoints follow RESTful conventions with consistent response schemas:
- Use `APIResponseSchema` for standard responses
- Include proper status codes and error handling
- Implement pagination for list endpoints using `PaginationQuery`

### Dapr Workflows
Workflows are defined in `workflows.py` files and registered in `scheduler.py`:
- Each workflow must handle exceptions and update status appropriately
- Use `WorkflowActivityContext` for activity functions
- Store workflow instance IDs in the database for tracking

### Database Models
- All models inherit from `Base` with standard fields (id, created_at, updated_at)
- Use UUID primary keys
- Include proper relationships and indexes
- Handle soft deletes with status fields rather than actual deletion

### Authentication
- All protected endpoints require JWT tokens via `get_current_user` dependency
- Multi-tenant support through Keycloak realms
- Role-based access control with permissions stored in database

### Error Handling
- Use custom exceptions from `commons/exceptions.py`
- Implement proper error responses with meaningful messages
- Log errors with structured logging via structlog

## Environment Configuration

Required environment variables (see `.env.sample`):
- Database: `POSTGRES_*`
- Redis: `REDIS_*`
- Keycloak: `KEYCLOAK_*`
- MinIO: `MINIO_*`
- Dapr: `DAPR_*`
- Application: `APP_NAME`, `SECRET_KEY`, `ALGORITHM`

## Testing Guidelines

### General Testing Practices
- Tests require Dapr to be running
- Use async test functions with `pytest.mark.asyncio`
- Mock external services (Keycloak, MinIO) in tests
- Test database operations use transactions that rollback after each test
- Include both positive and negative test cases

### Common Testing Pitfalls to Avoid

#### 1. SQLAlchemy Query Mocking
**Wrong:**
```python
# Old-style mocking that doesn't work with modern SQLAlchemy
mock_session.query = Mock(return_value=mock_query)
```

**Correct:**
```python
# Mock the DataManagerUtils methods directly
data_manager.execute_scalar = Mock(return_value=5)  # For count queries
data_manager.scalars_all = Mock(return_value=[])   # For list queries
data_manager.scalar_one_or_none = Mock(return_value=record)  # For single record
```

#### 2. CRUD Method Parameters
**Wrong:**
```python
# Don't pass schema objects to CRUD methods
audit_data = AuditRecordCreate(...)
data_manager.create_audit_record(audit_data)
```

**Correct:**
```python
# Pass individual parameters
data_manager.create_audit_record(
    action=AuditActionEnum.CREATE,
    resource_type=AuditResourceTypeEnum.PROJECT,
    resource_id=resource_id,
    user_id=user_id,
    details={"key": "value"},
)
```

#### 3. Mock Records for Pydantic Validation
**Wrong:**
```python
# Incomplete mock missing required fields
record = Mock(spec=AuditTrail)
record.id = uuid4()
record.record_hash = "hash"
# Missing other required fields - will fail Pydantic validation
```

**Correct:**
```python
# Complete mock with ALL required fields
record = Mock(spec=AuditTrail)
record.id = uuid4()
record.user_id = uuid4()
record.action = "CREATE"
record.resource_type = "PROJECT"
record.timestamp = datetime.now(timezone.utc)
record.record_hash = "a" * 64
record.created_at = datetime.now(timezone.utc)
record.details = {}
record.ip_address = "192.168.1.1"
# Include all fields that Pydantic schema expects
```

#### 4. JSON Serialization Format
**Wrong:**
```python
# Don't expect JSON with spaces
assert result == '{"a": 1, "b": 2}'
```

**Correct:**
```python
# Expect compact JSON format
assert result == '{"a":1,"b":2}'
```

#### 5. Boolean Serialization
**Wrong:**
```python
# Don't expect Python string representation
assert serialize_for_hash(True) == "True"
```

**Correct:**
```python
# Expect JSON format
assert serialize_for_hash(True) == "true"
assert serialize_for_hash(False) == "false"
```

#### 6. Return Structure Keys
**Wrong:**
```python
# Don't assume field names - check the actual implementation
assert tampered[0]["audit_id"] == str(record_id)
assert tampered[0]["reason"] == "message"
```

**Correct:**
```python
# Use the actual keys from the service implementation
assert tampered[0]["id"] == str(record_id)
assert tampered[0]["verification_message"] == "message"
```

### Testing Best Practices

1. **Always check the actual implementation** for correct field names and return structures
2. **Mock at the right level** - DataManagerUtils methods, not session.query
3. **Create complete mocks** - Include all required fields for Pydantic schemas
4. **Use consistent serialization** - Compact JSON, lowercase booleans
5. **Verify return structures** - Check actual service methods for correct keys

## BudPipeline Integration

BudApp provides authenticated proxy routes to the BudPipeline service for workflow management and execution monitoring. All routes are prefixed with `/budpipeline` and require authentication.

### Execution Monitoring Routes (002-pipeline-event-persistence)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/budpipeline/executions` | List executions with filters (workflow_id, status, initiator, date range) and pagination |
| `GET` | `/budpipeline/executions/{id}` | Get execution details with step statuses |
| `GET` | `/budpipeline/executions/{id}/progress` | Get detailed progress including steps, events, and aggregated progress |

### Workflow Management Routes

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/budpipeline` | Create a new workflow |
| `GET` | `/budpipeline` | List all workflows |
| `GET` | `/budpipeline/{id}` | Get workflow details |
| `PUT` | `/budpipeline/{id}` | Update workflow |
| `DELETE` | `/budpipeline/{id}` | Delete workflow |
| `POST` | `/budpipeline/{id}/execute` | Start execution (supports `callback_topics` for real-time updates) |
| `POST` | `/budpipeline/validate` | Validate DAG definition |

### Schedule Management Routes

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/budpipeline/schedules` | List schedules |
| `POST` | `/budpipeline/schedules` | Create schedule |
| `GET` | `/budpipeline/schedules/{id}` | Get schedule details |
| `PUT` | `/budpipeline/schedules/{id}` | Update schedule |
| `DELETE` | `/budpipeline/schedules/{id}` | Delete schedule |
| `POST` | `/budpipeline/schedules/{id}/pause` | Pause schedule |
| `POST` | `/budpipeline/schedules/{id}/resume` | Resume schedule |
| `POST` | `/budpipeline/schedules/{id}/trigger` | Trigger immediately |

### Webhook Routes

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/budpipeline/webhooks` | List webhooks |
| `POST` | `/budpipeline/webhooks` | Create webhook |
| `DELETE` | `/budpipeline/webhooks/{id}` | Delete webhook |
| `POST` | `/budpipeline/webhooks/{id}/rotate-secret` | Rotate webhook secret |

### Event Trigger Routes

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/budpipeline/event-triggers` | List event triggers |
| `POST` | `/budpipeline/event-triggers` | Create event trigger |
| `DELETE` | `/budpipeline/event-triggers/{id}` | Delete event trigger |

### Key Files

- `workflow_ops/budpipeline_routes.py` - FastAPI route definitions
- `workflow_ops/budpipeline_service.py` - Service layer with Dapr invocation to budpipeline
- `workflow_ops/schemas.py` - Pydantic schemas for execution responses

### Usage Example

```python
# Start execution with callback topics for real-time progress
response = await client.post(
    "/budpipeline/{workflow_id}/execute",
    json={
        "params": {"input": "data"},
        "callback_topics": ["my-progress-topic"]
    }
)
execution_id = response.json()["id"]

# Poll for progress
progress = await client.get(f"/budpipeline/executions/{execution_id}/progress")
# Returns: execution details, step progress, aggregated progress %, ETA
```
