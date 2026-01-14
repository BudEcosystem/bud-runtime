import asyncio
import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, Optional, Union
from uuid import UUID

import asynch
import orjson
from budmicroframe.commons import logging

from budmetrics.commons.config import app_settings, secrets_settings
from budmetrics.commons.profiling_utils import (
    PerformanceMetrics,
    performance_logger,
    profile_async,
    profile_sync,
)


UTC = timezone.utc


class StrEnum(str, Enum):
    pass


logging.skip_module_warnings_and_logs(["asynch"])
logger = logging.get_logger(__name__)


@dataclass
class ClickHouseConfig:
    host: str = app_settings.clickhouse_host
    port: int = app_settings.clickhouse_port  # Native protocol port
    user: str = secrets_settings.clickhouse_user
    password: str = secrets_settings.clickhouse_password
    database: str = app_settings.clickhouse_dbname
    pool_min_size: int = 2
    pool_max_size: int = 20
    query_timeout: int = 300
    connect_timeout: int = 30
    max_concurrent_queries: int = 10  # Semaphore limit
    enable_query_cache: bool = app_settings.clickhouse_enable_query_cache
    query_cache_ttl: int = 600  # 10 minutes
    query_cache_max_size: int = 1000
    enable_connection_warmup: bool = app_settings.clickhouse_enable_connection_warmup
    settings: dict[str, Any] = field(
        default_factory=lambda: {
            "max_execution_time": 300,
            "log_queries": 1,
            "query_id": "",  # Will be set per query
            "send_progress_in_http_headers": 1,
            "wait_end_of_query": 1,
            "max_threads": 8,
            "max_memory_usage": 10000000000,  # 10GB
            "use_uncompressed_cache": 1,
            "load_balancing": "random",
        }
    )


class FrequencyUnit(StrEnum):
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"


@dataclass
class Frequency:
    value: Optional[int]  # None means use standard functions, numeric means align to from_date
    unit: FrequencyUnit

    @classmethod
    def hourly(cls) -> "Frequency":
        """Create an hourly frequency."""
        return cls(None, FrequencyUnit.HOUR)

    @classmethod
    def daily(cls) -> "Frequency":
        """Create a daily frequency."""
        return cls(None, FrequencyUnit.DAY)

    @classmethod
    def weekly(cls) -> "Frequency":
        """Create a weekly frequency."""
        return cls(None, FrequencyUnit.WEEK)

    @classmethod
    def monthly(cls) -> "Frequency":
        """Create a monthly frequency."""
        return cls(None, FrequencyUnit.MONTH)

    @classmethod
    def quarterly(cls) -> "Frequency":
        """Create a quarterly frequency."""
        return cls(None, FrequencyUnit.QUARTER)

    @classmethod
    def yearly(cls) -> "Frequency":
        """Create a yearly frequency."""
        return cls(None, FrequencyUnit.YEAR)

    @classmethod
    def custom(cls, value: int, unit: Union[FrequencyUnit, str]) -> "Frequency":
        """Create custom frequency like every 7 days, every 3 months, etc."""
        if isinstance(unit, str):
            unit = FrequencyUnit(unit)
        return cls(value, unit)

    @property
    def name(self) -> str:
        """Get human-readable name for the frequency."""
        if self.value is None or self.value == 1:
            return self.unit.value + "ly" if isinstance(self.unit, FrequencyUnit) else f"every_{self.unit.value}"
        else:
            return f"every_{self.value}_{self.unit.value}s"

    def to_clickhouse_interval(self, order: Literal["asc", "desc"] = "asc") -> str:
        """Convert to ClickHouse INTERVAL syntax."""
        unit_map = {
            FrequencyUnit.HOUR: "HOUR",
            FrequencyUnit.DAY: "DAY",
            FrequencyUnit.WEEK: "WEEK",
            FrequencyUnit.MONTH: "MONTH",
            FrequencyUnit.QUARTER: "QUARTER",
            FrequencyUnit.YEAR: "YEAR",
        }
        # Default to 1 if value is None (for standard intervals)
        value = self.value if self.value is not None else 1
        return f"INTERVAL {value if order == 'asc' else -value} {unit_map[self.unit]}"

    def __str__(self) -> str:
        """Return string representation of frequency."""
        return self.name


class TimeSeriesHelper:
    """Helper class for time series operations in ClickHouse queries.

    This class provides utilities for:
    - Converting frequency specifications to ClickHouse time functions
    - Generating time bucket expressions for grouping
    - Handling both standard intervals (daily, weekly) and custom aligned intervals
    """

    @staticmethod
    def get_time_format(frequency: Frequency) -> str:
        """Get ClickHouse date truncation function for different frequencies.

        For custom intervals, we'll use a different approach in the query.

        Args:
            frequency: Frequency object specifying the interval

        Returns:
            ClickHouse function string or None for custom intervals
        """
        # If frequency value is None, use ClickHouse's built-in functions
        if frequency.value is None:
            formats = {
                FrequencyUnit.HOUR: "toStartOfHour",
                FrequencyUnit.DAY: "toDate",
                FrequencyUnit.WEEK: "toStartOfWeek",
                FrequencyUnit.MONTH: "toStartOfMonth",
                FrequencyUnit.QUARTER: "toStartOfQuarter",
                FrequencyUnit.YEAR: "toStartOfYear",
            }
            return formats.get(frequency.unit, "toDate") + "({time_field})"
        else:
            # For any numeric interval (including 1), we'll handle with custom logic
            return None  # Signal that we need custom handling

    @staticmethod
    def get_time_bucket_expression(frequency: Frequency, time_field: str, from_date: Optional[datetime] = None) -> str:
        """Generate ClickHouse expression for time buckets.

        - If frequency.value is None: Use standard ClickHouse functions (toStartOfWeek, etc.)
        - If frequency.value is numeric (including 1): Align buckets to from_date
        """
        # Check if we should use standard functions
        time_func = TimeSeriesHelper.get_time_format(frequency)
        if time_func is not None:
            return time_func.format(time_field=time_field)

        # For numeric intervals, align to from_date
        if from_date and frequency.value is not None:
            # Calculate buckets aligned to from_date
            interval_seconds = TimeSeriesHelper._get_interval_seconds(frequency)
            from_timestamp = f"toUnixTimestamp('{from_date.strftime('%Y-%m-%d %H:%M:%S')}')"

            # Formula: from_date + floor((timestamp - from_date) / interval) * interval
            return (
                f"toDateTime("
                f"{from_timestamp} + "
                f"floor((toUnixTimestamp({time_field}) - {from_timestamp}) / {interval_seconds}) * {interval_seconds}"
                f")"
            )
        else:
            # Fallback to toStartOfInterval
            return f"toStartOfInterval({time_field}, {frequency.to_clickhouse_interval()})"

    @staticmethod
    def _get_interval_seconds(frequency: Frequency) -> int:
        """Convert frequency to seconds for custom interval calculation."""
        unit_seconds = {
            FrequencyUnit.HOUR: 3600,
            FrequencyUnit.DAY: 86400,
            FrequencyUnit.WEEK: 604800,
            FrequencyUnit.MONTH: 2592000,  # Approximate (30 days)
            FrequencyUnit.QUARTER: 7776000,  # Approximate (90 days)
            FrequencyUnit.YEAR: 31536000,  # Approximate (365 days)
        }
        return frequency.value * unit_seconds.get(frequency.unit, 86400)


@dataclass
class CTEDefinition:
    """Definition for a Common Table Expression."""

    name: str
    query: str  # Can contain placeholders like {from_date}, {to_date}, {filters}, {group_columns}
    base_tables: list[str]  # Actual tables this CTE depends on
    is_template: bool = False  # Whether the query contains placeholders


@dataclass
class MetricDefinition:
    metrics_name: str
    required_tables: list[str]
    select_clause: str
    select_alias: str
    # Optional CTE that this metric depends on
    cte_definition: Optional[CTEDefinition] = None
    # Optional topk CTE configuration
    topk_cte_query: Optional[str] = None  # Custom query for topk ranking
    topk_sort_order: Optional[Literal["ASC", "DESC"]] = None  # Sort order for ranking


class QueryBuilder:
    """Core query builder for ClickHouse analytics queries.

    This class is responsible for:
    - Constructing complex SQL queries based on metric requirements
    - Managing table joins and CTEs (Common Table Expressions)
    - Handling time series bucketing and aggregations
    - Supporting filtering, grouping, and TopK operations

    The builder uses a composable pattern where each metric type has its own
    definition method that returns MetricDefinition objects. These are then
    combined to build the final query.

    Attributes:
        _MAPPING_COLUMNS: Maps API field names to database columns
        _MAPPING_TABLE_ALIAS: Maps table names to their query aliases
        metric_type: Registry of available metric types and their builders
    """

    _MAPPING_COLUMNS = {
        "model": "mid.model_id",
        "project": "mid.project_id",
        "endpoint": "mid.endpoint_id",
        "user_project": "mid.api_key_project_id",
    }
    _MAPPING_TABLE_ALIAS = {
        "ModelInference": "mi",
        "ModelInferenceDetails": "mid",
        "InferenceFact": "ifact",
    }

    # InferenceFact column mappings (for raw data queries using InferenceFact)
    _INFERENCE_FACT_MAPPING_COLUMNS = {
        "model": "ifact.model_id",
        "project": "ifact.project_id",
        "endpoint": "ifact.endpoint_id",
        "user_project": "ifact.api_key_project_id",
    }

    # Rollup table column mappings (for rollup queries)
    _ROLLUP_MAPPING_COLUMNS = {
        "model": "model_id",
        "project": "project_id",
        "endpoint": "endpoint_id",
        "user_project": "api_key_project_id",
    }

    # Metrics that can be served from rollup tables (pre-aggregated)
    ROLLUP_COMPATIBLE_METRICS = {
        "request_count",
        "success_request",
        "failure_request",
        "input_token",
        "output_token",
        "cache",
        "throughput",
    }

    # Metrics that always require raw data (InferenceFact) for percentiles or timestamps
    REQUIRES_RAW_DATA_METRICS = {
        "queuing_time",
        "concurrent_requests",
        "latency",  # Requires raw data for p95/p99 percentiles
        "ttft",  # Requires raw data for p95/p99 percentiles
    }

    def __init__(self, performance_metrics: Optional[PerformanceMetrics] = None):
        """Initialize TimeSeriesHelper with optional performance metrics."""
        self.time_helper = TimeSeriesHelper()
        self.performance_metrics = performance_metrics

        self.datetime_fmt = "%Y-%m-%d %H:%M:%S"

        self.metric_type = {
            "request_count": self._get_request_count_metrics_definitions,
            "success_request": self._get_success_request_metrics_definitions,
            "failure_request": self._get_failure_request_metrics_definitions,
            "queuing_time": self._get_queuing_time_metrics_definitions,
            "input_token": self._get_input_token_metrics_definitions,
            "output_token": self._get_output_token_metrics_definitions,
            "concurrent_requests": self._get_concurrent_requests_metrics_definitions,
            "ttft": self._get_ttft_metrics_definitions,
            "latency": self._get_latency_metrics_definitions,
            "throughput": self._get_throughput_metrics_definitions,
            "cache": self._get_cache_metrics_definitions,
        }

    def can_use_rollup(self, metrics: list[str]) -> bool:
        """Check if all requested metrics can be served from rollup tables.

        Rollup tables have pre-aggregated counts and sums but cannot provide:
        - Percentiles (p95, p99) - need raw latency values
        - Queuing time - needs raw timestamps
        - Concurrent requests - needs raw timestamps

        Args:
            metrics: List of metric types requested

        Returns:
            True if all metrics can use rollup tables, False otherwise
        """
        for metric in metrics:
            # Metrics that always require raw data
            if metric in self.REQUIRES_RAW_DATA_METRICS:
                return False
            # Check if metric is known and compatible
            if metric not in self.ROLLUP_COMPATIBLE_METRICS:
                # Unknown metric - fall back to raw data
                return False
        return True

    def _select_rollup_table(
        self,
        from_date: datetime,
        to_date: datetime,
        frequency_unit: Optional[str] = None,
    ) -> str:
        """Select optimal rollup table based on time range and granularity.

        Table selection logic:
        - InferenceMetrics5m: Recent data (< 6 hours) or hourly frequency
        - InferenceMetrics1h: Short-term (6 hours - 7 days) or daily frequency
        - InferenceMetrics1d: Long-term (> 7 days) or weekly/monthly frequency

        Args:
            from_date: Start of the query time range
            to_date: End of the query time range
            frequency_unit: Optional frequency hint (hour, day, week, month)

        Returns:
            Table name to query
        """
        # Frequency-based selection (most accurate)
        if frequency_unit:
            if frequency_unit == "hour":
                return "InferenceMetrics5m"
            elif frequency_unit == "day":
                return "InferenceMetrics1h"
            elif frequency_unit in ("week", "month", "quarter", "year"):
                return "InferenceMetrics1d"

        # Time range-based selection (fallback)
        time_range = to_date - from_date
        total_hours = time_range.total_seconds() / 3600

        if total_hours < 6:
            return "InferenceMetrics5m"
        elif time_range.days < 7:
            return "InferenceMetrics1h"
        else:
            return "InferenceMetrics1d"

    def build_rollup_query(
        self,
        metrics: list[str],
        from_date: datetime,
        to_date: datetime,
        frequency_unit: str = "day",
        frequency_interval: Optional[int] = None,
        filters: Optional[dict[str, Union[list[UUID], UUID]]] = None,
        group_by: Optional[list[str]] = None,
        return_delta: bool = False,
        fill_time_gaps: bool = True,
        topk: Optional[int] = None,
    ) -> tuple[str, list[str]]:
        """Build query against rollup tables (InferenceMetrics5m/1h/1d).

        Uses pre-aggregated data for better performance on large time ranges.
        Supports delta calculations via window functions and time gap filling.

        Args:
            metrics: List of metrics to retrieve
            from_date: Start of the query time range
            to_date: End of the query time range
            frequency_unit: Time bucket granularity (hour, day, week, month)
            frequency_interval: Custom interval value
            filters: Optional filters (project, model, endpoint)
            group_by: Optional grouping fields
            return_delta: Whether to include delta calculations
            fill_time_gaps: Whether to fill time gaps with zeros
            topk: Optional limit for top K results

        Returns:
            Tuple of (query_string, field_order_list)
        """
        # Handle optional to_date (default to now)
        to_date = datetime.now(UTC) if to_date is None else to_date

        # Select appropriate rollup table
        table = self._select_rollup_table(from_date, to_date, frequency_unit)

        # Build time bucket expression based on frequency and interval
        time_bucket_expr = self._get_rollup_time_bucket_expr(frequency_unit, frequency_interval, from_date)

        # Build field order list
        field_order = ["time_bucket"]

        # Add group by fields
        group_by_fields = []
        if group_by:
            for field in group_by:
                col = self._ROLLUP_MAPPING_COLUMNS.get(field)
                if col:
                    group_by_fields.append(col)
                    field_order.append(col)

        # Add metric aggregations
        metric_select, metric_fields = self._build_rollup_metric_select(metrics)
        field_order.extend(metric_fields)

        # Extract SQL aliases from metric_select (e.g., "sum(x) AS alias" -> "alias")
        metric_sql_aliases = []
        for clause in metric_select:
            if " AS " in clause:
                alias = clause.split(" AS ")[-1].strip()
                metric_sql_aliases.append(alias)

        # Build WHERE conditions
        conditions = [
            f"time_bucket >= '{from_date.strftime(self.datetime_fmt)}'",
            f"time_bucket <= '{to_date.strftime(self.datetime_fmt)}'",
        ]

        # Add filter conditions
        if filters:
            for key, value in filters.items():
                col = self._ROLLUP_MAPPING_COLUMNS.get(key.lower())
                if col:
                    if isinstance(value, list) and len(value):
                        conditions.append(f"{col} IN (" + ",".join([f"'{str(v)}'" for v in value]) + ")")
                    else:
                        conditions.append(f"{col} = '{str(value)}'")

        # Use a different alias for the time bucket to avoid shadowing the column in WHERE clause
        # This prevents ClickHouse from resolving time_bucket in WHERE to the alias instead of the column
        time_bucket_alias = "period_bucket"

        # Build GROUP BY clause for inner query
        inner_group_by_cols = [time_bucket_alias] + group_by_fields
        group_by_sql = f"GROUP BY {', '.join(inner_group_by_cols)}"

        # Build inner SELECT fields (aggregation query)
        inner_select = [f"{time_bucket_expr} AS {time_bucket_alias}"]
        inner_select.extend(group_by_fields)
        inner_select.extend(metric_select)

        # Build inner aggregation query
        inner_query = f"""
            SELECT {', '.join(inner_select)}
            FROM {table}
            WHERE {' AND '.join(conditions)}
            {group_by_sql}
        """

        # Build WITH FILL expression for time gap filling
        fill_expr = ""
        if fill_time_gaps:
            frequency = Frequency(frequency_interval, FrequencyUnit(frequency_unit))
            # For week/month/quarter/year, the time bucket returns Date type, so use toDate()
            # For hour/day, the time bucket returns DateTime type, so use toDateTime()
            if frequency_unit in ("week", "month", "quarter", "year"):
                fill_expr = f"WITH FILL FROM toDate('{from_date.strftime('%Y-%m-%d')}') TO toDate('{to_date.strftime('%Y-%m-%d')}') STEP {frequency.to_clickhouse_interval('asc')}"
            else:
                fill_expr = f"WITH FILL FROM toDateTime('{from_date.strftime(self.datetime_fmt)}') TO toDateTime('{to_date.strftime(self.datetime_fmt)}') STEP {frequency.to_clickhouse_interval('asc')}"

        # Build outer SELECT fields (rename period_bucket back to time_bucket for API compatibility)
        outer_select = [f"{time_bucket_alias} AS time_bucket"]
        outer_select.extend(group_by_fields)
        outer_select.extend(metric_sql_aliases)

        # Add delta expressions if requested (use SQL aliases for window functions)
        if return_delta:
            # Zip SQL aliases with semantic field names to build delta expressions
            for sql_alias, semantic_name in zip(metric_sql_aliases, metric_fields):
                delta_clauses, delta_field_names = self._build_rollup_delta_expressions(
                    sql_alias, semantic_name, time_bucket_alias, group_by_fields if group_by_fields else None
                )
                outer_select.extend(delta_clauses)
                field_order.extend(delta_field_names)

        # Build final query with subquery structure
        if topk and group_by_fields:
            # Get primary metric for ranking (first metric or request_count)
            rank_metric = metric_sql_aliases[0] if metric_sql_aliases else "request_count"

            # Build ranking CTE to identify top K groups
            topk_group_cols = ", ".join(group_by_fields)
            ranking_cte = f"""
            topk_groups AS (
                SELECT {topk_group_cols}
                FROM ({inner_query}) AS rank_agg
                GROUP BY {topk_group_cols}
                ORDER BY SUM({rank_metric}) DESC
                LIMIT {topk}
            )
            """

            # Build join conditions for topk filtering
            topk_join_conditions = [f"agg.{col} = tg.{col}" for col in group_by_fields]
            topk_join = f"INNER JOIN topk_groups tg ON {' AND '.join(topk_join_conditions)}"

            query = f"""
            WITH {ranking_cte}
            SELECT {', '.join(outer_select)}
            FROM ({inner_query}) AS agg
            {topk_join}
            ORDER BY {time_bucket_alias} ASC {fill_expr}
            """
        else:
            query = f"""
            SELECT {', '.join(outer_select)}
            FROM ({inner_query}) AS agg
            ORDER BY {time_bucket_alias} ASC {fill_expr}
            """

        return query, field_order

    def _get_rollup_time_bucket_expr(
        self,
        frequency_unit: str,
        frequency_interval: Optional[int] = None,
        from_date: Optional[datetime] = None,
    ) -> str:
        """Get ClickHouse time bucket expression for rollup queries.

        Args:
            frequency_unit: Time bucket unit (hour, day, week, etc.)
            frequency_interval: Custom interval multiplier (e.g., 2 for 2-hour buckets)
            from_date: Start date for custom interval alignment

        Returns:
            ClickHouse expression for time bucketing
        """
        # If frequency_interval is provided and > 1, use custom interval formula
        if frequency_interval is not None and frequency_interval > 1 and from_date is not None:
            # Calculate interval in seconds
            unit_seconds = {
                "hour": 3600,
                "day": 86400,
                "week": 604800,
                "month": 2592000,  # Approximate (30 days)
                "quarter": 7776000,  # Approximate (90 days)
                "year": 31536000,  # Approximate (365 days)
            }
            interval_seconds = frequency_interval * unit_seconds.get(frequency_unit, 86400)
            from_timestamp = f"toUnixTimestamp('{from_date.strftime('%Y-%m-%d %H:%M:%S')}')"

            # Formula: from_date + floor((timestamp - from_date) / interval) * interval
            return (
                f"toDateTime("
                f"{from_timestamp} + "
                f"floor((toUnixTimestamp(time_bucket) - {from_timestamp}) / {interval_seconds}) * {interval_seconds}"
                f")"
            )

        # Standard functions for single-unit intervals
        time_bucket_map = {
            "hour": "toStartOfHour(time_bucket)",
            "day": "toStartOfDay(time_bucket)",
            "week": "toMonday(time_bucket)",
            "month": "toStartOfMonth(time_bucket)",
            "quarter": "toStartOfQuarter(time_bucket)",
            "year": "toStartOfYear(time_bucket)",
        }
        return time_bucket_map.get(frequency_unit, "toStartOfDay(time_bucket)")

    def _build_rollup_metric_select(self, metrics: list[str]) -> tuple[list[str], list[str]]:
        """Build SELECT clauses for rollup metrics.

        Maps metric names to rollup table columns with proper aggregations.

        Args:
            metrics: List of metric types

        Returns:
            Tuple of (select_clauses, field_names)
        """
        select_clauses = []
        field_names = []

        for metric in metrics:
            if metric == "request_count":
                # Use alias 'req_count_sum' to avoid collision with column name 'request_count'
                select_clauses.append("sum(request_count) AS req_count_sum")
                field_names.append("request_count")

            elif metric == "success_request":
                select_clauses.append("sum(success_count) AS success_request_count")
                select_clauses.append(
                    "if(sum(request_count) > 0, sum(success_count) * 100.0 / sum(request_count), 0) AS success_rate"
                )
                field_names.extend(["success_request_count", "success_rate"])

            elif metric == "failure_request":
                select_clauses.append("sum(error_count) AS failure_request_count")
                select_clauses.append(
                    "if(sum(request_count) > 0, sum(error_count) * 100.0 / sum(request_count), 0) AS failure_rate"
                )
                field_names.extend(["failure_request_count", "failure_rate"])

            elif metric == "input_token":
                select_clauses.append("sum(total_input_tokens) AS input_token_count")
                field_names.append("input_token_count")

            elif metric == "output_token":
                select_clauses.append("sum(total_output_tokens) AS output_token_count")
                field_names.append("output_token_count")

            elif metric == "cache":
                select_clauses.append("sum(cached_count) AS cache_hit_count")
                select_clauses.append(
                    "if(sum(request_count) > 0, sum(cached_count) * 100.0 / sum(request_count), 0) AS cache_hit_rate"
                )
                field_names.extend(["cache_hit_count", "cache_hit_rate"])

            elif metric == "latency":
                # Average latency from sum/count
                select_clauses.append(
                    "if(sum(request_count) > 0, sum(sum_response_time_ms) / sum(request_count), 0) AS avg_latency_ms"
                )
                select_clauses.append("min(min_response_time_ms) AS min_latency_ms")
                select_clauses.append("max(max_response_time_ms) AS max_latency_ms")
                field_names.extend(["avg_latency_ms", "min_latency_ms", "max_latency_ms"])

            elif metric == "ttft":
                # Average TTFT from sum/count
                select_clauses.append(
                    "if(sum(request_count) > 0, sum(sum_ttft_ms) / sum(request_count), 0) AS avg_ttft_ms"
                )
                field_names.append("avg_ttft_ms")

            elif metric == "throughput":
                # Weighted average throughput: total output tokens / total response time
                select_clauses.append(
                    "if(sum(sum_response_time_ms) > 0, "
                    "sum(total_output_tokens) * 1000.0 / sum(sum_response_time_ms), 0) "
                    "AS avg_throughput_tokens_per_sec"
                )
                field_names.append("avg_throughput_tokens_per_sec")

        return select_clauses, field_names

    def _build_rollup_delta_expressions(
        self,
        sql_alias: str,
        semantic_name: str,
        time_bucket_alias: str,
        group_by_fields: Optional[list[str]] = None,
    ) -> tuple[list[str], list[str]]:
        """Build delta window function expressions for rollup queries.

        Uses lagInFrame to calculate previous value, delta, and percent change
        for time series metrics.

        Args:
            sql_alias: The SQL column alias from inner query (e.g., 'req_count_sum')
            semantic_name: The semantic field name for API response (e.g., 'request_count')
            time_bucket_alias: The time bucket column alias
            group_by_fields: Optional list of grouping fields for PARTITION BY

        Returns:
            Tuple of (select_clauses, field_names)
        """
        # SQL aliases use the actual column name from inner query
        sql_previous = f"previous_{sql_alias}"
        sql_delta = f"{sql_alias}_delta"
        sql_percent = f"{sql_alias}_percent_change"

        # Semantic field names use the API field name for field_order
        semantic_previous = f"previous_{semantic_name}"
        semantic_delta = f"{semantic_name}_delta"
        semantic_percent = f"{semantic_name}_percent_change"

        # Build PARTITION BY clause if grouping
        partition_clause = ""
        if group_by_fields:
            partition_clause = f"PARTITION BY {', '.join(group_by_fields)} "

        window_spec = (
            f"OVER ({partition_clause}ORDER BY {time_bucket_alias} ASC "
            f"ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING)"
        )

        # SQL clauses use SQL aliases for the actual query
        select_clauses = [
            f"lagInFrame({sql_alias}, 1, {sql_alias}) {window_spec} AS {sql_previous}",
            f"COALESCE(ROUND({sql_alias} - {sql_previous}, 2)) AS {sql_delta}",
            f"COALESCE(ROUND(({sql_delta} / NULLIF({sql_previous}, 0)) * 100, 2)) AS {sql_percent}",
        ]

        # Field names use semantic names for the services layer to map correctly
        field_names = [semantic_previous, semantic_delta, semantic_percent]
        return select_clauses, field_names

    def _get_table_join_clause(
        self,
        required_tables: list[str],
        cte_registry: Optional[dict[str, CTEDefinition]] = None,
        group_by_fields: Optional[list[str]] = None,
    ):
        model_inference_alias = self._MAPPING_TABLE_ALIAS["ModelInference"]
        model_inference_details_alias = self._MAPPING_TABLE_ALIAS["ModelInferenceDetails"]

        # Initialize CTE registry if not provided
        cte_registry = cte_registry or {}

        # Separate CTEs from actual tables
        cte_tables = [t for t in required_tables if t in cte_registry]
        base_tables = [t for t in required_tables if t not in cte_registry]

        # If we have CTEs, we need to include their base tables
        for cte_name in cte_tables:
            if cte_name in cte_registry:
                base_tables.extend(cte_registry[cte_name].base_tables)

        # Remove duplicates
        base_tables = list(set(base_tables))

        # Build FROM clause with CTEs
        from_parts = []

        # Add base tables
        if "ModelInference" in base_tables and "ModelInferenceDetails" in base_tables:
            from_parts.append(
                f"ModelInference {model_inference_alias} INNER JOIN ModelInferenceDetails {model_inference_details_alias} ON {model_inference_alias}.inference_id = {model_inference_details_alias}.inference_id"
            )
        elif "ModelInference" in base_tables:
            from_parts.append(f"ModelInference {self._MAPPING_TABLE_ALIAS['ModelInference']}")
        elif "ModelInferenceDetails" in base_tables:
            from_parts.append(f"ModelInferenceDetails {self._MAPPING_TABLE_ALIAS['ModelInferenceDetails']}")
        elif "InferenceFact" in base_tables:
            from_parts.append(f"InferenceFact {self._MAPPING_TABLE_ALIAS['InferenceFact']}")

        # Add CTEs as joins
        inference_fact_alias = self._MAPPING_TABLE_ALIAS["InferenceFact"]
        for cte_name in cte_tables:
            if from_parts and ("ModelInferenceDetails" in base_tables or "InferenceFact" in base_tables):
                # Determine the table alias for join conditions
                if "InferenceFact" in base_tables:
                    table_alias = inference_fact_alias
                else:
                    table_alias = model_inference_details_alias

                # If we have base tables, join the CTE
                # For concurrent_counts CTE, we use LEFT JOIN to handle cases with no concurrency
                join_conditions = [f"cc.request_arrival_time = {table_alias}.request_arrival_time"]

                # Add group by fields to join conditions
                if group_by_fields:
                    for field in group_by_fields:
                        col_name = field.split(".")[-1]  # Extract column name
                        join_conditions.append(f"cc.{col_name} = {field}")

                # Use LEFT JOIN for concurrent_counts to handle cases with no concurrency
                join_type = "LEFT JOIN" if cte_name == "concurrent_counts" else "INNER JOIN"
                from_parts.append(f"{join_type} {cte_name} cc ON {' AND '.join(join_conditions)}")
            else:
                # If no base tables, CTE is the main table
                from_parts.append(f"{cte_name} cc")

        if not from_parts:
            raise ValueError("No valid tables specified")

        return f"FROM {' '.join(from_parts)}"

    def _get_filter_conditions(
        self,
        required_tables: list[str],
        from_date: datetime,
        to_date: datetime,
        filters: Optional[dict[str, Union[list[UUID], UUID]]] = None,
        include_table_prefix: bool = True,
        include_date_filters: bool = True,
    ):
        """Build filter conditions for queries.

        Args:
            required_tables: List of required tables
            from_date: Start date for filtering
            to_date: End date for filtering
            filters: Optional filters dictionary
            include_table_prefix: Whether to include table aliases (mid., mi.)
            include_date_filters: Whether to include date range filters

        Returns:
            List of filter condition strings
        """
        conditions = []

        if include_date_filters:
            # Determine time field based on table being used
            if "InferenceFact" in required_tables:
                time_field = "ifact.request_arrival_time"
            elif "ModelInferenceDetails" in required_tables:
                time_field = "mid.request_arrival_time"
            else:
                time_field = "mi.timestamp"

            # Remove prefix if not needed (for CTEs)
            if not include_table_prefix:
                time_field = time_field.split(".")[-1]

            conditions.append(f"{time_field} >= '{from_date.strftime(self.datetime_fmt)}'")
            conditions.append(f"{time_field} <= '{to_date.strftime(self.datetime_fmt)}'")

        if filters is not None:
            # Choose column mapping based on table being used
            if "InferenceFact" in required_tables:
                col_mapping_dict = self._INFERENCE_FACT_MAPPING_COLUMNS
            else:
                col_mapping_dict = self._MAPPING_COLUMNS

            for key, value in filters.items():
                if col_mapping := col_mapping_dict.get(key.lower(), None):
                    if not value:
                        raise ValueError(
                            f"{key} filter expected type list[UUID] or UUID, but got type {type(value).__name__}"
                        )

                    # Use mapped column or remove prefix based on flag
                    col_name = col_mapping if include_table_prefix else col_mapping.split(".")[-1]

                    if isinstance(value, list) and len(value):
                        conditions.append(f"{col_name} IN (" + ",".join([f"'{str(val)}'" for val in value]) + ")")
                    else:
                        conditions.append(f"{col_name}='{str(value)}'")
                else:
                    raise ValueError(
                        f"{key} is not a supported filter. Choose from ({', '.join(col_mapping_dict)})"
                    )

        return conditions

    def _get_group_by_fields(self, fields: Optional[list[str]], use_inference_fact: bool = False):
        if not fields:
            return []

        # Choose column mapping based on table being used
        col_mapping_dict = self._INFERENCE_FACT_MAPPING_COLUMNS if use_inference_fact else self._MAPPING_COLUMNS

        group_by_fields = []
        for field in fields:
            if value := col_mapping_dict.get(field):
                group_by_fields.append(value)
            else:
                raise ValueError(
                    f"{field} is not a supported field for grouping. Choose from ({', '.join(col_mapping_dict)})"
                )

        return group_by_fields

    def _get_request_count_metrics_definitions(
        self,
        time_period_bin_alias: str,
        incl_delta: bool = False,
        group_by_fields: Optional[list[str]] = None,
        filters: Optional[dict[str, Union[list[UUID], UUID]]] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> list[MetricDefinition]:
        req_count_alias = "request_count"
        metric = MetricDefinition(
            metrics_name="request_count",
            required_tables=["InferenceFact"],
            select_clause=f"COUNT(ifact.inference_id) AS {req_count_alias}",
            select_alias=req_count_alias,
        )
        metric_delta = []
        if incl_delta:
            metric_delta = self._get_metrics_trend_definitions(req_count_alias, time_period_bin_alias, group_by_fields)

        return [metric, *metric_delta]

    def _get_success_request_metrics_definitions(
        self,
        time_period_bin_alias: str,
        incl_delta: bool = False,
        group_by_fields: Optional[list[str]] = None,
        filters: Optional[dict[str, Union[list[UUID], UUID]]] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> list[MetricDefinition]:
        success_req_count_alias = "success_request_count"
        metrics = [
            MetricDefinition(
                metrics_name="success_request",
                required_tables=["InferenceFact"],
                select_clause=f"SUM(CASE WHEN ifact.is_success THEN 1 ELSE 0 END) AS {success_req_count_alias}",
                select_alias=success_req_count_alias,
            ),
            MetricDefinition(
                metrics_name="success_request",
                required_tables=["InferenceFact"],
                select_clause="AVG(CASE WHEN ifact.is_success THEN 1 ELSE 0 END) * 100 AS success_rate",
                select_alias="success_rate",
            ),
        ]
        metric_delta = []
        if incl_delta:
            metric_delta = self._get_metrics_trend_definitions(
                success_req_count_alias, time_period_bin_alias, group_by_fields
            )

        return [*metrics, *metric_delta]

    def _get_failure_request_metrics_definitions(
        self,
        time_period_bin_alias: str,
        incl_delta: bool = False,
        group_by_fields: Optional[list[str]] = None,
        filters: Optional[dict[str, Union[list[UUID], UUID]]] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> list[MetricDefinition]:
        failure_req_count_alias = "failure_request_count"
        metrics = [
            MetricDefinition(
                metrics_name="failure_request",
                required_tables=["InferenceFact"],
                select_clause=f"SUM(CASE WHEN NOT ifact.is_success THEN 1 ELSE 0 END) AS {failure_req_count_alias}",
                select_alias=failure_req_count_alias,
            ),
            MetricDefinition(
                metrics_name="failure_request",
                required_tables=["InferenceFact"],
                select_clause="AVG(CASE WHEN NOT ifact.is_success THEN 1 ELSE 0 END) * 100 AS failure_rate",
                select_alias="failure_rate",
            ),
        ]
        metric_delta = []
        if incl_delta:
            metric_delta = self._get_metrics_trend_definitions(
                failure_req_count_alias, time_period_bin_alias, group_by_fields
            )

        return [*metrics, *metric_delta]

    def _get_queuing_time_metrics_definitions(
        self,
        time_period_bin_alias: str,
        incl_delta: bool = False,
        group_by_fields: Optional[list[str]] = None,
        filters: Optional[dict[str, Union[list[UUID], UUID]]] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> list[MetricDefinition]:
        queuing_time_alias = "avg_queuing_time_ms"
        metric = MetricDefinition(
            metrics_name="queuing_time",
            required_tables=["InferenceFact"],
            select_clause=f"AVG(toUnixTimestamp64Milli(ifact.request_forward_time) - toUnixTimestamp64Milli(ifact.request_arrival_time)) AS {queuing_time_alias}",
            select_alias=queuing_time_alias,
            topk_sort_order="ASC",  # Lower queuing time is better
        )
        metric_delta = []
        if incl_delta:
            metric_delta = self._get_metrics_trend_definitions(
                queuing_time_alias, time_period_bin_alias, group_by_fields
            )

        return [metric, *metric_delta]

    def _get_input_token_metrics_definitions(
        self,
        time_period_bin_alias: str,
        incl_delta: bool = False,
        group_by_fields: Optional[list[str]] = None,
        filters: Optional[dict[str, Union[list[UUID], UUID]]] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> list[MetricDefinition]:
        input_token_alias = "input_token_count"
        metric = MetricDefinition(
            metrics_name="input_token",
            required_tables=["InferenceFact"],
            select_clause=f"SUM(ifact.input_tokens) AS {input_token_alias}",
            select_alias=input_token_alias,
        )
        metric_delta = []
        if incl_delta:
            metric_delta = self._get_metrics_trend_definitions(
                input_token_alias, time_period_bin_alias, group_by_fields
            )

        return [metric, *metric_delta]

    def _get_output_token_metrics_definitions(
        self,
        time_period_bin_alias: str,
        incl_delta: bool = False,
        group_by_fields: Optional[list[str]] = None,
        filters: Optional[dict[str, Union[list[UUID], UUID]]] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> list[MetricDefinition]:
        output_token_alias = "output_token_count"
        metric = MetricDefinition(
            metrics_name="output_token",
            required_tables=["InferenceFact"],
            select_clause=f"SUM(ifact.output_tokens) AS {output_token_alias}",
            select_alias=output_token_alias,
        )
        metric_delta = []
        if incl_delta:
            metric_delta = self._get_metrics_trend_definitions(
                output_token_alias, time_period_bin_alias, group_by_fields
            )

        return [metric, *metric_delta]

    def _get_concurrent_requests_metrics_definitions(
        self,
        time_period_bin_alias: str,
        incl_delta: bool = False,
        group_by_fields: Optional[list[str]] = None,
        filters: Optional[dict[str, Union[list[UUID], UUID]]] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> list[MetricDefinition]:
        concurrent_alias = "max_concurrent_requests"

        # Build dynamic GROUP BY clause for CTE
        group_by_columns = ["request_arrival_time"]
        select_columns = ["request_arrival_time"]

        # Add group by fields if provided (these are already processed like mid.project_id)
        if group_by_fields:
            # Extract just the column names for both select and group by
            for field in group_by_fields:
                # field is like "mid.project_id", we need just "project_id"
                col_name = field.split(".")[-1]
                select_columns.append(col_name)
                group_by_columns.append(col_name)

        # Create CTE template for concurrent requests calculation
        cte_template = f"""
            SELECT
                {", ".join(select_columns)},
                COUNT(*) as concurrent_count
            FROM InferenceFact
            WHERE request_arrival_time >= '{{from_date}}'
              AND request_arrival_time <= '{{to_date}}'
              {{filters}}
            GROUP BY {", ".join(group_by_columns)}
            HAVING COUNT(*) > 1
            """

        cte_def = CTEDefinition(
            name="concurrent_counts",
            query=cte_template,
            base_tables=["InferenceFact"],
            is_template=True,
        )

        # Build topk CTE query template for concurrent requests
        topk_cte_query = f"""(
            SELECT {{group_columns}}, MAX(concurrent_count) as rank_value
            FROM (
                SELECT
                    {", ".join(select_columns)},
                    COUNT(*) as concurrent_count
                FROM InferenceFact
                WHERE request_arrival_time >= '{{from_date}}'
                  AND request_arrival_time <= '{{to_date}}'
                  {{filters}}
                GROUP BY {", ".join(group_by_columns)}
                HAVING COUNT(*) > 1
            ) AS inner_query
            GROUP BY {{group_columns}}
        )"""

        # Use the CTE in the main metric - we need to join with base table
        # Use COALESCE to return 0 when no concurrent requests exist
        metric = MetricDefinition(
            metrics_name="concurrent_requests",
            required_tables=["InferenceFact", "concurrent_counts"],
            select_clause=f"COALESCE(MAX(cc.concurrent_count), 0) AS {concurrent_alias}",
            select_alias=concurrent_alias,
            cte_definition=cte_def,
            topk_cte_query=topk_cte_query,
        )
        metric_delta = []
        if incl_delta:
            metric_delta = self._get_metrics_trend_definitions(
                concurrent_alias, time_period_bin_alias, group_by_fields
            )

        return [metric, *metric_delta]

    def _get_ttft_metrics_definitions(
        self,
        time_period_bin_alias: str,
        incl_delta: bool = False,
        group_by_fields: Optional[list[str]] = None,
        filters: Optional[dict[str, Union[list[UUID], UUID]]] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> list[MetricDefinition]:
        ttft_alias = "avg_ttft_ms"
        metrics = [
            MetricDefinition(
                metrics_name="ttft",
                required_tables=["InferenceFact"],
                select_clause=f"AVG(ifact.ttft_ms) AS {ttft_alias}",
                select_alias=ttft_alias,
                topk_sort_order="ASC",  # Lower TTFT is better
            ),
            MetricDefinition(
                metrics_name="ttft_p99",
                required_tables=["InferenceFact"],
                select_clause="quantile(0.99)(ifact.ttft_ms) AS ttft_p99",
                select_alias="ttft_p99",
            ),
            MetricDefinition(
                metrics_name="ttft_p95",
                required_tables=["InferenceFact"],
                select_clause="quantile(0.95)(ifact.ttft_ms) AS ttft_p95",
                select_alias="ttft_p95",
            ),
        ]
        metric_delta = []
        if incl_delta:
            metric_delta = self._get_metrics_trend_definitions(ttft_alias, time_period_bin_alias, group_by_fields)

        return [*metrics, *metric_delta]

    def _get_latency_metrics_definitions(
        self,
        time_period_bin_alias: str,
        incl_delta: bool = False,
        group_by_fields: Optional[list[str]] = None,
        filters: Optional[dict[str, Union[list[UUID], UUID]]] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> list[MetricDefinition]:
        latency_alias = "avg_latency_ms"
        metrics = [
            MetricDefinition(
                metrics_name="latency",
                required_tables=["InferenceFact"],
                select_clause=f"AVG(ifact.response_time_ms) AS {latency_alias}",
                select_alias=latency_alias,
                topk_sort_order="ASC",  # Lower latency is better
            ),
            MetricDefinition(
                metrics_name="latency_p99",
                required_tables=["InferenceFact"],
                select_clause="quantile(0.99)(ifact.response_time_ms) AS latency_p99",
                select_alias="latency_p99",
            ),
            MetricDefinition(
                metrics_name="latency_p95",
                required_tables=["InferenceFact"],
                select_clause="quantile(0.95)(ifact.response_time_ms) AS latency_p95",
                select_alias="latency_p95",
            ),
        ]
        metric_delta = []
        if incl_delta:
            metric_delta = self._get_metrics_trend_definitions(latency_alias, time_period_bin_alias, group_by_fields)

        return [*metrics, *metric_delta]

    def _get_throughput_metrics_definitions(
        self,
        time_period_bin_alias: str,
        incl_delta: bool = False,
        group_by_fields: Optional[list[str]] = None,
        filters: Optional[dict[str, Union[list[UUID], UUID]]] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> list[MetricDefinition]:
        throughput_alias = "avg_throughput_tokens_per_sec"
        metric = MetricDefinition(
            metrics_name="throughput",
            required_tables=["InferenceFact"],
            select_clause=f"AVG(ifact.output_tokens * 1000.0 / NULLIF(ifact.response_time_ms, 0)) AS {throughput_alias}",
            select_alias=throughput_alias,
        )
        metric_delta = []
        if incl_delta:
            metric_delta = self._get_metrics_trend_definitions(
                throughput_alias, time_period_bin_alias, group_by_fields
            )

        return [metric, *metric_delta]

    def _get_cache_metrics_definitions(
        self,
        time_period_bin_alias: str,
        incl_delta: bool = False,
        group_by_fields: Optional[list[str]] = None,
        filters: Optional[dict[str, Union[list[UUID], UUID]]] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> list[MetricDefinition]:
        cache_hit_rate_alias = "cache_hit_rate"
        cache_hit_count_alias = "cache_hit_count"
        metrics = [
            MetricDefinition(
                metrics_name="cache_hit_rate",
                required_tables=["InferenceFact"],
                select_clause=f"AVG(CASE WHEN ifact.cached THEN 1 ELSE 0 END) * 100 AS {cache_hit_rate_alias}",
                select_alias=cache_hit_rate_alias,
            ),
            MetricDefinition(
                metrics_name="cache_hit_count",
                required_tables=["InferenceFact"],
                select_clause=f"SUM(CASE WHEN ifact.cached THEN 1 ELSE 0 END) AS {cache_hit_count_alias}",
                select_alias=cache_hit_count_alias,
            ),
            MetricDefinition(
                metrics_name="cache_latency",
                required_tables=["InferenceFact"],
                select_clause="AVG(CASE WHEN ifact.cached THEN ifact.response_time_ms END) AS avg_cache_latency_ms",
                select_alias="avg_cache_latency_ms",
            ),
        ]
        metric_delta = []
        if incl_delta:
            metric_delta = self._get_metrics_trend_definitions(
                cache_hit_rate_alias, time_period_bin_alias, group_by_fields
            )

        return [*metrics, *metric_delta]

    def _get_metrics_trend_definitions(
        self,
        metrics_alias_or_column: str,
        time_period_bin_alias: str,
        group_by_fields: Optional[list[str]] = None,
    ) -> list[MetricDefinition]:
        lag_in_frame_alias = f"previous_{metrics_alias_or_column}"
        delta_alias = f"{metrics_alias_or_column}_delta"
        p_change_alias = f"{metrics_alias_or_column}_percent_change"

        lag_in_frame_query = (
            f"lagInFrame({metrics_alias_or_column}, 1, {metrics_alias_or_column}) OVER (ORDER BY {time_period_bin_alias} ASC ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS {lag_in_frame_alias}"
            if not group_by_fields
            else f"lagInFrame({metrics_alias_or_column}, 1, {metrics_alias_or_column}) OVER (PARTITION BY {', '.join(group_by_fields)} ORDER BY {time_period_bin_alias} ASC ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS {lag_in_frame_alias}"
        )

        return [
            MetricDefinition(
                metrics_name=lag_in_frame_alias,
                required_tables=["InferenceFact"],
                select_clause=lag_in_frame_query,
                select_alias=lag_in_frame_alias,
            ),
            MetricDefinition(
                metrics_name=delta_alias,
                required_tables=["InferenceFact"],
                select_clause=f"COALESCE(ROUND({metrics_alias_or_column} - {lag_in_frame_alias}, 2)) AS {delta_alias}",
                select_alias=delta_alias,
            ),
            MetricDefinition(
                metrics_name=p_change_alias,
                required_tables=["InferenceFact"],
                select_clause=f"COALESCE(ROUND(({delta_alias} / {lag_in_frame_alias}) * 100, 2)) AS {p_change_alias}",
                select_alias=p_change_alias,
            ),
        ]

    def _build_filter_clause(self, filters: Optional[dict[str, Union[list[UUID], UUID]]]) -> str:
        """Build a filter clause string for template substitution.

        Reuses _get_filter_conditions with appropriate flags for CTE usage.
        """
        if not filters:
            return ""

        # Get filter conditions without table prefixes and without date filters
        filter_conditions = self._get_filter_conditions(
            required_tables=["InferenceFact"],  # Dummy, just to satisfy the function
            from_date=datetime.now(),  # Dummy dates
            to_date=datetime.now(),
            filters=filters,
            include_table_prefix=False,  # No table aliases for CTEs
            include_date_filters=False,  # Date filters are handled separately in templates
        )

        return f" AND {' AND '.join(filter_conditions)}" if filter_conditions else ""

    def _process_cte_template(
        self,
        cte_def: CTEDefinition,
        from_date: datetime,
        to_date: datetime,
        filters: Optional[dict[str, Union[list[UUID], UUID]]] = None,
        group_columns: Optional[list[str]] = None,
    ) -> str:
        """Process a CTE template and replace placeholders with actual values."""
        if not cte_def.is_template:
            return cte_def.query

        # Prepare template values
        template_values = {
            "from_date": from_date.strftime(self.datetime_fmt),
            "to_date": to_date.strftime(self.datetime_fmt),
            "filters": self._build_filter_clause(filters),
            "group_columns": ", ".join(group_columns) if group_columns else "",
        }

        # Replace placeholders in the template
        return cte_def.query.format(**template_values)

    def _build_topk_cte(
        self,
        metric_definitions: dict[str, MetricDefinition],
        metrics: list[str],
        group_fields: list[str],
        from_date: datetime,
        to_date: Optional[datetime],
        topk: int,
        filters: Optional[dict[str, Union[list[UUID], UUID]]] = None,
    ) -> Optional[str]:
        """Build a CTE for topk filtering based on the primary metric.

        Returns the CTE string or None if topk is not needed.
        """
        if topk is None or not group_fields:
            return None

        # Use the first metric for ranking, or default to request_count
        primary_metric = metrics[0] if metrics else "request_count"
        metric_def = metric_definitions.get(primary_metric)

        # Build column lists
        topk_group_cols_with_alias = group_fields or []
        topk_group_cols_without_alias = [col.split(".")[-1] for col in topk_group_cols_with_alias]

        from_date = from_date.strftime(self.datetime_fmt)
        to_date = to_date.strftime(self.datetime_fmt)

        # Determine the ranking query
        if metric_def and metric_def.topk_cte_query:
            # Use the custom topk CTE query if provided
            filters_clause = self._build_filter_clause(filters) if filters else ""
            ranking_query = metric_def.topk_cte_query.format(
                group_columns=", ".join(topk_group_cols_without_alias),
                from_date=from_date,
                to_date=to_date,
                filters=filters_clause,
            )
        elif metric_def:
            # Use the metric's select clause as the ranking metric
            ranking_metric = metric_def.select_clause.split(" AS ")[0]

            # Get required tables for the metric
            required_tables = [
                t for t in metric_def.required_tables if t in ["ModelInference", "ModelInferenceDetails", "InferenceFact"]
            ]

            # Ensure InferenceFact is included for grouping
            if "InferenceFact" not in required_tables:
                required_tables.append("InferenceFact")

            # Build the FROM clause
            from_clause = self._get_table_join_clause(required_tables, {}, [])

            # Build the ranking query
            filters_clause = self._build_filter_clause(filters) if filters else ""
            ranking_query = f"""(
                SELECT {", ".join(topk_group_cols_without_alias)}, {ranking_metric} as rank_value
                {from_clause}
                WHERE ifact.request_arrival_time >= '{from_date}'
                  AND ifact.request_arrival_time <= '{(to_date)}'
                  {filters_clause}
                GROUP BY {", ".join(topk_group_cols_without_alias)}
            )"""
        else:
            # Fallback to request count
            filters_clause = self._build_filter_clause(filters) if filters else ""
            ranking_query = f"""(
                SELECT {", ".join(topk_group_cols_without_alias)}, COUNT(*) as rank_value
                FROM InferenceFact inf
                WHERE ifact.request_arrival_time >= '{from_date}'
                  AND ifact.request_arrival_time <= '{(to_date)}'
                  {filters_clause}
                GROUP BY {", ".join(topk_group_cols_without_alias)}
            )"""

        # Determine sort order
        ranking_order = metric_def.topk_sort_order if (metric_def and metric_def.topk_sort_order) else "DESC"

        # Build the complete topk CTE
        topk_cte = f"""topk_entities AS (
            SELECT {", ".join(topk_group_cols_without_alias)}
            FROM {ranking_query} AS ranking_subquery
            ORDER BY rank_value {ranking_order}
            LIMIT {topk}
        )"""

        return topk_cte

    @profile_sync("query_building")
    def build_query(
        self,
        metrics: list[
            Literal[
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
        ],
        from_date: datetime,
        to_date: Optional[datetime] = None,
        frequency_unit: Union[FrequencyUnit, str] = FrequencyUnit.DAY,
        frequency_interval: Optional[int] = None,
        filters: Optional[dict[Literal["model", "project", "endpoint"], Union[list[UUID], UUID]]] = None,
        group_by: Optional[list[Literal["model", "project", "endpoint", "user_project"]]] = None,
        return_delta: bool = False,
        fill_time_gaps: bool = True,
        topk: Optional[int] = None,
    ):
        """Build a complete ClickHouse analytics query.

        This method orchestrates the entire query building process:
        1. Validates and processes input parameters
        2. Determines required metric definitions
        3. Builds CTEs if needed
        4. Constructs the main SELECT query
        5. Adds filtering, grouping, and ordering

        Args:
            metrics: List of metrics to include in the query
            from_date: Start date for the query range
            to_date: End date (defaults to current time)
            frequency_unit: Time bucket unit (hour, day, week, etc.)
            frequency_interval: Custom interval multiplier. If None, uses standard intervals
            filters: Optional filters by model, project, or endpoint UUIDs
            group_by: Fields to group by (model, project, endpoint)
            return_delta: Whether to include period-over-period changes
            fill_time_gaps: Whether to fill missing time periods with NULL
            topk: Limit results to top K entities by primary metric

        Returns:
            Tuple of (query_string, field_order_list)

        Raises:
            ValueError: If invalid metric or filter is specified
        """
        if isinstance(frequency_unit, str):
            if not hasattr(FrequencyUnit, frequency_unit.upper()):
                raise ValueError(
                    f"{frequency_unit} is not a supported frequency unit. Choose from ({', '.join(FrequencyUnit.__members__)})"
                )
            else:
                frequency_unit = getattr(FrequencyUnit, frequency_unit.upper())

        to_date = datetime.now(UTC) if to_date is None else to_date

        # Use None for standard intervals (when frequency_interval is None or 1)
        # Use numeric value for custom intervals that need from_date alignment
        if frequency_interval is None:
            # Standard intervals - use built-in functions
            frequency = Frequency(None, frequency_unit)
        else:
            # Custom intervals - align to from_date
            frequency = Frequency.custom(frequency_interval, frequency_unit)

        time_bucket_alias = "time_bucket"

        group_by = group_by or []
        group_fields = self._get_group_by_fields(group_by, use_inference_fact=True)

        select_parts = []
        select_field_order = []
        required_tables = []
        cte_registry: dict[str, CTEDefinition] = {}  # Local CTE registry for this query
        metric_definitions: dict[str, MetricDefinition] = {}  # Store metric definitions for reuse

        for metric in metrics:
            if metric not in self.metric_type:
                raise ValueError(f"{metric} is not a support metrics. Choose from ({', '.join(self.metric_type)})")

            for item in self.metric_type[metric](
                time_bucket_alias,
                incl_delta=return_delta,
                group_by_fields=group_fields,
                filters=filters,
                from_date=from_date,
                to_date=to_date,
            ):
                select_parts.append(item.select_clause)
                select_field_order.append(item.select_alias)
                required_tables.extend(item.required_tables)

                # Store the primary metric definition (not delta/percent change)
                if item.metrics_name == metric:
                    metric_definitions[metric] = item

                # Register CTE if present
                if item.cte_definition:
                    cte_registry[item.cte_definition.name] = item.cte_definition

        required_tables = list(set(required_tables))

        if group_by and "InferenceFact" not in required_tables:
            required_tables.append("InferenceFact")

        # Determine time column based on table being used
        if "InferenceFact" in required_tables:
            time_column = f"{self._MAPPING_TABLE_ALIAS['InferenceFact']}.request_arrival_time"
        elif "ModelInferenceDetails" in required_tables:
            time_column = f"{self._MAPPING_TABLE_ALIAS['ModelInferenceDetails']}.request_arrival_time"
        else:
            time_column = "mi.timestamp"
        time_bucket_expr = self.time_helper.get_time_bucket_expression(frequency, time_column, from_date)
        time_bucket_expr += f" AS {time_bucket_alias}"

        conditions = self._get_filter_conditions(list(required_tables), from_date, to_date, filters)

        group_by_parts = [time_bucket_alias, *group_fields]
        select_parts = [time_bucket_expr, *group_fields, *select_parts]
        select_field_order = [time_bucket_alias, *group_by, *select_field_order]

        fill_expr = ""
        if fill_time_gaps:
            fill_expr = f"WITH FILL STEP {frequency.to_clickhouse_interval('desc')}"

        # Build CTEs if any
        cte_clauses = []

        # Add topk CTE if needed (only when group_by is specified)
        topk_join_clause = ""
        if topk and group_fields:
            topk_cte = self._build_topk_cte(
                metric_definitions,
                metrics,
                group_fields,
                from_date,
                to_date,
                topk,
                filters,
            )
            if topk_cte:
                cte_clauses.append(topk_cte)

                # Build JOIN clause instead of WHERE subquery to avoid asynch driver issues
                # The asynch library cannot handle nested subqueries in WHERE clauses
                topk_join_conditions = []
                for col in group_fields:
                    col_name = col.split(".")[-1]
                    topk_join_conditions.append(f"{col} = te.{col_name}")
                topk_join_clause = f"INNER JOIN topk_entities te ON {' AND '.join(topk_join_conditions)}"

        if cte_registry:
            for cte_name, cte_def in cte_registry.items():
                # Process template if needed
                cte_query = self._process_cte_template(
                    cte_def,
                    from_date,
                    to_date,
                    filters,
                    ([col.split(".")[-1] for col in group_fields] if group_fields else None),
                )
                cte_clauses.append(f"{cte_name} AS ({cte_query})")

        cte_prefix = f"WITH {', '.join(cte_clauses)}" if cte_clauses else ""

        query = f"""
        {cte_prefix}
        SELECT
            {", ".join(select_parts)}
        {self._get_table_join_clause(required_tables, cte_registry, group_fields)}
        {topk_join_clause}
        WHERE {" AND ".join(conditions)}
        GROUP BY {", ".join(group_by_parts)}
        ORDER BY {time_bucket_alias} DESC
        {fill_expr}
        """

        return query, select_field_order


class QueryCache:
    """Simple LRU cache for query results with TTL support."""

    def __init__(self, max_size: int = 1000, ttl: int = 300):
        """Initialize LRU cache with max size and TTL."""
        self.max_size = max_size
        self.ttl = ttl
        self.cache: dict[str, tuple[Any, float]] = {}
        self.access_order: list[str] = []
        self._lock = asyncio.Lock()

    def _make_key(self, query: str, params: Optional[dict[str, Any]] = None) -> str:
        """Generate cache key from query and params."""
        key_data = {"query": query, "params": params or {}}
        key_str = orjson.dumps(dict(sorted(key_data.items(), key=lambda x: x[0])))
        return hashlib.md5(key_str, usedforsecurity=False).hexdigest()

    async def get(self, query: str, params: Optional[dict[str, Any]] = None) -> Optional[Any]:
        """Get cached result if available and not expired."""
        async with self._lock:
            key = self._make_key(query, params)
            if key in self.cache:
                result, timestamp = self.cache[key]
                if time.time() - timestamp < self.ttl:
                    # Move to end (most recently used)
                    self.access_order.remove(key)
                    self.access_order.append(key)
                    return result
                else:
                    # Expired
                    del self.cache[key]
                    self.access_order.remove(key)
            return None

    async def set(self, query: str, result: Any, params: Optional[dict[str, Any]] = None):
        """Cache query result."""
        async with self._lock:
            key = self._make_key(query, params)

            # If key already exists, remove it from access_order
            if key in self.cache:
                self.access_order.remove(key)

            # Remove oldest entries if cache is full
            while len(self.cache) >= self.max_size:
                oldest_key = self.access_order.pop(0)
                del self.cache[oldest_key]

            self.cache[key] = (result, time.time())
            self.access_order.append(key)

    async def clear(self):
        """Clear all cached entries."""
        async with self._lock:
            self.cache.clear()
            self.access_order.clear()


class ClickHouseClient:
    def __init__(self, config: Optional[ClickHouseConfig] = None):
        """Initialize ClickHouse client with optional config."""
        self.config = config
        self._pool: Optional[asynch.Pool] = None
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._initialized = False
        self._query_cache = None
        # Use shared performance logger in debug mode
        self.performance_metrics = performance_logger.get_metrics()

    async def initialize(self):
        """Initialize the ClickHouse connection pool."""
        if self._initialized:
            return

        config = self.config if self.config is not None else ClickHouseConfig()

        self._pool = asynch.Pool(
            minsize=config.pool_min_size,
            maxsize=config.pool_max_size,
            host=config.host,
            port=config.port,
            user=config.user,
            password=config.password,
            database=config.database,
            connect_timeout=config.connect_timeout,
            server_settings=config.settings,
        )
        await self._pool.startup()

        self._semaphore = asyncio.Semaphore(config.max_concurrent_queries)

        # Warm up connections if enabled
        if config.enable_connection_warmup:
            await self._warmup_connections()

        self._initialized = True
        logger.info(f"ClickHouse connection pool initialized: min={config.pool_min_size}, max={config.pool_max_size}")

        if self.config is None:
            self.config = config

        self._query_cache = (
            QueryCache(
                max_size=self.config.query_cache_max_size,
                ttl=self.config.query_cache_ttl,
            )
            if self.config.enable_query_cache
            else None
        )

    async def _warmup_connections(self):
        """Pre-establish connections to reduce cold start latency."""
        for _ in range(self.config.pool_min_size):
            try:
                async with self._pool.connection() as conn, conn.cursor() as cursor:
                    await cursor.execute("SELECT 1")
                    await cursor.fetchall()
            except Exception as e:
                logger.warning(f"Connection warmup failed: {e}")
                # Don't fail initialization if warmup fails

    async def _execute_warmup_query(self):
        """Execute a simple query for connection warmup without going through the full execute_query path."""
        try:
            async with self._pool.connection() as conn, conn.cursor() as cursor:
                await cursor.execute("SELECT 1")
                await cursor.fetchall()
        except Exception as e:
            logger.warning(f"Warmup query failed: {e}")

    async def _cleanup_cursor_state(self, cursor):
        """Clean up pending cursor state."""
        try:
            # Try to consume any remaining results
            while True:
                result = await cursor.fetchmany(1000)
                if not result:
                    break
        except Exception as e:
            # Ignore errors during cleanup
            logger.warning(f"Cleanup state failed: {e}")

    async def close(self):
        """Close the ClickHouse connection pool."""
        if self._pool:
            try:
                await self._pool.shutdown()
            except Exception as e:
                logger.warning(f"Error during connection pool shutdown: {e}")
            finally:
                self._initialized = False
                logger.info("ClickHouse connection pool closed")

    @profile_async("query_execution")
    async def execute_query(
        self,
        query: str,
        params: Optional[dict[str, Any]] = None,
        with_column_types: bool = False,
        use_cache: bool = True,
    ) -> Union[list[tuple], tuple[list[tuple], Any]]:
        """Execute a query against ClickHouse."""
        if not self._initialized:
            await self.initialize()

        if self.performance_metrics:
            self.performance_metrics.increment_counter("total_queries")

        # Check cache if enabled
        if use_cache and self._query_cache and not with_column_types:
            cached_result = await self._query_cache.get(query, params)
            if cached_result is not None:
                if self.performance_metrics:
                    self.performance_metrics.increment_counter("cache_hits")
                return cached_result
            else:
                if self.performance_metrics:
                    self.performance_metrics.increment_counter("cache_misses")

        async with self._semaphore, self._pool.connection() as conn, conn.cursor() as cursor:
            try:
                await cursor.execute(query, params or {})
                result = await cursor.fetchall()

                if with_column_types:
                    return result, cursor.description
                else:
                    # Cache the result if caching is enabled
                    if use_cache and self._query_cache:
                        await self._query_cache.set(query, result, params)
                    return result
            except Exception as e:
                # Log the error
                logger.error(f"Query execution failed: {e}. Query: {query[:100]}...")

                # CRITICAL FIX: Mark connection as bad so it won't be reused
                # The asynch library doesn't expose a direct way to invalidate a connection,
                # but closing it should prevent reuse
                try:
                    await conn.close()
                    logger.info("Closed connection after query failure to prevent reuse")
                except Exception as close_error:
                    logger.warning(f"Failed to close connection after error: {close_error}")

                raise

    async def execute_iter(
        self,
        query: str,
        params: Optional[dict[str, Any]] = None,
        batch_size: int = 10000,
    ):
        """Execute query and yield results in batches."""
        if not self._initialized:
            await self.initialize()

        async with self._semaphore, self._pool.connection() as conn, conn.cursor() as cursor:
            try:
                await cursor.execute(query, params or {})

                while True:
                    batch = await cursor.fetchmany(batch_size)
                    if not batch:
                        break
                    for row in batch:
                        yield row

            except Exception as e:
                logger.error(f"Iterator query execution failed: {e}. Query: {query[:100]}...")
                # Close connection to prevent reuse in dirty state
                try:
                    await conn.close()
                    logger.info("Closed connection after iterator query failure")
                except Exception as close_error:
                    logger.warning(f"Failed to close connection after error: {close_error}")
                raise

    async def execute_many(self, queries: list[str]) -> list[list[tuple]]:
        """Execute multiple queries concurrently with proper error handling."""
        try:
            tasks = [self.execute_query(query) for query in queries]
            return await asyncio.gather(*tasks)
        except Exception as e:
            logger.error(f"Concurrent query execution failed: {e}")
            # Log which queries were being executed for debugging
            logger.error(f"Failed queries: {[q[:100] + '...' if len(q) > 100 else q for q in queries]}")
            raise

    async def insert_data(self, table: str, data: list[tuple], columns: Optional[list[str]] = None):
        """Insert data into a table."""
        if not self._initialized:
            await self.initialize()

        async with self._semaphore, self._pool.connection() as conn, conn.cursor() as cursor:
            try:
                query = (
                    f"INSERT INTO {table} ({','.join(columns)}) VALUES" if columns else f"INSERT INTO {table} VALUES"
                )

                # Execute the insert with data
                await cursor.execute(query, data)

                # Consume any results to ensure cursor is clean
                try:
                    await cursor.fetchall()
                except Exception as e:
                    # Some insert queries may not return results, ignore errors
                    logger.warning(f"consume remaining in insert failed: {e}")
            except Exception as e:
                logger.error(f"Insert data failed: {e}. Table: {table}")
                raise

    @staticmethod
    def rows_to_dicts(rows: list[tuple], column_descriptions: Any) -> list[dict[str, Any]]:
        """Convert query result rows to dictionaries using column descriptions.

        Args:
            rows: List of tuples from execute_query result
            column_descriptions: Column descriptions from cursor.description

        Returns:
            List of dictionaries with column names as keys
        """
        if not rows or not column_descriptions:
            return []

        # Extract column names from descriptions
        # cursor.description format: [(name, type_code, display_size, internal_size, precision, scale, null_ok), ...]
        column_names = [desc[0] for desc in column_descriptions]

        # Convert each row to dictionary
        return [dict(zip(column_names, row, strict=True)) for row in rows]

    @staticmethod
    def row_to_dict(row: tuple, column_descriptions: Any) -> dict[str, Any]:
        """Convert single query result row to dictionary using column descriptions.

        Args:
            row: Single tuple from execute_query result
            column_descriptions: Column descriptions from cursor.description

        Returns:
            Dictionary with column names as keys
        """
        if not row or not column_descriptions:
            return {}

        # Extract column names from descriptions
        column_names = [desc[0] for desc in column_descriptions]

        return dict(zip(column_names, row, strict=True))

    async def get_pool_stats(self) -> dict[str, Any]:
        """Get connection pool statistics."""
        if not self._pool:
            return {"status": "not_initialized"}

        return {
            "status": self._pool.status,
            "free_connections": self._pool.free_connections,
            "acquired_connections": self._pool.acquired_connections,
            "max_size": self._pool.maxsize,
            "min_size": self._pool.minsize,
            "concurrent_limit": self.config.max_concurrent_queries,
        }
