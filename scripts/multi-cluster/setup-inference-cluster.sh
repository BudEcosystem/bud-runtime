#!/bin/bash
# setup-inference-cluster.sh - Setup K3d cluster for inference services (AIBrix and VLLM) with GPU support

set -euo pipefail

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/utils/common.sh"

# Default values
CLUSTER_NAME="${INFERENCE_CLUSTER_NAME:-bud-inference}"
K3S_VERSION="${K3S_VERSION:-v1.28.5-k3s1}"
AGENTS="${INFERENCE_CLUSTER_AGENTS:-3}"
SERVER_MEMORY="${INFERENCE_SERVER_MEMORY:-8G}"
AGENT_MEMORY="${INFERENCE_AGENT_MEMORY:-16G}"
API_PORT="${INFERENCE_API_PORT:-6444}"
LB_PORT="${INFERENCE_LB_PORT:-8081}"
REGISTRY_NAME="${REGISTRY_NAME:-bud-registry}"
REGISTRY_PORT="${REGISTRY_PORT:-5111}"
ENABLE_GPU="${ENABLE_GPU:-true}"
GPU_OPERATOR_VERSION="${GPU_OPERATOR_VERSION:-v23.9.1}"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --cluster-name)
            CLUSTER_NAME="$2"
            shift 2
            ;;
        --agents)
            AGENTS="$2"
            shift 2
            ;;
        --k3s-version)
            K3S_VERSION="$2"
            shift 2
            ;;
        --server-memory)
            SERVER_MEMORY="$2"
            shift 2
            ;;
        --agent-memory)
            AGENT_MEMORY="$2"
            shift 2
            ;;
        --enable-gpu)
            ENABLE_GPU="$2"
            shift 2
            ;;
        --gpu-operator-version)
            GPU_OPERATOR_VERSION="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  --cluster-name NAME         Name of the cluster (default: $CLUSTER_NAME)"
            echo "  --agents N                  Number of agent nodes (default: $AGENTS)"
            echo "  --k3s-version VERSION       K3s version to use (default: $K3S_VERSION)"
            echo "  --server-memory SIZE        Memory for server node (default: $SERVER_MEMORY)"
            echo "  --agent-memory SIZE         Memory for agent nodes (default: $AGENT_MEMORY)"
            echo "  --enable-gpu true|false     Enable GPU support (default: $ENABLE_GPU)"
            echo "  --gpu-operator-version VER  GPU operator version (default: $GPU_OPERATOR_VERSION)"
            echo "  --help                      Show this help message"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Check if running in environment with GPU support
check_gpu_availability() {
    if [[ "$ENABLE_GPU" == "true" ]]; then
        if command_exists nvidia-smi; then
            log_info "NVIDIA GPU detected:"
            nvidia-smi --list-gpus || true
            return 0
        else
            log_warning "No NVIDIA GPU detected. GPU support will be simulated for testing."
            log_warning "In production, ensure NVIDIA drivers are installed on GPU nodes."
            return 1
        fi
    fi
    return 0
}

# Main setup function
setup_inference_cluster() {
    log_info "Setting up inference cluster: $CLUSTER_NAME"
    
    # Verify prerequisites
    verify_prerequisites || exit 1
    install_k3d || exit 1
    install_helm || exit 1
    
    # Check GPU availability
    check_gpu_availability
    
    # Check if cluster already exists
    if k3d cluster list | grep -q "^$CLUSTER_NAME"; then
        log_warning "Cluster '$CLUSTER_NAME' already exists. Deleting it..."
        k3d cluster delete "$CLUSTER_NAME"
    fi
    
    # Create local registry if it doesn't exist
    if ! k3d registry list | grep -q "^$REGISTRY_NAME"; then
        log_info "Creating local registry '$REGISTRY_NAME' on port $REGISTRY_PORT..."
        k3d registry create "$REGISTRY_NAME" --port "$REGISTRY_PORT"
    fi
    
    # Prepare K3d cluster creation command
    local k3d_cmd=(
        k3d cluster create "$CLUSTER_NAME"
        --servers 1
        --agents "$AGENTS"
        --image "rancher/k3s:$K3S_VERSION"
        --api-port "$API_PORT"
        --port "$LB_PORT:80@loadbalancer"
        --port "443:443@loadbalancer"
        --registry-use "k3d-$REGISTRY_NAME:$REGISTRY_PORT"
        --k3s-arg "--disable=traefik@server:0"
        --k3s-arg "--kube-apiserver-arg=feature-gates=EphemeralContainers=true@server:0"
        --k3s-arg "--kube-scheduler-arg=feature-gates=EphemeralContainers=true@server:0"
        --k3s-arg "--kubelet-arg=feature-gates=EphemeralContainers=true@agent:*"
        --k3s-arg "--kubelet-arg=cpu-manager-policy=static@agent:*"
        --k3s-arg "--kubelet-arg=reserved-cpus=0-3@agent:*"
        --k3s-arg "--kubelet-arg=kube-reserved=cpu=500m,memory=1Gi@agent:*"
        --k3s-arg "--kubelet-arg=system-reserved=cpu=500m,memory=1Gi@agent:*"
        --servers-memory "$SERVER_MEMORY"
        --agents-memory "$AGENT_MEMORY"
    )
    
    # Add GPU-specific configurations if GPU is enabled
    if [[ "$ENABLE_GPU" == "true" ]]; then
        k3d_cmd+=(
            --k3s-arg "--kubelet-arg=fail-swap-on=false@agent:*"
            --volume "/dev/shm:/dev/shm@agent:*"
        )
        
        # If real GPUs are available, mount GPU devices
        if command_exists nvidia-smi; then
            k3d_cmd+=(
                --gpus all
            )
        fi
    fi
    
    k3d_cmd+=(--wait)
    
    # Create K3d cluster for inference services
    log_info "Creating K3d cluster '$CLUSTER_NAME' with 1 server and $AGENTS agents..."
    "${k3d_cmd[@]}"
    
    # Wait for cluster to be ready
    wait_for_cluster_ready "$CLUSTER_NAME" || exit 1
    
    # Get kubeconfig
    get_cluster_kubeconfig "$CLUSTER_NAME" || exit 1
    
    # Apply system optimizations
    apply_system_optimizations
    
    # Label nodes for the inference cluster
    log_info "Labeling nodes for inference cluster..."
    kubectl --context="k3d-$CLUSTER_NAME" label nodes --all cluster-type=inference --overwrite
    kubectl --context="k3d-$CLUSTER_NAME" label nodes --all cluster-name="$CLUSTER_NAME" --overwrite
    
    # Label agent nodes for GPU workloads (even in simulation mode)
    if [[ "$ENABLE_GPU" == "true" ]]; then
        log_info "Labeling agent nodes for GPU workloads..."
        for node in $(kubectl --context="k3d-$CLUSTER_NAME" get nodes -l '!node-role.kubernetes.io/control-plane' -o name); do
            kubectl --context="k3d-$CLUSTER_NAME" label "$node" nvidia.com/gpu.present=true --overwrite
            kubectl --context="k3d-$CLUSTER_NAME" label "$node" workload-type=gpu --overwrite
        done
    fi
    
    # Add Helm repositories
    add_helm_repos
    
    # Install cert-manager
    log_info "Installing cert-manager..."
    create_namespace_if_not_exists "cert-manager" "k3d-$CLUSTER_NAME"
    helm upgrade --install cert-manager jetstack/cert-manager \
        --namespace cert-manager \
        --set installCRDs=true \
        --set global.leaderElection.namespace=cert-manager \
        --kubeconfig "$HOME/.kube/config" \
        --kube-context "k3d-$CLUSTER_NAME" \
        --wait
    
    # Install NVIDIA GPU Operator if GPU is enabled
    if [[ "$ENABLE_GPU" == "true" ]]; then
        log_info "Installing NVIDIA GPU Operator..."
        source "$SCRIPT_DIR/gpu/install-gpu-operator.sh"
        install_gpu_operator "k3d-$CLUSTER_NAME" "$GPU_OPERATOR_VERSION"
    fi
    
    # Install Prometheus for monitoring with GPU metrics
    log_info "Installing Prometheus with GPU monitoring..."
    create_namespace_if_not_exists "monitoring" "k3d-$CLUSTER_NAME"
    
    # Create values file for Prometheus with GPU monitoring
    cat > /tmp/prometheus-gpu-values.yaml <<EOF
prometheus:
  prometheusSpec:
    retention: 7d
    storageSpec:
      volumeClaimTemplate:
        spec:
          accessModes: ["ReadWriteOnce"]
          resources:
            requests:
              storage: 20Gi
    additionalScrapeConfigs:
    - job_name: gpu-metrics
      scrape_interval: 30s
      kubernetes_sd_configs:
      - role: endpoints
        namespaces:
          names:
          - gpu-operator
      relabel_configs:
      - source_labels: [__meta_kubernetes_service_name]
        regex: nvidia-dcgm-exporter
        action: keep
grafana:
  enabled: true
  adminPassword: admin
  persistence:
    enabled: true
    size: 5Gi
  dashboardProviders:
    dashboardproviders.yaml:
      apiVersion: 1
      providers:
      - name: 'gpu-dashboards'
        orgId: 1
        folder: 'GPU'
        type: file
        disableDeletion: false
        updateIntervalSeconds: 60
        options:
          path: /var/lib/grafana/dashboards/gpu-dashboards
EOF
    
    helm upgrade --install prometheus prometheus-community/kube-prometheus-stack \
        --namespace monitoring \
        --values /tmp/prometheus-gpu-values.yaml \
        --kubeconfig "$HOME/.kube/config" \
        --kube-context "k3d-$CLUSTER_NAME" \
        --wait
    
    rm -f /tmp/prometheus-gpu-values.yaml
    
    # Create namespaces for inference services
    create_namespace_if_not_exists "aibrix-system" "k3d-$CLUSTER_NAME"
    create_namespace_if_not_exists "vllm-system" "k3d-$CLUSTER_NAME"
    
    # Apply resource quotas for inference namespaces
    log_info "Applying resource quotas for inference namespaces..."
    
    cat <<EOF | kubectl --context="k3d-$CLUSTER_NAME" apply -f -
apiVersion: v1
kind: ResourceQuota
metadata:
  name: inference-quota
  namespace: vllm-system
spec:
  hard:
    requests.cpu: "100"
    requests.memory: "500Gi"
    requests.nvidia.com/gpu: "8"
    persistentvolumeclaims: "20"
---
apiVersion: v1
kind: ResourceQuota
metadata:
  name: control-plane-quota
  namespace: aibrix-system
spec:
  hard:
    requests.cpu: "20"
    requests.memory: "40Gi"
    persistentvolumeclaims: "10"
EOF
    
    # Generate cluster-specific configuration
    CONFIG_DIR="$SCRIPT_DIR/../../configs/inference-cluster"
    mkdir -p "$CONFIG_DIR"
    
    cat > "$CONFIG_DIR/cluster-info.yaml" <<EOF
# Inference Cluster Information
cluster:
  name: $CLUSTER_NAME
  type: inference
  context: k3d-$CLUSTER_NAME
  api_endpoint: https://localhost:$API_PORT
  lb_endpoint: http://localhost:$LB_PORT
  
nodes:
  servers: 1
  agents: $AGENTS
  gpu_enabled: $ENABLE_GPU
  
resources:
  server_memory: $SERVER_MEMORY
  agent_memory: $AGENT_MEMORY
  gpu_operator_version: $GPU_OPERATOR_VERSION
  
namespaces:
  - cert-manager
  - monitoring
  - gpu-operator
  - aibrix-system
  - vllm-system
  
services:
  cert_manager:
    namespace: cert-manager
    chart: jetstack/cert-manager
  prometheus:
    namespace: monitoring
    chart: prometheus-community/kube-prometheus-stack
    grafana_url: http://localhost:$LB_PORT/grafana
    prometheus_url: http://localhost:$LB_PORT/prometheus
  gpu_operator:
    namespace: gpu-operator
    enabled: $ENABLE_GPU
    version: $GPU_OPERATOR_VERSION
    
inference_services:
  aibrix:
    namespace: aibrix-system
    description: "Cloud-native AI platform for managing LLM infrastructure"
  vllm:
    namespace: vllm-system
    description: "High-performance inference engine for LLMs"
    gpu_required: true
EOF
    
    log_success "Inference cluster '$CLUSTER_NAME' setup completed successfully!"
    log_info "Cluster context: k3d-$CLUSTER_NAME"
    log_info "API endpoint: https://localhost:$API_PORT"
    log_info "Load balancer: http://localhost:$LB_PORT"
    log_info "Grafana URL: http://localhost:$LB_PORT (admin/admin)"
    if [[ "$ENABLE_GPU" == "true" ]]; then
        log_info "GPU support: Enabled"
    fi
    
    # Display cluster info
    echo
    log_info "Cluster nodes:"
    kubectl --context="k3d-$CLUSTER_NAME" get nodes --show-labels
    
    echo
    log_info "Namespaces:"
    kubectl --context="k3d-$CLUSTER_NAME" get namespaces
    
    if [[ "$ENABLE_GPU" == "true" ]]; then
        echo
        log_info "GPU Resources:"
        kubectl --context="k3d-$CLUSTER_NAME" get nodes -o json | jq -r '.items[] | select(.status.capacity."nvidia.com/gpu" != null) | .metadata.name + ": " + .status.capacity."nvidia.com/gpu" + " GPUs"' || log_warning "GPU resources will be available after GPU operator installation completes"
    fi
}

# Run main function
setup_inference_cluster