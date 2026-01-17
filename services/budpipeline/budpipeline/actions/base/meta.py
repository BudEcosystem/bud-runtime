"""Action metadata definitions.

This module defines the declarative metadata structures for pipeline actions.
ActionMeta is the single source of truth for action configuration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ParamType(str, Enum):
    """Parameter types supported by actions."""

    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    SELECT = "select"
    MULTISELECT = "multiselect"
    JSON = "json"
    TEMPLATE = "template"  # Jinja2 template string
    BRANCHES = "branches"  # Conditional branches
    MODEL_REF = "model_ref"  # Model reference (fetched from API)
    CLUSTER_REF = "cluster_ref"  # Cluster reference
    PROJECT_REF = "project_ref"  # Project reference
    ENDPOINT_REF = "endpoint_ref"  # Endpoint reference


class ExecutionMode(str, Enum):
    """Execution modes for actions."""

    SYNC = "sync"  # Completes immediately
    EVENT_DRIVEN = "event_driven"  # Waits for external events


@dataclass
class SelectOption:
    """Option for select/multiselect parameters."""

    label: str
    value: str


@dataclass
class ValidationRules:
    """Validation rules for parameters."""

    min: float | None = None
    max: float | None = None
    min_length: int | None = None
    max_length: int | None = None
    pattern: str | None = None
    pattern_message: str | None = None


@dataclass
class ConditionalVisibility:
    """Conditional visibility rules for parameters."""

    param: str
    equals: Any | None = None
    not_equals: Any | None = None


@dataclass
class ParamDefinition:
    """Parameter definition with validation and UI hints."""

    name: str
    label: str
    type: ParamType
    required: bool = False
    default: Any = None
    description: str | None = None
    placeholder: str | None = None

    # Type-specific
    options: list[SelectOption] | None = None
    validation: ValidationRules | None = None

    # UI hints
    group: str | None = None
    show_when: ConditionalVisibility | None = None


@dataclass
class OutputDefinition:
    """Output field definition."""

    name: str
    type: str  # string, number, boolean, object, array
    description: str | None = None


@dataclass
class RetryPolicy:
    """Retry policy for action execution."""

    max_attempts: int = 3
    backoff_multiplier: float = 2.0
    initial_interval_seconds: float = 1.0
    max_interval_seconds: float = 60.0


@dataclass
class ActionExample:
    """Usage example for an action."""

    title: str
    params: dict[str, Any]
    description: str | None = None


@dataclass
class ActionMeta:
    """Complete action metadata - single source of truth.

    This dataclass defines all the metadata for a pipeline action,
    including identity, display properties, parameters, outputs,
    execution behavior, and documentation.
    """

    # === Identity ===
    type: str  # Unique identifier (e.g., "model_add")
    name: str  # Human-readable name
    category: str  # Grouping (Model, Cluster, Control Flow, etc.)
    description: str  # What this action does

    # === Version ===
    version: str = "1.0.0"

    # === Display ===
    icon: str = ""  # Emoji or icon identifier
    color: str = "#8c8c8c"  # Hex color for UI

    # === Parameters ===
    params: list[ParamDefinition] = field(default_factory=list)

    # === Outputs ===
    outputs: list[OutputDefinition] = field(default_factory=list)

    # === Behavior ===
    execution_mode: ExecutionMode = ExecutionMode.SYNC
    timeout_seconds: int | None = None
    retry_policy: RetryPolicy | None = None
    idempotent: bool = True

    # === Dependencies ===
    required_services: list[str] = field(default_factory=list)
    required_permissions: list[str] = field(default_factory=list)

    # === Documentation ===
    examples: list[ActionExample] = field(default_factory=list)
    docs_url: str | None = None

    def validate(self) -> list[str]:
        """Validate the action metadata.

        Returns:
            List of validation error messages. Empty if valid.
        """
        errors = []

        if not self.type:
            errors.append("type is required")
        if not self.name:
            errors.append("name is required")
        if not self.category:
            errors.append("category is required")
        if not self.description:
            errors.append("description is required")

        # Validate type format (lowercase, alphanumeric with underscores)
        if self.type and not self.type.replace("_", "").isalnum():
            errors.append("type must be alphanumeric with underscores only")

        # Validate params
        param_names = set()
        for i, param in enumerate(self.params):
            if not param.name:
                errors.append(f"param[{i}].name is required")
            elif param.name in param_names:
                errors.append(f"duplicate param name: {param.name}")
            else:
                param_names.add(param.name)

            if not param.label:
                errors.append(f"param[{i}].label is required")

            # Validate select options
            if param.type in (ParamType.SELECT, ParamType.MULTISELECT):
                if not param.options:
                    errors.append(f"param '{param.name}' requires options for {param.type.value}")

        # Validate outputs
        output_names = set()
        for i, output in enumerate(self.outputs):
            if not output.name:
                errors.append(f"output[{i}].name is required")
            elif output.name in output_names:
                errors.append(f"duplicate output name: {output.name}")
            else:
                output_names.add(output.name)

        return errors

    def get_required_params(self) -> list[ParamDefinition]:
        """Get list of required parameters."""
        return [p for p in self.params if p.required]

    def get_optional_params(self) -> list[ParamDefinition]:
        """Get list of optional parameters."""
        return [p for p in self.params if not p.required]

    def get_param(self, name: str) -> ParamDefinition | None:
        """Get a parameter definition by name."""
        for param in self.params:
            if param.name == name:
                return param
        return None

    def get_output(self, name: str) -> OutputDefinition | None:
        """Get an output definition by name."""
        for output in self.outputs:
            if output.name == name:
                return output
        return None
