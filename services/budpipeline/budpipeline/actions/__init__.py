"""Pipeline actions module.

This module provides the pluggable action architecture for budpipeline.
Actions are self-contained, modular components that can be extended or
added without affecting the base structure.

Usage:
    from budpipeline.actions import action_registry, ActionMeta, BaseActionExecutor

    # Discover all registered actions
    action_registry.discover_actions()

    # Get action metadata
    meta = action_registry.get_meta("model_add")

    # Get action executor
    executor = action_registry.get_executor("model_add")
"""

from .base import (
    ActionContext,
    ActionExample,
    ActionMeta,
    ActionRegistry,
    ActionResult,
    BaseActionExecutor,
    ConditionalVisibility,
    EventAction,
    EventContext,
    EventResult,
    ExecutionMode,
    OutputDefinition,
    ParamDefinition,
    ParamType,
    RetryPolicy,
    SelectOption,
    StepStatus,
    ValidationRules,
    action_registry,
    register_action,
)

__all__ = [
    # Registry
    "action_registry",
    "ActionRegistry",
    "register_action",
    # Metadata
    "ActionMeta",
    "ParamDefinition",
    "OutputDefinition",
    "ParamType",
    "ExecutionMode",
    "SelectOption",
    "ValidationRules",
    "ConditionalVisibility",
    "RetryPolicy",
    "ActionExample",
    # Context
    "ActionContext",
    "EventContext",
    # Results
    "ActionResult",
    "EventResult",
    "EventAction",
    "StepStatus",
    # Executor
    "BaseActionExecutor",
]
