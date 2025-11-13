"""Cluster metrics module for querying infrastructure metrics from ClickHouse.

This module provides a clean separation of concerns:
- routes.py: FastAPI endpoints (thin API layer)
- services.py: Business logic and result processing
- repository.py: ClickHouse data access layer
- schemas.py: Pydantic models for validation
"""

from .repository import ClusterMetricsRepository
from .routes import router
from .schemas import (
    ClusterHealthStatus,
    ClusterMetricsQuery,
    ClusterMetricsResponse,
    ClusterResourceSummary,
    GPUMetricsResponse,
    MetricsAggregationRequest,
    MetricsAggregationResponse,
    NodeMetricsResponse,
    PodMetricsResponse,
)
from .services import ClusterMetricsService


__all__ = [
    "router",
    "ClusterMetricsRepository",
    "ClusterMetricsService",
    "ClusterHealthStatus",
    "ClusterMetricsQuery",
    "ClusterMetricsResponse",
    "ClusterResourceSummary",
    "GPUMetricsResponse",
    "MetricsAggregationRequest",
    "MetricsAggregationResponse",
    "NodeMetricsResponse",
    "PodMetricsResponse",
]
