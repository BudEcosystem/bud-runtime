import uuid
from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple

import dapr.ext.workflow as wf
from budmicroframe.commons import logging
from budmicroframe.commons.constants import WorkflowStatus
from budmicroframe.commons.schemas import NotificationContent, NotificationRequest, WorkflowStep
from budmicroframe.shared.dapr_workflow import DaprWorkflow

from .schemas import ClusterMetrics, ClusterRecommendationRequest, ClusterRecommendationResponse
from .services import SimulationService, calculate_available_gpu_memory


logger = logging.get_logger(__name__)

dapr_workflow = DaprWorkflow()


def _normalize_device_type(device_type: str) -> str:
    """Normalize device type to generic type for matching.
    
    Maps specific device type variants to their generic types:
    - cpu_high, cpu_low -> cpu
    - cuda -> cuda  
    - rocm -> rocm
    
    Args:
        device_type: The device type string (e.g., 'cpu_high', 'CUDA', 'cpu')
        
    Returns:
        Normalized device type in lowercase (e.g., 'cpu', 'cuda', 'rocm')
    """
    device_type_lower = device_type.lower()
    
    # Map CPU variants to generic 'cpu'
    if device_type_lower.startswith('cpu'):
        return 'cpu'
    
    # Map other device types to their base type
    # rocm variants, cuda variants, etc.
    return device_type_lower


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
            # Step 1: Create tasks per cluster to maintain cluster separation
            parallel_tasks = []
            task_count = 0

            for cluster in cluster_info:
                cluster_id = cluster.get("id")
                logger.debug(f"Processing cluster {cluster_id}")

                # Analyze topology for this specific cluster
                single_cluster_list = [cluster]
                cluster_topology = SimulationService.analyze_cluster_topology(single_cluster_list)
                logger.info(
                    f"Cluster {cluster_id} topology: {cluster_topology['total_nodes']} nodes, "
                    f"{cluster_topology['total_cluster_devices']} total devices"
                )

                # Group devices by type within THIS cluster only
                logger.debug(f"Grouping devices by type for cluster {cluster_id}")

                # Extract user's hardware mode preference for device filtering
                user_hardware_mode = (
                    request.hardware_mode.value if hasattr(request.hardware_mode, "value") else request.hardware_mode
                )

                device_groups = SimulationService._group_devices_by_type_across_cluster(
                    single_cluster_list, cluster_topology, user_hardware_mode
                )

                # Log device groups for this cluster
                for device_type, group in device_groups.items():
                    logger.debug(
                        f"Cluster {cluster_id} - Device group {device_type}: "
                        f"{group.get('total_nodes_with_device', 0)} nodes, "
                        f"max {group.get('max_devices_per_node', 0)} devices/node"
                    )

                # Create tasks for each device type in THIS cluster
                for device_type, device_group in device_groups.items():
                    # Skip if no devices available
                    total_available = sum(device_group.get("node_distribution", {}).values())
                    if total_available <= 0:
                        logger.warning(
                            f"Cluster {cluster_id}: Skipping device type {device_type}: no available devices"
                        )
                        continue

                    for engine_device_combo in compatible_engines:
                        # Normalize both device types for comparison (e.g., cpu_high -> cpu, CPU -> cpu)
                        if _normalize_device_type(engine_device_combo["device"]) == _normalize_device_type(device_type):
                            task_count += 1

                            # Get representative device for specs (use first device)
                            if not device_group.get("devices"):
                                logger.warning(
                                    f"Cluster {cluster_id}: No devices in group for {device_type}, skipping"
                                )
                                continue

                            representative_device = device_group["devices"][0].copy()

                            # Create cluster-aware device configuration - ensure cluster_id is set correctly
                            cluster_device_config = {
                                **representative_device,  # Device specs first
                                # Override with cluster-specific values (these take precedence)
                                "device_type": device_type,
                                # Ensure we have the device identification fields with fallbacks
                                "device_model": representative_device.get(
                                    "raw_name", representative_device.get("name", "")
                                ),
                                "device_name": representative_device.get("name", ""),
                                "raw_name": representative_device.get(
                                    "raw_name", representative_device.get("name", "")
                                ),
                                "cluster_id": cluster_id,  # Use the specific cluster ID
                                "total_devices": total_available,
                                "node_distribution": device_group.get("node_distribution", {}),
                                "devices_by_node": device_group.get("devices_by_node", {}),
                                "max_devices_per_node": device_group.get("max_devices_per_node", 0),
                                "total_nodes_with_device": device_group.get("total_nodes_with_device", 0),
                                "cluster_topology": cluster_topology,
                                "available_count": total_available,  # Ensure this is set for optimizer
                            }

                            # Convert memory from MB to GB if needed
                            if "memory" in cluster_device_config and "mem_per_GPU_in_GB" not in cluster_device_config:
                                cluster_device_config["mem_per_GPU_in_GB"] = cluster_device_config["memory"] / 1024.0

                            # Calculate available memory based on user's hardware mode
                            user_hardware_mode = (
                                request.hardware_mode.value
                                if hasattr(request.hardware_mode, "value")
                                else request.hardware_mode
                            )

                            logger.debug(
                                f"Workflow memory override check: user_hardware_mode={user_hardware_mode}, "
                                f"device_type={device_type}, "
                                f"representative_device has mem_per_GPU_in_GB={representative_device.get('mem_per_GPU_in_GB')}, "
                                f"memory_allocated_gb={representative_device.get('memory_allocated_gb')}"
                            )

                            if user_hardware_mode == "shared":
                                # For shared mode, use unutilized memory (100% of available, no safety margin)
                                total_memory_gb, memory_allocated_gb, available_memory_gb = (
                                    calculate_available_gpu_memory(cluster_device_config)
                                )

                                logger.info(
                                    f"Shared mode GPU memory calculation for {device_type}: "
                                    f"total={total_memory_gb:.2f}GB, allocated={memory_allocated_gb:.2f}GB, "
                                    f"available={available_memory_gb:.2f}GB (no safety margin applied)"
                                )

                                # Override memory fields with available memory
                                cluster_device_config["mem_per_GPU_in_GB"] = available_memory_gb
                                cluster_device_config["memory_gb"] = available_memory_gb
                                cluster_device_config["available_memory_gb"] = available_memory_gb
                                cluster_device_config["total_memory_gb_original"] = total_memory_gb

                            logger.info(
                                f"Creating task for cluster {cluster_id}, {device_type} with engine "
                                f"{engine_device_combo['engine_name']}: total_devices={total_available}, "
                                f"max_tp={cluster_device_config['max_devices_per_node']}, "
                                f"max_pp={cluster_device_config['total_nodes_with_device']}"
                            )

                            task = ctx.call_activity(
                                method,
                                input=ensure_json_serializable(
                                    {
                                        "device_config": cluster_device_config,
                                        **request.model_dump(mode="json"),
                                        "engine_name": engine_device_combo["engine_name"],
                                        "engine_image": engine_device_combo["image"],
                                        "engine_version": engine_device_combo.get("version"),
                                        "tool_calling_parser_type": engine_device_combo.get(
                                            "tool_calling_parser_type"
                                        ),
                                        "reasoning_parser_type": engine_device_combo.get("reasoning_parser_type"),
                                        "architecture_family": engine_device_combo.get("architecture_family"),
                                        "chat_template": engine_device_combo.get("chat_template"),
                                        "supports_lora": engine_device_combo.get("supports_lora", False),
                                        "supports_pipeline_parallelism": engine_device_combo.get(
                                            "supports_pipeline_parallelism", False
                                        ),
                                        "simulation_method": simulation_method.value,
                                    }
                                ),
                            )
                            parallel_tasks.append(task)

            logger.info(f"Created {len(parallel_tasks)} tasks across {len(cluster_info)} clusters")

            # Check if no tasks were created - this means no devices are available
            if len(parallel_tasks) == 0:
                raise ValueError(
                    "No devices available for simulation. All devices were skipped because: "
                    "(1) devices have 0 available_count (already in use or unavailable), or "
                    "(2) no compatible device types found for the selected model. "
                    "Please check cluster health and device availability."
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

            # Flatten results since get_topk_engine_configs may return lists for cluster-wide configs
            flattened_results = []
            for result in results:
                if isinstance(result, list):
                    flattened_results.extend(result)
                else:
                    flattened_results.append(result)

            return flattened_results

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
                    f"Fix: {error_detail[:100]}"
                    if len(error_detail) < 100
                    else "Fix: use smaller model or add more devices."
                )

            notification_req.payload.content = NotificationContent(
                title="No suitable device found for deployment",
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
                "model_uri": request.model_uri,  # Pass the cloud/HF URI
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
