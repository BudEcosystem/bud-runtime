import asyncio
import math
from collections import defaultdict
from typing import Optional
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
    MetricsData,
    ModerationInferenceDetail,
    ObservabilityMetricsRequest,
    ObservabilityMetricsResponse,
    PerformanceMetric,
    PeriodBin,
    TimeMetric,
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
                       request_arrival_time, request_forward_time)

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
            # Unpack the tuple
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
                f"'{request_forward_time.strftime('%Y-%m-%d %H:%M:%S')}')"
            )
            values.append(row)

        # Build and execute the INSERT query
        # Safe: values are escaped using _escape_string method
        query = f"""
        INSERT INTO ModelInferenceDetails
        (inference_id, request_ip, project_id, endpoint_id, model_id,
         cost, response_analysis, is_success, request_arrival_time, request_forward_time)
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
        count_query = f"""
        SELECT COUNT(*) as total_count
        FROM ModelInference mi
        INNER JOIN ModelInferenceDetails mid ON mi.inference_id = mid.inference_id
        LEFT JOIN ChatInference ci ON mi.inference_id = ci.id
        WHERE {where_clause}
        """  # nosec B608

        # Execute count query with parameters
        count_result = await self.clickhouse_client.execute_query(count_query, params)
        total_count = count_result[0][0] if count_result else 0

        # Get paginated data
        # Safe: where_clause and order_by are validated, limit/offset use parameters
        list_query = f"""
        SELECT
            mi.inference_id,
            mi.timestamp,
            mi.model_name,
            CASE
                WHEN mi.endpoint_type = 'chat' THEN substring(coalesce(ci.input, mi.input_messages), 1, 100)
                WHEN mi.endpoint_type = 'embedding' THEN substring(ei.input, 1, 100)
                WHEN mi.endpoint_type IN ('audio_transcription', 'audio_translation', 'text_to_speech') THEN substring(ai.input, 1, 100)
                WHEN mi.endpoint_type = 'image_generation' THEN substring(ii.prompt, 1, 100)
                WHEN mi.endpoint_type = 'moderation' THEN substring(modi.input, 1, 100)
                ELSE substring(mi.input_messages, 1, 100)
            END as prompt_preview,
            CASE
                WHEN mi.endpoint_type = 'chat' THEN substring(coalesce(ci.output, mi.output), 1, 100)
                WHEN mi.endpoint_type = 'embedding' THEN concat('Generated ', toString(ei.input_count), ' embeddings')
                WHEN mi.endpoint_type IN ('audio_transcription', 'audio_translation', 'text_to_speech') THEN substring(ai.output, 1, 100)
                WHEN mi.endpoint_type = 'image_generation' THEN concat('Generated ', toString(ii.image_count), ' images')
                WHEN mi.endpoint_type = 'moderation' THEN if(modi.flagged, 'Content flagged', 'Content passed')
                ELSE substring(mi.output, 1, 100)
            END as response_preview,
            mi.input_tokens,
            mi.output_tokens,
            mi.input_tokens + mi.output_tokens as total_tokens,
            mi.response_time_ms,
            mid.cost,
            mid.is_success,
            mi.cached,
            mid.project_id,
            mid.endpoint_id,
            mid.model_id,
            coalesce(mi.endpoint_type, 'chat') as endpoint_type
        FROM ModelInference mi
        INNER JOIN ModelInferenceDetails mid ON mi.inference_id = mid.inference_id
        LEFT JOIN ChatInference ci ON mi.inference_id = ci.id AND mi.endpoint_type = 'chat'
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
                    is_success=bool(row[10]),
                    cached=bool(row[11]),
                    project_id=row[12],
                    endpoint_id=row[13],
                    model_id=row[14],
                    endpoint_type=row[15],
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
                coalesce(ci.input, mi.input_messages) as input_messages,
                coalesce(ci.output, mi.output) as output,
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
                mid.endpoint_id,
                mid.is_success,
                mi.cached,
                mi.finish_reason,
                mid.cost,
                mi.raw_request,
                mi.raw_response,
                mi.gateway_request,
                mi.gateway_response,
                coalesce(mi.endpoint_type, 'chat') as endpoint_type,
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
                ga.user_agent,
                ga.device_type,
                ga.browser_name,
                ga.browser_version,
                ga.os_name,
                ga.os_version,
                ga.is_bot,
                ga.method,
                ga.path,
                ga.query_params,
                ga.request_headers,
                ga.body_size,
                ga.api_key_id,
                ga.auth_method,
                ga.user_id,
                ga.gateway_processing_ms,
                ga.total_duration_ms,
                ga.routing_decision,
                ga.model_version,
                ga.status_code,
                ga.response_size,
                ga.response_headers,
                ga.error_type,
                ga.error_message,
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
                coalesce(ci.input, mi.input_messages) as input_messages,
                coalesce(ci.output, mi.output) as output,
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
                mid.endpoint_id,
                mid.is_success,
                mi.cached,
                mi.finish_reason,
                mid.cost,
                mi.raw_request,
                mi.raw_response,
                mi.gateway_request,
                mi.gateway_response,
                coalesce(mi.endpoint_type, 'chat') as endpoint_type
            FROM ModelInference mi
            INNER JOIN ModelInferenceDetails mid ON mi.inference_id = mid.inference_id
            LEFT JOIN ChatInference ci ON mi.inference_id = ci.id
            WHERE mi.inference_id = %(inference_id)s
            """

        params = {"inference_id": inference_id}
        results = await self.clickhouse_client.execute_query(query, params)

        if not results:
            raise ValueError("Inference not found")

        row = results[0]

        # Extract gateway metadata based on whether table exists and data is available
        gateway_metadata = None
        if gateway_table_exists:
            # With GatewayAnalytics table, endpoint_type is at index 29 and gateway fields start at 30
            endpoint_type = row[29] if len(row) > 29 else "chat"

            logger.debug(f"Row length: {len(row)}, checking gateway fields from index 30")

            if len(row) > 30:
                # Check if any gateway fields are present (not all None/empty)
                gateway_fields = row[30:69] if len(row) >= 69 else row[30:]
                has_gateway_data = any(field is not None and field != "" for field in gateway_fields)

                logger.debug(f"Gateway fields present: {has_gateway_data}")
                logger.debug(
                    f"Sample gateway fields: client_ip={row[30] if len(row) > 30 else None}, "
                    f"country_code={row[33] if len(row) > 33 else None}, "
                    f"user_agent={row[41] if len(row) > 41 else None}"
                )

                if has_gateway_data:
                    try:
                        # Parse headers and tags if they exist
                        request_headers = None
                        if len(row) > 51 and row[51]:
                            try:
                                request_headers = dict(row[51]) if isinstance(row[51], (dict, tuple)) else None
                            except (TypeError, ValueError):
                                request_headers = None

                        response_headers = None
                        if len(row) > 62 and row[62]:
                            try:
                                response_headers = dict(row[62]) if isinstance(row[62], (dict, tuple)) else None
                            except (TypeError, ValueError):
                                response_headers = None

                        tags = None
                        if len(row) > 68 and row[68]:
                            try:
                                tags = dict(row[68]) if isinstance(row[68], (dict, tuple)) else None
                            except (TypeError, ValueError):
                                tags = None

                        gateway_metadata = GatewayMetadata(
                            client_ip=row[30] if len(row) > 30 and row[30] else None,
                            proxy_chain=row[31] if len(row) > 31 and row[31] else None,
                            protocol_version=row[32] if len(row) > 32 and row[32] else None,
                            country_code=row[33] if len(row) > 33 and row[33] else None,
                            region=row[34] if len(row) > 34 and row[34] else None,
                            city=row[35] if len(row) > 35 and row[35] else None,
                            latitude=row[36] if len(row) > 36 and row[36] is not None else None,
                            longitude=row[37] if len(row) > 37 and row[37] is not None else None,
                            timezone=row[38] if len(row) > 38 and row[38] else None,
                            asn=row[39] if len(row) > 39 and row[39] is not None else None,
                            isp=row[40] if len(row) > 40 and row[40] else None,
                            user_agent=row[41] if len(row) > 41 and row[41] else None,
                            device_type=row[42] if len(row) > 42 and row[42] else None,
                            browser_name=row[43] if len(row) > 43 and row[43] else None,
                            browser_version=row[44] if len(row) > 44 and row[44] else None,
                            os_name=row[45] if len(row) > 45 and row[45] else None,
                            os_version=row[46] if len(row) > 46 and row[46] else None,
                            is_bot=row[47] if len(row) > 47 and row[47] is not None else None,
                            method=row[48] if len(row) > 48 and row[48] else None,
                            path=row[49] if len(row) > 49 and row[49] else None,
                            query_params=row[50] if len(row) > 50 and row[50] else None,
                            request_headers=request_headers,
                            body_size=row[52] if len(row) > 52 and row[52] is not None else None,
                            api_key_id=row[53] if len(row) > 53 and row[53] else None,
                            auth_method=row[54] if len(row) > 54 and row[54] else None,
                            user_id=row[55] if len(row) > 55 and row[55] else None,
                            gateway_processing_ms=row[56] if len(row) > 56 and row[56] is not None else None,
                            total_duration_ms=row[57] if len(row) > 57 and row[57] is not None else None,
                            routing_decision=row[58] if len(row) > 58 and row[58] else None,
                            model_version=row[59] if len(row) > 59 and row[59] else None,
                            status_code=row[60] if len(row) > 60 and row[60] is not None else None,
                            response_size=row[61] if len(row) > 61 and row[61] is not None else None,
                            response_headers=response_headers,
                            error_type=row[63] if len(row) > 63 and row[63] else None,
                            error_message=row[64] if len(row) > 64 and row[64] else None,
                            is_blocked=row[65] if len(row) > 65 and row[65] is not None else None,
                            block_reason=row[66] if len(row) > 66 and row[66] else None,
                            block_rule_id=row[67] if len(row) > 67 and row[67] else None,
                            tags=tags,
                        )
                        logger.info(f"Successfully parsed gateway metadata for inference {inference_id}")
                    except (IndexError, TypeError) as e:
                        logger.warning(f"Failed to parse gateway metadata for inference {inference_id}: {e}")
                        gateway_metadata = None
                else:
                    logger.debug(f"No gateway data found for inference {inference_id}")
            else:
                logger.warning(f"Row too short for gateway data: {len(row)} columns")
        else:
            # Without GatewayAnalytics table, endpoint_type is at the last index
            endpoint_type = row[-1] if len(row) > 0 else "chat"
            logger.info("GatewayAnalytics table not available, gateway_metadata will be null")

        # Parse messages from JSON string
        import json

        try:
            if row[6]:
                if isinstance(row[6], str):
                    parsed_data = json.loads(row[6])
                    # Handle the case where the JSON contains {"messages": [...]}
                    if isinstance(parsed_data, dict) and "messages" in parsed_data:
                        messages = parsed_data["messages"]
                    elif isinstance(parsed_data, list):
                        messages = parsed_data
                    else:
                        messages = []
                elif isinstance(row[6], list):
                    messages = row[6]
                else:
                    messages = []
            else:
                messages = []
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Failed to parse messages for inference {inference_id}: {e}")
            # Try to parse as a simple message format
            messages = [{"role": "user", "content": row[6]}] if row[6] and isinstance(row[6], str) else []

        # Skip feedback queries for now
        feedback_count = 0
        average_rating = None

        # Combine system prompt with messages if it exists
        combined_messages = []
        if row[5]:  # system_prompt exists
            combined_messages.append({"role": "system", "content": str(row[5])})

        # Add the parsed messages
        combined_messages.extend(messages)

        # Add the assistant's response as the last message
        if row[7]:  # output exists
            try:
                # Try to parse the output as JSON if it's a JSON string
                output_content = json.loads(row[7])
                # Keep the parsed JSON content as is
                content = output_content
            except (json.JSONDecodeError, TypeError):
                # If it's not JSON or parsing fails, use as is
                content = str(row[7])

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
            episode_id = safe_uuid(row[10])

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
                inference_id=safe_uuid(row[0]),  # Keep as UUID
                timestamp=row[1],
                model_name=str(row[2]) if row[2] else "",
                model_provider=str(row[3]) if row[3] else "unknown",
                model_id=safe_uuid(row[4]),  # Keep as UUID
                system_prompt=str(row[5]) if row[5] else None,  # Keep for backward compatibility
                messages=combined_messages,  # Now includes system, user, and assistant messages
                output=str(row[7]) if row[7] else "",  # Keep for backward compatibility
                function_name=str(row[8]) if row[8] else None,
                variant_name=str(row[9]) if row[9] else None,
                episode_id=episode_id,
                input_tokens=int(row[11]) if row[11] else 0,
                output_tokens=int(row[12]) if row[12] else 0,
                response_time_ms=int(row[13]) if row[13] else 0,
                ttft_ms=int(row[14]) if row[14] else None,
                processing_time_ms=int(row[15]) if row[15] else None,
                request_ip=str(row[16]) if row[16] else None,
                request_arrival_time=row[17],
                request_forward_time=row[18],
                project_id=safe_uuid(row[19]),  # Keep as UUID
                endpoint_id=safe_uuid(row[20]),  # Keep as UUID
                is_success=bool(row[21]) if row[21] is not None else True,
                cached=bool(row[22]) if row[22] is not None else False,
                finish_reason=str(row[23]) if row[23] else None,
                cost=float(row[24]) if row[24] else None,
                raw_request=str(row[25]) if row[25] else None,
                raw_response=str(row[26]) if row[26] else None,
                gateway_request=str(row[27]) if row[27] else None,
                gateway_response=str(row[28]) if row[28] else None,
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
            logger.error(f"Row data: {row}")
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

    async def get_blocking_stats(self, from_date, to_date, project_id):
        """Get blocking rule statistics."""
        self._ensure_initialized()

        # Build and execute blocking stats query
        query = self._build_blocking_stats_query(from_date, to_date, project_id)
        result = await self._clickhouse_client.execute_query(query)

        # Process results
        total_blocked = 0
        blocked_by_rule = {}

        if result:
            for row in result:
                total_blocked += row[1]
                blocked_by_rule[row[0]] = row[1]

        # Get total requests for block rate calculation
        total_query = self._build_total_requests_query(from_date, to_date, project_id)
        total_result = await self._clickhouse_client.execute_query(total_query)
        total_requests = total_result[0][0] if total_result else 0

        block_rate = (total_blocked / total_requests * 100) if total_requests > 0 else 0

        from budmetrics.observability.schemas import GatewayBlockingRuleStats

        return GatewayBlockingRuleStats(
            total_blocked=total_blocked,
            block_rate=block_rate,
            blocked_by_rule=blocked_by_rule,
            blocked_by_reason={},
            top_blocked_ips=[],
            time_series=[],
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
