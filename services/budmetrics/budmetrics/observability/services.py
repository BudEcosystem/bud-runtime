import asyncio
import math
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional, Union
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
    AudioInferenceDetail,
    CacheMetric,
    CountMetric,
    CredentialUsageItem,
    CredentialUsageRequest,
    CredentialUsageResponse,
    EmbeddingInferenceDetail,
    EnhancedInferenceDetailResponse,
    FeedbackItem,
    GatewayAnalyticsRequest,
    GatewayAnalyticsResponse,
    GatewayMetadata,
    ImageInferenceDetail,
    InferenceFeedbackResponse,
    InferenceListItem,
    InferenceListRequest,
    InferenceListResponse,
    LatencyDistributionRequest,
    LatencyDistributionResponse,
    MetricsData,
    MetricsSyncRequest,
    MetricsSyncResponse,
    ModerationInferenceDetail,
    ObservabilityMetricsRequest,
    ObservabilityMetricsResponse,
    PerformanceMetric,
    PeriodBin,
    TimeMetric,
    UserUsageItem,
)


logger = logging.get_logger(__name__)


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

    @profile_sync("result_processing")
    def _process_query_results(
        self,
        results: list[tuple],
        field_order: list[str],
        metrics: list[str],
        group_by: Optional[list[str]] = None,
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

        # Pre-compute group field indices
        group_field_indices = {}
        if group_by:
            for group_field in group_by:
                if group_field in field_index:
                    group_field_indices[group_field] = field_index[group_field]

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
                # Check if any group field has a zero UUID
                is_gap_filled = False
                for _group_field, idx in group_field_indices.items():
                    if row[idx] == self._ZERO_UUID:
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
                data=metrics_data,
            )

            period_bins[time_period].append(metrics_item)

        # Convert to list of PeriodBin objects, sorted by time descending
        # Use list comprehension for better performance
        result_bins = [
            PeriodBin(time_period=time_period, items=period_bins[time_period] or None)
            for time_period in sorted(period_bins.keys(), reverse=True)
        ]

        return result_bins

    async def get_metrics(self, request: ObservabilityMetricsRequest) -> ObservabilityMetricsResponse:
        """Get metrics based on the request.

        Args:
            request: ObservabilityMetricsRequest with query parameters

        Returns:
            ObservabilityMetricsResponse with processed metrics data
        """
        await self.initialize()

        # Build query (validation already done by Pydantic)
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
        )

        # Execute query
        try:
            results = await self.clickhouse_client.execute_query(query)
        except Exception as e:
            logger.error(f"Failed to execute metrics query: {str(e)}")
            raise RuntimeError("Failed to execute metrics query") from e

        # Process results
        period_bins = self._process_query_results(results, field_order, request.metrics, request.group_by)

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

        Args:
            request: InferenceListRequest with query parameters

        Returns:
            InferenceListResponse with paginated inference data
        """
        await self.initialize()

        # Build WHERE clause for filters
        where_conditions = []
        params = {}

        # Always filter by date range
        where_conditions.append("mi.timestamp >= %(from_date)s")
        params["from_date"] = request.from_date

        if request.to_date:
            where_conditions.append("mi.timestamp <= %(to_date)s")
            params["to_date"] = request.to_date

        if request.project_id:
            where_conditions.append("mid.project_id = %(project_id)s")
            params["project_id"] = str(request.project_id)

        # Support filtering by api_key_project_id (for CLIENT users)
        if hasattr(request, "filters") and request.filters and "api_key_project_id" in request.filters:
            api_key_project_ids = request.filters["api_key_project_id"]
            if isinstance(api_key_project_ids, list):
                placeholders = [f"%(api_key_project_{i})s" for i in range(len(api_key_project_ids))]
                where_conditions.append(f"mid.api_key_project_id IN ({','.join(placeholders)})")
                for i, val in enumerate(api_key_project_ids):
                    params[f"api_key_project_{i}"] = str(val)
            else:
                where_conditions.append("mid.api_key_project_id = %(api_key_project_id)s")
                params["api_key_project_id"] = str(api_key_project_ids)

        if request.endpoint_id:
            where_conditions.append("mid.endpoint_id = %(endpoint_id)s")
            params["endpoint_id"] = str(request.endpoint_id)

        if request.model_id:
            where_conditions.append("mid.model_id = %(model_id)s")
            params["model_id"] = str(request.model_id)

        if request.is_success is not None:
            where_conditions.append("mid.is_success = %(is_success)s")
            params["is_success"] = 1 if request.is_success else 0

        if request.min_tokens is not None:
            where_conditions.append("(mi.input_tokens + mi.output_tokens) >= %(min_tokens)s")
            params["min_tokens"] = request.min_tokens

        if request.max_tokens is not None:
            where_conditions.append("(mi.input_tokens + mi.output_tokens) <= %(max_tokens)s")
            params["max_tokens"] = request.max_tokens

        if request.max_latency_ms is not None:
            where_conditions.append("mi.response_time_ms <= %(max_latency_ms)s")
            params["max_latency_ms"] = request.max_latency_ms

        if request.endpoint_type:
            where_conditions.append("mi.endpoint_type = %(endpoint_type)s")
            params["endpoint_type"] = request.endpoint_type

        where_clause = " AND ".join(where_conditions)

        # Build ORDER BY clause - validate sort_by to prevent injection
        sort_column_map = {
            "timestamp": "mi.timestamp",
            "tokens": "(mi.input_tokens + mi.output_tokens)",
            "latency": "mi.response_time_ms",
            "cost": "mid.cost",
        }

        # Validate sort_by is in allowed columns
        if request.sort_by not in sort_column_map:
            raise ValueError("Invalid sort_by parameter")

        # Validate sort_order
        if request.sort_order.upper() not in ("ASC", "DESC"):
            raise ValueError("Invalid sort_order parameter")

        order_by = f"{sort_column_map[request.sort_by]} {request.sort_order.upper()}"

        # Count total records
        # Safe: where_clause is built from validated conditions
        # Optimized: Use count() instead of COUNT(*) and join with ModelInference only if needed
        # This reduces memory usage by avoiding loading large text fields from unnecessary tables
        if any(cond.startswith("mi.") for cond in where_conditions):
            # If we have filters on ModelInference fields, we need the JOIN
            count_query = f"""
            SELECT count() as total_count
            FROM ModelInferenceDetails mid
            INNER JOIN ModelInference mi ON mid.inference_id = mi.inference_id
            WHERE {where_clause}
            """  # nosec B608
        else:
            # If all filters are on ModelInferenceDetails, we can count directly
            count_query = f"""
            SELECT count() as total_count
            FROM ModelInferenceDetails mid
            WHERE {where_clause}
            """  # nosec B608

        # Execute count query with parameters
        count_result = await self.clickhouse_client.execute_query(count_query, params)
        total_count = count_result[0][0] if count_result else 0

        # Get paginated data
        # Safe: where_clause and order_by are validated, limit/offset use parameters
        # Optimized: Removed ChatInference JOIN as data is already in ModelInference.input_messages and ModelInference.output
        list_query = f"""
        SELECT
            mi.inference_id,
            mi.timestamp,
            mi.model_name,
            CASE
                WHEN mi.endpoint_type = 'chat' THEN toValidUTF8(substring(mi.input_messages, 1, 100))
                WHEN mi.endpoint_type = 'embedding' THEN toValidUTF8(substring(ei.input, 1, 100))
                WHEN mi.endpoint_type IN ('audio_transcription', 'audio_translation', 'text_to_speech') THEN toValidUTF8(substring(ai.input, 1, 100))
                WHEN mi.endpoint_type = 'image_generation' THEN toValidUTF8(substring(ii.prompt, 1, 100))
                WHEN mi.endpoint_type = 'moderation' THEN toValidUTF8(substring(modi.input, 1, 100))
                ELSE toValidUTF8(substring(mi.input_messages, 1, 100))
            END as prompt_preview,
            CASE
                WHEN mi.endpoint_type = 'chat' THEN toValidUTF8(substring(mi.output, 1, 100))
                WHEN mi.endpoint_type = 'embedding' THEN concat('Generated ', toString(ei.input_count), ' embeddings')
                WHEN mi.endpoint_type IN ('audio_transcription', 'audio_translation', 'text_to_speech') THEN toValidUTF8(substring(ai.output, 1, 100))
                WHEN mi.endpoint_type = 'image_generation' THEN concat('Generated ', toString(ii.image_count), ' images')
                WHEN mi.endpoint_type = 'moderation' THEN if(modi.flagged, 'Content flagged', 'Content passed')
                ELSE toValidUTF8(substring(mi.output, 1, 100))
            END as response_preview,
            mi.input_tokens,
            mi.output_tokens,
            mi.input_tokens + mi.output_tokens as total_tokens,
            mi.response_time_ms,
            mid.cost,
            mid.is_success,
            mi.cached,
            mid.project_id,
            mid.api_key_project_id,
            mid.endpoint_id,
            mid.model_id,
            coalesce(mi.endpoint_type, 'chat') as endpoint_type,
            mid.error_code,
            mid.error_message,
            mid.error_type,
            mid.status_code
        FROM ModelInference mi
        INNER JOIN ModelInferenceDetails mid ON mi.inference_id = mid.inference_id
        LEFT JOIN EmbeddingInference ei ON mi.inference_id = ei.id AND mi.endpoint_type = 'embedding'
        LEFT JOIN AudioInference ai ON mi.inference_id = ai.id AND mi.endpoint_type IN ('audio_transcription', 'audio_translation', 'text_to_speech')
        LEFT JOIN ImageInference ii ON mi.inference_id = ii.id AND mi.endpoint_type = 'image_generation'
        LEFT JOIN ModerationInference modi ON mi.inference_id = modi.id AND mi.endpoint_type = 'moderation'
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

        # First check if GatewayAnalytics table exists
        try:
            table_exists_query = "EXISTS TABLE GatewayAnalytics"
            table_exists_result = await self.clickhouse_client.execute_query(table_exists_query)
            gateway_table_exists = table_exists_result and table_exists_result[0][0] == 1
            logger.info(f"GatewayAnalytics table exists: {gateway_table_exists}")

            # If table exists, do some debugging checks
            if gateway_table_exists:
                await self._debug_gateway_analytics_table(inference_id)
        except Exception as e:
            logger.warning(f"Failed to check GatewayAnalytics table existence: {e}")
            gateway_table_exists = False

        # Build query conditionally based on table existence
        if gateway_table_exists:
            query = """
            SELECT
                mi.inference_id,
                mi.timestamp,
                mi.model_name,
                mi.model_provider_name,
                mid.model_id,
                mi.system,
                toValidUTF8(coalesce(ci.input, mi.input_messages)) as input_messages,
                toValidUTF8(coalesce(ci.output, mi.output)) as output,
                ci.function_name,
                ci.variant_name,
                ci.episode_id,
                mi.input_tokens,
                mi.output_tokens,
                mi.response_time_ms,
                mi.ttft_ms,
                ci.processing_time_ms,
                mid.request_ip,
                mid.request_arrival_time,
                mid.request_forward_time,
                mid.project_id,
                mid.api_key_project_id,
                mid.endpoint_id,
                mid.is_success,
                mi.cached,
                mi.finish_reason,
                mid.cost,
                toValidUTF8(mi.raw_request) as raw_request,
                toValidUTF8(mi.raw_response) as raw_response,
                toValidUTF8(mi.gateway_request) as gateway_request,
                toValidUTF8(mi.gateway_response) as gateway_response,
                coalesce(mi.endpoint_type, 'chat') as endpoint_type,
                -- Error fields
                mid.error_code,
                mid.error_message,
                mid.error_type,
                mid.status_code,
                -- Gateway Analytics fields
                ga.client_ip,
                ga.proxy_chain,
                ga.protocol_version,
                ga.country_code,
                ga.region,
                ga.city,
                ga.latitude,
                ga.longitude,
                ga.timezone,
                ga.asn,
                ga.isp,
                toValidUTF8(ga.user_agent) as user_agent,
                ga.device_type,
                ga.browser_name,
                ga.browser_version,
                ga.os_name,
                ga.os_version,
                ga.is_bot,
                ga.method,
                ga.path,
                ga.query_params as query_params,
                ga.request_headers as request_headers,
                ga.body_size,
                ga.api_key_id,
                ga.auth_method,
                ga.user_id,
                ga.project_id as ga_project_id,
                ga.endpoint_id as ga_endpoint_id,
                ga.request_timestamp,
                ga.response_timestamp,
                ga.gateway_processing_ms,
                ga.total_duration_ms,
                ga.model_name as ga_model_name,
                ga.model_provider,
                ga.model_version,
                ga.routing_decision,
                ga.response_size,
                ga.response_headers,
                ga.is_blocked,
                ga.block_reason,
                ga.block_rule_id,
                ga.tags
            FROM ModelInference mi
            INNER JOIN ModelInferenceDetails mid ON mi.inference_id = mid.inference_id
            LEFT JOIN ChatInference ci ON mi.inference_id = ci.id
            LEFT JOIN GatewayAnalytics ga ON mi.inference_id = ga.inference_id
            WHERE mi.inference_id = %(inference_id)s
            """
        else:
            # Query without GatewayAnalytics table
            logger.info("GatewayAnalytics table not found, querying without gateway metadata")
            query = """
            SELECT
                mi.inference_id,
                mi.timestamp,
                mi.model_name,
                mi.model_provider_name,
                mid.model_id,
                mi.system,
                toValidUTF8(coalesce(ci.input, mi.input_messages)) as input_messages,
                toValidUTF8(coalesce(ci.output, mi.output)) as output,
                ci.function_name,
                ci.variant_name,
                ci.episode_id,
                mi.input_tokens,
                mi.output_tokens,
                mi.response_time_ms,
                mi.ttft_ms,
                ci.processing_time_ms,
                mid.request_ip,
                mid.request_arrival_time,
                mid.request_forward_time,
                mid.project_id,
                mid.api_key_project_id,
                mid.endpoint_id,
                mid.is_success,
                mi.cached,
                mi.finish_reason,
                mid.cost,
                toValidUTF8(mi.raw_request) as raw_request,
                toValidUTF8(mi.raw_response) as raw_response,
                toValidUTF8(mi.gateway_request) as gateway_request,
                toValidUTF8(mi.gateway_response) as gateway_response,
                coalesce(mi.endpoint_type, 'chat') as endpoint_type,
                -- Error fields
                mid.error_code,
                mid.error_message,
                mid.error_type,
                mid.status_code
            FROM ModelInference mi
            INNER JOIN ModelInferenceDetails mid ON mi.inference_id = mid.inference_id
            LEFT JOIN ChatInference ci ON mi.inference_id = ci.id
            WHERE mi.inference_id = %(inference_id)s
            """

        params = {"inference_id": inference_id}
        results, column_descriptions = await self.clickhouse_client.execute_query(
            query, params, with_column_types=True
        )

        if not results:
            raise ValueError("Inference not found")

        # Convert row to dictionary for named access
        from budmetrics.observability.models import ClickHouseClient

        row_dict = ClickHouseClient.row_to_dict(results[0], column_descriptions)

        logger.debug(f"Available columns: {list(row_dict.keys())}")
        logger.debug(f"Gateway table exists: {gateway_table_exists}")

        # Extract gateway metadata based on whether table exists and data is available
        gateway_metadata = None
        if gateway_table_exists:
            endpoint_type = row_dict.get("endpoint_type", "chat")

            logger.debug(f"Endpoint type: {endpoint_type}")

            # Check if any gateway fields are present (not all None/empty)
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
                "api_key_id",
                "auth_method",
                "user_id",
                "ga_project_id",
                "ga_endpoint_id",
                "request_timestamp",
                "response_timestamp",
                "gateway_processing_ms",
                "total_duration_ms",
                "ga_model_name",
                "model_provider",
                "model_version",
                "routing_decision",
                "status_code",
                "response_size",
                "response_headers",
                "error_type",
                "error_message",
                "is_blocked",
                "block_reason",
                "block_rule_id",
                "tags",
            ]

            gateway_field_values = [row_dict.get(field) for field in gateway_field_names]
            has_gateway_data = any(field is not None and field != "" for field in gateway_field_values)

            logger.debug(f"Gateway fields present: {has_gateway_data}")
            logger.debug(
                f"Sample gateway fields: client_ip={row_dict.get('client_ip')}, "
                f"country_code={row_dict.get('country_code')}, "
                f"user_agent={row_dict.get('user_agent')}"
            )

            if has_gateway_data:
                try:
                    # Helper function to safely convert to float
                    def safe_float(val):
                        try:
                            if val is None or val == "":
                                return None
                            return float(val)
                        except (ValueError, TypeError):
                            return None

                    # Helper function to safely convert to int
                    def safe_int(val):
                        try:
                            if val is None or val == "":
                                return None
                            return int(val)
                        except (ValueError, TypeError):
                            return None

                    # Helper function to parse dict-like fields
                    def safe_dict(val):
                        try:
                            if val is None or val == "":
                                return None
                            if isinstance(val, dict):
                                return val
                            if isinstance(val, (list, tuple)):
                                return dict(val)
                            return None
                        except (TypeError, ValueError):
                            return None

                    # Create gateway metadata using named column access
                    gateway_metadata = GatewayMetadata(
                        client_ip=row_dict.get("client_ip"),
                        proxy_chain=row_dict.get("proxy_chain"),
                        protocol_version=row_dict.get("protocol_version"),
                        country_code=row_dict.get("country_code"),
                        region=row_dict.get("region"),
                        city=row_dict.get("city"),
                        latitude=safe_float(row_dict.get("latitude")),
                        longitude=safe_float(row_dict.get("longitude")),
                        timezone=row_dict.get("timezone"),
                        asn=safe_int(row_dict.get("asn")),
                        isp=row_dict.get("isp"),
                        user_agent=row_dict.get("user_agent"),
                        device_type=row_dict.get("device_type"),
                        browser_name=row_dict.get("browser_name"),
                        browser_version=row_dict.get("browser_version"),
                        os_name=row_dict.get("os_name"),
                        os_version=row_dict.get("os_version"),
                        is_bot=row_dict.get("is_bot"),
                        method=row_dict.get("method"),
                        path=row_dict.get("path"),
                        query_params=row_dict.get("query_params"),
                        request_headers=safe_dict(row_dict.get("request_headers")),
                        body_size=safe_int(row_dict.get("body_size")),
                        api_key_id=row_dict.get("api_key_id"),
                        auth_method=row_dict.get("auth_method"),
                        user_id=row_dict.get("user_id"),
                        gateway_processing_ms=safe_int(row_dict.get("gateway_processing_ms")),
                        total_duration_ms=safe_int(row_dict.get("total_duration_ms")),
                        routing_decision=row_dict.get("routing_decision"),
                        model_version=row_dict.get("model_version"),
                        status_code=safe_int(row_dict.get("status_code")),
                        response_size=safe_int(row_dict.get("response_size")),
                        response_headers=safe_dict(row_dict.get("response_headers")),
                        error_type=row_dict.get("error_type"),
                        error_message=row_dict.get("error_message"),
                        is_blocked=row_dict.get("is_blocked"),
                        block_reason=row_dict.get("block_reason"),
                        block_rule_id=row_dict.get("block_rule_id"),
                        tags=safe_dict(row_dict.get("tags")),
                    )
                    logger.info(f"Successfully parsed gateway metadata for inference {inference_id}")
                except Exception as e:
                    logger.warning(f"Failed to parse gateway metadata for inference {inference_id}: {e}")
                    gateway_metadata = None
            else:
                logger.debug(f"No gateway data found for inference {inference_id}")
        else:
            # Without GatewayAnalytics table, get endpoint_type from the row_dict
            endpoint_type = row_dict.get("endpoint_type", "chat")
            logger.info("GatewayAnalytics table not available, gateway_metadata will be null")

        # Parse messages from JSON string
        import json

        input_messages = row_dict.get("input_messages")
        try:
            if input_messages:
                if isinstance(input_messages, str):
                    parsed_data = json.loads(input_messages)
                    # Handle the case where the JSON contains {"messages": [...]}
                    if isinstance(parsed_data, dict) and "messages" in parsed_data:
                        messages = parsed_data["messages"]
                    elif isinstance(parsed_data, list):
                        messages = parsed_data
                    else:
                        messages = []
                elif isinstance(input_messages, list):
                    messages = input_messages
                else:
                    messages = []
            else:
                messages = []
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Failed to parse messages for inference {inference_id}: {e}")
            # Try to parse as a simple message format
            messages = (
                [{"role": "user", "content": input_messages}]
                if input_messages and isinstance(input_messages, str)
                else []
            )

        # Skip feedback queries for now
        feedback_count = 0
        average_rating = None

        # Combine system prompt with messages if it exists
        combined_messages = []
        system_prompt = row_dict.get("system")
        if system_prompt:  # system_prompt exists
            combined_messages.append({"role": "system", "content": str(system_prompt)})

        # Add the parsed messages
        combined_messages.extend(messages)

        # Add the assistant's response as the last message
        output = row_dict.get("output")
        if output:  # output exists
            try:
                # Try to parse the output as JSON if it's a JSON string
                output_content = json.loads(output)
                # Keep the parsed JSON content as is
                content = output_content
            except (json.JSONDecodeError, TypeError):
                # If it's not JSON or parsing fails, use as is
                content = str(output)

            combined_messages.append({"role": "assistant", "content": content})

        try:
            # Handle UUID fields properly - keep as UUID objects or convert strings to UUID
            def safe_uuid(value):
                if value is None:
                    return None
                if isinstance(value, UUID):
                    return value
                try:
                    return UUID(str(value))
                except (ValueError, TypeError):
                    return None

            # Handle potential UUID conversion for episode_id
            episode_id = safe_uuid(row_dict.get("episode_id"))

            # Fetch type-specific details based on endpoint_type
            embedding_details = None
            audio_details = None
            image_details = None
            moderation_details = None

            if endpoint_type == "embedding":
                embedding_query = """
                SELECT embeddings, embedding_dimensions, input_count, input
                FROM EmbeddingInference
                WHERE id = %(inference_id)s
                """
                embedding_results = await self.clickhouse_client.execute_query(embedding_query, params)
                if embedding_results:
                    emb_row = embedding_results[0]
                    embedding_details = EmbeddingInferenceDetail(
                        embeddings=json.loads(emb_row[0]) if isinstance(emb_row[0], str) else emb_row[0],
                        embedding_dimensions=emb_row[1],
                        input_count=emb_row[2],
                        input_text=emb_row[3],
                    )

            elif endpoint_type in ["audio_transcription", "audio_translation", "text_to_speech"]:
                audio_query = """
                SELECT audio_type, input, output, language, duration_seconds, file_size_bytes, response_format
                FROM AudioInference
                WHERE id = %(inference_id)s
                """
                audio_results = await self.clickhouse_client.execute_query(audio_query, params)
                if audio_results:
                    audio_row = audio_results[0]
                    audio_details = AudioInferenceDetail(
                        audio_type=audio_row[0],
                        input=audio_row[1],
                        output=audio_row[2],
                        language=audio_row[3],
                        duration_seconds=audio_row[4],
                        file_size_bytes=audio_row[5],
                        response_format=audio_row[6],
                    )

            elif endpoint_type == "image_generation":
                image_query = """
                SELECT prompt, image_count, size, quality, style, images
                FROM ImageInference
                WHERE id = %(inference_id)s
                """
                image_results = await self.clickhouse_client.execute_query(image_query, params)
                if image_results:
                    img_row = image_results[0]
                    image_details = ImageInferenceDetail(
                        prompt=img_row[0],
                        image_count=img_row[1],
                        size=img_row[2],
                        quality=img_row[3],
                        style=img_row[4],
                        images=json.loads(img_row[5]) if isinstance(img_row[5], str) else [],
                    )

            elif endpoint_type == "moderation":
                moderation_query = """
                SELECT input, results, flagged, categories, category_scores
                FROM ModerationInference
                WHERE id = %(inference_id)s
                """
                moderation_results = await self.clickhouse_client.execute_query(moderation_query, params)
                if moderation_results:
                    mod_row = moderation_results[0]
                    moderation_details = ModerationInferenceDetail(
                        input=mod_row[0],
                        results=json.loads(mod_row[1]) if isinstance(mod_row[1], str) else [],
                        flagged=mod_row[2],
                        categories=mod_row[3],
                        category_scores=mod_row[4],
                    )

            return EnhancedInferenceDetailResponse(
                object="inference_detail",
                inference_id=safe_uuid(row_dict.get("mi.inference_id")),
                timestamp=row_dict.get("mi.timestamp"),
                model_name=str(row_dict.get("mi.model_name")) if row_dict.get("mi.model_name") else "",
                model_provider=str(row_dict.get("model_provider_name"))
                if row_dict.get("model_provider_name")
                else "unknown",
                model_id=safe_uuid(row_dict.get("model_id")),
                system_prompt=str(row_dict.get("system"))
                if row_dict.get("system")
                else None,  # Keep for backward compatibility
                messages=combined_messages,  # Now includes system, user, and assistant messages
                output=str(row_dict.get("output"))
                if row_dict.get("output")
                else "",  # Keep for backward compatibility
                function_name=str(row_dict.get("function_name")) if row_dict.get("function_name") else None,
                variant_name=str(row_dict.get("variant_name")) if row_dict.get("variant_name") else None,
                episode_id=episode_id,
                input_tokens=int(row_dict.get("input_tokens")) if row_dict.get("input_tokens") else 0,
                output_tokens=int(row_dict.get("output_tokens")) if row_dict.get("output_tokens") else 0,
                response_time_ms=int(row_dict.get("response_time_ms")) if row_dict.get("response_time_ms") else 0,
                ttft_ms=int(row_dict.get("ttft_ms")) if row_dict.get("ttft_ms") else None,
                processing_time_ms=int(row_dict.get("processing_time_ms"))
                if row_dict.get("processing_time_ms")
                else None,
                request_ip=str(row_dict.get("request_ip")) if row_dict.get("request_ip") else None,
                request_arrival_time=row_dict.get("request_arrival_time") or row_dict.get("mi.timestamp"),
                request_forward_time=row_dict.get("request_forward_time") or row_dict.get("mi.timestamp"),
                project_id=safe_uuid(row_dict.get("mid.project_id")),
                api_key_project_id=safe_uuid(row_dict.get("api_key_project_id")),
                endpoint_id=safe_uuid(row_dict.get("mid.endpoint_id")),
                is_success=bool(row_dict.get("is_success")) if row_dict.get("is_success") is not None else True,
                cached=bool(row_dict.get("cached")) if row_dict.get("cached") is not None else False,
                finish_reason=str(row_dict.get("finish_reason")) if row_dict.get("finish_reason") else None,
                cost=float(row_dict.get("cost")) if row_dict.get("cost") else None,
                error_code=str(row_dict.get("error_code")) if row_dict.get("error_code") else None,
                error_message=str(row_dict.get("error_message")) if row_dict.get("error_message") else None,
                error_type=str(row_dict.get("error_type")) if row_dict.get("error_type") else None,
                status_code=int(row_dict.get("status_code")) if row_dict.get("status_code") else None,
                raw_request=str(row_dict.get("raw_request")) if row_dict.get("raw_request") else None,
                raw_response=str(row_dict.get("raw_response")) if row_dict.get("raw_response") else None,
                gateway_request=str(row_dict.get("gateway_request")) if row_dict.get("gateway_request") else None,
                gateway_response=str(row_dict.get("gateway_response")) if row_dict.get("gateway_response") else None,
                gateway_metadata=gateway_metadata,  # New gateway metadata
                feedback_count=feedback_count,
                average_rating=average_rating,
                endpoint_type=endpoint_type,
                embedding_details=embedding_details,
                audio_details=audio_details,
                image_details=image_details,
                moderation_details=moderation_details,
            )
        except Exception as e:
            logger.error(f"Failed to create InferenceDetailResponse: {e}")
            logger.error(f"Row data columns: {list(row_dict.keys())}")
            raise ValueError(f"Failed to process inference data: {str(e)}") from e

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
        result = await self._clickhouse_client.execute_query(query)

        # Process results into response format
        items = await self._process_gateway_metrics_results(result, request)

        # Calculate summary statistics if requested
        summary = None
        if len(items) > 0:
            summary = self._calculate_gateway_summary_stats(items, request)

        return GatewayAnalyticsResponse(object="gateway_analytics", code=200, items=items, summary=summary)

    async def get_geographical_stats(self, from_date, to_date, project_id):
        """Get geographical distribution statistics."""
        self._ensure_initialized()

        # Build queries for country and city stats
        country_query = self._build_geographical_query(from_date, to_date, project_id, "country")
        city_query = self._build_geographical_query(from_date, to_date, project_id, "city")

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

    async def get_top_routes(self, from_date, to_date, limit, project_id):
        """Get top API routes by request count."""
        self._ensure_initialized()

        query = self._build_top_routes_query(from_date, to_date, limit, project_id)
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

    async def get_client_analytics(self, from_date, to_date, group_by, project_id):
        """Get client analytics (device, browser, OS distribution)."""
        self._ensure_initialized()

        query = self._build_client_analytics_query(from_date, to_date, group_by, project_id)
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
        # This is a simplified version - you would need to implement the full query builder
        return """
            SELECT
                toStartOfHour(timestamp) as time_bucket,
                count(*) as request_count,
                avg(response_time_ms) as avg_response_time
            FROM bud.ModelInferenceDetails
            WHERE timestamp >= %(from_date)s
                AND timestamp <= %(to_date)s
            GROUP BY time_bucket
            ORDER BY time_bucket
        """

    def _build_geographical_query(self, from_date, to_date, project_id, group_type):
        """Build query for geographical statistics."""
        if group_type == "country":
            return f"""
                SELECT
                    country_code,
                    count(*) as count
                FROM bud.ModelInferenceDetails
                WHERE timestamp >= '{from_date.isoformat()}'
                    {f"AND timestamp <= '{to_date.isoformat()}'" if to_date else ""}
                    {f"AND project_id = '{project_id}'" if project_id else ""}
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
                FROM bud.ModelInferenceDetails
                WHERE timestamp >= '{from_date.isoformat()}'
                    {f"AND timestamp <= '{to_date.isoformat()}'" if to_date else ""}
                    {f"AND project_id = '{project_id}'" if project_id else ""}
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

    def _build_top_routes_query(self, from_date, to_date, limit, project_id):
        """Build query for top routes."""
        return f"""
            SELECT
                path,
                http_method,
                count(*) as count,
                avg(response_time_ms) as avg_response_time,
                sum(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) / count(*) * 100 as error_rate
            FROM bud.ModelInferenceDetails
            WHERE timestamp >= '{from_date.isoformat()}'
                {f"AND timestamp <= '{to_date.isoformat()}'" if to_date else ""}
                {f"AND project_id = '{project_id}'" if project_id else ""}
            GROUP BY path, http_method
            ORDER BY count DESC
            LIMIT {limit}
        """

    def _build_client_analytics_query(self, from_date, to_date, group_by, project_id):
        """Build query for client analytics."""
        field_map = {"device_type": "device_type", "browser": "browser_name", "os": "os_name"}
        field = field_map.get(group_by, "device_type")

        return f"""
            SELECT
                {field},
                count(*) as count
            FROM bud.ModelInferenceDetails
            WHERE timestamp >= '{from_date.isoformat()}'
                {f"AND timestamp <= '{to_date.isoformat()}'" if to_date else ""}
                {f"AND project_id = '{project_id}'" if project_id else ""}
                AND {field} IS NOT NULL
            GROUP BY {field}
            ORDER BY count DESC
        """

    def _process_gateway_metrics_results(self, result, request):
        """Process gateway metrics query results."""
        # Simplified processing - would need full implementation
        from budmetrics.observability.schemas import GatewayMetricsData, GatewayPeriodBin

        items = []

        if result:
            for row in result:
                items.append(
                    GatewayPeriodBin(
                        time_period=row[0],
                        items=[
                            GatewayMetricsData(
                                data={
                                    "request_count": {"count": row[1]},
                                    "avg_response_time": {"avg": row[2]} if len(row) > 2 else {"avg": 0},
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
        total_requests = sum(
            item.items[0].data.get("request_count", {}).get("count", 0) for item in items if item.items
        )

        return {
            "total_requests": total_requests,
            "time_range": {
                "from": request.from_date.isoformat(),
                "to": request.to_date.isoformat() if request.to_date else None,
            },
        }

    # New Aggregated Metrics Methods
    async def get_aggregated_metrics(self, request) -> dict:
        """Get aggregated metrics with server-side calculations."""
        from budmetrics.observability.schemas import (
            AggregatedMetricsGroup,
            AggregatedMetricsResponse,
            AggregatedMetricValue,
        )

        # Build the base query with efficient aggregations
        select_fields = []

        # Add grouping fields if specified
        group_by_fields = []
        if request.group_by:
            for group in request.group_by:
                if group == "model":
                    group_by_fields.extend(["mid.model_id", "mi.model_name"])
                    select_fields.extend(["mid.model_id", "mi.model_name"])
                elif group == "project":
                    group_by_fields.append("mid.project_id")
                    select_fields.append("mid.project_id")
                elif group == "endpoint":
                    group_by_fields.append("mid.endpoint_id")
                    select_fields.append("mid.endpoint_id")
                elif group == "user":
                    group_by_fields.append("ga.user_id")
                    select_fields.append("ga.user_id")
                elif group == "user_project":
                    group_by_fields.append("mid.api_key_project_id")
                    select_fields.append("mid.api_key_project_id")

        # Build aggregation fields based on requested metrics
        for metric in request.metrics:
            if metric == "total_requests":
                select_fields.append("COUNT(*) as total_requests")
            elif metric == "success_rate":
                select_fields.append("AVG(CASE WHEN mid.is_success THEN 1.0 ELSE 0.0 END) * 100 as success_rate")
            elif metric == "avg_latency":
                select_fields.append("AVG(mi.response_time_ms) as avg_latency")
            elif metric == "p95_latency":
                select_fields.append("quantile(0.95)(mi.response_time_ms) as p95_latency")
            elif metric == "p99_latency":
                select_fields.append("quantile(0.99)(mi.response_time_ms) as p99_latency")
            elif metric == "total_tokens":
                select_fields.append("SUM(mi.input_tokens + mi.output_tokens) as total_tokens")
            elif metric == "total_input_tokens":
                select_fields.append("SUM(mi.input_tokens) as total_input_tokens")
            elif metric == "total_output_tokens":
                select_fields.append("SUM(mi.output_tokens) as total_output_tokens")
            elif metric == "avg_tokens":
                select_fields.append("AVG(mi.input_tokens + mi.output_tokens) as avg_tokens")
            elif metric == "total_cost":
                select_fields.append("SUM(mid.cost) as total_cost")
            elif metric == "avg_cost":
                select_fields.append("AVG(mid.cost) as avg_cost")
            elif metric == "ttft_avg":
                select_fields.append("AVG(mi.ttft_ms) as ttft_avg")
            elif metric == "ttft_p95":
                select_fields.append("quantile(0.95)(mi.ttft_ms) as ttft_p95")
            elif metric == "ttft_p99":
                select_fields.append("quantile(0.99)(mi.ttft_ms) as ttft_p99")
            elif metric == "cache_hit_rate":
                select_fields.append("AVG(CASE WHEN mi.cached THEN 1.0 ELSE 0.0 END) * 100 as cache_hit_rate")
            elif metric == "throughput_avg":
                select_fields.append(
                    "AVG(mi.output_tokens * 1000.0 / NULLIF(mi.response_time_ms, 0)) as throughput_avg"
                )
            elif metric == "error_rate":
                select_fields.append("AVG(CASE WHEN NOT mid.is_success THEN 1.0 ELSE 0.0 END) * 100 as error_rate")
            elif metric == "unique_users":
                select_fields.append("uniqExact(ga.user_id) as unique_users")

        # Build FROM clause with joins
        from_clause = """
        FROM ModelInferenceDetails mid
        INNER JOIN ModelInference mi ON mid.inference_id = mi.inference_id
        LEFT JOIN GatewayAnalytics ga ON mid.inference_id = ga.inference_id
        """

        # Build WHERE clause
        where_conditions = ["mid.request_arrival_time >= %(from_date)s", "mid.request_arrival_time <= %(to_date)s"]

        params = {
            "from_date": request.from_date,
            "to_date": request.to_date or datetime.now(),
        }

        # Add filters
        if request.filters:
            for filter_key, filter_value in request.filters.items():
                if filter_key == "project_id":
                    if isinstance(filter_value, list):
                        placeholders = [f"%(project_{i})s" for i in range(len(filter_value))]
                        where_conditions.append(f"mid.project_id IN ({','.join(placeholders)})")
                        for i, val in enumerate(filter_value):
                            params[f"project_{i}"] = val
                    else:
                        where_conditions.append("mid.project_id = %(project_id)s")
                        params["project_id"] = filter_value
                elif filter_key == "api_key_project_id":
                    # Support filtering by api_key_project_id for CLIENT users
                    if isinstance(filter_value, list):
                        placeholders = [f"%(api_key_project_{i})s" for i in range(len(filter_value))]
                        where_conditions.append(f"mid.api_key_project_id IN ({','.join(placeholders)})")
                        for i, val in enumerate(filter_value):
                            params[f"api_key_project_{i}"] = val
                    else:
                        where_conditions.append("mid.api_key_project_id = %(api_key_project_id)s")
                        params["api_key_project_id"] = filter_value
                elif filter_key == "model_id":
                    where_conditions.append("mid.model_id = %(model_id)s")
                    params["model_id"] = filter_value
                elif filter_key == "endpoint_id":
                    where_conditions.append("mid.endpoint_id = %(endpoint_id)s")
                    params["endpoint_id"] = filter_value

        # Build final query
        order_by = "total_requests DESC" if "total_requests" in request.metrics else "1"
        query = f"""
        SELECT {", ".join(select_fields)}
        {from_clause}
        WHERE {" AND ".join(where_conditions)}
        {f"GROUP BY {', '.join(group_by_fields)}" if group_by_fields else ""}
        ORDER BY {order_by}
        """

        # Execute query
        results = await self.clickhouse_client.execute_query(query, params)

        # Process results
        groups = []
        overall_summary = {}

        if not results:
            return AggregatedMetricsResponse(
                groups=[],
                summary={},
                total_groups=0,
                date_range={"from": request.from_date, "to": request.to_date or datetime.now()},
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
            date_range={"from": request.from_date, "to": request.to_date or datetime.now()},
        )

    async def get_time_series_data(self, request) -> dict:
        """Get time-series data with efficient bucketing."""
        from budmetrics.observability.schemas import (
            TimeSeriesGroup,
            TimeSeriesPoint,
            TimeSeriesResponse,
        )

        # Map interval to ClickHouse interval functions
        # For simple functions, we'll add the column parameter later
        # For toStartOfInterval, include the full expression
        if request.interval == "1m":
            time_bucket_expr = "toStartOfMinute(mid.request_arrival_time)"
        elif request.interval == "5m":
            time_bucket_expr = "toStartOfInterval(mid.request_arrival_time, INTERVAL 5 minute)"
        elif request.interval == "15m":
            time_bucket_expr = "toStartOfInterval(mid.request_arrival_time, INTERVAL 15 minute)"
        elif request.interval == "30m":
            time_bucket_expr = "toStartOfInterval(mid.request_arrival_time, INTERVAL 30 minute)"
        elif request.interval == "1h":
            time_bucket_expr = "toStartOfHour(mid.request_arrival_time)"
        elif request.interval == "6h":
            time_bucket_expr = "toStartOfInterval(mid.request_arrival_time, INTERVAL 6 hour)"
        elif request.interval == "12h":
            time_bucket_expr = "toStartOfInterval(mid.request_arrival_time, INTERVAL 12 hour)"
        elif request.interval == "1d":
            time_bucket_expr = "toStartOfDay(mid.request_arrival_time)"
        elif request.interval == "1w":
            time_bucket_expr = "toStartOfWeek(mid.request_arrival_time)"
        else:
            time_bucket_expr = "toStartOfHour(mid.request_arrival_time)"

        # Build select fields
        select_fields = [f"{time_bucket_expr} as time_bucket"]

        # Add grouping fields
        group_by_fields = ["time_bucket"]
        if request.group_by:
            for group in request.group_by:
                if group == "model":
                    group_by_fields.extend(["mid.model_id", "mi.model_name"])
                    select_fields.extend(["mid.model_id", "mi.model_name"])
                elif group == "project":
                    group_by_fields.append("mid.project_id")
                    select_fields.append("mid.project_id")
                elif group == "endpoint":
                    group_by_fields.append("mid.endpoint_id")
                    select_fields.append("mid.endpoint_id")
                elif group == "user_project":
                    group_by_fields.append("mid.api_key_project_id")
                    select_fields.append("mid.api_key_project_id")

        # Add metric calculations
        for metric in request.metrics:
            if metric == "requests":
                select_fields.append("COUNT(*) as requests")
            elif metric == "success_rate":
                select_fields.append("AVG(CASE WHEN mid.is_success THEN 1.0 ELSE 0.0 END) * 100 as success_rate")
            elif metric == "avg_latency":
                select_fields.append("AVG(mi.response_time_ms) as avg_latency")
            elif metric == "p95_latency":
                select_fields.append("quantile(0.95)(mi.response_time_ms) as p95_latency")
            elif metric == "p99_latency":
                select_fields.append("quantile(0.99)(mi.response_time_ms) as p99_latency")
            elif metric == "tokens":
                select_fields.append("SUM(mi.input_tokens + mi.output_tokens) as tokens")
            elif metric == "cost":
                select_fields.append("SUM(mid.cost) as cost")
            elif metric == "ttft_avg":
                select_fields.append("AVG(mi.ttft_ms) as ttft_avg")
            elif metric == "cache_hit_rate":
                select_fields.append("AVG(CASE WHEN mi.cached THEN 1.0 ELSE 0.0 END) * 100 as cache_hit_rate")
            elif metric == "throughput":
                select_fields.append("AVG(mi.output_tokens * 1000.0 / NULLIF(mi.response_time_ms, 0)) as throughput")
            elif metric == "error_rate":
                select_fields.append("AVG(CASE WHEN NOT mid.is_success THEN 1.0 ELSE 0.0 END) * 100 as error_rate")

        # Build WHERE clause
        where_conditions = ["mid.request_arrival_time >= %(from_date)s", "mid.request_arrival_time <= %(to_date)s"]

        params = {
            "from_date": request.from_date,
            "to_date": request.to_date or datetime.now(),
        }

        # Add filters
        if hasattr(request, "filters") and request.filters:
            for filter_key, filter_value in request.filters.items():
                if filter_key == "project_id":
                    if isinstance(filter_value, list):
                        placeholders = [f"%(project_{i})s" for i in range(len(filter_value))]
                        where_conditions.append(f"mid.project_id IN ({','.join(placeholders)})")
                        for i, val in enumerate(filter_value):
                            params[f"project_{i}"] = val
                    else:
                        where_conditions.append("mid.project_id = %(project_id)s")
                        params["project_id"] = filter_value
                elif filter_key == "api_key_project_id":
                    # Support filtering by api_key_project_id for CLIENT users
                    if isinstance(filter_value, list):
                        placeholders = [f"%(api_key_project_{i})s" for i in range(len(filter_value))]
                        where_conditions.append(f"mid.api_key_project_id IN ({','.join(placeholders)})")
                        for i, val in enumerate(filter_value):
                            params[f"api_key_project_{i}"] = val
                    else:
                        where_conditions.append("mid.api_key_project_id = %(api_key_project_id)s")
                        params["api_key_project_id"] = filter_value
                elif filter_key == "model_id":
                    where_conditions.append("mid.model_id = %(model_id)s")
                    params["model_id"] = filter_value
                elif filter_key == "endpoint_id":
                    where_conditions.append("mid.endpoint_id = %(endpoint_id)s")
                    params["endpoint_id"] = filter_value

        # Build query
        query = f"""
        SELECT {", ".join(select_fields)}
        FROM ModelInferenceDetails mid
        INNER JOIN ModelInference mi ON mid.inference_id = mi.inference_id
        WHERE {" AND ".join(where_conditions)}
        GROUP BY {", ".join(group_by_fields)}
        ORDER BY time_bucket ASC
        """

        # Execute query
        results = await self.clickhouse_client.execute_query(query, params)

        # Process results into groups
        groups_dict = defaultdict(list)

        for row in results:
            time_bucket = row[0]

            # Extract grouping info
            group_key = "default"
            group_info = {}
            field_idx = 1

            if request.group_by:
                group_key_parts = []
                for group in request.group_by:
                    if group == "model":
                        model_id = row[field_idx]
                        model_name = row[field_idx + 1]
                        group_info["model_id"] = model_id
                        group_info["model_name"] = model_name
                        group_key_parts.append(f"model:{model_id}")
                        field_idx += 2
                    elif group == "project":
                        project_id = row[field_idx]
                        group_info["project_id"] = project_id
                        group_key_parts.append(f"project:{project_id}")
                        field_idx += 1
                    elif group == "endpoint":
                        endpoint_id = row[field_idx]
                        group_info["endpoint_id"] = endpoint_id
                        group_key_parts.append(f"endpoint:{endpoint_id}")
                        field_idx += 1
                    elif group == "user_project":
                        api_key_project_id = row[field_idx]
                        group_info["api_key_project_id"] = api_key_project_id
                        group_key_parts.append(f"api_key_project:{api_key_project_id}")
                        field_idx += 1

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

        # Fill gaps if requested
        if request.fill_gaps and groups:
            groups = self._fill_time_series_gaps(groups, request)

        return TimeSeriesResponse(
            groups=groups,
            interval=request.interval,
            date_range={"from": request.from_date, "to": request.to_date or datetime.now()},
        )

    async def get_geographic_data(self, request) -> dict:
        """Get geographic distribution data from GatewayAnalytics table.

        Note: Currently inference_id in GatewayAnalytics is not populated,
        so success_rate and avg_latency_ms will be NULL until that is fixed.
        Geographic data (country, region, city, lat/long) is directly available.
        """
        from budmetrics.observability.schemas import (
            GeographicDataPoint,
            GeographicDataResponse,
        )

        # Build query based on group_by parameter
        # Note: success_rate and avg_latency_ms require inference_id to be populated
        # For now, we use NULL-safe expressions that return NULL when no match
        # Success rate calculation that handles NULL inference_id (returns NULL when no match)
        success_rate_expr = (
            "AVG(CASE WHEN mid.is_success IS NOT NULL "
            "THEN (CASE WHEN mid.is_success THEN 1.0 ELSE 0.0 END) "
            "ELSE NULL END) * 100 as success_rate"
        )

        if request.group_by == "country":
            select_fields = [
                "ga.country_code",
                "COUNT(*) as request_count",
                success_rate_expr,
                "AVG(mi.response_time_ms) as avg_latency_ms",
                "uniqExact(ga.user_id) as unique_users",
                "any(ga.latitude) as latitude",
                "any(ga.longitude) as longitude",
            ]
            group_by_clause = "ga.country_code"
            having_clause = "ga.country_code IS NOT NULL AND ga.country_code != ''"
        elif request.group_by == "region":
            select_fields = [
                "ga.country_code",
                "ga.region",
                "COUNT(*) as request_count",
                success_rate_expr,
                "AVG(mi.response_time_ms) as avg_latency_ms",
                "uniqExact(ga.user_id) as unique_users",
            ]
            group_by_clause = "ga.country_code, ga.region"
            having_clause = "ga.region IS NOT NULL AND ga.region != ''"
        else:  # city
            select_fields = [
                "ga.country_code",
                "ga.region",
                "ga.city",
                "COUNT(*) as request_count",
                success_rate_expr,
                "AVG(mi.response_time_ms) as avg_latency_ms",
                "uniqExact(ga.user_id) as unique_users",
                "any(ga.latitude) as latitude",
                "any(ga.longitude) as longitude",
            ]
            group_by_clause = "ga.country_code, ga.region, ga.city"
            having_clause = "ga.city IS NOT NULL AND ga.city != ''"

        # Build WHERE conditions (only for GatewayAnalytics table)
        where_conditions = ["ga.timestamp >= %(from_date)s", "ga.timestamp <= %(to_date)s"]

        # Build JOIN conditions for project filtering (applied in JOIN, not WHERE)
        join_conditions = ["ga.inference_id = mid.inference_id"]

        params = {
            "from_date": request.from_date,
            "to_date": request.to_date or datetime.now(),
        }

        # Add filters - project filters go in JOIN condition, others in WHERE
        if request.filters:
            for filter_key, filter_value in request.filters.items():
                if filter_key == "project_id":
                    # Move project filter to JOIN condition to preserve LEFT JOIN semantics
                    if isinstance(filter_value, list):
                        placeholders = [f"%(project_{i})s" for i in range(len(filter_value))]
                        join_conditions.append(f"mid.project_id IN ({','.join(placeholders)})")
                        for i, val in enumerate(filter_value):
                            params[f"project_{i}"] = val
                    else:
                        join_conditions.append("mid.project_id = %(project_id)s")
                        params["project_id"] = filter_value
                elif filter_key == "api_key_project_id":
                    # Support filtering by api_key_project_id for CLIENT users
                    # Move to JOIN condition to preserve LEFT JOIN semantics
                    if isinstance(filter_value, list):
                        placeholders = [f"%(api_key_project_{i})s" for i in range(len(filter_value))]
                        join_conditions.append(f"mid.api_key_project_id IN ({','.join(placeholders)})")
                        for i, val in enumerate(filter_value):
                            params[f"api_key_project_{i}"] = val
                    else:
                        join_conditions.append("mid.api_key_project_id = %(api_key_project_id)s")
                        params["api_key_project_id"] = filter_value
                elif filter_key == "country_code":
                    # Country filter stays in WHERE clause
                    if isinstance(filter_value, list):
                        placeholders = [f"%(country_{i})s" for i in range(len(filter_value))]
                        where_conditions.append(f"ga.country_code IN ({','.join(placeholders)})")
                        for i, val in enumerate(filter_value):
                            params[f"country_{i}"] = val
                    else:
                        where_conditions.append("ga.country_code = %(country_code)s")
                        params["country_code"] = filter_value

        # Build main query with JOIN conditions in the ON clause
        join_clause = " AND ".join(join_conditions)
        query = f"""
        WITH total_requests AS (
            SELECT COUNT(*) as total
            FROM GatewayAnalytics ga
            LEFT JOIN ModelInferenceDetails mid ON {join_clause}
            LEFT JOIN ModelInference mi ON mid.inference_id = mi.inference_id
            WHERE {" AND ".join(where_conditions)}
        )
        SELECT
            {", ".join(select_fields)},
            (request_count * 100.0 / NULLIF((SELECT total FROM total_requests), 0)) as percentage
        FROM GatewayAnalytics ga
        LEFT JOIN ModelInferenceDetails mid ON {join_clause}
        LEFT JOIN ModelInference mi ON mid.inference_id = mi.inference_id
        WHERE {" AND ".join(where_conditions)}
        GROUP BY {group_by_clause}
        HAVING {having_clause}
        ORDER BY request_count DESC
        LIMIT %(limit)s
        """

        params["limit"] = request.limit
        # Execute query
        results = await self.clickhouse_client.execute_query(query, params)

        # Get total count for summary (only from GatewayAnalytics, no need to join)
        total_query = f"""
        SELECT COUNT(*) as total_requests
        FROM GatewayAnalytics ga
        WHERE {" AND ".join(where_conditions)}
        """
        total_result = await self.clickhouse_client.execute_query(
            total_query, {k: v for k, v in params.items() if k != "limit"}
        )
        total_requests = total_result[0][0] if total_result else 0
        # Process results
        locations = []
        for row in results:
            if request.group_by == "country":
                location = GeographicDataPoint(
                    country_code=row[0],
                    request_count=row[1],
                    success_rate=row[2] if len(row) > 2 else 0.0,
                    avg_latency_ms=row[3] if len(row) > 3 else None,
                    unique_users=row[4] if len(row) > 4 else None,
                    latitude=row[5] if len(row) > 5 else None,
                    longitude=row[6] if len(row) > 6 else None,
                    percentage=row[7] if len(row) > 7 else 0.0,
                )
            elif request.group_by == "region":
                location = GeographicDataPoint(
                    country_code=row[0],
                    region=row[1],
                    request_count=row[2],
                    success_rate=row[3] if len(row) > 3 else 0.0,
                    avg_latency_ms=row[4] if len(row) > 4 else None,
                    unique_users=row[5] if len(row) > 5 else None,
                    percentage=row[6] if len(row) > 6 else 0.0,
                )
            else:  # city
                location = GeographicDataPoint(
                    country_code=row[0],
                    region=row[1],
                    city=row[2],
                    request_count=row[3],
                    success_rate=row[4] if len(row) > 4 else 0.0,
                    avg_latency_ms=row[5] if len(row) > 5 else None,
                    unique_users=row[6] if len(row) > 6 else None,
                    latitude=row[7] if len(row) > 7 else None,
                    longitude=row[8] if len(row) > 8 else None,
                    percentage=row[9] if len(row) > 9 else 0.0,
                )

            locations.append(location)

        return GeographicDataResponse(
            locations=locations,
            total_requests=total_requests,
            total_locations=len(locations),
            date_range={"from": request.from_date, "to": request.to_date or datetime.now()},
            group_by=request.group_by,
        )

    async def get_latency_distribution(self, request: LatencyDistributionRequest) -> LatencyDistributionResponse:
        """Get latency distribution data with optional grouping.

        This method calculates latency distribution by creating histogram buckets
        and counting requests that fall into each bucket. It supports custom buckets
        and grouping by various dimensions.

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

        # Build filters
        filter_conditions = [
            f"toDateTime('{from_date_str}') <= request_arrival_time",
            f"request_arrival_time < toDateTime('{to_date_str}')",
        ]

        if request.filters:
            if "project_id" in request.filters:
                project_ids = request.filters["project_id"]
                if isinstance(project_ids, str):
                    project_ids = [project_ids]
                project_filter = "', '".join(str(pid) for pid in project_ids)
                filter_conditions.append(f"toString(project_id) IN ('{project_filter}')")

            if "api_key_project_id" in request.filters:
                # Support filtering by api_key_project_id for CLIENT users
                api_key_project_ids = request.filters["api_key_project_id"]
                if isinstance(api_key_project_ids, str):
                    api_key_project_ids = [api_key_project_ids]
                api_key_project_filter = "', '".join(str(pid) for pid in api_key_project_ids)
                filter_conditions.append(f"toString(api_key_project_id) IN ('{api_key_project_filter}')")

            if "endpoint_id" in request.filters:
                endpoint_ids = request.filters["endpoint_id"]
                if isinstance(endpoint_ids, str):
                    endpoint_ids = [endpoint_ids]
                endpoint_filter = "', '".join(str(eid) for eid in endpoint_ids)
                filter_conditions.append(f"toString(endpoint_id) IN ('{endpoint_filter}')")

            if "model_id" in request.filters:
                model_ids = request.filters["model_id"]
                if isinstance(model_ids, str):
                    model_ids = [model_ids]
                model_filter = "', '".join(str(mid) for mid in model_ids)
                filter_conditions.append(f"toString(model_id) IN ('{model_filter}')")

        where_clause = " AND ".join(filter_conditions)

        # Calculate latency from ModelInference table's response_time_ms column
        # We need to join with ModelInference table to get the actual response time
        latency_expr = "COALESCE(mid.response_time_ms, 0)"

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

            query = f"""
                SELECT
                    {bucket_case_expr} as bucket,
                    count() as request_count,
                    avg({latency_expr}) as avg_latency_in_bucket
                FROM ModelInferenceDetails mdi
                LEFT JOIN ModelInference mid ON mid.inference_id = mdi.inference_id
                WHERE {where_clause}
                GROUP BY bucket
                ORDER BY
                    CASE bucket
                        WHEN '{buckets[0]["label"]}' THEN 1
                        WHEN '{buckets[1]["label"]}' THEN 2
                        WHEN '{buckets[2]["label"]}' THEN 3
                        WHEN '{buckets[3]["label"]}' THEN 4
                        WHEN '{buckets[4]["label"]}' THEN 5
                        WHEN '{buckets[5]["label"]}' THEN 6
                        WHEN '{buckets[6]["label"]}' THEN 7
                        ELSE 8
                    END
            """

            result = await self.clickhouse_client.execute_query(query)

            # Get total count for percentage calculation
            total_query = f"SELECT count() FROM ModelInferenceDetails mdi LEFT JOIN ModelInference mid ON mid.inference_id = mdi.inference_id WHERE {where_clause}"
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

            return LatencyDistributionResponse(
                groups=[],
                overall_distribution=overall_buckets,
                total_requests=total_requests,
                date_range={"from": request.from_date, "to": request.to_date or datetime.now()},
                bucket_definitions=buckets,
            )

        # Handle grouped queries
        groups = []
        total_requests = 0

        # Determine grouping columns and joins needed
        group_columns = []
        join_tables = []

        # Always join with ModelInference to get response_time_ms
        join_tables.append("LEFT JOIN ModelInference mid ON mid.inference_id = mdi.inference_id")

        if "model" in request.group_by:
            group_columns.extend(["toString(mdi.model_id) as model_id", "mid.model_name as model_name"])

        if "project" in request.group_by:
            # We have project_id in ModelInferenceDetails, but might need project name
            group_columns.extend(["toString(mdi.project_id) as project_id", "'Unknown' as project_name"])

        if "endpoint" in request.group_by:
            group_columns.extend(["toString(mdi.endpoint_id) as endpoint_id", "'Unknown' as endpoint_name"])

        if "user" in request.group_by:
            # User info would need additional joins - for now use project as proxy
            group_columns.extend(["toString(mdi.project_id) as user_id"])

        if "user_project" in request.group_by:
            group_columns.extend(["toString(mdi.api_key_project_id) as api_key_project_id"])

        group_by_clause = ", ".join([col.split(" as ")[1] if " as " in col else col for col in group_columns])
        select_columns = ", ".join(group_columns)

        # Build grouped query with bucket distribution
        bucket_case_expr = f"CASE {' '.join(bucket_cases)} ELSE 'Other' END"

        joins_clause = " ".join(join_tables) if join_tables else ""

        query = f"""
            WITH grouped_data AS (
                SELECT
                    {select_columns},
                    {bucket_case_expr} as bucket,
                    count() as request_count,
                    avg({latency_expr}) as avg_latency_in_bucket
                FROM ModelInferenceDetails mdi
                {joins_clause}
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

        # Get overall total for percentage calculations
        total_query = f"SELECT count() FROM ModelInferenceDetails mdi {joins_clause} WHERE {where_clause}"
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

    def _fill_time_series_gaps(self, groups: list, request) -> list:
        """Fill gaps in time series data with zero values."""
        # This is a simplified implementation - in production you'd want more sophisticated gap filling
        # For now, just return the groups as-is
        return groups

    async def get_blocking_stats(self, from_date, to_date, project_id=None, rule_id=None):
        """Get comprehensive blocking rule statistics from ClickHouse.

        Args:
            from_date: Start date for the query
            to_date: End date for the query
            project_id: Optional project filter
            rule_id: Optional specific rule filter

        Returns:
            Dictionary with blocking statistics
        """
        self._ensure_initialized()

        # Check if GatewayBlockingEvents table exists
        try:
            table_exists_query = "EXISTS TABLE GatewayBlockingEvents"
            table_exists_result = await self.clickhouse_client.execute_query(table_exists_query)
            blocking_table_exists = table_exists_result and table_exists_result[0][0] == 1
        except Exception as e:
            logger.warning(f"Failed to check GatewayBlockingEvents table existence: {e}")
            # Fallback to basic statistics from ModelInferenceDetails
            return await self._get_blocking_stats_fallback(from_date, to_date, project_id)

        if not blocking_table_exists:
            logger.info("GatewayBlockingEvents table not found, using fallback")
            return await self._get_blocking_stats_fallback(from_date, to_date, project_id)

        # Build parameters
        params = {
            "from_date": from_date,
            "to_date": to_date or datetime.now(),
        }

        # Build base where conditions
        where_conditions = ["blocked_at >= %(from_date)s", "blocked_at <= %(to_date)s"]

        if project_id:
            where_conditions.append("project_id = %(project_id)s")
            params["project_id"] = project_id

        if rule_id:
            where_conditions.append("rule_id = %(rule_id)s")
            params["rule_id"] = rule_id

        where_clause = " AND ".join(where_conditions)

        # Get total blocked count and rule breakdown
        stats_query = f"""
            SELECT
                COUNT(*) as total_blocked,
                uniqExact(rule_id) as unique_rules,
                uniqExact(client_ip) as unique_ips
            FROM GatewayBlockingEvents
            WHERE {where_clause}
        """

        stats_result = await self.clickhouse_client.execute_query(stats_query, params)
        total_blocked = stats_result[0][0] if stats_result else 0

        # Get blocks by rule type and name
        rule_breakdown_query = f"""
            SELECT
                rule_type,
                rule_name,
                rule_id,
                COUNT(*) as block_count,
                uniqExact(client_ip) as unique_ips_blocked
            FROM GatewayBlockingEvents
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

            blocked_by_rule[rule_name] = block_count
            if rule_type in blocked_by_type:
                blocked_by_type[rule_type] += block_count
            else:
                blocked_by_type[rule_type] = block_count

        # Get blocks by reason
        reason_query = f"""
            SELECT
                block_reason,
                COUNT(*) as count
            FROM GatewayBlockingEvents
            WHERE {where_clause}
            GROUP BY block_reason
            ORDER BY count DESC
        """

        reason_result = await self.clickhouse_client.execute_query(reason_query, params)
        blocked_by_reason = {row[0]: row[1] for row in reason_result}

        # Get top blocked IPs with country info
        top_ips_query = f"""
            SELECT
                client_ip,
                any(country_code) as country_code,
                COUNT(*) as block_count
            FROM GatewayBlockingEvents
            WHERE {where_clause}
            GROUP BY client_ip
            ORDER BY block_count DESC
            LIMIT 10
        """

        top_ips_result = await self.clickhouse_client.execute_query(top_ips_query, params)
        top_blocked_ips = [{"ip": row[0], "country": row[1] or "Unknown", "count": row[2]} for row in top_ips_result]

        # Get time series data (hourly buckets)
        time_series_query = f"""
            SELECT
                toStartOfHour(blocked_at) as hour,
                COUNT(*) as blocked_count
            FROM GatewayBlockingEvents
            WHERE {where_clause}
            GROUP BY hour
            ORDER BY hour
        """

        time_series_result = await self.clickhouse_client.execute_query(time_series_query, params)
        time_series = [{"timestamp": row[0].isoformat(), "blocked_count": row[1]} for row in time_series_result]

        # Calculate block rate (need total requests in same period)
        total_requests_query = f"""
            SELECT COUNT(*)
            FROM ModelInferenceDetails
            WHERE request_arrival_time >= %(from_date)s
            AND request_arrival_time <= %(to_date)s
            {"AND project_id = %(project_id)s" if project_id else ""}
        """

        try:
            total_requests_result = await self.clickhouse_client.execute_query(total_requests_query, params)
            total_requests = total_requests_result[0][0] if total_requests_result else 0
            block_rate = (total_blocked / total_requests * 100) if total_requests > 0 else 0.0
        except Exception:
            # If we can't get total requests, set block rate to 0
            block_rate = 0.0
            total_requests = 0

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
        """Get credential usage statistics from ModelInferenceDetails.

        This method queries the ModelInferenceDetails table to find the most recent
        usage for each credential (api_key_id) within the specified time window.

        Args:
            request: Request containing the time window and optional credential IDs

        Returns:
            CredentialUsageResponse with usage statistics for each credential
        """
        self._ensure_initialized()

        try:
            # Build the query to get last usage per credential
            query = """
            SELECT
                api_key_id as credential_id,
                MAX(request_arrival_time) as last_used_at,
                COUNT(*) as request_count
            FROM ModelInferenceDetails
            WHERE request_arrival_time >= %(since)s
                AND api_key_id IS NOT NULL
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

        try:
            # 1. Get credential usage data if requested
            if request.credential_sync:
                credential_usage = await self._get_sync_credential_data(
                    request.sync_mode, request.activity_threshold_minutes
                )
                stats["active_credentials"] = len(credential_usage)

            # 2. Get user usage data if requested
            if request.user_usage_sync:
                user_usage = await self._get_sync_user_data(
                    request.sync_mode, request.activity_threshold_minutes, request.user_ids
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

    async def _get_sync_credential_data(self, sync_mode: str, threshold_minutes: int) -> list[CredentialUsageItem]:
        """Get credential usage data for sync based on mode."""
        try:
            # Base query for credential usage
            query = """
            SELECT
                api_key_id as credential_id,
                MAX(request_arrival_time) as last_used_at,
                COUNT(*) as request_count
            FROM ModelInferenceDetails
            WHERE api_key_id IS NOT NULL
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
        self, sync_mode: str, threshold_minutes: int, user_ids: Optional[list[UUID]] = None
    ) -> list[UserUsageItem]:
        """Get user usage data for sync based on mode."""
        try:
            from datetime import datetime, timezone

            logger.info(f"_get_sync_user_data called: mode={sync_mode}, user_ids={len(user_ids) if user_ids else 0}")
            # Base query for user usage - need to join with ModelInference for token data
            query = """
            SELECT
                mid.user_id,
                MAX(mid.request_arrival_time) as last_activity_at,
                SUM(COALESCE(mi.input_tokens, 0) + COALESCE(mi.output_tokens, 0)) as total_tokens,
                SUM(COALESCE(mid.cost, 0)) as total_cost,
                COUNT(*) as request_count,
                AVG(CASE WHEN mid.is_success THEN 1 ELSE 0 END) as success_rate
            FROM ModelInferenceDetails mid
            LEFT JOIN ModelInference mi ON mid.inference_id = mi.inference_id
            WHERE mid.user_id IS NOT NULL
            """

            params = {}

            if sync_mode == "incremental":
                # Only users with activity within threshold
                since_time = datetime.now() - timedelta(minutes=threshold_minutes)
                query += " AND mid.request_arrival_time >= %(since)s"
                params["since"] = since_time
            # For full sync, get ALL users with any activity (no time filter, no user filter)

            query += """
            GROUP BY mid.user_id
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
