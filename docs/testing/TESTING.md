# E2E Testing Guide

This guide covers end-to-end testing of the Bud Runtime inference stack across multiple Kubernetes clusters.

## Overview

The E2E testing framework validates the complete inference pipeline:
```
User Request → BudProxy (App Cluster) → AIBrix (Inference Cluster) → VLLM (Inference Cluster) → Response
```

## Prerequisites

- Multi-cluster environment setup (see [MULTI-CLUSTER-SETUP.md](MULTI-CLUSTER-SETUP.md))
- Services deployed to both clusters
- Python 3.8+ with pytest installed
- (Optional) K6 or Locust for load testing

## Test Categories

### 1. Inference Flow Tests
Validate end-to-end inference requests through the complete pipeline.

**Test Scenarios:**
- Single model inference
- Multi-model routing
- Batch inference requests
- Streaming responses
- Token generation limits

### 2. Routing Tests
Verify BudProxy correctly routes requests to appropriate models.

**Test Scenarios:**
- Model selection based on request
- Load balancing across VLLM instances
- Fallback routing on failure
- A/B testing configurations

### 3. Autoscaling Tests
Validate dynamic scaling based on load.

**Test Scenarios:**
- VLLM pod scaling on high load
- Scale down on idle
- GPU resource allocation
- Queue management during scaling

### 4. Failover Tests
Ensure system resilience and recovery.

**Test Scenarios:**
- VLLM instance failure
- AIBrix control plane failure
- Network partition between clusters
- GPU failure simulation

### 5. Performance Tests
Measure and validate performance metrics.

**Test Scenarios:**
- Latency benchmarks
- Throughput testing
- Concurrent request handling
- Resource utilization

## Running Tests

### Quick Test Suite
```bash
# Run basic E2E tests
cd tests/e2e
pytest -v test_inference_flow.py

# Run with specific cluster configuration
pytest -v test_inference_flow.py \
  --app-cluster k3d-bud-app \
  --inference-cluster k3d-bud-inference
```

### Full Test Suite
```bash
# Run all E2E tests
cd tests/e2e
pytest -v

# Run with detailed output
pytest -v -s --log-cli-level=INFO

# Run specific test categories
pytest -v -k "routing"
pytest -v -k "autoscaling"
pytest -v -k "failover"
```

### Load Testing
```bash
# Using K6
k6 run tests/load/inference_load_test.js

# Using Locust
locust -f tests/load/locustfile.py \
  --host http://localhost:8080 \
  --users 100 \
  --spawn-rate 10
```

## Test Configuration

### Environment Variables
```bash
# Cluster endpoints
export APP_CLUSTER_ENDPOINT=http://localhost:8080
export INFERENCE_CLUSTER_ENDPOINT=http://localhost:8081

# Test parameters
export TEST_MODEL_NAME=llama-2-7b
export TEST_TIMEOUT=300
export TEST_MAX_TOKENS=1000

# Authentication (if enabled)
export TEST_API_KEY=your-api-key
```

### Test Configuration File
Create `tests/e2e/config.yaml`:
```yaml
clusters:
  application:
    name: bud-app
    endpoint: http://localhost:8080
    context: k3d-bud-app
  inference:
    name: bud-inference
    endpoint: http://localhost:8081
    context: k3d-bud-inference

models:
  - name: llama-2-7b
    type: text-generation
    max_tokens: 4096
  - name: mistral-7b
    type: text-generation
    max_tokens: 8192

test_data:
  prompts:
    - "Explain quantum computing in simple terms"
    - "Write a Python function to calculate fibonacci"
    - "What are the benefits of Kubernetes?"
```

## Writing Custom Tests

### Basic E2E Test Example
```python
import pytest
import requests
import time
from kubernetes import client, config

class TestInferenceFlow:
    @pytest.fixture(scope="class")
    def setup_clusters(self):
        """Setup Kubernetes clients for both clusters"""
        config.load_kube_config(context="k3d-bud-app")
        self.app_k8s = client.CoreV1Api()
        
        config.load_kube_config(context="k3d-bud-inference")
        self.inf_k8s = client.CoreV1Api()
    
    def test_simple_inference(self, setup_clusters):
        """Test a simple inference request"""
        # Send request to BudProxy
        response = requests.post(
            "http://localhost:8080/v1/completions",
            json={
                "model": "llama-2-7b",
                "prompt": "Hello, world!",
                "max_tokens": 50
            },
            headers={"Authorization": "Bearer test-key"}
        )
        
        assert response.status_code == 200
        result = response.json()
        assert "choices" in result
        assert len(result["choices"]) > 0
        assert "text" in result["choices"][0]
```

### Load Test Example
```javascript
// k6 load test script
import http from 'k6/http';
import { check, sleep } from 'k6';

export let options = {
  stages: [
    { duration: '2m', target: 10 },  // Ramp up
    { duration: '5m', target: 50 },  // Stay at 50 users
    { duration: '2m', target: 0 },   // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<2000'], // 95% of requests under 2s
    http_req_failed: ['rate<0.1'],     // Error rate under 10%
  },
};

export default function() {
  const payload = JSON.stringify({
    model: 'llama-2-7b',
    prompt: 'Generate a random fact',
    max_tokens: 100,
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer test-key',
    },
  };

  const res = http.post('http://localhost:8080/v1/completions', payload, params);
  
  check(res, {
    'status is 200': (r) => r.status === 200,
    'response has choices': (r) => JSON.parse(r.body).choices !== undefined,
  });
  
  sleep(1);
}
```

## Monitoring During Tests

### Real-time Metrics
```bash
# Watch pod status during tests
watch kubectl --context k3d-bud-inference get pods -n vllm-system

# Monitor GPU usage
watch nvidia-smi

# View logs
kubectl --context k3d-bud-app logs -f -n bud-system -l app=budproxy
kubectl --context k3d-bud-inference logs -f -n vllm-system -l app=vllm
```

### Grafana Dashboards
1. Application Metrics: http://localhost:8080
2. Inference Metrics: http://localhost:8081
3. Key dashboards:
   - Request Rate and Latency
   - GPU Utilization
   - Pod Autoscaling
   - Error Rates

## Test Reports

### Generate HTML Report
```bash
# Install pytest-html
pip install pytest-html

# Run tests with HTML report
pytest -v --html=report.html --self-contained-html
```

### Generate JUnit XML (for CI/CD)
```bash
pytest -v --junitxml=junit.xml
```

## CI/CD Integration

### GitHub Actions Example
```yaml
name: E2E Tests
on: [push, pull_request]

jobs:
  e2e-tests:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Setup Multi-Cluster
      run: |
        ./scripts/multi-cluster/setup-multi-cluster.sh \
          --enable-gpu false \
          --parallel
    
    - name: Deploy Services
      run: |
        # Deploy your services here
        
    - name: Run E2E Tests
      run: |
        cd tests/e2e
        pytest -v --junitxml=junit.xml
    
    - name: Upload Test Results
      uses: actions/upload-artifact@v3
      with:
        name: test-results
        path: tests/e2e/junit.xml
    
    - name: Cleanup
      if: always()
      run: |
        ./scripts/multi-cluster/utils/cleanup-clusters.sh \
          --all --force
```

## Debugging Failed Tests

### Common Issues

1. **Connection Refused**
   - Check service endpoints
   - Verify port forwarding
   - Check network policies

2. **Timeout Errors**
   - Increase test timeouts
   - Check pod readiness
   - Monitor resource limits

3. **Authentication Failures**
   - Verify API keys
   - Check RBAC policies
   - Review service accounts

### Debug Commands
```bash
# Check service endpoints
kubectl --context k3d-bud-app get endpoints -n bud-system

# Test connectivity between clusters
kubectl --context k3d-bud-app run test-curl --rm -it \
  --image=curlimages/curl -- sh

# Check pod logs
kubectl --context k3d-bud-inference logs -n vllm-system \
  -l app=vllm --tail=50

# Describe failing pods
kubectl --context k3d-bud-inference describe pod -n vllm-system <pod-name>
```

## Best Practices

1. **Test Isolation**: Each test should be independent
2. **Cleanup**: Always cleanup resources after tests
3. **Timeouts**: Set appropriate timeouts for different operations
4. **Retries**: Implement retry logic for transient failures
5. **Logging**: Use structured logging for better debugging
6. **Assertions**: Make assertions specific and meaningful
7. **Test Data**: Use consistent test data across runs
8. **Monitoring**: Always monitor resource usage during tests

## Using Mock vLLM for Testing

For integration testing without GPU resources, you can use the mock vLLM service that provides the same API interface but returns simulated responses.

### Deploying Mock vLLM

```bash
# Deploy mock vLLM to the inference cluster
./scripts/deploy/deploy-mock-vllm.sh

# Switch to mock vLLM for testing
./scripts/deploy/switch-vllm-mode.sh --mode mock

# Run your tests...

# Switch back to real vLLM when needed
./scripts/deploy/switch-vllm-mode.sh --mode real
```

### Benefits of Mock vLLM

1. **No GPU Required**: Runs on CPU-only nodes
2. **Fast Startup**: Seconds instead of minutes
3. **Low Resources**: Uses <512MB RAM vs 16GB+ for real vLLM
4. **Deterministic**: Responses based on input for consistent testing
5. **Full API Coverage**: All vLLM endpoints implemented

### When to Use Mock vs Real vLLM

**Use Mock vLLM for:**
- Integration testing
- CI/CD pipelines
- Development environments
- Testing request routing and error handling

**Use Real vLLM for:**
- Performance benchmarking
- Model accuracy testing
- Production validation
- Load testing with realistic inference times

See [Mock vLLM Deployment Guide](./mock-vllm-deployment.md) and [Mock vLLM in Inference Cluster](./inference-cluster-mock-vllm.md) for detailed instructions.

## Next Steps

1. Extend test coverage for your specific use cases
2. Integrate with your CI/CD pipeline
3. Set up automated performance regression testing
4. Create chaos engineering tests
5. Implement security testing scenarios