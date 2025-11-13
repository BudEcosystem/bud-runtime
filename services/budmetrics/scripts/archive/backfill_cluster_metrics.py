#!/usr/bin/env python3
"""Backfill historical cluster metrics data from otel_metrics_gauge to NodeMetrics, PodMetrics, and ClusterMetrics tables.

This script should be run after executing fix_cluster_metrics_materialized_views.sql
to populate tables with historical data that arrived before the materialized views were created.

Usage:
    # Backfill all clusters
    python backfill_cluster_metrics.py

    # Backfill specific cluster
    python backfill_cluster_metrics.py --cluster-id f48bae4c-3b3a-490f-bc58-ec856c3e3b97

    # Backfill specific time range
    python backfill_cluster_metrics.py --from-date "2025-10-20" --to-date "2025-10-21"

    # Dry run (show what would be done without making changes)
    python backfill_cluster_metrics.py --dry-run
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path


# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from budmicroframe.commons import logging

from budmetrics.observability.models import ClickHouseClient, ClickHouseConfig


logger = logging.get_logger(__name__)


def get_clickhouse_config() -> ClickHouseConfig:
    """Get ClickHouse configuration from environment variables."""
    required_vars = [
        "CLICKHOUSE_HOST",
        "CLICKHOUSE_PORT",
        "CLICKHOUSE_DB_NAME",
        "SECRETS_CLICKHOUSE_USER",
        "SECRETS_CLICKHOUSE_PASSWORD",
    ]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

    logger.info(
        f"Connecting to ClickHouse at {os.getenv('CLICKHOUSE_HOST')}:{os.getenv('CLICKHOUSE_PORT')} "
        f"as user {os.getenv('SECRETS_CLICKHOUSE_USER')}"
    )

    return ClickHouseConfig(
        host=os.getenv("CLICKHOUSE_HOST"),
        port=int(os.getenv("CLICKHOUSE_PORT")),
        database=os.getenv("CLICKHOUSE_DB_NAME"),
        user=os.getenv("SECRETS_CLICKHOUSE_USER"),
        password=os.getenv("SECRETS_CLICKHOUSE_PASSWORD"),
    )


class ClusterMetricsBackfill:
    """Backfill historical cluster metrics from otel_metrics_gauge to structured tables."""

    def __init__(
        self,
        cluster_id: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        dry_run: bool = False,
    ):
        """Initialize the backfill process.

        Args:
            cluster_id: Optional cluster ID to backfill (if None, backfills all clusters)
            from_date: Start date for backfill (YYYY-MM-DD format)
            to_date: End date for backfill (YYYY-MM-DD format)
            dry_run: If True, show what would be done without making changes
        """
        self.cluster_id = cluster_id
        self.from_date = from_date
        self.to_date = to_date
        self.dry_run = dry_run
        self.config = get_clickhouse_config()
        self.client = ClickHouseClient(self.config)

    async def initialize(self):
        """Initialize the ClickHouse client."""
        await self.client.initialize()
        logger.info("ClickHouse client initialized")

    async def check_prerequisites(self):
        """Check if required tables and views exist."""
        logger.info("Checking prerequisites...")

        # Check if otel_metrics_gauge exists
        result = await self.client.execute_query("EXISTS TABLE otel_metrics_gauge")
        if not result or not result[0][0]:
            raise Exception("otel_metrics_gauge table does not exist. No data to backfill.")

        # Check if target tables exist
        for table in ["NodeMetrics", "PodMetrics", "ClusterMetrics"]:
            result = await self.client.execute_query(f"EXISTS TABLE {table}")
            if not result or not result[0][0]:
                raise Exception(f"{table} table does not exist. Run fix_cluster_metrics_materialized_views.sql first.")

        # Check if materialized views exist
        mv_query = """
        SELECT name FROM system.tables
        WHERE database = currentDatabase()
        AND engine = 'MaterializedView'
        AND name LIKE 'mv_populate_%'
        """
        mvs = await self.client.execute_query(mv_query)
        if not mvs:
            logger.warning(
                "No materialized views found. Run fix_cluster_metrics_materialized_views.sql to create them."
            )

        logger.info("✓ Prerequisites check passed")

    async def get_data_info(self):
        """Get information about available data to backfill."""
        logger.info("Analyzing data to backfill...")

        where_clause = "WHERE ResourceAttributes['cluster_id'] IS NOT NULL"
        if self.cluster_id:
            where_clause += f" AND ResourceAttributes['cluster_id'] = '{self.cluster_id}'"
        if self.from_date:
            where_clause += f" AND TimeUnix >= toDateTime('{self.from_date}')"
        if self.to_date:
            where_clause += f" AND TimeUnix < toDateTime('{self.to_date}')"

        # Get count and time range
        query = f"""
        SELECT
            count(*) as total_metrics,
            count(DISTINCT ResourceAttributes['cluster_id']) as cluster_count,
            min(TimeUnix) as earliest,
            max(TimeUnix) as latest
        FROM otel_metrics_gauge
        {where_clause}
        """

        result = await self.client.execute_query(query)
        if result and result[0][0] > 0:
            total, clusters, earliest, latest = result[0]
            logger.info(f"Found {total:,} metrics from {clusters} cluster(s)")
            logger.info(f"Time range: {earliest} to {latest}")
            return total
        else:
            logger.warning("No data found matching the criteria")
            return 0

    async def backfill_node_metrics(self):
        """Backfill NodeMetrics table from otel_metrics_gauge."""
        logger.info("Backfilling NodeMetrics table...")

        where_clause = "WHERE ResourceAttributes['cluster_id'] IS NOT NULL AND ResourceAttributes['cluster_id'] != ''"
        if self.cluster_id:
            where_clause += f" AND ResourceAttributes['cluster_id'] = '{self.cluster_id}'"
        if self.from_date:
            where_clause += f" AND TimeUnix >= toDateTime('{self.from_date}')"
        if self.to_date:
            where_clause += f" AND TimeUnix < toDateTime('{self.to_date}')"

        # Insert using the same aggregation logic as the materialized view
        query = f"""
        INSERT INTO NodeMetrics
        SELECT
            toStartOfInterval(TimeUnix, INTERVAL 1 MINUTE) AS ts,
            ResourceAttributes['cluster_id'] AS cluster_id,
            anyLast(ResourceAttributes['cluster_name']) AS cluster_name,
            splitByChar(':', Attributes['instance'])[1] AS node_name,

            -- CPU metrics
            countDistinctIf(Attributes['cpu'], MetricName = 'node_cpu_seconds_total') AS cpu_cores,
            100 - (avgIf(Value, MetricName = 'node_cpu_seconds_total' AND Attributes['mode'] = 'idle') * 100 /
                   nullIf(sumIf(Value, MetricName = 'node_cpu_seconds_total'), 0) * 100) AS cpu_usage_percent,

            -- Memory metrics
            maxIf(Value, MetricName = 'node_memory_MemTotal_bytes') AS memory_total_bytes,
            (maxIf(Value, MetricName = 'node_memory_MemTotal_bytes') -
             maxIf(Value, MetricName = 'node_memory_MemAvailable_bytes')) AS memory_used_bytes,
            ((maxIf(Value, MetricName = 'node_memory_MemTotal_bytes') -
              maxIf(Value, MetricName = 'node_memory_MemAvailable_bytes')) /
             nullIf(maxIf(Value, MetricName = 'node_memory_MemTotal_bytes'), 0)) * 100 AS memory_usage_percent,

            -- Disk metrics
            sumIf(Value, MetricName = 'node_filesystem_size_bytes' AND
                  Attributes['fstype'] NOT IN ('tmpfs', 'devtmpfs', 'overlay')) AS disk_total_bytes,
            (sumIf(Value, MetricName = 'node_filesystem_size_bytes' AND
                   Attributes['fstype'] NOT IN ('tmpfs', 'devtmpfs', 'overlay')) -
             sumIf(Value, MetricName = 'node_filesystem_avail_bytes' AND
                   Attributes['fstype'] NOT IN ('tmpfs', 'devtmpfs', 'overlay'))) AS disk_used_bytes,
            ((sumIf(Value, MetricName = 'node_filesystem_size_bytes' AND
                    Attributes['fstype'] NOT IN ('tmpfs', 'devtmpfs', 'overlay')) -
              sumIf(Value, MetricName = 'node_filesystem_avail_bytes' AND
                    Attributes['fstype'] NOT IN ('tmpfs', 'devtmpfs', 'overlay'))) /
             nullIf(sumIf(Value, MetricName = 'node_filesystem_size_bytes' AND
                          Attributes['fstype'] NOT IN ('tmpfs', 'devtmpfs', 'overlay')), 0)) * 100 AS disk_usage_percent,

            -- Load averages
            avgIf(Value, MetricName = 'node_load1') AS load_1,
            avgIf(Value, MetricName = 'node_load5') AS load_5,
            avgIf(Value, MetricName = 'node_load15') AS load_15

        FROM otel_metrics_gauge
        {where_clause}
        AND MetricName IN (
            'node_cpu_seconds_total',
            'node_memory_MemTotal_bytes',
            'node_memory_MemAvailable_bytes',
            'node_filesystem_size_bytes',
            'node_filesystem_avail_bytes',
            'node_load1',
            'node_load5',
            'node_load15'
        )
        AND Attributes['instance'] IS NOT NULL
        AND Attributes['instance'] != ''
        GROUP BY
            toStartOfInterval(TimeUnix, INTERVAL 1 MINUTE),
            ResourceAttributes['cluster_id'],
            splitByChar(':', Attributes['instance'])[1]
        """

        if self.dry_run:
            logger.info("[DRY RUN] Would execute NodeMetrics backfill")
            # Show sample of what would be inserted
            sample_query = query.replace("INSERT INTO NodeMetrics", "").strip() + " LIMIT 5"
            result = await self.client.execute_query(sample_query)
            if result:
                logger.info(f"Sample data (showing {len(result)} rows):")
                for row in result:
                    logger.info(f"  {row}")
        else:
            await self.client.execute_query(query)
            # Get count of inserted rows
            count_query = (
                f"SELECT count(*) FROM NodeMetrics {where_clause.replace('otel_metrics_gauge', 'NodeMetrics')}"
            )
            result = await self.client.execute_query(count_query)
            count = result[0][0] if result else 0
            logger.info(f"✓ Backfilled {count:,} rows into NodeMetrics")

    async def backfill_pod_metrics(self):
        """Backfill PodMetrics table from otel_metrics_gauge."""
        logger.info("Backfilling PodMetrics table...")

        where_clause = "WHERE ResourceAttributes['cluster_id'] IS NOT NULL AND ResourceAttributes['cluster_id'] != ''"
        if self.cluster_id:
            where_clause += f" AND ResourceAttributes['cluster_id'] = '{self.cluster_id}'"
        if self.from_date:
            where_clause += f" AND TimeUnix >= toDateTime('{self.from_date}')"
        if self.to_date:
            where_clause += f" AND TimeUnix < toDateTime('{self.to_date}')"

        query = f"""
        INSERT INTO PodMetrics
        SELECT
            toStartOfInterval(TimeUnix, INTERVAL 1 MINUTE) AS ts,
            ResourceAttributes['cluster_id'] AS cluster_id,
            anyLast(ResourceAttributes['cluster_name']) AS cluster_name,
            Attributes['namespace'] AS namespace,
            Attributes['pod'] AS pod_name,
            Attributes['container'] AS container_name,

            -- Resource requests/limits
            maxIf(Value, MetricName = 'kube_pod_container_resource_requests' AND
                  Attributes['resource'] = 'cpu') AS cpu_requests,
            maxIf(Value, MetricName = 'kube_pod_container_resource_limits' AND
                  Attributes['resource'] = 'cpu') AS cpu_limits,
            maxIf(Value, MetricName = 'kube_pod_container_resource_requests' AND
                  Attributes['resource'] = 'memory') AS memory_requests_bytes,
            maxIf(Value, MetricName = 'kube_pod_container_resource_limits' AND
                  Attributes['resource'] = 'memory') AS memory_limits_bytes,

            -- Actual usage
            avgIf(Value, MetricName = 'container_cpu_usage_seconds_total') AS cpu_usage,
            avgIf(Value, MetricName = 'container_memory_working_set_bytes') AS memory_usage_bytes,

            -- Restarts
            toInt32(maxIf(Value, MetricName = 'kube_pod_container_status_restarts_total')) AS restarts,

            -- Status
            CASE
                WHEN maxIf(Value, MetricName = 'kube_pod_status_phase' AND Attributes['phase'] = 'Running') = 1 THEN 'Running'
                WHEN maxIf(Value, MetricName = 'kube_pod_status_phase' AND Attributes['phase'] = 'Pending') = 1 THEN 'Pending'
                WHEN maxIf(Value, MetricName = 'kube_pod_status_phase' AND Attributes['phase'] = 'Failed') = 1 THEN 'Failed'
                WHEN maxIf(Value, MetricName = 'kube_pod_status_phase' AND Attributes['phase'] = 'Succeeded') = 1 THEN 'Succeeded'
                ELSE 'Unknown'
            END AS status

        FROM otel_metrics_gauge
        {where_clause}
        AND MetricName IN (
            'kube_pod_container_resource_requests',
            'kube_pod_container_resource_limits',
            'container_cpu_usage_seconds_total',
            'container_memory_usage_bytes',
            'container_memory_working_set_bytes',
            'kube_pod_container_status_restarts_total',
            'kube_pod_status_phase'
        )
        AND Attributes['pod'] IS NOT NULL
        AND Attributes['pod'] != ''
        GROUP BY
            toStartOfInterval(TimeUnix, INTERVAL 1 MINUTE),
            ResourceAttributes['cluster_id'],
            Attributes['namespace'],
            Attributes['pod'],
            Attributes['container']
        """

        if self.dry_run:
            logger.info("[DRY RUN] Would execute PodMetrics backfill")
        else:
            # Check if we have pod metrics first
            check_query = f"""
            SELECT count(*)
            FROM otel_metrics_gauge
            {where_clause}
            AND MetricName LIKE 'kube_pod%'
            """
            result = await self.client.execute_query(check_query)
            if result and result[0][0] > 0:
                await self.client.execute_query(query)
                logger.info(f"✓ Backfilled PodMetrics (found {result[0][0]:,} source metrics)")
            else:
                logger.info("⊘ No pod metrics found in source data (skipping)")

    async def backfill_cluster_metrics(self):
        """Backfill ClusterMetrics table from otel_metrics_gauge."""
        logger.info("Backfilling ClusterMetrics table...")

        where_clause = "WHERE ResourceAttributes['cluster_id'] IS NOT NULL AND ResourceAttributes['cluster_id'] != ''"
        if self.cluster_id:
            where_clause += f" AND ResourceAttributes['cluster_id'] = '{self.cluster_id}'"
        if self.from_date:
            where_clause += f" AND TimeUnix >= toDateTime('{self.from_date}')"
        if self.to_date:
            where_clause += f" AND TimeUnix < toDateTime('{self.to_date}')"

        query = f"""
        INSERT INTO ClusterMetrics
        SELECT
            TimeUnix AS ts,
            ResourceAttributes['cluster_id'] AS cluster_id,
            anyLast(ResourceAttributes['cluster_name']) AS cluster_name,
            anyLast(ResourceAttributes['cluster_platform']) AS cluster_platform,
            MetricName AS metric_name,
            avg(Value) AS value,
            Attributes AS labels
        FROM otel_metrics_gauge
        {where_clause}
        GROUP BY
            TimeUnix,
            ResourceAttributes['cluster_id'],
            MetricName,
            Attributes
        """

        if self.dry_run:
            logger.info("[DRY RUN] Would execute ClusterMetrics backfill")
        else:
            await self.client.execute_query(query)
            count_query = "SELECT count(*) FROM ClusterMetrics"
            result = await self.client.execute_query(count_query)
            count = result[0][0] if result else 0
            logger.info(f"✓ Backfilled {count:,} rows into ClusterMetrics")

    async def run_backfill(self):
        """Run the complete backfill process."""
        try:
            await self.initialize()
            await self.check_prerequisites()

            total_metrics = await self.get_data_info()
            if total_metrics == 0:
                logger.warning("No data to backfill")
                return

            if self.dry_run:
                logger.info("\n" + "=" * 60)
                logger.info("DRY RUN MODE - No changes will be made")
                logger.info("=" * 60 + "\n")

            # Backfill each table
            await self.backfill_node_metrics()
            await self.backfill_pod_metrics()
            await self.backfill_cluster_metrics()

            if self.dry_run:
                logger.info("\n" + "=" * 60)
                logger.info("DRY RUN COMPLETE - Run without --dry-run to apply changes")
                logger.info("=" * 60)
            else:
                logger.info("\n" + "=" * 60)
                logger.info("✓ Backfill completed successfully!")
                logger.info("=" * 60)
                logger.info("\nFuture metrics will be automatically populated by materialized views.")

        except Exception as e:
            logger.error(f"Backfill failed: {e}")
            raise
        finally:
            await self.client.close()


async def main():
    """Run the cluster metrics backfill script."""
    parser = argparse.ArgumentParser(
        description="Backfill historical cluster metrics from otel_metrics_gauge to structured tables"
    )
    parser.add_argument(
        "--cluster-id",
        type=str,
        help="Backfill only this cluster ID (default: all clusters)",
    )
    parser.add_argument(
        "--from-date",
        type=str,
        help="Start date for backfill in YYYY-MM-DD format (default: earliest available)",
    )
    parser.add_argument(
        "--to-date",
        type=str,
        help="End date for backfill in YYYY-MM-DD format (default: latest available)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )

    args = parser.parse_args()

    backfill = ClusterMetricsBackfill(
        cluster_id=args.cluster_id,
        from_date=args.from_date,
        to_date=args.to_date,
        dry_run=args.dry_run,
    )

    try:
        await backfill.run_backfill()
    except Exception as e:
        logger.error(f"Backfill error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
