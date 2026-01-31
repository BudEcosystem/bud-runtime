# Guardrail Deployment Workflow Migration Design

**Date:** 2026-01-28
**Status:** Draft
**Author:** Claude Code

## Overview

This design migrates the guardrail deployment workflow from the legacy Dapr workflow implementation to use BudPipeline for orchestration while preserving the existing workflow structure for frontend compatibility.

### Goals

1. Enable multi-model deployment orchestration (onboarding, simulation, deployment)
2. Support skip logic for already-onboarded/deployed models
3. Provide cluster recommendations that account for cumulative resource usage
4. Maintain frontend compatibility with existing workflow step structure
5. Enable full rollback on cancellation/failure

### Key Architecture

- **Workflow layer** (budapp): Handles UI step coordination, stores step data, triggers pipelines
- **Pipeline layer** (budpipeline): Orchestrates async operations with proper progress tracking
- **Actions** (budpipeline): Registered entry points for guardrail-specific operations

### Design Decisions

| # | Topic | Decision |
|---|-------|----------|
| A | Migration scope | Execute-only (workflow for UI, pipeline for execution) |
| D | Orchestration | BudPipeline |
| D3 | Cluster sim strategy | Hybrid: parallel sim → aggregate → sequential validate |
| E1 | Onboarding timing | Step 5, before cluster recommendations |
| F1 | Integration | Workflow wraps Pipeline |
| G1 | Project selection | Early (Step 2, before probes) |
| H1 | Existing deployments | Auto-reuse |
| I1 | Unhealthy endpoints | Reusable with warning |
| J2 | Rollback | Full (except keep onboarded models) |
| K1 | Notifications | Individual per operation (use existing service notifications) |
| L1 | Actions | Register as proper BudPipeline entry points |

---

## Step Flow

### 12-Step Workflow (Revised Ordering)

```
Step 1: Provider Selection
├── Input: provider_id, provider_type
└── Output: Available probes filtered by provider

Step 2: Project Selection
├── Input: project_id
└── Output: Project context for deployment status checks

Step 3: Probe Selection
├── Input: probe_selections[] with:
│   ├── id (probe_id)
│   ├── severity_threshold (optional override)
│   ├── guard_types (optional override)
│   └── rules[] (optional - if empty, ALL rules enabled)
│       ├── id (rule_id)
│       ├── status: ACTIVE
│       ├── severity_threshold (optional)
│       └── guard_types (optional)
└── Output: Selected probes with enabled rules

Step 4: Model Status Identification
├── Query: For each model-based rule (from enabled rules), check status
├── Output: GuardrailModelStatus[] with endpoint details
└── Skip Logic: If all deployed_running → skip to Step 9

Step 5: Credentials + Onboarding
├── Input: credential_id (single, if any model needs onboarding)
├── PIPELINE: model_onboarding_pipeline
├── Wait: Until all models onboarded
└── Skip: If no models need onboarding

Step 6: Hardware Mode Selection
├── Input: hardware_mode ("dedicated" | "shared")
└── Skip: If all models already deployed

Step 7: Deployment Specifications
├── Input: concurrency, target_ttft, target_latency per model
└── Skip: If all models already deployed

Step 8: Cluster Recommendations
├── PIPELINE: cluster_recommendation_pipeline (D3 hybrid)
├── Output: Clusters that can fit ALL models
└── Skip: If all models already deployed

Step 9: Deployment Type
├── Input: is_standalone
└── Output: Deployment mode

Step 10: Endpoint Selection
├── Input: endpoint_ids[] (if not standalone)
└── Skip: If is_standalone = true

Step 11: Profile Settings
├── Input: name, description, guard_types, severity_threshold
└── Output: Profile configuration

Step 12: Final Deployment
├── PIPELINE: deployment_pipeline
├── Always: Redis sync + create GuardrailDeployment records
└── Conditional: Deploy models only if needed
```

### Rule Selection Logic

- `probe_selections[].rules = null/[]` → All rules of probe enabled
- `probe_selections[].rules = [{id: X}, {id: Y}]` → Only rules X and Y enabled

---

## Model Status Schema

### Status Enum

```python
class ModelDeploymentStatus(str, Enum):
    NOT_ONBOARDED = "not_onboarded"
    ONBOARDED = "onboarded"  # Onboarded but not deployed for this project
    # Deployed statuses (same as EndpointStatusEnum)
    RUNNING = "running"
    UNHEALTHY = "unhealthy"
    DEPLOYING = "deploying"
    PENDING = "pending"
    FAILURE = "failure"
    DELETING = "deleting"
```

### GuardrailModelStatus Schema

```python
class GuardrailModelStatus(BaseModel):
    """Status of a model required by guardrail rules."""

    model_config = ConfigDict(from_attributes=True)

    # Rule identification
    rule_id: UUID4
    rule_name: str
    probe_id: UUID4
    probe_name: str

    # Model info
    model_uri: str
    model_id: UUID4 | None  # None if not onboarded

    # Status
    status: ModelDeploymentStatus

    # Endpoint details (populated when deployed)
    endpoint_id: UUID4 | None = None
    endpoint_name: str | None = None
    endpoint_url: str | None = None
    cluster_id: UUID4 | None = None
    cluster_name: str | None = None

    # Derived flags for UI
    requires_onboarding: bool  # status == NOT_ONBOARDED
    requires_deployment: bool  # NOT_ONBOARDED, ONBOARDED, FAILURE, DELETING
    can_reuse: bool  # RUNNING, UNHEALTHY, DEPLOYING, PENDING
    show_warning: bool = False  # UNHEALTHY
```

### Status Derivation

| Status | Meaning | `can_reuse` | `requires_deployment` |
|--------|---------|-------------|----------------------|
| `not_onboarded` | Model not in registry | ❌ | ✅ |
| `onboarded` | In registry, no endpoint for project | ❌ | ✅ |
| `running` | Endpoint running | ✅ | ❌ |
| `unhealthy` | Endpoint unhealthy (warn) | ✅ | ❌ |
| `deploying` | Endpoint deploying | ✅ | ❌ |
| `pending` | Endpoint pending | ✅ | ❌ |
| `failure` | Endpoint failed | ❌ | ✅ |
| `deleting` | Endpoint being deleted | ❌ | ✅ |

---

## Pipeline DAGs

### Pipeline 1: Model Onboarding (Step 5)

```yaml
name: guardrail-model-onboarding
version: "1.0"
description: Onboard models required by guardrail rules

parameters:
  - name: workflow_id
    type: string
    required: true
  - name: models_to_onboard
    type: json  # [{rule_id, model_uri, model_provider_type}]
    required: true
  - name: credential_id
    type: string
    required: true
  - name: user_id
    type: string
    required: true
  - name: callback_topics
    type: json
    required: false

steps:
  - id: validate_credential
    name: Validate Credential
    action: guardrail.validate_credential
    params:
      credential_id: "{{ params.credential_id }}"

  - id: onboard_models
    name: Onboard Models
    action: guardrail.batch_onboard_models
    depends_on: [validate_credential]
    params:
      models: "{{ params.models_to_onboard }}"
      credential_id: "{{ params.credential_id }}"
      user_id: "{{ params.user_id }}"
      callback_topics: "{{ params.callback_topics }}"

  - id: update_rules
    name: Update Rule Model IDs
    action: guardrail.update_rule_model_ids
    depends_on: [onboard_models]
    params:
      onboard_results: "{{ steps.onboard_models.outputs.results }}"

outputs:
  onboarded_models: "{{ steps.onboard_models.outputs.results }}"
  all_succeeded: "{{ steps.update_rules.outputs.success }}"
```

### Pipeline 2: Cluster Recommendations (Step 8) - D3 Hybrid

```yaml
name: guardrail-cluster-recommendation
version: "1.0"
description: Get cluster recommendations for multi-model deployment

parameters:
  - name: workflow_id
    type: string
    required: true
  - name: models
    type: json  # [{model_id, model_uri, deployment_config}]
    required: true
  - name: hardware_mode
    type: string  # "dedicated" | "shared"
    required: true
  - name: callback_topics
    type: json
    required: false

steps:
  - id: parallel_simulate
    name: Run Parallel Simulations
    action: guardrail.parallel_simulate
    params:
      models: "{{ params.models }}"
      hardware_mode: "{{ params.hardware_mode }}"
      callback_topics: "{{ params.callback_topics }}"

  - id: aggregate_requirements
    name: Aggregate Resource Requirements
    action: guardrail.aggregate_requirements
    depends_on: [parallel_simulate]
    params:
      simulation_results: "{{ steps.parallel_simulate.outputs.results }}"

  - id: validate_cluster_fit
    name: Validate Cluster Fit
    action: guardrail.validate_cluster_fit
    depends_on: [aggregate_requirements]
    params:
      candidate_clusters: "{{ steps.aggregate_requirements.outputs.candidate_clusters }}"
      total_requirements: "{{ steps.aggregate_requirements.outputs.total_requirements }}"
      models: "{{ params.models }}"

outputs:
  recommended_clusters: "{{ steps.validate_cluster_fit.outputs.valid_clusters }}"
  per_model_configs: "{{ steps.validate_cluster_fit.outputs.per_model_configs }}"
```

### Pipeline 3: Final Deployment (Step 12)

```yaml
name: guardrail-deployment
version: "1.0"
description: Deploy guardrail models and configure profile

parameters:
  - name: workflow_id
    type: string
    required: true
  - name: profile_config
    type: json  # {name, description, guard_types, severity_threshold}
    required: true
  - name: project_id
    type: string
    required: true
  - name: endpoint_ids
    type: json  # Target endpoints (null if standalone)
    required: false
  - name: is_standalone
    type: boolean
    required: true
  - name: models_to_deploy
    type: json  # [{rule_id, model_id, cluster_id, deployment_config}]
    required: true
  - name: models_to_reuse
    type: json  # [{rule_id, model_id, endpoint_id}]
    required: true
  - name: probe_selections
    type: json
    required: true
  - name: user_id
    type: string
    required: true
  - name: callback_topics
    type: json
    required: false

steps:
  - id: deploy_models
    name: Deploy Models
    action: guardrail.deploy_models
    params:
      models: "{{ params.models_to_deploy }}"
      user_id: "{{ params.user_id }}"
      project_id: "{{ params.project_id }}"
      callback_topics: "{{ params.callback_topics }}"

  - id: create_profile
    name: Create Guardrail Profile
    action: guardrail.create_profile
    depends_on: [deploy_models]
    params:
      config: "{{ params.profile_config }}"
      project_id: "{{ params.project_id }}"
      probe_selections: "{{ params.probe_selections }}"
      user_id: "{{ params.user_id }}"

  - id: create_deployment
    name: Create Guardrail Deployment
    action: guardrail.create_deployment
    depends_on: [create_profile]
    params:
      profile_id: "{{ steps.create_profile.outputs.profile_id }}"
      project_id: "{{ params.project_id }}"
      endpoint_ids: "{{ params.endpoint_ids }}"
      is_standalone: "{{ params.is_standalone }}"
      deployed_models: "{{ steps.deploy_models.outputs.results }}"
      reused_models: "{{ params.models_to_reuse }}"
      user_id: "{{ params.user_id }}"

  - id: build_config
    name: Build Guardrail Config
    action: guardrail.build_config
    depends_on: [create_deployment]
    params:
      deployment_id: "{{ steps.create_deployment.outputs.deployment_id }}"
      profile_id: "{{ steps.create_profile.outputs.profile_id }}"

  - id: sync_redis
    name: Sync to Redis
    action: guardrail.sync_redis
    depends_on: [build_config]
    params:
      profile_id: "{{ steps.create_profile.outputs.profile_id }}"
      config: "{{ steps.build_config.outputs.config }}"

outputs:
  profile_id: "{{ steps.create_profile.outputs.profile_id }}"
  deployment_id: "{{ steps.create_deployment.outputs.deployment_id }}"
  endpoint_urls: "{{ steps.deploy_models.outputs.endpoint_urls }}"
```

---

## BudPipeline Actions

### New Actions to Register

| Action Type | Mode | Purpose |
|-------------|------|---------|
| `guardrail.validate_credential` | SYNC | Validate credential exists and is accessible |
| `guardrail.batch_onboard_models` | EVENT_DRIVEN | Onboard multiple models, wait for completion |
| `guardrail.update_rule_model_ids` | SYNC | Update GuardrailRule.model_id after onboarding |
| `guardrail.parallel_simulate` | EVENT_DRIVEN | Run budsim for each model in parallel |
| `guardrail.aggregate_requirements` | SYNC | Sum resource requirements, find candidate clusters |
| `guardrail.validate_cluster_fit` | SYNC | Sequential validation that cluster fits all models |
| `guardrail.deploy_models` | EVENT_DRIVEN | Deploy models to cluster, wait for completion |
| `guardrail.create_profile` | SYNC | Create GuardrailProfile with probe selections |
| `guardrail.create_deployment` | SYNC | Create GuardrailDeployment + GuardrailRuleDeployment records |
| `guardrail.build_config` | SYNC | Build guardrail config structure |
| `guardrail.sync_redis` | SYNC | Write config to Redis |
| `guardrail.rollback` | SYNC | Rollback on failure (delete deployments, clean Redis) |

### Entry Points Registration

```toml
# budpipeline/pyproject.toml

[project.entry-points."budpipeline.actions"]
# Guardrail actions
guardrail_validate_credential = "budpipeline.actions.guardrail.validate_credential:ValidateCredentialAction"
guardrail_batch_onboard = "budpipeline.actions.guardrail.batch_onboard:BatchOnboardAction"
guardrail_update_rule_model_ids = "budpipeline.actions.guardrail.update_rules:UpdateRuleModelIdsAction"
guardrail_parallel_simulate = "budpipeline.actions.guardrail.parallel_simulate:ParallelSimulateAction"
guardrail_aggregate_requirements = "budpipeline.actions.guardrail.aggregate_requirements:AggregateRequirementsAction"
guardrail_validate_cluster_fit = "budpipeline.actions.guardrail.validate_cluster_fit:ValidateClusterFitAction"
guardrail_deploy_models = "budpipeline.actions.guardrail.deploy_models:DeployModelsAction"
guardrail_create_profile = "budpipeline.actions.guardrail.create_profile:CreateProfileAction"
guardrail_create_deployment = "budpipeline.actions.guardrail.create_deployment:CreateDeploymentAction"
guardrail_build_config = "budpipeline.actions.guardrail.build_config:BuildConfigAction"
guardrail_sync_redis = "budpipeline.actions.guardrail.sync_redis:SyncRedisAction"
guardrail_rollback = "budpipeline.actions.guardrail.rollback:RollbackAction"
```

### Action File Structure

```
budpipeline/actions/guardrail/
├── __init__.py
├── validate_credential.py
├── batch_onboard.py
├── update_rules.py
├── parallel_simulate.py
├── aggregate_requirements.py
├── validate_cluster_fit.py
├── deploy_models.py
├── create_profile.py
├── create_deployment.py
├── build_config.py
├── sync_redis.py
└── rollback.py
```

---

## Rollback Handling

### Rollback Scope per Pipeline

**Pipeline 1 (Model Onboarding):**
| Component | Action | Reason |
|-----------|--------|--------|
| Onboarded models | ❌ Keep | Reusable for other deployments |
| Updated `GuardrailRule.model_id` | ❌ Keep | Model is onboarded regardless |
| Workflow record | Mark CANCELLED/FAILED | Audit trail |

**Pipeline 2 (Cluster Recommendation):**
| Component | Action | Reason |
|-----------|--------|--------|
| Simulation results | ❌ Keep | Cached in budsim, no side effects |
| Workflow record | Mark CANCELLED/FAILED | Audit trail |

**Pipeline 3 (Final Deployment):**
| Component | Action | Reason |
|-----------|--------|--------|
| Deployed model endpoints | ✅ Delete | Created for this workflow |
| GuardrailProfile | ✅ Delete | Incomplete profile |
| GuardrailDeployment | ✅ Delete | Incomplete deployment |
| GuardrailRuleDeployment records | ✅ Cascade delete | Linked to deployment |
| Redis config entry | ✅ Clean | Partial/invalid config |
| Workflow record | Mark CANCELLED/FAILED | Audit trail |

### Pipeline Error Handling

```yaml
# Added to Pipeline 3: Final Deployment
settings:
  on_failure: "rollback"

steps:
  # ... existing steps ...

  - id: rollback
    name: Rollback on Failure
    action: guardrail.rollback
    condition: "{{ execution.status == 'FAILED' }}"
    params:
      workflow_id: "{{ params.workflow_id }}"
      profile_id: "{{ steps.create_profile.outputs.profile_id | default(none) }}"
      deployment_id: "{{ steps.create_deployment.outputs.deployment_id | default(none) }}"
      deployed_endpoint_ids: "{{ steps.deploy_models.outputs.endpoint_ids | default([]) }}"
      reason: "{{ execution.error_message }}"
```

---

## Workflow Service Integration

### Pattern: Workflow wraps Pipeline (F1)

The existing `GuardrailDeploymentWorkflowService` coordinates UI steps and triggers pipelines at execution points.

### Schema Extensions

**Add to `RetrieveWorkflowStepData` (workflow_ops/schemas.py):**

```python
class RetrieveWorkflowStepData(BaseModel):
    # ... existing fields ...

    # NEW: Model status fields (Step 4)
    model_statuses: list[dict] | None = None
    models_requiring_onboarding: int | None = None
    models_requiring_deployment: int | None = None
    models_reusable: int | None = None

    # NEW: Skip logic
    skip_to_step: int | None = None
    credential_required: bool | None = None

    # NEW: Pipeline execution tracking
    pipeline_execution_id: UUID4 | None = None
    pipeline_status: str | None = None
    pipeline_results: dict | None = None

    # NEW: Cluster recommendation results
    recommended_clusters: list[dict] | None = None
    per_model_configs: list[dict] | None = None

    # NEW: Models categorization for deployment
    models_to_deploy: list[dict] | None = None
    models_to_reuse: list[dict] | None = None

    # NEW: Deployment results
    deployment_id: UUID4 | None = None
    deployed_endpoint_ids: list[UUID4] | None = None
```

### Frontend Integration

Frontend retrieves step data via existing endpoint:
```
GET /workflows/{workflow_id}
```

Returns `RetrieveWorkflowDataResponse` with all step data including:
- `model_statuses` (Step 4)
- `pipeline_execution_id`, `pipeline_status` (Steps 5, 8, 12)
- `skip_to_step` (skip logic hints)
- `recommended_clusters` (Step 8 results)

Frontend polls pipeline progress via:
```
GET /budpipeline/executions/{pipeline_execution_id}/progress
```

---

## Notifications

### Approach: Use Existing Service Notifications

| Pipeline Step | Notification Source | What User Sees |
|---------------|--------------------|--------------------|
| Model onboarding | Model service | "Model X onboarded" |
| Cluster simulation | BudSim service | "Simulation complete" |
| Model deployment | BudCluster service | "Endpoint deployed" |

No additional guardrail-specific notifications needed. Individual service notifications provide sufficient visibility.

---

## Implementation Checklist

### Phase 1: Schema & Models
- [ ] Add `ModelDeploymentStatus` enum to guardrails/schemas.py
- [ ] Add `GuardrailModelStatus` schema to guardrails/schemas.py
- [ ] Extend `RetrieveWorkflowStepData` with new fields

### Phase 2: BudPipeline Actions
- [ ] Create `budpipeline/actions/guardrail/` directory
- [ ] Implement all 12 guardrail actions
- [ ] Register entry points in pyproject.toml
- [ ] Add unit tests for each action

### Phase 3: Pipeline DAGs
- [ ] Create `guardrail-model-onboarding` pipeline definition
- [ ] Create `guardrail-cluster-recommendation` pipeline definition
- [ ] Create `guardrail-deployment` pipeline definition
- [ ] Test pipeline execution end-to-end

### Phase 4: Workflow Service
- [ ] Refactor `GuardrailDeploymentWorkflowService` with new step handlers
- [ ] Implement skip logic in step handlers
- [ ] Implement pipeline triggering and result handling
- [ ] Implement cancellation with rollback

### Phase 5: Testing
- [ ] Unit tests for model status derivation
- [ ] Integration tests for each pipeline
- [ ] End-to-end workflow tests
- [ ] Rollback scenario tests

---

## Additional Decisions

### Partial Success Handling

Partial success in batch operations is treated as **failure**:
- If 2/3 models onboard successfully but 1 fails → entire step fails
- Rollback is triggered for the current pipeline
- Users are notified of the failure via existing service notifications
- User must restart the workflow after resolving the issue

### No Retry Mechanism

Individual operation retry is not implemented:
- Existing service notifications inform users of failures
- Users can restart the workflow to retry
- Keeps the workflow logic simple and predictable
