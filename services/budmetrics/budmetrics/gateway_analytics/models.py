"""Gateway Analytics Models and Query Builder for budmetrics service."""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import List

from asynch import connect

from budmetrics.gateway_analytics.schemas import GatewayAnalyticsRequest, GatewayMetricType
from budmetrics.observability.models import ClickHouseConfig


# Get ClickHouse configuration
clickhouse_config = ClickHouseConfig()


@asynccontextmanager
async def get_clickhouse_client():
    """Get ClickHouse client connection."""
    conn = await connect(
        host=clickhouse_config.host,
        port=clickhouse_config.port,
        database=clickhouse_config.database,
        user=clickhouse_config.user,
        password=clickhouse_config.password,
    )
    try:
        yield conn
    finally:
        await conn.close()


class GatewayAnalyticsQueryBuilder:
    """Query builder for gateway analytics."""

    # Metric definitions with their aggregations
    METRIC_DEFINITIONS = {
        "request_count": "COUNT(*) as request_count",
        "success_rate": "AVG(CASE WHEN status_code < 400 THEN 1 ELSE 0 END) * 100 as success_rate",
        "error_rate": "AVG(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) * 100 as error_rate",
        "blocked_requests": "SUM(CASE WHEN is_blocked = 1 THEN 1 ELSE 0 END) as blocked_requests",
        "avg_response_time": "AVG(total_duration_ms) as avg_response_time",
        "p99_response_time": "quantile(0.99)(total_duration_ms) as p99_response_time",
        "p95_response_time": "quantile(0.95)(total_duration_ms) as p95_response_time",
        "unique_clients": "COUNT(DISTINCT client_ip) as unique_clients",
        "bot_traffic": "SUM(CASE WHEN is_bot = 1 THEN 1 ELSE 0 END) as bot_traffic",
    }

    # Metrics that require special handling
    DISTRIBUTION_METRICS = {
        "geographical_distribution",
        "device_distribution",
        "browser_distribution",
        "os_distribution",
        "route_distribution",
        "status_code_distribution",
    }

    # Time interval mappings
    TIME_INTERVALS = {
        "minute": "toStartOfMinute",
        "hour": "toStartOfHour",
        "day": "toDate",
        "week": "toStartOfWeek",
        "month": "toStartOfMonth",
    }

    def build_query(self, request: GatewayAnalyticsRequest) -> str:
        """Build ClickHouse query based on request parameters."""
        # Separate regular metrics from distribution metrics
        regular_metrics = [m for m in request.metrics if m not in self.DISTRIBUTION_METRICS]
        distribution_metrics = [m for m in request.metrics if m in self.DISTRIBUTION_METRICS]

        # Handle regular metrics
        if regular_metrics:
            return self._build_regular_metrics_query(request, regular_metrics)
        elif distribution_metrics:
            # For now, handle one distribution metric at a time
            return self._build_distribution_query(request, distribution_metrics[0])
        else:
            raise ValueError("No valid metrics specified")

    def _build_regular_metrics_query(self, request: GatewayAnalyticsRequest, metrics: List[GatewayMetricType]) -> str:
        """Build query for regular (non-distribution) metrics."""
        # Build SELECT clause
        select_parts = [self._get_time_bucket(request)]

        # Add grouping columns
        if request.group_by:
            for group in request.group_by:
                select_parts.append(f"{group}")

        # Add metric aggregations
        for metric in metrics:
            if metric in self.METRIC_DEFINITIONS:
                select_parts.append(self.METRIC_DEFINITIONS[metric])

        # Build FROM and WHERE clauses
        from_clause = "FROM GatewayAnalytics"
        where_conditions = self._build_where_conditions(request)

        # Build GROUP BY clause
        group_by_parts = ["time_bucket"]
        if request.group_by:
            group_by_parts.extend(request.group_by)

        # Build base query
        query_parts = [
            f"SELECT {', '.join(select_parts)}",
            from_clause,
            f"WHERE {' AND '.join(where_conditions)}",
            f"GROUP BY {', '.join(group_by_parts)}",
            "ORDER BY time_bucket",
        ]

        # Add LIMIT for top-k queries
        if request.topk and request.group_by:
            # Need to wrap in subquery to get top-k per time bucket
            base_query = "\n".join(query_parts)
            return self._wrap_with_topk(base_query, request)

        # Handle delta calculations if requested
        if request.return_delta:
            base_query = "\n".join(query_parts)
            return self._wrap_with_delta_calculation(base_query, metrics)

        return "\n".join(query_parts)

    def _build_distribution_query(self, request: GatewayAnalyticsRequest, metric: GatewayMetricType) -> str:
        """Build query for distribution metrics."""
        distribution_field = {
            "geographical_distribution": "country_code",
            "device_distribution": "device_type",
            "browser_distribution": "browser_name",
            "os_distribution": "os_name",
            "route_distribution": "path",
            "status_code_distribution": "status_code",
        }.get(metric)

        if not distribution_field:
            raise ValueError(f"Unknown distribution metric: {metric}")

        where_conditions = self._build_where_conditions(request)

        query = f"""
            SELECT
                {self._get_time_bucket(request)},
                {distribution_field},
                COUNT(*) as count,
                COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY time_bucket) as percent
            FROM GatewayAnalytics
            WHERE {" AND ".join(where_conditions)}
                AND {distribution_field} IS NOT NULL
            GROUP BY time_bucket, {distribution_field}
            ORDER BY time_bucket, count DESC
        """

        return query

    def _build_where_conditions(self, request: GatewayAnalyticsRequest) -> List[str]:
        """Build WHERE conditions based on request filters."""
        conditions = []

        # Time range conditions
        conditions.append(f"request_timestamp >= '{request.from_date.isoformat()}'")

        to_date = request.to_date or datetime.now(timezone.utc)
        conditions.append(f"request_timestamp <= '{to_date.isoformat()}'")

        # Project filter
        if request.project_id:
            conditions.append(f"project_id = '{request.project_id}'")

        # Custom filters
        if request.filters:
            for key, value in request.filters.items():
                if isinstance(value, list):
                    # Handle list filters (IN clause)
                    values_str = ", ".join([f"'{v}'" for v in value])
                    conditions.append(f"{key} IN ({values_str})")
                elif isinstance(value, bool):
                    conditions.append(f"{key} = {1 if value else 0}")
                else:
                    conditions.append(f"{key} = '{value}'")

        return conditions

    def _get_time_bucket(self, request: GatewayAnalyticsRequest) -> str:
        """Get time bucket expression based on frequency."""
        time_func = self.TIME_INTERVALS.get(request.frequency_unit, "toDate")

        if request.frequency_interval and request.frequency_interval > 1:
            # Handle custom intervals (e.g., every 5 minutes)
            if request.frequency_unit == "minute":
                return f"toStartOfInterval(request_timestamp, INTERVAL {request.frequency_interval} MINUTE) as time_bucket"
            elif request.frequency_unit == "hour":
                return (
                    f"toStartOfInterval(request_timestamp, INTERVAL {request.frequency_interval} HOUR) as time_bucket"
                )
            elif request.frequency_unit == "day":
                return (
                    f"toStartOfInterval(request_timestamp, INTERVAL {request.frequency_interval} DAY) as time_bucket"
                )

        return f"{time_func}(request_timestamp) as time_bucket"

    def _wrap_with_delta_calculation(self, base_query: str, metrics: List[str]) -> str:
        """Wrap query with delta calculation using window functions."""
        delta_calculations = []

        for metric in metrics:
            if metric == "request_count":
                delta_calculations.extend(
                    [
                        "request_count - LAG(request_count, 1, 0) OVER (ORDER BY time_bucket) as request_count_delta",
                        "CASE WHEN LAG(request_count, 1) OVER (ORDER BY time_bucket) > 0 THEN "
                        "((request_count - LAG(request_count, 1) OVER (ORDER BY time_bucket)) * 100.0 / "
                        "LAG(request_count, 1) OVER (ORDER BY time_bucket)) ELSE 0 END as request_count_delta_percent",
                    ]
                )
            # Add more delta calculations for other metrics as needed

        if not delta_calculations:
            return base_query

        return f"""
            SELECT
                *,
                {", ".join(delta_calculations)}
            FROM (
                {base_query}
            ) as base
            ORDER BY time_bucket
        """

    def _wrap_with_topk(self, base_query: str, request: GatewayAnalyticsRequest) -> str:
        """Wrap query to get top-k results per time bucket."""
        return f"""
            SELECT *
            FROM (
                SELECT
                    *,
                    row_number() OVER (PARTITION BY time_bucket ORDER BY request_count DESC) as rn
                FROM (
                    {base_query}
                ) as base
            ) as ranked
            WHERE rn <= {request.topk}
            ORDER BY time_bucket, rn
        """
