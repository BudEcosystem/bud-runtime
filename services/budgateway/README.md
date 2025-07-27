# BudGateway Service

[![License](https://img.shields.io/badge/License-AGPL%203.0-blue.svg)](https://opensource.org/licenses/AGPL-3.0)
[![Rust](https://img.shields.io/badge/rust-1.70+-orange.svg)](https://www.rust-lang.org/)
[![Tokio](https://img.shields.io/badge/tokio-async-blue.svg)](https://tokio.rs/)
[![Redis](https://img.shields.io/badge/redis-6.0+-red.svg)](https://redis.io/)

A high-performance API gateway service built in Rust for model inference routing and load balancing. BudGateway provides enterprise-grade performance, reliability, and scalability for AI/ML model serving with sub-millisecond latency overhead.

## 🚀 Features

- **High-Performance Routing**: Sub-millisecond latency overhead with async Rust architecture
- **Load Balancing**: Intelligent request distribution across multiple model endpoints
- **Multi-Provider Support**: Routes requests to various AI/ML serving engines (VLLM, SGLang, LiteLLM)
- **Rate Limiting**: Configurable rate limiting per user, model, and endpoint
- **Circuit Breaker**: Automatic failover and circuit breaking for unhealthy endpoints
- **Request/Response Transformation**: Protocol conversion and payload transformation
- **Metrics & Monitoring**: Comprehensive metrics collection with Prometheus integration
- **Authentication & Authorization**: JWT-based authentication with role-based access control
- **Caching**: Intelligent response caching with Redis backend
- **Health Checking**: Active health monitoring of downstream services

## 📋 Table of Contents

- [Architecture](#-architecture)
- [Prerequisites](#-prerequisites)
- [Quick Start](#-quick-start)
- [Development](#-development)
- [Configuration](#-configuration)
- [API Documentation](#-api-documentation)
- [Deployment](#-deployment)
- [Testing](#-testing)
- [Troubleshooting](#-troubleshooting)

## 🏗️ Architecture

### Service Structure

```
budgateway/
├── src/
│   ├── main.rs             # Application entry point
│   ├── config/             # Configuration management
│   │   ├── mod.rs
│   │   ├── gateway.rs      # Gateway configuration
│   │   └── routes.rs       # Route configuration
│   ├── gateway/            # Core gateway functionality
│   │   ├── mod.rs
│   │   ├── router.rs       # Request routing logic
│   │   ├── load_balancer.rs # Load balancing algorithms
│   │   ├── circuit_breaker.rs # Circuit breaker implementation
│   │   └── middleware.rs   # Request/response middleware
│   ├── providers/          # Model provider integrations
│   │   ├── mod.rs
│   │   ├── vllm.rs        # VLLM integration
│   │   ├── sglang.rs      # SGLang integration
│   │   ├── litellm.rs     # LiteLLM integration
│   │   └── openai.rs      # OpenAI-compatible APIs
│   ├── auth/               # Authentication & authorization
│   │   ├── mod.rs
│   │   ├── jwt.rs         # JWT token validation
│   │   └── rbac.rs        # Role-based access control
│   ├── cache/              # Caching layer
│   │   ├── mod.rs
│   │   ├── redis.rs       # Redis cache implementation
│   │   └── strategies.rs  # Caching strategies
│   ├── metrics/            # Metrics collection
│   │   ├── mod.rs
│   │   ├── prometheus.rs  # Prometheus metrics
│   │   └── collectors.rs  # Custom metric collectors
│   └── utils/              # Shared utilities
│       ├── mod.rs
│       ├── health.rs      # Health check utilities
│       └── tracing.rs     # Distributed tracing
├── config/                 # Configuration files
│   ├── gateway.toml        # Main gateway configuration
│   ├── routes.toml         # Route definitions
│   └── providers.toml      # Provider configurations
├── tests/                  # Test suite
│   ├── integration/        # Integration tests
│   ├── load/              # Load tests
│   └── unit/              # Unit tests
├── benchmarks/             # Performance benchmarks
├── docker/                 # Docker configurations
└── deploy/                 # Deployment scripts
```

### Core Components

- **Router Engine**: High-performance request routing with pattern matching
- **Load Balancer**: Multiple algorithms (round-robin, least-connections, weighted)
- **Circuit Breaker**: Automatic failure detection and recovery
- **Provider Adapters**: Pluggable adapters for different AI/ML serving engines
- **Authentication Layer**: JWT validation and role-based access control
- **Cache Manager**: Intelligent caching with TTL and invalidation strategies
- **Metrics Collector**: Real-time performance and usage metrics

### Request Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │────▶│    Auth     │────▶│   Router    │
│   Request   │     │Middleware   │     │   Engine    │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                    ┌──────────────────────────┼──────────────────────────┐
                    │                          │                          │
            ┌───────▼───────┐        ┌────────▼────────┐        ┌────────▼────────┐
            │     Cache     │        │  Load Balancer  │        │ Circuit Breaker │
            │    Check      │        │   Selection     │        │    Health       │
            └───────┬───────┘        └────────┬────────┘        └────────┬────────┘
                    │                         │                          │
                    └─────────────────────────┼──────────────────────────┘
                                              │
                                    ┌─────────▼─────────┐
                                    │   Provider        │
                                    │   Proxy           │
                                    └─────────┬─────────┘
                                              │
                                    ┌─────────▼─────────┐
                                    │   Response        │
                                    │   Transform       │
                                    └───────────────────┘
```

## 📦 Prerequisites

### Required

- **Rust** 1.70+
- **Docker** and Docker Compose
- **Git**

### Service Dependencies

- **Redis** - Caching and session management
- **Model Providers** - At least one AI/ML serving endpoint (VLLM, SGLang, etc.)

### Optional Dependencies

- **Prometheus** - Metrics collection
- **Jaeger** - Distributed tracing
- **Grafana** - Metrics visualization

## 🚀 Quick Start

### 1. Clone and Setup

```bash
# Clone the repository
git clone https://github.com/BudEcosystem/bud-stack.git
cd bud-stack/services/budgateway

# Setup environment
cp .env.sample .env
# Edit .env with your configuration
```

### 2. Configure Environment

Edit `.env` file with required configurations:

```bash
# Gateway Configuration
GATEWAY_HOST=0.0.0.0
GATEWAY_PORT=8080
WORKERS=4
LOG_LEVEL=info

# Redis Configuration
REDIS_URL=redis://localhost:6379
REDIS_POOL_SIZE=10

# Authentication
JWT_SECRET=your-jwt-secret
JWT_EXPIRATION=3600

# Metrics
ENABLE_METRICS=true
METRICS_PORT=9090

# Tracing
ENABLE_TRACING=true
JAEGER_ENDPOINT=http://localhost:14268/api/traces

# Provider Endpoints
VLLM_ENDPOINTS=http://vllm-1:8000,http://vllm-2:8000
SGLANG_ENDPOINTS=http://sglang-1:8001
LITELLM_ENDPOINT=http://litellm:4000
```

### 3. Configure Gateway

Edit `config/gateway.toml`:

```toml
[gateway]
host = "0.0.0.0"
port = 8080
workers = 4
max_connections = 1000
request_timeout = 30
keepalive_timeout = 60

[rate_limiting]
enabled = true
requests_per_minute = 1000
burst_capacity = 100

[circuit_breaker]
failure_threshold = 5
timeout_duration = 60
half_open_max_calls = 3

[cache]
enabled = true
default_ttl = 300
max_memory = "1GB"
```

### 4. Start Development Environment

```bash
# Build the project
cargo build --release

# Start Redis
docker-compose up -d redis

# Run the gateway
cargo run --release

# Or start with development configuration
./deploy/start_dev.sh

# Gateway will be available at:
# API: http://localhost:8080
# Metrics: http://localhost:9090/metrics
```

## 💻 Development

### Code Quality

```bash
# Format code
cargo fmt

# Lint code
cargo clippy

# Run tests
cargo test

# Run tests with coverage
cargo tarpaulin --out html

# Check for security vulnerabilities
cargo audit
```

### Configuration Management

```bash
# Validate configuration
cargo run -- --validate-config

# Reload configuration (without restart)
curl -X POST http://localhost:8080/admin/reload-config
```

### Load Testing

```bash
# Simple load test
cargo run --bin load-test -- --url http://localhost:8080 --requests 1000 --concurrency 10

# Advanced load test with wrk
wrk -t12 -c400 -d30s --latency http://localhost:8080/v1/models

# Artillery.js load test
artillery run tests/load/artillery-config.yml
```

## ⚙️ Configuration

### Route Configuration

Edit `config/routes.toml`:

```toml
[[routes]]
path = "/v1/models"
method = "GET"
provider = "vllm"
load_balancer = "round_robin"
cache_ttl = 300

[[routes]]
path = "/v1/chat/completions"
method = "POST"
provider = "vllm"
load_balancer = "least_connections"
rate_limit = 100
auth_required = true

[[routes]]
path = "/v1/completions"
method = "POST"
provider = "sglang"
load_balancer = "weighted"
timeout = 60
```

### Provider Configuration

Edit `config/providers.toml`:

```toml
[providers.vllm]
name = "VLLM Provider"
endpoints = [
    { url = "http://vllm-1:8000", weight = 1 },
    { url = "http://vllm-2:8000", weight = 1 }
]
health_check_path = "/health"
health_check_interval = 30

[providers.sglang]
name = "SGLang Provider"
endpoints = [
    { url = "http://sglang-1:8001", weight = 2 },
    { url = "http://sglang-2:8001", weight = 1 }
]
health_check_path = "/v1/health"
health_check_interval = 15

[providers.litellm]
name = "LiteLLM Provider"
endpoints = [
    { url = "http://litellm:4000", weight = 1 }
]
```

## 📚 API Documentation

### Gateway Management Endpoints

#### Health Check
```
GET /health
```

#### Metrics
```
GET /metrics
```

#### Configuration Reload
```
POST /admin/reload-config
```

#### Route Information
```
GET /admin/routes
```

### Proxy Endpoints

The gateway proxies requests to configured model providers:

#### Model List
```
GET /v1/models
```

#### Chat Completions
```
POST /v1/chat/completions
Content-Type: application/json
Authorization: Bearer <token>

{
  "model": "llama-2-7b",
  "messages": [
    {
      "role": "user",
      "content": "Hello, how are you?"
    }
  ],
  "max_tokens": 100,
  "temperature": 0.7
}
```

#### Text Completions
```
POST /v1/completions
Content-Type: application/json

{
  "model": "llama-2-7b",
  "prompt": "Once upon a time",
  "max_tokens": 100,
  "temperature": 0.7
}
```

### Authentication

The gateway supports JWT-based authentication:

```bash
# Include JWT token in requests
curl -H "Authorization: Bearer <jwt-token>" \
     -H "Content-Type: application/json" \
     -d '{"model": "llama-2-7b", "prompt": "Hello"}' \
     http://localhost:8080/v1/completions
```

### Rate Limiting

Rate limits are enforced per user/IP:

```
Rate-Limit-Limit: 1000
Rate-Limit-Remaining: 999
Rate-Limit-Reset: 1642089600
```

## 🚀 Deployment

### Docker Deployment

```bash
# Build Docker image
docker build -t budgateway:latest .

# Run with docker-compose
docker-compose up -d

# Check logs
docker-compose logs -f budgateway
```

### Kubernetes Deployment

```bash
# Deploy with Helm
helm install budgateway ./charts/budgateway/

# Or as part of full stack
cd ../../infra/helm/bud
helm dependency update
helm install bud .
```

### Production Configuration

```yaml
# values.yaml for Helm
budgateway:
  replicas: 3
  resources:
    requests:
      memory: "512Mi"
      cpu: "500m"
    limits:
      memory: "2Gi"
      cpu: "2000m"
  env:
    - name: WORKERS
      value: "8"
    - name: LOG_LEVEL
      value: "info"
  service:
    type: LoadBalancer
    port: 80
    targetPort: 8080
  ingress:
    enabled: true
    annotations:
      nginx.ingress.kubernetes.io/rate-limit: "1000"
    hosts:
      - host: gateway.yourdomain.com
        paths:
          - path: /
            pathType: Prefix
```

## 🧪 Testing

### Unit Tests

```bash
# Run all tests
cargo test

# Run specific test
cargo test test_load_balancer

# Run tests with output
cargo test -- --nocapture
```

### Integration Tests

```bash
# Start test dependencies
docker-compose -f docker-compose.test.yml up -d

# Run integration tests
cargo test --test integration

# Clean up
docker-compose -f docker-compose.test.yml down
```

### Load Tests

```bash
# HTTP load test
cargo run --bin http-load-test

# WebSocket load test (if applicable)
cargo run --bin ws-load-test

# Custom benchmark
cargo bench
```

### Performance Benchmarks

```bash
# Run benchmarks
cargo bench

# Profile with perf
cargo build --release
perf record --call-graph=dwarf ./target/release/budgateway
perf report
```

## 🔧 Troubleshooting

### Common Issues

#### High Memory Usage
```bash
# Error: Gateway consuming too much memory
# Solution: Adjust cache settings and connection limits
# In gateway.toml:
[cache]
max_memory = "512MB"

[gateway]
max_connections = 500
```

#### Connection Pool Exhausted
```bash
# Error: Cannot acquire connection from pool
# Solution: Increase Redis pool size
export REDIS_POOL_SIZE=20

# Or in config:
[redis]
pool_size = 20
max_connections = 100
```

#### Circuit Breaker Triggered
```bash
# Error: Circuit breaker open for provider
# Solution: Check provider health and adjust thresholds
curl http://vllm-endpoint:8000/health

# Adjust in gateway.toml:
[circuit_breaker]
failure_threshold = 10
timeout_duration = 30
```

#### Rate Limiting False Positives
```bash
# Error: Rate limit exceeded unexpectedly
# Solution: Check rate limit configuration and Redis state
redis-cli GET rate_limit:user:123

# Adjust limits in gateway.toml:
[rate_limiting]
requests_per_minute = 2000
burst_capacity = 200
```

### Debug Mode

Enable detailed logging:
```bash
# Set log level
export LOG_LEVEL=debug
export RUST_LOG=budgateway=debug

# Enable request tracing
export ENABLE_REQUEST_TRACING=true

# Start with debug symbols
cargo run --features debug
```

### Performance Monitoring

```bash
# Check gateway metrics
curl http://localhost:9090/metrics

# Monitor connection stats
curl http://localhost:8080/admin/stats

# Check provider health
curl http://localhost:8080/admin/providers/health
```

### Profiling

```bash
# CPU profiling
cargo flamegraph --bin budgateway

# Memory profiling
valgrind --tool=massif ./target/release/budgateway

# Async profiling
tokio-console ./target/release/budgateway
```

## 🤝 Contributing

Please see the main [Bud Stack Contributing Guide](../../CONTRIBUTING.md).

### Service-Specific Guidelines

1. Follow Rust best practices and idioms
2. Add benchmarks for performance-critical code
3. Write comprehensive integration tests
4. Update configuration documentation
5. Ensure memory safety and thread safety
6. Profile performance impact of changes

## 📄 License

This project is licensed under the AGPL-3.0 License - see the [LICENSE](../../LICENSE) file for details.

## 🔗 Related Documentation

- [Main Bud Stack README](../../README.md)
- [CLAUDE.md Development Guide](../../CLAUDE.md)
- [Gateway Metrics](http://localhost:9090/metrics) (when running)
- [Configuration Reference](./docs/configuration.md)
- [Provider Integration Guide](./docs/provider-integration.md)
- [Performance Tuning Guide](./docs/performance-tuning.md)

# Acknowlegment

- Thanks to TensorZero for providing intial version of the gateway. https://github.com/tensorzero/tensorzero
