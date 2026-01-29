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

"""The cluster ops services. Contains business logic for cluster ops."""

import json
import tempfile
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

import aiohttp
import yaml
from fastapi import UploadFile, status
from pydantic import ValidationError

from budapp.cluster_ops.utils import ClusterMetricsFetcher
from budapp.commons import logging
from budapp.commons.async_utils import check_file_extension, get_range_label
from budapp.commons.config import app_settings
from budapp.commons.db_utils import SessionMixin
from budapp.commons.exceptions import ClientException, DatabaseException
from budapp.core.schemas import NotificationPayload
from budapp.credential_ops.crud import CloudProviderCredentialDataManager
from budapp.credential_ops.models import CloudCredentials
from budapp.endpoint_ops.crud import EndpointDataManager
from budapp.endpoint_ops.models import Endpoint as EndpointModel
from budapp.shared.grafana import Grafana
from budapp.workflow_ops.crud import WorkflowDataManager, WorkflowStepDataManager
from budapp.workflow_ops.models import Workflow as WorkflowModel
from budapp.workflow_ops.models import WorkflowStep as WorkflowStepModel
from budapp.workflow_ops.services import WorkflowService, WorkflowStepService

from ..commons.constants import (
    APP_ICONS,
    BUD_INTERNAL_WORKFLOW,
    RECOMMENDED_CLUSTER_SCHEDULER_STATE_STORE_KEY,
    BudServeWorkflowStepEventName,
    ClusterStatusEnum,
    EndpointStatusEnum,
    ModelProviderTypeEnum,
    ModelStatusEnum,
    NotificationTypeEnum,
    WorkflowStatusEnum,
    WorkflowTypeEnum,
)
from ..commons.helpers import get_hardware_types
from ..core.schemas import NotificationResult
from ..model_ops.crud import ModelDataManager
from ..model_ops.models import Model
from ..model_ops.schemas import DeploymentTemplateCreate
from ..model_ops.schemas import Model as ModelSchema
from ..model_ops.services import ModelServiceUtil
from ..project_ops.schemas import Project as ProjectSchema
from ..shared.dapr_service import DaprService
from ..shared.notification_service import BudNotifyService, NotificationBuilder
from ..workflow_ops.schemas import WorkflowUtilCreate
from .crud import ClusterDataManager, ClusterSettingsDataManager, ModelClusterRecommendedDataManager
from .models import Cluster as ClusterModel
from .models import ModelClusterRecommended as ModelClusterRecommendedModel
from .schemas import (
    ClusterCreate,
    ClusterDetailResponse,
    ClusterEndpointResponse,
    ClusterPaginatedResponse,
    ClusterResourcesInfo,
    ClusterResponse,
    ClusterSettingsResponse,
    CreateClusterWorkflowRequest,
    CreateClusterWorkflowSteps,
    MetricTypeEnum,
    ModelClusterRecommendedCreate,
    ModelClusterRecommendedUpdate,
    RecommendedCluster,
    RecommendedClusterData,
)


logger = logging.get_logger(__name__)


class ClusterService(SessionMixin):
    """Cluster service."""

    async def get_all_active_clusters(
        self,
        offset: int = 0,
        limit: int = 10,
        filters: Dict = {},
        order_by: List = [],
        search: bool = False,
    ) -> Tuple[List[ClusterPaginatedResponse], int]:
        """Get all active clusters."""
        results, count = await ClusterDataManager(self.session).get_all_clusters(
            offset, limit, filters, order_by, search
        )
        updated_clusters = []
        for result in results:
            cluster, endpoints_count = result
            updated_cluster = ClusterPaginatedResponse(
                id=cluster.id,
                cluster_id=cluster.cluster_id,
                name=cluster.name,
                icon=cluster.icon,
                ingress_url=cluster.ingress_url,
                created_at=cluster.created_at,
                modified_at=cluster.modified_at,
                endpoint_count=endpoints_count,
                status=cluster.status,
                gpu_count=cluster.gpu_count,
                cpu_count=cluster.cpu_count,
                hpu_count=cluster.hpu_count,
                cpu_total_workers=cluster.cpu_total_workers,
                cpu_available_workers=cluster.cpu_available_workers,
                gpu_total_workers=cluster.gpu_total_workers,
                gpu_available_workers=cluster.gpu_available_workers,
                hpu_total_workers=cluster.hpu_total_workers,
                hpu_available_workers=cluster.hpu_available_workers,
                total_nodes=cluster.total_nodes,
                available_nodes=cluster.available_nodes,
            )
            updated_clusters.append(updated_cluster)

        return updated_clusters, count

    async def create_cluster_workflow(
        self,
        current_user_id: UUID,
        request: CreateClusterWorkflowRequest,
        configuration_file: UploadFile | None = None,
    ) -> None:
        """Create a cluster workflow.

        Args:
            current_user_id: The current user id.
            request: The request to create the cluster workflow with.
            configuration_file: The configuration file to create the cluster with.

        Raises:
            ClientException: If the cluster already exists.
        """
        # Get request data
        workflow_id = request.workflow_id
        workflow_total_steps = request.workflow_total_steps
        step_number = request.step_number
        cluster_name = request.name
        cluster_icon = request.icon
        ingress_url = request.ingress_url
        trigger_workflow = request.trigger_workflow

        # Cloud Specific
        cluster_type = request.cluster_type or "ON_PREM"
        credential_id = request.credential_id
        provider_id = request.provider_id
        region = request.region

        # Get Cluster Credential
        credentials = None
        cloud_credentials = None

        current_step_number = step_number

        # Retrieve or create workflow
        workflow_create = WorkflowUtilCreate(
            workflow_type=WorkflowTypeEnum.CLUSTER_ONBOARDING,
            title="Cluster Onboarding",
            total_steps=workflow_total_steps,
            icon=APP_ICONS["general"]["cluster_mono"],
            tag="Cluster Onboarding",
        )
        db_workflow = await WorkflowService(self.session).retrieve_or_create_workflow(
            workflow_id, workflow_create, current_user_id
        )
        configuration_yaml = None

        # Validate the configuration file
        if configuration_file:
            # Validate the configuration file for ON_PERM cluster

            if cluster_type == "ON_PREM" and configuration_file:
                if not await check_file_extension(configuration_file.filename, ["yaml", "yml"]):
                    logger.error("Invalid file extension for configuration file")
                    raise ClientException("Invalid file extension for configuration file")

            try:
                configuration_yaml = yaml.safe_load(configuration_file.file)
            except yaml.YAMLError as e:
                logger.exception(f"Invalid cluster configuration yaml file found: {e}")
                raise ClientException("Invalid cluster configuration yaml file found") from e

        # For CLOUD clusters, validate required cloud parameters
        if cluster_type == "CLOUD":
            if not credential_id:
                raise ClientException("Credential ID is required for cloud clusters")
            if not provider_id:
                raise ClientException("Provider ID is required for cloud clusters")
            if not region:
                raise ClientException("Region is required for cloud clusters")

        # Data Validation & Credential Fetching
        if cluster_type == "CLOUD":
            cloud_credentials = await CloudProviderCredentialDataManager(self.session).retrieve_by_fields(
                CloudCredentials,
                fields={"id": credential_id, "provider_id": provider_id},
                missing_ok=False,
            )
            if not cloud_credentials:
                raise ClientException("Cloud provider credential not found")

            credentials = cloud_credentials.credential  # type: ignore

            logger.debug(f"====== Unique ID {cloud_credentials.provider.unique_id}")  # type: ignore

        if cluster_name:
            # Check duplicate cluster name
            db_cluster = await ClusterDataManager(self.session).retrieve_by_fields(
                ClusterModel,
                fields={"name": cluster_name},
                exclude_fields={"status": ClusterStatusEnum.DELETED},
                missing_ok=True,
                case_sensitive=False,
            )
            if db_cluster:
                raise ClientException("Cluster name already exists")

            # Update title on workflow
            db_workflow = await WorkflowDataManager(self.session).update_by_fields(
                db_workflow,
                {"title": cluster_name},
            )

        if cluster_icon:
            # Update icon on workflow
            # NOTE: Multiple queries because of considering future orchestration upgrade
            db_workflow = await WorkflowDataManager(self.session).update_by_fields(
                db_workflow,
                {"icon": cluster_icon},
            )

        logger.debug("====== Preparing The Payload")

        # Prepare workflow step data (UI Steps)
        workflow_step_data = CreateClusterWorkflowSteps(
            name=cluster_name,
            icon=cluster_icon,
            ingress_url=ingress_url,
            configuration_yaml=configuration_yaml,
            cluster_type=cluster_type,
            credential_id=credential_id if cluster_type == "CLOUD" else None,
            provider_id=provider_id if cluster_type == "CLOUD" else None,
            region=region if cluster_type == "CLOUD" else None,
            credentials=credentials if cluster_type == "CLOUD" else None,
            cloud_provider_unique_id=cloud_credentials.provider.unique_id if cluster_type == "CLOUD" else None,
        ).model_dump(exclude_none=True, exclude_unset=True, mode="json")

        logger.debug(f"====== {workflow_step_data}")

        # Get workflow steps
        db_workflow_steps = await WorkflowStepDataManager(self.session).get_all_workflow_steps(
            {"workflow_id": db_workflow.id}
        )

        # For avoiding another db call for record retrieval, storing db object while iterating over db_workflow_steps
        db_current_workflow_step = None

        if db_workflow_steps:
            for db_step in db_workflow_steps:
                # Get current workflow step
                if db_step.step_number == current_step_number:
                    db_current_workflow_step = db_step

        if db_current_workflow_step:
            logger.debug(f"Workflow {db_workflow.id} step {current_step_number} already exists")

            # Update workflow step data in db
            db_workflow_step = await WorkflowStepDataManager(self.session).update_by_fields(
                db_current_workflow_step,
                {"data": workflow_step_data},
            )
            logger.debug(f"Workflow {db_workflow.id} step {current_step_number} updated")
        else:
            logger.debug(f"Creating workflow step {current_step_number} for workflow {db_workflow.id}")

            # Insert step details in db
            db_workflow_step = await WorkflowStepDataManager(self.session).insert_one(
                WorkflowStepModel(
                    workflow_id=db_workflow.id,
                    step_number=current_step_number,
                    data=workflow_step_data,
                )
            )

        # Update workflow current step as the highest step_number
        db_max_workflow_step_number = max(step.step_number for step in db_workflow_steps) if db_workflow_steps else 0
        workflow_current_step = max(current_step_number, db_max_workflow_step_number)
        logger.info(f"The current step of workflow {db_workflow.id} is {workflow_current_step}")

        # Update workflow step data in db
        db_workflow = await WorkflowDataManager(self.session).update_by_fields(
            db_workflow,
            {"current_step": workflow_current_step},
        )

        # Execute workflow
        # Create next step if workflow is triggered
        if trigger_workflow:
            logger.debug("Workflow triggered")

            # TODO: Currently querying workflow steps again by ordering steps in ascending order
            # To ensure the latest step update is fetched, Consider excluding it later
            db_workflow_steps = await WorkflowStepDataManager(self.session).get_all_workflow_steps(
                {"workflow_id": db_workflow.id}
            )

            # Define the keys required for cluster creation
            keys_of_interest = [
                "name",
                "icon",
                # "configuration_yaml",
                "cluster_type",  # Addition For Cloud Cluster
            ]

            # Add type-specific keys
            if cluster_type == "ON_PREM":
                keys_of_interest.extend(["configuration_yaml", "ingress_url"])
            elif cluster_type == "CLOUD":
                keys_of_interest.extend(
                    ["credential_id", "provider_id", "region", "credentials", "cloud_provider_unique_id"]
                )

            # from workflow steps extract necessary information
            required_data = {}
            for db_workflow_step in db_workflow_steps:
                for key in keys_of_interest:
                    if key in db_workflow_step.data:
                        required_data[key] = db_workflow_step.data[key]

            # Check if all required keys are present
            # required_keys = ["name", "icon", "ingress_url", "configuration_yaml"]
            missing_keys = [key for key in keys_of_interest if key not in required_data]
            if missing_keys:
                raise ClientException(f"Missing required data: {', '.join(missing_keys)}")

            # Check duplicate cluster name
            db_cluster = await ClusterDataManager(self.session).retrieve_by_fields(
                ClusterModel,
                {"name": required_data["name"]},
                exclude_fields={"status": ClusterStatusEnum.DELETED},
                missing_ok=True,
                case_sensitive=False,
            )
            if db_cluster:
                raise ClientException("Cluster name already exists")

            # Trigger create cluster workflow by step
            await self._execute_create_cluster_workflow(
                required_data, current_user_id, db_workflow, current_step_number
            )
            logger.debug("Successfully executed create cluster workflow")

        return db_workflow

    async def _execute_create_cluster_workflow(
        self, data: Dict[str, Any], current_user_id: UUID, db_workflow: WorkflowModel, current_step_number: int
    ) -> None:
        """Execute create cluster workflow."""
        # Create cluster in bud_cluster app
        bud_cluster_response = await self._perform_create_cluster_request(data, db_workflow.id, current_user_id)

        # Add payload dict to response
        for step in bud_cluster_response["steps"]:
            step["payload"] = {}

        create_cluster_events = {BudServeWorkflowStepEventName.CREATE_CLUSTER_EVENTS.value: bud_cluster_response}

        # Increment step number of workflow and workflow step
        current_step_number = current_step_number + 1
        workflow_current_step = current_step_number

        # Update or create next workflow step
        db_workflow_step = await WorkflowStepService(self.session).create_or_update_next_workflow_step(
            db_workflow.id, current_step_number, create_cluster_events
        )
        logger.debug(f"Created workflow step {db_workflow_step.id} for storing create cluster events")

        # Update progress in workflow
        bud_cluster_response["progress_type"] = BudServeWorkflowStepEventName.CREATE_CLUSTER_EVENTS.value
        db_workflow = await WorkflowDataManager(self.session).update_by_fields(
            db_workflow, {"progress": bud_cluster_response, "current_step": workflow_current_step}
        )
        logger.debug(f"Updated progress, current step in workflow {db_workflow.id}")

    async def _perform_create_cluster_request(
        self, data: Dict[str, str], workflow_id: UUID, current_user_id: UUID
    ) -> dict:
        """Make async POST request to create cluster to budcluster app.

        Args:
            data (Dict[str, str]): Data to be sent in the request.

        Returns:
            dict: Response from the server.

        Raises:
            aiohttp.ClientError: If the request fails.
        """
        create_cluster_endpoint = (
            f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_cluster_app_id}/method/cluster"
        )
        cluster_create_request = {
            "enable_master_node": True,
            "name": data["name"],
            "ingress_url": data.get("ingress_url", ""),  # Empty String
            "notification_metadata": {
                "name": BUD_INTERNAL_WORKFLOW,
                "subscriber_ids": str(current_user_id),
                "workflow_id": str(workflow_id),
            },
            "source_topic": f"{app_settings.source_topic}",
        }

        # Extra Values
        cluster_type = data.get("cluster_type", "ON_PREM")
        cluster_create_request["cluster_type"] = cluster_type

        # Add cloud-specific parameters if it's a cloud cluster
        if cluster_type == "CLOUD":
            # TODO: Replace with cloud-specific cedentials and provider information
            cluster_create_request["credential_id"] = str(data["credential_id"])
            cluster_create_request["provider_id"] = str(data["provider_id"])
            cluster_create_request["region"] = data["region"]
            cluster_create_request["credentials"] = data["credentials"]
            cluster_create_request["cluster_type"] = cluster_type
            cluster_create_request["cloud_provider_unique_id"] = data["cloud_provider_unique_id"]

            logger.debug(f"=====Cluster create request: {cluster_create_request}")

            # Make the request for cloud cluster
            async with aiohttp.ClientSession() as session:
                try:
                    form = aiohttp.FormData()
                    form.add_field("cluster_create_request", json.dumps(cluster_create_request))
                    # For cloud cluster, we create a temporary YAML file with minimal configuration
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".yaml", mode="w") as temp_file:
                        # Write minimal configuration to the temporary file
                        yaml.safe_dump({"name": "dummy-cluster"}, temp_file)
                        # temp_file.flush()
                        # Open the file as a binary for proper upload
                        with open(temp_file.name, "rb") as config_file:
                            form.add_field("configuration", config_file, filename="dummy.yaml")
                            # Log Form data
                            logger.debug(f"Form data: {json.dumps(cluster_create_request)}")

                            async with session.post(create_cluster_endpoint, data=form) as response:
                                response_data = await response.json()
                                logger.debug(f"Response from budcluster service: {response_data}")

                                if response.status != 200 or response_data.get("object") == "error":
                                    error_message = response_data.get("message", "Failed to create cloud cluster")
                                    logger.error(
                                        f"Failed to create cloud cluster with external service: {error_message}"
                                    )
                                    raise ClientException(error_message)

                                logger.debug("Successfully created cloud cluster with budcluster service")
                                return response_data

                except ClientException as e:
                    raise e

                except Exception as e:
                    logger.error(f"Failed to make request to budcluster service: {e}")
                    raise ClientException("Unable to create cloud cluster with external service") from e

        else:
            # Create temporary yaml file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".yaml", mode="w") as temp_file:
                try:
                    # Write configuration yaml to temporary yaml file
                    yaml.safe_dump(data["configuration_yaml"], temp_file)

                    logger.debug(f"cluster_create_request: {cluster_create_request}")
                    # Perform the request as a form data
                    async with aiohttp.ClientSession() as session:
                        form = aiohttp.FormData()
                        form.add_field("cluster_create_request", json.dumps(cluster_create_request))

                        # Open the file for reading after writing is complete
                        with open(temp_file.name, "rb") as config_file:
                            form.add_field("configuration", config_file, filename=temp_file.name)
                            try:
                                logger.debug("************************")
                                logger.debug(config_file)
                                logger.debug("************************")

                                async with session.post(create_cluster_endpoint, data=form) as response:
                                    response_data = await response.json()
                                    logger.debug(f"Response from budcluster service: {response_data}")

                                    if response.status != 200 or response_data.get("object") == "error":
                                        error_message = response_data.get("message", "Failed to create cluster")
                                        logger.error(
                                            f"Failed to create cluster with external service: {error_message}"
                                        )
                                        raise ClientException(error_message)

                                    logger.debug("Successfully created cluster with budcluster service")
                                    return response_data

                            except ClientException as e:
                                raise e

                            except Exception as e:
                                logger.error(f"Failed to make request to budcluster service: {e}")
                                raise ClientException("Unable to create cluster with external service") from e

                except yaml.YAMLError as e:
                    logger.error(f"Failed to process YAML configuration: {e}")
                    raise ClientException("Invalid YAML configuration") from e

                except IOError as e:
                    logger.error(f"Failed to write temporary file: {e}")
                    raise ClientException("Failed to process configuration file") from e

                except ClientException as e:
                    raise e

                except Exception as e:
                    logger.exception(f"Unexpected error during cluster creation request {e}")
                    raise ClientException("Unexpected error during cluster creation") from e

                finally:
                    # Delete the temporary file
                    temp_file.close()

    async def create_cluster_from_notification_event(self, payload: NotificationPayload) -> None:
        """Create a cluster in database.

        Args:
            payload: The payload to create the cluster with.

        Raises:
            ClientException: If the cluster already exists.
        """
        logger.debug("Received event for creating cluster")

        # TODO : ask varun if this is can actuallt get data saved in workflow in cluster repo

        # Get workflow and steps
        workflow_id = payload.workflow_id
        db_workflow = await WorkflowDataManager(self.session).retrieve_by_fields(WorkflowModel, {"id": workflow_id})
        db_workflow_steps = await WorkflowStepDataManager(self.session).get_all_workflow_steps(
            {"workflow_id": workflow_id}
        )

        # Define the keys required for endpoint creation
        keys_of_interest = [
            "name",
            "icon",
            "ingress_url",
            "cluster_type",
            "provider_id",
            "credential_id",
            "region",
        ]

        # from workflow steps extract necessary information
        required_data = {}
        for db_workflow_step in db_workflow_steps:
            for key in keys_of_interest:
                if key in db_workflow_step.data:
                    required_data[key] = db_workflow_step.data[key]

        logger.debug("Collected required data from workflow steps")

        # Check duplicate cluster name
        db_cluster = await ClusterDataManager(self.session).retrieve_by_fields(
            ClusterModel,
            {"name": required_data["name"]},
            exclude_fields={"status": ClusterStatusEnum.DELETED},
            missing_ok=True,
            case_sensitive=False,
        )

        if db_cluster:
            logger.error(f"Cluster {required_data['name']} already exists")
            raise ClientException(f"Cluster {required_data['name']} already exists")

        # Get cluster resources from event
        cluster_resources = await self._calculate_cluster_resources(payload.content.result)
        logger.debug("Cluster resources calculated.")

        # Get bud cluster id from event
        bud_cluster_id = payload.content.result["id"]

        cluster_data = ClusterCreate(
            name=required_data["name"],
            icon=required_data["icon"],
            ingress_url=required_data.get("ingress_url"),
            created_by=db_workflow.created_by,
            cluster_id=UUID(bud_cluster_id),
            **cluster_resources.model_dump(exclude_unset=True, exclude_none=True),
            status=ClusterStatusEnum.AVAILABLE,
            status_sync_at=datetime.now(tz=timezone.utc),
            # Cloud Cluster
            cluster_type=required_data.get("cluster_type", "ON_PERM"),
            cloud_provider_id=required_data.get("provider_id"),
            credential_id=required_data.get("credential_id"),
            region=required_data.get("region"),
        )

        # Mark workflow as completed
        logger.debug(f"Updating workflow status: {workflow_id}")

        # Update status for last step
        execution_status = {"status": "success", "message": "Cluster successfully created"}
        try:
            db_cluster = await ClusterDataManager(self.session).insert_one(
                ClusterModel(**cluster_data.model_dump(exclude_unset=True, exclude_none=True))
            )

            # Run The Grafana Creation Workflow
            # grafana = Grafana()
            # await grafana.create_dashboard_from_file(bud_cluster_id, "prometheus", cluster_data.name)

            logger.debug(f"Cluster created successfully: {db_cluster.id}")
        except Exception as e:
            logger.exception(f"Failed to create cluster: {e}")
            execution_status.update({"status": "error", "message": "Failed to create cluster"})
            workflow_data = {"status": WorkflowStatusEnum.FAILED, "reason": str(e)}
        else:
            workflow_data = {"status": WorkflowStatusEnum.COMPLETED}
        finally:
            if db_cluster:
                workflow_step_data = {"workflow_execution_status": execution_status, "cluster_id": str(db_cluster.id)}
            else:
                workflow_step_data = {"workflow_execution_status": execution_status}

            # Update current step number
            current_step_number = db_workflow.current_step + 1
            workflow_current_step = current_step_number

            # Update or create next workflow step
            db_workflow_step = await WorkflowStepService(self.session).create_or_update_next_workflow_step(
                db_workflow.id, current_step_number, workflow_step_data
            )
            logger.debug(f"Upsert workflow step {db_workflow_step.id} for storing create cluster status")

            # Update workflow step data
            workflow_data.update({"current_step": workflow_current_step})
            await WorkflowDataManager(self.session).update_by_fields(db_workflow, workflow_data)

            # Send notification to workflow creator
            notification_request = (
                NotificationBuilder()
                .set_content(
                    title=db_cluster.name,
                    message="Cluster is onboarded",
                    icon=db_cluster.icon,
                    result=NotificationResult(target_id=db_cluster.id, target_type="cluster").model_dump(
                        exclude_none=True, exclude_unset=True
                    ),
                )
                .set_payload(
                    workflow_id=str(db_workflow.id), type=NotificationTypeEnum.CLUSTER_ONBOARDING_SUCCESS.value
                )
                .set_notification_request(subscriber_ids=[str(db_workflow.created_by)])
                .build()
            )
            await BudNotifyService().send_notification(notification_request)

            # Create request to trigger cluster status update periodic task
            await self._perform_cluster_status_update_request(db_cluster.cluster_id)

    async def delete_cluster_from_notification_event(self, payload: NotificationPayload) -> None:
        """Delete a cluster in database.

        Args:
            payload: The payload to delete the cluster with.

        Raises:
            ClientException: If the cluster already exists.
        """
        logger.debug("Received event for deleting cluster")

        # Get workflow and steps
        workflow_id = payload.workflow_id
        db_workflow = await WorkflowDataManager(self.session).retrieve_by_fields(WorkflowModel, {"id": workflow_id})
        db_workflow_steps = await WorkflowStepDataManager(self.session).get_all_workflow_steps(
            {"workflow_id": workflow_id}
        )

        # Define the keys required for endpoint creation
        keys_of_interest = [
            "cluster_id",
        ]

        # from workflow steps extract necessary information
        required_data = {}
        for db_workflow_step in db_workflow_steps:
            for key in keys_of_interest:
                if key in db_workflow_step.data:
                    required_data[key] = db_workflow_step.data[key]

        logger.debug("Collected required data from workflow steps")

        # Retrieve cluster from db
        db_cluster = await ClusterDataManager(self.session).retrieve_by_fields(
            ClusterModel,
            {"id": required_data["cluster_id"]},
            exclude_fields={"status": ClusterStatusEnum.DELETED},
            missing_ok=True,
        )
        logger.debug(f"Cluster retrieved successfully: {db_cluster.id}")

        # Mark cluster as deleted
        db_cluster = await ClusterDataManager(self.session).update_by_fields(
            db_cluster, {"status": ClusterStatusEnum.DELETED}
        )
        logger.debug(f"Cluster {db_cluster.id} marked as deleted")

        # Mark workflow as completed
        await WorkflowDataManager(self.session).update_by_fields(db_workflow, {"status": WorkflowStatusEnum.COMPLETED})
        logger.debug(f"Workflow {db_workflow.id} marked as completed")

        # Remove from recommended clusters
        await ModelClusterRecommendedDataManager(self.session).delete_by_fields(
            ModelClusterRecommendedModel, {"cluster_id": db_cluster.id}
        )
        logger.debug(f"Model recommended cluster data for cluster {db_cluster.id} deleted")

        # Send notification to workflow creator
        notification_request = (
            NotificationBuilder()
            .set_content(
                title=db_cluster.name,
                message="Cluster Deleted",
                icon=db_cluster.icon,
            )
            .set_payload(workflow_id=str(db_workflow.id), type=NotificationTypeEnum.CLUSTER_DELETION_SUCCESS.value)
            .set_notification_request(subscriber_ids=[str(db_workflow.created_by)])
            .build()
        )
        await BudNotifyService().send_notification(notification_request)

    async def update_cluster_status_from_notification_event(self, payload: NotificationPayload) -> None:
        """Delete a cluster in database.

        Args:
            payload: The payload to delete the cluster with.

        Raises:
            ClientException: If the cluster already exists.
        """
        logger.debug("Received event for updating cluster status")

        # Get cluster from db
        db_cluster = await ClusterDataManager(self.session).retrieve_by_fields(
            ClusterModel,
            {"cluster_id": payload.content.result["cluster_id"]},
            exclude_fields={"status": ClusterStatusEnum.DELETED},
        )
        logger.debug(f"Cluster retrieved successfully: {db_cluster.id}")

        # Check if cluster is already in deleting state
        if db_cluster.status == ClusterStatusEnum.DELETING:
            # Check how long the cluster has been in deleting state
            time_in_deleting = datetime.now(timezone.utc) - db_cluster.modified_at

            if time_in_deleting > timedelta(days=1):
                # Move to ERROR state if stuck in DELETING for more than 24 hours
                logger.warning(
                    f"Cluster {db_cluster.id} has been in DELETING state for {time_in_deleting}. "
                    "Moving to ERROR state."
                )
                update_data = {
                    "status": ClusterStatusEnum.ERROR,
                    "reason": f"Cluster stuck in DELETING state for {time_in_deleting}",
                }
                await ClusterDataManager(self.session).update_by_fields(db_cluster, update_data)
                return  # Successfully handled, no error
            else:
                # Log as info and treat as success (idempotent operation)
                logger.info(
                    f"Cluster {db_cluster.id} already in DELETING state for {time_in_deleting}. "
                    "Ignoring duplicate status update."
                )
                return  # Successfully handled, no error

        # Update data
        update_data = {"status": payload.content.result["status"]}

        if "node_info" in payload.content.result and (
            "nodes" in payload.content.result["node_info"] and len(payload.content.result["node_info"]["nodes"]) > 0
        ):
            cluster_resources = await self._calculate_cluster_resources(payload.content.result["node_info"])
            update_data.update(cluster_resources.model_dump(exclude_unset=True, exclude_none=True))
            logger.debug(f"Cluster resources updated: {update_data}")

        # Update cluster status
        db_cluster = await ClusterDataManager(self.session).update_by_fields(db_cluster, update_data)
        logger.debug(f"Cluster {db_cluster.id} status updated to {payload.content.result['status']}")

    async def _calculate_cluster_resources(self, data: Dict[str, Any]) -> ClusterResourcesInfo:
        """Calculate the cluster resources.

        Args:
            data: The data to calculate the cluster resources with.

        Returns:
            ClusterResourcesInfo: The cluster resources.
        """
        cpu_count = 0
        gpu_count = 0
        hpu_count = 0
        cpu_total_workers = 0
        gpu_total_workers = 0
        hpu_total_workers = 0
        total_nodes = len(data.get("nodes", []))
        available_nodes = len([node for node in data.get("nodes", []) if node.get("status", False)])

        # Iterate through each node
        for node in data.get("nodes", []):
            # Iterate through devices in each node
            for device in node.get("devices", []):
                # Get the available count and device type
                worker_count = device.get("available_count", 0)
                device_type = device.get("type", "").lower()

                # Increment the appropriate counter
                # Device types from budcluster: "cpu", "cpu_high", "cuda", "gpu", "hpu"
                if device_type in ("cpu", "cpu_high"):
                    cpu_count += 1
                    cpu_total_workers += worker_count
                elif device_type in ("gpu", "cuda"):
                    gpu_count += 1
                    gpu_total_workers += worker_count
                elif device_type == "hpu":
                    hpu_count += 1
                    hpu_total_workers += worker_count

        return ClusterResourcesInfo(
            cpu_count=cpu_count,
            gpu_count=gpu_count,
            hpu_count=hpu_count,
            cpu_total_workers=cpu_total_workers,
            cpu_available_workers=cpu_total_workers,
            gpu_total_workers=gpu_total_workers,
            gpu_available_workers=gpu_total_workers,
            hpu_total_workers=hpu_total_workers,
            hpu_available_workers=hpu_total_workers,
            total_nodes=total_nodes,
            available_nodes=available_nodes,
        )

    async def _perform_bud_cluster_edit_request(self, bud_cluster_id: UUID, data: Dict[str, Any]) -> Dict:
        """Perform edit cluster request to bud_cluster app.

        Args:
            bud_cluster_id: The ID of the cluster to edit.
            data: The data to edit the cluster with.
        """
        edit_cluster_endpoint = f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_cluster_app_id}/method/cluster/{bud_cluster_id}"

        payload = {"ingress_url": data["ingress_url"]}

        logger.debug(f"Performing edit cluster request to budcluster {payload}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.patch(edit_cluster_endpoint, json=payload) as response:
                    response_data = await response.json()
                    if response.status != 200 or response_data.get("object") == "error":
                        logger.error(f"Failed to edit cluster: {response.status} {response_data}")
                        raise ClientException(
                            "Failed to edit cluster", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                        )

                    logger.debug("Successfully edited cluster from budcluster")
                    return response_data
        except Exception as e:
            logger.exception(f"Failed to send edit cluster request: {e}")
            raise ClientException("Failed to edit cluster", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR) from e

    async def edit_cluster(self, cluster_id: UUID, data: Dict[str, Any]) -> ClusterResponse:
        """Edit cloud model by validating and updating specific fields, and saving an uploaded file if provided."""
        # Retrieve existing model
        db_cluster = await ClusterDataManager(self.session).retrieve_by_fields(
            model=ClusterModel, fields={"id": cluster_id}
        )

        if "name" in data:
            duplicate_cluster = await ClusterDataManager(self.session).retrieve_by_fields(
                model=ClusterModel,
                fields={"name": data["name"]},
                exclude_fields={"id": cluster_id, "status": ClusterStatusEnum.DELETED},
                missing_ok=True,
                case_sensitive=False,
            )
            if duplicate_cluster:
                raise ClientException("Cluster name already exists")

        if "ingress_url" in data:
            await self._perform_bud_cluster_edit_request(db_cluster.cluster_id, data)

        db_cluster = await ClusterDataManager(self.session).update_by_fields(db_cluster, data)

        return db_cluster

    async def get_cluster_details(self, cluster_id: UUID) -> ClusterDetailResponse:
        """Retrieve cluster details."""
        # Retrieve cluster details
        db_cluster = await ClusterDataManager(self.session).retrieve_by_fields(
            ClusterModel, fields={"id": cluster_id}, exclude_fields={"status": ClusterStatusEnum.DELETED}
        )

        cluster_details = ClusterResponse.model_validate(db_cluster)

        total_endpoints_count, running_endpoints_count, active_replicas, total_replicas = await EndpointDataManager(
            self.session
        ).get_cluster_count_details(cluster_id)
        # Determine hardware types
        hardware_type = get_hardware_types(db_cluster.cpu_count, db_cluster.gpu_count, db_cluster.hpu_count)

        # Combine details and stats
        cluster_details_response = ClusterDetailResponse.model_validate(
            {
                **cluster_details.model_dump(),
                "total_endpoints_count": total_endpoints_count,
                "running_endpoints_count": running_endpoints_count,
                "active_workers_count": active_replicas,
                "total_workers_count": total_replicas,
                "hardware_type": hardware_type,
            }
        )

        return cluster_details_response

    async def delete_cluster(self, cluster_id: UUID, current_user_id: UUID) -> WorkflowModel:
        """Delete a cluster by its ID.

        Args:
            cluster_id: The ID of the cluster to delete.
        """
        db_cluster = await ClusterDataManager(self.session).retrieve_by_fields(
            ClusterModel, fields={"id": cluster_id}, exclude_fields={"status": ClusterStatusEnum.DELETED}
        )

        if db_cluster.status == ClusterStatusEnum.DELETING:
            raise ClientException("Cluster is already deleting")

        # Check for active endpoints
        db_endpoints = await EndpointDataManager(self.session).get_all_by_fields(
            EndpointModel,
            fields={"cluster_id": cluster_id},
            exclude_fields={"status": EndpointStatusEnum.DELETED},
        )

        # Raise error if cluster has active endpoints
        if db_endpoints:
            raise ClientException("Cannot delete cluster with active deployments")

        current_step_number = 1
        # Retrieve or create workflow
        workflow_create = WorkflowUtilCreate(
            workflow_type=WorkflowTypeEnum.CLUSTER_DELETION,
            title=db_cluster.name,
            total_steps=current_step_number,
            icon=db_cluster.icon,
            tag="Cluster Repository",
        )
        db_workflow = await WorkflowService(self.session).retrieve_or_create_workflow(
            workflow_id=None, workflow_data=workflow_create, current_user_id=current_user_id
        )
        logger.debug(f"Delete cluster workflow {db_workflow.id} created")

        cloud_payload = None
        # # Branch For Cloud & On Perm
        if db_cluster.cluster_type == "CLOUD":
            # Get Credentials
            credential_id = db_cluster.credential_id
            provider_id = db_cluster.cloud_provider_id

            # Debug
            logger.debug(f"+++ CLOUD +++ {credential_id}")
            logger.debug(f"+++ CLOUD +++ {provider_id}")

            cloud_credentials = await CloudProviderCredentialDataManager(self.session).retrieve_by_fields(
                CloudCredentials,
                fields={"id": credential_id, "provider_id": provider_id},
                missing_ok=False,
            )

            if not cloud_credentials:
                raise ClientException("Cloud provider credential not found")

            credentials = cloud_credentials.credential
            provider_unique_id = cloud_credentials.provider.unique_id

            cloud_payload = {
                "credentail_id": str(credential_id),
                "provider_id": str(provider_id),
                "region": db_cluster.region,
                "credentials": credentials,
                "provider_unique_id": str(provider_unique_id),
                "cluster_type": db_cluster.cluster_type,
                "name": db_cluster.name,
            }

        # Perform delete cluster request to bud_cluster app
        try:
            bud_cluster_response = await self._perform_bud_cluster_delete_request(
                db_cluster.cluster_id, current_user_id, db_workflow.id, cloud_payload
            )
        except ClientException as e:
            await WorkflowDataManager(self.session).update_by_fields(
                db_workflow, {"status": WorkflowStatusEnum.FAILED}
            )
            raise e

        # Add payload dict to response
        for step in bud_cluster_response["steps"]:
            step["payload"] = {}

        delete_cluster_workflow_id = bud_cluster_response.get("workflow_id")
        delete_cluster_events = {
            BudServeWorkflowStepEventName.DELETE_CLUSTER_EVENTS.value: bud_cluster_response,
            "delete_cluster_workflow_id": delete_cluster_workflow_id,
            "cluster_id": str(db_cluster.id),
        }

        # Insert step details in db
        await WorkflowStepDataManager(self.session).insert_one(
            WorkflowStepModel(
                workflow_id=db_workflow.id,
                step_number=current_step_number,
                data=delete_cluster_events,
            )
        )
        logger.debug(f"Created workflow step {current_step_number} for workflow {db_workflow.id}")

        # Update progress in workflow
        bud_cluster_response["progress_type"] = BudServeWorkflowStepEventName.DELETE_CLUSTER_EVENTS.value
        await WorkflowDataManager(self.session).update_by_fields(
            db_workflow, {"progress": bud_cluster_response, "current_step": current_step_number}
        )

        # Update cluster status to deleting
        await ClusterDataManager(self.session).update_by_fields(db_cluster, {"status": ClusterStatusEnum.DELETING})
        logger.debug(f"Cluster {db_cluster.id} status updated to {ClusterStatusEnum.DELETING.value}")

        return db_workflow

    async def _perform_bud_cluster_delete_request(
        self,
        bud_cluster_id: UUID,
        current_user_id: UUID,
        workflow_id: UUID,
        cloud_payload: Optional[Dict[str, Any]] = None,
    ) -> Dict:
        """Perform delete cluster request to bud_cluster app.

        Args:
            bud_cluster_id: The ID of the cluster to delete.
        """
        delete_cluster_endpoint = (
            f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_cluster_app_id}/method/cluster/delete"
        )

        cluster_type = cloud_payload.get("cluster_type", "ON_PREM") if cloud_payload is not None else "ON_PREM"

        payload = {
            "cluster_id": str(bud_cluster_id),
            "cluster_type": cluster_type,
            "notification_metadata": {
                "name": BUD_INTERNAL_WORKFLOW,
                "subscriber_ids": str(current_user_id),
                "workflow_id": str(workflow_id),
            },
            "source_topic": f"{app_settings.source_topic}",
        }

        if cloud_payload:
            payload["cloud_payload"] = json.dumps(cloud_payload)

        logger.debug(f"Performing delete cluster request to budcluster {payload}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(delete_cluster_endpoint, json=payload) as response:
                    response_data = await response.json()
                    if response.status != 200 or response_data.get("object") == "error":
                        logger.error(f"Failed to delete cluster: {response.status} {response_data}")
                        raise ClientException(
                            "Failed to delete cluster", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                        )

                    logger.debug("Successfully deleted cluster from budcluster")
                    return response_data
        except Exception as e:
            logger.exception(f"Failed to send delete cluster request: {e}")
            raise ClientException("Failed to delete cluster", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR) from e

    async def handle_recommended_cluster_events(self, payload: NotificationPayload) -> None:
        """Handle recommended cluster events."""
        logger.debug("Received event of recommending cluster")

        workflow_id = payload.workflow_id
        dapr_service = DaprService()
        state_store_key = RECOMMENDED_CLUSTER_SCHEDULER_STATE_STORE_KEY

        # Check the event belongs to recommended cluster scheduler workflow (Dapr state store)
        try:
            recommended_cluster_scheduler_state = dapr_service.get_state(
                store_name=app_settings.statestore_name, key=state_store_key
            ).json()
            logger.debug("State store %s already exists", state_store_key)
        except Exception as e:
            logger.exception("Failed to get state store %s", e)
            return

        if workflow_id in recommended_cluster_scheduler_state:
            logger.debug("Workflow %s found in state store", workflow_id)
            logger.debug("Identified as recommended cluster scheduler workflow")
            await self._handle_recommended_cluster_scheduler_workflow_event(
                payload, recommended_cluster_scheduler_state
            )
        else:
            logger.debug("Workflow %s not found in state store", workflow_id)
            logger.debug("Identified as recommended cluster notification event")
            await self._notify_recommended_cluster_from_notification_event(payload)

    async def _handle_recommended_cluster_scheduler_workflow_event(
        self, payload: NotificationPayload, recommended_cluster_scheduler_state: Dict[str, Any]
    ) -> None:
        """Handle recommended cluster scheduler workflow."""
        from .workflows import ClusterRecommendedSchedulerWorkflows

        logger.debug("Received event of recommending cluster scheduler workflow")

        # Get workflow and steps
        workflow_id = payload.workflow_id

        try:
            # Get workflow data from state store
            recommended_cluster_scheduler_data = recommended_cluster_scheduler_state.get(str(workflow_id))
            model_id = UUID(recommended_cluster_scheduler_data["model_id"])

            db_model = await ModelDataManager(self.session).retrieve_by_fields(
                Model, fields={"id": model_id, "status": ModelStatusEnum.ACTIVE}, missing_ok=True
            )

            if not db_model:
                logger.debug("Model not found")
                await self._cleanup_recommended_cluster_data(
                    model_id, workflow_id, recommended_cluster_scheduler_state
                )
                return

            recommended_clusters = payload.content.result.get("recommendations", [])

            if not recommended_clusters:
                logger.debug("No recommended clusters found")
                await self._cleanup_recommended_cluster_data(
                    model_id, workflow_id, recommended_cluster_scheduler_state
                )
                return

            recommended_cluster = recommended_clusters[0]
            bud_cluster_id = recommended_cluster["cluster_id"]
            db_cluster = await ClusterDataManager(self.session).retrieve_by_fields(
                ClusterModel,
                fields={"cluster_id": bud_cluster_id},
                exclude_fields={"status": ClusterStatusEnum.DELETED},
                missing_ok=True,
            )

            if not db_cluster:
                logger.debug("Cluster not found")
                await self._cleanup_recommended_cluster_data(
                    model_id, workflow_id, recommended_cluster_scheduler_state
                )
                return

            device_types = [
                device["device_type"].lower()
                for device in recommended_cluster.get("metrics", {}).get("device_types", [])
                if device.get("device_type")
            ]
            cost_per_million_tokens = recommended_cluster.get("metrics", {}).get("cost_per_million_tokens")

            # Check if model cluster recommended already exists
            db_model_cluster_recommended = await ModelClusterRecommendedDataManager(self.session).retrieve_by_fields(
                ModelClusterRecommendedModel, fields={"model_id": model_id}, missing_ok=True
            )

            if db_model_cluster_recommended:
                # Update model cluster recommended
                model_cluster_recommended_update = ModelClusterRecommendedUpdate(
                    model_id=model_id,
                    cluster_id=db_cluster.id,
                    hardware_type=device_types,
                    cost_per_million_tokens=cost_per_million_tokens,
                )
                db_model_cluster_recommended = await ModelClusterRecommendedDataManager(self.session).update_by_fields(
                    db_model_cluster_recommended, model_cluster_recommended_update.model_dump()
                )
                logger.debug("Updated model cluster recommended %s", db_model_cluster_recommended.id)
            else:
                # Create model cluster recommended
                model_cluster_recommended_create = ModelClusterRecommendedCreate(
                    model_id=model_id,
                    cluster_id=db_cluster.id,
                    hardware_type=device_types,
                    cost_per_million_tokens=cost_per_million_tokens,
                )
                db_model_cluster_recommended = await ModelClusterRecommendedDataManager(self.session).insert_one(
                    ModelClusterRecommendedModel(**model_cluster_recommended_create.model_dump())
                )
                logger.debug("Created model cluster recommended %s", db_model_cluster_recommended.id)

            # Remove workflow specific state store data
            recommended_cluster_scheduler_state.pop(str(workflow_id))
            try:
                dapr_service = DaprService()
                await dapr_service.save_to_statestore(
                    store_name=app_settings.statestore_name,
                    key=RECOMMENDED_CLUSTER_SCHEDULER_STATE_STORE_KEY,
                    value=recommended_cluster_scheduler_state,
                )
                logger.debug("State store %s updated", RECOMMENDED_CLUSTER_SCHEDULER_STATE_STORE_KEY)
            except Exception as e:
                logger.exception("Failed to save state store %s", e)

            # Trigger recommended cluster scheduler workflow
            await ClusterRecommendedSchedulerWorkflows().__call__()
            logger.debug("Recommended cluster scheduler workflow re-triggered")
        except Exception as e:
            logger.error("Error occurred while handling recommended cluster scheduler workflow %s", e)

            # Remove workflow specific state store data
            recommended_cluster_scheduler_state.pop(str(workflow_id))

            try:
                dapr_service = DaprService()
                await dapr_service.save_to_statestore(
                    store_name=app_settings.statestore_name,
                    key=RECOMMENDED_CLUSTER_SCHEDULER_STATE_STORE_KEY,
                    value=recommended_cluster_scheduler_state,
                )
                logger.debug("State store %s updated", RECOMMENDED_CLUSTER_SCHEDULER_STATE_STORE_KEY)
            except Exception as e:
                logger.error("Failed to update state store data %s", e)

            # Trigger recommended cluster scheduler workflow
            await ClusterRecommendedSchedulerWorkflows().__call__()
            logger.debug("Recommended cluster scheduler workflow re-triggered")

    async def _cleanup_recommended_cluster_data(
        self, model_id: UUID, workflow_id: UUID, recommended_cluster_scheduler_state: Dict[str, Any]
    ) -> None:
        """Cleanup recommended cluster data."""
        from .workflows import ClusterRecommendedSchedulerWorkflows

        logger.debug("Cleaning up recommended cluster data for model %s", model_id)

        try:
            # Check existing recommended cluster data
            db_model_cluster_recommended = await ModelClusterRecommendedDataManager(self.session).retrieve_by_fields(
                ModelClusterRecommendedModel, fields={"model_id": model_id}, missing_ok=True
            )

            # Delete model cluster recommended
            if db_model_cluster_recommended:
                await ModelClusterRecommendedDataManager(self.session).delete_one(db_model_cluster_recommended)
                logger.debug("Deleted model cluster recommended %s", db_model_cluster_recommended.id)

            # Remove workflow specific state store data
            recommended_cluster_scheduler_state.pop(str(workflow_id))
            try:
                dapr_service = DaprService()
                await dapr_service.save_to_statestore(
                    store_name=app_settings.statestore_name,
                    key=RECOMMENDED_CLUSTER_SCHEDULER_STATE_STORE_KEY,
                    value=recommended_cluster_scheduler_state,
                )
                logger.debug("State store %s updated", RECOMMENDED_CLUSTER_SCHEDULER_STATE_STORE_KEY)
            except Exception as e:
                logger.exception("Failed to save state store %s", e)

            # Trigger recommended cluster scheduler workflow
            await ClusterRecommendedSchedulerWorkflows().__call__()
            logger.debug("Recommended cluster scheduler workflow re-triggered")
        except Exception as e:
            logger.error("Error occurred while cleaning up recommended cluster workflow %s", e)

            # Trigger recommended cluster scheduler workflow
            await ClusterRecommendedSchedulerWorkflows().__call__()
            logger.debug("Recommended cluster scheduler workflow re-triggered")

    async def handle_recommended_cluster_failure_events(self, payload: NotificationPayload) -> None:
        """Handle recommended cluster failure events."""
        from .workflows import ClusterRecommendedSchedulerWorkflows

        logger.debug("Received failure event of recommending cluster")

        workflow_id = payload.workflow_id
        dapr_service = DaprService()
        state_store_key = RECOMMENDED_CLUSTER_SCHEDULER_STATE_STORE_KEY

        # Check the event belongs to recommended cluster scheduler workflow (Dapr state store)
        try:
            recommended_cluster_scheduler_state = dapr_service.get_state(
                store_name=app_settings.statestore_name, key=state_store_key
            ).json()
            logger.debug("State store %s already exists", state_store_key)
        except Exception as e:
            logger.exception("Failed to get state store %s", e)
            return

        if workflow_id in recommended_cluster_scheduler_state:
            logger.debug("Found failed events from bud simulator")

            # Remove workflow specific state store data
            recommended_cluster_scheduler_state.pop(str(workflow_id))

            try:
                dapr_service = DaprService()
                await dapr_service.save_to_statestore(
                    store_name=app_settings.statestore_name,
                    key=RECOMMENDED_CLUSTER_SCHEDULER_STATE_STORE_KEY,
                    value=recommended_cluster_scheduler_state,
                )
                logger.debug("State store %s updated", RECOMMENDED_CLUSTER_SCHEDULER_STATE_STORE_KEY)
            except Exception as e:
                logger.exception("Failed to save state store %s", e)

            # Trigger recommended cluster scheduler workflow
            await ClusterRecommendedSchedulerWorkflows().__call__()
            logger.debug("Recommended cluster scheduler workflow re-triggered")

    async def _notify_recommended_cluster_from_notification_event(self, payload: NotificationPayload) -> None:
        logger.debug("Received event of recommending cluster")

        # Get workflow and steps
        workflow_id = payload.workflow_id
        db_workflow = await WorkflowDataManager(self.session).retrieve_by_fields(WorkflowModel, {"id": workflow_id})
        db_workflow_steps = await WorkflowStepDataManager(self.session).get_all_workflow_steps(
            {"workflow_id": workflow_id}
        )

        # Define the keys required for endpoint creation
        keys_of_interest = [
            "model_id",
        ]

        # from workflow steps extract necessary information
        required_data = {}
        for db_workflow_step in db_workflow_steps:
            for key in keys_of_interest:
                if key in db_workflow_step.data:
                    required_data[key] = db_workflow_step.data[key]
        logger.debug("Collected required data from workflow steps")

        # NOTE: Frontend will fetch this step details from clusters/recommended/{workflow_id}
        # In order to navigate from widget this extra step need to be created.
        # Update current step number
        current_step_number = db_workflow.current_step + 1
        workflow_current_step = current_step_number

        db_workflow_step = await WorkflowStepService(self.session).create_or_update_next_workflow_step(
            db_workflow.id, current_step_number, {}
        )
        logger.debug(f"Upsert workflow step {db_workflow_step.id} as empty step")

        # Update current step number in workflow
        await WorkflowDataManager(self.session).update_by_fields(db_workflow, {"current_step": workflow_current_step})
        logger.debug(f"Updated current step number in workflow: {workflow_id}")

        # Fetch model
        db_model = await ModelDataManager(self.session).retrieve_by_fields(
            Model, {"id": required_data["model_id"], "status": ModelStatusEnum.ACTIVE}, missing_ok=True
        )
        model_icon = await ModelServiceUtil(self.session).get_model_icon(db_model)

        # Get bud cluster ids from recommendations
        recommendations = payload.content.result.get("recommendations", [])
        bud_cluster_ids = [UUID(recommendation["cluster_id"]) for recommendation in recommendations]
        logger.debug(f"Found {len(bud_cluster_ids)} clusters from budsim")
        logger.debug(f"bud cluster_ids from budsim: {bud_cluster_ids}")

        # Get active clusters by cluster ids
        _, db_active_clusters_count = await ClusterDataManager(self.session).get_available_clusters_by_cluster_ids(
            bud_cluster_ids
        )
        logger.debug(f"Found {db_active_clusters_count} active clusters from db")

        # Update cluster count in workflow current progress
        await self._update_workflow_progress_cluster_count(db_workflow, db_active_clusters_count)
        logger.debug(f"Updated cluster count in workflow progress: {db_workflow.id}")

        if db_active_clusters_count == 0:
            message = "Clusters Not Found"
        else:
            message = f"Found Top {db_active_clusters_count} Clusters"

        # Send notification to workflow creator
        notification_request = (
            NotificationBuilder()
            .set_content(
                title=db_model.name,
                message=message,
                icon=model_icon,
                result=NotificationResult(target_id=db_workflow.id, target_type="workflow").model_dump(
                    exclude_none=True, exclude_unset=True
                ),
            )
            .set_payload(workflow_id=str(db_workflow.id), type=NotificationTypeEnum.RECOMMENDED_CLUSTER_SUCCESS.value)
            .set_notification_request(subscriber_ids=[str(db_workflow.created_by)])
            .build()
        )
        await BudNotifyService().send_notification(notification_request)

    async def _update_workflow_progress_cluster_count(self, db_workflow: WorkflowModel, cluster_count: int) -> None:
        """Update workflow progress cluster count."""
        if not isinstance(db_workflow.progress, dict):
            logger.warning(f"Workflow {db_workflow.id} progress is not in expected format")
            return

        progress_type = db_workflow.progress.get("progress_type")
        if progress_type != BudServeWorkflowStepEventName.BUD_SIMULATOR_EVENTS.value:
            logger.warning(
                f"Progress type {progress_type} does not match event name {BudServeWorkflowStepEventName.BUD_SIMULATOR_EVENTS.value}"
            )
            return

        workflow_progress = db_workflow.progress
        workflow_progress["recommended_cluster_count"] = cluster_count

        # Update progress in workflow
        self.session.refresh(db_workflow)
        db_workflow = await WorkflowDataManager(self.session).update_by_fields(
            db_workflow, {"progress": workflow_progress}
        )
        logger.debug(f"Updated workflow progress cluster count: {db_workflow.id}")

    async def cancel_cluster_onboarding_workflow(self, workflow_id: UUID) -> None:
        """Cancel cluster onboarding workflow."""
        db_workflow = await WorkflowDataManager(self.session).retrieve_by_fields(WorkflowModel, {"id": workflow_id})
        db_workflow_steps = await WorkflowStepDataManager(self.session).get_all_workflow_steps(
            {"workflow_id": db_workflow.id}
        )

        # Define the keys required for endpoint creation
        keys_of_interest = [
            BudServeWorkflowStepEventName.CREATE_CLUSTER_EVENTS.value,
        ]

        # from workflow steps extract necessary information
        required_data = {}
        for db_workflow_step in db_workflow_steps:
            for key in keys_of_interest:
                if key in db_workflow_step.data:
                    required_data[key] = db_workflow_step.data[key]
        logger.debug("Collected required data from workflow steps")

        if required_data.get(BudServeWorkflowStepEventName.CREATE_CLUSTER_EVENTS.value) is None:
            raise ClientException("Cluster onboarding process has not been initiated")

        create_cluster_response = required_data.get(BudServeWorkflowStepEventName.CREATE_CLUSTER_EVENTS.value)
        dapr_workflow_id = create_cluster_response.get("workflow_id")

        try:
            await self._perform_cancel_cluster_onboarding_request(dapr_workflow_id)
        except ClientException as e:
            raise e

    async def _perform_cancel_cluster_onboarding_request(self, workflow_id: str) -> Dict:
        """Perform delete cluster request to bud_cluster app.

        Args:
            workflow_id: The ID of the workflow to cancel.
        """
        cancel_cluster_endpoint = f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_cluster_app_id}/method/cluster/cancel/{workflow_id}"

        logger.debug(f"Performing cancel cluster onboarding request to budcluster {cancel_cluster_endpoint}")
        try:
            async with aiohttp.ClientSession() as session, session.post(cancel_cluster_endpoint) as response:
                response_data = await response.json()
                if response.status != 200 or response_data.get("object") == "error":
                    logger.error(f"Failed to cancel cluster onboarding: {response.status} {response_data}")
                    raise ClientException(
                        "Failed to cancel cluster onboarding", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )

                logger.debug("Successfully cancelled cluster onboarding")
                return response_data
        except Exception as e:
            logger.exception(f"Failed to send cancel cluster onboarding request: {e}")
            raise ClientException(
                "Failed to cancel cluster onboarding", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            ) from e

    async def _perform_cluster_status_update_request(self, cluster_id: UUID) -> Dict:
        """Perform update cluster node status request to bud_cluster app.

        Args:
            cluster_id: The ID of the cluster to update.
            current_user_id: The ID of the current user.
        """
        update_cluster_endpoint = f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_cluster_app_id}/method/cluster/update-node-status"

        try:
            payload = {"cluster_id": str(cluster_id)}
            logger.debug(
                f"Performing update cluster node status request. payload: {payload}, endpoint: {update_cluster_endpoint}"
            )
            async with aiohttp.ClientSession() as session:
                async with session.post(update_cluster_endpoint, json=payload) as response:
                    response_data = await response.json()
                    if response.status != 200 or response_data.get("object") == "error":
                        logger.error(f"Failed to update cluster node status: {response.status} {response_data}")
                        raise ClientException(
                            "Failed to update cluster node status", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                        )

                    logger.debug("Successfully updated cluster node status")
                    return response_data
        except Exception as e:
            logger.exception(f"Failed to send update cluster node status request: {e}")
            raise ClientException(
                "Failed to update cluster node status", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            ) from e

    async def get_all_endpoints_in_cluster(
        self,
        cluster_id: UUID,
        offset: int,
        limit: int,
        filters: Dict[str, Any],
        order_by: List[str],
        search: bool,
    ) -> Tuple[List[ClusterEndpointResponse], int]:
        """Get all endpoints in a cluster."""
        # verify cluster id
        await ClusterDataManager(self.session).retrieve_by_fields(
            ClusterModel,
            fields={"id": cluster_id},
            exclude_fields={"status": ClusterStatusEnum.DELETED},
        )

        db_results, count = await EndpointDataManager(self.session).get_all_endpoints_in_cluster(
            cluster_id, offset, limit, filters, order_by, search
        )

        result = []
        for db_result in db_results:
            db_endpoint = db_result[0]
            db_project = db_result[1]
            db_model = db_result[2]
            total_workers = db_result[3]
            active_workers = db_result[4]

            result.append(
                ClusterEndpointResponse(
                    id=db_endpoint.id,
                    name=db_endpoint.name,
                    status=db_endpoint.status,
                    created_at=db_endpoint.created_at,
                    project=ProjectSchema.model_validate(db_project),
                    model=ModelSchema.model_validate(db_model),
                    active_workers=active_workers,
                    total_workers=total_workers,
                    roi=12,  # Dummy value for ROI
                )
            )

        return result, count

    async def get_cluster_metrics(
        self, cluster_id: UUID, time_range: str = "today", metric_type: MetricTypeEnum = MetricTypeEnum.ALL
    ) -> Dict[str, Any]:
        """Get cluster metrics.

        Args:
            cluster_id: The cluster ID to get metrics for
            time_range: The time range to get metrics for ('today', '7days', 'month')
            metric_type: The type of metrics to return (ALL, MEMORY, CPU, DISK, GPU, HPU, NETWORK)

        Returns:
            Dict containing the filtered metrics based on metric_type
        """
        # Get cluster details to verify it exists
        db_cluster = await self.get_cluster_details(cluster_id)

        # Get metrics from Prometheus with filtering at query level
        metrics_fetcher = ClusterMetricsFetcher(app_settings.prometheus_url)
        metrics = await metrics_fetcher.get_cluster_metrics(
            cluster_id=db_cluster.cluster_id, time_range=time_range, metric_type=metric_type.value.lower()
        )

        if not metrics:
            raise ClientException("Failed to fetch metrics from Prometheus")

        # Add metric type to response
        metrics["metric_type"] = metric_type
        return metrics

    async def get_node_wise_metrics(self, cluster_id: UUID) -> Dict[str, Dict[str, Any]]:
        """Get node-wise metrics for a cluster.

        Args:
            cluster_id: The ID of the cluster to get metrics for

        Returns:
            Dict containing the node-wise metrics
        """
        # Get cluster details to verify it exists
        db_cluster = await self.get_cluster_details(cluster_id)

        try:
            # Call budmetrics service to get ClickHouse-based node metrics
            metrics_endpoint = (
                f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_metrics_app_id}/"
                f"method/cluster-metrics/{db_cluster.cluster_id}/nodes"
            )

            # Call budcluster service to get node details
            nodes_data = await self._perform_get_cluster_nodes_request(db_cluster.cluster_id)

            # Fetch metrics from budmetrics and event counts from budmetrics in parallel
            events_endpoint = (
                f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_metrics_app_id}/"
                f"method/cluster-metrics/{db_cluster.cluster_id}/node-events-count"
            )

            async with aiohttp.ClientSession() as http_session:
                # Fetch metrics and events in parallel
                metrics_task = http_session.get(metrics_endpoint)
                events_task = http_session.get(events_endpoint)

                async with metrics_task as metrics_resp, events_task as events_resp:
                    # Handle metrics response
                    if metrics_resp.status != 200:
                        error_data = await metrics_resp.json()
                        logger.error(f"Failed to get node metrics from budmetrics: {error_data}")
                        raise ClientException(
                            f"Failed to get node metrics: {error_data.get('detail', 'Unknown error')}"
                        )

                    metrics_response = await metrics_resp.json()

                    # Handle events response (non-blocking, log error but continue)
                    events_by_hostname = {}
                    if events_resp.status == 200:
                        events_response = await events_resp.json()
                        # budmetrics returns events_count dict
                        events_by_hostname = events_response.get("events_count", {})
                    else:
                        logger.warning(f"Failed to get event counts from budmetrics: status {events_resp.status}")

            # Helper function to extract system info from kernel_info
            def extract_system_info(node: dict) -> dict:
                """Extract system info from budcluster node kernel_info."""
                kernel_info = node.get("kernel_info", {})
                return {
                    "os": kernel_info.get("os_release", kernel_info.get("os", "N/A")),
                    "kernel": kernel_info.get("kernel_version", "N/A"),
                    "architecture": kernel_info.get("architecture", "N/A"),
                }

            # Helper function to extract GPU count from hardware_info
            def extract_gpu_count(devices: list) -> int:
                """Extract total GPU count from hardware_info devices list."""
                gpu_count = 0
                for device in devices:
                    # Check if device is a GPU (has 'vendor' field with GPU vendors)
                    vendor = device.get("vendor", "").lower()
                    if vendor in ["nvidia", "amd", "intel"] and "raw_name" in device:
                        # Check if it's actually a GPU (not CPU/HPU)
                        raw_name = device.get("raw_name", "").lower()
                        if any(
                            gpu_indicator in raw_name
                            for gpu_indicator in ["gpu", "geforce", "tesla", "rtx", "gtx", "radeon", "mi250", "mi300"]
                        ):
                            gpu_count += device.get("count", 1)
                return gpu_count

            # Create node mapping from budcluster data
            # Use IP-based and hostname-based matching for flexibility
            budcluster_nodes = nodes_data.get("nodes", [])

            # Create both IP-to-node-info and hostname-to-node-info mappings
            node_info_by_ip = {}
            node_info_by_hostname = {}
            nodes_without_ip = []

            for node in budcluster_nodes:
                node_info = {
                    "id": node["id"],
                    "hostname": node["name"],
                    "devices": node["hardware_info"],
                    "status": "Ready" if node.get("status", False) else "NotReady",
                    "system_info": extract_system_info(node),
                    "gpu_count": extract_gpu_count(node["hardware_info"]),
                }

                # Map by hostname (always available)
                node_info_by_hostname[node["name"]] = node_info

                internal_ip = node.get("internal_ip")
                if internal_ip:
                    node_info_by_ip[internal_ip] = node_info
                else:
                    # Track nodes without IP for logging
                    nodes_without_ip.append(node["name"])

            # Log warning if some nodes don't have internal_ip (backwards compatibility)
            if nodes_without_ip:
                logger.warning(
                    f"Nodes without internal_ip in cluster {db_cluster.cluster_id}: {nodes_without_ip}. "
                    "Metrics may not be associated correctly. Please refresh node info."
                )

            # Transform metrics data into the expected format
            nodes_status = {"nodes": {}}

            metrics_nodes = metrics_response.get("nodes", [])

            # Match metrics to budcluster nodes using IP or hostname lookup
            # node_name from ClickHouse can be either IP (legacy) or hostname (with node enrichment)
            for node_metric in metrics_nodes:
                node_name = node_metric["node_name"]  # Can be IP or hostname from ClickHouse

                # Try to get corresponding budcluster node info by IP first, then by hostname
                node_info = node_info_by_ip.get(node_name) or node_info_by_hostname.get(node_name)

                if not node_info:
                    # Fallback to defaults if no match found
                    logger.debug(f"No node info found for {node_name}, using defaults")
                    node_info = {
                        "id": "",
                        "hostname": node_name,
                        "devices": [],
                        "status": "Unknown",
                        "system_info": {"os": "N/A", "kernel": "N/A", "architecture": "N/A"},
                        "gpu_count": 0,
                    }

                # Get network bandwidth time series from budmetrics
                network_bandwidth_time_series = node_metric.get("network_bandwidth_time_series", [])

                # If no time series data, create a fallback single point with average values
                if not network_bandwidth_time_series:
                    network_receive_bps = node_metric.get("network_receive_bytes_per_sec", 0)
                    network_transmit_bps = node_metric.get("network_transmit_bytes_per_sec", 0)
                    total_bandwidth_bytes_per_sec = network_receive_bps + network_transmit_bps
                    total_bandwidth_mbps = round((total_bandwidth_bytes_per_sec * 8) / 1_000_000, 2)

                    network_bandwidth_time_series = [
                        {"timestamp": int(datetime.now(timezone.utc).timestamp()), "mbps": total_bandwidth_mbps}
                    ]

                # Use IP as the key (current API contract, matches frontend expectation)
                # Display the actual hostname from budcluster when available
                node_response = {
                    "hostname": node_info["hostname"],  # Actual Kubernetes hostname
                    "status": node_info["status"],  # "Ready" or "NotReady"
                    "system_info": node_info["system_info"],  # Extracted from kernel_info
                    "pods": {
                        "current": 0,  # Not available from ClickHouse metrics yet
                        "max": 0,
                    },
                    "cpu": {
                        "current": round(node_metric["cpu_usage_percent"], 2),
                        "capacity": node_metric["cpu_cores"],
                    },
                    "memory": {
                        "current": round(node_metric["memory_used_gb"], 2),
                        "capacity": round(node_metric["memory_total_gb"], 2),
                    },
                    "network": {"bandwidth": network_bandwidth_time_series},
                    "events_count": events_by_hostname.get(node_info["hostname"], 0),
                    "capacity": {
                        "cpu": str(node_metric["cpu_cores"]),
                        "memory": f"{int(node_metric['memory_total_gb'])}Gi",
                        "disk": f"{int(node_metric['disk_total_gb'])}Gi",
                    },
                    "id": node_info["id"],
                    "devices": node_info["devices"],
                }

                # Add GPU field if node has GPUs
                # Use GPU data from budmetrics (DCGM-based utilization) if available
                # Falls back to budcluster's hardware_info for GPU count
                metrics_gpu_count = node_metric.get("gpu_count", 0)
                hardware_gpu_count = node_info.get("gpu_count", 0)
                gpu_count = metrics_gpu_count if metrics_gpu_count > 0 else hardware_gpu_count
                if gpu_count > 0:
                    # GPU utilization from budmetrics (DCGM_FI_PROF_GR_ENGINE_ACTIVE)
                    gpu_utilization = node_metric.get("gpu_utilization_percent", 0)
                    node_response["gpu"] = {
                        "current": round(gpu_utilization, 2),
                        "capacity": gpu_count,
                    }

                nodes_status["nodes"][node_name] = node_response

            return nodes_status

        except ClientException:
            raise
        except Exception as e:
            logger.exception(f"Failed to get node metrics: {e}")
            raise ClientException(f"Failed to get node metrics: {str(e)}")

    async def get_node_wise_events_by_hostname(self, cluster_id: UUID, node_hostname: str) -> Dict[str, Any]:
        """Get node-wise events for a cluster by hostname.

        Args:
            cluster_id: The ID of the cluster to get events for
            node_hostname: The hostname of the node to get events for

        Returns:
            Dict containing the node-wise events
        """
        db_cluster = await self.get_cluster_details(cluster_id)

        try:
            # Use budmetrics for node events (from ClickHouse)
            events_endpoint = (
                f"{app_settings.dapr_base_url}/v1.0/invoke"
                f"/{app_settings.bud_metrics_app_id}/method"
                f"/cluster-metrics/{db_cluster.cluster_id}/node-events/{node_hostname}"
            )

            async with aiohttp.ClientSession() as session, session.get(events_endpoint) as response:
                response_data = await response.json()

                logger.debug(f"Node-wise events response: {response_data}")

                if response.status != 200:
                    logger.error(f"Failed to get node-wise events: {response.status} {response_data}")
                    raise ClientException("Failed to get node-wise events")

                # Return events in expected format
                return {"events": response_data.get("events", [])}

        except Exception as e:
            raise ClientException(f"Failed to get node-wise events: {str(e)}")

    async def _perform_get_cluster_nodes_request(self, cluster_id: UUID) -> Dict:
        """Perform get cluster nodes request to bud_cluster app.

        Args:
            cluster_id: The ID of the cluster to update.
        """
        get_cluster_node_endpoint = f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_cluster_app_id}/method/cluster/{cluster_id}/nodes"

        try:
            logger.debug(f"Performing get cluster node request. endpoint: {get_cluster_node_endpoint}")
            async with aiohttp.ClientSession() as session, session.get(get_cluster_node_endpoint) as response:
                response_data = await response.json()
                if response.status != 200 or response_data.get("object") == "error":
                    logger.error(f"Failed to get cluster nodes: {response.status} {response_data}")
                    raise ClientException(
                        "Failed to get cluster nodes", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )

                logger.debug("Successfully fetched cluster nodes")
                return response_data["param"]
        except Exception as e:
            logger.exception(f"Failed to send get cluster nodes request: {e}")
            raise ClientException(
                "Failed to get cluster nodes", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            ) from e

    async def get_recommended_clusters(self, workflow_id: UUID) -> List[RecommendedCluster]:
        """Get recommended clusters for a workflow.

        Args:
            workflow_id: The ID of the workflow to get recommended clusters for

        Returns:
            List of recommended clusters
        """
        # From workflow id get simulator_id and deploy_config
        await WorkflowDataManager(self.session).retrieve_by_fields(WorkflowModel, {"id": workflow_id})

        # Get all workflow steps according with ascending order of step number
        db_workflow_steps = await WorkflowStepDataManager(self.session).get_all_workflow_steps(
            {"workflow_id": workflow_id}
        )

        # Define the keys required for model deployment
        keys_of_interest = [
            "deploy_config",
            "simulator_id",
            "model_id",
        ]

        # from workflow steps extract necessary information
        required_data = {}
        for db_workflow_step in db_workflow_steps:
            for key in keys_of_interest:
                if key in db_workflow_step.data:
                    required_data[key] = db_workflow_step.data[key]

        # Check if required data is present
        if (
            "deploy_config" not in required_data
            or "simulator_id" not in required_data
            or "model_id" not in required_data
        ):
            logger.error("Unable to find required data from workflow steps")
            raise ClientException("Unable to find required data from workflow steps")

        # Get model details
        db_model = await ModelDataManager(self.session).retrieve_by_fields(
            Model, {"id": required_data["model_id"], "status": ModelStatusEnum.ACTIVE}
        )

        # Validate deploy_config
        try:
            deploy_config = DeploymentTemplateCreate(**required_data["deploy_config"])
        except ValidationError as e:
            logger.error("Invalid deployment configuration: %s", e)
            raise ClientException("Invalid deployment configuration found")

        # Validate simulator_id
        try:
            simulator_id = UUID(required_data["simulator_id"])
            if not isinstance(simulator_id, UUID):
                raise ClientException("Invalid simulator details found")
        except ValueError as e:
            logger.error("Invalid simulator ID: %s", e)
            raise ClientException("Invalid simulator details found")

        # Get recommended clusters from simulator app
        recommended_clusters = await self._perform_get_recommended_clusters_request(simulator_id)

        # Get all active clusters by recommended cluster ids
        db_clusters, _ = await ClusterDataManager(self.session).get_available_clusters_by_cluster_ids(
            [UUID(item["cluster_id"]) for item in recommended_clusters["items"]]
        )

        # Parse recommended clusters response
        return await self._parse_recommended_clusters_response(
            db_clusters, recommended_clusters, deploy_config, db_model
        )

    async def _perform_get_recommended_clusters_request(self, simulator_id: UUID) -> Dict:
        """Perform get recommended clusters request to simulator app.

        Args:
            simulator_id: The ID of the simulator to get recommended clusters for
        """
        get_recommended_clusters_endpoint = f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_simulator_app_id}/method/simulator/recommendations"
        query_params = {
            "workflow_id": str(simulator_id),
            "limit": 20,
        }

        try:
            logger.debug(f"Performing get recommended clusters request. endpoint: {get_recommended_clusters_endpoint}")
            async with aiohttp.ClientSession() as session:
                async with session.get(get_recommended_clusters_endpoint, params=query_params) as response:
                    response_data = await response.json()
                    if response.status != 200 or response_data.get("object") == "error":
                        logger.error(f"Failed to get recommended clusters: {response.status} {response_data}")
                        raise ClientException(
                            "Failed to get recommended clusters", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                        )

                    logger.debug("Successfully fetched recommended clusters")
                    return response_data
        except Exception as e:
            logger.exception(f"Failed to send get recommended clusters request: {e}")
            raise ClientException(
                "Failed to get recommended clusters", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            ) from e

    async def _parse_recommended_clusters_response(
        self,
        db_clusters: List[ClusterModel],
        recommended_clusters: Dict,
        deploy_config: DeploymentTemplateCreate,
        db_model: Model,
    ) -> List[RecommendedCluster]:
        """Parse recommended clusters response.

        Args:
            db_clusters: List of active clusters
            recommended_clusters: Recommended clusters
        """
        # Create a mapper for recommended cluster details with cluster id
        recommended_cluster_mapper = {(item["cluster_id"]): item for item in recommended_clusters["items"]}

        # Create a mapper for cluster details with cluster id
        db_cluster_mapper = {(str(db_cluster.cluster_id)): db_cluster for db_cluster in db_clusters}

        # Create a list to store recommended cluster data
        data = []

        # Iterate over all recommended clusters
        for recommended_cluster_id, recommended_cluster_data in recommended_cluster_mapper.items():
            if recommended_cluster_id not in db_cluster_mapper:
                logger.info(f"BudSimulator cluster id {recommended_cluster_id} not found in database")
                continue

            db_cluster = db_cluster_mapper[recommended_cluster_id]

            # calculate replicas
            total_replicas = recommended_cluster_data["metrics"]["replica"]

            # calculate concurrency
            concurrency_data = {
                "label": await get_range_label(
                    recommended_cluster_data["metrics"]["concurrency"], deploy_config.concurrent_requests
                ),
                "value": recommended_cluster_data["metrics"]["concurrency"],
            }

            if db_model.provider_type == ModelProviderTypeEnum.CLOUD_MODEL:
                ttft_data = None
                per_session_tokens_per_sec_data = None
                over_all_throughput_data = None
                e2e_latency_data = None
            else:
                # calculate ttft - only calculate label if target is set
                ttft_value = recommended_cluster_data["metrics"]["ttft"]
                if deploy_config.ttft is not None:
                    ttft_data = {
                        "label": await get_range_label(ttft_value, deploy_config.ttft, higher_is_better=False),
                        "value": ttft_value,
                    }
                else:
                    ttft_data = {"label": None, "value": ttft_value}

                # calculate per_session_tokens_per_sec - only calculate label if target is set
                throughput_value = recommended_cluster_data["metrics"]["throughput_per_user"]
                if deploy_config.per_session_tokens_per_sec is not None:
                    per_session_tokens_per_sec_data = {
                        "label": await get_range_label(throughput_value, deploy_config.per_session_tokens_per_sec),
                        "value": throughput_value,
                    }
                else:
                    per_session_tokens_per_sec_data = {"label": None, "value": throughput_value}

                # calculate overall throughput
                over_all_throughput = (
                    recommended_cluster_data["metrics"]["concurrency"]
                    * recommended_cluster_data["metrics"]["throughput_per_user"]
                )
                over_all_throughput_data = {
                    "label": per_session_tokens_per_sec_data[
                        "label"
                    ],  # Since overall throughput is a product of concurrency and throughput_per_user, the label is the same as throughput_per_user
                    "value": over_all_throughput,
                }

                # calculate e2e_latency - only calculate label if target is set
                e2e_latency_value = recommended_cluster_data["metrics"]["e2e_latency"]
                if deploy_config.e2e_latency is not None:
                    e2e_latency_data = {
                        "label": await get_range_label(
                            e2e_latency_value, deploy_config.e2e_latency, higher_is_better=False
                        ),
                        "value": e2e_latency_value,
                    }
                else:
                    e2e_latency_data = {"label": None, "value": e2e_latency_value}

            # cost per million tokens
            cost_per_million_tokens = recommended_cluster_data["metrics"]["cost_per_million_tokens"]

            # Resource details
            resource_details = []
            if db_cluster.cpu_count > 0:
                resource_details.append(
                    {
                        "type": "CPU",
                        "available": db_cluster.cpu_available_workers,
                        "total": db_cluster.cpu_total_workers,
                    }
                )
            if db_cluster.gpu_count > 0:
                resource_details.append(
                    {
                        "type": "GPU",
                        "available": db_cluster.gpu_available_workers,
                        "total": db_cluster.gpu_total_workers,
                    }
                )
            if db_cluster.hpu_count > 0:
                resource_details.append(
                    {
                        "type": "HPU",
                        "available": db_cluster.hpu_available_workers,
                        "total": db_cluster.hpu_total_workers,
                    }
                )

            # Total resources
            total_resources = sum([item["total"] for item in resource_details])

            # Resources used
            resources_used = total_resources - sum([item["available"] for item in resource_details])

            # device types
            device_types = recommended_cluster_data["metrics"].get("device_types", [])

            # append recommended cluster data to the response
            data.append(
                RecommendedCluster(
                    id=db_cluster.id,
                    cluster_id=db_cluster.cluster_id,
                    name=db_cluster.name,
                    cost_per_token=cost_per_million_tokens,
                    total_resources=total_resources,
                    resources_used=resources_used,
                    resource_details=resource_details,
                    required_devices=device_types,
                    benchmarks=RecommendedClusterData(
                        replicas=total_replicas,
                        ttft=ttft_data,
                        per_session_tokens_per_sec=per_session_tokens_per_sec_data,
                        e2e_latency=e2e_latency_data,
                        over_all_throughput=over_all_throughput_data,
                        concurrency=concurrency_data,
                    ),
                    # Add parser metadata from simulator
                    tool_calling_parser_type=recommended_cluster_data.get("tool_calling_parser_type"),
                    reasoning_parser_type=recommended_cluster_data.get("reasoning_parser_type"),
                    chat_template=recommended_cluster_data.get("chat_template"),
                    # Add engine capability flags from simulator
                    supports_lora=recommended_cluster_data.get("supports_lora"),
                    supports_pipeline_parallelism=recommended_cluster_data.get("supports_pipeline_parallelism"),
                )
            )

        return data

    # Cluster Settings Methods
    async def get_cluster_settings(self, cluster_id: UUID) -> ClusterSettingsResponse | None:
        """Get cluster settings by cluster ID."""
        cluster_settings_manager = ClusterSettingsDataManager(self.session)
        db_settings = await cluster_settings_manager.get_cluster_settings(cluster_id)

        if not db_settings:
            return None

        return ClusterSettingsResponse.model_validate(db_settings)

    async def create_cluster_settings(
        self,
        cluster_id: UUID,
        created_by: UUID,
        default_storage_class: str | None = None,
        default_access_mode: str | None = None,
    ) -> ClusterSettingsResponse:
        """Create cluster settings."""
        # First check if cluster exists
        cluster_manager = ClusterDataManager(self.session)
        db_cluster = await cluster_manager.retrieve_by_fields(ClusterModel, fields={"id": cluster_id}, missing_ok=True)

        if not db_cluster:
            raise ClientException("Cluster not found", status_code=status.HTTP_404_NOT_FOUND)

        resolved_access_mode = await self._resolve_default_access_mode(
            cluster_id=cluster_id,
            default_storage_class=default_storage_class,
            requested_access_mode=default_access_mode,
        )

        cluster_settings_manager = ClusterSettingsDataManager(self.session)
        db_settings = await cluster_settings_manager.create_cluster_settings(
            cluster_id=cluster_id,
            created_by=created_by,
            default_storage_class=default_storage_class,
            default_access_mode=resolved_access_mode,
        )

        return ClusterSettingsResponse.model_validate(db_settings)

    async def update_cluster_settings(
        self,
        cluster_id: UUID,
        default_storage_class: str | None = None,
        default_access_mode: str | None = None,
    ) -> ClusterSettingsResponse:
        """Update cluster settings."""
        resolved_access_mode = await self._resolve_default_access_mode(
            cluster_id=cluster_id,
            default_storage_class=default_storage_class,
            requested_access_mode=default_access_mode,
        )

        cluster_settings_manager = ClusterSettingsDataManager(self.session)
        db_settings = await cluster_settings_manager.update_cluster_settings(
            cluster_id=cluster_id,
            default_storage_class=default_storage_class,
            default_access_mode=resolved_access_mode,
        )

        if not db_settings:
            raise ClientException("Cluster settings not found", status_code=status.HTTP_404_NOT_FOUND)

        return ClusterSettingsResponse.model_validate(db_settings)

    async def upsert_cluster_settings(
        self,
        cluster_id: UUID,
        created_by: UUID,
        default_storage_class: str | None = None,
        default_access_mode: str | None = None,
    ) -> ClusterSettingsResponse:
        """Create or update cluster settings."""
        resolved_access_mode = await self._resolve_default_access_mode(
            cluster_id=cluster_id,
            default_storage_class=default_storage_class,
            requested_access_mode=default_access_mode,
        )

        # First check if cluster exists
        cluster_manager = ClusterDataManager(self.session)
        db_cluster = await cluster_manager.retrieve_by_fields(ClusterModel, fields={"id": cluster_id}, missing_ok=True)

        if not db_cluster:
            raise ClientException("Cluster not found", status_code=status.HTTP_404_NOT_FOUND)

        cluster_settings_manager = ClusterSettingsDataManager(self.session)
        db_settings = await cluster_settings_manager.upsert_cluster_settings(
            cluster_id=cluster_id,
            created_by=created_by,
            default_storage_class=default_storage_class,
            default_access_mode=resolved_access_mode,
        )

        return ClusterSettingsResponse.model_validate(db_settings)

    async def delete_cluster_settings(self, cluster_id: UUID) -> bool:
        """Delete cluster settings."""
        cluster_settings_manager = ClusterSettingsDataManager(self.session)
        return await cluster_settings_manager.delete_cluster_settings(cluster_id)

    async def get_cluster_storage_classes(self, cluster_id: UUID) -> Dict[str, Any]:
        """Get storage classes from a cluster via budcluster service.

        Args:
            cluster_id: The ID of the cluster to get storage classes from.

        Returns:
            Dict containing storage classes data.

        Raises:
            ClientException: If the request fails or cluster is not found.
        """
        # First verify cluster exists
        cluster_manager = ClusterDataManager(self.session)
        db_cluster = await cluster_manager.retrieve_by_fields(ClusterModel, fields={"id": cluster_id}, missing_ok=True)

        if not db_cluster:
            raise ClientException("Cluster not found", status_code=status.HTTP_404_NOT_FOUND)

        # Make request to budcluster service
        get_storage_classes_endpoint = (
            f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_cluster_app_id}"
            f"/method/cluster/{db_cluster.cluster_id}/storage-classes"
        )

        try:
            logger.debug(f"Fetching storage classes from budcluster: {get_storage_classes_endpoint}")
            async with aiohttp.ClientSession() as session:
                async with session.get(get_storage_classes_endpoint) as response:
                    response_data = await response.json()

                    if response.status != 200 or response_data.get("object") == "error":
                        error_message = response_data.get("message", "Failed to fetch storage classes")
                        logger.error(f"Failed to fetch storage classes from budcluster: {error_message}")
                        raise ClientException(error_message, status_code=response.status)

                    logger.debug("Successfully fetched storage classes from budcluster")
                    return response_data
        except ClientException:
            raise
        except Exception as e:
            logger.error(f"Failed to make request to budcluster service for storage classes: {e}")
            raise ClientException(
                "Unable to fetch storage classes from cluster", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            ) from e

    async def _resolve_default_access_mode(
        self,
        cluster_id: UUID,
        default_storage_class: str | None,
        requested_access_mode: str | None,
    ) -> str | None:
        """Determine which access mode should be stored for a cluster.

        Preference order:
        1. Explicit value provided by the caller.
        2. Recommended access mode returned by budcluster for the selected storage class.
        3. Fallback to ``ReadWriteOnce`` when nothing else is available.
        """
        if requested_access_mode:
            return requested_access_mode

        if not default_storage_class:
            # No storage class means we can't infer a specific access mode
            return None

        try:
            storage_class_payload = await self.get_cluster_storage_classes(cluster_id)
        except ClientException as exc:
            logger.warning("Unable to resolve access mode from cluster %s: %s", cluster_id, exc)
            return None
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.warning("Unexpected error resolving access mode for cluster %s: %s", cluster_id, exc)
            return None

        storage_classes: list[dict[str, Any]] = []
        if isinstance(storage_class_payload, dict):
            storage_classes = storage_class_payload.get("storage_classes") or storage_class_payload.get(
                "param", {}
            ).get("storage_classes", [])

        for sc in storage_classes:
            if sc.get("name") == default_storage_class:
                recommended = sc.get("recommended_access_mode")
                if recommended:
                    return recommended

        # If we made it this far we could not determine anything better
        return None
