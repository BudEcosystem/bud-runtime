import asyncio
import json
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from typing import Any, Optional, Union

import dapr.ext.workflow as wf
import requests
from budmicroframe.commons import logging
from budmicroframe.commons.config import app_settings
from budmicroframe.commons.constants import WorkflowStatus
from budmicroframe.commons.exceptions import ClientException
from budmicroframe.commons.schemas import (
    ErrorResponse,
    NotificationContent,
    NotificationRequest,
    SuccessResponse,
    WorkflowMetadataResponse,
    WorkflowStep,
)
from budmicroframe.shared.dapr_service import DaprService, DaprServiceCrypto
from budmicroframe.shared.dapr_workflow import DaprWorkflow
from budmicroframe.shared.psql_service import DBSession
from dapr.clients import DaprClient
from pydantic import ValidationError

from ..benchmark_ops.models import BenchmarkCRUD, BenchmarkResultCRUD, BenchmarkResultSchema, BenchmarkSchema
from ..benchmark_ops.schemas import LLMBenchmarkResultSchema
from ..cluster_ops.schemas import VerifyClusterConnection
from ..cluster_ops.workflows import RegisterClusterWorkflow
from ..commons.constants import BenchmarkStatusEnum
from ..commons.exceptions import BenchmarkResultSaveError
from ..commons.utils import (
    check_workflow_status_in_statestore,
    save_workflow_status_in_statestore,
    update_workflow_data_in_statestore,
)
from .crud import WorkerInfoDataManager
from .handler import DeploymentHandler, SimulatorHandler
from .models import WorkerInfo as WorkerInfoModel
from .performance import DeploymentPerformance
from .schemas import (
    DeleteDeploymentRequest,
    DeleteNamespaceRequest,
    DeleteWorkerActivityRequest,
    DeleteWorkerRequest,
    DeploymentStatusEnum,
    DeploymentWorkflowRequest,
    DeployModelWorkflowResult,
    RunPerformanceBenchmarkRequest,
    TransferModelRequest,
    UpdateModelTransferStatusRequest,
    VerifyDeploymentHealthRequest,
    WorkerInfo,
    WorkflowRunPerformanceBenchmarkRequest,
)
from .services import DeploymentService, WorkerInfoService


logger = logging.get_logger(__name__)

dapr_workflows = DaprWorkflow()

retry_policy = wf.RetryPolicy(
    first_retry_interval=timedelta(seconds=1),
    max_number_of_attempts=3,
    backoff_coefficient=2,
    max_retry_interval=timedelta(seconds=10),
    retry_timeout=timedelta(seconds=100),
)


@dapr_workflows.register_activity
def delete_namespace(ctx: wf.WorkflowActivityContext, delete_namespace_request: str) -> dict:
    """Delete the namespace."""
    logger = logging.get_logger("DeleteNamespace")
    workflow_id = ctx.workflow_id
    task_id = ctx.task_id
    logger.info(f"Deleting namespace for workflow_id: {workflow_id} and task_id: {task_id}")
    delete_namespace_request_json = DeleteNamespaceRequest.model_validate_json(delete_namespace_request)
    response: Union[SuccessResponse, ErrorResponse]
    try:
        namespace = delete_namespace_request_json.namespace
        deployment_handler = DeploymentHandler(config=delete_namespace_request_json.cluster_config)
        deployment_handler.delete(namespace=namespace, platform=delete_namespace_request_json.platform)
        response = SuccessResponse(
            message=f"Namespace {namespace} deleted successfully", param={"namespace": namespace}
        )
    except Exception as e:
        error_msg = f"Error deleting namespace for workflow_id: {workflow_id} and task_id: {task_id}, error: {e}"
        logger.error(error_msg)
        response = ErrorResponse(
            message="Namespace deletion failed", code=HTTPStatus.BAD_REQUEST.value, param={"namespace": namespace}
        )
    return response.model_dump(mode="json")


def merge_deploy_config(deploy_config, current_deploy_config):
    """Merge two deployment configurations, combining devices and summing replicas.

    Args:
        deploy_config: New deployment configuration
        current_deploy_config: Existing deployment configuration

    Returns:
        list: Merged configuration with combined devices and summed replicas

    Example Input:
        deploy_config = [
            {
                "id": "node1",
                "name": "worker1",
                "devices": [{"name": "cpu1", "replicas": 1}]
            }
        ]
        current_deploy_config = [
            {
                "id": "node1",
                "name": "worker1",
                "devices": [{"name": "cpu1", "replicas": 2}]
            }
        ]
    """
    node_info = {
        config["name"]: config["id"] for configs in (deploy_config, current_deploy_config) for config in configs
    }

    # Initialize final config with deep copy of first config
    from copy import deepcopy

    final_config_dict = {config["name"]: deepcopy(config["devices"]) for config in deploy_config}

    for config in current_deploy_config:
        node_name = config["name"]
        if node_name not in final_config_dict:
            final_config_dict[node_name] = deepcopy(config["devices"])
            for device in final_config_dict[node_name]:
                device["name"] = to_k8s_label(device["name"])
            continue
        # Create device name to index mapping for faster lookups
        # Assuming devices are unique by name
        device_indices = {device["name"]: idx for idx, device in enumerate(final_config_dict[node_name])}
        # Update or append devices
        for device in config["devices"]:
            device["name"] = to_k8s_label(device["name"])
            if device["name"] in device_indices:
                # Update existing device replicas
                final_config_dict[node_name][device_indices[device["name"]]]["replica"] += device["replica"]
            else:
                # Add new device
                final_config_dict[node_name].append(deepcopy(device))

    return [
        {"name": node_name, "id": node_info[node_name], "devices": devices}
        for node_name, devices in final_config_dict.items()
    ]


def to_k8s_label(label: str):
    """Convert a label to a valid k8s label."""
    # Convert to lowercase
    label = label.lower()
    # Replace invalid characters with a hyphen
    label = re.sub(r"[^a-z0-9]+", "-", label)
    # Ensure it starts and ends with an alphanumeric character
    label = re.sub(r"^-+|-+$", "", label)
    return label


def save_benchmark_result(result: dict[str, Any]):
    """Save the benchmark result to the database."""
    logger.info(f"benchmark_result received from llm-benchmark : {result}")
    benchmark_id = result["bud_cluster_benchmark_id"]
    try:
        benchmark_result = LLMBenchmarkResultSchema.model_validate(result["result"])
    except ValidationError as e:
        logger.error(f"Error validating benchmark result: {e}")
        with BenchmarkCRUD() as crud:
            crud.update(
                data={"status": BenchmarkStatusEnum.FAILED, "reason": f"Unable to save benchmark result : {result}"},
                conditions={"id": benchmark_id},
            )
        raise BenchmarkResultSaveError("Unable to save benchmark result due to validation error") from None
    with BenchmarkResultCRUD() as crud:
        crud.insert(
            BenchmarkResultSchema(
                benchmark_id=benchmark_id,
                **benchmark_result.model_dump(mode="json"),
            )
        )


def save_benchmark_request_metrics(budapp_benchmark_id, request_metrics: list[dict]):
    """Send request to budapp for saving benchmark request metrics."""
    add_benchmark_request_metrics_endpoint = (
        f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_app_id}/method/benchmark/request-metrics"
    )

    try:
        with requests.Session() as session:
            for metric in request_metrics:
                metric["benchmark_id"] = str(budapp_benchmark_id)
            response = session.post(
                add_benchmark_request_metrics_endpoint, json={"metrics": request_metrics}, timeout=30
            )
            response_data = response.json()

        if response.status_code >= 400 or response_data.get("object") == "error":
            raise ClientException("Unable to save benchmark request metrics")
    except ClientException as e:
        raise e
    except Exception as e:
        logger.error(f"Failed to save benchmark request metrics: {e}")
        raise ClientException("Unable to save benchmark request metrics to budapp") from e


class CreateDeploymentWorkflow:
    @dapr_workflows.register_activity
    @staticmethod
    def transfer_model(ctx: wf.WorkflowActivityContext, transfer_model_request: str):
        """Transfer the model to the cluster."""
        logger = logging.get_logger("TransferModel")
        workflow_id = ctx.workflow_id
        task_id = ctx.task_id
        logger.info(f"Transferring model for workflow_id: {workflow_id} and task_id: {task_id}")
        transfer_model_request_json = TransferModelRequest.model_validate_json(transfer_model_request)
        response: Union[SuccessResponse, ErrorResponse]
        try:
            # TODO: add delete model logic here if workflow is terminated
            # Description: If the workflow is terminated,
            # delete the model from the cluster only if it is not associated with any other deployment on the same cluster
            cluster_config = json.loads(transfer_model_request_json.cluster_config)
            model = transfer_model_request_json.model
            endpoint_name = transfer_model_request_json.endpoint_name
            node_list = transfer_model_request_json.simulator_config
            platform = transfer_model_request_json.platform
            existing_deployment_namespace = transfer_model_request_json.existing_deployment_namespace
            logger.info(f"Transferring model id: {model}")

            workflow_status = check_workflow_status_in_statestore(workflow_id)
            if workflow_status:
                return workflow_status

            deployment_handler = DeploymentHandler(config=cluster_config)

            status, namespace = deployment_handler.transfer_model(
                model_uri=model,
                endpoint_name=endpoint_name,
                node_list=node_list,
                platform=platform,
                namespace=existing_deployment_namespace,
                default_storage_class=transfer_model_request_json.default_storage_class,
                default_access_mode=transfer_model_request_json.default_access_mode,
                storage_size_gb=transfer_model_request_json.storage_size_gb,
            )
            if status is not None:
                workflow_status = check_workflow_status_in_statestore(workflow_id)
                if workflow_status:
                    # cleanup the namespace if workflow is terminated
                    deployment_handler.delete(namespace=namespace, platform=platform)
                    return workflow_status
                response = SuccessResponse(
                    message="Model transferred successfully",
                    param={"status": status, "namespace": namespace},
                )
            else:
                deployment_handler.delete(namespace=namespace, platform=platform)
                response = ErrorResponse(message="Failed to transfer model", code=HTTPStatus.BAD_REQUEST.value)
        except Exception as e:
            error_msg = f"Error transferring model for workflow_id: {workflow_id} and task_id: {task_id}, error: {e}"
            logger.error(error_msg)
            response = ErrorResponse(message="Transfer model failed", code=HTTPStatus.BAD_REQUEST.value)
        return response.model_dump(mode="json")

    @dapr_workflows.register_activity
    @staticmethod
    def deploy_engine(ctx: wf.WorkflowActivityContext, deploy_engine_request: str):
        """Deploy the engine to the cluster."""
        logger = logging.get_logger("DeployEngine")
        workflow_id = ctx.workflow_id
        task_id = ctx.task_id
        logger.info(f"Deploying engine for workflow_id: {workflow_id} and task_id: {task_id}")
        deploy_engine_request_json = DeploymentWorkflowRequest.model_validate_json(deploy_engine_request)
        response: Union[SuccessResponse, ErrorResponse]
        try:
            cluster_config = json.loads(deploy_engine_request_json.cluster_config)
            node_list = deploy_engine_request_json.simulator_config
            endpoint_name = deploy_engine_request_json.endpoint_name
            hf_token = deploy_engine_request_json.hf_token
            namespace = deploy_engine_request_json.namespace
            ingress_url = deploy_engine_request_json.ingress_url
            platform = deploy_engine_request_json.platform
            add_worker = deploy_engine_request_json.add_worker
            podscaler = deploy_engine_request_json.podscaler
            if add_worker:
                with DaprService() as dapr_service:
                    deploy_config = dapr_service.get_state(
                        store_name=app_settings.statestore_name,
                        key=f"deploy_config_{deploy_engine_request_json.existing_deployment_namespace}",
                    )
                    deploy_config = json.loads(deploy_config.data) if deploy_config.data else []
                node_list = merge_deploy_config(deploy_config, node_list)
            logger.info(f"Node list local model: {node_list}")
            deployment_handler = DeploymentHandler(config=cluster_config)
            workflow_status = check_workflow_status_in_statestore(workflow_id)
            if workflow_status:
                return workflow_status
            # Get parser types from workflow request (fetched from BudSim)
            tool_calling_parser = getattr(deploy_engine_request_json, "tool_calling_parser_type", None)
            reasoning_parser = getattr(deploy_engine_request_json, "reasoning_parser_type", None)
            chat_template = getattr(deploy_engine_request_json, "chat_template", None)

            status, namespace, deployment_url, number_of_nodes, node_list = deployment_handler.deploy(
                node_list=node_list,
                endpoint_name=endpoint_name,
                hf_token=hf_token,
                namespace=namespace,
                ingress_url=ingress_url,
                platform=platform,
                add_worker=add_worker,
                podscaler=podscaler,
                input_tokens=deploy_engine_request_json.input_tokens,
                output_tokens=deploy_engine_request_json.output_tokens,
                tool_calling_parser_type=tool_calling_parser,
                reasoning_parser_type=reasoning_parser,
                enable_tool_calling=deploy_engine_request_json.enable_tool_calling,
                enable_reasoning=deploy_engine_request_json.enable_reasoning,
                chat_template=chat_template,
                default_storage_class=getattr(deploy_engine_request_json, "default_storage_class", None),
                default_access_mode=getattr(deploy_engine_request_json, "default_access_mode", None),
            )
            update_workflow_data_in_statestore(
                str(workflow_id),
                {
                    "namespace": namespace,
                    "cluster_config_dict": cluster_config,
                },
            )
            if status is not None:
                workflow_status = check_workflow_status_in_statestore(workflow_id)
                if workflow_status:
                    # cleanup the namespace if workflow is terminated
                    deployment_handler.delete(namespace=namespace, platform=platform)
                    return workflow_status
                response = SuccessResponse(
                    message="Engine deployed successfully",
                    param={
                        "status": status,
                        "namespace": namespace,
                        "endpoint_name": endpoint_name,
                        "deployment_url": deployment_url,
                        "number_of_nodes": number_of_nodes,
                        "deploy_config": node_list,
                    },
                )
            else:
                response = ErrorResponse(message="Failed to deploy runtime", code=HTTPStatus.BAD_REQUEST.value)
        except Exception as e:
            import traceback

            logger.error(traceback.format_exc())
            error_msg = f"Error deploying engine for workflow_id: {workflow_id} and task_id: {task_id}, error: {e}"
            logger.error(error_msg)
            response = ErrorResponse(message="Failed to deploy runtime", code=HTTPStatus.BAD_REQUEST.value)
        return response.model_dump(mode="json")

    @dapr_workflows.register_activity
    @staticmethod
    def verify_deployment_health(ctx: wf.WorkflowActivityContext, verify_deployment_health_request: str):
        """Verify the deployment health."""
        logger = logging.get_logger("VerifyDeploymentHealth")
        workflow_id = ctx.workflow_id
        task_id = ctx.task_id
        verify_deployment_health_request_json = VerifyDeploymentHealthRequest.model_validate_json(
            verify_deployment_health_request
        )
        logger.info(
            f"Verifying engine health for {verify_deployment_health_request_json.namespace} workflow_id: {workflow_id} and task_id: {task_id}"
        )
        add_worker = verify_deployment_health_request_json.add_worker

        response: Union[SuccessResponse, ErrorResponse]
        try:
            deployment_handler = DeploymentHandler(  # noqa: F841
                config=json.loads(verify_deployment_health_request_json.cluster_config)
            )
            ingress_url = verify_deployment_health_request_json.ingress_url  # noqa: F841
            deployment_status = deployment_handler.get_deployment_status(
                verify_deployment_health_request_json.namespace,
                ingress_url,
                cloud_model=verify_deployment_health_request_json.cloud_model,
                platform=verify_deployment_health_request_json.platform,
                ingress_health=verify_deployment_health_request_json.ingress_health,
            )
            # Check deployment status - get_deployment_status now handles endpoint validation with retries
            if deployment_status["status"] == DeploymentStatusEnum.READY:
                # Supported endpoints are now included in deployment_status response
                supported_endpoints = deployment_status.get("supported_endpoints", {})
                logger.info(f"Supported endpoints: {supported_endpoints}")
                # Convert dict to list of supported endpoints (where value is True)
                supported_endpoints_list = [
                    endpoint for endpoint, supported in supported_endpoints.items() if supported
                ]
                if add_worker:
                    current_workers_info = deployment_status["worker_data_list"]
                    with DBSession() as session:
                        worker_info_filters = {
                            "cluster_id": verify_deployment_health_request_json.cluster_id,
                            "namespace": verify_deployment_health_request_json.namespace,
                        }
                        workers_info, _ = asyncio.run(
                            WorkerInfoDataManager(session).get_all_workers(filters=worker_info_filters)
                        )
                        workers_info_list = [
                            WorkerInfoModel(
                                cluster_id=verify_deployment_health_request_json.cluster_id,
                                namespace=verify_deployment_health_request_json.namespace,
                                **worker,
                                deployment_status=deployment_status["status"],
                                last_updated_datetime=datetime.now(timezone.utc),
                            )
                            for worker in current_workers_info
                        ]
                        _ = asyncio.run(
                            WorkerInfoService(session).update_worker_info(
                                workers_info_list, workers_info, verify_deployment_health_request_json.cluster_id
                            )
                        )
                response = SuccessResponse(
                    message="Engine health verified successfully",
                    param={**deployment_status, "supported_endpoints": supported_endpoints_list},
                )
            else:
                # Handle different failure types
                # if not add_worker:
                #     deployment_handler.delete(
                #         namespace=verify_deployment_health_request_json.namespace,
                #         platform=verify_deployment_health_request_json.platform,
                #     )

                if deployment_status["status"] == DeploymentStatusEnum.FAILED:
                    message = f"Engine deployment failed: {deployment_status['replicas']['reason']}"
                elif deployment_status["status"] == DeploymentStatusEnum.ENDPOINTS_FAILED:
                    message = f"Deployment endpoints failed to become ready within {app_settings.max_endpoint_retry_attempts * app_settings.endpoint_retry_interval} seconds"
                elif deployment_status["status"] == DeploymentStatusEnum.INGRESS_FAILED:
                    message = "Deployment ingress verification failed"
                else:
                    message = "Deployment verification failed"

                response = ErrorResponse(
                    message=message,
                    code=HTTPStatus.BAD_REQUEST.value,
                )
        except Exception as e:
            if not add_worker:
                deployment_handler = DeploymentHandler(  # noqa: F841
                    config=json.loads(verify_deployment_health_request_json.cluster_config)
                )
                deployment_handler.delete(
                    namespace=verify_deployment_health_request_json.namespace,
                    platform=verify_deployment_health_request_json.platform,
                )
            error_msg = (
                f"Error verifying engine health for workflow_id: {workflow_id} and task_id: {task_id}, error: {e}"
            )
            logger.error(error_msg)
            response = ErrorResponse(message="Engine health verification failed", code=HTTPStatus.BAD_REQUEST.value)
        return response.model_dump(mode="json")

    @dapr_workflows.register_activity
    @staticmethod
    def run_performance_benchmark(ctx: wf.WorkflowActivityContext, workflow_run_benchmark_request: str):
        """Execute the workflow to run the performance benchmark."""
        logger = logging.get_logger("RunPerformanceBenchmark")
        workflow_id = ctx.workflow_id
        task_id = ctx.task_id
        logger.info(f"Running performance benchmark for workflow_id: {workflow_id} and task_id: {task_id}")
        workflow_run_benchmark_request_json = WorkflowRunPerformanceBenchmarkRequest.model_validate_json(
            workflow_run_benchmark_request
        )
        namespace = workflow_run_benchmark_request_json.namespace
        # NOTE: For performance benchmark, we need to cleanup the namespace after the benchmark is done
        cleanup_namespace = workflow_run_benchmark_request_json.cleanup_namespace
        run_benchmark_request_json = workflow_run_benchmark_request_json.benchmark_request
        logger.info(f"Run benchmark for endpoint: {run_benchmark_request_json.deployment_url}")
        exception_occurred = False
        try:
            # request is for performance benchmark
            benchmark_id = None
            if cleanup_namespace:
                # TODO: insert benchmark in budcluster db
                with BenchmarkCRUD() as crud:
                    db_benchmark = crud.insert(
                        BenchmarkSchema(
                            benchmark_id=workflow_run_benchmark_request_json.benchmark_id,
                            cluster_id=workflow_run_benchmark_request_json.cluster_id,
                            user_id=workflow_run_benchmark_request_json.user_id,
                            model_id=workflow_run_benchmark_request_json.model_id,
                            model=workflow_run_benchmark_request_json.benchmark_request.model,
                            nodes=workflow_run_benchmark_request_json.nodes,
                            num_of_users=workflow_run_benchmark_request_json.benchmark_request.concurrency,
                            max_input_tokens=workflow_run_benchmark_request_json.benchmark_request.input_tokens,
                            max_output_tokens=workflow_run_benchmark_request_json.benchmark_request.output_tokens,
                            datasets=workflow_run_benchmark_request_json.benchmark_request.datasets,
                            status=BenchmarkStatusEnum.PROCESSING,
                        )
                    )
                    benchmark_id = db_benchmark.id
            deployment_performance = DeploymentPerformance(
                provider_type=workflow_run_benchmark_request_json.provider_type,
                deployment_name=namespace,
                model=run_benchmark_request_json.model,
                deployment_url=run_benchmark_request_json.deployment_url,
                concurrency=run_benchmark_request_json.concurrency,
                input_tokens=run_benchmark_request_json.input_tokens,
                output_tokens=run_benchmark_request_json.output_tokens,
                target_ttft=run_benchmark_request_json.target_ttft,
                target_e2e_latency=run_benchmark_request_json.target_e2e_latency,
                target_throughput_per_user=run_benchmark_request_json.target_throughput_per_user,
                datasets=run_benchmark_request_json.datasets,
                benchmark_id=benchmark_id,
                model_type=run_benchmark_request_json.model_type,
            )  # noqa: F841
            workflow_status = check_workflow_status_in_statestore(workflow_id)
            if workflow_status:
                return workflow_status
            benchmark_result = deployment_performance.run_performance_test()
            logger.debug(f"Benchmark result: {benchmark_result}")

            benchmark_result["bud_cluster_benchmark_id"] = benchmark_id
            if benchmark_result["benchmark_status"] and isinstance(benchmark_result["result"], dict):
                benchmark_result["result"]["deployment_url"] = run_benchmark_request_json.deployment_url
                workflow_status = check_workflow_status_in_statestore(workflow_id)
                if workflow_status:
                    # cleanup the namespace if workflow is terminated
                    deployment_handler = DeploymentHandler(
                        config=json.loads(workflow_run_benchmark_request_json.cluster_config)
                    )
                    deployment_handler.delete(namespace=workflow_run_benchmark_request_json.namespace)
                    return workflow_status

                if cleanup_namespace:
                    budapp_benchmark_id = workflow_run_benchmark_request_json.benchmark_id
                    save_benchmark_result(benchmark_result)
                    save_benchmark_request_metrics(
                        budapp_benchmark_id, benchmark_result["result"]["individual_responses"]
                    )
                    with BenchmarkCRUD() as crud:
                        crud.update(
                            data={"status": BenchmarkStatusEnum.SUCCESS},
                            conditions={"id": benchmark_id},
                        )
                response = SuccessResponse(message="Performance benchmark successful", param=benchmark_result)
            else:
                exception_occurred = True
                if cleanup_namespace:
                    # TODO: update benchmark status in db
                    with BenchmarkCRUD() as crud:
                        crud.update(
                            data={"status": BenchmarkStatusEnum.FAILED, "reason": benchmark_result["result"]},
                            conditions={"id": benchmark_id},
                        )
                response = ErrorResponse(message=benchmark_result["result"], code=HTTPStatus.BAD_REQUEST.value)
        except BenchmarkResultSaveError as e:
            exception_occurred = True
            response = ErrorResponse(message=e.message, code=e.status_code)
        except Exception as e:
            exception_occurred = True
            import traceback

            error_msg = f"Error running performance benchmark for workflow_id: {workflow_id} and task_id: {task_id}, error: {e}"
            logger.error(error_msg)
            logger.error(f"Traceback: {traceback.format_exc()}")
            response = ErrorResponse(message="Performance benchmark failed", code=HTTPStatus.BAD_REQUEST.value)
        finally:
            if exception_occurred or cleanup_namespace:
                deployment_handler = DeploymentHandler(
                    config=json.loads(workflow_run_benchmark_request_json.cluster_config)
                )
                deployment_handler.delete(
                    namespace=namespace,
                    platform=workflow_run_benchmark_request_json.platform,
                )
                logger.debug(f"Benchmark completed, namespace {namespace} cleaned up")
        return response.model_dump(mode="json")

    @dapr_workflows.register_workflow
    @staticmethod
    def create_deployment(ctx: wf.DaprWorkflowContext, deployment_request: str):
        """Execute the workflow to create a deployment."""
        logger = logging.get_logger("CreateDeployment")
        instance_id = str(ctx.instance_id)
        logger.info(f"Creating deployment for instance_id: {instance_id}")
        save_workflow_status_in_statestore(instance_id, WorkflowStatus.RUNNING.value)
        deployment_request_json = DeploymentWorkflowRequest.model_validate_json(deployment_request)

        workflow_name = "deploy_model"
        if deployment_request_json.existing_deployment_namespace is not None:
            workflow_name = "add_worker"
        elif deployment_request_json.is_performance_benchmark:
            workflow_name = "performance_benchmark"
        notification_request = NotificationRequest.from_cloud_event(
            cloud_event=deployment_request_json, name=workflow_name, workflow_id=instance_id
        )
        notification_req = notification_request.model_copy(deep=True)

        DeploymentService.publish_eta(
            notification_req, deployment_request_json, instance_id, "verify_cluster_connection"
        )

        # notify activity that deployment creating process is initiated
        notification_req.payload.event = "deployment_status"
        notification_req.payload.content = NotificationContent(
            title="Model deployment process is initiated",
            message=f"Model deployment process is initiated for simulator config : {deployment_request_json.simulator_config}",
            status=WorkflowStatus.STARTED,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=deployment_request_json.source_topic,
            target_name=deployment_request_json.source,
        )
        # yield ctx.call_activity(
        #     notify_activity,
        #     input=notification_activity_request.model_dump_json(),
        # )

        # fetch cluster details from db
        with DBSession() as session:
            db_cluster = asyncio.run(
                DeploymentService(session)._get_cluster(deployment_request_json.cluster_id, missing_ok=True)
            )
            if db_cluster is None:
                # notify activity that cluster verification failed
                notification_req.payload.event = "verify_cluster_connection"
                notification_req.payload.content = NotificationContent(
                    title="Cluster connection verification failed",
                    message="Cluster not found",
                    status=WorkflowStatus.FAILED,
                    primary_action="retry",
                )
                dapr_workflows.publish_notification(
                    workflow_id=instance_id,
                    notification=notification_req,
                    target_topic_name=deployment_request_json.source_topic,
                    target_name=deployment_request_json.source,
                )
                # yield ctx.call_activity(notify_activity, input=notification_activity_request.model_dump_json())
                return
            with DaprServiceCrypto() as dapr_service:
                configuration_decrypted = dapr_service.decrypt_data(db_cluster.configuration)

        deployment_request_json.cluster_config = configuration_decrypted
        deployment_request_json.ingress_url = db_cluster.ingress_url
        deployment_request_json.platform = db_cluster.platform

        # verify cluster connection
        verify_cluster_connection_request = VerifyClusterConnection(
            cluster_config=deployment_request_json.cluster_config,
            platform=deployment_request_json.platform,
        )
        verify_cluster_connection_result = yield ctx.call_activity(
            RegisterClusterWorkflow.verify_cluster_connection,
            input=verify_cluster_connection_request.model_dump_json(),
        )

        # if verify cluster connection is not successful
        if verify_cluster_connection_result.get("code", HTTPStatus.OK.value) != HTTPStatus.OK.value:
            # notify activity that cluster verification failed
            notification_req.payload.event = "verify_cluster_connection"
            notification_req.payload.content = NotificationContent(
                title="Cluster connection verification failed",
                message=verify_cluster_connection_result["message"],
                status=WorkflowStatus.FAILED,
                primary_action="retry",
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=deployment_request_json.source_topic,
                target_name=deployment_request_json.source,
            )
            # yield ctx.call_activity(notify_activity, input=notification_activity_request.model_dump_json())
            return

        # notify activity that cluster verification is successful
        notification_req.payload.event = "verify_cluster_connection"
        notification_req.payload.content = NotificationContent(
            title="Cluster connection verification successful",
            message=verify_cluster_connection_result["message"],
            status=WorkflowStatus.COMPLETED,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=deployment_request_json.source_topic,
            target_name=deployment_request_json.source,
        )
        # yield ctx.call_activity(notify_activity, input=notification_activity_request.model_dump_json())

        # notify activity ETA
        DeploymentService.publish_eta(
            notification_req, deployment_request_json, instance_id, "transfer_model_to_cluster"
        )

        # fetch simulator configuration
        try:
            if deployment_request_json.is_performance_benchmark and deployment_request_json.nodes:
                # TODO: perform validation of nodes
                simulator_config = []
                for node in deployment_request_json.nodes:
                    node_info = {
                        "id": node["id"],
                        "name": node["hostname"],
                        "devices": [
                            {
                                "name": node["hostname"],
                                "type": node["devices"][0]["type"],
                                "image": "aibrix/vllm-openai:v0.7.3.self.post1"
                                if node["devices"][0]["type"] == "cuda"
                                else "budimages.azurecr.io/budecosystem/bud-runtime-cpu:0.09",
                                "memory": 21722998784 if node["devices"][0]["type"] == "cuda" else 40762560000,
                                "num_cpus": -1 if node["devices"][0]["type"] == "cuda" else 1,
                                "replica": 2 if node["devices"][0]["type"] == "cuda" else 1,
                                "tp_size": 1,
                                "core_count": 4 if node["devices"][0]["type"] == "cuda" else 14,
                                "concurrency": 18 if node["devices"][0]["type"] == "cuda" else 100,
                                "args": {
                                    "model": deployment_request_json.model,
                                    "block-size": 32,
                                    "tensor-parallel-size": 1,
                                    "pipeline-parallel-size": 1,
                                    "scheduler-delay-factor": 0.14,
                                    "max-num-seqs": 72,
                                    "enable-chunked-prefill": True,
                                    "enable-prefix-caching": True,
                                },
                            }
                        ],
                    }
                    if node["devices"][0]["type"] == "cuda":
                        node_info["devices"][0]["envs"] = {"VLLM_TARGET_DEVICE": "cuda"}
                    else:
                        node_info["devices"][0]["envs"] = {
                            "VLLM_ALLOW_RUNTIME_LORA_UPDATING": "True",
                        }
                    simulator_config.append(node_info)
            elif deployment_request_json.simulator_id:
                simulator_config, metadata = asyncio.run(
                    SimulatorHandler().get_cluster_simulator_config(
                        deployment_request_json.cluster_id,
                        deployment_request_json.simulator_id,
                        deployment_request_json.concurrency,
                    )
                )
                # Store metadata for later use in deployment
                deployment_request_json.tool_calling_parser_type = metadata.get("tool_calling_parser_type")
                deployment_request_json.reasoning_parser_type = metadata.get("reasoning_parser_type")
                deployment_request_json.chat_template = metadata.get("chat_template")
            logger.info(f"Simulator config got from budsim: {simulator_config}")
            deployment_request_json.simulator_config = simulator_config
        except Exception as e:
            # notify activity that cluster verification failed
            notification_req.payload.event = "transfer_model_to_cluster"
            notification_req.payload.content = NotificationContent(
                title="Model transfer failed",
                message=f"Failed to fetch simulator configuration: {e}",
                status=WorkflowStatus.FAILED,
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=deployment_request_json.source_topic,
                target_name=deployment_request_json.source,
            )
            # yield ctx.call_activity(notify_activity, input=notification_activity_request.model_dump_json())
            return

        # transfer model to cluster
        transfer_model_request = TransferModelRequest(
            model=deployment_request_json.model,
            cluster_config=deployment_request_json.cluster_config,
            simulator_config=deployment_request_json.simulator_config,
            endpoint_name=deployment_request_json.endpoint_name,
            platform=deployment_request_json.platform,
            existing_deployment_namespace=deployment_request_json.existing_deployment_namespace,
            default_storage_class=getattr(deployment_request_json, "default_storage_class", None),
            default_access_mode=getattr(deployment_request_json, "default_access_mode", None),
            storage_size_gb=getattr(deployment_request_json, "storage_size_gb", None),
        )
        transfer_model_result = yield ctx.call_activity(
            CreateDeploymentWorkflow.transfer_model, input=transfer_model_request.model_dump_json()
        )
        logger.info(f"Transfer model result: {transfer_model_result}")

        # if transfer model is not successful
        if transfer_model_result.get("code", HTTPStatus.OK.value) != HTTPStatus.OK.value:
            # notify activity that model transfer failed
            notification_req.payload.event = "transfer_model_to_cluster"
            notification_req.payload.content = NotificationContent(
                title="Model transfer failed",
                message=transfer_model_result["message"],
                status=WorkflowStatus.FAILED,
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=deployment_request_json.source_topic,
                target_name=deployment_request_json.source,
            )
            # yield ctx.call_activity(notify_activity, input=notification_activity_request.model_dump_json())
            return

        deployment_request_json.namespace = transfer_model_result["param"]["namespace"]

        # update model transfer status
        update_model_transfer_status_request = UpdateModelTransferStatusRequest(
            main_workflow_id=instance_id,
            workflow_name=workflow_name,
            **deployment_request_json.model_dump(),
        )

        child_instance_id = instance_id + "-child"
        ctx.call_child_workflow(
            workflow=UpdateModelTransferStatusWorkflow.update_model_transfer_status,
            input=update_model_transfer_status_request.model_dump_json(),
            instance_id=child_instance_id,
        )

        # response = asyncio.run(
        #     UpdateModelTransferStatusWorkflow().__call__(update_model_transfer_status_request.model_dump_json())
        # )
        # logger.info(f"Update model transfer status response: {response}")

        # update model transfer status and should be completed with in 24 hrs
        timeout_event = ctx.create_timer(fire_at=ctx.current_utc_datetime + timedelta(hours=24))
        model_transfer_completed_event = ctx.wait_for_external_event("model_transfer_completed")

        # wait for model transfer to be completed or timeout
        winner = yield wf.when_any([model_transfer_completed_event, timeout_event])
        if winner == timeout_event:
            _ = ErrorResponse(message="Failed to complete model transfer job", code=HTTPStatus.BAD_REQUEST.value)

        model_transfer_result = model_transfer_completed_event.get_result()
        logger.info(f"Model transfer result: {model_transfer_result}")

        if model_transfer_result["param"]["status"] == "failed":
            notification_req.payload.event = "transfer_model_to_cluster"
            notification_req.payload.content = NotificationContent(
                title="Model transfer failed",
                message="Model transfer failed",
                status=WorkflowStatus.FAILED,
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=deployment_request_json.source_topic,
                target_name=deployment_request_json.source,
            )
            return

        # notify activity that model transfer is successful
        notification_req.payload.event = "transfer_model_to_cluster"
        notification_req.payload.content = NotificationContent(
            title="Model transfer successful",
            message=transfer_model_result["message"],
            status=WorkflowStatus.COMPLETED,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=deployment_request_json.source_topic,
            target_name=deployment_request_json.source,
        )
        # yield ctx.call_activity(notify_activity, input=notification_activity_request.model_dump_json())

        # notify activity ETA
        DeploymentService.publish_eta(notification_req, deployment_request_json, instance_id, "deploy_to_engine")

        deploy_engine_result = yield ctx.call_activity(
            CreateDeploymentWorkflow.deploy_engine, input=deployment_request_json.model_dump_json()
        )
        logger.info(f"Deploy engine result: {deploy_engine_result}")

        if deploy_engine_result.get("code", HTTPStatus.OK.value) != HTTPStatus.OK.value:
            # notify activity that engine deployment failed
            notification_req.payload.event = "deploy_to_engine"
            notification_req.payload.content = NotificationContent(
                title="Model deployment to engine failed",
                message=deploy_engine_result["message"],
                status=WorkflowStatus.FAILED,
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=deployment_request_json.source_topic,
                target_name=deployment_request_json.source,
            )
            # yield ctx.call_activity(notify_activity, input=notification_activity_request.model_dump_json())
            return

        # notify activity that engine deployment is successful
        notification_req.payload.event = "deploy_to_engine"
        notification_req.payload.content = NotificationContent(
            title="Model deployment to engine successful",
            message=deploy_engine_result["message"],
            status=WorkflowStatus.COMPLETED,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=deployment_request_json.source_topic,
            target_name=deployment_request_json.source,
        )
        # yield ctx.call_activity(notify_activity, input=notification_activity_request.model_dump_json())

        # notify activity ETA
        DeploymentService.publish_eta(
            notification_req, deployment_request_json, instance_id, "verify_deployment_status"
        )

        verify_deployment_health_request = VerifyDeploymentHealthRequest(
            cluster_id=deployment_request_json.cluster_id,
            cluster_config=deployment_request_json.cluster_config,
            namespace=deploy_engine_result["param"]["namespace"],
            ingress_url=deployment_request_json.ingress_url,
            cloud_model=False,
            platform=deployment_request_json.platform,
            add_worker=deployment_request_json.add_worker,
        )
        verify_deployment_health_result = yield ctx.call_activity(
            CreateDeploymentWorkflow.verify_deployment_health, input=verify_deployment_health_request.model_dump_json()
        )
        logger.info(f"Verify deployment health result: {verify_deployment_health_result}")

        if verify_deployment_health_result.get("code", HTTPStatus.OK.value) != HTTPStatus.OK.value:
            # notify activity that engine health verification failed
            notification_req.payload.event = "verify_deployment_status"
            notification_req.payload.content = NotificationContent(
                title="Model deployment is not healthy",
                message=verify_deployment_health_result["message"],
                status=WorkflowStatus.FAILED,
                primary_action="retry",
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=deployment_request_json.source_topic,
                target_name=deployment_request_json.source,
            )
            # yield ctx.call_activity(notify_activity, input=notification_activity_request.model_dump_json())
            return

        # notify activity that engine health verification is successful
        notification_req.payload.event = "verify_deployment_status"
        notification_req.payload.content = NotificationContent(
            title="Model deployment is healthy",
            message=verify_deployment_health_result["message"],
            status=WorkflowStatus.COMPLETED,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=deployment_request_json.source_topic,
            target_name=deployment_request_json.source,
        )
        # yield ctx.call_activity(notify_activity, input=notification_activity_request.model_dump_json())

        # notify activity ETA
        DeploymentService.publish_eta(
            notification_req, deployment_request_json, instance_id, "run_performance_benchmark"
        )

        model_type = "llm"
        if "/v1/embeddings" in verify_deployment_health_result["param"]["supported_endpoints"]:
            model_type = "embedding"

        run_performance_benchmark_request = RunPerformanceBenchmarkRequest(
            model=app_settings.model_registry_path + deployment_request_json.model,
            deployment_url=deploy_engine_result["param"]["deployment_url"],
            target_ttft=deployment_request_json.target_ttft,
            target_e2e_latency=deployment_request_json.target_e2e_latency,
            target_throughput_per_user=deployment_request_json.target_throughput_per_user,
            concurrency=deployment_request_json.concurrency,
            input_tokens=deployment_request_json.input_tokens,
            output_tokens=deployment_request_json.output_tokens,
            datasets=deployment_request_json.datasets,
            model_type=model_type,
        )
        workflow_run_performance_benchmark_request = WorkflowRunPerformanceBenchmarkRequest(
            cluster_config=deployment_request_json.cluster_config,
            namespace=deploy_engine_result["param"]["namespace"],
            benchmark_request=run_performance_benchmark_request,
            platform=deployment_request_json.platform,
            cleanup_namespace=deployment_request_json.is_performance_benchmark,
        )

        if deployment_request_json.is_performance_benchmark:
            workflow_run_performance_benchmark_request.benchmark_id = deployment_request_json.benchmark_id
            workflow_run_performance_benchmark_request.cluster_id = deployment_request_json.cluster_id
            workflow_run_performance_benchmark_request.user_id = deployment_request_json.user_id
            workflow_run_performance_benchmark_request.model_id = deployment_request_json.model_id
            workflow_run_performance_benchmark_request.nodes = deployment_request_json.nodes

        run_performance_benchmark_result = yield ctx.call_activity(
            CreateDeploymentWorkflow.run_performance_benchmark,
            input=workflow_run_performance_benchmark_request.model_dump_json(),
        )
        logger.info(f"Run performance benchmark result: {run_performance_benchmark_result}")

        if run_performance_benchmark_result.get("code", HTTPStatus.OK.value) != HTTPStatus.OK.value:
            # notify activity that performance benchmark failed
            notification_req.payload.event = "run_performance_benchmark"
            notification_req.payload.content = NotificationContent(
                title="Performance benchmark failed",
                message=run_performance_benchmark_result["message"],
                status=WorkflowStatus.FAILED,
                primary_action="retry",
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=deployment_request_json.source_topic,
                target_name=deployment_request_json.source,
            )
            # yield ctx.call_activity(notify_activity, input=notification_activity_request.model_dump_json())
            return

        # notify activity that performance benchmark is successful
        notification_req.payload.event = "run_performance_benchmark"
        notification_req.payload.content = NotificationContent(
            title="Performance benchmark successful",
            message=run_performance_benchmark_result["message"],
            status=WorkflowStatus.COMPLETED,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=deployment_request_json.source_topic,
            target_name=deployment_request_json.source,
        )
        # yield ctx.call_activity(notify_activity, input=notification_activity_request.model_dump_json())

        # notify activity that results are published
        deploy_model_result = DeployModelWorkflowResult(
            **run_performance_benchmark_result["param"],
            workflow_id=instance_id,
            cluster_id=deployment_request_json.cluster_id,
            simulator_id=deployment_request_json.simulator_id,
            namespace=deploy_engine_result["param"]["namespace"],
            deployment_status=verify_deployment_health_result["param"],
            number_of_nodes=deploy_engine_result["param"]["number_of_nodes"],
            deploy_config=deploy_engine_result["param"]["deploy_config"],
            supported_endpoints=list(verify_deployment_health_result["param"]["supported_endpoints"].keys())
            if isinstance(verify_deployment_health_result["param"]["supported_endpoints"], dict)
            else verify_deployment_health_result["param"]["supported_endpoints"],
        )

        # update deploy config in statestore
        with DaprService() as dapr_service:
            dapr_service.save_to_statestore(
                key=f"deploy_config_{deploy_model_result.namespace}",
                value=json.dumps(deploy_model_result.deploy_config),
            )

        notification_req.payload.event = "results"
        notification_req.payload.content = NotificationContent(
            title="Performance benchmark successful",
            message=run_performance_benchmark_result["message"],
            status=WorkflowStatus.COMPLETED,
            result=deploy_model_result.model_dump(mode="json"),
        )

        workflow_status = check_workflow_status_in_statestore(instance_id)
        if workflow_status:
            return
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=deployment_request_json.source_topic,
            target_name=deployment_request_json.source,
        )
        # yield ctx.call_activity(notify_activity, input=notification_activity_request.model_dump_json())

        # notify activity that performance benchmark is successful
        notification_req.payload.event = "deployment_status"
        notification_req.payload.content = NotificationContent(
            title="Model deployment completed",
            message="Model deployment completed successfully",
            status=WorkflowStatus.COMPLETED,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=deployment_request_json.source_topic,
            target_name=deployment_request_json.source,
        )
        # yield ctx.call_activity(notify_activity, input=notification_activity_request.model_dump_json())

        return

    async def __call__(
        self, request: DeploymentWorkflowRequest, workflow_id: Optional[str] = None
    ) -> Union[WorkflowMetadataResponse, ErrorResponse]:
        """Schedule the workflow to deploy a model."""
        workflow_name = "create_deployment"
        response = await dapr_workflows.schedule_workflow(
            workflow_name=workflow_name,
            workflow_input=request.model_dump_json(),
            workflow_id=str(workflow_id or uuid.uuid4()),
            workflow_steps=[
                WorkflowStep(
                    id="verify_cluster_connection",
                    title="Verifying cluster connection",
                    description="Verify the cluster connection",
                ),
                WorkflowStep(
                    id="transfer_model_to_cluster",
                    title="Transferring model to cluster",
                    description="Transfer the model to the cluster",
                ),
                WorkflowStep(
                    id="deploy_to_engine",
                    title="Deploying model to engine",
                    description="Deploy the model to the engine",
                ),
                WorkflowStep(
                    id="verify_deployment_status",
                    title="Verifying deployment status",
                    description="Verify the deployment status",
                ),
                WorkflowStep(
                    id="run_performance_benchmark",
                    title="Running performance benchmark",
                    description="Run the performance benchmark",
                ),
            ],
            eta=DeploymentService.get_deployment_eta("verify_cluster_connection"),
            target_topic_name=request.source_topic,
            target_name=request.source,
        )
        return response


class CreateCloudDeploymentWorkflow:
    """Workflow to create a cloud deployment."""

    @dapr_workflows.register_activity
    @staticmethod
    def deploy_cloud_model(ctx: wf.WorkflowActivityContext, deploy_engine_request: str):
        """Deploy the cloud model to the cluster."""
        logger = logging.get_logger("DeployCloudModel")
        workflow_id = ctx.workflow_id
        task_id = ctx.task_id
        logger.info(f"Deploying cloud model for workflow_id: {workflow_id} and task_id: {task_id}")
        deploy_engine_request_json = DeploymentWorkflowRequest.model_validate_json(deploy_engine_request)
        response: Union[SuccessResponse, ErrorResponse]
        try:
            # logger.info(f"Cluster config in deploy_cloud_model: {deploy_engine_request_json.cluster_config}")
            cluster_config = json.loads(deploy_engine_request_json.cluster_config)
            node_list = deploy_engine_request_json.simulator_config
            endpoint_name = deploy_engine_request_json.endpoint_name
            model = deploy_engine_request_json.model
            credential_id = deploy_engine_request_json.credential_id
            ingress_url = deploy_engine_request_json.ingress_url
            platform = deploy_engine_request_json.platform
            existing_deployment_namespace = deploy_engine_request_json.existing_deployment_namespace
            add_worker = deploy_engine_request_json.add_worker
            if add_worker:
                with DaprService() as dapr_service:
                    deploy_config = dapr_service.get_state(
                        store_name=app_settings.statestore_name,
                        key=f"deploy_config_{existing_deployment_namespace}",
                    )
                    deploy_config = json.loads(deploy_config.data) if deploy_config.data else []
                logger.info(f"Deploy config: {deploy_config}")
                logger.info(f"Node list: {node_list}")
                node_list = merge_deploy_config(deploy_config, node_list)
            logger.info(f"Node list after merge cloud model: {node_list}")
            deployment_handler = DeploymentHandler(config=cluster_config)
            workflow_status = check_workflow_status_in_statestore(workflow_id)
            if workflow_status:
                return workflow_status
            status, namespace, deployment_url, number_of_nodes, node_list = deployment_handler.cloud_model_deploy(
                node_list=node_list,
                endpoint_name=endpoint_name,
                model=model,
                credential_id=credential_id,
                ingress_url=ingress_url,
                platform=platform,
                namespace=existing_deployment_namespace,
                add_worker=add_worker,
                use_tensorzero=True,
                provider=deploy_engine_request_json.provider,
                default_storage_class=getattr(deploy_engine_request_json, "default_storage_class", None),
                default_access_mode=getattr(deploy_engine_request_json, "default_access_mode", None),
            )
            update_workflow_data_in_statestore(
                str(workflow_id),
                {
                    "namespace": namespace,
                    "cluster_config_dict": cluster_config,
                },
            )
            if status is not None:
                workflow_status = check_workflow_status_in_statestore(workflow_id)
                if workflow_status:
                    deployment_handler.delete(namespace=namespace, platform=platform)
                    return workflow_status
                response = SuccessResponse(
                    message="Engine deployed successfully",
                    param={
                        "status": status,
                        "namespace": namespace,
                        "endpoint_name": endpoint_name,
                        "deployment_url": deployment_url,
                        "number_of_nodes": number_of_nodes,
                        "deploy_config": node_list,
                    },
                )
            else:
                response = ErrorResponse(message="Failed to deploy runtime", code=HTTPStatus.BAD_REQUEST.value)
        except Exception as e:
            error_msg = f"Error deploying engine for workflow_id: {workflow_id} and task_id: {task_id}, error: {e}"
            import traceback

            logger.error(traceback.format_exc())
            logger.error(error_msg)
            response = ErrorResponse(message="Failed to deploy runtime", code=HTTPStatus.BAD_REQUEST.value)
        return response.model_dump(mode="json")

    @dapr_workflows.register_workflow
    @staticmethod
    def create_cloud_deployment(ctx: wf.DaprWorkflowContext, deployment_request: str):
        """Execute the workflow to create a cloud deployment."""
        logger = logging.get_logger("CreateCloudDeployment")
        instance_id = str(ctx.instance_id)
        logger.info(f"Creating cloud deployment for instance_id: {instance_id}")
        save_workflow_status_in_statestore(instance_id, WorkflowStatus.RUNNING.value)
        deployment_request_json = DeploymentWorkflowRequest.model_validate_json(deployment_request)

        workflow_name = "deploy_model"
        if deployment_request_json.existing_deployment_namespace is not None:
            workflow_name = "add_worker"
        elif deployment_request_json.is_performance_benchmark:
            workflow_name = "performance_benchmark"
        deployment_request_json.add_worker = deployment_request_json.existing_deployment_namespace is not None
        notification_request = NotificationRequest.from_cloud_event(
            cloud_event=deployment_request_json, name=workflow_name, workflow_id=instance_id
        )
        notification_req = notification_request.model_copy(deep=True)

        # notify activity ETA
        notification_req.payload.event = "eta"
        notification_req.payload.content = NotificationContent(
            title="Estimated time to completion",
            message=f"{4 * 10}",
            status=WorkflowStatus.RUNNING,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=deployment_request_json.source_topic,
            target_name=deployment_request_json.source,
        )
        # yield ctx.call_activity(
        #     notify_activity,
        #     input=notification_activity_request.model_dump_json(),
        # )

        # notify activity that deployment creating process is initiated
        notification_req.payload.event = "deployment_status"
        notification_req.payload.content = NotificationContent(
            title="Model deployment process is initiated",
            message=f"Model deployment process is initiated for simulator config : {deployment_request_json.simulator_config}",
            status=WorkflowStatus.STARTED,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=deployment_request_json.source_topic,
            target_name=deployment_request_json.source,
        )
        # yield ctx.call_activity(
        #     notify_activity,
        #     input=notification_activity_request.model_dump_json(),
        # )

        # fetch cluster details from db
        with DBSession() as session:
            db_cluster = asyncio.run(
                DeploymentService(session)._get_cluster(deployment_request_json.cluster_id, missing_ok=True)
            )
            if db_cluster is None:
                notification_req.payload.event = "verify_cluster_connection"
                notification_req.payload.content = NotificationContent(
                    title="Cluster not found",
                    message="Cluster not found",
                    status=WorkflowStatus.FAILED,
                    primary_action="retry",
                )
                dapr_workflows.publish_notification(
                    workflow_id=instance_id,
                    notification=notification_req,
                    target_topic_name=deployment_request_json.source_topic,
                    target_name=deployment_request_json.source,
                )
                # yield ctx.call_activity(notify_activity, input=notification_activity_request.model_dump_json())
                return
            with DaprServiceCrypto() as dapr_service:
                configuration_decrypted = dapr_service.decrypt_data(db_cluster.configuration)

            deployment_request_json.cluster_config = configuration_decrypted
            deployment_request_json.ingress_url = db_cluster.ingress_url
            deployment_request_json.platform = db_cluster.platform
            # fetch simulator configuration
            # nodes = db_cluster.nodes
            # node_name = nodes[0].name if len(nodes) > 0 else "dev-server"
            # simulator_config = [
            #     {
            #         "id": "0f0879c5-b4c7-47a1-ae61-6cacf8329f1d",
            #         "name": "dev-server",
            #         "devices": [
            #             {
            #                 "config_id": "1912",
            #                 "name": "AMD EPYC 7763 64-Core Processor",
            #                 "type": "cpu",
            #                 "image": "ghcr.io/berriai/litellm:main-latest",
            #                 "memory": 1000.0,
            #                 "num_cpus": 1,
            #                 "args": {},
            #                 "envs": {"NUM_CPUS": 1},
            #                 "tp_size": 1,
            #                 "replica": 1,
            #                 "concurrency": 100,
            #                 "ttft": 0.0,
            #                 "throughput_per_user": 0.0,
            #                 "e2e_latency": 0.0,
            #                 "error_rate": 0.0,
            #                 "cost_per_million_tokens": 0.06742872863083715,
            #             }
            #         ],
            #     }
            # ]

        try:
            if deployment_request_json.is_performance_benchmark and deployment_request_json.nodes:
                # TODO: perform validation of nodes
                simulator_config = []
                for node in deployment_request_json.nodes:
                    simulator_config.append(
                        {
                            "id": node["id"],
                            "name": node["hostname"],
                            "devices": [
                                {
                                    "name": node["hostname"],
                                    "type": node["devices"][0]["type"],
                                    "image": "ghcr.io/berriai/litellm:main-latest",
                                    "memory": 1000.0,
                                    "num_cpus": 1,
                                    "replica": 1,
                                    "concurrency": 100,
                                    "envs": {"NUM_CPUS": 1},
                                }
                            ],
                        }
                    )
            elif deployment_request_json.simulator_id:
                simulator_config, metadata = asyncio.run(
                    SimulatorHandler().get_cluster_simulator_config(
                        deployment_request_json.cluster_id,
                        deployment_request_json.simulator_id,
                        deployment_request_json.concurrency,
                    )
                )
                # Store metadata for later use in deployment (cloud workflow)
                deployment_request_json.tool_calling_parser_type = metadata.get("tool_calling_parser_type")
                deployment_request_json.reasoning_parser_type = metadata.get("reasoning_parser_type")
                deployment_request_json.chat_template = metadata.get("chat_template")
            logger.info(f"Simulator config got from budsim: {simulator_config}")
            deployment_request_json.simulator_config = simulator_config
        except Exception as e:
            logger.error(f"Error fetching simulator configuration: {e}")
            # import traceback

            # notify activity that cluster verification failed
            notification_req.payload.event = "verify_cluster_connection"
            notification_req.payload.content = NotificationContent(
                title="Verify cluster connection failed",
                message=f"{e}",
                status=WorkflowStatus.FAILED,
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=deployment_request_json.source_topic,
                target_name=deployment_request_json.source,
            )
            # yield ctx.call_activity(notify_activity, input=notification_activity_request.model_dump_json())
            return

        # verify cluster connection
        verify_cluster_connection_request = VerifyClusterConnection(
            cluster_config=deployment_request_json.cluster_config,
            platform=deployment_request_json.platform,
        )
        verify_cluster_connection_result = yield ctx.call_activity(
            RegisterClusterWorkflow.verify_cluster_connection,
            input=verify_cluster_connection_request.model_dump_json(),
        )

        # if verify cluster connection is not successful
        if verify_cluster_connection_result.get("code", HTTPStatus.OK.value) != HTTPStatus.OK.value:
            # notify activity that cluster verification failed
            notification_req.payload.event = "verify_cluster_connection"
            notification_req.payload.content = NotificationContent(
                title="Cluster connection verification failed",
                message=verify_cluster_connection_result["message"],
                status=WorkflowStatus.FAILED,
                primary_action="retry",
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=deployment_request_json.source_topic,
                target_name=deployment_request_json.source,
            )
            # yield ctx.call_activity(notify_activity, input=notification_activity_request.model_dump_json())
            return

        # notify activity that cluster verification is successful
        notification_req.payload.event = "verify_cluster_connection"
        notification_req.payload.content = NotificationContent(
            title="Cluster connection verification successful",
            message=verify_cluster_connection_result["message"],
            status=WorkflowStatus.COMPLETED,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=deployment_request_json.source_topic,
            target_name=deployment_request_json.source,
        )
        # yield ctx.call_activity(notify_activity, input=notification_activity_request.model_dump_json())

        # notify activity ETA
        notification_req.payload.event = "eta"
        notification_req.payload.content = NotificationContent(
            title="Estimated time to completion",
            message=f"{3 * 10}",
            status=WorkflowStatus.RUNNING,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=deployment_request_json.source_topic,
            target_name=deployment_request_json.source,
        )
        # yield ctx.call_activity(
        #     notify_activity,
        #     input=notification_activity_request.model_dump_json(),
        # )

        deploy_engine_result = yield ctx.call_activity(
            CreateCloudDeploymentWorkflow.deploy_cloud_model, input=deployment_request_json.model_dump_json()
        )
        logger.info(f"Deploy engine result: {deploy_engine_result}")

        if deploy_engine_result.get("code", HTTPStatus.OK.value) != HTTPStatus.OK.value:
            # notify activity that engine deployment failed
            notification_req.payload.event = "deploy_to_engine"
            notification_req.payload.content = NotificationContent(
                title="Model deployment to engine failed",
                message=deploy_engine_result["message"],
                status=WorkflowStatus.FAILED,
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=deployment_request_json.source_topic,
                target_name=deployment_request_json.source,
            )
            # yield ctx.call_activity(notify_activity, input=notification_activity_request.model_dump_json())
            return

        # notify activity that engine deployment is successful
        notification_req.payload.event = "deploy_to_engine"
        notification_req.payload.content = NotificationContent(
            title="Model deployment to engine successful",
            message=deploy_engine_result["message"],
            status=WorkflowStatus.COMPLETED,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=deployment_request_json.source_topic,
            target_name=deployment_request_json.source,
        )
        # yield ctx.call_activity(notify_activity, input=notification_activity_request.model_dump_json())

        # notify activity ETA
        notification_req.payload.event = "eta"
        notification_req.payload.content = NotificationContent(
            title="Estimated time to completion",
            message=f"{2 * 10}",
            status=WorkflowStatus.RUNNING,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=deployment_request_json.source_topic,
            target_name=deployment_request_json.source,
        )
        # yield ctx.call_activity(
        #     notify_activity,
        #     input=notification_activity_request.model_dump_json(),
        # )

        verify_deployment_health_request = VerifyDeploymentHealthRequest(
            cluster_id=deployment_request_json.cluster_id,
            cluster_config=deployment_request_json.cluster_config,
            namespace=deploy_engine_result["param"]["namespace"],
            ingress_url=deployment_request_json.ingress_url,
            cloud_model=True,
            platform=deployment_request_json.platform,
            add_worker=deployment_request_json.add_worker,
        )
        verify_deployment_health_result = yield ctx.call_activity(
            CreateDeploymentWorkflow.verify_deployment_health, input=verify_deployment_health_request.model_dump_json()
        )
        logger.info(f"Verify deployment health result: {verify_deployment_health_result}")

        if verify_deployment_health_result.get("code", HTTPStatus.OK.value) != HTTPStatus.OK.value:
            # notify activity that engine health verification failed
            notification_req.payload.event = "verify_deployment_status"
            notification_req.payload.content = NotificationContent(
                title="Model deployment is not healthy",
                message=verify_deployment_health_result["message"],
                status=WorkflowStatus.FAILED,
                primary_action="retry",
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=deployment_request_json.source_topic,
                target_name=deployment_request_json.source,
            )
            # yield ctx.call_activity(notify_activity, input=notification_activity_request.model_dump_json())
            return

        # notify activity that engine health verification is successful
        notification_req.payload.event = "verify_deployment_status"
        notification_req.payload.content = NotificationContent(
            title="Model deployment is healthy",
            message=verify_deployment_health_result["message"],
            status=WorkflowStatus.COMPLETED,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=deployment_request_json.source_topic,
            target_name=deployment_request_json.source,
        )
        # yield ctx.call_activity(notify_activity, input=notification_activity_request.model_dump_json())

        # notify activity ETA
        notification_req.payload.event = "eta"
        notification_req.payload.content = NotificationContent(
            title="Estimated time to completion",
            message=f"{1 * 10}",
            status=WorkflowStatus.RUNNING,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=deployment_request_json.source_topic,
            target_name=deployment_request_json.source,
        )
        # yield ctx.call_activity(
        #     notify_activity,
        #     input=notification_activity_request.model_dump_json(),
        # )
        model_type = "llm"
        if "/v1/embeddings" in verify_deployment_health_result["param"]["supported_endpoints"]:
            model_type = "embedding"

        run_performance_benchmark_request = RunPerformanceBenchmarkRequest(
            model=deployment_request_json.model,
            deployment_url=deploy_engine_result["param"]["deployment_url"],
            concurrency=deployment_request_json.concurrency,
            input_tokens=deployment_request_json.input_tokens,
            output_tokens=deployment_request_json.output_tokens,
            datasets=deployment_request_json.datasets,
            model_type=model_type,
        )
        workflow_run_performance_benchmark_request = WorkflowRunPerformanceBenchmarkRequest(
            cluster_config=deployment_request_json.cluster_config,
            namespace=deploy_engine_result["param"]["namespace"],
            benchmark_request=run_performance_benchmark_request,
            provider_type="cloud",
            platform=deployment_request_json.platform,
            cleanup_namespace=deployment_request_json.is_performance_benchmark,
        )
        if deployment_request_json.is_performance_benchmark:
            workflow_run_performance_benchmark_request.benchmark_id = deployment_request_json.benchmark_id
            workflow_run_performance_benchmark_request.cluster_id = deployment_request_json.cluster_id
            workflow_run_performance_benchmark_request.user_id = deployment_request_json.user_id
            workflow_run_performance_benchmark_request.model_id = deployment_request_json.model_id
            workflow_run_performance_benchmark_request.nodes = deployment_request_json.nodes

        run_performance_benchmark_result = yield ctx.call_activity(
            CreateDeploymentWorkflow.run_performance_benchmark,
            input=workflow_run_performance_benchmark_request.model_dump_json(),
        )
        logger.info(f"Run performance benchmark result: {run_performance_benchmark_result}")

        if run_performance_benchmark_result.get("code", HTTPStatus.OK.value) != HTTPStatus.OK.value:
            # notify activity that performance benchmark failed
            notification_req.payload.event = "run_performance_benchmark"
            notification_req.payload.content = NotificationContent(
                title="Performance benchmark failed",
                message=run_performance_benchmark_result["message"],
                status=WorkflowStatus.FAILED,
                primary_action="retry",
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=deployment_request_json.source_topic,
                target_name=deployment_request_json.source,
            )
            # yield ctx.call_activity(notify_activity, input=notification_activity_request.model_dump_json())
            return

        # notify activity that performance benchmark is successful
        notification_req.payload.event = "run_performance_benchmark"
        notification_req.payload.content = NotificationContent(
            title="Performance benchmark successful",
            message=run_performance_benchmark_result["message"],
            status=WorkflowStatus.COMPLETED,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=deployment_request_json.source_topic,
            target_name=deployment_request_json.source,
        )
        # yield ctx.call_activity(notify_activity, input=notification_activity_request.model_dump_json())

        # notify activity that results are published
        deploy_model_result = DeployModelWorkflowResult(
            **run_performance_benchmark_result["param"],
            workflow_id=instance_id,
            cluster_id=deployment_request_json.cluster_id,
            simulator_id=deployment_request_json.simulator_id,
            namespace=deploy_engine_result["param"]["namespace"],
            deployment_status=verify_deployment_health_result["param"],
            credential_id=deployment_request_json.credential_id,
            number_of_nodes=deploy_engine_result["param"]["number_of_nodes"],
            deploy_config=deploy_engine_result["param"]["deploy_config"],
            supported_endpoints=verify_deployment_health_result["param"]["supported_endpoints"],
        )
        logger.info(f"Deploy model result: {deploy_model_result}")

        # update deploy config in statestore
        with DaprService() as dapr_service:
            dapr_service.save_to_statestore(
                key=f"deploy_config_{deploy_model_result.namespace}",
                value=json.dumps(deploy_model_result.deploy_config),
            )

        notification_req.payload.event = "results"
        notification_req.payload.content = NotificationContent(
            title="Performance benchmark successful",
            message=run_performance_benchmark_result["message"],
            status=WorkflowStatus.COMPLETED,
            result=deploy_model_result.model_dump(mode="json"),
        )
        workflow_status = check_workflow_status_in_statestore(instance_id)
        if workflow_status:
            return
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=deployment_request_json.source_topic,
            target_name=deployment_request_json.source,
        )
        # yield ctx.call_activity(notify_activity, input=notification_activity_request.model_dump_json())

        # notify activity that performance benchmark is successful
        notification_req.payload.event = "deployment_status"
        notification_req.payload.content = NotificationContent(
            title="Model deployment completed",
            message="Model deployment completed successfully",
            status=WorkflowStatus.COMPLETED,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=deployment_request_json.source_topic,
            target_name=deployment_request_json.source,
        )
        # yield ctx.call_activity(notify_activity, input=notification_activity_request.model_dump_json())

        return

    async def __call__(
        self, request: DeploymentWorkflowRequest, workflow_id: Optional[str] = None
    ) -> Union[WorkflowMetadataResponse, ErrorResponse]:
        """Schedule the workflow to deploy a model."""
        workflow_name = "create_cloud_deployment"
        response = await dapr_workflows.schedule_workflow(
            workflow_name=workflow_name,
            workflow_input=request.model_dump_json(),
            workflow_id=str(workflow_id or uuid.uuid4()),
            workflow_steps=[
                WorkflowStep(
                    id="verify_cluster_connection",
                    title="Verifying cluster connection",
                    description="Verify the cluster connection",
                ),
                WorkflowStep(
                    id="deploy_to_engine",
                    title="Deploying model to engine",
                    description="Deploy the model to the engine",
                ),
                WorkflowStep(
                    id="verify_deployment_status",
                    title="Verifying deployment status",
                    description="Verify the deployment status",
                ),
                WorkflowStep(
                    id="run_performance_benchmark",
                    title="Running performance benchmark",
                    description="Run the performance benchmark",
                ),
            ],
            eta=30 * 60,
            target_topic_name=request.source_topic,
            target_name=request.source,
        )
        return response


class DeleteDeploymentWorkflow:
    """Workflow to delete a deployment."""

    @dapr_workflows.register_workflow
    @staticmethod
    def delete_deployment(ctx: wf.DaprWorkflowContext, delete_deployment_request: str):
        """Delete a deployment."""
        logger = logging.get_logger("DeleteDeployment")
        instance_id = ctx.instance_id
        logger.info(f"Deleting deployment for workflow_id: {instance_id}")
        delete_deployment_request_json = DeleteDeploymentRequest.model_validate_json(delete_deployment_request)
        namespace = delete_deployment_request_json.namespace
        cluster_id = delete_deployment_request_json.cluster_id

        workflow_name = "delete_deployment"
        notification_request = NotificationRequest.from_cloud_event(
            cloud_event=delete_deployment_request_json, name=workflow_name, workflow_id=instance_id
        )
        notification_req = notification_request.model_copy(deep=True)

        # notify activity that cluster deletion process is initiated
        notification_req.payload.event = "deployment_deletion_status"
        notification_req.payload.content = NotificationContent(
            title="Deployment deletion process is initiated",
            message=f"Deployment deletion process is initiated for namespace : {namespace}",
            status=WorkflowStatus.STARTED,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=delete_deployment_request_json.source_topic,
            target_name=delete_deployment_request_json.source,
        )
        # yield ctx.call_activity(notify_activity, input=notification_activity_request.model_dump_json())

        # notify activity ETA
        notification_req.payload.event = "eta"
        notification_req.payload.content = NotificationContent(
            title="Estimated time to completion",
            message=f"{1 * 10}",
            status=WorkflowStatus.RUNNING,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=delete_deployment_request_json.source_topic,
            target_name=delete_deployment_request_json.source,
        )
        # yield ctx.call_activity(notify_activity, input=notification_activity_request.model_dump_json())

        with DBSession() as session:
            db_cluster = asyncio.run(DeploymentService(session)._get_cluster(cluster_id, missing_ok=True))

            if db_cluster is None:
                notification_req.payload.event = "delete_namespace"
                notification_req.payload.content = NotificationContent(
                    title="Cluster not found",
                    message="Deployment deletion failed since cluster not found",
                    status=WorkflowStatus.FAILED,
                )
                dapr_workflows.publish_notification(
                    workflow_id=instance_id,
                    notification=notification_req,
                    target_topic_name=delete_deployment_request_json.source_topic,
                    target_name=delete_deployment_request_json.source,
                )
                # yield ctx.call_activity(notify_activity, input=notification_activity_request.model_dump_json())
                return

            config_file_dict = db_cluster.config_file_dict
            platform = db_cluster.platform

        with DBSession() as session:
            worker_info_filters = {"cluster_id": cluster_id, "namespace": namespace}
            workers_info, _ = asyncio.run(WorkerInfoDataManager(session).get_all_workers(filters=worker_info_filters))
            if workers_info:
                asyncio.run(WorkerInfoDataManager(session).delete_worker_info(workers_info))
                logger.info(
                    f"Deleted {len(workers_info)} worker_info records for cluster {cluster_id}, namespace {namespace}"
                )

        delete_namespace_request = DeleteNamespaceRequest(
            cluster_config=config_file_dict, namespace=namespace, platform=platform
        )
        delete_namespace_result = yield ctx.call_activity(
            delete_namespace, input=delete_namespace_request.model_dump_json()
        )
        logger.info(f"Delete namespace result: {delete_namespace_result}")

        if delete_namespace_result.get("code", HTTPStatus.OK.value) != HTTPStatus.OK.value:
            logger.info(f"Error : Delete namespace result: {delete_namespace_result}")
            # notify activity that namespace deletion failed
            notification_req.payload.event = "delete_namespace"
            notification_req.payload.content = NotificationContent(
                title="Deployment deletion failed",
                message=delete_namespace_result["message"],
                status=WorkflowStatus.FAILED,
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=delete_deployment_request_json.source_topic,
                target_name=delete_deployment_request_json.source,
            )
            # yield ctx.call_activity(notify_activity, input=notification_activity_request.model_dump_json())
            return

        # notify activity that namespace deletion is successful
        notification_req.payload.event = "delete_namespace"
        notification_req.payload.content = NotificationContent(
            title="Namespace deleted successfully",
            message="Namespace deleted successfully",
            status=WorkflowStatus.COMPLETED,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=delete_deployment_request_json.source_topic,
            target_name=delete_deployment_request_json.source,
        )
        # yield ctx.call_activity(notify_activity, input=notification_activity_request.model_dump_json())

        with DaprService() as dapr_service:
            dapr_service.delete_state(store_name=app_settings.statestore_name, key=f"deploy_config_{namespace}")

        # notify activity that deployment deleting process is completed
        notification_req.payload.event = "results"
        notification_req.payload.content = NotificationContent(
            title="Deployment deleted successfully",
            message=f"Deployment {namespace} was deleted successfully",
            status=WorkflowStatus.COMPLETED,
            results={"namespace": namespace, "cluster_id": str(cluster_id)},
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=delete_deployment_request_json.source_topic,
            target_name=delete_deployment_request_json.source,
        )
        # yield ctx.call_activity(notify_activity, input=notification_activity_request.model_dump_json())

        notification_req.payload.event = "deployment_deletion_status"
        notification_req.payload.content = NotificationContent(
            title="Deployment deleted successfully",
            message=f"Deployment {namespace} was deleted successfully",
            status=WorkflowStatus.COMPLETED,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=delete_deployment_request_json.source_topic,
            target_name=delete_deployment_request_json.source,
        )
        # yield ctx.call_activity(
        #     notify_activity,
        #     input=notification_activity_request.model_dump_json(),
        # )

        return

    async def __call__(
        self, request: DeleteDeploymentRequest, workflow_id: Optional[str] = None
    ) -> Union[WorkflowMetadataResponse, ErrorResponse]:
        """Schedule the workflow to delete a deployment."""
        response = await dapr_workflows.schedule_workflow(
            workflow_name="delete_deployment",
            workflow_input=request.model_dump_json(),
            workflow_id=str(workflow_id or uuid.uuid4()),
            workflow_steps=[
                WorkflowStep(
                    id="delete_namespace",
                    title="Deleting model deployment",
                    description="Delete the model deployment",
                ),
            ],
            eta=1 * 30,
            target_topic_name=request.source_topic,
            target_name=request.source,
        )
        return response


class DeleteWorkerWorkflow:
    @dapr_workflows.register_workflow
    @staticmethod
    def delete_worker(ctx: wf.DaprWorkflowContext, delete_worker_request: str):
        """Delete a worker."""
        logger = logging.get_logger("DeleteWorker")
        instance_id = str(ctx.instance_id)
        logger.info(f"Deleting worker for workflow_id: {instance_id}")
        delete_worker_request_json = DeleteWorkerRequest.model_validate_json(delete_worker_request)

        workflow_name = "delete_worker"
        notification_request = NotificationRequest.from_cloud_event(
            cloud_event=delete_worker_request_json, name=workflow_name
        )
        notification_req = notification_request.model_copy(deep=True)
        notification_req.payload.event = "delete_worker_status"
        notification_req.payload.content = NotificationContent(
            title="Deleting worker",
            message=f"Deleting worker {delete_worker_request_json.worker_id}",
            status=WorkflowStatus.STARTED,
        )

        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=delete_worker_request_json.source_topic,
            target_name=delete_worker_request_json.source,
        )

        # yield ctx.call_activity(notify_activity, input=notification_activity_request.model_dump_json())

        # notify activity ETA
        notification_req.payload.event = "eta"
        notification_req.payload.content = NotificationContent(
            title="Estimated time to completion",
            message=f"{1 * 10}",
            status=WorkflowStatus.RUNNING,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=delete_worker_request_json.source_topic,
            target_name=delete_worker_request_json.source,
        )
        # yield ctx.call_activity(notify_activity, input=notification_activity_request.model_dump_json())

        with DBSession() as session:
            db_worker = asyncio.run(
                WorkerInfoService(session).get_worker_detail(
                    {"id": delete_worker_request_json.worker_id}, missing_ok=True
                )
            )
            if db_worker is None:
                notification_req.payload.event = "delete_worker"
                notification_req.payload.content = NotificationContent(
                    title="Worker not found",
                    message=f"Worker {delete_worker_request_json.worker_id} not found",
                    status=WorkflowStatus.FAILED,
                )
                dapr_workflows.publish_notification(
                    workflow_id=instance_id,
                    notification=notification_req,
                    target_topic_name=delete_worker_request_json.source_topic,
                    target_name=delete_worker_request_json.source,
                )
                # yield ctx.call_activity(notify_activity, input=notification_activity_request.model_dump_json())
                return

            namespace = db_worker.namespace
            pod_name = db_worker.name
            cluster_id = db_worker.cluster_id
            deployment_name = db_worker.deployment_name
            config_dict = db_worker.cluster.config_file_dict
            platform = db_worker.cluster.platform
            ingress_url = db_worker.cluster.ingress_url
            hardware = db_worker.hardware

            # Update deploy config in statestore
            with DaprService() as dapr_service:
                deploy_config = dapr_service.get_state(
                    store_name=app_settings.statestore_name, key=f"deploy_config_{namespace}"
                )
                deploy_config = json.loads(deploy_config.data) if deploy_config.data else []
                if deploy_config:
                    for config in deploy_config:
                        for device in config["devices"]:
                            if device["type"] == hardware:
                                device["replica"] -= 1
                                break
                    dapr_service.save_to_statestore(key=f"deploy_config_{namespace}", value=json.dumps(deploy_config))
        delete_worker_activity_request_json = DeleteWorkerActivityRequest(
            cluster_id=cluster_id,
            worker_name=pod_name,
            namespace=namespace,
            cluster_config=config_dict,
            platform=platform,
            deployment_name=deployment_name,
            ingress_url=ingress_url,
        )

        try:
            deployment_handler = DeploymentHandler(config=delete_worker_activity_request_json.cluster_config)
            result = deployment_handler.delete_pod(
                delete_worker_activity_request_json.namespace,
                delete_worker_activity_request_json.deployment_name,
                delete_worker_activity_request_json.worker_name,
                delete_worker_activity_request_json.platform,
            )
            if result == "successful":
                response = SuccessResponse(message="Worker deleted successfully", param={"delete_status": result})
            else:
                response = ErrorResponse(message="Failed to delete worker")
        except Exception as e:
            logger.error(f"Failed to delete worker : {e}")
            response = ErrorResponse(message=f"Failed to delete worker : {e}")

        if response.code == HTTPStatus.OK.value:
            try:
                # delete worker info from db
                time.sleep(5)
                with DBSession() as session:
                    worker_info_filters = {
                        "name": delete_worker_activity_request_json.worker_name,
                        "cluster_id": delete_worker_activity_request_json.cluster_id,
                        "namespace": delete_worker_activity_request_json.namespace,
                    }
                    workers_info, _ = asyncio.run(
                        WorkerInfoDataManager(session).get_all_workers(filters=worker_info_filters)
                    )
                    if workers_info:
                        asyncio.run(WorkerInfoDataManager(session).delete_worker_info(workers_info))

                verify_deployment_health_request_json = VerifyDeploymentHealthRequest(
                    cluster_id=delete_worker_activity_request_json.cluster_id,
                    cluster_config=json.dumps(delete_worker_activity_request_json.cluster_config),
                    namespace=delete_worker_activity_request_json.namespace,
                    ingress_url=delete_worker_activity_request_json.ingress_url,
                    cloud_model=False,
                    platform=delete_worker_activity_request_json.platform,
                    ingress_health=False,
                )
                # deployment_handler = DeploymentHandler(  # noqa: F841
                #     config=json.loads(verify_deployment_health_request_json.cluster_config)
                # )
                ingress_url = verify_deployment_health_request_json.ingress_url  # noqa: F841
                deployment_status = deployment_handler.get_deployment_status(
                    verify_deployment_health_request_json.namespace,
                    ingress_url,
                    cloud_model=verify_deployment_health_request_json.cloud_model,
                    platform=verify_deployment_health_request_json.platform,
                    ingress_health=verify_deployment_health_request_json.ingress_health,
                )
                logger.info(f"Deployment status: {deployment_status}")
                if deployment_status["ingress_health"]:
                    response = SuccessResponse(
                        message="Engine health verified successfully", param={**deployment_status}
                    )
                else:
                    # TODO: if ingress fails in delete worker - what to do ?
                    deployment_handler.delete(
                        namespace=verify_deployment_health_request_json.namespace,
                        platform=verify_deployment_health_request_json.platform,
                    )
                    if deployment_status["status"] == DeploymentStatusEnum.FAILED:
                        message = f"Engine deployment failed: {deployment_status['replicas']['reason']}"
                    else:
                        message = "Deployment ingress verification failed"
                    response = ErrorResponse(
                        message=f"{message}",
                        code=HTTPStatus.BAD_REQUEST.value,
                    )
            except Exception as e:
                error_msg = f"Error verifying engine health for workflow_id: {instance_id}, error: {e}"
                logger.exception(error_msg)
                response = ErrorResponse(
                    message="Engine health verification failed", code=HTTPStatus.BAD_REQUEST.value
                )

        logger.info(f"Verify deployment health result: {response}")
        get_deployment_status_result = response.model_dump(mode="json")

        if get_deployment_status_result.get("code", HTTPStatus.OK.value) != HTTPStatus.OK.value:
            notification_req.payload.event = "delete_worker_activity"
            notification_req.payload.content = NotificationContent(
                title="Get deployment status failed",
                message=f"Get deployment {namespace} status failed",
                status=WorkflowStatus.FAILED,
                result=get_deployment_status_result,
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=delete_worker_request_json.source_topic,
                target_name=delete_worker_request_json.source,
            )
            # yield ctx.call_activity(notify_activity, input=notification_activity_request.model_dump_json())
            return

        notification_req.payload.event = "delete_worker"
        notification_req.payload.content = NotificationContent(
            title="Deleted worker",
            message=f"Worker {pod_name} deleted successfully",
            status=WorkflowStatus.COMPLETED,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=delete_worker_request_json.source_topic,
            target_name=delete_worker_request_json.source,
        )
        # yield ctx.call_activity(notify_activity, input=notification_activity_request.model_dump_json())

        # update workers info in db
        worker_data_list = get_deployment_status_result["param"]["worker_data_list"]
        workers_info = [
            WorkerInfoModel(
                cluster_id=cluster_id,
                namespace=namespace,
                **worker,
                deployment_status=get_deployment_status_result["param"]["status"],
                last_updated_datetime=datetime.now(timezone.utc),
            )
            for worker in worker_data_list
        ]
        with DBSession() as session:
            worker_info_filters = {
                "cluster_id": cluster_id,
                "namespace": deployment_name,
            }
            db_workers_info, _ = asyncio.run(
                WorkerInfoDataManager(session).get_all_workers(filters=worker_info_filters)
            )
            db_workers_info = asyncio.run(
                WorkerInfoService(session).update_worker_info(workers_info, db_workers_info, cluster_id)
            )

            notification_req.payload.event = "results"
            notification_req.payload.content = NotificationContent(
                title="Worker deleted",
                message=f"Worker {pod_name} deleted successfully",
                status=WorkflowStatus.COMPLETED,
                result={
                    "worker_data_list": [
                        (WorkerInfo.model_validate(worker)).model_dump(mode="json") for worker in db_workers_info
                    ]
                },
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=delete_worker_request_json.source_topic,
                target_name=delete_worker_request_json.source,
            )
        # yield ctx.call_activity(notify_activity, input=notification_activity_request.model_dump_json())

        notification_req.payload.event = "delete_worker_status"
        notification_req.payload.content = NotificationContent(
            title="Worker deleted",
            message=f"Worker {pod_name} deleted successfully",
            status=WorkflowStatus.COMPLETED,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=delete_worker_request_json.source_topic,
            target_name=delete_worker_request_json.source,
        )
        # yield ctx.call_activity(notify_activity, input=notification_activity_request.model_dump_json())
        return

    async def __call__(
        self, request: DeleteWorkerRequest, workflow_id: Optional[str] = None
    ) -> Union[WorkflowMetadataResponse, ErrorResponse]:
        """Schedule the workflow to delete a worker."""
        workflow_id = str(workflow_id or uuid.uuid4())
        workflow_name = "delete_worker"
        workflow_input = request.model_dump_json()
        workflow_steps = [
            WorkflowStep(
                id="delete_worker",
                title="Deleting worker",
                description="Delete the worker",
            ),
        ]
        eta = 1 * 30
        # response = WorkflowMetadataResponse(
        #     workflow_id=workflow_id,
        #     workflow_name=workflow_name,
        #     steps=workflow_steps or [],
        #     status=WorkflowStatus.PENDING,
        #     eta=eta,
        # )
        # asyncio.create_task(
        #     dapr_workflows.schedule_workflow(
        #         workflow_name=workflow_name,
        #         workflow_input=workflow_input,
        #         workflow_id=workflow_id,
        #         workflow_steps=workflow_steps,
        #         eta=eta,
        #         target_topic_name=request.source_topic,
        #         target_name=request.source,
        #     )
        # )
        response = await dapr_workflows.schedule_workflow(
            workflow_name=workflow_name,
            workflow_input=workflow_input,
            workflow_id=workflow_id,
            workflow_steps=workflow_steps,
            eta=eta,
            target_topic_name=request.source_topic,
            target_name=request.source,
        )
        return response


class UpdateModelTransferStatusWorkflow:
    @dapr_workflows.register_workflow
    @staticmethod
    def update_model_transfer_status(ctx: wf.DaprWorkflowContext, update_model_transfer_request: str):
        """Schedule the workflow to update the model transfer status."""
        logger = logging.get_logger("UpdateModelTransferStatus")
        instance_id = str(ctx.instance_id)
        logger.info(f"Updating model transfer status for workflow_id: {instance_id}")

        update_model_transfer_request_json = UpdateModelTransferStatusRequest.model_validate_json(
            update_model_transfer_request
        )
        main_workflow_id = update_model_transfer_request_json.main_workflow_id
        instance_id = main_workflow_id

        namespace = update_model_transfer_request_json.namespace
        platform = update_model_transfer_request_json.platform

        # Initialize start time on first run
        if not update_model_transfer_request_json.workflow_start_time:
            update_model_transfer_request_json.workflow_start_time = ctx.current_utc_datetime.isoformat()

        # Check overall workflow timeout (30 minutes for model transfer)
        from datetime import datetime

        workflow_start = datetime.fromisoformat(
            update_model_transfer_request_json.workflow_start_time.replace("Z", "+00:00")
        )
        elapsed_minutes = (ctx.current_utc_datetime - workflow_start).total_seconds() / 60
        max_transfer_minutes = 5 * 60

        if elapsed_minutes > max_transfer_minutes:
            logger.error(f"Model transfer workflow exceeded {max_transfer_minutes} minutes timeout")
            response = ErrorResponse(
                message=f"Model transfer timeout after {int(elapsed_minutes)} minutes",
                param={"status": "failed", "reason": "Workflow timeout exceeded"},
                code=HTTPStatus.REQUEST_TIMEOUT.value,
            )
            with DaprClient() as d:
                d.raise_workflow_event(
                    instance_id=str(instance_id),
                    workflow_component="dapr",
                    event_name="model_transfer_completed",
                    event_data=response.model_dump(mode="json"),
                )
            cluster_config = json.loads(update_model_transfer_request_json.cluster_config)
            deployment_handler = DeploymentHandler(config=cluster_config)
            deployment_handler.delete(namespace=namespace, platform=platform)
            return

        notification_request = NotificationRequest.from_cloud_event(
            cloud_event=update_model_transfer_request_json,
            name=update_model_transfer_request_json.workflow_name,
            workflow_id=instance_id,
        )
        notification_req = notification_request.model_copy(deep=True)

        cluster_config = json.loads(update_model_transfer_request_json.cluster_config)
        deployment_handler = DeploymentHandler(config=cluster_config)

        status = deployment_handler.get_model_transfer_status(namespace=namespace)

        if status is not None:
            workflow_status = check_workflow_status_in_statestore(instance_id)
            if workflow_status:
                # cleanup the namespace if workflow is terminated
                deployment_handler.delete(namespace=namespace, platform=platform)
                return status

            if status["status"] == "downloading":
                eta = round(float(status["eta"]) / 60)
                DeploymentService.publish_eta(
                    notification_req, update_model_transfer_request_json, instance_id, "transfer_model_to_cluster", eta
                )

                yield ctx.create_timer(fire_at=ctx.current_utc_datetime + timedelta(minutes=1))
                # Preserve workflow start time when continuing
                ctx.continue_as_new(update_model_transfer_request_json.model_dump_json())
                return

            if status["status"] == "failed":
                # deployment_handler.delete(namespace=namespace, platform=platform)
                response = ErrorResponse(
                    message="Model transfer failed",
                    param=status,
                    code=HTTPStatus.BAD_REQUEST.value,
                )

            if status["status"] == "completed":
                response = SuccessResponse(
                    message="Model transfer completed",
                    param=status,
                )
            with DaprClient() as d:
                d.raise_workflow_event(
                    instance_id=str(instance_id),
                    workflow_component="dapr",
                    event_name="model_transfer_completed",
                    event_data=response.model_dump(mode="json"),
                )
            return

        yield ctx.create_timer(fire_at=ctx.current_utc_datetime + timedelta(minutes=1))
        # Preserve workflow start time when continuing
        ctx.continue_as_new(update_model_transfer_request_json.model_dump_json())

    async def __call__(
        self, request: str, workflow_id: Optional[str] = None
    ) -> Union[WorkflowMetadataResponse, ErrorResponse]:
        """Schedule the workflow to update the model transfer status."""
        return await dapr_workflows.schedule_workflow(
            workflow_name="update_model_transfer_status",
            workflow_input=request,
            workflow_id=str(workflow_id or uuid.uuid4()),
            workflow_steps=[
                WorkflowStep(
                    id="update_model_transfer_status",
                    title="Updating model transfer status",
                    description="Update the model transfer status",
                )
            ],
            eta=1 * 30,
            target_topic_name=None,
            target_name=None,
        )
