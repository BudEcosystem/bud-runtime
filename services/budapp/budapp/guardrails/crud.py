#  -----------------------------------------------------------------------------
#  Copyright (c) 2024 Bud Ecosystem Inc.
#  #
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#  #
#      http://www.apache.org/licenses/LICENSE-2.0
#  #
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#  -----------------------------------------------------------------------------

"""CRUD operations for guardrail models."""

from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, delete, func, or_
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.sql import select

from budapp.commons.constants import GuardrailDeploymentStatusEnum, GuardrailProviderEnum
from budapp.guardrails.models import (
    GuardrailDeployment,
    GuardrailDeploymentProbe,
    GuardrailDeploymentRuleConfig,
    GuardrailGuardType,
    GuardrailModalityType,
    GuardrailProbe,
    GuardrailProvider,
    GuardrailRule,
    GuardrailRuleGuardType,
    GuardrailRuleModality,
    GuardrailRuleScanner,
    GuardrailScannerType,
)
from budapp.guardrails.schemas import (
    GuardrailDeploymentCreate,
    GuardrailDeploymentListRequestSchema,
    GuardrailDeploymentProbeCreate,
    GuardrailDeploymentUpdate,
    GuardrailGuardTypeCreate,
    GuardrailModalityTypeCreate,
    GuardrailProbeCreate,
    GuardrailProviderCreate,
    GuardrailProviderUpdate,
    GuardrailProbeListRequestSchema,
    GuardrailProbeUpdate,
    GuardrailRuleCreate,
    GuardrailRuleUpdate,
    GuardrailScannerTypeCreate,
)


# Scanner type CRUD operations
async def create_scanner_type(db: AsyncSession, scanner_data: GuardrailScannerTypeCreate) -> GuardrailScannerType:
    """Create a new scanner type."""
    scanner = GuardrailScannerType(**scanner_data.model_dump())
    db.add(scanner)
    await db.commit()
    await db.refresh(scanner)
    return scanner


async def get_scanner_type(db: AsyncSession, scanner_id: UUID) -> Optional[GuardrailScannerType]:
    """Get a scanner type by ID."""
    result = await db.execute(select(GuardrailScannerType).where(GuardrailScannerType.id == scanner_id))
    return result.scalar_one_or_none()


async def get_scanner_types(db: AsyncSession) -> List[GuardrailScannerType]:
    """Get all scanner types."""
    result = await db.execute(select(GuardrailScannerType).order_by(GuardrailScannerType.name))
    return result.scalars().all()


# Modality type CRUD operations
async def create_modality_type(db: AsyncSession, modality_data: GuardrailModalityTypeCreate) -> GuardrailModalityType:
    """Create a new modality type."""
    modality = GuardrailModalityType(**modality_data.model_dump())
    db.add(modality)
    await db.commit()
    await db.refresh(modality)
    return modality


async def get_modality_type(db: AsyncSession, modality_id: UUID) -> Optional[GuardrailModalityType]:
    """Get a modality type by ID."""
    result = await db.execute(select(GuardrailModalityType).where(GuardrailModalityType.id == modality_id))
    return result.scalar_one_or_none()


async def get_modality_types(db: AsyncSession) -> List[GuardrailModalityType]:
    """Get all modality types."""
    result = await db.execute(select(GuardrailModalityType).order_by(GuardrailModalityType.name))
    return result.scalars().all()


# Provider CRUD operations
async def create_provider(
    db: AsyncSession, provider_data: GuardrailProviderCreate, created_by: UUID
) -> GuardrailProvider:
    """Create a new guardrail provider."""
    provider_dict = provider_data.model_dump()
    provider_dict["created_by"] = created_by
    provider = GuardrailProvider(**provider_dict)
    db.add(provider)
    await db.commit()
    await db.refresh(provider)
    return provider


async def get_provider(db: AsyncSession, provider_id: UUID) -> Optional[GuardrailProvider]:
    """Get a provider by ID."""
    result = await db.execute(
        select(GuardrailProvider)
        .where(GuardrailProvider.id == provider_id)
        .options(selectinload(GuardrailProvider.probes))
    )
    return result.scalar_one_or_none()


async def get_providers(db: AsyncSession, include_inactive: bool = False) -> List[GuardrailProvider]:
    """Get all providers."""
    query = select(GuardrailProvider).order_by(GuardrailProvider.display_name)
    if not include_inactive:
        query = query.where(GuardrailProvider.is_active.is_(True))
    result = await db.execute(query)
    return result.scalars().all()


async def update_provider(
    db: AsyncSession, provider_id: UUID, provider_data: GuardrailProviderUpdate, user_id: UUID
) -> Optional[GuardrailProvider]:
    """Update a provider (only custom providers can be updated by their owner)."""
    provider = await get_provider(db, provider_id)
    if not provider:
        return None

    # Only custom providers can be updated, and only by their owner
    if provider.provider_type != GuardrailProviderEnum.CUSTOM or provider.user_id != user_id:
        return None

    for field, value in provider_data.model_dump(exclude_unset=True).items():
        setattr(provider, field, value)

    await db.commit()
    await db.refresh(provider)
    return provider


async def delete_provider(db: AsyncSession, provider_id: UUID, user_id: UUID) -> bool:
    """Delete a provider (only custom providers can be deleted by their owner)."""
    provider = await get_provider(db, provider_id)
    if not provider:
        return False

    # Only custom providers can be deleted, and only by their owner
    if provider.provider_type != GuardrailProviderEnum.CUSTOM or provider.user_id != user_id:
        return False

    await db.delete(provider)
    await db.commit()
    return True


# Guard type CRUD operations
async def create_guard_type(db: AsyncSession, guard_data: GuardrailGuardTypeCreate) -> GuardrailGuardType:
    """Create a new guard type."""
    guard = GuardrailGuardType(**guard_data.model_dump())
    db.add(guard)
    await db.commit()
    await db.refresh(guard)
    return guard


async def get_guard_type(db: AsyncSession, guard_id: UUID) -> Optional[GuardrailGuardType]:
    """Get a guard type by ID."""
    result = await db.execute(select(GuardrailGuardType).where(GuardrailGuardType.id == guard_id))
    return result.scalar_one_or_none()


async def get_guard_types(db: AsyncSession) -> List[GuardrailGuardType]:
    """Get all guard types."""
    result = await db.execute(select(GuardrailGuardType).order_by(GuardrailGuardType.name))
    return result.scalars().all()


# Rule CRUD operations
async def create_rule(db: AsyncSession, rule_data: GuardrailRuleCreate, created_by: UUID) -> GuardrailRule:
    """Create a new guardrail rule with junction table associations."""
    rule_dict = rule_data.model_dump(exclude={"scanner_type_ids", "modality_type_ids", "guard_type_ids"})
    rule = GuardrailRule(**rule_dict)
    db.add(rule)
    await db.flush()  # Flush to get the ID

    # Create scanner associations
    for scanner_type_id in rule_data.scanner_type_ids:
        scanner_assoc = GuardrailRuleScanner(rule_id=rule.id, scanner_type_id=scanner_type_id)
        db.add(scanner_assoc)

    # Create modality associations
    for modality_type_id in rule_data.modality_type_ids:
        modality_assoc = GuardrailRuleModality(rule_id=rule.id, modality_type_id=modality_type_id)
        db.add(modality_assoc)

    # Create guard type associations
    for guard_type_id in rule_data.guard_type_ids:
        guard_assoc = GuardrailRuleGuardType(rule_id=rule.id, guard_type_id=guard_type_id)
        db.add(guard_assoc)

    await db.commit()
    await db.refresh(rule)
    return rule


async def get_rule(db: AsyncSession, rule_id: UUID) -> Optional[GuardrailRule]:
    """Get a rule by ID."""
    result = await db.execute(
        select(GuardrailRule)
        .options(
            joinedload(GuardrailRule.probe),
            selectinload(GuardrailRule.scanner_associations).selectinload(GuardrailRuleScanner.scanner_type),
            selectinload(GuardrailRule.modality_associations).selectinload(GuardrailRuleModality.modality_type),
            selectinload(GuardrailRule.guard_type_associations).selectinload(GuardrailRuleGuardType.guard_type),
        )
        .where(GuardrailRule.id == rule_id)
    )
    return result.scalar_one_or_none()


async def get_rules_by_probe(db: AsyncSession, probe_id: UUID) -> List[GuardrailRule]:
    """Get all rules for a probe."""
    result = await db.execute(
        select(GuardrailRule).where(GuardrailRule.probe_id == probe_id).order_by(GuardrailRule.name)
    )
    return result.scalars().all()


async def update_rule(db: AsyncSession, rule_id: UUID, rule_data: GuardrailRuleUpdate) -> Optional[GuardrailRule]:
    """Update a rule with junction table associations."""
    rule = await get_rule(db, rule_id)
    if not rule:
        return None

    update_dict = rule_data.model_dump(
        exclude_unset=True, exclude={"scanner_type_ids", "modality_type_ids", "guard_type_ids"}
    )
    for field, value in update_dict.items():
        setattr(rule, field, value)

    # Update scanner associations if provided
    if rule_data.scanner_type_ids is not None:
        # Delete existing associations
        await db.execute(delete(GuardrailRuleScanner).where(GuardrailRuleScanner.rule_id == rule_id))

        # Create new associations
        for scanner_type_id in rule_data.scanner_type_ids:
            scanner_assoc = GuardrailRuleScanner(rule_id=rule.id, scanner_type_id=scanner_type_id)
            db.add(scanner_assoc)

    # Update modality associations if provided
    if rule_data.modality_type_ids is not None:
        # Delete existing associations
        await db.execute(delete(GuardrailRuleModality).where(GuardrailRuleModality.rule_id == rule_id))

        # Create new associations
        for modality_type_id in rule_data.modality_type_ids:
            modality_assoc = GuardrailRuleModality(rule_id=rule.id, modality_type_id=modality_type_id)
            db.add(modality_assoc)

    # Update guard type associations if provided
    if rule_data.guard_type_ids is not None:
        # Delete existing associations
        await db.execute(delete(GuardrailRuleGuardType).where(GuardrailRuleGuardType.rule_id == rule_id))

        # Create new associations
        for guard_type_id in rule_data.guard_type_ids:
            guard_assoc = GuardrailRuleGuardType(rule_id=rule.id, guard_type_id=guard_type_id)
            db.add(guard_assoc)

    await db.commit()
    await db.refresh(rule)
    return rule


async def delete_rule(db: AsyncSession, rule_id: UUID) -> bool:
    """Delete a rule."""
    rule = await get_rule(db, rule_id)
    if not rule:
        return False

    await db.delete(rule)
    await db.commit()
    return True


# Probe CRUD operations
async def create_probe(db: AsyncSession, probe_data: GuardrailProbeCreate, created_by: UUID) -> GuardrailProbe:
    """Create a new guardrail probe."""
    probe_dict = probe_data.model_dump()
    probe_dict["created_by"] = created_by
    probe = GuardrailProbe(**probe_dict)
    db.add(probe)
    await db.commit()
    await db.refresh(probe)
    return probe


async def get_probe(db: AsyncSession, probe_id: UUID) -> Optional[GuardrailProbe]:
    """Get a probe by ID with rules."""
    result = await db.execute(
        select(GuardrailProbe)
        .options(
            selectinload(GuardrailProbe.provider),
            selectinload(GuardrailProbe.rules)
            .selectinload(GuardrailRule.scanner_associations)
            .selectinload(GuardrailRuleScanner.scanner_type),
            selectinload(GuardrailProbe.rules)
            .selectinload(GuardrailRule.modality_associations)
            .selectinload(GuardrailRuleModality.modality_type),
            selectinload(GuardrailProbe.rules)
            .selectinload(GuardrailRule.guard_type_associations)
            .selectinload(GuardrailRuleGuardType.guard_type),
        )
        .where(GuardrailProbe.id == probe_id)
    )
    return result.scalar_one_or_none()


async def get_probes(
    db: AsyncSession, filters: GuardrailProbeListRequestSchema, user_id: UUID
) -> Tuple[List[GuardrailProbe], int]:
    """Get probes with filtering and pagination."""
    query = select(GuardrailProbe).options(
        selectinload(GuardrailProbe.provider),
        selectinload(GuardrailProbe.rules)
        .selectinload(GuardrailRule.scanner_associations)
        .selectinload(GuardrailRuleScanner.scanner_type),
        selectinload(GuardrailProbe.rules)
        .selectinload(GuardrailRule.modality_associations)
        .selectinload(GuardrailRuleModality.modality_type),
        selectinload(GuardrailProbe.rules)
        .selectinload(GuardrailRule.guard_type_associations)
        .selectinload(GuardrailRuleGuardType.guard_type),
    )
    count_query = select(func.count(GuardrailProbe.id))

    # Apply filters
    conditions = []

    # Provider filter
    if filters.provider_id:
        conditions.append(GuardrailProbe.provider_id == filters.provider_id)
    elif filters.provider_type:
        query = query.join(GuardrailProvider)
        count_query = count_query.join(GuardrailProvider)
        conditions.append(GuardrailProvider.provider_type == filters.provider_type)

    # Tags filter - using JSONB contains for exact tag name matching
    if filters.tags:
        # Create OR condition to match any of the provided tag names
        tag_conditions = []
        for tag_name in filters.tags:
            tag_conditions.append(GuardrailProbe.tags.cast(JSONB).contains([{"name": tag_name}]))
        conditions.append(or_(*tag_conditions))

    # User/project/endpoint filters
    if filters.user_id:
        conditions.append(GuardrailProbe.user_id == filters.user_id)
    elif filters.project_id:
        conditions.append(GuardrailProbe.project_id == filters.project_id)
    elif filters.endpoint_id:
        # For endpoint filter, we need to join with deployments
        from budapp.guardrails.models import GuardrailDeployment, GuardrailDeploymentProbe

        query = query.join(GuardrailDeploymentProbe).join(GuardrailDeployment)
        count_query = count_query.join(GuardrailDeploymentProbe).join(GuardrailDeployment)
        conditions.append(GuardrailDeployment.endpoint_id == filters.endpoint_id)
    else:
        # Default: show only non-custom probes (provider_type != CUSTOM)
        query = query.join(GuardrailProvider)
        count_query = count_query.join(GuardrailProvider)
        conditions.append(GuardrailProvider.provider_type != GuardrailProviderEnum.CUSTOM)

    # Search filter
    if filters.search:
        search_term = f"%{filters.search}%"
        conditions.append(or_(GuardrailProbe.name.ilike(search_term), GuardrailProbe.description.ilike(search_term)))

    # Apply all conditions
    if conditions:
        query = query.where(and_(*conditions))
        count_query = count_query.where(and_(*conditions))

    # Get total count
    count_result = await db.execute(count_query)
    total = count_result.scalar()

    # Apply pagination and ordering
    query = query.order_by(GuardrailProbe.name)
    query = query.offset((filters.page - 1) * filters.page_size).limit(filters.page_size)

    # Execute query
    result = await db.execute(query)
    probes = result.scalars().all()

    return probes, total


async def update_probe(
    db: AsyncSession, probe_id: UUID, probe_data: GuardrailProbeUpdate, user_id: UUID
) -> Optional[GuardrailProbe]:
    """Update a probe (only if user owns it)."""
    probe = await get_probe(db, probe_id)
    if not probe:
        return None

    # Check ownership (non-custom probes can't be updated, user must own custom probes)
    if not probe.is_custom or (probe.is_custom and probe.user_id != user_id):
        return None

    for field, value in probe_data.model_dump(exclude_unset=True).items():
        setattr(probe, field, value)

    await db.commit()
    await db.refresh(probe)
    return probe


async def delete_probe(db: AsyncSession, probe_id: UUID, user_id: UUID) -> bool:
    """Delete a probe (only if user owns it)."""
    probe = await get_probe(db, probe_id)
    if not probe:
        return False

    # Check ownership
    if not probe.is_custom or (probe.is_custom and probe.user_id != user_id):
        return False

    await db.delete(probe)
    await db.commit()
    return True


# Deployment CRUD operations
async def create_deployment(
    db: AsyncSession, deployment_data: GuardrailDeploymentCreate, user_id: UUID
) -> GuardrailDeployment:
    """Create a new guardrail deployment with probes."""
    # Create deployment
    deployment_dict = deployment_data.model_dump(exclude={"probes"})
    deployment_dict["user_id"] = user_id
    deployment = GuardrailDeployment(**deployment_dict)
    db.add(deployment)
    await db.flush()  # Flush to get the ID

    # Create probe associations
    for probe_data in deployment_data.probes:
        deployment_probe = await _create_deployment_probe(db, deployment.id, probe_data)
        deployment.probe_associations.append(deployment_probe)

    await db.commit()
    await db.refresh(deployment)
    return deployment


async def _create_deployment_probe(
    db: AsyncSession, deployment_id: UUID, probe_data: GuardrailDeploymentProbeCreate
) -> GuardrailDeploymentProbe:
    """Create a deployment-probe association with rule configs."""
    # Create deployment-probe association
    deployment_probe_dict = probe_data.model_dump(exclude={"rule_configs"})
    deployment_probe_dict["deployment_id"] = deployment_id
    deployment_probe = GuardrailDeploymentProbe(**deployment_probe_dict)
    db.add(deployment_probe)
    await db.flush()  # Flush to get the ID

    # Create rule configurations if provided
    if probe_data.rule_configs:
        for rule_config_data in probe_data.rule_configs:
            rule_config_dict = rule_config_data.model_dump()
            rule_config_dict["deployment_probe_id"] = deployment_probe.id
            rule_config = GuardrailDeploymentRuleConfig(**rule_config_dict)
            db.add(rule_config)

    return deployment_probe


async def get_deployment(db: AsyncSession, deployment_id: UUID) -> Optional[GuardrailDeployment]:
    """Get a deployment by ID with all related data."""
    result = await db.execute(
        select(GuardrailDeployment)
        .options(
            selectinload(GuardrailDeployment.probe_associations).selectinload(GuardrailDeploymentProbe.probe),
            selectinload(GuardrailDeployment.probe_associations)
            .selectinload(GuardrailDeploymentProbe.rule_configs)
            .selectinload(GuardrailDeploymentRuleConfig.rule),
        )
        .where(GuardrailDeployment.id == deployment_id)
    )
    return result.scalar_one_or_none()


async def get_deployments(
    db: AsyncSession, filters: GuardrailDeploymentListRequestSchema, user_id: UUID
) -> Tuple[List[GuardrailDeployment], int]:
    """Get deployments with filtering and pagination."""
    query = select(GuardrailDeployment)
    count_query = select(func.count(GuardrailDeployment.id))

    # Apply filters
    conditions = [
        GuardrailDeployment.user_id == user_id,  # User can only see their deployments
        GuardrailDeployment.status != GuardrailDeploymentStatusEnum.DELETED,  # Exclude deleted deployments
    ]

    if filters.project_id:
        conditions.append(GuardrailDeployment.project_id == filters.project_id)

    if filters.endpoint_id:
        conditions.append(GuardrailDeployment.endpoint_id == filters.endpoint_id)

    if filters.deployment_type:
        conditions.append(GuardrailDeployment.deployment_type == filters.deployment_type)

    if filters.status:
        conditions.append(GuardrailDeployment.status == filters.status)

    if filters.search:
        search_term = f"%{filters.search}%"
        conditions.append(
            or_(GuardrailDeployment.name.ilike(search_term), GuardrailDeployment.description.ilike(search_term))
        )

    # Apply conditions
    query = query.where(and_(*conditions))
    count_query = count_query.where(and_(*conditions))

    # Get total count
    count_result = await db.execute(count_query)
    total = count_result.scalar()

    # Apply pagination and ordering
    query = query.order_by(GuardrailDeployment.created_at.desc())
    query = query.offset((filters.page - 1) * filters.page_size).limit(filters.page_size)

    # Load probe associations for counting
    query = query.options(selectinload(GuardrailDeployment.probe_associations))

    # Execute query
    result = await db.execute(query)
    deployments = result.scalars().all()

    return deployments, total


async def update_deployment(
    db: AsyncSession, deployment_id: UUID, deployment_data: GuardrailDeploymentUpdate, user_id: UUID
) -> Optional[GuardrailDeployment]:
    """Update a deployment."""
    deployment = await get_deployment(db, deployment_id)
    if not deployment or deployment.user_id != user_id:
        return None

    update_dict = deployment_data.model_dump(exclude_unset=True, exclude={"probes"})

    # Update basic fields
    for field, value in update_dict.items():
        setattr(deployment, field, value)

    # Update probe associations if provided
    if deployment_data.probes is not None:
        # Delete existing associations
        for existing_probe in deployment.probe_associations:
            await db.delete(existing_probe)

        # Create new associations
        deployment.probe_associations = []
        for probe_data in deployment_data.probes:
            deployment_probe = await _create_deployment_probe(db, deployment.id, probe_data)
            deployment.probe_associations.append(deployment_probe)

    await db.commit()
    await db.refresh(deployment)
    return deployment


async def delete_deployment(db: AsyncSession, deployment_id: UUID, user_id: UUID) -> bool:
    """Delete a deployment (soft delete by updating status)."""
    deployment = await get_deployment(db, deployment_id)
    if not deployment or deployment.user_id != user_id:
        return False

    # Soft delete: update status to DELETED instead of removing the row
    deployment.status = GuardrailDeploymentStatusEnum.DELETED
    await db.commit()
    return True


async def get_deployments_by_endpoint(db: AsyncSession, endpoint_id: UUID, user_id: UUID) -> List[GuardrailDeployment]:
    """Get all deployments for a specific endpoint."""
    result = await db.execute(
        select(GuardrailDeployment)
        .where(
            and_(
                GuardrailDeployment.endpoint_id == endpoint_id,
                GuardrailDeployment.user_id == user_id,
                GuardrailDeployment.status == GuardrailDeploymentStatusEnum.ACTIVE,
            )
        )
        .options(
            selectinload(GuardrailDeployment.probe_associations).selectinload(GuardrailDeploymentProbe.probe),
            selectinload(GuardrailDeployment.probe_associations)
            .selectinload(GuardrailDeploymentProbe.rule_configs)
            .selectinload(GuardrailDeploymentRuleConfig.rule),
        )
    )
    return result.scalars().all()


async def get_deployments_by_project(db: AsyncSession, project_id: UUID, user_id: UUID) -> List[GuardrailDeployment]:
    """Get all deployments for a specific project."""
    result = await db.execute(
        select(GuardrailDeployment)
        .where(
            and_(
                GuardrailDeployment.project_id == project_id,
                GuardrailDeployment.user_id == user_id,
                GuardrailDeployment.status == GuardrailDeploymentStatusEnum.ACTIVE,
            )
        )
        .options(
            selectinload(GuardrailDeployment.probe_associations).selectinload(GuardrailDeploymentProbe.probe),
            selectinload(GuardrailDeployment.probe_associations)
            .selectinload(GuardrailDeploymentProbe.rule_configs)
            .selectinload(GuardrailDeploymentRuleConfig.rule),
        )
    )
    return result.scalars().all()
