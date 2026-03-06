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
#  WITHOUT WARRANTIES OssR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#  -----------------------------------------------------------------------------

"""The main entry point for the application, initializing the FastAPI app and setting up the application's lifespan management, including configuration and secret syncs."""

import asyncio
import os
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict
from urllib.parse import urlencode

import httpx
from budmicroframe.main import configure_app
from budmicroframe.shared.dapr_workflow import DaprWorkflow
from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from .audit_ops import audit_routes
from .auth import (
    auth_routes,
    oauth_admin_routes,
    oauth_internal_proxy,
    oauth_routes,
    secure_oauth_callback,
    token_exchange_routes,
)
from .benchmark_ops import benchmark_routes
from .billing_ops import billing_router
from .cluster_ops import cluster_routes
from .cluster_ops.cluster_settings_routes import cluster_settings_router
from .cluster_ops.workflows import ClusterRecommendedSchedulerWorkflows
from .commons import logging
from .commons.config import app_settings, secrets_settings
from .commons.exceptions import ClientException
from .connector_ops import connector_routes
from .core import common_routes, meta_routes, notify_routes
from .credential_ops import credential_routes
from .dataset_ops import dataset_routes
from .endpoint_ops import endpoint_routes
from .eval_ops import eval_routes
from .eval_ops.workflows import EvalDataSyncWorkflows
from .guardrails import guardrail_routes
from .guardrails.workflows import GuardrailSyncWorkflows
from .initializers.seeder import seeders
from .metric_ops import metric_routes
from .model_ops import model_routes
from .model_ops.workflows import CloudModelSyncWorkflows
from .permissions import permission_routes
from .playground_ops import playground_routes
from .project_ops import project_routes
from .prompt_ops import prompt_routes
from .router_ops import router_routes
from .user_ops import user_routes
from .workflow_ops import budpipeline_routes, budusecases_routes, workflow_routes


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

    response = await GuardrailSyncWorkflows().__call__()
    logger.debug("Guardrail sync workflow response: %s", response)

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

    async def schedule_hybrid_metrics_sync() -> None:
        """Schedule hybrid metrics sync combining credential usage and user limits."""
        from .metric_ops.hybrid_sync import start_hybrid_sync, stop_hybrid_sync

        # Wait for services to be ready
        await asyncio.sleep(15)

        try:
            logger.info("Starting hybrid metrics sync task")
            await start_hybrid_sync()
        except Exception as e:
            logger.error("Failed to start hybrid metrics sync: %s", e)

    async def schedule_billing_cycle_reset() -> None:
        """Schedule periodic check for expired billing cycles."""
        from .billing_ops.reset_usage import start_billing_reset_task, stop_billing_reset_task

        # Wait for services to be ready
        await asyncio.sleep(15)

        try:
            logger.info("Starting billing cycle reset task")
            await start_billing_reset_task()
        except Exception as e:
            logger.error("Failed to start billing cycle reset task: %s", e)

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

    # Start the hybrid metrics sync scheduler (combines credential usage + user limits)
    hybrid_sync_task = asyncio.create_task(schedule_hybrid_metrics_sync())

    # Start the billing cycle reset scheduler
    billing_reset_task = asyncio.create_task(schedule_billing_cycle_reset())

    yield

    try:
        task.cancel()
        dapr_workflow_task.cancel()
        eval_sync_task.cancel()
        blocking_stats_task.cancel()
        hybrid_sync_task.cancel()
        billing_reset_task.cancel()

        # Stop the background tasks
        from .billing_ops.reset_usage import stop_billing_reset_task
        from .metric_ops.hybrid_sync import stop_hybrid_sync

        await stop_hybrid_sync()
        await stop_billing_reset_task()
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

# Add middleware to validate Dapr APP_API_TOKEN for internal endpoints (MUST be added early)
_middleware_logger = logging.get_logger("budapp.middleware.internal_auth")


@app.middleware("http")
async def internal_auth_middleware(request: Request, call_next):
    """Validate Dapr APP_API_TOKEN for /internal/ endpoints."""
    _middleware_logger.debug(f"Middleware processing: {request.url.path}")
    if "/internal/" in request.url.path:
        _middleware_logger.info(f"Internal endpoint: {request.url.path}")
        expected_token = os.environ.get("APP_API_TOKEN")
        if not expected_token:
            _middleware_logger.warning("APP_API_TOKEN not configured")
            return JSONResponse(
                status_code=403,
                content={"detail": "Forbidden - Internal auth not configured"},
            )
        # Check both dapr-api-token and x-app-api-token (Dapr may consume dapr-api-token)
        actual_token = request.headers.get("dapr-api-token") or request.headers.get("x-app-api-token")
        if actual_token != expected_token:
            _middleware_logger.warning(f"Invalid internal token for {request.url.path}")
            return JSONResponse(
                status_code=403,
                content={"detail": "Forbidden - Invalid internal token"},
            )
        _middleware_logger.debug("Token valid")
    return await call_next(request)


# Headers stripped from the *request* before forwarding upstream.
# With subdomain routing the browser never sends the budadmin JWT to the
# usecase subdomain (different origin), so "authorization" is NOT stripped —
# usecase apps (e.g. RAGFlow) need it for their own auth tokens.
_PROXY_REQUEST_HOP_BY_HOP = frozenset(
    {
        "host",
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
        "content-length",
        "content-encoding",
    }
)

# Headers stripped from the upstream *response* before returning to the browser.
# "authorization" is intentionally NOT listed here so usecase apps (e.g. RAGFlow)
# can set auth tokens via the Authorization response header.
_PROXY_RESPONSE_HOP_BY_HOP = frozenset(
    {
        "host",
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
        "content-length",
        "content-encoding",
    }
)

_usecase_proxy_logger = logging.get_logger("budapp.middleware.usecase_proxy")

# In-process TTL cache for deployment lookups to avoid Dapr+DB round-trip on
# every proxied request (CSS, JS, images, etc.).  30s TTL is short enough to
# pick up status changes (RUNNING → STOPPED) promptly.
_DEPLOYMENT_CACHE_TTL = 30.0
_deployment_cache: Dict[str, tuple[dict, float]] = {}  # deployment_id → (data, expires_at)


def _get_cached_deployment(deployment_id: str) -> dict | None:
    entry = _deployment_cache.get(deployment_id)
    if entry and entry[1] > time.monotonic():
        return entry[0]
    _deployment_cache.pop(deployment_id, None)
    return None


def _set_cached_deployment(deployment_id: str, data: dict) -> None:
    _deployment_cache[deployment_id] = (data, time.monotonic() + _DEPLOYMENT_CACHE_TTL)


@app.middleware("http")
async def usecase_subdomain_proxy(request: Request, call_next):
    """Proxy requests arriving on uc-{id}.usecases.dev.bud.studio.

    The middleware intercepts requests on usecase subdomains and proxies
    them directly to the target cluster's gateway. It returns a Response
    directly — it does NOT pass to FastAPI's route handlers.
    """
    usecase_domain = app_settings.usecase_domain
    if not usecase_domain:
        _usecase_proxy_logger.debug("usecase_domain not configured, skipping")
        return await call_next(request)

    host = (request.headers.get("host") or "").split(":")[0]
    suffix = f".{usecase_domain}"
    if not host.endswith(suffix):
        return await call_next(request)

    prefix = host[: -len(suffix)]
    if not prefix.startswith("uc-"):
        return await call_next(request)

    deployment_id = prefix[3:]  # "uc-abc123" → "abc123"
    path = request.url.path.lstrip("/")

    # Sanitise path to prevent path traversal
    if ".." in path.split("/"):
        return Response(content="Invalid path", status_code=400)

    # Fetch deployment details (with in-process TTL cache)
    deployment = _get_cached_deployment(deployment_id)
    if deployment is None:
        from .commons.database import SessionLocal
        from .workflow_ops.budusecases_service import BudUseCasesService

        try:
            with SessionLocal() as session:
                service = BudUseCasesService(session)
                deployment = await service.get_deployment(deployment_id)
        except Exception:
            _usecase_proxy_logger.exception("Failed to fetch deployment %s", deployment_id)
            return Response(content="Deployment not found", status_code=404)

        if deployment:
            _set_cached_deployment(deployment_id, deployment)

    if not deployment:
        return Response(content="Deployment not found", status_code=404)

    dep_status = (deployment.get("status") or "").upper()
    if dep_status != "RUNNING":
        return Response(content=f"Deployment not running (status: {dep_status})", status_code=404)

    access_config = deployment.get("access_config") or {}
    ui_config = access_config.get("ui") or {}
    if not ui_config.get("enabled"):
        return Response(content="UI access not enabled", status_code=403)

    gateway_url = deployment.get("gateway_url")
    if not gateway_url:
        return Response(content="Gateway route not available", status_code=503)

    # Construct upstream URL
    target_url = f"{gateway_url.rstrip('/')}/usecases/{deployment_id}/ui/{path}"

    # Forward query params, excluding the auth token
    filtered_params = {k: v for k, v in request.query_params.items() if k != "token"}
    if filtered_params:
        target_url += "?" + urlencode(filtered_params)

    # Forward headers (strip request hop-by-hop)
    forwarded_headers: Dict[str, str] = {}
    for key, value in request.headers.items():
        if key.lower() not in _PROXY_REQUEST_HOP_BY_HOP:
            forwarded_headers[key] = value

    body = await request.body()

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            upstream = await client.request(
                method=request.method,
                url=target_url,
                headers=forwarded_headers,
                content=body,
            )
    except httpx.TimeoutException:
        return Response(content="Upstream timeout", status_code=504)
    except httpx.HTTPError as exc:
        _usecase_proxy_logger.exception("Upstream request failed: %s", exc)
        return Response(content="Failed to reach upstream", status_code=502)

    # Return raw upstream response — NO HTML/JS rewriting needed
    response_headers: Dict[str, str] = {}
    for key, value in upstream.headers.items():
        if key.lower() not in _PROXY_RESPONSE_HOP_BY_HOP:
            response_headers[key] = value

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=response_headers,
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

logger = logging.get_logger(__name__)

internal_router = APIRouter()
internal_router.include_router(audit_routes.audit_router)
internal_router.include_router(auth_routes.auth_router)
internal_router.include_router(oauth_routes.oauth_router)
internal_router.include_router(secure_oauth_callback.secure_oauth_callback_router)
internal_router.include_router(token_exchange_routes.token_exchange_router)
internal_router.include_router(oauth_admin_routes.oauth_admin_router)
internal_router.include_router(oauth_internal_proxy.internal_oauth_router)
internal_router.include_router(benchmark_routes.benchmark_router)
internal_router.include_router(cluster_routes.cluster_router)
internal_router.include_router(cluster_settings_router)
internal_router.include_router(connector_routes.connector_router)
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
internal_router.include_router(budpipeline_routes.budpipeline_router)
internal_router.include_router(budusecases_routes.budusecases_router)
internal_router.include_router(playground_routes.playground_router)
internal_router.include_router(project_routes.project_router)
internal_router.include_router(prompt_routes.router)
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
