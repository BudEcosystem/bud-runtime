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

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing_extensions import Annotated

from budapp.commons import logging
from budapp.commons.constants import PermissionEnum
from budapp.commons.dependencies import get_current_active_user, get_session, parse_ordering_fields
from budapp.commons.exception import ClientException
from budapp.commons.permission_handler import require_permissions
from budapp.commons.schemas import ErrorResponse, SuccessResponse
from budapp.guardrails.models import GuardrailProbes, GuardrailRules
from budapp.guardrails.schemas import (
    GuardrailFilter,
    GuardrailProbeDetailResponse,
    GuardrailProbePaginatedResponse,
    GuardrailProbeUpdate,
    GuardrailRuleCreate,
    GuardrailRuleDetailResponse,
    GuardrailRulePaginatedResponse,
    GuardrailRuleUpdate,
    TagsListResponse,
)
from budapp.guardrails.services import GuardrailProbeRuleService
from budapp.user_ops.schemas import User


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/guardrails", tags=["Guardrails"])


@model_router.get(
    "/tags",
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


# Probe endpoints
@router.get(
    "/probes",
    response_model=GuardrailProbePaginatedResponse,
)
@require_permissions(permissions=[PermissionEnum.MODEL_VIEW])
async def list_all_probes(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    filters: Annotated[GuardrailFilter, Depends()],
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=0),
    order_by: Optional[list[str]] = Depends(parse_ordering_fields),
    search: bool = False,
) -> Union[GuardrailProbePaginatedResponse, ErrorResponse]:
    # Calculate offset
    offset = (page - 1) * limit

    # Construct filters
    filters_dict = filters.model_dump(exclude_none=True, exclude_unset=True)

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
        rule=db_rules,
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
    except HTTPException as e:
        return ErrorResponse(code=e.status_code, message=e.detail).to_http_response()
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
    except HTTPException as e:
        return ErrorResponse(code=e.status_code, message=e.detail).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to delete probe: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to delete probe",
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
            tags=request.tags,
            scanner_types=request.scanner_types,
            modality_types=request.modality_types,
            guard_types=request.guard_types,
            examples=request.examples,
        )
        return result.to_http_response()
    except HTTPException as e:
        return ErrorResponse(code=e.status_code, message=e.detail).to_http_response()
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
            tags=request.tags,
            status=request.status,
            scanner_types=request.scanner_types,
            modality_types=request.modality_types,
            guard_types=request.guard_types,
            examples=request.examples,
        )
        return result.to_http_response()
    except HTTPException as e:
        return ErrorResponse(code=e.status_code, message=e.detail).to_http_response()
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
    except HTTPException as e:
        return ErrorResponse(code=e.status_code, message=e.detail).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to delete rule: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to delete rule",
        ).to_http_response()
