#!/bin/bash
# switch-vllm-mode.sh - Switch between mock and real vLLM deployments

set -euo pipefail

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../multi-cluster/utils/common.sh"

# Default values
CLUSTER_NAME="${INFERENCE_CLUSTER_NAME:-bud-inference}"
NAMESPACE="${VLLM_NAMESPACE:-vllm-system}"
MODE=""
MOCK_RELEASE="mock-vllm"
REAL_RELEASE="vllm"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --mode)
            MODE="$2"
            shift 2
            ;;
        --cluster-name)
            CLUSTER_NAME="$2"
            shift 2
            ;;
        --namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 --mode {mock|real} [options]"
            echo "Options:"
            echo "  --mode MODE                 Switch to 'mock' or 'real' vLLM"
            echo "  --cluster-name NAME         Target cluster name (default: $CLUSTER_NAME)"
            echo "  --namespace NS              Kubernetes namespace (default: $NAMESPACE)"
            echo "  --help                      Show this help message"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Validate mode
if [[ -z "$MODE" ]]; then
    log_error "Mode is required. Use --mode {mock|real}"
    exit 1
fi

if [[ "$MODE" != "mock" ]] && [[ "$MODE" != "real" ]]; then
    log_error "Invalid mode: $MODE. Must be 'mock' or 'real'"
    exit 1
fi

# Switch to cluster context
kubectl config use-context "k3d-$CLUSTER_NAME" >/dev/null
log_info "Using cluster: $CLUSTER_NAME"

# Function to scale deployment
scale_deployment() {
    local release=$1
    local replicas=$2
    
    if kubectl get deployment -n "$NAMESPACE" "$release" &>/dev/null; then
        log_info "Scaling $release to $replicas replicas..."
        kubectl scale deployment -n "$NAMESPACE" "$release" --replicas="$replicas"
        kubectl rollout status deployment -n "$NAMESPACE" "$release" --timeout=60s || true
    else
        log_warning "Deployment $release not found in namespace $NAMESPACE"
    fi
}

# Function to update service selector
update_service_selector() {
    local service_name="vllm"
    local selector_app=$1
    
    # Check if a common vllm service exists
    if kubectl get svc -n "$NAMESPACE" "$service_name" &>/dev/null; then
        log_info "Updating service $service_name to point to $selector_app..."
        kubectl patch svc -n "$NAMESPACE" "$service_name" -p \
            "{\"spec\":{\"selector\":{\"app.kubernetes.io/name\":\"$selector_app\"}}}"
    else
        log_info "Creating service $service_name pointing to $selector_app..."
        cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Service
metadata:
  name: $service_name
  namespace: $NAMESPACE
  labels:
    app: vllm-common
spec:
  type: ClusterIP
  ports:
  - port: 8000
    targetPort: 8000
    protocol: TCP
    name: http
  selector:
    app.kubernetes.io/name: $selector_app
EOF
    fi
}

# Main switching logic
switch_mode() {
    log_info "Switching to $MODE mode..."
    
    if [[ "$MODE" == "mock" ]]; then
        # Scale down real vLLM
        scale_deployment "$REAL_RELEASE" 0
        
        # Scale up mock vLLM
        scale_deployment "$MOCK_RELEASE" 1
        
        # Update service to point to mock
        update_service_selector "mock-vllm"
        
        log_success "Switched to mock vLLM mode"
        log_info "Mock vLLM is now active at http://vllm.$NAMESPACE.svc.cluster.local:8000"
        
    else  # real mode
        # Scale down mock vLLM
        scale_deployment "$MOCK_RELEASE" 0
        
        # Scale up real vLLM
        scale_deployment "$REAL_RELEASE" 1
        
        # Update service to point to real vLLM
        update_service_selector "vllm"
        
        log_success "Switched to real vLLM mode"
        log_info "Real vLLM is now active at http://vllm.$NAMESPACE.svc.cluster.local:8000"
        log_warning "Ensure GPU resources are available for real vLLM to function properly"
    fi
    
    # Show current status
    echo
    log_info "Current deployments in $NAMESPACE:"
    kubectl get deployments -n "$NAMESPACE" | grep -E "(mock-)?vllm" || true
    
    echo
    log_info "Current services in $NAMESPACE:"
    kubectl get svc -n "$NAMESPACE" | grep -E "(mock-)?vllm" || true
}

# Main execution
main() {
    log_info "vLLM Mode Switcher"
    log_info "=================="
    
    # Verify cluster exists
    if ! k3d cluster list | grep -q "^$CLUSTER_NAME"; then
        log_error "Cluster '$CLUSTER_NAME' not found"
        exit 1
    fi
    
    # Create namespace if it doesn't exist
    create_namespace_if_not_exists "$NAMESPACE" "k3d-$CLUSTER_NAME"
    
    # Perform the switch
    switch_mode
    
    # Test the endpoint
    echo
    log_info "Testing the vLLM endpoint..."
    kubectl run test-vllm-$RANDOM --rm -it --restart=Never \
        --image=curlimages/curl:latest \
        --command -- curl -s http://vllm.$NAMESPACE.svc.cluster.local:8000/health || \
        log_warning "Health check failed. Service may still be starting up."
}

# Run main function
main "$@"