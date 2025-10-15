# Cluster Settings API endpoints
from typing import Union
from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.orm import Session
from typing_extensions import Annotated

from budapp.commons import logging
from budapp.commons.dependencies import get_current_active_user, get_session
from budapp.commons.exceptions import ClientException
from budapp.commons.schemas import ErrorResponse, SuccessResponse
from budapp.user_ops.schemas import User

from ..commons.constants import PermissionEnum
from ..commons.permission_handler import require_permissions
from .schemas import (
    ClusterSettingsDetailResponse,
    CreateClusterSettingsRequest,
    UpdateClusterSettingsRequest,
)
from .services import ClusterService


logger = logging.get_logger(__name__)

cluster_settings_router = APIRouter(prefix="/clusters", tags=["cluster-settings"])


@cluster_settings_router.get(
    "/{cluster_id}/settings",
    responses={
        status.HTTP_200_OK: {
            "model": ClusterSettingsDetailResponse,
            "description": "Successfully retrieved cluster settings",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Cluster settings not found",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
    },
    description="Get cluster settings by cluster ID",
)
@require_permissions(permissions=[PermissionEnum.CLUSTER_VIEW])
async def get_cluster_settings(
    cluster_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Union[ClusterSettingsDetailResponse, ErrorResponse]:
    """Get cluster settings by cluster ID."""
    try:
        cluster_service = ClusterService(session)
        settings = await cluster_service.get_cluster_settings(cluster_id)

        if not settings:
            return ErrorResponse(
                code=status.HTTP_404_NOT_FOUND,
                message="Cluster settings not found",
            ).to_http_response()

        return ClusterSettingsDetailResponse(
            settings=settings,
            message="Cluster settings retrieved successfully",
            code=status.HTTP_200_OK,
            object="cluster.settings.get",
        )
    except ClientException as e:
        logger.exception(f"Failed to get cluster settings: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get cluster settings: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve cluster settings",
        ).to_http_response()


@cluster_settings_router.post(
    "/{cluster_id}/settings",
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_201_CREATED: {
            "model": ClusterSettingsDetailResponse,
            "description": "Successfully created cluster settings",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Invalid request parameters",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Cluster not found",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
    },
    description="Create cluster settings",
)
@require_permissions(permissions=[PermissionEnum.CLUSTER_MANAGE])
async def create_cluster_settings(
    cluster_id: UUID,
    request: CreateClusterSettingsRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Union[ClusterSettingsDetailResponse, ErrorResponse]:
    """Create cluster settings."""
    try:
        cluster_service = ClusterService(session)
        settings = await cluster_service.create_cluster_settings(
            cluster_id=cluster_id,
            created_by=current_user.id,
            default_storage_class=request.default_storage_class,
            default_access_mode=request.default_access_mode,
        )

        return ClusterSettingsDetailResponse(
            settings=settings,
            message="Cluster settings created successfully",
            code=status.HTTP_201_CREATED,
            object="cluster.settings.create",
        )
    except ClientException as e:
        logger.exception(f"Failed to create cluster settings: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except ValidationError as e:
        logger.exception(f"ValidationErrors: {str(e)}")
        raise RequestValidationError(e.errors())
    except Exception as e:
        logger.exception(f"Failed to create cluster settings: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to create cluster settings",
        ).to_http_response()


@cluster_settings_router.put(
    "/{cluster_id}/settings",
    responses={
        status.HTTP_200_OK: {
            "model": ClusterSettingsDetailResponse,
            "description": "Successfully updated cluster settings",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Invalid request parameters",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Cluster or cluster settings not found",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
    },
    description="Update or create cluster settings (upsert)",
)
@require_permissions(permissions=[PermissionEnum.CLUSTER_MANAGE])
async def update_cluster_settings(
    cluster_id: UUID,
    request: UpdateClusterSettingsRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Union[ClusterSettingsDetailResponse, ErrorResponse]:
    """Update or create cluster settings."""
    try:
        cluster_service = ClusterService(session)
        settings = await cluster_service.upsert_cluster_settings(
            cluster_id=cluster_id,
            created_by=current_user.id,
            default_storage_class=request.default_storage_class,
            default_access_mode=request.default_access_mode,
        )

        return ClusterSettingsDetailResponse(
            settings=settings,
            message="Cluster settings updated successfully",
            code=status.HTTP_200_OK,
            object="cluster.settings.update",
        )
    except ClientException as e:
        logger.exception(f"Failed to update cluster settings: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except ValidationError as e:
        logger.exception(f"ValidationErrors: {str(e)}")
        raise RequestValidationError(e.errors())
    except Exception as e:
        logger.exception(f"Failed to update cluster settings: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to update cluster settings",
        ).to_http_response()


@cluster_settings_router.delete(
    "/{cluster_id}/settings",
    responses={
        status.HTTP_200_OK: {
            "model": SuccessResponse,
            "description": "Successfully deleted cluster settings",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Cluster settings not found",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
    },
    description="Delete cluster settings",
)
@require_permissions(permissions=[PermissionEnum.CLUSTER_MANAGE])
async def delete_cluster_settings(
    cluster_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Union[SuccessResponse, ErrorResponse]:
    """Delete cluster settings."""
    try:
        cluster_service = ClusterService(session)
        deleted = await cluster_service.delete_cluster_settings(cluster_id)

        if not deleted:
            return ErrorResponse(
                code=status.HTTP_404_NOT_FOUND,
                message="Cluster settings not found",
            ).to_http_response()

        return SuccessResponse(
            message="Cluster settings deleted successfully",
            code=status.HTTP_200_OK,
            object="cluster.settings.delete",
        )
    except Exception as e:
        logger.exception(f"Failed to delete cluster settings: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to delete cluster settings",
        ).to_http_response()
