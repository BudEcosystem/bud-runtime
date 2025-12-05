# BudObserve SDK Architecture Reference

This document provides a comprehensive reference for building the BudObserve SDK, based on research of OpenTelemetry Python SDK and Logfire. It serves as the authoritative guide for Claude Code sessions implementing observability features.

---

## Table of Contents

1. [OpenTelemetry Python SDK Core Concepts](#1-opentelemetry-python-sdk-core-concepts)
2. [Logfire Architecture Over OTEL](#2-logfire-architecture-over-otel)
3. [Comparison: Raw OTEL vs Logfire](#3-comparison-raw-otel-vs-logfire)
4. [Proposed Principles for BudObserve SDK](#4-proposed-principles-for-budobserve-sdk)

---

## 1. OpenTelemetry Python SDK Core Concepts

### 1.1 Package Architecture

The OpenTelemetry Python SDK is organized into distinct packages with clear separation of concerns:

| Package | Purpose |
|---------|---------|
| `opentelemetry-api` | Abstract interfaces and no-op implementations |
| `opentelemetry-sdk` | Concrete SDK implementations |
| `opentelemetry-proto` | Protocol buffer definitions for OTLP |
| `opentelemetry-semantic-conventions` | Standard attribute names |
| `exporter/` | Backend exporters (OTLP, Zipkin, Prometheus, Jaeger) |
| `propagator/` | Context propagation (B3, Jaeger, W3C TraceContext) |

**Key Design Principle**: The API package provides abstract interfaces that can work with no-op implementations (for libraries) or the full SDK (for applications). This allows libraries to instrument without depending on the SDK.

### 1.2 Core Providers

All three signal types (traces, metrics, logs) follow the same provider pattern:

```
Provider Pattern:
  XProvider.get_X(name, version, schema_url) -> X instance

TracerProvider -> get_tracer() -> Tracer
MeterProvider  -> get_meter()  -> Meter
LoggerProvider -> get_logger() -> Logger
```

**TracerProvider** is the central component for distributed tracing:
- Creates and manages Tracer instances
- Holds configuration: samplers, processors, resource
- Manages lifecycle: shutdown, force_flush

**MeterProvider** manages metrics collection:
- Creates Meter instances for different instruments
- Handles aggregation and export scheduling

**LoggerProvider** manages structured logging:
- Creates Logger instances for log emission
- Integrates with trace context for correlation

### 1.3 Key Classes and Relationships

```
TracerProvider
├── get_tracer(name, version, schema_url) -> Tracer
├── add_span_processor(processor)
├── shutdown()
└── force_flush(timeout_millis)

Tracer
├── start_span(name, context, kind, attributes, links) -> Span
└── start_as_current_span(name, ...) -> ContextManager[Span]

Span
├── set_attribute(key, value)
├── set_attributes(attributes_dict)
├── add_event(name, attributes, timestamp)
├── add_link(context, attributes)
├── record_exception(exception, attributes)
├── set_status(status_code, description)
├── update_name(name)
├── is_recording() -> bool
├── get_span_context() -> SpanContext
└── end(end_time)

SpanContext (immutable)
├── trace_id: 128-bit identifier
├── span_id: 64-bit identifier
├── trace_flags: sampling flags
├── trace_state: vendor-specific data
└── is_remote: from external service
```

**SpanKind** defines the role of a span:
- `INTERNAL`: Default, internal operation
- `SERVER`: Handles incoming request
- `CLIENT`: Makes outgoing request
- `PRODUCER`: Creates message/job
- `CONSUMER`: Processes message/job

### 1.4 Resources and Attributes

**Resource**: Immutable entity metadata describing the service/process producing telemetry.

Standard resource attributes:
- `service.name`: Logical service name (required)
- `service.version`: Service version
- `service.instance.id`: Unique instance identifier
- `host.name`: Hostname
- `process.pid`: Process ID
- `telemetry.sdk.name`: SDK name
- `telemetry.sdk.version`: SDK version

**Attributes**: Key-value pairs attached to spans, metrics, logs.

**BoundedAttributes**: Thread-safe dictionary with:
- Maximum attribute count (default: 128)
- Maximum string value length (optional)
- Dropped count tracking

### 1.5 Context Propagation

Context is an immutable bag of key-value pairs for execution context. The Python SDK uses `contextvars` for async-safe context management.

**Context API**:
- `create_key(name)`: Create unique context key
- `get_value(key, context)`: Retrieve value from context
- `set_value(key, value, context)`: Create new context with value
- `get_current()`: Get current execution context
- `attach(context)`: Set context, return token
- `detach(token)`: Restore previous context

**Propagation**: Transferring context across process boundaries.
- `extract(carrier, context, getter)`: Extract context from carrier (headers)
- `inject(carrier, context, setter)`: Inject context into carrier

**Propagator Types**:
- W3C TraceContext (default): `traceparent`, `tracestate` headers
- W3C Baggage: Key-value pairs across services
- B3: Zipkin format (single/multi header)
- Jaeger: Jaeger format

### 1.6 Exporters and Processors

**Processing Pipeline**:
```
Span -> SpanProcessor.on_start() -> [recording] -> SpanProcessor.on_end() -> SpanExporter -> Backend
```

**SpanProcessor Types**:

| Processor | Behavior |
|-----------|----------|
| `SimpleSpanProcessor` | Immediate export, no batching (for debugging) |
| `BatchSpanProcessor` | Batched export with configurable delay (production) |
| `ConcurrentMultiSpanProcessor` | Parallel export to multiple backends |

**BatchSpanProcessor Configuration** (via environment variables):
- `OTEL_BSP_SCHEDULE_DELAY`: Export interval (default: 5000ms)
- `OTEL_BSP_MAX_QUEUE_SIZE`: Queue capacity (default: 2048)
- `OTEL_BSP_MAX_EXPORT_BATCH_SIZE`: Batch size (default: 512)
- `OTEL_BSP_EXPORT_TIMEOUT`: Export timeout (default: 30000ms)

**SpanExporter Types**:

| Exporter | Protocol | Use Case |
|----------|----------|----------|
| `OTLPSpanExporter` | gRPC or HTTP/protobuf | OTEL Collector, backends |
| `ZipkinSpanExporter` | HTTP/JSON | Zipkin backends |
| `JaegerSpanExporter` | gRPC or HTTP | Jaeger backends |
| `ConsoleSpanExporter` | stdout | Debugging |

### 1.7 Samplers

Samplers decide whether to record a span. Decision made at span creation time.

**SamplingDecision**:
- `DROP`: Don't record, don't propagate
- `RECORD_ONLY`: Record but don't propagate sampling flag
- `RECORD_AND_SAMPLE`: Record and propagate

**Built-in Samplers**:

| Sampler | Behavior |
|---------|----------|
| `ALWAYS_ON` | Sample everything |
| `ALWAYS_OFF` | Sample nothing |
| `TraceIdRatioBased(rate)` | Probabilistic (0.0-1.0), deterministic per trace |
| `ParentBased(root, remote_parent_sampled, ...)` | Respect parent decision |

**Configuration**:
- `OTEL_TRACES_SAMPLER`: Sampler type
- `OTEL_TRACES_SAMPLER_ARG`: Sampler argument (rate)

### 1.8 Environment Variable Configuration

Key environment variables:

| Variable | Purpose |
|----------|---------|
| `OTEL_SERVICE_NAME` | Service name resource attribute |
| `OTEL_RESOURCE_ATTRIBUTES` | Additional resource attributes (key=value,...) |
| `OTEL_TRACES_SAMPLER` | Sampler type |
| `OTEL_TRACES_SAMPLER_ARG` | Sampler argument |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP exporter endpoint |
| `OTEL_EXPORTER_OTLP_HEADERS` | OTLP headers (key=value,...) |
| `OTEL_EXPORTER_OTLP_TIMEOUT` | Export timeout |
| `OTEL_PROPAGATORS` | Comma-separated propagator names |
| `OTEL_SDK_DISABLED` | Disable SDK globally |

---

## 2. Logfire Architecture Over OTEL

### 2.1 Architectural Overview

Logfire is a developer-experience-focused wrapper around OpenTelemetry that:

1. **Abstracts Complexity**: Hides OTEL's multi-step configuration behind sensible defaults
2. **Uses Proxy Pattern**: Wraps OTEL providers for runtime flexibility
3. **Provides Unified API**: Single interface for logging, tracing, metrics
4. **Adds Rich Typing**: JSON Schema for intelligent attribute rendering
5. **Includes Integrations**: 30+ framework integrations out of the box

### 2.2 Core Design Patterns

**Proxy Pattern**: Wraps OTEL providers to allow runtime reconfiguration.

```
Logfire Instance
├── _tracer_provider: ProxyTracerProvider
│   └── provider: TracerProvider (actual OTEL provider)
├── _meter_provider: ProxyMeterProvider
│   └── provider: MeterProvider (actual OTEL provider)
└── _logs_tracer: _ProxyTracer
    └── tracer: Tracer (actual OTEL tracer)

ProxyTracerProvider
├── set_provider(provider)     # Swap underlying provider
├── suppress_scopes(names)     # Filter instrumentation scopes
└── get_tracer() -> _ProxyTracer

_ProxyTracer
├── set_tracer(tracer)         # Swap underlying tracer
└── start_span() -> _LogfireWrappedSpan

_LogfireWrappedSpan
├── span: Span                 # Wrapped OTEL span
├── end()                      # With Logfire cleanup
└── record_exception()         # With exception callback
```

**Why Proxies?**
- Allow provider swap after initialization (e.g., lazy configuration)
- Enable scope suppression without reinstantiation
- Maintain weak references to prevent memory leaks
- Thread-safe with locks for concurrent access

**Global Singleton Pattern**:
```python
DEFAULT_LOGFIRE_INSTANCE = Logfire()

# Module-level functions delegate to singleton
logfire.info(...)  # -> DEFAULT_LOGFIRE_INSTANCE.info(...)

# Custom instances for isolation
custom = Logfire(config=custom_config)
custom.info(...)
```

### 2.3 High-Level API

**Logging Methods** (create spans with log semantics):
```python
logfire.trace(msg_template, **attributes)
logfire.debug(msg_template, **attributes)
logfire.info(msg_template, **attributes)
logfire.notice(msg_template, **attributes)
logfire.warn(msg_template, **attributes)
logfire.error(msg_template, **attributes)
logfire.fatal(msg_template, **attributes)
logfire.exception(exc_info, msg)  # With traceback
```

**Tracing** (create spans with trace semantics):
```python
with logfire.span(msg_template, _level=None, _tags=None, **attributes) as span:
    span.set_attribute(key, value)
    span.add_event(name, attributes)
```

**Instrumentation Decorator**:
```python
@logfire.instrument(
    tags=['database'],
    msg_template='Processing {user_id}',
    extract_args=True,      # Capture function arguments
    record_return=True,     # Capture return value
    new_trace=False         # Start new trace (ignore parent)
)
def process_user(user_id: int) -> Result:
    ...
```

**Metrics**:
```python
counter = logfire.metric_counter('requests', unit='1', description='Request count')
histogram = logfire.metric_histogram('latency', unit='ms', description='Latency')
gauge = logfire.metric_gauge('active_connections', unit='1')

counter.add(1, attributes={'method': 'GET'})
histogram.record(0.123, attributes={'endpoint': '/api'})
```

### 2.4 Configuration

```python
logfire.configure(
    # Authentication
    token='...',                          # Logfire API token

    # Service identity
    service_name='my-service',            # Service name
    environment='production',             # Deployment environment

    # Export targets
    console=True,                         # Console output
    send_to_logfire=True,                # Backend export

    # Sampling
    sampling=SamplingOptions(
        head_sample_rate=1.0,            # 100% sampling
    ),

    # Scrubbing
    scrubbing=ScrubbingOptions(
        callback=custom_scrub_fn,         # Custom callback
        extra_patterns=['user_email'],    # Additional patterns
    ),

    # Advanced
    advanced=AdvancedOptions(
        exception_callback=handle_exc,    # Exception customization
        min_level=logging.INFO,           # Minimum log level
    ),
)
```

### 2.5 JSON Schema for Attributes

Logfire auto-generates JSON Schema for user-provided attributes, enabling intelligent frontend rendering.

**Supported Types**:
- Python built-ins: str, int, float, bool, dict, list, None
- Pydantic models: BaseModel, RootModel
- Standard library: datetime, date, time, UUID, Path, Decimal
- Data science: numpy arrays (with shape/dtype), pandas DataFrames (with columns)
- Exceptions: with traceback info

**Schema Extensions**:
- `x-python-datatype`: Python type name for rendering
- `x-columns`: DataFrame column names
- `x-shape`: Array shape
- `x-dtype`: Array dtype

### 2.6 Message Templates

Message templates enable span grouping and analytics.

```python
logfire.info('User {name} logged in', name='alice')

# Stored as:
# - Template: 'User {name} logged in' (for grouping)
# - Message: 'User alice logged in' (for display)

# Magic variable syntax:
logfire.debug('{user=} {count=!r}', user=user_obj, count=42)
# -> "user=User(id=1) count=42"
```

**Key Attributes**:
- `logfire_msg_template`: Original template string
- `logfire_msg`: Formatted message
- `logfire_json_schema`: Attribute schema
- `logfire_span_type`: Span category
- `logfire_tags`: Tag list

### 2.7 Scrubbing/Redaction

Built-in sensitive data redaction with configurable patterns.

**Default Patterns**:
```
password, passwd, secret, auth, credential, private_key, api_key,
session, cookie, social_security, credit_card, logfire_token,
csrf, xsrf, jwt, ssn
```

**Scrubbing Process**:
1. Recursively walk span attributes
2. Match key names and string values against patterns
3. Replace matches with `[REDACTED]` or custom value
4. Preserve safe keys (templates, schemas, tags)

**Configuration**:
```python
ScrubbingOptions(
    callback=lambda match: '[CUSTOM]' if match.pattern_match else None,
    extra_patterns=['user_email', r'phone_\d+'],
)
```

### 2.8 Auto-Instrumentation

AST-based automatic tracing via import hooks.

**How It Works**:
1. Install meta-path finder (LogfireFinder)
2. On module import, check if matches target pattern
3. Parse source code to AST
4. Wrap functions with `@logfire.instrument`
5. Compile and execute modified bytecode

**Configuration**:
```python
logfire.install_auto_tracing(
    modules=['myapp.services', 'myapp.handlers'],
    min_duration=0.001,  # Only trace calls > 1ms
    check_imported_modules='error',  # Warn if already imported
)
```

### 2.9 Integration Architecture

Logfire wraps OTEL instrumentors and adds enhancements.

**Integration Pattern**:
1. Get OTEL instrumentor (e.g., FastAPIInstrumentor)
2. Call instrumentor with Logfire's providers
3. Add framework-specific hooks for enrichment
4. Return context manager for uninstrumentation

**Common Features**:
- WeakKeyDictionary for per-instance tracking
- Scope suffix for namespace isolation
- Error handling with silent failures
- Configurable capture options

---

## 3. Comparison: Raw OTEL vs Logfire

| Aspect | Raw OTEL | Logfire |
|--------|----------|---------|
| **Setup** | 15+ lines configuration | 1-2 lines |
| **Logging** | Separate LoggerProvider | logfire.info/debug/error |
| **Tracing** | start_as_current_span() | with logfire.span() |
| **Instrumentation** | Manual or plugins | @logfire.instrument or auto |
| **Attributes** | Dict with string keys | Rich JSON Schema |
| **Scrubbing** | Custom processor | Built-in ScrubbingOptions |
| **Framework Support** | Library-specific | Unified interface for 30+ |
| **LLM Support** | Unsupported | First-class with metrics |
| **Message Grouping** | Manual span names | Message templates |
| **Runtime Flexibility** | Fixed after init | Proxy allows swaps |
| **Configuration** | Programmatic + env vars | configure() + env vars |
| **Testing** | InMemoryExporter | TestExporter + helpers |

---

## 4. Proposed Principles for BudObserve SDK

### 4.1 Core Architecture

**Principle 1: Proxy Providers**

Wrap OTEL providers for runtime flexibility and scope control.

```
BudObserve
├── _tracer_provider: BudTracerProvider (proxy)
├── _meter_provider: BudMeterProvider (proxy)
└── _logger_provider: BudLoggerProvider (proxy)

BudTracerProvider
├── _provider: TracerProvider (actual OTEL)
├── _tracers: WeakKeyDictionary
├── set_provider(provider)
├── suppress_scopes(names)
└── get_tracer() -> BudTracer
```

**Principle 2: Global Singleton with Escape Hatch**

Provide module-level convenience with instance isolation capability.

```python
# Global singleton
DEFAULT_INSTANCE = BudObserve()

# Module-level API
def info(msg, **attrs):
    DEFAULT_INSTANCE.info(msg, **attrs)

# Custom instances for isolation
custom = BudObserve(config=custom_config)
```

**Principle 3: Unified API Surface**

Single class with methods for all observability signals.

```python
class BudObserve:
    # Logging
    def trace/debug/info/warn/error(msg_template, **attrs)

    # Tracing
    def span(msg_template, _level, _tags, **attrs) -> BudSpan

    # Metrics
    def metric_counter/histogram/gauge(name, unit, description)

    # Configuration
    @classmethod
    def configure(cls, **options)

    # Integration
    def instrument_fastapi(app, **options)
    def instrument_sqlalchemy(engine, **options)
    ...
```

### 4.2 Configuration Strategy

Hierarchical configuration with sensible defaults.

```python
budobserve.configure(
    # Service identity
    service_name='my-service',
    service_version='1.0.0',
    environment='production',

    # Backend
    backend=BackendConfig(
        endpoint='https://observe.bud.dev',
        token=os.environ.get('BUD_OBSERVE_TOKEN'),
    ),

    # Console
    console=ConsoleConfig(
        enabled=True,
        colors='auto',
        style='show-parents',
    ),

    # Sampling
    sampling=SamplingConfig(
        head_sample_rate=1.0,
    ),

    # Scrubbing
    scrubbing=ScrubbingConfig(
        enabled=True,
        extra_patterns=['user_email'],
    ),
)
```

**Environment Variable Overrides**:
- `BUD_OBSERVE_SERVICE_NAME`
- `BUD_OBSERVE_ENVIRONMENT`
- `BUD_OBSERVE_ENDPOINT`
- `BUD_OBSERVE_TOKEN`
- `BUD_OBSERVE_SAMPLE_RATE`

### 4.3 Integration Strategy

Follow Logfire patterns for consistency:

1. **Wrap OTEL Instrumentors**: Use existing OTEL instrumentors where available
2. **Add Framework Hooks**: Enhance with Bud-specific attributes
3. **WeakKeyDictionary**: Track per-instance instrumentation
4. **Context Managers**: Provide uninstrumentation capability
5. **Scope Suffix**: Isolate integration namespaces

### 4.4 Critical Integrations (Priority Order)

| Priority | Integration | Purpose |
|----------|-------------|---------|
| 1 | FastAPI | HTTP request/response, dependency injection |
| 2 | SQLAlchemy/asyncpg | Database query tracing |
| 3 | httpx/aiohttp | HTTP client calls |
| 4 | Redis | Cache operations |
| 5 | OpenAI/Anthropic/LiteLLM | LLM calls with token tracking |
| 6 | Celery | Background task tracing |
| 7 | Dapr | Service-to-service calls |

### 4.5 Schema Design

Standardized attributes following OTEL semantic conventions plus Bud-specific extensions.

**Standard Attributes** (OTEL semantic conventions):
- `service.name`: Service identifier
- `service.version`: Service version
- `deployment.environment`: Environment (prod, staging, dev)
- `enduser.id`: User identifier

**Bud-Specific Attributes**:
- `bud.project.id`: Project identifier
- `bud.endpoint.id`: Model endpoint identifier
- `bud.model.id`: Model identifier
- `bud.cluster.id`: Cluster identifier
- `bud.request.id`: Request correlation ID

**LLM Attributes** (gen_ai namespace):
- `gen_ai.request.model`: Model name
- `gen_ai.request.temperature`: Temperature setting
- `gen_ai.request.max_tokens`: Max tokens requested
- `gen_ai.usage.input_tokens`: Input token count
- `gen_ai.usage.output_tokens`: Output token count
- `gen_ai.usage.total_tokens`: Total token count
- `gen_ai.usage.cost`: Estimated cost

### 4.6 File Structure

```
budobserve/
├── __init__.py              # Public API exports
├── types.py                 # Public types (SpanLevel, etc.)
├── propagate.py             # Context propagation helpers
├── testing.py               # Test utilities
├── _internal/
│   ├── main.py              # BudObserve class
│   ├── config.py            # Configuration management
│   ├── tracer.py            # BudTracerProvider (proxy)
│   ├── meter.py             # BudMeterProvider (proxy)
│   ├── logger.py            # BudLoggerProvider (proxy)
│   ├── span.py              # BudSpan wrapper
│   ├── attributes.py        # Attribute helpers, schema
│   ├── scrubbing.py         # Data redaction
│   ├── constants.py         # Attribute names, defaults
│   ├── exporters/
│   │   ├── __init__.py
│   │   ├── otlp.py          # OTLP exporter wrapper
│   │   ├── console.py       # Console exporter
│   │   └── processor.py     # Batch processor wrapper
│   └── integrations/
│       ├── __init__.py
│       ├── fastapi.py
│       ├── sqlalchemy.py
│       ├── httpx.py
│       ├── redis.py
│       ├── openai.py
│       ├── celery.py
│       └── dapr.py
└── py.typed                 # PEP 561 marker
```

---

## Key Source Files Reference

### OpenTelemetry Python SDK
| File | Purpose |
|------|---------|
| `opentelemetry-sdk/src/opentelemetry/sdk/trace/__init__.py` | TracerProvider, Tracer, Span |
| `opentelemetry-sdk/src/opentelemetry/sdk/trace/sampling.py` | Sampler implementations |
| `opentelemetry-sdk/src/opentelemetry/sdk/trace/export/__init__.py` | Processors and exporters |
| `opentelemetry-sdk/src/opentelemetry/sdk/resources/__init__.py` | Resource class |
| `opentelemetry-api/src/opentelemetry/context/__init__.py` | Context management |
| `opentelemetry-api/src/opentelemetry/propagate/__init__.py` | Propagation |

### Logfire
| File | Lines | Purpose |
|------|-------|---------|
| `logfire/_internal/main.py` | ~2600 | Core Logfire class |
| `logfire/_internal/config.py` | ~1700 | Configuration management |
| `logfire/_internal/tracer.py` | ~500 | ProxyTracerProvider |
| `logfire/_internal/scrubbing.py` | ~300 | Data redaction |
| `logfire/_internal/json_schema.py` | ~400 | Attribute schema |
| `logfire/_internal/integrations/` | - | Framework integrations |

---

## Implementation Checklist

When implementing BudObserve, follow this order:

1. **Core Infrastructure**
   - [ ] Proxy providers (BudTracerProvider, BudMeterProvider)
   - [ ] BudObserve main class with logging methods
   - [ ] BudSpan wrapper class
   - [ ] Configuration management

2. **Export Pipeline**
   - [ ] OTLP exporter wrapper
   - [ ] Console exporter
   - [ ] Batch processor wrapper

3. **Features**
   - [ ] Scrubbing infrastructure
   - [ ] Message templates
   - [ ] Attribute schema (JSON Schema optional)

4. **Integrations** (in priority order)
   - [ ] FastAPI
   - [ ] SQLAlchemy/asyncpg
   - [ ] httpx
   - [ ] Redis
   - [ ] OpenAI/Anthropic
   - [ ] Celery
   - [ ] Dapr

5. **Testing & Polish**
   - [ ] Test utilities
   - [ ] Documentation
   - [ ] Type annotations

---

*Document generated for BudObserve SDK development. Based on OpenTelemetry Python SDK and Logfire v2.x analysis.*
