"""ClickHouse storage adapter for evaluation results - simplified version."""

import asyncio
import hashlib
import logging
import time
from contextlib import asynccontextmanager, suppress
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from budeval.commons.config import app_settings
from budeval.evals.storage.base import StorageAdapter


logger = logging.getLogger(__name__)


class ClickHouseStorage(StorageAdapter):
    """Simplified ClickHouse storage adapter for evaluation results."""

    def __init__(self):
        """Initialize ClickHouse storage adapter."""
        self._config = app_settings
        self._pool = None
        self._initialized = False
        # Guard to prevent re-entrant initialization during migrations
        self._initializing = False

    async def initialize(self) -> None:
        """Initialize connection pool and run migrations if needed."""
        if self._initialized:
            return
        # If another coroutine is already initializing, do not re-enter
        if self._initializing:
            return

        self._initializing = True
        try:
            from asynch.pool import Pool

            # Create connection pool
            self._pool = Pool(
                host=self._config.clickhouse_host,
                port=self._config.clickhouse_port,
                user=self._config.clickhouse_user,
                password=self._config.clickhouse_password,
                database=self._config.clickhouse_database,
                minsize=self._config.clickhouse_pool_min_size,
                maxsize=self._config.clickhouse_pool_max_size,
                secure=self._config.clickhouse_secure if hasattr(self._config, "clickhouse_secure") else False,
                # Server-side async insert settings
                server_settings={
                    "async_insert": 1,
                    "wait_for_async_insert": 1,
                    "async_insert_busy_timeout_ms": 1000,
                    "async_insert_max_data_size": 1_000_000,
                    "async_insert_max_query_number": 450,
                },
            )

            # Start the pool
            await self._pool.startup()

            # Run database migrations
            await self._run_migrations()

            self._initialized = True
            logger.info("ClickHouse storage initialized successfully")
        except ImportError as e:
            raise ImportError(
                "ClickHouse dependencies not available. Install with: pip install asynch clickhouse-connect"
            ) from e
        finally:
            self._initializing = False

    async def close(self) -> None:
        """Close the connection pool."""
        if self._pool:
            await self._pool.shutdown()
            self._pool = None
            self._initialized = False
            logger.info("ClickHouse connection pool closed")

    @asynccontextmanager
    async def get_connection(self):
        """Get a connection from the pool."""
        if not self._initialized:
            # If not initialized and not already initializing, perform init
            if not self._initializing:
                await self.initialize()
            else:
                # Wait until pool is available (initialize() sets it before migrations)
                while self._pool is None:
                    await asyncio.sleep(0)

        async with self._pool.connection() as conn:
            yield conn

    async def health_check(self) -> bool:
        """Check if ClickHouse is accessible."""
        try:
            async with self.get_connection() as conn, conn.cursor() as cursor:
                await cursor.execute("SELECT 1")
                result = await cursor.fetchone()
                return result[0] == 1
        except Exception as e:
            logger.error(f"ClickHouse health check failed: {e}")
            return False

    async def save_results(self, job_id: str, results: Dict) -> bool:
        """Save evaluation results using server-side async inserts."""
        try:
            async with self.get_connection() as conn:
                # Save main job record
                await self._save_evaluation_job(conn, job_id, results)

                # Save dataset results
                await self._save_dataset_results(conn, job_id, results)

                # Save predictions in batches
                await self._save_predictions_batch(conn, job_id, results)

                logger.info(f"Successfully saved results for job: {job_id}")
                return True

        except Exception as e:
            logger.error(f"Failed to save results for job {job_id}: {e}")
            return False

    async def get_results(self, job_id: str) -> Optional[Dict]:
        """Retrieve evaluation results for a job."""
        try:
            async with self.get_connection() as conn, conn.cursor() as cursor:
                # Get main job info
                job_query = """
                    SELECT model_name, engine, job_start_time, job_end_time,
                           job_duration_seconds, overall_accuracy, total_datasets,
                           total_examples, total_correct, experiment_id
                    FROM budeval.evaluation_jobs
                    WHERE job_id = %(job_id)s
                    ORDER BY updated_at DESC LIMIT 1
                    """
                await cursor.execute(job_query, {"job_id": job_id})
                job_row = await cursor.fetchone()

                if not job_row:
                    return None

                # Get dataset results
                dataset_query = """
                    SELECT dataset_name, accuracy, total_examples, correct_examples
                    FROM budeval.dataset_results
                    WHERE job_id = %(job_id)s
                    """
                await cursor.execute(dataset_query, {"job_id": job_id})
                dataset_rows = await cursor.fetchall()

                result = {
                    "job_id": job_id,
                    "model_name": job_row[0],
                    "engine": job_row[1],
                    "experiment_id": job_row[9],
                    "summary": {
                        "model_name": job_row[0],
                        "overall_accuracy": float(job_row[5]),
                        "total_datasets": int(job_row[6]),
                        "total_examples": int(job_row[7]),
                        "total_correct": int(job_row[8]),
                    },
                    "datasets": [],
                }

                for row in dataset_rows:
                    dataset = {
                        "dataset_name": row[0],
                        "accuracy": float(row[1]),
                        "total_examples": int(row[2]),
                        "correct_examples": int(row[3]),
                    }
                    result["datasets"].append(dataset)

                return result

        except Exception as e:
            logger.error(f"Failed to get results for job {job_id}: {e}")
            return None

    async def delete_results(self, job_id: str) -> bool:
        """Delete evaluation results for a job."""
        try:
            async with self.get_connection() as conn, conn.cursor() as cursor:
                tables = ["budeval.predictions", "budeval.dataset_results", "budeval.evaluation_jobs"]

                for table in tables:
                    query = f"DELETE FROM {table} WHERE job_id = %(job_id)s"
                    await cursor.execute(query, {"job_id": job_id})

                logger.info(f"Successfully deleted results for job: {job_id}")
                return True

        except Exception as e:
            logger.error(f"Failed to delete results for job {job_id}: {e}")
            return False

    async def list_results(self) -> List[str]:
        """List all available job IDs with results."""
        try:
            async with self.get_connection() as conn, conn.cursor() as cursor:
                query = "SELECT DISTINCT job_id FROM budeval.evaluation_jobs"
                await cursor.execute(query)
                rows = await cursor.fetchall()
                return [row[0] for row in rows]

        except Exception as e:
            logger.error(f"Failed to list results: {e}")
            return []

    async def exists(self, job_id: str) -> bool:
        """Check if results exist for a job."""
        try:
            async with self.get_connection() as conn, conn.cursor() as cursor:
                query = "SELECT 1 FROM budeval.evaluation_jobs WHERE job_id = %(job_id)s LIMIT 1"
                await cursor.execute(query, {"job_id": job_id})
                row = await cursor.fetchone()
                return row is not None

        except Exception as e:
            logger.error(f"Failed to check existence for job {job_id}: {e}")
            return False

    async def create_initial_job_record(
        self, job_id: str, model_name: str, engine: str, experiment_id: Optional[str] = None
    ) -> None:
        """Create an initial job record with 'running' status."""
        try:
            async with self.get_connection() as conn, conn.cursor() as cursor:
                start_time = datetime.now()

                query = """
                INSERT INTO budeval.evaluation_jobs (
                    job_id, experiment_id, model_name, engine, status,
                    job_start_time, job_end_time, job_duration_seconds,
                    overall_accuracy, total_datasets, total_examples, total_correct,
                    extracted_at, created_at, updated_at
                ) VALUES (
                    %(job_id)s, %(experiment_id)s, %(model_name)s, %(engine)s, 'running',
                    %(start_time)s, %(start_time)s, 0.0,
                    0.0, 0, 0, 0,
                    %(start_time)s, %(start_time)s, %(start_time)s
                )
                """

                await cursor.execute(
                    query,
                    {
                        "job_id": job_id,
                        "experiment_id": experiment_id,
                        "model_name": model_name,
                        "engine": engine,
                        "start_time": start_time,
                    },
                )

                logger.info(f"Created initial job record for: {job_id}")

        except Exception as e:
            logger.error(f"Failed to create initial job record for {job_id}: {e}")
            raise

    # Helper methods for saving data
    async def _save_evaluation_job(self, conn, job_id: str, results: Dict) -> None:
        """Save the main evaluation job record."""
        async with conn.cursor() as cursor:
            summary = results.get("summary", {})

            job_data = {
                "job_id": job_id,
                "experiment_id": results.get("experiment_id"),
                "model_name": summary.get("model_name", "unknown"),
                "engine": results.get("engine", "opencompass"),
                "status": "completed",
                "job_start_time": self._parse_datetime(results.get("start_time")),
                "job_end_time": self._parse_datetime(results.get("end_time")),
                "job_duration_seconds": results.get("duration_seconds", 0.0),
                "overall_accuracy": summary.get("overall_accuracy", 0.0),
                "total_datasets": summary.get("total_datasets", 0),
                "total_examples": summary.get("total_examples", 0),
                "total_correct": summary.get("total_correct", 0),
                "extracted_at": self._parse_datetime(results.get("extracted_at")),
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }

            # Use ReplacingMergeTree upsert pattern
            query = """
            INSERT INTO budeval.evaluation_jobs (
                job_id, experiment_id, model_name, engine, status,
                job_start_time, job_end_time, job_duration_seconds,
                overall_accuracy, total_datasets, total_examples, total_correct,
                extracted_at, created_at, updated_at
            ) VALUES (
                %(job_id)s, %(experiment_id)s, %(model_name)s, %(engine)s, %(status)s,
                %(job_start_time)s, %(job_end_time)s, %(job_duration_seconds)s,
                %(overall_accuracy)s, %(total_datasets)s, %(total_examples)s, %(total_correct)s,
                %(extracted_at)s, %(created_at)s, %(updated_at)s
            )
            """

            await cursor.execute(query, job_data)

    async def _save_dataset_results(self, conn, job_id: str, results: Dict) -> None:
        """Save dataset-level results."""
        datasets = results.get("datasets", [])
        if not datasets:
            return

        async with conn.cursor() as cursor:
            dataset_records = []

            for dataset in datasets:
                record = {
                    "job_id": job_id,
                    "model_name": results.get("summary", {}).get("model_name", "unknown"),
                    "dataset_name": dataset.get("dataset_name", "unknown"),
                    "accuracy": dataset.get("accuracy", 0.0),
                    "total_examples": dataset.get("total_examples", 0),
                    "correct_examples": dataset.get("correct_examples", 0),
                    "evaluated_at": self._parse_datetime(results.get("extracted_at")),
                    "metadata": "{}",
                    "created_at": datetime.now(),
                }
                dataset_records.append(record)

            if dataset_records:
                query = """
                INSERT INTO budeval.dataset_results (
                    job_id, model_name, dataset_name, accuracy, total_examples,
                    correct_examples, evaluated_at, metadata, created_at
                ) VALUES (
                    %(job_id)s, %(model_name)s, %(dataset_name)s, %(accuracy)s, %(total_examples)s,
                    %(correct_examples)s, %(evaluated_at)s, %(metadata)s, %(created_at)s
                )
                """

                for record in dataset_records:
                    await cursor.execute(query, record)

    async def _save_predictions_batch(self, conn, job_id: str, results: Dict) -> None:
        """Save predictions in batches."""
        datasets = results.get("datasets", [])
        model_name = results.get("summary", {}).get("model_name", "unknown")
        evaluated_at = self._parse_datetime(results.get("extracted_at"))

        async with conn.cursor() as cursor:
            for dataset in datasets:
                dataset_name = dataset.get("dataset_name", "unknown")
                predictions = dataset.get("predictions", [])

                if not predictions:
                    continue

                # Process predictions in batches
                batch_size = self._config.clickhouse_batch_size
                for i in range(0, len(predictions), batch_size):
                    batch = predictions[i : i + batch_size]
                    await self._insert_predictions_batch(cursor, job_id, model_name, dataset_name, evaluated_at, batch)

                    # Small delay between batches
                    if i + batch_size < len(predictions):
                        await asyncio.sleep(0.1)

    async def _insert_predictions_batch(
        self, cursor, job_id: str, model_name: str, dataset_name: str, evaluated_at: datetime, predictions: List[Dict]
    ) -> None:
        """Insert a batch of predictions."""
        prediction_records = []

        for pred in predictions:
            record = {
                "job_id": job_id,
                "model_name": model_name,
                "dataset_name": dataset_name,
                "example_id": pred.get("example_abbr", "unknown"),
                "prediction_text": str(pred.get("prediction", "")),
                "origin_prompt": str(pred.get("origin_prompt", "")),
                "model_answer": str(pred.get("pred", [""])[0] if pred.get("pred") else ""),
                "correct_answer": str(pred.get("answer", [""])[0] if pred.get("answer") else ""),
                "is_correct": bool(pred.get("correct", [False])[0] if pred.get("correct") else False),
                "evaluated_at": evaluated_at,
                "created_at": datetime.now(),
            }
            prediction_records.append(record)

        if prediction_records:
            query = """
            INSERT INTO budeval.predictions (
                job_id, model_name, dataset_name, example_id, prediction_text,
                origin_prompt, model_answer, correct_answer, is_correct,
                evaluated_at, created_at
            ) VALUES (
                %(job_id)s, %(model_name)s, %(dataset_name)s, %(example_id)s, %(prediction_text)s,
                %(origin_prompt)s, %(model_answer)s, %(correct_answer)s, %(is_correct)s,
                %(evaluated_at)s, %(created_at)s
            )
            """

            for record in prediction_records:
                await cursor.execute(query, record)

    def _parse_datetime(self, dt_input: Any) -> datetime:
        """Parse datetime from various input formats."""
        if isinstance(dt_input, datetime):
            return dt_input
        elif isinstance(dt_input, str):
            try:
                # Try ISO format first
                return datetime.fromisoformat(dt_input.replace("Z", "+00:00"))
            except ValueError:
                pass

        # Fallback to now if parsing fails
        return datetime.now()

    async def _run_migrations(self) -> None:
        """Run ClickHouse database migrations with tracking."""
        try:
            migrations_dir = Path(__file__).parent.parent.parent.parent / "migrations"

            if not migrations_dir.exists():
                logger.warning(f"Migrations directory not found: {migrations_dir}")
                return

            # First, ensure migration tracking table exists
            await self._ensure_migration_tracking_table()

            # Get list of already applied migrations
            applied_migrations = await self._get_applied_migrations()

            # Get all migration files sorted by name
            migration_files = sorted(migrations_dir.glob("*.sql"))

            # Process each migration
            pending_count = 0
            for migration_file in migration_files:
                migration_name = migration_file.stem

                # Skip if already applied
                if migration_name in applied_migrations:
                    continue

                # Calculate checksum for the migration file
                checksum = self._calculate_checksum(migration_file)

                # Apply the migration
                logger.info(f"Applying migration: {migration_name}")
                success = await self._apply_migration(migration_file, migration_name, checksum)

                if success:
                    pending_count += 1
                    logger.info(f"Migration {migration_name} applied successfully")
                else:
                    logger.error(f"Migration {migration_name} failed")

            if pending_count > 0:
                logger.info(f"Applied {pending_count} new migrations")
            else:
                logger.info("All migrations are up to date")

        except Exception as e:
            logger.error(f"Migration process failed: {e}")

    async def _ensure_migration_tracking_table(self) -> None:
        """Ensure the migration tracking table exists."""
        async with self.get_connection() as conn, conn.cursor() as cursor:
            tracking_migration = (
                Path(__file__).parent.parent.parent.parent / "migrations" / "000_migration_tracking.sql"
            )

            if tracking_migration.exists():
                migration_sql = tracking_migration.read_text()
                commands = self._split_sql_commands(migration_sql)

                for command in commands:
                    with suppress(Exception):
                        await cursor.execute(command)

    async def _get_applied_migrations(self) -> Set[str]:
        """Get set of already applied migration versions."""
        try:
            async with self.get_connection() as conn, conn.cursor() as cursor:
                query = "SELECT DISTINCT version FROM budeval.schema_migrations WHERE success = 1"
                await cursor.execute(query)
                rows = await cursor.fetchall()
                return {row[0] for row in rows}
        except Exception:
            return set()

    def _calculate_checksum(self, migration_file: Path) -> str:
        """Calculate SHA256 checksum of migration file content."""
        with open(migration_file, "r", encoding="utf-8") as f:
            content = f.read()
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    async def _apply_migration(self, migration_file: Path, version: str, checksum: str) -> bool:
        """Apply a single migration and record it."""
        start_time = time.time()
        error_message = None
        success = True

        try:
            async with self.get_connection() as conn, conn.cursor() as cursor:
                migration_sql = migration_file.read_text()
                commands = self._split_sql_commands(migration_sql)

                for command in commands:
                    if not command.strip():
                        continue

                    if "schema_migrations" in command and version != "000_migration_tracking":
                        continue

                    try:
                        await cursor.execute(command)
                    except Exception as e:
                        error_str = str(e)
                        if "already exists" not in error_str.lower():
                            error_message = error_str[:500]
                            success = False
                            break

                if success:
                    execution_time_ms = int((time.time() - start_time) * 1000)
                    await self._record_migration(cursor, version, checksum, execution_time_ms, True, None)

        except Exception as e:
            error_message = str(e)[:500]
            success = False

            # Try to record the failure
            try:
                async with self.get_connection() as conn, conn.cursor() as cursor:
                    execution_time_ms = int((time.time() - start_time) * 1000)
                    await self._record_migration(cursor, version, checksum, execution_time_ms, False, error_message)
            except Exception:
                pass

        return success

    async def _record_migration(
        self, cursor, version: str, checksum: str, execution_time_ms: int, success: bool, error_message: Optional[str]
    ) -> None:
        """Record a migration execution in the tracking table."""
        record = {
            "version": version,
            "checksum": checksum,
            "execution_time_ms": execution_time_ms,
            "success": success,
            "error_message": error_message,
        }

        query = """
        INSERT INTO budeval.schema_migrations (
            version, checksum, execution_time_ms, success, error_message
        ) VALUES (
            %(version)s, %(checksum)s, %(execution_time_ms)s, %(success)s, %(error_message)s
        )
        """

        await cursor.execute(query, record)

    def _split_sql_commands(self, sql_text: str) -> List[str]:
        """Split a .sql file into individual statements."""
        result_commands: List[str] = []
        current: List[str] = []
        i = 0
        length = len(sql_text)
        in_single = False
        in_double = False
        in_block_comment = False

        while i < length:
            ch = sql_text[i]

            # Handle start/end of block comments
            if not in_single and not in_double and i < length - 1 and sql_text[i : i + 2] == "/*":
                in_block_comment = True
                i += 2
                continue
            elif in_block_comment and i < length - 1 and sql_text[i : i + 2] == "*/":
                in_block_comment = False
                i += 2
                continue
            elif in_block_comment:
                i += 1
                continue

            # Handle line comments -- ... (skip until end of line)
            if not in_single and not in_double and i < length - 1 and sql_text[i : i + 2] == "--":
                # Skip to end of line
                while i < length and sql_text[i] != "\n":
                    i += 1
                # Retain the newline to avoid gluing tokens together
                if i < length:
                    current.append(sql_text[i])
                    i += 1
                continue

            # Toggle quotes
            if ch == "'" and not in_double:
                in_single = not in_single
            elif ch == '"' and not in_single:
                in_double = not in_double

            # Split on semicolon outside quotes
            if ch == ";" and not in_single and not in_double:
                command = "".join(current).strip()
                if command:
                    result_commands.append(command)
                current = []
            else:
                current.append(ch)

            i += 1

        # Flush last command
        tail = "".join(current).strip()
        if tail:
            result_commands.append(tail)

        # Drop any empty commands
        return [cmd for cmd in result_commands if cmd.strip()]
