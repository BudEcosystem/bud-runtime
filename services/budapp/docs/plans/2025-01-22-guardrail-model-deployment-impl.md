# Guardrail Model Deployment - Implementation Plan

**Goal:** Enable guardrail profiles to use model-based rules (classifiers/LLMs) with automatic onboarding and deployment to clusters.

**Architecture:** Extend existing GuardrailProbe/GuardrailRule with model fields, add GuardrailRuleDeployment junction table, integrate with BudPipeline for orchestrated deployment with progress tracking.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL, Pydantic v2, BudPipeline, Redis

---

## Phase 1: Database Schema Changes

### Task 1.1: Add Enums for Probe and Scanner Types

**Files:**
- Modify: `.worktrees/sentinel-v2/services/budapp/budapp/commons/constants.py`

**Step 1: Add new enum classes**

Add after existing guardrail enums (around line 200-250):

```python
class ProbeTypeEnum(str, Enum):
    """Type of guardrail probe."""
    PROVIDER = "provider"        # Traditional probe from external provider
    MODEL_SCANNER = "model_scanner"  # System model-based rule
    CUSTOM = "custom"            # User-created model-based rule


class ScannerTypeEnum(str, Enum):
    """Type of model scanner for guardrail rules."""
    CLASSIFIER = "classifier"    # Classification model (e.g., Arch-Guard)
    LLM = "llm"                  # LLM-based policy scanner


class GuardrailRuleDeploymentStatusEnum(str, Enum):
    """Status of a guardrail rule model deployment."""
    PENDING = "pending"
    DEPLOYING = "deploying"
    READY = "ready"
    FAILED = "failed"
```

**Step 2: Verify syntax**

Run: `cd .worktrees/sentinel-v2/services/budapp && python -c "from budapp.commons.constants import ProbeTypeEnum, ScannerTypeEnum, GuardrailRuleDeploymentStatusEnum; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
cd .worktrees/sentinel-v2/services/budapp
git add budapp/commons/constants.py
git commit -m "feat(guardrails): add enums for probe types and scanner types"
```

---

### Task 1.2: Create Database Migration for Schema Changes

**Files:**
- Create: `.worktrees/sentinel-v2/services/budapp/budapp/migrations/versions/XXXXXX_add_guardrail_model_fields.py`

**Step 1: Generate migration file**

```bash
cd .worktrees/sentinel-v2/services/budapp
alembic -c budapp/alembic.ini revision -m "add_guardrail_model_fields"
```

**Step 2: Edit migration with schema changes**

Replace the generated file content with:

```python
"""add_guardrail_model_fields

Revision ID: <generated>
Revises: <current_head>
Create Date: 2025-01-22 XX:XX:XX.XXXXXX

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '<generated>'
down_revision = '<current_head>'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create new enum types
    probe_type_enum = postgresql.ENUM(
        'provider', 'model_scanner', 'custom',
        name='probe_type_enum',
        create_type=False
    )
    probe_type_enum.create(op.get_bind(), checkfirst=True)

    scanner_type_enum = postgresql.ENUM(
        'classifier', 'llm',
        name='scanner_type_enum',
        create_type=False
    )
    scanner_type_enum.create(op.get_bind(), checkfirst=True)

    rule_deployment_status_enum = postgresql.ENUM(
        'pending', 'deploying', 'ready', 'failed',
        name='guardrail_rule_deployment_status_enum',
        create_type=False
    )
    rule_deployment_status_enum.create(op.get_bind(), checkfirst=True)

    # Add probe_type to guardrail_probe
    op.add_column(
        'guardrail_probe',
        sa.Column(
            'probe_type',
            sa.Enum('provider', 'model_scanner', 'custom', name='probe_type_enum'),
            nullable=False,
            server_default='provider'
        )
    )

    # Add model fields to guardrail_rule
    op.add_column(
        'guardrail_rule',
        sa.Column(
            'scanner_type',
            sa.Enum('classifier', 'llm', name='scanner_type_enum'),
            nullable=True
        )
    )
    op.add_column(
        'guardrail_rule',
        sa.Column('model_uri', sa.String(255), nullable=True)
    )
    op.add_column(
        'guardrail_rule',
        sa.Column('model_provider_type', sa.String(50), nullable=True)
    )
    op.add_column(
        'guardrail_rule',
        sa.Column('is_gated', sa.Boolean(), nullable=False, server_default='false')
    )
    op.add_column(
        'guardrail_rule',
        sa.Column('model_config_json', postgresql.JSONB(), nullable=True)
    )
    op.add_column(
        'guardrail_rule',
        sa.Column('model_id', postgresql.UUID(as_uuid=True), nullable=True)
    )

    # Add foreign key for model_id
    op.create_foreign_key(
        'fk_guardrail_rule_model_id',
        'guardrail_rule', 'model',
        ['model_id'], ['id'],
        ondelete='SET NULL'
    )

    # Create guardrail_rule_deployment table
    op.create_table(
        'guardrail_rule_deployment',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('guardrail_deployment_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('rule_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('model_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('endpoint_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('cluster_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('config_override_json', postgresql.JSONB(), nullable=True),
        sa.Column(
            'status',
            sa.Enum('pending', 'deploying', 'ready', 'failed', name='guardrail_rule_deployment_status_enum'),
            nullable=False,
            server_default='pending'
        ),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('modified_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['guardrail_deployment_id'], ['guardrail_deployment.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['rule_id'], ['guardrail_rule.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['model_id'], ['model.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['endpoint_id'], ['endpoint.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['cluster_id'], ['cluster.id'], ondelete='CASCADE'),
    )

    # Create indexes
    op.create_index(
        'idx_guardrail_rule_deployment_deployment',
        'guardrail_rule_deployment',
        ['guardrail_deployment_id']
    )
    op.create_index(
        'idx_guardrail_rule_deployment_rule',
        'guardrail_rule_deployment',
        ['rule_id']
    )
    op.create_index(
        'idx_guardrail_rule_deployment_endpoint',
        'guardrail_rule_deployment',
        ['endpoint_id']
    )


def downgrade() -> None:
    # Drop guardrail_rule_deployment table
    op.drop_index('idx_guardrail_rule_deployment_endpoint', 'guardrail_rule_deployment')
    op.drop_index('idx_guardrail_rule_deployment_rule', 'guardrail_rule_deployment')
    op.drop_index('idx_guardrail_rule_deployment_deployment', 'guardrail_rule_deployment')
    op.drop_table('guardrail_rule_deployment')

    # Drop model fields from guardrail_rule
    op.drop_constraint('fk_guardrail_rule_model_id', 'guardrail_rule', type_='foreignkey')
    op.drop_column('guardrail_rule', 'model_id')
    op.drop_column('guardrail_rule', 'model_config_json')
    op.drop_column('guardrail_rule', 'is_gated')
    op.drop_column('guardrail_rule', 'model_provider_type')
    op.drop_column('guardrail_rule', 'model_uri')
    op.drop_column('guardrail_rule', 'scanner_type')

    # Drop probe_type from guardrail_probe
    op.drop_column('guardrail_probe', 'probe_type')

    # Drop enum types
    op.execute('DROP TYPE IF EXISTS guardrail_rule_deployment_status_enum')
    op.execute('DROP TYPE IF EXISTS scanner_type_enum')
    op.execute('DROP TYPE IF EXISTS probe_type_enum')
```

**Step 3: Run migration**

Run: `cd .worktrees/sentinel-v2/services/budapp && alembic -c budapp/alembic.ini upgrade head`
Expected: Migration applies successfully

**Step 4: Commit**

```bash
git add budapp/migrations/versions/
git commit -m "feat(guardrails): add migration for model fields and rule deployment table"
```

---

### Task 1.3: Update SQLAlchemy Models

**Files:**
- Modify: `.worktrees/sentinel-v2/services/budapp/budapp/guardrails/models.py`

**Step 1: Add imports**

Add to imports at top of file:

```python
from budapp.commons.constants import (
    GuardrailDeploymentStatusEnum,
    GuardrailProviderTypeEnum,
    GuardrailStatusEnum,
    GuardrailRuleDeploymentStatusEnum,
    ProbeTypeEnum,
    ScannerTypeEnum,
)
from budapp.cluster_ops.models import Cluster
from budapp.model_ops.models import Model, Provider
```

**Step 2: Add probe_type to GuardrailProbe class**

Add after line 72 (after `provider_type` field):

```python
    probe_type: Mapped[str] = mapped_column(
        Enum(
            ProbeTypeEnum,
            name="probe_type_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=ProbeTypeEnum.PROVIDER,
    )
```

**Step 3: Add model fields to GuardrailRule class**

Add after line 200 (after `modality_types` field):

```python
    # Model-based rule fields
    scanner_type: Mapped[Optional[str]] = mapped_column(
        Enum(
            ScannerTypeEnum,
            name="scanner_type_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=True,
    )
    model_uri: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    model_provider_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_gated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    model_config_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    model_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("model.id", ondelete="SET NULL"), nullable=True)

    # Relationship to Model
    model: Mapped[Optional["Model"]] = relationship("Model")
```

**Step 4: Add GuardrailRuleDeployment model**

Add at end of file:

```python
class GuardrailRuleDeployment(Base, TimestampMixin):
    """Tracks model deployments for guardrail rules."""

    __tablename__ = "guardrail_rule_deployment"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    guardrail_deployment_id: Mapped[UUID] = mapped_column(
        ForeignKey("guardrail_deployment.id", ondelete="CASCADE"), index=True, nullable=False
    )
    rule_id: Mapped[UUID] = mapped_column(
        ForeignKey("guardrail_rule.id", ondelete="CASCADE"), index=True, nullable=False
    )
    model_id: Mapped[UUID] = mapped_column(
        ForeignKey("model.id", ondelete="CASCADE"), nullable=False
    )
    endpoint_id: Mapped[UUID] = mapped_column(
        ForeignKey("endpoint.id", ondelete="CASCADE"), index=True, nullable=False
    )
    cluster_id: Mapped[UUID] = mapped_column(
        ForeignKey("cluster.id", ondelete="CASCADE"), nullable=False
    )
    config_override_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum(
            GuardrailRuleDeploymentStatusEnum,
            name="guardrail_rule_deployment_status_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=GuardrailRuleDeploymentStatusEnum.PENDING,
    )
    error_message: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Relationships
    guardrail_deployment: Mapped["GuardrailDeployment"] = relationship(
        "GuardrailDeployment", back_populates="rule_deployments"
    )
    rule: Mapped["GuardrailRule"] = relationship("GuardrailRule")
    model: Mapped["Model"] = relationship("Model")
    endpoint: Mapped["Endpoint"] = relationship("Endpoint")
    cluster: Mapped["Cluster"] = relationship("Cluster")
```

**Step 5: Add relationship to GuardrailDeployment**

Find `GuardrailDeployment` class and add:

```python
    rule_deployments: Mapped[List["GuardrailRuleDeployment"]] = relationship(
        "GuardrailRuleDeployment", back_populates="guardrail_deployment"
    )
```

**Step 6: Verify models compile**

Run: `cd .worktrees/sentinel-v2/services/budapp && python -c "from budapp.guardrails.models import GuardrailProbe, GuardrailRule, GuardrailRuleDeployment; print('OK')"`
Expected: `OK`

**Step 7: Commit**

```bash
git add budapp/guardrails/models.py
git commit -m "feat(guardrails): update models with probe_type, model fields, and rule deployment"
```

---

## Phase 2: Pydantic Schemas

### Task 2.1: Add Schema Classes for Model Rules

**Files:**
- Modify: `.worktrees/sentinel-v2/services/budapp/budapp/guardrails/schemas.py`

**Step 1: Add enum imports and new schemas**

Add to imports:

```python
from budapp.commons.constants import (
    ProbeTypeEnum,
    ScannerTypeEnum,
    GuardrailRuleDeploymentStatusEnum,
)
```

**Step 2: Add classifier and LLM config schemas**

Add after existing schemas:

```python
# Model config schemas for custom rules
class HeadMapping(BaseModel):
    """Head mapping for classifier models."""
    head_name: str = "default"
    target_labels: list[str]


class ClassifierConfig(BaseModel):
    """Configuration for classifier-based rules."""
    head_mappings: list[HeadMapping]
    post_processing: list[dict] | None = None


class CategoryDef(BaseModel):
    """Category definition for LLM policy."""
    id: str
    description: str
    violation: bool
    escalate: bool | None = None


class ExampleDef(BaseModel):
    """Example for LLM policy."""
    input: str
    output: dict


class PolicyConfig(BaseModel):
    """Policy configuration for LLM-based rules."""
    task: str
    instructions: str
    categories: list[CategoryDef]
    examples: list[ExampleDef] | None = None


class LLMConfig(BaseModel):
    """Configuration for LLM-based rules."""
    handler: str = "gpt_safeguard"
    policy: PolicyConfig
```

**Step 3: Add custom probe create/response schemas**

```python
class GuardrailCustomProbeCreate(BaseModel):
    """Schema for creating a custom model probe."""
    name: str
    description: str | None = None
    scanner_type: ScannerTypeEnum
    model_id: UUID  # User's onboarded model
    model_config: ClassifierConfig | LLMConfig

    @model_validator(mode='after')
    def validate_config_type(self) -> 'GuardrailCustomProbeCreate':
        if self.scanner_type == ScannerTypeEnum.CLASSIFIER:
            if not isinstance(self.model_config, ClassifierConfig):
                raise ValueError("Classifier scanner requires ClassifierConfig")
        elif self.scanner_type == ScannerTypeEnum.LLM:
            if not isinstance(self.model_config, LLMConfig):
                raise ValueError("LLM scanner requires LLMConfig")
        return self


class GuardrailCustomProbeUpdate(BaseModel):
    """Schema for updating a custom model probe."""
    name: str | None = None
    description: str | None = None
    model_config: ClassifierConfig | LLMConfig | None = None


class GuardrailCustomProbeResponse(BaseModel):
    """Response schema for custom probe."""
    id: UUID
    name: str
    description: str | None
    probe_type: ProbeTypeEnum
    scanner_type: ScannerTypeEnum | None
    model_id: UUID | None
    model_uri: str | None
    model_config: dict | None
    status: str
    created_at: datetime
    modified_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

**Step 4: Add rule deployment response schema**

```python
class GuardrailRuleDeploymentResponse(BaseModel):
    """Response schema for rule deployment."""
    id: UUID
    rule_id: UUID
    model_id: UUID
    endpoint_id: UUID
    cluster_id: UUID
    status: GuardrailRuleDeploymentStatusEnum
    error_message: str | None
    config_override_json: dict | None
    created_at: datetime
    modified_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

**Step 5: Update GuardrailProbeResponse to include probe_type**

Find `GuardrailProbeResponse` and add field:

```python
    probe_type: ProbeTypeEnum = ProbeTypeEnum.PROVIDER
```

**Step 6: Update GuardrailRuleResponse to include model fields**

Find `GuardrailRuleResponse` and add fields:

```python
    scanner_type: ScannerTypeEnum | None = None
    model_uri: str | None = None
    model_provider_type: str | None = None
    is_gated: bool = False
    model_config_json: dict | None = None
    model_id: UUID | None = None
```

**Step 7: Update GuardrailDeploymentWorkflowRequest**

Find `GuardrailDeploymentWorkflowRequest` and add fields:

```python
    # Model deployment fields
    cluster_id: UUID | None = None
    deployment_config: dict | None = None  # DeploymentConfig as dict
    callback_topics: list[str] | None = None
```

**Step 8: Update ProbeSelection schema**

Find `ProbeSelection` and add:

```python
    cluster_config_override: dict | None = None  # Per-probe deployment config override
```

**Step 9: Verify schemas**

Run: `cd .worktrees/sentinel-v2/services/budapp && python -c "from budapp.guardrails.schemas import GuardrailCustomProbeCreate, GuardrailRuleDeploymentResponse; print('OK')"`
Expected: `OK`

**Step 10: Commit**

```bash
git add budapp/guardrails/schemas.py
git commit -m "feat(guardrails): add schemas for custom probes and model rule deployment"
```

---

## Phase 3: CRUD Operations

### Task 3.1: Add CRUD for Custom Probes and Rule Deployments

**Files:**
- Modify: `.worktrees/sentinel-v2/services/budapp/budapp/guardrails/crud.py`

**Step 1: Add imports**

```python
from budapp.guardrails.models import GuardrailRuleDeployment
from budapp.commons.constants import ProbeTypeEnum, ScannerTypeEnum, GuardrailRuleDeploymentStatusEnum
```

**Step 2: Add methods to GuardrailsDeploymentDataManager**

Add after existing methods:

```python
    async def create_custom_probe_with_rule(
        self,
        name: str,
        description: str | None,
        scanner_type: str,
        model_id: UUID,
        model_config: dict,
        model_uri: str,
        model_provider_type: str,
        is_gated: bool,
        project_id: UUID,
        user_id: UUID,
        provider_id: UUID,
    ) -> GuardrailProbe:
        """Create a custom probe with a single model-based rule atomically."""
        async with self.session.begin_nested():
            # Create probe
            probe = GuardrailProbe(
                name=name,
                uri=f"custom.{user_id}.{name.lower().replace(' ', '_')}",
                description=description,
                probe_type=ProbeTypeEnum.CUSTOM,
                provider_type=GuardrailProviderTypeEnum.BUD_SENTINEL,
                provider_id=provider_id,
                created_by=user_id,
                status=GuardrailStatusEnum.ACTIVE,
            )
            self.session.add(probe)
            await self.session.flush()

            # Create single rule for the probe
            rule = GuardrailRule(
                probe_id=probe.id,
                name=name,
                uri=f"custom.{user_id}.{name.lower().replace(' ', '_')}.rule",
                description=description,
                scanner_type=scanner_type,
                model_uri=model_uri,
                model_provider_type=model_provider_type,
                is_gated=is_gated,
                model_config_json=model_config,
                model_id=model_id,
                created_by=user_id,
                status=GuardrailStatusEnum.ACTIVE,
            )
            self.session.add(rule)
            await self.session.flush()

        return probe

    async def get_custom_probes(
        self,
        user_id: UUID,
        project_id: UUID | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[GuardrailProbe], int]:
        """Get custom probes created by user."""
        filters = {
            "probe_type": ProbeTypeEnum.CUSTOM,
            "created_by": user_id,
            "status": GuardrailStatusEnum.ACTIVE,
        }

        query = select(GuardrailProbe).filter_by(**filters)
        count_query = select(func.count()).select_from(GuardrailProbe).filter_by(**filters)

        total = await self.session.scalar(count_query)
        result = await self.session.execute(query.offset(offset).limit(limit))
        probes = result.scalars().all()

        return list(probes), total or 0

    async def get_model_probes_from_selections(
        self,
        probe_ids: list[UUID],
    ) -> list[GuardrailProbe]:
        """Get probes that are model-based (model_scanner or custom) from selection."""
        query = (
            select(GuardrailProbe)
            .where(GuardrailProbe.id.in_(probe_ids))
            .where(GuardrailProbe.probe_type.in_([ProbeTypeEnum.MODEL_SCANNER, ProbeTypeEnum.CUSTOM]))
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def create_rule_deployment(
        self,
        guardrail_deployment_id: UUID,
        rule_id: UUID,
        model_id: UUID,
        endpoint_id: UUID,
        cluster_id: UUID,
        config_override: dict | None = None,
    ) -> GuardrailRuleDeployment:
        """Create a rule deployment record."""
        deployment = GuardrailRuleDeployment(
            guardrail_deployment_id=guardrail_deployment_id,
            rule_id=rule_id,
            model_id=model_id,
            endpoint_id=endpoint_id,
            cluster_id=cluster_id,
            config_override_json=config_override,
            status=GuardrailRuleDeploymentStatusEnum.PENDING,
        )
        self.session.add(deployment)
        await self.session.flush()
        return deployment

    async def update_rule_deployment_status(
        self,
        rule_deployment_id: UUID,
        status: GuardrailRuleDeploymentStatusEnum,
        error_message: str | None = None,
    ) -> GuardrailRuleDeployment:
        """Update rule deployment status."""
        deployment = await self.retrieve_by_fields(
            GuardrailRuleDeployment, {"id": rule_deployment_id}
        )
        deployment.status = status
        if error_message:
            deployment.error_message = error_message
        await self.session.flush()
        return deployment

    async def get_rule_deployments_for_guardrail(
        self,
        guardrail_deployment_id: UUID,
    ) -> list[GuardrailRuleDeployment]:
        """Get all rule deployments for a guardrail deployment."""
        query = select(GuardrailRuleDeployment).where(
            GuardrailRuleDeployment.guardrail_deployment_id == guardrail_deployment_id
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())
```

**Step 3: Verify CRUD**

Run: `cd .worktrees/sentinel-v2/services/budapp && python -c "from budapp.guardrails.crud import GuardrailsDeploymentDataManager; print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add budapp/guardrails/crud.py
git commit -m "feat(guardrails): add CRUD methods for custom probes and rule deployments"
```

---

## Phase 4: API Routes

### Task 4.1: Add Custom Probe Routes

**Files:**
- Modify: `.worktrees/sentinel-v2/services/budapp/budapp/guardrails/guardrail_routes.py`

**Step 1: Add imports**

```python
from budapp.guardrails.schemas import (
    GuardrailCustomProbeCreate,
    GuardrailCustomProbeUpdate,
    GuardrailCustomProbeResponse,
)
```

**Step 2: Add custom probe endpoints**

Add after existing probe routes:

```python
@router.post(
    "/custom-probe",
    response_model=APIResponseSchema[GuardrailCustomProbeResponse],
    summary="Create a custom model probe",
)
@require_permissions([UserPermissionEnum.ENDPOINT_MANAGE])
async def create_custom_probe(
    request: GuardrailCustomProbeCreate,
    project_id: UUID = Query(..., description="Project ID"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """Create a custom model-based probe with a single rule."""
    service = GuardrailCustomProbeService(session)
    probe = await service.create_custom_probe(
        request=request,
        project_id=project_id,
        user_id=current_user.id,
    )
    return APIResponseSchema(
        code=status.HTTP_201_CREATED,
        object="guardrail.custom_probe.create",
        message="Custom probe created successfully",
        data=GuardrailCustomProbeResponse.model_validate(probe),
    )


@router.get(
    "/custom-probes",
    response_model=APIResponsePaginatedSchema[GuardrailCustomProbeResponse],
    summary="List custom probes",
)
@require_permissions([UserPermissionEnum.ENDPOINT_VIEW])
async def list_custom_probes(
    project_id: UUID | None = Query(None, description="Filter by project"),
    pagination: PaginationQuery = Depends(),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """List custom probes created by the current user."""
    data_manager = GuardrailsDeploymentDataManager(session)
    probes, total = await data_manager.get_custom_probes(
        user_id=current_user.id,
        project_id=project_id,
        offset=pagination.offset,
        limit=pagination.limit,
    )
    return APIResponsePaginatedSchema(
        code=status.HTTP_200_OK,
        object="guardrail.custom_probe.list",
        message="Custom probes retrieved successfully",
        data=[GuardrailCustomProbeResponse.model_validate(p) for p in probes],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.put(
    "/custom-probe/{probe_id}",
    response_model=APIResponseSchema[GuardrailCustomProbeResponse],
    summary="Update a custom probe",
)
@require_permissions([UserPermissionEnum.ENDPOINT_MANAGE])
async def update_custom_probe(
    probe_id: UUID,
    request: GuardrailCustomProbeUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """Update a custom probe (user must be owner)."""
    service = GuardrailCustomProbeService(session)
    probe = await service.update_custom_probe(
        probe_id=probe_id,
        request=request,
        user_id=current_user.id,
    )
    return APIResponseSchema(
        code=status.HTTP_200_OK,
        object="guardrail.custom_probe.update",
        message="Custom probe updated successfully",
        data=GuardrailCustomProbeResponse.model_validate(probe),
    )


@router.delete(
    "/custom-probe/{probe_id}",
    response_model=APIResponseSchema,
    summary="Delete a custom probe",
)
@require_permissions([UserPermissionEnum.ENDPOINT_MANAGE])
async def delete_custom_probe(
    probe_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """Delete a custom probe (soft delete, user must be owner)."""
    service = GuardrailCustomProbeService(session)
    await service.delete_custom_probe(
        probe_id=probe_id,
        user_id=current_user.id,
    )
    return APIResponseSchema(
        code=status.HTTP_200_OK,
        object="guardrail.custom_probe.delete",
        message="Custom probe deleted successfully",
    )
```

**Step 3: Add deployment progress endpoint**

```python
@router.get(
    "/deployment/{deployment_id}/progress",
    response_model=APIResponseSchema,
    summary="Get deployment progress",
)
@require_permissions([UserPermissionEnum.ENDPOINT_VIEW])
async def get_deployment_progress(
    deployment_id: UUID,
    detail: str = Query("summary", description="Detail level: summary, steps, full"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """Get progress of a guardrail deployment via BudPipeline."""
    service = GuardrailDeploymentWorkflowService(session)
    progress = await service.get_deployment_progress(
        deployment_id=deployment_id,
        detail=detail,
    )
    return APIResponseSchema(
        code=status.HTTP_200_OK,
        object="guardrail.deployment.progress",
        message="Deployment progress retrieved",
        data=progress,
    )
```

**Step 4: Verify routes compile**

Run: `cd .worktrees/sentinel-v2/services/budapp && python -c "from budapp.guardrails.guardrail_routes import router; print('OK')"`
Expected: `OK`

**Step 5: Commit**

```bash
git add budapp/guardrails/guardrail_routes.py
git commit -m "feat(guardrails): add API routes for custom probes and deployment progress"
```

---

## Phase 5: Service Layer

### Task 5.1: Add Custom Probe Service

**Files:**
- Modify: `.worktrees/sentinel-v2/services/budapp/budapp/guardrails/services.py`

**Step 1: Add GuardrailCustomProbeService class**

Add new service class:

```python
class GuardrailCustomProbeService(SessionMixin):
    """Service for managing custom model-based probes."""

    async def create_custom_probe(
        self,
        request: GuardrailCustomProbeCreate,
        project_id: UUID,
        user_id: UUID,
    ) -> GuardrailProbe:
        """Create a custom probe with model-based rule."""
        # Validate model exists and belongs to user/project
        model = await ModelDataManager(self.session).retrieve_by_fields(
            Model, {"id": request.model_id}
        )
        if not model:
            raise ClientException("Model not found")

        # Get Bud Sentinel provider
        provider = await ProviderDataManager(self.session).get_provider_by_type(
            GuardrailProviderTypeEnum.BUD_SENTINEL.value
        )
        if not provider:
            raise ClientException("Bud Sentinel provider not configured")

        # Create probe with rule
        data_manager = GuardrailsDeploymentDataManager(self.session)
        probe = await data_manager.create_custom_probe_with_rule(
            name=request.name,
            description=request.description,
            scanner_type=request.scanner_type.value,
            model_id=request.model_id,
            model_config=request.model_config.model_dump(),
            model_uri=model.uri,
            model_provider_type=model.provider_type,
            is_gated=False,  # User's onboarded model is already accessible
            project_id=project_id,
            user_id=user_id,
            provider_id=provider.id,
        )

        return probe

    async def update_custom_probe(
        self,
        probe_id: UUID,
        request: GuardrailCustomProbeUpdate,
        user_id: UUID,
    ) -> GuardrailProbe:
        """Update a custom probe."""
        data_manager = GuardrailsDeploymentDataManager(self.session)

        # Get probe and verify ownership
        probe = await data_manager.retrieve_by_fields(
            GuardrailProbe, {"id": probe_id, "created_by": user_id, "probe_type": ProbeTypeEnum.CUSTOM}
        )
        if not probe:
            raise ClientException("Custom probe not found or access denied")

        # Update probe fields
        update_data = request.model_dump(exclude_none=True)
        if update_data:
            for key, value in update_data.items():
                if key == "model_config" and probe.rules:
                    # Update the rule's model_config
                    probe.rules[0].model_config_json = value
                elif hasattr(probe, key):
                    setattr(probe, key, value)
            await self.session.flush()

        return probe

    async def delete_custom_probe(
        self,
        probe_id: UUID,
        user_id: UUID,
    ) -> None:
        """Soft delete a custom probe."""
        data_manager = GuardrailsDeploymentDataManager(self.session)

        probe = await data_manager.retrieve_by_fields(
            GuardrailProbe, {"id": probe_id, "created_by": user_id, "probe_type": ProbeTypeEnum.CUSTOM}
        )
        if not probe:
            raise ClientException("Custom probe not found or access denied")

        # Soft delete
        probe.status = GuardrailStatusEnum.DELETED
        for rule in probe.rules:
            rule.status = GuardrailStatusEnum.DELETED
        await self.session.flush()
```

**Step 2: Verify service**

Run: `cd .worktrees/sentinel-v2/services/budapp && python -c "from budapp.guardrails.services import GuardrailCustomProbeService; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add budapp/guardrails/services.py
git commit -m "feat(guardrails): add custom probe service"
```

---

## Phase 6: BudPipeline Integration

### Task 6.1: Create Guardrail Pipeline Actions

**Files:**
- Create: `.worktrees/sentinel-v2/services/budapp/budapp/guardrails/pipeline_actions.py`

**Step 1: Create pipeline actions module**

```python
"""BudPipeline actions for guardrail deployment workflow."""

from typing import Any, Dict
from uuid import UUID

from budapp.commons.db_utils import SessionMixin
from budapp.guardrails.crud import GuardrailsDeploymentDataManager
from budapp.guardrails.models import GuardrailProbe, GuardrailRule
from budapp.commons.constants import ProbeTypeEnum, GuardrailRuleDeploymentStatusEnum


class GuardrailPipelineActions(SessionMixin):
    """Pipeline action handlers for guardrail deployment."""

    async def validate_deployment(
        self,
        profile_id: UUID | None,
        probe_selections: list[dict],
        cluster_id: UUID | None,
        credential_id: UUID | None,
    ) -> Dict[str, Any]:
        """Validate deployment request and return validated data."""
        errors = []
        data_manager = GuardrailsDeploymentDataManager(self.session)

        # Get probe IDs
        probe_ids = [UUID(s["probe_id"]) for s in probe_selections]

        # Check for model probes
        model_probes = await data_manager.get_model_probes_from_selections(probe_ids)

        if model_probes:
            if not cluster_id:
                errors.append("cluster_id required when deploying model-based probes")

            # Check gated models
            gated_probes = []
            for probe in model_probes:
                for rule in probe.rules:
                    if rule.is_gated:
                        gated_probes.append(probe.name)
                        break

            if gated_probes and not credential_id:
                errors.append(f"credential_id required for gated models: {gated_probes}")

        if errors:
            return {"success": False, "errors": errors}

        return {
            "success": True,
            "probe_selections": probe_selections,
            "model_probes": [{"id": str(p.id), "name": p.name} for p in model_probes],
        }

    async def identify_model_requirements(
        self,
        probe_selections: list[dict],
        cluster_id: UUID,
    ) -> Dict[str, Any]:
        """Identify which models need onboarding and deployment."""
        data_manager = GuardrailsDeploymentDataManager(self.session)

        probe_ids = [UUID(s["probe_id"]) for s in probe_selections]
        model_probes = await data_manager.get_model_probes_from_selections(probe_ids)

        models_to_onboard = []
        models_to_deploy = []

        for probe in model_probes:
            rule = probe.rules[0]  # Model probes have single rule
            selection = next((s for s in probe_selections if s["probe_id"] == str(probe.id)), {})

            if rule.model_id is None:
                # Model not onboarded yet
                models_to_onboard.append({
                    "rule_id": str(rule.id),
                    "model_uri": rule.model_uri,
                    "provider_type": rule.model_provider_type,
                    "is_gated": rule.is_gated,
                    "cluster_config": selection.get("cluster_config_override"),
                })
            else:
                # Check if already deployed to target cluster
                # TODO: Check existing deployments
                models_to_deploy.append({
                    "rule_id": str(rule.id),
                    "model_id": str(rule.model_id),
                    "cluster_config": selection.get("cluster_config_override"),
                })

        return {
            "models_to_onboard": models_to_onboard,
            "models_to_deploy": models_to_deploy,
        }

    async def build_guardrail_config(
        self,
        profile_id: UUID,
        rule_deployments: list[dict],
    ) -> Dict[str, Any]:
        """Build guardrail configuration with deployed endpoint URLs."""
        # Build metadata_json with scanner URLs
        metadata = {}
        custom_rules = []

        for rd in rule_deployments:
            rule = await self.session.get(GuardrailRule, UUID(rd["rule_id"]))
            endpoint_url = rd.get("endpoint_url", "")

            if rule.scanner_type == "llm":
                metadata["llm"] = {
                    "url": f"{endpoint_url}/v1",
                    "api_key_header": "Authorization",
                    "timeout_ms": 30000,
                }
                custom_rules.append({
                    "id": rule.uri,
                    "scanner": "llm",
                    "scanner_config_json": rule.model_config_json,
                })
            elif rule.scanner_type == "classifier":
                metadata["latentbud"] = {
                    "url": endpoint_url,
                    "api_key_header": "Authorization",
                    "timeout_ms": 30000,
                }
                custom_rules.append({
                    "id": rule.uri,
                    "scanner": "latentbud",
                    "scanner_config_json": rule.model_config_json,
                })

        return {
            "custom_rules": custom_rules,
            "metadata_json": metadata,
        }
```

**Step 2: Verify actions**

Run: `cd .worktrees/sentinel-v2/services/budapp && python -c "from budapp.guardrails.pipeline_actions import GuardrailPipelineActions; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add budapp/guardrails/pipeline_actions.py
git commit -m "feat(guardrails): add BudPipeline action handlers for deployment workflow"
```

---

## Phase 7: Testing

### Task 7.1: Add Unit Tests for Custom Probes

**Files:**
- Create: `.worktrees/sentinel-v2/services/budapp/tests/test_guardrail_custom_probes.py`

**Step 1: Create test file**

```python
"""Tests for guardrail custom probe functionality."""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from budapp.guardrails.services import GuardrailCustomProbeService
from budapp.guardrails.schemas import GuardrailCustomProbeCreate, ClassifierConfig, HeadMapping
from budapp.commons.constants import ScannerTypeEnum, ProbeTypeEnum


@pytest.mark.asyncio
async def test_create_custom_probe_classifier():
    """Test creating a custom classifier probe."""
    mock_session = AsyncMock()
    service = GuardrailCustomProbeService(mock_session)

    request = GuardrailCustomProbeCreate(
        name="Test Classifier",
        description="Test description",
        scanner_type=ScannerTypeEnum.CLASSIFIER,
        model_id=uuid4(),
        model_config=ClassifierConfig(
            head_mappings=[HeadMapping(head_name="default", target_labels=["JAILBREAK"])]
        ),
    )

    with patch.object(service, '_get_model') as mock_get_model:
        mock_model = Mock()
        mock_model.uri = "test/model"
        mock_model.provider_type = "hugging_face"
        mock_get_model.return_value = mock_model

        # Test will fail initially - this is expected for TDD
        # Implementation will make it pass


@pytest.mark.asyncio
async def test_custom_probe_requires_model_id():
    """Test that custom probe creation requires valid model_id."""
    with pytest.raises(ValueError):
        GuardrailCustomProbeCreate(
            name="Test",
            scanner_type=ScannerTypeEnum.CLASSIFIER,
            model_id=None,  # Should fail
            model_config=ClassifierConfig(
                head_mappings=[HeadMapping(target_labels=["TEST"])]
            ),
        )


@pytest.mark.asyncio
async def test_classifier_config_validation():
    """Test classifier config requires head_mappings."""
    config = ClassifierConfig(
        head_mappings=[
            HeadMapping(head_name="default", target_labels=["SAFE", "UNSAFE"])
        ]
    )
    assert len(config.head_mappings) == 1
    assert config.head_mappings[0].target_labels == ["SAFE", "UNSAFE"]
```

**Step 2: Run tests**

Run: `cd .worktrees/sentinel-v2/services/budapp && pytest tests/test_guardrail_custom_probes.py -v`
Expected: Tests run (some may fail until implementation complete)

**Step 3: Commit**

```bash
git add tests/test_guardrail_custom_probes.py
git commit -m "test(guardrails): add unit tests for custom probe functionality"
```

---

## Phase 8: Documentation and Cleanup

### Task 8.1: Update __init__.py exports

**Files:**
- Modify: `.worktrees/sentinel-v2/services/budapp/budapp/guardrails/__init__.py`

**Step 1: Add exports**

```python
from budapp.guardrails.models import (
    GuardrailProbe,
    GuardrailRule,
    GuardrailProfile,
    GuardrailProfileProbe,
    GuardrailProfileRule,
    GuardrailDeployment,
    GuardrailRuleDeployment,
)
from budapp.guardrails.services import (
    GuardrailCustomProbeService,
    GuardrailDeploymentWorkflowService,
)

__all__ = [
    "GuardrailProbe",
    "GuardrailRule",
    "GuardrailProfile",
    "GuardrailProfileProbe",
    "GuardrailProfileRule",
    "GuardrailDeployment",
    "GuardrailRuleDeployment",
    "GuardrailCustomProbeService",
    "GuardrailDeploymentWorkflowService",
]
```

**Step 2: Commit**

```bash
git add budapp/guardrails/__init__.py
git commit -m "chore(guardrails): update module exports"
```

---

### Task 8.2: Final Integration Test

**Step 1: Run full test suite**

```bash
cd .worktrees/sentinel-v2/services/budapp
pytest tests/ -v --tb=short -x
```

**Step 2: Run linting**

```bash
ruff check budapp/guardrails/ --fix
ruff format budapp/guardrails/
```

**Step 3: Type check**

```bash
mypy budapp/guardrails/
```

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat(guardrails): complete model-based rules implementation

- Add probe_type to distinguish provider, model_scanner, custom probes
- Add model fields to GuardrailRule (scanner_type, model_uri, etc.)
- Add GuardrailRuleDeployment junction table
- Add custom probe CRUD and API endpoints
- Add BudPipeline action handlers for deployment workflow
- Add unit tests for custom probe functionality"
```

---

## Summary

| Phase | Tasks | Key Files |
|-------|-------|-----------|
| 1. Schema | 1.1-1.3 | constants.py, migrations, models.py |
| 2. Schemas | 2.1 | schemas.py |
| 3. CRUD | 3.1 | crud.py |
| 4. Routes | 4.1 | guardrail_routes.py |
| 5. Services | 5.1 | services.py |
| 6. Pipeline | 6.1 | pipeline_actions.py |
| 7. Testing | 7.1 | test_guardrail_custom_probes.py |
| 8. Cleanup | 8.1-8.2 | __init__.py, lint/format |

**Total Tasks:** 11 tasks across 8 phases

**Next Steps After Implementation:**
1. Register BudPipeline actions in budpipeline service
2. Seed model_scanner probes for curated rules (Arch-Guard, etc.)
3. Update budadmin frontend to support custom probe creation
4. Integration testing with actual model deployment
