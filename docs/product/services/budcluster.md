# budcluster - Low-Level Design
---

## 1. Document Overview

### 1.1 Purpose

This LLD provides build-ready technical specifications for budcluster, the cluster lifecycle and model deployment service of Bud AI Foundry. Developers should be able to implement cluster provisioning, model deployment, and infrastructure management features directly from this document.

### 1.2 Scope

**In Scope:**
- Kubernetes/OpenShift cluster registration and lifecycle management
- Multi-cloud cluster provisioning (AWS EKS, Azure AKS, on-premises)
- AI model deployment orchestration to clusters
- Node Feature Discovery (NFD) for hardware detection
- GPU time-slicing integration
- Worker/pod lifecycle management
- Performance benchmarking
- Cluster health monitoring
- Credential encryption and secure storage

**Out of Scope:**
- Model inference execution (handled by budgateway)
- Performance optimization algorithms (handled by budsim)
- Model registry metadata (handled by budmodel)
- User authentication (handled by budapp)

### 1.3 Intended Audience

| Audience | What They Need |
|----------|----------------|
| Developers | Implementation details, workflow patterns, database schemas |
| Reviewers | Architecture decisions, trade-offs, security model |
| Security | Credential encryption, cluster access patterns |
| Operations | Deployment topology, health checks, runbooks |

### 1.4 References

| Document | Description |
|----------|-------------|
| [High-Level Architecture](../architecture/high-level-architecture.md) | System overview |
| [Main LLD Index](../architecture/low-level-design.md) | Cross-cutting concerns |
| [budcluster Service Documentation](./budcluster.md) | Service summary |
| [Model Deployment Flow](../architecture/model-deployment.md) | Deployment architecture |

---

## 2. System Context & Assumptions

### 2.1 Business Assumptions

- Users deploy AI models ranging from 7B to 1T+ parameters
- Clusters can be managed (cloud-provisioned) or unmanaged (on-premises)
- Hardware varies: NVIDIA GPUs, Intel Gaudi HPUs, CPU-only
- Multiple deployments per cluster are common
- Benchmark data is critical for optimization decisions

### 2.2 Technical Assumptions

- Kubernetes clusters have API server accessible from budcluster
- NFD can be deployed to all clusters for hardware detection
- Helm is available for all Kubernetes deployments
- Dapr sidecar is co-located with budcluster pods
- Redis/Valkey is available for workflow state management

### 2.3 Constraints

| Constraint Type | Description | Impact |
|-----------------|-------------|--------|
| Network | Cluster API must be reachable | VPN/tunnel may be required |
| Timeout | NFD detection timeout: 30s default | Configurable via env var |
| Security | Credentials encrypted at rest | RSA/AES encryption required |
| Hardware | GPU availability varies | NFD detection required |

### 2.4 External Dependencies

| Dependency | Type | Failure Impact | Fallback Strategy |
|------------|------|----------------|-------------------|
| Target Clusters | Required | Cannot deploy/manage | Return error, retry later |
| PostgreSQL | Required | No data persistence | Return 503 |
| Redis/Valkey | Required | No workflow state | Workflows fail |
| budsim | Optional | No optimization | Use default configs |
| budapp | Optional | No endpoint updates | Queue status updates |
| budnotify | Optional | No notifications | Log warnings |
| budmodel | Optional | No model metadata | Use cached data |

---

## 3. Detailed Architecture

### 3.1 Component Overview

![Budcluster component overview](./images/budcluster-overview.png)

### 3.2 Component Breakdown

#### 3.2.1 Cluster Operations Module (`cluster_ops/`)

| Property | Value |
|----------|-------|
| **Responsibility** | Manage cluster lifecycle: registration, deletion, health checks, node status |
| **Owner Module** | `budcluster/cluster_ops/` |

**Inputs:**
| Input | Source | Format | Validation |
|-------|--------|--------|------------|
| Cluster config | HTTP POST `/cluster` | YAML kubeconfig + JSON metadata | Valid YAML, reachable API |
| Cluster ID | HTTP requests | UUID | Exists in database |
| Health checks | HTTP GET `/cluster/{id}/health` | Query params | Valid check types |

**Outputs:**
| Output | Destination | Format | Guarantees |
|--------|-------------|--------|------------|
| Workflow ID | HTTP response | UUID | Workflow trackable |
| Cluster status | PostgreSQL | Enum | Persisted |
| Node info | PostgreSQL | JSONB | Updated periodically |

**Internal Sub-modules:**
- `routes.py` - Cluster CRUD endpoints
- `services.py` - Business logic for cluster operations
- `workflows.py` - Dapr workflows for cluster provisioning
- `crud.py` - Database operations
- `models.py` - SQLAlchemy models (Cluster, ClusterNodeInfo)
- `nfd_handler.py` - NFD deployment and parsing

**Error Handling:**
| Error Condition | Response | Recovery |
|-----------------|----------|----------|
| Cluster unreachable | 503, mark ERROR status | Retry with backoff |
| Invalid kubeconfig | 400 Bad Request | User corrects config |
| NFD timeout | Warning, continue | Use fallback detection |
| Workflow failure | 500, log details | Manual retry |

**Scalability:**
- Horizontal: Yes, stateless with workflow state in Redis
- Vertical: Memory for large cluster node lists
- Bottlenecks: Concurrent cluster operations limited by Kubernetes API

#### 3.2.2 Deployment Module (`deployment/`)

| Property | Value |
|----------|-------|
| **Responsibility** | Deploy AI models to clusters, manage workers, handle autoscaling |
| **Owner Module** | `budcluster/deployment/` |

**Inputs:**
| Input | Source | Format | Validation |
|-------|--------|--------|------------|
| Deployment request | HTTP POST `/deployment` | DeploymentCreateRequest | Valid cluster, model |
| Worker filters | HTTP GET `/deployment/worker-info` | Query params | Valid cluster, namespace |
| Autoscale config | HTTP PUT `/deployment/autoscale` | UpdateAutoscaleRequest | Valid ranges |

**Outputs:**
| Output | Destination | Format | Guarantees |
|--------|-------------|--------|------------|
| Workflow ID | HTTP response | UUID | Workflow trackable |
| Worker info | HTTP response | WorkerInfoResponse | Paginated |
| Deployment status | PostgreSQL | Enum | Updated via periodic job |

**Internal Sub-modules:**
- `routes.py` - Deployment and worker endpoints
- `services.py` - Deployment orchestration logic
- `models.py` - WorkerInfo, Deployment models
- `utils.py` - Helm operations, resource calculations
- `quantization_workflows.py` - Model quantization handling

**Error Handling:**
| Error Condition | Response | Recovery |
|-----------------|----------|----------|
| Insufficient resources | 400, resource details | User scales cluster |
| Deployment failed | 500, pod logs | Check logs, retry |
| Worker unhealthy | Status update | Automatic pod restart |

**Scalability:**
- Horizontal: Yes, workflows are distributed
- Vertical: Memory for worker info aggregation
- Bottlenecks: Helm operations, model transfer

#### 3.2.3 Benchmark Operations Module (`benchmark_ops/`)

| Property | Value |
|----------|-------|
| **Responsibility** | Execute performance benchmarks, store results, compare configurations |
| **Owner Module** | `budcluster/benchmark_ops/` |

**Inputs:**
| Input | Source | Format | Validation |
|-------|--------|--------|------------|
| Benchmark request | Internal workflow | BenchmarkSchema | Valid cluster, model |
| Query filters | HTTP GET `/benchmark` | Query params | Valid ranges |

**Outputs:**
| Output | Destination | Format | Guarantees |
|--------|-------------|--------|------------|
| Benchmark results | PostgreSQL | BenchmarkResultSchema | Persisted |
| TTFT/TPOT metrics | HTTP response | Float values | Calculated |

### 3.3 Component Interaction Diagrams

#### 3.3.1 Cluster Registration - Happy Path

![Cluster Registration Flow](./images/budcluster-register-flow.png)

#### 3.3.2 Model Deployment Flow

![Model Deployment Flow](./images/budcluster-deploy-flow.png)

#### 3.3.3 Cluster State Diagram

![Cluster State Diagram](./images/budcluster-cluster-states.png)

#### 3.3.4 Deployment State Diagram

![Deployment State Diagram](./images/budcluster-deployment-states.png)

---

## 4. Data Design

### 4.1 Data Models

#### 4.1.1 Cluster

**Table:** `cluster`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, NOT NULL | Primary identifier |
| `platform` | ENUM | NOT NULL | ON_PREM, EKS, AKS |
| `configuration` | STRING | NOT NULL | Encrypted kubeconfig |
| `ingress_url` | STRING | NOT NULL | Cluster ingress URL |
| `host` | STRING | NOT NULL | Cluster hostname |
| `server_url` | STRING | NOT NULL | Kubernetes API URL |
| `enable_master_node` | BOOLEAN | DEFAULT FALSE | Allow scheduling on master |
| `status` | ENUM | NOT NULL | REGISTERING, AVAILABLE, NOT_AVAILABLE, ERROR, DELETING |
| `reason` | STRING | NULL | Status reason/error message |
| `last_metrics_collection` | TIMESTAMP | NULL | Last metrics sync time |
| `metrics_collection_status` | STRING(50) | NULL | Metrics collection status |
| `not_available_since` | TIMESTAMP | NULL | When cluster became unavailable |
| `last_retry_time` | TIMESTAMP | NULL | Last connection retry |
| `created_at` | TIMESTAMP(tz) | NOT NULL | Creation timestamp |
| `updated_at` | TIMESTAMP(tz) | NOT NULL | Last modification |

**Indexes:**
| Index Name | Columns | Type | Purpose |
|------------|---------|------|---------|
| `ix_cluster_status` | `status` | B-tree | Filter by status |
| `ix_cluster_platform` | `platform` | B-tree | Filter by platform |

#### 4.1.2 ClusterNodeInfo

**Table:** `cluster_node_info`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, NOT NULL | Primary identifier |
| `cluster_id` | UUID | FK, NOT NULL | Parent cluster |
| `name` | STRING | NOT NULL | Node hostname |
| `internal_ip` | STRING | NULL | Internal IP address |
| `type` | ENUM | NOT NULL | MASTER, WORKER, GPU, HPU |
| `total_workers` | INTEGER | DEFAULT 0 | Total worker capacity |
| `available_workers` | INTEGER | DEFAULT 0 | Available workers |
| `used_workers` | INTEGER | DEFAULT 0 | Currently used workers |
| `threads_per_core` | INTEGER | NULL | CPU threads per core |
| `core_count` | INTEGER | NULL | Total CPU cores |
| `hardware_info` | JSONB | NOT NULL | Detected hardware details |
| `status` | BOOLEAN | NOT NULL | Node ready status |
| `status_sync_at` | TIMESTAMP | NOT NULL | Last status sync |
| `schedulable` | BOOLEAN | DEFAULT TRUE | Can schedule pods |
| `unschedulable` | BOOLEAN | DEFAULT FALSE | Cordoned status |
| `taints` | JSONB | NULL | Node taints |
| `conditions` | JSONB | NULL | Node conditions |
| `nfd_detected` | BOOLEAN | DEFAULT FALSE | NFD labels detected |
| `nfd_labels` | JSONB | NULL | NFD hardware labels |
| `detection_method` | STRING | DEFAULT 'configmap' | How hardware was detected |
| `kernel_info` | JSONB | NULL | Kernel version info |
| `driver_info` | JSONB | NULL | GPU/HPU driver info |
| `created_at` | TIMESTAMP(tz) | NOT NULL | Creation timestamp |
| `updated_at` | TIMESTAMP(tz) | NOT NULL | Last modification |

**Indexes:**
| Index Name | Columns | Type | Purpose |
|------------|---------|------|---------|
| `uq_cluster_node_info_cluster_id_name` | `cluster_id, name` | Unique | Prevent duplicate nodes |
| `ix_cluster_node_info_cluster_id` | `cluster_id` | B-tree | List nodes by cluster |

#### 4.1.3 WorkerInfo

**Table:** `worker_info`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, NOT NULL | Primary identifier |
| `cluster_id` | UUID | FK, NOT NULL | Parent cluster |
| `deployment_id` | UUID | FK, NULL | Parent deployment |
| `deployment_name` | STRING | NOT NULL | Deployment name |
| `namespace` | STRING | NOT NULL | Kubernetes namespace |
| `name` | STRING | NOT NULL | Pod name |
| `node_ip` | STRING | NOT NULL | Node IP address |
| `node_name` | STRING | NOT NULL | Node hostname |
| `device_name` | STRING | NOT NULL | GPU/HPU device name |
| `utilization` | STRING | NULL | Resource utilization |
| `hardware` | STRING | NOT NULL | Hardware type |
| `uptime` | STRING | NOT NULL | Pod uptime |
| `status` | ENUM | NOT NULL | RUNNING, PENDING, ERROR, TERMINATED |
| `reason` | STRING | NULL | Status reason |
| `cores` | INTEGER | NOT NULL | Allocated CPU cores |
| `memory` | STRING | NOT NULL | Allocated memory |
| `deployment_status` | ENUM | NOT NULL | RUNNING, STOPPED, FAILED, etc. |
| `concurrency` | INTEGER | NOT NULL | Max concurrent requests |
| `created_datetime` | TIMESTAMP(tz) | NOT NULL | Pod creation time |
| `last_restart_datetime` | TIMESTAMP(tz) | NOT NULL | Last restart time |
| `last_updated_datetime` | TIMESTAMP(tz) | NOT NULL | Last status update |

**Indexes:**
| Index Name | Columns | Type | Purpose |
|------------|---------|------|---------|
| `ix_worker_info_cluster_id` | `cluster_id` | B-tree | List workers by cluster |
| `ix_worker_info_deployment_id` | `deployment_id` | B-tree | List workers by deployment |
| `ix_worker_info_namespace` | `namespace` | B-tree | Filter by namespace |

#### 4.1.4 Deployment

**Table:** `deployment`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, NOT NULL | Primary identifier |
| `cluster_id` | UUID | FK, NOT NULL | Target cluster |
| `namespace` | STRING | UNIQUE, NOT NULL | Kubernetes namespace |
| `deployment_name` | STRING | NOT NULL | Helm release name |
| `endpoint_name` | STRING | NOT NULL | Associated endpoint name |
| `model` | STRING | NOT NULL | Model name/path |
| `deployment_url` | STRING | NULL | Inference endpoint URL |
| `supported_endpoints` | ARRAY(STRING) | NULL | Supported API endpoints |
| `concurrency` | INTEGER | NOT NULL | Max concurrent requests |
| `number_of_replicas` | INTEGER | DEFAULT 1 | Replica count |
| `deploy_config` | JSONB | NULL | Full deployment config |
| `status` | ENUM | NOT NULL | DEPLOYING, RUNNING, STOPPED, FAILED |
| `workflow_id` | UUID | NULL | Associated workflow |
| `simulator_id` | UUID | NULL | Optimization config source |
| `credential_id` | UUID | NULL | Model registry credential |
| `last_status_check` | TIMESTAMP(tz) | NULL | Last health check |

#### 4.1.5 Benchmark Tables

**Table:** `benchmark`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, NOT NULL | Primary identifier |
| `benchmark_id` | UUID | NOT NULL | Benchmark run ID |
| `cluster_id` | UUID | FK, NULL | Target cluster |
| `user_id` | UUID | NOT NULL | Requesting user |
| `model_id` | UUID | NOT NULL | Model being benchmarked |
| `model` | STRING | NOT NULL | Model name |
| `nodes` | JSONB | NULL | Nodes used |
| `num_of_users` | INTEGER | NOT NULL | Concurrent users |
| `max_input_tokens` | INTEGER | NULL | Max input tokens |
| `max_output_tokens` | INTEGER | NULL | Max output tokens |
| `datasets` | JSONB | NULL | Benchmark datasets |
| `status` | ENUM | NOT NULL | PENDING, RUNNING, COMPLETED, FAILED, CANCELLED |
| `reason` | STRING | NULL | Status reason |

**Table:** `benchmark_result`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, NOT NULL | Primary identifier |
| `benchmark_id` | UUID | FK, NOT NULL | Parent benchmark |
| `duration` | FLOAT | NOT NULL | Total duration |
| `successful_requests` | INTEGER | NOT NULL | Successful request count |
| `total_input_tokens` | INTEGER | NOT NULL | Total input tokens |
| `total_output_tokens` | INTEGER | NOT NULL | Total output tokens |
| `request_throughput` | FLOAT | NULL | Requests/second |
| `input_throughput` | FLOAT | NULL | Input tokens/second |
| `output_throughput` | FLOAT | NULL | Output tokens/second |
| `mean_ttft_ms` | FLOAT | NULL | Mean time to first token |
| `p99_ttft_ms` | FLOAT | NULL | P99 TTFT |
| `mean_tpot_ms` | FLOAT | NULL | Mean time per output token |
| `p99_tpot_ms` | FLOAT | NULL | P99 TPOT |
| `mean_itl_ms` | FLOAT | NULL | Mean inter-token latency |
| `mean_e2el_ms` | FLOAT | NULL | Mean end-to-end latency |

#### 4.1.6 Entity Relationship Diagram

![ER Diagram](./images/budcluster-er-diagram.png)

### 4.2 Data Flow

#### 4.2.1 Data Lifecycle

| Stage | Location | Retention | Transition Trigger |
|-------|----------|-----------|-------------------|
| Created | PostgreSQL | Indefinite | Cluster registration |
| Active | PostgreSQL | While cluster exists | Status changes |
| Error | PostgreSQL | Until recovered | Health check failure |
| Deleted | Removed | N/A | User deletion |

#### 4.2.2 Read/Write Paths

**Write Path (Cluster Registration):**
```
1. Request received at /cluster endpoint
2. Kubeconfig validated and encrypted
3. Cluster record created in PostgreSQL
4. Dapr workflow started for registration
5. NFD deployed to cluster
6. Node info collected and stored
7. Status updated to AVAILABLE
```

**Read Path (Worker Info):**
```
1. Request received at /deployment/worker-info
2. Query PostgreSQL for cached worker data
3. If refresh=true, query Kubernetes API
4. Update cache in PostgreSQL
5. Return paginated response
```

#### 4.2.3 Caching Strategy

| Cache Layer | Technology | TTL | Invalidation Strategy |
|-------------|------------|-----|----------------------|
| Workflow state | Redis (Dapr) | Workflow lifetime | On completion/failure |
| Node info | PostgreSQL | 3 minutes | Periodic sync job |
| Worker info | PostgreSQL | 3 minutes | Periodic sync job |

---

## 5. API & Interface Design

### 5.1 Internal APIs

#### 5.1.1 Cluster Operations

**`POST /cluster`**

| Property | Value |
|----------|-------|
| **Description** | Register a new cluster |
| **Authentication** | Dapr API token |
| **Rate Limit** | 10 requests/minute |
| **Timeout** | 60 seconds |

**Request (multipart/form-data):**
```json
{
  "cluster_create_request": "JSON string with cluster metadata",
  "configuration": "YAML kubeconfig file"
}
```

**Response (Success):**
```json
{
  "success": true,
  "workflow_id": "uuid",
  "steps": [
    {"name": "verify_connection", "status": "pending"},
    {"name": "deploy_nfd", "status": "pending"},
    {"name": "collect_node_info", "status": "pending"}
  ]
}
```

**`POST /deployment`**

| Property | Value |
|----------|-------|
| **Description** | Deploy a model to a cluster |
| **Authentication** | Dapr API token |
| **Rate Limit** | 5 requests/minute |
| **Timeout** | 120 seconds |

**Request:**
```json
{
  "cluster_id": "uuid",
  "simulator_id": "uuid - optimization config",
  "model_name": "string",
  "namespace": "string",
  "credential_id": "uuid - optional"
}
```

**Response (Success):**
```json
{
  "success": true,
  "workflow_id": "uuid",
  "steps": [
    {"name": "transfer_model", "status": "pending"},
    {"name": "deploy_runtime", "status": "pending"},
    {"name": "verify_health", "status": "pending"}
  ]
}
```

**`GET /deployment/worker-info`**

| Property | Value |
|----------|-------|
| **Description** | Get workers for a deployment |
| **Authentication** | Dapr API token |
| **Rate Limit** | 100 requests/minute |
| **Timeout** | 30 seconds |

**Query Parameters:**
- `cluster_id` (required): UUID
- `namespace` (required): string
- `refresh` (optional): boolean
- `page` (optional): integer
- `limit` (optional): integer

### 5.2 External Integrations

#### 5.2.1 Kubernetes Clusters

| Property | Value |
|----------|-------|
| **Purpose** | Manage cluster resources, deploy workloads |
| **Auth Mechanism** | Kubeconfig (encrypted) |
| **Rate Limits** | Kubernetes API QPS limits |
| **SLA** | Cluster-dependent |

**Failure Fallback:**
- Mark cluster as NOT_AVAILABLE
- Retry with exponential backoff
- Notify user via budnotify

#### 5.2.2 budsim

| Property | Value |
|----------|-------|
| **Purpose** | Get optimized deployment configurations |
| **Auth Mechanism** | Dapr service invocation |
| **Rate Limits** | None (internal) |
| **SLA** | Best effort |

**Failure Fallback:**
- Use default deployment configurations
- Log warning, continue deployment

---

## 6. Logic & Algorithm Details

### 6.1 Credential Encryption

**Purpose:** Securely store cluster kubeconfigs and credentials.

**Inputs:**
- `plaintext`: Raw credential data (kubeconfig YAML)
- `rsa_public_key`: RSA-4096 public key

**Outputs:**
- `encrypted_data`: Base64-encoded encrypted credential

**Algorithm (Step-by-Step):**

1. Generate random AES-256 symmetric key
2. Encrypt plaintext with AES-256-GCM
3. Encrypt AES key with RSA-4096 public key
4. Concatenate: encrypted_key + nonce + ciphertext + tag
5. Base64 encode result

**Pseudocode:**
```python
def encrypt_credential(plaintext: str) -> str:
    # Generate symmetric key
    aes_key = os.urandom(32)  # 256 bits
    nonce = os.urandom(12)

    # Encrypt data with AES-GCM
    cipher = AES.new(aes_key, AES.MODE_GCM, nonce=nonce)
    ciphertext, tag = cipher.encrypt_and_digest(plaintext.encode())

    # Encrypt AES key with RSA
    rsa_key = load_rsa_public_key()
    encrypted_key = rsa_key.encrypt(aes_key, OAEP(MGF1(SHA256())))

    # Combine and encode
    result = encrypted_key + nonce + ciphertext + tag
    return base64.b64encode(result).decode()
```

### 6.2 Max Model Length Calculation

**Purpose:** Calculate optimal `--max-model-len` for deployments.

**Inputs:**
- `input_tokens`: Expected max input tokens
- `output_tokens`: Expected max output tokens

**Outputs:**
- `max_model_len`: Calculated model context length

**Algorithm:**
```python
def calculate_max_model_len(input_tokens: int, output_tokens: int) -> int:
    # Add 10% safety margin
    base_length = input_tokens + output_tokens
    max_model_len = int(base_length * 1.1)

    # Ensure minimum of 128
    return max(max_model_len, 128)
```

### 6.3 NFD Hardware Detection

**Purpose:** Detect hardware capabilities via Node Feature Discovery labels.

**Inputs:**
- `cluster_id`: Target cluster UUID
- `timeout`: Detection timeout (default 30s)

**Outputs:**
- `hardware_info`: List of detected hardware per node

**Algorithm (Step-by-Step):**

1. Deploy NFD Helm chart to cluster
2. Wait for NFD pods to be ready
3. Query node labels starting with `feature.node.kubernetes.io/`
4. Parse PCI vendor/device IDs
5. Map to known hardware (NVIDIA GPU, Intel Gaudi)
6. Return structured hardware info

**Decision Tree:**
```
Does node have NFD labels?
├── Yes → Parse labels
│   ├── PCI vendor 10de (NVIDIA)?
│   │   ├── Yes → Extract GPU model from device ID
│   │   └── No → Check for 8086 (Intel)
│   │       ├── Yes → Check for Gaudi accelerator
│   │       └── No → Mark as CPU-only
└── No → Log warning, use fallback detection
```

---

## 7. GenAI/ML-Specific Design

### 7.1 Model Deployment Flow

#### 7.1.1 Deployment Pipeline

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   budapp    │───▶│ budcluster  │───▶│   Cluster   │───▶│   Runtime   │
│  (request)  │    │ (workflow)  │    │  (deploy)   │    │  (verify)   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

| Stage | Duration | Rollback Point | Validation |
|-------|----------|----------------|------------|
| Transfer model | 1-30 min | Yes | Model exists in storage |
| Deploy Helm chart | 1-5 min | Yes | Release created |
| Wait for pods | 1-10 min | Yes | Pods running |
| Health check | 30s | Yes | HTTP 200 from /health |

#### 7.1.2 Model Configuration

| Parameter | Source | Default | Constraints |
|-----------|--------|---------|-------------|
| `max_model_len` | Calculated | (input + output) * 1.1 | Min: 128 |
| `tensor_parallel` | budsim | 1 | Must divide GPU count |
| `pipeline_parallel` | budsim | 1 | TP * PP ≤ total GPUs |
| `gpu_memory_utilization` | budsim | 0.9 | 0.1-0.95 |
| `max_num_seqs` | budsim | 256 | Memory constrained |

### 7.2 Hardware Resource Allocation

#### 7.2.1 GPU/Accelerator Selection

| Hardware Type | Detection Method | Allocation Strategy |
|---------------|------------------|---------------------|
| NVIDIA GPU | NFD PCI vendor 10de | nvidia.com/gpu resource |
| Intel Gaudi | NFD Gaudi labels | habana.ai/gaudi resource |
| CPU | Default | Request CPU cores |

#### 7.2.2 Resource Calculation

**GPU Memory Formula:**
```
required_vram = model_params * bytes_per_param + kv_cache + overhead
kv_cache = batch_size * seq_len * hidden_size * num_layers * 2 * dtype_size
```

**GPU Count Formula:**
```
gpu_count = ceil(required_vram / (gpu_memory * utilization)) * tensor_parallel
```

### 7.3 Performance Optimization

#### 7.3.1 Benchmarking Metrics

| Metric | Definition | Target |
|--------|------------|--------|
| TTFT | Time to first token (ms) | < 500ms |
| TPOT | Time per output token (ms) | < 50ms |
| Throughput | Output tokens/second | Model-dependent |
| E2EL | End-to-end latency (ms) | Context-dependent |

### 7.4 HAMI GPU Time-Slicing

#### 7.4.1 Installation Flow

```
NFD detects NVIDIA GPUs
        │
        ▼
GPU Operator deployed
        │
        ▼
FCSP Helm chart installed
        │
        ▼
FCSP scheduler available
        │
        ▼
GPU time-slicing enabled
```

#### 7.4.2 Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `ENABLE_HAMI_METRICS` | false | Enable metrics collection |
| `HAMI_SCHEDULER_PORT` | 31993 | Scheduler metrics port |
| `HAMI_UTILIZATION_THRESHOLD` | 80 | GPU availability threshold |

---

## 8. Configuration & Environment Design

### 8.1 Environment Variables

| Variable | Required | Default | Description | Sensitive |
|----------|----------|---------|-------------|-----------|
| `DATABASE_URL` | Yes | - | PostgreSQL connection string | Yes |
| `DAPR_HTTP_ENDPOINT` | No | `http://localhost:3500` | Dapr sidecar endpoint | No |
| `APP_API_TOKEN` | Yes | - | Internal service auth token | Yes |
| `NFD_DETECTION_TIMEOUT` | No | `30` | NFD detection timeout (seconds) | No |
| `NFD_NAMESPACE` | No | `node-feature-discovery` | NFD deployment namespace | No |
| `ENABLE_HAMI_METRICS` | No | `false` | Enable HAMI metrics | No |
| `HAMI_SCHEDULER_PORT` | No | `31993` | HAMI scheduler port | No |
| `CRYPTO_KEY_PATH` | Yes | - | Path to encryption keys | No |

### 8.2 Secrets Management

| Secret | Storage | Rotation | Access |
|--------|---------|----------|--------|
| RSA private key | File (crypto-keys/) | Annually | budcluster only |
| Symmetric key | File (crypto-keys/) | Annually | budcluster only |
| Database password | Kubernetes Secret | 90 days | budcluster pods |
| APP_API_TOKEN | Kubernetes Secret | On demand | All services |

### 8.3 Environment Differences

| Aspect | Development | Staging | Production |
|--------|-------------|---------|------------|
| Database | Local PostgreSQL | Shared PostgreSQL | HA PostgreSQL |
| Redis | Local Redis | Shared Redis | HA Redis cluster |
| Replicas | 1 | 2 | 3+ |
| Log level | DEBUG | INFO | INFO |
| Cluster access | Local clusters | Test clusters | Production clusters |

---

## 9. Security Design

### 9.1 Authentication

| Flow | Mechanism | Token Lifetime | Refresh Strategy |
|------|-----------|----------------|------------------|
| Service-to-service | Dapr API token | Indefinite | Manual rotation |
| Cluster access | Kubeconfig | Varies | Re-register cluster |

### 9.2 Authorization

| Resource | Permission Model | Enforcement Point |
|----------|------------------|-------------------|
| Clusters | Project membership | budapp proxy |
| Deployments | Cluster access | budapp proxy |
| Workers | Deployment access | budapp proxy |

### 9.3 Encryption

| Data Type | At Rest | In Transit | Key Management |
|-----------|---------|------------|----------------|
| Kubeconfigs | RSA + AES-256-GCM | TLS 1.3 | File-based keys |
| Credentials | RSA + AES-256-GCM | TLS 1.3 | File-based keys |
| Workflow state | Plaintext in Redis | TLS 1.3 | N/A |

### 9.4 Threat Model (Basic)

| Threat | Likelihood | Impact | Mitigation |
|--------|------------|--------|------------|
| Kubeconfig exposure | Medium | Critical | RSA/AES encryption |
| Cluster credential theft | Low | Critical | Short-lived tokens where possible |
| Man-in-the-middle | Low | High | TLS for all connections |
| Workflow state tampering | Low | Medium | Redis authentication |

---

## 10. Performance & Scalability

### 10.1 Expected Load

| Metric | Normal | Peak | Burst |
|--------|--------|------|-------|
| Cluster operations/hour | 10 | 50 | 100 |
| Deployments/hour | 20 | 100 | 200 |
| Worker info queries/min | 100 | 500 | 1000 |

### 10.2 Bottlenecks

| Bottleneck | Trigger Condition | Symptom | Mitigation |
|------------|-------------------|---------|------------|
| Kubernetes API | Many concurrent cluster ops | Timeouts | Rate limiting |
| Helm operations | Many deployments | Slow deployments | Queue operations |
| Model transfer | Large models | Long deploy times | Parallel transfers |

### 10.3 Scaling Strategy

| Dimension | Trigger | Target | Cooldown |
|-----------|---------|--------|----------|
| Horizontal (pods) | CPU > 70% | 2-5 replicas | 5 minutes |
| Workflow workers | Queue depth | Auto-scale | 2 minutes |

---

## 11. Error Handling & Logging

### 11.1 Error Classification

| Category | Severity | Retry | Alert |
|----------|----------|-------|-------|
| Cluster unreachable | High | Yes (3x) | After 3 failures |
| Deployment failed | High | Yes (1x) | Immediately |
| NFD timeout | Medium | Yes (2x) | After 5 failures |
| Workflow failure | High | No | Immediately |

### 11.2 Retry Strategy

| Error Type | Max Retries | Backoff | Circuit Breaker |
|------------|-------------|---------|-----------------|
| Cluster connection | 3 | Exponential (30s base) | 5 failures in 5 min |
| Helm operation | 2 | Linear (60s) | None |
| Dapr invocation | 3 | Exponential (1s base) | 10 failures in 60s |

### 11.3 Observability

| Signal | Tool | Retention | Alert Threshold |
|--------|------|-----------|-----------------|
| Metrics | Prometheus | 30 days | Error rate > 5% |
| Traces | Tempo | 7 days | P99 latency > 60s |
| Logs | Loki | 14 days | ERROR count > 5/min |

---

## 12. Deployment & Infrastructure

### 12.1 Deployment Topology

```
┌─────────────────────────────────────────────────────────────────┐
│                        Kubernetes Cluster                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐                │
│  │ budcluster │  │ budcluster │  │ budcluster │   (3 replicas) │
│  │  + Dapr    │  │  + Dapr    │  │  + Dapr    │                │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘                │
│        │               │               │                        │
│        └───────────────┼───────────────┘                        │
│                        │                                         │
│                        ▼                                         │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Service Mesh (Dapr)                    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                        │                                         │
│        ┌───────────────┼───────────────┐                        │
│        ▼               ▼               ▼                        │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐                    │
│  │PostgreSQL│   │  Redis   │   │ Target   │                    │
│  └──────────┘   └──────────┘   │ Clusters │                    │
│                                 └──────────┘                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 12.2 Container Specification

| Property | Value |
|----------|-------|
| Base Image | `python:3.11-slim` |
| Resource Requests | CPU: 200m, Memory: 512Mi |
| Resource Limits | CPU: 1000m, Memory: 2Gi |
| Health Checks | Liveness: `/health`, Readiness: `/ready` |

### 12.3 Rollback Strategy

| Scenario | Detection | Rollback Method | Recovery Time |
|----------|-----------|-----------------|---------------|
| Failed deployment | Health checks fail | Kubernetes rollback | < 2 minutes |
| Workflow corruption | State inconsistency | Clear Redis state | < 5 minutes |

---

## 13. Testing Strategy

### 13.1 Unit Tests

| Module | Coverage Target | Mocking Strategy |
|--------|-----------------|------------------|
| `cluster_ops/` | 80% | Mock Kubernetes client |
| `deployment/` | 80% | Mock Helm, K8s client |
| `benchmark_ops/` | 85% | Mock database |

### 13.2 Integration Tests

| Integration | Test Approach | Environment |
|-------------|---------------|-------------|
| PostgreSQL | Real database | Docker Compose |
| Redis | Real Redis | Docker Compose |
| Kubernetes | Kind cluster | CI/CD |

### 13.3 Edge Case Coverage

| Edge Case | Test | Expected Behavior |
|-----------|------|-------------------|
| Cluster unreachable | `test_cluster_unreachable` | Mark ERROR, retry |
| NFD timeout | `test_nfd_timeout` | Continue with warning |
| Concurrent deployments | `test_concurrent_deploys` | Queue properly |

---

## 14. Limitations & Future Enhancements

### 14.1 Known Limitations

| Limitation | Impact | Workaround |
|------------|--------|------------|
| Single Helm per cluster | Concurrent deploy conflicts | Queue operations |
| NFD required | No hardware detection without it | Manual node labeling |
| No multi-region | Single control plane | Deploy multiple budclusters |

### 14.2 Technical Debt

| Item | Priority | Effort | Tracking |
|------|----------|--------|----------|
| Add OpenTelemetry tracing | Medium | 1 week | TBD |
| Migrate to async K8s client | High | 2 weeks | TBD |
| Add GKE support | Medium | 2 weeks | TBD |

### 14.3 Planned Improvements

| Enhancement | Rationale | Target Version |
|-------------|-----------|----------------|
| GKE cluster support | Multi-cloud expansion | v2.0 |
| Cluster federation | Multi-cluster management | v2.5 |
| GitOps integration | Declarative deployments | v2.0 |

---

## 15. Appendix

### 15.1 Glossary

| Term | Definition |
|------|------------|
| NFD | Node Feature Discovery - Kubernetes component for hardware detection |
| HAMI | HAMi GPU Device Plugin - GPU time-slicing support |
| TP | Tensor Parallelism - model sharding across GPUs |
| PP | Pipeline Parallelism - layer sharding across GPUs |
| TTFT | Time to First Token - latency metric |
| TPOT | Time Per Output Token - generation speed metric |

### 15.2 Design Alternatives Considered

| Alternative | Pros | Cons | Why Not Chosen |
|-------------|------|------|----------------|
| ArgoCD for deployments | GitOps native | Complex setup | Helm sufficient for now |
| Crossplane for clusters | Declarative | Learning curve | Terraform more familiar |
| Direct K8s client | No Helm dependency | More code | Helm charts standard |
