# AIBrix Integration with Mock vLLM Models

This guide explains how to deploy mock vLLM models that are discoverable by AIBrix for integration testing.

## Overview

AIBrix discovers vLLM models through Kubernetes labels and services. The mock vLLM models are deployed with the same discovery patterns as real vLLM deployments, allowing AIBrix to:

1. Automatically discover available models
2. Route requests to the appropriate model endpoints
3. Manage model lifecycle and autoscaling
4. Collect metrics and monitor health

## Architecture

```
AIBrix Controller
    ↓ (watches for model.aibrix.ai/* labels)
Model Registry
    ↓ (discovers services)
Mock vLLM Services
    - llama-2-7b-chat → mock-vllm container
    - gpt-4 → mock-vllm container
    - mistral-7b-instruct → mock-vllm container
```

## Deployment

### Quick Start

Deploy common models for testing:

```bash
./scripts/deploy/deploy-mock-vllm-aibrix.sh \
  --enable-models "llama-2-7b-chat,gpt-4,mistral-7b-instruct"
```

### Custom Model Selection

Deploy specific models:

```bash
./scripts/deploy/deploy-mock-vllm-aibrix.sh \
  --enable-models "gpt-3.5-turbo,mistral-7b-instruct"
```

### Available Models

| Model Name | Description | Processing Delay |
|------------|-------------|------------------|
| `llama-2-7b-chat` | Llama 2 7B Chat | 0.1s |
| `gpt-4` | GPT-4 | 0.2s |
| `gpt-3.5-turbo` | GPT-3.5 Turbo | 0.1s |
| `mistral-7b-instruct` | Mistral 7B Instruct | 0.15s |
| `deepseek-coder-6.7b` | Deepseek Coder 6.7B | 0.15s |
| `qwen-coder-1.5b` | Qwen 2.5 Coder 1.5B | 0.08s |

## AIBrix Discovery

### Label-Based Discovery

Each deployment must have these labels for AIBrix discovery:

```yaml
labels:
  model.aibrix.ai/name: <model-name>  # Must match service name
  model.aibrix.ai/port: "8000"         # Service port
```

### Service Requirements

Services must:
1. Have the same name as `model.aibrix.ai/name`
2. Select pods using `model.aibrix.ai/name` label
3. Expose port matching `model.aibrix.ai/port`

Example:
```yaml
apiVersion: v1
kind: Service
metadata:
  name: llama-2-7b-chat
  labels:
    model.aibrix.ai/name: llama-2-7b-chat
spec:
  selector:
    model.aibrix.ai/name: llama-2-7b-chat
  ports:
  - name: serve
    port: 8000
```

### Model Naming Consistency

The following must all match:
- Deployment `model.aibrix.ai/name` label
- Service name
- Service `model.aibrix.ai/name` label
- vLLM `--served-model-name` argument

## Testing AIBrix Integration

### 1. Verify Model Discovery

Check if models are deployed with correct labels:

```bash
# List all models with AIBrix labels
kubectl get deployments -n aibrix-models \
  -l model.aibrix.ai/name \
  -o custom-columns=NAME:.metadata.name,MODEL:.metadata.labels.model\\.aibrix\\.ai/name,PORT:.metadata.labels.model\\.aibrix\\.ai/port
```

### 2. Test Model Endpoints

Test individual model endpoints:

```bash
# Test a specific model
MODEL_NAME="llama-2-7b-chat"
kubectl run test-$MODEL_NAME --rm -it --restart=Never \
  --namespace=aibrix-models \
  --image=curlimages/curl:latest \
  -- curl -s -X POST http://$MODEL_NAME:8000/v1/chat/completions \
     -H "Content-Type: application/json" \
     -d '{"model": "'$MODEL_NAME'", "messages": [{"role": "user", "content": "Test"}]}'
```

### 3. AIBrix Model Registry

Once AIBrix is deployed, verify model registration:

```bash
# Check AIBrix logs for model discovery
kubectl logs -n aibrix-system deploy/aibrix-controller | grep "model discovered"

# List registered models (using AIBrix API)
curl http://aibrix-api.aibrix-system:8080/v1/models
```

## Integration Patterns

### 1. Direct Model Access

Applications can access models directly:
```
http://llama-2-7b-chat.aibrix-models:8000/v1/chat/completions
```

### 2. Through AIBrix Gateway

AIBrix provides unified access:
```
http://aibrix-gateway.aibrix-system:8080/v1/chat/completions
Headers:
  X-Model-Name: llama-2-7b-chat
```

### 3. Load Balancing

AIBrix can load balance across multiple replicas:
```bash
# Scale a model
kubectl scale deployment/llama-2-7b-chat -n aibrix-models --replicas=3
```

## Mock vLLM Behavior

### Response Patterns

Mock vLLM provides consistent responses for testing:

1. **Chat Completions**: Returns contextual responses from a predefined set
2. **Embeddings**: Generates deterministic 768-dimensional vectors
3. **Tokenization**: Simple character-based tokenization
4. **Health Checks**: Always returns 200 OK when healthy

### Configuration

Adjust mock behavior per model:

```yaml
models:
  - name: gpt-4
    processingDelay: "0.2"  # Simulate slower "larger" model
    env:
      - name: MOCK_RESPONSE_STYLE
        value: "verbose"    # Custom response style
```

## Troubleshooting

### Models Not Discovered by AIBrix

1. **Check Labels**:
   ```bash
   kubectl get deploy,svc -n aibrix-models --show-labels
   ```

2. **Verify Service Endpoints**:
   ```bash
   kubectl get endpoints -n aibrix-models
   ```

3. **Check AIBrix Controller**:
   ```bash
   kubectl logs -n aibrix-system deploy/aibrix-controller
   ```

### Model Endpoint Not Responding

1. **Check Pod Status**:
   ```bash
   kubectl get pods -n aibrix-models -l model.aibrix.ai/name=<model-name>
   ```

2. **View Pod Logs**:
   ```bash
   kubectl logs -n aibrix-models -l model.aibrix.ai/name=<model-name>
   ```

3. **Test Internal Connectivity**:
   ```bash
   kubectl exec -n aibrix-models deploy/<model-name> -- curl localhost:8000/health
   ```

## Best Practices

1. **Consistent Naming**: Always ensure model names match across all resources
2. **Resource Limits**: Set appropriate resource limits for mock models
3. **Health Checks**: Configure proper liveness/readiness probes
4. **Monitoring**: Enable Prometheus scraping with annotations
5. **Namespace Isolation**: Deploy models in dedicated namespace (aibrix-models)

## Cleanup

Remove all mock models:

```bash
helm uninstall mock-vllm-models -n aibrix-models
kubectl delete namespace aibrix-models
```

Remove specific models:

```bash
kubectl delete deploy,svc <model-name> -n aibrix-models
```