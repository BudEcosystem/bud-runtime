"""Configuration management for BudObserve SDK.

This module handles SDK configuration from multiple sources:
- Environment variables (BUDOBSERVE_*, OTEL_*)
- Programmatic configuration via configure()
- Default values

Configuration follows a priority order:
1. Explicit programmatic configuration (highest)
2. Environment variables
3. Default values (lowest)

Will be implemented in Phase 1 (Core OTEL Wrapper).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


@dataclass
class BudObserveConfig:
    """Configuration for BudObserve SDK.

    Attributes:
        service_name: Name of the service for telemetry identification.
        service_version: Version of the service.
        environment: Deployment environment (dev, staging, prod).
        otlp_endpoint: OTLP exporter endpoint URL.
        budmetrics_endpoint: BudMetrics ClickHouse endpoint URL.
        enable_console_exporter: Enable console exporter for debugging.
        scrub_patterns: Patterns for sensitive data scrubbing.
    """

    service_name: str = "unknown-service"
    service_version: str = "0.0.0"
    environment: str = "development"
    otlp_endpoint: str | None = None
    budmetrics_endpoint: str | None = None
    enable_console_exporter: bool = False
    scrub_patterns: list[str] = field(default_factory=list)

    @classmethod
    def from_environment(cls) -> BudObserveConfig:
        """Create configuration from environment variables.

        Environment variables:
            BUDOBSERVE_SERVICE_NAME: Service name
            BUDOBSERVE_SERVICE_VERSION: Service version
            BUDOBSERVE_ENVIRONMENT: Deployment environment
            BUDOBSERVE_OTLP_ENDPOINT: OTLP endpoint
            BUDOBSERVE_BUDMETRICS_ENDPOINT: BudMetrics endpoint
            BUDOBSERVE_CONSOLE_EXPORTER: Enable console exporter (true/false)
            OTEL_SERVICE_NAME: Fallback for service name
        """
        # Placeholder - will be implemented in Phase 1
        return cls()


def get_default_config() -> BudObserveConfig:
    """Get default configuration with environment overrides."""
    return BudObserveConfig.from_environment()
