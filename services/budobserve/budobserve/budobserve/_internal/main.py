"""BudObserve main class - the singleton entry point.

This module contains the BudObserve class which is the main entry point
for the SDK. It manages initialization, configuration, and provides
the high-level API for creating spans, metrics, and logs.

Architecture:
- Singleton pattern (like Logfire)
- Lazy initialization of OTEL providers
- Proxy providers for runtime flexibility
"""

from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING, Literal

from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.trace.sampling import ParentBasedTraceIdRatio

from budobserve._internal.config import GLOBAL_CONFIG, BudObserveConfig
from budobserve._internal.logger import ProxyLoggerProvider
from budobserve._internal.meter import ProxyMeterProvider
from budobserve._internal.tracer import ProxyTracerProvider
from budobserve._internal.version import __version__

if TYPE_CHECKING:
    from budobserve._internal.tracer import ProxyTracer


class BudObserve:
    """Main BudObserve class - singleton entry point for the SDK.

    This class manages:
    - SDK initialization and configuration
    - Proxy providers for tracing, metrics, and logging
    - High-level API for creating spans and recording metrics

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
        self._tracer_provider: ProxyTracerProvider | None = None
        self._meter_provider: ProxyMeterProvider | None = None
        self._logger_provider: ProxyLoggerProvider | None = None
        self._configured = False

    @property
    def config(self) -> BudObserveConfig:
        """Get the current configuration."""
        return self._config

    @property
    def is_configured(self) -> bool:
        """Check if SDK has been configured."""
        return self._configured

    @cached_property
    def tracer_provider(self) -> ProxyTracerProvider:
        """Get the proxy tracer provider.

        Creates the provider lazily on first access.
        """
        if self._tracer_provider is None:
            self._tracer_provider = ProxyTracerProvider()
        return self._tracer_provider

    @cached_property
    def meter_provider(self) -> ProxyMeterProvider:
        """Get the proxy meter provider.

        Creates the provider lazily on first access.
        """
        if self._meter_provider is None:
            self._meter_provider = ProxyMeterProvider()
        return self._meter_provider

    @cached_property
    def logger_provider(self) -> ProxyLoggerProvider:
        """Get the proxy logger provider.

        Creates the provider lazily on first access.
        """
        if self._logger_provider is None:
            self._logger_provider = ProxyLoggerProvider()
        return self._logger_provider

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

    def configure(
        self,
        *,
        service_name: str | None = None,
        service_version: str | None = None,
        environment: str | None = None,
        otlp_endpoint: str | None = None,
        budmetrics_endpoint: str | None = None,
        console: bool | None = None,
        console_colors: Literal["auto", "always", "never"] | None = None,
        sample_rate: float | None = None,
    ) -> BudObserve:
        """Configure the BudObserve SDK.

        This method initializes the SDK with the given configuration.
        Explicit arguments override environment variables and defaults.

        Args:
            service_name: Name of the service for telemetry.
            service_version: Version of the service.
            environment: Deployment environment (dev, staging, prod).
            otlp_endpoint: OTLP exporter endpoint URL.
            budmetrics_endpoint: BudMetrics endpoint URL.
            console: Enable console exporter for debugging.
            console_colors: Console color mode.
            sample_rate: Trace sampling rate (0.0 to 1.0).

        Returns:
            This BudObserve instance for chaining.
        """
        # Merge explicit config with existing config
        self._config = self._config.merge_with(
            service_name=service_name,
            service_version=service_version,
            environment=environment,
            otlp_endpoint=otlp_endpoint,
            budmetrics_endpoint=budmetrics_endpoint,
            console_enabled=console,
            console_colors=console_colors,
            sample_rate=sample_rate,
        )

        # Initialize the SDK
        self._initialize()

        return self

    def _initialize(self) -> None:
        """Initialize the OTEL providers with current configuration."""
        # Create resource from config
        resource = self._config.create_resource()

        # Create sampler based on sample rate
        sampler = ParentBasedTraceIdRatio(self._config.sample_rate)

        # Create the real SDK TracerProvider
        sdk_tracer_provider = SDKTracerProvider(
            sampler=sampler,
            resource=resource,
        )

        # Add console exporter if enabled
        if self._config.console_enabled:
            console_exporter = ConsoleSpanExporter()
            sdk_tracer_provider.add_span_processor(BatchSpanProcessor(console_exporter))

        # Set the real provider on our proxy
        self.tracer_provider.set_provider(sdk_tracer_provider)

        # Set as global OTEL provider
        otel_trace.set_tracer_provider(self.tracer_provider)

        # Mark as configured
        self._configured = True
        self._config.mark_initialized()

    def shutdown(self) -> None:
        """Shutdown the SDK and flush all pending telemetry.

        Should be called when the application exits.
        """
        if self._tracer_provider:
            self._tracer_provider.shutdown()
        if self._meter_provider:
            self._meter_provider.shutdown()
        if self._logger_provider:
            self._logger_provider.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Force flush all pending telemetry.

        Args:
            timeout_millis: Maximum time to wait for flush.

        Returns:
            True if flush succeeded, False otherwise.
        """
        success = True
        if self._tracer_provider:
            success = success and self._tracer_provider.force_flush(timeout_millis)
        if self._meter_provider:
            success = success and self._meter_provider.force_flush(timeout_millis)
        if self._logger_provider:
            success = success and self._logger_provider.force_flush(timeout_millis)
        return success


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


def configure(
    *,
    service_name: str | None = None,
    service_version: str | None = None,
    environment: str | None = None,
    otlp_endpoint: str | None = None,
    budmetrics_endpoint: str | None = None,
    console: bool | None = None,
    console_colors: Literal["auto", "always", "never"] | None = None,
    sample_rate: float | None = None,
) -> BudObserve:
    """Configure the global BudObserve SDK instance.

    This is the primary way to initialize BudObserve.

    Args:
        service_name: Name of the service for telemetry.
        service_version: Version of the service.
        environment: Deployment environment (dev, staging, prod).
        otlp_endpoint: OTLP exporter endpoint URL.
        budmetrics_endpoint: BudMetrics endpoint URL.
        console: Enable console exporter for debugging.
        console_colors: Console color mode.
        sample_rate: Trace sampling rate (0.0 to 1.0).

    Returns:
        The configured BudObserve instance.

    Example:
        >>> import budobserve
        >>> budobserve.configure(
        ...     service_name="my-service",
        ...     environment="production",
        ...     console=True,
        ... )
    """
    return get_default_instance().configure(
        service_name=service_name,
        service_version=service_version,
        environment=environment,
        otlp_endpoint=otlp_endpoint,
        budmetrics_endpoint=budmetrics_endpoint,
        console=console,
        console_colors=console_colors,
        sample_rate=sample_rate,
    )
