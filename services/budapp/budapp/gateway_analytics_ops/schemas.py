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

"""Gateway analytics Pydantic schemas for data validation and serialization."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ..commons.constants import BlockingRuleStatus, BlockingRuleType
from ..commons.schemas import SuccessResponse


class GatewayAnalyticsRequest(BaseModel):
    """Request schema for gateway analytics query."""

    model_config = ConfigDict(from_attributes=True)

    project_ids: Optional[List[UUID]] = Field(
        None, description="List of project IDs to filter by. If not provided, uses user's accessible projects"
    )
    model_ids: Optional[List[UUID]] = Field(None, description="List of model IDs to filter by")
    endpoint_ids: Optional[List[UUID]] = Field(None, description="List of endpoint IDs to filter by")
    start_time: datetime = Field(..., description="Start time for the analytics query")
    end_time: datetime = Field(..., description="End time for the analytics query")
    time_bucket: str = Field("1h", description="Time bucket for aggregation (e.g., 1m, 5m, 1h, 1d)")
    metrics: List[str] = Field(
        default_factory=lambda: ["total_requests", "error_rate", "avg_response_time"],
        description="List of metrics to return",
    )
    group_by: Optional[List[str]] = Field(None, description="Fields to group results by")
    filters: Optional[Dict[str, Any]] = Field(None, description="Additional filters")


class GeographicalStats(BaseModel):
    """Geographical statistics item."""

    country: str = Field(..., description="Country name")
    country_code: str = Field(..., description="Country ISO code")
    region: Optional[str] = Field(None, description="Region/state name")
    city: Optional[str] = Field(None, description="City name")
    request_count: int = Field(..., description="Number of requests from this location")
    error_count: int = Field(0, description="Number of errors from this location")
    avg_response_time: float = Field(..., description="Average response time in milliseconds")


class GeographicalStatsResponse(SuccessResponse):
    """Response schema for geographical statistics."""

    items: List[GeographicalStats] = Field(..., description="List of geographical statistics")
    total: int = Field(..., description="Total number of unique locations")


class BlockingStats(BaseModel):
    """Blocking statistics item."""

    timestamp: datetime = Field(..., description="Timestamp of the blocking event")
    ip_address: str = Field(..., description="Blocked IP address")
    reason: str = Field(..., description="Reason for blocking")
    block_count: int = Field(..., description="Number of times blocked")
    project_id: Optional[UUID] = Field(None, description="Associated project ID")
    project_name: Optional[str] = Field(None, description="Associated project name")


class BlockingStatsResponse(SuccessResponse):
    """Response schema for blocking statistics."""

    items: List[BlockingStats] = Field(..., description="List of blocking statistics")
    total_blocked_ips: int = Field(..., description="Total number of unique blocked IPs")
    total_block_events: int = Field(..., description="Total number of blocking events")


class TopRoute(BaseModel):
    """Top API route item."""

    route: str = Field(..., description="API route path")
    method: str = Field(..., description="HTTP method")
    request_count: int = Field(..., description="Number of requests to this route")
    error_count: int = Field(0, description="Number of errors for this route")
    avg_response_time: float = Field(..., description="Average response time in milliseconds")
    p95_response_time: float = Field(..., description="95th percentile response time")
    p99_response_time: float = Field(..., description="99th percentile response time")
    error_rate: float = Field(..., description="Error rate percentage")
    project_id: Optional[UUID] = Field(None, description="Associated project ID")
    project_name: Optional[str] = Field(None, description="Associated project name")
    model_id: Optional[UUID] = Field(None, description="Associated model ID")
    model_name: Optional[str] = Field(None, description="Associated model name")
    endpoint_id: Optional[UUID] = Field(None, description="Associated endpoint ID")
    endpoint_name: Optional[str] = Field(None, description="Associated endpoint name")


class TopRoutesResponse(SuccessResponse):
    """Response schema for top routes."""

    items: List[TopRoute] = Field(..., description="List of top routes")
    total: int = Field(..., description="Total number of routes")


class ClientAnalytics(BaseModel):
    """Client analytics item."""

    client_id: str = Field(..., description="Client identifier (could be user ID, API key, etc.)")
    client_name: Optional[str] = Field(None, description="Client name if available")
    request_count: int = Field(..., description="Number of requests from this client")
    error_count: int = Field(0, description="Number of errors for this client")
    avg_response_time: float = Field(..., description="Average response time in milliseconds")
    total_tokens_used: Optional[int] = Field(None, description="Total tokens consumed")
    total_cost: Optional[float] = Field(None, description="Total cost incurred")
    last_request_time: datetime = Field(..., description="Timestamp of last request")
    project_ids: List[UUID] = Field(default_factory=list, description="Associated project IDs")
    model_ids: List[UUID] = Field(default_factory=list, description="Models used by this client")


class ClientAnalyticsResponse(SuccessResponse):
    """Response schema for client analytics."""

    items: List[ClientAnalytics] = Field(..., description="List of client analytics")
    total_clients: int = Field(..., description="Total number of unique clients")
    total_requests: int = Field(..., description="Total number of requests")


class GatewayAnalyticsItem(BaseModel):
    """Gateway analytics item in the response."""

    timestamp: datetime = Field(..., description="Timestamp for this data point")
    project_id: Optional[UUID] = Field(None, description="Project ID")
    project_name: Optional[str] = Field(None, description="Project name")
    model_id: Optional[UUID] = Field(None, description="Model ID")
    model_name: Optional[str] = Field(None, description="Model name")
    endpoint_id: Optional[UUID] = Field(None, description="Endpoint ID")
    endpoint_name: Optional[str] = Field(None, description="Endpoint name")
    total_requests: int = Field(0, description="Total number of requests")
    error_count: int = Field(0, description="Number of errors")
    error_rate: float = Field(0.0, description="Error rate percentage")
    avg_response_time: float = Field(0.0, description="Average response time in milliseconds")
    p95_response_time: Optional[float] = Field(None, description="95th percentile response time")
    p99_response_time: Optional[float] = Field(None, description="99th percentile response time")
    total_tokens_used: Optional[int] = Field(None, description="Total tokens consumed")
    total_cost: Optional[float] = Field(None, description="Total cost incurred")
    additional_metrics: Optional[Dict[str, Any]] = Field(None, description="Additional custom metrics")


class GatewayAnalyticsBucket(BaseModel):
    """Time bucket containing analytics items."""

    timestamp: datetime = Field(..., description="Start of the time bucket")
    items: List[GatewayAnalyticsItem] = Field(..., description="Analytics items in this time bucket")


class GatewayAnalyticsResponse(SuccessResponse):
    """Response schema for gateway analytics."""

    items: List[GatewayAnalyticsBucket] = Field(..., description="List of time buckets with analytics data")
    summary: Dict[str, Any] = Field(
        default_factory=dict,
        description="Summary statistics across all time buckets",
    )


class BlockingRuleBase(BaseModel):
    """Base schema for blocking rules."""

    name: str = Field(..., description="Name of the blocking rule", max_length=255)
    description: Optional[str] = Field(None, description="Description of the rule", max_length=1000)
    rule_type: BlockingRuleType = Field(..., description="Type of blocking rule")
    rule_config: Dict[str, Any] = Field(..., description="Rule configuration (varies by type)")
    reason: Optional[str] = Field(None, description="Reason for creating this rule", max_length=500)
    priority: int = Field(default=0, description="Rule priority (higher values evaluated first)")
    endpoint_id: Optional[UUID] = Field(None, description="Optional endpoint-specific rule")


class BlockingRuleCreate(BlockingRuleBase):
    """Schema for creating a blocking rule."""

    pass


class BlockingRuleUpdate(BaseModel):
    """Schema for updating a blocking rule."""

    name: Optional[str] = Field(None, description="Name of the blocking rule", max_length=255)
    description: Optional[str] = Field(None, description="Description of the rule", max_length=1000)
    rule_config: Optional[Dict[str, Any]] = Field(None, description="Rule configuration")
    status: Optional[BlockingRuleStatus] = Field(None, description="Rule status")
    reason: Optional[str] = Field(None, description="Reason for the rule", max_length=500)
    priority: Optional[int] = Field(None, description="Rule priority")


class BlockingRule(BlockingRuleBase):
    """Schema for blocking rule response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Unique identifier of the rule")
    project_id: UUID = Field(..., description="Project ID this rule belongs to")
    status: BlockingRuleStatus = Field(..., description="Current status of the rule")
    created_by: UUID = Field(..., description="User who created the rule")
    match_count: int = Field(default=0, description="Number of times this rule has been matched")
    last_matched_at: Optional[datetime] = Field(None, description="Last time this rule was matched")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    # Optional enriched fields
    project_name: Optional[str] = Field(None, description="Project name")
    endpoint_name: Optional[str] = Field(None, description="Endpoint name if applicable")
    created_by_name: Optional[str] = Field(None, description="Name of user who created the rule")


class BlockingRuleListResponse(SuccessResponse):
    """Response schema for listing blocking rules."""

    items: List[BlockingRule] = Field(..., description="List of blocking rules")
    total: int = Field(..., description="Total number of rules")
    page: int = Field(1, description="Current page number")
    page_size: int = Field(20, description="Number of items per page")


class BlockingRuleResponse(SuccessResponse):
    """Response schema for single blocking rule."""

    data: BlockingRule = Field(..., description="Blocking rule details")


class BlockingRuleDeleteResponse(SuccessResponse):
    """Response schema for deleting a blocking rule."""

    id: UUID = Field(..., description="ID of the deleted rule")


class AutoBlockingConfig(BaseModel):
    """Configuration for automatic blocking based on analytics."""

    enable_auto_blocking: bool = Field(default=False, description="Enable automatic blocking")
    error_threshold: int = Field(default=50, description="Number of errors before blocking")
    error_window_minutes: int = Field(default=60, description="Time window for error counting")
    block_duration_minutes: int = Field(default=1440, description="Duration to block (default 24 hours)")
    whitelist_ips: List[str] = Field(default_factory=list, description="IPs to never auto-block")


class BlockingRuleSyncRequest(BaseModel):
    """Request to sync blocking rules to Redis for real-time access."""

    project_ids: Optional[List[UUID]] = Field(None, description="Specific projects to sync")
    force_sync: bool = Field(default=False, description="Force sync even if no changes")
