"""Routes for cluster metrics queries.

This module provides FastAPI routes for accessing cluster metrics.
Routes are kept thin, delegating to the service layer for business logic.
"""

from datetime import datetime, timedelta
from typing import Optional

from budmicroframe.commons.logging import get_logger
from fastapi import APIRouter, Depends, HTTPException, Query
from starlette.status import HTTP_404_NOT_FOUND, HTTP_500_INTERNAL_SERVER_ERROR

from ..observability.models import ClickHouseClient, ClickHouseConfig
from .repository import ClusterMetricsRepository
from .schemas import (
    ClusterGPUMetricsResponse,
    ClusterHealthStatus,
    ClusterMetricsQuery,
    ClusterMetricsResponse,
    ClusterResourceSummary,
    GPUMetricsResponse,
    GPUTimeSeriesResponse,
    MetricsAggregationRequest,
    MetricsAggregationResponse,
    NodeEventDetail,
    NodeEventsCountResponse,
    NodeEventsListResponse,
    NodeEventsStoreRequest,
    NodeGPUMetricsResponse,
    NodeMetricsResponse,
    PodMetricsResponse,
    PrometheusCompatibleMetricsResponse,
)
from .services import ClusterMetricsService


logger = get_logger(__name__)
router = APIRouter(prefix="/cluster-metrics", tags=["Cluster Metrics"])


async def get_cluster_metrics_service() -> ClusterMetricsService:
    """Dependency injection for cluster metrics service.

    Creates and initializes the service layer with repository and ClickHouse client.
    Ensures proper cleanup of resources after request completion.

    Yields:
        ClusterMetricsService: Initialized service instance

    Note:
        This is a FastAPI dependency that handles the lifecycle of the
        ClickHouse client and ensures proper resource cleanup.
    """
    config = ClickHouseConfig()
    client = ClickHouseClient(config)
    await client.initialize()
    repository = ClusterMetricsRepository(client)
    service = ClusterMetricsService(repository)
    try:
        yield service
    finally:
        await client.close()


@router.get("/{cluster_id}/summary", response_model=ClusterResourceSummary)
async def get_cluster_summary(
    cluster_id: str,
    from_time: Optional[datetime] = Query(default=None),
    to_time: Optional[datetime] = Query(default=None),
    service: ClusterMetricsService = Depends(get_cluster_metrics_service),
) -> ClusterResourceSummary:
    """Get cluster resource utilization summary.

    Args:
        cluster_id: Cluster identifier
        from_time: Start time for metrics window (defaults to 1 hour ago)
        to_time: End time for metrics window (defaults to now)
        service: Injected cluster metrics service

    Returns:
        ClusterResourceSummary with aggregated cluster metrics

    Raises:
        HTTPException: 404 if cluster not found, 500 on server error
    """
    try:
        # Default time range: last hour
        if not from_time:
            from_time = datetime.utcnow() - timedelta(hours=1)
        if not to_time:
            to_time = datetime.utcnow()

        return await service.get_cluster_summary(cluster_id, from_time, to_time)

    except ValueError as e:
        # No metrics found for cluster
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from None
    except Exception as e:
        logger.error(f"Error getting cluster summary: {e}")
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve cluster metrics: {str(e)}",
        ) from e


@router.get("/{cluster_id}/nodes", response_model=NodeMetricsResponse)
async def get_node_metrics(
    cluster_id: str,
    from_time: Optional[datetime] = Query(default=None),
    to_time: Optional[datetime] = Query(default=None),
    service: ClusterMetricsService = Depends(get_cluster_metrics_service),
) -> NodeMetricsResponse:
    """Get node-level metrics for a cluster.

    Args:
        cluster_id: Cluster identifier
        from_time: Start time for metrics window (defaults to 1 hour ago)
        to_time: End time for metrics window (defaults to now)
        service: Injected cluster metrics service

    Returns:
        NodeMetricsResponse with node metrics and network time series

    Raises:
        HTTPException: 500 on server error
    """
    try:
        # Default time range: last hour
        if not from_time:
            from_time = datetime.utcnow() - timedelta(hours=1)
        if not to_time:
            to_time = datetime.utcnow()

        return await service.get_node_metrics(cluster_id, from_time, to_time)

    except Exception as e:
        logger.error(f"Error getting node metrics: {e}")
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve node metrics: {str(e)}",
        ) from e


@router.get("/{cluster_id}/pods", response_model=PodMetricsResponse)
async def get_pod_metrics(
    cluster_id: str,
    namespace: Optional[str] = Query(default=None),
    from_time: Optional[datetime] = Query(default=None),
    to_time: Optional[datetime] = Query(default=None),
    limit: int = Query(default=100, le=1000),
    service: ClusterMetricsService = Depends(get_cluster_metrics_service),
) -> PodMetricsResponse:
    """Get pod-level metrics for a cluster.

    Args:
        cluster_id: Cluster identifier
        namespace: Optional namespace filter
        from_time: Start time for metrics window (defaults to 1 hour ago)
        to_time: End time for metrics window (defaults to now)
        limit: Maximum number of pods to return (max 1000)
        service: Injected cluster metrics service

    Returns:
        PodMetricsResponse with pod metrics

    Raises:
        HTTPException: 500 on server error
    """
    try:
        # Default time range: last hour
        if not from_time:
            from_time = datetime.utcnow() - timedelta(hours=1)
        if not to_time:
            to_time = datetime.utcnow()

        return await service.get_pod_metrics(cluster_id, from_time, to_time, namespace, limit)

    except Exception as e:
        logger.error(f"Error getting pod metrics: {e}")
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve pod metrics: {str(e)}",
        ) from e


@router.get("/{cluster_id}/gpus", response_model=GPUMetricsResponse)
async def get_gpu_metrics(
    cluster_id: str,
    from_time: Optional[datetime] = Query(default=None),
    to_time: Optional[datetime] = Query(default=None),
    service: ClusterMetricsService = Depends(get_cluster_metrics_service),
) -> GPUMetricsResponse:
    """Get GPU metrics for a cluster.

    Args:
        cluster_id: Cluster identifier
        from_time: Start time for metrics window (defaults to 1 hour ago)
        to_time: End time for metrics window (defaults to now)
        service: Injected cluster metrics service

    Returns:
        GPUMetricsResponse with GPU metrics

    Raises:
        HTTPException: 500 on server error
    """
    try:
        # Default time range: last hour
        if not from_time:
            from_time = datetime.utcnow() - timedelta(hours=1)
        if not to_time:
            to_time = datetime.utcnow()

        return await service.get_gpu_metrics(cluster_id, from_time, to_time)

    except Exception as e:
        logger.error(f"Error getting GPU metrics: {e}")
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve GPU metrics: {str(e)}",
        ) from e


@router.post("/query", response_model=ClusterMetricsResponse)
async def query_cluster_metrics(
    request: ClusterMetricsQuery,
    service: ClusterMetricsService = Depends(get_cluster_metrics_service),
) -> ClusterMetricsResponse:
    """Execute custom metrics query for a cluster.

    Args:
        request: Query parameters including cluster_id, time range, metrics, and aggregation
        service: Injected cluster metrics service

    Returns:
        ClusterMetricsResponse with time-series metrics

    Raises:
        HTTPException: 500 on server error
    """
    try:
        return await service.query_metrics(request)

    except Exception as e:
        logger.error(f"Error querying cluster metrics: {e}")
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query metrics: {str(e)}",
        ) from e


@router.post("/aggregate", response_model=MetricsAggregationResponse)
async def aggregate_metrics(
    request: MetricsAggregationRequest,
    service: ClusterMetricsService = Depends(get_cluster_metrics_service),
) -> MetricsAggregationResponse:
    """Perform custom aggregation on cluster metrics.

    Args:
        request: Aggregation parameters including cluster_ids, metrics, and grouping
        service: Injected cluster metrics service

    Returns:
        MetricsAggregationResponse with aggregated results and execution time

    Raises:
        HTTPException: 500 on server error
    """
    try:
        return await service.aggregate_metrics(request)

    except Exception as e:
        logger.error(f"Error aggregating metrics: {e}")
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to aggregate metrics: {str(e)}",
        ) from e


@router.get("/{cluster_id}/health", response_model=ClusterHealthStatus)
async def get_cluster_health(
    cluster_id: str,
    service: ClusterMetricsService = Depends(get_cluster_metrics_service),
) -> ClusterHealthStatus:
    """Get health status of a cluster based on metrics analysis.

    Args:
        cluster_id: Cluster identifier
        service: Injected cluster metrics service

    Returns:
        ClusterHealthStatus with health analysis, issues, and recommendations

    Raises:
        HTTPException: 404 if cluster not found, 500 on server error
    """
    try:
        return await service.get_cluster_health(cluster_id)

    except ValueError as e:
        # No metrics found for cluster
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from None
    except Exception as e:
        logger.error(f"Error getting cluster health: {e}")
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to assess cluster health: {str(e)}",
        ) from e


@router.get("/{cluster_id}/prometheus-compatible", response_model=PrometheusCompatibleMetricsResponse)
async def get_prometheus_compatible_metrics(
    cluster_id: str,
    filter: str = Query("today", regex="^(today|7days|month)$"),
    metric_type: str = Query("all", regex="^(all|cpu|memory|disk|network|network_bandwidth|gpu|hpu)$"),
    service: ClusterMetricsService = Depends(get_cluster_metrics_service),
) -> PrometheusCompatibleMetricsResponse:
    """Get cluster metrics in Prometheus-compatible format for BudApp.

    This endpoint returns metrics in the same format as the original Prometheus-based
    implementation, allowing BudApp to switch seamlessly between data sources.

    NOTE: This implementation properly handles Prometheus counter metrics (CPU, network)
    by calculating rates, and gauge metrics (memory, disk) by averaging values.

    Args:
        cluster_id: Cluster identifier
        filter: Time range filter (today, 7days, month)
        metric_type: Type of metrics to return (all, cpu, memory, disk, network, etc.)
        service: Injected cluster metrics service

    Returns:
        PrometheusCompatibleMetricsResponse with metrics in Prometheus format

    Raises:
        HTTPException: 500 on server error

    Note:
        The Prometheus-compatible endpoint implementation is simplified in the service layer.
        For full implementation with detailed metric processing, see the original routes.py
        file in version control history.
    """
    try:
        return await service.get_prometheus_compatible_metrics(cluster_id, filter, metric_type)

    except Exception as e:
        logger.error(f"Error getting Prometheus-compatible metrics: {e}")
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve metrics: {str(e)}",
        ) from e


# Node Events endpoints


@router.post("/events/store")
async def store_node_events(
    request: NodeEventsStoreRequest,
    service: ClusterMetricsService = Depends(get_cluster_metrics_service),
):
    """Store node events from budcluster.

    This endpoint receives node events collected from Kubernetes clusters
    and stores them in ClickHouse for later querying.

    Args:
        request: Request body containing cluster_id and events list
        service: Injected cluster metrics service

    Returns:
        Dict with stored count

    Raises:
        HTTPException: 500 on server error
    """
    try:
        events_dict = [event.model_dump() for event in request.events]
        count = await service.store_node_events(request.cluster_id, events_dict)

        return {"status": "success", "stored_count": count}

    except Exception as e:
        logger.error(f"Error storing node events: {e}")
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store node events: {str(e)}",
        ) from e


@router.get("/{cluster_id}/node-events-count", response_model=NodeEventsCountResponse)
async def get_node_events_count(
    cluster_id: str,
    from_time: Optional[datetime] = Query(default=None),
    to_time: Optional[datetime] = Query(default=None),
    service: ClusterMetricsService = Depends(get_cluster_metrics_service),
) -> NodeEventsCountResponse:
    """Get event counts per node for a cluster.

    Args:
        cluster_id: Cluster identifier
        from_time: Start time (defaults to 24 hours ago)
        to_time: End time (defaults to now)
        service: Injected cluster metrics service

    Returns:
        Dict mapping node names to event counts

    Raises:
        HTTPException: 500 on server error
    """
    try:
        # Handle default time range here to ensure response reflects the actual query window
        effective_to_time = to_time or datetime.utcnow()
        effective_from_time = from_time or (effective_to_time - timedelta(hours=24))

        events_count = await service.get_node_events_count(cluster_id, effective_from_time, effective_to_time)

        return NodeEventsCountResponse(
            cluster_id=cluster_id,
            events_count=events_count,
            from_time=effective_from_time,
            to_time=effective_to_time,
        )

    except Exception as e:
        logger.error(f"Error getting node events count: {e}")
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve node events count: {str(e)}",
        ) from e


@router.get("/{cluster_id}/node-events/{node_name}", response_model=NodeEventsListResponse)
async def get_node_events(
    cluster_id: str,
    node_name: str,
    from_time: Optional[datetime] = Query(default=None),
    to_time: Optional[datetime] = Query(default=None),
    limit: int = Query(default=100, le=1000),
    service: ClusterMetricsService = Depends(get_cluster_metrics_service),
) -> NodeEventsListResponse:
    """Get events for a specific node.

    Args:
        cluster_id: Cluster identifier
        node_name: Node hostname
        from_time: Start time (defaults to 24 hours ago)
        to_time: End time (defaults to now)
        limit: Maximum events to return
        service: Injected cluster metrics service

    Returns:
        List of node events

    Raises:
        HTTPException: 500 on server error
    """
    try:
        # Handle default time range here to ensure response reflects the actual query window
        effective_to_time = to_time or datetime.utcnow()
        effective_from_time = from_time or (effective_to_time - timedelta(hours=24))

        events = await service.get_node_events(cluster_id, node_name, effective_from_time, effective_to_time, limit)

        # Convert dict events to NodeEventDetail models
        event_details = [NodeEventDetail(**event) for event in events]

        return NodeEventsListResponse(
            cluster_id=cluster_id,
            node_name=node_name,
            events=event_details,
            total_events=len(event_details),
            from_time=effective_from_time,
            to_time=effective_to_time,
        )

    except Exception as e:
        logger.error(f"Error getting node events: {e}")
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve node events: {str(e)}",
        ) from e


# ============ HAMI GPU Metrics endpoints ============


@router.get("/{cluster_id}/hami-gpu", response_model=ClusterGPUMetricsResponse)
async def get_cluster_hami_gpu_metrics(
    cluster_id: str,
    service: ClusterMetricsService = Depends(get_cluster_metrics_service),
) -> ClusterGPUMetricsResponse:
    """Get cluster-wide HAMI GPU metrics.

    Returns GPU device metrics and slice allocations for all nodes in the cluster.
    Includes summary statistics for the entire cluster.

    Args:
        cluster_id: Cluster identifier
        service: Injected cluster metrics service

    Returns:
        ClusterGPUMetricsResponse with devices, slices, and summary

    Raises:
        HTTPException: 500 on server error
    """
    try:
        return await service.get_cluster_hami_gpu_metrics(cluster_id)

    except Exception as e:
        logger.error(f"Error getting cluster HAMI GPU metrics: {e}")
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve cluster GPU metrics: {str(e)}",
        ) from e


@router.get("/{cluster_id}/nodes/{hostname}/hami-gpu", response_model=NodeGPUMetricsResponse)
async def get_node_hami_gpu_metrics(
    cluster_id: str,
    hostname: str,
    service: ClusterMetricsService = Depends(get_cluster_metrics_service),
) -> NodeGPUMetricsResponse:
    """Get HAMI GPU metrics for a specific node.

    Returns GPU device metrics and slice allocations for the specified node.
    Includes summary statistics for the node.

    Args:
        cluster_id: Cluster identifier
        hostname: Node hostname
        service: Injected cluster metrics service

    Returns:
        NodeGPUMetricsResponse with devices, slices, and summary

    Raises:
        HTTPException: 500 on server error
    """
    try:
        return await service.get_node_hami_gpu_metrics(cluster_id, hostname)

    except Exception as e:
        logger.error(f"Error getting node HAMI GPU metrics: {e}")
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve node GPU metrics: {str(e)}",
        ) from e


@router.get("/{cluster_id}/nodes/{hostname}/hami-gpu/timeseries", response_model=GPUTimeSeriesResponse)
async def get_node_gpu_timeseries(
    cluster_id: str,
    hostname: str,
    hours: int = Query(default=6, ge=1, le=168),
    service: ClusterMetricsService = Depends(get_cluster_metrics_service),
) -> GPUTimeSeriesResponse:
    """Get GPU timeseries data for a specific node.

    Returns historical GPU metrics for charts including utilization,
    memory, temperature, power, and slice activity.

    Args:
        cluster_id: Cluster identifier
        hostname: Node hostname
        hours: Number of hours to look back (1-168, default 6)
        service: Injected cluster metrics service

    Returns:
        GPUTimeSeriesResponse with timeseries arrays for charts

    Raises:
        HTTPException: 500 on server error
    """
    try:
        return await service.get_node_gpu_timeseries(cluster_id, hostname, hours)

    except Exception as e:
        logger.error(f"Error getting node GPU timeseries: {e}")
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve GPU timeseries: {str(e)}",
        ) from e
