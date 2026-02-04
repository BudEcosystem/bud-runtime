#!/bin/bash
#
# Teardown k3d cluster for E2E testing
#
# Usage:
#   ./teardown-k3d.sh           # Delete cluster
#   ./teardown-k3d.sh --keep    # Keep cluster, only uninstall Helm release

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

CLUSTER_NAME="bud-e2e"
NAMESPACE="bud-e2e"
HELM_RELEASE="bud-e2e"

KEEP_CLUSTER=false
for arg in "$@"; do
    case $arg in
        --keep)
            KEEP_CLUSTER=true
            ;;
    esac
done

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

echo ""
echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}  Bud Stack E2E Environment Teardown${NC}"
echo -e "${YELLOW}========================================${NC}"
echo ""

if [ "$KEEP_CLUSTER" = true ]; then
    log_info "Keeping cluster, only uninstalling Helm release..."

    # Check if release exists
    if helm list -n "$NAMESPACE" 2>/dev/null | grep -q "$HELM_RELEASE"; then
        log_info "Uninstalling Helm release '$HELM_RELEASE'..."
        helm uninstall "$HELM_RELEASE" -n "$NAMESPACE" --wait
        log_success "Helm release uninstalled"
    else
        log_info "Helm release '$HELM_RELEASE' not found"
    fi

    # Delete namespace
    log_info "Deleting namespace '$NAMESPACE'..."
    kubectl delete namespace "$NAMESPACE" --wait=false 2>/dev/null || true

else
    log_info "Deleting k3d cluster '$CLUSTER_NAME'..."

    if k3d cluster list 2>/dev/null | grep -q "^${CLUSTER_NAME}"; then
        k3d cluster delete "$CLUSTER_NAME"
        log_success "Cluster deleted"
    else
        log_info "Cluster '$CLUSTER_NAME' not found"
    fi
fi

echo ""
log_success "Teardown complete"
echo ""
