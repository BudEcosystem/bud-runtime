#!/bin/bash

# Install pre-commit hooks for the entire bud-stack project
# This script sets up pre-commit hooks for all service types (Python, Rust, TypeScript)

set -e

echo "Installing pre-commit hooks for bud-stack..."

# Check if we're in the root directory
if [[ ! -f "CLAUDE.md" ]]; then
    echo "Error: This script must be run from the bud-stack root directory"
    exit 1
fi

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Install pre-commit if not available
if ! command_exists pre-commit; then
    echo "Installing pre-commit..."
    if command_exists pip; then
        pip install pre-commit
    elif command_exists pip3; then
        pip3 install pre-commit
    else
        echo "Error: pip not found. Please install Python and pip first."
        exit 1
    fi
fi

# Install pip-audit for security checks (optional)
if command_exists pip; then
    pip install pip-audit 2>/dev/null || echo "Note: pip-audit installation failed, security checks will be skipped"
fi

# Install the pre-commit hooks
echo "Installing pre-commit hooks..."
pre-commit install

# Install commit-msg hook for conventional commits
echo "Installing commit-msg hook..."
pre-commit install --hook-type commit-msg

# Install dependencies for Node.js services
echo "Installing Node.js dependencies for frontend services..."

# Install dependencies for budadmin
if [[ -d "services/budadmin" && -f "services/budadmin/package.json" ]]; then
    echo "Installing dependencies for budadmin..."
    cd services/budadmin
    if command_exists npm; then
        npm install
    else
        echo "Warning: npm not found, skipping budadmin dependency installation"
    fi
    cd ../..
fi

# Install dependencies for budplayground
if [[ -d "services/budplayground" && -f "services/budplayground/package.json" ]]; then
    echo "Installing dependencies for budplayground..."
    cd services/budplayground
    if command_exists npm; then
        npm install
    else
        echo "Warning: npm not found, skipping budplayground dependency installation"
    fi
    cd ../..
fi

# Install dependencies for budCustomer
if [[ -d "services/budCustomer" && -f "services/budCustomer/package.json" ]]; then
    echo "Installing dependencies for budCustomer..."
    cd services/budCustomer
    if command_exists npm; then
        npm install
    else
        echo "Warning: npm not found, skipping budCustomer dependency installation"
    fi
    cd ../..
fi

# Check if Rust is available for budgateway
if [[ -d "services/budgateway" ]]; then
    if ! command_exists cargo; then
        echo "Warning: Rust/Cargo not found. Rust formatting and linting will be skipped for budgateway."
        echo "Install Rust from https://rustup.rs/ to enable Rust pre-commit hooks."
    else
        echo "Rust found, budgateway hooks will work correctly."
    fi
fi

echo ""
echo "✅ Pre-commit hooks installed successfully!"
echo ""
echo "The following hooks are now active:"
echo "  - General file checks (large files, merge conflicts, etc.)"
echo "  - Python linting and formatting (Ruff) for all Python services"
echo "  - Rust formatting and linting (Cargo) for budgateway"
echo "  - TypeScript/JavaScript linting for budadmin and budplayground"
echo "  - Conventional commit message validation"
echo "  - Python security scanning (if pip-audit is available)"
echo ""
echo "You can run hooks manually with:"
echo "  pre-commit run --all-files"
echo ""
echo "To bypass hooks temporarily (not recommended):"
echo "  git commit --no-verify"
