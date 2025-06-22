#!/bin/bash
# Deploy test services to both clusters

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "=========================================="
echo "Deploying Test Services"
echo "=========================================="

# Deploy to app cluster
echo -e "\n${YELLOW}Deploying to App Cluster...${NC}"
kubectl config use-context k3d-bud-app

# Apply BudProxy deployment
kubectl apply -f "$SCRIPT_DIR/app-cluster/budproxy.yaml"

# Wait for deployment
echo "Waiting for BudProxy to be ready..."
kubectl wait --for=condition=ready pod -l app=budproxy -n bud-system --timeout=60s

echo -e "${GREEN}✓ BudProxy deployed successfully${NC}"

# Deploy to inference cluster
echo -e "\n${YELLOW}Deploying to Inference Cluster...${NC}"
kubectl config use-context k3d-bud-inference

# Apply AIBrix deployment
kubectl apply -f "$SCRIPT_DIR/inference-cluster/aibrix.yaml"

# Wait for deployment
echo "Waiting for AIBrix to be ready..."
kubectl wait --for=condition=ready pod -l app=aibrix -n inference-system --timeout=60s

echo -e "${GREEN}✓ AIBrix deployed successfully${NC}"

# Show status
echo -e "\n${YELLOW}Deployment Status:${NC}"
echo -e "\n${GREEN}App Cluster:${NC}"
kubectl --context k3d-bud-app get pods -n bud-system
kubectl --context k3d-bud-app get svc -n bud-system

echo -e "\n${GREEN}Inference Cluster:${NC}"
kubectl --context k3d-bud-inference get pods -n inference-system
kubectl --context k3d-bud-inference get svc -n inference-system

echo -e "\n${GREEN}✓ Test services deployed successfully!${NC}"
echo ""
echo "To access services:"
echo "  BudProxy: kubectl port-forward -n bud-system svc/budproxy-service 8890:3000"
echo "  AIBrix:   kubectl --context k3d-bud-inference port-forward -n inference-system svc/aibrix-service 8891:8080"