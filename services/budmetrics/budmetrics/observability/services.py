import asyncio
import contextlib
import math
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Union
from uuid import UUID

from budmicroframe.commons import logging

from budmetrics.commons.config import app_settings, secrets_settings
from budmetrics.commons.profiling_utils import PerformanceMetrics, profile_sync
from budmetrics.observability.models import (
    ClickHouseClient,
    ClickHouseConfig,
    QueryBuilder,
)
from budmetrics.observability.schemas import (
    DEFAULT_SELECT_COLUMNS,
    MAX_TRACE_LIMIT,
    QUERYABLE_COLUMNS,
    CacheMetric,
    CountMetric,
    CredentialUsageItem,
    CredentialUsageRequest,
    CredentialUsageResponse,
    EnhancedInferenceDetailResponse,
    FeedbackItem,
    FilterCondition,
    FilterOperator,
    GatewayAnalyticsRequest,
    GatewayAnalyticsResponse,
    GatewayMetadata,
    InferenceFeedbackResponse,
    InferenceListItem,
    InferenceListRequest,
    InferenceListResponse,
    LatencyDistributionRequest,
    LatencyDistributionResponse,
    MetricsData,
    MetricsSyncRequest,
    MetricsSyncResponse,
    ObservabilityMetricsRequest,
    ObservabilityMetricsResponse,
    PerformanceMetric,
    PeriodBin,
    PromptDistributionBucket,
    PromptDistributionRequest,
    PromptDistributionResponse,
    TelemetryQueryRequest,
    TelemetryQueryResponse,
    TelemetrySpanItem,
    TimeMetric,
    TraceDetailResponse,
    TraceEvent,
    TraceItem,
    TraceLink,
    TraceListResponse,
    TraceResourceType,
    UserUsageItem,
    validate_attribute_key,
)


logger = logging.get_logger(__name__)

# The table is hardcoded to match existing patterns in services.py
_TELEMETRY_TRACE_TABLE = "metrics.otel_traces"


class TelemetryQueryBuilder:
    """Build parameterized ClickHouse queries for telemetry trace data.

    Produces two queries:
    - **count_query**: count of target spans matching all criteria (pagination)
    - **data_query**: all spans for the paginated trace set (tree building)
    """

    def build_query(self, request: TelemetryQueryRequest) -> tuple[str, str, dict[str, Any]]:
        """Build count and data queries from a validated request.

        Args:
            request: Validated TelemetryQueryRequest.

        Returns:
            Tuple of (data_query, count_query, params).
        """
        params: dict[str, Any] = {
            "prompt_id": request.prompt_id,
            "project_id": request.project_id,
            "from_date": request.from_date,
        }

        # Default to_date to now if not specified
        if request.to_date is not None:
            params["to_date"] = request.to_date
        else:
            from datetime import datetime, timezone

            params["to_date"] = datetime.now(timezone.utc)

        if request.version is not None:
            params["version"] = request.version

        if request.trace_id is not None:
            params["trace_id"] = request.trace_id

        params["limit"] = min(request.limit, MAX_TRACE_LIMIT)
        params["offset"] = request.offset

        # Build components
        select_clause = self._build_select_clause(request)
        trace_id_subquery = self._build_trace_id_subquery(request, params)
        target_conditions = self._build_target_span_conditions(request, params)

        # Count query: count distinct traces for pagination metadata
        count_query = f"""
            SELECT count(DISTINCT TraceId)
            FROM {_TELEMETRY_TRACE_TABLE}
            WHERE {target_conditions}
        """  # nosec B608

        # Data query: all spans for the paginated trace set
        data_query = f"""
            SELECT {select_clause}
            FROM {_TELEMETRY_TRACE_TABLE}
            WHERE TraceId IN ({trace_id_subquery})
            ORDER BY Timestamp ASC
        """  # nosec B608

        return data_query, count_query, params

    # ------------------------------------------------------------------
    # SELECT clause
    # ------------------------------------------------------------------

    def _build_select_clause(self, request: TelemetryQueryRequest) -> str:
        """Build the SELECT column list based on projection options."""
        columns = list(DEFAULT_SELECT_COLUMNS)

        if request.select_attributes:
            for key in request.select_attributes:
                validate_attribute_key(key)
                columns.append(f"SpanAttributes['{key}']")  # nosec B608

        if request.include_all_attributes:
            columns.append("SpanAttributes")
            columns.append("ResourceAttributes")
        elif request.include_resource_attributes:
            columns.append("ResourceAttributes")

        if request.include_events:
            columns.extend(["Events.Timestamp", "Events.Name", "Events.Attributes"])

        if request.include_links:
            columns.extend(["Links.TraceId", "Links.SpanId", "Links.TraceState", "Links.Attributes"])

        # Include prompt/project attrs for tree builder target filtering
        if request.span_names is None and not request.include_all_attributes:
            columns.append("SpanAttributes['gateway_analytics.prompt_id']")
            columns.append("SpanAttributes['gateway_analytics.project_id']")

        return ", ".join(columns)

    # ------------------------------------------------------------------
    # Trace ID subquery
    # ------------------------------------------------------------------

    def _build_trace_id_subquery(self, request: TelemetryQueryRequest, params: dict[str, Any]) -> str:
        """Build subquery that finds TraceIds via gateway_analytics spans.

        Always filters by project_id, prompt_id, and timestamp range for
        tenant isolation. Applies span_filters and resource_filters to the
        gateway_analytics anchor spans.
        """
        conditions = [
            "Timestamp >= %(from_date)s",
            "Timestamp <= %(to_date)s",
            "SpanName = 'gateway_analytics'",
            "SpanAttributes['gateway_analytics.prompt_id'] = %(prompt_id)s",
            "SpanAttributes['gateway_analytics.project_id'] = %(project_id)s",
        ]

        if request.version is not None:
            conditions.append("SpanAttributes['gateway_analytics.prompt_version'] = %(version)s")

        if request.trace_id is not None:
            conditions.append("TraceId = %(trace_id)s")

        # Apply span_filters to the subquery (filter the anchor spans)
        if request.span_filters and request.span_names is None:
            # When no span_names, filters apply to gateway_analytics spans
            filter_sql = self._build_span_attr_filters(request.span_filters, params)
            if filter_sql:
                conditions.append(filter_sql)

        # Apply resource_filters to the subquery only when targeting
        # gateway_analytics spans (no span_names).  When span_names is set,
        # the subquery still selects traces via gateway_analytics, but the
        # resource_filters should only constrain the *target* spans.
        if request.resource_filters and request.span_names is None:
            filter_sql = self._build_resource_attr_filters(request.resource_filters, params)
            if filter_sql:
                conditions.append(filter_sql)

        order_clause = self._build_order_clause(request)
        where = " AND ".join(conditions)

        return f"""
            SELECT DISTINCT TraceId
            FROM {_TELEMETRY_TRACE_TABLE}
            WHERE {where}
            {order_clause}
            LIMIT %(limit)s OFFSET %(offset)s
        """  # nosec B608

    # ------------------------------------------------------------------
    # Target span conditions (for count query)
    # ------------------------------------------------------------------

    def _build_target_span_conditions(self, request: TelemetryQueryRequest, params: dict[str, Any]) -> str:
        """Build WHERE conditions for the target spans.

        When ``span_names`` is null, targets are ``gateway_analytics`` spans.
        When specified, targets are spans matching the given names within
        the same trace scope.
        """
        conditions = [
            "Timestamp >= %(from_date)s",
            "Timestamp <= %(to_date)s",
        ]

        if request.span_names is None:
            # Default: target gateway_analytics spans
            conditions.extend(
                [
                    "SpanName = 'gateway_analytics'",
                    "SpanAttributes['gateway_analytics.prompt_id'] = %(prompt_id)s",
                    "SpanAttributes['gateway_analytics.project_id'] = %(project_id)s",
                ]
            )

            if request.version is not None:
                conditions.append("SpanAttributes['gateway_analytics.prompt_version'] = %(version)s")

            if request.trace_id is not None:
                conditions.append("TraceId = %(trace_id)s")

            # span_filters apply to gateway_analytics spans
            if request.span_filters:
                filter_sql = self._build_span_attr_filters(request.span_filters, params)
                if filter_sql:
                    conditions.append(filter_sql)
        else:
            # span_names specified: target those specific spans within matching traces
            trace_id_subquery = self._build_trace_id_subquery(request, params)
            conditions.append(f"TraceId IN ({trace_id_subquery})")  # nosec B608

            # Build SpanName IN clause
            span_name_placeholders = []
            for i, name in enumerate(request.span_names):
                param_key = f"span_name_{i}"
                params[param_key] = name
                span_name_placeholders.append(f"%({param_key})s")
            conditions.append(f"SpanName IN ({', '.join(span_name_placeholders)})")  # nosec B608

            # span_filters apply to the named spans
            if request.span_filters:
                filter_sql = self._build_span_attr_filters(request.span_filters, params)
                if filter_sql:
                    conditions.append(filter_sql)

        # resource_filters always apply to target spans
        if request.resource_filters:
            filter_sql = self._build_resource_attr_filters(request.resource_filters, params)
            if filter_sql:
                conditions.append(filter_sql)

        return " AND ".join(conditions)

    # ------------------------------------------------------------------
    # Attribute filter builders
    # ------------------------------------------------------------------

    def _build_span_attr_filters(
        self,
        filters: list[FilterCondition],
        params: dict[str, Any],
    ) -> str:
        """Build SQL conditions for SpanAttributes filters."""
        clauses = []
        for i, condition in enumerate(filters):
            clause = self._build_filter_condition(condition, params, i, "span")
            if clause:
                clauses.append(clause)
        return " AND ".join(clauses)

    def _build_resource_attr_filters(
        self,
        filters: list[FilterCondition],
        params: dict[str, Any],
    ) -> str:
        """Build SQL conditions for ResourceAttributes filters."""
        clauses = []
        for i, condition in enumerate(filters):
            clause = self._build_filter_condition(condition, params, i, "resource")
            if clause:
                clauses.append(clause)
        return " AND ".join(clauses)

    def _build_filter_condition(
        self,
        condition: FilterCondition,
        params: dict[str, Any],
        idx: int,
        attr_type: str,
    ) -> str:
        """Translate a single FilterCondition into a parameterized SQL fragment.

        Args:
            condition: The filter condition.
            params: Mutable params dict to add values to.
            idx: Unique index for parameter naming.
            attr_type: Either "span" or "resource".

        Returns:
            SQL fragment string.
        """
        validate_attribute_key(condition.field)

        if attr_type == "span":
            field_expr = f"SpanAttributes['{condition.field}']"  # nosec B608
        else:
            field_expr = f"ResourceAttributes['{condition.field}']"  # nosec B608

        op = condition.op
        param_prefix = f"{attr_type}_f{idx}"

        if op == FilterOperator.is_null:
            return f"{field_expr} = ''"
        if op == FilterOperator.is_not_null:
            return f"{field_expr} != ''"

        if op == FilterOperator.in_:
            if not isinstance(condition.value, list):
                raise ValueError(f"in_ operator requires a list value, got {type(condition.value)}")
            placeholders = []
            for j, val in enumerate(condition.value):
                pk = f"{param_prefix}_{j}"
                params[pk] = str(val)
                placeholders.append(f"%({pk})s")
            return f"{field_expr} IN ({', '.join(placeholders)})"

        if op == FilterOperator.not_in:
            if not isinstance(condition.value, list):
                raise ValueError(f"not_in operator requires a list value, got {type(condition.value)}")
            placeholders = []
            for j, val in enumerate(condition.value):
                pk = f"{param_prefix}_{j}"
                params[pk] = str(val)
                placeholders.append(f"%({pk})s")
            return f"{field_expr} NOT IN ({', '.join(placeholders)})"

        # Scalar operators
        params[param_prefix] = str(condition.value) if condition.value is not None else ""

        _NUMERIC_OPS = {FilterOperator.gt, FilterOperator.gte, FilterOperator.lt, FilterOperator.lte}

        op_map = {
            FilterOperator.eq: "=",
            FilterOperator.neq: "!=",
            FilterOperator.gt: ">",
            FilterOperator.gte: ">=",
            FilterOperator.lt: "<",
            FilterOperator.lte: "<=",
            FilterOperator.like: "LIKE",
        }

        sql_op = op_map.get(op)
        if sql_op is None:
            raise ValueError(f"Unsupported filter operator: {op}")

        # SpanAttributes/ResourceAttributes are Map(String, String), so
        # comparisons like "2782" > "10000" are lexicographic (wrong).
        # Cast both sides to Float64 for numeric operators.
        if op in _NUMERIC_OPS:
            return f"toFloat64OrZero({field_expr}) {sql_op} toFloat64OrZero(%({param_prefix})s)"

        return f"{field_expr} {sql_op} %({param_prefix})s"

    # ------------------------------------------------------------------
    # ORDER BY
    # ------------------------------------------------------------------

    def _build_order_clause(self, request: TelemetryQueryRequest) -> str:
        """Build ORDER BY clause from request order_by specs."""
        if not request.order_by:
            return "ORDER BY Timestamp DESC"

        parts = []
        for spec in request.order_by:
            ch_col = QUERYABLE_COLUMNS.get(spec.field)
            if ch_col is None:
                raise ValueError(f"Invalid order_by field: {spec.field}")
            parts.append(f"{ch_col} {spec.direction.upper()}")

        return f"ORDER BY {', '.join(parts)}"


class ObservabilityMetricsService:
    """Main service class for observability metrics operations.

    This service orchestrates the flow of analytics queries and metrics ingestion:
    - Coordinates with QueryBuilder to construct SQL queries
    - Manages ClickHouse client connections and query execution
    - Processes and formats query results
    - Handles metrics ingestion with deduplication

    The service implements performance optimizations including:
    - Efficient result processing with minimal memory allocation
    - Gap-filled row detection for time series data
    - Batch processing for metrics ingestion
    """

    def __init__(self, config: Optional[ClickHouseConfig] = None):
        """Initialize the observability service with optional configuration."""
        # Lazy initialization
        self._clickhouse_client: Optional[ClickHouseClient] = None
        self._performance_metrics: Optional[PerformanceMetrics] = None
        self._query_builder: Optional[QueryBuilder] = None
        self._metric_processors = None

        self.clickhouse_client_config = config or ClickHouseConfig()

    def _ensure_initialized(self):
        """Ensure all components are initialized."""
        if self._clickhouse_client is None or not self._clickhouse_client._initialized:
            self.clickhouse_client_config.host = app_settings.clickhouse_host
            self.clickhouse_client_config.port = app_settings.clickhouse_port
            self.clickhouse_client_config.database = app_settings.clickhouse_dbname
            self.clickhouse_client_config.user = secrets_settings.clickhouse_user
            self.clickhouse_client_config.password = secrets_settings.clickhouse_password
            # Set configuration from app settings
            self.clickhouse_client_config.enable_query_cache = app_settings.clickhouse_enable_query_cache
            self.clickhouse_client_config.enable_connection_warmup = app_settings.clickhouse_enable_connection_warmup
            self._clickhouse_client = ClickHouseClient(self.clickhouse_client_config)
            # Performance metrics are only available in debug mode
            self._performance_metrics = self._clickhouse_client.performance_metrics
            self._query_builder = QueryBuilder(self._performance_metrics)

    @property
    def clickhouse_client(self):
        """Get the ClickHouse client instance."""
        self._ensure_initialized()
        return self._clickhouse_client

    @property
    def query_builder(self):
        """Get the query builder instance."""
        self._ensure_initialized()
        return self._query_builder

    @property
    def performance_metrics(self):
        """Get the performance metrics instance."""
        self._ensure_initialized()
        return self._performance_metrics

    async def initialize(self):
        """Initialize the ClickHouse client connection pool."""
        await self.clickhouse_client.initialize()

    async def close(self):
        """Close the ClickHouse client connection pool."""
        if self._clickhouse_client is not None:
            await self._clickhouse_client.close()

    def _create_metric_processors(self):
        """Create a mapping of metric types to their processor functions."""
        # Define metric configurations
        count_metric_configs = {
            "request_count": {
                "count_field": "request_count",
                "rate_field": None,
                "output_key": "request_count",
            },
            "success_request": {
                "count_field": "success_request_count",
                "rate_field": "success_rate",
                "output_key": "success_request",  # Note: keeping typo for backward compatibility
            },
            "failure_request": {
                "count_field": "failure_request_count",
                "rate_field": "failure_rate",
                "output_key": "failure_request",
            },
            "input_token": {
                "count_field": "input_token_count",
                "rate_field": None,
                "output_key": "input_token",
            },
            "output_token": {
                "count_field": "output_token_count",
                "rate_field": None,
                "output_key": "output_token",
            },
        }

        time_metric_configs = {
            "queuing_time": {
                "time_field": "avg_queuing_time_ms",
                "output_key": "queuing_time",
            }
        }

        performance_metric_configs = {
            "ttft": {
                "avg_field": "avg_ttft_ms",
                "p99_field": "ttft_p99",
                "p95_field": "ttft_p95",
                "output_key": "ttft",
            },
            "latency": {
                "avg_field": "avg_latency_ms",
                "p99_field": "latency_p99",
                "p95_field": "latency_p95",
                "output_key": "latency",
            },
            "throughput": {
                "avg_field": "avg_throughput_tokens_per_sec",
                "output_key": "throughput",
            },
            "concurrent_requests": {
                "avg_field": "max_concurrent_requests",
                "output_key": "concurrent_requests",
            },
        }

        cache_metric_configs = {
            "cache": {
                "hit_rate_field": "cache_hit_rate",
                "hit_count_field": "cache_hit_count",
                "latency_field": "avg_cache_latency_ms",
                "output_key": "cache",
            }
        }

        # Create processor map
        processors = {}

        # Add count metric processors
        for metric_name, config in count_metric_configs.items():
            processors[metric_name] = lambda row, indices, delta_map, percent_map, cfg=config: (
                self._process_count_metric(row, indices, delta_map, percent_map, cfg)
            )

        # Add time metric processors
        for metric_name, config in time_metric_configs.items():
            processors[metric_name] = lambda row, indices, delta_map, percent_map, cfg=config: (
                self._process_time_metric(row, indices, delta_map, percent_map, cfg)
            )

        # Add performance metric processors
        for metric_name, config in performance_metric_configs.items():
            processors[metric_name] = lambda row, indices, delta_map, percent_map, cfg=config: (
                self._process_performance_metric(row, indices, delta_map, percent_map, cfg)
            )

        # Add cache metric processors
        for metric_name, config in cache_metric_configs.items():
            processors[metric_name] = lambda row, indices, delta_map, percent_map, cfg=config: (
                self._process_cache_metric(row, indices, delta_map, percent_map, cfg)
            )

        return processors

    def _sanitize_delta_percent(self, delta_percent: float):
        if math.isnan(delta_percent):
            return 0.0
        elif math.isinf(delta_percent):
            return 100.0 if delta_percent > 0 else -100.0

        return delta_percent

    def _process_count_metric(self, row, field_indices, delta_map, percent_map, config):
        """Process count-based metrics with optional rate field."""
        count_idx = field_indices.get(config["count_field"], -1)
        count = row[count_idx] if count_idx >= 0 else 0

        metric_obj = CountMetric(count=count or 0)

        # Add rate if available
        if config["rate_field"]:
            rate_idx = field_indices.get(config["rate_field"], -1)
            if rate_idx >= 0:
                metric_obj.rate = row[rate_idx]

        # Add delta fields
        count_field = config["count_field"]
        if count_field in delta_map:
            delta_idx = field_indices[delta_map[count_field]]
            if row[delta_idx] is not None:
                metric_obj.delta = row[delta_idx]

        if count_field in percent_map:
            percent_idx = field_indices[percent_map[count_field]]
            if row[percent_idx] is not None:
                metric_obj.delta_percent = self._sanitize_delta_percent(row[percent_idx])

        return config["output_key"], metric_obj

    def _process_time_metric(self, row, field_indices, delta_map, percent_map, config):
        """Process time-based metrics."""
        time_idx = field_indices.get(config["time_field"], -1)
        time_value = row[time_idx] if time_idx >= 0 else 0.0

        metric_obj = TimeMetric(avg_time_ms=time_value or 0.0)

        # Add delta fields
        time_field = config["time_field"]
        if time_field in delta_map:
            delta_idx = field_indices[delta_map[time_field]]
            if row[delta_idx] is not None:
                metric_obj.delta = row[delta_idx]

        if time_field in percent_map:
            percent_idx = field_indices[percent_map[time_field]]
            if row[percent_idx] is not None:
                metric_obj.delta_percent = self._sanitize_delta_percent(row[percent_idx])

        return config["output_key"], metric_obj

    def _process_performance_metric(self, row, field_indices, delta_map, percent_map, config):
        """Process performance-based metrics with optional percentiles."""
        avg_idx = field_indices.get(config["avg_field"], -1)
        avg_value = row[avg_idx] if avg_idx >= 0 else 0.0

        metric_obj = PerformanceMetric(avg=avg_value or 0.0)

        # Add percentiles if available
        if "p99_field" in config:
            p99_idx = field_indices.get(config["p99_field"], -1)
            if p99_idx >= 0 and row[p99_idx] is not None:
                metric_obj.p99 = row[p99_idx]

        if "p95_field" in config:
            p95_idx = field_indices.get(config["p95_field"], -1)
            if p95_idx >= 0 and row[p95_idx] is not None:
                metric_obj.p95 = row[p95_idx]

        # Add delta fields
        avg_field = config["avg_field"]
        if avg_field in delta_map:
            delta_idx = field_indices[delta_map[avg_field]]
            if row[delta_idx] is not None:
                metric_obj.delta = row[delta_idx]

        if avg_field in percent_map:
            percent_idx = field_indices[percent_map[avg_field]]
            if row[percent_idx] is not None:
                metric_obj.delta_percent = self._sanitize_delta_percent(row[percent_idx])

        return config["output_key"], metric_obj

    def _process_cache_metric(self, row, field_indices, delta_map, percent_map, config):
        """Process cache-based metrics."""
        hit_rate_idx = field_indices.get(config["hit_rate_field"], -1)
        hit_count_idx = field_indices.get(config["hit_count_field"], -1)

        hit_rate = row[hit_rate_idx] if hit_rate_idx >= 0 else 0.0
        hit_count = row[hit_count_idx] if hit_count_idx >= 0 else 0

        metric_obj = CacheMetric(hit_rate=hit_rate or 0.0, hit_count=hit_count or 0)

        # Add latency if available
        if "latency_field" in config:
            latency_idx = field_indices.get(config["latency_field"], -1)
            if latency_idx >= 0 and row[latency_idx] is not None:
                metric_obj.avg_latency_ms = row[latency_idx]

        # Add delta fields for hit rate
        hit_rate_field = config["hit_rate_field"]
        if hit_rate_field in delta_map:
            delta_idx = field_indices[delta_map[hit_rate_field]]
            if row[delta_idx] is not None:
                metric_obj.delta = row[delta_idx]

        if hit_rate_field in percent_map:
            percent_idx = field_indices[percent_map[hit_rate_field]]
            if row[percent_idx] is not None:
                metric_obj.delta_percent = self._sanitize_delta_percent(row[percent_idx])

        return config["output_key"], metric_obj

    # Pre-compile zero UUID for faster comparison
    _ZERO_UUID = UUID("00000000-0000-0000-0000-000000000000")

    # Mapping from API group_by field names to database column names
    _GROUP_BY_TO_COLUMN = {
        "model": "model_id",
        "project": "project_id",
        "endpoint": "endpoint_id",
        "user_project": "api_key_project_id",
        "api_key": "api_key_id",
    }

    def _extract_single_resource_ids_from_filters(
        self, filters: Optional[Dict[str, Any]]
    ) -> Dict[str, Optional[UUID]]:
        """Extract resource IDs when filters contain exactly one resource.

        When a filter contains exactly one resource ID, return it so the
        response can identify which resource the metrics belong to.

        Args:
            filters: Filter dictionary (e.g., {"project": ["uuid"]})

        Returns:
            Dict with keys: project_id, model_id, endpoint_id
            Values are UUID if single resource, None otherwise

        Examples:
            {"project": ["abc-123"]} -> {"project_id": UUID("abc-123"), ...}
            {"project": ["id1", "id2"]} -> {"project_id": None, ...}  # Multiple = aggregated
        """
        result = {
            "project_id": None,
            "model_id": None,
            "endpoint_id": None,
        }

        if not filters:
            return result

        # Map filter keys to result keys
        filter_mappings = {
            "project": "project_id",
            "project_id": "project_id",
            "model": "model_id",
            "model_id": "model_id",
            "endpoint": "endpoint_id",
            "endpoint_id": "endpoint_id",
        }

        for filter_key, result_key in filter_mappings.items():
            if filter_key not in filters:
                continue

            filter_value = filters[filter_key]

            # Handle list with single element
            if isinstance(filter_value, list):
                if len(filter_value) == 1:
                    with contextlib.suppress(ValueError, TypeError):
                        result[result_key] = UUID(str(filter_value[0]))
            # Handle single value (not in list)
            elif isinstance(filter_value, (str, UUID)):
                with contextlib.suppress(ValueError, TypeError):
                    result[result_key] = UUID(str(filter_value))

        return result

    @profile_sync("result_processing")
    def _process_query_results(
        self,
        results: list[tuple],
        field_order: list[str],
        metrics: list[str],
        group_by: Optional[list[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> list[PeriodBin]:
        """Process raw query results into structured response format."""
        if not results:
            return []

        # Create a mapping of field names to indices
        field_index = {field: idx for idx, field in enumerate(field_order)}

        # Pre-compute delta field mappings for all metrics
        delta_field_map = {}
        percent_field_map = {}
        for field in field_index:
            if field.endswith("_delta"):
                base = field[:-6]  # Remove "_delta"
                delta_field_map[base] = field
            elif field.endswith("_percent_change"):
                base = field[:-15]  # Remove "_percent_change"
                percent_field_map[base] = field

        # Extract single resource IDs from filters (only when no group_by)
        single_resource_ids = None
        if not group_by:
            single_resource_ids = self._extract_single_resource_ids_from_filters(filters)

        # Pre-compute group field indices
        # Map API field names (model, project, etc.) to column names (model_id, project_id, etc.)
        group_field_indices = {}
        if group_by:
            for group_field in group_by:
                col_name = self._GROUP_BY_TO_COLUMN.get(group_field, group_field)
                if col_name in field_index:
                    group_field_indices[group_field] = field_index[col_name]

        # Get metric processors (create once and cache)
        if self._metric_processors is None:
            self._metric_processors = self._create_metric_processors()
        metric_processors = self._metric_processors

        time_bucket_idx = field_index["time_bucket"]

        # Use defaultdict for all cases to avoid key existence checks
        period_bins = defaultdict(list)

        # Pre-check if we need to check for gap-filled rows
        check_gap_filled = bool(group_field_indices)

        # Process all rows efficiently
        for row in results:
            time_period = row[time_bucket_idx]

            # Fast path for gap-filled row detection
            if check_gap_filled:
                # Check if any group field has a zero UUID or NULL
                is_gap_filled = False
                for _group_field, idx in group_field_indices.items():
                    if row[idx] == self._ZERO_UUID or row[idx] is None:
                        is_gap_filled = True
                        break

                if is_gap_filled:
                    # Ensure time period exists in period_bins even if empty
                    period_bins[time_period]  # This creates an empty list if not exists
                    continue

            # Extract grouping dimensions
            dimensions = {}
            for group_field, idx in group_field_indices.items():
                value = row[idx]
                if value is not None:
                    dimensions[f"{group_field}_id"] = value

            # Populate dimensions from single-resource filters if no group_by
            if single_resource_ids and not group_by:
                if single_resource_ids["project_id"]:
                    dimensions["project_id"] = single_resource_ids["project_id"]
                if single_resource_ids["model_id"]:
                    dimensions["model_id"] = single_resource_ids["model_id"]
                if single_resource_ids["endpoint_id"]:
                    dimensions["endpoint_id"] = single_resource_ids["endpoint_id"]

            # Extract metrics data using processors
            metrics_data = {}
            for metric in metrics:
                if metric in metric_processors:
                    output_key, metric_obj = metric_processors[metric](
                        row, field_index, delta_field_map, percent_field_map
                    )
                    metrics_data[output_key] = metric_obj

            # Create MetricsData object
            metrics_item = MetricsData(
                model_id=dimensions.get("model_id"),
                project_id=dimensions.get("project_id"),
                endpoint_id=dimensions.get("endpoint_id"),
                api_key_id=dimensions.get("api_key_id"),
                data=metrics_data,
            )

            period_bins[time_period].append(metrics_item)

        # Convert to list of PeriodBin objects, sorted by time descending
        # Use list comprehension for better performance
        result_bins = [
            PeriodBin(time_period=time_period, items=period_bins[time_period] or [])
            for time_period in sorted(period_bins.keys(), reverse=True)
        ]

        return result_bins

    async def get_metrics(self, request: ObservabilityMetricsRequest) -> ObservabilityMetricsResponse:
        """Get metrics based on the request.

        Uses rollup tables (InferenceMetrics5m/1h/1d) for compatible metrics,
        falls back to raw data queries for percentiles and complex metrics.

        Args:
            request: ObservabilityMetricsRequest with query parameters

        Returns:
            ObservabilityMetricsResponse with processed metrics data
        """
        await self.initialize()

        # Check if rollup tables can handle this request (better performance)
        use_rollup = self.query_builder.can_use_rollup(request.metrics)

        # Get data_source from request, defaulting to "inference"
        data_source = getattr(request, "data_source", "inference")

        if use_rollup:
            # Use rollup tables for pre-aggregated data (faster for large time ranges)
            logger.debug(f"Using rollup tables for metrics: {request.metrics}")
            query, field_order = self.query_builder.build_rollup_query(
                metrics=request.metrics,
                from_date=request.from_date,
                to_date=request.to_date,
                frequency_unit=request.frequency_unit,
                frequency_interval=request.frequency_interval,
                filters=request.filters,
                group_by=request.group_by,
                return_delta=request.return_delta,
                fill_time_gaps=request.fill_time_gaps,
                topk=request.topk,
                data_source=data_source,
            )
        else:
            # Fall back to raw data queries (needed for percentiles, queuing_time, etc.)
            logger.debug(f"Using raw data for metrics: {request.metrics}")
            query, field_order = self.query_builder.build_query(
                metrics=request.metrics,
                from_date=request.from_date,
                to_date=request.to_date,
                frequency_unit=request.frequency_unit,
                frequency_interval=request.frequency_interval,
                filters=request.filters,
                group_by=request.group_by,
                return_delta=request.return_delta,
                fill_time_gaps=request.fill_time_gaps,
                topk=request.topk,
                data_source=data_source,
            )

        # Execute query
        try:
            results = await self.clickhouse_client.execute_query(query)
        except Exception as e:
            logger.error(f"Failed to execute metrics query: {str(e)}")
            raise RuntimeError("Failed to execute metrics query") from e

        # Process results
        period_bins = self._process_query_results(
            results, field_order, request.metrics, request.group_by, request.filters
        )

        # Return response
        return ObservabilityMetricsResponse(object="observability_metrics", items=period_bins)

    async def get_metrics_batch(
        self, requests: list[ObservabilityMetricsRequest]
    ) -> list[ObservabilityMetricsResponse]:
        """Execute multiple metrics requests concurrently for better performance.

        Args:
            requests: List of ObservabilityMetricsRequest objects

        Returns:
            List of ObservabilityMetricsResponse objects in the same order
        """
        tasks = [self.get_metrics(request) for request in requests]
        return await asyncio.gather(*tasks)

    def _escape_string(self, value):
        """Escape string for SQL."""
        if value is None:
            return "NULL"
        if isinstance(value, str):
            escaped = value.replace("'", "''")
            return f"'{escaped}'"
        return str(value)

    async def insert_inference_details(self, batch_data: list[tuple]) -> dict:
        """Insert batch data into ModelInferenceDetails table.

        Args:
            batch_data: List of tuples containing (inference_id, request_ip, project_id,
                       endpoint_id, model_id, cost, response_analysis, is_success,
                       request_arrival_time, request_forward_time, api_key_id, user_id, api_key_project_id,
                       error_code, error_message, error_type, status_code)

        Returns:
            dict: Insertion results with counts and duplicate inference_ids
        """
        await self.initialize()

        if not batch_data:
            return {
                "total_records": 0,
                "inserted": 0,
                "duplicates": 0,
                "duplicate_ids": [],
            }

        # Extract all inference_ids to check for existing records
        inference_ids = [str(record[0]) for record in batch_data]

        # Check for existing inference_ids
        if not inference_ids:
            return {
                "total_records": 0,
                "inserted": 0,
                "duplicates": 0,
                "duplicate_ids": [],
            }

        # Use parameterized query with placeholders
        placeholders = ",".join([f"%(id_{i})s" for i in range(len(inference_ids))])
        # Safe: placeholders are generated programmatically, not from user input
        existing_check_query = f"""
        SELECT inference_id
        FROM ModelInferenceDetails
        WHERE inference_id IN ({placeholders})
        """  # nosec B608

        # Create params dict
        params = {f"id_{i}": inference_id for i, inference_id in enumerate(inference_ids)}

        existing_records = await self.clickhouse_client.execute_query(existing_check_query, params)
        existing_ids = {str(row[0]) for row in existing_records} if existing_records else set()

        # Filter out records with existing inference_ids
        new_records = [record for record in batch_data if str(record[0]) not in existing_ids]
        duplicate_ids = list(existing_ids)

        if not new_records:
            logger.info(f"All {len(batch_data)} records already exist, skipping insert")
            return {
                "total_records": len(batch_data),
                "inserted": 0,
                "duplicates": len(batch_data),
                "duplicate_ids": duplicate_ids,
            }

        if len(new_records) < len(batch_data):
            logger.info(f"Filtered out {len(batch_data) - len(new_records)} duplicate records")

        # Build VALUES clause using raw SQL similar to simple_seeder
        values = []
        for record in new_records:
            # Handle different formats based on record length
            if len(record) == 10:
                # Legacy format without auth metadata and error fields
                (
                    inference_id,
                    request_ip,
                    project_id,
                    endpoint_id,
                    model_id,
                    cost,
                    response_analysis,
                    is_success,
                    request_arrival_time,
                    request_forward_time,
                ) = record
                api_key_id = None
                user_id = None
                api_key_project_id = None
                error_code = None
                error_message = None
                error_type = None
                status_code = None
            elif len(record) == 13:
                # Format with auth metadata but no error fields
                (
                    inference_id,
                    request_ip,
                    project_id,
                    endpoint_id,
                    model_id,
                    cost,
                    response_analysis,
                    is_success,
                    request_arrival_time,
                    request_forward_time,
                    api_key_id,
                    user_id,
                    api_key_project_id,
                ) = record
                error_code = None
                error_message = None
                error_type = None
                status_code = None
            else:
                # New format with auth metadata and error fields (17 fields)
                (
                    inference_id,
                    request_ip,
                    project_id,
                    endpoint_id,
                    model_id,
                    cost,
                    response_analysis,
                    is_success,
                    request_arrival_time,
                    request_forward_time,
                    api_key_id,
                    user_id,
                    api_key_project_id,
                    error_code,
                    error_message,
                    error_type,
                    status_code,
                ) = record

            # Format each row
            row = (
                f"({self._escape_string(str(inference_id))}, "
                f"{self._escape_string(request_ip) if request_ip else 'NULL'}, "
                f"{self._escape_string(str(project_id))}, "
                f"{self._escape_string(str(endpoint_id))}, "
                f"{self._escape_string(str(model_id))}, "
                f"{cost if cost is not None else 'NULL'}, "
                f"{self._escape_string(response_analysis) if response_analysis else 'NULL'}, "
                f"{1 if is_success else 0}, "
                f"'{request_arrival_time.strftime('%Y-%m-%d %H:%M:%S')}', "
                f"'{request_forward_time.strftime('%Y-%m-%d %H:%M:%S')}', "
                f"{self._escape_string(str(api_key_id)) if api_key_id else 'NULL'}, "
                f"{self._escape_string(str(user_id)) if user_id else 'NULL'}, "
                f"{self._escape_string(str(api_key_project_id)) if api_key_project_id else 'NULL'}, "
                f"{self._escape_string(error_code) if error_code else 'NULL'}, "
                f"{self._escape_string(error_message) if error_message else 'NULL'}, "
                f"{self._escape_string(error_type) if error_type else 'NULL'}, "
                f"{status_code if status_code is not None else 'NULL'})"
            )
            values.append(row)

        # Build and execute the INSERT query
        # Safe: values are escaped using _escape_string method
        query = f"""
        INSERT INTO ModelInferenceDetails
        (inference_id, request_ip, project_id, endpoint_id, model_id,
         cost, response_analysis, is_success, request_arrival_time, request_forward_time,
         api_key_id, user_id, api_key_project_id, error_code, error_message, error_type, status_code)
        VALUES {",".join(values)}
        """  # nosec B608

        await self.clickhouse_client.execute_query(query)
        logger.info(f"Successfully inserted {len(new_records)} new records")

        return {
            "total_records": len(batch_data),
            "inserted": len(new_records),
            "duplicates": len(duplicate_ids),
            "duplicate_ids": duplicate_ids,
        }

    async def list_inferences(self, request: InferenceListRequest) -> InferenceListResponse:
        """List inference requests with pagination and filtering.

        Uses InferenceFact (denormalized table) for optimal query performance.

        Args:
            request: InferenceListRequest with query parameters

        Returns:
            InferenceListResponse with paginated inference data
        """
        await self.initialize()

        # Build WHERE clause for filters
        where_conditions = []
        params = {}

        # Exclude blocked requests (they have inference_id = NULL, only trace_id)
        # These shouldn't appear in the inference list as they don't have actual inference data
        where_conditions.append("ifact.inference_id IS NOT NULL")

        # Always filter by date range
        # Note: Using 'ifact' alias instead of 'inf' to avoid conflict with ClickHouse's infinity constant
        where_conditions.append("ifact.timestamp >= %(from_date)s")
        params["from_date"] = request.from_date

        if request.to_date:
            where_conditions.append("ifact.timestamp <= %(to_date)s")
            params["to_date"] = request.to_date

        if request.project_id:
            where_conditions.append("ifact.project_id = %(project_id)s")
            params["project_id"] = str(request.project_id)

        # Support filtering by api_key_project_id (for CLIENT users)
        if hasattr(request, "filters") and request.filters and "api_key_project_id" in request.filters:
            api_key_project_ids = request.filters["api_key_project_id"]
            if isinstance(api_key_project_ids, list):
                placeholders = [f"%(api_key_project_{i})s" for i in range(len(api_key_project_ids))]
                where_conditions.append(f"ifact.api_key_project_id IN ({','.join(placeholders)})")
                for i, val in enumerate(api_key_project_ids):
                    params[f"api_key_project_{i}"] = str(val)
            else:
                where_conditions.append("ifact.api_key_project_id = %(api_key_project_id)s")
                params["api_key_project_id"] = str(api_key_project_ids)

        if request.endpoint_id:
            where_conditions.append("ifact.endpoint_id = %(endpoint_id)s")
            params["endpoint_id"] = str(request.endpoint_id)

        if request.model_id:
            where_conditions.append("ifact.model_id = %(model_id)s")
            params["model_id"] = str(request.model_id)

        if request.is_success is not None:
            where_conditions.append("ifact.is_success = %(is_success)s")
            params["is_success"] = 1 if request.is_success else 0

        if request.min_tokens is not None:
            where_conditions.append("(ifact.input_tokens + ifact.output_tokens) >= %(min_tokens)s")
            params["min_tokens"] = request.min_tokens

        if request.max_tokens is not None:
            where_conditions.append("(ifact.input_tokens + ifact.output_tokens) <= %(max_tokens)s")
            params["max_tokens"] = request.max_tokens

        if request.max_latency_ms is not None:
            where_conditions.append("ifact.response_time_ms <= %(max_latency_ms)s")
            params["max_latency_ms"] = request.max_latency_ms

        if request.endpoint_type:
            where_conditions.append("ifact.endpoint_type = %(endpoint_type)s")
            params["endpoint_type"] = request.endpoint_type

        where_clause = " AND ".join(where_conditions)

        # Build ORDER BY clause - validate sort_by to prevent injection
        sort_column_map = {
            "timestamp": "ifact.timestamp",
            "tokens": "(ifact.input_tokens + ifact.output_tokens)",
            "latency": "ifact.response_time_ms",
            "cost": "ifact.cost",
        }

        # Validate sort_by is in allowed columns
        if request.sort_by not in sort_column_map:
            raise ValueError("Invalid sort_by parameter")

        # Validate sort_order
        if request.sort_order.upper() not in ("ASC", "DESC"):
            raise ValueError("Invalid sort_order parameter")

        order_by = f"{sort_column_map[request.sort_by]} {request.sort_order.upper()}"

        # Count total records from InferenceFact (denormalized, no JOIN needed)
        count_query = f"""
        SELECT count() as total_count
        FROM InferenceFact ifact
        WHERE {where_clause}
        """  # nosec B608

        # Execute count query with parameters
        count_result = await self.clickhouse_client.execute_query(count_query, params)
        total_count = count_result[0][0] if count_result else 0

        # Get paginated data from InferenceFact (denormalized table)
        # Safe: where_clause and order_by are validated, limit/offset use parameters
        # Note: LEFT JOINs kept for modality-specific tables (embedding, audio, image, moderation)
        list_query = f"""
        SELECT
            ifact.inference_id,
            ifact.timestamp,
            ifact.model_name,
            CASE
                WHEN ifact.endpoint_type = 'chat' THEN toValidUTF8(substring(ifact.input_messages, 1, 100))
                WHEN ifact.endpoint_type = 'embedding' THEN toValidUTF8(substring(ei.input, 1, 100))
                WHEN ifact.endpoint_type IN ('audio_transcription', 'audio_translation', 'text_to_speech') THEN toValidUTF8(substring(ai.input, 1, 100))
                WHEN ifact.endpoint_type = 'image_generation' THEN toValidUTF8(substring(ii.prompt, 1, 100))
                WHEN ifact.endpoint_type = 'moderation' THEN toValidUTF8(substring(modi.input, 1, 100))
                ELSE toValidUTF8(substring(ifact.input_messages, 1, 100))
            END as prompt_preview,
            CASE
                WHEN ifact.endpoint_type = 'chat' THEN toValidUTF8(substring(ifact.output, 1, 100))
                WHEN ifact.endpoint_type = 'embedding' THEN concat('Generated ', toString(ei.input_count), ' embeddings')
                WHEN ifact.endpoint_type IN ('audio_transcription', 'audio_translation', 'text_to_speech') THEN toValidUTF8(substring(ai.output, 1, 100))
                WHEN ifact.endpoint_type = 'image_generation' THEN concat('Generated ', toString(ii.image_count), ' images')
                WHEN ifact.endpoint_type = 'moderation' THEN if(modi.flagged, 'Content flagged', 'Content passed')
                ELSE toValidUTF8(substring(ifact.output, 1, 100))
            END as response_preview,
            ifact.input_tokens,
            ifact.output_tokens,
            ifact.input_tokens + ifact.output_tokens as total_tokens,
            ifact.response_time_ms,
            ifact.cost,
            ifact.is_success,
            ifact.cached,
            ifact.project_id,
            ifact.api_key_project_id,
            ifact.endpoint_id,
            ifact.model_id,
            coalesce(ifact.endpoint_type, 'chat') as endpoint_type,
            ifact.error_code,
            ifact.error_message,
            ifact.error_type,
            ifact.status_code
        FROM InferenceFact ifact
        LEFT JOIN EmbeddingInference ei ON ifact.inference_id = ei.id AND ifact.endpoint_type = 'embedding'
        LEFT JOIN AudioInference ai ON ifact.inference_id = ai.id AND ifact.endpoint_type IN ('audio_transcription', 'audio_translation', 'text_to_speech')
        LEFT JOIN ImageInference ii ON ifact.inference_id = ii.id AND ifact.endpoint_type = 'image_generation'
        LEFT JOIN ModerationInference modi ON ifact.inference_id = modi.id AND ifact.endpoint_type = 'moderation'
        WHERE {where_clause}
        ORDER BY {order_by}
        LIMIT %(limit)s OFFSET %(offset)s
        """  # nosec B608

        params["limit"] = request.limit
        params["offset"] = request.offset

        # Execute list query with parameters
        results = await self.clickhouse_client.execute_query(list_query, params)

        # Convert results to InferenceListItem objects
        items = []
        for row in results:
            is_success = bool(row[10])
            items.append(
                InferenceListItem(
                    inference_id=row[0],
                    timestamp=row[1],
                    model_name=row[2],
                    prompt_preview=row[3] or "",
                    response_preview=row[4] or "",
                    input_tokens=row[5] or 0,
                    output_tokens=row[6] or 0,
                    total_tokens=row[7] or 0,
                    response_time_ms=row[8] or 0,
                    cost=row[9],
                    is_success=is_success,
                    cached=bool(row[11]),
                    project_id=row[12],
                    api_key_project_id=row[13],  # Added api_key_project_id
                    endpoint_id=row[14],
                    model_id=row[15],
                    endpoint_type=row[16],
                    error_code=row[17],
                    error_message=row[18],
                    error_type=row[19],
                    status_code=row[20],
                )
            )

        has_more = (request.offset + request.limit) < total_count

        return InferenceListResponse(
            object="inference_list",
            items=items,
            total_count=total_count,
            offset=request.offset,
            limit=request.limit,
            has_more=has_more,
        )

    async def list_traces(
        self,
        resource_type: TraceResourceType,
        resource_id: str,
        project_id: UUID,
        from_date: datetime,
        to_date: datetime,
        offset: int = 0,
        limit: int = 50,
        flatten: bool = False,
    ) -> TraceListResponse:
        """List OTel traces filtered by resource type/id and project_id.

        Queries the otel_traces table for spans that match the specified resource and project.

        Args:
            resource_type: Type of resource to filter by (TraceResourceType enum)
            resource_id: ID of the resource to filter by
            project_id: Project ID to filter by
            from_date: Start date for filtering
            to_date: End date for filtering
            offset: Pagination offset
            limit: Number of results to return
            flatten: If True, return all spans (root + children) sorted by time

        Returns:
            TraceListResponse with paginated trace data
        """
        await self.initialize()

        # Build the attribute key dynamically (e.g., 'gateway_analytics.prompt_id')
        # resource_type.value is safe because it comes from the TraceResourceType enum
        resource_attr_key = f"gateway_analytics.{resource_type.value}_id"

        # Build params dict
        params = {
            "resource_id": resource_id,
            "project_id": str(project_id),
            "from_date": from_date,
            "to_date": to_date,
            "offset": offset,
            "limit": limit,
        }

        # Subquery to find matching TraceIds (used by both modes for flatten, count for non-flatten)
        trace_id_subquery = f"""
            SELECT DISTINCT TraceId
            FROM metrics.otel_traces
            WHERE Timestamp >= %(from_date)s
              AND Timestamp <= %(to_date)s
              AND SpanName = 'gateway_analytics'
              AND SpanAttributes['{resource_attr_key}'] = %(resource_id)s
              AND SpanAttributes['gateway_analytics.project_id'] = %(project_id)s
        """  # nosec B608

        if flatten:
            # Flatten mode: return all spans for matching traces
            count_query = f"""
            SELECT count() as total_count
            FROM metrics.otel_traces
            WHERE TraceId IN ({trace_id_subquery})
            """  # nosec B608

            count_result = await self.clickhouse_client.execute_query(count_query, params)
            total_count = count_result[0][0] if count_result else 0

            # Data query: all spans for matching traces, sorted by timestamp
            data_query = f"""
            SELECT *
            FROM metrics.otel_traces
            WHERE TraceId IN ({trace_id_subquery})
            ORDER BY Timestamp DESC
            LIMIT %(limit)s OFFSET %(offset)s
            """  # nosec B608

            results = await self.clickhouse_client.execute_query(data_query, params)

            # Transform rows to TraceItem objects
            # In flatten mode, child_span_count is always 0 since all spans are visible in the flat list
            items = []
            for row in results:
                events = []
                if row[15] and row[16]:
                    for i in range(len(row[15])):
                        events.append(
                            TraceEvent(
                                timestamp=row[15][i],
                                name=row[16][i],
                                attributes=dict(row[17][i]) if row[17] and i < len(row[17]) else {},
                            )
                        )

                links = []
                if row[18] and row[19]:
                    for i in range(len(row[18])):
                        links.append(
                            TraceLink(
                                trace_id=row[18][i],
                                span_id=row[19][i] if i < len(row[19]) else "",
                                trace_state=row[20][i] if row[20] and i < len(row[20]) else "",
                                attributes=dict(row[21][i]) if row[21] and i < len(row[21]) else {},
                            )
                        )

                items.append(
                    TraceItem(
                        timestamp=row[0],
                        trace_id=row[1],
                        span_id=row[2],
                        parent_span_id=row[3] or "",
                        trace_state=row[4] or "",
                        span_name=row[5],
                        span_kind=row[6],
                        service_name=row[7],
                        resource_attributes=dict(row[8]) if row[8] else {},
                        scope_name=row[9] or "",
                        scope_version=row[10] or "",
                        span_attributes=dict(row[11]) if row[11] else {},
                        duration=row[12],
                        status_code=row[13],
                        status_message=row[14] or "",
                        events=events,
                        links=links,
                        child_span_count=0,  # Always 0 in flatten mode - all spans visible
                    )
                )
        else:
            # Default mode: return only root spans with child count
            count_query = f"""
            SELECT count() as total_count
            FROM metrics.otel_traces
            WHERE Timestamp >= %(from_date)s
              AND Timestamp <= %(to_date)s
              AND SpanName = 'gateway_analytics'
              AND SpanAttributes['{resource_attr_key}'] = %(resource_id)s
              AND SpanAttributes['gateway_analytics.project_id'] = %(project_id)s
            """  # nosec B608

            count_result = await self.clickhouse_client.execute_query(count_query, params)
            total_count = count_result[0][0] if count_result else 0

            # Data query with child span count using LEFT JOIN
            data_query = f"""
            SELECT
                t.*,
                COALESCE(counts.span_count, 1) - 1 as child_span_count
            FROM metrics.otel_traces t
            LEFT JOIN (
                SELECT TraceId, count() as span_count
                FROM metrics.otel_traces
                WHERE TraceId IN ({trace_id_subquery})
                GROUP BY TraceId
            ) as counts ON t.TraceId = counts.TraceId
            WHERE t.Timestamp >= %(from_date)s
              AND t.Timestamp <= %(to_date)s
              AND t.SpanName = 'gateway_analytics'
              AND t.SpanAttributes['{resource_attr_key}'] = %(resource_id)s
              AND t.SpanAttributes['gateway_analytics.project_id'] = %(project_id)s
            ORDER BY t.Timestamp DESC
            LIMIT %(limit)s OFFSET %(offset)s
            """  # nosec B608

            results = await self.clickhouse_client.execute_query(data_query, params)

            # Transform rows to TraceItem objects
            # Column indices: 0-21 from otel_traces, 22: child_span_count from JOIN
            items = []
            for row in results:
                events = []
                if row[15] and row[16]:
                    for i in range(len(row[15])):
                        events.append(
                            TraceEvent(
                                timestamp=row[15][i],
                                name=row[16][i],
                                attributes=dict(row[17][i]) if row[17] and i < len(row[17]) else {},
                            )
                        )

                links = []
                if row[18] and row[19]:
                    for i in range(len(row[18])):
                        links.append(
                            TraceLink(
                                trace_id=row[18][i],
                                span_id=row[19][i] if i < len(row[19]) else "",
                                trace_state=row[20][i] if row[20] and i < len(row[20]) else "",
                                attributes=dict(row[21][i]) if row[21] and i < len(row[21]) else {},
                            )
                        )

                items.append(
                    TraceItem(
                        timestamp=row[0],
                        trace_id=row[1],
                        span_id=row[2],
                        parent_span_id=row[3] or "",
                        trace_state=row[4] or "",
                        span_name=row[5],
                        span_kind=row[6],
                        service_name=row[7],
                        resource_attributes=dict(row[8]) if row[8] else {},
                        scope_name=row[9] or "",
                        scope_version=row[10] or "",
                        span_attributes=dict(row[11]) if row[11] else {},
                        duration=row[12],
                        status_code=row[13],
                        status_message=row[14] or "",
                        events=events,
                        links=links,
                        child_span_count=row[22],
                    )
                )

        return TraceListResponse(
            items=items,
            total_count=total_count,
            offset=offset,
            limit=limit,
        )

    async def get_trace(self, trace_id: str) -> TraceDetailResponse:
        """Get all spans for a single trace.

        Queries the otel_traces table for all spans matching the trace_id.

        Args:
            trace_id: The trace ID to retrieve

        Returns:
            TraceDetailResponse with all spans for the trace
        """
        await self.initialize()

        query = """
        SELECT *
        FROM metrics.otel_traces
        WHERE TraceId = %(trace_id)s
        ORDER BY Timestamp ASC
        """

        params = {"trace_id": trace_id}
        results = await self.clickhouse_client.execute_query(query, params)

        # Transform rows to TraceItem objects
        # Column indices based on otel_traces table:
        # 0: Timestamp, 1: TraceId, 2: SpanId, 3: ParentSpanId, 4: TraceState,
        # 5: SpanName, 6: SpanKind, 7: ServiceName, 8: ResourceAttributes,
        # 9: ScopeName, 10: ScopeVersion, 11: SpanAttributes, 12: Duration,
        # 13: StatusCode, 14: StatusMessage, 15: Events.Timestamp, 16: Events.Name,
        # 17: Events.Attributes, 18: Links.TraceId, 19: Links.SpanId,
        # 20: Links.TraceState, 21: Links.Attributes

        # Build parent-child relationship map for counting all nested descendants
        children_map: dict[str, list[str]] = {}
        for row in results:
            span_id = row[2]
            parent_span_id = row[3] or ""
            if parent_span_id:
                if parent_span_id not in children_map:
                    children_map[parent_span_id] = []
                children_map[parent_span_id].append(span_id)

        # Memoization cache for O(n) performance instead of O(n²)
        descendant_count_cache: dict[str, int] = {}

        def count_all_descendants(span_id: str) -> int:
            """Count all nested descendants with memoization for O(n) performance."""
            if span_id in descendant_count_cache:
                return descendant_count_cache[span_id]

            direct_children = children_map.get(span_id, [])
            total = len(direct_children)
            for child_id in direct_children:
                total += count_all_descendants(child_id)

            descendant_count_cache[span_id] = total
            return total

        spans = []
        for row in results:
            # Build events list (columns 15, 16, 17)
            events = []
            if row[15] and row[16]:
                for i in range(len(row[15])):
                    events.append(
                        TraceEvent(
                            timestamp=row[15][i],
                            name=row[16][i],
                            attributes=dict(row[17][i]) if row[17] and i < len(row[17]) else {},
                        )
                    )

            # Build links list (columns 18, 19, 20, 21)
            links = []
            if row[18] and row[19]:
                for i in range(len(row[18])):
                    links.append(
                        TraceLink(
                            trace_id=row[18][i],
                            span_id=row[19][i] if i < len(row[19]) else "",
                            trace_state=row[20][i] if row[20] and i < len(row[20]) else "",
                            attributes=dict(row[21][i]) if row[21] and i < len(row[21]) else {},
                        )
                    )

            span_id = row[2]
            spans.append(
                TraceItem(
                    timestamp=row[0],
                    trace_id=row[1],
                    span_id=span_id,
                    parent_span_id=row[3] or "",
                    trace_state=row[4] or "",
                    span_name=row[5],
                    span_kind=row[6],
                    service_name=row[7],
                    resource_attributes=dict(row[8]) if row[8] else {},
                    scope_name=row[9] or "",
                    scope_version=row[10] or "",
                    span_attributes=dict(row[11]) if row[11] else {},
                    duration=row[12],
                    status_code=row[13],
                    status_message=row[14] or "",
                    events=events,
                    links=links,
                    child_span_count=count_all_descendants(span_id),
                )
            )

        return TraceDetailResponse(
            trace_id=trace_id,
            spans=spans,
            total_spans=len(spans),
        )

    # ------------------------------------------------------------------
    # Telemetry Query API
    # ------------------------------------------------------------------

    async def query_prompt_telemetry(self, request: TelemetryQueryRequest) -> TelemetryQueryResponse:
        """Query prompt telemetry data with flexible span selection and tree building.

        Executes a two-query approach:
        1. Count query for pagination metadata
        2. Data query for all spans in the matching trace set

        Then builds a nested span tree in Python, pruned to the requested depth.

        Args:
            request: Validated TelemetryQueryRequest with project_id injected.

        Returns:
            TelemetryQueryResponse with nested span tree and pagination info.
        """
        import time

        await self.initialize()

        start_time = time.monotonic()

        builder = TelemetryQueryBuilder()
        data_query, count_query, params = builder.build_query(request)

        # Execute count query for pagination
        try:
            count_result = await self.clickhouse_client.execute_query(count_query, params)
            total_count = count_result[0][0] if count_result else 0
        except Exception as e:
            if "timeout" in str(e).lower() or "TIMEOUT" in str(e):
                from budmicroframe.commons.schemas import ErrorResponse

                return ErrorResponse(  # type: ignore[return-value]
                    message="Query timed out. Try narrowing the time range or adding filters.",
                    status_code=504,
                )
            raise

        # Execute data query for all spans in matching traces
        try:
            results = await self.clickhouse_client.execute_query(data_query, params)
        except Exception as e:
            if "timeout" in str(e).lower() or "TIMEOUT" in str(e):
                from budmicroframe.commons.schemas import ErrorResponse

                return ErrorResponse(  # type: ignore[return-value]
                    message="Query timed out. Try narrowing the time range or adding filters.",
                    status_code=504,
                )
            raise

        # Determine column names from the SELECT clause
        column_names = self._get_telemetry_column_names(request)

        # Build the span tree
        data = self._build_telemetry_span_tree(results, column_names, request)

        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        return TelemetryQueryResponse(
            data=data,
            total_count=total_count,
            limit=request.limit,
            offset=request.offset,
            has_more=(request.offset + request.limit) < total_count,
            query_time_ms=elapsed_ms,
        )

    def _get_telemetry_column_names(self, request: TelemetryQueryRequest) -> list[str]:
        """Build a list of column names matching the SELECT clause order.

        This must match the order produced by TelemetryQueryBuilder._build_select_clause.
        """
        columns = list(DEFAULT_SELECT_COLUMNS)

        if request.select_attributes:
            for key in request.select_attributes:
                validate_attribute_key(key)
                columns.append(f"attr:{key}")

        if request.include_all_attributes:
            columns.append("SpanAttributes")
            columns.append("ResourceAttributes")
        elif request.include_resource_attributes:
            columns.append("ResourceAttributes")

        if request.include_events:
            columns.extend(["Events.Timestamp", "Events.Name", "Events.Attributes"])

        if request.include_links:
            columns.extend(["Links.TraceId", "Links.SpanId", "Links.TraceState", "Links.Attributes"])

        # Internal columns for tree builder target filtering
        if request.span_names is None and not request.include_all_attributes:
            columns.append("_internal:prompt_id")
            columns.append("_internal:project_id")

        return columns

    def _build_telemetry_span_tree(
        self,
        flat_rows: list[tuple],
        column_names: list[str],
        request: TelemetryQueryRequest,
    ) -> list[TelemetrySpanItem]:
        """Build nested span tree from flat ClickHouse rows.

        1. Index all spans by span_id
        2. Build children_map: parent_span_id -> [child_span_ids]
        3. Count all descendants per span (memoized, O(n))
        4. Identify target spans (gateway_analytics or span_names matches)
        5. For each target span, recursively build nested children up to depth

        Args:
            flat_rows: Raw row tuples from ClickHouse.
            column_names: Column names matching row positions.
            request: The original query request (for depth, span_names).

        Returns:
            List of TelemetrySpanItem with nested children.
        """
        if not flat_rows:
            return []

        # Map column names to indices
        col_idx = {name: i for i, name in enumerate(column_names)}

        # Build span_by_id and children_map
        span_by_id: dict[str, dict[str, Any]] = {}
        children_map: dict[str, list[str]] = {}
        target_span_ids: list[str] = []

        for row in flat_rows:
            span_dict = self._telemetry_row_to_dict(row, col_idx, request)
            span_id = span_dict["span_id"]
            span_by_id[span_id] = span_dict

            parent_id = span_dict["parent_span_id"]
            if parent_id:
                if parent_id not in children_map:
                    children_map[parent_id] = []
                children_map[parent_id].append(span_id)

        # Identify target spans
        for span_id, span_dict in span_by_id.items():
            if request.span_names is None:
                # Default: gateway_analytics spans are targets
                if span_dict["span_name"] == "gateway_analytics":
                    # Verify prompt_id and project_id match to exclude
                    # gateway_analytics spans from other prompts sharing the trace
                    if request.include_all_attributes:
                        attrs = span_dict.get("attributes", {})
                        prompt_ok = attrs.get("gateway_analytics.prompt_id") == request.prompt_id
                        project_ok = attrs.get("gateway_analytics.project_id") == request.project_id
                    else:
                        prompt_ok = span_dict.get("_prompt_id", "") == request.prompt_id
                        project_ok = span_dict.get("_project_id", "") == request.project_id
                    if prompt_ok and project_ok:
                        target_span_ids.append(span_id)
            else:
                # Custom: spans matching the requested names
                if span_dict["span_name"] in request.span_names:
                    target_span_ids.append(span_id)

        # Memoized descendant count (O(n) total)
        descendant_cache: dict[str, int] = {}

        def count_descendants(sid: str) -> int:
            if sid in descendant_cache:
                return descendant_cache[sid]
            children = children_map.get(sid, [])
            total = len(children)
            for child_id in children:
                total += count_descendants(child_id)
            descendant_cache[sid] = total
            return total

        # Build nested tree with depth pruning
        depth = request.depth

        def build_node(sid: str, current_depth: int) -> TelemetrySpanItem:
            span = span_by_id[sid]
            child_count = count_descendants(sid)

            children_items: list[TelemetrySpanItem] = []
            if depth == -1 or current_depth < depth:
                for child_id in children_map.get(sid, []):
                    if child_id in span_by_id:
                        children_items.append(build_node(child_id, current_depth + 1))

            return TelemetrySpanItem(
                timestamp=span["timestamp"],
                trace_id=span["trace_id"],
                span_id=span["span_id"],
                parent_span_id=span["parent_span_id"],
                trace_state=span.get("trace_state", ""),
                span_name=span["span_name"],
                span_kind=span.get("span_kind", ""),
                service_name=span.get("service_name", ""),
                scope_name=span.get("scope_name", ""),
                scope_version=span.get("scope_version", ""),
                duration=span.get("duration", 0),
                status_code=span.get("status_code", ""),
                status_message=span.get("status_message", ""),
                child_count=child_count,
                children=children_items,
                attributes=span.get("attributes", {}),
                resource_attributes=span.get("resource_attributes"),
                events=span.get("events"),
                links=span.get("links"),
            )

        return [build_node(sid, 0) for sid in target_span_ids if sid in span_by_id]

    def _telemetry_row_to_dict(
        self,
        row: tuple,
        col_idx: dict[str, int],
        request: TelemetryQueryRequest,
    ) -> dict[str, Any]:
        """Convert a ClickHouse row tuple to a span dict.

        Args:
            row: Raw row tuple from ClickHouse.
            col_idx: Map of column name to position index.
            request: The query request (for projection options).

        Returns:
            Dict with span fields ready for TelemetrySpanItem construction.
        """
        span: dict[str, Any] = {
            "timestamp": str(row[col_idx["Timestamp"]]) if "Timestamp" in col_idx else "",
            "trace_id": row[col_idx["TraceId"]] if "TraceId" in col_idx else "",
            "span_id": row[col_idx["SpanId"]] if "SpanId" in col_idx else "",
            "parent_span_id": (row[col_idx["ParentSpanId"]] or "") if "ParentSpanId" in col_idx else "",
            "trace_state": (row[col_idx["TraceState"]] or "") if "TraceState" in col_idx else "",
            "span_name": row[col_idx["SpanName"]] if "SpanName" in col_idx else "",
            "span_kind": row[col_idx["SpanKind"]] if "SpanKind" in col_idx else "",
            "service_name": row[col_idx["ServiceName"]] if "ServiceName" in col_idx else "",
            "scope_name": (row[col_idx["ScopeName"]] or "") if "ScopeName" in col_idx else "",
            "scope_version": (row[col_idx["ScopeVersion"]] or "") if "ScopeVersion" in col_idx else "",
            "duration": row[col_idx["Duration"]] if "Duration" in col_idx else 0,
            "status_code": row[col_idx["StatusCode"]] if "StatusCode" in col_idx else "",
            "status_message": (row[col_idx["StatusMessage"]] or "") if "StatusMessage" in col_idx else "",
        }

        # Internal filtering columns (not exposed in response attributes)
        if "_internal:prompt_id" in col_idx:
            span["_prompt_id"] = row[col_idx["_internal:prompt_id"]] or ""
        if "_internal:project_id" in col_idx:
            span["_project_id"] = row[col_idx["_internal:project_id"]] or ""

        # Build attributes from select_attributes
        attributes: dict[str, str] = {}
        if request.select_attributes:
            for key in request.select_attributes:
                attr_col = f"attr:{key}"
                if attr_col in col_idx:
                    val = row[col_idx[attr_col]]
                    attributes[key] = str(val) if val else ""

        # If include_all_attributes, merge the full SpanAttributes map
        if request.include_all_attributes and "SpanAttributes" in col_idx:
            raw = row[col_idx["SpanAttributes"]]
            if raw:
                attributes.update({k: str(v) for k, v in dict(raw).items()})

        span["attributes"] = attributes

        # Resource attributes
        if (request.include_all_attributes or request.include_resource_attributes) and "ResourceAttributes" in col_idx:
            raw = row[col_idx["ResourceAttributes"]]
            span["resource_attributes"] = {k: str(v) for k, v in dict(raw).items()} if raw else {}

        # Events
        if request.include_events and "Events.Timestamp" in col_idx:
            events = []
            ts_col = col_idx["Events.Timestamp"]
            name_col = col_idx["Events.Name"]
            attr_col = col_idx["Events.Attributes"]
            if row[ts_col] and row[name_col]:
                for i in range(len(row[ts_col])):
                    events.append(
                        {
                            "timestamp": str(row[ts_col][i]),
                            "name": row[name_col][i],
                            "attributes": dict(row[attr_col][i]) if row[attr_col] and i < len(row[attr_col]) else {},
                        }
                    )
            span["events"] = events

        # Links
        if request.include_links and "Links.TraceId" in col_idx:
            links = []
            tid_col = col_idx["Links.TraceId"]
            sid_col = col_idx["Links.SpanId"]
            state_col = col_idx["Links.TraceState"]
            lattr_col = col_idx["Links.Attributes"]
            if row[tid_col] and row[sid_col]:
                for i in range(len(row[tid_col])):
                    links.append(
                        {
                            "trace_id": row[tid_col][i],
                            "span_id": row[sid_col][i] if i < len(row[sid_col]) else "",
                            "trace_state": row[state_col][i] if row[state_col] and i < len(row[state_col]) else "",
                            "attributes": dict(row[lattr_col][i])
                            if row[lattr_col] and i < len(row[lattr_col])
                            else {},
                        }
                    )
            span["links"] = links

        return span

    async def _get_inference_from_fact_table(self, inference_id: str) -> Optional[dict]:
        """Try to get inference from InferenceFact table.

        This is the optimized path for chat/blocked endpoint types.
        Returns None if not found, otherwise returns dict with all columns.

        Args:
            inference_id: UUID of the inference or trace_id for blocked requests

        Returns:
            Dictionary with all InferenceFact columns, or None if not found
        """
        # First check if InferenceFact table exists
        try:
            table_exists_query = "EXISTS TABLE InferenceFact"
            table_exists_result = await self.clickhouse_client.execute_query(table_exists_query)
            if not table_exists_result or table_exists_result[0][0] != 1:
                logger.debug("InferenceFact table does not exist")
                return None
        except Exception as e:
            logger.warning(f"Failed to check InferenceFact table existence: {e}")
            return None

        # Query InferenceFact by inference_id OR trace_id (for blocked requests)
        query = """
        SELECT
            -- OTel identifiers
            id,
            trace_id,
            span_id,
            -- Core identifiers
            inference_id,
            project_id,
            endpoint_id,
            model_id,
            api_key_id,
            api_key_project_id,
            user_id,
            -- Timestamps
            timestamp,
            request_arrival_time,
            request_forward_time,
            -- Status & cost
            is_success,
            cost,
            status_code,
            toString(request_ip) as request_ip,
            response_analysis,
            -- Error tracking
            error_code,
            error_message,
            error_type,
            -- Model info
            model_inference_id,
            model_name,
            model_provider,
            endpoint_type,
            -- Performance metrics
            input_tokens,
            output_tokens,
            response_time_ms,
            ttft_ms,
            cached,
            finish_reason,
            -- Content
            toValidUTF8(system_prompt) as system_prompt,
            toValidUTF8(input_messages) as input_messages,
            toValidUTF8(output) as output,
            toValidUTF8(raw_request) as raw_request,
            toValidUTF8(raw_response) as raw_response,
            toValidUTF8(gateway_request) as gateway_request,
            toValidUTF8(gateway_response) as gateway_response,
            guardrail_scan_summary,
            -- Chat inference
            chat_inference_id,
            episode_id,
            function_name,
            variant_name,
            processing_time_ms,
            toValidUTF8(chat_input) as chat_input,
            toValidUTF8(chat_output) as chat_output,
            tags,
            inference_params,
            extra_body,
            tool_params,
            -- Gateway analytics - geographic
            country_code,
            country_name,
            region,
            city,
            latitude,
            longitude,
            timezone,
            asn,
            isp,
            -- Gateway analytics - client
            toString(client_ip) as client_ip,
            toValidUTF8(user_agent) as user_agent,
            device_type,
            browser_name,
            browser_version,
            os_name,
            os_version,
            is_bot,
            -- Gateway analytics - request context
            method,
            path,
            query_params,
            body_size,
            response_size,
            protocol_version,
            -- Gateway analytics - performance
            gateway_processing_ms,
            total_duration_ms,
            -- Gateway analytics - routing & blocking
            model_version,
            routing_decision,
            is_blocked,
            block_reason,
            block_rule_id,
            proxy_chain,
            -- Gateway analytics - headers & timestamps
            request_headers,
            response_headers,
            request_timestamp,
            response_timestamp,
            gateway_tags,
            -- Blocking event data
            blocking_event_id,
            rule_id,
            rule_type,
            rule_name,
            rule_priority,
            block_reason_detail,
            action_taken,
            blocked_at
        FROM InferenceFact
        WHERE inference_id = %(inference_id)s
           OR trace_id = %(inference_id)s
        ORDER BY timestamp DESC
        LIMIT 1
        """

        params = {"inference_id": inference_id}
        try:
            results, column_descriptions = await self.clickhouse_client.execute_query(
                query, params, with_column_types=True
            )

            if not results:
                logger.debug(f"Inference {inference_id} not found in InferenceFact")
                return None

            # Convert row to dictionary
            from budmetrics.observability.models import ClickHouseClient

            row_dict = ClickHouseClient.row_to_dict(results[0], column_descriptions)
            logger.info(f"Found inference {inference_id} in InferenceFact table")
            return row_dict
        except Exception as e:
            logger.warning(f"Error querying InferenceFact for {inference_id}: {e}")
            return None

    def _build_response_from_fact_row(self, row_dict: dict) -> EnhancedInferenceDetailResponse:
        """Build EnhancedInferenceDetailResponse from InferenceFact row.

        Args:
            row_dict: Dictionary with all InferenceFact columns

        Returns:
            EnhancedInferenceDetailResponse populated from the fact table row
        """
        import json

        # Helper functions
        def safe_uuid(value):
            if value is None:
                return None
            if isinstance(value, UUID):
                return value
            try:
                return UUID(str(value))
            except (ValueError, TypeError):
                return None

        def safe_float(val):
            try:
                if val is None or val == "":
                    return None
                return float(val)
            except (ValueError, TypeError):
                return None

        def safe_int(val):
            try:
                if val is None or val == "":
                    return None
                return int(val)
            except (ValueError, TypeError):
                return None

        def safe_dict(val):
            try:
                if val is None or val == "":
                    return None
                if isinstance(val, dict):
                    return val
                if isinstance(val, str):
                    return json.loads(val)
                if isinstance(val, (list, tuple)):
                    return dict(val)
                return None
            except (TypeError, ValueError, json.JSONDecodeError):
                return None

        def safe_str(val):
            if val is None or val == "":
                return None
            return str(val)

        # Get endpoint type
        endpoint_type = row_dict.get("endpoint_type", "chat")

        # Parse input messages - prefer chat_input over input_messages
        input_messages_raw = row_dict.get("chat_input") or row_dict.get("input_messages")
        messages = []
        try:
            if input_messages_raw:
                if isinstance(input_messages_raw, str):
                    parsed_data = json.loads(input_messages_raw)
                    if isinstance(parsed_data, dict) and "messages" in parsed_data:
                        messages = parsed_data["messages"]
                    elif isinstance(parsed_data, list):
                        messages = parsed_data
                elif isinstance(input_messages_raw, list):
                    messages = input_messages_raw
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Failed to parse messages: {e}")
            if input_messages_raw and isinstance(input_messages_raw, str):
                messages = [{"role": "user", "content": input_messages_raw}]

        # Build combined messages with system prompt
        combined_messages = []
        system_prompt = row_dict.get("system_prompt")
        if system_prompt:
            combined_messages.append({"role": "system", "content": str(system_prompt)})
        combined_messages.extend(messages)

        # Add assistant response - prefer chat_output over output
        output_raw = row_dict.get("chat_output") or row_dict.get("output")
        if output_raw:
            try:
                output_content = json.loads(output_raw)
                content = output_content
            except (json.JSONDecodeError, TypeError):
                content = str(output_raw)
            combined_messages.append({"role": "assistant", "content": content})

        # Build gateway metadata if data is present
        gateway_metadata = None
        gateway_field_names = [
            "client_ip",
            "proxy_chain",
            "protocol_version",
            "country_code",
            "region",
            "city",
            "latitude",
            "longitude",
            "timezone",
            "asn",
            "isp",
            "user_agent",
            "device_type",
            "browser_name",
            "browser_version",
            "os_name",
            "os_version",
            "is_bot",
            "method",
            "path",
            "query_params",
            "request_headers",
            "body_size",
            "gateway_processing_ms",
            "total_duration_ms",
            "routing_decision",
            "model_version",
            "response_size",
            "response_headers",
            "is_blocked",
            "block_reason",
            "block_rule_id",
            "gateway_tags",
        ]
        gateway_field_values = [row_dict.get(field) for field in gateway_field_names]
        has_gateway_data = any(field is not None and field != "" for field in gateway_field_values)

        if has_gateway_data:
            try:
                gateway_metadata = GatewayMetadata(
                    client_ip=safe_str(row_dict.get("client_ip")),
                    proxy_chain=safe_str(row_dict.get("proxy_chain")),
                    protocol_version=safe_str(row_dict.get("protocol_version")),
                    country_code=safe_str(row_dict.get("country_code")),
                    region=safe_str(row_dict.get("region")),
                    city=safe_str(row_dict.get("city")),
                    latitude=safe_float(row_dict.get("latitude")),
                    longitude=safe_float(row_dict.get("longitude")),
                    timezone=safe_str(row_dict.get("timezone")),
                    asn=safe_int(row_dict.get("asn")),
                    isp=safe_str(row_dict.get("isp")),
                    user_agent=safe_str(row_dict.get("user_agent")),
                    device_type=safe_str(row_dict.get("device_type")),
                    browser_name=safe_str(row_dict.get("browser_name")),
                    browser_version=safe_str(row_dict.get("browser_version")),
                    os_name=safe_str(row_dict.get("os_name")),
                    os_version=safe_str(row_dict.get("os_version")),
                    is_bot=row_dict.get("is_bot"),
                    method=safe_str(row_dict.get("method")),
                    path=safe_str(row_dict.get("path")),
                    query_params=safe_str(row_dict.get("query_params")),
                    request_headers=safe_dict(row_dict.get("request_headers")),
                    body_size=safe_int(row_dict.get("body_size")),
                    api_key_id=safe_str(row_dict.get("api_key_id")),
                    auth_method=None,  # Not stored in InferenceFact
                    user_id=safe_str(row_dict.get("user_id")),
                    gateway_processing_ms=safe_int(row_dict.get("gateway_processing_ms")),
                    total_duration_ms=safe_int(row_dict.get("total_duration_ms")),
                    routing_decision=safe_str(row_dict.get("routing_decision")),
                    model_version=safe_str(row_dict.get("model_version")),
                    status_code=safe_int(row_dict.get("status_code")),
                    response_size=safe_int(row_dict.get("response_size")),
                    response_headers=safe_dict(row_dict.get("response_headers")),
                    error_type=safe_str(row_dict.get("error_type")),
                    error_message=safe_str(row_dict.get("error_message")),
                    is_blocked=row_dict.get("is_blocked"),
                    block_reason=safe_str(row_dict.get("block_reason")),
                    block_rule_id=safe_str(row_dict.get("block_rule_id")),
                    tags=safe_dict(row_dict.get("gateway_tags")),
                )
            except Exception as e:
                logger.warning(f"Failed to build gateway metadata: {e}")
                gateway_metadata = None

        # Get inference_id - for blocked requests it might be None
        inference_id = safe_uuid(row_dict.get("inference_id"))
        # Fall back to trace_id for blocked requests
        if inference_id is None:
            trace_id = row_dict.get("trace_id")
            if trace_id:
                with contextlib.suppress(ValueError, TypeError):
                    inference_id = UUID(trace_id)

        # Get timestamps
        timestamp = row_dict.get("timestamp")
        request_arrival_time = row_dict.get("request_arrival_time") or timestamp
        request_forward_time = row_dict.get("request_forward_time") or timestamp

        return EnhancedInferenceDetailResponse(
            object="inference_detail",
            inference_id=inference_id,
            timestamp=timestamp,
            model_name=str(row_dict.get("model_name")) if row_dict.get("model_name") else "",
            model_provider=str(row_dict.get("model_provider")) if row_dict.get("model_provider") else "unknown",
            model_id=safe_uuid(row_dict.get("model_id")),
            system_prompt=safe_str(row_dict.get("system_prompt")),
            messages=combined_messages,
            output=str(output_raw) if output_raw else "",
            function_name=safe_str(row_dict.get("function_name")),
            variant_name=safe_str(row_dict.get("variant_name")),
            episode_id=safe_uuid(row_dict.get("episode_id")),
            input_tokens=safe_int(row_dict.get("input_tokens")) or 0,
            output_tokens=safe_int(row_dict.get("output_tokens")) or 0,
            response_time_ms=safe_int(row_dict.get("response_time_ms")) or 0,
            ttft_ms=safe_int(row_dict.get("ttft_ms")),
            processing_time_ms=safe_int(row_dict.get("processing_time_ms")),
            request_ip=safe_str(row_dict.get("request_ip")),
            request_arrival_time=request_arrival_time,
            request_forward_time=request_forward_time,
            project_id=safe_uuid(row_dict.get("project_id")),
            api_key_project_id=safe_uuid(row_dict.get("api_key_project_id")),
            endpoint_id=safe_uuid(row_dict.get("endpoint_id")),
            is_success=bool(row_dict.get("is_success")) if row_dict.get("is_success") is not None else True,
            cached=bool(row_dict.get("cached")) if row_dict.get("cached") is not None else False,
            finish_reason=safe_str(row_dict.get("finish_reason")),
            cost=safe_float(row_dict.get("cost")),
            error_code=safe_str(row_dict.get("error_code")),
            error_message=safe_str(row_dict.get("error_message")),
            error_type=safe_str(row_dict.get("error_type")),
            status_code=safe_int(row_dict.get("status_code")),
            raw_request=safe_str(row_dict.get("raw_request")),
            raw_response=safe_str(row_dict.get("raw_response")),
            gateway_request=safe_str(row_dict.get("gateway_request")),
            gateway_response=safe_str(row_dict.get("gateway_response")),
            gateway_metadata=gateway_metadata,
            feedback_count=0,  # Will be fetched separately if needed
            average_rating=None,
            endpoint_type=endpoint_type,
            embedding_details=None,
            audio_details=None,
            image_details=None,
            moderation_details=None,
        )

    async def get_inference_details(self, inference_id: str) -> EnhancedInferenceDetailResponse:
        """Get complete details for a single inference.

        Args:
            inference_id: UUID of the inference

        Returns:
            InferenceDetailResponse with full inference details
        """
        await self.initialize()

        # Validate inference_id is a valid UUID
        try:
            UUID(inference_id)
        except ValueError:
            raise ValueError("Invalid inference ID format") from None

        # InferenceFact is the canonical source for all inference data
        fact_row = await self._get_inference_from_fact_table(inference_id)
        if fact_row:
            endpoint_type = fact_row.get("endpoint_type", "chat")
            logger.info(f"Using InferenceFact for inference {inference_id} (endpoint_type={endpoint_type})")
            return self._build_response_from_fact_row(fact_row)

        # Inference not found in InferenceFact
        raise ValueError("Inference not found")

    async def get_inference_feedback(self, inference_id: str) -> InferenceFeedbackResponse:
        """Get all feedback associated with an inference.

        Args:
            inference_id: UUID of the inference

        Returns:
            InferenceFeedbackResponse with aggregated feedback
        """
        await self.initialize()

        # Validate inference_id is a valid UUID
        try:
            UUID(inference_id)
        except ValueError:
            raise ValueError("Invalid inference ID format") from None

        feedback_items = []

        # Get boolean feedback
        boolean_query = """
        SELECT id, metric_name, value, created_at
        FROM BooleanMetricFeedback
        WHERE target_id = %(inference_id)s
        ORDER BY created_at DESC
        """
        params = {"inference_id": inference_id}
        boolean_results = await self.clickhouse_client.execute_query(boolean_query, params)
        for row in boolean_results:
            feedback_items.append(
                FeedbackItem(
                    feedback_id=row[0],
                    feedback_type="boolean",
                    metric_name=row[1],
                    value=bool(row[2]),
                    created_at=row[3],
                )
            )

        # Get float feedback
        float_query = """
        SELECT id, metric_name, value, created_at
        FROM FloatMetricFeedback
        WHERE target_id = %(inference_id)s
        ORDER BY created_at DESC
        """
        float_results = await self.clickhouse_client.execute_query(float_query, params)
        for row in float_results:
            feedback_items.append(
                FeedbackItem(
                    feedback_id=row[0],
                    feedback_type="float",
                    metric_name=row[1],
                    value=float(row[2]),
                    created_at=row[3],
                )
            )

        # Get comment feedback
        comment_query = """
        SELECT id, comment, created_at
        FROM CommentFeedback
        WHERE target_id = %(inference_id)s
        ORDER BY created_at DESC
        """
        comment_results = await self.clickhouse_client.execute_query(comment_query, params)
        for row in comment_results:
            feedback_items.append(
                FeedbackItem(
                    feedback_id=row[0],
                    feedback_type="comment",
                    metric_name=None,
                    value=row[1],
                    created_at=row[2],
                )
            )

        # Get demonstration feedback
        # TODO: DemonstrationFeedback table might not exist or has different schema
        # Commenting out for now
        # demo_query = """
        # SELECT id, demonstration, created_at
        # FROM DemonstrationFeedback
        # WHERE target_id = %(inference_id)s
        # ORDER BY created_at DESC
        # """
        # demo_results = await self.clickhouse_client.execute_query(demo_query, params)
        # for row in demo_results:
        #     feedback_items.append(
        #         FeedbackItem(
        #             feedback_id=row[0],
        #             feedback_type="demonstration",
        #             metric_name=None,
        #             value=row[1],
        #             created_at=row[2],
        #         )
        #     )

        # Sort all feedback by created_at
        feedback_items.sort(key=lambda x: x.created_at, reverse=True)

        return InferenceFeedbackResponse(
            object="inference_feedback",
            inference_id=UUID(inference_id),
            feedback_items=feedback_items,
            total_count=len(feedback_items),
        )

    async def get_gateway_metrics(self, request: GatewayAnalyticsRequest) -> GatewayAnalyticsResponse:
        """Get gateway analytics metrics based on request parameters."""
        self._ensure_initialized()

        # Build and execute query
        query = self._build_gateway_analytics_query(request)
        params = {
            "from_date": request.from_date,
            "to_date": request.to_date or datetime.now(),
        }
        result = await self._clickhouse_client.execute_query(query, params)

        # Process results into response format
        items = self._process_gateway_metrics_results(result, request)

        # Calculate summary statistics if requested
        summary = None
        if len(items) > 0:
            summary = self._calculate_gateway_summary_stats(items, request)

        return GatewayAnalyticsResponse(object="gateway_analytics", code=200, items=items, summary=summary)

    async def get_geographical_stats(self, from_date, to_date, project_id, data_source="inference"):
        """Get geographical distribution statistics."""
        self._ensure_initialized()

        # Build queries for country and city stats
        country_query = self._build_geographical_query(from_date, to_date, project_id, "country", data_source)
        city_query = self._build_geographical_query(from_date, to_date, project_id, "city", data_source)

        # Execute queries in parallel
        country_result, city_result = await asyncio.gather(
            self._clickhouse_client.execute_query(country_query), self._clickhouse_client.execute_query(city_query)
        )

        # Process results
        total_requests = sum(row[1] for row in country_result) if country_result else 0

        countries = (
            [
                {
                    "country_code": row[0],
                    "count": row[1],
                    "percent": round((row[1] / total_requests) * 100, 2) if total_requests > 0 else 0,
                }
                for row in country_result
            ]
            if country_result
            else []
        )

        cities = (
            [
                {
                    "city": row[0],
                    "country_code": row[1],
                    "count": row[2],
                    "percent": round((row[2] / total_requests) * 100, 2) if total_requests > 0 else 0,
                    "latitude": row[3] if len(row) > 3 else None,
                    "longitude": row[4] if len(row) > 4 else None,
                }
                for row in city_result
                if row[0] is not None
            ]
            if city_result
            else []
        )

        # Create heatmap data for visualization
        heatmap_data = [
            {
                "lat": city["latitude"],
                "lng": city["longitude"],
                "count": city["count"],
                "city": city["city"],
                "country_code": city["country_code"],
            }
            for city in cities
            if city.get("latitude") and city.get("longitude")
        ]

        from budmetrics.observability.schemas import GatewayGeographicalStats

        return GatewayGeographicalStats(
            total_requests=total_requests,
            unique_countries=len(countries),
            unique_cities=len(cities),
            countries=countries[:50],
            cities=cities[:100],
            heatmap_data=heatmap_data,
        )

    async def get_top_routes(self, from_date, to_date, limit, project_id, data_source="inference"):
        """Get top API routes by request count."""
        self._ensure_initialized()

        query = self._build_top_routes_query(from_date, to_date, limit, project_id, data_source)
        result = await self._clickhouse_client.execute_query(query)

        routes = []
        if result:
            for row in result:
                routes.append(
                    {
                        "path": row[0],
                        "method": row[1] if len(row) > 1 else "GET",
                        "count": row[2] if len(row) > 2 else row[1],
                        "avg_response_time": row[3] if len(row) > 3 else 0,
                        "error_rate": row[4] if len(row) > 4 else 0,
                    }
                )

        return routes

    async def get_client_analytics(self, from_date, to_date, group_by, project_id, data_source="inference"):
        """Get client analytics (device, browser, OS distribution)."""
        self._ensure_initialized()

        query = self._build_client_analytics_query(from_date, to_date, group_by, project_id, data_source)
        result = await self._clickhouse_client.execute_query(query)

        distribution = {}
        total = 0

        if result:
            for row in result:
                distribution[row[0]] = row[1]
                total += row[1]

        # Calculate percentages
        distribution_with_percent = [
            {"name": name, "count": count, "percent": round((count / total * 100), 2) if total > 0 else 0}
            for name, count in distribution.items()
        ]

        return {"distribution": distribution_with_percent, "total": total, "group_by": group_by}

    def _build_gateway_analytics_query(self, request):
        """Build ClickHouse query for gateway analytics."""
        # Build prompt_id filter based on data_source
        data_source = getattr(request, "data_source", "inference")
        if data_source == "prompt":
            prompt_filter = "AND prompt_id IS NOT NULL AND prompt_id != ''"
        else:  # inference (default)
            prompt_filter = "AND (prompt_id IS NULL OR prompt_id = '')"

        # Build project_id filter
        project_id = getattr(request, "project_id", None)
        project_filter = f"AND project_id = '{project_id}'" if project_id else ""

        # This is a simplified version - you would need to implement the full query builder
        return f"""
            SELECT
                toStartOfHour(timestamp) as time_bucket,
                count(*) as request_count,
                avg(response_time_ms) as avg_response_time
            FROM InferenceFact
            WHERE timestamp >= %(from_date)s
                AND timestamp <= %(to_date)s
                {prompt_filter}
                {project_filter}
            GROUP BY time_bucket
            ORDER BY time_bucket
        """

    def _build_geographical_query(self, from_date, to_date, project_id, group_type, data_source="inference"):
        """Build query for geographical statistics."""
        # Build prompt_id filter based on data_source
        if data_source == "prompt":
            prompt_filter = "AND prompt_id IS NOT NULL AND prompt_id != ''"
        else:  # inference (default)
            prompt_filter = "AND (prompt_id IS NULL OR prompt_id = '')"

        if group_type == "country":
            return f"""
                SELECT
                    country_code,
                    count(*) as count
                FROM InferenceFact
                WHERE timestamp >= '{from_date.isoformat()}'
                    {f"AND timestamp <= '{to_date.isoformat()}'" if to_date else ""}
                    {f"AND project_id = '{project_id}'" if project_id else ""}
                    {prompt_filter}
                GROUP BY country_code
                ORDER BY count DESC
                LIMIT 50
            """
        else:  # city
            return f"""
                SELECT
                    city,
                    country_code,
                    count(*) as count,
                    any(latitude) as latitude,
                    any(longitude) as longitude
                FROM InferenceFact
                WHERE timestamp >= '{from_date.isoformat()}'
                    {f"AND timestamp <= '{to_date.isoformat()}'" if to_date else ""}
                    {f"AND project_id = '{project_id}'" if project_id else ""}
                    {prompt_filter}
                    AND city IS NOT NULL
                GROUP BY city, country_code
                ORDER BY count DESC
                LIMIT 100
            """

    def _build_blocking_stats_query(self, from_date, to_date, project_id):
        """Build query for blocking statistics."""
        return f"""
            SELECT
                blocking_rule,
                count(*) as count
            FROM bud.ModelInferenceDetails
            WHERE timestamp >= '{from_date.isoformat()}'
                {f"AND timestamp <= '{to_date.isoformat()}'" if to_date else ""}
                {f"AND project_id = '{project_id}'" if project_id else ""}
                AND is_blocked = true
            GROUP BY blocking_rule
            ORDER BY count DESC
        """

    def _build_total_requests_query(self, from_date, to_date, project_id):
        """Build query for total requests count."""
        return f"""
            SELECT count(*) as total
            FROM bud.ModelInferenceDetails
            WHERE timestamp >= '{from_date.isoformat()}'
                {f"AND timestamp <= '{to_date.isoformat()}'" if to_date else ""}
                {f"AND project_id = '{project_id}'" if project_id else ""}
        """

    def _build_top_routes_query(self, from_date, to_date, limit, project_id, data_source="inference"):
        """Build query for top routes."""
        # Build prompt_id filter based on data_source
        if data_source == "prompt":
            prompt_filter = "AND prompt_id IS NOT NULL AND prompt_id != ''"
        else:  # inference (default)
            prompt_filter = "AND (prompt_id IS NULL OR prompt_id = '')"

        return f"""
            SELECT
                path,
                method,
                count(*) as count,
                avg(response_time_ms) as avg_response_time,
                sum(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) / count(*) * 100 as error_rate
            FROM InferenceFact
            WHERE timestamp >= '{from_date.isoformat()}'
                {f"AND timestamp <= '{to_date.isoformat()}'" if to_date else ""}
                {f"AND project_id = '{project_id}'" if project_id else ""}
                {prompt_filter}
            GROUP BY path, method
            ORDER BY count DESC
            LIMIT {limit}
        """

    def _build_client_analytics_query(self, from_date, to_date, group_by, project_id, data_source="inference"):
        """Build query for client analytics."""
        field_map = {"device_type": "device_type", "browser": "browser_name", "os": "os_name"}
        field = field_map.get(group_by, "device_type")

        # Build prompt_id filter based on data_source
        if data_source == "prompt":
            prompt_filter = "AND prompt_id IS NOT NULL AND prompt_id != ''"
        else:  # inference (default)
            prompt_filter = "AND (prompt_id IS NULL OR prompt_id = '')"

        return f"""
            SELECT
                {field},
                count(*) as count
            FROM InferenceFact
            WHERE timestamp >= '{from_date.isoformat()}'
                {f"AND timestamp <= '{to_date.isoformat()}'" if to_date else ""}
                {f"AND project_id = '{project_id}'" if project_id else ""}
                {prompt_filter}
                AND {field} IS NOT NULL
            GROUP BY {field}
            ORDER BY count DESC
        """

    def _process_gateway_metrics_results(self, result, request):
        """Process gateway metrics query results."""
        from budmetrics.observability.schemas import (
            GatewayCountMetric,
            GatewayMetricsData,
            GatewayPerformanceMetric,
            GatewayPeriodBin,
        )

        items = []

        if result:
            for row in result:
                # Explicit type conversion for ClickHouse Decimal types
                request_count = int(row[1]) if row[1] is not None else 0
                avg_response_time = float(row[2]) if len(row) > 2 and row[2] is not None else 0.0

                items.append(
                    GatewayPeriodBin(
                        time_period=row[0],
                        items=[
                            GatewayMetricsData(
                                data={
                                    "request_count": GatewayCountMetric(count=request_count),
                                    "avg_response_time": GatewayPerformanceMetric(avg=avg_response_time),
                                }
                            )
                        ],
                    )
                )

        return items

    async def _debug_gateway_analytics_table(self, inference_id: str):
        """Debug method to check GatewayAnalytics table status and data."""
        try:
            # Check total count in GatewayAnalytics table
            count_query = "SELECT COUNT(*) FROM GatewayAnalytics"
            count_result = await self.clickhouse_client.execute_query(count_query)
            total_count = count_result[0][0] if count_result else 0
            logger.info(f"Total records in GatewayAnalytics: {total_count}")

            # Check count with non-null inference_id
            non_null_query = "SELECT COUNT(*) FROM GatewayAnalytics WHERE inference_id IS NOT NULL"
            non_null_result = await self.clickhouse_client.execute_query(non_null_query)
            non_null_count = non_null_result[0][0] if non_null_result else 0
            logger.info(f"Records with non-null inference_id: {non_null_count}")

            # Check for specific inference_id
            specific_query = "SELECT COUNT(*) FROM GatewayAnalytics WHERE inference_id = %(inference_id)s"
            params = {"inference_id": inference_id}
            specific_result = await self.clickhouse_client.execute_query(specific_query, params)
            specific_count = specific_result[0][0] if specific_result else 0
            logger.info(f"Records for inference_id {inference_id}: {specific_count}")

            # If no specific record, show some sample records
            if specific_count == 0 and non_null_count > 0:
                sample_query = "SELECT inference_id, client_ip, country_code, user_agent FROM GatewayAnalytics WHERE inference_id IS NOT NULL LIMIT 3"
                sample_result = await self.clickhouse_client.execute_query(sample_query)
                logger.info(f"Sample records from GatewayAnalytics: {sample_result}")

        except Exception as e:
            logger.error(f"Failed to debug GatewayAnalytics table: {e}")

    def _calculate_gateway_summary_stats(self, items, request):
        """Calculate summary statistics for gateway metrics."""
        total_requests = 0
        for item in items:
            if item.items:
                metric = item.items[0].data.get("request_count")
                if metric:
                    total_requests += metric.count

        return {
            "total_requests": total_requests,
            "time_range": {
                "from": request.from_date.isoformat(),
                "to": request.to_date.isoformat() if request.to_date else None,
            },
        }

    # New Aggregated Metrics Methods
    async def get_aggregated_metrics(self, request) -> dict:
        """Get aggregated metrics with server-side calculations.

        Strategy:
        - Uses rollup tables for metrics that don't require raw data (pre-aggregated)
        - Falls back to InferenceFact for percentile metrics (p95/p99 latency and ttft)

        Rollup Compatible: total_requests, success_rate, avg_latency, total_tokens,
                          total_input_tokens, total_output_tokens, avg_tokens, total_cost,
                          avg_cost, ttft_avg, cache_hit_rate, throughput_avg, error_rate,
                          unique_users
        Requires Raw Data: p95_latency, p99_latency, ttft_p95, ttft_p99
        """
        to_date = request.to_date or datetime.now()

        # Metrics that require raw data for percentile calculations
        raw_data_metrics = {"p95_latency", "p99_latency", "ttft_p95", "ttft_p99"}
        # Dimensions that require InferenceFact (not available in rollup tables)
        raw_data_dimensions = {"user"}
        needs_raw_data = any(m in raw_data_metrics for m in request.metrics) or (
            request.group_by and any(d in raw_data_dimensions for d in request.group_by)
        )

        if needs_raw_data:
            return await self._get_aggregated_metrics_from_inference_fact(request, to_date)
        else:
            return await self._get_aggregated_metrics_from_rollup(request, to_date)

    async def _get_aggregated_metrics_from_rollup(self, request, to_date: datetime) -> dict:
        """Get aggregated metrics from rollup tables (pre-aggregated).

        Uses InferenceMetrics5m/1h/1d based on time range for better performance.
        """
        # Select rollup table based on time range
        table = self.query_builder._select_rollup_table(request.from_date, to_date)

        # Build the base query with efficient aggregations
        select_fields = []

        # Add grouping fields if specified (use rm alias prefix)
        group_by_fields = []
        if request.group_by:
            for group in request.group_by:
                if group == "model":
                    group_by_fields.extend(["rm.model_id", "rm.model_name"])
                    select_fields.extend(["rm.model_id", "rm.model_name"])
                elif group == "project":
                    group_by_fields.append("rm.project_id")
                    select_fields.append("rm.project_id")
                elif group == "endpoint":
                    group_by_fields.append("rm.endpoint_id")
                    select_fields.append("rm.endpoint_id")
                elif group == "user_project":
                    group_by_fields.append("rm.api_key_project_id")
                    select_fields.append("rm.api_key_project_id")

        # Build aggregation fields using rollup aggregations
        # Use rm alias prefix to avoid column/alias name conflicts
        for metric in request.metrics:
            if metric == "total_requests":
                select_fields.append("SUM(rm.request_count) as total_requests")
            elif metric == "success_rate":
                select_fields.append(
                    "SUM(rm.success_count) * 100.0 / NULLIF(SUM(rm.request_count), 0) as success_rate"
                )
            elif metric == "avg_latency":
                select_fields.append("SUM(rm.sum_response_time_ms) / NULLIF(SUM(rm.request_count), 0) as avg_latency")
            elif metric == "total_tokens":
                select_fields.append("(SUM(rm.total_input_tokens) + SUM(rm.total_output_tokens)) as total_tokens")
            elif metric == "total_input_tokens":
                select_fields.append("SUM(rm.total_input_tokens) as total_input_tokens")
            elif metric == "total_output_tokens":
                select_fields.append("SUM(rm.total_output_tokens) as total_output_tokens")
            elif metric == "avg_tokens":
                select_fields.append(
                    "(SUM(rm.total_input_tokens) + SUM(rm.total_output_tokens)) / NULLIF(SUM(rm.request_count), 0) as avg_tokens"
                )
            elif metric == "total_cost":
                select_fields.append("SUM(rm.total_cost) as total_cost")
            elif metric == "avg_cost":
                select_fields.append("SUM(rm.total_cost) / NULLIF(SUM(rm.request_count), 0) as avg_cost")
            elif metric == "ttft_avg":
                select_fields.append("SUM(rm.sum_ttft_ms) / NULLIF(SUM(rm.request_count), 0) as ttft_avg")
            elif metric == "cache_hit_rate":
                select_fields.append(
                    "SUM(rm.cached_count) * 100.0 / NULLIF(SUM(rm.request_count), 0) as cache_hit_rate"
                )
            elif metric == "throughput_avg":
                select_fields.append(
                    "SUM(rm.total_output_tokens) * 1000.0 / NULLIF(SUM(rm.sum_response_time_ms), 0) as throughput_avg"
                )
            elif metric == "error_rate":
                select_fields.append("SUM(rm.error_count) * 100.0 / NULLIF(SUM(rm.request_count), 0) as error_rate")
            elif metric == "unique_users":
                select_fields.append("uniqMerge(rm.unique_users) as unique_users")

        # Build WHERE clause (use rm alias prefix)
        where_conditions = ["rm.time_bucket >= %(from_date)s", "rm.time_bucket <= %(to_date)s"]

        params = {
            "from_date": request.from_date,
            "to_date": to_date,
        }

        # Add filters (use rm alias prefix)
        if request.filters:
            for filter_key, filter_value in request.filters.items():
                if filter_key == "project_id":
                    if isinstance(filter_value, list):
                        placeholders = [f"%(project_{i})s" for i in range(len(filter_value))]
                        where_conditions.append(f"rm.project_id IN ({','.join(placeholders)})")
                        for i, val in enumerate(filter_value):
                            params[f"project_{i}"] = val
                    else:
                        where_conditions.append("rm.project_id = %(project_id)s")
                        params["project_id"] = filter_value
                elif filter_key == "api_key_project_id":
                    if isinstance(filter_value, list):
                        placeholders = [f"%(api_key_project_{i})s" for i in range(len(filter_value))]
                        where_conditions.append(f"rm.api_key_project_id IN ({','.join(placeholders)})")
                        for i, val in enumerate(filter_value):
                            params[f"api_key_project_{i}"] = val
                    else:
                        where_conditions.append("rm.api_key_project_id = %(api_key_project_id)s")
                        params["api_key_project_id"] = filter_value
                elif filter_key == "model_id":
                    where_conditions.append("rm.model_id = %(model_id)s")
                    params["model_id"] = filter_value
                elif filter_key == "endpoint_id":
                    where_conditions.append("rm.endpoint_id = %(endpoint_id)s")
                    params["endpoint_id"] = filter_value

        # Add data_source filter for prompt analytics
        if hasattr(request, "data_source"):
            if request.data_source == "inference":
                where_conditions.append("(rm.prompt_id IS NULL OR rm.prompt_id = '')")
            elif request.data_source == "prompt":
                where_conditions.append("rm.prompt_id IS NOT NULL AND rm.prompt_id != ''")

        # Build final query (use rm as table alias)
        order_by = "total_requests DESC" if "total_requests" in request.metrics else "1"
        query = f"""
        SELECT {", ".join(select_fields)}
        FROM {table} AS rm
        WHERE {" AND ".join(where_conditions)}
        {f"GROUP BY {', '.join(group_by_fields)}" if group_by_fields else ""}
        ORDER BY {order_by}
        """

        # Execute query
        results = await self.clickhouse_client.execute_query(query, params)

        return self._process_aggregated_metrics_results(results, request, to_date)

    async def _get_aggregated_metrics_from_inference_fact(self, request, to_date: datetime) -> dict:
        """Get aggregated metrics from InferenceFact (for percentile metrics).

        Uses InferenceFact when raw data is needed for quantile calculations.
        No JOINs required - all data in one denormalized table.
        """
        # Build the base query with efficient aggregations
        select_fields = []

        # Add grouping fields if specified (using ifact alias)
        group_by_fields = []
        if request.group_by:
            for group in request.group_by:
                if group == "model":
                    group_by_fields.extend(["ifact.model_id", "ifact.model_name"])
                    select_fields.extend(["ifact.model_id", "ifact.model_name"])
                elif group == "project":
                    group_by_fields.append("ifact.project_id")
                    select_fields.append("ifact.project_id")
                elif group == "endpoint":
                    group_by_fields.append("ifact.endpoint_id")
                    select_fields.append("ifact.endpoint_id")
                elif group == "user":
                    group_by_fields.append("ifact.user_id")
                    select_fields.append("ifact.user_id")
                elif group == "user_project":
                    group_by_fields.append("ifact.api_key_project_id")
                    select_fields.append("ifact.api_key_project_id")

        # Build aggregation fields based on requested metrics
        for metric in request.metrics:
            if metric == "total_requests":
                select_fields.append("COUNT(*) as total_requests")
            elif metric == "success_rate":
                select_fields.append("AVG(CASE WHEN ifact.is_success THEN 1.0 ELSE 0.0 END) * 100 as success_rate")
            elif metric == "avg_latency":
                select_fields.append("AVG(ifact.response_time_ms) as avg_latency")
            elif metric == "p95_latency":
                select_fields.append("quantile(0.95)(ifact.response_time_ms) as p95_latency")
            elif metric == "p99_latency":
                select_fields.append("quantile(0.99)(ifact.response_time_ms) as p99_latency")
            elif metric == "total_tokens":
                select_fields.append("SUM(ifact.input_tokens + ifact.output_tokens) as total_tokens")
            elif metric == "total_input_tokens":
                select_fields.append("SUM(ifact.input_tokens) as total_input_tokens")
            elif metric == "total_output_tokens":
                select_fields.append("SUM(ifact.output_tokens) as total_output_tokens")
            elif metric == "avg_tokens":
                select_fields.append("AVG(ifact.input_tokens + ifact.output_tokens) as avg_tokens")
            elif metric == "total_cost":
                select_fields.append("SUM(ifact.cost) as total_cost")
            elif metric == "avg_cost":
                select_fields.append("AVG(ifact.cost) as avg_cost")
            elif metric == "ttft_avg":
                select_fields.append("AVG(ifact.ttft_ms) as ttft_avg")
            elif metric == "ttft_p95":
                select_fields.append("quantile(0.95)(ifact.ttft_ms) as ttft_p95")
            elif metric == "ttft_p99":
                select_fields.append("quantile(0.99)(ifact.ttft_ms) as ttft_p99")
            elif metric == "cache_hit_rate":
                select_fields.append("AVG(CASE WHEN ifact.cached THEN 1.0 ELSE 0.0 END) * 100 as cache_hit_rate")
            elif metric == "throughput_avg":
                select_fields.append(
                    "AVG(ifact.output_tokens * 1000.0 / NULLIF(ifact.response_time_ms, 0)) as throughput_avg"
                )
            elif metric == "error_rate":
                select_fields.append("AVG(CASE WHEN NOT ifact.is_success THEN 1.0 ELSE 0.0 END) * 100 as error_rate")
            elif metric == "unique_users":
                select_fields.append("uniqExact(ifact.user_id) as unique_users")

        # Build WHERE clause
        where_conditions = [
            "ifact.request_arrival_time >= %(from_date)s",
            "ifact.request_arrival_time <= %(to_date)s",
        ]

        params = {
            "from_date": request.from_date,
            "to_date": to_date,
        }

        # Add filters
        if request.filters:
            for filter_key, filter_value in request.filters.items():
                if filter_key == "project_id":
                    if isinstance(filter_value, list):
                        placeholders = [f"%(project_{i})s" for i in range(len(filter_value))]
                        where_conditions.append(f"ifact.project_id IN ({','.join(placeholders)})")
                        for i, val in enumerate(filter_value):
                            params[f"project_{i}"] = val
                    else:
                        where_conditions.append("ifact.project_id = %(project_id)s")
                        params["project_id"] = filter_value
                elif filter_key == "api_key_project_id":
                    if isinstance(filter_value, list):
                        placeholders = [f"%(api_key_project_{i})s" for i in range(len(filter_value))]
                        where_conditions.append(f"ifact.api_key_project_id IN ({','.join(placeholders)})")
                        for i, val in enumerate(filter_value):
                            params[f"api_key_project_{i}"] = val
                    else:
                        where_conditions.append("ifact.api_key_project_id = %(api_key_project_id)s")
                        params["api_key_project_id"] = filter_value
                elif filter_key == "model_id":
                    where_conditions.append("ifact.model_id = %(model_id)s")
                    params["model_id"] = filter_value
                elif filter_key == "endpoint_id":
                    where_conditions.append("ifact.endpoint_id = %(endpoint_id)s")
                    params["endpoint_id"] = filter_value

        # Add data_source filter for prompt analytics
        if hasattr(request, "data_source"):
            if request.data_source == "inference":
                where_conditions.append("(ifact.prompt_id IS NULL OR ifact.prompt_id = '')")
            elif request.data_source == "prompt":
                where_conditions.append("ifact.prompt_id IS NOT NULL AND ifact.prompt_id != ''")

        # Build final query (no JOINs - all data in InferenceFact)
        order_by = "total_requests DESC" if "total_requests" in request.metrics else "1"
        query = f"""
        SELECT {", ".join(select_fields)}
        FROM InferenceFact ifact
        WHERE {" AND ".join(where_conditions)}
        {f"GROUP BY {', '.join(group_by_fields)}" if group_by_fields else ""}
        ORDER BY {order_by}
        """

        # Execute query
        results = await self.clickhouse_client.execute_query(query, params)

        return self._process_aggregated_metrics_results(results, request, to_date)

    def _process_aggregated_metrics_results(self, results, request, to_date: datetime) -> dict:
        """Process aggregated metrics query results into response format."""
        from budmetrics.observability.schemas import (
            AggregatedMetricsGroup,
            AggregatedMetricsResponse,
            AggregatedMetricValue,
        )

        # Process results
        groups = []
        overall_summary = {}

        if not results:
            return AggregatedMetricsResponse(
                groups=[],
                summary={},
                total_groups=0,
                date_range={"from": request.from_date, "to": to_date},
            )

        # If no grouping, create summary from single result
        if not request.group_by:
            row = results[0]
            for i, metric in enumerate(request.metrics):
                value = row[i] if i < len(row) else 0
                safe_value = self._safe_float(value)
                formatted_value, unit = self._format_metric_value(metric, safe_value)
                overall_summary[metric] = AggregatedMetricValue(
                    value=safe_value, formatted_value=formatted_value, unit=unit
                )
        else:
            # Process grouped results
            field_offset = len(
                [
                    f
                    for group in request.group_by
                    for f in (
                        ["model_id", "model_name"]
                        if group == "model"
                        else [
                            "api_key_project_id"
                            if group == "user_project"
                            else (f"{group}_id" if group != "user" else "user_id")
                        ]
                    )
                ]
            )

            for row in results:
                group = AggregatedMetricsGroup(metrics={})

                # Extract grouping dimensions
                field_idx = 0
                for group_by in request.group_by:
                    if group_by == "model":
                        group.model_id = row[field_idx]
                        group.model_name = row[field_idx + 1]
                        field_idx += 2
                    elif group_by == "project":
                        group.project_id = row[field_idx]
                        field_idx += 1
                    elif group_by == "endpoint":
                        group.endpoint_id = row[field_idx]
                        field_idx += 1
                    elif group_by == "user":
                        group.user_id = row[field_idx]
                        field_idx += 1
                    elif group_by == "user_project":
                        group.api_key_project_id = row[field_idx]
                        field_idx += 1

                # Extract metrics
                for i, metric in enumerate(request.metrics):
                    value = row[field_offset + i] if field_offset + i < len(row) else 0
                    safe_value = self._safe_float(value)
                    formatted_value, unit = self._format_metric_value(metric, safe_value)
                    group.metrics[metric] = AggregatedMetricValue(
                        value=safe_value, formatted_value=formatted_value, unit=unit
                    )

                groups.append(group)

        return AggregatedMetricsResponse(
            groups=groups,
            summary=overall_summary,
            total_groups=len(groups),
            date_range={"from": request.from_date, "to": to_date},
        )

    async def get_time_series_data(self, request) -> dict:
        """Get time-series data with efficient bucketing.

        Strategy:
        - Uses rollup tables for metrics that don't require raw data (pre-aggregated)
        - Falls back to InferenceFact for percentile metrics (p95_latency, p99_latency)

        Rollup Compatible: requests, success_rate, avg_latency, tokens, cost,
                          ttft_avg, cache_hit_rate, throughput, error_rate
        Requires Raw Data: p95_latency, p99_latency (quantile functions need raw values)
        """
        to_date = request.to_date or datetime.now()

        # Metrics that require raw data for percentile calculations or exact aggregations
        # unique_users needs uniqExact which requires raw data (can't be pre-aggregated in rollups)
        raw_data_metrics = {"p95_latency", "p99_latency", "unique_users"}
        needs_raw_data = any(m in raw_data_metrics for m in request.metrics)

        if needs_raw_data:
            return await self._get_time_series_from_inference_fact(request, to_date)
        else:
            return await self._get_time_series_from_rollup(request, to_date)

    async def _get_time_series_from_rollup(self, request, to_date: datetime) -> dict:
        """Get time-series data from rollup tables (pre-aggregated).

        Uses InferenceMetrics5m/1h/1d based on time range for better performance.
        """
        # Select rollup table based on time range
        table = self.query_builder._select_rollup_table(request.from_date, to_date)

        # Map interval to ClickHouse time bucket expression
        time_bucket_expr = self._get_rollup_time_bucket_expr(request.interval)

        # Build select fields
        select_fields = [f"{time_bucket_expr} as time_bucket"]

        # Add grouping fields
        group_by_fields = ["time_bucket"]
        if request.group_by:
            for group in request.group_by:
                if group == "model":
                    group_by_fields.extend(["model_id", "model_name"])
                    select_fields.extend(["model_id", "model_name"])
                elif group == "project":
                    group_by_fields.append("project_id")
                    select_fields.append("project_id")
                elif group == "endpoint":
                    group_by_fields.append("endpoint_id")
                    select_fields.append("endpoint_id")
                elif group == "user_project":
                    group_by_fields.append("api_key_project_id")
                    select_fields.append("api_key_project_id")

        # Add metric calculations using rollup aggregations
        for metric in request.metrics:
            if metric == "requests":
                select_fields.append("SUM(request_count) as requests")
            elif metric == "success_rate":
                select_fields.append("SUM(success_count) * 100.0 / NULLIF(SUM(request_count), 0) as success_rate")
            elif metric == "avg_latency":
                select_fields.append("SUM(sum_response_time_ms) / NULLIF(SUM(request_count), 0) as avg_latency")
            elif metric == "tokens":
                select_fields.append("SUM(total_input_tokens + total_output_tokens) as tokens")
            elif metric == "cost":
                select_fields.append("SUM(total_cost) as cost")
            elif metric == "ttft_avg":
                select_fields.append("SUM(sum_ttft_ms) / NULLIF(SUM(request_count), 0) as ttft_avg")
            elif metric == "cache_hit_rate":
                select_fields.append("SUM(cached_count) * 100.0 / NULLIF(SUM(request_count), 0) as cache_hit_rate")
            elif metric == "throughput":
                select_fields.append(
                    "SUM(total_output_tokens) * 1000.0 / NULLIF(SUM(sum_response_time_ms), 0) as throughput"
                )
            elif metric == "error_rate":
                select_fields.append("SUM(error_count) * 100.0 / NULLIF(SUM(request_count), 0) as error_rate")
            elif metric == "success_count":
                select_fields.append("SUM(success_count) as success_count")
            elif metric == "error_count":
                select_fields.append("SUM(error_count) as error_count")

        # Build WHERE clause
        where_conditions = ["time_bucket >= %(from_date)s", "time_bucket <= %(to_date)s"]

        params = {
            "from_date": request.from_date,
            "to_date": to_date,
        }

        # Add filters
        if hasattr(request, "filters") and request.filters:
            for filter_key, filter_value in request.filters.items():
                if filter_key == "project_id":
                    if isinstance(filter_value, list):
                        placeholders = [f"%(project_{i})s" for i in range(len(filter_value))]
                        where_conditions.append(f"project_id IN ({','.join(placeholders)})")
                        for i, val in enumerate(filter_value):
                            params[f"project_{i}"] = val
                    else:
                        where_conditions.append("project_id = %(project_id)s")
                        params["project_id"] = filter_value
                elif filter_key == "api_key_project_id":
                    if isinstance(filter_value, list):
                        placeholders = [f"%(api_key_project_{i})s" for i in range(len(filter_value))]
                        where_conditions.append(f"api_key_project_id IN ({','.join(placeholders)})")
                        for i, val in enumerate(filter_value):
                            params[f"api_key_project_{i}"] = val
                    else:
                        where_conditions.append("api_key_project_id = %(api_key_project_id)s")
                        params["api_key_project_id"] = filter_value
                elif filter_key == "model_id":
                    where_conditions.append("model_id = %(model_id)s")
                    params["model_id"] = filter_value
                elif filter_key == "endpoint_id":
                    where_conditions.append("endpoint_id = %(endpoint_id)s")
                    params["endpoint_id"] = filter_value
                elif filter_key == "prompt_id":
                    if isinstance(filter_value, list):
                        placeholders = [f"%(prompt_{i})s" for i in range(len(filter_value))]
                        where_conditions.append(f"prompt_id IN ({','.join(placeholders)})")
                        for i, val in enumerate(filter_value):
                            params[f"prompt_{i}"] = val
                    else:
                        where_conditions.append("prompt_id = %(prompt_id)s")
                        params["prompt_id"] = filter_value

        # Add data_source filter for prompt analytics
        if hasattr(request, "data_source"):
            if request.data_source == "inference":
                where_conditions.append("(prompt_id IS NULL OR prompt_id = '')")
            elif request.data_source == "prompt":
                where_conditions.append("prompt_id IS NOT NULL AND prompt_id != ''")

        # Build WITH FILL expression for time gap filling
        fill_expr = ""
        if request.fill_gaps:
            step = self._get_interval_step(request.interval)
            fill_expr = (
                f"WITH FILL FROM toDateTime('{request.from_date.strftime('%Y-%m-%d %H:%M:%S')}') "
                f"TO toDateTime('{to_date.strftime('%Y-%m-%d %H:%M:%S')}') STEP {step}"
            )

        # Build query using rollup table
        query = f"""
        SELECT {", ".join(select_fields)}
        FROM {table}
        WHERE {" AND ".join(where_conditions)}
        GROUP BY {", ".join(group_by_fields)}
        ORDER BY time_bucket ASC {fill_expr}
        """

        # Execute query
        results = await self.clickhouse_client.execute_query(query, params)

        return self._process_time_series_results(results, request)

    async def _get_time_series_from_inference_fact(self, request, to_date: datetime) -> dict:
        """Get time-series data from InferenceFact (for percentile metrics).

        Uses InferenceFact when raw data is needed for quantile calculations.
        No JOINs required - all data in one denormalized table.
        """
        # Map interval to ClickHouse time bucket expression using ifact alias
        time_bucket_expr = self._get_inference_fact_time_bucket_expr(request.interval)

        # Build select fields
        select_fields = [f"{time_bucket_expr} as time_bucket"]

        # Add grouping fields
        group_by_fields = ["time_bucket"]
        if request.group_by:
            for group in request.group_by:
                if group == "model":
                    group_by_fields.extend(["ifact.model_id", "ifact.model_name"])
                    select_fields.extend(["ifact.model_id", "ifact.model_name"])
                elif group == "project":
                    group_by_fields.append("ifact.project_id")
                    select_fields.append("ifact.project_id")
                elif group == "endpoint":
                    group_by_fields.append("ifact.endpoint_id")
                    select_fields.append("ifact.endpoint_id")
                elif group == "user_project":
                    group_by_fields.append("ifact.api_key_project_id")
                    select_fields.append("ifact.api_key_project_id")

        # Add metric calculations
        for metric in request.metrics:
            if metric == "requests":
                select_fields.append("COUNT(*) as requests")
            elif metric == "success_rate":
                select_fields.append("AVG(CASE WHEN ifact.is_success THEN 1.0 ELSE 0.0 END) * 100 as success_rate")
            elif metric == "avg_latency":
                select_fields.append("AVG(ifact.response_time_ms) as avg_latency")
            elif metric == "p95_latency":
                select_fields.append("quantile(0.95)(ifact.response_time_ms) as p95_latency")
            elif metric == "p99_latency":
                select_fields.append("quantile(0.99)(ifact.response_time_ms) as p99_latency")
            elif metric == "tokens":
                select_fields.append("SUM(ifact.input_tokens + ifact.output_tokens) as tokens")
            elif metric == "cost":
                select_fields.append("SUM(ifact.cost) as cost")
            elif metric == "ttft_avg":
                select_fields.append("AVG(ifact.ttft_ms) as ttft_avg")
            elif metric == "cache_hit_rate":
                select_fields.append("AVG(CASE WHEN ifact.cached THEN 1.0 ELSE 0.0 END) * 100 as cache_hit_rate")
            elif metric == "throughput":
                select_fields.append(
                    "AVG(ifact.output_tokens * 1000.0 / NULLIF(ifact.response_time_ms, 0)) as throughput"
                )
            elif metric == "error_rate":
                select_fields.append("AVG(CASE WHEN NOT ifact.is_success THEN 1.0 ELSE 0.0 END) * 100 as error_rate")
            elif metric == "unique_users":
                select_fields.append("uniqExact(ifact.user_id) as unique_users")
            elif metric == "success_count":
                select_fields.append("countIf(ifact.is_success = true) as success_count")
            elif metric == "error_count":
                select_fields.append("countIf(ifact.is_success = false OR ifact.is_success IS NULL) as error_count")

        # Build WHERE clause
        where_conditions = [
            "ifact.request_arrival_time >= %(from_date)s",
            "ifact.request_arrival_time <= %(to_date)s",
        ]

        params = {
            "from_date": request.from_date,
            "to_date": to_date,
        }

        # Add filters
        if hasattr(request, "filters") and request.filters:
            for filter_key, filter_value in request.filters.items():
                if filter_key == "project_id":
                    if isinstance(filter_value, list):
                        placeholders = [f"%(project_{i})s" for i in range(len(filter_value))]
                        where_conditions.append(f"ifact.project_id IN ({','.join(placeholders)})")
                        for i, val in enumerate(filter_value):
                            params[f"project_{i}"] = val
                    else:
                        where_conditions.append("ifact.project_id = %(project_id)s")
                        params["project_id"] = filter_value
                elif filter_key == "api_key_project_id":
                    if isinstance(filter_value, list):
                        placeholders = [f"%(api_key_project_{i})s" for i in range(len(filter_value))]
                        where_conditions.append(f"ifact.api_key_project_id IN ({','.join(placeholders)})")
                        for i, val in enumerate(filter_value):
                            params[f"api_key_project_{i}"] = val
                    else:
                        where_conditions.append("ifact.api_key_project_id = %(api_key_project_id)s")
                        params["api_key_project_id"] = filter_value
                elif filter_key == "model_id":
                    where_conditions.append("ifact.model_id = %(model_id)s")
                    params["model_id"] = filter_value
                elif filter_key == "endpoint_id":
                    where_conditions.append("ifact.endpoint_id = %(endpoint_id)s")
                    params["endpoint_id"] = filter_value
                elif filter_key == "prompt_id":
                    if isinstance(filter_value, list):
                        placeholders = [f"%(prompt_{i})s" for i in range(len(filter_value))]
                        where_conditions.append(f"ifact.prompt_id IN ({','.join(placeholders)})")
                        for i, val in enumerate(filter_value):
                            params[f"prompt_{i}"] = val
                    else:
                        where_conditions.append("ifact.prompt_id = %(prompt_id)s")
                        params["prompt_id"] = filter_value

        # Add data_source filter for prompt analytics
        if hasattr(request, "data_source"):
            if request.data_source == "inference":
                where_conditions.append("(ifact.prompt_id IS NULL OR ifact.prompt_id = '')")
            elif request.data_source == "prompt":
                where_conditions.append("ifact.prompt_id IS NOT NULL AND ifact.prompt_id != ''")

        # Build WITH FILL expression for time gap filling
        fill_expr = ""
        if request.fill_gaps:
            step = self._get_interval_step(request.interval)
            fill_expr = (
                f"WITH FILL FROM toDateTime('{request.from_date.strftime('%Y-%m-%d %H:%M:%S')}') "
                f"TO toDateTime('{to_date.strftime('%Y-%m-%d %H:%M:%S')}') STEP {step}"
            )

        # Build query (no JOINs - all data in InferenceFact)
        query = f"""
        SELECT {", ".join(select_fields)}
        FROM InferenceFact ifact
        WHERE {" AND ".join(where_conditions)}
        GROUP BY {", ".join(group_by_fields)}
        ORDER BY time_bucket ASC {fill_expr}
        """

        # Execute query
        results = await self.clickhouse_client.execute_query(query, params)

        return self._process_time_series_results(results, request)

    # Time bucket expression mappings for rollup tables
    _ROLLUP_TIME_BUCKET_EXPRS = {
        "1m": "toStartOfMinute(time_bucket)",
        "5m": "toStartOfInterval(time_bucket, INTERVAL 5 minute)",
        "15m": "toStartOfInterval(time_bucket, INTERVAL 15 minute)",
        "30m": "toStartOfInterval(time_bucket, INTERVAL 30 minute)",
        "1h": "toStartOfHour(time_bucket)",
        "6h": "toStartOfInterval(time_bucket, INTERVAL 6 hour)",
        "12h": "toStartOfInterval(time_bucket, INTERVAL 12 hour)",
        "1d": "toStartOfDay(time_bucket)",
        # Wrap with toDateTime to ensure DateTime type for comparison
        "1w": "toDateTime(toStartOfWeek(time_bucket))",
    }

    # Time bucket expression mappings for InferenceFact table
    _INFERENCE_FACT_TIME_BUCKET_EXPRS = {
        "1m": "toStartOfMinute(ifact.request_arrival_time)",
        "5m": "toStartOfInterval(ifact.request_arrival_time, INTERVAL 5 minute)",
        "15m": "toStartOfInterval(ifact.request_arrival_time, INTERVAL 15 minute)",
        "30m": "toStartOfInterval(ifact.request_arrival_time, INTERVAL 30 minute)",
        "1h": "toStartOfHour(ifact.request_arrival_time)",
        "6h": "toStartOfInterval(ifact.request_arrival_time, INTERVAL 6 hour)",
        "12h": "toStartOfInterval(ifact.request_arrival_time, INTERVAL 12 hour)",
        "1d": "toStartOfDay(ifact.request_arrival_time)",
        # Wrap with toDateTime to ensure DateTime type for comparison
        "1w": "toDateTime(toStartOfWeek(ifact.request_arrival_time))",
    }

    def _get_rollup_time_bucket_expr(self, interval: str) -> str:
        """Get time bucket expression for rollup tables."""
        return self._ROLLUP_TIME_BUCKET_EXPRS.get(interval, "toStartOfHour(time_bucket)")

    def _get_inference_fact_time_bucket_expr(self, interval: str) -> str:
        """Get time bucket expression for InferenceFact table."""
        return self._INFERENCE_FACT_TIME_BUCKET_EXPRS.get(interval, "toStartOfHour(ifact.request_arrival_time)")

    def _get_interval_step(self, interval: str) -> str:
        """Convert interval string to ClickHouse INTERVAL syntax for WITH FILL."""
        interval_map = {
            "1m": "INTERVAL 1 MINUTE",
            "5m": "INTERVAL 5 MINUTE",
            "15m": "INTERVAL 15 MINUTE",
            "30m": "INTERVAL 30 MINUTE",
            "1h": "INTERVAL 1 HOUR",
            "6h": "INTERVAL 6 HOUR",
            "12h": "INTERVAL 12 HOUR",
            "1d": "INTERVAL 1 DAY",
            "1w": "INTERVAL 1 WEEK",
        }
        return interval_map.get(interval, "INTERVAL 1 HOUR")

    def _process_time_series_results(self, results, request) -> dict:
        """Process time series query results into response format."""
        from budmetrics.observability.schemas import (
            TimeSeriesGroup,
            TimeSeriesPoint,
            TimeSeriesResponse,
        )

        # Process results into groups
        groups_dict = defaultdict(list)

        for row in results:
            time_bucket = row[0]

            # Extract grouping info
            group_key = "default"
            group_info = {}
            field_idx = 1
            is_gap_filled_row = False

            if request.group_by:
                group_key_parts = []
                for group in request.group_by:
                    if group == "model":
                        model_id = row[field_idx]
                        model_name = row[field_idx + 1]
                        # Skip gap-filled rows with zero UUID or NULL (created by WITH FILL)
                        if model_id == self._ZERO_UUID or model_id is None:
                            is_gap_filled_row = True
                            break
                        group_info["model_id"] = model_id
                        group_info["model_name"] = model_name
                        group_key_parts.append(f"model:{model_id}|{model_name}")
                        field_idx += 2
                    elif group == "project":
                        project_id = row[field_idx]
                        if project_id == self._ZERO_UUID or project_id is None:
                            is_gap_filled_row = True
                            break
                        group_info["project_id"] = project_id
                        group_key_parts.append(f"project:{project_id}")
                        field_idx += 1
                    elif group == "endpoint":
                        endpoint_id = row[field_idx]
                        if endpoint_id == self._ZERO_UUID or endpoint_id is None:
                            is_gap_filled_row = True
                            break
                        group_info["endpoint_id"] = endpoint_id
                        group_key_parts.append(f"endpoint:{endpoint_id}")
                        field_idx += 1
                    elif group == "user_project":
                        api_key_project_id = row[field_idx]
                        if api_key_project_id == self._ZERO_UUID or api_key_project_id is None:
                            is_gap_filled_row = True
                            break
                        group_info["api_key_project_id"] = api_key_project_id
                        group_key_parts.append(f"api_key_project:{api_key_project_id}")
                        field_idx += 1

                # Skip gap-filled phantom rows
                if is_gap_filled_row:
                    continue

                group_key = "|".join(group_key_parts)

            # Extract metric values
            values = {}
            for i, metric in enumerate(request.metrics):
                metric_value = row[field_idx + i] if field_idx + i < len(row) else None
                # Ensure safe float values for JSON serialization
                values[metric] = self._safe_float(metric_value)

            groups_dict[group_key].append({"timestamp": time_bucket, "values": values, "group_info": group_info})

        # Convert to response format
        groups = []
        for _group_key, data_points in groups_dict.items():
            group = TimeSeriesGroup(
                data_points=[TimeSeriesPoint(timestamp=dp["timestamp"], values=dp["values"]) for dp in data_points]
            )

            # Set group info
            if data_points and data_points[0]["group_info"]:
                group_info = data_points[0]["group_info"]
                group.model_id = group_info.get("model_id")
                group.model_name = group_info.get("model_name")
                group.project_id = group_info.get("project_id")
                group.endpoint_id = group_info.get("endpoint_id")
                group.api_key_project_id = group_info.get("api_key_project_id")

            groups.append(group)

        # Gap filling is now handled by ClickHouse WITH FILL clause in the query

        return TimeSeriesResponse(
            groups=groups,
            interval=request.interval,
            date_range={"from": request.from_date, "to": request.to_date or datetime.now()},
        )

    async def get_geographic_data(self, request) -> dict:
        """Get geographic distribution data using rollup tables or InferenceFact.

        Strategy:
        - Country-level queries use rollup tables (InferenceMetrics5m/1h/1d) for performance
        - Region/City queries use InferenceFact (rollup doesn't have these columns)

        All geographic data is now available in InferenceFact, eliminating JOIN issues.
        """
        to_date = request.to_date or datetime.now()

        # Country-level can use rollup tables for better performance
        if request.group_by == "country":
            return await self._get_geographic_data_from_rollup(request, to_date)
        else:
            # Region/City require InferenceFact (not in rollup tables)
            return await self._get_geographic_data_from_inference_fact(request, to_date)

    async def _get_geographic_data_from_rollup(self, request, to_date: datetime) -> dict:
        """Get country-level geographic data from rollup tables.

        Uses pre-aggregated data for better performance on large time ranges.
        Rollup tables have country_code as a dimension column.
        """
        from budmetrics.observability.schemas import (
            GeographicDataPoint,
            GeographicDataResponse,
        )

        # Select appropriate rollup table based on time range
        table = self.query_builder._select_rollup_table(request.from_date, to_date)

        params = {
            "from_date": request.from_date,
            "to_date": to_date,
            "limit": request.limit,
        }

        # Build WHERE conditions
        where_conditions = [
            "time_bucket >= %(from_date)s",
            "time_bucket <= %(to_date)s",
            "country_code IS NOT NULL",
            "country_code != ''",
        ]

        # Add filters
        if request.filters:
            for filter_key, filter_value in request.filters.items():
                if filter_key == "project_id":
                    if isinstance(filter_value, list):
                        placeholders = [f"%(project_{i})s" for i in range(len(filter_value))]
                        where_conditions.append(f"project_id IN ({','.join(placeholders)})")
                        for i, val in enumerate(filter_value):
                            params[f"project_{i}"] = val
                    else:
                        where_conditions.append("project_id = %(project_id)s")
                        params["project_id"] = filter_value
                elif filter_key == "api_key_project_id":
                    if isinstance(filter_value, list):
                        placeholders = [f"%(api_key_project_{i})s" for i in range(len(filter_value))]
                        where_conditions.append(f"api_key_project_id IN ({','.join(placeholders)})")
                        for i, val in enumerate(filter_value):
                            params[f"api_key_project_{i}"] = val
                    else:
                        where_conditions.append("api_key_project_id = %(api_key_project_id)s")
                        params["api_key_project_id"] = filter_value
                elif filter_key == "country_code":
                    if isinstance(filter_value, list):
                        placeholders = [f"%(country_{i})s" for i in range(len(filter_value))]
                        where_conditions.append(f"country_code IN ({','.join(placeholders)})")
                        for i, val in enumerate(filter_value):
                            params[f"country_{i}"] = val
                    else:
                        where_conditions.append("country_code = %(country_code)s")
                        params["country_code"] = filter_value

        # Add data_source filter for prompt analytics
        if hasattr(request, "data_source"):
            if request.data_source == "inference":
                where_conditions.append("(prompt_id IS NULL OR prompt_id = '')")
            elif request.data_source == "prompt":
                where_conditions.append("prompt_id IS NOT NULL AND prompt_id != ''")

        where_clause = " AND ".join(where_conditions)

        # Query with pre-aggregated metrics
        # Note: Use different alias names to avoid ClickHouse confusing column vs alias
        query = f"""
        WITH
            total_cte AS (
                SELECT SUM(request_count) as total
                FROM {table}
                WHERE {where_clause}
            )
        SELECT
            country_code,
            SUM(request_count) as total_requests,
            SUM(success_count) * 100.0 / NULLIF(SUM(request_count), 0) as success_rate,
            SUM(sum_response_time_ms) / NULLIF(SUM(request_count), 0) as avg_latency_ms,
            uniqMerge(unique_users) as unique_users,
            (SUM(request_count) * 100.0 / NULLIF((SELECT total FROM total_cte), 0)) as percentage
        FROM {table}
        WHERE {where_clause}
        GROUP BY country_code
        ORDER BY 2 DESC
        LIMIT %(limit)s
        """

        results = await self.clickhouse_client.execute_query(query, params)

        # Get total requests
        total_query = f"""
        SELECT SUM(request_count) as total_requests
        FROM {table}
        WHERE {where_clause}
        """
        total_result = await self.clickhouse_client.execute_query(
            total_query, {k: v for k, v in params.items() if k != "limit"}
        )
        total_requests = int(total_result[0][0] or 0) if total_result else 0

        # Process results
        locations = []
        for row in results:
            location = GeographicDataPoint(
                country_code=row[0],
                request_count=int(row[1] or 0),
                success_rate=float(row[2]) if row[2] is not None else 0.0,
                avg_latency_ms=float(row[3]) if row[3] is not None else None,
                unique_users=int(row[4] or 0) if row[4] is not None else None,
                latitude=None,  # Not available in rollup tables
                longitude=None,  # Not available in rollup tables
                percentage=float(row[5]) if row[5] is not None else 0.0,
            )
            locations.append(location)

        return GeographicDataResponse(
            locations=locations,
            total_requests=total_requests,
            total_locations=len(locations),
            date_range={"from": request.from_date, "to": to_date},
            group_by=request.group_by,
        )

    async def _get_geographic_data_from_inference_fact(self, request, to_date: datetime) -> dict:
        """Get region/city-level geographic data from InferenceFact.

        Uses InferenceFact for queries that need region, city, latitude, longitude.
        No JOINs required - all data is in one denormalized table.
        """
        from budmetrics.observability.schemas import (
            GeographicDataPoint,
            GeographicDataResponse,
        )

        params = {
            "from_date": request.from_date,
            "to_date": to_date,
            "limit": request.limit,
        }

        # Build WHERE conditions using ifact alias (avoid conflict with ClickHouse inf constant)
        where_conditions = [
            "ifact.timestamp >= %(from_date)s",
            "ifact.timestamp <= %(to_date)s",
        ]

        # Build select fields and group by based on group_by parameter
        if request.group_by == "region":
            select_fields = [
                "ifact.country_code",
                "ifact.region",
                "COUNT(*) as request_count",
                "AVG(CASE WHEN ifact.is_success THEN 1.0 ELSE 0.0 END) * 100 as success_rate",
                "AVG(ifact.response_time_ms) as avg_latency_ms",
                "uniqExact(ifact.user_id) as unique_users",
            ]
            group_by_clause = "ifact.country_code, ifact.region"
            having_clause = "ifact.region IS NOT NULL AND ifact.region != ''"
            request_count_pos = 3  # Position of COUNT(*) in SELECT (1-indexed)
        else:  # city
            select_fields = [
                "ifact.country_code",
                "ifact.region",
                "ifact.city",
                "COUNT(*) as request_count",
                "AVG(CASE WHEN ifact.is_success THEN 1.0 ELSE 0.0 END) * 100 as success_rate",
                "AVG(ifact.response_time_ms) as avg_latency_ms",
                "uniqExact(ifact.user_id) as unique_users",
                "any(ifact.latitude) as latitude",
                "any(ifact.longitude) as longitude",
            ]
            group_by_clause = "ifact.country_code, ifact.region, ifact.city"
            having_clause = "ifact.city IS NOT NULL AND ifact.city != ''"
            request_count_pos = 4  # Position of COUNT(*) in SELECT (1-indexed)

        # Add filters
        if request.filters:
            for filter_key, filter_value in request.filters.items():
                if filter_key == "project_id":
                    if isinstance(filter_value, list):
                        placeholders = [f"%(project_{i})s" for i in range(len(filter_value))]
                        where_conditions.append(f"ifact.project_id IN ({','.join(placeholders)})")
                        for i, val in enumerate(filter_value):
                            params[f"project_{i}"] = val
                    else:
                        where_conditions.append("ifact.project_id = %(project_id)s")
                        params["project_id"] = filter_value
                elif filter_key == "api_key_project_id":
                    if isinstance(filter_value, list):
                        placeholders = [f"%(api_key_project_{i})s" for i in range(len(filter_value))]
                        where_conditions.append(f"ifact.api_key_project_id IN ({','.join(placeholders)})")
                        for i, val in enumerate(filter_value):
                            params[f"api_key_project_{i}"] = val
                    else:
                        where_conditions.append("ifact.api_key_project_id = %(api_key_project_id)s")
                        params["api_key_project_id"] = filter_value
                elif filter_key == "country_code":
                    if isinstance(filter_value, list):
                        placeholders = [f"%(country_{i})s" for i in range(len(filter_value))]
                        where_conditions.append(f"ifact.country_code IN ({','.join(placeholders)})")
                        for i, val in enumerate(filter_value):
                            params[f"country_{i}"] = val
                    else:
                        where_conditions.append("ifact.country_code = %(country_code)s")
                        params["country_code"] = filter_value

        # Add data_source filter for prompt analytics
        if hasattr(request, "data_source"):
            if request.data_source == "inference":
                where_conditions.append("(ifact.prompt_id IS NULL OR ifact.prompt_id = '')")
            elif request.data_source == "prompt":
                where_conditions.append("ifact.prompt_id IS NOT NULL AND ifact.prompt_id != ''")

        where_clause = " AND ".join(where_conditions)

        # Build query (no JOINs - InferenceFact has all data)
        query = f"""
        WITH
            total_cte AS (
                SELECT COUNT(*) as total
                FROM InferenceFact ifact
                WHERE {where_clause}
            )
        SELECT
            {", ".join(select_fields)},
            (COUNT(*) * 100.0 / NULLIF((SELECT total FROM total_cte), 0)) as percentage
        FROM InferenceFact ifact
        WHERE {where_clause}
        GROUP BY {group_by_clause}
        HAVING {having_clause}
        ORDER BY {request_count_pos} DESC
        LIMIT %(limit)s
        """

        results = await self.clickhouse_client.execute_query(query, params)

        # Get total count
        total_query = f"""
        SELECT COUNT(*) as total_requests
        FROM InferenceFact ifact
        WHERE {where_clause}
        """
        total_result = await self.clickhouse_client.execute_query(
            total_query, {k: v for k, v in params.items() if k != "limit"}
        )
        total_requests = int(total_result[0][0] or 0) if total_result else 0

        # Process results
        locations = []
        for row in results:
            if request.group_by == "region":
                location = GeographicDataPoint(
                    country_code=row[0],
                    region=row[1],
                    request_count=int(row[2] or 0),
                    success_rate=float(row[3]) if row[3] is not None else 0.0,
                    avg_latency_ms=float(row[4]) if row[4] is not None else None,
                    unique_users=int(row[5] or 0) if row[5] is not None else None,
                    percentage=float(row[6]) if row[6] is not None else 0.0,
                )
            else:  # city
                location = GeographicDataPoint(
                    country_code=row[0],
                    region=row[1],
                    city=row[2],
                    request_count=int(row[3] or 0),
                    success_rate=float(row[4]) if row[4] is not None else 0.0,
                    avg_latency_ms=float(row[5]) if row[5] is not None else None,
                    unique_users=int(row[6] or 0) if row[6] is not None else None,
                    latitude=float(row[7]) if row[7] is not None else None,
                    longitude=float(row[8]) if row[8] is not None else None,
                    percentage=float(row[9]) if row[9] is not None else 0.0,
                )

            locations.append(location)

        return GeographicDataResponse(
            locations=locations,
            total_requests=total_requests,
            total_locations=len(locations),
            date_range={"from": request.from_date, "to": to_date},
            group_by=request.group_by,
        )

    async def get_latency_distribution(self, request: LatencyDistributionRequest) -> LatencyDistributionResponse:
        """Get latency distribution data with optional grouping.

        This method calculates latency distribution by creating histogram buckets
        and counting requests that fall into each bucket. It supports custom buckets
        and grouping by various dimensions.

        Uses InferenceFact table (denormalized) - no JOINs required.

        Args:
            request: The latency distribution request parameters.

        Returns:
            LatencyDistributionResponse: Response containing distribution data.
        """
        from budmetrics.observability.schemas import (
            LatencyDistributionBucket,
            LatencyDistributionGroup,
            LatencyDistributionResponse,
        )

        logger.info(f"Getting latency distribution for date range {request.from_date} to {request.to_date}")

        # Default latency buckets if none provided
        default_buckets = [
            {"min": 0, "max": 100, "label": "0-100ms"},
            {"min": 100, "max": 500, "label": "100-500ms"},
            {"min": 500, "max": 1000, "label": "500ms-1s"},
            {"min": 1000, "max": 2000, "label": "1-2s"},
            {"min": 2000, "max": 5000, "label": "2-5s"},
            {"min": 5000, "max": 10000, "label": "5-10s"},
            {"min": 10000, "max": float("inf"), "label": ">10s"},
        ]

        buckets = request.buckets or default_buckets

        # Base query components
        from_date_str = request.from_date.strftime("%Y-%m-%d %H:%M:%S")
        to_date_str = (request.to_date or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")

        # Build filters using ifact alias (avoid conflict with ClickHouse inf constant)
        filter_conditions = [
            f"toDateTime('{from_date_str}') <= ifact.request_arrival_time",
            f"ifact.request_arrival_time < toDateTime('{to_date_str}')",
        ]

        if request.filters:
            if "project_id" in request.filters:
                project_ids = request.filters["project_id"]
                if isinstance(project_ids, str):
                    project_ids = [project_ids]
                project_filter = "', '".join(str(pid) for pid in project_ids)
                filter_conditions.append(f"toString(ifact.project_id) IN ('{project_filter}')")

            if "api_key_project_id" in request.filters:
                # Support filtering by api_key_project_id for CLIENT users
                api_key_project_ids = request.filters["api_key_project_id"]
                if isinstance(api_key_project_ids, str):
                    api_key_project_ids = [api_key_project_ids]
                api_key_project_filter = "', '".join(str(pid) for pid in api_key_project_ids)
                filter_conditions.append(f"toString(ifact.api_key_project_id) IN ('{api_key_project_filter}')")

            if "endpoint_id" in request.filters:
                endpoint_ids = request.filters["endpoint_id"]
                if isinstance(endpoint_ids, str):
                    endpoint_ids = [endpoint_ids]
                endpoint_filter = "', '".join(str(eid) for eid in endpoint_ids)
                filter_conditions.append(f"toString(ifact.endpoint_id) IN ('{endpoint_filter}')")

            if "model_id" in request.filters:
                model_ids = request.filters["model_id"]
                if isinstance(model_ids, str):
                    model_ids = [model_ids]
                model_filter = "', '".join(str(mid) for mid in model_ids)
                filter_conditions.append(f"toString(ifact.model_id) IN ('{model_filter}')")

        # Add data_source filter for prompt analytics
        if hasattr(request, "data_source"):
            if request.data_source == "inference":
                filter_conditions.append("(ifact.prompt_id IS NULL OR ifact.prompt_id = '')")
            elif request.data_source == "prompt":
                filter_conditions.append("ifact.prompt_id IS NOT NULL AND ifact.prompt_id != ''")

        where_clause = " AND ".join(filter_conditions)

        # Latency from InferenceFact's response_time_ms column (no JOIN needed)
        latency_expr = "COALESCE(ifact.response_time_ms, 0)"

        # Build bucket case expressions for distribution
        bucket_cases = []
        for bucket in buckets:
            if bucket["max"] == float("inf"):
                condition = f"{latency_expr} >= {bucket['min']}"
            else:
                condition = f"{latency_expr} >= {bucket['min']} AND {latency_expr} < {bucket['max']}"
            bucket_cases.append(f"WHEN {condition} THEN '{bucket['label']}'")

        # If no grouping, create simple overall distribution
        if not request.group_by:
            bucket_case_expr = f"CASE {' '.join(bucket_cases)} ELSE 'Other' END"

            # Build dynamic ORDER BY based on actual number of buckets
            order_cases = [f"WHEN '{bucket['label']}' THEN {i + 1}" for i, bucket in enumerate(buckets)]
            order_case_expr = f"CASE bucket {' '.join(order_cases)} ELSE {len(buckets) + 1} END"

            query = f"""
                SELECT
                    {bucket_case_expr} as bucket,
                    count() as request_count,
                    avg({latency_expr}) as avg_latency_in_bucket
                FROM InferenceFact ifact
                WHERE {where_clause}
                GROUP BY bucket
                ORDER BY {order_case_expr}
            """

            result = await self.clickhouse_client.execute_query(query)

            # Get total count for percentage calculation (no JOIN needed)
            total_query = f"SELECT count() FROM InferenceFact ifact WHERE {where_clause}"
            total_result = await self.clickhouse_client.execute_query(total_query)
            total_requests = total_result[0][0] if total_result else 0

            # Process results
            overall_buckets = []
            bucket_data = {row[0]: (row[1], row[2]) for row in result}

            for bucket in buckets:
                count, avg_latency = bucket_data.get(bucket["label"], (0, 0))
                percentage = (count / total_requests * 100) if total_requests > 0 else 0
                safe_percentage = self._safe_float(percentage)
                safe_avg_latency = self._safe_float(avg_latency) if avg_latency else None

                overall_buckets.append(
                    LatencyDistributionBucket(
                        range=bucket["label"],
                        count=count,
                        percentage=round(safe_percentage, 2),
                        avg_latency=round(safe_avg_latency, 2) if safe_avg_latency else None,
                    )
                )

            # Clean up bucket definitions for response (replace inf with large number for JSON serialization)
            clean_buckets = [
                {
                    "min": bucket["min"],
                    "max": 999999999 if bucket["max"] == float("inf") else bucket["max"],
                    "label": bucket["label"],
                }
                for bucket in buckets
            ]

            return LatencyDistributionResponse(
                groups=[],
                overall_distribution=overall_buckets,
                total_requests=total_requests,
                date_range={"from": request.from_date, "to": request.to_date or datetime.now()},
                bucket_definitions=clean_buckets,
            )

        # Handle grouped queries
        groups = []
        total_requests = 0

        # Determine grouping columns (all from InferenceFact - no JOINs needed)
        group_columns = []

        if "model" in request.group_by:
            group_columns.extend(["toString(ifact.model_id) as model_id", "ifact.model_name as model_name"])

        if "project" in request.group_by:
            group_columns.extend(["toString(ifact.project_id) as project_id", "'Unknown' as project_name"])

        if "endpoint" in request.group_by:
            group_columns.extend(["toString(ifact.endpoint_id) as endpoint_id", "'Unknown' as endpoint_name"])

        if "user" in request.group_by:
            group_columns.extend(["toString(ifact.user_id) as user_id"])

        if "user_project" in request.group_by:
            group_columns.extend(["toString(ifact.api_key_project_id) as api_key_project_id"])

        group_by_clause = ", ".join([col.split(" as ")[1] if " as " in col else col for col in group_columns])
        select_columns = ", ".join(group_columns)

        # Build grouped query with bucket distribution (no JOINs needed)
        bucket_case_expr = f"CASE {' '.join(bucket_cases)} ELSE 'Other' END"

        query = f"""
            WITH grouped_data AS (
                SELECT
                    {select_columns},
                    {bucket_case_expr} as bucket,
                    count() as request_count,
                    avg({latency_expr}) as avg_latency_in_bucket
                FROM InferenceFact ifact
                WHERE {where_clause}
                GROUP BY {group_by_clause}, bucket
            )
            SELECT
                *,
                sum(request_count) OVER (PARTITION BY {group_by_clause}) as group_total
            FROM grouped_data
            ORDER BY group_total DESC, bucket
        """

        result = await self.clickhouse_client.execute_query(query)

        # Get overall total for percentage calculations (no JOIN needed)
        total_query = f"SELECT count() FROM InferenceFact ifact WHERE {where_clause}"
        total_result = await self.clickhouse_client.execute_query(total_query)
        total_requests = total_result[0][0] if total_result else 0

        # Process grouped results
        groups_data = {}

        for row in result:
            # Extract group identifiers based on what was selected
            group_key = []
            group_values = {}
            col_idx = 0

            if "model" in request.group_by:
                group_values["model_id"] = row[col_idx]
                group_values["model_name"] = row[col_idx + 1] or "Unknown"
                group_key.append(f"model:{group_values['model_id']}")
                col_idx += 2

            if "project" in request.group_by:
                group_values["project_id"] = row[col_idx]
                group_values["project_name"] = row[col_idx + 1] or "Unknown"
                group_key.append(f"project:{group_values['project_id']}")
                col_idx += 2

            if "endpoint" in request.group_by:
                group_values["endpoint_id"] = row[col_idx]
                group_values["endpoint_name"] = row[col_idx + 1] or "Unknown"
                group_key.append(f"endpoint:{group_values['endpoint_id']}")
                col_idx += 2

            if "user" in request.group_by:
                group_values["user_id"] = row[col_idx]
                group_key.append(f"user:{group_values['user_id']}")
                col_idx += 1

            if "user_project" in request.group_by:
                group_values["api_key_project_id"] = row[col_idx]
                group_key.append(f"user_project:{group_values['api_key_project_id']}")
                col_idx += 1

            group_key_str = "|".join(group_key)
            bucket = row[col_idx]
            request_count = row[col_idx + 1]
            avg_latency = row[col_idx + 2]
            group_total = row[col_idx + 3]

            if group_key_str not in groups_data:
                groups_data[group_key_str] = {"group_values": group_values, "buckets": {}, "total": group_total}

            groups_data[group_key_str]["buckets"][bucket] = {"count": request_count, "avg_latency": avg_latency}

        # Convert to response format
        for _group_key, group_data in groups_data.items():
            group_buckets = []
            group_total = group_data["total"]

            for bucket in buckets:
                bucket_info = group_data["buckets"].get(bucket["label"], {"count": 0, "avg_latency": 0})
                count = bucket_info["count"]
                avg_latency = bucket_info["avg_latency"]
                percentage = (count / group_total * 100) if group_total > 0 else 0
                safe_percentage = self._safe_float(percentage)
                safe_avg_latency = self._safe_float(avg_latency) if avg_latency else None

                group_buckets.append(
                    LatencyDistributionBucket(
                        range=bucket["label"],
                        count=count,
                        percentage=round(safe_percentage, 2),
                        avg_latency=round(safe_avg_latency, 2) if safe_avg_latency else None,
                    )
                )

            group_obj = LatencyDistributionGroup(buckets=group_buckets, total_requests=group_total)

            # Set group identifiers
            group_vals = group_data["group_values"]
            if "model_id" in group_vals:
                try:
                    group_obj.model_id = UUID(group_vals["model_id"]) if group_vals["model_id"] else None
                except (ValueError, TypeError):
                    group_obj.model_id = None
                group_obj.model_name = group_vals["model_name"]
            if "project_id" in group_vals:
                try:
                    group_obj.project_id = UUID(group_vals["project_id"]) if group_vals["project_id"] else None
                except (ValueError, TypeError):
                    group_obj.project_id = None
                group_obj.project_name = group_vals["project_name"]
            if "endpoint_id" in group_vals:
                try:
                    group_obj.endpoint_id = UUID(group_vals["endpoint_id"]) if group_vals["endpoint_id"] else None
                except (ValueError, TypeError):
                    group_obj.endpoint_id = None
                group_obj.endpoint_name = group_vals["endpoint_name"]
            if "user_id" in group_vals:
                group_obj.user_id = group_vals["user_id"]
            if "api_key_project_id" in group_vals:
                try:
                    group_obj.api_key_project_id = (
                        UUID(group_vals["api_key_project_id"]) if group_vals["api_key_project_id"] else None
                    )
                except (ValueError, TypeError):
                    group_obj.api_key_project_id = None

            groups.append(group_obj)

        # Calculate overall distribution across all groups
        overall_bucket_counts = {}
        for group in groups:
            for bucket in group.buckets:
                if bucket.range not in overall_bucket_counts:
                    overall_bucket_counts[bucket.range] = {"count": 0, "latencies": []}
                overall_bucket_counts[bucket.range]["count"] += bucket.count
                if bucket.avg_latency:
                    overall_bucket_counts[bucket.range]["latencies"].append(bucket.avg_latency)

        overall_buckets = []
        for bucket in buckets:
            bucket_data = overall_bucket_counts.get(bucket["label"], {"count": 0, "latencies": []})
            count = bucket_data["count"]
            percentage = (count / total_requests * 100) if total_requests > 0 else 0
            safe_percentage = self._safe_float(percentage)
            avg_latency = (
                (sum(bucket_data["latencies"]) / len(bucket_data["latencies"])) if bucket_data["latencies"] else None
            )
            safe_avg_latency = self._safe_float(avg_latency) if avg_latency else None

            overall_buckets.append(
                LatencyDistributionBucket(
                    range=bucket["label"],
                    count=count,
                    percentage=round(safe_percentage, 2),
                    avg_latency=round(safe_avg_latency, 2) if safe_avg_latency else None,
                )
            )

        # Clean up bucket definitions for response (replace inf with large number for JSON serialization)
        clean_buckets = []
        for bucket in buckets:
            clean_bucket = {
                "min": bucket["min"],
                "max": 999999999 if bucket["max"] == float("inf") else bucket["max"],
                "label": bucket["label"],
            }
            clean_buckets.append(clean_bucket)

        return LatencyDistributionResponse(
            groups=groups,
            overall_distribution=overall_buckets,
            total_requests=total_requests,
            date_range={"from": request.from_date, "to": request.to_date or datetime.now()},
            bucket_definitions=clean_buckets,
        )

    async def get_prompt_distribution(self, request: PromptDistributionRequest) -> PromptDistributionResponse:
        """Get prompt analytics distribution data.

        Supports bucketing by concurrency, input_tokens, or output_tokens (X-axis)
        and metrics like total_duration_ms, ttft_ms, response_time_ms, throughput_per_user (Y-axis).

        Args:
            request: The prompt distribution request parameters.

        Returns:
            PromptDistributionResponse: Response containing distribution data.
        """
        logger.info(f"Getting prompt distribution for date range {request.from_date} to {request.to_date}")

        # Build time filter
        from_date_str = request.from_date.strftime("%Y-%m-%d %H:%M:%S")
        to_date_str = (request.to_date or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")

        # Build filter conditions - only prompt analytics data (prompt_id is set)
        filter_conditions = [
            f"toDateTime('{from_date_str}') <= ifact.request_arrival_time",
            f"ifact.request_arrival_time < toDateTime('{to_date_str}')",
            "ifact.prompt_id IS NOT NULL AND ifact.prompt_id != ''",
        ]

        # Apply additional filters
        if request.filters:
            if "project_id" in request.filters:
                project_ids = request.filters["project_id"]
                if isinstance(project_ids, str):
                    project_ids = [project_ids]
                project_filter = "', '".join(str(pid) for pid in project_ids)
                filter_conditions.append(f"toString(ifact.project_id) IN ('{project_filter}')")

            if "endpoint_id" in request.filters:
                endpoint_ids = request.filters["endpoint_id"]
                if isinstance(endpoint_ids, str):
                    endpoint_ids = [endpoint_ids]
                endpoint_filter = "', '".join(str(eid) for eid in endpoint_ids)
                filter_conditions.append(f"toString(ifact.endpoint_id) IN ('{endpoint_filter}')")

            if "prompt_id" in request.filters:
                prompt_ids = request.filters["prompt_id"]
                if isinstance(prompt_ids, str):
                    prompt_ids = [prompt_ids]
                prompt_filter = "', '".join(str(pid) for pid in prompt_ids)
                filter_conditions.append(f"ifact.prompt_id IN ('{prompt_filter}')")

        where_clause = " AND ".join(filter_conditions)

        # Determine the bucket_by field expression
        if request.bucket_by == "concurrency":
            # Concurrency is calculated as count of requests in the same second window
            # We'll use a window function approach
            bucket_field = "concurrent_count"
        elif request.bucket_by == "input_tokens":
            bucket_field = "ifact.input_tokens"
        elif request.bucket_by == "output_tokens":
            bucket_field = "ifact.output_tokens"
        else:
            bucket_field = "ifact.input_tokens"

        # Determine the metric expression
        if request.metric == "total_duration_ms":
            metric_expr = "COALESCE(ifact.total_duration_ms, 0)"
        elif request.metric == "ttft_ms":
            # Return NULL for NULL or 0 values - they represent missing/invalid TTFT data
            metric_expr = "NULLIF(ifact.ttft_ms, 0)"
        elif request.metric == "response_time_ms":
            metric_expr = "COALESCE(ifact.response_time_ms, 0)"
        elif request.metric == "throughput_per_user":
            # throughput_per_user = output_tokens * 1000 / response_time_ms / concurrent_count
            metric_expr = (
                "ifact.output_tokens * 1000.0 / NULLIF(COALESCE(ifact.response_time_ms, 0), 0) / "
                "NULLIF(concurrent_count, 0)"
            )
        else:
            metric_expr = "COALESCE(ifact.response_time_ms, 0)"

        # Auto-generate buckets if not provided
        buckets = request.buckets
        if buckets is None:
            # Query min/max of bucket_by field to auto-generate 10 buckets
            if request.bucket_by == "concurrency":
                # For concurrency, we need to calculate it first
                min_max_query = f"""
                    WITH request_counts AS (
                        SELECT
                            count(*) OVER (PARTITION BY toStartOfSecond(ifact.request_arrival_time)) as concurrent_count
                        FROM InferenceFact ifact
                        WHERE {where_clause}
                    )
                    SELECT
                        min(concurrent_count) as min_val,
                        max(concurrent_count) as max_val
                    FROM request_counts
                """
            else:
                min_max_query = f"""
                    SELECT
                        min({bucket_field}) as min_val,
                        max({bucket_field}) as max_val
                    FROM InferenceFact ifact
                    WHERE {where_clause}
                """

            min_max_result = await self.clickhouse_client.execute_query(min_max_query)
            if min_max_result and min_max_result[0][0] is not None:
                min_val = float(min_max_result[0][0])
                max_val = float(min_max_result[0][1])
            else:
                min_val = 0.0
                max_val = 100.0

            # Ensure we have a valid range
            if min_val >= max_val:
                max_val = min_val + 10.0

            # Auto-generate buckets based on bucket_by type
            if request.bucket_by == "concurrency":
                # Use integer buckets for concurrency since it's always a whole number
                min_int = int(min_val)
                max_int = int(max_val)
                unique_values = max_int - min_int + 1

                if unique_values <= 10:
                    # One bucket per integer value
                    buckets = [{"min": i, "max": i, "label": str(i)} for i in range(min_int, max_int + 1)]
                else:
                    # Group into ranges
                    bucket_size = math.ceil(unique_values / 10)
                    buckets = []
                    for i in range(10):
                        start = min_int + i * bucket_size
                        end = min(start + bucket_size - 1, max_int)
                        if start <= max_int:
                            buckets.append(
                                {
                                    "min": start,
                                    "max": end,
                                    "label": f"{start}-{end}" if start != end else str(start),
                                }
                            )
            else:
                # Token bucketing - use integer labels
                bucket_width = (max_val - min_val) / 10.0
                buckets = []
                for i in range(10):
                    bucket_start = min_val + i * bucket_width
                    bucket_end = min_val + (i + 1) * bucket_width
                    buckets.append(
                        {
                            "min": bucket_start,
                            "max": bucket_end,
                            "label": f"{int(bucket_start)}-{int(bucket_end)}",
                        }
                    )

        # Build bucket case expressions
        bucket_cases = []
        for bucket in buckets:
            bucket_min = bucket["min"]
            bucket_max = bucket["max"]
            if bucket_min == bucket_max:
                # Single value bucket (e.g., concurrency = 2)
                condition = f"bucket_value = {bucket_min}"
            elif bucket == buckets[-1]:
                # Last bucket includes upper bound
                condition = f"bucket_value >= {bucket_min}"
            else:
                condition = f"bucket_value >= {bucket_min} AND bucket_value < {bucket_max}"
            bucket_cases.append(f"WHEN {condition} THEN '{bucket['label']}'")

        bucket_case_expr = f"CASE {' '.join(bucket_cases)} ELSE 'Other' END"

        # Build the main query
        if request.bucket_by == "concurrency":
            # For concurrency, use a CTE to calculate concurrent requests per second
            query = f"""
                WITH request_with_concurrency AS (
                    SELECT
                        ifact.*,
                        count(*) OVER (PARTITION BY toStartOfSecond(ifact.request_arrival_time)) as concurrent_count
                    FROM InferenceFact ifact
                    WHERE {where_clause}
                ),
                with_bucket AS (
                    SELECT
                        concurrent_count as bucket_value,
                        {metric_expr.replace("ifact.", "")} as metric_value
                    FROM request_with_concurrency ifact
                )
                SELECT
                    {bucket_case_expr} as bucket_label,
                    count() as request_count,
                    avgIf(metric_value, metric_value IS NOT NULL AND isFinite(metric_value)) as avg_metric
                FROM with_bucket
                GROUP BY bucket_label
                ORDER BY bucket_label
            """
        else:
            # For input_tokens/output_tokens, simpler query
            # Still need concurrency for throughput_per_user metric
            if request.metric == "throughput_per_user":
                query = f"""
                    WITH request_with_concurrency AS (
                        SELECT
                            ifact.*,
                            count(*) OVER (PARTITION BY toStartOfSecond(ifact.request_arrival_time)) as concurrent_count
                        FROM InferenceFact ifact
                        WHERE {where_clause}
                    ),
                    with_bucket AS (
                        SELECT
                            {bucket_field.replace("ifact.", "")} as bucket_value,
                            {metric_expr.replace("ifact.", "")} as metric_value
                        FROM request_with_concurrency ifact
                    )
                    SELECT
                        {bucket_case_expr} as bucket_label,
                        count() as request_count,
                        avgIf(metric_value, metric_value IS NOT NULL AND isFinite(metric_value)) as avg_metric
                    FROM with_bucket
                    GROUP BY bucket_label
                    ORDER BY bucket_label
                """
            else:
                query = f"""
                    WITH with_bucket AS (
                        SELECT
                            {bucket_field} as bucket_value,
                            {metric_expr} as metric_value
                        FROM InferenceFact ifact
                        WHERE {where_clause}
                    )
                    SELECT
                        {bucket_case_expr} as bucket_label,
                        count() as request_count,
                        avgIf(metric_value, metric_value IS NOT NULL AND isFinite(metric_value)) as avg_metric
                    FROM with_bucket
                    GROUP BY bucket_label
                    ORDER BY bucket_label
                """

        result = await self.clickhouse_client.execute_query(query)

        # Get total count
        total_query = f"SELECT count() FROM InferenceFact ifact WHERE {where_clause}"
        total_result = await self.clickhouse_client.execute_query(total_query)
        total_count = total_result[0][0] if total_result else 0

        # Process results into buckets
        bucket_data = {row[0]: (row[1], row[2]) for row in result}
        response_buckets = []

        for bucket in buckets:
            count, avg_value = bucket_data.get(bucket["label"], (0, 0.0))
            avg_value = self._safe_float(avg_value)

            response_buckets.append(
                PromptDistributionBucket(
                    range=bucket["label"],
                    bucket_start=float(bucket["min"]),
                    bucket_end=float(bucket["max"]),
                    count=count,
                    avg_value=round(avg_value, 2),
                )
            )

        # Clean up bucket definitions for response (replace inf with large number)
        clean_buckets = [
            {
                "min": bucket["min"],
                "max": 999999999 if bucket["max"] == float("inf") else bucket["max"],
                "label": bucket["label"],
            }
            for bucket in buckets
        ]

        return PromptDistributionResponse(
            buckets=response_buckets,
            total_count=total_count,
            bucket_by=request.bucket_by,
            metric=request.metric,
            date_range={"from": request.from_date, "to": request.to_date or datetime.now()},
            bucket_definitions=clean_buckets,
        )

    def _safe_float(self, value: Union[int, float, None]) -> float:
        """Convert value to safe float, handling NaN and Infinity."""
        if value is None:
            return 0.0
        if isinstance(value, int):
            return float(value)
        if isinstance(value, float):
            if math.isnan(value) or math.isinf(value):
                return 0.0
            return value
        return 0.0

    def _format_metric_value(self, metric: str, value: Union[int, float, None]) -> tuple[str, str]:
        """Format metric values with appropriate units and human-readable formatting."""
        if value is None:
            return "0", ""

        # Ensure value is safe for JSON serialization
        value = self._safe_float(value)

        # Percentage metrics
        if metric in ["success_rate", "cache_hit_rate", "error_rate"]:
            return f"{value:.1f}%", "%"

        # Time metrics (milliseconds)
        elif metric in ["avg_latency", "p95_latency", "p99_latency", "ttft_avg", "ttft_p95", "ttft_p99"]:
            if value >= 1000:
                return f"{value / 1000:.2f}s", "ms"
            return f"{value:.0f}ms", "ms"

        # Token metrics
        elif metric in ["total_tokens", "total_input_tokens", "total_output_tokens", "avg_tokens"]:
            if value >= 1_000_000:
                return f"{value / 1_000_000:.1f}M", "tokens"
            elif value >= 1_000:
                return f"{value / 1_000:.1f}K", "tokens"
            return f"{value:.0f}", "tokens"

        # Cost metrics
        elif metric in ["total_cost", "avg_cost"]:
            return f"${value:.4f}", "$"

        # Count metrics
        elif metric in ["total_requests", "unique_users"]:
            if value >= 1_000_000:
                return f"{value / 1_000_000:.1f}M", "requests" if "request" in metric else "users"
            elif value >= 1_000:
                return f"{value / 1_000:.1f}K", "requests" if "request" in metric else "users"
            return f"{value:.0f}", "requests" if "request" in metric else "users"

        # Throughput
        elif metric == "throughput_avg":
            return f"{value:.1f}", "tokens/sec"

        # Default formatting
        else:
            return f"{value:.2f}", ""

    async def get_blocking_stats(self, from_date, to_date, project_id=None, rule_id=None, data_source="inference"):
        """Get comprehensive blocking rule statistics from InferenceFact table.

        This method queries the unified InferenceFact table which contains blocking event data
        from both the main inference MV (for requests that reached inference) and the blocking MV
        (for blocked-only requests that never reached inference).

        Args:
            from_date: Start date for the query
            to_date: End date for the query
            project_id: Optional project filter
            rule_id: Optional specific rule filter
            data_source: Filter by data source (inference or prompt)

        Returns:
            GatewayBlockingRuleStats with blocking statistics
        """
        self._ensure_initialized()

        # Build parameters
        params = {
            "from_date": from_date,
            "to_date": to_date or datetime.now(),
        }

        # Build WHERE conditions - filter on is_blocked = true
        where_conditions = [
            "is_blocked = true",
            "timestamp >= %(from_date)s",
            "timestamp <= %(to_date)s",
        ]

        # Add prompt_id filter based on data_source
        if data_source == "prompt":
            where_conditions.append("prompt_id IS NOT NULL AND prompt_id != ''")
        else:  # inference (default)
            where_conditions.append("(prompt_id IS NULL OR prompt_id = '')")

        if project_id:
            where_conditions.append("project_id = %(project_id)s")
            params["project_id"] = project_id

        if rule_id:
            where_conditions.append("rule_id = %(rule_id)s")
            params["rule_id"] = rule_id

        where_clause = " AND ".join(where_conditions)

        # Query 1: Total stats
        stats_query = f"""
            SELECT
                COUNT(*) as total_blocked,
                uniqExact(rule_id) as unique_rules,
                uniqExact(client_ip) as unique_ips
            FROM InferenceFact
            WHERE {where_clause}
        """

        stats_result = await self.clickhouse_client.execute_query(stats_query, params)
        total_blocked = stats_result[0][0] if stats_result else 0

        # Query 2: Rule breakdown
        rule_breakdown_query = f"""
            SELECT
                rule_type,
                rule_name,
                rule_id,
                COUNT(*) as block_count,
                uniqExact(client_ip) as unique_ips_blocked
            FROM InferenceFact
            WHERE {where_clause}
            GROUP BY rule_type, rule_name, rule_id
            ORDER BY block_count DESC
        """

        rule_breakdown_result = await self.clickhouse_client.execute_query(rule_breakdown_query, params)

        blocked_by_rule = {}
        blocked_by_type = {}

        for row in rule_breakdown_result:
            rule_type = row[0]
            rule_name = row[1]
            block_count = row[3]

            if rule_name:
                blocked_by_rule[rule_name] = block_count
            if rule_type:
                if rule_type in blocked_by_type:
                    blocked_by_type[rule_type] += block_count
                else:
                    blocked_by_type[rule_type] = block_count

        # Query 3: Block reason breakdown (using block_reason_detail for detailed reason)
        reason_query = f"""
            SELECT
                coalesce(block_reason_detail, block_reason, 'unknown') as reason,
                COUNT(*) as count
            FROM InferenceFact
            WHERE {where_clause}
            GROUP BY reason
            ORDER BY count DESC
        """

        reason_result = await self.clickhouse_client.execute_query(reason_query, params)
        blocked_by_reason = {row[0]: row[1] for row in reason_result if row[0]}

        # Query 4: Top blocked IPs
        top_ips_query = f"""
            SELECT
                toString(client_ip) as ip,
                any(country_code) as country_code,
                COUNT(*) as block_count
            FROM InferenceFact
            WHERE {where_clause}
            GROUP BY client_ip
            ORDER BY block_count DESC
            LIMIT 10
        """

        top_ips_result = await self.clickhouse_client.execute_query(top_ips_query, params)
        top_blocked_ips = [
            {"ip": row[0] or "Unknown", "country": row[1] or "Unknown", "count": row[2]} for row in top_ips_result
        ]

        # Query 5: Time series (hourly)
        time_series_query = f"""
            SELECT
                toStartOfHour(timestamp) as hour,
                COUNT(*) as blocked_count
            FROM InferenceFact
            WHERE {where_clause}
            GROUP BY hour
            ORDER BY hour
        """

        time_series_result = await self.clickhouse_client.execute_query(time_series_query, params)
        time_series = [{"timestamp": row[0].isoformat(), "blocked_count": row[1]} for row in time_series_result]

        # Calculate block rate (total requests from InferenceFact in same period)
        total_requests_query = f"""
            SELECT COUNT(*)
            FROM InferenceFact
            WHERE timestamp >= %(from_date)s
            AND timestamp <= %(to_date)s
            {"AND project_id = %(project_id)s" if project_id else ""}
        """

        try:
            total_requests_result = await self.clickhouse_client.execute_query(total_requests_query, params)
            total_requests = total_requests_result[0][0] if total_requests_result else 0
            block_rate = (total_blocked / total_requests * 100) if total_requests > 0 else 0.0
        except Exception:
            # If we can't get total requests, set block rate to 0
            block_rate = 0.0

        # Import the response model
        from .schemas import GatewayBlockingRuleStats

        return GatewayBlockingRuleStats(
            total_blocked=total_blocked,
            block_rate=round(block_rate, 2),
            blocked_by_rule=blocked_by_rule,
            blocked_by_reason=blocked_by_reason,
            top_blocked_ips=top_blocked_ips,
            time_series=time_series,
        )

    async def _get_blocking_stats_fallback(self, from_date, to_date, project_id=None):
        """Fallback method for blocking stats when GatewayBlockingEvents table doesn't exist."""
        logger.info("Using fallback blocking stats from GatewayAnalytics table")

        # Build parameters
        params = {
            "from_date": from_date,
            "to_date": to_date or datetime.now(),
        }

        # Build base where conditions
        where_conditions = ["timestamp >= %(from_date)s", "timestamp <= %(to_date)s", "is_blocked = true"]

        if project_id:
            where_conditions.append("project_id = %(project_id)s")
            params["project_id"] = project_id

        where_clause = " AND ".join(where_conditions)

        try:
            # Get basic blocking stats from GatewayAnalytics
            fallback_query = f"""
                SELECT
                    COUNT(*) as total_blocked,
                    uniqExact(block_rule_id) as unique_rules,
                    uniqExact(client_ip) as unique_ips
                FROM GatewayAnalytics
                WHERE {where_clause}
            """

            result = await self.clickhouse_client.execute_query(fallback_query, params)
            total_blocked = result[0][0] if result else 0

            from budmetrics.observability.schemas import GatewayBlockingRuleStats

            return GatewayBlockingRuleStats(
                total_blocked=total_blocked,
                block_rate=0.0,
                blocked_by_rule={},
                blocked_by_reason={},
                top_blocked_ips=[],
                time_series=[],
            )
        except Exception as e:
            logger.error(f"Failed to get fallback blocking stats: {e}")
            from budmetrics.observability.schemas import GatewayBlockingRuleStats

            return GatewayBlockingRuleStats(
                total_blocked=0,
                block_rate=0.0,
                blocked_by_rule={},
                blocked_by_reason={},
                top_blocked_ips=[],
                time_series=[],
            )

    async def get_rule_block_count(self, rule_id: str, from_date=None, to_date=None):
        """Get block count for a specific rule.

        Args:
            rule_id: The UUID of the blocking rule
            from_date: Optional start date (defaults to 24 hours ago)
            to_date: Optional end date (defaults to now)

        Returns:
            Integer count of blocks for this rule
        """
        from datetime import timedelta

        self._ensure_initialized()

        # Default to last 24 hours if no dates provided
        if not from_date:
            from_date = datetime.now() - timedelta(days=1)
        if not to_date:
            to_date = datetime.now()

        # Check if GatewayBlockingEvents table exists
        try:
            table_exists_query = "EXISTS TABLE GatewayBlockingEvents"
            table_exists_result = await self.clickhouse_client.execute_query(table_exists_query)
            blocking_table_exists = table_exists_result and table_exists_result[0][0] == 1
        except Exception:
            blocking_table_exists = False

        if not blocking_table_exists:
            logger.warning("GatewayBlockingEvents table not found, returning 0")
            return 0

        # Query for specific rule
        query = """
            SELECT COUNT(*) as block_count
            FROM GatewayBlockingEvents
            WHERE rule_id = %(rule_id)s
            AND blocked_at >= %(from_date)s
            AND blocked_at <= %(to_date)s
        """

        params = {"rule_id": rule_id, "from_date": from_date, "to_date": to_date}

        try:
            result = await self.clickhouse_client.execute_query(query, params)
            return result[0][0] if result else 0
        except Exception as e:
            logger.error(f"Failed to get block count for rule {rule_id}: {e}")
            return 0

    async def get_credential_usage(
        self,
        request: CredentialUsageRequest,
    ) -> CredentialUsageResponse:
        """Get credential usage statistics from InferenceFact.

        This method queries the InferenceFact table to find the most recent
        usage for each credential (api_key_id) within the specified time window.

        Args:
            request: Request containing the time window and optional credential IDs

        Returns:
            CredentialUsageResponse with usage statistics for each credential
        """
        self._ensure_initialized()

        try:
            # Get data_source from request, defaulting to "inference"
            data_source = getattr(request, "data_source", "inference")

            # Build prompt_id filter based on data_source
            if data_source == "prompt":
                prompt_filter = "AND prompt_id IS NOT NULL AND prompt_id != ''"
            else:  # inference (default)
                prompt_filter = "AND (prompt_id IS NULL OR prompt_id = '')"

            # Build the query to get last usage per credential
            query = f"""
            SELECT
                api_key_id as credential_id,
                MAX(request_arrival_time) as last_used_at,
                COUNT(*) as request_count
            FROM InferenceFact
            WHERE request_arrival_time >= %(since)s
                AND api_key_id IS NOT NULL
                {prompt_filter}
            """

            params = {"since": request.since}

            # Add credential ID filter if specified
            if request.credential_ids:
                placeholders = [f"%(cred_{i})s" for i in range(len(request.credential_ids))]
                query += f" AND api_key_id IN ({','.join(placeholders)})"
                for i, cred_id in enumerate(request.credential_ids):
                    params[f"cred_{i}"] = str(cred_id)

            query += """
            GROUP BY api_key_id
            ORDER BY last_used_at DESC
            """

            # Execute the query
            results = await self.clickhouse_client.execute_query(query, params)

            # Parse results into response items
            credentials = []
            for row in results:
                # Handle both UUID objects and strings from ClickHouse
                cred_id = row[0]
                if isinstance(cred_id, str):
                    cred_id = UUID(cred_id)
                elif not isinstance(cred_id, UUID):
                    # Convert to string first if it's neither UUID nor string
                    cred_id = UUID(str(cred_id))

                credentials.append(
                    CredentialUsageItem(
                        credential_id=cred_id,
                        last_used_at=row[1],
                        request_count=row[2],
                    )
                )

            # Create response
            response = CredentialUsageResponse(
                credentials=credentials,
                query_window={
                    "since": request.since,
                    "until": datetime.now(),
                },
            )

            return response

        except Exception as e:
            logger.error(f"Error fetching credential usage: {e}")
            # Return empty credentials list on error
            response = CredentialUsageResponse(
                credentials=[],
                query_window={
                    "since": request.since,
                    "until": datetime.now(),
                },
            )
            return response

    async def get_metrics_sync(
        self,
        request: MetricsSyncRequest,
    ) -> MetricsSyncResponse:
        """Get unified metrics sync data for both credentials and users.

        This method provides efficient sync capabilities by combining credential usage
        and user usage data in a single call. It supports both incremental (recent activity)
        and full sync modes.

        Args:
            request: Request containing sync mode and parameters

        Returns:
            MetricsSyncResponse with both credential and user usage data
        """
        self._ensure_initialized()

        query_timestamp = datetime.now()
        credential_usage = []
        user_usage = []
        stats = {"active_credentials": 0, "active_users": 0, "total_users_checked": 0}

        # Get data_source from request, defaulting to "inference"
        data_source = getattr(request, "data_source", "inference")

        try:
            # 1. Get credential usage data if requested
            if request.credential_sync:
                credential_usage = await self._get_sync_credential_data(
                    request.sync_mode, request.activity_threshold_minutes, data_source
                )
                stats["active_credentials"] = len(credential_usage)

            # 2. Get user usage data if requested
            if request.user_usage_sync:
                user_usage = await self._get_sync_user_data(
                    request.sync_mode, request.activity_threshold_minutes, request.user_ids, data_source
                )
                stats["active_users"] = len(user_usage)
                # For stats, estimate total users checked based on mode
                if request.sync_mode == "full":
                    stats["total_users_checked"] = await self._get_total_users_count()
                else:
                    stats["total_users_checked"] = len(user_usage)

            response = MetricsSyncResponse(
                sync_mode=request.sync_mode,
                activity_threshold_minutes=request.activity_threshold_minutes,
                query_timestamp=query_timestamp,
                credential_usage=credential_usage,
                user_usage=user_usage,
                stats=stats,
            )

            logger.info(
                f"Metrics sync completed: mode={request.sync_mode}, credentials={len(credential_usage)}, users={len(user_usage)}"
            )
            return response

        except Exception as e:
            logger.error(f"Error in metrics sync: {e}")
            # Return empty response on error
            return MetricsSyncResponse(
                sync_mode=request.sync_mode,
                activity_threshold_minutes=request.activity_threshold_minutes,
                query_timestamp=query_timestamp,
                credential_usage=[],
                user_usage=[],
                stats={"active_credentials": 0, "active_users": 0, "total_users_checked": 0},
            )

    async def _get_sync_credential_data(
        self, sync_mode: str, threshold_minutes: int, data_source: str = "inference"
    ) -> list[CredentialUsageItem]:
        """Get credential usage data for sync based on mode."""
        try:
            # Build prompt_id filter based on data_source
            if data_source == "prompt":
                prompt_filter = "AND prompt_id IS NOT NULL AND prompt_id != ''"
            else:  # inference (default)
                prompt_filter = "AND (prompt_id IS NULL OR prompt_id = '')"

            # Base query for credential usage from InferenceFact
            query = f"""
            SELECT
                api_key_id as credential_id,
                MAX(request_arrival_time) as last_used_at,
                COUNT(*) as request_count
            FROM InferenceFact
            WHERE api_key_id IS NOT NULL
                {prompt_filter}
            """

            params = {}

            if sync_mode == "incremental":
                # Only credentials used within threshold
                since_time = datetime.now() - timedelta(minutes=threshold_minutes)
                query += " AND request_arrival_time >= %(since)s"
                params["since"] = since_time

            query += """
            GROUP BY api_key_id
            ORDER BY last_used_at DESC
            """

            results = await self.clickhouse_client.execute_query(query, params)

            credentials = []
            for row in results:
                # Handle both UUID objects and strings from ClickHouse
                cred_id = row[0]
                if isinstance(cred_id, str):
                    cred_id = UUID(cred_id)
                elif not isinstance(cred_id, UUID):
                    cred_id = UUID(str(cred_id))

                credentials.append(
                    CredentialUsageItem(
                        credential_id=cred_id,
                        last_used_at=row[1],
                        request_count=row[2],
                    )
                )

            return credentials

        except Exception as e:
            logger.error(f"Error getting sync credential data: {e}")
            return []

    async def _get_sync_user_data(
        self,
        sync_mode: str,
        threshold_minutes: int,
        user_ids: Optional[list[UUID]] = None,
        data_source: str = "inference",
    ) -> list[UserUsageItem]:
        """Get user usage data for sync based on mode."""
        try:
            from datetime import datetime, timezone

            logger.info(f"_get_sync_user_data called: mode={sync_mode}, user_ids={len(user_ids) if user_ids else 0}")

            # Build prompt_id filter based on data_source
            if data_source == "prompt":
                prompt_filter = "AND prompt_id IS NOT NULL AND prompt_id != ''"
            else:  # inference (default)
                prompt_filter = "AND (prompt_id IS NULL OR prompt_id = '')"

            # Base query for user usage from InferenceFact (denormalized, no JOIN needed)
            query = f"""
            SELECT
                user_id,
                MAX(request_arrival_time) as last_activity_at,
                SUM(COALESCE(input_tokens, 0) + COALESCE(output_tokens, 0)) as total_tokens,
                SUM(COALESCE(cost, 0)) as total_cost,
                COUNT(*) as request_count,
                AVG(CASE WHEN is_success THEN 1 ELSE 0 END) as success_rate
            FROM InferenceFact
            WHERE user_id IS NOT NULL
                {prompt_filter}
            """

            params = {}

            if sync_mode == "incremental":
                # Only users with activity within threshold
                since_time = datetime.now() - timedelta(minutes=threshold_minutes)
                query += " AND request_arrival_time >= %(since)s"
                params["since"] = since_time
            # For full sync, get ALL users with any activity (no time filter, no user filter)

            query += """
            GROUP BY user_id
            ORDER BY last_activity_at DESC
            """

            results = await self.clickhouse_client.execute_query(query, params)
            logger.info(f"ClickHouse query returned {len(results)} rows")

            users = []
            found_user_ids = set()

            for row in results:
                # Handle both UUID objects and strings from ClickHouse
                user_id = row[0]
                if isinstance(user_id, str):
                    user_id = UUID(user_id)
                elif not isinstance(user_id, UUID):
                    user_id = UUID(str(user_id))

                found_user_ids.add(user_id)

                usage_data = {
                    "total_tokens": int(row[2]) if row[2] else 0,
                    "total_cost": float(row[3]) if row[3] else 0.0,
                    "request_count": int(row[4]) if row[4] else 0,
                    "success_rate": float(row[5]) if row[5] else 0.0,
                }

                users.append(
                    UserUsageItem(
                        user_id=user_id,
                        last_activity_at=row[1],
                        usage_data=usage_data,
                    )
                )

            # For full sync, include all users with active billing records (even if no activity)
            if sync_mode == "full":
                # Import the Dapr service function
                from budmetrics.shared.dapr_service import get_users_with_active_billing

                # Get users with active billing from budapp
                billing_user_ids = await get_users_with_active_billing()
                logger.info(
                    f"Full sync: found {len(found_user_ids)} users with activity, {len(billing_user_ids)} users with active billing"
                )

                # Combine specific user_ids (if provided) with billing users
                users_to_add = set(billing_user_ids)
                if user_ids:
                    users_to_add.update(user_ids)

                no_activity_count = 0
                for user_id in users_to_add:
                    if user_id not in found_user_ids:
                        # Create entry for users with no activity but who have billing records
                        users.append(
                            UserUsageItem(
                                user_id=user_id,
                                last_activity_at=datetime.now(
                                    timezone.utc
                                ),  # Use current time for users with no activity
                                usage_data={
                                    "total_tokens": 0,
                                    "total_cost": 0.0,
                                    "request_count": 0,
                                    "success_rate": 0.0,
                                },
                            )
                        )
                        no_activity_count += 1

                logger.info(
                    f"Added {no_activity_count} users with no activity to sync data "
                    f"({len(billing_user_ids)} with billing, {len(user_ids) if user_ids else 0} admin users)"
                )

            return users

        except Exception as e:
            logger.error(f"Error getting sync user data: {e}")
            return []

    async def _get_total_users_count(self) -> int:
        """Get total count of users with activity for stats."""
        try:
            query = "SELECT COUNT(DISTINCT user_id) FROM ModelInferenceDetails WHERE user_id IS NOT NULL"
            result = await self.clickhouse_client.execute_query(query, {})
            return result[0][0] if result else 0
        except Exception as e:
            logger.error(f"Error getting total users count: {e}")
            return 0
