# Unified Architecture: Use Case Deployment + GPU-as-a-Service

> **Document Version:** 1.8
> **Date:** January 2026
> **Status:** Research & Planning
> **Authors:** Engineering Team
> **Last Updated:** February 5, 2026 - Updated Section 8.3 with Hybrid Template Storage (YAML files for system templates + DB for user templates)

## Executive Summary

This document synthesizes patterns from leading GPU cloud providers (RunPod, CoreWeave, Lambda Labs, Vast.ai, Modal) with use case deployment platforms (Dify, TrueFoundry, NVIDIA NIM) to propose a unified architecture for Bud AI Foundry that combines:

1. **Use Case Deployment** - RAG, chatbot, agent templates
2. **GPU-as-a-Service** - Similar to RunPod (pods + serverless)
3. **Resource Scheduling & Queuing** - Enterprise-grade GPU management

---

## Table of Contents

1. [Industry Research Summary](#part-1-industry-research-summary)
2. [Unified Architecture Proposal](#part-2-unified-architecture-proposal)
3. [BudCompute - GPU-as-a-Service Core (Optional)](#part-3-budcompute---gpu-as-a-service-core-optional)
4. [BudCluster Scheduling - Kueue + MultiKueue](#part-4-budcluster-scheduling---kueue--multikueue)
5. [Job & Pipeline Layer](#part-5-job--pipeline-layer) *(NEW)*
   - [5.1 Job Abstraction](#51-job-abstraction) - Atomic scheduling unit
   - [5.2 Pipeline & Step Types](#52-pipeline--step-types) - JOB, API_CALL, FUNCTION, CONDITION
   - [5.3 Scheduling Dimensions](#53-scheduling-dimensions) - Resource, Time, Event, Priority
   - [5.4 UI Schedule Visualization](#54-ui-schedule-visualization)
   - [5.6 Data Ownership](#56-data-ownership) - BudCluster owns Jobs, BudPipeline owns Pipelines
6. [BudQueue - Request Queue Management](#part-6-budqueue---request-queue-management)
7. [BudMetrics (Extended) - Observability + Metering](#part-7-budmetrics-extended---observability--metering)
8. [BudUseCases - Template-Based Deployment](#part-8-budusecases---template-based-deployment)
   - [8.2 Component Registry](#82-component-registry) (Docker + Helm support)
   - [8.3 Use Case Template Schema](#83-use-case-template-schema)
   - [8.4 Template-Driven Orchestration](#84-template-driven-orchestration)
9. [Unified Data Model](#part-9-unified-data-model)
10. [Implementation Roadmap](#part-10-implementation-roadmap)
11. [Key Differentiators](#part-11-key-differentiators-vs-competitors)
12. [Sources & References](#sources)

---

## Part 1: Industry Research Summary

### 1.1 GPU-as-a-Service Models

| Provider | Model | Key Innovation | Pricing |
|----------|-------|----------------|---------|
| [RunPod](https://www.runpod.io/) | Pods + Serverless | FlashBoot (1-2s cold start), Community Cloud | Per-second billing |
| [CoreWeave](https://www.coreweave.com/) | Bare-metal K8s | CKS + SUNK, 50%+ MFU, DPU offload | Per-minute billing |
| [Lambda Labs](https://lambda.ai/) | On-demand + Reserved | 1-Click Clusters, zero egress | Per-minute billing |
| [Vast.ai](https://vast.ai/) | P2P Marketplace | 17K GPUs, 1300 providers, 3-5x cheaper | Dynamic bidding |
| [Modal](https://modal.com/) | Pure Serverless | GPU snapshotting (10x faster cold start) | Per-second billing |

### 1.2 GPU Scheduling Patterns

| Pattern | Use Case | Technology |
|---------|----------|------------|
| **Full GPU** | Training, large inference | Standard K8s scheduling |
| **MIG** | Production inference, isolation | NVIDIA A100/H100, 7 partitions max |
| **Time-slicing** | Dev/test, bursty workloads | HAMI (already in Bud) |
| **Kueue** | Multi-tenant quotas | CNCF, queuing + admission |
| **Volcano** | Gang scheduling, HPC | Preemption, topology-aware |

**Source:** [Kubernetes GPU Scheduling 2025](https://debugg.ai/resources/kubernetes-gpu-scheduling-2025-kueue-volcano-mig)

### 1.3 Request Queue & Autoscaling

Key insight: **Queue size is better than GPU utilization for autoscaling decisions**.

- **NVIDIA Dynamo**: Inference-aware autoscaler monitoring KV cache and prefill queue
- **KEDA**: Event-driven autoscaling, faster than HPA for spiky traffic
- **Pre-warmed pools**: 500ms provisioning vs 3-7 minute cold starts

**Source:** [NVIDIA Dynamo](https://developer.nvidia.com/blog/nvidia-dynamo-adds-gpu-autoscaling-kubernetes-automation-and-networking-optimizations/)

### 1.4 Multi-Cluster Federation

- **vCluster**: Virtual clusters for GPU isolation, VPN for hybrid networking
- **Spectro Cloud Palette**: Multi-cloud Kubernetes management
- **OpenAI Pattern**: 25K GPUs, custom operators, 97% utilization

**Source:** [vCluster AI Platform](https://www.vcluster.com/blog/vcluster-ai-platform-nvidia-gpu-kubernetes)

### 1.5 Use Case Deployment Platforms

| Platform | Approach | Key Components |
|----------|----------|----------------|
| TrueFoundry | MCP Gateway Blueprint | AI Gateway + Deployment Layer + Observability |
| NVIDIA RAG Blueprint | Helm-based microservices | LLM NIM + Embedding NIM + Vector DB + Orchestrator |
| Dify | Visual workflow + plugin marketplace | LLM Orchestration + Visual Studio + Deployment Hub |
| RunPod | Serverless templates | GPU pods + Container templates + Autoscaling |
| Flowise/LangFlow | Visual drag-drop builders | Chatflow + Agentflow + RAG components |

---

## Part 2: Unified Architecture Proposal

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        BUD AI FOUNDRY - UNIFIED PLATFORM                         │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │                         CUSTOMER INTERFACE LAYER                         │   │
│   │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐│   │
│   │  │  BudAdmin    │  │ BudPlayground│  │   REST API   │  │     CLI      ││   │
│   │  │  Dashboard   │  │  Inference   │  │   /api/v1    │  │   bud-cli    ││   │
│   │  │  + Schedule  │  │              │  │              │  │              ││   │
│   │  │    Timeline  │  │              │  │              │  │              ││   │
│   │  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘│   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                         │                                       │
│   ┌─────────────────────────────────────▼───────────────────────────────────┐   │
│   │                    ORCHESTRATION LAYER (Pipelines & Templates)           │   │
│   │                                                                          │   │
│   │   ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐     │   │
│   │   │   BudUseCases   │    │   BudCompute    │    │   BudPipeline   │     │   │
│   │   │                 │    │  (Optional)     │    │                 │     │   │
│   │   │ • Templates     │    │ • GPU Pools     │    │ • Owns Pipelines│     │   │
│   │   │ • Components    │    │ • Serverless    │    │ • Owns Steps    │     │   │
│   │   │ • RAG/Chat/Agent│    │ • Pods          │    │ • DAG Execution │     │   │
│   │   │                 │    │                 │    │ • Cron/Events   │     │   │
│   │   │ Creates ────────┼────┼─────────────────┼───►│ Triggers        │     │   │
│   │   │ Pipelines       │    │                 │    │                 │     │   │
│   │   └─────────────────┘    └────────┬────────┘    └────────┬────────┘     │   │
│   │                                   │                      │              │   │
│   │                                   │        Only JOB-type │              │   │
│   │                                   │        steps create  │              │   │
│   └───────────────────────────────────┼──────────Jobs────────┼──────────────┘   │
│                                       │                      │                  │
│   ┌───────────────────────────────────▼──────────────────────▼──────────────┐   │
│   │                    JOB LAYER (Atomic Scheduling Unit)                    │   │
│   │                                                                          │   │
│   │   BudCluster OWNS Jobs                                                  │   │
│   │   ┌─────────────────────────────────────────────────────────────────┐   │   │
│   │   │                                                                  │   │   │
│   │   │  jobs table: id, type, status, resources, schedule, cost        │   │   │
│   │   │                                                                  │   │   │
│   │   │  Job Types:           Sources:           Scheduling:            │   │   │
│   │   │  • SERVICE (deploy)   • DIRECT (BudApp)  • Kueue admission      │   │   │
│   │   │  • BATCH (run task)   • PIPELINE         • Priority/preemption  │   │   │
│   │   │  • TRAINING           • USECASE          • Time windows         │   │   │
│   │   │                                                                  │   │   │
│   │   │  Timeline API: GET /clusters/{id}/schedule (for UI)             │   │   │
│   │   │                                                                  │   │   │
│   │   └─────────────────────────────────────────────────────────────────┘   │   │
│   │                                   │                                      │   │
│   │   ┌───────────────────────────────┼───────────────────────────────┐     │   │
│   │   │  Kueue + MultiKueue           │          BudQueue             │     │   │
│   │   │  • Quota enforcement          │          (Serverless only)    │     │   │
│   │   │  • Fair-share (Cohorts)       │          • Request queue      │     │   │
│   │   │  • Multi-cluster dispatch     │          • Warm pools         │     │   │
│   │   └───────────────────────────────┼───────────────────────────────┘     │   │
│   └───────────────────────────────────┼─────────────────────────────────────┘   │
│                                       │                                         │
│   ┌───────────────────────────────────▼─────────────────────────────────────┐   │
│   │                    INFRASTRUCTURE LAYER (Execution)                      │   │
│   │                                                                          │   │
│   │   ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐     │   │
│   │   │   BudCluster    │    │   BudGateway    │    │   BudMetrics    │     │   │
│   │   │  (Deployment)   │    │                 │    │  (Extended)     │     │   │
│   │   │                 │    │ • Request Route │    │                 │     │   │
│   │   │ • Helm/Docker/  │    │ • Load Balance  │    │ • Job cost track│     │   │
│   │   │   Model deploy  │    │ • Provider API  │    │ • GPU metering  │     │   │
│   │   │ • Kueue submit  │    │ • Rate Limit    │    │ • Per-sec bill  │     │   │
│   │   │ • HAMI/MIG      │    │                 │    │ • Usage APIs    │     │   │
│   │   └─────────────────┘    └─────────────────┘    └─────────────────┘     │   │
│   │                                                                          │   │
│   │   ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐     │   │
│   │   │   BudApp        │    │   BudSim        │    │   BudModel      │     │   │
│   │   │  (Endpoints)    │    │  (Optimizer)    │    │  (Registry)     │     │   │
│   │   │  stores job_id  │    │                 │    │                 │     │   │
│   │   └─────────────────┘    └─────────────────┘    └─────────────────┘     │   │
│   └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │                         GPU INFRASTRUCTURE                               │   │
│   │                                                                          │   │
│   │   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐│   │
│   │   │ AWS EKS GPU  │  │ Azure AKS GPU│  │  On-Prem GPU │  │ Community    ││   │
│   │   │  Clusters    │  │   Clusters   │  │   Clusters   │  │ GPU Hosts    ││   │
│   │   │              │  │              │  │              │  │ (P2P Future) ││   │
│   │   │ A100,H100,T4 │  │ A100,H100,T4 │  │ Any NVIDIA   │  │              ││   │
│   │   └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘│   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 2.1.1 Data Flow Summary

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              DATA FLOW                                           │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   USER ACTIONS                           DATA OWNERSHIP                          │
│   ────────────                           ──────────────                          │
│                                                                                 │
│   Deploy Template ──► BudUseCases ──► BudPipeline ──► BudCluster               │
│                       (templates)     (pipelines)     (jobs)                    │
│                                                                                 │
│   Deploy Endpoint ──► BudApp ─────────────────────►  BudCluster                │
│                       (endpoints)                     (jobs)                    │
│                                                                                 │
│   View Schedule ───► BudAdmin ──► BudCluster.GET /clusters/{id}/schedule       │
│                                   (jobs with estimated_start/end)              │
│                                                                                 │
│   ─────────────────────────────────────────────────────────────────────────────│
│                                                                                 │
│   SERVICE              OWNS                  STORES REFERENCE TO               │
│   ───────              ────                  ──────────────────                 │
│   BudCluster           Jobs                  -                                  │
│   BudPipeline          Pipelines, Steps      job_id (in steps)                 │
│   BudUseCases          Templates, Components -                                  │
│   BudApp               Endpoints             job_id (in endpoints)             │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 New Services Required

| Service | Purpose | Required? | Key Capabilities |
|---------|---------|-----------|------------------|
| **BudCompute** | GPU-as-a-Service core | **Optional** | GPU pools, serverless endpoints, pod management, cross-cluster inventory |
| **BudQueue** | Request queue management | **Optional** | Priority queuing, admission control, warm pools (for serverless only) |
| **BudUseCases** | Use case templates | **Optional** | RAG, chatbot, agent templates, component registry |

> **Note:** BudCompute is only needed for GPU-as-a-Service features (pools, pods, serverless).
> Basic model deployment works without it via BudCluster directly.

### 2.2.1 Job & Pipeline Layer (New)

| Concept | Owner | Description |
|---------|-------|-------------|
| **Job** | BudCluster | Atomic scheduling unit. Every deployment creates a Job. Tracked in `jobs` table. |
| **Pipeline** | BudPipeline | Collection of Steps with trigger (cron/event/manual). |
| **Step** | BudPipeline | Unit within Pipeline. Only `JOB`-type steps create Jobs. Other types: `API_CALL`, `FUNCTION`, `CONDITION`, `WAIT`, etc. |

```
Step Types:
├── JOB (creates Job) ────► Scheduled by Kueue, appears on timeline
├── API_CALL ─────────────► Runs in BudPipeline (no resources)
├── FUNCTION ─────────────► Runs in BudPipeline (no resources)
├── CONDITION ────────────► Flow control (if/else)
├── NOTIFICATION ─────────► Send alert
└── WAIT ─────────────────► Delay or wait for event
```

### 2.2.1 Existing Services Extended

| Service | Extension | New Capabilities |
|---------|-----------|------------------|
| **BudCluster** | Kueue + MultiKueue | Quota enforcement, fair-share scheduling, multi-cluster dispatch, job-type limits |
| **BudCluster** | Monitoring Deployment | Deploys in-cluster Prometheus + DCGM exporters during cluster registration |
| **BudMetrics** | Metering & Billing | Per-second GPU tracking, cost attribution, billing API, usage aggregation |

> **Architecture Decision:** BudScheduler has been **removed**. Kueue handles all scheduling
> concerns (quotas, fair-share, multi-cluster) and is integrated directly into BudCluster.
> See [Appendix B: Decision Log](#appendix-b-decision-log) for rationale.

### 2.3 Service Responsibilities Matrix

```
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│                              SERVICE RESPONSIBILITY MATRIX                                 │
├───────────────┬───────────────────────────────────────────────────────────────────────────┤
│ Capability    │ BudCluster  BudCompute(Opt)  BudQueue  BudMetrics(Ext)  BudUseCases      │
├───────────────┼───────────────────────────────────────────────────────────────────────────┤
│ Cluster Mgmt  │    ★★★          -              -           -              -              │
│ Helm Deploy   │    ★★★          ★              -           -              ★              │
│ Kueue/Sched   │    ★★★          ★              ★           -              -              │
│ Quota Enforce │    ★★★          ★              -           -              -              │
│ Fair-share    │    ★★★          -              -           -              -              │
│ Multi-cluster │    ★★★          ★              -           -              -              │
│ GPU Pool Mgmt │     ★          ★★★             -           ★              -              │
│ Serverless    │     ★          ★★★            ★★★          ★              -              │
│ Pods          │    ★★          ★★★             ★           ★              -              │
│ Queuing       │     -           ★             ★★★          -              -              │
│ Warm Pools    │     -          ★★             ★★★          -              -              │
│ Metering      │     -           ★              ★          ★★★             -              │
│ Billing       │     -           -              -          ★★★             -              │
│ Metrics Recv  │     -           -              -          ★★★             -              │
│ Mon. Deploy   │    ★★★          -              -           -              -              │
│ Use Cases     │     ★           ★              -           -             ★★★             │
│ Templates     │     -           -              -           -             ★★★             │
├───────────────┼───────────────────────────────────────────────────────────────────────────┤
│ Legend: ★★★ Primary, ★★ Secondary, ★ Integration, - Not applicable                       │
│ Note: BudCompute is optional - basic deployment works via BudCluster directly             │
└───────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Part 3: BudCompute - GPU-as-a-Service Core (Optional)

> **Note:** BudCompute is an **optional** service for advanced GPU-as-a-Service features.
> Basic model deployment works without it - users can deploy directly via BudCluster.
> Enable BudCompute when you need: GPU pools, RunPod-like pods, serverless endpoints, or cross-cluster inventory.

### 3.1 Deployment Models (Like RunPod)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         BUDCOMPUTE DEPLOYMENT MODELS                             │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │ MODEL 1: PODS (Persistent GPU Instances)                                 │   │
│   │                                                                          │   │
│   │ • Dedicated GPU access (full, MIG, or time-sliced)                       │   │
│   │ • Persistent storage                                                     │   │
│   │ • SSH access option                                                      │   │
│   │ • Long-running workloads (training, fine-tuning, development)            │   │
│   │ • Per-hour billing                                                       │   │
│   │                                                                          │   │
│   │ User → Create Pod → Provision GPU Node → Connect (SSH/Jupyter/VSCode)    │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │ MODEL 2: SERVERLESS ENDPOINTS (Auto-scaling)                             │   │
│   │                                                                          │   │
│   │ • Scale-to-zero capability                                               │   │
│   │ • Automatic scaling based on queue depth                                 │   │
│   │ • Per-second billing (only when processing)                              │   │
│   │ • Warm pool for fast cold starts                                         │   │
│   │ • API inference workloads                                                │   │
│   │                                                                          │   │
│   │ Request → Queue → (Warm Pool | Cold Start) → Process → Scale Down        │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │ MODEL 3: USE CASE DEPLOYMENTS (Template-based)                           │   │
│   │                                                                          │   │
│   │ • Pre-configured RAG, Chatbot, Agent stacks                              │   │
│   │ • Multi-component deployment (Vector DB + Models + Orchestrator)         │   │
│   │ • Hybrid billing (infra + usage)                                         │   │
│   │ • Managed lifecycle                                                      │   │
│   │                                                                          │   │
│   │ Template → Configure → Deploy Stack → Manage Lifecycle → Monitor         │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 GPU Pool Management Schema

```python
# Proposed BudCompute Schema
class GPUPool(SQLModel):
    """GPU Pool representing available capacity"""
    id: UUID
    name: str
    cluster_id: UUID

    # Pool configuration
    gpu_type: str  # "A100-80GB", "H100-SXM", "RTX-4090"
    sharing_mode: GPUSharingMode  # FULL, MIG, TIME_SLICE

    # Capacity
    total_gpus: int
    available_gpus: int
    reserved_gpus: int

    # Pricing tier
    tier: GPUTier  # SECURE_CLOUD, COMMUNITY_CLOUD, ON_PREM
    price_per_hour: Decimal
    price_per_second: Decimal

    # Warm pool settings (for serverless)
    warm_pool_size: int = 0
    warm_pool_timeout_seconds: int = 300

    # MIG configuration (if applicable)
    mig_profile: Optional[str]  # "1g.5gb", "2g.10gb", "3g.20gb", etc.
    mig_instances_per_gpu: Optional[int]

class GPUAllocation(SQLModel):
    """Individual GPU allocation to a workload"""
    id: UUID
    pool_id: UUID
    workload_id: UUID  # Pod, Serverless Endpoint, or UseCase
    workload_type: WorkloadType

    # Allocation details
    gpu_count: int
    sharing_mode: GPUSharingMode
    mig_profile: Optional[str]

    # Timing
    allocated_at: datetime
    released_at: Optional[datetime]

    # Metering
    compute_seconds: int = 0
    last_metered_at: datetime
```

### 3.3 Serverless Endpoint Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                     SERVERLESS ENDPOINT ARCHITECTURE                             │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   ┌───────────┐                                                                 │
│   │  Request  │                                                                 │
│   │  Ingress  │                                                                 │
│   └─────┬─────┘                                                                 │
│         │                                                                       │
│   ┌─────▼─────────────────────────────────────────────────────────────────┐     │
│   │                         BUD GATEWAY                                   │     │
│   │  • Rate limiting    • Auth    • Load balancing    • Routing          │     │
│   └─────┬─────────────────────────────────────────────────────────────────┘     │
│         │                                                                       │
│   ┌─────▼─────────────────────────────────────────────────────────────────┐     │
│   │                         BUD QUEUE                                     │     │
│   │                                                                       │     │
│   │  ┌─────────────────────────────────────────────────────────────────┐ │     │
│   │  │ Priority Queues                                                  │ │     │
│   │  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │ │     │
│   │  │  │ Premium  │  │ Standard │  │   Spot   │  │  Batch   │        │ │     │
│   │  │  │ (P0)     │  │ (P1)     │  │ (P2)     │  │ (P3)     │        │ │     │
│   │  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │ │     │
│   │  └─────────────────────────────────────────────────────────────────┘ │     │
│   │                                                                       │     │
│   │  ┌─────────────────────────────────────────────────────────────────┐ │     │
│   │  │ Admission Control                                                │ │     │
│   │  │  • Quota check    • Rate limit    • Budget check                │ │     │
│   │  └─────────────────────────────────────────────────────────────────┘ │     │
│   └─────┬─────────────────────────────────────────────────────────────────┘     │
│         │                                                                       │
│   ┌─────▼─────────────────────────────────────────────────────────────────┐     │
│   │                         BUD SCHEDULER                                 │     │
│   │                                                                       │     │
│   │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐   │     │
│   │  │   Warm Pool      │  │   Cold Start     │  │   Preemption     │   │     │
│   │  │   (< 500ms)      │  │   (10-60s)       │  │   (if needed)    │   │     │
│   │  │                  │  │                  │  │                  │   │     │
│   │  │  Pre-loaded:     │  │  On-demand:      │  │  Priority-based: │   │     │
│   │  │  • Container     │  │  • Pull image    │  │  • Bump low-pri  │   │     │
│   │  │  • Model weights │  │  • Load model    │  │  • Reschedule    │   │     │
│   │  │  • CUDA context  │  │  • Warm CUDA     │  │  • Queue evicted │   │     │
│   │  └──────────────────┘  └──────────────────┘  └──────────────────┘   │     │
│   └─────┬─────────────────────────────────────────────────────────────────┘     │
│         │                                                                       │
│   ┌─────▼─────────────────────────────────────────────────────────────────┐     │
│   │                         GPU WORKER POOL                               │     │
│   │                                                                       │     │
│   │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐   │     │
│   │  │Worker 1 │  │Worker 2 │  │Worker 3 │  │Worker N │  │ (scale) │   │     │
│   │  │ A100    │  │ A100    │  │ H100    │  │ H100    │  │         │   │     │
│   │  │ vLLM    │  │ vLLM    │  │ vLLM    │  │ vLLM    │  │         │   │     │
│   │  └─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘   │     │
│   └───────────────────────────────────────────────────────────────────────┘     │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 3.4 Cold Start Optimization Strategy

Based on [Modal's GPU snapshotting](https://modal.com/blog/mistral-3) (10x faster cold starts):

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      COLD START OPTIMIZATION LAYERS                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  Layer 1: CONTAINER CACHING                                         ~5-10s     │
│  ┌────────────────────────────────────────────────────────────────────────┐    │
│  │ • Pre-pull common base images to all GPU nodes                         │    │
│  │ • Registry mirror close to compute (MinIO/Harbor)                      │    │
│  │ • Multi-stage builds with minimal runtime images                       │    │
│  └────────────────────────────────────────────────────────────────────────┘    │
│                                                                                 │
│  Layer 2: MODEL WEIGHT CACHING                                      ~10-30s    │
│  ┌────────────────────────────────────────────────────────────────────────┐    │
│  │ • Network volumes (NFS/EFS) with model weights pre-loaded              │    │
│  │ • Local NVMe cache on GPU nodes                                        │    │
│  │ • Model sharding for parallel loading                                  │    │
│  └────────────────────────────────────────────────────────────────────────┘    │
│                                                                                 │
│  Layer 3: GPU MEMORY SNAPSHOTTING                                   ~1-5s      │
│  ┌────────────────────────────────────────────────────────────────────────┐    │
│  │ • CUDA context checkpoint/restore                                      │    │
│  │ • Model weights pre-loaded in GPU memory                               │    │
│  │ • vLLM KV cache pre-warmed                                             │    │
│  │ • Requires: NVIDIA CUDA 12+, kernel support, custom orchestration      │    │
│  └────────────────────────────────────────────────────────────────────────┘    │
│                                                                                 │
│  Layer 4: WARM POOL (Target)                                        <500ms     │
│  ┌────────────────────────────────────────────────────────────────────────┐    │
│  │ • Pre-provisioned containers with loaded models                        │    │
│  │ • Idle timeout management (cost vs. latency tradeoff)                  │    │
│  │ • Predictive pre-warming based on traffic patterns                     │    │
│  │ • Pool size auto-adjustment (ML-based prediction)                      │    │
│  └────────────────────────────────────────────────────────────────────────┘    │
│                                                                                 │
│  IMPLEMENTATION PRIORITY:                                                       │
│  Phase 1: Container + Model caching (immediate value)                          │
│  Phase 2: Warm pool with configurable size                                     │
│  Phase 3: GPU snapshotting (advanced, requires R&D)                            │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Part 4: BudCluster Scheduling - Kueue + MultiKueue

> **Architecture Decision:** BudScheduler has been **removed** as a separate service.
> Kueue handles all scheduling concerns and is integrated directly into BudCluster.
> This avoids an unnecessary service layer while providing enterprise-grade scheduling.

### 4.1 Scheduling Architecture (Kueue in BudCluster)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    BUDCLUSTER SCHEDULING ARCHITECTURE                            │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   BudCluster now includes:                                                      │
│   • Kueue installation during cluster registration                              │
│   • MultiKueue for cross-cluster scheduling                                     │
│   • Quota enforcement before Helm deployment                                    │
│   • Fair-share configuration                                                    │
│                                                                                 │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │                      MANAGER CLUSTER                                    │   │
│   │                                                                          │   │
│   │  ┌─────────────────────────────────────────────────────────────────┐    │   │
│   │  │ Kueue + MultiKueue Controller                                   │    │   │
│   │  │                                                                  │    │   │
│   │  │ • Receives workload submissions                                 │    │   │
│   │  │ • Checks quota against ClusterQueues                            │    │   │
│   │  │ • Dispatches to worker cluster with capacity                    │    │   │
│   │  │ • Syncs status back                                             │    │   │
│   │  └─────────────────────────────────────────────────────────────────┘    │   │
│   │                                                                          │   │
│   │  ┌─────────────────────────────────────────────────────────────────┐    │   │
│   │  │ ClusterQueues (Job-Type Quotas)                                 │    │   │
│   │  │                                                                  │    │   │
│   │  │  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐       │    │   │
│   │  │  │ model-endpoints│  │ serverless    │  │ usecases      │       │    │   │
│   │  │  │               │  │               │  │               │       │    │   │
│   │  │  │ A100: 100     │  │ A100: 50      │  │ A100: 30      │       │    │   │
│   │  │  │ H100: 50      │  │ H100: 25      │  │ H100: 15      │       │    │   │
│   │  │  └───────────────┘  └───────────────┘  └───────────────┘       │    │   │
│   │  └─────────────────────────────────────────────────────────────────┘    │   │
│   │                                                                          │   │
│   │  ┌─────────────────────────────────────────────────────────────────┐    │   │
│   │  │ Cohorts (Fair-Share Groups)                                     │    │   │
│   │  │                                                                  │    │   │
│   │  │  tenant-a-cohort ←→ tenant-b-cohort (can borrow idle GPUs)     │    │   │
│   │  └─────────────────────────────────────────────────────────────────┘    │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                         │                                       │
│              ┌──────────────────────────┼──────────────────────────┐            │
│              │                          │                          │            │
│        ┌─────▼─────┐              ┌─────▼─────┐              ┌─────▼─────┐      │
│        │ Worker 1  │              │ Worker 2  │              │ Worker 3  │      │
│        │ AWS EKS   │              │ Azure AKS │              │ On-Prem   │      │
│        │           │              │           │              │           │      │
│        │ • Kueue   │              │ • Kueue   │              │ • Kueue   │      │
│        │ • HAMI    │              │ • HAMI    │              │ • HAMI    │      │
│        │ • A100x8  │              │ • H100x4  │              │ • RTX4090 │      │
│        └───────────┘              └───────────┘              └───────────┘      │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Deployment Flow with Kueue

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    DEPLOYMENT FLOW WITH KUEUE                                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   BASIC DEPLOYMENT (Current behavior preserved)                                 │
│   ─────────────────────────────────────────────                                 │
│                                                                                 │
│   POST /deployment                                                              │
│        ↓                                                                        │
│   BudCluster.deploy()                                                           │
│        ↓                                                                        │
│   Check Kueue quota (tenant + job-type)                                         │
│        ↓                                                                        │
│   ┌─────────────────┐    ┌─────────────────┐                                   │
│   │ Quota Available │    │ Quota Exceeded  │                                   │
│   │       ↓         │    │       ↓         │                                   │
│   │ Helm deploy     │    │ Return 429 or   │                                   │
│   │ (as before)     │    │ queue request   │                                   │
│   └─────────────────┘    └─────────────────┘                                   │
│        ↓                                                                        │
│   hami-scheduler places pods                                                    │
│        ↓                                                                        │
│   Kueue tracks usage for fair-share                                             │
│                                                                                 │
│   ─────────────────────────────────────────────────────────────────────────     │
│                                                                                 │
│   MULTI-CLUSTER DEPLOYMENT (With MultiKueue)                                    │
│   ──────────────────────────────────────────                                    │
│                                                                                 │
│   POST /deployment (to any cluster or Manager)                                  │
│        ↓                                                                        │
│   MultiKueue finds worker with capacity                                         │
│        ↓                                                                        │
│   Workload dispatched to selected worker                                        │
│        ↓                                                                        │
│   Worker's BudCluster executes Helm deploy                                      │
│        ↓                                                                        │
│   Status synced back to Manager                                                 │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 4.3 What BudCluster Installs During Registration

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    CLUSTER REGISTRATION (Updated)                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   During cluster registration, BudCluster now deploys:                          │
│                                                                                 │
│   EXISTING (No change):                                                         │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │ 1. Node Feature Discovery (NFD) - Hardware detection                    │   │
│   │ 2. GPU Operator - NVIDIA drivers + device plugin                        │   │
│   │ 3. HAMI - GPU time-slicing scheduler                                    │   │
│   │ 4. Prometheus stack - Metrics collection                                │   │
│   │ 5. Aibrix components - ML framework support                             │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│   NEW (Added):                                                                  │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │ 6. Kueue - Quota and admission control                                  │   │
│   │    • Helm: kueue/kueue                                                  │   │
│   │    • Namespace: kueue-system                                            │   │
│   │                                                                          │   │
│   │ 7. MultiKueue Worker Config - Cross-cluster registration                │   │
│   │    • AdmissionCheck for remote dispatch                                 │   │
│   │    • MultiKueueCluster pointing to Manager                              │   │
│   │                                                                          │   │
│   │ 8. Default ClusterQueues - Based on detected GPU types                  │   │
│   │    • Auto-created from NFD labels                                       │   │
│   │    • ResourceFlavors for A100, H100, T4, etc.                          │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 4.4 Job-Type Quota Configuration

```yaml
# Example: Quotas per job type (managed by BudCluster API)
# POST /clusters/{id}/quotas

# ClusterQueue for model endpoints
apiVersion: kueue.x-k8s.io/v1beta1
kind: ClusterQueue
metadata:
  name: model-endpoints
spec:
  cohort: platform-gpu-pool  # For fair-share borrowing
  resourceGroups:
  - coveredResources: ["nvidia.com/gpu"]
    flavors:
    - name: a100-80gb
      resources:
      - name: "nvidia.com/gpu"
        nominalQuota: 100
        borrowingLimit: 20
    - name: h100-sxm
      resources:
      - name: "nvidia.com/gpu"
        nominalQuota: 50
        borrowingLimit: 10
---
# ClusterQueue for serverless endpoints
apiVersion: kueue.x-k8s.io/v1beta1
kind: ClusterQueue
metadata:
  name: serverless-endpoints
spec:
  cohort: platform-gpu-pool
  resourceGroups:
  - coveredResources: ["nvidia.com/gpu"]
    flavors:
    - name: a100-80gb
      resources:
      - name: "nvidia.com/gpu"
        nominalQuota: 50
        borrowingLimit: 30
---
# ClusterQueue for use-case deployments
apiVersion: kueue.x-k8s.io/v1beta1
kind: ClusterQueue
metadata:
  name: usecase-deployments
spec:
  cohort: platform-gpu-pool
  resourceGroups:
  - coveredResources: ["nvidia.com/gpu"]
    flavors:
    - name: a100-80gb
      resources:
      - name: "nvidia.com/gpu"
        nominalQuota: 30
        borrowingLimit: 10
```

### 4.5 BudCluster Quota API

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    BUDCLUSTER QUOTA API (NEW ENDPOINTS)                          │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   Quota Management:                                                             │
│   ─────────────────                                                             │
│   GET  /clusters/{id}/quotas              # List all quotas for cluster         │
│   POST /clusters/{id}/quotas              # Create quota (ClusterQueue)         │
│   PUT  /clusters/{id}/quotas/{name}       # Update quota                        │
│   DEL  /clusters/{id}/quotas/{name}       # Delete quota                        │
│                                                                                 │
│   Tenant Queue Management:                                                      │
│   ────────────────────────                                                      │
│   GET  /clusters/{id}/queues              # List LocalQueues                    │
│   POST /clusters/{id}/queues              # Create tenant queue                 │
│   PUT  /clusters/{id}/queues/{name}       # Update tenant queue                 │
│                                                                                 │
│   Usage & Metrics:                                                              │
│   ────────────────                                                              │
│   GET  /clusters/{id}/usage               # Current usage by queue              │
│   GET  /clusters/{id}/usage/{tenant}      # Tenant-specific usage               │
│   GET  /clusters/{id}/capacity            # Available capacity                  │
│                                                                                 │
│   Fair-Share:                                                                   │
│   ───────────                                                                   │
│   GET  /clusters/{id}/cohorts             # List cohorts                        │
│   POST /clusters/{id}/cohorts             # Create cohort                       │
│   PUT  /clusters/{id}/cohorts/{name}      # Update cohort membership            │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 4.6 GPU Partitioning Layer (Unchanged)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      GPU PARTITIONING LAYER                                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐              │
│  │ NVIDIA MIG       │  │ HAMI Time-Slice  │  │ Full GPU         │              │
│  │                  │  │                  │  │                  │              │
│  │ Hard isolation   │  │ Soft sharing     │  │ Dedicated        │              │
│  │ A100/H100 only   │  │ Any NVIDIA GPU   │  │ All GPUs         │              │
│  │ 7 profiles       │  │ Configurable %   │  │ Best performance │              │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘              │
│                                                                                 │
│  Selection: Kueue ResourceFlavors + HAMI scheduler (unchanged)                 │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Part 5: Job & Pipeline Layer

> **Key Insight:** Everything deployed to a cluster is a **Job**. Jobs are the atomic scheduling unit.
> Pipelines orchestrate multiple Steps, but only **JOB-type steps** create actual Jobs for resource scheduling.

### 5.1 Job Abstraction

A **Job** is the atomic unit of work that requires cluster resources (GPU, CPU, memory). Jobs are:
- Scheduled by Kueue (resource-based admission)
- Tracked on the cluster timeline (for resource visibility)
- Metered for cost (by BudMetrics)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         JOB: ATOMIC SCHEDULING UNIT                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   What creates Jobs:                                                            │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │ • Direct API call: POST /api/v1/jobs (standalone job)                   │   │
│   │ • Pipeline step with type=JOB (pipeline creates job)                    │   │
│   │ • BudUseCases template deployment (each component → job)                │   │
│   │ • BudCompute pod/serverless creation (each → job)                       │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│   What Jobs represent:                                                          │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │ • Model endpoint deployment (SERVICE job)                               │   │
│   │ • Database/service deployment (SERVICE job)                             │   │
│   │ • Batch inference task (BATCH job)                                      │   │
│   │ • Training/fine-tuning task (TRAINING job)                              │   │
│   │ • Any workload consuming cluster resources                              │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

#### 5.1.1 Job Schema

```python
class JobType(str, Enum):
    SERVICE = "service"       # Long-running deployment (model endpoint, database, UI)
    BATCH = "batch"           # Run-to-completion task (inference batch, data processing)
    TRAINING = "training"     # Model training/fine-tuning (with checkpoints, resumable)

class JobStatus(str, Enum):
    PENDING = "pending"       # Created, waiting for scheduling
    QUEUED = "queued"         # In Kueue, waiting for resources
    SCHEDULED = "scheduled"   # Resources allocated, starting
    RUNNING = "running"       # Actively executing
    COMPLETED = "completed"   # Finished successfully
    FAILED = "failed"         # Finished with error
    CANCELLED = "cancelled"   # Manually stopped
    PREEMPTED = "preempted"   # Stopped by higher priority job

class JobPriority(str, Enum):
    CRITICAL = "critical"     # Cannot be preempted, highest priority
    HIGH = "high"             # Production workloads
    NORMAL = "normal"         # Default
    LOW = "low"               # Background tasks
    SPOT = "spot"             # Use preemptible/spot resources, lowest cost


class Job(SQLModel):
    """
    Job = Atomic scheduling unit. This is what Kueue schedules and what
    appears on the cluster resource timeline.
    """
    id: UUID
    name: str
    tenant_id: UUID
    project_id: UUID
    cluster_id: UUID

    # Source tracking
    pipeline_id: Optional[UUID]       # Null for standalone jobs
    pipeline_step_id: Optional[UUID]  # The step that created this job
    usecase_deployment_id: Optional[UUID]  # If created by BudUseCases

    # Job classification
    job_type: JobType                 # SERVICE, BATCH, TRAINING

    # What to deploy/run
    deployment_type: DeploymentType   # HELM, DOCKER, MODEL
    spec: dict                        # Deployment specification (component config)

    # Resource requirements (FOR KUEUE SCHEDULING)
    gpu_type: Optional[str]           # "nvidia-a100-80gb", "nvidia-h100-sxm"
    gpu_count: int = 0
    cpu_cores: float = 1.0
    memory_gb: float = 4.0
    storage_gb: Optional[int]

    # Time constraints
    estimated_duration_seconds: Optional[int]  # For scheduling estimates
    max_duration_seconds: Optional[int]        # Kill if exceeds (timeout)
    deadline: Optional[datetime]               # Must complete by this time

    # Priority & preemption
    priority: JobPriority = JobPriority.NORMAL
    preemptible: bool = False         # Can be stopped by higher priority
    preempts_others: bool = False     # Can stop lower priority jobs

    # Schedule tracking (FOR UI TIMELINE)
    estimated_start: Optional[datetime]   # Calculated based on queue position
    estimated_end: Optional[datetime]     # estimated_start + estimated_duration
    actual_start: Optional[datetime]
    actual_end: Optional[datetime]

    # Status
    status: JobStatus = JobStatus.PENDING
    status_message: Optional[str]
    retry_count: int = 0
    max_retries: int = 3

    # Cost tracking
    estimated_cost: Optional[Decimal]
    actual_cost: Optional[Decimal]
    budget_limit: Optional[Decimal]   # Fail if cost exceeds

    # Outputs (for dependent jobs/steps)
    outputs: dict = {}                # {"url": "http://...", "api_key": "..."}

    # Timestamps
    created_at: datetime
    updated_at: datetime
```

#### 5.1.2 Job API (BudCluster)

```yaml
# Job Management API
POST   /api/v1/jobs                    # Create job (standalone or from pipeline)
GET    /api/v1/jobs                    # List jobs (with filters)
GET    /api/v1/jobs/{id}               # Get job details
DELETE /api/v1/jobs/{id}               # Cancel job
POST   /api/v1/jobs/{id}/retry         # Retry failed job

# Job Scheduling
GET    /api/v1/jobs/{id}/schedule      # Get estimated schedule
PUT    /api/v1/jobs/{id}/priority      # Update priority
POST   /api/v1/jobs/{id}/preempt       # Manually preempt (admin)

# Cluster Schedule View
GET    /api/v1/clusters/{id}/schedule  # Get all jobs timeline for cluster
GET    /api/v1/clusters/{id}/resources # Get resource availability forecast
```

### 5.2 Pipeline & Step Types

A **Pipeline** is a collection of **Steps** with dependencies. Steps can be of different types,
and only **JOB-type steps** create actual Jobs for resource scheduling.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              STEP TYPES                                          │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   RESOURCE STEPS (Create Jobs → Appear on Timeline)                            │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │ JOB          │ Deploy/run something that needs GPU/CPU/memory           │   │
│   │              │ → Creates a Job → Scheduled by Kueue                     │   │
│   │              │ Examples: deploy model, run training, batch inference    │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│   FUNCTIONAL STEPS (No Jobs → Run in Pipeline Engine)                          │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │ API_CALL     │ HTTP request to internal/external service                │   │
│   │              │ Examples: call BudSim, fetch config, trigger webhook     │   │
│   ├──────────────┼──────────────────────────────────────────────────────────┤   │
│   │ FUNCTION     │ Lightweight code execution in pipeline engine            │   │
│   │              │ Examples: transform data, validate output, compute value │   │
│   ├──────────────┼──────────────────────────────────────────────────────────┤   │
│   │ NOTIFICATION │ Send alert/message                                       │   │
│   │              │ Examples: Slack, email, webhook, PagerDuty               │   │
│   ├──────────────┼──────────────────────────────────────────────────────────┤   │
│   │ TRANSFORM    │ Data transformation (lightweight)                        │   │
│   │              │ Examples: parse JSON, extract fields, format output      │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│   CONTROL STEPS (No Jobs → Pipeline Flow Control)                              │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │ CONDITION    │ If/else branching based on expression                    │   │
│   │              │ Example: if params.enable_reranker then deploy_reranker  │   │
│   ├──────────────┼──────────────────────────────────────────────────────────┤   │
│   │ PARALLEL     │ Fan-out to run multiple steps concurrently               │   │
│   │              │ Example: deploy embedding AND llm in parallel            │   │
│   ├──────────────┼──────────────────────────────────────────────────────────┤   │
│   │ WAIT         │ Pause execution (time delay or wait for event)           │   │
│   │              │ Example: wait 60 seconds, wait for webhook               │   │
│   ├──────────────┼──────────────────────────────────────────────────────────┤   │
│   │ LOOP         │ Iterate over a collection                                │   │
│   │              │ Example: for each model in models, deploy endpoint       │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

#### 5.2.1 Pipeline & Step Schema

```python
class StepType(str, Enum):
    # Resource step → Creates Job
    JOB = "job"

    # Functional steps → Run in pipeline engine (no Job)
    API_CALL = "api_call"
    FUNCTION = "function"
    NOTIFICATION = "notification"
    TRANSFORM = "transform"

    # Control steps → Pipeline flow control (no Job)
    CONDITION = "condition"
    PARALLEL = "parallel"
    WAIT = "wait"
    LOOP = "loop"

class TriggerType(str, Enum):
    MANUAL = "manual"           # Started by user/API
    SCHEDULED = "scheduled"     # Cron-based
    EVENT = "event"             # Webhook, data arrival, etc.
    PIPELINE = "pipeline"       # Triggered by another pipeline completing

class StepStatus(str, Enum):
    PENDING = "pending"
    WAITING = "waiting"         # Waiting for dependencies
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"         # Condition evaluated to false


class Pipeline(SQLModel):
    """
    Pipeline = Collection of Steps with trigger configuration.
    Managed by BudPipeline service.
    """
    id: UUID
    name: str
    tenant_id: UUID
    project_id: UUID

    # Trigger configuration (when/how pipeline starts)
    trigger_type: TriggerType
    cron_expression: Optional[str]         # For SCHEDULED: "0 2 * * *"
    event_config: Optional[dict]           # For EVENT: webhook, S3 path, etc.
    triggered_by_pipeline_id: Optional[UUID]  # For PIPELINE trigger

    # Time constraints (pipeline level)
    timeout_seconds: Optional[int]         # Max total duration
    deadline: Optional[datetime]           # Must complete by

    # Status
    status: PipelineStatus
    current_step_id: Optional[UUID]

    # Timestamps
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    # Metadata
    template_id: Optional[str]             # If created from BudUseCases template
    parameters: dict = {}                  # User-provided parameters


class PipelineStep(SQLModel):
    """
    Step within a Pipeline. Only JOB-type steps create actual Jobs.
    """
    id: UUID
    pipeline_id: UUID
    name: str
    order: int                             # Execution order (for UI display)

    # Step type determines execution behavior
    step_type: StepType

    # Dependencies (step IDs that must complete first)
    depends_on: list[UUID] = []

    # Condition (optional Jinja2 expression)
    condition: Optional[str]               # "{{ params.enable_reranker }}"

    # Type-specific configuration
    config: dict                           # Varies by step_type (see below)

    # For JOB steps: link to created Job
    job_id: Optional[UUID]                 # Set when Job is created

    # Outputs (available to dependent steps)
    outputs: dict = {}

    # Status
    status: StepStatus = StepStatus.PENDING
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]


# Step config schemas by type

class JobStepConfig(BaseModel):
    """Config for step_type=JOB"""
    job_type: JobType                      # SERVICE, BATCH, TRAINING
    deployment_type: DeploymentType        # HELM, DOCKER, MODEL
    component_ref: Optional[str]           # Reference to component registry
    spec: Optional[dict]                   # Direct specification (if no component_ref)

    # Resource requirements
    cluster_id: Optional[UUID]             # Specific cluster or auto-select
    gpu_type: Optional[str]
    gpu_count: int = 0
    cpu_cores: float = 1.0
    memory_gb: float = 4.0

    # Time constraints (job level)
    estimated_duration_seconds: Optional[int]
    max_duration_seconds: Optional[int]
    time_window_start: Optional[str]       # "22:00" (only run during off-peak)
    time_window_end: Optional[str]         # "06:00"

    # Priority
    priority: JobPriority = JobPriority.NORMAL
    preemptible: bool = False

    # BudSim optimization
    optimize_with_budsim: bool = False


class ApiCallStepConfig(BaseModel):
    """Config for step_type=API_CALL"""
    url: str                               # Supports Jinja2: "{{ services.budsim }}/optimize"
    method: str = "POST"
    headers: dict = {}
    body: Optional[dict]                   # Supports Jinja2 templating
    timeout_seconds: int = 30
    retry_count: int = 3


class ConditionStepConfig(BaseModel):
    """Config for step_type=CONDITION"""
    expression: str                        # Jinja2: "{{ params.enable_reranker }}"
    then_steps: list[UUID]                 # Step IDs to run if true
    else_steps: list[UUID] = []            # Step IDs to run if false


class WaitStepConfig(BaseModel):
    """Config for step_type=WAIT"""
    duration_seconds: Optional[int]        # Wait fixed time
    wait_for_event: Optional[str]          # Wait for webhook/event
    timeout_seconds: int = 3600            # Max wait time


class NotificationStepConfig(BaseModel):
    """Config for step_type=NOTIFICATION"""
    channel: str                           # "slack", "email", "webhook", "pagerduty"
    recipients: list[str]
    message: str                           # Supports Jinja2
    severity: str = "info"                 # "info", "warning", "error"
```

#### 5.2.2 Example: RAG Deployment Pipeline

```json
{
  "pipeline": {
    "id": "pipeline-123",
    "name": "deploy-enterprise-rag",
    "trigger_type": "manual",
    "parameters": {
      "llm_model": "meta-llama/Llama-3.3-70B-Instruct",
      "embedding_model": "BAAI/bge-large-en-v1.5",
      "enable_reranker": true
    }
  },
  "steps": [
    {
      "id": "step-1",
      "name": "optimize-llm-config",
      "order": 1,
      "step_type": "API_CALL",
      "depends_on": [],
      "config": {
        "url": "http://budsim/api/v1/optimize",
        "method": "POST",
        "body": {
          "model_id": "{{ params.llm_model }}",
          "target_throughput": 100
        }
      }
    },
    {
      "id": "step-2",
      "name": "deploy-qdrant",
      "order": 2,
      "step_type": "JOB",
      "depends_on": [],
      "config": {
        "job_type": "SERVICE",
        "deployment_type": "HELM",
        "component_ref": "qdrant",
        "cpu_cores": 2,
        "memory_gb": 8
      }
    },
    {
      "id": "step-3",
      "name": "deploy-embedding",
      "order": 3,
      "step_type": "JOB",
      "depends_on": ["step-1"],
      "config": {
        "job_type": "SERVICE",
        "deployment_type": "MODEL",
        "spec": {
          "model_id": "{{ params.embedding_model }}",
          "engine": "latentbud"
        },
        "gpu_type": "nvidia-t4",
        "gpu_count": 1
      }
    },
    {
      "id": "step-4",
      "name": "deploy-llm",
      "order": 4,
      "step_type": "JOB",
      "depends_on": ["step-1"],
      "config": {
        "job_type": "SERVICE",
        "deployment_type": "MODEL",
        "spec": {
          "model_id": "{{ params.llm_model }}",
          "engine": "vllm",
          "budsim_config": "{{ steps.step-1.outputs.config }}"
        },
        "gpu_type": "nvidia-a100-80gb",
        "gpu_count": 2,
        "priority": "HIGH"
      }
    },
    {
      "id": "step-5",
      "name": "check-reranker",
      "order": 5,
      "step_type": "CONDITION",
      "depends_on": [],
      "config": {
        "expression": "{{ params.enable_reranker }}",
        "then_steps": ["step-6"],
        "else_steps": []
      }
    },
    {
      "id": "step-6",
      "name": "deploy-reranker",
      "order": 6,
      "step_type": "JOB",
      "depends_on": ["step-5"],
      "condition": "{{ params.enable_reranker }}",
      "config": {
        "job_type": "SERVICE",
        "deployment_type": "MODEL",
        "spec": {
          "model_id": "BAAI/bge-reranker-v2-m3",
          "engine": "latentbud"
        },
        "gpu_type": "nvidia-t4",
        "gpu_count": 1
      }
    },
    {
      "id": "step-7",
      "name": "deploy-orchestrator",
      "order": 7,
      "step_type": "JOB",
      "depends_on": ["step-2", "step-3", "step-4", "step-5"],
      "config": {
        "job_type": "SERVICE",
        "deployment_type": "DOCKER",
        "component_ref": "rag-orchestrator",
        "spec": {
          "env": {
            "VECTOR_DB_URL": "{{ steps.step-2.outputs.url }}",
            "EMBEDDING_URL": "{{ steps.step-3.outputs.url }}",
            "LLM_URL": "{{ steps.step-4.outputs.url }}",
            "RERANKER_URL": "{{ steps.step-6.outputs.url | default('') }}"
          }
        },
        "cpu_cores": 2,
        "memory_gb": 4
      }
    },
    {
      "id": "step-8",
      "name": "notify-complete",
      "order": 8,
      "step_type": "NOTIFICATION",
      "depends_on": ["step-7"],
      "config": {
        "channel": "slack",
        "recipients": ["#deployments"],
        "message": "RAG system deployed! URL: {{ steps.step-7.outputs.url }}"
      }
    }
  ]
}
```

### 5.3 Scheduling Dimensions

Jobs can be scheduled based on multiple dimensions:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         SCHEDULING DIMENSIONS                                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   1. RESOURCE-BASED (Kueue)                                                    │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │ • "Run when 4x A100 available"                                          │   │
│   │ • "Run when tenant quota allows"                                        │   │
│   │ • "Run with fair-share across tenants"                                  │   │
│   │ • Handled by: Kueue ClusterQueues, LocalQueues, ResourceFlavors         │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│   2. TIME-BASED (Pipeline trigger + Job constraints)                           │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │ • Pipeline cron: "0 2 * * *" (start pipeline at 2 AM)                   │   │
│   │ • Job time window: "Only run 10 PM - 6 AM" (off-peak)                   │   │
│   │ • Job deadline: "Must complete by 6 AM"                                 │   │
│   │ • Job timeout: "Kill if running > 4 hours"                              │   │
│   │ • Handled by: BudPipeline (triggers), BudCluster (job constraints)      │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│   3. EVENT-BASED (Pipeline trigger)                                            │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │ • Webhook: "Run when external system calls endpoint"                    │   │
│   │ • Data arrival: "Run when new files in S3 bucket"                       │   │
│   │ • Pipeline completion: "Run after pipeline X completes"                 │   │
│   │ • Handled by: BudPipeline event listeners                               │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│   4. PRIORITY-BASED (Kueue + BudCluster)                                       │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │ • Priority classes: CRITICAL > HIGH > NORMAL > LOW > SPOT               │   │
│   │ • Preemption: Higher priority can stop lower priority jobs              │   │
│   │ • Starvation prevention: Boost priority after waiting too long          │   │
│   │ • Handled by: Kueue PriorityClasses, BudCluster preemption logic        │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│   5. DEPENDENCY-BASED (Pipeline DAG)                                           │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │ • "Run after step X completes"                                          │   │
│   │ • "Run after jobs A, B, C all complete"                                 │   │
│   │ • Handled by: BudPipeline DAG executor                                  │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│   6. COST-BASED (BudCluster + BudMetrics)                                      │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │ • Budget limit: "Fail if cost exceeds $100"                             │   │
│   │ • Spot instances: "Use preemptible GPUs for lower cost"                 │   │
│   │ • Cost optimization: "Choose cheapest GPU that meets requirements"      │   │
│   │ • Handled by: BudCluster (limits), BudMetrics (tracking)                │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 5.4 UI Schedule Visualization

The cluster schedule view shows **only Jobs** (from JOB-type steps), not functional or control steps.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    CLUSTER SCHEDULE VIEW - UI DESIGN                            │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │  CLUSTER: prod-us-east-1            [All Pipelines ▼] [All GPUs ▼]      │   │
│   ├─────────────────────────────────────────────────────────────────────────┤   │
│   │                                                                          │   │
│   │  RESOURCE TIMELINE                  ◀ Jan 30  ●  Jan 31 ▶               │   │
│   │  ─────────────────────────────────────────────────────────────────────  │   │
│   │                                                                          │   │
│   │  GPU        10PM   11PM   12AM   1AM    2AM    3AM    4AM    5AM        │   │
│   │  ────────── ────── ────── ────── ────── ────── ────── ────── ──────    │   │
│   │                                                                          │   │
│   │  A100-1     │▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓│░░░░░│               │   │
│   │  A100-2     │▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓│     │               │   │
│   │             │        deploy-llm (step-4)         │     │               │   │
│   │                                                                          │   │
│   │  T4-1       │    │▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓│                    │               │   │
│   │             │    │ deploy-embed  │                    │               │   │
│   │             │    │   (step-3)    │                    │               │   │
│   │                                                                          │   │
│   │  T4-2       │    │▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓│               │               │   │
│   │             │    │ deploy-reranker     │               │               │   │
│   │             │    │    (step-6)         │               │               │   │
│   │                                                                          │   │
│   │  CPU Pool   │████████████████████████████████████████████████│          │   │
│   │             │qdrant│              │   rag-orchestrator   │               │   │
│   │             │(st-2)│              │      (step-7)        │               │   │
│   │                                                                          │   │
│   │  ─────────────────────────────────────────────────────────────────────  │   │
│   │  Legend:                                                                 │   │
│   │  ▓▓▓ Pipeline: deploy-enterprise-rag                                    │   │
│   │  ███ Standalone job                                                      │   │
│   │  ░░░ Estimated (not yet started)                                         │   │
│   │      Available                                                           │   │
│   │                                                                          │   │
│   │  Note: Steps 1 (API_CALL), 5 (CONDITION), 8 (NOTIFICATION) are NOT     │   │
│   │        shown - they don't consume cluster resources.                    │   │
│   │                                                                          │   │
│   ├─────────────────────────────────────────────────────────────────────────┤   │
│   │                                                                          │   │
│   │  QUEUED JOBS                                            [+ Submit Job]  │   │
│   │  ─────────────────────────────────────────────────────────────────────  │   │
│   │                                                                          │   │
│   │  Priority │ Job Name          │ Pipeline          │ GPUs    │ Est.Start │   │
│   │  ──────── │ ───────────────── │ ───────────────── │ ─────── │ ───────── │   │
│   │  HIGH     │ deploy-llm        │ deploy-rag        │ 2xA100  │ 10:05 PM  │   │
│   │  NORMAL   │ deploy-embedding  │ deploy-rag        │ 1xT4    │ 10:05 PM  │   │
│   │  NORMAL   │ deploy-reranker   │ deploy-rag        │ 1xT4    │ 10:05 PM  │   │
│   │  NORMAL   │ batch-inference   │ (standalone)      │ 2xA100  │ ~2:30 AM  │   │
│   │                                                                          │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│   Interaction:                                                                  │
│   • Click job block → View details, change priority, cancel                    │
│   • Click empty slot → "Schedule job here" (if time-flexible)                  │
│   • Hover → Show estimated vs actual timing                                    │
│   • Filter by pipeline, job type, priority                                     │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

#### 5.4.1 Estimated vs Actual Scheduling

Jobs from pipelines have **estimated** start/end times that update as dependencies complete:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    ESTIMATED vs ACTUAL SCHEDULE                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   When pipeline starts, estimates are calculated:                               │
│                                                                                 │
│   Job 1 (qdrant):     estimated_start = now,        estimated_duration = 2 min │
│   Job 2 (embedding):  estimated_start = now + 30s,  estimated_duration = 3 min │
│   Job 3 (llm):        estimated_start = now + 30s,  estimated_duration = 5 min │
│   Job 4 (orchestrator): estimated_start = max(job1,2,3) + buffer = ~6 min      │
│                                                                                 │
│   As jobs complete, estimates UPDATE:                                           │
│                                                                                 │
│   Job 1: COMPLETED at T+1:45 (15s early)                                       │
│   Job 2: RUNNING, estimated_end = T+4:30                                       │
│   Job 3: RUNNING, estimated_end = T+5:30                                       │
│   Job 4: estimated_start = T+5:30 (updated based on Job 3)                     │
│                                                                                 │
│   Timeline display:                                                             │
│                                                                                 │
│   T=0      T=2min   T=4min   T=6min   T=8min                                   │
│   │─────────│─────────│─────────│─────────│                                    │
│   │██qdrant█│         │         │         │  ██ = Completed                    │
│   │   │░░░░░░░░░░░│   │         │         │  ░░ = Running                      │
│   │   │  embedding │   │         │         │  ┄┄ = Estimated                    │
│   │   │░░░░░░░░░░░░░░░░│        │         │                                    │
│   │   │      llm       │        │         │                                    │
│   │   │                │┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄│ │                                    │
│   │   │                │  orchestrator   │ │                                    │
│   │                                                                             │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 5.5 Service Responsibilities

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    SERVICE RESPONSIBILITIES                                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   BudPipeline                                                                   │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │ • Pipeline CRUD and lifecycle                                           │   │
│   │ • Trigger management (cron, events, webhooks)                           │   │
│   │ • Step execution in DAG order                                           │   │
│   │ • Execute non-JOB steps (API_CALL, FUNCTION, CONDITION, etc.)          │   │
│   │ • Create Jobs for JOB-type steps → call BudCluster                     │   │
│   │ • Pass outputs between steps (Jinja2 templating)                        │   │
│   │ • Handle pipeline-level retry, timeout, failure                         │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│   BudCluster                                                                    │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │ • Job CRUD and lifecycle                                                │   │
│   │ • Submit to Kueue for resource scheduling                               │   │
│   │ • Execute deployments (Helm, Docker, Model)                             │   │
│   │ • Job-level retry, timeout, preemption                                  │   │
│   │ • Track job schedule (estimated/actual start/end)                       │   │
│   │ • Provide cluster schedule API for UI                                   │   │
│   │ • Cost tracking per job                                                 │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│   BudUseCases                                                                   │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │ • Template and component registry                                       │   │
│   │ • Convert template → Pipeline definition                                │   │
│   │ • Call BudPipeline to create and start pipeline                         │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│   Flow:                                                                         │
│   ──────                                                                        │
│   User → BudUseCases.deploy(template, params)                                  │
│            │                                                                    │
│            ▼                                                                    │
│          BudUseCases: Resolve template → Pipeline spec                         │
│            │                                                                    │
│            ▼                                                                    │
│          BudPipeline.create(pipeline_spec)                                     │
│            │                                                                    │
│            │  For each step in DAG order:                                      │
│            │                                                                    │
│            ├─► If step.type == JOB:                                            │
│            │     BudCluster.create_job(job_spec)                               │
│            │       → Kueue admission → Helm/Docker deploy → Running            │
│            │       → Wait for completion → Store outputs                       │
│            │                                                                    │
│            ├─► If step.type == API_CALL:                                       │
│            │     BudPipeline executes HTTP request → Store outputs             │
│            │                                                                    │
│            ├─► If step.type == CONDITION:                                      │
│            │     BudPipeline evaluates → Route to then/else steps             │
│            │                                                                    │
│            └─► etc.                                                            │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 5.6 Data Ownership

Jobs, Pipelines, and Steps are stored in different service databases. This section clarifies ownership.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         DATA OWNERSHIP                                           │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   BudCluster (PostgreSQL)          ← OWNS JOBS                                 │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │                                                                          │   │
│   │   jobs (NEW TABLE)                                                      │   │
│   │   ┌──────────────────────────────────────────────────────────────────┐  │   │
│   │   │ id, name, tenant_id, project_id, cluster_id                      │  │   │
│   │   │ job_type (SERVICE, BATCH, TRAINING)                              │  │   │
│   │   │ deployment_type (HELM, DOCKER, MODEL)                            │  │   │
│   │   │ spec (JSONB)                                                      │  │   │
│   │   │ resources (gpu_type, gpu_count, cpu_cores, memory_gb)            │  │   │
│   │   │ priority, preemptible                                            │  │   │
│   │   │ status (PENDING, QUEUED, RUNNING, COMPLETED, FAILED)             │  │   │
│   │   │ estimated_start, estimated_end, actual_start, actual_end         │  │   │
│   │   │ estimated_cost, actual_cost                                      │  │   │
│   │   │                                                                   │  │   │
│   │   │ # Source tracking                                                │  │   │
│   │   │ source_type (DIRECT, PIPELINE, USECASE)                          │  │   │
│   │   │ source_id (endpoint_id, pipeline_step_id, usecase_id)           │  │   │
│   │   └──────────────────────────────────────────────────────────────────┘  │   │
│   │                                                                          │   │
│   │   Existing: clusters, deployments, kueue_quotas, etc.                   │   │
│   │                                                                          │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│   BudPipeline (PostgreSQL)         ← OWNS PIPELINES & STEPS                    │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │                                                                          │   │
│   │   pipelines                                                             │   │
│   │   ┌──────────────────────────────────────────────────────────────────┐  │   │
│   │   │ id, name, tenant_id, project_id                                  │  │   │
│   │   │ trigger_type, cron_expression, event_config                      │  │   │
│   │   │ status, parameters (JSONB)                                       │  │   │
│   │   │ template_id (if from BudUseCases)                                │  │   │
│   │   └──────────────────────────────────────────────────────────────────┘  │   │
│   │                                                                          │   │
│   │   pipeline_steps                                                        │   │
│   │   ┌──────────────────────────────────────────────────────────────────┐  │   │
│   │   │ id, pipeline_id, name, order                                     │  │   │
│   │   │ step_type (JOB, API_CALL, FUNCTION, CONDITION, etc.)            │  │   │
│   │   │ depends_on, config, status, outputs (JSONB)                     │  │   │
│   │   │                                                                   │  │   │
│   │   │ job_id (reference to BudCluster.jobs - for JOB steps only)      │  │   │
│   │   └──────────────────────────────────────────────────────────────────┘  │   │
│   │                                                                          │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│   BudApp (PostgreSQL)              ← OWNS ENDPOINTS (stores job_id ref)        │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │   endpoints: id, name, project_id, model_id, ..., job_id (NEW)         │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│   BudUseCases (PostgreSQL)         ← OWNS TEMPLATES & COMPONENTS               │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │   use_case_templates, component_definitions                             │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

#### 5.6.1 Why BudCluster Owns Jobs

| Reason | Explanation |
|--------|-------------|
| **Cluster proximity** | Jobs run on clusters; BudCluster already manages cluster lifecycle |
| **Kueue integration** | BudCluster submits Jobs to Kueue, tracks admission and quota status |
| **Resource scheduling** | BudCluster knows cluster capacity and GPU availability |
| **Timeline API** | Cluster schedule view needs Job data locally for efficient queries |
| **Single source of truth** | All Jobs in one place regardless of source (direct, pipeline, usecase) |

#### 5.6.2 Cross-Service Job Creation Flows

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    JOB CREATION FLOWS                                            │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   FLOW 1: Direct Deployment (BudApp → BudCluster)                              │
│   ─────────────────────────────────────────────────────────────────────────────│
│                                                                                 │
│   BudApp                              BudCluster                                │
│   ┌───────────────┐                   ┌─────────────────────────────────────┐   │
│   │ POST          │    Dapr/HTTP      │                                     │   │
│   │ /endpoints    │ ────────────────► │ 1. Create Job record in jobs table  │   │
│   │               │ deploy_model()    │ 2. source_type = DIRECT             │   │
│   │               │                   │ 3. source_id = endpoint_id          │   │
│   │               │                   │ 4. Submit to Kueue                  │   │
│   │               │ ◄──────────────── │ 5. Deploy Helm                      │   │
│   │               │ { job_id }        │ 6. Return job_id                    │   │
│   │               │                   │                                     │   │
│   │ Store job_id  │                   └─────────────────────────────────────┘   │
│   │ in endpoints  │                                                             │
│   │ table         │                                                             │
│   └───────────────┘                                                             │
│                                                                                 │
│   Existing BudApp API unchanged - BudCluster internally creates Job            │
│                                                                                 │
│   ─────────────────────────────────────────────────────────────────────────────│
│                                                                                 │
│   FLOW 2: Pipeline Deployment (BudPipeline → BudCluster)                       │
│   ─────────────────────────────────────────────────────────────────────────────│
│                                                                                 │
│   BudPipeline                         BudCluster                                │
│   ┌───────────────┐                   ┌─────────────────────────────────────┐   │
│   │ Execute       │    Dapr/HTTP      │                                     │   │
│   │ JOB-type step │ ────────────────► │ 1. Create Job record                │   │
│   │               │ POST /jobs        │ 2. source_type = PIPELINE           │   │
│   │               │                   │ 3. source_id = pipeline_step_id     │   │
│   │               │                   │ 4. Submit to Kueue                  │   │
│   │               │ ◄──────────────── │ 5. Return job_id                    │   │
│   │               │ { job_id }        │                                     │   │
│   │               │                   └─────────────────────────────────────┘   │
│   │ Store job_id  │                                                             │
│   │ in step.job_id│                                                             │
│   │               │                   BudCluster                                │
│   │ Poll status   │ ────────────────► GET /jobs/{id}                           │
│   │               │ ◄──────────────── { status: COMPLETED, outputs: {...} }    │
│   │               │                                                             │
│   │ Continue to   │                                                             │
│   │ next step     │                                                             │
│   └───────────────┘                                                             │
│                                                                                 │
│   ─────────────────────────────────────────────────────────────────────────────│
│                                                                                 │
│   FLOW 3: UseCase Deployment (BudUseCases → BudPipeline → BudCluster)          │
│   ─────────────────────────────────────────────────────────────────────────────│
│                                                                                 │
│   BudUseCases            BudPipeline               BudCluster                   │
│   ┌──────────────┐       ┌──────────────┐          ┌──────────────┐            │
│   │ Deploy       │       │              │          │              │            │
│   │ template     │──────►│ Create       │          │              │            │
│   │              │create │ Pipeline +   │          │              │            │
│   │              │pipeline│ Steps       │          │              │            │
│   │              │       │              │          │              │            │
│   │              │       │ For each     │          │              │            │
│   │              │       │ JOB step:    │─────────►│ Create Job   │            │
│   │              │       │              │POST /jobs│ Track in DB  │            │
│   │              │       │              │◄─────────│              │            │
│   │              │       │              │ job_id   │              │            │
│   └──────────────┘       └──────────────┘          └──────────────┘            │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

#### 5.6.3 Data Ownership Summary

| Data | Owner Service | Database | Other Services Access Via |
|------|---------------|----------|--------------------------|
| **Jobs** | BudCluster | BudCluster PostgreSQL | API: `GET/POST /jobs` |
| **Pipelines** | BudPipeline | BudPipeline PostgreSQL | API: `GET/POST /pipelines` |
| **Steps** | BudPipeline | BudPipeline PostgreSQL | Internal (via Pipeline API) |
| **Endpoints** | BudApp | BudApp PostgreSQL | Stores `job_id` reference |
| **Templates** | BudUseCases | BudUseCases PostgreSQL | Creates Pipelines via API |
| **Components** | BudUseCases | BudUseCases PostgreSQL | Referenced by Templates |

---

## Part 6: BudQueue - Request Queue Management (Serverless Only)

### 6.1 Queue Schema

```python
# Proposed BudQueue Schema
class QueuedRequest(SQLModel):
    """Request waiting for GPU resources"""
    id: UUID
    endpoint_id: UUID
    tenant_id: UUID

    # Request details
    payload_hash: str  # For deduplication
    payload_size_bytes: int
    estimated_compute_seconds: float

    # Priority
    priority: RequestPriority  # PREMIUM, STANDARD, SPOT, BATCH
    priority_score: float  # Computed score for ordering

    # Timing
    enqueued_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    timeout_at: datetime

    # Status
    status: QueueStatus  # PENDING, ASSIGNED, PROCESSING, COMPLETED, FAILED, TIMEOUT
    assigned_worker_id: Optional[UUID]

    # SLA
    max_wait_seconds: int
    max_process_seconds: int

class WarmPoolConfig(SQLModel):
    """Warm pool configuration for an endpoint"""
    endpoint_id: UUID

    # Pool sizing
    min_warm_workers: int = 0
    max_warm_workers: int = 5
    target_warm_workers: int = 1

    # Timing
    idle_timeout_seconds: int = 300  # 5 minutes
    warmup_timeout_seconds: int = 120  # 2 minutes to warm

    # Cost controls
    max_idle_cost_per_hour: Decimal

    # Predictive scaling
    enable_predictive_scaling: bool = False
    traffic_history_hours: int = 24
```

### 6.2 Queue Processing Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         REQUEST QUEUE PROCESSING FLOW                            │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   ┌───────────────────────────────────────────────────────────────────────┐     │
│   │ STEP 1: REQUEST INGRESS                                               │     │
│   │                                                                       │     │
│   │ Client → BudGateway → Auth → Rate Limit → BudQueue                   │     │
│   │                                                                       │     │
│   │ Validations:                                                          │     │
│   │ • API key valid                                                       │     │
│   │ • Tenant quota not exceeded                                           │     │
│   │ • Request size within limits                                          │     │
│   │ • Budget available (if billing enabled)                               │     │
│   └───────────────────────────────────────────────────────────────────────┘     │
│                                          │                                      │
│   ┌──────────────────────────────────────▼────────────────────────────────┐     │
│   │ STEP 2: QUEUE ADMISSION                                               │     │
│   │                                                                       │     │
│   │ Priority scoring:                                                     │     │
│   │   score = (priority_weight * 1000) +                                  │     │
│   │           (tenant_fairness_score * 100) +                             │     │
│   │           (wait_time_bonus * 10)                                      │     │
│   │                                                                       │     │
│   │ Admission checks:                                                     │     │
│   │ • Queue depth < max_queue_size                                        │     │
│   │ • Estimated wait < SLA timeout                                        │     │
│   │ • Tenant concurrent requests < limit                                  │     │
│   └───────────────────────────────────────────────────────────────────────┘     │
│                                          │                                      │
│   ┌──────────────────────────────────────▼────────────────────────────────┐     │
│   │ STEP 3: WORKER ASSIGNMENT                                             │     │
│   │                                                                       │     │
│   │ ┌─────────────────┐                                                   │     │
│   │ │ Check Warm Pool │──Yes──► Assign immediately (< 100ms)              │     │
│   │ └────────┬────────┘                                                   │     │
│   │          │ No                                                          │     │
│   │ ┌────────▼────────┐                                                   │     │
│   │ │ Check Cold Pool │──Yes──► Start cold worker, wait (10-60s)          │     │
│   │ └────────┬────────┘                                                   │     │
│   │          │ No capacity                                                 │     │
│   │ ┌────────▼────────┐                                                   │     │
│   │ │ Check Preemption│──Yes──► Preempt lower-pri, reassign               │     │
│   │ └────────┬────────┘                                                   │     │
│   │          │ No                                                          │     │
│   │          └──────────────► Wait in queue (with timeout)                │     │
│   └───────────────────────────────────────────────────────────────────────┘     │
│                                          │                                      │
│   ┌──────────────────────────────────────▼────────────────────────────────┐     │
│   │ STEP 4: PROCESSING & METERING                                         │     │
│   │                                                                       │     │
│   │ Worker receives request:                                              │     │
│   │ • Start metering timer                                                │     │
│   │ • Process inference                                                   │     │
│   │ • Stream response (if applicable)                                     │     │
│   │ • Stop metering timer                                                 │     │
│   │ • Report usage to BudMetering                                         │     │
│   │                                                                       │     │
│   │ Metering granularity: per-second GPU compute time                     │     │
│   └───────────────────────────────────────────────────────────────────────┘     │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Part 7: BudMetrics (Extended) - Observability + Metering

> **Architecture Decision:** Metering capabilities are consolidated into the existing BudMetrics service
> rather than creating a separate BudMetering service. This avoids service overlap and credential
> management complexity. See [Appendix B: Decision Log](#appendix-b-decision-log) for rationale.

### 7.1 Push-Based Metrics Architecture

BudMetrics uses a **push-based pattern** (similar to Thanos, Cortex, Grafana Cloud) where clusters push
metrics to a central endpoint, avoiding the need for BudMetrics to hold cluster credentials.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    PUSH-BASED METRICS ARCHITECTURE                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │  BUDCLUSTER: Deploys monitoring stack during cluster registration       │   │
│   │                                                                          │   │
│   │  1. Register Cluster → 2. Deploy Helm Chart → 3. Start pushing metrics  │   │
│   │                                                                          │   │
│   │  Deployed Components:                                                    │   │
│   │  • Prometheus (with remote-write configured)                            │   │
│   │  • DCGM Exporter (GPU utilization, memory, power)                       │   │
│   │  • HAMI Exporter (time-slice allocation, vGPU metrics)                  │   │
│   │  • Node Exporter (CPU, memory, disk, network)                           │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                         │                                       │
│                                         │ Prometheus remote-write               │
│                                         │ (cluster_id, api_key in headers)     │
│                                         ▼                                       │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │  BUDMETRICS: Central metrics receiver and processor                     │   │
│   │                                                                          │   │
│   │  ┌─────────────────────────────────────────────────────────────────┐    │   │
│   │  │ Remote Write Endpoint (/api/v1/push)                            │    │   │
│   │  │                                                                  │    │   │
│   │  │ • Auth via cluster API key (issued during registration)         │    │   │
│   │  │ • Validates cluster_id matches token                            │    │   │
│   │  │ • Enriches with tenant metadata                                 │    │   │
│   │  │ • Writes to ClickHouse                                          │    │   │
│   │  └─────────────────────────────────────────────────────────────────┘    │   │
│   │                                                                          │   │
│   │  ┌─────────────────────────────────────────────────────────────────┐    │   │
│   │  │ Fallback: Dapr Service Invocation (when push fails)             │    │   │
│   │  │                                                                  │    │   │
│   │  │ BudMetrics → Dapr → BudCluster → kubectl/API → Cluster metrics  │    │   │
│   │  │                                                                  │    │   │
│   │  │ Used for: historical backfill, push gap recovery, on-demand     │    │   │
│   │  └─────────────────────────────────────────────────────────────────┘    │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 Service Boundary Clarification

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    SERVICE RESPONSIBILITIES (Clear Boundaries)                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   BUDCLUSTER (Infrastructure)           BUDMETRICS (Observability + Metering)  │
│   ─────────────────────────────         ────────────────────────────────────   │
│                                                                                 │
│   ✓ Holds cluster credentials           ✓ Receives pushed metrics              │
│   ✓ Deploys monitoring stack            ✓ Stores in ClickHouse                 │
│   ✓ Provisions GPU nodes                ✓ Aggregates usage data                │
│   ✓ Installs HAMI/DCGM exporters        ✓ Calculates costs                     │
│   ✓ Manages cluster lifecycle           ✓ Exposes usage/billing APIs           │
│   ✓ Provides fallback metrics API       ✓ Generates invoices                   │
│                                         ✓ Sends budget alerts                  │
│                                                                                 │
│   Does NOT:                             Does NOT:                              │
│   ✗ Process or store metrics            ✗ Hold cluster credentials             │
│   ✗ Calculate billing                   ✗ Directly query clusters              │
│   ✗ Generate usage reports              ✗ Deploy infrastructure                │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 7.3 Extended BudMetrics Architecture

Based on [OpenCost](https://opencost.io/) and [Flexprice](https://flexprice.io/blog/best-solutions-for-tracking-gpu-costs-in-machine-learning) patterns:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    BUDMETRICS (EXTENDED) ARCHITECTURE                            │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │                      DATA INGESTION LAYER                               │   │
│   │                                                                          │   │
│   │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐          │   │
│   │  │ Remote Write    │  │ Request Events  │  │ Dapr Fallback   │          │   │
│   │  │ (Primary)       │  │                 │  │ (Secondary)     │          │   │
│   │  │                 │  │                 │  │                 │          │   │
│   │  │ • GPU metrics   │  │ • Request count │  │ • On-demand pull│          │   │
│   │  │ • Node metrics  │  │ • Tokens I/O    │  │ • Backfill      │          │   │
│   │  │ • HAMI vGPU     │  │ • Latency       │  │ • Gap recovery  │          │   │
│   │  │ • Power draw    │  │ • Error rate    │  │                 │          │   │
│   │  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘          │   │
│   │           │                    │                    │                   │   │
│   └───────────┼────────────────────┼────────────────────┼───────────────────┘   │
│               │                    │                    │                       │
│   ┌───────────▼────────────────────▼────────────────────▼───────────────────┐   │
│   │                      AGGREGATION LAYER                                   │   │
│   │                                                                          │   │
│   │  ┌─────────────────────────────────────────────────────────────────┐    │   │
│   │  │ Usage Aggregator (per-second → per-minute → per-hour)           │    │   │
│   │  │                                                                  │    │   │
│   │  │ Dimensions:                                                      │    │   │
│   │  │ • tenant_id    • cluster_id    • gpu_type    • sharing_mode    │    │   │
│   │  │ • workload_id  • endpoint_id   • priority    • region          │    │   │
│   │  └─────────────────────────────────────────────────────────────────┘    │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                         │                                       │
│   ┌─────────────────────────────────────▼───────────────────────────────────┐   │
│   │                      PRICING LAYER                                       │   │
│   │                                                                          │   │
│   │  ┌─────────────────────────────────────────────────────────────────┐    │   │
│   │  │ Price Book                                                       │    │   │
│   │  │                                                                  │    │   │
│   │  │ GPU Type        | Mode        | Tier     | $/hour  | $/second  │    │   │
│   │  │ ─────────────────────────────────────────────────────────────── │    │   │
│   │  │ A100-80GB       | Full        | Secure   | $3.50   | $0.00097  │    │   │
│   │  │ A100-80GB       | Full        | OnPrem   | $1.50   | $0.00042  │    │   │
│   │  │ A100-80GB       | MIG-3g.40gb | Secure   | $1.75   | $0.00049  │    │   │
│   │  │ A100-80GB       | TimeSlice   | Secure   | $1.20   | $0.00033  │    │   │
│   │  │ H100-SXM        | Full        | Secure   | $5.00   | $0.00139  │    │   │
│   │  │ RTX-4090        | Full        | Community| $0.50   | $0.00014  │    │   │
│   │  └─────────────────────────────────────────────────────────────────┘    │   │
│   │                                                                          │   │
│   │  ┌─────────────────────────────────────────────────────────────────┐    │   │
│   │  │ Cost Calculator                                                  │    │   │
│   │  │                                                                  │    │   │
│   │  │ cost = gpu_seconds * price_per_second * sharing_multiplier      │    │   │
│   │  │      + storage_gb * storage_price_per_gb_month                  │    │   │
│   │  │      + egress_gb * egress_price_per_gb (if applicable)          │    │   │
│   │  └─────────────────────────────────────────────────────────────────┘    │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                         │                                       │
│   ┌─────────────────────────────────────▼───────────────────────────────────┐   │
│   │                      BILLING LAYER                                       │   │
│   │                                                                          │   │
│   │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐      │   │
│   │  │ Invoice Generator│  │ Usage API        │  │ Budget Alerts    │      │   │
│   │  │                  │  │                  │  │                  │      │   │
│   │  │ • Monthly invoice│  │ • Real-time usage│  │ • Threshold alert│      │   │
│   │  │ • Line items     │  │ • Cost breakdown │  │ • Forecast alert │      │   │
│   │  │ • Payment link   │  │ • Export CSV     │  │ • Stop on budget │      │   │
│   │  └──────────────────┘  └──────────────────┘  └──────────────────┘      │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 7.4 Database Schema for Metering

```python
# Extended BudMetrics Schema (ClickHouse tables)
class UsageRecord(SQLModel):
    """Per-second GPU usage record (stored in ClickHouse)"""
    id: UUID

    # Dimensions
    tenant_id: UUID
    workload_id: UUID
    workload_type: WorkloadType  # POD, SERVERLESS, USECASE
    endpoint_id: Optional[UUID]
    cluster_id: UUID
    node_name: str

    # GPU details
    gpu_type: str  # "A100-80GB", "H100-SXM"
    gpu_index: int
    sharing_mode: GPUSharingMode
    mig_profile: Optional[str]

    # Usage metrics
    timestamp: datetime
    gpu_seconds: float  # Actual GPU compute time
    gpu_memory_gb_seconds: float  # Memory × time
    tokens_in: int = 0
    tokens_out: int = 0

    # Cost
    computed_cost: Decimal  # Pre-calculated for fast queries

class BillingPeriod(SQLModel):
    """Monthly billing period for a tenant"""
    id: UUID
    tenant_id: UUID

    # Period
    period_start: datetime
    period_end: datetime

    # Aggregated usage
    total_gpu_seconds: float
    total_cost: Decimal
    total_requests: int

    # Breakdown by GPU type
    usage_by_gpu_type: dict  # {"A100-80GB": {"seconds": 1000, "cost": 100.00}}

    # Status
    status: BillingStatus  # OPEN, CLOSED, INVOICED, PAID
    invoice_id: Optional[str]
```

---

## Part 8: BudUseCases - Template-Based Deployment

### 8.1 Use Case Template Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      BUDUSECASES TEMPLATE ARCHITECTURE                           │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │                         TEMPLATE CATALOG                                │   │
│   │                                                                          │   │
│   │  ┌─────────────────────────────────────────────────────────────────┐    │   │
│   │  │ RAG Templates                                                    │    │   │
│   │  │  • Simple RAG (LLM + Vector DB)                                 │    │   │
│   │  │  • Enterprise RAG (Embedding + Reranker + LLM + Vector DB)      │    │   │
│   │  │  • Multimodal RAG (Vision + Text + Vector DB)                   │    │   │
│   │  │  • Conversational RAG (Memory + Context Management)             │    │   │
│   │  └─────────────────────────────────────────────────────────────────┘    │   │
│   │                                                                          │   │
│   │  ┌─────────────────────────────────────────────────────────────────┐    │   │
│   │  │ Chatbot Templates                                                │    │   │
│   │  │  • Simple Chatbot (Single LLM)                                  │    │   │
│   │  │  • Multi-turn Chatbot (Memory + Session Management)             │    │   │
│   │  │  • Customer Support Bot (RAG + Routing + Escalation)            │    │   │
│   │  │  • Voice Bot (STT + LLM + TTS)                                  │    │   │
│   │  └─────────────────────────────────────────────────────────────────┘    │   │
│   │                                                                          │   │
│   │  ┌─────────────────────────────────────────────────────────────────┐    │   │
│   │  │ Agent Templates                                                  │    │   │
│   │  │  • Single Agent (LLM + Tools)                                   │    │   │
│   │  │  • ReAct Agent (Reasoning + Acting Loop)                        │    │   │
│   │  │  • Multi-Agent System (Orchestrator + Specialists)              │    │   │
│   │  │  • Code Agent (LLM + Code Execution + Sandbox)                  │    │   │
│   │  │  • Research Agent (Web Search + Summarization)                  │    │   │
│   │  └─────────────────────────────────────────────────────────────────┘    │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │                         COMPONENT LIBRARY                               │   │
│   │                                                                          │   │
│   │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐         │   │
│   │  │ Model Endpoints │  │ Vector Databases│  │ Orchestrators   │         │   │
│   │  │                 │  │                 │  │                 │         │   │
│   │  │ • LLM (vLLM)    │  │ • Qdrant        │  │ • LangChain     │         │   │
│   │  │ • Embedding     │  │ • Milvus        │  │ • LlamaIndex    │         │   │
│   │  │ • Reranker      │  │ • Weaviate      │  │ • LangGraph     │         │   │
│   │  │ • Vision        │  │ • pgvector      │  │ • CrewAI        │         │   │
│   │  │ • STT/TTS       │  │ • Chroma        │  │ • Custom        │         │   │
│   │  └─────────────────┘  └─────────────────┘  └─────────────────┘         │   │
│   │                                                                          │   │
│   │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐         │   │
│   │  │ Storage         │  │ Memory/State    │  │ Applications    │         │   │
│   │  │                 │  │                 │  │                 │         │   │
│   │  │ • MinIO/S3      │  │ • Redis/Valkey  │  │ • Chat UI       │         │   │
│   │  │ • PostgreSQL    │  │ • PostgreSQL    │  │ • API Gateway   │         │   │
│   │  │ • ClickHouse    │  │ • MongoDB       │  │ • Admin Panel   │         │   │
│   │  └─────────────────┘  └─────────────────┘  └─────────────────┘         │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 8.2 Component Registry

The Component Registry is the core of BudUseCases extensibility. Components are stored in a database
and define HOW to deploy each type of service. Templates reference components by ID.

**Key Design Principle:** Adding new templates or components requires NO code changes - only database entries.

#### 7.2.1 Component Registry Schema

```python
class DeploymentType(str, Enum):
    HELM = "helm"           # Helm chart deployment
    DOCKER = "docker"       # Direct Docker/container deployment
    MODEL = "model"         # Model endpoint (via BudCluster's bud_runtime_container)

class ComponentCategory(str, Enum):
    MODEL_ENDPOINT = "model_endpoint"   # LLM, Embedding, Reranker, etc.
    DATABASE = "database"               # Vector DBs, PostgreSQL, etc.
    SERVICE = "service"                 # Orchestrators, custom services
    APPLICATION = "application"         # UIs, gateways
    STORAGE = "storage"                 # MinIO, S3, etc.
    CACHE = "cache"                     # Redis, Valkey, etc.

class ComponentDefinition(SQLModel):
    """
    Component Registry entry - defines HOW to deploy a component.
    Templates reference components by ID.
    """
    id: str                              # e.g., "qdrant", "rag-orchestrator", "vllm-endpoint"
    name: str                            # Human-readable name
    description: str
    category: ComponentCategory
    version: str                         # Component definition version

    # Deployment configuration
    deployment_type: DeploymentType

    # For HELM deployments
    helm_repo: Optional[str]             # e.g., "https://qdrant.github.io/qdrant-helm"
    helm_chart: Optional[str]            # e.g., "qdrant/qdrant"
    helm_version: Optional[str]          # e.g., "1.12.x"
    default_values: Optional[dict]       # Default Helm values

    # For DOCKER deployments
    image: Optional[str]                 # e.g., "ghcr.io/budecosystem/rag-orchestrator"
    image_tag: Optional[str]             # e.g., "latest" or "v1.2.0"
    default_command: Optional[list[str]]
    default_args: Optional[list[str]]

    # For MODEL deployments (uses BudCluster's bud_runtime_container)
    model_engine: Optional[str]          # "vllm", "latentbud", "tgi"
    default_gpu_type: Optional[str]      # "nvidia-a100-80gb"
    default_gpu_count: Optional[int]

    # Common configuration
    default_env: dict = {}               # Default environment variables
    default_resources: dict = {}         # CPU, memory defaults
    required_inputs: list[str] = []      # Inputs that MUST be provided by template
    outputs: list[str] = []              # What this component exposes (url, api_key, etc.)

    # Health & readiness
    health_check_path: Optional[str]     # e.g., "/health"
    readiness_timeout_seconds: int = 300

    # Metadata
    tags: list[str] = []                 # For filtering/search
    documentation_url: Optional[str]
    is_active: bool = True


class ComponentVersion(SQLModel):
    """Track multiple versions of a component definition"""
    id: UUID
    component_id: str
    version: str
    definition: dict                     # Full ComponentDefinition as JSON
    created_at: datetime
    is_default: bool = False
```

#### 7.2.2 Example Component Definitions

```json
[
  {
    "id": "qdrant",
    "name": "Qdrant Vector Database",
    "description": "High-performance vector database for similarity search",
    "category": "database",
    "version": "1.0.0",
    "deployment_type": "helm",
    "helm_repo": "https://qdrant.github.io/qdrant-helm",
    "helm_chart": "qdrant/qdrant",
    "helm_version": "1.12.x",
    "default_values": {
      "replicaCount": 1,
      "persistence": { "size": "50Gi" },
      "resources": {
        "requests": { "memory": "4Gi", "cpu": "2" },
        "limits": { "memory": "8Gi", "cpu": "4" }
      }
    },
    "default_env": {},
    "required_inputs": [],
    "outputs": ["url", "api_key", "grpc_url"],
    "health_check_path": "/readyz",
    "tags": ["vector-db", "qdrant", "similarity-search"]
  },
  {
    "id": "rag-orchestrator",
    "name": "RAG Orchestrator Service",
    "description": "Bud's RAG orchestration service with retrieval and generation",
    "category": "service",
    "version": "1.0.0",
    "deployment_type": "docker",
    "image": "ghcr.io/budecosystem/rag-orchestrator",
    "image_tag": "latest",
    "default_env": {
      "LOG_LEVEL": "INFO",
      "MAX_CONTEXT_LENGTH": "4096"
    },
    "default_resources": {
      "requests": { "memory": "2Gi", "cpu": "1" },
      "limits": { "memory": "4Gi", "cpu": "2" }
    },
    "required_inputs": ["VECTOR_DB_URL", "EMBEDDING_URL", "LLM_URL"],
    "outputs": ["url", "health_endpoint"],
    "health_check_path": "/health",
    "tags": ["rag", "orchestrator", "retrieval"]
  },
  {
    "id": "vllm-endpoint",
    "name": "vLLM Model Endpoint",
    "description": "High-throughput LLM serving with vLLM engine",
    "category": "model_endpoint",
    "version": "1.0.0",
    "deployment_type": "model",
    "model_engine": "vllm",
    "default_gpu_type": "nvidia-a100-80gb",
    "default_gpu_count": 1,
    "default_env": {
      "VLLM_ATTENTION_BACKEND": "FLASH_ATTN"
    },
    "required_inputs": ["model_id"],
    "outputs": ["url", "metrics_url"],
    "health_check_path": "/health",
    "tags": ["llm", "vllm", "inference"]
  },
  {
    "id": "chat-ui",
    "name": "Chat Interface",
    "description": "Web-based chat UI for conversational AI",
    "category": "application",
    "version": "1.0.0",
    "deployment_type": "docker",
    "image": "ghcr.io/budecosystem/chat-ui",
    "image_tag": "latest",
    "default_env": {
      "THEME": "light"
    },
    "default_resources": {
      "requests": { "memory": "512Mi", "cpu": "0.5" },
      "limits": { "memory": "1Gi", "cpu": "1" }
    },
    "required_inputs": ["API_ENDPOINT"],
    "outputs": ["url"],
    "health_check_path": "/",
    "tags": ["ui", "chat", "frontend"]
  }
]
```

#### 7.2.3 Component Registry API

```yaml
# Component Management
POST   /api/v1/components                    # Create new component definition
GET    /api/v1/components                    # List all components (with filters)
GET    /api/v1/components/{id}               # Get component by ID
PUT    /api/v1/components/{id}               # Update component definition
DELETE /api/v1/components/{id}               # Soft delete (set is_active=false)

# Component Versions
GET    /api/v1/components/{id}/versions      # List all versions
POST   /api/v1/components/{id}/versions      # Create new version
PUT    /api/v1/components/{id}/versions/{v}/default  # Set default version

# Component Search
GET    /api/v1/components/search?category=database&tags=vector-db
```

### 8.3 Use Case Template Schema

Templates define complete use case deployments. They reference components from the registry and define how to wire them together.

**Key Design Principles:**

1. **Hybrid Storage**: System templates are YAML files (version controlled in Git), loaded into database at startup
2. **Database Runtime**: All templates (system + user-created) live in database for queries and API access
3. **No Code Changes**: Adding/updating templates = editing YAML files or API calls (no code deployment needed)

#### 8.3.0 Template File Structure

```
services/budusecases/
├── templates/
│   ├── system/                        # Git-tracked system templates
│   │   ├── rag/
│   │   │   ├── simple-rag-v1.yaml
│   │   │   └── enterprise-rag-v1.yaml
│   │   ├── chatbot/
│   │   │   ├── simple-chatbot-v1.yaml
│   │   │   └── chatbot-memory-v1.yaml
│   │   └── agent/
│   │       └── simple-agent-v1.yaml
│   └── seed.py                        # Loads YAML → DB on startup
└── budusecases/
    └── templates/
        ├── models.py                  # SQLAlchemy models
        ├── schemas.py                 # Pydantic validation
        └── loader.py                  # YAML parsing + DB sync
```

#### 8.3.0.1 Example System Template (YAML)

```yaml
# templates/system/rag/simple-rag-v1.yaml
id: simple-rag-v1
name: Simple RAG
description: Basic RAG pipeline with vector search, embedding, and LLM generation
category: rag
version: "1.0.0"
complexity: simple
tags: [rag, vector-search, retrieval, beginner]

parameters:
  - name: model_id
    type: model_ref
    label: LLM Model
    description: The language model for text generation
    required: true

  - name: embedding_model
    type: string
    label: Embedding Model
    description: Model for generating vector embeddings
    default: "BAAI/bge-base-en-v1.5"
    required: false

  - name: vector_db_size
    type: string
    label: Vector DB Storage Size
    default: "50Gi"
    options: ["10Gi", "50Gi", "100Gi", "500Gi"]

  - name: gpu_type
    type: string
    label: GPU Type
    default: "nvidia-a100-40gb"
    options: ["nvidia-t4", "nvidia-a10g", "nvidia-a100-40gb", "nvidia-a100-80gb"]

components:
  - id: vector-db
    component_ref: qdrant
    config:
      persistence:
        size: "{{ parameters.vector_db_size }}"
      resources:
        requests:
          memory: "4Gi"
          cpu: "2"

  - id: embedding
    component_ref: tei-embedding
    config:
      model_id: "{{ parameters.embedding_model }}"
    resources:
      requests:
        memory: "4Gi"
        cpu: "2"

  - id: llm
    component_ref: vllm-endpoint
    model_id: "{{ parameters.model_id }}"
    gpu_type: "{{ parameters.gpu_type }}"
    gpu_count: 1
    optimize_with_budsim: true

  - id: orchestrator
    component_ref: rag-orchestrator
    depends_on: [vector-db, embedding, llm]
    env:
      VECTOR_DB_URL: "{{ components['vector-db'].outputs.url }}"
      EMBEDDING_URL: "{{ components['embedding'].outputs.url }}"
      LLM_URL: "{{ components['llm'].outputs.url }}"
    config:
      max_context_length: 4096
      retrieval_top_k: 5

routing:
  entrypoint: orchestrator
  path_prefix: /rag

observability:
  dashboard: rag-default
  alerts:
    - name: high-latency
      condition: p99_latency > 5s
```

#### 8.3.0.2 Template Loader (Startup Sync)

```python
# services/budusecases/templates/seed.py
import yaml
from pathlib import Path
from budusecases.templates.crud import TemplateCRUD

TEMPLATES_DIR = Path(__file__).parent / "system"

async def seed_system_templates(db: AsyncSession):
    """
    Load system templates from YAML files into database.
    Called on service startup.

    Behavior:
    - New templates: INSERT
    - Existing with same version: SKIP
    - Existing with different version: UPDATE (preserve user customizations flag)
    """
    crud = TemplateCRUD(db)

    for yaml_file in TEMPLATES_DIR.rglob("*.yaml"):
        template_data = yaml.safe_load(yaml_file.read_text())
        template_id = template_data["id"]

        existing = await crud.get_by_id(template_id)

        if existing is None:
            # New template - create it
            await crud.create(
                **template_data,
                is_system=True,
                source_file=str(yaml_file.relative_to(TEMPLATES_DIR))
            )
            logger.info(f"Created system template: {template_id}")

        elif existing.version != template_data["version"]:
            # Version changed - update it
            await crud.update(
                template_id,
                **template_data,
                is_system=True
            )
            logger.info(f"Updated system template: {template_id} to v{template_data['version']}")

        else:
            # Same version - skip
            logger.debug(f"System template unchanged: {template_id}")

async def validate_all_templates():
    """Validate all YAML templates against schema before loading."""
    errors = []
    for yaml_file in TEMPLATES_DIR.rglob("*.yaml"):
        try:
            data = yaml.safe_load(yaml_file.read_text())
            UseCaseTemplateSchema(**data)  # Pydantic validation
        except Exception as e:
            errors.append(f"{yaml_file}: {e}")

    if errors:
        raise ValueError(f"Template validation failed:\n" + "\n".join(errors))
```

#### 7.3.1 Template Schema

```python
class UseCaseTemplate(SQLModel):
    """
    Use Case Template - defines WHAT to deploy and how components connect.
    """
    id: str                              # e.g., "enterprise-rag-v1"
    name: str
    description: str
    category: str                        # "rag", "chatbot", "agent"
    version: str

    # User-facing configuration
    parameters: list[TemplateParameter]  # User inputs when deploying

    # Component graph
    components: list[TemplateComponent]  # What to deploy

    # Wiring
    routing: Optional[dict]              # BudGateway route configuration
    observability: Optional[dict]        # Dashboards, alerts

    # Metadata
    estimated_monthly_cost_usd: Optional[str]
    complexity: str                      # "simple", "intermediate", "advanced"
    tags: list[str] = []
    documentation_url: Optional[str]
    is_active: bool = True


class TemplateParameter(SQLModel):
    """User-configurable parameter for a template"""
    name: str                            # e.g., "llm_model"
    type: str                            # "string", "integer", "boolean", "enum", "model_ref", "cluster_ref"
    label: str                           # Human-readable label
    description: Optional[str]
    required: bool = True
    default: Optional[Any]
    options: Optional[list[Any]]         # For enum types
    min: Optional[float]                 # For numeric types
    max: Optional[float]


class TemplateComponent(SQLModel):
    """Component instance within a template"""
    id: str                              # Instance ID within template (e.g., "my-vector-db")
    component_ref: str                   # Reference to ComponentDefinition.id (e.g., "qdrant")

    # Conditional deployment
    condition: Optional[str]             # Jinja2 condition: "{{ params.enable_reranker }}"

    # Configuration overrides (merged with component defaults)
    config: dict = {}                    # Helm values or Docker config overrides
    env: dict = {}                       # Environment variable overrides (supports Jinja2)
    resources: Optional[dict]            # Resource overrides

    # For model endpoints
    model_id: Optional[str]              # "{{ params.llm_model }}"
    gpu_type: Optional[str]
    gpu_count: Optional[int]
    optimize_with_budsim: bool = False

    # Dependencies
    depends_on: list[str] = []           # Other component instance IDs

    # Output mapping
    output_mappings: dict = {}           # Map component outputs to custom names
```

#### 8.3.2 Template Storage (Hybrid Model)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    HYBRID TEMPLATE & COMPONENT STORAGE                           │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   SOURCE OF TRUTH                                                               │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │                                                                          │   │
│   │   SYSTEM TEMPLATES (Git-tracked)         USER TEMPLATES (API-created)   │   │
│   │   ┌──────────────────────────┐          ┌──────────────────────────┐    │   │
│   │   │  templates/system/       │          │  POST /api/v1/templates  │    │   │
│   │   │  ├── rag/                │          │                          │    │   │
│   │   │  │   └── simple-rag.yaml │          │  Created via API or UI   │    │   │
│   │   │  ├── chatbot/            │          │  is_system = false       │    │   │
│   │   │  └── agent/              │          │                          │    │   │
│   │   │                          │          │                          │    │   │
│   │   │  • Version controlled    │          │  • Per-tenant            │    │   │
│   │   │  • PR review for changes │          │  • Runtime creation      │    │   │
│   │   │  • is_system = true      │          │  • Fork from system      │    │   │
│   │   └──────────────────────────┘          └──────────────────────────┘    │   │
│   │              │                                    │                      │   │
│   │              │  On startup                        │  Direct              │   │
│   │              │  (seed.py)                         │                      │   │
│   │              ▼                                    ▼                      │   │
│   │   ┌─────────────────────────────────────────────────────────────────┐   │   │
│   │   │                   PostgreSQL (Runtime Storage)                   │   │   │
│   │   │                                                                  │   │   │
│   │   │  use_case_templates                                              │   │   │
│   │   │  ┌────────────────────────────────────────────────────────────┐ │   │   │
│   │   │  │ id (PK)           │ is_system (bool)   │ source_file       │ │   │   │
│   │   │  │ name              │ tenant_id (nullable)│ created_by       │ │   │   │
│   │   │  │ category          │ forked_from        │ parameters (JSONB)│ │   │   │
│   │   │  │ version           │ is_active          │ components (JSONB)│ │   │   │
│   │   │  └────────────────────────────────────────────────────────────┘ │   │   │
│   │   │                                                                  │   │   │
│   │   └─────────────────────────────────────────────────────────────────┘   │   │
│   │                                                                          │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│   WORKFLOW:                                                                     │
│   • System templates: Edit YAML → PR review → Merge → Deploy → Auto-sync to DB │
│   • User templates: UI/API → Direct DB insert → Immediate availability          │
│   • Fork system template: Copy system template → Set is_system=false, tenant_id │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Benefits of Hybrid Approach:**

| Aspect | System Templates (YAML) | User Templates (DB) |
|--------|------------------------|---------------------|
| Version control | Git history, PR reviews | Audit table |
| Deployment | Code deploy syncs to DB | Immediate via API |
| Validation | CI/CD + startup validation | API validation |
| Rollback | Git revert + redeploy | DB version table |
| Multi-tenant | Same for all tenants | Per-tenant isolation |
| Discoverability | IDE support, grep | SQL queries, API |

### 8.4 Template-Driven Orchestration

The orchestration engine is **generic** - it reads templates and executes them without
template-specific code.

#### 7.4.1 Orchestration Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      TEMPLATE-DRIVEN ORCHESTRATION FLOW                          │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   USER REQUEST                                                                  │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │ POST /api/v1/usecases/deploy                                            │   │
│   │ {                                                                        │   │
│   │   "template_id": "enterprise-rag-v1",                                   │   │
│   │   "name": "my-rag-system",                                              │   │
│   │   "cluster_id": "cluster-123",                                          │   │
│   │   "parameters": {                                                        │   │
│   │     "llm_model": "meta-llama/Llama-3.3-70B-Instruct",                   │   │
│   │     "embedding_model": "BAAI/bge-large-en-v1.5",                        │   │
│   │     "vector_db": "qdrant",                                              │   │
│   │     "enable_reranker": true                                             │   │
│   │   }                                                                      │   │
│   │ }                                                                        │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                          │                                      │
│                                          ▼                                      │
│   STEP 1: TEMPLATE RESOLUTION                                                   │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │ BudUseCases:                                                            │   │
│   │  1. Load template from DB: use_case_templates[enterprise-rag-v1]        │   │
│   │  2. Validate parameters against template.parameters schema              │   │
│   │  3. For each component in template.components:                          │   │
│   │     a. Load component definition from DB: component_definitions[ref]    │   │
│   │     b. Evaluate condition (if any): "{{ params.enable_reranker }}"     │   │
│   │     c. Merge: component defaults + template overrides + user params     │   │
│   │  4. Build dependency graph from depends_on                              │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                          │                                      │
│                                          ▼                                      │
│   STEP 2: DAG GENERATION                                                        │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │ BudPipeline:                                                            │   │
│   │                                                                          │   │
│   │   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐                   │   │
│   │   │qdrant   │  │embedding│  │reranker │  │  llm    │   Step 1          │   │
│   │   │(helm)   │  │(model)  │  │(model)  │  │(model)  │   (parallel)      │   │
│   │   └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘                   │   │
│   │        │            │            │            │                         │   │
│   │        └────────────┴─────┬──────┴────────────┘                         │   │
│   │                           ▼                                              │   │
│   │                    ┌─────────────┐                                       │   │
│   │                    │rag-orch    │   Step 2                              │   │
│   │                    │(docker)    │   (wait for Step 1)                   │   │
│   │                    └──────┬─────┘                                       │   │
│   │                           ▼                                              │   │
│   │                    ┌─────────────┐                                       │   │
│   │                    │  chat-ui   │   Step 3                              │   │
│   │                    │ (docker)   │   (wait for Step 2)                   │   │
│   │                    └────────────┘                                       │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                          │                                      │
│                                          ▼                                      │
│   STEP 3: DEPLOYMENT EXECUTION                                                  │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │ For each step in DAG (in order):                                        │   │
│   │   For each component in step (parallel):                                │   │
│   │                                                                          │   │
│   │     SWITCH component.deployment_type:                                   │   │
│   │                                                                          │   │
│   │     CASE "helm":                                                        │   │
│   │       → BudCluster.deploy_helm({                                        │   │
│   │           cluster_id, chart, repo, version, values (merged)             │   │
│   │         })                                                               │   │
│   │                                                                          │   │
│   │     CASE "docker":                                                      │   │
│   │       → BudCluster.deploy_docker({                                      │   │
│   │           cluster_id, image, tag, env (resolved), resources             │   │
│   │         })                                                               │   │
│   │       # Uses BudCluster's generic Deployment/Service chart              │   │
│   │                                                                          │   │
│   │     CASE "model":                                                       │   │
│   │       → BudCluster.deploy_model({                                       │   │
│   │           cluster_id, model_id, engine, gpu_type, gpu_count             │   │
│   │         })                                                               │   │
│   │       # Optionally call BudSim for optimization first                   │   │
│   │       # Uses BudCluster's bud_runtime_container chart                   │   │
│   │                                                                          │   │
│   │     Wait for health check: GET {component.url}{health_check_path}       │   │
│   │     Store outputs: url, api_key, etc. → context for next steps          │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                          │                                      │
│                                          ▼                                      │
│   STEP 4: WIRING & FINALIZATION                                                 │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │ 1. Configure BudGateway routes (from template.routing)                  │   │
│   │ 2. Create observability dashboards (from template.observability)        │   │
│   │ 3. Store deployment record in usecase_deployments table                 │   │
│   │ 4. Return deployment status + component URLs to user                    │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

#### 7.4.2 BudCluster Deployment Interface

BudCluster provides three deployment methods that the orchestrator calls:

```python
# BudCluster Service API (called by BudUseCases orchestrator)

class BudClusterDeploymentAPI:

    async def deploy_helm(
        self,
        cluster_id: UUID,
        release_name: str,
        helm_repo: str,
        helm_chart: str,
        helm_version: str,
        values: dict,
        namespace: str = "default"
    ) -> DeploymentResult:
        """
        Deploy any Helm chart to a cluster.
        Used for: databases (Qdrant, Milvus), caches (Redis), etc.
        """
        pass

    async def deploy_docker(
        self,
        cluster_id: UUID,
        release_name: str,
        image: str,
        tag: str,
        env: dict,
        resources: dict,
        replicas: int = 1,
        ports: list[int] = [8000],
        health_check_path: str = "/health",
        namespace: str = "default"
    ) -> DeploymentResult:
        """
        Deploy a Docker container using generic Kubernetes manifests.
        Uses internal bud-generic-service Helm chart.
        Used for: orchestrators, UIs, custom services.
        """
        pass

    async def deploy_model(
        self,
        cluster_id: UUID,
        release_name: str,
        model_id: str,
        engine: str,  # "vllm", "latentbud", "tgi"
        gpu_type: str,
        gpu_count: int,
        tensor_parallel_size: int = 1,
        extra_env: dict = {},
        budsim_config: Optional[dict] = None,  # If provided, optimize first
        namespace: str = "default"
    ) -> DeploymentResult:
        """
        Deploy a model endpoint using bud_runtime_container chart.
        Integrates with Kueue for quota checking.
        Optionally calls BudSim for configuration optimization.
        """
        pass


class DeploymentResult(BaseModel):
    success: bool
    release_name: str
    namespace: str
    outputs: dict  # {"url": "http://...", "api_key": "...", etc.}
    error: Optional[str]
```

### 8.5 Enterprise RAG Template Example

```json
{
  "schema_version": "1.0",
  "template": {
    "id": "enterprise-rag-v1",
    "name": "Enterprise RAG System",
    "description": "Production-ready RAG with embedding, reranking, and LLM",
    "category": "rag",
    "complexity": "advanced",
    "estimated_monthly_cost_usd": "500-2000",

    "parameters": [
      {
        "name": "cluster_id",
        "type": "cluster_ref",
        "label": "Target Cluster",
        "required": true
      },
      {
        "name": "embedding_model",
        "type": "model_ref",
        "label": "Embedding Model",
        "default": "BAAI/bge-large-en-v1.5",
        "options": [
          "BAAI/bge-large-en-v1.5",
          "sentence-transformers/all-MiniLM-L6-v2",
          "intfloat/e5-large-v2"
        ]
      },
      {
        "name": "reranker_model",
        "type": "model_ref",
        "label": "Reranker Model",
        "default": "BAAI/bge-reranker-v2-m3",
        "optional": true
      },
      {
        "name": "llm_model",
        "type": "model_ref",
        "label": "Generation LLM",
        "default": "meta-llama/Llama-3.3-70B-Instruct",
        "required": true
      },
      {
        "name": "vector_db",
        "type": "enum",
        "label": "Vector Database",
        "options": ["qdrant", "milvus", "weaviate"],
        "default": "qdrant"
      },
      {
        "name": "chunk_size",
        "type": "integer",
        "label": "Document Chunk Size",
        "default": 512,
        "min": 128,
        "max": 2048
      },
      {
        "name": "enable_budsim",
        "type": "boolean",
        "label": "Enable Performance Optimization",
        "default": true
      }
    ],

    "components": [
      {
        "id": "vector-db",
        "type": "database",
        "provider": "{{ params.vector_db }}",
        "config": {
          "qdrant": {
            "helm_chart": "qdrant/qdrant",
            "helm_version": "1.12.x",
            "values": {
              "replicaCount": 1,
              "persistence": {
                "size": "50Gi",
                "storageClass": "{{ cluster.default_storage_class }}"
              },
              "resources": {
                "requests": { "memory": "4Gi", "cpu": "2" },
                "limits": { "memory": "8Gi", "cpu": "4" }
              }
            }
          }
        },
        "outputs": ["url", "api_key"]
      },
      {
        "id": "embedding-endpoint",
        "type": "model_endpoint",
        "model": "{{ params.embedding_model }}",
        "engine": "latentbud",
        "config": {
          "replicas": 2,
          "gpu_type": "nvidia-t4",
          "gpu_count": 1,
          "autoscaling": {
            "min_replicas": 1,
            "max_replicas": 5,
            "target_queue_depth": 10
          }
        },
        "outputs": ["url"]
      },
      {
        "id": "reranker-endpoint",
        "type": "model_endpoint",
        "condition": "{{ params.reranker_model is not none }}",
        "model": "{{ params.reranker_model }}",
        "engine": "latentbud",
        "config": {
          "replicas": 1,
          "gpu_type": "nvidia-t4",
          "gpu_count": 1
        },
        "outputs": ["url"]
      },
      {
        "id": "llm-endpoint",
        "type": "model_endpoint",
        "model": "{{ params.llm_model }}",
        "engine": "vllm",
        "config": {
          "replicas": 1,
          "gpu_type": "nvidia-a100-80gb",
          "gpu_count": 2,
          "tensor_parallel_size": 2,
          "autoscaling": {
            "min_replicas": 1,
            "max_replicas": 3,
            "target_kv_cache_util": 0.8
          }
        },
        "optimize_with_budsim": "{{ params.enable_budsim }}",
        "outputs": ["url"]
      },
      {
        "id": "rag-orchestrator",
        "type": "service",
        "image": "ghcr.io/budecosystem/rag-orchestrator:latest",
        "depends_on": ["vector-db", "embedding-endpoint", "llm-endpoint"],
        "config": {
          "replicas": 2,
          "env": {
            "VECTOR_DB_URL": "{{ components.vector-db.url }}",
            "VECTOR_DB_API_KEY": "{{ components.vector-db.api_key }}",
            "EMBEDDING_URL": "{{ components.embedding-endpoint.url }}",
            "RERANKER_URL": "{{ components.reranker-endpoint.url | default('') }}",
            "LLM_URL": "{{ components.llm-endpoint.url }}",
            "CHUNK_SIZE": "{{ params.chunk_size }}"
          }
        },
        "outputs": ["url"]
      },
      {
        "id": "chat-ui",
        "type": "application",
        "template": "chat-interface",
        "depends_on": ["rag-orchestrator"],
        "config": {
          "title": "{{ usecase.name }} Chat",
          "api_endpoint": "{{ components.rag-orchestrator.url }}/chat"
        },
        "outputs": ["url"]
      }
    ],

    "routing": {
      "budgateway": {
        "routes": [
          {
            "path": "/v1/chat/completions",
            "target": "{{ components.rag-orchestrator.url }}/v1/chat/completions"
          },
          {
            "path": "/v1/embeddings",
            "target": "{{ components.embedding-endpoint.url }}/embeddings"
          },
          {
            "path": "/v1/ingest",
            "target": "{{ components.rag-orchestrator.url }}/ingest"
          }
        ]
      }
    },

    "observability": {
      "metrics": [
        "rag_query_latency_p99",
        "rag_retrieval_precision",
        "llm_tokens_per_second",
        "embedding_requests_per_second"
      ],
      "dashboards": ["rag-overview", "model-performance"],
      "alerts": [
        {
          "name": "high-latency",
          "metric": "rag_query_latency_p99",
          "threshold": 5000,
          "operator": "gt",
          "action": "notify"
        }
      ]
    }
  }
}
```

---

## Part 9: Unified Data Model

### 9.1 Core Entities

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                              UNIFIED DATA MODEL                                           │
├──────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│   ┌─────────────┐         ┌─────────────┐         ┌─────────────┐                       │
│   │   Tenant    │────────►│   Project   │────────►│  Workload   │                       │
│   │             │   1:N   │             │   1:N   │             │                       │
│   │ • id        │         │ • id        │         │ • id        │                       │
│   │ • name      │         │ • tenant_id │         │ • project_id│                       │
│   │ • quota     │         │ • name      │         │ • type      │                       │
│   │ • billing   │         │ • clusters  │         │ • status    │                       │
│   └─────────────┘         └─────────────┘         └──────┬──────┘                       │
│                                                          │                               │
│                           ┌──────────────────────────────┼──────────────────┐            │
│                           │                              │                  │            │
│                   ┌───────▼───────┐              ┌───────▼───────┐          │            │
│                   │     Pod       │              │  Serverless   │          │            │
│                   │               │              │   Endpoint    │          │            │
│                   │ • gpu_type    │              │               │          │            │
│                   │ • gpu_count   │              │ • gpu_type    │          │            │
│                   │ • ssh_access  │              │ • min_replicas│          │            │
│                   │ • storage     │              │ • max_replicas│          │            │
│                   │ • image       │              │ • warm_pool   │          │            │
│                   └───────┬───────┘              └───────┬───────┘          │            │
│                           │                              │                  │            │
│                           └───────────┬──────────────────┘                  │            │
│                                       │                                     │            │
│                                       ▼                                     │            │
│                               ┌───────────────┐                  ┌──────────▼──────┐    │
│                               │     JOB       │◄─────────────────│   UseCase       │    │
│                               │  (BudCluster) │                  │   Deployment    │    │
│                               │               │                  │                 │    │
│                               │ • id          │                  │ • template_id   │    │
│                               │ • job_type    │                  │ • components    │    │
│                               │ • source_type │                  │ • parameters    │    │
│                               │ • source_id   │                  └─────────────────┘    │
│                               │ • priority    │                                         │
│                               │ • status      │                                         │
│                               │ • gpu_type    │                                         │
│                               │ • gpu_count   │                                         │
│                               │ • est_start   │                                         │
│                               │ • est_end     │                                         │
│                               └───────────────┘                                         │
│                                       ▲                                                 │
│                                       │ Only JOB-type                                   │
│                                       │ steps create Jobs                               │
│                                       │                                                 │
│   ┌─────────────┐         ┌───────────┴───┐         ┌─────────────┐                    │
│   │  Pipeline   │────────►│     Step      │         │  Trigger    │                    │
│   │ (BudPipeline)│   1:N  │               │         │             │                    │
│   │             │         │ • id          │         │ • type      │                    │
│   │ • id        │         │ • step_type   │◄────────│ • schedule  │                    │
│   │ • name      │         │ • config      │         │ • event     │                    │
│   │ • dag       │         │ • depends_on  │         │             │                    │
│   │ • status    │         │ • status      │         └─────────────┘                    │
│   └─────────────┘         └───────────────┘                                            │
│                                                                                          │
│   Step Types (only JOB creates Jobs):                                                    │
│   ├── JOB ────────► Creates Job in BudCluster (requires GPU/CPU resources)              │
│   ├── API_CALL ───► No Job, runs in pipeline engine                                     │
│   ├── FUNCTION ───► No Job, runs in pipeline engine                                     │
│   ├── NOTIFICATION► No Job, sends notification                                          │
│   ├── CONDITION ──► No Job, flow control                                                │
│   ├── WAIT ───────► No Job, flow control                                                │
│   ├── LOOP ───────► No Job, flow control                                                │
│   └── PARALLEL ───► No Job, parallel execution control                                  │
│                                                                                          │
│   ┌─────────────┐         ┌─────────────┐         ┌─────────────┐                       │
│   │  GPUPool    │────────►│GPUAllocation│────────►│UsageRecord  │                       │
│   │             │   1:N   │             │   1:N   │             │                       │
│   │ • cluster_id│         │ • pool_id   │         │ • alloc_id  │                       │
│   │ • gpu_type  │         │ • workload  │         │ • gpu_secs  │                       │
│   │ • capacity  │         │ • start/end │         │ • cost      │                       │
│   │ • available │         │ • mode      │         │ • timestamp │                       │
│   └─────────────┘         └─────────────┘         └─────────────┘                       │
│                                                                                          │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

### 9.2 Data Ownership by Service

| Entity | Owner Service | Database | Referenced By |
|--------|--------------|----------|---------------|
| **Tenant** | BudApp | PostgreSQL | Project, Quota |
| **Project** | BudApp | PostgreSQL | Workload, Endpoint |
| **Job** | BudCluster | PostgreSQL | Endpoint (job_id), Step (job_id) |
| **Pipeline** | BudPipeline | PostgreSQL | Step, UseCase Deployment |
| **Step** | BudPipeline | PostgreSQL | Job (if JOB type) |
| **Endpoint** | BudApp | PostgreSQL | Job |
| **UseCase Template** | BudUseCases | PostgreSQL | Pipeline, Component |
| **Component** | BudUseCases | PostgreSQL | UseCase Template |
| **GPUPool** | BudCluster | PostgreSQL | GPUAllocation |
| **UsageRecord** | BudMetrics | ClickHouse | Job, GPUAllocation |

---

## Part 10: Implementation Roadmap

### 10.1 Phase Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         IMPLEMENTATION ROADMAP                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   PHASE 1: JOB LAYER & FOUNDATION (10-12 weeks)                                 │
│   ─────────────────────────────────────────────                                 │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │ Goal: Job abstraction layer + Basic GPU-as-a-Service with metering      │   │
│   │                                                                          │   │
│   │ Deliverables:                                                            │   │
│   │ • Job model in BudCluster (schema, CRUD, status tracking)               │   │
│   │ • Job API: POST/GET/DELETE /clusters/{id}/jobs                          │   │
│   │ • Schedule Timeline API: GET /clusters/{id}/schedule                    │   │
│   │ • Internal job creation for existing model deployments                  │   │
│   │ • GPU Pool management (CRUD operations)                                 │   │
│   │ • Basic Pod deployment → creates SERVICE Job                            │   │
│   │ • BudMetrics metering extension (per-minute tracking, remote-write)     │   │
│   │ • BudCluster monitoring stack deployment (Helm chart for Prom+DCGM)     │   │
│   │ • BudAdmin: GPU inventory, Pod UI, Schedule Timeline view               │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│   PHASE 2: PIPELINE LAYER & SERVERLESS (10-12 weeks)                            │
│   ──────────────────────────────────────────────                                │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │ Goal: Pipeline orchestration + Serverless endpoints with auto-scaling   │   │
│   │                                                                          │   │
│   │ Deliverables:                                                            │   │
│   │ • BudPipeline: Pipeline & Step models with all step types               │   │
│   │ • JOB-type step integration → creates Job via BudCluster                │   │
│   │ • API_CALL, FUNCTION, NOTIFICATION step execution                       │   │
│   │ • CONDITION, WAIT, LOOP, PARALLEL flow control                          │   │
│   │ • Trigger types: cron, event, manual                                    │   │
│   │ • BudQueue service (request queuing, priority)                          │   │
│   │ • Serverless endpoint deployment → creates SERVICE Job                  │   │
│   │ • Scale-to-zero implementation                                          │   │
│   │ • Per-second billing                                                    │   │
│   │ • BudAdmin: Pipeline DAG editor, Serverless endpoint UI                 │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│   PHASE 3: SCHEDULING & QUOTAS (6-8 weeks)                                      │
│   ────────────────────────────────────────                                      │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │ Goal: Advanced GPU scheduling with quotas (Kueue in BudCluster)         │   │
│   │                                                                          │   │
│   │ Deliverables:                                                            │   │
│   │ • Kueue + MultiKueue deployment in BudCluster                           │   │
│   │ • Job → Kueue WorkloadPriority mapping                                  │   │
│   │ • ClusterQueues for job types (SERVICE, BATCH, TRAINING)                │   │
│   │ • LocalQueues for tenants with Cohort fair-share                        │   │
│   │ • ResourceFlavors for GPU types (A100, H100, T4)                        │   │
│   │ • MIG support (A100/H100 partitioning)                                  │   │
│   │ • BudCluster quota APIs (CRUD + usage)                                  │   │
│   │ • Preemption for spot instances                                         │   │
│   │ • BudAdmin: Quota management, Schedule Timeline with estimates          │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│   PHASE 4: USE CASES & TEMPLATES (8-10 weeks)                                   │
│   ───────────────────────────────────────────                                   │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │ Goal: Template-based use case deployment with Component Registry        │   │
│   │                                                                          │   │
│   │ Deliverables:                                                            │   │
│   │ • BudUseCases service                                                   │   │
│   │ • Component Registry (Docker + Helm support)                            │   │
│   │ • UseCase Template schema and resolver                                  │   │
│   │ • Template → Pipeline generation (JOB-type steps for components)        │   │
│   │ • Component library (Vector DBs, Orchestrators)                         │   │
│   │ • RAG template (Simple + Enterprise)                                    │   │
│   │ • Chatbot template                                                      │   │
│   │ • BudAdmin: Use case catalog, deployment wizard, component browser      │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│   PHASE 5: ADVANCED FEATURES (10-12 weeks)                                      │
│   ────────────────────────────────────────                                      │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │ Goal: Enterprise features + P2P GPU marketplace (future)                │   │
│   │                                                                          │   │
│   │ Deliverables:                                                            │   │
│   │ • Agent templates (LangGraph, CrewAI)                                   │   │
│   │ • TRAINING job type with checkpointing                                  │   │
│   │ • Multi-cluster federation (MultiKueue)                                 │   │
│   │ • GPU snapshotting for faster cold starts                               │   │
│   │ • Community GPU hosting (P2P model like Vast.ai)                        │   │
│   │ • Template marketplace                                                  │   │
│   │ • Advanced billing (invoicing, payment integration)                     │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 10.2 Phase 1 Detailed Breakdown (Job Layer & Foundation)

| Week | Focus Area | Deliverables |
|------|------------|--------------|
| 1-2 | Job Model in BudCluster | Job schema, SQLAlchemy models, Alembic migration, CRUD operations |
| 3-4 | Job API | POST/GET/DELETE /clusters/{id}/jobs, schedule timeline API |
| 5-6 | Job Integration | Internal job creation for model deployments, source_type tracking |
| 7-8 | GPU Pool management | Pool CRUD, cluster integration, NFD sync |
| 9-10 | Pod deployment | Pod creation → SERVICE Job, SSH access, storage |
| 10-11 | BudMetrics extension | Remote-write endpoint, ClickHouse schema, metering aggregation |
| 11-12 | BudAdmin UI | GPU inventory, Pod management, Schedule Timeline view

### 10.3 Phase 2 Detailed Breakdown (Pipeline Layer & Serverless)

| Week | Focus Area | Deliverables |
|------|------------|--------------|
| 1-2 | Pipeline & Step Models | BudPipeline schema, all step types, Alembic migration |
| 3-4 | JOB-type Step Integration | Job creation via BudCluster API, status sync |
| 5-6 | Functional Steps | API_CALL, FUNCTION, NOTIFICATION execution |
| 7-8 | Control Flow Steps | CONDITION, WAIT, LOOP, PARALLEL, DAG execution engine |
| 9-10 | BudQueue & Serverless | Request queuing, serverless endpoint deployment |
| 10-12 | BudAdmin UI | Pipeline DAG editor, Serverless UI, usage dashboard

---

## Part 11: Key Differentiators vs Competitors

| Feature | RunPod | CoreWeave | Vast.ai | **Bud (Proposed)** |
|---------|--------|-----------|---------|-------------------|
| **GPU Pods** | ✅ | ✅ | ✅ | ✅ |
| **Serverless** | ✅ | ❌ | ✅ | ✅ |
| **Use Case Templates** | ❌ | ❌ | ❌ | ✅ **Unique** |
| **RAG Deployment** | Manual | Manual | Manual | ✅ **One-click** |
| **Agent Deployment** | ❌ | ❌ | ❌ | ✅ **Templates** |
| **Performance Opt** | ❌ | ❌ | ❌ | ✅ **BudSim** |
| **Model Registry** | ❌ | ❌ | ❌ | ✅ **BudModel** |
| **Multi-cloud** | ✅ | ❌ | ❌ | ✅ |
| **On-premises** | ❌ | ❌ | ❌ | ✅ |
| **P2P Marketplace** | ✅ (Community) | ❌ | ✅ | ✅ (Phase 5) |
| **Observability** | Basic | Basic | Basic | ✅ **BudMetrics** |
| **API Gateway** | ❌ | ❌ | ❌ | ✅ **BudGateway** |

### Bud's Unique Value Proposition

1. **Use Case Templates** - Deploy RAG/Chatbot/Agent with one click
2. **Integrated Performance Optimization** - BudSim for GPU tuning
3. **Full MLOps Stack** - Model registry, metrics, pipelines
4. **Multi-cloud + On-prem** - Single platform for all infrastructure
5. **High-performance Gateway** - Sub-millisecond Rust-based routing

---

## Part 12: Success Metrics & KPIs

This section defines the success metrics for measuring platform health, performance, and business outcomes during development and operation of Bud AI Foundry.

### 12.1 Metric Categories Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         SUCCESS METRICS FRAMEWORK                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   ┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐ │
│   │  INFRASTRUCTURE     │    │     PLATFORM        │    │     BUSINESS        │ │
│   │     METRICS         │    │     METRICS         │    │     METRICS         │ │
│   ├─────────────────────┤    ├─────────────────────┤    ├─────────────────────┤ │
│   │ • GPU Utilization   │    │ • Job Success Rate  │    │ • Revenue/GPU Hour  │ │
│   │ • Cold Start Time   │    │ • Pipeline Success  │    │ • Customer Churn    │ │
│   │ • Uptime/SLA        │    │ • Deployment Rate   │    │ • NPS Score         │ │
│   │ • Scheduling Latency│    │ • Time to Deploy    │    │ • NRR/GRR           │ │
│   │ • Resource Waste    │    │ • Feature Adoption  │    │ • LTV:CAC Ratio     │ │
│   └─────────────────────┘    └─────────────────────┘    └─────────────────────┘ │
│                                                                                 │
│   ┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐ │
│   │   INFERENCE         │    │   OPERATIONAL       │    │   DEVELOPER         │ │
│   │   METRICS           │    │   EXCELLENCE        │    │   EXPERIENCE        │ │
│   ├─────────────────────┤    ├─────────────────────┤    ├─────────────────────┤ │
│   │ • TTFT (P50/P95/P99)│    │ • MTTR              │    │ • Time to First     │ │
│   │ • ITL Latency       │    │ • MTTD              │    │   Deployment        │ │
│   │ • Throughput (TPS)  │    │ • Change Failure    │    │ • Developer NPS     │ │
│   │ • Error Rate        │    │ • Error Budget      │    │ • Adoption Rate     │ │
│   │ • Queue Wait Time   │    │ • API Success Rate  │    │ • 90-day Retention  │ │
│   └─────────────────────┘    └─────────────────────┘    └─────────────────────┘ │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 12.2 Infrastructure Metrics

#### 12.2.1 GPU Utilization Targets

| Workload Type | Target | Alert Threshold | Industry Benchmark |
|---------------|--------|-----------------|-------------------|
| Training workloads | > 80% | < 50% | Manual allocation: 30-50% |
| Inference workloads | > 60% | < 30% | Fluctuating: 40-60% |
| Serverless endpoints | > 40% | < 20% | With scale-to-zero |
| Production threshold | > 35% | < 20% | Below = cloud cheaper than owning |

**Prometheus Metrics (DCGM Exporter):**
```promql
# GPU compute utilization
DCGM_FI_DEV_GPU_UTIL

# More accurate - GPU engine active time
DCGM_FI_PROF_GR_ENGINE_ACTIVE

# GPU memory utilization
(DCGM_FI_DEV_FB_USED / (DCGM_FI_DEV_FB_USED + DCGM_FI_DEV_FB_FREE)) * 100

# Alert: Low GPU utilization (wasted resources)
avg_over_time(DCGM_FI_DEV_GPU_UTIL[1h]) < 20
```

**Target:** Reduce GPU waste from industry-typical 5.5% to < 1% through idle job reapers and automation.

#### 12.2.2 Cold Start Performance

| Scenario | Target | Good | Needs Improvement |
|----------|--------|------|-------------------|
| Warm container | < 200ms | < 500ms | > 1s |
| Cold container (cached) | < 2s | < 5s | > 10s |
| Cold container (new) | < 5s | < 10s | > 30s |
| Model loading (small) | < 3s | < 5s | > 10s |
| Model loading (70B LLM) | < 30s | < 60s | > 120s |

**Industry Benchmarks:**
- RunPod FlashBoot: 48% of cold starts < 200ms, 95% under 2.3 seconds
- Modal GPU snapshots: 2-5 seconds (10x improvement over baseline)

#### 12.2.3 Uptime and Availability SLA

| Service Tier | Target SLA | Max Monthly Downtime | Use Case |
|--------------|------------|---------------------|----------|
| BudGateway (API) | 99.95% | 21.9 minutes | Customer-facing inference |
| BudApp (Control Plane) | 99.9% | 43.2 minutes | Management APIs |
| BudMetrics | 99.9% | 43.2 minutes | Observability |
| BudCluster | 99.9% | 43.2 minutes | Infrastructure management |
| Batch Pipelines | 99.5% | 3.65 hours | Non-real-time workloads |

#### 12.2.4 Scheduling Metrics (Kueue)

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Admission wait time (P50) | < 30s | > 2 min |
| Admission wait time (P99) | < 5 min | > 10 min |
| Scheduling success rate | > 99% | < 95% |
| Pending workloads (inadmissible) | 0 | > 0 for > 30 min |

**Prometheus Metrics:**
```promql
# Admission latency
histogram_quantile(0.99,
  sum(rate(kueue_admission_wait_time_seconds_bucket[5m])) by (cluster_queue, le)
)

# Quota utilization
kueue_cluster_queue_resource_usage / kueue_cluster_queue_nominal_quota * 100

# Eviction rate (should be low)
rate(kueue_evicted_workloads_total{reason="Preempted"}[1h])
```

### 12.3 Inference Performance Metrics

#### 12.3.1 LLM Serving Latency

| Metric | Target | Good | Critical Threshold |
|--------|--------|------|-------------------|
| Time to First Token (TTFT) P50 | < 100ms | < 200ms | > 500ms |
| TTFT P95 | < 200ms | < 500ms | > 1s |
| TTFT P99 | < 500ms | < 1s | > 2s |
| Inter-Token Latency (ITL) P99 | < 50ms | < 80ms | > 100ms |

**MLPerf Inference v5.1 Requirements:**
- TTFT: < 2 seconds at P99
- ITL: < 80ms at P99

#### 12.3.2 Throughput Benchmarks

| Hardware | Model Size | Target Throughput |
|----------|------------|-------------------|
| H100 SXM5 | Llama 3.1 70B | > 3,000 tokens/s |
| H100 | 13-70B models | > 250 tokens/s |
| A100 NVLink | Llama 3.1 70B | > 1,100 tokens/s |
| H200 | Llama 2-70B | > 30,000 tokens/s |

#### 12.3.3 Error Rates

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Inference error rate | < 0.1% | > 0.5% |
| Timeout rate | < 0.5% | > 2% |
| 5xx error rate | < 0.01% | > 0.1% |
| Queue overflow rate | < 0.1% | > 1% |

### 12.4 Job & Pipeline Metrics

#### 12.4.1 Job Success Rates

| Job Type | Target Success Rate | Alert Threshold |
|----------|---------------------|-----------------|
| SERVICE (deployments) | > 99% | < 95% |
| BATCH (one-time jobs) | > 95% | < 90% |
| TRAINING (long-running) | > 90% | < 85% |

#### 12.4.2 Pipeline Metrics

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| DAG success rate | > 95% | < 90% |
| Step success rate | > 98% | < 95% |
| Step failure rate | < 2% | > 5% |
| Pipeline completion (P95) | < SLA | > 2x SLA |

**Key Metrics to Track:**
```yaml
# Pipeline execution
pipeline_executions_total{status="success|failed"}
pipeline_duration_seconds{pipeline_id, status}

# Step execution
step_executions_total{step_type, status}
step_duration_seconds{step_type, status}

# Job creation from steps
jobs_created_from_steps_total{step_type="job"}
job_wait_time_seconds{source_type="PIPELINE"}
```

#### 12.4.3 Job Lifecycle Metrics

Jobs are the **atomic scheduling unit** - everything deployed on a cluster becomes a Job. These metrics track the full job lifecycle.

**Job State Transitions:**
```
PENDING → QUEUED → ADMITTED → RUNNING → COMPLETED/FAILED
    │         │         │         │
    └─────────┴─────────┴─────────┴──► Can transition to FAILED at any stage
```

| Metric | Description | Target | Alert Threshold |
|--------|-------------|--------|-----------------|
| **Queue Wait Time** | Time from PENDING to ADMITTED | < 2 min (P50), < 10 min (P95) | > 30 min |
| **Admission Rate** | Jobs admitted / Jobs submitted | > 95% | < 85% |
| **Job Start Latency** | Time from ADMITTED to RUNNING | < 30s (SERVICE), < 5 min (BATCH) | > 2x target |
| **Job Duration Accuracy** | Actual / Estimated duration | 0.8 - 1.2x | < 0.5x or > 2x |
| **Resource Utilization** | Actual / Requested resources | > 70% | < 40% |
| **Preemption Rate** | Preempted jobs / Total jobs | < 5% | > 15% |
| **Retry Rate** | Jobs requiring retry / Total jobs | < 3% | > 10% |

**Job Metrics by Type:**

| Job Type | Key Metrics | Target |
|----------|-------------|--------|
| **SERVICE** | Uptime, restart count, health check pass rate | 99.9% uptime, < 3 restarts/day |
| **BATCH** | Completion rate, duration vs estimate, output validation | > 95% success, ±20% duration |
| **TRAINING** | Checkpoint frequency, loss convergence, GPU hours efficiency | Checkpoint every 30 min, < 10% wasted GPU |

**Job Cost Metrics:**

| Metric | Description | Target |
|--------|-------------|--------|
| Estimated vs Actual Cost | Cost accuracy | ±15% |
| Cost per Successful Job | Total cost / Successful jobs | Track trend |
| Wasted Spend | Cost of failed + preempted jobs | < 5% of total |
| GPU Hour Efficiency | Productive GPU time / Total GPU time | > 85% |

**Prometheus Metrics for Jobs:**
```yaml
# Job lifecycle
job_state_transitions_total{job_type, from_state, to_state}
job_queue_wait_seconds{job_type, priority, cluster_queue}
job_duration_seconds{job_type, status, source_type}

# Job resource efficiency
job_resource_requested{job_type, resource="gpu|cpu|memory"}
job_resource_used{job_type, resource="gpu|cpu|memory"}
job_resource_efficiency_ratio{job_type}  # used/requested

# Job cost tracking
job_estimated_cost_dollars{job_type, source_type}
job_actual_cost_dollars{job_type, source_type, status}

# Job failures and retries
job_failures_total{job_type, failure_reason}
job_retries_total{job_type}
job_preemptions_total{job_type, preemption_reason}

# Jobs by source
jobs_total{source_type="DIRECT|PIPELINE|USECASE", job_type, status}
```

**Job SLAs by Source:**

| Source Type | Job Type | Success SLA | Latency SLA |
|-------------|----------|-------------|-------------|
| DIRECT (BudApp) | SERVICE | 99.5% | Start < 2 min |
| DIRECT (BudApp) | BATCH | 95% | Queue < 10 min |
| PIPELINE | SERVICE | 99% | Start < 5 min |
| PIPELINE | BATCH | 95% | Queue < 15 min |
| USECASE | SERVICE | 99% | Full deploy < 10 min |
| USECASE | BATCH | 90% | Queue < 20 min |

#### 12.4.4 Schedule Timeline Metrics

The Schedule Timeline shows Jobs on a resource visualization. These metrics ensure accurate timeline rendering.

| Metric | Description | Target |
|--------|-------------|--------|
| Schedule Accuracy | Jobs starting within estimated window | > 80% |
| Timeline Refresh Latency | Time to update UI after job state change | < 5s |
| Estimation Error (P50) | Actual start - Estimated start | < 5 min |
| Estimation Error (P95) | Actual start - Estimated start | < 30 min |
| Resource Conflict Rate | Jobs delayed due to resource contention | < 10% |

### 12.5 Use Case Metrics

Use Cases are template-based deployments (RAG, Chatbot, Agent) that orchestrate multiple components via Pipelines and Jobs.

#### 12.5.1 Use Case Deployment Metrics

| Metric | Description | Target | Alert Threshold |
|--------|-------------|--------|-----------------|
| **Template Deployment Success** | Successful deployments / Attempts | > 95% | < 85% |
| **Time to First Request** | Deploy start to serving first request | < 15 min | > 30 min |
| **Component Health Rate** | Healthy components / Total components | > 99% | < 95% |
| **Use Case Uptime** | Availability of deployed use case | > 99.5% | < 99% |
| **Rollback Rate** | Deployments requiring rollback | < 5% | > 15% |

**Prometheus Metrics:**
```yaml
# Use case deployment
usecase_deployments_total{template_id, status="success|failed|rollback"}
usecase_deployment_duration_seconds{template_id, status}
usecase_time_to_first_request_seconds{template_id}

# Component health
usecase_components_total{usecase_id, status="healthy|degraded|failed"}
usecase_component_restarts_total{usecase_id, component_type}

# Use case availability
usecase_uptime_ratio{usecase_id, template_id}
```

#### 12.5.2 Use Case Type-Specific Metrics

**RAG (Retrieval-Augmented Generation):**

| Metric | Description | Target |
|--------|-------------|--------|
| Query Latency (E2E) | User query to complete response | P95 < 3s |
| Retrieval Latency | Query to retrieved chunks | P95 < 500ms |
| Retrieval Recall | Relevant chunks retrieved / Total relevant | > 80% |
| Context Relevance Score | LLM-judged relevance of retrieved context | > 0.7 |
| Embedding Throughput | Documents embedded per second | > 100 docs/s |
| Index Freshness | Time since last index update | < 1 hour |
| Hallucination Rate | Responses with unsupported claims | < 5% |

```yaml
# RAG-specific metrics
rag_query_latency_seconds{usecase_id, stage="retrieval|generation|total"}
rag_retrieval_recall_ratio{usecase_id}
rag_context_relevance_score{usecase_id}
rag_chunks_retrieved_total{usecase_id}
rag_index_documents_total{usecase_id}
rag_index_last_updated_timestamp{usecase_id}
```

**Chatbot:**

| Metric | Description | Target |
|--------|-------------|--------|
| Response Latency | User message to bot response | P95 < 2s |
| TTFT (Time to First Token) | Message to first streamed token | P95 < 500ms |
| Conversation Completion Rate | Completed conversations / Started | > 70% |
| User Satisfaction (CSAT) | Post-conversation rating | > 4.0/5.0 |
| Handoff Rate | Conversations escalated to human | < 20% |
| Session Duration | Average conversation length | Track trend |
| Messages per Session | Average messages exchanged | Track trend |

```yaml
# Chatbot-specific metrics
chatbot_response_latency_seconds{usecase_id}
chatbot_ttft_seconds{usecase_id}
chatbot_conversations_total{usecase_id, status="completed|abandoned|escalated"}
chatbot_user_satisfaction_score{usecase_id}
chatbot_messages_total{usecase_id, role="user|assistant"}
```

**Agent (Autonomous AI):**

| Metric | Description | Target |
|--------|-------------|--------|
| Task Completion Rate | Successfully completed tasks / Assigned | > 85% |
| Tool Call Success Rate | Successful tool executions / Attempts | > 95% |
| Planning Accuracy | Correct action sequences / Total plans | > 80% |
| Steps per Task | Average reasoning steps to complete | Track (lower is better) |
| Token Efficiency | Tokens used / Task complexity | Track trend |
| Timeout Rate | Tasks exceeding time limit | < 10% |
| Loop Detection Rate | Tasks caught in reasoning loops | < 5% |
| Human Intervention Rate | Tasks requiring human help | < 15% |

```yaml
# Agent-specific metrics
agent_tasks_total{usecase_id, status="completed|failed|timeout|escalated"}
agent_tool_calls_total{usecase_id, tool_name, status="success|failed"}
agent_reasoning_steps_total{usecase_id, task_id}
agent_tokens_used_total{usecase_id, token_type="input|output"}
agent_task_duration_seconds{usecase_id, status}
agent_loops_detected_total{usecase_id}
```

#### 12.5.3 Use Case Cost Metrics

| Metric | Description | Target |
|--------|-------------|--------|
| Cost per Query (RAG) | Total cost / Queries served | Track, optimize |
| Cost per Conversation (Chatbot) | Total cost / Conversations | Track, optimize |
| Cost per Task (Agent) | Total cost / Tasks completed | Track, optimize |
| Infrastructure Cost Ratio | Infra cost / Total use case cost | < 40% |
| Model Cost Ratio | LLM API cost / Total use case cost | Track trend |

```yaml
# Use case cost tracking
usecase_cost_dollars{usecase_id, template_type, cost_type="compute|model|storage"}
usecase_queries_total{usecase_id}  # For calculating cost per query
usecase_cost_per_unit{usecase_id, unit_type="query|conversation|task"}
```

#### 12.5.4 Use Case Quality Metrics

| Metric | Category | Description | Target |
|--------|----------|-------------|--------|
| Response Quality Score | Quality | LLM-as-judge evaluation | > 0.8 |
| Factual Accuracy | Quality | Correct facts / Total facts | > 95% |
| Toxicity Rate | Safety | Toxic responses / Total | < 0.1% |
| PII Leak Rate | Safety | Responses with leaked PII | 0% |
| Latency SLA Compliance | Performance | Requests within SLA / Total | > 99% |
| Error Rate | Reliability | Failed requests / Total | < 1% |

#### 12.5.5 Use Case Dashboard Summary

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         USE CASE HEALTH DASHBOARD                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │  USE CASE: Enterprise RAG (rag-enterprise-001)                          │   │
│   │  Template: rag-enterprise-v2    Status: ● HEALTHY                       │   │
│   ├─────────────────────────────────────────────────────────────────────────┤   │
│   │                                                                         │   │
│   │  COMPONENTS (4/4 healthy)         JOBS (3 active)                       │   │
│   │  ├── ● Vector DB (Qdrant)         ├── SERVICE: qdrant-001 (RUNNING)    │   │
│   │  ├── ● Embedding Service          ├── SERVICE: embedder-001 (RUNNING)  │   │
│   │  ├── ● LLM Endpoint               └── SERVICE: llm-001 (RUNNING)       │   │
│   │  └── ● Orchestrator                                                     │   │
│   │                                                                         │   │
│   │  PERFORMANCE (Last 24h)           COST (Last 24h)                       │   │
│   │  ├── Queries: 12,450              ├── Compute: $45.20                   │   │
│   │  ├── P95 Latency: 2.3s            ├── Model API: $120.50                │   │
│   │  ├── Success Rate: 99.2%          ├── Storage: $5.00                    │   │
│   │  └── Retrieval Recall: 0.85       └── Total: $170.70 ($0.014/query)    │   │
│   │                                                                         │   │
│   │  QUALITY                          ALERTS                                │   │
│   │  ├── Relevance Score: 0.82        └── None                              │   │
│   │  ├── Hallucination Rate: 2.1%                                           │   │
│   │  └── User Satisfaction: 4.2/5.0                                         │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 12.6 Platform Adoption Metrics

#### 12.6.1 Developer Experience

| Metric | Target | Good | Needs Work |
|--------|--------|------|------------|
| Time to first deployment | < 4 hours | < 1 day | > 1 week |
| Time to first model serving | < 1 hour | < 4 hours | > 1 day |
| Developer NPS | > 40 | > 30 | < 20 |
| Platform adoption rate | > 80% | > 60% | < 40% |

#### 12.6.2 Feature Adoption

| Feature | Target Adoption | Measurement |
|---------|-----------------|-------------|
| Model deployment | > 90% | Users who deployed at least 1 model |
| Use case templates | > 40% | Users who used templates vs manual |
| Pipeline creation | > 30% | Users with at least 1 pipeline |
| GPU scheduling | > 50% | Jobs using priority/quotas |
| BudSim optimization | > 25% | Deployments using recommendations |

#### 12.6.3 Retention Metrics

| Metric | Target | Good | At Risk |
|--------|--------|------|---------|
| 30-day retention | > 85% | > 75% | < 60% |
| 60-day retention | > 75% | > 65% | < 50% |
| 90-day retention | > 70% | > 60% | < 45% |
| Monthly active projects | Increasing | Stable | Declining |

### 12.7 Operational Excellence (DORA + SRE)

#### 12.7.1 DORA Metrics

| Metric | Elite Target | Good | Needs Improvement |
|--------|--------------|------|-------------------|
| Deployment frequency | Multiple/day | Weekly | < Monthly |
| Lead time for changes | < 1 hour | < 1 day | > 1 week |
| Change failure rate | < 5% | < 15% | > 30% |
| Mean time to recovery | < 1 hour | < 4 hours | > 1 day |

#### 12.7.2 Incident Response

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Mean time to detect (MTTD) | < 5 min | > 15 min |
| Mean time to acknowledge (MTTA) | < 5 min | > 15 min |
| Mean time to repair (MTTR) | < 1 hour | > 4 hours |

#### 12.7.3 Error Budget Management

| SLO | Error Budget | Monthly Allowed Downtime |
|-----|-------------|-------------------------|
| 99.99% | 0.01% | 4.32 minutes |
| 99.95% | 0.05% | 21.6 minutes |
| 99.9% | 0.1% | 43.2 minutes |
| 99.5% | 0.5% | 3.65 hours |

**Error Budget Policy:**
- Burn rate < 1.0x: Proceed normally
- Burn rate 1.0x-2.0x: Add reliability task to sprint
- Burn rate 2.0x-10.0x: Pause feature work
- Burn rate > 10.0x: Emergency response

### 12.8 Business Metrics

#### 12.8.1 Unit Economics

| Metric | Target | Benchmark |
|--------|--------|-----------|
| GPU COGS as % of ARR | < 18% | Seed/Series A target |
| Gross margin | > 82% | With efficient utilization |
| LTV:CAC ratio | > 3:1 | Industry standard |
| CAC payback period | < 24 months | 23 months average |

#### 12.8.2 Revenue Retention

| Metric | Elite | Good | At Risk |
|--------|-------|------|---------|
| Net Revenue Retention (NRR) | > 120% | > 105% | < 100% |
| Gross Revenue Retention (GRR) | > 95% | > 90% | < 85% |
| Logo retention (annual) | > 90% | > 85% | < 80% |
| Monthly churn | < 1% | < 3% | > 5% |

#### 12.8.3 Customer Success

| Metric | Target | Benchmark |
|--------|--------|-----------|
| NPS (Net Promoter Score) | > 40 | B2B SaaS average: 41 |
| Customer health score coverage | 100% | All accounts tracked |
| Support ticket resolution | < 4 hours | First response |
| Expansion revenue % | > 30% | Of new ARR |

### 12.9 Metrics by Development Phase

| Phase | Primary Metrics | Secondary Metrics |
|-------|-----------------|-------------------|
| **Phase 1: Job Layer** | Job creation success, Schedule API latency, GPU pool accuracy | Pod deployment time, Metering accuracy |
| **Phase 2: Pipeline Layer** | Pipeline success rate, Step execution time, JOB-step integration | Serverless cold start, Queue wait time |
| **Phase 3: Scheduling** | Kueue admission latency, Fair-share compliance, Quota utilization | Preemption rate, Multi-cluster latency |
| **Phase 4: Use Cases** | Template adoption rate, Component deployment success, Time to RAG | User satisfaction, Feature discovery |
| **Phase 5: Advanced** | Multi-cluster efficiency, Training checkpoint success, P2P utilization | Agent reliability, Marketplace activity |

### 12.10 Monitoring Stack Integration

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         METRICS COLLECTION ARCHITECTURE                          │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   Clusters                    BudMetrics                      Dashboards        │
│   ┌─────────────┐            ┌─────────────┐                 ┌─────────────┐   │
│   │ Prometheus  │───push────►│ ClickHouse  │────────────────►│  Grafana    │   │
│   │ + DCGM      │            │             │                 │             │   │
│   └─────────────┘            │ • GPU metrics│                │ • GPU util  │   │
│                              │ • Job metrics│                │ • Job status│   │
│   ┌─────────────┐            │ • Inference  │                │ • SLA       │   │
│   │   Kueue     │───scrape──►│ • Pipeline   │                │ • Business  │   │
│   │  Metrics    │            │ • Business   │                │             │   │
│   └─────────────┘            └─────────────┘                 └─────────────┘   │
│                                     │                                          │
│   ┌─────────────┐                   │                        ┌─────────────┐   │
│   │ BudGateway  │───────────────────┘                        │   Alerts    │   │
│   │  Metrics    │                                            │  (Grafana)  │   │
│   └─────────────┘                                            └─────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Key Grafana Dashboards to Build:**
1. **GPU Fleet Overview**: Utilization, temperature, memory across clusters
2. **Job & Pipeline Status**: Success rates, queue depths, execution times
3. **Inference Performance**: TTFT, ITL, throughput, error rates
4. **Business Metrics**: Revenue, retention, adoption trends
5. **SLA Compliance**: Error budget burn, uptime tracking

---

## Sources

### GPU Cloud Providers
- [RunPod Serverless](https://www.runpod.io/product/serverless)
- [CoreWeave Platform](https://www.coreweave.com/)
- [Lambda Labs Pricing](https://lambda.ai/pricing)
- [Vast.ai GPU Cloud](https://vast.ai/)
- [Modal Labs](https://modal.com/)

### GPU Scheduling & Management
- [Kubernetes GPU Scheduling 2025](https://debugg.ai/resources/kubernetes-gpu-scheduling-2025-kueue-volcano-mig)
- [NVIDIA Time-Slicing GPUs](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/gpu-sharing.html)
- [NVIDIA Dynamo Autoscaling](https://developer.nvidia.com/blog/nvidia-dynamo-adds-gpu-autoscaling-kubernetes-automation-and-networking-optimizations/)
- [Google LLM Autoscaling Best Practices](https://docs.cloud.google.com/kubernetes-engine/docs/best-practices/machine-learning/inference/autoscaling)

### Cost & Metering
- [OpenCost](https://opencost.io/)
- [Flexprice AI Metering](https://flexprice.io/blog/top-5-real-time-ai-usage-tracking-and-cost-metering-solutions-for-startups)
- [Rafay GPU Cloud Billing](https://rafay.co/ai-and-cloud-native-blog/gpu-neocloud-billing-using-rafays-usage-metering-apis)

### Multi-Cluster & Federation
- [vCluster AI Infrastructure Platform](https://www.vcluster.com/blog/vcluster-ai-platform-nvidia-gpu-kubernetes)
- [Kubernetes Multi-Cluster Federation](https://medium.com/@serverwalainfra/kubernetes-1-30-and-beyond-multi-cluster-federation-and-gpu-aware-scheduling-explained-5a945022e0ee)

### Cold Start Optimization
- [Modal GPU Snapshotting](https://modal.com/blog/mistral-3)
- [Cold Start Optimization Research](https://dl.acm.org/doi/10.1145/3745812.3745825)

### Bare Metal GPU
- [Bare Metal Kubernetes GPUs](https://www.servermania.com/kb/articles/kubernetes-dedicated-gpu-clusters)
- [Rafay BMaaS](https://rafay.co/solutions/rafay-powered-bare-metal-gpus-as-a-service-bmaas)

### Use Case Deployment Platforms
- [TrueFoundry](https://www.truefoundry.com/)
- [Dify.AI 2025 Guide](https://skywork.ai/skypage/en/Dify.AI-The-Ultimate-2025-Guide-to-Building-Production-Ready-AI-Applications/1974389253846265856)
- [Dify Marketplace](https://marketplace.dify.ai/)
- [NVIDIA RAG Blueprint](https://github.com/NVIDIA-AI-Blueprints/rag)
- [Flowise AI](https://flowiseai.com/)
- [LangFlow](https://www.langflow.org/)

### Success Metrics & Benchmarks
- [DORA Metrics](https://dora.dev/guides/dora-metrics/)
- [Kueue Prometheus Metrics Reference](https://kueue.sigs.k8s.io/docs/reference/metrics/)
- [NVIDIA DCGM Exporter](https://github.com/NVIDIA/dcgm-exporter)
- [NVIDIA Data Center Monitoring](https://developer.nvidia.com/blog/making-gpu-clusters-more-efficient-with-nvidia-data-center-monitoring/)
- [RunPod FlashBoot](https://www.runpod.io/blog/introducing-flashboot-serverless-cold-start)
- [Modal GPU Memory Snapshots](https://modal.com/blog/gpu-mem-snapshots)
- [MLPerf Inference v5.1](https://mlcommons.org/2025/09/small-llm-inference-5-1/)
- [NVIDIA TensorRT-LLM Benchmarks](https://developer.nvidia.com/blog/llm-inference-benchmarking-performance-tuning-with-tensorrt-llm/)
- [BentoML LLM Inference Handbook](https://bentoml.com/llm/inference-optimization/llm-inference-metrics)
- [Galileo AI MLOps KPIs](https://galileo.ai/blog/mlops-kpis-measure-prove-roi)
- [Userpilot Feature Adoption Benchmarks](https://userpilot.com/blog/core-feature-adoption-rate-benchmark-report-2024/)
- [CustomerGauge B2B NPS Benchmarks](https://customergauge.com/blog/b2b-nps-benchmarks-tying-revenue-to-your-experience-program)
- [SaaS Capital Retention Benchmarks](https://www.saas-capital.com/research/saas-retention-benchmarks-for-private-b2b-companies/)
- [Google SRE Book - Error Budgets](https://sre.google/sre-book/embracing-risk/)
- [Platform Engineering Metrics](https://platformengineering.org/blog/how-to-measure-developer-productivity-and-platform-roi-a-complete-framework-for-platform-engineers)

---

## Appendix A: Existing Bud Architecture Analysis

### Current Services & Capabilities

| Service | Purpose | Database | GPU-Related Capabilities |
|---------|---------|----------|--------------------------|
| **BudCluster** | Cluster lifecycle | PostgreSQL | NFD detection, HAMI time-slicing, multi-cloud |
| **BudGateway** | API routing | - | High-performance Rust gateway |
| **BudMetrics** | Observability | ClickHouse | DCGM/HAMI metrics collection |
| **BudModel** | Model registry | PostgreSQL | Model metadata, versioning |
| **BudSim** | Performance opt | PostgreSQL | XGBoost + genetic algorithms |
| **BudPipeline** | Workflows | PostgreSQL | DAG execution, event-driven |
| **BudApp** | Main API | PostgreSQL | User/project management |

### Service Extensions Required

| Service | Extension | New Responsibilities |
|---------|-----------|---------------------|
| **BudMetrics** | Metering & Billing | Per-second GPU metering, cost calculation, billing APIs, usage aggregation, budget alerts |
| **BudCluster** | Monitoring Deployment | Deploy Prometheus+DCGM stack during cluster registration, configure remote-write to BudMetrics |

### Key Gaps for GPU-as-a-Service

1. **No GPU inventory/pool tracking** - Current system tracks nodes but not GPU pools
2. **No reservation system** - Can't pre-allocate GPUs across users
3. **Limited cost metering** - Basic metrics collected but no billing integration
4. **No cross-cluster GPU federation** - Single-cluster deployments only
5. **No request prioritization** - FIFO queuing only, no priority classes
6. **Limited vGPU support** - HAMI time-slicing supported but not exposed as pricing tier
7. **No capacity planning APIs** - Can't query available GPU capacity upfront
8. **No pre-warming** - GPUs don't stay warm between requests

---

## Appendix B: Decision Log

| Decision | Options Considered | Decision | Rationale |
|----------|-------------------|----------|-----------|
| Queue System | Redis, Kafka, Custom | Valkey (existing) + BudQueue | Leverage existing infra, add queue logic |
| Metering Storage | PostgreSQL, ClickHouse | ClickHouse | Time-series optimized, already in stack |
| Scheduler | Kueue, Volcano, Custom | **Kueue + MultiKueue** | Kueue covers quotas, admission, fair-share, gang scheduling; MultiKueue adds multi-cluster |
| Scheduler Service | Separate BudScheduler, Merge into BudCompute, Integrate into BudCluster | **Integrate into BudCluster** | Kueue handles all scheduling logic; BudCluster already manages clusters; avoids bottleneck |
| BudCompute | Required, Optional | **Optional** | Basic deployments work without it; only needed for GPU-as-a-Service features |
| Template Format | YAML, JSON, HCL | JSON with Jinja2 | Familiar, IDE support, type-safe |
| Cold Start Opt | CRIU, Modal-style | Phased approach | Start with caching, evolve to snapshots |
| Metrics Architecture | Separate BudMetering, Extend BudMetrics, BudCluster handles all | **Extend BudMetrics** with push-based pattern | See detailed rationale below |
| Component Registry | Hardcoded in code, File-based, Database | **Database (PostgreSQL)** | No code changes to add components; versioning; API-driven management |
| Component Deployment | Helm only, Docker only, Both | **Both Helm + Docker** | Helm for complex charts (DBs), Docker for simple services; BudCluster handles both |
| Template Storage | Files in repo, Database | **Database (PostgreSQL)** | No code changes to add templates; versioning; API-driven; searchable |
| Helm Chart Location | All in BudUseCases, All in BudCluster, Split | **BudCluster owns all Helm execution** | Single deployment engine; external repos for components; internal chart for Docker deploys |
| Scheduling Unit | Pipeline, Step, Job | **Job** | Job is atomic; only JOB-type steps create Jobs; visible on resource timeline; Kueue schedules Jobs |
| Step vs Job | All steps are Jobs, Some steps are Jobs | **Only JOB-type steps create Jobs** | Functional steps (API_CALL, NOTIFICATION) don't need resources; Control steps (CONDITION, WAIT) are flow control |
| Job Management | BudPipeline, BudCluster, New BudJobs | **BudCluster manages Jobs** | BudCluster already handles deployments; Jobs are deployment units; avoids new service |
| Pipeline Management | BudCluster, BudUseCases, BudPipeline | **BudPipeline manages Pipelines** | BudPipeline handles DAGs, triggers, step execution; creates Jobs via BudCluster |

### Metrics Architecture Decision (Detailed)

**Problem:** GPU metering requires collecting metrics from clusters, but creating a separate BudMetering
service would duplicate functionality already in BudMetrics and create credential management complexity.

**Options Considered:**

1. **Separate BudMetering Service**
   - Pros: Clean separation, dedicated service
   - Cons: Duplicates ClickHouse storage, requires cluster credentials, overlaps with BudMetrics

2. **Extend BudCluster with Metering**
   - Pros: Already has cluster access
   - Cons: Wrong responsibility (BudCluster is infrastructure, not observability), couples billing to infra

3. **Extend BudMetrics with Push-Based Pattern** ✅ SELECTED
   - Pros: Natural fit (observability domain), no credential sprawl, industry-standard pattern
   - Cons: Requires BudCluster to deploy monitoring stack

**Selected Approach:** Push-based metrics with BudMetrics extension

```
Clusters push metrics → BudMetrics receives → Stores in ClickHouse → Calculates billing
       ↑                                                                      │
       └── BudCluster deploys Prometheus+DCGM during registration ←───────────┘
                                                                     (Dapr fallback if push fails)
```

**Key Benefits:**
- BudMetrics doesn't need cluster credentials (push vs pull)
- BudCluster stays infrastructure-focused
- Industry-standard pattern (Thanos, Cortex, Grafana Cloud use similar)
- Dapr fallback provides resilience without tight coupling
- Single ClickHouse instance for all metrics + metering

### Scheduler Architecture Decision (Detailed)

**Problem:** GPU scheduling requires quotas, admission control, fair-share, and multi-cluster support.
Creating a separate BudScheduler service adds unnecessary complexity when Kubernetes-native solutions exist.

**Options Considered:**

1. **Separate BudScheduler Service**
   - Pros: Clean separation, custom logic
   - Cons: Duplicates Kueue functionality, adds service layer, requires complex state management

2. **Merge Scheduling into BudCompute**
   - Pros: Single service for GPU management
   - Cons: Makes BudCompute a bottleneck, can't deploy basic workloads without full GPU-as-a-Service

3. **Integrate Kueue into BudCluster** ✅ SELECTED
   - Pros: Kueue is battle-tested, handles all requirements, BudCluster already manages clusters
   - Cons: BudCluster scope expands slightly

**Selected Approach:** Kueue + MultiKueue integrated into BudCluster

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      SCHEDULING ARCHITECTURE                                     │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   BudCluster (Manager)                                                          │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │ • Deploys Kueue during cluster registration                             │   │
│   │ • Creates ClusterQueues for job types (endpoints, serverless, usecases) │   │
│   │ • Creates LocalQueues for tenants                                       │   │
│   │ • Configures Cohorts for fair-share borrowing                           │   │
│   │ • MultiKueue for cross-cluster job distribution                         │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│   Why NOT Volcano?                                                              │
│   • Kueue 0.6+ supports gang scheduling (was the main Volcano advantage)        │
│   • MultiKueue provides multi-cluster (Volcano doesn't)                         │
│   • Better integration with Kubernetes ecosystem                                │
│   • Active CNCF development                                                     │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Key Benefits:**
- No separate scheduler service to maintain
- Kubernetes-native (CRDs, operators, ecosystem compatibility)
- BudCompute remains optional (basic deployments work without it)
- MultiKueue handles cross-cluster scheduling natively
- Fair-share via Cohorts without custom implementation

---

## Appendix C: Open Questions

1. **P2P GPU Marketplace** - Should we pursue this in Phase 5 or focus on enterprise features?
2. **Billing Integration** - Stripe vs. custom billing vs. enterprise invoicing?
3. **Template Marketplace** - Open vs. curated vs. enterprise-only templates?
4. **Multi-Region** - How to handle cross-region GPU allocation and data residency?
5. **GPU Reservations** - Should we support reserved capacity pricing model?

---

*Document maintained by Engineering Team. Last updated: January 30, 2026 (v1.5)*
