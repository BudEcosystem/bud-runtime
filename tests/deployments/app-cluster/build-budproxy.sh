#!/bin/bash
set -e

echo "Building budproxy from source..."

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
REGISTRY_NAME="bud-registry"
REGISTRY_PORT="5111"
REGISTRY_HOST="localhost:${REGISTRY_PORT}"
IMAGE_NAME="budproxy"
IMAGE_TAG="latest"
FULL_IMAGE="${REGISTRY_HOST}/${IMAGE_NAME}:${IMAGE_TAG}"

# Paths
BUDPROXY_SOURCE_DIR="/home/budadmin/bud-runtime/.worktrees/testing-setup/services/budproxy"
DOCKERFILE_PATH="${BUDPROXY_SOURCE_DIR}/gateway/Dockerfile"

echo -e "${YELLOW}Building budproxy image...${NC}"
cd "${BUDPROXY_SOURCE_DIR}"

# Build the Docker image
docker build -f "${DOCKERFILE_PATH}" . -t "${IMAGE_NAME}:${IMAGE_TAG}"

echo -e "${YELLOW}Tagging image for local registry...${NC}"
docker tag "${IMAGE_NAME}:${IMAGE_TAG}" "${FULL_IMAGE}"

echo -e "${YELLOW}Pushing to local registry...${NC}"
docker push "${FULL_IMAGE}"

echo -e "${GREEN}Successfully built and pushed budproxy to ${FULL_IMAGE}${NC}"
echo -e "${GREEN}To use in Kubernetes, reference: k3d-${REGISTRY_NAME}:5000/${IMAGE_NAME}:${IMAGE_TAG}${NC}"

# Update the deployment to use the new image
echo -e "${YELLOW}Updating deployment to use new image...${NC}"
kubectl set image deployment/budproxy budproxy=k3d-${REGISTRY_NAME}:5000/${IMAGE_NAME}:${IMAGE_TAG} -n bud-system

# Restart the deployment to ensure fresh pull
echo -e "${YELLOW}Restarting budproxy deployment...${NC}"
kubectl rollout restart deployment/budproxy -n bud-system

# Wait for rollout to complete
echo -e "${YELLOW}Waiting for rollout to complete...${NC}"
kubectl rollout status deployment/budproxy -n bud-system

echo -e "${GREEN}Deployment successfully updated and restarted!${NC}"