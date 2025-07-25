#!/bin/bash
set -e

echo "Running Together AI SDK tests..."
echo "================================"

# Set the test configuration
export TENSORZERO_CONFIG_FILE="test_config_together.toml"

# Function to check if API key is available
check_api_key() {
    if [ -z "$TOGETHER_API_KEY" ]; then
        echo "Warning: TOGETHER_API_KEY not set. Tests requiring real API will be skipped."
        return 1
    fi
    return 0
}

# Function to run gateway
run_gateway() {
    local config_file=$1
    echo "Starting gateway with config: $config_file"
    
    # Kill any existing gateway process
    pkill -f "gateway.*--config-file" || true
    sleep 1
    
    # Start the gateway
    TENSORZERO_CONFIG_FILE="$config_file" cargo run --bin gateway -- --config-file "$config_file" > gateway.log 2>&1 &
    GATEWAY_PID=$!
    
    # Wait for gateway to be ready
    echo "Waiting for gateway to start..."
    for i in {1..30}; do
        if curl -s http://localhost:3001/health > /dev/null 2>&1; then
            echo "Gateway is ready!"
            break
        fi
        if [ $i -eq 30 ]; then
            echo "Gateway failed to start. Check gateway.log for details."
            cat gateway.log
            exit 1
        fi
        sleep 1
    done
}

# Function to stop gateway
stop_gateway() {
    if [ ! -z "$GATEWAY_PID" ]; then
        echo "Stopping gateway..."
        kill $GATEWAY_PID || true
        wait $GATEWAY_PID 2>/dev/null || true
    fi
}

# Trap to ensure gateway is stopped on exit
trap stop_gateway EXIT

# Run CI tests (always run, no API key needed)
echo ""
echo "Running CI tests with dummy provider..."
echo "---------------------------------------"
run_gateway "test_config_together_ci.toml"
python -m pytest together_tests/test_ci_together.py -v
python -m pytest together_tests/test_ci_together_multimodal.py -v
stop_gateway

# Run full tests if API key is available
if check_api_key; then
    echo ""
    echo "Running full tests with Together AI provider..."
    echo "----------------------------------------------"
    run_gateway "test_config_together.toml"
    python -m pytest together_tests/test_universal_openai_sdk.py -v
    python -m pytest together_tests/test_embeddings.py -v
    python -m pytest together_tests/test_image_generation.py -v
    python -m pytest together_tests/test_text_to_speech.py -v
    python -m pytest together_tests/test_together_multimodal.py -v
    stop_gateway
else
    echo ""
    echo "Skipping full tests (no API key)"
fi

echo ""
echo "Together AI SDK tests completed!"
echo "================================"