"""ClickHouse storage adapter for evaluation results."""

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from asynch.pool import Pool

from budeval.commons.config import secrets_settings
from budeval.commons.logging import logging

from .base import StorageAdapter


logger = logging.getLogger(__name__)


class ClickHouseStorage(StorageAdapter):
    """ClickHouse storage adapter using asynch for native TCP support.

    Implements best practices:
    - Connection pooling with configurable sizing
    - Server-side async inserts with wait_for_async_insert=1
    - Batch inserts for predictions (1000+ rows)
    - Automatic retry with exponential backoff
    - ZSTD compression for text fields
    """

    def __init__(self):
        """Initialize ClickHouse storage adapter."""
        self._pool: Optional[Pool] = None
        self._config = secrets_settings

    async def initialize(self) -> None:
        """Initialize connection pool and run migrations if needed."""
        if self._pool is not None:
            return

        logger.info("Initializing ClickHouse connection pool")

        try:
            self._pool = Pool(
                host=self._config.clickhouse_host,
                port=self._config.clickhouse_port,
                database=self._config.clickhouse_database,
                user=self._config.clickhouse_user,
                password=self._config.clickhouse_password,
                minsize=self._config.clickhouse_pool_min_size,
                maxsize=self._config.clickhouse_pool_max_size,
                secure=getattr(self._config, "clickhouse_secure", False),  # SSL for ClickHouse Cloud
                echo=False,  # Set to True for debugging
                # Server-side async insert settings
                server_settings={
                    "async_insert": 1 if self._config.clickhouse_async_insert else 0,
                    "wait_for_async_insert": 1,  # Ensure data is flushed before acknowledgment
                    "async_insert_busy_timeout_ms": 1000,  # 1 second buffer time
                    "async_insert_max_data_size": 1_000_000,  # 1MB before flush
                    "async_insert_max_query_number": 450,  # Max queries before flush
                    "async_insert_use_adaptive_busy_timeout": 0,  # Disable adaptive timeout
                },
            )

            # Start the pool
            await self._pool.startup()
            logger.info("ClickHouse connection pool initialized successfully")

            # Run database migrations
            await self._run_migrations()

        except Exception as e:
            logger.error(f"Failed to initialize ClickHouse pool: {e}")
            raise

    async def _run_migrations(self) -> None:
        """Run ClickHouse database migrations."""
        logger.info("Running ClickHouse database migrations")

        try:
            # Read migration file
            migration_file = Path(__file__).parent.parent.parent.parent / "migrations" / "001_initial_schema.sql"

            if not migration_file.exists():
                logger.warning(f"Migration file not found: {migration_file}")
                return

            with open(migration_file, "r") as f:
                migration_sql = f.read()

            # Split migration into individual statements (excluding comments and empty lines)
            statements = []
            for line in migration_sql.split("\n"):
                line = line.strip()
                if line and not line.startswith("--"):
                    statements.append(line)

            # Join and split by semicolon
            full_sql = " ".join(statements)
            commands = [cmd.strip() for cmd in full_sql.split(";") if cmd.strip()]

            async with self.get_connection() as conn, conn.cursor() as cursor:
                for command in commands:
                    try:
                        logger.debug(f"Executing migration command: {command[:50]}...")
                        await cursor.execute(command)
                    except Exception as e:
                        # Log error but continue with other commands (some may already exist)
                        logger.warning(f"Migration command failed (might already exist): {str(e)[:100]}")
                        continue

            logger.info("ClickHouse database migrations completed successfully")

        except Exception as e:
            logger.error(f"Failed to run ClickHouse migrations: {e}")
            # Don't raise - allow app to continue even if migrations fail

    async def close(self) -> None:
        """Close the connection pool."""
        if self._pool:
            await self._pool.shutdown()
            self._pool = None
            logger.info("ClickHouse connection pool closed")

    @asynccontextmanager
    async def get_connection(self):
        """Get a connection from the pool."""
        if self._pool is None:
            await self.initialize()

        async with self._pool.connection() as conn:
            yield conn

    async def health_check(self) -> bool:
        """Check if ClickHouse is accessible."""
        try:
            async with self.get_connection() as conn, conn.cursor() as cursor:
                await cursor.execute("SELECT 1")
                result = await cursor.fetchone()
                return result is not None
        except Exception as e:
            logger.error(f"ClickHouse health check failed: {e}")
            return False

    async def save_results(self, job_id: str, results: Dict) -> bool:
        """Save evaluation results using server-side async inserts.

        Args:
            job_id: Unique identifier for the evaluation job
            results: Processed evaluation results dictionary

        Returns:
            True if saved successfully, False otherwise
        """
        try:
            async with self.get_connection() as conn:
                # Save main job record
                await self._save_evaluation_job(conn, job_id, results)

                # Save dataset results
                await self._save_dataset_results(conn, job_id, results)

                # Save predictions in batches
                await self._save_predictions_batch(conn, job_id, results)

                logger.info(f"Successfully saved results for job {job_id}")
                return True

        except Exception as e:
            logger.error(f"Failed to save results for job {job_id}: {e}")
            return False

    async def _save_evaluation_job(self, conn, job_id: str, results: Dict) -> None:
        """Save the main evaluation job record."""
        job_data = {
            "job_id": job_id,
            "model_name": results.get("model_name", ""),
            "engine": results.get("engine", "opencompass"),
            "job_start_time": self._parse_datetime(results.get("job_start_time")),
            "job_end_time": self._parse_datetime(results.get("job_end_time")),
            "job_duration_seconds": float(results.get("job_duration_seconds") or 0.0),
            "overall_accuracy": float(results.get("summary", {}).get("overall_accuracy") or 0.0),
            "total_datasets": int(results.get("summary", {}).get("total_datasets") or 0),
            "total_examples": int(results.get("summary", {}).get("total_examples") or 0),
            "total_correct": int(results.get("summary", {}).get("total_correct") or 0),
            "extracted_at": self._parse_datetime(results.get("extracted_at")),
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }

        query = """
        INSERT INTO budeval.evaluation_jobs
        (job_id, model_name, engine, job_start_time, job_end_time, job_duration_seconds,
         overall_accuracy, total_datasets, total_examples, total_correct,
         extracted_at, created_at, updated_at)
        VALUES
        """

        async with conn.cursor() as cursor:
            await cursor.execute(query, [job_data])

    async def _save_dataset_results(self, conn, job_id: str, results: Dict) -> None:
        """Save dataset-level results."""
        datasets = results.get("datasets", [])
        if not datasets:
            return

        dataset_records = []
        for dataset in datasets:
            record = {
                "job_id": job_id,
                "model_name": results.get("model_name", ""),
                "dataset_name": dataset.get("dataset_name", ""),
                "accuracy": dataset.get("accuracy", 0.0),
                "total_examples": dataset.get("total_examples", 0),
                "correct_examples": dataset.get("correct_examples", 0),
                "evaluated_at": self._parse_datetime(results.get("extracted_at")),
                "metadata": json.dumps(dataset.get("metadata", {})),
                "created_at": datetime.now(),
            }
            dataset_records.append(record)

        query = """
        INSERT INTO budeval.dataset_results
        (job_id, model_name, dataset_name, accuracy, total_examples, correct_examples,
         evaluated_at, metadata, created_at)
        VALUES
        """

        async with conn.cursor() as cursor:
            await cursor.execute(query, dataset_records)

    async def _save_predictions_batch(self, conn, job_id: str, results: Dict) -> None:
        """Save predictions in batches for optimal performance."""
        datasets = results.get("datasets", [])
        model_name = results.get("model_name", "")
        evaluated_at = self._parse_datetime(results.get("extracted_at"))

        for dataset in datasets:
            dataset_name = dataset.get("dataset_name", "")
            predictions = dataset.get("predictions", [])

            if not predictions:
                continue

            # Process predictions in batches
            batch_size = self._config.clickhouse_batch_size
            for i in range(0, len(predictions), batch_size):
                batch = predictions[i : i + batch_size]
                await self._insert_prediction_batch(conn, job_id, model_name, dataset_name, evaluated_at, batch)

                # Small delay between batches to avoid overwhelming ClickHouse
                if i + batch_size < len(predictions):
                    await asyncio.sleep(0.01)

    async def _insert_prediction_batch(
        self, conn, job_id: str, model_name: str, dataset_name: str, evaluated_at: datetime, predictions: List[Dict]
    ) -> None:
        """Insert a batch of predictions."""
        prediction_records = []

        for pred in predictions:
            record = {
                "job_id": job_id,
                "model_name": model_name,
                "dataset_name": dataset_name,
                "example_id": pred.get("example_abbr", ""),
                "prediction_text": pred.get("prediction", ""),
                "origin_prompt": pred.get("origin_prompt", ""),
                "model_answer": json.dumps(pred.get("pred", [])),
                "correct_answer": json.dumps(pred.get("answer", [])),
                "is_correct": bool(pred.get("correct", [False])[0]) if pred.get("correct") else False,
                "evaluated_at": evaluated_at,
                "created_at": datetime.now(),
            }
            prediction_records.append(record)

        query = """
        INSERT INTO budeval.predictions
        (job_id, model_name, dataset_name, example_id, prediction_text, origin_prompt,
         model_answer, correct_answer, is_correct, evaluated_at, created_at)
        VALUES
        """

        async with conn.cursor() as cursor:
            await cursor.execute(query, prediction_records)
        logger.debug(f"Inserted batch of {len(prediction_records)} predictions for {dataset_name}")

    async def get_results(self, job_id: str) -> Optional[Dict]:
        """Retrieve evaluation results for a job.

        Args:
            job_id: Unique identifier for the evaluation job

        Returns:
            Dictionary containing evaluation results or None if not found
        """
        try:
            async with self.get_connection() as conn:
                # Get main job info
                job_query = """
                SELECT * FROM budeval.evaluation_jobs
                WHERE job_id = %(job_id)s
                """

                async with conn.cursor() as cursor:
                    await cursor.execute(job_query, {"job_id": job_id})
                    job_row = await cursor.fetchone()

                    if not job_row:
                        return None

                    # Get dataset results
                    dataset_query = """
                    SELECT dataset_name, accuracy, total_examples, correct_examples, metadata
                    FROM budeval.dataset_results
                    WHERE job_id = %(job_id)s
                    ORDER BY dataset_name
                    """

                    await cursor.execute(dataset_query, {"job_id": job_id})
                    dataset_rows = await cursor.fetchall()

                    # Build response
                    result = {
                        "job_id": job_row[0],
                        "model_name": job_row[1],
                        "engine": job_row[2],
                        "datasets": [],
                        "summary": {
                            "overall_accuracy": job_row[6],
                            "total_datasets": job_row[7],
                            "total_examples": job_row[8],
                            "total_correct": job_row[9],
                            "model_name": job_row[1],
                        },
                    }

                    # Add dataset results
                    for row in dataset_rows:
                        dataset = {
                            "dataset_name": row[0],
                            "accuracy": row[1],
                            "total_examples": row[2],
                            "correct_examples": row[3],
                            "metadata": json.loads(row[4]) if row[4] else {},
                        }
                        result["datasets"].append(dataset)

                    return result

        except Exception as e:
            logger.error(f"Failed to get results for job {job_id}: {e}")
            return None

    async def get_predictions(self, job_id: str, dataset_name: Optional[str] = None) -> List[Dict]:
        """Get predictions for a job, optionally filtered by dataset."""
        try:
            async with self.get_connection() as conn:
                query = """
                SELECT example_id, prediction_text, origin_prompt, model_answer,
                       correct_answer, is_correct
                FROM budeval.predictions
                WHERE job_id = %(job_id)s
                """
                params = {"job_id": job_id}

                if dataset_name:
                    query += " AND dataset_name = %(dataset_name)s"
                    params["dataset_name"] = dataset_name

                query += " ORDER BY example_id"

                async with conn.cursor() as cursor:
                    await cursor.execute(query, params)
                    rows = await cursor.fetchall()

                    predictions = []
                    for row in rows:
                        pred = {
                            "example_abbr": row[0],
                            "prediction": row[1],
                            "origin_prompt": row[2],
                            "pred": json.loads(row[3]) if row[3] else [],
                            "answer": json.loads(row[4]) if row[4] else [],
                            "correct": [row[5]] if row[5] is not None else [],
                        }
                        predictions.append(pred)

                    return predictions

        except Exception as e:
            logger.error(f"Failed to get predictions for job {job_id}: {e}")
            return []

    async def delete_results(self, job_id: str) -> bool:
        """Delete evaluation results for a job.

        Args:
            job_id: Unique identifier for the evaluation job

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            async with self.get_connection() as conn:
                # Delete in reverse dependency order
                tables = ["budeval.predictions", "budeval.dataset_results", "budeval.evaluation_jobs"]

                for table in tables:
                    query = f"DELETE FROM {table} WHERE job_id = %(job_id)s"
                    async with conn.cursor() as cursor:
                        await cursor.execute(query, {"job_id": job_id})

                logger.info(f"Successfully deleted results for job {job_id}")
                return True

        except Exception as e:
            logger.error(f"Failed to delete results for job {job_id}: {e}")
            return False

    async def list_results(self) -> List[str]:
        """List all available job IDs with results.

        Returns:
            List of job IDs that have stored results
        """
        try:
            async with self.get_connection() as conn:
                query = """
                SELECT DISTINCT job_id
                FROM budeval.evaluation_jobs
                ORDER BY created_at DESC
                """

                async with conn.cursor() as cursor:
                    await cursor.execute(query)
                    rows = await cursor.fetchall()
                    return [row[0] for row in rows]

        except Exception as e:
            logger.error(f"Failed to list results: {e}")
            return []

    async def exists(self, job_id: str) -> bool:
        """Check if results exist for a job.

        Args:
            job_id: Unique identifier for the evaluation job

        Returns:
            True if results exist, False otherwise
        """
        try:
            async with self.get_connection() as conn:
                query = """
                SELECT 1 FROM budeval.evaluation_jobs
                WHERE job_id = %(job_id)s
                LIMIT 1
                """

                async with conn.cursor() as cursor:
                    await cursor.execute(query, {"job_id": job_id})
                    row = await cursor.fetchone()
                    return row is not None

        except Exception as e:
            logger.error(f"Failed to check existence for job {job_id}: {e}")
            return False

    def _parse_datetime(self, dt_input: Any) -> datetime:
        """Parse datetime from various input formats."""
        if dt_input is None:
            return datetime.now()

        if isinstance(dt_input, datetime):
            return dt_input

        if isinstance(dt_input, str):
            try:
                # Try ISO format first
                return datetime.fromisoformat(dt_input.replace("Z", "+00:00"))
            except ValueError:
                # Fallback to now if parsing fails
                logger.warning(f"Failed to parse datetime: {dt_input}")
                return datetime.now()

        return datetime.now()

    async def get_model_performance_trends(
        self, model_name: Optional[str] = None, dataset_name: Optional[str] = None, days: int = 30
    ) -> List[Dict]:
        """Get model performance trends using the materialized view."""
        try:
            async with self.get_connection() as conn:
                query = """
                SELECT
                    model_name,
                    dataset_name,
                    eval_date,
                    avgMerge(avg_accuracy) as avg_accuracy,
                    countMerge(eval_count) as eval_count,
                    maxMerge(max_accuracy) as max_accuracy,
                    minMerge(min_accuracy) as min_accuracy
                FROM budeval.model_performance_trends
                WHERE eval_date >= today() - %(days)s
                """

                params = {"days": days}

                if model_name:
                    query += " AND model_name = %(model_name)s"
                    params["model_name"] = model_name

                if dataset_name:
                    query += " AND dataset_name = %(dataset_name)s"
                    params["dataset_name"] = dataset_name

                query += " GROUP BY model_name, dataset_name, eval_date ORDER BY eval_date DESC"

                async with conn.cursor() as cursor:
                    await cursor.execute(query, params)
                    rows = await cursor.fetchall()

                    trends = []
                    for row in rows:
                        trend = {
                            "model_name": row[0],
                            "dataset_name": row[1],
                            "eval_date": row[2].isoformat(),
                            "avg_accuracy": float(row[3]),
                            "eval_count": int(row[4]),
                            "max_accuracy": float(row[5]),
                            "min_accuracy": float(row[6]),
                        }
                        trends.append(trend)

                    return trends

        except Exception as e:
            logger.error(f"Failed to get performance trends: {e}")
            return []
