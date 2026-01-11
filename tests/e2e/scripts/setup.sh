#!/bin/bash
#
# Unified E2E Setup Script
#
# Automatically selects the best setup method based on environment:
# 1. Existing cluster (if kubectl context is available and cluster is reachable)
# 2. k3d (if available - preferred for local dev)
# 3. Kind (fallback)
#
# Usage:
#   ./setup.sh                    # Auto-detect best method
#   ./setup.sh --method k3d       # Force k3d
#   ./setup.sh --method kind      # Force Kind
#   ./setup.sh --method existing  # Use existing cluster
#   ./setup.sh --help             # Show help

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

METHOD=""
EXTRA_ARGS=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --method)
            METHOD="$2"
            shift 2
            ;;
        --help)
            echo "E2E Environment Setup"
            echo ""
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --method METHOD    Force setup method: k3d, kind, existing"
            echo "  --help             Show this help"
            echo ""
            echo "All other arguments are passed to the underlying setup script."
            echo ""
            echo "Methods:"
            echo "  k3d       Create new k3d cluster (recommended)"
            echo "  kind      Create new Kind cluster"
            echo "  existing  Deploy to existing Kubernetes cluster"
            echo ""
            echo "Examples:"
            echo "  $0                           # Auto-detect"
            echo "  $0 --method k3d              # Force k3d"
            echo "  $0 --method existing         # Use existing cluster"
            echo "  $0 --skip-build              # Skip image build"
            exit 0
            ;;
        *)
            EXTRA_ARGS="$EXTRA_ARGS $1"
            shift
            ;;
    esac
done

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# Auto-detect method if not specified
if [ -z "$METHOD" ]; then
    log_info "Auto-detecting setup method..."

    # Check if we have an existing cluster that's not k3d/kind
    if kubectl cluster-info &> /dev/null; then
        CONTEXT=$(kubectl config current-context 2>/dev/null)
        if [[ ! "$CONTEXT" =~ ^(k3d-|kind-) ]]; then
            log_info "Found existing cluster: $CONTEXT"
            read -p "Use existing cluster? (Y/n) " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Nn]$ ]]; then
                METHOD="existing"
            fi
        fi
    fi

    # If not using existing, prefer k3d
    if [ -z "$METHOD" ]; then
        if command -v k3d &> /dev/null; then
            METHOD="k3d"
        elif command -v kind &> /dev/null; then
            METHOD="kind"
        else
            echo "Error: Neither k3d nor kind is installed."
            echo "Install k3d: curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash"
            exit 1
        fi
    fi
fi

log_info "Using method: $METHOD"
echo ""

# Run appropriate setup script
case $METHOD in
    k3d)
        exec "$SCRIPT_DIR/setup-k3d.sh" $EXTRA_ARGS
        ;;
    kind)
        exec "$SCRIPT_DIR/setup-kind.sh" $EXTRA_ARGS
        ;;
    existing)
        exec "$SCRIPT_DIR/setup-existing-cluster.sh" $EXTRA_ARGS
        ;;
    *)
        echo "Unknown method: $METHOD"
        echo "Valid methods: k3d, kind, existing"
        exit 1
        ;;
esac
