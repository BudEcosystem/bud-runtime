# End-to-End Test Suite

This directory contains end-to-end (E2E) tests for the bud-stack platform, validating critical user workflows that span multiple services.

## Quick Start

### Prerequisites

- Docker
- k3d (Kubernetes in Docker): `curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash`
- kubectl
- Helm 3.x
- Python 3.10+

### Quick Start (Auto-detect)

The unified setup script automatically selects the best method:

```bash
cd tests/e2e

# Auto-detect and setup (recommends k3d > kind > existing)
./scripts/setup.sh

# Verify all services are running
./scripts/health-check.sh

# Run auth flow tests
./run_auth_tests.sh

# Cleanup
./scripts/teardown.sh
```

### Setup Options

#### Option 1: k3d (Recommended for Local Development)

Creates a lightweight k3s cluster in Docker:

```bash
./scripts/setup-k3d.sh              # Create k3d cluster
./scripts/setup-k3d.sh --skip-build # Skip Docker image building
./scripts/teardown-k3d.sh           # Cleanup
```

#### Option 2: Existing Kubernetes Cluster

Deploy to your current kubectl context (k3s, EKS, AKS, GKE, etc.):

```bash
./scripts/setup-existing-cluster.sh                     # Use current context
./scripts/setup-existing-cluster.sh --context mycluster # Specific context
./scripts/setup-existing-cluster.sh --namespace e2e-dev # Custom namespace
./scripts/setup-existing-cluster.sh --skip-dapr         # Skip Dapr (if installed)
./scripts/setup-existing-cluster.sh --skip-build        # Skip image build
```

#### Option 3: Kind (Alternative)

```bash
./scripts/setup-kind.sh
./scripts/teardown-kind.sh
```

#### Option 4: Docker Compose (Lightweight, No K8s)

For quick iteration without Kubernetes:

```bash
# 1. Start lightweight E2E infrastructure
docker compose -f tests/e2e/config/docker-compose-e2e.yaml up -d

# 2. Run tests
pytest tests/e2e/ -v

# 3. Cleanup
docker compose -f tests/e2e/config/docker-compose-e2e.yaml down -v
```

### Running Specific Test Suites

```bash
# Workflow tests
pytest tests/e2e/workflows/ -v

# User flow tests
pytest tests/e2e/flows/ -v

# Integration tests
pytest tests/e2e/integrations/ -v

# By priority level
pytest tests/e2e/ -m priority_p0  # Critical paths
pytest tests/e2e/ -m priority_p1  # Important paths
pytest tests/e2e/ -m priority_p2  # Nice-to-have
```

## Test Organization

### Directory Structure

```
tests/e2e/
├── README.md                    # This file
├── conftest.py                  # Shared pytest fixtures
├── pytest.ini                   # pytest configuration
├── requirements.txt             # Python dependencies
│
├── fixtures/                    # Reusable test fixtures
│   ├── auth.py                  # Authentication fixtures
│   ├── services.py              # Service client fixtures
│   ├── infrastructure.py        # Database, Redis fixtures
│   ├── data.py                  # Test data fixtures
│   └── cleanup.py               # Cleanup fixtures
│
├── helpers/                     # Test utilities
│   ├── api_client.py            # HTTP client wrapper
│   ├── dapr_client.py           # Dapr service invocation
│   ├── workflow_waiter.py       # Workflow polling utilities
│   ├── database.py              # Database helpers
│   ├── assertions.py            # Custom assertions
│   └── data_factory.py          # Test data generators
│
├── workflows/                   # Workflow-specific E2E tests
│   ├── test_model_deployment.py
│   ├── test_cluster_onboarding.py
│   ├── test_cloud_model_onboarding.py
│   └── ...
│
├── flows/                       # Complete user journey tests
│   ├── test_complete_model_deployment_flow.py
│   ├── test_cluster_to_inference_flow.py
│   └── ...
│
├── integrations/                # Cross-service integration tests
│   ├── test_budapp_budcluster.py
│   ├── test_budapp_budsim.py
│   └── ...
│
├── performance/                 # Performance/load tests
│   ├── test_concurrent_deployments.py
│   └── ...
│
├── data/                        # Test data files
│   ├── models/
│   ├── kubeconfigs/
│   └── fixtures/
│
└── config/                      # Configuration files
    ├── docker-compose-e2e.yaml  # Docker Compose setup
    ├── test_config.yaml         # Test configuration
    └── .env.e2e.sample          # Environment variables template
```

### Test Categories

**Workflow Tests** (`workflows/`):
- Test individual Dapr workflows
- Focus on workflow orchestration
- Validate workflow state transitions
- Examples: MODEL_DEPLOYMENT, CLUSTER_ONBOARDING

**Flow Tests** (`flows/`):
- Test complete user journeys
- Span multiple services
- End-to-end validation
- Examples: Model selection → deployment → inference

**Integration Tests** (`integrations/`):
- Test service-to-service communication
- Validate Dapr integration
- Cross-service data flow
- Examples: budapp ↔ budcluster communication

**Performance Tests** (`performance/`):
- Load testing
- Concurrent operations
- Scalability validation
- Examples: Concurrent deployments, high-volume inference

## Writing E2E Tests

### Test Template

```python
import pytest
from tests.e2e.helpers.api_client import APIClient
from tests.e2e.helpers.workflow_waiter import WorkflowWaiter

@pytest.mark.e2e
@pytest.mark.priority_p1
@pytest.mark.timeout(300)
async def test_my_feature_e2e(
    budapp_client: APIClient,
    auth_token: str,
):
    """
    Test my feature end-to-end.

    Flow:
    1. Step one description
    2. Step two description
    3. Step three description
    """
    # Step 1: Setup
    response = await budapp_client.post(
        "/my-endpoint",
        json={"key": "value"},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200

    # Step 2: Perform action
    resource_id = response.json()["id"]
    # ... test logic ...

    # Step 3: Validate
    assert resource_id is not None

    # Cleanup is handled by fixtures
```

### Common Patterns

#### Waiting for Workflows

```python
from tests.e2e.helpers.workflow_waiter import WorkflowWaiter

waiter = WorkflowWaiter(budapp_client, auth_token)
result = await waiter.wait_for_workflow(
    workflow_type="MODEL_DEPLOYMENT",
    workflow_id=workflow_id,
    timeout=300
)
assert result["status"] == "COMPLETED"
```

#### Creating Test Data

```python
from tests.e2e.helpers.data_factory import TestDataFactory

project = TestDataFactory.create_test_project(user_id)
cluster = TestDataFactory.create_test_cluster()
deployment = TestDataFactory.create_test_model_deployment()
```

#### Custom Assertions

```python
from tests.e2e.helpers.assertions import assert_workflow_completed

await assert_workflow_completed(
    budapp_client,
    auth_token,
    workflow_id,
    timeout=300
)
```

### Test Markers

Use pytest markers to categorize tests:

```python
@pytest.mark.e2e                  # Mark as E2E test
@pytest.mark.priority_p0          # Critical path (run on every PR)
@pytest.mark.priority_p1          # Important (run on merge)
@pytest.mark.priority_p2          # Nice-to-have (nightly)
@pytest.mark.timeout(300)         # 5 minute timeout
@pytest.mark.flaky(reruns=3)      # Retry up to 3 times
@pytest.mark.slow                 # Long-running test
```

## Fixtures

### Available Fixtures

**Authentication**:
- `auth_token`: Valid JWT token
- `test_user`: Test user object
- `admin_token`: Admin JWT token

**Service Clients**:
- `budapp_client`: budapp HTTP client
- `budcluster_client`: budcluster HTTP client
- `budsim_client`: budsim HTTP client
- `budmodel_client`: budmodel HTTP client
- `budgateway_client`: budgateway HTTP client
- `budmetrics_client`: budmetrics HTTP client

**Test Data**:
- `test_project`: Pre-created test project
- `test_cluster`: Pre-created test cluster
- `test_model`: Pre-created test model
- `test_endpoint`: Pre-created test endpoint

**Infrastructure**:
- `postgres_connection`: PostgreSQL connection
- `redis_client`: Redis client
- `clickhouse_client`: ClickHouse client

### Creating Custom Fixtures

```python
# In conftest.py or fixture files
@pytest.fixture
async def my_custom_fixture(budapp_client, auth_token):
    """Create a custom fixture."""
    # Setup
    resource = await create_resource()

    yield resource

    # Teardown
    await cleanup_resource(resource)
```

## Debugging

### View Service Logs

```bash
# All services
docker compose -f tests/e2e/config/docker-compose-e2e.yaml logs

# Specific service
docker compose -f tests/e2e/config/docker-compose-e2e.yaml logs budapp-e2e

# Follow logs
docker compose -f tests/e2e/config/docker-compose-e2e.yaml logs -f budapp-e2e
```

### Interactive Debugging

```python
# Add to test to drop into debugger
import pdb; pdb.set_trace()

# Or use pytest's built-in
pytest tests/e2e/my_test.py --pdb
```

### Verbose Output

```bash
# Show detailed output
pytest tests/e2e/ -vv

# Show print statements
pytest tests/e2e/ -s

# Show full tracebacks
pytest tests/e2e/ --tb=long
```

## Troubleshooting

### Tests Hanging

**Symptoms**: Tests don't complete, hang indefinitely

**Solutions**:
1. Check service health: `docker compose ps`
2. Check logs: `docker compose logs`
3. Increase timeout: `@pytest.mark.timeout(600)`
4. Verify Dapr sidecars are running

### Flaky Tests

**Symptoms**: Tests pass/fail inconsistently

**Solutions**:
1. Add retry logic: `@pytest.mark.flaky(reruns=3)`
2. Check for race conditions
3. Increase wait times between steps
4. Verify cleanup is complete

### Database Connection Errors

**Symptoms**: Connection refused, database not available

**Solutions**:
1. Reset database: `docker compose down -v && docker compose up -d`
2. Check connection string in `.env.e2e`
3. Wait for database to be ready (healthcheck)
4. Verify migrations have run

### Service Communication Failures

**Symptoms**: 502 Bad Gateway, connection errors

**Solutions**:
1. Check Dapr sidecars: `docker compose ps`
2. Verify service ports are correct
3. Check network configuration
4. Review Dapr component configuration

## Best Practices

### Test Isolation

- Each test should be independent
- Use unique resource names (UUIDs)
- Clean up resources after tests
- Don't rely on test execution order

### Performance

- Run tests in parallel when possible
- Use pytest-xdist for parallelization
- Mock external services where appropriate
- Minimize database queries

### Maintainability

- Write clear test descriptions
- Use descriptive variable names
- Add comments for complex logic
- Keep tests focused and simple
- Reuse fixtures and helpers

### Reliability

- Add appropriate timeouts
- Use retry logic for flaky operations
- Validate all assumptions
- Handle errors gracefully
- Log important state for debugging

## CI/CD Integration

E2E tests run automatically in CI/CD:

- **Pull Requests**: P0 tests (~15 min)
- **Merge to Master**: P0 + P1 tests (~30 min)
- **Nightly**: Full suite (~60 min)
- **Releases**: Full + performance tests

See `.github/workflows/e2e-tests.yaml` for configuration.

## Resources

- **Full Implementation Plan**: `/docs/testing/e2e-test-plan.md`
- **Summary**: `/docs/testing/E2E-IMPLEMENTATION-SUMMARY.md`
- **pytest Documentation**: https://docs.pytest.org/
- **httpx Documentation**: https://www.python-httpx.org/
- **budgateway E2E Examples**: `/services/budgateway/tensorzero-internal/tests/e2e/`

## Contributing

### Adding New Tests

1. Choose appropriate directory (workflows/flows/integrations)
2. Follow test template and naming conventions
3. Add appropriate markers (@pytest.mark.priority_pX)
4. Document test flow in docstring
5. Add cleanup fixtures if needed
6. Run locally before committing
7. Update this README if adding new patterns

### Updating Fixtures

1. Add fixture to appropriate file in `fixtures/`
2. Document fixture behavior
3. Update `conftest.py` if needed
4. Add example usage to this README

## Support

For questions or issues:
- Check troubleshooting section above
- Review full implementation plan
- Ask in #engineering-testing Slack channel
- Contact Architecture Team

---

**Status**: Implementation in Progress
**Last Updated**: 2025-12-24
