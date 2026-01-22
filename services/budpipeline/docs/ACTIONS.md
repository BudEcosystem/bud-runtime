# Pluggable Action Architecture

This document describes the pluggable action architecture in budpipeline, which enables modular, extensible, and testable pipeline actions.

## Overview

The action architecture allows each pipeline action to be defined as an independent module with:
- **Declarative metadata** describing parameters, outputs, and behavior
- **Execution logic** in a standardized executor class
- **Automatic discovery** via Python entry points

This design enables:
- Dynamic action discovery at runtime
- Consistent parameter validation
- API-driven metadata for frontend rendering
- External action packages

## Architecture

```
budpipeline/actions/
├── base/                    # Core infrastructure
│   ├── meta.py              # ActionMeta, ParamDefinition, etc.
│   ├── context.py           # ActionContext, EventContext
│   ├── result.py            # ActionResult, EventResult
│   ├── executor.py          # BaseActionExecutor ABC
│   └── registry.py          # ActionRegistry singleton
├── builtin/                 # Control flow actions
│   ├── log.py               # Log messages
│   ├── delay.py             # Async delays
│   ├── conditional.py       # Multi-branch routing
│   ├── transform.py         # Data transformation
│   ├── aggregate.py         # Data aggregation
│   ├── set_output.py        # Set workflow outputs
│   └── fail.py              # Intentional failure
├── model/                   # Model operations
│   ├── add.py               # Add model (event-driven)
│   ├── delete.py            # Delete model
│   └── benchmark.py         # Benchmark model (event-driven)
├── cluster/                 # Cluster operations
│   └── health.py            # Cluster health check
├── deployment/              # Deployment operations (placeholders)
│   ├── create.py
│   ├── delete.py
│   ├── autoscale.py
│   └── ratelimit.py
└── integration/             # External integrations
    ├── http_request.py      # Generic HTTP requests
    ├── notification.py      # Send notifications
    └── webhook.py           # Trigger webhooks
```

## Creating a New Action

### Step 1: Create the Action File

Create a new Python file in the appropriate category directory:

```python
# budpipeline/actions/builtin/my_action.py

from budpipeline.actions.base import (
    ActionMeta,
    ParamDefinition,
    ParamType,
    OutputDefinition,
    ExecutionMode,
    BaseActionExecutor,
    ActionContext,
    ActionResult,
)
```

### Step 2: Define the Metadata

```python
META = ActionMeta(
    type="my_action",                    # Unique identifier
    version="1.0.0",                     # Semantic version
    name="My Action",                    # Display name
    description="Performs a custom operation",
    category="Control Flow",             # Grouping category
    icon="⚙️",                           # Icon for UI
    color="#1890ff",                     # Theme color
    params=[
        ParamDefinition(
            name="input_value",
            label="Input Value",
            type=ParamType.STRING,
            required=True,
            description="The value to process",
            placeholder="Enter a value...",
        ),
        ParamDefinition(
            name="uppercase",
            label="Convert to Uppercase",
            type=ParamType.BOOLEAN,
            required=False,
            default=False,
        ),
    ],
    outputs=[
        OutputDefinition(
            name="result",
            type="string",
            description="The processed result",
        ),
    ],
    execution_mode=ExecutionMode.SYNC,
    idempotent=True,
    required_services=[],
    required_permissions=["pipeline:execute"],
)
```

### Step 3: Implement the Executor

```python
class Executor(BaseActionExecutor):
    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute the action."""
        input_value = context.params.get("input_value", "")
        uppercase = context.params.get("uppercase", False)

        result = input_value.upper() if uppercase else input_value

        return ActionResult(
            success=True,
            outputs={"result": result},
        )

    def validate_params(self, params: dict) -> list[str]:
        """Optional: Custom parameter validation."""
        errors = []
        if not params.get("input_value"):
            errors.append("input_value is required")
        return errors
```

### Step 4: Export the Action Class

```python
class MyAction:
    """My custom action."""
    meta = META
    executor_class = Executor
```

### Step 5: Update Category __init__.py

```python
# budpipeline/actions/builtin/__init__.py
from .my_action import MyAction

__all__ = [
    # ... existing exports
    "MyAction",
]
```

### Step 6: Register via Entry Points

Add to `pyproject.toml`:

```toml
[project.entry-points."budpipeline.actions"]
my_action = "budpipeline.actions.builtin.my_action:MyAction"
```

### Step 7: Reinstall the Package

```bash
pip install -e .
```

## Parameter Types Reference

| Type | UI Rendering | Value Type |
|------|--------------|------------|
| `STRING` | Text input | `str` |
| `NUMBER` | Numeric input | `int` or `float` |
| `BOOLEAN` | Checkbox | `bool` |
| `SELECT` | Dropdown | `str` (from options) |
| `MULTISELECT` | Multi-select dropdown | `list[str]` |
| `JSON` | JSON editor | `dict` or `list` |
| `TEMPLATE` | Template editor (Jinja2) | `str` |
| `BRANCHES` | Branch editor | `list[Branch]` |
| `MODEL_REF` | Model picker | `str` (UUID) |
| `CLUSTER_REF` | Cluster picker | `str` (UUID) |
| `PROJECT_REF` | Project picker | `str` (UUID) |
| `ENDPOINT_REF` | Endpoint picker | `str` (UUID) |

## Validation Rules

Parameters can include validation rules:

```python
ParamDefinition(
    name="count",
    label="Count",
    type=ParamType.NUMBER,
    required=True,
    validation=ValidationRules(
        min=1,
        max=100,
    ),
)

ParamDefinition(
    name="email",
    label="Email",
    type=ParamType.STRING,
    required=True,
    validation=ValidationRules(
        pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$",
        pattern_message="Must be a valid email address",
    ),
)
```

## Conditional Visibility

Parameters can be shown/hidden based on other parameter values:

```python
ParamDefinition(
    name="use_custom_timeout",
    label="Use Custom Timeout",
    type=ParamType.BOOLEAN,
    default=False,
),
ParamDefinition(
    name="timeout_seconds",
    label="Timeout (seconds)",
    type=ParamType.NUMBER,
    default=30,
    visible_when=ConditionalVisibility(
        param="use_custom_timeout",
        equals=True,
    ),
)
```

## Execution Modes

### Synchronous Actions (SYNC)

Actions that complete within a single execution:

```python
class Executor(BaseActionExecutor):
    async def execute(self, context: ActionContext) -> ActionResult:
        # Do work...
        return ActionResult(success=True, outputs={"result": "done"})
```

### Event-Driven Actions (EVENT_DRIVEN)

Actions that wait for external events to complete:

```python
class Executor(BaseActionExecutor):
    async def execute(self, context: ActionContext) -> ActionResult:
        # Start external operation
        workflow_id = await start_external_operation(context.params)

        return ActionResult(
            success=True,
            awaiting_event=True,
            external_workflow_id=workflow_id,
            timeout_seconds=1800,  # Max wait time
            outputs={"status": "waiting"},
        )

    async def on_event(self, context: EventContext) -> EventResult:
        """Handle completion event."""
        if context.event_data.get("status") == "completed":
            return EventResult(
                action=EventAction.COMPLETE,
                status="completed",
                outputs={"result": context.event_data.get("result")},
            )
        elif context.event_data.get("status") == "failed":
            return EventResult(
                action=EventAction.COMPLETE,
                status="failed",
                error=context.event_data.get("error"),
            )
        # Keep waiting
        return EventResult(action=EventAction.IGNORE)
```

## Service Invocation

Actions can call other services via Dapr:

```python
async def execute(self, context: ActionContext) -> ActionResult:
    response = await context.invoke_service(
        app_id="budcluster",
        method_path="/api/v1/clusters/{cluster_id}/health",
        method="GET",
    )
    return ActionResult(success=True, outputs=response)
```

## Testing Actions

### Unit Tests

```python
# tests/actions/builtin/test_my_action.py
import pytest
from budpipeline.actions.builtin.my_action import META, Executor
from budpipeline.actions.base import ActionContext

class TestMyAction:
    def test_meta_attributes(self):
        assert META.type == "my_action"
        assert META.category == "Control Flow"
        assert len(META.params) > 0

    @pytest.mark.asyncio
    async def test_execute_basic(self):
        context = ActionContext(
            step_id="step-1",
            execution_id="exec-1",
            params={"input_value": "hello"},
        )
        executor = Executor()
        result = await executor.execute(context)

        assert result.success is True
        assert result.outputs["result"] == "hello"

    def test_validate_params_missing_required(self):
        executor = Executor()
        errors = executor.validate_params({})
        assert "input_value is required" in errors
```

### Integration Tests

```python
@pytest.mark.asyncio
async def test_action_via_api(test_client):
    # Test via Actions API
    response = await test_client.get("/actions/my_action")
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "my_action"
```

## API Endpoints

The Actions API exposes metadata for all registered actions:

| Endpoint | Description |
|----------|-------------|
| `GET /actions` | List all actions with metadata |
| `GET /actions/{type}` | Get specific action metadata |
| `POST /actions/validate` | Validate parameters for an action |

### Example Response

```json
GET /actions/log
{
  "type": "log",
  "version": "1.0.0",
  "name": "Log",
  "description": "Log a message to the pipeline execution log",
  "category": "Control Flow",
  "icon": "📝",
  "color": "#8c8c8c",
  "params": [
    {
      "name": "message",
      "label": "Message",
      "type": "string",
      "required": false,
      "default": "Step executed",
      "description": "The message to log"
    },
    {
      "name": "level",
      "label": "Log Level",
      "type": "select",
      "required": false,
      "default": "INFO",
      "options": [
        {"value": "DEBUG", "label": "Debug"},
        {"value": "INFO", "label": "Info"},
        {"value": "WARNING", "label": "Warning"},
        {"value": "ERROR", "label": "Error"}
      ]
    }
  ],
  "outputs": [
    {
      "name": "logged",
      "type": "boolean",
      "description": "Whether the message was logged"
    }
  ],
  "executionMode": "sync",
  "idempotent": true,
  "requiredServices": [],
  "requiredPermissions": ["pipeline:execute"]
}
```

## Best Practices

1. **Keep actions focused**: Each action should do one thing well
2. **Use descriptive names**: Action type should clearly indicate purpose
3. **Document parameters**: Every parameter should have a description
4. **Handle errors gracefully**: Return clear error messages
5. **Test thoroughly**: Unit test all execution paths
6. **Version appropriately**: Increment version on breaking changes
7. **Mark idempotency**: Set `idempotent=True` only if safe to retry
8. **List dependencies**: Include required services and permissions
