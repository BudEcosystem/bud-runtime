"""Simplified Dapr workflow for coordinating BudEval evaluation jobs."""

import asyncio
import json
import logging
from datetime import timedelta
from http import HTTPStatus
from uuid import uuid4

# Import response schemas
from budmicroframe.commons.schemas import (
    ErrorResponse,
    NotificationContent,
    NotificationRequest,
    SuccessResponse,
    WorkflowMetadataResponse,
    WorkflowStatus,
    WorkflowStep,
)

# Import BudDaprWorkflow which extends the base Dapr workflow
from budmicroframe.shared.dapr_workflow import DaprWorkflow

# Correct imports from dapr.ext.workflow
from dapr.ext.workflow import DaprWorkflowContext, RetryPolicy, WorkflowActivityContext

from budeval.commons.config import app_settings
from budeval.evals.schemas import EvaluationRequest
from budeval.evals.services import EvaluationService
from budeval.evals.storage.clickhouse import ClickHouseStorage


logger = logging.getLogger(__name__)

# Initialize Dapr workflow
dapr_workflows = DaprWorkflow()

# Retry policy for activities
retry_policy = RetryPolicy(
    first_retry_interval=timedelta(seconds=10),
    max_number_of_attempts=3,
    backoff_coefficient=2,
    max_retry_interval=timedelta(seconds=60),
    retry_timeout=timedelta(seconds=600),
)


class EvaluationWorkflow:
    """Simplified evaluation workflow orchestration."""

    # Activity: Verify Cluster Connection
    @dapr_workflows.register_activity
    @staticmethod
    def verify_cluster_connection(ctx: WorkflowActivityContext, evaluate_request: str) -> dict:
        """Verify cluster connection activity."""
        logger = logging.getLogger("::EVAL:: VerifyClusterConnection")
        workflow_id = ctx.workflow_id
        task_id = ctx.task_id

        logger.info(f"Verifying cluster for workflow_id: {workflow_id}, task_id: {task_id}")

        try:
            request = EvaluationRequest.model_validate_json(evaluate_request)
            service = EvaluationService()

            # Verify cluster using Kubernetes manager
            verified = service.k8s_manager.verify_cluster(namespace=request.namespace, kubeconfig=request.kubeconfig)

            response = SuccessResponse(
                message="Cluster verified successfully" if verified else "Cluster verification failed",
                param={"verified": verified},
            )

        except Exception as e:
            logger.error(f"Cluster verification failed: {e}")
            response = ErrorResponse(
                message=f"Cluster verification failed: {str(e)}", code=HTTPStatus.BAD_REQUEST.value
            )

        return response.model_dump(mode="json")

    # Activity: Deploy Evaluation Job
    @dapr_workflows.register_activity
    @staticmethod
    def deploy_evaluation_job(ctx: WorkflowActivityContext, evaluate_request: str) -> dict:
        """Deploy OpenCompass evaluation job to Kubernetes."""
        logger = logging.getLogger("::EVAL:: DeployEvaluationJob")
        workflow_id = ctx.workflow_id
        task_id = ctx.task_id

        logger.info(f"Deploying evaluation job for workflow_id: {workflow_id}, task_id: {task_id}")

        try:
            request = EvaluationRequest.model_validate_json(evaluate_request)
            service = EvaluationService()

            # Get the job ID first
            job_id = f"eval-{request.eval_request_id}"

            # Create initial job record in ClickHouse with "running" status
            # This should happen BEFORE deployment to track all jobs
            try:
                storage = ClickHouseStorage()

                async def init_job_record():
                    await storage.initialize()
                    await storage.create_initial_job_record(
                        job_id=job_id,
                        model_name=request.model.name,
                        engine="opencompass",
                        experiment_id=str(request.experiment_id) if request.experiment_id else None,
                    )
                    await storage.shutdown()

                asyncio.run(init_job_record())
                logger.info(f"Created initial ClickHouse record for job: {job_id}")
            except Exception as e:
                logger.warning(f"Failed to create initial ClickHouse record: {e}")
                # Continue even if ClickHouse fails - don't block the deployment

            # Deploy job using Kubernetes manager
            job_result = service.k8s_manager.deploy_evaluation_job(request)

            # Check deployment result
            deployment_success = job_result.get("status") == "deployed" or job_result.get("success", False)

            response = SuccessResponse(
                message="Evaluation job deployment initiated",
                param={"job_id": job_id, "success": deployment_success, "status": job_result.get("status", "unknown")},
            )

        except Exception as e:
            logger.error(f"Job deployment failed: {e}")
            response = ErrorResponse(
                message=f"Job deployment failed: {str(e)}", code=HTTPStatus.INTERNAL_SERVER_ERROR.value
            )

        return response.model_dump(mode="json")

    # Activity: Monitor Job Progress
    @dapr_workflows.register_activity
    @staticmethod
    def monitor_job_progress(ctx: WorkflowActivityContext, monitor_request: str) -> dict:
        """Monitor evaluation job progress."""
        logger = logging.getLogger("::EVAL:: MonitorJobProgress")

        try:
            monitor_data = json.loads(monitor_request)
            job_id = monitor_data["job_id"]
            namespace = monitor_data.get("namespace", app_settings.namespace)
            kubeconfig = monitor_data.get("kubeconfig")

            service = EvaluationService()

            # Get job status using Kubernetes manager
            status = service.k8s_manager.get_job_status(job_id=job_id, namespace=namespace, kubeconfig=kubeconfig)

            # Determine if job is complete
            job_status = status.get("status", "unknown")
            completed = job_status in ["completed", "failed"]

            response = {
                "job_id": job_id,
                "status": job_status,
                "completed": completed,
                "details": status.get("details", {}),
            }

        except Exception as e:
            logger.error(f"Job monitoring failed: {e}")
            response = {
                "job_id": monitor_data.get("job_id", "unknown"),
                "status": "error",
                "completed": True,
                "error": str(e),
            }

        return response

    # Activity: Extract Results
    @dapr_workflows.register_activity
    @staticmethod
    def extract_results(ctx: WorkflowActivityContext, extract_request: str) -> dict:
        """Extract and process evaluation results."""
        logger = logging.getLogger("::EVAL:: ExtractResults")

        try:
            extract_data = json.loads(extract_request)
            job_id = extract_data["job_id"]
            model_name = extract_data["model_name"]
            namespace = extract_data.get("namespace", app_settings.namespace)
            kubeconfig = extract_data.get("kubeconfig")
            experiment_id = extract_data.get("experiment_id")

            service = EvaluationService()

            async def process_results():
                # Extract results from PVC
                extraction_result = service.k8s_manager.extract_results(
                    job_id=job_id, namespace=namespace, kubeconfig=kubeconfig
                )

                if not extraction_result.get("success"):
                    return {"success": False, "error": "Failed to extract results from PVC"}

                # Process results
                from budeval.evals.results_processor import ResultsProcessor

                storage = ClickHouseStorage()
                await storage.initialize()

                processor = ResultsProcessor(storage)
                results = await processor.process_opencompass_results(
                    extracted_path=extraction_result["local_path"],
                    job_id=job_id,
                    model_name=model_name,
                    experiment_id=experiment_id,
                )

                # Save to storage
                await storage.save_results(job_id, results.model_dump())
                await storage.close()

                return {
                    "success": True,
                    "job_id": job_id,
                    "overall_accuracy": results.summary.overall_accuracy,
                    "total_datasets": results.summary.total_datasets,
                    "extraction_path": results.extraction_path,
                }

            response = asyncio.run(process_results())

        except Exception as e:
            logger.error(f"Results extraction failed: {e}")
            response = {"success": False, "job_id": extract_data.get("job_id", "unknown"), "error": str(e)}

        return response

    # Main Workflow
    @dapr_workflows.register_workflow
    @staticmethod
    def evaluate_model(ctx: DaprWorkflowContext, evaluate_request: str):
        """Run the evaluation workflow for OpenCompass-powered jobs."""
        logger = logging.getLogger("::EVAL:: EvaluateModel")
        instance_id = str(ctx.instance_id)

        # Parse request to check if this is monitoring phase
        request_dict = json.loads(evaluate_request)
        phase = request_dict.get("phase", "deployment")

        logger.info(f"Starting evaluation workflow: {instance_id}, phase: {phase}")

        # Handle monitoring phase with continue_as_new pattern
        if phase == "monitoring":
            logger.info("Entering monitoring phase with continue_as_new pattern")
            yield from EvaluationWorkflow._handle_monitoring_phase(ctx, evaluate_request)
            return

        try:
            # Parse request for deployment phase
            request = EvaluationRequest.model_validate_json(evaluate_request)
            job_id = f"eval-{request.eval_request_id}"

            # Set up notifications
            workflow_name = "evaluate_model"
            notification_request = NotificationRequest.from_cloud_event(
                cloud_event=request, name=workflow_name, workflow_id=instance_id
            )
            notification_req = notification_request.model_copy(deep=True)

            # Publish initial notification
            notification_req.payload.event = "workflow_started"
            notification_req.payload.content = NotificationContent(
                title="Model evaluation process initiated",
                message=f"Starting evaluation for model {request.model.name}",
                status=WorkflowStatus.STARTED,
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=request.source_topic,
                target_name=request.source,
            )

            # Send ETA notification
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
                target_topic_name=request.source_topic,
                target_name=request.source,
            )

            # Step 1: Verify Cluster Connection
            logger.info(f"Step 1: Verifying cluster for {job_id}")
            verify_result = yield ctx.call_activity(
                EvaluationWorkflow.verify_cluster_connection, input=evaluate_request, retry_policy=retry_policy
            )

            if verify_result.get("code", HTTPStatus.OK.value) != HTTPStatus.OK.value:
                logger.error(f"Cluster verification failed: {verify_result}")
                # Send failure notification
                notification_req.payload.event = "verify_cluster_connection"
                notification_req.payload.content = NotificationContent(
                    title="Cluster verification failed",
                    message=verify_result.get("message", "Cluster verification failed"),
                    status=WorkflowStatus.FAILED,
                    primary_action="retry",
                )
                dapr_workflows.publish_notification(
                    workflow_id=instance_id,
                    notification=notification_req,
                    target_topic_name=request.source_topic,
                    target_name=request.source,
                )
                # Send final results notification
                notification_req.payload.event = "results"
                notification_req.payload.content = NotificationContent(
                    title="Evaluation failed",
                    message=verify_result.get("message", "Cluster verification failed"),
                    status=WorkflowStatus.FAILED,
                    primary_action="retry",
                )
                dapr_workflows.publish_notification(
                    workflow_id=instance_id,
                    notification=notification_req,
                    target_topic_name=request.source_topic,
                    target_name=request.source,
                )
                return {
                    "job_id": job_id,
                    "status": "failed",
                    "step": "cluster_verification",
                    "error": verify_result.get("message", "Cluster verification failed"),
                }

            # Send success notification for cluster verification
            notification_req.payload.event = "verify_cluster_connection"
            notification_req.payload.content = NotificationContent(
                title="Cluster verification successful",
                message="Cluster connection verified successfully",
                status=WorkflowStatus.COMPLETED,
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=request.source_topic,
                target_name=request.source,
            )

            # Step 2: Deploy Evaluation Job
            logger.info(f"Step 2: Deploying job {job_id}")
            deploy_result = yield ctx.call_activity(
                EvaluationWorkflow.deploy_evaluation_job, input=evaluate_request, retry_policy=retry_policy
            )

            if deploy_result.get("code", HTTPStatus.OK.value) != HTTPStatus.OK.value:
                logger.error(f"Job deployment failed: {deploy_result}")
                return {
                    "job_id": job_id,
                    "status": "failed",
                    "step": "job_deployment",
                    "error": deploy_result.get("message", "Job deployment failed"),
                }

            # Get job ID from deployment result
            deployed_job_id = deploy_result.get("param", {}).get("job_id", job_id)

            # Step 3: Transition to Monitoring Phase using continue_as_new
            logger.info(f"Step 3: Transitioning to monitoring phase for job {deployed_job_id}")
            logger.info("Using continue_as_new pattern to prevent workflow history buildup")

            # Prepare monitoring data for continue_as_new
            monitoring_data = {
                **request.model_dump(mode="json"),
                "job_id": deployed_job_id,
                "monitoring_attempt": 0,
                "max_attempts": 360,  # 30 minutes with 5-second intervals
                "phase": "monitoring",
                "job_start_time": ctx.current_utc_datetime.isoformat(),
            }

            logger.info(f"Continuing workflow as monitoring phase for job_id: {deployed_job_id}")
            logger.debug(f"Monitoring data keys: {list(monitoring_data.keys())}")
            logger.debug(f"Job start time recorded: {monitoring_data['job_start_time']}")
            logger.debug(f"Max monitoring attempts: {monitoring_data['max_attempts']}")

            # Continue as new workflow instance for monitoring
            ctx.continue_as_new(json.dumps(monitoring_data))
            return

        except Exception as e:
            logger.error(f"Workflow failed: {e}")
            return {
                "job_id": f"eval-{ctx.instance_id}",
                "status": "error",
                "step": "workflow_execution",
                "error": str(e),
            }

    @staticmethod
    def _handle_monitoring_phase(ctx: DaprWorkflowContext, request_str: str):
        """Handle the monitoring phase using proper Dapr continue_as_new pattern.

        This method uses continue_as_new to prevent workflow history buildup
        during long-running job monitoring, allowing for efficient monitoring
        of jobs that run for extended periods.
        """
        logger = logging.getLogger("::EVAL:: MonitoringPhase")

        logger.info(f"Monitoring phase handler called for workflow instance: {ctx.instance_id}")
        logger.debug(f"Request string length: {len(request_str)} bytes")

        # Parse the monitoring request
        try:
            request_data = json.loads(request_str)
            job_id = request_data["job_id"]
            monitoring_attempt = request_data.get("monitoring_attempt", 0) + 1
            max_attempts = request_data.get("max_attempts", 360)
            instance_id = str(ctx.instance_id)
            job_start_time_str = request_data.get("job_start_time")

            logger.info(f"Monitoring job_id: {job_id}, attempt: {monitoring_attempt}/{max_attempts}")
            logger.debug(f"Job start time: {job_start_time_str}")

            # Reconstruct EvaluationRequest without monitoring fields
            eval_request_data = {
                k: v
                for k, v in request_data.items()
                if k not in ["job_id", "monitoring_attempt", "max_attempts", "phase", "job_start_time"]
            }
            request = EvaluationRequest(**eval_request_data)

            logger.info(f"Monitoring job {job_id}, attempt {monitoring_attempt}/{max_attempts}")
        except Exception as e:
            logger.error(f"Error parsing monitoring request: {e}", exc_info=True)
            return {"status": "error", "error": f"Failed to parse monitoring request: {str(e)}"}

        # Set up notifications
        notification_request = NotificationRequest.from_cloud_event(
            cloud_event=request, name="evaluate_model", workflow_id=instance_id
        )
        notification_req = notification_request.model_copy(deep=True)

        # Check if we've exceeded max attempts
        if monitoring_attempt > max_attempts:
            logger.warning(f"Job {job_id} monitoring timed out after {max_attempts} attempts")

            # Send timeout notification
            notification_req.payload.event = "monitor_eval_job_progress"
            notification_req.payload.content = NotificationContent(
                title="Job monitoring timeout",
                message=f"Job {job_id} monitoring timed out after 30 minutes",
                status=WorkflowStatus.FAILED,
                primary_action="retry",
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=request.source_topic,
                target_name=request.source,
            )

            # Send final results notification
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
                target_topic_name=request.source_topic,
                target_name=request.source,
            )

            return {"status": "timeout", "job_id": job_id}

        # Check job status
        monitor_request = {"job_id": job_id, "namespace": request.namespace, "kubeconfig": request.kubeconfig}

        monitor_result = yield ctx.call_activity(
            EvaluationWorkflow.monitor_job_progress, input=json.dumps(monitor_request), retry_policy=retry_policy
        )

        # Handle monitoring activity failure
        if isinstance(monitor_result, dict) and monitor_result.get("error"):
            logger.warning(f"Monitoring attempt {monitoring_attempt} failed: {monitor_result.get('error')}")
            logger.debug("Will retry monitoring after 5 seconds delay")

            # Wait and continue monitoring
            yield ctx.create_timer(ctx.current_utc_datetime + timedelta(seconds=5))

            request_data["monitoring_attempt"] = monitoring_attempt
            logger.debug("Retrying monitoring with continue_as_new after activity failure")
            ctx.continue_as_new(json.dumps(request_data))
            return

        job_completed = monitor_result.get("completed", False)
        job_status = monitor_result.get("status", "unknown")

        # If job completed, handle results
        if job_completed:
            logger.info(f"Job {job_id} completed with status: {job_status}")

            if job_status == "completed":
                # Job succeeded - extract and process results
                logger.info(f"Job {job_id} succeeded, extracting results")

                extract_request = {
                    "job_id": job_id,
                    "model_name": request.model.name,
                    "namespace": request.namespace,
                    "kubeconfig": request.kubeconfig,
                    "experiment_id": str(request.experiment_id) if request.experiment_id else None,
                }

                extract_result = yield ctx.call_activity(
                    EvaluationWorkflow.extract_results, input=json.dumps(extract_request), retry_policy=retry_policy
                )

                if extract_result.get("success"):
                    # Log the duration for debugging
                    try:
                        from datetime import datetime

                        # Calculate duration for logging
                        start_time = None
                        if job_start_time_str:
                            try:
                                start_time = datetime.fromisoformat(job_start_time_str)
                            except Exception:
                                start_time = None

                        end_time = datetime.utcnow()
                        duration = (end_time - start_time).total_seconds() if start_time else None

                        logger.info(
                            f"Job {job_id} completed - Duration: {duration:.2f} seconds"
                            if duration
                            else f"Job {job_id} completed"
                        )
                    except Exception as e:
                        logger.warning(f"Failed to calculate job duration: {e}")

                    # Send success notification
                    notification_req.payload.event = "monitor_eval_job_progress"
                    notification_req.payload.content = NotificationContent(
                        title="Job completed successfully",
                        message=f"Job {job_id} completed successfully. Accuracy: {extract_result.get('overall_accuracy', 0):.2f}%",
                        status=WorkflowStatus.COMPLETED,
                        result=extract_result,
                    )
                    dapr_workflows.publish_notification(
                        workflow_id=instance_id,
                        notification=notification_req,
                        target_topic_name=request.source_topic,
                        target_name=request.source,
                    )

                    # Send final results notification
                    notification_req.payload.event = "results"
                    notification_req.payload.content = NotificationContent(
                        title="Evaluation results",
                        message="Results are ready",
                        status=WorkflowStatus.COMPLETED,
                        result=extract_result,
                    )
                    dapr_workflows.publish_notification(
                        workflow_id=instance_id,
                        notification=notification_req,
                        target_topic_name=request.source_topic,
                        target_name=request.source,
                    )

                    return {
                        "job_id": job_id,
                        "status": "completed",
                        "overall_accuracy": extract_result.get("overall_accuracy"),
                        "total_datasets": extract_result.get("total_datasets"),
                    }
                else:
                    # Results extraction failed
                    notification_req.payload.event = "monitor_eval_job_progress"
                    notification_req.payload.content = NotificationContent(
                        title="Job completed - Results extraction failed",
                        message=f"Job {job_id} completed but results extraction failed",
                        status=WorkflowStatus.FAILED,
                        primary_action="retry",
                    )
                    dapr_workflows.publish_notification(
                        workflow_id=instance_id,
                        notification=notification_req,
                        target_topic_name=request.source_topic,
                        target_name=request.source,
                    )

                    return {
                        "job_id": job_id,
                        "status": "failed",
                        "error": extract_result.get("error", "Results extraction failed"),
                    }
            else:
                # Job failed
                # Log failure duration for debugging
                try:
                    from datetime import datetime

                    # Calculate duration for logging
                    start_time = None
                    if job_start_time_str:
                        try:
                            start_time = datetime.fromisoformat(job_start_time_str)
                        except Exception:
                            start_time = None

                    end_time = datetime.utcnow()
                    duration = (end_time - start_time).total_seconds() if start_time else None

                    logger.info(
                        f"Job {job_id} failed - Duration: {duration:.2f} seconds"
                        if duration
                        else f"Job {job_id} failed"
                    )
                except Exception as e:
                    logger.warning(f"Failed to calculate job duration: {e}")

                # Send failure notification
                notification_req.payload.event = "monitor_eval_job_progress"
                notification_req.payload.content = NotificationContent(
                    title="Job failed",
                    message=f"Job {job_id} failed with status: {job_status}",
                    status=WorkflowStatus.FAILED,
                    primary_action="retry",
                )
                dapr_workflows.publish_notification(
                    workflow_id=instance_id,
                    notification=notification_req,
                    target_topic_name=request.source_topic,
                    target_name=request.source,
                )

                # Send final results notification
                notification_req.payload.event = "results"
                notification_req.payload.content = NotificationContent(
                    title="Evaluation failed",
                    message=f"Job {job_id} failed",
                    status=WorkflowStatus.FAILED,
                    primary_action="retry",
                )
                dapr_workflows.publish_notification(
                    workflow_id=instance_id,
                    notification=notification_req,
                    target_topic_name=request.source_topic,
                    target_name=request.source,
                )

                return {"job_id": job_id, "status": "failed", "error": f"Job failed with status: {job_status}"}

        # Job still running - send progress notification if needed
        if monitoring_attempt % 10 == 0:  # Every 50 seconds
            notification_req.payload.event = "monitor_eval_job_progress"
            notification_req.payload.content = NotificationContent(
                title="Job monitoring in progress",
                message=f"Job {job_id} is still running. Attempt: {monitoring_attempt}/{max_attempts}",
                status=WorkflowStatus.RUNNING,
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=request.source_topic,
                target_name=request.source,
            )

        # Job still running - set timer and continue monitoring
        logger.debug(f"Job {job_id} still running, waiting 5 seconds before next check")
        yield ctx.create_timer(ctx.current_utc_datetime + timedelta(seconds=5))

        # Continue as new with updated attempt count
        request_data["monitoring_attempt"] = monitoring_attempt
        logger.debug(f"Continuing workflow as new instance with attempt {monitoring_attempt + 1}")
        logger.debug("Using continue_as_new to reset workflow history and prevent memory buildup")
        ctx.continue_as_new(json.dumps(request_data))
        return  # Required return after continue_as_new

    # Entry point
    async def __call__(
        self, request: EvaluationRequest, workflow_id: str | None = None
    ) -> WorkflowMetadataResponse | ErrorResponse:
        """Start an evaluation workflow.

        Args:
            request: Evaluation request
            workflow_id: Optional workflow ID

        Returns:
            Workflow metadata response or error
        """
        logger = logging.getLogger("::EVAL:: EvaluateModelCall")

        workflow_id = str(workflow_id or uuid4())

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

        eta = 60 * 60  # 30 minutes estimate

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

            # Ensure we return a proper response type
            if response is None:
                return ErrorResponse(
                    message="Workflow scheduling returned no response", code=HTTPStatus.INTERNAL_SERVER_ERROR.value
                )

            return response

        except Exception as e:
            logger.error(f"Failed to start workflow: {e}")
            return ErrorResponse(
                message=f"Failed to start evaluation workflow: {str(e)}", code=HTTPStatus.INTERNAL_SERVER_ERROR.value
            )
