# Cluster Setup and NFD Configuration Guide

## Installation

### Automatic Deployment (Recommended)

Cluster setup is integrated into the provisioning process. When you provision a new cluster or run the setup playbook, NFD, GPU operators, and Aibrix components will be automatically deployed.

```bash
# Cluster setup with NFD, GPU operators, Prometheus, and Aibrix components
ansible-playbook budcluster/playbooks/setup_cluster.yaml \
  -e cluster_id=<cluster-uuid> \
  -e namespace=bud-runtime
```

This playbook will:
1. Install Node Feature Discovery (NFD)
2. Detect and install GPU Operator if NVIDIA GPUs are present
3. Detect and install Intel Device Plugin if HPUs are present
4. Configure NFD to extract CPU model names
5. Install Aibrix dependencies and core components for model autoscaling
6. Deploy Prometheus stack for hardware metrics collection
7. Configure Prometheus for metrics collection (forwarded to OTel Collector → ClickHouse)
8. Deploy DCGM Exporter for GPU metrics (if GPUs are detected)

### Manual Deployment

```bash
# Deploy NFD using the bud-stack chart
cd services/budcluster
helm install node-feature-discovery budcluster/charts/nfd \
  --namespace bud-runtime \
  --create-namespace \
  --set nfd.enabled=true

# Verify NFD is running
kubectl get pods -n node-feature-discovery
kubectl get nodes --show-labels | grep feature.node.kubernetes.io
```

## Configuration

### Environment Variables

```bash
# NFD Detection Configuration
ENABLE_NFD_DETECTION=true           # Enable NFD-based detection
NFD_FALLBACK_TO_CONFIGMAP=true     # Fall back to ConfigMap on NFD failure
NFD_DETECTION_TIMEOUT=30           # Timeout for NFD operations (seconds)
NFD_NAMESPACE=node-feature-discovery # NFD deployment namespace
```

### Runtime Behavior

- **NFD Primary**: When `ENABLE_NFD_DETECTION=true`, NFD is used as primary method
- **Fallback Mode**: When NFD fails and `NFD_FALLBACK_TO_CONFIGMAP=true`, falls back to ConfigMap
- **ConfigMap Only**: When `ENABLE_NFD_DETECTION=false`, uses existing ConfigMap method

### NFD Configuration Files

#### Main Configuration (`charts/nfd/values.yaml`)

```yaml
config:
  core:
    sleepInterval: 60s  # Update interval
  sources:
    cpu:
      cpuid:
        attributeBlacklist: []
        attributeWhitelist: []
    custom:
      - name: "cpu-info"
        labels:
          "cpu-model": "@cpu.model"
          "cpu-vendor": "@cpu.vendor_id"
    local:
      hooksEnabled: true  # Enable CPU model detection hooks
```

#### CPU Model Detection Hook

Create `/etc/nfd/hooks/cpu-model.sh`:
```bash
#!/bin/bash
CPU_MODEL=$(lscpu | grep "Model name:" | sed 's/Model name:\s*//')
echo "feature.node.kubernetes.io/local-cpu.model=$CPU_MODEL"
```

## Verification

### Check Installation

```bash
# Check NFD pods are running
kubectl get pods -n node-feature-discovery

# Check nodes have NFD labels
kubectl get nodes --show-labels | grep feature.node.kubernetes.io

# Test node info collection
ansible-playbook budcluster/playbooks/get_node_info.yaml \
  -e cluster_id=<cluster-uuid> \
  -e namespace=bud-runtime
```

### Expected Labels

#### GPU Node Labels
```yaml
nvidia.com/gpu.present: "true"
nvidia.com/gpu.count: "8"
nvidia.com/gpu.product: "NVIDIA A100-SXM4-40GB"
nvidia.com/gpu.memory: "40960"
nvidia.com/cuda.runtime.major: "12"
nvidia.com/cuda.runtime.minor: "2"
feature.node.kubernetes.io/pci-10de.present: "true"
```

#### CPU Node Labels
```yaml
feature.node.kubernetes.io/cpu-cpuid.AVX512F: "true"
feature.node.kubernetes.io/cpu-cpuid.VNNI: "true"
feature.node.kubernetes.io/cpu-cpuid.AMX: "true"
feature.node.kubernetes.io/cpu-cpuid.vendor_id: "GenuineIntel"
feature.node.kubernetes.io/cpu-model.family: "6"
feature.node.kubernetes.io/cpu-model.id: "143"
feature.node.kubernetes.io/local-cpu.model: "Intel(R) Xeon(R) Platinum 8480+"
```

## Chart Structure

The NFD integration uses proper Helm chart structure under `budcluster/charts/nfd/`:

```
charts/nfd/
├── Chart.yaml                    # Chart metadata with official NFD/GPU Operator dependencies
├── values.yaml                   # Bud-stack specific NFD configuration
├── nfd-worker-conf.yaml         # NFD worker configuration
├── templates/
│   ├── _helpers.tpl             # Common template helpers
│   ├── cpu-hook-configmap.yaml  # CPU model detection hook
│   ├── intel-device-plugin.yaml # Intel Gaudi HPU support
│   └── gaudi-device-plugin.yaml # Gaudi device plugin configuration
└── hooks/
    └── cpu-model.sh             # CPU model extraction script
```

## Troubleshooting

### NFD Not Installed

If you see this error:
```
Node Feature Discovery (NFD) is not installed on this cluster.
Please run setup_cluster.yaml to install NFD and required components.
```

Solution: Run `ansible-playbook setup_cluster.yaml` to setup the cluster.

### Missing CPU Model

If CPU model is not detected:
1. Check NFD local source configuration in `charts/nfd/values.yaml`
2. Ensure the local source hook is properly configured
3. Restart NFD workers after configuration changes

```bash
kubectl rollout restart daemonset/nfd-worker -n node-feature-discovery
```

### GPU Not Detected

If GPUs are not detected:
1. Check if GPU drivers are installed on nodes
2. Verify GPU Operator is deployed (automatic with setup_cluster.yaml)
3. Check node labels: `kubectl get node <node-name> -o yaml | grep nvidia`

### Detection Timeouts

```bash
# Increase timeout in configuration
export NFD_DETECTION_TIMEOUT=60
```

### Check Logs

```bash
# NFD master logs
kubectl logs -n node-feature-discovery deployment/nfd-master

# NFD worker logs (per node)
kubectl logs -n node-feature-discovery daemonset/nfd-worker

# GPU Feature Discovery logs
kubectl logs -n gpu-operator daemonset/gpu-feature-discovery

# Budcluster fallback logs
docker logs budcluster-app 2>&1 | grep -i "fallback\|nfd"
```

## Migration from node-info-collector

If upgrading from a version that used node-info-collector:

1. **Setup Cluster**: Run `setup_cluster.yaml`
2. **Clean up ConfigMaps**: Remove old node-info-collector ConfigMaps
   ```bash
   kubectl delete configmap -n <namespace> -l app=node-info-collector
   ```
3. **Remove DaemonSets**: Delete old collector DaemonSets
   ```bash
   kubectl delete daemonset -n <namespace> node-info-collector-cpu
   kubectl delete daemonset -n <namespace> node-info-collector-cuda
   ```
4. **Update environment**: Remove node-info-collector image variables from `.env`

## Performance Considerations

- **NFD Detection**: ~2-5 seconds for 10-20 nodes
- **ConfigMap Fallback**: ~10-15 seconds for same cluster
- **Memory Usage**: Minimal increase (~50MB per cluster)
- **Database Impact**: Additional JSONB fields, negligible performance impact
