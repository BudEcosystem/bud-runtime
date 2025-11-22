#!/usr/bin/env python3
"""Seeder script for observability metrics using the /add endpoint.

This script generates and posts test data to the observability/add endpoint.
Optionally, it can also seed the ModelInference table directly.
"""

import argparse
import asyncio
import json
import os
import random
import sys
import time
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple
from uuid import UUID, uuid4

import aiohttp


# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ["DEBUG"] = "False"
os.environ["LOG_LEVEL"] = "INFO"

from budmicroframe.commons import logging

from budmetrics.observability.models import ClickHouseClient, ClickHouseConfig


logger = logging.get_logger(__name__)


class ObservabilityMetricsSeeder:
    """Seeder for observability metrics via the /add endpoint and direct DB access."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        seed_model_inference: bool = False,
        direct_db: bool = False,
    ):
        """Initialize the observability metrics seeder.

        Args:
            base_url: Base URL of the API
            seed_model_inference: Whether to seed ModelInference table
            direct_db: Whether to use direct DB for ModelInferenceDetails
        """
        self.base_url = base_url
        self.endpoint_url = f"{base_url}/observability/add"
        self.seed_model_inference = seed_model_inference
        self.direct_db = direct_db  # Whether to use direct DB for ModelInferenceDetails

        # Reference data - maintaining relationships
        self.projects = []
        self.models = []
        self.endpoints = []
        self.model_to_endpoints = {}  # Track which endpoints belong to which model
        self.project_to_endpoints = {}  # Track which endpoints belong to which project

        # Model names and providers for realistic data
        self.model_names = [
            "gpt-4",
            "gpt-3.5-turbo",
            "claude-3",
            "llama-2",
            "mistral-7b",
        ]
        self.providers = ["openai", "anthropic", "meta", "mistral"]
        self.finish_reasons = [
            1,
            2,
            3,
            4,
            5,
        ]  # stop, length, tool_call, content_filter, unknown

        # Statistics
        self.total_sent = 0
        self.total_inserted = 0
        self.total_duplicates = 0
        self.total_failed = 0

        # ClickHouse client for direct insertion
        if self.seed_model_inference or self.direct_db:
            self.clickhouse_config = self._get_clickhouse_config()
            self.clickhouse_client = ClickHouseClient(self.clickhouse_config)

    def _get_clickhouse_config(self) -> ClickHouseConfig:
        """Get ClickHouse configuration from environment variables."""
        return ClickHouseConfig(
            host=os.getenv("PSQL_HOST", "localhost"),
            port=int(os.getenv("PSQL_PORT", "9000")),
            database=os.getenv("PSQL_DB_NAME", "tensorzero"),
            user=os.getenv("PSQL_USER", "default"),
            password=os.getenv("PSQL_PASSWORD", ""),
        )

    async def initialize(self):
        """Initialize connections."""
        if self.seed_model_inference or self.direct_db:
            await self.clickhouse_client.initialize()
            logger.info("ClickHouse client initialized for direct DB seeding")

    async def close(self):
        """Close connections."""
        if (self.seed_model_inference or self.direct_db) and self.clickhouse_client:
            await self.clickhouse_client.close()

    def generate_reference_data(self, num_projects: int = 10, num_models: int = 20):
        """Generate reference data maintaining proper relationships."""
        logger.info(f"Generating reference data: {num_projects} projects, {num_models} models...")

        # Generate projects
        self.projects = [uuid4() for _ in range(num_projects)]

        # Generate models with names
        self.models = []
        for i in range(num_models):
            model = {
                "id": uuid4(),
                "name": f"{random.choice(self.model_names)}-{i}",
                "provider": random.choice(self.providers),
            }
            self.models.append(model)

        # Generate endpoints with proper relationships
        # Key constraint: Each endpoint has exactly ONE model
        # Projects can have multiple endpoints
        self.endpoints = []
        self.model_to_endpoints = {model["id"]: [] for model in self.models}
        self.project_to_endpoints = {project: [] for project in self.projects}

        # First, ensure each model has at least one endpoint
        for model in self.models:
            project_id = random.choice(self.projects)
            endpoint = {
                "id": uuid4(),
                "model_id": model["id"],
                "project_id": project_id,
                "model_name": model["name"],
                "provider": model["provider"],
            }
            self.endpoints.append(endpoint)
            self.model_to_endpoints[model["id"]].append(endpoint)
            self.project_to_endpoints[project_id].append(endpoint)

        # Add some additional endpoints (some models will have multiple endpoints)
        additional_endpoints = num_models // 2
        for _ in range(additional_endpoints):
            model = random.choice(self.models)
            project_id = random.choice(self.projects)
            endpoint = {
                "id": uuid4(),
                "model_id": model["id"],
                "project_id": project_id,
                "model_name": model["name"],
                "provider": model["provider"],
            }
            self.endpoints.append(endpoint)
            self.model_to_endpoints[model["id"]].append(endpoint)
            self.project_to_endpoints[project_id].append(endpoint)

        logger.info(f"Generated {len(self.endpoints)} endpoints")
        logger.info("Relationship check: Each endpoint has 1 model, projects have multiple endpoints")

        # Verify relationships
        model_endpoint_counts = [len(endpoints) for endpoints in self.model_to_endpoints.values()]
        project_endpoint_counts = [len(endpoints) for endpoints in self.project_to_endpoints.values()]
        logger.info(f"  Models have 1-{max(model_endpoint_counts)} endpoints each")
        logger.info(f"  Projects have 1-{max(project_endpoint_counts)} endpoints each")

    def _uuid7(self) -> UUID:
        """Generate a UUIDv7 (time-ordered UUID)."""
        timestamp = int(time.time() * 1000)  # milliseconds

        # UUIDv7 format: 48 bits timestamp + 74 bits random
        timestamp_hex = format(timestamp, "012x")
        random_hex = format(random.getrandbits(74), "019x")

        # Construct UUID
        uuid_hex = timestamp_hex + random_hex[:3] + "7" + random_hex[3:7] + "8" + random_hex[7:]

        return UUID(
            uuid_hex[:8] + "-" + uuid_hex[8:12] + "-" + uuid_hex[12:16] + "-" + uuid_hex[16:20] + "-" + uuid_hex[20:32]
        )

    def generate_model_inference_batch(
        self, batch_size: int, base_time: datetime, inference_ids: List[UUID]
    ) -> List[Tuple]:
        """Generate a batch of ModelInference records."""
        records = []

        for i in range(batch_size):
            # Generate UUIDv7 for timestamp extraction
            id_val = self._uuid7()
            inference_id = inference_ids[i]

            # Select an endpoint to get model info
            endpoint = random.choice(self.endpoints)

            # Random realistic data
            input_tokens = random.randint(10, 2000) if random.random() > 0.1 else None
            output_tokens = random.randint(10, 2000) if random.random() > 0.1 else None
            response_time = random.randint(100, 5000) if random.random() > 0.1 else None
            ttft = random.randint(50, response_time) if response_time else None
            cached = random.choice([True, False])
            finish_reason = random.choice(self.finish_reasons) if random.random() > 0.1 else None

            record = (
                str(id_val),
                str(inference_id),
                f"Request {i}",  # raw_request
                f"Response {i}",  # raw_response
                endpoint["model_name"],  # model_name
                endpoint["provider"],  # model_provider_name
                input_tokens,
                output_tokens,
                response_time,
                ttft,
                f"System prompt {i % 10}" if random.random() > 0.5 else None,  # system
                f"Input messages {i}",  # input_messages
                f"Output {i}",  # output
                cached,
                finish_reason,
            )
            records.append(record)

        return records

    def _escape_string(self, value):
        """Escape string for SQL."""
        if value is None:
            return "NULL"
        escaped = value.replace("'", "''")
        return f"'{escaped}'"

    async def _insert_model_inference_batch(self, records):
        """Insert ModelInference records using FORMAT VALUES."""
        if not records:
            return

        values = []
        for r in records:
            row = (
                f"({self._escape_string(r[0])}, {self._escape_string(r[1])}, "
                f"{self._escape_string(r[2])}, {self._escape_string(r[3])}, "
                f"{self._escape_string(r[4])}, {self._escape_string(r[5])}, "
                f"{r[6] if r[6] is not None else 'NULL'}, "
                f"{r[7] if r[7] is not None else 'NULL'}, "
                f"{r[8] if r[8] is not None else 'NULL'}, "
                f"{r[9] if r[9] is not None else 'NULL'}, "
                f"{self._escape_string(r[10])}, {self._escape_string(r[11])}, "
                f"{self._escape_string(r[12])}, {1 if r[13] else 0}, "
                f"{r[14] if r[14] is not None else 'NULL'})"
            )
            values.append(row)

        query = f"""  # nosec B608
        INSERT INTO ModelInference
        (id, inference_id, raw_request, raw_response, model_name, model_provider_name,
         input_tokens, output_tokens, response_time_ms, ttft_ms, system, input_messages,
         output, cached, finish_reason)
        VALUES {",".join(values)}
        """
        await self.clickhouse_client.execute_query(query)

    async def _insert_model_inference_details_batch(self, batch_data: List[Dict[str, Any]]):
        """Insert ModelInferenceDetails records directly to DB."""
        if not batch_data:
            return {"inserted": 0, "duplicates": 0, "failures": 0}

        # Extract all inference_ids to check for existing records
        inference_ids = [record["inference_id"] for record in batch_data]

        # Check for existing inference_ids
        existing_check_query = f"""  # nosec B608
        SELECT inference_id
        FROM ModelInferenceDetails
        WHERE inference_id IN ({",".join([f"'{id}'" for id in inference_ids])})
        """

        existing_records = await self.clickhouse_client.execute_query(existing_check_query)
        existing_ids = {str(row[0]) for row in existing_records} if existing_records else set()

        # Filter out records with existing inference_ids
        new_records = [record for record in batch_data if record["inference_id"] not in existing_ids]
        duplicate_count = len(batch_data) - len(new_records)

        if not new_records:
            logger.debug(f"All {len(batch_data)} records already exist, skipping insert")
            return {"inserted": 0, "duplicates": duplicate_count, "failures": 0}

        # Build VALUES clause
        values = []
        for record in new_records:
            row = (
                f"({self._escape_string(record['inference_id'])}, "
                f"{self._escape_string(record.get('request_ip')) if record.get('request_ip') else 'NULL'}, "
                f"{self._escape_string(record['project_id'])}, "
                f"{self._escape_string(record['endpoint_id'])}, "
                f"{self._escape_string(record['model_id'])}, "
                f"{record.get('cost') if record.get('cost') is not None else 'NULL'}, "
                f"{self._escape_string(json.dumps(record['response_analysis'])) if record.get('response_analysis') else 'NULL'}, "
                f"{1 if record['is_success'] else 0}, "
                f"'{record['request_arrival_time']}', "
                f"'{record['request_forward_time']}')"
            )
            values.append(row)

        # Build and execute the INSERT query
        query = f"""  # nosec B608
        INSERT INTO ModelInferenceDetails
        (inference_id, request_ip, project_id, endpoint_id, model_id,
         cost, response_analysis, is_success, request_arrival_time, request_forward_time)
        VALUES {",".join(values)}
        """

        try:
            await self.clickhouse_client.execute_query(query)
            return {"inserted": len(new_records), "duplicates": duplicate_count, "failures": 0}
        except Exception as e:
            logger.error(f"Error inserting ModelInferenceDetails batch: {e}")
            return {"inserted": 0, "duplicates": duplicate_count, "failures": len(new_records)}

    def generate_batch_data(self, batch_size: int, base_time: datetime) -> Tuple[List[Dict[str, Any]], List[UUID]]:
        """Generate a batch of InferenceDetailsMetrics data."""
        batch_data = []
        inference_ids = []

        for _ in range(batch_size):
            # Generate inference_id that will be shared between both tables
            inference_id = uuid4()
            inference_ids.append(inference_id)

            # Select an endpoint (which has model_id and project_id)
            endpoint = random.choice(self.endpoints)

            # Generate realistic times
            time_offset = timedelta(seconds=random.randint(0, 3600))
            request_time = base_time + time_offset
            forward_time = request_time + timedelta(milliseconds=random.randint(1, 100))

            # Success rate around 95%
            is_success = random.random() < 0.95

            # Cost calculation
            cost = round(random.uniform(0.001, 0.1), 4) if is_success else None

            # IP address (optional)
            request_ip = None
            if random.random() > 0.3:  # 70% have IP
                request_ip = f"192.168.{random.randint(1, 255)}.{random.randint(1, 255)}"

            # Response analysis (optional)
            response_analysis = None
            if is_success and random.random() > 0.5:  # 50% of successful requests have analysis
                response_analysis = {
                    "sentiment": random.choice(["positive", "negative", "neutral"]),
                    "confidence": round(random.random(), 2),
                    "topics": [f"topic_{j}" for j in range(random.randint(1, 3))],
                    "language": random.choice(["en", "es", "fr", "de"]),
                    "model_name": endpoint["model_name"],  # Include model info in analysis
                }

            # Create the metric data following InferenceDetailsMetrics schema
            metric_data = {
                "inference_id": str(inference_id),
                "project_id": str(endpoint["project_id"]),
                "endpoint_id": str(endpoint["id"]),
                "model_id": str(endpoint["model_id"]),
                "is_success": is_success,
                "request_arrival_time": request_time.strftime("%Y-%m-%d %H:%M:%S"),
                "request_forward_time": forward_time.strftime("%Y-%m-%d %H:%M:%S"),
                "cost": cost,
                "request_ip": request_ip,
                "response_analysis": response_analysis,
                # CloudEventBase fields
                "type": "com.budserve.metrics.inference",
                "source": "observability-seeder",
                "id": str(uuid4()),
                "time": datetime.now(timezone.utc).isoformat(),
                "datacontenttype": "application/json",
                "specversion": "1.0",
            }

            batch_data.append(metric_data)

        return batch_data, inference_ids

    def create_bulk_request(self, batch_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create a BulkCloudEventBase request from batch data."""
        request_id = str(uuid4())

        entries = []
        for data in batch_data:
            # Remove CloudEventBase fields from the event data
            event_data = {
                "inference_id": data["inference_id"],
                "project_id": data["project_id"],
                "endpoint_id": data["endpoint_id"],
                "model_id": data["model_id"],
                "is_success": data["is_success"],
                "request_arrival_time": data["request_arrival_time"],
                "request_forward_time": data["request_forward_time"],
                "request_ip": data.get("request_ip"),
                "cost": data.get("cost"),
                "response_analysis": data.get("response_analysis"),
            }

            entry = {
                "event": event_data,
                "entryId": request_id,
                "metadata": {
                    "cloudevent.id": request_id,
                    "cloudevent.type": "add_request_metrics",
                },
                "contentType": "add_request_metrics",
            }
            entries.append(entry)

        return {
            "entries": entries,
            "id": request_id,
            "metadata": {},
            "pubsubname": "pubsub",
            "topic": "topic",
            "type": "add_request_metrics",
        }

    async def send_batch(self, session: aiohttp.ClientSession, batch_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Send a batch of metrics to the /add endpoint."""
        bulk_request = self.create_bulk_request(batch_data)

        try:
            async with session.post(
                self.endpoint_url,
                json=bulk_request,
                headers={"Content-Type": "application/json"},
            ) as response:
                result = await response.json()

                if response.status == 200:
                    # Extract summary from successful response
                    param = result.get("param", {})
                    summary = param.get("summary", {})
                    return {
                        "success": True,
                        "status": response.status,
                        "inserted": summary.get("successfully_inserted", 0),
                        "duplicates": summary.get("duplicates_skipped", 0),
                        "failures": summary.get("validation_failures", 0),
                        "message": result.get("message", ""),
                    }
                else:
                    return {
                        "success": False,
                        "status": response.status,
                        "error": result.get("message", "Unknown error"),
                        "details": result.get("details", {}),
                    }

        except Exception as e:
            logger.error(f"Error sending batch: {e}")
            return {"success": False, "error": str(e)}

    async def seed_data(
        self,
        total_records: int = 10000,
        batch_size: int = 100,
        start_date: datetime = None,
        end_date: datetime = None,
        delay_between_batches: float = 0.1,
    ):
        """Seed the database with test data via the API."""
        if start_date is None:
            start_date = datetime.now(UTC) - timedelta(days=30)
        if end_date is None:
            end_date = datetime.now(UTC)

        # Initialize if needed
        await self.initialize()

        # Generate reference data
        self.generate_reference_data()

        total_batches = (total_records + batch_size - 1) // batch_size
        time_range = (end_date - start_date).total_seconds()

        logger.info("\nStarting data seeding:")
        if self.direct_db:
            logger.info(
                f"  ModelInferenceDetails via direct DB: {self.clickhouse_config.host}:{self.clickhouse_config.port}"
            )
        else:
            logger.info(f"  ModelInferenceDetails via API: {self.endpoint_url}")
        if self.seed_model_inference:
            logger.info(f"  ModelInference via direct DB: {self.clickhouse_config.host}:{self.clickhouse_config.port}")
        logger.info(f"  Total records: {total_records:,}")
        logger.info(f"  Batch size: {batch_size:,}")
        logger.info(f"  Total batches: {total_batches:,}")
        logger.info(f"  Date range: {start_date} to {end_date}")

        start_time = time.time()

        async with aiohttp.ClientSession() as session:
            for batch_num in range(total_batches):
                # Calculate time for this batch
                batch_time = start_date + timedelta(seconds=(batch_num / total_batches) * time_range)

                # Calculate actual batch size for last batch
                current_batch_size = min(batch_size, total_records - (batch_num * batch_size))

                # Generate batch data with shared inference_ids
                batch_data, inference_ids = self.generate_batch_data(current_batch_size, batch_time)

                # If seeding ModelInference, insert that data first
                if self.seed_model_inference:
                    try:
                        inference_records = self.generate_model_inference_batch(
                            current_batch_size, batch_time, inference_ids
                        )
                        await self._insert_model_inference_batch(inference_records)
                    except Exception as e:
                        logger.error(f"Error inserting ModelInference batch {batch_num + 1}: {e}")

                # Send ModelInferenceDetails either via API or direct DB
                if self.direct_db:
                    # Direct DB insertion
                    result = await self._insert_model_inference_details_batch(batch_data)
                    self.total_sent += current_batch_size
                    self.total_inserted += result.get("inserted", 0)
                    self.total_duplicates += result.get("duplicates", 0)
                    self.total_failed += result.get("failures", 0)
                else:
                    # API insertion
                    result = await self.send_batch(session, batch_data)

                    # Update statistics
                    self.total_sent += current_batch_size
                    if result.get("success"):
                        self.total_inserted += result.get("inserted", 0)
                        self.total_duplicates += result.get("duplicates", 0)
                        self.total_failed += result.get("failures", 0)
                    else:
                        self.total_failed += current_batch_size
                        logger.error(f"Batch {batch_num + 1} failed: {result.get('error')}")

                # Progress update
                if (batch_num + 1) % 10 == 0 or batch_num == total_batches - 1:
                    elapsed = time.time() - start_time
                    rate = self.total_sent / elapsed if elapsed > 0 else 0
                    eta = (total_records - self.total_sent) / rate if rate > 0 else 0

                    logger.info(
                        f"Progress: {self.total_sent:,}/{total_records:,} sent "
                        f"({self.total_sent / total_records * 100:.1f}%) - "
                        f"Inserted: {self.total_inserted:,}, "
                        f"Duplicates: {self.total_duplicates:,}, "
                        f"Failed: {self.total_failed:,} - "
                        f"Rate: {rate:.0f} records/sec - "
                        f"ETA: {eta / 60:.1f} minutes"
                    )

                # Delay between batches to avoid overwhelming the server
                if batch_num < total_batches - 1:
                    await asyncio.sleep(delay_between_batches)

        # Final summary
        elapsed = time.time() - start_time
        logger.info("\nSeeding completed:")
        logger.info(f"  Total time: {elapsed:.1f} seconds")
        logger.info(f"  Records sent: {self.total_sent:,}")
        logger.info(f"  Successfully inserted: {self.total_inserted:,}")
        logger.info(f"  Duplicates skipped: {self.total_duplicates:,}")
        logger.info(f"  Failed: {self.total_failed:,}")
        logger.info(f"  Average rate: {self.total_sent / elapsed:.0f} records/second")

    async def verify_data(self):
        """Verify the seeded data by calling the analytics endpoint."""
        logger.info("\nVerifying seeded data...")

        # Create a simple analytics request
        analytics_url = f"{self.base_url}/observability/analytics"
        analytics_request = {
            "metrics": ["request_count"],
            "from_date": (datetime.now(UTC) - timedelta(days=31)).isoformat(),
            "to_date": datetime.now(UTC).isoformat(),
            "frequency_unit": "day",
            "return_delta": False,
            "fill_time_gaps": False,
        }

        try:
            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    analytics_url,
                    json=analytics_request,
                    headers={"Content-Type": "application/json"},
                ) as response,
            ):
                if response.status == 200:
                    result = await response.json()

                    # Count total requests from all time periods
                    total_requests = 0
                    for period in result.get("items", []):
                        for item in period.get("items", []):
                            request_count = item.get("data", {}).get("request_count", {}).get("count", 0)
                            total_requests += request_count

                    logger.info(f"  Total records in ModelInferenceDetails: {total_requests:,}")
                    logger.info(f"  Expected records (inserted): {self.total_inserted:,}")

                    if total_requests >= self.total_inserted:
                        logger.info("  ✓ Verification successful!")
                    else:
                        logger.warning("  ⚠ Found fewer records than expected")
                else:
                    logger.error(f"  Failed to verify: HTTP {response.status}")

        except Exception as e:
            logger.error(f"  Verification error: {e}")

        # Verify relationships if we have direct DB access
        if self.seed_model_inference or self.direct_db:
            logger.info("\nVerifying relationships...")
            try:
                # Check endpoint-model relationship (should be 1:1)
                result = await self.clickhouse_client.execute_query(
                    """
                    SELECT endpoint_id, COUNT(DISTINCT model_id) as model_count
                    FROM ModelInferenceDetails
                    GROUP BY endpoint_id
                    HAVING model_count > 1
                    LIMIT 10
                """
                )
                if result:
                    logger.warning(f"  WARNING: Found {len(result)} endpoints with multiple models!")
                else:
                    logger.info("  ✓ All endpoints have exactly one model (correct 1:1 relationship)")

                # Check project-endpoint relationship (should be 1:many)
                result = await self.clickhouse_client.execute_query(
                    """
                    SELECT project_id, COUNT(DISTINCT endpoint_id) as endpoint_count
                    FROM ModelInferenceDetails
                    GROUP BY project_id
                    ORDER BY endpoint_count DESC
                    LIMIT 5
                """
                )
                if result:
                    logger.info("  Top 5 projects by endpoint count:")
                    for project_id, endpoint_count in result:
                        logger.info(f"    Project {str(project_id)[:8]}...: {endpoint_count} endpoints")
            except Exception as e:
                logger.error(f"  Relationship verification error: {e}")


async def main():
    """Run the seeder."""
    parser = argparse.ArgumentParser(description="Seed observability metrics via the /add API endpoint")
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Base URL of the API (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--records",
        type=int,
        default=10000,
        help="Total number of records to seed (default: 10000)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of records per batch (default: 100)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days to spread the data over (default: 30)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.1,
        help="Delay between batches in seconds (default: 0.1)",
    )
    parser.add_argument(
        "--seed-model-inference",
        action="store_true",
        help="Also seed ModelInference table directly (requires DB access)",
    )
    parser.add_argument(
        "--direct-db",
        action="store_true",
        help="Use direct DB insertion for ModelInferenceDetails instead of API",
    )
    parser.add_argument("--verify", action="store_true", help="Verify the data after seeding")

    args = parser.parse_args()

    seeder = ObservabilityMetricsSeeder(
        base_url=args.url, seed_model_inference=args.seed_model_inference, direct_db=args.direct_db
    )

    try:
        # Calculate date range
        end_date = datetime.now(UTC)
        start_date = end_date - timedelta(days=args.days)

        # Seed the data
        await seeder.seed_data(
            total_records=args.records,
            batch_size=args.batch_size,
            start_date=start_date,
            end_date=end_date,
            delay_between_batches=args.delay,
        )

        # Optionally verify
        if args.verify:
            await seeder.verify_data()

    except KeyboardInterrupt:
        logger.info("\nSeeding interrupted by user")
    except Exception as e:
        logger.error(f"Seeding error: {e}")
        sys.exit(1)
    finally:
        await seeder.close()


if __name__ == "__main__":
    asyncio.run(main())
