"""Proxy TracerProvider for BudObserve SDK.

This module implements the proxy provider pattern from Logfire.
The proxy provider wraps OTEL's TracerProvider to allow:
- Lazy initialization (configure later)
- Runtime reconfiguration
- Multiple exporter support

Architecture:
    ProxyTracerProvider -> Real TracerProvider -> Exporters
                       └-> Fallback/NoOp when unconfigured

Will be implemented in Phase 1 (Core OTEL Wrapper).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.trace import Tracer


class ProxyTracerProvider:
    """Proxy TracerProvider that wraps the real OTEL TracerProvider.

    This allows BudObserve to:
    - Accept traces before configuration (queued or dropped)
    - Switch underlying provider at runtime
    - Add multiple exporters dynamically

    Following Logfire's architecture pattern.
    """

    def __init__(self) -> None:
        """Initialize proxy provider in unconfigured state."""
        self._real_provider: TracerProvider | None = None

    def set_provider(self, provider: TracerProvider) -> None:
        """Set the real underlying TracerProvider.

        Args:
            provider: The OTEL TracerProvider to delegate to.
        """
        self._real_provider = provider

    def get_tracer(
        self,
        instrumenting_module_name: str,
        instrumenting_library_version: str | None = None,
        schema_url: str | None = None,
    ) -> Tracer:
        """Get a tracer from the underlying provider.

        Args:
            instrumenting_module_name: Name of the instrumenting module.
            instrumenting_library_version: Version of the instrumenting library.
            schema_url: Schema URL for the instrumentation.

        Returns:
            A Tracer instance (or NoOp tracer if unconfigured).
        """
        # Placeholder - will be implemented in Phase 1
        raise NotImplementedError("ProxyTracerProvider.get_tracer not implemented")

    @property
    def is_configured(self) -> bool:
        """Check if a real provider has been set."""
        return self._real_provider is not None
