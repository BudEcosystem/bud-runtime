import uuid
from copy import deepcopy
from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple

import dapr.ext.workflow as wf
from budmicroframe.commons import logging
from budmicroframe.commons.constants import WorkflowStatus
from budmicroframe.commons.schemas import NotificationContent, NotificationRequest, WorkflowStep
from budmicroframe.shared.dapr_workflow import DaprWorkflow

from .schemas import ClusterMetrics, ClusterRecommendationRequest, ClusterRecommendationResponse
from .services import SimulationService


logger = logging.get_logger(__name__)

dapr_workflow = DaprWorkflow()


def ensure_json_serializable(obj: Any) -> Any:
    """Ensure object is JSON serializable by converting non-serializable types."""
    if isinstance(obj, dict):
        return {k: ensure_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [ensure_json_serializable(item) for item in obj]
    elif isinstance(obj, tuple):
        return list(obj)
    elif isinstance(obj, bool):
        # Python bool is already JSON serializable, but ensure it's not a numpy bool
        return bool(obj)
    elif obj is None or isinstance(obj, (str, int, float)):
        return obj
    else:
        # Convert any other type to string
        return str(obj)


retry_policy = wf.RetryPolicy(
    first_retry_interval=timedelta(seconds=1),
    max_number_of_attempts=3,
    backoff_coefficient=2,
    max_retry_interval=timedelta(seconds=10),
    retry_timeout=timedelta(seconds=100),
)


class SimulationWorkflows:
    @dapr_workflow.register_activity
    @staticmethod
    def get_topk_engine_configs(ctx: wf.WorkflowActivityContext, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Get top-k engine configurations."""
        # Convert simulation_method string back to enum if present
        if "simulation_method" in kwargs and isinstance(kwargs["simulation_method"], str):
            from .schemas import SimulationMethod

            kwargs["simulation_method"] = SimulationMethod(kwargs["simulation_method"])
        return SimulationService.get_topk_engine_configs(**kwargs)

    @dapr_workflow.register_activity
    @staticmethod
    def get_topk_proprietary_engine_configs(ctx: wf.WorkflowActivityContext, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Get top-k proprietary engine configurations."""
        # Convert simulation_method string back to enum if present
        if "simulation_method" in kwargs and isinstance(kwargs["simulation_method"], str):
            from .schemas import SimulationMethod

            kwargs["simulation_method"] = SimulationMethod(kwargs["simulation_method"])
        return SimulationService.get_topk_proprietary_engine_configs(**kwargs)

    @dapr_workflow.register_activity
    @staticmethod
    def get_topk_quantization_engine_configs(
        ctx: wf.WorkflowActivityContext, kwargs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get top-k quantization engine configurations."""
        # Convert simulation_method string back to enum if present
        if "simulation_method" in kwargs and isinstance(kwargs["simulation_method"], str):
            from .schemas import SimulationMethod

            kwargs["simulation_method"] = SimulationMethod(kwargs["simulation_method"])
        return SimulationService.get_topk_quantization_engine_configs(**kwargs)

    @dapr_workflow.register_activity
    @staticmethod
    def get_available_clusters(ctx: wf.WorkflowActivityContext, kwargs: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get available clusters."""
        notification_request = NotificationRequest(**kwargs.pop("notification_request"))
        return SimulationService.get_available_clusters(**kwargs, notification_request=notification_request)

    @dapr_workflow.register_activity
    @staticmethod
    def get_compatible_engines(ctx: wf.WorkflowActivityContext, kwargs: Dict[str, Any]) -> List[Tuple[str, str]]:
        """Get compatible engines for the given configuration."""
        notification_request = NotificationRequest(**kwargs.pop("notification_request"))
        return SimulationService.get_compatible_engines(**kwargs, notification_request=notification_request)

    @dapr_workflow.register_workflow
    @staticmethod
    def get_topk_engine_configs_per_cluster(ctx: wf.WorkflowActivityContext, kwargs: Dict[str, Any]):
        """Get top-k engine configurations per cluster."""
        workflow_id = kwargs.pop("workflow_id")
        request = ClusterRecommendationRequest(**kwargs.pop("request"))
        cluster_info = kwargs.pop("cluster_info")
        compatible_engines = kwargs.pop("compatible_engines")
        notification_request = NotificationRequest(**kwargs.pop("notification_request"))
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
            SimulationWorkflows.get_topk_engine_configs
            if not request.is_proprietary_model
            else SimulationWorkflows.get_topk_proprietary_engine_configs
        )

        if request.is_quantization:
            method = SimulationWorkflows.get_topk_quantization_engine_configs

        # Determine the simulation method to use
        simulation_service = SimulationService()
        simulation_method = simulation_service.get_simulation_method(request)

        try:
            parallel_tasks = []
            devices_found = 0
            for cluster in cluster_info:
                cluster_id = cluster.get("id", "unknown")
                nodes = cluster.get("nodes", [])
                if cluster_id == "953b141f-7915-4187-9504-a3790e4a3c":
                    logger.info(f"Processing target cluster {cluster_id} with {len(nodes)} nodes")

                for node in nodes:
                    devices = node.get("devices", [])
                    if cluster_id == "953b141f-7915-4187-9504-a3790e4a3c":
                        logger.info(f"  Node {node.get('id')} has {len(devices)} devices")

                    for device in devices:
                        device_type = device.get("type", "unknown")
                        if cluster_id == "953b141f-7915-4187-9504-a3790e4a3c":
                            logger.info(
                                f"    Device: type={device_type}, model={device.get('model')}, memory={device.get('memory')}MB"
                            )

                        for engine_device_combo in compatible_engines:
                            if device_type.lower() == engine_device_combo["device"].lower():
                                devices_found += 1
                                # Prepare device config with proper memory conversion
                                device_config = deepcopy(device)

                                # Convert memory from MB to GB if needed
                                if "memory" in device_config and "mem_per_GPU_in_GB" not in device_config:
                                    device_config["mem_per_GPU_in_GB"] = device_config["memory"] / 1024.0

                                # Add cluster and node info
                                device_config.update(
                                    {
                                        "cluster_id": cluster_id,
                                        "node_id": node["id"],
                                        "node_name": node["name"],
                                    }
                                )

                                if cluster_id == "953b141f-7915-4187-9504-a3790e4a3c":
                                    logger.info(
                                        f"    Creating task for engine={engine_device_combo['engine_name']}, device_memory_gb={device_config.get('mem_per_GPU_in_GB', 0):.2f}"
                                    )

                                task = ctx.call_activity(
                                    method,
                                    input=ensure_json_serializable(
                                        {
                                            "device_config": device_config,
                                            **request.model_dump(mode="json"),
                                            "engine_name": engine_device_combo["engine_name"],
                                            "engine_image": engine_device_combo["image"],
                                            "simulation_method": simulation_method.value,
                                        }
                                    ),
                                )
                                parallel_tasks.append(task)

            logger.info(
                f"Created {len(parallel_tasks)} tasks for {devices_found} devices across {len(cluster_info)} clusters"
            )
            results = yield wf.when_all(parallel_tasks)  # type: ignore

            notification_req.payload.content = NotificationContent(
                title="Generated best configurations for each cluster",
                message="All performance metrics are estimated",
                status=WorkflowStatus.COMPLETED,
            )
            dapr_workflow.publish_notification(
                workflow_id=workflow_id,
                notification=notification_req,
                target_topic_name=request.source_topic,
                target_name=request.source,
            )
            return list(results)

        except Exception as e:
            # Extract meaningful error message from exception
            error_detail = str(e)
            if "cannot run on any of the" in error_detail and "available device(s)" in error_detail:
                # Model doesn't fit on any device
                fix_message = "Fix: Use a smaller model or add devices with more memory"
            elif "No valid configurations found" in error_detail:
                fix_message = "Fix: Model requires more memory than available on devices"
            else:
                fix_message = (
                    f"Fix: {error_detail[:100]}" if len(error_detail) < 100 else "Fix: Check logs for details"
                )

            notification_req.payload.content = NotificationContent(
                title="Failed to generate best configurations",
                message=fix_message,
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

    @dapr_workflow.register_activity
    @staticmethod
    def rank_configs(ctx: wf.WorkflowActivityContext, kwargs: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Rank configurations based on performance metrics."""
        notification_request = NotificationRequest(**kwargs.pop("notification_request"))
        request = ClusterRecommendationRequest(**kwargs.pop("request"))
        return SimulationService().rank_configs(
            request=request,
            notification_request=notification_request,
            serialize=True,
            **kwargs,
        )

    @dapr_workflow.register_workflow
    @staticmethod
    def run_simulation(ctx: wf.DaprWorkflowContext, payload: Dict[str, Any]):
        """Run the simulation workflow."""
        workflow_name = "get_cluster_recommendations"
        workflow_id = ctx.instance_id

        cluster_id = payload.get("cluster_id")
        request = ClusterRecommendationRequest(**payload)

        notification_request = NotificationRequest.from_cloud_event(
            cloud_event=request,
            name=workflow_name,
            workflow_id=workflow_id,
        )
        notification_request_dict = notification_request.model_dump(mode="json")
        response = ClusterRecommendationResponse(workflow_id=workflow_id, recommendations=[])

        cluster_info = yield ctx.call_activity(
            SimulationWorkflows.get_available_clusters,
            input={
                "workflow_id": workflow_id,
                "notification_request": notification_request_dict,
                "target_topic_name": request.source_topic,
                "target_name": request.source,
                "cluster_id": cluster_id,
            },
            retry_policy=retry_policy,
        )
        compatible_engines = yield ctx.call_activity(
            SimulationWorkflows.get_compatible_engines,
            input={
                "workflow_id": workflow_id,
                "pretrained_model_uri": request.pretrained_model_uri,
                "cluster_info": cluster_info,
                "notification_request": notification_request_dict,
                "target_topic_name": request.source_topic,
                "target_name": request.source,
                "proprietary_only": request.is_proprietary_model,
                "cluster_id": cluster_id,
            },
            retry_policy=retry_policy,
        )

        topk_engine_configs = yield ctx.call_child_workflow(
            SimulationWorkflows.get_topk_engine_configs_per_cluster,
            input={
                "workflow_id": workflow_id,
                "request": payload,
                "compatible_engines": compatible_engines,
                "cluster_info": cluster_info,
                "notification_request": notification_request_dict,
                "cluster_id": cluster_id,
            },
            retry_policy=retry_policy,
        )
        recommendations = yield ctx.call_activity(
            SimulationWorkflows.rank_configs,
            input={
                "workflow_id": workflow_id,
                "request": payload,
                "topk_engine_configs": topk_engine_configs,
                "notification_request": notification_request_dict,
                "cluster_id": cluster_id,
            },
            retry_policy=retry_policy,
        )

        response.recommendations = list(map(ClusterMetrics.model_validate, recommendations))

        notification_request.payload.event = "results"
        notification_request.payload.content = NotificationContent(
            title="Deployment Recommendation Results",
            message="The deployment recommendation results are ready",
            result=response.model_dump(mode="json"),
            status=WorkflowStatus.COMPLETED,
        )
        dapr_workflow.publish_notification(
            workflow_id=workflow_id,
            notification=notification_request,
            target_topic_name=request.source_topic,
            target_name=request.source,
        )

        return response.model_dump(mode="json")

    def __call__(self, request: ClusterRecommendationRequest, workflow_id: Optional[str] = None):
        """Schedule and execute the simulation workflow."""
        response = dapr_workflow.schedule_workflow(
            workflow_name="run_simulation",
            workflow_input=request.model_dump(mode="json"),
            workflow_id=str(workflow_id or uuid.uuid4()),
            workflow_steps=[
                WorkflowStep(
                    id="validation",
                    title="Identifying compatibles clusters",
                    description="Ensure all requirements and runtime compatibility are met",
                ),
                WorkflowStep(
                    id="performance_estimation",
                    title="Generating best configuration for each cluster",
                    description="Analyze and estimate the optimal performance for each cluster",
                ),
                WorkflowStep(
                    id="ranking",
                    title="Ranking the cluster based on performance",
                    description="Rank the clusters to find the best configuration",
                ),
            ],
            eta=SimulationService.get_eta(
                current_step="validation", cluster_count=1, simulation_method=SimulationService.get_simulation_method()
            ),
            target_topic_name=request.source_topic,
            target_name=request.source,
        )
        return response
