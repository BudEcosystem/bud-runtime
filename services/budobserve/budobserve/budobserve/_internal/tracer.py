"""Proxy TracerProvider for BudObserve SDK.

This module implements the proxy provider pattern from Logfire.
The proxy provider wraps OTEL's TracerProvider to allow:
- Lazy initialization (configure later)
- Runtime reconfiguration
- Multiple exporter support

Architecture:
    ProxyTracerProvider -> Real TracerProvider -> Exporters
                       └-> Fallback/NoOp when unconfigured
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from threading import Lock
from typing import TYPE_CHECKING, Any
from weakref import WeakKeyDictionary

from opentelemetry import context as otel_context
from opentelemetry.trace import (
    Link,
    NoOpTracer,
    Span,
    SpanKind,
    Tracer,
    TracerProvider,
)
from opentelemetry.trace import (
    NoOpTracerProvider as OTELNoOpTracerProvider,
)
from opentelemetry.util.types import Attributes

if TYPE_CHECKING:
    from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider


class NoOpTracerProvider(OTELNoOpTracerProvider):
    """NoOp TracerProvider that returns NoOp tracers.

    Used as the initial provider before configure() is called.
    """

    pass


class SuppressedTracer(NoOpTracer):
    """A tracer that creates no-op spans for suppressed scopes."""

    pass


class ProxyTracer(Tracer):
    """Proxy tracer that delegates to a real tracer.

    This allows the underlying tracer to be swapped at runtime
    when the provider is reconfigured.
    """

    def __init__(
        self,
        tracer: Tracer,
        instrumenting_module_name: str,
        provider: ProxyTracerProvider,
        is_span_tracer: bool = False,
    ) -> None:
        """Initialize proxy tracer.

        Args:
            tracer: The underlying tracer to delegate to.
            instrumenting_module_name: Name of the instrumenting module.
            provider: The parent ProxyTracerProvider.
            is_span_tracer: Whether this tracer is for explicit spans (vs logs).
        """
        self._tracer = tracer
        self._instrumenting_module_name = instrumenting_module_name
        self._provider = provider
        self._is_span_tracer = is_span_tracer

    @property
    def instrumenting_module_name(self) -> str:
        """Get the instrumenting module name."""
        return self._instrumenting_module_name

    @property
    def is_span_tracer(self) -> bool:
        """Check if this is a span tracer."""
        return self._is_span_tracer

    def set_tracer(self, tracer: Tracer) -> None:
        """Update the underlying tracer.

        Args:
            tracer: The new tracer to delegate to.
        """
        self._tracer = tracer

    def start_span(
        self,
        name: str,
        context: otel_context.Context | None = None,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: Attributes = None,
        links: Sequence[Link] | None = None,
        start_time: int | None = None,
        record_exception: bool = True,
        set_status_on_exception: bool = True,
    ) -> Span:
        """Start a new span.

        Delegates to the underlying tracer.
        """
        return self._tracer.start_span(
            name=name,
            context=context,
            kind=kind,
            attributes=attributes,
            links=links,
            start_time=start_time,
            record_exception=record_exception,
            set_status_on_exception=set_status_on_exception,
        )

    @contextmanager
    def start_as_current_span(
        self,
        name: str,
        context: otel_context.Context | None = None,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: Attributes = None,
        links: Sequence[Link] | None = None,
        start_time: int | None = None,
        record_exception: bool = True,
        set_status_on_exception: bool = True,
        end_on_exit: bool = True,
    ) -> Iterator[Span]:
        """Start a span and set it as the current span in context.

        Delegates to the underlying tracer.
        """
        with self._tracer.start_as_current_span(
            name=name,
            context=context,
            kind=kind,
            attributes=attributes,
            links=links,
            start_time=start_time,
            record_exception=record_exception,
            set_status_on_exception=set_status_on_exception,
            end_on_exit=end_on_exit,
        ) as span:
            yield span


class ProxyTracerProvider(TracerProvider):
    """Proxy TracerProvider that wraps the real OTEL TracerProvider.

    This allows BudObserve to:
    - Accept traces before configuration (queued or dropped)
    - Switch underlying provider at runtime
    - Add multiple exporters dynamically

    Following Logfire's architecture pattern with:
    - WeakKeyDictionary for tracer tracking (allows GC)
    - Lock for thread-safe provider swapping
    - Factory functions to recreate tracers after swap
    """

    def __init__(self, provider: TracerProvider | None = None) -> None:
        """Initialize proxy provider.

        Args:
            provider: Initial provider to wrap. Defaults to NoOpTracerProvider.
        """
        self._provider: TracerProvider = provider or NoOpTracerProvider()
        self._lock = Lock()
        # WeakKeyDictionary allows tracers to be garbage collected
        # Values are factory functions to recreate tracers after provider swap
        self._tracers: WeakKeyDictionary[ProxyTracer, Callable[[], Tracer]] = WeakKeyDictionary()
        self._suppressed_scopes: set[str] = set()

    @property
    def provider(self) -> TracerProvider:
        """Get the underlying provider."""
        return self._provider

    @property
    def is_configured(self) -> bool:
        """Check if a real provider has been set."""
        return not isinstance(self._provider, NoOpTracerProvider)

    def set_provider(self, provider: SDKTracerProvider) -> None:
        """Set the real underlying TracerProvider.

        This will update all existing proxy tracers to use the new provider.

        Args:
            provider: The OTEL TracerProvider to delegate to.
        """
        with self._lock:
            self._provider = provider
            # Update all existing tracers with new underlying tracers
            for proxy_tracer, factory in self._tracers.items():
                if proxy_tracer.instrumenting_module_name in self._suppressed_scopes:
                    proxy_tracer.set_tracer(SuppressedTracer())
                else:
                    proxy_tracer.set_tracer(factory())

    def get_tracer(
        self,
        instrumenting_module_name: str,
        instrumenting_library_version: str | None = None,
        schema_url: str | None = None,
        attributes: Attributes = None,
        *,
        is_span_tracer: bool = False,
    ) -> ProxyTracer:
        """Get a tracer from the underlying provider.

        Args:
            instrumenting_module_name: Name of the instrumenting module.
            instrumenting_library_version: Version of the instrumenting library.
            schema_url: Schema URL for the instrumentation.
            attributes: Additional attributes for the tracer.
            is_span_tracer: Whether this tracer is for explicit spans.

        Returns:
            A ProxyTracer instance that delegates to the real tracer.
        """
        with self._lock:
            # Factory function to create/recreate the underlying tracer
            def tracer_factory() -> Tracer:
                return self._provider.get_tracer(
                    instrumenting_module_name=instrumenting_module_name,
                    instrumenting_library_version=instrumenting_library_version,
                    schema_url=schema_url,
                    attributes=attributes,
                )

            # Check if scope is suppressed
            if instrumenting_module_name in self._suppressed_scopes:
                tracer = SuppressedTracer()
            else:
                tracer = tracer_factory()

            proxy_tracer = ProxyTracer(
                tracer=tracer,
                instrumenting_module_name=instrumenting_module_name,
                provider=self,
                is_span_tracer=is_span_tracer,
            )

            # Store factory for later recreation on provider swap
            self._tracers[proxy_tracer] = tracer_factory

            return proxy_tracer

    def suppress_scopes(self, *scopes: str) -> None:
        """Suppress tracing for the given module scopes.

        Suppressed scopes will return SuppressedTracer instances
        that create no-op spans.

        Args:
            *scopes: Module names to suppress.
        """
        with self._lock:
            self._suppressed_scopes.update(scopes)
            # Update existing tracers for these scopes
            for proxy_tracer in self._tracers:
                if proxy_tracer.instrumenting_module_name in scopes:
                    proxy_tracer.set_tracer(SuppressedTracer())

    def shutdown(self) -> None:
        """Shutdown the provider and all processors.

        Should be called when the application exits.
        """
        with self._lock:
            if hasattr(self._provider, "shutdown"):
                self._provider.shutdown()  # type: ignore[union-attr]

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Force flush all pending spans.

        Args:
            timeout_millis: Maximum time to wait for flush.

        Returns:
            True if flush succeeded, False otherwise.
        """
        with self._lock:
            if hasattr(self._provider, "force_flush"):
                return self._provider.force_flush(timeout_millis)  # type: ignore[union-attr]
            return True

    def add_span_processor(self, span_processor: Any) -> None:
        """Add a span processor to the underlying provider.

        Args:
            span_processor: The span processor to add.
        """
        with self._lock:
            if hasattr(self._provider, "add_span_processor"):
                self._provider.add_span_processor(span_processor)  # type: ignore[union-attr]
