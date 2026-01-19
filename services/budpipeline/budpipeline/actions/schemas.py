"""Pydantic schemas for Actions API responses.

These schemas define the API contract for exposing action metadata
to frontend clients and external consumers.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SelectOptionResponse(BaseModel):
    """A selectable option for dropdown/multiselect parameters."""

    value: str
    label: str


class ValidationRulesResponse(BaseModel):
    """Validation rules for a parameter."""

    min: float | None = None
    max: float | None = None
    min_length: int | None = Field(None, alias="minLength")
    max_length: int | None = Field(None, alias="maxLength")
    pattern: str | None = None
    pattern_message: str | None = Field(None, alias="patternMessage")

    model_config = {"populate_by_name": True}


class ConditionalVisibilityResponse(BaseModel):
    """Conditional visibility for a parameter."""

    param: str
    equals: Any | None = None
    not_equals: Any | None = Field(None, alias="notEquals")

    model_config = {"populate_by_name": True}


class ParamDefinitionResponse(BaseModel):
    """Parameter definition for an action."""

    name: str
    label: str
    type: str
    description: str | None = None
    required: bool = False
    default: Any | None = None
    placeholder: str | None = None
    options: list[SelectOptionResponse] | None = None
    validation: ValidationRulesResponse | None = None
    visible_when: ConditionalVisibilityResponse | None = Field(None, alias="visibleWhen")

    model_config = {"populate_by_name": True}


class OutputDefinitionResponse(BaseModel):
    """Output definition for an action."""

    name: str
    type: str
    description: str | None = None


class RetryPolicyResponse(BaseModel):
    """Retry policy for an action."""

    max_attempts: int = Field(alias="maxAttempts")
    backoff_multiplier: float = Field(alias="backoffMultiplier")
    initial_interval_seconds: float = Field(alias="initialIntervalSeconds")

    model_config = {"populate_by_name": True}


class ActionExampleResponse(BaseModel):
    """Example usage for an action."""

    title: str
    params: dict[str, Any]
    description: str | None = None


class ActionMetaResponse(BaseModel):
    """Full action metadata response."""

    type: str
    version: str
    name: str
    description: str
    category: str
    icon: str | None = None
    color: str | None = None
    params: list[ParamDefinitionResponse] = []
    outputs: list[OutputDefinitionResponse] = []
    execution_mode: str = Field(alias="executionMode")
    timeout_seconds: int | None = Field(None, alias="timeoutSeconds")
    retry_policy: RetryPolicyResponse | None = Field(None, alias="retryPolicy")
    idempotent: bool = False
    required_services: list[str] = Field(default_factory=list, alias="requiredServices")
    required_permissions: list[str] = Field(default_factory=list, alias="requiredPermissions")
    examples: list[ActionExampleResponse] = []
    docs_url: str | None = Field(None, alias="docsUrl")

    model_config = {"populate_by_name": True}


class ActionCategoryResponse(BaseModel):
    """Action category with its actions."""

    name: str
    icon: str
    actions: list[ActionMetaResponse]


class ActionListResponse(BaseModel):
    """Response for listing all actions."""

    actions: list[ActionMetaResponse]
    categories: list[ActionCategoryResponse]
    total: int


class ValidateRequest(BaseModel):
    """Request to validate action parameters."""

    action_type: str = Field(alias="actionType")
    params: dict[str, Any]

    model_config = {"populate_by_name": True}


class ValidateResponse(BaseModel):
    """Response for parameter validation."""

    valid: bool
    errors: list[str] = []
