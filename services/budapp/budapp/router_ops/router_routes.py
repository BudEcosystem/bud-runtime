from typing import Annotated, List, Optional, Union
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.orm import Session

from budapp.commons import logging
from budapp.commons.dependencies import get_current_active_user, get_session, parse_ordering_fields
from budapp.commons.exceptions import ClientException
from budapp.commons.schemas import ErrorResponse, SingleResponse, SuccessResponse
from budapp.user_ops.schemas import User

from ..commons.constants import PermissionEnum
from ..commons.permission_handler import require_permissions
from .schemas import PaginatedRouterResponse, RouterFilter, RouterRequest, RouterResponse
from .services import RouterService


logger = logging.get_logger(__name__)


router_router = APIRouter(prefix="/routers", tags=["router"])


@router_router.post("/", status_code=status.HTTP_201_CREATED, response_model=SingleResponse[RouterResponse])
@require_permissions(permissions=[PermissionEnum.ENDPOINT_MANAGE])
async def create_router(
    router: RouterRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    x_resource_type: Annotated[Optional[str], Header()] = None,
    x_entity_id: Annotated[Optional[str], Header()] = None,
):
    router_response = await RouterService(session).create_router(current_user.id, router)
    return SingleResponse(message="Router created successfully", result=router_response)


@router_router.get("/", response_model=PaginatedRouterResponse)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_MANAGE])
async def get_routers(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    project_id: UUID = Query(description="List routers by project id"),
    filters: RouterFilter = Depends(),  # noqa: B008
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=0),
    order_by: Optional[List[str]] = Depends(parse_ordering_fields),  # noqa: B008
    search: bool = False,
    x_resource_type: Annotated[Optional[str], Header()] = None,
    x_entity_id: Annotated[Optional[str], Header()] = None,
):
    # Calculate offset
    offset = (page - 1) * limit

    # Construct filters
    filters_dict = filters.model_dump(exclude_none=True, exclude_unset=True)

    try:
        router_response, count = await RouterService(session).get_routers(
            project_id, offset, limit, filters_dict, order_by, search
        )
    except ClientException as e:
        logger.exception(f"Failed to get all routers: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get all routers: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get all routers"
        ).to_http_response()

    return PaginatedRouterResponse(
        routers=router_response,
        total_record=count,
        page=page,
        limit=limit,
        object="routers.list",
        code=status.HTTP_200_OK,
        message="Successfully list all routers",
    ).to_http_response()


@router_router.put(
    "/{router_id}",
    response_model=SingleResponse[RouterResponse],
    response_model_exclude_none=True,
    description="Update saved router.",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_MANAGE])
async def update_router(
    router_id: UUID,
    router_data: RouterRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    x_resource_type: Annotated[Optional[str], Header()] = None,
    x_entity_id: Annotated[Optional[str], Header()] = None,
):
    router_response = await RouterService(session).update_router(router_id, router_data, current_user.id)
    logger.info(f"Router updated: {router_response.id}")

    return SingleResponse(message="Router updated successfully", result=router_response)


@router_router.delete(
    "/{router_id}",
    response_model=SuccessResponse,
    description="Delete saved router",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_MANAGE])
async def delete_router(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    router_id: UUID,
    x_resource_type: Annotated[Optional[str], Header()] = None,
    x_entity_id: Annotated[Optional[str], Header()] = None,
) -> Union[SuccessResponse, ErrorResponse]:
    """Delete a router by its ID."""
    try:
        await RouterService(session).delete_router(router_id, current_user.id)
        logger.debug(f"Router deleting initiated with router id: {router_id}")
        return SuccessResponse(
            message="Router deleting initiated successfully",
            code=status.HTTP_200_OK,
            object="router.delete",
        )
    except ClientException as e:
        logger.exception(f"Failed to delete router: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to delete router: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to delete router",
        ).to_http_response()
