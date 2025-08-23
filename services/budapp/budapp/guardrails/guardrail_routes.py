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
from budapp.commons.schemas import SuccessResponse
from budapp.guardrails import crud
from budapp.guardrails.schemas import (
    CreateGuardrailDeploymentWorkflowRequest,
    GuardrailDeploymentCreate,
    GuardrailDeploymentListRequestSchema,
    GuardrailDeploymentListResponseSchema,
    GuardrailDeploymentResponse,
    GuardrailDeploymentUpdate,
    GuardrailProbeCreate,
    GuardrailProbeListRequestSchema,
    GuardrailProbeListResponseSchema,
    GuardrailProbeResponse,
    GuardrailProbeUpdate,
    GuardrailRuleCreate,
    GuardrailRuleListRequestSchema,
    GuardrailRuleListResponseSchema,
    GuardrailRuleResponse,
    GuardrailRuleUpdate,
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
    )

    probes, total = await GuardrailProbeService.get_probes(db, filters, current_user.id, page, page_size)

    response = GuardrailProbeListResponseSchema(
        probes=probes,
        total_record=total,
        page=page,
        limit=page_size,
        message="Successfully retrieved probes",
    )

    return response


@router.get(
    "/probes/{probe_id}",
    response_model=GuardrailProbeResponse,
)
async def get_probe(
    probe_id: UUID,
    include_rules: bool = Query(False, description="Include rules in the response"),
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
    response_model=ProbeTagSearchResponse,
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

    response = ProbeTagSearchResponse(
        tags=tags,
        total_record=total_count,
        page=page,
        limit=limit,
        message="Tags retrieved successfully",
    )

    return response


@router.get(
    "/probes/{probe_id}/rules",
    response_model=GuardrailRuleListResponseSchema,
)
async def get_probe_rules(
    probe_id: UUID,
    search: str = Query(None),
    scanner_types: List[str] = Query(None),
    modality_types: List[str] = Query(None),
    guard_types: List[str] = Query(None),
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
        scanner_types=scanner_types,
        modality_types=modality_types,
        guard_types=guard_types,
        is_enabled=is_enabled,
        is_custom=is_custom,
    )

    rules, total = await GuardrailRuleService.get_rules_paginated(
        db, probe_id, filters, current_user.id, page, page_size
    )

    response = GuardrailRuleListResponseSchema(
        rules=rules,
        total_record=total,
        page=page,
        limit=page_size,
        message="Successfully retrieved probe rules",
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
    )

    deployments, total = await GuardrailDeploymentService.get_deployments(
        db, filters, current_user.id, page, page_size
    )

    response = GuardrailDeploymentListResponseSchema(
        deployments=deployments,
        total_record=total,
        page=page,
        limit=page_size,
        message="Successfully retrieved deployments",
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
    response_model=GuardrailDeploymentListResponseSchema,
)
async def get_endpoint_deployments(
    endpoint_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get all active deployments for a specific endpoint."""
    filters = GuardrailDeploymentListRequestSchema(endpoint_id=endpoint_id)
    deployments, total = await GuardrailDeploymentService.get_deployments(
        db, filters, current_user.id, page, page_size
    )

    response = GuardrailDeploymentListResponseSchema(
        deployments=deployments,
        total_record=total,
        page=page,
        limit=page_size,
        message="Endpoint deployments retrieved successfully",
    )

    return response


# Project-specific deployment endpoints
@router.get(
    "/projects/{project_id}/deployments",
    response_model=GuardrailDeploymentListResponseSchema,
)
async def get_project_deployments(
    project_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get all active deployments for a specific project."""
    filters = GuardrailDeploymentListRequestSchema(project_id=project_id)
    deployments, total = await GuardrailDeploymentService.get_deployments(
        db, filters, current_user.id, page, page_size
    )

    response = GuardrailDeploymentListResponseSchema(
        deployments=deployments,
        total_record=total,
        page=page,
        limit=page_size,
        message="Project deployments retrieved successfully",
    )

    return response


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
