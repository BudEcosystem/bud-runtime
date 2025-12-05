"""BudObserve main class - the singleton entry point.

This module contains the BudObserve class which is the main entry point
for the SDK. It manages initialization, configuration, and provides
the high-level API for creating spans, metrics, and logs.

Architecture:
- Singleton pattern (like Logfire)
- Lazy initialization of OTEL providers
- Proxy providers for runtime flexibility

Will be implemented in Phase 1 (Core OTEL Wrapper).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class BudObserve:
    """Main BudObserve class - singleton entry point for the SDK.

    This class manages:
    - SDK initialization and configuration
    - Proxy providers for tracing, metrics, and logging
    - High-level API for creating spans and recording metrics

    Example:
        >>> budobserve = BudObserve()
        >>> budobserve.configure(service_name="my-service")
        >>> with budobserve.span("operation"):
        ...     pass
    """

    _instance: BudObserve | None = None

    def __new__(cls) -> BudObserve:
        """Ensure singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize BudObserve instance."""
        # Prevent re-initialization
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._configured = False

    def configure(
        self,
        *,
        service_name: str | None = None,
    ) -> None:
        """Configure BudObserve SDK.

        Args:
            service_name: Name of the service for telemetry.
        """
        # Placeholder - will be implemented in Phase 1
        self._configured = True

    @property
    def is_configured(self) -> bool:
        """Check if SDK has been configured."""
        return self._configured


# Global singleton instance
_budobserve: BudObserve | None = None


def get_budobserve() -> BudObserve:
    """Get the global BudObserve instance."""
    global _budobserve
    if _budobserve is None:
        _budobserve = BudObserve()
    return _budobserve
