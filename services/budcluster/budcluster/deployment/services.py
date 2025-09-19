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
import math
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

import requests
from budmicroframe.commons.constants import NotificationCategory, NotificationType, WorkflowStatus
from budmicroframe.commons.logging import get_logger
from budmicroframe.commons.schemas import (
    ErrorResponse,
    NotificationContent,
    NotificationPayload,
    NotificationRequest,
    SuccessResponse,
    WorkflowMetadataResponse,
)
from budmicroframe.shared.dapr_service import DaprService
from budmicroframe.shared.dapr_workflow import DaprWorkflow

# # from ..commons.database import SessionLocal
from budmicroframe.shared.psql_service import DBSession
from fastapi import BackgroundTasks

from ..cluster_ops.crud import ClusterDataManager
from ..cluster_ops.models import Cluster as ClusterModel
from ..commons.base_crud import SessionMixin
from ..commons.config import app_settings
from ..commons.utils import (
    get_workflow_data_from_statestore,
    save_workflow_status_in_statestore,
)
from .crud import WorkerInfoDataManager
from .handler import DeploymentHandler
from .models import WorkerInfo as WorkerInfoModel
from .schemas import (
    AdapterRequest,
    DeleteDeploymentRequest,
    DeleteWorkerRequest,
    DeploymentCreateRequest,
    DeployQuantizationRequest,
    UpdateDeploymentStatusRequest,
    WorkerData,
    WorkerInfo,
    WorkerStatusEnum,
)


logger = get_logger(__name__)


class DeploymentOpsService:
    @classmethod
    async def update_deployment_status(
        cls, cluster_id: UUID, deployment_name: str, cloud_model: bool = False, workflow_id: str = None
    ):
        """Update the status of a deployment."""
        # get deployment from budapp
        with DBSession() as session:
            db_cluster = await ClusterDataManager(session).retrieve_cluster_by_fields(
                {"id": cluster_id}, missing_ok=True
            )
            if not db_cluster:
                return
            # if deployment exists, get deployment status
        # if deployment does not exist, return None
        status = DeploymentHandler(config=db_cluster.config_file_dict).get_deployment_status(
            deployment_name, db_cluster.ingress_url, cloud_model=cloud_model
        )
        status["deployment_name"] = deployment_name
        # if deployment status is not same as current status
        # send deployment status to budapp to update in db
        event_name = "deployment-status"
        notification_request = NotificationRequest(
            notification_type=NotificationType.EVENT,
            name=event_name,
            payload=NotificationPayload(
                category=NotificationCategory.INTERNAL,
                type=event_name,
                event="results",
                workflow_id=workflow_id,
                content=NotificationContent(
                    result=status,
                ),
            ),
        )
        with DaprService() as dapr_service:
            await dapr_service.publish_notification(
                notification=notification_request,
                target_topic_name="budAppMessages",
            )

    @classmethod
    def cancel_deployment(cls, workflow_id: UUID) -> Union[SuccessResponse, ErrorResponse]:
        """Cancel a deployment."""
        workflow_status_dict = get_workflow_data_from_statestore(str(workflow_id))
        if not workflow_status_dict:
            return ErrorResponse(message="Workflow not found")
        # cleanup resources create deployment workflow
        if "namespace" in workflow_status_dict:
            from .handler import DeploymentHandler

            deployment_handler = DeploymentHandler(config=workflow_status_dict["cluster_config_dict"])
            deployment_handler.delete(workflow_status_dict["namespace"])
        return SuccessResponse(message="Create deployment resources cleaned up")

    @classmethod
    async def trigger_update_deployment_status(cls, deployment_name: str, cluster_id: UUID, cloud_model: bool = False):
        """Trigger the update deployment status workflow."""
        from .workflows import UpdateDeploymentStatusWorkflow

        update_deployment_request = UpdateDeploymentStatusRequest(
            deployment_name=deployment_name,
            cluster_id=cluster_id,
            cloud_model=cloud_model,
        )
        response = await UpdateDeploymentStatusWorkflow().__call__(update_deployment_request.model_dump_json())
        return response


class DeploymentService(SessionMixin):
    async def _get_cluster(self, cluster_id: UUID, missing_ok: bool = False) -> ClusterModel:
        """Get cluster details from db."""
        return await ClusterDataManager(self.session).retrieve_cluster_by_fields(
            {"id": cluster_id}, missing_ok=missing_ok
        )

    def _is_cloud_deployment(self, deployment: DeploymentCreateRequest) -> bool:
        """Determine if deployment is for cloud model based on provider and credential_id.

        Args:
            deployment: The deployment request object

        Returns:
            bool: True if this is a cloud deployment, False for local deployment
        """
        # Cloud deployment indicators:
        # 1. Provider is explicitly a cloud provider (not HUGGING_FACE, URL, DISK)
        # 2. Credential ID is required and provided for cloud models

        cloud_providers = {"OPENAI", "ANTHROPIC", "AZURE_OPENAI", "BEDROCK", "COHERE", "GROQ"}
        local_providers = {"HUGGING_FACE", "URL", "DISK"}

        if deployment.provider:
            provider_upper = deployment.provider.upper()
            if provider_upper in cloud_providers:
                logger.debug(f"Detected cloud provider: {deployment.provider}")
                return True
            elif provider_upper in local_providers:
                logger.debug(f"Detected local provider: {deployment.provider}")
                return False

        # Fallback: If credential_id is provided and required, it's likely a cloud deployment
        # But for local models (especially HuggingFace), credential_id can be None
        if deployment.credential_id is not None:
            logger.debug("Credential ID provided - checking if cloud deployment")
            # Additional validation could be added here to check if credential is for cloud service
            return deployment.provider not in local_providers if deployment.provider else True

        logger.debug("No cloud provider detected and no credential_id - treating as local deployment")
        return False

    async def create_deployment(
        self, deployment: DeploymentCreateRequest
    ) -> Union[WorkflowMetadataResponse, ErrorResponse]:
        """Create a new deployment.

        Args:
            deployment (DeploymentCreateRequest): The request object contains cluster_id and simulator_id.

        Returns:
            DeploymentResponse: A response object containing the workflow id, steps and deployment info.
        """
        # check if cluster is available
        # fetch cluster details from db
        db_cluster = await self._get_cluster(deployment.cluster_id, missing_ok=True)
        if db_cluster is None:
            logger.error(f"Cluster not found for id: {deployment.cluster_id}")
            raise Exception("Cluster not found")

        from .workflows import CreateDeploymentWorkflow, CreateCloudDeploymentWorkflow  # noqa: I001

        # Determine deployment type based on provider and credential_id
        is_cloud_deployment = self._is_cloud_deployment(deployment)

        logger.info(
            f"Deployment type detection - Provider: {deployment.provider}, "
            f"Credential ID: {deployment.credential_id}, "
            f"Cloud deployment: {is_cloud_deployment}"
        )

        if is_cloud_deployment:
            logger.info("Routing to cloud deployment workflow")
            response = await CreateCloudDeploymentWorkflow().__call__(deployment)
        else:
            logger.info("Routing to local deployment workflow")
            response = await CreateDeploymentWorkflow().__call__(deployment)

        return response

    def cancel_deployment(
        self, workflow_id: UUID, background_tasks: BackgroundTasks
    ) -> Union[SuccessResponse, ErrorResponse]:
        """Cancel a deployment."""
        stop_workflow_response = asyncio.run(DaprWorkflow().stop_workflow(str(workflow_id)))
        if stop_workflow_response.code == 200:
            save_workflow_status_in_statestore(str(workflow_id), WorkflowStatus.TERMINATED.value)
            background_tasks.add_task(DeploymentOpsService.cancel_deployment, workflow_id)
        return stop_workflow_response

    async def delete_deployment(
        self, delete_deployment_request: DeleteDeploymentRequest
    ) -> Union[WorkflowMetadataResponse, ErrorResponse]:
        """Delete a deployment."""
        logger.info(f"Deleting deployment with namespace: {delete_deployment_request.namespace}")

        from .workflows import DeleteDeploymentWorkflow

        try:
            response = await DeleteDeploymentWorkflow().__call__(delete_deployment_request)
        except Exception as e:
            logger.error(f"Error deleting deployment: {e}")
            # Return ErrorResponse instead of raising it since it's not an Exception
            return ErrorResponse(message=str(e))
        return response

    @staticmethod
    def get_deployment_eta(
        current_step: str, model_size: Optional[int] = None, device_type: Optional[str] = None, step_time: int = None
    ) -> dict:
        """Get deployment eta with model size and device type considerations."""
        # Define base times for each step in minutes
        step_times = {
            "verify_cluster_connection": 0.5,
            "transfer_model_to_cluster": 5,
            "deploy_to_engine": 1,
            "verify_deployment_status": 5,
            "run_performance_benchmark": 1,
        }

        # Define the order of steps
        step_order = [
            "verify_cluster_connection",
            "transfer_model_to_cluster",
            "deploy_to_engine",
            "verify_deployment_status",
            "run_performance_benchmark",
        ]

        # Apply model size scaling if provided
        if model_size is not None:
            # Convert model size if it's in compact format (e.g., 7 for 7B, 1760 for 1.76B)
            # Assume if model_size < 100000, it's in billions format
            model_size_in_params = model_size * 1000000000 if model_size < 100000 else model_size

            # Adjust transfer time based on model size
            if model_size_in_params > 7000000000:  # 7B+ parameters
                transfer_scale_factor = 2.0
                deploy_scale_factor = 1.5
            elif model_size_in_params > 3000000000:  # 3B+ parameters
                transfer_scale_factor = 1.5
                deploy_scale_factor = 1.2
            else:
                transfer_scale_factor = 1.0
                deploy_scale_factor = 1.0

            step_times["transfer_model_to_cluster"] *= transfer_scale_factor
            step_times["deploy_to_engine"] *= deploy_scale_factor
            step_times["verify_deployment_status"] *= deploy_scale_factor

        # Apply device type scaling if provided
        if device_type is not None:
            device_type_lower = device_type.lower()
            if device_type_lower == "cpu":
                # CPU deployments take longer
                device_scale_factor = 1.5
                if model_size is not None:
                    # Even longer for larger models on CPU
                    if model_size_in_params > 7000000000:  # 7B+ parameters
                        device_scale_factor = 2.5
                    elif model_size_in_params > 3000000000:  # 3B+ parameters
                        device_scale_factor = 2.0
            elif device_type_lower in ["cuda", "gpu"]:
                # GPU deployments are faster
                device_scale_factor = 0.8
            else:
                device_scale_factor = 1.0

            # Apply device scaling to deployment and verification steps
            step_times["deploy_to_engine"] *= device_scale_factor
            step_times["verify_deployment_status"] *= device_scale_factor
            step_times["run_performance_benchmark"] *= device_scale_factor

        if step_time is not None:
            step_times[current_step] = step_time

        # Calculate total time for current and future steps
        total_time = 0
        current_step_index = step_order.index(current_step) if current_step in step_order else 0

        for i in range(current_step_index, len(step_order)):
            step = step_order[i]
            total_time += step_times.get(step, 10)  # Default 10 minutes for unknown steps

        return math.ceil(total_time)

    @staticmethod
    def publish_eta(
        notification_req: dict,
        deployment_request_json: dict,
        workflow_id: str,
        current_step: str,
        model_size: Optional[int] = None,
        device_type: Optional[str] = None,
        step_time: int = None,
    ):
        """Publish estimated time to completion notification with model size and device type considerations."""
        # Extract model_size from request if not explicitly provided
        if model_size is None:
            if hasattr(deployment_request_json, "model_size"):
                model_size = deployment_request_json.model_size
            elif isinstance(deployment_request_json, dict) and "model_size" in deployment_request_json:
                model_size = deployment_request_json.get("model_size")

        # Try to extract device_type from simulator_config if not provided
        if device_type is None:
            simulator_config = None
            if hasattr(deployment_request_json, "simulator_config"):
                simulator_config = deployment_request_json.simulator_config
            elif isinstance(deployment_request_json, dict) and "simulator_config" in deployment_request_json:
                simulator_config = deployment_request_json.get("simulator_config")

            if (
                simulator_config
                and len(simulator_config) > 0
                and isinstance(simulator_config[0], dict)
                and "devices" in simulator_config[0]
            ):
                # Get device type from first simulator config
                devices = simulator_config[0].get("devices", [])
                if devices and len(devices) > 0 and isinstance(devices[0], dict):
                    device_type = devices[0].get("type", None)

        eta = DeploymentService.get_deployment_eta(current_step, model_size, device_type, step_time)
        notification_req.payload.event = "eta"
        notification_req.payload.content = NotificationContent(
            title="Estimated time to completion",
            message=f"{eta}",
            status=WorkflowStatus.RUNNING,
        )
        # Extract source_topic and source for notification
        if hasattr(deployment_request_json, "source_topic"):
            source_topic = deployment_request_json.source_topic
            source = deployment_request_json.source
        elif isinstance(deployment_request_json, dict):
            source_topic = deployment_request_json.get("source_topic")
            source = deployment_request_json.get("source")
        else:
            source_topic = None
            source = None

        DaprWorkflow().publish_notification(
            workflow_id=workflow_id,
            notification=notification_req,
            target_topic_name=source_topic,
            target_name=source,
        )


class WorkerInfoService(SessionMixin):
    async def parse_worker_info(self, worker_info: List[WorkerInfoModel]) -> List[WorkerInfo]:
        """Parse worker info."""
        workers = []
        for worker in worker_info:
            workers.append(WorkerInfo.model_validate(worker))
        return workers

    async def get_workers_info(
        self, filters_dict, cluster_id, namespace, refresh, offset, limit, order_by, search
    ) -> List[WorkerInfo]:
        """Get worker info."""
        filters_dict = filters_dict or {}
        filters_dict.update({"cluster_id": cluster_id, "namespace": namespace})
        logger.info(f"Services : filters_dict: {filters_dict}")
        if not refresh:
            result, count = await WorkerInfoDataManager(self.session).get_all_workers(
                filters_dict, offset, limit, order_by, search
            )
        else:
            raise Exception("Refresh is not supported yet")
        return await self.parse_worker_info(result), count

    async def add_worker_info(self, workers_info: List[WorkerData]) -> List[WorkerInfoModel]:
        """Add worker info."""
        return await WorkerInfoDataManager(self.session).add_worker_info(workers_info)

    async def get_worker_metrics(self, filters_dict, missing_ok: bool = False) -> Union[Dict[str, Any], None]:
        """Get worker metrics from Prometheus.

        Args:
            filters_dict: Dictionary containing filters to find the worker
            missing_ok: If True, return None if worker not found instead of raising error

        Returns:
            Dictionary containing memory usage and CPU metrics, or None if worker not found
        """
        try:
            # Get worker info from database
            db_worker = await WorkerInfoDataManager(self.session).retrieve_workers_by_fields(
                filters_dict, missing_ok=missing_ok
            )
            if not db_worker:
                return None

            # Fetch metrics from Prometheus in parallel using asyncio.gather
            memory_usage, cpu_metrics = await asyncio.gather(
                self._get_memory_usage(db_worker), self._get_cpu_metrics(db_worker)
            )

            return {
                "memory_usage": memory_usage,
                "cpu_metrics": cpu_metrics,
            }
        except Exception as e:
            logger.error(f"Error fetching worker metrics: {e}")
            return None

    async def _get_memory_usage(self, db_worker: WorkerInfoModel) -> Union[float, None]:
        """Get worker memory usage from Prometheus."""
        try:
            query = f"""
            (container_memory_usage_bytes{{
                cluster="{db_worker.cluster_id}",
                namespace="{db_worker.namespace}",
                pod="{db_worker.name}",
                service="prometheus-stack-kube-prom-kubelet",
                container=""
            }} / (1024^3))
            """

            response = requests.get(f"{app_settings.prometheus_url}/api/v1/query", params={"query": query}, timeout=10)
            response.raise_for_status()
            data = response.json()

            if "data" in data and "result" in data["data"] and data["data"]["result"]:
                logger.debug(f"Memory data found in Prometheus for pod: {db_worker.name}")
                logger.debug(f"Memory data: {data['data']['result']}")

                return float(data["data"]["result"][0]["value"][1])

            logger.debug(f"No memory data found in Prometheus for pod: {db_worker.name}")
            return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching memory metrics: {e}")
            return None

    async def _get_cpu_metrics(self, db_worker: WorkerInfoModel) -> Union[Dict[int, float], None]:
        """Get worker CPU metrics from Prometheus."""
        try:
            query = f"""
            100 *
            avg_over_time(
              rate(container_cpu_usage_seconds_total{{
                pod="{db_worker.name}",
                namespace="{db_worker.namespace}",
                container!="POD"
              }}[1h])[1m:]
            )
            /
            on(pod, container, namespace)
            group_left()
            max by (pod, container, namespace) (
              kube_pod_container_resource_limits{{
                resource="cpu",
                namespace="{db_worker.namespace}"
              }}
            )
            """

            # Calculate time range
            end_time = int(time.time())
            end_time = end_time - (end_time % 3600)  # Round down to nearest hour
            start_time = end_time - (12 * 3600)  # 12 hours ago
            step = 3600  # 1 hour

            params = {"query": query, "start": start_time, "end": end_time, "step": step}
            logger.debug(f"Prometheus query params: {params}")
            response = requests.get(f"{app_settings.prometheus_url}/api/v1/query_range", params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if "data" in data and "result" in data["data"]:
                time_data = {}
                for result in data["data"]["result"]:
                    for timestamp, cpu_usage in result["values"]:
                        timestamp = int(timestamp)
                        cpu_usage = float(cpu_usage)
                        if timestamp not in time_data:
                            time_data[timestamp] = cpu_usage
                        else:
                            time_data[timestamp] = max(time_data[timestamp], cpu_usage)
                logger.debug(f"CPU data: {time_data}")
                return time_data

            logger.debug(f"No CPU data found in Prometheus for pod: {db_worker.name}")
            return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching CPU metrics: {e}")
            return None

    async def get_worker_logs(self, filters_dict, missing_ok: bool = False) -> Union[List[Dict[str, Any]], str, None]:
        """Get worker logs."""
        db_worker = await WorkerInfoDataManager(self.session).retrieve_workers_by_fields(
            filters_dict, missing_ok=missing_ok
        )

        from .handler import DeploymentHandler

        deployment_handler = DeploymentHandler(config=db_worker.cluster.config_file_dict)

        logs = await deployment_handler.get_pod_logs(db_worker.namespace, db_worker.name, db_worker.cluster.platform)
        logger.debug(f"::LOGS:: Logs: {logs}")
        return logs

    async def get_worker_detail(self, filters_dict, reload: bool = False, missing_ok: bool = False) -> WorkerInfoModel:
        """Get worker detail."""
        db_worker = await WorkerInfoDataManager(self.session).retrieve_workers_by_fields(
            filters_dict, missing_ok=missing_ok
        )
        if reload:
            from .handler import DeploymentHandler

            deployment_handler = DeploymentHandler(config=db_worker.cluster.config_file_dict)
            worker_data = await deployment_handler.get_pod_status(
                db_worker.namespace, db_worker.name, db_worker.cluster.platform
            )
            for field, value in worker_data.items():
                setattr(db_worker, field, value)
            db_worker.last_updated_datetime = datetime.now(timezone.utc)
            db_worker = await WorkerInfoDataManager(self.session).update_worker_info(db_worker)
        return db_worker

    async def delete_worker(self, delete_worker_request: DeleteWorkerRequest) -> Union[SuccessResponse, ErrorResponse]:
        """Delete a worker."""
        start_time = time.perf_counter()

        # Measure get_worker_detail
        t1 = time.perf_counter()
        db_worker = await self.get_worker_detail({"id": delete_worker_request.worker_id})
        t2 = time.perf_counter()
        logger.info(f"get_worker_detail took {t2 - t1:.3f} seconds")

        # Measure status update
        t1 = time.perf_counter()
        db_worker.status = WorkerStatusEnum.DELETING.value
        db_worker = await WorkerInfoDataManager(self.session).update_worker_info(db_worker)
        t2 = time.perf_counter()
        logger.info(f"update_worker_info took {t2 - t1:.3f} seconds")

        # Measure workflow execution
        t1 = time.perf_counter()
        from .workflows import DeleteWorkerWorkflow

        workflow_id = None
        notification_metadata = delete_worker_request.notification_metadata
        if notification_metadata:
            workflow_id = notification_metadata.workflow_id
        response = await DeleteWorkerWorkflow().__call__(delete_worker_request, workflow_id)
        t2 = time.perf_counter()
        logger.info(f"DeleteWorkerWorkflow execution took {t2 - t1:.3f} seconds")

        total_time = time.perf_counter() - start_time
        logger.info(f"Total delete_worker execution took {total_time:.3f} seconds")

        return response

    async def update_worker_info(
        self, worker_info_list: List[WorkerInfoModel], db_workers: List[WorkerInfoModel], cluster_id: UUID
    ) -> List[WorkerInfoModel]:
        """Update worker info."""
        workers_info = []

        db_worker_names = [worker.name for worker in db_workers]
        for worker in worker_info_list:
            db_worker = await self.get_worker_detail(
                {"name": worker.name, "cluster_id": worker.cluster_id}, missing_ok=True
            )
            if db_worker:
                db_worker.uptime = worker.uptime
                db_worker.deployment_status = worker.deployment_status
                db_worker.last_restart_datetime = worker.last_restart_datetime
                db_worker.last_updated_datetime = datetime.now(timezone.utc)
                db_worker = await WorkerInfoDataManager(self.session).update_worker_info(db_worker)
            else:
                db_worker_list = await WorkerInfoDataManager(self.session).add_worker_info([worker])
                db_worker = db_worker_list[0]
            if db_worker.name in db_worker_names:
                db_worker_names.remove(db_worker.name)
            workers_info.append(db_worker)
        if db_worker_names:
            for name in db_worker_names:
                db_worker = await self.get_worker_detail({"name": name, "cluster_id": cluster_id}, missing_ok=True)
                if db_worker:
                    await WorkerInfoDataManager(self.session).delete_one(db_worker)
        return workers_info


class QuantizationService(SessionMixin):
    async def deploy_quantization(
        self, deploy_quantization_request: DeployQuantizationRequest
    ) -> Union[WorkflowMetadataResponse, ErrorResponse]:
        """Deploy quantization."""
        from .quantization_workflows import DeployQuantizationWorkflow

        try:
            response = await DeployQuantizationWorkflow().__call__(deploy_quantization_request)
        except Exception as e:
            logger.error(f"Error deploying quantization: {e}")
            # Return ErrorResponse instead of raising it since it's not an Exception
            return ErrorResponse(message=str(e))
        return response

    @staticmethod
    def create_quantization_config(deploy_quantization_request: DeployQuantizationRequest) -> dict:
        """Create quantization config."""
        seed = 42
        quantization_config = {
            "base": {"seed": seed},
            "model": {
                "type": "Llama",
                "path": "/data/model-registry/" + deploy_quantization_request.model,
                "tokenizer_mode": "slow",
                "torch_dtype": "auto",
            },
            # "calib": {
            #     "name": "pileval",
            #     "download": True,
            #     # "path": deploy_quantization_request.calib_data_path,
            #     "n_samples": 128,
            #     "bs": -1,
            #     "seq_len": 512,
            #     "preproc": "pileval_awq",
            #     "seed": seed,
            # },
            "eval": {
                "eval_pos": ["pretrain", "fake_quant"],
                "name": "wikitext2",
                "download": True,
                # "path": deploy_quantization_request.eval_data_path,
                "seq_len": 2048,
                "bs": 1,
                "inference_per_block": False,
            },
            "quant": {
                "method": deploy_quantization_request.quantization_config.get("method", "RTN"),
                "weight": {
                    "bit": deploy_quantization_request.quantization_config["weight"]["bit"],
                    "symmetric": deploy_quantization_request.quantization_config["weight"]["symmetric"],
                    "granularity": deploy_quantization_request.quantization_config["weight"]["granularity"],
                    # "group_size": deploy_quantization_request.quantization_config['weight']['group_size'],
                },
                "act": {
                    "bit": deploy_quantization_request.quantization_config["activation"]["bit"],
                    "symmetric": deploy_quantization_request.quantization_config["activation"]["symmetric"],
                    "granularity": deploy_quantization_request.quantization_config["activation"]["granularity"],
                },
                "special": {
                    "trans": True,
                    # The options for "trans_version" include "v1" and "v2".
                    "trans_version": "v2",
                    "weight_clip": True,
                    "clip_sym": True,
                },
            },
            "save": {
                "save_trans": False,
                "save_fake": False,
                "save_vllm": True,
                "save_path": "/path/to/save/",
            },
        }

        return quantization_config

    @staticmethod
    def get_deployment_eta(current_step: str, model_size: int, device_type: str, step_time: int = None) -> dict:
        """Get deployment eta."""
        # Define default times for each step in minutes
        step_times = {
            "verify_cluster_connection": 0.5,
            "transfer_model_to_cluster": 5,
            "deploy_quantization_job": 2,
            "running_quantization": 5,
            "run_evaluation": 5,
        }

        # Define the order of steps
        step_order = [
            "verify_cluster_connection",
            "transfer_model_to_cluster",
            "deploy_quantization_job",
            "running_quantization",
            "run_evaluation",
        ]

        # Adjust times based on model size (larger models take longer)
        if model_size > 7000000000:  # 7B
            transfer_model_scale_factor = 2.0
        elif model_size > 3000000000:  # 3B
            transfer_model_scale_factor = 1.5
        else:
            transfer_model_scale_factor = 1.0

        # Add scale factor based on device type and model size
        device_scale_factor = 1.0
        if device_type == "cpu":
            device_scale_factor = 1.0
            # Increase scale factor for larger models on CPU
            if model_size > 7000000000:  # 7B
                device_scale_factor = 3.0
            elif model_size > 3000000000:  # 3B
                device_scale_factor = 2.0
        elif device_type == "cuda":
            device_scale_factor = 0.5
            # Even with GPU, larger models take more time
            if model_size > 7000000000:  # 7B
                device_scale_factor = 1.0
            elif model_size > 3000000000:  # 3B
                device_scale_factor = 0.75

        # Apply scaling
        step_times["transfer_model_to_cluster"] = int(
            step_times["transfer_model_to_cluster"] * transfer_model_scale_factor
        )
        step_times["running_quantization"] = int(step_times["running_quantization"] * device_scale_factor)
        step_times["run_evaluation"] = int(step_times["run_evaluation"] * device_scale_factor)

        # If step_time is provided, use it for the current step
        if step_time is not None:
            step_times[current_step] = step_time

        # Calculate total time for current and future steps
        total_time = 0
        current_step_index = step_order.index(current_step) if current_step in step_order else 0

        for i in range(current_step_index, len(step_order)):
            step = step_order[i]
            total_time += step_times.get(step, 10)  # Default 10 minutes for unknown steps

        return math.ceil(total_time)

    @staticmethod
    def publish_eta(
        notification_req: dict, deploy_quantization_request_json: dict, workflow_id: str, current_step: str
    ):
        """Publish estimated time to completion notification.

        Args:
            notification_req (str): The notification request object.
            deploy_quantization_request_json (str): The deployment quantization request object.
            workflow_id (str): The ID of the workflow.

        This method updates the notification payload with ETA information and publishes
        it to the appropriate topic using the DaprWorkflow service.
        """
        eta = QuantizationService.get_deployment_eta(
            current_step=current_step,
            model_size=deploy_quantization_request_json.model_size,
            device_type=deploy_quantization_request_json.device_type,
        )
        notification_req.payload.event = "eta"
        notification_req.payload.content = NotificationContent(
            title="Estimated time to completion",
            message=f"{eta}",
            status=WorkflowStatus.RUNNING,
        )
        DaprWorkflow().publish_notification(
            workflow_id=workflow_id,
            notification=notification_req,
            target_topic_name=deploy_quantization_request_json.source_topic,
            target_name=deploy_quantization_request_json.source,
        )


class AdapterService(SessionMixin):
    async def deploy_adapter(self, adapter_request: AdapterRequest) -> Union[WorkflowMetadataResponse, ErrorResponse]:
        """Deploy adapter."""
        from .adapter_workflows import AdapterWorkflow, DeleteAdapterWorkflow

        try:
            if adapter_request.action == "add":
                response = await AdapterWorkflow().__call__(adapter_request)
            elif adapter_request.action == "delete":
                response = await DeleteAdapterWorkflow().__call__(adapter_request)
        except Exception as e:
            logger.error(f"Error deploying adapter: {e}")
            # Return ErrorResponse instead of raising it since it's not an Exception
            return ErrorResponse(message=str(e))
        return response

    @staticmethod
    def get_adapter_eta(current_step: str, step_time: int = None) -> dict:
        """Get adapter eta."""
        step_times = {
            "verify_cluster_connection": 0.5,
            "transfer_adapter_to_cluster": 5,
            "deploy_adapter": 2,
            "adapter_status": 2,
        }

        # Define the order of steps
        step_order = [
            "verify_cluster_connection",
            "transfer_adapter_to_cluster",
            "deploy_adapter",
            "adapter_status",
        ]

        # If step_time is provided, use it for the current step
        if step_time is not None:
            step_times[current_step] = step_time

        # Calculate total time for current and future steps
        total_time = 0
        current_step_index = step_order.index(current_step) if current_step in step_order else 0

        for i in range(current_step_index, len(step_order)):
            step = step_order[i]
            total_time += step_times.get(step, 10)  # Default 10 minutes for unknown steps

        return math.ceil(total_time)

    @staticmethod
    def publish_eta(notification_req: dict, adapter_request_json: dict, workflow_id: str, current_step: str):
        """Publish estimated time to completion notification.

        Args:
            notification_req (str): The notification request object.
            deploy_quantization_request_json (str): The deployment quantization request object.
            workflow_id (str): The ID of the workflow.

        This method updates the notification payload with ETA information and publishes
        it to the appropriate topic using the DaprWorkflow service.
        """
        eta = AdapterService.get_adapter_eta(current_step=current_step)
        notification_req.payload.event = "eta"
        notification_req.payload.content = NotificationContent(
            title="Estimated time to completion",
            message=f"{eta}",
            status=WorkflowStatus.RUNNING,
        )
        DaprWorkflow().publish_notification(
            workflow_id=workflow_id,
            notification=notification_req,
            target_topic_name=adapter_request_json.source_topic,
            target_name=adapter_request_json.source,
        )
