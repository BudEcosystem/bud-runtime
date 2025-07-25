#!/bin/bash
set -euo pipefail

# Quick performance test that assumes binaries are already built

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

# Configuration
DURATION="${PERF_TEST_DURATION:-5s}"
RATE="${PERF_TEST_RATE:-50}"
OUTPUT_FILE="${PERF_TEST_OUTPUT:-performance-results.json}"

echo "🚀 Starting Quick Performance Test"
echo "Duration: $DURATION, Rate: $RATE req/s"

# Check if binaries exist
if [ ! -f "$PROJECT_ROOT/target/release/mock-inference-provider" ] || [ ! -f "$PROJECT_ROOT/target/release/gateway" ]; then
    echo "❌ Binaries not found. Please run: cargo build --release --bin gateway --bin mock-inference-provider"
    exit 1
fi

# Start services
"$PROJECT_ROOT/target/release/mock-inference-provider" &
MOCK_PID=$!

sleep 2

"$PROJECT_ROOT/target/release/gateway" "$PROJECT_ROOT/tensorzero-internal/tests/load/tensorzero-without-observability.toml" &
GW_PID=$!

sleep 3

# Run test
echo 'POST http://localhost:3000/inference' | \
vegeta attack \
    -header="Content-Type: application/json" \
    -body="$SCRIPT_DIR/test-request.json" \
    -duration="$DURATION" \
    -rate="$RATE" \
    | vegeta encode | \
    vegeta report -type=json > "$OUTPUT_FILE"

# Cleanup
kill $GW_PID $MOCK_PID 2>/dev/null || true

echo "✅ Results saved to $OUTPUT_FILE"
jq -r '.latencies | "P99: \(.["99th"]/1000000)ms, Mean: \(.mean/1000000)ms"' "$OUTPUT_FILE"