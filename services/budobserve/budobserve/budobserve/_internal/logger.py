"""Proxy LoggerProvider for BudObserve SDK.

This module implements the proxy provider pattern for logging.
Similar to ProxyTracerProvider, it wraps OTEL's LoggerProvider to allow:
- Lazy initialization (configure later)
- Runtime reconfiguration
- Multiple exporter support

Architecture:
    ProxyLoggerProvider -> Real LoggerProvider -> Exporters
                       └-> Fallback/NoOp when unconfigured
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from threading import Lock
from typing import TYPE_CHECKING, Any
from weakref import WeakSet

from opentelemetry._logs import (
    Logger,
    LoggerProvider,
    NoOpLogger,
)
from opentelemetry._logs import (
    NoOpLoggerProvider as OTELNoOpLoggerProvider,
)

if TYPE_CHECKING:
    from opentelemetry.sdk._logs import LoggerProvider as SDKLoggerProvider


class NoOpLoggerProvider(OTELNoOpLoggerProvider):
    """NoOp LoggerProvider that returns NoOp loggers.

    Used as the initial provider before configure() is called.
    """

    pass


class SuppressedLogger(NoOpLogger):
    """A logger that discards all log records for suppressed scopes."""

    pass


class ProxyLogger(Logger):
    """Proxy logger that delegates to a real logger.

    This allows the underlying logger to be swapped at runtime
    when the provider is reconfigured.
    """

    def __init__(
        self,
        logger: Logger,
        name: str,
        provider: ProxyLoggerProvider,
    ) -> None:
        """Initialize proxy logger.

        Args:
            logger: The underlying logger to delegate to.
            name: Name of the logger.
            provider: The parent ProxyLoggerProvider.
        """
        self._logger = logger
        self._name = name
        self._provider = provider

    @property
    def name(self) -> str:
        """Get the logger name."""
        return self._name

    def set_logger(self, logger: Logger) -> None:
        """Update the underlying logger.

        Args:
            logger: The new logger to delegate to.
        """
        self._logger = logger

    def emit(self, record: Any) -> None:
        """Emit a log record.

        Args:
            record: The log record to emit.
        """
        self._logger.emit(record)


class ProxyLoggerProvider(LoggerProvider):
    """Proxy LoggerProvider that wraps the real OTEL LoggerProvider.

    This allows BudObserve to:
    - Accept logs before configuration
    - Switch underlying provider at runtime
    - Add multiple exporters dynamically
    - Filter logs by minimum level

    Following Logfire's architecture pattern with:
    - WeakSet for logger tracking (allows GC)
    - Lock for thread-safe provider swapping
    """

    def __init__(
        self,
        provider: LoggerProvider | None = None,
        min_level: int = logging.NOTSET,
    ) -> None:
        """Initialize proxy provider.

        Args:
            provider: Initial provider to wrap. Defaults to NoOpLoggerProvider.
            min_level: Minimum log level to record. Defaults to NOTSET (all).
        """
        self._provider: LoggerProvider = provider or NoOpLoggerProvider()
        self._lock = Lock()
        self._min_level = min_level
        # WeakSet allows loggers to be garbage collected
        self._loggers: WeakSet[ProxyLogger] = WeakSet()
        # Store factories to recreate loggers after provider swap
        self._logger_factories: dict[str, Callable[[], Logger]] = {}
        self._suppressed_scopes: set[str] = set()

    @property
    def provider(self) -> LoggerProvider:
        """Get the underlying provider."""
        return self._provider

    @property
    def is_configured(self) -> bool:
        """Check if a real provider has been set."""
        return not isinstance(self._provider, NoOpLoggerProvider)

    @property
    def min_level(self) -> int:
        """Get the minimum log level."""
        return self._min_level

    @min_level.setter
    def min_level(self, level: int) -> None:
        """Set the minimum log level.

        Args:
            level: The minimum log level to record.
        """
        self._min_level = level

    def set_provider(self, provider: SDKLoggerProvider) -> None:
        """Set the real underlying LoggerProvider.

        This will update all existing proxy loggers to use the new provider.

        Args:
            provider: The OTEL LoggerProvider to delegate to.
        """
        with self._lock:
            self._provider = provider
            # Update all existing loggers with new underlying loggers
            for proxy_logger in self._loggers:
                if proxy_logger.name in self._suppressed_scopes:
                    proxy_logger.set_logger(SuppressedLogger(proxy_logger.name))
                elif proxy_logger.name in self._logger_factories:
                    proxy_logger.set_logger(self._logger_factories[proxy_logger.name]())

    def get_logger(
        self,
        name: str,
        version: str | None = None,
        schema_url: str | None = None,
        attributes: Any = None,
    ) -> ProxyLogger:
        """Get a logger from the underlying provider.

        Args:
            name: Name of the logger.
            version: Version of the logger.
            schema_url: Schema URL for the logger.
            attributes: Additional attributes for the logger.

        Returns:
            A ProxyLogger instance that delegates to the real logger.
        """
        with self._lock:
            # Factory function to create/recreate the underlying logger
            def logger_factory() -> Logger:
                return self._provider.get_logger(
                    name=name,
                    version=version,
                    schema_url=schema_url,
                    attributes=attributes,
                )

            # Check if scope is suppressed
            if name in self._suppressed_scopes:
                logger = SuppressedLogger(name)
            else:
                logger = logger_factory()

            proxy_logger = ProxyLogger(
                logger=logger,
                name=name,
                provider=self,
            )

            # Store factory and logger reference
            self._logger_factories[name] = logger_factory
            self._loggers.add(proxy_logger)

            return proxy_logger

    def suppress_scopes(self, *scopes: str) -> None:
        """Suppress logging for the given scopes.

        Suppressed scopes will return SuppressedLogger instances.

        Args:
            *scopes: Names to suppress.
        """
        with self._lock:
            self._suppressed_scopes.update(scopes)
            # Update existing loggers for these scopes
            for proxy_logger in self._loggers:
                if proxy_logger.name in scopes:
                    proxy_logger.set_logger(SuppressedLogger(proxy_logger.name))

    def shutdown(self) -> None:
        """Shutdown the provider."""
        with self._lock:
            if hasattr(self._provider, "shutdown"):
                self._provider.shutdown()  # type: ignore[union-attr]

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Force flush all pending log records.

        Args:
            timeout_millis: Maximum time to wait for flush.

        Returns:
            True if flush succeeded, False otherwise.
        """
        with self._lock:
            if hasattr(self._provider, "force_flush"):
                return self._provider.force_flush(timeout_millis)  # type: ignore[union-attr]
            return True
