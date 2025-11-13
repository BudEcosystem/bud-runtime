"""Routes for metrics collection operations."""

from budmicroframe.commons.logging import get_logger
from budmicroframe.commons.schemas import ErrorResponse, SuccessResponse
from fastapi import APIRouter

from ..commons.dependencies import get_session
from .metrics_service import MetricsCollectionService


logger = get_logger(__name__)

# Create router for metrics collection
metrics_router = APIRouter(prefix="/metrics", tags=["Metrics Collection"])


@metrics_router.post("/collect-all-cluster-metrics")
async def collect_all_cluster_metrics():
    """Periodic job to collect metrics from all clusters and forward to OTel Collector.

    This endpoint is triggered by the Dapr cron binding configured
    to run every 5 minutes (configurable via environment).

    Returns:
        Metrics collection result summary
    """
    try:
        logger.info("Starting periodic metrics collection")

        # Create metrics service
        async for session in get_session():
            service = MetricsCollectionService(session)

            # Collect metrics from all clusters
            result = await service.collect_all_clusters_metrics()

            logger.info(
                f"Metrics collection completed: {result.successful}/{result.total_clusters} successful, "
                f"duration: {result.duration_seconds:.2f}s"
            )

            # Return simple success response
            return SuccessResponse(
                message=f"Metrics collection completed: {result.successful}/{result.total_clusters} successful, {result.failed} failed, {result.skipped} skipped",
                code=200,
            ).to_http_response()

    except Exception as e:
        logger.exception("Error in metrics collection job: %s", str(e))
        return ErrorResponse(
            code=500,
            message=f"Failed to collect metrics: {str(e)}",
        ).to_http_response()
