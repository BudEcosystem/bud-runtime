import asyncio
import json
import uuid
from datetime import timedelta
from http import HTTPStatus
from typing import Optional, Union

import dapr.ext.workflow as wf
from budmicroframe.commons import logging
from budmicroframe.commons.constants import NotificationCategory, NotificationType, WorkflowStatus  # noqa: F401
from budmicroframe.commons.schemas import (
    ErrorResponse,
    NotificationContent,
    NotificationRequest,
    SuccessResponse,
    WorkflowMetadataResponse,
    WorkflowStep,
)
from budmicroframe.shared.dapr_service import DaprServiceCrypto
from budmicroframe.shared.dapr_workflow import DaprWorkflow
from budmicroframe.shared.psql_service import DBSession
from dapr.clients import DaprClient

from budcluster.deployment.handler import DeploymentHandler

from ..cluster_ops.schemas import VerifyClusterConnection
from ..cluster_ops.workflows import RegisterClusterWorkflow
from ..commons.utils import (
    check_workflow_status_in_statestore,
    save_workflow_status_in_statestore,
    update_workflow_data_in_statestore,
)
from .schemas import (
    DeployQuantizationActivityRequest,
    DeployQuantizationRequest,
    TransferModelRequest,
    UpdateQuantizationStatusRequest,
)
from .services import DeploymentService, QuantizationService
from .workflows import CreateDeploymentWorkflow


logger = logging.get_logger(__name__)

dapr_workflows = DaprWorkflow()

retry_policy = wf.RetryPolicy(
    first_retry_interval=timedelta(seconds=1),
    max_number_of_attempts=3,
    backoff_coefficient=2,
    max_retry_interval=timedelta(seconds=10),
    retry_timeout=timedelta(seconds=100),
)


class DeployQuantizationWorkflow:
    @dapr_workflows.register_activity
    @staticmethod
    def deploy_quantization_job(ctx: wf.WorkflowActivityContext, deploy_quantization_job_request: str):
        """Deploy the quantization job to the cluster."""
        logger = logging.get_logger("DeployQuantizationJob")
        workflow_id = ctx.workflow_id
        task_id = ctx.task_id
        logger.info(f"Deploying quantization job for workflow_id: {workflow_id} and task_id: {task_id}")
        deploy_quantization_job_request_json = DeployQuantizationActivityRequest.model_validate_json(
            deploy_quantization_job_request
        )
        response: Union[SuccessResponse, ErrorResponse]
        try:
            cluster_config = json.loads(deploy_quantization_job_request_json.cluster_config)
            _ = deploy_quantization_job_request_json.simulator_config
            namespace = deploy_quantization_job_request_json.namespace
            platform = deploy_quantization_job_request_json.platform
            _ = deploy_quantization_job_request_json.model
            quantization_name = deploy_quantization_job_request_json.quantization_name

            deployment_handler = DeploymentHandler(config=cluster_config)
            workflow_status = check_workflow_status_in_statestore(workflow_id)
            if workflow_status:
                return workflow_status

            quantization_config = QuantizationService.create_quantization_config(deploy_quantization_job_request_json)
            status = deployment_handler.deploy_quantization(
                namespace=namespace, qunatization_config=quantization_config
            )
            update_workflow_data_in_statestore(
                str(workflow_id),
                {
                    "namespace": namespace,
                    "cluster_config_dict": cluster_config,
                },
            )
            if status == "successful":
                workflow_status = check_workflow_status_in_statestore(workflow_id)
                if workflow_status:
                    # cleanup the namespace if workflow is terminated
                    deployment_handler.delete(namespace=namespace, platform=platform)
                    return workflow_status
                response = SuccessResponse(
                    message="Quantization job deployed successfully",
                    param={
                        "status": status,
                        "namespace": namespace,
                        "quantization_name": quantization_name,
                    },
                )
            else:
                response = ErrorResponse(
                    message=f"Failed to deploy quantization job: {status}", code=HTTPStatus.BAD_REQUEST.value
                )
        except Exception as e:
            error_msg = f"Error deploying engine for workflow_id: {workflow_id} and task_id: {task_id}, error: {e}"
            logger.error(error_msg)
            response = ErrorResponse(message="Failed to deploy runtime", code=HTTPStatus.BAD_REQUEST.value)
        return response.model_dump(mode="json")

    @dapr_workflows.register_workflow
    @staticmethod
    def deploy_quantization(ctx: wf.DaprWorkflowContext, deploy_quantization_request: DeployQuantizationRequest):
        """Deploy quantization."""
        logger.info("Deploying quantization")
        instance_id = str(ctx.instance_id)
        logger.info(f"Creating deployment for instance_id: {instance_id}")
        save_workflow_status_in_statestore(instance_id, WorkflowStatus.RUNNING.value)

        deploy_quantization_request_json = DeployQuantizationRequest.model_validate_json(deploy_quantization_request)

        notification_request = NotificationRequest.from_cloud_event(
            cloud_event=deploy_quantization_request_json, name="deploy_quantization", workflow_id=instance_id
        )
        notification_req = notification_request.model_copy(deep=True)

        # notify activity ETA
        QuantizationService.publish_eta(
            notification_req, deploy_quantization_request_json, instance_id, "verify_cluster_connection"
        )

        # fetch cluster details from db
        with DBSession() as session:
            db_cluster = asyncio.run(
                DeploymentService(session)._get_cluster(deploy_quantization_request_json.cluster_id, missing_ok=True)
            )
            if db_cluster is None:
                logger.error(f"Cluster not found for cluster_id: {deploy_quantization_request_json.cluster_id}")
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
                    target_topic_name=deploy_quantization_request_json.source_topic,
                    target_name=deploy_quantization_request_json.source,
                )
                return
            with DaprServiceCrypto() as dapr_service:
                configuration_decrypted = dapr_service.decrypt_data(db_cluster.configuration)

        deploy_quantization_request_json.cluster_config = configuration_decrypted
        deploy_quantization_request_json.platform = db_cluster.platform

        # verify cluster connection
        verify_cluster_connection_request = VerifyClusterConnection(
            cluster_config=deploy_quantization_request_json.cluster_config,
            platform=deploy_quantization_request_json.platform,
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
                target_topic_name=deploy_quantization_request_json.source_topic,
                target_name=deploy_quantization_request_json.source,
            )
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
            target_topic_name=deploy_quantization_request_json.source_topic,
            target_name=deploy_quantization_request_json.source,
        )

        QuantizationService.publish_eta(
            notification_req, deploy_quantization_request_json, instance_id, "transfer_model_to_cluster"
        )

        # TODO: update simulator config with the simulator service interface
        deploy_quantization_request_json.simulator_config = [
            {
                "name": "dev-server",
                # "name": "ng-bwz4qgjo2e-efd7d",
                "devices": [
                    {
                        "type": "cpu",
                        "image": "budimages.azurecr.io/budecosystem/bud-runtime-cpu:0.09",
                        "replica": 1,
                        "memory": 40762560000,
                        "tp_size": 1,
                        "args": {
                            "tensor-parallel-size": 1,
                            "model": "/data/models-registry/boomer634_92669771",
                            "block-size": 32,
                            "max-num-seqs": 392,
                        },
                        "envs": {
                            # HF_TOKEN should be injected from environment or secrets
                            "VLLM_LOGGING_LEVEL": "INFO",
                            "VLLM_SKIP_WARMUP": "true",
                        },
                        "core_count": 10,
                    }
                ],
            }
        ]

        # transfer model to cluster
        transfer_model_request = TransferModelRequest(
            model=deploy_quantization_request_json.model,
            cluster_config=deploy_quantization_request_json.cluster_config,
            simulator_config=deploy_quantization_request_json.simulator_config,
            endpoint_name=deploy_quantization_request_json.quantization_name,
            platform=deploy_quantization_request_json.platform,
            operation="download",
            storage_size_gb=getattr(deploy_quantization_request_json, "storage_size_gb", None),
            # existing_deployment_namespace=deploy_quantization_request_json.existing_deployment_namespace,
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
                target_topic_name=deploy_quantization_request_json.source_topic,
                target_name=deploy_quantization_request_json.source,
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
            target_topic_name=deploy_quantization_request_json.source_topic,
            target_name=deploy_quantization_request_json.source,
        )

        QuantizationService.publish_eta(
            notification_req, deploy_quantization_request_json, instance_id, "deploy_quantization_job"
        )

        # deploy quantization
        deploy_quantization_activity_request = DeployQuantizationActivityRequest(
            cluster_config=deploy_quantization_request_json.cluster_config,
            simulator_config=deploy_quantization_request_json.simulator_config,
            namespace=transfer_model_result["param"]["namespace"],
            platform=deploy_quantization_request_json.platform,
            model=deploy_quantization_request_json.model,
            quantization_name=deploy_quantization_request_json.quantization_name,
            quantization_config=deploy_quantization_request_json.quantization_config,
        )
        deploy_quantization_result = yield ctx.call_activity(
            DeployQuantizationWorkflow.deploy_quantization_job,
            input=deploy_quantization_activity_request.model_dump_json(),
        )
        logger.info(f"Deploy quantization result: {deploy_quantization_result}")

        if deploy_quantization_result.get("code", HTTPStatus.OK.value) != HTTPStatus.OK.value:
            # notify activity that engine deployment failed
            notification_req.payload.event = "deploy_quantization_job"
            notification_req.payload.content = NotificationContent(
                title="Quantization job deployment failed",
                message=deploy_quantization_result["message"],
                status=WorkflowStatus.FAILED,
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=deploy_quantization_request_json.source_topic,
                target_name=deploy_quantization_request_json.source,
            )
            return

        # notify activity that quantization job deployment is successful
        notification_req.payload.event = "deploy_quantization_job"
        notification_req.payload.content = NotificationContent(
            title="Quantization job deployment successful",
            message=deploy_quantization_result["message"],
            status=WorkflowStatus.COMPLETED,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=deploy_quantization_request_json.source_topic,
            target_name=deploy_quantization_request_json.source,
        )

        deploy_quantization_request_json.cluster_config = {}
        deploy_quantization_request_json.namespace = transfer_model_result["param"]["namespace"]
        logger.info("Scheduling update quantization status workflow")

        update_quantization_status_request = UpdateQuantizationStatusRequest(
            main_workflow_id=instance_id,
            **deploy_quantization_request_json.model_dump(),
        )
        response = asyncio.run(
            UpdateQuantizationStatusWorkflow().__call__(update_quantization_status_request.model_dump_json())
        )

        logger.info(f"Update quantization status workflow response: {response}")

        # Quantization job should be completed with in 24 hrs
        # timeout_event =  ctx.create_timer(fire_at=ctx.current_utc_datetime + timedelta(hours=24))
        # qunatization_completed_event = ctx.wait_for_external_event("quantization_completed")

        # winner = yield wf.when_any([qunatization_completed_event, timeout_event])
        # if winner == timeout_event:
        #     _ = ErrorResponse(message="Failed to complete quantization job", code=HTTPStatus.BAD_REQUEST.value)

        # quantization_result = qunatization_completed_event.get_result()
        # logger.info(f"Quantization result: {quantization_result}")

        # #if quantization is not successful
        # if quantization_result.get("code", HTTPStatus.OK.value) != HTTPStatus.OK.value:
        #     # notify activity that quantization job failed
        #     notification_req.payload.event = "running_quantization"
        #     notification_req.payload.content = NotificationContent(
        #         title="Quantization job failed",
        #         message=quantization_result["message"],
        #         status=WorkflowStatus.FAILED,
        #     )
        #     dapr_workflows.publish_notification(
        #         workflow_id=instance_id,
        #         notification=notification_req,
        #         target_topic_name=deploy_quantization_request_json.source_topic,
        #         target_name=deploy_quantization_request_json.source,
        #     )
        #     return

        # # Upload model to model registry
        # transfer_model_request = TransferModelRequest(
        #     model=deploy_quantization_request_json.model,
        #     cluster_config=deploy_quantization_request_json.cluster_config,
        #     simulator_config=deploy_quantization_request_json.simulator_config,
        #     endpoint_name=deploy_quantization_request_json.quantization_name,
        #     platform=deploy_quantization_request_json.platform,
        #     operation="upload",
        #     # existing_deployment_namespace=deploy_quantization_request_json.existing_deployment_namespace,
        # )
        # transfer_model_result = yield ctx.call_activity(
        #     CreateDeploymentWorkflow.transfer_model, input=transfer_model_request.model_dump_json()
        # )
        # logger.info(f"Upload model result: {transfer_model_result}")

        # # if transfer model is not successful
        # if transfer_model_result.get("code", HTTPStatus.OK.value) != HTTPStatus.OK.value:
        #     # notify activity that model transfer failed
        #     notification_req.payload.event = "upload_model_to_registry"
        #     notification_req.payload.content = NotificationContent(
        #         title="Model upload failed",
        #         message=transfer_model_result["message"],
        #         status=WorkflowStatus.FAILED,
        #     )
        #     dapr_workflows.publish_notification(
        #         workflow_id=instance_id,
        #         notification=notification_req,
        #         target_topic_name=deploy_quantization_request_json.source_topic,
        #         target_name=deploy_quantization_request_json.source,
        #     )
        #     return

        # # notify activity that model transfer is successful
        # notification_req.payload.event = "upload_model_to_registry"
        # notification_req.payload.content = NotificationContent(
        #     title="Model upload successful",
        #     message=transfer_model_result["message"],
        #     status=WorkflowStatus.COMPLETED,
        # )
        # dapr_workflows.publish_notification(
        #     workflow_id=instance_id,
        #     notification=notification_req,
        #     target_topic_name=deploy_quantization_request_json.source_topic,
        #     target_name=deploy_quantization_request_json.source,
        # )

        # workflow_status = check_workflow_status_in_statestore(instance_id)
        # if workflow_status:
        #     return

        # # notify quantization job completed
        # notification_req.payload.event = "results"
        # notification_req.payload.content = NotificationContent(
        #     title="Quantization job completed",
        #     message="Quantization job completed successfully",
        #     status=WorkflowStatus.COMPLETED,
        #     result=deploy_quantization_result.model_dump(mode="json"),
        # )

        # dapr_workflows.publish_notification(
        #     workflow_id=instance_id,
        #     notification=notification_req,
        #     target_topic_name=deploy_quantization_request_json.source_topic,
        #     target_name=deploy_quantization_request_json.source,
        # )

        # return

    def __call__(
        self, request: DeployQuantizationRequest, workflow_id: Optional[str] = None
    ) -> Union[WorkflowMetadataResponse, ErrorResponse]:
        """Schedule the workflow to deploy quantization."""
        workflow_id = str(workflow_id or uuid.uuid4())
        workflow_name = "deploy_quantization"
        workflow_input = request.model_dump_json()
        workflow_steps = [
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
                id="deploy_quantization_job",
                title="Deploying quantization job",
                description="Deploy the quantization job",
            ),
            # WorkflowStep(
            #     id="download_dataset",
            #     title="Downloading dataset",
            #     description="Download the dataset",
            # ),
            WorkflowStep(
                id="running_quantization",
                title="Quantizing the model",
                description="Quantize the model",
            ),
            WorkflowStep(
                id="run_evaluation",
                title="Running evaluation",
                description="Run evaluation",
            ),
            WorkflowStep(
                id="upload_model_to_registry",
                title="Saving model",
                description="Save the model",
            ),
        ]

        response = dapr_workflows.schedule_workflow(
            workflow_name=workflow_name,
            workflow_input=workflow_input,
            workflow_steps=workflow_steps,
            eta=QuantizationService.get_deployment_eta(
                current_step="verify_cluster_connection",
                model_size=request.model_size,
                device_type=request.device_type,
            ),
            target_topic_name=request.source_topic,
            target_name=request.source,
        )
        return response


class UpdateQuantizationStatusWorkflow:
    @dapr_workflows.register_workflow
    @staticmethod
    def update_quantization_status(ctx: wf.DaprWorkflowContext, update_quantization_request: str):
        """Update the quantization status."""
        logger = logging.get_logger("UpdateQuantizationStatus")
        instance_id = str(ctx.instance_id)

        logger.info(f"Updating quantization status for workflow_id: {instance_id}")

        update_quantization_request_json = UpdateQuantizationStatusRequest.model_validate_json(
            update_quantization_request
        )
        main_workflow_id = update_quantization_request_json.main_workflow_id
        instance_id = main_workflow_id

        notification_request = NotificationRequest.from_cloud_event(
            cloud_event=update_quantization_request_json, name="deploy_quantization", workflow_id=instance_id
        )
        notification_req = notification_request.model_copy(deep=True)

        with DBSession() as session:
            db_cluster = asyncio.run(
                DeploymentService(session)._get_cluster(update_quantization_request_json.cluster_id, missing_ok=True)
            )
            if db_cluster is None:
                return

        deployment_handler = DeploymentHandler(config=db_cluster.config_file_dict)
        quantization_data = None
        # get status from cluster
        try:
            job_status, quantization_data = deployment_handler.get_quantization_status(
                update_quantization_request_json.namespace,
            )
            logger.info(f"Update quantization status: {quantization_data}")
            logger.info(f"Job status: {job_status}")

            if job_status == "Failed":
                notification_req.payload.event = "running_quantization"
                notification_req.payload.content = NotificationContent(
                    title="Quantization failed",
                    message="Unable to get quantization resources in cluster",
                    status=WorkflowStatus.FAILED,
                    primary_action="retry",
                )
                dapr_workflows.publish_notification(
                    workflow_id=instance_id,
                    notification=notification_req,
                    target_topic_name=update_quantization_request_json.source_topic,
                    target_name=update_quantization_request_json.source,
                )
                return
            if job_status in ["Running", "Completed"]:
                if not quantization_data:
                    yield ctx.create_timer(fire_at=ctx.current_utc_datetime + timedelta(minutes=3))
                    ctx.continue_as_new(update_quantization_request)
                    return
                if "quantization_eval" in quantization_data:
                    notification_req.payload.event = "run_evaluation"
                    notification_req.payload.content = NotificationContent(
                        title="Quantization evaluation completed",
                        message="Quantization evaluation completed",
                        status=WorkflowStatus.COMPLETED,
                    )
                    dapr_workflows.publish_notification(
                        workflow_id=instance_id,
                        notification=notification_req,
                        target_topic_name=update_quantization_request_json.source_topic,
                        target_name=update_quantization_request_json.source,
                    )
                    response = SuccessResponse(
                        message="Model transferred successfully",
                        param={"status": "Completed", "quantization_data": quantization_data},
                    )
                    with DaprClient() as d:
                        d.raise_workflow_event(
                            instance_id=instance_id,
                            workflow_component="dapr",
                            event_name="quantization_completed",
                            event_data=response.model_dump(mode="json"),
                        )
                    return
                if quantization_data["quantization_progress"] == "success":
                    notification_req.payload.event = "running_quantization"
                    notification_req.payload.content = NotificationContent(
                        title="Quantization completed",
                        message="Quantization completed",
                        status=WorkflowStatus.COMPLETED,
                    )
                    dapr_workflows.publish_notification(
                        workflow_id=instance_id,
                        notification=notification_req,
                        target_topic_name=update_quantization_request_json.source_topic,
                        target_name=update_quantization_request_json.source,
                    )
                    notification_req.payload.event = "run_evaluation"
                    notification_req.payload.content = NotificationContent(
                        title="Quantization evaluation completed",
                        message="Quantization evaluation completed",
                        status=WorkflowStatus.RUNNING,
                    )
                    dapr_workflows.publish_notification(
                        workflow_id=instance_id,
                        notification=notification_req,
                        target_topic_name=update_quantization_request_json.source_topic,
                        target_name=update_quantization_request_json.source,
                    )
                    import time

                    time.sleep(10)
                    # TODO: to be removed after testing
                    notification_req.payload.event = "run_evaluation"
                    notification_req.payload.content = NotificationContent(
                        title="Quantization evaluation completed",
                        message="Quantization evaluation completed",
                        status=WorkflowStatus.COMPLETED,
                    )
                    dapr_workflows.publish_notification(
                        workflow_id=instance_id,
                        notification=notification_req,
                        target_topic_name=update_quantization_request_json.source_topic,
                        target_name=update_quantization_request_json.source,
                    )

                    results = {
                        "model_path": update_quantization_request_json.quantization_name,
                        "quantization_data": quantization_data,
                    }
                    # notify quantization job completed
                    notification_req.payload.event = "results"
                    notification_req.payload.content = NotificationContent(
                        title="Quantization job completed",
                        message="Quantization job completed successfully",
                        status=WorkflowStatus.COMPLETED,
                        result=results,
                    )
                    dapr_workflows.publish_notification(
                        workflow_id=instance_id,
                        notification=notification_req,
                        target_topic_name=update_quantization_request_json.source_topic,
                        target_name=update_quantization_request_json.source,
                    )
                    return
                    yield ctx.create_timer(fire_at=ctx.current_utc_datetime + timedelta(minutes=3))
                    ctx.continue_as_new(update_quantization_request)
                    return

                yield ctx.create_timer(fire_at=ctx.current_utc_datetime + timedelta(minutes=3))
                ctx.continue_as_new(update_quantization_request)
                return

        except Exception as e:
            logger.error(f"Error updating deployment status: {e}")
            import traceback

            logger.error(traceback.format_exc())
            return

        if quantization_data is None:
            yield ctx.create_timer(fire_at=ctx.current_utc_datetime + timedelta(minutes=3))
            ctx.continue_as_new(update_quantization_request)
            return

        if quantization_data["quantization_progress"] == "success":
            notification_req.payload.event = "running_quantization"
            notification_req.payload.content = NotificationContent(
                title="Quantization completed",
                message="Quantization completed",
                status=WorkflowStatus.COMPLETED,
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=update_quantization_request_json.source_topic,
                target_name=update_quantization_request_json.source,
            )

            notification_req.payload.event = "run_evaluation"
            notification_req.payload.content = NotificationContent(
                title="Quantization evaluation completed",
                message="Quantization evaluation completed",
                status=WorkflowStatus.RUNNING,
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=update_quantization_request_json.source_topic,
                target_name=update_quantization_request_json.source,
            )
            import time

            time.sleep(10)
            # TODO: to be removed after testing
            notification_req.payload.event = "run_evaluation"
            notification_req.payload.content = NotificationContent(
                title="Quantization evaluation completed",
                message="Quantization evaluation completed",
                status=WorkflowStatus.COMPLETED,
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=update_quantization_request_json.source_topic,
                target_name=update_quantization_request_json.source,
            )

            results = {
                "model_path": update_quantization_request_json.quantization_name,
                "quantization_data": quantization_data,
            }
            # notify quantization job completed
            notification_req.payload.event = "results"
            notification_req.payload.content = NotificationContent(
                title="Quantization job completed",
                message="Quantization job completed successfully",
                status=WorkflowStatus.COMPLETED,
                result=results,
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=update_quantization_request_json.source_topic,
                target_name=update_quantization_request_json.source,
            )
            return
        yield ctx.create_timer(fire_at=ctx.current_utc_datetime + timedelta(minutes=3))
        ctx.continue_as_new(update_quantization_request)

    def __call__(
        self, request: str, workflow_id: Optional[str] = None
    ) -> Union[WorkflowMetadataResponse, ErrorResponse]:
        """Schedule the workflow to update the quantization status."""
        return dapr_workflows.schedule_workflow(
            workflow_name="update_quantization_status",
            workflow_input=request,
            workflow_id=str(workflow_id or uuid.uuid4()),
            workflow_steps=[
                WorkflowStep(
                    id="update_deployment_status",
                    title="Updating deployment status",
                    description="Update the deployment status",
                ),
            ],
            eta=1 * 30,
            target_topic_name=None,
            target_name=None,
        )
