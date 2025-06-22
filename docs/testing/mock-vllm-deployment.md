# Mock vLLM Deployment Guide

This guide explains how to deploy and use the mock vLLM service for integration testing.

## Overview

The mock vLLM service is a lightweight alternative to the real vLLM service, designed specifically for integration testing. It provides the same OpenAI-compatible API endpoints but returns mock responses instead of running actual LLM inference.

## Deployment Options

### 1. Standalone Deployment

Deploy mock vLLM in its own namespace:

```bash
# Deploy mock vLLM
helm install mock-vllm ./helm/mock-vllm \
  --namespace mock-vllm \
  --create-namespace

# Check deployment status
kubectl get all -n mock-vllm
```

### 2. Integration with Existing Services

To use mock vLLM with services like budproxy or other applications:

```bash
# Deploy mock vLLM
helm install mock-vllm ./helm/mock-vllm \
  --namespace dapr-system

# Update budproxy or other services to use mock vLLM
# Set environment variable:
# VLLM_BASE_URL=http://mock-vllm:8000/v1
```

### 3. Local Development

For local testing without Kubernetes:

```bash
cd services/mock-vllm
docker-compose up -d

# Service will be available at http://localhost:8000
```

## Configuration

### Key Configuration Options

```yaml
# helm/mock-vllm/values.yaml
config:
  processingDelay: "0.1"  # Simulated processing time
  apiKey: ""              # Optional API key for auth
  servedModelNames:       # Models to advertise
    - "gpt-3.5-turbo"
    - "gpt-4"
    - "text-embedding-ada-002"
```

### Resource Requirements

Mock vLLM is designed to be lightweight:
- CPU: 100m (request), 500m (limit)
- Memory: 256Mi (request), 512Mi (limit)

Compare with real vLLM which typically requires:
- CPU: 8+ cores
- Memory: 16GB+
- GPU: Required for most models

## Testing Integration

### 1. Test Basic Connectivity

```bash
# Port forward to test locally
kubectl port-forward -n mock-vllm svc/mock-vllm 8000:8000

# Test health endpoint
curl http://localhost:8000/health

# List models
curl http://localhost:8000/v1/models
```

### 2. Test API Endpoints

```bash
# Test chat completion
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [{"role": "user", "content": "Hello"}]
  }'

# Test embeddings
curl -X POST http://localhost:8000/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "model": "text-embedding-ada-002",
    "input": "Test text"
  }'
```

### 3. Run Integration Tests

```bash
cd services/mock-vllm
python tests/simple_test.py
```

## Switching Between Mock and Real vLLM

### For Development/Testing
Use mock vLLM:
```bash
export VLLM_BASE_URL=http://mock-vllm:8000/v1
```

### For Production
Use real vLLM:
```bash
export VLLM_BASE_URL=http://vllm:8000/v1
```

## Benefits

1. **Fast Startup**: Mock vLLM starts in seconds vs minutes for real vLLM
2. **Low Resources**: Uses <512MB RAM vs 16GB+ for real vLLM
3. **No GPU Required**: Runs on any CPU-only node
4. **Deterministic**: Responses based on input hash for consistent testing
5. **Full API Coverage**: All vLLM endpoints implemented

## Limitations

1. **No Real Inference**: Responses are pre-defined, not generated
2. **No Model Loading**: Model names are just identifiers
3. **Simplified Tokenization**: Basic character-based tokenization
4. **Mock Embeddings**: Random but deterministic vectors

## Troubleshooting

### Service Not Accessible
```bash
# Check if pod is running
kubectl get pods -n mock-vllm

# Check logs
kubectl logs -n mock-vllm -l app.kubernetes.io/name=mock-vllm

# Check service
kubectl describe svc -n mock-vllm mock-vllm
```

### Performance Issues
- Increase `processingDelay` to simulate slower responses
- Scale replicas for higher throughput
- Check resource limits if experiencing throttling

### Integration Issues
- Verify service DNS name is correct
- Check network policies if applicable
- Ensure API compatibility with client expectations