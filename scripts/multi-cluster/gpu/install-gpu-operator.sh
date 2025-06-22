#!/bin/bash
# install-gpu-operator.sh - Install NVIDIA GPU Operator for Kubernetes GPU support

set -euo pipefail

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../utils/common.sh"

# Function to install GPU operator
install_gpu_operator() {
    local context=${1:-""}
    local version=${2:-"v23.9.1"}
    local simulate_gpu=${3:-"false"}
    
    if [ -z "$context" ]; then
        log_error "Kubernetes context is required"
        return 1
    fi
    
    log_info "Installing NVIDIA GPU Operator version $version..."
    
    # Create namespace
    create_namespace_if_not_exists "gpu-operator" "$context"
    
    # Add NVIDIA helm repository
    helm repo add nvidia https://nvidia.github.io/k8s-device-plugin || true
    helm repo add nvidia-gpu-operator https://nvidia.github.io/gpu-operator || true
    helm repo update
    
    # Check if we're in simulation mode (no real GPUs)
    local gpu_discovery_args=""
    if ! command_exists nvidia-smi || [[ "$simulate_gpu" == "true" ]]; then
        log_warning "No real GPUs detected. Installing GPU operator in simulation mode for testing."
        gpu_discovery_args="--set driver.enabled=false --set toolkit.enabled=false"
    fi
    
    # Create values file for GPU operator
    cat > /tmp/gpu-operator-values.yaml <<EOF
operator:
  defaultRuntime: containerd
  
driver:
  enabled: $([ -z "$gpu_discovery_args" ] && echo "true" || echo "false")
  version: "535.104.12"
  
toolkit:
  enabled: $([ -z "$gpu_discovery_args" ] && echo "true" || echo "false")
  version: "v1.14.3-centos7"
  
devicePlugin:
  enabled: true
  version: "v0.14.3"
  config:
    name: nvidia-device-plugin-config
    data:
      any: |
        version: v1
        flags:
          migStrategy: none
          failOnInitError: true
          nvidiaDriverRoot: /
          plugin:
            passDeviceSpecs: false
            deviceListStrategy: envvar
            deviceIDStrategy: uuid
          
dcgmExporter:
  enabled: true
  version: "3.1.7-3.1.4"
  serviceMonitor:
    enabled: true
    
gfd:
  enabled: true
  version: "v0.8.2"
  
migManager:
  enabled: false
  
nodeStatusExporter:
  enabled: true
  
gds:
  enabled: false
  
vgpuManager:
  enabled: false
  
vgpuDeviceManager:
  enabled: false
  
sandboxDevicePlugin:
  enabled: false
  
validator:
  repository: nvcr.io/nvidia/cloud-native
  image: gpu-operator-validator
  version: "v23.9.1"
EOF
    
    # Install GPU operator
    helm upgrade --install gpu-operator nvidia-gpu-operator/gpu-operator \
        --namespace gpu-operator \
        --values /tmp/gpu-operator-values.yaml \
        $gpu_discovery_args \
        --kubeconfig "$HOME/.kube/config" \
        --kube-context "$context" \
        --version "$version" \
        --wait --timeout 10m
    
    rm -f /tmp/gpu-operator-values.yaml
    
    log_success "GPU Operator installed successfully"
    
    # Wait for GPU operator pods to be ready
    log_info "Waiting for GPU operator pods to be ready..."
    kubectl --context="$context" wait --for=condition=ready pod \
        -l app.kubernetes.io/name=gpu-operator \
        -n gpu-operator \
        --timeout=300s || log_warning "Some GPU operator pods may still be initializing"
    
    # Create GPU resource test pod
    if [[ "$simulate_gpu" != "true" ]] && command_exists nvidia-smi; then
        log_info "Creating GPU test pod..."
        cat <<EOF | kubectl --context="$context" apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: gpu-test
  namespace: default
spec:
  restartPolicy: Never
  containers:
  - name: cuda-container
    image: nvcr.io/nvidia/cuda:12.2.0-base-ubuntu22.04
    command: ["nvidia-smi"]
    resources:
      limits:
        nvidia.com/gpu: 1
EOF
        
        # Wait for test pod to complete
        sleep 5
        kubectl --context="$context" logs gpu-test -n default || log_warning "GPU test pod logs not available yet"
        kubectl --context="$context" delete pod gpu-test -n default --ignore-not-found=true
    fi
    
    # Display GPU resources
    log_info "GPU Resources in cluster:"
    kubectl --context="$context" describe nodes | grep -E "nvidia.com/gpu|Capacity:|Allocatable:" || log_info "No GPU resources detected"
}

# Function to create GPU device plugin for testing (when no real GPUs)
create_mock_gpu_plugin() {
    local context=$1
    
    log_info "Creating mock GPU device plugin for testing..."
    
    cat <<EOF | kubectl --context="$context" apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: mock-gpu-config
  namespace: kube-system
data:
  config.yaml: |
    version: v1
    flags:
      migStrategy: none
    resources:
    - name: nvidia.com/gpu
      replicas: 2
---
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: nvidia-device-plugin-daemonset
  namespace: kube-system
spec:
  selector:
    matchLabels:
      name: nvidia-device-plugin-ds
  updateStrategy:
    type: RollingUpdate
  template:
    metadata:
      labels:
        name: nvidia-device-plugin-ds
    spec:
      tolerations:
      - key: nvidia.com/gpu
        operator: Exists
        effect: NoSchedule
      priorityClassName: "system-node-critical"
      containers:
      - image: nvcr.io/nvidia/k8s-device-plugin:v0.14.3
        name: nvidia-device-plugin-ctr
        env:
        - name: FAIL_ON_INIT_ERROR
          value: "false"
        - name: PASS_DEVICE_SPECS
          value: "false"
        - name: DEVICE_LIST_STRATEGY
          value: "envvar"
        - name: DEVICE_ID_STRATEGY
          value: "uuid"
        - name: NVIDIA_VISIBLE_DEVICES
          value: "all"
        securityContext:
          allowPrivilegeEscalation: false
          capabilities:
            drop: ["ALL"]
        volumeMounts:
        - name: device-plugin
          mountPath: /var/lib/kubelet/device-plugins
        - name: config
          mountPath: /etc/nvidia-device-plugin
          readOnly: true
      volumes:
      - name: device-plugin
        hostPath:
          path: /var/lib/kubelet/device-plugins
      - name: config
        configMap:
          name: mock-gpu-config
      nodeSelector:
        nvidia.com/gpu.present: "true"
EOF
    
    log_success "Mock GPU device plugin created"
}

# Function to install GPU monitoring
install_gpu_monitoring() {
    local context=$1
    
    log_info "Installing GPU monitoring components..."
    
    # Create ServiceMonitor for Prometheus
    cat <<EOF | kubectl --context="$context" apply -f -
apiVersion: v1
kind: Service
metadata:
  name: nvidia-dcgm-exporter
  namespace: gpu-operator
  labels:
    app: nvidia-dcgm-exporter
spec:
  ports:
  - name: metrics
    port: 9400
    targetPort: 9400
  selector:
    app.kubernetes.io/name: nvidia-dcgm-exporter
---
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: nvidia-dcgm-exporter
  namespace: gpu-operator
spec:
  selector:
    matchLabels:
      app: nvidia-dcgm-exporter
  endpoints:
  - port: metrics
    interval: 30s
    path: /metrics
EOF
    
    # Create Grafana dashboard ConfigMap
    cat <<EOF | kubectl --context="$context" apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: gpu-dashboard
  namespace: monitoring
  labels:
    grafana_dashboard: "1"
data:
  gpu-dashboard.json: |
    {
      "dashboard": {
        "title": "NVIDIA GPU Metrics",
        "panels": [
          {
            "title": "GPU Utilization",
            "targets": [
              {
                "expr": "DCGM_FI_DEV_GPU_UTIL"
              }
            ]
          },
          {
            "title": "GPU Memory Usage",
            "targets": [
              {
                "expr": "DCGM_FI_DEV_FB_USED"
              }
            ]
          },
          {
            "title": "GPU Temperature",
            "targets": [
              {
                "expr": "DCGM_FI_DEV_GPU_TEMP"
              }
            ]
          }
        ]
      }
    }
EOF
    
    log_success "GPU monitoring components installed"
}

# Export functions
export -f install_gpu_operator
export -f create_mock_gpu_plugin
export -f install_gpu_monitoring