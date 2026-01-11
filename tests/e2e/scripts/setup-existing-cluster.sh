#!/bin/bash
#
# Setup E2E tests on an existing Kubernetes cluster
#
# This script deploys the E2E test environment to your current kubectl context.
# Use this when you already have a k3s, k8s, or any Kubernetes cluster running.
#
# Prerequisites:
# - kubectl configured with access to your cluster
# - helm
#
# Usage:
#   ./setup-existing-cluster.sh                    # Deploy to current context
#   ./setup-existing-cluster.sh --context myctx    # Use specific context
#   ./setup-existing-cluster.sh --namespace test   # Use custom namespace
#   ./setup-existing-cluster.sh --skip-build       # Skip image building
#   ./setup-existing-cluster.sh --skip-dapr        # Skip Dapr installation (if already installed)
#   ./setup-existing-cluster.sh --local-registry   # Use local registry for images

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
E2E_DIR="$(dirname "$SCRIPT_DIR")"
REPO_ROOT="$(dirname "$(dirname "$E2E_DIR")")"
CONFIG_DIR="$E2E_DIR/config"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Defaults
NAMESPACE="bud-e2e"
HELM_RELEASE="bud-e2e"
KUBE_CONTEXT=""
SKIP_BUILD=false
SKIP_DAPR=false
LOCAL_REGISTRY=""
VALUES_FILE="$CONFIG_DIR/values.e2e.yaml"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --context)
            KUBE_CONTEXT="$2"
            shift 2
            ;;
        --namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        --skip-build)
            SKIP_BUILD=true
            shift
            ;;
        --skip-dapr)
            SKIP_DAPR=true
            shift
            ;;
        --local-registry)
            LOCAL_REGISTRY="$2"
            shift 2
            ;;
        --values)
            VALUES_FILE="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --context NAME      Use specific kubectl context"
            echo "  --namespace NAME    Deploy to specific namespace (default: bud-e2e)"
            echo "  --skip-build        Skip Docker image building"
            echo "  --skip-dapr         Skip Dapr installation"
            echo "  --local-registry    Local registry URL (e.g., localhost:5000)"
            echo "  --values FILE       Custom values file"
            echo "  --help              Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Bud Stack E2E Setup${NC}"
echo -e "${GREEN}  (Existing Cluster Mode)${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check prerequisites
log_info "Checking prerequisites..."
command -v kubectl &> /dev/null || { log_error "kubectl not found"; exit 1; }
command -v helm &> /dev/null || { log_error "helm not found"; exit 1; }
log_success "Prerequisites OK"

# Set kubectl context if specified
if [ -n "$KUBE_CONTEXT" ]; then
    log_info "Switching to context: $KUBE_CONTEXT"
    kubectl config use-context "$KUBE_CONTEXT"
fi

# Verify cluster access
log_info "Verifying cluster access..."
CURRENT_CONTEXT=$(kubectl config current-context)
log_info "Using context: $CURRENT_CONTEXT"

if ! kubectl cluster-info &> /dev/null; then
    log_error "Cannot connect to cluster. Please check your kubeconfig."
    exit 1
fi
log_success "Cluster connection verified"

# Show cluster info
kubectl cluster-info | head -2

# Create namespace
log_info "Creating namespace '$NAMESPACE'..."
kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
log_success "Namespace ready"

# Install Dapr if not skipped
if [ "$SKIP_DAPR" = false ]; then
    log_info "Checking Dapr installation..."
    if ! kubectl get namespace dapr-system &> /dev/null; then
        log_info "Installing Dapr runtime..."
        helm repo add dapr https://dapr.github.io/helm-charts/ 2>/dev/null || true
        helm repo update dapr

        helm upgrade --install dapr dapr/dapr \
            --namespace dapr-system \
            --create-namespace \
            --wait \
            --timeout 5m \
            --set global.ha.enabled=false \
            --set dapr_scheduler.replicaCount=1 \
            --set dapr_placement.replicaCount=1

        log_success "Dapr installed"
    else
        log_info "Dapr already installed"
    fi

    # Wait for Dapr
    log_info "Waiting for Dapr to be ready..."
    kubectl rollout status deployment/dapr-operator -n dapr-system --timeout=120s
    kubectl rollout status deployment/dapr-sidecar-injector -n dapr-system --timeout=120s
    # Placement server is a StatefulSet
    kubectl rollout status statefulset/dapr-placement-server -n dapr-system --timeout=120s 2>/dev/null || true
    log_success "Dapr is ready"
else
    log_info "Skipping Dapr installation (--skip-dapr)"
fi

# Build image if not skipped
if [ "$SKIP_BUILD" = false ]; then
    log_info "Building budapp Docker image..."
    cd "$REPO_ROOT/services/budapp"

    if [ -n "$LOCAL_REGISTRY" ]; then
        IMAGE_TAG="$LOCAL_REGISTRY/budstudio/budapp:latest"
        docker build -t "$IMAGE_TAG" -f deploy/Dockerfile .
        docker push "$IMAGE_TAG"
        log_success "Image pushed to $LOCAL_REGISTRY"
    else
        docker build -t budstudio/budapp:latest -f deploy/Dockerfile .

        # Try to import to k3d if running k3d
        if echo "$CURRENT_CONTEXT" | grep -q "k3d-"; then
            CLUSTER_NAME=$(echo "$CURRENT_CONTEXT" | sed 's/k3d-//')
            log_info "Importing image to k3d cluster: $CLUSTER_NAME"
            k3d image import budstudio/budapp:latest -c "$CLUSTER_NAME" 2>/dev/null || true
        fi
        log_success "Image built"
    fi
    cd "$SCRIPT_DIR"
else
    log_info "Skipping image build (--skip-build)"
fi

# Add Helm repos
log_info "Adding Helm repositories..."
helm repo add bitnami https://charts.bitnami.com/bitnami 2>/dev/null || true
helm repo update
log_success "Helm repositories updated"

# Update chart dependencies
log_info "Updating Helm chart dependencies..."
cd "$REPO_ROOT/infra/helm/bud"
helm dependency update
cd "$SCRIPT_DIR"
log_success "Dependencies updated"

# Prepare values override for existing cluster
EXTRA_VALUES=""
if [ -n "$LOCAL_REGISTRY" ]; then
    EXTRA_VALUES="--set microservices.budapp.image=$LOCAL_REGISTRY/budstudio/budapp:latest"
fi

# Deploy
log_info "Deploying bud-stack..."
log_info "Using values: $VALUES_FILE"

helm upgrade --install "$HELM_RELEASE" "$REPO_ROOT/infra/helm/bud" \
    --namespace "$NAMESPACE" \
    --values "$VALUES_FILE" \
    $EXTRA_VALUES \
    --wait \
    --timeout 10m

log_success "Helm release deployed"

# Wait for pods
log_info "Waiting for pods to be ready..."

wait_for_deployment() {
    local name=$1
    local timeout=${2:-300}
    log_info "Waiting for $name..."
    kubectl rollout status deployment/"$name" -n "$NAMESPACE" --timeout="${timeout}s" 2>/dev/null || \
    kubectl rollout status statefulset/"$name" -n "$NAMESPACE" --timeout="${timeout}s" 2>/dev/null || true
}

# Get service URLs based on service type
get_service_url() {
    local svc=$1
    local port=$2

    SVC_TYPE=$(kubectl get svc "$svc" -n "$NAMESPACE" -o jsonpath='{.spec.type}' 2>/dev/null || echo "ClusterIP")

    case $SVC_TYPE in
        NodePort)
            NODE_PORT=$(kubectl get svc "$svc" -n "$NAMESPACE" -o jsonpath='{.spec.ports[0].nodePort}')
            echo "localhost:$NODE_PORT"
            ;;
        LoadBalancer)
            LB_IP=$(kubectl get svc "$svc" -n "$NAMESPACE" -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
            if [ -n "$LB_IP" ]; then
                echo "$LB_IP:$port"
            else
                echo "pending (use port-forward)"
            fi
            ;;
        *)
            echo "ClusterIP (use port-forward)"
            ;;
    esac
}

sleep 5

# Show status
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  E2E Environment Deployed!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Context: $CURRENT_CONTEXT"
echo "Namespace: $NAMESPACE"
echo "Release: $HELM_RELEASE"
echo ""

# Check pod status
echo "Pod Status:"
kubectl get pods -n "$NAMESPACE" --no-headers 2>/dev/null | while read line; do
    NAME=$(echo $line | awk '{print $1}')
    STATUS=$(echo $line | awk '{print $3}')
    if [ "$STATUS" = "Running" ]; then
        echo -e "  $NAME: ${GREEN}$STATUS${NC}"
    else
        echo -e "  $NAME: ${YELLOW}$STATUS${NC}"
    fi
done

echo ""
echo "Port-Forward Commands (if needed):"
echo "  kubectl port-forward -n $NAMESPACE svc/${HELM_RELEASE}-budapp 9001:9082"
echo "  kubectl port-forward -n $NAMESPACE svc/${HELM_RELEASE}-keycloak 9080:80"
echo "  kubectl port-forward -n $NAMESPACE svc/${HELM_RELEASE}-postgresql 9432:5432"
echo "  kubectl port-forward -n $NAMESPACE svc/${HELM_RELEASE}-valkey-master 9379:6379"
echo ""
echo "To run auth tests:"
echo "  cd tests/e2e && ./run_auth_tests.sh"
echo ""
echo "To cleanup:"
echo "  helm uninstall $HELM_RELEASE -n $NAMESPACE"
echo "  kubectl delete namespace $NAMESPACE"
echo ""
