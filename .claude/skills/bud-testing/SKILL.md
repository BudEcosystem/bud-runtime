---
name: bud-testing
description: Testing workflow for bud-stack services. Use when running tests, setting up test environment, building/deploying services, or debugging test failures across budapp, budadmin, budgateway, or any bud-stack service.
---

# Bud-Stack Testing

## Configuration

**Before starting, read the config file:** `.claude/skills/bud-testing/config.env`

All commands below use variables from the config file. Source it or substitute values manually:

```bash
# Source the config (from repo root)
source .claude/skills/bud-testing/config.env

# Or export individual variables
export NAMESPACE=pde-ditto
export REGISTRY=dittops
export IMAGE_TAG=nightly
```

## Quick Reference

### Test Environment

| Setting | Value |
|---------|-------|
| Kubernetes Namespace | `${NAMESPACE}` |
| Container Registry | `${REGISTRY}` |
| budadmin UI (local dev) | `${FRONTEND_DEV_URL}` (via `npm run dev`) |
| budapp API (port-forward) | `kubectl port-forward svc/budapp ${BUDAPP_PORT}:${BUDAPP_PORT} -n ${NAMESPACE}` |

### Test Credentials

```
Admin Email: ${ADMIN_EMAIL}
Admin Password: ${ADMIN_PASSWORD}
Keycloak Admin: ${KEYCLOAK_ADMIN_USER} / ${KEYCLOAK_ADMIN_PASSWORD}
Default Realm: ${KEYCLOAK_REALM}
```

## Build & Deploy Workflow

All services run in Kubernetes. To deploy changes:

### 1. Build Docker Image

```bash
cd services/<service_name>
docker build -t ${REGISTRY}/<image_name>:${IMAGE_TAG} -f deploy/Dockerfile .

# Examples:
docker build -t ${REGISTRY}/budapp:${IMAGE_TAG} -f deploy/Dockerfile .
docker build -t ${REGISTRY}/budadmin:${IMAGE_TAG} -f deploy/Dockerfile .
docker build -t ${REGISTRY}/budgateway:${IMAGE_TAG} -f gateway/Dockerfile .
```

### 2. Push to Registry

```bash
docker push ${REGISTRY}/<image_name>:${IMAGE_TAG}

# Examples:
docker push ${REGISTRY}/budapp:${IMAGE_TAG}
docker push ${REGISTRY}/budadmin:${IMAGE_TAG}
```

### 3. Rollout Restart in Kubernetes

```bash
kubectl rollout restart deployment/<deployment_name> -n ${NAMESPACE}

# Examples:
kubectl rollout restart deployment/budapp -n ${NAMESPACE}
kubectl rollout restart deployment/budadmin -n ${NAMESPACE}
kubectl rollout restart deployment/budgateway -n ${NAMESPACE}

# Watch rollout status
kubectl rollout status deployment/<deployment_name> -n ${NAMESPACE}

# Check pods
kubectl get pods -n ${NAMESPACE} -l app=<app_name>
```

### Quick Deploy Script

```bash
# Build, push, and deploy in one go
SERVICE=budapp
docker build -t ${REGISTRY}/$SERVICE:${IMAGE_TAG} -f services/$SERVICE/deploy/Dockerfile services/$SERVICE && \
docker push ${REGISTRY}/$SERVICE:${IMAGE_TAG} && \
kubectl rollout restart deployment/$SERVICE -n ${NAMESPACE} && \
kubectl rollout status deployment/$SERVICE -n ${NAMESPACE}
```

## Accessing Services

### Port Forwarding (Local Development)

```bash
# budapp API
kubectl port-forward svc/budapp ${BUDAPP_PORT}:${BUDAPP_PORT} -n ${NAMESPACE}

# budadmin UI
kubectl port-forward svc/budadmin ${BUDADMIN_PORT}:${BUDADMIN_PORT} -n ${NAMESPACE}

# PostgreSQL
kubectl port-forward svc/budapp-postgres ${POSTGRES_PORT}:${POSTGRES_PORT} -n ${NAMESPACE}

# Redis
kubectl port-forward svc/budapp-redis ${REDIS_PORT}:${REDIS_PORT} -n ${NAMESPACE}
```

### Ingress URLs (Integration Testing)

Access services via their ingress URLs when available for integration testing.

## Frontend Testing (budadmin)

### Local Development

```bash
cd services/budadmin
npm install
npm run dev  # Starts on localhost:3001
```

### UI Testing with Playwright

**IMPORTANT:** Before running UI tests, check if the dev server is running. If not, start it automatically:

```bash
# Check if ${FRONTEND_DEV_URL} is accessible, if not start the dev server
curl -s -o /dev/null -w "%{http_code}" "${FRONTEND_DEV_URL}" 2>/dev/null | grep -q "200\|301\|302" || \
  (cd services/budadmin && npm install && npm run dev &)

# Wait for server to be ready (up to 60 seconds)
timeout 60 bash -c 'until curl -s "${FRONTEND_DEV_URL}" > /dev/null 2>&1; do sleep 2; done'
```

**Auto-start procedure:**
1. Try to connect to `${FRONTEND_DEV_URL}`
2. If connection refused, run `cd services/budadmin && npm run dev` in background
3. Wait for server to become available before proceeding with tests

```
# Use Playwright MCP tools to test
- browser_navigate to ${FRONTEND_DEV_URL}
- browser_snapshot to capture page state
- browser_click / browser_type to interact
- browser_take_screenshot to capture results
```

**Login Flow:**
1. Navigate to `${FRONTEND_DEV_URL}/auth/login`
2. Fill email: `${ADMIN_EMAIL}`
3. Fill password: `${ADMIN_PASSWORD}`
4. Click login button
5. Verify redirect to dashboard

### Build for Deployment

```bash
npm run typecheck
npm run lint
npm run build
docker build -t ${REGISTRY}/budadmin:${IMAGE_TAG} .
docker push ${REGISTRY}/budadmin:${IMAGE_TAG}
kubectl rollout restart deployment/budadmin -n ${NAMESPACE}
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
docker build -t ${REGISTRY}/budgateway:${IMAGE_TAG} .
docker push ${REGISTRY}/budgateway:${IMAGE_TAG}
kubectl rollout restart deployment/budgateway -n ${NAMESPACE}
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
kubectl get pods -n ${NAMESPACE}

# View logs
kubectl logs -f deployment/<service> -n ${NAMESPACE}

# Describe pod for events
kubectl describe pod <pod_name> -n ${NAMESPACE}

# Exec into pod
kubectl exec -it <pod_name> -n ${NAMESPACE} -- /bin/bash

# Check service endpoints
kubectl get endpoints -n ${NAMESPACE}
```

## Common Issues

| Issue | Solution |
|-------|----------|
| Pod CrashLoopBackOff | Check logs: `kubectl logs <pod> -n ${NAMESPACE}` |
| Image pull error | Verify registry credentials and image tag |
| Service not accessible | Check port-forward or ingress configuration |
| Database connection | Port-forward PostgreSQL or check service DNS |
| Rollout stuck | Check `kubectl rollout status` and pod events |

## Database Operations

```bash
# Port-forward PostgreSQL first
kubectl port-forward svc/budapp-postgres ${POSTGRES_PORT}:${POSTGRES_PORT} -n ${NAMESPACE}

# Then run migrations
cd services/budapp
alembic -c ./budapp/alembic.ini upgrade head

# Create new migration
alembic -c ./budapp/alembic.ini revision --autogenerate -m "description"
```

## See Also

- [TESTING_GUIDELINES.md](../../../services/budapp/TESTING_GUIDELINES.md) - Detailed testing patterns for budapp
- Service-specific CLAUDE.md files in each service directory
