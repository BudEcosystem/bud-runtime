# E2E Testing Framework

This directory contains the comprehensive E2E testing framework for the multi-cluster inference stack.

## Overview

The testing framework provides:
- **Functional Tests**: Core inference functionality testing
- **Integration Tests**: Cross-service integration validation
- **Performance Tests**: Load testing with K6 and Locust
- **Failover Tests**: Resilience and recovery testing
- **Autoscaling Tests**: HPA and GPU scaling validation
- **Monitoring**: Real-time test execution monitoring

## Directory Structure

```
tests/
├── deployments/           # Test deployment manifests
│   ├── app-cluster/       # App cluster test deployments
│   │   ├── budproxy.yaml
│   │   └── README.md
│   ├── inference-cluster/ # Inference cluster test deployments
│   │   ├── aibrix.yaml
│   │   └── README.md
│   └── deploy-test-services.sh
├── e2e/
│   ├── scenarios/          # Test scenarios
│   │   ├── test_inference_flow.py
│   │   ├── test_routing.py
│   │   ├── test_autoscaling.py
│   │   ├── test_failover.py
│   │   └── test_performance.py
│   ├── utils/             # Test utilities
│   │   ├── __init__.py
│   │   ├── kubernetes_utils.py
│   │   ├── inference_utils.py
│   │   └── monitoring_utils.py
│   ├── fixtures/          # Test data
│   │   └── test_data.yaml
│   ├── run_tests.py       # Main test runner
│   ├── run_performance_tests.sh
│   ├── monitor_tests.py
│   └── generate_test_report.py
├── load/                  # Load testing tools
│   ├── k6/
│   │   └── inference_load_test.js
│   └── locust/
│       └── locustfile.py
├── conftest.py           # PyTest configuration
├── pytest.ini            # PyTest settings
└── requirements-test.txt # Test dependencies
```

## Quick Start

### 1. Deploy Test Services

```bash
# Deploy BudProxy and AIBrix to test clusters
./deployments/deploy-test-services.sh
```

### 2. Install Dependencies

```bash
pip install -r requirements-test.txt
```

### 3. Run Smoke Tests

```bash
# Quick smoke tests
./e2e/run_tests.py --scenario smoke

# With specific clusters
./e2e/run_tests.py --scenario smoke \
  --clusters app=app-cluster,inference=inference-cluster
```

### 4. Run Full Test Suite

```bash
# All functional tests
./e2e/run_tests.py --scenario functional

# Full test suite with HTML report
./e2e/run_tests.py --scenario full --report html
```

### 5. Run Performance Tests

```bash
# Run all performance tests
./e2e/run_performance_tests.sh all

# Run specific tool
./e2e/run_performance_tests.sh k6
./e2e/run_performance_tests.sh locust
```

### 6. Monitor Test Execution

```bash
# Monitor with Prometheus metrics collection
./e2e/monitor_tests.py \
  --test-name "integration-test" \
  --prometheus http://localhost:9090 \
  --grafana http://localhost:3000 \
  -- ./e2e/run_tests.py --scenario integration
```

## Test Scenarios

### Smoke Tests (`@pytest.mark.smoke`)
Quick validation tests that run in < 5 minutes:
- Basic inference request
- Health check validation
- Service connectivity

### Functional Tests
Core functionality validation:
- Simple inference
- Batch inference
- Model routing
- Request validation
- Error handling

### Integration Tests (`@pytest.mark.integration`)
Cross-service integration:
- BudProxy → AIBrix → VLLM flow
- Database integration
- Cache functionality
- Monitoring integration

### Performance Tests (`@pytest.mark.load`)
Load and stress testing:
- Throughput testing
- Latency measurements
- Concurrent user simulation
- Resource utilization

### Failover Tests (`@pytest.mark.failover`)
Resilience testing:
- Pod crash recovery
- Service failure handling
- Network partition simulation
- Database connection loss

### Autoscaling Tests
Scaling behavior validation:
- HPA trigger testing
- Scale up/down verification
- GPU scaling
- AIBrix-controlled scaling

## Test Deployments

The `deployments/` directory contains minimal Kubernetes manifests for testing:

### App Cluster Services
- **BudProxy**: TensorZero Gateway running on port 3000
  - Image: `budstudio/budproxy:nightly`
  - Deployed to `bud-system` namespace

### Inference Cluster Services
- **AIBrix**: Two deployment options
  - Placeholder using nginx for quick testing
  - Build from source using `./build-aibrix.sh` for development
  - Deployed to `inference-system` or `aibrix-system` namespace

Deploy all test services:
```bash
./deployments/deploy-test-services.sh
```

## Configuration

### Environment Variables

```bash
# Cluster contexts
export K8S_APP_CONTEXT=k3d-bud-app
export K8S_INFERENCE_CONTEXT=k3d-bud-inference

# Service endpoints
export BUDPROXY_ENDPOINT=http://budproxy.example.com
export AIBRIX_ENDPOINT=http://aibrix.example.com

# Test models
export TEST_MODELS=test-model,llama2-7b,mistral-7b

# Performance test settings
export TEST_DURATION=5m
export TEST_VUS=50
```

### PyTest Configuration

The `pytest.ini` file configures:
- Test markers
- Timeout settings
- Output formatting
- Plugin configuration

### Test Data

Test prompts and expected responses are defined in `fixtures/test_data.yaml`:
- Simple prompts
- Complex prompts
- Domain-specific prompts
- Edge cases
- Performance configurations

## Running Specific Tests

### By Marker

```bash
# Only smoke tests
pytest -m smoke

# Integration tests without slow tests
pytest -m "integration and not slow"

# GPU tests only
pytest -m gpu
```

### By Test File

```bash
# Specific scenario
pytest tests/e2e/scenarios/test_inference_flow.py

# Specific test
pytest tests/e2e/scenarios/test_inference_flow.py::TestBasicInference::test_simple_inference
```

### With Options

```bash
# Verbose output with short traceback
pytest -v --tb=short

# Stop on first failure
pytest -x

# Run in parallel (4 workers)
pytest -n 4

# Generate coverage report
pytest --cov=tests --cov-report=html
```

## Performance Testing

### K6 Load Test

```bash
# Basic load test
k6 run tests/load/k6/inference_load_test.js

# Custom configuration
k6 run -e MODEL=llama2-7b -e ENDPOINT=http://localhost:8000 \
  --vus 100 --duration 10m tests/load/k6/inference_load_test.js
```

### Locust Load Test

```bash
# Headless mode
locust -f tests/load/locust/locustfile.py \
  --host http://localhost:8000 \
  --users 100 --spawn-rate 10 --run-time 5m \
  --headless

# Web UI mode
locust -f tests/load/locust/locustfile.py \
  --host http://localhost:8000
```

## Test Reports

### Generate HTML Report

```bash
# After running tests
./e2e/generate_test_report.py --format html --report-dir reports
```

### Report Contents

- **Summary**: Overall test results
- **Scenario Results**: Per-scenario breakdown
- **Performance Metrics**: Response times, throughput
- **Issues**: Failed tests and threshold violations
- **Charts**: Visual representations of results

### Report Locations

```
reports/
├── test_summary.json           # Summary data
├── test_report_*.html         # HTML reports
├── test_report_*.md           # Markdown reports
├── k6_*_summary.json          # K6 results
├── locust_report_*.html       # Locust reports
├── monitoring/                # Monitoring data
│   └── metrics_*.json
└── charts/                    # Generated charts
    ├── test_results.png
    └── performance_comparison.png
```

## CI/CD Integration

### GitHub Actions Example

```yaml
- name: Run E2E Tests
  run: |
    ./tests/e2e/run_tests.py \
      --scenario smoke \
      --report junit \
      --parallel 4

- name: Upload Test Results
  uses: actions/upload-artifact@v3
  with:
    name: test-results
    path: tests/reports/
```

### Jenkins Pipeline Example

```groovy
stage('E2E Tests') {
    steps {
        sh './tests/e2e/run_tests.py --scenario integration --report junit'
    }
    post {
        always {
            junit 'tests/reports/junit_report.xml'
            publishHTML([
                reportDir: 'tests/reports',
                reportFiles: 'test_report_*.html',
                reportName: 'E2E Test Report'
            ])
        }
    }
}
```

## Troubleshooting

### Common Issues

1. **Connection refused errors**
   - Verify services are running: `kubectl get pods -n bud-system`
   - Check service endpoints: `kubectl get svc -n bud-system`
   - Verify ingress configuration

2. **Test timeouts**
   - Increase timeout in pytest.ini
   - Check resource availability
   - Review service logs

3. **GPU tests failing**
   - Verify GPU operator installation
   - Check node GPU availability: `kubectl describe nodes`
   - Ensure GPU models are deployed

4. **Performance test failures**
   - Reduce concurrent users
   - Increase test duration
   - Check cluster resources

### Debug Mode

```bash
# Run with debug logging
LOG_LEVEL=DEBUG ./e2e/run_tests.py --scenario smoke

# Run with pytest debug
pytest -vvs --log-cli-level=DEBUG

# Capture stdout
pytest --capture=no
```

## Contributing

When adding new tests:

1. **Use appropriate markers**: `@pytest.mark.smoke`, `@pytest.mark.slow`, etc.
2. **Follow naming conventions**: `test_<feature>_<scenario>`
3. **Add docstrings**: Describe what the test validates
4. **Handle cleanup**: Use fixtures for setup/teardown
5. **Consider timeouts**: Set appropriate timeouts for long operations
6. **Add to scenarios**: Update run_tests.py if adding new categories

## Best Practices

1. **Isolation**: Tests should not depend on each other
2. **Idempotency**: Tests should be runnable multiple times
3. **Cleanup**: Always clean up created resources
4. **Logging**: Use structured logging for debugging
5. **Assertions**: Use descriptive assertion messages
6. **Fixtures**: Reuse common setup code
7. **Data**: Use test_data.yaml for test inputs