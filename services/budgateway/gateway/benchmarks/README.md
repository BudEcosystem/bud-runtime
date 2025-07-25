# Benchmarks

## CI Performance Testing

Performance tests run automatically on every PR to detect regressions. The CI system:

1. **Runs high-load performance tests** (30 seconds, 1000 RPS) on every PR
2. **Tests the OpenAI-compatible `/v1/chat/completions` endpoint**
3. **Compares results against baseline** from the main branch
4. **Posts results as a PR comment** with detailed metrics
5. **Fails if performance doesn't meet strict thresholds**:
   - P99 latency: Must be under 1.5ms (absolute threshold)
   - P95 latency: +5% maximum increase allowed
   - Success rate: 99.9% minimum required

### Running Performance Tests Locally

```bash
# Run the CI performance test
./ci/performance/run-performance-test.sh

# Run with custom parameters
PERF_TEST_DURATION=30s PERF_TEST_RATE=500 ./ci/performance/run-performance-test.sh

# Compare two results
python ci/performance/compare-performance.py baseline.json current.json
```

### Performance Test Configuration

The CI tests use:
- **Mock inference provider**: Simulates OpenAI API with consistent response times
- **OpenAI-compatible endpoint**: Tests `/v1/chat/completions` for real-world scenarios
- **High concurrency**: 1000 requests/second with 200 max workers
- **No observability**: Tests raw gateway performance without telemetry overhead
- **Warmup phase**: 100 requests before measurement begins
- **Vegeta load tester**: Industry-standard HTTP load testing tool

## Full Benchmarks

## TensorZero Gateway vs. LiteLLM Proxy (LiteLLM Gateway)

### Environment Setup

- Launch an AWS EC2 Instance: `c7i.xlarge` (4 vCPUs, 8 GB RAM)
- Increase the limits for open file descriptors:

  - Run `sudo vim /etc/security/limits.conf` and add the following lines:
    ```
    *               soft    nofile          65536
    *               hard    nofile          65536
    ```
  - Run `sudo vim /etc/pam.d/common-session` and add the following line:
    ```
    session required pam_limits.so
    ```
  - Reboot the instance with `sudo reboot`
  - Run `ulimit -Hn` and `ulimit -Sn` to check that the limits are now `65536`

- Install Python 3.10.14.
- Install LiteLLM: `pip install 'litellm[proxy]'==1.34.42`
- Install Rust 1.80.1.
- Install `vegeta` [→](https://github.com/tsenart/vegeta).
- Set the `OPENAI_API_KEY` environment variable to anything (e.g. `OPENAI_API_KEY=test`).

### Test Setup

- Launch the mock inference provider in performance mode:

  ```bash
  cargo run --profile performance --bin mock-inference-provider
  ```

#### TensorZero Gateway

- Launch the TensorZero Gateway in performance mode (without observability):

  ```bash
  cargo run --profile performance --bin gateway tensorzero-internal/tests/load/tensorzero-without-observability.toml
  ```

- Run the benchmark:
  ```bash
  sh tensorzero-internal/tests/load/simple/run.sh
  ```

#### LiteLLM Gateway (LiteLLM Proxy)

- Launch the LiteLLM Gateway:

  ```
  litellm --config tensorzero-internal/tests/load/simple-litellm/config.yaml --num_workers=4
  ```

- Run the benchmark:

  ```bash
  sh tensorzero-internal/tests/load/simple-litellm/run.sh
  ```
