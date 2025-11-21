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
from contextlib import asynccontextmanager
from typing import AsyncIterator

from budmicroframe.commons import logging
from budmicroframe.main import configure_app, schedule_secrets_and_config_sync
from budmicroframe.shared.dapr_workflow import DaprWorkflow
from fastapi import FastAPI

from seeders.seeder import seeders

from .commons.config import app_settings, secrets_settings
from .leaderboard.routes import leaderboard_router
from .model_info.routes import model_info_router
from .shared.aria2_daemon import ensure_aria2_daemon_running, get_aria2_daemon_manager


logger = logging.get_logger(__name__)


@asynccontextmanager
async def dapr_lifespan(app: FastAPI) -> AsyncIterator[None]:
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

    # Start aria2 daemon for I/O-aware downloads
    try:
        if ensure_aria2_daemon_running():
            logger.info("Aria2 daemon started successfully for I/O-aware downloads")
        else:
            logger.warning("Failed to start aria2 daemon - downloads may use standard method")
    except Exception as e:
        logger.error(f"Error starting aria2 daemon: {e}")

    if app_settings.enable_seeder:
        logger.info("Seeding pre-defined data...")
        for seeder_name, seeder in seeders.items():
            try:
                await seeder().seed()
                logger.info(f"Seeded {seeder_name} seeder successfully.")
            except Exception as e:
                logger.error(f"Failed to seed {seeder_name}. Error: {e}")

    yield

    try:
        task.cancel()

        # Stop aria2 daemon on shutdown
        try:
            daemon_manager = get_aria2_daemon_manager()
            if daemon_manager.stop_daemon():
                logger.info("Aria2 daemon stopped successfully")
        except Exception as e:
            logger.warning(f"Failed to stop aria2 daemon: {e}")

    except asyncio.CancelledError:
        logger.exception("Failed to cleanup config & store sync.")

    DaprWorkflow().shutdown_workflow_runtime()


app = configure_app(app_settings, secrets_settings, dapr_lifespan)

app.include_router(model_info_router)
app.include_router(leaderboard_router)
