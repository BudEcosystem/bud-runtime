# Deployment Scripts

This directory contains scripts for deploying services to the multi-cluster environment.

## Available Scripts

### deploy-mock-vllm.sh

Deploy the mock vLLM service to the inference cluster for integration testing.

**Basic Usage:**
```bash
./deploy-mock-vllm.sh
```

**Advanced Usage:**
```bash
./deploy-mock-vllm.sh \
  --cluster-name bud-inference \
  --namespace vllm-system \
  --api-key "secret-key" \
  --processing-delay 0.5 \
  --image-tag v1.0.0
```

**Key Features:**
- Builds and pushes Docker image to local registry
- Deploys using Helm chart
- Optionally runs integration tests
- Supports dry-run mode

### switch-vllm-mode.sh

Switch between mock and real vLLM deployments in the inference cluster.

**Switch to Mock vLLM:**
```bash
./switch-vllm-mode.sh --mode mock
```

**Switch to Real vLLM:**
```bash
./switch-vllm-mode.sh --mode real
```

**How it works:**
- Scales down one deployment and scales up the other
- Updates the common `vllm` service to point to the active deployment
- Provides near-zero downtime switching

## Common Workflows

### 1. Initial Setup for Testing

```bash
# Deploy mock vLLM
./deploy-mock-vllm.sh

# Verify deployment
kubectl get all -n vllm-system
```

### 2. Testing with Mock vLLM

```bash
# Switch to mock mode
./switch-vllm-mode.sh --mode mock

# Run your integration tests
# ...

# Switch back to real vLLM if needed
./switch-vllm-mode.sh --mode real
```

### 3. Update Mock vLLM

```bash
# Deploy with new image tag
./deploy-mock-vllm.sh --image-tag v2.0.0

# Or update configuration
./deploy-mock-vllm.sh --processing-delay 1.0
```

### 4. Troubleshooting Deployment

```bash
# Dry run to see what would happen
./deploy-mock-vllm.sh --dry-run

# Check logs
kubectl logs -n vllm-system -l app.kubernetes.io/name=mock-vllm

# Test connectivity
kubectl port-forward -n vllm-system svc/mock-vllm 8000:8000
curl http://localhost:8000/health
```

## Environment Variables

The scripts respect these environment variables:

- `INFERENCE_CLUSTER_NAME`: Default cluster name (default: bud-inference)
- `VLLM_NAMESPACE`: Default namespace (default: vllm-system)
- `REGISTRY_NAME`: Docker registry name (default: bud-registry)
- `REGISTRY_PORT`: Docker registry port (default: 5111)
- `MOCK_VLLM_API_KEY`: API key for mock vLLM authentication

## Requirements

- K3d cluster must be running
- Local Docker registry must be available
- kubectl configured with cluster access
- Helm 3.x installed

## Related Documentation

- [Mock vLLM Service](../../services/mock-vllm/README.md)
- [Mock vLLM Deployment Guide](../../docs/testing/mock-vllm-deployment.md)
- [Inference Cluster Mock vLLM](../../docs/testing/inference-cluster-mock-vllm.md)
- [Multi-Cluster Setup](../multi-cluster/README.md)