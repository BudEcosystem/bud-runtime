# budeval Service Documentation

---

## Overview

budeval is the model evaluation and benchmarking service that assesses model quality, compares performance across configurations, and generates evaluation reports.

---

## Service Identity

| Property | Value |
|----------|-------|
| **App ID** | budeval |
| **Port** | 9087 |
| **Database** | budeval_db (PostgreSQL) |
| **Language** | Python 3.11 |
| **Framework** | FastAPI |

---

## Responsibilities

- Run standardized benchmarks on deployed models
- Compare model performance across configurations
- Quality assessment (accuracy, coherence, safety)
- Generate evaluation reports
- Support A/B testing scenarios

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/evaluations` | Create evaluation job |
| GET | `/evaluations` | List evaluations |
| GET | `/evaluations/{id}` | Get evaluation results |
| DELETE | `/evaluations/{id}` | Cancel evaluation |
| GET | `/benchmarks` | List benchmark suites |
| POST | `/benchmarks/run` | Run benchmark suite |
| GET | `/comparisons` | Model comparisons |

---

## Benchmark Suites

| Suite | Description |
|-------|-------------|
| `latency` | Response time benchmarks |
| `throughput` | Requests per second |
| `quality` | Output quality metrics |
| `safety` | Safety and alignment checks |
| `accuracy` | Task-specific accuracy |

---

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `EVALUATION_TIMEOUT` | Max evaluation time | `3600` |
| `CONCURRENT_EVALUATIONS` | Parallel evaluation jobs | `5` |

---

## Related Documents

- [Benchmarking Methodology](../ai-ml/benchmarking.md)
- [Model Monitoring Guide](../ai-ml/model-monitoring.md)
