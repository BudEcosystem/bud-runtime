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

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from budapp.commons.dependencies import get_current_user, get_session
from budapp.commons.schemas import SingleResponse, SuccessResponse
from budapp.guardrails import crud
from budapp.guardrails.schemas import (
    CreateGuardrailDeploymentWorkflowRequest,
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
    GuardrailRuleListRequestSchema,
    GuardrailRuleListResponseSchema,
    GuardrailRuleResponse,
    GuardrailRuleUpdate,
    GuardrailScannerTypeCreate,
    GuardrailScannerTypeResponse,
    ProbeTagSearchResponse,
)
from budapp.guardrails.services import (
    GuardrailDeploymentService,
    GuardrailDeploymentWorkflowService,
    GuardrailProbeService,
    GuardrailRuleService,
)
from budapp.user_ops.models import User
from budapp.workflow_ops.schemas import RetrieveWorkflowDataResponse
from budapp.workflow_ops.services import WorkflowService


router = APIRouter(prefix="/guardrails", tags=["Guardrails"])


# Provider endpoints
@router.post(
    "/providers",
    response_model=GuardrailProviderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_provider(
    provider_data: GuardrailProviderCreate,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Create a new guardrail provider."""
    provider = await crud.create_provider(db, provider_data, current_user.id)
    return GuardrailProviderResponse.model_validate(provider)


@router.get(
    "/providers",
    response_model=SingleResponse[List[GuardrailProviderResponse]],
)
async def get_providers(
    include_inactive: bool = Query(False, description="Include inactive providers"),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get all guardrail providers."""
    providers = await crud.get_providers(db, include_inactive)
    provider_responses = [GuardrailProviderResponse.model_validate(provider) for provider in providers]
    return SingleResponse(success=True, result=provider_responses, message="Providers retrieved successfully")


@router.get(
    "/providers/{provider_id}",
    response_model=GuardrailProviderResponse,
)
async def get_provider(
    provider_id: UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get a specific provider by ID."""
    provider = await crud.get_provider(db, provider_id)
    if not provider:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    return GuardrailProviderResponse.model_validate(provider)


@router.put(
    "/providers/{provider_id}",
    response_model=GuardrailProviderResponse,
)
async def update_provider(
    provider_id: UUID,
    provider_data: GuardrailProviderUpdate,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Update a provider (only custom providers can be updated by their owner)."""
    provider = await crud.update_provider(db, provider_id, provider_data, current_user.id)
    if not provider:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot update this provider")
    return GuardrailProviderResponse.model_validate(provider)


@router.delete(
    "/providers/{provider_id}",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_provider(
    provider_id: UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Delete a provider (only custom providers can be deleted by their owner)."""
    if not await crud.delete_provider(db, provider_id, current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot delete this provider")
    return None


@router.post(
    "/scanner-types",
    response_model=GuardrailScannerTypeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_scanner_type(
    scanner_data: GuardrailScannerTypeCreate,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Create a new scanner type."""
    scanner = await crud.create_scanner_type(db, scanner_data)
    return GuardrailScannerTypeResponse.model_validate(scanner)


@router.get(
    "/scanner-types",
    response_model=SingleResponse[List[GuardrailScannerTypeResponse]],
)
async def get_scanner_types(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get all scanner types."""
    scanners = await crud.get_scanner_types(db)
    scanner_responses = [GuardrailScannerTypeResponse.model_validate(scanner) for scanner in scanners]
    return SingleResponse(success=True, result=scanner_responses, message="Scanner types retrieved successfully")


# Modality type endpoints
@router.post(
    "/modality-types",
    response_model=GuardrailModalityTypeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_modality_type(
    modality_data: GuardrailModalityTypeCreate,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Create a new modality type."""
    modality = await crud.create_modality_type(db, modality_data)
    return GuardrailModalityTypeResponse.model_validate(modality)


@router.get(
    "/modality-types",
    response_model=SingleResponse[List[GuardrailModalityTypeResponse]],
)
async def get_modality_types(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get all modality types."""
    modalities = await crud.get_modality_types(db)
    modality_responses = [GuardrailModalityTypeResponse.model_validate(modality) for modality in modalities]
    return SingleResponse(success=True, result=modality_responses, message="Modality types retrieved successfully")


# Guard type endpoints
@router.post(
    "/guard-types",
    response_model=GuardrailGuardTypeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_guard_type(
    guard_data: GuardrailGuardTypeCreate,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Create a new guard type."""
    guard = await crud.create_guard_type(db, guard_data)
    return GuardrailGuardTypeResponse.model_validate(guard)


@router.get(
    "/guard-types",
    response_model=SingleResponse[List[GuardrailGuardTypeResponse]],
)
async def get_guard_types(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get all guard types."""
    guards = await crud.get_guard_types(db)
    guard_responses = [GuardrailGuardTypeResponse.model_validate(guard) for guard in guards]
    return SingleResponse(success=True, result=guard_responses, message="Guard types retrieved successfully")


# Probe endpoints
@router.post(
    "/probes",
    response_model=GuardrailProbeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_probe(
    probe_data: GuardrailProbeCreate,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Create a new guardrail probe."""
    probe = await GuardrailProbeService.create_probe(db, probe_data, current_user.id)
    return probe


@router.get(
    "/probes",
    response_model=GuardrailProbeListResponseSchema,
)
async def get_probes(
    tags: List[str] = Query(None),
    provider_id: UUID = Query(None),
    provider_type: str = Query(None),
    user_id: UUID = Query(None),
    project_id: UUID = Query(None),
    endpoint_id: UUID = Query(None),
    search: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_session),
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
        page=page,
        page_size=page_size,
    )

    probes, total = await GuardrailProbeService.get_probes(db, filters, current_user.id)

    response = GuardrailProbeListResponseSchema(
        probes=probes,
        total=total,
        page=page,
        page_size=page_size,
    )

    return response


@router.get(
    "/probes/{probe_id}",
    response_model=GuardrailProbeResponse,
)
async def get_probe(
    probe_id: UUID,
    include_rules: bool = Query(True, description="Include rules in the response"),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get detailed probe information."""
    probe = await GuardrailProbeService.get_probe(db, probe_id, current_user.id, include_rules=include_rules)
    return probe


@router.put(
    "/probes/{probe_id}",
    response_model=GuardrailProbeResponse,
)
async def update_probe(
    probe_id: UUID,
    probe_data: GuardrailProbeUpdate,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Update a probe."""
    probe = await GuardrailProbeService.update_probe(db, probe_id, probe_data, current_user.id)
    return probe


@router.delete(
    "/probes/{probe_id}",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_probe(
    probe_id: UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Delete a probe."""
    await GuardrailProbeService.delete_probe(db, probe_id, current_user.id)
    return None


@router.get(
    "/probes/tags/search",
    response_model=SingleResponse[ProbeTagSearchResponse],
)
async def search_probe_tags(
    search_term: str = Query(..., description="Tag name to search for"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=0),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Search for tags used in guardrail probes."""
    offset = (page - 1) * limit
    tags, total_count = await GuardrailProbeService.search_probe_tags(db, search_term, offset, limit)

    response_data = ProbeTagSearchResponse(
        tags=tags,
        total=total_count,
        page=page,
        page_size=limit,
    )

    return SingleResponse(success=True, result=response_data, message="Tags retrieved successfully")


@router.get(
    "/probes/{probe_id}/rules",
    response_model=GuardrailRuleListResponseSchema,
)
async def get_probe_rules(
    probe_id: UUID,
    search: str = Query(None),
    scanner_type_ids: List[UUID] = Query(None),
    modality_type_ids: List[UUID] = Query(None),
    guard_type_ids: List[UUID] = Query(None),
    is_enabled: bool = Query(None),
    is_custom: bool = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get paginated rules for a specific probe."""
    filters = GuardrailRuleListRequestSchema(
        search=search,
        scanner_type_ids=scanner_type_ids,
        modality_type_ids=modality_type_ids,
        guard_type_ids=guard_type_ids,
        is_enabled=is_enabled,
        is_custom=is_custom,
        page=page,
        page_size=page_size,
    )

    rules, total = await GuardrailRuleService.get_rules_paginated(db, probe_id, filters, current_user.id)

    response = GuardrailRuleListResponseSchema(
        rules=rules,
        total=total,
        page=page,
        page_size=page_size,
    )

    return response


# Rule endpoints
@router.post(
    "/rules",
    response_model=GuardrailRuleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_rule(
    rule_data: GuardrailRuleCreate,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Create a new guardrail rule."""
    rule = await GuardrailRuleService.create_rule(db, rule_data, current_user.id)
    return rule


@router.get(
    "/rules/{rule_id}",
    response_model=GuardrailRuleResponse,
)
async def get_rule(
    rule_id: UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get a rule by ID."""
    rule = await GuardrailRuleService.get_rule(db, rule_id, current_user.id)
    return rule


@router.put(
    "/rules/{rule_id}",
    response_model=GuardrailRuleResponse,
)
async def update_rule(
    rule_id: UUID,
    rule_data: GuardrailRuleUpdate,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Update a rule."""
    rule = await GuardrailRuleService.update_rule(db, rule_id, rule_data, current_user.id)
    return rule


@router.delete(
    "/rules/{rule_id}",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_rule(
    rule_id: UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Delete a rule."""
    await GuardrailRuleService.delete_rule(db, rule_id, current_user.id)
    return None


# Deployment endpoints
@router.post(
    "/deployments",
    response_model=GuardrailDeploymentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_deployment(
    deployment_data: GuardrailDeploymentCreate,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Create a new guardrail deployment."""
    deployment = await GuardrailDeploymentService.create_deployment(db, deployment_data, current_user.id)
    return deployment


@router.get(
    "/deployments",
    response_model=GuardrailDeploymentListResponseSchema,
)
async def get_deployments(
    project_id: UUID = Query(None),
    endpoint_id: UUID = Query(None),
    deployment_type: str = Query(None),
    status: str = Query(None),
    search: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get deployments with filtering and pagination."""
    filters = GuardrailDeploymentListRequestSchema(
        project_id=project_id,
        endpoint_id=endpoint_id,
        deployment_type=deployment_type,
        status=status,
        search=search,
        page=page,
        page_size=page_size,
    )

    deployments, total = await GuardrailDeploymentService.get_deployments(db, filters, current_user.id)

    response = GuardrailDeploymentListResponseSchema(
        deployments=deployments,
        total=total,
        page=page,
        page_size=page_size,
    )

    return response


@router.get(
    "/deployments/{deployment_id}",
    response_model=GuardrailDeploymentResponse,
)
async def get_deployment(
    deployment_id: UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get detailed deployment information."""
    deployment = await GuardrailDeploymentService.get_deployment(db, deployment_id, current_user.id)
    return deployment


@router.put(
    "/deployments/{deployment_id}",
    response_model=GuardrailDeploymentResponse,
)
async def update_deployment(
    deployment_id: UUID,
    deployment_data: GuardrailDeploymentUpdate,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Update a deployment."""
    deployment = await GuardrailDeploymentService.update_deployment(
        db, deployment_id, deployment_data, current_user.id
    )
    return deployment


@router.delete(
    "/deployments/{deployment_id}",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_deployment(
    deployment_id: UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Delete a deployment."""
    await GuardrailDeploymentService.delete_deployment(db, deployment_id, current_user.id)
    return None


# Endpoint-specific deployment endpoints
@router.get(
    "/endpoints/{endpoint_id}/deployments",
    response_model=SingleResponse[List[GuardrailDeploymentResponse]],
)
async def get_endpoint_deployments(
    endpoint_id: UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get all active deployments for a specific endpoint."""
    deployments = await GuardrailDeploymentService.get_deployments_by_endpoint(db, endpoint_id, current_user.id)
    return SingleResponse(success=True, result=deployments, message="Endpoint deployments retrieved successfully")


# Project-specific deployment endpoints
@router.get(
    "/projects/{project_id}/deployments",
    response_model=SingleResponse[List[GuardrailDeploymentResponse]],
)
async def get_project_deployments(
    project_id: UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get all active deployments for a specific project."""
    deployments = await GuardrailDeploymentService.get_deployments_by_project(db, project_id, current_user.id)
    return SingleResponse(success=True, result=deployments, message="Project deployments retrieved successfully")


# Workflow routes
@router.post(
    "/deployment-workflow",
    response_model=RetrieveWorkflowDataResponse,
    status_code=status.HTTP_200_OK,
)
async def create_or_update_deployment_workflow(
    request: CreateGuardrailDeploymentWorkflowRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Create or update a guardrail deployment workflow."""
    workflow = await GuardrailDeploymentWorkflowService(db).create_guardrail_deployment_workflow(
        current_user.id, request
    )
    workflow_data = await WorkflowService(db).retrieve_workflow_data(workflow.id)
    return workflow_data


@router.get(
    "/deployment-workflow/{workflow_id}",
    response_model=RetrieveWorkflowDataResponse,
)
async def get_deployment_workflow(
    workflow_id: UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get guardrail deployment workflow status and data."""
    workflow_data = await WorkflowService(db).retrieve_workflow_data(workflow_id)
    return workflow_data


@router.post(
    "/deployment-workflow/{workflow_id}/complete",
    response_model=GuardrailDeploymentResponse,
)
async def complete_deployment_workflow(
    workflow_id: UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Complete the workflow and create the guardrail deployment."""
    deployment = await GuardrailDeploymentWorkflowService(db).complete_workflow_and_deploy(
        workflow_id, current_user.id
    )

    # Get full deployment details
    deployment_response = await GuardrailDeploymentService.get_deployment(db, deployment.id, current_user.id)
    return deployment_response


@router.delete(
    "/deployment-workflow/{workflow_id}",
    response_model=SuccessResponse,
)
async def delete_deployment_workflow(
    workflow_id: UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Cancel and delete a guardrail deployment workflow."""
    success_message = await WorkflowService(db).delete_workflow(workflow_id, current_user.id)
    return SuccessResponse(
        code=status.HTTP_200_OK,
        object="workflow.delete",
        message=success_message,
    )
