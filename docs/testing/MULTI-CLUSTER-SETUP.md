# Multi-Cluster Setup Guide

This guide provides comprehensive instructions for setting up and managing a multi-cluster Kubernetes environment for E2E testing of the Bud Runtime inference stack (BudProxy → AIBrix → VLLM).

## Overview

The multi-cluster setup consists of:
- **Application Cluster**: Hosts BudProxy (API Gateway) and supporting services
- **Inference Cluster**: Hosts AIBrix (Control Plane) and VLLM (Inference Engine) with GPU support
- **Cross-Cluster Networking**: Secure communication between clusters

## Prerequisites

### System Requirements
- Linux or macOS (WSL2 for Windows)
- Minimum 16GB RAM (32GB recommended for GPU workloads)
- 50GB free disk space
- Docker installed and running
- (Optional) NVIDIA GPU with drivers for real GPU testing

### Required Tools
The setup scripts will automatically install these if missing:
- K3d (for creating K3s clusters)
- kubectl
- Helm 3.x
- jq (for JSON processing)
- curl

## Quick Start

### 1. Clone the Repository
```bash
git clone <repository-url>
cd bud-runtime
git checkout testing-setup
```

### 2. Setup Complete Multi-Cluster Environment
```bash
# Default setup with GPU support
./scripts/multi-cluster/setup-multi-cluster.sh

# Setup without GPU support
./scripts/multi-cluster/setup-multi-cluster.sh --enable-gpu false

# Setup with custom cluster names
./scripts/multi-cluster/setup-multi-cluster.sh \
  --app-cluster-name my-app \
  --inference-cluster-name my-inference

# Parallel cluster setup (faster)
./scripts/multi-cluster/setup-multi-cluster.sh --parallel
```

### 3. Verify Setup
```bash
# Check cluster status
./scripts/multi-cluster/utils/cluster-status.sh

# Show detailed status with pods
./scripts/multi-cluster/utils/cluster-status.sh --show-pods --show-services
```

## Detailed Setup Instructions

### Application Cluster Setup

The application cluster hosts the API gateway and supporting services:

```bash
./scripts/multi-cluster/setup-app-cluster.sh \
  --cluster-name bud-app \
  --agents 2 \
  --server-memory 4G \
  --agent-memory 4G
```

**Installed Components:**
- Cert-Manager for TLS certificate management
- Dapr for service mesh capabilities
- Prometheus & Grafana for monitoring
- Namespace: `bud-system` for application services

**Access Points:**
- API Server: https://localhost:6443
- Load Balancer: http://localhost:8080
- Grafana: http://localhost:8080 (admin/admin)

### Inference Cluster Setup

The inference cluster hosts AI/ML workloads with optional GPU support:

```bash
./scripts/multi-cluster/setup-inference-cluster.sh \
  --cluster-name bud-inference \
  --agents 3 \
  --server-memory 8G \
  --agent-memory 16G \
  --enable-gpu true
```

**Installed Components:**
- NVIDIA GPU Operator (if GPU enabled)
- Prometheus with GPU metrics
- Namespaces: `aibrix-system`, `vllm-system`
- Resource quotas for workload isolation

**Access Points:**
- API Server: https://localhost:6444
- Load Balancer: http://localhost:8081
- Grafana: http://localhost:8081 (admin/admin)

### Cross-Cluster Networking

Setup secure communication between clusters:

```bash
# Basic networking (NodePort-based)
./scripts/multi-cluster/networking/setup-cluster-mesh.sh \
  --cluster1 bud-app \
  --cluster2 bud-inference \
  --networking-solution basic

# Advanced networking with Submariner (recommended for production)
./scripts/multi-cluster/networking/setup-cluster-mesh.sh \
  --cluster1 bud-app \
  --cluster2 bud-inference \
  --networking-solution submariner
```

## Working with Clusters

### Switching Between Clusters
```bash
# Switch to application cluster
kubectl config use-context k3d-bud-app

# Switch to inference cluster
kubectl config use-context k3d-bud-inference

# List all contexts
kubectl config get-contexts
```

### Deploying Services

#### Deploy BudProxy to Application Cluster
```bash
kubectl config use-context k3d-bud-app
helm install budproxy ./helm/budproxy \
  --namespace bud-system \
  --create-namespace
```

#### Deploy AIBrix to Inference Cluster
```bash
kubectl config use-context k3d-bud-inference
helm install aibrix ./helm/aibrix \
  --namespace aibrix-system \
  --create-namespace
```

#### Deploy VLLM to Inference Cluster
```bash
kubectl config use-context k3d-bud-inference
helm install vllm ./helm/vllm \
  --namespace vllm-system \
  --create-namespace \
  --set resources.nvidia.com/gpu=1
```

## GPU Support

### Checking GPU Availability
```bash
# Check GPU nodes
kubectl --context k3d-bud-inference get nodes -l nvidia.com/gpu.present=true

# Check GPU resources
kubectl --context k3d-bud-inference describe nodes | grep nvidia.com/gpu

# Test GPU access
kubectl --context k3d-bud-inference run gpu-test \
  --image=nvcr.io/nvidia/cuda:12.2.0-base-ubuntu22.04 \
  --rm -it --restart=Never \
  --limits=nvidia.com/gpu=1 \
  -- nvidia-smi
```

### GPU Monitoring
Access GPU metrics in Grafana:
1. Navigate to http://localhost:8081
2. Login with admin/admin
3. Go to Dashboards → GPU → NVIDIA GPU Metrics

## Monitoring and Observability

### Accessing Grafana
- Application Cluster: http://localhost:8080
- Inference Cluster: http://localhost:8081
- Default credentials: admin/admin

### Accessing Prometheus
- Application Cluster: http://localhost:8080/prometheus
- Inference Cluster: http://localhost:8081/prometheus

### Key Metrics to Monitor
- Cluster resource utilization (CPU, Memory)
- GPU utilization and temperature (inference cluster)
- Pod status and restart counts
- Service latency and error rates
- Cross-cluster network latency

## Troubleshooting

### Common Issues

#### Cluster Creation Fails
```bash
# Check Docker status
docker info

# Check available resources
free -h
df -h

# Check for port conflicts
sudo lsof -i :6443
sudo lsof -i :6444
```

#### GPU Not Detected
```bash
# Check NVIDIA drivers
nvidia-smi

# Check GPU operator logs
kubectl --context k3d-bud-inference logs -n gpu-operator -l app=gpu-operator

# Reinstall GPU operator
kubectl --context k3d-bud-inference delete namespace gpu-operator
./scripts/multi-cluster/gpu/install-gpu-operator.sh k3d-bud-inference
```

#### Cross-Cluster Communication Issues
```bash
# Test basic connectivity
./scripts/multi-cluster/utils/cluster-status.sh

# Check network policies
kubectl --context k3d-bud-app get networkpolicies --all-namespaces
kubectl --context k3d-bud-inference get networkpolicies --all-namespaces

# Re-setup networking
./scripts/multi-cluster/networking/setup-cluster-mesh.sh \
  --cluster1 bud-app \
  --cluster2 bud-inference
```

### Cleanup and Reset

#### Clean Specific Clusters
```bash
./scripts/multi-cluster/utils/cleanup-clusters.sh \
  --app-cluster-name bud-app \
  --inference-cluster-name bud-inference
```

#### Clean Everything
```bash
# Remove all clusters and registry
./scripts/multi-cluster/utils/cleanup-clusters.sh \
  --all \
  --cleanup-registry \
  --force
```

## Configuration Files

Configuration files are generated during setup:

```
configs/
├── app-cluster/
│   └── cluster-info.yaml      # Application cluster configuration
├── inference-cluster/
│   └── cluster-info.yaml      # Inference cluster configuration
└── networking/
    ├── cluster-endpoints.yaml  # Cross-cluster service endpoints
    └── networking-info.yaml    # Networking configuration
```

## Environment Variables

Key environment variables for customization:

```bash
# Application Cluster
export APP_CLUSTER_NAME=bud-app
export APP_CLUSTER_AGENTS=2
export APP_API_PORT=6443
export APP_LB_PORT=8080

# Inference Cluster
export INFERENCE_CLUSTER_NAME=bud-inference
export INFERENCE_CLUSTER_AGENTS=3
export INFERENCE_API_PORT=6444
export INFERENCE_LB_PORT=8081
export ENABLE_GPU=true

# Shared
export REGISTRY_NAME=bud-registry
export REGISTRY_PORT=5111
export K3S_VERSION=v1.28.5-k3s1
```

## Next Steps

1. **Deploy Services**: Follow the deployment guide to install BudProxy, AIBrix, and VLLM
2. **Run E2E Tests**: See [TESTING.md](TESTING.md) for running end-to-end tests
3. **Configure Models**: Set up LLM models for inference testing
4. **Performance Tuning**: Optimize cluster resources based on workload

## References

- [K3d Documentation](https://k3d.io/)
- [K3s Documentation](https://docs.k3s.io/)
- [NVIDIA GPU Operator](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/overview.html)
- [Submariner Documentation](https://submariner.io/)
- [Dapr Documentation](https://docs.dapr.io/)