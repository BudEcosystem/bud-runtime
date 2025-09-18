import asyncio
import json
import uuid
from datetime import timedelta
from http import HTTPStatus

import dapr.ext.workflow as wf
from budmicroframe.commons.constants import WorkflowStatus
from budmicroframe.commons.schemas import (
    ErrorResponse,
    NotificationContent,
    NotificationRequest,
    SuccessResponse,
    WorkflowMetadataResponse,
    WorkflowStep,
)
from budmicroframe.shared.dapr_workflow import DaprWorkflow

from budeval.commons.logging import logging
from budeval.commons.storage_config import StorageConfig
from budeval.commons.utils import update_workflow_data_in_statestore
from budeval.core.schemas import (
    DatasetCategory,
    GenericDatasetConfig,
    GenericEvaluationRequest,
    GenericModelConfig,
    ModelType,
)
from budeval.core.transformers.registry import TransformerRegistry
from budeval.evals.schemas import DeployEvalJobRequest, StartEvaluationRequest
from budeval.evals.services import EvaluationOpsService


logger = logging.getLogger(__name__)


# Worflow
dapr_workflows = DaprWorkflow()

# Retry Policy
retry_policy = wf.RetryPolicy(
    first_retry_interval=timedelta(seconds=1),
    max_number_of_attempts=1,
    backoff_coefficient=1,
    max_retry_interval=timedelta(seconds=10),
    retry_timeout=timedelta(seconds=100),
)


# EvaluationWorkflow
class EvaluationWorkflow:
    # Activities
    @dapr_workflows.register_activity  # type: ignore [reportUnknownReturnType,reportArgumentType] # noqa
    @staticmethod
    def create_engine_config(
        ctx: wf.WorkflowActivityContext,
        evaluate_model_request: str,
    ) -> dict:
        """Create engine-specific configuration using transformers.

        Args:
            ctx (WorkflowActivityContext): The context of the Dapr workflow
            evaluate_model_request (str): A JSON string containing the evaluate model request parameters
        """
        logger = logging.getLogger("::EVAL:: Create Engine Config")
        logger.debug(f"Creating engine config for {evaluate_model_request}")

        evaluate_model_request_json = StartEvaluationRequest.model_validate_json(evaluate_model_request)

        response: SuccessResponse | ErrorResponse
        try:
            # TODO: check the none cases, see if the opencompass handles it
            # Convert to generic evaluation request
            generic_request = GenericEvaluationRequest(
                eval_request_id=evaluate_model_request_json.uuid,
                engine=evaluate_model_request_json.engine,
                model=GenericModelConfig(
                    api_version=None,
                    model_path=None,
                    tokenizer_path=None,
                    top_p=None,
                    name=evaluate_model_request_json.eval_model_info.model_name,
                    type=ModelType.API,
                    api_key=evaluate_model_request_json.eval_model_info.api_key,
                    base_url=evaluate_model_request_json.eval_model_info.endpoint,
                    temperature=None,
                    max_tokens=None,
                ),
                datasets=[
                    GenericDatasetConfig(
                        name=dataset.dataset_id,
                        category=DatasetCategory.CUSTOM,  # Default category
                        version="1.0.0",
                        split="test",
                        subset=None,
                        sample_size=None,
                        random_seed=None,
                        custom_path=None,
                        custom_format=None,
                    )
                    for dataset in (evaluate_model_request_json.eval_datasets or [])
                ],
                batch_size=8,
                num_workers=1,
                timeout_minutes=30,
                kubeconfig=evaluate_model_request_json.kubeconfig,
                debug=True,
            )

            # Get the appropriate transformer
            transformer = TransformerRegistry.get_transformer(generic_request.engine)

            # Transform the request
            transformed = transformer.transform_request(generic_request)

            # Create ConfigMap with transformed configuration
            from budeval.commons.storage_config import StorageConfig

            from .configmap_manager import ConfigMapManager

            configmap_manager = ConfigMapManager(namespace=StorageConfig.get_current_namespace())

            configmap_result = configmap_manager.create_generic_config_map(
                eval_request_id=str(generic_request.eval_request_id),
                engine=generic_request.engine.value,
                config_files=transformed.config_files,
                kubeconfig=evaluate_model_request_json.kubeconfig,
            )

            logger.info(f"Created {generic_request.engine.value} ConfigMap: {configmap_result['configmap_name']}")
            response = SuccessResponse(
                code=HTTPStatus.CREATED.value,
                message=f"{generic_request.engine.value} configuration created successfully",
                param={
                    **configmap_result,
                    "transformed_data": transformed.model_dump(mode="json"),
                },
            )
            # Manually construct response to ensure code field is included
            return {
                "object": "info",
                "code": HTTPStatus.CREATED.value,
                "message": response.message,
                "param": response.param,
            }
        except Exception as e:
            logger.error(f"Error creating engine config: {e}", exc_info=True)
            response = ErrorResponse(
                message="Error creating engine configuration", code=HTTPStatus.INTERNAL_SERVER_ERROR.value
            )
            # Manually construct error response to ensure code field is included
            return {"object": "error", "code": HTTPStatus.INTERNAL_SERVER_ERROR.value, "message": response.message}

    @dapr_workflows.register_activity  # type: ignore [reportUnknownReturnType,reportArgumentType] # noqa
    @staticmethod
    def deploy_eval_job(
        ctx: wf.WorkflowActivityContext,
        deploy_request: str,
    ) -> dict:
        """Deploy the evaluation job using transformed configuration.

        Args:
            ctx (WorkflowActivityContext): The context of the Dapr workflow, providing
                access to workflow instance information.
            deploy_request (str): A JSON string containing the deployment request with transformed data.
        """
        logger = logging.getLogger("::EVAL:: Eval Deployment Job")
        logger.debug(f"Deploying evaluation job with request: {deploy_request}")

        workflow_id = ctx.workflow_id
        task_id = ctx.task_id

        deploy_request_json = json.loads(deploy_request)

        # Extract the original request and config metadata
        evaluate_model_request_json = StartEvaluationRequest.model_validate_json(
            deploy_request_json["evaluate_model_request"]
        )
        config_metadata = deploy_request_json["config_metadata"]

        # Create deployment payload with engine from request
        payload = DeployEvalJobRequest(
            engine=evaluate_model_request_json.engine.value,
            eval_request_id=str(evaluate_model_request_json.uuid),
            api_key=evaluate_model_request_json.eval_model_info.api_key,
            base_url=evaluate_model_request_json.eval_model_info.endpoint,
            kubeconfig=evaluate_model_request_json.kubeconfig,
            dataset=[dataset.dataset_id for dataset in evaluate_model_request_json.eval_datasets],
        )

        logger.debug(f"Deploying evaluation job for engine: {payload.engine}")

        response: SuccessResponse | ErrorResponse
        try:
            # Reconstruct job config from metadata (without large args)
            job_config = {
                "job_id": config_metadata.get("job_id"),
                "engine": config_metadata.get("engine"),
                "image": config_metadata.get("image"),
                "command": ["/bin/bash", "-c"],  # Standard command
                "env_vars": config_metadata.get("env_vars", {}),
                "config_volume": config_metadata.get("config_volume"),
                "data_volumes": config_metadata.get("data_volumes"),
                "output_volume": config_metadata.get("output_volume"),
                "cpu_request": config_metadata.get("cpu_request"),
                "cpu_limit": config_metadata.get("cpu_limit"),
                "memory_request": config_metadata.get("memory_request"),
                "memory_limit": config_metadata.get("memory_limit"),
                "ttl_seconds": config_metadata.get("ttl_seconds"),
                "backoff_limit": config_metadata.get("backoff_limit"),
                "extra_params": {},
            }

            # Reconstruct minimal transformed_data structure
            transformed_data = {"job_config": job_config}

            # Pass reconstructed data to the service
            job_details = asyncio.run(
                EvaluationOpsService.deploy_eval_job_with_transformation(
                    payload, transformed_data, str(task_id), workflow_id
                )
            )

            response = SuccessResponse(
                code=HTTPStatus.OK.value, message="Evaluation job deployed successfully", param=dict(job_details)
            )

            # Create initial job record in ClickHouse with status=running
            try:
                from budeval.evals.storage.factory import get_storage_adapter, initialize_storage

                storage = get_storage_adapter()

                async def _init_and_create():
                    await initialize_storage(storage)
                    # Build initial record fields
                    job_id = job_details.get("job_id")
                    model_name = evaluate_model_request_json.eval_model_info.model_name
                    engine = evaluate_model_request_json.engine.value
                    experiment_id = (
                        str(evaluate_model_request_json.experiment_id)
                        if evaluate_model_request_json.experiment_id
                        else None
                    )

                    if hasattr(storage, "create_initial_job_record"):
                        await storage.create_initial_job_record(
                            job_id=job_id,
                            experiment_id=experiment_id,
                            model_name=model_name,
                            engine=engine,
                            status="running",
                        )

                asyncio.run(_init_and_create())
            except Exception as ch_e:
                logger.warning(f"Failed to create initial ClickHouse job record: {ch_e}")
        except Exception as e:
            logger.error(f"Error deploying evaluation job: {e}", exc_info=True)
            response = ErrorResponse(
                message="Error deploying evaluation job", code=HTTPStatus.INTERNAL_SERVER_ERROR.value
            )
        return response.model_dump(mode="json")

    @dapr_workflows.register_activity  # type: ignore [reportUnknownReturnType,reportArgumentType] # noqa
    @staticmethod
    def verify_cluster_connection(
        ctx: wf.WorkflowActivityContext,
        verify_cluster_connection_request: str,
    ) -> dict:
        """Verify the cluster connection.

        Args:
            ctx (WorkflowActivityContext): The context of the Dapr workflow, providing
                access to workflow instance information.
            verify_cluster_connection_request (str): A JSON string containing the verify cluster connection request parameters
                including model name, API key, and cluster configuration.
        """
        logger = logging.getLogger("::EVAL:: VerifyClusterConnectionActivity")
        logger.debug(f"Verifying cluster connection for {verify_cluster_connection_request}")

        workflow_id = ctx.workflow_id
        task_id = str(ctx.task_id)

        verify_cluster_connection_request_json = StartEvaluationRequest.model_validate_json(
            verify_cluster_connection_request
        )

        try:
            cluster_verified = asyncio.run(
                EvaluationOpsService.verify_cluster_connection(
                    verify_cluster_connection_request_json, task_id, workflow_id
                )
            )

            if cluster_verified:
                return SuccessResponse(
                    code=HTTPStatus.OK.value,
                    message="Cluster connection verified successfully",
                    param={"cluster_verified": cluster_verified},
                ).model_dump(mode="json")
            else:
                return ErrorResponse(
                    code=HTTPStatus.BAD_REQUEST.value, message="Cluster connection verification failed"
                ).model_dump(mode="json")
        except Exception as e:
            error_msg = (
                f"Error verifying cluster connection for workflow_id: {workflow_id} and task_id: {task_id}, error: {e}"
            )
            logger.error(error_msg)
            return ErrorResponse(
                message="Cluster connection verification failed", code=HTTPStatus.BAD_REQUEST.value
            ).model_dump(mode="json")  # type: ignore # noqa

    @dapr_workflows.register_activity  # type: ignore [reportUnknownReturnType,reportArgumentType] # noqa
    @staticmethod
    def extract_and_process_results(
        ctx: wf.WorkflowActivityContext,
        extract_request: str,
    ) -> dict:
        """Extract and process evaluation results from PVC.

        Args:
            ctx (WorkflowActivityContext): The context of the Dapr workflow
            extract_request (str): A JSON string containing the extraction request parameters
                including job_id, model_name, namespace, and kubeconfig.
        """
        logger = logging.getLogger("::EVAL:: Extract Results")
        logger.debug(f"Extracting results for {extract_request}")

        extract_request_json = json.loads(extract_request)
        job_id = extract_request_json["job_id"]
        model_name = extract_request_json["model_name"]
        # Resolve namespace with fallback to current cluster namespace
        namespace = extract_request_json.get("namespace") or StorageConfig.get_current_namespace()
        kubeconfig = extract_request_json.get("kubeconfig")
        experiment_id = extract_request_json.get("experiment_id")

        response: SuccessResponse | ErrorResponse
        try:
            from budeval.evals.results_processor import ResultsProcessor
            from budeval.evals.storage.factory import get_storage_adapter, initialize_storage

            # Run async operations in a new event loop
            async def extract_with_storage():
                # Create storage adapter within this event loop context
                storage = get_storage_adapter()
                processor = ResultsProcessor(storage)

                # Initialize storage if needed (e.g., ClickHouse connection pool)
                if hasattr(storage, "initialize"):
                    await initialize_storage(storage)

                # Extract and process results
                return await processor.extract_and_process(
                    job_id=job_id,
                    model_name=model_name,
                    namespace=namespace,
                    kubeconfig=kubeconfig,
                    experiment_id=experiment_id,
                )

            # Run in a new event loop (Dapr workflows run in threads)
            results = asyncio.run(extract_with_storage())

            logger.info(f"Successfully processed results for job {job_id}")
            response = SuccessResponse(
                code=HTTPStatus.OK.value,
                message="Results extracted and processed successfully",
                param={
                    "job_id": job_id,
                    "datasets_processed": len(results.datasets),
                    "overall_accuracy": results.summary.overall_accuracy,
                    "storage_path": results.extraction_path,
                },
            )
        except Exception as e:
            logger.error(f"Error extracting results: {e}", exc_info=True)
            response = ErrorResponse(
                message=f"Error extracting results: {str(e)}", code=HTTPStatus.INTERNAL_SERVER_ERROR.value
            )
        return response.model_dump(mode="json")

    @dapr_workflows.register_activity  # type: ignore [reportUnknownReturnType,reportArgumentType] # noqa
    @staticmethod
    def monitor_eval_job_progress(
        ctx: wf.WorkflowActivityContext,
        monitor_request: str,
    ) -> dict:
        """Monitor the evaluation job progress.

        Args:
            ctx (WorkflowActivityContext): The context of the Dapr workflow, providing
                access to workflow instance information.
            monitor_request (str): A JSON string containing the monitoring request parameters
                including job_id, kubeconfig, and namespace.
        """
        logger = logging.getLogger("::EVAL:: Monitor Job Progress")
        logger.debug(f"Monitoring job progress for {monitor_request}")

        monitor_request_json = json.loads(monitor_request)
        job_id = monitor_request_json["job_id"]
        kubeconfig = monitor_request_json["kubeconfig"]
        # Resolve namespace with fallback to current cluster namespace
        namespace = monitor_request_json.get("namespace") or StorageConfig.get_current_namespace()

        response: SuccessResponse | ErrorResponse
        try:
            job_status = asyncio.run(EvaluationOpsService.get_job_status(job_id, kubeconfig, namespace))

            logger.debug(f"Job status for {job_id}: {job_status}")

            response = SuccessResponse(
                code=HTTPStatus.OK.value, message="Job status retrieved successfully", param=job_status
            )
        except Exception as e:
            logger.error(f"Error monitoring job progress: {e}", exc_info=True)
            response = ErrorResponse(
                message="Error monitoring job progress", code=HTTPStatus.INTERNAL_SERVER_ERROR.value
            )
        return response.model_dump(mode="json")

    @dapr_workflows.register_workflow  # type: ignore [reportUnknownReturnType,reportArgumentType] # noqa  # type: ignore [reportUnknownReturnType,reportArgumentType] # noqa
    @staticmethod
    def evaluate_model(ctx: wf.DaprWorkflowContext, evaluate_model_request: str):
        """Execute the workflow to evaluate a model.

        This workflow verifies the cluster connection, deploys an evaluation job, and monitors its progress.

        Args:
            ctx (DaprWorkflowContext): The context of the Dapr workflow, providing
                access to workflow instance information.
            evaluate_model_request (str): A JSON string containing the evaluation request parameters
                including model name, API key, and cluster configuration.
        """
        logger = logging.getLogger("::EVAL:: EvaluateModelWorkflow")
        logger.debug(f"Evaluating model {evaluate_model_request}")

        instance_id = str(ctx.instance_id)

        # Parse request to check if this is monitoring phase
        request_dict = json.loads(evaluate_model_request)
        phase = request_dict.get("phase", "deployment")

        logger.debug(f"Workflow phase: {phase}")

        if phase == "monitoring":
            # Handle monitoring phase with proper Dapr pattern
            logger.info("Transitioning to monitoring phase")
            yield from EvaluationWorkflow._handle_monitoring_phase(ctx, evaluate_model_request)
            return

        # Continue with deployment phase
        logger.info(f"Evaluating model for instance_id: {instance_id}")

        # Parse the request
        try:
            evaluate_model_request_json = StartEvaluationRequest.model_validate_json(evaluate_model_request)
        except Exception as e:
            logger.error(f"Error parsing cluster create request: {e}", exc_info=True)
            return

        # Set workflow data
        update_workflow_data_in_statestore(
            instance_id,
            evaluate_model_request_json.model_dump(mode="json"),
        )

        # Notifications
        # Set up notification
        workflow_name = "evaluate_model"

        # Notification Request
        notification_request = NotificationRequest.from_cloud_event(
            cloud_event=evaluate_model_request_json, name=workflow_name, workflow_id=instance_id
        )
        notification_req = notification_request.model_copy(deep=True)
        notification_req.payload.event = "monitor_eval_job_progress"
        notification_req.payload.content = NotificationContent(
            title="Model evaluation process is initiated",
            message=f"Model evaluation process is initiated for {evaluate_model_request_json.eval_model_info.model_name}",
            status=WorkflowStatus.STARTED,
        )

        # Publish initial notification
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=evaluate_model_request_json.source_topic,
            target_name=evaluate_model_request_json.source,
        )

        # Set initial ETA
        notification_req.payload.event = "eta"
        eta_minutes = 30
        notification_req.payload.content = NotificationContent(
            title="Estimated time to completion",
            message=f"{eta_minutes}",
            status=WorkflowStatus.RUNNING,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=evaluate_model_request_json.source_topic,
            target_name=evaluate_model_request_json.source,
        )

        # End Of Notifications
        logger.info("Starting Cluster Connection Verification")
        verify_cluster_connection_result = yield ctx.call_activity(
            EvaluationWorkflow.verify_cluster_connection,
            input=evaluate_model_request_json.model_dump_json(),
        )

        logger.debug(f"Cluster Connection Verification Result: {verify_cluster_connection_result}")

        if verify_cluster_connection_result.get("code", HTTPStatus.OK.value) != HTTPStatus.OK.value:
            logger.error(f"Cluster Connection Verification Failed: {verify_cluster_connection_result.get('message')}")
            # notify activity that cluster verification failed
            notification_req.payload.event = "verify_cluster_connection"
            notification_req.payload.content = NotificationContent(
                title="Cluster verification failed",
                message=verify_cluster_connection_result["message"],
                status=WorkflowStatus.FAILED,
                primary_action="retry",
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=evaluate_model_request_json.source_topic,
                target_name=evaluate_model_request_json.source,
            )
            # Emit terminal results event
            notification_req.payload.event = "results"
            notification_req.payload.content = NotificationContent(
                title="Evaluation failed",
                message=verify_cluster_connection_result["message"],
                status=WorkflowStatus.FAILED,
                primary_action="retry",
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=evaluate_model_request_json.source_topic,
                target_name=evaluate_model_request_json.source,
            )
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
            target_topic_name=evaluate_model_request_json.source_topic,
            target_name=evaluate_model_request_json.source,
        )

        # notify activity ETA
        notification_req.payload.event = "eta"
        notification_req.payload.content = NotificationContent(
            title="Estimated time to completion",
            message=f"{25}",
            status=WorkflowStatus.RUNNING,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=evaluate_model_request_json.source_topic,
            target_name=evaluate_model_request_json.source,
        )

        # Create Engine Configuration
        logger.info(f"Creating {evaluate_model_request_json.engine.value} configuration")
        create_config_result = yield ctx.call_activity(
            EvaluationWorkflow.create_engine_config,
            input=evaluate_model_request_json.model_dump_json(),
        )

        # Log only essential info to avoid large payload serialization issues
        logger.debug(
            f"Engine Configuration Creation Result: ConfigMap '{create_config_result.get('param', {}).get('configmap_name')}' in namespace '{create_config_result.get('param', {}).get('namespace')}'"
        )

        # Print the code value
        logger.debug(f"Engine Configuration Creation Result Code: {create_config_result.get('code')}")

        # Check if the result code indicates an error (not in 2xx success range)
        result_code = create_config_result.get("code", HTTPStatus.OK.value)
        if not (200 <= result_code < 300):
            logger.error(f"Engine Configuration Creation Failed: {create_config_result.get('message')}")
            # notify that config creation failed
            notification_req.payload.event = "preparing_eval_engine"
            notification_req.payload.content = NotificationContent(
                title="Configuration creation failed",
                message=create_config_result["message"],
                status=WorkflowStatus.FAILED,
                primary_action="retry",
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=evaluate_model_request_json.source_topic,
                target_name=evaluate_model_request_json.source,
            )
            # Emit terminal results event
            notification_req.payload.event = "results"
            notification_req.payload.content = NotificationContent(
                title="Evaluation failed",
                message=create_config_result["message"],
                status=WorkflowStatus.FAILED,
                primary_action="retry",
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=evaluate_model_request_json.source_topic,
                target_name=evaluate_model_request_json.source,
            )
            return

        # notify that config creation is successful
        notification_req.payload.event = "preparing_eval_engine"
        configmap_name = create_config_result.get("param", {}).get("configmap_name", "configuration")
        engine_name = evaluate_model_request_json.engine.value
        notification_req.payload.content = NotificationContent(
            title="Configuration created successfully",
            message=f"{engine_name} configuration '{configmap_name}' created for model",
            status=WorkflowStatus.COMPLETED,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=evaluate_model_request_json.source_topic,
            target_name=evaluate_model_request_json.source,
        )

        # Deploy Evaluation Job with essential metadata (avoid large payload)
        config_metadata = create_config_result.get("param", {})
        deploy_request = {
            "evaluate_model_request": evaluate_model_request_json.model_dump_json(),
            "config_metadata": {
                "configmap_name": config_metadata.get("configmap_name"),
                "namespace": config_metadata.get("namespace"),
                "engine": config_metadata.get("engine"),
                "job_id": config_metadata.get("transformed_data", {}).get("job_config", {}).get("job_id"),
                "image": config_metadata.get("transformed_data", {}).get("job_config", {}).get("image"),
                "env_vars": config_metadata.get("transformed_data", {}).get("job_config", {}).get("env_vars", {}),
                "cpu_request": config_metadata.get("transformed_data", {}).get("job_config", {}).get("cpu_request"),
                "cpu_limit": config_metadata.get("transformed_data", {}).get("job_config", {}).get("cpu_limit"),
                "memory_request": config_metadata.get("transformed_data", {})
                .get("job_config", {})
                .get("memory_request"),
                "memory_limit": config_metadata.get("transformed_data", {}).get("job_config", {}).get("memory_limit"),
                "ttl_seconds": config_metadata.get("transformed_data", {}).get("job_config", {}).get("ttl_seconds"),
                "backoff_limit": config_metadata.get("transformed_data", {})
                .get("job_config", {})
                .get("backoff_limit"),
                "output_volume": config_metadata.get("transformed_data", {})
                .get("job_config", {})
                .get("output_volume"),
                "data_volumes": config_metadata.get("transformed_data", {}).get("job_config", {}).get("data_volumes"),
                "config_volume": config_metadata.get("transformed_data", {})
                .get("job_config", {})
                .get("config_volume"),
            },
        }

        # Print the deploy request
        logger.debug(f"Deploy Request: {deploy_request}")

        deploy_eval_job_result = yield ctx.call_activity(
            EvaluationWorkflow.deploy_eval_job,
            input=json.dumps(deploy_request),
        )

        logger.debug(f"Deploy Evaluation Job Result: {deploy_eval_job_result}")

        if deploy_eval_job_result.get("code", HTTPStatus.OK.value) != HTTPStatus.OK.value:
            logger.error(f"Deploy Evaluation Job Failed: {deploy_eval_job_result.get('message')}")
            # notify activity that deploy evaluation job failed
            notification_req.payload.event = "deploy_eval_job"
            notification_req.payload.content = NotificationContent(
                title="Deploy evaluation job failed",
                message=deploy_eval_job_result["message"],
                status=WorkflowStatus.FAILED,
                primary_action="retry",
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=evaluate_model_request_json.source_topic,
                target_name=evaluate_model_request_json.source,
            )
            # Emit terminal results event
            notification_req.payload.event = "results"
            notification_req.payload.content = NotificationContent(
                title="Evaluation failed",
                message=deploy_eval_job_result["message"],
                status=WorkflowStatus.FAILED,
                primary_action="retry",
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=evaluate_model_request_json.source_topic,
                target_name=evaluate_model_request_json.source,
            )
            return

        # notify activity that deploy evaluation job is successful
        notification_req.payload.event = "deploy_eval_job"
        notification_req.payload.content = NotificationContent(
            title="Deploy evaluation job successful",
            message=deploy_eval_job_result["message"],
            status=WorkflowStatus.COMPLETED,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=evaluate_model_request_json.source_topic,
            target_name=evaluate_model_request_json.source,
        )

        # Monitor Evaluation Job Progress
        logger.info("Starting job monitoring")

        # Extract job details from deployment result
        job_details = deploy_eval_job_result.get("param", {})
        job_id = job_details.get("job_id")

        if not job_id:
            logger.error("No job_id found in deployment result")
            notification_req.payload.event = "monitor_eval_job_progress"
            notification_req.payload.content = NotificationContent(
                title="Job monitoring failed",
                message="No job ID found to monitor",
                status=WorkflowStatus.FAILED,
                primary_action="retry",
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=evaluate_model_request_json.source_topic,
                target_name=evaluate_model_request_json.source,
            )
            # Emit terminal results event
            notification_req.payload.event = "results"
            notification_req.payload.content = NotificationContent(
                title="Evaluation failed",
                message="No job ID found to monitor",
                status=WorkflowStatus.FAILED,
                primary_action="retry",
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=evaluate_model_request_json.source_topic,
                target_name=evaluate_model_request_json.source,
            )
            return

        # Prepare monitoring request with initial monitoring data
        resolved_namespace = StorageConfig.get_current_namespace()
        monitor_request = {
            "job_id": job_id,
            "kubeconfig": evaluate_model_request_json.kubeconfig,
            "namespace": resolved_namespace,
            "monitoring_attempt": 0,
            "max_attempts": 360,  # 30 minutes with 5-second intervals
            "notification_data": {
                "instance_id": instance_id,
                "source_topic": evaluate_model_request_json.source_topic,
                "source": evaluate_model_request_json.source,
                "model_name": evaluate_model_request_json.eval_model_info.model_name,
            },
        }

        logger.debug(f"Prepared monitor request: {monitor_request}")

        # Start monitoring using proper Dapr pattern
        # Add monitoring state to the request and continue as new
        monitoring_data = {
            **evaluate_model_request_json.model_dump(mode="json"),
            "job_id": job_id,
            "monitoring_attempt": monitor_request.get("monitoring_attempt", 0),
            "max_attempts": monitor_request.get("max_attempts", 360),
            "phase": "monitoring",
            # Carry initial start time for accurate duration on completion
            "job_start_time": ctx.current_utc_datetime.isoformat(),
        }

        logger.info(f"Continuing workflow as monitoring phase for job_id: {job_id}")
        logger.debug(f"Monitoring data: {json.dumps(monitoring_data, indent=2)}")

        ctx.continue_as_new(json.dumps(monitoring_data))
        return

    @staticmethod
    def _handle_monitoring_phase(ctx: wf.DaprWorkflowContext, request_str: str):
        """Handle the monitoring phase using proper Dapr continue_as_new pattern."""
        logger = logging.getLogger("::EVAL:: Monitoring Phase")

        logger.debug(f"Monitoring phase handler called with request: {request_str[:200]}...")

        # Parse the monitoring request
        try:
            request_data = json.loads(request_str)
            job_id = request_data["job_id"]
            monitoring_attempt = request_data.get("monitoring_attempt", 0) + 1
            max_attempts = request_data.get("max_attempts", 360)
            instance_id = str(ctx.instance_id)

            logger.debug(
                f"Parsed monitoring data - job_id: {job_id}, attempt: {monitoring_attempt}, max_attempts: {max_attempts}"
            )

            # Reconstruct EvaluateModelRequest without monitoring fields
            eval_request_data = {
                k: v
                for k, v in request_data.items()
                if k not in ["job_id", "monitoring_attempt", "max_attempts", "phase", "job_start_time"]
            }
            evaluate_model_request_json = StartEvaluationRequest(**eval_request_data)
            job_start_time_str = request_data.get("job_start_time")

            logger.info(f"Monitoring job {job_id}, attempt {monitoring_attempt}/{max_attempts}")
        except Exception as e:
            logger.error(f"Error parsing monitoring request: {e}", exc_info=True)
            return

        # Check if we've exceeded max attempts
        if monitoring_attempt > max_attempts:
            logger.warning(f"Job {job_id} monitoring timed out after {max_attempts} attempts")
            notification_req = NotificationRequest.from_cloud_event(
                cloud_event=evaluate_model_request_json, name="evaluate_model", workflow_id=instance_id
            )
            notification_req.payload.event = "monitor_eval_job_progress"
            notification_req.payload.content = NotificationContent(
                title="Job monitoring timeout",
                message=f"Job {job_id} monitoring timed out after {max_attempts} attempts (30 minutes)",
                status=WorkflowStatus.FAILED,
                primary_action="retry",
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=evaluate_model_request_json.source_topic,
                target_name=evaluate_model_request_json.source,
            )
            # Emit terminal results event
            notification_req.payload.event = "results"
            notification_req.payload.content = NotificationContent(
                title="Evaluation timeout",
                message=f"Job {job_id} monitoring timed out",
                status=WorkflowStatus.FAILED,
                primary_action="retry",
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=evaluate_model_request_json.source_topic,
                target_name=evaluate_model_request_json.source,
            )
            return  # End workflow on timeout

        # Check job status
        resolved_namespace = StorageConfig.get_current_namespace()
        basic_monitor_request = {
            "job_id": job_id,
            "kubeconfig": evaluate_model_request_json.kubeconfig,
            "namespace": resolved_namespace,
        }

        monitor_result = yield ctx.call_activity(
            EvaluationWorkflow.monitor_eval_job_progress,
            input=json.dumps(basic_monitor_request),
        )

        # Handle monitoring activity failure
        if monitor_result.get("code", HTTPStatus.OK.value) != HTTPStatus.OK.value:
            logger.warning(f"Monitoring attempt {monitoring_attempt} failed: {monitor_result.get('message')}")

            # Wait and continue monitoring
            yield ctx.create_timer(fire_at=ctx.current_utc_datetime + timedelta(seconds=5))

            request_data["monitoring_attempt"] = monitoring_attempt
            ctx.continue_as_new(json.dumps(request_data))
            return

        job_status_data = monitor_result.get("param", {})
        job_status = job_status_data.get("status", "unknown")
        job_details_info = job_status_data.get("details", {})

        # Check if job is completed
        job_completed = False
        final_job_status = None

        if job_status in ["completed", "succeeded", "failed", "error"]:
            job_completed = True
            final_job_status = job_status_data
            logger.info(f"Job {job_id} completed with status: {job_status}")
        elif job_details_info:
            try:
                succeeded = int(job_details_info.get("succeeded", 0))
                failed = int(job_details_info.get("failed", 0))
            except (ValueError, TypeError):
                succeeded = 0
                failed = 0

            if succeeded > 0:
                job_completed = True
                final_job_status = job_status_data
                final_job_status["status"] = "succeeded"
                logger.info(f"Job {job_id} succeeded")
            elif failed > 0:
                job_completed = True
                final_job_status = job_status_data
                final_job_status["status"] = "failed"
                logger.info(f"Job {job_id} failed")

        # If job completed, handle results
        if job_completed and final_job_status:
            final_status = final_job_status.get("status", "unknown")

            notification_req = NotificationRequest.from_cloud_event(
                cloud_event=evaluate_model_request_json, name="evaluate_model", workflow_id=instance_id
            )

            if final_status in ["succeeded", "completed"]:
                # Job succeeded - extract and process results
                logger.info(f"Job {job_id} succeeded, extracting results")

                extract_request = {
                    "job_id": job_id,
                    "model_name": evaluate_model_request_json.eval_model_info.model_name,
                    "namespace": resolved_namespace,
                    "kubeconfig": evaluate_model_request_json.kubeconfig,
                    "experiment_id": str(evaluate_model_request_json.experiment_id)
                    if evaluate_model_request_json.experiment_id
                    else None,
                }

                extract_result = yield ctx.call_activity(
                    EvaluationWorkflow.extract_and_process_results,
                    input=json.dumps(extract_request),
                )

                if extract_result.get("code", HTTPStatus.OK.value) == HTTPStatus.OK.value:
                    results_info = extract_result.get("param", {})
                    # Update final status and duration in ClickHouse
                    try:
                        from datetime import datetime

                        from budeval.evals.storage.factory import get_storage_adapter, initialize_storage

                        storage = get_storage_adapter()

                        async def _update_final():
                            await initialize_storage(storage)
                            engine = evaluate_model_request_json.engine.value
                            model_name = evaluate_model_request_json.eval_model_info.model_name
                            experiment_id = (
                                str(evaluate_model_request_json.experiment_id)
                                if evaluate_model_request_json.experiment_id
                                else None
                            )
                            # Prefer Kubernetes timestamps if available
                            start_time = None
                            end_time = None
                            try:
                                k8s_start = final_job_status.get("start_time") or final_job_status.get("startTime")
                                if k8s_start:
                                    start_time = datetime.fromisoformat(str(k8s_start).replace("Z", "+00:00"))
                            except Exception:
                                start_time = None
                            try:
                                k8s_end = final_job_status.get("completion_time") or final_job_status.get(
                                    "completionTime"
                                )
                                if k8s_end:
                                    end_time = datetime.fromisoformat(str(k8s_end).replace("Z", "+00:00"))
                            except Exception:
                                end_time = None
                            if start_time is None and job_start_time_str:
                                try:
                                    start_time = datetime.fromisoformat(job_start_time_str)
                                except Exception:
                                    start_time = None
                            if end_time is None:
                                end_time = datetime.utcnow()
                            duration = (end_time - start_time).total_seconds() if start_time else None
                            if hasattr(storage, "update_job_status"):
                                await storage.update_job_status(
                                    job_id=job_id,
                                    experiment_id=experiment_id,
                                    model_name=model_name,
                                    engine=engine,
                                    status="succeeded",
                                    job_start_time=start_time,
                                    job_end_time=end_time,
                                    job_duration_seconds=duration,
                                )

                        asyncio.run(_update_final())
                    except Exception as ch_e:
                        logger.warning(f"Failed to update final ClickHouse job record: {ch_e}")
                    notification_req.payload.event = "monitor_eval_job_progress"
                    notification_req.payload.content = NotificationContent(
                        title="Job completed successfully",
                        message=f"Job {job_id} completed successfully. Results processed: {results_info.get('datasets_processed', 0)} datasets, {results_info.get('overall_accuracy', 0):.2f}% accuracy",
                        status=WorkflowStatus.COMPLETED,
                        result=results_info,
                    )
                else:
                    notification_req.payload.event = "monitor_eval_job_progress"
                    notification_req.payload.content = NotificationContent(
                        title="Job completed - Results extraction failed",
                        message=f"Job {job_id} completed successfully but results extraction failed: {extract_result.get('message')}",
                        status=WorkflowStatus.FAILED,
                        primary_action="retry",
                    )
                dapr_workflows.publish_notification(
                    workflow_id=instance_id,
                    notification=notification_req,
                    target_topic_name=evaluate_model_request_json.source_topic,
                    target_name=evaluate_model_request_json.source,
                )
                # Emit terminal results event reflecting final state
                if extract_result.get("code", HTTPStatus.OK.value) == HTTPStatus.OK.value:
                    notification_req.payload.event = "results"
                    notification_req.payload.content = NotificationContent(
                        title="Evaluation results",
                        message="Results are ready",
                        status=WorkflowStatus.COMPLETED,
                        result=results_info,
                    )
                else:
                    notification_req.payload.event = "results"
                    notification_req.payload.content = NotificationContent(
                        title="Evaluation failed",
                        message=f"Results extraction failed: {extract_result.get('message')}",
                        status=WorkflowStatus.FAILED,
                        primary_action="retry",
                    )
                dapr_workflows.publish_notification(
                    workflow_id=instance_id,
                    notification=notification_req,
                    target_topic_name=evaluate_model_request_json.source_topic,
                    target_name=evaluate_model_request_json.source,
                )
                return
            else:
                # Job failed
                notification_req.payload.event = "monitor_eval_job_progress"
                notification_req.payload.content = NotificationContent(
                    title="Job failed",
                    message=f"Job {job_id} failed with status: {final_status}",
                    status=WorkflowStatus.FAILED,
                    primary_action="retry",
                )
                dapr_workflows.publish_notification(
                    workflow_id=instance_id,
                    notification=notification_req,
                    target_topic_name=evaluate_model_request_json.source_topic,
                    target_name=evaluate_model_request_json.source,
                )
                # Emit terminal results event
                notification_req.payload.event = "results"
                notification_req.payload.content = NotificationContent(
                    title="Evaluation failed",
                    message=f"Job {job_id} failed with status: {final_status}",
                    status=WorkflowStatus.FAILED,
                    primary_action="retry",
                )
                dapr_workflows.publish_notification(
                    workflow_id=instance_id,
                    notification=notification_req,
                    target_topic_name=evaluate_model_request_json.source_topic,
                    target_name=evaluate_model_request_json.source,
                )
                # Update failure in ClickHouse
                try:
                    from datetime import datetime

                    from budeval.evals.storage.factory import get_storage_adapter, initialize_storage

                    storage = get_storage_adapter()

                    async def _update_failed():
                        await initialize_storage(storage)
                        engine = evaluate_model_request_json.engine.value
                        model_name = evaluate_model_request_json.eval_model_info.model_name
                        experiment_id = (
                            str(evaluate_model_request_json.experiment_id)
                            if evaluate_model_request_json.experiment_id
                            else None
                        )
                        # Prefer Kubernetes timestamps if available
                        start_time = None
                        end_time = None
                        try:
                            k8s_start = final_job_status.get("start_time") or final_job_status.get("startTime")
                            if k8s_start:
                                start_time = datetime.fromisoformat(str(k8s_start).replace("Z", "+00:00"))
                        except Exception:
                            start_time = None
                        try:
                            k8s_end = final_job_status.get("completion_time") or final_job_status.get("completionTime")
                            if k8s_end:
                                end_time = datetime.fromisoformat(str(k8s_end).replace("Z", "+00:00"))
                        except Exception:
                            end_time = None
                        if start_time is None and job_start_time_str:
                            try:
                                start_time = datetime.fromisoformat(job_start_time_str)
                            except Exception:
                                start_time = None
                        if end_time is None:
                            end_time = datetime.utcnow()
                        duration = (end_time - start_time).total_seconds() if start_time else None
                        if hasattr(storage, "update_job_status"):
                            await storage.update_job_status(
                                job_id=job_id,
                                experiment_id=experiment_id,
                                model_name=model_name,
                                engine=engine,
                                status="failed",
                                job_start_time=start_time,
                                job_end_time=end_time,
                                job_duration_seconds=duration,
                            )

                    asyncio.run(_update_failed())
                except Exception as ch_e:
                    logger.warning(f"Failed to write failure ClickHouse job record: {ch_e}")
                return

        # Job still running - send progress notification if needed
        if monitoring_attempt % 10 == 0:  # Every 50 seconds
            notification_req = NotificationRequest.from_cloud_event(
                cloud_event=evaluate_model_request_json, name="evaluate_model", workflow_id=instance_id
            )
            notification_req.payload.event = "monitor_eval_job_progress"
            notification_req.payload.content = NotificationContent(
                title="Job monitoring in progress",
                message=f"Job {job_id} is still running. Status: {job_status}. Attempt: {monitoring_attempt}/{max_attempts}",
                status=WorkflowStatus.RUNNING,
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=evaluate_model_request_json.source_topic,
                target_name=evaluate_model_request_json.source,
            )

        # Job still running - set timer and continue monitoring
        yield ctx.create_timer(fire_at=ctx.current_utc_datetime + timedelta(seconds=5))

        # Continue as new with updated attempt count
        request_data["monitoring_attempt"] = monitoring_attempt
        ctx.continue_as_new(json.dumps(request_data))
        return  # Required return after continue_as_new

    async def __call__(
        self, request: StartEvaluationRequest, workflow_id: str | None = None
    ) -> WorkflowMetadataResponse | ErrorResponse:
        """Evaluate a model with the given name."""
        logger = logging.getLogger("::EVAL:: EvaluateModelCall")

        # Workflow ID
        workflow_id = str(workflow_id or uuid.uuid4())

        logger.debug(f"Evaluating model {request.eval_model_info.model_name} for request {request.uuid}")
        workflow_steps = [
            WorkflowStep(
                id="verify_cluster_connection",
                title="Verifying Cluster Connection",
                description="Verify if the cluster is reachable",
            ),
            WorkflowStep(
                id="preparing_eval_engine",
                title="Preparing Eval Engine",
                description="Warming up eval enfine",
            ),
            WorkflowStep(
                id="deploy_eval_job",
                title="Deploying Evaluation Job",
                description="Deploy the evaluation job to the cluster",
            ),
            WorkflowStep(
                id="monitor_eval_job_progress",
                title="Monitoring Evaluation Job Progress",
                description="Monitor the progress of the evaluation job",
            ),
        ]

        eta = 30 * 60  # 30 minutes estimate for evaluation jobs
        # Schedule the workflow
        try:
            response = await dapr_workflows.schedule_workflow(
                workflow_name="evaluate_model",
                workflow_input=request.model_dump_json(),
                workflow_id=workflow_id,
                workflow_steps=workflow_steps,
                eta=eta,
                target_topic_name=request.source_topic,
                target_name=request.source,
            )
            return response or ErrorResponse(
                message="Failed to schedule workflow", code=HTTPStatus.INTERNAL_SERVER_ERROR.value
            )
        except Exception as e:
            logger.error(f"Error scheduling workflow: {e}", exc_info=True)
            return ErrorResponse(
                message=f"Error scheduling workflow: {e}", code=HTTPStatus.INTERNAL_SERVER_ERROR.value
            )
