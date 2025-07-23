#!/bin/bash
set -euo pipefail

# Performance test script to compare with and without rate limiting
# This script runs the performance test twice to measure rate limiting overhead

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

# Configuration
DURATION="${PERF_TEST_DURATION:-30s}"
RATE="${PERF_TEST_RATE:-1000}"
TIMEOUT="${PERF_TEST_TIMEOUT:-5s}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "🚀 TensorZero Rate Limiting Performance Comparison Test"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Duration: $DURATION"
echo "Rate: $RATE requests/sec"
echo ""

# Function to run a single test
run_test() {
    local config_file=$1
    local output_file=$2
    local test_name=$3
    
    echo ""
    echo -e "${BLUE}🔧 Running test: $test_name${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Run the actual performance test
    "$SCRIPT_DIR/run-performance-test-ci.sh" > test.log 2>&1
    
    # Copy the results
    cp performance-results.json "$output_file"
    
    # Extract and display metrics
    if command -v jq >/dev/null 2>&1; then
        local p50=$(jq -r '.latencies."50th"' "$output_file" | awk '{print $1/1000000}')
        local p95=$(jq -r '.latencies."95th"' "$output_file" | awk '{print $1/1000000}')
        local p99=$(jq -r '.latencies."99th"' "$output_file" | awk '{print $1/1000000}')
        local success=$(jq -r '.success' "$output_file" | awk '{print $1*100}')
        
        printf "Results:\n"
        printf "  P50: %7.2f ms\n" "$p50"
        printf "  P95: %7.2f ms\n" "$p95"
        printf "  P99: %7.2f ms\n" "$p99"
        printf "  Success: %.2f%%\n" "$success"
    fi
}

# Check if Redis is available for rate limiting test
REDIS_AVAILABLE=false
if command -v redis-cli >/dev/null 2>&1; then
    if redis-cli -h localhost ping >/dev/null 2>&1; then
        REDIS_AVAILABLE=true
        echo -e "${GREEN}✓ Redis is available${NC}"
    else
        echo -e "${YELLOW}⚠ Redis not available - starting Redis container${NC}"
        # Try to start Redis using docker compose
        if [ -f "$PROJECT_ROOT/tensorzero-internal/tests/e2e/docker-compose.yml" ]; then
            cd "$PROJECT_ROOT/tensorzero-internal/tests/e2e"
            docker compose up -d redis
            sleep 5
            if redis-cli -h localhost ping >/dev/null 2>&1; then
                REDIS_AVAILABLE=true
                echo -e "${GREEN}✓ Redis started successfully${NC}"
            fi
        fi
    fi
else
    echo -e "${YELLOW}⚠ redis-cli not found${NC}"
fi

# Test 1: Without rate limiting
echo ""
echo "📊 Test 1: WITHOUT Rate Limiting"
cp "$SCRIPT_DIR/tensorzero-perf-test.toml" "$SCRIPT_DIR/tensorzero-perf-test.toml.bak"
run_test "$SCRIPT_DIR/tensorzero-perf-test.toml" "performance-without-rate-limit.json" "Without Rate Limiting"

# Test 2: With rate limiting (if Redis is available)
if [ "$REDIS_AVAILABLE" = true ]; then
    echo ""
    echo "📊 Test 2: WITH Rate Limiting"
    
    # Set Redis URL for rate limiting
    export TENSORZERO_REDIS_URL="redis://localhost:6379"
    
    # Temporarily replace config file
    cp "$SCRIPT_DIR/tensorzero-perf-test-with-rate-limit.toml" "$SCRIPT_DIR/tensorzero-perf-test.toml"
    
    run_test "$SCRIPT_DIR/tensorzero-perf-test.toml" "performance-with-rate-limit.json" "With Rate Limiting"
    
    # Restore original config
    cp "$SCRIPT_DIR/tensorzero-perf-test.toml.bak" "$SCRIPT_DIR/tensorzero-perf-test.toml"
    rm "$SCRIPT_DIR/tensorzero-perf-test.toml.bak"
    
    # Compare results
    echo ""
    echo "📊 Performance Comparison"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━"
    
    if command -v jq >/dev/null 2>&1; then
        p99_without=$(jq -r '.latencies."99th"' "performance-without-rate-limit.json" | awk '{print $1/1000000}')
        p99_with=$(jq -r '.latencies."99th"' "performance-with-rate-limit.json" | awk '{print $1/1000000}')
        overhead=$(awk -v with="$p99_with" -v without="$p99_without" 'BEGIN { print ((with - without) / without) * 100 }')
        
        printf "P99 without rate limiting: %7.2f ms\n" "$p99_without"
        printf "P99 with rate limiting:    %7.2f ms\n" "$p99_with"
        printf "Overhead:                  %7.2f%%\n" "$overhead"
        
        # Check if overhead is acceptable (< 10%)
        if [ $(awk -v oh="$overhead" 'BEGIN { print (oh > 10) }') -eq 1 ]; then
            echo -e "${YELLOW}⚠ Warning: Rate limiting overhead is ${overhead}%${NC}"
        else
            echo -e "${GREEN}✓ Rate limiting overhead is acceptable (${overhead}%)${NC}"
        fi
        
        # Still check against absolute threshold
        if [ $(awk -v p99="$p99_with" 'BEGIN { print (p99 > 1.5) }') -eq 1 ]; then
            echo -e "${RED}❌ Error: P99 latency with rate limiting (${p99_with}ms) exceeds threshold (1.5ms)${NC}"
            exit 1
        fi
    fi
else
    echo ""
    echo -e "${YELLOW}⚠ Skipping rate limiting test - Redis not available${NC}"
    echo "To test with rate limiting, ensure Redis is running on localhost:6379"
fi

echo ""
echo -e "${GREEN}✅ Performance tests completed!${NC}"