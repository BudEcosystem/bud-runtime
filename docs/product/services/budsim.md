# BudSim Service - Low-Level Design (LLD)

## 1. Document Overview

### 1.1 Purpose
This document provides the Low-Level Design (LLD) for the BudSim service, a performance simulation and optimization microservice within the Bud AI Foundry platform. BudSim predicts LLM deployment performance and optimizes configurations using machine learning models and genetic algorithms.

### 1.2 Scope
- Performance prediction using XGBoost regressors
- Configuration optimization using DEAP genetic algorithms
- Heuristic-based calculations using llm-memory-calculator
- Multi-hardware support (CPU, CUDA, HPU)
- Tensor Parallel (TP) and Pipeline Parallel (PP) optimization

---

## 2. System Context

### 2.1 Service Role
BudSim serves as the performance simulation engine that:
- Predicts LLM inference metrics (TTFT, throughput, latency)
- Optimizes deployment configurations across heterogeneous hardware
- Recommends optimal cluster and device allocations
- Validates memory requirements for deployment feasibility

### 2.2 Service Dependencies

| Dependency | Type | Purpose |
|------------|------|---------|
| budcluster | Service | Provides cluster topology and device information |
| budapp | Service | Triggers simulation requests, receives recommendations |
| PostgreSQL | Database | Stores simulation results and workflow state |
| Redis/Valkey | State Store | Dapr state management and pub/sub |
| Dapr Sidecar | Runtime | Service mesh, workflows, pub/sub |

### 2.3 Integration Points
- **Inbound**: Receives simulation requests from budapp via Dapr pub/sub
- **Outbound**: Stores results in PostgreSQL, publishes notifications
- **External**: Fetches model configs from HuggingFace (AutoConfig)

---

## 3. Detailed Architecture

### 3.1 Component Diagram

![Budsim component overview](./images/budsim-overview.png)
#### 3.3.1 Simulation Request Flow

![Simulation Request Flow](./images/budsim-simulation-flow.png)

#### 3.3.2 Genetic Algorithm Optimization Flow

![Genetic Algorithm Flow](./images/budsim-evolution-flow.png)

---

## 4. Data Design
#### 4.1.1 simulation_results Table

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PK, AUTO | Primary key |
| workflow_id | UUID | NOT NULL, INDEX | Workflow identifier |
| model_name | VARCHAR(255) | NOT NULL | Model name/path |
| model_version | VARCHAR(50) | NOT NULL | Model version |
| input_tokens | INTEGER | NOT NULL | Input token count |
| output_tokens | INTEGER | NOT NULL | Output token count |
| target_concurrency | INTEGER | NOT NULL | Target concurrent requests |
| target_ttft | FLOAT | NOT NULL | Target time to first token |
| target_throughput_per_user | FLOAT | NOT NULL | Target throughput |
| target_e2e_latency | FLOAT | NOT NULL | Target end-to-end latency |
| cluster_id | VARCHAR(255) | NOT NULL | Cluster identifier |
| node_id | VARCHAR(255) | NOT NULL | Node identifier |
| node_name | VARCHAR(255) | NOT NULL | Node hostname |
| device_id | VARCHAR(255) | NOT NULL | Device identifier |
| device_name | VARCHAR(255) | NOT NULL | Device name (e.g., A100) |
| device_type | VARCHAR(10) | NOT NULL | Device type (cuda/cpu/hpu) |
| device_model | VARCHAR(255) | NULLABLE | Specific device model |
| raw_name | VARCHAR(255) | NULLABLE | Raw device name |
| available_count | INTEGER | NOT NULL | Available device count |
| cores | INTEGER | NULLABLE | CPU cores (for cpu/cpu_high) |
| mem_per_gpu_in_gb | FLOAT | NOT NULL | Memory per device |
| hbm_bandwidth_in_gb_per_sec | FLOAT | NOT NULL | HBM bandwidth |
| intra_node_bandwidth_in_gb_per_sec | FLOAT | NOT NULL | Intra-node bandwidth |
| intra_node_min_message_latency | FLOAT | NOT NULL | Min message latency |
| peak_fp16_tflops | FLOAT | NOT NULL | Peak FP16 performance |
| peak_i8_tflops | FLOAT | NOT NULL | Peak INT8 performance |
| peak_i4_tflops | FLOAT | NOT NULL | Peak INT4 performance |
| inter_node_bandwidth_in_gb_per_sec | FLOAT | NOT NULL | Inter-node bandwidth |
| engine | VARCHAR(255) | NOT NULL | Engine name |
| engine_image | VARCHAR(255) | NOT NULL | Container image |
| engine_version | VARCHAR(50) | NULLABLE | Engine version |
| tool_calling_parser_type | VARCHAR(100) | NULLABLE | Tool calling parser |
| reasoning_parser_type | VARCHAR(100) | NULLABLE | Reasoning parser |
| architecture_family | VARCHAR(100) | NULLABLE | Model architecture |
| chat_template | VARCHAR(500) | NULLABLE | Chat template |
| supports_lora | BOOLEAN | NULLABLE | LoRA support flag |
| supports_pipeline_parallelism | BOOLEAN | NULLABLE | PP support flag |
| top_k_configs | JSONB | NULLABLE | Top-K configurations |
| is_blacklisted | BOOLEAN | DEFAULT FALSE | Blacklist flag |
| created_at | TIMESTAMP WITH TZ | DEFAULT NOW() | Creation timestamp |
| modified_at | TIMESTAMP WITH TZ | ON UPDATE | Modification timestamp |
#### 4.2.1 EvaluationResult

#---

## 5. API Design
#### 5.1.1 POST /simulator/run
Triggers a simulation workflow for cluster recommendations.

**Request Body (ClusterRecommendationRequest)**:

**Response (ClusterRecommendationResponse)**:

#### 5.1.2 GET /simulator/recommendations
Retrieves cached recommendations for a workflow.

**Query Parameters**:
- `workflow_id` (UUID): Required workflow identifier
- `cluster_id` (string): Optional cluster filter
- `concurrency` (int): Optional concurrency filter
- `error_rate_threshold` (float): Max error rate (default: 0.5)
- `page` (int): Page number (default: 1)
- `limit` (int): Results per page (default: 1)

#### 5.1.3 POST /simulator/configurations
Retrieves deployment configurations for a workflow.

**Request Body**:

#### 5.1.4 POST /simulator/node-configurations
Gets valid TP/PP configuration options for selected nodes.

**Request Body**:

#### 5.1.5 POST /simulator/benchmark-config
Generates deployment configuration for benchmark with user-selected parameters.

---

## 6. Logic and Algorithms

### 6.1 Simulation Methods

BudSim supports two simulation methods:

| Method | Description | Use Case |
|--------|-------------|----------|
| **REGRESSOR** | ML-based (XGBoost) genetic algorithm optimizing all engine parameters | Production deployments requiring accuracy |
| **HEURISTIC** | Memory-based calculations using llm-memory-calculator | Quick estimates, memory validation |

### 6.2 Genetic Algorithm (Evolution Class)

The Evolution class implements a genetic algorithm using DEAP:

**Optimization Parameters**:
- `tensor_parallel_size`: 1 to max_devices_per_node
- `pipeline_parallel_size`: 1 to total_nodes
- `max_num_seqs`: 1 to 256
- `scheduler_delay_factor`: 0.1 to 1.0
- `enable_chunked_prefill`: boolean
- `enable_prefix_caching`: boolean
- `block_size`: 8, 16, 32

**Fitness Function**:

**Algorithm Parameters**:
- Population size: Configurable (default: 50)
- Generations: Configurable (default: 30)
- Elite ratio: 0.2 (top 20% preserved)
- Crossover probability: 0.7
- Mutation probability: 0.2
- Convergence check: 10 generations without improvement

---

## 7. Configuration Management

### 7.1 Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `REDIS_URL` | Redis/Valkey connection | Required |
| `BENCHMARK_PREDICTOR_MODELS_DIR` | Path to pre-trained models | `./cache/pretrained_models` |
| `MODEL_REGISTRY_DIR` | Local model registry path | `/models` |
| `DEFAULT_SIMULATION_METHOD` | Default method (regressor/heuristic) | `regressor` |
| `SKIP_MASTER_NODE_FOR_CPU` | Skip master for CPU deployments | `true` |
| `NFD_DETECTION_TIMEOUT` | Node feature detection timeout | `300` |
| `VLLM_IMAGE` | Default vLLM image | Configurable |
| `SGLANG_IMAGE` | Default SGLang image | Configurable |
| `LITELLM_IMAGE` | Default LiteLLM image | Configurable |

---

## 8. Security Design

### 8.1 Authentication
- All endpoints require valid Dapr API token
- Service-to-service communication via Dapr mTLS

### 8.2 Authorization
- Simulation requests validated against user's project access
- Cluster access validated via budcluster

### 8.3 Data Protection
- No sensitive data stored (model URIs are public)
- Configuration data encrypted in transit
- Database credentials via environment variables

---

## 9. Performance Design

### 9.1 Optimization Strategies

| Strategy | Implementation |
|----------|----------------|
| Parallel evaluation | ThreadPoolExecutor for XGBoost predictions |
| Caching | LRU cache for llm-memory-calculator results |
| Batch processing | Dapr workflow parallel activities |
| Early termination | Convergence detection in GA |
| Database optimization | Window functions, JSONB indexes |

### 9.2 Performance Targets

| Metric | Target |
|--------|--------|
| Single simulation (regressor) | < 60s |
| Single simulation (heuristic) | < 10s |
| GA convergence | < 30 generations |
| Memory validation | < 1s |

### 9.3 ETA Calculation

Dynamic ETA based on simulation complexity:

---

---

## 11. Known Limitations

### 12.1 Current Limitations

| Limitation | Impact | Planned Resolution |
|------------|--------|-------------------|
| Pre-trained models required | New hardware needs training data | Model retraining pipeline |
| Single-cluster optimization | Cannot optimize across clusters | Multi-cluster support |
| Static cost model | Costs hardcoded | Dynamic pricing integration |
| Limited quantization support | Only int8/int4 | Broader quant methods |

### 12.2 Technical Debt

| Item | Priority | Estimated Effort |
|------|----------|------------------|
| Migrate to async XGBoost | Medium | 2 sprints |
| Add model versioning | Low | 1 sprint |
| Implement A/B testing for predictions | Medium | 2 sprints |
