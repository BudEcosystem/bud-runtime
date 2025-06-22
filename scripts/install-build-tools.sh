#!/bin/bash
# Install build tools required for compiling software

set -e

# Ensure PATH includes system directories
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "=========================================="
echo "Installing Build Tools"
echo "=========================================="

# Update package list
echo -e "${YELLOW}Updating package list...${NC}"
sudo apt-get update

# Install build-essential (includes make, gcc, g++, etc.)
echo -e "${YELLOW}Installing build-essential...${NC}"
sudo apt-get install -y build-essential

# Install additional useful build tools
echo -e "${YELLOW}Installing additional build tools...${NC}"
sudo apt-get install -y \
    git \
    curl \
    wget \
    jq \
    zip \
    unzip

echo -e "${GREEN}✓ Build tools installed successfully!${NC}"
echo ""
echo "Installed tools:"
echo "  - make: $(make --version | head -1)"
echo "  - gcc: $(gcc --version | head -1)"
echo "  - git: $(git --version)"
echo "  - curl: $(curl --version | head -1)"
echo "  - jq: $(jq --version)"