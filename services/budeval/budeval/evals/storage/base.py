"""Base storage adapter interface."""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class StorageAdapter(ABC):
    """Abstract base class for storage adapters.

    Provides a common interface for storing and retrieving evaluation results
    across different storage backends.
    """

    @abstractmethod
    async def save_results(self, job_id: str, results: Dict) -> bool:
        """Save evaluation results for a job.

        Args:
            job_id: Unique identifier for the evaluation job
            results: Processed evaluation results dictionary

        Returns:
            True if saved successfully, False otherwise
        """

    @abstractmethod
    async def get_results(self, job_id: str) -> Optional[Dict]:
        """Retrieve evaluation results for a job.

        Args:
            job_id: Unique identifier for the evaluation job

        Returns:
            Dictionary containing evaluation results or None if not found
        """

    @abstractmethod
    async def delete_results(self, job_id: str) -> bool:
        """Delete evaluation results for a job.

        Args:
            job_id: Unique identifier for the evaluation job

        Returns:
            True if deleted successfully, False otherwise
        """

    @abstractmethod
    async def list_results(self) -> List[str]:
        """List all available job IDs with results.

        Returns:
            List of job IDs that have stored results
        """

    @abstractmethod
    async def exists(self, job_id: str) -> bool:
        """Check if results exist for a job.

        Args:
            job_id: Unique identifier for the evaluation job

        Returns:
            True if results exist, False otherwise
        """
