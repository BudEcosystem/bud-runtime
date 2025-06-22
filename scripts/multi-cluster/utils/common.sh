#!/bin/bash
# common.sh - Common utilities and functions for multi-cluster deployment

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Verify prerequisites
verify_prerequisites() {
    local prereqs=("curl" "kubectl" "helm" "jq")
    local missing=()
    
    for cmd in "${prereqs[@]}"; do
        if ! command_exists "$cmd"; then
            missing+=("$cmd")
        fi
    done
    
    if [ ${#missing[@]} -gt 0 ]; then
        log_error "Missing prerequisites: ${missing[*]}"
        log_info "Please install the missing tools and try again."
        return 1
    fi
    
    log_success "All prerequisites are installed"
    return 0
}

# Wait for cluster to be ready
wait_for_cluster_ready() {
    local cluster_name=$1
    local max_attempts=${2:-60}
    local attempt=0
    
    log_info "Waiting for cluster '$cluster_name' to be ready..."
    
    while [ $attempt -lt $max_attempts ]; do
        if kubectl --context="k3d-$cluster_name" get nodes >/dev/null 2>&1; then
            local ready_nodes=$(kubectl --context="k3d-$cluster_name" get nodes -o json | jq '.items[] | select(.status.conditions[] | select(.type=="Ready" and .status=="True")) | .metadata.name' | wc -l)
            local total_nodes=$(kubectl --context="k3d-$cluster_name" get nodes -o json | jq '.items | length')
            
            if [ "$ready_nodes" -eq "$total_nodes" ] && [ "$total_nodes" -gt 0 ]; then
                log_success "Cluster '$cluster_name' is ready with $ready_nodes nodes"
                return 0
            fi
        fi
        
        attempt=$((attempt + 1))
        echo -n "."
        sleep 5
    done
    
    echo
    log_error "Cluster '$cluster_name' failed to become ready after $max_attempts attempts"
    return 1
}

# Install K3d if not present
install_k3d() {
    if command_exists k3d; then
        log_info "K3d is already installed"
        return 0
    fi
    
    log_info "Installing K3d..."
    curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash
    
    if command_exists k3d; then
        log_success "K3d installed successfully"
        return 0
    else
        log_error "Failed to install K3d"
        return 1
    fi
}

# Get cluster kubeconfig
get_cluster_kubeconfig() {
    local cluster_name=$1
    local kubeconfig_path=${2:-"$HOME/.kube/config"}
    
    log_info "Retrieving kubeconfig for cluster '$cluster_name'..."
    
    if k3d kubeconfig merge "$cluster_name" --output "$kubeconfig_path" >/dev/null 2>&1; then
        log_success "Kubeconfig for '$cluster_name' saved to $kubeconfig_path"
        return 0
    else
        log_error "Failed to retrieve kubeconfig for cluster '$cluster_name'"
        return 1
    fi
}

# Create namespace if it doesn't exist
create_namespace_if_not_exists() {
    local namespace=$1
    local context=${2:-""}
    
    local kubectl_cmd="kubectl"
    if [ -n "$context" ]; then
        kubectl_cmd="kubectl --context=$context"
    fi
    
    if $kubectl_cmd get namespace "$namespace" >/dev/null 2>&1; then
        log_info "Namespace '$namespace' already exists"
    else
        log_info "Creating namespace '$namespace'..."
        if $kubectl_cmd create namespace "$namespace"; then
            log_success "Namespace '$namespace' created"
        else
            log_error "Failed to create namespace '$namespace'"
            return 1
        fi
    fi
    
    return 0
}

# Apply system optimizations (from original setup-cluster.sh)
apply_system_optimizations() {
    log_info "Applying system optimizations..."
    
    # Network optimizations
    sudo sysctl -w net.core.somaxconn=65535
    sudo sysctl -w net.ipv4.ip_local_port_range="1024 65535"
    sudo sysctl -w net.ipv4.tcp_tw_reuse=1
    sudo sysctl -w net.ipv4.tcp_fin_timeout=30
    sudo sysctl -w net.core.netdev_max_backlog=5000
    sudo sysctl -w net.ipv4.tcp_max_syn_backlog=8192
    
    # Memory optimizations
    sudo sysctl -w vm.overcommit_memory=1
    sudo sysctl -w vm.panic_on_oom=0
    sudo sysctl -w kernel.panic=10
    sudo sysctl -w kernel.panic_on_oops=1
    
    # File descriptor limits
    sudo sysctl -w fs.file-max=2097152
    sudo sysctl -w fs.nr_open=2097152
    
    log_success "System optimizations applied"
}

# Install Helm if not present
install_helm() {
    if command_exists helm; then
        log_info "Helm is already installed"
        return 0
    fi
    
    log_info "Installing Helm..."
    curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
    
    if command_exists helm; then
        log_success "Helm installed successfully"
        return 0
    else
        log_error "Failed to install Helm"
        return 1
    fi
}

# Add common Helm repositories
add_helm_repos() {
    log_info "Adding Helm repositories..."
    
    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
    helm repo add grafana https://grafana.github.io/helm-charts
    helm repo add dapr https://dapr.github.io/helm-charts/
    helm repo add jetstack https://charts.jetstack.io
    helm repo add nvidia https://nvidia.github.io/k8s-device-plugin
    helm repo add cilium https://helm.cilium.io/
    helm repo add submariner-latest https://submariner-io.github.io/submariner-charts/charts
    
    helm repo update
    
    log_success "Helm repositories added and updated"
}

# Generate cluster-specific configuration
generate_cluster_config() {
    local cluster_name=$1
    local cluster_type=$2
    local config_path=$3
    
    log_info "Generating configuration for cluster '$cluster_name' of type '$cluster_type'..."
    
    # This will be expanded in the specific cluster setup scripts
    case "$cluster_type" in
        "app")
            # Application cluster specific config
            ;;
        "inference")
            # Inference cluster specific config
            ;;
        *)
            log_warning "Unknown cluster type: $cluster_type"
            ;;
    esac
    
    log_success "Configuration generated at $config_path"
}

# Export functions for use in other scripts
export -f log_info log_success log_warning log_error
export -f command_exists verify_prerequisites
export -f wait_for_cluster_ready install_k3d
export -f get_cluster_kubeconfig create_namespace_if_not_exists
export -f apply_system_optimizations install_helm add_helm_repos
export -f generate_cluster_config