# MLOps Workflow Guide

---

## Overview

This guide describes the end-to-end MLOps workflow in Bud AI Foundry, from model selection through deployment, monitoring, and optimization.

---

## Workflow Stages

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

### Deployment Process

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

### Runtime Options

| Runtime | Best For |
|---------|----------|
| **vLLM** | High throughput, general LLM workloads |
| **SGLang** | Structured generation, complex prompts |
| **TensorRT-LLM** | Maximum NVIDIA GPU performance |

---

## Stage 4: Monitoring & Scaling

### Metrics Collected

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| `inference_latency_p99` | 99th percentile latency | >2s |
| `ttft_p99` | Time to first token | >500ms |
| `throughput` | Tokens per second | <target |
| `gpu_utilization` | GPU compute usage | >95% sustained |
| `queue_depth` | Pending requests | >100 |

### Scaling Options

**Horizontal Scaling (Replicas)**
```bash
# Scale endpoint replicas
curl -X POST /endpoints/{id}/scale -d '{"replicas": 4}'
```

**Vertical Scaling (Re-optimization)**
1. Update performance targets
2. Re-run budsim optimization
3. Apply new configuration (rolling update)

### Continuous Optimization

1. budmetrics collects performance data
2. Compare actual vs predicted performance
3. budsim refines model with real-world data
4. Recommendations surface in dashboard

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

## Related Documents

- [Model Deployment Guide](./model-deployment.md)
- [BudSim User Guide](./budsim-user-guide.md)
- [Model Monitoring Guide](./model-monitoring.md)
