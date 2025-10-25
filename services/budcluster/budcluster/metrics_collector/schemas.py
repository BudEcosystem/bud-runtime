"""Schemas for metrics collection."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MetricType(str, Enum):
    """Prometheus metric types."""

    GAUGE = "gauge"
    COUNTER = "counter"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"
    UNTYPED = "untyped"


class MetricSample(BaseModel):
    """A single metric sample."""

    timestamp: float = Field(..., description="Unix timestamp in seconds")
    value: float = Field(..., description="Metric value")


class Metric(BaseModel):
    """Prometheus metric with labels and samples."""

    name: str = Field(..., description="Metric name")
    labels: Dict[str, str] = Field(default_factory=dict, description="Metric labels")
    type: MetricType = Field(default=MetricType.UNTYPED, description="Metric type")
    samples: List[MetricSample] = Field(default_factory=list, description="Metric samples")


class PrometheusQueryResult(BaseModel):
    """Result from a Prometheus query."""

    status: str = Field(..., description="Query status")
    data: Dict[str, Any] = Field(..., description="Query result data")


class MetricsCollectionStatus(str, Enum):
    """Status of metrics collection for a cluster."""

    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SKIPPED = "skipped"


class ClusterMetricsInfo(BaseModel):
    """Information about metrics collection for a cluster."""

    cluster_id: str = Field(..., description="Cluster ID")
    cluster_name: str = Field(..., description="Cluster name")
    last_collection: Optional[datetime] = Field(None, description="Last successful collection time")
    status: MetricsCollectionStatus = Field(..., description="Collection status")
    error: Optional[str] = Field(None, description="Error message if failed")
    metrics_count: Optional[int] = Field(None, description="Number of metrics collected")


class MetricsCollectionResult(BaseModel):
    """Result of metrics collection from multiple clusters."""

    total_clusters: int = Field(..., description="Total number of clusters processed")
    successful: int = Field(..., description="Number of successful collections")
    failed: int = Field(..., description="Number of failed collections")
    skipped: int = Field(..., description="Number of skipped collections")
    clusters: List[ClusterMetricsInfo] = Field(default_factory=list, description="Per-cluster results")
    duration_seconds: float = Field(..., description="Total collection duration in seconds")
