from datetime import datetime
from typing import Any, Dict, Literal, Optional, Union
from uuid import UUID
import ipaddress

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
    data: dict[
        MetricType, Union[CountMetric, TimeMetric, PerformanceMetric, CacheMetric]
    ]


class PeriodBin(BaseModel):
    time_period: datetime
    items: Optional[list[MetricsData]]


class ObservabilityMetricsRequest(BaseModel):
    metrics: list[MetricType]
    from_date: datetime
    to_date: Optional[datetime] = None
    frequency_unit: Literal["hour", "day", "week", "month", "quarter", "year"] = "day"
    frequency_interval: Optional[int] = None
    filters: Optional[
        dict[Literal["model", "project", "endpoint"], Union[list[UUID], UUID]]
    ] = None
    group_by: Optional[list[Literal["model", "project", "endpoint"]]] = None
    return_delta: bool = True
    fill_time_gaps: bool = True
    topk: Optional[int] = None

    @field_validator("frequency_interval")
    @classmethod
    def validate_frequency_interval(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 1:
            raise ValueError("frequency_interval must be at least 1")
        return v

    @field_validator("to_date")
    @classmethod
    def validate_to_date(cls, v: Optional[datetime], info) -> Optional[datetime]:
        if v is None:
            return v
        from_date = info.data.get("from_date")
        if from_date and v < from_date:
            raise ValueError("to_date must be after from_date")
        return v

    @field_validator("filters")
    @classmethod
    def validate_filters(cls, v: Optional[dict]) -> Optional[dict]:
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
                raise ValueError(
                    "topk is ignored when filters are specified and should not be used together"
                )
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

    @field_validator("request_ip")
    @classmethod
    def validate_ip(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        try:
            # Validate IPv4 address format
            ipaddress.IPv4Address(v)
            return v
        except ipaddress.AddressValueError:
            raise ValueError(f"Invalid IPv4 address: {v}")

    @field_validator("cost")
    @classmethod
    def validate_cost(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v < 0:
            raise ValueError("Cost cannot be negative")
        return v

    @model_validator(mode="after")
    def validate_timestamps(self) -> "InferenceDetailsMetrics":
        """Ensure request_forward_time is not before request_arrival_time."""
        if self.request_forward_time < self.request_arrival_time:
            raise ValueError(
                "request_forward_time cannot be before request_arrival_time"
            )
        return self
