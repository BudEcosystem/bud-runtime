import asyncio
import json
import time
import uuid
from http import HTTPStatus
from typing import Optional, Union

import dapr.ext.workflow as wf
from budmicroframe.commons import logging
from budmicroframe.commons.config import app_settings
from budmicroframe.commons.constants import WorkflowStatus
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

from budcluster.deployment.handler import DeploymentHandler

from ..cluster_ops.schemas import VerifyClusterConnection
from ..cluster_ops.workflows import RegisterClusterWorkflow
from ..commons.utils import (
    check_workflow_status_in_statestore,
    save_workflow_status_in_statestore,
    update_workflow_data_in_statestore,
)
from .schemas import AdapterRequest, DeployAdapterActivityRequest, TransferModelRequest
from .services import AdapterService, DeploymentService
from .workflows import CreateDeploymentWorkflow


logger = logging.get_logger(__name__)

dapr_workflows = DaprWorkflow()


class AdapterWorkflow:
    @dapr_workflows.register_activity
    @staticmethod
    def deploy_adapter(ctx: wf.WorkflowActivityContext, deploy_adapter_request: str):
        """Deploy adapter."""
        logger.info("Deploying adapter")
        workflow_id = ctx.workflow_id
        task_id = ctx.task_id
        logger.info(f"Deploying adapter for workflow_id: {workflow_id} and task_id: {task_id}")
        deploy_adapter_request_json = DeployAdapterActivityRequest.model_validate_json(deploy_adapter_request)

        response: Union[SuccessResponse, ErrorResponse]

        try:
            cluster_config = json.loads(deploy_adapter_request_json.cluster_config)

            deployment_handler = DeploymentHandler(config=cluster_config)

            workflow_status = check_workflow_status_in_statestore(workflow_id)
            if workflow_status:
                return workflow_status
            status, namespace, _, _, _ = deployment_handler.deploy(
                node_list=deploy_adapter_request_json.simulator_config,
                endpoint_name=deploy_adapter_request_json.endpoint_name,
                namespace=deploy_adapter_request_json.namespace,
                ingress_url=deploy_adapter_request_json.ingress_url,
                platform=deploy_adapter_request_json.platform,
                adapters=deploy_adapter_request_json.adapters,
                delete_on_failure=False,
                input_tokens=deploy_adapter_request_json.input_tokens,
                output_tokens=deploy_adapter_request_json.output_tokens,
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
                    return workflow_status
                response = SuccessResponse(
                    message="Adapter deployed successfully",
                    param={"status": status},
                )
            else:
                response = ErrorResponse(message="Failed to deploy adapter", code=HTTPStatus.BAD_REQUEST.value)
        except Exception as e:
            error_msg = f"Error deploying adapter for workflow_id: {workflow_id} and task_id: {task_id}, error: {e}"
            logger.error(error_msg)
            response = ErrorResponse(message="Failed to deploy adapter", code=HTTPStatus.BAD_REQUEST.value)
        return response.model_dump(mode="json")

    @dapr_workflows.register_workflow
    @staticmethod
    def add_adapter(ctx: wf.DaprWorkflowContext, add_adapter_request: AdapterRequest):
        """Add adapter."""
        logger.info("Adding adapter")
        instance_id = str(ctx.instance_id)
        logger.info(f"Creating deployment for instance_id: {instance_id}")
        save_workflow_status_in_statestore(instance_id, WorkflowStatus.RUNNING.value)

        add_adapter_request_json = AdapterRequest.model_validate_json(add_adapter_request)

        notification_request = NotificationRequest.from_cloud_event(
            cloud_event=add_adapter_request_json, name="add_adapter", workflow_id=instance_id
        )
        notification_req = notification_request.model_copy(deep=True)

        # notify activity ETA
        AdapterService.publish_eta(
            notification_req, add_adapter_request_json, instance_id, "verify_cluster_connection"
        )

        # fetch cluster details from db
        with DBSession() as session:
            db_cluster = asyncio.run(
                DeploymentService(session)._get_cluster(add_adapter_request_json.cluster_id, missing_ok=True)
            )
            if db_cluster is None:
                logger.error(f"Cluster not found for cluster_id: {add_adapter_request_json.cluster_id}")
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
                    target_topic_name=add_adapter_request_json.source_topic,
                    target_name=add_adapter_request_json.source,
                )
                return
            with DaprServiceCrypto() as dapr_service:
                configuration_decrypted = dapr_service.decrypt_data(db_cluster.configuration)

        cluster_config = configuration_decrypted
        platform = db_cluster.platform

        # verify cluster connection
        verify_cluster_connection_request = VerifyClusterConnection(
            cluster_config=cluster_config,
            platform=platform,
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
                target_topic_name=add_adapter_request_json.source_topic,
                target_name=add_adapter_request_json.source,
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
            target_topic_name=add_adapter_request_json.source_topic,
            target_name=add_adapter_request_json.source,
        )

        AdapterService.publish_eta(
            notification_req, add_adapter_request_json, instance_id, "transfer_adapter_to_cluster"
        )

        simulator_config = []
        with DaprService() as dapr_service:
            deploy_config = dapr_service.get_state(
                store_name=app_settings.statestore_name,
                key=f"deploy_config_{add_adapter_request_json.namespace}",
            )
            simulator_config = json.loads(deploy_config.data) if deploy_config.data else []

        # transfer model to cluster
        transfer_model_request = TransferModelRequest(
            model=add_adapter_request_json.adapter_path,
            cluster_config=cluster_config,
            simulator_config=simulator_config,
            endpoint_name=add_adapter_request_json.endpoint_name,
            platform=platform,
            operation="download",
            existing_deployment_namespace=add_adapter_request_json.namespace,
        )
        transfer_model_result = yield ctx.call_activity(
            CreateDeploymentWorkflow.transfer_model, input=transfer_model_request.model_dump_json()
        )
        logger.info(f"Transfer adapter result: {transfer_model_result}")

        # if transfer model is not successful
        if transfer_model_result.get("code", HTTPStatus.OK.value) != HTTPStatus.OK.value:
            # notify activity that model transfer failed
            notification_req.payload.event = "transfer_adapter_to_cluster"
            notification_req.payload.content = NotificationContent(
                title="Adapter transfer failed",
                message=transfer_model_result["message"],
                status=WorkflowStatus.FAILED,
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=add_adapter_request_json.source_topic,
                target_name=add_adapter_request_json.source,
            )
            return

        # notify activity that model transfer is successful
        notification_req.payload.event = "transfer_adapter_to_cluster"
        notification_req.payload.content = NotificationContent(
            title="Adapter transfer successful",
            message=transfer_model_result["message"],
            status=WorkflowStatus.COMPLETED,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=add_adapter_request_json.source_topic,
            target_name=add_adapter_request_json.source,
        )

        AdapterService.publish_eta(notification_req, add_adapter_request_json, instance_id, "deploy_adapter")

        adapters = []
        for adapter in add_adapter_request_json.adapters:
            adapter["artifactURL"] = app_settings.model_registry_path + adapter["artifactURL"]
            adapters.append(adapter)

        deploy_adapter_activity_request = DeployAdapterActivityRequest(
            cluster_config=cluster_config,
            simulator_config=simulator_config,
            namespace=add_adapter_request_json.namespace,
            platform=platform,
            adapters=add_adapter_request_json.adapters,
            endpoint_name=add_adapter_request_json.endpoint_name,
            ingress_url=add_adapter_request_json.ingress_url,
            input_tokens=add_adapter_request_json.input_tokens,
            output_tokens=add_adapter_request_json.output_tokens,
        )
        deploy_adapter_result = yield ctx.call_activity(
            AdapterWorkflow.deploy_adapter, input=deploy_adapter_activity_request.model_dump_json()
        )
        logger.info(f"Deploy adapter result: {deploy_adapter_result}")

        if deploy_adapter_result.get("code", HTTPStatus.OK.value) != HTTPStatus.OK.value:
            # notify activity that engine deployment failed
            notification_req.payload.event = "deploy_adapter"
            notification_req.payload.content = NotificationContent(
                title="Adapter deployment failed",
                message=deploy_adapter_result["message"],
                status=WorkflowStatus.FAILED,
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=add_adapter_request_json.source_topic,
                target_name=add_adapter_request_json.source,
            )
            return

        # notify activity that adapter deployment is successful
        notification_req.payload.event = "deploy_adapter"
        notification_req.payload.content = NotificationContent(
            title="Adapter deployment successful",
            message=deploy_adapter_result["message"],
            status=WorkflowStatus.COMPLETED,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=add_adapter_request_json.source_topic,
            target_name=add_adapter_request_json.source,
        )

        AdapterService.publish_eta(notification_req, add_adapter_request_json, instance_id, "adapter_status")

        # wait for 60 seconds to get the adapter status
        time.sleep(60)
        cluster_config = json.loads(cluster_config)
        deployment_handler = DeploymentHandler(config=cluster_config)
        logger.info(f"within adapter workflow: {add_adapter_request_json.adapter_name}")
        adapter_status = deployment_handler.get_adapter_status(
            add_adapter_request_json.adapter_name, add_adapter_request_json.ingress_url
        )
        logger.info(f"adapter status: {adapter_status}")

        if not adapter_status:
            notification_req.payload.event = "adapter_status"
            notification_req.payload.content = NotificationContent(
                title="Adapter deployment failed",
                message="Adapter deployment failed",
                status=WorkflowStatus.FAILED,
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=add_adapter_request_json.source_topic,
                target_name=add_adapter_request_json.source,
            )
            return

        notification_req.payload.event = "adapter_status"
        notification_req.payload.content = NotificationContent(
            title="Adapter deployment completed",
            message="Adapter deployment completed",
            status=WorkflowStatus.COMPLETED,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=add_adapter_request_json.source_topic,
            target_name=add_adapter_request_json.source,
        )

        results = {
            "adapter_status": adapter_status,
            "deployment_name": add_adapter_request_json.adapter_name,
        }

        # notify adapter deployment completed
        notification_req.payload.event = "results"
        notification_req.payload.content = NotificationContent(
            title="Adapter deployment completed",
            message="Adapter deployment completed successfully",
            status=WorkflowStatus.COMPLETED,
            result=results,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=add_adapter_request_json.source_topic,
            target_name=add_adapter_request_json.source,
        )

    def __call__(
        self, request: AdapterRequest, workflow_id: Optional[str] = None
    ) -> Union[WorkflowMetadataResponse, ErrorResponse]:
        """Schedule the workflow to add an adapter."""
        workflow_id = str(workflow_id or uuid.uuid4())
        workflow_name = "add_adapter"
        workflow_input = request.model_dump_json()
        workflow_steps = [
            WorkflowStep(
                id="verify_cluster_connection",
                title="Verifying cluster connection",
                description="Verify the cluster connection",
            ),
            WorkflowStep(
                id="transfer_adapter_to_cluster",
                title="Transferring Adapter to cluster",
                description="Transfer the adapter to the cluster",
            ),
            WorkflowStep(
                id="deploy_adapter",
                title="Deploying adapter",
                description="Deploy the adapter",
            ),
            WorkflowStep(
                id="adapter_status",
                title="Adapter status",
                description="Check the adapter status",
            ),
        ]

        # TODO: update eta
        response = dapr_workflows.schedule_workflow(
            workflow_name=workflow_name,
            workflow_input=workflow_input,
            workflow_steps=workflow_steps,
            eta=20,
            target_topic_name=request.source_topic,
            target_name=request.source,
        )
        return response


class DeleteAdapterWorkflow:
    @dapr_workflows.register_workflow
    @staticmethod
    def delete_adapter(ctx: wf.DaprWorkflowContext, delete_adapter_request: str):
        """Delete adapter."""
        logger.info("Deleting adapter")
        instance_id = str(ctx.instance_id)
        logger.info(f"Deleting deployment for instance_id: {instance_id}")
        save_workflow_status_in_statestore(instance_id, WorkflowStatus.RUNNING.value)

        delete_adapter_request_json = AdapterRequest.model_validate_json(delete_adapter_request)

        notification_request = NotificationRequest.from_cloud_event(
            cloud_event=delete_adapter_request_json, name="delete_adapter", workflow_id=instance_id
        )
        notification_req = notification_request.model_copy(deep=True)

        # fetch cluster details from db
        with DBSession() as session:
            db_cluster = asyncio.run(
                DeploymentService(session)._get_cluster(delete_adapter_request_json.cluster_id, missing_ok=True)
            )
            if db_cluster is None:
                logger.error(f"Cluster not found for cluster_id: {delete_adapter_request_json.cluster_id}")
                # notify activity that cluster verification failed
                notification_req.payload.event = "perform_delete_adapter"
                notification_req.payload.content = NotificationContent(
                    title="Cluster connection verification failed",
                    message="Cluster not found",
                    status=WorkflowStatus.FAILED,
                    primary_action="retry",
                )
                dapr_workflows.publish_notification(
                    workflow_id=instance_id,
                    notification=notification_req,
                    target_topic_name=delete_adapter_request_json.source_topic,
                    target_name=delete_adapter_request_json.source,
                )
                return
            with DaprServiceCrypto() as dapr_service:
                configuration_decrypted = dapr_service.decrypt_data(db_cluster.configuration)

        cluster_config = configuration_decrypted
        platform = db_cluster.platform

        simulator_config = []
        with DaprService() as dapr_service:
            deploy_config = dapr_service.get_state(
                store_name=app_settings.statestore_name,
                key=f"deploy_config_{delete_adapter_request_json.namespace}",
            )
            simulator_config = json.loads(deploy_config.data) if deploy_config.data else []

        adapters = []
        for adapter in delete_adapter_request_json.adapters:
            adapter["artifactURL"] = app_settings.model_registry_path + adapter["artifactURL"]
            adapters.append(adapter)

        deploy_adapter_activity_request = DeployAdapterActivityRequest(
            cluster_config=cluster_config,
            simulator_config=simulator_config,
            namespace=delete_adapter_request_json.namespace,
            platform=platform,
            adapters=delete_adapter_request_json.adapters,
            endpoint_name=delete_adapter_request_json.endpoint_name,
            ingress_url=delete_adapter_request_json.ingress_url,
            input_tokens=delete_adapter_request_json.input_tokens,
            output_tokens=delete_adapter_request_json.output_tokens,
        )
        deploy_adapter_result = yield ctx.call_activity(
            AdapterWorkflow.deploy_adapter, input=deploy_adapter_activity_request.model_dump_json()
        )
        logger.info(f"Deploy adapter result: {deploy_adapter_result}")

        if deploy_adapter_result.get("code", HTTPStatus.OK.value) != HTTPStatus.OK.value:
            # notify activity that engine deployment failed
            notification_req.payload.event = "perform_delete_adapter"
            notification_req.payload.content = NotificationContent(
                title="Adapter deletion failed",
                message=deploy_adapter_result["message"],
                status=WorkflowStatus.FAILED,
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=delete_adapter_request_json.source_topic,
                target_name=delete_adapter_request_json.source,
            )
            return

        # notify activity that adapter deletion is successful
        notification_req.payload.event = "perform_delete_adapter"
        notification_req.payload.content = NotificationContent(
            title="Adapter deletion successful",
            message=deploy_adapter_result["message"],
            status=WorkflowStatus.COMPLETED,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=delete_adapter_request_json.source_topic,
            target_name=delete_adapter_request_json.source,
        )

        # notify adapter deletion completed
        notification_req.payload.event = "results"
        notification_req.payload.content = NotificationContent(
            title="Adapter deleted successfully",
            message="Adapter deletion completed successfully",
            status=WorkflowStatus.COMPLETED,
            result={"adapter_id": str(delete_adapter_request_json.adapter_id)},
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=delete_adapter_request_json.source_topic,
            target_name=delete_adapter_request_json.source,
        )

        return

    def __call__(
        self, request: AdapterRequest, workflow_id: Optional[str] = None
    ) -> Union[WorkflowMetadataResponse, ErrorResponse]:
        """Schedule the workflow to delete an adapter."""
        workflow_id = str(workflow_id or uuid.uuid4())
        workflow_name = "delete_adapter"
        workflow_input = request.model_dump_json()
        workflow_steps = [
            WorkflowStep(
                id="perform_delete_adapter",
                title="Deleting adapter",
                description="Deleting the adapter",
            )
        ]

        # TODO: update eta
        response = dapr_workflows.schedule_workflow(
            workflow_name=workflow_name,
            workflow_input=workflow_input,
            workflow_steps=workflow_steps,
            eta=20,
            target_topic_name=request.source_topic,
            target_name=request.source,
        )
        return response
