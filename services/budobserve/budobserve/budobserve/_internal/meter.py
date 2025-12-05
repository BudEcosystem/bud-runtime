"""Proxy MeterProvider for BudObserve SDK.

This module implements the proxy provider pattern for metrics.
Similar to ProxyTracerProvider, it wraps OTEL's MeterProvider to allow:
- Lazy initialization (configure later)
- Runtime reconfiguration
- Multiple exporter support

Architecture:
    ProxyMeterProvider -> Real MeterProvider -> Exporters
                      └-> Fallback/NoOp when unconfigured
"""

from __future__ import annotations

from collections.abc import Callable
from threading import Lock
from typing import TYPE_CHECKING, Any
from weakref import WeakSet

from opentelemetry.metrics import (
    Meter,
    MeterProvider,
    NoOpMeter,
)
from opentelemetry.metrics import (
    NoOpMeterProvider as OTELNoOpMeterProvider,
)

if TYPE_CHECKING:
    from opentelemetry.sdk.metrics import MeterProvider as SDKMeterProvider


class NoOpMeterProvider(OTELNoOpMeterProvider):
    """NoOp MeterProvider that returns NoOp meters.

    Used as the initial provider before configure() is called.
    """

    pass


class SuppressedMeter(NoOpMeter):
    """A meter that creates no-op instruments for suppressed scopes."""

    pass


class ProxyMeter(Meter):
    """Proxy meter that delegates to a real meter.

    This allows the underlying meter to be swapped at runtime
    when the provider is reconfigured.
    """

    def __init__(
        self,
        meter: Meter,
        name: str,
        provider: ProxyMeterProvider,
    ) -> None:
        """Initialize proxy meter.

        Args:
            meter: The underlying meter to delegate to.
            name: Name of the meter.
            provider: The parent ProxyMeterProvider.
        """
        self._meter = meter
        self._name = name
        self._provider = provider

    @property
    def name(self) -> str:
        """Get the meter name."""
        return self._name

    def set_meter(self, meter: Meter) -> None:
        """Update the underlying meter.

        Args:
            meter: The new meter to delegate to.
        """
        self._meter = meter

    def create_counter(
        self,
        name: str,
        unit: str = "",
        description: str = "",
    ) -> Any:
        """Create a counter instrument."""
        return self._meter.create_counter(name, unit=unit, description=description)

    def create_up_down_counter(
        self,
        name: str,
        unit: str = "",
        description: str = "",
    ) -> Any:
        """Create an up-down counter instrument."""
        return self._meter.create_up_down_counter(name, unit=unit, description=description)

    def create_histogram(
        self,
        name: str,
        unit: str = "",
        description: str = "",
    ) -> Any:
        """Create a histogram instrument."""
        return self._meter.create_histogram(name, unit=unit, description=description)

    def create_observable_counter(
        self,
        name: str,
        callbacks: Any = None,
        unit: str = "",
        description: str = "",
    ) -> Any:
        """Create an observable counter instrument."""
        return self._meter.create_observable_counter(name, callbacks=callbacks, unit=unit, description=description)

    def create_observable_up_down_counter(
        self,
        name: str,
        callbacks: Any = None,
        unit: str = "",
        description: str = "",
    ) -> Any:
        """Create an observable up-down counter instrument."""
        return self._meter.create_observable_up_down_counter(
            name, callbacks=callbacks, unit=unit, description=description
        )

    def create_observable_gauge(
        self,
        name: str,
        callbacks: Any = None,
        unit: str = "",
        description: str = "",
    ) -> Any:
        """Create an observable gauge instrument."""
        return self._meter.create_observable_gauge(name, callbacks=callbacks, unit=unit, description=description)

    def create_gauge(
        self,
        name: str,
        unit: str = "",
        description: str = "",
    ) -> Any:
        """Create a gauge instrument."""
        return self._meter.create_gauge(name, unit=unit, description=description)


class ProxyMeterProvider(MeterProvider):
    """Proxy MeterProvider that wraps the real OTEL MeterProvider.

    This allows BudObserve to:
    - Accept metrics before configuration
    - Switch underlying provider at runtime
    - Add multiple exporters dynamically

    Following Logfire's architecture pattern with:
    - WeakSet for meter tracking (allows GC)
    - Lock for thread-safe provider swapping
    """

    def __init__(self, provider: MeterProvider | None = None) -> None:
        """Initialize proxy provider.

        Args:
            provider: Initial provider to wrap. Defaults to NoOpMeterProvider.
        """
        self._provider: MeterProvider = provider or NoOpMeterProvider()
        self._lock = Lock()
        # WeakSet allows meters to be garbage collected
        self._meters: WeakSet[ProxyMeter] = WeakSet()
        # Store factories to recreate meters after provider swap
        self._meter_factories: dict[str, Callable[[], Meter]] = {}
        self._suppressed_scopes: set[str] = set()

    @property
    def provider(self) -> MeterProvider:
        """Get the underlying provider."""
        return self._provider

    @property
    def is_configured(self) -> bool:
        """Check if a real provider has been set."""
        return not isinstance(self._provider, NoOpMeterProvider)

    def set_provider(self, provider: SDKMeterProvider) -> None:
        """Set the real underlying MeterProvider.

        This will update all existing proxy meters to use the new provider.

        Args:
            provider: The OTEL MeterProvider to delegate to.
        """
        with self._lock:
            self._provider = provider
            # Update all existing meters with new underlying meters
            for proxy_meter in self._meters:
                if proxy_meter.name in self._suppressed_scopes:
                    proxy_meter.set_meter(SuppressedMeter(proxy_meter.name))
                elif proxy_meter.name in self._meter_factories:
                    proxy_meter.set_meter(self._meter_factories[proxy_meter.name]())

    def get_meter(
        self,
        name: str,
        version: str | None = None,
        schema_url: str | None = None,
    ) -> ProxyMeter:
        """Get a meter from the underlying provider.

        Args:
            name: Name of the meter.
            version: Version of the meter.
            schema_url: Schema URL for the meter.

        Returns:
            A ProxyMeter instance that delegates to the real meter.
        """
        with self._lock:
            # Factory function to create/recreate the underlying meter
            def meter_factory() -> Meter:
                return self._provider.get_meter(
                    name=name,
                    version=version,
                    schema_url=schema_url,
                )

            # Check if scope is suppressed
            if name in self._suppressed_scopes:
                meter = SuppressedMeter(name)
            else:
                meter = meter_factory()

            proxy_meter = ProxyMeter(
                meter=meter,
                name=name,
                provider=self,
            )

            # Store factory and meter reference
            self._meter_factories[name] = meter_factory
            self._meters.add(proxy_meter)

            return proxy_meter

    def suppress_scopes(self, *scopes: str) -> None:
        """Suppress metrics for the given scopes.

        Suppressed scopes will return SuppressedMeter instances.

        Args:
            *scopes: Names to suppress.
        """
        with self._lock:
            self._suppressed_scopes.update(scopes)
            # Update existing meters for these scopes
            for proxy_meter in self._meters:
                if proxy_meter.name in scopes:
                    proxy_meter.set_meter(SuppressedMeter(proxy_meter.name))

    def shutdown(self, timeout_millis: float = 30000) -> None:
        """Shutdown the provider.

        Args:
            timeout_millis: Maximum time to wait for shutdown.
        """
        with self._lock:
            if hasattr(self._provider, "shutdown"):
                self._provider.shutdown(timeout_millis)  # type: ignore[union-attr]

    def force_flush(self, timeout_millis: float = 30000) -> bool:
        """Force flush all pending metrics.

        Args:
            timeout_millis: Maximum time to wait for flush.

        Returns:
            True if flush succeeded, False otherwise.
        """
        with self._lock:
            if hasattr(self._provider, "force_flush"):
                return self._provider.force_flush(timeout_millis)  # type: ignore[union-attr]
            return True
