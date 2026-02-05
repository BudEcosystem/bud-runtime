# Custom Probe Workflow Design

**Date:** 2026-02-05
**Status:** Approved
**Service:** budapp (guardrails module)

## Overview

Create a new workflow for custom probes similar to the deployment workflow. This follows a **probe-first pattern** where the probe is created with `model_uri` only, and `model_id` gets assigned later during deployment (or immediately if model is already onboarded).

## Workflow Steps

```
┌─────────────────────────────────────────────────────────────────┐
│                    CUSTOM PROBE WORKFLOW                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Step 1: SELECT PROBE TYPE                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ • User selects: llm_policy (future: classifier, etc.)   │   │
│  │ • System auto-sets:                                     │   │
│  │   - model_uri = "openai/gpt-oss-safeguard-20b"         │   │
│  │   - provider = "bud"                                    │   │
│  │   - scanner_type = LLM                                  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                            ↓                                    │
│  Step 2: CONFIGURE POLICY                                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ • User provides policy config (task, definitions,       │   │
│  │   violations, safe_content, etc.)                       │   │
│  │ • System wraps in LLMConfig with handler="gpt_safeguard"│   │
│  │ • model_id = looked up by URI (or None if not onboarded)│   │
│  └─────────────────────────────────────────────────────────┘   │
│                            ↓                                    │
│  Step 3: PROBE METADATA                                         │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ • name, description                                     │   │
│  │ • guard_types: ["input"] or ["output"] or both          │   │
│  │ • modality_types: ["text"], ["image"], etc.             │   │
│  └─────────────────────────────────────────────────────────┘   │
│                            ↓                                    │
│  RESULT: Probe + Rule created with model_uri                   │
│  • model_id assigned if model exists, else None                │
│  • model_id assigned during deployment if not set              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Key Design Decisions

### 1. model_id Assignment Strategy

- **At probe creation:** Check if model exists by URI → assign `model_id` if found, else `None`
- **At deployment:** Existing flow handles URI lookup if `model_id` is null
- **model_id on rule is kept** as a cached lookup optimization (avoids repeated URI lookups)

### 2. Probe Type Configuration Mapping

| probe_type_option | model_uri | scanner_type | handler | provider_type |
|-------------------|-----------|--------------|---------|---------------|
| `llm_policy` | `openai/gpt-oss-safeguard-20b` | `LLM` | `gpt_safeguard` | `bud` |
| *(future)* `classifier` | TBD | `CLASSIFIER` | TBD | `bud` |

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

### New Schema: `GuardrailCustomProbeWorkflowCreate`

```python
# File: budapp/guardrails/schemas.py

class GuardrailCustomProbeWorkflowCreate(BaseModel):
    """Schema for creating custom probe via workflow (probe-first approach)."""

    # Step 1: Probe type selection
    probe_type_option: CustomProbeTypeEnum

    # Step 2: Policy configuration (for llm_policy)
    policy: PolicyConfig

    # Step 3: Probe metadata
    name: str
    description: str | None = None
    guard_types: list[str]
    modality_types: list[str]
```

### Configuration Constants

```python
# File: budapp/guardrails/constants.py (new file) or in services.py

from dataclasses import dataclass

@dataclass
class ProbeTypeConfig:
    model_uri: str
    scanner_type: ScannerTypeEnum
    handler: str
    model_provider_type: ModelProviderTypeEnum

PROBE_TYPE_CONFIGS: dict[CustomProbeTypeEnum, ProbeTypeConfig] = {
    CustomProbeTypeEnum.LLM_POLICY: ProbeTypeConfig(
        model_uri="openai/gpt-oss-safeguard-20b",
        scanner_type=ScannerTypeEnum.LLM,
        handler="gpt_safeguard",
        model_provider_type=ModelProviderTypeEnum.OPENAI,
    ),
}
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

### New Service Method: `create_custom_probe_workflow`

```python
# File: budapp/guardrails/services.py

class GuardrailCustomProbeService:

    async def create_custom_probe_workflow(
        self,
        request: GuardrailCustomProbeWorkflowCreate,
        project_id: UUID,
        user_id: UUID,
    ) -> GuardrailProbe:
        """Create a custom probe via workflow (probe-first approach).

        Args:
            request: Workflow creation request with probe type, policy, and metadata
            project_id: Project ID for the probe
            user_id: User ID of the creator

        Returns:
            The created GuardrailProbe instance
        """
        from budapp.model_ops.crud import ModelDataManager
        from budapp.model_ops.models import Model

        # 1. Get config for probe type
        config = PROBE_TYPE_CONFIGS.get(request.probe_type_option)
        if not config:
            raise ClientException(
                message=f"Unknown probe type: {request.probe_type_option}",
                status_code=HTTPStatus.HTTP_400_BAD_REQUEST,
            )

        # 2. Check if model already exists (optional assignment)
        model_id = None
        model_data_manager = ModelDataManager(self.session)
        existing_model = await model_data_manager.retrieve_by_fields(
            Model,
            {"uri": config.model_uri, "status": ModelStatusEnum.ACTIVE},
            missing_ok=True
        )
        if existing_model:
            model_id = existing_model.id

        # 3. Get the BudSentinel provider
        provider = await ProviderDataManager(self.session).retrieve_by_fields(
            Provider, {"type": "bud_sentinel"}
        )
        if not provider:
            raise ClientException(
                message="BudSentinel provider not found",
                status_code=HTTPStatus.HTTP_404_NOT_FOUND,
            )

        # 4. Build model config
        model_config = LLMConfig(
            handler=config.handler,
            policy=request.policy
        ).model_dump()

        # 5. Create the custom probe with its rule
        probe = await GuardrailsDeploymentDataManager(self.session).create_custom_probe_with_rule(
            name=request.name,
            description=request.description,
            scanner_type=config.scanner_type.value,
            model_id=model_id,
            model_config=model_config,
            model_uri=config.model_uri,
            model_provider_type=config.model_provider_type.value,
            is_gated=False,
            project_id=project_id,
            user_id=user_id,
            provider_id=provider.id,
            guard_types=request.guard_types,
            modality_types=request.modality_types,
        )

        return probe
```

## Route Changes

### New Endpoint: `POST /guardrails/custom-probe-workflow`

```python
# File: budapp/guardrails/guardrail_routes.py

@router.post(
    "/custom-probe-workflow",
    responses={
        status.HTTP_201_CREATED: {
            "model": GuardrailCustomProbeDetailResponse,
            "description": "Successfully created custom probe via workflow",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Invalid request",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Server error",
        },
    },
    description="Create a custom probe via workflow (probe-first approach)",
    status_code=status.HTTP_201_CREATED,
)
@require_permissions(permissions=[PermissionEnum.MODEL_MANAGE])
async def create_custom_probe_workflow(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    request: GuardrailCustomProbeWorkflowCreate,
    project_id: UUID = Query(..., description="Project ID"),
) -> Union[GuardrailCustomProbeDetailResponse, ErrorResponse]:
    """Create a custom probe via workflow.

    This endpoint follows the probe-first pattern where:
    1. User selects probe type (e.g., llm_policy)
    2. System auto-assigns model_uri based on probe type
    3. User provides policy configuration and metadata
    4. Probe is created with model_id if model exists, else None
    5. model_id gets assigned during deployment workflow if not set
    """
    try:
        service = GuardrailCustomProbeService(session)
        probe = await service.create_custom_probe_workflow(
            request=request,
            project_id=project_id,
            user_id=current_user.id,
        )
        return GuardrailCustomProbeDetailResponse(
            code=status.HTTP_201_CREATED,
            object="guardrail.custom_probe_workflow.create",
            message="Custom probe created successfully via workflow",
            probe=GuardrailCustomProbeResponse.model_validate(probe),
        ).to_http_response()
    except ClientException as e:
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to create custom probe via workflow: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to create custom probe",
        ).to_http_response()
```

## Response Schema Updates

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
```

## Files to Modify

| File | Changes |
|------|---------|
| `budapp/guardrails/schemas.py` | Add `CustomProbeTypeEnum`, `GuardrailCustomProbeWorkflowCreate`, update `GuardrailCustomProbeResponse` |
| `budapp/guardrails/services.py` | Add `PROBE_TYPE_CONFIGS`, `create_custom_probe_workflow` method |
| `budapp/guardrails/crud.py` | Update `create_custom_probe_with_rule` to accept `guard_types`, `modality_types` |
| `budapp/guardrails/guardrail_routes.py` | Add `POST /custom-probe-workflow` endpoint |

## Testing Plan

1. **Unit tests:**
   - Test `create_custom_probe_workflow` with model exists (model_id assigned)
   - Test `create_custom_probe_workflow` with model not exists (model_id = None)
   - Test validation of `probe_type_option`
   - Test `guard_types` and `modality_types` are stored correctly

2. **Integration tests:**
   - Create probe via workflow → verify in DB
   - Create probe with non-existent model → verify model_id is None
   - Deploy probe via deployment workflow → verify model_id gets resolved via URI lookup

## Future Extensions

- Add `CLASSIFIER` probe type option
- Add `REGEX` probe type option
- Support multiple policies per probe
- Support custom model_uri override for advanced users
