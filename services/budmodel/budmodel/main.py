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
from .leaderboard.workflows import LeaderboardCronWorkflows
from .model_info.routes import model_info_router


logger = logging.get_logger(__name__)


async def execute_leaderboard_cron_workflow() -> None:
    """Execute the leaderboard cron workflow.

    This function checks if the Dapr workflow is running and executes the leaderboard cron workflow.
    """
    POLLING_INTERVAL = 5
    attempts = 0

    while True:
        await asyncio.sleep(POLLING_INTERVAL)
        if DaprWorkflow().is_running:
            logger.info("Dapr workflow runtime is ready. Initializing leaderboard cron workflow.")
            break
        else:
            attempts += 1
            logger.info("Waiting for Dapr workflow runtime to start... Attempt: %s", attempts)

    response = await LeaderboardCronWorkflows().__call__()
    logger.debug("Leaderboard cron workflow response: %s", response)


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
    leaderboard_cron_task = asyncio.create_task(execute_leaderboard_cron_workflow())

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
        leaderboard_cron_task.cancel()
    except asyncio.CancelledError:
        logger.exception("Failed to cleanup config & store sync.")

    DaprWorkflow().shutdown_workflow_runtime()


app = configure_app(app_settings, secrets_settings, dapr_lifespan)

app.include_router(model_info_router)
app.include_router(leaderboard_router)
