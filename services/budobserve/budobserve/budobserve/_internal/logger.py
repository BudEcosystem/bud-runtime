"""Proxy LoggerProvider for BudObserve SDK.

This module implements the proxy provider pattern for logging.
Similar to ProxyTracerProvider, it wraps OTEL's LoggerProvider.

Will be implemented in Phase 1 (Core OTEL Wrapper).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from opentelemetry.sdk._logs import LoggerProvider


class ProxyLoggerProvider:
    """Proxy LoggerProvider that wraps the real OTEL LoggerProvider.

    This allows BudObserve to manage log collection with
    lazy initialization and runtime configuration.
    """

    def __init__(self) -> None:
        """Initialize proxy provider in unconfigured state."""
        self._real_provider: LoggerProvider | None = None

    def set_provider(self, provider: LoggerProvider) -> None:
        """Set the real underlying LoggerProvider.

        Args:
            provider: The OTEL LoggerProvider to delegate to.
        """
        self._real_provider = provider

    @property
    def is_configured(self) -> bool:
        """Check if a real provider has been set."""
        return self._real_provider is not None
