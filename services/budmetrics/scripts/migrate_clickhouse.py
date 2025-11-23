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
            hardware_mode LowCardinality(String) DEFAULT 'whole-gpu'  -- 'time-slicing', 'mig', 'whole-gpu'
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
            await self.migrate_node_metrics_network_columns()  # Add network columns to NodeMetrics (legacy migration)
            await self.setup_cluster_metrics_materialized_views()  # Set up materialized views for cluster metrics
            await self.add_auth_metadata_columns()  # Add auth metadata columns migration
            await self.update_api_key_project_id()  # Update api_key_project_id where null
            await self.add_error_tracking_columns()  # Add error tracking columns for failed inferences
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
