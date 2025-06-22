#!/bin/bash
# cluster-status.sh - Check status of multi-cluster setup

set -euo pipefail

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# Default values
APP_CLUSTER_NAME="${APP_CLUSTER_NAME:-bud-app}"
INFERENCE_CLUSTER_NAME="${INFERENCE_CLUSTER_NAME:-bud-inference}"
SHOW_PODS="${SHOW_PODS:-false}"
SHOW_SERVICES="${SHOW_SERVICES:-false}"
CHECK_NETWORKING="${CHECK_NETWORKING:-true}"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --app-cluster-name)
            APP_CLUSTER_NAME="$2"
            shift 2
            ;;
        --inference-cluster-name)
            INFERENCE_CLUSTER_NAME="$2"
            shift 2
            ;;
        --show-pods)
            SHOW_PODS="true"
            shift
            ;;
        --show-services)
            SHOW_SERVICES="true"
            shift
            ;;
        --no-networking-check)
            CHECK_NETWORKING="false"
            shift
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  --app-cluster-name NAME         Name of application cluster (default: $APP_CLUSTER_NAME)"
            echo "  --inference-cluster-name NAME   Name of inference cluster (default: $INFERENCE_CLUSTER_NAME)"
            echo "  --show-pods                    Show pod status in all namespaces"
            echo "  --show-services                Show service endpoints"
            echo "  --no-networking-check          Skip cross-cluster networking check"
            echo "  --help                         Show this help message"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Function to check cluster status
check_cluster_status() {
    local cluster_name=$1
    local context="k3d-$cluster_name"
    
    echo
    log_info "=== Cluster: $cluster_name ==="
    
    # Check if cluster exists
    if ! k3d cluster list | grep -q "^$cluster_name"; then
        log_error "Cluster '$cluster_name' not found"
        return 1
    fi
    
    # Check if context exists
    if ! kubectl config get-contexts -o name | grep -q "^$context$"; then
        log_error "Context '$context' not found in kubeconfig"
        return 1
    fi
    
    # Get cluster info
    local cluster_info=$(k3d cluster list | grep "^$cluster_name")
    echo "K3d Status: $cluster_info"
    
    # Check node status
    echo
    echo "Nodes:"
    if ! kubectl --context="$context" get nodes; then
        log_error "Failed to get node information"
        return 1
    fi
    
    # Check key namespaces
    echo
    echo "Key Namespaces:"
    local namespaces=(
        "kube-system"
        "cert-manager"
        "monitoring"
    )
    
    if [[ "$cluster_name" == "$APP_CLUSTER_NAME" ]]; then
        namespaces+=("dapr-system" "bud-system")
    elif [[ "$cluster_name" == "$INFERENCE_CLUSTER_NAME" ]]; then
        namespaces+=("gpu-operator" "aibrix-system" "vllm-system")
    fi
    
    for ns in "${namespaces[@]}"; do
        if kubectl --context="$context" get namespace "$ns" >/dev/null 2>&1; then
            local pod_count=$(kubectl --context="$context" get pods -n "$ns" --no-headers 2>/dev/null | wc -l)
            local running_count=$(kubectl --context="$context" get pods -n "$ns" --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l)
            echo "  $ns: $running_count/$pod_count pods running"
        else
            echo "  $ns: Not found"
        fi
    done
    
    # Show GPU resources if inference cluster
    if [[ "$cluster_name" == "$INFERENCE_CLUSTER_NAME" ]]; then
        echo
        echo "GPU Resources:"
        local gpu_nodes=$(kubectl --context="$context" get nodes -l nvidia.com/gpu.present=true --no-headers 2>/dev/null | wc -l)
        echo "  GPU-enabled nodes: $gpu_nodes"
        
        # Check GPU operator status
        if kubectl --context="$context" get namespace gpu-operator >/dev/null 2>&1; then
            local gpu_pods=$(kubectl --context="$context" get pods -n gpu-operator --no-headers 2>/dev/null | wc -l)
            local gpu_running=$(kubectl --context="$context" get pods -n gpu-operator --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l)
            echo "  GPU Operator: $gpu_running/$gpu_pods pods running"
        fi
    fi
    
    # Show pods if requested
    if [[ "$SHOW_PODS" == "true" ]]; then
        echo
        echo "All Pods:"
        kubectl --context="$context" get pods --all-namespaces
    fi
    
    # Show services if requested
    if [[ "$SHOW_SERVICES" == "true" ]]; then
        echo
        echo "Services:"
        kubectl --context="$context" get services --all-namespaces | grep -v "^kube-system"
    fi
    
    # Check storage
    echo
    echo "Storage:"
    local pvc_count=$(kubectl --context="$context" get pvc --all-namespaces --no-headers 2>/dev/null | wc -l)
    local bound_pvc=$(kubectl --context="$context" get pvc --all-namespaces --field-selector=status.phase=Bound --no-headers 2>/dev/null | wc -l)
    echo "  PVCs: $bound_pvc/$pvc_count bound"
    
    return 0
}

# Function to check cross-cluster networking
check_cross_cluster_networking() {
    log_info "=== Cross-Cluster Networking ==="
    
    # Check if Submariner is installed
    if kubectl --context="k3d-$APP_CLUSTER_NAME" get namespace submariner-operator >/dev/null 2>&1 || \
       kubectl --context="k3d-$INFERENCE_CLUSTER_NAME" get namespace submariner-operator >/dev/null 2>&1; then
        echo "Networking Solution: Submariner"
        
        # Check Submariner status
        if command_exists subctl; then
            echo
            echo "Submariner Status:"
            subctl show all --kubeconfig "$HOME/.kube/config" || log_warning "Failed to get Submariner status"
        else
            log_warning "subctl not found, cannot check Submariner status"
        fi
    else
        echo "Networking Solution: Basic/NodePort"
        
        # Check if cross-cluster endpoints exist
        if kubectl --context="k3d-$APP_CLUSTER_NAME" get configmap cluster-endpoints -n default >/dev/null 2>&1; then
            echo "Cross-cluster endpoints configured"
        else
            echo "Cross-cluster endpoints not configured"
        fi
    fi
}

# Function to check resource usage
check_resource_usage() {
    local cluster_name=$1
    local context="k3d-$cluster_name"
    
    echo
    log_info "Resource Usage for $cluster_name:"
    
    # Get node resource usage
    if kubectl --context="$context" top nodes >/dev/null 2>&1; then
        kubectl --context="$context" top nodes
    else
        log_warning "Metrics server not available, cannot show resource usage"
    fi
}

# Function to generate status report
generate_status_report() {
    local report_file="/tmp/multi-cluster-status-$(date +%Y%m%d-%H%M%S).txt"
    
    {
        echo "Multi-Cluster Status Report"
        echo "Generated: $(date)"
        echo "=========================="
        echo
        
        # Cluster information
        echo "Clusters:"
        k3d cluster list
        echo
        
        # Contexts
        echo "Kubernetes Contexts:"
        kubectl config get-contexts | grep "k3d-"
        echo
        
        # Detailed status for each cluster
        for cluster in "$APP_CLUSTER_NAME" "$INFERENCE_CLUSTER_NAME"; do
            if k3d cluster list | grep -q "^$cluster"; then
                echo "=== Cluster: $cluster ==="
                kubectl --context="k3d-$cluster" get nodes
                echo
                kubectl --context="k3d-$cluster" get pods --all-namespaces | grep -v "^kube-system"
                echo
            fi
        done
        
    } > "$report_file"
    
    log_success "Status report saved to: $report_file"
}

# Main function
main() {
    log_info "Checking multi-cluster status..."
    
    # Check K3d installation
    if ! command_exists k3d; then
        log_error "K3d is not installed"
        exit 1
    fi
    
    # Check kubectl installation
    if ! command_exists kubectl; then
        log_error "kubectl is not installed"
        exit 1
    fi
    
    # List all K3d clusters
    echo
    log_info "=== K3d Clusters ==="
    k3d cluster list
    
    # Check each cluster
    local app_status=0
    local inf_status=0
    
    if k3d cluster list | grep -q "^$APP_CLUSTER_NAME"; then
        check_cluster_status "$APP_CLUSTER_NAME" || app_status=1
        check_resource_usage "$APP_CLUSTER_NAME"
    else
        log_warning "Application cluster '$APP_CLUSTER_NAME' not found"
        app_status=1
    fi
    
    if k3d cluster list | grep -q "^$INFERENCE_CLUSTER_NAME"; then
        check_cluster_status "$INFERENCE_CLUSTER_NAME" || inf_status=1
        check_resource_usage "$INFERENCE_CLUSTER_NAME"
    else
        log_warning "Inference cluster '$INFERENCE_CLUSTER_NAME' not found"
        inf_status=1
    fi
    
    # Check cross-cluster networking if both clusters exist
    if [[ $app_status -eq 0 ]] && [[ $inf_status -eq 0 ]] && [[ "$CHECK_NETWORKING" == "true" ]]; then
        echo
        check_cross_cluster_networking
    fi
    
    # Generate status report
    echo
    generate_status_report
    
    # Summary
    echo
    log_info "=== Summary ==="
    if [[ $app_status -eq 0 ]]; then
        log_success "Application cluster: Healthy"
    else
        log_error "Application cluster: Issues detected"
    fi
    
    if [[ $inf_status -eq 0 ]]; then
        log_success "Inference cluster: Healthy"
    else
        log_error "Inference cluster: Issues detected"
    fi
    
    if [[ $app_status -eq 0 ]] && [[ $inf_status -eq 0 ]]; then
        log_success "Multi-cluster setup is operational"
        return 0
    else
        log_warning "Multi-cluster setup has issues"
        return 1
    fi
}

# Run main function
main