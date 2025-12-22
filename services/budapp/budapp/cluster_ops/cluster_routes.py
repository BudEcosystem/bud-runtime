# budapp/cluster_ops/cluster_routes.py
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

"""The cluster ops package, containing essential business logic, services, and routing configurations for the cluster ops."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

import aiohttp
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.exceptions import RequestValidationError
from pydantic import AnyHttpUrl, BaseModel, ValidationError
from sqlalchemy.orm import Session
from typing_extensions import Annotated

from budapp.commons import logging
from budapp.commons.config import app_settings
from budapp.commons.dependencies import (
    get_current_active_user,
    get_session,
    parse_ordering_fields,
)
from budapp.commons.exceptions import ClientException
from budapp.commons.schemas import ErrorResponse, SuccessResponse
from budapp.shared.dapr_service import DaprService
from budapp.shared.grafana import Grafana
from budapp.user_ops.schemas import User
from budapp.workflow_ops.schemas import RetrieveWorkflowDataResponse
from budapp.workflow_ops.services import WorkflowService

from ..commons.constants import PermissionEnum
from ..commons.permission_handler import require_permissions
from .schemas import (
    CancelClusterOnboardingRequest,
    ClusterEndpointFilter,
    ClusterEndpointPaginatedResponse,
    ClusterFilter,
    ClusterListResponse,
    ClusterMetricsResponse,
    ClusterNodeWiseEventsResponse,
    ClusterSettingsDetailResponse,
    CreateClusterSettingsRequest,
    CreateClusterWorkflowRequest,
    EditClusterRequest,
    GrafanaDashboardResponse,
    MetricTypeEnum,
    NodeMetricsResponse,
    RecommendedClusterResponse,
    SingleClusterResponse,
    UpdateClusterSettingsRequest,
)
from .services import ClusterService
from .workflows import ClusterRecommendedSchedulerWorkflows


logger = logging.get_logger(__name__)

cluster_router = APIRouter(prefix="/clusters", tags=["cluster"])


@cluster_router.get(
    "/{cluster_id}/grafana-dashboard",
    responses={
        status.HTTP_200_OK: {
            "model": GrafanaDashboardResponse,
            "description": "Successfully retrieved Grafana dashboard URL",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
    },
    description="Get Grafana dashboard URL by cluster id",
)
@require_permissions(permissions=[PermissionEnum.CLUSTER_VIEW])
async def get_grafana_dashboard_url(
    cluster_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Union[GrafanaDashboardResponse, ErrorResponse]:
    """Get Grafana dashboard URL by cluster id."""
    try:
        cluster_details = await ClusterService(session).get_cluster_details(cluster_id)
        grafana = Grafana()
        url = grafana.get_public_dashboard_url_by_uid(cluster_details.cluster_id)
        return GrafanaDashboardResponse(
            message="Successfully retrieved Grafana dashboard URL",
            code=status.HTTP_200_OK,
            object="cluster.grafana-dashboard",
            url=url,
        )
    except Exception as e:
        logger.exception(f"Error retrieving Grafana dashboard URL: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Error retrieving Grafana dashboard URL",
        ).to_http_response()


@cluster_router.get(
    "/clusters/{cluster_id}/metrics/summary",
    response_model=None,
    description="Get cluster metrics summary",
)
async def get_cluster_metrics_summary(
    cluster_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Get cluster metrics summary from budmetrics service."""
    try:
        # Check cluster access
        cluster_service = ClusterService(session)
        cluster = await cluster_service.get_cluster_details(UUID(cluster_id))
        if not cluster:
            return ErrorResponse(
                code=status.HTTP_404_NOT_FOUND,
                message="Cluster not found",
            ).to_http_response()

        # Forward to budmetrics (use cluster.cluster_id which is the budcluster ID)
        result = await DaprService.invoke_service(
            "budmetrics",
            f"cluster-metrics/{cluster.cluster_id}/summary",
            method="GET",
        )
        return result
    except Exception as e:
        logger.exception(f"Error getting cluster metrics summary: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Error retrieving cluster metrics",
        ).to_http_response()


@cluster_router.get(
    "/clusters/{cluster_id}/metrics/nodes",
    response_model=None,
    description="Get cluster node metrics",
)
async def get_cluster_node_metrics(
    cluster_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
):
    """Get cluster node metrics from budmetrics service."""
    try:
        # Check cluster access
        cluster_service = ClusterService(session)
        cluster = await cluster_service.get_cluster_details(UUID(cluster_id))
        if not cluster:
            return ErrorResponse(
                code=status.HTTP_404_NOT_FOUND,
                message="Cluster not found",
            ).to_http_response()

        # Build query params
        params = {}
        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time

        # Forward to budmetrics (use cluster.cluster_id which is the budcluster ID)
        result = await DaprService.invoke_service(
            "budmetrics",
            f"cluster-metrics/{cluster.cluster_id}/nodes",
            method="GET",
            params=params,
        )
        return result
    except Exception as e:
        logger.exception(f"Error getting cluster node metrics: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Error retrieving node metrics",
        ).to_http_response()


@cluster_router.get(
    "/clusters/{cluster_id}/metrics/pods",
    response_model=None,
    description="Get cluster pod metrics",
)
async def get_cluster_pod_metrics(
    cluster_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    namespace: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
):
    """Get cluster pod metrics from budmetrics service."""
    try:
        # Check cluster access
        cluster_service = ClusterService(session)
        cluster = await cluster_service.get_cluster_details(UUID(cluster_id))
        if not cluster:
            return ErrorResponse(
                code=status.HTTP_404_NOT_FOUND,
                message="Cluster not found",
            ).to_http_response()

        # Build query params
        params = {}
        if namespace:
            params["namespace"] = namespace
        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time

        # Forward to budmetrics (use cluster.cluster_id which is the budcluster ID)
        result = await DaprService.invoke_service(
            "budmetrics",
            f"cluster-metrics/{cluster.cluster_id}/pods",
            method="GET",
            params=params,
        )
        return result
    except Exception as e:
        logger.exception(f"Error getting cluster pod metrics: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Error retrieving pod metrics",
        ).to_http_response()


@cluster_router.get(
    "/clusters/{cluster_id}/metrics/health",
    response_model=None,
    description="Get cluster health status",
)
async def get_cluster_health_status(
    cluster_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Get cluster health status from budmetrics service."""
    try:
        # Check cluster access
        cluster_service = ClusterService(session)
        cluster = await cluster_service.get_cluster_details(UUID(cluster_id))
        if not cluster:
            return ErrorResponse(
                code=status.HTTP_404_NOT_FOUND,
                message="Cluster not found",
            ).to_http_response()

        # Forward to budmetrics (use cluster.cluster_id which is the budcluster ID)
        result = await DaprService.invoke_service(
            "budmetrics",
            f"cluster-metrics/{cluster.cluster_id}/health",
            method="GET",
        )
        return result
    except Exception as e:
        logger.exception(f"Error getting cluster health status: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Error retrieving health status",
        ).to_http_response()


@cluster_router.post(
    "/clusters/{cluster_id}/metrics/query",
    response_model=None,
    description="Query custom cluster metrics",
)
async def query_cluster_metrics(
    cluster_id: str,
    query: dict,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Query custom cluster metrics from budmetrics service."""
    try:
        # Check cluster access
        cluster_service = ClusterService(session)
        cluster = await cluster_service.get_cluster_details(UUID(cluster_id))
        if not cluster:
            return ErrorResponse(
                code=status.HTTP_404_NOT_FOUND,
                message="Cluster not found",
            ).to_http_response()

        # Ensure cluster_id is in the query data for budmetrics (use budcluster ID)
        query["cluster_id"] = str(cluster.cluster_id)

        # Forward to budmetrics
        result = await DaprService.invoke_service(
            "budmetrics",
            "cluster-metrics/query",
            method="POST",
            data=query,
        )
        return result
    except Exception as e:
        logger.exception(f"Error querying cluster metrics: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Error querying metrics",
        ).to_http_response()


@cluster_router.post(
    "/clusters",
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
            "description": "Create cluster workflow executed successfully",
        },
    },
    description="Create cluster workflow",
)
@require_permissions(permissions=[PermissionEnum.CLUSTER_MANAGE])
async def create_cluster_workflow(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    step_number: Annotated[int, Form(gt=0)],
    name: Annotated[str | None, Form(min_length=1, max_length=100)] = None,
    icon: Annotated[str | None, Form(min_length=1, max_length=100)] = None,
    ingress_url: Annotated[AnyHttpUrl | None, Form()] = None,
    configuration_file: Annotated[
        UploadFile | None, File(description="The configuration file for the cluster")
    ] = None,
    workflow_id: Annotated[UUID | None, Form()] = None,
    workflow_total_steps: Annotated[int | None, Form()] = None,
    trigger_workflow: Annotated[bool, Form()] = False,
    # Cloud Cluster
    cluster_type: Annotated[str, Form(description="Type of cluster", enum=["ON_PREM", "CLOUD"])] = "ON_PREM",
    # Cluster Specific Inputs
    credential_id: Annotated[UUID | None, Form()] = None,
    provider_id: Annotated[UUID | None, Form()] = None,
    region: Annotated[str | None, Form()] = None,
) -> Union[RetrieveWorkflowDataResponse, ErrorResponse]:
    """Create cluster workflow."""
    # Perform router level validation
    if workflow_id is None and workflow_total_steps is None:
        return ErrorResponse(
            code=status.HTTP_400_BAD_REQUEST,
            message="workflow_total_steps is required when workflow_id is not provided",
        ).to_http_response()

    if workflow_id is not None and workflow_total_steps is not None:
        return ErrorResponse(
            code=status.HTTP_400_BAD_REQUEST,
            message="workflow_total_steps and workflow_id cannot be provided together",
        ).to_http_response()

    if cluster_type == "CLOUD" and workflow_id is not None and trigger_workflow:
        # validate all the details are
        required_fields = [credential_id, provider_id, region]
        if None in required_fields:
            return ErrorResponse(
                code=status.HTTP_400_BAD_REQUEST,
                message="credential_id, provider_id, and region are required for CLOUD cluster creation",
            ).to_http_response()

    # Check if at least one of the other fields is provided
    other_fields = [name, ingress_url, configuration_file]
    required_fields = ["name", "ingress_url", "configuration_file"]
    if not any(other_fields):
        return ErrorResponse(
            code=status.HTTP_400_BAD_REQUEST,
            message=f"At least one of {', '.join(required_fields)} is required when workflow_id is provided",
        )

    try:
        db_workflow = await ClusterService(session).create_cluster_workflow(
            current_user_id=current_user.id,
            request=CreateClusterWorkflowRequest(
                name=name,
                icon=icon,
                ingress_url=str(ingress_url) if ingress_url else None,
                workflow_id=workflow_id,
                workflow_total_steps=workflow_total_steps,
                step_number=step_number,
                trigger_workflow=trigger_workflow,
                credential_id=credential_id,
                provider_id=provider_id,
                region=region,
                cluster_type=cluster_type,
            ),
            configuration_file=configuration_file,
        )

        return await WorkflowService(session).retrieve_workflow_data(db_workflow.id)
    except ClientException as e:
        logger.exception(f"Failed to execute create cluster workflow: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except ValidationError as e:
        logger.exception(f"ValidationErrors: {str(e)}")
        raise RequestValidationError(e.errors())
    except Exception as e:
        logger.error(f"Error occurred while executing create cluster workflow: {str(e)}", exc_info=True)
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to execute create cluster workflow"
        ).to_http_response()


@cluster_router.get(
    "/clusters",
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
            "model": ClusterListResponse,
            "description": "Successfully listed all clusters",
        },
    },
    description="List all clusters",
)
@require_permissions(permissions=[PermissionEnum.CLUSTER_VIEW])
async def list_clusters(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    filters: ClusterFilter = Depends(),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=0),
    order_by: Optional[List[str]] = Depends(parse_ordering_fields),
    search: bool = False,
) -> Union[ClusterListResponse, ErrorResponse]:
    """List all clusters."""
    offset = (page - 1) * limit

    filters_dict = filters.model_dump(exclude_none=True)

    try:
        db_clusters, count = await ClusterService(session).get_all_active_clusters(
            offset, limit, filters_dict, order_by, search
        )
    except Exception as e:
        logger.error(f"Error occurred while listing clusters: {str(e)}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to list clusters"
        ).to_http_response()

    return ClusterListResponse(
        clusters=db_clusters,
        total_record=count,
        page=page,
        limit=limit,
        object="cluster.list",
        code=status.HTTP_200_OK,
    ).to_http_response()


@cluster_router.patch(
    "/{cluster_id}",
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
            "model": SingleClusterResponse,
            "description": "Successfully edited cluster",
        },
    },
    description="Edit cluster",
)
@require_permissions(permissions=[PermissionEnum.CLUSTER_MANAGE])
async def edit_cluster(
    cluster_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    edit_cluster: EditClusterRequest,
) -> Union[SingleClusterResponse, ErrorResponse]:
    """Edit cluster."""
    try:
        db_cluster = await ClusterService(session).edit_cluster(
            cluster_id=cluster_id, data=edit_cluster.model_dump(exclude_unset=True, exclude_none=True)
        )
        return SingleClusterResponse(
            cluster=db_cluster,
            message="Cluster details updated successfully",
            code=status.HTTP_200_OK,
            object="cluster.edit",
        )
    except ClientException as e:
        logger.exception(f"Failed to edit cluster: {e}")
        return ErrorResponse(code=status.HTTP_400_BAD_REQUEST, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to edit cluster: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to edit cluster"
        ).to_http_response()


@cluster_router.get(
    "/{cluster_id}",
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
            "model": SingleClusterResponse,
            "description": "Successfully retrieved cluster details",
        },
    },
    description="Retrieve details of a cluster by ID",
)
@require_permissions(permissions=[PermissionEnum.CLUSTER_VIEW])
async def get_cluster_details(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    cluster_id: UUID,
) -> Union[SingleClusterResponse, ErrorResponse]:
    """Retrieve details of a cluster by its ID."""
    try:
        cluster_details = await ClusterService(session).get_cluster_details(cluster_id)
    except ClientException as e:
        logger.exception(f"Failed to get cluster details: {e}")
        return ErrorResponse(code=status.HTTP_400_BAD_REQUEST, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get cluster details: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve cluster details",
        ).to_http_response()

    return SingleClusterResponse(
        cluster=cluster_details,
        message="Cluster details fetched successfully",
        code=status.HTTP_200_OK,
        object="cluster.get",
    )


@cluster_router.post(
    "/{cluster_id}/delete-workflow",
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
            "model": SuccessResponse,
            "description": "Successfully executed delete cluster workflow",
        },
    },
    description="Delete a cluster by ID",
)
@require_permissions(permissions=[PermissionEnum.CLUSTER_MANAGE])
async def delete_cluster(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    cluster_id: UUID,
) -> Union[SuccessResponse, ErrorResponse]:
    """Delete a cluster by its ID."""
    try:
        db_workflow = await ClusterService(session).delete_cluster(cluster_id, current_user.id)
        logger.debug(f"Cluster deleting initiated with workflow id: {db_workflow.id}")
        return SuccessResponse(
            message="Cluster deleting initiated successfully",
            code=status.HTTP_200_OK,
            object="cluster.delete",
        )
    except ClientException as e:
        logger.exception(f"Failed to delete cluster: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to delete cluster: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to delete cluster",
        ).to_http_response()


@cluster_router.post(
    "/cancel-onboarding",
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
            "description": "Successfully cancel cluster onboarding",
        },
    },
    description="Cancel cluster onboarding",
)
@require_permissions(permissions=[PermissionEnum.CLUSTER_MANAGE])
async def cancel_cluster_onboarding(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    cancel_request: CancelClusterOnboardingRequest,
) -> Union[SuccessResponse, ErrorResponse]:
    """Cancel cluster onboarding."""
    try:
        await ClusterService(session).cancel_cluster_onboarding_workflow(cancel_request.workflow_id)
        return SuccessResponse(
            message="Cluster onboarding cancelled successfully",
            code=status.HTTP_200_OK,
            object="cluster.cancel",
        )
    except ClientException as e:
        logger.exception(f"Failed to cancel cluster onboarding: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to cancel cluster onboarding: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to cancel cluster onboarding"
        ).to_http_response()


@cluster_router.get(
    "/{cluster_id}/endpoints",
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
            "model": ClusterEndpointPaginatedResponse,
            "description": "Successfully listed all endpoints in the cluster",
        },
    },
    description="List all endpoints in a cluster.\n\nOrder by values are: name, status, created_at, project_name, model_name.",
)
@require_permissions(permissions=[PermissionEnum.CLUSTER_VIEW])
async def list_all_endpoints(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    cluster_id: UUID,
    filters: Annotated[ClusterEndpointFilter, Depends()],
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=0),
    order_by: Optional[List[str]] = Depends(parse_ordering_fields),
    search: bool = False,
) -> Union[ClusterEndpointPaginatedResponse, ErrorResponse]:
    """List all endpoints in a cluster."""
    # Calculate offset
    offset = (page - 1) * limit

    # Construct filters
    filters_dict = filters.model_dump(exclude_none=True, exclude_unset=True)

    try:
        result, count = await ClusterService(session).get_all_endpoints_in_cluster(
            cluster_id, offset, limit, filters_dict, order_by, search
        )
    except ClientException as e:
        logger.exception(f"Failed to get all endpoints: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get all endpoints: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get all endpoints"
        ).to_http_response()

    return ClusterEndpointPaginatedResponse(
        endpoints=result,
        total_record=count,
        page=page,
        limit=limit,
        object="cluster.endpoints.list",
        code=status.HTTP_200_OK,
        message="Successfully listed all endpoints in the cluster",
    ).to_http_response()


# Cluster Metrics Endpoint
@cluster_router.get(
    "/{cluster_id}/metrics",
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
            "model": ClusterMetricsResponse,
            "description": "Successfully retrieved cluster metrics",
        },
    },
    description="Get detailed metrics for a specific cluster including CPU, memory, disk, GPU, HPU, and network statistics. Use metric_type to filter specific metrics.",
)
@require_permissions(permissions=[PermissionEnum.CLUSTER_VIEW])
async def get_cluster_metrics(
    cluster_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    filter: str = Query("today", enum=["today", "7days", "month"]),
    metric_type: MetricTypeEnum = Query(MetricTypeEnum.ALL, description="Type of metrics to return"),
) -> Union[ClusterMetricsResponse, ErrorResponse]:
    """Get cluster metrics from BudMetrics service via ClickHouse.

    This endpoint queries the BudMetrics service which retrieves data from ClickHouse
    instead of directly querying Prometheus. The data flows through:
    Prometheus → BudCluster → OTel Collector → ClickHouse → BudMetrics → BudApp
    """
    try:
        # Check cluster access
        cluster_service = ClusterService(session)
        cluster = await cluster_service.get_cluster_details(cluster_id)
        if not cluster:
            return ErrorResponse(
                code=status.HTTP_404_NOT_FOUND,
                message="Cluster not found",
            ).to_http_response()

        # Forward to budmetrics prometheus-compatible endpoint via Dapr sidecar
        # This endpoint returns the same format as the old Prometheus-based implementation
        metrics_endpoint = (
            f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_metrics_app_id}/"
            f"method/cluster-metrics/{cluster.cluster_id}/prometheus-compatible"
        )

        async with aiohttp.ClientSession() as http_session:
            async with http_session.get(
                metrics_endpoint,
                params={
                    "filter": filter,
                    "metric_type": metric_type.value.lower(),
                },
            ) as response:
                response_data = await response.json()

                if response.status != status.HTTP_200_OK:
                    logger.error(f"Cluster metrics request failed: status={response.status}, response={response_data}")
                    error_detail = response_data.get("detail", "Failed to retrieve cluster metrics")
                    raise ClientException(
                        error_detail if isinstance(error_detail, str) else "Failed to retrieve cluster metrics",
                        status_code=response.status,
                    )

                # Add required 'message' field for SuccessResponse validation
                response_data["message"] = "Successfully retrieved cluster metrics"
                return ClusterMetricsResponse(**response_data)

    except ClientException as e:
        return ErrorResponse(
            code=status.HTTP_400_BAD_REQUEST,
            message=str(e),
        ).to_http_response()
    except Exception as e:
        logger.exception(f"Error retrieving cluster metrics: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Error retrieving cluster metrics",
        ).to_http_response()


@cluster_router.get(
    "/{cluster_id}/node-metrics",
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
            "model": NodeMetricsResponse,
            "description": "Successfully retrieved node-wise metrics",
        },
    },
    description="Get node-wise metrics for a cluster",
)
@require_permissions(permissions=[PermissionEnum.CLUSTER_VIEW])
async def get_node_wise_metrics(
    cluster_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Union[NodeMetricsResponse, ErrorResponse]:
    """Get node-wise metrics for a cluster."""
    try:
        metrics = await ClusterService(session).get_node_wise_metrics(cluster_id)

        return NodeMetricsResponse(code=status.HTTP_200_OK, message="Successfully retrieved node metrics", **metrics)
    except ClientException as e:
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Error retrieving node-wise metrics: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Error retrieving node-wise metrics",
        ).to_http_response()


@cluster_router.get(
    "/{cluster_id}/node-events/{node_hostname}",
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
            "model": ClusterNodeWiseEventsResponse,
            "description": "Successfully retrieved node-wise metrics by hostname with pagination",
        },
    },
    description="Get node-wise Events by hostname with pagination",
)
@require_permissions(permissions=[PermissionEnum.CLUSTER_VIEW])
async def get_node_wise_events_by_hostname(
    cluster_id: UUID,
    node_hostname: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Union[ClusterNodeWiseEventsResponse, ErrorResponse]:
    """Get node-wise metrics by hostname with pagination."""
    try:
        events_raw = await ClusterService(session).get_node_wise_events_by_hostname(cluster_id, node_hostname)

        events = events_raw.get("events", [])

        return ClusterNodeWiseEventsResponse(
            code=status.HTTP_200_OK, message="Successfully retrieved node metrics by hostname", events=events
        )
    except ClientException as e:
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Error retrieving node-wise metrics by hostname: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Error retrieving node-wise metrics by hostname",
        ).to_http_response()


@cluster_router.post("/recommended-scheduler")
async def recommended_scheduler():
    """Recommended scheduler cron job.

    This endpoint processes the recommended scheduler cron job.

    Returns:
        HTTP response containing the recommended scheduler.
    """
    response: Union[SuccessResponse, ErrorResponse]
    try:
        await ClusterRecommendedSchedulerWorkflows().__call__()
        logger.debug("Recommended cluster scheduler triggered")
        response = SuccessResponse(
            message="Recommended cluster scheduler triggered",
            code=status.HTTP_200_OK,
            object="cluster.recommended-scheduler",
        )
    except Exception as e:
        logger.exception("Error recommended scheduler: %s", str(e))
        response = ErrorResponse(message="Error recommended scheduler", code=500)

    return response.to_http_response()


@cluster_router.get(
    "/recommended/{workflow_id}",
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
            "model": RecommendedClusterResponse,
            "description": "Successfully retrieved recommended clusters",
        },
    },
    description="Get all recommended clusters by id",
)
async def get_recommended_clusters(
    workflow_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Union[RecommendedClusterResponse, ErrorResponse]:
    """Get recommended clusters by workflow id."""
    try:
        recommended_clusters = await ClusterService(session).get_recommended_clusters(workflow_id)

        return RecommendedClusterResponse(
            code=status.HTTP_200_OK,
            message="Successfully retrieved recommended clusters",
            clusters=recommended_clusters,
            object="cluster.recommended_clusters",
            workflow_id=workflow_id,
        )
    except ClientException as e:
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Error retrieving recommended clusters: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Error retrieving recommended clusters",
        ).to_http_response()


@cluster_router.get(
    "/internal/get-clusters",
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
            "model": ClusterListResponse,
            "description": "Successfully listed all clusters",
        },
    },
    description="List all clusters (internal service use only)",
)
async def list_clusters_internal(
    session: Annotated[Session, Depends(get_session)],
    filters: ClusterFilter = Depends(),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=0),
    order_by: Optional[List[str]] = Depends(parse_ordering_fields),
    search: bool = False,
) -> Union[ClusterListResponse, ErrorResponse]:
    """List all clusters for internal service use."""
    offset = (page - 1) * limit

    filters_dict = filters.model_dump(exclude_none=True)

    try:
        db_clusters, count = await ClusterService(session).get_all_active_clusters(
            offset, limit, filters_dict, order_by, search
        )
    except Exception as e:
        logger.error(f"Error occurred while listing clusters: {str(e)}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to list clusters"
        ).to_http_response()

    return ClusterListResponse(
        clusters=db_clusters,
        total_record=count,
        page=page,
        limit=limit,
        object="cluster.list",
        code=status.HTTP_200_OK,
    ).to_http_response()


@cluster_router.get(
    "/{cluster_id}/storage-classes",
    responses={
        status.HTTP_200_OK: {
            "model": SuccessResponse,
            "description": "Successfully retrieved storage classes",
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
    description="Get all storage classes available in the cluster",
)
@require_permissions(permissions=[PermissionEnum.CLUSTER_VIEW])
async def get_cluster_storage_classes(
    cluster_id: UUID,
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Get all storage classes available in the cluster."""
    try:
        storage_classes_data = await ClusterService(session).get_cluster_storage_classes(cluster_id)

        # Extract storage classes from the budcluster response
        param_data = storage_classes_data.get("param", {})
        storage_classes = param_data.get("storage_classes", [])

        # Return the data directly as JSON response since SuccessResponse doesn't support param
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "storage_classes": storage_classes,
                "message": storage_classes_data.get("message", "Storage classes retrieved successfully"),
                "object": "cluster.storage-classes",
                "code": status.HTTP_200_OK,
            },
        )
    except ClientException as e:
        logger.error(f"Client error retrieving storage classes for cluster {cluster_id}: {e}")
        return ErrorResponse(
            code=e.status_code,
            message=str(e),
        ).to_http_response()
    except Exception as e:
        logger.exception(f"Error retrieving storage classes for cluster {cluster_id}: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Error retrieving storage classes",
        ).to_http_response()


# ============ HAMI GPU Metrics Routes ============


@cluster_router.get(
    "/{cluster_id}/metrics/gpu",
    response_model=None,
    responses={
        status.HTTP_200_OK: {
            "description": "Successfully retrieved cluster GPU metrics",
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
    description="Get cluster-wide HAMI GPU metrics including device info, slices, and summary",
)
@require_permissions(permissions=[PermissionEnum.CLUSTER_VIEW])
async def get_cluster_gpu_metrics(
    cluster_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Get cluster-wide GPU metrics from budmetrics service.

    Returns GPU device metrics and slice allocations for all nodes in the cluster.
    Includes summary statistics for the entire cluster.
    """
    try:
        # Check cluster access
        cluster_service = ClusterService(session)
        cluster = await cluster_service.get_cluster_details(cluster_id)
        if not cluster:
            return ErrorResponse(
                code=status.HTTP_404_NOT_FOUND,
                message="Cluster not found",
            ).to_http_response()

        # Forward to budmetrics via Dapr service invocation
        # Use cluster.cluster_id (budcluster ID) not cluster_id (budapp ID)
        result = await DaprService.invoke_service(
            app_settings.bud_metrics_app_id,
            f"cluster-metrics/{cluster.cluster_id}/hami-gpu",
            method="GET",
        )
        return result
    except ClientException as e:
        logger.error(f"Client error getting cluster GPU metrics: {e}")
        return ErrorResponse(
            code=e.status_code,
            message=str(e),
        ).to_http_response()
    except Exception as e:
        logger.exception(f"Error getting cluster GPU metrics: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Error retrieving cluster GPU metrics",
        ).to_http_response()


@cluster_router.get(
    "/{cluster_id}/nodes/{hostname}/metrics/gpu",
    response_model=None,
    responses={
        status.HTTP_200_OK: {
            "description": "Successfully retrieved node GPU metrics",
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
    description="Get HAMI GPU metrics for a specific node",
)
@require_permissions(permissions=[PermissionEnum.CLUSTER_VIEW])
async def get_node_gpu_metrics(
    cluster_id: UUID,
    hostname: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Get GPU metrics for a specific node from budmetrics service.

    Returns GPU device metrics and slice allocations for the specified node.
    Includes summary statistics for the node.
    """
    try:
        # Check cluster access
        cluster_service = ClusterService(session)
        cluster = await cluster_service.get_cluster_details(cluster_id)
        if not cluster:
            return ErrorResponse(
                code=status.HTTP_404_NOT_FOUND,
                message="Cluster not found",
            ).to_http_response()

        # Forward to budmetrics via Dapr service invocation
        # Use cluster.cluster_id (budcluster ID) not cluster_id (budapp ID)
        result = await DaprService.invoke_service(
            app_settings.bud_metrics_app_id,
            f"cluster-metrics/{cluster.cluster_id}/nodes/{hostname}/hami-gpu",
            method="GET",
        )
        return result
    except ClientException as e:
        logger.error(f"Client error getting node GPU metrics: {e}")
        return ErrorResponse(
            code=e.status_code,
            message=str(e),
        ).to_http_response()
    except Exception as e:
        logger.exception(f"Error getting node GPU metrics: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Error retrieving node GPU metrics",
        ).to_http_response()


@cluster_router.get(
    "/{cluster_id}/nodes/{hostname}/metrics/gpu/timeseries",
    response_model=None,
    responses={
        status.HTTP_200_OK: {
            "description": "Successfully retrieved GPU timeseries data",
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
    description="Get GPU timeseries data for a specific node for charts",
)
@require_permissions(permissions=[PermissionEnum.CLUSTER_VIEW])
async def get_node_gpu_timeseries(
    cluster_id: UUID,
    hostname: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    hours: int = Query(default=6, ge=1, le=168, description="Number of hours to look back"),
):
    """Get GPU timeseries data for a specific node from budmetrics service.

    Returns historical GPU metrics for charts including utilization,
    memory, temperature, power, and slice activity.
    """
    try:
        # Check cluster access
        cluster_service = ClusterService(session)
        cluster = await cluster_service.get_cluster_details(cluster_id)
        if not cluster:
            return ErrorResponse(
                code=status.HTTP_404_NOT_FOUND,
                message="Cluster not found",
            ).to_http_response()

        # Forward to budmetrics via Dapr service invocation
        # Use cluster.cluster_id (budcluster ID) not cluster_id (budapp ID)
        result = await DaprService.invoke_service(
            app_settings.bud_metrics_app_id,
            f"cluster-metrics/{cluster.cluster_id}/nodes/{hostname}/hami-gpu/timeseries",
            method="GET",
            params={"hours": hours},
        )
        return result
    except ClientException as e:
        logger.error(f"Client error getting GPU timeseries: {e}")
        return ErrorResponse(
            code=e.status_code,
            message=str(e),
        ).to_http_response()
    except Exception as e:
        logger.exception(f"Error getting GPU timeseries: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Error retrieving GPU timeseries",
        ).to_http_response()
