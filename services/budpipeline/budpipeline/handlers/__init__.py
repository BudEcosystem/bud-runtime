"""Handlers module - event routing for pipeline steps.

NOTE: The legacy handler system has been removed.
All action implementations are now in budpipeline.actions/ using the
pluggable action architecture.

This module now only contains:
- event_router: Routes incoming events to action executors

For creating new actions, use the actions module:
    from budpipeline.actions.base import (
        ActionMeta,
        ParamDefinition,
        BaseActionExecutor,
        ActionContext,
        ActionResult,
        action_registry,
    )

See the documentation at:
    services/budpipeline/docs/ACTIONS.md
    services/budpipeline/docs/ACTION_MIGRATION.md
"""

from budpipeline.handlers.event_router import (
    EventRouteResult,
    extract_workflow_id,
    get_steps_awaiting_events,
    process_timeout,
    route_event,
    trigger_pipeline_continuation,
)

__all__ = [
    "EventRouteResult",
    "extract_workflow_id",
    "get_steps_awaiting_events",
    "process_timeout",
    "route_event",
    "trigger_pipeline_continuation",
]
