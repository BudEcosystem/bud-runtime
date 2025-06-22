#!/bin/bash
# Install required tools for multi-cluster setup

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running with sufficient privileges
check_privileges() {
    if [[ $EUID -ne 0 ]] && ! groups | grep -q docker; then
        log_warn "This script needs to be run with sudo or by a user in the docker group"
        log_info "You may need to run: sudo $0"
    fi
}

# Install Docker
install_docker() {
    log_info "Installing Docker..."
    
    if command -v docker &> /dev/null; then
        log_info "Docker is already installed"
        docker --version
        return
    fi
    
    # Update package index
    sudo apt-get update
    
    # Install prerequisites
    sudo apt-get install -y \
        apt-transport-https \
        ca-certificates \
        curl \
        gnupg \
        lsb-release
    
    # Add Docker's official GPG key
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
    
    # Set up stable repository
    echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
        $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    # Install Docker Engine
    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
    
    # Add current user to docker group
    sudo usermod -aG docker $USER
    
    log_info "Docker installed successfully"
    log_warn "You may need to log out and back in for group changes to take effect"
}

# Install kubectl
install_kubectl() {
    log_info "Installing kubectl..."
    
    if command -v kubectl &> /dev/null; then
        log_info "kubectl is already installed"
        kubectl version --client --short
        return
    fi
    
    # Download latest stable kubectl
    curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
    
    # Validate binary
    curl -LO "https://dl.k8s.io/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl.sha256"
    echo "$(cat kubectl.sha256)  kubectl" | sha256sum --check
    
    # Install kubectl
    sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
    
    # Clean up
    rm kubectl kubectl.sha256
    
    log_info "kubectl installed successfully"
}

# Install k3d
install_k3d() {
    log_info "Installing k3d..."
    
    if command -v k3d &> /dev/null; then
        log_info "k3d is already installed"
        k3d version
        return
    fi
    
    # Install k3d using the official script
    curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash
    
    log_info "k3d installed successfully"
}

# Install Helm
install_helm() {
    log_info "Installing Helm..."
    
    if command -v helm &> /dev/null; then
        log_info "Helm is already installed"
        helm version --short
        return
    fi
    
    # Download Helm installation script
    curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3
    chmod 700 get_helm.sh
    ./get_helm.sh
    rm get_helm.sh
    
    log_info "Helm installed successfully"
}

# Install k6 (optional, for performance testing)
install_k6() {
    log_info "Installing k6 (optional - for performance testing)..."
    
    if command -v k6 &> /dev/null; then
        log_info "k6 is already installed"
        k6 version
        return
    fi
    
    # Add k6 repository
    sudo gpg -k
    sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
    echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
    
    # Install k6
    sudo apt-get update
    sudo apt-get install -y k6
    
    log_info "k6 installed successfully"
}

# Install Python dependencies
install_python_deps() {
    log_info "Installing Python dependencies..."
    
    # Ensure pip is installed
    if ! command -v pip3 &> /dev/null; then
        sudo apt-get update
        sudo apt-get install -y python3-pip
    fi
    
    # Install test requirements if file exists
    if [[ -f "tests/requirements-test.txt" ]]; then
        log_info "Installing Python test requirements..."
        pip3 install --user -r tests/requirements-test.txt
    else
        log_warn "tests/requirements-test.txt not found, skipping Python dependencies"
    fi
}

# Verify installations
verify_installations() {
    log_info "Verifying installations..."
    echo ""
    
    tools=("docker" "kubectl" "k3d" "helm")
    all_installed=true
    
    for tool in "${tools[@]}"; do
        if command -v $tool &> /dev/null; then
            echo -e "${GREEN}✓${NC} $tool: $(command -v $tool)"
            $tool version --short 2>/dev/null || $tool version 2>/dev/null || true
        else
            echo -e "${RED}✗${NC} $tool: not found"
            all_installed=false
        fi
        echo ""
    done
    
    if $all_installed; then
        log_info "All required tools are installed!"
    else
        log_error "Some tools are missing. Please check the installation logs above."
        return 1
    fi
}

# Main installation
main() {
    echo "================================"
    echo "Installing Multi-Cluster Tools"
    echo "================================"
    echo ""
    
    check_privileges
    
    # Check OS
    if [[ ! -f /etc/os-release ]]; then
        log_error "Cannot determine OS. This script is designed for Ubuntu/Debian."
        exit 1
    fi
    
    source /etc/os-release
    if [[ "$ID" != "ubuntu" ]] && [[ "$ID" != "debian" ]]; then
        log_warn "This script is designed for Ubuntu/Debian. It may not work on $ID."
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    
    # Install tools
    install_docker
    install_kubectl
    install_k3d
    install_helm
    
    # Optional tools
    read -p "Install optional k6 for performance testing? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        install_k6
    fi
    
    # Python dependencies
    install_python_deps
    
    # Verify
    echo ""
    verify_installations
    
    echo ""
    log_info "Installation complete!"
    log_info "Next steps:"
    echo "  1. If you were added to the docker group, log out and back in"
    echo "  2. Run: ./scripts/multi-cluster/setup-multi-cluster.sh create"
    echo "  3. Deploy services with Helm"
    echo "  4. Run tests: ./tests/e2e/run_tests.py --scenario smoke"
}

# Run main
main "$@"