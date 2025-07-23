#!/bin/bash
set -euo pipefail

# Script to test rate limiting performance with different optimization levels
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "🚀 Testing Rate Limiting Performance Optimizations"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Test 1: Baseline (no rate limiting)
echo -e "\n📊 Test 1: Baseline (no rate limiting)"
cp "$SCRIPT_DIR/tensorzero-perf-test.toml" "$SCRIPT_DIR/test-config.toml"
./run-performance-test-ci.sh
mv performance-results.json results-baseline.json
P99_BASELINE=$(jq -r '.latencies."99th"' results-baseline.json | awk '{print $1/1000000}')
echo "P99 Baseline: ${P99_BASELINE}ms"

# Test 2: Standard rate limiting
echo -e "\n📊 Test 2: Standard rate limiting"
cp "$SCRIPT_DIR/tensorzero-perf-test-with-rate-limit.toml" "$SCRIPT_DIR/test-config.toml"
export TENSORZERO_REDIS_URL="redis://localhost:6379"
./run-performance-test-ci.sh
mv performance-results.json results-standard.json
P99_STANDARD=$(jq -r '.latencies."99th"' results-standard.json | awk '{print $1/1000000}')
echo "P99 Standard: ${P99_STANDARD}ms"

# Test 3: Optimized rate limiting
echo -e "\n📊 Test 3: Optimized rate limiting"
cp "$SCRIPT_DIR/tensorzero-perf-test-optimized-rate-limit.toml" "$SCRIPT_DIR/test-config.toml"
./run-performance-test-ci.sh
mv performance-results.json results-optimized.json
P99_OPTIMIZED=$(jq -r '.latencies."99th"' results-optimized.json | awk '{print $1/1000000}')
echo "P99 Optimized: ${P99_OPTIMIZED}ms"

# Restore original config
rm "$SCRIPT_DIR/test-config.toml"

# Summary
echo -e "\n📊 Performance Summary"
echo "━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Baseline (no RL):     ${P99_BASELINE}ms"
echo "Standard RL:          ${P99_STANDARD}ms"
echo "Optimized RL:         ${P99_OPTIMIZED}ms"

OVERHEAD_STANDARD=$(awk -v base="$P99_BASELINE" -v rl="$P99_STANDARD" 'BEGIN { printf "%.2f", ((rl - base) / base) * 100 }')
OVERHEAD_OPTIMIZED=$(awk -v base="$P99_BASELINE" -v rl="$P99_OPTIMIZED" 'BEGIN { printf "%.2f", ((rl - base) / base) * 100 }')

echo ""
echo "Standard RL overhead:  ${OVERHEAD_STANDARD}%"
echo "Optimized RL overhead: ${OVERHEAD_OPTIMIZED}%"

# Check if optimized meets target
if [ $(awk -v p99="$P99_OPTIMIZED" 'BEGIN { print (p99 > 1.5) }') -eq 1 ]; then
    echo -e "\n❌ Optimized rate limiting still exceeds 1.5ms target"
    exit 1
else
    echo -e "\n✅ Optimized rate limiting meets performance target!"
fi