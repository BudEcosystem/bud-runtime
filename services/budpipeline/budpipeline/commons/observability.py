"""Observability infrastructure for budpipeline.

This module provides structured logging with correlation IDs and Prometheus
metrics configuration (002-pipeline-event-persistence - T020, T021).
"""

import logging
import sys
from enum import Enum
from typing import Any

import structlog
from asgi_correlation_id import CorrelationIdMiddleware
from asgi_correlation_id.context import correlation_id
from fastapi import FastAPI
from prometheus_client import Counter, Gauge, Histogram
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_fastapi_instrumentator.metrics import Info

from budpipeline.commons.config import settings


def _get_log_level_string(log_level: Any) -> str:
    """Convert log level to string for use with logging module.

    Args:
        log_level: Log level value (can be Enum, string, or int).

    Returns:
        String representation of the log level.
    """
    if isinstance(log_level, Enum):
        return log_level.value.upper() if isinstance(log_level.value, str) else log_level.name
    if isinstance(log_level, str):
        return log_level.upper()
    return str(log_level)


# Custom Prometheus metrics for pipeline persistence (FR-031 to FR-035)
EXECUTION_CREATED = Counter(
    "budpipeline_execution_created_total",
    "Total number of pipeline executions created",
    ["initiator"],
)

EXECUTION_COMPLETED = Counter(
    "budpipeline_execution_completed_total",
    "Total number of pipeline executions completed",
    ["status"],  # COMPLETED, FAILED, INTERRUPTED
)

EXECUTION_DURATION = Histogram(
    "budpipeline_execution_duration_seconds",
    "Pipeline execution duration in seconds",
    ["status"],
    buckets=[1, 5, 10, 30, 60, 120, 300, 600, 1800, 3600, 7200],
)

STEP_EXECUTION_DURATION = Histogram(
    "budpipeline_step_duration_seconds",
    "Step execution duration in seconds",
    ["step_name", "status"],
    buckets=[0.1, 0.5, 1, 5, 10, 30, 60, 120, 300],
)

ACTIVE_EXECUTIONS = Gauge(
    "budpipeline_active_executions",
    "Number of currently active (RUNNING) pipeline executions",
)

DB_OPERATION_DURATION = Histogram(
    "budpipeline_db_operation_seconds",
    "Database operation duration in seconds",
    ["operation", "entity"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)

DB_ERRORS = Counter(
    "budpipeline_db_errors_total",
    "Total number of database errors",
    ["operation", "error_type"],
)

EVENT_PUBLISHED = Counter(
    "budpipeline_events_published_total",
    "Total number of events published to callback topics",
    ["event_type"],
)

FALLBACK_ACTIVE = Gauge(
    "budpipeline_fallback_active",
    "Whether in-memory fallback is currently active (1) or not (0)",
)


def add_correlation_id(
    logger: logging.Logger, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Add correlation ID to log events.

    Args:
        logger: The logger instance.
        method_name: The method name.
        event_dict: The event dictionary.

    Returns:
        Modified event dictionary with correlation_id.
    """
    request_id = correlation_id.get()
    if request_id:
        event_dict["correlation_id"] = request_id
    return event_dict


def configure_structlog() -> None:
    """Configure structlog for structured logging with correlation IDs.

    Sets up processors for JSON output with correlation ID injection (FR-032).
    """
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        add_correlation_id,
    ]

    if settings.debug:
        # Development: colored console output
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    else:
        # Production: JSON output
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging
    # Handle LogLevel enum from budmicroframe
    log_level_str = _get_log_level_string(settings.log_level)
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level_str, logging.INFO),
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a configured structlog logger.

    Args:
        name: Logger name (optional, defaults to module name).

    Returns:
        Configured structlog logger instance.
    """
    return structlog.get_logger(name)


def setup_prometheus_metrics(app: FastAPI) -> Instrumentator:
    """Setup Prometheus metrics instrumentation for FastAPI.

    Configures automatic HTTP request metrics plus custom pipeline metrics (FR-031).

    Args:
        app: FastAPI application instance.

    Returns:
        Configured Instrumentator instance.
    """
    instrumentator = Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        should_respect_env_var=True,
        should_instrument_requests_inprogress=True,
        excluded_handlers=["/health", "/metrics"],
        inprogress_name="budpipeline_http_requests_inprogress",
        inprogress_labels=True,
    )

    # Add default HTTP metrics
    instrumentator.add(
        http_request_duration_seconds_histogram(
            metric_name="budpipeline_http_request_duration_seconds",
        )
    )

    # Instrument the app
    instrumentator.instrument(app)

    return instrumentator


def http_request_duration_seconds_histogram(
    metric_name: str = "budpipeline_http_request_duration_seconds",
    metric_doc: str = "HTTP request duration in seconds",
    metric_namespace: str = "",
    metric_subsystem: str = "",
    buckets: tuple = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
) -> callable:
    """Create HTTP request duration histogram metric.

    Args:
        metric_name: Name of the metric.
        metric_doc: Description of the metric.
        metric_namespace: Prometheus metric namespace.
        metric_subsystem: Prometheus metric subsystem.
        buckets: Histogram buckets.

    Returns:
        Instrumentation function.
    """
    histogram = Histogram(
        metric_name,
        metric_doc,
        ["method", "handler", "status"],
        namespace=metric_namespace,
        subsystem=metric_subsystem,
        buckets=buckets,
    )

    def instrumentation(info: Info) -> None:
        handler = info.modified_handler or info.request.url.path

        histogram.labels(
            method=info.request.method,
            handler=handler,
            status=info.modified_status or info.response.status_code,
        ).observe(info.modified_duration)

    return instrumentation


def setup_observability(app: FastAPI) -> None:
    """Setup all observability features for the application.

    Configures:
    - Structured logging with structlog
    - Correlation ID middleware
    - Prometheus metrics

    Args:
        app: FastAPI application instance.
    """
    # Configure structlog
    configure_structlog()

    # Add correlation ID middleware (FR-032)
    app.add_middleware(
        CorrelationIdMiddleware,
        header_name="X-Correlation-ID",
        generator=lambda: None,  # Use UUID from header or generate
        validator=None,
        transformer=lambda x: x,
    )

    # Setup Prometheus metrics
    instrumentator = setup_prometheus_metrics(app)

    # Expose metrics endpoint
    @app.on_event("startup")
    async def _startup() -> None:
        instrumentator.expose(app, endpoint="/metrics", include_in_schema=False)

    logger = get_logger(__name__)
    logger.info("Observability configured", debug=settings.debug, log_level=settings.log_level)


# Convenience functions for recording metrics
def record_execution_created(initiator: str) -> None:
    """Record a new execution creation."""
    EXECUTION_CREATED.labels(initiator=initiator).inc()


def record_execution_completed(status: str, duration_seconds: float) -> None:
    """Record execution completion with duration."""
    EXECUTION_COMPLETED.labels(status=status).inc()
    EXECUTION_DURATION.labels(status=status).observe(duration_seconds)


def record_step_completed(step_name: str, status: str, duration_seconds: float) -> None:
    """Record step completion with duration."""
    STEP_EXECUTION_DURATION.labels(step_name=step_name, status=status).observe(duration_seconds)


def record_db_operation(operation: str, entity: str, duration_seconds: float) -> None:
    """Record database operation duration."""
    DB_OPERATION_DURATION.labels(operation=operation, entity=entity).observe(duration_seconds)


def record_db_error(operation: str, error_type: str) -> None:
    """Record database error."""
    DB_ERRORS.labels(operation=operation, error_type=error_type).inc()


def record_event_published(event_type: str) -> None:
    """Record event publication."""
    EVENT_PUBLISHED.labels(event_type=event_type).inc()


def set_active_executions(count: int) -> None:
    """Set current active execution count."""
    ACTIVE_EXECUTIONS.set(count)


def set_fallback_active(active: bool) -> None:
    """Set fallback mode status."""
    FALLBACK_ACTIVE.set(1 if active else 0)
