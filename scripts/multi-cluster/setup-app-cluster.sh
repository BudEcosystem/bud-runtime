#!/bin/bash
# setup-app-cluster.sh - Setup K3d cluster for application services (BudProxy and supporting services)

set -euo pipefail

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/utils/common.sh"

# Default values
CLUSTER_NAME="${APP_CLUSTER_NAME:-bud-app}"
K3S_VERSION="${K3S_VERSION:-v1.28.5-k3s1}"
AGENTS="${APP_CLUSTER_AGENTS:-2}"
SERVER_MEMORY="${APP_SERVER_MEMORY:-4G}"
AGENT_MEMORY="${APP_AGENT_MEMORY:-4G}"
API_PORT="${APP_API_PORT:-6443}"
LB_PORT="${APP_LB_PORT:-8080}"
REGISTRY_NAME="${REGISTRY_NAME:-bud-registry}"
REGISTRY_PORT="${REGISTRY_PORT:-5111}"

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
        --help)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  --cluster-name NAME     Name of the cluster (default: $CLUSTER_NAME)"
            echo "  --agents N              Number of agent nodes (default: $AGENTS)"
            echo "  --k3s-version VERSION   K3s version to use (default: $K3S_VERSION)"
            echo "  --server-memory SIZE    Memory for server node (default: $SERVER_MEMORY)"
            echo "  --agent-memory SIZE     Memory for agent nodes (default: $AGENT_MEMORY)"
            echo "  --help                  Show this help message"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Main setup function
setup_app_cluster() {
    log_info "Setting up application cluster: $CLUSTER_NAME"
    
    # Verify prerequisites
    verify_prerequisites || exit 1
    install_k3d || exit 1
    install_helm || exit 1
    
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
    
    # Create K3d cluster for application services
    log_info "Creating K3d cluster '$CLUSTER_NAME' with 1 server and $AGENTS agents..."
    
    k3d cluster create "$CLUSTER_NAME" \
        --servers 1 \
        --agents "$AGENTS" \
        --image "rancher/k3s:$K3S_VERSION" \
        --api-port "$API_PORT" \
        --port "$LB_PORT:80@loadbalancer" \
        --port "443:443@loadbalancer" \
        --registry-use "k3d-$REGISTRY_NAME:$REGISTRY_PORT" \
        --k3s-arg "--disable=traefik@server:0" \
        --k3s-arg "--kube-apiserver-arg=feature-gates=EphemeralContainers=true@server:0" \
        --k3s-arg "--kube-scheduler-arg=feature-gates=EphemeralContainers=true@server:0" \
        --k3s-arg "--kubelet-arg=feature-gates=EphemeralContainers=true@agent:*" \
        --k3s-arg "--kubelet-arg=cpu-manager-policy=static@agent:*" \
        --k3s-arg "--kubelet-arg=reserved-cpus=0-1@agent:*" \
        --k3s-arg "--kubelet-arg=kube-reserved=cpu=200m,memory=500Mi@agent:*" \
        --k3s-arg "--kubelet-arg=system-reserved=cpu=200m,memory=500Mi@agent:*" \
        --servers-memory "$SERVER_MEMORY" \
        --agents-memory "$AGENT_MEMORY" \
        --wait
    
    # Wait for cluster to be ready
    wait_for_cluster_ready "$CLUSTER_NAME" || exit 1
    
    # Get kubeconfig
    get_cluster_kubeconfig "$CLUSTER_NAME" || exit 1
    
    # Apply system optimizations
    apply_system_optimizations
    
    # Label nodes for the application cluster
    log_info "Labeling nodes for application cluster..."
    kubectl --context="k3d-$CLUSTER_NAME" label nodes --all cluster-type=application --overwrite
    kubectl --context="k3d-$CLUSTER_NAME" label nodes --all cluster-name="$CLUSTER_NAME" --overwrite
    
    # Add Helm repositories
    add_helm_repos
    
    # Install cert-manager (required for many services)
    log_info "Installing cert-manager..."
    create_namespace_if_not_exists "cert-manager" "k3d-$CLUSTER_NAME"
    helm upgrade --install cert-manager jetstack/cert-manager \
        --namespace cert-manager \
        --set installCRDs=true \
        --set global.leaderElection.namespace=cert-manager \
        --kubeconfig "$HOME/.kube/config" \
        --kube-context "k3d-$CLUSTER_NAME" \
        --wait
    
    # Install Dapr for service mesh
    log_info "Installing Dapr..."
    create_namespace_if_not_exists "dapr-system" "k3d-$CLUSTER_NAME"
    helm upgrade --install dapr dapr/dapr \
        --namespace dapr-system \
        --set global.ha.enabled=false \
        --set global.mtls.enabled=true \
        --kubeconfig "$HOME/.kube/config" \
        --kube-context "k3d-$CLUSTER_NAME" \
        --wait
    
    # Install Prometheus for monitoring
    log_info "Installing Prometheus..."
    create_namespace_if_not_exists "monitoring" "k3d-$CLUSTER_NAME"
    helm upgrade --install prometheus prometheus-community/kube-prometheus-stack \
        --namespace monitoring \
        --set prometheus.prometheusSpec.retention=7d \
        --set prometheus.prometheusSpec.storageSpec.volumeClaimTemplate.spec.accessModes[0]=ReadWriteOnce \
        --set prometheus.prometheusSpec.storageSpec.volumeClaimTemplate.spec.resources.requests.storage=10Gi \
        --set grafana.enabled=true \
        --set grafana.adminPassword=admin \
        --kubeconfig "$HOME/.kube/config" \
        --kube-context "k3d-$CLUSTER_NAME" \
        --wait
    
    # Create namespace for bud services
    create_namespace_if_not_exists "bud-system" "k3d-$CLUSTER_NAME"
    
    # Generate cluster-specific configuration
    CONFIG_DIR="$SCRIPT_DIR/../../configs/app-cluster"
    mkdir -p "$CONFIG_DIR"
    
    cat > "$CONFIG_DIR/cluster-info.yaml" <<EOF
# Application Cluster Information
cluster:
  name: $CLUSTER_NAME
  type: application
  context: k3d-$CLUSTER_NAME
  api_endpoint: https://localhost:$API_PORT
  lb_endpoint: http://localhost:$LB_PORT
  
nodes:
  servers: 1
  agents: $AGENTS
  
resources:
  server_memory: $SERVER_MEMORY
  agent_memory: $AGENT_MEMORY
  
namespaces:
  - cert-manager
  - dapr-system
  - monitoring
  - bud-system
  
services:
  cert_manager:
    namespace: cert-manager
    chart: jetstack/cert-manager
  dapr:
    namespace: dapr-system
    chart: dapr/dapr
  prometheus:
    namespace: monitoring
    chart: prometheus-community/kube-prometheus-stack
    grafana_url: http://localhost:$LB_PORT/grafana
    prometheus_url: http://localhost:$LB_PORT/prometheus
EOF
    
    log_success "Application cluster '$CLUSTER_NAME' setup completed successfully!"
    log_info "Cluster context: k3d-$CLUSTER_NAME"
    log_info "API endpoint: https://localhost:$API_PORT"
    log_info "Load balancer: http://localhost:$LB_PORT"
    log_info "Grafana URL: http://localhost:$LB_PORT (admin/admin)"
    
    # Display cluster info
    echo
    log_info "Cluster nodes:"
    kubectl --context="k3d-$CLUSTER_NAME" get nodes
    
    echo
    log_info "Namespaces:"
    kubectl --context="k3d-$CLUSTER_NAME" get namespaces
}

# Run main function
setup_app_cluster