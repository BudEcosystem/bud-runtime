# Creating BudPipeline Actions

This guide explains how to create new actions for the BudPipeline service, including best practices and common pitfalls learned from real implementation experience.

## Table of Contents

1. [Overview](#overview)
2. [Action Structure](#action-structure)
3. [Creating a Sync Action](#creating-a-sync-action)
4. [Creating an Event-Driven Action](#creating-an-event-driven-action)
5. [Registering Actions](#registering-actions)
6. [Calling External Services](#calling-external-services)
7. [Common Pitfalls & Lessons Learned](#common-pitfalls--lessons-learned)
8. [Testing Actions](#testing-actions)
9. [Reference](#reference)

---

## Overview

BudPipeline uses a **pluggable action architecture** where each action is defined by:

1. **`ActionMeta`** - Declarative metadata (name, parameters, outputs, execution mode)
2. **`BaseActionExecutor`** - Implementation class with `execute()` and optionally `on_event()`
3. **Entry Point Registration** - Python entry points for automatic discovery

Actions can be:
- **Sync** (`ExecutionMode.SYNC`) - Complete immediately and return result
- **Event-Driven** (`ExecutionMode.EVENT_DRIVEN`) - Initiate operation, wait for external events

---

## Action Structure

Every action requires three components:

```
budpipeline/actions/<category>/my_action.py
├── META (ActionMeta)           # Declarative metadata
├── Executor (BaseActionExecutor) # Implementation
└── ActionClass                 # Combines meta + executor
```

### Basic Template

```python
"""My Action - Brief description."""

from budpipeline.actions.base import (
    ActionContext,
    ActionMeta,
    ActionResult,
    BaseActionExecutor,
    ExecutionMode,
    OutputDefinition,
    ParamDefinition,
    ParamType,
    register_action,
)

import structlog

logger = structlog.get_logger(__name__)


class MyActionExecutor(BaseActionExecutor):
    """Executor for my action."""

    async def execute(self, context: ActionContext) -> ActionResult:
        # Implementation here
        pass


META = ActionMeta(
    type="my_action",  # Unique identifier
    version="1.0.0",
    name="My Action",
    description="What this action does",
    category="Category",
    # ... more fields
)


@register_action(META)
class MyAction:
    """My action class."""
    meta = META
    executor_class = MyActionExecutor
```

---

## Creating a Sync Action

Sync actions complete immediately and return a result.

### Example: Log Action

```python
from budpipeline.actions.base import (
    ActionContext,
    ActionMeta,
    ActionResult,
    BaseActionExecutor,
    ExecutionMode,
    OutputDefinition,
    ParamDefinition,
    ParamType,
    register_action,
)

import structlog

logger = structlog.get_logger(__name__)


class LogExecutor(BaseActionExecutor):
    """Executor for log action."""

    async def execute(self, context: ActionContext) -> ActionResult:
        message = context.params.get("message", "")
        level = context.params.get("level", "info")

        # Log the message
        log_func = getattr(logger, level, logger.info)
        log_func("pipeline_log", message=message, step_id=context.step_id)

        return ActionResult(
            success=True,
            outputs={
                "logged": True,
                "message": message,
                "level": level,
            },
        )


META = ActionMeta(
    type="log",
    version="1.0.0",
    name="Log",
    description="Logs a message to the pipeline execution log",
    category="Control Flow",
    icon="📝",
    execution_mode=ExecutionMode.SYNC,  # Sync action
    idempotent=True,
    required_services=[],
    params=[
        ParamDefinition(
            name="message",
            label="Message",
            type=ParamType.STRING,
            required=True,
            description="The message to log",
        ),
        ParamDefinition(
            name="level",
            label="Log Level",
            type=ParamType.SELECT,
            default="info",
            options=[
                SelectOption(label="Debug", value="debug"),
                SelectOption(label="Info", value="info"),
                SelectOption(label="Warning", value="warning"),
                SelectOption(label="Error", value="error"),
            ],
        ),
    ],
    outputs=[
        OutputDefinition(name="logged", type="boolean", description="Whether logging succeeded"),
        OutputDefinition(name="message", type="string", description="The logged message"),
    ],
)


@register_action(META)
class LogAction:
    meta = META
    executor_class = LogExecutor
```

---

## Creating an Event-Driven Action

Event-driven actions are for long-running operations that complete asynchronously.

### Key Concepts

1. **`execute()`** - Initiates the operation, returns `awaiting_event=True`
2. **`on_event()`** - Handles completion events from external services
3. **`external_workflow_id`** - Correlation ID to match events to waiting steps
4. **`callback_topic`** - Tell external services where to send completion events

### Example: Deployment Delete Action

```python
from budpipeline.actions.base import (
    ActionContext,
    ActionMeta,
    ActionResult,
    BaseActionExecutor,
    EventAction,
    EventContext,
    EventResult,
    ExecutionMode,
    OutputDefinition,
    ParamDefinition,
    ParamType,
    StepStatus,
    register_action,
)
from budpipeline.commons.config import settings
from budpipeline.commons.constants import CALLBACK_TOPIC

import structlog

logger = structlog.get_logger(__name__)


class DeploymentDeleteExecutor(BaseActionExecutor):
    """Executor for deleting deployments."""

    async def execute(self, context: ActionContext) -> ActionResult:
        """Initiate delete operation."""
        endpoint_id = context.params.get("endpoint_id", "")

        try:
            # CRITICAL: Pass callback_topic so events are published back
            response = await context.invoke_service(
                app_id=settings.budapp_app_id,
                method_path=f"endpoints/{endpoint_id}/delete-workflow",
                http_method="POST",
                data={"callback_topic": CALLBACK_TOPIC},
                timeout_seconds=60,
            )

            # Extract workflow_id from response for event matching
            workflow_id = response.get("workflow_id")

            if workflow_id:
                # Event-driven: wait for completion events
                return ActionResult(
                    success=True,
                    awaiting_event=True,
                    external_workflow_id=str(workflow_id),  # CRITICAL: Must match event's workflow_id
                    timeout_seconds=300,
                    outputs={
                        "endpoint_id": endpoint_id,
                        "workflow_id": str(workflow_id),
                        "status": "deleting",
                    },
                )

            # Sync completion (e.g., cloud model)
            return ActionResult(
                success=True,
                outputs={"endpoint_id": endpoint_id, "status": "deleted"},
            )

        except Exception as e:
            return ActionResult(
                success=False,
                error=str(e),
                outputs={"endpoint_id": endpoint_id, "status": "failed"},
            )

    async def on_event(self, context: EventContext) -> EventResult:
        """Handle completion events from external service."""
        event_type = context.event_data.get("type", "")
        payload = context.event_data.get("payload", {})
        event_name = payload.get("event", "")
        content = payload.get("content", {})
        status = content.get("status", "")

        logger.info(
            "delete_event_received",
            step_execution_id=context.step_execution_id,
            event_type=event_type,
            event_name=event_name,
            status=status,
        )

        # Handle completion
        if event_name == "results" and status == "COMPLETED":
            return EventResult(
                action=EventAction.COMPLETE,
                status=StepStatus.COMPLETED,
                outputs={
                    "success": True,
                    "endpoint_id": context.step_outputs.get("endpoint_id"),
                    "status": "deleted",
                    "message": content.get("message", "Deleted successfully"),
                },
            )

        # Handle failure
        if status == "FAILED":
            error_msg = content.get("message", "Operation failed")
            return EventResult(
                action=EventAction.COMPLETE,
                status=StepStatus.FAILED,
                outputs={"success": False, "status": "failed"},
                error=error_msg,
            )

        # Ignore intermediate events, keep waiting
        return EventResult(action=EventAction.IGNORE)
```

---

## Registering Actions

Actions are discovered via Python entry points.

### 1. Add to `pyproject.toml`

```toml
[project.entry-points."budpipeline.actions"]
log = "budpipeline.actions.builtin.log:LogAction"
delay = "budpipeline.actions.builtin.delay:DelayAction"
deployment_delete = "budpipeline.actions.deployment.delete:DeploymentDeleteAction"
# Add your action here
my_action = "budpipeline.actions.category.my_action:MyAction"
```

### 2. Verify Registration

```python
from budpipeline.actions import action_registry

action_registry.discover_actions()
print(action_registry.list_actions())  # Should include "my_action"
```

---

## Calling External Services

Use `context.invoke_service()` for Dapr service invocation:

```python
response = await context.invoke_service(
    app_id="budapp",              # Target service
    method_path="endpoints/123/delete-workflow",  # Endpoint path
    http_method="POST",           # HTTP method
    data={"callback_topic": CALLBACK_TOPIC},  # Request body
    params={"user_id": "abc"},    # Query params
    timeout_seconds=60,           # Timeout
)
```

### Critical: Callback Topics

**Always pass `callback_topic`** when calling services that trigger async workflows:

```python
data={"callback_topic": CALLBACK_TOPIC}
```

This tells the external service (budapp, budcluster) where to publish completion events. Without this, your action will timeout waiting for events that never arrive.

---

## Common Pitfalls & Lessons Learned

### 1. Pydantic Schema Validation Errors

**Problem**: When adding new fields to API responses, Pydantic validation fails.

**Root Cause**: `SuccessResponse` in budapp uses `ConfigDict(extra="forbid")`, rejecting unknown fields.

**Wrong Approach**:
```python
# This will FAIL - SuccessResponse doesn't allow extra fields
return SuccessResponse(
    message="Success",
    data={"workflow_id": str(workflow.id)},  # ❌ FAILS
)
```

**Correct Approach**: Create a custom response schema:
```python
# In budapp/endpoint_ops/schemas.py
from budapp.commons.schemas import SuccessResponse

class EndpointDeleteResponse(SuccessResponse):
    """Response schema for endpoint delete operation."""
    workflow_id: Optional[UUID] = None

# In routes.py
return EndpointDeleteResponse(
    message="Delete initiated",
    workflow_id=db_workflow.id,  # ✅ WORKS
)
```

### 2. Event Matching with external_workflow_id

**Problem**: Events aren't matched to waiting steps.

**Root Cause**: The `external_workflow_id` in `ActionResult` must exactly match the `workflow_id` in incoming events.

**Solution**: Ensure the external service returns the same ID you use for matching:

```python
# In execute():
workflow_id = response.get("workflow_id")
return ActionResult(
    awaiting_event=True,
    external_workflow_id=str(workflow_id),  # Must match event's workflow_id
)

# External service must publish events with matching workflow_id:
# {"payload": {"workflow_id": "<same-id>"}}
```

### 3. Missing callback_topic

**Problem**: Action waits forever; no events arrive.

**Solution**: Always pass `callback_topic` to external services:

```python
response = await context.invoke_service(
    app_id="budapp",
    method_path="endpoints/{id}/delete-workflow",
    data={"callback_topic": CALLBACK_TOPIC},  # CRITICAL!
)
```

### 4. Forgetting to Handle Failure Events

**Problem**: Steps hang when external operations fail.

**Solution**: Always handle FAILED status in `on_event()`:

```python
async def on_event(self, context: EventContext) -> EventResult:
    status = context.event_data.get("payload", {}).get("content", {}).get("status", "")

    if status == "FAILED":
        return EventResult(
            action=EventAction.COMPLETE,
            status=StepStatus.FAILED,  # Don't forget to set FAILED status
            error=error_msg,
        )
    # ... handle success
```

### 5. Not Returning Consistent Outputs

**Problem**: Pipeline DAG can't reference step outputs reliably.

**Solution**: Always return consistent output structure:

```python
# Good: Always return the same output keys
return ActionResult(
    success=True,
    outputs={
        "success": True,
        "endpoint_id": endpoint_id,
        "status": "deleted",
        "message": "...",
    },
)

return ActionResult(
    success=False,
    outputs={
        "success": False,          # Same keys!
        "endpoint_id": endpoint_id,
        "status": "failed",
        "message": error_msg,
    },
    error=error_msg,
)
```

### 6. Type Mismatches in workflow_id

**Problem**: UUID vs string comparison fails.

**Solution**: Always convert to string for consistency:

```python
external_workflow_id=str(workflow_id)  # Always string
```

---

## Testing Actions

### Unit Test Template

```python
import pytest
from unittest.mock import AsyncMock, patch
from budpipeline.actions.deployment.delete import DeploymentDeleteExecutor
from budpipeline.actions.base import ActionContext, EventContext, EventAction, StepStatus


@pytest.fixture
def context():
    return ActionContext(
        step_id="step_1",
        execution_id="exec_1",
        params={"endpoint_id": "endpoint-123"},
        workflow_params={"user_id": "user-123"},
        step_outputs={},
    )


@pytest.mark.asyncio
async def test_execute_returns_awaiting_event(context):
    """Test that execute returns awaiting_event for async operations."""
    executor = DeploymentDeleteExecutor()

    with patch.object(context, "invoke_service", new_callable=AsyncMock) as mock_invoke:
        mock_invoke.return_value = {"workflow_id": "wf-123", "code": 200}

        result = await executor.execute(context)

        assert result.success is True
        assert result.awaiting_event is True
        assert result.external_workflow_id == "wf-123"


@pytest.mark.asyncio
async def test_on_event_completes_on_success():
    """Test that on_event completes the step on success event."""
    executor = DeploymentDeleteExecutor()
    event_context = EventContext(
        step_execution_id="step-exec-1",
        execution_id="exec-1",
        external_workflow_id="wf-123",
        event_type="notification",
        event_data={
            "type": "notification",
            "payload": {
                "event": "results",
                "content": {"status": "COMPLETED", "message": "Deleted"},
            },
        },
        step_outputs={"endpoint_id": "endpoint-123"},
    )

    result = await executor.on_event(event_context)

    assert result.action == EventAction.COMPLETE
    assert result.status == StepStatus.COMPLETED
    assert result.outputs["success"] is True
```

### Integration Testing

1. Deploy the action to a test environment
2. Create a test pipeline using the action
3. Execute and verify event flow via logs:

```bash
kubectl logs -n pde-ditto deployment/ditto-budpipeline -c budpipeline --tail=100 | grep -i "your_action"
```

---

## Reference

### ActionMeta Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | str | Yes | Unique identifier (e.g., "deployment_delete") |
| `version` | str | Yes | Semantic version (e.g., "1.0.0") |
| `name` | str | Yes | Human-readable name |
| `description` | str | Yes | What this action does |
| `category` | str | Yes | Grouping (e.g., "Deployment", "Model", "Control Flow") |
| `icon` | str | No | Icon identifier |
| `color` | str | No | Hex color for UI |
| `execution_mode` | ExecutionMode | Yes | `SYNC` or `EVENT_DRIVEN` |
| `timeout_seconds` | int | No | Default timeout |
| `idempotent` | bool | Yes | Safe to retry? |
| `required_services` | list[str] | Yes | Dapr services needed |
| `params` | list[ParamDefinition] | Yes | Parameter definitions |
| `outputs` | list[OutputDefinition] | Yes | Output definitions |

### ParamType Values

| Type | Description |
|------|-------------|
| `STRING` | Single-line text |
| `NUMBER` | Numeric with optional min/max |
| `BOOLEAN` | Checkbox |
| `SELECT` | Dropdown with options |
| `MULTISELECT` | Multi-select dropdown |
| `JSON` | JSON editor |
| `TEMPLATE` | Jinja2 template |
| `MODEL_REF` | Model reference (dynamic) |
| `CLUSTER_REF` | Cluster reference |
| `ENDPOINT_REF` | Endpoint reference |

### EventAction Values

| Action | Description |
|--------|-------------|
| `COMPLETE` | Finish the step (success or failure) |
| `UPDATE_PROGRESS` | Update progress, keep waiting |
| `IGNORE` | Ignore event, keep waiting |

### StepStatus Values

| Status | Description |
|--------|-------------|
| `PENDING` | Not started |
| `RUNNING` | In progress |
| `COMPLETED` | Successfully finished |
| `FAILED` | Failed with error |
| `TIMEOUT` | Timed out waiting |
| `SKIPPED` | Skipped (conditional) |

---

## Checklist for New Actions

- [ ] Created action file in `budpipeline/actions/<category>/`
- [ ] Defined `ActionMeta` with all required fields
- [ ] Implemented `BaseActionExecutor.execute()`
- [ ] For EVENT_DRIVEN: Implemented `on_event()`
- [ ] Added entry point to `pyproject.toml`
- [ ] External service returns `workflow_id` for event matching
- [ ] External service has custom response schema (not using `data={}` on SuccessResponse)
- [ ] Passing `callback_topic` to external services
- [ ] Handling both success and failure in `on_event()`
- [ ] Consistent output structure in all code paths
- [ ] Unit tests written
- [ ] Tested end-to-end in dev environment
