# Inference Stack Helm Chart

This Helm chart deploys the inference stack (AIBrix + VLLM) for testing the Bud Runtime E2E inference pipeline.

## Overview

The inference stack consists of:
- **AIBrix**: Cloud-native AI platform for managing LLM infrastructure
- **VLLM**: High-performance inference engine for serving LLMs
- **Monitoring**: Prometheus and Grafana for observability
- **Storage**: Integration with MinIO for model storage

## Prerequisites

- Kubernetes 1.24+
- Helm 3.x
- GPU nodes (optional but recommended)
- MinIO deployed (or S3-compatible storage)

## Installation

### Add Helm repositories
```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update
```

### Install the chart
```bash
# Install with default values
helm install inference-stack ./helm/inference-stack \
  --namespace inference-system \
  --create-namespace

# Install with custom values
helm install inference-stack ./helm/inference-stack \
  --namespace inference-system \
  --create-namespace \
  -f my-values.yaml

# Install with specific cluster configuration
helm install inference-stack ./helm/inference-stack \
  --namespace inference-system \
  --create-namespace \
  -f environments/values-inference-cluster.yaml
```

## Configuration

### Key Configuration Options

| Parameter | Description | Default |
|-----------|-------------|---------|
| `global.namespace` | Target namespace | `inference-system` |
| `aibrix.enabled` | Enable AIBrix deployment | `true` |
| `aibrix.replicas` | Number of AIBrix replicas | `2` |
| `aibrix.resources` | Resource requests/limits | See values.yaml |
| `vllm.enabled` | Enable VLLM deployment | `true` |
| `vllm.instances` | List of VLLM model instances | See values.yaml |
| `prometheus.enabled` | Enable Prometheus | `true` |
| `grafana.enabled` | Enable Grafana | `true` |

### Model Configuration

Configure VLLM instances in `values.yaml`:

```yaml
vllm:
  instances:
    - name: llama2-7b
      enabled: true
      model: meta-llama/Llama-2-7b-chat-hf
      replicas: 1
      downloadModel: true
      tensorParallelSize: 1
      maxModelLen: 4096
      resources:
        requests:
          nvidia.com/gpu: 1
```

### GPU Configuration

For GPU support:
```yaml
vllm:
  nodeSelector:
    nvidia.com/gpu.present: "true"
  tolerations:
    - key: nvidia.com/gpu
      operator: Exists
      effect: NoSchedule
```

### Storage Configuration

Configure model storage:
```yaml
vllm:
  defaults:
    storage:
      size: 100Gi
      className: local-path

minio:
  enabled: true
  endpoint: minio-service.bud-system.svc.cluster.local:9000
  accessKey: minioadmin
  secretKey: minioadmin
```

## Usage

### Accessing Services

After installation, you can access:

```bash
# AIBrix API
kubectl port-forward -n inference-system svc/inference-stack-aibrix 8080:8080

# VLLM instances
kubectl port-forward -n inference-system svc/inference-stack-vllm-llama2-7b 8000:8000

# Grafana
kubectl port-forward -n inference-system svc/grafana 3000:80

# Prometheus
kubectl port-forward -n inference-system svc/prometheus-prometheus 9090:9090
```

### Testing Inference

```bash
# Test VLLM endpoint
curl http://localhost:8000/v1/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "meta-llama/Llama-2-7b-chat-hf",
    "prompt": "Hello, how are you?",
    "max_tokens": 50
  }'

# Check model status
curl http://localhost:8000/v1/models
```

### Monitoring

Grafana dashboards are available at http://localhost:3000 (admin/admin):
- GPU Metrics Dashboard
- Inference Performance Dashboard
- Resource Utilization Dashboard

## Troubleshooting

### Common Issues

1. **Models not downloading**
   - Check HuggingFace token if using private models
   - Verify internet connectivity
   - Check PVC storage availability

2. **GPU not detected**
   - Ensure GPU operator is installed
   - Check node labels: `nvidia.com/gpu.present=true`
   - Verify GPU driver installation

3. **High memory usage**
   - Adjust `gpuMemoryUtilization` parameter
   - Reduce `maxNumSeqs` for batching
   - Consider quantization options

### Debug Commands

```bash
# Check AIBrix logs
kubectl logs -n inference-system -l app.kubernetes.io/component=aibrix

# Check VLLM logs
kubectl logs -n inference-system -l app.kubernetes.io/component=vllm

# Check pod status
kubectl get pods -n inference-system

# Describe problematic pod
kubectl describe pod -n inference-system <pod-name>
```

## Uninstall

```bash
# Uninstall the release
helm uninstall inference-stack -n inference-system

# Clean up namespace (optional)
kubectl delete namespace inference-system
```

## Development

### Running locally without GPU
```yaml
vllm:
  instances:
    - name: test-model
      model: facebook/opt-125m  # Small model
      resources:
        requests:
          cpu: 2
          memory: 4Gi
        limits:
          cpu: 4
          memory: 8Gi
```

### Updating Dependencies
```bash
helm dependency update
```

## License

Apache License 2.0