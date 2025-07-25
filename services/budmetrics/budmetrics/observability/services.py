import asyncio
import math
from typing import Optional
from uuid import UUID
from collections import defaultdict

from budmicroframe.commons import logging
from budmetrics.commons.config import app_settings, secrets_settings
from budmetrics.commons.profiling_utils import PerformanceMetrics, profile_sync
from budmetrics.observability.models import (
    ClickHouseClient,
    ClickHouseConfig,
    QueryBuilder,
)
from budmetrics.observability.schemas import (
    CacheMetric,
    CountMetric,
    MetricsData,
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
            self.clickhouse_client_config.enable_query_cache = (
                app_settings.clickhouse_enable_query_cache
            )
            self.clickhouse_client_config.enable_connection_warmup = (
                app_settings.clickhouse_enable_connection_warmup
            )
            self._clickhouse_client = ClickHouseClient(self.clickhouse_client_config)
            # Performance metrics are only available in debug mode
            self._performance_metrics = self._clickhouse_client.performance_metrics
            self._query_builder = QueryBuilder(self._performance_metrics)

    @property
    def clickhouse_client(self):
        self._ensure_initialized()
        return self._clickhouse_client

    @property
    def query_builder(self):
        self._ensure_initialized()
        return self._query_builder

    @property
    def performance_metrics(self):
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
            processors[metric_name] = (
                lambda row, indices, delta_map, percent_map, cfg=config: (
                    self._process_count_metric(
                        row, indices, delta_map, percent_map, cfg
                    )
                )
            )

        # Add time metric processors
        for metric_name, config in time_metric_configs.items():
            processors[metric_name] = (
                lambda row, indices, delta_map, percent_map, cfg=config: (
                    self._process_time_metric(row, indices, delta_map, percent_map, cfg)
                )
            )

        # Add performance metric processors
        for metric_name, config in performance_metric_configs.items():
            processors[metric_name] = (
                lambda row, indices, delta_map, percent_map, cfg=config: (
                    self._process_performance_metric(
                        row, indices, delta_map, percent_map, cfg
                    )
                )
            )

        # Add cache metric processors
        for metric_name, config in cache_metric_configs.items():
            processors[metric_name] = (
                lambda row, indices, delta_map, percent_map, cfg=config: (
                    self._process_cache_metric(
                        row, indices, delta_map, percent_map, cfg
                    )
                )
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
                metric_obj.delta_percent = self._sanitize_delta_percent(
                    row[percent_idx]
                )

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
                metric_obj.delta_percent = self._sanitize_delta_percent(
                    row[percent_idx]
                )

        return config["output_key"], metric_obj

    def _process_performance_metric(
        self, row, field_indices, delta_map, percent_map, config
    ):
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
                metric_obj.delta_percent = self._sanitize_delta_percent(
                    row[percent_idx]
                )

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
                metric_obj.delta_percent = self._sanitize_delta_percent(
                    row[percent_idx]
                )

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
                for group_field, idx in group_field_indices.items():
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

    async def get_metrics(
        self, request: ObservabilityMetricsRequest
    ) -> ObservabilityMetricsResponse:
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
            raise RuntimeError(f"Failed to execute metrics query: {str(e)}") from e

        # Process results
        period_bins = self._process_query_results(
            results, field_order, request.metrics, request.group_by
        )

        # Return response
        return ObservabilityMetricsResponse(
            object="observability_metrics", items=period_bins
        )

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
        existing_check_query = f"""
        SELECT inference_id 
        FROM ModelInferenceDetails 
        WHERE inference_id IN ({','.join([f"'{id}'" for id in inference_ids])})
        """

        existing_records = await self.clickhouse_client.execute_query(
            existing_check_query
        )
        existing_ids = (
            {str(row[0]) for row in existing_records} if existing_records else set()
        )

        # Filter out records with existing inference_ids
        new_records = [
            record for record in batch_data if str(record[0]) not in existing_ids
        ]
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
            logger.info(
                f"Filtered out {len(batch_data) - len(new_records)} duplicate records"
            )

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
        query = f"""
        INSERT INTO ModelInferenceDetails
        (inference_id, request_ip, project_id, endpoint_id, model_id,
         cost, response_analysis, is_success, request_arrival_time, request_forward_time)
        VALUES {",".join(values)}
        """

        await self.clickhouse_client.execute_query(query)
        logger.info(f"Successfully inserted {len(new_records)} new records")

        return {
            "total_records": len(batch_data),
            "inserted": len(new_records),
            "duplicates": len(duplicate_ids),
            "duplicate_ids": duplicate_ids,
        }
