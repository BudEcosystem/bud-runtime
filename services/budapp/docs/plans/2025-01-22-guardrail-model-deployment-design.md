# Guardrail Profile Deployment with Model Rules - Design Document

**Date:** 2025-01-22
**Status:** Draft
**Author:** Claude (with user input)

## Overview

Extend the guardrail feature to support model-based rules (classifiers and LLMs) that require model onboarding and deployment to clusters. This enables guardrail profiles to use custom AI models for content moderation, jailbreak detection, and policy enforcement.

## Problem Statement

The current guardrail feature uses probe-based rules from external providers (OpenAI, Azure, AWS, Bud Sentinel). The new feature extends this to support:

1. **Classifier models** (e.g., `katanemo/Arch-Guard`) for threat detection
2. **LLM models** (e.g., `openai/gpt-oss-safeguard-20b`) for policy-based scanning
3. **Custom user-defined rules** using their own onboarded models
4. **Auto-onboarding** of models during deployment if not yet onboarded
5. **Model deployment** to user-selected clusters

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Deploy target | User selects per deployment | Maximum flexibility |
| Notifications | Parent workflow aggregates | Unified progress, suppress child noise |
| Model source for rules | Curated registry + user's onboarded models | System models for standard rules, user models for custom |
| Auto-onboard behavior | Auto-onboard during deployment | Seamless UX, longer deployment time acceptable |
| Cluster config | Global with per-model override | Balance simplicity and flexibility |
| Token/credential indicator | `is_gated` bool + provider type | Simple, sufficient for requirements |
| Deployment linking | New junction table | Clean separation, queryable |
| Model rule discovery | Model rules as single-rule probes | Consistent UX, appears in probe list naturally |
| Custom rules | Users create custom probes | Full flexibility, project-scoped |
| Workflow pattern | BudPipeline | Full progress/ETA, callback_topics, already integrated |

## Data Model Changes

### Extended: GuardrailProbe

```sql
ALTER TABLE guardrail_probe ADD COLUMN probe_type VARCHAR(20) DEFAULT 'provider';
-- Values: 'provider' | 'model_scanner' | 'custom'
```

| probe_type | Description | created_by | Rules |
|------------|-------------|------------|-------|
| `provider` | Traditional probe synced from Bud Connect | null | Multiple pattern-based rules |
| `model_scanner` | System model rule (e.g., Arch-Guard) | null | Single model-based rule |
| `custom` | User-created model rule | user_id | Single model-based rule |

### Extended: GuardrailRule

```sql
ALTER TABLE guardrail_rule ADD COLUMN scanner_type VARCHAR(20);  -- 'classifier' | 'llm'
ALTER TABLE guardrail_rule ADD COLUMN model_uri VARCHAR(255);
ALTER TABLE guardrail_rule ADD COLUMN provider_type VARCHAR(50);  -- ModelProviderTypeEnum
ALTER TABLE guardrail_rule ADD COLUMN is_gated BOOLEAN DEFAULT FALSE;
ALTER TABLE guardrail_rule ADD COLUMN model_config_json JSONB;
ALTER TABLE guardrail_rule ADD COLUMN model_id UUID REFERENCES model(id);
```

**model_config_json examples:**

Classifier:
```json
{
  "head_mappings": [{"head_name": "default", "target_labels": ["JAILBREAK"]}],
  "post_processing": [{"sanitize.label_rename": {"map": {"JAILBREAK": "malicious"}}}]
}
```

LLM:
```json
{
  "handler": "gpt_safeguard",
  "policy": {
    "task": "Classify content for spam indicators",
    "instructions": "Evaluate content...",
    "categories": [
      {"id": "safe", "description": "...", "violation": false},
      {"id": "likely_spam", "description": "...", "violation": true}
    ],
    "examples": [...]
  }
}
```

### New: GuardrailRuleDeployment

```sql
CREATE TABLE guardrail_rule_deployment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    guardrail_deployment_id UUID NOT NULL REFERENCES guardrail_deployment(id) ON DELETE CASCADE,
    rule_id UUID NOT NULL REFERENCES guardrail_rule(id),
    model_id UUID NOT NULL REFERENCES model(id),
    endpoint_id UUID NOT NULL REFERENCES endpoint(id),
    cluster_id UUID NOT NULL REFERENCES cluster(id),
    config_override_json JSONB,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',  -- PENDING | DEPLOYING | READY | FAILED
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    modified_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_guardrail_rule_deployment_deployment ON guardrail_rule_deployment(guardrail_deployment_id);
CREATE INDEX idx_guardrail_rule_deployment_rule ON guardrail_rule_deployment(rule_id);
CREATE INDEX idx_guardrail_rule_deployment_endpoint ON guardrail_rule_deployment(endpoint_id);
```

## API Changes

### New Endpoints

```
POST   /guardrails/custom-probe                   # Create custom model probe + rule
GET    /guardrails/custom-probes                  # List user's custom probes
PUT    /guardrails/custom-probe/{probe_id}        # Update custom probe + rule
DELETE /guardrails/custom-probe/{probe_id}        # Delete custom probe
GET    /guardrails/deployment/{id}/progress       # Get deployment progress
```

### Updated: Deployment Workflow Request

```python
class GuardrailDeploymentWorkflowRequest(BaseModel):
    # Existing fields
    workflow_id: UUID | None = None
    workflow_total_steps: int | None = None
    step_number: int = 1
    trigger_workflow: bool = False
    provider_type: str | None = None
    provider_id: UUID | None = None
    name: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    project_id: UUID | None = None
    endpoint_ids: list[UUID] | None = None
    is_standalone: bool = False
    probe_selections: list[ProbeSelection]
    guard_types: list[str] | None = None
    severity_threshold: float | None = None

    # NEW fields
    cluster_id: UUID | None = None
    deployment_config: DeploymentConfig | None = None
    credential_id: UUID | None = None
    callback_topics: list[str] | None = None

class ProbeSelection(BaseModel):
    probe_id: UUID
    severity_threshold: float | None = None
    guard_types: list[str] | None = None
    rule_overrides: list[RuleOverride] | None = None
    cluster_config_override: DeploymentConfig | None = None  # NEW

class DeploymentConfig(BaseModel):
    concurrent_requests: int = 1
    avg_sequence_length: int = 512
    avg_context_length: int = 4096
    per_session_tokens_per_sec: tuple[int, int] | None = None
    ttft: tuple[int, int] | None = None
    e2e_latency: tuple[int, int] | None = None
```

### Custom Probe Schemas

```python
class ScannerTypeEnum(str, Enum):
    CLASSIFIER = "classifier"
    LLM = "llm"

class GuardrailCustomProbeCreate(BaseModel):
    name: str
    description: str | None = None
    scanner_type: ScannerTypeEnum
    model_id: UUID  # User's onboarded model
    model_config: ClassifierConfig | LLMConfig

class ClassifierConfig(BaseModel):
    head_mappings: list[HeadMapping]
    post_processing: list[dict] | None = None

class HeadMapping(BaseModel):
    head_name: str = "default"
    target_labels: list[str]

class LLMConfig(BaseModel):
    handler: str = "gpt_safeguard"
    policy: PolicyConfig

class PolicyConfig(BaseModel):
    task: str
    instructions: str
    categories: list[CategoryDef]
    examples: list[ExampleDef] | None = None
```

## Workflow Implementation (BudPipeline)

### Pipeline Definition

```json
{
    "name": "guardrail-profile-deployment",
    "version": "1.0",
    "steps": [
        {
            "id": "validate",
            "name": "Validate Deployment Request",
            "type": "guardrail.validate"
        },
        {
            "id": "identify_models",
            "name": "Identify Model Requirements",
            "type": "guardrail.identify_models",
            "depends_on": ["validate"]
        },
        {
            "id": "onboard_models",
            "name": "Onboard Required Models",
            "type": "model.batch_onboard",
            "depends_on": ["identify_models"]
        },
        {
            "id": "deploy_models",
            "name": "Deploy Models to Cluster",
            "type": "model.batch_deploy",
            "depends_on": ["onboard_models"]
        },
        {
            "id": "build_config",
            "name": "Build Guardrail Configuration",
            "type": "guardrail.build_config",
            "depends_on": ["deploy_models"]
        },
        {
            "id": "save_deployment",
            "name": "Save Deployment & Update Cache",
            "type": "guardrail.save_deployment",
            "depends_on": ["build_config"]
        }
    ]
}
```

### New BudPipeline Actions

| Action Type | Service | Description |
|-------------|---------|-------------|
| `guardrail.validate` | budapp | Validate profile, probes, cluster, credentials |
| `guardrail.identify_models` | budapp | Identify which models need onboarding/deployment |
| `guardrail.build_config` | budapp | Build guardrail config JSON with endpoint URLs |
| `guardrail.save_deployment` | budapp | Save deployment records and update Redis cache |
| `model.batch_onboard` | budapp | Onboard multiple models (wraps existing LocalModelWorkflow) |
| `model.batch_deploy` | budapp | Deploy multiple models (wraps existing DeployModelWorkflow) |

### Progress Tracking

BudPipeline provides:
- Per-step events: `STEP_STARTED`, `STEP_COMPLETED`, `STEP_FAILED`
- ETA estimation based on average step duration
- Real-time updates via `callback_topics`
- Queryable event history

Progress response structure:
```json
{
  "execution": {
    "id": "execution-uuid",
    "status": "RUNNING",
    "progress_percentage": 45.50
  },
  "steps": [
    {"id": "validate", "status": "COMPLETED", "progress": 100.0},
    {"id": "identify_models", "status": "COMPLETED", "progress": 100.0},
    {"id": "onboard_models", "status": "RUNNING", "progress": 50.0},
    {"id": "deploy_models", "status": "PENDING", "progress": 0},
    {"id": "build_config", "status": "PENDING", "progress": 0},
    {"id": "save_deployment", "status": "PENDING", "progress": 0}
  ],
  "aggregated_progress": {
    "overall_progress": 45.50,
    "eta_seconds": 180,
    "completed_steps": 2,
    "total_steps": 6,
    "current_step": "Onboard Required Models"
  }
}
```

## Guardrail Config Output

After deployment, Redis `guardrail_table:{profile_id}` contains:

```json
{
    "probe_config": {
        "pii": ["pii.australian.au_abn"],
        "secrets": []
    },
    "endpoint": "http://bud-sentinel-service:50051",
    "api_key_location": "dynamic::store_{profile_id}",
    "custom_rules": [
        {
            "id": "arch_guard_jailbreak",
            "scanner": "latentbud",
            "scanner_config_json": {
                "model_id": "katanemo/Arch-Guard",
                "head_mappings": [{"head_name": "default", "target_labels": ["JAILBREAK"]}]
            }
        },
        {
            "id": "custom_spam_detector",
            "scanner": "llm",
            "scanner_config_json": {
                "model_id": "openai/gpt-oss-safeguard-20b",
                "handler": "gpt_safeguard",
                "handler_config": {"policy": {...}}
            }
        }
    ],
    "metadata_json": {
        "llm": {
            "url": "http://endpoint-{uuid}.namespace.svc:8000/v1",
            "api_key_header": "Authorization",
            "timeout_ms": 30000
        },
        "latentbud": {
            "url": "http://endpoint-{uuid}.namespace.svc:7997",
            "api_key_header": "Authorization",
            "timeout_ms": 30000
        }
    }
}
```

## Error Handling

| Scenario | Handling |
|----------|----------|
| Model onboarding fails | Mark `GuardrailRuleDeployment.status = FAILED`, stop pipeline |
| Model deployment fails | Same - partial deployments kept, profile marked PARTIAL_FAILURE |
| Gated model without credential | Validation step fails: "Model X requires credential_id" |
| Cluster unavailable | Validation step checks cluster status |
| Duplicate deployment | Reuse existing endpoint if model already deployed to cluster |
| Pipeline timeout | BudPipeline handles - mark deployment FAILED |

## Implementation Scope

### Database Migrations
- Add `probe_type` to `guardrail_probe`
- Add model fields to `guardrail_rule`
- Create `guardrail_rule_deployment` table

### budapp Changes
- Extend `guardrails/models.py` with new fields
- Extend `guardrails/schemas.py` with new schemas
- Add custom probe CRUD in `guardrails/crud.py`
- Add custom probe routes in `guardrails/guardrail_routes.py`
- Update deployment workflow in `guardrails/services.py`
- Register BudPipeline actions

### budpipeline Changes
- Register new action types
- Implement action handlers for guardrail operations

### Seeder Updates
- Seed model_scanner probes for curated rules (Arch-Guard, etc.)

## Open Questions

1. Should model deployments be shared across profiles using the same model on the same cluster?
2. How to handle model version updates in existing deployments?
3. Cleanup strategy when guardrail deployment is deleted - delete model deployments too?

## References

- Existing guardrails: `.worktrees/sentinel-v2/services/budapp/budapp/guardrails/`
- Model onboarding: `services/budapp/budapp/model_ops/services.py`
- BudPipeline: `services/budpipeline/`
- BudAIFoundry-SDK: https://github.com/BudEcosystem/BudAIFoundry-SDK
