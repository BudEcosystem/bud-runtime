import ipaddress
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union
from uuid import UUID

from budmicroframe.commons.schemas import CloudEventBase, ResponseBase
from fastapi.responses import ORJSONResponse
from pydantic import BaseModel, field_validator, model_validator


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
    group_by: Optional[list[Literal["model", "project", "endpoint"]]] = None
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
        """Validate that to_date is after from_date."""
        if v is None:
            return v
        from_date = info.data.get("from_date")
        if from_date and v < from_date:
            raise ValueError("to_date must be after from_date")
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
        """Validate that to_date is after from_date."""
        if v is None:
            return v
        from_date = info.data.get("from_date")
        if from_date and v < from_date:
            raise ValueError("to_date must be after from_date")
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
    endpoint_id: Optional[UUID] = None
    model_id: Optional[UUID] = None
    endpoint_type: str = "chat"  # New field to identify inference type


class InferenceListResponse(ResponseBase):
    """Response schema for listing inference requests."""

    object: str = "inference_list"
    items: List[InferenceListItem]
    total_count: int
    offset: int
    limit: int
    has_more: bool


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
    endpoint_id: UUID

    # Status
    is_success: bool
    cached: bool
    finish_reason: Optional[str] = None
    cost: Optional[float] = None

    # Raw data (optional)
    raw_request: Optional[str] = None
    raw_response: Optional[str] = None
    gateway_request: Optional[str] = None
    gateway_response: Optional[str] = None

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
