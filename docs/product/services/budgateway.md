# budgateway - Low-Level Design
---

## 1. Document Overview

### 1.1 Purpose

This LLD provides build-ready technical specifications for budgateway, the high-performance Rust-based API gateway of Bud AI Foundry. It is forked from TensorZero and handles all inference traffic with OpenAI-compatible APIs, multi-provider routing, and sub-millisecond latency.

### 1.2 Scope

**In Scope:**
- OpenAI-compatible inference API (chat, completions, embeddings, audio, images)
- Multi-provider routing with fallback chains
- Request/response streaming (SSE)
- API key authentication with RSA decryption
- Rate limiting and usage limiting
- Metrics collection for budmetrics
- Guardrails and blocking rules
- GeoIP and user-agent analytics

**Out of Scope:**
- User/project management (handled by budapp)
- Model registry (handled by budmodel)
- Cluster management (handled by budcluster)
- Performance simulation (handled by budsim)

---

## 2. System Context & Assumptions

### 2.1 Business Assumptions

- Inference traffic is latency-sensitive (<1ms P99 gateway overhead target)
- Multiple AI providers serve the same model for redundancy
- API keys are stored encrypted in Redis by budapp
- Clients use OpenAI-compatible SDK interfaces
- Streaming responses are common for chat completions

### 2.2 Technical Assumptions

- Rust 1.70+ with async runtime (Tokio)
- Redis available for authentication and rate limiting
- ClickHouse available for observability (optional)
- Model runtimes accessible via HTTP (Bud, OpenAI API, etc.)
- TOML configuration files mounted at runtime

### 2.3 Constraints

| Constraint Type | Description | Impact |
|-----------------|-------------|--------|
| Latency | <1ms P99 gateway overhead | Minimal middleware |
| Memory | ~50MB baseline footprint | MiMalloc allocator |
| Connections | 10,000+ concurrent | Async I/O |
| Audio File Size | 25MB max upload | Multipart limits |

### 2.4 External Dependencies

| Dependency | Type | Failure Impact | Fallback Strategy |
|------------|------|----------------|-------------------|
| Redis | Optional | No auth/rate limiting | Pass through |
| ClickHouse | Optional | No observability | Local logging |
| Model Runtimes | Required | Inference fails | Fallback chain |
| budapp | Producer | No API key updates | Use cached |
| budmetrics | Consumer | No metrics storage | Discard |

---

## 3. Detailed Architecture

### 3.1 Component Overview

![Budgateway component overview](./images/budgateway-overview.png)
#### 3.3.1 Config Parser

**Purpose:** Load and validate TOML configuration

**Key Structures:**

#### 3.3.2 Model Resolution

**Purpose:** Map client request to provider routing

**Flow:**
1. Extract model name from request
2. Look up model configuration
3. Verify capability (chat, embedding, audio, etc.)
4. Return provider routing list

#### 3.3.3 Provider System

**Purpose:** Abstract AI provider implementations

**Supported Providers:**

| Provider | Type | Capabilities |
|----------|------|--------------|
| OpenAI | `openai` | chat, embedding, audio, images, moderation |
| Anthropic | `anthropic` | chat |
| Azure OpenAI | `azure` | chat, embedding |
| Together AI | `together` | chat, images |
| Anyscale | `anyscale` | chat |
| Bud/Local | `openai` | chat, embedding |

**Provider Trait:**

---

## 4. Data Design

### 4.1 Configuration Schema

**Gateway Configuration:**

**Model Configuration:**

### 4.2 Credential Storage (Redis)

**Key Format:** `api_key:{api_key_id}`

**Value Schema:**

### 4.3 Analytics Events (ClickHouse)

**Inference Event Schema:**

---

## 5. API & Interface Design

### 5.2 Management Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/metrics` | Prometheus metrics |
| GET | `/v1/models` | List available models |

### 5.3 Internal Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/inference` | TensorZero native inference |
| POST | `/batch_inference` | Batch inference |
| POST | `/feedback` | Inference feedback |

---

## 6. Configuration & Environment

### 6.1 Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| TENSORZERO_CONFIG_PATH | No | tensorzero.toml | Config file path |
| TENSORZERO_REDIS_URL | No | - | Redis for auth/rate limit |
| TENSORZERO_CLICKHOUSE_URL | No | - | ClickHouse for analytics |
| TENSORZERO_RSA_PRIVATE_KEY_PATH | No | - | RSA key for decryption |
| TENSORZERO_RSA_PRIVATE_KEY_PASSWORD | No | - | Key password |
| OPENAI_API_KEY | No | - | OpenAI provider key |
| ANTHROPIC_API_KEY | No | - | Anthropic provider key |
| OTEL_EXPORTER_OTLP_TRACES_ENDPOINT | No | - | OTLP endpoint |

### 6.2 Feature Flags

| Flag | Description |
|------|-------------|
| `gateway.debug` | Enable debug logging |
| `gateway.authentication.enabled` | Enable API key auth |
| `gateway.export.otlp.traces.enabled` | Enable OTLP tracing |

### 6.3 Provider-Specific Configuration

**OpenAI:**

**Azure:**

---

## 7. Security Design

### 7.2 RSA Encryption Details

| Property | Value |
|----------|-------|
| Algorithm | RSA-OAEP |
| Hash | SHA-256 |
| Key Format | PEM (PKCS#1 or PKCS#8) |
| Encoding | Hex or Base64 |
| Key Size | 4096 bits (recommended) |

---

## 8. Performance & Scalability

### 8.1 Performance Targets

| Metric | Target |
|--------|--------|
| Gateway Latency (P99) | <1ms |
| Max Concurrent Connections | 10,000+ |
| Memory Footprint | ~50MB |
| Throughput | 100,000+ req/s |

### 8.2 Optimization Techniques

| Technique | Benefit |
|-----------|---------|
| MiMalloc allocator | Better multi-threaded allocation |
| Zero-copy streaming | Minimal memory for large responses |
| Connection pooling | Reuse provider connections |
| Async I/O (Tokio) | Non-blocking concurrency |
| Arc for config | Shared immutable config |

---

## 9. Deployment & Infrastructure

### 10.2 Resource Requirements

| Component | CPU | Memory | Notes |
|-----------|-----|--------|-------|
| budgateway | 500m-4 | 128Mi-512Mi | Scales with connections |

### 10.4 Configuration Mounting
