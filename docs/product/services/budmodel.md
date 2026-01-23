# budmodel Service Documentation

---

## Overview

budmodel is the model registry service that manages model metadata, licensing information, security scanning, and performance leaderboard data.

---

## Service Identity

| Property | Value |
|----------|-------|
| **App ID** | budmodel |
| **Port** | 9084 |
| **Database** | budmodel_db (PostgreSQL) |
| **Language** | Python 3.11 |
| **Framework** | FastAPI |

---

## Responsibilities

- Maintain catalog of available AI models
- Store model metadata (parameters, architecture, requirements)
- Track licensing information and restrictions
- Security scanning of model artifacts (ClamAV)
- Performance leaderboard and benchmarks
- Integration with HuggingFace Hub

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/models` | List models |
| GET | `/models/{id}` | Get model details |
| POST | `/models` | Register custom model |
| PUT | `/models/{id}` | Update model metadata |
| DELETE | `/models/{id}` | Remove model |
| GET | `/models/{id}/license` | Get license info |
| POST | `/models/{id}/scan` | Trigger security scan |
| GET | `/leaderboard` | Performance leaderboard |
| GET | `/benchmarks` | Model benchmarks |

---

## Data Models

### Model

```python
class Model(Base):
    id: UUID
    name: str
    provider: str  # HuggingFace, OpenAI, Custom
    architecture: str  # Llama, Mistral, etc.
    parameter_count: int  # In billions
    context_length: int
    license_type: str
    license_restrictions: dict
    requirements: dict  # GPU memory, etc.
    scan_status: ScanStatus
    created_at: datetime
```

### Benchmark

```python
class Benchmark(Base):
    id: UUID
    model_id: UUID
    hardware_profile: str
    metrics: dict  # TTFT, throughput, latency
    configuration: dict
    created_at: datetime
```

---

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `HUGGINGFACE_TOKEN` | HuggingFace API token | Optional |
| `CLAMAV_HOST` | ClamAV server for scanning | `localhost` |
| `LEADERBOARD_UPDATE_INTERVAL` | Cron interval | `0 */6 * * *` |

---

## Development

```bash
cd services/budmodel
./deploy/start_dev.sh --build
pytest
```

---

## Related Documents

- [Model Registry Documentation](../ai-ml/model-registry.md)
- [LLM Support Matrix](../ai-ml/llm-support-matrix.md)
