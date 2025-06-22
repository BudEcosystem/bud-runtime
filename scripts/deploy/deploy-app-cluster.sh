#!/bin/bash
# deploy-app-cluster.sh - Deploy application services to the app cluster

set -euo pipefail

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/../multi-cluster/utils/common.sh"

# Default values
CLUSTER_NAME="${APP_CLUSTER_NAME:-bud-app}"
NAMESPACE="${NAMESPACE:-bud-system}"
RELEASE_NAME="${RELEASE_NAME:-bud-app}"
VALUES_FILE="${VALUES_FILE:-$ROOT_DIR/helm/bud-stack/environments/values-app-cluster.yaml}"
WAIT="${WAIT:-true}"
TIMEOUT="${TIMEOUT:-10m}"
DRY_RUN="${DRY_RUN:-false}"

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
        --help)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  --cluster-name NAME     Target cluster name (default: $CLUSTER_NAME)"
            echo "  --namespace NAME        Kubernetes namespace (default: $NAMESPACE)"
            echo "  --release-name NAME     Helm release name (default: $RELEASE_NAME)"
            echo "  --values-file FILE      Values file path (default: environments/values-app-cluster.yaml)"
            echo "  --no-wait              Don't wait for deployment to complete"
            echo "  --timeout DURATION     Deployment timeout (default: $TIMEOUT)"
            echo "  --dry-run              Show what would be deployed without deploying"
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
        log_info "Make sure the cluster is running: ./scripts/multi-cluster/setup-app-cluster.sh"
        exit 1
    fi
    
    log_success "Connected to cluster '$CLUSTER_NAME'"
}

# Function to prepare deployment
prepare_deployment() {
    log_info "Preparing deployment..."
    
    # Create namespace if it doesn't exist
    create_namespace_if_not_exists "$NAMESPACE" "k3d-$CLUSTER_NAME"
    
    # Update Helm dependencies
    log_info "Updating Helm dependencies..."
    cd "$ROOT_DIR/helm/bud-stack"
    helm dependency update
    
    # Validate values file
    if [ ! -f "$VALUES_FILE" ]; then
        log_error "Values file not found: $VALUES_FILE"
        exit 1
    fi
    
    log_success "Deployment prepared"
}

# Function to deploy services
deploy_services() {
    log_info "Deploying services to application cluster..."
    
    cd "$ROOT_DIR/helm/bud-stack"
    
    # Build helm command
    local helm_cmd=(
        helm upgrade --install "$RELEASE_NAME" .
        --namespace "$NAMESPACE"
        --values "$VALUES_FILE"
        --kubeconfig "$HOME/.kube/config"
        --kube-context "k3d-$CLUSTER_NAME"
        --create-namespace
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
    
    # Wait for pods to be ready if requested
    if [[ "$WAIT" == "true" ]]; then
        log_info "Waiting for all pods to be ready..."
        kubectl --context="k3d-$CLUSTER_NAME" wait --for=condition=ready pod \
            --all -n "$NAMESPACE" \
            --timeout="$TIMEOUT" || log_warning "Some pods may still be starting"
    fi
    
    # Check services
    log_info "Services deployed:"
    kubectl --context="k3d-$CLUSTER_NAME" get services -n "$NAMESPACE"
    
    # Check ingresses
    log_info "Ingresses configured:"
    kubectl --context="k3d-$CLUSTER_NAME" get ingress -n "$NAMESPACE"
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
    echo "  # BudProxy API Gateway"
    echo "  kubectl --context=k3d-$CLUSTER_NAME port-forward -n $NAMESPACE svc/budproxy-service 8000:8000"
    echo
    echo "  # Grafana Dashboard"
    echo "  kubectl --context=k3d-$CLUSTER_NAME port-forward -n $NAMESPACE svc/grafana 3000:80"
    echo
    echo "  # Prometheus"
    echo "  kubectl --context=k3d-$CLUSTER_NAME port-forward -n $NAMESPACE svc/prometheus-kube-prometheus-prometheus 9090:9090"
    echo
    echo "To view logs:"
    echo "  kubectl --context=k3d-$CLUSTER_NAME logs -n $NAMESPACE -l app=budproxy -f"
    echo
    echo "To check deployment status:"
    echo "  helm status $RELEASE_NAME -n $NAMESPACE --kube-context k3d-$CLUSTER_NAME"
}

# Function to create post-deployment config
create_post_deployment_config() {
    if [[ "$DRY_RUN" == "true" ]]; then
        return 0
    fi
    
    local config_file="$ROOT_DIR/configs/app-cluster/deployment-info.yaml"
    mkdir -p "$(dirname "$config_file")"
    
    cat > "$config_file" <<EOF
# Application Cluster Deployment Information
# Generated: $(date)

deployment:
  cluster: $CLUSTER_NAME
  namespace: $NAMESPACE
  release: $RELEASE_NAME
  values_file: $VALUES_FILE
  
services:
  budproxy:
    name: budproxy-service
    port: 8000
    endpoint: http://localhost:8000  # After port-forward
  grafana:
    name: grafana
    port: 80
    endpoint: http://localhost:3000  # After port-forward
  prometheus:
    name: prometheus-kube-prometheus-prometheus
    port: 9090
    endpoint: http://localhost:9090  # After port-forward

commands:
  port_forward:
    budproxy: kubectl --context=k3d-$CLUSTER_NAME port-forward -n $NAMESPACE svc/budproxy-service 8000:8000
    grafana: kubectl --context=k3d-$CLUSTER_NAME port-forward -n $NAMESPACE svc/grafana 3000:80
    prometheus: kubectl --context=k3d-$CLUSTER_NAME port-forward -n $NAMESPACE svc/prometheus-kube-prometheus-prometheus 9090:9090
  
  logs:
    budproxy: kubectl --context=k3d-$CLUSTER_NAME logs -n $NAMESPACE -l app=budproxy -f
    all_apps: kubectl --context=k3d-$CLUSTER_NAME logs -n $NAMESPACE -l component=app -f
  
  status:
    helm: helm status $RELEASE_NAME -n $NAMESPACE --kube-context k3d-$CLUSTER_NAME
    pods: kubectl --context=k3d-$CLUSTER_NAME get pods -n $NAMESPACE
    services: kubectl --context=k3d-$CLUSTER_NAME get services -n $NAMESPACE
EOF
    
    log_success "Deployment configuration saved to: $config_file"
}

# Main deployment flow
main() {
    log_info "Starting application cluster deployment..."
    
    # Check prerequisites
    verify_prerequisites || exit 1
    
    # Check cluster connectivity
    check_cluster
    
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
    
    log_success "Application cluster deployment completed!"
}

# Run main function
main