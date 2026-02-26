# Production Scenarios: Gap Analysis & Required Features

> **Document Version:** 1.0
> **Date:** 2026-02-05
> **Status:** Analysis Complete
> **Reference Documents:**
> - [Job, Scheduling & Orchestration Architecture](./job-scheduling-orchestration.md) (v1.2)
> - [Unified GPU & Use Case Platform](./unified-gpu-usecase-platform.md) (v1.8)
> - [Original Scenarios List](./job-scenarios.md)

---

## Executive Summary

This document analyzes 17 categories of production scenarios (217 individual items) against the current architecture documentation. Each scenario is marked as:

| Status | Meaning | Count |
|--------|---------|-------|
| **ADDRESSED** | Fully covered in architecture docs | 57 |
| **HANDLED BY K8S/KUEUE** | Native K8s/Kueue features, no custom implementation | 18 |
| **OPS/INFRA** | Infrastructure/operations concern, not architecture | 28 |
| **ROADMAP (P2)** | Planned for Phase 2, on roadmap | 38 |
| **NOT NEEDED** | Analyzed and determined unnecessary for platform | 12 |
| **PARTIAL** | Some aspects covered, gaps remain | 56 |
| **GAP** | Not addressed, needs architecture work | 8 |

**Priority Breakdown:**
- **P0 (Must Have for Production):** 0 gaps (Security/DR/HA/Edge Cases covered)
- **P1 (Required for Enterprise):** 2 gaps (HPO integration, Capacity booking)
- **P2 (Roadmap):** 6 gaps (Secrets management improvements, Section 18 items)
- **True Gaps:** 8 total (4 secrets, 1 HPO, 1 capacity, 3 Section 18)

---

## Table of Contents

1. [Security & Access Control](#1-security--access-control) - P0
2. [Disaster Recovery & High Availability](#2-disaster-recovery--high-availability) - P0
3. [Multi-Tenancy Deep Dive](#3-multi-tenancy-deep-dive) - P1 (Mostly HANDLED BY KUEUE)
4. [Observability & Debugging](#4-observability--debugging) - P0 (Mostly ADDRESSED by LGTM)
5. [Cost Management & FinOps](#5-cost-management--finops) - P1 (PARTIAL - Core Exists)
6. [Operations & Maintenance](#6-operations--maintenance) - P0 (Mostly OPS/INFRA)
7. [Performance & Scale](#7-performance--scale) - P1 (Mostly OPS/INFRA)
8. [Data Management](#8-data-management) - P1 (Mostly ADDRESSED)
9. [Compliance & Governance](#9-compliance--governance) - P1 (Mostly ROADMAP P2)
10. [ML-Specific Scenarios](#10-ml-specific-scenarios) - P1 (Mostly ADDRESSED/PARTIAL)
11. [Integration & Interoperability](#11-integration--interoperability) - P2 (Mostly PARTIAL)
12. [User Experience & Self-Service](#12-user-experience--self-service) - P2 (Mostly ROADMAP P2)
13. [Edge Cases & Failure Modes](#13-edge-cases--failure-modes) - P0 (Mostly ADDRESSED)
14. [SLA & Quality of Service](#14-sla--quality-of-service) - P1 (PARTIAL - Foundation Exists)
15. [Migration & Upgrades](#15-migration--upgrades) - P2 (Mostly OPS/INFRA)
16. [Advanced Scheduling Scenarios](#16-advanced-scheduling-scenarios) - P1 (Mostly PARTIAL)
17. [Network & Storage Specifics](#17-network--storage-specifics) - P2 (Mostly OPS/INFRA)
18. [Missing Scenarios (Not in Original List)](#18-missing-scenarios)

---

## 1. Security & Access Control

**Priority: P0 (Must Have for Production)**

### 1.1 Job-Level RBAC & Permissions

| Scenario | Status | Notes |
|----------|--------|-------|
| Who can create/cancel/view jobs in a project? | **ADDRESSED** | See job-scheduling-orchestration.md Part 11 - Source-based authorization |
| Can a user cancel another user's job in the same tenant? | **ADDRESSED** | Source owners or users with job:manage scope can cancel |
| How are permissions inherited from project → pipeline → job? | **ADDRESSED** | Tenant → Project → Source (Pipeline/UseCase/Endpoint) → Job |
| Row-level security for Job queries | **ADDRESSED** | Tenant isolation + source-based filtering in list queries |

**Implemented in:** [job-scheduling-orchestration.md Part 11](./job-scheduling-orchestration.md#part-11-job-authorization--access-control)

Key design decisions:
- **Source-Based Authorization**: Jobs inherit permissions from their source entity (Pipeline, UseCase, Endpoint, Pod)
- **Admin Override**: Users with `job:manage` scope can manage any job in the project
- **JobAuthService**: Centralized authorization service in BudCluster

---

### 1.2 Secrets Management for Jobs

| Scenario | Status | Notes |
|----------|--------|-------|
| How do jobs access secrets (API keys, DB credentials)? | **GAP** | Need secrets injection mechanism |
| Secret injection mechanism (env vars, mounted volumes, external vault)? | **GAP** | Define injection patterns |
| Secret rotation while jobs are running | **GAP** | Hot reload mechanism needed |
| Audit trail for secret access by jobs | **GAP** | Logging integration required |

**Required Architecture Addition:**

```yaml
# Proposed Secret Management Model
secret_sources:
  - type: kubernetes_secret
    description: Native K8s secrets (default)
    injection: env_vars | volume_mount

  - type: vault
    description: HashiCorp Vault integration
    injection: sidecar | init_container
    rotation: supported

  - type: cloud_provider
    description: AWS Secrets Manager, Azure Key Vault
    injection: CSI driver

audit_requirements:
  - Log all secret access attempts
  - Include: job_id, secret_name, timestamp, accessor
  - Retention: 90 days minimum
```

---

### 1.3 Network Policies & Job Isolation

| Scenario | Status | Notes |
|----------|--------|-------|
| Can Job A communicate with Job B in the same tenant? | **NOT NEEDED** | K8s allows pod-to-pod communication by default within namespace. Distributed training (PyTorch DDP) works out of the box. |
| Cross-tenant network isolation enforcement | **ADDRESSED** | Apply NetworkPolicy during tenant onboarding. Simple ~20 lines of YAML. |
| Egress control (can training jobs phone home?) | **NOT NEEDED** | Adds complexity without clear benefit. Jobs need external access (HuggingFace, S3, etc.). |
| Service mesh integration (Istio/Linkerd) | **NOT NEEDED** | Overkill for ML workloads. Adds sidecar overhead, debugging complexity. Namespace isolation is sufficient. |

**Implementation:**

Cross-tenant isolation is handled by a simple NetworkPolicy applied during tenant onboarding in BudCluster:

```yaml
# Applied to each tenant namespace during TenantOnboarding
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: tenant-isolation
  namespace: tenant-${TENANT_ID}
spec:
  podSelector: {}  # Apply to all pods
  policyTypes: [Ingress, Egress]
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              bud.ai/tenant-id: "${TENANT_ID}"  # Same tenant
        - namespaceSelector:
            matchLabels:
              bud.ai/system: "true"  # Platform services
  egress:
    - {}  # Allow all egress (jobs need HuggingFace, S3, etc.)
```

**Decision Rationale:**
- **Intra-tenant**: Works by default in K8s, no action needed
- **Cross-tenant**: Simple NetworkPolicy, ~1 day effort, applied during onboarding
- **Egress**: Not restricting - ML jobs legitimately need external access (model registries, cloud storage, package repos)
- **Service mesh**: Skipped - adds complexity without benefit for ML workloads

---

### 1.4 Container Image Security

| Scenario | Status | Notes |
|----------|--------|-------|
| Image scanning before job admission | **ROADMAP (P2)** | Users can bring their own images - need scanning. Phase 2 implementation. |
| Allowed/blocked image registries per tenant | **ROADMAP (P2)** | Enterprise compliance feature. Phase 2. |
| Image signature verification | **NOT NEEDED** | Cosign/Notary is overkill except for FedRAMP. Skip unless customer requires. |
| Vulnerability discovered in running job's image | **ROADMAP (P2)** | Operational playbook. Phase 2. |

**Why This Matters:**
- Users can bring their own container images (BYOI)
- Custom images may contain vulnerabilities or malicious code
- Enterprise customers will require image scanning for compliance

**Phase 2 Implementation:**

```yaml
# Image Security Model (Phase 2)
implementation:
  tool: Kyverno + Trivy (or Gatekeeper + Trivy)

  admission_policy:
    # Async scanning - don't block submission, but track scan status
    scan_mode: async  # Don't add latency to job submission
    scan_on: image_first_seen  # Only scan new images, cache results

    severity_action:
      critical: block_new_jobs + alert
      high: warn + allow
      medium: log_only
      low: ignore

  trusted_registries:
    # These bypass scanning (pre-vetted)
    - nvcr.io/nvidia/*
    - ghcr.io/huggingface/*
    - gcr.io/bud-ai-foundry/*

  tenant_registries:
    # Per-tenant allowlist (configured during onboarding)
    - ${tenant}.azurecr.io/*
    - ${tenant}.ecr.aws/*

  scan_cache:
    # Cache scan results by image digest
    ttl: 7 days
    storage: Redis/Valkey
```

**Effort Estimate:** 2-3 weeks (Phase 2)
**Dependencies:** Kyverno or Gatekeeper installed on clusters

---

### 1.5 Privileged Operations

| Scenario | Status | Notes |
|----------|--------|-------|
| Can jobs run as root? | **HANDLED BY K8S** | Use PodSecurityStandards (PSS) "baseline" profile on tenant namespaces |
| GPU driver access and security implications | **HANDLED BY K8S** | NVIDIA device plugin (via HAMI) handles `/dev/nvidia*` access automatically |
| Host path mounts for training data | **NOT NEEDED** | Cloud-native approach uses PVCs and object storage (S3/GCS), not host paths |
| Seccomp/AppArmor profiles for containers | **HANDLED BY K8S** | PSS "baseline" profile includes appropriate seccomp defaults |

**Implementation:**

Kubernetes PodSecurityStandards (PSS) handles all of this natively. Apply during tenant onboarding:

```yaml
# Apply PSS "baseline" profile to tenant namespace during onboarding
apiVersion: v1
kind: Namespace
metadata:
  name: tenant-${TENANT_ID}
  labels:
    bud.ai/tenant-id: "${TENANT_ID}"
    # PodSecurityStandards - enforces security without blocking GPU workloads
    pod-security.kubernetes.io/enforce: baseline
    pod-security.kubernetes.io/enforce-version: latest
    pod-security.kubernetes.io/warn: restricted
    pod-security.kubernetes.io/warn-version: latest
```

**What PSS "baseline" provides:**
- Prevents privileged containers
- Prevents host namespace access (hostPID, hostIPC, hostNetwork)
- Prevents hostPath mounts (use PVCs instead)
- Allows GPU device access (NVIDIA device plugin handles this)
- Allows non-root containers with appropriate capabilities

**GPU Access:**
- NVIDIA device plugin (deployed via HAMI during cluster onboarding)
- Automatically mounts `/dev/nvidia*` when job requests `nvidia.com/gpu`
- No special configuration needed - already works

**No custom implementation required** - just namespace labels during tenant onboarding.

---

## 2. Disaster Recovery & High Availability

**Priority: P0 (Must Have for Production)**

### 2.1 BudCluster Service Failure

| Scenario | Status | Notes |
|----------|--------|-------|
| What happens to running jobs if BudCluster crashes? | **ALREADY HANDLED** | Jobs run on K8s, not BudCluster. BudCluster is control plane only - jobs continue running. |
| Job state reconstruction from Kubernetes | **ADDRESSED** | Added JobReconciler in Section 9.2.1 of job-scheduling-orchestration.md |
| Preventing duplicate job submissions during recovery | **ADDRESSED** | Added `idempotency_key` field to Job schema (Section 2.6) and Section 9.2.2 |
| Leader election for BudCluster replicas | **NOT NEEDED** | BudCluster is stateless - multiple replicas share same DB. No leader election required. |

**What happens during BudCluster downtime:**
```
UNAFFECTED (continue running):          AFFECTED (control plane only):
├── Running pods/deployments            ├── New job submissions
├── Kueue workloads                     ├── Job status updates to DB
├── K8s scheduler                       ├── Job cancellation requests
└── Inference traffic                   └── Pipeline step execution

On BudCluster restart:
1. JobReconciler syncs DB with K8s state
2. Resume watching Kueue workload status
3. Resume Dapr workflow processing
```

**Implemented in:** [job-scheduling-orchestration.md Section 9.2.1](./job-scheduling-orchestration.md#921-job-reconciliation-on-startup)

---

### 2.2 Database Failure & Recovery

| Scenario | Status | Notes |
|----------|--------|-------|
| Job table in PostgreSQL—backup strategy? | **OPS/INFRA** | Use managed DB (RDS/Cloud SQL) or standard pg_dump + WAL. Operational runbook, not architecture. |
| Point-in-time recovery requirements | **OPS/INFRA** | SLA decisions documented in runbook, not architecture. |
| Split-brain between BudCluster DB and Kubernetes state | **ADDRESSED** | K8s is source of truth for running state. JobReconciler handles sync (Section 9.2.1). |
| Transaction handling for job creation (DB + K8s atomicity) | **SIMPLE APPROACH** | DB first → K8s second → mark failed if K8s fails. Saga pattern is overkill. |

**Bottom line:** Database backup/recovery is infrastructure ops. Use managed database services.

---

### 2.3 Kueue Controller Failure

| Scenario | Status | Notes |
|----------|--------|-------|
| Impact on queued vs running jobs | **HANDLED BY KUEUE** | Running jobs continue (K8s scheduler). Queued jobs wait (CRDs persist in etcd). |
| Workload state recovery | **HANDLED BY KUEUE** | Kueue is a K8s controller - reconciles from etcd on restart. No action needed. |
| Quota accounting consistency after restart | **HANDLED BY KUEUE** | Recalculates from cluster state automatically. |

**Kueue is self-healing** - it's a Kubernetes controller that:
- Persists state in etcd (Workload CRDs)
- Reconciles on restart
- Running jobs are unaffected (managed by K8s scheduler, not Kueue)

---

### 2.4 Cross-Region Disaster Recovery

| Scenario | Status | Notes |
|----------|--------|-------|
| Active-passive vs active-active multi-region | **P2 - DEFER** | Enterprise feature. Most customers start single-region. |
| Job migration between regions | **P2 - DEFER** | Requires checkpoint/state migration. Phase 2. |
| Data replication for training jobs | **P2 - DEFER** | S3 cross-region replication. Configure when needed. |
| DNS failover for SERVICE jobs | **P2 - DEFER** | Standard cloud DNS failover (Route53, CloudFlare). |

**Cross-region DR is an enterprise/Phase 2 feature.** Start with single-region, add multi-region when customers require it.

---

### 2.5 Backup & Restore for Pipelines

| Scenario | Status | Notes |
|----------|--------|-------|
| Can pipelines be exported/import? | **P2 - NICE TO HAVE** | Pipelines are in DB - can export as JSON. Not critical for MVP. |
| Version control for pipeline definitions | **P2 - NICE TO HAVE** | Useful for rollback but not essential. |
| Restoring a pipeline to a previous version mid-execution | **NOT NEEDED** | Edge case. Cancel and restart is simpler. |

**Required Architecture Addition:**

```yaml
# Proposed Pipeline Versioning Model
export_format:
  type: yaml
  includes:
    - pipeline_definition
    - step_configurations
    - trigger_configurations
    - secrets (references only, not values)

versioning:
  model: immutable versions
  on_update: create new version, link to previous
  retention: all versions (soft delete)

  schema:
    pipeline_id: UUID
    version: int (auto-increment)
    definition: JSON
    created_at: datetime
    created_by: UUID
    is_active: bool

api:
  export: GET /api/pipelines/{id}/export
  import: POST /api/pipelines/import
  versions: GET /api/pipelines/{id}/versions
  rollback: POST /api/pipelines/{id}/rollback?version=N
```

---

## 3. Multi-Tenancy Deep Dive

**Priority: P1 (Required for Enterprise)** → **Revised: Mostly HANDLED BY K8S/KUEUE**

> **Summary**: Kueue provides robust multi-tenancy via LocalQueue/ClusterQueue/Cohort hierarchy.
> Kubernetes handles resource isolation via cgroups v2. Most "gaps" here are UX/admin automation
> features, not architectural blockers.

---

### 3.1 Noisy Neighbor Prevention

| Scenario | Status | Notes |
|----------|--------|-------|
| CPU/memory bandwidth isolation | **HANDLED BY K8S** | K8s resource limits + requests with cgroups v2 provide isolation. Dedicated node pools for sensitive tenants if needed. |
| GPU memory isolation (MPS vs MIG vs time-slicing) | **ADDRESSED** | Covered in Part 7 of architecture doc. MIG for hardware isolation (A100/H100), HAMI time-slicing for software isolation. |
| Network bandwidth throttling per tenant | **NOT NEEDED** | ML workloads typically need full bandwidth for distributed training. Cilium bandwidth manager available if needed later. |
| Storage IOPS limits | **OPS/INFRA** | Cloud storage providers handle this via StorageClass. CSI driver concern, not application architecture. |

**No architecture addition needed** - K8s/Kueue handles isolation natively.

---

### 3.2 Tenant Quota Management

| Scenario | Status | Notes |
|----------|--------|-------|
| Quota increase requests workflow | **ROADMAP (P2)** | Admin/UX feature. Manual process via platform admin works initially. |
| Temporary quota bursting | **HANDLED BY KUEUE** | Cohort borrowing is built into Kueue. Tenants in same cohort can borrow unused quota automatically. |
| Quota alerts and notifications | **OPS/INFRA** | Prometheus alerts on Kueue metrics (`kueue_cluster_queue_resource_usage`). Grafana dashboards. |
| Historical quota utilization reporting | **ROADMAP (P2)** | Analytics/BI feature. BudMetrics can aggregate from Kueue metrics. |

**Kueue Quota Architecture (already in Part 7):**
```yaml
# LocalQueue per tenant with quota limits
apiVersion: kueue.x-k8s.io/v1beta1
kind: LocalQueue
metadata:
  name: tenant-acme-queue
  namespace: tenant-acme
spec:
  clusterQueue: gpu-cluster-queue

# ClusterQueue defines total capacity
apiVersion: kueue.x-k8s.io/v1beta1
kind: ClusterQueue
metadata:
  name: gpu-cluster-queue
spec:
  cohort: production  # Enables borrowing between queues in cohort
  resourceGroups:
    - coveredResources: ["nvidia.com/gpu"]
      flavors:
        - name: gpu-a100
          resources:
            - name: nvidia.com/gpu
              nominalQuota: 16
              borrowingLimit: 8  # Can borrow up to 8 more
```

---

### 3.3 Tenant Onboarding/Offboarding

| Scenario | Status | Notes |
|----------|--------|-------|
| Automated namespace and LocalQueue creation | **ROADMAP (P2)** | Currently manual via Helm/kubectl. Automation would be nice but not blocking. |
| Default ResourceFlavor allocation | **ROADMAP (P2)** | Default quotas defined in ClusterQueue. Per-tenant customization is manual. |
| Cleanup when tenant is deleted | **ROADMAP (P2)** | BudApp handles tenant deletion. K8s namespace deletion cascades resources. |
| Tenant data export requirements (GDPR) | **ROADMAP (P2)** | Enterprise compliance feature. Not needed for initial production. |

**Current State**: Tenant management lives in BudApp (Keycloak integration). Namespace/queue creation
is part of cluster setup. Jobs specify their namespace in the Job spec. Full automation is a P2
UX improvement.

---

### 3.4 Cross-Tenant Resource Sharing

| Scenario | Status | Notes |
|----------|--------|-------|
| Can Tenant A explicitly share GPU quota with Tenant B? | **HANDLED BY KUEUE** | Cohort borrowing handles this automatically. Tenants in same cohort share unused capacity. |
| Chargeback for borrowed resources | **ROADMAP (P2)** | FinOps/billing feature. Cost tracking can identify borrowed usage via Kueue metrics. |
| Approval workflow for resource sharing | **NOT NEEDED** | Cohort membership is platform admin decision. No per-request approval needed. |

**How Kueue Cohort Borrowing Works:**
```
┌─────────────────────────────────────────────────────────────┐
│  Cohort: "production"                                       │
│  ┌─────────────────────┐  ┌─────────────────────┐          │
│  │ ClusterQueue:       │  │ ClusterQueue:       │          │
│  │ tenant-a-queue      │  │ tenant-b-queue      │          │
│  │ Quota: 10 GPUs      │  │ Quota: 10 GPUs      │          │
│  │ BorrowingLimit: 5   │  │ BorrowingLimit: 5   │          │
│  └─────────────────────┘  └─────────────────────┘          │
│                                                             │
│  If Tenant A uses 2 GPUs, Tenant B can borrow up to 5      │
│  of Tenant A's unused 8 GPUs (limited by BorrowingLimit)   │
└─────────────────────────────────────────────────────────────┘
```

---

### 3.5 Tenant-Specific Cluster Access

| Scenario | Status | Notes |
|----------|--------|-------|
| Some tenants may need dedicated clusters (compliance) | **PARTIAL** | Job schema has `cluster_id` field. Tenants select target cluster on job submission. |
| Tenant → Cluster affinity rules | **ROADMAP (P2)** | Simple validation on job submit. Not needed for initial production. |
| Preventing accidental deployment to wrong cluster | **PARTIAL** | UI shows available clusters. API validates cluster_id exists. Affinity rules are P2. |

**Current State**: Job schema includes `cluster_id: UUID` field. Platform admins control which
clusters are available. Advanced affinity rules (required/preferred/excluded) can be added
later as a P2 feature if compliance requirements demand it.

---

## 4. Observability & Debugging

**Priority: P0 (Must Have for Production)** → **Revised: Mostly ADDRESSED by LGTM Stack**

> **Summary**: LGTM stack (Grafana, Loki, Tempo, Mimir) already in Helm chart provides the
> observability foundation. BudMetrics handles analytics with ClickHouse. BudNotify provides
> alerting via Novu. Most "gaps" are implementation/configuration work, not architecture.

---

### 4.1 Distributed Tracing

| Scenario | Status | Notes |
|----------|--------|-------|
| Trace ID propagation: User → BudUseCases → BudPipeline → BudCluster → Kueue → Pod | **OPS/INFRA** | Add OpenTelemetry SDK to Python services. W3C Trace Context propagation. Implementation work. |
| Integration with Jaeger/Zipkin/OpenTelemetry | **ADDRESSED** | Tempo in LGTM stack IS the tracing backend. Already deployed via Helm chart. |
| Tracing across multi-cluster deployments | **OPS/INFRA** | Baggage propagation with cluster_id. Central Tempo receives from all clusters. Standard OTel pattern. |

**Existing Infrastructure:**
- Tempo deployed via LGTM Helm chart
- OpenTelemetry Collector available
- Just needs SDK instrumentation in services (implementation task)

---

### 4.2 Job-Level Metrics

| Scenario | Status | Notes |
|----------|--------|-------|
| GPU utilization per job (not just per node) | **PARTIAL** | DCGM exports GPU metrics. Need pod labels (`bud.ai/job-id`) for attribution. BudMetrics aggregates to ClickHouse. |
| Memory bandwidth, cache hit rates | **ROADMAP (P2)** | Advanced GPU profiling via DCGM. Nice-to-have for optimization insights. |
| Custom application metrics from jobs | **PARTIAL** | Prometheus push gateway pattern. Standard approach, needs implementation. |
| Metrics retention policy | **OPS/INFRA** | ClickHouse TTL policies. Prometheus retention config. Ops configuration. |

**Existing Infrastructure:**
- BudMetrics with ClickHouse for time-series analytics
- DCGM for GPU metrics (standard practice)
- Prometheus/Mimir in LGTM stack

---

### 4.3 Log Aggregation

| Scenario | Status | Notes |
|----------|--------|-------|
| Centralized logging for all job containers | **ADDRESSED** | Loki in LGTM stack. Promtail for collection. Already deployed. |
| Log retention per compliance requirements | **OPS/INFRA** | Loki retention policies. Configure per tenant requirements. |
| Log access control (can Tenant A see Tenant B's logs?) | **PARTIAL** | Loki multi-tenancy via tenant_id label. BudMetrics can proxy queries with tenant filter enforcement. |
| Real-time log streaming during job execution | **PARTIAL** | Loki tail API supports streaming. SSE endpoint in BudCluster needs implementation. |

**Existing Infrastructure:**
- Loki deployed via LGTM Helm chart
- Promtail for log collection
- Labels: namespace, pod, container (add job_id, tenant_id)

---

### 4.4 Debugging Failed Jobs

| Scenario | Status | Notes |
|----------|--------|-------|
| Preserving failed pod for debugging | **HANDLED BY K8S** | `ttlSecondsAfterFinished` in Job spec. Set longer TTL for debug mode. Already configurable. |
| Exec into running containers for debugging | **ADDRESSED** | Part 11 defines `JobPermission.EXEC`. Authorization model exists. BudCluster proxies kubectl exec. |
| Core dump collection for crashed containers | **ROADMAP (P2)** | Opt-in feature. Not critical for initial production. |
| GPU error logs (Xid errors, ECC errors) | **OPS/INFRA** | DCGM + dmesg parsing. Standard GPU monitoring. Correlate via timestamp to job_id. |

**Existing Infrastructure:**
- JobPermission.EXEC in Part 11 of architecture doc
- K8s native ttlSecondsAfterFinished
- DCGM for GPU error monitoring

---

### 4.5 Capacity Planning Insights

| Scenario | Status | Notes |
|----------|--------|-------|
| Predictive analytics for resource demand | **ROADMAP (P2)** | ML-based forecasting. BudMetrics has the data. Prophet/similar can be added later. |
| Historical queue wait times | **PARTIAL** | Kueue exports metrics (`kueue_pending_workloads`, `kueue_admitted_active_workloads`). Store in ClickHouse via BudMetrics. |
| Peak usage patterns by time/day | **ROADMAP (P2)** | Analytics feature. BudMetrics can aggregate existing data. |
| Recommendations for quota adjustments | **ROADMAP (P2)** | ML-based recommendations. Future enhancement. |

**Existing Infrastructure:**
- Kueue metrics available via Prometheus
- BudMetrics ClickHouse for long-term storage
- Grafana for visualization

---

### 4.6 Alerting & On-Call

| Scenario | Status | Notes |
|----------|--------|-------|
| Job failure alerts (who gets notified?) | **PARTIAL** | BudNotify exists with Novu. Need to integrate job failure events via Dapr pub/sub. |
| SLA breach alerts | **ROADMAP (P2)** | Need to define SLAs first. Prometheus alerting rules can trigger. |
| Quota exhaustion warnings | **PARTIAL** | Prometheus alerts on Kueue metrics. BudNotify can route to users. |
| Integration with PagerDuty/OpsGenie | **OPS/INFRA** | BudNotify/Novu supports multiple channels. Configuration task. |

**Existing Infrastructure:**
- BudNotify service with Novu
- Supports: email, Slack, in-app notifications
- PagerDuty/OpsGenie can be added as Novu integrations

---

## 5. Cost Management & FinOps

**Priority: P1 (Required for Enterprise)** → **Revised: PARTIAL - Core Infrastructure Exists**

> **Summary**: Cost tracking infrastructure exists in Job schema and BudMetrics. Job-level budgets
> implemented. Project/tenant budgets and advanced analytics are P2 business features.

---

### 5.1 Granular Cost Attribution

| Scenario | Status | Notes |
|----------|--------|-------|
| Cost breakdown: compute vs storage vs network | **PARTIAL** | BudMetrics tracks compute (tokens, GPU-seconds). Storage/network are cloud provider billing concerns - get from AWS Cost Explorer/Azure Cost Management. |
| Cost by label (team, project, experiment) | **PARTIAL** | Job schema has `cost_center`. BudMetrics usage APIs support `project_id` filtering. Label-based grouping is query implementation. |
| Shared infrastructure cost allocation | **ROADMAP (P2)** | FinOps feature. Overhead allocation is business logic, not architecture. |
| Idle resource cost tracking | **PARTIAL** | GPU utilization via DCGM. Idle = allocated - utilized. BudMetrics can calculate. |

**Existing Infrastructure:**
```python
# Job schema (Part 2.6 of architecture doc)
class Job:
    estimated_cost: Optional[Decimal]  # Pre-calculated estimate
    actual_cost: Optional[Decimal]     # Tracked during execution
    cost_center: Optional[str]         # For chargeback attribution

# BudMetrics usage API
GET /usage/summary?project_id=X&start_date=Y&end_date=Z
# Returns: total_tokens, total_cost, request_count
```

---

### 5.2 Budget Management

| Scenario | Status | Notes |
|----------|--------|-------|
| Project-level budgets | **PARTIAL** | Job-level `budget_cap` exists. Project aggregation is implementation work on BudMetrics data. |
| Monthly/quarterly budget cycles | **ROADMAP (P2)** | Business feature. BudMetrics has time-range queries for data. |
| Budget rollover policies | **ROADMAP (P2)** | Business policy configuration, not architecture. |
| Approval workflow when exceeded | **PARTIAL** | Job has `budget_action: "warn" | "pause" | "cancel"`. Project-level approval is P2. |

**Existing Infrastructure:**
```python
# Job Intent (Part 2.6 of architecture doc)
class JobIntent:
    budget_cap: Optional[Decimal]  # Max cost in USD
    budget_action: str = "warn"    # "warn" | "pause" | "cancel" when exceeded
```

---

### 5.3 Cost Anomaly Detection

| Scenario | Status | Notes |
|----------|--------|-------|
| Unusual spending patterns | **ROADMAP (P2)** | Analytics feature. BudMetrics ClickHouse has historical data for baseline comparison. |
| Runaway job detection | **PARTIAL** | Job has `expected_duration`. Alert if actual > 3x expected. Implementation work. |
| Historical baselines | **ROADMAP (P2)** | Analytics/ML feature. Data exists in ClickHouse rollup tables. |

**Existing Infrastructure:**
- Section 9.4.4: CostEstimationFeedback class learns from actual vs estimated costs
- BudMetrics: InferenceMetrics rollup tables (5m, 1h, 1d) for historical analysis

---

### 5.4-5.6 Reserved Capacity, Chargeback, Cost Optimization

| Scenario | Status | Notes |
|----------|--------|-------|
| Reserved instances mapping | **OPS/INFRA** | Cloud provider concern. Tag ResourceFlavor with `ri-backed: true`. Track utilization in cloud console. |
| Invoice generation | **PARTIAL** | BudMetrics has usage data. PDF/CSV generation is reporting feature, not architecture. |
| Right-sizing suggestions | **PARTIAL** | Section 9.4.4 CostEstimationFeedback tracks over/under-estimation. UI exposure needed. |

**Existing Infrastructure:**
- Section 4.7: Cost-Based Scheduling (spot instances, off-peak scheduling)
- Section 9.4.4: CostEstimationFeedback (learns from actual costs)
- BudMetrics: Usage APIs with project/time filtering

---

## 6. Operations & Maintenance

**Priority: P0 (Must Have for Production)** → **Revised: Mostly OPS/INFRA**

> **Summary**: Section 9.4.1 already handles job draining and migration during cluster removal.
> Most operations tasks are standard K8s/ops procedures, not architecture gaps.

---

### 6.1 Cluster Maintenance Windows

| Scenario | Status | Notes |
|----------|--------|-------|
| Draining jobs before node maintenance | **ADDRESSED** | Section 9.4.1 `handle_cluster_removal()` with graceful drain, checkpoint signals for TRAINING, migration for SERVICE. |
| Coordinating maintenance across multi-cluster | **OPS/INFRA** | Operational process - stagger maintenance windows across clusters. Calendar/scheduling task. |
| Communicating maintenance to affected tenants | **PARTIAL** | BudNotify exists. Need to integrate maintenance events and tenant notification. Implementation work. |
| Automatic job migration during maintenance | **ADDRESSED** | Section 9.4.1 handles: SERVICE → migrate, TRAINING → checkpoint + migrate, BATCH → wait or retry. |

**Existing Infrastructure (Section 9.4.1):**
```python
async def handle_cluster_removal(cluster_id: UUID, force: bool = False):
    # 1. Stop new admissions (mark cluster as draining)
    await mark_cluster_draining(cluster_id)

    # 2. For each running job, attempt migration or wait
    for job in jobs:
        if job.job_type == JobType.SERVICE:
            await attempt_service_migration(job)
        elif job.job_type == JobType.TRAINING:
            await signal_checkpoint(job)
            await wait_for_checkpoint(job, timeout=300)
            await migrate_training_job(job)
        else:  # BATCH
            await wait_for_completion(job, timeout=job.policy.max_runtime)
```

---

### 6.2-6.6 K8s Upgrades, GPU Drivers, Scaling, Config, Incidents

| Scenario | Status | Notes |
|----------|--------|-------|
| K8s upgrade impact on running jobs | **OPS/INFRA** | Standard K8s rolling upgrade with PodDisruptionBudgets. Node drain respects running pods. |
| GPU driver updates | **OPS/INFRA** | GPU Operator manages NVIDIA drivers. Rolling update by node pool. Standard ops procedure. |
| When to add new nodes (autoscaling) | **PARTIAL** | BudCluster has `update_autoscale.yaml` playbook. Karpenter/Cluster Autoscaler available in K8s. Trigger config needed. |
| Kueue config versioning (GitOps) | **OPS/INFRA** | ArgoCD/Flux for GitOps. Standard K8s config management practice. Not architecture. |
| Runbooks for common failures | **OPS/INFRA** | Documentation task. Write runbooks as issues arise. Not architecture. |

**Existing Infrastructure:**
- **BudCluster Playbooks**: `update_autoscale.yaml` for scaling config
- **GPU Operator**: Deployed via Ansible, manages NVIDIA drivers automatically
- **HAMI**: Auto-installed during cluster onboarding for GPU time-slicing
- **Karpenter/Cluster Autoscaler**: Standard K8s autoscaling solutions

---

## 7. Performance & Scale

**Priority: P1 (Required for Enterprise)** → **Revised: Mostly OPS/INFRA + Existing Coverage**

> **Summary**: MultiKueue architecture already documented (Part 8.1-8.3). Performance tuning
> is standard ops work. Rate limiting is gateway configuration.

---

### 7.1-7.6 Rate Limits, Large Pipelines, Kueue Scale, DB Performance, Multi-Cluster, Cold Start

| Scenario | Status | Notes |
|----------|--------|-------|
| Max jobs per second per tenant | **PARTIAL** | Rate limiting at BudGateway (Rust, high-performance). Standard pattern, needs configuration. |
| Pipelines with 1000+ steps | **ROADMAP (P2)** | Implementation optimization (lazy loading, pagination). Not blocking for MVP. |
| Max workloads per ClusterQueue | **OPS/INFRA** | Kueue documented capacity: ~10K workloads/queue. Monitor via Prometheus, shard if needed. |
| Job table partitioning strategy | **OPS/INFRA** | Standard DBA best practice. PostgreSQL native partitioning by `created_at`. |
| Max clusters in MultiKueue | **ADDRESSED** | Part 8.1-8.3 covers MultiKueue architecture with remote cluster federation. Tested to 50+ clusters. |
| Cold start optimization | **HANDLED BY K8S** | For `SERVICE` + `scale_to_zero`, KEDA/Knative handles cold start. Image pre-pulling via DaemonSet. |

**Existing Infrastructure:**
- **Part 8.1-8.3**: MultiKueue architecture with `MultiKueueConfig`, `AdmissionCheck`, remote clusters
- **JobPolicy**: `scale_to_zero`, `min_replicas`, `max_replicas` for serverless scaling
- **BudGateway**: Rust-based high-performance gateway (forked from TensorZero)
- **Kueue Metrics**: `kueue_pending_workloads`, `kueue_admitted_active_workloads` for capacity monitoring

---

## 8. Data Management

**Priority: P1 (Required for Enterprise)** → **Revised: Mostly ADDRESSED or User Responsibility**

> **Summary**: CheckpointConfig covers checkpoint storage. BudModel + MinIO handles model artifacts.
> Dataset access is user responsibility (standard K8s volume patterns).

---

### 8.1-8.5 Training Data, Model Artifacts, Checkpoints, Data Residency, Large Files

| Scenario | Status | Notes |
|----------|--------|-------|
| How do TRAINING jobs access datasets? | **NOT NEEDED** | User responsibility. Jobs specify volume mounts in container spec (NFS, S3 FUSE, PVC). Standard K8s patterns. |
| Where are trained models stored? | **ADDRESSED** | BudModel service uses MinIO (S3-compatible). Config: `minio_bucket: "models-registry"`. Metadata in PostgreSQL. |
| Checkpoint storage backend configuration | **ADDRESSED** | `CheckpointConfig` schema in Part 2.5: `storage_class`, `storage_size`, `checkpoint_path`, `checkpoint_interval`, `max_checkpoints`. |
| Ensuring data stays in specific regions | **PARTIAL** | `cluster_id` field controls job placement by region. Storage bucket per region is cloud provider config (OPS/INFRA). |
| Datasets larger than node storage | **NOT NEEDED** | Standard ML patterns (PyTorch DataLoader streaming, data sharding). User responsibility, not platform architecture. |

**Existing Infrastructure:**
```python
# CheckpointConfig (Part 2.5 of architecture doc)
class CheckpointConfig(SQLModel):
    enabled: bool = True
    storage_class: str = "standard"       # PVC storage class
    storage_size: str = "100Gi"           # PVC size
    checkpoint_interval: int = 3600       # Seconds between checkpoints
    max_checkpoints: int = 3              # Retention count
    checkpoint_path: str = "/checkpoints" # Mount path in container

# BudModel MinIO configuration
minio_endpoint: str = "bud-store.bud.studio"
minio_bucket: str = "models-registry"      # Trained model artifacts
minio_model_bucket: str = "model-info"     # Model metadata
```

---

## 9. Compliance & Governance

**Priority: P1 (Required for Enterprise)**

### 9.1-9.6 Audit Logging, Certifications, Data Classification, Model Governance, Reproducibility, Export Controls

| Scenario | Status | Notes |
|----------|--------|-------|
| Who created/modified/deleted each job? | **ADDRESSED** | Part 11.9 JobAuditEvents + BudApp log_audit() infrastructure |
| SOC 2, HIPAA, PCI-DSS, FedRAMP requirements | **ROADMAP (P2)** | Compliance certifications are customer responsibility; platform provides building blocks |
| Jobs processing PII vs non-PII data | **PARTIAL** | Job labels + cluster_id for regional placement; full classification taxonomy is P2 |
| Model approval workflows before production | **ROADMAP (P2)** | BudApp/BudModel concern; promotion flows planned for P2 |
| Can a job be exactly reproduced later? | **PARTIAL** | Image digest + config captured; full reproducibility manifest API is P2 |
| ITAR, export controls | **ROADMAP (P2)** | Requires dedicated geo-restriction + model flagging features |

**Existing Infrastructure:**
- **JobAuditEvents** (Part 11.9): `JOB_VIEW`, `JOB_CREATE`, `JOB_CANCEL`, `JOB_DELETE`, `JOB_LOGS`, `JOB_EXEC`
- **BudApp Audit**: `log_audit()` function with `AuditActionEnum`, `AuditResourceTypeEnum`
- **Job Labels**: Can include `data-classification` labels for routing to appropriate clusters
- **Cluster Selection**: `cluster_id` in JobIntent for data residency requirements

**Required Architecture Addition:**

```yaml
# Proposed Compliance Model
audit_logging:
  scope:
    - all API calls (who, what, when, from where)
    - all job lifecycle events
    - all data access (secrets, artifacts)
    - all admin actions

  storage:
    - immutable log store (S3 with object lock)
    - retention: 7 years for regulated industries

  format: JSON Lines, compatible with SIEM

compliance_features:
  soc2:
    - access controls (RBAC)
    - audit logging
    - encryption at rest and in transit
    - change management (GitOps)

  hipaa:
    - BAA required with cloud providers
    - PHI data classification
    - access logging
    - encryption (AES-256)

  pci_dss:
    - network segmentation
    - key management
    - vulnerability scanning

data_classification:
  levels:
    - public
    - internal
    - confidential
    - restricted (PII, PHI)

  enforcement:
    - job labels indicate data classification
    - restricted data → dedicated clusters only
    - audit all access to restricted data

model_governance:
  approval_workflow:
    - development → staging → production
    - required approvers per stage
    - automated checks (bias, performance)

reproducibility:
  captured_state:
    - container image digest
    - model weights hash
    - config/hyperparameters
    - random seed
    - GPU type (for numerical reproducibility)

  api: GET /api/jobs/{id}/reproducibility-manifest

export_controls:
  geo_restrictions:
    - block job submission from sanctioned countries
    - block model deployment to restricted regions

  model_restrictions:
    - flag dual-use models
    - require export license for certain model types
```

---

## 10. ML-Specific Scenarios

**Priority: P1 (Required for Enterprise)**

### 10.1-10.8 HPO, Distributed Training, Preemption Intelligence, Autoscaling, Warm-up, Batch Inference, GPU Memory, Multi-Model

| Scenario | Status | Notes |
|----------|--------|-------|
| Integration with HPO frameworks (Optuna, Ray Tune) | **GAP** | HPO controller as SERVICE spawning TRAINING jobs; explicit framework integration not built |
| Multi-node training coordination (PyTorch DDP) | **PARTIAL** | TopologyConstraint (SAME_NODE, NVLINK) + Kueue gang-scheduling; rank/world_size is user container config |
| Don't preempt if training is 95% complete | **PARTIAL** | `preemption_grace_period` + CRITICAL never preempted; progress-aware decisions are P2 |
| HPA integration for SERVICE jobs | **ADDRESSED** | `scale_to_zero`, `min_replicas`, `max_replicas` in JobPolicy; K8s HPA/KEDA handles scaling |
| Pre-loading models before traffic arrives | **OPS/INFRA** | K8s readiness probes; inference engine (vLLM, TensorRT-LLM) responsibility |
| Dynamic batching configuration | **NOT NEEDED** | Inference engine responsibility (vLLM continuous batching); platform routes requests |
| OOM handling and recovery | **HANDLED BY K8S/KUEUE** | K8s OOMKilled + Job retry policy + MIG prevents fragmentation |
| Multiple models per GPU (multiplexing) | **ADDRESSED** | HAMI (time-slicing) auto-installed during cluster onboarding; MIG ResourceFlavors documented |

**Existing Infrastructure:**
- **TopologyConstraint** (Part 2.4): `SAME_NODE`, `NVLINK`, `SPREAD` for multi-GPU jobs
- **Section 9.4.7**: Multi-GPU topology failure handling with relaxation offers
- **JobPolicy autoscaling**: `scale_to_zero`, `min_replicas`, `max_replicas`
- **HAMI**: GPU time-slicing auto-installed during cluster onboarding
- **MIG ResourceFlavors**: Part 7.3 documents `nvidia.com/mig.config` labels

**Required Architecture Addition:**

```yaml
# Proposed ML-Specific Features
hpo_integration:
  supported_frameworks:
    - optuna
    - ray_tune
    - wandb_sweeps

  integration_pattern:
    - HPO controller runs as SERVICE job
    - Spawns TRAINING jobs for each trial
    - BudPipeline manages trial lifecycle
    - Early stopping via Kueue job cancellation

distributed_training:
  frameworks:
    - pytorch_ddp
    - horovod
    - deepspeed

  implementation:
    - job_type: TRAINING
    - parallelism: N workers
    - topology: SAME_NODE or NVLINK
    - gang_scheduling: all-or-nothing via Kueue

preemption_intelligence:
  rules:
    - if training_progress > 90%: preemption_cost = HIGH
    - if time_since_checkpoint < 5min: preemption_cost = LOW
    - if priority_class == CRITICAL: never_preempt

  configuration:
    api: PATCH /api/clusters/{id}/preemption-policy

inference_autoscaling:
  metrics:
    - queue_depth (primary)
    - latency_p99
    - gpu_utilization (secondary)

  hpa_config:
    - scale_up_threshold: queue_depth > 10
    - scale_down_threshold: queue_depth < 2 for 5min
    - min_replicas: 0 (if scale_to_zero enabled)
    - max_replicas: configurable

model_warmup:
  strategies:
    - pre_load: load model on container start
    - warm_requests: send synthetic requests before ready
    - eager_loading: load all model layers immediately

  health_check:
    - readiness: model loaded and responding
    - liveness: container running

batch_inference:
  configuration:
    - max_batch_size
    - max_wait_time_ms
    - dynamic_batching: enabled

gpu_memory:
  oom_handling:
    - detect: monitor GPU memory usage
    - prevent: enforce limits via MIG or time-slicing
    - recover: restart container, optionally with more memory

  fragmentation:
    - detection: monitor allocation patterns
    - mitigation: periodic container restart during low-traffic

multi_model:
  approaches:
    - mig_partitioning: hardware isolation
    - time_slicing: shared context via HAMI
    - model_multiplexing: single container, model switching

  scheduling:
    - track active models per GPU
    - route requests to GPU with model loaded
    - model eviction policy: LRU
```

---

## 11. Integration & Interoperability

**Priority: P2 (Important for Maturity)**

### 11.1-11.6 CI/CD, MLOps, Data Platform, Identity, Notifications, External Schedulers

| Scenario | Status | Notes |
|----------|--------|-------|
| Triggering pipelines from GitHub Actions | **PARTIAL** | `POST /budpipeline/{id}/execute` API exists; standard HTTP call from Actions |
| MLflow integration | **ROADMAP (P2)** | Experiment tracking configured in user code; auto-logging is P2 feature |
| Triggering jobs from Airflow/Dagster | **PARTIAL** | Same API exists; custom Operator/Sensor wraps Bud API |
| SSO (SAML, OIDC) | **ADDRESSED** | Keycloak provides SAML, OIDC, LDAP federation |
| Custom webhook payloads | **PARTIAL** | `POST /api/clusters/{cluster_id}/webhooks` for job events |
| External scheduler integration (Control-M) | **PARTIAL** | POST /api/jobs + idempotency_key + webhook callback pattern |

**Existing Infrastructure:**
- **BudPipeline API**: `POST /budpipeline/{id}/execute` with `callback_topics` for real-time updates
- **Webhook API**: `POST /api/clusters/{cluster_id}/webhooks` with event filtering
- **Idempotency**: `idempotency_key` field prevents duplicate job creation during retries
- **Keycloak**: Supports SAML 2.0, OIDC, LDAP federation, social login

**Required Architecture Addition:**

```yaml
# Proposed Integration Model
ci_cd:
  github_actions:
    - action: bud-ai-foundry/deploy-action
    - inputs: pipeline_id, parameters, wait_for_completion

  gitlab_ci:
    - template: .bud-ai-foundry.yml

  api:
    - POST /api/pipelines/{id}/trigger (with API key auth)

mlops:
  mlflow:
    - tracking_uri: configured per project
    - artifact_store: shared S3 bucket
    - auto_logging: training metrics

  wandb:
    - api_key: stored in secrets
    - project: auto-created per Bud project

data_platform:
  airflow:
    - operator: BudPipelineTriggerOperator
    - sensor: BudJobCompleteSensor

  dagster:
    - asset: bud_job_asset
    - io_manager: bud_artifact_io_manager

external_schedulers:
  pattern:
    - external system calls Bud API
    - Bud returns job_id
    - external system polls for completion (or uses webhook)

  api:
    - POST /api/jobs with idempotency_key
    - GET /api/jobs/{id}/status
    - webhook callback on completion
```

---

## 12. User Experience & Self-Service

**Priority: P2 (Important for Maturity)**

### 12.1-12.6 Templates, Cost Preview, Debug, Quota Requests, Comparison, Favorites

| Scenario | Status | Notes |
|----------|--------|-------|
| Pre-defined job templates | **ADDRESSED** | BudUseCases templates + system_owned pipelines |
| Cost estimation before submission | **PARTIAL** | `estimated_cost` in Job; BudSim integration for accurate estimates |
| Jupyter notebook jobs with GPU | **PARTIAL** | SERVICE + `workload_class: interactive`; port forwarding via Ingress |
| Self-service quota requests | **ROADMAP (P2)** | UX workflow for quota request/approval |
| Compare two training runs | **ROADMAP (P2)** | BudMetrics comparison API |
| Quick access to favorites | **ROADMAP (P2)** | BudAdmin UX feature |

**Existing Infrastructure:**
- **BudUseCases**: Template system with `system_owned` flag for shared templates
- **Cost Estimation**: `estimated_cost`, `actual_cost` fields with CostEstimationFeedback (Section 9.4.4)
- **Interactive Jobs**: `intent.workload_class: interactive` for Jupyter/VS Code; K8s Service + Ingress for access

**Required Architecture Addition:**

```yaml
# Proposed UX Features
cost_preview:
  api: POST /api/jobs/estimate
  inputs:
    - job_type
    - resources
    - expected_duration
  outputs:
    - estimated_cost
    - cost_breakdown
    - alternative_configurations (cheaper options)

interactive_jobs:
  types:
    - jupyter: JupyterLab with GPU
    - vscode: VS Code Server
    - ssh: direct SSH access

  implementation:
    - job_type: SERVICE
    - special_deployment_type: INTERACTIVE
    - port_forwarding: via BudGateway
    - session_persistence: optional PVC

job_comparison:
  api: GET /api/jobs/compare?ids=a,b
  response:
    - config_diff
    - performance_comparison
    - cost_comparison
    - timeline_overlay

favorites:
  api: POST /api/users/{id}/favorites
  entities:
    - jobs
    - pipelines
    - templates

  features:
    - clone_job: create new job from favorite
    - quick_rerun: rerun with same config
```

---

## 13. Edge Cases & Failure Modes

**Priority: P0 (Must Have for Production)**

### 13.1-13.7 Zombies, Infinite Retry, Resource Leaks, Clock Skew, Partial Failures, Quota Races, API Skew

| Scenario | Status | Notes |
|----------|--------|-------|
| Jobs stuck in RUNNING but container is dead | **ADDRESSED** | Section 9.2.1 JobReconciler syncs DB state with K8s on startup |
| Jobs that fail immediately and keep retrying | **ADDRESSED** | `max_retries` + `retry_delay_seconds` with exponential backoff |
| Orphaned PVCs from TRAINING jobs | **PARTIAL** | Section 9.4.3 cleanup_orphaned_workloads(); PVC retention policy is P2 |
| Impact on scheduled jobs across clusters | **OPS/INFRA** | NTP mandatory; `scheduled_start` uses server time; Dapr handles cluster coordination |
| 3 of 5 parallel steps succeeded, 2 failed | **PARTIAL** | BudPipeline handles step failures; `on_failure` strategy configuration is P2 |
| Two jobs submitted simultaneously, only quota for one | **HANDLED BY KUEUE** | Kueue admission is atomic; first admitted wins, others queue |
| BudCluster at v2, Kueue at v1beta1 | **OPS/INFRA** | Version compatibility documented in cluster onboarding |

**Existing Infrastructure:**
- **JobReconciler** (Section 9.2.1): Syncs Job DB state with K8s on BudCluster startup
- **Retry Policy**: `max_retries`, `retry_delay_seconds`, `retry_on_preemption` in JobPolicy
- **Orphan Cleanup**: `cleanup_orphaned_workloads()` removes K8s resources without Job records
- **Kueue Atomicity**: Quota admission handled atomically at Kueue level

**Required Architecture Addition:**

```yaml
# Proposed Failure Mode Handling
zombie_detection:
  mechanism:
    - periodic health check (every 30s)
    - compare K8s pod status with Job status
    - if pod terminated but Job is RUNNING → zombie

  remediation:
    - update Job status to match K8s
    - trigger retry if applicable
    - alert if repeated zombies

circuit_breaker:
  configuration:
    - max_failures_per_hour: 5
    - backoff: exponential (30s, 1m, 5m, 15m, 1h)
    - circuit_open_duration: 1 hour

  behavior:
    - after max_failures: stop retrying, mark FAILED
    - require manual intervention to retry

resource_cleanup:
  pvcs:
    - retention: 7 days after job completion
    - cleanup_job: daily scan for orphaned PVCs

  load_balancers:
    - cleanup on SERVICE job deletion
    - orphan detection: weekly scan

clock_skew:
  tolerance: 30 seconds
  mitigation:
    - NTP mandatory on all nodes
    - scheduled_start uses server time, not client
    - deadline enforcement has grace period

partial_failure:
  strategies:
    - fail_fast: cancel remaining steps on first failure
    - continue_on_error: complete successful steps, report partial
    - rollback: undo successful steps (if compensating actions defined)

  configuration:
    - per pipeline: on_failure: fail_fast | continue | rollback

quota_races:
  mechanism:
    - pessimistic locking at admission
    - Kueue handles this natively
    - BudCluster does NOT pre-reserve quota

  behavior:
    - first admitted wins
    - others wait in queue

version_compatibility:
  matrix:
    - BudCluster v2.x: Kueue v0.5+, K8s 1.27+
    - BudCluster v1.x: Kueue v0.4+, K8s 1.25+

  handling:
    - check versions on cluster registration
    - warn if approaching deprecation
    - block if incompatible
```

---

## 14. SLA & Quality of Service

**Priority: P1 (Required for Enterprise)**

### 14.1-14.4 SLA Definitions, Monitoring, QoS, Capacity Guarantees

| Scenario | Status | Notes |
|----------|--------|-------|
| What SLAs are offered per priority class? | **PARTIAL** | PriorityClass defines implicit SLAs (CRITICAL=never preempted, etc.); formal SLA docs is P2 |
| Real-time SLA compliance dashboard | **PARTIAL** | LGTM stack + BudMetrics can track; Grafana dashboard template is P2 |
| Guaranteed vs burstable vs best-effort | **PARTIAL** | PriorityClass + Kueue quotas map to QoS tiers; explicit naming is P2 |
| Capacity booking for large training jobs | **GAP** | Advance reservation requires Kueue extension or custom admission |

**Existing Infrastructure:**
- **PriorityClass** (Part 2.4): CRITICAL (1000), HIGH (100), NORMAL (10), LOW (1)
- **Preemption Rules**: CRITICAL=never preempted, LOW=always preemptible
- **LGTM Stack**: Grafana dashboards can track queue wait times, uptime
- **Kueue Quotas**: LocalQueue/ClusterQueue/Cohort hierarchy for resource guarantees

**Required Architecture Addition:**

```yaml
# Proposed SLA Model
sla_definitions:
  priority_critical:
    queue_wait_sla: 5 minutes (p99)
    uptime_sla: 99.99% (SERVICE)
    preemption: never

  priority_high:
    queue_wait_sla: 30 minutes (p99)
    uptime_sla: 99.9% (SERVICE)
    preemption: only by CRITICAL

  priority_normal:
    queue_wait_sla: 2 hours (p99)
    uptime_sla: 99.5% (SERVICE)
    preemption: by HIGH and CRITICAL

  priority_low:
    queue_wait_sla: best effort
    uptime_sla: best effort
    preemption: by any higher priority

sla_monitoring:
  metrics:
    - queue_wait_time_p99
    - uptime_percentage
    - job_success_rate

  dashboard: Grafana dashboard template
  alerts: on SLA breach risk (80% of threshold)

qos_tiers:
  guaranteed:
    resources: reserved, not shared
    priority_class: CRITICAL
    cost: premium (2x)

  burstable:
    resources: base + burst when available
    priority_class: HIGH or NORMAL
    cost: standard + burst pricing

  best_effort:
    resources: only when available
    priority_class: LOW
    cost: discounted (0.5x)

capacity_booking:
  api: POST /api/capacity/reservations
  inputs:
    - start_time
    - end_time
    - resources (GPU type, count)
    - cluster_id (optional)

  behavior:
    - reserves capacity in Kueue
    - guaranteed admission at start_time
    - charged even if not used (configurable)
```

---

## 15. Migration & Upgrades

**Priority: P2 (Important for Maturity)**

### 15.1-15.4 Schema Migration, Kueue Upgrades, Platform Migration, API Versioning

| Scenario | Status | Notes |
|----------|--------|-------|
| Adding new fields to Job table | **ADDRESSED** | Alembic migrations already in use across all services |
| Kueue CRD migration procedures | **OPS/INFRA** | Standard K8s operator upgrade; documented in runbook |
| Import jobs from Kubeflow | **ROADMAP (P2)** | Migration tool for KFP → BudPipeline |
| Supporting multiple API versions | **OPS/INFRA** | FastAPI router versioning (/api/v1, /api/v2) |

**Existing Infrastructure:**
- **Alembic**: All Python services use Alembic for PostgreSQL migrations
- **K8s Operators**: Kueue, GPU Operator, HAMI follow standard Helm/operator upgrade patterns
- **API Versioning**: FastAPI routers support path-based versioning

**Required Architecture Addition:**

```yaml
# Proposed Migration Model
schema_migration:
  tool: Alembic (already in use)
  strategy:
    - backwards compatible changes: deploy first, migrate later
    - breaking changes: blue-green deployment

  testing:
    - migration scripts tested in staging
    - rollback scripts mandatory

kueue_migration:
  procedure:
    1: backup all CRDs (kubectl get workloads -o yaml)
    2: test new version in staging
    3: drain queues (optional, for zero-risk)
    4: upgrade Kueue controller
    5: apply CRD updates
    6: verify workload reconciliation

platform_migration:
  kubeflow_import:
    - map KFP pipelines to BudPipeline
    - map experiments to projects
    - migrate artifacts to BudModel registry

  tool: bud-migrate CLI

api_versioning:
  strategy: URL path versioning (/api/v1, /api/v2)
  deprecation:
    - announce 6 months before removal
    - sunset header in responses
    - migration guide published

  compatibility:
    - v1 and v2 can run simultaneously
    - v1 deprecated when v3 releases
```

---

## 16. Advanced Scheduling Scenarios

**Priority: P1 (Required for Enterprise)**

### 16.1-16.6 Gang Scheduling, Affinity, Fragmentation, Preemption, Priority Inversion, Deadline-Aware

| Scenario | Status | Notes |
|----------|--------|-------|
| All-or-nothing scheduling for distributed training | **ADDRESSED** | Kueue gang scheduling with podGroup; documented in Part 7 |
| Co-locate related jobs (cache sharing) | **PARTIAL** | K8s nodeSelector + podAffinity; job-to-job affinity is P2 |
| Defragmentation strategies | **OPS/INFRA** | Cluster maintenance via node drain/cordon; automated defrag is P2 |
| Preemption cost calculation | **PARTIAL** | `preemption_grace_period`, `retry_on_preemption`; multi-factor cost is P2 |
| Low-priority job blocking high-priority dependency | **ROADMAP (P2)** | Priority inheritance requires custom admission logic |
| Scheduling based on deadline feasibility | **PARTIAL** | `policy.deadline` exists; feasibility check + dynamic priority boost is P2 |

**Existing Infrastructure:**
- **Kueue Gang Scheduling**: All-or-nothing admission for multi-pod jobs (distributed training)
- **TopologyConstraint**: SAME_NODE, NVLINK, SPREAD for placement control
- **K8s Affinity**: nodeSelector, nodeAffinity, podAffinity for co-location
- **Preemption**: `preemption_grace_period` (30s default), `retry_on_preemption`, PriorityClass

**Required Architecture Addition:**

```yaml
# Proposed Advanced Scheduling Features
gang_scheduling:
  implementation: Kueue with podGroup
  configuration:
    min_replicas: all pods must be admitted together
    timeout: max wait before failure

  use_cases:
    - distributed training (PyTorch DDP)
    - multi-GPU inference

affinity_rules:
  job_affinity:
    - co_locate: schedule on same node as job X
    - separate: schedule on different node from job X

  data_affinity:
    - prefer nodes with cached data
    - Kueue ResourceFlavor with data labels

defragmentation:
  triggers:
    - scheduled (nightly during low traffic)
    - on demand (before large job submission)

  strategy:
    - identify low-priority jobs on fragmented nodes
    - evict and reschedule to consolidate
    - preserve CRITICAL and running jobs

preemption_policies:
  cost_factors:
    - time_since_start
    - checkpoint_recency
    - priority_difference
    - estimated_remaining_time

  min_runtime_before_preemption: 5 minutes (configurable)
  max_preemptions_per_hour: 10 (per cluster)

priority_inversion:
  detection:
    - high-priority job waiting on low-priority dependency

  resolution:
    - priority inheritance: boost low-priority job temporarily
    - alert: notify platform team

deadline_aware:
  feasibility_check:
    - on job submission, estimate if deadline is achievable
    - warn if unlikely (queue too long)
    - optionally reject impossible deadlines

  dynamic_priority:
    - as deadline approaches, increase effective priority
    - Kueue integration: priority boost at 50%, 75%, 90% of time budget
```

---

## 17. Network & Storage Specifics

**Priority: P2 (Important for Maturity)**

### 17.1-17.4 GPU-Direct Storage, InfiniBand, Ephemeral Storage, Shared Filesystem

| Scenario | Status | Notes |
|----------|--------|-------|
| NVMe-oF for training data | **OPS/INFRA** | Hardware/driver setup; nodeSelector for GPU-direct storage nodes |
| InfiniBand/RoCE for distributed training | **PARTIAL** | TopologyConstraint + nodeSelector; specific IB config is cluster onboarding |
| Local SSD allocation for jobs | **HANDLED BY K8S** | `ephemeral-storage` resource + nodeSelector for SSD nodes |
| NFS/Lustre for shared datasets | **OPS/INFRA** | StorageClass configuration during cluster onboarding |

**Existing Infrastructure:**
- **TopologyConstraint**: NVLINK constraint implies high-speed interconnect
- **ResourceFlavor**: Kueue ResourceFlavors with node labels for specialized hardware
- **K8s Resources**: `ephemeral-storage` limits, emptyDir volumes, nodeSelector
- **StorageClass**: Configured per cluster for shared filesystem access

**Required Architecture Addition:**

```yaml
# Proposed Storage & Network Model
gpu_direct_storage:
  support: optional feature for supported hardware
  configuration:
    - node_label: nvidia.com/gpu-direct-storage=true
    - storage_class: nvmeof-direct
    - use_case: training with large datasets

high_performance_networking:
  infiniband:
    - node_label: network.nvidia.com/rdma=true
    - network_type: secondary network (Multus)
    - use_case: distributed training

  configuration:
    - Kueue ResourceFlavor: hpc-rdma
    - topology_constraint: same IB fabric

ephemeral_storage:
  allocation:
    - resource: ephemeral-storage
    - limits: per job configuration
    - default: 100Gi
    - max: 1Ti

  local_ssd:
    - node_selector: storage.type=nvme-ssd
    - StorageClass: local-ssd
    - emptyDir with sizeLimit

shared_filesystem:
  options:
    - nfs: simple, moderate performance
    - efs: AWS native, managed
    - lustre: high performance, complex
    - azure_files: Azure native

  configuration:
    - per_tenant: dedicated share or subdirectory
    - quotas: enforced via StorageClass or external
    - access_modes: ReadWriteMany for shared, ReadWriteOnce for exclusive
```

---

## 18. Missing Scenarios (Not in Original List)

These scenarios were identified during the analysis but were not in the original list:

### 18.1 Tenant Self-Registration

| Scenario | Status | Notes |
|----------|--------|-------|
| Self-service tenant signup | **GAP** | Onboarding flow |
| Trial quotas and limits | **GAP** | Trial management |
| Upgrade from trial to paid | **GAP** | Upgrade flow |

### 18.2 Model Deployment Rollback

| Scenario | Status | Notes |
|----------|--------|-------|
| Rollback SERVICE job to previous version | **GAP** | Version rollback |
| Canary deployments for models | **GAP** | Progressive rollout |
| A/B testing between model versions | **GAP** | Traffic splitting |

### 18.3 Cost Alerts Integration

| Scenario | Status | Notes |
|----------|--------|-------|
| Real-time cost alerts to Slack/Teams | **PARTIAL** | Mentioned but not detailed |
| Daily cost digest emails | **GAP** | Cost reporting |
| Weekly spend forecasts | **GAP** | Cost prediction |

### 18.4 Compliance Reporting

| Scenario | Status | Notes |
|----------|--------|-------|
| Automated compliance reports | **GAP** | Report generation |
| Evidence collection for audits | **GAP** | Audit support |
| Attestation signing | **GAP** | Compliance attestation |

### 18.5 Federated Learning Support

| Scenario | Status | Notes |
|----------|--------|-------|
| Cross-cluster federated training | **GAP** | FL architecture |
| Data privacy in distributed training | **GAP** | Privacy preservation |
| Model aggregation orchestration | **GAP** | FL coordination |

---

## Summary: Priority Matrix

### P0 - Must Have for Production (22 gaps)

| Category | Key Gaps | Status |
|----------|----------|--------|
| Security | ~~RBAC~~, Secrets, ~~Network~~, ~~Privileged ops~~, ~~Image scanning~~ | RBAC addressed, Network simplified, Privileged → K8s PSS, Image scanning → P2 |
| DR/HA | ~~Service failure~~, ~~DB sync~~, ~~Kueue recovery~~, ~~Multi-region~~ | JobReconciler added, Kueue self-healing, Multi-region → P2 |
| Observability | Distributed tracing, Log aggregation, Alerting | GAP |
| Operations | Maintenance windows, Incident runbooks | GAP |
| Edge Cases | Zombie detection, Circuit breaker, Cleanup | GAP |

### P1 - Required for Enterprise (51 gaps)

| Category | Key Gaps |
|----------|----------|
| Multi-Tenancy | Quota management, Onboarding, Resource sharing |
| Cost/FinOps | Budget management, Anomaly detection, Chargeback |
| Compliance | Audit logging, Data classification, Model governance |
| ML Features | HPO, Distributed training, Autoscaling |
| SLA | SLA definitions, Monitoring, Capacity booking |
| Advanced Scheduling | Gang scheduling, Fragmentation, Deadline-aware |

### P2 - Important for Maturity (32 gaps)

| Category | Key Gaps |
|----------|----------|
| Integration | CI/CD, MLOps platforms, External schedulers |
| UX | Cost preview, Interactive jobs, Comparison |
| Migration | Schema migration, Platform migration, API versioning |
| Network/Storage | GPU-Direct, InfiniBand, Shared filesystems |

---

## Next Steps

1. **Prioritize P0 gaps** for immediate architecture work
2. **Create detailed design docs** for each P0 category
3. **Update architecture docs** with accepted designs
4. **Create implementation tickets** for engineering teams
5. **Review P1 gaps** for next planning cycle

---

*Document generated: 2026-02-05*
*Review scheduled: Weekly architecture review*
