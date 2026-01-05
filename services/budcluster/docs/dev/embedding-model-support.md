# Embedding Model Support Implementation

## Overview

This document describes the changes implemented to add embedding model support to the bud-serve-cluster service.

## Changes Implemented

### 1. Automatic Endpoint Detection

**File**: `budcluster/cluster_ops/kubernetes.py`

Added `identify_supported_endpoints` method that checks which API endpoints a deployed model supports:
- Tests `/v1/embeddings` endpoint with a minimal POST request
- Tests `/v1/chat/completions` endpoint
- Returns a dictionary of endpoint availability

**File**: `budcluster/cluster_ops/__init__.py`

Exported the `identify_supported_endpoints` function for use by other modules.

**File**: `budcluster/deployment/handler.py`

Added `identify_supported_endpoints` method to `DeploymentHandler` class to expose endpoint detection capability.

### 2. Model Type Detection in Workflows

**File**: `budcluster/deployment/workflows.py`

#### Automatic Model Type Detection
- After verifying deployment health, the workflow calls `identify_supported_endpoints`
- If `/v1/embeddings` endpoint is available, sets `model_type = "embedding"`
- Otherwise, sets `model_type = "llm"`

#### Changes in `deploy_model_workflow`:
```python
# Line 943-947
model_type = "llm"
if verify_deployment_health_result["param"]["supported_endpoints"].get("/v1/embeddings"):
    model_type = "embedding"
```

#### Pass Model Type to Performance Benchmark:
- Added `model_type` field to `RunPerformanceBenchmarkRequest` (line 956)
- Included `supported_endpoints` in workflow result (line 1022)

### 3. Performance Benchmarking for Embeddings

**File**: `budcluster/deployment/performance.py`

#### Benchmark Script Selection
- Added `model_type` parameter to `DeploymentPerformance` constructor
- When `model_type == "embedding"`, uses `budlatent` benchmark script instead of `vllm`

```python
# Lines 47-50
if model_type == "embedding":
    self.benchmark_script = "budlatent"
else:
    self.benchmark_script = "vllm"
```

#### Performance Verification
- For embedding models, only verifies e2e latency (no TTFT or throughput checks)

```python
# Lines 67-70
if self.model_type == "embedding":
    return not (
        result["mean_e2el_ms"] > self.target_e2e_latency * (1 + self.error_threshold)
    )
```

### 4. Schema Updates

**File**: `budcluster/deployment/schemas.py`

- Added `model_type: Optional[str] = None` to `RunPerformanceBenchmarkRequest` (line 167)
- Added `supported_endpoints: List[str]` to `DeployModelWorkflowResult` (line 208)

### 5. Infrastructure Updates

**File**: `deploy/Dockerfile`
- Updated llm-benchmark version from v1.0.0 to v1.1.0 (includes budlatent tool)

**File**: `budcluster/charts/bud_runtime_container/templates/_cuda.yaml`
- Increased liveness probe `failureThreshold` to 20 (better tolerance for slow model loading)

**File**: `budcluster/deployment/handler.py`
- Removed problematic vLLM args: `scheduler-delay-factor` and `enable-chunked-prefill`

## How It Works

1. **Deployment**: When a model is deployed, the system doesn't need to know if it's an embedding model upfront
2. **Health Check**: After deployment, the system verifies the model is available by checking `/v1/models`
3. **Endpoint Detection**: The system then probes available endpoints to determine model capabilities
4. **Model Type Assignment**: If `/v1/embeddings` is available, the model is classified as "embedding"
5. **Benchmarking**: Based on model type, appropriate benchmark tool is selected (budlatent for embeddings)
6. **Performance Verification**: For embeddings, only e2e latency is checked (TTFT and throughput are not applicable)

## Usage

No API changes are required. The system automatically detects embedding models based on their exposed endpoints. Users can deploy embedding models the same way as text generation models:

```bash
curl -X POST http://localhost:8080/api/v1/deployments \
  -H "Content-Type: application/json" \
  -d '{
    "cluster_id": "your-cluster-id",
    "endpoint_name": "bge-embeddings",
    "model": "BAAI/bge-base-en-v1.5",
    "concurrency": 100,
    "target_e2e_latency": 50
  }'
```

The system will:
1. Deploy the model using vLLM
2. Detect it supports `/v1/embeddings`
3. Run benchmarks using `budlatent`
4. Verify only e2e latency performance

## Notes

- vLLM automatically detects model type and exposes appropriate endpoints
- No changes to deployment templates needed - vLLM handles both model types
- The implementation leverages existing infrastructure with minimal changes
