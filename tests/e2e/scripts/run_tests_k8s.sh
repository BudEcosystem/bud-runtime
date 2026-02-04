#!/bin/bash
#
# Run E2E tests against a Kubernetes deployment
#
# Usage:
#   ./scripts/run_tests_k8s.sh                      # Run all tests (default namespace: bud-dev)
#   ./scripts/run_tests_k8s.sh -n bud-staging auth  # Run auth tests against bud-staging
#   ./scripts/run_tests_k8s.sh --install            # Install dependencies first
#   ./scripts/run_tests_k8s.sh --check              # Only check connectivity
#
# Environment Variables:
#   E2E_NAMESPACE     - Kubernetes namespace (default: bud-dev)
#   E2E_RELEASE_NAME  - Helm release name (default: same as namespace)
#   E2E_SKIP_PORT_FORWARD - Skip port-forwarding if services are already accessible

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
E2E_DIR="$(dirname "$SCRIPT_DIR")"
cd "$E2E_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration with defaults
NAMESPACE="${E2E_NAMESPACE:-bud-dev}"
RELEASE_NAME="${E2E_RELEASE_NAME:-}"
SKIP_PORT_FORWARD="${E2E_SKIP_PORT_FORWARD:-false}"
PORT_FORWARD_PIDS=()

# Parse arguments
TEST_SUITE=""
INSTALL_DEPS=false
CHECK_ONLY=false
VERBOSE=""
PYTEST_ARGS=""

print_usage() {
    echo "Usage: $0 [OPTIONS] [TEST_SUITE]"
    echo ""
    echo "Run E2E tests against a Kubernetes deployment of Bud Stack."
    echo ""
    echo "Test Suites:"
    echo "  auth          Run authentication tests only"
    echo "  models        Run model tests only"
    echo "  flows         Run all flow tests"
    echo "  all           Run all tests (default)"
    echo ""
    echo "Options:"
    echo "  -n, --namespace NS    Kubernetes namespace (default: bud-dev)"
    echo "  -r, --release NAME    Helm release name (default: same as namespace)"
    echo "  -i, --install         Install Python dependencies first"
    echo "  -c, --check           Only check connectivity, don't run tests"
    echo "  -v, --verbose         Verbose test output"
    echo "  -x, --exitfirst       Exit on first failure (default)"
    echo "  --no-exitfirst        Don't exit on first failure"
    echo "  --skip-port-forward   Skip port-forwarding (use if already set up)"
    echo "  -k EXPRESSION         Only run tests matching expression"
    echo "  -m MARKER             Only run tests with marker"
    echo "  -h, --help            Show this help"
    echo ""
    echo "Examples:"
    echo "  $0 --install auth              # Install deps and run auth tests"
    echo "  $0 -n bud-staging --check      # Check connectivity to bud-staging"
    echo "  $0 -v models                   # Run model tests with verbose output"
    echo "  $0 -k 'login' auth             # Run only login tests in auth suite"
    echo "  $0 -m slow models              # Run slow model tests"
    echo ""
    echo "Environment Variables:"
    echo "  E2E_NAMESPACE         Default namespace"
    echo "  E2E_RELEASE_NAME      Helm release name"
    echo "  E2E_SKIP_PORT_FORWARD Skip port-forwarding"
}

while [[ $# -gt 0 ]]; do
    case $1 in
        auth|models|flows|all)
            TEST_SUITE="$1"
            shift
            ;;
        -n|--namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        -r|--release)
            RELEASE_NAME="$2"
            shift 2
            ;;
        -i|--install)
            INSTALL_DEPS=true
            shift
            ;;
        -c|--check)
            CHECK_ONLY=true
            shift
            ;;
        -v|--verbose)
            VERBOSE="-v"
            shift
            ;;
        -x|--exitfirst)
            PYTEST_ARGS="$PYTEST_ARGS -x"
            shift
            ;;
        --no-exitfirst)
            # Remove -x from default
            shift
            ;;
        --skip-port-forward)
            SKIP_PORT_FORWARD=true
            shift
            ;;
        -k)
            PYTEST_ARGS="$PYTEST_ARGS -k '$2'"
            shift 2
            ;;
        -m)
            PYTEST_ARGS="$PYTEST_ARGS -m '$2'"
            shift 2
            ;;
        -h|--help)
            print_usage
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Set release name to namespace if not specified
RELEASE_NAME="${RELEASE_NAME:-$NAMESPACE}"

# Service name prefix (based on Helm release)
SVC_PREFIX="${RELEASE_NAME}"

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

cleanup() {
    log_info "Cleaning up port-forwards..."
    for pid in "${PORT_FORWARD_PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
        fi
    done
    # Also kill any orphaned port-forwards from this script
    pkill -f "kubectl port-forward -n $NAMESPACE svc/${SVC_PREFIX}" 2>/dev/null || true
    log_success "Cleanup complete"
}

trap cleanup EXIT

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Bud Stack E2E Tests${NC}"
echo -e "${GREEN}  Namespace: ${NAMESPACE}${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check prerequisites
log_info "Checking prerequisites..."

if ! command -v kubectl &> /dev/null; then
    log_error "kubectl not found. Please install kubectl."
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    log_error "python3 not found. Please install Python 3.10+."
    exit 1
fi

# Check if we can reach the cluster
if ! kubectl cluster-info &> /dev/null; then
    log_error "Cannot connect to Kubernetes cluster. Check your kubeconfig."
    exit 1
fi

# Verify namespace exists
if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
    log_error "Namespace '$NAMESPACE' not found."
    echo ""
    echo "Available namespaces with bud deployments:"
    kubectl get namespaces -o name | xargs -I{} sh -c 'kubectl get deploy -n $(echo {} | cut -d/ -f2) 2>/dev/null | grep -q budapp && echo "  - $(echo {} | cut -d/ -f2)"' 2>/dev/null || echo "  (none found)"
    exit 1
fi

log_success "Prerequisites OK"

# Check .env.e2e exists
if [ ! -f ".env.e2e" ]; then
    log_warn ".env.e2e not found."
    if [ -f ".env.e2e.sample" ]; then
        log_info "Creating .env.e2e from sample..."
        cp .env.e2e.sample .env.e2e
        log_warn "Please review and update .env.e2e with correct values"
    else
        log_error "No .env.e2e.sample found. Please create .env.e2e manually."
        exit 1
    fi
fi
log_success ".env.e2e found"

# Install dependencies if requested
if [ "$INSTALL_DEPS" = true ]; then
    log_info "Installing Python dependencies..."
    pip install -r requirements.txt -q
    log_success "Dependencies installed"
fi

# Check if dependencies are installed
if ! python3 -c "import pytest, httpx" 2>/dev/null; then
    log_warn "Python dependencies not installed. Run with --install flag."
    log_info "Or manually: pip install -r requirements.txt"
    exit 1
fi

# Discover service names
log_info "Discovering services in namespace $NAMESPACE..."

# Try to find PostgreSQL service
POSTGRES_SVC=$(kubectl get svc -n "$NAMESPACE" -o name 2>/dev/null | grep -E "postgresql|postgres" | head -1 | cut -d/ -f2 || echo "")
if [ -z "$POSTGRES_SVC" ]; then
    POSTGRES_SVC="${SVC_PREFIX}-postgresql"
fi

# Try to find Redis/Valkey service
REDIS_SVC=$(kubectl get svc -n "$NAMESPACE" -o name 2>/dev/null | grep -E "valkey|redis" | grep -v "headless" | head -1 | cut -d/ -f2 || echo "")
if [ -z "$REDIS_SVC" ]; then
    REDIS_SVC="${SVC_PREFIX}-valkey-primary"
fi

log_info "Using PostgreSQL service: $POSTGRES_SVC"
log_info "Using Redis/Valkey service: $REDIS_SVC"

if [ "$SKIP_PORT_FORWARD" != "true" ]; then
    # Kill existing port-forwards to avoid conflicts
    log_info "Cleaning up existing port-forwards..."
    pkill -f "kubectl port-forward -n $NAMESPACE svc/.*postgresql" 2>/dev/null || true
    pkill -f "kubectl port-forward -n $NAMESPACE svc/.*valkey" 2>/dev/null || true
    pkill -f "kubectl port-forward -n $NAMESPACE svc/.*redis" 2>/dev/null || true
    sleep 1

    # Start port-forwards
    log_info "Starting port-forwards..."

    # PostgreSQL
    if kubectl get svc -n "$NAMESPACE" "$POSTGRES_SVC" &>/dev/null; then
        kubectl port-forward -n "$NAMESPACE" "svc/$POSTGRES_SVC" 5432:5432 &>/dev/null &
        PORT_FORWARD_PIDS+=($!)
        sleep 1
    else
        log_warn "PostgreSQL service $POSTGRES_SVC not found, skipping port-forward"
    fi

    # Valkey/Redis
    if kubectl get svc -n "$NAMESPACE" "$REDIS_SVC" &>/dev/null; then
        kubectl port-forward -n "$NAMESPACE" "svc/$REDIS_SVC" 6379:6379 &>/dev/null &
        PORT_FORWARD_PIDS+=($!)
        sleep 1
    else
        log_warn "Redis/Valkey service $REDIS_SVC not found, skipping port-forward"
    fi

    # Wait for port-forwards to be ready
    log_info "Waiting for port-forwards to establish..."
    sleep 3

    # Verify port-forwards
    if nc -z localhost 5432 2>/dev/null; then
        log_success "PostgreSQL port-forward active (localhost:5432)"
    else
        log_warn "PostgreSQL port-forward may not be ready"
    fi

    if nc -z localhost 6379 2>/dev/null; then
        log_success "Valkey/Redis port-forward active (localhost:6379)"
    else
        log_warn "Valkey/Redis port-forward may not be ready"
    fi
else
    log_info "Skipping port-forward setup (--skip-port-forward)"
fi

# Check service connectivity
log_info "Checking service connectivity..."

# budapp via ingress (from .env.e2e)
BUDAPP_URL=$(grep -E "^E2E_BUDAPP_URL=" .env.e2e 2>/dev/null | cut -d'=' -f2 || echo "")
if [ -n "$BUDAPP_URL" ]; then
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BUDAPP_URL/health" 2>/dev/null || echo "000")
    if [ "$HTTP_CODE" = "200" ]; then
        log_success "budapp reachable at $BUDAPP_URL (HTTP $HTTP_CODE)"
    else
        log_error "budapp not reachable at $BUDAPP_URL (HTTP $HTTP_CODE)"
        echo ""
        echo "Possible issues:"
        echo "  - Check if E2E_BUDAPP_URL in .env.e2e is correct"
        echo "  - Check if ingress is configured"
        echo "  - Check if budapp pod is running: kubectl get pods -n $NAMESPACE | grep budapp"
        exit 1
    fi
else
    log_warn "E2E_BUDAPP_URL not set in .env.e2e"
fi

# If check only, exit here
if [ "$CHECK_ONLY" = true ]; then
    echo ""
    log_success "All connectivity checks passed!"
    echo ""
    echo "Configuration:"
    echo "  - Namespace: $NAMESPACE"
    echo "  - Release: $RELEASE_NAME"
    echo "  - budapp: $BUDAPP_URL"
    echo "  - PostgreSQL: localhost:5432 (via $POSTGRES_SVC)"
    echo "  - Valkey/Redis: localhost:6379 (via $REDIS_SVC)"
    echo ""
    echo "Ready to run tests:"
    echo "  $0 -n $NAMESPACE [auth|models|all]"
    exit 0
fi

# Determine test path
case "$TEST_SUITE" in
    auth)
        TEST_PATH="flows/auth/"
        ;;
    models)
        TEST_PATH="flows/models/"
        ;;
    flows)
        TEST_PATH="flows/"
        ;;
    all|"")
        TEST_PATH="."
        ;;
esac

# Default to exit on first failure
if [[ ! "$PYTEST_ARGS" =~ "-x" ]] && [[ ! "$PYTEST_ARGS" =~ "no-exitfirst" ]]; then
    PYTEST_ARGS="$PYTEST_ARGS -x"
fi

echo ""
log_info "Running E2E tests: $TEST_PATH"
log_info "Namespace: $NAMESPACE"
echo ""

# Run tests
set +e  # Don't exit on test failure
eval "python3 -m pytest \"$TEST_PATH\" $VERBOSE --tb=short $PYTEST_ARGS"
TEST_EXIT_CODE=$?
set -e

echo ""
if [ $TEST_EXIT_CODE -eq 0 ]; then
    log_success "All tests passed!"
else
    log_error "Some tests failed (exit code: $TEST_EXIT_CODE)"
fi

exit $TEST_EXIT_CODE
