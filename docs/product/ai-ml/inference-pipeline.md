# Inference Pipeline Architecture

---

## Overview

This document describes the inference request flow through Bud AI Foundry, including routing, batching, load balancing, and response streaming.

---

## Request Flow

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  Client  │───►│ Ingress  │───►│budgateway│───►│  Model   │───►│budmetrics│
│          │    │          │    │          │    │ Runtime  │    │          │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
     │               │               │               │               │
     │    HTTPS      │     HTTP      │    HTTP/      │   Metrics     │
     │               │               │    gRPC       │   Async       │
     ▼               ▼               ▼               ▼               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          Detailed Flow                                   │
│                                                                          │
│  1. Client sends OpenAI-compatible request                              │
│  2. Ingress terminates TLS, forwards to gateway                         │
│  3. Gateway authenticates via API key                                   │
│  4. Gateway resolves model → endpoint routing                           │
│  5. Gateway transforms request for provider format                      │
│  6. Runtime processes inference (batching, scheduling)                  │
│  7. Response streamed back through gateway                              │
│  8. Metrics recorded asynchronously to ClickHouse                       │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Gateway Routing

### Route Resolution

```
Request: POST /v1/chat/completions
Headers: Authorization: Bearer <api-key>
Body: { "model": "llama-3.1-70b", ... }

1. Extract model from request body
2. Lookup model → endpoint mapping
3. Resolve endpoint → provider configuration
4. Forward to appropriate backend
```

### Provider Types

| Provider | Backend | Use Case |
|----------|---------|----------|
| `local` | vLLM/SGLang on cluster | Self-hosted models |
| `openai` | OpenAI API | GPT models |
| `anthropic` | Anthropic API | Claude models |
| `azure` | Azure OpenAI | Enterprise OpenAI |
| `together` | Together AI | Hosted open models |

### Fallback Chains

Configure automatic failover:

```toml
[[fallback_chains]]
primary = "local-vllm"
fallbacks = ["openai", "anthropic"]
conditions = ["timeout", "rate_limit", "server_error"]
```

---

## Batching

### Runtime Batching (vLLM)

vLLM implements continuous batching:

- Requests queued as they arrive
- Batched dynamically based on:
  - Sequence length
  - Available GPU memory
  - Configured batch size
- No fixed batch windows

### Configuration

```yaml
batching:
  max_num_seqs: 256        # Max concurrent sequences
  max_num_batched_tokens: 4096  # Max tokens per batch
  swap_space_gb: 4         # CPU offload space
```

---

## Load Balancing

### Request Distribution

Gateway distributes across replicas:

```
┌───────────────┐
│  budgateway   │
└───────┬───────┘
        │
   Load Balancer
   (Round Robin)
        │
   ┌────┴────┐────────┐
   ▼         ▼        ▼
┌──────┐  ┌──────┐  ┌──────┐
│Pod 1 │  │Pod 2 │  │Pod 3 │
└──────┘  └──────┘  └──────┘
```

### Balancing Strategies

| Strategy | Description |
|----------|-------------|
| `round_robin` | Equal distribution |
| `least_connections` | Prefer idle pods |
| `weighted` | Based on pod capacity |

---

## Streaming

### Server-Sent Events (SSE)

Streaming responses for chat completions:

```http
POST /v1/chat/completions
Content-Type: application/json

{
  "model": "llama-3.1-70b",
  "messages": [...],
  "stream": true
}
```

Response:

```http
HTTP/1.1 200 OK
Content-Type: text/event-stream

data: {"choices":[{"delta":{"content":"Hello"}}]}
data: {"choices":[{"delta":{"content":" world"}}]}
data: {"choices":[{"delta":{"content":"!"}}]}
data: [DONE]
```

### Streaming Architecture

```
Client ◄──SSE──► Gateway ◄──SSE──► Runtime
         │                │
    Buffered          Token-by-
    Events            Token
```

---

## Error Handling

### Error Categories

| Code | Category | Action |
|------|----------|--------|
| 400 | Bad Request | Return error, no retry |
| 401 | Unauthorized | Return error, no retry |
| 429 | Rate Limited | Queue or fallback |
| 500 | Server Error | Retry or fallback |
| 503 | Unavailable | Retry or fallback |
| 504 | Timeout | Retry or fallback |

### Retry Policy

```yaml
retry:
  max_attempts: 3
  initial_delay_ms: 100
  max_delay_ms: 5000
  backoff_multiplier: 2
  retryable_codes: [429, 500, 502, 503, 504]
```

---

## Metrics Collection

### Metrics Recorded

| Metric | Type | Description |
|--------|------|-------------|
| `request_count` | Counter | Total requests |
| `request_latency_ms` | Histogram | Full request latency |
| `ttft_ms` | Histogram | Time to first token |
| `tokens_input` | Counter | Input tokens |
| `tokens_output` | Counter | Output tokens |
| `error_count` | Counter | Failed requests |

### Collection Flow

```
Gateway → Async Queue → budmetrics → ClickHouse
                              ↓
                          Prometheus
                          (scrape)
```

---

## Performance Tuning

### Gateway Tuning

| Parameter | Description | Default |
|-----------|-------------|---------|
| `max_connections` | Connection pool size | 1000 |
| `request_timeout_ms` | Request timeout | 30000 |
| `keepalive_timeout_ms` | Connection keepalive | 60000 |

### Runtime Tuning

| Parameter | Impact |
|-----------|--------|
| `tensor_parallel_size` | GPU utilization |
| `max_num_seqs` | Concurrent requests |
| `gpu_memory_utilization` | Memory efficiency |
| `max_model_len` | Context window |

---

## Related Documents

- [Model Deployment Guide](./model-deployment.md)
- [API Gateway Security](../security/api-gateway-security.md)
- [Performance Tuning Guide](./performance-tuning.md)
