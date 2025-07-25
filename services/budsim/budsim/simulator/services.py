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

import math
import uuid
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple, Union

from budmicroframe.commons import logging
from budmicroframe.commons.constants import WorkflowStatus
from budmicroframe.commons.schemas import (
    ErrorResponse,
    NotificationContent,
    NotificationRequest,
    PaginatedResponse,
)
from budmicroframe.shared.dapr_service import DaprService
from budmicroframe.shared.dapr_workflow import DaprWorkflow
from pydantic import ValidationError
from sqlalchemy.orm import Session

from ..commons.config import app_settings
from ..engine_ops import (
    get_compatible_engine_image,
    get_compatible_engines,
    get_engine_args_and_envs,
)
from .evolution import Evolution
from .models import SimulationResultsCRUD, SimulationResultsSchema
from .schemas import (
    ClusterInfo,
    ClusterMetrics,
    ClusterRecommendationRequest,
    ClusterRecommendationResponse,
    DeploymentConfigurationRequest,
    DeploymentConfigurationResponse,
    DeviceConfiguration,
    DeviceTypeMetrics,
    NodeConfiguration,
    SimulationMetrics,
)


logger = logging.get_logger(__name__)

dapr_workflow = DaprWorkflow()


class SimulationService:

    @staticmethod
    def get_eta(current_step: str, cluster_count: int, step_time: int=None):
        """Calculate the estimated time to completion for workflow steps.

        This method calculates the estimated time for the current step and remaining steps
        in the workflow, with performance estimation time scaling based on cluster count.

        Args:
            current_step (str): The current step in the workflow process.
            cluster_count (int): Number of clusters being processed.
            step_time (int, optional): Override the default time for the current step. Defaults to None.

        Returns:
            int: The estimated time in minutes for the current step.
        """
        step_times = {
            "validation": 0.1,
            "performance_estimation": 0.5,
            "ranking": 0.2
        }

        # Define the order of steps
        step_order = ["validation", "performance_estimation", "ranking"]

        #Apply scaling factor
        step_times["performance_estimation"] = int(step_times["performance_estimation"] * cluster_count)


        if step_time is not None:
            step_times[current_step] = step_time

        # Calculate total time for current and future steps
        total_time = 0
        current_step_index = step_order.index(current_step) if current_step in step_order else 0

        for i in range(current_step_index, len(step_order)):
            step = step_order[i]
            total_time += step_times.get(step, 10)  # Default 10 minutes for unknown steps

        return int(total_time)

    @staticmethod
    def get_topk_engine_configs(
        engine_name: str,
        pretrained_model_uri: str,
        input_tokens: int,
        output_tokens: int,
        concurrency: int,
        target_ttft: float,
        target_throughput_per_user: float,
        target_e2e_latency: float,
        device_config: Dict[str, Any],
        quantization_type: str,
        engine_image: str,
        **kwargs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate the top K deployment configurations based on the provided parameters.

        Args:
            engine_name (str): The name of the engine to be used for deployment.
            pretrained_model_uri (str): The URI of the pretrained model.
            input_tokens (int): The number of input tokens.
            output_tokens (int): The number of output tokens.
            concurrency (int): The level of concurrency for the deployment.
            target_throughput (int): The target throughput for the deployment.
            target_ttft (int): The target time to first token (TTFT).
            target_throughput_per_user (int): The target throughput per user.
            device_config (Dict[str, Any]): Configuration details for the device.
            **kwargs (Dict[str, Any]): Additional keyword arguments.

        Returns:
            Dict[str, Any]: A dictionary containing the top K configurations, the engine name, and the device configuration.
        """
        try:
            evolution = Evolution(
                model=pretrained_model_uri,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                max_concurrency=concurrency,
                target_ttft=target_ttft,
                target_throughput_per_user=target_throughput_per_user,
                target_e2e_latency=target_e2e_latency,
                engine_name=engine_name,
                device_config=device_config,
                benchmark_predictor_models_dir=app_settings.benchmark_predictor_models_dir,
                generation=app_settings.generation_count,
                population_size=app_settings.population_size,
                dtype=quantization_type,
            )
            top_k_configs = evolution.evolve()

            device_config["device_id"] = device_config.pop("id", str(uuid.uuid4()))
            device_config["device_type"] = device_config.pop("type")
            device_config["device_name"] = device_config.pop("name", device_config["device_id"])
            device_config = {k.lower(): v for k, v in device_config.items()}

            return {
                "top_k_configs": top_k_configs,
                "engine": engine_name,
                "engine_image": engine_image,
                "device_config": device_config,
            }
        except Exception as e:
            logger.exception(
                "Error running simulation for %s with device type %s: %s",
                engine_name,
                device_config.get("device_type") or device_config.get("type"),
                str(e),
            )

    @staticmethod
    def get_topk_proprietary_engine_configs(
        engine_name: str,
        pretrained_model_uri: str,
        input_tokens: int,
        output_tokens: int,
        concurrency: int,
        device_config: Dict[str, Any],
        engine_image: str,
        **kwargs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate the top K deployment configurations based on the provided parameters.

        Args:
            engine_name (str): The name of the engine to be used for deployment.
            pretrained_model_uri (str): The URI of the pretrained model.
            input_tokens (int): The number of input tokens.
            output_tokens (int): The number of output tokens.
            concurrency (int): The level of concurrency for the deployment.
            target_throughput (int): The target throughput for the deployment.
            target_ttft (int): The target time to first token (TTFT).
            target_throughput_per_user (int): The target throughput per user.
            device_config (Dict[str, Any]): Configuration details for the device.
            **kwargs (Dict[str, Any]): Additional keyword arguments.

        Returns:
            Dict[str, Any]: A dictionary containing the top K configurations, the engine name, and the device configuration.
        """
        import random

        from ..engine_ops import get_engine_max_concurrency
        from .evolution import EvaluationResult

        top_k_configs = [
            EvaluationResult(
                config={"model": pretrained_model_uri},
                kv_cache_memory=512,
                ttft=0,
                e2e_latency=0,
                throughput_per_user=0,
                concurrency=get_engine_max_concurrency(engine_name),
                fitness=(0, 0, 0),
                error_rate=0,
                cost_per_million_tokens=random.random(),
            )
        ]

        device_config["device_id"] = device_config.pop("id", str(uuid.uuid4()))
        device_config["device_type"] = device_config.pop("type")
        device_config["device_name"] = device_config.pop("name", device_config["device_id"])
        device_config = {k.lower(): v for k, v in device_config.items()}
        return {
            "top_k_configs": top_k_configs,
            "engine": engine_name,
            "engine_image": engine_image,
            "device_config": device_config,
        }

    @staticmethod
    def get_topk_quantization_engine_configs(
        engine_name: str,
        pretrained_model_uri: str,
        device_config: Dict[str, Any],
        quantization_method: str,
        quantization_type: str,
        engine_image: str,
        **kwargs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate the top K quantization engine configurations based on the provided parameters.

        Args:
            engine_name (str): The name of the engine to be used for quantization.
            pretrained_model_uri (str): The URI of the pretrained model.
            device_config (Dict[str, Any]): Configuration details for the device.
            method (str): The quantization method to be used (e.g., "RTN", "AWQ").
            **kwargs (Dict[str, Any]): Additional keyword arguments.

        Returns:
            Dict[str, Any]: A dictionary containing the top K configurations, the engine name, and the device configuration.
        """
        from .evolution import EvaluationResult
        from .hardware import CostCalculator

        cost_calculator = CostCalculator()

        top_k_configs = [
            EvaluationResult(
                config={"model": pretrained_model_uri, "quantization_method": quantization_method, "quantization_type": quantization_type},
                kv_cache_memory=512,
                ttft=0,
                e2e_latency=0,
                throughput_per_user=0,
                concurrency=1,
                fitness=(0, 0, 0),
                error_rate=0,
                cost_per_million_tokens=cost_calculator.get_quantization_cost(pretrained_model_uri, quantization_method, device_config),
            )
        ]
        
        device_config["device_id"] = device_config.pop("id", str(uuid.uuid4()))
        device_config["device_type"] = device_config.pop("type")
        device_config["device_name"] = device_config.pop("name", device_config["device_id"])
        device_config = {k.lower(): v for k, v in device_config.items()}
        return {
            "top_k_configs": top_k_configs,
            "engine": engine_name,
            "engine_image": engine_image,
            "device_config": device_config,
        }

    @staticmethod
    def validate_cluster_info(cluster_info: Union[List[Dict[str, Any]], str]) -> List[Dict[str, Any]]:
        """Validate and normalize cluster information.

        This function validates the provided cluster information against the ClusterInfo model
        and returns a normalized JSON representation of the data.

        Args:
            cluster_info (Union[List[Dict[str, Any]], str]): The cluster information to validate,
                either as a JSON string or a list of dictionaries.

        Returns:
            List[Dict[str, Any]]: A validated and normalized list of cluster information dictionaries.

        Raises:
            ValidationError: If the provided cluster information does not conform to the ClusterInfo model.
        """
        model = (
            ClusterInfo.model_validate_json(cluster_info)
            if isinstance(cluster_info, str)
            else ClusterInfo.model_validate(cluster_info)
        )

        return model.model_dump(mode="json")

    @staticmethod
    def get_available_clusters(
        workflow_id: str,
        notification_request: NotificationRequest,
        target_topic_name: Optional[str] = None,
        target_name: Optional[str] = None,
        cluster_id: Optional[uuid.UUID] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve available clusters for simulation.

        This function fetches cluster information from the state store, validates it,
        and filters by cluster_id if provided. It sends notifications about the
        validation process and any errors encountered.

        Args:
            workflow_id (str): The ID of the workflow.
            notification_request (NotificationRequest): The notification request object.
            target_topic_name (Optional[str], optional): The target topic name for notifications. Defaults to None.
            target_name (Optional[str], optional): The target name for notifications. Defaults to None.
            cluster_id (Optional[uuid.UUID], optional): The specific cluster ID to filter by. Defaults to None.

        Returns:
            List[Dict[str, Any]]: A list of available cluster information dictionaries.

        Raises:
            ValidationError: If the cluster information fails validation.
            ValueError: If no cluster information is available.
            Exception: For any other errors encountered during the process.
        """
        notification_req = notification_request.model_copy(deep=True)
        notification_req.payload.event = "validation"

        notification_req.payload.content = NotificationContent(
            title="Requirement validation",
            message="Validating the requirements for the simulation",
            status=WorkflowStatus.STARTED,
        )
        dapr_workflow.publish_notification(
            workflow_id=workflow_id,
            notification=notification_req,
            target_topic_name=target_topic_name,
            target_name=target_name,
        )

        try:
            with DaprService() as dapr_service:
                cluster_info = dapr_service.get_state(
                    app_settings.statestore_name, app_settings.cluster_info_state_key
                )

            cluster_info = SimulationService.validate_cluster_info(cluster_info.data.decode("utf-8"))

            # Filter out inactive nodes in each cluster
            for cluster in cluster_info:
                cluster["nodes"] = [node for node in cluster.get("nodes", []) if node.get("status", True)]

            if cluster_id:
                cluster_info = [cluster for cluster in cluster_info if cluster["id"] == str(cluster_id)]

            if not len(cluster_info):
                raise ValueError("Cluster info is required to run the simulation")

            return cluster_info
        except ValidationError as e:
            logger.exception("Error validating cluster info: %s", str(e))
            notification_req.payload.content = NotificationContent(
                title="Invalid cluster info",
                message="Fix: Contact support",
                status=WorkflowStatus.FAILED,
            )
            dapr_workflow.publish_notification(
                workflow_id=workflow_id,
                notification=notification_req,
                target_topic_name=target_topic_name,
                target_name=target_name,
            )
            raise e
        except Exception as e:
            logger.exception("Error getting cluster info: %s", str(e))
            notification_req.payload.content = NotificationContent(
                title="No clusters found" if cluster_id is None else "The cluster is not available",
                message="Fix: Go to cluster management to add clusters",
                status=WorkflowStatus.FAILED,
                primary_action="retry",
            )
            dapr_workflow.publish_notification(
                workflow_id=workflow_id,
                notification=notification_req,
                target_topic_name=target_topic_name,
                target_name=target_name,
            )
            raise e

    @staticmethod
    def get_compatible_engines(
        workflow_id: str,
        pretrained_model_uri: str,
        cluster_info: List[Dict[str, Any]],
        notification_request: NotificationRequest,
        target_topic_name: Optional[str] = None,
        target_name: Optional[str] = None,
        proprietary_only: bool = False,
        cluster_id: Optional[uuid.UUID] = None,
    ) -> List[Dict[str, str]]:
        """Identify compatible engines for a given model and cluster configuration.

        This method determines which inference engines are compatible with the specified
        pretrained model, considering the available clusters. It sends notifications about
        the progress and results of the compatibility check.

        Args:
            workflow_id (str): The ID of the current workflow.
            pretrained_model_uri (str): URI of the pretrained model to check compatibility for.
            cluster_info (List[Dict[str, Any]]): Information about available clusters.
            notification_request (NotificationRequest): Template for notifications to be sent.
            target_topic_name (Optional[str], optional): Topic name for notifications. Defaults to None.
            target_name (Optional[str], optional): Target name for notifications. Defaults to None.
            proprietary_only (bool, optional): Whether to check only proprietary engines. Defaults to False.
            cluster_id (Optional[uuid.UUID], optional): Specific cluster ID to check. Defaults to None.

        Returns:
            List[Dict[str, str]]: List of compatible engine configurations, each containing
                                 engine_name and device information.

        Raises:
            Exception: If compatibility check fails, with appropriate notification sent.
        """
        notification_req = notification_request.model_copy(deep=True)

        try:
            # Notify the ETA based on the number of clusters
            notification_req.payload.event = "eta"
            notification_req.payload.content = NotificationContent(
                title="Estimated time to completion",
                message=f"{SimulationService.get_eta(current_step='validation', cluster_count=len(cluster_info))}",
                status=WorkflowStatus.RUNNING,
            )
            dapr_workflow.publish_notification(
                workflow_id=workflow_id,
                notification=notification_req,
                target_topic_name=target_topic_name,
                target_name=target_name,
            )

            compatible_engines = get_compatible_engines(pretrained_model_uri, proprietary_only)

            if len(compatible_engines) == 0:
                raise ValueError("No compatible engines found")

            notification_req.payload.event = "validation"
            notification_req.payload.content = NotificationContent(
                title="Identified compatible clusters" if cluster_id is None else "Cluster is compatible",
                message="All requirements and runtime compatibility are met for the cluster(s)",
                status=WorkflowStatus.COMPLETED,
            )
            dapr_workflow.publish_notification(
                workflow_id=workflow_id,
                notification=notification_req,
                target_topic_name=target_topic_name,
                target_name=target_name,
            )
            return compatible_engines
        except Exception as e:
            notification_req.payload.event = "validation"
            notification_req.payload.content = NotificationContent(
                title="Model is not compatible with engine",
                message="Fix: Try a different model",
                status=WorkflowStatus.FAILED,
                primary_action="retry",
            )
            dapr_workflow.publish_notification(
                workflow_id=workflow_id,
                notification=notification_req,
                target_topic_name=target_topic_name,
                target_name=target_name,
            )
            raise e

    def get_topk_engine_configs_per_cluster(
        self,
        workflow_id: str,
        request: ClusterRecommendationRequest,
        compatible_engines: List[Tuple[str, str]],
        cluster_info: List[Dict[str, Any]],
        notification_request: NotificationRequest,
        cluster_id: Optional[uuid.UUID] = None,
    ) -> List[Dict[str, Any]]:
        """Get the top-k engine configurations for each cluster.

        This function processes each cluster and its nodes to find the best engine configurations
        based on the compatible engines and device types. It uses parallel processing to evaluate
        multiple configurations simultaneously.

        Args:
            workflow_id (str): The ID of the workflow.
            request (ClusterRecommendationRequest): The request containing parameters for recommendation.
            compatible_engines (List[Tuple[str, str]]): List of compatible engine and device combinations.
            cluster_info (List[Dict[str, Any]]): Information about available clusters.
            notification_request (NotificationRequest): The notification request to update workflow status.
            cluster_id (Optional[uuid.UUID], optional): Specific cluster ID to focus on. Defaults to None.

        Returns:
            List[Dict[str, Any]]: List of top engine configurations for each cluster.

        Raises:
            Exception: If there's an error during configuration generation, with appropriate notification sent.
        """
        notification_req = notification_request.model_copy(deep=True)
        notification_req.payload.event = "performance_estimation"

        notification_req.payload.content = NotificationContent(
            title="Generating best configurations",
            message="Estimating the performance metrics for the configurations",
            status=WorkflowStatus.STARTED,
        )
        dapr_workflow.publish_notification(
            workflow_id=workflow_id,
            notification=notification_req,
            target_topic_name=request.source_topic,
            target_name=request.source,
        )

        method = (
            self.get_topk_engine_configs
            if not request.is_proprietary_model
            else self.get_topk_proprietary_engine_configs
        )

        if request.is_quantization:
            method = self.get_topk_quantization_engine_configs

        try:
            with ProcessPoolExecutor() as executor:
                results = [
                    executor.submit(
                        method,
                        device_config={
                            **deepcopy(device),
                            "cluster_id": cluster["id"],
                            "node_id": node["id"],
                            "node_name": node["name"],
                        },
                        **request.model_dump(),
                        engine_name=engine_device_combo["engine_name"],
                        engine_image=engine_device_combo["image"],
                    )
                    for cluster in cluster_info
                    for node in cluster.get("nodes", [])
                    for device in node.get("devices", [])
                    for engine_device_combo in compatible_engines
                    if device["type"] == engine_device_combo["device"]
                ]
                results = [future.result() for future in results]  # type: ignore

            notification_req.payload.content = NotificationContent(
                title="Generated best configurations for each cluster" if cluster_id is None else "Generated best configurations for the cluster",
                message="All performance metrics are estimated",
                status=WorkflowStatus.COMPLETED,
            )
            dapr_workflow.publish_notification(
                workflow_id=workflow_id,
                notification=notification_req,
                target_topic_name=request.source_topic,
                target_name=request.source,
            )
            return results

        except Exception as e:
            notification_req.payload.content = NotificationContent(
                title="Failed to generate best configurations",
                message="Fix: Retry the simulation",
                status=WorkflowStatus.FAILED,
                primary_action="retry",
            )
            dapr_workflow.publish_notification(
                workflow_id=workflow_id,
                notification=notification_req,
                target_topic_name=request.source_topic,
                target_name=request.source,
            )
            raise e

    def rank_configs(
        self,
        workflow_id: str,
        request: ClusterRecommendationRequest,
        topk_engine_configs: List[Dict[str, Any]],
        notification_request: NotificationRequest,
        serialize: bool = False,
        cluster_id: Optional[uuid.UUID] = None,
    ) -> Union[List[ClusterInfo], List[Dict[str, Any]]]:
        """Rank the configurations based on performance metrics.

        This method processes the top K engine configurations, stores them in the database,
        and ranks them based on performance metrics. It publishes notifications about the
        ranking process status.

        Args:
            workflow_id (str): The ID of the workflow.
            request (ClusterRecommendationRequest): The request containing model and performance requirements.
            topk_engine_configs (List[Dict[str, Any]]): The top K engine configurations to rank.
            notification_request (NotificationRequest): The notification request template.
            serialize (bool, optional): Whether to serialize the results. Defaults to False.
            cluster_id (Optional[uuid.UUID], optional): The specific cluster ID to rank. Defaults to None.

        Returns:
            Union[List[ClusterInfo], List[Dict[str, Any]]]: The ranked configurations, either as model objects
                or serialized dictionaries based on the serialize parameter.

        Raises:
            ValueError: If there are no simulation results to process.
            Exception: If any error occurs during the ranking process.
        """
        notification_req = notification_request.model_copy(deep=True)
        notification_req.payload.event = "ranking"
        recommendations = []

        notification_req.payload.content = NotificationContent(
            title="Ranking the clusters based on performance" if cluster_id is None else "Ranking the configurations based on performance",
            message="Finding the most suitable clusters based on performance metrics" if cluster_id is None else "Finding the most suitable configurations based on performance metrics",
            status=WorkflowStatus.STARTED,
        )
        dapr_workflow.publish_notification(
            workflow_id=workflow_id,
            notification=notification_req,
            target_topic_name=request.source_topic,
            target_name=request.source,
        )

        try:
            kwargs = {
                "workflow_id": workflow_id,
                "model_name": request.pretrained_model_uri,
                "model_version": "latest",
                "input_tokens": request.input_tokens,
                "output_tokens": request.output_tokens,
                "target_concurrency": request.concurrency,
                "target_ttft": request.target_ttft,
                "target_throughput_per_user": request.target_throughput_per_user,
                "target_e2e_latency": request.target_e2e_latency,
            }
            records = [
                {
                    **kwargs,
                    **result["device_config"],
                    "engine": result["engine"],
                    "engine_image": result["engine_image"],
                    "top_k_configs": config.__dict__,
                }
                for result in topk_engine_configs
                if result is not None
                for config in result["top_k_configs"]
            ]

            with SimulationResultsCRUD() as crud:
                if len(records):
                    crud.delete(conditions={"workflow_id": workflow_id})
                    crud.bulk_insert(records)
                else:
                    raise ValueError("No simulation results to process")

            recommendations = []
            result = self.get_topk_cluster_recommendations(workflow_id=workflow_id, limit=10)
            for item in result.items:
                recommendations.append(item.model_dump(mode="json") if serialize else item)

            notification_req.payload.content = NotificationContent(
                title="Ranked the clusters based on performance" if cluster_id is None else "Ranked the configurations based on performance",
                message=f"Found {len(recommendations)} suitable cluster(s)",
                status=WorkflowStatus.COMPLETED,
            )
            dapr_workflow.publish_notification(
                workflow_id=workflow_id,
                notification=notification_req,
                target_topic_name=request.source_topic,
                target_name=request.source,
            )

            return recommendations
        except Exception as e:
            notification_req.payload.content = NotificationContent(
                title="Failed to rank the clusters" if cluster_id is None else "Failed to rank the configurations",
                message="Fix: Retry the simulation",
                status=WorkflowStatus.FAILED,
                primary_action="retry",
            )
            dapr_workflow.publish_notification(
                workflow_id=workflow_id,
                notification=notification_req,
                target_topic_name=request.source_topic,
                target_name=request.source,
            )
            raise e

    def __call__(
        self, request: ClusterRecommendationRequest, workflow_id: Optional[str] = None
    ) -> ClusterRecommendationResponse:
        """Execute the simulation process based on the provided deployment configuration.

        This method retrieves cluster information, determines compatible engines,
        and generates the top K deployment configurations. It also logs the results
        and publishes the recommendations to a specified topic if provided.

        Args:
            config (ClusterRecommendationRequest): The deployment configuration
            containing model URI, input/output tokens, concurrency, and target
            performance metrics.
            workflow_id (Optional[str]): An optional workflow ID for tracking the
            simulation process.

        Raises:
            ValueError: If the cluster information is not available or empty.

        Returns:
            List[Dict[str, Any]]: A sorted list of deployment recommendations based
            on error rates and device types.
        """
        workflow_name = "get_cluster_recommendations"
        notification_request = NotificationRequest.from_cloud_event(
            cloud_event=request,
            name=workflow_name,
            workflow_id=workflow_id,
        )
        response = ClusterRecommendationResponse(workflow_id=workflow_id, recommendations=[])

        cluster_info = self.get_available_clusters(
            workflow_id, notification_request, request.source_topic, request.source, request.cluster_id
        )
        compatible_engines = self.get_compatible_engines(
            workflow_id,
            request.pretrained_model_uri,
            cluster_info,
            notification_request,
            request.source_topic,
            request.source,
            proprietary_only=request.is_proprietary_model,
            cluster_id=request.cluster_id,
        )
        topk_engine_configs = self.get_topk_engine_configs_per_cluster(
            workflow_id, request, compatible_engines, cluster_info, notification_request, cluster_id=request.cluster_id
        )
        recommendations = self.rank_configs(workflow_id, request, topk_engine_configs, notification_request, cluster_id=request.cluster_id)

        response.recommendations = recommendations

        notification_request.payload.event = "results"
        notification_request.payload.content = NotificationContent(
            title="Deployment Recommendation Results",
            message="The deployment recommendation results are ready",
            result=response.model_dump(),
            status=WorkflowStatus.COMPLETED,
        )

        dapr_workflow.publish_notification(
            workflow_id=workflow_id,
            notification=notification_request,
            target_topic_name=request.source_topic,
            target_name=request.source,
        )

        return response

    def get_topk_cluster_recommendations(
        self,
        workflow_id: str,
        cluster_id: Optional[str] = None,
        concurrency: Optional[int] = None,
        error_rate_threshold: float = 0.5,
        page: int = 1,
        limit: int = 1,
        session: Optional[Session] = None,
    ) -> PaginatedResponse[ClusterMetrics]:
        results, total_count = SimulationResultsCRUD().fetch_topk_configs_by_cluster(
            workflow_id=workflow_id,
            cluster_id=cluster_id,
            error_rate_threshold=error_rate_threshold,
            limit=limit,
            skip=(page - 1) * limit,
            session=session,
        )

        logger.info("Found %s/%s deployment configurations", len(results), total_count)

        recommendations = {}

        for result in results:
            recommendation = ClusterMetrics(
                cluster_id="",
                metrics=SimulationMetrics(
                    device_types=[],
                    replica=0,
                    concurrency=0,
                    ttft=0,
                    throughput_per_user=0,
                    e2e_latency=0,
                    error_rate=0,
                    cost_per_million_tokens=0,
                ),
            )
            deployment_config = self.optimal_search_deployment_config(result, concurrency)
            if deployment_config is not None:
                device_types = {}
                for node in deployment_config.nodes:
                    for device in node.devices:
                        if device.type not in device_types:
                            device_types[device.type] = DeviceTypeMetrics(
                                device_type=device.type,
                                num_replicas=device.replica,
                                concurrency=device.concurrency,
                                cost_per_million_tokens=device.cost_per_million_tokens,
                            )
                        else:
                            device_types[device.type].num_replicas += device.replica
                            device_types[device.type].concurrency += device.concurrency
                            device_types[device.type].cost_per_million_tokens += device.cost_per_million_tokens

                recommendation.cluster_id = deployment_config.id
                recommendation.metrics.device_types = list(device_types.values())
                recommendation.metrics.replica = deployment_config.replica
                recommendation.metrics.concurrency = deployment_config.concurrency
                recommendation.metrics.ttft = deployment_config.ttft
                recommendation.metrics.throughput_per_user = deployment_config.throughput_per_user
                recommendation.metrics.e2e_latency = deployment_config.e2e_latency
                recommendation.metrics.error_rate = deployment_config.error_rate
                recommendation.metrics.cost_per_million_tokens = deployment_config.cost_per_million_tokens

                if (
                    recommendation.cluster_id not in recommendations
                    or recommendations[recommendation.cluster_id].metrics.cost_per_million_tokens
                    > deployment_config.cost_per_million_tokens
                ):
                    recommendations[recommendation.cluster_id] = recommendation

        return PaginatedResponse(
            object="cluster_recommendations",
            items=sorted(recommendations.values(), key=lambda x: x.metrics.cost_per_million_tokens),
            total_items=total_count,
            page=page,
            limit=limit,
        )

    @staticmethod
    def greedy_search_deployment_config(
        simulation_results: List[SimulationResultsSchema], target_concurrency: int = None
    ) -> DeploymentConfigurationResponse:
        nodes = {}
        device_ids = set()
        config = DeploymentConfigurationResponse(
            id=simulation_results[0].cluster_id,
            nodes=[],
            replica=0,
            concurrency=0,
            ttft=0,
            throughput_per_user=0,
            e2e_latency=0,
            error_rate=0,
            cost_per_million_tokens=0,
        )
        target_concurrency = target_concurrency or simulation_results[0].target_concurrency

        for entry in sorted(
            simulation_results,
            key=lambda x: x.top_k_configs["cost_per_million_tokens"] / x.top_k_configs["concurrency"],
        ):
            node_id = entry.node_id
            if node_id not in nodes:
                nodes[node_id] = NodeConfiguration(
                    id=node_id,
                    name=entry.node_name,
                    devices=[],
                )

            engine_config = entry.top_k_configs["config"]
            engine_config["model"] = entry.model_name
            if entry.device_id in device_ids or engine_config.get("tensor_parallel_size", 1) > entry.available_count:
                continue
            try:
                args_and_envs = get_engine_args_and_envs(entry.engine, engine_config)
            except Exception:
                logger.exception("Failed to get engine args and envs for %s", engine_config)
                continue

            device_info = DeviceConfiguration(
                config_id=str(entry.id),
                name=entry.device_name,
                type=entry.device_type,
                image=entry.engine_image,
                memory=entry.top_k_configs["kv_cache_memory"],
                num_cpus=args_and_envs["envs"].get("NUM_CPUS", -1),
                args=args_and_envs["args"],
                envs=args_and_envs["envs"],
                tp_size=engine_config.get("tensor_parallel_size", 1),
                replica=0,
                concurrency=0,
                ttft=float(entry.top_k_configs["ttft"]),
                throughput_per_user=float(entry.top_k_configs["throughput_per_user"]),
                e2e_latency=float(entry.top_k_configs["e2e_latency"]),
                error_rate=float(entry.top_k_configs["error_rate"]),
                cost_per_million_tokens=0,
            )

            config.ttft += device_info.ttft
            config.throughput_per_user += device_info.throughput_per_user
            config.e2e_latency += device_info.e2e_latency
            config.error_rate += device_info.error_rate

            for _ in range(1, entry.available_count + 1, device_info.tp_size):
                config.concurrency += int(entry.top_k_configs["concurrency"])
                config.cost_per_million_tokens += float(entry.top_k_configs["cost_per_million_tokens"])
                config.replica += 1

                device_info.concurrency += int(entry.top_k_configs["concurrency"])
                device_info.cost_per_million_tokens += float(entry.top_k_configs["cost_per_million_tokens"])
                device_info.replica += 1

                if config.concurrency >= target_concurrency:
                    break

            nodes[node_id].devices.append(device_info)
            device_ids.add(entry.device_id)

            if config.concurrency >= target_concurrency:
                break

        if config.concurrency >= target_concurrency:
            num_workers = len(device_ids)
            config.ttft /= num_workers
            config.throughput_per_user /= num_workers
            config.e2e_latency /= num_workers
            config.error_rate /= num_workers
            config.nodes = list(filter(lambda x: x.devices, nodes.values()))
        else:
            config = None

        return config

    @staticmethod
    def optimal_search_deployment_config(
        simulation_results: List[SimulationResultsSchema], target_concurrency: int = None
    ) -> DeploymentConfigurationResponse:
        target_concurrency = target_concurrency or simulation_results[0].target_concurrency

        device_args_and_envs = {}
        valid_combination = None
        for i, entry in enumerate(simulation_results):
            if entry.device_id not in device_args_and_envs:
                engine_config = entry.top_k_configs["config"]
                engine_config["model"] = entry.model_name
                if engine_config.get("tensor_parallel_size", 1) > entry.available_count:
                    continue

                try:
                    device_args_and_envs[entry.device_id] = {
                        **get_engine_args_and_envs(entry.engine, engine_config),
                        "tp_size": engine_config.get("tensor_parallel_size", 1),
                    }
                except Exception:
                    logger.exception("Failed to get engine args and envs for %s", engine_config)
                    continue

            combos = []
            tp_size = device_args_and_envs[entry.device_id]["tp_size"]
            replicas = min(
                entry.available_count // tp_size,
                math.ceil(target_concurrency / entry.top_k_configs["concurrency"]),
            )
            combos.append((i, replicas))
            cur_concurrency = entry.top_k_configs["concurrency"] * replicas
            cur_cost = entry.top_k_configs["cost_per_million_tokens"] * replicas
            last_best_entry = None

            if cur_concurrency >= target_concurrency and (
                valid_combination is None or cur_cost < valid_combination[1]
            ):
                valid_combination = (combos, cur_cost, cur_concurrency)
                continue

            for j, _entry in enumerate(simulation_results):
                if i == j:
                    continue

                if entry.device_id not in device_args_and_envs:
                    engine_config = entry.top_k_configs["config"]
                    engine_config["model"] = entry.model_name
                    if engine_config.get("tensor_parallel_size", 1) > entry.available_count:
                        continue

                    try:
                        device_args_and_envs[entry.device_id] = {
                            **get_engine_args_and_envs(entry.engine, engine_config),
                            "tp_size": engine_config.get("tensor_parallel_size", 1),
                        }
                    except Exception:
                        logger.exception("Failed to get engine args and envs for %s", engine_config)
                        continue

                tp_size = device_args_and_envs[entry.device_id]["tp_size"]
                replicas = min(
                    _entry.available_count // tp_size,
                    max(1, math.ceil((target_concurrency - cur_concurrency) / _entry.top_k_configs["concurrency"])),
                )

                if cur_concurrency + _entry.top_k_configs["concurrency"] * replicas > target_concurrency:
                    last_best_cost = (
                        simulation_results[last_best_entry[0]].top_k_configs["cost_per_million_tokens"]
                        * last_best_entry[1]
                        if last_best_entry is not None
                        else float("inf")
                    )
                    if last_best_cost > _entry.top_k_configs["cost_per_million_tokens"] * replicas:
                        last_best_entry = (j, replicas)

                    continue

                combos.append((j, replicas))
                cur_concurrency += _entry.top_k_configs["concurrency"] * replicas
                cur_cost += _entry.top_k_configs["cost_per_million_tokens"] * replicas
                if cur_concurrency == target_concurrency:
                    break

            if last_best_entry is not None and cur_concurrency < target_concurrency:
                combos.append(last_best_entry)
                cur_concurrency += (
                    simulation_results[last_best_entry[0]].top_k_configs["concurrency"] * last_best_entry[1]
                )
                cur_cost += (
                    simulation_results[last_best_entry[0]].top_k_configs["cost_per_million_tokens"]
                    * last_best_entry[1]
                )

            if cur_concurrency >= target_concurrency and (
                valid_combination is None or cur_cost < valid_combination[1]
            ):
                valid_combination = (combos, cur_cost, cur_concurrency)

        if valid_combination is None:
            return None

        config = DeploymentConfigurationResponse(
            id=simulation_results[0].cluster_id,
            nodes=[],
            replica=0,
            concurrency=valid_combination[2],
            ttft=0,
            throughput_per_user=0,
            e2e_latency=0,
            error_rate=0,
            cost_per_million_tokens=valid_combination[1],
        )
        nodes = {}
        for idx, replica in valid_combination[0]:
            entry = simulation_results[idx]
            node_id = entry.node_id
            if node_id not in nodes:
                nodes[node_id] = NodeConfiguration(
                    id=node_id,
                    name=entry.node_name,
                    devices=[],
                )

            device_info = DeviceConfiguration(
                config_id=str(entry.id),
                name=entry.device_name,
                type=entry.device_type,
                image=entry.engine_image,
                memory=entry.top_k_configs["kv_cache_memory"],
                num_cpus=device_args_and_envs[entry.device_id]["envs"].get("NUM_CPUS", -1),
                args=device_args_and_envs[entry.device_id]["args"],
                envs=device_args_and_envs[entry.device_id]["envs"],
                tp_size=device_args_and_envs[entry.device_id]["tp_size"],
                replica=replica,
                concurrency=int(entry.top_k_configs["concurrency"]) * replica,
                ttft=float(entry.top_k_configs["ttft"]),
                throughput_per_user=float(entry.top_k_configs["throughput_per_user"]),
                e2e_latency=float(entry.top_k_configs["e2e_latency"]),
                error_rate=float(entry.top_k_configs["error_rate"]),
                cost_per_million_tokens=float(entry.top_k_configs["cost_per_million_tokens"]) * replica,
            )
            nodes[node_id].devices.append(device_info)

            config.ttft += device_info.ttft
            config.throughput_per_user += device_info.throughput_per_user
            config.e2e_latency += device_info.e2e_latency
            config.error_rate += device_info.error_rate
            config.replica += replica

        num_workers = len(valid_combination[0])
        config.ttft /= num_workers
        config.throughput_per_user /= num_workers
        config.e2e_latency /= num_workers
        config.error_rate /= num_workers
        config.nodes = list(nodes.values())

        return config if len(config.nodes) else None

    def get_deployment_configs(
        self,
        request: DeploymentConfigurationRequest,
        session: Optional[Session] = None,
    ) -> DeploymentConfigurationResponse:
        if request.feedback:
            try:
                SimulationResultsCRUD().update_feedback(request.feedback, session)
            except Exception:
                return ErrorResponse(message="Failed to update feedback", code=500)

        results, total_count = SimulationResultsCRUD().fetch_topk_configs_by_cluster(
            workflow_id=request.workflow_id,
            cluster_id=request.cluster_id,
            error_rate_threshold=request.error_rate_threshold,
            limit=1,
            skip=0,
            session=session,
        )

        config = None

        for page in range(1, total_count + 1):
            for result in results:
                config = self.optimal_search_deployment_config(result, request.concurrency)

            if config is not None:
                break

            results, _ = SimulationResultsCRUD().fetch_topk_configs_by_cluster(
                workflow_id=request.workflow_id,
                cluster_id=request.cluster_id,
                error_rate_threshold=request.error_rate_threshold,
                limit=1,
                skip=page,
                session=session,
            )

        return (
            config
            if config is not None
            else ErrorResponse(
                message="No deployment configuration found",
                code=400,
            )
        )
