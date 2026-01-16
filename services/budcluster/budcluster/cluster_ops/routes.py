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
from typing import Annotated, Optional, Union
from uuid import UUID

import yaml
from budmicroframe.commons.logging import get_logger
from budmicroframe.commons.schemas import ErrorResponse, SuccessResponse, WorkflowMetadataResponse
from fastapi import APIRouter, BackgroundTasks, Body, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from ..commons.dependencies import get_session
from .schemas import (
    ClusterCreateRequest,
    ClusterDeleteRequest,
    ClusterHealthResponse,
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
    "/{cluster_id}/device-info",
    responses={
        status.HTTP_200_OK: {
            "model": SuccessResponse,
            "description": "Structured device information for llm-memory-calculator",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Internal server error",
        },
    },
    status_code=status.HTTP_200_OK,
    description="Get structured device information for llm-memory-calculator",
    tags=["Clusters"],
)
async def get_cluster_device_info(
    cluster_id: UUID,
) -> Union[SuccessResponse, ErrorResponse]:
    """Get structured device information for llm-memory-calculator.

    Returns device information in a format that can be used by llm-memory-calculator
    for matching against its configuration database. Includes:
    - Raw device names
    - PCI vendor/device IDs
    - Memory sizes
    - Vendor, model, and variant information
    """
    try:
        device_info = ClusterOpsService.get_device_info_for_llm_calculator(cluster_id)
        return SuccessResponse(message="Device information retrieved successfully", data=device_info)
    except Exception as e:
        logger.error(f"Error getting device info for cluster {cluster_id}: {e}")
        return ErrorResponse(error="Failed to get device information", message=str(e))


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


@cluster_router.get(
    "/{cluster_id}/storage-classes",
    responses={
        status.HTTP_200_OK: {
            "model": SuccessResponse,
            "description": "Get cluster storage classes",
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
    description="Get all storage classes available in the cluster",
    tags=["Clusters"],
)
async def get_cluster_storage_classes(
    cluster_id: UUID,
    session: Session = Depends(get_session),  # noqa: B008
):
    """Get all storage classes available in the cluster.

    Args:
        cluster_id: The ID of the cluster to get storage classes from.

    Returns:
        SuccessResponse: A response object containing the list of storage classes.
        ErrorResponse: A response object containing the error message.
    """
    try:
        response = await ClusterService(session).get_cluster_storage_classes(cluster_id)
    except Exception as e:
        logger.error(f"Error getting storage classes for cluster {cluster_id}: {e}")
        response = ErrorResponse(message=str(e))
    return response.to_http_response()


@cluster_router.get(
    "/{cluster_id}/health",
    responses={
        status.HTTP_200_OK: {
            "model": ClusterHealthResponse,
            "description": "Cluster health check results",
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
    description="Get cluster health status for specified checks",
    tags=["Clusters"],
)
async def get_cluster_health(
    cluster_id: UUID,
    checks: Optional[str] = Query(
        default=None,
        description="Comma-separated list of health checks to perform. "
        "Valid values: nodes, api, storage, network, gpu. "
        "If not specified, all checks are performed.",
    ),
    session: Session = Depends(get_session),  # noqa: B008
) -> Union[ClusterHealthResponse, ErrorResponse]:
    """Get cluster health status for specified checks.

    This endpoint performs health checks on the cluster and returns the status
    of each requested check. Available checks include:
    - nodes: Check if all cluster nodes are ready
    - api: Check if the Kubernetes API server is responding
    - storage: Check if PVCs are bound
    - network: Check if network policies are active and DNS is healthy
    - gpu: Check if GPU drivers are detected and GPUs are allocatable

    Args:
        cluster_id: The ID of the cluster to check health for.
        checks: Comma-separated list of checks to perform (e.g., "nodes,api,gpu").

    Returns:
        ClusterHealthResponse: Health status for each requested check.
        ErrorResponse: Error message if the check fails.
    """
    try:
        # Parse checks parameter
        checks_list = None
        if checks:
            checks_list = [c.strip().lower() for c in checks.split(",") if c.strip()]

        response = await ClusterService(session).get_cluster_health(cluster_id, checks_list)
    except Exception as e:
        logger.error(f"Error checking cluster health for {cluster_id}: {e}")
        response = ErrorResponse(message=str(e))
    return response.to_http_response()


@cluster_router.get("/periodic-node-status-update/health")
async def periodic_node_status_health():
    """Health check endpoint to verify periodic node status sync is configured.

    Returns:
        dict: Status of the periodic sync configuration.
    """
    import os
    from datetime import datetime, timedelta

    # Check if Dapr binding file exists
    binding_file = "/datadisk/ditto/bud-stack/services/budcluster/.dapr/components/binding.yaml"
    binding_exists = os.path.exists(binding_file)

    # Store last sync time in a class variable (simple in-memory tracking)
    if not hasattr(periodic_node_status_health, "last_sync_time"):
        periodic_node_status_health.last_sync_time = None
        periodic_node_status_health.last_sync_source = None
        periodic_node_status_health.sync_history = []

    # Check if sync is stale (hasn't run in > 5 minutes)
    is_stale = False
    if periodic_node_status_health.last_sync_time:
        last_sync = datetime.fromisoformat(periodic_node_status_health.last_sync_time)
        if datetime.utcnow() - last_sync > timedelta(minutes=5):
            is_stale = True

    # Determine health status
    if not binding_exists:
        health_status = "unhealthy"
    elif periodic_node_status_health.last_sync_time is None:
        health_status = "initializing"
    elif is_stale:
        health_status = "stale"
    else:
        health_status = "healthy"

    status = {
        "binding_configured": binding_exists,
        "schedule": "@every 3m",
        "last_sync_time": periodic_node_status_health.last_sync_time,
        "last_sync_source": getattr(periodic_node_status_health, "last_sync_source", None),
        "is_stale": is_stale,
        "status": health_status,
        "sync_history": getattr(periodic_node_status_health, "sync_history", []),
    }

    return status


@cluster_router.get("/periodic-node-status-update/state")
async def get_sync_state():
    """Get the current sync state from the state store.

    Returns:
        dict: Current sync state including active syncs, last sync times, and failed clusters.
    """
    from budmicroframe.shared.dapr_service import DaprService

    from ..commons.config import app_settings

    STATE_STORE_KEY = "cluster_node_sync_state"

    try:
        # Check if state store is configured
        if not hasattr(app_settings, "statestore_name") or not app_settings.statestore_name:
            return {
                "status": "info",
                "message": "State store not configured - using in-memory state only",
                "note": "State is not persisted across restarts",
            }

        dapr_service = DaprService()
        sync_state = dapr_service.get_state(store_name=app_settings.statestore_name, key=STATE_STORE_KEY).json()

        # Add summary statistics
        summary = {
            "active_syncs_count": len(sync_state.get("active_syncs", {})),
            "clusters_synced": len(sync_state.get("last_sync_times", {})),
            "failed_clusters_count": len(sync_state.get("failed_clusters", {})),
        }

        return {"status": "success", "summary": summary, "state": sync_state}
    except Exception as e:
        logger.debug(f"Could not retrieve sync state from state store: {e}")
        return {
            "status": "info",
            "message": "State store not available - using in-memory state only",
            "note": "This is normal in Kubernetes mode without configured state store components",
        }


@cluster_router.post("/periodic-node-status-update/trigger")
async def trigger_manual_sync():
    """Manually trigger a node status sync for all clusters.

    This endpoint allows manual triggering of the sync process without waiting for the cron job.

    Returns:
        SuccessResponse or ErrorResponse
    """
    try:
        logger.info("Manual node status sync triggered via API")

        # Track this as a manual trigger
        from datetime import datetime

        periodic_node_status_health.last_sync_time = datetime.utcnow().isoformat()
        periodic_node_status_health.last_sync_source = "manual"

        response = await ClusterOpsService.trigger_periodic_node_status_update()
        return response.to_http_response()
    except Exception as e:
        logger.exception("Error in manual node status sync: %s", str(e))
        return ErrorResponse(message=f"Error in manual sync: {str(e)}", code=500).to_http_response()


@cluster_router.post("/periodic-node-status-update")
async def periodic_node_status_update():
    """Periodic job endpoint to update node status for all active clusters.

    This endpoint is triggered by a Dapr cron binding to keep the cluster
    node information in sync with the actual cluster state.

    Returns:
        SuccessResponse: A response object indicating success.
        ErrorResponse: A response object containing the error message.
    """
    response: Union[SuccessResponse, ErrorResponse]
    try:
        # Log that the periodic sync was triggered (helps with debugging)
        from datetime import datetime

        trigger_time = datetime.utcnow()
        logger.info(f"Periodic node status update triggered by Dapr cron binding at {trigger_time.isoformat()}")

        # Track last sync time for health check
        periodic_node_status_health.last_sync_time = trigger_time.isoformat()
        periodic_node_status_health.last_sync_source = "cron"

        response = await ClusterOpsService.trigger_periodic_node_status_update()

        # Track completion time
        completion_time = datetime.utcnow()
        duration = (completion_time - trigger_time).total_seconds()

        logger.info(
            f"Periodic node status update completed in {duration:.2f}s: {response.message if hasattr(response, 'message') else 'success'}"
        )

        # Store additional metrics
        if not hasattr(periodic_node_status_health, "sync_history"):
            periodic_node_status_health.sync_history = []

        periodic_node_status_health.sync_history.append(
            {
                "triggered_at": trigger_time.isoformat(),
                "completed_at": completion_time.isoformat(),
                "duration_seconds": duration,
                "result": response.param if hasattr(response, "param") else None,
            }
        )

        # Keep only last 10 sync records
        if len(periodic_node_status_health.sync_history) > 10:
            periodic_node_status_health.sync_history = periodic_node_status_health.sync_history[-10:]

    except Exception as e:
        logger.exception("Error in periodic node status update: %s", str(e))
        response = ErrorResponse(message="Error in periodic node status update", code=500)

    return response.to_http_response()
