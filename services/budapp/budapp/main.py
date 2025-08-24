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

from budmicroframe.main import configure_app
from budmicroframe.shared.dapr_workflow import DaprWorkflow
from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .audit_ops import audit_routes
from .auth import auth_routes
from .benchmark_ops import benchmark_routes
from .billing_ops import billing_router
from .cluster_ops import cluster_routes
from .cluster_ops.workflows import ClusterRecommendedSchedulerWorkflows
from .commons import logging
from .commons.config import app_settings, secrets_settings
from .commons.exceptions import ClientException
from .core import common_routes, meta_routes, notify_routes
from .credential_ops import credential_routes
from .dataset_ops import dataset_routes
from .endpoint_ops import endpoint_routes
from .eval_ops import eval_routes
from .eval_ops.workflows import EvalDataSyncWorkflows
from .guardrails import guardrail_routes
from .initializers.seeder import seeders
from .metric_ops import metric_routes
from .model_ops import model_routes
from .model_ops.workflows import CloudModelSyncWorkflows
from .permissions import permission_routes
from .playground_ops import playground_routes
from .project_ops import project_routes
from .router_ops import router_routes
from .user_ops import user_routes
from .workflow_ops import workflow_routes


logger = logging.get_logger(__name__)


async def execute_initial_dapr_workflows() -> None:
    """Execute the dapr workflows.

    This function checks if the Dapr workflow is running and executes the dapr workflow.
    """
    POLLING_INTERVAL = 5
    attempts = 0

    # Start workflow runtime
    dapr_workflow = DaprWorkflow()
    dapr_workflow.start_workflow_runtime()

    while True:
        await asyncio.sleep(POLLING_INTERVAL)
        if dapr_workflow.is_running:
            logger.info("Dapr workflow runtime is ready. Initializing dapr workflows.")
            break
        else:
            attempts += 1
            logger.info("Waiting for Dapr workflow runtime to start... Attempt: %s", attempts)

    response = await CloudModelSyncWorkflows().__call__()
    logger.debug("Cloud model sync workflow response: %s", response)

    response = await ClusterRecommendedSchedulerWorkflows().__call__()
    logger.debug("Recommended cluster scheduler workflow response: %s", response)

    # Execute initial eval data sync workflow if enabled
    if app_settings.eval_sync_enabled:
        logger.info("Evaluation data sync is enabled")
        eval_sync_response = await EvalDataSyncWorkflows().__call__()
        logger.debug("Evaluation data sync workflow response: %s", eval_sync_response)
    else:
        logger.info("Evaluation data sync is disabled")


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
        await meta_routes.register_service()
        await asyncio.sleep(1.5)

        while True:
            await meta_routes.sync_configurations()
            await meta_routes.sync_secrets()

            await asyncio.sleep(
                randint(
                    int(app_settings.max_sync_interval * 0.9),
                    app_settings.max_sync_interval,
                )
            )

    async def schedule_eval_data_sync() -> None:
        """Schedule hourly evaluation data synchronization from cloud repository."""
        if not app_settings.eval_sync_enabled:
            logger.info("Evaluation data sync is disabled, skipping scheduler")
            return

        # Wait for Dapr workflow runtime to be ready
        await asyncio.sleep(10)

        while True:
            try:
                logger.info("Running scheduled evaluation data sync workflow")
                response = await EvalDataSyncWorkflows().__call__()
                logger.info("Scheduled eval data sync workflow response: %s", response)
            except Exception as e:
                logger.error("Failed to run scheduled eval data sync: %s", e)

            # Sleep for 1 hour (3600 seconds)
            await asyncio.sleep(3600)

    async def schedule_blocking_rule_stats_sync() -> None:
        """Schedule periodic synchronization of blocking rule statistics from ClickHouse."""
        from .commons.database import SessionLocal
        from .metric_ops.services import MetricService

        # Wait for services to be ready
        await asyncio.sleep(15)

        while True:
            try:
                logger.info("Running scheduled blocking rule stats sync")
                # Create a new session for this sync operation
                with SessionLocal() as session:
                    metric_service = MetricService(session)
                    result = await metric_service.sync_blocking_rule_stats_from_clickhouse()
                    logger.info("Blocking rule stats sync completed: %s", result)
            except Exception as e:
                logger.error("Failed to sync blocking rule stats: %s", e)

            # Sleep for 30 minutes (1800 seconds)
            await asyncio.sleep(1800)

    async def schedule_credential_usage_sync() -> None:
        """Schedule periodic synchronization of credential usage data from budmetrics."""
        from .commons.database import SessionLocal
        from .credential_ops.services import CredentialService

        # Wait for services to be ready
        await asyncio.sleep(20)

        while True:
            try:
                logger.info("Running scheduled credential usage sync")
                # Create a new session for this sync operation
                with SessionLocal() as session:
                    credential_service = CredentialService(session)
                    result = await credential_service.sync_credential_usage_from_metrics()
                    logger.info("Credential usage sync completed: %s", result)
            except Exception as e:
                logger.error("Failed to sync credential usage: %s", e)

            # Sleep for 5 minutes (300 seconds)
            await asyncio.sleep(300)

    task = asyncio.create_task(schedule_secrets_and_config_sync())

    for seeder_name, seeder in seeders.items():
        try:
            await seeder().seed()
            logger.info(f"Seeded {seeder_name} seeder successfully.")
        except Exception as e:
            logger.error(f"Failed to seed {seeder_name}. Error: {e}")

    # Execute initial dapr workflows
    dapr_workflow_task = asyncio.create_task(execute_initial_dapr_workflows())

    # Start the hourly eval data sync scheduler
    eval_sync_task = asyncio.create_task(schedule_eval_data_sync())

    # Start the blocking rule stats sync scheduler
    blocking_stats_task = asyncio.create_task(schedule_blocking_rule_stats_sync())

    # Start the credential usage sync scheduler
    credential_usage_task = asyncio.create_task(schedule_credential_usage_sync())

    yield

    try:
        task.cancel()
        dapr_workflow_task.cancel()
        eval_sync_task.cancel()
        blocking_stats_task.cancel()
        credential_usage_task.cancel()
    except asyncio.CancelledError:
        logger.exception("Failed to cleanup config & store sync.")

    DaprWorkflow().shutdown_workflow_runtime()


# app = FastAPI(
#     title=app_settings.name,
#     description=app_settings.description,
#     version=app_settings.version,
#     root_path=app_settings.api_root,
#     lifespan=lifespan,
#     openapi_url=None if app_settings.env == Environment.PRODUCTION else "/openapi.json",
# )

app = configure_app(
    app_settings,
    secrets_settings,
    lifespan=lifespan,
)


# Add exception handler for ClientException
@app.exception_handler(ClientException)
async def client_exception_handler(request: Request, exc: ClientException):
    """Handle ClientException and return proper HTTP status code."""
    return JSONResponse(
        status_code=exc.status_code, content={"success": False, "message": exc.message, "detail": str(exc)}
    )


# Serve static files
app.mount("/static", StaticFiles(directory=app_settings.static_dir), name="static")

# Set all CORS enabled origins
if app_settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin).strip("/") for origin in app_settings.cors_origins],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

internal_router = APIRouter()
internal_router.include_router(audit_routes.audit_router)
internal_router.include_router(auth_routes.auth_router)
internal_router.include_router(benchmark_routes.benchmark_router)
internal_router.include_router(cluster_routes.cluster_router)
internal_router.include_router(common_routes.common_router)
internal_router.include_router(credential_routes.credential_router)
internal_router.include_router(credential_routes.proprietary_credential_router)
internal_router.include_router(dataset_routes.dataset_router)
internal_router.include_router(endpoint_routes.endpoint_router)
internal_router.include_router(meta_routes.meta_router)
internal_router.include_router(metric_routes.metric_router)
internal_router.include_router(model_routes.model_router)
internal_router.include_router(notify_routes.notify_router)
internal_router.include_router(permission_routes.permission_router)
internal_router.include_router(user_routes.user_router)
internal_router.include_router(workflow_routes.workflow_router)
internal_router.include_router(playground_routes.playground_router)
internal_router.include_router(project_routes.project_router)
internal_router.include_router(router_routes.router_router)
internal_router.include_router(eval_routes.router)
internal_router.include_router(billing_router)
internal_router.include_router(guardrail_routes.router)

app.include_router(internal_router)


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
