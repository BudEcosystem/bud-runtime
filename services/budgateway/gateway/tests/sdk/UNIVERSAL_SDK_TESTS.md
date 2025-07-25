# Running Universal SDK Tests

## Quick Start

### 1. Start the Gateway

First, start the TensorZero gateway with the unified configuration:

```bash
# From the repository root
cargo run --bin gateway -- --config-file gateway/tests/sdk/test_config_unified_ci.toml
```

### 2. Run Universal SDK Tests

In a new terminal, navigate to the SDK tests directory and run:

```bash
cd gateway/tests/sdk

# Run universal SDK compatibility tests
./run_tests.sh --provider universal

# Run interactive architecture demonstration
./run_tests.sh --demo
```

## Test Options

### Universal SDK Tests

Tests that demonstrate OpenAI SDK working with ALL providers:

```bash
# Run universal compatibility tests
./run_tests.sh --provider universal

# This runs:
# - OpenAI SDK with Anthropic models (Claude Haiku, Sonnet, Opus)
# - OpenAI SDK with OpenAI models (GPT-3.5, GPT-4)
# - Native Anthropic SDK tests for comparison
```

### Architecture Demonstration

Interactive demo showing the architecture in action:

```bash
# Run the architecture demonstration
./run_tests.sh --demo

# Or run directly
python demonstrate_universal_sdk.py
```

### Individual Test Files

You can also run specific test files:

```bash
# Activate virtual environment
source .venv/bin/activate

# Set environment variables
export TENSORZERO_BASE_URL="http://localhost:3001"
export TENSORZERO_API_KEY="test-api-key"

# Run universal compatibility tests
pytest openai_tests/test_all_providers.py -v

# Run native Anthropic SDK tests
pytest anthropic_tests/test_native_messages.py -v

# Run focused demo tests
pytest openai_tests/test_universal_sdk_demo.py -v -s
```

## What These Tests Prove

1. **Universal OpenAI SDK**: The OpenAI SDK works with ALL providers through `/v1/chat/completions`
2. **Native SDKs**: Provider-specific SDKs (like Anthropic) work with their native endpoints
3. **Architecture**: One universal SDK (OpenAI) + specialized native SDKs = best of both worlds

## Expected Output

When running `./run_tests.sh --provider universal`, you should see:

```
✅ OpenAI SDK + Anthropic models: PASSED
✅ OpenAI SDK + OpenAI models: PASSED  
✅ Native Anthropic SDK + /v1/messages: PASSED
```

This demonstrates that:
- OpenAI SDK is truly universal
- Native SDKs work with their specific endpoints
- The architecture supports both approaches seamlessly

## Troubleshooting

### Gateway Not Running

If you see "TensorZero gateway is not running!", make sure to start it:

```bash
cargo run --bin gateway -- --config-file gateway/tests/sdk/test_config_unified_ci.toml
```

### Missing Dependencies

If you get import errors, install dependencies:

```bash
pip install -r requirements.txt
```

### Port Already in Use

If port 3001 is in use, specify a different port:

```bash
# Start gateway on different port
cargo run --bin gateway -- --config-file gateway/tests/sdk/test_config_unified_ci.toml --bind-address 0.0.0.0:3002

# Run tests with custom port
./run_tests.sh --provider universal --port 3002
```