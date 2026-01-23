# Model Monitoring Guide

---

## Overview

This guide covers monitoring deployed models including metrics, drift detection, alerting, and performance optimization.

---

## Metrics Overview

### Inference Metrics

| Metric | Description | Good Range |
|--------|-------------|------------|
| **Latency (P50)** | Median request latency | <500ms |
| **Latency (P99)** | 99th percentile latency | <2000ms |
| **TTFT** | Time to first token | <200ms |
| **Throughput** | Tokens per second | Model-dependent |
| **Error Rate** | Failed request percentage | <1% |

### Resource Metrics

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| **GPU Utilization** | Compute usage | >95% sustained |
| **GPU Memory** | VRAM usage | >90% |
| **CPU Usage** | Host CPU | >80% |
| **Queue Depth** | Pending requests | >100 |

---

## Monitoring Stack

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Observability Stack                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐               │
│  │   Grafana   │   │ ClickHouse  │   │ Prometheus  │               │
│  │ Dashboards  │   │  (Metrics)  │   │  (Scrape)   │               │
│  └──────┬──────┘   └──────┬──────┘   └──────┬──────┘               │
│         │                 │                 │                        │
│         └─────────────────┼─────────────────┘                       │
│                           │                                          │
│                    ┌──────┴──────┐                                  │
│                    │ budmetrics  │                                  │
│                    └──────┬──────┘                                  │
│                           │                                          │
│              ┌────────────┼────────────┐                            │
│              ▼            ▼            ▼                            │
│        ┌──────────┐ ┌──────────┐ ┌──────────┐                      │
│        │ Endpoint │ │ Endpoint │ │ Endpoint │                      │
│        │    A     │ │    B     │ │    C     │                      │
│        └──────────┘ └──────────┘ └──────────┘                      │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Pre-Built Dashboards

### Inference Overview

- Request rate by endpoint
- Latency distribution
- Error rate trends
- Token throughput

### Endpoint Deep Dive

- Per-endpoint metrics
- Resource utilization
- Queue depth over time
- Top error messages

### Cost Analysis

- Token usage by project
- Cost per endpoint
- Usage trends
- Budget alerts

---

## Alerting

### Default Alert Rules

| Alert | Condition | Severity |
|-------|-----------|----------|
| High Latency | P99 > 5s for 5m | Warning |
| Very High Latency | P99 > 10s for 2m | Critical |
| High Error Rate | Error rate > 5% for 5m | Warning |
| Very High Error Rate | Error rate > 20% for 2m | Critical |
| GPU Memory Full | Memory > 95% for 5m | Warning |
| Endpoint Down | No requests for 15m | Warning |

### Custom Alerts

```yaml
# prometheus-rules.yaml
groups:
  - name: model-alerts
    rules:
      - alert: ModelLatencyHigh
        expr: |
          histogram_quantile(0.99,
            rate(inference_latency_ms_bucket[5m])
          ) > 2000
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High latency on {{ $labels.endpoint }}"
```

---

## Drift Detection

### Performance Drift

Monitor for degradation over time:

```
Baseline (Week 1):
  - P99 latency: 800ms
  - Throughput: 150 tps

Current:
  - P99 latency: 1200ms (+50%)
  - Throughput: 120 tps (-20%)

Alert: Performance drift detected
```

### Usage Pattern Drift

Detect changes in request patterns:

- Average input length
- Request rate distribution
- Peak hours shift
- Model usage ratio

---

## Troubleshooting

### High Latency

1. **Check GPU utilization**
   - If >95%: Scale up replicas or optimize config
   - If <50%: Check batch size, queue depth

2. **Check memory pressure**
   - High swap activity indicates OOM risk
   - Reduce `max_num_seqs` or context length

3. **Check network**
   - Model download latency
   - Cross-AZ traffic

### High Error Rate

1. **Check error logs**
   ```bash
   kubectl logs -l app=vllm -n bud-workloads
   ```

2. **Common errors**
   - CUDA OOM: Reduce batch size
   - Timeout: Increase timeout, check queue
   - Model not found: Verify model path

### Resource Exhaustion

1. **GPU Memory**
   - Reduce `max_model_len`
   - Reduce `max_num_seqs`
   - Lower `gpu_memory_utilization`

2. **CPU/RAM**
   - Check for memory leaks
   - Review pod resource limits

---

## Optimization Loop

```
Monitor → Analyze → Optimize → Validate → Monitor
    ↑                                        │
    └────────────────────────────────────────┘
```

1. **Monitor**: Collect metrics continuously
2. **Analyze**: Identify bottlenecks weekly
3. **Optimize**: Adjust configuration
4. **Validate**: Verify improvements
5. **Repeat**: Continuous improvement

---

## Best Practices

- Set up alerts before production deployment
- Review dashboards daily during initial deployment
- Establish baselines during first week
- Document optimization changes
- Schedule weekly performance reviews

---

## Related Documents

- [Observability Architecture](../operations/observability-architecture.md)
- [Metrics Catalog](../operations/metrics-catalog.md)
- [Performance Tuning Guide](./performance-tuning.md)
