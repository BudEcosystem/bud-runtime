"""Internal implementation details for BudObserve SDK.

WARNING: This module is internal and should not be imported directly.
All public API is exported from the top-level budobserve package.

The internal structure mirrors Logfire's architecture:
- main.py: BudObserve singleton class
- config.py: Configuration management
- tracer.py: Proxy TracerProvider
- meter.py: Proxy MeterProvider
- logger.py: Proxy LoggerProvider
- span.py: BudSpan wrapper
- constants.py: Attribute constants
- exporters/: Custom exporters (OTLP, BudMetrics)
- integrations/: Framework integrations
"""

from __future__ import annotations

__all__: list[str] = []
