#!/bin/bash
set -euo pipefail

echo "🚀 Quick Local Performance Test"
echo "================================"
echo "This test assumes binaries are already built."
echo ""

# Check if binaries exist
if [ ! -f "target/release/mock-inference-provider" ] || [ ! -f "target/release/gateway" ]; then
    echo "❌ Error: Binaries not found!"
    echo "Please run: cargo build --release --bin gateway --bin mock-inference-provider"
    exit 1
fi

# Start mock provider
echo "Starting mock provider..."
./target/release/mock-inference-provider > mock.log 2>&1 &
MOCK_PID=$!

# Wait for mock provider
sleep 3

# Start gateway
echo "Starting gateway..."
./target/release/gateway tensorzero-internal/tests/load/tensorzero-without-observability.toml > gateway.log 2>&1 &
GW_PID=$!

# Wait for gateway
sleep 3

# Check if services are running
if ! kill -0 $MOCK_PID 2>/dev/null; then
    echo "❌ Mock provider failed to start"
    cat mock.log
    exit 1
fi

if ! kill -0 $GW_PID 2>/dev/null; then
    echo "❌ Gateway failed to start"
    cat gateway.log
    kill $MOCK_PID 2>/dev/null || true
    exit 1
fi

# Run quick test
echo ""
echo "Running performance test (5s @ 50 req/s)..."
echo 'POST http://localhost:3000/inference' | \
vegeta attack \
    -header="Content-Type: application/json" \
    -body="ci/performance/test-request.json" \
    -duration=5s \
    -rate=50 \
    | vegeta encode | \
    vegeta report

# Cleanup
echo ""
echo "Cleaning up..."
kill $GW_PID $MOCK_PID 2>/dev/null || true

echo "✅ Test complete!"