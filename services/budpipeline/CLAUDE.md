# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture Overview

BudPipeline is a FastAPI-based microservice for pipeline orchestration in the Bud Runtime ecosystem. It manages workflow definitions, executions, scheduling, and event-driven triggers.

### Key Technologies
- **Python 3.11** with FastAPI for REST API
- **PostgreSQL** with SQLAlchemy async ORM for persistence
- **Dapr** for service mesh, pub/sub, and state management
- **Alembic** for database migrations
- **Pydantic** for data validation
- **structlog** for structured logging

## Module Structure

Each module follows a consistent pattern:

```
budpipeline/
├── commons/                  # Shared utilities
│   ├── config.py            # Settings from environment
│   ├── database.py          # Async SQLAlchemy setup
│   ├── observability.py     # Logging, metrics, correlation IDs
│   ├── resilience.py        # Circuit breaker, retry, fallback
│   ├── sanitization.py      # Credential masking
│   └── rate_limiting.py     # API rate limiting
├── pipeline/                 # Core pipeline functionality
│   ├── models.py            # PipelineExecution, StepExecution models
│   ├── schemas.py           # Pydantic request/response schemas
│   ├── crud.py              # Database operations with optimistic locking
│   ├── service.py           # Business logic
│   ├── persistence_service.py  # Execution persistence with resilience
│   ├── routes.py            # Workflow CRUD endpoints
│   ├── execution_routes.py  # Execution endpoints with pagination
│   └── retention.py         # Cleanup workflow for old data
├── progress/                 # Progress tracking
│   ├── models.py            # ProgressEvent model
│   ├── schemas.py           # Event schemas
│   ├── crud.py              # Event CRUD operations
│   ├── service.py           # Aggregation with weighted averaging
│   ├── routes.py            # Progress event API endpoints
│   └── publisher.py         # Multi-topic event publishing
├── subscriptions/           # Callback subscriptions
│   ├── models.py            # ExecutionSubscription model
│   ├── schemas.py           # Subscription schemas
│   ├── crud.py              # Subscription CRUD
│   └── service.py           # Topic validation
├── scheduler/               # Schedule and trigger management
│   ├── routes.py            # Schedule/webhook/trigger endpoints
│   └── polling.py           # Cron-based schedule polling
├── handlers/                # Built-in step handlers
└── main.py                  # FastAPI application setup
```

## Key Patterns

### Optimistic Locking
Database models use version columns for concurrent update handling:
```python
class PipelineExecution(Base):
    version = Column(Integer, default=1)  # Incremented on update

# CRUD enforces version check
crud.update_with_version(id, expected_version, **updates)  # Raises OptimisticLockError if mismatch
```

### Resilience Stack
- **Circuit Breaker**: Opens after 5 failures, recovers after 30s
- **Retry with Backoff**: Exponential backoff (2^n seconds, max 3 attempts)
- **In-Memory Fallback**: Serves stale data when DB unavailable
- **Staleness Headers**: `X-Data-Staleness` indicates fallback mode

### Progress Aggregation
- Weighted averaging across concurrent steps
- Monotonic enforcement (progress never decreases)
- ETA estimation based on completed step durations

### Event Publishing
- Non-blocking async publishing to multiple topics
- Retry queue for failed publishes
- Correlation IDs in all events

## Development Commands

### Running the Service
```bash
# Start with Dapr sidecar
./deploy/start_dev.sh --build

# Stop
./deploy/stop_dev.sh
```

### Database Migrations
```bash
# Apply migrations
alembic -c budpipeline/alembic.ini upgrade head

# Create new migration
alembic -c budpipeline/alembic.ini revision --autogenerate -m "description"
```

### Code Quality
```bash
# Lint and format
ruff check . --fix && ruff format .

# Type checking
mypy budpipeline/

# Run tests
pytest --dapr-http-port 3510 --dapr-api-token <TOKEN>
```

## API Endpoints

### Pipeline Management
- `POST /workflows` - Create workflow
- `GET /workflows` - List workflows
- `GET /workflows/{id}` - Get workflow details
- `PUT /workflows/{id}` - Update workflow
- `DELETE /workflows/{id}` - Delete workflow

### Execution Management
- `POST /executions` - Start execution with optional `callback_topics`
- `GET /executions` - List executions with filters and pagination
- `GET /executions/{id}` - Get execution status
- `GET /executions/{id}/progress` - Get detailed progress with granularity options
- `GET /executions/{id}/steps` - Get step history
- `GET /executions/{id}/events` - Get progress events with filtering

### Scheduling
- `POST /schedules` - Create cron schedule
- `GET /schedules` - List schedules
- `POST /schedules/{id}/pause` - Pause schedule
- `POST /schedules/{id}/resume` - Resume schedule
- `POST /schedules/{id}/trigger` - Trigger immediately

### Webhooks & Triggers
- `POST /webhooks` - Create webhook trigger
- `POST /event-triggers` - Create event-based trigger

## Configuration

Key environment variables (see `.env.sample`):

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL connection string |
| `PIPELINE_RETENTION_DAYS` | `30` | Days to retain execution history |
| `PIPELINE_CLEANUP_SCHEDULE` | `0 3 * * *` | Cron for retention cleanup |
| `DB_RETRY_MAX_ATTEMPTS` | `3` | Max database retry attempts |
| `CIRCUIT_BREAKER_FAILURE_THRESHOLD` | `5` | Failures before circuit opens |

## Testing Guidelines

### Test File Organization
- `test_pipeline_crud.py` - CRUD with optimistic locking
- `test_progress_aggregation.py` - Weighted averaging, monotonic progress
- `test_api_endpoints.py` - API contract tests
- `test_subscriptions.py` - Topic validation
- `test_event_publishing.py` - Multi-topic publishing
- `test_historical_queries.py` - Date range, pagination
- `test_retention.py` - Cleanup workflow
- `test_multi_client.py` - Consistency tests

### Mocking Patterns
```python
# Mock database session
mock_session = AsyncMock()
mock_session.execute = AsyncMock()

# Mock CRUD operations
with patch("budpipeline.pipeline.crud.PipelineExecutionCRUD") as mock_crud:
    mock_crud.return_value.get_by_id = AsyncMock(return_value=mock_execution)
```

## Feature: Pipeline Event Persistence (002)

This feature adds durable persistence for pipeline executions:

### Database Models
- `PipelineExecution` - Execution state with optimistic locking
- `StepExecution` - Step-level state with progress percentage
- `ProgressEvent` - Timestamped progress events
- `ExecutionSubscription` - Callback topic subscriptions

### Key Functionality
1. **External Polling (US1)**: REST API for execution status/progress
2. **Real-time Events (US2)**: Pub/sub publishing to callback topics
3. **Historical Queries (US3)**: Filtered queries with pagination
4. **Multi-client Consistency (US4)**: Rate limiting, granularity options

### Integration Points
- **budapp**: Proxy endpoints with authentication
- **Dapr pub/sub**: Event publishing to callback topics
- **Dapr cron binding**: Retention cleanup scheduling

### Documentation
- [DAG Structure](docs/DAG_STRUCTURE.md) - Pipeline DAG schema and control flow patterns
- [Service Communication](docs/SERVICE_COMMUNICATION.md) - Dapr service invocation and authentication
- [Event Flow](docs/EVENT_FLOW.md) - Event-driven architecture and callback topics

## Service-to-Service Communication

### Dapr Service Invocation

BudPipeline communicates with other services using Dapr's service invocation pattern. The core utility is in `commons/dapr_utils.py`:

```python
async def invoke_dapr_service(
    app_id: str,           # Target service name (e.g., "budcluster", "budapp")
    method_path: str,      # Endpoint path (e.g., "/api/v1/health")
    http_method: str = "GET",
    data: dict | None = None,
    headers: dict | None = None,
) -> dict:
    """Invoke another service via Dapr sidecar."""
    url = f"{DAPR_HTTP_ENDPOINT}/v1.0/invoke/{app_id}/method{method_path}"
    # Adds dapr-api-token header for authentication
```

**URL Pattern**: `{dapr_http_endpoint}/v1.0/invoke/{app_id}/method/{method_path}`

**Example**: To call budcluster's health endpoint:
```python
response = await invoke_dapr_service("budcluster", "/api/v1/health")
```

### Authentication Between Services

#### 1. Dapr API Token (Service Mesh Level)
All inter-service calls via Dapr require the `dapr-api-token` header:
```python
headers = {"dapr-api-token": settings.DAPR_API_TOKEN}
```

#### 2. APP_API_TOKEN (Application Level)
Internal endpoints in budpipeline validate an additional application token:
```python
# In main.py - middleware validates internal endpoints
@app.middleware("http")
async def validate_internal_requests(request: Request, call_next):
    if request.url.path.startswith("/internal/") or request.url.path == "/workflow-events":
        token = request.headers.get("dapr-api-token")
        if token != settings.APP_API_TOKEN:
            return JSONResponse(status_code=403, content={"detail": "Forbidden"})
    return await call_next(request)
```

#### 3. Keycloak JWT (External API Level)
External API calls through budapp are authenticated via Keycloak JWT tokens. BudPipeline itself doesn't validate JWTs directly - budapp handles external auth and forwards requests.

### Service Communication Patterns

#### BudApp → BudPipeline
BudApp proxies pipeline requests to budpipeline using `BudPipelineService`:
```python
# In budapp/workflow_ops/budpipeline_service.py
class BudPipelineService:
    async def _invoke_pipeline_service(self, method: str, path: str, data: dict = None):
        """Invoke budpipeline via Dapr service invocation."""
        url = f"{self.dapr_http_endpoint}/v1.0/invoke/budpipeline/method{path}"
        headers = {"dapr-api-token": self.dapr_api_token}
        # Makes HTTP request via Dapr
```

#### BudPipeline → BudCluster
Pipeline handlers invoke budcluster for deployment operations:
```python
# In handlers/cluster_handlers.py
response = await invoke_dapr_service(
    app_id="budcluster",
    method_path="/api/v1/clusters/{cluster_id}/deployments",
    http_method="POST",
    data=deployment_request,
)
```

#### BudCluster → BudPipeline (via Pub/Sub)
BudCluster publishes events back to budpipeline when operations complete:
```python
# BudCluster publishes to topic
await dapr_client.publish_event(
    pubsub_name="budpubsub",
    topic_name="workflow-events",
    data={"event": "verify_deployment_status", "status": "FAILED", ...}
)

# BudPipeline receives via subscription endpoint /workflow-events
```

## Event Flow Architecture

### Event-Driven Step Completion

BudPipeline supports event-driven completion for long-running operations. A step can return `awaiting_event=True` and wait for an external event to complete it.

#### Flow Diagram:
```
1. Pipeline executes step → handler returns awaiting_event=True, external_workflow_id=X
2. Step saved with status=RUNNING, awaiting_event=True
3. External service (e.g., budcluster) performs operation
4. External service publishes event to "workflow-events" topic
5. BudPipeline receives event at /workflow-events endpoint
6. EventRouter matches event to waiting step via external_workflow_id
7. Handler's on_event() processes event and returns completion status
8. Step updated to COMPLETED or FAILED
```

### Event Routing

The `EventRouter` in `handlers/event_router.py` routes incoming events to the appropriate handler:

```python
async def route_event(event_data: dict, db_session: AsyncSession) -> bool:
    """Route an incoming event to the waiting step that should handle it."""

    # 1. Extract workflow_id from event
    workflow_id = event_data.get("workflow_id") or event_data.get("external_workflow_id")

    # 2. Find waiting step by external_workflow_id
    step = await crud.find_step_awaiting_event(workflow_id)
    if not step:
        return False  # No step waiting for this event

    # 3. Get the appropriate handler
    handler = get_handler_for_step(step.step_type)

    # 4. Call handler's on_event method
    result = await handler.on_event(event_data, context)

    # 5. Complete the step based on handler result
    if result.action == EventAction.COMPLETE:
        await crud.complete_step_from_event(
            step.id,
            step.version,
            status=result.status,
            outputs=result.outputs,
            error_message=result.error,
        )

    return True
```

### Event Handler Interface

Step handlers implement `on_event()` to process incoming events:

```python
class ModelBenchmarkHandler(BaseHandler):
    async def on_event(self, event: dict, context: EventContext) -> EventHandlerResult:
        """Handle incoming benchmark events from budcluster."""
        event_type = event.get("event_type")
        status = event.get("status", "").upper()
        content = event.get("content", {})

        # Handle failure events from intermediate steps
        if status == "FAILED":
            return EventHandlerResult(
                action=EventAction.COMPLETE,
                status=StepStatus.FAILED,
                outputs={"success": False, "message": content.get("message")},
                error=content.get("message"),
            )

        # Handle successful completion
        if event.get("event") == "results":
            return EventHandlerResult(
                action=EventAction.COMPLETE,
                status=StepStatus.COMPLETED,
                outputs={"success": True, "results": content.get("results")},
            )

        # Keep waiting for more events
        return EventHandlerResult(action=EventAction.CONTINUE)
```

### Event Handler Result Actions

```python
class EventAction(Enum):
    COMPLETE = "complete"   # Step is done (success or failure)
    CONTINUE = "continue"   # Keep waiting for more events
    RETRY = "retry"         # Retry the step
```

## Callback Topics (Multi-Topic Publishing)

### Overview

When starting a pipeline execution, clients can specify `callback_topics` - a list of Dapr pub/sub topics where progress updates will be published.

```python
# API request to start execution
POST /executions
{
    "workflow_id": "uuid",
    "parameters": {...},
    "callback_topics": ["my-app-events", "analytics-events"]
}
```

### Subscription Storage

Callback topics are stored in `ExecutionSubscription` model:

```python
class ExecutionSubscription(Base):
    __tablename__ = "execution_subscription"

    id = Column(UUID, primary_key=True)
    execution_id = Column(UUID, ForeignKey("pipeline_execution.id"))
    topic_name = Column(String(255), nullable=False)
    pubsub_name = Column(String(100), default="budpubsub")
    created_at = Column(DateTime(timezone=True))
```

### Event Publisher

The `EventPublisher` class in `progress/publisher.py` handles multi-topic publishing:

```python
class EventPublisher:
    def __init__(self, dapr_client: DaprClient):
        self.dapr_client = dapr_client
        self.retry_queue: asyncio.Queue = asyncio.Queue()

    async def publish_progress_event(
        self,
        execution_id: UUID,
        event_type: str,
        data: dict,
    ):
        """Publish progress event to all subscribed topics."""
        # Get subscriptions for this execution
        subscriptions = await subscription_crud.get_by_execution_id(execution_id)

        # Publish to each topic
        for sub in subscriptions:
            try:
                await self.dapr_client.publish_event(
                    pubsub_name=sub.pubsub_name,
                    topic_name=sub.topic_name,
                    data={
                        "execution_id": str(execution_id),
                        "event_type": event_type,
                        "correlation_id": get_correlation_id(),
                        **data,
                    },
                )
            except Exception as e:
                # Queue for retry
                await self.retry_queue.put((sub, data))

    async def start_retry_worker(self):
        """Background worker to retry failed publishes."""
        while True:
            sub, data = await self.retry_queue.get()
            await asyncio.sleep(self.retry_delay)
            await self._retry_publish(sub, data)
```

### Published Event Types

| Event Type | When Published | Data |
|------------|---------------|------|
| `execution.started` | Execution begins | `{execution_id, workflow_id, parameters}` |
| `execution.progress` | Progress updates | `{execution_id, progress_percentage, current_step}` |
| `step.started` | Step begins | `{execution_id, step_id, step_name}` |
| `step.progress` | Step progress | `{execution_id, step_id, progress_percentage, message}` |
| `step.completed` | Step finishes | `{execution_id, step_id, status, outputs}` |
| `execution.completed` | Execution finishes | `{execution_id, status, outputs, error_info}` |

## Dapr Pub/Sub Topics

### Topics Used by BudPipeline

| Topic | Publisher | Subscriber | Purpose |
|-------|-----------|------------|---------|
| `workflow-events` | budcluster, budapp | budpipeline | External events for event-driven steps |
| `pipeline-notifications` | budpipeline | budnotify | Execution notifications |
| `{callback_topics}` | budpipeline | Client apps | Progress updates to registered topics |

### Dapr Subscription Configuration

```yaml
# dapr/components/pubsub.yaml
apiVersion: dapr.io/v1alpha1
kind: Subscription
metadata:
  name: workflow-events-subscription
spec:
  topic: workflow-events
  route: /workflow-events
  pubsubname: budpubsub
```

### Workflow Event Endpoint

```python
# In main.py
@app.post("/workflow-events")
async def handle_workflow_event(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Receive events from Dapr pub/sub for event-driven steps."""
    event_data = await request.json()

    # Extract CloudEvents envelope
    data = event_data.get("data", event_data)

    # Route to appropriate handler
    handled = await route_event(data, db)

    if handled:
        return {"status": "SUCCESS"}
    else:
        logger.warning(f"No handler found for event: {data.get('event_type')}")
        return {"status": "DROP"}  # Don't retry unhandled events
```

## Error Handling in Events

### Failed Step Handling

When an external service reports failure:

```python
# In crud.py - complete_step_from_event()
async def complete_step_from_event(
    self,
    step_uuid: UUID,
    expected_version: int,
    status: StepStatus,
    outputs: dict | None = None,
    error_message: str | None = None,
) -> StepExecution:
    """Complete a step that was awaiting an event."""

    # For failed steps, set progress to 0% (NOT NULL constraint)
    progress = Decimal("100.00") if status == StepStatus.COMPLETED else Decimal("0.00")

    return await self.update_with_version(
        step_uuid,
        expected_version,
        status=status,
        awaiting_event=False,
        end_time=datetime.utcnow(),
        progress_percentage=progress,
        outputs=outputs,
        error_message=error_message,
    )
```

### Execution Failure Aggregation

When any step fails, the execution is marked as failed with error info:

```python
# In service.py
async def finalize_execution(self, execution_id: UUID):
    """Check if all steps are done and finalize execution."""
    steps = await step_crud.get_by_execution_id(execution_id)

    failed_steps = [s for s in steps if s.status == StepStatus.FAILED]

    if failed_steps:
        await execution_crud.update_with_version(
            execution_id,
            version,
            status=ExecutionStatus.FAILED,
            error_info={
                "total_steps": len(steps),
                "failed_steps": len(failed_steps),
                "failed_step_names": [s.name for s in failed_steps],
            },
        )
```
