"""Main entry point for budpipeline service."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from budpipeline.__about__ import __version__
from budpipeline.commons.config import secrets_settings, settings
from budpipeline.commons.exceptions import WorkflowException
from budpipeline.commons.observability import get_logger, setup_observability
from budpipeline.commons.resilience import db_circuit_breaker, fallback_storage

# Get structlog logger
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    logger.info(f"Starting {settings.name} v{__version__}")
    logger.info(f"Dapr HTTP endpoint: {settings.dapr_http_endpoint}")

    # Register built-in handlers
    from budpipeline.handlers import global_registry

    logger.info(f"Registered handlers: {global_registry.list_handlers()}")

    yield

    # Cleanup
    logger.info(f"Shutting down {settings.name}")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="BudPipeline",
        description="Pipeline orchestration service for bud-stack platform",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def internal_auth_middleware(request: Request, call_next):
        """Validate APP_API_TOKEN for internal endpoints."""
        path = request.url.path
        if path.startswith("/internal/") or path == "/workflow-events":
            expected_token = secrets_settings.app_api_token
            if not expected_token:
                logger.warning(
                    "APP_API_TOKEN not configured - rejecting internal request to %s",
                    path,
                )
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Forbidden - Internal auth not configured"},
                )
            actual_token = request.headers.get("dapr-api-token")
            if actual_token != expected_token:
                logger.warning(
                    "Invalid dapr-api-token header - rejecting internal request to %s",
                    path,
                )
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Forbidden - Invalid internal token"},
                )

        return await call_next(request)

    # Rate limiting middleware for GET endpoints (T069)
    @app.middleware("http")
    async def rate_limiting_middleware(request: Request, call_next):
        """Apply rate limiting to GET execution endpoints."""
        from budpipeline.commons.rate_limiting import execution_rate_limiter, get_client_id

        path = request.url.path

        # Only rate limit GET requests to execution endpoints
        if request.method == "GET" and "/executions" in path:
            client_id = get_client_id(request)
            allowed, remaining = execution_rate_limiter.check_and_record(client_id)

            if not allowed:
                logger.warning(
                    "Rate limit exceeded",
                    client_id=client_id,
                    path=path,
                )
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "TooManyRequests",
                        "message": "Rate limit exceeded. Please slow down.",
                        "retry_after_seconds": 60,
                    },
                    headers={
                        "Retry-After": "60",
                        "X-RateLimit-Limit": str(execution_rate_limiter.rate_limit),
                        "X-RateLimit-Remaining": "0",
                    },
                )

            response = await call_next(request)

            # Add rate limit headers to response
            response.headers["X-RateLimit-Limit"] = str(execution_rate_limiter.rate_limit)
            response.headers["X-RateLimit-Remaining"] = str(remaining)

            return response

        return await call_next(request)

    # Exception handlers
    @app.exception_handler(WorkflowException)
    async def workflow_exception_handler(request: Request, exc: WorkflowException) -> JSONResponse:
        """Handle workflow exceptions."""
        return JSONResponse(
            status_code=400,
            content={
                "error": exc.__class__.__name__,
                "message": exc.message,
                "details": exc.details,
            },
        )

    # Setup observability (correlation IDs, metrics, structured logging) - T022
    setup_observability(app)

    # Health endpoints
    @app.get("/health", tags=["Health"])
    async def health() -> dict:
        """Health check endpoint with database and fallback status."""
        # Check database connectivity via circuit breaker state
        db_connected = not db_circuit_breaker.is_open
        fallback_active = fallback_storage.is_active()

        status = "healthy" if db_connected else "degraded"
        if fallback_active and not db_connected:
            status = "degraded"

        return {
            "status": status,
            "service": settings.name,
            "version": __version__,
            "database": "connected" if db_connected else "disconnected",
            "fallback_mode": fallback_active,
        }

    @app.get("/ready", tags=["Health"])
    async def ready() -> dict:
        """Readiness check endpoint."""
        # Check if we can serve requests (either DB or fallback)
        db_connected = not db_circuit_breaker.is_open
        fallback_active = fallback_storage.is_active()

        # Ready if either DB is connected or fallback is active
        is_ready = db_connected or fallback_active

        return {
            "status": "ready" if is_ready else "not_ready",
            "dapr_connected": True,
            "database_connected": db_connected,
            "fallback_active": fallback_active,
        }

    # Register routers
    from budpipeline.pipeline.execution_routes import router as execution_router
    from budpipeline.pipeline.routes import router as pipeline_router
    from budpipeline.progress.routes import router as progress_router
    from budpipeline.scheduler.routes import (
        event_trigger_router,
        schedule_router,
        webhook_router,
    )

    # Mount at root for direct Dapr service invocation compatibility
    # Also mount at /api/v1/pipeline for direct API access
    app.include_router(pipeline_router, tags=["Pipeline"])
    app.include_router(pipeline_router, prefix="/api/v1/pipeline", tags=["Pipeline API"])

    # Execution persistence routes (002-pipeline-event-persistence)
    app.include_router(execution_router, tags=["Executions"])
    app.include_router(execution_router, prefix="/api/v1", tags=["Executions API"])

    # Progress event routes (002-pipeline-event-persistence - T058)
    app.include_router(progress_router, tags=["Progress Events"])
    app.include_router(progress_router, prefix="/api/v1", tags=["Progress Events API"])

    # Schedule/trigger routers
    app.include_router(schedule_router, tags=["Schedules"])
    app.include_router(webhook_router, tags=["Webhooks"])
    app.include_router(event_trigger_router, tags=["Event Triggers"])

    # Dapr pub/sub callback endpoint for workflow completion events
    @app.post("/workflow-events", tags=["Internal"])
    async def receive_workflow_event(request: Request) -> dict:
        """Receive pipeline events from external services via Dapr pub/sub.

        This endpoint is called by Dapr when events are published to the
        'budpipelineEvents' topic. It routes events to the appropriate handlers
        using the event-driven completion architecture.

        Events can come from:
        - budcluster: performance_benchmark:results, model_extraction:*, etc.
        - budapp: workflow_completed (legacy support)

        The event router finds the step waiting for the event and calls the
        handler's on_event() method to process it.
        """
        from budpipeline.commons.database import get_db_session
        from budpipeline.handlers.event_router import route_event
        from budpipeline.webhook.event_handler import event_handler

        try:
            # Dapr sends CloudEvents format - get the raw body
            body = await request.json()

            # CloudEvents wraps data in 'data' field
            event_data = body.get("data", body)

            event_type = event_data.get("type")
            logger.info(f"Received workflow event: type={event_type}")
            logger.debug(f"Event data: {event_data}")

            trigger_results = []
            route_result = None

            # Route the event to the appropriate handler via database lookup
            try:
                async with get_db_session() as session:
                    route_result = await route_event(session, event_data)
                    await session.commit()

                    if route_result.routed and route_result.step_completed:
                        logger.info(
                            f"Event routed to step {route_result.step_execution_id}, "
                            f"action={route_result.action_taken}, "
                            f"final_status={route_result.final_status}"
                        )

                        # Trigger pipeline continuation after step completion
                        if route_result.step_completed:
                            try:
                                from budpipeline.handlers.event_router import (
                                    trigger_pipeline_continuation,
                                )

                                await trigger_pipeline_continuation(
                                    session, route_result.step_execution_id
                                )
                                await session.commit()  # Commit the execution status update
                            except Exception as cont_err:
                                logger.error(f"Failed to trigger pipeline continuation: {cont_err}")
                    elif route_result.routed:
                        logger.debug(
                            f"Event processed for step {route_result.step_execution_id}, "
                            f"action={route_result.action_taken}"
                        )
                    else:
                        logger.debug(f"Event not routed: {route_result.error}")

            except Exception as route_err:
                logger.warning(f"Event routing failed: {route_err}")
                # Fall through to try event triggers

            # Also process event triggers for event-driven pipelines
            # (This allows events to both complete steps AND trigger new pipelines)
            try:
                trigger_results = await event_handler.handle_event(event_data)
                if trigger_results:
                    logger.info(f"Event {event_type} triggered {len(trigger_results)} workflows")
            except Exception as trigger_err:
                logger.warning(f"Event trigger handling failed: {trigger_err}")

            # Always return success to acknowledge the message
            return {
                "status": "received",
                "routed": route_result.routed if route_result else False,
                "step_completed": route_result.step_completed if route_result else False,
                "triggers": trigger_results if trigger_results else None,
            }

        except Exception as e:
            logger.error(f"Error processing workflow event: {e}")
            # Still return success to avoid message retry loops
            return {"status": "error", "message": str(e)}

    # Dapr cron binding endpoint for schedule polling
    @app.post("/internal/schedule-poll", tags=["Internal"])
    async def schedule_poll() -> dict:
        """Internal endpoint called by Dapr cron binding every minute.

        Polls for due schedules and triggers workflow executions.
        This endpoint is not meant to be called directly by users.
        """
        from budpipeline.scheduler.polling import polling_service

        result = await polling_service.poll_and_execute()

        logger.info(
            f"Schedule poll completed: triggered {result.get('triggered_count', 0)} "
            f"of {result.get('due_count', 0)} due schedules"
        )

        return result

    # Dapr cron binding endpoint for retention cleanup (002-pipeline-event-persistence - T063)
    @app.post("/internal/retention-cleanup", tags=["Internal"])
    async def retention_cleanup() -> dict:
        """Internal endpoint called by Dapr cron binding for retention cleanup.

        Cleans up old pipeline execution records based on PIPELINE_RETENTION_DAYS.
        This endpoint is called according to PIPELINE_CLEANUP_SCHEDULE (default: 3 AM daily).
        """
        from budpipeline.pipeline.retention import run_retention_cleanup

        result = await run_retention_cleanup()

        logger.info(
            f"Retention cleanup completed: deleted {result.get('deleted', {}).get('executions', 0)} "
            f"executions in {result.get('duration_seconds', 0)}s"
        )

        return result

    # Endpoint to get retention cleanup statistics
    @app.get("/internal/retention-stats", tags=["Internal"])
    async def retention_stats() -> dict:
        """Get statistics about executions pending retention cleanup."""
        from budpipeline.pipeline.retention import retention_service

        return await retention_service.get_cleanup_stats()

    # Dapr cron binding endpoint for step timeout checking (event-driven-completion)
    @app.post("/internal/step-timeout-check", tags=["Internal"])
    async def step_timeout_check() -> dict:
        """Internal endpoint called by Dapr cron binding to check for timed-out steps.

        Checks for steps that have been waiting for external events past their
        timeout_at deadline and marks them as TIMEOUT status.

        This endpoint is called according to STEP_TIMEOUT_CHECK_INTERVAL (default: 60s).
        """
        from budpipeline.scheduler.timeout_scheduler import check_and_process_timeouts

        result = await check_and_process_timeouts()

        if result.get("processed_count", 0) > 0:
            logger.info(
                f"Step timeout check: processed {result.get('processed_count')} "
                f"of {result.get('timed_out_count')} timed-out steps"
            )

        return result

    # Endpoint to get step timeout statistics
    @app.get("/internal/step-timeout-stats", tags=["Internal"])
    async def step_timeout_stats() -> dict:
        """Get statistics about steps awaiting events and timeouts."""
        from budpipeline.scheduler.timeout_scheduler import get_timeout_stats

        return await get_timeout_stats()

    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "budpipeline.main:app",
        host="0.0.0.0",
        port=settings.service_port,
        reload=settings.debug,
    )
