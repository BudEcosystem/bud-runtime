#!/bin/bash
# deploy-inference-cluster.sh - Deploy inference services to the inference cluster

set -euo pipefail

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/../multi-cluster/utils/common.sh"

# Default values
CLUSTER_NAME="${INFERENCE_CLUSTER_NAME:-bud-inference}"
NAMESPACE="${NAMESPACE:-inference-system}"
RELEASE_NAME="${RELEASE_NAME:-inference-stack}"
VALUES_FILE="${VALUES_FILE:-$ROOT_DIR/helm/inference-stack/values.yaml}"
WAIT="${WAIT:-true}"
TIMEOUT="${TIMEOUT:-15m}"
DRY_RUN="${DRY_RUN:-false}"
SKIP_GPU_CHECK="${SKIP_GPU_CHECK:-false}"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --cluster-name)
            CLUSTER_NAME="$2"
            shift 2
            ;;
        --namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        --release-name)
            RELEASE_NAME="$2"
            shift 2
            ;;
        --values-file)
            VALUES_FILE="$2"
            shift 2
            ;;
        --no-wait)
            WAIT="false"
            shift
            ;;
        --timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN="true"
            shift
            ;;
        --skip-gpu-check)
            SKIP_GPU_CHECK="true"
            shift
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  --cluster-name NAME     Target cluster name (default: $CLUSTER_NAME)"
            echo "  --namespace NAME        Kubernetes namespace (default: $NAMESPACE)"
            echo "  --release-name NAME     Helm release name (default: $RELEASE_NAME)"
            echo "  --values-file FILE      Values file path (default: helm/inference-stack/values.yaml)"
            echo "  --no-wait              Don't wait for deployment to complete"
            echo "  --timeout DURATION     Deployment timeout (default: $TIMEOUT)"
            echo "  --dry-run              Show what would be deployed without deploying"
            echo "  --skip-gpu-check       Skip GPU availability check"
            echo "  --help                 Show this help message"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Function to check cluster connectivity
check_cluster() {
    log_info "Checking cluster connectivity..."
    
    if ! kubectl --context="k3d-$CLUSTER_NAME" cluster-info >/dev/null 2>&1; then
        log_error "Cannot connect to cluster '$CLUSTER_NAME'"
        log_info "Make sure the cluster is running: ./scripts/multi-cluster/setup-inference-cluster.sh"
        exit 1
    fi
    
    log_success "Connected to cluster '$CLUSTER_NAME'"
}

# Function to check GPU availability
check_gpu_availability() {
    if [[ "$SKIP_GPU_CHECK" == "true" ]]; then
        log_warning "Skipping GPU availability check"
        return 0
    fi
    
    log_info "Checking GPU availability in the cluster..."
    
    local gpu_nodes=$(kubectl --context="k3d-$CLUSTER_NAME" get nodes -l nvidia.com/gpu.present=true --no-headers 2>/dev/null | wc -l)
    
    if [ "$gpu_nodes" -eq 0 ]; then
        log_warning "No GPU nodes found in the cluster"
        log_warning "VLLM performance will be significantly reduced without GPUs"
        
        read -p "Continue without GPUs? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Deployment cancelled"
            exit 1
        fi
    else
        log_success "Found $gpu_nodes GPU-enabled nodes"
        
        # Check GPU operator
        if kubectl --context="k3d-$CLUSTER_NAME" get namespace gpu-operator >/dev/null 2>&1; then
            log_success "GPU operator is installed"
        else
            log_warning "GPU operator namespace not found"
            log_info "GPU support may not be fully configured"
        fi
    fi
}

# Function to prepare deployment
prepare_deployment() {
    log_info "Preparing deployment..."
    
    # Create namespace if it doesn't exist
    create_namespace_if_not_exists "$NAMESPACE" "k3d-$CLUSTER_NAME"
    
    # Update Helm dependencies
    log_info "Updating Helm dependencies..."
    cd "$ROOT_DIR/helm/inference-stack"
    helm dependency update
    
    # Validate values file
    if [ ! -f "$VALUES_FILE" ]; then
        log_error "Values file not found: $VALUES_FILE"
        exit 1
    fi
    
    # Check MinIO connectivity if referenced in values
    if grep -q "minio-service" "$VALUES_FILE"; then
        log_info "Checking MinIO connectivity..."
        if kubectl --context="k3d-$CLUSTER_NAME" get service minio-service -n bud-system >/dev/null 2>&1; then
            log_success "MinIO service found"
        else
            log_warning "MinIO service not found in bud-system namespace"
            log_warning "Model storage may not work correctly"
        fi
    fi
    
    log_success "Deployment prepared"
}

# Function to deploy services
deploy_services() {
    log_info "Deploying inference services..."
    
    cd "$ROOT_DIR/helm/inference-stack"
    
    # Build helm command
    local helm_cmd=(
        helm upgrade --install "$RELEASE_NAME" .
        --namespace "$NAMESPACE"
        --values "$VALUES_FILE"
        --kubeconfig "$HOME/.kube/config"
        --kube-context "k3d-$CLUSTER_NAME"
        --create-namespace
    )
    
    # Add additional values for cross-cluster communication
    helm_cmd+=(
        --set "minio.endpoint=minio-service.bud-system.svc.cluster.local:9000"
    )
    
    if [[ "$WAIT" == "true" ]]; then
        helm_cmd+=(--wait --timeout "$TIMEOUT")
    fi
    
    if [[ "$DRY_RUN" == "true" ]]; then
        helm_cmd+=(--dry-run --debug)
        log_info "Running in dry-run mode..."
    fi
    
    # Execute deployment
    log_info "Executing: ${helm_cmd[*]}"
    if "${helm_cmd[@]}"; then
        log_success "Deployment completed successfully"
    else
        log_error "Deployment failed"
        exit 1
    fi
}

# Function to verify deployment
verify_deployment() {
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "Skipping verification in dry-run mode"
        return 0
    fi
    
    log_info "Verifying deployment..."
    
    # Check Helm release status
    log_info "Checking Helm release status..."
    helm status "$RELEASE_NAME" \
        --namespace "$NAMESPACE" \
        --kubeconfig "$HOME/.kube/config" \
        --kube-context "k3d-$CLUSTER_NAME"
    
    # Check pod status
    log_info "Checking pod status..."
    kubectl --context="k3d-$CLUSTER_NAME" get pods -n "$NAMESPACE"
    
    # Check for GPU allocations
    log_info "Checking GPU allocations..."
    kubectl --context="k3d-$CLUSTER_NAME" get pods -n "$NAMESPACE" \
        -o custom-columns="NAME:.metadata.name,GPU:.spec.containers[*].resources.limits.nvidia\.com/gpu" \
        | grep -v "<none>" || log_info "No GPU allocations found"
    
    # Wait for AIBrix to be ready
    if [[ "$WAIT" == "true" ]]; then
        log_info "Waiting for AIBrix to be ready..."
        kubectl --context="k3d-$CLUSTER_NAME" wait --for=condition=ready pod \
            -l app.kubernetes.io/component=aibrix -n "$NAMESPACE" \
            --timeout=5m || log_warning "AIBrix may still be starting"
    fi
    
    # Check services
    log_info "Services deployed:"
    kubectl --context="k3d-$CLUSTER_NAME" get services -n "$NAMESPACE"
    
    # Check PVCs
    log_info "Persistent Volume Claims:"
    kubectl --context="k3d-$CLUSTER_NAME" get pvc -n "$NAMESPACE"
}

# Function to display access information
display_access_info() {
    if [[ "$DRY_RUN" == "true" ]]; then
        return 0
    fi
    
    echo
    log_info "=== Deployment Access Information ==="
    echo
    echo "Cluster: $CLUSTER_NAME"
    echo "Namespace: $NAMESPACE"
    echo "Release: $RELEASE_NAME"
    echo
    echo "To access services locally, use port-forward:"
    echo "  # AIBrix Control Plane"
    echo "  kubectl --context=k3d-$CLUSTER_NAME port-forward -n $NAMESPACE svc/${RELEASE_NAME}-aibrix 8080:8080"
    echo
    echo "  # VLLM Instances (if deployed)"
    kubectl --context="k3d-$CLUSTER_NAME" get svc -n "$NAMESPACE" -l app.kubernetes.io/component=vllm -o name | while read svc; do
        svc_name=$(echo "$svc" | cut -d'/' -f2)
        echo "  kubectl --context=k3d-$CLUSTER_NAME port-forward -n $NAMESPACE svc/$svc_name 8000:8000"
    done
    echo
    echo "  # Grafana Dashboard"
    echo "  kubectl --context=k3d-$CLUSTER_NAME port-forward -n $NAMESPACE svc/grafana 3000:80"
    echo
    echo "  # Prometheus"
    echo "  kubectl --context=k3d-$CLUSTER_NAME port-forward -n $NAMESPACE svc/prometheus-prometheus 9090:9090"
    echo
    echo "To view logs:"
    echo "  # AIBrix logs"
    echo "  kubectl --context=k3d-$CLUSTER_NAME logs -n $NAMESPACE -l app.kubernetes.io/component=aibrix -f"
    echo
    echo "  # VLLM logs"
    echo "  kubectl --context=k3d-$CLUSTER_NAME logs -n $NAMESPACE -l app.kubernetes.io/component=vllm -f"
    echo
    echo "To test inference (after port-forward):"
    echo '  curl http://localhost:8000/v1/completions \'
    echo '    -H "Content-Type: application/json" \'
    echo '    -d "{"model": "meta-llama/Llama-2-7b-chat-hf", "prompt": "Hello!", "max_tokens": 50}"'
}

# Function to create post-deployment config
create_post_deployment_config() {
    if [[ "$DRY_RUN" == "true" ]]; then
        return 0
    fi
    
    local config_file="$ROOT_DIR/configs/inference-cluster/deployment-info.yaml"
    mkdir -p "$(dirname "$config_file")"
    
    # Get deployed services
    local aibrix_svc="${RELEASE_NAME}-aibrix"
    local vllm_services=$(kubectl --context="k3d-$CLUSTER_NAME" get svc -n "$NAMESPACE" -l app.kubernetes.io/component=vllm -o jsonpath='{.items[*].metadata.name}')
    
    cat > "$config_file" <<EOF
# Inference Cluster Deployment Information
# Generated: $(date)

deployment:
  cluster: $CLUSTER_NAME
  namespace: $NAMESPACE
  release: $RELEASE_NAME
  values_file: $VALUES_FILE
  
services:
  aibrix:
    name: $aibrix_svc
    port: 8080
    endpoint: http://localhost:8080  # After port-forward
  
  vllm_instances:
EOF
    
    # Add VLLM instances
    for svc in $vllm_services; do
        cat >> "$config_file" <<EOF
    - name: $svc
      port: 8000
      endpoint: http://localhost:8000  # After port-forward
EOF
    done
    
    cat >> "$config_file" <<EOF
  
  monitoring:
    grafana:
      name: grafana
      port: 80
      endpoint: http://localhost:3000  # After port-forward
      credentials: admin/admin
    prometheus:
      name: prometheus-prometheus
      port: 9090
      endpoint: http://localhost:9090  # After port-forward

commands:
  port_forward:
    aibrix: kubectl --context=k3d-$CLUSTER_NAME port-forward -n $NAMESPACE svc/$aibrix_svc 8080:8080
    grafana: kubectl --context=k3d-$CLUSTER_NAME port-forward -n $NAMESPACE svc/grafana 3000:80
    prometheus: kubectl --context=k3d-$CLUSTER_NAME port-forward -n $NAMESPACE svc/prometheus-prometheus 9090:9090
  
  logs:
    aibrix: kubectl --context=k3d-$CLUSTER_NAME logs -n $NAMESPACE -l app.kubernetes.io/component=aibrix -f
    vllm: kubectl --context=k3d-$CLUSTER_NAME logs -n $NAMESPACE -l app.kubernetes.io/component=vllm -f
  
  status:
    helm: helm status $RELEASE_NAME -n $NAMESPACE --kube-context k3d-$CLUSTER_NAME
    pods: kubectl --context=k3d-$CLUSTER_NAME get pods -n $NAMESPACE
    services: kubectl --context=k3d-$CLUSTER_NAME get services -n $NAMESPACE
    gpu: kubectl --context=k3d-$CLUSTER_NAME describe nodes | grep -E "nvidia.com/gpu|Allocated resources" -A 5
EOF
    
    log_success "Deployment configuration saved to: $config_file"
}

# Main deployment flow
main() {
    log_info "Starting inference cluster deployment..."
    
    # Check prerequisites
    verify_prerequisites || exit 1
    
    # Check cluster connectivity
    check_cluster
    
    # Check GPU availability
    check_gpu_availability
    
    # Prepare deployment
    prepare_deployment
    
    # Deploy services
    deploy_services
    
    # Verify deployment
    verify_deployment
    
    # Create post-deployment config
    create_post_deployment_config
    
    # Display access information
    display_access_info
    
    log_success "Inference cluster deployment completed!"
}

# Run main function
main