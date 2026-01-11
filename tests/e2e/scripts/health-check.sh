#!/bin/bash
#
# Health check for E2E environment
#
# Verifies all services are up and responding
# Works with both k3d and Kind clusters

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

NAMESPACE="bud-e2e"

# Detect cluster type
if kubectl config current-context 2>/dev/null | grep -q "k3d-"; then
    CLUSTER_TYPE="k3d"
elif kubectl config current-context 2>/dev/null | grep -q "kind-"; then
    CLUSTER_TYPE="kind"
else
    CLUSTER_TYPE="unknown"
fi

echo "Detected cluster type: $CLUSTER_TYPE"

echo ""
echo "========================================="
echo "  E2E Environment Health Check"
echo "========================================="
echo ""

check_service() {
    local name=$1
    local url=$2
    local expected_status=${3:-200}

    printf "%-20s" "$name:"

    response=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "$url" 2>/dev/null || echo "000")

    if [ "$response" = "$expected_status" ] || [ "$response" = "200" ]; then
        echo -e "${GREEN}OK${NC} (HTTP $response)"
        return 0
    else
        echo -e "${RED}FAIL${NC} (HTTP $response)"
        return 1
    fi
}

check_pod() {
    local label=$1
    local name=$2

    printf "%-20s" "$name:"

    status=$(kubectl get pods -n "$NAMESPACE" -l "$label" -o jsonpath='{.items[0].status.phase}' 2>/dev/null || echo "NotFound")

    if [ "$status" = "Running" ]; then
        echo -e "${GREEN}Running${NC}"
        return 0
    else
        echo -e "${RED}$status${NC}"
        return 1
    fi
}

echo "Kubernetes Pods:"
echo "----------------"
check_pod "app.kubernetes.io/name=postgresql" "PostgreSQL"
check_pod "app.kubernetes.io/name=valkey" "Redis/Valkey"
check_pod "app.kubernetes.io/name=keycloak" "Keycloak"
check_pod "app=budapp" "budapp"

echo ""
echo "Service Endpoints:"
echo "------------------"

# Check if services are accessible
BUDAPP_URL=${E2E_BUDAPP_URL:-"http://localhost:9001"}
KEYCLOAK_URL=${E2E_KEYCLOAK_URL:-"http://localhost:9080"}

check_service "budapp /health" "$BUDAPP_URL/health"
check_service "Keycloak" "$KEYCLOAK_URL/health/ready" "200"

echo ""
echo "API Endpoints:"
echo "--------------"
check_service "budapp /docs" "$BUDAPP_URL/docs" "200"
check_service "budapp /auth" "$BUDAPP_URL/auth/login" "422"  # Expects POST, so 422 is ok

echo ""

# Summary
echo "========================================="
if kubectl get pods -n "$NAMESPACE" 2>/dev/null | grep -q "0/"; then
    echo -e "${YELLOW}Some pods are not fully ready${NC}"
    echo "Run: kubectl get pods -n $NAMESPACE"
else
    echo -e "${GREEN}All services appear healthy!${NC}"
fi
echo "========================================="
echo ""
