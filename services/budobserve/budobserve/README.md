# BudObserve

Observability SDK for Bud-Stack platform - built on OpenTelemetry.

## Installation

```bash
pip install budobserve
```

## Quick Start

```python
import budobserve

# Configure the SDK
budobserve.configure(service_name="my-service")

# Create spans
with budobserve.span("processing request"):
    # your code here
    pass
```

## Features

- Built on OpenTelemetry for industry-standard telemetry
- High-level Pythonic API
- Automatic instrumentation for common frameworks
- LLM observability support
- Multiple backend support (OTLP, BudMetrics)

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check .
ruff format .
```

## License

MIT
