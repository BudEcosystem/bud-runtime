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
        return SimulationService.get_topk_engine_configs(**kwargs)

    @dapr_workflow.register_activity
    @staticmethod
    def get_topk_proprietary_engine_configs(ctx: wf.WorkflowActivityContext, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Get top-k proprietary engine configurations."""
        return SimulationService.get_topk_proprietary_engine_configs(**kwargs)

    @dapr_workflow.register_activity
    @staticmethod
    def get_topk_quantization_engine_configs(
        ctx: wf.WorkflowActivityContext, kwargs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get top-k quantization engine configurations."""
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

        try:
            parallel_tasks = [
                ctx.call_activity(
                    method,
                    input={
                        "device_config": {
                            **deepcopy(device),
                            "cluster_id": cluster["id"],
                            "node_id": node["id"],
                            "node_name": node["name"],
                        },
                        **request.model_dump(mode="json"),
                        "engine_name": engine_device_combo["engine_name"],
                        "engine_image": engine_device_combo["image"],
                    },
                )
                for cluster in cluster_info
                for node in cluster.get("nodes", [])
                for device in node.get("devices", [])
                for engine_device_combo in compatible_engines
                if device["type"] == engine_device_combo["device"]
            ]
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
        logger.info("Is workflow replaying: %s", ctx.is_replaying)

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
            eta=SimulationService.get_eta(current_step="validation", cluster_count=1),
            target_topic_name=request.source_topic,
            target_name=request.source,
        )
        return response
