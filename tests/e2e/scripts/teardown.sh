#!/bin/bash
#
# Unified E2E Teardown Script
#
# Cleans up E2E environment based on current cluster type.
#
# Usage:
#   ./teardown.sh           # Auto-detect and cleanup
#   ./teardown.sh --keep    # Keep cluster, only remove Helm release

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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
echo -e "${YELLOW}  E2E Environment Teardown${NC}"
echo -e "${YELLOW}========================================${NC}"
echo ""

# Detect cluster type
CONTEXT=$(kubectl config current-context 2>/dev/null || echo "")

if [ -z "$CONTEXT" ]; then
    log_info "No kubectl context found. Nothing to cleanup."
    exit 0
fi

log_info "Current context: $CONTEXT"

# Determine cleanup method
if [[ "$CONTEXT" =~ ^k3d- ]]; then
    CLUSTER_TYPE="k3d"
    CLUSTER_NAME="${CONTEXT#k3d-}"
elif [[ "$CONTEXT" =~ ^kind- ]]; then
    CLUSTER_TYPE="kind"
    CLUSTER_NAME="${CONTEXT#kind-}"
else
    CLUSTER_TYPE="existing"
    CLUSTER_NAME=""
fi

log_info "Detected cluster type: $CLUSTER_TYPE"

if [ "$KEEP_CLUSTER" = true ] || [ "$CLUSTER_TYPE" = "existing" ]; then
    # Just remove Helm release
    log_info "Removing Helm release..."

    if helm list -n "$NAMESPACE" 2>/dev/null | grep -q "$HELM_RELEASE"; then
        helm uninstall "$HELM_RELEASE" -n "$NAMESPACE" --wait
        log_success "Helm release removed"
    else
        log_info "Helm release not found"
    fi

    log_info "Deleting namespace..."
    kubectl delete namespace "$NAMESPACE" --wait=false 2>/dev/null || true
    log_success "Namespace deletion initiated"

else
    # Delete the entire cluster
    case $CLUSTER_TYPE in
        k3d)
            log_info "Deleting k3d cluster: $CLUSTER_NAME"
            k3d cluster delete "$CLUSTER_NAME"
            log_success "k3d cluster deleted"
            ;;
        kind)
            log_info "Deleting Kind cluster: $CLUSTER_NAME"
            kind delete cluster --name "$CLUSTER_NAME"
            log_success "Kind cluster deleted"
            ;;
    esac
fi

echo ""
log_success "Teardown complete"
echo ""
