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

"""Defines metadata routes for the microservices, providing endpoints for retrieving service-level information."""

from datetime import datetime, timezone
from typing import Annotated, List, Optional
from uuid import UUID

from budmicroframe.commons import logging
from budmicroframe.commons.schemas import ErrorResponse, SuccessResponse, WorkflowMetadataResponse
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..commons.dependencies import get_session, parse_ordering_fields
from ..commons.exceptions import KubernetesException
from .schemas import (
    AdapterRequest,
    DeleteDeploymentRequest,
    DeleteWorkerRequest,
    DeploymentCreateRequest,
    DeployQuantizationRequest,
    WorkerDetailResponse,
    WorkerInfo,
    WorkerInfoFilter,
    WorkerInfoResponse,
    WorkerLogsResponse,
    WorkerMetricsResponse,
)
from .services import AdapterService, DeploymentOpsService, DeploymentService, QuantizationService, WorkerInfoService


logger = logging.get_logger(__name__)

deployment_router = APIRouter(prefix="/deployment")


@deployment_router.post(
    "",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_200_OK: {
            "model": WorkflowMetadataResponse,
            "description": "Deployment created successfully",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Cluster not found",
        },
    },
    status_code=status.HTTP_200_OK,
    description="Creates a new deployment",
    tags=["Deployments"],
)
async def create_deployment(deployment: DeploymentCreateRequest, session: Session = Depends(get_session)):  # noqa: B008
    """Create a new deployment.

    This function triggers the process of creating a new deployment by fetching configuration from simulator service.
    Steps:
    1. Verify the cluster connection
    2. Tranferring model
    3. Deploying engine
    4. Verifying deployment health
    5. Run performance benchmark

    If benchmark is not within user required limits, deploy engine with new configuration from simulator service.

    Args:
        deployment (DeploymentCreateRequest): The request object contains cluster_id and simulator_id.

    Returns:
        DeploymentResponse: A response object containing the workflow id, steps and deployment info.
    """
    try:
        response = await DeploymentService(session).create_deployment(deployment)
    except Exception as e:
        response = ErrorResponse(message=str(e))
    return response.to_http_response()


@deployment_router.post(
    "/cancel/{workflow_id}",
    responses={
        status.HTTP_200_OK: {
            "model": SuccessResponse,
            "description": "Deployment cancelled successfully",
        },
    },
    status_code=status.HTTP_200_OK,
    description="Cancels a deployment",
    tags=["Deployments"],
)
def cancel_deployment(
    workflow_id: UUID,
    session: Session = Depends(get_session),  # noqa: B008
    background_tasks: BackgroundTasks = BackgroundTasks(),  # noqa: B008
):
    """Cancel a deployment.

    Args:
        workflow_id (UUID): The workflow id.
        background_tasks (BackgroundTasks): The background tasks.

    Returns:
        SuccessResponse: A response object containing the success message.
        ErrorResponse: A response object containing the error message.
    """
    try:
        response = DeploymentService(session).cancel_deployment(workflow_id, background_tasks)
    except Exception as e:
        response = ErrorResponse(message=str(e))
    return response.to_http_response()


@deployment_router.post(
    "/periodic-deployment-status-update",
    responses={
        status.HTTP_200_OK: {
            "model": SuccessResponse,
            "description": "Periodic deployment status update triggered successfully",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Internal server error",
        },
    },
    status_code=status.HTTP_200_OK,
    description="Periodic job endpoint to update deployment status for all active deployments",
    tags=["Deployments"],
)
async def periodic_deployment_status_update():
    """Periodic job endpoint to update deployment status for all active deployments.

    This endpoint is triggered by a Dapr cron binding every 3 minutes to keep
    deployment status up-to-date. It implements batch processing and state
    management to prevent resource exhaustion.

    Returns:
        SuccessResponse: If updates were triggered successfully with counts
        ErrorResponse: If there was an error triggering updates
    """
    try:
        trigger_time = datetime.now(timezone.utc)
        logger.info(f"Periodic deployment status update triggered at {trigger_time.isoformat()}")

        response = await DeploymentOpsService.trigger_periodic_deployment_status_update()

        completion_time = datetime.now(timezone.utc)
        duration = (completion_time - trigger_time).total_seconds()

        logger.info(
            f"Periodic deployment status update completed in {duration:.2f}s: "
            f"{response.message if hasattr(response, 'message') else 'success'}"
        )

        return response.to_http_response()
    except Exception as e:
        logger.exception(f"Error in periodic deployment status update: {e}")
        return ErrorResponse(message=f"Error in periodic deployment status update: {str(e)}").to_http_response()


@deployment_router.post(
    "/delete",
    responses={
        status.HTTP_200_OK: {
            "model": WorkflowMetadataResponse,
            "description": "Delete deployment workflow initiated",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Internal server error",
        },
    },
    status_code=status.HTTP_200_OK,
    description="Deletes a deployment",
    tags=["Deployments"],
)
async def delete_deployment(
    delete_deployment_request: DeleteDeploymentRequest,
    session: Session = Depends(get_session),  # noqa: B008
):
    """Delete a deployment.

    Args:
        delete_deployment_request (DeleteDeploymentRequest): The request object contains namespace and cluster_id.

    Returns:
        WorkflowMetadataResponse: A response object containing the workflow id, steps.
        ErrorResponse: A response object containing the error message.
    """
    try:
        response = await DeploymentService(session).delete_deployment(delete_deployment_request)
    except Exception as e:
        response = ErrorResponse(
            message=str(e),
            param=delete_deployment_request.model_dump(mode="json"),
        )
    return response.to_http_response()


@deployment_router.get(
    "/worker-info",
    responses={
        status.HTTP_200_OK: {
            "model": WorkerInfoResponse,
            "description": "Worker info retrieved successfully",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Worker info not found",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Internal server error",
        },
    },
    description="Get workers info",
    tags=["Worker Info"],
)
async def get_workers_info(
    session: Annotated[Session, Depends(get_session)],
    filters: Annotated[WorkerInfoFilter, Depends()],
    cluster_id: UUID = Query(...),  # noqa: B008
    namespace: str = Query(...),  # noqa: B008
    refresh: bool = Query(False),  # noqa: B008
    page: int = Query(1, ge=1),  # noqa: B008
    limit: int = Query(10, ge=0),  # noqa: B008
    order_by: Optional[List[str]] = Depends(parse_ordering_fields),  # noqa: B008
    search: bool = False,  # noqa: B008
):
    """Get workers info."""
    offset = (page - 1) * limit
    filters_dict = filters.model_dump(exclude_none=True)
    logger.info(f"Routes: filters_dict: {filters_dict}")

    try:
        worker_info_response, count = await WorkerInfoService(session).get_workers_info(
            filters_dict, cluster_id, namespace, refresh, offset, limit, order_by, search
        )
        response = WorkerInfoResponse(
            workers=worker_info_response,
            total_record=count,
            page=page,
            limit=limit,
            object="workers.list",
            code=status.HTTP_200_OK,
            message="Worker info retrieved successfully",
        )
    except Exception as e:
        import traceback

        logger.exception(f"Failed to get workers info: {e}")
        logger.exception(traceback.format_exc())
        response = ErrorResponse(message="Failed to get workers info", code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    return response.to_http_response()


@deployment_router.get(
    "/worker-info/{worker_id}/logs",
    responses={
        status.HTTP_200_OK: {
            "model": WorkerLogsResponse,
            "description": "Worker logs retrieved successfully",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Worker logs not found",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Internal server error",
        },
    },
    description="Get worker logs",
    tags=["Worker logs"],
)
async def get_worker_logs(
    worker_id: UUID,
    session: Session = Depends(get_session),  # noqa: B008
):
    """Get worker logs."""
    try:
        filters = {"id": worker_id}
        response = await WorkerInfoService(session).get_worker_logs(filters)

        if response is None:
            return ErrorResponse(message="Worker logs not found", code=status.HTTP_404_NOT_FOUND)

        response = WorkerLogsResponse(
            logs=response,
            message="Worker logs retrieved successfully",
            code=status.HTTP_200_OK,
            object="worker.logs",
        )
    except Exception as e:
        response = ErrorResponse(message=str(e), code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    return response.to_http_response()


@deployment_router.get(
    "/worker-info/{worker_id}/metrics",
    responses={
        status.HTTP_200_OK: {
            "model": WorkerMetricsResponse,
            "description": "Worker metrics retrieved successfully",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Worker metrics not found",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Internal server error",
        },
    },
    description="Get worker metrics from Prometheus",
    tags=["Worker metrics"],
)
async def get_worker_metrics(
    worker_id: UUID,
    session: Session = Depends(get_session),  # noqa: B008
):
    """Get worker metrics from Prometheus.

    Args:
        worker_id: UUID of the worker to get metrics for
        session: Database session

    Returns:
        WorkerMetricsResponse: Response containing memory and CPU metrics
        ErrorResponse: If worker not found or error occurs
    """
    try:
        # Get worker metrics from service
        filters = {"id": worker_id}
        metrics = await WorkerInfoService(session).get_worker_metrics(filters)

        logger.debug(f"::METRICS:: Metrics: {metrics}")

        if metrics is None:
            logger.warning(f"No metrics found for worker with ID: {worker_id}")
            return ErrorResponse(
                message="Worker metrics not found", code=status.HTTP_404_NOT_FOUND, param={"worker_id": str(worker_id)}
            ).to_http_response()

        # Construct successful response
        return WorkerMetricsResponse(
            data=metrics,
            message="Worker metrics retrieved successfully",
            code=status.HTTP_200_OK,
            object="worker.metrics",
        ).to_http_response()

    except Exception as e:
        logger.exception(f"Error retrieving metrics for worker {worker_id}: {e}")
        return ErrorResponse(
            message="Failed to retrieve worker metrics",
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            param={"worker_id": str(worker_id), "error": str(e)},
        ).to_http_response()


@deployment_router.get(
    "/worker-info/{worker_id}",
    responses={
        status.HTTP_200_OK: {
            "model": WorkerDetailResponse,
            "description": "Worker info retrieved successfully",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Worker info not found",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Internal server error",
        },
    },
    description="Get worker detail",
    tags=["Worker Info"],
)
async def get_worker_detail(
    worker_id: UUID,
    reload: bool = Query(False),  # noqa: B008
    session: Session = Depends(get_session),  # noqa: B008
):
    """Get worker detail."""
    try:
        filters = {"id": worker_id}
        worker_detail = await WorkerInfoService(session).get_worker_detail(filters, reload=reload)
        response = WorkerDetailResponse(
            worker=WorkerInfo.model_validate(worker_detail),
            message="Worker detail retrieved successfully",
            code=status.HTTP_200_OK,
            object="worker.get",
        )
    except KubernetesException as e:
        response = ErrorResponse(message=e.message, code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except HTTPException as e:
        response = ErrorResponse(message=e.detail, code=e.status_code)
    except Exception as e:
        logger.exception(f"Failed to get worker detail: {e}")
        response = ErrorResponse(message="Failed to get worker detail", code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    return response.to_http_response()


@deployment_router.delete(
    "/worker-info",
    responses={
        status.HTTP_200_OK: {
            "model": SuccessResponse,
            "description": "Worker deleted successfully",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Internal server error",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Worker not found",
        },
    },
    description="Delete a worker",
    tags=["Worker Info"],
)
async def delete_worker(
    delete_worker_request: DeleteWorkerRequest,
    session: Session = Depends(get_session),  # noqa: B008
):
    """Delete a worker."""
    try:
        response = await WorkerInfoService(session).delete_worker(delete_worker_request)
    except HTTPException as e:
        response = ErrorResponse(message=e.detail, code=e.status_code)
    except Exception as e:
        logger.exception(f"Failed to delete worker: {e}")
        response = ErrorResponse(message="Failed to delete worker", code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    return response.to_http_response()


@deployment_router.post(
    "/deploy-quantization",
    responses={
        status.HTTP_200_OK: {
            "model": SuccessResponse,
            "description": "Quantization deployed successfully",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Internal server error",
        },
    },
    description="Deploy quantization",
    tags=["Quantization"],
)
async def deploy_quantization(
    deploy_quantization_request: DeployQuantizationRequest,
    session: Session = Depends(get_session),  # noqa: B008
):
    """Deploy quantization."""
    try:
        response = await QuantizationService(session).deploy_quantization(deploy_quantization_request)
    except Exception as e:
        response = ErrorResponse(message=str(e))
    return response.to_http_response()


@deployment_router.post(
    "/deploy-adapter",
    responses={
        status.HTTP_200_OK: {
            "model": SuccessResponse,
            "description": "Adapter added successfully",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Internal server error",
        },
    },
    description="Add adapter",
    tags=["Adapter"],
)
async def deploy_adapter(
    add_adapter_request: AdapterRequest,
    session: Session = Depends(get_session),  # noqa: B008
):
    """Add adapter."""
    try:
        response = await AdapterService(session).deploy_adapter(add_adapter_request)
    except Exception as e:
        response = ErrorResponse(message=str(e))
    return response.to_http_response()
