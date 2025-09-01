#  -----------------------------------------------------------------------------
#  Copyright (c) 2024 Bud Ecosystem Inc.
#  #
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#  #
#      http://www.apache.org/licenses/LICENSE-2.0
#  #
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#  -----------------------------------------------------------------------------

"""The main entry point for the application, initializing the FastAPI app and setting up the application's lifespan management, including configuration and secret syncs."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from budmicroframe.commons import logging
from budmicroframe.main import configure_app, schedule_secrets_and_config_sync
from budmicroframe.shared.dapr_workflow import DaprWorkflow
from budmicroframe.shared.psql_service import Database
from fastapi import FastAPI

from .commons.config import app_settings, secrets_settings
from .commons.exceptions import SeederException
from .evals.eval_sync.routes import router as eval_sync_router
from .evals.routes import evals_routes


# from .seeders import seeders
logger = logging.get_logger(__name__)


async def execute_initial_eval_sync() -> None:
    """Execute initial evaluation data sync on startup.

    This function runs the evaluation data sync once when the application starts,
    similar to how budapp handles it.
    """
    if not app_settings.eval_sync_enabled:
        logger.info("Evaluation data sync is disabled, skipping initial sync")
        return

    try:
        from .evals.eval_sync.sync_service import get_sync_service

        logger.info("Running initial evaluation data sync")
        sync_service = get_sync_service()

        # Fetch manifest
        manifest = await sync_service.fetch_manifest(app_settings.eval_manifest_url)

        # Get current version
        with sync_service.db.get_session() as db:
            current_version = sync_service.get_current_version(db)

        logger.info(
            f"Initial sync check - Current version: {current_version}, Latest version: {manifest.version_info.current_version}"
        )

        # Only sync if versions differ (not forcing on startup)
        if current_version != manifest.version_info.current_version:
            logger.info("Version mismatch detected, syncing datasets")
            sync_results = await sync_service.sync_datasets(manifest, current_version, force_sync=False)

            # Record sync results
            with sync_service.db.get_session() as db:
                sync_service.record_sync_results(
                    db,
                    manifest.version_info.current_version,
                    "completed",
                    {
                        "synced_datasets": sync_results["synced_datasets"],
                        "failed_datasets": sync_results["failed_datasets"],
                        "total_datasets": sync_results.get("total_datasets", 0),
                        "source": "cloud" if not app_settings.eval_sync_local_mode else "local",
                        "trigger": "startup",
                    },
                )
            logger.info(f"Initial sync completed: {len(sync_results['synced_datasets'])} datasets synced")
        else:
            logger.info("Datasets are up to date, no sync needed")

    except Exception as e:
        logger.error(f"Failed to run initial evaluation data sync: {e}")


async def schedule_eval_data_sync() -> None:
    """Schedule hourly evaluation data synchronization from cloud repository.

    This function runs evaluation data sync periodically based on the configured interval,
    similar to budapp's hourly sync.
    """
    if not app_settings.eval_sync_enabled:
        logger.info("Evaluation data sync is disabled, skipping scheduler")
        return

    # Wait a bit for services to be ready
    await asyncio.sleep(10)

    while True:
        try:
            from .evals.eval_sync.sync_service import get_sync_service

            logger.info("Running scheduled evaluation data sync")
            sync_service = get_sync_service()

            # Fetch manifest
            manifest = await sync_service.fetch_manifest(app_settings.eval_manifest_url)

            # Get current version
            with sync_service.db.get_session() as db:
                current_version = sync_service.get_current_version(db)

            # Check if sync is needed
            if current_version != manifest.version_info.current_version:
                logger.info(
                    f"Scheduled sync - version update detected: {current_version} -> {manifest.version_info.current_version}"
                )
                sync_results = await sync_service.sync_datasets(manifest, current_version, force_sync=False)

                # Record sync results
                with sync_service.db.get_session() as db:
                    sync_service.record_sync_results(
                        db,
                        manifest.version_info.current_version,
                        "completed",
                        {
                            "synced_datasets": sync_results["synced_datasets"],
                            "failed_datasets": sync_results["failed_datasets"],
                            "total_datasets": sync_results.get("total_datasets", 0),
                            "source": "cloud" if not app_settings.eval_sync_local_mode else "local",
                            "trigger": "scheduled",
                        },
                    )
                logger.info(f"Scheduled sync completed: {len(sync_results['synced_datasets'])} datasets synced")
            else:
                logger.debug(f"Scheduled sync check - datasets are up to date (version: {current_version})")

        except Exception as e:
            logger.error(f"Failed to run scheduled eval data sync: {e}")

        # Sleep for the configured interval (default 1 hour)
        await asyncio.sleep(app_settings.eval_sync_interval_seconds)


# Start Event
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage the lifespan of the FastAPI application, including scheduling periodic syncs of configurations and secrets.

    This context manager starts a background task that periodically syncs configurations and secrets from
    their respective stores if they are configured. The sync intervals are randomized between 90% and 100%
    of the maximum sync interval specified in the application settings. The task is canceled upon exiting the
    context.

    Args:
        app (FastAPI): The FastAPI application instance.

    Yields:
        None: Yields control back to the context where the lifespan management is performed.
    """
    task = asyncio.create_task(schedule_secrets_and_config_sync())
    eval_sync_task = None

    try:
        logger.info("Starting background initialization on startup")

        # Initialize database connection
        logger.info("Initializing database connection")
        db = Database()
        db.connect()
        logger.info("Database connection initialized successfully")

        # Initialize ClickHouse storage if configured
        logger.info("Initializing storage backend")
        from .evals.storage.factory import get_storage_adapter, initialize_storage

        try:
            storage = get_storage_adapter()
            await initialize_storage(storage)
            logger.info("Storage backend initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize storage backend: {e}")
            # Don't fail startup if storage initialization fails

        # Check volume for dataset storage exists
        # try:
        #     volume_init = VolumeInitializer()
        #     logger.info("Checking for dataset volume existence")
        #     await volume_init.ensure_eval_datasets_volume()
        #     logger.info("Dataset volume check completed successfully")
        # except DatasetVolumeNotFoundError as e:
        #     logger.error(f"Dataset volume check failed: {e}")
        #     # Re-raise to fail startup if volume doesn't exist
        #     raise
        # except Exception as e:
        #     logger.warning(f"Could not check dataset volume (may be running outside Kubernetes): {e}")
        # Don't fail if we can't check (e.g., local dev without k8s)

        # Execute initial evaluation data sync
        # if app_settings.eval_sync_enabled:
        #     logger.info("Eval sync is enabled - running initial sync and starting scheduler")
        #     _ = asyncio.create_task(execute_initial_eval_sync())

        #     # Start the hourly eval data sync scheduler
        #     eval_sync_task = asyncio.create_task(schedule_eval_data_sync())
        # else:
        #     logger.info("Eval sync is disabled")
        #     eval_sync_task = None

        logger.info("Background initialization tasks started successfully")
        logger.info("Prepared dataset successfully.")
    except SeederException as e:
        logger.error("Failed to prepare dataset. Error: %s", e.message)
    except Exception as e:
        logger.error(f"Failed to prepare dataset. Error: {e}")

    yield

    try:
        logger.info("Shutting down application")

        # Cancel all background tasks
        task.cancel()

        if eval_sync_task:
            eval_sync_task.cancel()

        # Wait for tasks to complete cancellation
        await asyncio.gather(task, eval_sync_task, return_exceptions=True) if eval_sync_task else await asyncio.gather(
            task, return_exceptions=True
        )

    except asyncio.CancelledError:
        logger.exception("Failed to cleanup config & store sync.")

    DaprWorkflow().shutdown_workflow_runtime()


app = configure_app(app_settings, secrets_settings, lifespan=lifespan)  # type: ignore[arg-type] # noqa: F841

app.include_router(evals_routes)
app.include_router(eval_sync_router)
