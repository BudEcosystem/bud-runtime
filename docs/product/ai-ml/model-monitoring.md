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
