# Event Flow Architecture

This document describes the event-driven architecture in BudPipeline, including event routing, pub/sub topics, and callback mechanisms.

## Overview

BudPipeline uses an event-driven architecture for:
1. **Long-running operations**: Steps can wait for external events to complete
2. **Progress updates**: Real-time progress published to subscribed topics
3. **Notifications**: Execution status changes trigger notifications

## Event-Driven Step Completion

### How It Works

Some pipeline steps trigger long-running operations in external services (e.g., model deployment, benchmarking). Instead of blocking, these steps return `awaiting_event=True` and wait for an event to complete them.

### Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 1. Pipeline Execution Starts                                            │
│    └─► Step handler returns: awaiting_event=True, external_workflow_id=X│
└────────────────────────────────────────┬────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 2. Step Saved to Database                                               │
│    └─► status=RUNNING, awaiting_event=True, external_workflow_id=X     │
└────────────────────────────────────────┬────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 3. External Service Performs Operation                                  │
│    └─► budcluster runs deployment, benchmarking, etc.                  │
└────────────────────────────────────────┬────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 4. External Service Publishes Event                                     │
│    └─► topic: "workflow-events", data: {workflow_id: X, status: ...}   │
└────────────────────────────────────────┬────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 5. BudPipeline Receives Event at /workflow-events                       │
│    └─► Dapr delivers event via subscription                            │
└────────────────────────────────────────┬────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 6. EventRouter Matches Event to Waiting Step                            │
│    └─► Finds step where external_workflow_id=X and awaiting_event=True │
└────────────────────────────────────────┬────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 7. Handler's on_event() Processes Event                                 │
│    └─► Returns EventHandlerResult with action and status               │
└────────────────────────────────────────┬────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 8. Step Updated Based on Result                                         │
│    └─► status=COMPLETED or FAILED, awaiting_event=False                │
└─────────────────────────────────────────────────────────────────────────┘
```

## Event Routing

### EventRouter

The `EventRouter` in `handlers/event_router.py` routes incoming events to the appropriate step handler.

```python
async def route_event(event_data: dict, db_session: AsyncSession) -> bool:
    """Route an incoming event to the waiting step that should handle it.

    Args:
        event_data: The event payload from Dapr pub/sub
        db_session: Database session for querying steps

    Returns:
        True if event was handled, False otherwise
    """
    # 1. Extract workflow_id from event (supports multiple field names)
    workflow_id = (
        event_data.get("workflow_id") or
        event_data.get("external_workflow_id") or
        event_data.get("content", {}).get("workflow_id")
    )

    if not workflow_id:
        logger.warning("Event missing workflow_id", event=event_data)
        return False

    # 2. Find step waiting for this event
    step_crud = StepExecutionCRUD(db_session)
    step = await step_crud.find_step_awaiting_event(workflow_id)

    if not step:
        logger.info(f"No step waiting for workflow_id={workflow_id}")
        return False

    # 3. Get handler for this step type
    handler = get_handler_for_step(step.step_type)
    if not handler:
        logger.error(f"No handler for step_type={step.step_type}")
        return False

    # 4. Build event context
    context = EventContext(
        step_execution_id=step.id,
        execution_id=step.execution_id,
        external_workflow_id=workflow_id,
        step_name=step.name,
        step_type=step.step_type,
    )

    # 5. Call handler's on_event method
    result = await handler.on_event(event_data, context)

    # 6. Process result
    if result.action == EventAction.COMPLETE:
        await step_crud.complete_step_from_event(
            step.id,
            step.version,
            status=result.status,
            outputs=result.outputs,
            error_message=result.error,
        )

        # Check if execution is complete
        await finalize_execution_if_done(step.execution_id, db_session)

    return True
```

### Finding Waiting Steps

```python
# In crud.py
async def find_step_awaiting_event(self, external_workflow_id: str) -> StepExecution | None:
    """Find a step that is waiting for an event with the given workflow ID."""
    result = await self.session.execute(
        select(StepExecution)
        .where(StepExecution.external_workflow_id == external_workflow_id)
        .where(StepExecution.awaiting_event == True)
        .where(StepExecution.status == StepStatus.RUNNING)
    )
    return result.scalar_one_or_none()
```

## Event Handler Interface

### BaseHandler

All step handlers extend `BaseHandler` and can implement `on_event()` for event-driven completion.

```python
class BaseHandler:
    async def execute(self, context: StepContext) -> StepResult:
        """Execute the step. Override in subclasses."""
        raise NotImplementedError

    async def on_event(self, event: dict, context: EventContext) -> EventHandlerResult:
        """Handle an incoming event. Override for event-driven steps."""
        # Default: ignore events
        return EventHandlerResult(action=EventAction.CONTINUE)
```

### EventHandlerResult

```python
class EventAction(Enum):
    COMPLETE = "complete"   # Step is done (success or failure)
    CONTINUE = "continue"   # Keep waiting for more events
    RETRY = "retry"         # Retry the step from beginning

class EventHandlerResult:
    action: EventAction
    status: StepStatus | None = None      # Required if action=COMPLETE
    outputs: dict | None = None           # Step outputs
    error: str | None = None              # Error message if failed
```

### Example: ModelBenchmarkHandler

```python
class ModelBenchmarkHandler(BaseHandler):
    async def execute(self, context: StepContext) -> StepResult:
        """Start a benchmark workflow in budcluster."""
        response = await invoke_dapr_service(
            app_id="budcluster",
            method_path="/api/v1/benchmarks",
            http_method="POST",
            data={
                "model_id": context.parameters["model_id"],
                "cluster_id": context.parameters["cluster_id"],
            },
        )

        # Return awaiting_event to wait for benchmark completion
        return StepResult(
            status=StepStatus.RUNNING,
            awaiting_event=True,
            external_workflow_id=response["workflow_id"],
            outputs={"benchmark_id": response["benchmark_id"]},
        )

    async def on_event(self, event: dict, context: EventContext) -> EventHandlerResult:
        """Handle benchmark events from budcluster."""
        event_name = event.get("event", "")
        status_str = event.get("status", "").upper()
        content = event.get("content", {})

        # Handle failure from any intermediate step
        if status_str == "FAILED":
            error_msg = content.get("message", f"Benchmark step '{event_name}' failed")
            return EventHandlerResult(
                action=EventAction.COMPLETE,
                status=StepStatus.FAILED,
                outputs={
                    "success": False,
                    "failed_step": event_name,
                    "message": error_msg,
                },
                error=error_msg,
            )

        # Handle successful completion (final results event)
        if event_name == "results":
            return EventHandlerResult(
                action=EventAction.COMPLETE,
                status=StepStatus.COMPLETED,
                outputs={
                    "success": True,
                    "results": content.get("results", {}),
                    "benchmark_id": content.get("benchmark_id"),
                },
            )

        # Keep waiting for more events (intermediate progress events)
        logger.info(f"Received intermediate event: {event_name}")
        return EventHandlerResult(action=EventAction.CONTINUE)
```

## Callback Topics (Multi-Topic Publishing)

### Overview

Clients can subscribe to pipeline execution updates by providing `callback_topics` when starting an execution.

```python
# API Request
POST /executions
{
    "workflow_id": "uuid",
    "parameters": {"model_id": "..."},
    "callback_topics": ["my-app-events", "analytics-events"]
}
```

### Subscription Storage

Callback topics are stored in the `ExecutionSubscription` table:

```python
class ExecutionSubscription(Base):
    __tablename__ = "execution_subscription"

    id = Column(UUID, primary_key=True, default=uuid4)
    execution_id = Column(UUID, ForeignKey("pipeline_execution.id"), nullable=False)
    topic_name = Column(String(255), nullable=False)
    pubsub_name = Column(String(100), default="budpubsub")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    execution = relationship("PipelineExecution", back_populates="subscriptions")
```

### Event Publisher

The `EventPublisher` class publishes events to all subscribed topics:

```python
class EventPublisher:
    def __init__(self, dapr_client: DaprClient):
        self.dapr_client = dapr_client
        self.retry_queue: asyncio.Queue = asyncio.Queue()
        self.retry_delay = 5  # seconds

    async def publish_progress_event(
        self,
        execution_id: UUID,
        event_type: str,
        data: dict,
        db_session: AsyncSession,
    ):
        """Publish event to all subscribed topics for an execution."""
        # Get all subscriptions for this execution
        sub_crud = ExecutionSubscriptionCRUD(db_session)
        subscriptions = await sub_crud.get_by_execution_id(execution_id)

        # Build event payload
        event_payload = {
            "execution_id": str(execution_id),
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "correlation_id": get_correlation_id(),
            **data,
        }

        # Publish to each topic
        for sub in subscriptions:
            try:
                await self.dapr_client.publish_event(
                    pubsub_name=sub.pubsub_name,
                    topic_name=sub.topic_name,
                    data=event_payload,
                )
                logger.info(f"Published {event_type} to {sub.topic_name}")
            except Exception as e:
                logger.error(f"Failed to publish to {sub.topic_name}: {e}")
                await self.retry_queue.put((sub, event_payload))

    async def start_retry_worker(self):
        """Background worker to retry failed publishes."""
        while True:
            sub, payload = await self.retry_queue.get()
            await asyncio.sleep(self.retry_delay)
            try:
                await self.dapr_client.publish_event(
                    pubsub_name=sub.pubsub_name,
                    topic_name=sub.topic_name,
                    data=payload,
                )
            except Exception as e:
                logger.error(f"Retry failed for {sub.topic_name}: {e}")
                # Could re-queue with exponential backoff
```

### Published Event Types

| Event Type | When Published | Payload |
|------------|---------------|---------|
| `execution.started` | Execution begins | `{execution_id, workflow_id, parameters}` |
| `execution.progress` | Overall progress changes | `{execution_id, progress_percentage, current_step}` |
| `step.started` | Step begins executing | `{execution_id, step_id, step_name, step_type}` |
| `step.progress` | Step progress updates | `{execution_id, step_id, progress_percentage, message}` |
| `step.completed` | Step finishes | `{execution_id, step_id, status, outputs, error}` |
| `execution.completed` | Execution finishes | `{execution_id, status, outputs, error_info}` |

### Example Event Payloads

**execution.started**:
```json
{
    "execution_id": "abc-123",
    "event_type": "execution.started",
    "timestamp": "2024-01-15T10:30:00Z",
    "correlation_id": "corr-xyz",
    "workflow_id": "def-456",
    "workflow_name": "Model Benchmark Pipeline",
    "parameters": {"model_id": "tinyllama", "cluster_id": "prod-cluster"}
}
```

**step.completed (success)**:
```json
{
    "execution_id": "abc-123",
    "event_type": "step.completed",
    "timestamp": "2024-01-15T10:35:00Z",
    "correlation_id": "corr-xyz",
    "step_id": "step-789",
    "step_name": "Benchmark TinyLlama",
    "status": "COMPLETED",
    "outputs": {"success": true, "throughput": 150.5}
}
```

**step.completed (failure)**:
```json
{
    "execution_id": "abc-123",
    "event_type": "step.completed",
    "timestamp": "2024-01-15T10:35:00Z",
    "correlation_id": "corr-xyz",
    "step_id": "step-789",
    "step_name": "Benchmark TinyLlama",
    "status": "FAILED",
    "error": "Engine deployment failed: Insufficient resources"
}
```

**execution.completed (failure)**:
```json
{
    "execution_id": "abc-123",
    "event_type": "execution.completed",
    "timestamp": "2024-01-15T10:40:00Z",
    "correlation_id": "corr-xyz",
    "status": "FAILED",
    "error_info": {
        "total_steps": 2,
        "failed_steps": 2,
        "failed_step_names": ["Benchmark TinyLlama", "Benchmark GPT2"]
    }
}
```

## Dapr Pub/Sub Configuration

### Topics Used

| Topic | Publisher | Subscriber | Purpose |
|-------|-----------|------------|---------|
| `workflow-events` | budcluster, budapp | budpipeline | External events for event-driven steps |
| `pipeline-notifications` | budpipeline | budnotify | Execution notifications |
| `{callback_topics}` | budpipeline | Client apps | Progress updates |

### Dapr Subscription Configuration

```yaml
# dapr/components/subscription.yaml
apiVersion: dapr.io/v1alpha1
kind: Subscription
metadata:
  name: workflow-events-subscription
spec:
  topic: workflow-events
  route: /workflow-events
  pubsubname: budpubsub
```

### Workflow Events Endpoint

```python
@app.post("/workflow-events")
async def handle_workflow_event(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Receive events from Dapr pub/sub for event-driven steps.

    This endpoint is called by Dapr when events are published to
    the 'workflow-events' topic.

    Returns:
        - {"status": "SUCCESS"} - Event was handled, Dapr won't retry
        - {"status": "DROP"} - Event wasn't handled, but don't retry
        - {"status": "RETRY"} - Temporary failure, Dapr should retry
    """
    try:
        # Parse CloudEvents envelope
        event_data = await request.json()
        data = event_data.get("data", event_data)

        logger.info(
            "Received workflow event",
            event_type=data.get("event_type"),
            workflow_id=data.get("workflow_id"),
        )

        # Route to appropriate handler
        handled = await route_event(data, db)

        if handled:
            return {"status": "SUCCESS"}
        else:
            # No handler found - drop to prevent infinite retries
            logger.warning("No handler for event", event=data)
            return {"status": "DROP"}

    except Exception as e:
        logger.exception("Error processing workflow event")
        return {"status": "RETRY"}
```

## Error Handling

### Step Failure from Events

When an event indicates failure, the step is marked as failed:

```python
# In crud.py
async def complete_step_from_event(
    self,
    step_uuid: UUID,
    expected_version: int,
    status: StepStatus,
    outputs: dict | None = None,
    error_message: str | None = None,
) -> StepExecution:
    """Complete a step that was awaiting an event."""

    # Progress: 100% for success, 0% for failure (NOT NULL constraint)
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

When steps fail, the execution aggregates failure information:

```python
async def finalize_execution_if_done(execution_id: UUID, db_session: AsyncSession):
    """Check if execution is complete and finalize status."""
    step_crud = StepExecutionCRUD(db_session)
    exec_crud = PipelineExecutionCRUD(db_session)

    steps = await step_crud.get_by_execution_id(execution_id)
    execution = await exec_crud.get_by_id(execution_id)

    # Check if all steps are done
    pending_steps = [s for s in steps if s.status in (StepStatus.PENDING, StepStatus.RUNNING)]
    if pending_steps:
        return  # Not done yet

    # Determine final status
    failed_steps = [s for s in steps if s.status == StepStatus.FAILED]

    if failed_steps:
        await exec_crud.update_with_version(
            execution_id,
            execution.version,
            status=ExecutionStatus.FAILED,
            end_time=datetime.utcnow(),
            error_info={
                "total_steps": len(steps),
                "failed_steps": len(failed_steps),
                "failed_step_names": [s.name for s in failed_steps],
            },
        )
    else:
        # All steps completed successfully
        outputs = {}
        for step in steps:
            if step.outputs:
                outputs[step.name] = step.outputs

        await exec_crud.update_with_version(
            execution_id,
            execution.version,
            status=ExecutionStatus.COMPLETED,
            end_time=datetime.utcnow(),
            outputs=outputs,
        )

    # Publish completion event to callback topics
    await publisher.publish_progress_event(
        execution_id,
        "execution.completed",
        {"status": execution.status.value, "error_info": execution.error_info},
        db_session,
    )
```

### Orphaned Events

Events for non-existent steps are logged and dropped:

```python
if not step:
    logger.warning(
        "Received event for unknown workflow_id",
        workflow_id=workflow_id,
        event_type=event_data.get("event_type"),
    )
    return False  # DROP - don't retry
```

## Best Practices

### For Event Publishers (External Services)

1. **Include workflow_id**: Always include the `workflow_id` returned when the step started
2. **Use consistent status values**: `COMPLETED`, `FAILED`, `RUNNING`
3. **Include error details**: When status is `FAILED`, include `message` in content
4. **Send intermediate events**: Progress events help with tracking
5. **Idempotent handling**: Events may be delivered multiple times

### For Event Handlers

1. **Handle all status values**: Check for `FAILED` status explicitly
2. **Return CONTINUE for progress**: Intermediate events shouldn't complete the step
3. **Include useful outputs**: Both success and failure should have informative outputs
4. **Log event processing**: Helps with debugging
5. **Handle unexpected events gracefully**: Return `CONTINUE` rather than failing
