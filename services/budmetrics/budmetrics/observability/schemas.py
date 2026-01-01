import ipaddress
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union
from uuid import UUID

from budmicroframe.commons.schemas import CloudEventBase, ResponseBase
from fastapi.responses import ORJSONResponse
from pydantic import BaseModel, ConfigDict, field_validator, model_validator


def validate_date_range(from_date: Optional[datetime], to_date: Optional[datetime], max_days: int = 90) -> None:
    """Validate date range constraints.

    Args:
        from_date: Start date
        to_date: End date
        max_days: Maximum allowed days between dates (default 90)

    Raises:
        ValueError: If date range is invalid
    """
    if to_date is None:
        return

    if from_date and to_date < from_date:
        raise ValueError("to_date must be after from_date")

    # Validate date range is not too large
    if from_date:
        date_diff = to_date - from_date
        if date_diff.days > max_days:
            raise ValueError(f"Date range cannot exceed {max_days} days")

    # Validate dates are not too far in the future
    now = datetime.now(to_date.tzinfo) if to_date.tzinfo else datetime.now()
    if to_date > now + timedelta(days=1):  # Allow 1 day in future for timezone differences
        raise ValueError("to_date cannot be more than 1 day in the future")


class CredentialUsageRequest(BaseModel):
    """Request for fetching credential usage statistics."""

    since: datetime
    """Get usage since this timestamp."""

    credential_ids: Optional[List[UUID]] = None
    """Optional list of specific credential IDs to query. If None, returns all."""


class CredentialUsageItem(BaseModel):
    """Individual credential usage information."""

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    credential_id: UUID
    """The credential ID (api_key_id from ModelInferenceDetails)."""

    last_used_at: datetime
    """The most recent timestamp when this credential was used."""

    request_count: int
    """Total number of requests made with this credential in the time window."""


class CredentialUsageResponse(ResponseBase):
    """Response containing credential usage statistics."""

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    object: str = "credential_usage"
    """The type of response object."""

    credentials: List[CredentialUsageItem]
    """List of credential usage information."""

    query_window: Dict[str, datetime]
    """The time window used for the query (since and until)."""


class MetricsSyncRequest(BaseModel):
    """Unified request for credential usage and user usage sync."""

    sync_mode: Literal["incremental", "full"] = "incremental"
    """Whether to return only active entities or all entities."""

    activity_threshold_minutes: int = 5
    """For incremental mode: how many minutes back to consider 'recent activity'."""

    credential_sync: bool = True
    """Whether to include credential usage data."""

    user_usage_sync: bool = True
    """Whether to include user usage data."""

    user_ids: Optional[List[UUID]] = None
    """For full mode: specific user IDs to sync. If None, syncs all users."""


class UserUsageItem(BaseModel):
    """User usage information for sync."""

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    user_id: UUID
    """The user ID."""

    last_activity_at: datetime
    """The most recent timestamp when this user made a request."""

    usage_data: Dict[str, Any]
    """Usage data including tokens, cost, request count, success rate."""


class MetricsSyncResponse(ResponseBase):
    """Unified response containing both credential and user data."""

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    object: str = "metrics_sync"
    """The type of response object."""

    sync_mode: str
    """The sync mode used (incremental or full)."""

    activity_threshold_minutes: int
    """The activity threshold used for incremental mode."""

    query_timestamp: datetime
    """When this sync was performed."""

    credential_usage: List[CredentialUsageItem]
    """List of credential usage information."""

    user_usage: List[UserUsageItem]
    """List of user usage information."""

    stats: Dict[str, int]
    """Statistics about the sync (active_credentials, active_users, total_users_checked)."""


MetricType = Literal[
    "request_count",
    "success_request",
    "failure_request",
    "queuing_time",
    "input_token",
    "output_token",
    "concurrent_requests",
    "ttft",
    "latency",
    "throughput",
    "cache",
]


class CountMetric(BaseModel):
    count: int
    rate: Optional[float] = None
    delta: Optional[Union[float, int]] = None
    delta_percent: Optional[float] = None


class TimeMetric(BaseModel):
    avg_time_ms: float
    delta: Optional[Union[float, int]] = None
    delta_percent: Optional[float] = None


class PerformanceMetric(BaseModel):
    avg: float
    p99: Optional[float] = None
    p95: Optional[float] = None
    delta: Optional[Union[float, int]] = None
    delta_percent: Optional[float] = None


class CacheMetric(BaseModel):
    hit_rate: float
    hit_count: int
    avg_latency_ms: Optional[float] = None
    delta: Optional[Union[float, int]] = None
    delta_percent: Optional[float] = None


class MetricsData(BaseModel):
    model_id: Optional[UUID] = None
    project_id: Optional[UUID] = None
    endpoint_id: Optional[UUID] = None
    data: dict[MetricType, Union[CountMetric, TimeMetric, PerformanceMetric, CacheMetric]]


class PeriodBin(BaseModel):
    time_period: datetime
    items: Optional[list[MetricsData]]


class ObservabilityMetricsRequest(BaseModel):
    metrics: list[MetricType]
    from_date: datetime
    to_date: Optional[datetime] = None
    frequency_unit: Literal["hour", "day", "week", "month", "quarter", "year"] = "day"
    frequency_interval: Optional[int] = None
    filters: Optional[dict[Literal["model", "project", "endpoint"], Union[list[UUID], UUID]]] = None
    group_by: Optional[list[Literal["model", "project", "endpoint", "user_project"]]] = None
    return_delta: bool = True
    fill_time_gaps: bool = True
    topk: Optional[int] = None

    @field_validator("frequency_interval")
    @classmethod
    def validate_frequency_interval(cls, v: Optional[int]) -> Optional[int]:
        """Validate that frequency_interval is at least 1."""
        if v is not None and v < 1:
            raise ValueError("frequency_interval must be at least 1")
        return v

    @field_validator("to_date")
    @classmethod
    def validate_to_date(cls, v: Optional[datetime], info) -> Optional[datetime]:
        """Validate that to_date is after from_date and within reasonable range."""
        validate_date_range(info.data.get("from_date"), v)
        return v

    @field_validator("filters")
    @classmethod
    def validate_filters(cls, v: Optional[dict]) -> Optional[dict]:
        """Validate that filter values are not empty."""
        if v is None:
            return v
        for key, value in v.items():
            if not value:
                raise ValueError(f"{key} filter must not be empty")
            if isinstance(value, list) and len(value) == 0:
                raise ValueError(f"{key} filter list must not be empty")
        return v

    @field_validator("topk")
    @classmethod
    def validate_topk(cls, v: Optional[int]) -> Optional[int]:
        """Validate that topk is at least 1."""
        if v is not None and v < 1:
            raise ValueError("topk must be at least 1")
        return v

    @model_validator(mode="after")
    def validate_topk_with_group_by(self) -> "ObservabilityMetricsRequest":
        """Ensure topk is only used with group_by and without filters."""
        if self.topk is not None:
            if not self.group_by:
                raise ValueError("topk requires group_by to be specified")
            if self.filters:
                raise ValueError("topk is ignored when filters are specified and should not be used together")
        return self


class ObservabilityMetricsResponse(ResponseBase):
    object: str = "observability_metrics"
    items: list[PeriodBin]

    def to_http_response(
        self,
        include: Union[set[int], set[str], dict[int, Any], dict[str, Any], None] = None,
        exclude: Union[set[int], set[str], dict[int, Any], dict[str, Any], None] = None,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
    ) -> ORJSONResponse:
        """Convert the model instance to an HTTP response.

        Serializes the model instance into a JSON response, with options to include or exclude specific fields
        and customize the response based on various parameters.

        Args:
            include (set[int] | set[str] | dict[int, Any] | dict[str, Any] | None): Fields to include in the response.
            exclude (set[int] | set[str] | dict[int, Any] | dict[str, Any] | None): Fields to exclude from the response.
            exclude_unset (bool): Whether to exclude unset fields from the response.
            exclude_defaults (bool): Whether to exclude default values from the response.
            exclude_none (bool): Whether to exclude fields with None values from the response.

        Returns:
            JSONResponse: The serialized JSON response with the appropriate status code.
        """
        if getattr(self, "object", "") == "error":
            details = self.model_dump()
            status_code = details["code"]
        else:
            details = self.model_dump(
                mode="json",
                include=include,
                exclude=exclude,
                exclude_unset=exclude_unset,
                exclude_defaults=exclude_defaults,
                exclude_none=exclude_none,
            )
            status_code = self.code

        return ORJSONResponse(content=details, status_code=status_code)


class InferenceDetailsMetrics(CloudEventBase):
    """Schema for inference details metrics that maps to ModelInferenceDetails table."""

    # Required fields matching ModelInferenceDetails table
    inference_id: UUID  # Maps to request_id from RequestMetrics
    project_id: UUID
    endpoint_id: UUID
    model_id: UUID
    is_success: bool
    request_arrival_time: datetime
    request_forward_time: datetime

    # Optional fields
    request_ip: Optional[str] = None
    cost: Optional[float] = None
    response_analysis: Optional[Dict[str, Any]] = None

    # Authentication metadata fields
    api_key_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    api_key_project_id: Optional[UUID] = None

    # Error information for failed inferences
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    error_type: Optional[str] = None
    status_code: Optional[int] = None

    @field_validator("request_ip")
    @classmethod
    def validate_ip(cls, v: Optional[str]) -> Optional[str]:
        """Validate IPv4 address format."""
        if v is None:
            return v
        try:
            # Validate IPv4 address format
            ipaddress.IPv4Address(v)
            return v
        except ipaddress.AddressValueError as err:
            raise ValueError(f"Invalid IPv4 address: {v}") from err

    @field_validator("cost")
    @classmethod
    def validate_cost(cls, v: Optional[float]) -> Optional[float]:
        """Validate that cost is not negative."""
        if v is not None and v < 0:
            raise ValueError("Cost cannot be negative")
        return v

    @model_validator(mode="after")
    def validate_timestamps(self) -> "InferenceDetailsMetrics":
        """Ensure request_forward_time is not before request_arrival_time."""
        if self.request_forward_time < self.request_arrival_time:
            raise ValueError("request_forward_time cannot be before request_arrival_time")
        return self


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

    @field_validator("to_date")
    @classmethod
    def validate_to_date(cls, v: Optional[datetime], info) -> Optional[datetime]:
        """Validate that to_date is after from_date and within reasonable range."""
        validate_date_range(info.data.get("from_date"), v)
        return v


class InferenceListItem(BaseModel):
    """Schema for inference items in list response."""

    inference_id: UUID
    timestamp: datetime
    model_name: str
    prompt_preview: str  # First 100 chars
    response_preview: str  # First 100 chars
    input_tokens: int
    output_tokens: int
    total_tokens: int
    response_time_ms: int
    cost: Optional[float] = None
    is_success: bool
    cached: bool
    project_id: Optional[UUID] = None
    api_key_project_id: Optional[UUID] = None  # Project associated with API key
    endpoint_id: Optional[UUID] = None
    model_id: Optional[UUID] = None
    endpoint_type: str = "chat"  # New field to identify inference type
    # Error fields for failed inferences
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    error_type: Optional[str] = None
    status_code: Optional[int] = None


class InferenceListResponse(ResponseBase):
    """Response schema for listing inference requests."""

    object: str = "inference_list"
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


class InferenceDetailResponse(ResponseBase):
    """Response schema for detailed inference information."""

    object: str = "inference_detail"

    # Core info
    inference_id: UUID
    timestamp: datetime

    # Model info
    model_name: str
    model_provider: str
    model_id: UUID

    # Content
    system_prompt: Optional[str] = None
    messages: List[Dict[str, Any]]  # Full chat messages
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
    project_id: UUID
    api_key_project_id: Optional[UUID] = None  # Project associated with API key
    endpoint_id: UUID

    # Status
    is_success: bool
    cached: bool
    finish_reason: Optional[str] = None
    cost: Optional[float] = None

    # Error details for failed inferences
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    error_type: Optional[str] = None
    status_code: Optional[int] = None

    # Raw data (optional)
    raw_request: Optional[str] = None
    raw_response: Optional[str] = None
    gateway_request: Optional[str] = None
    gateway_response: Optional[str] = None

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


class InferenceFeedbackResponse(ResponseBase):
    """Response schema for inference feedback."""

    object: str = "inference_feedback"
    inference_id: UUID
    feedback_items: List[FeedbackItem]
    total_count: int


# New schemas for different inference types
class EmbeddingInferenceDetail(BaseModel):
    """Schema for embedding inference details."""

    embeddings: List[List[float]]
    embedding_dimensions: int
    input_count: int
    input_text: str


class AudioInferenceDetail(BaseModel):
    """Schema for audio inference details."""

    audio_type: Literal["transcription", "translation", "text_to_speech"]
    input: str
    output: str
    language: Optional[str] = None
    duration_seconds: Optional[float] = None
    file_size_bytes: Optional[int] = None
    response_format: Optional[str] = None


class ImageInferenceDetail(BaseModel):
    """Schema for image generation inference details."""

    prompt: str
    image_count: int
    size: str
    quality: str
    style: Optional[str] = None
    images: List[Dict[str, Any]]  # List of image data


class ModerationInferenceDetail(BaseModel):
    """Schema for moderation inference details."""

    input: str
    results: List[Dict[str, Any]]
    flagged: bool
    categories: Dict[str, bool]
    category_scores: Dict[str, float]


class EnhancedInferenceDetailResponse(InferenceDetailResponse):
    """Enhanced response schema for detailed inference information supporting all types."""

    # Type-specific details (only one will be populated based on endpoint_type)
    endpoint_type: str
    embedding_details: Optional[EmbeddingInferenceDetail] = None
    audio_details: Optional[AudioInferenceDetail] = None
    image_details: Optional[ImageInferenceDetail] = None
    moderation_details: Optional[ModerationInferenceDetail] = None


GatewayMetricType = Literal[
    "request_count",
    "success_rate",
    "error_rate",
    "blocked_requests",
    "avg_response_time",
    "p99_response_time",
    "p95_response_time",
    "geographical_distribution",
    "device_distribution",
    "browser_distribution",
    "os_distribution",
    "bot_traffic",
    "unique_clients",
    "bandwidth_usage",
    "route_distribution",
    "status_code_distribution",
]


class GatewayCountMetric(BaseModel):
    """Metric for count-based data."""

    count: int
    rate: Optional[float] = None
    delta: Optional[int] = None
    delta_percent: Optional[float] = None


class GatewayPerformanceMetric(BaseModel):
    """Metric for performance-based data."""

    avg: float
    p99: Optional[float] = None
    p95: Optional[float] = None
    p50: Optional[float] = None
    min: Optional[float] = None
    max: Optional[float] = None
    delta: Optional[float] = None
    delta_percent: Optional[float] = None


class GatewayDistributionMetric(BaseModel):
    """Metric for distribution data."""

    distribution: Dict[str, int]  # e.g., {"US": 100, "UK": 50}
    top_items: Optional[list[Dict[str, Any]]] = None  # e.g., [{"country": "US", "count": 100, "percent": 66.7}]
    total: int


class GatewayRateMetric(BaseModel):
    """Metric for rate-based data."""

    rate: float  # Percentage
    count: int
    total: int
    delta: Optional[float] = None
    delta_percent: Optional[float] = None


class GatewayBandwidthMetric(BaseModel):
    """Metric for bandwidth usage."""

    bytes_sent: int
    bytes_received: int
    total_bytes: int
    avg_request_size: float
    avg_response_size: float


class GatewayAnalyticsRequest(BaseModel):
    """Request model for gateway analytics queries."""

    metrics: list[GatewayMetricType]
    from_date: datetime
    to_date: Optional[datetime] = None
    frequency_unit: Literal["minute", "hour", "day", "week", "month"] = "hour"
    frequency_interval: Optional[int] = None
    filters: Optional[Dict[str, Any]] = None  # e.g., {"country_code": ["US", "UK"], "is_bot": False}
    group_by: Optional[
        list[
            Literal[
                "project", "country", "city", "device_type", "browser", "os", "path", "status_code", "user_project"
            ]
        ]
    ] = None
    return_delta: bool = True
    fill_time_gaps: bool = True
    topk: Optional[int] = None
    project_id: Optional[UUID] = None  # Filter by specific project

    @field_validator("frequency_interval")
    @classmethod
    def validate_frequency_interval(cls, v: Optional[int]) -> Optional[int]:
        """Validate that frequency_interval is at least 1."""
        if v is not None and v < 1:
            raise ValueError("frequency_interval must be at least 1")
        return v

    @field_validator("to_date")
    @classmethod
    def validate_to_date(cls, v: Optional[datetime], info) -> Optional[datetime]:
        """Validate that to_date is after from_date and within reasonable range."""
        validate_date_range(info.data.get("from_date"), v)
        return v

    @field_validator("topk")
    @classmethod
    def validate_topk(cls, v: Optional[int]) -> Optional[int]:
        """Validate that topk is at least 1."""
        if v is not None and v < 1:
            raise ValueError("topk must be at least 1")
        return v

    @model_validator(mode="after")
    def validate_topk_with_group_by(self) -> "GatewayAnalyticsRequest":
        """Ensure topk is only used with group_by."""
        if self.topk is not None and not self.group_by:
            raise ValueError("topk requires group_by to be specified")
        return self


class GatewayMetricsData(BaseModel):
    """Container for gateway metrics data."""

    # Grouping dimensions (optional based on group_by)
    project_id: Optional[UUID] = None
    api_key_project_id: Optional[UUID] = None  # For user_project grouping
    country_code: Optional[str] = None
    city: Optional[str] = None
    device_type: Optional[str] = None
    browser_name: Optional[str] = None
    os_name: Optional[str] = None
    path: Optional[str] = None
    status_code: Optional[int] = None

    # Metrics data
    data: Dict[
        GatewayMetricType,
        Union[
            GatewayCountMetric,
            GatewayPerformanceMetric,
            GatewayDistributionMetric,
            GatewayRateMetric,
            GatewayBandwidthMetric,
        ],
    ]


class GatewayPeriodBin(BaseModel):
    """Time period bin containing metrics data."""

    time_period: datetime
    items: Optional[list[GatewayMetricsData]] = None


class GatewayAnalyticsResponse(ResponseBase):
    """Response model for gateway analytics."""

    object: str = "gateway_analytics"
    items: list[GatewayPeriodBin]
    summary: Optional[Dict[str, Any]] = None  # Overall summary statistics

    def to_http_response(
        self,
        include: Union[set[int], set[str], dict[int, Any], dict[str, Any], None] = None,
        exclude: Union[set[int], set[str], dict[int, Any], dict[str, Any], None] = None,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
    ) -> ORJSONResponse:
        """Convert the model instance to an HTTP response."""
        if getattr(self, "object", "") == "error":
            details = self.model_dump()
            status_code = details["code"]
        else:
            details = self.model_dump(
                mode="json",
                include=include,
                exclude=exclude,
                exclude_unset=exclude_unset,
                exclude_defaults=exclude_defaults,
                exclude_none=exclude_none,
            )
            status_code = self.code

        return ORJSONResponse(content=details, status_code=status_code)


class GatewayGeographicalStats(BaseModel):
    """Response model for geographical statistics."""

    object: str = "gateway_geographical_stats"
    total_requests: int
    unique_countries: int
    unique_cities: int
    countries: list[
        Dict[str, Any]
    ]  # [{"country_code": "US", "country_name": "United States", "count": 1000, "percent": 50.0}]
    cities: list[Dict[str, Any]]  # [{"city": "New York", "country_code": "US", "count": 500, "percent": 25.0}]
    heatmap_data: Optional[list[Dict[str, Any]]] = None  # For map visualization

    def to_http_response(self) -> ORJSONResponse:
        """Convert to HTTP response."""
        return ORJSONResponse(content=self.model_dump(mode="json", exclude_none=True), status_code=200)


class GatewayBlockingRuleStats(BaseModel):
    """Response model for blocking rule statistics."""

    object: str = "gateway_blocking_stats"
    total_blocked: int
    block_rate: float
    blocked_by_rule: Dict[str, int]  # {"ip_block": 100, "country_block": 50}
    blocked_by_reason: Dict[str, int]  # {"suspicious_activity": 75, "rate_limit": 75}
    top_blocked_ips: list[Dict[str, Any]]  # [{"ip": "1.2.3.4", "count": 50, "country": "CN"}]
    time_series: list[Dict[str, Any]]  # Blocked requests over time

    def to_http_response(self) -> ORJSONResponse:
        """Convert to HTTP response."""
        return ORJSONResponse(content=self.model_dump(mode="json", exclude_none=True), status_code=200)


# New Aggregated Metrics Schemas
class AggregatedMetricsRequest(BaseModel):
    """Request schema for aggregated metrics with server-side calculations."""

    from_date: datetime
    to_date: Optional[datetime] = None
    group_by: Optional[list[Literal["model", "project", "endpoint", "user", "user_project"]]] = None
    filters: Optional[Dict[str, Any]] = None  # e.g., {"project_id": ["uuid1", "uuid2"], "model_id": "uuid"}
    metrics: list[
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
        ]
    ]

    @field_validator("to_date")
    @classmethod
    def validate_to_date(cls, v: Optional[datetime], info) -> Optional[datetime]:
        """Validate that to_date is after from_date and within reasonable range."""
        validate_date_range(info.data.get("from_date"), v)
        return v


class AggregatedMetricValue(BaseModel):
    """Single aggregated metric value."""

    value: Union[int, float]
    formatted_value: Optional[str] = None  # Human readable format (e.g., "1.2K", "95.5%")
    unit: Optional[str] = None  # Unit of measurement (e.g., "ms", "%", "requests")


class AggregatedMetricsGroup(BaseModel):
    """Grouped aggregated metrics."""

    # Grouping dimensions
    model_id: Optional[UUID] = None
    model_name: Optional[str] = None
    project_id: Optional[UUID] = None
    project_name: Optional[str] = None
    endpoint_id: Optional[UUID] = None
    endpoint_name: Optional[str] = None
    user_id: Optional[str] = None
    api_key_project_id: Optional[UUID] = None  # For user_project grouping
    api_key_project_name: Optional[str] = None

    # Aggregated metrics
    metrics: Dict[str, AggregatedMetricValue]


class AggregatedMetricsResponse(ResponseBase):
    """Response schema for aggregated metrics."""

    object: str = "aggregated_metrics"
    groups: List[AggregatedMetricsGroup]
    summary: Dict[str, AggregatedMetricValue]  # Overall aggregated values
    total_groups: int
    date_range: Dict[str, datetime]  # {"from": datetime, "to": datetime}


class TimeSeriesRequest(BaseModel):
    """Request schema for time-series data."""

    from_date: datetime
    to_date: Optional[datetime] = None
    interval: Literal["1m", "5m", "15m", "30m", "1h", "6h", "12h", "1d", "1w"] = "1h"
    metrics: list[
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
        ]
    ]
    filters: Optional[Dict[str, Any]] = None
    group_by: Optional[list[Literal["model", "project", "endpoint", "user_project"]]] = None
    fill_gaps: bool = True

    @field_validator("to_date")
    @classmethod
    def validate_to_date(cls, v: Optional[datetime], info) -> Optional[datetime]:
        """Validate that to_date is after from_date and within reasonable range."""
        validate_date_range(info.data.get("from_date"), v)
        return v


class TimeSeriesPoint(BaseModel):
    """Single time series data point."""

    timestamp: datetime
    values: Dict[str, Optional[float]]  # metric_name -> value


class TimeSeriesGroup(BaseModel):
    """Time series data for a specific group."""

    # Grouping dimensions
    model_id: Optional[UUID] = None
    model_name: Optional[str] = None
    project_id: Optional[UUID] = None
    project_name: Optional[str] = None
    endpoint_id: Optional[UUID] = None
    endpoint_name: Optional[str] = None
    api_key_project_id: Optional[UUID] = None  # For user_project grouping
    api_key_project_name: Optional[str] = None

    # Time series data
    data_points: List[TimeSeriesPoint]


class TimeSeriesResponse(ResponseBase):
    """Response schema for time-series data."""

    object: str = "time_series"
    groups: List[TimeSeriesGroup]
    interval: str
    date_range: Dict[str, datetime]


class GeographicDataRequest(BaseModel):
    """Request schema for geographic distribution data."""

    from_date: datetime
    to_date: Optional[datetime] = None
    filters: Optional[Dict[str, Any]] = None
    group_by: Literal["country", "region", "city"] = "country"
    limit: int = 50

    @field_validator("to_date")
    @classmethod
    def validate_to_date(cls, v: Optional[datetime], info) -> Optional[datetime]:
        """Validate that to_date is after from_date and within reasonable range."""
        validate_date_range(info.data.get("from_date"), v)
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
    country_code: Optional[str] = None
    country_name: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # Metrics
    request_count: int
    success_rate: float
    avg_latency_ms: Optional[float] = None
    unique_users: Optional[int] = None
    percentage: float  # Percentage of total requests


class GeographicDataResponse(ResponseBase):
    """Response schema for geographic distribution data."""

    object: str = "geographic_data"
    locations: List[GeographicDataPoint]
    total_requests: int
    total_locations: int
    date_range: Dict[str, datetime]
    group_by: str


class LatencyDistributionRequest(BaseModel):
    """Request schema for latency distribution data."""

    from_date: datetime
    to_date: Optional[datetime] = None
    filters: Optional[Dict[str, Any]] = None
    group_by: Optional[list[Literal["model", "project", "endpoint", "user", "user_project"]]] = None
    buckets: Optional[List[Dict[str, Union[int, str]]]] = None

    @field_validator("to_date")
    @classmethod
    def validate_to_date(cls, v: Optional[datetime], info) -> Optional[datetime]:
        """Validate that to_date is after from_date and within reasonable range."""
        validate_date_range(info.data.get("from_date"), v)
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

    range: str  # e.g., "0-100ms"
    count: int
    percentage: float
    avg_latency: Optional[float] = None  # Average latency within this bucket


class LatencyDistributionGroup(BaseModel):
    """Latency distribution for a specific group."""

    # Grouping dimensions
    model_id: Optional[UUID] = None
    model_name: Optional[str] = None
    project_id: Optional[UUID] = None
    project_name: Optional[str] = None
    endpoint_id: Optional[UUID] = None
    endpoint_name: Optional[str] = None
    user_id: Optional[str] = None
    api_key_project_id: Optional[UUID] = None  # For user_project grouping
    api_key_project_name: Optional[str] = None

    # Distribution data
    buckets: List[LatencyDistributionBucket]
    total_requests: int


class LatencyDistributionResponse(ResponseBase):
    """Response schema for latency distribution data."""

    object: str = "latency_distribution"
    groups: List[LatencyDistributionGroup]
    overall_distribution: List[LatencyDistributionBucket]  # Aggregated across all groups
    total_requests: int
    date_range: Dict[str, datetime]
    bucket_definitions: List[Dict[str, Union[int, str]]]  # The bucket ranges used


# ============================================
# OTel Traces Schemas
# ============================================


class TraceResourceType(str, Enum):
    """Enum for trace resource types used in filtering."""

    PROMPT = "prompt"
    # Future resource types can be added here


class TraceEvent(BaseModel):
    """Schema for span events (otel_traces columns 16-18 combined)."""

    timestamp: datetime
    name: str
    attributes: Dict[str, str]


class TraceLink(BaseModel):
    """Schema for span links (otel_traces columns 19-22 combined)."""

    trace_id: str
    span_id: str
    trace_state: str
    attributes: Dict[str, str]


class TraceItem(BaseModel):
    """Schema for a single trace/span item with all 22 otel_traces columns."""

    timestamp: datetime
    trace_id: str
    span_id: str
    parent_span_id: str
    trace_state: str
    span_name: str
    span_kind: str
    service_name: str
    resource_attributes: Dict[str, str]
    scope_name: str
    scope_version: str
    span_attributes: Dict[str, str]
    duration: int  # nanoseconds
    status_code: str
    status_message: str
    events: List[TraceEvent]
    links: List[TraceLink]

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})


class TraceListResponse(ResponseBase):
    """Response schema for listing traces."""

    object: str = "trace_list"
    items: List[TraceItem]
    total_count: int
    offset: int
    limit: int
