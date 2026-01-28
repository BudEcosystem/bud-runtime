---
name: bud-testing
description: Testing workflow for bud-stack services. Use when running tests, setting up test environment, building/deploying services, or debugging test failures across budapp, budadmin, budgateway, or any bud-stack service.
---

# Bud-Stack Testing

## Quick Reference

### Test Environment

| Setting | Value |
|---------|-------|
| Kubernetes Namespace | `pde-ditto` |
| Container Registry | Docker Hub |
| budadmin UI (local dev) | `http://localhost:3000` (via `npm run dev`) |
| budapp API (port-forward) | `kubectl port-forward svc/budapp 9081:9081 -n pde-ditto` |

### Test Credentials

```
Admin Email: admin@bud.studio
Admin Password: Budadmin@stud!0
Keycloak Admin: admin / admin
Default Realm: bud-v14
```

## Build & Deploy Workflow

All services run in Kubernetes. To deploy changes:

### 1. Build Docker Image

```bash
cd services/<service_name>
docker build -t <registry>/<image_name>:<tag> deploy/Dockerfile .

# Examples:
docker build -t dittops/budapp:nightly deploy/Dockerfile .
docker build -t dittops/budadmin:nightly deploy/Dockerfile .
docker build -t dittops/budgateway:nightly gateway/Dockerfile .
```

### 2. Push to Registry

```bash
docker push <registry>/<image_name>:<tag>

# Examples:
docker push dittops/budapp:nightly
docker push dittops/budadmin:nightly
```

### 3. Rollout Restart in Kubernetes

```bash
kubectl rollout restart deployment/<deployment_name> -n pde-ditto

# Examples:
kubectl rollout restart deployment/budapp -n pde-ditto
kubectl rollout restart deployment/budadmin -n pde-ditto
kubectl rollout restart deployment/budgateway -n pde-ditto

# Watch rollout status
kubectl rollout status deployment/<deployment_name> -n pde-ditto

# Check pods
kubectl get pods -n pde-ditto -l app=<app_name>
```

### Quick Deploy Script

```bash
# Build, push, and deploy in one go
SERVICE=budapp
docker build -t dittops/$SERVICE:nightly services/$SERVICE && \
docker push dittops/$SERVICE:nightly && \
kubectl rollout restart deployment/$SERVICE -n pde-ditto && \
kubectl rollout status deployment/$SERVICE -n pde-ditto
```

## Accessing Services

### Port Forwarding (Local Development)

```bash
# budapp API
kubectl port-forward svc/budapp 9081:9081 -n pde-ditto

# budadmin UI
kubectl port-forward svc/budadmin 8007:8007 -n pde-ditto

# PostgreSQL
kubectl port-forward svc/budapp-postgres 5432:5432 -n pde-ditto

# Redis
kubectl port-forward svc/budapp-redis 6379:6379 -n pde-ditto
```

### Ingress URLs (Integration Testing)

Access services via their ingress URLs when available for integration testing.

## Frontend Testing (budadmin)

### Local Development

```bash
cd services/budadmin
npm install
npm run dev  # Starts on localhost:3000
```

### UI Testing with Playwright

Start the dev server first, then use Playwright MCP tools:

```bash
# 1. Start dev server
cd services/budadmin && npm run dev
```

```
# 2. Use Playwright MCP tools to test
- browser_navigate to http://localhost:3000
- browser_snapshot to capture page state
- browser_click / browser_type to interact
- browser_take_screenshot to capture results
```

**Login Flow:**
1. Navigate to `http://localhost:3000/auth/login`
2. Fill email: `admin@bud.studio`
3. Fill password: `Budadmin@stud!0`
4. Click login button
5. Verify redirect to dashboard

### Build for Deployment

```bash
npm run typecheck
npm run lint
npm run build
docker build -t dittops/budadmin:nightly .
docker push dittops/budadmin:nightly
kubectl rollout restart deployment/budadmin -n pde-ditto
```

## Backend Testing (Python Services)

### Unit Tests (Local)

```bash
cd services/<service_name>

# Run all tests
pytest

# Run specific test file
pytest tests/test_file.py -v

# Run specific test function
pytest tests/test_file.py::test_function_name -v

# Run with coverage
pytest --cov=<service_name> --cov-report=html
```

### With Dapr (Integration Tests)

```bash
# Port-forward Dapr sidecar first if needed
pytest --dapr-http-port 3510 --dapr-api-token <TOKEN>
```

## Rust Gateway (budgateway)

```bash
cd services/budgateway

# Run all tests
cargo test --workspace

# Run specific test
cargo test test_name -- --nocapture

# Lint before testing
cargo clippy --all-targets --all-features -- -D warnings

# Build and deploy
cargo build --release
docker build -t dittops/budgateway:nightly .
docker push dittops/budgateway:nightly
kubectl rollout restart deployment/budgateway -n pde-ditto
```

## Testing Patterns

### SQLAlchemy Mocking (Modern Pattern)

```python
# Correct: Mock DataManagerUtils methods
data_manager.execute_scalar = Mock(return_value=5)
data_manager.scalars_all = Mock(return_value=[])
data_manager.scalar_one_or_none = Mock(return_value=record)

# Wrong: Old session.query style won't work
# mock_session.query = Mock(...)  # DON'T DO THIS
```

### Pydantic Mock Objects

Include ALL required fields when mocking objects for Pydantic validation:

```python
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
# Include ALL fields the schema expects
```

### JSON Assertions

```python
# Correct: Compact JSON, lowercase booleans
assert result == '{"a":1,"b":2}'
assert serialize_for_hash(True) == "true"

# Wrong: Spaces or Python booleans
# assert result == '{"a": 1}'  # DON'T
# assert serialize_for_hash(True) == "True"  # DON'T
```

## Code Quality Before Testing

### Python

```bash
ruff check . --fix && ruff format .
mypy <service_name>/
```

### TypeScript

```bash
npm run lint
npm run typecheck
```

### Rust

```bash
cargo fmt
cargo clippy --all-targets --all-features -- -D warnings
```

## Kubernetes Debugging

```bash
# Check pod status
kubectl get pods -n pde-ditto

# View logs
kubectl logs -f deployment/<service> -n pde-ditto

# Describe pod for events
kubectl describe pod <pod_name> -n pde-ditto

# Exec into pod
kubectl exec -it <pod_name> -n pde-ditto -- /bin/bash

# Check service endpoints
kubectl get endpoints -n pde-ditto
```

## Common Issues

| Issue | Solution |
|-------|----------|
| Pod CrashLoopBackOff | Check logs: `kubectl logs <pod> -n pde-ditto` |
| Image pull error | Verify registry credentials and image tag |
| Service not accessible | Check port-forward or ingress configuration |
| Database connection | Port-forward PostgreSQL or check service DNS |
| Rollout stuck | Check `kubectl rollout status` and pod events |

## Database Operations

```bash
# Port-forward PostgreSQL first
kubectl port-forward svc/budapp-postgres 5432:5432 -n pde-ditto

# Then run migrations
cd services/budapp
alembic -c ./budapp/alembic.ini upgrade head

# Create new migration
alembic -c ./budapp/alembic.ini revision --autogenerate -m "description"
```

## See Also

- [TESTING_GUIDELINES.md](../../../services/budapp/TESTING_GUIDELINES.md) - Detailed testing patterns for budapp
- Service-specific CLAUDE.md files in each service directory
