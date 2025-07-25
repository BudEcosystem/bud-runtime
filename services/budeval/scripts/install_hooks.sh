# Function to check if NVM is installed
check_nvm_installed() {
    if command -v nvm >/dev/null 2>&1; then
        echo "NVM is already installed."
        return 0
    else
        return 1
    fi
}

# Function to check if a specific Node.js version is installed
check_node_version_installed() {
    local version=$1
    if nvm ls "$version" >/dev/null 2>&1; then
        echo "Node.js $version is already installed."
        return 0
    else
        return 1
    fi
}

# Function to install NVM if it's not installed
install_nvm() {
    echo "Installing NVM..."
    # Install node version manager(https://github.com/nvm-sh/nvm)
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.0/install.sh | bash

    # Source NVM to use it immediately in the same session
    export NVM_DIR="$([ -z "${XDG_CONFIG_HOME-}" ] && printf %s "${HOME}/.nvm" || printf %s "${XDG_CONFIG_HOME}/nvm")"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh" # This loads nvm
}

# Function to install Node.js if the specified version is not installed
install_node_version() {
    local version=$1
    echo "Installing Node.js $version..."
    nvm install "$version"
}

# Install nvm if not found
if check_nvm_installed; then
    echo "Skipping NVM installation."
else
    install_nvm
fi

# Verify nvm installation
command -v nvm

# Check and install the required Node.js version
NODE_VERSION="v20.16.0"
if ! check_node_version_installed "$NODE_VERSION"; then
    install_node_version "$NODE_VERSION"
else
    echo "Skipping Node.js $NODE_VERSION installation."
fi

# Install pre commit hooks assuming the python env is activated
pip install -r requirements-dev.txt
pre-commit install
pre-commit install --hook-type commit-msg

# Re-load the shell
#exec "$SHELL" -l