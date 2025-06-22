# Mock vLLM in Inference Cluster

This guide explains how to deploy and manage mock vLLM in the inference cluster for testing purposes.

## Overview

The inference cluster can run either real vLLM (requiring GPUs) or mock vLLM (CPU-only) for different testing scenarios:

- **Mock vLLM**: Lightweight, fast startup, no GPU required - ideal for integration testing
- **Real vLLM**: Full inference capabilities, requires GPU resources - for performance testing

## Prerequisites

1. Inference cluster must be running:
   ```bash
   ./scripts/multi-cluster/setup-inference-cluster.sh
   ```

2. Local Docker registry must be available:
   ```bash
   docker ps | grep bud-registry
   ```

## Deploying Mock vLLM

### Quick Start

Deploy mock vLLM with default settings:

```bash
./scripts/deploy/deploy-mock-vllm.sh
```

### Advanced Deployment

Deploy with custom configuration:

```bash
./scripts/deploy/deploy-mock-vllm.sh \
  --cluster-name bud-inference \
  --namespace vllm-system \
  --api-key "your-secret-key" \
  --processing-delay 0.5 \
  --image-tag v1.0.0
```

### Deployment Options

| Option | Description | Default |
|--------|-------------|---------|
| `--cluster-name` | Target cluster name | bud-inference |
| `--namespace` | Kubernetes namespace | vllm-system |
| `--release-name` | Helm release name | mock-vllm |
| `--build-image` | Build and push Docker image | true |
| `--image-tag` | Docker image tag | latest |
| `--api-key` | API key for authentication | (none) |
| `--processing-delay` | Simulated processing delay (seconds) | 0.1 |
| `--values-file` | Additional Helm values file | (none) |
| `--dry-run` | Show what would be done | false |

### Using Custom Values

Create a custom values file for specific configurations:

```yaml
# custom-values.yaml
config:
  processingDelay: "0.2"
  servedModelNames:
    - "custom-model-1"
    - "custom-model-2"
  
resources:
  limits:
    cpu: 1000m
    memory: 1Gi

autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 5
```

Deploy with custom values:

```bash
./scripts/deploy/deploy-mock-vllm.sh --values-file custom-values.yaml
```

## Switching Between Mock and Real vLLM

The switch script allows seamless transition between mock and real vLLM:

### Switch to Mock vLLM

```bash
./scripts/deploy/switch-vllm-mode.sh --mode mock
```

### Switch to Real vLLM

```bash
./scripts/deploy/switch-vllm-mode.sh --mode real
```

**Note**: Switching to real vLLM requires GPU resources to be available in the cluster.

### How It Works

1. **Scales deployments**: Scales down one deployment and scales up the other
2. **Updates service**: Points the common `vllm` service to the active deployment
3. **Zero downtime**: If both deployments exist, switching is near-instantaneous

## Testing the Deployment

### Port Forwarding

Access mock vLLM locally:

```bash
kubectl port-forward -n vllm-system svc/mock-vllm 8000:8000
```

### Test Endpoints

```bash
# Health check
curl http://localhost:8000/health

# List models
curl http://localhost:8000/v1/models

# Chat completion
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

### Run Integration Tests

The deployment script can automatically run integration tests:

```bash
# Run deployment with automatic testing
./scripts/deploy/deploy-mock-vllm.sh
# When prompted, type 'y' to run tests
```

## Integration with Services

### Configure Services to Use vLLM

Services in the application cluster can connect to vLLM in the inference cluster:

```yaml
# Example configuration for budproxy
env:
  - name: VLLM_BASE_URL
    value: "http://vllm.vllm-system.svc.cluster.local:8000/v1"
```

### Cross-Cluster Communication

If using multi-cluster setup with network connectivity:

1. **Same cluster**: Use internal service DNS
   ```
   http://vllm.vllm-system.svc.cluster.local:8000
   ```

2. **Cross-cluster**: Use cluster gateway or external ingress
   ```
   http://inference-gateway.example.com:8000
   ```

## Monitoring

### View Logs

```bash
# Mock vLLM logs
kubectl logs -n vllm-system -l app.kubernetes.io/name=mock-vllm -f

# All vLLM-related resources
kubectl get all -n vllm-system
```

### Metrics

Mock vLLM exposes Prometheus metrics at `/metrics`:

```bash
kubectl port-forward -n vllm-system svc/mock-vllm 8000:8000
curl http://localhost:8000/metrics
```

## Troubleshooting

### Deployment Fails

1. Check if namespace exists:
   ```bash
   kubectl get ns vllm-system
   ```

2. Check if image was pushed to registry:
   ```bash
   curl http://localhost:5111/v2/mock-vllm/tags/list
   ```

3. Check pod events:
   ```bash
   kubectl describe pod -n vllm-system -l app.kubernetes.io/name=mock-vllm
   ```

### Service Not Responding

1. Check pod status:
   ```bash
   kubectl get pods -n vllm-system
   ```

2. Check service endpoints:
   ```bash
   kubectl get endpoints -n vllm-system mock-vllm
   ```

3. Test internal connectivity:
   ```bash
   kubectl run test-curl --rm -it --restart=Never \
     --image=curlimages/curl:latest \
     -- curl http://mock-vllm.vllm-system.svc.cluster.local:8000/health
   ```

### Switching Fails

1. Check both deployments exist:
   ```bash
   kubectl get deploy -n vllm-system
   ```

2. Manually scale if needed:
   ```bash
   kubectl scale deploy -n vllm-system mock-vllm --replicas=1
   kubectl scale deploy -n vllm-system vllm --replicas=0
   ```

## Best Practices

1. **Use mock vLLM for**:
   - Integration testing
   - Development environments
   - CI/CD pipelines
   - Resource-constrained environments

2. **Use real vLLM for**:
   - Performance testing
   - Model evaluation
   - Production workloads
   - Accuracy testing

3. **Resource Planning**:
   - Mock vLLM: 256Mi-512Mi RAM, 100m-500m CPU
   - Real vLLM: 16Gi+ RAM, 8+ CPU cores, 1+ GPU

4. **Configuration Management**:
   - Keep separate values files for different environments
   - Use consistent naming for easy switching
   - Document model mappings between mock and real

## Cleanup

Remove mock vLLM deployment:

```bash
helm uninstall mock-vllm -n vllm-system
```

Remove all vLLM resources:

```bash
kubectl delete all -n vllm-system -l app.kubernetes.io/name=mock-vllm
```