#!/usr/bin/env python3
"""ClickHouse migration script for bud-serve-metrics.

Run this script to create required tables in ClickHouse.
"""

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path


# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from budmicroframe.commons import logging

from budmetrics.observability.models import ClickHouseClient, ClickHouseConfig


logger = logging.get_logger(__name__)


def get_cluster_metrics_ttl_days(default: int = 30) -> int:
    """Get TTL in days for cluster metrics from environment variable.

    Args:
        default: Default TTL in days if env var is not set or invalid

    Returns:
        TTL value in days
    """
    try:
        return int(os.getenv("CLICKHOUSE_TTL_CLUSTER_METRICS", default))
    except ValueError:
        logger.warning(f"Invalid CLICKHOUSE_TTL_CLUSTER_METRICS value, using default: {default} days")
        return default


def get_clickhouse_config() -> ClickHouseConfig:
    """Get ClickHouse configuration from environment variables."""
    # Check required environment variables
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

    # Log connection info (without password)
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


class ClickHouseMigration:
    def __init__(self, include_model_inference: bool = False, max_retries: int = 30, retry_delay: int = 2):
        """Initialize the ClickHouse migration.

        Args:
            include_model_inference: Whether to include ModelInference table creation
            max_retries: Maximum number of connection retries
            retry_delay: Delay between retries in seconds
        """
        self.include_model_inference = include_model_inference
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.config = get_clickhouse_config()
        self.client = ClickHouseClient(self.config)

    async def wait_for_clickhouse(self):
        """Wait for ClickHouse to be ready with retry mechanism."""
        logger.info("Waiting for ClickHouse to be ready...")

        for attempt in range(self.max_retries):
            try:
                # Try to initialize the client
                await self.client.initialize()

                # Test connection by running a simple query
                result = await self.client.execute_query("SELECT 1")
                if result and result[0][0] == 1:
                    logger.info("ClickHouse is ready!")
                    return True

            except Exception as e:
                if attempt < self.max_retries - 1:
                    logger.warning(f"ClickHouse not ready yet (attempt {attempt + 1}/{self.max_retries}): {e}")
                    logger.info(f"Retrying in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)

                    # Close the client to reset connection
                    try:
                        await self.client.close()
                    except Exception as close_exc:
                        logger.warning(f"Failed to close ClickHouse client during retry: {close_exc}")
                else:
                    logger.error(f"ClickHouse failed to become ready after {self.max_retries} attempts")
                    raise Exception(f"ClickHouse connection failed: {e}") from e

        return False

    async def initialize(self):
        """Initialize the ClickHouse client with retry mechanism."""
        if not await self.wait_for_clickhouse():
            raise Exception("Failed to connect to ClickHouse")
        logger.info("ClickHouse client initialized")

    async def create_database(self):
        """Create database if it doesn't exist."""
        try:
            await self.client.execute_query(f"CREATE DATABASE IF NOT EXISTS {self.config.database}")
            logger.info(f"Database '{self.config.database}' created or already exists")
        except Exception as e:
            logger.error(f"Error creating database: {e}")
            raise

    async def create_model_inference_table(self):
        """Create ModelInference table (optional)."""
        if not self.include_model_inference:
            logger.info("Skipping ModelInference table creation (use --include-model-inference to create)")
            return

        query = """
        CREATE TABLE IF NOT EXISTS ModelInference
        (
            id UUID,
            inference_id UUID,
            raw_request String,
            raw_response String,
            model_name LowCardinality(String),
            model_provider_name LowCardinality(String),
            input_tokens Nullable(UInt32),
            output_tokens Nullable(UInt32),
            response_time_ms Nullable(UInt32),
            ttft_ms Nullable(UInt32),
            timestamp DateTime MATERIALIZED UUIDv7ToDateTime(id),
            system Nullable(String),
            input_messages String,
            output String,
            cached Bool DEFAULT false,
            finish_reason Nullable(Enum8('stop' = 1, 'length' = 2, 'tool_call' = 3, 'content_filter' = 4, 'unknown' = 5)),
            endpoint_type LowCardinality(String) DEFAULT 'chat'
        )
        ENGINE = MergeTree()
        PARTITION BY toYYYYMM(timestamp)
        ORDER BY (model_name, timestamp, inference_id)
        SETTINGS index_granularity = 8192
        """

        try:
            await self.client.execute_query(query)
            logger.info("ModelInference table created successfully")

            # Create indexes
            indexes = [
                "ALTER TABLE ModelInference ADD INDEX IF NOT EXISTS idx_inference_id (inference_id) TYPE minmax GRANULARITY 1",
                "ALTER TABLE ModelInference ADD INDEX IF NOT EXISTS idx_model_timestamp (model_name, timestamp) TYPE minmax GRANULARITY 1",
            ]

            for index_query in indexes:
                try:
                    await self.client.execute_query(index_query)
                except Exception as e:
                    if "already exists" not in str(e):
                        logger.warning(f"Index creation warning: {e}")

        except Exception as e:
            logger.error(f"Error creating ModelInference table: {e}")
            raise

    async def create_model_inference_details_table(self):
        """Create ModelInferenceDetails table."""
        # Note: ClickHouse doesn't support UNIQUE constraints
        # Uniqueness should be handled at the application level or by using ReplacingMergeTree
        query = """
        CREATE TABLE IF NOT EXISTS ModelInferenceDetails
        (
            inference_id UUID,
            request_ip Nullable(IPv4),
            project_id UUID,
            endpoint_id UUID,
            model_id UUID,
            cost Nullable(Float64),
            response_analysis Nullable(JSON),
            is_success Bool,
            request_arrival_time DateTime,
            request_forward_time DateTime,
            api_key_id Nullable(UUID),
            user_id Nullable(UUID),
            api_key_project_id Nullable(UUID),
            error_code Nullable(String),
            error_message Nullable(String),
            error_type Nullable(String),
            status_code Nullable(UInt16),
            created_at DateTime DEFAULT now()
        )
        ENGINE = MergeTree()
        PARTITION BY toYYYYMM(request_arrival_time)
        ORDER BY (project_id, model_id, endpoint_id, request_arrival_time, inference_id)
        SETTINGS index_granularity = 8192
        """

        try:
            await self.client.execute_query(query)
            logger.info("ModelInferenceDetails table created successfully")

            # Create indexes
            indexes = [
                "ALTER TABLE ModelInferenceDetails ADD INDEX IF NOT EXISTS idx_project_timestamp (project_id, request_arrival_time) TYPE minmax GRANULARITY 1",
                "ALTER TABLE ModelInferenceDetails ADD INDEX IF NOT EXISTS idx_model_timestamp (model_id, request_arrival_time) TYPE minmax GRANULARITY 1",
                "ALTER TABLE ModelInferenceDetails ADD INDEX IF NOT EXISTS idx_endpoint_timestamp (endpoint_id, request_arrival_time) TYPE minmax GRANULARITY 1",
                "ALTER TABLE ModelInferenceDetails ADD INDEX IF NOT EXISTS idx_project_model_endpoint_timestamp (project_id, model_id, endpoint_id, request_arrival_time) TYPE minmax GRANULARITY 1",
                "ALTER TABLE ModelInferenceDetails ADD INDEX IF NOT EXISTS idx_api_key_id (api_key_id) TYPE minmax GRANULARITY 1",
                "ALTER TABLE ModelInferenceDetails ADD INDEX IF NOT EXISTS idx_user_id (user_id) TYPE minmax GRANULARITY 1",
                "ALTER TABLE ModelInferenceDetails ADD INDEX IF NOT EXISTS idx_api_key_project_id (api_key_project_id) TYPE minmax GRANULARITY 1",
                "ALTER TABLE ModelInferenceDetails ADD INDEX IF NOT EXISTS idx_error_type (error_type) TYPE minmax GRANULARITY 1",
                "ALTER TABLE ModelInferenceDetails ADD INDEX IF NOT EXISTS idx_status_code (status_code) TYPE minmax GRANULARITY 1",
            ]

            for index_query in indexes:
                try:
                    await self.client.execute_query(index_query)
                except Exception as e:
                    if "already exists" not in str(e):
                        logger.warning(f"Index creation warning: {e}")

        except Exception as e:
            logger.error(f"Error creating ModelInferenceDetails table: {e}")
            raise

    async def create_embedding_inference_table(self):
        """Create EmbeddingInference table."""
        query = """
        CREATE TABLE IF NOT EXISTS EmbeddingInference
        (
            id UUID,
            function_name LowCardinality(String),
            variant_name LowCardinality(String),
            episode_id Nullable(UUID),
            embeddings Array(Array(Float32)),
            embedding_dimensions UInt32,
            input_count UInt32,
            input String,
            processing_time_ms Nullable(UInt32),
            tags Map(String, String),
            extra_body String,
            timestamp DateTime DEFAULT now()
        )
        ENGINE = MergeTree()
        PARTITION BY toYYYYMM(timestamp)
        ORDER BY (function_name, timestamp, id)
        SETTINGS index_granularity = 8192
        """

        try:
            await self.client.execute_query(query)
            logger.info("EmbeddingInference table created successfully")
        except Exception as e:
            logger.error(f"Error creating EmbeddingInference table: {e}")
            raise

    async def create_audio_inference_table(self):
        """Create AudioInference table."""
        query = """
        CREATE TABLE IF NOT EXISTS AudioInference
        (
            id UUID,
            function_name LowCardinality(String),
            variant_name LowCardinality(String),
            episode_id Nullable(UUID),
            audio_type Enum8('transcription' = 1, 'translation' = 2, 'text_to_speech' = 3),
            input String,
            output String,
            language Nullable(String),
            duration_seconds Nullable(Float32),
            file_size_bytes Nullable(UInt64),
            response_format Nullable(String),
            inference_params String,
            processing_time_ms Nullable(UInt32),
            tags Map(String, String),
            extra_body String,
            timestamp DateTime DEFAULT now()
        )
        ENGINE = MergeTree()
        PARTITION BY toYYYYMM(timestamp)
        ORDER BY (function_name, audio_type, timestamp, id)
        SETTINGS index_granularity = 8192
        """

        try:
            await self.client.execute_query(query)
            logger.info("AudioInference table created successfully")
        except Exception as e:
            logger.error(f"Error creating AudioInference table: {e}")
            raise

    async def create_image_inference_table(self):
        """Create ImageInference table."""
        query = """
        CREATE TABLE IF NOT EXISTS ImageInference
        (
            id UUID,
            function_name LowCardinality(String),
            variant_name LowCardinality(String),
            episode_id Nullable(UUID),
            prompt String,
            image_count UInt8,
            size LowCardinality(String),
            quality LowCardinality(String),
            style LowCardinality(Nullable(String)),
            images String,
            inference_params String,
            processing_time_ms Nullable(UInt32),
            tags Map(String, String),
            extra_body String,
            timestamp DateTime DEFAULT now()
        )
        ENGINE = MergeTree()
        PARTITION BY toYYYYMM(timestamp)
        ORDER BY (function_name, timestamp, id)
        SETTINGS index_granularity = 8192
        """

        try:
            await self.client.execute_query(query)
            logger.info("ImageInference table created successfully")
        except Exception as e:
            logger.error(f"Error creating ImageInference table: {e}")
            raise

    async def create_moderation_inference_table(self):
        """Create ModerationInference table."""
        query = """
        CREATE TABLE IF NOT EXISTS ModerationInference
        (
            id UUID,
            function_name LowCardinality(String),
            variant_name LowCardinality(String),
            episode_id Nullable(UUID),
            input String,
            results String,
            flagged Bool,
            categories Map(String, Bool),
            category_scores Map(String, Float32),
            processing_time_ms Nullable(UInt32),
            tags Map(String, String),
            extra_body String,
            timestamp DateTime DEFAULT now()
        )
        ENGINE = MergeTree()
        PARTITION BY toYYYYMM(timestamp)
        ORDER BY (function_name, flagged, timestamp, id)
        SETTINGS index_granularity = 8192
        """

        try:
            await self.client.execute_query(query)
            logger.info("ModerationInference table created successfully")
        except Exception as e:
            logger.error(f"Error creating ModerationInference table: {e}")
            raise

    async def create_gateway_analytics_table(self):
        """Create GatewayAnalytics table for API gateway request analytics."""
        query = """
        CREATE TABLE IF NOT EXISTS GatewayAnalytics
        (
            -- Core identifiers
            id UUID,                           -- UUIDv7 for analytics record
            inference_id Nullable(UUID),       -- Associated inference if applicable

            -- Network metadata
            client_ip String,
            proxy_chain Nullable(String),      -- X-Forwarded-For chain
            protocol_version LowCardinality(String),

            -- Geographical data (from GeoIP lookup)
            country_code Nullable(String),
            region Nullable(String),
            city Nullable(String),
            latitude Nullable(Float32),
            longitude Nullable(Float32),
            timezone Nullable(String),
            asn Nullable(UInt32),              -- Autonomous System Number
            isp Nullable(String),              -- Internet Service Provider

            -- Client metadata
            user_agent Nullable(String),
            device_type LowCardinality(Nullable(String)),
            browser_name LowCardinality(Nullable(String)),
            browser_version Nullable(String),
            os_name LowCardinality(Nullable(String)),
            os_version Nullable(String),
            is_bot Bool DEFAULT false,

            -- Request context
            method LowCardinality(String),
            path String,
            query_params Nullable(String),
            request_headers Map(String, String),
            body_size Nullable(UInt32),

            -- Authentication context
            api_key_id Nullable(String),       -- Hashed/masked API key
            auth_method LowCardinality(Nullable(String)),
            user_id Nullable(String),
            project_id Nullable(UUID),
            endpoint_id Nullable(UUID),

            -- Performance metrics
            request_timestamp DateTime64(3),
            response_timestamp DateTime64(3),
            gateway_processing_ms UInt32,
            total_duration_ms UInt32,

            -- Model routing information
            model_name LowCardinality(Nullable(String)),
            model_provider LowCardinality(Nullable(String)),
            model_version Nullable(String),
            routing_decision LowCardinality(Nullable(String)),

            -- Response metadata
            status_code UInt16,
            response_size Nullable(UInt32),
            response_headers Map(String, String),
            error_type LowCardinality(Nullable(String)),
            error_message Nullable(String),

            -- Blocking information
            is_blocked Bool DEFAULT false,
            block_reason Nullable(String),
            block_rule_id Nullable(String),

            -- Custom tags
            tags Map(String, String),

            -- Materialized columns
            timestamp DateTime MATERIALIZED toDateTime(request_timestamp),
            date Date MATERIALIZED toDate(request_timestamp),
            hour DateTime MATERIALIZED toStartOfHour(request_timestamp)
        )
        ENGINE = MergeTree()
        PARTITION BY toYYYYMM(request_timestamp)
        ORDER BY (timestamp, id)
        TTL toDateTime(request_timestamp) + INTERVAL 90 DAY
        SETTINGS index_granularity = 8192
        """

        try:
            await self.client.execute_query(query)
            logger.info("GatewayAnalytics table created successfully")

            # Create indexes
            indexes = [
                "ALTER TABLE GatewayAnalytics ADD INDEX IF NOT EXISTS idx_inference_id (inference_id) TYPE minmax GRANULARITY 1",
                "ALTER TABLE GatewayAnalytics ADD INDEX IF NOT EXISTS idx_model_name (model_name) TYPE set(100) GRANULARITY 4",
                "ALTER TABLE GatewayAnalytics ADD INDEX IF NOT EXISTS idx_country_code (country_code) TYPE set(300) GRANULARITY 4",
                "ALTER TABLE GatewayAnalytics ADD INDEX IF NOT EXISTS idx_status_code (status_code) TYPE set(20) GRANULARITY 4",
                "ALTER TABLE GatewayAnalytics ADD INDEX IF NOT EXISTS idx_is_blocked (is_blocked) TYPE minmax GRANULARITY 1",
                "ALTER TABLE GatewayAnalytics ADD INDEX IF NOT EXISTS idx_endpoint_id (endpoint_id) TYPE bloom_filter(0.01) GRANULARITY 4",
                "ALTER TABLE GatewayAnalytics ADD INDEX IF NOT EXISTS idx_client_ip (client_ip) TYPE bloom_filter(0.01) GRANULARITY 8",
            ]

            for index_query in indexes:
                try:
                    await self.client.execute_query(index_query)
                except Exception as e:
                    if "already exists" not in str(e):
                        logger.warning(f"Index creation warning: {e}")

        except Exception as e:
            logger.error(f"Error creating GatewayAnalytics table: {e}")
            raise

    async def create_gateway_blocking_events_table(self):
        """Create GatewayBlockingEvents table for tracking blocked requests."""
        query = """
        CREATE TABLE IF NOT EXISTS GatewayBlockingEvents
        (
            -- Event identifiers
            id UUID,                           -- UUIDv7 for event record
            rule_id UUID,                      -- Blocking rule that triggered the block

            -- Client information
            client_ip String,
            country_code Nullable(String),
            user_agent Nullable(String),

            -- Request context
            request_path String,
            request_method LowCardinality(String),
            api_key_id Nullable(String),       -- Hashed/masked API key if available

            -- Project/endpoint context (optional)
            project_id Nullable(UUID),
            endpoint_id Nullable(UUID),
            model_name LowCardinality(Nullable(String)),

            -- Rule information
            rule_type LowCardinality(String),  -- IP_BLOCKING, COUNTRY_BLOCKING, etc.
            rule_name String,
            rule_priority Int32,

            -- Block details
            block_reason String,
            action_taken LowCardinality(String), -- BLOCK, RATE_LIMIT, etc.

            -- Timing
            blocked_at DateTime64(3),          -- When the block occurred

            -- Materialized columns for efficient querying
            timestamp DateTime MATERIALIZED toDateTime(blocked_at),
            date Date MATERIALIZED toDate(blocked_at),
            hour DateTime MATERIALIZED toStartOfHour(blocked_at)
        )
        ENGINE = MergeTree()
        PARTITION BY toYYYYMM(blocked_at)
        ORDER BY (rule_id, blocked_at, id)
        TTL toDateTime(blocked_at) + INTERVAL 90 DAY
        SETTINGS index_granularity = 8192
        """

        try:
            await self.client.execute_query(query)
            logger.info("GatewayBlockingEvents table created successfully")

            # Create indexes for efficient queries
            indexes = [
                "ALTER TABLE GatewayBlockingEvents ADD INDEX IF NOT EXISTS idx_rule_timestamp (rule_id, blocked_at) TYPE minmax GRANULARITY 1",
                "ALTER TABLE GatewayBlockingEvents ADD INDEX IF NOT EXISTS idx_client_ip (client_ip) TYPE bloom_filter(0.01) GRANULARITY 8",
                "ALTER TABLE GatewayBlockingEvents ADD INDEX IF NOT EXISTS idx_country_code (country_code) TYPE set(300) GRANULARITY 4",
                "ALTER TABLE GatewayBlockingEvents ADD INDEX IF NOT EXISTS idx_rule_type (rule_type) TYPE set(10) GRANULARITY 4",
                "ALTER TABLE GatewayBlockingEvents ADD INDEX IF NOT EXISTS idx_project_timestamp (project_id, blocked_at) TYPE minmax GRANULARITY 1",
                "ALTER TABLE GatewayBlockingEvents ADD INDEX IF NOT EXISTS idx_endpoint_timestamp (endpoint_id, blocked_at) TYPE minmax GRANULARITY 1",
            ]

            for index_query in indexes:
                try:
                    await self.client.execute_query(index_query)
                except Exception as e:
                    if "already exists" not in str(e):
                        logger.warning(f"Index creation warning: {e}")

        except Exception as e:
            logger.error(f"Error creating GatewayBlockingEvents table: {e}")
            raise

    async def add_auth_metadata_columns(self):
        """Add authentication metadata columns to existing ModelInferenceDetails table.

        This migration adds api_key_id, user_id, and api_key_project_id columns
        for tracking API usage in existing deployments.
        """
        logger.info("Adding authentication metadata columns to ModelInferenceDetails table...")

        # Check if the table exists first
        try:
            table_exists = await self.client.execute_query("EXISTS TABLE ModelInferenceDetails")
            if not table_exists or not table_exists[0][0]:
                logger.warning("ModelInferenceDetails table does not exist. Creating it first...")
                await self.create_model_inference_details_table()
                logger.info("ModelInferenceDetails table created with auth metadata columns included")
                return
        except Exception as e:
            logger.error(f"Error checking if ModelInferenceDetails table exists: {e}")
            raise

        # Check which columns already exist
        existing_columns_query = """
        SELECT name FROM system.columns
        WHERE database = currentDatabase()
        AND table = 'ModelInferenceDetails'
        AND name IN ('api_key_id', 'user_id', 'api_key_project_id')
        """

        try:
            existing_columns_result = await self.client.execute_query(existing_columns_query)
            existing_columns = {row[0] for row in existing_columns_result} if existing_columns_result else set()

            columns_to_add = []
            if "api_key_id" not in existing_columns:
                columns_to_add.append("ADD COLUMN IF NOT EXISTS api_key_id Nullable(UUID)")
            if "user_id" not in existing_columns:
                columns_to_add.append("ADD COLUMN IF NOT EXISTS user_id Nullable(UUID)")
            if "api_key_project_id" not in existing_columns:
                columns_to_add.append("ADD COLUMN IF NOT EXISTS api_key_project_id Nullable(UUID)")

            if columns_to_add:
                # Add the columns
                alter_query = f"ALTER TABLE ModelInferenceDetails {', '.join(columns_to_add)}"
                await self.client.execute_query(alter_query)
                logger.info(f"Added columns: {', '.join(col.split()[-1] for col in columns_to_add)}")
            else:
                logger.info("All authentication metadata columns already exist")

            # Add indexes for the new columns (if they don't exist)
            indexes = [
                ("idx_api_key_id", "api_key_id", "minmax", 1),
                ("idx_user_id", "user_id", "minmax", 1),
                ("idx_api_key_project_id", "api_key_project_id", "minmax", 1),
            ]

            for index_name, column, index_type, granularity in indexes:
                index_query = f"ALTER TABLE ModelInferenceDetails ADD INDEX IF NOT EXISTS {index_name} ({column}) TYPE {index_type} GRANULARITY {granularity}"
                try:
                    await self.client.execute_query(index_query)
                    logger.info(f"Index {index_name} created or already exists")
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        logger.warning(f"Index creation warning for {index_name}: {e}")

            logger.info("Authentication metadata columns migration completed successfully")

        except Exception as e:
            logger.error(f"Error adding authentication metadata columns: {e}")
            raise

    async def create_cluster_metrics_tables(self):
        """Create tables for cluster metrics collected via OTel."""
        logger.info("Creating cluster metrics tables...")

        # Ensure metrics database exists (for cluster metrics tables)
        try:
            await self.client.execute_query("CREATE DATABASE IF NOT EXISTS metrics")
            logger.info("Database 'metrics' created or already exists")
        except Exception as e:
            logger.error(f"Error creating metrics database: {e}")
            raise

        # Main cluster metrics table (raw metrics from OTel)
        ttl_days = get_cluster_metrics_ttl_days()
        query_cluster_metrics = f"""
        CREATE TABLE IF NOT EXISTS metrics.ClusterMetrics
        (
            ts DateTime64(3) CODEC(Delta, ZSTD),
            cluster_id String,
            cluster_name String,
            cluster_platform String,
            metric_name String,
            value Float64 CODEC(Gorilla, ZSTD),
            labels Map(String, String)
        )
        ENGINE = ReplacingMergeTree()
        PARTITION BY toYYYYMM(ts)
        ORDER BY (cluster_id, metric_name, ts)
        TTL ts + INTERVAL {ttl_days} DAY
        SETTINGS index_granularity = 8192
        """

        try:
            await self.client.execute_query(query_cluster_metrics)
            logger.info("ClusterMetrics table created successfully")

            # Add indexes for ClusterMetrics (matching SQL file conventions)
            indexes = [
                "ALTER TABLE metrics.ClusterMetrics ADD INDEX IF NOT EXISTS idx_cluster_metric_time (cluster_id, metric_name, ts) TYPE minmax GRANULARITY 1",
            ]

            for index_query in indexes:
                try:
                    await self.client.execute_query(index_query)
                except Exception as e:
                    if "already exists" not in str(e):
                        logger.warning(f"Index creation warning: {e}")

        except Exception as e:
            logger.error(f"Error creating ClusterMetrics table: {e}")
            raise

        # Node-level aggregated metrics
        query_node_metrics = f"""
        CREATE TABLE IF NOT EXISTS metrics.NodeMetrics
        (
            ts DateTime64(3) CODEC(Delta, ZSTD),
            cluster_id String,
            cluster_name String,
            node_name String,
            cpu_cores Float64,
            cpu_usage_percent Float64 CODEC(Gorilla),
            memory_total_bytes Float64,
            memory_used_bytes Float64,
            memory_usage_percent Float64 CODEC(Gorilla),
            disk_total_bytes Float64,
            disk_used_bytes Float64,
            disk_usage_percent Float64 CODEC(Gorilla),
            load_1 Float64,
            load_5 Float64,
            load_15 Float64,
            network_receive_bytes_per_sec Float64 DEFAULT 0,
            network_transmit_bytes_per_sec Float64 DEFAULT 0
        )
        ENGINE = ReplacingMergeTree()
        PARTITION BY toYYYYMM(ts)
        ORDER BY (cluster_id, node_name, ts)
        TTL ts + INTERVAL {ttl_days} DAY
        SETTINGS index_granularity = 8192
        """

        try:
            await self.client.execute_query(query_node_metrics)
            logger.info("NodeMetrics table created successfully")

            # Add indexes for NodeMetrics (matching SQL file conventions)
            indexes = [
                "ALTER TABLE metrics.NodeMetrics ADD INDEX IF NOT EXISTS idx_cluster_node_time (cluster_id, node_name, ts) TYPE minmax GRANULARITY 1",
            ]

            for index_query in indexes:
                try:
                    await self.client.execute_query(index_query)
                except Exception as e:
                    if "already exists" not in str(e):
                        logger.warning(f"Index creation warning: {e}")

        except Exception as e:
            logger.error(f"Error creating NodeMetrics table: {e}")
            raise

        # Pod/Container metrics
        query_pod_metrics = f"""
        CREATE TABLE IF NOT EXISTS metrics.PodMetrics
        (
            ts DateTime64(3) CODEC(Delta, ZSTD),
            cluster_id String,
            cluster_name String,
            namespace String,
            pod_name String,
            container_name String,
            cpu_requests Float64,
            cpu_limits Float64,
            cpu_usage Float64 CODEC(Gorilla),
            memory_requests_bytes Float64,
            memory_limits_bytes Float64,
            memory_usage_bytes Float64,
            restarts Int32,
            status String
        )
        ENGINE = ReplacingMergeTree()
        PARTITION BY toYYYYMM(ts)
        ORDER BY (cluster_id, namespace, pod_name, ts)
        TTL ts + INTERVAL {ttl_days} DAY
        SETTINGS index_granularity = 8192
        """

        try:
            await self.client.execute_query(query_pod_metrics)
            logger.info("PodMetrics table created successfully")

            # Add indexes for PodMetrics (matching SQL file conventions)
            indexes = [
                "ALTER TABLE metrics.PodMetrics ADD INDEX IF NOT EXISTS idx_cluster_ns_pod_time (cluster_id, namespace, pod_name, ts) TYPE minmax GRANULARITY 1",
            ]

            for index_query in indexes:
                try:
                    await self.client.execute_query(index_query)
                except Exception as e:
                    if "already exists" not in str(e):
                        logger.warning(f"Index creation warning: {e}")

        except Exception as e:
            logger.error(f"Error creating PodMetrics table: {e}")
            raise

        # GPU metrics (optional)
        query_gpu_metrics = f"""
        CREATE TABLE IF NOT EXISTS metrics.GPUMetrics
        (
            ts DateTime64(3) CODEC(Delta, ZSTD),
            cluster_id String,
            cluster_name String,
            node_name String,
            gpu_index UInt8,
            gpu_model String,
            utilization_percent Float64 CODEC(Gorilla),
            memory_used_bytes Float64,
            memory_total_bytes Float64,
            temperature_celsius Float64,
            power_watts Float64
        )
        ENGINE = ReplacingMergeTree()
        PARTITION BY toYYYYMM(ts)
        ORDER BY (cluster_id, node_name, gpu_index, ts)
        TTL ts + INTERVAL {ttl_days} DAY
        SETTINGS index_granularity = 8192
        """

        try:
            await self.client.execute_query(query_gpu_metrics)
            logger.info("GPUMetrics table created successfully")

            # Add indexes for GPUMetrics (matching SQL file conventions)
            indexes = [
                "ALTER TABLE metrics.GPUMetrics ADD INDEX IF NOT EXISTS idx_cluster_gpu_time (cluster_id, node_name, gpu_index, ts) TYPE minmax GRANULARITY 1",
            ]

            for index_query in indexes:
                try:
                    await self.client.execute_query(index_query)
                except Exception as e:
                    if "already exists" not in str(e):
                        logger.warning(f"Index creation warning: {e}")

        except Exception as e:
            logger.error(f"Error creating GPUMetrics table: {e}")
            raise

        logger.info("All cluster metrics tables created successfully")

    async def create_node_events_table(self):
        """Create NodeEvents table for storing Kubernetes node events."""
        logger.info("Creating NodeEvents table...")

        # Ensure metrics database exists
        try:
            await self.client.execute_query("CREATE DATABASE IF NOT EXISTS metrics")
        except Exception as e:
            logger.error(f"Error creating metrics database: {e}")
            raise

        ttl_days = get_cluster_metrics_ttl_days()
        query_node_events = f"""
        CREATE TABLE IF NOT EXISTS metrics.NodeEvents
        (
            ts DateTime64(3) CODEC(Delta, ZSTD),
            cluster_id String,
            cluster_name String,
            node_name String,
            event_uid String,
            event_type LowCardinality(String),
            reason LowCardinality(String),
            message String CODEC(ZSTD(3)),
            source_component LowCardinality(String),
            source_host String,
            first_timestamp DateTime64(3),
            last_timestamp DateTime64(3),
            event_count UInt32 DEFAULT 1
        )
        ENGINE = ReplacingMergeTree(ts)
        PARTITION BY toYYYYMM(ts)
        ORDER BY (cluster_id, node_name, reason, ts, event_uid)
        TTL ts + INTERVAL {ttl_days} DAY
        SETTINGS index_granularity = 8192
        """

        try:
            await self.client.execute_query(query_node_events)
            logger.info("NodeEvents table created successfully")

            # Add indexes for efficient queries
            indexes = [
                "ALTER TABLE metrics.NodeEvents ADD INDEX IF NOT EXISTS idx_cluster_time (cluster_id, ts) TYPE minmax GRANULARITY 1",
                "ALTER TABLE metrics.NodeEvents ADD INDEX IF NOT EXISTS idx_event_type (event_type) TYPE set(10) GRANULARITY 4",
                "ALTER TABLE metrics.NodeEvents ADD INDEX IF NOT EXISTS idx_node_name (node_name) TYPE bloom_filter(0.01) GRANULARITY 8",
                "ALTER TABLE metrics.NodeEvents ADD INDEX IF NOT EXISTS idx_reason (reason) TYPE set(100) GRANULARITY 4",
            ]

            for index_query in indexes:
                try:
                    await self.client.execute_query(index_query)
                except Exception as e:
                    if "already exists" not in str(e):
                        logger.warning(f"Index creation warning: {e}")

        except Exception as e:
            logger.error(f"Error creating NodeEvents table: {e}")
            raise

    async def create_hami_gpu_metrics_table(self):
        """Create HAMI GPU time-slicing metrics table for tracking vGPU allocation and utilization."""
        logger.info("Creating HAMI GPU metrics table...")

        ttl_days = get_cluster_metrics_ttl_days()
        query_hami_gpu_metrics = f"""
        CREATE TABLE IF NOT EXISTS metrics.HAMIGPUMetrics
        (
            ts DateTime64(3) CODEC(Delta, ZSTD),
            cluster_id String,
            cluster_name String,
            node_name String,

            -- Device identification
            device_uuid String,
            device_type String,
            device_index UInt8,

            -- HAMI allocation metrics
            core_allocated_percent Float64 CODEC(Gorilla),
            memory_allocated_gb Float64 CODEC(Gorilla),
            shared_containers_count UInt16,

            -- Device capacity
            total_memory_gb Float64,
            total_cores_percent Float64,

            -- Calculated utilization
            core_utilization_percent Float64 CODEC(Gorilla),
            memory_utilization_percent Float64 CODEC(Gorilla),

            -- Hardware mode
            hardware_mode LowCardinality(String) DEFAULT 'whole-gpu',  -- 'time-slicing', 'mig', 'whole-gpu'

            -- DCGM hardware metrics (enriched from DCGM Exporter when available)
            temperature_celsius Float64 DEFAULT 0 CODEC(Gorilla),
            power_watts Float64 DEFAULT 0 CODEC(Gorilla),
            sm_clock_mhz UInt32 DEFAULT 0,
            mem_clock_mhz UInt32 DEFAULT 0,
            gpu_utilization_percent Float64 DEFAULT 0 CODEC(Gorilla)
        )
        ENGINE = ReplacingMergeTree()
        PARTITION BY toYYYYMM(ts)
        ORDER BY (cluster_id, node_name, device_uuid, ts)
        TTL ts + INTERVAL {ttl_days} DAY
        SETTINGS index_granularity = 8192
        """

        try:
            await self.client.execute_query(query_hami_gpu_metrics)
            logger.info("HAMIGPUMetrics table created successfully")

            # Add indexes for HAMIGPUMetrics
            indexes = [
                "ALTER TABLE metrics.HAMIGPUMetrics ADD INDEX IF NOT EXISTS idx_cluster_node_device_time (cluster_id, node_name, device_uuid, ts) TYPE minmax GRANULARITY 1",
                "ALTER TABLE metrics.HAMIGPUMetrics ADD INDEX IF NOT EXISTS idx_hardware_mode (hardware_mode) TYPE set(10) GRANULARITY 4",
            ]

            for index_query in indexes:
                try:
                    await self.client.execute_query(index_query)
                except Exception as e:
                    if "already exists" not in str(e):
                        logger.warning(f"Index creation warning: {e}")

        except Exception as e:
            logger.error(f"Error creating HAMIGPUMetrics table: {e}")
            raise

    async def create_hami_slice_metrics_table(self):
        """Create HAMI slice metrics table for tracking per-container GPU allocation and utilization."""
        logger.info("Creating HAMI slice metrics table...")

        ttl_days = get_cluster_metrics_ttl_days()
        query_hami_slice_metrics = f"""
        CREATE TABLE IF NOT EXISTS metrics.HAMISliceMetrics
        (
            ts DateTime64(3) CODEC(Delta, ZSTD),
            cluster_id String,
            node_name String,

            -- Device identification
            device_uuid String,
            device_index UInt8,

            -- Pod/Container identification
            pod_name String,
            pod_namespace String,
            container_name String,

            -- Memory allocation (bytes)
            memory_limit_bytes Int64 CODEC(DoubleDelta, ZSTD),
            memory_used_bytes Int64 CODEC(DoubleDelta, ZSTD),

            -- Core allocation (percent)
            core_limit_percent Float64 CODEC(Gorilla),
            core_used_percent Float64 CODEC(Gorilla),

            -- GPU utilization
            gpu_utilization_percent Float64 CODEC(Gorilla),

            -- Status
            status LowCardinality(String) DEFAULT 'unknown'  -- 'running', 'pending', 'terminated', 'unknown'
        )
        ENGINE = ReplacingMergeTree()
        PARTITION BY toYYYYMM(ts)
        ORDER BY (cluster_id, node_name, device_uuid, pod_namespace, pod_name, ts)
        TTL ts + INTERVAL {ttl_days} DAY
        SETTINGS index_granularity = 8192
        """

        try:
            await self.client.execute_query(query_hami_slice_metrics)
            logger.info("HAMISliceMetrics table created successfully")

            # Add indexes for HAMISliceMetrics
            indexes = [
                "ALTER TABLE metrics.HAMISliceMetrics ADD INDEX IF NOT EXISTS idx_cluster_node_device_time (cluster_id, node_name, device_uuid, ts) TYPE minmax GRANULARITY 1",
                "ALTER TABLE metrics.HAMISliceMetrics ADD INDEX IF NOT EXISTS idx_pod_namespace (pod_namespace) TYPE set(100) GRANULARITY 4",
                "ALTER TABLE metrics.HAMISliceMetrics ADD INDEX IF NOT EXISTS idx_status (status) TYPE set(10) GRANULARITY 4",
            ]

            for index_query in indexes:
                try:
                    await self.client.execute_query(index_query)
                except Exception as e:
                    if "already exists" not in str(e):
                        logger.warning(f"Index creation warning: {e}")

        except Exception as e:
            logger.error(f"Error creating HAMISliceMetrics table: {e}")
            raise

    async def verify_tables(self):
        """Verify that tables were created successfully."""
        # Tables in budproxy database (or configured database)
        budproxy_tables = [
            "ModelInferenceDetails",
            "EmbeddingInference",
            "AudioInference",
            "ImageInference",
            "ModerationInference",
            "GatewayAnalytics",
            "GatewayBlockingEvents",
            "InferenceFact",
            "InferenceMetrics5m",
            "InferenceMetrics1h",
            "InferenceMetrics1d",
        ]
        # Cluster metrics tables in metrics database
        metrics_tables = [
            "metrics.ClusterMetrics",
            "metrics.NodeMetrics",
            "metrics.PodMetrics",
            "metrics.GPUMetrics",
            "metrics.HAMIGPUMetrics",
            "metrics.HAMISliceMetrics",
            "metrics.NodeEvents",
        ]

        if self.include_model_inference:
            budproxy_tables.append("ModelInference")

        all_tables = budproxy_tables + metrics_tables

        for table in all_tables:
            try:
                result = await self.client.execute_query(f"EXISTS TABLE {table}")
                if result and result[0][0]:
                    logger.info(f"✓ Table {table} exists")

                    # Get row count
                    count_result = await self.client.execute_query(f"SELECT COUNT(*) FROM {table}")
                    count = count_result[0][0] if count_result else 0
                    logger.info(f"  - Row count: {count:,}")
                else:
                    logger.error(f"✗ Table {table} does not exist")

            except Exception as e:
                logger.error(f"Error checking table {table}: {e}")

    async def update_api_key_project_id(self):
        """Update api_key_project_id to project_id where api_key_project_id is null.

        This ensures billing queries work correctly by using the api_key_project_id field
        which is more accurate for API key based usage tracking.
        """
        try:
            # First check if there are any records to update
            check_query = """
            SELECT COUNT(*)
            FROM ModelInferenceDetails
            WHERE api_key_project_id IS NULL AND project_id IS NOT NULL
            """
            result = await self.client.execute_query(check_query)
            count_to_update = result[0][0] if result else 0

            if count_to_update > 0:
                logger.info(f"Found {count_to_update} records with null api_key_project_id to update")

                # Update in batches to avoid locking issues
                update_query = """
                ALTER TABLE ModelInferenceDetails
                UPDATE api_key_project_id = project_id
                WHERE api_key_project_id IS NULL AND project_id IS NOT NULL
                """

                await self.client.execute_query(update_query)
                logger.info(f"Successfully updated {count_to_update} records with api_key_project_id = project_id")
            else:
                logger.info("No records found with null api_key_project_id that need updating")

        except Exception as e:
            logger.warning(f"Could not update api_key_project_id (may not be critical): {e}")

    async def create_inference_fact_table(self):
        """Create InferenceFact table - denormalized flat table from OTel traces.

        This table combines data from all span attributes into a single denormalized table:
        - model_inference_details.* (from inference_handler_observability span)
        - model_inference.* (from inference_handler_observability span)
        - chat_inference.* (from inference_handler_observability span)
        - gateway_analytics.* (from gateway_analytics span, via LEFT JOIN on TraceId)

        This enables fast query performance without JOINs at query time.
        """
        logger.info("Creating InferenceFact table...")

        query = """
        CREATE TABLE IF NOT EXISTS InferenceFact
        (
            -- ===== OTel TRACE IDENTIFIERS =====
            id UUID DEFAULT generateUUIDv4() CODEC(ZSTD(1)),
            trace_id String CODEC(ZSTD(1)),
            span_id String CODEC(ZSTD(1)),

            -- ===== CORE IDENTIFIERS (from model_inference_details.*) =====
            -- Nullable to support blocked requests that never reach inference
            inference_id Nullable(UUID) CODEC(ZSTD(1)),
            -- Nullable to support early-blocked requests that may not have these set
            project_id Nullable(UUID) CODEC(ZSTD(1)),
            endpoint_id Nullable(UUID) CODEC(ZSTD(1)),
            model_id Nullable(UUID) CODEC(ZSTD(1)),
            api_key_id Nullable(UUID) CODEC(ZSTD(1)),
            api_key_project_id Nullable(UUID) CODEC(ZSTD(1)),
            user_id Nullable(String) CODEC(ZSTD(1)),

            -- ===== TIMESTAMPS =====
            timestamp DateTime64(3) CODEC(Delta, ZSTD(1)),
            request_arrival_time Nullable(DateTime64(3)) CODEC(Delta, ZSTD(1)),
            request_forward_time Nullable(DateTime64(3)) CODEC(Delta, ZSTD(1)),

            -- ===== STATUS & COST (from model_inference_details.*) =====
            is_success Bool DEFAULT true,
            cost Nullable(Float64) CODEC(Gorilla, ZSTD(1)),
            status_code Nullable(UInt16) CODEC(ZSTD(1)),
            request_ip Nullable(IPv4) CODEC(ZSTD(1)),
            response_analysis Nullable(String) CODEC(ZSTD(1)),

            -- ===== ERROR TRACKING (from model_inference_details.*) =====
            error_code Nullable(String) CODEC(ZSTD(1)),
            error_message Nullable(String) CODEC(ZSTD(3)),
            error_type Nullable(String) CODEC(ZSTD(1)),

            -- ===== MODEL INFO (from model_inference.*) =====
            model_inference_id Nullable(UUID) CODEC(ZSTD(1)),
            model_name LowCardinality(String) DEFAULT '' CODEC(ZSTD(1)),
            model_provider LowCardinality(String) DEFAULT '' CODEC(ZSTD(1)),
            endpoint_type LowCardinality(String) DEFAULT 'chat' CODEC(ZSTD(1)),

            -- ===== PERFORMANCE METRICS (from model_inference.*) =====
            input_tokens Nullable(UInt32) CODEC(Delta, ZSTD(1)),
            output_tokens Nullable(UInt32) CODEC(Delta, ZSTD(1)),
            response_time_ms Nullable(UInt32) CODEC(Delta, ZSTD(1)),
            ttft_ms Nullable(UInt32) CODEC(Delta, ZSTD(1)),
            cached Bool DEFAULT false,
            finish_reason Nullable(Enum8('stop' = 1, 'length' = 2, 'tool_call' = 3, 'content_filter' = 4, 'unknown' = 5)),

            -- ===== CONTENT (from model_inference.*) =====
            system_prompt Nullable(String) CODEC(ZSTD(3)),
            input_messages Nullable(String) CODEC(ZSTD(3)),
            output Nullable(String) CODEC(ZSTD(3)),
            raw_request Nullable(String) CODEC(ZSTD(3)),
            raw_response Nullable(String) CODEC(ZSTD(3)),
            gateway_request Nullable(String) CODEC(ZSTD(3)),
            gateway_response Nullable(String) CODEC(ZSTD(3)),
            guardrail_scan_summary Nullable(String) CODEC(ZSTD(1)),
            model_inference_timestamp Nullable(UInt64) CODEC(ZSTD(1)),

            -- ===== CHAT INFERENCE (from chat_inference.*) =====
            chat_inference_id Nullable(UUID) CODEC(ZSTD(1)),
            episode_id Nullable(UUID) CODEC(ZSTD(1)),
            function_name LowCardinality(Nullable(String)) CODEC(ZSTD(1)),
            variant_name LowCardinality(Nullable(String)) CODEC(ZSTD(1)),
            processing_time_ms Nullable(UInt32) CODEC(Delta, ZSTD(1)),
            chat_input Nullable(String) CODEC(ZSTD(3)),
            chat_output Nullable(String) CODEC(ZSTD(3)),
            tags Nullable(String) CODEC(ZSTD(1)),
            inference_params Nullable(String) CODEC(ZSTD(1)),
            extra_body Nullable(String) CODEC(ZSTD(1)),
            tool_params Nullable(String) CODEC(ZSTD(1)),

            -- ===== GATEWAY ANALYTICS (from gateway_analytics.* span) =====
            -- Geographic
            country_code LowCardinality(Nullable(String)) CODEC(ZSTD(1)),
            country_name Nullable(String) CODEC(ZSTD(1)),
            region Nullable(String) CODEC(ZSTD(1)),
            city Nullable(String) CODEC(ZSTD(1)),
            latitude Nullable(Float32) CODEC(Gorilla, ZSTD(1)),
            longitude Nullable(Float32) CODEC(Gorilla, ZSTD(1)),
            timezone Nullable(String) CODEC(ZSTD(1)),
            asn Nullable(UInt32) CODEC(ZSTD(1)),
            isp Nullable(String) CODEC(ZSTD(1)),

            -- Client metadata
            client_ip Nullable(IPv4) CODEC(ZSTD(1)),
            user_agent Nullable(String) CODEC(ZSTD(3)),
            device_type LowCardinality(Nullable(String)) CODEC(ZSTD(1)),
            browser_name LowCardinality(Nullable(String)) CODEC(ZSTD(1)),
            browser_version Nullable(String) CODEC(ZSTD(1)),
            os_name LowCardinality(Nullable(String)) CODEC(ZSTD(1)),
            os_version Nullable(String) CODEC(ZSTD(1)),
            is_bot Nullable(Bool) CODEC(ZSTD(1)),

            -- Request context
            method LowCardinality(Nullable(String)) CODEC(ZSTD(1)),
            path Nullable(String) CODEC(ZSTD(1)),
            query_params Nullable(String) CODEC(ZSTD(1)),
            body_size Nullable(UInt32) CODEC(ZSTD(1)),
            response_size Nullable(UInt32) CODEC(ZSTD(1)),
            protocol_version Nullable(String) CODEC(ZSTD(1)),

            -- Performance
            gateway_processing_ms Nullable(UInt32) CODEC(Delta, ZSTD(1)),
            total_duration_ms Nullable(UInt32) CODEC(Delta, ZSTD(1)),

            -- Routing & blocking
            model_version Nullable(String) CODEC(ZSTD(1)),
            routing_decision LowCardinality(Nullable(String)) CODEC(ZSTD(1)),
            is_blocked Nullable(Bool) CODEC(ZSTD(1)),
            block_reason Nullable(String) CODEC(ZSTD(1)),
            block_rule_id Nullable(String) CODEC(ZSTD(1)),
            proxy_chain Nullable(String) CODEC(ZSTD(1)),

            -- Headers & timestamps
            request_headers Nullable(String) CODEC(ZSTD(3)),
            response_headers Nullable(String) CODEC(ZSTD(3)),
            request_timestamp Nullable(DateTime64(3)) CODEC(Delta, ZSTD(1)),
            response_timestamp Nullable(DateTime64(3)) CODEC(Delta, ZSTD(1)),
            gateway_tags Nullable(String) CODEC(ZSTD(1)),

            -- ===== BLOCKING EVENT DATA (from gateway_blocking_events.* span) =====
            blocking_event_id Nullable(UUID) CODEC(ZSTD(1)),
            rule_id Nullable(UUID) CODEC(ZSTD(1)),
            rule_type LowCardinality(Nullable(String)) CODEC(ZSTD(1)),
            rule_name Nullable(String) CODEC(ZSTD(1)),
            rule_priority Nullable(Int32) CODEC(ZSTD(1)),
            block_reason_detail Nullable(String) CODEC(ZSTD(1)),
            action_taken LowCardinality(Nullable(String)) CODEC(ZSTD(1)),
            blocked_at Nullable(DateTime64(3)) CODEC(Delta, ZSTD(1)),

            -- ===== MATERIALIZED COLUMNS =====
            date Date MATERIALIZED toDate(timestamp),
            hour DateTime MATERIALIZED toStartOfHour(timestamp)
        )
        ENGINE = ReplacingMergeTree(timestamp)
        PARTITION BY toYYYYMMDD(timestamp)
        ORDER BY (trace_id)
        TTL toDateTime(timestamp) + INTERVAL 90 DAY
        SETTINGS index_granularity = 8192, allow_nullable_key = 1
        """

        try:
            await self.client.execute_query(query)
            logger.info("InferenceFact table created successfully")

            # Create data-skipping indexes
            indexes = [
                # Core identifiers
                "ALTER TABLE InferenceFact ADD INDEX IF NOT EXISTS idx_inference_id (inference_id) TYPE bloom_filter(0.01) GRANULARITY 4",
                "ALTER TABLE InferenceFact ADD INDEX IF NOT EXISTS idx_episode_id (episode_id) TYPE bloom_filter(0.01) GRANULARITY 4",
                "ALTER TABLE InferenceFact ADD INDEX IF NOT EXISTS idx_api_key_project (api_key_project_id) TYPE bloom_filter(0.01) GRANULARITY 4",
                "ALTER TABLE InferenceFact ADD INDEX IF NOT EXISTS idx_user_id (user_id) TYPE bloom_filter(0.01) GRANULARITY 4",
                # Model info
                "ALTER TABLE InferenceFact ADD INDEX IF NOT EXISTS idx_model_name (model_name) TYPE set(100) GRANULARITY 4",
                "ALTER TABLE InferenceFact ADD INDEX IF NOT EXISTS idx_model_provider (model_provider) TYPE set(50) GRANULARITY 4",
                "ALTER TABLE InferenceFact ADD INDEX IF NOT EXISTS idx_endpoint_type (endpoint_type) TYPE set(10) GRANULARITY 4",
                "ALTER TABLE InferenceFact ADD INDEX IF NOT EXISTS idx_function_name (function_name) TYPE set(100) GRANULARITY 4",
                # Status flags
                "ALTER TABLE InferenceFact ADD INDEX IF NOT EXISTS idx_is_success (is_success) TYPE minmax GRANULARITY 4",
                "ALTER TABLE InferenceFact ADD INDEX IF NOT EXISTS idx_cached (cached) TYPE minmax GRANULARITY 4",
                "ALTER TABLE InferenceFact ADD INDEX IF NOT EXISTS idx_status_code (status_code) TYPE set(20) GRANULARITY 4",
                "ALTER TABLE InferenceFact ADD INDEX IF NOT EXISTS idx_finish_reason (finish_reason) TYPE set(10) GRANULARITY 4",
                # Gateway analytics - geographic
                "ALTER TABLE InferenceFact ADD INDEX IF NOT EXISTS idx_country_code (country_code) TYPE set(300) GRANULARITY 4",
                "ALTER TABLE InferenceFact ADD INDEX IF NOT EXISTS idx_city (city) TYPE bloom_filter(0.01) GRANULARITY 4",
                # Gateway analytics - client
                "ALTER TABLE InferenceFact ADD INDEX IF NOT EXISTS idx_device_type (device_type) TYPE set(20) GRANULARITY 4",
                "ALTER TABLE InferenceFact ADD INDEX IF NOT EXISTS idx_is_bot (is_bot) TYPE minmax GRANULARITY 4",
                "ALTER TABLE InferenceFact ADD INDEX IF NOT EXISTS idx_client_ip (client_ip) TYPE bloom_filter(0.01) GRANULARITY 8",
                # Gateway analytics - routing
                "ALTER TABLE InferenceFact ADD INDEX IF NOT EXISTS idx_is_blocked (is_blocked) TYPE minmax GRANULARITY 4",
                "ALTER TABLE InferenceFact ADD INDEX IF NOT EXISTS idx_routing_decision (routing_decision) TYPE set(20) GRANULARITY 4",
                # Error tracking
                "ALTER TABLE InferenceFact ADD INDEX IF NOT EXISTS idx_error_type (error_type) TYPE set(50) GRANULARITY 4",
                # Blocking event data
                "ALTER TABLE InferenceFact ADD INDEX IF NOT EXISTS idx_rule_id (rule_id) TYPE bloom_filter(0.01) GRANULARITY 4",
                "ALTER TABLE InferenceFact ADD INDEX IF NOT EXISTS idx_rule_type (rule_type) TYPE set(20) GRANULARITY 4",
                "ALTER TABLE InferenceFact ADD INDEX IF NOT EXISTS idx_action_taken (action_taken) TYPE set(10) GRANULARITY 4",
            ]

            for index_query in indexes:
                try:
                    await self.client.execute_query(index_query)
                except Exception as e:
                    if "already exists" not in str(e):
                        logger.warning(f"Index creation warning: {e}")

            logger.info("InferenceFact indexes created successfully")

        except Exception as e:
            logger.error(f"Error creating InferenceFact table: {e}")
            raise

    async def create_mv_otel_to_inference_fact(self):
        """Create Materialized View to transform otel_traces to InferenceFact.

        This MV extracts span attributes from two span types using LEFT JOIN on TraceId:
        - inference_handler_observability span: model_inference_details.*, model_inference.*, chat_inference.*
        - gateway_analytics span: gateway_analytics.*

        The LEFT JOIN ensures inference data is captured even if gateway span is missing.
        """
        logger.info("Creating mv_otel_to_inference_fact materialized view...")

        # First drop existing view if it exists to ensure clean state
        try:
            await self.client.execute_query("DROP VIEW IF EXISTS mv_otel_to_inference_fact")
            logger.info("Dropped existing mv_otel_to_inference_fact (if any)")
        except Exception as e:
            logger.warning(f"Could not drop existing view: {e}")

        query = """
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_otel_to_inference_fact TO InferenceFact AS
        SELECT
            -- ===== OTel TRACE IDENTIFIERS =====
            generateUUIDv4() AS id,
            i.TraceId AS trace_id,
            i.SpanId AS span_id,

            -- ===== CORE IDENTIFIERS (from model_inference_details.*) =====
            toUUIDOrNull(nullIf(i.SpanAttributes['model_inference_details.inference_id'], '')) AS inference_id,
            toUUIDOrNull(nullIf(i.SpanAttributes['model_inference_details.project_id'], '')) AS project_id,
            toUUIDOrNull(nullIf(i.SpanAttributes['model_inference_details.endpoint_id'], '')) AS endpoint_id,
            toUUIDOrNull(nullIf(i.SpanAttributes['model_inference_details.model_id'], '')) AS model_id,
            toUUIDOrNull(nullIf(i.SpanAttributes['model_inference_details.api_key_id'], '')) AS api_key_id,
            toUUIDOrNull(nullIf(i.SpanAttributes['model_inference_details.api_key_project_id'], '')) AS api_key_project_id,
            nullIf(i.SpanAttributes['model_inference_details.user_id'], '') AS user_id,

            -- ===== TIMESTAMPS =====
            toDateTime64(i.Timestamp, 3) AS timestamp,
            parseDateTime64BestEffortOrNull(i.SpanAttributes['model_inference_details.request_arrival_time']) AS request_arrival_time,
            parseDateTime64BestEffortOrNull(i.SpanAttributes['model_inference_details.request_forward_time']) AS request_forward_time,

            -- ===== STATUS & COST (from model_inference_details.*) =====
            i.SpanAttributes['model_inference_details.is_success'] = 'true' AS is_success,
            toFloat64OrNull(i.SpanAttributes['model_inference_details.cost']) AS cost,
            toUInt16OrNull(i.SpanAttributes['model_inference_details.status_code']) AS status_code,
            toIPv4OrNull(i.SpanAttributes['model_inference_details.request_ip']) AS request_ip,
            nullIf(i.SpanAttributes['model_inference_details.response_analysis'], '') AS response_analysis,

            -- ===== ERROR TRACKING (from model_inference_details.*) =====
            nullIf(i.SpanAttributes['model_inference_details.error_code'], '') AS error_code,
            nullIf(i.SpanAttributes['model_inference_details.error_message'], '') AS error_message,
            nullIf(i.SpanAttributes['model_inference_details.error_type'], '') AS error_type,

            -- ===== MODEL INFO (from model_inference.*) =====
            toUUIDOrNull(nullIf(i.SpanAttributes['model_inference.id'], '')) AS model_inference_id,
            i.SpanAttributes['model_inference.model_name'] AS model_name,
            i.SpanAttributes['model_inference.model_provider_name'] AS model_provider,
            if(i.SpanAttributes['model_inference.endpoint_type'] != '', i.SpanAttributes['model_inference.endpoint_type'], 'chat') AS endpoint_type,

            -- ===== PERFORMANCE METRICS (from model_inference.*) =====
            toUInt32OrNull(i.SpanAttributes['model_inference.input_tokens']) AS input_tokens,
            toUInt32OrNull(i.SpanAttributes['model_inference.output_tokens']) AS output_tokens,
            toUInt32OrNull(i.SpanAttributes['model_inference.response_time_ms']) AS response_time_ms,
            toUInt32OrNull(i.SpanAttributes['model_inference.ttft_ms']) AS ttft_ms,
            i.SpanAttributes['model_inference.cached'] = 'true' AS cached,
            multiIf(
                i.SpanAttributes['model_inference.finish_reason'] = 'stop', toNullable(CAST(1, 'Enum8(\\'stop\\' = 1, \\'length\\' = 2, \\'tool_call\\' = 3, \\'content_filter\\' = 4, \\'unknown\\' = 5)')),
                i.SpanAttributes['model_inference.finish_reason'] = 'length', toNullable(CAST(2, 'Enum8(\\'stop\\' = 1, \\'length\\' = 2, \\'tool_call\\' = 3, \\'content_filter\\' = 4, \\'unknown\\' = 5)')),
                i.SpanAttributes['model_inference.finish_reason'] = 'tool_call', toNullable(CAST(3, 'Enum8(\\'stop\\' = 1, \\'length\\' = 2, \\'tool_call\\' = 3, \\'content_filter\\' = 4, \\'unknown\\' = 5)')),
                i.SpanAttributes['model_inference.finish_reason'] = 'content_filter', toNullable(CAST(4, 'Enum8(\\'stop\\' = 1, \\'length\\' = 2, \\'tool_call\\' = 3, \\'content_filter\\' = 4, \\'unknown\\' = 5)')),
                i.SpanAttributes['model_inference.finish_reason'] != '', toNullable(CAST(5, 'Enum8(\\'stop\\' = 1, \\'length\\' = 2, \\'tool_call\\' = 3, \\'content_filter\\' = 4, \\'unknown\\' = 5)')),
                NULL
            ) AS finish_reason,

            -- ===== CONTENT (from model_inference.*) =====
            nullIf(i.SpanAttributes['model_inference.system'], '') AS system_prompt,
            nullIf(i.SpanAttributes['model_inference.input_messages'], '') AS input_messages,
            nullIf(i.SpanAttributes['model_inference.output'], '') AS output,
            nullIf(i.SpanAttributes['model_inference.raw_request'], '') AS raw_request,
            nullIf(i.SpanAttributes['model_inference.raw_response'], '') AS raw_response,
            nullIf(i.SpanAttributes['model_inference.gateway_request'], '') AS gateway_request,
            nullIf(i.SpanAttributes['model_inference.gateway_response'], '') AS gateway_response,
            nullIf(i.SpanAttributes['model_inference.guardrail_scan_summary'], '') AS guardrail_scan_summary,
            toUInt64OrNull(i.SpanAttributes['model_inference.timestamp']) AS model_inference_timestamp,

            -- ===== CHAT INFERENCE (from chat_inference.*) =====
            toUUIDOrNull(nullIf(i.SpanAttributes['chat_inference.id'], '')) AS chat_inference_id,
            toUUIDOrNull(nullIf(i.SpanAttributes['chat_inference.episode_id'], '')) AS episode_id,
            nullIf(i.SpanAttributes['chat_inference.function_name'], '') AS function_name,
            nullIf(i.SpanAttributes['chat_inference.variant_name'], '') AS variant_name,
            toUInt32OrNull(i.SpanAttributes['chat_inference.processing_time_ms']) AS processing_time_ms,
            nullIf(i.SpanAttributes['chat_inference.input'], '') AS chat_input,
            nullIf(i.SpanAttributes['chat_inference.output'], '') AS chat_output,
            nullIf(i.SpanAttributes['chat_inference.tags'], '') AS tags,
            nullIf(i.SpanAttributes['chat_inference.inference_params'], '') AS inference_params,
            nullIf(i.SpanAttributes['chat_inference.extra_body'], '') AS extra_body,
            nullIf(i.SpanAttributes['chat_inference.tool_params'], '') AS tool_params,

            -- ===== GATEWAY ANALYTICS (from gateway_analytics.* span via LEFT JOIN) =====
            -- Geographic
            nullIf(g.SpanAttributes['gateway_analytics.country_code'], '') AS country_code,
            nullIf(g.SpanAttributes['gateway_analytics.country_name'], '') AS country_name,
            nullIf(g.SpanAttributes['gateway_analytics.region'], '') AS region,
            nullIf(g.SpanAttributes['gateway_analytics.city'], '') AS city,
            toFloat32OrNull(g.SpanAttributes['gateway_analytics.latitude']) AS latitude,
            toFloat32OrNull(g.SpanAttributes['gateway_analytics.longitude']) AS longitude,
            nullIf(g.SpanAttributes['gateway_analytics.timezone'], '') AS timezone,
            toUInt32OrNull(g.SpanAttributes['gateway_analytics.asn']) AS asn,
            nullIf(g.SpanAttributes['gateway_analytics.isp'], '') AS isp,

            -- Client metadata
            toIPv4OrNull(g.SpanAttributes['gateway_analytics.client_ip']) AS client_ip,
            nullIf(g.SpanAttributes['gateway_analytics.user_agent'], '') AS user_agent,
            nullIf(g.SpanAttributes['gateway_analytics.device_type'], '') AS device_type,
            nullIf(g.SpanAttributes['gateway_analytics.browser_name'], '') AS browser_name,
            nullIf(g.SpanAttributes['gateway_analytics.browser_version'], '') AS browser_version,
            nullIf(g.SpanAttributes['gateway_analytics.os_name'], '') AS os_name,
            nullIf(g.SpanAttributes['gateway_analytics.os_version'], '') AS os_version,
            g.SpanAttributes['gateway_analytics.is_bot'] = 'true' AS is_bot,

            -- Request context
            nullIf(g.SpanAttributes['gateway_analytics.method'], '') AS method,
            nullIf(g.SpanAttributes['gateway_analytics.path'], '') AS path,
            nullIf(g.SpanAttributes['gateway_analytics.query_params'], '') AS query_params,
            toUInt32OrNull(g.SpanAttributes['gateway_analytics.body_size']) AS body_size,
            toUInt32OrNull(g.SpanAttributes['gateway_analytics.response_size']) AS response_size,
            nullIf(g.SpanAttributes['gateway_analytics.protocol_version'], '') AS protocol_version,

            -- Performance
            toUInt32OrNull(g.SpanAttributes['gateway_analytics.gateway_processing_ms']) AS gateway_processing_ms,
            toUInt32OrNull(g.SpanAttributes['gateway_analytics.total_duration_ms']) AS total_duration_ms,

            -- Routing & blocking
            nullIf(g.SpanAttributes['gateway_analytics.model_version'], '') AS model_version,
            nullIf(g.SpanAttributes['gateway_analytics.routing_decision'], '') AS routing_decision,
            g.SpanAttributes['gateway_analytics.is_blocked'] = 'true' AS is_blocked,
            nullIf(g.SpanAttributes['gateway_analytics.block_reason'], '') AS block_reason,
            nullIf(g.SpanAttributes['gateway_analytics.block_rule_id'], '') AS block_rule_id,
            nullIf(g.SpanAttributes['gateway_analytics.proxy_chain'], '') AS proxy_chain,

            -- Headers & timestamps
            nullIf(g.SpanAttributes['gateway_analytics.request_headers'], '') AS request_headers,
            nullIf(g.SpanAttributes['gateway_analytics.response_headers'], '') AS response_headers,
            parseDateTime64BestEffortOrNull(g.SpanAttributes['gateway_analytics.request_timestamp']) AS request_timestamp,
            parseDateTime64BestEffortOrNull(g.SpanAttributes['gateway_analytics.response_timestamp']) AS response_timestamp,
            nullIf(g.SpanAttributes['gateway_analytics.tags'], '') AS gateway_tags,

            -- ===== BLOCKING EVENT DATA (from gateway_blocking_events.* in gateway span) =====
            toUUIDOrNull(nullIf(g.SpanAttributes['gateway_blocking_events.id'], '')) AS blocking_event_id,
            toUUIDOrNull(nullIf(g.SpanAttributes['gateway_blocking_events.rule_id'], '')) AS rule_id,
            nullIf(g.SpanAttributes['gateway_blocking_events.rule_type'], '') AS rule_type,
            nullIf(g.SpanAttributes['gateway_blocking_events.rule_name'], '') AS rule_name,
            toInt32OrNull(g.SpanAttributes['gateway_blocking_events.rule_priority']) AS rule_priority,
            nullIf(g.SpanAttributes['gateway_blocking_events.block_reason'], '') AS block_reason_detail,
            nullIf(g.SpanAttributes['gateway_blocking_events.action_taken'], '') AS action_taken,
            parseDateTime64BestEffortOrNull(g.SpanAttributes['gateway_blocking_events.blocked_at']) AS blocked_at

        FROM metrics.otel_traces i
        LEFT JOIN metrics.otel_traces g
            ON i.TraceId = g.TraceId
            AND g.SpanName = 'gateway_analytics'
        WHERE i.SpanName = 'inference_handler_observability'
          AND i.SpanAttributes['model_inference_details.inference_id'] != ''
          AND i.SpanAttributes['model_inference_details.project_id'] != ''
        """

        try:
            await self.client.execute_query(query)
            logger.info("mv_otel_to_inference_fact materialized view created successfully")
        except Exception as e:
            logger.error(f"Error creating mv_otel_to_inference_fact: {e}")
            raise

    async def create_inference_metrics_rollup_tables(self):
        """Create InferenceMetrics rollup tables for time-series aggregation.

        Creates three rollup tables with different granularities:
        - InferenceMetrics5m: 5-minute granularity, 90 day TTL (real-time dashboards)
        - InferenceMetrics1h: 1-hour granularity, 90 day TTL (daily/weekly analytics)
        - InferenceMetrics1d: 1-day granularity, 90 day TTL (monthly trends, billing)

        UUID handling strategy:
        - Dimension UUIDs (keep): project_id, endpoint_id, model_id, api_key_project_id
        - Count-Only UUIDs (aggregate): user_id, inference_id, episode_id, api_key_id
        - Drop UUIDs: id, model_inference_id, chat_inference_id
        """
        logger.info("Creating InferenceMetrics rollup tables...")

        # Common table structure (shared across all granularities)
        common_columns = """
            -- Time bucket (granularity varies by table)
            time_bucket DateTime,

            -- Dimension UUIDs (for filtering)
            -- NOTE: Nullable to support blocked requests that don't have project/endpoint/model
            project_id Nullable(UUID) CODEC(ZSTD(1)),
            endpoint_id Nullable(UUID) CODEC(ZSTD(1)),
            model_id Nullable(UUID) CODEC(ZSTD(1)),
            api_key_project_id Nullable(UUID) CODEC(ZSTD(1)),

            -- String dimensions (for grouping)
            model_name LowCardinality(String) CODEC(ZSTD(1)),
            model_provider LowCardinality(String) CODEC(ZSTD(1)),
            endpoint_type LowCardinality(String) DEFAULT 'chat' CODEC(ZSTD(1)),
            is_success Bool,
            country_code LowCardinality(Nullable(String)) CODEC(ZSTD(1)),

            -- Counts
            request_count UInt64 CODEC(Delta, ZSTD(1)),
            success_count UInt64 CODEC(Delta, ZSTD(1)),
            error_count UInt64 CODEC(Delta, ZSTD(1)),
            cached_count UInt64 CODEC(Delta, ZSTD(1)),

            -- Token metrics
            total_input_tokens UInt64 CODEC(Delta, ZSTD(1)),
            total_output_tokens UInt64 CODEC(Delta, ZSTD(1)),

            -- Cost metrics
            total_cost Float64 CODEC(Gorilla, ZSTD(1)),

            -- Latency metrics (for average/min/max calculation)
            sum_response_time_ms UInt64 CODEC(Delta, ZSTD(1)),
            sum_ttft_ms UInt64 CODEC(Delta, ZSTD(1)),
            min_response_time_ms Nullable(UInt32) CODEC(ZSTD(1)),
            max_response_time_ms Nullable(UInt32) CODEC(ZSTD(1)),

            -- Unique counts (using AggregateFunction for rollup compatibility)
            unique_users AggregateFunction(uniq, Nullable(String)),
            unique_inferences AggregateFunction(uniq, Nullable(UUID)),
            unique_episodes AggregateFunction(uniq, Nullable(UUID)),
            unique_api_keys AggregateFunction(uniq, Nullable(UUID)),

            -- Blocking metrics
            block_count UInt64 DEFAULT 0 CODEC(Delta, ZSTD(1)),
            unique_blocked_ips AggregateFunction(uniq, IPv4)
        """

        # InferenceMetrics5m - 5-minute granularity, 90 day TTL
        query_5m = f"""
        CREATE TABLE IF NOT EXISTS InferenceMetrics5m
        (
            {common_columns}
        )
        ENGINE = SummingMergeTree(
            (request_count, success_count, error_count, cached_count,
             total_input_tokens, total_output_tokens, total_cost,
             sum_response_time_ms, sum_ttft_ms)
        )
        PARTITION BY toYYYYMM(time_bucket)
        ORDER BY (project_id, endpoint_id, model_id, time_bucket, is_success, country_code)
        TTL time_bucket + INTERVAL 90 DAY
        SETTINGS index_granularity = 8192, allow_nullable_key = 1
        """

        # InferenceMetrics1h - 1-hour granularity, 90 day TTL
        query_1h = f"""
        CREATE TABLE IF NOT EXISTS InferenceMetrics1h
        (
            {common_columns}
        )
        ENGINE = SummingMergeTree(
            (request_count, success_count, error_count, cached_count,
             total_input_tokens, total_output_tokens, total_cost,
             sum_response_time_ms, sum_ttft_ms)
        )
        PARTITION BY toYYYYMM(time_bucket)
        ORDER BY (project_id, endpoint_id, model_id, time_bucket, is_success, country_code)
        TTL time_bucket + INTERVAL 90 DAY
        SETTINGS index_granularity = 8192, allow_nullable_key = 1
        """

        # InferenceMetrics1d - 1-day granularity, 90 day TTL
        query_1d = f"""
        CREATE TABLE IF NOT EXISTS InferenceMetrics1d
        (
            {common_columns}
        )
        ENGINE = SummingMergeTree(
            (request_count, success_count, error_count, cached_count,
             total_input_tokens, total_output_tokens, total_cost,
             sum_response_time_ms, sum_ttft_ms)
        )
        PARTITION BY toYYYYMM(time_bucket)
        ORDER BY (project_id, endpoint_id, model_id, time_bucket, is_success, country_code)
        TTL time_bucket + INTERVAL 90 DAY
        SETTINGS index_granularity = 8192, allow_nullable_key = 1
        """

        tables = [
            ("InferenceMetrics5m", query_5m),
            ("InferenceMetrics1h", query_1h),
            ("InferenceMetrics1d", query_1d),
        ]

        for table_name, query in tables:
            try:
                await self.client.execute_query(query)
                logger.info(f"{table_name} table created successfully")

                # Add indexes for each table
                indexes = [
                    f"ALTER TABLE {table_name} ADD INDEX IF NOT EXISTS idx_time_bucket (time_bucket) TYPE minmax GRANULARITY 1",
                    f"ALTER TABLE {table_name} ADD INDEX IF NOT EXISTS idx_model_name (model_name) TYPE set(100) GRANULARITY 4",
                    f"ALTER TABLE {table_name} ADD INDEX IF NOT EXISTS idx_model_provider (model_provider) TYPE set(50) GRANULARITY 4",
                    f"ALTER TABLE {table_name} ADD INDEX IF NOT EXISTS idx_endpoint_type (endpoint_type) TYPE set(10) GRANULARITY 4",
                    f"ALTER TABLE {table_name} ADD INDEX IF NOT EXISTS idx_country_code (country_code) TYPE set(300) GRANULARITY 4",
                ]

                for index_query in indexes:
                    try:
                        await self.client.execute_query(index_query)
                    except Exception as e:
                        if "already exists" not in str(e):
                            logger.warning(f"Index creation warning: {e}")

            except Exception as e:
                logger.error(f"Error creating {table_name} table: {e}")
                raise

        logger.info("All InferenceMetrics rollup tables created successfully")

    async def create_inference_metrics_materialized_views(self):
        """Create Materialized Views for cascading rollup aggregation.

        Creates three MVs for the cascading rollup:
        - mv_inference_to_5m: InferenceFact → InferenceMetrics5m
        - mv_5m_to_1h: InferenceMetrics5m → InferenceMetrics1h
        - mv_1h_to_1d: InferenceMetrics1h → InferenceMetrics1d

        Uses AggregateFunction with uniqState/uniqMerge for accurate unique counts.
        """
        logger.info("Creating InferenceMetrics materialized views...")

        # MV: InferenceFact → InferenceMetrics5m
        mv_inference_to_5m = """
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_inference_to_5m TO InferenceMetrics5m AS
        SELECT
            toStartOfFiveMinutes(timestamp) AS time_bucket,

            -- Dimension UUIDs
            project_id,
            endpoint_id,
            model_id,
            api_key_project_id,

            -- String dimensions
            model_name,
            model_provider,
            endpoint_type,
            is_success,
            country_code,

            -- Counts
            count() AS request_count,
            countIf(is_success) AS success_count,
            countIf(NOT is_success) AS error_count,
            countIf(cached) AS cached_count,

            -- Token metrics
            sum(ifNull(input_tokens, 0)) AS total_input_tokens,
            sum(ifNull(output_tokens, 0)) AS total_output_tokens,

            -- Cost
            sum(ifNull(cost, 0)) AS total_cost,

            -- Latency
            sum(ifNull(response_time_ms, 0)) AS sum_response_time_ms,
            sum(ifNull(ttft_ms, 0)) AS sum_ttft_ms,
            min(response_time_ms) AS min_response_time_ms,
            max(response_time_ms) AS max_response_time_ms,

            -- Unique counts (using uniqState for accurate counts across rollups)
            uniqState(user_id) AS unique_users,
            uniqState(inference_id) AS unique_inferences,
            uniqState(episode_id) AS unique_episodes,
            uniqState(api_key_id) AS unique_api_keys,

            -- Blocking metrics
            countIf(is_blocked = true) AS block_count,
            uniqStateIf(client_ip, is_blocked = true) AS unique_blocked_ips

        FROM InferenceFact
        GROUP BY
            time_bucket,
            project_id, endpoint_id, model_id, api_key_project_id,
            model_name, model_provider, endpoint_type, is_success, country_code
        """

        # MV: InferenceMetrics5m → InferenceMetrics1h
        mv_5m_to_1h = """
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_5m_to_1h TO InferenceMetrics1h AS
        SELECT
            toStartOfHour(time_bucket) AS time_bucket,

            -- Dimension UUIDs
            project_id,
            endpoint_id,
            model_id,
            api_key_project_id,

            -- String dimensions
            model_name,
            model_provider,
            endpoint_type,
            is_success,
            country_code,

            -- Counts (summed)
            sum(request_count) AS request_count,
            sum(success_count) AS success_count,
            sum(error_count) AS error_count,
            sum(cached_count) AS cached_count,

            -- Token metrics
            sum(total_input_tokens) AS total_input_tokens,
            sum(total_output_tokens) AS total_output_tokens,

            -- Cost
            sum(total_cost) AS total_cost,

            -- Latency
            sum(sum_response_time_ms) AS sum_response_time_ms,
            sum(sum_ttft_ms) AS sum_ttft_ms,
            min(min_response_time_ms) AS min_response_time_ms,
            max(max_response_time_ms) AS max_response_time_ms,

            -- Unique counts (merge states)
            uniqMergeState(unique_users) AS unique_users,
            uniqMergeState(unique_inferences) AS unique_inferences,
            uniqMergeState(unique_episodes) AS unique_episodes,
            uniqMergeState(unique_api_keys) AS unique_api_keys,

            -- Blocking metrics
            sum(block_count) AS block_count,
            uniqMergeState(unique_blocked_ips) AS unique_blocked_ips

        FROM InferenceMetrics5m
        GROUP BY
            time_bucket,
            project_id, endpoint_id, model_id, api_key_project_id,
            model_name, model_provider, endpoint_type, is_success, country_code
        """

        # MV: InferenceMetrics1h → InferenceMetrics1d
        mv_1h_to_1d = """
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_1h_to_1d TO InferenceMetrics1d AS
        SELECT
            toStartOfDay(time_bucket) AS time_bucket,

            -- Dimension UUIDs
            project_id,
            endpoint_id,
            model_id,
            api_key_project_id,

            -- String dimensions
            model_name,
            model_provider,
            endpoint_type,
            is_success,
            country_code,

            -- Counts (summed)
            sum(request_count) AS request_count,
            sum(success_count) AS success_count,
            sum(error_count) AS error_count,
            sum(cached_count) AS cached_count,

            -- Token metrics
            sum(total_input_tokens) AS total_input_tokens,
            sum(total_output_tokens) AS total_output_tokens,

            -- Cost
            sum(total_cost) AS total_cost,

            -- Latency
            sum(sum_response_time_ms) AS sum_response_time_ms,
            sum(sum_ttft_ms) AS sum_ttft_ms,
            min(min_response_time_ms) AS min_response_time_ms,
            max(max_response_time_ms) AS max_response_time_ms,

            -- Unique counts (merge states)
            uniqMergeState(unique_users) AS unique_users,
            uniqMergeState(unique_inferences) AS unique_inferences,
            uniqMergeState(unique_episodes) AS unique_episodes,
            uniqMergeState(unique_api_keys) AS unique_api_keys,

            -- Blocking metrics
            sum(block_count) AS block_count,
            uniqMergeState(unique_blocked_ips) AS unique_blocked_ips

        FROM InferenceMetrics1h
        GROUP BY
            time_bucket,
            project_id, endpoint_id, model_id, api_key_project_id,
            model_name, model_provider, endpoint_type, is_success, country_code
        """

        views = [
            ("mv_inference_to_5m", mv_inference_to_5m),
            ("mv_5m_to_1h", mv_5m_to_1h),
            ("mv_1h_to_1d", mv_1h_to_1d),
        ]

        for view_name, query in views:
            try:
                # Drop existing view to ensure clean state (optional, remove if incremental updates preferred)
                # await self.client.execute_query(f"DROP VIEW IF EXISTS {view_name}")
                await self.client.execute_query(query)
                logger.info(f"{view_name} materialized view created successfully")
            except Exception as e:
                if "already exists" in str(e).lower():
                    logger.info(f"{view_name} materialized view already exists")
                else:
                    logger.error(f"Error creating {view_name}: {e}")
                    raise

        logger.info("All InferenceMetrics materialized views created successfully")

    async def add_error_tracking_columns(self):
        """Add error tracking columns to ModelInferenceDetails table for failed inference tracking.

        This migration adds error_code, error_message, error_type, and status_code columns
        to track failed inferences and their error details.
        """
        logger.info("Adding error tracking columns to ModelInferenceDetails table...")

        # Check if the table exists first
        try:
            table_exists = await self.client.execute_query("EXISTS TABLE ModelInferenceDetails")
            if not table_exists or not table_exists[0][0]:
                logger.warning("ModelInferenceDetails table does not exist. Skipping error columns migration.")
                return
        except Exception as e:
            logger.error(f"Error checking if ModelInferenceDetails table exists: {e}")
            return

        # Define the columns to add with their types
        columns_to_add = [
            ("error_code", "Nullable(String)"),
            ("error_message", "Nullable(String)"),
            ("error_type", "Nullable(String)"),
            ("status_code", "Nullable(UInt16)"),
        ]

        # Add each column
        for column_name, column_type in columns_to_add:
            try:
                # Check if column already exists
                check_column_query = f"""  # nosec B608
                SELECT COUNT(*)
                FROM system.columns
                WHERE table = 'ModelInferenceDetails'
                  AND database = currentDatabase()
                  AND name = '{column_name}'
                """
                result = await self.client.execute_query(check_column_query)
                column_exists = result[0][0] > 0 if result else False

                if not column_exists:
                    # Add the column
                    alter_query = f"""
                    ALTER TABLE ModelInferenceDetails
                    ADD COLUMN IF NOT EXISTS {column_name} {column_type}
                    """
                    await self.client.execute_query(alter_query)
                    logger.info(f"Added column {column_name} ({column_type}) to ModelInferenceDetails table")
                else:
                    logger.info(f"Column {column_name} already exists in ModelInferenceDetails table")

            except Exception as e:
                if "already exists" in str(e).lower():
                    logger.info(f"Column {column_name} already exists")
                else:
                    logger.error(f"Error adding column {column_name}: {e}")

        # Add indexes for error columns
        indexes = [
            ("idx_error_type", "error_type", "minmax", 1),
            ("idx_status_code", "status_code", "minmax", 1),
        ]

        for index_name, column, index_type, granularity in indexes:
            index_query = f"ALTER TABLE ModelInferenceDetails ADD INDEX IF NOT EXISTS {index_name} ({column}) TYPE {index_type} GRANULARITY {granularity}"
            try:
                await self.client.execute_query(index_query)
                logger.info(f"Index {index_name} created or already exists")
            except Exception as e:
                if "already exists" not in str(e).lower():
                    logger.warning(f"Index creation warning for {index_name}: {e}")

        logger.info("Error tracking columns migration completed successfully")

    async def add_gateway_columns_to_inference_fact(self):
        """Add gateway analytics columns and error columns to existing InferenceFact table.

        This migration adds columns for:
        - Error tracking: error_code, error_message, error_type
        - Geographic: country_code, country_name, region, city, latitude, longitude, timezone, asn, isp
        - Client metadata: client_ip, user_agent, device_type, browser_name, browser_version, os_name, os_version, is_bot
        - Request context: method, path, query_params, body_size, response_size, protocol_version
        - Performance: gateway_processing_ms, total_duration_ms
        - Routing: model_version, routing_decision, is_blocked, block_reason, block_rule_id, proxy_chain
        - Headers: request_headers, response_headers, request_timestamp, response_timestamp, gateway_tags
        """
        logger.info("Adding gateway analytics columns to InferenceFact table...")

        # Check if the table exists first
        try:
            table_exists = await self.client.execute_query("EXISTS TABLE InferenceFact")
            if not table_exists or not table_exists[0][0]:
                logger.info("InferenceFact table does not exist. Skipping gateway columns migration.")
                return
        except Exception as e:
            logger.error(f"Error checking if InferenceFact table exists: {e}")
            return

        # Define the columns to add with their types and codecs
        columns_to_add = [
            # Error tracking
            ("error_code", "Nullable(String) CODEC(ZSTD(1))"),
            ("error_message", "Nullable(String) CODEC(ZSTD(3))"),
            ("error_type", "Nullable(String) CODEC(ZSTD(1))"),
            # Geographic
            ("country_code", "LowCardinality(Nullable(String)) CODEC(ZSTD(1))"),
            ("country_name", "Nullable(String) CODEC(ZSTD(1))"),
            ("region", "Nullable(String) CODEC(ZSTD(1))"),
            ("city", "Nullable(String) CODEC(ZSTD(1))"),
            ("latitude", "Nullable(Float32) CODEC(Gorilla, ZSTD(1))"),
            ("longitude", "Nullable(Float32) CODEC(Gorilla, ZSTD(1))"),
            ("timezone", "Nullable(String) CODEC(ZSTD(1))"),
            ("asn", "Nullable(UInt32) CODEC(ZSTD(1))"),
            ("isp", "Nullable(String) CODEC(ZSTD(1))"),
            # Client metadata
            ("client_ip", "Nullable(IPv4) CODEC(ZSTD(1))"),
            ("user_agent", "Nullable(String) CODEC(ZSTD(3))"),
            ("device_type", "LowCardinality(Nullable(String)) CODEC(ZSTD(1))"),
            ("browser_name", "LowCardinality(Nullable(String)) CODEC(ZSTD(1))"),
            ("browser_version", "Nullable(String) CODEC(ZSTD(1))"),
            ("os_name", "LowCardinality(Nullable(String)) CODEC(ZSTD(1))"),
            ("os_version", "Nullable(String) CODEC(ZSTD(1))"),
            ("is_bot", "Nullable(Bool) CODEC(ZSTD(1))"),
            # Request context
            ("method", "LowCardinality(Nullable(String)) CODEC(ZSTD(1))"),
            ("path", "Nullable(String) CODEC(ZSTD(1))"),
            ("query_params", "Nullable(String) CODEC(ZSTD(1))"),
            ("body_size", "Nullable(UInt32) CODEC(ZSTD(1))"),
            ("response_size", "Nullable(UInt32) CODEC(ZSTD(1))"),
            ("protocol_version", "Nullable(String) CODEC(ZSTD(1))"),
            # Performance
            ("gateway_processing_ms", "Nullable(UInt32) CODEC(Delta, ZSTD(1))"),
            ("total_duration_ms", "Nullable(UInt32) CODEC(Delta, ZSTD(1))"),
            # Routing & blocking
            ("model_version", "Nullable(String) CODEC(ZSTD(1))"),
            ("routing_decision", "LowCardinality(Nullable(String)) CODEC(ZSTD(1))"),
            ("is_blocked", "Nullable(Bool) CODEC(ZSTD(1))"),
            ("block_reason", "Nullable(String) CODEC(ZSTD(1))"),
            ("block_rule_id", "Nullable(String) CODEC(ZSTD(1))"),
            ("proxy_chain", "Nullable(String) CODEC(ZSTD(1))"),
            # Headers & timestamps
            ("request_headers", "Nullable(String) CODEC(ZSTD(3))"),
            ("response_headers", "Nullable(String) CODEC(ZSTD(3))"),
            ("request_timestamp", "Nullable(DateTime64(3)) CODEC(Delta, ZSTD(1))"),
            ("response_timestamp", "Nullable(DateTime64(3)) CODEC(Delta, ZSTD(1))"),
            ("gateway_tags", "Nullable(String) CODEC(ZSTD(1))"),
        ]

        # Add each column
        for column_name, column_type in columns_to_add:
            try:
                # Check if column already exists
                check_column_query = f"""
                SELECT COUNT(*)
                FROM system.columns
                WHERE table = 'InferenceFact'
                  AND database = currentDatabase()
                  AND name = '{column_name}'
                """  # nosec B608
                result = await self.client.execute_query(check_column_query)
                column_exists = result[0][0] > 0 if result else False

                if not column_exists:
                    # Add the column
                    alter_query = f"""
                    ALTER TABLE InferenceFact
                    ADD COLUMN IF NOT EXISTS {column_name} {column_type}
                    """
                    await self.client.execute_query(alter_query)
                    logger.info(f"Added column {column_name} to InferenceFact table")
                else:
                    logger.debug(f"Column {column_name} already exists in InferenceFact table")

            except Exception as e:
                if "already exists" in str(e).lower():
                    logger.debug(f"Column {column_name} already exists")
                else:
                    logger.error(f"Error adding column {column_name}: {e}")

        # Add indexes for new columns
        indexes = [
            ("idx_country_code", "country_code", "set(300)", 4),
            ("idx_city", "city", "bloom_filter(0.01)", 4),
            ("idx_device_type", "device_type", "set(20)", 4),
            ("idx_is_bot", "is_bot", "minmax", 4),
            ("idx_client_ip", "client_ip", "bloom_filter(0.01)", 8),
            ("idx_is_blocked", "is_blocked", "minmax", 4),
            ("idx_routing_decision", "routing_decision", "set(20)", 4),
            ("idx_error_type", "error_type", "set(50)", 4),
        ]

        for index_name, column, index_type, granularity in indexes:
            index_query = f"ALTER TABLE InferenceFact ADD INDEX IF NOT EXISTS {index_name} ({column}) TYPE {index_type} GRANULARITY {granularity}"
            try:
                await self.client.execute_query(index_query)
                logger.debug(f"Index {index_name} created or already exists")
            except Exception as e:
                if "already exists" not in str(e).lower():
                    logger.warning(f"Index creation warning for {index_name}: {e}")

        logger.info("Gateway analytics columns migration to InferenceFact completed successfully")

    async def add_blocking_columns_to_inference_fact(self):
        """Add blocking event columns to existing InferenceFact table.

        This migration adds columns for detailed blocking event data:
        - blocking_event_id: UUID of the blocking event
        - rule_id: UUID of the rule that triggered the block
        - rule_type: Type of blocking rule (e.g., 'rate_limit', 'geo_block')
        - rule_name: Human-readable rule name
        - rule_priority: Priority of the rule
        - block_reason_detail: Detailed reason for the block
        - action_taken: Action taken (e.g., 'block', 'allow', 'log')
        - blocked_at: Timestamp when the request was blocked
        """
        logger.info("Adding blocking event columns to InferenceFact table...")

        # Check if the table exists first
        try:
            table_exists = await self.client.execute_query("EXISTS TABLE InferenceFact")
            if not table_exists or not table_exists[0][0]:
                logger.info("InferenceFact table does not exist. Skipping blocking columns migration.")
                return
        except Exception as e:
            logger.error(f"Error checking if InferenceFact table exists: {e}")
            return

        # Define the columns to add with their types and codecs
        columns_to_add = [
            ("blocking_event_id", "Nullable(UUID) CODEC(ZSTD(1))"),
            ("rule_id", "Nullable(UUID) CODEC(ZSTD(1))"),
            ("rule_type", "LowCardinality(Nullable(String)) CODEC(ZSTD(1))"),
            ("rule_name", "Nullable(String) CODEC(ZSTD(1))"),
            ("rule_priority", "Nullable(Int32) CODEC(ZSTD(1))"),
            ("block_reason_detail", "Nullable(String) CODEC(ZSTD(1))"),
            ("action_taken", "LowCardinality(Nullable(String)) CODEC(ZSTD(1))"),
            ("blocked_at", "Nullable(DateTime64(3)) CODEC(Delta, ZSTD(1))"),
        ]

        for column_name, column_type in columns_to_add:
            try:
                # Check if column already exists
                check_column_query = f"""
                SELECT COUNT(*)
                FROM system.columns
                WHERE table = 'InferenceFact'
                  AND database = currentDatabase()
                  AND name = '{column_name}'
                """
                result = await self.client.execute_query(check_column_query)
                column_exists = result[0][0] > 0 if result else False

                if not column_exists:
                    alter_query = f"""
                    ALTER TABLE InferenceFact
                    ADD COLUMN IF NOT EXISTS {column_name} {column_type}
                    """
                    await self.client.execute_query(alter_query)
                    logger.info(f"Added column {column_name} to InferenceFact table")
                else:
                    logger.debug(f"Column {column_name} already exists in InferenceFact table")

            except Exception as e:
                if "already exists" in str(e).lower():
                    logger.debug(f"Column {column_name} already exists")
                else:
                    logger.error(f"Error adding column {column_name}: {e}")

        # Add indexes for blocking columns
        indexes = [
            ("idx_rule_id", "rule_id", "bloom_filter(0.01)", 4),
            ("idx_rule_type", "rule_type", "set(20)", 4),
            ("idx_action_taken", "action_taken", "set(10)", 4),
        ]

        for index_name, column, index_type, granularity in indexes:
            index_query = f"ALTER TABLE InferenceFact ADD INDEX IF NOT EXISTS {index_name} ({column}) TYPE {index_type} GRANULARITY {granularity}"
            try:
                await self.client.execute_query(index_query)
                logger.debug(f"Index {index_name} created or already exists")
            except Exception as e:
                if "already exists" not in str(e).lower():
                    logger.warning(f"Index creation warning for {index_name}: {e}")

        logger.info("Blocking event columns migration to InferenceFact completed successfully")

    async def create_mv_otel_blocking_to_inference_fact(self):
        """Create Materialized View for blocked-only requests to InferenceFact.

        This MV captures gateway_analytics spans with blocking events that never reached inference.
        It uses NOT EXISTS to avoid duplicates (in case both spans exist for the same trace).

        Key insight: The main MV (mv_otel_to_inference_fact) only triggers when an
        inference_handler_observability span exists. Blocked requests are stopped BEFORE
        reaching inference, so they only have a gateway_analytics span. This MV captures
        those blocked-only requests.
        """
        logger.info("Creating mv_otel_blocking_to_inference_fact materialized view...")

        # First drop existing view if it exists to ensure clean state
        try:
            await self.client.execute_query("DROP VIEW IF EXISTS mv_otel_blocking_to_inference_fact")
            logger.info("Dropped existing mv_otel_blocking_to_inference_fact (if any)")
        except Exception as e:
            logger.warning(f"Could not drop existing view: {e}")

        query = """
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_otel_blocking_to_inference_fact TO InferenceFact AS
        SELECT
            -- ===== OTel TRACE IDENTIFIERS =====
            -- Note: GROUP BY TraceId with any() ensures only ONE row per trace is inserted,
            -- even if multiple gateway_analytics spans arrive in the same batch.
            -- This prevents duplicates that can occur when NOT EXISTS checks don't see
            -- uncommitted/unmerged rows from concurrent inserts.
            generateUUIDv4() AS id,
            TraceId AS trace_id,
            any(g.SpanId) AS span_id,

            -- ===== CORE IDENTIFIERS (from gateway_analytics span) =====
            -- No inference_id for blocked requests
            any(CAST(NULL AS Nullable(UUID))) AS inference_id,
            any(toUUIDOrNull(nullIf(g.SpanAttributes['gateway_analytics.project_id'], ''))) AS project_id,
            any(toUUIDOrNull(nullIf(g.SpanAttributes['gateway_analytics.endpoint_id'], ''))) AS endpoint_id,
            any(toUUIDOrNull(nullIf(g.SpanAttributes['gateway_analytics.model_id'], ''))) AS model_id,
            any(toUUIDOrNull(nullIf(g.SpanAttributes['gateway_analytics.api_key_id'], ''))) AS api_key_id,
            any(toUUIDOrNull(nullIf(g.SpanAttributes['gateway_analytics.api_key_project_id'], ''))) AS api_key_project_id,
            any(nullIf(g.SpanAttributes['gateway_analytics.user_id'], '')) AS user_id,

            -- ===== TIMESTAMPS =====
            any(toDateTime64(g.Timestamp, 3)) AS timestamp,
            any(parseDateTime64BestEffortOrNull(g.SpanAttributes['gateway_analytics.request_timestamp'])) AS request_arrival_time,
            any(parseDateTime64BestEffortOrNull(g.SpanAttributes['gateway_analytics.request_timestamp'])) AS request_forward_time,

            -- ===== STATUS (blocked = failed) =====
            any(false) AS is_success,
            any(CAST(NULL AS Nullable(Float64))) AS cost,
            any(toUInt16OrNull(g.SpanAttributes['gateway_analytics.status_code'])) AS status_code,
            any(toIPv4OrNull(g.SpanAttributes['gateway_analytics.client_ip'])) AS request_ip,
            any(CAST(NULL AS Nullable(String))) AS response_analysis,

            -- ===== ERROR TRACKING =====
            any('BLOCKED') AS error_code,
            any(nullIf(g.SpanAttributes['gateway_analytics.error_message'], '')) AS error_message,
            any(nullIf(g.SpanAttributes['gateway_analytics.error_type'], '')) AS error_type,

            -- ===== MODEL INFO (from gateway_analytics if available) =====
            -- model_name and model_provider are LowCardinality(String) (non-nullable)
            -- so we must provide empty string instead of NULL
            any(CAST(NULL AS Nullable(UUID))) AS model_inference_id,
            any(g.SpanAttributes['gateway_analytics.model_name']) AS model_name,
            any(g.SpanAttributes['gateway_analytics.model_provider']) AS model_provider,
            any('blocked') AS endpoint_type,

            -- ===== PERFORMANCE METRICS (zeros for blocked requests) =====
            any(CAST(0 AS Nullable(UInt32))) AS input_tokens,
            any(CAST(0 AS Nullable(UInt32))) AS output_tokens,
            any(CAST(NULL AS Nullable(UInt32))) AS response_time_ms,
            any(CAST(NULL AS Nullable(UInt32))) AS ttft_ms,
            any(false) AS cached,
            any(CAST(NULL AS Nullable(String))) AS finish_reason,

            -- ===== CONTENT (empty for blocked requests) =====
            any(CAST(NULL AS Nullable(String))) AS system_prompt,
            any(CAST(NULL AS Nullable(String))) AS input_messages,
            any(CAST(NULL AS Nullable(String))) AS output,
            any(CAST(NULL AS Nullable(String))) AS raw_request,
            any(CAST(NULL AS Nullable(String))) AS raw_response,
            any(CAST(NULL AS Nullable(String))) AS gateway_request,
            any(CAST(NULL AS Nullable(String))) AS gateway_response,
            any(CAST(NULL AS Nullable(String))) AS guardrail_scan_summary,
            any(CAST(NULL AS Nullable(UInt64))) AS model_inference_timestamp,

            -- ===== CHAT INFERENCE (empty for blocked requests) =====
            any(CAST(NULL AS Nullable(UUID))) AS chat_inference_id,
            any(CAST(NULL AS Nullable(UUID))) AS episode_id,
            any(CAST(NULL AS Nullable(String))) AS function_name,
            any(CAST(NULL AS Nullable(String))) AS variant_name,
            any(CAST(NULL AS Nullable(UInt32))) AS processing_time_ms,
            any(CAST(NULL AS Nullable(String))) AS chat_input,
            any(CAST(NULL AS Nullable(String))) AS chat_output,
            any(CAST(NULL AS Nullable(String))) AS tags,
            any(CAST(NULL AS Nullable(String))) AS inference_params,
            any(CAST(NULL AS Nullable(String))) AS extra_body,
            any(CAST(NULL AS Nullable(String))) AS tool_params,

            -- ===== GATEWAY ANALYTICS (full data available) =====
            any(nullIf(g.SpanAttributes['gateway_analytics.country_code'], '')) AS country_code,
            any(nullIf(g.SpanAttributes['gateway_analytics.country_name'], '')) AS country_name,
            any(nullIf(g.SpanAttributes['gateway_analytics.region'], '')) AS region,
            any(nullIf(g.SpanAttributes['gateway_analytics.city'], '')) AS city,
            any(toFloat32OrNull(g.SpanAttributes['gateway_analytics.latitude'])) AS latitude,
            any(toFloat32OrNull(g.SpanAttributes['gateway_analytics.longitude'])) AS longitude,
            any(nullIf(g.SpanAttributes['gateway_analytics.timezone'], '')) AS timezone,
            any(toUInt32OrNull(g.SpanAttributes['gateway_analytics.asn'])) AS asn,
            any(nullIf(g.SpanAttributes['gateway_analytics.isp'], '')) AS isp,
            any(toIPv4OrNull(g.SpanAttributes['gateway_analytics.client_ip'])) AS client_ip,
            any(nullIf(g.SpanAttributes['gateway_analytics.user_agent'], '')) AS user_agent,
            any(nullIf(g.SpanAttributes['gateway_analytics.device_type'], '')) AS device_type,
            any(nullIf(g.SpanAttributes['gateway_analytics.browser_name'], '')) AS browser_name,
            any(nullIf(g.SpanAttributes['gateway_analytics.browser_version'], '')) AS browser_version,
            any(nullIf(g.SpanAttributes['gateway_analytics.os_name'], '')) AS os_name,
            any(nullIf(g.SpanAttributes['gateway_analytics.os_version'], '')) AS os_version,
            any(g.SpanAttributes['gateway_analytics.is_bot'] = 'true') AS is_bot,
            any(nullIf(g.SpanAttributes['gateway_analytics.method'], '')) AS method,
            any(nullIf(g.SpanAttributes['gateway_analytics.path'], '')) AS path,
            any(nullIf(g.SpanAttributes['gateway_analytics.query_params'], '')) AS query_params,
            any(toUInt32OrNull(g.SpanAttributes['gateway_analytics.body_size'])) AS body_size,
            any(toUInt32OrNull(g.SpanAttributes['gateway_analytics.response_size'])) AS response_size,
            any(nullIf(g.SpanAttributes['gateway_analytics.protocol_version'], '')) AS protocol_version,
            any(toUInt32OrNull(g.SpanAttributes['gateway_analytics.gateway_processing_ms'])) AS gateway_processing_ms,
            any(toUInt32OrNull(g.SpanAttributes['gateway_analytics.total_duration_ms'])) AS total_duration_ms,
            any(nullIf(g.SpanAttributes['gateway_analytics.model_version'], '')) AS model_version,
            any(nullIf(g.SpanAttributes['gateway_analytics.routing_decision'], '')) AS routing_decision,
            any(true) AS is_blocked,  -- Always true for this MV
            any(nullIf(g.SpanAttributes['gateway_analytics.block_reason'], '')) AS block_reason,
            any(nullIf(g.SpanAttributes['gateway_analytics.block_rule_id'], '')) AS block_rule_id,
            any(nullIf(g.SpanAttributes['gateway_analytics.proxy_chain'], '')) AS proxy_chain,
            any(nullIf(g.SpanAttributes['gateway_analytics.request_headers'], '')) AS request_headers,
            any(nullIf(g.SpanAttributes['gateway_analytics.response_headers'], '')) AS response_headers,
            any(parseDateTime64BestEffortOrNull(g.SpanAttributes['gateway_analytics.request_timestamp'])) AS request_timestamp,
            any(parseDateTime64BestEffortOrNull(g.SpanAttributes['gateway_analytics.response_timestamp'])) AS response_timestamp,
            any(nullIf(g.SpanAttributes['gateway_analytics.tags'], '')) AS gateway_tags,

            -- ===== BLOCKING EVENT DATA =====
            any(toUUIDOrNull(nullIf(g.SpanAttributes['gateway_blocking_events.id'], ''))) AS blocking_event_id,
            any(toUUIDOrNull(nullIf(g.SpanAttributes['gateway_blocking_events.rule_id'], ''))) AS rule_id,
            any(nullIf(g.SpanAttributes['gateway_blocking_events.rule_type'], '')) AS rule_type,
            any(nullIf(g.SpanAttributes['gateway_blocking_events.rule_name'], '')) AS rule_name,
            any(toInt32OrNull(g.SpanAttributes['gateway_blocking_events.rule_priority'])) AS rule_priority,
            any(nullIf(g.SpanAttributes['gateway_blocking_events.block_reason'], '')) AS block_reason_detail,
            any(nullIf(g.SpanAttributes['gateway_blocking_events.action_taken'], '')) AS action_taken,
            any(parseDateTime64BestEffortOrNull(g.SpanAttributes['gateway_blocking_events.blocked_at'])) AS blocked_at

        FROM metrics.otel_traces g
        WHERE g.SpanName = 'gateway_analytics'
          AND g.SpanAttributes['gateway_blocking_events.id'] != ''
          AND g.SpanAttributes['gateway_blocking_events.action_taken'] = 'block'
          -- PRODUCTION FIX: Commented out NOT EXISTS - ClickHouse doesn't support correlated subqueries
          -- AND NOT EXISTS (
          --     -- Exclude if there's already a row for this trace in InferenceFact
          --     -- This prevents duplicates when multiple gateway_analytics spans exist
          --     SELECT 1 FROM InferenceFact f
          --     WHERE f.trace_id = g.TraceId
          -- )
          -- Deduplication is handled by:
          -- 1. GROUP BY TraceId - ensures one row per trace within each batch
          -- 2. ReplacingMergeTree - handles cross-batch deduplication at merge time
          -- 3. The fact that blocked requests never reach inference (no overlap)
        GROUP BY TraceId
        """

        try:
            await self.client.execute_query(query)
            logger.info("mv_otel_blocking_to_inference_fact materialized view created successfully")
        except Exception as e:
            logger.error(f"Error creating mv_otel_blocking_to_inference_fact: {e}")
            raise

    async def add_blocking_metrics_to_rollup_tables(self):
        """Add blocking metrics columns to InferenceMetrics rollup tables.

        This migration adds block_count and unique_blocked_ips columns to:
        - InferenceMetrics5m
        - InferenceMetrics1h
        - InferenceMetrics1d

        These columns enable efficient querying of blocking statistics.
        """
        logger.info("Adding blocking metrics columns to rollup tables...")

        tables = ["InferenceMetrics5m", "InferenceMetrics1h", "InferenceMetrics1d"]

        for table_name in tables:
            try:
                # Check if table exists
                table_exists = await self.client.execute_query(f"EXISTS TABLE {table_name}")
                if not table_exists or not table_exists[0][0]:
                    logger.info(f"{table_name} table does not exist. Skipping blocking metrics migration.")
                    continue

                # Define columns to add
                columns_to_add = [
                    ("block_count", "UInt64 DEFAULT 0 CODEC(Delta, ZSTD(1))"),
                    ("unique_blocked_ips", "AggregateFunction(uniq, IPv4)"),
                ]

                for column_name, column_type in columns_to_add:
                    try:
                        # Check if column already exists
                        check_column_query = f"""
                        SELECT COUNT(*)
                        FROM system.columns
                        WHERE table = '{table_name}'
                          AND database = currentDatabase()
                          AND name = '{column_name}'
                        """
                        result = await self.client.execute_query(check_column_query)
                        column_exists = result[0][0] > 0 if result else False

                        if not column_exists:
                            alter_query = f"""
                            ALTER TABLE {table_name}
                            ADD COLUMN IF NOT EXISTS {column_name} {column_type}
                            """
                            await self.client.execute_query(alter_query)
                            logger.info(f"Added column {column_name} to {table_name} table")
                        else:
                            logger.debug(f"Column {column_name} already exists in {table_name} table")

                    except Exception as e:
                        if "already exists" in str(e).lower():
                            logger.debug(f"Column {column_name} already exists in {table_name}")
                        else:
                            logger.error(f"Error adding column {column_name} to {table_name}: {e}")

            except Exception as e:
                logger.error(f"Error adding blocking metrics to {table_name}: {e}")

        logger.info("Blocking metrics columns migration to rollup tables completed successfully")

    async def make_metrics_dimension_columns_nullable(self):
        """Make dimension columns nullable in InferenceMetrics rollup tables.

        Blocked requests don't have project_id, endpoint_id, or model_id (they're blocked
        before routing to a model). Since these columns are part of the ORDER BY (primary key),
        we need to recreate the tables with nullable columns.

        This fixes duplicate inserts in otel_traces caused by the OTel Collector retrying
        when MV inserts fail due to NULL values in non-nullable columns.
        """
        logger.info("Checking if dimension columns need to be made nullable in rollup tables...")

        tables = ["InferenceMetrics5m", "InferenceMetrics1h", "InferenceMetrics1d"]
        mvs = ["mv_inference_to_5m", "mv_5m_to_1h", "mv_1h_to_1d"]

        needs_recreation = False

        # First check if any table needs recreation
        for table_name in tables:
            try:
                table_exists = await self.client.execute_query(f"EXISTS TABLE {table_name}")
                if not table_exists or not table_exists[0][0]:
                    continue

                check_query = f"""
                SELECT type
                FROM system.columns
                WHERE database = currentDatabase()
                  AND table = '{table_name}'
                  AND name = 'project_id'
                """
                result = await self.client.execute_query(check_query)

                if result and result[0][0] and "Nullable" not in result[0][0]:
                    needs_recreation = True
                    break
            except Exception as e:
                logger.error(f"Error checking {table_name}: {e}")

        if not needs_recreation:
            logger.info("Dimension columns are already nullable, no recreation needed")
            return

        logger.info("Dimension columns are not nullable, recreating tables...")

        # Drop MVs first (they reference the tables)
        for mv_name in mvs:
            try:
                await self.client.execute_query(f"DROP VIEW IF EXISTS {mv_name}")
                logger.info(f"Dropped MV {mv_name}")
            except Exception as e:
                logger.debug(f"Could not drop MV {mv_name}: {e}")

        # Drop tables
        for table_name in tables:
            try:
                await self.client.execute_query(f"DROP TABLE IF EXISTS {table_name}")
                logger.info(f"Dropped {table_name} for recreation with nullable columns")
            except Exception as e:
                logger.error(f"Error dropping {table_name}: {e}")

        logger.info("Dimension columns nullable migration completed - tables will be recreated")

    async def setup_cluster_metrics_materialized_views(self):
        """Set up materialized views for cluster metrics.

        This executes the setup_cluster_metrics_materialized_views.sql script
        which creates materialized views that automatically populate NodeMetrics,
        PodMetrics, and ClusterMetrics tables from otel_metrics_gauge.
        """
        logger.info("Setting up cluster metrics materialized views...")

        sql_file_path = Path(__file__).parent / "setup_cluster_metrics_materialized_views.sql"

        if not sql_file_path.exists():
            logger.warning(
                f"Cluster metrics materialized views SQL file not found at {sql_file_path}. "
                "Skipping materialized views setup."
            )
            return

        try:
            # Read the SQL file
            with open(sql_file_path, "r") as f:
                sql_content = f.read()

            # Split into individual statements (separated by semicolons)
            # Remove comments and empty lines
            statements = []
            for statement in sql_content.split(";"):
                # Remove SQL comments (-- style)
                lines = []
                for line in statement.split("\n"):
                    # Remove inline comments
                    if "--" in line:
                        line = line[: line.index("--")]
                    line = line.strip()
                    if line:
                        lines.append(line)

                clean_statement = " ".join(lines)
                if clean_statement and not clean_statement.startswith("--"):
                    statements.append(clean_statement)

            # Execute each statement
            logger.info(f"Executing {len(statements)} SQL statements from materialized views script...")

            for i, statement in enumerate(statements, 1):
                try:
                    # Skip comments and empty statements
                    if not statement.strip() or statement.strip().startswith("--"):
                        continue

                    # Log what we're executing (first 100 chars)
                    preview = statement[:100] + ("..." if len(statement) > 100 else "")
                    logger.info(f"  [{i}/{len(statements)}] {preview}")

                    await self.client.execute_query(statement)

                except Exception as e:
                    # Some statements may fail if objects already exist - that's okay
                    error_msg = str(e).lower()
                    if "already exists" in error_msg or "duplicate" in error_msg:
                        logger.info("    Skipped (already exists)")
                    else:
                        logger.warning(f"    Statement execution warning: {e}")

            logger.info("✓ Cluster metrics materialized views setup completed successfully")

        except Exception as e:
            logger.error(f"Error setting up cluster metrics materialized views: {e}")
            raise

    async def create_hami_slice_metrics_materialized_view(self):
        """Create or recreate the HAMI Slice Metrics materialized view.

        This view populates HAMISliceMetrics from vGPU* metrics in otel_metrics_gauge,
        providing per-pod/container GPU allocation data for time-slicing.

        NOTE: Uses REFRESH EVERY 1 MINUTE (Refreshable MV) instead of streaming MV because
        streaming MVs with complex JOINs between CTEs don't work correctly in ClickHouse.
        Each CTE filters different MetricNames, and streaming MVs only see the current INSERT
        batch, causing JOINs to fail. Refreshable MVs run on a schedule and see all data.
        """
        logger.info("Setting up HAMI Slice Metrics materialized view (Refreshable)...")

        try:
            # Drop existing view to ensure we get the latest definition
            await self.client.execute_query("DROP VIEW IF EXISTS metrics.mv_populate_hami_slice_metrics")
            logger.info("Dropped existing mv_populate_hami_slice_metrics (if any)")

            # Create the refreshable materialized view
            # Uses REFRESH EVERY 1 MINUTE to periodically aggregate vGPU metrics
            # Uses device plugin metrics (vGPU_device_memory_limit/usage) for accurate per-container data
            mv_query = """
            CREATE MATERIALIZED VIEW metrics.mv_populate_hami_slice_metrics
            REFRESH EVERY 1 MINUTE
            TO metrics.HAMISliceMetrics
            AS
            WITH
            -- Memory limit from device plugin (per-container limit)
            memory_limit AS (
                SELECT
                    toDateTime64(toStartOfInterval(TimeUnix, INTERVAL 1 MINUTE), 3) AS ts,
                    ResourceAttributes['cluster_id'] AS cluster_id,
                    Attributes['deviceuuid'] AS device_uuid,
                    Attributes['podname'] AS pod_name,
                    Attributes['podnamespace'] AS pod_namespace,
                    Attributes['ctrname'] AS container_name,
                    avg(Value) AS memory_limit_bytes
                FROM metrics.otel_metrics_gauge
                WHERE MetricName = 'vGPU_device_memory_limit_in_bytes'
                  AND ResourceAttributes['cluster_id'] IS NOT NULL
                  AND ResourceAttributes['cluster_id'] != ''
                  AND Attributes['deviceuuid'] IS NOT NULL
                  AND Attributes['podname'] IS NOT NULL
                  AND TimeUnix >= now() - INTERVAL 5 MINUTE
                GROUP BY ts, cluster_id, device_uuid, pod_name, pod_namespace, container_name
            ),
            -- Memory usage from device plugin (actual per-container usage)
            memory_usage AS (
                SELECT
                    toDateTime64(toStartOfInterval(TimeUnix, INTERVAL 1 MINUTE), 3) AS ts,
                    ResourceAttributes['cluster_id'] AS cluster_id,
                    Attributes['deviceuuid'] AS device_uuid,
                    Attributes['podname'] AS pod_name,
                    Attributes['podnamespace'] AS pod_namespace,
                    Attributes['ctrname'] AS container_name,
                    avg(Value) AS memory_used_bytes
                FROM metrics.otel_metrics_gauge
                WHERE MetricName = 'vGPU_device_memory_usage_in_bytes'
                  AND ResourceAttributes['cluster_id'] IS NOT NULL
                  AND ResourceAttributes['cluster_id'] != ''
                  AND Attributes['deviceuuid'] IS NOT NULL
                  AND Attributes['podname'] IS NOT NULL
                  AND TimeUnix >= now() - INTERVAL 5 MINUTE
                GROUP BY ts, cluster_id, device_uuid, pod_name, pod_namespace, container_name
            ),
            -- Core metrics from scheduler
            core_metrics AS (
                SELECT
                    toDateTime64(toStartOfInterval(TimeUnix, INTERVAL 1 MINUTE), 3) AS ts,
                    ResourceAttributes['cluster_id'] AS cluster_id,
                    Attributes['deviceuuid'] AS device_uuid,
                    Attributes['podname'] AS pod_name,
                    Attributes['podnamespace'] AS pod_namespace,
                    avg(Value) AS core_used_percent
                FROM metrics.otel_metrics_gauge
                WHERE MetricName = 'vGPUCorePercentage'
                  AND ResourceAttributes['cluster_id'] IS NOT NULL
                  AND ResourceAttributes['cluster_id'] != ''
                  AND Attributes['deviceuuid'] IS NOT NULL
                  AND Attributes['podname'] IS NOT NULL
                  AND TimeUnix >= now() - INTERVAL 5 MINUTE
                GROUP BY ts, cluster_id, device_uuid, pod_name, pod_namespace
            ),
            -- Device info for device_index and node_name
            device_info AS (
                SELECT
                    cluster_id,
                    device_uuid,
                    argMax(device_index, ts) AS device_index,
                    argMax(node_name, ts) AS node_name
                FROM metrics.HAMIGPUMetrics
                WHERE cluster_id IS NOT NULL AND device_uuid IS NOT NULL
                GROUP BY cluster_id, device_uuid
            )
            -- Note: Pod status is joined at query time in repository.py
            -- using kube_pod_status_phase for accurate real-time status
            SELECT
                l.ts AS ts,
                l.cluster_id AS cluster_id,
                COALESCE(d.node_name, '') AS node_name,
                l.device_uuid AS device_uuid,
                COALESCE(d.device_index, 0) AS device_index,
                l.pod_name AS pod_name,
                l.pod_namespace AS pod_namespace,
                l.container_name AS container_name,
                toInt64(l.memory_limit_bytes) AS memory_limit_bytes,
                toInt64(COALESCE(u.memory_used_bytes, 0)) AS memory_used_bytes,
                100.0 AS core_limit_percent,
                COALESCE(c.core_used_percent, 0) AS core_used_percent,
                COALESCE(c.core_used_percent, 0) AS gpu_utilization_percent,
                -- Status is determined at query time by joining with kube_pod_status_phase
                'unknown' AS status
            FROM memory_limit l
            LEFT JOIN memory_usage u
                ON l.ts = u.ts
                AND l.cluster_id = u.cluster_id
                AND l.device_uuid = u.device_uuid
                AND l.pod_name = u.pod_name
                AND l.pod_namespace = u.pod_namespace
                AND l.container_name = u.container_name
            LEFT JOIN core_metrics c
                ON l.ts = c.ts
                AND l.cluster_id = c.cluster_id
                AND l.device_uuid = c.device_uuid
                AND l.pod_name = c.pod_name
                AND l.pod_namespace = c.pod_namespace
            LEFT JOIN device_info d
                ON l.cluster_id = d.cluster_id
                AND l.device_uuid = d.device_uuid
            """

            await self.client.execute_query(mv_query)
            logger.info("✓ Created mv_populate_hami_slice_metrics materialized view")

        except Exception as e:
            logger.error(f"Error creating HAMI Slice Metrics materialized view: {e}")
            raise

    async def migrate_hami_gpu_metrics_dcgm_columns(self):
        """Add DCGM hardware metrics columns to HAMIGPUMetrics table.

        This migration adds columns for DCGM Exporter data (temperature, power, clocks)
        that enrich the HAMI time-slicing metrics with hardware-level data.
        """
        logger.info("Adding DCGM columns to HAMIGPUMetrics table...")

        table_ref = "metrics.HAMIGPUMetrics"

        try:
            # Check which columns already exist
            existing_columns_query = """
            SELECT name FROM system.columns
            WHERE database = 'metrics' AND table = 'HAMIGPUMetrics'
            """
            existing_columns_result = await self.client.execute_query(existing_columns_query)
            existing_col_names = {row[0] for row in existing_columns_result} if existing_columns_result else set()

            # Columns to add
            new_columns = {
                "temperature_celsius": "Float64 DEFAULT 0",
                "power_watts": "Float64 DEFAULT 0",
                "sm_clock_mhz": "UInt32 DEFAULT 0",
                "mem_clock_mhz": "UInt32 DEFAULT 0",
                "gpu_utilization_percent": "Float64 DEFAULT 0",
            }

            columns_to_add = []
            for col_name, col_type in new_columns.items():
                if col_name not in existing_col_names:
                    columns_to_add.append(f"ADD COLUMN IF NOT EXISTS {col_name} {col_type}")

            if columns_to_add:
                alter_query = f"ALTER TABLE {table_ref} {', '.join(columns_to_add)}"
                await self.client.execute_query(alter_query)
                logger.info(f"Added DCGM columns to HAMIGPUMetrics: {list(new_columns.keys())}")
            else:
                logger.info("DCGM columns already exist in HAMIGPUMetrics")

        except Exception as e:
            logger.error(f"Error adding DCGM columns to HAMIGPUMetrics: {e}")
            raise

    async def migrate_node_metrics_network_columns(self):
        """Add network columns to existing NodeMetrics table for legacy deployments.

        This migration adds network_receive_bytes_per_sec and network_transmit_bytes_per_sec
        columns to NodeMetrics tables that were created before these columns were added.
        """
        logger.info("Checking if NodeMetrics network columns migration is needed...")

        # Check if NodeMetrics table exists (check both budproxy and metrics databases)
        try:
            # Check in metrics database first (new location)
            table_exists = await self.client.execute_query("EXISTS TABLE metrics.NodeMetrics")
            database = "metrics"
            if not table_exists or not table_exists[0][0]:
                # Fallback to budproxy database (legacy location)
                table_exists = await self.client.execute_query("EXISTS TABLE NodeMetrics")
                database = self.config.database
                if not table_exists or not table_exists[0][0]:
                    logger.info("NodeMetrics table does not exist yet. Skipping network columns migration.")
                    return
        except Exception as e:
            logger.warning(f"Error checking if NodeMetrics table exists: {e}")
            return

        # Check which network columns are missing
        check_columns_query = f"""  # nosec B608
        SELECT name FROM system.columns
        WHERE database = '{database}'
        AND table = 'NodeMetrics'
        AND name IN ('network_receive_bytes_per_sec', 'network_transmit_bytes_per_sec')
        """

        try:
            existing_columns_result = await self.client.execute_query(check_columns_query)
            existing_columns = {row[0] for row in existing_columns_result} if existing_columns_result else set()

            columns_to_add = []
            if "network_receive_bytes_per_sec" not in existing_columns:
                columns_to_add.append("ADD COLUMN IF NOT EXISTS network_receive_bytes_per_sec Float64 DEFAULT 0")
            if "network_transmit_bytes_per_sec" not in existing_columns:
                columns_to_add.append("ADD COLUMN IF NOT EXISTS network_transmit_bytes_per_sec Float64 DEFAULT 0")

            if columns_to_add:
                # Add the missing columns
                table_ref = f"{database}.NodeMetrics" if database != self.config.database else "NodeMetrics"
                alter_query = f"ALTER TABLE {table_ref} {', '.join(columns_to_add)}"
                await self.client.execute_query(alter_query)
                logger.info(
                    f"✓ Added network columns to NodeMetrics: {', '.join(col.split()[-3] for col in columns_to_add)}"
                )
            else:
                logger.info("✓ NodeMetrics already has network columns")

        except Exception as e:
            logger.error(f"Error adding network columns to NodeMetrics: {e}")
            raise

    async def migrate_inference_tables_ttl_90_days(self):
        """Update TTL to 90 days for all inference-related tables.

        This migration updates the TTL from their previous values to 90 days:
        - InferenceFact: 30 days -> 90 days
        - InferenceMetrics5m: 30 days -> 90 days
        - InferenceMetrics1h: 30 days -> 90 days
        - InferenceMetrics1d: 60 days -> 90 days
        """
        logger.info("Checking if inference tables TTL migration to 90 days is needed...")

        ttl_updates = [
            ("InferenceFact", "toDateTime(timestamp) + INTERVAL 90 DAY"),
            ("InferenceMetrics5m", "time_bucket + INTERVAL 90 DAY"),
            ("InferenceMetrics1h", "time_bucket + INTERVAL 90 DAY"),
            ("InferenceMetrics1d", "time_bucket + INTERVAL 90 DAY"),
        ]

        for table_name, ttl_expression in ttl_updates:
            try:
                # Check if table exists
                table_exists = await self.client.execute_query(f"EXISTS TABLE {table_name}")
                if not table_exists or not table_exists[0][0]:
                    logger.info(f"{table_name} table does not exist yet. Skipping TTL migration.")
                    continue

                # Check current TTL - look for 90 DAY in the CREATE TABLE statement
                create_stmt = await self.client.execute_query(f"SHOW CREATE TABLE {table_name}")
                if create_stmt and create_stmt[0][0]:
                    create_sql = create_stmt[0][0]
                    # Check if already has 90 day TTL
                    if "toIntervalDay(90)" in create_sql or "INTERVAL 90 DAY" in create_sql:
                        logger.info(f"{table_name} already has 90-day TTL")
                        continue

                # Update TTL to 90 days
                alter_query = f"ALTER TABLE {table_name} MODIFY TTL {ttl_expression}"
                await self.client.execute_query(alter_query)
                logger.info(f"Updated {table_name} TTL to 90 days")

            except Exception as e:
                logger.error(f"Error updating TTL for {table_name}: {e}")
                raise

        logger.info("Inference tables TTL migration to 90 days completed successfully")

    async def run_migration(self):
        """Run the complete migration process."""
        try:
            await self.initialize()
            await self.create_database()
            await self.create_model_inference_details_table()
            await self.create_model_inference_table()
            await self.create_embedding_inference_table()
            await self.create_audio_inference_table()
            await self.create_image_inference_table()
            await self.create_moderation_inference_table()
            await self.create_gateway_analytics_table()
            await self.create_gateway_blocking_events_table()
            await self.create_cluster_metrics_tables()  # Add cluster metrics tables
            await self.create_hami_gpu_metrics_table()  # Add HAMI GPU time-slicing metrics table
            await self.create_hami_slice_metrics_table()  # Add HAMI slice metrics for per-container GPU tracking
            await self.migrate_hami_gpu_metrics_dcgm_columns()  # Add DCGM columns for hardware metrics
            await self.create_hami_slice_metrics_materialized_view()  # Create MV for vGPU slice data
            await self.create_node_events_table()  # Add NodeEvents table for K8s node events
            await self.migrate_node_metrics_network_columns()  # Add network columns to NodeMetrics (legacy migration)
            await self.setup_cluster_metrics_materialized_views()  # Set up materialized views for cluster metrics
            await self.add_auth_metadata_columns()  # Add auth metadata columns migration
            await self.update_api_key_project_id()  # Update api_key_project_id where null
            await self.add_error_tracking_columns()  # Add error tracking columns for failed inferences
            await self.create_inference_fact_table()  # Create InferenceFact denormalized table
            await (
                self.add_gateway_columns_to_inference_fact()
            )  # Add gateway analytics columns to existing InferenceFact
            await self.add_blocking_columns_to_inference_fact()  # Add blocking event columns to existing InferenceFact
            await self.create_mv_otel_to_inference_fact()  # Create MV to populate InferenceFact from otel_traces
            await (
                self.create_mv_otel_blocking_to_inference_fact()
            )  # Create MV for blocked-only requests to InferenceFact
            await (
                self.make_metrics_dimension_columns_nullable()
            )  # Drop old tables if dimension columns aren't nullable (must be before table creation)
            await self.create_inference_metrics_rollup_tables()  # Create InferenceMetrics rollup tables (5m, 1h, 1d)
            await self.add_blocking_metrics_to_rollup_tables()  # Add blocking metrics columns to rollup tables
            await self.create_inference_metrics_materialized_views()  # Create MVs for cascading rollup
            await self.migrate_inference_tables_ttl_90_days()  # Update TTL to 90 days for inference tables
            await self.verify_tables()
            logger.info("Migration completed successfully!")

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            raise
        finally:
            await self.client.close()


async def main():
    """Run the ClickHouse migration script."""
    parser = argparse.ArgumentParser(description="ClickHouse migration script for bud-serve-metrics")
    parser.add_argument(
        "--include-model-inference",
        action="store_true",
        help="Include ModelInference table creation (optional, for reference)",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify existing tables without creating new ones",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=30,
        help="Maximum number of retries to connect to ClickHouse (default: 30)",
    )
    parser.add_argument(
        "--retry-delay",
        type=int,
        default=2,
        help="Delay in seconds between retries (default: 2)",
    )

    args = parser.parse_args()

    migration = ClickHouseMigration(
        include_model_inference=args.include_model_inference,
        max_retries=args.max_retries,
        retry_delay=args.retry_delay,
    )

    try:
        if args.verify_only:
            await migration.initialize()
            await migration.verify_tables()
            await migration.client.close()
        else:
            await migration.run_migration()

    except Exception as e:
        logger.error(f"Migration error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
