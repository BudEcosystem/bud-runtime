"""Service for collecting metrics from clusters and forwarding to OTel Collector."""

import asyncio
import inspect
import time
from datetime import datetime, timedelta
from typing import Optional

from budmicroframe.commons.logging import get_logger
from budmicroframe.shared.dapr_service import DaprServiceCrypto
from sqlalchemy.ext.asyncio import AsyncSession

from ..cluster_ops.crud import ClusterDataManager
from ..commons.config import app_settings
from ..commons.constants import ClusterStatusEnum
from ..commons.metrics_config import get_queries_for_cluster_type
from .otel_bridge import OTelBridge
from .schemas import (
    ClusterMetricsInfo,
    MetricsCollectionResult,
    MetricsCollectionStatus,
)


logger = get_logger(__name__)


class MetricsCollectionService:
    """Service for collecting metrics from clusters.

    Standard Prometheus queries are now defined in commons/metrics_config.py
    for easier customization and maintenance.
    """

    def __init__(self, session: AsyncSession):
        """Initialize metrics collection service.

        Args:
            session: Database session
        """
        self.session = session
        self.crypto = DaprServiceCrypto()

        # Initialize OTel bridge for metrics forwarding
        self.otel_bridge = OTelBridge(otel_endpoint=app_settings.otel_collector_endpoint)

    async def collect_all_clusters_metrics(self) -> MetricsCollectionResult:
        """Collect metrics from all active clusters.

        Returns:
            Collection result summary
        """
        start_time = time.time()

        # Check if metrics collection is enabled
        if not app_settings.metrics_collection_enabled:
            logger.info("Metrics collection is disabled globally")
            return MetricsCollectionResult(
                total_clusters=0, successful=0, failed=0, skipped=0, clusters=[], duration_seconds=0
            )

        # Get all available clusters
        cluster_manager = ClusterDataManager(self.session)
        clusters = await cluster_manager.get_all_clusters_by_status([ClusterStatusEnum.AVAILABLE])

        if not clusters:
            logger.info("No available clusters found")
            return MetricsCollectionResult(
                total_clusters=0,
                successful=0,
                failed=0,
                skipped=0,
                clusters=[],
                duration_seconds=time.time() - start_time,
            )

        logger.info(f"Starting metrics collection for {len(clusters)} clusters")

        # Collect metrics from each cluster in parallel
        tasks = []
        for cluster in clusters:
            # Pass only the cluster ID to avoid session issues
            tasks.append(self._collect_cluster_metrics_safe(str(cluster.id)))

        cluster_results = await asyncio.gather(*tasks)

        # Count results
        successful = sum(1 for r in cluster_results if r.status == MetricsCollectionStatus.SUCCESS)
        failed = sum(1 for r in cluster_results if r.status == MetricsCollectionStatus.FAILED)
        skipped = sum(1 for r in cluster_results if r.status == MetricsCollectionStatus.SKIPPED)

        duration = time.time() - start_time

        logger.info(
            f"Metrics collection completed: {successful}/{len(clusters)} successful, "
            f"{failed} failed, {skipped} skipped, duration: {duration:.2f}s"
        )

        return MetricsCollectionResult(
            total_clusters=len(clusters),
            successful=successful,
            failed=failed,
            skipped=skipped,
            clusters=cluster_results,
            duration_seconds=duration,
        )

    async def _collect_cluster_metrics_safe(self, cluster_id: str) -> ClusterMetricsInfo:
        """Safely collect metrics from a single cluster with exception handling.

        This is a wrapper method that provides fault isolation when collecting metrics
        from multiple clusters in parallel. It converts exceptions into result objects
        to prevent one cluster's failure from breaking the entire collection process.

        **Error Handling Pattern:**
        - Catches ALL exceptions from collect_cluster_metrics()
        - Returns ClusterMetricsInfo with status=FAILED instead of propagating exception
        - Logs the error for debugging
        - Allows parallel collection to continue for other clusters

        **When to use:**
        - Use this wrapper in collect_all_clusters_metrics() for parallel collection
        - Ensures resilience: one cluster failure doesn't affect others

        **When NOT to use:**
        - Don't use for single cluster operations where caller expects exceptions
        - Don't use when immediate failure feedback is needed

        **Contract:**
        - ALWAYS returns ClusterMetricsInfo (never raises)
        - Check status field to determine success/failure
        - error field contains exception message when status=FAILED

        Args:
            cluster_id: ID of the cluster

        Returns:
            ClusterMetricsInfo with status field indicating success or failure.
            Never raises exceptions - all errors converted to FAILED status.

        Example:
            >>> result = await service._collect_cluster_metrics_safe("cluster-123")
            >>> if result.status == MetricsCollectionStatus.FAILED:
            ...     print(f"Collection failed: {result.error}")
        """
        try:
            return await self.collect_cluster_metrics(cluster_id)
        except Exception as e:
            logger.error(
                f"Failed to collect metrics from cluster {cluster_id}: {e}",
                exc_info=True,  # Include stack trace in logs for debugging
            )
            return ClusterMetricsInfo(
                cluster_id=cluster_id,
                cluster_name="unknown",
                status=MetricsCollectionStatus.FAILED,
                error=str(e),
            )

    async def collect_cluster_metrics(self, cluster_id: str) -> ClusterMetricsInfo:
        """Configure OTel Collector to pull metrics from a cluster.

        Args:
            cluster_id: ID of the cluster

        Returns:
            Cluster metrics info with status
        """
        logger.info(f"Setting up metrics collection for cluster {cluster_id}")

        # Get cluster from database
        cluster_manager = ClusterDataManager(self.session)
        cluster = await cluster_manager.retrieve_cluster_by_fields({"id": cluster_id}, missing_ok=True)
        if not cluster:
            logger.error(f"Cluster {cluster_id} not found")
            return ClusterMetricsInfo(
                cluster_id=cluster_id,
                cluster_name="unknown",
                status=MetricsCollectionStatus.FAILED,
                error="Cluster not found",
            )

        # Skip if cluster is not active
        if cluster.status != ClusterStatusEnum.AVAILABLE:
            logger.info(f"Skipping cluster {cluster_id} with status {cluster.status}")
            return ClusterMetricsInfo(
                cluster_id=str(cluster.id),
                cluster_name=cluster.name if hasattr(cluster, "name") else str(cluster.id),
                status=MetricsCollectionStatus.SKIPPED,
                error=f"Cluster status is {cluster.status}",
            )

        try:
            # Decrypt kubeconfig
            kubeconfig = self.crypto.decrypt_data(cluster.configuration)

            # Setup OTel scraping for this cluster
            success, error_msg = await self.otel_bridge.setup_cluster_scraping(
                cluster_id=str(cluster.id),
                cluster_name=cluster.name if hasattr(cluster, "name") else str(cluster.id),
                cluster_platform=cluster.platform,
                kubeconfig=kubeconfig,
                prometheus_namespace=app_settings.prometheus_namespace,
                prometheus_service=app_settings.prometheus_service_name,
            )

            if not success:
                raise Exception(error_msg or "Failed to setup OTel scraping")

            # Get cluster-type-specific queries
            # Uses configuration from commons/metrics_config.py
            queries = get_queries_for_cluster_type(cluster.platform)
            logger.debug(f"Using {len(queries)} queries for cluster type '{cluster.platform}'")

            # Trigger initial scraping
            success, error_msg = await self.otel_bridge.scrape_and_forward_metrics(
                cluster_id=str(cluster.id),
                queries=queries,
                duration=timedelta(minutes=5),
                step="30s",
            )

            if not success:
                raise Exception(error_msg or "Failed to scrape and forward metrics")

            # Update cluster with collection status
            await self._update_cluster_metrics_status(cluster.id, MetricsCollectionStatus.SUCCESS, datetime.utcnow())

            logger.info(f"Successfully configured metrics collection for cluster {cluster_id}")

            return ClusterMetricsInfo(
                cluster_id=str(cluster.id),
                cluster_name=cluster.name if hasattr(cluster, "name") else str(cluster.id),
                status=MetricsCollectionStatus.SUCCESS,
                metrics_count=len(queries),  # Number of configured queries
                last_collection=datetime.utcnow(),
            )

        except Exception as e:
            logger.error(f"Failed to setup metrics collection for cluster {cluster_id}: {e}")

            # Clean up on failure
            await self.otel_bridge.cleanup_cluster(str(cluster.id))

            # Update cluster with failure status
            await self._update_cluster_metrics_status(
                cluster.id,
                MetricsCollectionStatus.FAILED,
                cluster.last_metrics_collection,  # Keep previous successful time
            )

            return ClusterMetricsInfo(
                cluster_id=str(cluster.id),
                cluster_name=cluster.name if hasattr(cluster, "name") else str(cluster.id),
                status=MetricsCollectionStatus.FAILED,
                error=str(e),
                last_collection=cluster.last_metrics_collection,
            )

    async def _update_cluster_metrics_status(
        self, cluster_id: str, status: MetricsCollectionStatus, last_collection: Optional[datetime]
    ) -> None:
        """Update cluster metrics collection status in database.

        IMPORTANT: Transaction Management
        ----------------------------------
        This method uses `session.flush()` to write changes to the database but does NOT commit.
        Callers MUST ensure this method is called within a proper transaction context that
        handles commit/rollback. In FastAPI endpoints, this is typically managed by:

        1. The session context manager (async with get_session() as session)
        2. Explicit commit in the endpoint after successful operations
        3. Rollback on exception via context manager cleanup

        WARNING: Calling this method outside a transaction context may result in:
        - Lost updates if the session is closed without commit
        - Uncommitted changes leaking to other operations
        - Database inconsistencies on errors

        Args:
            cluster_id: Cluster ID
            status: Collection status
            last_collection: Last successful collection timestamp

        Raises:
            No exceptions - errors are logged but not propagated to avoid breaking workflows
        """
        try:
            if not self.session:
                logger.warning(f"No session available to update metrics status for cluster {cluster_id}")
                return

            update_data = {"metrics_collection_status": status.value}
            if last_collection:
                update_data["last_metrics_collection"] = last_collection

            # Update cluster directly using SQLAlchemy
            cluster_manager = ClusterDataManager(self.session)
            cluster = await cluster_manager.retrieve_cluster_by_fields({"id": cluster_id}, missing_ok=True)
            if cluster:
                for key, value in update_data.items():
                    setattr(cluster, key, value)
                # Flush changes to database (commit handled by transaction context)
                # Handle both sync and async sessions safely
                flush_res = self.session.flush()
                if inspect.isawaitable(flush_res):
                    await flush_res
                logger.debug(f"Flushed metrics status update for cluster {cluster_id}: {status.value}")
            else:
                logger.warning(f"Cluster {cluster_id} not found when updating metrics status")
        except Exception as e:
            logger.error(f"Failed to update cluster metrics status for {cluster_id}: {e}")
            # Rollback is handled by the session context manager
            # Re-raising here would break workflow execution, so we log and continue
