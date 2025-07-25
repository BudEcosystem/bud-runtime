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

import json
import logging
from typing import Annotated, Union
from uuid import UUID

import yaml
from budmicroframe.commons.logging import get_logger
from budmicroframe.commons.schemas import ErrorResponse, SuccessResponse, WorkflowMetadataResponse
from fastapi import APIRouter, BackgroundTasks, Body, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from ..commons.dependencies import get_session
from .schemas import (
    ClusterCreateRequest,
    ClusterDeleteRequest,
    EditClusterRequest,
    NodeEventsCountSuccessResponse,
    NodeEventsResponse,
)
from .services import ClusterOpsService, ClusterService


logger = get_logger(__name__)

cluster_router = APIRouter(prefix="/cluster")


@cluster_router.post(
    "",
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
            "model": WorkflowMetadataResponse,
            "description": "Cluster registering process initiated",
        },
    },
    status_code=status.HTTP_200_OK,
    description="Adds a new cluster to the system",
    tags=["Clusters"],
)
async def register_cluster(
    cluster_create_request: Annotated[str, Form()],
    configuration: Annotated[UploadFile, File()],
    session: Session = Depends(get_session),  # noqa: B008
) -> Union[WorkflowMetadataResponse, ErrorResponse]:
    """Add a new cluster to the db and initiate the registering process.

    This function triggers the process of adding a new cluster to the db and initiating the registering process.

    Args:
        cluster (ClusterCreateRequest): The request object contains metadata for the cluster.

    Returns:
        WorkflowMetadataResponse: A response object containing the workflow id, steps.
        ErrorResponse: A response object containing the error message.
    """
    # Validate yaml configuration file

    try:
        cluster_data = json.loads(cluster_create_request)
        cluster_create_obj = ClusterCreateRequest(**cluster_data)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON in cluster_create_request",
        ) from exc

    logger.info(cluster_create_obj)

    if cluster_create_obj.cluster_type == "ON_PREM":
        # Check if configuration is provided for ON_PREM cluster type
        if not configuration:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Configuration file is required for Exisiting cluster type",
            )

        try:
            config_yaml = await configuration.read()

            logging.debug("Configuration file read successfully")
            logging.debug(config_yaml)

            config_dict = yaml.safe_load(config_yaml)
        except (yaml.YAMLError, Exception) as exc:
            logger.error(exc)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid configuration file",
            ) from exc

        cluster_create_obj.configuration = json.dumps(config_dict)

    cluster_register_response = await ClusterService(session).register_cluster(cluster_create_obj)

    logger.info("Cluster registering process initiated")

    return cluster_register_response.to_http_response()


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
            "model": SuccessResponse,
            "description": "Successfully edited cluster",
        },
    },
    description="Edit cluster",
    tags=["Clusters"],
)
async def edit_cluster(
    cluster_id: UUID,
    session: Annotated[Session, Depends(get_session)],
    edit_cluster: EditClusterRequest,
) -> Union[SuccessResponse, ErrorResponse]:
    """Edit cluster."""
    try:
        db_cluster = await ClusterService(session).edit_cluster(
            cluster_id=cluster_id, data=edit_cluster.model_dump(exclude_unset=True, exclude_none=True)
        )
        response = SuccessResponse(
            param={"cluster_id": str(db_cluster.id), "ingress_url": db_cluster.ingress_url},
            message="Cluster details updated successfully",
            code=status.HTTP_200_OK,
            object="cluster.edit",
        )
    except HTTPException as e:
        logger.exception(f"Failed to edit cluster: {e}")
        response = ErrorResponse(code=e.status_code, message=e.detail)
    except Exception as e:
        logger.exception(f"Failed to edit cluster: {e}")
        response = ErrorResponse(code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to edit cluster")
    return response.to_http_response()


@cluster_router.post(
    "/update-node-status",
    responses={
        status.HTTP_200_OK: {
            "model": WorkflowMetadataResponse,
            "description": "Node status updated successfully",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Internal server error",
        },
    },
    status_code=status.HTTP_200_OK,
    description="Update the status of a node",
    tags=["Clusters"],
)
async def update_node_status(
    cluster_id: Annotated[UUID, Body(embed=True, description="The ID of the cluster to update")],
):
    """Update the status of a node."""
    try:
        response = await ClusterOpsService.trigger_update_node_status_workflow(cluster_id)
    except Exception as e:
        return ErrorResponse(message=str(e), param={"cluster_id": str(cluster_id)})
    return response.to_http_response()


@cluster_router.post(
    "/delete",
    responses={
        status.HTTP_200_OK: {
            "model": WorkflowMetadataResponse,
            "description": "Delete cluster workflow initiated",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Internal server error",
        },
    },
    status_code=status.HTTP_200_OK,
    description="Delete a cluster from the system",
    tags=["Clusters"],
)
async def delete_cluster(
    cluster_delete_request: ClusterDeleteRequest,
    session: Session = Depends(get_session),  # noqa: B008
):
    """Delete a cluster from the system.

    Args:
        cluster_delete_request (ClusterDeleteRequest): The request object contains metadata for the cluster.

    Returns:
        WorkflowMetadataResponse: A response object containing the workflow id, steps.
        ErrorResponse: A response object containing the error message.
    """
    try:
        response = await ClusterService(session).delete_cluster(cluster_delete_request)
    except Exception as e:
        logger.error(e)
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        if isinstance(e, HTTPException):
            status_code = e.status_code
            logger.info(f"HTTPException Status Code : {status_code}")
        response = ErrorResponse(
            message=str(e),
            param={"cluster_id": str(cluster_delete_request.cluster_id)},
            code=status_code,
        )
    return response.to_http_response()


@cluster_router.post(
    "/cancel/{workflow_id}",
    responses={
        status.HTTP_200_OK: {
            "model": SuccessResponse,
            "description": "Cluster registration cancelled successfully",
        },
    },
    status_code=status.HTTP_200_OK,
    description="Cancel a cluster registration",
    tags=["Clusters"],
)
def cancel_cluster(
    workflow_id: UUID,
    session: Session = Depends(get_session),  # noqa: B008
    background_tasks: BackgroundTasks = BackgroundTasks(),  # noqa: B008
):
    """Cancel a cluster."""
    try:
        response = ClusterService(session).cancel_cluster_registration(workflow_id, background_tasks)
    except Exception as e:
        response = ErrorResponse(message=str(e))
    return response.to_http_response()


# Get Cluster Events Count By Node With Cluster ID
@cluster_router.get(
    "/{cluster_id}/events-count-by-node",
    responses={
        status.HTTP_200_OK: {
            "model": NodeEventsCountSuccessResponse,
            "description": "Cluster events count by node",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Internal server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Bad request",
        },
    },
    status_code=status.HTTP_200_OK,
    description="Get cluster events count by node",
    tags=["Clusters"],
)
async def get_cluster_events_count_by_node(
    cluster_id: UUID,
    session: Session = Depends(get_session),  # noqa: B008
):
    """Get cluster events count by node.

    Args:
        cluster_id: The ID of the cluster to get events count by node.

    Returns:
        SuccessResponse: A response object containing the events count by node.
        ErrorResponse: A response object containing the error message.
    """
    try:
        response = await ClusterService(session).get_cluster_events_count_by_node(cluster_id)
    except Exception as e:
        response = ErrorResponse(message=str(e))
    return response.to_http_response()


# Get Node Wise Events with Cluster ID  pagination and total event count for the cluster.
@cluster_router.get(
    "/{cluster_id}/node-wise-events/{node_hostname}",
    responses={
        status.HTTP_200_OK: {
            "model": NodeEventsResponse,
            "description": "Node wise events with pagination and total event count for the cluster",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Internal server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Bad request",
        },
    },
    status_code=status.HTTP_200_OK,
    description="Get node-wise events with pagination and total event count for the cluster.",
    tags=["Clusters"],
)
async def get_node_wise_events(
    cluster_id: UUID,
    node_hostname: str,
    session: Session = Depends(get_session),  # noqa: B008
):
    """Get node-wise events with pagination and total event count for the cluster."""
    try:
        response = await ClusterService(session).get_node_wise_events(cluster_id, node_hostname)
    except Exception as e:
        logger.error(e)
        response = ErrorResponse(message=str(e))
    return response.to_http_response()


@cluster_router.get(
    "/{cluster_id}/nodes",
    responses={
        status.HTTP_200_OK: {
            "model": SuccessResponse,
            "description": "Cluster events count by node",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Internal server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Bad request",
        },
    },
    status_code=status.HTTP_200_OK,
    description="Get cluster nodes",
    tags=["Clusters"],
)
async def get_cluster_nodes(
    cluster_id: UUID,
    session: Session = Depends(get_session),  # noqa: B008
):
    """Get cluster nodes.

    Args:
        cluster_id: The ID of the cluster to get nodes.

    Returns:
        SuccessResponse: A response object containing list of nodes.
        ErrorResponse: A response object containing the error message.
    """
    try:
        response = await ClusterService(session).get_cluster_nodes(cluster_id)
    except Exception as e:
        response = ErrorResponse(message=str(e))
    return response.to_http_response()


@cluster_router.get(
    "/{cluster_id}/get-config",
    responses={
        status.HTTP_200_OK: {
            "model": SuccessResponse,
            "description": "Get cluster config",
        },
    },
    status_code=status.HTTP_200_OK,
    description="Get cluster config",
    tags=["Clusters"],
)
async def get_cluster_config(
    cluster_id: UUID,
    session: Session = Depends(get_session),  # noqa: B008
):
    """Get cluster config."""
    try:
        response = await ClusterService(session).get_cluster_config(cluster_id)
    except Exception as e:
        response = ErrorResponse(message=str(e))
    return response.to_http_response()
