# Custom Probe Workflow Design

**Date:** 2026-02-05
**Status:** Approved
**Service:** budapp (guardrails module)

## Overview

Create a new **multi-step workflow** for custom probes similar to the guardrail deployment workflow. This follows a **probe-first pattern** where the probe is created with `model_uri` only, and `model_id` gets assigned later during deployment (or immediately if model is already onboarded).

## Workflow Steps

```
┌─────────────────────────────────────────────────────────────────┐
│              CUSTOM PROBE WORKFLOW (3 Steps)                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  STEP 1: SELECT PROBE TYPE                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Input:                                                  │   │
│  │   • probe_type_option: "llm_policy"                     │   │
│  │   • project_id: UUID                                    │   │
│  │                                                         │   │
│  │ System auto-sets:                                       │   │
│  │   • model_uri = "openai/gpt-oss-safeguard-20b"         │   │
│  │   • provider_type = "bud"                               │   │
│  │   • scanner_type = "llm"                                │   │
│  │   • handler = "gpt_safeguard"                           │   │
│  └─────────────────────────────────────────────────────────┘   │
│                            ↓                                    │
│  STEP 2: CONFIGURE POLICY                                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Input:                                                  │   │
│  │   • policy: PolicyConfig (task, definitions,            │   │
│  │     violations, safe_content, etc.)                     │   │
│  │                                                         │   │
│  │ System wraps in LLMConfig with handler                  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                            ↓                                    │
│  STEP 3: PROBE METADATA + TRIGGER                               │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Input:                                                  │   │
│  │   • name: str                                           │   │
│  │   • description: str | None                             │   │
│  │   • guard_types: ["input", "output"]                    │   │
│  │   • modality_types: ["text"]                            │   │
│  │   • trigger_workflow: true                              │   │
│  │                                                         │   │
│  │ On trigger_workflow=true:                               │   │
│  │   • Check if model exists by URI → assign model_id      │   │
│  │   • Create Probe + Rule                                 │   │
│  │   • Return workflow complete                            │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  RESULT: Probe + Rule created with model_uri                   │
│  • model_id assigned if model exists, else None                │
│  • model_id assigned during deployment workflow if not set     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Key Design Decisions

### 1. model_id Assignment Strategy

- **At probe creation (Step 3):** Check if model exists by URI → assign `model_id` if found, else `None`
- **At deployment:** Existing guardrail deployment flow handles URI lookup if `model_id` is null
- **model_id on rule is kept** as a cached lookup optimization

### 2. Probe Type Configuration Mapping

| probe_type_option | model_uri | scanner_type | handler | provider_type |
|-------------------|-----------|--------------|---------|---------------|
| `llm_policy` | `openai/gpt-oss-safeguard-20b` | `llm` | `gpt_safeguard` | `bud` |
| *(future)* `classifier` | TBD | `classifier` | TBD | `bud` |

### 3. Workflow Pattern

Follows the same pattern as `GuardrailDeploymentWorkflowRequest`:
- `workflow_id` - existing workflow UUID (to continue)
- `workflow_total_steps` - total steps for new workflow (3)
- `step_number` - current step being processed
- `trigger_workflow` - when true at step 3, creates the probe

## Schema Changes

### New Enum: `CustomProbeTypeEnum`

```python
# File: budapp/guardrails/schemas.py

class CustomProbeTypeEnum(str, Enum):
    """Available custom probe type options."""
    LLM_POLICY = "llm_policy"
    # Future extensions:
    # CLASSIFIER = "classifier"
    # REGEX = "regex"
```

### New Schema: `CustomProbeWorkflowRequest`

```python
# File: budapp/guardrails/schemas.py

class CustomProbeWorkflowRequest(BaseModel):
    """Custom probe workflow request schema (multi-step).

    Similar to GuardrailDeploymentWorkflowRequest but for creating custom probes.
    """

    # Workflow management
    workflow_id: UUID4 | None = None
    workflow_total_steps: int | None = None  # Should be 3 for new workflows
    step_number: int = Field(..., gt=0)
    trigger_workflow: bool = False

    # Step 1: Probe type selection
    probe_type_option: CustomProbeTypeEnum | None = None
    project_id: UUID4 | None = None

    # Step 2: Policy configuration
    policy: PolicyConfig | None = None

    # Step 3: Probe metadata
    name: str | None = None
    description: str | None = None
    guard_types: list[str] | None = None
    modality_types: list[str] | None = None

    @model_validator(mode="after")
    def validate_fields(self) -> "CustomProbeWorkflowRequest":
        """Validate workflow request fields."""
        if self.workflow_id is None and self.workflow_total_steps is None:
            raise ValueError("workflow_total_steps is required when workflow_id is not provided")

        if self.workflow_id is not None and self.workflow_total_steps is not None:
            raise ValueError("workflow_total_steps and workflow_id cannot be provided together")

        return self
```

### New Schema: `CustomProbeWorkflowSteps`

```python
# File: budapp/guardrails/schemas.py

class CustomProbeWorkflowSteps(BaseModel):
    """Custom probe workflow step data schema.

    Tracks accumulated data across workflow steps.
    """

    # Step 1 data
    probe_type_option: CustomProbeTypeEnum | None = None
    project_id: UUID4 | None = None
    # Auto-derived from probe_type_option
    model_uri: str | None = None
    scanner_type: str | None = None
    handler: str | None = None
    model_provider_type: str | None = None

    # Step 2 data
    policy: dict | None = None  # PolicyConfig as dict

    # Step 3 data
    name: str | None = None
    description: str | None = None
    guard_types: list[str] | None = None
    modality_types: list[str] | None = None

    # Result data (after trigger_workflow)
    probe_id: UUID4 | None = None
    model_id: UUID4 | None = None  # Assigned if model exists
    workflow_execution_status: dict | None = None
```

### Update: `GuardrailCustomProbeResponse`

Add `guard_types` and `modality_types` to the response:

```python
# File: budapp/guardrails/schemas.py

class GuardrailCustomProbeResponse(BaseModel):
    """Response schema for custom probe."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID4
    name: str
    description: str | None = None
    probe_type: ProbeTypeEnum
    scanner_type: ScannerTypeEnum | None = None
    model_id: UUID4 | None = None
    model_uri: str | None = None
    model_config_json: dict | None = None
    guard_types: list[str] | None = None        # NEW
    modality_types: list[str] | None = None     # NEW
    status: str
    created_at: datetime
    modified_at: datetime

    @model_validator(mode="before")
    @classmethod
    def extract_rule_data(cls, data: Any) -> Any:
        """Extract rule data from the probe's rules relationship for custom probes."""
        if isinstance(data, dict):
            return data

        if hasattr(data, "rules") and data.rules:
            rule = data.rules[0]
            return {
                "id": data.id,
                "name": data.name,
                "description": data.description,
                "probe_type": data.probe_type,
                "scanner_type": getattr(rule, "scanner_type", None),
                "model_id": getattr(rule, "model_id", None),
                "model_uri": getattr(rule, "model_uri", None),
                "model_config_json": getattr(rule, "model_config_json", None),
                "guard_types": getattr(rule, "guard_types", None),        # NEW
                "modality_types": getattr(rule, "modality_types", None),  # NEW
                "status": data.status,
                "created_at": data.created_at,
                "modified_at": data.modified_at,
            }

        return data
```

## CRUD Changes

### Update: `create_custom_probe_with_rule`

```python
# File: budapp/guardrails/crud.py

async def create_custom_probe_with_rule(
    self,
    name: str,
    description: str | None,
    scanner_type: str,
    model_id: UUID | None,              # Changed: now optional
    model_config: dict,
    model_uri: str,
    model_provider_type: str,
    is_gated: bool,
    project_id: UUID,
    user_id: UUID,
    provider_id: UUID,
    guard_types: list[str] | None = None,      # NEW
    modality_types: list[str] | None = None,   # NEW
) -> GuardrailProbe:
    """Create a custom probe with a single model-based rule atomically."""
    # ... existing code ...

    # Create single rule for the probe
    rule = GuardrailRule(
        probe_id=probe.id,
        name=name,
        uri=f"{probe_uri}.rule",
        description=description,
        scanner_type=scanner_type,
        model_uri=model_uri,
        model_provider_type=model_provider_type,
        is_gated=is_gated,
        model_config_json=model_config,
        model_id=model_id,              # Can be None
        guard_types=guard_types,        # NEW
        modality_types=modality_types,  # NEW
        created_by=user_id,
        status=GuardrailStatusEnum.ACTIVE,
    )
    # ... rest of existing code ...
```

## Service Changes

### Configuration Constants

```python
# File: budapp/guardrails/services.py (at module level)

from dataclasses import dataclass

@dataclass
class ProbeTypeConfig:
    """Configuration for a custom probe type."""
    model_uri: str
    scanner_type: str
    handler: str
    model_provider_type: str


PROBE_TYPE_CONFIGS: dict[str, ProbeTypeConfig] = {
    "llm_policy": ProbeTypeConfig(
        model_uri="openai/gpt-oss-safeguard-20b",
        scanner_type="llm",
        handler="gpt_safeguard",
        model_provider_type="openai",
    ),
}
```

### New Service Method: `add_custom_probe_workflow`

```python
# File: budapp/guardrails/services.py (in GuardrailCustomProbeService class)

async def add_custom_probe_workflow(
    self,
    current_user_id: UUID,
    request: CustomProbeWorkflowRequest,
) -> WorkflowModel:
    """Add custom probe workflow (multi-step).

    Similar to add_guardrail_deployment_workflow but for creating custom probes.

    Step 1: Select probe type → auto-derive model_uri, scanner_type, etc.
    Step 2: Configure policy
    Step 3: Probe metadata + trigger_workflow → create probe
    """
    from budapp.commons.constants import ModelStatusEnum
    from budapp.model_ops.crud import ModelDataManager
    from budapp.model_ops.models import Model
    from budapp.workflow_ops.crud import WorkflowDataManager, WorkflowStepDataManager
    from budapp.workflow_ops.models import Workflow as WorkflowModel
    from budapp.workflow_ops.schemas import WorkflowUtilCreate

    step_number = request.step_number
    workflow_id = request.workflow_id
    workflow_total_steps = request.workflow_total_steps
    trigger_workflow = request.trigger_workflow

    current_step_number = step_number

    # Retrieve or create workflow
    workflow_create = WorkflowUtilCreate(
        workflow_type=WorkflowTypeEnum.CLOUD_MODEL_ONBOARDING,  # Reuse existing type
        title="Custom Probe Creation",
        total_steps=workflow_total_steps,
        icon=APP_ICONS["general"]["deployment_mono"],
    )

    db_workflow, db_workflow_step = await WorkflowService(
        self.session
    ).get_or_create_workflow_with_step(
        workflow_id=workflow_id,
        workflow_create=workflow_create,
        current_user_id=current_user_id,
        step_number=current_step_number,
    )

    # Get existing step data
    workflow_step_data = db_workflow_step.data or {}

    # Process step data based on step_number
    if step_number == 1:
        # Step 1: Probe type selection
        if request.probe_type_option:
            config = PROBE_TYPE_CONFIGS.get(request.probe_type_option.value)
            if config:
                workflow_step_data["probe_type_option"] = request.probe_type_option.value
                workflow_step_data["model_uri"] = config.model_uri
                workflow_step_data["scanner_type"] = config.scanner_type
                workflow_step_data["handler"] = config.handler
                workflow_step_data["model_provider_type"] = config.model_provider_type
        if request.project_id:
            workflow_step_data["project_id"] = str(request.project_id)

    elif step_number == 2:
        # Step 2: Policy configuration
        if request.policy:
            workflow_step_data["policy"] = request.policy.model_dump()

    elif step_number == 3:
        # Step 3: Probe metadata
        if request.name:
            workflow_step_data["name"] = request.name
        if request.description:
            workflow_step_data["description"] = request.description
        if request.guard_types:
            workflow_step_data["guard_types"] = request.guard_types
        if request.modality_types:
            workflow_step_data["modality_types"] = request.modality_types

    # Update workflow step data
    await WorkflowStepDataManager(self.session).update_by_fields(
        db_workflow_step, {"data": workflow_step_data}
    )

    # Execute workflow if triggered at step 3
    if trigger_workflow and step_number == 3:
        await self._execute_custom_probe_workflow(
            workflow_step_data, db_workflow.id, current_user_id
        )

    return db_workflow


async def _execute_custom_probe_workflow(
    self,
    data: dict,
    workflow_id: UUID,
    current_user_id: UUID,
) -> None:
    """Execute custom probe workflow - create the probe."""
    from budapp.commons.constants import ModelStatusEnum
    from budapp.model_ops.crud import ModelDataManager
    from budapp.model_ops.models import Model
    from budapp.workflow_ops.crud import WorkflowDataManager, WorkflowStepDataManager

    db_workflow = await WorkflowDataManager(self.session).retrieve_by_fields(
        WorkflowModel, {"id": workflow_id}
    )
    db_workflow_steps = await WorkflowStepDataManager(self.session).get_all_workflow_steps(
        {"workflow_id": workflow_id}
    )
    db_latest_workflow_step = db_workflow_steps[-1]

    execution_status_data = {
        "workflow_execution_status": {
            "status": "success",
            "message": "Custom probe created successfully",
        },
        "probe_id": None,
    }

    try:
        # Check if model exists
        model_id = None
        model_uri = data.get("model_uri")
        if model_uri:
            model_data_manager = ModelDataManager(self.session)
            existing_model = await model_data_manager.retrieve_by_fields(
                Model,
                {"uri": model_uri, "status": ModelStatusEnum.ACTIVE},
                missing_ok=True,
            )
            if existing_model:
                model_id = existing_model.id

        # Get BudSentinel provider
        provider = await ProviderDataManager(self.session).retrieve_by_fields(
            Provider, {"type": "bud_sentinel"}
        )
        if not provider:
            raise ClientException(
                message="BudSentinel provider not found",
                status_code=HTTPStatus.HTTP_404_NOT_FOUND,
            )

        # Build model config
        model_config = LLMConfig(
            handler=data.get("handler", "gpt_safeguard"),
            policy=PolicyConfig(**data["policy"]),
        ).model_dump()

        # Create probe
        probe = await GuardrailsDeploymentDataManager(self.session).create_custom_probe_with_rule(
            name=data["name"],
            description=data.get("description"),
            scanner_type=data["scanner_type"],
            model_id=model_id,
            model_config=model_config,
            model_uri=model_uri,
            model_provider_type=data.get("model_provider_type", "openai"),
            is_gated=False,
            project_id=UUID(data["project_id"]),
            user_id=current_user_id,
            provider_id=provider.id,
            guard_types=data.get("guard_types"),
            modality_types=data.get("modality_types"),
        )

        execution_status_data["probe_id"] = str(probe.id)
        execution_status_data["model_id"] = str(model_id) if model_id else None

        # Mark workflow completed
        await WorkflowDataManager(self.session).update_by_fields(
            db_workflow, {"status": WorkflowStatusEnum.COMPLETED}
        )

    except Exception as e:
        logger.exception(f"Failed to create custom probe: {e}")
        execution_status_data["workflow_execution_status"] = {
            "status": "error",
            "message": str(e),
        }
        await WorkflowDataManager(self.session).update_by_fields(
            db_workflow, {"status": WorkflowStatusEnum.FAILED, "reason": str(e)}
        )

    # Update step data with execution status
    await WorkflowStepDataManager(self.session).update_by_fields(
        db_latest_workflow_step, {"data": {**data, **execution_status_data}}
    )
```

## Route Changes

### New Endpoint: `POST /guardrails/custom-probe-workflow`

```python
# File: budapp/guardrails/guardrail_routes.py

@router.post(
    "/custom-probe-workflow",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Invalid request",
        },
        status.HTTP_200_OK: {
            "model": RetrieveWorkflowDataResponse,
            "description": "Workflow step processed successfully",
        },
    },
    description="Create custom probe via multi-step workflow",
)
@require_permissions(permissions=[PermissionEnum.MODEL_MANAGE])
async def add_custom_probe_workflow(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    request: CustomProbeWorkflowRequest,
) -> Union[RetrieveWorkflowDataResponse, ErrorResponse]:
    """Add custom probe workflow.

    Multi-step workflow for creating custom probes:
    - Step 1: Select probe type (llm_policy, etc.)
    - Step 2: Configure policy
    - Step 3: Probe metadata + trigger_workflow=true creates probe
    """
    try:
        from budapp.guardrails.services import GuardrailCustomProbeService

        db_workflow = await GuardrailCustomProbeService(session).add_custom_probe_workflow(
            current_user_id=current_user.id,
            request=request,
        )

        return await WorkflowService(session).retrieve_workflow_data(db_workflow.id)
    except ClientException as e:
        logger.exception(f"Failed to add custom probe workflow: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to add custom probe workflow: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to add custom probe workflow",
        ).to_http_response()
```

## Files to Modify

| File | Changes |
|------|---------|
| `budapp/guardrails/schemas.py` | Add `CustomProbeTypeEnum`, `CustomProbeWorkflowRequest`, `CustomProbeWorkflowSteps`, update `GuardrailCustomProbeResponse` |
| `budapp/guardrails/services.py` | Add `PROBE_TYPE_CONFIGS`, `ProbeTypeConfig`, `add_custom_probe_workflow`, `_execute_custom_probe_workflow` |
| `budapp/guardrails/crud.py` | Update `create_custom_probe_with_rule` to accept `guard_types`, `modality_types`, optional `model_id` |
| `budapp/guardrails/guardrail_routes.py` | Add `POST /guardrails/custom-probe-workflow` endpoint |

## API Usage Example

### Step 1: Select Probe Type

```bash
curl -X POST "http://localhost:9081/guardrails/custom-probe-workflow" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_total_steps": 3,
    "step_number": 1,
    "probe_type_option": "llm_policy",
    "project_id": "<project-uuid>"
  }'
```

Response includes `workflow_id` for subsequent steps.

### Step 2: Configure Policy

```bash
curl -X POST "http://localhost:9081/guardrails/custom-probe-workflow" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "<workflow-uuid-from-step-1>",
    "step_number": 2,
    "policy": {
      "task": "Evaluate content for harmful material",
      "definitions": [{"term": "harmful", "definition": "Content that could cause harm"}],
      "safe_content": {
        "description": "Safe content",
        "items": [{"name": "safe", "description": "Safe", "example": "Hello"}]
      },
      "violations": [{
        "category": "harmful_content",
        "severity": "High",
        "description": "Harmful content",
        "items": [{"name": "harm", "description": "Harmful", "example": "Bad"}],
        "examples": [{"input": "test", "rationale": "test"}]
      }]
    }
  }'
```

### Step 3: Probe Metadata + Trigger

```bash
curl -X POST "http://localhost:9081/guardrails/custom-probe-workflow" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "<workflow-uuid-from-step-1>",
    "step_number": 3,
    "trigger_workflow": true,
    "name": "My Custom Probe",
    "description": "Detects harmful content",
    "guard_types": ["input", "output"],
    "modality_types": ["text"]
  }'
```

Response includes `workflow_execution_status` with `probe_id` on success.

## Testing Plan

1. **Unit tests:**
   - Test each step data accumulation
   - Test `trigger_workflow` creates probe
   - Test model_id assignment when model exists vs doesn't exist
   - Test validation errors

2. **Integration tests:**
   - Full 3-step workflow execution
   - Verify probe created with correct data
   - Verify workflow status transitions

## Future Extensions

- Add `CLASSIFIER` probe type option
- Add validation step before trigger
- Support editing policy after probe creation via similar workflow
