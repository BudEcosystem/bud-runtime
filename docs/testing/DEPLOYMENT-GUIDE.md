# Deployment Guide

This guide covers the deployment of services across the multi-cluster environment for E2E testing.

## Overview

The deployment consists of two main components:
1. **Application Stack** (bud-stack): Deployed to the application cluster
2. **Inference Stack**: Deployed to the inference cluster

## Prerequisites

- Multi-cluster environment set up (see [MULTI-CLUSTER-SETUP.md](MULTI-CLUSTER-SETUP.md))
- Helm 3.x installed
- kubectl configured with both cluster contexts

## Quick Deployment

### Deploy Everything
```bash
# Deploy to both clusters with default configuration
./scripts/deploy/deploy-multi-cluster.sh

# Deploy with custom namespaces
./scripts/deploy/deploy-multi-cluster.sh \
  --app-namespace my-app \
  --inference-namespace my-inference

# Dry run to see what would be deployed
./scripts/deploy/deploy-multi-cluster.sh --dry-run
```

### Validate Deployment
```bash
# Run validation checks
./scripts/deploy/validate-deployment.sh

# Validate with E2E test
./scripts/deploy/validate-deployment.sh --verbose

# Skip GPU checks for CPU-only environments
./scripts/deploy/validate-deployment.sh --skip-gpu-check
```

## Detailed Deployment Steps

### 1. Deploy Application Stack

The application stack includes BudProxy (TensorZero Gateway) and supporting services.

```bash
# Deploy to application cluster
./scripts/deploy/deploy-app-cluster.sh \
  --cluster-name bud-app \
  --namespace bud-system

# Use custom values file
./scripts/deploy/deploy-app-cluster.sh \
  --values-file helm/bud-stack/environments/values-app-cluster.yaml

# Deploy without waiting
./scripts/deploy/deploy-app-cluster.sh --no-wait
```

**Deployed Services:**
- BudProxy (API Gateway)
- PostgreSQL (Primary database)
- Redis (Cache and pub/sub)
- MinIO (Object storage)
- ClickHouse (Analytics)
- Prometheus & Grafana (Monitoring)

### 2. Deploy Inference Stack

The inference stack includes AIBrix and VLLM instances.

```bash
# Deploy to inference cluster
./scripts/deploy/deploy-inference-cluster.sh \
  --cluster-name bud-inference \
  --namespace inference-system

# Deploy without GPU check
./scripts/deploy/deploy-inference-cluster.sh --skip-gpu-check

# Custom timeout for large models
./scripts/deploy/deploy-inference-cluster.sh --timeout 20m
```

**Deployed Services:**
- AIBrix (Control plane)
- VLLM instances (Model serving)
- Prometheus & Grafana (GPU monitoring)

### 3. Configure Cross-Cluster Communication

The deployment scripts automatically set up basic cross-cluster configuration:

```yaml
# In app cluster: Reference to inference services
apiVersion: v1
kind: Service
metadata:
  name: aibrix-external
  namespace: bud-system
spec:
  type: ExternalName
  externalName: inference-stack-aibrix.inference-system.svc.cluster.local
```

For full cross-cluster networking, ensure you've run:
```bash
./scripts/multi-cluster/networking/setup-cluster-mesh.sh \
  --cluster1 bud-app \
  --cluster2 bud-inference
```

## Configuration

### TensorZero Configuration

The BudProxy uses TensorZero configuration to route requests to models:

```toml
# configs/tensorzero-multi-cluster.toml
[models.llama2-7b]
routing = ["llama2-7b-vllm"]

[models.llama2-7b.providers.llama2-7b-vllm]
type = "openai"
base_url = "http://inference-stack-vllm-llama2-7b.inference-system.svc.cluster.local:8000/v1"
model_name = "meta-llama/Llama-2-7b-chat-hf"
```

### Model Configuration

Configure VLLM instances in the inference stack values:

```yaml
# helm/inference-stack/values.yaml
vllm:
  instances:
    - name: llama2-7b
      model: meta-llama/Llama-2-7b-chat-hf
      replicas: 1
      tensorParallelSize: 1
      maxModelLen: 4096
      resources:
        requests:
          nvidia.com/gpu: 1
```

### Environment-Specific Values

Use environment-specific values files:

```bash
# Local testing (small models, no GPU)
helm install inference-stack ./helm/inference-stack \
  -f helm/inference-stack/environments/values-local-testing.yaml

# Production-like (full models, GPU)
helm install inference-stack ./helm/inference-stack \
  -f helm/inference-stack/environments/values-inference-cluster.yaml
```

## Accessing Services

### Port Forwarding

After deployment, access services via port-forward:

```bash
# BudProxy API Gateway
kubectl --context=k3d-bud-app port-forward \
  -n bud-system svc/budproxy-service 8000:8000

# AIBrix Control Plane
kubectl --context=k3d-bud-inference port-forward \
  -n inference-system svc/inference-stack-aibrix 8080:8080

# VLLM Model Endpoint
kubectl --context=k3d-bud-inference port-forward \
  -n inference-system svc/inference-stack-vllm-llama2-7b 8001:8000
```

### Testing Endpoints

```bash
# Test BudProxy health
curl http://localhost:8000/health

# Test model inference through BudProxy
curl http://localhost:8000/v1/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama2-7b",
    "prompt": "Hello, how are you?",
    "max_tokens": 50
  }'

# Test VLLM directly
curl http://localhost:8001/v1/models
```

### Monitoring

Access Grafana dashboards:

```bash
# App cluster monitoring
kubectl --context=k3d-bud-app port-forward \
  -n bud-system svc/grafana 3000:80
# http://localhost:3000 (admin/admin)

# Inference cluster monitoring
kubectl --context=k3d-bud-inference port-forward \
  -n inference-system svc/grafana 3001:80
# http://localhost:3001 (admin/admin)
```

## Troubleshooting

### Deployment Issues

1. **Pods not starting**
   ```bash
   # Check pod status
   kubectl get pods -n bud-system
   kubectl get pods -n inference-system
   
   # Describe problematic pod
   kubectl describe pod <pod-name> -n <namespace>
   
   # Check logs
   kubectl logs <pod-name> -n <namespace>
   ```

2. **Service connectivity issues**
   ```bash
   # Test service DNS resolution
   kubectl run test-dns --rm -it --image=busybox -- \
     nslookup aibrix-external.bud-system.svc.cluster.local
   
   # Test service endpoint
   kubectl run test-curl --rm -it --image=curlimages/curl -- \
     curl -v http://budproxy-service.bud-system:8000/health
   ```

3. **GPU not available**
   ```bash
   # Check GPU nodes
   kubectl get nodes -l nvidia.com/gpu.present=true
   
   # Check GPU operator
   kubectl get pods -n gpu-operator
   
   # Check GPU allocation
   kubectl describe nodes | grep -A 5 "Allocated resources"
   ```

### Model Loading Issues

1. **Model download fails**
   - Check internet connectivity
   - Verify HuggingFace token if using private models
   - Check PVC storage space

2. **Out of memory**
   - Reduce `gpu_memory_utilization`
   - Use smaller batch sizes
   - Consider model quantization

3. **Slow inference**
   - Check GPU utilization
   - Verify tensor parallel settings
   - Monitor network latency between clusters

## Advanced Configuration

### Custom Model Deployment

Deploy a custom model by creating a new values file:

```yaml
# my-model-values.yaml
vllm:
  instances:
    - name: my-model
      model: organization/model-name
      replicas: 2
      tensorParallelSize: 2
      resources:
        requests:
          nvidia.com/gpu: 2
      autoscaling:
        enabled: true
        minReplicas: 1
        maxReplicas: 4
```

Deploy with:
```bash
helm upgrade inference-stack ./helm/inference-stack \
  -f my-model-values.yaml
```

### Multi-Model Routing

Configure BudProxy for A/B testing:

```toml
[models.chat]
routing = ["model-a", "model-b"]
routing_strategy = "round_robin"  # or "weighted", "least_latency"

[models.chat.providers.model-a]
type = "openai"
base_url = "http://vllm-model-a:8000/v1"
weight = 0.7

[models.chat.providers.model-b]
type = "openai"
base_url = "http://vllm-model-b:8000/v1"
weight = 0.3
```

### Resource Optimization

1. **CPU-only deployment** (for testing):
   ```yaml
   vllm:
     instances:
       - name: test-model
         model: facebook/opt-125m
         resources:
           requests:
             cpu: 2
             memory: 4Gi
   ```

2. **Multi-GPU deployment**:
   ```yaml
   vllm:
     instances:
       - name: large-model
         model: meta-llama/Llama-2-70b-chat-hf
         tensorParallelSize: 4
         resources:
           requests:
             nvidia.com/gpu: 4
   ```

## Next Steps

1. **Run E2E Tests**: See [TESTING.md](TESTING.md)
2. **Monitor Performance**: Check Grafana dashboards
3. **Scale Services**: Adjust replicas and resources
4. **Add Models**: Deploy additional models as needed

## Reference

- [Multi-Cluster Setup](MULTI-CLUSTER-SETUP.md)
- [Testing Guide](TESTING.md)
- [Helm Charts Documentation](../../helm/)