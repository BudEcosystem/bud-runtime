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
from .evals.evaluations_submit import submit_evaluation  # noqa: F401 - imported for side effects
from .evals.routes import evals_routes, evaluations_routes


# from .seeders import seeders
logger = logging.get_logger(__name__)


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
app.include_router(evaluations_routes)
