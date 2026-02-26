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

"""Pydantic schemas for Job API in BudCluster.

This module defines the request/response schemas for the unified job
tracking REST API, providing validation and serialization for job data.
"""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .enums import JobPriority, JobSource, JobStatus, JobType


class JobBase(BaseModel):
    """Base schema with common job fields."""

    name: str = Field(..., min_length=1, max_length=255, description="Job name")
    job_type: JobType = Field(..., description="Type of job")
    source: JobSource = Field(..., description="Source service that created the job")
    cluster_id: UUID = Field(..., description="Cluster where the job runs")
    source_id: Optional[UUID] = Field(None, description="ID in the source service")
    namespace: Optional[str] = Field(None, max_length=255, description="Kubernetes namespace")
    endpoint_id: Optional[UUID] = Field(None, description="Optional endpoint link")
    priority: int = Field(default=JobPriority.NORMAL.value, ge=0, description="Job priority")
    config: Optional[dict[str, Any]] = Field(None, description="Job configuration")
    metadata_: Optional[dict[str, Any]] = Field(None, alias="metadata_", description="Additional metadata")
    timeout_seconds: Optional[int] = Field(None, gt=0, description="Job timeout in seconds")

    @field_validator("name", mode="before")
    @classmethod
    def validate_name_not_whitespace(cls, v: str) -> str:
        """Validate that name is not just whitespace."""
        if isinstance(v, str) and not v.strip():
            raise ValueError("name cannot be empty or whitespace only")
        return v


class JobCreate(JobBase):
    """Schema for creating a new job."""

    pass


class JobUpdate(BaseModel):
    """Schema for updating an existing job.

    All fields are optional to allow partial updates.
    """

    status: Optional[JobStatus] = Field(None, description="New job status")
    namespace: Optional[str] = Field(None, max_length=255, description="Kubernetes namespace")
    error_message: Optional[str] = Field(None, description="Error details if failed")
    retry_count: Optional[int] = Field(None, ge=0, description="Number of retry attempts")
    config: Optional[dict[str, Any]] = Field(None, description="Job configuration")
    metadata_: Optional[dict[str, Any]] = Field(None, alias="metadata_", description="Additional metadata")
    started_at: Optional[datetime] = Field(None, description="Job start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Job completion timestamp")


class JobResponse(BaseModel):
    """Schema for job API responses.

    Used for returning job data from API endpoints.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Unique job identifier")
    name: str = Field(..., description="Job name")
    job_type: JobType = Field(..., description="Type of job")
    status: JobStatus = Field(..., description="Current job status")
    source: JobSource = Field(..., description="Source service that created the job")
    source_id: Optional[UUID] = Field(None, description="ID in the source service")
    cluster_id: UUID = Field(..., description="Cluster where the job runs")
    namespace: Optional[str] = Field(None, description="Kubernetes namespace")
    endpoint_id: Optional[UUID] = Field(None, description="Optional endpoint link")
    priority: int = Field(..., description="Job priority")
    config: Optional[dict[str, Any]] = Field(None, description="Job configuration")
    metadata_: Optional[dict[str, Any]] = Field(None, alias="metadata_", description="Additional metadata")
    error_message: Optional[str] = Field(None, description="Error details if failed")
    retry_count: int = Field(..., description="Number of retry attempts")
    timeout_seconds: Optional[int] = Field(None, description="Job timeout in seconds")
    started_at: Optional[datetime] = Field(None, description="Job start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Job completion timestamp")
    created_at: datetime = Field(..., description="Record creation timestamp")
    modified_at: datetime = Field(..., description="Record modification timestamp")


class JobFilter(BaseModel):
    """Schema for filtering jobs in list queries."""

    status: Optional[JobStatus] = Field(None, description="Filter by status")
    job_type: Optional[JobType] = Field(None, description="Filter by job type")
    source: Optional[JobSource] = Field(None, description="Filter by source")
    cluster_id: Optional[UUID] = Field(None, description="Filter by cluster")
    source_id: Optional[UUID] = Field(None, description="Filter by source ID")
    priority_min: Optional[int] = Field(None, ge=0, description="Minimum priority")
    priority_max: Optional[int] = Field(None, ge=0, description="Maximum priority")


class JobListResponse(BaseModel):
    """Schema for paginated job list responses."""

    jobs: list[JobResponse] = Field(..., description="List of jobs")
    total: int = Field(..., ge=0, description="Total number of matching jobs")
    page: int = Field(..., ge=1, description="Current page number")
    page_size: int = Field(..., ge=1, description="Number of items per page")


class JobStatusTransition(BaseModel):
    """Schema for transitioning job status."""

    status: JobStatus = Field(..., description="New status")
    error_message: Optional[str] = Field(None, description="Error message if transitioning to FAILED")
