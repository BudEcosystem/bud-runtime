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

"""The endpoint ops package, containing essential business logic, services, and routing configurations for the endpoint ops."""

from typing import List, Optional, Union
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Header, Query, status
from sqlalchemy.orm import Session
from typing_extensions import Annotated

from budapp.commons import logging
from budapp.commons.dependencies import (
    get_current_active_user,
    get_current_active_user_or_internal,
    get_session,
    parse_ordering_fields,
)
from budapp.commons.exceptions import ClientException
from budapp.user_ops.schemas import User

from ..commons.constants import PermissionEnum
from ..commons.permission_handler import require_permissions, require_permissions_or_internal
from ..commons.schemas import ErrorResponse, SuccessResponse
from ..workflow_ops.schemas import RetrieveWorkflowDataResponse
from ..workflow_ops.services import WorkflowService
from .schemas import (
    AdapterFilter,
    AdapterPaginatedResponse,
    AddAdapterRequest,
    AddWorkerRequest,
    AutoscaleConfigResponse,
    DeleteWorkerRequest,
    DeploymentPricingResponse,
    DeploymentSettingsResponse,
    EndpointDeleteResponse,
    EndpointFilter,
    EndpointPaginatedResponse,
    ModelClusterDetailResponse,
    PricingHistoryResponse,
    PublicationHistoryResponse,
    PublishEndpointResponse,
    UpdateAutoscaleRequest,
    UpdateDeploymentSettingsRequest,
    UpdatePricingRequest,
    UpdatePublicationStatusRequest,
    WorkerDetailResponse,
    WorkerInfoFilter,
    WorkerInfoResponse,
    WorkerLogsResponse,
    WorkerMetricsResponse,
)
from .services import EndpointService


logger = logging.get_logger(__name__)

endpoint_router = APIRouter(prefix="/endpoints", tags=["endpoint"])


@endpoint_router.get(
    "/",
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
            "model": EndpointPaginatedResponse,
            "description": "Successfully list all endpoints",
        },
    },
    description="List all endpoints. \n\n order_by fields are: name, status, created_at, modified_at, cluster_name, model_name, modality, is_published, published_date",
)
@require_permissions(permissions=[PermissionEnum.PROJECT_VIEW, PermissionEnum.ENDPOINT_VIEW])
async def list_all_endpoints(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    filters: Annotated[EndpointFilter, Depends()],
    project_id: Optional[UUID] = Query(
        None, description="List endpoints by project id. If not provided, returns all endpoints across all projects."
    ),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=0),
    order_by: Optional[List[str]] = Depends(parse_ordering_fields),
    search: bool = False,
    x_resource_type: Annotated[Optional[str], Header()] = None,
    x_entity_id: Annotated[Optional[str], Header()] = None,
) -> Union[EndpointPaginatedResponse, ErrorResponse]:
    """List all endpoints."""
    # Calculate offset
    offset = (page - 1) * limit

    # Construct filters
    filters_dict = filters.model_dump(exclude_none=True, exclude_unset=True)

    try:
        db_endpoints, count = await EndpointService(session).get_all_endpoints(
            current_user.id, current_user.is_superuser, project_id, offset, limit, filters_dict, order_by, search
        )
    except ClientException as e:
        logger.exception(f"Failed to get all endpoints: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get all endpoints: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get all endpoints"
        ).to_http_response()

    return EndpointPaginatedResponse(
        endpoints=db_endpoints,
        total_record=count,
        page=page,
        limit=limit,
        object="endpoints.list",
        code=status.HTTP_200_OK,
        message="Successfully list all endpoints",
    ).to_http_response()


@endpoint_router.post(
    "/{endpoint_id}/delete-workflow",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Invalid request parameters",
        },
        status.HTTP_200_OK: {
            "model": EndpointDeleteResponse,
            "description": "Successfully executed delete endpoint workflow",
        },
    },
    description="Delete an endpoint by ID",
)
@require_permissions_or_internal(permissions=[PermissionEnum.ENDPOINT_MANAGE])
async def delete_endpoint(
    current_user: Annotated[User, Depends(get_current_active_user_or_internal)],
    session: Annotated[Session, Depends(get_session)],
    endpoint_id: UUID,
    x_resource_type: Annotated[Optional[str], Header()] = None,
    x_entity_id: Annotated[Optional[str], Header()] = None,
    callback_topic: Annotated[Optional[str], Body(embed=True)] = None,
) -> Union[EndpointDeleteResponse, ErrorResponse]:
    """Delete a endpoint by its ID.

    Args:
        callback_topic: Optional Dapr pub/sub topic for budpipeline integration.
                       If provided, completion events will be published to this topic.
    """
    try:
        db_workflow = await EndpointService(session).delete_endpoint(
            endpoint_id, current_user.id, callback_topic=callback_topic
        )
        logger.debug(f"Endpoint deleting initiated with workflow id: {db_workflow.id}")
        return EndpointDeleteResponse(
            message="Deployment deleting initiated successfully",
            code=status.HTTP_200_OK,
            object="endpoint.delete",
            workflow_id=db_workflow.id,
        )
    except ClientException as e:
        logger.exception(f"Failed to delete endpoint: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to delete endpoint: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to delete endpoint",
        ).to_http_response()


@endpoint_router.get(
    "/{endpoint_id}/workers",
    responses={
        status.HTTP_200_OK: {
            "model": WorkerInfoResponse,
            "description": "Successfully get endpoint detail",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Failed to get endpoint workers",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Endpoint not found",
        },
    },
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_VIEW])
async def get_endpoint_workers(
    endpoint_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    filters: Annotated[WorkerInfoFilter, Depends()],
    refresh: bool = Query(False),  # noqa: B008
    page: int = Query(1, ge=1),  # noqa: B008
    limit: int = Query(10, ge=0),  # noqa: B008
    order_by: Optional[List[str]] = Query(None),  # noqa: B008
    search: bool = Query(False),  # noqa: B008
    x_resource_type: Annotated[Optional[str], Header()] = None,
    x_entity_id: Annotated[Optional[str], Header()] = None,
) -> Union[WorkerInfoResponse, ErrorResponse]:
    """Get endpoint workers."""
    try:
        workers = await EndpointService(session).get_endpoint_workers(
            endpoint_id, filters, refresh, page, limit, order_by, search
        )
        response = WorkerInfoResponse(**workers)
    except ClientException as e:
        logger.exception(f"Failed to get endpoint workers: {e}")
        response = ErrorResponse(message=e.message, code=e.status_code)
    except Exception as e:
        logger.exception(f"Failed to get endpoint workers: {e}")
        response = ErrorResponse(message="Failed to get endpoint workers", code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    return response.to_http_response()


@endpoint_router.get(
    "/{endpoint_id}/workers/{worker_id}/logs",
    responses={
        status.HTTP_200_OK: {
            "model": WorkerLogsResponse,
            "description": "Successfully get endpoint detail",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Failed to get endpoint workers",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Worker not found",
        },
    },
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_VIEW])
async def get_endpoint_worker_logs(
    endpoint_id: UUID,
    worker_id: UUID,
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    x_resource_type: Annotated[Optional[str], Header()] = None,
    x_entity_id: Annotated[Optional[str], Header()] = None,
) -> Union[WorkerLogsResponse, ErrorResponse]:
    """Get endpoint worker logs."""
    try:
        worker_log = await EndpointService(session).get_endpoint_worker_logs(endpoint_id, worker_id)
        response = WorkerLogsResponse(
            logs=worker_log,
            object="endpoint.worker.logs",
            message="Successfully fetched endpoint worker logs",
            code=status.HTTP_200_OK,
        )
    except ClientException as e:
        logger.exception(f"Failed to get endpoint worker detail: {e}")
        response = ErrorResponse(message=e.message, code=e.status_code)
    except Exception as e:
        logger.exception(f"Failed to get endpoint worker detail: {e}")
        response = ErrorResponse(
            message="Failed to get endpoint worker detail", code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    return response.to_http_response()


@endpoint_router.get(
    "/{endpoint_id}/workers/{worker_id}/metrics",
    responses={
        status.HTTP_200_OK: {
            "model": WorkerMetricsResponse,  # noqa: F821
            "description": "Successfully get endpoint worker metrics",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Worker not found",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Failed to get endpoint worker metrics",
        },
    },
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_VIEW])
async def get_endpoint_worker_metrics(
    endpoint_id: UUID,
    worker_id: UUID,
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    x_resource_type: Annotated[Optional[str], Header()] = None,
    x_entity_id: Annotated[Optional[str], Header()] = None,
) -> Union[WorkerMetricsResponse, ErrorResponse]:
    """Get endpoint worker metrics."""
    try:
        worker_metrics = await EndpointService(session).get_worker_metrics_history(endpoint_id, worker_id)
        response = WorkerMetricsResponse(
            metrics=worker_metrics,
            object="endpoint.worker.metrics",
            message="Successfully fetched endpoint worker metrics",
            code=status.HTTP_200_OK,
        )
    except ClientException as e:
        logger.exception(f"Failed to get endpoint worker metrics: {e}")
        response = ErrorResponse(message=e.message, code=e.status_code)
    except Exception as e:
        logger.exception(f"Failed to get endpoint worker metrics: {e}")
        response = ErrorResponse(
            message="Failed to get endpoint worker metrics", code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    return response.to_http_response()


@endpoint_router.get(
    "/{endpoint_id}/workers/{worker_id}",
    responses={
        status.HTTP_200_OK: {
            "model": WorkerDetailResponse,
            "description": "Successfully get endpoint detail",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Failed to get endpoint workers",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Worker not found",
        },
    },
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_VIEW])
async def get_endpoint_worker_detail(
    endpoint_id: UUID,
    worker_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    reload: bool = Query(False),  # noqa: B008
    x_resource_type: Annotated[Optional[str], Header()] = None,
    x_entity_id: Annotated[Optional[str], Header()] = None,
) -> Union[WorkerDetailResponse, ErrorResponse]:
    """Get endpoint workers."""
    try:
        worker_detail = await EndpointService(session).get_endpoint_worker_detail(endpoint_id, worker_id, reload)
        response = WorkerDetailResponse(**worker_detail)
    except ClientException as e:
        logger.exception(f"Failed to get endpoint worker detail: {e}")
        response = ErrorResponse(message=e.message, code=e.status_code)
    except Exception as e:
        logger.exception(f"Failed to get endpoint worker detail: {e}")
        response = ErrorResponse(
            message="Failed to get endpoint worker detail", code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    return response.to_http_response()


@endpoint_router.get(
    "/{endpoint_id}/model-cluster-detail",
    responses={
        status.HTTP_200_OK: {
            "model": ModelClusterDetailResponse,
            "description": "Successfully get model cluster detail",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Endpoint not found",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Failed to get model cluster detail",
        },
    },
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_VIEW])
async def get_model_cluster_detail(
    endpoint_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    x_resource_type: Annotated[Optional[str], Header()] = None,
    x_entity_id: Annotated[Optional[str], Header()] = None,
) -> Union[ModelClusterDetailResponse, ErrorResponse]:
    """Get model cluster detail."""
    try:
        model_cluster_detail = await EndpointService(session).get_model_cluster_detail(endpoint_id)
        response = ModelClusterDetailResponse(
            object="endpoint.detail",
            result=model_cluster_detail,
            message="Successfully fetched model cluster detail for the deployment.",
        )
    except ClientException as e:
        logger.exception(f"Failed to get model cluster detail: {e}")
        response = ErrorResponse(message=e.message, code=e.status_code)
    except Exception as e:
        logger.exception(f"Failed to get model cluster detail: {e}")
        response = ErrorResponse(
            message="Failed to get model cluster detail", code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    return response.to_http_response()


@endpoint_router.post(
    "/delete-worker",
    responses={
        status.HTTP_200_OK: {
            "model": SuccessResponse,
            "description": "Successfully deleted deploymentworker",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Worker not found",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Failed to delete deployment worker",
        },
    },
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_MANAGE])
async def delete_endpoint_worker(
    request: DeleteWorkerRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    x_resource_type: Annotated[Optional[str], Header()] = None,
    x_entity_id: Annotated[Optional[str], Header()] = None,
) -> Union[SuccessResponse, ErrorResponse]:
    """Delete a endpoint worker by its ID."""
    try:
        db_workflow = await EndpointService(session).delete_endpoint_worker(
            request.endpoint_id, request.worker_id, request.worker_name, current_user.id
        )
        logger.debug(f"Endpoint deleting initiated with workflow id: {db_workflow.id}")
        response = SuccessResponse(
            message="Worker deleting initiated successfully",
            code=status.HTTP_200_OK,
            object="worker.delete",
        )
    except ClientException as e:
        logger.exception(f"Failed to get endpoint worker detail: {e}")
        response = ErrorResponse(message=e.message, code=e.status_code)
    except Exception as e:
        logger.exception(f"Failed to get endpoint worker detail: {e}")
        response = ErrorResponse(
            message="Failed to get endpoint worker detail", code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    return response.to_http_response()


@endpoint_router.post(
    "/add-worker",
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
            "description": "Successfully add worker",
        },
    },
    description="Add worker to endpoint",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_MANAGE])
async def add_worker_to_endpoint(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    request: AddWorkerRequest,
    x_resource_type: Annotated[Optional[str], Header()] = None,
    x_entity_id: Annotated[Optional[str], Header()] = None,
) -> Union[RetrieveWorkflowDataResponse, ErrorResponse]:
    """Add worker to endpoint."""
    try:
        db_workflow = await EndpointService(session).add_worker_to_endpoint_workflow(
            current_user_id=current_user.id,
            request=request,
        )

        return await WorkflowService(session).retrieve_workflow_data(db_workflow.id)
    except ClientException as e:
        logger.exception(f"Failed to add worker to endpoint: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to add worker to endpoint: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to add worker to endpoint"
        ).to_http_response()


@endpoint_router.post(
    "/add-adapter",
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
            "description": "Successfully updated Add Adapter workflow",
        },
    },
    description="Add worker to endpoint",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_MANAGE])
async def add_adapter_to_endpoint(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    request: AddAdapterRequest,
    x_resource_type: Annotated[Optional[str], Header()] = None,
    x_entity_id: Annotated[Optional[str], Header()] = None,
) -> Union[RetrieveWorkflowDataResponse, ErrorResponse]:
    """Add worker to endpoint."""
    try:
        db_workflow = await EndpointService(session).add_adapter_workflow(
            current_user_id=current_user.id,
            request=request,
        )

        return await WorkflowService(session).retrieve_workflow_data(db_workflow.id)
    except ClientException as e:
        logger.exception(f"Failed to add adapter to endpoint: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to add adapter to endpoint: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to add adapter to endpoint"
        ).to_http_response()


@endpoint_router.get(
    "/{endpoint_id}/adapters",
    responses={
        status.HTTP_200_OK: {
            "model": AdapterPaginatedResponse,
            "description": "Successfully get endpoint adapters",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Failed to get endpoint workers",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Endpoint not found",
        },
    },
    description="Get endpoint adapters",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_VIEW])
async def get_endpoint_adapters(
    endpoint_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    filters: Annotated[AdapterFilter, Depends()],
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=0),
    order_by: Optional[List[str]] = Depends(parse_ordering_fields),
    search: bool = Query(False),
    x_resource_type: Annotated[Optional[str], Header()] = None,
    x_entity_id: Annotated[Optional[str], Header()] = None,
) -> Union[AdapterPaginatedResponse, ErrorResponse]:
    """Get endpoint adapters."""
    offset = (page - 1) * limit

    # Construct filters
    filters_dict = filters.model_dump(exclude_none=True, exclude_unset=True)

    try:
        adapters, count = await EndpointService(session).get_adapters_by_endpoint(
            endpoint_id, filters_dict, offset, limit, order_by, search
        )
        response = AdapterPaginatedResponse(
            adapters=adapters,
            total_record=count,
            page=page,
            limit=limit,
            object="adapters.list",
            code=status.HTTP_200_OK,
            message="Successfully list all adapters",
        )
    except ClientException as e:
        logger.exception(f"Failed to get endpoint adapters: {e}")
        response = ErrorResponse(message=e.message, code=e.status_code)
    except Exception as e:
        logger.exception(f"Failed to get endpoint adapters: {e}")
        response = ErrorResponse(message="Failed to get endpoint adapters", code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return response.to_http_response()


@endpoint_router.post(
    "/delete-adapter/{adapter_id}",
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
            "description": "Successfully updated delete adapter workflow",
        },
    },
    description="Add worker to endpoint",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_MANAGE])
async def delete_adapter_from_endpoint(
    adapter_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    x_resource_type: Annotated[Optional[str], Header()] = None,
    x_entity_id: Annotated[Optional[str], Header()] = None,
) -> Union[RetrieveWorkflowDataResponse, ErrorResponse]:
    """Add worker to endpoint."""
    try:
        await EndpointService(session).delete_adapter_workflow(
            current_user_id=current_user.id,
            adapter_id=adapter_id,
        )
        response = SuccessResponse(
            message="Adapter deleting initiated successfully",
            code=status.HTTP_200_OK,
            object="adapter.delete",
        )
        return response.to_http_response()
    except ClientException as e:
        logger.exception(f"Failed to delete adapter from endpoint: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to delete adapter from endpoint: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to delete adapter from endpoint"
        ).to_http_response()


@endpoint_router.put(
    "/{endpoint_id}/publish",
    responses={
        status.HTTP_200_OK: {
            "model": PublishEndpointResponse,
            "description": "Successfully updated publication status",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Invalid request or action",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Endpoint not found",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Failed to update publication status",
        },
    },
    description="Update publication status of an endpoint (publish/unpublish)",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_MANAGE])
async def update_publication_status(
    endpoint_id: UUID,
    request: UpdatePublicationStatusRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    x_resource_type: Annotated[Optional[str], Header()] = None,
    x_entity_id: Annotated[Optional[str], Header()] = None,
) -> Union[PublishEndpointResponse, ErrorResponse]:
    """Update publication status of an endpoint (publish/unpublish)."""
    try:
        # Convert pricing to dict if provided
        pricing_data = None
        if request.pricing:
            pricing_data = request.pricing.model_dump()

        endpoint = await EndpointService(session).update_publication_status(
            endpoint_id=endpoint_id,
            action=request.action,
            current_user_id=current_user.id,
            action_metadata=request.action_metadata,
            pricing=pricing_data,
        )
        # Get current pricing if published
        pricing_response = None
        if endpoint.is_published:
            current_pricing = await EndpointService(session).get_current_pricing(endpoint_id)
            if current_pricing:
                pricing_response = DeploymentPricingResponse.model_validate(current_pricing)

        return PublishEndpointResponse(
            endpoint_id=endpoint.id,
            is_published=endpoint.is_published,
            published_date=endpoint.published_date,
            published_by=endpoint.published_by,
            pricing=pricing_response,
            message=f"Endpoint {request.action}ed successfully",
        ).to_http_response()
    except ClientException as e:
        logger.exception(f"Failed to update publication status: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to update publication status: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to update publication status"
        ).to_http_response()


@endpoint_router.put(
    "/{endpoint_id}/pricing",
    responses={
        status.HTTP_200_OK: {
            "model": DeploymentPricingResponse,
            "description": "Successfully updated pricing",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Invalid request data",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Endpoint not found",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Failed to update pricing",
        },
    },
    description="Update pricing for a published endpoint",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_MANAGE])
async def update_endpoint_pricing(
    endpoint_id: UUID,
    request: UpdatePricingRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    x_resource_type: Annotated[Optional[str], Header()] = None,
    x_entity_id: Annotated[Optional[str], Header()] = None,
) -> Union[DeploymentPricingResponse, ErrorResponse]:
    """Update pricing for a published endpoint."""
    try:
        pricing = await EndpointService(session).update_pricing(
            endpoint_id=endpoint_id,
            pricing_data=request.model_dump(),
            current_user_id=current_user.id,
        )
        return DeploymentPricingResponse.model_validate(pricing)
    except ClientException as e:
        logger.exception(f"Failed to update pricing: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to update pricing: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to update pricing"
        ).to_http_response()


@endpoint_router.get(
    "/{endpoint_id}/pricing",
    responses={
        status.HTTP_200_OK: {
            "model": DeploymentPricingResponse,
            "description": "Successfully retrieved current pricing",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Endpoint or pricing not found",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Failed to get pricing",
        },
    },
    description="Get current pricing for an endpoint",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_VIEW])
async def get_endpoint_pricing(
    endpoint_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    x_resource_type: Annotated[Optional[str], Header()] = None,
    x_entity_id: Annotated[Optional[str], Header()] = None,
) -> Union[DeploymentPricingResponse, ErrorResponse]:
    """Get current pricing for an endpoint."""
    try:
        pricing = await EndpointService(session).get_current_pricing(endpoint_id)
        if not pricing:
            return ErrorResponse(
                code=status.HTTP_404_NOT_FOUND,
                message=f"No pricing found for endpoint {endpoint_id}",
            ).to_http_response()
        return DeploymentPricingResponse.model_validate(pricing)
    except ClientException as e:
        logger.exception(f"Failed to get pricing: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get pricing: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get pricing"
        ).to_http_response()


@endpoint_router.get(
    "/{endpoint_id}/pricing/history",
    responses={
        status.HTTP_200_OK: {
            "model": PricingHistoryResponse,
            "description": "Successfully retrieved pricing history",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Endpoint not found",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Failed to get pricing history",
        },
    },
    description="Get pricing history for an endpoint",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_VIEW])
async def get_pricing_history(
    endpoint_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    x_resource_type: Annotated[Optional[str], Header()] = None,
    x_entity_id: Annotated[Optional[str], Header()] = None,
) -> Union[PricingHistoryResponse, ErrorResponse]:
    """Get pricing history for an endpoint."""
    try:
        result = await EndpointService(session).get_pricing_history(
            endpoint_id=endpoint_id,
            page=page,
            limit=limit,
        )
        return PricingHistoryResponse(**result).to_http_response()
    except ClientException as e:
        logger.exception(f"Failed to get pricing history: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get pricing history: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get pricing history"
        ).to_http_response()


@endpoint_router.get(
    "/{endpoint_id}/publication-history",
    responses={
        status.HTTP_200_OK: {
            "model": PublicationHistoryResponse,
            "description": "Successfully retrieved publication history",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Endpoint not found",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Failed to get publication history",
        },
    },
    description="Get publication history for an endpoint",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_VIEW])
async def get_publication_history(
    endpoint_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    x_resource_type: Annotated[Optional[str], Header()] = None,
    x_entity_id: Annotated[Optional[str], Header()] = None,
) -> Union[PublicationHistoryResponse, ErrorResponse]:
    """Get publication history for an endpoint."""
    try:
        result = await EndpointService(session).get_publication_history(
            endpoint_id=endpoint_id,
            page=page,
            limit=limit,
        )
        return PublicationHistoryResponse(**result).to_http_response()
    except ClientException as e:
        logger.exception(f"Failed to get publication history: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get publication history: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get publication history"
        ).to_http_response()


@endpoint_router.get(
    "/{endpoint_id}/deployment-settings",
    responses={
        status.HTTP_200_OK: {
            "model": DeploymentSettingsResponse,
            "description": "Successfully retrieved deployment settings",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Endpoint not found",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Failed to get deployment settings",
        },
    },
    description="Get deployment settings for an endpoint",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_VIEW])
async def get_deployment_settings(
    endpoint_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    x_resource_type: Annotated[Optional[str], Header()] = None,
    x_entity_id: Annotated[Optional[str], Header()] = None,
) -> Union[DeploymentSettingsResponse, ErrorResponse]:
    """Get deployment settings for an endpoint."""
    try:
        deployment_settings = await EndpointService(session).get_deployment_settings(endpoint_id)
        return DeploymentSettingsResponse(
            endpoint_id=endpoint_id,
            deployment_settings=deployment_settings,
            message="Successfully retrieved deployment settings",
        ).to_http_response()
    except ClientException as e:
        logger.exception(f"Failed to get deployment settings: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get deployment settings: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get deployment settings"
        ).to_http_response()


@endpoint_router.put(
    "/{endpoint_id}/deployment-settings",
    responses={
        status.HTTP_200_OK: {
            "model": DeploymentSettingsResponse,
            "description": "Successfully updated deployment settings",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Invalid deployment settings",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Endpoint not found",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Failed to update deployment settings",
        },
    },
    description="Update deployment settings for an endpoint",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_MANAGE])
async def update_deployment_settings(
    endpoint_id: UUID,
    request: UpdateDeploymentSettingsRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    x_resource_type: Annotated[Optional[str], Header()] = None,
    x_entity_id: Annotated[Optional[str], Header()] = None,
) -> Union[DeploymentSettingsResponse, ErrorResponse]:
    """Update deployment settings for an endpoint."""
    try:
        deployment_settings = await EndpointService(session).update_deployment_settings(
            endpoint_id=endpoint_id,
            settings=request,
            current_user_id=current_user.id,
        )
        return DeploymentSettingsResponse(
            endpoint_id=endpoint_id,
            deployment_settings=deployment_settings,
            message="Successfully updated deployment settings",
        ).to_http_response()
    except ClientException as e:
        logger.exception(f"Failed to update deployment settings: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to update deployment settings: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to update deployment settings"
        ).to_http_response()


@endpoint_router.get(
    "/{endpoint_id}/autoscale",
    responses={
        status.HTTP_200_OK: {
            "model": AutoscaleConfigResponse,
            "description": "Successfully retrieved autoscale configuration",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Endpoint not found",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Failed to get autoscale configuration",
        },
    },
    description="Get autoscale configuration for an endpoint",
)
@require_permissions_or_internal(permissions=[PermissionEnum.ENDPOINT_VIEW])
async def get_autoscale_config(
    endpoint_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user_or_internal)],
    session: Annotated[Session, Depends(get_session)],
    x_resource_type: Annotated[Optional[str], Header()] = None,
    x_entity_id: Annotated[Optional[str], Header()] = None,
) -> Union[AutoscaleConfigResponse, ErrorResponse]:
    """Get autoscale configuration for an endpoint."""
    try:
        autoscale_config = await EndpointService(session).get_autoscale_config(
            endpoint_id=endpoint_id,
            current_user_id=current_user.id,
        )
        return autoscale_config.to_http_response()
    except ClientException as e:
        logger.exception(f"Failed to get autoscale config: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get autoscale config: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get autoscale configuration"
        ).to_http_response()


@endpoint_router.put(
    "/{endpoint_id}/autoscale",
    responses={
        status.HTTP_200_OK: {
            "model": AutoscaleConfigResponse,
            "description": "Successfully updated autoscale configuration",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Invalid autoscale configuration",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Endpoint not found",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Failed to update autoscale configuration",
        },
    },
    description="Update autoscale configuration for an endpoint",
)
@require_permissions_or_internal(permissions=[PermissionEnum.ENDPOINT_MANAGE])
async def update_autoscale_config(
    endpoint_id: UUID,
    request: UpdateAutoscaleRequest,
    current_user: Annotated[User, Depends(get_current_active_user_or_internal)],
    session: Annotated[Session, Depends(get_session)],
    x_resource_type: Annotated[Optional[str], Header()] = None,
    x_entity_id: Annotated[Optional[str], Header()] = None,
) -> Union[AutoscaleConfigResponse, ErrorResponse]:
    """Update autoscale configuration for an endpoint.

    This endpoint allows updating the BudAIScaler configuration for a deployment
    that has already been created. It communicates with budcluster to apply the
    new autoscale settings via Helm upgrade.
    """
    try:
        autoscale_response = await EndpointService(session).update_autoscale_config(
            endpoint_id=endpoint_id,
            request=request,
            current_user_id=current_user.id,
        )
        return autoscale_response.to_http_response()
    except ClientException as e:
        logger.exception(f"Failed to update autoscale config: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to update autoscale config: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to update autoscale configuration"
        ).to_http_response()
