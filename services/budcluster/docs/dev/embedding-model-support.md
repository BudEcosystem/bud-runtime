# Embedding Model Support Implementation

## Overview

This document describes the changes implemented to add embedding model support to the bud-serve-cluster service.

## API Documentation

### Embedding Endpoint (`/v1/embeddings`)

#### Base Fields

| Field           | Type             | Default                 | Supported Values                              |
|-----------------|------------------|-------------------------|-----------------------------------------------|
| model           | str              | "default/not-specified" | Any deployed model name                       |
| input           | str \| list[str] | required                | Text strings, URLs, or data:<mime>;base64,... |
| encoding_format | str              | "float"                 | "float", "base64"                             |
| modality        | str              | "text"                  | "text", "image", "audio"                      |
| dimensions      | int              | 0                       | 0 (full), or model-supported dimensions       |
| priority        | str \| null      | null                    | "high", "normal", "low", null                 |
| user            | str \| null      | null                    | Any string                                    |

#### Text-only Fields

| Field         | Type          | Default | Supported Values      |
|---------------|---------------|---------|----------------------|
| include_input | bool          | false   | true, false          |
| chunking      | object \| null| null    | ChunkingConfig object|

### ChunkingConfig Schema

#### Core Parameters

| Field         | Type | Default       | Supported Values                                              |
|---------------|------|---------------|---------------------------------------------------------------|
| enabled       | bool | false         | true, false                                                   |
| strategy      | str  | "token"       | "token", "sentence", "recursive", "semantic", "code", "table" |
| chunk_size    | int  | 512           | 1 - 8192                                                      |
| chunk_overlap | int  | 0             | 0 - chunk_size-1                                              |
| tokenizer     | str  | "cl100k_base" | "cl100k_base", "p50k_base", "r50k_base", "gpt2", etc.         |

#### Sentence Strategy

| Field         | Type             | Default | Supported Values              |
|---------------|------------------|---------|-------------------------------|
| min_sentences | int              | 1       | >= 1                          |
| delimiters    | list[str] \| null| null    | e.g. [". ", "! ", "? ", "\n"] |

#### Recursive Strategy

| Field  | Type        | Default | Supported Values |
|--------|-------------|---------|------------------|
| recipe | str \| null | null    | "markdown", null |

#### Semantic Strategy

| Field              | Type  | Default                     | Supported Values                |
|--------------------|-------|-----------------------------|---------------------------------|
| semantic_threshold | float | 0.8                         | 0.0 - 1.0                       |
| semantic_model     | str   | "minishlab/potion-base-32M" | Any sentence-transformers model |
| semantic_window    | int   | 3                           | >= 1                            |

#### Code Strategy

| Field    | Type        | Default     | Supported Values                                   |
|----------|-------------|-------------|----------------------------------------------------|
| language | str \| null | null (auto) | "python", "javascript", "typescript", "java", etc. |

#### Preprocessing (Chef)

| Field | Type        | Default | Supported Values                  |
|-------|-------------|---------|-----------------------------------|
| chef  | str \| null | null    | "text", "markdown", "table", null |

- **"text"** - Normalize whitespace, remove excessive newlines
- **"markdown"** - Strip markdown formatting (headers, bold, links, code blocks)
- **"table"** - Preserve table structure, normalize cell content

#### Pipeline Mode

| Field    | Type             | Default | Supported Values                               |
|----------|------------------|---------|------------------------------------------------|
| pipeline | list[str] \| null| null    | e.g. ["sentence", "token"], ["recursive", "semantic"] |

When pipeline is set, it overrides strategy. Chunkers run sequentially - output from one becomes input to the next.

#### Overlap Refinery

| Field               | Type        | Default  | Supported Values                         |
|---------------------|-------------|----------|------------------------------------------|
| add_overlap_context | bool        | false    | true, false                              |
| overlap_size        | int \| float| 0.25     | Integer (tokens) or float (fraction 0-1) |
| overlap_method      | str         | "suffix" | "prefix", "suffix"                       |

#### Response Options

| Field             | Type | Default | Supported Values |
|-------------------|------|---------|------------------|
| return_chunk_text | bool | true    | true, false      |

### Classify Endpoint (`/v1/classify`)

#### Fields

| Field      | Type             | Default                 | Supported Values              |
|------------|------------------|-------------------------|-------------------------------|
| model      | str              | "default/not-specified" | Any deployed classifier model |
| input      | list[str]        | required                | Text strings to classify      |
| raw_scores | bool             | false                   | true, false                   |
| priority   | str \| null      | null                    | "high", "normal", "low", null |

### Example Requests

#### Basic Text Embedding

```json
{
  "model": "BAAI/bge-small-en-v1.5",
  "input": ["Hello world"]
}
```

#### With Priority and Dimensions

```json
{
  "model": "BAAI/bge-small-en-v1.5",
  "input": ["Important query"],
  "priority": "high",
  "dimensions": 384
}
```

#### Sentence Chunking with Markdown Preprocessing

```json
{
  "model": "BAAI/bge-small-en-v1.5",
  "input": ["# Title\n\nLong markdown document..."],
  "chunking": {
    "enabled": true,
    "strategy": "sentence",
    "chunk_size": 256,
    "min_sentences": 2,
    "chef": "markdown"
  }
}
```

#### Pipeline: Sentence -> Token with Overlap

```json
{
  "model": "BAAI/bge-small-en-v1.5",
  "input": ["Very long document..."],
  "chunking": {
    "enabled": true,
    "pipeline": ["sentence", "token"],
    "chunk_size": 512,
    "add_overlap_context": true,
    "overlap_size": 64,
    "overlap_method": "suffix"
  }
}
```

#### Code Chunking

```json
{
  "model": "BAAI/bge-small-en-v1.5",
  "input": ["def foo():\n    pass\n\nclass Bar:\n    ..."],
  "chunking": {
    "enabled": true,
    "strategy": "code",
    "language": "python",
    "chunk_size": 1024
  }
}
```

#### Semantic Chunking

```json
{
  "model": "BAAI/bge-small-en-v1.5",
  "input": ["Document with multiple topics..."],
  "chunking": {
    "enabled": true,
    "strategy": "semantic",
    "semantic_threshold": 0.7,
    "semantic_model": "minishlab/potion-base-32M",
    "chunk_size": 512
  }
}
```

#### Image Embedding

```json
{
  "model": "openai/clip-vit-base-patch32",
  "input": ["http://example.com/image.jpg"],
  "modality": "image",
  "encoding_format": "base64"
}
```

#### Classification Request

```json
{
  "model": "ProsusAI/finbert",
  "input": ["The stock market is performing well today"],
  "raw_scores": false,
  "priority": "high"
}
```

---

## Implementation Details

### 1. Automatic Endpoint Detection

**File**: `budcluster/cluster_ops/kubernetes.py`

Added `identify_supported_endpoints` method that checks which API endpoints a deployed model supports:
- Tests `/v1/embeddings` endpoint with a minimal POST request
- Tests `/v1/chat/completions` endpoint
- Tests `/v1/classify` endpoint for classifier models (e.g., FinBERT, BERT-based classifiers)
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
- If `/v1/classify` endpoint is available, sets `model_type = "classifier"`
- Otherwise, sets `model_type = "llm"`

#### Changes in `deploy_model_workflow`:
```python
model_type = "llm"
if verify_deployment_health_result["param"]["supported_endpoints"].get("/v1/embeddings"):
    model_type = "embedding"
if verify_deployment_health_result["param"]["supported_endpoints"].get("/v1/classify"):
    model_type = "classifier"
```

#### Pass Model Type to Performance Benchmark:
- Added `model_type` field to `RunPerformanceBenchmarkRequest`
- Included `supported_endpoints` in workflow result

### 3. Performance Benchmarking for Embeddings

**File**: `budcluster/deployment/performance.py`

#### Benchmark Script Selection
- Added `model_type` parameter to `DeploymentPerformance` constructor
- When `model_type == "embedding"`, uses `budlatent` benchmark script instead of `vllm`

```python
if model_type == "embedding":
    self.benchmark_script = "budlatent"
else:
    self.benchmark_script = "vllm"
```

#### Performance Verification
- For embedding models, only verifies e2e latency (no TTFT or throughput checks)

```python
if self.model_type == "embedding":
    return not (
        result["mean_e2el_ms"] > self.target_e2e_latency * (1 + self.error_threshold)
    )
```

### 4. Schema Updates

**File**: `budcluster/deployment/schemas.py`

- Added `model_type: Optional[str] = None` to `RunPerformanceBenchmarkRequest`
- Added `supported_endpoints: List[str]` to `DeployModelWorkflowResult`

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
4. **Model Type Assignment**: Based on endpoint availability:
   - `/v1/embeddings` available -> "embedding"
   - `/v1/classify` available -> "classifier"
   - Otherwise -> "llm"
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
