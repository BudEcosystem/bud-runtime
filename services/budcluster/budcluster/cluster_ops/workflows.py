import asyncio
import hashlib
import json
import traceback
import uuid
from datetime import timedelta
from http import HTTPStatus
from typing import Optional, Union

import dapr.ext.workflow as wf
import yaml
from budmicroframe.commons import logging
from budmicroframe.commons.constants import NotificationCategory, NotificationType, WorkflowStatus
from budmicroframe.commons.schemas import (
    ErrorResponse,
    NotificationContent,
    NotificationPayload,
    NotificationRequest,
    SuccessResponse,
    WorkflowMetadataResponse,
    WorkflowStep,
)
from budmicroframe.shared.dapr_service import DaprService, DaprServiceCrypto

# from .dapr_workflow import DaprWorkflow
from budmicroframe.shared.dapr_workflow import DaprWorkflow

# from ..commons.database import SessionLocal
from budmicroframe.shared.psql_service import DBSession

from ..commons.constants import ClusterPlatformEnum
from ..commons.utils import (
    check_workflow_status_in_statestore,
    get_workflow_data_from_statestore,
    update_workflow_data_in_statestore,
)
from ..deployment.handler import DeploymentHandler
from ..terraform.aks_terraform import AzureAksManager
from ..terraform.eks_terraform import AWSEksManager
from . import get_cluster_hostname, get_cluster_server_url
from .crud import ClusterDataManager
from .schemas import (
    CheckDuplicateConfig,
    ClusterCreateRequest,
    ClusterDeleteRequest,
    ConfigureCluster,
    CreateCloudProviderClusterActivityRequest,
    CreateCloudProviderClusterRequest,
    DeleteCluster,
    DetermineClusterPlatformRequest,
    FetchClusterInfo,
    VerifyClusterConnection,
)
from .services import ClusterOpsService, ClusterService
from .terrafrom_schemas import AWSConfig, AzureConfig, TagsModel


logger = logging.get_logger(__name__)

dapr_workflows = DaprWorkflow()

retry_policy = wf.RetryPolicy(
    first_retry_interval=timedelta(seconds=1),
    max_number_of_attempts=3,
    backoff_coefficient=2,
    max_retry_interval=timedelta(seconds=10),
    retry_timeout=timedelta(seconds=100),
)


class RegisterClusterWorkflow:
    @dapr_workflows.register_activity
    @staticmethod
    def determine_cluster_platform(
        ctx: wf.WorkflowActivityContext,
        determine_cluster_platform_request: str,
    ) -> dict:
        """Determine the cluster platform."""
        logger = logging.get_logger("DetermineClusterPlatform")
        workflow_id = ctx.workflow_id
        task_id = ctx.task_id
        logger.info(f"Determining cluster platform for workflow_id: {workflow_id} and task_id: {task_id}")
        determine_cluster_platform_request_json = DetermineClusterPlatformRequest.model_validate_json(
            determine_cluster_platform_request
        )
        cluster_config = json.loads(determine_cluster_platform_request_json.cluster_config)  # configuration string
        response: Union[SuccessResponse, ErrorResponse]
        try:
            cluster_platform = asyncio.run(
                ClusterOpsService.determine_cluster_platform(cluster_config, task_id, workflow_id)
            )
            # Openshift doesn't support master node
            # if cluster_platform == ClusterPlatformEnum.OPENSHIFT and enable_master_node:
            #     logger.debug("OpenShift doesn't support master node")
            #     response = ErrorResponse(
            #         message="OpenShift doesn't support master node", code=HTTPStatus.BAD_REQUEST.value
            #     )
            # else:
            # Get cluster hostname
            hostname = asyncio.run(get_cluster_hostname(cluster_config, cluster_platform))
            # Get cluster server url
            server_url = asyncio.run(get_cluster_server_url(cluster_config))
            if not hostname:
                response = ErrorResponse(message="Failed to get cluster hostname", code=HTTPStatus.BAD_REQUEST.value)
            else:
                update_workflow_data_in_statestore(
                    str(workflow_id),
                    {
                        "platform": cluster_platform,
                        "hostname": hostname,
                        "server_url": server_url,
                    },
                )
                response = SuccessResponse(
                    message="Cluster platform determined successfully",
                    param={"cluster_platform": cluster_platform, "hostname": hostname, "server_url": server_url},
                )
        except Exception as e:
            error_msg = (
                f"Error determining cluster platform for workflow_id: {workflow_id} and task_id: {task_id}, error: {e}"
            )
            logger.error(error_msg)
            response = ErrorResponse(
                message="Cluster platform determination failed", code=HTTPStatus.BAD_REQUEST.value
            )
        return response.model_dump(mode="json")

    @dapr_workflows.register_activity
    @staticmethod
    def check_duplicate_config(
        ctx: wf.WorkflowActivityContext,
        check_duplicate_config_request: str,
    ) -> dict:
        """Check for duplicate cluster config."""
        logger = logging.get_logger("CheckDuplicateConfig")
        workflow_id = ctx.workflow_id
        task_id = ctx.task_id
        logger.info(f"Checking for duplicate cluster config for workflow_id: {workflow_id} and task_id: {task_id}")
        check_duplicate_config_request_json = CheckDuplicateConfig.model_validate_json(check_duplicate_config_request)
        workflow_data = get_workflow_data_from_statestore(str(workflow_id))
        if workflow_data and workflow_data.get("check_duplicate_config", "not_done") == "done":
            response = SuccessResponse(message="Duplicate cluster config already checked")
        else:
            with DBSession() as session:
                server_url = check_duplicate_config_request_json.server_url
                platform = check_duplicate_config_request_json.platform.value
                response = asyncio.run(ClusterService(session)._check_duplicate_config(server_url, platform))
                if response.code == HTTPStatus.OK.value:
                    update_workflow_data_in_statestore(
                        str(workflow_id),
                        {
                            "check_duplicate_config": "done",
                        },
                    )
        return response.model_dump(mode="json")

    @dapr_workflows.register_activity
    @staticmethod
    def verify_cluster_connection(
        ctx: wf.WorkflowActivityContext,
        verify_cluster_connection_request: str,
    ) -> dict:
        """Verify the cluster connection."""
        logger = logging.get_logger("VerifyClusterConnection")
        workflow_id = ctx.workflow_id
        task_id = ctx.task_id
        logger.info(f"Verifying cluster connection for workflow_id: {workflow_id} and task_id: {task_id}")
        verify_cluster_connection_request_json = VerifyClusterConnection.model_validate_json(
            verify_cluster_connection_request
        )
        response: Union[SuccessResponse, ErrorResponse]
        try:
            cluster_verified = asyncio.run(
                ClusterOpsService.verify_cluster_connection(
                    verify_cluster_connection_request_json, task_id, workflow_id
                )
            )
            response = SuccessResponse(
                message="Cluster connection verified successfully", param={"cluster_verified": cluster_verified}
            )
        except Exception as e:
            error_msg = (
                f"Error verifying cluster connection for workflow_id: {workflow_id} and task_id: {task_id}, error: {e}"
            )
            logger.error(error_msg)
            response = ErrorResponse(
                message="Cluster connection verification failed", code=HTTPStatus.BAD_REQUEST.value
            )
        return response.model_dump(mode="json")

    @dapr_workflows.register_activity
    @staticmethod
    def configure_cluster(ctx: wf.WorkflowActivityContext, configure_cluster_request: str) -> dict:
        """Configure the cluster."""
        logger = logging.get_logger("ConfigureCluster")
        workflow_id = ctx.workflow_id
        task_id = ctx.task_id
        logger.info(f"Configuring cluster for workflow_id: {workflow_id} and task_id: {task_id}")
        configure_cluster_request_json = ConfigureCluster.model_validate_json(configure_cluster_request)
        response: Union[SuccessResponse, ErrorResponse]
        try:
            workflow_status = check_workflow_status_in_statestore(workflow_id)
            if workflow_status:
                return workflow_status
            #  Cluster ID Available
            workflow_data = get_workflow_data_from_statestore(str(workflow_id))
            if workflow_data and workflow_data.get("configuration_status", "not_successful") == "successful":
                # Cluster ID
                cluster_id = workflow_data["cluster_id"]
                configuration_status = workflow_data["configuration_status"]
                response = SuccessResponse(
                    message="Cluster configured successfully",
                    param={"configuration_status": configuration_status, "cluster_id": str(cluster_id)},
                )
            else:
                configuration_status, cluster_id = asyncio.run(
                    ClusterOpsService.configure_cluster(configure_cluster_request_json, task_id, workflow_id)
                )
                configuration_status = "successful"
                if configuration_status == "successful":
                    namespace = "bud-system"
                    update_workflow_data_in_statestore(
                        str(workflow_id),
                        {
                            "namespace": namespace,
                            "configuration_status": configuration_status,
                            "cluster_config_dict": configure_cluster_request_json.config_dict,
                            "cluster_id": str(cluster_id),
                        },
                    )
                    response = SuccessResponse(
                        message="Cluster configured successfully",
                        param={"configuration_status": configuration_status, "cluster_id": str(cluster_id)},
                    )
                else:
                    # Update cluster status to NOT_AVAILABLE when configuration fails
                    try:
                        from budmicroframe.shared.psql_service import DBSession

                        from ..commons.constants import ClusterStatusEnum
                        from .crud import ClusterDataManager

                        if cluster_id:
                            with DBSession() as session:
                                db_cluster = asyncio.run(
                                    ClusterDataManager(session).retrieve_cluster_by_fields({"id": cluster_id})
                                )
                                if db_cluster:
                                    asyncio.run(
                                        ClusterDataManager(session).update_cluster_by_fields(
                                            db_cluster, {"status": ClusterStatusEnum.NOT_AVAILABLE}
                                        )
                                    )
                                    logger.info(
                                        f"Marked cluster {cluster_id} as NOT_AVAILABLE due to configuration failure"
                                    )
                    except Exception as db_e:
                        logger.error(f"Failed to update cluster status on configuration failure: {db_e}")

                    response = ErrorResponse(message="Cluster configuration failed", code=HTTPStatus.BAD_REQUEST.value)
            workflow_status = check_workflow_status_in_statestore(workflow_id)
            if workflow_status:
                workflow_data = get_workflow_data_from_statestore(str(workflow_id))
                cluster_id = workflow_data.get("cluster_id")
                if cluster_id:
                    with DBSession() as session:
                        db_cluster = asyncio.run(ClusterService(session)._get_cluster(cluster_id, missing_ok=True))
                        if db_cluster:
                            asyncio.run(ClusterDataManager(session).delete_cluster(db_cluster=db_cluster))
                # cleanup the namespace if workflow is terminated
                deployement_handler = DeploymentHandler(config=configure_cluster_request_json.config_dict)
                deployement_handler.delete(namespace=namespace, platform=configure_cluster_request_json.platform)
                return workflow_status
        except Exception as e:
            error_msg = f"Error configuring cluster for workflow_id: {workflow_id} and task_id: {task_id}, error: {e}"
            logger.error(error_msg)

            # Update cluster status to NOT_AVAILABLE on configuration failure
            try:
                from ..commons.constants import ClusterStatusEnum

                workflow_data = get_workflow_data_from_statestore(str(workflow_id))
                cluster_id = workflow_data.get("cluster_id") if workflow_data else None

                if cluster_id:
                    with DBSession() as session:
                        db_cluster = asyncio.run(
                            ClusterDataManager(session).retrieve_cluster_by_fields({"id": cluster_id})
                        )
                        if db_cluster:
                            asyncio.run(
                                ClusterDataManager(session).update_cluster_by_fields(
                                    db_cluster, {"status": ClusterStatusEnum.NOT_AVAILABLE}
                                )
                            )
                            logger.info(
                                f"Marked cluster {cluster_id} as NOT_AVAILABLE due to configure_cluster failure"
                            )
            except Exception as db_e:
                logger.error(f"Failed to update cluster status on configure_cluster failure: {db_e}")

            response = ErrorResponse(message="Cluster configuration failed", code=HTTPStatus.BAD_REQUEST.value)
        return response.model_dump(mode="json")

    @dapr_workflows.register_activity
    @staticmethod
    def provision_cluster(ctx: wf.WorkflowActivityContext, provision_cluster_request: str) -> dict:
        """Provision the cluster."""
        logger = logging.get_logger("ProvisionCluster")
        workflow_id = ctx.workflow_id
        task_id = ctx.task_id

        try:
            pass
        except Exception as e:
            error_msg = f"Error provisioning cluster for workflow_id: {workflow_id} and task_id: {task_id}, error: {e}"
            logger.error(error_msg)
            response = ErrorResponse(message="Cluster provisioning failed", code=HTTPStatus.BAD_REQUEST.value)
        return response.model_dump(mode="json")

    @dapr_workflows.register_activity
    @staticmethod
    def fetch_cluster_info(
        ctx: wf.WorkflowActivityContext,
        fetch_cluster_info_request: str,
    ) -> dict:
        """Fetch the cluster info from the cluster."""
        logger = logging.get_logger("FetchClusterInfo")
        workflow_id = ctx.workflow_id
        task_id = ctx.task_id
        logger.info(f"Fetching cluster info for workflow_id: {workflow_id} and task_id: {task_id}")
        fetch_cluster_info_json = FetchClusterInfo.model_validate_json(fetch_cluster_info_request)
        try:
            workflow_status = check_workflow_status_in_statestore(workflow_id)
            if workflow_status:
                return workflow_status
            workflow_data = get_workflow_data_from_statestore(str(workflow_id))
            if workflow_data and workflow_data.get("node_info"):
                result = workflow_data["node_info"]
            else:
                result = asyncio.run(
                    ClusterOpsService.fetch_cluster_info(fetch_cluster_info_json, task_id, workflow_id)
                )
            logger.info(f"Fetched cluster info: {result}")
            if result:
                result_json = json.loads(result)
                cluster_id = result_json.get("id")
                logger.info(f"Cluster id in fetch cluster info: {cluster_id}")
                workflow_status = check_workflow_status_in_statestore(workflow_id)
                if workflow_status and cluster_id:
                    # not deleting 'bud-system' namespace here, as it is already deleted in the configure_cluster activity
                    # or cancel_cluster_registration background task
                    with DBSession() as session:
                        db_cluster = asyncio.run(ClusterService(session)._get_cluster(cluster_id, missing_ok=True))
                        if db_cluster:
                            asyncio.run(ClusterDataManager(session).delete_cluster(db_cluster=db_cluster))
                    return workflow_status
                response = SuccessResponse(
                    message="Cluster info fetched successfully",
                    param={"result": result},
                )
        except Exception as e:
            error_msg = (
                f"Error fetching cluster info for workflow_id: {workflow_id} and task_id: {task_id}, error: {e}"
            )
            logger.error(error_msg)
            response = ErrorResponse(message="Fetching cluster info failed", code=HTTPStatus.BAD_REQUEST.value)
        return response.model_dump(mode="json")

    @dapr_workflows.register_activity  # type: ignore
    @staticmethod
    def get_cloud_provider_credentials(ctx: wf.WorkflowActivityContext, cloud_provider_request: str) -> dict:
        """Process and validate the cloud provider credentials."""
        logger = logging.get_logger("GetCloudProviderCredentials")
        workflow_id = ctx.workflow_id
        task_id = ctx.task_id
        logger.info(f"Processing cloud provider credentials for workflow_id: {workflow_id} and task_id: {task_id}")

        try:
            create_cluster_request_json = CreateCloudProviderClusterActivityRequest.model_validate_json(
                cloud_provider_request
            )

            config: AzureConfig | AWSConfig | None = None

            logger.debug(f"===== Unique ID: {create_cluster_request_json.cloud_provider_unique_id}")

            match create_cluster_request_json.cloud_provider_unique_id:
                case "azure":
                    required_fields = ["subscription_id", "tenant_id", "client_id", "client_secret"]
                    for field in required_fields:
                        if field not in create_cluster_request_json.config_credentials:  # type: ignore
                            raise ValueError(f"Missing required credential field: {field}")
                    config = AzureConfig(
                        subscription_id=create_cluster_request_json.config_credentials["subscription_id"],  # type: ignore
                        tenant_id=create_cluster_request_json.config_credentials["tenant_id"],  # type: ignore
                        client_id=create_cluster_request_json.config_credentials["client_id"],  # type: ignore
                        client_secret=create_cluster_request_json.config_credentials["client_secret"],  # type: ignore
                        cluster_name=create_cluster_request_json.name,
                        cluster_location=create_cluster_request_json.region,
                        resource_group_name=f"{create_cluster_request_json.name}-bud-inc",
                        tags=TagsModel(
                            Environment="Production",
                            Project="Bud Managed Inference Cluster",
                            Owner="Bud Ecosystem",
                            ManagedBy="Bud",
                        ),
                    )

                case "aws":
                    required_fields = ["access_key_id", "secret_access_key"]
                    for field in required_fields:
                        if field not in create_cluster_request_json.config_credentials:  # type: ignore
                            raise ValueError(f"Missing required credential field: {field}")
                    config = AWSConfig(
                        access_key=create_cluster_request_json.config_credentials["access_key_id"],  # type: ignore
                        secret_key=create_cluster_request_json.config_credentials["secret_access_key"],  # type: ignore
                        region=create_cluster_request_json.region,  # type: ignore
                        cluster_name=create_cluster_request_json.name,
                        vpc_name=f"{create_cluster_request_json.name}-bud-inc",
                        tags=TagsModel(
                            Environment="Production",
                            Project="Bud Managed Inference Cluster",
                            Owner="Bud Ecosystem",
                            ManagedBy="Bud",
                        ),
                    )
                case _:
                    raise ValueError("Unsupported provider")

            return SuccessResponse(  # type: ignore
                message="Cloud provider credentials validated successfully",
                param={
                    "provider": create_cluster_request_json.cloud_provider_unique_id,  # type: ignore
                    "config": config.model_dump(mode="json"),  # type: ignore
                },
            ).model_dump(mode="json")
        except Exception as e:
            logger.error(f"Error processing cloud provider credentials: {e}", exc_info=True)

            logger.error(f"Traceback ++++: {traceback.format_exc()}")
            return ErrorResponse(
                message=f"Error processing cloud provider credentials: {str(e)}",
                code=HTTPStatus.INTERNAL_SERVER_ERROR.value,
            ).model_dump(mode="json")

    @dapr_workflows.register_activity  # type: ignore
    @staticmethod
    def create_cloud_provider_cluster(ctx: wf.WorkflowActivityContext, cloud_provider_config: str) -> dict:
        """Create a Kubernetes cluster in the cloud provider."""
        logger = logging.get_logger("CreateCloudProviderCluster")
        workflow_id = ctx.workflow_id
        task_id = ctx.task_id
        logger.info(f"Creating cloud provider cluster for workflow_id: {workflow_id} and task_id: {task_id}")

        try:
            # Check if workflow has been terminated
            workflow_status = check_workflow_status_in_statestore(workflow_id)
            if workflow_status:
                return workflow_status

            # Get the cloud config from previous step
            cloud_config = json.loads(cloud_provider_config)
            provider = cloud_config["param"]["provider"]
            config = cloud_config["param"]["config"]

            tf_manager = None
            tf_config = None

            # Branch Based On Provider
            match provider:
                case "azure":
                    # Create AzureConfig from the config dict
                    tf_config = AzureConfig(**config)
                    # Create the AKS cluster using TerraformClusterManager
                    tf_manager = AzureAksManager(tf_config)
                case "aws":
                    # Create AWSConfig from the config dict
                    tf_config = AWSConfig(**config)
                    tf_manager = AWSEksManager(tf_config)
                case _:
                    raise ValueError(f"Unsupported provider: {provider}")

            # Initialize Terraform
            prefix = f"{hashlib.md5(tf_config.cluster_name.encode(), usedforsecurity=False).hexdigest()}"
            init_result = tf_manager.init(prefix)

            if init_result.returncode != 0:
                logger.error(f"Terraform init failed: {init_result.stdout}")
                return ErrorResponse(
                    message="Failed to initialize Terraform for cloud cluster creation",
                    code=HTTPStatus.INTERNAL_SERVER_ERROR.value,
                ).model_dump(mode="json")

            # Create a plan
            plan_result = tf_manager.plan()
            if plan_result.returncode != 0:
                logger.error(f"Terraform plan failed: {plan_result.stdout}")
                return ErrorResponse(
                    message="Failed to create a Terraform init for cloud cluster creation",
                    code=HTTPStatus.INTERNAL_SERVER_ERROR.value,
                ).model_dump(mode="json")

            # Apply the plan to create the cluster
            apply_result = tf_manager.apply()
            if apply_result.returncode != 0:
                logger.error(f"Terraform apply failed: {apply_result.stdout}")
                return ErrorResponse(
                    message="Failed to apply Terraform plan for cloud cluster creation",
                    code=HTTPStatus.INTERNAL_SERVER_ERROR.value,
                ).model_dump(mode="json")

            # Get the outputs
            outputs = tf_manager.get_outputs()
            if not outputs:
                logger.error("Failed to get Terraform outputs")
                return ErrorResponse(
                    message="Failed to get Terraform outputs after cluster creation",
                    code=HTTPStatus.INTERNAL_SERVER_ERROR.value,
                ).model_dump(mode="json")

            # Store the terraform directory path in the workflow data for cleanup
            workflow_data = get_workflow_data_from_statestore(str(workflow_id))
            workflow_data["terraform_dir"] = tf_manager.temp_dir
            update_workflow_data_in_statestore(str(workflow_id), workflow_data)

            return SuccessResponse(  # type: ignore
                message="Cloud cluster created successfully",
                param={"provider": provider, "terraform_outputs": outputs, "cluster_name": tf_config.cluster_name},
            ).model_dump(mode="json")

        except Exception as e:
            logger.error(f"Error creating cloud provider cluster: {e}")
            return ErrorResponse(
                message=f"Error creating cloud provider cluster: {str(e)}", code=HTTPStatus.INTERNAL_SERVER_ERROR.value
            ).model_dump(mode="json")

    @dapr_workflows.register_workflow  # type: ignore
    @staticmethod
    def register_cluster(ctx: wf.DaprWorkflowContext, add_cluster_request: str):
        """Execute the workflow to register a cluster.

        This workflow verifies the cluster connection, configures the cluster, and fetches the cluster info.

        Args:
            ctx (DaprWorkflowContext): The context of the Dapr workflow, providing
            access to workflow instance information.
            add_cluster_request (str): A JSON string containing the cluster configuration.
        """
        logger = logging.get_logger("RegisterCluster")
        instance_id = str(ctx.instance_id)
        logger.info(f"Registering cluster for instance_id: {instance_id}")

        # Parse the request
        try:
            add_cluster_request_json = ClusterCreateRequest.model_validate_json(add_cluster_request)
        except Exception as e:
            logger.error(f"Error parsing cluster create request: {e}")
            return

        # Set workflow data
        update_workflow_data_in_statestore(
            instance_id,
            {
                "status": WorkflowStatus.RUNNING.value,
                "namespace": "bud-system",
                "cluster_config_dict": add_cluster_request_json.config_dict,
                "enable_master_node": add_cluster_request_json.enable_master_node,
                "ingress_url": str(add_cluster_request_json.ingress_url),
                "name": add_cluster_request_json.name,
                "credential_id": add_cluster_request_json.credential_id,
                "cloud_provider_id": add_cluster_request_json.provider_id,
                "region": add_cluster_request_json.region,
                "cluster_type": add_cluster_request_json.cluster_type,
                "cloud_provider_unique_id": add_cluster_request_json.cloud_provider_unique_id,
            },
        )

        # Set up notification
        workflow_name = "register_cluster"
        notification_request = NotificationRequest.from_cloud_event(
            cloud_event=add_cluster_request_json, name=workflow_name, workflow_id=instance_id
        )
        notification_req = notification_request.model_copy(deep=True)
        notification_req.payload.event = "cluster_registration_status"
        notification_req.payload.content = NotificationContent(
            title="Cluster registering process is initiated",
            message=f"Cluster registering process is initiated for {add_cluster_request_json.name}",
            status=WorkflowStatus.STARTED,
        )

        # Publish initial notification
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=add_cluster_request_json.source_topic,
            target_name=add_cluster_request_json.source,
        )

        # Set initial ETA (in minutes for notification)
        notification_req.payload.event = "eta"
        # Cloud clusters: ~10 minutes, On-premises: ~3 minutes
        eta_minutes = 10 if add_cluster_request_json.cluster_type == "CLOUD" else 3
        notification_req.payload.content = NotificationContent(
            title="Estimated time to completion",
            message=f"{eta_minutes}",
            status=WorkflowStatus.RUNNING,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=add_cluster_request_json.source_topic,
            target_name=add_cluster_request_json.source,
        )

        # Branch based on cluster type
        is_cloud_deployment = add_cluster_request_json.cluster_type == "CLOUD"

        # Cloud Deployments
        if is_cloud_deployment:
            logger.info(f"::CLOUD:: Cloud deployment flow for {add_cluster_request_json.name}")

            # Convert request to cloud provider activity request
            cloud_provider_request = CreateCloudProviderClusterActivityRequest(
                name=add_cluster_request_json.name,
                credential_id=add_cluster_request_json.credential_id,
                provider_id=add_cluster_request_json.provider_id,
                region=add_cluster_request_json.region,
                credentials=add_cluster_request_json.credentials,
                cluster_type=add_cluster_request_json.cluster_type,
                cloud_provider_unique_id=add_cluster_request_json.cloud_provider_unique_id
                or "",  # For Cloud Request value will be always present
            )

            # Step 1: Get and validate cloud provider credentials
            get_credentials_result = yield ctx.call_activity(
                RegisterClusterWorkflow.get_cloud_provider_credentials,
                input=cloud_provider_request.model_dump_json(),
            )
            logger.debug(f"::CLOUD:: Get cloud provider credentials result: {get_credentials_result}")

            # Notification
            if get_credentials_result.get("code", HTTPStatus.OK.value) != HTTPStatus.OK.value:
                notification_req.payload.event = "get_cloud_provider_credentials"
                notification_req.payload.content = NotificationContent(
                    title="Cloud provider credentials validation failed",
                    message=get_credentials_result["message"],
                    status=WorkflowStatus.FAILED,
                )
                dapr_workflows.publish_notification(
                    workflow_id=instance_id,
                    notification=notification_req,
                    target_topic_name=add_cluster_request_json.source_topic,
                    target_name=add_cluster_request_json.source,
                )
                return

            # Update ETA - Credentials validated, ~9 minutes remaining
            notification_req.payload.event = "eta"
            notification_req.payload.content = NotificationContent(
                title="Estimated time to completion",
                message=f"{9}",
                status=WorkflowStatus.RUNNING,
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=add_cluster_request_json.source_topic,
                target_name=add_cluster_request_json.source,
            )

            # Step 2: Create cloud provider cluster

            # Notification
            notification_req.payload.event = "create_cloud_provider_cluster"
            notification_req.payload.content = NotificationContent(
                title="Cluster Provisioning",
                message="Starting cloud cluster provisioning",
                status=WorkflowStatus.STARTED,
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=add_cluster_request_json.source_topic,
                target_name=add_cluster_request_json.source,
            )

            notification_req.payload.event = "create_cloud_provider_cluster"
            notification_req.payload.content = NotificationContent(
                title="Cluster Provisioning",
                message="Starting cloud cluster provisioning",
                status=WorkflowStatus.RUNNING,
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=add_cluster_request_json.source_topic,
                target_name=add_cluster_request_json.source,
            )

            # TODO: ETA
            create_cluster_result = yield ctx.call_activity(
                RegisterClusterWorkflow.create_cloud_provider_cluster,
                input=json.dumps(get_credentials_result),
            )

            logger.info(f"::CLOUD:: Create cloud provider cluster result: {create_cluster_result}")

            # Validate The Response
            if create_cluster_result.get("code", HTTPStatus.OK.value) != HTTPStatus.OK.value:
                notification_req.payload.event = "create_cloud_provider_cluster"
                notification_req.payload.content = NotificationContent(
                    title="Failed to create cluster",
                    message=create_cluster_result["message"],
                    status=WorkflowStatus.FAILED,
                )
                dapr_workflows.publish_notification(
                    workflow_id=instance_id,
                    notification=notification_req,
                    target_topic_name=add_cluster_request_json.source_topic,
                    target_name=add_cluster_request_json.source,
                )
                return

            # Extract aks_host from the response
            terraform_outputs = create_cluster_result.get("param", {}).get("terraform_outputs", {})

            # Group Based On The Provider

            aks_host_data = terraform_outputs.get("aks_host", {})
            aks_host = aks_host_data.get("value", "")

            # Extract Kube Configure Cluster
            kube_config_data = terraform_outputs.get("kube_config", {})
            kube_config = json.dumps(yaml.safe_load(kube_config_data.get("value", "")))

            # Log the extracted host
            logger.info(f"Extracted AKS host: {aks_host}")
            logger.info(f"::CLOUD:: JSON Config {kube_config}")

            # TODO: Save the whole response to db if required

            # Store it in workflow data for later use
            update_workflow_data_in_statestore(
                str(instance_id),
                {"ingress_url": aks_host, "cluster_config_dict": kube_config},
            )

            # Update the variable
            add_cluster_request_json.configuration = kube_config
            add_cluster_request_json.ingress_url = aks_host

            # Job Complited
            notification_req.payload.event = "create_cloud_provider_cluster"
            notification_req.payload.content = NotificationContent(
                title="Cluster Provisioned",
                message="Cluster provisioned successfully",
                status=WorkflowStatus.COMPLETED,
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=add_cluster_request_json.source_topic,
                target_name=add_cluster_request_json.source,
            )

            # Set platform to Kubernetes for cloud clusters
            determine_cluster_platform_result = {
                "code": HTTPStatus.OK.value,
                "message": "Cluster platform determined automatically for cloud deployment",
                "param": {
                    "cluster_platform": ClusterPlatformEnum.KUBERNETES,
                    "hostname": aks_host,
                    "server_url": aks_host,
                },
            }

            # Update workflow data with platform info
            update_workflow_data_in_statestore(
                str(instance_id),
                {
                    "platform": ClusterPlatformEnum.KUBERNETES,
                    "hostname": aks_host,
                    "server_url": aks_host,
                },
            )

            # Update ETA - Cloud cluster created, ~5 minutes for configuration
            notification_req.payload.event = "eta"
            notification_req.payload.content = NotificationContent(
                title="Estimated time to completion",
                message=f"{5}",
                status=WorkflowStatus.RUNNING,
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=add_cluster_request_json.source_topic,
                target_name=add_cluster_request_json.source,
            )

            # Verification
            verify_cluster_connection_request = VerifyClusterConnection(
                cluster_config=kube_config, platform=ClusterPlatformEnum.KUBERNETES
            )

        else:
            # On-Premise Deployments
            logger.info(f"On-premises deployment flow for {add_cluster_request_json.name}")

            # Step 1: Determine cluster platform
            determine_cluster_platform_request = DetermineClusterPlatformRequest(
                cluster_config=add_cluster_request_json.configuration,
                enable_master_node=add_cluster_request_json.enable_master_node,
            )
            determine_cluster_platform_result = yield ctx.call_activity(
                RegisterClusterWorkflow.determine_cluster_platform,
                input=determine_cluster_platform_request.model_dump_json(),
            )
            logger.info(f"Determine cluster platform result: {determine_cluster_platform_result}")

            if determine_cluster_platform_result.get("code", HTTPStatus.OK.value) != HTTPStatus.OK.value:
                notification_req.payload.event = "determine_cluster_platform"
                notification_req.payload.content = NotificationContent(
                    title="Cluster platform determination failed",
                    message=determine_cluster_platform_result["message"],
                    status=WorkflowStatus.FAILED,
                )
                dapr_workflows.publish_notification(
                    workflow_id=instance_id,
                    notification=notification_req,
                    target_topic_name=add_cluster_request_json.source_topic,
                    target_name=add_cluster_request_json.source,
                )
                return

            notification_req.payload.event = "determine_cluster_platform"
            notification_req.payload.content = NotificationContent(
                title="Cluster platform determined successfully",
                message=determine_cluster_platform_result["message"],
                status=WorkflowStatus.COMPLETED,
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=add_cluster_request_json.source_topic,
                target_name=add_cluster_request_json.source,
            )

            # Update ETA - Platform determined, ~3 minutes remaining
            notification_req.payload.event = "eta"
            notification_req.payload.content = NotificationContent(
                title="Estimated time to completion",
                message=f"{3}",
                status=WorkflowStatus.RUNNING,
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=add_cluster_request_json.source_topic,
                target_name=add_cluster_request_json.source,
            )

            # Step 2: Check for duplicate configurations
            check_duplicate_config_request = CheckDuplicateConfig(
                server_url=determine_cluster_platform_result["param"]["server_url"],
                platform=determine_cluster_platform_result["param"]["cluster_platform"],
            )
            check_duplicate_config_result = yield ctx.call_activity(
                RegisterClusterWorkflow.check_duplicate_config,
                input=check_duplicate_config_request.model_dump_json(),
            )
            logger.info(f"Check duplicate config result: {check_duplicate_config_result}")

            if check_duplicate_config_result.get("code", HTTPStatus.OK.value) != HTTPStatus.OK.value:
                notification_req.payload.event = "check_duplicate_config"
                notification_req.payload.content = NotificationContent(
                    title="Duplicate cluster found",
                    message=check_duplicate_config_result["message"],
                    status=WorkflowStatus.FAILED,
                )
                dapr_workflows.publish_notification(
                    workflow_id=instance_id,
                    notification=notification_req,
                    target_topic_name=add_cluster_request_json.source_topic,
                    target_name=add_cluster_request_json.source,
                )
                return

            notification_req.payload.event = "check_duplicate_config"
            notification_req.payload.content = NotificationContent(
                title="Duplicate cluster not found",
                message="Duplicate cluster not found",
                status=WorkflowStatus.COMPLETED,
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=add_cluster_request_json.source_topic,
                target_name=add_cluster_request_json.source,
            )

            # Update ETA - Duplicate check done, ~2 minutes remaining
            notification_req.payload.event = "eta"
            notification_req.payload.content = NotificationContent(
                title="Estimated time to completion",
                message=f"{2}",
                status=WorkflowStatus.RUNNING,
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=add_cluster_request_json.source_topic,
                target_name=add_cluster_request_json.source,
            )

            # Verification
            verify_cluster_connection_request = VerifyClusterConnection(
                cluster_config=add_cluster_request_json.configuration,
                platform=determine_cluster_platform_result["param"]["cluster_platform"],
            )

        # verify cluster connection
        verify_cluster_connection_result = yield ctx.call_activity(
            RegisterClusterWorkflow.verify_cluster_connection,
            input=verify_cluster_connection_request.model_dump_json(),
        )
        logger.info(f"Verify cluster connection result: {verify_cluster_connection_result}")

        # if verify cluster connection is not successful
        if verify_cluster_connection_result.get("code", HTTPStatus.OK.value) != HTTPStatus.OK.value:
            # notify activity that cluster verification failed
            notification_req.payload.event = "verify_cluster_connection"
            notification_req.payload.content = NotificationContent(
                title="Cluster verification failed",
                message=verify_cluster_connection_result["message"],
                status=WorkflowStatus.FAILED,
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=add_cluster_request_json.source_topic,
                target_name=add_cluster_request_json.source,
            )
            # yield ctx.call_activity(notify_activity, input=notification_activity_request.model_dump_json())
            return

        # notify activity that cluster verification is successful
        notification_req.payload.event = "verify_cluster_connection"
        notification_req.payload.content = NotificationContent(
            title="Cluster verification successful",
            message=verify_cluster_connection_result["message"],
            status=WorkflowStatus.COMPLETED,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=add_cluster_request_json.source_topic,
            target_name=add_cluster_request_json.source,
        )

        # notify activity ETA - Cluster verified, ~2 minutes for configuration
        notification_req.payload.event = "eta"
        notification_req.payload.content = NotificationContent(
            title="Estimated time to completion",
            message=f"{2}",
            status=WorkflowStatus.RUNNING,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=add_cluster_request_json.source_topic,
            target_name=add_cluster_request_json.source,
        )

        # configure the cluster
        configure_cluster_request = ConfigureCluster(
            config_dict=add_cluster_request_json.config_dict,
            platform=determine_cluster_platform_result["param"]["cluster_platform"],
            hostname=determine_cluster_platform_result["param"]["hostname"],
            enable_master_node=add_cluster_request_json.enable_master_node,
            ingress_url=str(add_cluster_request_json.ingress_url),
            server_url=determine_cluster_platform_result["param"]["server_url"],
        )
        configure_cluster_result = yield ctx.call_activity(
            RegisterClusterWorkflow.configure_cluster, input=configure_cluster_request.model_dump_json()
        )

        # if configure cluster is not successful
        if configure_cluster_result.get("code", HTTPStatus.OK.value) != HTTPStatus.OK.value:
            # Update cluster status to NOT_AVAILABLE if cluster was created
            try:
                from budmicroframe.shared.psql_service import DBSession

                from ..commons.constants import ClusterStatusEnum
                from .crud import ClusterDataManager

                # Try to get cluster_id from the configure_cluster_result or workflow data
                cluster_id = configure_cluster_result.get("param", {}).get("cluster_id")
                if not cluster_id:
                    # Fallback to workflow data
                    workflow_data = get_workflow_data_from_statestore(str(instance_id))
                    cluster_id = workflow_data.get("cluster_id") if workflow_data else None

                if cluster_id:
                    with DBSession() as session:
                        db_cluster = asyncio.run(
                            ClusterDataManager(session).retrieve_cluster_by_fields({"id": cluster_id})
                        )
                        if db_cluster:
                            asyncio.run(
                                ClusterDataManager(session).update_cluster_by_fields(
                                    db_cluster, {"status": ClusterStatusEnum.NOT_AVAILABLE}
                                )
                            )
                            logger.info(
                                f"Marked cluster {cluster_id} as NOT_AVAILABLE due to workflow configure_cluster failure"
                            )
            except Exception as e:
                logger.error(f"Failed to update cluster status on workflow configure_cluster failure: {e}")

            # notify activity that cluster configuration failed
            notification_req.payload.event = "configure_cluster"
            notification_req.payload.content = NotificationContent(
                title="Cluster configuration failed",
                message=configure_cluster_result["message"],
                status=WorkflowStatus.FAILED,
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=add_cluster_request_json.source_topic,
                target_name=add_cluster_request_json.source,
            )
            # yield ctx.call_activity(notify_activity, input=notification_activity_request.model_dump_json())
            return

        # notify activity that cluster configuration is successful
        notification_req.payload.event = "configure_cluster"
        notification_req.payload.content = NotificationContent(
            title="Cluster configuration successful",
            message=configure_cluster_result["message"],
            status=WorkflowStatus.COMPLETED,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=add_cluster_request_json.source_topic,
            target_name=add_cluster_request_json.source,
        )

        # notify activity ETA - Configuration done, ~1 minute for fetching info
        notification_req.payload.event = "eta"
        notification_req.payload.content = NotificationContent(
            title="Estimated time to completion",
            message=f"{1}",
            status=WorkflowStatus.RUNNING,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=add_cluster_request_json.source_topic,
            target_name=add_cluster_request_json.source,
        )

        # fetch the cluster info
        fetch_cluster_info_request = FetchClusterInfo(
            config_dict=add_cluster_request_json.config_dict,
            name=add_cluster_request_json.name,
            platform=determine_cluster_platform_result["param"]["cluster_platform"],
            hostname=determine_cluster_platform_result["param"]["hostname"],
            enable_master_node=add_cluster_request_json.enable_master_node,
            ingress_url=str(add_cluster_request_json.ingress_url),
            server_url=determine_cluster_platform_result["param"]["server_url"],
            cluster_id=configure_cluster_result["param"]["cluster_id"],
        )
        fetch_cluster_info_result = yield ctx.call_activity(
            RegisterClusterWorkflow.fetch_cluster_info, input=fetch_cluster_info_request.model_dump_json()
        )

        logger.info(f" ::CLOUD:: Fetch cluster info result: {fetch_cluster_info_result}")
        # if fetch cluster info is not successful
        if fetch_cluster_info_result.get("code", HTTPStatus.OK.value) != HTTPStatus.OK.value:
            # notify activity that cluster info fetching failed
            notification_req.payload.event = "fetch_cluster_info"
            notification_req.payload.content = NotificationContent(
                title="Cluster info fetching failed",
                message=fetch_cluster_info_result["message"],
                status=WorkflowStatus.FAILED,
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=add_cluster_request_json.source_topic,
                target_name=add_cluster_request_json.source,
            )

            # Mark cluster as failed in DB since registration failed
            try:
                from budmicroframe.shared.psql_service import DBSession

                from ..commons.constants import ClusterStatusEnum
                from .crud import ClusterDataManager

                with DBSession() as session:
                    db_cluster = asyncio.run(
                        ClusterDataManager(session).retrieve_cluster_by_fields(
                            {"id": fetch_cluster_info_request.cluster_id}
                        )
                    )
                    if db_cluster:
                        asyncio.run(
                            ClusterDataManager(session).update_cluster_by_fields(
                                db_cluster, {"status": ClusterStatusEnum.NOT_AVAILABLE}
                            )
                        )
                        logger.info(
                            f"Marked cluster {fetch_cluster_info_request.cluster_id} as NOT_AVAILABLE due to fetch_cluster_info failure"
                        )
            except Exception as e:
                logger.error(f"Failed to update cluster status on fetch_cluster_info failure: {e}")

            # yield ctx.call_activity(notify_activity, input=notification_activity_request.model_dump_json())
            return

        # save cluster node info to statestore
        asyncio.run(ClusterOpsService.update_node_info_in_statestore(fetch_cluster_info_result["param"]["result"]))

        # notify activity that cluster info fetching is successful
        notification_req.payload.event = "fetch_cluster_info"
        notification_req.payload.content = NotificationContent(
            title="Cluster info fetching successful",
            message=fetch_cluster_info_result["message"],
            status=WorkflowStatus.COMPLETED,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=add_cluster_request_json.source_topic,
            target_name=add_cluster_request_json.source,
        )

        logger.info(f"::CLOUD:: Cluster info fetching successful {fetch_cluster_info_result}")
        logger.info(f"::CLOUD:: Cluster info fetching successful {fetch_cluster_info_result['param']['result']}")

        notification_req.payload.event = "results"
        notification_req.payload.content = NotificationContent(
            title="Fetching cluster nodes info successful",
            message="Cluster nodes info fetched successfully",
            status=WorkflowStatus.COMPLETED,
            result=json.loads(fetch_cluster_info_result["param"]["result"]),
        )
        workflow_status = check_workflow_status_in_statestore(instance_id)
        if workflow_status:
            # TODO:  Update this for CLOUD Platform too

            asyncio.run(ClusterOpsService.delete_node_info_from_statestore(str(add_cluster_request_json.id)))
            return workflow_status
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=add_cluster_request_json.source_topic,
            target_name=add_cluster_request_json.source,
        )
        # yield ctx.call_activity(notify_activity, input=notification_activity_request.model_dump_json())

        notification_req.payload.event = "cluster_registration_status"
        notification_req.payload.content = NotificationContent(
            title="Cluster added successfully",
            message=f"Cluster {add_cluster_request_json.name} was registered successfully and is now available.",
            status=WorkflowStatus.COMPLETED,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=add_cluster_request_json.source_topic,
            target_name=add_cluster_request_json.source,
        )

        return

    @dapr_workflows.register_activity  # type: ignore
    @staticmethod
    def get_kube_config(ctx: wf.WorkflowActivityContext, cluster_info: str) -> dict:
        """Get the kubeconfig for the created cloud cluster."""
        logger = logging.get_logger("GetKubeConfig")
        workflow_id = ctx.workflow_id
        task_id = ctx.task_id
        logger.info(f"Getting kubeconfig for workflow_id: {workflow_id} and task_id: {task_id}")

        try:
            # Check if workflow has been terminated
            workflow_status = check_workflow_status_in_statestore(workflow_id)
            if workflow_status:
                return workflow_status

            # Parse the cluster info
            cluster_info_dict = json.loads(cluster_info)
            provider = cluster_info_dict["param"]["provider"]
            terraform_outputs = cluster_info_dict["param"]["terraform_outputs"]

            if provider == "azure":
                # Extract kubeconfig from terraform outputs
                kube_config = terraform_outputs.get("kube_config", {}).get("value")
                if not kube_config:
                    return ErrorResponse(
                        message="Kubeconfig not found in terraform outputs",
                        code=HTTPStatus.INTERNAL_SERVER_ERROR.value,
                    ).model_dump(mode="json")

                # Store the kubeconfig in the workflow data
                workflow_data = get_workflow_data_from_statestore(str(workflow_id))
                workflow_data["kube_config"] = kube_config
                update_workflow_data_in_statestore(str(workflow_id), workflow_data)

                # Extract host information for later use
                server_url = None
                hostname = None

                try:
                    kube_config_dict = json.loads(kube_config)
                    if "clusters" in kube_config_dict and len(kube_config_dict["clusters"]) > 0:
                        server_url = kube_config_dict["clusters"][0].get("cluster", {}).get("server")
                        if server_url:
                            from urllib.parse import urlparse

                            parsed_url = urlparse(server_url)
                            hostname = parsed_url.hostname
                except Exception:
                    # Fall back to standard naming convention if parsing fails
                    cluster_name = cluster_info_dict["param"].get("cluster_name", "aks-cluster")
                    hostname = f"{cluster_name}.azmk8s.io"
                    server_url = f"https://{hostname}"

                if not hostname:
                    hostname = f"{cluster_info_dict['param'].get('cluster_name', 'aks-cluster')}.azmk8s.io"

                if not server_url:
                    server_url = f"https://{hostname}"

                return SuccessResponse(
                    message="Kubeconfig retrieved successfully",
                    param={
                        "provider": provider,
                        "configuration": kube_config,
                        "hostname": hostname,
                        "server_url": server_url,
                    },
                ).model_dump(mode="json")
            else:
                return ErrorResponse(
                    message=f"Unsupported cloud provider: {provider}", code=HTTPStatus.BAD_REQUEST.value
                ).model_dump(mode="json")
        except Exception as e:
            logger.error(f"Error getting kubeconfig: {e}")
            return ErrorResponse(
                message=f"Error getting kubeconfig: {str(e)}", code=HTTPStatus.INTERNAL_SERVER_ERROR.value
            ).model_dump(mode="json")

    async def __call__(
        self, request: ClusterCreateRequest, workflow_id: Optional[str] = None
    ) -> Union[WorkflowMetadataResponse, ErrorResponse]:
        """Entry point for registering a cluster, handling both on-premises and cloud deployments."""
        logger = logging.get_logger("RegisterClusterCall")
        workflow_id = str(workflow_id or uuid.uuid4())

        if isinstance(request, CreateCloudProviderClusterRequest) or (
            isinstance(request, ClusterCreateRequest) and request.cluster_type == "CLOUD"
        ):
            logger.info(f"Setting up workflow for cloud cluster: {request.name}")

            # Convert CreateCloudProviderClusterRequest to ClusterCreateRequest if needed

            if isinstance(request, CreateCloudProviderClusterRequest):
                cluster_request = ClusterCreateRequest(
                    name=request.name,
                    enable_master_node=False,  # Cloud clusters don't need master node flag
                    ingress_url="",
                    credential_id=request.credential_id,
                    provider_id=request.provider_id,
                    region=request.region,
                    # credentials=request.credentials,
                    cluster_type="CLOUD",
                    source=request.source,
                    source_topic=request.source_topic,
                    id=request.id,
                )
            else:
                cluster_request = request

            # Define workflow steps for cloud deployment
            workflow_steps = [
                WorkflowStep(
                    id="create_cloud_provider_cluster",
                    title="Creating Bud Inference Cluster",
                    description="Provision a new Kubernetes cluster in the cloud",
                ),
                WorkflowStep(
                    id="verify_cluster_connection",
                    title="Verifying cluster connection",
                    description="Verify connectivity to the new cluster",
                ),
                WorkflowStep(
                    id="configure_cluster",
                    title="Configuring cluster",
                    description="Configure the cluster",
                ),
                WorkflowStep(
                    id="fetch_cluster_info",
                    title="Fetching cluster info",
                    description="Fetch the cluster information",
                ),
            ]

            # Set longer ETA for cloud deployments (10 minutes)
            eta = 600  # 600 seconds = 10 minutes

        else:
            logger.info(f"Setting up workflow for on-prem cluster: {request.name}")
            cluster_request = request

            # Define workflow steps for on-premises deployment
            workflow_steps = [
                WorkflowStep(
                    id="determine_cluster_platform",
                    title="Determining cluster platform",
                    description="Determine the cluster platform",
                ),
                WorkflowStep(
                    id="check_duplicate_config",
                    title="Checking for duplicate cluster",
                    description="Check for any duplicate cluster",
                ),
                WorkflowStep(
                    id="verify_cluster_connection",
                    title="Verifying cluster connection",
                    description="Verify the cluster connection",
                ),
                WorkflowStep(
                    id="configure_cluster",
                    title="Configuring cluster",
                    description="Configure the cluster",
                ),
                WorkflowStep(
                    id="fetch_cluster_info",
                    title="Fetching cluster info",
                    description="Fetch the cluster info",
                ),
            ]

            # Set standard ETA for on-prem deployments (10 minutes)
            eta = 10
        # Schedule the workflow
        response = await dapr_workflows.schedule_workflow(
            workflow_name="register_cluster",
            workflow_input=cluster_request.model_dump_json(),
            workflow_id=workflow_id,
            workflow_steps=workflow_steps,
            eta=eta,
            target_topic_name=cluster_request.source_topic,
            target_name=cluster_request.source,
        )

        return response


class DeleteClusterWorkflow:
    @dapr_workflows.register_activity
    @staticmethod
    def delete_cluster_from_db(ctx: wf.WorkflowActivityContext, cluster_id: str) -> dict:
        """Delete the cluster from the database."""
        logger = logging.get_logger("DeleteCluster")
        workflow_id = ctx.workflow_id
        task_id = ctx.task_id
        logger.info(f"Deleting cluster from database for workflow_id: {workflow_id} and task_id: {task_id}")
        response: Union[SuccessResponse, ErrorResponse]
        try:
            with DBSession() as session:
                db_cluster = asyncio.run(ClusterService(session)._get_cluster(cluster_id, missing_ok=True))
                if db_cluster is None:
                    response = ErrorResponse(message="Cluster not found", code=HTTPStatus.NOT_FOUND.value)
                else:
                    asyncio.run(ClusterDataManager(session).delete_cluster(db_cluster=db_cluster))
                    response = SuccessResponse(
                        message="Cluster successfully deleted from database",
                        param={
                            "cluster_id": str(db_cluster.id),
                            "cluster_config": db_cluster.config_file_dict,
                            "platform": db_cluster.platform,
                        },
                    )
        except Exception as e:
            logger.error(
                f"Error deleting cluster from database for workflow_id: {workflow_id} and task_id: {task_id}, error: {e}"
            )
            response = ErrorResponse(
                message="Error deleting cluster from database", code=HTTPStatus.INTERNAL_SERVER_ERROR.value
            )
        return response.model_dump(mode="json")

    @dapr_workflows.register_activity
    @staticmethod
    def delete_cluster_resources(ctx: wf.WorkflowActivityContext, delete_cluster_request: str) -> dict:
        """Delete the namespace."""
        logger = logging.get_logger("DeleteCluster")
        workflow_id = ctx.workflow_id
        task_id = ctx.task_id
        logger.info(f"Deleting cluster resources for workflow_id: {workflow_id} and task_id: {task_id}")
        # delete_namespace_request_json = DeleteNamespaceRequest.model_validate_json(delete_namespace_request)
        delete_cluster_json = DeleteCluster.model_validate_json(delete_cluster_request)

        response: Union[SuccessResponse, ErrorResponse]
        try:
            # namespace = delete_namespace_request_json.namespace
            # deployment_handler = DeploymentHandler(config=delete_namespace_request_json.cluster_config)
            # deployment_handler.delete(namespace=namespace, platform=delete_namespace_request_json.platform)
            cluster_deleted = asyncio.run(ClusterOpsService.delete_cluster(delete_cluster_json, task_id, workflow_id))
            logger.info(f"Cluster deleted: {cluster_deleted}")
            if cluster_deleted == "successful":
                response = SuccessResponse(
                    message="Cluster resources deleted successfully",
                    param={},
                )
            else:
                response = ErrorResponse(
                    message="Cluster resources deletion failed",
                    code=HTTPStatus.BAD_REQUEST.value,
                    param={},
                )
        except Exception as e:
            error_msg = (
                f"Error deleting cluster resources for workflow_id: {workflow_id} and task_id: {task_id}, error: {e}"
            )
            logger.error(error_msg)
            response = ErrorResponse(
                message="Cluster resources deletion failed",
                code=HTTPStatus.BAD_REQUEST.value,
                param={},
            )
        return response.model_dump(mode="json")

    @dapr_workflows.register_workflow
    @staticmethod
    def delete_cluster(ctx: wf.DaprWorkflowContext, delete_cluster_request: str):
        """Execute the workflow to delete a cluster.

        This workflow supports both cloud and on-premises cluster deletions.
        For cloud clusters, it calls the cloud provider’s Terraform destroy command.
        For on-premises clusters, it deletes cluster resources and then the database record.

        Args:
            ctx (DaprWorkflowContext): The workflow context containing instance details.
            delete_cluster_request (str): A JSON string conforming to ClusterDeleteRequest.
        """
        logger = logging.get_logger("DeleteCluster")
        instance_id = str(ctx.instance_id)
        logger.info(f"Deleting cluster for workflow_id: {instance_id}")

        # Validate the deletion request
        delete_cluster_request_json = ClusterDeleteRequest.model_validate_json(delete_cluster_request)
        cluster_id = delete_cluster_request_json.cluster_id

        # Prepare a notification request for publishing progress events.
        workflow_name = "delete_cluster"
        notification_request = NotificationRequest.from_cloud_event(
            cloud_event=delete_cluster_request_json, name=workflow_name, workflow_id=instance_id
        )
        notification_req = notification_request.model_copy(deep=True)

        # notify activity that cluster deletion process is initiated
        notification_req.payload.event = "delete_namespace"
        notification_req.payload.content = NotificationContent(
            title="Cluster deletion process is initiated",
            message=f"Cluster deletion process is initiated for cluster id : {cluster_id}",
            status=WorkflowStatus.STARTED,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=delete_cluster_request_json.source_topic,
            target_name=delete_cluster_request_json.source,
        )

        # notify activity ETA - Final deletion steps
        notification_req.payload.event = "eta"
        notification_req.payload.content = NotificationContent(
            title="Estimated time to completion",
            message=f"{1}",
            status=WorkflowStatus.RUNNING,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=delete_cluster_request_json.source_topic,
            target_name=delete_cluster_request_json.source,
        )

        # Cloud Branchout
        if delete_cluster_request_json.cluster_type == "CLOUD":
            # Get The Provider UniqueID
            cloud_event_payload = delete_cluster_request_json.cloud_payload_dict
            cloud_provider_id = cloud_event_payload.get("provider_unique_id", None)
            logger.debug(f"::CLOUD:: {cloud_event_payload}")

            if not cloud_provider_id:
                logger.error("Cloud provider unique ID is missing")
                notification_req.payload.event = "delete_namespace"
                notification_req.payload.content = NotificationContent(
                    title="Cloud cluster deletion failed",
                    message="Cloud provider unique identifier missing",
                    status=WorkflowStatus.FAILED,
                )
                dapr_workflows.publish_notification(
                    workflow_id=instance_id,
                    notification=notification_req,
                    target_topic_name=delete_cluster_request_json.source_topic,
                    target_name=delete_cluster_request_json.source,
                )
                return

            try:
                # Extract credentials from the payload
                credentials = cloud_event_payload.get("credentials", {})
                # If credentials is empty or None, try looking for specific fields
                if not credentials:
                    logger.debug("No credentials object found, looking for direct credential fields")
                    credentials = {}

                match cloud_provider_id:
                    case "azure":
                        # Build the Azure configuration instance from the payload.
                        azure_config = AzureConfig(
                            subscription_id=credentials.get("subscription_id"),
                            tenant_id=credentials.get("tenant_id"),
                            client_id=credentials.get("client_id"),
                            client_secret=credentials.get("client_secret"),
                            cluster_name=cloud_event_payload.get("name", ""),
                            cluster_location=cloud_event_payload.get("region", ""),
                            resource_group_name=cloud_event_payload.get(
                                "resource_group_name", f"{cloud_event_payload.get('name', '')}-bud-inc"
                            ),
                            tags=TagsModel(
                                Environment="Production",
                                Project="Bud Managed Inference Cluster",
                                Owner="Bud Ecosystem",
                                ManagedBy="Bud",
                            ),
                        )

                        # Create the Azure Terraform manager instance.
                        azure_tf_manager = AzureAksManager(azure_config)

                        # Init
                        prefix = (
                            f"{hashlib.md5(azure_config.cluster_name.encode(), usedforsecurity=False).hexdigest()}"
                        )
                        init_result = azure_tf_manager.init(prefix)

                        if init_result.returncode != 0:
                            logger.error(f"Terraform init failed: {init_result.stdout}")
                            return ErrorResponse(
                                message="Failed to initialize Terraform for cloud cluster creation",
                                code=HTTPStatus.INTERNAL_SERVER_ERROR.value,
                            ).model_dump(mode="json")

                        # Run Terraform destroy for the Azure cluster.
                        destroy_result = azure_tf_manager.destroy()
                        if destroy_result.returncode != 0:
                            logger.error(f"Terraform destroy failed on Azure: {destroy_result.stdout}")
                            notification_request.payload.event = "delete_namespace"
                            notification_request.payload.content = NotificationContent(
                                title="Cloud cluster deletion failed",
                                message=f"Terraform destroy failed on Azure: {destroy_result.stdout}",
                                status=WorkflowStatus.FAILED,
                            )
                            dapr_workflows.publish_notification(
                                workflow_id=instance_id,
                                notification=notification_request,
                                target_topic_name=delete_cluster_request_json.source_topic,
                                target_name=delete_cluster_request_json.source,
                            )
                            return ErrorResponse(
                                message="Cloud cluster deletion failed on Azure",
                                code=HTTPStatus.INTERNAL_SERVER_ERROR.value,
                            ).model_dump(mode="json")
                        # else:
                        #     logger.info("Cloud cluster deletion successful on Azure")
                        #     notification_request.payload.event = "delete_namespace"
                        #     notification_request.payload.content = NotificationContent(
                        #         title="Cloud cluster deletion successful",
                        #         message="Azure cluster resources deleted successfully",
                        #         status=WorkflowStatus.COMPLETED,
                        #     )
                        #     dapr_workflows.publish_notification(
                        #         workflow_id=instance_id,
                        #         notification=notification_request,
                        #         target_topic_name=delete_cluster_request_json.source_topic,
                        #         target_name=delete_cluster_request_json.source,
                        #     )

                        # azure_tf_manager.cleanup()
                    case "aws":
                        # Build the AWS configuration instance from the payload.
                        aws_config = AWSConfig(
                            access_key=cloud_event_payload.get("access_key_id"),
                            secret_key=cloud_event_payload.get("secret_access_key"),
                            region=cloud_event_payload.get("region", ""),
                            cluster_name=cloud_event_payload.get("name", ""),
                            vpc_name=cloud_event_payload.get(
                                "vpc_name", f"{cloud_event_payload.get('name', '')}-bud-inc"
                            ),
                            tags=TagsModel(
                                Environment="Production",
                                Project="Bud Managed Inference Cluster",
                                Owner="Bud Ecosystem",
                                ManagedBy="Bud",
                            ),
                        )
                        # Create the AWS Terraform manager instance.
                        aws_tf_manager = AWSEksManager(aws_config)

                        prefix = f"{hashlib.md5(aws_config.cluster_name.encode(), usedforsecurity=False).hexdigest()}"
                        init_result = aws_tf_manager.init(prefix)
                        if init_result.returncode != 0:
                            logger.error(f"Terraform init failed: {init_result.stdout}")
                            return ErrorResponse(
                                message="Failed to initialize Terraform for cloud cluster creation",
                                code=HTTPStatus.INTERNAL_SERVER_ERROR.value,
                            ).model_dump(mode="json")

                        # Run Terraform destroy for the AWS cluster.
                        destroy_result = aws_tf_manager.destroy()
                        if destroy_result.returncode != 0:
                            logger.error(f"Terraform destroy failed on AWS: {destroy_result.stdout}")
                            notification_request.payload.event = "delete_namespace"
                            notification_request.payload.content = NotificationContent(
                                title="Cloud cluster deletion failed",
                                message=f"Terraform destroy failed on AWS: {destroy_result.stdout}",
                                status=WorkflowStatus.FAILED,
                            )
                            dapr_workflows.publish_notification(
                                workflow_id=instance_id,
                                notification=notification_request,
                                target_topic_name=delete_cluster_request_json.source_topic,
                                target_name=delete_cluster_request_json.source,
                            )
                            return ErrorResponse(
                                message="Cloud cluster deletion failed on AWS",
                                code=HTTPStatus.INTERNAL_SERVER_ERROR.value,
                            ).model_dump(mode="json")
                        # else:
                        #     logger.info("Cloud cluster deletion successful on AWS")
                        #     notification_request.payload.event = "delete_namespace"
                        #     notification_request.payload.content = NotificationContent(
                        #         title="Cloud cluster deletion successful",
                        #         message="AWS cluster resources deleted successfully",
                        #         status=WorkflowStatus.COMPLETED,
                        #     )
                        #     dapr_workflows.publish_notification(
                        #         workflow_id=instance_id,
                        #         notification=notification_request,
                        #         target_topic_name=delete_cluster_request_json.source_topic,
                        #         target_name=delete_cluster_request_json.source,
                        #     )
                    case _:
                        raise ValueError(f"Unsupported cloud provider: {cloud_provider_id}")

            except Exception as e:
                logger.error(f"Error deleting cloud provider resources: {e}\n{traceback.format_exc()}")
                notification_request.payload.event = "delete_namespace"
                notification_request.payload.content = NotificationContent(
                    title="Cloud cluster deletion failed",
                    message=f"Error deleting cloud provider resources: {str(e)}",
                    status=WorkflowStatus.FAILED,
                )
                dapr_workflows.publish_notification(
                    workflow_id=instance_id,
                    notification=notification_request,
                    target_topic_name=delete_cluster_request_json.source_topic,
                    target_name=delete_cluster_request_json.source,
                )
                return ErrorResponse(
                    message=f"Error deleting cloud provider resources: {str(e)}",
                    code=HTTPStatus.INTERNAL_SERVER_ERROR.value,
                ).model_dump(mode="json")

        else:
            if delete_cluster_request_json.cluster_config is not None:
                delete_cluster_req = DeleteCluster(
                    platform=delete_cluster_request_json.platform,
                    cluster_config=delete_cluster_request_json.cluster_config,
                )
                delete_cluster_result = yield ctx.call_activity(
                    DeleteClusterWorkflow.delete_cluster_resources, input=delete_cluster_req.model_dump_json()
                )
                logger.info(f"Delete cluster result: {delete_cluster_result}")

                if delete_cluster_result.get("code", HTTPStatus.OK.value) != HTTPStatus.OK.value:
                    # notify activity that cluster deletion failed
                    notification_req.payload.event = "delete_namespace"
                    notification_req.payload.content = NotificationContent(
                        title="Cluster deletion failed",
                        message=delete_cluster_result["message"],
                        status=WorkflowStatus.FAILED,
                    )
                    dapr_workflows.publish_notification(
                        workflow_id=instance_id,
                        notification=notification_req,
                        target_topic_name=delete_cluster_request_json.source_topic,
                        target_name=delete_cluster_request_json.source,
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
                target_topic_name=delete_cluster_request_json.source_topic,
                target_name=delete_cluster_request_json.source,
            )

            if delete_cluster_request_json.cluster_config is not None:
                # get the cluster config from the database
                delete_cluster_from_db_result = yield ctx.call_activity(
                    DeleteClusterWorkflow.delete_cluster_from_db, input=str(cluster_id)
                )
                if delete_cluster_from_db_result.get("code", HTTPStatus.OK.value) != HTTPStatus.OK.value:
                    notification_req.payload.event = "delete_namespace"
                    notification_req.payload.content = NotificationContent(
                        title="Cluster deleted",
                        message="Cluster deleted successfully",
                        status=WorkflowStatus.FAILED,
                    )
                    dapr_workflows.publish_notification(
                        workflow_id=instance_id,
                        notification=notification_req,
                        target_topic_name=delete_cluster_request_json.source_topic,
                        target_name=delete_cluster_request_json.source,
                    )
                    # yield ctx.call_activity(notify_activity, input=notification_activity_request.model_dump_json())
                    return
        asyncio.run(ClusterOpsService.delete_node_info_from_statestore(str(cluster_id)))

        # notify activity that cluster deleting process is initiated
        notification_req.payload.event = "results"
        notification_req.payload.content = NotificationContent(
            title="Cluster deleted successfully",
            message=f"Cluster {cluster_id} was deleted successfully",
            status=WorkflowStatus.COMPLETED,
            results={"cluster_id": str(cluster_id)},
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=delete_cluster_request_json.source_topic,
            target_name=delete_cluster_request_json.source,
        )

        notification_req.payload.event = "delete_namespace"
        notification_req.payload.content = NotificationContent(
            title="Cluster deleted successfully",
            message=f"Cluster {cluster_id} was deleted successfully",
            status=WorkflowStatus.COMPLETED,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=delete_cluster_request_json.source_topic,
            target_name=delete_cluster_request_json.source,
        )

        return

    async def __call__(
        self, request: ClusterDeleteRequest, workflow_id: Optional[str] = None
    ) -> Union[WorkflowMetadataResponse, ErrorResponse]:
        """Schedule the workflow to delete a cluster."""
        workflow_id = str(workflow_id or uuid.uuid4())
        workflow_name = "delete_cluster"
        workflow_input = request.model_dump_json()
        workflow_steps = [
            WorkflowStep(
                id="delete_namespace",
                title="Deleting Cluster",
                description="Deleting Cluster",
            ),
        ]
        eta = 1 * 30
        response = await dapr_workflows.schedule_workflow(
            workflow_name=workflow_name,
            workflow_input=workflow_input,
            workflow_id=str(workflow_id or uuid.uuid4()),
            workflow_steps=workflow_steps,
            eta=eta,
            target_topic_name=request.source_topic,
            target_name=request.source,
        )
        # response = WorkflowMetadataResponse(
        #     workflow_id=workflow_id,
        #     workflow_name=workflow_name,
        #     steps=workflow_steps or [],
        #     status=WorkflowStatus.PENDING,
        #     eta=eta,
        # )
        # asyncio.create_task(
        #     dapr_workflows.schedule_workflow(
        #         workflow_name="delete_cluster",
        #         workflow_input=workflow_input,
        #         workflow_id=str(workflow_id or uuid.uuid4()),
        #         workflow_steps=workflow_steps,
        #         eta=1 * 30,
        #         target_topic_name=request.source_topic,
        #         target_name=request.source,
        #     )
        # )
        return response


class UpdateClusterStatusWorkflow:
    @dapr_workflows.register_activity
    @staticmethod
    def compute_cluster_status(ctx: wf.WorkflowActivityContext, cluster_id: str) -> dict:
        """Compute cluster status and node info in an activity thread.

        Returns a JSON-serializable dict with keys:
        - status: ClusterStatusEnum value
        - nodes_info_present: bool
        - node_info: list
        - node_status_change: bool
        - cluster_id: str
        """
        logger = logging.get_logger("ComputeClusterStatus")
        try:
            with DBSession() as session:
                db_cluster = asyncio.run(ClusterService(session)._get_cluster(cluster_id, missing_ok=True))
                if db_cluster is None:
                    logger.info(f"Cluster {cluster_id} not found in the database")
                    return {"skipped": True, "cluster_id": cluster_id, "reason": "cluster_not_found"}

            # Decrypt config
            config_dict = {}
            if db_cluster.configuration:
                try:
                    with DaprServiceCrypto() as dapr_service:
                        configuration_decrypted = dapr_service.decrypt_data(db_cluster.configuration)
                        config_dict = json.loads(configuration_decrypted)
                    logger.debug(f"Successfully decrypted config for cluster {cluster_id}")
                except Exception as e:
                    logger.error(f"Failed to decrypt config for cluster {cluster_id}: {e}")
                    return {
                        "skipped": True,
                        "cluster_id": cluster_id,
                        "reason": "crypto_unavailable",
                    }

            # Compute node status
            cluster_status, nodes_info_present, node_info, node_status_change = asyncio.run(
                ClusterOpsService.update_node_status(db_cluster.id, config_dict)
            )

            return {
                "status": cluster_status,
                "prev_status": db_cluster.status,
                "nodes_info_present": nodes_info_present,
                "node_info": node_info,
                "node_status_change": node_status_change,
                "cluster_id": str(db_cluster.id),
                "skipped": False,
            }
        except Exception as e:
            logger.exception(f"Failed to compute cluster status for {cluster_id}: {e}")
            return {"skipped": True, "cluster_id": cluster_id, "reason": str(e)}

    @dapr_workflows.register_workflow
    @staticmethod
    def update_cluster_status(ctx: wf.DaprWorkflowContext, cluster_id: str):
        """Update the cluster status."""
        logger = logging.get_logger("UpdateClusterStatus")
        instance_id = str(ctx.instance_id)
        logger.info(f"Updating cluster status for workflow_id: {instance_id}")

        # Delegate heavy lifting to an activity to avoid blocking workflow thread
        result = yield ctx.call_activity(
            UpdateClusterStatusWorkflow.compute_cluster_status,
            input=cluster_id,
        )
        if result.get("skipped"):
            logger.info(f"Skipping update for cluster {cluster_id}: {result.get('reason')}")
            return result

        cluster_status = result["status"]
        prev_status = result.get("prev_status")
        nodes_info_present = result["nodes_info_present"]
        node_info = result["node_info"]
        node_status_change = result["node_status_change"]
        # Always send notification when node_info is available to ensure resource counts are up-to-date
        # This ensures gpu_count/cpu_count are recalculated even without status changes
        has_node_info = node_info and "nodes" in node_info and len(node_info.get("nodes", [])) > 0
        if cluster_status != prev_status or not nodes_info_present or node_status_change or has_node_info:
            logger.info(f"Sending cluster status notification: {cluster_status}")
            event_name = "cluster-status-update"
            event_type = "results"
            content = NotificationContent(
                title="Cluster status updated",
                message=f"Cluster {cluster_id} status updated",
                status=WorkflowStatus.COMPLETED,
                result={"cluster_id": cluster_id, "status": cluster_status, "node_info": node_info},
            )
            notification_request = NotificationRequest(
                notification_type=NotificationType.EVENT,
                name=event_name,
                payload=NotificationPayload(
                    category=NotificationCategory.INTERNAL,
                    type=event_name,
                    event=event_type,
                    content=content,
                    workflow_id=instance_id,
                ),
                topic_keys=["budAppMessages"],
            )
            with DaprService() as dapr_service:
                dapr_service.publish_to_topic(
                    data=notification_request.model_dump(mode="json"),
                    target_topic_name="budAppMessages",
                    target_name=None,
                    event_type=notification_request.payload.type,
                )
            logger.info(f"Cluster status update notification sent: {notification_request}")
            # yield ctx.call_activity(notify_activity, input=notification_activity_request.model_dump_json())

        # Workflow completes after single execution - no perpetual loop
        logger.info(f"Cluster status update workflow completed for cluster {cluster_id}")
        return {"status": "completed", "cluster_id": cluster_id}

    async def __call__(
        self, request: str, workflow_id: Optional[str] = None
    ) -> Union[WorkflowMetadataResponse, ErrorResponse]:
        """Schedule the workflow to update the cluster status."""
        return await dapr_workflows.schedule_workflow(
            workflow_name="update_cluster_status",
            workflow_input=request,
            workflow_id=str(workflow_id or uuid.uuid4()),
            workflow_steps=[
                WorkflowStep(
                    id="update_cluster_status",
                    title="Updating cluster status",
                    description="Update the cluster status",
                ),
            ],
            eta=1 * 30,
            target_topic_name=None,
            target_name=None,
        )
