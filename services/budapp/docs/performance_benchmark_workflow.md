# Run Performance Benchmark Workflow

API : POST /benchmark/run-workflow

## Steps for Running Performance Benchmark

### Step 1: Provide Basic Info

Give:
- Name
- Tags
- Description
- Concurrent requests
- Evaluation method: `configuration` or `dataset`

### Step 2: Evaluation Details

- If **evaluation method is "configuration"**: specify `max_input_tokens` and `max_output_tokens`
- If **evaluation method is "dataset"**: choose datasets from the list

### Step 3: Choose Cluster

Select the cluster where the benchmark should run.

### Step 4: Choose Nodes

Pick the specific nodes within the cluster.

### Step 5: Choose Model

Choose the model to run the benchmark.

#### Step 5.1: If Model is Cloud-Based

Select the cloud model credential.

### Step 6: Confirm Benchmark Details

User confirmation of all benchmark details.

### Step 7: Execution Option

Choose either:
- `Simulate` (currently not operational)
- `Run on cluster`

### Step 8: Deployment

Trigger deployment steps which are performed by budcluster microservice.
- Verify cluster connection
- Transfer model to cluster (this step is skipped if benchmark is requested for cloud model)
- Deploy model engine
  - for cloud model, deployed engine is instance of litellm server.
  - for local model, deployed engine is instance of budruntime server.
- Verify model deployment
- Run performance benchmark

If successful, workflow ends with a success step; otherwise, an error event is published to budapp microservice.
Cleanup is performed in both success and failure conditions. Deployed model is deleted and cluster resources are freed.

---

## Example JSON Payloads

### Step 1

<details>
<summary>Configuration method</summary>

```json
{
  "name": "test-111",
  "tags": [],
  "description": "test-111",
  "concurrent_requests": 50,
  "eval_with": "configuration",
  "workflow_total_steps": 9,
  "step_number": 1,
  "trigger_workflow": false
}
```
</details>

<details>
<summary>Dataset method</summary>

```json
{
  "name": "test-111",
  "tags": [],
  "description": "test-111",
  "concurrent_requests": 50,
  "eval_with": "dataset",
  "workflow_total_steps": 9,
  "step_number": 1,
  "trigger_workflow": false
}
```
</details>

---

### Step 2

<details>
<summary>Using Configuration</summary>

```json
{
  "name": "test-111",
  "tags": [],
  "description": "test-111",
  "concurrent_requests": 50,
  "eval_with": "configuration",
  "workflow_id": "dcfddf9b-5f07-47e9-8483-24f546bb7667",
  "step_number": 2,
  "trigger_workflow": false,
  "max_input_tokens": 50,
  "max_output_tokens": 100
}
```
</details>

<details>
<summary>Using Dataset</summary>

```json
{
  "name": "test-111",
  "tags": [],
  "description": "test-111",
  "concurrent_requests": 50,
  "eval_with": "dataset",
  "workflow_id": "dcfddf9b-5f07-47e9-8483-24f546bb7667",
  "step_number": 2,
  "trigger_workflow": false,
  "datset_ids": ["effddf9b-5f07-47e9-8483-24f546bb7667"]
}
```
</details>

---

### Step 3: Choose Cluster

```json
{
  "name": "test-111",
  "tags": [],
  "description": "test-111",
  "concurrent_requests": 50,
  "eval_with": "configuration",
  "workflow_id": "9e4aa5c6-d2df-42ab-8972-a954bd7f6485",
  "step_number": 3,
  "trigger_workflow": false,
  "cluster_id": "1fbb9c3c-4198-4e7e-8a1e-02b86041ea82"
}
```

---

### Step 4: Choose Nodes

Node json is response of GET node-metrics API

```json
{
  "name": "test-111",
  "tags": [],
  "description": "test-111",
  "concurrent_requests": 50,
  "eval_with": "configuration",
  "workflow_id": "9e4aa5c6-d2df-42ab-8972-a954bd7f6485",
  "step_number": 4,
  "trigger_workflow": false,
  "nodes": [
    {
      "hostname": "fl4u42",
      "status": "Ready",
      "devices": [
        {
          "name": "Intel(R) Xeon(R) Platinum 8480+",
          "type": "cpu",
          "device_info": {
            "num_virtual_cores": 224
          },
          "device_config": {
            "peak_fp16_TFLOPS": 329.00454400000007
          },
          "available_count": 8
        }
      ]
    }
  ]
}
```

---

### Step 5: Choose Model

```json
{
  "name": "test-111",
  "tags": [],
  "description": "test-111",
  "concurrent_requests": 50,
  "eval_with": "configuration",
  "workflow_id": "9e4aa5c6-d2df-42ab-8972-a954bd7f6485",
  "step_number": 5,
  "model_id": "30cc08ec-465c-4041-898e-a08e3889cee9"
}
```

---

### Step 6: Cloud Credential (If Cloud Model)

```json
{
  "name": "test-111",
  "tags": [],
  "description": "test-111",
  "concurrent_requests": 50,
  "eval_with": "configuration",
  "workflow_id": "9e4aa5c6-d2df-42ab-8972-a954bd7f6485",
  "step_number": 6,
  "credential_id": "22d4bb50-d574-4cb1-8b09-0b00138b2bcc"
}
```

---

### Step 7: User Confirmation

```json
{
  "name": "test-111",
  "tags": [],
  "description": "test-111",
  "concurrent_requests": 50,
  "eval_with": "configuration",
  "workflow_id": "9e4aa5c6-d2df-42ab-8972-a954bd7f6485",
  "step_number": 7,
  "user_confirmation": true
}
```

---

### Step 8: Execute

```json
{
  "name": "test-111",
  "tags": [],
  "description": "test-111",
  "concurrent_requests": 50,
  "eval_with": "configuration",
  "workflow_id": "9e4aa5c6-d2df-42ab-8972-a954bd7f6485",
  "step_number": 8,
  "run_as_simulation": false,
  "trigger_workflow": true
}
```

# List all benchmarks

API: GET /benchmark

```python
curl -X 'GET' \
  'https://bud-app-dev.bud.studio/benchmark?page=1&limit=1&search=true&name=test-11' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer <token>'
```

Sample Response:

```json
{
  "object": "benchmarks.list",
  "message": "Successfully list all benchmarks",
  "page": 1,
  "limit": 1,
  "total_record": 3,
  "benchmarks": [
    {
      "id": "220f5283-121b-480e-91e8-b71097f2877f",
      "name": "test-111",
      "status": "processing",
      "model": {
        "id": "30cc08ec-465c-4041-898e-a08e3889cee9",
        "name": "chatgpt-3-5",
        "author": null,
        "modality": "llm",
        "source": "openai",
        "uri": "gpt-3.5-turbo-0125",
        "created_user": null,
        "model_size": null,
        "tasks": [],
        "tags": [
          {
            "name": "cloud",
            "color": "#479D5F"
          },
          {
            "name": "openai",
            "color": "#D1B854"
          },
          {
            "name": "gpt-3.5-turbo",
            "color": "#EEEEEE"
          }
        ],
        "icon": null,
        "description": "Fine-tuning for GPT-3.5 Turbo is now available, with fine-tuning for GPT-4 coming this fall. This update gives developers the ability to customize models that perform better for their use cases and run these custom models at scale. Early tests have shown a fine-tuned version of GPT-3.5 Turbo can match, or even outperform, base GPT-4-level capabilities on certain narrow ta",
        "provider_type": "cloud_model",
        "created_at": "2025-01-03T22:19:14.213380Z",
        "modified_at": "2025-04-15T13:26:27.089755Z",
        "provider": null,
        "is_present_in_model": null,
        "model_cluster_recommended": null
      },
      "cluster": {
        "id": "1fbb9c3c-4198-4e7e-8a1e-02b86041ea82",
        "name": "Dev cluster",
        "icon": "😍",
        "ingress_url": "http://20.244.107.114:13025/",
        "cluster_type": "ON_PERM",
        "created_at": "2025-03-05T14:23:09.647681Z",
        "modified_at": "2025-03-24T00:33:25.049724Z",
        "status": "available",
        "cluster_id": "ef8b285a-07ef-4659-bb90-d5a96f57789f",
        "cpu_count": 1,
        "gpu_count": 0,
        "hpu_count": 0,
        "cpu_total_workers": 1,
        "cpu_available_workers": 1,
        "gpu_total_workers": 0,
        "gpu_available_workers": 0,
        "hpu_total_workers": 0,
        "hpu_available_workers": 0,
        "total_nodes": 1,
        "available_nodes": 1
      },
      "node_type": "cpu",
      "vendor_type": "AMD EPYC 7763 64-Core Processor",
      "concurrency": 50,
      "tpot": 0.44,
      "ttft": 0.2,
      "created_at": "2025-03-20T19:12:15.633452Z",
      "eval_with": "configuration",
      "dataset_ids": null,
      "max_input_tokens": 50,
      "max_output_tokens": 100
    }
  ],
  "total_pages": 3
}
```

# Get benchmark result

API: GET /benchmark/result

```python
curl -X 'GET' \
  'https://bud-app-dev.bud.studio/benchmark/result?benchmark_id=58f55925-ff56-4db6-93d1-df39bae9d3b5' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer <token>'
```

Sample Response :

```json
{
  "object": "benchmark.result",
  "message": "Successfully fetched benchmark result",
  "param": {
    "result": {
      "p75_throughput": 4.300698902318045,
      "p25_ttft_ms": 2569.148689508438,
      "p25_tpot_ms": 0.015527673531323673,
      "p25_itl_ms": 0.004825007636100054,
      "p25_e2el_ms": 2569.315565750003,
      "modified_at": "2025-04-02T08:33:53.117246Z",
      "successful_requests": 10,
      "p95_throughput": 4.588590623106642,
      "p75_ttft_ms": 3401.8989767646417,
      "p75_tpot_ms": 0.021012703655287623,
      "p75_itl_ms": 0.009750074241310358,
      "p75_e2el_ms": 3402.0501280319877,
      "total_input_tokens": 362,
      "p99_throughput": 4.624298499975314,
      "p95_ttft_ms": 5160.884857946074,
      "p95_tpot_ms": 0.02514269552193582,
      "p95_itl_ms": 2447.7159860543898,
      "p95_e2el_ms": 5161.0546293319185,
      "duration": 5.881510099163279,
      "total_output_tokens": 110,
      "min_throughput": 1.8702679778727054,
      "p99_ttft_ms": 5737.269610133953,
      "p99_tpot_ms": 0.026204691035673026,
      "p99_itl_ms": 3850.991507018908,
      "p99_e2el_ms": 5737.419005197007,
      "benchmark_id": "b05ee56a-72a3-4b25-b66a-87f9b33cead0",
      "id": "621bc745-d815-447b-9a1f-ee03aed51bf9",
      "request_throughput": 38.91524578973733,
      "max_throughput": 4.633225469192483,
      "min_ttft_ms": 2373.891287948936,
      "min_tpot_ms": 0.014430098235607147,
      "min_itl_ms": 0.0036009587347507477,
      "min_e2el_ms": 2374.1559898480773,
      "input_throughput": 1408.7318975884914,
      "mean_ttft_ms": 3348.7767771352082,
      "max_ttft_ms": 5881.365798180923,
      "max_tpot_ms": 0.026470189914107323,
      "max_itl_ms": 5881.365798180923,
      "max_e2el_ms": 5881.510099163279,
      "output_throughput": 7.13446172811851,
      "median_ttft_ms": 3190.8154611010104,
      "mean_tpot_ms": 0.0189321581274271,
      "mean_itl_ms": 223.25901988117644,
      "mean_e2el_ms": 3348.9660987164825,
      "created_at": "2025-04-02T08:33:53.117240Z",
      "p25_throughput": 3.233348778128036,
      "median_tpot_ms": 0.01861514756456018,
      "median_itl_ms": 0.0073499977588653564,
      "median_e2el_ms": 3191.0227625630796
    }
  }
}
```

# Fetch model and cluster details of a benchmark

API: GET /benchmark/<benchmark_id>/model-cluster-detail

```python
curl -X 'GET' \
  'https://bud-app-dev.bud.studio/benchmark/58f55925-ff56-4db6-93d1-df39bae9d3b5/model-cluster-detail' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer <token>'
```
Sample Response :

```json
{
  "object": "benchmark.model.cluster.detail",
  "message": "Successfully fetched model cluster detail for the benchmark.",
  "result": {
    "id": "58f55925-ff56-4db6-93d1-df39bae9d3b5",
    "name": "sonali-321",
    "status": "success",
    "model": {
      "id": "30cc08ec-465c-4041-898e-a08e3889cee9",
      "name": "chatgpt-3-5",
      "description": "Fine-tuning for GPT-3.5 Turbo is now available, with fine-tuning for GPT-4 coming this fall. This update gives developers the ability to customize models that perform better for their use cases and run these custom models at scale. Early tests have shown a fine-tuned version of GPT-3.5 Turbo can match, or even outperform, base GPT-4-level capabilities on certain narrow ta",
      "tags": [
        {
          "name": "cloud",
          "color": "#479D5F"
        },
        {
          "name": "openai",
          "color": "#D1B854"
        },
        {
          "name": "gpt-3.5-turbo",
          "color": "#EEEEEE"
        }
      ],
      "tasks": [],
      "author": null,
      "model_size": null,
      "icon": null,
      "github_url": "https://github.com/BudEcosystem/",
      "huggingface_url": "https://github.com/BudEcosystem/",
      "website_url": "https://www.google.com/",
      "bud_verified": false,
      "scan_verified": false,
      "eval_verified": false,
      "strengths": null,
      "limitations": null,
      "languages": null,
      "use_cases": null,
      "minimum_requirements": null,
      "examples": null,
      "base_model": null,
      "model_type": null,
      "family": null,
      "model_weights_size": null,
      "kv_cache_size": null,
      "architecture_text_config": null,
      "architecture_vision_config": null,
      "modality": "llm",
      "source": "openai",
      "provider_type": "cloud_model",
      "uri": "gpt-3.5-turbo-0125",
      "paper_published": [
        {
          "id": "d3fe40c2-9252-4f24-9174-7279cfcf6b36",
          "title": "Untitled Research Paper",
          "authors": null,
          "url": "https://n/",
          "model_id": "30cc08ec-465c-4041-898e-a08e3889cee9"
        },
        {
          "id": "f88b67ae-ac95-497b-95b8-bda68ab43c93",
          "title": "Untitled Research Paper",
          "authors": null,
          "url": "https://saurabhharak.medium.com/fine-tuning-davinci-002-a-practical-guide-for-enhanced-llm-performance-f2b3ca2e8661",
          "model_id": "30cc08ec-465c-4041-898e-a08e3889cee9"
        },
        {
          "id": "108bb085-2dd2-4bfe-8277-db10042c3f74",
          "title": "Untitled Research Paper",
          "authors": null,
          "url": "https://worldofwork.io/2019/08/the-grow-coaching-model",
          "model_id": "30cc08ec-465c-4041-898e-a08e3889cee9"
        }
      ],
      "model_licenses": {
        "id": "61365faa-8a66-445d-a1f9-124005590e89",
        "name": "Template_RS21.docx.pdf",
        "url": null,
        "path": "licenses/Template_RS21.docx.pdf",
        "faqs": null,
        "license_type": null,
        "description": null,
        "suitability": null,
        "model_id": "30cc08ec-465c-4041-898e-a08e3889cee9",
        "data_type": "url"
      },
      "provider": {
        "id": "1c64b7bf-7302-45f1-bd3d-2405a23a9111",
        "name": "OpenAI",
        "description": "Offers advanced models for language, image generation, and audio conversion.",
        "type": "openai",
        "icon": "icons/providers/openai.png"
      },
      "created_at": "2025-01-03T22:19:14.213380Z"
    },
    "cluster": {
      "id": "2c3ec72b-d8b6-41a6-8425-7e046c6f3966",
      "name": "SPR Cluster",
      "icon": "🚄",
      "ingress_url": "http://20.244.107.114:10701/",
      "cluster_type": "ON_PREM",
      "created_at": "2025-03-29T16:53:33.995735Z",
      "modified_at": "2025-04-07T13:33:35.078512Z",
      "status": "available",
      "cluster_id": "60d5a04c-cebc-4d2d-a106-9f4fcc5cabe7",
      "cpu_count": 2,
      "gpu_count": 0,
      "hpu_count": 0,
      "cpu_total_workers": 16,
      "cpu_available_workers": 16,
      "gpu_total_workers": 0,
      "gpu_available_workers": 0,
      "hpu_total_workers": 0,
      "hpu_available_workers": 0,
      "total_nodes": 2,
      "available_nodes": 2
    },
    "deployment_config": null
  }
}
```

# Fetch relationship data of any two outputs of a benchmark

API: POST /benchmark/<benchmark_id>/analysis/field1_vs_field2

Acceptable values for field1 and field2:
- ttft
- tpot
- latency
- prompt_len
- output_len
- req_output_throughput
- itl

```python
curl -X 'POST' \
  'https://bud-app-dev.bud.studio/benchmark/58f55925-ff56-4db6-93d1-df39bae9d3b5/analysis/field1_vs_field2?field1=prompt_len&field2=tpot' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer <token>'
```
Sample Response :

```json
{
  "object": "benchmark.request.metrics.detail",
  "message": "Successfully fetched prompt_len vs tpot analysis data for benchmark : 58f55925-ff56-4db6-93d1-df39bae9d3b5.",
  "param": {
    "result": [
      {
        "prompt_len": 64,
        "tpot": 0.00001582009717822075
      },
      {
        "prompt_len": 12,
        "tpot": 0.000019290205091238023
      },
      {
        "prompt_len": 12,
        "tpot": 0.000020090187899768352
      },
      {
        "prompt_len": 8,
        "tpot": 0.000015430198982357978
      },
      {
        "prompt_len": 26,
        "tpot": 0.00002352020237594843
      },
      {
        "prompt_len": 9,
        "tpot": 0.000026470189914107324
      },
      {
        "prompt_len": 16,
        "tpot": 0.000021320208907127382
      },
      {
        "prompt_len": 30,
        "tpot": 0.000014430098235607148
      },
      {
        "prompt_len": 157,
        "tpot": 0.00001794009003788233
      },
      {
        "prompt_len": 28,
        "tpot": 0.000015010102652013302
      }
    ]
  }
}
```

# Add benchmark request metrics to benchmark_request_metrics table in budapp's db

API: POST /benchmark/request-metrics

This API is used internally. Not exposed to the user.

# Fetch benchmark's request metrics data for benchmark detail page table

API: GET /benchmark/request-metrics

```python
curl -X 'GET' \
  'https://bud-app-dev.bud.studio/benchmark/request-metrics?benchmark_id=58f55925-ff56-4db6-93d1-df39bae9d3b5&page=1&limit=1' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer <token>'
```
Sample Response :

```json
{
  "object": "benchmark.request.metrics.list",
  "page": 1,
  "limit": 1,
  "total_items": 10,
  "total_pages": 10,
  "items": [
    {
      "benchmark_id": "58f55925-ff56-4db6-93d1-df39bae9d3b5",
      "dataset_id": "3557d4d7-d8dc-4bd3-8969-8d5d572bb45e",
      "latency": 2.465739300008863,
      "success": true,
      "error": "",
      "prompt_len": 64,
      "output_len": 11,
      "req_output_throughput": 4.461136665972944,
      "ttft": 2.465581099037081,
      "tpot": 0.00001582009717822075,
      "itl": [
        2.465581099037081,
        0.000009500188753008842,
        0.000006200047209858894,
        0.00000509992241859436,
        0.000013800105080008507,
        0.0000057998113334178925,
        0.000004899920895695686,
        0.000006600050255656242,
        0.000004699919372797012,
        0.000004200031980872154,
        0.00000400003045797348,
        0.00000409991480410099,
        0.000003899913281202316,
        0.0000038000289350748062,
        0.0000037010759115219116
      ],
      "itl_sum": 2.465661399997771
    }
  ]
}
```

# Fetch input-distribution of a benchmark with evaluation method dataset 

API: POST /benchmark/dataset/input-distribution

```python
curl -X 'POST' \
  'https://bud-app-dev.bud.studio/benchmark/dataset/input-distribution?benchmark_id=58f55925-ff56-4db6-93d1-df39bae9d3b5&num_bins=2' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '["d830e2ab-756a-4819-a7e5-6fe1e6751275"]'
```
Sample Response :

```json
{
  "object": "benchmark.dataset.input.distribution",
  "message": "Successfully fetched dataset input distribution",
  "param": {
    "result": [
      {
        "bin_id": 1,
        "bin_range": "0.0-78.5",
        "avg_ttft": 3.71,
        "avg_tpot": 0,
        "avg_latency": 3.71,
        "p95_ttft": 5.51,
        "p95_tpot": 0,
        "p95_latency": 5.51,
        "avg_output_len": 11
      },
      {
        "bin_id": 2,
        "bin_range": "78.5-157.1",
        "avg_ttft": 3.27,
        "avg_tpot": 0,
        "avg_latency": 3.27,
        "p95_ttft": 3.27,
        "p95_tpot": 0,
        "p95_latency": 3.27,
        "avg_output_len": 11
      }
    ]
  }
}
```

# Fetch output-distribution of a benchmark with evaluation method dataset 

API: POST /benchmark/dataset/output-distribution

```python
curl -X 'POST' \
  'https://bud-app-dev.bud.studio/benchmark/dataset/output-distribution?benchmark_id=58f55925-ff56-4db6-93d1-df39bae9d3b5&num_bins=2' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '["d830e2ab-756a-4819-a7e5-6fe1e6751275"]'
```
Sample Response :

```json
{
  "object": "benchmark.dataset.input.distribution",
  "message": "Successfully fetched dataset output distribution",
  "param": {
    "result": [
      {
        "bin_id": 1,
        "bin_range": "0.0-5.5",
        "avg_ttft": 0,
        "avg_tpot": 0,
        "avg_latency": 0,
        "p95_ttft": 0,
        "p95_tpot": 0,
        "p95_latency": 0
      },
      {
        "bin_id": 2,
        "bin_range": "5.5-11.1",
        "avg_ttft": 3.62,
        "avg_tpot": 0,
        "avg_latency": 3.62,
        "p95_ttft": 5.39,
        "p95_tpot": 0,
        "p95_latency": 5.39
      }
    ]
  }
}
```