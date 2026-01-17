"""Base classes and interfaces for pipeline actions.

This module exports all the core classes needed to define actions:
- ActionMeta: Declarative metadata for actions
- ParamDefinition, OutputDefinition: Parameter and output schemas
- ActionContext, EventContext: Execution contexts
- ActionResult, EventResult: Execution results
- BaseActionExecutor: Base class for executors
- ActionRegistry, action_registry: Central registry
"""

from .context import ActionContext, EventContext
from .executor import BaseActionExecutor
from .meta import (
    ActionExample,
    ActionMeta,
    ConditionalVisibility,
    ExecutionMode,
    OutputDefinition,
    ParamDefinition,
    ParamType,
    RetryPolicy,
    SelectOption,
    ValidationRules,
)
from .registry import (
    ActionRegistry,
    action_registry,
    register_action,
)
from .result import ActionResult, EventAction, EventResult, StepStatus

__all__ = [
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
    # Registry
    "ActionRegistry",
    "action_registry",
    "register_action",
]
