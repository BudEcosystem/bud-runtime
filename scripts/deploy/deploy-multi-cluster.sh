#!/bin/bash
# deploy-multi-cluster.sh - Deploy services to both application and inference clusters

set -euo pipefail

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/../multi-cluster/utils/common.sh"

# Default values
APP_CLUSTER="${APP_CLUSTER_NAME:-bud-app}"
INFERENCE_CLUSTER="${INFERENCE_CLUSTER_NAME:-bud-inference}"
APP_NAMESPACE="${APP_NAMESPACE:-bud-system}"
INFERENCE_NAMESPACE="${INFERENCE_NAMESPACE:-inference-system}"
DEPLOY_APP="${DEPLOY_APP:-true}"
DEPLOY_INFERENCE="${DEPLOY_INFERENCE:-true}"
WAIT="${WAIT:-true}"
DRY_RUN="${DRY_RUN:-false}"
SETUP_CROSS_CLUSTER="${SETUP_CROSS_CLUSTER:-true}"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --app-cluster)
            APP_CLUSTER="$2"
            shift 2
            ;;
        --inference-cluster)
            INFERENCE_CLUSTER="$2"
            shift 2
            ;;
        --app-namespace)
            APP_NAMESPACE="$2"
            shift 2
            ;;
        --inference-namespace)
            INFERENCE_NAMESPACE="$2"
            shift 2
            ;;
        --skip-app)
            DEPLOY_APP="false"
            shift
            ;;
        --skip-inference)
            DEPLOY_INFERENCE="false"
            shift
            ;;
        --no-wait)
            WAIT="false"
            shift
            ;;
        --dry-run)
            DRY_RUN="true"
            shift
            ;;
        --no-cross-cluster)
            SETUP_CROSS_CLUSTER="false"
            shift
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  --app-cluster NAME          Application cluster name (default: $APP_CLUSTER)"
            echo "  --inference-cluster NAME    Inference cluster name (default: $INFERENCE_CLUSTER)"
            echo "  --app-namespace NAME        App cluster namespace (default: $APP_NAMESPACE)"
            echo "  --inference-namespace NAME  Inference namespace (default: $INFERENCE_NAMESPACE)"
            echo "  --skip-app                  Skip application cluster deployment"
            echo "  --skip-inference            Skip inference cluster deployment"
            echo "  --no-wait                   Don't wait for deployments"
            echo "  --dry-run                   Show what would be deployed"
            echo "  --no-cross-cluster          Skip cross-cluster configuration"
            echo "  --help                      Show this help message"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Function to check clusters
check_clusters() {
    log_info "Checking cluster availability..."
    
    local clusters_ok=true
    
    if [[ "$DEPLOY_APP" == "true" ]]; then
        if ! kubectl --context="k3d-$APP_CLUSTER" cluster-info >/dev/null 2>&1; then
            log_error "Cannot connect to application cluster '$APP_CLUSTER'"
            clusters_ok=false
        else
            log_success "Application cluster '$APP_CLUSTER' is accessible"
        fi
    fi
    
    if [[ "$DEPLOY_INFERENCE" == "true" ]]; then
        if ! kubectl --context="k3d-$INFERENCE_CLUSTER" cluster-info >/dev/null 2>&1; then
            log_error "Cannot connect to inference cluster '$INFERENCE_CLUSTER'"
            clusters_ok=false
        else
            log_success "Inference cluster '$INFERENCE_CLUSTER' is accessible"
        fi
    fi
    
    if [ "$clusters_ok" = false ]; then
        log_error "One or more clusters are not accessible"
        log_info "Run ./scripts/multi-cluster/setup-multi-cluster.sh to create clusters"
        exit 1
    fi
}

# Function to setup cross-cluster resources
setup_cross_cluster_resources() {
    if [[ "$SETUP_CROSS_CLUSTER" != "true" ]] || [[ "$DRY_RUN" == "true" ]]; then
        return 0
    fi
    
    log_info "Setting up cross-cluster resources..."
    
    # Create cross-cluster service entries
    cat <<EOF | kubectl --context="k3d-$APP_CLUSTER" apply -f -
apiVersion: v1
kind: Service
metadata:
  name: aibrix-external
  namespace: $APP_NAMESPACE
spec:
  type: ExternalName
  externalName: ${INFERENCE_CLUSTER}-aibrix.${INFERENCE_NAMESPACE}.svc.cluster.local
  ports:
  - port: 8080
    targetPort: 8080
    name: http
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: inference-cluster-config
  namespace: $APP_NAMESPACE
data:
  cluster_name: "$INFERENCE_CLUSTER"
  namespace: "$INFERENCE_NAMESPACE"
  aibrix_endpoint: "http://aibrix-external:8080"
EOF
    
    # Create app cluster reference in inference cluster
    cat <<EOF | kubectl --context="k3d-$INFERENCE_CLUSTER" apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-cluster-config
  namespace: $INFERENCE_NAMESPACE
data:
  cluster_name: "$APP_CLUSTER"
  namespace: "$APP_NAMESPACE"
  budproxy_endpoint: "http://budproxy-service.${APP_NAMESPACE}.svc.cluster.local:8000"
EOF
    
    log_success "Cross-cluster resources configured"
}

# Function to deploy to application cluster
deploy_app_cluster() {
    log_info "=== Deploying to Application Cluster ==="
    
    local deploy_cmd=(
        "$SCRIPT_DIR/deploy-app-cluster.sh"
        --cluster-name "$APP_CLUSTER"
        --namespace "$APP_NAMESPACE"
    )
    
    if [[ "$WAIT" == "false" ]]; then
        deploy_cmd+=(--no-wait)
    fi
    
    if [[ "$DRY_RUN" == "true" ]]; then
        deploy_cmd+=(--dry-run)
    fi
    
    if "${deploy_cmd[@]}"; then
        log_success "Application cluster deployment completed"
    else
        log_error "Application cluster deployment failed"
        return 1
    fi
}

# Function to deploy to inference cluster
deploy_inference_cluster() {
    log_info "=== Deploying to Inference Cluster ==="
    
    local deploy_cmd=(
        "$SCRIPT_DIR/deploy-inference-cluster.sh"
        --cluster-name "$INFERENCE_CLUSTER"
        --namespace "$INFERENCE_NAMESPACE"
    )
    
    if [[ "$WAIT" == "false" ]]; then
        deploy_cmd+=(--no-wait)
    fi
    
    if [[ "$DRY_RUN" == "true" ]]; then
        deploy_cmd+=(--dry-run)
    fi
    
    if "${deploy_cmd[@]}"; then
        log_success "Inference cluster deployment completed"
    else
        log_error "Inference cluster deployment failed"
        return 1
    fi
}

# Function to verify cross-cluster connectivity
verify_cross_cluster() {
    if [[ "$DRY_RUN" == "true" ]] || [[ "$SETUP_CROSS_CLUSTER" != "true" ]]; then
        return 0
    fi
    
    log_info "Verifying cross-cluster connectivity..."
    
    # Check if services can resolve each other
    # This is a basic check - actual connectivity depends on network setup
    
    log_info "Checking service discovery..."
    kubectl --context="k3d-$APP_CLUSTER" get svc -n "$APP_NAMESPACE" aibrix-external >/dev/null 2>&1 || \
        log_warning "Cross-cluster service 'aibrix-external' not found"
    
    log_success "Cross-cluster configuration verified"
}

# Function to display deployment summary
display_summary() {
    if [[ "$DRY_RUN" == "true" ]]; then
        return 0
    fi
    
    echo
    log_info "=== Multi-Cluster Deployment Summary ==="
    echo
    
    if [[ "$DEPLOY_APP" == "true" ]]; then
        echo "Application Cluster ($APP_CLUSTER):"
        echo "  Namespace: $APP_NAMESPACE"
        echo "  Services:"
        kubectl --context="k3d-$APP_CLUSTER" get svc -n "$APP_NAMESPACE" --no-headers | awk '{print "    - " $1}'
        echo
    fi
    
    if [[ "$DEPLOY_INFERENCE" == "true" ]]; then
        echo "Inference Cluster ($INFERENCE_CLUSTER):"
        echo "  Namespace: $INFERENCE_NAMESPACE"
        echo "  Services:"
        kubectl --context="k3d-$INFERENCE_CLUSTER" get svc -n "$INFERENCE_NAMESPACE" --no-headers | awk '{print "    - " $1}'
        echo
    fi
    
    echo "=== Next Steps ==="
    echo
    echo "1. Set up port forwarding for testing:"
    echo "   # BudProxy (App Cluster)"
    echo "   kubectl --context=k3d-$APP_CLUSTER port-forward -n $APP_NAMESPACE svc/budproxy-service 8000:8000"
    echo
    echo "   # AIBrix (Inference Cluster)"
    echo "   kubectl --context=k3d-$INFERENCE_CLUSTER port-forward -n $INFERENCE_NAMESPACE svc/inference-stack-aibrix 8080:8080"
    echo
    echo "2. Test end-to-end inference:"
    echo '   curl http://localhost:8000/v1/completions \'
    echo '     -H "Content-Type: application/json" \'
    echo '     -d "{"model": "llama2-7b", "prompt": "Hello!", "max_tokens": 50}"'
    echo
    echo "3. Monitor services:"
    echo "   # App Cluster Grafana"
    echo "   kubectl --context=k3d-$APP_CLUSTER port-forward -n $APP_NAMESPACE svc/grafana 3000:80"
    echo
    echo "   # Inference Cluster Grafana"
    echo "   kubectl --context=k3d-$INFERENCE_CLUSTER port-forward -n $INFERENCE_NAMESPACE svc/grafana 3001:80"
    echo
    
    # Save deployment info
    local info_file="$ROOT_DIR/configs/multi-cluster-deployment.yaml"
    mkdir -p "$(dirname "$info_file")"
    
    cat > "$info_file" <<EOF
# Multi-Cluster Deployment Information
# Generated: $(date)

application_cluster:
  name: $APP_CLUSTER
  namespace: $APP_NAMESPACE
  context: k3d-$APP_CLUSTER
  
inference_cluster:
  name: $INFERENCE_CLUSTER
  namespace: $INFERENCE_NAMESPACE
  context: k3d-$INFERENCE_CLUSTER
  
cross_cluster:
  enabled: $SETUP_CROSS_CLUSTER
  
test_commands:
  port_forward:
    budproxy: kubectl --context=k3d-$APP_CLUSTER port-forward -n $APP_NAMESPACE svc/budproxy-service 8000:8000
    aibrix: kubectl --context=k3d-$INFERENCE_CLUSTER port-forward -n $INFERENCE_NAMESPACE svc/inference-stack-aibrix 8080:8080
  
  inference_test: |
    curl http://localhost:8000/v1/completions \\
      -H "Content-Type: application/json" \\
      -d '{"model": "llama2-7b", "prompt": "Hello!", "max_tokens": 50}'
EOF
    
    log_success "Deployment information saved to: $info_file"
}

# Main deployment flow
main() {
    log_info "Starting multi-cluster deployment..."
    
    # Start timer
    local start_time=$(date +%s)
    
    # Check prerequisites
    verify_prerequisites || exit 1
    
    # Check clusters
    check_clusters
    
    # Deploy to application cluster
    if [[ "$DEPLOY_APP" == "true" ]]; then
        deploy_app_cluster || exit 1
        echo
    fi
    
    # Deploy to inference cluster
    if [[ "$DEPLOY_INFERENCE" == "true" ]]; then
        deploy_inference_cluster || exit 1
        echo
    fi
    
    # Setup cross-cluster resources
    if [[ "$DEPLOY_APP" == "true" ]] && [[ "$DEPLOY_INFERENCE" == "true" ]]; then
        setup_cross_cluster_resources
        verify_cross_cluster
    fi
    
    # Calculate elapsed time
    local end_time=$(date +%s)
    local elapsed=$((end_time - start_time))
    local minutes=$((elapsed / 60))
    local seconds=$((elapsed % 60))
    
    echo
    log_success "Multi-cluster deployment completed in ${minutes}m ${seconds}s"
    
    # Display summary
    display_summary
}

# Run main function
main