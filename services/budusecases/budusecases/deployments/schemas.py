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

"""Pydantic schemas for Deployment module."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DeploymentCreateSchema(BaseModel):
    """Schema for creating a new deployment."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., description="Deployment name")
    template_name: str = Field(..., description="Template to deploy")
    cluster_id: str = Field(..., description="Target cluster ID")
    project_id: str | None = Field(None, description="Project ID for API access scoping")
    components: dict[str, str] = Field(
        default_factory=dict, description="Component selections (slot -> component name)"
    )
    parameters: dict[str, Any] = Field(default_factory=dict, description="Deployment parameters")
    metadata_: dict[str, Any] = Field(default_factory=dict, alias="metadata", description="Additional metadata")


class ComponentDeploymentResponseSchema(BaseModel):
    """Schema for component deployment response."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str = Field(..., description="Component deployment ID")
    component_name: str = Field(..., description="Component slot name")
    component_type: str = Field(..., description="Component type")
    selected_component: str | None = Field(None, description="Selected component name")
    job_id: str | None = Field(None, description="BudCluster job ID")
    status: str = Field(..., description="Component deployment status")
    endpoint_url: str | None = Field(None, description="Deployed endpoint URL")
    error_message: str | None = Field(None, description="Error message if failed")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")


class DeploymentResponseSchema(BaseModel):
    """Schema for deployment response."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str = Field(..., description="Deployment ID")
    name: str = Field(..., description="Deployment name")
    template_id: str | None = Field(None, description="Template ID")
    template_name: str | None = Field(None, description="Template name")
    cluster_id: str = Field(..., description="Cluster ID")
    project_id: str | None = Field(None, description="Project ID for API access scoping")
    status: str = Field(..., description="Deployment status")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Deployment parameters")
    error_message: str | None = Field(None, description="Error message if failed")
    pipeline_execution_id: str | None = Field(None, description="BudPipeline execution ID")
    access_config: dict[str, Any] | None = Field(None, description="Access mode configuration")
    gateway_url: str | None = Field(None, description="Envoy Gateway endpoint URL")
    access_urls: dict[str, str] | None = Field(None, description="Resolved access URLs when running")
    components: list[ComponentDeploymentResponseSchema] = Field(
        default_factory=list, description="Component deployments"
    )
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")
    started_at: str | None = Field(None, description="Start timestamp")
    completed_at: str | None = Field(None, description="Completion timestamp")


class DeploymentListResponseSchema(BaseModel):
    """Schema for deployment list response."""

    items: list[DeploymentResponseSchema] = Field(..., description="Deployments")
    total: int = Field(..., description="Total count")
    page: int = Field(..., description="Current page")
    page_size: int = Field(..., description="Items per page")


class DeploymentStartResponseSchema(BaseModel):
    """Schema for deployment start response."""

    id: str = Field(..., description="Deployment ID")
    status: str = Field(..., description="New status")
    message: str = Field(..., description="Status message")
    pipeline_execution_id: str | None = Field(None, description="BudPipeline execution ID")


class DeploymentStopResponseSchema(BaseModel):
    """Schema for deployment stop response."""

    id: str = Field(..., description="Deployment ID")
    status: str = Field(..., description="New status")
    message: str = Field(..., description="Status message")


class StepProgressSchema(BaseModel):
    """Schema for a single pipeline step's progress."""

    id: str = Field("", description="Step progress ID")
    execution_id: str = Field("", description="Pipeline execution ID")
    step_id: str = Field("", description="Step ID")
    step_name: str = Field(..., description="Step name")
    status: str = Field(..., description="Step status")
    start_time: str | None = Field(None, description="Step start time")
    end_time: str | None = Field(None, description="Step end time")
    progress_percentage: str = Field("0", description="Step progress percentage")
    outputs: dict[str, Any] | None = Field(None, description="Step outputs")
    error_message: str | None = Field(None, description="Error message")
    sequence_number: int = Field(0, description="Step sequence number")
    awaiting_event: bool = Field(False, description="Whether step is awaiting external event")


class ProgressEventSchema(BaseModel):
    """Schema for a pipeline progress event."""

    id: str = Field("", description="Event ID")
    execution_id: str = Field("", description="Pipeline execution ID")
    event_type: str = Field(..., description="Event type")
    data: dict[str, Any] = Field(default_factory=dict, description="Event data")
    timestamp: str = Field(..., description="Event timestamp")


class AggregatedProgressSchema(BaseModel):
    """Schema for aggregated deployment progress."""

    overall_progress: str = Field("0", description="Overall progress percentage")
    eta_seconds: int | None = Field(None, description="Estimated seconds remaining")
    completed_steps: int = Field(0, description="Number of completed steps")
    total_steps: int = Field(0, description="Total number of steps")
    current_step: str | None = Field(None, description="Currently executing step name")


class DeploymentProgressResponseSchema(BaseModel):
    """Schema for deployment progress response (from BudPipeline)."""

    execution: dict[str, Any] = Field(..., description="Pipeline execution summary")
    steps: list[StepProgressSchema] = Field(default_factory=list, description="Step-level progress")
    recent_events: list[ProgressEventSchema] = Field(default_factory=list, description="Recent pipeline events")
    aggregated_progress: AggregatedProgressSchema = Field(..., description="Aggregated progress summary")
