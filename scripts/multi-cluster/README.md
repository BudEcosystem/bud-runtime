# Multi-Cluster Scripts

This directory contains scripts for setting up and managing a multi-cluster Kubernetes environment for E2E testing of the Bud Runtime inference stack.

## Directory Structure

```
multi-cluster/
├── setup-app-cluster.sh        # Setup application cluster (BudProxy)
├── setup-inference-cluster.sh  # Setup inference cluster (AIBrix + VLLM)
├── setup-multi-cluster.sh      # Wrapper script for complete setup
├── gpu/
│   └── install-gpu-operator.sh # GPU operator installation
├── networking/
│   └── setup-cluster-mesh.sh   # Cross-cluster networking setup
└── utils/
    ├── common.sh               # Shared functions and utilities
    ├── cleanup-clusters.sh     # Cleanup clusters and resources
    └── cluster-status.sh       # Check cluster health and status
```

## Quick Start

### Complete Setup
```bash
# Setup both clusters with default configuration
./setup-multi-cluster.sh

# Setup without GPU support
./setup-multi-cluster.sh --enable-gpu false

# Setup with custom names
./setup-multi-cluster.sh \
  --app-cluster-name prod-app \
  --inference-cluster-name prod-inference
```

### Individual Cluster Setup
```bash
# Setup only application cluster
./setup-app-cluster.sh --cluster-name bud-app

# Setup only inference cluster
./setup-inference-cluster.sh --cluster-name bud-inference --enable-gpu true
```

### Cluster Management
```bash
# Check status
./utils/cluster-status.sh

# Cleanup specific clusters
./utils/cleanup-clusters.sh

# Cleanup everything
./utils/cleanup-clusters.sh --all --cleanup-registry --force
```

## Script Details

### setup-multi-cluster.sh
Main orchestration script that:
- Sets up both application and inference clusters
- Configures cross-cluster networking
- Validates the complete setup
- Supports parallel cluster creation

**Options:**
- `--app-cluster-name`: Name for application cluster
- `--inference-cluster-name`: Name for inference cluster
- `--setup-networking`: Enable cross-cluster networking (default: true)
- `--enable-gpu`: Enable GPU support (default: true)
- `--parallel`: Create clusters in parallel

### setup-app-cluster.sh
Creates the application cluster with:
- K3s using K3d
- Cert-Manager for TLS
- Dapr for service mesh
- Prometheus & Grafana for monitoring
- Optimized for API gateway workloads

**Options:**
- `--cluster-name`: Cluster name
- `--agents`: Number of worker nodes
- `--server-memory`: Memory for control plane
- `--agent-memory`: Memory for worker nodes

### setup-inference-cluster.sh
Creates the inference cluster with:
- K3s with GPU support
- NVIDIA GPU Operator
- Larger resource allocations
- Namespaces for AIBrix and VLLM
- GPU-aware monitoring

**Options:**
- `--cluster-name`: Cluster name
- `--agents`: Number of worker nodes
- `--enable-gpu`: Enable GPU support
- `--gpu-operator-version`: GPU operator version

### networking/setup-cluster-mesh.sh
Configures cross-cluster communication:
- Basic mode: NodePort-based connectivity
- Submariner mode: Full service mesh (recommended)
- Service discovery configuration
- Network policies

**Options:**
- `--cluster1`: First cluster name
- `--cluster2`: Second cluster name
- `--networking-solution`: basic or submariner

### utils/cleanup-clusters.sh
Safely removes clusters and resources:
- Individual or all clusters
- Optional registry cleanup
- Kubeconfig cleanup
- Temporary file removal

**Options:**
- `--all`: Remove all K3d clusters
- `--cleanup-registry`: Also remove local registry
- `--force`: Skip confirmation prompts

### utils/cluster-status.sh
Comprehensive health checking:
- Node and pod status
- Service availability
- Resource usage
- Cross-cluster connectivity
- Status report generation

**Options:**
- `--show-pods`: Display all pods
- `--show-services`: Display service endpoints
- `--no-networking-check`: Skip networking validation

## Environment Variables

```bash
# Application cluster
export APP_CLUSTER_NAME=bud-app
export APP_CLUSTER_AGENTS=2
export APP_API_PORT=6443
export APP_LB_PORT=8080

# Inference cluster
export INFERENCE_CLUSTER_NAME=bud-inference
export INFERENCE_CLUSTER_AGENTS=3
export INFERENCE_API_PORT=6444
export INFERENCE_LB_PORT=8081

# Common
export K3S_VERSION=v1.28.5-k3s1
export ENABLE_GPU=true
export SETUP_NETWORKING=true
```

## Troubleshooting

### Script Failures
- Check Docker daemon is running
- Ensure sufficient system resources
- Look for port conflicts
- Review logs in `/tmp/multi-cluster-setup-*.log`

### GPU Issues
- Verify NVIDIA drivers are installed
- Check GPU operator logs
- Ensure GPU nodes are properly labeled

### Networking Problems
- Verify both clusters are running
- Check firewall rules
- Review network policy configurations

## See Also
- [Multi-Cluster Setup Guide](../../docs/testing/MULTI-CLUSTER-SETUP.md)
- [E2E Testing Guide](../../docs/testing/TESTING.md)
- [Main Project README](../../README.md)