#!/bin/bash
# Run performance tests with different tools

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPORT_DIR="${SCRIPT_DIR}/reports/performance"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Create report directory
mkdir -p "$REPORT_DIR"

# Default values
ENDPOINT="${BUDPROXY_ENDPOINT:-http://localhost:8000}"
MODEL="${TEST_MODEL:-test-model}"
DURATION="${TEST_DURATION:-5m}"
VUS="${TEST_VUS:-20}"

echo "=========================================="
echo "Performance Test Suite"
echo "=========================================="
echo "Endpoint: $ENDPOINT"
echo "Model: $MODEL"
echo "Duration: $DURATION"
echo "Virtual Users: $VUS"
echo ""

# Function to run K6 tests
run_k6_tests() {
    echo -e "${GREEN}Running K6 load tests...${NC}"
    
    if ! command -v k6 &> /dev/null; then
        echo -e "${YELLOW}K6 not installed. Installing...${NC}"
        # Download and install k6
        curl -L https://github.com/grafana/k6/releases/download/v0.47.0/k6-v0.47.0-linux-amd64.tar.gz | tar xvz
        sudo mv k6-v0.47.0-linux-amd64/k6 /usr/local/bin/
    fi
    
    # Run different scenarios
    echo "Running smoke test..."
    k6 run \
        -e ENDPOINT="$ENDPOINT" \
        -e MODEL="$MODEL" \
        --out json="$REPORT_DIR/k6_smoke_${TIMESTAMP}.json" \
        --summary-export="$REPORT_DIR/k6_smoke_summary_${TIMESTAMP}.json" \
        "$SCRIPT_DIR/../load/k6/inference_load_test.js" \
        --tag scenario=smoke
    
    echo "Running load test..."
    k6 run \
        -e ENDPOINT="$ENDPOINT" \
        -e MODEL="$MODEL" \
        --vus "$VUS" \
        --duration "$DURATION" \
        --out json="$REPORT_DIR/k6_load_${TIMESTAMP}.json" \
        --summary-export="$REPORT_DIR/k6_load_summary_${TIMESTAMP}.json" \
        "$SCRIPT_DIR/../load/k6/inference_load_test.js"
    
    echo -e "${GREEN}✓ K6 tests completed${NC}"
}

# Function to run Locust tests
run_locust_tests() {
    echo -e "${GREEN}Running Locust load tests...${NC}"
    
    if ! command -v locust &> /dev/null; then
        echo -e "${YELLOW}Locust not installed. Please run: pip install locust${NC}"
        return 1
    fi
    
    # Run headless test
    echo "Running Locust test (headless)..."
    locust \
        -f "$SCRIPT_DIR/../load/locust/locustfile.py" \
        --host "$ENDPOINT" \
        --users "$VUS" \
        --spawn-rate 2 \
        --run-time "$DURATION" \
        --headless \
        --html "$REPORT_DIR/locust_report_${TIMESTAMP}.html" \
        --csv "$REPORT_DIR/locust_stats_${TIMESTAMP}"
    
    echo -e "${GREEN}✓ Locust tests completed${NC}"
}

# Function to run custom performance tests
run_custom_tests() {
    echo -e "${GREEN}Running custom performance tests...${NC}"
    
    cd "$SCRIPT_DIR"
    
    # Run pytest performance tests
    python -m pytest scenarios/test_performance.py \
        -v \
        --tb=short \
        --json-report \
        --json-report-file="$REPORT_DIR/pytest_performance_${TIMESTAMP}.json" \
        -k performance
    
    echo -e "${GREEN}✓ Custom tests completed${NC}"
}

# Function to analyze results
analyze_results() {
    echo -e "${GREEN}Analyzing performance results...${NC}"
    
    # Create analysis script
    cat > "$REPORT_DIR/analyze_${TIMESTAMP}.py" << 'EOF'
#!/usr/bin/env python3
import json
import sys
from pathlib import Path
import statistics

def analyze_k6_results(summary_file):
    """Analyze K6 test results."""
    with open(summary_file) as f:
        data = json.load(f)
    
    metrics = data.get("metrics", {})
    
    print("\n=== K6 Performance Metrics ===")
    
    # HTTP metrics
    if "http_req_duration" in metrics:
        duration = metrics["http_req_duration"]["values"]
        print(f"Response Time:")
        print(f"  Average: {duration['avg']:.2f}ms")
        print(f"  Median: {duration['med']:.2f}ms")
        print(f"  P95: {duration['p(95)']:.2f}ms")
        print(f"  P99: {duration['p(99)']:.2f}ms")
    
    # Throughput
    if "http_reqs" in metrics:
        reqs = metrics["http_reqs"]["values"]
        print(f"\nThroughput: {reqs['rate']:.2f} req/s")
    
    # Error rate
    if "http_req_failed" in metrics:
        failed = metrics["http_req_failed"]["values"]
        print(f"Error Rate: {failed['rate']*100:.2f}%")

def analyze_locust_results(stats_file):
    """Analyze Locust test results."""
    import csv
    
    print("\n=== Locust Performance Metrics ===")
    
    # Read stats CSV
    with open(f"{stats_file}_stats.csv") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['Name'] == 'Aggregated':
                print(f"Total Requests: {row['Request Count']}")
                print(f"Failure Rate: {row['Failure Count']}/{row['Request Count']}")
                print(f"Average Response Time: {row['Average Response Time']}ms")
                print(f"Median Response Time: {row['Median Response Time']}ms")
                print(f"RPS: {row['Requests/s']}")

def main():
    report_dir = Path(sys.argv[1])
    timestamp = sys.argv[2]
    
    # Analyze K6 results
    k6_summary = report_dir / f"k6_load_summary_{timestamp}.json"
    if k6_summary.exists():
        analyze_k6_results(k6_summary)
    
    # Analyze Locust results
    locust_stats = report_dir / f"locust_stats_{timestamp}"
    if Path(f"{locust_stats}_stats.csv").exists():
        analyze_locust_results(locust_stats)
    
    print("\n=== Performance Test Summary ===")
    print("✓ All performance tests completed")
    print(f"✓ Reports saved to: {report_dir}")

if __name__ == "__main__":
    main()
EOF
    
    chmod +x "$REPORT_DIR/analyze_${TIMESTAMP}.py"
    python "$REPORT_DIR/analyze_${TIMESTAMP}.py" "$REPORT_DIR" "$TIMESTAMP"
}

# Function to generate consolidated report
generate_report() {
    echo -e "${GREEN}Generating consolidated report...${NC}"
    
    cat > "$REPORT_DIR/performance_report_${TIMESTAMP}.md" << EOF
# Performance Test Report

**Date:** $(date)
**Endpoint:** $ENDPOINT
**Model:** $MODEL
**Duration:** $DURATION
**Virtual Users:** $VUS

## Test Results

### K6 Load Test
- Smoke test results: [k6_smoke_summary_${TIMESTAMP}.json](k6_smoke_summary_${TIMESTAMP}.json)
- Load test results: [k6_load_summary_${TIMESTAMP}.json](k6_load_summary_${TIMESTAMP}.json)

### Locust Load Test
- HTML Report: [locust_report_${TIMESTAMP}.html](locust_report_${TIMESTAMP}.html)
- CSV Stats: [locust_stats_${TIMESTAMP}_stats.csv](locust_stats_${TIMESTAMP}_stats.csv)

### Custom Performance Tests
- PyTest Results: [pytest_performance_${TIMESTAMP}.json](pytest_performance_${TIMESTAMP}.json)

## Key Metrics

### Response Times
- Target: P95 < 5 seconds
- Actual: See individual reports

### Throughput
- Target: > 10 req/s per instance
- Actual: See individual reports

### Error Rate
- Target: < 1%
- Actual: See individual reports

## Recommendations

Based on the test results:
1. Monitor response times under load
2. Consider scaling thresholds
3. Review error patterns
4. Optimize slow endpoints

EOF
    
    echo -e "${GREEN}✓ Report generated: $REPORT_DIR/performance_report_${TIMESTAMP}.md${NC}"
}

# Main execution
main() {
    echo "Starting performance test suite..."
    
    # Check if specific test type is requested
    TEST_TYPE="${1:-all}"
    
    case "$TEST_TYPE" in
        k6)
            run_k6_tests
            ;;
        locust)
            run_locust_tests
            ;;
        custom)
            run_custom_tests
            ;;
        all)
            run_k6_tests || echo -e "${YELLOW}K6 tests failed${NC}"
            run_locust_tests || echo -e "${YELLOW}Locust tests failed${NC}"
            run_custom_tests || echo -e "${YELLOW}Custom tests failed${NC}"
            ;;
        *)
            echo "Usage: $0 [k6|locust|custom|all]"
            exit 1
            ;;
    esac
    
    # Analyze and report
    analyze_results
    generate_report
    
    echo ""
    echo "=========================================="
    echo -e "${GREEN}Performance tests completed!${NC}"
    echo "Reports saved to: $REPORT_DIR"
    echo "=========================================="
}

# Run main
main "$@"