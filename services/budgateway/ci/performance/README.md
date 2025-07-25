# CI Performance Testing

This directory contains scripts for automated performance testing in CI/CD pipelines.

## Scripts

### `run-performance-test.sh`
Main performance test runner that:
- Builds the gateway and mock provider with performance optimizations
- Starts both services
- Runs warmup requests
- Executes load test using Vegeta
- Outputs results in JSON format
- Performs basic threshold checks

**Environment Variables:**
- `PERF_TEST_DURATION`: Test duration (default: 30s)
- `PERF_TEST_RATE`: Requests per second (default: 1000)
- `PERF_TEST_TIMEOUT`: Request timeout (default: 5s)
- `PERF_TEST_WARMUP`: Number of warmup requests (default: 100)
- `PERF_TEST_OUTPUT`: Output file path (default: performance-results.json)

### `compare-performance.py`
Compares two performance test results and generates a markdown report:
- Calculates percentage changes for all metrics
- Checks for regressions against configurable thresholds
- Outputs markdown suitable for PR comments
- Exits with error code if regressions are detected

**Usage:**
```bash
python compare-performance.py baseline.json current.json
```

## Integration with GitHub Actions

The performance test job in `.github/workflows/pr.yaml`:
1. Runs on every PR
2. Builds with the `performance` profile (maximum optimizations)
3. Executes the performance test
4. Uploads results as artifacts
5. Downloads baseline from the most recent successful main branch run
6. Compares and posts results as a PR comment
7. Currently set as non-blocking (`continue-on-error: true`)

## Thresholds

Strict performance thresholds:
- **P99 Latency**: Must be under 1.5ms (absolute threshold, no exceptions)
- **P95 Latency**: +5% maximum increase from baseline
- **Success Rate**: 99.9% minimum required

These thresholds ensure the gateway maintains ultra-low latency even under high load (1000 req/s).

## Test Details

The performance tests now:
- Test the **OpenAI-compatible `/v1/chat/completions` endpoint**
- Use **1000 concurrent requests per second** for 30 seconds
- Employ **200 max workers** for high concurrency
- Include **100 warmup requests** before measurement

## Local Development

To run performance tests locally:

```bash
# Basic run
./ci/performance/run-performance-test.sh

# Custom parameters
PERF_TEST_DURATION=30s PERF_TEST_RATE=500 ./ci/performance/run-performance-test.sh

# Compare with a baseline
./ci/performance/run-performance-test.sh
mv performance-results.json baseline.json
# Make some changes...
./ci/performance/run-performance-test.sh
python ci/performance/compare-performance.py baseline.json performance-results.json
```