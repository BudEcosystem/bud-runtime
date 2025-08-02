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


"""Contains core Pydantic schemas used for data validation and serialization within the metric ops services."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union
from uuid import UUID

from pydantic import BaseModel, field_validator

from ..commons.schemas import SuccessResponse


class DashboardStatsResponse(SuccessResponse):
    """Dashboard stats response schema."""

    total_model_count: int
    cloud_model_count: int
    local_model_count: int
    total_projects: int
    total_project_users: int
    total_endpoints_count: int
    running_endpoints_count: int
    total_clusters: int
    inactive_clusters: int


class InferenceListRequest(BaseModel):
    """Request schema for listing inference requests."""

    # Pagination
    offset: int = 0
    limit: int = 50

    # Filters
    project_id: Optional[UUID] = None
    endpoint_id: Optional[UUID] = None
    model_id: Optional[UUID] = None
    from_date: datetime
    to_date: Optional[datetime] = None
    is_success: Optional[bool] = None
    min_tokens: Optional[int] = None
    max_tokens: Optional[int] = None
    max_latency_ms: Optional[int] = None

    # Sorting
    sort_by: Literal["timestamp", "tokens", "latency", "cost"] = "timestamp"
    sort_order: Literal["asc", "desc"] = "desc"

    @field_validator("limit")
    @classmethod
    def validate_limit(cls, v: int) -> int:
        """Validate that limit is between 1 and 1000."""
        if v < 1:
            raise ValueError("limit must be at least 1")
        if v > 1000:
            raise ValueError("limit must not exceed 1000")
        return v

    @field_validator("offset")
    @classmethod
    def validate_offset(cls, v: int) -> int:
        """Validate that offset is not negative."""
        if v < 0:
            raise ValueError("offset must not be negative")
        return v


class InferenceListItem(BaseModel):
    """Schema for inference items in list response with enriched data."""

    inference_id: UUID
    timestamp: datetime
    model_name: str
    model_display_name: Optional[str] = None  # Enriched
    project_name: Optional[str] = None  # Enriched
    endpoint_name: Optional[str] = None  # Enriched
    prompt_preview: str
    response_preview: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    response_time_ms: int
    cost: Optional[float] = None
    is_success: bool
    cached: bool


class InferenceListResponse(SuccessResponse):
    """Response schema for listing inference requests."""

    items: List[InferenceListItem]
    total_count: int
    offset: int
    limit: int
    has_more: bool


class InferenceDetailResponse(SuccessResponse):
    """Response schema for detailed inference information with enriched data."""

    # Core info
    inference_id: UUID
    timestamp: datetime

    # Model info
    model_name: str
    model_display_name: Optional[str] = None  # Enriched
    model_provider: str
    model_id: UUID

    # Project/Endpoint info
    project_id: UUID
    project_name: Optional[str] = None  # Enriched
    endpoint_id: UUID
    endpoint_name: Optional[str] = None  # Enriched

    # Content
    system_prompt: Optional[str] = None
    messages: List[Dict[str, Any]]
    output: str

    # Metadata
    function_name: Optional[str] = None
    variant_name: Optional[str] = None
    episode_id: Optional[UUID] = None

    # Performance
    input_tokens: int
    output_tokens: int
    response_time_ms: int
    ttft_ms: Optional[int] = None
    processing_time_ms: Optional[int] = None

    # Request details
    request_ip: Optional[str] = None
    request_arrival_time: datetime
    request_forward_time: datetime

    # Status
    is_success: bool
    cached: bool
    finish_reason: Optional[str] = None
    cost: Optional[float] = None

    # Raw data (optional)
    raw_request: Optional[str] = None
    raw_response: Optional[str] = None

    # Feedback summary
    feedback_count: int
    average_rating: Optional[float] = None


class FeedbackItem(BaseModel):
    """Schema for individual feedback item."""

    feedback_id: UUID
    feedback_type: Literal["boolean", "float", "comment", "demonstration"]
    metric_name: Optional[str] = None
    value: Optional[Union[bool, float, str]] = None
    created_at: datetime


class InferenceFeedbackResponse(SuccessResponse):
    """Response schema for inference feedback."""

    inference_id: UUID
    feedback_items: List[FeedbackItem]
    total_count: int
