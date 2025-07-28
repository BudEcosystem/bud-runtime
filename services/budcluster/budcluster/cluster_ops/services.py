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


"""Implements core services and business logic that power the microservices, including key functionality and integrations."""

import asyncio
import json
from typing import Any, Dict, List, Union
from uuid import UUID

from budmicroframe.commons.constants import WorkflowStatus
from budmicroframe.commons.logging import get_logger
from budmicroframe.commons.schemas import ErrorResponse, SuccessResponse, WorkflowMetadataResponse
from budmicroframe.shared.dapr_service import DaprService, DaprServiceCrypto
from budmicroframe.shared.dapr_workflow import DaprWorkflow

# from ..commons.database import SessionLocal
from budmicroframe.shared.psql_service import DBSession
from fastapi import BackgroundTasks, HTTPException, status

from ..commons.base_crud import SessionMixin
from ..commons.config import app_settings
from ..commons.constants import ClusterPlatformEnum, ClusterStatusEnum
from ..commons.utils import (
    get_workflow_data_from_statestore,
    save_workflow_status_in_statestore,
)
from . import (
    delete_cluster,
    determine_cluster_platform,
    get_node_info,
    get_node_wise_events,
    get_node_wise_events_count,
    initial_setup,
    verify_cluster_connection,
)
from .crud import ClusterDataManager, ClusterNodeInfoDataManager
from .models import Cluster as ClusterModel
from .models import ClusterNodeInfo as ClusterNodeInfoModel
from .models import ClusterNodeInfoCRUD
from .schemas import (
    ClusterCreate,
    ClusterCreateRequest,
    ClusterDeleteRequest,
    ClusterNodeInfo,
    ClusterNodeInfoResponse,
    ClusterStatusUpdate,
    ConfigureCluster,
    FetchClusterInfo,
    NodeEventsCountSuccessResponse,
    NodeEventsResponse,
    VerifyClusterConnection,
)


logger = get_logger(__name__)


class ClusterOpsService:
    @classmethod
    async def determine_cluster_platform(cls, config_dict: Dict[str, Any], task_id: str, workflow_id: str):
        """Determine the cluster platform."""
        logger.info(f"Determining cluster platform for workflow_id: {workflow_id} and task_id: {task_id}")
        return await determine_cluster_platform(config_dict)

    @classmethod
    async def verify_cluster_connection(
        cls, verify_cluster_connection_request: VerifyClusterConnection, task_id: str, workflow_id: str
    ):
        """Verify cluster connection."""
        logger.info(f"Verifying cluster connection for workflow_id: {workflow_id} and task_id: {task_id}")
        cluster_config = verify_cluster_connection_request.config_dict
        platform = verify_cluster_connection_request.platform
        return await verify_cluster_connection(cluster_config, platform)

    @classmethod
    async def configure_cluster(cls, configure_cluster_request: ConfigureCluster, task_id: str, workflow_id: str):
        """Configure cluster."""
        logger.info(f"Configuring cluster for workflow_id: {workflow_id} and task_id: {task_id}")
        platform = configure_cluster_request.platform
        hostname = configure_cluster_request.hostname
        enable_master_node = configure_cluster_request.enable_master_node
        ingress_url = configure_cluster_request.ingress_url
        server_url = configure_cluster_request.server_url
        # Encrypt configuration
        with DaprServiceCrypto() as dapr_service:
            configuration_encrypted = dapr_service.encrypt_data(json.dumps(configure_cluster_request.config_dict))
            logger.info("Encrypted cluster configuration file")

        # Create cluster
        cluster_data = ClusterCreate(
            platform=platform,
            configuration=configuration_encrypted,
            host=hostname,
            status=ClusterStatusEnum.NOT_AVAILABLE,
            enable_master_node=enable_master_node,
            ingress_url=ingress_url,
            server_url=server_url,
        )
        cluster_model = ClusterModel(**cluster_data.model_dump())
        with DBSession() as session:
            db_cluster = await ClusterDataManager(session).create_cluster(cluster_model)
            cluster_id = db_cluster.id
        # Pass The Cluster ID to the next step
        status = await initial_setup(configure_cluster_request.config_dict, cluster_id, platform)
        with DBSession() as session:
            if status != "successful":
                await ClusterDataManager(session).delete_cluster(cluster_id)
                cluster_id = None
            else:
                db_cluster = await ClusterDataManager(session).retrieve_cluster_by_fields({"id": cluster_id})
                await ClusterDataManager(session).update_cluster_by_fields(
                    db_cluster, {"status": ClusterStatusEnum.AVAILABLE}
                )
        return status, cluster_id

    @classmethod
    async def fetch_cluster_info(cls, fetch_cluster_info_request: FetchClusterInfo, task_id: str, workflow_id: str):
        """Fetch cluster info."""
        logger.info(f"Fetching cluster info for workflow_id: {workflow_id} and task_id: {task_id}")
        try:
            cluster_name = fetch_cluster_info_request.name
            # cluster_config = fetch_cluster_info_request.config_dict
            platform = fetch_cluster_info_request.platform
            # hostname = fetch_cluster_info_request.hostname
            # enable_master_node = fetch_cluster_info_request.enable_master_node
            # ingress_url = fetch_cluster_info_request.ingress_url
            # server_url = fetch_cluster_info_request.server_url
            cluster_id = fetch_cluster_info_request.cluster_id

            node_info = await get_node_info(fetch_cluster_info_request.config_dict, platform)
            logger.info(f"Node info: {node_info}")

            cluster_status = any(node["node_status"] for node in node_info)

            with DBSession() as session:
                db_cluster = await ClusterDataManager(session).retrieve_cluster_by_fields({"id": cluster_id})
                await ClusterDataManager(session).update_cluster_by_fields(
                    db_cluster,
                    {"status": ClusterStatusEnum.AVAILABLE if cluster_status else ClusterStatusEnum.NOT_AVAILABLE},
                )

            node_objects = []
            for node in node_info:
                devices = json.loads(node.get("devices", "[]"))
                hardware_info = devices[0]["device_info"] if len(devices) > 0 else {}
                device_type = devices[0]["type"] if len(devices) > 0 else "cpu"
                node_objects.append(
                    ClusterNodeInfo(
                        cluster_id=cluster_id,
                        name=node["node_name"],
                        type=device_type,
                        hardware_info=devices,
                        status=node["node_status"],
                        status_sync_at=node["timestamp"],
                        threads_per_core=hardware_info.get("threads_per_core", 0),
                        core_count=hardware_info.get("num_physical_cores", 0),
                    )
                )

            # add node info to db
            with DBSession() as session:
                db_nodes = await ClusterNodeInfoDataManager(session).create_cluster_node_info(node_objects)
            logger.info("Added node info to db")
            nodes = await cls.transform_db_nodes(db_nodes)
            logger.info("Transformed db nodes")
            result = {
                "id": str(cluster_id),
                "name": cluster_name,
                "nodes": nodes,
            }

            logger.info("Fetched cluster info result inside services")
            return json.dumps(result)
        except Exception as e:
            import traceback

            logger.error(
                f"Error fetching cluster info for workflow_id: {workflow_id} and task_id: {task_id}, error: {e}\n"
                f"Stacktrace:\n{traceback.format_exc()}"
            )
            raise e

    @classmethod
    async def delete_cluster(cls, delete_cluster_request: ClusterDeleteRequest, task_id: str, workflow_id: str):
        """Delete cluster resources."""
        logger.info(f"Deleting cluster resources for workflow_id: {workflow_id} and task_id: {task_id}")
        cluster_config = delete_cluster_request.cluster_config
        platform = delete_cluster_request.platform
        return await delete_cluster(cluster_config, platform)

    @classmethod
    async def transform_db_nodes(cls, db_nodes: List[ClusterNodeInfoModel]):
        """Transform db nodes to response."""
        result = []
        for node in db_nodes:
            hardware_info = node.hardware_info
            devices = []
            for each_info in hardware_info:
                device_config = each_info.get("device_config", {})
                devices.append(
                    {
                        **device_config,
                        "available_count": each_info.get("available_count", 0),
                    }
                )
            result.append(
                {
                    "name": node.name,
                    "id": str(node.id),
                    "status": node.status,
                    "devices": devices,
                }
            )
        return result

    @classmethod
    async def update_node_status(cls, cluster_id: UUID) -> ClusterStatusEnum:
        """Update node status."""
        logger.info(f"Updating node status for cluster_id: {cluster_id}")
        with DBSession() as session:
            # Get cluster info
            db_cluster = await ClusterDataManager(session).retrieve_cluster_by_fields(
                {"id": cluster_id}, missing_ok=True
            )

            if not db_cluster:
                logger.debug(f"Cluster not found: {cluster_id}")
                return

            node_status_change = False
            prev_node_status_map = {each.name: each.status for each in db_cluster.nodes}

            # Get node info
            node_info = await get_node_info(db_cluster.config_file_dict, db_cluster.platform)

            # Create node objects
            node_objects = []
            for node in node_info:
                devices = json.loads(node.get("devices", "[]"))
                hardware_info = devices[0]["device_info"] if len(devices) > 0 else {}
                device_type = devices[0]["type"] if len(devices) > 0 else "cpu"
                if (
                    node["node_name"] in prev_node_status_map
                    and prev_node_status_map[node["node_name"]] != node["node_status"]
                ):
                    node_status_change = True
                node_objects.append(
                    ClusterNodeInfo(
                        cluster_id=cluster_id,
                        name=node["node_name"],
                        type=device_type,
                        hardware_info=devices,
                        status=node["node_status"],
                        status_sync_at=node["timestamp"],
                        threads_per_core=hardware_info.get("threads_per_core", 0),
                        core_count=hardware_info.get("num_physical_cores", 0),
                    )
                )

            nodes_info_present = len(node_objects) > 0 and len(db_cluster.nodes) == len(node_objects)

            node_map = {node.name: node for node in node_objects}
            db_node_map = {node.name: node for node in db_cluster.nodes}

            # Identify nodes to update, add, or delete
            update_nodes = []
            add_nodes = []
            delete_nodes = []
            for node in node_map:
                if node in db_node_map:
                    for field, value in node_map[node].model_dump(mode="json").items():
                        setattr(db_node_map[node], field, value)
                    update_nodes.append(db_node_map[node])
                else:
                    add_nodes.append(node_map[node])

            delete_nodes = [db_node_map[name] for name in db_node_map if name not in node_map]

            if add_nodes or delete_nodes:
                node_status_change = True

            if update_nodes:
                await ClusterNodeInfoDataManager(session).update_cluster_node_info(update_nodes)

            if add_nodes:
                await ClusterNodeInfoDataManager(session).create_cluster_node_info(add_nodes)

            if delete_nodes:
                await ClusterNodeInfoDataManager(session).delete_cluster_node_info(delete_nodes)

            db_nodes = await ClusterNodeInfoDataManager(session).get_cluster_node_info_by_cluster_id(cluster_id)

            cluster_status = (
                ClusterStatusEnum.AVAILABLE
                if any(node.status for node in node_objects)
                else ClusterStatusEnum.NOT_AVAILABLE
            )

            # Prepare and store results in statestore
            nodes = await cls.transform_db_nodes(db_nodes)
            result = {
                "id": str(cluster_id),
                "nodes": nodes,
            }

            logger.info(f"Cluster status: {cluster_status} Nodes info present: {nodes_info_present}")
            if cluster_status != db_cluster.status:
                await ClusterDataManager(session).update_cluster_by_fields(db_cluster, {"status": cluster_status})

            await cls.update_node_info_in_statestore(json.dumps(result))
            return cluster_status, nodes_info_present, result, node_status_change

    @classmethod
    async def update_node_info_in_statestore(cls, input_data: str):
        """Update node info in state store."""
        data = json.loads(input_data)
        cluster_id = data["id"]

        with DaprService() as dapr_service:
            key = "cluster_info"
            response = dapr_service.get_state(store_name=app_settings.statestore_name, key=key)
            all_cluster_info = json.loads(response.data) if response.data else []
            filtered_cluster_info = [info for info in all_cluster_info if info["id"] != cluster_id]
            filtered_cluster_info.append(data)
            dapr_service.save_to_statestore(key=key, value=json.dumps(filtered_cluster_info))

    @classmethod
    async def delete_node_info_from_statestore(cls, cluster_id: str):
        """Delete node info from state store."""
        with DaprService() as dapr_service:
            key = "cluster_info"
            response = dapr_service.get_state(store_name=app_settings.statestore_name, key=key)
            all_cluster_info = json.loads(response.data) if response.data else []
            filtered_cluster_info = [info for info in all_cluster_info if info["id"] != cluster_id]
            dapr_service.save_to_statestore(key=key, value=json.dumps(filtered_cluster_info))

    @classmethod
    def cancel_cluster_registration(cls, workflow_id: UUID) -> Union[SuccessResponse, ErrorResponse]:
        """Cancel a cluster registration."""
        workflow_status_dict = get_workflow_data_from_statestore(str(workflow_id))
        if not workflow_status_dict:
            return ErrorResponse(message="Workflow not found")
        if "cluster_id" in workflow_status_dict:
            cluster_id = workflow_status_dict["cluster_id"]
            with DBSession() as session:
                db_cluster = asyncio.run(ClusterService(session)._get_cluster(cluster_id, missing_ok=True))

                if db_cluster is None:
                    return ErrorResponse(message="Cluster not found")

                asyncio.run(ClusterDataManager(session).delete_cluster(db_cluster=db_cluster))

            asyncio.run(ClusterOpsService.delete_node_info_from_statestore(str(cluster_id)))
        # cleanup resources create deployment workflow
        if "namespace" in workflow_status_dict:
            from ..deployment.handler import DeploymentHandler

            platform = workflow_status_dict.get("platform")
            deployment_handler = DeploymentHandler(config=workflow_status_dict["cluster_config_dict"])
            deployment_handler.delete(workflow_status_dict["namespace"], platform)
        return SuccessResponse(message="Create deployment resources cleaned up")

    @classmethod
    async def trigger_update_node_status_workflow(cls, cluster_id: UUID):
        """Trigger update node status workflow."""
        from .workflows import UpdateClusterStatusWorkflow

        response = await UpdateClusterStatusWorkflow().__call__(str(cluster_id))
        return response

    @classmethod
    async def trigger_periodic_node_status_update(cls) -> Union[SuccessResponse, ErrorResponse]:
        """Trigger node status update for all active clusters.

        This method is called by a periodic job to keep cluster node information
        up-to-date in the state store.

        Returns:
            SuccessResponse: If updates were triggered successfully
            ErrorResponse: If there was an error triggering updates
        """
        from .workflows import UpdateClusterStatusWorkflow

        try:
            # Get all active clusters from database
            with DBSession() as session:
                active_clusters = await ClusterDataManager(session).get_all_clusters_by_status(
                    [ClusterStatusEnum.AVAILABLE, ClusterStatusEnum.NOT_AVAILABLE]
                )

            logger.info(f"Found {len(active_clusters)} active clusters for node status update")

            # Trigger update workflow for each cluster
            update_count = 0
            failed_count = 0

            for cluster in active_clusters:
                try:
                    logger.debug(f"Triggering node status update for cluster {cluster.id}")
                    await UpdateClusterStatusWorkflow().__call__(str(cluster.id))
                    update_count += 1
                except Exception as e:
                    logger.error(f"Failed to trigger update for cluster {cluster.id}: {e}")
                    failed_count += 1

            message = f"Triggered node status update for {update_count} clusters"
            if failed_count > 0:
                message += f" ({failed_count} failed)"

            logger.info(message)
            return SuccessResponse(
                message=message, param={"total": len(active_clusters), "updated": update_count, "failed": failed_count}
            )

        except Exception as e:
            logger.exception("Failed to trigger periodic node status update")
            return ErrorResponse(message=f"Failed to trigger periodic node status update: {str(e)}")


class ClusterService(SessionMixin):
    async def _get_cluster(self, cluster_id: UUID, missing_ok: bool = False) -> ClusterModel:
        """Get cluster details from db."""
        return await ClusterDataManager(self.session).retrieve_cluster_by_fields(
            {"id": cluster_id}, missing_ok=missing_ok
        )

    async def _check_duplicate_config(
        self, server_url: str, platform: ClusterPlatformEnum
    ) -> Union[SuccessResponse, ErrorResponse]:
        """Check duplicate config.

        1. check if cluster is registering, give notification try again later.
        2. check if cluster is not_available, give notification delete and try again later.

        Args:
            server_url (str): The server URL of the cluster.
            platform (ClusterPlatformEnum): The platform of the cluster.

        Returns:
            Union[SuccessResponse, ErrorResponse]: A response object containing the success or error message.
        """
        db_cluster = await ClusterDataManager(self.session).retrieve_cluster_by_fields(
            {"server_url": server_url, "platform": platform, "status": ClusterStatusEnum.AVAILABLE}, missing_ok=True
        )
        if db_cluster and db_cluster.status == ClusterStatusEnum.REGISTERING:
            # send notification to budapp
            return ErrorResponse(
                message="This cluster is already registering. Please try again later.",
                code=status.HTTP_400_BAD_REQUEST,
                param={"cluster_id": str(db_cluster.id)},
            )
        if db_cluster and db_cluster.status == ClusterStatusEnum.NOT_AVAILABLE:
            # send notification to budapp
            return ErrorResponse(
                message="This cluster is temporarily not available, please wait for sometime or delete it and try again.",
                code=status.HTTP_400_BAD_REQUEST,
                param={"cluster_id": str(db_cluster.id)},
            )
        if db_cluster and db_cluster.status == ClusterStatusEnum.AVAILABLE:
            return ErrorResponse(
                message="This cluster is already registered. Please delete it and try again.",
                code=status.HTTP_400_BAD_REQUEST,
                param={"cluster_id": str(db_cluster.id)},
            )
        return SuccessResponse(message="No duplicate cluster found")

    async def register_cluster(self, cluster: ClusterCreateRequest) -> Union[WorkflowMetadataResponse, ErrorResponse]:
        """Register cluster.

        This function triggers the process of registering a new cluster.

        Args:
            cluster (ClusterCreateRequest): The request object contains metadata for the cluster.

        Returns:
            Union[WorkflowMetadataResponse, ErrorResponse]: A response object containing the workflow id and steps.
        """
        logger.info(f"Registering cluster: {cluster.name}")

        response: Union[WorkflowMetadataResponse, ErrorResponse]

        from .workflows import RegisterClusterWorkflow

        try:
            if cluster.cluster_type == "ON_PERM":
                cluster.ingress_url = str(cluster.ingress_url)
            response = await RegisterClusterWorkflow().__call__(cluster)
        except Exception as e:
            logger.error(f"Error registering cluster: {e}")
            raise ErrorResponse(message=f"Error registering cluster: {e}") from e
        return response

    async def update_cluster_registration_status(self, cluster_id: UUID, data: ClusterStatusUpdate) -> None:
        """Update cluster registration status."""
        logger.info(f"Updating cluster registration status for cluster_id: {cluster_id}, data: {data}")
        db_cluster = await ClusterDataManager(self.session).retrieve_cluster_by_fields(
            {"id": cluster_id}, missing_ok=False
        )
        await ClusterDataManager(self.session).update_cluster_by_fields(db_cluster, data.model_dump(exclude_none=True))
        logger.info(f"Cluster: {db_cluster.id} updated in database")

    async def delete_cluster(
        self, cluster_delete_request: ClusterDeleteRequest
    ) -> Union[WorkflowMetadataResponse, ErrorResponse]:
        """Delete a cluster from the system."""
        logger.info(f"Deleting cluster with id: {cluster_delete_request.cluster_id}")

        from .workflows import DeleteClusterWorkflow

        try:
            db_cluster = await self._get_cluster(cluster_delete_request.cluster_id, missing_ok=True)
            cluster_delete_request.cluster_config = db_cluster.config_file_dict if db_cluster else None
            cluster_delete_request.platform = db_cluster.platform if db_cluster else None
            response = await DeleteClusterWorkflow().__call__(cluster_delete_request)
        except Exception as e:
            logger.error(f"Error deleting cluster: {e}")
            if isinstance(e, HTTPException):
                raise e
            raise ErrorResponse(message=f"Error deleting cluster: {e}") from None
        return response

    def cancel_cluster_registration(
        self, workflow_id: UUID, background_tasks: BackgroundTasks
    ) -> Union[SuccessResponse, ErrorResponse]:
        """Cancel a cluster registration."""
        stop_workflow_response = asyncio.run(DaprWorkflow().stop_workflow(str(workflow_id)))
        if stop_workflow_response.code == 200:
            save_workflow_status_in_statestore(str(workflow_id), WorkflowStatus.TERMINATED.value)
            background_tasks.add_task(ClusterOpsService.cancel_cluster_registration, workflow_id)
        return stop_workflow_response

    # Get Cluster Events Count By Node With Cluster ID
    async def get_cluster_events_count_by_node(
        self, cluster_id: UUID
    ) -> Union[NodeEventsCountSuccessResponse, ErrorResponse]:
        """Get cluster events count by node."""
        logger.info(f"Collecting Node Events Count for Cluster: {cluster_id}")

        with DBSession() as session:
            # Get Cluster Info
            db_cluster = await ClusterDataManager(session).retrieve_cluster_by_fields(
                {"id": cluster_id}, missing_ok=False
            )
            if db_cluster is None:
                return ErrorResponse(message="Cluster not found")

            node_metrics = await get_node_wise_events_count(db_cluster.config_file_dict, db_cluster.platform)
            logger.info(f"Node metrics: {node_metrics}")

            # node_info = await get_node_info(db_cluster.config_file_dict, db_cluster.platform)
            # logger.info(f"Node info: {node_info}")

            return NodeEventsCountSuccessResponse(message="Node events count collected", data=node_metrics)

    # Get Node Wise Events with Cluster ID
    async def get_node_wise_events(
        self, cluster_id: UUID, node_hostname: str
    ) -> Union[NodeEventsResponse, ErrorResponse]:
        """Get node-wise events with pagination and total event count for the cluster."""
        logger.info(f"Collecting Node Events for Cluster: {cluster_id} and Node: {node_hostname}")

        with DBSession() as session:
            # Get Cluster Info
            db_cluster = await ClusterDataManager(session).retrieve_cluster_by_fields(
                {"id": cluster_id}, missing_ok=False
            )

            logger.info(f"DB Cluster: {db_cluster.platform}")

            if db_cluster is None:
                return ErrorResponse(message="Cluster not found")

            node_events = await get_node_wise_events(
                config=db_cluster.config_file_dict, node_hostname=node_hostname, platform=db_cluster.platform
            )
            logger.info(f"Node events: {node_events}")

            return NodeEventsResponse(message="Node events collected", data=node_events)

    async def edit_cluster(self, cluster_id: UUID, data: Dict[str, Any]) -> ClusterModel:
        """Edit cloud model by validating and updating specific fields, and saving an uploaded file if provided."""
        # Retrieve existing model
        db_cluster = await self._get_cluster(cluster_id, missing_ok=False)
        db_cluster = await ClusterDataManager(self.session).update_cluster_by_fields(db_cluster, data)
        return db_cluster

    async def get_cluster_nodes(self, cluster_id: UUID) -> Union[SuccessResponse, ErrorResponse]:
        """Get cluster nodes."""
        with ClusterNodeInfoCRUD() as crud:
            nodes, _ = crud.fetch_many(conditions={"cluster_id": cluster_id})
            nodes_list = [ClusterNodeInfoResponse.model_validate(node) for node in nodes]
        return SuccessResponse(param={"nodes": nodes_list}, message="Cluster nodes fetched successfully")

    async def get_cluster_config(self, cluster_id: UUID) -> Union[SuccessResponse, ErrorResponse]:
        """Get all clusters."""
        db_cluster = await ClusterDataManager(self.session).retrieve_cluster_by_fields(
            {"id": cluster_id, "status": ClusterStatusEnum.AVAILABLE}
        )

        logger.info(f"DB Clusters: {db_cluster}")
        cluster_details = {
            "platform": db_cluster.platform,
            "status": db_cluster.status,
            "configuration": db_cluster.configuration,
            "ingress_url": db_cluster.ingress_url,
        }
        return SuccessResponse(
            param={"cluster_details": cluster_details}, message="Cluster details fetched successfully"
        )
