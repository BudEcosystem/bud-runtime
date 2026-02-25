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

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..commons.constants import BlockingRuleStatus, BlockingRuleType
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
    endpoint_type: Optional[
        Literal[
            "chat",
            "embedding",
            "audio_transcription",
            "audio_translation",
            "text_to_speech",
            "image_generation",
            "moderation",
        ]
    ] = None

    # Additional filters for complex queries (e.g., {"api_key_project_id": ["uuid1", "uuid2"]})
    filters: Optional[Dict[str, Any]] = None

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
    endpoint_type: str = "chat"  # Default to chat for backward compatibility
    # Error fields for failed inferences
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    error_type: Optional[str] = None
    status_code: Optional[int] = None


class InferenceListResponse(SuccessResponse):
    """Response schema for listing inference requests."""

    items: List[InferenceListItem]
    total_count: int
    offset: int
    limit: int
    has_more: bool


class GatewayMetadata(BaseModel):
    """Schema for gateway metadata."""

    # Network metadata
    client_ip: Optional[str] = None
    proxy_chain: Optional[str] = None
    protocol_version: Optional[str] = None

    # Geographical data
    country_code: Optional[str] = None
    country_name: Optional[str] = None  # Enriched from country_code
    region: Optional[str] = None
    city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    timezone: Optional[str] = None
    asn: Optional[int] = None
    isp: Optional[str] = None

    # Client metadata
    user_agent: Optional[str] = None
    device_type: Optional[str] = None
    browser_name: Optional[str] = None
    browser_version: Optional[str] = None
    os_name: Optional[str] = None
    os_version: Optional[str] = None
    is_bot: Optional[bool] = None

    # Request context
    method: Optional[str] = None
    path: Optional[str] = None
    query_params: Optional[str] = None
    request_headers: Optional[Dict[str, str]] = None
    body_size: Optional[int] = None

    # Authentication context
    api_key_id: Optional[str] = None
    auth_method: Optional[str] = None
    user_id: Optional[str] = None

    # Performance metrics
    gateway_processing_ms: Optional[int] = None
    total_duration_ms: Optional[int] = None

    # Model routing information
    routing_decision: Optional[str] = None
    model_version: Optional[str] = None

    # Response metadata
    status_code: Optional[int] = None
    response_size: Optional[int] = None
    response_headers: Optional[Dict[str, str]] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None

    # Blocking information
    is_blocked: Optional[bool] = None
    block_reason: Optional[str] = None
    block_rule_id: Optional[str] = None

    # Custom tags
    tags: Optional[Dict[str, str]] = None


class InferenceDetailResponse(SuccessResponse):
    """Response schema for detailed inference information with enriched data."""

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    # Core info
    inference_id: UUID
    timestamp: datetime

    # Model info
    model_name: str
    model_display_name: Optional[str] = None  # Enriched
    model_provider: str
    model_id: Optional[UUID] = None  # Can be NULL for /v1/responses endpoint type

    # Project/Endpoint info
    project_id: UUID
    project_name: Optional[str] = None  # Enriched
    endpoint_id: Optional[UUID] = None  # Can be NULL for /v1/responses endpoint type
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
    endpoint_type: Optional[str] = None

    # Error details for failed inferences
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    error_type: Optional[str] = None
    status_code: Optional[int] = None

    # Raw data (optional)
    raw_request: Optional[str] = None
    raw_response: Optional[str] = None
    gateway_request: Optional[Dict[str, Any]] = None
    gateway_response: Optional[Dict[str, Any]] = None

    # Gateway metadata (new)
    gateway_metadata: Optional[GatewayMetadata] = None

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


# Gateway Analytics Schemas


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


class BlockingRulesStatsOverview(BaseModel):
    """Overview statistics for blocking rules dashboard cards."""

    total_rules: int = Field(..., description="Total number of blocking rules")
    active_rules: int = Field(..., description="Number of active blocking rules")
    inactive_rules: int = Field(..., description="Number of inactive blocking rules")
    expired_rules: int = Field(..., description="Number of expired blocking rules")
    total_blocks_today: int = Field(..., description="Total blocks in the last 24 hours")
    total_blocks_week: int = Field(..., description="Total blocks in the last 7 days")
    top_blocked_ips: List[Dict[str, Any]] = Field(default_factory=list, description="Top blocked IP addresses")
    top_blocked_countries: List[Dict[str, Any]] = Field(default_factory=list, description="Top blocked countries")
    blocks_by_type: Dict[str, int] = Field(default_factory=dict, description="Blocks grouped by rule type")
    blocks_timeline: List[Dict[str, Any]] = Field(default_factory=list, description="Timeline of blocking events")


class BlockingRulesStatsOverviewResponse(SuccessResponse):
    """Response schema for blocking rules overview statistics."""

    object: str = "blocking_rules_stats"
    total_rules: int = Field(..., description="Total number of blocking rules")
    active_rules: int = Field(..., description="Number of active blocking rules")
    inactive_rules: int = Field(..., description="Number of inactive blocking rules")
    expired_rules: int = Field(..., description="Number of expired blocking rules")
    total_blocks_today: int = Field(..., description="Total blocks in the last 24 hours")
    total_blocks_week: int = Field(..., description="Total blocks in the last 7 days")
    top_blocked_ips: List[Dict[str, Any]] = Field(default_factory=list, description="Top blocked IP addresses")
    top_blocked_countries: List[Dict[str, Any]] = Field(default_factory=list, description="Top blocked countries")
    blocks_by_type: Dict[str, int] = Field(default_factory=dict, description="Blocks grouped by rule type")
    blocks_timeline: List[Dict[str, Any]] = Field(default_factory=list, description="Timeline of blocking events")


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


# Blocking Rules Schemas


class BlockingRuleBase(BaseModel):
    """Base schema for blocking rules."""

    name: str = Field(..., description="Name of the blocking rule", max_length=255)
    description: Optional[str] = Field(None, description="Description of the rule", max_length=1000)
    rule_type: BlockingRuleType = Field(..., description="Type of blocking rule")
    rule_config: Dict[str, Any] = Field(..., description="Rule configuration (varies by type)")
    reason: Optional[str] = Field(None, description="Reason for creating this rule", max_length=500)
    priority: int = Field(default=0, description="Rule priority (higher values evaluated first)")
    model_name: Optional[str] = Field(None, description="Model name for model-specific rules (None for global rules)")
    endpoint_id: Optional[UUID] = Field(None, description="Deprecated - use model_name instead")


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
    model_name: Optional[str] = Field(None, description="Model name for model-specific rules")


class BlockingRule(BlockingRuleBase):
    """Schema for blocking rule response."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID = Field(..., description="Unique identifier of the rule")
    project_id: Optional[UUID] = Field(None, description="Project ID (None for global rules)")
    status: BlockingRuleStatus = Field(..., description="Current status of the rule")
    created_by: UUID = Field(..., description="User who created the rule")
    match_count: int = Field(default=0, description="Number of times this rule has been matched")
    last_matched_at: Optional[datetime] = Field(None, description="Last time this rule was matched")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(
        ..., validation_alias="modified_at", serialization_alias="updated_at", description="Last update timestamp"
    )

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


# New Aggregated Metrics Schemas


class AggregatedMetricsRequest(BaseModel):
    """Request schema for aggregated metrics with server-side calculations."""

    from_date: Optional[datetime] = Field(
        None, description="Start date for the analysis (defaults to full retention window)"
    )
    to_date: Optional[datetime] = Field(None, description="End date for the analysis")
    group_by: Optional[List[Literal["model", "project", "endpoint", "user", "user_project"]]] = Field(
        None, description="Dimensions to group by"
    )
    filters: Optional[Dict[str, Any]] = Field(None, description="Filters to apply")
    metrics: List[
        Literal[
            "total_requests",
            "success_rate",
            "avg_latency",
            "p95_latency",
            "p99_latency",
            "total_tokens",
            "total_input_tokens",
            "total_output_tokens",
            "avg_tokens",
            "total_cost",
            "avg_cost",
            "ttft_avg",
            "ttft_p95",
            "ttft_p99",
            "cache_hit_rate",
            "throughput_avg",
            "error_rate",
            "unique_users",
            "p95_inference_cost",
            "max_inference_cost",
            "min_inference_cost",
        ]
    ] = Field(..., description="Metrics to calculate")
    data_source: Literal["inference", "prompt"] = Field(
        default="inference",
        description="Filter by data source: 'inference' for standard requests, 'prompt' for prompt analytics",
    )

    @field_validator("to_date")
    @classmethod
    def validate_to_date(cls, v: Optional[datetime], info) -> Optional[datetime]:
        """Validate that to_date is after from_date."""
        if v is None:
            return v
        from_date = info.data.get("from_date")
        if from_date and v < from_date:
            raise ValueError("to_date must be after from_date")
        return v


class AggregatedMetricValue(BaseModel):
    """Single aggregated metric value."""

    value: Union[int, float] = Field(..., description="The metric value")
    formatted_value: Optional[str] = Field(None, description="Human readable format (e.g., '1.2K', '95.5%')")
    unit: Optional[str] = Field(None, description="Unit of measurement (e.g., 'ms', '%', 'requests')")


class AggregatedMetricsGroup(BaseModel):
    """Grouped aggregated metrics."""

    # Grouping dimensions
    model_id: Optional[UUID] = Field(None, description="Model ID")
    model_name: Optional[str] = Field(None, description="Model name")
    project_id: Optional[UUID] = Field(None, description="Project ID")
    project_name: Optional[str] = Field(None, description="Project name")
    endpoint_id: Optional[UUID] = Field(None, description="Endpoint ID")
    endpoint_name: Optional[str] = Field(None, description="Endpoint name")
    user_id: Optional[str] = Field(None, description="User ID")
    api_key_project_id: Optional[UUID] = Field(None, description="API key's project ID (for user_project grouping)")
    api_key_project_name: Optional[str] = Field(None, description="API key's project name")

    # Aggregated metrics
    metrics: Dict[str, AggregatedMetricValue] = Field(..., description="Calculated metrics")


class AggregatedMetricsResponse(SuccessResponse):
    """Response schema for aggregated metrics."""

    object: str = Field(default="aggregated_metrics", description="Response object type")
    groups: List[AggregatedMetricsGroup] = Field(..., description="Grouped metrics")
    summary: Dict[str, AggregatedMetricValue] = Field(..., description="Overall aggregated values")
    total_groups: int = Field(..., description="Total number of groups")
    date_range: Dict[str, datetime] = Field(..., description="Date range used for analysis")


class TimeSeriesRequest(BaseModel):
    """Request schema for time-series data."""

    from_date: datetime = Field(..., description="Start date for the time series")
    to_date: Optional[datetime] = Field(None, description="End date for the time series")
    interval: Literal["1m", "5m", "15m", "30m", "1h", "6h", "12h", "1d", "1w"] = Field(
        default="1h", description="Time interval for data points"
    )
    metrics: List[
        Literal[
            "requests",
            "success_rate",
            "avg_latency",
            "p95_latency",
            "p99_latency",
            "tokens",
            "cost",
            "ttft_avg",
            "cache_hit_rate",
            "throughput",
            "error_rate",
            "unique_users",
            "success_count",
            "error_count",
        ]
    ] = Field(..., description="Metrics to include in time series")
    filters: Optional[Dict[str, Any]] = Field(None, description="Filters to apply")
    group_by: Optional[List[Literal["model", "project", "endpoint", "user_project"]]] = Field(
        None, description="Dimensions to group by"
    )
    fill_gaps: bool = Field(default=True, description="Fill gaps in time series data")
    data_source: Literal["inference", "prompt"] = Field(
        default="inference",
        description="Filter by data source: 'inference' excludes prompt analytics (default), 'prompt' returns only prompt analytics",
    )

    @field_validator("to_date")
    @classmethod
    def validate_to_date(cls, v: Optional[datetime], info) -> Optional[datetime]:
        """Validate that to_date is after from_date."""
        if v is None:
            return v
        from_date = info.data.get("from_date")
        if from_date and v < from_date:
            raise ValueError("to_date must be after from_date")
        return v


class TimeSeriesPoint(BaseModel):
    """Single time series data point."""

    timestamp: datetime = Field(..., description="Timestamp for this data point")
    values: Dict[str, Optional[float]] = Field(..., description="Metric values at this timestamp")


class TimeSeriesGroup(BaseModel):
    """Time series data for a specific group."""

    # Grouping dimensions
    model_id: Optional[UUID] = Field(None, description="Model ID")
    model_name: Optional[str] = Field(None, description="Model name")
    project_id: Optional[UUID] = Field(None, description="Project ID")
    project_name: Optional[str] = Field(None, description="Project name")
    endpoint_id: Optional[UUID] = Field(None, description="Endpoint ID")
    endpoint_name: Optional[str] = Field(None, description="Endpoint name")
    api_key_project_id: Optional[UUID] = Field(None, description="API key's project ID (for user_project grouping)")
    api_key_project_name: Optional[str] = Field(None, description="API key's project name")

    # Time series data
    data_points: List[TimeSeriesPoint] = Field(..., description="Time series data points")


class TimeSeriesResponse(SuccessResponse):
    """Response schema for time-series data."""

    object: str = Field(default="time_series", description="Response object type")
    groups: List[TimeSeriesGroup] = Field(..., description="Time series groups")
    interval: str = Field(..., description="Time interval used")
    date_range: Dict[str, datetime] = Field(..., description="Date range for the time series")


class GeographicDataRequest(BaseModel):
    """Request schema for geographic distribution data."""

    from_date: datetime = Field(..., description="Start date for the analysis")
    to_date: Optional[datetime] = Field(None, description="End date for the analysis")
    filters: Optional[Dict[str, Any]] = Field(None, description="Filters to apply")
    group_by: Literal["country", "region", "city"] = Field(default="country", description="Geographic grouping level")
    limit: int = Field(default=50, description="Maximum number of locations to return")

    @field_validator("to_date")
    @classmethod
    def validate_to_date(cls, v: Optional[datetime], info) -> Optional[datetime]:
        """Validate that to_date is after from_date."""
        if v is None:
            return v
        from_date = info.data.get("from_date")
        if from_date and v < from_date:
            raise ValueError("to_date must be after from_date")
        return v

    @field_validator("limit")
    @classmethod
    def validate_limit(cls, v: int) -> int:
        """Validate that limit is between 1 and 1000."""
        if v < 1 or v > 1000:
            raise ValueError("limit must be between 1 and 1000")
        return v


class GeographicDataPoint(BaseModel):
    """Geographic data point."""

    # Geographic info
    country_code: Optional[str] = Field(None, description="Country ISO code")
    country_name: Optional[str] = Field(None, description="Country name")
    region: Optional[str] = Field(None, description="Region/state name")
    city: Optional[str] = Field(None, description="City name")
    latitude: Optional[float] = Field(None, description="Latitude coordinate")
    longitude: Optional[float] = Field(None, description="Longitude coordinate")

    # Metrics
    request_count: int = Field(..., description="Number of requests from this location")
    success_rate: float = Field(..., description="Success rate percentage")
    avg_latency_ms: Optional[float] = Field(None, description="Average latency in milliseconds")
    unique_users: Optional[int] = Field(None, description="Number of unique users")
    percentage: float = Field(..., description="Percentage of total requests")


class GeographicDataResponse(SuccessResponse):
    """Response schema for geographic distribution data."""

    object: str = Field(default="geographic_data", description="Response object type")
    locations: List[GeographicDataPoint] = Field(..., description="Geographic data points")
    total_requests: int = Field(..., description="Total number of requests")
    total_locations: int = Field(..., description="Total number of unique locations")
    date_range: Dict[str, datetime] = Field(..., description="Date range for the analysis")
    group_by: str = Field(..., description="Geographic grouping level used")


class LatencyDistributionRequest(BaseModel):
    """Request schema for latency distribution data."""

    from_date: datetime = Field(..., description="Start date for the analysis")
    to_date: Optional[datetime] = Field(None, description="End date for the analysis")
    filters: Optional[Dict[str, Any]] = Field(None, description="Additional filters to apply")
    group_by: Optional[list[Literal["model", "project", "endpoint", "user", "user_project"]]] = Field(
        None, description="Dimensions to group the results by"
    )
    buckets: Optional[List[Dict[str, Union[int, str]]]] = Field(
        None, description="Custom latency buckets (min, max, label)"
    )

    @field_validator("to_date")
    @classmethod
    def validate_to_date(cls, v: Optional[datetime], info) -> Optional[datetime]:
        """Validate that to_date is after from_date."""
        if v is None:
            return v
        from_date = info.data.get("from_date")
        if from_date and v < from_date:
            raise ValueError("to_date must be after from_date")
        return v

    @field_validator("buckets")
    @classmethod
    def validate_buckets(
        cls, v: Optional[List[Dict[str, Union[int, str]]]]
    ) -> Optional[List[Dict[str, Union[int, str]]]]:
        """Validate bucket format."""
        if v is None:
            return v
        for bucket in v:
            if not isinstance(bucket, dict) or "min" not in bucket or "max" not in bucket or "label" not in bucket:
                raise ValueError("Each bucket must have 'min', 'max', and 'label' fields")
        return v


class LatencyDistributionBucket(BaseModel):
    """Single latency distribution bucket."""

    range: str = Field(..., description="Latency range (e.g., '0-100ms')")
    count: int = Field(..., description="Number of requests in this bucket")
    percentage: float = Field(..., description="Percentage of total requests")
    avg_latency: Optional[float] = Field(None, description="Average latency within this bucket")


class LatencyDistributionGroup(BaseModel):
    """Latency distribution for a specific group."""

    # Grouping dimensions
    model_id: Optional[UUID] = Field(None, description="Model ID")
    model_name: Optional[str] = Field(None, description="Model display name")
    project_id: Optional[UUID] = Field(None, description="Project ID")
    project_name: Optional[str] = Field(None, description="Project name")
    endpoint_id: Optional[UUID] = Field(None, description="Endpoint ID")
    endpoint_name: Optional[str] = Field(None, description="Endpoint name")
    user_id: Optional[str] = Field(None, description="User ID")
    api_key_project_id: Optional[UUID] = Field(None, description="API key's project ID (for user_project grouping)")
    api_key_project_name: Optional[str] = Field(None, description="API key's project name")

    # Distribution data
    buckets: List[LatencyDistributionBucket] = Field(..., description="Distribution buckets")
    total_requests: int = Field(..., description="Total requests for this group")


class LatencyDistributionResponse(SuccessResponse):
    """Response schema for latency distribution data."""

    object: str = Field(default="latency_distribution", description="Response object type")
    groups: List[LatencyDistributionGroup] = Field(..., description="Grouped distribution data")
    overall_distribution: List[LatencyDistributionBucket] = Field(
        ..., description="Overall distribution aggregated across all groups"
    )
    total_requests: int = Field(..., description="Total number of requests")
    date_range: Dict[str, datetime] = Field(..., description="Date range for the analysis")
    bucket_definitions: List[Dict[str, Union[int, str]]] = Field(
        ..., description="The bucket ranges used for the distribution"
    )


# ============ GPU Metrics Proxy Schemas ============


class GPUDeviceMetrics(BaseModel):
    """GPU device metrics data."""

    device_uuid: str
    device_index: int
    device_type: str
    node_name: str
    total_memory_gb: float
    memory_allocated_gb: float
    memory_utilization_percent: float
    core_utilization_percent: float
    cores_allocated_percent: float
    shared_containers_count: int
    hardware_mode: str
    last_metrics_update: datetime
    temperature_celsius: Optional[float] = None
    power_watts: Optional[float] = None
    sm_clock_mhz: Optional[int] = None
    memory_clock_mhz: Optional[int] = None


class HAMISliceMetrics(BaseModel):
    """HAMI slice (container GPU allocation) metrics data."""

    pod_name: str
    pod_namespace: str
    container_name: str
    device_uuid: str
    device_index: int
    node_name: str
    memory_limit_bytes: int
    memory_limit_gb: float
    memory_used_bytes: int
    memory_used_gb: float
    memory_utilization_percent: float
    core_limit_percent: float
    core_used_percent: float
    gpu_utilization_percent: float
    status: str


class NodeGPUSummaryMetrics(BaseModel):
    """Summary of GPU metrics for a single node."""

    gpu_count: int
    total_memory_gb: float
    allocated_memory_gb: float
    memory_utilization_percent: float
    avg_gpu_utilization_percent: float
    active_slices: int


class NodeGPUMetricsResponse(SuccessResponse):
    """Response for node-specific GPU metrics."""

    cluster_id: str
    node_name: str
    timestamp: datetime
    devices: List[GPUDeviceMetrics]
    slices: List[HAMISliceMetrics]
    summary: NodeGPUSummaryMetrics


class ClusterGPUSummaryMetrics(BaseModel):
    """Summary of GPU metrics for entire cluster."""

    total_gpus: int
    total_memory_gb: float
    allocated_memory_gb: float
    available_memory_gb: float
    memory_utilization_percent: float
    avg_gpu_utilization_percent: float
    total_slices: int
    active_slices: int
    avg_temperature_celsius: Optional[float] = None
    total_power_watts: Optional[float] = None


class NodeGPUSummaryItem(BaseModel):
    """Summary of GPU metrics for a node within cluster response."""

    node_name: str
    gpu_count: int
    total_memory_gb: float
    allocated_memory_gb: float
    memory_utilization_percent: float
    avg_gpu_utilization_percent: float
    active_slices: int


class ClusterGPUMetricsResponse(SuccessResponse):
    """Response for cluster-wide GPU metrics."""

    cluster_id: str
    timestamp: datetime
    summary: ClusterGPUSummaryMetrics
    nodes: List[NodeGPUSummaryItem]
    devices: List[GPUDeviceMetrics]
    slices: List[HAMISliceMetrics]


class SliceActivityData(BaseModel):
    """Slice activity data for timeseries charts."""

    slice_name: str
    namespace: str
    data: List[float]


class GPUTimeSeriesResponse(SuccessResponse):
    """Response for GPU timeseries data."""

    timestamps: List[int]
    gpu_utilization: List[List[float]]
    memory_utilization: List[List[float]]
    temperature: List[List[float]]
    power: List[List[float]]
    slice_activity: List[SliceActivityData]


# ============ Prompt Distribution Schemas ============


class PromptDistributionRequest(BaseModel):
    """Request schema for prompt analytics distribution data.

    Supports bucketing by concurrency, input_tokens, or output_tokens (X-axis)
    and metrics like total_duration_ms, ttft_ms, response_time_ms, throughput_per_user (Y-axis).
    """

    from_date: datetime
    to_date: Optional[datetime] = None
    filters: Optional[Dict[str, Any]] = None  # project_id, endpoint_id, prompt_id
    bucket_by: Literal["concurrency", "input_tokens", "output_tokens"]
    metric: Literal["total_duration_ms", "ttft_ms", "response_time_ms", "throughput_per_user"]
    buckets: Optional[List[Dict[str, Union[float, str]]]] = None  # Auto-generate 10 buckets if None

    @field_validator("to_date")
    @classmethod
    def validate_to_date(cls, v: Optional[datetime], info) -> Optional[datetime]:
        """Validate that to_date is after from_date."""
        if v is None:
            return v
        from_date = info.data.get("from_date")
        if from_date and v < from_date:
            raise ValueError("to_date must be after from_date")
        return v

    @field_validator("buckets")
    @classmethod
    def validate_buckets(
        cls, v: Optional[List[Dict[str, Union[float, str]]]]
    ) -> Optional[List[Dict[str, Union[float, str]]]]:
        """Validate bucket format."""
        if v is None:
            return v
        for bucket in v:
            if not isinstance(bucket, dict) or "min" not in bucket or "max" not in bucket or "label" not in bucket:
                raise ValueError("Each bucket must have 'min', 'max', and 'label' fields")
        return v


class PromptDistributionBucket(BaseModel):
    """Single prompt distribution bucket."""

    range: str = Field(..., description="Bucket range label (e.g., '0-5', '5-10')")
    bucket_start: float = Field(..., description="Start value of the bucket")
    bucket_end: float = Field(..., description="End value of the bucket")
    count: int = Field(..., description="Number of items in this bucket")
    avg_value: float = Field(..., description="Average of the metric within this bucket")


class PromptDistributionResponse(SuccessResponse):
    """Response schema for prompt analytics distribution data."""

    object: str = Field(default="prompt_distribution", description="Response object type")
    buckets: List[PromptDistributionBucket] = Field(..., description="Distribution buckets")
    total_count: int = Field(..., description="Total number of items across all buckets")
    bucket_by: str = Field(..., description="The dimension used for bucketing")
    metric: str = Field(..., description="The metric being aggregated")
    date_range: Dict[str, datetime] = Field(..., description="Date range for the analysis")
    bucket_definitions: List[Dict[str, Union[float, str]]] = Field(
        ..., description="The bucket ranges used for the distribution"
    )
