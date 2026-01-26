# budeval - Low-Level Design
---

## 1. Document Overview

### 1.1 Purpose

This LLD provides build-ready technical specifications for budeval, the model evaluation and benchmarking service of Bud AI Foundry. Developers should be able to implement evaluation jobs, benchmark execution, and performance analysis directly from this document.

### 1.2 Scope

**In Scope:**
- Model evaluation job orchestration
- Standardized benchmark execution (MMLU, HellaSwag, ARC, GSM8K)
- OpenCompass integration for benchmark runs
- Performance metrics calculation
- Evaluation result storage and analysis
- Ansible-based evaluation orchestration on clusters
- ClickHouse integration for results storage

**Out of Scope:**
- Model inference execution (handled by budgateway)
- Cluster management (handled by budcluster)
- Model registry (handled by budmodel)
- User authentication (handled by budapp)

---

## 2. System Context & Assumptions

### 2.1 Business Assumptions

- Users evaluate models before production deployment
- Standard benchmarks provide comparable metrics
- Evaluations may run for hours on large datasets
- Results need persistence for historical comparison
- Multiple models may be compared side-by-side

### 2.2 Technical Assumptions

- OpenCompass is the primary evaluation engine
- Ansible orchestrates evaluation jobs on clusters
- PostgreSQL stores job metadata
- ClickHouse stores evaluation results
- Dapr workflows manage long-running jobs

### 2.3 Constraints

| Constraint Type | Description | Impact |
|-----------------|-------------|--------|
| Timeout | 1 hour default evaluation timeout | Large datasets may need extension |
| Concurrency | 5 concurrent evaluations default | Queuing for high load |
| GPU | GPU may be required for large models | Resource scheduling needed |
| Storage | Large benchmark datasets | Pre-download or streaming required |

### 2.4 External Dependencies

| Dependency | Type | Failure Impact | Fallback Strategy |
|------------|------|----------------|-------------------|
| PostgreSQL | Required | No job persistence | Return 503 |
| ClickHouse | Required | No results storage | Buffer locally |
| Target Cluster | Required | Cannot run evaluation | Return error |
| OpenCompass | Required | No benchmark execution | Return error |
| budgateway | Optional | Cannot evaluate via API | Direct model access |
| budcluster | Optional | No cluster info | Manual config |

---

## 3. Detailed Architecture

### 3.1 Component Overview

![Budeval component overview](./images/budeval-overview.png)
#### 3.2.1 Evaluation Service

**Purpose:** Orchestrates evaluation job execution

**Key Responsibilities:**
- Accept evaluation requests
- Validate evaluation configuration
- Start Dapr workflow for long-running jobs
- Return workflow metadata for tracking

#### 3.2.2 Evaluation Workflow

**Purpose:** Long-running workflow for evaluation execution

**Workflow Steps:**
1. Validate evaluation request
2. Prepare OpenCompass configuration
3. Deploy evaluation job via Ansible
4. Monitor job progress
5. Collect results from ClickHouse
6. Publish completion event

#### 3.2.3 Ansible Orchestrator

**Purpose:** Deploy and manage evaluation jobs on clusters

**Capabilities:**
- Generate Ansible playbooks for evaluation
- Deploy OpenCompass container to cluster
- Monitor job status
- Clean up after completion

#### 3.2.4 OpenCompass Transformer

**Purpose:** Transform evaluation requests to OpenCompass format

**Responsibilities:**
- Map datasets to OpenCompass dataset IDs
- Generate OpenCompass config files
- Handle model endpoint configuration
- Parse OpenCompass results

---

## 4. Data Design

### 4.3 Supported Benchmark Suites

| Benchmark | Type | Description |
|-----------|------|-------------|
| MMLU | Knowledge | Massive Multitask Language Understanding |
| HellaSwag | Reasoning | Commonsense reasoning |
| ARC | Reasoning | AI2 Reasoning Challenge |
| GSM8K | Math | Grade school math problems |
| TruthfulQA | Safety | Truthfulness benchmark |
| HumanEval | Coding | Code generation |

---

## 5. API & Interface Design

### 5.1 POST /evals/start

**Purpose:** Start a new evaluation job

### 5.2 GET /evals/{eval_id}

**Purpose:** Get evaluation status and results

---

## 6. Configuration & Environment

### 6.1 Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| DATABASE_URL | Yes | - | PostgreSQL connection string |
| CLICKHOUSE_URL | Yes | - | ClickHouse for results |
| DAPR_HTTP_PORT | Yes | 3510 | Dapr sidecar port |
| DAPR_API_TOKEN | Yes | - | Dapr authentication |
| MAX_CONCURRENT_EVALUATIONS | No | 5 | Parallel evaluations |
| EVALUATION_TIMEOUT | No | 3600 | Timeout in seconds |
| BENCHMARK_DATA_PATH | No | /app/benchmarks | Dataset location |
| RESULTS_STORAGE_PATH | No | /app/results | Results location |

---

## 7. Security Design

### 7.1 API Key Handling

- API keys passed in eval_model_info are used only during evaluation
- Keys are not persisted in results
- Keys are masked in logs

### 7.2 Cluster Access

- Kubeconfig is optional (uses local cluster config)
- When provided, kubeconfig is validated before use
- Ansible uses SSH key-based authentication

---

## 8. Performance & Scalability

### 8.1 Evaluation Performance

| Factor | Impact | Optimization |
|--------|--------|--------------|
| Dataset Size | Linear time increase | Batch processing |
| Model Size | GPU memory constraints | Multi-GPU distribution |
| Concurrent Jobs | Resource contention | Queue management |

### 8.2 Scaling Strategy

- Horizontal: Multiple evaluation workers
- Vertical: GPU-accelerated evaluation nodes
- Dataset: Pre-download benchmarks

---

## 9. Deployment & Infrastructure

### 10.1 Resource Requirements

| Component | CPU | Memory | GPU |
|-----------|-----|--------|-----|
| budeval API | 500m-1 | 512Mi-1Gi | - |
| Evaluation Job | 4+ | 16Gi+ | 1-8 |
