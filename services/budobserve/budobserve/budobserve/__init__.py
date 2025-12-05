"""BudObserve - Observability SDK for Bud-Stack platform.

Built on OpenTelemetry, BudObserve provides a high-level API for tracing,
metrics, and logging with automatic instrumentation for common frameworks.

Example:
    >>> import budobserve
    >>> budobserve.configure(service_name="my-service")
    >>> with budobserve.span("processing request"):
    ...     # your code here
    ...     pass

Public API will be exported here in future phases.
"""

from budobserve._internal.version import __version__

__all__ = [
    "__version__",
]
