# Services

## BudProxy (Modified TensorZero Gateway)

**Purpose**: High-performance API gateway for LLM inference with authentication, routing, and optimization capabilities.

**Repository**: https://github.com/BudEcosystem/tensorzero

### Key Features:
- **Technology**: Built in Rust with Axum framework for <1ms P99 latency overhead
- **Multi-Provider Support**: 15+ LLM providers (OpenAI, Anthropic, AWS Bedrock, Azure, Google, etc.)
- **Dynamic Configuration**: Real-time updates via Redis without restarts
- **Authentication**: API key-based multi-tenant support with model access control
- **Intelligent Routing**: Automatic retries, fallbacks, and load balancing
- **Observability**: Built-in metrics (ClickHouse), distributed tracing (OpenTelemetry)
- **API Compatibility**: OpenAI-compatible endpoints for easy integration
- **Performance Features**: Caching, batching, mixture-of-N sampling

### Configuration:
- TOML-based configuration (`tensorzero.toml`)
- Redis for dynamic API keys and model mappings
- Environment variables for sensitive credentials

### Deployment:
- Docker image: `budstudio/budproxy:nightly`
- Default port: 3000
- Resource limits: 2 CPU, 4GB memory

---

## AIBrix

**Purpose**: Cloud-native control plane for managing LLM inference infrastructure on Kubernetes.

**Repository**: https://github.com/BudEcosystem/aibrix

### Key Features:
- **Technology**: Built in Go with Kubernetes controller-runtime
- **Autoscaling**: Three strategies - HPA, KPA, and custom APA for LLM-specific metrics
- **Intelligent Routing**: Multiple algorithms (least request, least latency, prefix cache, token-aware)
- **Multi-Model Support**: Dynamic LoRA adapter management
- **Distributed Inference**: KubeRay integration for multi-node deployments
- **Observability**: Comprehensive metrics and Grafana dashboards

### Core Components:
- **Control Plane**: PodAutoscaler, ModelAdapter, RayClusterFleet, KVCache controllers
- **Data Plane**: Envoy-based gateway with custom routing logic
- **Metadata Service**: Model registration and discovery

### Autoscaling Metrics:
- GPU cache utilization
- Request queue depth
- Token throughput (tokens/second)
- Time to first token (TTFT)
- KV cache utilization

### Integration:
- Custom Resource Definitions (CRDs) for Kubernetes-native management
- Service discovery via Kubernetes labels
- Prometheus ServiceMonitors for automatic metric collection

---

## VLLM

**Purpose**: High-performance inference engine for serving large language models.

**Repository**: https://github.com/BudEcosystem/vllm

### Key Features:
- **Technology**: Python-based with FastAPI, PyTorch, and custom CUDA kernels
- **Model Support**: Text generation, multi-modal, embeddings, classification, MoE models
- **Optimization**: PagedAttention, continuous batching, speculative decoding, prefix caching
- **Hardware Support**: NVIDIA GPUs, AMD GPUs, Intel GPUs, Google TPUs
- **Quantization**: Multiple methods (AWQ, GPTQ, FP8, INT8, BitsAndBytes)
- **API**: OpenAI-compatible endpoints with extensions

### Performance Features:
- **Memory Management**: Efficient KV cache with paging
- **Parallelism**: Tensor, pipeline, and data parallelism support
- **Dynamic Batching**: Automatic request batching for throughput
- **Streaming**: Token-by-token generation with SSE support
- **LoRA Support**: Hot-swappable adapters without model reload

### Configuration Options:
- Model selection and quantization
- GPU memory utilization control
- Batch size and sequence length limits
- Performance tuning parameters

### Deployment:
- Kubernetes-ready with health checks
- Prometheus metrics integration
- Model storage via S3/MinIO or Hugging Face Hub

---

# Architecture

## Overview

The Bud Runtime inference stack follows a microservices architecture designed for scalable, high-performance LLM serving.

### Deployment Topologies:

1. **Multi-Cluster Setup** (Production):
   - **Application Cluster**: BudProxy, BudUI, BudCluster, and other application services
   - **Inference Cluster**: AIBrix control plane and VLLM inference pods
   - Benefits: Isolation, independent scaling, security boundaries

2. **Single-Cluster Setup** (Development/Small Scale):
   - All services deployed in one Kubernetes cluster
   - Simplified networking and management
   - Cost-effective for smaller deployments

## Data Flow

```
User Request → BudProxy → AIBrix Gateway → VLLM Pod
     ↓             ↓              ↓              ↓
[Auth & Route] [Redis Config] [Load Balance] [Inference]
     ↓             ↓              ↓              ↓
[Multi-tenant] [Model Map]   [Route Logic]  [Generate]
     ↓                            ↓              ↓
[Rate Limit]                 [Autoscale]    [Stream]
     ↓                            ↓              ↓
Response ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← Response
```

### Detailed Request Flow:

1. **Client Request**: User sends inference request with API key
2. **BudProxy Authentication**: 
   - Validates API key against Redis
   - Maps user model to internal model configuration
   - Applies rate limiting and tenant policies
3. **BudProxy Routing**:
   - Determines target inference cluster/endpoint
   - Applies retry and fallback logic
   - Adds tracing headers
4. **AIBrix Gateway**:
   - Receives request via Envoy proxy
   - Applies routing algorithm (least latency, prefix cache, etc.)
   - Selects optimal VLLM pod based on metrics
5. **VLLM Processing**:
   - Loads model and LoRA adapters if needed
   - Processes request with optimizations
   - Streams tokens back through the chain
6. **Response Path**:
   - Metrics collected at each layer
   - Response streamed to client
   - Observability data sent to ClickHouse/Prometheus

## Key Architectural Decisions

### 1. **Separation of Concerns**
- **BudProxy**: Authentication, multi-tenant routing, provider abstraction
- **AIBrix**: Kubernetes-native orchestration, autoscaling, load balancing
- **VLLM**: Model serving, inference optimization, hardware acceleration

### 2. **Scalability Patterns**
- Horizontal scaling at each layer
- Request-based autoscaling with LLM-specific metrics
- Distributed caching for efficiency

### 3. **Reliability Features**
- Multiple fallback providers in BudProxy
- Health checking and automatic recovery
- Circuit breakers and timeouts

### 4. **Performance Optimizations**
- Rust-based gateway for minimal latency
- Intelligent routing based on cache availability
- Hardware-optimized inference with custom kernels

### 5. **Operational Excellence**
- GitOps-friendly configuration
- Comprehensive observability stack
- Dynamic configuration without restarts

## Integration Points

### Storage:
- **Redis**: Dynamic configuration, API keys, caching
- **ClickHouse**: Metrics and analytics
- **MinIO/S3**: Model artifact storage

### Observability:
- **Prometheus**: Metrics collection
- **Grafana**: Visualization dashboards
- **OpenTelemetry**: Distributed tracing

### Orchestration:
- **Kubernetes**: Container orchestration
- **Helm**: Deployment management
- **Dapr**: Service mesh capabilities (when integrated with other Bud services)

## Security Considerations

- API key-based authentication at gateway
- Network policies for cluster isolation
- Non-root container execution
- Secrets management via Kubernetes
- TLS encryption for inter-service communication

## Performance Characteristics

- **Latency**: <1ms gateway overhead + inference time
- **Throughput**: Scales with number of VLLM pods
- **Availability**: 99.9%+ with proper redundancy
- **Resource Efficiency**: Optimized GPU utilization with batching