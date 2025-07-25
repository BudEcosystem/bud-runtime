#!/bin/bash
set -euo pipefail

echo "🚀 Local Performance Test"
echo "========================"

# Kill any existing processes on our ports
echo "Cleaning up any existing processes..."
lsof -i :3000 | grep -v COMMAND | awk '{print $2}' | xargs -r kill -9 2>/dev/null || true
lsof -i :3030 | grep -v COMMAND | awk '{print $2}' | xargs -r kill -9 2>/dev/null || true
sleep 1

# Start mock provider
echo "Starting mock provider..."
./target/debug/mock-inference-provider > mock.log 2>&1 &
MOCK_PID=$!

# Wait for mock provider
echo "Waiting for mock provider..."
for i in {1..10}; do
    if nc -z localhost 3030 2>/dev/null; then
        echo "✓ Mock provider ready"
        break
    fi
    if [ $i -eq 10 ]; then
        echo "❌ Mock provider failed to start"
        cat mock.log
        exit 1
    fi
    sleep 1
done

# Start gateway
echo "Starting gateway..."
./target/debug/gateway --config-file tensorzero-internal/tests/load/tensorzero-without-observability.toml > gateway.log 2>&1 &
GW_PID=$!

# Wait for gateway
echo "Waiting for gateway..."
for i in {1..10}; do
    if curl -s http://localhost:3000/health >/dev/null 2>&1; then
        echo "✓ Gateway ready"
        break
    fi
    if [ $i -eq 10 ]; then
        echo "❌ Gateway failed to start"
        cat gateway.log
        kill $MOCK_PID 2>/dev/null || true
        exit 1
    fi
    sleep 1
done

# Test the inference endpoint
echo ""
echo "Testing inference endpoint..."
curl -X POST http://localhost:3000/inference \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer budserve_ApTuiKIpZEjMytHt3nmCJqBQGaIlqc2TfoKYFusk" \
    -d @ci/performance/test-request.json \
    -w "\nStatus: %{http_code}\nTime: %{time_total}s\n" \
    -s | head -20

# Run performance test
echo ""
echo "Running performance test (5s @ 50 req/s)..."
echo 'POST http://localhost:3000/inference' | \
vegeta attack \
    -header="Content-Type: application/json" \
    -header="Authorization: Bearer budserve_ApTuiKIpZEjMytHt3nmCJqBQGaIlqc2TfoKYFusk" \
    -body="ci/performance/test-request.json" \
    -duration=5s \
    -rate=50 \
    | vegeta encode | \
    vegeta report -type=json > performance-results.json

# Show results
echo ""
echo "Results:"
jq -r '.latencies | "P99: \(.["99th"]/1000000)ms, P95: \(.["95th"]/1000000)ms, Mean: \(.mean/1000000)ms"' performance-results.json
jq -r '"Success rate: \(.success * 100)%, Throughput: \(.throughput) req/s"' performance-results.json

# Cleanup
echo ""
echo "Cleaning up..."
kill $GW_PID $MOCK_PID 2>/dev/null || true

echo "✅ Test complete!"