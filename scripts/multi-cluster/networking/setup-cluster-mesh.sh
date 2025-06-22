#!/bin/bash
# setup-cluster-mesh.sh - Setup cross-cluster networking between application and inference clusters

set -euo pipefail

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../utils/common.sh"

# Default values
CLUSTER1="${CLUSTER1:-bud-app}"
CLUSTER2="${CLUSTER2:-bud-inference}"
NETWORKING_SOLUTION="${NETWORKING_SOLUTION:-submariner}"  # Options: submariner, cilium
BROKER_NS="submariner-k8s-broker"
SUBMARINER_VERSION="${SUBMARINER_VERSION:-0.16.2}"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --cluster1)
            CLUSTER1="$2"
            shift 2
            ;;
        --cluster2)
            CLUSTER2="$2"
            shift 2
            ;;
        --networking-solution)
            NETWORKING_SOLUTION="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  --cluster1 NAME              First cluster name (default: $CLUSTER1)"
            echo "  --cluster2 NAME              Second cluster name (default: $CLUSTER2)"
            echo "  --networking-solution TYPE   Networking solution: submariner|cilium (default: $NETWORKING_SOLUTION)"
            echo "  --help                       Show this help message"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Function to install subctl CLI tool
install_subctl() {
    if command_exists subctl; then
        log_info "subctl is already installed"
        return 0
    fi
    
    log_info "Installing subctl CLI tool..."
    
    local SUBCTL_VERSION="0.16.2"
    local OS=$(uname -s | tr '[:upper:]' '[:lower:]')
    local ARCH=$(uname -m)
    
    if [ "$ARCH" = "x86_64" ]; then
        ARCH="amd64"
    fi
    
    curl -Ls https://get.submariner.io | VERSION=v${SUBCTL_VERSION} bash
    
    # Add to PATH if not already there
    if ! command_exists subctl; then
        export PATH=$PATH:~/.local/bin
    fi
    
    if command_exists subctl; then
        log_success "subctl installed successfully"
        subctl version
    else
        log_error "Failed to install subctl"
        return 1
    fi
}

# Function to setup Submariner cross-cluster networking
setup_submariner_networking() {
    log_info "Setting up Submariner cross-cluster networking..."
    
    # Install subctl
    install_subctl || return 1
    
    # Deploy broker on cluster1
    log_info "Deploying Submariner broker on cluster $CLUSTER1..."
    subctl deploy-broker \
        --kubeconfig "$HOME/.kube/config" \
        --context "k3d-$CLUSTER1" \
        --globalnet
    
    # Join cluster1 to the broker
    log_info "Joining cluster $CLUSTER1 to Submariner broker..."
    subctl join \
        --kubeconfig "$HOME/.kube/config" \
        --context "k3d-$CLUSTER1" \
        broker-info.subm \
        --clusterid "$CLUSTER1" \
        --cable-driver vxlan \
        --natt=false
    
    # Join cluster2 to the broker
    log_info "Joining cluster $CLUSTER2 to Submariner broker..."
    subctl join \
        --kubeconfig "$HOME/.kube/config" \
        --context "k3d-$CLUSTER2" \
        broker-info.subm \
        --clusterid "$CLUSTER2" \
        --cable-driver vxlan \
        --natt=false
    
    # Wait for submariner to be ready
    log_info "Waiting for Submariner to be ready..."
    sleep 30
    
    # Verify connectivity
    log_info "Verifying cross-cluster connectivity..."
    subctl verify \
        --kubeconfig "$HOME/.kube/config" \
        --context "k3d-$CLUSTER1" \
        --tocontext "k3d-$CLUSTER2" \
        --only connectivity \
        --verbose
    
    # Export services for cross-cluster discovery
    setup_service_exports
    
    log_success "Submariner cross-cluster networking setup completed"
}

# Function to setup basic cross-cluster networking using NodePort services
setup_basic_networking() {
    log_info "Setting up basic cross-cluster networking using NodePort services..."
    
    # Get cluster node IPs
    local cluster1_ip=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' k3d-$CLUSTER1-server-0)
    local cluster2_ip=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' k3d-$CLUSTER2-server-0)
    
    log_info "Cluster 1 ($CLUSTER1) IP: $cluster1_ip"
    log_info "Cluster 2 ($CLUSTER2) IP: $cluster2_ip"
    
    # Create cross-cluster service configurations
    CONFIG_DIR="$SCRIPT_DIR/../../../configs/networking"
    mkdir -p "$CONFIG_DIR"
    
    # Create ConfigMap with cluster endpoints
    cat > "$CONFIG_DIR/cluster-endpoints.yaml" <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: cluster-endpoints
  namespace: default
data:
  app-cluster-ip: "$cluster1_ip"
  inference-cluster-ip: "$cluster2_ip"
  app-cluster-name: "$CLUSTER1"
  inference-cluster-name: "$CLUSTER2"
---
apiVersion: v1
kind: Service
metadata:
  name: cross-cluster-discovery
  namespace: default
spec:
  type: NodePort
  ports:
  - port: 8080
    targetPort: 8080
    nodePort: 30080
    name: http
  selector:
    app: cross-cluster-proxy
EOF
    
    # Apply to both clusters
    kubectl --context="k3d-$CLUSTER1" apply -f "$CONFIG_DIR/cluster-endpoints.yaml"
    kubectl --context="k3d-$CLUSTER2" apply -f "$CONFIG_DIR/cluster-endpoints.yaml"
    
    # Create network policies for cross-cluster communication
    cat > "$CONFIG_DIR/cross-cluster-network-policy.yaml" <<EOF
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-cross-cluster
  namespace: default
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector: {}
  egress:
  - to:
    - namespaceSelector: {}
  - to:
    - podSelector: {}
  - ports:
    - protocol: TCP
      port: 53
    - protocol: UDP
      port: 53
EOF
    
    kubectl --context="k3d-$CLUSTER1" apply -f "$CONFIG_DIR/cross-cluster-network-policy.yaml"
    kubectl --context="k3d-$CLUSTER2" apply -f "$CONFIG_DIR/cross-cluster-network-policy.yaml"
    
    log_success "Basic cross-cluster networking configured"
}

# Function to setup service exports for cross-cluster discovery
setup_service_exports() {
    log_info "Setting up service exports for cross-cluster discovery..."
    
    # Create namespace for cross-cluster services if not exists
    create_namespace_if_not_exists "cross-cluster" "k3d-$CLUSTER1"
    create_namespace_if_not_exists "cross-cluster" "k3d-$CLUSTER2"
    
    # Export BudProxy service from app cluster
    cat <<EOF | kubectl --context="k3d-$CLUSTER1" apply -f -
apiVersion: v1
kind: Service
metadata:
  name: budproxy-cross-cluster
  namespace: bud-system
  labels:
    app: budproxy
    cross-cluster: "true"
spec:
  type: ClusterIP
  ports:
  - port: 8000
    targetPort: 8000
    name: http
  - port: 50051
    targetPort: 50051
    name: grpc
  selector:
    app: budproxy
EOF
    
    # Export AIBrix service from inference cluster
    cat <<EOF | kubectl --context="k3d-$CLUSTER2" apply -f -
apiVersion: v1
kind: Service
metadata:
  name: aibrix-cross-cluster
  namespace: aibrix-system
  labels:
    app: aibrix
    cross-cluster: "true"
spec:
  type: ClusterIP
  ports:
  - port: 8080
    targetPort: 8080
    name: http
  - port: 9090
    targetPort: 9090
    name: metrics
  selector:
    app: aibrix
---
apiVersion: v1
kind: Service
metadata:
  name: vllm-cross-cluster
  namespace: vllm-system
  labels:
    app: vllm
    cross-cluster: "true"
spec:
  type: ClusterIP
  ports:
  - port: 8000
    targetPort: 8000
    name: http
  selector:
    app: vllm
EOF
    
    log_success "Service exports configured"
}

# Function to create test pods for connectivity verification
create_test_pods() {
    log_info "Creating test pods for connectivity verification..."
    
    # Create test pod in cluster1
    cat <<EOF | kubectl --context="k3d-$CLUSTER1" apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: netshoot-test
  namespace: default
spec:
  containers:
  - name: netshoot
    image: nicolaka/netshoot
    command: ["sleep", "3600"]
EOF
    
    # Create test pod in cluster2
    cat <<EOF | kubectl --context="k3d-$CLUSTER2" apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: netshoot-test
  namespace: default
spec:
  containers:
  - name: netshoot
    image: nicolaka/netshoot
    command: ["sleep", "3600"]
EOF
    
    log_info "Waiting for test pods to be ready..."
    kubectl --context="k3d-$CLUSTER1" wait --for=condition=ready pod/netshoot-test -n default --timeout=60s
    kubectl --context="k3d-$CLUSTER2" wait --for=condition=ready pod/netshoot-test -n default --timeout=60s
    
    log_success "Test pods created successfully"
}

# Function to verify cross-cluster connectivity
verify_connectivity() {
    log_info "Verifying cross-cluster connectivity..."
    
    # Get pod IPs
    local pod1_ip=$(kubectl --context="k3d-$CLUSTER1" get pod netshoot-test -n default -o jsonpath='{.status.podIP}')
    local pod2_ip=$(kubectl --context="k3d-$CLUSTER2" get pod netshoot-test -n default -o jsonpath='{.status.podIP}')
    
    log_info "Testing connectivity from cluster $CLUSTER1 to cluster $CLUSTER2..."
    
    # For basic networking, we'll test node connectivity
    if [[ "$NETWORKING_SOLUTION" == "basic" ]]; then
        local cluster2_node_ip=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' k3d-$CLUSTER2-server-0)
        kubectl --context="k3d-$CLUSTER1" exec -n default netshoot-test -- ping -c 3 $cluster2_node_ip || log_warning "Direct connectivity test failed (this is expected with basic networking)"
    fi
    
    # Clean up test pods
    kubectl --context="k3d-$CLUSTER1" delete pod netshoot-test -n default --ignore-not-found=true
    kubectl --context="k3d-$CLUSTER2" delete pod netshoot-test -n default --ignore-not-found=true
    
    log_success "Connectivity verification completed"
}

# Function to save networking configuration
save_networking_config() {
    CONFIG_DIR="$SCRIPT_DIR/../../../configs/networking"
    mkdir -p "$CONFIG_DIR"
    
    cat > "$CONFIG_DIR/networking-info.yaml" <<EOF
# Cross-Cluster Networking Configuration
networking:
  solution: $NETWORKING_SOLUTION
  clusters:
    - name: $CLUSTER1
      type: application
      context: k3d-$CLUSTER1
    - name: $CLUSTER2
      type: inference
      context: k3d-$CLUSTER2
  
services:
  budproxy:
    cluster: $CLUSTER1
    namespace: bud-system
    ports:
      http: 8000
      grpc: 50051
  aibrix:
    cluster: $CLUSTER2
    namespace: aibrix-system
    ports:
      http: 8080
      metrics: 9090
  vllm:
    cluster: $CLUSTER2
    namespace: vllm-system
    ports:
      http: 8000

$(if [[ "$NETWORKING_SOLUTION" == "submariner" ]]; then
    echo "submariner:"
    echo "  version: $SUBMARINER_VERSION"
    echo "  broker_namespace: $BROKER_NS"
    echo "  cable_driver: vxlan"
    echo "  globalnet: enabled"
fi)
EOF
    
    log_success "Networking configuration saved to $CONFIG_DIR/networking-info.yaml"
}

# Main function
main() {
    log_info "Setting up cross-cluster networking between '$CLUSTER1' and '$CLUSTER2'..."
    
    # Verify clusters exist
    if ! k3d cluster list | grep -q "^$CLUSTER1"; then
        log_error "Cluster '$CLUSTER1' not found"
        exit 1
    fi
    
    if ! k3d cluster list | grep -q "^$CLUSTER2"; then
        log_error "Cluster '$CLUSTER2' not found"
        exit 1
    fi
    
    # Setup networking based on solution
    case "$NETWORKING_SOLUTION" in
        "submariner")
            setup_submariner_networking
            ;;
        "basic"|"nodeport")
            setup_basic_networking
            ;;
        *)
            log_error "Unknown networking solution: $NETWORKING_SOLUTION"
            exit 1
            ;;
    esac
    
    # Create test pods and verify connectivity
    create_test_pods
    verify_connectivity
    
    # Save configuration
    save_networking_config
    
    log_success "Cross-cluster networking setup completed!"
    log_info "Networking solution: $NETWORKING_SOLUTION"
    log_info "Connected clusters: $CLUSTER1 <-> $CLUSTER2"
}

# Run main function
main