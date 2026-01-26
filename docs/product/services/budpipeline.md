# budpipeline - Low-Level Design
---

## 1. Document Overview

### 1.1 Purpose

This LLD provides build-ready technical specifications for budpipeline, the pipeline orchestration service of Bud AI Foundry. Developers should be able to implement workflow definitions, executions, scheduling, and event-driven triggers directly from this document.

### 1.2 Scope

**In Scope:**
- Pipeline/workflow definition management with DAG structures
- Execution lifecycle with optimistic locking
- Pluggable action architecture with declarative metadata
- Event-driven step completion for long-running operations
- Progress tracking with weighted averaging
- Cron-based scheduling and webhook triggers
- Callback subscription management
- Data retention and cleanup workflows

**Out of Scope:**
- User authentication (handled by budapp)
- Model inference (handled by budgateway)
- Cluster management (handled by budcluster)
- Performance optimization (handled by budsim)

---

## 2. System Context & Assumptions

### 2.1 Business Assumptions

- Users create multi-step workflows for model operations
- Pipelines may run for minutes to hours (model downloads, benchmarks)
- Multiple concurrent executions of the same pipeline are common
- Real-time progress visibility is critical for UX
- Webhooks enable external system integration

### 2.2 Technical Assumptions

- PostgreSQL with async support (asyncpg) is available
- Dapr sidecar provides pub/sub and service invocation
- Redis/Valkey provides state store for Dapr
- External services (budcluster, budmodel) are reachable via Dapr
- Keycloak JWT validation handled by budapp gateway

### 2.3 Constraints

| Constraint Type | Description | Impact |
|-----------------|-------------|--------|
| Concurrent Updates | Optimistic locking required | Version conflicts possible |
| Progress Monotonic | Progress can only increase | Cannot show step rollbacks |
| Retention | 30-day default retention | Old executions auto-deleted |
| Circuit Breaker | Opens after 5 failures | 30s recovery period |

### 2.4 External Dependencies

| Dependency | Type | Failure Impact | Fallback Strategy |
|------------|------|----------------|-------------------|
| PostgreSQL | Required | No persistence | Return 503 |
| Redis/Valkey | Required | No Dapr state | Service degraded |
| budcluster | Optional | Cluster actions fail | Return error to step |
| budmodel | Optional | Model actions fail | Return error to step |
| budapp | Consumer | No auth proxy | Queue events |
| budnotify | Optional | No notifications | Log warning |

---

## 3. Detailed Architecture

### 3.1 Component Overview

![Budpipeline component overview](./images/budpipeline-overview.png)
#### 3.2.1 Pipeline Module

**Purpose:** Manages pipeline definitions and executions

**Key Classes:**
- `PipelineDefinition` - Workflow DAG storage
- `PipelineExecution` - Execution state with optimistic locking
- `StepExecution` - Step-level state tracking
- `PipelineCRUD` - Database operations with version checking
- `PipelineService` - Business logic orchestration

#### 3.2.2 Actions Module

**Purpose:** Pluggable action architecture for extensibility

**Structure:**

#### 3.2.3 Progress Module

**Purpose:** Tracks and aggregates execution progress

**Key Features:**
- Weighted averaging across concurrent steps
- Monotonic enforcement (progress never decreases)
- ETA estimation based on step durations
- Event publishing to callback topics

#### 3.2.4 Scheduler Module

**Purpose:** Cron schedules and trigger management

**Trigger Types:**
- Cron schedules (interval-based)
- Webhooks (HTTP-triggered)
- Event triggers (Dapr pub/sub)

---

## 4. Data Design

### 4.1 Entity Relationship Diagram

![ER Diagram](./images/budpipeline-er-diagram.png)

### 4.2 Status Enumerations

**PipelineStatus (Definition):**

| Status | Description |
|--------|-------------|
| DRAFT | Under construction, not executable |
| ACTIVE | Ready for execution |
| ARCHIVED | Soft-deleted, not listed |

**ExecutionStatus:**

| Status | Description |
|--------|-------------|
| PENDING | Created, not yet started |
| RUNNING | Currently executing |
| COMPLETED | Successfully finished |
| FAILED | Terminated with error |
| INTERRUPTED | Manually stopped |

**StepStatus:**

| Status | Description |
|--------|-------------|
| PENDING | Not yet started |
| RUNNING | Currently executing |
| COMPLETED | Successfully finished |
| FAILED | Step failed |
| SKIPPED | Skipped due to condition |
| RETRYING | Retry in progress |
| TIMEOUT | Timed out waiting for event |

### 4.3 Optimistic Locking

All main entities use version columns for concurrent update handling:

**Update Pattern:**

---

## 5. API & Interface Design

### 5.1 Pipeline Management APIs
#### 5.1.2 POST /executions

**Purpose:** Start pipeline execution

#### 5.1.3 GET /executions/{id}/progress

**Purpose:** Get detailed execution progress

**Query Parameters:**
- `granularity`: "summary" | "steps" | "detailed"
- `include_eta`: boolean

### 5.3 Scheduling APIs
#### 5.3.2 POST /webhooks

**Purpose:** Create webhook trigger

---

## 6. Configuration & Environment

### 6.1 Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| DATABASE_URL | Yes | - | PostgreSQL async connection string |
| DAPR_HTTP_ENDPOINT | Yes | - | Dapr sidecar HTTP endpoint |
| DAPR_API_TOKEN | Yes | - | Dapr authentication token |
| APP_API_TOKEN | Yes | - | Application-level auth token |
| PIPELINE_RETENTION_DAYS | No | 30 | Days to retain execution history |
| PIPELINE_CLEANUP_SCHEDULE | No | 0 3 * * * | Cron for retention cleanup |
| DB_RETRY_MAX_ATTEMPTS | No | 3 | Max database retry attempts |
| CIRCUIT_BREAKER_FAILURE_THRESHOLD | No | 5 | Failures before circuit opens |
| CIRCUIT_BREAKER_RECOVERY_TIMEOUT | No | 30 | Seconds before recovery attempt |

---

## 7. Security Design

### 7.1 Authentication Layers

| Layer | Mechanism | Validates |
|-------|-----------|-----------|
| Service Mesh | dapr-api-token | Inter-service calls |
| Application | APP_API_TOKEN | Internal endpoints |
| External | Keycloak JWT | User requests (via budapp) |

---

## 8. Performance & Scalability

### 8.1 Resilience Stack

| Component | Configuration | Purpose |
|-----------|---------------|---------|
| Circuit Breaker | 5 failures → open, 30s recovery | Prevent cascade failures |
| Retry | Exponential backoff, 3 attempts | Handle transient errors |
| In-Memory Fallback | Serves stale data | Degraded availability |

### 8.4 Scaling Considerations

- **Horizontal:** Multiple budpipeline replicas behind load balancer
- **Database:** Connection pooling with asyncpg
- **Events:** Non-blocking async publishing
- **Retention:** Automated cleanup prevents unbounded growth

---

## 9. Deployment & Infrastructure

### 10.2 Resource Requirements

| Component | CPU | Memory | Notes |
|-----------|-----|--------|-------|
| budpipeline | 500m-2 | 512Mi-2Gi | Scales with concurrent executions |
| Dapr sidecar | 100m | 128Mi | Per pod |

### 10.3 Health Checks
