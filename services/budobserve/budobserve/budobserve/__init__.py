"""BudObserve - Observability SDK for Bud-Stack platform.

Built on OpenTelemetry, BudObserve provides a high-level API for tracing,
metrics, and logging with automatic instrumentation for common frameworks.

Example:
    >>> import budobserve
    >>> budobserve.configure(service_name="my-service")
    >>> with budobserve.span("processing request"):
    ...     # your code here
    ...     pass

Configuration:
    The SDK can be configured via:
    1. Explicit arguments to configure()
    2. Environment variables (BUDOBSERVE_*, OTEL_*)
    3. Default values

    Environment variables:
        BUDOBSERVE_SERVICE_NAME / OTEL_SERVICE_NAME: Service name
        BUDOBSERVE_SERVICE_VERSION / OTEL_SERVICE_VERSION: Service version
        BUDOBSERVE_ENVIRONMENT: Deployment environment
        BUDOBSERVE_OTLP_ENDPOINT / OTEL_EXPORTER_OTLP_ENDPOINT: OTLP endpoint
        BUDOBSERVE_BUDMETRICS_ENDPOINT: BudMetrics endpoint
        BUDOBSERVE_CONSOLE: Enable console exporter (true/false)
        BUDOBSERVE_SAMPLE_RATE / OTEL_TRACES_SAMPLER_ARG: Sample rate
"""

from budobserve._internal.config import GLOBAL_CONFIG, BudObserveConfig, configure
from budobserve._internal.main import BudObserve, get_default_instance
from budobserve._internal.version import __version__

# Global singleton instance - lazily created on first access
DEFAULT_INSTANCE = get_default_instance()

__all__ = [
    "DEFAULT_INSTANCE",
    "GLOBAL_CONFIG",
    "BudObserve",
    "BudObserveConfig",
    "__version__",
    "configure",
    "get_default_instance",
]
