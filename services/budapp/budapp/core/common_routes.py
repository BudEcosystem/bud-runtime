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

"""Defines common routes for the microservices, providing endpoints for retrieving common information."""

from typing import Annotated, List, Optional, Union

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from budapp.commons import logging
from budapp.commons.dependencies import (
    get_current_active_user,
    get_session,
    parse_ordering_fields,
)
from budapp.commons.schemas import ErrorResponse
from budapp.user_ops.schemas import User

from ..commons.exceptions import ClientException
from .schemas import IconFilter, IconListResponse, ModelTemplateFilter, ModelTemplateListResponse
from .services import IconService, ModelTemplateService


logger = logging.get_logger(__name__)

common_router = APIRouter()


@common_router.get(
    "/icons",
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
            "model": IconListResponse,
            "description": "Successfully list all icons",
        },
    },
    description="List all icons",
    tags=["icon"],
)
async def list_all_icons(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    filters: Annotated[IconFilter, Depends()],
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=0),
    order_by: Optional[List[str]] = Depends(parse_ordering_fields),
    search: bool = False,
) -> Union[IconListResponse, ErrorResponse]:
    """List all icons."""
    # Calculate offset
    offset = (page - 1) * limit

    # Convert UserFilter to dictionary
    filters_dict = filters.model_dump(exclude_none=True)

    try:
        db_icons, count = await IconService(session).get_all_icons(offset, limit, filters_dict, order_by, search)
    except Exception as e:
        logger.exception(f"Failed to get all icons: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get all icons"
        ).to_http_response()

    return IconListResponse(
        icons=db_icons,
        total_record=count,
        page=page,
        limit=limit,
        object="icons.list",
        code=status.HTTP_200_OK,
    ).to_http_response()


@common_router.get(
    "/templates",
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
            "model": ModelTemplateListResponse,
            "description": "Successfully list all model templates",
        },
    },
    description="Get all model templates from the database",
    tags=["template"],
)
async def get_all_model_templates(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    filters: Annotated[ModelTemplateFilter, Depends()],
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=0),
    order_by: Optional[List[str]] = Depends(parse_ordering_fields),
    search: bool = False,
) -> Union[ModelTemplateListResponse, ErrorResponse]:
    """List all model templates."""
    # Calculate offset
    offset = (page - 1) * limit

    # Convert UserFilter to dictionary
    filters_dict = filters.model_dump(exclude_none=True)

    try:
        db_templates, count = await ModelTemplateService(session).get_all_templates(
            offset, limit, filters_dict, order_by, search
        )
    except ClientException as e:
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get all model templates: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get all model templates"
        ).to_http_response()

    return ModelTemplateListResponse(
        templates=db_templates,
        total_record=count,
        page=page,
        limit=limit,
        object="templates.list",
        code=status.HTTP_200_OK,
    ).to_http_response()
