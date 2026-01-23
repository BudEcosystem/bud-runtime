# budgateway Service Documentation

---

## Overview

budgateway is a high-performance Rust service that handles all inference traffic with an OpenAI-compatible API. It routes requests to model runtimes or external AI providers with sub-millisecond latency.

---

## Service Identity

| Property | Value |
|----------|-------|
| **App ID** | budgateway |
| **Port** | 3000 |
| **Language** | Rust 1.70+ |
| **Framework** | Axum |
| **Configuration** | TOML |

---

## Responsibilities

- OpenAI-compatible inference API
- Multi-provider routing with fallback chains
- Request/response streaming
- API key authentication (RSA decryption)
- Metrics collection for budmetrics
- Rate limiting and request validation

---

## API Endpoints

### Inference (OpenAI-compatible)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/chat/completions` | Chat completions |
| POST | `/v1/completions` | Text completions |
| POST | `/v1/embeddings` | Generate embeddings |
| POST | `/v1/audio/transcriptions` | Audio transcription |
| POST | `/v1/audio/speech` | Text-to-speech |
| POST | `/v1/images/generations` | Image generation |
| POST | `/v1/responses` | Structured responses |

### Management

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/metrics` | Prometheus metrics |
| GET | `/v1/models` | List available models |

---

## Configuration

Configuration is TOML-based in `config/` directory:

```toml
# config/gateway.toml

[server]
host = "0.0.0.0"
port = 3000

[auth]
enabled = true
rsa_public_key_path = "/keys/rsa-public-key.pem"

[routing]
default_timeout_ms = 30000
max_retries = 3

[[providers]]
name = "local-vllm"
type = "openai"
base_url = "http://vllm-runtime:8000"
models = ["llama-3.1-8b", "llama-3.1-70b"]

[[providers]]
name = "openai"
type = "openai"
base_url = "https://api.openai.com"
api_key_env = "OPENAI_API_KEY"
models = ["gpt-4", "gpt-3.5-turbo"]

[[fallback_chains]]
primary = "local-vllm"
fallbacks = ["openai"]
```

---

## Provider Types

| Provider | Description |
|----------|-------------|
| `openai` | OpenAI-compatible API |
| `anthropic` | Anthropic Claude API |
| `azure` | Azure OpenAI |
| `together` | Together AI |
| `anyscale` | Anyscale Endpoints |
| `local` | Local model runtime |

---

## Performance Characteristics

| Metric | Value |
|--------|-------|
| **Gateway Latency** | <1ms P99 |
| **Max Concurrent Connections** | 10,000+ |
| **Streaming Support** | Yes (SSE) |
| **Memory Footprint** | ~50MB |

---

## Development

```bash
cd services/budgateway

# Format
cargo fmt

# Lint
cargo clippy --all-targets --all-features -- -D warnings

# Test
cargo test --workspace

# Build release
cargo build --release

# Run
cargo run -- --config config/gateway.toml
```

---

## Related Documents

- [Inference Pipeline Architecture](../ai-ml/inference-pipeline.md)
- [API Gateway Security](../security/api-gateway-security.md)
