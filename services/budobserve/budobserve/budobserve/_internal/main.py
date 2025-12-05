"""BudObserve main class - the singleton entry point.

This module contains the BudObserve class which is the main entry point
for the SDK. It provides the high-level API for creating spans, metrics,
and logs.

Architecture (following Logfire pattern):
- BudObserve class delegates provider management to BudObserveConfig
- Config module owns initialization and provider lifecycle
- This class is a thin wrapper for user-facing API
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from budobserve._internal.config import GLOBAL_CONFIG, BudObserveConfig
from budobserve._internal.logger import ProxyLoggerProvider
from budobserve._internal.meter import ProxyMeterProvider
from budobserve._internal.tracer import ProxyTracerProvider
from budobserve._internal.version import __version__

if TYPE_CHECKING:
    from budobserve._internal.tracer import ProxyTracer


class BudObserve:
    """Main BudObserve class - singleton entry point for the SDK.

    This class provides:
    - Access to proxy providers (delegated to config)
    - High-level API for creating spans and recording metrics

    Note: Configuration and initialization are handled by BudObserveConfig.
    Use budobserve.configure() to initialize the SDK.

    Example:
        >>> import budobserve
        >>> budobserve.configure(service_name="my-service")
        >>> with budobserve.span("operation"):
        ...     pass
    """

    def __init__(self, config: BudObserveConfig | None = None) -> None:
        """Initialize BudObserve instance.

        Args:
            config: Configuration to use. Defaults to GLOBAL_CONFIG.
        """
        self._config = config or GLOBAL_CONFIG

    @property
    def config(self) -> BudObserveConfig:
        """Get the current configuration."""
        return self._config

    @property
    def is_configured(self) -> bool:
        """Check if SDK has been configured."""
        return self._config.is_initialized

    @property
    def tracer_provider(self) -> ProxyTracerProvider:
        """Get the proxy tracer provider (delegated to config)."""
        return self._config.tracer_provider

    @property
    def meter_provider(self) -> ProxyMeterProvider:
        """Get the proxy meter provider (delegated to config)."""
        return self._config.meter_provider

    @property
    def logger_provider(self) -> ProxyLoggerProvider:
        """Get the proxy logger provider (delegated to config)."""
        return self._config.logger_provider

    def _get_tracer(self, is_span_tracer: bool = False) -> ProxyTracer:
        """Get a tracer for internal use.

        Args:
            is_span_tracer: Whether this tracer is for explicit spans.

        Returns:
            A ProxyTracer instance.
        """
        return self.tracer_provider.get_tracer(
            instrumenting_module_name="budobserve",
            instrumenting_library_version=__version__,
            is_span_tracer=is_span_tracer,
        )

    def shutdown(self) -> None:
        """Shutdown the SDK and flush all pending telemetry.

        Should be called when the application exits.
        """
        self._config.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Force flush all pending telemetry.

        Args:
            timeout_millis: Maximum time to wait for flush.

        Returns:
            True if flush succeeded, False otherwise.
        """
        return self._config.force_flush(timeout_millis)


# Global singleton instance
_default_instance: BudObserve | None = None


def get_default_instance() -> BudObserve:
    """Get the global default BudObserve instance.

    Creates the instance lazily on first access.

    Returns:
        The global BudObserve instance.
    """
    global _default_instance
    if _default_instance is None:
        _default_instance = BudObserve(config=GLOBAL_CONFIG)
    return _default_instance
