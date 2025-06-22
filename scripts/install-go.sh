#!/bin/bash
# Install Go for building AIBrix

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

GO_VERSION="1.22.0"

echo "=========================================="
echo "Installing Go ${GO_VERSION}"
echo "=========================================="

# Check if Go is already installed
if command -v go &> /dev/null; then
    CURRENT_VERSION=$(go version | awk '{print $3}')
    echo -e "${GREEN}✓ Go is already installed: ${CURRENT_VERSION}${NC}"
    exit 0
fi

# Download Go
echo -e "${YELLOW}Downloading Go ${GO_VERSION}...${NC}"
wget -q "https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz"

# Install Go
echo -e "${YELLOW}Installing Go...${NC}"
sudo tar -C /usr/local -xzf "go${GO_VERSION}.linux-amd64.tar.gz"
rm "go${GO_VERSION}.linux-amd64.tar.gz"

# Add Go to PATH
echo -e "${YELLOW}Configuring PATH...${NC}"
echo 'export PATH=$PATH:/usr/local/go/bin' >> ~/.bashrc
echo 'export PATH=$PATH:$HOME/go/bin' >> ~/.bashrc

# Also add to current session
export PATH=$PATH:/usr/local/go/bin
export PATH=$PATH:$HOME/go/bin

echo -e "${GREEN}✓ Go ${GO_VERSION} installed successfully!${NC}"
echo ""
echo "Go has been installed to /usr/local/go"
echo ""
echo "To use Go in the current terminal session, run:"
echo "  export PATH=\$PATH:/usr/local/go/bin"
echo ""
echo "Or start a new terminal session."
echo ""
go version 2>/dev/null || echo "Run the export command above to use Go immediately."