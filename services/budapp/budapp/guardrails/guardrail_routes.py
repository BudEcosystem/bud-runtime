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

from typing import Optional, Union
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from typing_extensions import Annotated

from budapp.commons import logging
from budapp.commons.constants import GuardrailDeploymentStatusEnum, PermissionEnum
from budapp.commons.dependencies import get_current_active_user, get_session, parse_ordering_fields
from budapp.commons.exceptions import ClientException
from budapp.commons.permission_handler import require_permissions
from budapp.commons.schemas import ErrorResponse, PaginatedSuccessResponse, SuccessResponse
from budapp.guardrails.crud import GuardrailsDeploymentDataManager
from budapp.guardrails.schemas import (
    GuardrailCustomProbeCreate,
    GuardrailCustomProbeResponse,
    GuardrailCustomProbeUpdate,
    GuardrailDeploymentDetailResponse,
    GuardrailDeploymentPaginatedResponse,
    GuardrailDeploymentUpdate,
    GuardrailDeploymentWorkflowRequest,
    GuardrailFilter,
    GuardrailProbeCreate,
    GuardrailProbeDetailResponse,
    GuardrailProbePaginatedResponse,
    GuardrailProbeUpdate,
    GuardrailProfileDetailResponse,
    GuardrailProfilePaginatedResponse,
    GuardrailProfileProbeResponse,
    GuardrailProfileRuleResponse,
    GuardrailProfileUpdate,
    GuardrailProfileUpdateWithProbes,
    GuardrailRuleCreate,
    GuardrailRuleDetailResponse,
    GuardrailRulePaginatedResponse,
    GuardrailRuleUpdate,
    TagsListResponse,
)
from budapp.guardrails.services import (
    GuardrailDeploymentWorkflowService,
    GuardrailProbeRuleService,
    GuardrailProfileDeploymentService,
)
from budapp.user_ops.schemas import User
from budapp.workflow_ops.schemas import RetrieveWorkflowDataResponse
from budapp.workflow_ops.services import WorkflowService


logger = logging.get_logger(__name__)


router = APIRouter(prefix="/guardrails", tags=["Guardrails"])


@router.get(
    "/probes/tags",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_200_OK: {
            "model": TagsListResponse,
            "description": "Successfully searched tags by name",
        },
    },
    description="Search guardrail tags by name with pagination",
)
@require_permissions(permissions=[PermissionEnum.MODEL_VIEW])
async def list_probe_tags(
    session: Annotated[Session, Depends(get_session)],
    name: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_active_user),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1),
) -> Union[TagsListResponse, ErrorResponse]:
    """List tags by name with pagination support."""
    offset = (page - 1) * limit

    try:
        db_tags, count = await GuardrailProbeRuleService(session).list_probe_tags(name or "", offset, limit)
    except Exception as e:
        return ErrorResponse(code=status.HTTP_500_INTERNAL_SERVER_ERROR, message=str(e)).to_http_response()

    return TagsListResponse(
        tags=db_tags,
        total_record=count,
        page=page,
        limit=limit,
        object="tags.search",
        code=status.HTTP_200_OK,
    ).to_http_response()


@router.get(
    "/probes",
    response_model=GuardrailProbePaginatedResponse,
)
@require_permissions(permissions=[PermissionEnum.MODEL_VIEW])
async def list_all_probes(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    filters: Annotated[GuardrailFilter, Depends()],
    provider_id: Optional[UUID] = Query(None, description="Filter by provider ID"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=0),
    order_by: Optional[list[str]] = Depends(parse_ordering_fields),
    search: bool = False,
) -> Union[GuardrailProbePaginatedResponse, ErrorResponse]:
    # Calculate offset
    offset = (page - 1) * limit

    # Construct filters
    filters_dict = filters.model_dump(exclude_none=True, exclude_unset=True)

    # Provider ID from query parameter takes precedence over filter
    if provider_id is not None:
        filters_dict["provider_id"] = provider_id

    try:
        db_probes, count = await GuardrailProbeRuleService(session).get_all_probes(
            offset, limit, filters_dict, order_by, search
        )
    except ClientException as e:
        logger.exception(f"Failed to get all probes: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get all probes: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get all probes"
        ).to_http_response()

    return GuardrailProbePaginatedResponse(
        probes=db_probes,
        total_record=count,
        page=page,
        limit=limit,
        code=status.HTTP_200_OK,
        message="Successfully list all probes",
    ).to_http_response()


@router.post(
    "/probe",
    response_model=GuardrailProbeDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
@require_permissions(permissions=[PermissionEnum.MODEL_MANAGE])
async def create_probe(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    request: GuardrailProbeCreate,
) -> Union[GuardrailProbeDetailResponse, ErrorResponse]:
    """Create a new guardrail probe."""
    try:
        result = await GuardrailProbeRuleService(session).create_probe(
            name=request.name,
            provider_id=request.provider_id,
            provider_type=request.provider_type,
            user_id=current_user.id,
            status=request.status,
            description=request.description,
            tags=request.tags,
        )
        return result.to_http_response()
    except ClientException as e:
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to create probe: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to create probe",
        ).to_http_response()


@router.get(
    "/probe/{probe_id}",
    response_model=GuardrailProbeDetailResponse,
)
@require_permissions(permissions=[PermissionEnum.MODEL_VIEW])
async def retrieve_probe(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    probe_id: UUID,
) -> Union[GuardrailProbeDetailResponse, ErrorResponse]:
    """Retrieve details of a probe by its ID."""
    try:
        result = await GuardrailProbeRuleService(session).retrieve_probe(probe_id)
        return result.to_http_response()
    except ClientException as e:
        logger.exception(f"Failed to get probe details: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get probe details: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve probe details",
        ).to_http_response()


@router.get(
    "/probe/{probe_id}/rules",
    response_model=GuardrailRulePaginatedResponse,
)
@require_permissions(permissions=[PermissionEnum.MODEL_VIEW])
async def get_probe_rules(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    probe_id: UUID,
    filters: Annotated[GuardrailFilter, Depends()],
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=0),
    order_by: Optional[list[str]] = Depends(parse_ordering_fields),
    search: bool = False,
):
    """Get paginated rules for a specific probe."""
    # Calculate offset
    offset = (page - 1) * limit

    # Construct filters
    filters_dict = filters.model_dump(exclude_none=True, exclude_unset=True)

    try:
        db_rules, count = await GuardrailProbeRuleService(session).get_all_probe_rules(
            probe_id, offset, limit, filters_dict, order_by, search
        )
    except ClientException as e:
        logger.exception(f"Failed to get all rules for {probe_id}: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get all rules for {probe_id}: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message=f"Failed to get all rules for {probe_id}"
        ).to_http_response()

    return GuardrailRulePaginatedResponse(
        rules=db_rules,
        total_record=count,
        page=page,
        limit=limit,
        code=status.HTTP_200_OK,
        message="Successfully list all rules",
    ).to_http_response()


@router.put(
    "/probe/{probe_id}",
    response_model=GuardrailProbeDetailResponse,
)
@require_permissions(permissions=[PermissionEnum.MODEL_MANAGE])
async def edit_probe(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    probe_id: UUID,
    request: GuardrailProbeUpdate,
) -> Union[GuardrailProbeDetailResponse, ErrorResponse]:
    """Update a probe."""
    try:
        result = await GuardrailProbeRuleService(session).edit_probe(
            probe_id=probe_id,
            user_id=current_user.id,
            name=request.name,
            description=request.description,
            tags=request.tags,
            status=request.status,
        )
        return result.to_http_response()
    except ClientException as e:
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to update probe: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to update probe",
        ).to_http_response()


@router.delete(
    "/probe/{probe_id}",
    response_model=SuccessResponse,
)
@require_permissions(permissions=[PermissionEnum.MODEL_MANAGE])
async def delete_probe(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    probe_id: UUID,
) -> Union[SuccessResponse, ErrorResponse]:
    """Delete a probe."""
    try:
        result = await GuardrailProbeRuleService(session).delete_probe(probe_id, current_user.id)
        return result.to_http_response()
    except ClientException as e:
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to delete probe: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to delete probe",
        ).to_http_response()


# Custom probe endpoints


class GuardrailCustomProbePaginatedResponse(PaginatedSuccessResponse):
    """Schema for custom probe list responses."""

    probes: list[GuardrailCustomProbeResponse] = []
    object: str = "guardrail.custom_probe.list"


@router.post(
    "/custom-probe",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_201_CREATED: {
            "model": SuccessResponse,
            "description": "Successfully created custom probe",
        },
    },
    description="Create a custom model-based probe with a single rule",
    status_code=status.HTTP_201_CREATED,
)
@require_permissions(permissions=[PermissionEnum.MODEL_MANAGE])
async def create_custom_probe(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    request: GuardrailCustomProbeCreate,
    project_id: UUID = Query(..., description="Project ID"),
) -> Union[SuccessResponse, ErrorResponse]:
    """Create a custom model-based probe with a single rule."""
    try:
        from budapp.guardrails.services import GuardrailCustomProbeService

        service = GuardrailCustomProbeService(session)
        probe = await service.create_custom_probe(
            request=request,
            project_id=project_id,
            user_id=current_user.id,
        )
        return SuccessResponse(
            code=status.HTTP_201_CREATED,
            object="guardrail.custom_probe.create",
            message="Custom probe created successfully",
            data=GuardrailCustomProbeResponse.model_validate(probe),
        ).to_http_response()
    except ClientException as e:
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to create custom probe: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to create custom probe",
        ).to_http_response()


@router.get(
    "/custom-probes",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_200_OK: {
            "model": GuardrailCustomProbePaginatedResponse,
            "description": "Successfully listed custom probes",
        },
    },
    description="List custom probes created by the current user",
)
@require_permissions(permissions=[PermissionEnum.MODEL_VIEW])
async def list_custom_probes(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    project_id: Optional[UUID] = Query(None, description="Filter by project"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1),
) -> Union[GuardrailCustomProbePaginatedResponse, ErrorResponse]:
    """List custom probes created by the current user."""
    offset = (page - 1) * limit
    try:
        data_manager = GuardrailsDeploymentDataManager(session)
        probes, total = await data_manager.get_custom_probes(
            user_id=current_user.id,
            project_id=project_id,
            offset=offset,
            limit=limit,
        )
        return GuardrailCustomProbePaginatedResponse(
            code=status.HTTP_200_OK,
            probes=[GuardrailCustomProbeResponse.model_validate(p) for p in probes],
            total_record=total,
            page=page,
            limit=limit,
            message="Custom probes retrieved successfully",
        ).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to list custom probes: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to list custom probes",
        ).to_http_response()


@router.put(
    "/custom-probe/{probe_id}",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_200_OK: {
            "model": SuccessResponse,
            "description": "Successfully updated custom probe",
        },
    },
    description="Update a custom probe (user must be owner)",
)
@require_permissions(permissions=[PermissionEnum.MODEL_MANAGE])
async def update_custom_probe(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    probe_id: UUID,
    request: GuardrailCustomProbeUpdate,
) -> Union[SuccessResponse, ErrorResponse]:
    """Update a custom probe (user must be owner)."""
    try:
        from budapp.guardrails.services import GuardrailCustomProbeService

        service = GuardrailCustomProbeService(session)
        probe = await service.update_custom_probe(
            probe_id=probe_id,
            request=request,
            user_id=current_user.id,
        )
        return SuccessResponse(
            code=status.HTTP_200_OK,
            object="guardrail.custom_probe.update",
            message="Custom probe updated successfully",
            data=GuardrailCustomProbeResponse.model_validate(probe),
        ).to_http_response()
    except ClientException as e:
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to update custom probe: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to update custom probe",
        ).to_http_response()


@router.delete(
    "/custom-probe/{probe_id}",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_200_OK: {
            "model": SuccessResponse,
            "description": "Successfully deleted custom probe",
        },
    },
    description="Delete a custom probe (soft delete, user must be owner)",
)
@require_permissions(permissions=[PermissionEnum.MODEL_MANAGE])
async def delete_custom_probe(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    probe_id: UUID,
) -> Union[SuccessResponse, ErrorResponse]:
    """Delete a custom probe (soft delete, user must be owner)."""
    try:
        from budapp.guardrails.services import GuardrailCustomProbeService

        service = GuardrailCustomProbeService(session)
        await service.delete_custom_probe(
            probe_id=probe_id,
            user_id=current_user.id,
        )
        return SuccessResponse(
            code=status.HTTP_200_OK,
            object="guardrail.custom_probe.delete",
            message="Custom probe deleted successfully",
        ).to_http_response()
    except ClientException as e:
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to delete custom probe: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to delete custom probe",
        ).to_http_response()


@router.get(
    "/rule/{rule_id}",
    response_model=GuardrailRuleDetailResponse,
)
@require_permissions(permissions=[PermissionEnum.MODEL_VIEW])
async def retrieve_rule(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    rule_id: UUID,
) -> Union[GuardrailRuleDetailResponse, ErrorResponse]:
    """Retrieve details of a rule by its ID."""
    try:
        result = await GuardrailProbeRuleService(session).retrieve_rule(rule_id)
        return result.to_http_response()
    except ClientException as e:
        logger.exception(f"Failed to get rule details: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get rule details: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve rule details",
        ).to_http_response()


@router.post(
    "/rule",
    response_model=GuardrailRuleDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
@require_permissions(permissions=[PermissionEnum.MODEL_MANAGE])
async def create_rule(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    request: GuardrailRuleCreate,
) -> Union[GuardrailRuleDetailResponse, ErrorResponse]:
    """Create a new rule."""
    try:
        result = await GuardrailProbeRuleService(session).create_rule(
            probe_id=request.probe_id,
            name=request.name,
            user_id=current_user.id,
            status=request.status,
            description=request.description,
            scanner_types=request.scanner_types,
            modality_types=request.modality_types,
            guard_types=request.guard_types,
            examples=request.examples,
        )
        return result.to_http_response()
    except ClientException as e:
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to create rule: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to create rule",
        ).to_http_response()


@router.put(
    "/rule/{rule_id}",
    response_model=GuardrailRuleDetailResponse,
)
@require_permissions(permissions=[PermissionEnum.MODEL_MANAGE])
async def edit_rule(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    rule_id: UUID,
    request: GuardrailRuleUpdate,
) -> Union[GuardrailRuleDetailResponse, ErrorResponse]:
    """Update a rule."""
    try:
        result = await GuardrailProbeRuleService(session).edit_rule(
            rule_id=rule_id,
            user_id=current_user.id,
            name=request.name,
            description=request.description,
            status=request.status,
            scanner_types=request.scanner_types,
            modality_types=request.modality_types,
            guard_types=request.guard_types,
            examples=request.examples,
        )
        return result.to_http_response()
    except ClientException as e:
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to update rule: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to update rule",
        ).to_http_response()


@router.delete(
    "/rule/{rule_id}",
    response_model=SuccessResponse,
)
@require_permissions(permissions=[PermissionEnum.MODEL_MANAGE])
async def delete_rule(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    rule_id: UUID,
) -> Union[SuccessResponse, ErrorResponse]:
    """Delete a rule."""
    try:
        result = await GuardrailProbeRuleService(session).delete_rule(rule_id, current_user.id)
        return result.to_http_response()
    except ClientException as e:
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to delete rule: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to delete rule",
        ).to_http_response()


# Profile endpoints
@router.get(
    "/profiles/tags",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_200_OK: {
            "model": TagsListResponse,
            "description": "Successfully searched tags by name",
        },
    },
    description="Search guardrail profile tags by name with pagination",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_VIEW])
async def list_profile_tags(
    session: Annotated[Session, Depends(get_session)],
    name: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_active_user),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1),
) -> Union[TagsListResponse, ErrorResponse]:
    """List profile tags by name with pagination support."""
    offset = (page - 1) * limit

    try:
        db_tags, count = await GuardrailProfileDeploymentService(session).list_profile_tags(name or "", offset, limit)
    except Exception as e:
        return ErrorResponse(code=status.HTTP_500_INTERNAL_SERVER_ERROR, message=str(e)).to_http_response()

    return TagsListResponse(
        tags=db_tags,
        total_record=count,
        page=page,
        limit=limit,
        object="tags.search",
        code=status.HTTP_200_OK,
    ).to_http_response()


@router.get(
    "/profiles",
    response_model=GuardrailProfilePaginatedResponse,
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_VIEW])
async def list_all_profiles(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    filters: Annotated[GuardrailFilter, Depends()],
    project_id: Optional[UUID] = Query(None, description="Filter by project ID"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=0),
    order_by: Optional[list[str]] = Depends(parse_ordering_fields),
    search: bool = False,
) -> Union[GuardrailProfilePaginatedResponse, ErrorResponse]:
    """List all guardrail profiles with pagination."""
    # Calculate offset
    offset = (page - 1) * limit

    # Construct filters
    filters_dict = filters.model_dump(exclude_none=True, exclude_unset=True)
    if project_id:
        filters_dict["project_id"] = project_id

    try:
        db_profiles, count = await GuardrailProfileDeploymentService(session).list_active_profiles(
            offset, limit, filters_dict, order_by, search
        )
    except ClientException as e:
        logger.exception(f"Failed to get all profiles: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get all profiles: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get all profiles"
        ).to_http_response()

    return GuardrailProfilePaginatedResponse(
        profiles=db_profiles,
        total_record=count,
        page=page,
        limit=limit,
        code=status.HTTP_200_OK,
        message="Successfully list all profiles",
    ).to_http_response()


@router.get(
    "/profile/{profile_id}",
    response_model=GuardrailProfileDetailResponse,
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_VIEW])
async def retrieve_profile(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    profile_id: UUID,
) -> Union[GuardrailProfileDetailResponse, ErrorResponse]:
    """Retrieve details of a profile by its ID."""
    try:
        result = await GuardrailProfileDeploymentService(session).retrieve_profile(profile_id)
        return result.to_http_response()
    except ClientException as e:
        logger.exception(f"Failed to get profile details: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get profile details: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve profile details",
        ).to_http_response()


@router.get(
    "/profile/{profile_id}/probes",
    response_model=GuardrailProbePaginatedResponse,
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_VIEW])
async def get_profile_probes(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    profile_id: UUID,
    filters: Annotated[GuardrailFilter, Depends()],
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=0),
    order_by: Optional[list[str]] = Depends(parse_ordering_fields),
    search: bool = False,
) -> Union[GuardrailProbePaginatedResponse, ErrorResponse]:
    """Get paginated probes for a specific profile."""
    # Calculate offset
    offset = (page - 1) * limit

    # Construct filters
    filters_dict = filters.model_dump(exclude_none=True, exclude_unset=True)

    try:
        db_probes, count = await GuardrailProfileDeploymentService(session).list_profile_probes(
            profile_id, offset, limit, filters_dict, order_by, search
        )
    except ClientException as e:
        logger.exception(f"Failed to get all probes for profile {profile_id}: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get all probes for profile {profile_id}: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message=f"Failed to get all probes for profile {profile_id}"
        ).to_http_response()

    return GuardrailProbePaginatedResponse(
        probes=db_probes,
        total_record=count,
        page=page,
        limit=limit,
        code=status.HTTP_200_OK,
        message="Successfully list all probes",
        object="guardrail.profile.probe.list",
    ).to_http_response()


@router.get(
    "/profile/{profile_id}/probe/{probe_id}/rules",
    response_model=GuardrailRulePaginatedResponse,
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_VIEW])
async def get_profile_probe_rules(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    profile_id: UUID,
    probe_id: UUID,
    filters: Annotated[GuardrailFilter, Depends()],
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=0),
    order_by: Optional[list[str]] = Depends(parse_ordering_fields),
    search: bool = False,
) -> Union[GuardrailRulePaginatedResponse, ErrorResponse]:
    """Get paginated rules for a specific probe in a profile with status overrides."""
    # Calculate offset
    offset = (page - 1) * limit

    # Construct filters
    filters_dict = filters.model_dump(exclude_none=True, exclude_unset=True)

    try:
        db_rules, count = await GuardrailProfileDeploymentService(session).list_profile_probe_rules(
            profile_id, probe_id, offset, limit, filters_dict, order_by, search
        )
    except ClientException as e:
        logger.exception(f"Failed to get all rules for probe {probe_id} in profile {profile_id}: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get all rules for probe {probe_id} in profile {profile_id}: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=f"Failed to get all rules for probe {probe_id} in profile {profile_id}",
        ).to_http_response()

    return GuardrailRulePaginatedResponse(
        rules=db_rules,
        total_record=count,
        page=page,
        limit=limit,
        code=status.HTTP_200_OK,
        message="Successfully list all rules",
        object="guardrail.profile.probe.rule.list",
    ).to_http_response()


@router.get(
    "/profile/{profile_id}/deployments",
    response_model=GuardrailDeploymentPaginatedResponse,
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_VIEW])
async def list_all_profile_deployments(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    profile_id: UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=0),
    order_by: Optional[list[str]] = Depends(parse_ordering_fields),
    search: bool = False,
) -> Union[GuardrailDeploymentPaginatedResponse, ErrorResponse]:
    """List all guardrail deployments with pagination."""
    # Calculate offset
    offset = (page - 1) * limit

    # Construct filters
    filters_dict = {}
    filters_dict["profile_id"] = profile_id

    try:
        db_deployments, count = await GuardrailProfileDeploymentService(session).list_deployments(
            offset, limit, filters_dict, order_by, search
        )
    except ClientException as e:
        logger.exception(f"Failed to get all deployments: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get all deployments: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get all deployments"
        ).to_http_response()

    return GuardrailDeploymentPaginatedResponse(
        deployments=db_deployments,
        total_record=count,
        page=page,
        limit=limit,
        code=status.HTTP_200_OK,
        message="Successfully list all deployments",
    ).to_http_response()


@router.put(
    "/profile/{profile_id}",
    response_model=GuardrailProfileDetailResponse,
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_MANAGE])
async def update_profile_with_probes(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    profile_id: UUID,
    request: GuardrailProfileUpdateWithProbes,
) -> Union[GuardrailProfileDetailResponse, ErrorResponse]:
    """Update a guardrail profile with probe selections.

    This endpoint allows updating both profile fields and probe/rule selections.
    Probe selections can:
    - Add new probes to the profile
    - Remove existing probes from the profile
    - Update probe-specific overrides (severity_threshold, guard_types)
    - Update rule-specific overrides within each probe
    """
    try:
        result = await GuardrailProfileDeploymentService(session).update_profile_with_probes(
            profile_id=profile_id,
            user_id=current_user.id,
            name=request.name,
            description=request.description,
            tags=request.tags,
            severity_threshold=request.severity_threshold,
            guard_types=request.guard_types,
            probe_selections=request.probe_selections,
        )
        return result.to_http_response()
    except ClientException as e:
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to update profile with probes: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to update profile",
        ).to_http_response()


@router.delete(
    "/profile/{profile_id}",
    response_model=SuccessResponse,
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_MANAGE])
async def delete_profile(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    profile_id: UUID,
) -> Union[SuccessResponse, ErrorResponse]:
    """Delete (soft delete) a guardrail profile."""
    try:
        result = await GuardrailProfileDeploymentService(session).delete_profile(profile_id, current_user.id)
        return result.to_http_response()
    except ClientException as e:
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to delete profile: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to delete profile",
        ).to_http_response()


@router.post(
    "/deploy-workflow",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_200_OK: {
            "model": RetrieveWorkflowDataResponse,
            "description": "Successfully add guardrail deployment workflow",
        },
    },
    description="Add guardrail deployment workflow",
)
@require_permissions(permissions=[PermissionEnum.MODEL_MANAGE])
async def add_guardrail_deployment_workflow(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    request: GuardrailDeploymentWorkflowRequest,
) -> Union[RetrieveWorkflowDataResponse, ErrorResponse]:
    """Add guardrail deployment workflow."""
    try:
        db_workflow = await GuardrailDeploymentWorkflowService(session).add_guardrail_deployment_workflow(
            current_user_id=current_user.id,
            request=request,
        )

        return await WorkflowService(session).retrieve_workflow_data(db_workflow.id)
    except ClientException as e:
        logger.exception(f"Failed to add guardrail deployment workflow: {e}")
        return ErrorResponse(code=status.HTTP_400_BAD_REQUEST, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to add guardrail deployment workflow: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to add guardrail deployment workflow"
        ).to_http_response()


# Deployment endpoints


@router.get(
    "/deployment/{deployment_id}",
    response_model=GuardrailDeploymentDetailResponse,
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_VIEW])
async def retrieve_deployment(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    deployment_id: UUID,
) -> Union[GuardrailDeploymentDetailResponse, ErrorResponse]:
    """Retrieve details of a deployment by its ID."""
    try:
        result = await GuardrailProfileDeploymentService(session).retrieve_deployment(deployment_id)
        return result.to_http_response()
    except ClientException as e:
        logger.exception(f"Failed to get deployment details: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get deployment details: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve deployment details",
        ).to_http_response()


@router.get(
    "/deployment/{deployment_id}/progress",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_200_OK: {
            "model": SuccessResponse,
            "description": "Successfully retrieved deployment progress",
        },
    },
    description="Get progress of a guardrail deployment via BudPipeline",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_VIEW])
async def get_deployment_progress(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    deployment_id: UUID,
    detail: str = Query("summary", description="Detail level: summary, steps, full"),
) -> Union[SuccessResponse, ErrorResponse]:
    """Get progress of a guardrail deployment via BudPipeline."""
    try:
        progress = await GuardrailDeploymentWorkflowService(session).get_deployment_progress(
            deployment_id=deployment_id,
            detail=detail,
        )
        return SuccessResponse(
            code=status.HTTP_200_OK,
            object="guardrail.deployment.progress",
            message="Deployment progress retrieved",
            data=progress,
        ).to_http_response()
    except ClientException as e:
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get deployment progress: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to get deployment progress",
        ).to_http_response()


@router.put(
    "/deployment/{deployment_id}",
    response_model=GuardrailDeploymentDetailResponse,
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_MANAGE])
async def edit_deployment(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    deployment_id: UUID,
    request: GuardrailDeploymentUpdate,
) -> Union[GuardrailDeploymentDetailResponse, ErrorResponse]:
    """Update a guardrail deployment.

    Only the following fields can be updated:
    - name
    - description
    - severity_threshold
    - guard_types
    """
    try:
        result = await GuardrailProfileDeploymentService(session).edit_deployment(
            deployment_id=deployment_id,
            user_id=current_user.id,
            name=request.name,
            description=request.description,
            severity_threshold=request.severity_threshold,
            guard_types=request.guard_types,
        )
        return result.to_http_response()
    except ClientException as e:
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to update deployment: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to update deployment",
        ).to_http_response()


@router.delete(
    "/deployment/{deployment_id}",
    response_model=SuccessResponse,
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_MANAGE])
async def delete_deployment(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    deployment_id: UUID,
) -> Union[SuccessResponse, ErrorResponse]:
    """Delete (soft delete) a guardrail deployment."""
    try:
        result = await GuardrailProfileDeploymentService(session).delete_deployment(deployment_id, current_user.id)
        return result.to_http_response()
    except ClientException as e:
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to delete deployment: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to delete deployment",
        ).to_http_response()
