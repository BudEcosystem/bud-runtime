# Development Plan for BudObserve SDK

This document defines the phased development roadmap for building the BudObserve SDK — a custom observability SDK built on OpenTelemetry, strictly following Logfire architectural patterns.

---

## Overview

**BudObserve** is an observability SDK for the bud-stack microservice platform that provides:
- Unified tracing, logging, and metrics on top of OpenTelemetry
- Logfire-style developer experience (high-level API, ergonomic helpers)
- Framework integrations for FastAPI, SQLAlchemy, LLM providers, and more
- Consistent schema across all bud-stack services

**Target Backends:**
- Standard OTLP collectors (Grafana, Jaeger, etc.)
- BudMetrics service (ClickHouse-based analytics)

---

## Phase 0: Research & Architecture Validation

### Goal
Validate the proposed architecture against Logfire patterns and confirm OpenTelemetry compatibility.

### Scope
- Review and finalize architecture.md
- Confirm OTEL SDK version requirements
- Define exact package structure
- Establish coding standards

### Key Tasks
1. Validate proxy provider pattern against `logfire/_internal/tracer.py`
2. Confirm OpenTelemetry SDK version (target: >= 1.35.0)
3. Define Python version support (target: 3.10+)
4. Create initial `pyproject.toml` with dependencies
5. Establish directory structure following Logfire conventions

### Dependencies
- Access to Logfire and OpenTelemetry source code
- architecture.md and CLAUDE.md finalized

### Deliverables
- [ ] Finalized architecture.md (if changes needed)
- [ ] Initial `pyproject.toml`
- [ ] Empty package structure with `__init__.py` files
- [ ] `py.typed` marker for type checking

### Risks / Open Questions
- Which OTEL instrumentation library versions to pin?
- Should we support Python 3.9 for broader compatibility?

---

## Phase 1: Core OTEL Wrapper & Initialization Layer

### Goal
Build the foundational proxy provider infrastructure that wraps OpenTelemetry.

### Scope
- Proxy providers for tracing, metrics, and logging
- BudObserve main class skeleton
- Global singleton pattern
- Basic `configure()` method

### Key Tasks

#### 1.1 Proxy Providers
Create proxy wrappers following Logfire's `_internal/tracer.py` pattern:

```
_internal/
├── tracer.py      # BudTracerProvider, BudTracer
├── meter.py       # BudMeterProvider, BudMeter
└── logger.py      # BudLoggerProvider, BudLogger
```

Key classes:
- `BudTracerProvider`: Wraps `TracerProvider`, supports `set_provider()` and `suppress_scopes()`
- `BudTracer`: Wraps `Tracer`, returns `BudSpan` instances
- `BudSpan`: Wraps `Span` with SDK-specific cleanup and callbacks

#### 1.2 Main Class Skeleton
Create `_internal/main.py` with:
- `BudObserve` class with placeholder methods
- Provider initialization
- Resource detection

#### 1.3 Global Singleton
Implement in `__init__.py`:
- `DEFAULT_INSTANCE = BudObserve()`
- Module-level function delegation
- `configure()` class method

#### 1.4 Basic Configuration
Create `_internal/config.py` with:
- `BudObserveConfig` dataclass
- Service name, version, environment
- Minimal exporter setup

### Dependencies
- OpenTelemetry SDK installed
- Package structure from Phase 0

### Deliverables
- [ ] `_internal/tracer.py` - BudTracerProvider, BudTracer, BudSpan
- [ ] `_internal/meter.py` - BudMeterProvider, BudMeter
- [ ] `_internal/logger.py` - BudLoggerProvider, BudLogger
- [ ] `_internal/main.py` - BudObserve class skeleton
- [ ] `_internal/config.py` - Basic configuration
- [ ] `__init__.py` - Public API with DEFAULT_INSTANCE

### Risks / Open Questions
- Thread-safety for provider swapping (use locks like Logfire)
- WeakKeyDictionary for tracer instance tracking

---

## Phase 2: Unified Schema — Span Naming + Attributes + Conventions

### Goal
Define the unified schema for span naming, attributes, and conventions across all services.

### Scope
- Message template system
- Attribute naming conventions
- SDK-internal attribute keys
- Span type categorization

### Key Tasks

#### 2.1 Message Templates
Implement template formatting following Logfire's `_internal/formatter.py`:
- Parse `{variable}` placeholders
- Store template and formatted message separately
- Support `{var=}` magic syntax for debug output

#### 2.2 Attribute Constants
Create `_internal/constants.py`:

```python
# SDK-internal attributes
ATTR_MSG_TEMPLATE = 'budobserve_msg_template'
ATTR_MSG = 'budobserve_msg'
ATTR_SPAN_TYPE = 'budobserve_span_type'
ATTR_TAGS = 'budobserve_tags'
ATTR_JSON_SCHEMA = 'budobserve_json_schema'

# Bud-specific attributes
ATTR_PROJECT_ID = 'bud.project.id'
ATTR_ENDPOINT_ID = 'bud.endpoint.id'
ATTR_MODEL_ID = 'bud.model.id'
ATTR_CLUSTER_ID = 'bud.cluster.id'
ATTR_REQUEST_ID = 'bud.request.id'

# LLM attributes (gen_ai namespace)
ATTR_LLM_MODEL = 'gen_ai.request.model'
ATTR_LLM_INPUT_TOKENS = 'gen_ai.usage.input_tokens'
ATTR_LLM_OUTPUT_TOKENS = 'gen_ai.usage.output_tokens'
ATTR_LLM_TOTAL_TOKENS = 'gen_ai.usage.total_tokens'
ATTR_LLM_COST = 'gen_ai.usage.cost'
```

#### 2.3 Span Types
Define span type enumeration:
- `log` - Log-level spans (info, debug, error, etc.)
- `span` - Explicit tracing spans
- `pending` - Incomplete spans
- `integration` - Framework integration spans

#### 2.4 Attribute Helpers
Create `_internal/attributes.py`:
- Attribute validation
- Type conversion utilities
- BoundedAttributes wrapper

### Dependencies
- Phase 1 complete (proxy providers)

### Deliverables
- [ ] `_internal/constants.py` - All attribute constants
- [ ] `_internal/formatter.py` - Message template formatting
- [ ] `_internal/attributes.py` - Attribute helpers
- [ ] `types.py` - SpanType enum and public types

### Risks / Open Questions
- JSON Schema generation (optional, defer if complex)
- Pydantic model serialization for attributes

---

## Phase 3: High-Level Python SDK API

### Goal
Implement the developer-facing API with Logfire-style ergonomics.

### Scope
- Logging methods (trace, debug, info, warn, error, fatal)
- `span()` context manager
- `@instrument` decorator
- Metrics API

### Key Tasks

#### 3.1 Logging Methods
Add to `BudObserve` class:

```python
def trace(self, msg_template: str, **attrs) -> None
def debug(self, msg_template: str, **attrs) -> None
def info(self, msg_template: str, **attrs) -> None
def notice(self, msg_template: str, **attrs) -> None
def warn(self, msg_template: str, **attrs) -> None
def error(self, msg_template: str, **attrs) -> None
def fatal(self, msg_template: str, **attrs) -> None
def exception(self, msg: str | None = None, exc_info: ExcInfo = None) -> None
```

Each creates a span with:
- Appropriate log level
- Formatted message
- User attributes
- Stack info (optional)

#### 3.2 Span Context Manager
Create `_internal/span.py`:

```python
class BudSpan:
    def __enter__(self) -> BudSpan
    def __exit__(self, exc_type, exc_val, exc_tb) -> bool | None
    async def __aenter__(self) -> BudSpan
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None

    def set_attribute(self, key: str, value: Any) -> None
    def set_attributes(self, attrs: dict[str, Any]) -> None
    def add_event(self, name: str, attributes: dict | None = None) -> None
    def record_exception(self, exception: BaseException) -> None
```

Add to `BudObserve`:

```python
def span(
    self,
    msg_template: str,
    *,
    _level: LevelName | None = None,
    _tags: Sequence[str] | None = None,
    **attributes,
) -> BudSpan
```

#### 3.3 Instrument Decorator
Create `_internal/instrument.py`:

```python
def instrument(
    *,
    tags: Sequence[str] = (),
    msg_template: str | None = None,
    span_name: str | None = None,
    extract_args: bool | Iterable[str] = True,
    record_return: bool = False,
    new_trace: bool = False,
) -> Callable[[F], F]
```

Support:
- Sync and async functions
- Methods, classmethods, staticmethods
- Generators (with warning)
- Argument extraction
- Return value capture

#### 3.4 Metrics API
Add to `BudObserve`:

```python
def metric_counter(
    self, name: str, *, unit: str = '', description: str = ''
) -> Counter

def metric_histogram(
    self, name: str, *, unit: str = '', description: str = ''
) -> Histogram

def metric_gauge(
    self, name: str, *, unit: str = '', description: str = ''
) -> Gauge

def metric_up_down_counter(
    self, name: str, *, unit: str = '', description: str = ''
) -> UpDownCounter
```

### Dependencies
- Phase 2 complete (schema, attributes)

### Deliverables
- [ ] Complete `BudObserve` class with all logging methods
- [ ] `_internal/span.py` - BudSpan context manager
- [ ] `_internal/instrument.py` - @instrument decorator
- [ ] Metrics API methods
- [ ] Unit tests for all API methods

### Risks / Open Questions
- Exception callback customization (defer to Phase 6)
- Stack frame extraction for source info

---

## Phase 4: Framework & Library Integrations

### Goal
Implement integrations for core bud-stack frameworks and libraries.

### Scope
- FastAPI integration
- SQLAlchemy/asyncpg integration
- httpx/aiohttp integration
- Redis integration

### Key Tasks

#### 4.1 Integration Base Pattern
Create `_internal/integrations/__init__.py` with base utilities:
- WeakKeyDictionary for instance tracking
- OTEL instrumentor wrapper pattern
- Context manager for uninstrumentation
- Scope suffix handling

#### 4.2 FastAPI Integration
Create `_internal/integrations/fastapi.py`:
- Wrap `FastAPIInstrumentor`
- Add request/response attribute enrichment
- Capture dependency injection info
- Handle route metadata (operation_id, path)

Public API:
```python
def instrument_fastapi(
    app: FastAPI,
    *,
    capture_headers: bool = False,
    excluded_urls: str | Iterable[str] | None = None,
    **kwargs,
) -> ContextManager[None]
```

#### 4.3 SQLAlchemy/asyncpg Integration
Create `_internal/integrations/sqlalchemy.py`:
- Wrap `SQLAlchemyInstrumentor`
- Capture query statements
- Support async engines
- Add `db.statement` attribute

Create `_internal/integrations/asyncpg.py`:
- Wrap `AsyncPGInstrumentor`

#### 4.4 HTTP Client Integrations
Create `_internal/integrations/httpx.py`:
- Wrap `HTTPXClientInstrumentor`
- Capture request/response bodies (configurable)
- Handle streaming responses

Create `_internal/integrations/aiohttp.py`:
- Wrap `AioHttpClientInstrumentor`

#### 4.5 Redis Integration
Create `_internal/integrations/redis.py`:
- Wrap `RedisInstrumentor`
- Capture command statements
- Add `db.statement` with truncation

### Dependencies
- Phase 3 complete (high-level API)
- OTEL instrumentation libraries installed

### Deliverables
- [ ] `_internal/integrations/fastapi.py`
- [ ] `_internal/integrations/sqlalchemy.py`
- [ ] `_internal/integrations/asyncpg.py`
- [ ] `_internal/integrations/httpx.py`
- [ ] `_internal/integrations/aiohttp.py`
- [ ] `_internal/integrations/redis.py`
- [ ] Integration tests for each

### Risks / Open Questions
- Version compatibility with OTEL instrumentors
- Monkeypatching vs. explicit instrumentation

---

## Phase 5: LLM Observability Layer

### Goal
Implement first-class observability for LLM calls with token tracking and cost estimation.

### Scope
- OpenAI integration
- Anthropic integration
- LiteLLM integration
- Token and cost metrics

### Key Tasks

#### 5.1 LLM Provider Base
Create `_internal/integrations/llm_providers/llm_provider.py`:
- Base pattern for LLM instrumentation
- Stream state tracking (like Logfire)
- Request/response attribute extraction
- Token counting utilities

#### 5.2 OpenAI Integration
Create `_internal/integrations/llm_providers/openai.py`:
- Monkeypatch OpenAI client methods
- Track chat completions, embeddings
- Capture streaming responses
- Extract token usage from response

Attributes captured:
```
gen_ai.request.model
gen_ai.request.temperature
gen_ai.request.max_tokens
gen_ai.usage.input_tokens
gen_ai.usage.output_tokens
gen_ai.usage.total_tokens
gen_ai.usage.cost
```

#### 5.3 Anthropic Integration
Create `_internal/integrations/llm_providers/anthropic.py`:
- Monkeypatch Anthropic client methods
- Track message completions
- Handle streaming

#### 5.4 LiteLLM Integration
Create `_internal/integrations/llm_providers/litellm.py`:
- Wrap LiteLLM completion calls
- Provider-agnostic instrumentation

#### 5.5 Cost Estimation
Create `_internal/integrations/llm_providers/cost.py`:
- Model pricing database
- Cost calculation from token counts
- Configurable pricing overrides

### Dependencies
- Phase 4 complete (integration patterns established)

### Deliverables
- [ ] `_internal/integrations/llm_providers/llm_provider.py` - Base utilities
- [ ] `_internal/integrations/llm_providers/openai.py`
- [ ] `_internal/integrations/llm_providers/anthropic.py`
- [ ] `_internal/integrations/llm_providers/litellm.py`
- [ ] `_internal/integrations/llm_providers/cost.py`
- [ ] LLM-specific tests

### Risks / Open Questions
- API changes in LLM providers
- Streaming response handling complexity
- Cost estimation accuracy

---

## Phase 6: Configuration + Redaction + Safety Layer

### Goal
Implement comprehensive configuration, scrubbing, and multi-backend support.

### Scope
- Full configuration system
- Scrubbing/redaction infrastructure
- Environment variable support
- Backend configuration (OTLP + BudMetrics)
- Dapr integration

### Key Tasks

#### 6.1 Configuration System
Expand `_internal/config.py`:

```python
@dataclass
class BudObserveConfig:
    service_name: str
    service_version: str | None
    environment: str | None

    backend: BackendConfig | None
    console: ConsoleConfig | None
    sampling: SamplingConfig | None
    scrubbing: ScrubbingConfig | None
    advanced: AdvancedConfig | None

@dataclass
class BackendConfig:
    endpoint: str
    token: str | None
    headers: dict[str, str] | None

@dataclass
class ConsoleConfig:
    enabled: bool = True
    colors: Literal['auto', 'always', 'never'] = 'auto'
    style: Literal['simple', 'indented', 'show-parents'] = 'show-parents'

@dataclass
class SamplingConfig:
    head_sample_rate: float = 1.0

@dataclass
class ScrubbingConfig:
    enabled: bool = True
    extra_patterns: Sequence[str] | None = None
    callback: Callable[[ScrubMatch], Any] | None = None
```

#### 6.2 Scrubbing Infrastructure
Create `_internal/scrubbing.py`:
- Default sensitive patterns (password, token, api_key, etc.)
- Recursive attribute scrubbing
- Custom callback support
- Safe keys that are never scrubbed

#### 6.3 Environment Variables
Support in config loading:
```
BUD_OBSERVE_SERVICE_NAME
BUD_OBSERVE_ENVIRONMENT
BUD_OBSERVE_ENDPOINT
BUD_OBSERVE_TOKEN
BUD_OBSERVE_SAMPLE_RATE
BUD_OBSERVE_CONSOLE
```

#### 6.4 Multi-Backend Export
Create exporters:
- `_internal/exporters/otlp.py` - OTLP HTTP/gRPC wrapper
- `_internal/exporters/budmetrics.py` - BudMetrics/ClickHouse exporter
- `_internal/exporters/console.py` - Console output
- `_internal/exporters/processor.py` - BatchProcessor wrapper

#### 6.5 Dapr Integration
Create `_internal/integrations/dapr.py`:
- Service invocation tracing
- Pub/sub message tracing
- State store operation tracing
- Context propagation across Dapr calls

### Dependencies
- Phase 5 complete (LLM layer)

### Deliverables
- [ ] Complete configuration system
- [ ] `_internal/scrubbing.py` - Redaction infrastructure
- [ ] `_internal/exporters/otlp.py`
- [ ] `_internal/exporters/budmetrics.py`
- [ ] `_internal/exporters/console.py`
- [ ] `_internal/integrations/dapr.py`
- [ ] Environment variable support

### Risks / Open Questions
- BudMetrics exporter protocol (OTLP or custom?)
- Dapr SDK version compatibility

---

## Phase 7: Testing Strategy & Tooling

### Goal
Build comprehensive testing utilities and establish testing patterns.

### Scope
- TestExporter utility
- pytest plugin
- Span assertion helpers
- Integration test patterns

### Key Tasks

#### 7.1 TestExporter
Create `testing.py`:

```python
class TestExporter(SpanExporter):
    """In-memory exporter for testing."""

    def get_finished_spans(self) -> list[ReadableSpan]
    def clear(self) -> None
    def get_span_by_name(self, name: str) -> ReadableSpan | None
    def assert_has_span(self, name: str, **expected_attrs) -> None
```

#### 7.2 Pytest Plugin
Create pytest fixtures:

```python
@pytest.fixture
def budobserve_test_exporter() -> TestExporter:
    """Provide test exporter with automatic cleanup."""

@pytest.fixture
def budobserve_configured() -> BudObserve:
    """Provide configured BudObserve instance for testing."""
```

#### 7.3 Span Assertions
Create assertion helpers:

```python
def assert_span_has_attributes(span: ReadableSpan, **attrs) -> None
def assert_span_has_event(span: ReadableSpan, event_name: str) -> None
def assert_span_status_ok(span: ReadableSpan) -> None
def assert_span_status_error(span: ReadableSpan) -> None
def assert_span_exception(span: ReadableSpan, exc_type: type) -> None
```

#### 7.4 Integration Test Patterns
Create test examples for:
- FastAPI app testing
- Database operation testing
- HTTP client testing
- LLM call testing

### Dependencies
- Phase 6 complete (full SDK)

### Deliverables
- [ ] `testing.py` - TestExporter and fixtures
- [ ] pytest plugin registration
- [ ] Assertion helpers
- [ ] Integration test examples
- [ ] Test coverage > 80%

### Risks / Open Questions
- pytest plugin entry point registration
- Async test support

---

## Phase 8: Documentation, Examples & Internal Adoption Plan

### Goal
Create comprehensive documentation and drive internal adoption across bud-stack services.

### Scope
- API documentation
- Integration guides
- Example applications
- Internal adoption plan

### Key Tasks

#### 8.1 API Documentation
Create `docs/api/`:
- Core API reference (BudObserve class)
- Configuration reference
- Integration reference
- Attribute schema reference

#### 8.2 Integration Guides
Create `docs/integrations/`:
- FastAPI guide with examples
- Database tracing guide
- LLM observability guide
- Dapr integration guide

#### 8.3 Example Applications
Create `examples/`:
- Basic FastAPI application
- Full-stack example with database and LLM
- Testing example

#### 8.4 Internal Adoption Plan
Create adoption guide for bud-stack services:

| Service | Priority | Integrations Needed |
|---------|----------|---------------------|
| budapp | High | FastAPI, SQLAlchemy, httpx |
| budcluster | High | FastAPI, Dapr, Ansible hooks |
| budsim | Medium | FastAPI, Redis, LLM |
| budmodel | Medium | FastAPI, SQLAlchemy |
| budmetrics | Low | ClickHouse client |
| budgateway | Low | Rust SDK (future) |

### Dependencies
- Phase 7 complete (testing ready)

### Deliverables
- [ ] Complete API documentation
- [ ] Integration guides for each framework
- [ ] Example applications
- [ ] Internal adoption plan
- [ ] Migration guide from raw OTEL

### Risks / Open Questions
- Documentation tooling (MkDocs vs Sphinx)
- Service-specific customization needs

---

## Summary

| Phase | Focus | Est. Effort |
|-------|-------|-------------|
| 0 | Research & Validation | Small |
| 1 | Core OTEL Wrapper | Medium |
| 2 | Schema & Conventions | Small |
| 3 | High-Level API | Large |
| 4 | Framework Integrations | Large |
| 5 | LLM Observability | Medium |
| 6 | Config + Redaction | Medium |
| 7 | Testing Tooling | Medium |
| 8 | Documentation & Adoption | Medium |

**Critical Path:** Phase 0 → 1 → 2 → 3 → (4, 5, 6 parallel possible) → 7 → 8

---

## Appendix: Key Reference Files

### Logfire (patterns to follow)
| File | Purpose |
|------|---------|
| `logfire/_internal/main.py` | Core class implementation |
| `logfire/_internal/config.py` | Configuration management |
| `logfire/_internal/tracer.py` | Proxy provider pattern |
| `logfire/_internal/scrubbing.py` | Redaction logic |
| `logfire/_internal/instrument.py` | Decorator implementation |
| `logfire/_internal/integrations/fastapi.py` | Integration pattern |
| `logfire/_internal/integrations/llm_providers/openai.py` | LLM pattern |

### OpenTelemetry (APIs to use)
| File | Purpose |
|------|---------|
| `opentelemetry-sdk/trace/__init__.py` | TracerProvider, Span |
| `opentelemetry-sdk/trace/sampling.py` | Sampler implementations |
| `opentelemetry-sdk/trace/export/__init__.py` | Exporter interfaces |
| `opentelemetry-sdk/resources/__init__.py` | Resource detection |
| `opentelemetry-api/context/__init__.py` | Context management |

---

*This plan is the canonical implementation roadmap for BudObserve SDK development.*
