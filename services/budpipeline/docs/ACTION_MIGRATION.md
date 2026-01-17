# Action Migration Guide

This guide helps you migrate from the legacy handler system to the new pluggable action architecture.

## Overview

The legacy handler system in `budpipeline/handlers/` is being replaced with the new action architecture in `budpipeline/actions/`. The new system provides:

- **Declarative metadata** instead of scattered configuration
- **Entry point discovery** instead of manual registration
- **Standardized interfaces** for consistency
- **Better testability** with isolated modules

## Migration Timeline

| Phase | Status | Description |
|-------|--------|-------------|
| **Phase 1** | Complete | New action architecture implemented |
| **Phase 2** | Complete | Built-in actions migrated |
| **Phase 3** | Complete | API integration complete |
| **Phase 4** | In Progress | Deprecation warnings, documentation |
| **Phase 5** | Planned | Legacy handler removal |

## Code Comparison

### Before (Legacy Handler)

```python
# budpipeline/handlers/builtin.py

class LogHandler(BaseHandler):
    """Log a message."""

    def __init__(self):
        self.name = "log"
        self.description = "Log a message"

    async def execute(
        self,
        params: dict[str, Any],
        context: ExecutionContext,
    ) -> HandlerResult:
        message = params.get("message", "Step executed")
        level = params.get("level", "INFO")

        logger.log(level, message)

        return HandlerResult(
            success=True,
            outputs={"logged": True, "message": message},
        )

# Registration in handlers/__init__.py
from .builtin import LogHandler
handler_registry.register("log", LogHandler())
```

### After (New Action)

```python
# budpipeline/actions/builtin/log.py

from budpipeline.actions.base import (
    ActionMeta,
    ParamDefinition,
    ParamType,
    OutputDefinition,
    ExecutionMode,
    SelectOption,
    BaseActionExecutor,
    ActionContext,
    ActionResult,
)

META = ActionMeta(
    type="log",
    version="1.0.0",
    name="Log",
    description="Log a message to the pipeline execution log",
    category="Control Flow",
    icon="📝",
    color="#8c8c8c",
    params=[
        ParamDefinition(
            name="message",
            label="Message",
            type=ParamType.STRING,
            required=False,
            default="Step executed",
            description="The message to log",
        ),
        ParamDefinition(
            name="level",
            label="Log Level",
            type=ParamType.SELECT,
            required=False,
            default="INFO",
            options=[
                SelectOption(value="DEBUG", label="Debug"),
                SelectOption(value="INFO", label="Info"),
                SelectOption(value="WARNING", label="Warning"),
                SelectOption(value="ERROR", label="Error"),
            ],
        ),
    ],
    outputs=[
        OutputDefinition(
            name="logged",
            type="boolean",
            description="Whether the message was logged",
        ),
        OutputDefinition(
            name="message",
            type="string",
            description="The logged message",
        ),
    ],
    execution_mode=ExecutionMode.SYNC,
    idempotent=True,
    required_services=[],
    required_permissions=["pipeline:execute"],
)


class Executor(BaseActionExecutor):
    async def execute(self, context: ActionContext) -> ActionResult:
        message = context.params.get("message", "Step executed")
        level = context.params.get("level", "INFO")

        logger.log(level, message)

        return ActionResult(
            success=True,
            outputs={"logged": True, "message": message},
        )


class LogAction:
    meta = META
    executor_class = Executor
```

```toml
# pyproject.toml
[project.entry-points."budpipeline.actions"]
log = "budpipeline.actions.builtin.log:LogAction"
```

## Key Differences

### 1. Metadata Definition

| Aspect | Legacy | New |
|--------|--------|-----|
| Location | Scattered in handler class | Centralized in `ActionMeta` |
| Parameters | Undocumented dict keys | Typed `ParamDefinition` |
| Outputs | Undocumented | Typed `OutputDefinition` |
| Validation | Manual | Automatic from metadata |

### 2. Registration

| Aspect | Legacy | New |
|--------|--------|-----|
| Method | Manual `registry.register()` | Entry points in pyproject.toml |
| Discovery | Import-time registration | Runtime discovery via `importlib` |
| External packages | Not supported | Supported via entry points |

### 3. Context Object

| Aspect | Legacy `ExecutionContext` | New `ActionContext` |
|--------|---------------------------|---------------------|
| `step_id` | ✓ | ✓ |
| `execution_id` | ✓ | ✓ |
| `params` | ✓ (via separate arg) | ✓ (included in context) |
| `workflow_params` | ✗ | ✓ |
| `step_outputs` | ✗ | ✓ (access other step outputs) |
| `invoke_service()` | ✗ | ✓ (built-in Dapr calls) |
| `timeout_seconds` | ✗ | ✓ |
| `retry_count` | ✗ | ✓ |

### 4. Result Object

| Aspect | Legacy `HandlerResult` | New `ActionResult` |
|--------|------------------------|---------------------|
| `success` | ✓ | ✓ |
| `outputs` | ✓ | ✓ |
| `error` | ✓ | ✓ |
| `awaiting_event` | ✓ | ✓ |
| `external_workflow_id` | ✓ | ✓ |
| `timeout_seconds` | ✗ | ✓ |
| `metadata` | ✓ | ✗ (use outputs) |

## Migration Steps

### Step 1: Create New Action File

```bash
# Create file in appropriate category
touch budpipeline/actions/<category>/<action_name>.py
```

### Step 2: Define Metadata

Copy the handler's behavior into explicit `ActionMeta`:

```python
META = ActionMeta(
    type="my_handler",  # Same as legacy handler name
    version="1.0.0",
    name="My Handler",
    description="...",
    category="...",
    params=[...],       # Document all params
    outputs=[...],      # Document all outputs
    execution_mode=ExecutionMode.SYNC,  # or EVENT_DRIVEN
    idempotent=True,    # Set appropriately
    required_services=[],
    required_permissions=["pipeline:execute"],
)
```

### Step 3: Implement Executor

Adapt the `execute()` method:

```python
# Before
async def execute(self, params: dict, context: ExecutionContext) -> HandlerResult:
    # ...
    return HandlerResult(success=True, outputs={...})

# After
async def execute(self, context: ActionContext) -> ActionResult:
    # Access params via context
    value = context.params.get("key")
    # ...
    return ActionResult(success=True, outputs={...})
```

### Step 4: Implement Event Handler (if needed)

For event-driven handlers:

```python
# Before
async def on_event(self, event: dict, context: ExecutionContext) -> EventHandlerResult:
    # ...

# After
async def on_event(self, context: EventContext) -> EventResult:
    # Event data is in context.event_data
    if context.event_data.get("status") == "completed":
        return EventResult(
            action=EventAction.COMPLETE,
            status="completed",
            outputs={...},
        )
```

### Step 5: Create Action Class

```python
class MyAction:
    meta = META
    executor_class = Executor
```

### Step 6: Update __init__.py

```python
# budpipeline/actions/<category>/__init__.py
from .my_action import MyAction
```

### Step 7: Add Entry Point

```toml
# pyproject.toml
[project.entry-points."budpipeline.actions"]
my_handler = "budpipeline.actions.<category>.my_action:MyAction"
```

### Step 8: Reinstall Package

```bash
pip install -e .
```

### Step 9: Test

```bash
pytest tests/actions/<category>/test_my_action.py -v
```

## Event-Driven Action Migration

Event-driven handlers require special attention:

### Before

```python
class ModelAddHandler(BaseHandler):
    async def execute(self, params, context):
        workflow_id = await start_workflow(params)
        return HandlerResult(
            success=True,
            awaiting_event=True,
            external_workflow_id=workflow_id,
        )

    async def on_event(self, event, context):
        if event.get("event") == "workflow_completed":
            return EventHandlerResult(
                action=EventAction.COMPLETE,
                status=StepStatus.COMPLETED,
                outputs=event.get("content", {}),
            )
        return EventHandlerResult(action=EventAction.CONTINUE)
```

### After

```python
class Executor(BaseActionExecutor):
    async def execute(self, context: ActionContext) -> ActionResult:
        workflow_id = await start_workflow(context.params)
        return ActionResult(
            success=True,
            awaiting_event=True,
            external_workflow_id=workflow_id,
            timeout_seconds=context.params.get("max_wait_seconds", 1800),
        )

    async def on_event(self, context: EventContext) -> EventResult:
        if context.event_data.get("event") == "workflow_completed":
            return EventResult(
                action=EventAction.COMPLETE,
                status="completed",
                outputs=context.event_data.get("content", {}),
            )
        return EventResult(action=EventAction.IGNORE)
```

## Breaking Changes

1. **Parameter access**: Params are now in `context.params` instead of separate argument
2. **Return types**: Use `ActionResult` and `EventResult` instead of `HandlerResult` and `EventHandlerResult`
3. **Event actions**: `EventAction.CONTINUE` → `EventAction.IGNORE`
4. **Registration**: Manual registration no longer needed; entry points are required

## Backward Compatibility

During the migration period:

1. **Fallback lookup**: Pipeline service falls back to legacy handlers if action not found
2. **Deprecation warnings**: Using legacy handlers logs deprecation warnings
3. **Dual registration**: Some actions may be in both systems temporarily

## Deprecation Warnings

When using legacy handlers, you'll see warnings like:

```
DeprecationWarning: The handler registry is deprecated. Use action_registry instead.
```

To fix these warnings, migrate to the new action system or update imports:

```python
# Before
from budpipeline.handlers import handler_registry

# After
from budpipeline.actions import action_registry
```

## FAQ

### Q: Do I need to migrate all handlers at once?

No. The fallback mechanism allows gradual migration. Migrate high-priority handlers first.

### Q: Will my pipelines break during migration?

No. The pipeline service checks both registries, so existing pipelines continue to work.

### Q: How do I test my migrated action?

Create unit tests in `tests/actions/<category>/test_<action>.py`. See existing tests for examples.

### Q: What if my handler doesn't fit a category?

Create a new category directory under `actions/` and update the entry points accordingly.

### Q: Can external packages still provide actions?

Yes! External packages can register actions via entry points in their own `pyproject.toml`.
