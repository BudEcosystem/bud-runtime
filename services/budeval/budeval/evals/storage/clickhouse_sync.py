"""Synchronous ClickHouse storage adapter for evaluation results.

This implementation uses synchronous clickhouse-connect client to avoid
event loop conflicts in Dapr workflows. It's simpler and more reliable
than the async version when running within workflow threads.
"""

import contextlib
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import clickhouse_connect
from clickhouse_connect.driver import Client

from budeval.commons.config import app_settings

from .base import StorageAdapter


logger = logging.getLogger(__name__)


class ClickHouseSyncStorage(StorageAdapter):
    """Synchronous ClickHouse storage adapter for evaluation results."""

    def __init__(self):
        """Initialize ClickHouse sync storage with configuration from settings."""
        self.host = app_settings.clickhouse_host
        self.http_port = app_settings.clickhouse_http_port
        self.database = app_settings.clickhouse_database
        self.user = app_settings.clickhouse_user
        self.password = app_settings.clickhouse_password
        self.batch_size = app_settings.clickhouse_batch_size

        self._client: Optional[Client] = None
        logger.info(
            f"Initialized ClickHouseSyncStorage with host={self.host}, "
            f"http_port={self.http_port}, database={self.database}"
        )

    def _get_client(self) -> Client:
        """Get or create ClickHouse client."""
        if self._client is None:
            self._client = clickhouse_connect.get_client(
                host=self.host,
                port=self.http_port,
                database=self.database,
                username=self.user,
                password=self.password,
                settings={
                    "async_insert": 1 if app_settings.clickhouse_async_insert else 0,
                    "wait_for_async_insert": 1,
                    "async_insert_busy_timeout_ms": 5000,
                },
            )
            logger.debug(f"Created new ClickHouse client connection to {self.host}:{self.http_port}")
        return self._client

    def close(self):
        """Close the ClickHouse client connection."""
        if self._client:
            self._client.close()
            self._client = None
            logger.debug("Closed ClickHouse client connection")

    async def initialize(self) -> None:
        """Initialize storage (no-op for sync implementation)."""
        # Verify connection works
        try:
            client = self._get_client()
            client.query("SELECT 1")
            logger.info("ClickHouse connection verified successfully")
        except Exception as e:
            logger.error(f"Failed to verify ClickHouse connection: {e}")
            raise

    async def save_results(self, job_id: str, results: Dict) -> bool:
        """Save evaluation results to ClickHouse.

        This is an async method for interface compatibility, but uses
        synchronous operations internally.
        """
        try:
            client = self._get_client()

            # Save main job record
            self._save_evaluation_job(client, job_id, results)

            # Save dataset results
            self._save_dataset_results(client, job_id, results)

            # Save predictions in batches
            self._save_predictions_batch(client, job_id, results)

            logger.info(f"Successfully saved results for job {job_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to save results for job {job_id}: {e}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")
            return False

    def _save_evaluation_job(self, client: Client, job_id: str, results: Dict) -> None:
        """Save the main evaluation job record."""
        # Check for existing record
        existing_query = """
        SELECT job_start_time, created_at
        FROM budeval.evaluation_jobs
        WHERE job_id = %(job_id)s
        ORDER BY updated_at DESC
        LIMIT 1
        """

        existing_records = client.query(existing_query, parameters={"job_id": job_id}).result_rows

        if existing_records:
            original_start_time = existing_records[0][0]
            original_created_at = existing_records[0][1]
            logger.debug(f"Found existing record for {job_id}, preserving timestamps")
        else:
            original_start_time = self._parse_datetime(results.get("job_start_time"))
            original_created_at = datetime.now()
            logger.debug(f"No existing record for {job_id}, using new timestamps")

        # Prepare job data (matching actual table schema)
        summary = results.get("summary", {})
        job_end_time = self._parse_datetime(results.get("job_end_time"))

        # Calculate duration if we have both times
        duration_seconds = 0
        if original_start_time and job_end_time:
            duration_seconds = (job_end_time - original_start_time).total_seconds()

        job_data = {
            "job_id": job_id,
            "experiment_id": results.get("experiment_id"),
            "model_name": results.get("model_name", ""),
            "engine": results.get("engine", "opencompass"),
            "status": results.get("status", "succeeded"),
            "job_start_time": original_start_time,
            "job_end_time": job_end_time,
            "job_duration_seconds": float(duration_seconds),
            "overall_accuracy": float(summary.get("overall_accuracy", 0.0)),
            "total_datasets": int(summary.get("total_datasets", 0)),
            "total_examples": int(summary.get("total_examples", 0)),
            "total_correct": int(summary.get("total_correct", 0)),
            "extracted_at": datetime.now(),
            "created_at": original_created_at,
            "updated_at": datetime.now(),
        }

        # Insert the job record
        insert_query = """
        INSERT INTO budeval.evaluation_jobs
        (job_id, experiment_id, model_name, engine, status,
         job_start_time, job_end_time, job_duration_seconds,
         overall_accuracy, total_datasets, total_examples, total_correct,
         extracted_at, created_at, updated_at)
        VALUES (%(job_id)s, %(experiment_id)s, %(model_name)s, %(engine)s, %(status)s,
                %(job_start_time)s, %(job_end_time)s, %(job_duration_seconds)s,
                %(overall_accuracy)s, %(total_datasets)s, %(total_examples)s, %(total_correct)s,
                %(extracted_at)s, %(created_at)s, %(updated_at)s)
        """

        client.query(insert_query, parameters=job_data)
        logger.debug(f"Saved evaluation job record for {job_id}")

    def _save_dataset_results(self, client: Client, job_id: str, results: Dict) -> None:
        """Save dataset-level results."""
        datasets = results.get("datasets", [])
        if not datasets:
            logger.debug(f"No dataset results to save for job {job_id}")
            return

        # Prepare batch data (matching actual table schema)
        dataset_records = []
        for dataset in datasets:
            num_examples = int(dataset.get("num_examples", 0))
            accuracy = float(dataset.get("accuracy", 0.0))
            correct_examples = int(num_examples * accuracy) if num_examples > 0 else 0

            dataset_records.append(
                {
                    "job_id": job_id,
                    "experiment_id": results.get("experiment_id"),
                    "model_name": results.get("model_name", ""),
                    "dataset_name": dataset.get("dataset_name", ""),
                    "accuracy": accuracy,
                    "total_examples": num_examples,
                    "correct_examples": correct_examples,
                    "evaluated_at": datetime.now(),
                    "metadata": json.dumps(dataset.get("metadata", {})),
                    "created_at": datetime.now(),
                }
            )

        # Insert dataset results
        if dataset_records:
            try:
                # Convert dict records to list-of-lists format for clickhouse-connect
                column_names = list(dataset_records[0].keys())
                data_rows = [[record[col] for col in column_names] for record in dataset_records]

                client.insert("budeval.dataset_results", data_rows, column_names=column_names)
                logger.debug(f"Saved {len(dataset_records)} dataset results for job {job_id}")
            except Exception as e:
                logger.error(f"Failed to save dataset results for job {job_id}: {e}")
                raise

    def _save_predictions_batch(self, client: Client, job_id: str, results: Dict) -> None:
        """Save prediction results in batches."""
        predictions = results.get("predictions", [])
        if not predictions:
            logger.debug(f"No predictions to save for job {job_id}")
            return

        # Process predictions in batches
        total_predictions = len(predictions)
        for i in range(0, total_predictions, self.batch_size):
            batch = predictions[i : i + self.batch_size]

            prediction_records = []
            for pred in batch:
                prediction_records.append(
                    {
                        "job_id": job_id,
                        "experiment_id": results.get("experiment_id"),
                        "model_name": results.get("model_name", ""),
                        "dataset_name": pred.get("dataset_name", ""),
                        "example_id": str(pred.get("example_id", "")),
                        "prediction_text": pred.get("prediction", ""),
                        "origin_prompt": pred.get("question", ""),
                        "model_answer": pred.get("prediction", ""),
                        "correct_answer": pred.get("ground_truth", ""),
                        "is_correct": bool(pred.get("is_correct", False)),
                        "evaluated_at": datetime.now(),
                        "created_at": datetime.now(),
                    }
                )

            # Insert batch
            if prediction_records:
                try:
                    # Convert dict records to list-of-lists format for clickhouse-connect
                    column_names = list(prediction_records[0].keys())
                    data_rows = [[record[col] for col in column_names] for record in prediction_records]

                    client.insert("budeval.predictions", data_rows, column_names=column_names)
                    logger.debug(
                        f"Saved batch {i // self.batch_size + 1} "
                        f"({len(prediction_records)} predictions) for job {job_id}"
                    )
                except Exception as e:
                    logger.error(f"Failed to save predictions batch for job {job_id}: {e}")
                    raise

        logger.info(f"Saved {total_predictions} predictions for job {job_id}")

    async def get_results(self, job_id: str) -> Optional[Dict]:
        """Get evaluation results from ClickHouse."""
        try:
            client = self._get_client()

            # Get job record
            job_query = """
            SELECT * FROM budeval.evaluation_jobs
            WHERE job_id = %(job_id)s
            ORDER BY updated_at DESC
            LIMIT 1
            """

            job_results = client.query(job_query, parameters={"job_id": job_id})
            if not job_results.result_rows:
                return None

            # Convert to dict (simplified for brevity)
            job_record = job_results.result_rows[0]
            column_names = job_results.column_names

            result = {column_names[i]: job_record[i] for i in range(len(column_names))}

            # Parse JSON fields
            for json_field in ["config", "summary", "metadata"]:
                if json_field in result and result[json_field]:
                    with contextlib.suppress(Exception):
                        result[json_field] = json.loads(result[json_field])

            # Get dataset results
            dataset_query = """
            SELECT * FROM budeval.dataset_results
            WHERE job_id = %(job_id)s
            ORDER BY dataset_name
            """

            dataset_results = client.query(dataset_query, parameters={"job_id": job_id})
            result["datasets"] = [
                {dataset_results.column_names[i]: row[i] for i in range(len(dataset_results.column_names))}
                for row in dataset_results.result_rows
            ]

            return result

        except Exception as e:
            logger.error(f"Failed to get results for job {job_id}: {e}")
            return None

    async def list_results(self) -> List[str]:
        """List all available job IDs."""
        try:
            client = self._get_client()

            query = """
            SELECT DISTINCT job_id
            FROM budeval.evaluation_jobs
            ORDER BY created_at DESC
            """

            results = client.query(query)
            return [row[0] for row in results.result_rows]

        except Exception as e:
            logger.error(f"Failed to list results: {e}")
            return []

    async def exists(self, job_id: str) -> bool:
        """Check if results exist for a job."""
        try:
            client = self._get_client()

            query = """
            SELECT COUNT(*) FROM budeval.evaluation_jobs
            WHERE job_id = %(job_id)s
            """

            result = client.query(query, parameters={"job_id": job_id})
            return result.result_rows[0][0] > 0

        except Exception as e:
            logger.error(f"Failed to check existence for job {job_id}: {e}")
            return False

    async def delete_results(self, job_id: str) -> bool:
        """Delete results for a specific job."""
        try:
            client = self._get_client()

            # Delete in order due to foreign key constraints
            tables = ["predictions", "dataset_results", "evaluation_jobs"]

            for table in tables:
                delete_query = f"DELETE FROM budeval.{table} WHERE job_id = %(job_id)s"
                client.query(delete_query, parameters={"job_id": job_id})
                logger.debug(f"Deleted records from {table} for job {job_id}")

            logger.info(f"Successfully deleted all results for job {job_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete results for job {job_id}: {e}")
            return False

    async def health_check(self) -> bool:
        """Check if ClickHouse is accessible."""
        try:
            client = self._get_client()
            client.query("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"ClickHouse health check failed: {e}")
            return False

    def _parse_datetime(self, dt_value: Any) -> Optional[datetime]:
        """Parse datetime from various formats."""
        if dt_value is None:
            return None
        if isinstance(dt_value, datetime):
            return dt_value
        if isinstance(dt_value, str):
            try:
                # Try ISO format first
                return datetime.fromisoformat(dt_value.replace("Z", "+00:00"))
            except ValueError:
                try:
                    # Try other common formats
                    from dateutil import parser

                    return parser.parse(dt_value)
                except (ValueError, ImportError):
                    pass
        return None
