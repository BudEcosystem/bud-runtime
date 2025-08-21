"""Filesystem storage adapter implementation."""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from budeval.commons.logging import logging

from .base import StorageAdapter


logger = logging.getLogger(__name__)


class FilesystemStorage(StorageAdapter):
    """Filesystem-based storage adapter for evaluation results.

    Stores results as JSON files in a local directory structure.
    Used primarily for testing and development.
    """

    def __init__(self, base_path: str = "/tmp/eval_results"):
        """Initialize filesystem storage.

        Args:
            base_path: Base directory path to store results
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Initialized filesystem storage at {self.base_path}")

    def _get_job_path(self, job_id: str) -> Path:
        """Get the directory path for a job's results.

        Args:
            job_id: Unique identifier for the evaluation job

        Returns:
            Path object for the job's directory
        """
        return self.base_path / job_id

    def _get_results_file(self, job_id: str) -> Path:
        """Get the path to the results JSON file.

        Args:
            job_id: Unique identifier for the evaluation job

        Returns:
            Path object for the results file
        """
        return self._get_job_path(job_id) / "results.json"

    def _get_metadata_file(self, job_id: str) -> Path:
        """Get the path to the metadata JSON file.

        Args:
            job_id: Unique identifier for the evaluation job

        Returns:
            Path object for the metadata file
        """
        return self._get_job_path(job_id) / "metadata.json"

    async def save_results(self, job_id: str, results: Dict) -> bool:
        """Save evaluation results to filesystem.

        Args:
            job_id: Unique identifier for the evaluation job
            results: Processed evaluation results dictionary

        Returns:
            True if saved successfully, False otherwise
        """
        try:
            job_path = self._get_job_path(job_id)
            job_path.mkdir(parents=True, exist_ok=True)

            # Save results
            results_file = self._get_results_file(job_id)
            with open(results_file, "w") as f:
                json.dump(results, f, indent=2, default=str)

            # Save metadata
            metadata = {
                "job_id": job_id,
                "stored_at": datetime.utcnow().isoformat(),
                "storage_type": "filesystem",
                "storage_path": str(results_file),
            }
            metadata_file = self._get_metadata_file(job_id)
            with open(metadata_file, "w") as f:
                json.dump(metadata, f, indent=2)

            logger.info(f"Saved results for job {job_id} to {results_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to save results for job {job_id}: {e}")
            return False

    async def get_results(self, job_id: str) -> Optional[Dict]:
        """Retrieve evaluation results from filesystem.

        Args:
            job_id: Unique identifier for the evaluation job

        Returns:
            Dictionary containing evaluation results or None if not found
        """
        try:
            results_file = self._get_results_file(job_id)

            if not results_file.exists():
                logger.warning(f"Results file not found for job {job_id}: {results_file}")
                return None

            with open(results_file, "r") as f:
                results = json.load(f)

            logger.debug(f"Retrieved results for job {job_id}")
            return results

        except Exception as e:
            logger.error(f"Failed to retrieve results for job {job_id}: {e}")
            return None

    async def delete_results(self, job_id: str) -> bool:
        """Delete evaluation results from filesystem.

        Args:
            job_id: Unique identifier for the evaluation job

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            job_path = self._get_job_path(job_id)

            if not job_path.exists():
                logger.warning(f"Job directory not found for deletion: {job_path}")
                return False

            # Remove all files in the job directory
            for file_path in job_path.iterdir():
                if file_path.is_file():
                    file_path.unlink()

            # Remove the directory
            job_path.rmdir()

            logger.info(f"Deleted results for job {job_id}")
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
            job_ids = []

            if not self.base_path.exists():
                return job_ids

            for item in self.base_path.iterdir():
                if item.is_dir():
                    results_file = item / "results.json"
                    if results_file.exists():
                        job_ids.append(item.name)

            logger.debug(f"Found {len(job_ids)} job results in storage")
            return job_ids

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
        results_file = self._get_results_file(job_id)
        return results_file.exists()

    async def get_metadata(self, job_id: str) -> Optional[Dict]:
        """Get metadata for a job's results.

        Args:
            job_id: Unique identifier for the evaluation job

        Returns:
            Dictionary containing metadata or None if not found
        """
        try:
            metadata_file = self._get_metadata_file(job_id)

            if not metadata_file.exists():
                return None

            with open(metadata_file, "r") as f:
                metadata = json.load(f)

            return metadata

        except Exception as e:
            logger.error(f"Failed to retrieve metadata for job {job_id}: {e}")
            return None
