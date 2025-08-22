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
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.sql import select

from budapp.commons.constants import GuardrailDeploymentStatusEnum
from budapp.guardrails.models import (
    GuardrailDeployment,
    GuardrailDeploymentProbe,
    GuardrailDeploymentRule,
    GuardrailProbe,
    GuardrailRule,
)
from budapp.guardrails.schemas import (
    GuardrailDeploymentCreate,
    GuardrailDeploymentListRequestSchema,
    GuardrailDeploymentProbeCreate,
    GuardrailDeploymentUpdate,
    GuardrailProbeCreate,
    GuardrailProbeListRequestSchema,
    GuardrailProbeUpdate,
    GuardrailRuleCreate,
    GuardrailRuleListRequestSchema,
    GuardrailRuleUpdate,
)
from budapp.model_ops.models import Provider


# Provider CRUD operations - using Provider model from model_ops
async def get_provider(db: Session, provider_id: UUID) -> Optional[Provider]:
    """Get a provider by ID."""
    result = db.execute(select(Provider).where(Provider.id == provider_id))
    return result.scalar_one_or_none()


async def get_providers(db: Session, include_inactive: bool = False) -> List[Provider]:
    """Get all providers."""
    query = select(Provider).order_by(Provider.name)
    if not include_inactive:
        query = query.where(Provider.is_active.is_(True))
    result = db.execute(query)
    return result.scalars().all()


# Rule CRUD operations
async def create_rule(db: Session, rule_data: GuardrailRuleCreate, created_by: UUID) -> GuardrailRule:
    """Create a new guardrail rule."""
    rule_dict = rule_data.model_dump()
    rule = GuardrailRule(**rule_dict)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


async def get_rule(db: Session, rule_id: UUID) -> Optional[GuardrailRule]:
    """Get a rule by ID."""
    result = db.execute(
        select(GuardrailRule).options(joinedload(GuardrailRule.probe)).where(GuardrailRule.id == rule_id)
    )
    return result.scalar_one_or_none()


async def get_rules_by_probe(db: Session, probe_id: UUID) -> List[GuardrailRule]:
    """Get all rules for a probe."""
    result = db.execute(select(GuardrailRule).where(GuardrailRule.probe_id == probe_id).order_by(GuardrailRule.name))
    return result.scalars().all()


async def update_rule(db: Session, rule_id: UUID, rule_data: GuardrailRuleUpdate) -> Optional[GuardrailRule]:
    """Update a rule."""
    rule = await get_rule(db, rule_id)
    if not rule:
        return None

    update_dict = rule_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(rule, field, value)

    db.commit()
    db.refresh(rule)
    return rule


async def delete_rule(db: Session, rule_id: UUID) -> bool:
    """Delete a rule."""
    rule = await get_rule(db, rule_id)
    if not rule:
        return False

    db.delete(rule)
    db.commit()
    return True


async def get_rules_paginated(
    db: Session, probe_id: UUID, filters: GuardrailRuleListRequestSchema, page: int, page_size: int
) -> Tuple[List[GuardrailRule], int]:
    """Get paginated rules for a probe with filtering."""
    # Base query for rules in the probe
    query = select(GuardrailRule).where(GuardrailRule.probe_id == probe_id)
    count_query = select(func.count(GuardrailRule.id)).where(GuardrailRule.probe_id == probe_id)

    # Apply filters
    conditions = []

    # Search filter
    if filters.search:
        search_term = f"%{filters.search}%"
        conditions.append(or_(GuardrailRule.name.ilike(search_term), GuardrailRule.description.ilike(search_term)))

    # Scanner type filter
    if filters.scanner_types:
        conditions.append(GuardrailRule.scanner_types.contains(filters.scanner_types))

    # Modality type filter
    if filters.modality_types:
        conditions.append(GuardrailRule.modality_types.contains(filters.modality_types))

    # Guard type filter
    if filters.guard_types:
        conditions.append(GuardrailRule.guard_types.contains(filters.guard_types))

    # Enabled filter
    if filters.is_enabled is not None:
        conditions.append(GuardrailRule.is_enabled == filters.is_enabled)

    # Custom filter
    if filters.is_custom is not None:
        conditions.append(GuardrailRule.is_custom == filters.is_custom)

    # Apply all conditions
    if conditions:
        query = query.where(and_(*conditions))
        count_query = count_query.where(and_(*conditions))

    # Get total count
    count_result = db.execute(count_query)
    total = count_result.scalar()

    # Apply pagination and ordering
    query = query.order_by(GuardrailRule.name)
    query = query.offset((page - 1) * page_size).limit(page_size)

    # Execute query
    result = db.execute(query)
    rules = result.scalars().all()

    return rules, total


# Probe CRUD operations
async def create_probe(db: Session, probe_data: GuardrailProbeCreate, created_by: UUID) -> GuardrailProbe:
    """Create a new guardrail probe."""
    probe_dict = probe_data.model_dump()
    probe_dict["created_by"] = created_by

    # Set is_custom to True by default if not specified
    if probe_dict.get("is_custom") is None:
        probe_dict["is_custom"] = True

    probe = GuardrailProbe(**probe_dict)
    db.add(probe)
    db.commit()
    db.refresh(probe)
    return probe


async def get_probe(db: Session, probe_id: UUID) -> Optional[GuardrailProbe]:
    """Get a probe by ID with rules."""
    result = db.execute(
        select(GuardrailProbe)
        .options(selectinload(GuardrailProbe.provider), selectinload(GuardrailProbe.rules))
        .where(GuardrailProbe.id == probe_id)
    )
    return result.scalar_one_or_none()


async def get_probes(
    db: Session, filters: GuardrailProbeListRequestSchema, user_id: UUID, page: int, page_size: int
) -> Tuple[List[GuardrailProbe], int]:
    """Get probes with filtering and pagination."""
    query = select(GuardrailProbe).options(selectinload(GuardrailProbe.provider), selectinload(GuardrailProbe.rules))
    count_query = select(func.count(GuardrailProbe.id))

    # Apply filters
    conditions = []

    # Provider filter
    if filters.provider_id:
        conditions.append(GuardrailProbe.provider_id == filters.provider_id)
    if filters.provider_type:
        conditions.append(GuardrailProbe.provider_type == filters.provider_type)

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
        # Default: show only non-custom probes (provider type != 'custom')
        query = query.join(Provider)
        count_query = count_query.join(Provider)
        # conditions.append(Provider.type != "custom")

    # Search filter
    if filters.search:
        search_term = f"%{filters.search}%"
        conditions.append(or_(GuardrailProbe.name.ilike(search_term), GuardrailProbe.description.ilike(search_term)))

    # Apply all conditions
    if conditions:
        query = query.where(and_(*conditions))
        count_query = count_query.where(and_(*conditions))

    # Get total count
    count_result = db.execute(count_query)
    total = count_result.scalar()

    # Apply pagination and ordering
    query = query.order_by(GuardrailProbe.name)
    query = query.offset((page - 1) * page_size).limit(page_size)

    # Execute query
    result = db.execute(query)
    probes = result.scalars().all()

    return probes, total


async def get_probes_by_provider(db: Session, provider_id: UUID) -> List[GuardrailProbe]:
    """Get all probes for a specific provider."""
    result = db.execute(
        select(GuardrailProbe)
        .where(GuardrailProbe.provider_id == provider_id)
        .options(
            selectinload(GuardrailProbe.provider),
            selectinload(GuardrailProbe.rules),
        )
    )
    return result.scalars().all()


async def update_probe(
    db: Session, probe_id: UUID, probe_data: GuardrailProbeUpdate, user_id: UUID
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

    db.commit()
    db.refresh(probe)
    return probe


async def delete_probe(db: Session, probe_id: UUID, user_id: UUID) -> bool:
    """Delete a probe (only if user owns it)."""
    probe = await get_probe(db, probe_id)
    if not probe:
        return False

    # Check ownership
    if not probe.is_custom or (probe.is_custom and probe.user_id != user_id):
        return False

    db.delete(probe)
    db.commit()
    return True


# Deployment CRUD operations
async def create_deployment(
    db: Session,
    deployment_data: GuardrailDeploymentCreate,
    user_id: UUID,
    probes: Optional[List[GuardrailDeploymentProbeCreate]] = None,
) -> GuardrailDeployment:
    """Create a new guardrail deployment with probes."""
    # Create deployment
    deployment_dict = deployment_data.model_dump(exclude={"probe_selections", "provider_ids"})
    deployment_dict["user_id"] = user_id
    deployment = GuardrailDeployment(**deployment_dict)
    db.add(deployment)
    db.flush()  # Flush to get the ID

    # Create probe associations
    if probes:
        for probe_data in probes:
            deployment_probe = await _create_deployment_probe(db, deployment.id, probe_data)
            deployment.probe_associations.append(deployment_probe)

    db.commit()
    db.refresh(deployment)
    return deployment


async def _create_deployment_probe(
    db: Session, deployment_id: UUID, probe_data: GuardrailDeploymentProbeCreate
) -> GuardrailDeploymentProbe:
    """Create a deployment-probe association with rule configs."""
    # Create deployment-probe association
    deployment_probe_dict = probe_data.model_dump(exclude={"rules"})
    deployment_probe_dict["deployment_id"] = deployment_id
    deployment_probe = GuardrailDeploymentProbe(**deployment_probe_dict)
    db.add(deployment_probe)
    db.flush()  # Flush to get the ID

    # Create rule configurations if provided
    if probe_data.rules:
        for rule_config_data in probe_data.rules:
            rule_config_dict = rule_config_data.model_dump()
            rule_config_dict["deployment_probe_id"] = deployment_probe.id
            rule_config = GuardrailDeploymentRule(**rule_config_dict)
            db.add(rule_config)

    return deployment_probe


async def get_deployment(db: Session, deployment_id: UUID) -> Optional[GuardrailDeployment]:
    """Get a deployment by ID with all related data."""
    result = db.execute(
        select(GuardrailDeployment)
        .options(
            selectinload(GuardrailDeployment.probe_associations).selectinload(GuardrailDeploymentProbe.probe),
            selectinload(GuardrailDeployment.probe_associations)
            .selectinload(GuardrailDeploymentProbe.rule)
            .selectinload(GuardrailDeploymentRule.rule),
        )
        .where(
            and_(
                GuardrailDeployment.id == deployment_id,
                GuardrailDeployment.status != GuardrailDeploymentStatusEnum.DELETED,
            )
        )
    )
    return result.scalar_one_or_none()


async def get_deployments(
    db: Session, filters: GuardrailDeploymentListRequestSchema, user_id: UUID, page: int, page_size: int
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
    count_result = db.execute(count_query)
    total = count_result.scalar()

    # Apply pagination and ordering
    query = query.order_by(GuardrailDeployment.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    # Load probe associations for counting
    query = query.options(selectinload(GuardrailDeployment.probe_associations))

    # Execute query
    result = db.execute(query)
    deployments = result.scalars().all()

    return deployments, total


async def update_deployment(
    db: Session, deployment_id: UUID, deployment_data: GuardrailDeploymentUpdate, user_id: UUID
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
            db.delete(existing_probe)

        # Create new associations
        deployment.probe_associations = []
        for probe_data in deployment_data.probes:
            deployment_probe = await _create_deployment_probe(db, deployment.id, probe_data)
            deployment.probe_associations.append(deployment_probe)

    db.commit()
    db.refresh(deployment)
    return deployment


async def delete_deployment(db: Session, deployment_id: UUID, user_id: UUID) -> bool:
    """Delete a deployment (soft delete by updating status)."""
    deployment = await get_deployment(db, deployment_id)
    if not deployment or deployment.user_id != user_id:
        return False

    # Soft delete: update status to DELETED instead of removing the row
    deployment.status = GuardrailDeploymentStatusEnum.DELETED
    db.commit()
    return True


async def get_deployments_by_endpoint(db: Session, endpoint_id: UUID, user_id: UUID) -> List[GuardrailDeployment]:
    """Get all deployments for a specific endpoint."""
    result = db.execute(
        select(GuardrailDeployment)
        .where(
            and_(
                GuardrailDeployment.endpoint_id == endpoint_id,
                GuardrailDeployment.user_id == user_id,
                GuardrailDeployment.status != GuardrailDeploymentStatusEnum.DELETED,
            )
        )
        .options(
            selectinload(GuardrailDeployment.probe_associations).selectinload(GuardrailDeploymentProbe.probe),
            selectinload(GuardrailDeployment.probe_associations)
            .selectinload(GuardrailDeploymentProbe.rule)
            .selectinload(GuardrailDeploymentRule.rule),
        )
    )
    return result.scalars().all()


async def get_deployments_by_project(db: Session, project_id: UUID, user_id: UUID) -> List[GuardrailDeployment]:
    """Get all deployments for a specific project."""
    result = db.execute(
        select(GuardrailDeployment)
        .where(
            and_(
                GuardrailDeployment.project_id == project_id,
                GuardrailDeployment.user_id == user_id,
                GuardrailDeployment.status != GuardrailDeploymentStatusEnum.DELETED,
            )
        )
        .options(
            selectinload(GuardrailDeployment.probe_associations).selectinload(GuardrailDeploymentProbe.probe),
            selectinload(GuardrailDeployment.probe_associations)
            .selectinload(GuardrailDeploymentProbe.rule)
            .selectinload(GuardrailDeploymentRule.rule),
        )
    )
    return result.scalars().all()
