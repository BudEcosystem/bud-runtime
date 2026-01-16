"""Dapr State Store wrapper for budpipeline.

Provides async operations for saving, retrieving, and deleting state
using the Dapr state store API.
"""

import logging
from typing import Any

import httpx

from budpipeline.commons.config import settings

logger = logging.getLogger(__name__)


class DaprStateStoreError(Exception):
    """Exception raised when state store operations fail."""

    def __init__(self, message: str, status_code: int | None = None):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class DaprStateStore:
    """Wrapper for Dapr state store operations.

    Uses the Dapr state management API to persist and retrieve state.
    Reference: https://docs.dapr.io/reference/api/state_api/
    """

    def __init__(self, store_name: str | None = None):
        """Initialize the state store client.

        Args:
            store_name: Name of the Dapr state store component.
                       Defaults to settings.state_store_name.
        """
        self.store_name = store_name or settings.state_store_name
        self.base_url = f"{settings.dapr_http_endpoint}/v1.0/state/{self.store_name}"
        self.headers: dict[str, str] = {"Content-Type": "application/json"}
        if settings.dapr_api_token:
            self.headers["dapr-api-token"] = settings.dapr_api_token

    async def save(
        self,
        key: str,
        value: dict[str, Any],
        etag: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> None:
        """Save state to the state store.

        Args:
            key: The key to store the value under
            value: The value to store (must be JSON serializable)
            etag: Optional ETag for optimistic concurrency
            metadata: Optional metadata for the state entry

        Raises:
            DaprStateStoreError: If the save operation fails
        """
        state_entry: dict[str, Any] = {
            "key": key,
            "value": value,
        }

        if etag:
            state_entry["etag"] = etag
            state_entry["options"] = {"concurrency": "first-write"}

        if metadata:
            state_entry["metadata"] = metadata

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    self.base_url,
                    json=[state_entry],
                    headers=self.headers,
                )
                response.raise_for_status()
                logger.debug(f"Saved state for key: {key}")
        except httpx.HTTPStatusError as e:
            error_msg = f"Failed to save state for key {key}: HTTP {e.response.status_code}"
            logger.error(error_msg)
            raise DaprStateStoreError(error_msg, e.response.status_code) from e
        except httpx.RequestError as e:
            error_msg = f"Failed to save state for key {key}: {str(e)}"
            logger.error(error_msg)
            raise DaprStateStoreError(error_msg) from e

    async def get(self, key: str) -> dict[str, Any] | None:
        """Get state from the state store.

        Args:
            key: The key to retrieve

        Returns:
            The stored value, or None if the key doesn't exist

        Raises:
            DaprStateStoreError: If the get operation fails
        """
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    f"{self.base_url}/{key}",
                    headers=self.headers,
                )

                if response.status_code == 204:
                    # No content - key doesn't exist
                    return None

                response.raise_for_status()

                # Dapr returns the value directly, not wrapped
                data = response.json()
                logger.debug(f"Retrieved state for key: {key}")
                return data

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            error_msg = f"Failed to get state for key {key}: HTTP {e.response.status_code}"
            logger.error(error_msg)
            raise DaprStateStoreError(error_msg, e.response.status_code) from e
        except httpx.RequestError as e:
            error_msg = f"Failed to get state for key {key}: {str(e)}"
            logger.error(error_msg)
            raise DaprStateStoreError(error_msg) from e

    async def delete(self, key: str) -> bool:
        """Delete state from the state store.

        Args:
            key: The key to delete

        Returns:
            True if the key was deleted, False if it didn't exist

        Raises:
            DaprStateStoreError: If the delete operation fails
        """
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.delete(
                    f"{self.base_url}/{key}",
                    headers=self.headers,
                )

                if response.status_code == 204:
                    logger.debug(f"Deleted state for key: {key}")
                    return True

                if response.status_code == 404:
                    return False

                response.raise_for_status()
                return True

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return False
            error_msg = f"Failed to delete state for key {key}: HTTP {e.response.status_code}"
            logger.error(error_msg)
            raise DaprStateStoreError(error_msg, e.response.status_code) from e
        except httpx.RequestError as e:
            error_msg = f"Failed to delete state for key {key}: {str(e)}"
            logger.error(error_msg)
            raise DaprStateStoreError(error_msg) from e

    async def bulk_get(self, keys: list[str]) -> dict[str, dict[str, Any]]:
        """Get multiple states from the state store in a single call.

        Args:
            keys: List of keys to retrieve

        Returns:
            Dictionary mapping keys to their values (missing keys are omitted)

        Raises:
            DaprStateStoreError: If the bulk get operation fails
        """
        if not keys:
            return {}

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self.base_url}/bulk",
                    json={"keys": keys},
                    headers=self.headers,
                )
                response.raise_for_status()

                # Dapr returns list of {key, data, etag}
                results = response.json()
                return {
                    item["key"]: item["data"] for item in results if item.get("data") is not None
                }

        except httpx.HTTPStatusError as e:
            error_msg = f"Failed to bulk get states: HTTP {e.response.status_code}"
            logger.error(error_msg)
            raise DaprStateStoreError(error_msg, e.response.status_code) from e
        except httpx.RequestError as e:
            error_msg = f"Failed to bulk get states: {str(e)}"
            logger.error(error_msg)
            raise DaprStateStoreError(error_msg) from e

    async def save_bulk(
        self,
        items: list[tuple[str, dict[str, Any]]],
    ) -> None:
        """Save multiple states to the state store in a single call.

        Args:
            items: List of (key, value) tuples to save

        Raises:
            DaprStateStoreError: If the bulk save operation fails
        """
        if not items:
            return

        state_entries = [{"key": key, "value": value} for key, value in items]

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    self.base_url,
                    json=state_entries,
                    headers=self.headers,
                )
                response.raise_for_status()
                logger.debug(f"Bulk saved {len(items)} state entries")

        except httpx.HTTPStatusError as e:
            error_msg = f"Failed to bulk save states: HTTP {e.response.status_code}"
            logger.error(error_msg)
            raise DaprStateStoreError(error_msg, e.response.status_code) from e
        except httpx.RequestError as e:
            error_msg = f"Failed to bulk save states: {str(e)}"
            logger.error(error_msg)
            raise DaprStateStoreError(error_msg) from e

    async def transaction(
        self,
        operations: list[dict[str, Any]],
    ) -> None:
        """Execute a transaction with multiple operations.

        Args:
            operations: List of operations, each with:
                - operation: "upsert" or "delete"
                - request: {"key": "...", "value": {...}} for upsert,
                          {"key": "..."} for delete

        Raises:
            DaprStateStoreError: If the transaction fails
        """
        if not operations:
            return

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self.base_url}/transaction",
                    json={"operations": operations},
                    headers=self.headers,
                )
                response.raise_for_status()
                logger.debug(f"Executed transaction with {len(operations)} operations")

        except httpx.HTTPStatusError as e:
            error_msg = f"Failed to execute transaction: HTTP {e.response.status_code}"
            logger.error(error_msg)
            raise DaprStateStoreError(error_msg, e.response.status_code) from e
        except httpx.RequestError as e:
            error_msg = f"Failed to execute transaction: {str(e)}"
            logger.error(error_msg)
            raise DaprStateStoreError(error_msg) from e


# Global instance for convenience
state_store = DaprStateStore()
