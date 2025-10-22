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
from .evals.clickhouse_service import clickhouse_service
from .evals.routes import evals_routes


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
    asyncio.create_task(schedule_secrets_and_config_sync())

    try:
        logger.info("Starting background initialization on startup")

        # Initialize database connection
        logger.info("Initializing database connection")
        db = Database()
        db.connect()
        logger.info("Database connection initialized successfully")

        if app_settings.storage_backend == "clickhouse":
            logger.info("Initializing ClickHouse connection")
            try:
                # Initialize synchronous connection
                clickhouse_service.connect()

                # Optionally, also initialize async connection
                await clickhouse_service.connect_async()

                logger.info("ClickHouse connection initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize ClickHouse connection: {e}")

    except SeederException as e:
        logger.error("Failed to prepare dataset. Error: %s", e.message)
    except Exception as e:
        logger.error(f"Failed to prepare dataset. Error: {e}")

    yield
    DaprWorkflow().shutdown_workflow_runtime()

    # Cleanup ClickHouse
    if app_settings.storage_backend == "clickhouse":
        logger.info("Closing ClickHouse connections")
        clickhouse_service.disconnect()
        await clickhouse_service.disconnect_async()


app = configure_app(app_settings, secrets_settings, lifespan=lifespan)  # type: ignore[arg-type] # noqa: F841

app.include_router(evals_routes)
