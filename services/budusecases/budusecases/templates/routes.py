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

"""REST API routes for Template module."""

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .crud import TemplateDataManager
from .schemas import CustomTemplateCreateSchema, CustomTemplateUpdateSchema
from .services import (
    InvalidComponentError,
    InvalidComponentTypeError,
    TemplateNameConflictError,
    TemplateNotOwnedError,
    TemplateService,
)
from .sync import TemplateSyncService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/templates", tags=["templates"])


def get_session() -> Session:
    """Get database session. Override in app setup."""
    raise NotImplementedError("Session dependency not configured")


def get_current_user_id() -> UUID:
    """Get current user ID. Override in app setup."""
    raise NotImplementedError("Auth dependency not configured")


class TemplateComponentResponse(BaseModel):
    """Template component response schema."""

    id: str
    name: str
    display_name: str
    description: str | None
    component_type: str
    required: bool
    default_component: str | None
    compatible_components: list[str]
    chart: dict[str, Any] | None = None
    sort_order: int


class TemplateResponse(BaseModel):
    """Template response schema."""

    id: str
    name: str
    display_name: str
    version: str
    description: str
    category: str | None
    tags: list[str]
    parameters: dict[str, Any]
    resources: dict[str, Any] | None
    deployment_order: list[str]
    access: dict[str, Any] | None = None
    source: str
    user_id: str | None
    is_public: bool
    components: list[TemplateComponentResponse]
    created_at: str
    updated_at: str


class TemplateListResponse(BaseModel):
    """Template list response schema."""

    items: list[TemplateResponse]
    total: int
    page: int
    page_size: int


class SyncResponse(BaseModel):
    """Sync response schema."""

    created: int
    updated: int
    deleted: int
    skipped: int


def _template_to_response(template) -> TemplateResponse:
    """Convert template model to response."""
    return TemplateResponse(
        id=str(template.id),
        name=template.name,
        display_name=template.display_name,
        version=template.version,
        description=template.description,
        category=template.category,
        tags=template.tags,
        parameters=template.parameters,
        resources=template.resources,
        deployment_order=template.deployment_order,
        access=template.access,
        source=template.source,
        user_id=str(template.user_id) if template.user_id else None,
        is_public=template.is_public,
        components=[
            TemplateComponentResponse(
                id=str(c.id),
                name=c.name,
                display_name=c.display_name,
                description=c.description,
                component_type=c.component_type,
                required=c.required,
                default_component=c.default_component,
                compatible_components=c.compatible_components,
                chart=c.chart,
                sort_order=c.sort_order,
            )
            for c in template.components
        ],
        created_at=template.created_at.isoformat(),
        updated_at=template.updated_at.isoformat(),
    )


@router.get("", response_model=TemplateListResponse)
async def list_templates(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    category: str | None = Query(None, description="Filter by category"),
    tag: str | None = Query(None, description="Filter by tag"),
    source: str | None = Query(None, description="Filter by source (system or user)"),
    session: Session = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
) -> TemplateListResponse:
    """List templates with optional filters.

    Returns public templates plus the requesting user's private templates.
    """
    manager = TemplateDataManager(session=session)

    templates = manager.list_templates(
        page=page,
        page_size=page_size,
        category=category,
        tag=tag,
        user_id=user_id,
        source=source,
    )

    total = manager.count_templates(
        category=category,
        tag=tag,
        user_id=user_id,
        source=source,
    )

    return TemplateListResponse(
        items=[_template_to_response(t) for t in templates],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: UUID,
    session: Session = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
) -> TemplateResponse:
    """Get a template by ID.

    Returns the template if it is public or owned by the requesting user.
    """
    manager = TemplateDataManager(session=session)
    template = manager.get_template(template_id)

    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template not found: {template_id}",
        )

    # Visibility check: public or owned by user
    if not template.is_public and template.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template not found: {template_id}",
        )

    return _template_to_response(template)


@router.get("/by-name/{name}", response_model=TemplateResponse)
async def get_template_by_name(
    name: str,
    session: Session = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
) -> TemplateResponse:
    """Get a template by name.

    When user has a template with the same name as a system template,
    the user's template takes precedence.
    """
    manager = TemplateDataManager(session=session)
    template = manager.get_template_by_name(name, user_id=user_id)

    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template not found: {name}",
        )

    return _template_to_response(template)


@router.post(
    "",
    response_model=TemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_template(
    request: CustomTemplateCreateSchema,
    session: Session = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
) -> TemplateResponse:
    """Create a custom user template."""
    service = TemplateService(session=session)

    try:
        template = service.create_custom_template(
            schema=request,
            user_id=user_id,
        )
        return _template_to_response(template)

    except TemplateNameConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e
    except (InvalidComponentTypeError, InvalidComponentError) as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: UUID,
    request: CustomTemplateUpdateSchema,
    session: Session = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
) -> TemplateResponse:
    """Update a custom user template.

    Only the template owner can update it.
    """
    service = TemplateService(session=session)

    try:
        template = service.update_custom_template(
            template_id=template_id,
            schema=request,
            user_id=user_id,
        )
        return _template_to_response(template)

    except TemplateNotOwnedError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except (InvalidComponentTypeError, InvalidComponentError) as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: UUID,
    session: Session = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
) -> None:
    """Delete a custom user template.

    Only the template owner can delete it.
    """
    service = TemplateService(session=session)

    try:
        service.delete_custom_template(
            template_id=template_id,
            user_id=user_id,
        )

    except TemplateNotOwnedError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.post("/sync", response_model=SyncResponse)
async def sync_templates(
    session: Session = Depends(get_session),
) -> SyncResponse:
    """Sync templates from YAML files to database.

    This endpoint should be restricted to admin users.
    """
    service = TemplateSyncService(session=session)
    result = service.sync_templates(delete_orphans=False)

    return SyncResponse(
        created=result.created,
        updated=result.updated,
        deleted=result.deleted,
        skipped=result.skipped,
    )
