#!/bin/bash
# setup-multi-cluster.sh - Wrapper script to setup complete multi-cluster environment

set -euo pipefail

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/utils/common.sh"

# Default values
APP_CLUSTER_NAME="${APP_CLUSTER_NAME:-bud-app}"
INFERENCE_CLUSTER_NAME="${INFERENCE_CLUSTER_NAME:-bud-inference}"
SETUP_NETWORKING="${SETUP_NETWORKING:-true}"
ENABLE_GPU="${ENABLE_GPU:-true}"
PARALLEL_SETUP="${PARALLEL_SETUP:-false}"

# Track setup progress
SETUP_LOG_FILE="/tmp/multi-cluster-setup-$(date +%Y%m%d-%H%M%S).log"

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
        --setup-networking)
            SETUP_NETWORKING="$2"
            shift 2
            ;;
        --enable-gpu)
            ENABLE_GPU="$2"
            shift 2
            ;;
        --parallel)
            PARALLEL_SETUP="true"
            shift
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  --app-cluster-name NAME         Name of application cluster (default: $APP_CLUSTER_NAME)"
            echo "  --inference-cluster-name NAME   Name of inference cluster (default: $INFERENCE_CLUSTER_NAME)"
            echo "  --setup-networking true|false   Setup cross-cluster networking (default: $SETUP_NETWORKING)"
            echo "  --enable-gpu true|false         Enable GPU support (default: $ENABLE_GPU)"
            echo "  --parallel                      Setup clusters in parallel (default: false)"
            echo "  --help                          Show this help message"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Function to setup clusters sequentially
setup_clusters_sequential() {
    log_info "Setting up clusters sequentially..."
    
    # Setup application cluster
    log_info "=== Setting up Application Cluster ==="
    if "$SCRIPT_DIR/setup-app-cluster.sh" --cluster-name "$APP_CLUSTER_NAME"; then
        log_success "Application cluster setup completed"
    else
        log_error "Application cluster setup failed"
        return 1
    fi
    
    echo
    
    # Setup inference cluster
    log_info "=== Setting up Inference Cluster ==="
    if "$SCRIPT_DIR/setup-inference-cluster.sh" \
        --cluster-name "$INFERENCE_CLUSTER_NAME" \
        --enable-gpu "$ENABLE_GPU"; then
        log_success "Inference cluster setup completed"
    else
        log_error "Inference cluster setup failed"
        return 1
    fi
}

# Function to setup clusters in parallel
setup_clusters_parallel() {
    log_info "Setting up clusters in parallel..."
    
    local app_pid=""
    local inference_pid=""
    local app_log="/tmp/app-cluster-setup.log"
    local inference_log="/tmp/inference-cluster-setup.log"
    
    # Start application cluster setup in background
    {
        "$SCRIPT_DIR/setup-app-cluster.sh" --cluster-name "$APP_CLUSTER_NAME" > "$app_log" 2>&1
    } &
    app_pid=$!
    log_info "Started application cluster setup (PID: $app_pid)"
    
    # Start inference cluster setup in background
    {
        "$SCRIPT_DIR/setup-inference-cluster.sh" \
            --cluster-name "$INFERENCE_CLUSTER_NAME" \
            --enable-gpu "$ENABLE_GPU" > "$inference_log" 2>&1
    } &
    inference_pid=$!
    log_info "Started inference cluster setup (PID: $inference_pid)"
    
    # Wait for both setups to complete
    local failed=false
    
    if wait $app_pid; then
        log_success "Application cluster setup completed"
    else
        log_error "Application cluster setup failed. Check logs at: $app_log"
        failed=true
    fi
    
    if wait $inference_pid; then
        log_success "Inference cluster setup completed"
    else
        log_error "Inference cluster setup failed. Check logs at: $inference_log"
        failed=true
    fi
    
    if [ "$failed" = true ]; then
        return 1
    fi
}

# Function to setup cross-cluster networking
setup_cross_cluster_networking() {
    log_info "=== Setting up Cross-Cluster Networking ==="
    
    if [ -f "$SCRIPT_DIR/networking/setup-cluster-mesh.sh" ]; then
        if "$SCRIPT_DIR/networking/setup-cluster-mesh.sh" \
            --cluster1 "$APP_CLUSTER_NAME" \
            --cluster2 "$INFERENCE_CLUSTER_NAME"; then
            log_success "Cross-cluster networking setup completed"
        else
            log_error "Cross-cluster networking setup failed"
            return 1
        fi
    else
        log_warning "Cross-cluster networking script not found. Skipping..."
    fi
}

# Function to verify multi-cluster setup
verify_multi_cluster_setup() {
    log_info "=== Verifying Multi-Cluster Setup ==="
    
    local all_good=true
    
    # Check application cluster
    log_info "Checking application cluster..."
    if kubectl --context="k3d-$APP_CLUSTER_NAME" get nodes >/dev/null 2>&1; then
        local app_nodes=$(kubectl --context="k3d-$APP_CLUSTER_NAME" get nodes --no-headers | wc -l)
        log_success "Application cluster is accessible with $app_nodes nodes"
    else
        log_error "Cannot access application cluster"
        all_good=false
    fi
    
    # Check inference cluster
    log_info "Checking inference cluster..."
    if kubectl --context="k3d-$INFERENCE_CLUSTER_NAME" get nodes >/dev/null 2>&1; then
        local inf_nodes=$(kubectl --context="k3d-$INFERENCE_CLUSTER_NAME" get nodes --no-headers | wc -l)
        log_success "Inference cluster is accessible with $inf_nodes nodes"
        
        if [[ "$ENABLE_GPU" == "true" ]]; then
            local gpu_nodes=$(kubectl --context="k3d-$INFERENCE_CLUSTER_NAME" get nodes -l nvidia.com/gpu.present=true --no-headers | wc -l)
            log_info "GPU-enabled nodes: $gpu_nodes"
        fi
    else
        log_error "Cannot access inference cluster"
        all_good=false
    fi
    
    # Check key services
    log_info "Checking key services..."
    
    # App cluster services
    local app_services=("cert-manager" "dapr-system" "monitoring")
    for ns in "${app_services[@]}"; do
        if kubectl --context="k3d-$APP_CLUSTER_NAME" get namespace "$ns" >/dev/null 2>&1; then
            log_success "Namespace '$ns' exists in application cluster"
        else
            log_warning "Namespace '$ns' missing in application cluster"
        fi
    done
    
    # Inference cluster services
    local inf_services=("cert-manager" "monitoring" "aibrix-system" "vllm-system")
    if [[ "$ENABLE_GPU" == "true" ]]; then
        inf_services+=("gpu-operator")
    fi
    
    for ns in "${inf_services[@]}"; do
        if kubectl --context="k3d-$INFERENCE_CLUSTER_NAME" get namespace "$ns" >/dev/null 2>&1; then
            log_success "Namespace '$ns' exists in inference cluster"
        else
            log_warning "Namespace '$ns' missing in inference cluster"
        fi
    done
    
    if [ "$all_good" = true ]; then
        return 0
    else
        return 1
    fi
}

# Function to display setup summary
display_setup_summary() {
    log_info "=== Multi-Cluster Setup Summary ==="
    
    echo
    echo "Application Cluster:"
    echo "  Name: $APP_CLUSTER_NAME"
    echo "  Context: k3d-$APP_CLUSTER_NAME"
    echo "  API: https://localhost:6443"
    echo "  Load Balancer: http://localhost:8080"
    echo "  Grafana: http://localhost:8080 (admin/admin)"
    
    echo
    echo "Inference Cluster:"
    echo "  Name: $INFERENCE_CLUSTER_NAME"
    echo "  Context: k3d-$INFERENCE_CLUSTER_NAME"
    echo "  API: https://localhost:6444"
    echo "  Load Balancer: http://localhost:8081"
    echo "  Grafana: http://localhost:8081 (admin/admin)"
    echo "  GPU Support: $ENABLE_GPU"
    
    if [[ "$SETUP_NETWORKING" == "true" ]]; then
        echo
        echo "Cross-Cluster Networking: Enabled"
    fi
    
    echo
    echo "Configuration files saved to:"
    echo "  - $SCRIPT_DIR/../../configs/app-cluster/cluster-info.yaml"
    echo "  - $SCRIPT_DIR/../../configs/inference-cluster/cluster-info.yaml"
    
    echo
    echo "To switch between clusters:"
    echo "  kubectl config use-context k3d-$APP_CLUSTER_NAME"
    echo "  kubectl config use-context k3d-$INFERENCE_CLUSTER_NAME"
    
    echo
    echo "To view all contexts:"
    echo "  kubectl config get-contexts"
    
    echo
    echo "Setup log saved to: $SETUP_LOG_FILE"
}

# Main setup function
main() {
    log_info "Starting multi-cluster setup..." | tee "$SETUP_LOG_FILE"
    log_info "Setup log: $SETUP_LOG_FILE"
    
    # Start timer
    local start_time=$(date +%s)
    
    # Verify prerequisites
    verify_prerequisites || exit 1
    
    # Setup clusters
    if [[ "$PARALLEL_SETUP" == "true" ]]; then
        setup_clusters_parallel | tee -a "$SETUP_LOG_FILE"
    else
        setup_clusters_sequential | tee -a "$SETUP_LOG_FILE"
    fi
    
    if [ $? -ne 0 ]; then
        log_error "Cluster setup failed. Check the log file: $SETUP_LOG_FILE"
        exit 1
    fi
    
    # Setup cross-cluster networking if enabled
    if [[ "$SETUP_NETWORKING" == "true" ]]; then
        echo
        setup_cross_cluster_networking | tee -a "$SETUP_LOG_FILE"
    fi
    
    # Verify setup
    echo
    verify_multi_cluster_setup | tee -a "$SETUP_LOG_FILE"
    
    # Calculate elapsed time
    local end_time=$(date +%s)
    local elapsed=$((end_time - start_time))
    local minutes=$((elapsed / 60))
    local seconds=$((elapsed % 60))
    
    echo
    log_success "Multi-cluster setup completed in ${minutes}m ${seconds}s" | tee -a "$SETUP_LOG_FILE"
    
    # Display summary
    echo
    display_setup_summary | tee -a "$SETUP_LOG_FILE"
}

# Run main function
main "$@"