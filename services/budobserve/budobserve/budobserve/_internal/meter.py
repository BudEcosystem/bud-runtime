"""Proxy MeterProvider for BudObserve SDK.

This module implements the proxy provider pattern for metrics.
Similar to ProxyTracerProvider, it wraps OTEL's MeterProvider.

Will be implemented in Phase 1 (Core OTEL Wrapper).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from opentelemetry.sdk.metrics import MeterProvider


class ProxyMeterProvider:
    """Proxy MeterProvider that wraps the real OTEL MeterProvider.

    This allows BudObserve to manage metrics collection with
    lazy initialization and runtime configuration.
    """

    def __init__(self) -> None:
        """Initialize proxy provider in unconfigured state."""
        self._real_provider: MeterProvider | None = None

    def set_provider(self, provider: MeterProvider) -> None:
        """Set the real underlying MeterProvider.

        Args:
            provider: The OTEL MeterProvider to delegate to.
        """
        self._real_provider = provider

    @property
    def is_configured(self) -> bool:
        """Check if a real provider has been set."""
        return self._real_provider is not None
