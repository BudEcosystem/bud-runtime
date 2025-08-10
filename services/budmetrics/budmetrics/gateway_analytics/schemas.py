"""Gateway Analytics Schemas for budmetrics service."""

from datetime import datetime
from typing import Any, Dict, Literal, Optional, Union
from uuid import UUID

from budmicroframe.commons.schemas import ResponseBase
from fastapi.responses import ORJSONResponse
from pydantic import BaseModel, field_validator, model_validator


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
        list[Literal["project", "country", "city", "device_type", "browser", "os", "path", "status_code"]]
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
        """Validate that to_date is after from_date."""
        if v is None:
            return v
        from_date = info.data.get("from_date")
        if from_date and v < from_date:
            raise ValueError("to_date must be after from_date")
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
