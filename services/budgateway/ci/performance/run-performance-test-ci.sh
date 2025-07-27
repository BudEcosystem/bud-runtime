#!/bin/bash
set -euo pipefail

# CI-specific performance test script
# Assumes binaries are already built

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

# Configuration
DURATION="${PERF_TEST_DURATION:-30s}"
RATE="${PERF_TEST_RATE:-1000}"
TIMEOUT="${PERF_TEST_TIMEOUT:-5s}"
OUTPUT_FILE="${PERF_TEST_OUTPUT:-performance-results.json}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo "🚀 Starting TensorZero Performance Test (CI)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Duration: $DURATION"
echo "Rate: $RATE requests/sec"
echo ""

# Function to check if a process is running
check_process() {
    if kill -0 "$1" 2>/dev/null; then
        return 0
    else
        return 1
    fi
}

# Function to cleanup processes
cleanup() {
    local exit_code=$?
    echo ""
    echo "🧹 Cleaning up..."

    if [ -n "${GATEWAY_PID:-}" ] && check_process "$GATEWAY_PID"; then
        kill "$GATEWAY_PID" 2>/dev/null || true
    fi

    if [ -n "${MOCK_PID:-}" ] && check_process "$MOCK_PID"; then
        kill "$MOCK_PID" 2>/dev/null || true
    fi

    # Show logs on failure
    if [ $exit_code -ne 0 ]; then
        echo ""
        echo "❌ Test failed. Showing logs:"
        if [ -f gateway.log ]; then
            echo ""
            echo "Gateway logs (last 30 lines):"
            tail -30 gateway.log
        fi
        if [ -f mock-provider.log ]; then
            echo ""
            echo "Mock provider logs (last 30 lines):"
            tail -30 mock-provider.log
        fi
    fi
}

# Set up cleanup on exit
trap cleanup EXIT

# Check if binaries exist
if [ ! -f "$PROJECT_ROOT/target/release/gateway" ] || [ ! -f "$PROJECT_ROOT/target/release/mock-inference-provider" ]; then
    echo -e "${RED}❌ Error: Release binaries not found!${NC}"
    echo "Expected:"
    echo "  - $PROJECT_ROOT/target/release/gateway"
    echo "  - $PROJECT_ROOT/target/release/mock-inference-provider"
    exit 1
fi

# Start mock inference provider
echo "🎭 Starting mock inference provider..."
cd "$PROJECT_ROOT"
./target/release/mock-inference-provider > mock-provider.log 2>&1 &
MOCK_PID=$!

# Wait for mock provider using nc (netcat)
echo "⏳ Waiting for mock provider..."
for i in {1..20}; do
    if nc -z localhost 3030 2>/dev/null; then
        echo -e "${GREEN}✓ Mock provider is ready${NC}"
        break
    fi
    if [ $i -eq 20 ]; then
        echo -e "${RED}❌ Mock provider failed to start${NC}"
        exit 1
    fi
    sleep 1
done

# Start gateway
echo "🌉 Starting TensorZero gateway..."
./target/release/gateway --config-file "$SCRIPT_DIR/tensorzero-perf-test.toml" > gateway.log 2>&1 &
GATEWAY_PID=$!

# Wait for gateway
echo "⏳ Waiting for gateway..."
for i in {1..20}; do
    if curl -s -f http://localhost:3000/health >/dev/null 2>&1; then
        echo -e "${GREEN}✓ Gateway is ready${NC}"
        break
    fi
    if [ $i -eq 20 ]; then
        echo -e "${RED}❌ Gateway failed to become healthy${NC}"
        exit 1
    fi
    sleep 1
done

# Test single request to OpenAI chat completions endpoint
echo ""
echo "🧪 Testing single request to /v1/chat/completions..."
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST http://localhost:3000/v1/chat/completions \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer PLACEHOLDER_API_KEY" \
    -H "X-Model-Name: gpt-3.5-turbo" \
    -d @"$SCRIPT_DIR/openai-test-request.json" \
    --max-time 5)

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
if [ "$HTTP_CODE" != "200" ]; then
    echo -e "${RED}❌ Test request failed with HTTP code: $HTTP_CODE${NC}"
    echo "Response:"
    echo "$RESPONSE" | head -n-1
    exit 1
else
    echo -e "${GREEN}✓ Test request successful${NC}"
fi

# Run performance test with high concurrency
echo ""
echo "📊 Running performance test (${DURATION} @ ${RATE} req/s)..."
echo "🔥 Testing OpenAI-compatible chat completions endpoint"
echo 'POST http://localhost:3000/v1/chat/completions' | \
vegeta attack \
    -header="Content-Type: application/json" \
    -header="Authorization: Bearer PLACEHOLDER_API_KEY" \
    -body="$SCRIPT_DIR/openai-test-request.json" \
    -duration="$DURATION" \
    -rate="$RATE" \
    -timeout="$TIMEOUT" \
    -max-workers=200 \
    | vegeta encode | \
    vegeta report -type=json > "$OUTPUT_FILE"

# Parse and display results
echo ""
echo "📈 Performance Test Results"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Extract key metrics using jq
if command -v jq >/dev/null 2>&1; then
    LATENCY_MEAN=$(jq -r '.latencies.mean' "$OUTPUT_FILE" | awk '{print $1/1000000}')
    LATENCY_P50=$(jq -r '.latencies."50th"' "$OUTPUT_FILE" | awk '{print $1/1000000}')
    LATENCY_P95=$(jq -r '.latencies."95th"' "$OUTPUT_FILE" | awk '{print $1/1000000}')
    LATENCY_P99=$(jq -r '.latencies."99th"' "$OUTPUT_FILE" | awk '{print $1/1000000}')
    SUCCESS_RATE=$(jq -r '.success' "$OUTPUT_FILE" | awk '{print $1*100}')
    THROUGHPUT=$(jq -r '.throughput' "$OUTPUT_FILE")

    printf "Latency:\n"
    printf "  P50:  %7.2f ms\n" "$LATENCY_P50"
    printf "  P95:  %7.2f ms\n" "$LATENCY_P95"
    printf "  P99:  %7.2f ms\n" "$LATENCY_P99"
    printf "  Mean: %7.2f ms\n" "$LATENCY_MEAN"
    printf "\n"
    printf "Success Rate: %.2f%%\n" "$SUCCESS_RATE"
    printf "Throughput:   %.2f req/s\n" "$THROUGHPUT"

    # Strict threshold check - P99 must be under 1.5ms
    echo ""
    if [ $(awk -v p99="$LATENCY_P99" 'BEGIN { print (p99 > 1.5) }') -eq 1 ]; then
        echo -e "${RED}❌ Error: P99 latency (${LATENCY_P99}ms) exceeds threshold (1.5ms)${NC}"
        exit 1
    fi

    if [ $(awk -v sr="$SUCCESS_RATE" 'BEGIN { print (sr < 99.9) }') -eq 1 ]; then
        echo -e "${RED}❌ Error: Success rate (${SUCCESS_RATE}%) below threshold (99.9%)${NC}"
        exit 1
    fi
fi

echo ""
echo -e "${GREEN}✅ Performance test completed successfully!${NC}"
echo "📄 Full results saved to: $OUTPUT_FILE"
