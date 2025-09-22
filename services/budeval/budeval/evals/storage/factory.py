"""Storage factory for creating storage adapters based on configuration.

This module provides a simple factory pattern for storage adapters.
The synchronous ClickHouse implementation avoids event loop conflicts
that can occur in Dapr workflows.
"""

from typing import Optional

from budeval.commons.config import app_settings
from budeval.commons.logging import logging

from .base import StorageAdapter
from .filesystem import FilesystemStorage


logger = logging.getLogger(__name__)


def get_storage_adapter(backend: Optional[str] = None) -> StorageAdapter:
    """Create and return a storage adapter based on configuration.

    Args:
        backend: Storage backend type ('filesystem' or 'clickhouse').
                If None, uses the configured storage_backend setting.

    Returns:
        StorageAdapter instance

    Raises:
        ValueError: If the backend type is not supported
        ImportError: If ClickHouse dependencies are not available
    """
    # Use provided backend or fall back to configuration
    storage_backend = backend or app_settings.storage_backend

    logger.info(f"Creating storage adapter for backend: {storage_backend}")

    if storage_backend == "filesystem":
        return FilesystemStorage()

    elif storage_backend == "clickhouse":
        try:
            from .clickhouse_sync import ClickHouseSyncStorage

            storage_instance = ClickHouseSyncStorage()
            logger.info("ClickHouse sync storage adapter created")
            return storage_instance

        except ImportError as e:
            logger.error(f"ClickHouse dependencies not available: {e}")
            raise ImportError(
                "ClickHouse storage requires 'clickhouse-connect' package. "
                "Install with: pip install clickhouse-connect"
            ) from e

    else:
        supported_backends = ["filesystem", "clickhouse"]
        raise ValueError(f"Unsupported storage backend: {storage_backend}. Supported backends: {supported_backends}")


async def initialize_storage(storage: StorageAdapter) -> None:
    """Initialize storage adapter if it has an initialize method.

    Args:
        storage: Storage adapter to initialize
    """
    if hasattr(storage, "initialize"):
        logger.info(f"Initializing {storage.__class__.__name__}")
        await storage.initialize()
        logger.info(f"{storage.__class__.__name__} initialized successfully")


async def close_storage(storage: StorageAdapter) -> None:
    """Close storage adapter if it has a close method.

    Args:
        storage: Storage adapter to close
    """
    if hasattr(storage, "close"):
        logger.info(f"Closing {storage.__class__.__name__}")
        # Handle both sync and async close methods
        if hasattr(storage.close, "__await__"):
            await storage.close()
        else:
            storage.close()
        logger.info(f"{storage.__class__.__name__} closed successfully")


def get_storage_info() -> dict:
    """Get information about the configured storage backend.

    Returns:
        Dictionary with storage configuration details
    """
    backend = app_settings.storage_backend

    info = {
        "backend": backend,
        "available_backends": ["filesystem", "clickhouse"],
    }

    if backend == "filesystem":
        storage = FilesystemStorage()
        info.update(
            {
                "base_path": str(storage.base_path),
                "description": "Local filesystem storage with JSON files",
            }
        )

    elif backend == "clickhouse":
        info.update(
            {
                "host": app_settings.clickhouse_host,
                "port": app_settings.clickhouse_port,
                "database": app_settings.clickhouse_database,
                "user": app_settings.clickhouse_user,
                "batch_size": app_settings.clickhouse_batch_size,
                "async_insert": app_settings.clickhouse_async_insert,
                "description": "ClickHouse database storage with synchronous client",
            }
        )

    return info


async def health_check_storage(storage: StorageAdapter) -> dict:
    """Perform health check on storage adapter.

    Args:
        storage: Storage adapter to check

    Returns:
        Dictionary with health check results
    """
    result = {
        "backend": storage.__class__.__name__,
        "healthy": False,
        "error": None,
    }

    try:
        if hasattr(storage, "health_check"):
            result["healthy"] = await storage.health_check()
        else:
            # For adapters without health_check, try a basic operation
            await storage.list_results()
            result["healthy"] = True

    except Exception as e:
        result["error"] = str(e)
        logger.error(f"Storage health check failed: {e}")

    return result


async def migrate_data(
    source_backend: str,
    target_backend: str,
    job_ids: Optional[list] = None,
    verify: bool = True,
    cleanup_source: bool = False,
) -> dict:
    """Migrate data between storage backends.

    Args:
        source_backend: Source storage backend type
        target_backend: Target storage backend type
        job_ids: Optional list of specific job IDs to migrate.
                If None, migrates all available results.
        verify: Whether to verify migration by comparing data
        cleanup_source: Whether to delete from source after successful migration

    Returns:
        Dictionary with migration results and statistics
    """
    logger.info(f"Starting migration: {source_backend} -> {target_backend}")

    # Validate backends
    if source_backend == target_backend:
        raise ValueError("Source and target backends cannot be the same")

    # Initialize migration statistics
    stats = {
        "total_jobs": 0,
        "migrated_jobs": 0,
        "failed_jobs": 0,
        "verified_jobs": 0,
        "cleaned_jobs": 0,
        "errors": [],
    }

    try:
        # Get storage adapters
        source_storage = get_storage_adapter(source_backend)
        target_storage = get_storage_adapter(target_backend)

        # Initialize storage adapters
        await initialize_storage(source_storage)
        await initialize_storage(target_storage)

        # Get job IDs to migrate
        if job_ids is None:
            job_ids = await source_storage.list_results()
            logger.info(f"Found {len(job_ids)} jobs to migrate")
        else:
            logger.info(f"Migrating {len(job_ids)} specific jobs")

        stats["total_jobs"] = len(job_ids)

        # Migrate each job
        for job_id in job_ids:
            try:
                logger.info(f"Migrating job: {job_id}")

                # Get results from source
                results = await source_storage.get_results(job_id)
                if not results:
                    logger.warning(f"No results found for job {job_id}")
                    continue

                # Check if already exists in target
                if await target_storage.exists(job_id):
                    logger.info(f"Job {job_id} already exists in target, skipping")
                    stats["migrated_jobs"] += 1
                    continue

                # Save to target
                success = await target_storage.save_results(job_id, results)
                if not success:
                    raise Exception("Failed to save results to target storage")

                stats["migrated_jobs"] += 1
                logger.info(f"Successfully migrated job: {job_id}")

                # Verify migration if requested
                if verify:
                    target_results = await target_storage.get_results(job_id)
                    if target_results and _verify_migration(results, target_results):
                        stats["verified_jobs"] += 1
                        logger.debug(f"Verified migration for job: {job_id}")
                    else:
                        raise Exception("Migration verification failed")

                # Cleanup source if requested and migration verified
                if cleanup_source and (not verify or target_results):
                    cleanup_success = await source_storage.delete_results(job_id)
                    if cleanup_success:
                        stats["cleaned_jobs"] += 1
                        logger.debug(f"Cleaned up source for job: {job_id}")

            except Exception as e:
                error_msg = f"Failed to migrate job {job_id}: {str(e)}"
                logger.error(error_msg)
                stats["failed_jobs"] += 1
                stats["errors"].append(error_msg)

        # Close storage adapters
        await close_storage(source_storage)
        await close_storage(target_storage)

        # Log summary
        logger.info(f"Migration completed: {stats['migrated_jobs']}/{stats['total_jobs']} jobs migrated")
        if stats["failed_jobs"] > 0:
            logger.warning(f"{stats['failed_jobs']} jobs failed to migrate")

        return stats

    except Exception as e:
        error_msg = f"Migration failed: {str(e)}"
        logger.error(error_msg)
        stats["errors"].append(error_msg)
        return stats


def _verify_migration(source_data: dict, target_data: dict) -> bool:
    """Verify that migration was successful by comparing key metrics.

    Args:
        source_data: Original data from source storage
        target_data: Retrieved data from target storage

    Returns:
        True if verification passes, False otherwise
    """
    try:
        # Compare job metadata
        source_summary = source_data.get("summary", {})
        target_summary = target_data.get("summary", {})

        if source_summary.get("overall_accuracy") != target_summary.get("overall_accuracy"):
            return False

        if source_summary.get("total_datasets") != target_summary.get("total_datasets"):
            return False

        if source_summary.get("total_examples") != target_summary.get("total_examples"):
            return False

        # Compare dataset counts
        source_datasets = len(source_data.get("datasets", []))
        target_datasets = len(target_data.get("datasets", []))

        if source_datasets != target_datasets:
            return False

        logger.debug("Migration verification passed")
        return True

    except Exception as e:
        logger.error(f"Migration verification error: {e}")
        return False
