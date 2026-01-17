# Pluggable Action Architecture Design

**Version:** 1.0
**Status:** Draft
**Author:** Principal Architect
**Date:** 2026-01-17

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Design Goals](#3-design-goals)
4. [Research & Industry Best Practices](#4-research--industry-best-practices)
5. [Proposed Architecture](#5-proposed-architecture)
6. [Action Definition Specification](#6-action-definition-specification)
7. [Directory Structure](#7-directory-structure)
8. [Implementation Details](#8-implementation-details)
9. [API Contract](#9-api-contract)
10. [Migration Plan](#10-migration-plan)
11. [Testing Strategy](#11-testing-strategy)
12. [Security Considerations](#12-security-considerations)
13. [Future Extensibility](#13-future-extensibility)

---

## 1. Executive Summary

This document proposes a **pluggable action architecture** for the budpipeline service that enables modular, extensible pipeline actions following industry best practices from Apache Airflow, Temporal, and Prefect.

### Key Principles

- **Single Source of Truth**: Action definitions live in budpipeline; frontend fetches metadata dynamically
- **Plugin Architecture**: Actions are self-contained modules with no direct dependency on core pipeline code
- **Self-Describing**: Each action declares its metadata, parameters, outputs, and execution behavior
- **Discoverable**: Actions are auto-discovered at runtime via Python entry points
- **Extensible**: New actions can be added without modifying core code

---

## 2. Problem Statement

### Current Issues

| Issue | Impact | Severity |
|-------|--------|----------|
| **Naming inconsistency**: Backend uses "handlers", frontend uses "actions" | Developer confusion, onboarding friction | Medium |
| **Monolithic files**: Multiple actions in single files (`builtin.py`, `model_handlers.py`) | Hard to maintain, test, and extend | High |
| **Duplicate definitions**: budadmin maintains separate action registry | Inconsistency, drift between frontend/backend | Critical |
| **Tight coupling**: Actions directly import from core modules | Difficult to add new actions without core changes | High |
| **No metadata API**: Frontend cannot discover available actions dynamically | Manual sync required between teams | High |

### Current Architecture (Problems Highlighted)

```
budpipeline/handlers/                  # "handlers" naming
├── builtin.py                         # 8 actions in one file
├── model_handlers.py                  # 3 actions in one file
├── cluster_handlers.py                # 1 action
├── notification_handlers.py           # 2 actions in one file
└── base.py                            # Tightly coupled base class

budadmin/.../actionRegistry.ts         # DUPLICATE definitions
└── 20+ actions with UI metadata       # Must be manually synced
```

---

## 3. Design Goals

### Must Have (P0)

1. **Rename handlers → actions** across the codebase
2. **One file per action** with self-contained definition
3. **Single source of truth** in budpipeline for action metadata
4. **API endpoint** for frontend to fetch action definitions
5. **Backward compatibility** with existing pipelines

### Should Have (P1)

6. **Plugin discovery** via Python entry points (stevedore pattern)
7. **Action validation** at registration time
8. **Hot reload** capability for development
9. **Action versioning** for breaking changes

### Nice to Have (P2)

10. **External action packages** installable via pip
11. **Action marketplace** for sharing across organizations
12. **Visual action builder** for no-code action creation

---

## 4. Research & Industry Best Practices

### 4.1 Apache Airflow Provider Pattern

Airflow uses a **provider package** pattern where:
- Each provider is a separate Python package
- Providers declare metadata via `get_provider_info()` function
- Discovery uses Python entry points (`apache_airflow_provider`)
- Schema validation via JSON Schema (`provider_info.schema.json`)

**Key Takeaway**: Declarative metadata + entry point discovery = extensibility

Reference: [Airflow Custom Providers](https://airflow.apache.org/docs/apache-airflow-providers/howto/create-custom-providers.html)

### 4.2 Stevedore Plugin Management

OpenStack's stevedore library provides:
- Plugin discovery via setuptools entry points
- Multiple manager patterns (Driver, Hook, Extension)
- Lazy loading for performance
- Validation at registration time

**Key Takeaway**: Use established patterns, don't reinvent plugin discovery

Reference: [Stevedore Documentation](https://docs.openstack.org/stevedore/latest/)

### 4.3 Temporal Activity Definitions

Temporal treats activities as:
- Self-contained units of work
- Declarative with retry policies, timeouts
- Registered by name (Activity Type)
- Idempotent by design

**Key Takeaway**: Activities should be idempotent and self-describing

Reference: [Temporal Activity Definition](https://docs.temporal.io/activity-definition)

### 4.4 Schema-First API Design

Modern APIs use schema-first approaches where:
- Schema is the contract between frontend and backend
- Auto-generation of client SDKs, documentation
- OpenAPI/JSON Schema as single source of truth

**Key Takeaway**: Define action schema once, generate everything from it

Reference: [Schema-First API Design](https://nordicapis.com/using-a-schema-first-design-as-your-single-source-of-truth/)

### 4.5 Prefect's Hybrid Model

Prefect separates orchestration from execution:
- Simple decorators for Python functions
- Dynamic task generation at runtime
- First-class subflows (composability)

**Key Takeaway**: Keep action definitions simple, enable composability

Reference: [Prefect Workflow Patterns](https://www.prefect.io/blog/workflow-design-patterns)

---

## 5. Proposed Architecture

### 5.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           budadmin (Frontend)                           │
│                                                                         │
│  ┌─────────────────┐    GET /actions     ┌─────────────────────────┐   │
│  │ Action Palette  │◄────────────────────│ Dynamic Action Registry │   │
│  │ (fetched)       │                     │ (cached from API)       │   │
│  └─────────────────┘                     └─────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         budpipeline (Backend)                           │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      Action Registry                             │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐             │   │
│  │  │ ActionMeta   │ │ ActionMeta   │ │ ActionMeta   │  ...        │   │
│  │  │ + executor   │ │ + executor   │ │ + executor   │             │   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘             │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                    ▲                                                    │
│                    │ Auto-discovery                                     │
│  ┌─────────────────┴───────────────────────────────────────────────┐   │
│  │                     Action Plugins                               │   │
│  │                                                                  │   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐│   │
│  │  │ model_add  │  │ conditional│  │ http_req   │  │ benchmark  ││   │
│  │  │ action.py  │  │ action.py  │  │ action.py  │  │ action.py  ││   │
│  │  └────────────┘  └────────────┘  └────────────┘  └────────────┘│   │
│  │                                                                  │   │
│  │        builtin/           model/          cluster/               │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Core Components

| Component | Responsibility |
|-----------|----------------|
| **ActionMeta** | Declarative metadata (name, params, outputs, UI hints) |
| **ActionExecutor** | Execution logic (sync or event-driven) |
| **ActionRegistry** | Discovers, validates, and manages actions |
| **ActionRouter** | Routes step execution to appropriate action |
| **ActionAPI** | REST endpoints for action discovery |

### 5.3 Separation of Concerns

```python
# Action = Metadata + Executor (combined in one module)
class ModelAddAction:
    # Metadata (declarative)
    meta = ActionMeta(
        type="model_add",
        name="Add Model",
        category="Model",
        ...
    )

    # Executor (imperative)
    class Executor(BaseActionExecutor):
        async def execute(self, context): ...
        async def on_event(self, context): ...
```

---

## 6. Action Definition Specification

### 6.1 ActionMeta Schema

```python
@dataclass
class ActionMeta:
    """Complete action metadata - single source of truth."""

    # === Identity ===
    type: str                          # Unique identifier (e.g., "model_add")
    version: str = "1.0.0"             # Semantic version

    # === Display ===
    name: str                          # Human-readable name
    description: str                   # What this action does
    category: str                      # Grouping (Model, Cluster, Control Flow, etc.)
    icon: str                          # Emoji or icon identifier
    color: str                         # Hex color for UI

    # === Parameters ===
    params: list[ParamDefinition]      # Input parameters

    # === Outputs ===
    outputs: list[OutputDefinition]    # Output fields produced

    # === Behavior ===
    execution_mode: ExecutionMode      # SYNC or EVENT_DRIVEN
    timeout_seconds: int | None        # Default timeout
    retry_policy: RetryPolicy | None   # Default retry behavior
    idempotent: bool = True            # Safe to retry?

    # === Dependencies ===
    required_services: list[str] = []  # e.g., ["budapp", "budcluster"]
    required_permissions: list[str] = []  # e.g., ["model:write"]

    # === Documentation ===
    examples: list[ActionExample] = [] # Usage examples
    docs_url: str | None = None        # Link to documentation


@dataclass
class ParamDefinition:
    """Parameter definition with validation and UI hints."""

    name: str                          # Parameter key
    label: str                         # Display label
    type: ParamType                    # string, number, boolean, select, etc.
    required: bool = False
    default: Any = None
    description: str | None = None
    placeholder: str | None = None

    # Type-specific
    options: list[SelectOption] | None = None  # For select/multiselect
    validation: ValidationRules | None = None  # min, max, pattern, etc.

    # UI hints
    group: str | None = None           # Parameter grouping
    show_when: ConditionalVisibility | None = None  # Conditional display

    # Reference types (fetched from API)
    ref_type: RefType | None = None    # model, cluster, project, endpoint


class ParamType(str, Enum):
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    SELECT = "select"
    MULTISELECT = "multiselect"
    JSON = "json"
    TEMPLATE = "template"              # Jinja2 template
    BRANCHES = "branches"              # Conditional branches
    MODEL_REF = "model_ref"            # Model selector
    CLUSTER_REF = "cluster_ref"        # Cluster selector
    PROJECT_REF = "project_ref"        # Project selector
    ENDPOINT_REF = "endpoint_ref"      # Endpoint selector


class ExecutionMode(str, Enum):
    SYNC = "sync"                      # Completes immediately
    EVENT_DRIVEN = "event_driven"      # Waits for external events
```

### 6.2 ActionExecutor Interface

```python
class BaseActionExecutor(ABC):
    """Base class for action execution logic."""

    @abstractmethod
    async def execute(self, context: ActionContext) -> ActionResult:
        """
        Execute the action.

        For SYNC actions: Complete and return result.
        For EVENT_DRIVEN actions: Initiate operation, return awaiting_event=True.
        """
        pass

    async def on_event(self, context: EventContext) -> EventResult:
        """
        Handle incoming event (EVENT_DRIVEN actions only).

        Called when an external event matches this action's correlation ID.
        """
        raise NotImplementedError("Event handling not implemented")

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        """Validate parameters beyond schema validation."""
        return []

    async def cleanup(self, context: ActionContext) -> None:
        """Cleanup resources on failure or cancellation."""
        pass
```

### 6.3 Complete Action Definition Example

```python
# budpipeline/actions/model/add.py
"""
Model Add Action

Adds a new model to the Bud AI Foundry repository from HuggingFace.
This is an event-driven action that waits for model download completion.
"""

from budpipeline.actions.base import (
    ActionMeta,
    BaseActionExecutor,
    ActionContext,
    ActionResult,
    EventContext,
    EventResult,
    ParamDefinition,
    OutputDefinition,
    ParamType,
    ExecutionMode,
    RetryPolicy,
    register_action,
)


# === Metadata Definition ===

META = ActionMeta(
    type="model_add",
    version="1.0.0",
    name="Add Model",
    description="Add a new model to the repository from HuggingFace",
    category="Model",
    icon="📥",
    color="#722ed1",

    execution_mode=ExecutionMode.EVENT_DRIVEN,
    timeout_seconds=1800,  # 30 minutes for large models
    idempotent=True,

    retry_policy=RetryPolicy(
        max_attempts=3,
        backoff_multiplier=2.0,
        initial_interval_seconds=5,
    ),

    required_services=["budapp"],
    required_permissions=["model:write"],

    params=[
        ParamDefinition(
            name="huggingface_id",
            label="HuggingFace Model ID",
            type=ParamType.STRING,
            required=True,
            placeholder="meta-llama/Llama-2-7b-hf",
            description="The HuggingFace model identifier (org/model)",
            validation=ValidationRules(
                pattern=r"^[\w-]+/[\w.-]+$",
                pattern_message="Must be in format 'organization/model-name'",
            ),
        ),
        ParamDefinition(
            name="model_name",
            label="Model Name",
            type=ParamType.STRING,
            required=False,
            placeholder="Auto-derived from HuggingFace ID",
            description="Display name (optional, derived from HuggingFace ID if not provided)",
        ),
        ParamDefinition(
            name="description",
            label="Description",
            type=ParamType.STRING,
            required=False,
            placeholder="A large language model for...",
        ),
        ParamDefinition(
            name="modality",
            label="Modality",
            type=ParamType.MULTISELECT,
            required=False,
            default=["text"],
            options=[
                SelectOption(label="Text", value="text"),
                SelectOption(label="Image", value="image"),
                SelectOption(label="Audio", value="audio"),
                SelectOption(label="Video", value="video"),
            ],
        ),
        ParamDefinition(
            name="max_wait_seconds",
            label="Max Wait Time (seconds)",
            type=ParamType.NUMBER,
            required=False,
            default=1800,
            description="Maximum time to wait for model download (default: 30 min)",
            validation=ValidationRules(min=60, max=7200),
            group="Advanced",
        ),
    ],

    outputs=[
        OutputDefinition(name="success", type="boolean", description="Whether operation succeeded"),
        OutputDefinition(name="model_id", type="string", description="UUID of the created model"),
        OutputDefinition(name="model_name", type="string", description="Name of the model"),
        OutputDefinition(name="workflow_id", type="string", description="BudApp workflow ID"),
        OutputDefinition(name="status", type="string", description="Final status"),
        OutputDefinition(name="message", type="string", description="Status message"),
    ],

    examples=[
        ActionExample(
            title="Add Llama 2 7B",
            params={"huggingface_id": "meta-llama/Llama-2-7b-hf"},
            description="Add the Llama 2 7B model from HuggingFace",
        ),
    ],

    docs_url="https://docs.budecosystem.com/actions/model-add",
)


# === Executor Implementation ===

class Executor(BaseActionExecutor):
    """Executes the model add operation."""

    async def execute(self, context: ActionContext) -> ActionResult:
        """Initiate model addition via budapp."""
        huggingface_id = context.params["huggingface_id"]
        model_name = context.params.get("model_name") or huggingface_id.split("/")[-1]

        # Call budapp to start model download workflow
        response = await context.invoke_service(
            app_id="budapp",
            method="/models/add",
            data={
                "huggingface_id": huggingface_id,
                "name": model_name,
                "description": context.params.get("description"),
                "modality": context.params.get("modality", ["text"]),
            },
        )

        if not response.get("success"):
            return ActionResult(
                success=False,
                error=response.get("message", "Failed to initiate model addition"),
            )

        workflow_id = response["workflow_id"]

        # Return awaiting event - execution continues when workflow completes
        return ActionResult(
            success=True,
            awaiting_event=True,
            external_workflow_id=workflow_id,
            outputs={
                "workflow_id": workflow_id,
                "model_name": model_name,
                "status": "downloading",
                "message": f"Model download initiated: {huggingface_id}",
            },
        )

    async def on_event(self, context: EventContext) -> EventResult:
        """Handle workflow completion event."""
        event_type = context.event_type
        event_data = context.event_data

        if event_type == "workflow_completed":
            status = event_data.get("status", "unknown")

            if status == "COMPLETED":
                return EventResult(
                    action=EventAction.COMPLETE,
                    status=StepStatus.COMPLETED,
                    outputs={
                        "success": True,
                        "model_id": event_data.get("model_id"),
                        "model_name": context.step_outputs.get("model_name"),
                        "workflow_id": context.external_workflow_id,
                        "status": "completed",
                        "message": "Model added successfully",
                    },
                )
            else:
                return EventResult(
                    action=EventAction.COMPLETE,
                    status=StepStatus.FAILED,
                    error=event_data.get("error", f"Workflow failed with status: {status}"),
                    outputs={
                        "success": False,
                        "status": "failed",
                        "message": event_data.get("error", "Model addition failed"),
                    },
                )

        # Unknown event type - ignore
        return EventResult(action=EventAction.IGNORE)


# === Registration ===

# This decorator registers the action with the global registry
@register_action(META)
class ModelAddAction:
    meta = META
    executor_class = Executor
```

---

## 7. Directory Structure

### 7.1 Proposed Structure

```
budpipeline/
├── actions/                           # All action definitions
│   ├── __init__.py                    # Exports ActionRegistry
│   ├── base/                          # Base classes and interfaces
│   │   ├── __init__.py
│   │   ├── meta.py                    # ActionMeta, ParamDefinition, etc.
│   │   ├── executor.py                # BaseActionExecutor
│   │   ├── context.py                 # ActionContext, EventContext
│   │   ├── result.py                  # ActionResult, EventResult
│   │   └── registry.py                # ActionRegistry singleton
│   │
│   ├── builtin/                       # Built-in control flow actions
│   │   ├── __init__.py
│   │   ├── log.py                     # Log action
│   │   ├── delay.py                   # Delay action
│   │   ├── conditional.py             # Conditional branching
│   │   ├── transform.py               # Data transformation
│   │   ├── aggregate.py               # Data aggregation
│   │   ├── set_output.py              # Set workflow outputs
│   │   └── fail.py                    # Intentional failure (testing)
│   │
│   ├── model/                         # Model-related actions
│   │   ├── __init__.py
│   │   ├── add.py                     # model_add
│   │   ├── delete.py                  # model_delete
│   │   └── benchmark.py               # model_benchmark
│   │
│   ├── cluster/                       # Cluster-related actions
│   │   ├── __init__.py
│   │   ├── health.py                  # cluster_health
│   │   ├── create.py                  # cluster_create (TODO)
│   │   └── delete.py                  # cluster_delete (TODO)
│   │
│   ├── deployment/                    # Deployment actions
│   │   ├── __init__.py
│   │   ├── create.py                  # deployment_create (TODO)
│   │   ├── delete.py                  # deployment_delete (TODO)
│   │   ├── autoscale.py               # deployment_autoscale (TODO)
│   │   └── ratelimit.py               # deployment_ratelimit (TODO)
│   │
│   ├── integration/                   # External integration actions
│   │   ├── __init__.py
│   │   ├── http_request.py            # HTTP requests
│   │   ├── notification.py            # Notifications
│   │   └── webhook.py                 # Webhooks
│   │
│   └── routes.py                      # Action API endpoints
│
├── pipeline/                          # Pipeline execution (unchanged)
│   ├── service.py                     # Uses ActionRegistry
│   └── ...
│
└── pyproject.toml                     # Entry points for plugin discovery
```

### 7.2 Entry Points Configuration

```toml
# pyproject.toml

[project.entry-points."budpipeline.actions"]
# Built-in actions
log = "budpipeline.actions.builtin.log:LogAction"
delay = "budpipeline.actions.builtin.delay:DelayAction"
conditional = "budpipeline.actions.builtin.conditional:ConditionalAction"
transform = "budpipeline.actions.builtin.transform:TransformAction"
aggregate = "budpipeline.actions.builtin.aggregate:AggregateAction"
set_output = "budpipeline.actions.builtin.set_output:SetOutputAction"
fail = "budpipeline.actions.builtin.fail:FailAction"

# Model actions
model_add = "budpipeline.actions.model.add:ModelAddAction"
model_delete = "budpipeline.actions.model.delete:ModelDeleteAction"
model_benchmark = "budpipeline.actions.model.benchmark:ModelBenchmarkAction"

# Cluster actions
cluster_health = "budpipeline.actions.cluster.health:ClusterHealthAction"

# Integration actions
http_request = "budpipeline.actions.integration.http_request:HttpRequestAction"
notification = "budpipeline.actions.integration.notification:NotificationAction"
webhook = "budpipeline.actions.integration.webhook:WebhookAction"
```

### 7.3 External Action Package Example

Third-party actions can be installed via pip:

```toml
# my-custom-actions/pyproject.toml

[project]
name = "budpipeline-actions-custom"
version = "1.0.0"

[project.entry-points."budpipeline.actions"]
custom_action = "my_custom_actions.custom:CustomAction"
another_action = "my_custom_actions.another:AnotherAction"
```

---

## 8. Implementation Details

### 8.1 ActionRegistry Implementation

```python
# budpipeline/actions/base/registry.py

import importlib.metadata
from typing import Type
import structlog

logger = structlog.get_logger()


class ActionRegistry:
    """
    Central registry for all pipeline actions.

    Actions are discovered via Python entry points at startup.
    This enables plugin-style extensibility without modifying core code.
    """

    _instance: "ActionRegistry | None" = None

    def __new__(cls) -> "ActionRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._actions = {}
            cls._instance._loaded = False
        return cls._instance

    def discover_actions(self) -> None:
        """Discover and load all actions from entry points."""
        if self._loaded:
            return

        entry_points = importlib.metadata.entry_points(group="budpipeline.actions")

        for ep in entry_points:
            try:
                action_class = ep.load()
                self._register_action_class(ep.name, action_class)
                logger.info("action_registered", action_type=ep.name)
            except Exception as e:
                logger.error("action_registration_failed",
                           action_type=ep.name, error=str(e))

        self._loaded = True
        logger.info("action_discovery_complete", count=len(self._actions))

    def _register_action_class(self, action_type: str, action_class: Type) -> None:
        """Register an action class."""
        if not hasattr(action_class, "meta"):
            raise ValueError(f"Action {action_type} missing 'meta' attribute")
        if not hasattr(action_class, "executor_class"):
            raise ValueError(f"Action {action_type} missing 'executor_class' attribute")

        meta: ActionMeta = action_class.meta

        # Validate metadata
        errors = self._validate_meta(meta)
        if errors:
            raise ValueError(f"Invalid action metadata: {errors}")

        self._actions[action_type] = {
            "meta": meta,
            "executor_class": action_class.executor_class,
            "executor_instance": None,  # Lazy instantiation
        }

    def register(self, action_class: Type) -> Type:
        """Decorator for manual action registration."""
        meta: ActionMeta = action_class.meta
        self._register_action_class(meta.type, action_class)
        return action_class

    def get_meta(self, action_type: str) -> ActionMeta | None:
        """Get action metadata by type."""
        action = self._actions.get(action_type)
        return action["meta"] if action else None

    def get_executor(self, action_type: str) -> BaseActionExecutor:
        """Get action executor instance (lazy singleton)."""
        action = self._actions.get(action_type)
        if not action:
            raise KeyError(f"Unknown action type: {action_type}")

        if action["executor_instance"] is None:
            action["executor_instance"] = action["executor_class"]()

        return action["executor_instance"]

    def has(self, action_type: str) -> bool:
        """Check if action type is registered."""
        return action_type in self._actions

    def list_actions(self) -> list[str]:
        """List all registered action types."""
        return list(self._actions.keys())

    def get_all_meta(self) -> list[ActionMeta]:
        """Get metadata for all registered actions."""
        return [a["meta"] for a in self._actions.values()]

    def get_by_category(self) -> dict[str, list[ActionMeta]]:
        """Get actions grouped by category."""
        by_category: dict[str, list[ActionMeta]] = {}
        for action in self._actions.values():
            meta = action["meta"]
            if meta.category not in by_category:
                by_category[meta.category] = []
            by_category[meta.category].append(meta)
        return by_category

    def _validate_meta(self, meta: ActionMeta) -> list[str]:
        """Validate action metadata."""
        errors = []
        if not meta.type:
            errors.append("type is required")
        if not meta.name:
            errors.append("name is required")
        if not meta.category:
            errors.append("category is required")
        # Add more validation as needed
        return errors


# Global registry instance
action_registry = ActionRegistry()


def register_action(meta: ActionMeta):
    """Decorator to register an action class."""
    def decorator(cls: Type) -> Type:
        cls.meta = meta
        return cls
    return decorator
```

### 8.2 Startup Integration

```python
# budpipeline/main.py

from contextlib import asynccontextmanager
from fastapi import FastAPI

from budpipeline.actions import action_registry
from budpipeline.actions.routes import router as actions_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: discover all actions
    action_registry.discover_actions()

    yield

    # Shutdown: cleanup


app = FastAPI(lifespan=lifespan)
app.include_router(actions_router, prefix="/actions", tags=["Actions"])
```

### 8.3 Pipeline Service Integration

```python
# budpipeline/pipeline/service.py

from budpipeline.actions import action_registry


class PipelineService:
    async def execute_step(self, step: StepDefinition, ...) -> StepResult:
        """Execute a pipeline step using the action registry."""

        action_type = step.action

        if not action_registry.has(action_type):
            raise ActionNotFoundError(f"Unknown action: {action_type}")

        # Get action metadata and executor
        meta = action_registry.get_meta(action_type)
        executor = action_registry.get_executor(action_type)

        # Create context
        context = ActionContext(
            step_id=step.id,
            execution_id=execution_id,
            params=resolved_params,
            workflow_params=workflow_params,
            step_outputs=step_outputs,
            timeout_seconds=meta.timeout_seconds,
        )

        # Execute with retry policy from metadata
        result = await self._execute_with_retry(
            executor=executor,
            context=context,
            retry_policy=meta.retry_policy,
        )

        return result
```

---

## 9. API Contract

### 9.1 Action Discovery Endpoints

```yaml
openapi: 3.1.0
info:
  title: BudPipeline Actions API
  version: 1.0.0

paths:
  /actions:
    get:
      summary: List all available actions
      description: Returns metadata for all registered actions, grouped by category
      responses:
        200:
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ActionListResponse'

  /actions/{action_type}:
    get:
      summary: Get action metadata
      parameters:
        - name: action_type
          in: path
          required: true
          schema:
            type: string
      responses:
        200:
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ActionMetaResponse'
        404:
          description: Action not found

  /actions/validate:
    post:
      summary: Validate action parameters
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ActionValidateRequest'
      responses:
        200:
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ActionValidateResponse'

components:
  schemas:
    ActionListResponse:
      type: object
      properties:
        categories:
          type: array
          items:
            $ref: '#/components/schemas/ActionCategory'
        actions:
          type: array
          items:
            $ref: '#/components/schemas/ActionMeta'

    ActionCategory:
      type: object
      properties:
        name:
          type: string
        icon:
          type: string
        actions:
          type: array
          items:
            $ref: '#/components/schemas/ActionMeta'

    ActionMeta:
      type: object
      required: [type, name, category, params]
      properties:
        type:
          type: string
          description: Unique action identifier
        version:
          type: string
        name:
          type: string
        description:
          type: string
        category:
          type: string
        icon:
          type: string
        color:
          type: string
        execution_mode:
          type: string
          enum: [sync, event_driven]
        params:
          type: array
          items:
            $ref: '#/components/schemas/ParamDefinition'
        outputs:
          type: array
          items:
            $ref: '#/components/schemas/OutputDefinition'

    ParamDefinition:
      type: object
      required: [name, label, type]
      properties:
        name:
          type: string
        label:
          type: string
        type:
          type: string
          enum: [string, number, boolean, select, multiselect, json, template, branches, model_ref, cluster_ref, project_ref, endpoint_ref]
        required:
          type: boolean
        default:
          type: any
        description:
          type: string
        placeholder:
          type: string
        options:
          type: array
          items:
            $ref: '#/components/schemas/SelectOption'
        validation:
          $ref: '#/components/schemas/ValidationRules'
        group:
          type: string
        show_when:
          $ref: '#/components/schemas/ConditionalVisibility'
```

### 9.2 FastAPI Routes Implementation

```python
# budpipeline/actions/routes.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from budpipeline.actions import action_registry

router = APIRouter()


class ActionListResponse(BaseModel):
    categories: list[dict]
    actions: list[dict]


@router.get("", response_model=ActionListResponse)
async def list_actions():
    """List all available actions grouped by category."""
    action_registry.discover_actions()  # Ensure loaded

    by_category = action_registry.get_by_category()

    categories = []
    for category_name, actions in by_category.items():
        categories.append({
            "name": category_name,
            "icon": _get_category_icon(category_name),
            "actions": [_serialize_meta(a) for a in actions],
        })

    all_actions = [_serialize_meta(m) for m in action_registry.get_all_meta()]

    return ActionListResponse(
        categories=categories,
        actions=all_actions,
    )


@router.get("/{action_type}")
async def get_action(action_type: str):
    """Get metadata for a specific action."""
    meta = action_registry.get_meta(action_type)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Action not found: {action_type}")

    return _serialize_meta(meta)


class ValidateRequest(BaseModel):
    action_type: str
    params: dict


@router.post("/validate")
async def validate_action_params(request: ValidateRequest):
    """Validate action parameters."""
    meta = action_registry.get_meta(request.action_type)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Action not found: {request.action_type}")

    errors = _validate_params(meta, request.params)

    return {
        "valid": len(errors) == 0,
        "errors": errors,
    }


def _serialize_meta(meta: ActionMeta) -> dict:
    """Serialize ActionMeta to JSON-compatible dict."""
    return {
        "type": meta.type,
        "version": meta.version,
        "name": meta.name,
        "description": meta.description,
        "category": meta.category,
        "icon": meta.icon,
        "color": meta.color,
        "execution_mode": meta.execution_mode.value,
        "timeout_seconds": meta.timeout_seconds,
        "idempotent": meta.idempotent,
        "params": [_serialize_param(p) for p in meta.params],
        "outputs": [_serialize_output(o) for o in meta.outputs],
        "required_services": meta.required_services,
        "examples": [_serialize_example(e) for e in meta.examples],
        "docs_url": meta.docs_url,
    }


def _get_category_icon(category: str) -> str:
    """Get icon for action category."""
    icons = {
        "Model": "🤖",
        "Cluster": "🖥️",
        "Deployment": "🚀",
        "Control Flow": "🔀",
        "Integration": "🔗",
        "Data": "📦",
    }
    return icons.get(category, "⚙️")
```

---

## 10. Migration Plan

### Phase 1: Foundation (Week 1)

1. **Create new directory structure**
   - `actions/base/` with new interfaces
   - Keep existing `handlers/` working

2. **Implement ActionRegistry**
   - Entry point discovery
   - Validation logic

3. **Create base classes**
   - ActionMeta dataclass
   - BaseActionExecutor ABC

### Phase 2: Action Migration (Week 2)

4. **Migrate built-in actions** (one file each)
   - `log.py`, `delay.py`, `conditional.py`, etc.
   - Maintain backward compatibility

5. **Migrate model actions**
   - `model/add.py`, `model/delete.py`, `model/benchmark.py`

6. **Migrate cluster & integration actions**
   - All remaining actions

### Phase 3: API & Frontend (Week 3)

7. **Implement Actions API**
   - `GET /actions` - list all
   - `GET /actions/{type}` - get one
   - `POST /actions/validate` - validate params

8. **Update budadmin**
   - Remove static `actionRegistry.ts`
   - Fetch from API with caching
   - Use OpenAPI types

### Phase 4: Cleanup (Week 4)

9. **Remove old code**
   - Delete `handlers/` directory
   - Update all imports

10. **Documentation**
    - Action development guide
    - Migration guide for custom actions

### Backward Compatibility Strategy

```python
# During migration: support both "handler" and "action" terminology
class DeprecatedHandlerRegistry:
    """Compatibility layer for old handler-based code."""

    def __init__(self, action_registry: ActionRegistry):
        self._action_registry = action_registry

    def get(self, handler_type: str):
        """Get handler by type (deprecated, use action_registry)."""
        import warnings
        warnings.warn(
            "HandlerRegistry.get() is deprecated, use action_registry.get_executor()",
            DeprecationWarning,
        )
        return self._action_registry.get_executor(handler_type)

    def has(self, handler_type: str) -> bool:
        return self._action_registry.has(handler_type)


# Expose as global_registry for compatibility
global_registry = DeprecatedHandlerRegistry(action_registry)
```

---

## 11. Testing Strategy

### 11.1 Unit Tests

```python
# tests/actions/test_registry.py

import pytest
from budpipeline.actions import action_registry, ActionMeta, ParamDefinition


class TestActionRegistry:
    def test_discover_actions(self):
        action_registry.discover_actions()
        assert action_registry.has("log")
        assert action_registry.has("model_add")

    def test_get_meta(self):
        meta = action_registry.get_meta("log")
        assert meta is not None
        assert meta.type == "log"
        assert meta.category == "Control Flow"

    def test_get_executor(self):
        executor = action_registry.get_executor("log")
        assert executor is not None
        assert hasattr(executor, "execute")

    def test_unknown_action_raises(self):
        with pytest.raises(KeyError):
            action_registry.get_executor("nonexistent")


class TestActionExecution:
    @pytest.mark.asyncio
    async def test_log_action(self):
        executor = action_registry.get_executor("log")
        context = ActionContext(
            step_id="test-step",
            execution_id="test-exec",
            params={"message": "Test log", "level": "info"},
            workflow_params={},
            step_outputs={},
        )

        result = await executor.execute(context)

        assert result.success
        assert result.outputs["logged"] is True
```

### 11.2 Integration Tests

```python
# tests/actions/test_api.py

import pytest
from httpx import AsyncClient


class TestActionsAPI:
    @pytest.mark.asyncio
    async def test_list_actions(self, client: AsyncClient):
        response = await client.get("/actions")
        assert response.status_code == 200

        data = response.json()
        assert "categories" in data
        assert "actions" in data
        assert len(data["actions"]) > 0

    @pytest.mark.asyncio
    async def test_get_action(self, client: AsyncClient):
        response = await client.get("/actions/model_add")
        assert response.status_code == 200

        data = response.json()
        assert data["type"] == "model_add"
        assert data["execution_mode"] == "event_driven"
        assert len(data["params"]) > 0

    @pytest.mark.asyncio
    async def test_validate_params_valid(self, client: AsyncClient):
        response = await client.post("/actions/validate", json={
            "action_type": "model_add",
            "params": {"huggingface_id": "meta-llama/Llama-2-7b"},
        })
        assert response.status_code == 200
        assert response.json()["valid"] is True

    @pytest.mark.asyncio
    async def test_validate_params_invalid(self, client: AsyncClient):
        response = await client.post("/actions/validate", json={
            "action_type": "model_add",
            "params": {},  # Missing required param
        })
        assert response.status_code == 200
        assert response.json()["valid"] is False
```

---

## 12. Security Considerations

### 12.1 Action Permissions

```python
@dataclass
class ActionMeta:
    ...
    required_permissions: list[str] = []  # e.g., ["model:write", "cluster:admin"]


# Enforced at execution time
async def execute_step(self, step: StepDefinition, user: User, ...):
    meta = action_registry.get_meta(step.action)

    # Check permissions
    for permission in meta.required_permissions:
        if not user.has_permission(permission):
            raise PermissionDeniedError(
                f"Action {step.action} requires permission: {permission}"
            )
```

### 12.2 Plugin Sandboxing

For external/untrusted actions:

```python
class ActionRegistry:
    def register_external(self, action_class: Type, trusted: bool = False) -> None:
        """Register an external action with optional sandboxing."""
        if not trusted:
            # Wrap executor in sandbox
            original_executor = action_class.executor_class
            action_class.executor_class = SandboxedExecutor(original_executor)
```

### 12.3 Input Validation

All action parameters are validated against their schema before execution:

```python
async def execute_step(self, ...):
    meta = action_registry.get_meta(step.action)

    # Schema validation
    errors = validate_params_against_schema(meta.params, resolved_params)
    if errors:
        raise ValidationError(errors)

    # Custom validation
    executor = action_registry.get_executor(step.action)
    errors = executor.validate_params(resolved_params)
    if errors:
        raise ValidationError(errors)
```

---

## 13. Future Extensibility

### 13.1 Action Marketplace

```yaml
# .budpipeline/marketplace.yaml
sources:
  - name: official
    url: https://marketplace.budecosystem.com/actions
  - name: community
    url: https://github.com/budecosystem/action-registry

installed:
  - budpipeline-actions-slack@1.2.0
  - budpipeline-actions-aws@2.0.1
```

### 13.2 Visual Action Builder

Low-code action creation via UI:

```json
{
  "type": "custom_notification",
  "name": "Custom Notification",
  "category": "Integration",
  "template": "http_request",
  "defaults": {
    "method": "POST",
    "url": "https://hooks.slack.com/...",
    "headers": {"Content-Type": "application/json"}
  },
  "exposed_params": ["message", "channel"]
}
```

### 13.3 Action Composition

Actions that combine other actions:

```python
class CompositeAction(BaseActionExecutor):
    """Action that runs multiple sub-actions."""

    sub_actions = ["validate_input", "transform_data", "send_notification"]

    async def execute(self, context: ActionContext) -> ActionResult:
        results = {}
        for action_type in self.sub_actions:
            executor = action_registry.get_executor(action_type)
            result = await executor.execute(context)
            if not result.success:
                return result
            results[action_type] = result.outputs

        return ActionResult(success=True, outputs=results)
```

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| **Action** | A discrete unit of work in a pipeline (formerly "handler") |
| **ActionMeta** | Declarative metadata describing an action |
| **ActionExecutor** | The execution logic for an action |
| **ActionRegistry** | Central registry managing all actions |
| **Entry Point** | Python packaging mechanism for plugin discovery |
| **Event-Driven Action** | Action that waits for external events to complete |
| **Sync Action** | Action that completes immediately |

## Appendix B: References

- [Apache Airflow Custom Providers](https://airflow.apache.org/docs/apache-airflow-providers/howto/create-custom-providers.html)
- [Stevedore Documentation](https://docs.openstack.org/stevedore/latest/)
- [Temporal Activity Definition](https://docs.temporal.io/activity-definition)
- [Python Packaging - Creating and Discovering Plugins](https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/)
- [Schema-First API Design](https://nordicapis.com/using-a-schema-first-design-as-your-single-source-of-truth/)
- [Prefect Workflow Patterns](https://www.prefect.io/blog/workflow-design-patterns)
- [FastAPI Best Architecture](https://github.com/fastapi-practices/fastapi_best_architecture)

---

## Appendix C: Decision Log

| Decision | Rationale | Alternatives Considered |
|----------|-----------|------------------------|
| Use Python entry points for discovery | Standard mechanism, works with pip install | Custom config file, decorator scanning |
| One file per action | Clear ownership, easy to test | Group by similarity, single registry file |
| ActionMeta as dataclass | Type safety, IDE support | Dict, Pydantic model |
| Singleton registry | Simple, thread-safe | Dependency injection, per-request |
| Keep executor as instance method | Access to self for configuration | Static methods, functions |

---

**Document Status**: Ready for Review

**Next Steps**:
1. Review with engineering team
2. Create implementation tickets
3. Begin Phase 1 implementation
