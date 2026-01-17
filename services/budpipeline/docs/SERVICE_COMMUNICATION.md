# Service-to-Service Communication

This document describes how BudPipeline communicates with other services in the Bud Runtime ecosystem.

## Dapr Service Invocation

BudPipeline uses Dapr's service invocation pattern for synchronous service-to-service calls. The core utility is in `commons/dapr_utils.py`.

### URL Pattern

```
{DAPR_HTTP_ENDPOINT}/v1.0/invoke/{app_id}/method{method_path}
```

| Component | Description | Example |
|-----------|-------------|---------|
| `DAPR_HTTP_ENDPOINT` | Dapr sidecar HTTP endpoint | `http://localhost:3500` |
| `app_id` | Target service's Dapr app ID | `budcluster`, `budapp` |
| `method_path` | API endpoint path | `/api/v1/health` |

### Example Usage

```python
from budpipeline.commons.dapr_utils import invoke_dapr_service

# Call budcluster's health endpoint
response = await invoke_dapr_service(
    app_id="budcluster",
    method_path="/api/v1/health",
    http_method="GET",
)

# Call budcluster to create a deployment
response = await invoke_dapr_service(
    app_id="budcluster",
    method_path=f"/api/v1/clusters/{cluster_id}/deployments",
    http_method="POST",
    data={"model_id": model_id, "config": deployment_config},
)
```

## Authentication

BudPipeline uses a layered authentication approach:

### Layer 1: Dapr API Token (Service Mesh)

All inter-service calls via Dapr require the `dapr-api-token` header. This is automatically added by the `invoke_dapr_service` utility.

```python
headers = {"dapr-api-token": settings.DAPR_API_TOKEN}
```

**Environment Variable**: `DAPR_API_TOKEN`

### Layer 2: APP_API_TOKEN (Application Level)

Internal endpoints in BudPipeline validate an additional application token via middleware:

```python
# Protected endpoints:
# - /internal/*
# - /workflow-events

# Middleware validation
if request.url.path.startswith("/internal/") or request.url.path == "/workflow-events":
    token = request.headers.get("dapr-api-token")
    if token != settings.APP_API_TOKEN:
        return JSONResponse(status_code=403, content={"detail": "Forbidden"})
```

**Environment Variable**: `APP_API_TOKEN`

### Layer 3: Keycloak JWT (External API)

External API calls (from frontend or external clients) are authenticated via Keycloak JWT tokens. BudPipeline doesn't validate JWTs directly - budapp handles external authentication and forwards authenticated requests to budpipeline.

```
External Client → budapp (JWT validation) → budpipeline (Dapr token)
```

## Service Communication Patterns

### BudApp → BudPipeline

BudApp acts as a gateway, proxying pipeline API requests to budpipeline.

**Location**: `budapp/workflow_ops/budpipeline_service.py`

```python
class BudPipelineService:
    def __init__(self):
        self.dapr_http_endpoint = settings.DAPR_HTTP_ENDPOINT
        self.dapr_api_token = settings.DAPR_API_TOKEN

    async def _invoke_pipeline_service(
        self,
        method: str,
        path: str,
        data: dict = None,
    ) -> dict:
        """Invoke budpipeline via Dapr service invocation."""
        url = f"{self.dapr_http_endpoint}/v1.0/invoke/budpipeline/method{path}"
        headers = {"dapr-api-token": self.dapr_api_token}

        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=method,
                url=url,
                json=data,
                headers=headers,
            )
            return response.json()

    # Public methods
    async def create_workflow(self, dag: dict, name: str, user_id: str):
        return await self._invoke_pipeline_service(
            "POST", "/workflows",
            data={"dag": dag, "name": name, "created_by": user_id},
        )

    async def execute_workflow(self, workflow_id: str, params: dict, callback_topics: list):
        return await self._invoke_pipeline_service(
            "POST", f"/workflows/{workflow_id}/execute",
            data={"parameters": params, "callback_topics": callback_topics},
        )

    async def get_execution_status(self, execution_id: str):
        return await self._invoke_pipeline_service(
            "GET", f"/executions/{execution_id}",
        )
```

### BudPipeline → BudCluster

Pipeline step handlers invoke budcluster for cluster and deployment operations.

**Location**: `budpipeline/handlers/cluster_handlers.py`

```python
class DeployModelHandler(BaseHandler):
    async def execute(self, context: StepContext) -> StepResult:
        """Deploy a model to a cluster."""
        cluster_id = context.parameters["cluster_id"]
        model_id = context.parameters["model_id"]

        # Invoke budcluster to create deployment
        response = await invoke_dapr_service(
            app_id="budcluster",
            method_path=f"/api/v1/clusters/{cluster_id}/deployments",
            http_method="POST",
            data={
                "model_id": model_id,
                "config": context.parameters.get("config", {}),
            },
        )

        if response.get("status") == "accepted":
            # Return awaiting_event to wait for deployment completion
            return StepResult(
                status=StepStatus.RUNNING,
                awaiting_event=True,
                external_workflow_id=response["workflow_id"],
                outputs={"deployment_id": response["deployment_id"]},
            )

        return StepResult(
            status=StepStatus.FAILED,
            error=response.get("error", "Deployment request failed"),
        )
```

### BudCluster → BudPipeline (via Pub/Sub)

BudCluster publishes events to the `workflow-events` topic when long-running operations complete.

**Publisher (budcluster)**:
```python
# When deployment status changes
await dapr_client.publish_event(
    pubsub_name="budpubsub",
    topic_name="workflow-events",
    data={
        "event_type": "deployment_status",
        "event": "verify_deployment_status",
        "workflow_id": workflow_id,
        "status": "COMPLETED",  # or "FAILED"
        "content": {
            "deployment_id": deployment_id,
            "message": "Deployment successful",
        },
    },
)
```

**Subscriber (budpipeline)**:
```python
# Endpoint: POST /workflow-events
# Receives events via Dapr subscription
@app.post("/workflow-events")
async def handle_workflow_event(request: Request, db: AsyncSession = Depends(get_db)):
    event_data = await request.json()
    data = event_data.get("data", event_data)

    # Route to appropriate handler
    handled = await route_event(data, db)
    return {"status": "SUCCESS" if handled else "DROP"}
```

## Service Dependencies

```
┌─────────────┐
│   budapp    │  ← External clients (JWT auth)
└──────┬──────┘
       │ Dapr invoke
       ▼
┌─────────────┐     Dapr invoke      ┌─────────────┐
│ budpipeline │ ──────────────────► │ budcluster  │
└──────┬──────┘                      └──────┬──────┘
       │                                    │
       │ ◄──────────────────────────────────┘
       │         Dapr pub/sub
       │         (workflow-events)
       ▼
┌─────────────┐
│  budnotify  │  ← Notifications
└─────────────┘
```

## Error Handling

### Retry with Exponential Backoff

Service invocations use retry with exponential backoff:

```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(httpx.HTTPStatusError),
)
async def invoke_dapr_service(...):
    ...
```

### Circuit Breaker

For critical paths, circuit breaker prevents cascading failures:

```python
from budpipeline.commons.resilience import circuit_breaker

@circuit_breaker(failure_threshold=5, recovery_timeout=30)
async def invoke_critical_service(...):
    ...
```

### Timeout Handling

All service calls have configurable timeouts:

```python
async with httpx.AsyncClient(timeout=30.0) as client:
    response = await client.request(...)
```

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `DAPR_HTTP_ENDPOINT` | `http://localhost:3500` | Dapr sidecar HTTP endpoint |
| `DAPR_API_TOKEN` | - | Token for Dapr API authentication |
| `APP_API_TOKEN` | - | Token for internal endpoint authentication |
| `SERVICE_INVOKE_TIMEOUT` | `30` | Timeout for service invocations (seconds) |
| `SERVICE_INVOKE_MAX_RETRIES` | `3` | Max retry attempts |
