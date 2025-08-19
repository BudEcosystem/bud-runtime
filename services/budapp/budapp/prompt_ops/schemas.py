#  -----------------------------------------------------------------------------
#  Copyright (c) 2024 Bud Ecosystem Inc.
#  #
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#  #
#      http://www.apache.org/licenses/LICENSE-2.0
#  #
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#  -----------------------------------------------------------------------------

"""Pydantic schemas for the prompt ops module."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import UUID4, BaseModel, Field, field_validator, model_validator

from budapp.commons.constants import (
    PromptStatusEnum,
    PromptTypeEnum,
    PromptVersionStatusEnum,
    RateLimitTypeEnum,
)
from budapp.commons.schemas import Tag


class PromptSchemaConfig(BaseModel):
    """Schema for prompt configuration stored in prompt_schema field."""

    messages: Optional[List[Dict[str, Any]]] = Field(default=None, description="Prompt messages")
    system_prompt: Optional[str] = Field(default=None, description="System prompt")
    model_parameters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Model parameters like temperature, max_tokens, etc."
    )
    input_schema: Optional[Dict[str, Any]] = Field(default=None, description="Input validation schema")
    output_schema: Optional[Dict[str, Any]] = Field(default=None, description="Output validation schema")
    validation_rules: Optional[Dict[str, Any]] = Field(default=None, description="Validation rules")


class CreatePromptWorkflowRequest(BaseModel):
    """Create prompt workflow request schema."""

    step_number: int = Field(..., gt=0)
    trigger_workflow: bool = False

    workflow_id: UUID4 | None = None
    workflow_total_steps: int | None = None

    project_id: UUID4 | None = None
    endpoint_id: UUID4 | None = None
    name: str | None = None
    description: str | None = None
    tags: list[Tag] | None = None
    prompt_type: PromptTypeEnum | None = None
    auto_scale: bool | None = None
    caching: bool | None = None
    concurrency: list[int] | None = None  # [min, max]
    rate_limit_type: RateLimitTypeEnum | None = None
    rate_limit_value: int | None = None
    prompt_schema: PromptSchemaConfig | None = None

    @model_validator(mode="after")
    def validate_fields(self):
        # Validate workflow_total_steps when workflow_id is not provided
        if self.workflow_id is None and self.workflow_total_steps is None:
            raise ValueError("workflow_total_steps is required when workflow_id is not provided")

        # Validate rate_limit_value when type is CUSTOM
        if self.rate_limit_type == RateLimitTypeEnum.CUSTOM and self.rate_limit_value is None:
            raise ValueError("rate_limit_value is required when rate_limit_type is CUSTOM")

        # Validate concurrency array length and values
        if self.concurrency is not None:
            if len(self.concurrency) != 2:
                raise ValueError("Concurrency must be a list of 2 integers [min, max]")
            if self.concurrency[0] >= self.concurrency[1]:
                raise ValueError("Concurrency min must be less than max")

        return self


class CreatePromptWorkflowSteps(BaseModel):
    """Create prompt workflow steps request schema."""

    project_id: UUID4 | None = None
    endpoint_id: UUID4 | None = None
    model_id: UUID4 | None = None
    cluster_id: UUID4 | None = None
    name: str | None = None
    description: str | None = None
    tags: list[Tag] | None = None
    prompt_type: PromptTypeEnum | None = None
    auto_scale: bool | None = None
    caching: bool | None = None
    concurrency: list[int] | None = None  # [min, max]
    rate_limit_type: RateLimitTypeEnum | None = None
    rate_limit_value: int | None = None
    prompt_schema: PromptSchemaConfig | None = None
