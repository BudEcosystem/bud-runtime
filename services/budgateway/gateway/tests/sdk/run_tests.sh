#!/bin/bash

# Universal test runner for TensorZero SDK tests
# Supports multiple providers and test modes

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
PROVIDER="all"
MODE="ci"
CONFIG_SUFFIX=""
PORT=3001

# Function to display usage
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --provider PROVIDER   Provider to test (openai, anthropic, together, fireworks, azure, all, universal) [default: all]"
    echo "  --mode MODE          Test mode (ci, full) [default: ci]"
    echo "  --port PORT          Gateway port [default: 3001]"
    echo "  --compare            Run comparison tests (full mode only)"
    echo "  --demo               Run the universal SDK demonstration"
    echo "  -h, --help           Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                           # Run all CI tests"
    echo "  $0 --provider openai --mode full  # Run full OpenAI tests"
    echo "  $0 --provider anthropic           # Run Anthropic CI tests"
    echo "  $0 --provider fireworks           # Run Fireworks CI tests"
    echo "  $0 --provider azure               # Run Azure CI tests"
    echo "  $0 --provider universal           # Run universal SDK compatibility tests"
    echo "  $0 --demo                         # Run interactive SDK architecture demo"
    exit 0
}

# Parse command line arguments
COMPARE=false
DEMO=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --provider)
            PROVIDER="$2"
            shift 2
            ;;
        --mode)
            MODE="$2"
            shift 2
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        --compare)
            COMPARE=true
            shift
            ;;
        --demo)
            DEMO=true
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            usage
            ;;
    esac
done

# Validate inputs
if [[ ! "$PROVIDER" =~ ^(openai|anthropic|together|fireworks|azure|all|universal)$ ]]; then
    echo -e "${RED}Error: Invalid provider '$PROVIDER'. Must be openai, anthropic, together, fireworks, azure, all, or universal.${NC}"
    exit 1
fi

if [[ ! "$MODE" =~ ^(ci|full)$ ]]; then
    echo -e "${RED}Error: Invalid mode '$MODE'. Must be ci or full.${NC}"
    exit 1
fi

# Set config suffix and unified config for CI mode
if [ "$MODE" == "ci" ]; then
    CONFIG_SUFFIX="_ci"
    UNIFIED_CONFIG="test_config_unified_ci.toml"
else
    UNIFIED_CONFIG=""
fi

echo -e "${BLUE}TensorZero SDK Tests${NC}"
echo -e "${BLUE}=====================${NC}"
echo -e "Provider: ${YELLOW}$PROVIDER${NC}"
echo -e "Mode: ${YELLOW}$MODE${NC}"
echo -e "Port: ${YELLOW}$PORT${NC}"
echo ""

# Check if virtual environment exists
if [ -d ".venv" ]; then
    VENV_DIR=".venv"
elif [ -d "venv" ]; then
    VENV_DIR="venv"
else
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv .venv
    VENV_DIR=".venv"
fi

# Activate virtual environment
source ${VENV_DIR}/bin/activate

# Install dependencies
echo -e "${YELLOW}Installing dependencies...${NC}"
pip install -q -r requirements.txt

# Set environment variables based on mode
export TENSORZERO_BASE_URL="http://localhost:$PORT"

if [ "$MODE" == "ci" ]; then
    # CI mode - use dummy keys
    export TENSORZERO_API_KEY="test-api-key"
    export OPENAI_API_KEY="dummy-key"
    export ANTHROPIC_API_KEY="dummy-key"
    export TOGETHER_API_KEY="dummy-key"
    export AZURE_OPENAI_API_KEY="dummy-key"
else
    # Full mode - check for .env file
    if [ ! -f ".env" ]; then
        echo -e "${RED}Error: .env file not found!${NC}"
        echo "Please copy .env.example to .env and set your API keys"
        exit 1
    fi
    
    # Load environment variables
    export $(cat .env | grep -v '^#' | xargs)
    
    # Check required API keys based on provider
    if [[ "$PROVIDER" == "openai" || "$PROVIDER" == "all" ]] && [ -z "$OPENAI_API_KEY" ]; then
        echo -e "${RED}Error: OPENAI_API_KEY is not set!${NC}"
        exit 1
    fi
    
    if [[ "$PROVIDER" == "anthropic" || "$PROVIDER" == "all" ]] && [ -z "$ANTHROPIC_API_KEY" ]; then
        echo -e "${RED}Error: ANTHROPIC_API_KEY is not set!${NC}"
        exit 1
    fi
    
    if [[ "$PROVIDER" == "together" || "$PROVIDER" == "all" ]] && [ -z "$TOGETHER_API_KEY" ]; then
        echo -e "${RED}Error: TOGETHER_API_KEY is not set!${NC}"
        exit 1
    fi
    
    if [[ "$PROVIDER" == "fireworks" || "$PROVIDER" == "all" ]] && [ -z "$FIREWORKS_API_KEY" ]; then
        echo -e "${RED}Error: FIREWORKS_API_KEY is not set!${NC}"
        exit 1
    fi
    
    if [[ "$PROVIDER" == "azure" || "$PROVIDER" == "all" ]] && [ -z "$AZURE_OPENAI_API_KEY" ]; then
        echo -e "${RED}Error: AZURE_OPENAI_API_KEY is not set!${NC}"
        exit 1
    fi
fi

# Function to check gateway with specific config
check_gateway() {
    local provider=$1
    local config_file
    
    # Use unified config for CI mode when testing all providers
    if [ "$MODE" == "ci" ] && [ "$PROVIDER" == "all" ] && [ -n "$UNIFIED_CONFIG" ]; then
        config_file="$UNIFIED_CONFIG"
    else
        config_file="test_config_${provider}${CONFIG_SUFFIX}.toml"
    fi
    
    echo -e "${YELLOW}Expected config file: $config_file${NC}"
    echo -e "${YELLOW}Gateway should be running on port $PORT${NC}"
    
    if ! curl -s -f "${TENSORZERO_BASE_URL}/health" > /dev/null 2>&1; then
        echo -e "${RED}Error: TensorZero gateway is not running!${NC}"
        echo "Please start TensorZero with appropriate config:"
        echo "  cargo run --bin gateway -- --config-file gateway/tests/sdk/$config_file"
        return 1
    fi
    echo -e "${GREEN}✓ TensorZero gateway is running${NC}"
    return 0
}

# Function to run tests for a specific provider
run_provider_tests() {
    local provider=$1
    echo -e "\n${BLUE}Running $provider tests...${NC}\n"
    
    # Check gateway
    if ! check_gateway $provider; then
        return 1
    fi
    
    # Note: Test images are created automatically by the test files themselves
    
    # Determine which tests to run
    local test_dir="${provider}_tests/"
    local test_pattern=""
    
    # Special handling for Fireworks and Azure providers
    if [ "$provider" == "fireworks" ]; then
        echo -e "${YELLOW}Running Fireworks parameter tests...${NC}"
        if [ "$MODE" == "ci" ]; then
            python fireworks_tests/test_ci_fireworks_params.py
        else
            python fireworks_tests/test_fireworks_params.py
        fi
        return $?
    elif [ "$provider" == "azure" ]; then
        echo -e "${YELLOW}Running Azure model tests via OpenAI SDK...${NC}"
        if [ "$MODE" == "ci" ]; then
            python azure_tests/test_ci_azure.py
            exit_code=$?
            echo -e "${BLUE}Note: Azure models are tested via OpenAI SDK since TensorZero provides OpenAI-compatible endpoints.${NC}"
            echo -e "${BLUE}Azure SDK with Azure-specific URL patterns is not supported.${NC}"
            return $exit_code
        else
            python azure_tests/test_azure_sdk_params.py
            exit_code=$?
            echo -e "${BLUE}Note: Azure models are tested via OpenAI SDK since TensorZero provides OpenAI-compatible endpoints.${NC}"
            echo -e "${BLUE}Azure SDK with Azure-specific URL patterns is not supported.${NC}"
            return $exit_code
        fi
    else
        # Standard pytest for other providers
        if [ "$MODE" == "ci" ]; then
            test_pattern="test_ci_*.py"
        else
            test_pattern="test_*.py"
            # Exclude CI tests in full mode
            test_pattern="test_*.py and not test_ci_*.py"
        fi
        
        # Run pytest
        echo -e "${YELLOW}Running pytest for $provider...${NC}"
        if [ "$MODE" == "ci" ]; then
            pytest -v "${test_dir}" -k "test_ci" -x
        else
            if [ "$COMPARE" == true ] && [ "$provider" == "openai" ]; then
                # Run all tests including comparison
                pytest -v "${test_dir}" -k "not test_ci"
            else
                # Run tests excluding comparison
                pytest -v "${test_dir}" -k "not test_ci and not compare_with_openai"
            fi
        fi
        return $?
    fi
}

# Main test execution
overall_success=true

# Handle demo mode
if [ "$DEMO" == true ]; then
    echo -e "${BLUE}Running Universal SDK Architecture Demonstration${NC}"
    echo -e "${BLUE}================================================${NC}"
    
    # Check gateway with unified config
    if ! check_gateway "all"; then
        exit 1
    fi
    
    # Run the demonstration script
    python demonstrate_universal_sdk.py
    exit $?
fi

# Handle universal provider tests
if [ "$PROVIDER" == "universal" ]; then
    echo -e "${BLUE}Running Universal SDK Compatibility Tests${NC}"
    echo -e "${BLUE}=========================================${NC}"
    
    # Check gateway with unified config
    if ! check_gateway "all"; then
        exit 1
    fi
    
    # Run universal SDK tests
    echo -e "${YELLOW}Running OpenAI SDK universal compatibility tests...${NC}"
    pytest -v openai_tests/test_all_providers.py -x
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Universal SDK tests passed${NC}"
        
        # Also run the native SDK tests to show the contrast
        echo -e "\n${YELLOW}Running native Anthropic SDK tests for comparison...${NC}"
        pytest -v anthropic_tests/test_native_messages.py -x
        
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✓ Native SDK tests passed${NC}"
        fi
    else
        echo -e "${RED}✗ Universal SDK tests failed${NC}"
        overall_success=false
    fi
elif [ "$PROVIDER" == "all" ]; then
    # Test all providers
    for p in openai anthropic together fireworks azure; do
        echo -e "\n${BLUE}================================${NC}"
        echo -e "${BLUE}Testing provider: $p${NC}"
        echo -e "${BLUE}================================${NC}"
        
        if run_provider_tests $p; then
            echo -e "${GREEN}✓ $p tests passed${NC}"
        else
            echo -e "${RED}✗ $p tests failed${NC}"
            overall_success=false
        fi
    done
else
    # Test specific provider
    if run_provider_tests $PROVIDER; then
        echo -e "${GREEN}✓ $PROVIDER tests passed${NC}"
    else
        echo -e "${RED}✗ $PROVIDER tests failed${NC}"
        overall_success=false
    fi
fi

# Final summary
echo -e "\n${BLUE}================================${NC}"
if [ "$overall_success" == true ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    exit_code=0
else
    echo -e "${RED}Some tests failed!${NC}"
    exit_code=1
fi

# Deactivate virtual environment
deactivate

exit $exit_code