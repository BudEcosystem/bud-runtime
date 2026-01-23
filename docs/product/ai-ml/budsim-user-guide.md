# BudSim User Guide

---

## Overview

BudSim is the performance simulation and optimization engine that recommends optimal deployment configurations for AI models based on hardware capabilities and performance targets.

---

## Optimization Methods

### REGRESSOR Method

ML-based optimization using XGBoost + DEAP genetic algorithm.

**Best for:**
- Production deployments requiring maximum accuracy
- Complex multi-objective optimization
- When performance predictions are critical

**How it works:**
1. XGBoost model predicts performance for a given configuration
2. DEAP genetic algorithm searches configuration space
3. Multi-objective optimization balances latency, throughput, cost
4. Returns Pareto-optimal configurations

**Optimized parameters:**
- Tensor Parallelism (TP)
- Pipeline Parallelism (PP)
- Batch size
- Max sequences
- GPU memory utilization
- Replica count

### HEURISTIC Method

Memory-based calculations for fast results.

**Best for:**
- Quick estimates
- Simple deployments
- When speed matters more than precision

**How it works:**
1. Calculate memory requirements from model architecture
2. Determine minimum TP based on GPU memory
3. Recommend configuration meeting constraints

**Optimized parameters:**
- Tensor Parallelism (TP) only
- Pipeline Parallelism (PP) only

---

## Using BudSim

### Via Dashboard

1. Navigate to **Endpoints** → **Create Endpoint**
2. Select model and cluster
3. Choose optimization method
4. Set performance targets
5. Click **Optimize**
6. Review recommendations
7. Deploy with suggested config

### Via API

```bash
# Run optimization
curl -X POST /api/optimize \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "model_id": "uuid",
    "cluster_id": "uuid",
    "method": "REGRESSOR",
    "targets": {
      "max_latency_ms": 2000,
      "min_throughput_tps": 100
    },
    "constraints": {
      "max_replicas": 4,
      "max_cost_per_hour": 50
    }
  }'
```

Response:
```json
{
  "optimal_config": {
    "tensor_parallel_size": 2,
    "pipeline_parallel_size": 1,
    "max_num_seqs": 128,
    "max_model_len": 8192,
    "replicas": 2
  },
  "predicted_metrics": {
    "ttft_p50_ms": 150,
    "ttft_p99_ms": 400,
    "throughput_tps": 120,
    "cost_per_hour": 35
  },
  "confidence": 0.92
}
```

---

## Performance Targets

| Target | Description | Example |
|--------|-------------|---------|
| `max_latency_ms` | Maximum acceptable P99 latency | 2000 |
| `min_throughput_tps` | Minimum tokens per second | 100 |
| `max_ttft_ms` | Maximum time to first token | 500 |
| `max_cost_per_hour` | Cost constraint | 50 |

---

## Constraints

| Constraint | Description | Default |
|------------|-------------|---------|
| `max_replicas` | Maximum deployment replicas | 10 |
| `max_gpus_per_replica` | Max GPUs per instance | 8 |
| `allowed_gpu_types` | Restrict GPU types | All |
| `require_high_availability` | Force multi-replica | false |

---

## Understanding Results

### Confidence Score

- **>0.9**: High confidence, production ready
- **0.7-0.9**: Moderate confidence, validate in staging
- **<0.7**: Low confidence, consider more data

### Predicted Metrics

| Metric | Description |
|--------|-------------|
| `ttft_p50_ms` | Median time to first token |
| `ttft_p99_ms` | 99th percentile TTFT |
| `throughput_tps` | Tokens per second |
| `cost_per_hour` | Estimated hourly cost |

---

## Best Practices

1. **Start with REGRESSOR** for production workloads
2. **Use HEURISTIC** for quick exploration
3. **Set realistic targets** based on use case
4. **Validate predictions** in staging environment
5. **Re-optimize** when hardware or models change

---

## Troubleshooting

### Low Confidence Score

- Model/hardware combination may be untested
- Consider running benchmarks to improve model
- Use HEURISTIC as fallback

### Recommendations Exceed Budget

- Relax latency requirements
- Consider smaller model variant
- Use quantization

### Optimization Timeout

- Simplify constraints
- Use HEURISTIC method
- Check service health

---

## Related Documents

- [Resource Optimization Guide](./resource-optimization.md)
- [Model Deployment Guide](./model-deployment.md)
- [budsim Service Documentation](../services/budsim.md)
