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

"""API routes for guardrail operations."""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from budapp.auth.models import User
from budapp.commons.database import get_db
from budapp.commons.dependencies import get_current_user
from budapp.commons.exceptions import ForbiddenException, NotFoundException
from budapp.commons.schemas import APIResponseSchema, PaginationQuery
from budapp.guardrails import crud
from budapp.guardrails.schemas import (
    GuardrailDeploymentCreate,
    GuardrailDeploymentListRequestSchema,
    GuardrailDeploymentListResponseSchema,
    GuardrailDeploymentResponse,
    GuardrailDeploymentUpdate,
    GuardrailGuardTypeCreate,
    GuardrailGuardTypeResponse,
    GuardrailModalityTypeCreate,
    GuardrailModalityTypeResponse,
    GuardrailProbeCreate,
    GuardrailProbeListRequestSchema,
    GuardrailProbeListResponseSchema,
    GuardrailProbeResponse,
    GuardrailProbeUpdate,
    GuardrailProviderCreate,
    GuardrailProviderResponse,
    GuardrailProviderUpdate,
    GuardrailRuleCreate,
    GuardrailRuleResponse,
    GuardrailRuleUpdate,
    GuardrailScannerTypeCreate,
    GuardrailScannerTypeResponse,
)
from budapp.guardrails.services import (
    GuardrailDeploymentService,
    GuardrailProbeService,
    GuardrailRuleService,
)


router = APIRouter(prefix="/guardrails", tags=["Guardrails"])


# Provider endpoints
@router.post(
    "/providers",
    response_model=APIResponseSchema[GuardrailProviderResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_provider(
    provider_data: GuardrailProviderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new guardrail provider."""
    provider = await crud.create_provider(db, provider_data, current_user.id)
    return APIResponseSchema(data=GuardrailProviderResponse.model_validate(provider))


@router.get(
    "/providers",
    response_model=APIResponseSchema[List[GuardrailProviderResponse]],
)
async def get_providers(
    include_inactive: bool = Query(False, description="Include inactive providers"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all guardrail providers."""
    providers = await crud.get_providers(db, include_inactive)
    provider_responses = [GuardrailProviderResponse.model_validate(provider) for provider in providers]
    return APIResponseSchema(data=provider_responses)


@router.get(
    "/providers/{provider_id}",
    response_model=APIResponseSchema[GuardrailProviderResponse],
)
async def get_provider(
    provider_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific provider by ID."""
    provider = await crud.get_provider(db, provider_id)
    if not provider:
        raise NotFoundException("Provider not found")
    return APIResponseSchema(data=GuardrailProviderResponse.model_validate(provider))


@router.put(
    "/providers/{provider_id}",
    response_model=APIResponseSchema[GuardrailProviderResponse],
)
async def update_provider(
    provider_id: UUID,
    provider_data: GuardrailProviderUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a provider (only custom providers can be updated by their owner)."""
    provider = await crud.update_provider(db, provider_id, provider_data, current_user.id)
    if not provider:
        raise ForbiddenException("Cannot update this provider")
    return APIResponseSchema(data=GuardrailProviderResponse.model_validate(provider))


@router.delete(
    "/providers/{provider_id}",
    response_model=APIResponseSchema,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_provider(
    provider_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a provider (only custom providers can be deleted by their owner)."""
    if not await crud.delete_provider(db, provider_id, current_user.id):
        raise ForbiddenException("Cannot delete this provider")
    return APIResponseSchema(data=None)


@router.post(
    "/scanner-types",
    response_model=APIResponseSchema[GuardrailScannerTypeResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_scanner_type(
    scanner_data: GuardrailScannerTypeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new scanner type."""
    scanner = await crud.create_scanner_type(db, scanner_data)
    return APIResponseSchema(data=GuardrailScannerTypeResponse.model_validate(scanner))


@router.get(
    "/scanner-types",
    response_model=APIResponseSchema[List[GuardrailScannerTypeResponse]],
)
async def get_scanner_types(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all scanner types."""
    scanners = await crud.get_scanner_types(db)
    scanner_responses = [GuardrailScannerTypeResponse.model_validate(scanner) for scanner in scanners]
    return APIResponseSchema(data=scanner_responses)


# Modality type endpoints
@router.post(
    "/modality-types",
    response_model=APIResponseSchema[GuardrailModalityTypeResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_modality_type(
    modality_data: GuardrailModalityTypeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new modality type."""
    modality = await crud.create_modality_type(db, modality_data)
    return APIResponseSchema(data=GuardrailModalityTypeResponse.model_validate(modality))


@router.get(
    "/modality-types",
    response_model=APIResponseSchema[List[GuardrailModalityTypeResponse]],
)
async def get_modality_types(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all modality types."""
    modalities = await crud.get_modality_types(db)
    modality_responses = [GuardrailModalityTypeResponse.model_validate(modality) for modality in modalities]
    return APIResponseSchema(data=modality_responses)


# Guard type endpoints
@router.post(
    "/guard-types",
    response_model=APIResponseSchema[GuardrailGuardTypeResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_guard_type(
    guard_data: GuardrailGuardTypeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new guard type."""
    guard = await crud.create_guard_type(db, guard_data)
    return APIResponseSchema(data=GuardrailGuardTypeResponse.model_validate(guard))


@router.get(
    "/guard-types",
    response_model=APIResponseSchema[List[GuardrailGuardTypeResponse]],
)
async def get_guard_types(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all guard types."""
    guards = await crud.get_guard_types(db)
    guard_responses = [GuardrailGuardTypeResponse.model_validate(guard) for guard in guards]
    return APIResponseSchema(data=guard_responses)


# Probe endpoints
@router.post(
    "/probes",
    response_model=APIResponseSchema[GuardrailProbeResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_probe(
    probe_data: GuardrailProbeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new guardrail probe."""
    probe = await GuardrailProbeService.create_probe(db, probe_data, current_user.id)
    return APIResponseSchema(data=probe)


@router.get(
    "/probes",
    response_model=APIResponseSchema[GuardrailProbeListResponseSchema],
)
async def get_probes(
    tags: List[str] = Query(None),
    provider_id: UUID = Query(None),
    provider_type: str = Query(None),
    user_id: UUID = Query(None),
    project_id: UUID = Query(None),
    endpoint_id: UUID = Query(None),
    search: str = Query(None),
    pagination: PaginationQuery = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get probes with filtering and pagination."""
    filters = GuardrailProbeListRequestSchema(
        tags=tags,
        provider_id=provider_id,
        provider_type=provider_type,
        user_id=user_id,
        project_id=project_id,
        endpoint_id=endpoint_id,
        search=search,
        page=pagination.page,
        page_size=pagination.page_size,
    )

    probes, total = await GuardrailProbeService.get_probes(db, filters, current_user.id)

    response = GuardrailProbeListResponseSchema(
        probes=probes,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )

    return APIResponseSchema(data=response)


@router.get(
    "/probes/{probe_id}",
    response_model=APIResponseSchema[GuardrailProbeResponse],
)
async def get_probe(
    probe_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get detailed probe information."""
    probe = await GuardrailProbeService.get_probe(db, probe_id, current_user.id)
    return APIResponseSchema(data=probe)


@router.put(
    "/probes/{probe_id}",
    response_model=APIResponseSchema[GuardrailProbeResponse],
)
async def update_probe(
    probe_id: UUID,
    probe_data: GuardrailProbeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a probe."""
    probe = await GuardrailProbeService.update_probe(db, probe_id, probe_data, current_user.id)
    return APIResponseSchema(data=probe)


@router.delete(
    "/probes/{probe_id}",
    response_model=APIResponseSchema,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_probe(
    probe_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a probe."""
    await GuardrailProbeService.delete_probe(db, probe_id, current_user.id)
    return APIResponseSchema(data=None)


@router.get(
    "/probes/tags/search",
    response_model=APIResponseSchema,
)
async def search_probe_tags(
    search_term: str = Query(..., description="Tag name to search for"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Search for tags used in guardrail probes."""
    offset = (page - 1) * limit
    tags, total_count = await GuardrailProbeService.search_probe_tags(db, search_term, offset, limit)

    return APIResponseSchema(
        data={
            "tags": tags,
            "total": total_count,
            "page": page,
            "page_size": limit,
        }
    )


# Rule endpoints
@router.post(
    "/rules",
    response_model=APIResponseSchema[GuardrailRuleResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_rule(
    rule_data: GuardrailRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new guardrail rule."""
    rule = await GuardrailRuleService.create_rule(db, rule_data, current_user.id)
    return APIResponseSchema(data=rule)


@router.get(
    "/rules/{rule_id}",
    response_model=APIResponseSchema[GuardrailRuleResponse],
)
async def get_rule(
    rule_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a rule by ID."""
    rule = await GuardrailRuleService.get_rule(db, rule_id, current_user.id)
    return APIResponseSchema(data=rule)


@router.put(
    "/rules/{rule_id}",
    response_model=APIResponseSchema[GuardrailRuleResponse],
)
async def update_rule(
    rule_id: UUID,
    rule_data: GuardrailRuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a rule."""
    rule = await GuardrailRuleService.update_rule(db, rule_id, rule_data, current_user.id)
    return APIResponseSchema(data=rule)


@router.delete(
    "/rules/{rule_id}",
    response_model=APIResponseSchema,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_rule(
    rule_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a rule."""
    await GuardrailRuleService.delete_rule(db, rule_id, current_user.id)
    return APIResponseSchema(data=None)


# Deployment endpoints
@router.post(
    "/deployments",
    response_model=APIResponseSchema[GuardrailDeploymentResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_deployment(
    deployment_data: GuardrailDeploymentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new guardrail deployment."""
    deployment = await GuardrailDeploymentService.create_deployment(db, deployment_data, current_user.id)
    return APIResponseSchema(data=deployment)


@router.get(
    "/deployments",
    response_model=APIResponseSchema[GuardrailDeploymentListResponseSchema],
)
async def get_deployments(
    project_id: UUID = Query(None),
    endpoint_id: UUID = Query(None),
    deployment_type: str = Query(None),
    status: str = Query(None),
    search: str = Query(None),
    pagination: PaginationQuery = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get deployments with filtering and pagination."""
    filters = GuardrailDeploymentListRequestSchema(
        project_id=project_id,
        endpoint_id=endpoint_id,
        deployment_type=deployment_type,
        status=status,
        search=search,
        page=pagination.page,
        page_size=pagination.page_size,
    )

    deployments, total = await GuardrailDeploymentService.get_deployments(db, filters, current_user.id)

    response = GuardrailDeploymentListResponseSchema(
        deployments=deployments,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )

    return APIResponseSchema(data=response)


@router.get(
    "/deployments/{deployment_id}",
    response_model=APIResponseSchema[GuardrailDeploymentResponse],
)
async def get_deployment(
    deployment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get detailed deployment information."""
    deployment = await GuardrailDeploymentService.get_deployment(db, deployment_id, current_user.id)
    return APIResponseSchema(data=deployment)


@router.put(
    "/deployments/{deployment_id}",
    response_model=APIResponseSchema[GuardrailDeploymentResponse],
)
async def update_deployment(
    deployment_id: UUID,
    deployment_data: GuardrailDeploymentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a deployment."""
    deployment = await GuardrailDeploymentService.update_deployment(
        db, deployment_id, deployment_data, current_user.id
    )
    return APIResponseSchema(data=deployment)


@router.delete(
    "/deployments/{deployment_id}",
    response_model=APIResponseSchema,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_deployment(
    deployment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a deployment."""
    await GuardrailDeploymentService.delete_deployment(db, deployment_id, current_user.id)
    return APIResponseSchema(data=None)


# Endpoint-specific deployment endpoints
@router.get(
    "/endpoints/{endpoint_id}/deployments",
    response_model=APIResponseSchema[List[GuardrailDeploymentResponse]],
)
async def get_endpoint_deployments(
    endpoint_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all active deployments for a specific endpoint."""
    deployments = await GuardrailDeploymentService.get_deployments_by_endpoint(db, endpoint_id, current_user.id)
    return APIResponseSchema(data=deployments)


# Project-specific deployment endpoints
@router.get(
    "/projects/{project_id}/deployments",
    response_model=APIResponseSchema[List[GuardrailDeploymentResponse]],
)
async def get_project_deployments(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all active deployments for a specific project."""
    deployments = await GuardrailDeploymentService.get_deployments_by_project(db, project_id, current_user.id)
    return APIResponseSchema(data=deployments)
