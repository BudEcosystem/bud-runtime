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
from typing import Any, AsyncIterator

from fastapi import APIRouter, FastAPI
from fastapi.openapi.utils import get_openapi

from .commons import logging
from .commons.config import app_settings
from .commons.constants import Environment
from .core import sync_routes
from .core.meta_routes import meta_router
from .core.notify_routes import notify_router


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

    async def schedule_secrets_and_config_sync() -> None:
        from random import randint

        await asyncio.sleep(3)
        while True:
            await sync_routes.sync_configurations()
            await sync_routes.sync_secrets()

            await asyncio.sleep(
                randint(
                    int(app_settings.max_sync_interval * 0.9),
                    app_settings.max_sync_interval,
                )
            )

    if app_settings.configstore_name or app_settings.secretstore_name:
        task = asyncio.create_task(schedule_secrets_and_config_sync())
    else:
        task = None

    yield

    if task is not None:
        try:
            task.cancel()
        except asyncio.CancelledError:
            logger.exception("Failed to cleanup config & store sync.")


app = FastAPI(
    title=app_settings.name,
    description=app_settings.description,
    version=app_settings.version,
    root_path=app_settings.api_root,
    lifespan=lifespan,
    openapi_url=None if app_settings.env == Environment.PRODUCTION else "/openapi.json",
)

internal_router = APIRouter()
internal_router.include_router(meta_router)
internal_router.include_router(sync_routes.sync_router)

app.include_router(internal_router)
app.include_router(notify_router)


# Override schemas for Swagger documentation
app.openapi_schema = None  # Clear the cached schema


def custom_openapi() -> Any:
    """Customize the OpenAPI schema for Swagger documentation.

    This function modifies the OpenAPI schema to include both API and PubSub models for routes that are marked as PubSub API endpoints.
    This approach allows the API to handle both direct API calls and PubSub events using the same endpoint, while providing clear documentation for API users in the Swagger UI.
    """
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    for route in app.routes:
        if hasattr(route, "endpoint") and hasattr(route.endpoint, "is_pubsub_api"):
            request_model = route.endpoint.request_model
            path = route.path
            method = list(route.methods)[0].lower()

            pubsub_model = request_model.create_pubsub_model()
            api_model = request_model.create_api_model()

            openapi_schema["components"]["schemas"][pubsub_model.__name__] = pubsub_model.model_json_schema()
            openapi_schema["components"]["schemas"][api_model.__name__] = api_model.model_json_schema()

            openapi_schema["components"]["schemas"][request_model.__name__] = {
                "oneOf": [
                    {"$ref": f"#/components/schemas/{api_model.__name__}"},
                    {"$ref": f"#/components/schemas/{pubsub_model.__name__}"},
                ]
            }

            openapi_schema["paths"][path][method]["requestBody"]["content"]["application/json"]["schema"] = {
                "$ref": f"#/components/schemas/{api_model.__name__}"
            }

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi
