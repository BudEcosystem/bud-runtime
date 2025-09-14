# BudDoc Configuration Guide

## Overview

BudDoc uses environment variables for configuration, supporting both local development and production deployments. Configuration is managed through `.env` files and can be overridden via Docker environment variables or Kubernetes ConfigMaps.

## Environment Variables

### Core Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `APP_NAME` | Application name | `buddoc` | Yes |
| `APP_PORT` | Service port | `9081` | Yes |
| `API_ROOT` | API root path | `/` | No |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | `INFO` | No |

### VLM Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `VLM_API_URL` | VLM API endpoint URL | `http://localhost:1234/v1/chat/completions` | Yes |
| `VLM_MODEL_NAME` | Default VLM model name | `qwen2-vl-7b` | Yes |
| `VLM_API_TOKEN` | Bearer token for VLM API authentication | None | No* |
| `VLM_API_TIMEOUT` | VLM API timeout in seconds | `90` | No |
| `VLM_RESPONSE_FORMAT` | Response format (markdown/doctags) | `markdown` | No |

*Note: `VLM_API_TOKEN` is optional if clients provide their own bearer tokens via Authorization header.

### Document Processing

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `MAX_FILE_SIZE_MB` | Maximum file size in megabytes | `50` | No |
| `ALLOWED_EXTENSIONS` | Comma-separated list of allowed file extensions | `pdf,docx,pptx,xlsx,png,jpg,jpeg,tiff,html` | No |
| `TEMP_UPLOAD_DIR` | Directory for temporary file storage | `/tmp/buddoc_uploads` | No |
| `OCR_MODELS` | Comma-separated list of supported OCR models | `docling-vlm,mistral-ocr-latest,pixtral-12b,qwen2-vl-7b` | No |
| `DEFAULT_OCR_MODEL` | Default OCR model when not specified | `qwen2-vl-7b` | No |

### Database Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+psycopg://user:pass@localhost:5432/buddoc` | Yes |
| `DB_HOST` | Database host | `localhost` | Yes |
| `DB_PORT` | Database port | `5432` | Yes |
| `DB_NAME` | Database name | `buddoc` | Yes |
| `DB_USER` | Database user | `bud` | Yes |
| `DB_PASSWORD` | Database password | `bud` | Yes |
| `DB_POOL_SIZE` | Connection pool size | `20` | No |
| `DB_MAX_OVERFLOW` | Max overflow connections | `40` | No |

### Redis Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `REDIS_URI` | Redis connection URI | `redis://localhost:6379` | Yes |
| `REDIS_HOST` | Redis host | `localhost` | Yes |
| `REDIS_PORT` | Redis port | `6379` | Yes |
| `REDIS_DB` | Redis database number | `0` | No |
| `REDIS_PASSWORD` | Redis password | None | No |

### Dapr Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DAPR_HTTP_PORT` | Dapr HTTP port | `3510` | Yes |
| `DAPR_GRPC_PORT` | Dapr gRPC port | `50001` | Yes |
| `DAPR_API_TOKEN` | Dapr API token for authentication | None | No |
| `DAPR_APP_ID` | Dapr application ID | `buddoc` | Yes |
| `DAPR_COMPONENTS_PATH` | Path to Dapr components | `../.dapr/components/` | Yes |

## Configuration Files

### `.env` File

Create a `.env` file in the service root directory:

```bash
# Core Configuration
APP_NAME=buddoc
APP_PORT=9081
LOG_LEVEL=INFO

# VLM Configuration
VLM_API_URL=http://localhost:1234/v1/chat/completions
VLM_MODEL_NAME=qwen2-vl-7b
VLM_API_TOKEN=sk-your-api-key-here
VLM_API_TIMEOUT=90
VLM_RESPONSE_FORMAT=markdown

# Document Processing
MAX_FILE_SIZE_MB=50
ALLOWED_EXTENSIONS=pdf,docx,pptx,xlsx,png,jpg,jpeg,tiff,html
TEMP_UPLOAD_DIR=/tmp/buddoc_uploads

# Database
DATABASE_URL=postgresql+psycopg://bud:bud@localhost:5432/buddoc
DB_HOST=localhost
DB_PORT=5432
DB_NAME=buddoc
DB_USER=bud
DB_PASSWORD=bud

# Redis
REDIS_URI=redis://localhost:6379
REDIS_HOST=localhost
REDIS_PORT=6379

# Dapr
DAPR_HTTP_PORT=3510
DAPR_GRPC_PORT=50001
DAPR_APP_ID=buddoc
```

### `.env.sample` File

A sample configuration file is provided as `.env.sample`. Copy it to create your `.env`:

```bash
cp .env.sample .env
```

## Configuration Profiles

### Development Configuration

For local development with Docker Compose:

```bash
# .env.development
LOG_LEVEL=DEBUG
VLM_API_URL=http://host.docker.internal:1234/v1/chat/completions
DATABASE_URL=postgresql+psycopg://bud:bud@postgres:5432/buddoc
REDIS_URI=redis://redis:6379
```

### Production Configuration

For production deployment:

```bash
# .env.production
LOG_LEVEL=INFO
VLM_API_URL=https://vlm-api.production.com/v1/chat/completions
VLM_API_TOKEN=${VLM_API_TOKEN_SECRET}
DATABASE_URL=postgresql+psycopg://prod_user:${DB_PASSWORD_SECRET}@db.production.com:5432/buddoc_prod
REDIS_URI=redis://:${REDIS_PASSWORD_SECRET}@redis.production.com:6379
MAX_FILE_SIZE_MB=100
VLM_API_TIMEOUT=180
```

## Docker Configuration

### Docker Compose Override

Use `docker-compose.override.yml` for local overrides:

```yaml
version: '3.8'
services:
  buddoc:
    environment:
      - LOG_LEVEL=DEBUG
      - VLM_API_URL=http://host.docker.internal:1234/v1/chat/completions
      - VLM_API_TOKEN=${VLM_API_TOKEN}
```

### Dockerfile Environment

Set build-time and runtime variables:

```dockerfile
# Build arguments
ARG APP_VERSION=latest

# Runtime environment
ENV APP_NAME=buddoc \
    APP_PORT=9081 \
    LOG_LEVEL=INFO
```

## Kubernetes Configuration

### ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: buddoc-config
data:
  APP_NAME: "buddoc"
  APP_PORT: "9081"
  LOG_LEVEL: "INFO"
  VLM_API_URL: "https://vlm-api.cluster.local/v1/chat/completions"
  VLM_MODEL_NAME: "qwen2-vl-7b"
  MAX_FILE_SIZE_MB: "100"
```

### Secret

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: buddoc-secrets
type: Opaque
stringData:
  VLM_API_TOKEN: "sk-your-secret-token"
  DB_PASSWORD: "secure-password"
  REDIS_PASSWORD: "redis-password"
```

### Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: buddoc
spec:
  template:
    spec:
      containers:
      - name: buddoc
        envFrom:
        - configMapRef:
            name: buddoc-config
        - secretRef:
            name: buddoc-secrets
        env:
        - name: DATABASE_URL
          value: "postgresql+psycopg://$(DB_USER):$(DB_PASSWORD)@postgres:5432/$(DB_NAME)"
```

## VLM Provider Configuration

### OpenAI Compatible APIs

For OpenAI or compatible APIs:

```bash
VLM_API_URL=https://api.openai.com/v1/chat/completions
VLM_MODEL_NAME=gpt-4-vision-preview
VLM_API_TOKEN=sk-your-openai-api-key
```

### Local VLM Server

For local VLM server (e.g., LM Studio, Ollama):

```bash
VLM_API_URL=http://localhost:1234/v1/chat/completions
VLM_MODEL_NAME=llava-v1.6-mistral-7b
VLM_API_TOKEN=  # Often not required for local servers
```

### Custom VLM Endpoints

For custom VLM deployments:

```bash
VLM_API_URL=https://your-vlm-endpoint.com/api/v1/completions
VLM_MODEL_NAME=custom-vision-model
VLM_API_TOKEN=Bearer your-custom-token
VLM_API_TIMEOUT=120
```

## Security Best Practices

1. **Never commit `.env` files** to version control
2. **Use secrets management** for production:
   - Kubernetes Secrets
   - AWS Secrets Manager
   - Azure Key Vault
   - HashiCorp Vault

3. **Rotate API tokens** regularly
4. **Use different tokens** for different environments
5. **Implement token scoping** where possible

## Validation

### Check Configuration

Validate configuration on startup:

```python
# The service validates required configuration on startup
# Check logs for configuration errors:
docker logs buddoc-container
```

### Test VLM Connection

```bash
# Test VLM API connection
curl -X POST $VLM_API_URL \
  -H "Authorization: Bearer $VLM_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "'$VLM_MODEL_NAME'", "messages": [{"role": "user", "content": "test"}]}'
```

## Troubleshooting

### Common Configuration Issues

1. **VLM Connection Failed**
   - Verify `VLM_API_URL` is accessible
   - Check `VLM_API_TOKEN` is valid
   - Ensure network connectivity

2. **Database Connection Error**
   - Verify `DATABASE_URL` format
   - Check database is running
   - Verify credentials

3. **Redis Connection Failed**
   - Check `REDIS_URI` format
   - Ensure Redis is running
   - Verify network access

4. **File Size Limits**
   - Adjust `MAX_FILE_SIZE_MB` as needed
   - Consider infrastructure limits

5. **Timeout Issues**
   - Increase `VLM_API_TIMEOUT` for large documents
   - Check VLM server performance

## Performance Tuning

### Optimize for Throughput

```bash
# Increase connection pools
DB_POOL_SIZE=50
DB_MAX_OVERFLOW=100

# Increase timeout for large documents
VLM_API_TIMEOUT=300

# Increase file size limit
MAX_FILE_SIZE_MB=200
```

### Optimize for Latency

```bash
# Reduce timeout for faster failures
VLM_API_TIMEOUT=30

# Use local VLM server
VLM_API_URL=http://localhost:1234/v1/chat/completions

# Smaller connection pools
DB_POOL_SIZE=10
```

## Monitoring

### Health Check Endpoints

- **Liveness**: `GET /health/live`
- **Readiness**: `GET /health/ready`

### Metrics

Configure metrics collection:

```bash
METRICS_ENABLED=true
METRICS_PORT=9090
METRICS_PATH=/metrics
```

### Logging

Configure structured logging:

```bash
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_OUTPUT=stdout
```