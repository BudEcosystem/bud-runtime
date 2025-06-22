#!/bin/bash
# Build AIBrix from source and deploy to inference cluster

set -e

# Hard-coded paths to avoid shell issues
AIBRIX_DIR="/home/budadmin/bud-runtime/.worktrees/testing-setup/services/aibrix"
SCRIPT_DIR="/home/budadmin/bud-runtime/.worktrees/testing-setup/tests/deployments/inference-cluster"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "=========================================="
echo "Building AIBrix from Source"
echo "=========================================="

# Check requirements
echo -e "${YELLOW}Checking requirements...${NC}"

# Check Go
if ! command -v go &> /dev/null; then
    # Check if Go is installed but not in PATH
    if [ -x "/usr/local/go/bin/go" ]; then
        echo -e "${YELLOW}Go is installed but not in PATH${NC}"
        echo "Adding Go to PATH for this session..."
        export PATH=$PATH:/usr/local/go/bin
        if go version &> /dev/null; then
            echo -e "${GREEN}✓ Go: $(go version)${NC}"
        else
            echo -e "${RED}Error: Could not run Go${NC}"
            exit 1
        fi
    else
        echo -e "${RED}Error: Go is not installed${NC}"
        echo "Please install Go first:"
        echo "  1. Run: ./scripts/install-go.sh"
        echo "  2. Run: export PATH=\$PATH:/usr/local/go/bin"
        exit 1
    fi
else
    echo -e "${GREEN}✓ Go: $(go version)${NC}"
fi

# Check make
if ! make --version &> /dev/null; then
    echo -e "${RED}Error: make is not installed${NC}"
    echo "Installing make..."
    sudo apt-get update && sudo apt-get install -y build-essential
fi
echo -e "${GREEN}✓ Make: found${NC}"

# Check Docker
if ! docker version &> /dev/null; then
    echo -e "${RED}Error: Docker is not running${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Docker: running${NC}"

# Check AIBrix directory
if [ ! -d "$AIBRIX_DIR" ]; then
    echo -e "${RED}Error: AIBrix directory not found at $AIBRIX_DIR${NC}"
    exit 1
fi
echo -e "${GREEN}✓ AIBrix source: found${NC}"

# Change to AIBrix directory
cd "$AIBRIX_DIR"
echo -e "\n${YELLOW}Working directory: $(pwd)${NC}"

# Set registry
REGISTRY="localhost:5111"
NAMESPACE="${REGISTRY}/aibrix"

echo -e "\n${YELLOW}Building AIBrix components...${NC}"
echo "Registry: $NAMESPACE"

# Build images
echo -e "\n${YELLOW}Running: make docker-build-all${NC}"
make docker-build-all AIBRIX_CONTAINER_REGISTRY_NAMESPACE="${NAMESPACE}"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Build successful${NC}"
else
    echo -e "${RED}✗ Build failed${NC}"
    exit 1
fi

# Push images
echo -e "\n${YELLOW}Pushing images to registry...${NC}"
make docker-push-all AIBRIX_CONTAINER_REGISTRY_NAMESPACE="${NAMESPACE}"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Push successful${NC}"
else
    echo -e "${RED}✗ Push failed${NC}"
    exit 1
fi

# Get git commit hash
GIT_HASH=$(git rev-parse HEAD)
echo -e "\n${YELLOW}Git commit: ${GIT_HASH}${NC}"

# Generate deployment manifest
echo -e "\n${YELLOW}Generating deployment manifest...${NC}"

# Use internal registry name for k8s pods
K8S_REGISTRY="k3d-bud-registry:5000/aibrix"

cat > "$SCRIPT_DIR/aibrix-local.yaml" << EOF
# AIBrix Deployment from Local Build
# Built from commit: ${GIT_HASH}
---
apiVersion: v1
kind: Namespace
metadata:
  name: aibrix-system
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: aibrix-controller-manager
  namespace: aibrix-system
spec:
  replicas: 1
  selector:
    matchLabels:
      app: aibrix-controller-manager
  template:
    metadata:
      labels:
        app: aibrix-controller-manager
    spec:
      containers:
      - name: manager
        image: ${K8S_REGISTRY}/controller-manager:${GIT_HASH}
        imagePullPolicy: Always
        ports:
        - containerPort: 8080
          name: metrics
        - containerPort: 9443
          name: webhook
        resources:
          limits:
            cpu: 500m
            memory: 512Mi
          requests:
            cpu: 100m
            memory: 128Mi
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: aibrix-gateway-plugins
  namespace: aibrix-system
spec:
  replicas: 1
  selector:
    matchLabels:
      app: aibrix-gateway-plugins
  template:
    metadata:
      labels:
        app: aibrix-gateway-plugins
    spec:
      containers:
      - name: plugins
        image: ${K8S_REGISTRY}/gateway-plugins:${GIT_HASH}
        imagePullPolicy: Always
        ports:
        - containerPort: 50051
          name: grpc
        env:
        - name: REDIS_HOST
          value: "redis-master"
        - name: REDIS_PORT
          value: "6379"
        resources:
          limits:
            cpu: 200m
            memory: 256Mi
          requests:
            cpu: 50m
            memory: 64Mi
---
apiVersion: v1
kind: Service
metadata:
  name: aibrix-controller-manager
  namespace: aibrix-system
spec:
  selector:
    app: aibrix-controller-manager
  ports:
  - name: metrics
    port: 8080
    targetPort: 8080
  - name: webhook
    port: 9443
    targetPort: 9443
---
apiVersion: v1
kind: Service
metadata:
  name: aibrix-gateway-plugins
  namespace: aibrix-system
spec:
  selector:
    app: aibrix-gateway-plugins
  ports:
  - name: grpc
    port: 50051
    targetPort: 50051
EOF

echo -e "${GREEN}✓ Deployment manifest created${NC}"

# Deploy to cluster
echo -e "\n${YELLOW}Deploying to inference cluster...${NC}"
kubectl config use-context k3d-bud-inference

# Install dependencies
echo -e "\n${YELLOW}Installing AIBrix dependencies...${NC}"
kubectl apply -k "$AIBRIX_DIR/config/dependency" --server-side || true

# Deploy Redis first
echo -e "\n${YELLOW}Deploying Redis for AIBrix...${NC}"
kubectl apply -f "$AIBRIX_DIR/config/metadata/redis.yaml" || true

# Apply deployment
echo -e "\n${YELLOW}Applying AIBrix deployment...${NC}"
kubectl apply -f "$SCRIPT_DIR/aibrix-local.yaml"

# Wait for pods
echo -e "\n${YELLOW}Waiting for pods to be ready...${NC}"
kubectl wait --for=condition=ready pod -l app=aibrix-controller-manager -n aibrix-system --timeout=120s || true
kubectl wait --for=condition=ready pod -l app=aibrix-gateway-plugins -n aibrix-system --timeout=120s || true

# Show status
echo -e "\n${GREEN}Deployment Status:${NC}"
kubectl get pods -n aibrix-system
kubectl get svc -n aibrix-system

echo -e "\n${GREEN}✓ AIBrix built and deployed!${NC}"
echo ""
echo "To view logs:"
echo "  kubectl logs -n aibrix-system -l app=aibrix-controller-manager"
echo "  kubectl logs -n aibrix-system -l app=aibrix-gateway-plugins"