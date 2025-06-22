#!/bin/bash
# Check which build tools are installed

# Ensure PATH includes system directories
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "=========================================="
echo "Checking Build Tools"
echo "=========================================="

# Function to check if command exists
check_tool() {
    local tool=$1
    local package=$2
    
    if command -v "$tool" &> /dev/null; then
        echo -e "${GREEN}✓ $tool: $(command -v $tool)${NC}"
        $tool --version 2>/dev/null | head -1 || echo "  Version info not available"
        return 0
    else
        echo -e "${RED}✗ $tool: NOT FOUND${NC}"
        if [ -n "$package" ]; then
            echo "  To install: sudo apt-get install $package"
        fi
        return 1
    fi
}

# Check essential build tools
echo -e "\n${YELLOW}Essential Build Tools:${NC}"
check_tool "make" "build-essential"
check_tool "gcc" "build-essential"
check_tool "g++" "build-essential"
check_tool "go" "Use ./scripts/install-go.sh"

# Check other useful tools
echo -e "\n${YELLOW}Other Useful Tools:${NC}"
check_tool "git" "git"
check_tool "curl" "curl"
check_tool "wget" "wget"
check_tool "jq" "jq"
check_tool "docker" "docker.io"
check_tool "kubectl" "Use ./scripts/install-tools.sh"
check_tool "helm" "Use ./scripts/install-tools.sh"

# Check if we can use sudo
echo -e "\n${YELLOW}System Access:${NC}"
if command -v sudo &> /dev/null; then
    echo -e "${GREEN}✓ sudo: available${NC}"
else
    echo -e "${RED}✗ sudo: NOT AVAILABLE${NC}"
    echo "  You may need to run commands as root or contact your administrator"
fi

# Summary
echo -e "\n${YELLOW}Summary:${NC}"
echo "This script shows which tools are installed and which are missing."
echo "For AIBrix building, you need: make, gcc, g++, and go"