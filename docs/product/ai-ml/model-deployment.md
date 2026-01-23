# Model Deployment Guide

---

## Overview

This guide covers the end-to-end model deployment workflow in Bud AI Foundry, from model selection through deployment, versioning, scaling, and monitoring.

---

## Deployment Flow

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Select     │───►│  Configure   │───►│   Deploy     │───►│   Monitor    │
│   Model      │    │   & Optimize │    │   Runtime    │    │   & Scale    │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
   budmodel            budsim            budcluster          budmetrics
   (Registry)       (Optimizer)        (Deployment)        (Observability)
```

---

## Stage 1: Model Selection

### From Model Registry

1. Browse available models in budadmin dashboard
2. Filter by:
   - Architecture (Llama, Mistral, Qwen, etc.)
   - Size (7B, 13B, 70B, 405B parameters)
   - License type (Apache, commercial, etc.)
   - Performance benchmarks

### Custom Model Registration

1. Upload model artifacts to MinIO storage
2. Register model metadata via API:
   ```json
   {
     "name": "my-custom-model",
     "architecture": "llama",
     "parameter_count": 7000000000,
     "context_length": 8192,
     "source_path": "s3://models/my-custom-model"
   }
   ```
3. Security scan triggers automatically (ClamAV)
4. Model appears in registry after scan passes

---

## Stage 2: Configuration & Optimization

### Automatic Optimization (Recommended)

budsim analyzes model and hardware to recommend optimal configuration:

1. Select target cluster
2. Define performance targets:
   - Maximum latency (TTFT, total)
   - Minimum throughput (tokens/sec)
   - Budget constraints
3. budsim runs optimization:
   - XGBoost predicts performance for configurations
   - Genetic algorithm finds optimal parameters
4. Review recommended configuration:
   - Tensor Parallelism (TP)
   - Pipeline Parallelism (PP)
   - Batch size
   - Max sequences
   - Replica count

### Manual Configuration

For advanced users who want direct control:

```yaml
deployment:
  runtime: vllm
  config:
    tensor_parallel_size: 4
    pipeline_parallel_size: 1
    max_model_len: 8192
    max_num_seqs: 256
    gpu_memory_utilization: 0.9
  replicas: 2
  resources:
    gpu_type: nvidia-a100-80gb
    gpu_count: 4
```

---

## Stage 3: Deployment

### Deployment Patterns

**Single Endpoint** - Standard deployment for most use cases:

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │────►│ budgateway  │────►│  Model Pod   │
│             │     │             │     │  (Model A)  │
└─────────────┘     └─────────────┘     └─────────────┘
```

**Multi-Replica (High Availability)** - Multiple replicas for load distribution:

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │────►│ budgateway  │──┬──│  Model Pod 1 │
│             │     │             │  │  └─────────────┘
└─────────────┘     └─────────────┘  │  ┌─────────────┐
                                     ├──│  Model Pod 2 │
                                     │  └─────────────┘
                                     │  ┌─────────────┐
                                     └──│  Model Pod 3 │
                                        └─────────────┘
```

**Multi-Model (Router Pattern)** - Single gateway routing to multiple models:

```
                                        ┌─────────────┐
                                     ┌──│  Llama 70B  │
┌─────────────┐     ┌─────────────┐  │  └─────────────┘
│   Client    │────►│ budgateway  │──┤  ┌─────────────┐
│             │     │  (Router)   │  ├──│  Mistral 7B │
└─────────────┘     └─────────────┘  │  └─────────────┘
                                     │  ┌─────────────┐
                                     └──│  GPT-4 API  │
                                        └─────────────┘
```

### Deployment Steps

**1. Create Endpoint**

```bash
curl -X POST /api/endpoints \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "name": "my-llm-endpoint",
    "project_id": "uuid",
    "model_id": "uuid",
    "cluster_id": "uuid"
  }'
```

**2. Configure Deployment**

```bash
curl -X PUT /api/endpoints/{id}/config \
  -d '{
    "runtime": "vllm",
    "optimization_method": "REGRESSOR",
    "performance_targets": {
      "max_latency_ms": 2000,
      "min_throughput_tps": 100
    }
  }'
```

**3. Deploy**

```bash
curl -X POST /api/endpoints/{id}/deploy
```

**4. Monitor Status**

```bash
curl /api/endpoints/{id}

# Response
{
  "id": "uuid",
  "status": "RUNNING",
  "deployment": {
    "runtime": "vllm",
    "replicas": 2,
    "ready_replicas": 2
  },
  "inference_url": "https://inference.example.com/v1"
}
```

### Deployment Process (Internal)

1. **Validation**
   - Verify cluster has required resources
   - Check model compatibility with runtime
   - Validate configuration parameters

2. **Model Transfer**
   - Transfer model from registry to cluster storage
   - Uses efficient streaming for large models

3. **Runtime Deployment**
   - Generate Helm values from configuration
   - Deploy vLLM/SGLang pod with Helm
   - Configure service and ingress

4. **Health Checks**
   - Wait for pod readiness
   - Verify model loads successfully
   - Test inference endpoint


---

## Versioning Strategies

### Blue-Green Deployment

1. Deploy new version alongside existing
2. Validate new version
3. Switch traffic atomically
4. Remove old version

```yaml
# Endpoint A (current - blue)
name: my-model-v1
model_version: 1.0.0
traffic_weight: 100

# Endpoint B (new - green)
name: my-model-v2
model_version: 2.0.0
traffic_weight: 0

# After validation, swap weights
```

---

## Stage 4: Scaling

### Horizontal Scaling (Replicas)

```bash
# Scale up
curl -X POST /api/endpoints/{id}/scale -d '{"replicas": 4}'

# Scale down
curl -X POST /api/endpoints/{id}/scale -d '{"replicas": 2}'
```

### Auto-Scaling

Configure HPA (Horizontal Pod Autoscaler):

```yaml
autoscaling:
  enabled: true
  min_replicas: 2
  max_replicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 80
    - type: External
      external:
        metric:
          name: inference_queue_depth
        target:
          type: Value
          value: 100
```

---

## Stage 5: Monitoring

### Metrics Collected

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| `inference_latency_p99` | 99th percentile latency | >2s |
| `ttft_p99` | Time to first token | >500ms |
| `throughput` | Tokens per second | <target |
| `gpu_utilization` | GPU compute usage | >95% sustained |
| `queue_depth` | Pending requests | >100 |

### Continuous Optimization

1. budmetrics collects performance data
2. Compare actual vs predicted performance
3. budsim refines model with real-world data
4. Recommendations surface in dashboard

---

## Configuration Reference

### Runtime Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `runtime` | Inference engine (vllm, sglang, tensorrt-llm) | vllm |
| `tensor_parallel_size` | GPUs for tensor parallelism | 1 |
| `pipeline_parallel_size` | Stages for pipeline parallelism | 1 |
| `max_model_len` | Maximum context length | Model default |
| `max_num_seqs` | Maximum concurrent sequences | 256 |
| `gpu_memory_utilization` | GPU memory fraction | 0.9 |

### Resource Requests

| Parameter | Description |
|-----------|-------------|
| `gpu_type` | GPU model (nvidia-a100-80gb, etc.) |
| `gpu_count` | Number of GPUs |
| `cpu_cores` | CPU cores |
| `memory_gb` | Memory in GB |

---

## Common Workflows

### New Model Deployment

```
1. Select model from registry
2. Choose target cluster
3. Run optimization (budsim)
4. Review and approve configuration
5. Deploy endpoint
6. Verify with test traffic
7. Update DNS/routing
8. Monitor performance
```

### Model Update (A/B Testing)

```
1. Deploy new model version as separate endpoint
2. Configure traffic split (90/10)
3. Monitor both versions
4. Gradually shift traffic
5. Remove old version when confident
```

### Performance Troubleshooting

```
1. Check metrics in Grafana
2. Identify bottleneck (GPU, memory, network)
3. Review configuration parameters
4. Re-run optimization with updated constraints
5. Apply new configuration
6. Verify improvement
```

---

## Troubleshooting

### Deployment Stuck in PENDING

1. Check cluster has available resources
2. Verify node selectors match available nodes
3. Check for GPU scheduling issues

### Model Load Failure

1. Verify model path is accessible
2. Check model format compatibility
3. Review GPU memory requirements

### High Latency

1. Check GPU utilization
2. Review batch size settings
3. Consider additional replicas

---

## Best Practices

### Model Selection
- Start with smaller models for evaluation
- Consider license restrictions for production
- Validate model on representative workloads

### Configuration
- Use automatic optimization for initial deployment
- Monitor actual performance before manual tuning
- Leave 10-20% GPU memory headroom

### Deployment
- Deploy to staging cluster first
- Validate with production-like traffic
- Use canary deployments for updates

### Monitoring
- Set up alerts for latency SLOs
- Monitor token usage for cost management
- Review metrics weekly for optimization opportunities

---

## Related Documents

- [BudSim User Guide](./budsim-user-guide.md)
- [Model Monitoring Guide](./model-monitoring.md)
- [Resource Optimization Guide](./resource-optimization.md)
- [Scaling Guidelines](./scaling-guidelines.md)
