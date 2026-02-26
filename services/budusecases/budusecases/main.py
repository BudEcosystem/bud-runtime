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

"""Main entry point for BudUseCases service.

This module initializes the FastAPI application with Dapr integration,
database connections, and all routes.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from budmicroframe.main import configure_app, dapr_lifespan
from budmicroframe.shared.psql_service import Database
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .commons.config import app_settings, secrets_settings
from .templates.startup import sync_templates_on_startup

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan: sync templates then delegate to Dapr lifespan."""
    db = Database()
    db.connect()
    sync_templates_on_startup(
        session_maker=db.Session,
        enabled=app_settings.templates_sync_on_startup,
        templates_path=app_settings.templates_path,
    )

    async with dapr_lifespan(app):
        yield


app = configure_app(app_settings, secrets_settings, lifespan=lifespan)

# Register routers
from .commons.dependencies import get_current_project_id, get_current_user_id, get_session  # noqa: E402
from .deployments.routes import get_current_project_id as deployment_get_project  # noqa: E402
from .deployments.routes import get_current_user_id as deployment_get_user  # noqa: E402
from .deployments.routes import get_session as deployment_get_session  # noqa: E402
from .deployments.routes import router as deployment_router  # noqa: E402
from .templates.routes import get_current_user_id as template_get_user  # noqa: E402
from .templates.routes import get_session as template_get_session  # noqa: E402
from .templates.routes import router as template_router  # noqa: E402

app.include_router(template_router, prefix="/api/v1")
app.include_router(deployment_router, prefix="/api/v1")

# Wire up dependencies
app.dependency_overrides[template_get_session] = get_session
app.dependency_overrides[deployment_get_session] = get_session
app.dependency_overrides[template_get_user] = get_current_user_id
app.dependency_overrides[deployment_get_user] = get_current_user_id
app.dependency_overrides[deployment_get_project] = get_current_project_id


@app.post("/budusecases-events")
async def handle_budusecases_event(request: Request):
    """Handle incoming Dapr pub/sub events from BudPipeline.

    Dapr delivers events as CloudEvents.  The actual payload is nested inside
    the ``data`` field of the CloudEvent envelope.  This handler extracts the
    inner payload and delegates to :func:`handle_pipeline_event`.

    Returns 200 in all cases to prevent Dapr from retrying on processing
    errors (idempotent acknowledgement).
    """
    from budmicroframe.shared.psql_service import Database

    from .events.pipeline_listener import handle_pipeline_event

    try:
        body = await request.json()

        # Dapr wraps the published payload inside a CloudEvent ``data`` field.
        event_data = body.get("data", body)

        logger.info(
            "Received pipeline event: type=%s, pipeline_event_type=%s, execution_id=%s",
            event_data.get("type", "unknown"),
            event_data.get("pipeline_event_type", "unknown"),
            event_data.get("execution_id", "unknown"),
        )

        # Obtain a database session using the same singleton Database pattern
        # used across all bud-stack services (see budcluster/commons/dependencies.py).
        db = Database()
        session = db.get_session()
        try:
            await handle_pipeline_event(event_data=event_data, session=session)
        finally:
            db.close_session(session)

        return JSONResponse(content={"status": "ok"}, status_code=200)

    except Exception as e:
        logger.error("Error processing pipeline event: %s", e, exc_info=True)
        # Return 200 to prevent Dapr from retrying on processing errors
        return JSONResponse(content={"status": "error", "detail": str(e)}, status_code=200)
