# Job, Scheduling & Orchestration Architecture

> **Document Version:** 1.3
>
> **Last Updated:** 2026-02-05 - Added Part 11: Job Authorization & Access Control with source-based permission model
>
> **Status:** Draft
>
> **Parent Document:** [Unified GPU & Use Case Platform](./unified-gpu-usecase-platform.md)

---

## Table of Contents

1. [Overview](#part-1-overview)
2. [Job Abstraction](#part-2-job-abstraction)
3. [Job Types & Classification](#part-3-job-types--classification)
4. [Scheduling Mechanisms](#part-4-scheduling-mechanisms)
5. [Orchestration Layers](#part-5-orchestration-layers)
6. [Kueue Deep Dive](#part-6-kueue-deep-dive)
7. [Pipeline & Step Execution](#part-7-pipeline--step-execution)
8. [Multi-Cluster Scheduling](#part-8-multi-cluster-scheduling)
9. [Job Lifecycle Management](#part-9-job-lifecycle-management)
10. [API Reference](#part-10-api-reference)
11. [Job Authorization & Access Control](#part-11-job-authorization--access-control)

---

## Part 1: Overview

### 1.1 Why Jobs?

In Bud AI Foundry, **everything deployed on a cluster is a Job**. The Job abstraction provides:

1. **Unified Tracking**: Single view of all workloads regardless of source
2. **Resource Accounting**: Consistent GPU/CPU/memory tracking and billing
3. **Scheduling Control**: Priority, quotas, fair-share across all workload types
4. **Lifecycle Management**: Common state machine for all deployments
5. **Cost Attribution**: Accurate cost tracking per tenant/project/workload

### 1.2 Core Concepts

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              CORE CONCEPTS                                       │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   JOB                          PIPELINE                      CLUSTER           │
│   ───                          ────────                      ───────           │
│   Atomic scheduling unit       Collection of Steps           Physical/virtual  │
│   that requires cluster        with dependencies             infrastructure    │
│   resources (GPU/CPU/RAM)      and triggers                  running K8s       │
│                                                                                 │
│   Examples:                    Examples:                     Examples:         │
│   • Model endpoint             • RAG deployment flow         • AWS EKS         │
│   • Training run               • Nightly retraining          • Azure AKS       │
│   • Batch inference            • Data ingestion              • On-premises     │
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   STEP                         TRIGGER                       QUEUE             │
│   ────                         ───────                       ─────             │
│   Single unit of work          What starts a Pipeline        Logical grouping  │
│   in a Pipeline                or Job                        for scheduling    │
│                                                                                 │
│   Types:                       Types:                        Types:            │
│   • JOB (creates Job)          • Manual (API call)           • ClusterQueue    │
│   • API_CALL                   • Cron (scheduled)            • LocalQueue      │
│   • FUNCTION                   • Event (webhook/pubsub)      • Cohort          │
│   • CONDITION                  • Dependency (job complete)                     │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 1.3 Service Ownership

| Concept | Owner Service | Database | Responsibility |
|---------|---------------|----------|----------------|
| **Job** | BudCluster | PostgreSQL | Create, track, lifecycle, cost |
| **Pipeline** | BudPipeline | PostgreSQL | DAG definition, triggers |
| **Step** | BudPipeline | PostgreSQL | Execution, dependencies |
| **Cluster** | BudCluster | PostgreSQL | Infrastructure, Kueue config |
| **Queue** | BudCluster | Kubernetes (Kueue CRDs) | Admission, quotas |
| **Template** | BudUseCases | PostgreSQL | Use case definitions |

### 1.4 High-Level Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           REQUEST TO EXECUTION FLOW                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   USER REQUEST                                                                  │
│   ────────────                                                                  │
│   "Deploy RAG with Llama 3"                                                     │
│           │                                                                     │
│           ▼                                                                     │
│   ┌───────────────┐                                                            │
│   │  BudUseCases  │ ──► Resolves template, creates Pipeline                    │
│   └───────┬───────┘                                                            │
│           │                                                                     │
│           ▼                                                                     │
│   ┌───────────────┐                                                            │
│   │  BudPipeline  │ ──► Executes DAG, runs Steps in order                      │
│   └───────┬───────┘                                                            │
│           │                                                                     │
│           │ Only JOB-type Steps                                                │
│           ▼                                                                     │
│   ┌───────────────┐                                                            │
│   │  BudCluster   │ ──► Creates Job record, submits to Kubernetes              │
│   └───────┬───────┘                                                            │
│           │                                                                     │
│           ▼                                                                     │
│   ┌───────────────┐                                                            │
│   │    Kueue      │ ──► Admission control: quota, priority, fair-share         │
│   └───────┬───────┘                                                            │
│           │                                                                     │
│           ▼                                                                     │
│   ┌───────────────┐                                                            │
│   │ K8s Scheduler │ ──► Node selection, pod placement                          │
│   └───────┬───────┘                                                            │
│           │                                                                     │
│           ▼                                                                     │
│   ┌───────────────┐                                                            │
│   │   Kubelet     │ ──► Container execution on node                            │
│   └───────────────┘                                                            │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Part 2: Job Abstraction

### 2.1 What is a Job?

A **Job** is the atomic scheduling unit in Bud AI Foundry. It represents any workload that:
- Requires cluster resources (GPU, CPU, memory)
- Has a defined lifecycle (start, run, complete/fail)
- Needs scheduling decisions (when, where, priority)
- Requires cost tracking

### 2.2 The 3-Axis Job Model

Jobs are defined across **three orthogonal axes**. This separation prevents "type explosion" and keeps the API stable while allowing rich scheduling control.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           3-AXIS JOB MODEL                                       │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   AXIS 1: TYPE (Lifecycle)         AXIS 2: POLICY (Constraints)                │
│   ────────────────────────         ────────────────────────────                │
│   "WHAT is it?"                    "HOW should it be scheduled?"               │
│                                                                                 │
│   • SERVICE (long-running)         • Priority & preemption rules               │
│   • BATCH (run-to-completion)      • Time constraints (deadline, window)       │
│   • TRAINING (with checkpoints)    • Resource constraints (queue, cohort)      │
│                                    • Topology constraints (NVLink, spread)     │
│                                    • Retry behavior                            │
│                                                                                 │
│   Affects:                         Affects:                                    │
│   • Restart semantics              • Kueue admission decisions                 │
│   • K8s resource type              • Scheduler placement                       │
│   • Billing model                  • Preemption eligibility                    │
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   AXIS 3: INTENT (Optimization)                                                │
│   ─────────────────────────────                                                │
│   "WHY does it run this way?"                                                  │
│                                                                                 │
│   • Optimization goal: LATENCY | THROUGHPUT | COST                             │
│   • Cost preferences: spot-eligible, budget cap                                │
│   • Workload classification: production, research, experiment                  │
│                                                                                 │
│   Affects:                                                                     │
│   • BudSim recommendations                                                     │
│   • Cluster selection (multi-cluster)                                          │
│   • Billing strategy                                                           │
│   • Capacity planning                                                          │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Key Principle**: Job types are NOT scheduling mechanisms. Types define lifecycle, while Policy and Intent define scheduling behavior.

| Axis | Question | Examples | Stability |
|------|----------|----------|-----------|
| **Type** | What is it? | SERVICE, BATCH, TRAINING | Very stable (rarely changes) |
| **Policy** | How to schedule? | Priority, deadline, topology | Stable (well-defined options) |
| **Intent** | Why this way? | Cost optimization, latency | Flexible (can be inferred) |

### 2.3 Job Type Definitions

```python
class JobType(str, Enum):
    """
    Lifecycle contract - determines restart semantics and K8s resource type.
    Keep this enum SMALL and STABLE.
    """
    SERVICE = "service"      # Long-running, always-on (endpoints, DBs)
    BATCH = "batch"          # Run-to-completion (preprocessing, inference)
    TRAINING = "training"    # Run-to-completion with checkpointing (ML training)
```

| Type | Lifecycle | K8s Resource | Restart | Preemption Handling |
|------|-----------|--------------|---------|---------------------|
| **SERVICE** | Long-running | Deployment/StatefulSet | Always | Reschedule immediately |
| **BATCH** | Run-to-completion | Job | On failure | Retry from start |
| **TRAINING** | Run-to-completion | Job + PVC | On failure | Save checkpoint, then retry |

**Why only 3 types?**
- SERVERLESS is not a type - it's `SERVICE` + `policy.scale_to_zero = true`
- INTERACTIVE is not a type - it's `SERVICE` + `intent.workload_class = "interactive"`
- SYSTEM is not a type - it's any type + `owner_type = "platform"`

### 2.4 Job Policy Schema

```python
class PriorityClass(str, Enum):
    """Priority determines admission order and preemption eligibility."""
    CRITICAL = "critical"    # 1000 - Never preempted, reserved capacity
    HIGH = "high"            # 100  - Rarely preempted
    NORMAL = "normal"        # 10   - Default, can be preempted
    LOW = "low"              # 1    - Background, always preemptible

class TopologyConstraint(str, Enum):
    """GPU topology requirements for multi-GPU jobs."""
    NONE = "none"            # No constraint
    SAME_NODE = "same_node"  # All GPUs on same node
    NVLINK = "nvlink"        # GPUs connected via NVLink
    SPREAD = "spread"        # Spread across nodes (fault tolerance)

class TimeWindow(SQLModel):
    """Time-of-day constraint for job execution."""
    start_hour: int          # 0-23 UTC
    end_hour: int            # 0-23 UTC
    days: List[str]          # ["monday", "tuesday", ...] or ["weekdays", "weekends"]
    timezone: str = "UTC"

class JobPolicy(SQLModel):
    """
    HOW the job should be scheduled.
    Maps directly to Kueue/K8s scheduling primitives.
    """

    # === Priority & Preemption ===
    priority_class: PriorityClass = PriorityClass.NORMAL
    preemptible: bool = True                     # Can be evicted by higher priority
    preemption_grace_period: int = 30            # Seconds to checkpoint before eviction

    # === Scaling (SERVICE only) ===
    scale_to_zero: bool = False                  # Enable serverless scale-to-zero behavior
    min_replicas: int = 1                        # Minimum replicas (0 for serverless)
    max_replicas: int = 10                       # Maximum replicas for autoscaling

    # === Time Constraints ===
    scheduled_start: Optional[datetime] = None   # Run at specific time (BudPipeline manages)
    deadline: Optional[datetime] = None          # Must complete by this time
    max_runtime: Optional[int] = None            # Max seconds (K8s activeDeadlineSeconds)
    # NOTE: time_window scheduling is handled at Pipeline layer (see Part 4.3)

    # === Queue & Fair-Share ===
    queue_name: Optional[str] = None             # Kueue LocalQueue (default: tenant queue)
    cohort: Optional[str] = None                 # Fair-share group for borrowing

    # === Topology Constraints ===
    topology: TopologyConstraint = TopologyConstraint.NONE
    node_selector: Optional[Dict[str, str]] = None  # K8s nodeSelector
    tolerations: Optional[List[Dict]] = None     # K8s tolerations

    # === Retry Behavior ===
    max_retries: int = 3
    retry_delay_seconds: int = 30
    retry_on_preemption: bool = True             # Auto-retry when preempted
```

### 2.5 Job Intent Schema

```python
class OptimizationGoal(str, Enum):
    """What to optimize for - guides BudSim and cluster selection."""
    LATENCY = "latency"          # Minimize response time (reserved capacity)
    THROUGHPUT = "throughput"    # Maximize jobs/hour (batch-friendly)
    COST = "cost"                # Minimize spend (spot, off-peak)
    BALANCED = "balanced"        # Balance all factors (default)

class WorkloadClass(str, Enum):
    """Classification for billing, quotas, and reporting."""
    PRODUCTION = "production"    # Revenue-generating workloads
    STAGING = "staging"          # Pre-production testing
    DEVELOPMENT = "development"  # Developer workloads
    RESEARCH = "research"        # Experimental, exploratory
    SYSTEM = "system"            # Platform-internal jobs

class CheckpointConfig(SQLModel):
    """Configuration for TRAINING job checkpointing."""
    enabled: bool = True                         # Enable automatic checkpointing
    storage_class: str = "standard"              # PVC storage class
    storage_size: str = "100Gi"                  # PVC size for checkpoints
    checkpoint_interval: int = 3600              # Seconds between checkpoints
    max_checkpoints: int = 3                     # Number of checkpoints to retain
    checkpoint_path: str = "/checkpoints"        # Mount path in container

class JobIntent(SQLModel):
    """
    WHY the job runs this way - optimization hints and classification.
    Can be explicitly set or inferred by BudSim.
    """

    # === Optimization ===
    optimization_goal: OptimizationGoal = OptimizationGoal.BALANCED

    # === Cost Preferences ===
    spot_eligible: bool = False              # Can use spot/preemptible instances
    budget_cap: Optional[Decimal] = None     # Max cost in USD
    budget_action: str = "warn"              # "warn" | "pause" | "cancel" when exceeded
    cost_center: Optional[str] = None        # For internal chargeback

    # === Workload Classification ===
    workload_class: WorkloadClass = WorkloadClass.DEVELOPMENT
    sla_tier: Optional[str] = None           # "gold", "silver", "bronze"

    # === Hints for BudSim ===
    expected_duration_hint: Optional[int] = None  # User estimate in seconds
    gpu_memory_hint: Optional[str] = None    # "40GB", "80GB" - helps right-sizing

    # === TRAINING-specific ===
    checkpoint_config: Optional[CheckpointConfig] = None  # Only for TRAINING jobs
```

### 2.6 Complete Job Schema

```python
class JobStatus(str, Enum):
    PENDING = "pending"          # Created, not yet submitted
    QUEUED = "queued"            # Submitted to Kueue, waiting admission
    ADMITTED = "admitted"        # Kueue admitted, waiting K8s scheduling
    RUNNING = "running"          # Executing on cluster
    SUCCEEDED = "succeeded"      # Completed successfully
    FAILED = "failed"            # Execution failed
    CANCELLED = "cancelled"      # User cancelled
    PREEMPTED = "preempted"      # Evicted by higher priority job

class DeploymentType(str, Enum):
    HELM = "helm"            # Helm chart deployment
    DOCKER = "docker"        # Direct container deployment
    MODEL = "model"          # Model serving (vLLM, TGI, etc.)

class SourceType(str, Enum):
    DIRECT = "direct"        # Created via BudApp API
    PIPELINE = "pipeline"    # Created by Pipeline step
    USECASE = "usecase"      # Created by UseCase deployment

class OwnerType(str, Enum):
    USER = "user"            # User-created workload
    PLATFORM = "platform"    # Platform-internal (system jobs)


class Job(SQLModel, table=True):
    """
    The atomic scheduling unit in Bud AI Foundry.
    Structured as: Identity + Type + Policy + Intent + Resources + Status
    """

    # ══════════════════════════════════════════════════════════════════════
    # IDENTITY
    # ══════════════════════════════════════════════════════════════════════
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str                                    # Human-readable name

    # ══════════════════════════════════════════════════════════════════════
    # TYPE (Axis 1: Lifecycle - WHAT is it?)
    # ══════════════════════════════════════════════════════════════════════
    job_type: JobType                            # SERVICE, BATCH, TRAINING
    deployment_type: DeploymentType              # HELM, DOCKER, MODEL

    # ══════════════════════════════════════════════════════════════════════
    # POLICY (Axis 2: Constraints - HOW to schedule?)
    # ══════════════════════════════════════════════════════════════════════
    policy: JobPolicy = Field(default_factory=JobPolicy, sa_column=Column(JSON))

    # ══════════════════════════════════════════════════════════════════════
    # INTENT (Axis 3: Optimization - WHY this way?)
    # ══════════════════════════════════════════════════════════════════════
    intent: JobIntent = Field(default_factory=JobIntent, sa_column=Column(JSON))

    # ══════════════════════════════════════════════════════════════════════
    # SOURCE & OWNERSHIP
    # ══════════════════════════════════════════════════════════════════════
    source_type: SourceType                      # DIRECT, PIPELINE, USECASE
    source_id: Optional[UUID] = None             # Pipeline ID, UseCase ID, or None
    step_id: Optional[UUID] = None               # Step ID if from Pipeline

    cluster_id: UUID                             # Target cluster
    project_id: UUID                             # Owning project
    tenant_id: UUID                              # Owning tenant
    created_by: UUID                             # User who created
    owner_type: OwnerType = OwnerType.USER       # USER or PLATFORM

    # ══════════════════════════════════════════════════════════════════════
    # IDEMPOTENCY (prevents duplicate job creation during failures/retries)
    # ══════════════════════════════════════════════════════════════════════
    idempotency_key: Optional[str] = Field(
        default=None,
        index=True,
        sa_column=Column(String, unique=True, nullable=True),
        description="Client-provided key to prevent duplicate job creation"
    )

    # ══════════════════════════════════════════════════════════════════════
    # RESOURCE REQUIREMENTS
    # ══════════════════════════════════════════════════════════════════════
    gpu_type: Optional[str] = None               # "A100", "H100", "T4", None
    gpu_count: int = 0                           # Number of GPUs
    cpu_request: str = "1"                       # CPU cores requested
    cpu_limit: str = "2"                         # CPU cores limit
    memory_request: str = "4Gi"                  # Memory requested
    memory_limit: str = "8Gi"                    # Memory limit

    # ══════════════════════════════════════════════════════════════════════
    # ESTIMATES (from BudSim or heuristics)
    # ══════════════════════════════════════════════════════════════════════
    estimated_duration: Optional[int] = None     # Seconds
    estimated_start: Optional[datetime] = None   # When expected to start
    estimated_end: Optional[datetime] = None     # When expected to complete
    estimated_cost: Optional[Decimal] = None     # Estimated cost in USD

    # ══════════════════════════════════════════════════════════════════════
    # ACTUALS (recorded during execution)
    # ══════════════════════════════════════════════════════════════════════
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    actual_cost: Optional[Decimal] = None

    # ══════════════════════════════════════════════════════════════════════
    # STATUS
    # ══════════════════════════════════════════════════════════════════════
    status: JobStatus = JobStatus.PENDING
    status_message: Optional[str] = None
    retry_count: int = 0

    # ══════════════════════════════════════════════════════════════════════
    # KUBERNETES REFERENCES
    # ══════════════════════════════════════════════════════════════════════
    k8s_namespace: Optional[str] = None
    k8s_resource_type: Optional[str] = None      # "deployment", "job", "statefulset"
    k8s_resource_name: Optional[str] = None
    kueue_workload_name: Optional[str] = None

    # ══════════════════════════════════════════════════════════════════════
    # METADATA
    # ══════════════════════════════════════════════════════════════════════
    labels: Dict = Field(default_factory=dict, sa_column=Column(JSON))
    annotations: Dict = Field(default_factory=dict, sa_column=Column(JSON))

    # ══════════════════════════════════════════════════════════════════════
    # TIMESTAMPS
    # ══════════════════════════════════════════════════════════════════════
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

### 2.7 3-Axis Mapping to Kueue

```yaml
# Example: TRAINING job with COST optimization and time constraints
# Bud Job → Kueue Workload mapping

# Source Job:
#   job_type: TRAINING
#   policy:
#     priority_class: normal
#     preemptible: true
#     deadline: "2026-02-03T06:00:00Z"
#     topology: nvlink
#     queue_name: research-queue
#   intent:
#     optimization_goal: cost
#     spot_eligible: true
#     workload_class: research

# Generated Kueue Workload:
apiVersion: kueue.x-k8s.io/v1beta1
kind: Workload
metadata:
  name: training-job-001
  namespace: tenant-acme
  labels:
    # TYPE (Axis 1)
    bud.ai/job-type: training
    bud.ai/deployment-type: model

    # INTENT (Axis 3)
    bud.ai/optimization-goal: cost
    bud.ai/workload-class: research
    bud.ai/spot-eligible: "true"
spec:
  # POLICY (Axis 2) → Kueue primitives
  queueName: research-queue                # policy.queue_name
  priorityClassName: normal                # policy.priority_class

  podSets:
  - name: trainer
    count: 1
    template:
      spec:
        # POLICY.topology → Node affinity
        affinity:
          nodeAffinity:
            requiredDuringSchedulingIgnoredDuringExecution:
              nodeSelectorTerms:
              - matchExpressions:
                - key: nvidia.com/gpu.topology
                  operator: In
                  values: ["nvlink"]

        # Resources
        containers:
        - name: trainer
          resources:
            limits:
              nvidia.com/gpu: 4
            requests:
              nvidia.com/gpu: 4
              memory: 128Gi

        # POLICY.preemptible → Toleration for spot nodes
        tolerations:
        - key: "kubernetes.azure.com/scalesetpriority"
          operator: "Equal"
          value: "spot"
          effect: "NoSchedule"
```

### 2.8 Job State Machine

```
                                    ┌─────────────────┐
                                    │    CANCELLED    │
                                    └────────▲────────┘
                                             │ User cancels
                                             │
┌─────────┐    Submit    ┌─────────┐    Admit    ┌──────────┐    Schedule    ┌─────────┐
│ PENDING │─────────────►│ QUEUED  │────────────►│ ADMITTED │───────────────►│ RUNNING │
└─────────┘              └────┬────┘             └────┬─────┘                └────┬────┘
                              │                       │                           │
                              │                       │                           ├─────────┐
                              │                       │                           │         │
                              │                       │                     ┌─────▼────┐    │
                              │                       │                     │SUCCEEDED │    │
                              │                       │                     └──────────┘    │
                              │                       │                                     │
                              │                       │ Rejected              ┌─────────┐   │
                              │                       └──────────────────────►│ FAILED  │◄──┘
                              │                                               └─────────┘
                              │                                                     ▲
                              │         ┌───────────┐                               │
                              └────────►│ PREEMPTED │───────────────────────────────┘
                                        └───────────┘   Can retry → QUEUED
                                              ▲
                                              │ Higher priority job needs resources
                                              │
                                        ┌─────┴─────┐
                                        │  RUNNING  │
                                        └───────────┘
```

> **Status Disambiguation:**
>
> | Status | Where | Meaning |
> |--------|-------|---------|
> | **PENDING** | BudCluster DB | Job created but NOT submitted to Kueue yet. May be waiting for: scheduled_start time, Pipeline step completion, or manual trigger. |
> | **QUEUED** | BudCluster DB + Kueue | Job submitted to Kueue, Workload CR created, waiting for quota/admission. Kueue is aware of the job. |
> | **ADMITTED** | Kueue → K8s | Kueue admitted the Workload, K8s pods being created. Resources reserved but containers not yet running. |
> | **RUNNING** | K8s | Pods running, containers executing. |
>
> **Kueue Workload Deletion Timing:**
> - Workload CR is created when job transitions PENDING → QUEUED
> - Workload CR is deleted when job reaches terminal state (SUCCEEDED, FAILED, CANCELLED)
> - For PREEMPTED: Workload evicted but NOT deleted (allows re-admission)
> - BudCluster is responsible for cleanup: garbage collect Workloads for jobs > 24h in terminal state

### 2.9 Job Creation Sources

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           JOB CREATION SOURCES                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   SOURCE: DIRECT                                                                │
│   ──────────────                                                                │
│   User deploys model via BudApp UI/API                                         │
│                                                                                 │
│   POST /api/endpoints                                                           │
│        │                                                                        │
│        ▼                                                                        │
│   BudApp ──► BudCluster.create_job(source_type=DIRECT)                         │
│        │                                                                        │
│        ▼                                                                        │
│   Endpoint record stores job_id reference                                       │
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   SOURCE: PIPELINE                                                              │
│   ────────────────                                                              │
│   Pipeline executes JOB-type step                                              │
│                                                                                 │
│   Pipeline DAG execution                                                        │
│        │                                                                        │
│        ▼                                                                        │
│   BudPipeline: Execute Step (type=JOB)                                         │
│        │                                                                        │
│        ▼                                                                        │
│   BudCluster.create_job(source_type=PIPELINE, source_id=pipeline_id)           │
│        │                                                                        │
│        ▼                                                                        │
│   Step record stores job_id, waits for completion                              │
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   SOURCE: USECASE                                                               │
│   ───────────────                                                               │
│   UseCase template deployment (creates Pipeline internally)                     │
│                                                                                 │
│   POST /api/usecases/deploy                                                     │
│        │                                                                        │
│        ▼                                                                        │
│   BudUseCases ──► Creates Pipeline from template                               │
│        │                                                                        │
│        ▼                                                                        │
│   BudPipeline executes (same as PIPELINE source)                               │
│        │                                                                        │
│        ▼                                                                        │
│   Jobs created with source_type=USECASE, source_id=usecase_deployment_id       │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Part 3: Job Types & Classification

> **Note**: Job Types are **Axis 1 (Lifecycle)** of the 3-axis model defined in Part 2.
> Types define WHAT a job is (lifecycle contract), not HOW it's scheduled (Policy) or WHY (Intent).
> Keep job types **small and stable** - use Policy and Intent for scheduling variations.

### 3.1 Job Types Overview (Axis 1: Lifecycle)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              JOB TYPES                                           │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   SERVICE                      BATCH                       TRAINING             │
│   ───────                      ─────                       ────────             │
│   Long-running                 Run-to-completion           Long-running         │
│   Always available             One-time execution          With checkpointing   │
│   Auto-restart on failure      No restart after success    Resumable            │
│                                                                                 │
│   K8s Resource:                K8s Resource:               K8s Resource:        │
│   Deployment/StatefulSet       Job/CronJob                 Job + PVC            │
│                                                                                 │
│   Examples:                    Examples:                   Examples:            │
│   • Model endpoints            • Data preprocessing        • Fine-tuning        │
│   • Vector databases           • Batch inference           • Full training      │
│   • API servers                • Report generation         • LoRA adaptation    │
│   • Chatbot backends           • Index building            • RLHF               │
│   • RAG orchestrators          • Embedding generation      • Continued pretrain │
│                                                                                 │
│   Lifecycle:                   Lifecycle:                  Lifecycle:           │
│   RUNNING until stopped        RUNNING → SUCCEEDED/FAILED  RUNNING with         │
│   or failed                                                checkpoints          │
│                                                                                 │
│   Billing:                     Billing:                    Billing:             │
│   Per-second while running     Per-second of execution     Per-second + storage │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 SERVICE Jobs

**Characteristics:**
- Run indefinitely until explicitly stopped
- Auto-restart on failure (based on `restartPolicy`)
- Health checks (liveness, readiness probes)
- Horizontal scaling (replicas)
- Load balancing

**Kubernetes Mapping:**
```yaml
# SERVICE Job → Kubernetes Deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: llm-endpoint-001
  labels:
    bud.ai/job-id: "uuid-here"
    bud.ai/job-type: "service"
spec:
  replicas: 2
  selector:
    matchLabels:
      app: llm-endpoint-001
  template:
    spec:
      containers:
      - name: vllm
        image: vllm/vllm-openai:latest
        resources:
          limits:
            nvidia.com/gpu: 1
```

**Kueue Integration:**
```yaml
# Deployment wrapped in Kueue-managed Job for admission control
apiVersion: kueue.x-k8s.io/v1beta1
kind: Workload
metadata:
  name: llm-endpoint-001-workload
spec:
  queueName: tenant-a-queue
  priority: 100
  podSets:
  - name: main
    count: 2
    template:
      spec:
        containers:
        - name: vllm
          resources:
            requests:
              nvidia.com/gpu: 1
```

### 3.3 BATCH Jobs

**Characteristics:**
- Run to completion
- No restart after success
- Retry on failure (configurable)
- Parallelism support
- Completion tracking

**Kubernetes Mapping:**
```yaml
# BATCH Job → Kubernetes Job
apiVersion: batch/v1
kind: Job
metadata:
  name: embedding-job-001
  labels:
    bud.ai/job-id: "uuid-here"
    bud.ai/job-type: "batch"
spec:
  completions: 1
  parallelism: 1
  backoffLimit: 3
  activeDeadlineSeconds: 3600
  template:
    spec:
      restartPolicy: Never
      containers:
      - name: embedder
        image: sentence-transformers/all-MiniLM-L6-v2
        resources:
          limits:
            nvidia.com/gpu: 1
```

**Kueue Integration:**
```yaml
apiVersion: kueue.x-k8s.io/v1beta1
kind: Workload
metadata:
  name: embedding-job-001-workload
spec:
  queueName: tenant-a-queue
  priority: 10  # Lower priority than SERVICE
  podSets:
  - name: main
    count: 1
    template:
      spec:
        containers:
        - name: embedder
          resources:
            requests:
              nvidia.com/gpu: 1
```

### 3.4 TRAINING Jobs

**Characteristics:**
- Long-running with periodic checkpoints
- Resumable from last checkpoint
- Distributed training support
- GPU memory optimization (gradient checkpointing)
- Progress tracking (loss, accuracy)

**Kubernetes Mapping:**
```yaml
# TRAINING Job → Kubernetes Job + PVC for checkpoints
apiVersion: batch/v1
kind: Job
metadata:
  name: finetune-llama-001
  labels:
    bud.ai/job-id: "uuid-here"
    bud.ai/job-type: "training"
spec:
  completions: 1
  parallelism: 1
  backoffLimit: 5  # More retries for long jobs
  template:
    spec:
      restartPolicy: OnFailure  # Resume on failure
      containers:
      - name: trainer
        image: pytorch/pytorch:2.0-cuda11.8
        resources:
          limits:
            nvidia.com/gpu: 4
        volumeMounts:
        - name: checkpoints
          mountPath: /checkpoints
      volumes:
      - name: checkpoints
        persistentVolumeClaim:
          claimName: finetune-llama-001-ckpt
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: finetune-llama-001-ckpt
spec:
  accessModes: [ReadWriteOnce]
  resources:
    requests:
      storage: 100Gi
```

### 3.5 Job Type Comparison

| Aspect | SERVICE | BATCH | TRAINING |
|--------|---------|-------|----------|
| **Duration** | Indefinite | Minutes to hours | Hours to days |
| **Restart** | Always | On failure only | On failure (resume) |
| **Scaling** | Horizontal (replicas) | Parallel pods | Distributed workers |
| **State** | Stateless (usually) | Stateless | Stateful (checkpoints) |
| **K8s Resource** | Deployment | Job | Job + PVC |
| **K8s restartPolicy** | Always | Never | OnFailure |
| **Priority Default** | HIGH | NORMAL | NORMAL |
| **Preemptible** | Rarely | Yes | Yes (with checkpoint) |
| **Billing** | Per-second running | Per-second execution | Per-second + storage |
| **SLA** | 99.9% uptime | 95% completion | 90% completion |

> **Note on restartPolicy:**
> - **BATCH** uses `restartPolicy: Never` because work is restarted from scratch on failure (backoffLimit handles retries)
> - **TRAINING** uses `restartPolicy: OnFailure` to enable checkpoint-based resumption without losing progress
> - Both have K8s Job `backoffLimit` for total retry limits
>
> **Note on SERVICE Preemption:**
> While SERVICE jobs are "rarely" preempted, they can be evicted in extreme resource pressure. When preempted:
> 1. K8s sends SIGTERM (respecting `terminationGracePeriodSeconds`)
> 2. Pod drains active connections
> 3. Kueue re-queues the Workload for rescheduling
> 4. New pod is scheduled ASAP (high priority means quick re-admission)

### 3.6 Resource Profiles

Jobs can be classified by their resource requirements:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           RESOURCE PROFILES                                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   GPU-INTENSIVE                                                                 │
│   ─────────────                                                                 │
│   • GPU: 1-8 (required)          Use Cases:                                    │
│   • CPU: Low (1-4 cores)         • LLM inference (vLLM, TGI)                   │
│   • Memory: High (32-256GB)      • Training, fine-tuning                       │
│   • Storage: Medium              • Image/video generation                       │
│                                                                                 │
│   ResourceFlavor: gpu-a100, gpu-h100, gpu-t4                                   │
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   CPU-ONLY                                                                      │
│   ────────                                                                      │
│   • GPU: 0                       Use Cases:                                    │
│   • CPU: High (4-32 cores)       • RAG orchestrators                           │
│   • Memory: Medium (8-64GB)      • API gateways                                │
│   • Storage: Low                 • Data preprocessing (small)                  │
│                                                                                 │
│   ResourceFlavor: cpu-standard, cpu-compute                                    │
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   MEMORY-INTENSIVE                                                              │
│   ────────────────                                                              │
│   • GPU: 0-1                     Use Cases:                                    │
│   • CPU: Medium (4-16 cores)     • Vector databases (Qdrant, Milvus)           │
│   • Memory: Very High (128GB+)   • Embedding stores                            │
│   • Storage: High (SSD)          • In-memory caches                            │
│                                                                                 │
│   ResourceFlavor: memory-optimized                                             │
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   STORAGE-INTENSIVE                                                             │
│   ─────────────────                                                             │
│   • GPU: 0                       Use Cases:                                    │
│   • CPU: Low (2-8 cores)         • Document stores                             │
│   • Memory: Low (4-16GB)         • Model registries                            │
│   • Storage: Very High (TB+)     • Training data                               │
│                                                                                 │
│   ResourceFlavor: storage-optimized                                            │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 3.7 What is NOT a Job Type

These are common workload patterns that should **NOT** be new job types. Instead, they are combinations of TYPE + POLICY + INTENT:

| Pattern | NOT a Type | Correct Modeling |
|---------|------------|------------------|
| **Serverless** | ~~SERVERLESS~~ | `type: SERVICE` + `policy.scale_to_zero: true` |
| **Spot/Preemptible** | ~~SPOT_JOB~~ | Any type + `intent.spot_eligible: true` |
| **Scheduled Batch** | ~~CRON_JOB~~ | `type: BATCH` + `policy.scheduled_start` or Pipeline trigger |
| **Interactive** | ~~INTERACTIVE~~ | `type: SERVICE` + `intent.workload_class: interactive` |
| **System Job** | ~~SYSTEM~~ | Any type + `owner_type: platform` |
| **Low Priority** | ~~BACKGROUND~~ | Any type + `policy.priority_class: low` |
| **Time-Bounded** | ~~DEADLINE_JOB~~ | Any type + `policy.deadline` |
| **Cost-Optimized** | ~~COST_JOB~~ | Any type + `intent.optimization_goal: cost` |

**Why this matters:**
1. **API Stability**: Types rarely change; Policy/Intent can evolve
2. **Scheduler Portability**: Kueue today, Slurm tomorrow - types stay the same
3. **No Type Explosion**: Avoids 20+ job types
4. **Clean Reporting**: Filter by type, policy, or intent independently

---

## Part 4: Scheduling Mechanisms

### 4.1 Scheduling Dimensions Overview

There are **6 dimensions** of scheduling in Bud AI Foundry:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        6 SCHEDULING DIMENSIONS                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   1. RESOURCE-BASED              2. TIME-BASED              3. EVENT-BASED     │
│   ──────────────────             ──────────────             ──────────────     │
│   "Do I have GPUs?"              "Run at 2am"               "Run when X"       │
│                                                                                 │
│   • Quota enforcement            • Cron schedules           • Data arrival     │
│   • Fair-share allocation        • Scheduled start          • Model update     │
│   • Resource flavors             • Time windows             • Webhook trigger  │
│   • Bin-packing                  • Deadlines                • Pub/sub event    │
│                                                                                 │
│   Owner: Kueue                   Owner: BudPipeline         Owner: BudPipeline │
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   4. PRIORITY-BASED              5. DEPENDENCY-BASED        6. COST-BASED      │
│   ─────────────────              ──────────────────         ─────────────      │
│   "Who goes first?"              "Run after Y done"         "Minimize cost"    │
│                                                                                 │
│   • Priority classes             • Pipeline DAG             • Spot instances   │
│   • Preemption rules             • Job dependencies         • Cluster pricing  │
│   • Queue ordering               • Data dependencies        • Right-sizing     │
│   • SLA tiers                    • Wait conditions          • Reserved vs OD   │
│                                                                                 │
│   Owner: Kueue                   Owner: BudPipeline         Owner: BudCluster  │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Mapping to 3-Axis Model:**

| Scheduling Dimension | Maps to Axis | Job Schema Field |
|---------------------|--------------|------------------|
| **Resource-based** | Policy (Axis 2) | `policy.queue_name`, `policy.cohort`, GPU/CPU/memory fields |
| **Time-based** | Policy (Axis 2) | `policy.scheduled_start`, `policy.deadline`, `policy.time_window` |
| **Event-based** | External | Pipeline triggers (not stored in Job) |
| **Priority-based** | Policy (Axis 2) | `policy.priority_class`, `policy.preemptible` |
| **Dependency-based** | External | Pipeline DAG, Step dependencies (not stored in Job) |
| **Cost-based** | Intent (Axis 3) | `intent.optimization_goal`, `intent.spot_eligible`, `intent.budget_cap` |

> **Key Insight**: Scheduling dimensions are NOT job types. They are combinations of Policy and Intent that influence HOW jobs are scheduled, not WHAT they are.

### 4.2 Resource-Based Scheduling (Kueue)

**What**: Decides IF and WHEN a job can start based on available resources.

**Components:**

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        KUEUE RESOURCE SCHEDULING                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   ClusterQueue                                                                  │
│   ────────────                                                                  │
│   Cluster-wide queue with total resource capacity                              │
│                                                                                 │
│   ┌─────────────────────────────────────────────────────┐                      │
│   │  ClusterQueue: "gpu-queue"                          │                      │
│   │  ├── ResourceFlavor: gpu-a100 (quota: 20 GPUs)     │                      │
│   │  ├── ResourceFlavor: gpu-h100 (quota: 8 GPUs)      │                      │
│   │  └── ResourceFlavor: gpu-t4 (quota: 50 GPUs)       │                      │
│   └─────────────────────────────────────────────────────┘                      │
│                         │                                                       │
│                         │ Serves multiple LocalQueues                          │
│                         ▼                                                       │
│   LocalQueue (per tenant/namespace)                                            │
│   ──────────                                                                   │
│   Namespace-scoped queue that users submit to                                  │
│                                                                                 │
│   ┌──────────────────────┐   ┌──────────────────────┐                         │
│   │ LocalQueue: tenant-a │   │ LocalQueue: tenant-b │                         │
│   │ Quota: 10 A100 GPUs  │   │ Quota: 10 A100 GPUs  │                         │
│   │ Borrowing: enabled   │   │ Borrowing: enabled   │                         │
│   └──────────────────────┘   └──────────────────────┘                         │
│                                                                                 │
│   Cohort (Fair-Share Group)                                                    │
│   ──────                                                                       │
│   Groups ClusterQueues for resource sharing                                    │
│                                                                                 │
│   ┌─────────────────────────────────────────────────────┐                      │
│   │  Cohort: "production"                               │                      │
│   │  ├── ClusterQueue: gpu-queue                        │                      │
│   │  └── ClusterQueue: cpu-queue                        │                      │
│   │                                                     │                      │
│   │  Fair-share: tenant-a (50%), tenant-b (50%)         │                      │
│   └─────────────────────────────────────────────────────┘                      │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**ResourceFlavor Examples:**

```yaml
# GPU ResourceFlavors
apiVersion: kueue.x-k8s.io/v1beta1
kind: ResourceFlavor
metadata:
  name: gpu-a100-80gb
spec:
  nodeLabels:
    nvidia.com/gpu.product: "NVIDIA-A100-SXM4-80GB"
---
apiVersion: kueue.x-k8s.io/v1beta1
kind: ResourceFlavor
metadata:
  name: gpu-h100-80gb
spec:
  nodeLabels:
    nvidia.com/gpu.product: "NVIDIA-H100-80GB-HBM3"
---
apiVersion: kueue.x-k8s.io/v1beta1
kind: ResourceFlavor
metadata:
  name: gpu-a100-mig-3g20gb
spec:
  nodeLabels:
    nvidia.com/mig.config: "all-3g.20gb"
```

### 4.3 Time-Based Scheduling

**What**: Jobs that run at specific times or within time windows.

> **Design Decision: Centralized Time Scheduling**
>
> Time-based scheduling is **centralized at the BudPipeline layer**, following industry best practices
> (Airflow, Argo Workflows, Prefect). This avoids fragmentation across BudPipeline, BudCluster, Kueue, and K8s.
>
> | Mechanism | Owner | How It Works |
> |-----------|-------|--------------|
> | Cron schedule | BudPipeline | Pipeline triggers with `trigger_type: CRON` |
> | Scheduled start | BudPipeline | Pipeline scheduled to run at specific time |
> | Time windows | BudPipeline | Pipeline only triggers during allowed hours |
> | Deadline | Job (BudCluster) | `policy.deadline` + K8s `activeDeadlineSeconds` |
>
> **Why BudPipeline owns time scheduling:**
> - Single point of control for all time logic
> - Easier debugging and monitoring
> - Consistent behavior across job types
> - Pipelines can wrap any job with time constraints

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        TIME-BASED SCHEDULING                                     │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   CRON SCHEDULE                                                                 │
│   ─────────────                                                                 │
│   "Run every Sunday at 2am UTC"                                                │
│                                                                                 │
│   Implementation: Pipeline Trigger                                             │
│   ┌────────────────────────────────────────────────────┐                       │
│   │  Pipeline: weekly-retraining                       │                       │
│   │  Trigger:                                          │                       │
│   │    type: cron                                      │                       │
│   │    schedule: "0 2 * * 0"                          │                       │
│   │  Steps:                                            │                       │
│   │    - name: retrain-model                          │                       │
│   │      type: JOB                                    │                       │
│   │      job_type: TRAINING                           │                       │
│   └────────────────────────────────────────────────────┘                       │
│                                                                                 │
│   SCHEDULED START                                                              │
│   ───────────────                                                              │
│   "Start this job at 2026-02-03 10:00 UTC"                                    │
│                                                                                 │
│   Implementation: Job.scheduled_start field                                    │
│   ┌────────────────────────────────────────────────────┐                       │
│   │  Job:                                              │                       │
│   │    name: batch-inference-001                       │                       │
│   │    scheduled_start: "2026-02-03T10:00:00Z"        │                       │
│   │    status: PENDING (until scheduled time)         │                       │
│   └────────────────────────────────────────────────────┘                       │
│                                                                                 │
│   BudCluster holds job until scheduled_start, then submits to Kueue            │
│                                                                                 │
│   TIME WINDOW                                                                  │
│   ───────────                                                                  │
│   "Only run during off-peak hours (10pm - 6am)"                               │
│                                                                                 │
│   Implementation: Custom admission webhook or Kueue extension                  │
│   ┌────────────────────────────────────────────────────┐                       │
│   │  Job:                                              │                       │
│   │    name: background-indexing                       │                       │
│   │    time_window:                                    │                       │
│   │      start: "22:00"                               │                       │
│   │      end: "06:00"                                 │                       │
│   │      timezone: "UTC"                              │                       │
│   └────────────────────────────────────────────────────┘                       │
│                                                                                 │
│   DEADLINE                                                                     │
│   ────────                                                                     │
│   "Must complete by 2026-02-03 18:00 UTC"                                     │
│                                                                                 │
│   Implementation: Job.deadline + K8s activeDeadlineSeconds                    │
│   ┌────────────────────────────────────────────────────┐                       │
│   │  Job:                                              │                       │
│   │    name: daily-report                              │                       │
│   │    deadline: "2026-02-03T18:00:00Z"               │                       │
│   │                                                    │                       │
│   │  K8s Job:                                          │                       │
│   │    activeDeadlineSeconds: 28800  # 8 hours max    │                       │
│   └────────────────────────────────────────────────────┘                       │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 4.4 Event-Based Scheduling

**What**: Jobs triggered by events rather than time or manual action.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        EVENT-BASED SCHEDULING                                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   DATA ARRIVAL                                                                  │
│   ────────────                                                                  │
│   "When new files appear in S3 bucket"                                         │
│                                                                                 │
│   ┌─────────┐     S3 Event      ┌───────────┐    Trigger    ┌────────────┐    │
│   │   S3    │──────────────────►│   Dapr    │──────────────►│ BudPipeline│    │
│   │ Bucket  │                   │  Pub/Sub  │               │            │    │
│   └─────────┘                   └───────────┘               └─────┬──────┘    │
│                                                                   │            │
│                                                           Execute Pipeline     │
│                                                                   │            │
│                                                                   ▼            │
│                                                           ┌────────────┐       │
│                                                           │ Create Job │       │
│                                                           └────────────┘       │
│                                                                                 │
│   MODEL UPDATE                                                                  │
│   ────────────                                                                  │
│   "When new model version is registered"                                       │
│                                                                                 │
│   ┌──────────┐    Webhook     ┌────────────┐    Trigger    ┌────────────┐     │
│   │ BudModel │───────────────►│ BudPipeline│──────────────►│ Deploy Job │     │
│   │ Registry │                │            │               │            │     │
│   └──────────┘                └────────────┘               └────────────┘     │
│                                                                                 │
│   THRESHOLD BREACH                                                             │
│   ────────────────                                                             │
│   "When queue depth > 100 or latency > SLA"                                   │
│                                                                                 │
│   ┌───────────┐   Alert      ┌────────────┐    Scale      ┌────────────┐     │
│   │BudMetrics │─────────────►│ BudCluster │──────────────►│ Scale Job  │     │
│   │ (Grafana) │              │            │               │ (add pods) │     │
│   └───────────┘              └────────────┘               └────────────┘     │
│                                                                                 │
│   DEPENDENCY COMPLETION                                                        │
│   ─────────────────────                                                        │
│   "When upstream job completes"                                                │
│                                                                                 │
│   ┌────────────┐  Complete   ┌────────────┐    Start     ┌────────────┐      │
│   │ Job A      │────────────►│ BudPipeline│─────────────►│ Job B      │      │
│   │ (Ingest)   │             │ DAG Engine │              │ (Process)  │      │
│   └────────────┘             └────────────┘              └────────────┘      │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Pipeline Trigger Schema:**

```python
class TriggerType(str, Enum):
    MANUAL = "manual"        # API call / UI button
    CRON = "cron"            # Cron expression
    EVENT = "event"          # Pub/sub event
    WEBHOOK = "webhook"      # HTTP webhook
    DEPENDENCY = "dependency" # Another pipeline/job completes

class PipelineTrigger(SQLModel, table=True):
    id: UUID
    pipeline_id: UUID
    trigger_type: TriggerType

    # Cron config
    cron_expression: Optional[str]      # "0 2 * * 0"
    timezone: Optional[str]             # "UTC"

    # Event config
    event_topic: Optional[str]          # "s3-file-uploaded"
    event_filter: Optional[dict]        # {"bucket": "my-bucket"}

    # Webhook config
    webhook_secret: Optional[str]

    # Dependency config
    depends_on_pipeline_id: Optional[UUID]
    depends_on_job_status: Optional[str]  # "succeeded", "any"

    enabled: bool = True
```

### 4.5 Priority-Based Scheduling

**What**: Determines the order in which jobs are admitted and whether jobs can preempt others.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        PRIORITY-BASED SCHEDULING                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   PRIORITY CLASSES                                                              │
│   ────────────────                                                              │
│                                                                                 │
│   ┌────────────┬────────────┬─────────────┬─────────────────────────────────┐  │
│   │  Priority  │   Value    │ Preemptible │ Use Case                        │  │
│   ├────────────┼────────────┼─────────────┼─────────────────────────────────┤  │
│   │ CRITICAL   │ 1000       │ No          │ Production endpoints, revenue   │  │
│   │ HIGH       │ 100        │ Rarely      │ Important batch, staging        │  │
│   │ NORMAL     │ 10         │ Yes         │ Development, testing            │  │
│   │ LOW        │ 1          │ Always      │ Background, spot workloads      │  │
│   └────────────┴────────────┴─────────────┴─────────────────────────────────┘  │
│                                                                                 │
│   PREEMPTION RULES                                                             │
│   ────────────────                                                             │
│                                                                                 │
│   Rule 1: Higher priority can preempt lower priority                           │
│   ┌─────────────────────────────────────────────────────────────────────┐      │
│   │  CRITICAL job arrives                                               │      │
│   │       │                                                             │      │
│   │       ▼                                                             │      │
│   │  Check for resources ──► Not available                              │      │
│   │       │                                                             │      │
│   │       ▼                                                             │      │
│   │  Find LOW/NORMAL jobs to preempt                                   │      │
│   │       │                                                             │      │
│   │       ▼                                                             │      │
│   │  Preempt jobs ──► CRITICAL job admitted                            │      │
│   └─────────────────────────────────────────────────────────────────────┘      │
│                                                                                 │
│   Rule 2: Same priority = FIFO within queue                                    │
│   Rule 3: Fair-share across tenants at same priority                           │
│   Rule 4: TRAINING jobs get grace period for checkpointing before preemption   │
│                                                                                 │
│   KUEUE WORKLOAD PRIORITY                                                      │
│   ───────────────────────                                                      │
│                                                                                 │
│   apiVersion: kueue.x-k8s.io/v1beta1                                          │
│   kind: WorkloadPriorityClass                                                  │
│   metadata:                                                                    │
│     name: critical                                                             │
│   value: 1000                                                                  │
│   preemptionPolicy: PreemptLowerPriority                                      │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 4.6 Dependency-Based Scheduling

**What**: Jobs that depend on other jobs or pipeline steps completing.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      DEPENDENCY-BASED SCHEDULING                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   PIPELINE DAG                                                                  │
│   ────────────                                                                  │
│   Steps execute based on DAG dependencies                                      │
│                                                                                 │
│   ┌─────────┐                                                                  │
│   │ Step 1  │ Ingest Data (BATCH Job)                                         │
│   │  (JOB)  │                                                                  │
│   └────┬────┘                                                                  │
│        │                                                                        │
│        ▼                                                                        │
│   ┌─────────┐                                                                  │
│   │ Step 2  │ Validate Data (FUNCTION - no Job)                               │
│   │(FUNCTION)│                                                                  │
│   └────┬────┘                                                                  │
│        │                                                                        │
│        ├────────────────┬────────────────┐                                     │
│        ▼                ▼                ▼                                     │
│   ┌─────────┐      ┌─────────┐      ┌─────────┐                               │
│   │ Step 3a │      │ Step 3b │      │ Step 3c │  Parallel execution           │
│   │  (JOB)  │      │  (JOB)  │      │  (JOB)  │                               │
│   └────┬────┘      └────┬────┘      └────┬────┘                               │
│        │                │                │                                     │
│        └────────────────┼────────────────┘                                     │
│                         │                                                       │
│                         ▼                                                       │
│                    ┌─────────┐                                                 │
│                    │ Step 4  │ Wait for all parallel jobs                     │
│                    │  (JOB)  │                                                 │
│                    └─────────┘                                                 │
│                                                                                 │
│   JOB-TO-JOB DEPENDENCY                                                        │
│   ─────────────────────                                                        │
│   Direct job dependency (outside of pipelines)                                 │
│                                                                                 │
│   ┌────────────────────────────────────────────────────┐                       │
│   │  Job B:                                            │                       │
│   │    name: process-data                              │                       │
│   │    depends_on:                                     │                       │
│   │      - job_id: "job-a-uuid"                       │                       │
│   │        status: succeeded                           │                       │
│   └────────────────────────────────────────────────────┘                       │
│                                                                                 │
│   Job B stays PENDING until Job A completes successfully                       │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 4.7 Cost-Based Scheduling

**What**: Optimize job placement and timing based on cost.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        COST-BASED SCHEDULING                                     │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   SPOT/PREEMPTIBLE INSTANCES                                                   │
│   ──────────────────────────                                                   │
│   Use cheaper spot instances for fault-tolerant jobs                           │
│                                                                                 │
│   ┌────────────────────────────────────────────────────┐                       │
│   │  Job:                                              │                       │
│   │    name: batch-inference                           │                       │
│   │    spot_eligible: true                             │                       │
│   │    checkpoint_enabled: true  # Can resume          │                       │
│   │                                                    │                       │
│   │  Kueue places on spot nodes first:                │                       │
│   │    ResourceFlavor: gpu-a100-spot (70% cheaper)    │                       │
│   └────────────────────────────────────────────────────┘                       │
│                                                                                 │
│   MULTI-CLUSTER COST OPTIMIZATION                                              │
│   ───────────────────────────────                                              │
│   Route jobs to cheapest cluster with capacity                                 │
│                                                                                 │
│   ┌────────────────────────────────────────────────────┐                       │
│   │  Cluster A (AWS): $2.50/GPU-hour                   │                       │
│   │  Cluster B (Azure): $2.80/GPU-hour                 │                       │
│   │  Cluster C (On-prem): $0.80/GPU-hour               │                       │
│   │                                                    │                       │
│   │  MultiKueue routes to Cluster C first (cheapest)   │                       │
│   │  Falls back to A, then B based on capacity         │                       │
│   └────────────────────────────────────────────────────┘                       │
│                                                                                 │
│   RIGHT-SIZING                                                                 │
│   ────────────                                                                 │
│   Match job to smallest sufficient GPU                                         │
│                                                                                 │
│   ┌────────────────────────────────────────────────────┐                       │
│   │  Job requests: 1 GPU, 40GB VRAM                    │                       │
│   │                                                    │                       │
│   │  Options:                                          │                       │
│   │    H100 (80GB) - $4.00/hr - Overkill              │                       │
│   │    A100 (80GB) - $2.50/hr - Overkill              │                       │
│   │    A100 (40GB) - $1.80/hr - Best fit ✓            │                       │
│   │    A10G (24GB) - $1.00/hr - Too small             │                       │
│   │                                                    │                       │
│   │  BudSim recommends A100-40GB                       │                       │
│   └────────────────────────────────────────────────────┘                       │
│                                                                                 │
│   MIG (MULTI-INSTANCE GPU)                                                     │
│   ────────────────────────                                                     │
│   Partition large GPUs for smaller workloads                                   │
│                                                                                 │
│   ┌────────────────────────────────────────────────────┐                       │
│   │  A100 (80GB) partitioned into:                     │                       │
│   │    ├── MIG 3g.40gb (3 instances)                  │                       │
│   │    ├── MIG 2g.20gb (2 instances)                  │                       │
│   │    └── MIG 1g.10gb (7 instances)                  │                       │
│   │                                                    │                       │
│   │  Small inference jobs use MIG slices               │                       │
│   │  Billing: proportional to slice size              │                       │
│   └────────────────────────────────────────────────────┘                       │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Part 5: Orchestration Layers

### 5.1 Orchestration Stack

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         ORCHESTRATION LAYERS                                     │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   LAYER 1: USER INTERFACE                                                       │
│   ───────────────────────                                                       │
│   ┌──────────────────────────────────────────────────────────────────────┐     │
│   │  BudAdmin UI / BudApp API                                            │     │
│   │  • Deploy model, create pipeline, deploy use case                    │     │
│   │  • View job status, schedule timeline, costs                         │     │
│   └────────────────────────────────────────────────────────────────┬─────┘     │
│                                                                    │            │
│   LAYER 2: USE CASE ORCHESTRATION                                  │            │
│   ───────────────────────────────                                  │            │
│   ┌────────────────────────────────────────────────────────────────▼─────┐     │
│   │  BudUseCases                                                         │     │
│   │  • Template resolution (RAG, Chatbot, Agent)                        │     │
│   │  • Component registry lookup                                         │     │
│   │  • Pipeline generation from template                                 │     │
│   └────────────────────────────────────────────────────────────────┬─────┘     │
│                                                                    │            │
│   LAYER 3: PIPELINE ORCHESTRATION                                  │            │
│   ───────────────────────────────                                  │            │
│   ┌────────────────────────────────────────────────────────────────▼─────┐     │
│   │  BudPipeline (Dapr Workflows)                                        │     │
│   │  • DAG execution                                                     │     │
│   │  • Step sequencing & parallel execution                              │     │
│   │  • Trigger management (cron, event, manual)                          │     │
│   │  • Non-Job step execution (API_CALL, FUNCTION, CONDITION)           │     │
│   └────────────────────────────────────────────────────────────────┬─────┘     │
│                                                                    │            │
│                                              Only JOB-type steps   │            │
│                                                                    │            │
│   LAYER 4: JOB MANAGEMENT                                          │            │
│   ───────────────────────                                          │            │
│   ┌────────────────────────────────────────────────────────────────▼─────┐     │
│   │  BudCluster                                                          │     │
│   │  • Job CRUD (create, read, update, delete)                          │     │
│   │  • Job lifecycle tracking                                            │     │
│   │  • Cost estimation & tracking                                        │     │
│   │  • Kubernetes resource generation                                    │     │
│   │  • Schedule timeline API                                             │     │
│   └────────────────────────────────────────────────────────────────┬─────┘     │
│                                                                    │            │
│   LAYER 5: ADMISSION CONTROL                                       │            │
│   ──────────────────────────                                       │            │
│   ┌────────────────────────────────────────────────────────────────▼─────┐     │
│   │  Kueue                                                               │     │
│   │  • Quota enforcement                                                 │     │
│   │  • Fair-share scheduling                                             │     │
│   │  • Priority-based admission                                          │     │
│   │  • Preemption                                                        │     │
│   │  • Multi-cluster placement (MultiKueue)                             │     │
│   └────────────────────────────────────────────────────────────────┬─────┘     │
│                                                                    │            │
│   LAYER 6: KUBERNETES SCHEDULING                                   │            │
│   ──────────────────────────────                                   │            │
│   ┌────────────────────────────────────────────────────────────────▼─────┐     │
│   │  Kubernetes Scheduler                                                │     │
│   │  • Node selection                                                    │     │
│   │  • Pod placement                                                     │     │
│   │  • Resource binding                                                  │     │
│   │  • Affinity/anti-affinity                                           │     │
│   └────────────────────────────────────────────────────────────────┬─────┘     │
│                                                                    │            │
│   LAYER 7: EXECUTION                                               │            │
│   ──────────────────                                               │            │
│   ┌────────────────────────────────────────────────────────────────▼─────┐     │
│   │  Kubelet + Container Runtime                                         │     │
│   │  • Container creation                                                │     │
│   │  • Resource enforcement (cgroups)                                    │     │
│   │  • Health monitoring                                                 │     │
│   │  • Log collection                                                    │     │
│   └──────────────────────────────────────────────────────────────────────┘     │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Who Does What?

| Component | Responsibility | Does NOT Do |
|-----------|----------------|-------------|
| **BudUseCases** | Template resolution, component lookup, pipeline generation | Job creation, scheduling |
| **BudPipeline** | DAG execution, triggers, non-Job steps, step dependencies | Resource allocation, admission |
| **BudCluster** | Job CRUD, lifecycle, cost tracking, K8s resource generation | DAG execution, quota enforcement |
| **Kueue** | Admission control, quotas, fair-share, priority, preemption | Job tracking, cost calculation |
| **K8s Scheduler** | Node selection, pod placement, resource binding | Quotas, priority queuing |
| **Kubelet** | Container execution, resource enforcement | Scheduling decisions |

### 5.3 Orchestration Flow Example

**Scenario**: User deploys Enterprise RAG use case

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│              EXAMPLE: DEPLOY ENTERPRISE RAG USE CASE                             │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   1. USER REQUEST                                                               │
│   ───────────────                                                               │
│   POST /api/usecases/deploy                                                     │
│   {                                                                             │
│     "template_id": "rag-enterprise",                                           │
│     "parameters": {                                                             │
│       "model": "llama-3.1-70b",                                                │
│       "vector_db": "qdrant",                                                   │
│       "embedding_model": "bge-large"                                           │
│     }                                                                          │
│   }                                                                             │
│                                                                                 │
│   2. BUDUSECASES: Template Resolution                                          │
│   ───────────────────────────────────                                          │
│   • Load template "rag-enterprise"                                             │
│   • Resolve components: qdrant, embedder, vllm, orchestrator                   │
│   • Generate Pipeline with 4 steps (all JOB-type for this template)           │
│   • Call BudPipeline.create_pipeline()                                         │
│                                                                                 │
│   3. BUDPIPELINE: Pipeline Execution                                           │
│   ─────────────────────────────────                                            │
│   Pipeline DAG:                                                                │
│   ┌─────────────┐                                                              │
│   │ Step 1: DB  │──┐                                                           │
│   │ (JOB:qdrant)│  │                                                           │
│   └─────────────┘  │ Parallel                                                  │
│   ┌─────────────┐  │                                                           │
│   │ Step 2: Emb │──┤                                                           │
│   │(JOB:embedder)│  │                                                           │
│   └─────────────┘  │                                                           │
│   ┌─────────────┐  │                                                           │
│   │ Step 3: LLM │──┘                                                           │
│   │ (JOB:vllm)  │                                                              │
│   └──────┬──────┘                                                              │
│          │ All complete                                                        │
│          ▼                                                                     │
│   ┌─────────────┐                                                              │
│   │ Step 4: Orch│                                                              │
│   │(JOB:langserve)│                                                             │
│   └─────────────┘                                                              │
│                                                                                 │
│   4. BUDCLUSTER: Job Creation (for each JOB-type step)                        │
│   ────────────────────────────────────────────────────                        │
│   Step 1 → Create Job {type: SERVICE, name: "qdrant-001", gpu: 0}            │
│   Step 2 → Create Job {type: SERVICE, name: "embedder-001", gpu: 1}          │
│   Step 3 → Create Job {type: SERVICE, name: "vllm-001", gpu: 4}              │
│   Step 4 → Create Job {type: SERVICE, name: "langserve-001", gpu: 0}         │
│                                                                                 │
│   For each job:                                                                │
│   • Generate K8s Deployment YAML                                               │
│   • Create Kueue Workload                                                      │
│   • Submit to cluster                                                          │
│                                                                                 │
│   5. KUEUE: Admission Control                                                  │
│   ───────────────────────────                                                  │
│   Job 1 (qdrant): CPU-only → Admitted immediately                             │
│   Job 2 (embedder): 1 GPU → Check quota → Admitted                            │
│   Job 3 (vllm): 4 GPUs → Check quota → Queued (waiting for capacity)         │
│   Job 4 (langserve): CPU-only → Admitted immediately                          │
│                                                                                 │
│   6. K8S SCHEDULER: Pod Placement                                              │
│   ───────────────────────────────                                              │
│   Job 1 → Node A (CPU node)                                                    │
│   Job 2 → Node B (1x A100 available)                                          │
│   Job 3 → Waiting... → Node C comes free → Scheduled                          │
│   Job 4 → Node A (CPU node)                                                    │
│                                                                                 │
│   7. COMPLETION                                                                │
│   ─────────────                                                                │
│   All jobs RUNNING → Pipeline marks as COMPLETED                              │
│   UseCase deployment marked as HEALTHY                                         │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Part 6: Kueue Deep Dive

### 6.1 Kueue Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           KUEUE ARCHITECTURE                                     │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │                        KUEUE CONTROLLER                                 │   │
│   │                                                                         │   │
│   │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │   │
│   │  │  Admission  │  │   Queue     │  │  Preemption │  │  Fair-share │   │   │
│   │  │  Controller │  │   Manager   │  │   Handler   │  │  Calculator │   │   │
│   │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘   │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                            │
│                                    ▼                                            │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │                         KUEUE CRDs                                      │   │
│   │                                                                         │   │
│   │  ┌───────────────────┐           ┌───────────────────┐                 │   │
│   │  │  ClusterQueue     │           │  LocalQueue       │                 │   │
│   │  │  (cluster-wide)   │◄──────────│  (per namespace)  │                 │   │
│   │  │                   │           │                   │                 │   │
│   │  │  • Quota limits   │           │  • Points to CQ   │                 │   │
│   │  │  • ResourceFlavors│           │  • User submits   │                 │   │
│   │  │  • Cohort member  │           │    workloads here │                 │   │
│   │  └───────────────────┘           └───────────────────┘                 │   │
│   │           │                                                             │   │
│   │           │                                                             │   │
│   │           ▼                                                             │   │
│   │  ┌───────────────────┐           ┌───────────────────┐                 │   │
│   │  │  ResourceFlavor   │           │  Workload         │                 │   │
│   │  │                   │           │                   │                 │   │
│   │  │  • Node labels    │           │  • Pod templates  │                 │   │
│   │  │  • Taints         │           │  • Resource reqs  │                 │   │
│   │  │  • GPU type       │           │  • Queue name     │                 │   │
│   │  └───────────────────┘           │  • Priority       │                 │   │
│   │                                  └───────────────────┘                 │   │
│   │                                                                         │   │
│   │  ┌───────────────────┐           ┌───────────────────┐                 │   │
│   │  │  Cohort           │           │WorkloadPriorityClass│                │   │
│   │  │                   │           │                   │                 │   │
│   │  │  • Groups CQs     │           │  • Priority value │                 │   │
│   │  │  • Resource share │           │  • Preemption     │                 │   │
│   │  └───────────────────┘           └───────────────────┘                 │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Kueue Configuration for Bud AI Foundry

**ResourceFlavors:**

```yaml
# GPU Flavors
apiVersion: kueue.x-k8s.io/v1beta1
kind: ResourceFlavor
metadata:
  name: gpu-h100-80gb
spec:
  nodeLabels:
    nvidia.com/gpu.product: "NVIDIA-H100-80GB-HBM3"
    node.kubernetes.io/instance-type: "p5.48xlarge"
---
apiVersion: kueue.x-k8s.io/v1beta1
kind: ResourceFlavor
metadata:
  name: gpu-a100-80gb
spec:
  nodeLabels:
    nvidia.com/gpu.product: "NVIDIA-A100-SXM4-80GB"
---
apiVersion: kueue.x-k8s.io/v1beta1
kind: ResourceFlavor
metadata:
  name: gpu-a100-40gb
spec:
  nodeLabels:
    nvidia.com/gpu.product: "NVIDIA-A100-PCIe-40GB"
---
apiVersion: kueue.x-k8s.io/v1beta1
kind: ResourceFlavor
metadata:
  name: gpu-t4
spec:
  nodeLabels:
    nvidia.com/gpu.product: "Tesla-T4"
---
# CPU-only Flavor
apiVersion: kueue.x-k8s.io/v1beta1
kind: ResourceFlavor
metadata:
  name: cpu-standard
spec:
  nodeLabels:
    node-type: "cpu-optimized"
---
# MIG Flavors
# NOTE: MIG labels use nvidia.com/mig.config (GPU Operator) to match nodes with specific MIG configuration
# The MIG profile (3g.40gb, 2g.20gb, etc.) determines available memory per slice
apiVersion: kueue.x-k8s.io/v1beta1
kind: ResourceFlavor
metadata:
  name: gpu-a100-mig-3g40gb
spec:
  nodeLabels:
    # GPU Operator label for MIG configuration (7 x 1g.10gb or 3 x 3g.40gb, etc.)
    nvidia.com/mig.config: "all-3g.40gb"
    nvidia.com/gpu.product: "NVIDIA-A100-SXM4-80GB-MIG-3g.40gb"
```

**ClusterQueue:**

```yaml
apiVersion: kueue.x-k8s.io/v1beta1
kind: ClusterQueue
metadata:
  name: gpu-cluster-queue
spec:
  cohort: production  # Fair-share group

  resourceGroups:
  - coveredResources: ["cpu", "memory", "nvidia.com/gpu"]
    flavors:
    # H100 - highest priority, limited supply
    - name: gpu-h100-80gb
      resources:
      - name: "nvidia.com/gpu"
        nominalQuota: 16
        borrowingLimit: 0  # Cannot borrow H100s
      - name: "cpu"
        nominalQuota: 256
      - name: "memory"
        nominalQuota: 2Ti

    # A100 80GB - main production
    - name: gpu-a100-80gb
      resources:
      - name: "nvidia.com/gpu"
        nominalQuota: 64
        borrowingLimit: 32  # Can borrow up to 32 more
      - name: "cpu"
        nominalQuota: 512
      - name: "memory"
        nominalQuota: 4Ti

    # A100 40GB - cost-optimized
    - name: gpu-a100-40gb
      resources:
      - name: "nvidia.com/gpu"
        nominalQuota: 32
        borrowingLimit: 16
      - name: "cpu"
        nominalQuota: 256
      - name: "memory"
        nominalQuota: 2Ti

    # T4 - inference, development
    - name: gpu-t4
      resources:
      - name: "nvidia.com/gpu"
        nominalQuota: 100
        borrowingLimit: 50
      - name: "cpu"
        nominalQuota: 400
      - name: "memory"
        nominalQuota: 3Ti

  preemption:
    reclaimWithinCohort: Any
    borrowWithinCohort:
      policy: LowerPriority
      maxPriorityThreshold: 100  # Only preempt NORMAL and below
    withinClusterQueue: LowerPriority
```

**Cohort Fair-Share Calculation:**

Kueue's cohort fair-share determines how borrowed resources are allocated among ClusterQueues:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        COHORT FAIR-SHARE ALGORITHM                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   Given Cohort "production" with:                                              │
│   - ClusterQueue A: nominalQuota=40 GPUs, weight=2                             │
│   - ClusterQueue B: nominalQuota=20 GPUs, weight=1                             │
│   - Total cohort capacity: 80 GPUs (sum of quotas + any lendable)              │
│                                                                                 │
│   Fair-Share Calculation:                                                       │
│   1. Each CQ gets guaranteed: nominalQuota (A=40, B=20)                        │
│   2. Unused capacity from one CQ can be borrowed by others                     │
│   3. Borrowing is weighted: A gets 2/(2+1)=66%, B gets 1/(2+1)=33%             │
│   4. Subject to borrowingLimit per CQ (prevents one tenant hogging all)        │
│                                                                                 │
│   Example Scenario:                                                             │
│   - CQ-A using 30/40 GPUs (10 unused)                                          │
│   - CQ-B wants 35 GPUs (15 more than quota)                                    │
│   - CQ-B can borrow: min(10 unused, borrowingLimit of B)                       │
│                                                                                 │
│   Priority Interaction:                                                         │
│   - HIGH priority in CQ-B can preempt NORMAL in CQ-A (if configured)           │
│   - CRITICAL never preempted, even for borrowing                               │
│                                                                                 │
│   Kueue Config:                                                                 │
│   - fairSharing.weight: Relative priority for borrowed resources               │
│   - borrowingLimit: Max additional resources beyond nominalQuota               │
│   - lendingLimit: Max resources this CQ will share with others                 │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**LocalQueues (per tenant):**

```yaml
apiVersion: kueue.x-k8s.io/v1beta1
kind: LocalQueue
metadata:
  name: tenant-acme-queue
  namespace: tenant-acme
spec:
  clusterQueue: gpu-cluster-queue
---
apiVersion: kueue.x-k8s.io/v1beta1
kind: LocalQueue
metadata:
  name: tenant-globex-queue
  namespace: tenant-globex
spec:
  clusterQueue: gpu-cluster-queue
```

**WorkloadPriorityClasses:**

```yaml
apiVersion: kueue.x-k8s.io/v1beta1
kind: WorkloadPriorityClass
metadata:
  name: critical
value: 1000
description: "Production endpoints - never preempted"
---
apiVersion: kueue.x-k8s.io/v1beta1
kind: WorkloadPriorityClass
metadata:
  name: high
value: 100
description: "Important workloads - rarely preempted"
---
apiVersion: kueue.x-k8s.io/v1beta1
kind: WorkloadPriorityClass
metadata:
  name: normal
value: 10
description: "Standard workloads - can be preempted"
---
apiVersion: kueue.x-k8s.io/v1beta1
kind: WorkloadPriorityClass
metadata:
  name: low
value: 1
description: "Background workloads - always preemptible"
```

### 6.3 How BudCluster Creates Kueue Workloads

```python
# BudCluster: Job to Kueue Workload mapping

def create_kueue_workload(job: Job, k8s_resource: dict) -> dict:
    """
    Create Kueue Workload wrapper for K8s resource.

    Maps Job.policy fields to Kueue primitives:
    - job.policy.priority_class → Kueue WorkloadPriorityClass
    - job.policy.queue_name → Kueue LocalQueue
    - job.intent.* → Labels for cluster selection
    """

    # Map Job priority to Kueue priority class (uses PriorityClass enum)
    priority_mapping = {
        PriorityClass.CRITICAL: "critical",
        PriorityClass.HIGH: "high",
        PriorityClass.NORMAL: "normal",
        PriorityClass.LOW: "low",
    }

    workload = {
        "apiVersion": "kueue.x-k8s.io/v1beta1",
        "kind": "Workload",
        "metadata": {
            "name": f"{job.name}-workload",
            "namespace": job.k8s_namespace,
            "labels": {
                # Identity labels
                "bud.ai/job-id": str(job.id),
                "bud.ai/job-type": job.job_type.value,
                "bud.ai/source-type": job.source_type.value,
                "bud.ai/tenant-id": str(job.tenant_id),
                "bud.ai/project-id": str(job.project_id),
                # Intent labels (for MultiKueue cluster selection)
                "bud.ai/optimization-goal": job.intent.optimization_goal.value,
                "bud.ai/workload-class": job.intent.workload_class.value,
                "bud.ai/spot-eligible": str(job.intent.spot_eligible).lower(),
            }
        },
        "spec": {
            # Policy fields mapped to Kueue spec
            "queueName": job.policy.queue_name or f"tenant-{job.tenant_id}-queue",
            "priorityClassName": priority_mapping[job.policy.priority_class],
            "podSets": extract_pod_sets(k8s_resource, job),
        }
    }

    return workload


def extract_pod_sets(k8s_resource: dict, job: Job) -> list:
    """
    Extract pod specifications for Kueue.
    """
    pod_template = k8s_resource.get("spec", {}).get("template", {})

    # Determine replica count
    if job.job_type == JobType.SERVICE:
        count = k8s_resource.get("spec", {}).get("replicas", 1)
    elif job.job_type == JobType.BATCH:
        count = k8s_resource.get("spec", {}).get("parallelism", 1)
    else:
        count = 1

    return [{
        "name": "main",
        "count": count,
        "template": pod_template,
    }]
```

### 6.4 Kueue Admission Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        KUEUE ADMISSION FLOW                                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   1. WORKLOAD SUBMITTED                                                         │
│   ─────────────────────                                                         │
│   BudCluster creates Workload CR → Kueue watches                               │
│                                                                                 │
│   2. QUEUE PLACEMENT                                                            │
│   ─────────────────                                                             │
│   Workload → LocalQueue → ClusterQueue                                         │
│                                                                                 │
│   3. ADMISSION CHECK                                                            │
│   ─────────────────                                                             │
│   ┌────────────────────────────────────────────────────────────────────┐       │
│   │  For each ResourceFlavor in ClusterQueue:                          │       │
│   │    1. Check if node labels match workload requirements             │       │
│   │    2. Check if quota available (nominalQuota - currentUsage)       │       │
│   │    3. Check if borrowing possible (borrowingLimit)                 │       │
│   │    4. Check priority vs pending workloads                          │       │
│   │                                                                    │       │
│   │  If resources available:                                           │       │
│   │    → ADMIT workload                                                │       │
│   │    → Reserve quota                                                 │       │
│   │    → Create underlying K8s resource (Deployment/Job)               │       │
│   │                                                                    │       │
│   │  If resources NOT available:                                       │       │
│   │    → Check preemption candidates                                   │       │
│   │    → If preemption possible: evict lower priority, admit           │       │
│   │    → Otherwise: QUEUE workload                                     │       │
│   └────────────────────────────────────────────────────────────────────┘       │
│                                                                                 │
│   4. STATUS UPDATE                                                              │
│   ───────────────                                                               │
│   Workload.status.conditions updated:                                          │
│   - Admitted: True/False                                                       │
│   - QuotaReserved: True/False                                                  │
│   - Evicted: True/False (if preempted)                                        │
│                                                                                 │
│   5. BUDCLUSTER SYNC                                                           │
│   ─────────────────                                                            │
│   BudCluster watches Workload status:                                          │
│   - Admitted → Job.status = ADMITTED                                           │
│   - Evicted → Job.status = PREEMPTED                                           │
│   - Pod Running → Job.status = RUNNING                                         │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Part 7: Pipeline & Step Execution

### 7.1 Step Types

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                             STEP TYPES                                           │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   RESOURCE-CONSUMING STEPS (Create Jobs)                                       │
│   ──────────────────────────────────────                                       │
│                                                                                 │
│   ┌─────────────────────────────────────────────────────────────────────────┐  │
│   │  JOB Step                                                               │  │
│   │  ────────                                                               │  │
│   │  Creates a Job in BudCluster → Scheduled by Kueue                      │  │
│   │                                                                         │  │
│   │  Config:                                                                │  │
│   │  {                                                                      │  │
│   │    "step_type": "job",                                                 │  │
│   │    "job_type": "service",      // service, batch, training             │  │
│   │    "deployment_type": "helm",  // helm, docker, model                  │  │
│   │    "helm_chart": "qdrant/qdrant",                                      │  │
│   │    "values": {...},                                                    │  │
│   │    "resources": {                                                      │  │
│   │      "gpu_type": "A100",                                               │  │
│   │      "gpu_count": 1,                                                   │  │
│   │      "memory": "32Gi"                                                  │  │
│   │    },                                                                  │  │
│   │    "wait_for_ready": true      // Wait for job to be RUNNING          │  │
│   │  }                                                                      │  │
│   └─────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
│   NON-RESOURCE STEPS (No Jobs)                                                 │
│   ────────────────────────────                                                 │
│                                                                                 │
│   ┌─────────────────────────────────────────────────────────────────────────┐  │
│   │  API_CALL Step                                                          │  │
│   │  ─────────────                                                          │  │
│   │  Makes HTTP request to external or internal service                    │  │
│   │                                                                         │  │
│   │  Config:                                                                │  │
│   │  {                                                                      │  │
│   │    "step_type": "api_call",                                            │  │
│   │    "method": "POST",                                                   │  │
│   │    "url": "https://api.example.com/webhook",                          │  │
│   │    "headers": {"Authorization": "Bearer ${SECRET}"},                  │  │
│   │    "body": {"status": "deployed"}                                     │  │
│   │  }                                                                      │  │
│   └─────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
│   ┌─────────────────────────────────────────────────────────────────────────┐  │
│   │  FUNCTION Step                                                          │  │
│   │  ─────────────                                                          │  │
│   │  Executes inline code or calls a registered function                   │  │
│   │                                                                         │  │
│   │  Config:                                                                │  │
│   │  {                                                                      │  │
│   │    "step_type": "function",                                            │  │
│   │    "function_name": "validate_deployment",                             │  │
│   │    "parameters": {"endpoint_url": "${steps.deploy_llm.endpoint}"}     │  │
│   │  }                                                                      │  │
│   └─────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
│   ┌─────────────────────────────────────────────────────────────────────────┐  │
│   │  NOTIFICATION Step                                                      │  │
│   │  ─────────────────                                                      │  │
│   │  Sends notification via BudNotify (email, Slack, webhook)              │  │
│   │                                                                         │  │
│   │  Config:                                                                │  │
│   │  {                                                                      │  │
│   │    "step_type": "notification",                                        │  │
│   │    "channel": "slack",                                                 │  │
│   │    "template": "deployment_complete",                                  │  │
│   │    "recipients": ["#deployments"],                                    │  │
│   │    "data": {"usecase": "${usecase.name}", "status": "healthy"}        │  │
│   │  }                                                                      │  │
│   └─────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
│   CONTROL FLOW STEPS (No Jobs)                                                 │
│   ────────────────────────────                                                 │
│                                                                                 │
│   ┌─────────────────────────────────────────────────────────────────────────┐  │
│   │  CONDITION Step                                                         │  │
│   │  ──────────────                                                         │  │
│   │  Conditional branching based on expression                             │  │
│   │                                                                         │  │
│   │  Config:                                                                │  │
│   │  {                                                                      │  │
│   │    "step_type": "condition",                                           │  │
│   │    "expression": "${steps.validate.result} == 'valid'",               │  │
│   │    "if_true": "deploy_production",                                     │  │
│   │    "if_false": "notify_failure"                                       │  │
│   │  }                                                                      │  │
│   └─────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
│   ┌─────────────────────────────────────────────────────────────────────────┐  │
│   │  WAIT Step                                                              │  │
│   │  ─────────                                                              │  │
│   │  Wait for duration or condition                                        │  │
│   │                                                                         │  │
│   │  Config:                                                                │  │
│   │  {                                                                      │  │
│   │    "step_type": "wait",                                                │  │
│   │    "duration": "5m",           // Fixed duration                       │  │
│   │    // OR                                                               │  │
│   │    "condition": "${job.health_check} == 'passing'",                   │  │
│   │    "timeout": "10m",                                                   │  │
│   │    "poll_interval": "30s"                                             │  │
│   │  }                                                                      │  │
│   └─────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
│   ┌─────────────────────────────────────────────────────────────────────────┐  │
│   │  PARALLEL Step                                                          │  │
│   │  ─────────────                                                          │  │
│   │  Execute multiple steps in parallel                                    │  │
│   │                                                                         │  │
│   │  Config:                                                                │  │
│   │  {                                                                      │  │
│   │    "step_type": "parallel",                                            │  │
│   │    "branches": ["deploy_db", "deploy_embedder", "deploy_llm"],        │  │
│   │    "fail_fast": true           // Stop all if one fails               │  │
│   │  }                                                                      │  │
│   └─────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
│   ┌─────────────────────────────────────────────────────────────────────────┐  │
│   │  LOOP Step                                                              │  │
│   │  ─────────                                                              │  │
│   │  Repeat steps for each item or until condition                         │  │
│   │                                                                         │  │
│   │  Config:                                                                │  │
│   │  {                                                                      │  │
│   │    "step_type": "loop",                                                │  │
│   │    "items": ["region-us", "region-eu", "region-asia"],                │  │
│   │    "variable": "region",                                               │  │
│   │    "body_step": "deploy_to_region",                                   │  │
│   │    "max_parallel": 3           // Run 3 at a time                      │  │
│   │  }                                                                      │  │
│   └─────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 Pipeline Schema

```python
class StepType(str, Enum):
    # Resource-consuming (creates Job)
    JOB = "job"

    # Non-resource (no Job)
    API_CALL = "api_call"
    FUNCTION = "function"
    NOTIFICATION = "notification"

    # Control flow (no Job)
    CONDITION = "condition"
    WAIT = "wait"
    PARALLEL = "parallel"
    LOOP = "loop"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class PipelineStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Pipeline(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str
    description: Optional[str]

    # Ownership
    project_id: UUID
    tenant_id: UUID
    created_by: UUID

    # Source (if from UseCase)
    usecase_deployment_id: Optional[UUID]

    # Execution
    status: PipelineStatus = PipelineStatus.PENDING
    current_step_id: Optional[UUID]

    # Timestamps
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Step(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    pipeline_id: UUID = Field(foreign_key="pipeline.id")

    name: str
    step_type: StepType
    config: dict = Field(default_factory=dict)  # Type-specific config

    # Dependencies
    depends_on: List[UUID] = Field(default_factory=list)  # Step IDs

    # Execution
    status: StepStatus = StepStatus.PENDING
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    # Result
    output: Optional[dict]  # Step output for downstream steps
    error: Optional[str]

    # Job reference (only for JOB-type steps)
    job_id: Optional[UUID]  # References Job in BudCluster
```

> **Step Referencing Convention:**
> - `depends_on` uses **Step UUIDs**, not step names
> - Step names are for human readability; UUIDs ensure correctness
> - When defining pipelines in YAML/JSON, use step names - BudPipeline resolves to IDs
>
> **Inter-Job Dependencies:**
> Jobs do NOT have a `depends_on` field. Job dependencies are expressed through Pipeline DAGs:
> - Job A must complete before Job B → Create Pipeline with Step A (JOB) → Step B (JOB)
> - For ad-hoc dependencies, use Pipeline triggers with `trigger_type: DEPENDENCY`

### 7.3 DAG Execution Engine

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        DAG EXECUTION ENGINE                                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   BUDPIPELINE (Dapr Workflow)                                                   │
│   ───────────────────────────                                                   │
│                                                                                 │
│   @workflow                                                                     │
│   async def execute_pipeline(ctx: WorkflowContext, pipeline_id: UUID):         │
│       """                                                                       │
│       Execute pipeline DAG using Dapr Workflows for durability.                │
│       """                                                                       │
│       pipeline = await ctx.call_activity(load_pipeline, pipeline_id)           │
│       steps = build_dag(pipeline.steps)                                        │
│                                                                                 │
│       # Track completed steps                                                   │
│       completed = set()                                                         │
│                                                                                 │
│       while not all_completed(steps, completed):                               │
│           # Find steps ready to execute (deps satisfied)                        │
│           ready = get_ready_steps(steps, completed)                            │
│                                                                                 │
│           # Execute ready steps in parallel                                     │
│           tasks = [execute_step(ctx, step) for step in ready]                  │
│           results = await asyncio.gather(*tasks)                               │
│                                                                                 │
│           # Update completed set                                                │
│           for step, result in zip(ready, results):                             │
│               completed.add(step.id)                                           │
│               step.output = result                                             │
│                                                                                 │
│       return {"status": "completed", "steps": len(completed)}                  │
│                                                                                 │
│                                                                                 │
│   @activity                                                                     │
│   async def execute_step(ctx: ActivityContext, step: Step):                    │
│       """                                                                       │
│       Execute a single step based on its type.                                 │
│       """                                                                       │
│       match step.step_type:                                                    │
│           case StepType.JOB:                                                   │
│               # Create Job via BudCluster                                      │
│               job = await budcluster_client.create_job(                        │
│                   job_type=step.config["job_type"],                           │
│                   deployment_type=step.config["deployment_type"],             │
│                   resources=step.config["resources"],                         │
│                   source_type=SourceType.PIPELINE,                            │
│                   source_id=step.pipeline_id,                                 │
│                   step_id=step.id,                                            │
│               )                                                                │
│               # Wait for job to reach target state                             │
│               if step.config.get("wait_for_ready", True):                     │
│                   await wait_for_job_ready(job.id)                            │
│               return {"job_id": str(job.id), "status": job.status}            │
│                                                                                 │
│           case StepType.API_CALL:                                              │
│               response = await http_client.request(                            │
│                   method=step.config["method"],                               │
│                   url=step.config["url"],                                     │
│                   headers=step.config.get("headers"),                         │
│                   json=step.config.get("body"),                               │
│               )                                                                │
│               return {"status_code": response.status, "body": response.json()} │
│                                                                                 │
│           case StepType.FUNCTION:                                              │
│               func = get_registered_function(step.config["function_name"])    │
│               return await func(**step.config.get("parameters", {}))          │
│                                                                                 │
│           case StepType.NOTIFICATION:                                          │
│               await budnotify_client.send(                                    │
│                   channel=step.config["channel"],                             │
│                   template=step.config["template"],                           │
│                   data=step.config["data"],                                   │
│               )                                                                │
│               return {"sent": True}                                            │
│                                                                                 │
│           case StepType.WAIT:                                                  │
│               if "duration" in step.config:                                   │
│                   await asyncio.sleep(parse_duration(step.config["duration"]))│
│               else:                                                            │
│                   await wait_for_condition(step.config["condition"])          │
│               return {"waited": True}                                          │
│                                                                                 │
│           case StepType.CONDITION:                                             │
│               result = evaluate_expression(step.config["expression"])         │
│               next_step = step.config["if_true" if result else "if_false"]   │
│               return {"branch": next_step, "condition_result": result}        │
│                                                                                 │
│           case StepType.PARALLEL:                                              │
│               # Parallel handled by DAG engine, not here                       │
│               return {"parallel": True}                                        │
│                                                                                 │
│           case StepType.LOOP:                                                  │
│               # Loop handled by DAG engine expansion                           │
│               return {"loop": True}                                            │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Part 8: Multi-Cluster Scheduling

### 8.1 MultiKueue Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        MULTI-CLUSTER SCHEDULING                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │                    MANAGEMENT CLUSTER                                   │   │
│   │                                                                         │   │
│   │   ┌─────────────────────────────────────────────────────────────────┐   │   │
│   │   │  BudCluster                                                     │   │   │
│   │   │  • Multi-cluster awareness                                      │   │   │
│   │   │  • Cluster selection logic                                      │   │   │
│   │   │  • Aggregated Job view                                          │   │   │
│   │   └─────────────────────────────────────────────────────────────────┘   │   │
│   │                              │                                          │   │
│   │                              ▼                                          │   │
│   │   ┌─────────────────────────────────────────────────────────────────┐   │   │
│   │   │  MultiKueue Controller                                          │   │   │
│   │   │  • Workload distribution                                        │   │   │
│   │   │  • Capacity aggregation                                         │   │   │
│   │   │  • Cross-cluster fair-share                                     │   │   │
│   │   └─────────────────────────────────────────────────────────────────┘   │   │
│   │                              │                                          │   │
│   └──────────────────────────────┼──────────────────────────────────────────┘   │
│                                  │                                              │
│            ┌─────────────────────┼─────────────────────┐                       │
│            │                     │                     │                       │
│            ▼                     ▼                     ▼                       │
│   ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐             │
│   │  CLUSTER A      │   │  CLUSTER B      │   │  CLUSTER C      │             │
│   │  (AWS EKS)      │   │  (Azure AKS)    │   │  (On-premises)  │             │
│   │                 │   │                 │   │                 │             │
│   │  GPU: 64 A100   │   │  GPU: 32 H100   │   │  GPU: 128 A100  │             │
│   │  Cost: $2.50/hr │   │  Cost: $4.00/hr │   │  Cost: $0.80/hr │             │
│   │                 │   │                 │   │                 │             │
│   │  Kueue          │   │  Kueue          │   │  Kueue          │             │
│   │  ├─ ClusterQ    │   │  ├─ ClusterQ    │   │  ├─ ClusterQ    │             │
│   │  └─ LocalQs     │   │  └─ LocalQs     │   │  └─ LocalQs     │             │
│   └─────────────────┘   └─────────────────┘   └─────────────────┘             │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 8.2 Cluster Selection Logic

```python
class ClusterSelector:
    """
    Selects optimal cluster for job placement.
    """

    async def select_cluster(self, job: Job) -> Cluster:
        """
        Select cluster based on:
        1. Resource availability
        2. Cost optimization
        3. Latency requirements
        4. Data locality
        5. Compliance requirements
        """
        candidates = await self.get_candidate_clusters(job)

        if not candidates:
            raise NoClusterAvailableError(job)

        # Score each cluster
        scored = []
        for cluster in candidates:
            score = await self.calculate_score(cluster, job)
            scored.append((cluster, score))

        # Sort by score (higher is better)
        scored.sort(key=lambda x: x[1], reverse=True)

        return scored[0][0]

    async def get_candidate_clusters(self, job: Job) -> List[Cluster]:
        """Filter clusters that CAN run the job."""
        all_clusters = await cluster_repo.get_active_clusters(
            tenant_id=job.tenant_id
        )

        candidates = []
        for cluster in all_clusters:
            # Check GPU type availability
            if job.gpu_type and job.gpu_type not in cluster.available_gpu_types:
                continue

            # Check quota availability
            quota = await kueue_client.get_available_quota(
                cluster_id=cluster.id,
                tenant_id=job.tenant_id,
                gpu_type=job.gpu_type,
            )
            if quota < job.gpu_count:
                continue

            # Check compliance (e.g., data residency)
            if job.labels.get("compliance") == "eu-only":
                if cluster.region not in EU_REGIONS:
                    continue

            candidates.append(cluster)

        return candidates

    async def calculate_score(self, cluster: Cluster, job: Job) -> float:
        """
        Score cluster for job placement.
        Higher score = better choice.
        """
        score = 0.0

        # Cost factor (weight: 40%)
        cost_per_hour = cluster.get_cost_per_gpu_hour(job.gpu_type)
        max_cost = 5.0  # Normalize against max expected cost
        cost_score = (max_cost - cost_per_hour) / max_cost
        score += cost_score * 0.4

        # Availability factor (weight: 30%)
        available = await kueue_client.get_available_quota(
            cluster_id=cluster.id,
            tenant_id=job.tenant_id,
            gpu_type=job.gpu_type,
        )
        availability_score = min(available / 10, 1.0)  # Cap at 10 GPUs
        score += availability_score * 0.3

        # Latency factor (weight: 20%)
        if job.labels.get("latency_sensitive"):
            latency_ms = cluster.estimated_latency_ms
            latency_score = max(0, (100 - latency_ms) / 100)
            score += latency_score * 0.2
        else:
            score += 0.2  # Full score if not latency sensitive

        # Utilization factor (weight: 10%) - prefer less loaded clusters
        utilization = cluster.current_gpu_utilization
        utilization_score = 1 - utilization
        score += utilization_score * 0.1

        return score
```

### 8.3 MultiKueue Configuration

```yaml
# AdmissionCheck for multi-cluster
apiVersion: kueue.x-k8s.io/v1beta1
kind: AdmissionCheck
metadata:
  name: multi-cluster-placement
spec:
  controllerName: "kueue.x-k8s.io/multikueue"
  parameters:
    apiGroup: kueue.x-k8s.io
    kind: MultiKueueConfig
    name: bud-multikueue-config
---
# MultiKueue Configuration
apiVersion: kueue.x-k8s.io/v1alpha1
kind: MultiKueueConfig
metadata:
  name: bud-multikueue-config
spec:
  clusters:
  - name: cluster-aws
    kubeConfig:
      secretRef:
        name: cluster-aws-kubeconfig
        namespace: bud-system
  - name: cluster-azure
    kubeConfig:
      secretRef:
        name: cluster-azure-kubeconfig
        namespace: bud-system
  - name: cluster-onprem
    kubeConfig:
      secretRef:
        name: cluster-onprem-kubeconfig
        namespace: bud-system
---
# ClusterQueue with MultiKueue
apiVersion: kueue.x-k8s.io/v1beta1
kind: ClusterQueue
metadata:
  name: multi-cluster-gpu-queue
spec:
  admissionChecks:
  - multi-cluster-placement
  resourceGroups:
  - coveredResources: ["nvidia.com/gpu"]
    flavors:
    - name: gpu-a100
      resources:
      - name: "nvidia.com/gpu"
        nominalQuota: 224  # Sum of all clusters
```

---

## Part 9: Job Lifecycle Management

### 9.1 Complete Lifecycle Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        JOB LIFECYCLE MANAGEMENT                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   1. CREATION                                                                   │
│   ───────────                                                                   │
│   Source (BudApp/BudPipeline/BudUseCases) → BudCluster.create_job()            │
│                                                                                 │
│   • Validate request                                                            │
│   • Estimate cost (via BudSim or heuristics)                                   │
│   • Create Job record (status: PENDING)                                        │
│   • Select target cluster (if multi-cluster)                                   │
│   • Return Job ID                                                               │
│                                                                                 │
│   2. SUBMISSION                                                                 │
│   ────────────                                                                  │
│   BudCluster → Kubernetes                                                       │
│                                                                                 │
│   • Generate K8s resource YAML (Deployment/Job/StatefulSet)                    │
│   • Create Kueue Workload wrapper                                              │
│   • Submit to cluster                                                           │
│   • Update Job status: QUEUED                                                  │
│                                                                                 │
│   3. ADMISSION                                                                  │
│   ────────────                                                                  │
│   Kueue Admission Controller                                                   │
│                                                                                 │
│   • Check quota availability                                                    │
│   • Check priority vs pending workloads                                        │
│   • Reserve quota                                                               │
│   • Mark Workload as admitted                                                  │
│   • BudCluster watches → Update Job status: ADMITTED                           │
│                                                                                 │
│   4. SCHEDULING                                                                 │
│   ─────────────                                                                 │
│   Kubernetes Scheduler                                                          │
│                                                                                 │
│   • Select node with matching resources                                        │
│   • Bind pod to node                                                            │
│   • Kubelet pulls image, creates container                                     │
│   • BudCluster watches → Update Job status: RUNNING                            │
│   • Record actual_start timestamp                                              │
│                                                                                 │
│   5. EXECUTION                                                                  │
│   ───────────                                                                   │
│   Container Runtime                                                             │
│                                                                                 │
│   • Container runs workload                                                     │
│   • BudMetrics collects resource usage                                         │
│   • Health checks monitored (for SERVICE)                                      │
│   • Progress tracked (for TRAINING)                                            │
│                                                                                 │
│   6. COMPLETION                                                                 │
│   ────────────                                                                  │
│   Kubernetes → BudCluster                                                       │
│                                                                                 │
│   • Container exits (BATCH/TRAINING) or is stopped (SERVICE)                   │
│   • BudCluster watches:                                                        │
│     - Exit code 0 → SUCCEEDED                                                  │
│     - Exit code != 0 → FAILED (may retry)                                     │
│     - User delete → CANCELLED                                                  │
│     - Preemption → PREEMPTED (may retry)                                      │
│   • Record actual_end timestamp                                                │
│   • Calculate actual_cost                                                      │
│   • Release Kueue quota                                                         │
│                                                                                 │
│   7. CLEANUP                                                                    │
│   ──────────                                                                    │
│   BudCluster housekeeping                                                       │
│                                                                                 │
│   • Delete K8s resources (if not persistent)                                   │
│   • Archive logs to object storage                                             │
│   • Update BudMetrics with final costs                                         │
│   • Notify source (Pipeline step, etc.)                                        │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 9.2 Job Status Sync

```python
class JobStatusSyncer:
    """
    Syncs Job status with Kubernetes resources.
    Runs as background task in BudCluster.
    """

    async def sync_job_status(self, job: Job):
        """
        Watch Kubernetes and Kueue resources, update Job status.
        """
        # Get Kueue Workload status
        workload = await kueue_client.get_workload(
            namespace=job.k8s_namespace,
            name=job.kueue_workload_name,
        )

        # Get K8s resource status
        k8s_resource = await k8s_client.get_resource(
            namespace=job.k8s_namespace,
            kind=job.k8s_resource_type,
            name=job.k8s_resource_name,
        )

        # Determine new status
        new_status = self.determine_status(job, workload, k8s_resource)

        if new_status != job.status:
            await self.update_job_status(job, new_status)

    def determine_status(
        self,
        job: Job,
        workload: dict,
        k8s_resource: dict
    ) -> JobStatus:
        """
        Determine Job status from K8s/Kueue state.
        """
        # Check Kueue Workload conditions
        conditions = workload.get("status", {}).get("conditions", [])

        for cond in conditions:
            if cond["type"] == "Evicted" and cond["status"] == "True":
                return JobStatus.PREEMPTED
            if cond["type"] == "Admitted" and cond["status"] == "True":
                # Admitted, check K8s resource
                pass
            if cond["type"] == "Admitted" and cond["status"] == "False":
                return JobStatus.QUEUED

        # Check K8s resource status
        if job.job_type == JobType.SERVICE:
            return self.determine_deployment_status(k8s_resource)
        elif job.job_type in [JobType.BATCH, JobType.TRAINING]:
            return self.determine_k8s_job_status(k8s_resource)

        return job.status  # No change

    def determine_deployment_status(self, deployment: dict) -> JobStatus:
        """Determine status from K8s Deployment."""
        status = deployment.get("status", {})

        available = status.get("availableReplicas", 0)
        desired = deployment["spec"]["replicas"]

        if available >= desired:
            return JobStatus.RUNNING
        elif status.get("unavailableReplicas", 0) > 0:
            # Check if it's starting up or failing
            conditions = status.get("conditions", [])
            for cond in conditions:
                if cond["type"] == "Progressing":
                    if cond["reason"] == "NewReplicaSetAvailable":
                        return JobStatus.RUNNING
            return JobStatus.ADMITTED  # Still starting

        return JobStatus.ADMITTED

    def determine_k8s_job_status(self, k8s_job: dict) -> JobStatus:
        """Determine status from K8s Job."""
        status = k8s_job.get("status", {})

        if status.get("succeeded", 0) > 0:
            return JobStatus.SUCCEEDED
        if status.get("failed", 0) > 0:
            return JobStatus.FAILED
        if status.get("active", 0) > 0:
            return JobStatus.RUNNING

        return JobStatus.ADMITTED
```

### 9.2.1 Job Reconciliation on Startup

When BudCluster starts (or recovers from a crash), it must reconcile its database state with Kubernetes. This handles the case where BudCluster was down while K8s continued running jobs.

```python
class JobReconciler:
    """
    Reconciles Job table with Kubernetes state.
    Runs on BudCluster startup and periodically (every 5 minutes).

    Principles:
    - K8s is source of truth for RUNNING state
    - DB is source of truth for metadata (source_type, tenant_id, etc.)
    - Idempotency key prevents duplicate job creation
    """

    def __init__(self, job_repo: JobRepository, k8s_client: K8sClient):
        self.job_repo = job_repo
        self.k8s_client = k8s_client

    async def reconcile_all_clusters(self):
        """
        Reconcile jobs across all managed clusters.
        Called on BudCluster startup.
        """
        clusters = await cluster_repo.get_all_active()

        for cluster in clusters:
            try:
                await self.reconcile_cluster(cluster.id)
            except Exception as e:
                logger.error(f"Reconciliation failed for cluster {cluster.id}: {e}")
                # Continue with other clusters

    async def reconcile_cluster(self, cluster_id: UUID):
        """
        Reconcile jobs for a single cluster.
        """
        # 1. Get all Jobs in non-terminal state from DB
        active_jobs = await self.job_repo.get_active_jobs(cluster_id)

        for job in active_jobs:
            await self.reconcile_job(job)

        # 2. Find orphaned K8s resources (resources without Job records)
        await self.cleanup_orphaned_resources(cluster_id)

    async def reconcile_job(self, job: Job):
        """
        Reconcile a single job with K8s state.
        """
        # Check if K8s resource exists
        k8s_resource = await self.k8s_client.get_resource(
            namespace=job.k8s_namespace,
            kind=job.k8s_resource_type,
            name=job.k8s_resource_name,
        )

        # Check if Kueue workload exists
        workload = await self.k8s_client.get_kueue_workload(
            namespace=job.k8s_namespace,
            name=job.kueue_workload_name,
        )

        if k8s_resource is None and workload is None:
            # Both gone - mark job as failed (likely deleted externally)
            await self.job_repo.update_status(
                job.id,
                JobStatus.FAILED,
                reason="Resource not found during reconciliation (deleted externally?)"
            )
            logger.warning(f"Job {job.id} marked FAILED - K8s resources missing")

        elif k8s_resource is None and workload is not None:
            # Workload exists but K8s resource missing - check workload status
            workload_status = self.get_workload_status(workload)
            if workload_status == "Admitted":
                # Should have K8s resource but doesn't - recreate
                logger.info(f"Recreating K8s resource for job {job.id}")
                await self.recreate_k8s_resource(job)
            else:
                # Still queued - sync status
                await self.job_repo.update_status(job.id, JobStatus.QUEUED)

        else:
            # Resource exists - sync status from K8s
            new_status = self.determine_status_from_k8s(job, k8s_resource, workload)
            if new_status != job.status:
                await self.job_repo.update_status(job.id, new_status)
                logger.info(f"Job {job.id} status synced: {job.status} -> {new_status}")

    async def cleanup_orphaned_resources(self, cluster_id: UUID):
        """
        Find and clean up K8s resources that have no corresponding Job record.
        Only cleans resources with bud.ai/job-id label.
        """
        # List all resources with bud.ai label
        resources = await self.k8s_client.list_resources_with_label(
            label_selector="bud.ai/job-id",
        )

        for resource in resources:
            job_id = resource.metadata.labels.get("bud.ai/job-id")
            job = await self.job_repo.get(UUID(job_id))

            if job is None:
                # Orphaned resource - delete it
                logger.warning(f"Deleting orphaned resource {resource.metadata.name}")
                await self.k8s_client.delete_resource(resource)
```

**Reconciliation Schedule:**
- **On startup**: Full reconciliation of all clusters
- **Every 5 minutes**: Incremental reconciliation of active jobs
- **On cluster reconnect**: Full reconciliation of that cluster

### 9.2.2 Idempotent Job Creation

To prevent duplicate job creation during failures or retries, use the `idempotency_key` field:

```python
async def create_job(self, request: JobCreateRequest) -> Job:
    """
    Create a job with idempotency guarantee.

    If idempotency_key is provided and a job with that key already exists,
    return the existing job instead of creating a duplicate.
    """
    if request.idempotency_key:
        # Check for existing job with same idempotency key
        existing = await self.job_repo.get_by_idempotency_key(
            request.idempotency_key
        )
        if existing:
            logger.info(f"Returning existing job {existing.id} for idempotency_key")
            return existing

    # Create new job
    job = Job(
        id=uuid4(),
        idempotency_key=request.idempotency_key,
        # ... other fields
    )

    await self.job_repo.create(job)
    return job
```

**Idempotency Key Guidelines:**
- Pipeline steps should use: `f"pipeline-{pipeline_id}-step-{step_id}-run-{run_id}"`
- UseCase deployments should use: `f"usecase-{deployment_id}-component-{component_name}"`
- Direct API calls should provide client-generated UUID

### 9.3 Retry and Recovery

```python
class JobRetryHandler:
    """
    Handles job retries and recovery.
    """

    async def handle_job_failure(self, job: Job, reason: str):
        """
        Handle job failure - decide whether to retry.
        """
        if job.retry_count >= job.max_retries:
            # Max retries exceeded
            await self.mark_job_failed(job, f"Max retries exceeded: {reason}")
            return

        if self.is_retryable_error(reason):
            await self.retry_job(job, reason)
        else:
            await self.mark_job_failed(job, reason)

    def is_retryable_error(self, reason: str) -> bool:
        """Determine if error is retryable."""
        retryable_reasons = [
            "OOMKilled",           # Out of memory - may work with different node
            "Preempted",           # Preempted by higher priority
            "NodeNotReady",        # Node failure
            "ImagePullBackOff",    # Transient registry issue
            "ContainerCreating",   # Timeout during creation
        ]
        return any(r in reason for r in retryable_reasons)

    async def retry_job(self, job: Job, reason: str):
        """Retry a failed job."""
        job.retry_count += 1
        job.status = JobStatus.PENDING
        job.status_message = f"Retry {job.retry_count}/{job.max_retries}: {reason}"

        await job_repo.update(job)

        # Resubmit to Kueue
        await self.submit_job(job)

    async def handle_preemption(self, job: Job):
        """
        Handle preempted job.
        For TRAINING jobs, save checkpoint first.
        """
        if job.job_type == JobType.TRAINING:
            # Signal container to save checkpoint
            await self.signal_checkpoint(job)
            # Wait for checkpoint completion
            await self.wait_for_checkpoint(job, timeout=300)

        # Mark as preempted
        job.status = JobStatus.PREEMPTED
        await job_repo.update(job)

        # Retry will be handled by retry handler
        await self.handle_job_failure(job, "Preempted")
```

### 9.4 Edge Cases and Operational Considerations

#### 9.4.1 Cluster Removal with Running Jobs

When a cluster is being removed or decommissioned while jobs are running:

```python
async def handle_cluster_removal(cluster_id: UUID, force: bool = False):
    """
    Handle cluster removal safely.

    Modes:
    - force=False (default): Drain gracefully, migrate if possible
    - force=True: Immediate termination, jobs marked as FAILED
    """
    jobs = await get_jobs_by_cluster(cluster_id, status=[RUNNING, QUEUED, ADMITTED])

    if not force:
        # 1. Stop new admissions (mark cluster as draining)
        await mark_cluster_draining(cluster_id)

        # 2. For each running job, attempt migration or wait for completion
        for job in jobs:
            if job.job_type == JobType.SERVICE:
                # SERVICE: Try to migrate to another cluster
                await attempt_service_migration(job)
            elif job.job_type == JobType.TRAINING:
                # TRAINING: Trigger checkpoint, then migrate
                await signal_checkpoint(job)
                await wait_for_checkpoint(job, timeout=300)
                await migrate_training_job(job)
            else:
                # BATCH: Wait for completion (up to max_runtime)
                await wait_for_completion(job, timeout=job.policy.max_runtime)
    else:
        # Force mode: Mark all jobs as FAILED
        for job in jobs:
            job.status = JobStatus.FAILED
            job.status_message = f"Cluster {cluster_id} removed forcefully"
            await job_repo.update(job)

    # 3. Delete Kueue resources
    await cleanup_kueue_resources(cluster_id)
```

#### 9.4.2 Quota Exhaustion in Parallel Steps

When a Pipeline has parallel steps that together exceed available quota:

```python
class ParallelStepQuotaHandler:
    """
    Handles quota exhaustion when parallel Pipeline steps compete for resources.
    """

    async def execute_parallel_steps(self, steps: List[Step]):
        """
        Execute parallel steps with quota awareness.

        Strategy:
        1. Pre-calculate total resource requirements
        2. If exceeds quota, serialize execution (priority order)
        3. If fits quota, execute in parallel
        """
        total_required = sum_resources(steps)
        available_quota = await get_available_quota(steps[0].pipeline.cluster_id)

        if total_required > available_quota:
            # Serialize: execute highest priority first
            sorted_steps = sorted(steps,
                key=lambda s: priority_value(s.config.get("priority_class", "normal")),
                reverse=True
            )
            for step in sorted_steps:
                await self.execute_step(step)  # Sequential
        else:
            # Parallel execution
            await asyncio.gather(*[self.execute_step(s) for s in steps])
```

#### 9.4.3 Orphaned Workload Cleanup

Kueue Workloads can become orphaned if BudCluster crashes during job creation:

```python
class OrphanedWorkloadCleaner:
    """
    Periodically cleans up orphaned Kueue Workloads.

    A Workload is orphaned if:
    - It exists in Kueue but no corresponding Job exists in BudCluster DB
    - OR the Job exists but has been in terminal state > 24 hours
    """

    async def cleanup_orphaned_workloads(self, cluster_id: UUID):
        # Get all Workloads with bud.ai/job-id label
        workloads = await k8s_client.list_workloads(
            namespace="*",
            label_selector="bud.ai/job-id"
        )

        for workload in workloads:
            job_id = workload.metadata.labels.get("bud.ai/job-id")
            job = await job_repo.get_by_id(job_id)

            if job is None:
                # No corresponding Job - delete Workload
                await k8s_client.delete_workload(workload)
                log.warning(f"Deleted orphaned Workload: {workload.metadata.name}")

            elif job.status in TERMINAL_STATES:
                age = datetime.utcnow() - job.updated_at
                if age > timedelta(hours=24):
                    await k8s_client.delete_workload(workload)
                    log.info(f"Cleaned up stale Workload for terminal job: {job.id}")
```

#### 9.4.4 Cost Estimation Feedback Loop

Improve cost estimates based on actual job costs:

```python
class CostEstimationFeedback:
    """
    Improves cost estimates by learning from actual job costs.
    """

    async def record_actual_cost(self, job: Job):
        """Record actual cost when job completes."""
        if job.actual_cost and job.estimated_cost:
            error = (job.actual_cost - job.estimated_cost) / job.estimated_cost

            # Store for model improvement
            await cost_feedback_repo.create({
                "job_type": job.job_type,
                "gpu_type": job.gpu_type,
                "gpu_count": job.gpu_count,
                "duration_seconds": (job.actual_end - job.actual_start).total_seconds(),
                "estimated_cost": job.estimated_cost,
                "actual_cost": job.actual_cost,
                "estimation_error": error,
                "cluster_id": job.cluster_id,
            })

            # If error > 20%, trigger BudSim model retraining
            if abs(error) > 0.20:
                await budsim_client.request_model_update(
                    job_type=job.job_type,
                    gpu_type=job.gpu_type
                )
```

#### 9.4.5 Multi-Tenant Isolation

Ensure strict tenant isolation at job and queue level:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        MULTI-TENANT ISOLATION                                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   NAMESPACE ISOLATION                                                           │
│   ───────────────────                                                           │
│   Each tenant gets dedicated K8s namespace(s):                                 │
│   - tenant-acme-prod                                                           │
│   - tenant-acme-dev                                                            │
│   - tenant-beta-prod                                                           │
│                                                                                 │
│   QUEUE ISOLATION                                                               │
│   ───────────────                                                               │
│   Each tenant has dedicated LocalQueues with guaranteed quotas:                │
│   ┌─────────────────────────────────────────────────────────────────┐          │
│   │  ClusterQueue: production-gpu-queue                             │          │
│   │  ├── LocalQueue: tenant-acme-queue (quota: 20 A100 GPUs)       │          │
│   │  ├── LocalQueue: tenant-beta-queue (quota: 10 A100 GPUs)       │          │
│   │  └── Cohort borrowing: enabled (share unused capacity)        │          │
│   └─────────────────────────────────────────────────────────────────┘          │
│                                                                                 │
│   NETWORK ISOLATION                                                             │
│   ─────────────────                                                             │
│   NetworkPolicies restrict cross-tenant communication:                         │
│   - Jobs can only access services in same tenant namespace                     │
│   - External egress controlled per tenant policy                               │
│                                                                                 │
│   DATA ISOLATION                                                                │
│   ──────────────                                                                │
│   - PVCs scoped to tenant namespace                                            │
│   - S3/blob storage uses tenant-specific prefixes                              │
│   - Secrets encrypted with tenant-specific keys                                │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

#### 9.4.6 TRAINING Timeout with Checkpoint Interaction

When a TRAINING job exceeds its deadline or max_runtime:

```python
async def handle_training_timeout(job: Job, reason: str):
    """
    Handle TRAINING job timeout gracefully.

    Unlike BATCH jobs which just fail, TRAINING jobs:
    1. Attempt to save final checkpoint
    2. Record checkpoint location
    3. Mark as FAILED with checkpoint info (allows manual resume)
    """
    if job.job_type != JobType.TRAINING:
        await mark_job_failed(job, reason)
        return

    # 1. Signal checkpoint (with short timeout - job is being killed)
    try:
        await signal_checkpoint(job)
        checkpoint_saved = await wait_for_checkpoint(job, timeout=60)
    except TimeoutError:
        checkpoint_saved = False

    # 2. Find latest checkpoint
    checkpoint_info = await get_latest_checkpoint(job)

    # 3. Mark as failed with checkpoint info
    job.status = JobStatus.FAILED
    job.status_message = f"Timeout: {reason}"
    if checkpoint_info:
        job.annotations["last_checkpoint"] = checkpoint_info["path"]
        job.annotations["checkpoint_step"] = checkpoint_info["step"]
        job.annotations["resume_command"] = f"budctl job resume {job.id}"

    await job_repo.update(job)

    # 4. Notify user
    await send_notification(
        channel="email",
        template="training_timeout",
        data={
            "job_name": job.name,
            "reason": reason,
            "checkpoint_available": checkpoint_saved,
            "resume_info": job.annotations.get("resume_command"),
        }
    )
```

#### 9.4.7 Multi-GPU Topology Failure Handling

When a multi-GPU job with topology constraints cannot be satisfied:

```python
async def handle_topology_scheduling_failure(job: Job, failure_reason: str):
    """
    Handle failure to schedule multi-GPU job with topology constraints.

    Common reasons:
    - No nodes with enough GPUs on same NVLink domain
    - GPUs available but fragmented across nodes
    - Topology constraint impossible with current hardware
    """
    if "topology" not in failure_reason.lower():
        return await standard_retry(job, failure_reason)

    # 1. Check if relaxing topology would help
    relaxed_flavor = await budsim_client.find_alternative_flavor(
        job=job,
        current_topology=job.policy.topology,
        relaxations=[
            TopologyConstraint.SAME_NODE,  # Try same node without NVLink
            TopologyConstraint.NONE,       # Try spread across nodes
        ]
    )

    if relaxed_flavor:
        # 2. Offer user a choice
        await send_notification(
            channel="slack",
            template="topology_relaxation_offer",
            data={
                "job_name": job.name,
                "original_topology": job.policy.topology,
                "suggested_topology": relaxed_flavor.topology,
                "performance_impact": relaxed_flavor.estimated_slowdown,
                "wait_time_reduction": relaxed_flavor.estimated_wait_reduction,
            }
        )
        # Job remains QUEUED, user can PATCH to accept relaxation
    else:
        # 3. No alternative - job cannot run with current cluster capacity
        job.status = JobStatus.FAILED
        job.status_message = f"Cannot satisfy topology constraint: {failure_reason}"
        await job_repo.update(job)
```

---

## Part 10: API Reference

### 10.1 Job API (BudCluster)

```yaml
# Create Job
POST /api/clusters/{cluster_id}/jobs
Request:
  {
    "name": "llm-endpoint-001",
    "job_type": "service",
    "deployment_type": "model",
    "model_id": "llama-3.1-70b",
    "resources": {
      "gpu_type": "A100",
      "gpu_count": 4,
      "memory": "128Gi"
    },
    "policy": {
      "priority_class": "high",
      "preemptible": false
    },
    "intent": {
      "workload_class": "production",
      "optimization_goal": "latency"
    },
    "labels": {
      "environment": "production"
    }
  }
Response:
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "llm-endpoint-001",
    "status": "pending",
    "estimated_cost": 12.50,
    "estimated_start": "2026-02-02T10:05:00Z"
  }

# Get Job
GET /api/clusters/{cluster_id}/jobs/{job_id}
Response:
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "llm-endpoint-001",
    "job_type": "service",
    "status": "running",
    "policy": {
      "priority_class": "high",
      "preemptible": false,
      "queue_name": "tenant-acme-queue"
    },
    "intent": {
      "workload_class": "production",
      "optimization_goal": "latency"
    },
    "resources": {
      "gpu_type": "A100",
      "gpu_count": 4,
      "memory": "128Gi"
    },
    "actual_start": "2026-02-02T10:04:30Z",
    "actual_cost": 5.25,
    "k8s_namespace": "tenant-acme",
    "k8s_resource_name": "llm-endpoint-001"
  }

# List Jobs
GET /api/clusters/{cluster_id}/jobs?status=running&job_type=service
Response:
  {
    "items": [...],
    "total": 25,
    "page": 1,
    "page_size": 20
  }

# Update Job (partial update)
PATCH /api/clusters/{cluster_id}/jobs/{job_id}
Request:
  {
    # Only policy and intent fields can be updated
    "policy": {
      "priority_class": "high",          # Upgrade priority (may trigger re-admission)
      "preemptible": false                # Make non-preemptible
    },
    "intent": {
      "budget_cap": 100.00                # Add/update budget cap
    },
    "labels": {
      "environment": "production"         # Update labels
    }
  }
Response:
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "running",
    "policy": {...},  # Updated
    "intent": {...}   # Updated
  }

# Cancel Job
DELETE /api/clusters/{cluster_id}/jobs/{job_id}
Response:
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "cancelled"
  }

# Get Schedule Timeline (with pagination)
GET /api/clusters/{cluster_id}/schedule?start=2026-02-02T00:00:00Z&end=2026-02-03T00:00:00Z&page=1&page_size=50
Response:
  {
    "timeline": [
      {
        "job_id": "...",
        "name": "llm-endpoint-001",
        "job_type": "service",
        "status": "running",
        "resources": {"gpu_type": "A100", "gpu_count": 4},
        "estimated_start": "2026-02-02T10:00:00Z",
        "estimated_end": null,  # SERVICE has no end
        "actual_start": "2026-02-02T10:04:30Z"
      },
      {
        "job_id": "...",
        "name": "training-job-001",
        "job_type": "training",
        "status": "queued",
        "resources": {"gpu_type": "A100", "gpu_count": 8},
        "estimated_start": "2026-02-02T14:00:00Z",
        "estimated_end": "2026-02-02T22:00:00Z"
      }
    ],
    "resources": {
      "A100": {"total": 64, "used": 24, "queued": 8}
    },
    "page": 1,
    "page_size": 50,
    "total": 127
  }

# Register Webhook for Status Changes
POST /api/clusters/{cluster_id}/webhooks
Request:
  {
    "url": "https://example.com/job-status-callback",
    "secret": "webhook-secret-for-signature",
    "events": ["job.queued", "job.running", "job.succeeded", "job.failed", "job.preempted"],
    "filters": {
      "job_type": ["training", "batch"],  # Optional: filter by job type
      "labels": {"environment": "production"}  # Optional: filter by labels
    }
  }
Response:
  {
    "id": "webhook-001",
    "url": "https://example.com/job-status-callback",
    "events": ["job.queued", "job.running", "job.succeeded", "job.failed", "job.preempted"],
    "created_at": "2026-02-03T10:00:00Z"
  }

# List Webhooks
GET /api/clusters/{cluster_id}/webhooks
Response:
  {
    "items": [
      {
        "id": "webhook-001",
        "url": "https://example.com/job-status-callback",
        "events": ["job.running", "job.succeeded"],
        "enabled": true
      }
    ]
  }

# Delete Webhook
DELETE /api/clusters/{cluster_id}/webhooks/{webhook_id}
```

### 10.2 Pipeline API (BudPipeline)

```yaml
# Create Pipeline
POST /api/pipelines
Request:
  {
    "name": "rag-deployment",
    "project_id": "...",
    "steps": [
      {
        "name": "deploy-vectordb",
        "step_type": "job",
        "config": {
          "job_type": "service",
          "deployment_type": "helm",
          "helm_chart": "qdrant/qdrant"
        }
      },
      {
        "name": "deploy-llm",
        "step_type": "job",
        "depends_on": ["deploy-vectordb"],
        "config": {
          "job_type": "service",
          "deployment_type": "model",
          "model_id": "llama-3.1-70b"
        }
      }
    ],
    "trigger": {
      "type": "manual"
    }
  }

# Execute Pipeline
POST /api/pipelines/{pipeline_id}/execute
Response:
  {
    "execution_id": "...",
    "status": "running",
    "steps": [
      {"name": "deploy-vectordb", "status": "running"},
      {"name": "deploy-llm", "status": "pending"}
    ]
  }

# Get Pipeline Status
GET /api/pipelines/{pipeline_id}/executions/{execution_id}
Response:
  {
    "execution_id": "...",
    "status": "succeeded",
    "started_at": "...",
    "completed_at": "...",
    "steps": [
      {
        "name": "deploy-vectordb",
        "status": "succeeded",
        "job_id": "...",
        "duration_seconds": 120
      },
      {
        "name": "deploy-llm",
        "status": "succeeded",
        "job_id": "...",
        "duration_seconds": 300
      }
    ]
  }

# Manage Pipeline Triggers
# Create Trigger
POST /api/pipelines/{pipeline_id}/triggers
Request:
  {
    "trigger_type": "cron",
    "cron_expression": "0 2 * * 0",  # Every Sunday at 2am
    "timezone": "UTC",
    "enabled": true
  }
Response:
  {
    "id": "trigger-001",
    "trigger_type": "cron",
    "cron_expression": "0 2 * * 0",
    "next_run": "2026-02-09T02:00:00Z",
    "enabled": true
  }

# List Triggers
GET /api/pipelines/{pipeline_id}/triggers
Response:
  {
    "items": [
      {
        "id": "trigger-001",
        "trigger_type": "cron",
        "cron_expression": "0 2 * * 0",
        "next_run": "2026-02-09T02:00:00Z",
        "last_run": "2026-02-02T02:00:00Z",
        "enabled": true
      },
      {
        "id": "trigger-002",
        "trigger_type": "event",
        "event_topic": "s3-file-uploaded",
        "event_filter": {"bucket": "training-data"},
        "enabled": true
      }
    ]
  }

# Update Trigger
PATCH /api/pipelines/{pipeline_id}/triggers/{trigger_id}
Request:
  {
    "enabled": false  # Disable trigger
  }

# Delete Trigger
DELETE /api/pipelines/{pipeline_id}/triggers/{trigger_id}
```

### 10.3 UseCase API (BudUseCases)

```yaml
# Deploy UseCase
POST /api/usecases/deploy
Request:
  {
    "template_id": "rag-enterprise",
    "name": "my-rag-app",
    "project_id": "...",
    "cluster_id": "...",
    "parameters": {
      "model": "llama-3.1-70b",
      "vector_db": "qdrant",
      "embedding_model": "bge-large"
    }
  }
Response:
  {
    "deployment_id": "...",
    "status": "deploying",
    "pipeline_id": "...",
    "components": [
      {"name": "qdrant", "status": "pending"},
      {"name": "embedder", "status": "pending"},
      {"name": "vllm", "status": "pending"},
      {"name": "orchestrator", "status": "pending"}
    ]
  }

# Get UseCase Deployment Status
GET /api/usecases/deployments/{deployment_id}
Response:
  {
    "deployment_id": "...",
    "template_id": "rag-enterprise",
    "status": "healthy",
    "components": [
      {
        "name": "qdrant",
        "job_id": "...",
        "status": "running",
        "endpoint": "http://qdrant.tenant-acme:6333"
      },
      {
        "name": "vllm",
        "job_id": "...",
        "status": "running",
        "endpoint": "http://vllm.tenant-acme:8000"
      }
    ],
    "entrypoint": "http://rag-orchestrator.tenant-acme:8080"
  }
```

---

## Part 11: Job Authorization & Access Control

This section defines how authorization works for Job operations, integrating with BudApp's existing authentication and permission system.

### 11.1 Authorization Principles

#### Why Source-Based Authorization?

Jobs are created from different sources (Pipeline, UseCase, Direct API), making job-level RBAC impractical:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         JOB SOURCES & OWNERSHIP                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   SourceType.PIPELINE                                                           │
│   └── Pipeline → Step → Job                                                     │
│       └── Who owns the Pipeline should own its Jobs                             │
│                                                                                 │
│   SourceType.USECASE                                                            │
│   └── UseCase Deployment → Job                                                  │
│       └── Who owns the UseCase deployment should own its Jobs                   │
│                                                                                 │
│   SourceType.DIRECT                                                             │
│   └── Endpoint (Model Deployment) → Job                                         │
│   └── Serverless Pod → Job                                                      │
│   └── Serverless Function → Job                                                 │
│       └── Who created the endpoint/pod should own its Jobs                      │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Key Insight**: Users think in terms of "my pipeline" or "my deployment", not "my job". Jobs are transient execution units; sources are the persistent entities users care about.

#### Permission Inheritance Model

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    PERMISSION INHERITANCE MODEL                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  Tenant                                                                         │
│    └── Project                                                                  │
│          ├── Pipeline ──────► Steps ──────► Jobs                                │
│          │     │                              ▲                                 │
│          │     └──────── Permission flows ────┘                                 │
│          │                                                                      │
│          ├── UseCase Deployment ──────────► Jobs                                │
│          │           │                        ▲                                 │
│          │           └── Permission flows ────┘                                 │
│          │                                                                      │
│          ├── Endpoint ────────────────────► Jobs                                │
│          │      │                             ▲                                 │
│          │      └──── Permission flows ───────┘                                 │
│          │                                                                      │
│          └── Serverless (Pod/Function) ───► Jobs                                │
│                    │                          ▲                                 │
│                    └── Permission flows ──────┘                                 │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Rule**: If a user can manage a source entity, they can manage all Jobs created from that source.

---

### 11.2 Integration with BudApp Auth

BudApp provides the authentication and authorization infrastructure:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         EXISTING AUTH ARCHITECTURE                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  Keycloak (Authentication)                                                      │
│  ├── JWT token validation                                                       │
│  ├── Realm roles: admin, super_admin, developer, devops, tester                 │
│  └── UMA permissions: module_{resource}#{scope}                                 │
│                                                                                 │
│  BudApp (Authorization)                                                         │
│  ├── Permission model: Global scopes (model:view, project:manage, etc.)         │
│  ├── ProjectPermission: Per-project scopes                                      │
│  ├── @require_permissions decorator: Checks against Keycloak UMA                │
│  └── validate_client_project_access(): Row-level security for CLIENT users      │
│                                                                                 │
│  EXTENDED FOR JOBS:                                                             │
│  ├── New permission scopes: pipeline:*, usecase:*, pod:*, job:*                 │
│  ├── JobAuthService: Source-based authorization                                 │
│  └── Row-level security via tenant_id + project membership                      │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

#### New Permission Scopes

Add these scopes to `PermissionEnum` in BudApp:

```python
class PermissionEnum(Enum):
    # ... existing scopes ...

    # Source-level permissions (for Job authorization)
    PIPELINE_VIEW = "pipeline:view"
    PIPELINE_MANAGE = "pipeline:manage"

    USECASE_VIEW = "usecase:view"
    USECASE_MANAGE = "usecase:manage"

    POD_VIEW = "pod:view"
    POD_MANAGE = "pod:manage"

    FUNCTION_VIEW = "function:view"
    FUNCTION_MANAGE = "function:manage"

    # Job permissions (admin override, not source-based)
    JOB_VIEW = "job:view"           # View any job in project
    JOB_MANAGE = "job:manage"       # Admin override for any job in project
    JOB_LOGS = "job:logs"           # View logs for jobs
    JOB_EXEC = "job:exec"           # Exec into running containers
```

---

### 11.3 Job Permission Types

```python
class JobPermission(str, Enum):
    """Actions that can be performed on Jobs."""

    # Read operations
    VIEW = "view"                   # View job details and status
    LIST = "list"                   # List jobs (filtered by access)
    LOGS = "logs"                   # View job logs
    METRICS = "metrics"             # View job metrics

    # Write operations
    CREATE = "create"               # Create new job (via source)
    CANCEL = "cancel"               # Cancel running job
    DELETE = "delete"               # Delete job record
    RETRY = "retry"                 # Retry failed job

    # Admin operations
    EXEC = "exec"                   # Exec into container
    UPDATE_PRIORITY = "priority"    # Change job priority
```

---

### 11.4 JobAuthService Implementation

This service lives in BudCluster and handles all Job authorization decisions:

```python
# services/budcluster/budcluster/auth/job_auth_service.py

from enum import Enum
from uuid import UUID
from typing import Optional

from budcluster.models import Job, SourceType
from budcluster.commons.exceptions import PermissionDeniedError


class JobAuthService:
    """
    Authorization service for Job operations.

    Jobs inherit permissions from their source entity (Pipeline, UseCase,
    Endpoint, Pod). A user who can manage a source can manage its Jobs.
    """

    def __init__(
        self,
        permission_client: "BudAppPermissionClient",
        pipeline_repo: "PipelineRepository",
        usecase_repo: "UseCaseRepository",
        endpoint_repo: "EndpointRepository",
        pod_repo: "PodRepository",
    ):
        self.permission_client = permission_client
        self.pipeline_repo = pipeline_repo
        self.usecase_repo = usecase_repo
        self.endpoint_repo = endpoint_repo
        self.pod_repo = pod_repo

    async def check_permission(
        self,
        user_id: UUID,
        user_tenant_id: UUID,
        job: Job,
        permission: JobPermission,
    ) -> bool:
        """
        Check if user can perform action on job.

        Authorization flow:
        1. Tenant isolation (hard requirement)
        2. Admin override check (job:manage scope)
        3. Source-based authorization (owner or source permission)
        """
        # 1. Tenant isolation - always enforced
        if user_tenant_id != job.tenant_id:
            return False

        # 2. Admin override - user with job:manage can do anything
        if await self._has_admin_override(user_id, job.project_id, permission):
            return True

        # 3. Source-based authorization
        return await self._check_source_permission(
            user_id, job, permission
        )

    async def authorize_or_raise(
        self,
        user_id: UUID,
        user_tenant_id: UUID,
        job: Job,
        permission: JobPermission,
    ) -> None:
        """Check permission and raise PermissionDeniedError if denied."""
        if not await self.check_permission(
            user_id, user_tenant_id, job, permission
        ):
            raise PermissionDeniedError(
                f"Permission denied: {permission.value} on job {job.id}"
            )

    async def _has_admin_override(
        self,
        user_id: UUID,
        project_id: UUID,
        permission: JobPermission,
    ) -> bool:
        """Check if user has admin-level job permissions."""
        # Map job permissions to required scopes
        scope_mapping = {
            JobPermission.VIEW: "job:view",
            JobPermission.LIST: "job:view",
            JobPermission.LOGS: "job:logs",
            JobPermission.METRICS: "job:view",
            JobPermission.CREATE: "job:manage",
            JobPermission.CANCEL: "job:manage",
            JobPermission.DELETE: "job:manage",
            JobPermission.RETRY: "job:manage",
            JobPermission.EXEC: "job:exec",
            JobPermission.UPDATE_PRIORITY: "job:manage",
        }

        required_scope = scope_mapping.get(permission)
        if not required_scope:
            return False

        return await self.permission_client.has_project_permission(
            user_id=user_id,
            project_id=project_id,
            scope=required_scope,
        )

    async def _check_source_permission(
        self,
        user_id: UUID,
        job: Job,
        permission: JobPermission,
    ) -> bool:
        """
        Check permission based on job's source entity.

        Delegates to source-specific authorization method based on source_type.
        """
        match job.source_type:
            case SourceType.PIPELINE:
                return await self._check_pipeline_permission(
                    user_id, job, permission
                )
            case SourceType.USECASE:
                return await self._check_usecase_permission(
                    user_id, job, permission
                )
            case SourceType.DIRECT:
                return await self._check_direct_permission(
                    user_id, job, permission
                )
            case _:
                # Unknown source type - deny by default
                return False

    async def _check_pipeline_permission(
        self,
        user_id: UUID,
        job: Job,
        permission: JobPermission,
    ) -> bool:
        """
        Pipeline Jobs: User can manage if they own or can manage the Pipeline.
        """
        pipeline = await self.pipeline_repo.get(job.source_id)
        if not pipeline:
            return False

        # Owner has full access
        if pipeline.created_by == user_id:
            return True

        # Check for pipeline:manage permission
        required_scope = self._get_source_scope(permission, "pipeline")
        return await self.permission_client.has_project_permission(
            user_id=user_id,
            project_id=pipeline.project_id,
            scope=required_scope,
        )

    async def _check_usecase_permission(
        self,
        user_id: UUID,
        job: Job,
        permission: JobPermission,
    ) -> bool:
        """
        UseCase Jobs: User can manage if they own or can manage the deployment.
        """
        deployment = await self.usecase_repo.get_deployment(job.source_id)
        if not deployment:
            return False

        # Owner has full access
        if deployment.created_by == user_id:
            return True

        # Check for usecase:manage permission
        required_scope = self._get_source_scope(permission, "usecase")
        return await self.permission_client.has_project_permission(
            user_id=user_id,
            project_id=deployment.project_id,
            scope=required_scope,
        )

    async def _check_direct_permission(
        self,
        user_id: UUID,
        job: Job,
        permission: JobPermission,
    ) -> bool:
        """
        Direct Jobs: Check based on the direct source (endpoint, pod, function).

        source_id can reference:
        - Endpoint (model deployment)
        - Serverless Pod
        - Serverless Function
        """
        # Try endpoint first
        endpoint = await self.endpoint_repo.get(job.source_id)
        if endpoint:
            if endpoint.created_by == user_id:
                return True
            required_scope = self._get_source_scope(permission, "endpoint")
            return await self.permission_client.has_project_permission(
                user_id=user_id,
                project_id=endpoint.project_id,
                scope=required_scope,
            )

        # Try serverless pod
        pod = await self.pod_repo.get(job.source_id)
        if pod:
            if pod.created_by == user_id:
                return True
            required_scope = self._get_source_scope(permission, "pod")
            return await self.permission_client.has_project_permission(
                user_id=user_id,
                project_id=pod.project_id,
                scope=required_scope,
            )

        # Fallback: check project-level job permission
        return await self.permission_client.has_project_permission(
            user_id=user_id,
            project_id=job.project_id,
            scope=self._get_source_scope(permission, "job"),
        )

    def _get_source_scope(
        self,
        permission: JobPermission,
        source_type: str,
    ) -> str:
        """Map job permission to source scope."""
        if permission in {
            JobPermission.VIEW,
            JobPermission.LIST,
            JobPermission.LOGS,
            JobPermission.METRICS,
        }:
            return f"{source_type}:view"
        else:
            return f"{source_type}:manage"
```

---

### 11.5 Authorization Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         JOB AUTHORIZATION FLOW                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   User Request: DELETE /api/clusters/{cluster_id}/jobs/{job_id}                 │
│           │                                                                     │
│           ▼                                                                     │
│   ┌───────────────────────────────────────────────────────────────────┐        │
│   │ Step 1: Authentication (BudApp/Keycloak)                          │        │
│   │ - Validate JWT token                                              │        │
│   │ - Extract user_id, tenant_id from token                           │        │
│   │ - Check token not blacklisted                                     │        │
│   └───────────────────────────────────────────────────────────────────┘        │
│           │                                                                     │
│           ▼                                                                     │
│   ┌───────────────────────────────────────────────────────────────────┐        │
│   │ Step 2: Basic Permission Check (@require_permissions)             │        │
│   │ - Check user has job:view scope (basic access)                    │        │
│   │ - This is a coarse-grained check                                  │        │
│   └───────────────────────────────────────────────────────────────────┘        │
│           │                                                                     │
│           ▼                                                                     │
│   ┌───────────────────────────────────────────────────────────────────┐        │
│   │ Step 3: Load Job from Database                                    │        │
│   │ - Fetch job by ID                                                 │        │
│   │ - Return 404 if not found                                         │        │
│   └───────────────────────────────────────────────────────────────────┘        │
│           │                                                                     │
│           ▼                                                                     │
│   ┌───────────────────────────────────────────────────────────────────┐        │
│   │ Step 4: Source-Based Authorization (JobAuthService)               │        │
│   │                                                                   │        │
│   │ 4a. Tenant Isolation                                              │        │
│   │     user.tenant_id == job.tenant_id? ─── No ──► 403 Forbidden     │        │
│   │          │                                                        │        │
│   │         Yes                                                       │        │
│   │          ▼                                                        │        │
│   │ 4b. Admin Override                                                │        │
│   │     user has job:manage for project? ─── Yes ──► ✓ Authorized     │        │
│   │          │                                                        │        │
│   │         No                                                        │        │
│   │          ▼                                                        │        │
│   │ 4c. Source Permission                                             │        │
│   │     job.source_type == PIPELINE?                                  │        │
│   │       └── user created pipeline OR has pipeline:manage?           │        │
│   │                   │                                               │        │
│   │     job.source_type == USECASE?                                   │        │
│   │       └── user created deployment OR has usecase:manage?          │        │
│   │                   │                                               │        │
│   │     job.source_type == DIRECT?                                    │        │
│   │       └── user created endpoint/pod OR has endpoint:manage?       │        │
│   │                   │                                               │        │
│   │          ▼                                                        │        │
│   │     Authorized? ─── No ──► 403 Forbidden                          │        │
│   │          │                                                        │        │
│   │         Yes                                                       │        │
│   │          ▼                                                        │        │
│   │     ✓ Proceed with operation                                      │        │
│   └───────────────────────────────────────────────────────────────────┘        │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

### 11.6 Route Protection Pattern

Example of how to protect Job routes in BudCluster:

```python
# services/budcluster/budcluster/routes/job_routes.py

from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated
from uuid import UUID

from budcluster.auth.job_auth_service import JobAuthService, JobPermission
from budcluster.commons.dependencies import (
    get_current_active_user,
    get_job_auth_service,
    get_session,
)
from budcluster.commons.permission_handler import require_permissions
from budcluster.commons.constants import PermissionEnum
from budcluster.services.job_service import JobService

router = APIRouter(prefix="/clusters/{cluster_id}/jobs", tags=["jobs"])


@router.get("/{job_id}")
@require_permissions(permissions=[PermissionEnum.JOB_VIEW])
async def get_job(
    cluster_id: UUID,
    job_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    job_auth: Annotated[JobAuthService, Depends(get_job_auth_service)],
    job_service: Annotated[JobService, Depends(get_job_service)],
) -> JobResponse:
    """Get job details. Requires source ownership or job:view permission."""

    job = await job_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Source-based authorization
    await job_auth.authorize_or_raise(
        user_id=current_user.id,
        user_tenant_id=current_user.tenant_id,
        job=job,
        permission=JobPermission.VIEW,
    )

    return JobResponse.from_orm(job)


@router.delete("/{job_id}")
@require_permissions(permissions=[PermissionEnum.JOB_VIEW])
async def cancel_job(
    cluster_id: UUID,
    job_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    job_auth: Annotated[JobAuthService, Depends(get_job_auth_service)],
    job_service: Annotated[JobService, Depends(get_job_service)],
) -> JobResponse:
    """Cancel a running job. Requires source ownership or job:manage permission."""

    job = await job_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Source-based authorization - CANCEL permission
    await job_auth.authorize_or_raise(
        user_id=current_user.id,
        user_tenant_id=current_user.tenant_id,
        job=job,
        permission=JobPermission.CANCEL,
    )

    return await job_service.cancel_job(job_id)


@router.get("/{job_id}/logs")
@require_permissions(permissions=[PermissionEnum.JOB_VIEW])
async def get_job_logs(
    cluster_id: UUID,
    job_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    job_auth: Annotated[JobAuthService, Depends(get_job_auth_service)],
    job_service: Annotated[JobService, Depends(get_job_service)],
    follow: bool = False,
    tail: int = 100,
) -> StreamingResponse:
    """Stream job logs. Requires source ownership or job:logs permission."""

    job = await job_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Source-based authorization - LOGS permission
    await job_auth.authorize_or_raise(
        user_id=current_user.id,
        user_tenant_id=current_user.tenant_id,
        job=job,
        permission=JobPermission.LOGS,
    )

    return await job_service.stream_logs(job_id, follow=follow, tail=tail)


@router.post("/{job_id}/exec")
@require_permissions(permissions=[PermissionEnum.JOB_EXEC])
async def exec_into_job(
    cluster_id: UUID,
    job_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    job_auth: Annotated[JobAuthService, Depends(get_job_auth_service)],
    job_service: Annotated[JobService, Depends(get_job_service)],
    request: ExecRequest,
) -> ExecResponse:
    """Exec into running container. Requires source ownership or job:exec permission."""

    job = await job_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Source-based authorization - EXEC permission (most privileged)
    await job_auth.authorize_or_raise(
        user_id=current_user.id,
        user_tenant_id=current_user.tenant_id,
        job=job,
        permission=JobPermission.EXEC,
    )

    # Audit log exec session
    await audit_service.log(
        action="job:exec",
        resource_type="job",
        resource_id=job_id,
        user_id=current_user.id,
        details={"command": request.command},
    )

    return await job_service.exec_into_container(job_id, request)
```

---

### 11.7 List Jobs with Filtering

When listing jobs, filter based on what the user can access:

```python
@router.get("")
@require_permissions(permissions=[PermissionEnum.JOB_VIEW])
async def list_jobs(
    cluster_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    job_service: Annotated[JobService, Depends(get_job_service)],
    project_id: Optional[UUID] = None,
    status: Optional[JobStatus] = None,
    source_type: Optional[SourceType] = None,
    limit: int = 50,
    offset: int = 0,
) -> JobListResponse:
    """
    List jobs with access control filtering.

    Returns only jobs the user can view:
    - Jobs from sources the user owns
    - Jobs from sources where user has {source}:view permission
    - All jobs if user has job:view for the project
    """

    # Build base query with tenant isolation
    query = JobQuery(
        tenant_id=current_user.tenant_id,
        cluster_id=cluster_id,
        project_id=project_id,
        status=status,
        source_type=source_type,
    )

    # Check if user has admin access to all jobs
    if await permission_client.has_project_permission(
        user_id=current_user.id,
        project_id=project_id,
        scope="job:view",
    ):
        # Admin can see all jobs in project
        jobs = await job_service.list_jobs(query, limit, offset)
    else:
        # Non-admin: filter to accessible jobs
        jobs = await job_service.list_accessible_jobs(
            query=query,
            user_id=current_user.id,
            limit=limit,
            offset=offset,
        )

    return JobListResponse(
        jobs=[JobResponse.from_orm(j) for j in jobs],
        total=len(jobs),
        limit=limit,
        offset=offset,
    )
```

---

### 11.8 Permission Matrix

| Role | Scope | Job Actions Allowed |
|------|-------|---------------------|
| **Source Owner** | Created the Pipeline/UseCase/Endpoint/Pod | All actions on jobs from that source |
| **Project Admin** | `job:manage` on project | All actions on all jobs in project |
| **Project Member** | `pipeline:view`, `job:view` on project | View jobs from pipelines they can access |
| **Viewer** | `job:view` on project | View-only for all jobs in project |
| **Tenant Admin** | Tenant-level admin | All actions on all jobs in tenant |

---

### 11.9 Audit Logging

All job authorization decisions should be logged for compliance:

```python
class JobAuditEvents:
    """Audit events for job operations."""

    JOB_VIEW = "job:view"
    JOB_CANCEL = "job:cancel"
    JOB_DELETE = "job:delete"
    JOB_LOGS_ACCESS = "job:logs_access"
    JOB_EXEC = "job:exec"
    JOB_PERMISSION_DENIED = "job:permission_denied"


async def log_job_access(
    session: Session,
    action: str,
    job: Job,
    user: User,
    success: bool,
    details: Optional[dict] = None,
):
    """Log job access for audit trail."""
    await audit_service.log(
        session=session,
        action=action,
        resource_type="job",
        resource_id=job.id,
        user_id=user.id,
        details={
            "job_type": job.job_type.value,
            "source_type": job.source_type.value,
            "source_id": str(job.source_id),
            "project_id": str(job.project_id),
            "success": success,
            **(details or {}),
        },
    )
```

---

### 11.10 Design Decisions

> **Decision: Source-Based over Job-Level RBAC**
>
> Jobs inherit permissions from their source entities rather than having their own permission model.
>
> **Rationale:**
> 1. Users think in terms of "my pipeline" not "my job"
> 2. Jobs are transient; sources are the persistent entities
> 3. Fewer permission checks, simpler model
> 4. Consistent with existing `created_by` patterns
>
> **Trade-off:**
> - Cannot have different permissions for different jobs from the same source
> - Accepted because this use case is rare and can use admin override

> **Decision: Admin Override via job:manage Scope**
>
> Users with `job:manage` scope on a project can manage any job regardless of source.
>
> **Rationale:**
> 1. Project admins need to cancel runaway jobs
> 2. Support/ops needs to intervene in emergencies
> 3. Consistent with existing `*:manage` pattern

> **Decision: JobAuthService in BudCluster**
>
> Authorization logic lives in BudCluster, not BudApp.
>
> **Rationale:**
> 1. BudCluster owns Jobs and knows source_type/source_id
> 2. Reduces cross-service calls during authorization
> 3. BudCluster calls BudApp permission API for scope checks
> 4. Source repositories are already in BudCluster's context

---

## Summary

This document defines the complete Job, Scheduling, and Orchestration architecture for Bud AI Foundry.

### Core Concepts

| Concept | Owner | Description |
|---------|-------|-------------|
| **Job** | BudCluster | Atomic scheduling unit - anything deployed on a cluster |
| **Job Types** | BudCluster | SERVICE (always-on), BATCH (run-to-completion), TRAINING (with checkpoints) |
| **Pipeline** | BudPipeline | DAG of Steps with triggers |
| **Step Types** | BudPipeline | JOB (creates Job), API_CALL, FUNCTION, NOTIFICATION, CONDITION, WAIT, PARALLEL, LOOP |
| **Scheduling** | Kueue | Resource-based admission control with quotas, priority, fair-share |
| **Multi-Cluster** | MultiKueue | Cross-cluster workload distribution |
| **Orchestration** | Dapr Workflows | Durable DAG execution engine |

### The 3-Axis Job Model

Jobs are defined across three orthogonal axes to prevent type explosion and maintain API stability:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           3-AXIS JOB MODEL SUMMARY                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   AXIS 1: TYPE                 AXIS 2: POLICY               AXIS 3: INTENT     │
│   ────────────                 ──────────────               ──────────────     │
│   "WHAT is it?"                "HOW to schedule?"           "WHY this way?"    │
│                                                                                 │
│   • SERVICE                    • priority_class             • optimization_goal│
│   • BATCH                      • preemptible               • spot_eligible     │
│   • TRAINING                   • scheduled_start           • budget_cap        │
│                                • deadline                  • workload_class    │
│                                • time_window               • sla_tier          │
│                                • queue_name                                    │
│                                • topology                                      │
│                                • max_retries                                   │
│                                                                                 │
│   Stable (rarely changes)      Stable (well-defined)       Flexible (inferred)│
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

| Axis | Question | Stored In | Affects |
|------|----------|-----------|---------|
| **Type** | What is it? | `job.job_type` | Lifecycle, K8s resource, restart, billing |
| **Policy** | How to schedule? | `job.policy.*` | Kueue admission, preemption, timing |
| **Intent** | Why this way? | `job.intent.*` | BudSim, cluster selection, cost strategy |

### Key Principles

1. **Types are NOT scheduling mechanisms**: Types define lifecycle (WHAT), not scheduling (HOW/WHY)
2. **Keep types small**: SERVICE, BATCH, TRAINING are sufficient
3. **Use Policy for constraints**: Priority, deadlines, topology, queues
4. **Use Intent for optimization**: Cost, latency, workload classification
5. **Only JOB-type steps create Jobs**: All other pipeline steps run without cluster resources
6. **BudCluster owns Jobs**: All scheduling flows through BudCluster → Kueue

### What is NOT a Job Type

| Pattern | Correct Modeling |
|---------|------------------|
| Serverless | `SERVICE` + `policy.scale_to_zero` |
| Spot/Preemptible | Any type + `intent.spot_eligible` |
| Scheduled | Any type + `policy.scheduled_start` |
| Interactive | `SERVICE` + `intent.workload_class: interactive` |
| System | Any type + `owner_type: platform` |
| Low Priority | Any type + `policy.priority_class: low` |

---

## Appendix: Changelog

### Version 1.3 (2026-02-05)

**New Section: Part 11 - Job Authorization & Access Control**

Added comprehensive authorization model for Job operations:

- **Source-Based Authorization**: Jobs inherit permissions from their source entity (Pipeline, UseCase, Endpoint, Pod) rather than having job-level RBAC
- **Permission Inheritance Model**: Tenant → Project → Source → Job hierarchy
- **JobAuthService**: Complete implementation for authorization decisions
- **Integration with BudApp Auth**: Uses existing Keycloak + ProjectPermission infrastructure
- **New Permission Scopes**: Added `pipeline:*`, `usecase:*`, `pod:*`, `function:*`, `job:*` scopes
- **JobPermission Enum**: VIEW, LIST, LOGS, METRICS, CREATE, CANCEL, DELETE, RETRY, EXEC, UPDATE_PRIORITY
- **Authorization Flow**: 4-step flow (Auth → Basic Check → Load Job → Source Auth)
- **Route Protection Pattern**: Examples for GET, DELETE, LOGS, EXEC endpoints
- **List Filtering**: Filter job lists based on user's accessible sources
- **Permission Matrix**: Role-based access summary
- **Audit Logging**: Compliance logging for all job access
- **Design Decisions**: Documented rationale for source-based over job-level RBAC

**Disaster Recovery & High Availability Additions:**

- **Idempotency Key**: Added `idempotency_key` field to Job schema (Part 2.6) to prevent duplicate job creation during failures/retries
- **Job Reconciliation Loop**: Added Section 9.2.1 with `JobReconciler` class that syncs DB state with K8s on BudCluster startup
- **Orphaned Resource Cleanup**: Reconciler detects and cleans up K8s resources without corresponding Job records
- **Idempotent Job Creation**: Added Section 9.2.2 with guidelines for idempotency key usage by Pipeline, UseCase, and direct API calls

**Multi-Tenancy Review:**

- Confirmed existing Kueue documentation (Part 7) fully covers multi-tenancy requirements:
  - **LocalQueue/ClusterQueue**: Per-tenant quotas and admission control
  - **Cohort Borrowing**: Automatic resource sharing between tenants in same cohort
  - **Fair-Share**: Priority-based scheduling across tenants
  - **Resource Isolation**: K8s cgroups v2 + Kueue quotas provide sufficient isolation
- No architecture additions needed - Kueue handles multi-tenancy natively
- UX features (quota request workflows, tenant onboarding automation) deferred to P2

**Observability Review:**

- Confirmed LGTM stack (already in Helm chart) provides observability foundation:
  - **Tempo**: Distributed tracing backend (replaces Jaeger/Zipkin)
  - **Loki**: Centralized log aggregation with multi-tenant isolation
  - **Mimir/Prometheus**: Metrics collection and storage
  - **Grafana**: Visualization and dashboards
- **BudMetrics**: ClickHouse analytics for time-series data, job metrics aggregation
- **BudNotify**: Novu-based alerting with email, Slack, PagerDuty support
- **Job Debugging**: `JobPermission.EXEC` (Part 11) + K8s `ttlSecondsAfterFinished`
- Remaining work is implementation/configuration, not architecture gaps
- P2 items: Capacity planning predictions, advanced GPU profiling, SLA monitoring

**Cost Management Review:**

- Confirmed cost tracking infrastructure exists:
  - **Job Schema**: `estimated_cost`, `actual_cost`, `budget_cap`, `budget_action`, `cost_center`
  - **BudMetrics**: Usage APIs (`/usage/summary`, `/usage/history`) with ClickHouse rollup tables
  - **Section 4.7**: Cost-Based Scheduling (spot instances, off-peak)
  - **Section 9.4.4**: CostEstimationFeedback (learns from actual vs estimated)
- Storage/network costs are cloud provider billing (OPS/INFRA concern)
- P2 items: Project-level budgets, budget workflows, cost anomaly detection, invoice generation

**Operations & Maintenance Review:**

- Confirmed Section 9.4.1 `handle_cluster_removal()` handles maintenance scenarios:
  - Graceful drain with `mark_cluster_draining()`
  - TRAINING: checkpoint signal + wait + migrate
  - SERVICE: attempt migration to other clusters
  - BATCH: wait for completion or retry
- K8s upgrades, GPU drivers, GitOps are standard OPS/INFRA procedures
- BudCluster has `update_autoscale.yaml` playbook for scaling config
- GPU Operator + HAMI auto-installed during cluster onboarding

**Performance & Scale Review:**

- Confirmed Part 8.1-8.3 covers MultiKueue for multi-cluster federation
- Rate limiting: BudGateway (Rust) handles at API gateway level
- Kueue capacity: ~10K workloads/queue documented, monitor via Prometheus
- Cold start for serverless: K8s/KEDA handles `scale_to_zero` SERVICE jobs
- DB partitioning and large pipelines are implementation/ops concerns, not architecture

**Data Management Review:**

- Confirmed `CheckpointConfig` (Part 2.5) covers checkpoint storage configuration
- BudModel service uses MinIO (S3-compatible) for model artifact storage
- Dataset access is user responsibility (standard K8s volume mount patterns)
- Data residency: `cluster_id` for regional placement + cloud storage config

**Compliance & Governance Review:**

- Confirmed Part 11.9 JobAuditEvents provides comprehensive audit logging:
  - Events: `JOB_VIEW`, `JOB_CREATE`, `JOB_CANCEL`, `JOB_DELETE`, `JOB_LOGS`, `JOB_EXEC`
  - Integrates with BudApp `log_audit()` infrastructure
- Data classification: Job labels + `cluster_id` for regional/compliance placement
- Reproducibility: Container image digests + config captured; full manifest API is P2
- P2 items: SOC2/HIPAA/PCI certifications (customer responsibility), model governance workflows, export controls

**ML-Specific Scenarios Review:**

- **Distributed Training**: TopologyConstraint (SAME_NODE, NVLINK, SPREAD) + Kueue gang-scheduling
- **Autoscaling**: `scale_to_zero`, `min_replicas`, `max_replicas` in JobPolicy; K8s HPA/KEDA handles
- **Multi-model serving**: HAMI (time-slicing) auto-installed; MIG ResourceFlavors documented
- **OOM handling**: K8s OOMKilled + Job retry policy + MIG prevents fragmentation
- **Model warm-up / Dynamic batching**: Inference engine (vLLM) responsibility, not platform
- P2 items: HPO framework integration, progress-aware preemption intelligence

**Integration & Interoperability Review:**

- BudPipeline API (`POST /budpipeline/{id}/execute`) enables CI/CD, Airflow, Dagster integration
- Webhook API for job status callbacks
- `idempotency_key` prevents duplicate jobs during retries
- Keycloak provides SSO (SAML, OIDC, LDAP)
- P2 items: MLflow auto-logging, custom GitHub Action

**Edge Cases & Failure Modes Review:**

- JobReconciler (Section 9.2.1) handles zombie detection on BudCluster startup
- `max_retries` + `retry_delay_seconds` prevent infinite retry loops
- Kueue handles quota admission atomically (no race conditions)
- Clock skew mitigated by NTP + server-side scheduling
- P2 items: `on_failure` strategy configuration for pipelines

**SLA & Quality of Service Review:**

- PriorityClass (CRITICAL, HIGH, NORMAL, LOW) defines implicit SLA tiers
- LGTM stack can track queue wait times and uptime metrics
- Kueue quotas provide resource guarantees per tenant
- P2 items: Formal SLA definitions, capacity booking/advance reservations

**Advanced Scheduling Review:**

- Kueue gang scheduling provides all-or-nothing admission
- K8s nodeSelector + podAffinity for co-location
- `preemption_grace_period` and `retry_on_preemption` for safe preemption
- `policy.deadline` exists; dynamic priority boost is P2
- P2 items: Priority inheritance, multi-factor preemption cost

**Network & Storage Review:**

- TopologyConstraint + ResourceFlavors support specialized hardware (InfiniBand, NVMe)
- K8s `ephemeral-storage` resource for local SSD allocation
- StorageClass configuration during cluster onboarding for shared filesystems
- Hardware-specific setup (GPU-direct storage, RDMA) is OPS/INFRA

### Version 1.2 (2026-02-03)

**Schema & Code Fixes:**
- Added `scale_to_zero`, `min_replicas`, `max_replicas` to JobPolicy for serverless support
- Added `CheckpointConfig` schema for TRAINING job checkpoint configuration
- Added `budget_action` field to JobIntent ("warn" | "pause" | "cancel")
- Fixed `create_kueue_workload()` to use `PriorityClass` enum (was incorrectly using `JobPriority`)
- Fixed field access: `job.policy.queue_name` and `job.policy.priority_class` (was using flat access)
- Added intent labels to Kueue Workload for MultiKueue cluster selection
- Fixed MIG ResourceFlavor labels to use consistent `nvidia.com/mig.config` format

**Clarifications Added:**
- Added Step referencing convention (UUIDs vs names)
- Added inter-job dependency note (handled via Pipeline DAG, not Job.depends_on)
- Added design decision box for centralized time-based scheduling at BudPipeline layer
- Added PENDING vs QUEUED status disambiguation table
- Added Kueue Workload deletion timing documentation
- Added K8s restartPolicy differences: BATCH (Never) vs TRAINING (OnFailure)
- Added SERVICE preemption handling details
- Added Cohort Fair-Share calculation explanation

**New Sections:**
- 9.4 Edge Cases and Operational Considerations:
  - 9.4.1 Cluster removal with running jobs
  - 9.4.2 Quota exhaustion in parallel Pipeline steps
  - 9.4.3 Orphaned Workload cleanup
  - 9.4.4 Cost estimation feedback loop
  - 9.4.5 Multi-tenant isolation
  - 9.4.6 TRAINING timeout with checkpoint interaction
  - 9.4.7 Multi-GPU topology failure handling

**API Additions:**
- Added `PATCH /api/clusters/{cluster_id}/jobs/{job_id}` for partial job updates
- Added pagination to schedule timeline endpoint
- Added webhook management endpoints for job status notifications
- Added trigger management endpoints for Pipelines (CRUD for cron, event triggers)
- Updated API request/response examples to use proper nested `policy`/`intent` structure

### Version 1.1 (2026-02-02)

- Added 3-axis job model (Type vs Policy vs Intent)
- Initial document structure with 10 parts
