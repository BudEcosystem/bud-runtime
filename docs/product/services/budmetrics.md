# budmetrics Service Documentation

---

## Overview

budmetrics is the observability service that collects, stores, and analyzes inference metrics using ClickHouse for time-series data.

---

## Service Identity

| Property | Value |
|----------|-------|
| **App ID** | budmetrics |
| **Port** | 9085 |
| **Database** | budmetrics_db (ClickHouse) |
| **Language** | Python 3.11 |
| **Framework** | FastAPI |

---

## Responsibilities

- Collect inference metrics from budgateway
- Store time-series data in ClickHouse
- Provide analytics and aggregations
- Track token usage and costs
- Feed data to Grafana dashboards
- Support billing calculations

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/metrics/ingest` | Ingest metrics batch |
| GET | `/metrics/query` | Query metrics |
| GET | `/metrics/aggregates` | Get aggregated stats |
| GET | `/usage/{project_id}` | Project usage summary |
| GET | `/usage/{project_id}/daily` | Daily breakdown |
| GET | `/costs/{project_id}` | Cost calculations |

---

## Metrics Collected

| Metric | Type | Description |
|--------|------|-------------|
| `inference_latency_ms` | Histogram | Total request latency |
| `ttft_ms` | Histogram | Time to first token |
| `tokens_input` | Counter | Input token count |
| `tokens_output` | Counter | Output token count |
| `request_count` | Counter | Total requests |
| `error_count` | Counter | Failed requests |
| `model_id` | Label | Model identifier |
| `endpoint_id` | Label | Endpoint identifier |
| `provider` | Label | AI provider |

---

## ClickHouse Schema

```sql
CREATE TABLE inference_metrics (
    timestamp DateTime64(3),
    endpoint_id UUID,
    model_id UUID,
    project_id UUID,
    provider String,
    latency_ms Float64,
    ttft_ms Float64,
    tokens_input UInt32,
    tokens_output UInt32,
    status_code UInt16,
    error_message Nullable(String)
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (project_id, endpoint_id, timestamp);
```

---

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `CLICKHOUSE_HOST` | ClickHouse server | Required |
| `CLICKHOUSE_PORT` | ClickHouse HTTP port | `8123` |
| `CLICKHOUSE_DATABASE` | Database name | `budmetrics_db` |
| `RETENTION_DAYS` | Data retention period | `90` |
| `AGGREGATION_INTERVAL` | Pre-aggregation interval | `1h` |

---

## Development

```bash
cd services/budmetrics
./deploy/start_dev.sh --build
python scripts/migrate_clickhouse.py  # Run migrations
pytest
```

---

## Related Documents

- [Observability Architecture](../operations/observability-architecture.md)
- [Metrics Catalog](../operations/metrics-catalog.md)
