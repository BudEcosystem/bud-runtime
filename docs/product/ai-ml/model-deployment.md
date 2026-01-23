# Model Deployment Guide

---

## Overview

This guide covers model deployment patterns, versioning strategies, and scaling approaches in Bud AI Foundry.

---

## Deployment Patterns

### Single Endpoint

Standard deployment for most use cases:

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │────►│ budgateway  │────►│  vLLM Pod   │
│             │     │             │     │  (Model A)  │
└─────────────┘     └─────────────┘     └─────────────┘
```

### Multi-Replica (High Availability)

Multiple replicas for load distribution:

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │────►│ budgateway  │──┬──│  vLLM Pod 1 │
│             │     │             │  │  └─────────────┘
└─────────────┘     └─────────────┘  │  ┌─────────────┐
                                     ├──│  vLLM Pod 2 │
                                     │  └─────────────┘
                                     │  ┌─────────────┐
                                     └──│  vLLM Pod 3 │
                                        └─────────────┘
```

### Multi-Model (Router Pattern)

Single gateway routing to multiple models:

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

---

## Deployment Steps

### 1. Create Endpoint

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

### 2. Configure Deployment

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

### 3. Deploy

```bash
curl -X POST /api/endpoints/{id}/deploy
```

### 4. Monitor Status

```bash
# Check deployment status
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

### Canary Deployment

Gradual traffic shift:

```
Day 1: v1=95%, v2=5%
Day 2: v1=90%, v2=10%
Day 3: v1=50%, v2=50%
Day 4: v1=0%, v2=100%
```

### Shadow Deployment

Test new version without affecting production:

```
All traffic → v1 (production)
Copy traffic → v2 (shadow, responses discarded)
```

---

## Scaling

### Horizontal Scaling

Add/remove replicas:

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

### Vertical Scaling

Change resource allocation (requires re-deployment):

```bash
curl -X PUT /api/endpoints/{id}/config \
  -d '{
    "resources": {
      "gpu_type": "nvidia-h100-80gb",
      "gpu_count": 8
    }
  }'

# Re-deploy with new configuration
curl -X POST /api/endpoints/{id}/deploy
```

---

## Configuration Reference

### Runtime Options

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

## Related Documents

- [MLOps Workflow Guide](./mlops-workflow.md)
- [Resource Optimization Guide](./resource-optimization.md)
- [Scaling Guidelines](./scaling-guidelines.md)
