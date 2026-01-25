# BudModel Service - Low-Level Design (LLD)

## 1. Document Overview

### 1.1 Purpose
This document provides the Low-Level Design (LLD) for the BudModel service, a model registry and intelligence microservice within the Bud AI Foundry platform. BudModel manages model metadata extraction, license analysis, security scanning, and benchmark leaderboard aggregation.

### 1.2 Scope
- Model metadata extraction from HuggingFace and cloud providers
- License analysis and FAQ generation using LLMs
- Security scanning (ClamAV, modelscan)
- Benchmark leaderboard aggregation from multiple sources
- Model download management with Aria2

### 1.3 Audience
- Platform engineers implementing model registry features
- DevOps engineers configuring model pipelines
- Security engineers reviewing model scanning workflows

### 1.4 Related Documents
- [High-Level Architecture](../architecture/high-level-architecture.md)
- [budapp LLD](./budapp.md)
- [budsim LLD](./budsim.md)

---

## 2. System Context

### 2.1 Service Role
BudModel serves as the model intelligence layer that:
- Extracts and stores model metadata from various providers
- Analyzes model licenses and generates compliance FAQs
- Performs security scans on model files
- Aggregates benchmark leaderboards from multiple sources
- Manages model file downloads and storage

### 2.2 Service Dependencies

| Dependency | Type | Purpose |
|------------|------|---------|
| budapp | Service | Triggers model extraction requests |
| PostgreSQL | Database | Model metadata, licenses, leaderboards |
| Redis/Valkey | Cache/Queue | Caching, job queuing |
| MinIO | Object Storage | Model files, license documents |
| HuggingFace | External | Model metadata, configs |
| BudConnect | External | Cloud model metadata |
| OpenAI/Perplexity | External | License analysis, FAQ generation |
| ClamAV | External | Malware scanning |

### 2.3 Integration Points
- **Inbound**: Model extraction requests from budapp via Dapr pub/sub
- **Outbound**: Stores metadata in PostgreSQL, files in MinIO
- **External APIs**: HuggingFace Hub, BudConnect, OpenAI, benchmark sources
- **Scheduled**: Dapr cron for leaderboard extraction (every 7 days)

---

## 3. Detailed Architecture

### 3.1 Component Diagram

![Budmodel component overview](./images/budmodel-overview.png)


### 3.2 Module Structure

```
budmodel/
├── __init__.py
├── main.py                      # FastAPI app initialization
├── commons/
│   ├── config.py                # Application settings
│   ├── constants.py             # Enums and constants
│   ├── huggingface.py           # HuggingFace utilities
│   ├── inference.py             # LLM inference utilities
│   ├── connect_utils.py         # BudConnect integration
│   └── git_utils.py             # Git operations
├── model_info/
│   ├── routes.py                # API endpoints
│   ├── services.py              # Business logic
│   ├── workflows.py             # Dapr workflows
│   ├── schemas.py               # Pydantic models
│   ├── models.py                # SQLAlchemy models
│   ├── security.py              # Security scanning
│   ├── license.py               # License analysis
│   ├── cloud_service.py         # Cloud model extraction
│   ├── huggingface_aria2.py     # HF download with Aria2
│   └── huggingface_budconnect.py # BudConnect integration
├── leaderboard/
│   ├── routes.py                # API endpoints
│   ├── services.py              # Business logic
│   ├── workflows.py             # Dapr workflows
│   ├── schemas.py               # Pydantic models
│   ├── crud.py                  # CRUD operations
│   ├── parser.py                # Data parsing
│   └── web_crawler.py           # Web scraping
├── metrics_collector/
│   ├── chatbot_arena.py         # Chatbot Arena collector
│   ├── berkeley.py              # Berkeley benchmark
│   ├── mteb_leaderboard.py      # MTEB benchmark
│   ├── live_codebench.py        # LiveCodeBench
│   ├── vllm.py                  # vLLM benchmark
│   ├── alpaca.py                # Alpaca Eval
│   └── ugi.py                   # UGI benchmark
├── shared/
│   ├── aria2_daemon.py          # Aria2 RPC management
│   ├── aria2p_service.py        # Aria2 client
│   ├── io_monitor.py            # I/O monitoring
│   └── volume_detector.py       # Storage detection
└── seeders/
    ├── license_seeder.py        # License data seeding
    └── source_seeder.py         # Benchmark sources
```

### 3.3 Key Flows

#### 3.3.1 Model Extraction Flow

![Model Extraction Flow](./images/budmodel-extraction-flow.png)

#### 3.3.2 Leaderboard Extraction Flow

![Leaderboard Extraction Flow](./images/budmodel-leaderboard-flow.png)

---

## 4. Data Design

### 4.1 Database Schema

#### 4.1.1 model_info Table

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK, DEFAULT uuid4 | Primary key |
| author | TEXT | NULLABLE | Model author/organization |
| description | TEXT | NULLABLE | Model description |
| uri | TEXT | NOT NULL, UNIQUE | Model URI (e.g., meta-llama/Llama-3.1-8B) |
| modality | TEXT | NULLABLE | Model modality (text, vision, audio) |
| tags | JSONB | NULLABLE | Model tags |
| tasks | JSONB | NULLABLE | Supported tasks |
| papers | JSONB | NULLABLE | Related papers |
| github_url | TEXT | NULLABLE | GitHub repository URL |
| provider_url | TEXT | NULLABLE | Provider URL |
| website_url | TEXT | NULLABLE | Website URL |
| logo_url | TEXT | NULLABLE | Logo URL |
| use_cases | JSONB | NULLABLE | Suggested use cases |
| strengths | JSONB | NULLABLE | Model strengths |
| limitations | JSONB | NULLABLE | Model limitations |
| model_tree | JSONB | NULLABLE | Model derivation tree |
| languages | JSONB | NULLABLE | Supported languages |
| architecture | JSONB | NULLABLE | Architecture details |
| extraction_status | ENUM | NOT NULL | completed/partial/cached |
| license_id | UUID | FK -> license_info.id | License reference |
| created_at | TIMESTAMP WITH TZ | DEFAULT NOW() | Creation timestamp |
| modified_at | TIMESTAMP WITH TZ | ON UPDATE | Modification timestamp |

#### 4.1.2 license_info Table

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK, DEFAULT uuid4 | Primary key |
| license_id | TEXT | NOT NULL | License identifier (e.g., apache-2.0) |
| name | TEXT | NOT NULL | License full name |
| url | TEXT | NULLABLE | License URL |
| faqs | JSONB | NULLABLE | Generated FAQs |
| type | TEXT | NULLABLE | License type classification |
| description | TEXT | NULLABLE | License description |
| suitability | TEXT | NULLABLE | Usage suitability assessment |
| is_extracted | BOOLEAN | DEFAULT FALSE | FAQ extraction status |
| created_at | TIMESTAMP WITH TZ | DEFAULT NOW() | Creation timestamp |
| modified_at | TIMESTAMP WITH TZ | ON UPDATE | Modification timestamp |

**Constraint**: `UNIQUE(license_id, url)`

#### 4.1.3 leaderboard Table

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK, DEFAULT uuid4 | Primary key |
| model_info_id | UUID | FK -> model_info.id, NOT NULL | Model reference |
| source_id | UUID | FK -> source.id, NULLABLE | Benchmark source |
| eval_name | VARCHAR(100) | NOT NULL, INDEX | Evaluation metric name |
| normalised_eval_name | VARCHAR(100) | NOT NULL, INDEX | Normalized metric name |
| eval_score | FLOAT | NULLABLE | Score value |
| data_origin | ENUM | NOT NULL | scraped/readme_llm |
| created_at | TIMESTAMP WITH TZ | DEFAULT NOW() | Creation timestamp |
| updated_at | TIMESTAMP WITH TZ | ON UPDATE | Update timestamp |

#### 4.1.4 source Table

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK, DEFAULT uuid4 | Primary key |
| name | VARCHAR(100) | NOT NULL, INDEX | Source name |
| url | TEXT | NOT NULL | Source URL |
| wait_for | TEXT | NULLABLE | CSS selector to wait for |
| js_code | TEXT | NULLABLE | JavaScript to execute |
| schema | TEXT | NULLABLE | Data extraction schema |
| css_base_selector | TEXT | NULLABLE | Base CSS selector |
| is_active | BOOLEAN | DEFAULT TRUE | Active status |
| last_extracted_at | TIMESTAMP WITH TZ | NULLABLE | Last extraction time |
| created_at | TIMESTAMP WITH TZ | DEFAULT NOW() | Creation timestamp |
| updated_at | TIMESTAMP WITH TZ | ON UPDATE | Update timestamp |

#### 4.1.5 model_download_history Table

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK, DEFAULT uuid4 | Primary key |
| status | ENUM | NOT NULL | running/completed/uploaded/failed |
| size | FLOAT | NOT NULL | Size in GB |
| path | TEXT | NOT NULL | Local path |
| created_at | TIMESTAMP WITH TZ | DEFAULT NOW() | Creation timestamp |
| modified_at | TIMESTAMP WITH TZ | ON UPDATE | Modification timestamp |

### 4.2 Key Data Structures

#### 4.2.1 ModelArchitecture

```python
class ModelArchitecture(BaseModel):
    type: Optional[str]                  # e.g., "transformer"
    family: Optional[str]                # e.g., "llama"
    num_params: Optional[int]            # Parameter count
    model_weights_size: Optional[int]    # Weights size in bytes
    kv_cache_size: Optional[int]         # KV cache size
    text_config: Optional[LLMConfig]     # Text model config
    vision_config: Optional[VisionConfig]  # Vision encoder config
    audio_config: Optional[AudioConfig]  # Audio encoder config
    embedding_config: Optional[EmbeddingConfig]  # Embedding config
    classifier_config: Optional[ClassifierConfig]  # Classifier config
```

#### 4.2.2 LLMConfig

```python
class LLMConfig(BaseModel):
    num_layers: Optional[int]
    hidden_size: Optional[int]
    intermediate_size: Optional[int]
    context_length: Optional[int]
    vocab_size: Optional[int]
    torch_dtype: Optional[str]
    num_attention_heads: Optional[int]
    num_key_value_heads: Optional[int]
    rope_scaling: Optional[Dict[str, Any]]
```

---

## 5. API Design

### 5.1 REST Endpoints

#### 5.1.1 POST /model-info/extract
Triggers model metadata extraction workflow.

**Request Body (ModelExtractionRequest)**:
```json
{
  "model_name": "Llama-3.1-8B-Instruct",
  "model_uri": "meta-llama/Llama-3.1-8B-Instruct",
  "provider_type": "hugging_face",
  "hf_token": "hf_xxx"
}
```

**Response (ModelExtractionResponse)**:
```json
{
  "object": "model_extraction",
  "workflow_id": "uuid",
  "model_info": {
    "author": "meta-llama",
    "description": "...",
    "uri": "meta-llama/Llama-3.1-8B-Instruct",
    "modality": "text",
    "tasks": ["text-generation", "chat"],
    "architecture": {...},
    "license": {...}
  },
  "local_path": "/models/meta-llama/Llama-3.1-8B-Instruct",
  "created": 1706000000
}
```

#### 5.1.2 POST /model-info/scan
Performs security scan on downloaded model.

**Request Body**:
```json
{
  "model_path": "/models/meta-llama/Llama-3.1-8B-Instruct"
}
```

**Response**:
```json
{
  "object": "model_security_scan",
  "workflow_id": "uuid",
  "issues": [
    {
      "title": "Unsafe pickle file",
      "severity": "high",
      "description": "...",
      "source": "modelscan"
    }
  ],
  "created": 1706000000
}
```

#### 5.1.3 POST /model-info/cloud-model/extract
Extracts cloud model metadata from BudConnect.

**Request Body**:
```json
{
  "model_uri": "gpt-4",
  "external_service_url": "https://api.budconnect.io"
}
```

#### 5.1.4 POST /model-info/license-faq
Generates license FAQs using LLM analysis.

**Request Body**:
```json
{
  "license_source": "https://opensource.org/licenses/MIT"
}
```

#### 5.1.5 GET /leaderboard/model-params
Gets benchmark scores for a model.

**Query Parameters**:
- `model_uri`: Model URI
- `k`: Number of entries (default: 5)

**Response**:
```json
{
  "object": "leaderboard.model-params",
  "leaderboards": [
    {
      "eval_name": "MMLU",
      "eval_score": 77.4,
      "data_origin": "scraped"
    }
  ]
}
```

#### 5.1.6 GET /leaderboard/models/compare
Compares benchmark scores across models.

**Query Parameters**:
- `model_uris[]`: List of model URIs
- `benchmark_fields[]`: Fields to compare
- `k`: Number of results (default: 5)

#### 5.1.7 POST /leaderboard/extraction-cron
Scheduled leaderboard extraction (Dapr cron trigger).

#### 5.1.8 POST /leaderboard/extraction-cron/trigger
Manual leaderboard extraction trigger.

#### 5.1.9 GET /leaderboard/extraction-cron/health
Health check for extraction scheduler.

---

## 6. Logic and Algorithms

### 6.1 Model Extraction Pipeline

```python
def extract_model_info(request: ModelExtractionRequest) -> ModelInfo:
    # 1. Check cache
    cached = check_existing_model(request.model_uri, COMPLETED)
    if cached:
        return cached

    # 2. Fetch model config from HuggingFace
    config = AutoConfig.from_pretrained(request.model_uri)

    # 3. Extract architecture details
    architecture = extract_architecture(config)

    # 4. Fetch README and parse description
    readme = fetch_model_readme(request.model_uri)
    analysis = analyze_model_description(readme)  # Uses LLM

    # 5. Extract license info
    license_info = extract_license(config, request.model_uri)
    if license_info and not license_info.is_extracted:
        faqs = generate_license_faqs(license_info)
        update_license(license_info.id, faqs=faqs)

    # 6. Save to database
    return save_model_info(...)
```

### 6.2 License Analysis

The LICENSE_ANALYSIS_PROMPT is used with LLMs to generate 22 FAQs covering:
- Modification rights (Q1-Q2)
- Distribution rights (Q3-Q5)
- Commercial use (Q6-Q8)
- Attribution requirements (Q9-Q11)
- API usage (Q12-Q14)
- Patent grants (Q15-Q17)
- Data/privacy (Q18-Q19)
- Liability/termination (Q20-Q22)

### 6.3 Benchmark Collectors

| Collector | Source | Schedule |
|-----------|--------|----------|
| ChatbotArena | lmsys.org | 7 days |
| Berkeley | Function Calling benchmark | 7 days |
| MTEB | HuggingFace MTEB leaderboard | 7 days |
| LiveCodeBench | Live coding benchmark | 7 days |
| vLLM | vLLM compatibility list | 7 days |
| AlpacaEval | Stanford Alpaca | 7 days |
| UGI | Unified General Intelligence | 7 days |

### 6.4 Security Scanning

```python
def scan_model(model_path: str) -> List[ModelIssue]:
    issues = []

    # 1. ClamAV virus scan
    clamav_results = run_clamav_scan(model_path)
    issues.extend(parse_clamav_results(clamav_results))

    # 2. Modelscan for ML-specific vulnerabilities
    modelscan_results = run_modelscan(model_path)
    issues.extend(parse_modelscan_results(modelscan_results))

    # 3. Pickle file analysis
    pickle_issues = analyze_pickle_files(model_path)
    issues.extend(pickle_issues)

    return issues
```

---

## 7. GenAI/ML-Specific Design

### 7.1 LLM Integration

Two LLM use cases:
1. **Model Description Analysis**: Uses MODEL_ANALYSIS_PROMPT to extract structured information
2. **License FAQ Generation**: Uses LICENSE_ANALYSIS_PROMPT for compliance analysis

### 7.2 Model Metadata Extraction

Extracts from HuggingFace config.json:
- `num_hidden_layers` → `num_layers`
- `hidden_size`
- `intermediate_size`
- `max_position_embeddings` → `context_length`
- `vocab_size`
- `torch_dtype`
- `num_attention_heads`
- `num_key_value_heads`

### 7.3 Benchmark Data Sources

Supported leaderboard fields:
- `lc_win_rate`: Chatbot Arena win rate
- `bcfl`: Berkeley Function Calling
- `live_code_bench`: LiveCodeBench
- `classification`, `clustering`, `retrieval`: MTEB metrics
- `mmbench`, `mmstar`, `mmmu`: Vision benchmarks
- `math_vista`, `ai2d`: Math/diagram reasoning

---

## 8. Configuration Management

### 8.1 Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `APP_NAME` | Application name | budmodel |
| `APP_PORT` | API port | 9083 |
| `DATABASE_URL` | PostgreSQL connection | Required |
| `REDIS_URL` | Redis connection | Required |
| `MINIO_ENDPOINT` | MinIO endpoint | Required |
| `MINIO_ACCESS_KEY` | MinIO access key | Required |
| `MINIO_SECRET_KEY` | MinIO secret key | Required |
| `MINIO_BUCKET` | Default bucket | budmodel |
| `HF_TOKEN` | HuggingFace token | Optional |
| `OPENAI_API_KEY` | OpenAI API key | Optional |
| `PERPLEXITY_API_KEY` | Perplexity API key | Optional |
| `BUDCONNECT_URL` | BudConnect API URL | Optional |
| `ARIA2_RPC_SECRET` | Aria2 RPC secret | Optional |

### 8.2 Dapr Cron Binding

```yaml
# .dapr/components/binding.yaml
apiVersion: dapr.io/v1alpha1
kind: Component
metadata:
  name: leaderboard-extraction-cron
spec:
  type: bindings.cron
  metadata:
    - name: schedule
      value: "@every 168h"  # 7 days
    - name: direction
      value: "input"
```

---

## 9. Security Design

### 9.1 Model Security Scanning
- **ClamAV**: Malware detection in model files
- **Modelscan**: ML-specific vulnerability detection (pickle exploits, etc.)
- **File validation**: Safe file extensions, size limits

### 9.2 Authentication
- Dapr API token for service-to-service
- HuggingFace token for gated models
- OpenAI/Perplexity API keys for LLM analysis

### 9.3 Data Protection
- License documents stored in MinIO with encryption
- Model files stored with access controls
- API keys via environment variables (never in code)

---

## 10. Performance Design

### 10.1 Optimization Strategies

| Strategy | Implementation |
|----------|----------------|
| Caching | Model metadata cached after extraction |
| Async downloads | Aria2 for parallel model downloads |
| Batch processing | Leaderboard extraction batched |
| Connection pooling | SQLAlchemy connection pool |
| Rate limiting | HuggingFace API rate limiting |

### 10.2 Performance Targets

| Metric | Target |
|--------|--------|
| Model metadata extraction | < 30s |
| Security scan (10GB model) | < 5 minutes |
| License FAQ generation | < 60s |
| Leaderboard extraction (all sources) | < 30 minutes |

### 10.3 Aria2 Download Manager

Multi-connection download with progress tracking:
```python
aria2_options = {
    "max-connection-per-server": 16,
    "split": 16,
    "min-split-size": "1M",
    "continue": True
}
```

---

## 11. Error Handling

### 11.1 Error Categories

| Category | HTTP Code | Recovery |
|----------|-----------|----------|
| Model not found | 404 | User fixes model URI |
| HuggingFace rate limit | 429 | Exponential backoff |
| Security scan failed | 500 | Retry or manual review |
| License extraction failed | 500 | Fallback to basic info |
| Leaderboard source unavailable | 503 | Skip source, continue others |

### 11.2 Extraction Status

```python
class ModelExtractionStatus(StrEnum):
    COMPLETED = auto()   # Full extraction successful
    PARTIAL = auto()     # Some fields missing
    CACHED = auto()      # Retrieved from BudConnect cache
```

---

## 12. Deployment Design

### 12.1 Container Specifications

```yaml
resources:
  requests:
    cpu: "500m"
    memory: "2Gi"
  limits:
    cpu: "2"
    memory: "8Gi"
```

### 12.2 Volumes

```yaml
volumes:
  - name: models
    persistentVolumeClaim:
      claimName: models-pvc
  - name: aria2-downloads
    emptyDir: {}
```

### 12.3 Health Checks

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 9083
  initialDelaySeconds: 30
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /ready
    port: 9083
  initialDelaySeconds: 5
  periodSeconds: 5
```

---

## 13. Testing Strategy

### 13.1 Unit Tests
- Model extraction parsing
- License FAQ generation
- Leaderboard data parsing
- Security scan result parsing

### 13.2 Integration Tests
- HuggingFace API integration
- PostgreSQL CRUD operations
- MinIO file operations
- Dapr workflow execution

### 13.3 Test Commands

```bash
# Run all tests
pytest

# Run specific module
pytest tests/test_model_extraction.py -v

# Run with coverage
pytest --cov=budmodel
```

---

## 14. Known Limitations

### 14.1 Current Limitations

| Limitation | Impact | Planned Resolution |
|------------|--------|-------------------|
| Single LLM provider | License analysis depends on OpenAI | Multi-provider fallback |
| Manual benchmark mapping | New benchmarks need code changes | Dynamic schema discovery |
| Limited vision model support | Architecture extraction incomplete | Extend architecture parser |
| No model versioning | Can't track model updates | Add version tracking |

### 14.2 Technical Debt

| Item | Priority | Estimated Effort |
|------|----------|------------------|
| Migrate to async HuggingFace client | Medium | 1 sprint |
| Add model comparison API | Low | 2 sprints |
| Implement benchmark score normalization | Medium | 1 sprint |

---

## 15. Appendix

### 15.1 Glossary

| Term | Definition |
|------|------------|
| MTEB | Massive Text Embedding Benchmark |
| MMLU | Massive Multitask Language Understanding |
| Modelscan | Security scanner for ML models |
| Aria2 | Multi-protocol download utility |
| BudConnect | External AI model marketplace API |

### 15.2 License Types

| Type | Description |
|------|-------------|
| Permissive Open Source | MIT, Apache 2.0, BSD |
| Copyleft Open Source | GPL, AGPL |
| Non-Commercial License | CC BY-NC, Llama 2 Community |
| Proprietary | OpenAI, Anthropic models |

### 15.3 Benchmark Fields

```python
LEADERBOARD_FIELDS = Literal[
    "lc_win_rate", "bcfl", "live_code_bench",
    "classification", "clustering", "pair_classification",
    "reranking", "retrieval", "semantic", "summarization",
    "ugi_score", "mmbench", "mmstar", "mmmu",
    "math_vista", "ocr_bench", "ai2d",
    "hallucination_bench", "mmvet", "lmsys_areana"
]
```
