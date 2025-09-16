"""Simplified storage factory - only ClickHouse support."""

import logging
import threading
from typing import TYPE_CHECKING, Optional

from budeval.commons.config import app_settings
from budeval.evals.storage.base import StorageAdapter


if TYPE_CHECKING:  # pragma: no cover - import for type checking only
    from budeval.evals.storage.clickhouse import ClickHouseStorage


logger = logging.getLogger(__name__)

# Per-thread ClickHouse storage instances to avoid cross-event-loop issues
_clickhouse_storage_by_thread: dict[int, "ClickHouseStorage"] = {}


def get_storage_adapter(backend: Optional[str] = None) -> StorageAdapter:
    """Create and return a ClickHouse storage adapter.

    Args:
        backend: Ignored - only ClickHouse is supported

    Returns:
        ClickHouseStorage instance

    Raises:
        ImportError: If ClickHouse dependencies are not available
    """
    try:
        from budeval.evals.storage.clickhouse import ClickHouseStorage
    except ImportError as e:
        raise ImportError(
            "ClickHouse dependencies not available. Install with: pip install asynch clickhouse-connect"
        ) from e

    # Per-thread instance to avoid cross-event-loop future issues
    thread_id = threading.get_ident()

    if thread_id not in _clickhouse_storage_by_thread:
        _clickhouse_storage_by_thread[thread_id] = ClickHouseStorage()

    return _clickhouse_storage_by_thread[thread_id]


async def initialize_storage(storage: StorageAdapter) -> None:
    """Initialize storage adapter if it has an initialize method.

    Args:
        storage: Storage adapter to initialize
    """
    if hasattr(storage, "initialize"):
        try:
            await storage.initialize()
            logger.info(f"Storage adapter {storage.__class__.__name__} initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize storage adapter: {e}")
            raise


async def close_storage(storage: StorageAdapter) -> None:
    """Close storage adapter if it has a close method.

    Args:
        storage: Storage adapter to close
    """
    if hasattr(storage, "close"):
        try:
            await storage.close()
            logger.info(f"Storage adapter {storage.__class__.__name__} closed successfully")
        except Exception as e:
            logger.error(f"Failed to close storage adapter: {e}")


def get_storage_info() -> dict:
    """Get information about the configured storage backend.

    Returns:
        Dictionary with storage configuration details
    """
    return {
        "backend": "clickhouse",
        "host": app_settings.clickhouse_host,
        "port": app_settings.clickhouse_port,
        "database": app_settings.clickhouse_database,
        "batch_size": app_settings.clickhouse_batch_size,
    }


async def health_check_storage(storage: StorageAdapter) -> dict:
    """Perform health check on storage adapter.

    Args:
        storage: Storage adapter to check

    Returns:
        Dictionary with health check results
    """
    result = {"backend": storage.__class__.__name__, "healthy": False, "error": None}

    try:
        if hasattr(storage, "health_check"):
            result["healthy"] = await storage.health_check()
        else:
            # For adapters without health_check, try a basic operation
            job_ids = await storage.list_results()
            result["healthy"] = True
            result["job_count"] = len(job_ids)

    except Exception as e:
        result["error"] = str(e)
        logger.error(f"Storage health check failed: {e}")

    return result
