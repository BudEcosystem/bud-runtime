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
                    raise Exception(f"ClickHouse connection failed: {e}")

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
            finish_reason Nullable(Enum8('stop' = 1, 'length' = 2, 'tool_call' = 3, 'content_filter' = 4, 'unknown' = 5))
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

    async def verify_tables(self):
        """Verify that tables were created successfully."""
        tables_to_check = ["ModelInferenceDetails"]
        if self.include_model_inference:
            tables_to_check.append("ModelInference")

        for table in tables_to_check:
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

    async def run_migration(self):
        """Run the complete migration process."""
        try:
            await self.initialize()
            await self.create_database()
            await self.create_model_inference_details_table()
            await self.create_model_inference_table()
            await self.verify_tables()
            logger.info("Migration completed successfully!")

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            raise
        finally:
            await self.client.close()


async def main():
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
