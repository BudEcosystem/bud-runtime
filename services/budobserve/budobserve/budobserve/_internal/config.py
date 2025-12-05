"""Configuration management for BudObserve SDK.

This module handles SDK configuration from multiple sources:
- Environment variables (BUDOBSERVE_*, OTEL_*)
- Programmatic configuration via configure()
- Default values

Configuration follows a priority order:
1. Explicit programmatic configuration (highest)
2. Environment variables
3. Default values (lowest)

Following Logfire's architecture, this module owns:
- BudObserveConfig class with settings AND provider management
- configure() module-level function as the main SDK entry point
- _initialize() method for OTEL provider setup
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from threading import RLock
from typing import TYPE_CHECKING, Literal
from uuid import uuid4

from opentelemetry import trace as otel_trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.trace.sampling import ParentBasedTraceIdRatio

from budobserve._internal.logger import ProxyLoggerProvider
from budobserve._internal.meter import ProxyMeterProvider
from budobserve._internal.tracer import ProxyTracerProvider
from budobserve._internal.version import __version__

if TYPE_CHECKING:
    from budobserve._internal.main import BudObserve


def _get_env(
    *keys: str,
    default: str | None = None,
) -> str | None:
    """Get the first non-empty environment variable from the given keys.

    Args:
        *keys: Environment variable names to check in order.
        default: Default value if none found.

    Returns:
        The first non-empty value found, or the default.
    """
    for key in keys:
        value = os.environ.get(key)
        if value:
            return value
    return default


def _get_env_bool(
    *keys: str,
    default: bool = False,
) -> bool:
    """Get a boolean from environment variables.

    Args:
        *keys: Environment variable names to check in order.
        default: Default value if none found.

    Returns:
        True if value is 'true', '1', 'yes'; False otherwise.
    """
    value = _get_env(*keys)
    if value is None:
        return default
    return value.lower() in ("true", "1", "yes")


def _get_env_float(
    *keys: str,
    default: float = 1.0,
) -> float:
    """Get a float from environment variables.

    Args:
        *keys: Environment variable names to check in order.
        default: Default value if none found or invalid.

    Returns:
        The float value, or default if not found/invalid.
    """
    value = _get_env(*keys)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


@dataclass
class BudObserveConfig:
    """Configuration for BudObserve SDK.

    Attributes:
        service_name: Name of the service for telemetry identification.
        service_version: Version of the service.
        environment: Deployment environment (dev, staging, prod).
        otlp_endpoint: OTLP exporter endpoint URL.
        budmetrics_endpoint: BudMetrics ClickHouse endpoint URL.
        console_enabled: Enable console exporter for debugging.
        console_colors: Console color mode.
        sample_rate: Trace sampling rate (0.0 to 1.0).
        scrub_patterns: Patterns for sensitive data scrubbing.
    """

    # Core settings
    service_name: str = "unknown-service"
    service_version: str | None = None
    environment: str | None = None

    # Backend settings
    otlp_endpoint: str | None = None
    budmetrics_endpoint: str | None = None

    # Console settings
    console_enabled: bool = False
    console_colors: Literal["auto", "always", "never"] = "auto"

    # Sampling
    sample_rate: float = 1.0

    # Scrubbing
    scrub_patterns: list[str] = field(default_factory=list)

    # Internal state (not part of config comparison)
    _initialized: bool = field(default=False, repr=False, compare=False)
    _lock: RLock = field(default_factory=RLock, repr=False, compare=False)
    _instance_id: str = field(default_factory=lambda: uuid4().hex, repr=False)

    # Provider references (owned by config, following Logfire pattern)
    _tracer_provider: ProxyTracerProvider | None = field(default=None, repr=False, compare=False)
    _meter_provider: ProxyMeterProvider | None = field(default=None, repr=False, compare=False)
    _logger_provider: ProxyLoggerProvider | None = field(default=None, repr=False, compare=False)

    @classmethod
    def from_environment(cls) -> BudObserveConfig:
        """Create configuration from environment variables.

        Environment variables (in priority order):
            BUDOBSERVE_SERVICE_NAME / OTEL_SERVICE_NAME: Service name
            BUDOBSERVE_SERVICE_VERSION / OTEL_SERVICE_VERSION: Service version
            BUDOBSERVE_ENVIRONMENT: Deployment environment
            BUDOBSERVE_OTLP_ENDPOINT / OTEL_EXPORTER_OTLP_ENDPOINT: OTLP endpoint
            BUDOBSERVE_BUDMETRICS_ENDPOINT: BudMetrics endpoint
            BUDOBSERVE_CONSOLE: Enable console exporter (true/false)
            BUDOBSERVE_CONSOLE_COLORS: Console color mode (auto/always/never)
            BUDOBSERVE_SAMPLE_RATE / OTEL_TRACES_SAMPLER_ARG: Sample rate

        Returns:
            A new BudObserveConfig populated from environment variables.
        """
        # Get console colors with validation
        console_colors_raw = _get_env("BUDOBSERVE_CONSOLE_COLORS", default="auto")
        console_colors: Literal["auto", "always", "never"] = "auto"
        if console_colors_raw in ("auto", "always", "never"):
            console_colors = console_colors_raw  # type: ignore[assignment]

        return cls(
            service_name=_get_env(
                "BUDOBSERVE_SERVICE_NAME",
                "OTEL_SERVICE_NAME",
                default="unknown-service",
            )
            or "unknown-service",
            service_version=_get_env(
                "BUDOBSERVE_SERVICE_VERSION",
                "OTEL_SERVICE_VERSION",
            ),
            environment=_get_env("BUDOBSERVE_ENVIRONMENT"),
            otlp_endpoint=_get_env(
                "BUDOBSERVE_OTLP_ENDPOINT",
                "OTEL_EXPORTER_OTLP_ENDPOINT",
            ),
            budmetrics_endpoint=_get_env("BUDOBSERVE_BUDMETRICS_ENDPOINT"),
            console_enabled=_get_env_bool("BUDOBSERVE_CONSOLE", default=False),
            console_colors=console_colors,
            sample_rate=_get_env_float(
                "BUDOBSERVE_SAMPLE_RATE",
                "OTEL_TRACES_SAMPLER_ARG",
                default=1.0,
            ),
        )

    def merge_with(
        self,
        *,
        service_name: str | None = None,
        service_version: str | None = None,
        environment: str | None = None,
        otlp_endpoint: str | None = None,
        budmetrics_endpoint: str | None = None,
        console_enabled: bool | None = None,
        console_colors: Literal["auto", "always", "never"] | None = None,
        sample_rate: float | None = None,
        scrub_patterns: list[str] | None = None,
    ) -> BudObserveConfig:
        """Create a new config by merging explicit values with this config.

        Explicit values (non-None) override existing values.

        Args:
            service_name: Override service name.
            service_version: Override service version.
            environment: Override environment.
            otlp_endpoint: Override OTLP endpoint.
            budmetrics_endpoint: Override BudMetrics endpoint.
            console_enabled: Override console enabled.
            console_colors: Override console colors.
            sample_rate: Override sample rate.
            scrub_patterns: Override scrub patterns.

        Returns:
            A new BudObserveConfig with merged values.
        """
        return BudObserveConfig(
            service_name=service_name if service_name is not None else self.service_name,
            service_version=service_version if service_version is not None else self.service_version,
            environment=environment if environment is not None else self.environment,
            otlp_endpoint=otlp_endpoint if otlp_endpoint is not None else self.otlp_endpoint,
            budmetrics_endpoint=budmetrics_endpoint if budmetrics_endpoint is not None else self.budmetrics_endpoint,
            console_enabled=console_enabled if console_enabled is not None else self.console_enabled,
            console_colors=console_colors if console_colors is not None else self.console_colors,
            sample_rate=sample_rate if sample_rate is not None else self.sample_rate,
            scrub_patterns=scrub_patterns if scrub_patterns is not None else self.scrub_patterns,
        )

    def create_resource(self) -> Resource:
        """Create an OTEL Resource from this configuration.

        Returns:
            A Resource with service attributes.
        """
        attributes: dict[str, str | int] = {
            "service.name": self.service_name,
            "service.instance.id": self._instance_id,
            "telemetry.sdk.name": "budobserve",
            "telemetry.sdk.version": __version__,
            "telemetry.sdk.language": "python",
            "process.pid": os.getpid(),
        }

        if self.service_version:
            attributes["service.version"] = self.service_version

        if self.environment:
            attributes["deployment.environment.name"] = self.environment

        return Resource.create(attributes)

    @property
    def is_initialized(self) -> bool:
        """Check if configuration has been initialized."""
        return self._initialized

    @property
    def tracer_provider(self) -> ProxyTracerProvider:
        """Get the proxy tracer provider.

        Creates the provider lazily on first access.
        """
        if self._tracer_provider is None:
            self._tracer_provider = ProxyTracerProvider()
        return self._tracer_provider

    @property
    def meter_provider(self) -> ProxyMeterProvider:
        """Get the proxy meter provider.

        Creates the provider lazily on first access.
        """
        if self._meter_provider is None:
            self._meter_provider = ProxyMeterProvider()
        return self._meter_provider

    @property
    def logger_provider(self) -> ProxyLoggerProvider:
        """Get the proxy logger provider.

        Creates the provider lazily on first access.
        """
        if self._logger_provider is None:
            self._logger_provider = ProxyLoggerProvider()
        return self._logger_provider

    def configure(
        self,
        *,
        service_name: str | None = None,
        service_version: str | None = None,
        environment: str | None = None,
        otlp_endpoint: str | None = None,
        budmetrics_endpoint: str | None = None,
        console_enabled: bool | None = None,
        console_colors: Literal["auto", "always", "never"] | None = None,
        sample_rate: float | None = None,
    ) -> None:
        """Configure the SDK with the given settings.

        This method updates configuration and initializes OTEL providers.
        Thread-safe via internal lock.

        Args:
            service_name: Name of the service for telemetry.
            service_version: Version of the service.
            environment: Deployment environment (dev, staging, prod).
            otlp_endpoint: OTLP exporter endpoint URL.
            budmetrics_endpoint: BudMetrics endpoint URL.
            console_enabled: Enable console exporter for debugging.
            console_colors: Console color mode.
            sample_rate: Trace sampling rate (0.0 to 1.0).
        """
        with self._lock:
            # Update settings in place (following Logfire pattern)
            if service_name is not None:
                self.service_name = service_name
            if service_version is not None:
                self.service_version = service_version
            if environment is not None:
                self.environment = environment
            if otlp_endpoint is not None:
                self.otlp_endpoint = otlp_endpoint
            if budmetrics_endpoint is not None:
                self.budmetrics_endpoint = budmetrics_endpoint
            if console_enabled is not None:
                self.console_enabled = console_enabled
            if console_colors is not None:
                self.console_colors = console_colors
            if sample_rate is not None:
                self.sample_rate = sample_rate

            # Initialize providers
            self._initialize()

    def _initialize(self) -> None:
        """Initialize the OTEL providers with current configuration.

        Creates SDK providers and sets them on the proxy providers.
        """
        # Create resource from config
        resource = self.create_resource()

        # Create sampler based on sample rate
        sampler = ParentBasedTraceIdRatio(self.sample_rate)

        # Create the real SDK TracerProvider
        sdk_tracer_provider = SDKTracerProvider(
            sampler=sampler,
            resource=resource,
        )

        # Add console exporter if enabled
        if self.console_enabled:
            console_exporter = ConsoleSpanExporter()
            sdk_tracer_provider.add_span_processor(BatchSpanProcessor(console_exporter))

        # Set the real provider on our proxy
        self.tracer_provider.set_provider(sdk_tracer_provider)

        # Set as global OTEL provider
        otel_trace.set_tracer_provider(self.tracer_provider)

        # Mark as initialized
        self._initialized = True

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


# Global configuration singleton
# This is created at module load with environment defaults
GLOBAL_CONFIG = BudObserveConfig.from_environment()


def get_default_config() -> BudObserveConfig:
    """Get the global default configuration.

    Returns:
        The global BudObserveConfig instance.
    """
    return GLOBAL_CONFIG


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
    # Import here to avoid circular dependency
    from budobserve._internal.main import get_default_instance

    # Configure the global config
    GLOBAL_CONFIG.configure(
        service_name=service_name,
        service_version=service_version,
        environment=environment,
        otlp_endpoint=otlp_endpoint,
        budmetrics_endpoint=budmetrics_endpoint,
        console_enabled=console,
        console_colors=console_colors,
        sample_rate=sample_rate,
    )

    # Return the default BudObserve instance
    return get_default_instance()
