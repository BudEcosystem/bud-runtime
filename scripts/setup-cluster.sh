#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

cat << "EOF"

______           _   _____                        _                 
| ___ \         | | |  ___|                      | |                
| |_/ /_   _  __| | | |__  ___ ___  ___ _   _ ___| |_ ___ _ __ ___  
| ___ \ | | |/ _` | |  __|/ __/ _ \/ __| | | / __| __/ _ \ '_ ` _ \ 
| |_/ / |_| | (_| | | |__| (_| (_) \__ \ |_| \__ \ ||  __/ | | | | |
\____/ \__,_|\__,_| \____/\___\___/|___/\__, |___/\__\___|_| |_| |_| inc
                                         __/ |                      
                                        |___/                                                                                                                                                                                                                                      
EOF

# Function to prompt for user confirmation
confirm() {
    while true; do
        read -p "$1 [y/n]: " yn
        case $yn in
            [Yy]* ) break;;
            [Nn]* ) echo "Aborting."; exit;;
            * ) echo "Please answer yes or no.";;
        esac
    done
}

# Function to check if a port is in use
check_port() {
    if sudo lsof -i:$1 &>/dev/null; then
        echo -e "\033[1;31mPort $1 is in use. Please free the port before proceeding.\033[0m"
        exit 1
    fi
}


# Check if any active Kubernetes or K3s service is running
if systemctl is-active --quiet k3s || systemctl is-active --quiet kubelet; then
    echo -e "\033[1;31mAn active Kubernetes or K3s service is already running. Please stop it before proceeding.\033[0m"
    exit 1
fi

# Check if ports 80, 443, and 6443 are occupied
# check_port 80
# check_port 443
# check_port 6443

# Get the directory where the script is located
SCRIPT_DIR=$(dirname "$(realpath "$0")")

# Prompt user for confirmation before updating system
confirm "This script will update your system packages. Do you want to continue?"




# Update system
echo "Updating system packages..."
sudo apt-get update -y
sudo apt-get upgrade -y

# Update system settings

# Define the entries to check/add
entries=(
"* soft nofile 1048576"
"* hard nofile 1048576"
)

# File to check
sysctl_conf="/etc/security/limits.conf"

# Loop through each entry and add it if it does not exist
for entry in "${entries[@]}"; do
    # Check if the entry exists in the file
    if ! grep -qF "$entry" "$sysctl_conf"; then
        echo "$entry" | sudo tee -a "$sysctl_conf" > /dev/null
        echo "Added: $entry"
    else
        echo "Exists: $entry"
    fi
done

# Function to determine maximum values based on system capabilities
calculate_max_values() {
    # fs.file-max: Typically, it's recommended to set this to a high value.
    file_max=$(( $(ulimit -n) * 2 ))  # For example, double the maximum number of open file descriptors
    
    # net.core.somaxconn: Maximum number of connections that can be queued for acceptance.
    somaxconn=65535  # Common maximum value
    
    # net.core.netdev_max_backlog: The maximum number of packets, queued on the INPUT side, when the interface receives packets faster than the kernel can process them.
    netdev_max_backlog=$(( $(getconf LONG_BIT) * 4096 ))  # Adjust based on system architecture (e.g., 64-bit system gets 262144)
    
    # net.core.rmem_max and net.core.wmem_max: Maximum receive and send buffer size.
    rmem_max=$(( $(getconf LONG_BIT) * 2097152 ))  # Example for 64-bit system
    wmem_max=$rmem_max  # Often set the same as rmem_max
    
    # net.ipv4.tcp_rmem and net.ipv4.tcp_wmem: TCP memory settings for receive and send buffers.
    tcp_rmem="4096 87380 $rmem_max"
    tcp_wmem="4096 65536 $wmem_max"
    
    # net.ipv4.tcp_max_syn_backlog: The maximum number of remembered connection requests, which have not yet received an acknowledgment from the connecting client.
    tcp_max_syn_backlog=$(( $(getconf LONG_BIT) * 1024 ))  # Example for 64-bit system
    
    # net.ipv4.ip_local_port_range: Range of ports to be used for outgoing connections.
    ip_local_port_range="1024 65535"  # Full range
    
    # vm.swappiness: Adjust how aggressively the kernel swaps memory pages.
    swappiness=10  # Common value for systems that prioritize performance
    
    # Disable IPv6 if not required
    disable_ipv6_all=1
    disable_ipv6_default=1
}

# Call the function to calculate max values
calculate_max_values

# Define the entries to check/add with dynamic max values
entries=(
"fs.file-max = $file_max"
"net.core.somaxconn = $somaxconn"
"net.core.netdev_max_backlog = $netdev_max_backlog"
"net.core.rmem_max = $rmem_max"
"net.core.wmem_max = $wmem_max"
"net.ipv4.tcp_rmem = $tcp_rmem"
"net.ipv4.tcp_wmem = $tcp_wmem"
"net.ipv4.tcp_max_syn_backlog = $tcp_max_syn_backlog"
"net.ipv4.ip_local_port_range = $ip_local_port_range"
"vm.swappiness = $swappiness"
"net.ipv6.conf.all.disable_ipv6 = $disable_ipv6_all"
"net.ipv6.conf.default.disable_ipv6 = $disable_ipv6_default"
)

# File to check
sysctl_conf="/etc/sysctl.conf"

# Loop through each entry and add it if it does not exist
for entry in "${entries[@]}"; do
    # Check if the entry exists in the file
    if ! grep -qF "$entry" "$sysctl_conf"; then
        echo "$entry" | sudo tee -a "$sysctl_conf" > /dev/null
        echo "Added: $entry"
    else
        echo "Exists: $entry"
    fi
done

# Apply the changes
sudo sysctl -p

# Kublet Args For Numa
# CUSTOM_KUBELET_ARGS=(
#   "feature-gates=MemoryManager=true"
#   "topology-manager-policy=single-numa-node"
#   "cpu-manager-policy=static"
#   "topology-manager-scope=pod"
#   "system-reserved=cpu=500m,memory=1Gi"
#   "kube-reserved=cpu=500m,memory=1Gi,ephemeral-storage=1Gi"
# )

# Construct the INSTALL_K3S_EXEC variable with custom kubelet arguments
# INSTALL_K3S_EXEC="server"
# for arg in "${CUSTOM_KUBELET_ARGS[@]}"; do
#   INSTALL_K3S_EXEC+=" --kubelet-arg=${arg}"
# done

# Install K3s
echo "Installing K3s..."
# export INSTALL_K3S_EXEC
curl -sfL https://get.k3s.io |  K3S_KUBECONFIG_MODE="644" sh -s -

# Verify K3s installation
echo "Verifying K3s installation..."
sudo systemctl stop k3s
echo 'if [ -f /var/lib/kubelet/cpu_manager_state ]; then
sudo rm /var/lib/kubelet/cpu_manager_state
sleep 10
fi' > check_cpu_manager_state.sh
sudo chmod +x check_cpu_manager_state.sh
sudo bash check_cpu_manager_state.sh
sudo rm check_cpu_manager_state.sh
sudo systemctl start k3s
sleep 10
sudo systemctl status k3s | grep "active (running)"

# Stop K3s, rotate logs, and clean up state files
echo "Stopping K3s, rotating logs, and cleaning up state files..."
sudo systemctl stop k3s
sudo journalctl --rotate
sudo journalctl --vacuum-time=1s
# if [ -f /var/lib/kubelet/cpu_manager_state ]; then
#   sudo rm /var/lib/kubelet/cpu_manager_state
# fi
# if [ -f /var/lib/kubelet/memory_manager_state ]; then
#   sudo rm /var/lib/kubelet/memory_manager_state
# fi

echo "Creating K3s configuration directory and file..."
sudo mkdir -p /etc/rancher/k3s
sudo tee /etc/rancher/k3s/config.yaml > /dev/null <<EOF
kubelet-arg:
  - "feature-gates=MemoryManager=true"
  - "topology-manager-policy=single-numa-node"
  - "cpu-manager-policy=static"
  - "topology-manager-scope=pod"
  - "system-reserved=cpu=500m,memory=1Gi"
  - "kube-reserved=cpu=500m,memory=1Gi,ephemeral-storage=1Gi"
EOF

# Restart K3s
echo "Restarting K3s..."
sudo systemctl stop k3s
echo 'if [ -f /var/lib/kubelet/cpu_manager_state ]; then
sudo rm /var/lib/kubelet/cpu_manager_state
sleep 10
fi' > check_cpu_manager_state.sh
sudo chmod +x check_cpu_manager_state.sh
sudo bash check_cpu_manager_state.sh
sudo rm check_cpu_manager_state.sh
sudo systemctl start k3s

# Create alias for kubectl
echo "Creating kubectl alias..."
alias kubectl='k3s kubectl '

# Verify node status
echo "Checking node status..."
kubectl get nodes

echo "Labeling Node for deployment"
NODES=$(kubectl get nodes --no-headers | wc -l)
if [ "$NODES" -ge 1 ]; then
    NODE_NAME=$(kubectl get nodes -o jsonpath='{.items[0].metadata.name}')
    echo "Labeling the node $NODE_NAME..."
    kubectl label nodes $NODE_NAME feature.node.kubernetes.io/numa-node=true
    echo -e "\033[1;32mNode $NODE_NAME labeled successfully.\033[0m"
else
    echo -e "\033[1;31mNo nodes found in the cluster.\033[0m"
    exit 1
fi

# Get node IP
NODE_IP=$(hostname -I | awk '{print $1}')

echo "K3s installation complete!"
# Provide information on how to use kubectl
echo -e "\033[1;32mTo use kubectl, run the following command:\033[0m"
echo -e "\033[1;33mexport KUBECONFIG=/etc/rancher/k3s/k3s.yaml\033[0m"
echo -e "\033[1;33malias kubectl='k3s kubectl'\033[0m"

echo "Installation script finished."
