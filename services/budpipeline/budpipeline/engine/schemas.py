"""Pydantic schemas for DAG/Workflow definitions."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class OnFailureAction(str, Enum):
    """Action to take when a step fails."""

    FAIL = "fail"
    CONTINUE = "continue"
    RETRY = "retry"


class ParameterType(str, Enum):
    """Supported parameter types."""

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"
    # Reference types
    CLUSTER_REF = "cluster_ref"
    MODEL_REF = "model_ref"
    ENDPOINT_REF = "endpoint_ref"
    PROJECT_REF = "project_ref"
    CREDENTIAL_REF = "credential_ref"


class RetryConfig(BaseModel):
    """Retry configuration for a step."""

    max_attempts: int = Field(default=3, ge=1, le=10)
    backoff_seconds: int = Field(default=60, ge=1)
    backoff_multiplier: float = Field(default=2.0, ge=1.0)
    max_backoff_seconds: int = Field(default=3600, ge=1)

    model_config = {"extra": "ignore"}


class WorkflowParameter(BaseModel):
    """Definition of a workflow parameter."""

    name: str = Field(..., min_length=1, max_length=100)
    type: str = Field(default="string")
    description: str | None = None
    required: bool = True
    default: Any = None

    model_config = {"extra": "ignore"}

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate parameter name follows conventions."""
        if not v[0].isalpha() and v[0] != "_":
            raise ValueError("Parameter name must start with a letter or underscore")
        return v


class WorkflowStep(BaseModel):
    """Definition of a workflow step."""

    id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    action: str = Field(..., min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    condition: str | None = None
    on_failure: OnFailureAction = OnFailureAction.FAIL
    timeout_seconds: int | None = None
    retry: RetryConfig | None = None

    model_config = {"extra": "ignore"}

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        """Validate step ID follows conventions."""
        if not v[0].isalnum():
            raise ValueError("Step ID must start with alphanumeric character")
        return v

    @field_validator("on_failure", mode="before")
    @classmethod
    def parse_on_failure(cls, v: Any) -> OnFailureAction:
        """Parse on_failure from string."""
        if isinstance(v, str):
            return OnFailureAction(v.lower())
        return v


class WorkflowSettings(BaseModel):
    """Global settings for a workflow."""

    timeout_seconds: int = Field(default=7200, ge=1)
    fail_fast: bool = True
    max_parallel_steps: int = Field(default=10, ge=1, le=100)
    retry_policy: RetryConfig | None = None

    model_config = {"extra": "ignore"}


class WorkflowDAG(BaseModel):
    """Complete workflow DAG definition."""

    name: str = Field(..., min_length=1, max_length=255)
    version: str = Field(default="1.0")
    description: str | None = None
    parameters: list[WorkflowParameter] = Field(default_factory=list)
    settings: WorkflowSettings = Field(default_factory=WorkflowSettings)
    steps: list[WorkflowStep] = Field(..., min_length=1)
    outputs: dict[str, str] = Field(default_factory=dict)

    model_config = {"extra": "ignore"}

    # Private cache for step lookup
    _step_index: dict[str, WorkflowStep] | None = None

    def model_post_init(self, __context: Any) -> None:
        """Build step index after initialization."""
        self._step_index = {step.id: step for step in self.steps}

    def get_step(self, step_id: str) -> WorkflowStep | None:
        """Get step by ID."""
        if self._step_index is None:
            self._step_index = {step.id: step for step in self.steps}
        return self._step_index.get(step_id)

    def has_step(self, step_id: str) -> bool:
        """Check if step exists."""
        return self.get_step(step_id) is not None

    def get_root_steps(self) -> list[WorkflowStep]:
        """Get steps with no dependencies."""
        return [step for step in self.steps if not step.depends_on]

    def get_leaf_steps(self) -> list[WorkflowStep]:
        """Get steps that no other step depends on."""
        all_deps: set[str] = set()
        for step in self.steps:
            all_deps.update(step.depends_on)

        return [step for step in self.steps if step.id not in all_deps]

    def get_dependents(self, step_id: str) -> list[WorkflowStep]:
        """Get all steps that depend on the given step."""
        return [step for step in self.steps if step_id in step.depends_on]

    def get_required_parameters(self) -> list[WorkflowParameter]:
        """Get all required parameters."""
        return [param for param in self.parameters if param.required]

    def get_parameter(self, name: str) -> WorkflowParameter | None:
        """Get parameter by name."""
        for param in self.parameters:
            if param.name == name:
                return param
        return None
