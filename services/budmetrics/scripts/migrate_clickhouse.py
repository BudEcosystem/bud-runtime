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
        # OTel Analytics tables (flat + rollup architecture)
        otel_analytics_tables = [
            "InferenceFact",
            "InferenceMetrics5m",
            "InferenceMetrics1h",
            "InferenceMetrics1d",
            "GeoAnalytics1h",
        ]

        if self.include_model_inference:
            budproxy_tables.append("ModelInference")

        all_tables = budproxy_tables + metrics_tables + otel_analytics_tables

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

    # =============================================================================
    # OTel Analytics Tables (Flat + Rollup Architecture)
    # =============================================================================
    # These tables form the new analytics architecture that processes OTel traces
    # into denormalized flat tables and pre-aggregated rollup tables for
    # sub-100ms query performance at scale.
    # =============================================================================

    def _get_inference_fact_ttl_days(self, default: int = 30) -> int:
        """Get TTL in days for InferenceFact from environment variable."""
        try:
            return int(os.getenv("CLICKHOUSE_TTL_INFERENCE_FACT", default))
        except ValueError:
            logger.warning(f"Invalid CLICKHOUSE_TTL_INFERENCE_FACT value, using default: {default} days")
            return default

    def _get_inference_metrics_5m_ttl_days(self, default: int = 90) -> int:
        """Get TTL in days for InferenceMetrics5m from environment variable."""
        try:
            return int(os.getenv("CLICKHOUSE_TTL_INFERENCE_METRICS_5M", default))
        except ValueError:
            logger.warning(f"Invalid CLICKHOUSE_TTL_INFERENCE_METRICS_5M value, using default: {default} days")
            return default

    def _get_inference_metrics_1h_ttl_days(self, default: int = 365) -> int:
        """Get TTL in days for InferenceMetrics1h from environment variable."""
        try:
            return int(os.getenv("CLICKHOUSE_TTL_INFERENCE_METRICS_1H", default))
        except ValueError:
            logger.warning(f"Invalid CLICKHOUSE_TTL_INFERENCE_METRICS_1H value, using default: {default} days")
            return default

    def _get_inference_metrics_1d_ttl_days(self, default: int = 1095) -> int:
        """Get TTL in days for InferenceMetrics1d (3 years) from environment variable."""
        try:
            return int(os.getenv("CLICKHOUSE_TTL_INFERENCE_METRICS_1D", default))
        except ValueError:
            logger.warning(f"Invalid CLICKHOUSE_TTL_INFERENCE_METRICS_1D value, using default: {default} days")
            return default

    def _get_geo_analytics_ttl_days(self, default: int = 365) -> int:
        """Get TTL in days for GeoAnalytics1h from environment variable."""
        try:
            return int(os.getenv("CLICKHOUSE_TTL_GEO_ANALYTICS", default))
        except ValueError:
            logger.warning(f"Invalid CLICKHOUSE_TTL_GEO_ANALYTICS value, using default: {default} days")
            return default

    async def create_inference_fact_table(self):
        """Create InferenceFact denormalized flat table for analytics.

        This table combines all OTel span data into a single denormalized table,
        eliminating JOINs for analytics queries. It serves as the source of truth
        for detailed inference data and feeds the rollup tables via materialized views.

        Key design decisions:
        - Daily partitioning for efficient TTL and query pruning
        - Order by (project_id, endpoint_id, model_id, timestamp) for common query patterns
        - LowCardinality for categorical strings (model_name, provider, etc.)
        - Compression codecs: Delta+ZSTD for timestamps, Gorilla+ZSTD for metrics
        - Data skipping indexes for fast filtering
        - Projections for common query patterns
        """
        logger.info("Creating InferenceFact table...")

        ttl_days = self._get_inference_fact_ttl_days()
        query = f"""
        CREATE TABLE IF NOT EXISTS InferenceFact
        (
            -- Primary Keys & Identifiers
            id UUID CODEC(ZSTD(1)),
            trace_id String CODEC(ZSTD(1)),
            span_id String CODEC(ZSTD(1)),
            inference_id UUID CODEC(ZSTD(1)),
            episode_id Nullable(UUID) CODEC(ZSTD(1)),

            -- Timestamps (critical for partitioning/ordering)
            timestamp DateTime64(3) CODEC(Delta, ZSTD(1)),
            request_arrival_time Nullable(DateTime64(3)) CODEC(Delta, ZSTD(1)),
            request_forward_time Nullable(DateTime64(3)) CODEC(Delta, ZSTD(1)),
            response_timestamp Nullable(DateTime64(3)) CODEC(Delta, ZSTD(1)),

            -- Project/Endpoint Context (denormalized for fast filtering)
            project_id UUID CODEC(ZSTD(1)),
            endpoint_id UUID CODEC(ZSTD(1)),
            model_id UUID CODEC(ZSTD(1)),
            api_key_id Nullable(UUID) CODEC(ZSTD(1)),
            api_key_project_id Nullable(UUID) CODEC(ZSTD(1)),
            user_id Nullable(String) CODEC(ZSTD(1)),

            -- Model Information (LowCardinality for dictionary encoding)
            model_name LowCardinality(String),
            model_provider LowCardinality(String),
            model_version LowCardinality(Nullable(String)),
            function_name LowCardinality(Nullable(String)),
            variant_name LowCardinality(Nullable(String)),
            endpoint_type LowCardinality(String) DEFAULT 'chat',

            -- Performance Metrics (Delta for time-series integers, ZSTD for compression)
            response_time_ms Nullable(UInt32) CODEC(Delta, ZSTD(1)),
            ttft_ms Nullable(UInt32) CODEC(Delta, ZSTD(1)),
            gateway_processing_ms Nullable(UInt32) CODEC(Delta, ZSTD(1)),
            total_duration_ms Nullable(UInt32) CODEC(Delta, ZSTD(1)),
            processing_time_ms Nullable(UInt32) CODEC(Delta, ZSTD(1)),

            -- Token Usage
            input_tokens Nullable(UInt32) CODEC(Delta, ZSTD(1)),
            output_tokens Nullable(UInt32) CODEC(Delta, ZSTD(1)),
            total_tokens Nullable(UInt32) CODEC(Delta, ZSTD(1)),

            -- Cost
            cost Nullable(Float64) CODEC(Gorilla, ZSTD(1)),

            -- Status & Success
            is_success Bool DEFAULT true,
            status_code Nullable(UInt16) CODEC(ZSTD(1)),
            finish_reason LowCardinality(Nullable(String)),
            cached Bool DEFAULT false,

            -- Error Information
            error_type Nullable(String) CODEC(ZSTD(1)),
            error_code Nullable(String) CODEC(ZSTD(1)),
            error_message Nullable(String) CODEC(ZSTD(3)),

            -- Geographic Data (from gateway_analytics)
            client_ip Nullable(IPv4),
            country_code LowCardinality(Nullable(String)),
            region Nullable(String) CODEC(ZSTD(1)),
            city Nullable(String) CODEC(ZSTD(1)),
            latitude Nullable(Float32),
            longitude Nullable(Float32),
            timezone LowCardinality(Nullable(String)),
            asn Nullable(UInt32),
            isp Nullable(String) CODEC(ZSTD(1)),

            -- Client Metadata
            user_agent Nullable(String) CODEC(ZSTD(3)),
            device_type LowCardinality(Nullable(String)),
            browser_name LowCardinality(Nullable(String)),
            os_name LowCardinality(Nullable(String)),
            is_bot Bool DEFAULT false,

            -- Request Context
            method LowCardinality(String) DEFAULT 'POST',
            path Nullable(String) CODEC(ZSTD(1)),
            body_size Nullable(UInt32),
            response_size Nullable(UInt32),

            -- Blocking Information
            is_blocked Bool DEFAULT false,
            block_reason Nullable(String) CODEC(ZSTD(1)),
            block_rule_id Nullable(String) CODEC(ZSTD(1)),

            -- Routing
            routing_decision LowCardinality(Nullable(String)),

            -- Large Text Fields (stored separately for efficiency)
            system_prompt Nullable(String) CODEC(ZSTD(3)),
            input_messages Nullable(String) CODEC(ZSTD(3)),
            output Nullable(String) CODEC(ZSTD(3)),
            raw_request Nullable(String) CODEC(ZSTD(3)),
            raw_response Nullable(String) CODEC(ZSTD(3)),

            -- Metadata (JSON stored as String)
            tags Nullable(String) CODEC(ZSTD(1)),
            inference_params Nullable(String) CODEC(ZSTD(1)),
            extra_body Nullable(String) CODEC(ZSTD(1)),
            response_analysis Nullable(String) CODEC(ZSTD(1)),
            guardrail_scan_summary Nullable(String) CODEC(ZSTD(1)),

            -- Gateway Request/Response (from ModelInference)
            gateway_request Nullable(String) CODEC(ZSTD(3)),
            gateway_response Nullable(String) CODEC(ZSTD(3)),

            -- Network/Protocol (from GatewayAnalytics)
            proxy_chain Nullable(String) CODEC(ZSTD(1)),
            protocol_version LowCardinality(String) DEFAULT 'HTTP/1.1',

            -- Additional Geo (from GatewayAnalytics)
            country_name Nullable(String) CODEC(ZSTD(1)),

            -- Additional Client Info (from GatewayAnalytics)
            browser_version Nullable(String) CODEC(ZSTD(1)),
            os_version Nullable(String) CODEC(ZSTD(1)),

            -- Request Details (from GatewayAnalytics)
            query_params Nullable(String) CODEC(ZSTD(1)),
            request_headers Nullable(String) CODEC(ZSTD(3)),
            response_headers Nullable(String) CODEC(ZSTD(3)),

            -- Auth (from GatewayAnalytics)
            auth_method LowCardinality(Nullable(String)),

            -- Tool Params (from ChatInference)
            tool_params Nullable(String) CODEC(ZSTD(1))
        )
        ENGINE = MergeTree()
        PARTITION BY toYYYYMMDD(timestamp)
        ORDER BY (project_id, endpoint_id, model_id, timestamp, inference_id)
        TTL toDateTime(timestamp) + INTERVAL {ttl_days} DAY
        SETTINGS index_granularity = 8192, allow_nullable_key = 1
        """

        try:
            await self.client.execute_query(query)
            logger.info("InferenceFact table created successfully")

            # Create data skipping indexes for fast filtering
            indexes = [
                "ALTER TABLE InferenceFact ADD INDEX IF NOT EXISTS idx_model_name (model_name) TYPE set(100) GRANULARITY 4",
                "ALTER TABLE InferenceFact ADD INDEX IF NOT EXISTS idx_model_provider (model_provider) TYPE set(50) GRANULARITY 4",
                "ALTER TABLE InferenceFact ADD INDEX IF NOT EXISTS idx_status_code (status_code) TYPE set(30) GRANULARITY 4",
                "ALTER TABLE InferenceFact ADD INDEX IF NOT EXISTS idx_country_code (country_code) TYPE set(200) GRANULARITY 4",
                "ALTER TABLE InferenceFact ADD INDEX IF NOT EXISTS idx_is_success (is_success) TYPE minmax GRANULARITY 4",
                "ALTER TABLE InferenceFact ADD INDEX IF NOT EXISTS idx_is_blocked (is_blocked) TYPE minmax GRANULARITY 4",
                "ALTER TABLE InferenceFact ADD INDEX IF NOT EXISTS idx_user_id (user_id) TYPE bloom_filter(0.01) GRANULARITY 4",
                "ALTER TABLE InferenceFact ADD INDEX IF NOT EXISTS idx_api_key_project (api_key_project_id) TYPE bloom_filter(0.01) GRANULARITY 4",
                "ALTER TABLE InferenceFact ADD INDEX IF NOT EXISTS idx_inference_id (inference_id) TYPE bloom_filter(0.01) GRANULARITY 4",
                "ALTER TABLE InferenceFact ADD INDEX IF NOT EXISTS idx_trace_id (trace_id) TYPE bloom_filter(0.01) GRANULARITY 4",
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

    async def create_inference_metrics_5m_table(self):
        """Create InferenceMetrics5m rollup table for 5-minute aggregations.

        This table stores pre-aggregated metrics at 5-minute intervals for fast
        /timeseries API queries with 1m-30m intervals. It uses AggregatingMergeTree
        for efficient incremental aggregation.

        Key features:
        - quantilesTDigest for accurate percentile calculations across time buckets
        - uniqState for approximate unique user counts (HyperLogLog)
        - Grouped by project, endpoint, model for common filter patterns
        """
        logger.info("Creating InferenceMetrics5m table...")

        ttl_days = self._get_inference_metrics_5m_ttl_days()
        query = f"""
        CREATE TABLE IF NOT EXISTS InferenceMetrics5m
        (
            -- Time bucket (5-minute intervals)
            ts DateTime CODEC(Delta, ZSTD(1)),

            -- Grouping dimensions
            project_id UUID CODEC(ZSTD(1)),
            endpoint_id UUID CODEC(ZSTD(1)),
            model_id UUID CODEC(ZSTD(1)),
            model_name LowCardinality(String),
            model_provider LowCardinality(String),
            api_key_project_id Nullable(UUID) CODEC(ZSTD(1)),

            -- Count metrics (Delta for sequential integer compression)
            request_count UInt64 CODEC(Delta, ZSTD(1)),
            success_count UInt64 CODEC(Delta, ZSTD(1)),
            error_count UInt64 CODEC(Delta, ZSTD(1)),
            cached_count UInt64 CODEC(Delta, ZSTD(1)),
            blocked_count UInt64 CODEC(Delta, ZSTD(1)),

            -- Token metrics (sum for throughput)
            input_tokens_sum UInt64 CODEC(Delta, ZSTD(1)),
            output_tokens_sum UInt64 CODEC(Delta, ZSTD(1)),

            -- Latency metrics (for percentile approximation)
            response_time_sum UInt64 CODEC(Delta, ZSTD(1)),
            response_time_count UInt64 CODEC(Delta, ZSTD(1)),
            response_time_min Nullable(UInt32) CODEC(Delta, ZSTD(1)),
            response_time_max Nullable(UInt32) CODEC(Delta, ZSTD(1)),
            ttft_sum UInt64 CODEC(Delta, ZSTD(1)),
            ttft_count UInt64 CODEC(Delta, ZSTD(1)),

            -- Queuing time metrics (for weighted average)
            queuing_time_sum UInt64 CODEC(Delta, ZSTD(1)),
            queuing_time_count UInt64 CODEC(Delta, ZSTD(1)),

            -- Percentile sketches (T-Digest for accurate percentiles)
            response_time_quantiles AggregateFunction(quantilesTDigest(0.5, 0.95, 0.99), UInt32),
            ttft_quantiles AggregateFunction(quantilesTDigest(0.5, 0.95, 0.99), UInt32),

            -- Cost (Gorilla is valid for Float64)
            cost_sum Float64 CODEC(Gorilla, ZSTD(1)),

            -- Unique counts (HyperLogLog for cardinality)
            unique_users AggregateFunction(uniq, String)
        )
        ENGINE = AggregatingMergeTree()
        PARTITION BY toYYYYMM(ts)
        ORDER BY (project_id, endpoint_id, model_id, ts)
        TTL ts + INTERVAL {ttl_days} DAY
        SETTINGS index_granularity = 8192
        """

        try:
            await self.client.execute_query(query)
            logger.info("InferenceMetrics5m table created successfully")

            # Create indexes for common query patterns
            indexes = [
                "ALTER TABLE InferenceMetrics5m ADD INDEX IF NOT EXISTS idx_model_name (model_name) TYPE set(100) GRANULARITY 4",
                "ALTER TABLE InferenceMetrics5m ADD INDEX IF NOT EXISTS idx_api_key_project (api_key_project_id) TYPE bloom_filter(0.01) GRANULARITY 4",
            ]

            for index_query in indexes:
                try:
                    await self.client.execute_query(index_query)
                except Exception as e:
                    if "already exists" not in str(e):
                        logger.warning(f"Index creation warning: {e}")

        except Exception as e:
            logger.error(f"Error creating InferenceMetrics5m table: {e}")
            raise

    async def create_inference_metrics_1h_table(self):
        """Create InferenceMetrics1h rollup table for hourly aggregations.

        This table stores pre-aggregated metrics at hourly intervals for
        /timeseries API queries with 1h-1w intervals and /aggregated API.
        It uses AggregatingMergeTree and merges from the 5m rollup table.

        Note: Uses quantilesTDigestMerge for combining T-Digest states from 5m table.
        """
        logger.info("Creating InferenceMetrics1h table...")

        ttl_days = self._get_inference_metrics_1h_ttl_days()
        query = f"""
        CREATE TABLE IF NOT EXISTS InferenceMetrics1h
        (
            -- Time bucket (hourly intervals)
            ts DateTime CODEC(Delta, ZSTD(1)),

            -- Grouping (less granular than 5m - no endpoint_id)
            project_id UUID CODEC(ZSTD(1)),
            model_id UUID CODEC(ZSTD(1)),
            model_name LowCardinality(String),
            model_provider LowCardinality(String),
            api_key_project_id Nullable(UUID) CODEC(ZSTD(1)),

            -- Aggregated counts (Delta for sequential integer compression)
            request_count UInt64 CODEC(Delta, ZSTD(1)),
            success_count UInt64 CODEC(Delta, ZSTD(1)),
            error_count UInt64 CODEC(Delta, ZSTD(1)),
            cached_count UInt64 CODEC(Delta, ZSTD(1)),

            -- Token sums
            input_tokens_sum UInt64 CODEC(Delta, ZSTD(1)),
            output_tokens_sum UInt64 CODEC(Delta, ZSTD(1)),

            -- Latency sum and count for computing true average
            response_time_sum UInt64 CODEC(Delta, ZSTD(1)),
            response_time_count UInt64 CODEC(Delta, ZSTD(1)),

            -- TTFT sum and count for computing true average
            ttft_sum UInt64 CODEC(Delta, ZSTD(1)),
            ttft_count UInt64 CODEC(Delta, ZSTD(1)),

            -- Queuing time metrics (for weighted average)
            queuing_time_sum UInt64 CODEC(Delta, ZSTD(1)),
            queuing_time_count UInt64 CODEC(Delta, ZSTD(1)),

            -- Latency and TTFT quantiles (merged from 5m)
            response_time_quantiles AggregateFunction(quantilesTDigest(0.5, 0.95, 0.99), UInt32),
            ttft_quantiles AggregateFunction(quantilesTDigest(0.5, 0.95, 0.99), UInt32),

            -- Cost (Gorilla is valid for Float64)
            cost_sum Float64 CODEC(Gorilla, ZSTD(1)),

            -- Cardinality
            unique_users AggregateFunction(uniq, String)
        )
        ENGINE = AggregatingMergeTree()
        PARTITION BY toYYYYMM(ts)
        ORDER BY (project_id, model_id, ts)
        TTL ts + INTERVAL {ttl_days} DAY
        SETTINGS index_granularity = 8192
        """

        try:
            await self.client.execute_query(query)
            logger.info("InferenceMetrics1h table created successfully")

            # Create indexes
            indexes = [
                "ALTER TABLE InferenceMetrics1h ADD INDEX IF NOT EXISTS idx_model_name (model_name) TYPE set(100) GRANULARITY 4",
                "ALTER TABLE InferenceMetrics1h ADD INDEX IF NOT EXISTS idx_api_key_project (api_key_project_id) TYPE bloom_filter(0.01) GRANULARITY 4",
            ]

            for index_query in indexes:
                try:
                    await self.client.execute_query(index_query)
                except Exception as e:
                    if "already exists" not in str(e):
                        logger.warning(f"Index creation warning: {e}")

        except Exception as e:
            logger.error(f"Error creating InferenceMetrics1h table: {e}")
            raise

    async def create_inference_metrics_1d_table(self):
        """Create InferenceMetrics1d rollup table for daily aggregations.

        This table stores pre-aggregated metrics at daily intervals for
        long-term trend analysis (up to 3 years). Uses SummingMergeTree
        with explicit column list to ensure only summable columns are summed.

        Note: response_time_sum and response_time_count are stored to allow
        calculating weighted averages at query time. unique_users stores
        the daily finalized count (approximate for multi-day queries).
        """
        logger.info("Creating InferenceMetrics1d table...")

        ttl_days = self._get_inference_metrics_1d_ttl_days()
        query = f"""
        CREATE TABLE IF NOT EXISTS InferenceMetrics1d
        (
            -- Time bucket (daily)
            ts Date CODEC(Delta, ZSTD(1)),

            -- Minimal grouping for long-term storage
            project_id UUID CODEC(ZSTD(1)),
            model_name LowCardinality(String),

            -- Aggregated counts (summable, Delta for integer compression)
            request_count UInt64 CODEC(Delta, ZSTD(1)),
            success_count UInt64 CODEC(Delta, ZSTD(1)),
            error_count UInt64 CODEC(Delta, ZSTD(1)),

            -- Token sums (summable)
            input_tokens_sum UInt64 CODEC(Delta, ZSTD(1)),
            output_tokens_sum UInt64 CODEC(Delta, ZSTD(1)),

            -- Cost (summable, Gorilla valid for Float64)
            cost_sum Float64 CODEC(Gorilla, ZSTD(1)),

            -- Latency metrics (for weighted average calculation at query time)
            response_time_sum UInt64 CODEC(Delta, ZSTD(1)),
            response_time_count UInt64 CODEC(Delta, ZSTD(1)),

            -- TTFT metrics (for weighted average calculation at query time)
            ttft_sum UInt64 CODEC(Delta, ZSTD(1)),
            ttft_count UInt64 CODEC(Delta, ZSTD(1)),

            -- Queuing time metrics (for weighted average calculation at query time)
            queuing_time_sum UInt64 CODEC(Delta, ZSTD(1)),
            queuing_time_count UInt64 CODEC(Delta, ZSTD(1)),

            -- Pre-computed p95 (finalized value from hourly data)
            -- Note: This is an approximation when querying multiple days
            response_time_p95 Float32 CODEC(Gorilla, ZSTD(1)),
            ttft_p95 Float32 CODEC(Gorilla, ZSTD(1)),

            -- Unique users (daily finalized count, approximate for multi-day)
            unique_users UInt64 CODEC(Delta, ZSTD(1))
        )
        ENGINE = SummingMergeTree((
            request_count, success_count, error_count,
            input_tokens_sum, output_tokens_sum, cost_sum,
            response_time_sum, response_time_count,
            ttft_sum, ttft_count,
            queuing_time_sum, queuing_time_count
        ))
        PARTITION BY toYear(ts)
        ORDER BY (project_id, model_name, ts)
        TTL ts + INTERVAL {ttl_days} DAY
        SETTINGS index_granularity = 8192
        """

        try:
            await self.client.execute_query(query)
            logger.info("InferenceMetrics1d table created successfully")

        except Exception as e:
            logger.error(f"Error creating InferenceMetrics1d table: {e}")
            raise

    async def create_geo_analytics_1h_table(self):
        """Create GeoAnalytics1h rollup table for geographic data aggregations.

        This table stores pre-aggregated geographic metrics at hourly intervals
        for the /geography API with fast queries on location-based data.
        """
        logger.info("Creating GeoAnalytics1h table...")

        ttl_days = self._get_geo_analytics_ttl_days()
        query = f"""
        CREATE TABLE IF NOT EXISTS GeoAnalytics1h
        (
            -- Time bucket (hourly)
            ts DateTime CODEC(Delta, ZSTD(1)),

            -- Project context
            project_id UUID CODEC(ZSTD(1)),
            api_key_project_id Nullable(UUID) CODEC(ZSTD(1)),

            -- Geo dimensions
            country_code LowCardinality(String),
            region Nullable(String) CODEC(ZSTD(1)),
            city Nullable(String) CODEC(ZSTD(1)),

            -- Representative coordinates (avg)
            latitude_avg Float32 CODEC(Gorilla, ZSTD(1)),
            longitude_avg Float32 CODEC(Gorilla, ZSTD(1)),

            -- Metrics (Delta for integers, Gorilla for floats)
            request_count UInt64 CODEC(Delta, ZSTD(1)),
            success_count UInt64 CODEC(Delta, ZSTD(1)),
            response_time_sum UInt64 CODEC(Delta, ZSTD(1)),
            response_time_avg Float32 CODEC(Gorilla, ZSTD(1)),

            -- Unique users per location
            unique_users AggregateFunction(uniq, String)
        )
        ENGINE = AggregatingMergeTree()
        PARTITION BY toYYYYMM(ts)
        ORDER BY (project_id, country_code, ts)
        TTL ts + INTERVAL {ttl_days} DAY
        SETTINGS index_granularity = 8192
        """

        try:
            await self.client.execute_query(query)
            logger.info("GeoAnalytics1h table created successfully")

            # Create indexes
            indexes = [
                "ALTER TABLE GeoAnalytics1h ADD INDEX IF NOT EXISTS idx_country_code (country_code) TYPE set(200) GRANULARITY 4",
                "ALTER TABLE GeoAnalytics1h ADD INDEX IF NOT EXISTS idx_api_key_project (api_key_project_id) TYPE bloom_filter(0.01) GRANULARITY 4",
            ]

            for index_query in indexes:
                try:
                    await self.client.execute_query(index_query)
                except Exception as e:
                    if "already exists" not in str(e):
                        logger.warning(f"Index creation warning: {e}")

        except Exception as e:
            logger.error(f"Error creating GeoAnalytics1h table: {e}")
            raise

    # =============================================================================
    # Materialized Views for OTel Analytics Pipeline
    # =============================================================================

    async def create_mv_otel_to_inference_fact(self):
        """Create materialized view to transform otel_traces into InferenceFact.

        This MV extracts span attributes from the OTel traces table and populates
        the denormalized InferenceFact table in real-time as new traces arrive.

        The span attribute naming follows the convention: table_name.column_name
        (e.g., model_inference_details.project_id, gateway_analytics.client_ip)
        """
        logger.info("Creating MV: otel_traces → InferenceFact...")

        # First, drop existing view if it exists (to allow updates)
        try:
            await self.client.execute_query("DROP VIEW IF EXISTS mv_otel_to_inference_fact")
        except Exception as e:
            logger.warning(f"Could not drop existing mv_otel_to_inference_fact: {e}")

        query = """
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_otel_to_inference_fact
        TO InferenceFact
        AS
        SELECT
            -- Generate unique ID
            generateUUIDv4() AS id,
            TraceId AS trace_id,
            SpanId AS span_id,

            -- Inference identifiers
            toUUIDOrNull(nullIf(SpanAttributes['model_inference_details.inference_id'], '')) AS inference_id,
            toUUIDOrNull(nullIf(SpanAttributes['chat_inference.episode_id'], '')) AS episode_id,

            -- Timestamps
            Timestamp AS timestamp,
            parseDateTime64BestEffortOrNull(SpanAttributes['model_inference_details.request_arrival_time']) AS request_arrival_time,
            parseDateTime64BestEffortOrNull(SpanAttributes['model_inference_details.request_forward_time']) AS request_forward_time,
            parseDateTime64BestEffortOrNull(SpanAttributes['gateway_analytics.response_timestamp']) AS response_timestamp,

            -- Project context
            toUUIDOrNull(nullIf(SpanAttributes['model_inference_details.project_id'], '')) AS project_id,
            toUUIDOrNull(nullIf(SpanAttributes['model_inference_details.endpoint_id'], '')) AS endpoint_id,
            toUUIDOrNull(nullIf(SpanAttributes['model_inference_details.model_id'], '')) AS model_id,
            toUUIDOrNull(nullIf(SpanAttributes['model_inference_details.api_key_id'], '')) AS api_key_id,
            toUUIDOrNull(nullIf(SpanAttributes['model_inference_details.api_key_project_id'], '')) AS api_key_project_id,
            nullIf(SpanAttributes['model_inference_details.user_id'], '') AS user_id,

            -- Model info
            SpanAttributes['model_inference.model_name'] AS model_name,
            SpanAttributes['model_inference.model_provider_name'] AS model_provider,
            nullIf(SpanAttributes['gateway_analytics.model_version'], '') AS model_version,
            nullIf(SpanAttributes['chat_inference.function_name'], '') AS function_name,
            nullIf(SpanAttributes['chat_inference.variant_name'], '') AS variant_name,
            if(SpanAttributes['model_inference.endpoint_type'] = '', 'chat', SpanAttributes['model_inference.endpoint_type']) AS endpoint_type,

            -- Performance
            toUInt32OrNull(SpanAttributes['model_inference.response_time_ms']) AS response_time_ms,
            toUInt32OrNull(SpanAttributes['model_inference.ttft_ms']) AS ttft_ms,
            toUInt32OrNull(SpanAttributes['gateway_analytics.gateway_processing_ms']) AS gateway_processing_ms,
            toUInt32OrNull(SpanAttributes['gateway_analytics.total_duration_ms']) AS total_duration_ms,
            toUInt32OrNull(SpanAttributes['chat_inference.processing_time_ms']) AS processing_time_ms,

            -- Tokens
            toUInt32OrNull(SpanAttributes['model_inference.input_tokens']) AS input_tokens,
            toUInt32OrNull(SpanAttributes['model_inference.output_tokens']) AS output_tokens,
            toUInt32OrNull(SpanAttributes['gen_ai.usage.total_tokens']) AS total_tokens,

            -- Cost
            toFloat64OrNull(SpanAttributes['model_inference_details.cost']) AS cost,

            -- Status
            SpanAttributes['model_inference_details.is_success'] = 'true' AS is_success,
            toUInt16OrNull(SpanAttributes['gateway_analytics.status_code']) AS status_code,
            nullIf(SpanAttributes['model_inference.finish_reason'], '') AS finish_reason,
            SpanAttributes['model_inference.cached'] = 'true' AS cached,

            -- Errors
            nullIf(SpanAttributes['model_inference_details.error_type'], '') AS error_type,
            nullIf(SpanAttributes['model_inference_details.error_code'], '') AS error_code,
            nullIf(SpanAttributes['model_inference_details.error_message'], '') AS error_message,

            -- Geographic
            toIPv4OrNull(SpanAttributes['gateway_analytics.client_ip']) AS client_ip,
            nullIf(SpanAttributes['gateway_analytics.country_code'], '') AS country_code,
            nullIf(SpanAttributes['gateway_analytics.region'], '') AS region,
            nullIf(SpanAttributes['gateway_analytics.city'], '') AS city,
            toFloat32OrNull(SpanAttributes['gateway_analytics.latitude']) AS latitude,
            toFloat32OrNull(SpanAttributes['gateway_analytics.longitude']) AS longitude,
            nullIf(SpanAttributes['gateway_analytics.timezone'], '') AS timezone,
            toUInt32OrNull(SpanAttributes['gateway_analytics.asn']) AS asn,
            nullIf(SpanAttributes['gateway_analytics.isp'], '') AS isp,

            -- Client
            nullIf(SpanAttributes['gateway_analytics.user_agent'], '') AS user_agent,
            nullIf(SpanAttributes['gateway_analytics.device_type'], '') AS device_type,
            nullIf(SpanAttributes['gateway_analytics.browser_name'], '') AS browser_name,
            nullIf(SpanAttributes['gateway_analytics.os_name'], '') AS os_name,
            SpanAttributes['gateway_analytics.is_bot'] = 'true' AS is_bot,

            -- Request
            if(SpanAttributes['gateway_analytics.method'] = '', 'POST', SpanAttributes['gateway_analytics.method']) AS method,
            nullIf(SpanAttributes['gateway_analytics.path'], '') AS path,
            toUInt32OrNull(SpanAttributes['gateway_analytics.body_size']) AS body_size,
            toUInt32OrNull(SpanAttributes['gateway_analytics.response_size']) AS response_size,

            -- Blocking
            SpanAttributes['gateway_analytics.is_blocked'] = 'true' AS is_blocked,
            nullIf(SpanAttributes['gateway_analytics.block_reason'], '') AS block_reason,
            nullIf(SpanAttributes['gateway_analytics.block_rule_id'], '') AS block_rule_id,

            -- Routing
            nullIf(SpanAttributes['gateway_analytics.routing_decision'], '') AS routing_decision,

            -- Content
            nullIf(SpanAttributes['model_inference.system'], '') AS system_prompt,
            nullIf(SpanAttributes['model_inference.input_messages'], '') AS input_messages,
            nullIf(SpanAttributes['model_inference.output'], '') AS output,
            nullIf(SpanAttributes['model_inference.raw_request'], '') AS raw_request,
            nullIf(SpanAttributes['model_inference.raw_response'], '') AS raw_response,

            -- Metadata
            nullIf(SpanAttributes['chat_inference.tags'], '') AS tags,
            nullIf(SpanAttributes['chat_inference.inference_params'], '') AS inference_params,
            nullIf(SpanAttributes['chat_inference.extra_body'], '') AS extra_body,
            nullIf(SpanAttributes['model_inference_details.response_analysis'], '') AS response_analysis,
            nullIf(SpanAttributes['model_inference.guardrail_scan_summary'], '') AS guardrail_scan_summary,

            -- Gateway Request/Response (from ModelInference)
            nullIf(SpanAttributes['model_inference.gateway_request'], '') AS gateway_request,
            nullIf(SpanAttributes['model_inference.gateway_response'], '') AS gateway_response,

            -- Network/Protocol (from GatewayAnalytics)
            nullIf(SpanAttributes['gateway_analytics.proxy_chain'], '') AS proxy_chain,
            if(SpanAttributes['gateway_analytics.protocol_version'] = '', 'HTTP/1.1', SpanAttributes['gateway_analytics.protocol_version']) AS protocol_version,

            -- Additional Geo (from GatewayAnalytics)
            nullIf(SpanAttributes['gateway_analytics.country_name'], '') AS country_name,

            -- Additional Client Info (from GatewayAnalytics)
            nullIf(SpanAttributes['gateway_analytics.browser_version'], '') AS browser_version,
            nullIf(SpanAttributes['gateway_analytics.os_version'], '') AS os_version,

            -- Request Details (from GatewayAnalytics)
            nullIf(SpanAttributes['gateway_analytics.query_params'], '') AS query_params,
            nullIf(SpanAttributes['gateway_analytics.request_headers'], '') AS request_headers,
            nullIf(SpanAttributes['gateway_analytics.response_headers'], '') AS response_headers,

            -- Auth (from GatewayAnalytics)
            nullIf(SpanAttributes['gateway_analytics.auth_method'], '') AS auth_method,

            -- Tool Params (from ChatInference)
            nullIf(SpanAttributes['chat_inference.tool_params'], '') AS tool_params

        FROM otel_traces
        WHERE SpanName = 'inference_handler_observability'
          AND SpanAttributes['model_inference_details.inference_id'] != ''
          AND SpanAttributes['model_inference_details.project_id'] != ''
        """

        try:
            await self.client.execute_query(query)
            logger.info("✓ Created mv_otel_to_inference_fact materialized view")
        except Exception as e:
            logger.error(f"Error creating mv_otel_to_inference_fact: {e}")
            raise

    async def create_mv_inference_5m_rollup(self):
        """Create materialized view to aggregate InferenceFact into 5-minute rollups.

        This MV aggregates the flat InferenceFact table into InferenceMetrics5m
        with 5-minute time buckets for efficient time-series queries.
        """
        logger.info("Creating MV: InferenceFact → InferenceMetrics5m...")

        # First, drop existing view if it exists
        try:
            await self.client.execute_query("DROP VIEW IF EXISTS mv_inference_5m_rollup")
        except Exception as e:
            logger.warning(f"Could not drop existing mv_inference_5m_rollup: {e}")

        query = """
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_inference_5m_rollup
        TO InferenceMetrics5m
        AS
        SELECT
            toStartOfFiveMinutes(timestamp) AS ts,
            project_id,
            endpoint_id,
            model_id,
            model_name,
            model_provider,
            api_key_project_id,

            count() AS request_count,
            countIf(is_success = true) AS success_count,
            countIf(is_success = false) AS error_count,
            countIf(cached = true) AS cached_count,
            countIf(is_blocked = true) AS blocked_count,

            sum(ifNull(input_tokens, 0)) AS input_tokens_sum,
            sum(ifNull(output_tokens, 0)) AS output_tokens_sum,

            sum(ifNull(response_time_ms, 0)) AS response_time_sum,
            countIf(response_time_ms IS NOT NULL) AS response_time_count,
            min(response_time_ms) AS response_time_min,
            max(response_time_ms) AS response_time_max,
            sum(ifNull(ttft_ms, 0)) AS ttft_sum,
            countIf(ttft_ms IS NOT NULL AND ttft_ms > 0) AS ttft_count,

            sumIf(toUnixTimestamp64Milli(request_forward_time) - toUnixTimestamp64Milli(request_arrival_time), request_forward_time IS NOT NULL AND request_arrival_time IS NOT NULL) AS queuing_time_sum,
            countIf(request_forward_time IS NOT NULL AND request_arrival_time IS NOT NULL) AS queuing_time_count,

            quantilesTDigestState(0.5, 0.95, 0.99)(ifNull(response_time_ms, 0)) AS response_time_quantiles,
            quantilesTDigestState(0.5, 0.95, 0.99)(ifNull(ttft_ms, 0)) AS ttft_quantiles,

            sum(ifNull(cost, 0)) AS cost_sum,

            uniqState(ifNull(user_id, '')) AS unique_users

        FROM InferenceFact
        WHERE project_id IS NOT NULL
        GROUP BY ts, project_id, endpoint_id, model_id, model_name, model_provider, api_key_project_id
        """

        try:
            await self.client.execute_query(query)
            logger.info("✓ Created mv_inference_5m_rollup materialized view")
        except Exception as e:
            logger.error(f"Error creating mv_inference_5m_rollup: {e}")
            raise

    async def create_mv_inference_1h_rollup(self):
        """Create materialized view to aggregate 5m rollups into hourly rollups.

        This MV merges the 5-minute aggregations into InferenceMetrics1h
        with hourly time buckets. Uses quantilesTDigestMergeState to combine
        T-Digest states from the 5m table.
        """
        logger.info("Creating MV: InferenceMetrics5m → InferenceMetrics1h...")

        # First, drop existing view if it exists
        try:
            await self.client.execute_query("DROP VIEW IF EXISTS mv_inference_1h_rollup")
        except Exception as e:
            logger.warning(f"Could not drop existing mv_inference_1h_rollup: {e}")

        query = """
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_inference_1h_rollup
        TO InferenceMetrics1h
        AS
        SELECT
            toStartOfHour(ts) AS ts,
            project_id,
            model_id,
            model_name,
            model_provider,
            api_key_project_id,

            sum(request_count) AS request_count,
            sum(success_count) AS success_count,
            sum(error_count) AS error_count,
            sum(cached_count) AS cached_count,

            sum(input_tokens_sum) AS input_tokens_sum,
            sum(output_tokens_sum) AS output_tokens_sum,

            sum(response_time_sum) AS response_time_sum,
            sum(response_time_count) AS response_time_count,

            sum(ttft_sum) AS ttft_sum,
            sum(ttft_count) AS ttft_count,

            sum(queuing_time_sum) AS queuing_time_sum,
            sum(queuing_time_count) AS queuing_time_count,

            quantilesTDigestMergeState(0.5, 0.95, 0.99)(response_time_quantiles) AS response_time_quantiles,
            quantilesTDigestMergeState(0.5, 0.95, 0.99)(ttft_quantiles) AS ttft_quantiles,

            sum(cost_sum) AS cost_sum,

            uniqMergeState(unique_users) AS unique_users

        FROM InferenceMetrics5m
        GROUP BY ts, project_id, model_id, model_name, model_provider, api_key_project_id
        """

        try:
            await self.client.execute_query(query)
            logger.info("✓ Created mv_inference_1h_rollup materialized view")
        except Exception as e:
            logger.error(f"Error creating mv_inference_1h_rollup: {e}")
            raise

    async def create_mv_inference_1d_rollup(self):
        """Create materialized view to aggregate 1h rollups into daily rollups.

        This MV aggregates the hourly data into InferenceMetrics1d with daily
        time buckets for long-term trend analysis.

        Note: Uses quantilesTDigestMerge to finalize p95 values from hourly states.
        unique_users is finalized per day (approximate for multi-day queries).
        """
        logger.info("Creating MV: InferenceMetrics1h → InferenceMetrics1d...")

        # First, drop existing view if it exists
        try:
            await self.client.execute_query("DROP VIEW IF EXISTS mv_inference_1d_rollup")
        except Exception as e:
            logger.warning(f"Could not drop existing mv_inference_1d_rollup: {e}")

        query = """
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_inference_1d_rollup
        TO InferenceMetrics1d
        AS
        SELECT
            toDate(ts) AS ts,
            project_id,
            model_name,

            sum(InferenceMetrics1h.request_count) AS request_count,
            sum(InferenceMetrics1h.success_count) AS success_count,
            sum(InferenceMetrics1h.error_count) AS error_count,

            sum(InferenceMetrics1h.input_tokens_sum) AS input_tokens_sum,
            sum(InferenceMetrics1h.output_tokens_sum) AS output_tokens_sum,

            sum(InferenceMetrics1h.cost_sum) AS cost_sum,

            -- Latency metrics (aggregated from 1h table)
            sum(InferenceMetrics1h.response_time_sum) AS response_time_sum,
            sum(InferenceMetrics1h.response_time_count) AS response_time_count,

            -- TTFT metrics (aggregated from 1h table)
            sum(InferenceMetrics1h.ttft_sum) AS ttft_sum,
            sum(InferenceMetrics1h.ttft_count) AS ttft_count,

            -- Queuing time metrics (aggregated from 1h table)
            sum(InferenceMetrics1h.queuing_time_sum) AS queuing_time_sum,
            sum(InferenceMetrics1h.queuing_time_count) AS queuing_time_count,

            -- p95 values (merged from 1h quantiles)
            quantilesTDigestMerge(0.95)(response_time_quantiles)[1] AS response_time_p95,
            quantilesTDigestMerge(0.95)(ttft_quantiles)[1] AS ttft_p95,

            -- Finalize unique users count per day (approximate for multi-day)
            uniqMerge(unique_users) AS unique_users

        FROM InferenceMetrics1h
        GROUP BY ts, project_id, model_name
        """

        try:
            await self.client.execute_query(query)
            logger.info("✓ Created mv_inference_1d_rollup materialized view")
        except Exception as e:
            logger.error(f"Error creating mv_inference_1d_rollup: {e}")
            raise

    async def create_mv_geo_analytics_1h(self):
        """Create materialized view for geographic analytics rollup.

        This MV aggregates InferenceFact into GeoAnalytics1h with hourly
        geographic data for the /geography API.
        """
        logger.info("Creating MV: InferenceFact → GeoAnalytics1h...")

        # First, drop existing view if it exists
        try:
            await self.client.execute_query("DROP VIEW IF EXISTS mv_geo_analytics_1h")
        except Exception as e:
            logger.warning(f"Could not drop existing mv_geo_analytics_1h: {e}")

        query = """
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_geo_analytics_1h
        TO GeoAnalytics1h
        AS
        SELECT
            toStartOfHour(timestamp) AS ts,
            project_id,
            api_key_project_id,
            country_code,
            region,
            city,
            avg(latitude) AS latitude_avg,
            avg(longitude) AS longitude_avg,
            count() AS request_count,
            countIf(is_success = true) AS success_count,
            sum(ifNull(response_time_ms, 0)) AS response_time_sum,
            avg(ifNull(response_time_ms, 0)) AS response_time_avg,
            uniqState(ifNull(user_id, '')) AS unique_users

        FROM InferenceFact
        WHERE country_code IS NOT NULL AND country_code != ''
          AND project_id IS NOT NULL
        GROUP BY ts, project_id, api_key_project_id, country_code, region, city
        """

        try:
            await self.client.execute_query(query)
            logger.info("✓ Created mv_geo_analytics_1h materialized view")
        except Exception as e:
            logger.error(f"Error creating mv_geo_analytics_1h: {e}")
            raise

    async def setup_otel_analytics_pipeline(self):
        """Set up the complete OTel analytics pipeline.

        Creates all flat tables, rollup tables, and materialized views
        for the new analytics architecture.
        """
        logger.info("Setting up OTel Analytics Pipeline...")

        # Create flat table
        await self.create_inference_fact_table()

        # Create rollup tables
        await self.create_inference_metrics_5m_table()
        await self.create_inference_metrics_1h_table()
        await self.create_inference_metrics_1d_table()
        await self.create_geo_analytics_1h_table()

        # Create materialized views (order matters - base tables must exist first)
        await self.create_mv_otel_to_inference_fact()
        await self.create_mv_inference_5m_rollup()
        await self.create_mv_inference_1h_rollup()
        await self.create_mv_inference_1d_rollup()  # New: 1h → 1d rollup
        await self.create_mv_geo_analytics_1h()

        logger.info("✓ OTel Analytics Pipeline setup completed successfully")

    # =============================================================================
    # End of OTel Analytics Tables
    # =============================================================================

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

    async def migrate_inference_metrics_1h_response_time_sum(self):
        """Add response_time_sum column to InferenceMetrics1h for true average latency calculation.

        This migration adds the response_time_sum column which enables computing true
        average latency (sum/count) instead of using p50 as an approximation.

        Also recreates the MV to include the new column from InferenceMetrics5m.
        """
        logger.info("Adding response_time_sum column to InferenceMetrics1h...")

        try:
            # Check if table exists
            table_exists = await self.client.execute_query("EXISTS TABLE InferenceMetrics1h")
            if not table_exists or not table_exists[0][0]:
                logger.info("InferenceMetrics1h table does not exist yet. Skipping column migration.")
                return

            # Check if column already exists
            columns_result = await self.client.execute_query("DESCRIBE TABLE InferenceMetrics1h")
            existing_columns = {row[0] for row in columns_result}

            if "response_time_sum" in existing_columns:
                logger.info("✓ response_time_sum column already exists in InferenceMetrics1h")
                return

            # Add the column
            alter_query = """
            ALTER TABLE InferenceMetrics1h
            ADD COLUMN IF NOT EXISTS response_time_sum UInt64 DEFAULT 0
            """
            await self.client.execute_query(alter_query)
            logger.info("✓ Added response_time_sum column to InferenceMetrics1h")

            # Recreate the MV to include the new column
            logger.info("Recreating mv_inference_1h_rollup to include response_time_sum...")

            # Drop and recreate the MV
            try:
                await self.client.execute_query("DROP VIEW IF EXISTS mv_inference_1h_rollup")
            except Exception as e:
                logger.warning(f"Could not drop existing mv_inference_1h_rollup: {e}")

            # Create MV with response_time_sum
            mv_query = """
            CREATE MATERIALIZED VIEW IF NOT EXISTS mv_inference_1h_rollup
            TO InferenceMetrics1h
            AS
            SELECT
                toStartOfHour(ts) AS ts,
                project_id,
                model_id,
                model_name,
                model_provider,
                api_key_project_id,

                sum(request_count) AS request_count,
                sum(success_count) AS success_count,
                sum(error_count) AS error_count,
                sum(cached_count) AS cached_count,

                sum(input_tokens_sum) AS input_tokens_sum,
                sum(output_tokens_sum) AS output_tokens_sum,

                sum(response_time_sum) AS response_time_sum,

                quantilesTDigestMergeState(0.5, 0.95, 0.99)(response_time_quantiles) AS response_time_quantiles,
                quantilesTDigestMergeState(0.5, 0.95, 0.99)(ttft_quantiles) AS ttft_quantiles,

                sum(cost_sum) AS cost_sum,

                uniqMergeState(unique_users) AS unique_users

            FROM InferenceMetrics5m
            GROUP BY ts, project_id, model_id, model_name, model_provider, api_key_project_id
            """
            await self.client.execute_query(mv_query)
            logger.info("✓ Recreated mv_inference_1h_rollup with response_time_sum")

        except Exception as e:
            logger.error(f"Error adding response_time_sum to InferenceMetrics1h: {e}")
            raise

    async def migrate_response_time_count(self):
        """Add response_time_count column to 5m and 1h tables for accurate average latency.

        This migration adds the response_time_count column which tracks the count of
        non-NULL latency values, enabling proper average calculation that matches
        SQL avg() behavior (ignoring NULLs).

        Without this, dividing response_time_sum by request_count gives wrong results
        when some requests have NULL latency values.
        """
        logger.info("Adding response_time_count column to InferenceMetrics5m and InferenceMetrics1h...")

        try:
            # Check if InferenceMetrics5m table exists
            table_5m_exists = await self.client.execute_query("EXISTS TABLE InferenceMetrics5m")
            if not table_5m_exists or not table_5m_exists[0][0]:
                logger.info("InferenceMetrics5m table does not exist yet. Skipping column migration.")
                return

            # Check if column already exists in 5m table
            columns_5m = await self.client.execute_query("DESCRIBE TABLE InferenceMetrics5m")
            existing_5m_columns = {row[0] for row in columns_5m}

            if "response_time_count" not in existing_5m_columns:
                # Add column to InferenceMetrics5m
                await self.client.execute_query("""
                    ALTER TABLE InferenceMetrics5m
                    ADD COLUMN IF NOT EXISTS response_time_count UInt64 DEFAULT 0
                """)
                logger.info("✓ Added response_time_count column to InferenceMetrics5m")

                # Recreate mv_inference_5m_rollup with countIf()
                logger.info("Recreating mv_inference_5m_rollup to include response_time_count...")
                try:
                    await self.client.execute_query("DROP VIEW IF EXISTS mv_inference_5m_rollup")
                except Exception as e:
                    logger.warning(f"Could not drop existing mv_inference_5m_rollup: {e}")

                mv_5m_query = """
                CREATE MATERIALIZED VIEW IF NOT EXISTS mv_inference_5m_rollup
                TO InferenceMetrics5m
                AS
                SELECT
                    toStartOfFiveMinutes(timestamp) AS ts,
                    project_id,
                    endpoint_id,
                    model_id,
                    model_name,
                    model_provider,
                    api_key_project_id,

                    count() AS request_count,
                    countIf(is_success = true) AS success_count,
                    countIf(is_success = false) AS error_count,
                    countIf(cached = true) AS cached_count,
                    countIf(is_blocked = true) AS blocked_count,

                    sum(ifNull(input_tokens, 0)) AS input_tokens_sum,
                    sum(ifNull(output_tokens, 0)) AS output_tokens_sum,

                    sum(ifNull(response_time_ms, 0)) AS response_time_sum,
                    countIf(response_time_ms IS NOT NULL) AS response_time_count,
                    min(response_time_ms) AS response_time_min,
                    max(response_time_ms) AS response_time_max,
                    sum(ifNull(ttft_ms, 0)) AS ttft_sum,

                    quantilesTDigestState(0.5, 0.95, 0.99)(ifNull(response_time_ms, 0)) AS response_time_quantiles,
                    quantilesTDigestState(0.5, 0.95, 0.99)(ifNull(ttft_ms, 0)) AS ttft_quantiles,

                    sum(ifNull(cost, 0)) AS cost_sum,

                    uniqState(ifNull(user_id, '')) AS unique_users

                FROM InferenceFact
                WHERE project_id IS NOT NULL
                GROUP BY ts, project_id, endpoint_id, model_id, model_name, model_provider, api_key_project_id
                """
                await self.client.execute_query(mv_5m_query)
                logger.info("✓ Recreated mv_inference_5m_rollup with response_time_count")
            else:
                logger.info("✓ response_time_count column already exists in InferenceMetrics5m")

            # Check if InferenceMetrics1h table exists
            table_1h_exists = await self.client.execute_query("EXISTS TABLE InferenceMetrics1h")
            if not table_1h_exists or not table_1h_exists[0][0]:
                logger.info("InferenceMetrics1h table does not exist yet. Skipping column migration.")
                return

            # Check if column already exists in 1h table
            columns_1h = await self.client.execute_query("DESCRIBE TABLE InferenceMetrics1h")
            existing_1h_columns = {row[0] for row in columns_1h}

            if "response_time_count" not in existing_1h_columns:
                # Add column to InferenceMetrics1h
                await self.client.execute_query("""
                    ALTER TABLE InferenceMetrics1h
                    ADD COLUMN IF NOT EXISTS response_time_count UInt64 DEFAULT 0
                """)
                logger.info("✓ Added response_time_count column to InferenceMetrics1h")

                # Recreate mv_inference_1h_rollup with sum(response_time_count)
                logger.info("Recreating mv_inference_1h_rollup to include response_time_count...")
                try:
                    await self.client.execute_query("DROP VIEW IF EXISTS mv_inference_1h_rollup")
                except Exception as e:
                    logger.warning(f"Could not drop existing mv_inference_1h_rollup: {e}")

                mv_1h_query = """
                CREATE MATERIALIZED VIEW IF NOT EXISTS mv_inference_1h_rollup
                TO InferenceMetrics1h
                AS
                SELECT
                    toStartOfHour(ts) AS ts,
                    project_id,
                    model_id,
                    model_name,
                    model_provider,
                    api_key_project_id,

                    sum(request_count) AS request_count,
                    sum(success_count) AS success_count,
                    sum(error_count) AS error_count,
                    sum(cached_count) AS cached_count,

                    sum(input_tokens_sum) AS input_tokens_sum,
                    sum(output_tokens_sum) AS output_tokens_sum,

                    sum(response_time_sum) AS response_time_sum,
                    sum(response_time_count) AS response_time_count,

                    quantilesTDigestMergeState(0.5, 0.95, 0.99)(response_time_quantiles) AS response_time_quantiles,
                    quantilesTDigestMergeState(0.5, 0.95, 0.99)(ttft_quantiles) AS ttft_quantiles,

                    sum(cost_sum) AS cost_sum,

                    uniqMergeState(unique_users) AS unique_users

                FROM InferenceMetrics5m
                GROUP BY ts, project_id, model_id, model_name, model_provider, api_key_project_id
                """
                await self.client.execute_query(mv_1h_query)
                logger.info("✓ Recreated mv_inference_1h_rollup with response_time_count")
            else:
                logger.info("✓ response_time_count column already exists in InferenceMetrics1h")

        except Exception as e:
            logger.error(f"Error adding response_time_count columns: {e}")
            raise

    async def migrate_ttft_columns(self):
        """Add ttft_sum and ttft_count columns to rollup tables for accurate TTFT metrics.

        This migration adds:
        - ttft_count to InferenceMetrics5m (count of non-NULL TTFT values)
        - ttft_sum, ttft_count to InferenceMetrics1h
        - ttft_sum, ttft_count, ttft_p95, response_time_p95, unique_users to InferenceMetrics1d

        This enables proper average TTFT calculation that matches SQL avg() behavior
        (ignoring NULLs in the denominator).
        """
        logger.info("Adding TTFT columns to rollup tables...")

        try:
            # Step 1: Add ttft_count to InferenceMetrics5m
            table_5m_exists = await self.client.execute_query("EXISTS TABLE InferenceMetrics5m")
            if table_5m_exists and table_5m_exists[0][0]:
                columns_5m = await self.client.execute_query("DESCRIBE TABLE InferenceMetrics5m")
                existing_5m_columns = {row[0] for row in columns_5m}

                if "ttft_count" not in existing_5m_columns:
                    await self.client.execute_query("""
                        ALTER TABLE InferenceMetrics5m
                        ADD COLUMN IF NOT EXISTS ttft_count UInt64 DEFAULT 0
                    """)
                    logger.info("✓ Added ttft_count column to InferenceMetrics5m")

                    # Recreate mv_inference_5m_rollup with ttft_count
                    logger.info("Recreating mv_inference_5m_rollup to include ttft_count...")
                    try:
                        await self.client.execute_query("DROP VIEW IF EXISTS mv_inference_5m_rollup")
                    except Exception as e:
                        logger.warning(f"Could not drop existing mv_inference_5m_rollup: {e}")

                    mv_5m_query = """
                    CREATE MATERIALIZED VIEW IF NOT EXISTS mv_inference_5m_rollup
                    TO InferenceMetrics5m
                    AS
                    SELECT
                        toStartOfFiveMinutes(timestamp) AS ts,
                        project_id,
                        endpoint_id,
                        model_id,
                        model_name,
                        model_provider,
                        api_key_project_id,

                        count() AS request_count,
                        countIf(is_success = true) AS success_count,
                        countIf(is_success = false) AS error_count,
                        countIf(cached = true) AS cached_count,
                        countIf(is_blocked = true) AS blocked_count,

                        sum(ifNull(input_tokens, 0)) AS input_tokens_sum,
                        sum(ifNull(output_tokens, 0)) AS output_tokens_sum,

                        sum(ifNull(response_time_ms, 0)) AS response_time_sum,
                        countIf(response_time_ms IS NOT NULL) AS response_time_count,
                        min(response_time_ms) AS response_time_min,
                        max(response_time_ms) AS response_time_max,
                        sum(ifNull(ttft_ms, 0)) AS ttft_sum,
                        countIf(ttft_ms IS NOT NULL AND ttft_ms > 0) AS ttft_count,

                        quantilesTDigestState(0.5, 0.95, 0.99)(ifNull(response_time_ms, 0)) AS response_time_quantiles,
                        quantilesTDigestState(0.5, 0.95, 0.99)(ifNull(ttft_ms, 0)) AS ttft_quantiles,

                        sum(ifNull(cost, 0)) AS cost_sum,

                        uniqState(ifNull(user_id, '')) AS unique_users

                    FROM InferenceFact
                    WHERE project_id IS NOT NULL
                    GROUP BY ts, project_id, endpoint_id, model_id, model_name, model_provider, api_key_project_id
                    """
                    await self.client.execute_query(mv_5m_query)
                    logger.info("✓ Recreated mv_inference_5m_rollup with ttft_count")
                else:
                    logger.info("✓ ttft_count column already exists in InferenceMetrics5m")

            # Step 2: Add ttft_sum and ttft_count to InferenceMetrics1h
            table_1h_exists = await self.client.execute_query("EXISTS TABLE InferenceMetrics1h")
            if table_1h_exists and table_1h_exists[0][0]:
                columns_1h = await self.client.execute_query("DESCRIBE TABLE InferenceMetrics1h")
                existing_1h_columns = {row[0] for row in columns_1h}

                columns_to_add_1h = []
                if "ttft_sum" not in existing_1h_columns:
                    columns_to_add_1h.append("ttft_sum UInt64 DEFAULT 0")
                if "ttft_count" not in existing_1h_columns:
                    columns_to_add_1h.append("ttft_count UInt64 DEFAULT 0")

                if columns_to_add_1h:
                    for col in columns_to_add_1h:
                        await self.client.execute_query(f"ALTER TABLE InferenceMetrics1h ADD COLUMN IF NOT EXISTS {col}")
                    logger.info(f"✓ Added columns to InferenceMetrics1h: {columns_to_add_1h}")

                    # Recreate mv_inference_1h_rollup with ttft columns
                    logger.info("Recreating mv_inference_1h_rollup to include ttft_sum and ttft_count...")
                    try:
                        await self.client.execute_query("DROP VIEW IF EXISTS mv_inference_1h_rollup")
                    except Exception as e:
                        logger.warning(f"Could not drop existing mv_inference_1h_rollup: {e}")

                    mv_1h_query = """
                    CREATE MATERIALIZED VIEW IF NOT EXISTS mv_inference_1h_rollup
                    TO InferenceMetrics1h
                    AS
                    SELECT
                        toStartOfHour(ts) AS ts,
                        project_id,
                        model_id,
                        model_name,
                        model_provider,
                        api_key_project_id,

                        sum(request_count) AS request_count,
                        sum(success_count) AS success_count,
                        sum(error_count) AS error_count,
                        sum(cached_count) AS cached_count,

                        sum(input_tokens_sum) AS input_tokens_sum,
                        sum(output_tokens_sum) AS output_tokens_sum,

                        sum(response_time_sum) AS response_time_sum,
                        sum(response_time_count) AS response_time_count,

                        sum(ttft_sum) AS ttft_sum,
                        sum(ttft_count) AS ttft_count,

                        quantilesTDigestMergeState(0.5, 0.95, 0.99)(response_time_quantiles) AS response_time_quantiles,
                        quantilesTDigestMergeState(0.5, 0.95, 0.99)(ttft_quantiles) AS ttft_quantiles,

                        sum(cost_sum) AS cost_sum,

                        uniqMergeState(unique_users) AS unique_users

                    FROM InferenceMetrics5m
                    GROUP BY ts, project_id, model_id, model_name, model_provider, api_key_project_id
                    """
                    await self.client.execute_query(mv_1h_query)
                    logger.info("✓ Recreated mv_inference_1h_rollup with ttft columns")
                else:
                    logger.info("✓ ttft_sum and ttft_count columns already exist in InferenceMetrics1h")

            # Step 3: Add ttft_sum, ttft_count, ttft_p95, response_time_p95, unique_users to InferenceMetrics1d
            table_1d_exists = await self.client.execute_query("EXISTS TABLE InferenceMetrics1d")
            if table_1d_exists and table_1d_exists[0][0]:
                columns_1d = await self.client.execute_query("DESCRIBE TABLE InferenceMetrics1d")
                existing_1d_columns = {row[0] for row in columns_1d}

                columns_to_add_1d = []
                if "ttft_sum" not in existing_1d_columns:
                    columns_to_add_1d.append("ttft_sum UInt64 DEFAULT 0")
                if "ttft_count" not in existing_1d_columns:
                    columns_to_add_1d.append("ttft_count UInt64 DEFAULT 0")
                if "ttft_p95" not in existing_1d_columns:
                    columns_to_add_1d.append("ttft_p95 Float32 DEFAULT 0")
                if "response_time_p95" not in existing_1d_columns:
                    columns_to_add_1d.append("response_time_p95 Float32 DEFAULT 0")
                if "unique_users" not in existing_1d_columns:
                    columns_to_add_1d.append("unique_users UInt64 DEFAULT 0")

                if columns_to_add_1d:
                    for col in columns_to_add_1d:
                        await self.client.execute_query(f"ALTER TABLE InferenceMetrics1d ADD COLUMN IF NOT EXISTS {col}")
                    logger.info(f"✓ Added columns to InferenceMetrics1d: {columns_to_add_1d}")

                    # Recreate mv_inference_1d_rollup with ttft columns
                    logger.info("Recreating mv_inference_1d_rollup to include ttft columns...")
                    try:
                        await self.client.execute_query("DROP VIEW IF EXISTS mv_inference_1d_rollup")
                    except Exception as e:
                        logger.warning(f"Could not drop existing mv_inference_1d_rollup: {e}")

                    mv_1d_query = """
                    CREATE MATERIALIZED VIEW IF NOT EXISTS mv_inference_1d_rollup
                    TO InferenceMetrics1d
                    AS
                    SELECT
                        toDate(ts) AS ts,
                        project_id,
                        model_name,

                        sum(InferenceMetrics1h.request_count) AS request_count,
                        sum(InferenceMetrics1h.success_count) AS success_count,
                        sum(InferenceMetrics1h.error_count) AS error_count,

                        sum(InferenceMetrics1h.input_tokens_sum) AS input_tokens_sum,
                        sum(InferenceMetrics1h.output_tokens_sum) AS output_tokens_sum,

                        sum(InferenceMetrics1h.cost_sum) AS cost_sum,

                        sum(InferenceMetrics1h.response_time_sum) AS response_time_sum,
                        sum(InferenceMetrics1h.response_time_count) AS response_time_count,

                        sum(InferenceMetrics1h.ttft_sum) AS ttft_sum,
                        sum(InferenceMetrics1h.ttft_count) AS ttft_count,

                        sum(InferenceMetrics1h.queuing_time_sum) AS queuing_time_sum,
                        sum(InferenceMetrics1h.queuing_time_count) AS queuing_time_count,

                        quantilesTDigestMerge(0.95)(response_time_quantiles)[1] AS response_time_p95,
                        quantilesTDigestMerge(0.95)(ttft_quantiles)[1] AS ttft_p95,

                        uniqMerge(unique_users) AS unique_users

                    FROM InferenceMetrics1h
                    GROUP BY ts, project_id, model_name
                    """
                    await self.client.execute_query(mv_1d_query)
                    logger.info("✓ Recreated mv_inference_1d_rollup with ttft columns")
                else:
                    logger.info("✓ ttft columns already exist in InferenceMetrics1d")

        except Exception as e:
            logger.error(f"Error adding TTFT columns: {e}")
            raise

    async def add_missing_columns_to_inference_fact(self):
        """Add missing columns to InferenceFact table for complete OTel data coverage.

        These 12 columns were missing from the original InferenceFact schema:
        - gateway_request, gateway_response (from ModelInference)
        - proxy_chain, protocol_version, country_name, browser_version, os_version,
          query_params, request_headers, response_headers, auth_method (from GatewayAnalytics)
        - tool_params (from ChatInference)
        """
        logger.info("Adding missing columns to InferenceFact...")

        # Check if table exists
        try:
            result = await self.client.execute_query(
                "SELECT count() FROM system.tables WHERE database = currentDatabase() AND name = 'InferenceFact'"
            )
            if not result or result[0][0] == 0:
                logger.info("InferenceFact table does not exist, skipping column addition")
                return
        except Exception as e:
            logger.warning(f"Could not check InferenceFact existence: {e}")
            return

        # Get current columns
        try:
            columns_result = await self.client.execute_query("DESCRIBE TABLE InferenceFact")
            current_columns = {row[0] for row in columns_result}
        except Exception as e:
            logger.warning(f"Could not describe InferenceFact: {e}")
            return

        # Columns to add (only if they don't exist)
        columns_to_add = [
            ("gateway_request", "Nullable(String) CODEC(ZSTD(3))"),
            ("gateway_response", "Nullable(String) CODEC(ZSTD(3))"),
            ("proxy_chain", "Nullable(String) CODEC(ZSTD(1))"),
            ("protocol_version", "LowCardinality(String) DEFAULT 'HTTP/1.1'"),
            ("country_name", "Nullable(String) CODEC(ZSTD(1))"),
            ("browser_version", "Nullable(String) CODEC(ZSTD(1))"),
            ("os_version", "Nullable(String) CODEC(ZSTD(1))"),
            ("query_params", "Nullable(String) CODEC(ZSTD(1))"),
            ("request_headers", "Nullable(String) CODEC(ZSTD(3))"),
            ("response_headers", "Nullable(String) CODEC(ZSTD(3))"),
            ("auth_method", "LowCardinality(Nullable(String))"),
            ("tool_params", "Nullable(String) CODEC(ZSTD(1))"),
        ]

        added_count = 0
        for col_name, col_type in columns_to_add:
            if col_name not in current_columns:
                try:
                    await self.client.execute_query(
                        f"ALTER TABLE InferenceFact ADD COLUMN IF NOT EXISTS {col_name} {col_type}"
                    )
                    logger.info(f"✓ Added column {col_name} to InferenceFact")
                    added_count += 1
                except Exception as e:
                    logger.warning(f"Could not add column {col_name}: {e}")

        if added_count > 0:
            # Recreate MV to include new columns
            logger.info("Recreating mv_otel_to_inference_fact with new columns...")
            try:
                await self.client.execute_query("DROP VIEW IF EXISTS mv_otel_to_inference_fact")
            except Exception as e:
                logger.warning(f"Could not drop existing mv_otel_to_inference_fact: {e}")
            await self.create_mv_otel_to_inference_fact()
        else:
            logger.info("✓ All missing columns already exist in InferenceFact")

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
            await self.migrate_inference_metrics_1h_response_time_sum()  # Add response_time_sum column first
            await self.migrate_response_time_count()  # Add response_time_count for accurate avg latency
            await self.migrate_ttft_columns()  # Add TTFT columns to rollup tables for accurate TTFT metrics
            await self.add_missing_columns_to_inference_fact()  # Add missing columns BEFORE setup_otel_analytics_pipeline
            await self.setup_otel_analytics_pipeline()  # Set up OTel analytics flat + rollup tables
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
