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

from .commons.config import app_settings, secrets_settings
from .prompt.routes import prompt_router
from .responses.routes import responses_router
from .shared.otel import otel_manager


logger = logging.get_logger(__name__)


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
    # Initialize OpenTelemetry for Pydantic AI instrumentation
    otel_manager.configure()

    task = asyncio.create_task(schedule_secrets_and_config_sync())

    yield

    try:
        task.cancel()
    except asyncio.CancelledError:
        logger.exception("Failed to cleanup config & store sync.")

    DaprWorkflow().shutdown_workflow_runtime()

    # Shutdown OpenTelemetry
    otel_manager.shutdown()


app = configure_app(app_settings, secrets_settings, lifespan=lifespan)

# Include routers
app.include_router(prompt_router)
app.include_router(responses_router)
