# Implementation Phase Plan: Bud AI Foundry Platform

> **Document Version:** 1.0
> **Date:** 2026-02-05
> **Status:** Active Planning
> **Reference Documents:**
> - [Job, Scheduling & Orchestration Architecture](./job-scheduling-orchestration.md) (v1.3)
> - [Unified GPU & Use Case Platform](./unified-gpu-usecase-platform.md) (v1.8)
> - [Production Scenarios Gap Analysis](./new-scenarios.md)

---

## Executive Summary

This document outlines a phased implementation plan for the Bud AI Foundry platform. **Phase 1 focuses on UseCase deployment**, enabling one-click deployment of RAG, Chatbot, and Agent templates. Serverless features are deferred to Phase 3.

### Phase Overview

| Phase | Focus | Duration | Key Deliverables |
|-------|-------|----------|------------------|
| **Phase 1** | Job Layer + UseCases Foundation | 10-12 weeks | Job abstraction, Component Registry, Basic Templates |
| **Phase 2** | Pipeline Integration + Advanced UseCases | 8-10 weeks | Template-Pipeline generation, Full RAG/Chat/Agent templates |
| **Phase 3** | Serverless + Advanced Scheduling | 10-12 weeks | Scale-to-zero, BudQueue, Kueue quotas |
| **Phase 4** | Enterprise Features | 8-10 weeks | Multi-cluster, Training jobs, Advanced billing |

### Current State Assessment

| Component | Status | Notes |
|-----------|--------|-------|
| **BudCluster** | Exists | Cluster management, Helm deploys, NFD - No Job layer |
| **BudPipeline** | Exists | Pipeline/Step execution, Event-driven actions, DAG engine |
| **BudUseCases** | NOT BUILT | Service does not exist |
| **Job Layer** | NOT BUILT | Schema defined in architecture, not implemented |
| **BudMetrics** | Exists | ClickHouse analytics, time-series - Needs metering extension |
| **BudGateway** | Exists | Rust API gateway - Ready for routing |

---

## Phase 1: Job Layer + UseCases Foundation (10-12 weeks)

### 1.1 Goals

1. **Job Abstraction Layer**: Single tracking point for all cluster workloads
2. **Component Registry**: Database of deployable components (Vector DBs, Models, Services)
3. **Basic Template System**: Simple UseCase templates that deploy multi-component stacks
4. **BudAdmin Integration**: UI for browsing and deploying templates

### 1.2 Template Storage: Hybrid Approach

**Decision**: Use YAML files for system templates, database for all runtime storage.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      TEMPLATE STORAGE ARCHITECTURE                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   SYSTEM TEMPLATES                     USER TEMPLATES                       │
│   (Git-tracked YAML)                   (API/UI-created)                     │
│   ┌─────────────────────┐             ┌─────────────────────┐              │
│   │ templates/system/   │             │ POST /api/templates │              │
│   │ ├── rag/            │             │                     │              │
│   │ │   └── simple.yaml │             │ • Per-tenant        │              │
│   │ └── chatbot/        │             │ • Fork from system  │              │
│   │     └── basic.yaml  │             │ • Immediate effect  │              │
│   └──────────┬──────────┘             └──────────┬──────────┘              │
│              │                                   │                          │
│              │ On startup (seed.py)              │ Direct insert            │
│              ▼                                   ▼                          │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                    PostgreSQL (Runtime Storage)                      │  │
│   │   usecase_templates: is_system=true/false, tenant_id, source_file   │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Benefits:**

| Aspect | YAML (System Templates) | Database (User Templates) |
|--------|------------------------|---------------------------|
| Version control | Git history, PR reviews | Audit table in DB |
| Change process | PR → Review → Merge → Deploy | API call → Immediate |
| Validation | CI + startup validation | API schema validation |
| Multi-tenant | Same for all tenants | Per-tenant isolation |
| Rollback | `git revert` | DB version restore |

### 1.3 Architecture Decisions

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PHASE 1 ARCHITECTURE                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   USER                                                                      │
│    │                                                                        │
│    ▼                                                                        │
│   BudAdmin ──────► BudApp ──────► BudUseCases (NEW)                        │
│   (UI)             (Auth)         │                                         │
│                                   │ 1. Resolve Template                     │
│                                   │ 2. For each component:                  │
│                                   │                                         │
│                                   ▼                                         │
│                              BudCluster                                     │
│                                   │                                         │
│                                   │ 3. Create Job record                    │
│                                   │ 4. Deploy via Helm/Docker               │
│                                   │                                         │
│                                   ▼                                         │
│                              Kubernetes                                     │
│                              (Deployments, Services, PVCs)                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Key Decision**: In Phase 1, BudUseCases calls BudCluster directly for each component deployment. Pipeline integration (DAG execution, dependency ordering) comes in Phase 2.

### 1.3 Detailed Breakdown

#### Week 1-2: Job Model in BudCluster

**Deliverables:**
- Job SQLAlchemy model in BudCluster (based on architecture doc Part 2)
- Alembic migration for `jobs` table
- Job CRUD operations
- Job status enum: `PENDING`, `QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED`, `CANCELLED`

**Schema (from architecture):**
```python
class Job(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str

    # Type & Classification
    job_type: JobType  # SERVICE, BATCH, TRAINING
    source_type: SourceType  # DIRECT, PIPELINE, USECASE, ENDPOINT, POD

    # Source tracking
    cluster_id: UUID
    tenant_id: UUID
    project_id: UUID
    usecase_deployment_id: Optional[UUID]  # If from BudUseCases

    # Status
    status: JobStatus
    status_message: Optional[str]

    # Resources
    resources: dict  # GPU, CPU, memory requests/limits

    # Timestamps
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    # Cost tracking
    estimated_cost: Optional[Decimal]
    actual_cost: Optional[Decimal]
```

**Files to create/modify:**
- `services/budcluster/budcluster/jobs/models.py`
- `services/budcluster/budcluster/jobs/schemas.py`
- `services/budcluster/budcluster/jobs/crud.py`
- `services/budcluster/budcluster/jobs/service.py`
- `services/budcluster/budcluster/alembic/versions/xxx_add_jobs_table.py`

#### Week 3-4: Job API + Internal Job Creation

**Deliverables:**
- Job REST API in BudCluster
- Internal job creation for existing model deployments (Endpoint → Job)
- Job lifecycle hooks (status sync with K8s)

**API Endpoints:**
```yaml
POST   /api/v1/clusters/{cluster_id}/jobs      # Create job
GET    /api/v1/clusters/{cluster_id}/jobs      # List jobs (with filters)
GET    /api/v1/clusters/{cluster_id}/jobs/{id} # Get job details
DELETE /api/v1/clusters/{cluster_id}/jobs/{id} # Cancel/delete job
PATCH  /api/v1/clusters/{cluster_id}/jobs/{id} # Update job (priority, labels)
GET    /api/v1/clusters/{cluster_id}/schedule  # Schedule timeline view
```

**Files to create/modify:**
- `services/budcluster/budcluster/jobs/routes.py`
- `services/budcluster/budcluster/deployment/service.py` (modify to create Job on deploy)

#### Week 5-6: BudUseCases Service Setup

**Deliverables:**
- New BudUseCases service (FastAPI + SQLAlchemy + Dapr)
- Component Registry database model
- Component CRUD API
- Seed data for initial components (Qdrant, Milvus, vLLM, etc.)

**Service structure:**
```
services/budusecases/
├── budusecases/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app
│   ├── commons/                   # Config, DB, logging
│   ├── components/                # Component Registry
│   │   ├── models.py              # ComponentDefinition, ComponentVersion
│   │   ├── schemas.py             # Pydantic schemas
│   │   ├── crud.py                # CRUD operations
│   │   ├── routes.py              # REST API
│   │   └── seed_data.py           # Initial components
│   ├── templates/                 # UseCase Templates
│   │   ├── models.py              # UseCaseTemplate, TemplateParameter
│   │   ├── schemas.py
│   │   ├── crud.py
│   │   ├── routes.py
│   │   └── resolver.py            # Template → Deployment plan
│   └── deployments/               # UseCase Deployments
│       ├── models.py              # UseCaseDeployment, ComponentDeployment
│       ├── schemas.py
│       ├── crud.py
│       ├── routes.py
│       └── service.py             # Orchestrates component deployments
├── alembic/
├── tests/
├── deploy/
├── pyproject.toml
└── CLAUDE.md
```

**Initial Components to seed:**
| Category | Components |
|----------|------------|
| Vector DB | Qdrant, Milvus, Weaviate, Chroma |
| LLM Endpoint | vLLM, TensorRT-LLM, LatentBud |
| Embedding | TEI (Text Embeddings Inference) |
| Orchestrator | RAG Orchestrator (Bud custom) |
| UI | Chat UI (Bud custom) |
| Reranker | Reranker service |

#### Week 7-8: Template System (Hybrid YAML + Database)

**Deliverables:**
- UseCaseTemplate database model
- Template CRUD API
- **YAML template files** for system templates (Git-tracked)
- **Template loader** (seed.py) to sync YAML → DB on startup
- Template resolver (template → list of components to deploy)
- Initial templates: Simple RAG, Simple Chatbot

**Hybrid Architecture:**

```
services/budusecases/
├── templates/
│   ├── system/                        # Git-tracked, PR-reviewed
│   │   ├── rag/
│   │   │   ├── simple-rag-v1.yaml
│   │   │   └── enterprise-rag-v1.yaml
│   │   └── chatbot/
│   │       └── simple-chatbot-v1.yaml
│   └── seed.py                        # Loads YAML → DB on startup
└── budusecases/
    └── templates/
        ├── models.py                  # SQLAlchemy model
        ├── schemas.py                 # Pydantic validation
        ├── crud.py                    # DB operations
        ├── routes.py                  # REST API
        ├── resolver.py                # Template → deployment plan
        └── loader.py                  # YAML parsing
```

**Template Schema (Database):**
```python
class UseCaseTemplate(SQLModel, table=True):
    id: str  # e.g., "simple-rag-v1"
    name: str
    description: str
    category: str  # "rag", "chatbot", "agent"
    version: str

    # User-facing parameters
    parameters: list[TemplateParameter]  # JSON column

    # Components to deploy
    components: list[TemplateComponent]  # JSON column

    # Metadata
    is_active: bool = True
    is_system: bool = True       # True = loaded from YAML, False = user-created
    source_file: Optional[str]   # Path to YAML file (for system templates)
    tenant_id: Optional[UUID]    # Null for system, set for user templates
    forked_from: Optional[str]   # If user forked a system template
    created_at: datetime
```

**Example System Template (YAML):**
```yaml
# templates/system/rag/simple-rag-v1.yaml
id: simple-rag-v1
name: Simple RAG
description: Basic RAG pipeline with vector search and LLM
category: rag
version: "1.0.0"
complexity: simple
tags: [rag, vector-search, beginner]

parameters:
  - name: model_id
    type: model_ref
    label: LLM Model
    required: true

  - name: embedding_model
    type: string
    label: Embedding Model
    default: "BAAI/bge-base-en-v1.5"

  - name: vector_db_size
    type: string
    label: Storage Size
    default: "50Gi"
    options: ["10Gi", "50Gi", "100Gi"]

components:
  - id: vector-db
    component_ref: qdrant
    config:
      persistence:
        size: "{{ parameters.vector_db_size }}"

  - id: embedding
    component_ref: tei-embedding
    config:
      model_id: "{{ parameters.embedding_model }}"

  - id: llm
    component_ref: vllm-endpoint
    model_id: "{{ parameters.model_id }}"
    gpu_count: 1
    optimize_with_budsim: true

  - id: orchestrator
    component_ref: rag-orchestrator
    depends_on: [vector-db, embedding, llm]
    env:
      VECTOR_DB_URL: "{{ components['vector-db'].outputs.url }}"
      EMBEDDING_URL: "{{ components['embedding'].outputs.url }}"
      LLM_URL: "{{ components['llm'].outputs.url }}"
```

**Template Loader (Startup Sync):**
```python
# templates/seed.py
async def seed_system_templates(db: AsyncSession):
    """Load YAML templates into DB on startup."""
    for yaml_file in TEMPLATES_DIR.rglob("*.yaml"):
        data = yaml.safe_load(yaml_file.read_text())
        existing = await crud.get_by_id(data["id"])

        if existing is None:
            await crud.create(**data, is_system=True, source_file=str(yaml_file))
        elif existing.version != data["version"]:
            await crud.update(data["id"], **data)
        # else: same version, skip
```

**Initial Templates:**

| Template ID | Category | Components |
|-------------|----------|------------|
| `simple-rag-v1` | RAG | Qdrant, TEI Embedding, vLLM, RAG Orchestrator |
| `simple-chatbot-v1` | Chatbot | vLLM, Chat UI |

**Files to create:**
- `services/budusecases/templates/system/rag/simple-rag-v1.yaml`
- `services/budusecases/templates/system/chatbot/simple-chatbot-v1.yaml`
- `services/budusecases/templates/seed.py`
- `services/budusecases/budusecases/templates/loader.py`

#### Week 9-10: Deployment Orchestration

**Deliverables:**
- UseCaseDeployment model (tracks deployment of a template)
- ComponentDeployment model (tracks each component within a UseCase)
- Deployment service that calls BudCluster for each component
- Status aggregation (all components healthy = UseCase healthy)

**Deployment Flow:**
```
1. User: POST /usecases/deploy
   {
     "template_id": "simple-rag-v1",
     "project_id": "...",
     "cluster_id": "...",
     "parameters": { "model_id": "meta-llama/Llama-3-70B" }
   }

2. BudUseCases:
   a. Resolve template → list of components
   b. Create UseCaseDeployment record
   c. For each component:
      - Create ComponentDeployment record
      - Call BudCluster: POST /clusters/{id}/jobs
      - Update ComponentDeployment with job_id

3. BudCluster:
   - Creates Job record (source_type=USECASE)
   - Deploys via Helm or Docker
   - Returns job_id

4. Status sync:
   - BudUseCases polls BudCluster for job status
   - Aggregates component statuses
   - Publishes progress events
```

**Files to create:**
- `services/budusecases/budusecases/deployments/models.py`
- `services/budusecases/budusecases/deployments/service.py`
- `services/budusecases/budusecases/deployments/routes.py`

#### Week 11-12: BudAdmin UI Integration

**Deliverables:**
- UseCase catalog page in BudAdmin
- Template detail view with parameters form
- Deployment wizard (select cluster, fill parameters, deploy)
- Deployment status view with component breakdown
- Component browser (explore available components)

**UI Pages:**
```
/usecases                    # Catalog of available templates
/usecases/{id}               # Template detail + "Deploy" button
/usecases/deploy/{id}        # Deployment wizard
/deployments                 # List of user's UseCase deployments
/deployments/{id}            # Deployment status + component list
/components                  # Browse component registry
```

**BudAdmin files to create:**
- `services/budadmin/src/pages/usecases/index.tsx`
- `services/budadmin/src/pages/usecases/[id].tsx`
- `services/budadmin/src/pages/usecases/deploy/[id].tsx`
- `services/budadmin/src/pages/deployments/index.tsx`
- `services/budadmin/src/pages/deployments/[id].tsx`
- `services/budadmin/src/stores/usecaseStore.ts`

### 1.4 Phase 1 Success Criteria

| Metric | Target |
|--------|--------|
| Deploy Simple RAG via UI | < 5 minutes (excluding model load) |
| Job creation success rate | > 99% |
| Component deployment success rate | > 95% |
| UI page load time | < 2 seconds |
| Template resolution time | < 500ms |

### 1.5 Phase 1 Dependencies

| Dependency | Status | Owner | Notes |
|------------|--------|-------|-------|
| BudCluster Helm deployment | Ready | BudCluster | Existing functionality |
| Keycloak authentication | Ready | BudApp | Existing functionality |
| PostgreSQL | Ready | Infrastructure | Existing in dev/prod |
| Dapr service invocation | Ready | Infrastructure | Existing pattern |

---

## Phase 2: Pipeline Integration + Advanced UseCases (8-10 weeks)

### 2.1 Goals

1. **Template → Pipeline Generation**: Templates generate BudPipeline DAGs for ordered deployment
2. **Advanced Templates**: Enterprise RAG, Chatbot with memory, Agent templates
3. **UseCase Lifecycle**: Update, scale, delete operations
4. **Observability**: Metrics dashboards per UseCase

### 2.2 Key Deliverables

#### Week 1-2: Pipeline Generation

- BudUseCases creates Pipeline in BudPipeline for complex deployments
- JOB-type steps in Pipeline call BudCluster
- Dependency ordering (e.g., deploy Vector DB before RAG Orchestrator)

**Pipeline generation example:**
```python
# simple-rag-v1 generates:
Pipeline:
  - Step 1: Deploy Qdrant (type=JOB, wait_for_ready=true)
  - Step 2: Deploy Embedding (type=JOB, wait_for_ready=true)
  - Step 3: Deploy LLM Endpoint (type=JOB, wait_for_ready=true)
  - Step 4: Deploy RAG Orchestrator (type=JOB, depends_on=[1,2,3])
```

#### Week 3-4: Advanced Templates

- **Enterprise RAG** (`enterprise-rag-v1`):
  - Qdrant (HA mode), Embedding, LLM, Reranker, RAG Orchestrator, Chat UI
  - Parameters: replication_factor, gpu_type, context_window

- **Chatbot with Memory** (`chatbot-memory-v1`):
  - Redis (for memory), LLM Endpoint, Chat UI
  - Parameters: memory_ttl, system_prompt

- **Simple Agent** (`simple-agent-v1`):
  - LLM Endpoint, Tool Server, Agent Framework
  - Parameters: tools_enabled[], agent_type

#### Week 5-6: UseCase Lifecycle Management

- Update UseCase (change parameters, upgrade components)
- Scale UseCase (add replicas, change resources)
- Delete UseCase (cascade delete all components)
- Health check aggregation

#### Week 7-8: Observability Integration

- BudMetrics dashboard per UseCase
- Component-level metrics aggregation
- Alerting rules for UseCase health
- Cost tracking per UseCase

#### Week 9-10: BudAdmin Advanced UI

- Pipeline visualization for UseCase deployment progress
- Update/scale/delete operations in UI
- Metrics dashboard integration
- Component health indicators

### 2.3 Phase 2 Success Criteria

| Metric | Target |
|--------|--------|
| Enterprise RAG deployment | < 10 minutes |
| Pipeline execution reliability | > 99% |
| UseCase update without downtime | Yes |
| Metrics dashboard accuracy | > 99% |

---

## Phase 3: Serverless + Advanced Scheduling (10-12 weeks)

### 3.1 Goals (Deferred from original Phase 2)

1. **Serverless Endpoints**: Scale-to-zero SERVICE jobs
2. **BudQueue**: Request queue management for inference
3. **Kueue Integration**: Quotas, fair-share, priority
4. **Auto-scaling**: HPA/KEDA integration

### 3.2 Key Deliverables

- BudQueue service for request queuing
- Scale-to-zero implementation for SERVICE jobs
- Kueue ClusterQueue/LocalQueue configuration
- Priority-based scheduling
- Pre-warmed pool management

### 3.3 Phase 3 Success Criteria

| Metric | Target |
|--------|--------|
| Cold start time | < 30 seconds |
| Scale-to-zero savings | > 40% cost reduction |
| Queue wait time (p99) | < 5 seconds |
| Fair-share accuracy | > 95% |

---

## Phase 4: Enterprise Features (8-10 weeks)

### 4.1 Goals

1. **Multi-cluster Federation**: MultiKueue for cross-cluster scheduling
2. **TRAINING Jobs**: Checkpointing, distributed training
3. **Advanced Billing**: Per-minute metering, invoicing
4. **Agent Templates**: LangGraph, CrewAI integration

### 4.2 Key Deliverables

- MultiKueue deployment in BudCluster
- TRAINING job type with checkpoint support
- Billing integration (Stripe or custom)
- Agent template library

---

## Risk Assessment

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Job layer complexity | High | Medium | Start with minimal schema, iterate |
| BudUseCases scope creep | Medium | High | Strict MVP definition, defer advanced features |
| BudPipeline integration complexity | High | Medium | Phase 2 only after Phase 1 stable |
| UI development delays | Medium | Medium | Use existing Ant Design components |
| Helm chart compatibility | Medium | Low | Test with existing component charts |

---

## Resource Requirements

### Phase 1 Team

| Role | FTE | Responsibilities |
|------|-----|------------------|
| Backend Engineer | 2 | Job layer, BudUseCases service |
| Frontend Engineer | 1 | BudAdmin UI |
| DevOps | 0.5 | Infrastructure, CI/CD |
| QA | 0.5 | Testing, validation |

### Infrastructure

| Component | Environment | Specification |
|-----------|-------------|---------------|
| PostgreSQL | Dev/Staging | Shared instance |
| PostgreSQL | Production | Dedicated RDS/CloudSQL |
| Kubernetes | Dev | 2-node cluster with GPU |
| Kubernetes | Staging/Prod | Multi-node with GPU pools |

---

## Appendix A: API Contracts

### BudUseCases API (Phase 1)

```yaml
# Components
GET    /api/v1/components                          # List components
GET    /api/v1/components/{id}                     # Get component
GET    /api/v1/components/search                   # Search by category/tags

# Templates
GET    /api/v1/templates                           # List templates
GET    /api/v1/templates/{id}                      # Get template
GET    /api/v1/templates/{id}/schema               # Get parameter schema

# Deployments
POST   /api/v1/deployments                         # Deploy UseCase
GET    /api/v1/deployments                         # List deployments
GET    /api/v1/deployments/{id}                    # Get deployment status
GET    /api/v1/deployments/{id}/components         # Get component statuses
DELETE /api/v1/deployments/{id}                    # Delete UseCase
```

### BudCluster Job API (Phase 1)

```yaml
POST   /api/v1/clusters/{cluster_id}/jobs          # Create job
GET    /api/v1/clusters/{cluster_id}/jobs          # List jobs
GET    /api/v1/clusters/{cluster_id}/jobs/{id}     # Get job
DELETE /api/v1/clusters/{cluster_id}/jobs/{id}     # Cancel job
PATCH  /api/v1/clusters/{cluster_id}/jobs/{id}     # Update job
```

---

## Appendix B: Database Schema Summary

### BudCluster (New Tables)

```sql
-- jobs table
CREATE TABLE jobs (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    job_type VARCHAR(50) NOT NULL,  -- SERVICE, BATCH, TRAINING
    source_type VARCHAR(50) NOT NULL,  -- DIRECT, PIPELINE, USECASE, ENDPOINT, POD
    cluster_id UUID NOT NULL REFERENCES clusters(id),
    tenant_id UUID NOT NULL,
    project_id UUID NOT NULL,
    usecase_deployment_id UUID,  -- FK to budusecases
    status VARCHAR(50) NOT NULL,
    status_message TEXT,
    resources JSONB,
    estimated_cost DECIMAL(10,4),
    actual_cost DECIMAL(10,4),
    created_at TIMESTAMP WITH TIME ZONE,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_jobs_cluster_id ON jobs(cluster_id);
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_source_type ON jobs(source_type);
```

### BudUseCases (New Database)

```sql
-- component_definitions table
CREATE TABLE component_definitions (
    id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(50) NOT NULL,
    version VARCHAR(50) NOT NULL,
    deployment_type VARCHAR(50) NOT NULL,  -- HELM, DOCKER, MODEL
    helm_repo VARCHAR(500),
    helm_chart VARCHAR(200),
    helm_version VARCHAR(50),
    default_values JSONB,
    image VARCHAR(500),
    image_tag VARCHAR(100),
    default_env JSONB,
    default_resources JSONB,
    required_inputs JSONB,
    outputs JSONB,
    health_check_path VARCHAR(200),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE
);

-- usecase_templates table (Hybrid: YAML system templates + DB user templates)
CREATE TABLE usecase_templates (
    id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(50) NOT NULL,
    version VARCHAR(50) NOT NULL,
    complexity VARCHAR(50) DEFAULT 'simple',  -- simple, intermediate, advanced
    tags JSONB DEFAULT '[]',
    parameters JSONB NOT NULL,
    components JSONB NOT NULL,
    routing JSONB,                             -- BudGateway config
    observability JSONB,                       -- Dashboard/alert config
    is_active BOOLEAN DEFAULT TRUE,
    is_system BOOLEAN DEFAULT TRUE,            -- True = YAML source, False = user-created
    source_file VARCHAR(500),                  -- Path to YAML (for system templates)
    tenant_id UUID,                            -- Null for system, set for user templates
    forked_from VARCHAR(100),                  -- If user forked a system template
    created_by UUID,                           -- User who created (for user templates)
    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_templates_category ON usecase_templates(category);
CREATE INDEX idx_templates_tenant ON usecase_templates(tenant_id);
CREATE INDEX idx_templates_is_system ON usecase_templates(is_system);

-- usecase_deployments table
CREATE TABLE usecase_deployments (
    id UUID PRIMARY KEY,
    template_id VARCHAR(100) REFERENCES usecase_templates(id),
    project_id UUID NOT NULL,
    cluster_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    parameters JSONB,
    status VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE
);

-- component_deployments table
CREATE TABLE component_deployments (
    id UUID PRIMARY KEY,
    usecase_deployment_id UUID REFERENCES usecase_deployments(id),
    component_id VARCHAR(100) REFERENCES component_definitions(id),
    job_id UUID,  -- FK to budcluster.jobs
    status VARCHAR(50) NOT NULL,
    config JSONB,
    outputs JSONB,  -- url, api_key, etc.
    created_at TIMESTAMP WITH TIME ZONE
);
```

---

## Changelog

### Version 1.1 (2026-02-05)
- **Hybrid Template Storage**: Updated to use YAML files for system templates + database for user templates
- Added template file structure (templates/system/*.yaml)
- Added seed.py loader for YAML → DB sync on startup
- Added example YAML template (simple-rag-v1.yaml)
- Updated database schema with source_file, tenant_id, forked_from columns
- Added architecture diagram for hybrid storage approach

### Version 1.0 (2026-02-05)
- Initial phase plan created
- Phase 1 focused on UseCases (not Serverless)
- Serverless deferred to Phase 3
- Detailed week-by-week breakdown for Phase 1
