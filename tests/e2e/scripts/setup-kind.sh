#!/bin/bash
#
# Setup Kind cluster for E2E testing
#
# This script:
# 1. Creates a Kind cluster with the E2E configuration
# 2. Installs Dapr runtime
# 3. Deploys the bud-stack with E2E values
# 4. Waits for all services to be ready
#
# Prerequisites:
# - kind (https://kind.sigs.k8s.io/)
# - kubectl
# - helm
# - dapr CLI (optional, for dapr init)
#
# Usage:
#   ./setup-kind.sh              # Full setup
#   ./setup-kind.sh --skip-build # Skip image building
#   ./setup-kind.sh --clean      # Clean existing cluster first

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

CLUSTER_NAME="bud-e2e"
NAMESPACE="bud-e2e"
HELM_RELEASE="bud-e2e"

# Parse arguments
SKIP_BUILD=false
CLEAN_FIRST=false
for arg in "$@"; do
    case $arg in
        --skip-build)
            SKIP_BUILD=true
            ;;
        --clean)
            CLEAN_FIRST=true
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
echo -e "${GREEN}  Bud Stack E2E Environment Setup${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check prerequisites
log_info "Checking prerequisites..."

check_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "$1 is not installed. Please install it first."
        exit 1
    fi
}

check_command "kind"
check_command "kubectl"
check_command "helm"
check_command "docker"

log_success "All prerequisites are installed"

# Clean existing cluster if requested
if [ "$CLEAN_FIRST" = true ]; then
    log_info "Cleaning existing cluster..."
    kind delete cluster --name "$CLUSTER_NAME" 2>/dev/null || true
fi

# Check if cluster already exists
if kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
    log_warn "Cluster '$CLUSTER_NAME' already exists"
    read -p "Do you want to delete and recreate it? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "Deleting existing cluster..."
        kind delete cluster --name "$CLUSTER_NAME"
    else
        log_info "Using existing cluster"
        kubectl cluster-info --context "kind-$CLUSTER_NAME"
    fi
fi

# Create Kind cluster
if ! kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
    log_info "Creating Kind cluster '$CLUSTER_NAME'..."
    kind create cluster --config "$CONFIG_DIR/kind-config.yaml"
    log_success "Kind cluster created"
fi

# Set kubectl context
kubectl cluster-info --context "kind-$CLUSTER_NAME"
kubectl config use-context "kind-$CLUSTER_NAME"

# Create namespace
log_info "Creating namespace '$NAMESPACE'..."
kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
log_success "Namespace created"

# Install Dapr
log_info "Installing Dapr runtime..."
if ! kubectl get namespace dapr-system &> /dev/null; then
    # Install Dapr using Helm
    helm repo add dapr https://dapr.github.io/helm-charts/ 2>/dev/null || true
    helm repo update

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

# Wait for Dapr to be ready
log_info "Waiting for Dapr to be ready..."
kubectl rollout status deployment/dapr-operator -n dapr-system --timeout=120s
kubectl rollout status deployment/dapr-sidecar-injector -n dapr-system --timeout=120s
# Placement server is a StatefulSet
kubectl rollout status statefulset/dapr-placement-server -n dapr-system --timeout=120s 2>/dev/null || true
log_success "Dapr is ready"

# Build and load budapp image if not skipping
if [ "$SKIP_BUILD" = false ]; then
    log_info "Building budapp Docker image..."

    cd "$REPO_ROOT/services/budapp"
    docker build -t budstudio/budapp:latest -f deploy/Dockerfile .

    log_info "Loading image into Kind cluster..."
    kind load docker-image budstudio/budapp:latest --name "$CLUSTER_NAME"

    log_success "Image loaded into cluster"
    cd "$SCRIPT_DIR"
else
    log_info "Skipping image build (--skip-build)"
fi

# Add Bitnami repo for dependencies
log_info "Adding Helm repositories..."
helm repo add bitnami https://charts.bitnami.com/bitnami 2>/dev/null || true
helm repo update
log_success "Helm repositories updated"

# Update Helm dependencies
log_info "Updating Helm chart dependencies..."
cd "$REPO_ROOT/infra/helm/bud"
helm dependency update
cd "$SCRIPT_DIR"
log_success "Dependencies updated"

# Deploy with E2E values
log_info "Deploying bud-stack with E2E configuration..."
helm upgrade --install "$HELM_RELEASE" "$REPO_ROOT/infra/helm/bud" \
    --namespace "$NAMESPACE" \
    --values "$CONFIG_DIR/values.e2e.yaml" \
    --wait \
    --timeout 10m

log_success "Helm release deployed"

# Wait for all pods to be ready
log_info "Waiting for pods to be ready..."

wait_for_pod() {
    local label=$1
    local timeout=${2:-300}

    log_info "Waiting for pod with label: $label"
    kubectl wait --for=condition=ready pod \
        -l "$label" \
        -n "$NAMESPACE" \
        --timeout="${timeout}s" 2>/dev/null || {
            log_warn "Pod with label '$label' not ready yet, retrying..."
            sleep 10
            kubectl wait --for=condition=ready pod \
                -l "$label" \
                -n "$NAMESPACE" \
                --timeout="${timeout}s"
        }
}

# Wait for core services
wait_for_pod "app.kubernetes.io/name=postgresql" 180
wait_for_pod "app.kubernetes.io/name=valkey" 120
wait_for_pod "app.kubernetes.io/name=keycloak" 300

# Wait for budapp (may take longer due to migrations)
log_info "Waiting for budapp to be ready (including migrations)..."
sleep 10  # Give time for pod to start
wait_for_pod "app=budapp" 300

log_success "All pods are ready"

# Display cluster info
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  E2E Environment Ready!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Cluster: kind-$CLUSTER_NAME"
echo "Namespace: $NAMESPACE"
echo ""
echo "Service URLs:"
echo "  - budapp:    http://localhost:9001"
echo "  - Keycloak:  http://localhost:9080"
echo "  - PostgreSQL: localhost:9432"
echo "  - Redis:     localhost:9379"
echo ""
echo "Useful commands:"
echo "  kubectl get pods -n $NAMESPACE"
echo "  kubectl logs -n $NAMESPACE -l app=budapp -f"
echo "  kubectl port-forward -n $NAMESPACE svc/$HELM_RELEASE-budapp 9001:9082"
echo ""
echo "To run auth tests:"
echo "  cd tests/e2e && ./run_auth_tests.sh"
echo ""
echo "To cleanup:"
echo "  ./scripts/teardown-kind.sh"
echo ""
