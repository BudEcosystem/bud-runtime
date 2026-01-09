"""OTel Analytics Query Helpers.

This module provides optimized query builders for the new OTel analytics architecture
with flat tables (InferenceFact) and rollup tables (InferenceMetrics5m, InferenceMetrics1h,
InferenceMetrics1d, GeoAnalytics1h).

The smart table selection logic chooses the most efficient table based on:
- Query interval (5m, 1h, 1d)
- Date range (recent vs historical data)
- Required columns (detailed data vs aggregates)

Performance targets:
- Rollup table queries: <100ms
- Fact table queries: <2s
- Scale: 1B+ records
"""

import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional
from uuid import UUID

from budmicroframe.commons import logging


logger = logging.get_logger(__name__)


class AnalyticsTable(Enum):
    """Available analytics tables."""

    INFERENCE_FACT = "InferenceFact"
    INFERENCE_METRICS_5M = "InferenceMetrics5m"
    INFERENCE_METRICS_1H = "InferenceMetrics1h"
    INFERENCE_METRICS_1D = "InferenceMetrics1d"
    GEO_ANALYTICS_1H = "GeoAnalytics1h"

    # Legacy tables (for fallback)
    MODEL_INFERENCE = "ModelInference"
    MODEL_INFERENCE_DETAILS = "ModelInferenceDetails"
    GATEWAY_ANALYTICS = "GatewayAnalytics"


class QueryInterval(Enum):
    """Query time intervals."""

    MINUTE_1 = "1m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    MINUTE_30 = "30m"
    HOUR_1 = "1h"
    HOUR_6 = "6h"
    HOUR_12 = "12h"
    DAY_1 = "1d"
    WEEK_1 = "1w"


@dataclass
class TableSelectionResult:
    """Result of smart table selection."""

    table: AnalyticsTable
    use_rollup: bool
    requires_merge_functions: bool
    reason: str


def is_otel_analytics_enabled() -> bool:
    """Check if OTel analytics tables are enabled.

    This can be controlled via environment variable to allow gradual rollout.
    """
    return os.getenv("OTEL_ANALYTICS_ENABLED", "true").lower() == "true"


def get_interval_minutes(interval: str) -> int:
    """Convert interval string to minutes."""
    interval_map = {
        "1m": 1,
        "5m": 5,
        "15m": 15,
        "30m": 30,
        "1h": 60,
        "6h": 360,
        "12h": 720,
        "1d": 1440,
        "1w": 10080,
    }
    return interval_map.get(interval, 60)


def select_metrics_table(
    interval: str,
    from_date: datetime,
    to_date: datetime,
    requires_detailed_data: bool = False,
) -> TableSelectionResult:
    """Select the most efficient metrics table based on query parameters.

    Args:
        interval: Query interval (1m, 5m, 15m, 30m, 1h, 6h, 12h, 1d, 1w)
        from_date: Query start date
        to_date: Query end date
        requires_detailed_data: Whether the query needs per-inference data

    Returns:
        TableSelectionResult with the selected table and metadata
    """
    if not is_otel_analytics_enabled():
        return TableSelectionResult(
            table=AnalyticsTable.MODEL_INFERENCE_DETAILS,
            use_rollup=False,
            requires_merge_functions=False,
            reason="OTel analytics disabled, using legacy tables",
        )

    # Calculate date range in days
    date_range_days = (to_date - from_date).days

    # For detailed data queries, always use InferenceFact
    if requires_detailed_data:
        return TableSelectionResult(
            table=AnalyticsTable.INFERENCE_FACT,
            use_rollup=False,
            requires_merge_functions=False,
            reason="Detailed data required, using InferenceFact",
        )

    interval_minutes = get_interval_minutes(interval)

    # Decision tree for table selection
    if interval_minutes <= 30:
        # Short intervals: use 5m rollup
        return TableSelectionResult(
            table=AnalyticsTable.INFERENCE_METRICS_5M,
            use_rollup=True,
            requires_merge_functions=True,
            reason=f"Short interval ({interval}), using 5m rollup",
        )
    elif interval_minutes <= 720:  # Up to 12 hours
        # Medium intervals: use hourly rollup for longer ranges
        if date_range_days > 7:
            return TableSelectionResult(
                table=AnalyticsTable.INFERENCE_METRICS_1H,
                use_rollup=True,
                requires_merge_functions=True,
                reason=f"Medium interval ({interval}) with {date_range_days}d range, using 1h rollup",
            )
        else:
            return TableSelectionResult(
                table=AnalyticsTable.INFERENCE_METRICS_5M,
                use_rollup=True,
                requires_merge_functions=True,
                reason=f"Medium interval ({interval}) with short range, using 5m rollup",
            )
    else:
        # Long intervals (1d, 1w): use daily rollup for historical
        if date_range_days > 30:
            return TableSelectionResult(
                table=AnalyticsTable.INFERENCE_METRICS_1D,
                use_rollup=True,
                requires_merge_functions=False,  # 1d table uses finalized values
                reason=f"Long interval ({interval}) with {date_range_days}d range, using 1d rollup",
            )
        else:
            return TableSelectionResult(
                table=AnalyticsTable.INFERENCE_METRICS_1H,
                use_rollup=True,
                requires_merge_functions=True,
                reason=f"Long interval ({interval}) with medium range, using 1h rollup",
            )


def select_geo_table(
    from_date: datetime,
    to_date: datetime,
    requires_detailed_data: bool = False,
) -> TableSelectionResult:
    """Select the most efficient table for geographic queries.

    Args:
        from_date: Query start date
        to_date: Query end date
        requires_detailed_data: Whether the query needs per-inference data

    Returns:
        TableSelectionResult with the selected table and metadata
    """
    if not is_otel_analytics_enabled():
        return TableSelectionResult(
            table=AnalyticsTable.GATEWAY_ANALYTICS,
            use_rollup=False,
            requires_merge_functions=False,
            reason="OTel analytics disabled, using GatewayAnalytics",
        )

    if requires_detailed_data:
        return TableSelectionResult(
            table=AnalyticsTable.INFERENCE_FACT,
            use_rollup=False,
            requires_merge_functions=False,
            reason="Detailed geo data required, using InferenceFact",
        )

    return TableSelectionResult(
        table=AnalyticsTable.GEO_ANALYTICS_1H,
        use_rollup=True,
        requires_merge_functions=True,
        reason="Geographic analytics using GeoAnalytics1h rollup",
    )


class OTelAnalyticsQueryBuilder:
    """Query builder for OTel analytics tables.

    This builder generates optimized queries for the new flat + rollup table
    architecture, eliminating JOINs and using pre-aggregated data where possible.
    """

    DATETIME_FMT = "%Y-%m-%d %H:%M:%S"

    # Column mappings for different tables
    COLUMN_MAPPINGS = {
        AnalyticsTable.INFERENCE_FACT: {
            "project": "project_id",
            "endpoint": "endpoint_id",
            "model": "model_id",
            "model_name": "model_name",
            "model_provider": "model_provider",
            "user_project": "api_key_project_id",
            "timestamp": "timestamp",
        },
        AnalyticsTable.INFERENCE_METRICS_5M: {
            "project": "project_id",
            "endpoint": "endpoint_id",
            "model": "model_id",
            "model_name": "model_name",
            "model_provider": "model_provider",
            "user_project": "api_key_project_id",
            "timestamp": "ts",
        },
        AnalyticsTable.INFERENCE_METRICS_1H: {
            "project": "project_id",
            "model": "model_id",
            "model_name": "model_name",
            "model_provider": "model_provider",
            "user_project": "api_key_project_id",
            "timestamp": "ts",
        },
        AnalyticsTable.INFERENCE_METRICS_1D: {
            "project": "project_id",
            "model_name": "model_name",
            "timestamp": "ts",
        },
        AnalyticsTable.GEO_ANALYTICS_1H: {
            "project": "project_id",
            "user_project": "api_key_project_id",
            "country": "country_code",
            "region": "region",
            "city": "city",
            "timestamp": "ts",
        },
    }

    def __init__(self):
        """Initialize the OTel analytics query builder."""
        pass

    def _escape_sql_value(self, value: str) -> str:
        """Escape single quotes in SQL values to prevent SQL injection.

        Args:
            value: The string value to escape

        Returns:
            Escaped string safe for SQL interpolation
        """
        if value is None:
            return ""
        # Escape single quotes by doubling them (standard SQL escaping)
        return str(value).replace("'", "''")

    def get_column(self, table: AnalyticsTable, field: str) -> str:
        """Get the column name for a field in a specific table."""
        mappings = self.COLUMN_MAPPINGS.get(table, {})
        return mappings.get(field, field)

    def build_timeseries_query(
        self,
        table_result: TableSelectionResult,
        metrics: list[str],
        from_date: datetime,
        to_date: datetime,
        interval: str,
        filters: Optional[dict] = None,
        group_by: Optional[list[str]] = None,
    ) -> str:
        """Build an optimized time series query.

        Args:
            table_result: Result from select_metrics_table
            metrics: List of metrics to query (request_count, success_rate, latency_p95, etc.)
            from_date: Query start date
            to_date: Query end date
            interval: Time bucket interval
            filters: Optional filters (project, endpoint, model, etc.)
            group_by: Optional grouping fields

        Returns:
            SQL query string
        """
        table = table_result.table
        use_merge = table_result.requires_merge_functions

        # Build SELECT clause
        select_parts = [self._build_time_bucket(table, interval)]
        select_parts.extend(self._build_metric_selects(table, metrics, use_merge, from_date, to_date))

        if group_by:
            for field in group_by:
                col = self.get_column(table, field)
                select_parts.append(col)

        # Build WHERE clause
        where_parts = self._build_filter_conditions(table, from_date, to_date, filters)

        # Build GROUP BY clause
        group_by_parts = [self._get_time_bucket_alias()]
        if group_by:
            for field in group_by:
                group_by_parts.append(self.get_column(table, field))

        query = f"""
        SELECT
            {', '.join(select_parts)}
        FROM {table.value}
        WHERE {' AND '.join(where_parts)}
        GROUP BY {', '.join(group_by_parts)}
        ORDER BY time_bucket
        """

        return query.strip()

    def build_aggregated_query(
        self,
        table_result: TableSelectionResult,
        metrics: list[str],
        from_date: datetime,
        to_date: datetime,
        filters: Optional[dict] = None,
        group_by: Optional[list[str]] = None,
    ) -> str:
        """Build an optimized aggregated metrics query.

        Args:
            table_result: Result from select_metrics_table
            metrics: List of metrics to query
            from_date: Query start date
            to_date: Query end date
            filters: Optional filters
            group_by: Optional grouping fields

        Returns:
            SQL query string
        """
        table = table_result.table
        use_merge = table_result.requires_merge_functions

        # Build SELECT clause
        select_parts = self._build_metric_selects(table, metrics, use_merge, from_date, to_date)

        if group_by:
            for field in group_by:
                col = self.get_column(table, field)
                select_parts.insert(0, col)

        # Build WHERE clause
        where_parts = self._build_filter_conditions(table, from_date, to_date, filters)

        # Build query
        if group_by:
            group_by_cols = [self.get_column(table, f) for f in group_by]
            query = f"""
            SELECT
                {', '.join(select_parts)}
            FROM {table.value}
            WHERE {' AND '.join(where_parts)}
            GROUP BY {', '.join(group_by_cols)}
            """
        else:
            query = f"""
            SELECT
                {', '.join(select_parts)}
            FROM {table.value}
            WHERE {' AND '.join(where_parts)}
            """

        return query.strip()

    def build_geo_query(
        self,
        table_result: TableSelectionResult,
        from_date: datetime,
        to_date: datetime,
        filters: Optional[dict] = None,
        group_by_level: str = "country",  # country, region, or city
    ) -> str:
        """Build an optimized geographic analytics query.

        Args:
            table_result: Result from select_geo_table
            from_date: Query start date
            to_date: Query end date
            filters: Optional filters
            group_by_level: Geographic grouping level

        Returns:
            SQL query string
        """
        table = table_result.table
        use_merge = table_result.requires_merge_functions

        # Determine grouping columns
        geo_cols = ["country_code"]
        if group_by_level in ["region", "city"]:
            geo_cols.append("region")
        if group_by_level == "city":
            geo_cols.append("city")

        # Build SELECT clause
        select_parts = geo_cols.copy()

        if use_merge:
            select_parts.extend([
                "sum(request_count) AS request_count",
                "sum(success_count) AS success_count",
                "if(sum(request_count) > 0, sum(response_time_sum) / sum(request_count), 0) AS avg_response_time_ms",
                "uniqMerge(unique_users) AS unique_users",
                "avg(latitude_avg) AS latitude",
                "avg(longitude_avg) AS longitude",
            ])
        else:
            select_parts.extend([
                "count() AS request_count",
                "countIf(is_success = true) AS success_count",
                "avg(response_time_ms) AS avg_response_time_ms",
                "uniq(user_id) AS unique_users",
                "avg(latitude) AS latitude",
                "avg(longitude) AS longitude",
            ])

        # Build WHERE clause
        where_parts = self._build_filter_conditions(table, from_date, to_date, filters)
        where_parts.append("country_code IS NOT NULL")
        where_parts.append("country_code != ''")

        query = f"""
        SELECT
            {', '.join(select_parts)}
        FROM {table.value}
        WHERE {' AND '.join(where_parts)}
        GROUP BY {', '.join(geo_cols)}
        ORDER BY request_count DESC
        """

        return query.strip()

    def _build_time_bucket(self, table: AnalyticsTable, interval: str) -> str:
        """Build time bucket expression."""
        ts_col = self.get_column(table, "timestamp")

        interval_map = {
            "1m": "toStartOfMinute",
            "5m": "toStartOfFiveMinutes",
            "15m": "toStartOfFifteenMinutes",
            "30m": "toStartOfInterval({col}, INTERVAL 30 MINUTE)",
            "1h": "toStartOfHour",
            "6h": "toStartOfInterval({col}, INTERVAL 6 HOUR)",
            "12h": "toStartOfInterval({col}, INTERVAL 12 HOUR)",
            "1d": "toStartOfDay",
            "1w": "toStartOfWeek",
        }

        func = interval_map.get(interval, "toStartOfHour")
        if "{col}" in func:
            return f"{func.format(col=ts_col)} AS time_bucket"
        return f"{func}({ts_col}) AS time_bucket"

    def _get_time_bucket_alias(self) -> str:
        """Get the time bucket alias."""
        return "time_bucket"

    def _build_metric_selects(
        self,
        table: AnalyticsTable,
        metrics: list[str],
        use_merge: bool,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> list[str]:
        """Build SELECT expressions for metrics.

        For rollup tables, uses merge functions (uniqMerge, quantilesTDigestMerge).
        For fact tables, uses regular aggregation functions.

        Args:
            table: The analytics table to query
            metrics: List of metric names to include
            use_merge: Whether to use merge functions (for rollup tables)
            from_date: Query start date (needed for concurrent_requests subquery)
            to_date: Query end date (needed for concurrent_requests subquery)
        """
        selects = []

        for metric in metrics:
            if metric == "request_count":
                # Use "_rc" suffix to avoid conflict with column name when other
                # metrics reference request_count column (e.g., latency_avg uses sum(request_count))
                # The alias will be renamed back to "request_count" in post-processing
                if table in [AnalyticsTable.INFERENCE_METRICS_5M, AnalyticsTable.INFERENCE_METRICS_1H]:
                    selects.append("sum(request_count) AS request_count_rc")
                elif table == AnalyticsTable.INFERENCE_METRICS_1D:
                    selects.append("sum(request_count) AS request_count_rc")
                else:
                    selects.append("count() AS request_count_rc")

            elif metric in ("success_count", "success_request"):
                # Support both internal name (success_count) and API name (success_request)
                alias = "success_request" if metric == "success_request" else "success_count"
                if table in [AnalyticsTable.INFERENCE_METRICS_5M, AnalyticsTable.INFERENCE_METRICS_1H, AnalyticsTable.INFERENCE_METRICS_1D]:
                    selects.append(f"sum(success_count) AS {alias}")
                else:
                    selects.append(f"countIf(is_success = true) AS {alias}")

            elif metric in ("error_count", "failure_request"):
                # Support both internal name (error_count) and API name (failure_request)
                alias = "failure_request" if metric == "failure_request" else "error_count"
                if table in [AnalyticsTable.INFERENCE_METRICS_5M, AnalyticsTable.INFERENCE_METRICS_1H, AnalyticsTable.INFERENCE_METRICS_1D]:
                    selects.append(f"sum(error_count) AS {alias}")
                else:
                    selects.append(f"countIf(is_success = false) AS {alias}")

            elif metric == "success_rate":
                if table in [AnalyticsTable.INFERENCE_METRICS_5M, AnalyticsTable.INFERENCE_METRICS_1H, AnalyticsTable.INFERENCE_METRICS_1D]:
                    selects.append("if(sum(request_count) > 0, sum(success_count) * 100.0 / sum(request_count), 0) AS success_rate")
                else:
                    selects.append("if(count() > 0, countIf(is_success = true) * 100.0 / count(), 0) AS success_rate")

            elif metric in ("input_tokens", "input_token"):
                # Support both plural (new) and singular (legacy API schema) names
                if table in [AnalyticsTable.INFERENCE_METRICS_5M, AnalyticsTable.INFERENCE_METRICS_1H, AnalyticsTable.INFERENCE_METRICS_1D]:
                    selects.append(f"sum(input_tokens_sum) AS {metric}")
                else:
                    selects.append(f"sum(input_tokens) AS {metric}")

            elif metric in ("output_tokens", "output_token"):
                # Support both plural (new) and singular (legacy API schema) names
                if table in [AnalyticsTable.INFERENCE_METRICS_5M, AnalyticsTable.INFERENCE_METRICS_1H, AnalyticsTable.INFERENCE_METRICS_1D]:
                    selects.append(f"sum(output_tokens_sum) AS {metric}")
                else:
                    selects.append(f"sum(output_tokens) AS {metric}")

            elif metric == "total_tokens":
                if table in [AnalyticsTable.INFERENCE_METRICS_5M, AnalyticsTable.INFERENCE_METRICS_1H, AnalyticsTable.INFERENCE_METRICS_1D]:
                    selects.append("sum(input_tokens_sum) + sum(output_tokens_sum) AS total_tokens")
                else:
                    selects.append("sum(input_tokens) + sum(output_tokens) AS total_tokens")

            elif metric == "cost":
                if table in [AnalyticsTable.INFERENCE_METRICS_5M, AnalyticsTable.INFERENCE_METRICS_1H, AnalyticsTable.INFERENCE_METRICS_1D]:
                    selects.append("sum(cost_sum) AS cost")
                else:
                    selects.append("sum(cost) AS cost")

            elif metric in ("latency_avg", "latency"):
                # Support both "latency_avg" (new) and "latency" (legacy API schema) names
                if table == AnalyticsTable.INFERENCE_METRICS_5M:
                    # 5m table has response_time_sum and response_time_count (non-NULL latency count)
                    selects.append(f"if(sum(response_time_count) > 0, sum(response_time_sum) / sum(response_time_count), 0) AS {metric}")
                elif table == AnalyticsTable.INFERENCE_METRICS_1H:
                    # 1h table has response_time_sum and response_time_count for true average
                    selects.append(f"if(sum(response_time_count) > 0, sum(response_time_sum) / sum(response_time_count), 0) AS {metric}")
                elif table == AnalyticsTable.INFERENCE_METRICS_1D:
                    selects.append(f"avg(response_time_avg) AS {metric}")
                else:
                    selects.append(f"avg(response_time_ms) AS {metric}")

            elif metric == "latency_p50":
                if use_merge:
                    # quantilesTDigestMerge(0.5)() returns single-element array, so [1] accesses it
                    selects.append("quantilesTDigestMerge(0.5)(response_time_quantiles)[1] AS latency_p50")
                else:
                    selects.append("quantile(0.5)(response_time_ms) AS latency_p50")

            elif metric == "latency_p95":
                # Note: 1d table doesn't have response_time_p95 column (removed for accuracy)
                # Services.py will fallback to 1h table when this metric is requested
                if use_merge:
                    # quantilesTDigestMerge(0.95)() returns single-element array, so [1] accesses it
                    selects.append("quantilesTDigestMerge(0.95)(response_time_quantiles)[1] AS latency_p95")
                else:
                    selects.append("quantile(0.95)(response_time_ms) AS latency_p95")

            elif metric == "latency_p99":
                if use_merge:
                    # quantilesTDigestMerge(0.99)() returns single-element array, so [1] accesses it
                    selects.append("quantilesTDigestMerge(0.99)(response_time_quantiles)[1] AS latency_p99")
                else:
                    selects.append("quantile(0.99)(response_time_ms) AS latency_p99")

            elif metric == "unique_users":
                # Note: 1d table doesn't have unique_users column (removed for accuracy)
                # Services.py will fallback to 1h table when this metric is requested
                if use_merge:
                    selects.append("uniqMerge(unique_users) AS unique_users")
                else:
                    selects.append("uniq(user_id) AS unique_users")

            elif metric in ("ttft", "ttft_avg"):
                # Support both "ttft" (legacy API) and "ttft_avg" (new API) names
                # "ttft" uses avg_ttft_ms alias for compatibility with services.py processor
                alias = "avg_ttft_ms" if metric == "ttft" else "ttft_avg"
                if table in [AnalyticsTable.INFERENCE_METRICS_5M, AnalyticsTable.INFERENCE_METRICS_1H]:
                    # Use ttft_count (non-NULL TTFT values) for accurate average
                    selects.append(f"if(sum(ttft_count) > 0, sum(ttft_sum) / sum(ttft_count), 0) AS {alias}")
                else:
                    selects.append(f"avg(ttft_ms) AS {alias}")

            elif metric == "ttft_p95":
                # Note: 1d table doesn't have ttft_p95 column (removed for accuracy)
                # Services.py will fallback to 1h table when this metric is requested
                if use_merge:
                    # quantilesTDigestMerge(0.95)() returns single-element array, so [1] accesses it
                    selects.append("quantilesTDigestMerge(0.95)(ttft_quantiles)[1] AS ttft_p95")
                else:
                    selects.append("quantile(0.95)(ttft_ms) AS ttft_p95")

            elif metric == "throughput":
                # Throughput = output_tokens per second
                # Formula: output_tokens * 1000 / response_time_ms
                if table in [AnalyticsTable.INFERENCE_METRICS_5M, AnalyticsTable.INFERENCE_METRICS_1H, AnalyticsTable.INFERENCE_METRICS_1D]:
                    # Rollup tables: use aggregated sums for weighted average
                    selects.append(
                        "if(sum(response_time_sum) > 0, "
                        "sum(output_tokens_sum) * 1000.0 / sum(response_time_sum), 0) "
                        "AS avg_throughput_tokens_per_sec"
                    )
                else:
                    # InferenceFact: compute per-request throughput and average
                    selects.append(
                        "AVG(output_tokens * 1000.0 / NULLIF(response_time_ms, 0)) "
                        "AS avg_throughput_tokens_per_sec"
                    )

            elif metric == "cache":
                # Cache metric returns hit_count and hit_rate
                if table in [AnalyticsTable.INFERENCE_METRICS_5M, AnalyticsTable.INFERENCE_METRICS_1H]:
                    selects.append("sum(cached_count) AS cache_hit_count")
                    selects.append("if(sum(request_count) > 0, sum(cached_count) * 100.0 / sum(request_count), 0) AS cache_hit_rate")
                else:
                    selects.append("countIf(cached = true) AS cache_hit_count")
                    selects.append("if(count(*) > 0, countIf(cached = true) * 100.0 / count(*), 0) AS cache_hit_rate")

            elif metric == "cached_count":
                if table in [AnalyticsTable.INFERENCE_METRICS_5M, AnalyticsTable.INFERENCE_METRICS_1H]:
                    selects.append("sum(cached_count) AS cached_count")
                else:
                    selects.append("countIf(cached = true) AS cached_count")

            elif metric == "blocked_count":
                if table == AnalyticsTable.INFERENCE_METRICS_5M:
                    selects.append("sum(blocked_count) AS blocked_count")
                else:
                    selects.append("countIf(is_blocked = true) AS blocked_count")

            elif metric == "queuing_time":
                # Queuing time = time between request arrival and forward
                if table in [AnalyticsTable.INFERENCE_METRICS_5M, AnalyticsTable.INFERENCE_METRICS_1H, AnalyticsTable.INFERENCE_METRICS_1D]:
                    # Use aggregated sum/count for weighted average from rollup tables
                    selects.append(
                        "if(sum(queuing_time_count) > 0, "
                        "sum(queuing_time_sum) / sum(queuing_time_count), 0) AS avg_queuing_time_ms"
                    )
                else:
                    # InferenceFact: compute directly
                    selects.append(
                        "AVG(toUnixTimestamp64Milli(request_forward_time) - "
                        "toUnixTimestamp64Milli(request_arrival_time)) AS avg_queuing_time_ms"
                    )

            elif metric == "concurrent_requests":
                # Concurrent requests = count of requests at same exact timestamp
                # Cannot use rollup tables - requires exact timestamp matching
                # Uses scalar subquery to calculate AVG concurrent count
                # Use if(isNaN) to return 0 when no concurrent requests (AVG returns NaN for empty set)
                selects.append(
                    f"(SELECT if(isNaN(avg_val), 0, avg_val) FROM ("
                    f"SELECT AVG(cc) AS avg_val FROM ("
                    f"SELECT COUNT(*) as cc "
                    f"FROM InferenceFact "
                    f"WHERE timestamp >= '{from_date.strftime(self.DATETIME_FMT)}' "
                    f"AND timestamp <= '{to_date.strftime(self.DATETIME_FMT)}' "
                    f"GROUP BY request_arrival_time "
                    f"HAVING COUNT(*) > 1"
                    f"))) AS max_concurrent_requests"
                )

        return selects

    def _build_filter_conditions(
        self,
        table: AnalyticsTable,
        from_date: datetime,
        to_date: datetime,
        filters: Optional[dict] = None,
    ) -> list[str]:
        """Build WHERE clause conditions."""
        ts_col = self.get_column(table, "timestamp")
        conditions = [
            f"{ts_col} >= '{from_date.strftime(self.DATETIME_FMT)}'",
            f"{ts_col} <= '{to_date.strftime(self.DATETIME_FMT)}'",
        ]

        if filters:
            for key, value in filters.items():
                col = self.get_column(table, key)
                if col:
                    if isinstance(value, list):
                        # Escape each value in the list to prevent SQL injection
                        values_str = ",".join([f"'{self._escape_sql_value(v)}'" for v in value])
                        conditions.append(f"{col} IN ({values_str})")
                    elif value is not None:
                        # Escape value to prevent SQL injection
                        escaped_value = self._escape_sql_value(value)
                        conditions.append(f"{col} = '{escaped_value}'")

        return conditions

    def build_inference_list_query(
        self,
        from_date: datetime,
        to_date: datetime,
        filters: Optional[dict] = None,
        sort_by: str = "timestamp",
        sort_order: str = "DESC",
        limit: int = 100,
        offset: int = 0,
    ) -> str:
        """Build query for listing inferences with pagination.

        Uses InferenceFact table directly (no JOINs needed).

        Args:
            from_date: Query start date
            to_date: Query end date
            filters: Optional filters (project_id, endpoint_id, model_id, etc.)
            sort_by: Column to sort by
            sort_order: ASC or DESC
            limit: Number of records to return
            offset: Number of records to skip

        Returns:
            SQL query string
        """
        table = AnalyticsTable.INFERENCE_FACT

        # Map sort columns to InferenceFact columns
        sort_column_map = {
            "timestamp": "timestamp",
            "tokens": "(input_tokens + output_tokens)",
            "latency": "response_time_ms",
            "cost": "cost",
        }
        sort_col = sort_column_map.get(sort_by, "timestamp")

        # Validate sort order
        sort_order = "DESC" if sort_order.upper() != "ASC" else "ASC"

        where_parts = self._build_filter_conditions(table, from_date, to_date, filters)

        query = f"""
        SELECT
            inference_id,
            timestamp,
            model_name,
            model_provider,
            endpoint_type,
            project_id,
            endpoint_id,
            model_id,
            input_tokens,
            output_tokens,
            response_time_ms,
            cost,
            is_success,
            error_type,
            error_message,
            cached,
            finish_reason,
            substring(system_prompt, 1, 200) AS system_prompt_preview,
            substring(input_messages, 1, 500) AS prompt_preview,
            substring(output, 1, 500) AS response_preview
        FROM {table.value}
        WHERE {' AND '.join(where_parts)}
        ORDER BY {sort_col} {sort_order}
        LIMIT {limit}
        OFFSET {offset}
        """

        return query.strip()

    def build_inference_count_query(
        self,
        from_date: datetime,
        to_date: datetime,
        filters: Optional[dict] = None,
    ) -> str:
        """Build count query for inference list pagination.

        Args:
            from_date: Query start date
            to_date: Query end date
            filters: Optional filters

        Returns:
            SQL query string for count
        """
        table = AnalyticsTable.INFERENCE_FACT
        where_parts = self._build_filter_conditions(table, from_date, to_date, filters)

        query = f"""
        SELECT count() AS total
        FROM {table.value}
        WHERE {' AND '.join(where_parts)}
        """

        return query.strip()

    def build_credential_usage_query(
        self,
        since: datetime,
        credential_ids: Optional[list[str]] = None,
    ) -> str:
        """Build query for credential usage statistics.

        Args:
            since: Query start date
            credential_ids: Optional list of credential IDs to filter

        Returns:
            SQL query string
        """
        table = AnalyticsTable.INFERENCE_FACT

        conditions = [
            f"timestamp >= '{since.strftime(self.DATETIME_FMT)}'",
            "api_key_id IS NOT NULL",
        ]

        if credential_ids:
            cred_values = ",".join([f"'{self._escape_sql_value(c)}'" for c in credential_ids])
            conditions.append(f"api_key_id IN ({cred_values})")

        query = f"""
        SELECT
            api_key_id AS credential_id,
            MAX(timestamp) AS last_used_at,
            count() AS request_count
        FROM {table.value}
        WHERE {' AND '.join(conditions)}
        GROUP BY api_key_id
        """

        return query.strip()

    def build_metrics_sync_credential_query(
        self,
        since: Optional[datetime] = None,
    ) -> str:
        """Build query for credential sync metrics.

        Args:
            since: Optional start date for incremental sync

        Returns:
            SQL query string
        """
        table = AnalyticsTable.INFERENCE_FACT

        conditions = ["api_key_id IS NOT NULL"]
        if since:
            conditions.append(f"timestamp >= '{since.strftime(self.DATETIME_FMT)}'")

        query = f"""
        SELECT
            api_key_id AS credential_id,
            MAX(timestamp) AS last_used_at,
            count() AS request_count
        FROM {table.value}
        WHERE {' AND '.join(conditions)}
        GROUP BY api_key_id
        """

        return query.strip()

    def build_metrics_sync_user_query(
        self,
        since: Optional[datetime] = None,
    ) -> str:
        """Build query for user sync metrics.

        Args:
            since: Optional start date for incremental sync

        Returns:
            SQL query string
        """
        table = AnalyticsTable.INFERENCE_FACT

        conditions = ["user_id IS NOT NULL", "user_id != ''"]
        if since:
            conditions.append(f"timestamp >= '{since.strftime(self.DATETIME_FMT)}'")

        query = f"""
        SELECT
            user_id,
            MAX(timestamp) AS last_activity_at,
            sum(COALESCE(input_tokens, 0) + COALESCE(output_tokens, 0)) AS total_tokens,
            sum(COALESCE(cost, 0)) AS total_cost,
            count() AS request_count,
            avg(CASE WHEN is_success THEN 1 ELSE 0 END) AS success_rate
        FROM {table.value}
        WHERE {' AND '.join(conditions)}
        GROUP BY user_id
        """

        return query.strip()

    def build_usage_summary_query(
        self,
        table_result: TableSelectionResult,
        from_date: datetime,
        to_date: datetime,
        filters: Optional[dict] = None,
    ) -> str:
        """Build query for usage summary.

        Args:
            table_result: Result from select_metrics_table
            from_date: Query start date
            to_date: Query end date
            filters: Optional filters (user_id, project_id)

        Returns:
            SQL query string
        """
        table = table_result.table
        use_rollup = table_result.use_rollup

        where_parts = self._build_filter_conditions(table, from_date, to_date, filters)

        if use_rollup and table in [AnalyticsTable.INFERENCE_METRICS_5M, AnalyticsTable.INFERENCE_METRICS_1H, AnalyticsTable.INFERENCE_METRICS_1D]:
            query = f"""
            SELECT
                sum(request_count) AS request_count,
                sum(success_count) AS success_count,
                sum(cost_sum) AS total_cost,
                sum(input_tokens_sum) AS total_input_tokens,
                sum(output_tokens_sum) AS total_output_tokens
            FROM {table.value}
            WHERE {' AND '.join(where_parts)}
            """
        else:
            query = f"""
            SELECT
                count() AS request_count,
                countIf(is_success = true) AS success_count,
                sum(COALESCE(cost, 0)) AS total_cost,
                sum(COALESCE(input_tokens, 0)) AS total_input_tokens,
                sum(COALESCE(output_tokens, 0)) AS total_output_tokens
            FROM {table.value}
            WHERE {' AND '.join(where_parts)}
            """

        return query.strip()

    def build_usage_history_query(
        self,
        table_result: TableSelectionResult,
        from_date: datetime,
        to_date: datetime,
        granularity: str = "daily",
        filters: Optional[dict] = None,
    ) -> str:
        """Build query for usage history with time buckets.

        Args:
            table_result: Result from select_metrics_table
            from_date: Query start date
            to_date: Query end date
            granularity: Time granularity (hourly, daily, weekly, monthly)
            filters: Optional filters

        Returns:
            SQL query string
        """
        table = table_result.table
        use_rollup = table_result.use_rollup
        ts_col = self.get_column(table, "timestamp")

        # Map granularity to time bucket function
        date_trunc_map = {
            "hourly": f"toStartOfHour({ts_col})",
            "daily": f"toDate({ts_col})",
            "weekly": f"toMonday({ts_col})",
            "monthly": f"toStartOfMonth({ts_col})",
        }
        date_trunc = date_trunc_map.get(granularity, f"toDate({ts_col})")

        where_parts = self._build_filter_conditions(table, from_date, to_date, filters)

        if use_rollup and table in [AnalyticsTable.INFERENCE_METRICS_5M, AnalyticsTable.INFERENCE_METRICS_1H, AnalyticsTable.INFERENCE_METRICS_1D]:
            query = f"""
            SELECT
                {date_trunc} AS period,
                sum(request_count) AS request_count,
                sum(cost_sum) AS total_cost,
                sum(input_tokens_sum) AS total_input_tokens,
                sum(output_tokens_sum) AS total_output_tokens
            FROM {table.value}
            WHERE {' AND '.join(where_parts)}
            GROUP BY period
            ORDER BY period ASC
            """
        else:
            query = f"""
            SELECT
                {date_trunc} AS period,
                count() AS request_count,
                sum(COALESCE(cost, 0)) AS total_cost,
                sum(COALESCE(input_tokens, 0)) AS total_input_tokens,
                sum(COALESCE(output_tokens, 0)) AS total_output_tokens
            FROM {table.value}
            WHERE {' AND '.join(where_parts)}
            GROUP BY period
            ORDER BY period ASC
            """

        return query.strip()

    def build_usage_by_project_query(
        self,
        table_result: TableSelectionResult,
        from_date: datetime,
        to_date: datetime,
        user_id: str,
    ) -> str:
        """Build query for usage grouped by project.

        Args:
            table_result: Result from select_metrics_table
            from_date: Query start date
            to_date: Query end date
            user_id: User ID to filter by

        Returns:
            SQL query string
        """
        table = table_result.table
        use_rollup = table_result.use_rollup

        filters = {"user_id": user_id} if table == AnalyticsTable.INFERENCE_FACT else None
        where_parts = self._build_filter_conditions(table, from_date, to_date, filters)

        # For rollup tables, we need to use api_key_project_id since user_id is not available
        if use_rollup and table in [AnalyticsTable.INFERENCE_METRICS_5M, AnalyticsTable.INFERENCE_METRICS_1H]:
            query = f"""
            SELECT
                api_key_project_id,
                sum(request_count) AS request_count,
                sum(cost_sum) AS total_cost,
                sum(input_tokens_sum) AS total_input_tokens,
                sum(output_tokens_sum) AS total_output_tokens
            FROM {table.value}
            WHERE {' AND '.join(where_parts)}
            GROUP BY api_key_project_id
            ORDER BY total_cost DESC
            """
        else:
            # Use InferenceFact for user-level filtering
            where_parts_fact = self._build_filter_conditions(
                AnalyticsTable.INFERENCE_FACT, from_date, to_date, {"user_id": user_id}
            )
            query = f"""
            SELECT
                api_key_project_id,
                count() AS request_count,
                sum(COALESCE(cost, 0)) AS total_cost,
                sum(COALESCE(input_tokens, 0)) AS total_input_tokens,
                sum(COALESCE(output_tokens, 0)) AS total_output_tokens
            FROM {AnalyticsTable.INFERENCE_FACT.value}
            WHERE {' AND '.join(where_parts_fact)}
            GROUP BY api_key_project_id
            ORDER BY total_cost DESC
            """

        return query.strip()

    def build_usage_bulk_query(
        self,
        table_result: TableSelectionResult,
        from_date: datetime,
        to_date: datetime,
        user_ids: list[str],
        project_id: Optional[str] = None,
    ) -> str:
        """Build query for bulk usage summary by user.

        Args:
            table_result: Result from select_metrics_table
            from_date: Query start date
            to_date: Query end date
            user_ids: List of user IDs
            project_id: Optional project ID filter

        Returns:
            SQL query string
        """
        # For bulk user queries, always use InferenceFact since rollups don't have user_id
        table = AnalyticsTable.INFERENCE_FACT

        filters = {}
        if project_id:
            filters["project"] = project_id

        where_parts = self._build_filter_conditions(table, from_date, to_date, filters)

        # Add user_id filter
        user_values = ",".join([f"'{self._escape_sql_value(u)}'" for u in user_ids])
        where_parts.append(f"user_id IN ({user_values})")

        query = f"""
        SELECT
            user_id,
            count() AS request_count,
            countIf(is_success = true) AS success_count,
            sum(COALESCE(cost, 0)) AS total_cost,
            sum(COALESCE(input_tokens, 0)) AS total_input_tokens,
            sum(COALESCE(output_tokens, 0)) AS total_output_tokens
        FROM {table.value}
        WHERE {' AND '.join(where_parts)}
        GROUP BY user_id
        """

        return query.strip()

    def build_top_routes_query(
        self,
        from_date: datetime,
        to_date: datetime,
        filters: Optional[dict] = None,
        limit: int = 20,
    ) -> str:
        """Build query for top routes analytics.

        Uses InferenceFact since it has path and method columns.

        Args:
            from_date: Query start date
            to_date: Query end date
            filters: Optional filters (project_id)
            limit: Number of top routes to return

        Returns:
            SQL query string
        """
        table = AnalyticsTable.INFERENCE_FACT
        where_parts = self._build_filter_conditions(table, from_date, to_date, filters)
        where_parts.append("path IS NOT NULL")
        where_parts.append("path != ''")

        query = f"""
        SELECT
            path,
            method,
            count() AS request_count,
            avg(response_time_ms) AS avg_response_time,
            countIf(status_code >= 400) * 100.0 / count() AS error_rate
        FROM {table.value}
        WHERE {' AND '.join(where_parts)}
        GROUP BY path, method
        ORDER BY request_count DESC
        LIMIT {limit}
        """

        return query.strip()

    def build_client_analytics_query(
        self,
        from_date: datetime,
        to_date: datetime,
        group_by: str = "device_type",
        filters: Optional[dict] = None,
    ) -> str:
        """Build query for client analytics (device, browser, OS).

        Uses InferenceFact since it has client metadata columns.

        Args:
            from_date: Query start date
            to_date: Query end date
            group_by: Field to group by (device_type, browser_name, os_name)
            filters: Optional filters

        Returns:
            SQL query string
        """
        table = AnalyticsTable.INFERENCE_FACT

        # Map group_by parameter to column
        field_map = {
            "device_type": "device_type",
            "browser": "browser_name",
            "os": "os_name",
        }
        field = field_map.get(group_by, "device_type")

        where_parts = self._build_filter_conditions(table, from_date, to_date, filters)
        where_parts.append(f"{field} IS NOT NULL")
        where_parts.append(f"{field} != ''")

        query = f"""
        SELECT
            {field},
            count() AS request_count
        FROM {table.value}
        WHERE {' AND '.join(where_parts)}
        GROUP BY {field}
        ORDER BY request_count DESC
        """

        return query.strip()

    def build_latency_distribution_query(
        self,
        from_date: datetime,
        to_date: datetime,
        filters: Optional[dict] = None,
        buckets: int = 20,
    ) -> str:
        """Build query for latency distribution histogram.

        Uses InferenceFact to get raw latency values.

        Args:
            from_date: Query start date
            to_date: Query end date
            filters: Optional filters
            buckets: Number of histogram buckets

        Returns:
            SQL query string
        """
        table = AnalyticsTable.INFERENCE_FACT
        where_parts = self._build_filter_conditions(table, from_date, to_date, filters)
        where_parts.append("response_time_ms IS NOT NULL")

        query = f"""
        SELECT
            quantiles(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99)(response_time_ms) AS latency_percentiles,
            min(response_time_ms) AS min_latency,
            max(response_time_ms) AS max_latency,
            avg(response_time_ms) AS avg_latency,
            count() AS total_requests,
            histogram({buckets})(response_time_ms) AS latency_histogram
        FROM {table.value}
        WHERE {' AND '.join(where_parts)}
        """

        return query.strip()


# Singleton instance for global access
_query_builder: Optional[OTelAnalyticsQueryBuilder] = None


def get_otel_analytics_query_builder() -> OTelAnalyticsQueryBuilder:
    """Get the global OTel analytics query builder instance."""
    global _query_builder
    if _query_builder is None:
        _query_builder = OTelAnalyticsQueryBuilder()
    return _query_builder
