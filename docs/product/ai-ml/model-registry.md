# Model Registry Documentation

---

## Overview

The Model Registry (budmodel) provides centralized management of AI models including versioning, metadata, licensing, and security scanning.

---

## Key Features

- **Centralized Catalog**: Single source of truth for all models
- **Versioning**: Track model versions and lineage
- **Metadata Management**: Store architecture, requirements, benchmarks
- **License Tracking**: Enforce usage restrictions
- **Security Scanning**: ClamAV scanning for artifacts
- **HuggingFace Integration**: Direct import from HuggingFace Hub

---

## Model Sources

### HuggingFace Hub

```bash
# Import model from HuggingFace
curl -X POST /api/models/import \
  -d '{
    "source": "huggingface",
    "model_id": "meta-llama/Llama-3.1-8B-Instruct",
    "name": "llama-3.1-8b"
  }'
```

### Custom Upload

```bash
# 1. Upload model to MinIO
mc cp ./model-weights s3://bud-models/my-model/

# 2. Register model
curl -X POST /api/models \
  -d '{
    "name": "my-custom-model",
    "source": "custom",
    "storage_path": "s3://bud-models/my-model/",
    "architecture": "llama",
    "parameter_count": 7000000000
  }'
```

---

## Model Metadata

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Unique model identifier |
| `architecture` | string | Model architecture (llama, mistral, etc.) |
| `parameter_count` | integer | Number of parameters |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `description` | string | Human-readable description |
| `context_length` | integer | Maximum context window |
| `license_type` | string | License identifier |
| `license_restrictions` | object | Usage restrictions |
| `requirements` | object | Hardware requirements |
| `tags` | array | Searchable tags |

### Example

```json
{
  "name": "llama-3.1-70b-instruct",
  "architecture": "llama",
  "parameter_count": 70000000000,
  "context_length": 128000,
  "license_type": "llama-3.1-community",
  "license_restrictions": {
    "commercial_use": true,
    "derivatives": true,
    "monthly_active_users_limit": 700000000
  },
  "requirements": {
    "min_gpu_memory_gb": 140,
    "recommended_gpu": "nvidia-h100-80gb",
    "recommended_gpu_count": 2
  },
  "tags": ["llm", "instruct", "chat", "multilingual"]
}
```

---

## Versioning

### Version Naming

Models use semantic versioning: `major.minor.patch`

- **Major**: Breaking changes (architecture, vocab)
- **Minor**: Fine-tuning, new capabilities
- **Patch**: Bug fixes, small improvements

### Version Management

```bash
# List versions
curl /api/models/{id}/versions

# Create new version
curl -X POST /api/models/{id}/versions \
  -d '{
    "version": "2.0.0",
    "storage_path": "s3://bud-models/my-model-v2/",
    "changelog": "Updated fine-tuning"
  }'

# Set default version
curl -X PUT /api/models/{id}/default-version \
  -d '{"version": "2.0.0"}'
```

---

## License Management

### License Types

| Type | Commercial | Derivatives | Notes |
|------|------------|-------------|-------|
| Apache-2.0 | Yes | Yes | Most permissive |
| MIT | Yes | Yes | Permissive |
| Llama-3.1-Community | Yes* | Yes | MAU limit |
| Mistral-Research | No | No | Research only |
| OpenAI-TOS | Yes | No | API only |

### Enforcement

- License checks during deployment
- Warnings for restricted usage
- Audit log of license acknowledgments

---

## Security Scanning

### Automatic Scanning

All uploaded models are scanned with ClamAV:

1. Upload triggers scan job
2. Scan checks for malware signatures
3. Model status updates:
   - `SCANNING`: In progress
   - `PASSED`: Clean
   - `FAILED`: Issues found
   - `SKIPPED`: Scan disabled

### Manual Rescan

```bash
curl -X POST /api/models/{id}/scan
```

---

## Leaderboard

### Performance Benchmarks

Models are benchmarked on standard datasets:

| Benchmark | Description |
|-----------|-------------|
| `inference_latency` | P50/P99 latency |
| `throughput` | Tokens per second |
| `mmlu` | Academic knowledge |
| `humaneval` | Code generation |
| `mt_bench` | Multi-turn conversation |

### Accessing Leaderboard

```bash
# Get leaderboard
curl /api/models/leaderboard

# Filter by architecture
curl /api/models/leaderboard?architecture=llama

# Filter by size
curl /api/models/leaderboard?max_params=10000000000
```

---

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| GET | `/models` | List models |
| POST | `/models` | Register model |
| GET | `/models/{id}` | Get model |
| PUT | `/models/{id}` | Update model |
| DELETE | `/models/{id}` | Remove model |
| GET | `/models/{id}/versions` | List versions |
| POST | `/models/{id}/versions` | Add version |
| GET | `/models/{id}/license` | Get license |
| POST | `/models/{id}/scan` | Trigger scan |
| GET | `/models/leaderboard` | Performance leaderboard |
| POST | `/models/import` | Import from source |

---

## Related Documents

- [LLM Support Matrix](./llm-support-matrix.md)
- [Custom Model Onboarding](./custom-model-onboarding.md)
- [Model Deployment Guide](./model-deployment.md)
