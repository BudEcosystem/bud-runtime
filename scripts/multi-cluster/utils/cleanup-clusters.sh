#!/bin/bash
# cleanup-clusters.sh - Cleanup K3d clusters and associated resources

set -euo pipefail

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# Default values
APP_CLUSTER_NAME="${APP_CLUSTER_NAME:-bud-app}"
INFERENCE_CLUSTER_NAME="${INFERENCE_CLUSTER_NAME:-bud-inference}"
CLEANUP_ALL="${CLEANUP_ALL:-false}"
CLEANUP_REGISTRY="${CLEANUP_REGISTRY:-false}"
FORCE="${FORCE:-false}"

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
        --all)
            CLEANUP_ALL="true"
            shift
            ;;
        --cleanup-registry)
            CLEANUP_REGISTRY="true"
            shift
            ;;
        --force)
            FORCE="true"
            shift
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  --app-cluster-name NAME         Name of application cluster (default: $APP_CLUSTER_NAME)"
            echo "  --inference-cluster-name NAME   Name of inference cluster (default: $INFERENCE_CLUSTER_NAME)"
            echo "  --all                          Cleanup all K3d clusters"
            echo "  --cleanup-registry             Also cleanup the local registry"
            echo "  --force                        Force cleanup without confirmation"
            echo "  --help                         Show this help message"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Function to confirm action
confirm_action() {
    if [[ "$FORCE" == "true" ]]; then
        return 0
    fi
    
    local message=$1
    echo -n "$message (y/N): "
    read -r response
    case "$response" in
        [yY][eE][sS]|[yY])
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

# Function to cleanup a specific cluster
cleanup_cluster() {
    local cluster_name=$1
    
    if k3d cluster list | grep -q "^$cluster_name"; then
        log_info "Cleaning up cluster: $cluster_name"
        
        # Delete the cluster
        if k3d cluster delete "$cluster_name"; then
            log_success "Cluster '$cluster_name' deleted successfully"
        else
            log_error "Failed to delete cluster '$cluster_name'"
            return 1
        fi
    else
        log_info "Cluster '$cluster_name' not found, skipping..."
    fi
}

# Function to cleanup local registry
cleanup_registry() {
    local registry_name="${REGISTRY_NAME:-bud-registry}"
    
    if k3d registry list | grep -q "^$registry_name"; then
        log_info "Cleaning up local registry: $registry_name"
        
        if k3d registry delete "$registry_name"; then
            log_success "Registry '$registry_name' deleted successfully"
        else
            log_error "Failed to delete registry '$registry_name'"
            return 1
        fi
    else
        log_info "Registry '$registry_name' not found, skipping..."
    fi
}

# Function to cleanup all K3d clusters
cleanup_all_clusters() {
    log_info "Cleaning up all K3d clusters..."
    
    local clusters=$(k3d cluster list -o json | jq -r '.[].name' 2>/dev/null || true)
    
    if [ -z "$clusters" ]; then
        log_info "No K3d clusters found"
        return 0
    fi
    
    for cluster in $clusters; do
        cleanup_cluster "$cluster"
    done
}

# Function to cleanup temporary files
cleanup_temp_files() {
    log_info "Cleaning up temporary files..."
    
    # Remove temporary log files
    rm -f /tmp/app-cluster-setup.log
    rm -f /tmp/inference-cluster-setup.log
    rm -f /tmp/multi-cluster-setup-*.log
    rm -f /tmp/prometheus-gpu-values.yaml
    rm -f /tmp/gpu-operator-values.yaml
    
    # Remove Submariner files if present
    rm -f broker-info.subm
    
    log_success "Temporary files cleaned up"
}

# Function to cleanup kubeconfig contexts
cleanup_kubeconfig() {
    log_info "Cleaning up kubeconfig contexts..."
    
    local contexts_to_remove=()
    
    if [[ "$CLEANUP_ALL" == "true" ]]; then
        # Get all k3d contexts
        contexts_to_remove=($(kubectl config get-contexts -o name | grep "^k3d-" || true))
    else
        # Only remove specific contexts
        contexts_to_remove=("k3d-$APP_CLUSTER_NAME" "k3d-$INFERENCE_CLUSTER_NAME")
    fi
    
    for context in "${contexts_to_remove[@]}"; do
        if kubectl config get-contexts -o name | grep -q "^$context$"; then
            log_info "Removing context: $context"
            kubectl config delete-context "$context" 2>/dev/null || true
            
            # Also remove the associated cluster and user entries
            kubectl config delete-cluster "$context" 2>/dev/null || true
            kubectl config delete-user "$context" 2>/dev/null || true
        fi
    done
    
    log_success "Kubeconfig cleaned up"
}

# Function to show cleanup summary
show_cleanup_summary() {
    log_info "=== Cleanup Summary ==="
    
    echo
    echo "Remaining K3d clusters:"
    k3d cluster list || echo "  None"
    
    echo
    echo "Remaining K3d registries:"
    k3d registry list || echo "  None"
    
    echo
    echo "Remaining kubeconfig contexts:"
    kubectl config get-contexts -o name | grep "^k3d-" || echo "  None"
}

# Main cleanup function
main() {
    log_info "Starting cluster cleanup process..."
    
    # Determine what to cleanup
    local clusters_to_cleanup=()
    
    if [[ "$CLEANUP_ALL" == "true" ]]; then
        if ! confirm_action "This will delete ALL K3d clusters. Are you sure?"; then
            log_info "Cleanup cancelled"
            exit 0
        fi
        cleanup_all_clusters
    else
        clusters_to_cleanup=("$APP_CLUSTER_NAME" "$INFERENCE_CLUSTER_NAME")
        
        log_info "Clusters to be cleaned up:"
        for cluster in "${clusters_to_cleanup[@]}"; do
            echo "  - $cluster"
        done
        
        if ! confirm_action "Proceed with cleanup?"; then
            log_info "Cleanup cancelled"
            exit 0
        fi
        
        for cluster in "${clusters_to_cleanup[@]}"; do
            cleanup_cluster "$cluster"
        done
    fi
    
    # Cleanup registry if requested
    if [[ "$CLEANUP_REGISTRY" == "true" ]]; then
        if confirm_action "Also cleanup the local registry?"; then
            cleanup_registry
        fi
    fi
    
    # Cleanup kubeconfig
    cleanup_kubeconfig
    
    # Cleanup temporary files
    cleanup_temp_files
    
    # Show summary
    echo
    show_cleanup_summary
    
    log_success "Cleanup completed successfully!"
}

# Run main function
main