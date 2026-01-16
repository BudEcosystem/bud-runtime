"""Main entry point for budpipeline service."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from budpipeline.__about__ import __version__
from budpipeline.commons.config import settings
from budpipeline.commons.exceptions import WorkflowException

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    logger.info(f"Starting {settings.service_name} v{__version__}")
    logger.info(f"Dapr HTTP endpoint: {settings.dapr_http_endpoint}")

    # Register built-in handlers
    from budpipeline.handlers import global_registry

    logger.info(f"Registered handlers: {global_registry.list_handlers()}")

    yield

    # Cleanup
    logger.info(f"Shutting down {settings.service_name}")


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
            expected_token = settings.app_api_token
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

    # Health endpoints
    @app.get("/health", tags=["Health"])
    async def health() -> dict:
        """Health check endpoint."""
        return {
            "status": "healthy",
            "service": settings.service_name,
            "version": __version__,
        }

    @app.get("/ready", tags=["Health"])
    async def ready() -> dict:
        """Readiness check endpoint."""
        # TODO: Check Dapr connectivity
        return {
            "status": "ready",
            "dapr_connected": True,
        }

    # Register routers
    from budpipeline.pipeline.routes import router as pipeline_router
    from budpipeline.scheduler.routes import (
        event_trigger_router,
        schedule_router,
        webhook_router,
    )

    # Mount at root for direct Dapr service invocation compatibility
    # Also mount at /api/v1/pipeline for direct API access
    app.include_router(pipeline_router, tags=["Pipeline"])
    app.include_router(pipeline_router, prefix="/api/v1/pipeline", tags=["Pipeline API"])

    # Schedule/trigger routers
    app.include_router(schedule_router, tags=["Schedules"])
    app.include_router(webhook_router, tags=["Webhooks"])
    app.include_router(event_trigger_router, tags=["Event Triggers"])

    # Dapr pub/sub callback endpoint for workflow completion events from budapp
    @app.post("/workflow-events", tags=["Internal"])
    async def receive_workflow_event(request: Request) -> dict:
        """Receive pipeline completion events from budapp via Dapr pub/sub.

        This endpoint is called by Dapr when events are published to the
        'budpipelineEvents' topic. It processes completion events from budapp
        pipelines (model_add, benchmark, etc.) and signals waiting handlers.
        It also processes platform events for event-driven triggers.
        """
        from budpipeline.handlers.completion_tracker import completion_tracker
        from budpipeline.webhook.event_handler import event_handler

        try:
            # Dapr sends CloudEvents format - get the raw body
            body = await request.json()

            # CloudEvents wraps data in 'data' field
            event_data = body.get("data", body)

            event_type = event_data.get("type")
            logger.debug(f"Received workflow event: type={event_type}, data={event_data}")

            trigger_results = []

            if event_type == "workflow_completed":
                workflow_id = event_data.get("workflow_id")
                status = event_data.get("status", "UNKNOWN")
                result = event_data.get("result", {})
                reason = event_data.get("reason")

                if workflow_id:
                    await completion_tracker.signal_completion(
                        workflow_id=str(workflow_id),
                        status=status,
                        result=result,
                        reason=reason,
                    )
                    logger.info(
                        f"Signaled completion for workflow {workflow_id}: "
                        f"status={status}, result={result}"
                    )
                else:
                    logger.warning("Received workflow_completed event without workflow_id")
            else:
                # Process event triggers for non-completion events
                trigger_results = await event_handler.handle_event(event_data)
                if trigger_results:
                    logger.info(f"Event {event_type} triggered {len(trigger_results)} workflows")

            # Always return success to acknowledge the message
            return {
                "status": "received",
                "triggers": trigger_results if trigger_results else None,
            }

        except Exception as e:
            logger.error(f"Error processing workflow event: {e}")
            # Still return success to avoid message retry loops
            # The completion tracker will handle timeouts
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
