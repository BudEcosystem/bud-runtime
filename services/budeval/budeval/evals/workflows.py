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
from budeval.commons.utils import (
    check_workflow_status_in_statestore,
    update_workflow_data_in_statestore,
)
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

dapr_workflows = DaprWorkflow()


class EvaluationWorkflow:
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

        response = SuccessResponse(
            code=HTTPStatus.OK.value,
            message="Job status retrieved successfully",
            param={},
        )

        monitor_request_json = json.loads(monitor_request)
        job_id = monitor_request_json["job_id"]
        kubeconfig = monitor_request_json["kubeconfig"]
        # Resolve namespace with fallback to current cluster namespace
        namespace = monitor_request_json.get("namespace") or StorageConfig.get_current_namespace()

        response: SuccessResponse | ErrorResponse
        try:
            # Handle async operations with proper event loop management
            try:
                asyncio.get_running_loop()
                # If we're in an existing loop, we need to run in a new thread
                import concurrent.futures

                def run_in_new_loop():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        # Clear any thread-local storage to force new instances
                        import threading

                        from budeval.evals.storage.factory import (
                            _clickhouse_storage_by_thread,
                        )

                        thread_id = threading.get_ident()
                        if thread_id in _clickhouse_storage_by_thread:
                            del _clickhouse_storage_by_thread[thread_id]

                        return new_loop.run_until_complete(
                            EvaluationOpsService.get_job_status(job_id, kubeconfig, namespace)
                        )
                    finally:
                        new_loop.close()

                # Run in a separate thread with its own event loop
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(run_in_new_loop)
                    job_status = future.result()
            except RuntimeError:
                # No loop running, safe to use asyncio.run()
                job_status = asyncio.run(EvaluationOpsService.get_job_status(job_id, kubeconfig, namespace))

            logger.debug(f"Job status for {job_id}: {job_status}")

            response = SuccessResponse(
                code=HTTPStatus.OK.value,
                message="Job status retrieved successfully",
                param=job_status,
            )
        except Exception as e:
            logger.error(f"Error monitoring job progress: {e}", exc_info=True)
            response = ErrorResponse(
                message="Error monitoring job progress",
                code=HTTPStatus.INTERNAL_SERVER_ERROR.value,
            )
        return response.model_dump(mode="json")

    @dapr_workflows.register_activity  # type: ignore [reportUnknownReturnType,reportArgumentType] # noqa
    @staticmethod
    def monitor_eval_job_simple(
        ctx: wf.WorkflowActivityContext,
        monitor_request: str,
    ) -> dict:
        """Monitor a job until completion."""
        logger = logging.getLogger("::EVAL:: Simple Monitor")

        try:
            request = json.loads(monitor_request)
            job_id = request["job_id"]
            kubeconfig = request.get("kubeconfig")
            namespace = request.get("namespace", "budeval")

            from budeval.registry.orchestrator.ansible_orchestrator import (
                AnsibleOrchestrator,
            )

            orchestrator = AnsibleOrchestrator()

            # Get simple status
            result = orchestrator.get_job_status_simple(job_id, namespace, kubeconfig)

            return result

        except Exception as e:
            logger.error(f"Error in simple monitoring: {e}", exc_info=True)
            return {"success": False, "job_status": None, "error": str(e)}

    @dapr_workflows.register_activity  # type: ignore [reportUnknownReturnType,reportArgumentType] # noqa
    @staticmethod
    def extract_results_simple(
        ctx: wf.WorkflowActivityContext,
        extraction_request: str,
    ) -> dict:
        """Extract and process evaluation results using ResultsProcessor."""
        logger = logging.getLogger("::EVAL:: Extract Results")

        try:
            request = json.loads(extraction_request)
            job_id = request["job_id"]
            evaluation_id = request.get("evaluation_id")
            model_name = request["model_name"]
            kubeconfig = request.get("kubeconfig")
            namespace = request.get("namespace", "budeval")
            experiment_id = request.get("experiment_id")

            from budeval.evals.results_processor import ResultsProcessor

            logger.info(f"Starting extraction for job {job_id}")

            # Simple async execution - no complex threading needed
            # The synchronous ClickHouse adapter handles event loop issues
            processor = ResultsProcessor()
            results = asyncio.run(
                processor.extract_and_process(
                    job_id=job_id,
                    evaluation_id=evaluation_id,
                    model_name=model_name,
                    namespace=namespace,
                    kubeconfig=kubeconfig,
                    experiment_id=experiment_id,
                )
            )

            logger.info(f"Successfully extracted and processed results for job {job_id}")

            # Return structured response
            return {
                "success": True,
                "job_id": job_id,
                "extracted_path": results.extraction_path,
                "files_count": len(results.datasets),
                "overall_accuracy": results.summary.overall_accuracy,
                "total_datasets": results.summary.total_datasets,
                "total_examples": results.summary.total_examples,
                "total_correct": results.summary.total_correct,
                "dataset_accuracies": results.summary.dataset_accuracies,
                "model_name": results.summary.model_name,
                "message": f"Extraction completed successfully. {results.summary.total_datasets} datasets processed with {results.summary.overall_accuracy:.2f}% overall accuracy",
                # "results": results.model_dump(),
            }

        except Exception as e:
            logger.error(f"Error in extraction and processing: {e}", exc_info=True)
            return {
                "success": False,
                "job_id": request.get("job_id", "unknown"),
                "extracted_path": "",
                "files_count": 0,
                "message": f"Extraction failed: {str(e)}",
                "error": str(e),
            }

    @dapr_workflows.register_workflow  # type: ignore [reportUnknownReturnType,reportArgumentType] # noqa
    @staticmethod
    def monitor_job_workflow(ctx: wf.DaprWorkflowContext, monitor_request: str):
        """Child workflow dedicated to monitoring a job until completion.

        Uses continue_as_new pattern to prevent replay storms from timer accumulation.
        """
        logger = logging.getLogger("::EVAL:: MonitorJobWorkflow")

        # Parse monitoring request
        try:
            request_data = json.loads(monitor_request)
            job_id = request_data["job_id"]
            _parent_workflow_id = request_data["parent_workflow_id"]
            poll_interval = request_data.get("poll_interval", 30)
            attempt = request_data.get("attempt", 1)  # Track current attempt
        except Exception as e:
            logger.error(f"Error parsing monitor request: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

        logger.debug(f"Monitoring job {job_id}, attempt {attempt}")

        # Monitor job once per workflow execution
        monitor_result = yield ctx.call_activity(
            EvaluationWorkflow.monitor_eval_job_simple,
            input=json.dumps(request_data),
        )

        # Handle monitoring failure
        if not monitor_result.get("success"):
            logger.warning(f"Monitoring attempt {attempt} failed, will retry")

            # Continue with next attempt using continue_as_new to reset timer history
            request_data["attempt"] = attempt + 1
            yield ctx.create_timer(fire_at=ctx.current_utc_datetime + timedelta(seconds=poll_interval))
            ctx.continue_as_new(json.dumps(request_data))
            return

        # Check job status
        job_status = monitor_result.get("job_status", {})
        status = job_status.get("status", "unknown")

        # Job completed - handle results
        if status in ["succeeded", "failed", "not_found"]:
            logger.info(f"Job {job_id} completed with status: {status} after {attempt} attempts")

            # Extract results if succeeded
            extraction_result = None
            if status == "succeeded":
                # Get model name from notification data or use default
                notification_data = request_data.get("notification_data", {})
                model_name = notification_data.get("model_name", "unknown-model")

                extraction_request = {
                    "job_id": job_id,
                    "evaluation_id": notification_data.get("evaluation_id"),  # Original UUID
                    "model_name": model_name,
                    "kubeconfig": request_data.get("kubeconfig"),
                    "namespace": request_data.get("namespace", "budeval"),
                    "experiment_id": notification_data.get("experiment_id"),
                }

                extraction_result = yield ctx.call_activity(
                    EvaluationWorkflow.extract_results_simple,
                    input=json.dumps(extraction_request),
                )

            return {
                "status": "completed",
                "job_status": status,
                "job_id": job_id,
                "attempts": attempt,
                "job_details": job_status,
                "extraction_summary": {
                    "success": extraction_result.get("success", False),
                    "overall_accuracy": extraction_result.get("overall_accuracy", 0.0),
                    "total_datasets": extraction_result.get("total_datasets", 0),
                    "total_examples": extraction_result.get("total_examples", 0),
                    "dataset_accuracies": extraction_result.get("dataset_accuracies", {}),
                    "model_name": extraction_result.get("model_name", ""),
                    "message": extraction_result.get("message", ""),
                }
                if extraction_result
                else None,
            }

        # Job still running - continue monitoring indefinitely
        logger.debug(f"Job {job_id} still running, will check again in {poll_interval} seconds")

        # Continue monitoring with next attempt using continue_as_new
        # This prevents replay storm by resetting workflow history
        request_data["attempt"] = attempt + 1
        yield ctx.create_timer(fire_at=ctx.current_utc_datetime + timedelta(seconds=poll_interval))
        ctx.continue_as_new(json.dumps(request_data))
        return

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
                message="Error creating engine configuration",
                code=HTTPStatus.INTERNAL_SERVER_ERROR.value,
            )
            # Manually construct error response to ensure code field is included
            return {
                "object": "error",
                "code": HTTPStatus.INTERNAL_SERVER_ERROR.value,
                "message": response.message,
            }

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
            # Handle async operations with proper event loop management
            try:
                asyncio.get_running_loop()
                # If we're in an existing loop, we need to run in a new thread
                import concurrent.futures

                def run_in_new_loop():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        # Clear any thread-local storage to force new instances
                        import threading

                        from budeval.evals.storage.factory import (
                            _clickhouse_storage_by_thread,
                        )

                        thread_id = threading.get_ident()
                        if thread_id in _clickhouse_storage_by_thread:
                            logger.debug(f"Clearing existing ClickHouse storage for thread {thread_id}")
                            del _clickhouse_storage_by_thread[thread_id]

                        return new_loop.run_until_complete(
                            EvaluationOpsService.deploy_eval_job_with_transformation(
                                payload,
                                transformed_data,
                                str(task_id),
                                workflow_id,
                            )
                        )
                    finally:
                        new_loop.close()

                # Run in a separate thread with its own event loop
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(run_in_new_loop)
                    job_details = future.result()
            except RuntimeError:
                # No loop running, safe to use asyncio.run()
                job_details = asyncio.run(
                    EvaluationOpsService.deploy_eval_job_with_transformation(
                        payload, transformed_data, str(task_id), workflow_id
                    )
                )

            response = SuccessResponse(
                code=HTTPStatus.OK.value,
                message="Evaluation job deployed successfully",
                param=dict(job_details),
            )

            # Create initial job record in ClickHouse with status=running
            try:
                from budeval.evals.storage.factory import (
                    get_storage_adapter,
                    initialize_storage,
                )

                storage = get_storage_adapter()

                async def _init_and_create():
                    await initialize_storage(storage)
                    # Build initial record fields
                    job_id = job_details.get("job_id")
                    evaluation_id = str(evaluate_model_request_json.uuid)  # Original evaluation request UUID
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
                            evaluation_id=evaluation_id,
                            experiment_id=experiment_id,
                            model_name=model_name,
                            engine=engine,
                            status="running",
                        )

                # Check if there's already an event loop running
                try:
                    asyncio.get_running_loop()
                    # If we're in an existing loop, we need to handle this differently
                    # For Dapr workflows, we should defer this to a background task
                    logger.warning("Event loop already running, skipping initial ClickHouse record creation")
                except RuntimeError:
                    # No loop running, safe to use asyncio.run()
                    asyncio.run(_init_and_create())
            except Exception as ch_e:
                logger.warning(f"Failed to create initial ClickHouse job record: {ch_e}")
        except Exception as e:
            logger.error(f"Error deploying evaluation job: {e}", exc_info=True)
            response = ErrorResponse(
                message="Error deploying evaluation job",
                code=HTTPStatus.INTERNAL_SERVER_ERROR.value,
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
            # Handle async operations with proper event loop management
            try:
                asyncio.get_running_loop()
                # If we're in an existing loop, we need to run in a new thread
                import concurrent.futures

                def run_in_new_loop():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        # Clear any thread-local storage to force new instances
                        import threading

                        from budeval.evals.storage.factory import (
                            _clickhouse_storage_by_thread,
                        )

                        thread_id = threading.get_ident()
                        if thread_id in _clickhouse_storage_by_thread:
                            logger.debug(f"Clearing existing ClickHouse storage for thread {thread_id}")
                            del _clickhouse_storage_by_thread[thread_id]

                        return new_loop.run_until_complete(
                            EvaluationOpsService.verify_cluster_connection(
                                verify_cluster_connection_request_json,
                                task_id,
                                workflow_id,
                            )
                        )
                    finally:
                        new_loop.close()

                # Run in a separate thread with its own event loop
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(run_in_new_loop)
                    cluster_verified = future.result()
            except RuntimeError:
                # No loop running, safe to use asyncio.run()
                cluster_verified = asyncio.run(
                    EvaluationOpsService.verify_cluster_connection(
                        verify_cluster_connection_request_json,
                        task_id,
                        workflow_id,
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
                    code=HTTPStatus.BAD_REQUEST.value,
                    message="Cluster connection verification failed",
                ).model_dump(mode="json")
        except Exception as e:
            error_msg = (
                f"Error verifying cluster connection for workflow_id: {workflow_id} and task_id: {task_id}, error: {e}"
            )
            logger.error(error_msg)
            return ErrorResponse(
                message="Cluster connection verification failed",
                code=HTTPStatus.BAD_REQUEST.value,
            ).model_dump(mode="json")  # type: ignore # noqa

    @dapr_workflows.register_workflow  # type: ignore [reportUnknownReturnType,reportArgumentType] # noqa
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

        try:
            evaluate_model_request_json = StartEvaluationRequest.model_validate_json(evaluate_model_request)
        except Exception as e:
            logger.error(f"Error parsing cluster create request: {e}", exc_info=True)
            return

        update_workflow_data_in_statestore(
            instance_id,
            evaluate_model_request_json.model_dump(mode="json"),
        )

        # Notifications
        # Set up notification
        workflow_name = "evaluate_model"

        # Notification Request
        notification_request = NotificationRequest.from_cloud_event(
            cloud_event=evaluate_model_request_json,
            name=workflow_name,
            workflow_id=instance_id,
        )

        notification_req = notification_request.model_copy(deep=True)

        notification_req = notification_request.model_copy(deep=True)
        notification_req.payload.event = "evaluate_model_status"
        notification_req.payload.content = NotificationContent(
            title="Evaluation Started",
            message="Evaluation Started",
            status=WorkflowStatus.STARTED,
        )

        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=evaluate_model_request_json.source_topic,
            target_name=evaluate_model_request_json.source,
        )

        # ----
        #
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

        # Starting The Notification

        notification_req.payload.event = "verify_cluster_connection"
        notification_req.payload.content = NotificationContent(
            title="Starting Cluster Connectivity Check",
            message="Starting Cluster Connectivity Check",
            status=WorkflowStatus.RUNNING,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=evaluate_model_request_json.source_topic,
            target_name=evaluate_model_request_json.source,
        )

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
            message=f"{29}",
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

        # Notification For Engine Configuration Creation
        notification_req.payload.event = "preparing_eval_engine"
        notification_req.payload.content = NotificationContent(
            title="Engine Configuration Creation",
            message="Engine Configuration Creation Started",
            status=WorkflowStatus.RUNNING,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=evaluate_model_request_json.source_topic,
            target_name=evaluate_model_request_json.source,
        )

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

        # notify activity ETA
        notification_req.payload.event = "eta"
        notification_req.payload.content = NotificationContent(
            title="Estimated time to completion",
            message=f"{27}",
            status=WorkflowStatus.RUNNING,
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

        # Notification For  Deploy Job
        notification_req.payload.event = "deploy_eval_job"
        notification_req.payload.content = NotificationContent(
            title="Deploying Evaluation Job",
            message="Deploying Evaluation Job",
            status=WorkflowStatus.RUNNING,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=evaluate_model_request_json.source_topic,
            target_name=evaluate_model_request_json.source,
        )

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

        # Monitor Evaluation Job Progress
        logger.info("Starting job monitoring")

        # Update Information To State Store

        # # Extract job details from deployment result
        job_details = deploy_eval_job_result.get("param", {})
        job_id = job_details.get("job_id")

        # Update the job id to state store
        update_workflow_data_in_statestore(instance_id, {"job_id": job_id})

        # Notification For Job Monitoring
        notification_req.payload.event = "monitor_eval_job_progress"
        notification_req.payload.content = NotificationContent(
            title="Waiting for evaluation to complete",
            message=f"Waiting for evaluation to complete - {job_id}",
            status=WorkflowStatus.RUNNING,
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
            message=f"{23}",
            status=WorkflowStatus.RUNNING,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=evaluate_model_request_json.source_topic,
            target_name=evaluate_model_request_json.source,
        )

        # Start Monitoring Child Workflow
        monitor_workflow_request = {
            "job_id": job_id,
            "parent_workflow_id": instance_id,
            "kubeconfig": evaluate_model_request_json.kubeconfig,
            "namespace": StorageConfig.get_current_namespace(),
            "poll_interval": 30,
            "notification_data": {
                "instance_id": instance_id,
                "source_topic": evaluate_model_request_json.source_topic,
                "source": evaluate_model_request_json.source,
                "model_name": evaluate_model_request_json.eval_model_info.model_name,
                "evaluation_id": str(evaluate_model_request_json.uuid),
                "experiment_id": str(evaluate_model_request_json.experiment_id)
                if evaluate_model_request_json.experiment_id
                else None,
            },
        }

        _monitoring_result = yield ctx.call_child_workflow(
            workflow=EvaluationWorkflow.monitor_job_workflow,
            input=json.dumps(monitor_workflow_request),
            instance_id=f"{instance_id}_monitor_{job_id}",
        )

        # Check monitoring result status (THIS IS MISSING IN CURRENT CODE!)
        # if _monitoring_result.get("status") == "completed":
        #     job_status = _monitoring_result.get("job_status")

        #     if job_status == "succeeded":
        #         # Success notification
        #         notification_req.payload.event = "monitor_eval_job_progress"
        #         notification_req.payload.content = NotificationContent(
        #             title="Evaluation Completed Successfully",
        #             message=f"Job {job_id} completed successfully",
        #             status=WorkflowStatus.COMPLETED,
        #         )

        #         # Check if extraction was successful using summary
        #         extraction_summary = _monitoring_result.get("extraction_summary", {})
        #         if extraction_summary and extraction_summary.get("success"):
        #             accuracy = extraction_summary.get("overall_accuracy", 0.0)
        #             datasets = extraction_summary.get("total_datasets", 0)
        #             notification_req.payload.content.message += (
        #                 f" - Results extracted: {datasets} datasets, {accuracy:.2f}% accuracy"
        #             )

        #     elif job_status == "failed":
        #         # Failure notification
        #         notification_req.payload.event = "monitor_eval_job_progress"
        #         notification_req.payload.content = NotificationContent(
        #             title="Evaluation Failed",
        #             message=f"Job {job_id} failed during execution",
        #             status=WorkflowStatus.FAILED,
        #             primary_action="retry",
        #         )

        # elif _monitoring_result.get("status") == "timeout":
        #     # Timeout notification
        #     notification_req.payload.event = "monitor_eval_job_progress"
        #     notification_req.payload.content = NotificationContent(
        #         title="Evaluation Timeout",
        #         message=f"Job {job_id} monitoring timed out after {_monitoring_result.get('attempts')} attempts",
        #         status=WorkflowStatus.FAILED,
        #         primary_action="retry",
        #     )

        # elif _monitoring_result.get("status") == "error":
        #     # Error notification
        #     notification_req.payload.event = "monitor_eval_job_progress"
        #     notification_req.payload.content = NotificationContent(
        #         title="Monitoring Error",
        #         message=f"Error monitoring job {job_id}: {_monitoring_result.get('message')}",
        #         status=WorkflowStatus.FAILED,
        #         primary_action="retry",
        #     )

        notification_req.payload.event = "monitor_eval_job_progress"
        notification_req.payload.content = NotificationContent(
            title="Monitoring Completed",
            message="Monitoring Completed",
            status=WorkflowStatus.COMPLETED,
        )

        # Publish the appropriate monitoring result notification
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=evaluate_model_request_json.source_topic,
            target_name=evaluate_model_request_json.source,
        )

        # Final workflow completion notification
        # notification_req.payload.event = "evaluate_model_status"

        # Set final status based on monitoring result
        # final_status = WorkflowStatus.COMPLETED
        # final_message = "Model Evaluation Completed Successfully"

        # if _monitoring_result.get("status") != "completed" or _monitoring_result.get("job_status") != "succeeded":
        #     final_status = WorkflowStatus.FAILED
        #     final_message = f"Model Evaluation Failed - {_monitoring_result.get('status', 'unknown')}"

        # notification_req.payload.content = NotificationContent(
        #     title=final_message,
        #     message=final_message,
        #     status=final_status,
        # )
        # dapr_workflows.publish_notification(
        #     workflow_id=instance_id,
        #     notification=notification_req,
        #     target_topic_name=evaluate_model_request_json.source_topic,
        #     target_name=evaluate_model_request_json.source,
        # )

        # Result Notification - Always send results regardless of status
        extraction_summary = (
            _monitoring_result.get("extraction_summary", {}) if _monitoring_result.get("status") == "completed" else {}
        )

        # Debug log to verify extraction_summary contents
        logger.debug(f"Monitoring result status: {_monitoring_result.get('status')}")
        logger.debug(f"Extraction summary received: {json.dumps(extraction_summary, default=str)}")

        # workflow_status = check_workflow_status_in_statestore(instance_id)
        # if workflow_status:
        #     logger.info(f"Workflow status: {workflow_status}")
        #     return workflow_status

        notification_req.payload.event = "results"
        notification_req.payload.content = NotificationContent(
            title="Evaluation Results",
            message=extraction_summary.get("message", "Evaluation completed"),
            status=WorkflowStatus.COMPLETED,
            result={
                "job_id": job_id,
                "status": _monitoring_result.get("job_status", "unknown"),
                "storage": "clickhouse",
                "model_name": extraction_summary.get("model_name", "unknown"),
                "summary": {
                    "overall_accuracy": extraction_summary.get("overall_accuracy", 0.0),
                    "total_datasets": extraction_summary.get("total_datasets", 0),
                    "total_examples": extraction_summary.get("total_examples", 0),
                    "dataset_results": extraction_summary.get("dataset_accuracies", {}),
                }
                if extraction_summary
                else {},
                "retrieval_info": f"Use job_id '{job_id}' to retrieve full results from ClickHouse",
            },
        )

        # Log the notification content in a readable JSON format for debugging
        logger.debug(
            f"Sending evaluation results notification: {notification_req.payload.content.model_dump_json(indent=2)}"
        )
        workflow_status = check_workflow_status_in_statestore(instance_id)
        if workflow_status:
            return
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=evaluate_model_request_json.source_topic,
            target_name=evaluate_model_request_json.source,
        )

        notification_req.payload.event = "evaluate_model_status"
        notification_req.payload.content = NotificationContent(
            title="Evaluation Completed",
            message="Evaluation Completed",
            status=WorkflowStatus.COMPLETED,
        )

        # Publish the appropriate monitoring result notification
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=evaluate_model_request_json.source_topic,
            target_name=evaluate_model_request_json.source,
        )

        # Return workflow result to prevent Dapr from marking it as FAILED
        return {
            "workflow_id": instance_id,
            "status": "completed",
            "job_id": job_id,
        }

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
                message="Failed to schedule workflow",
                code=HTTPStatus.INTERNAL_SERVER_ERROR.value,
            )
        except Exception as e:
            logger.error(f"Error scheduling workflow: {e}", exc_info=True)
            return ErrorResponse(
                message=f"Error scheduling workflow: {e}",
                code=HTTPStatus.INTERNAL_SERVER_ERROR.value,
            )
