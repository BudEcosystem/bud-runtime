import json
import uuid
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
from budeval.commons.utils import (
    update_workflow_data_in_statestore,
)
from budeval.engines.opencompass.transformer import (
    OpencompassTransformer,
)

from .ansible_orchestrator import AnsibleOrchestrator
from .job_monitor import monitor_job_workflow
from .schema import EvaluationRequest


logger = logging.getLogger(__name__)

dapr_workflows = DaprWorkflow()


class EvaluationWorkflow:
    @dapr_workflows.register_workflow  # type: ignore [reportUnknownReturnType,reportArgumentType] # noqa
    @staticmethod
    def evaluate_model(ctx: wf.DaprWorkflowContext, evaluate_model_request: str):
        """Evaluate a model with the given name."""
        logger = logging.getLogger("::EVAL:: EvaluateModelWorkflow")
        logger.debug(f"Evaluating model {evaluate_model_request}")

        # Workflow ID
        instance_id = str(ctx.instance_id)

        try:
            evaluate_model_request_json = EvaluationRequest.model_validate_json(evaluate_model_request)
        except Exception as e:
            logger.error(f"Error parsing cluster create request: {e}", exc_info=True)
            return

        # Update the data in db
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

        ## ==================== Notification Block ====================
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
        ## ==================== Notification Block ====================

        # Set initial ETA
        notification_req.payload.event = "eta"
        eta_minutes = 3 * 60
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

        # ==================== NOTIFICATION - Cluster Connectivity  ====================
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

        # ====================  Cluster Connectivity  ====================
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
            message=f"{eta_minutes - 1}",
            status=WorkflowStatus.RUNNING,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=evaluate_model_request_json.source_topic,
            target_name=evaluate_model_request_json.source,
        )

        # ==================== END Cluster Connectivity  ====================

        # ====================  Engine Configuration  ====================
        ## ==================== NOTIFICATION  ====================
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

        transformed_data = yield ctx.call_activity(
            EvaluationWorkflow.create_engine_config,
            input=evaluate_model_request_json.model_dump_json(),
        )

        logger.debug(f"Engine Configuration Creation Result Code: {transformed_data.get('code')}")

        result_code = transformed_data.get("code", HTTPStatus.OK.value)
        if not (200 <= result_code < 300):
            logger.error(f"Engine Configuration Creation Failed: {transformed_data.get('message')}")
            # notify that config creation failed
            notification_req.payload.event = "preparing_eval_engine"
            notification_req.payload.content = NotificationContent(
                title="Configuration creation failed",
                message=transformed_data["message"],
                status=WorkflowStatus.FAILED,
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=evaluate_model_request_json.source_topic,
                target_name=evaluate_model_request_json.source,
            )

            return

        transformed_param = transformed_data.get("param", {}).get("transformed_data", {})
        logger.info(f"Transformed Data: {transformed_param}")

        # Transformation Success
        notification_req.payload.event = "preparing_eval_engine"
        notification_req.payload.content = NotificationContent(
            title="Configuration created successfully",
            message="Configuration created for the model",
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
            message=f"{eta_minutes - 2}",
            status=WorkflowStatus.RUNNING,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=evaluate_model_request_json.source_topic,
            target_name=evaluate_model_request_json.source,
        )

        logger.debug(f" preparing_eval_engine completed with records {transformed_data}")

        # ====================  End Engine Configuration  ====================
        #
        # ====================  Deploy Each Job  ====================
        notification_req.payload.event = "deploy_eval_job"
        notification_req.payload.content = NotificationContent(
            title="Deploying Evaluation Jobs",
            message="Deploying Evaluation Jobs",
            status=WorkflowStatus.RUNNING,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=evaluate_model_request_json.source_topic,
            target_name=evaluate_model_request_json.source,
        )

        # Start The Activity
        deploy_eval_job_result = yield ctx.call_activity(
            EvaluationWorkflow.deploy_eval_job_v2,
            input=json.dumps(transformed_param),
        )

        result_code = deploy_eval_job_result.get("code", HTTPStatus.OK.value)
        if not (200 <= result_code < 300):
            logger.error(f"Deploy Evaluation Job Failed: {deploy_eval_job_result.get('message')}")
            # notify that config creation failed
            notification_req.payload.event = "deploy_eval_job"
            notification_req.payload.content = NotificationContent(
                title="Deploy evaluation job failed",
                message=deploy_eval_job_result["message"],
                status=WorkflowStatus.FAILED,
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=evaluate_model_request_json.source_topic,
                target_name=evaluate_model_request_json.source,
            )

            return

        logger.debug(f"Deploy Evaluation Job: {deploy_eval_job_result}")
        # Notify that all jobs are deployed
        notification_req.payload.event = "deploy_eval_job"
        notification_req.payload.content = NotificationContent(
            title="All evaluation jobs deployed",
            message="All evaluation jobs deployed successfully",
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
            message=f"{eta_minutes - 3}",
            status=WorkflowStatus.RUNNING,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=evaluate_model_request_json.source_topic,
            target_name=evaluate_model_request_json.source,
        )

        logger.debug("All jobs deployed, starting monitoring step")
        # ====================  End Deploy Each Job   ====================

        # update the state with the run ids
        run_ids = deploy_eval_job_result.get("param", {}).get("job_ids", [])
        update_workflow_data_in_statestore(
            instance_id,
            {"run_ids": run_ids},
        )

        # ====================  Start Monitoring For Each Job   ====================

        # NOTE: Initial static notification removed - now sending real-time progress updates every 30s from monitoring workflow

        from budeval.commons.storage_config import StorageConfig

        monitor_input = {
            "job_ids": run_ids,
            "poll_interval": 30,  # keep it simple
            "max_attempts": 1000,  # ~2h cap
            "kubeconfig": None,  # Will use default kubeconfig resolution
            "namespace": StorageConfig.get_current_namespace(),
            # NEW: Pass notification metadata for child workflow to use
            "workflow_id": instance_id,
            "source_topic": evaluate_model_request_json.source_topic,
            "evaluate_model_request_json_raw": evaluate_model_request_json.model_dump(mode="json"),
            "source": evaluate_model_request_json.source,
        }

        monitoring_result = yield ctx.call_child_workflow(
            workflow=monitor_job_workflow,  # from job_monitor.py
            input=json.dumps(monitor_input),
            instance_id=f"{instance_id}_monitor",
        )

        logger.debug(f"Monitoring result: {monitoring_result}")

        if monitoring_result.get("status") != "completed":
            # Notify that all jobs are failed
            notification_req.payload.event = "monitor_eval_job_progress"
            notification_req.payload.content = NotificationContent(
                title="Job Monitoring Failed",
                message="Some evaluation jobs failed or monitoring timed out",
                status=WorkflowStatus.FAILED,
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=evaluate_model_request_json.source_topic,
                target_name=evaluate_model_request_json.source,
            )

            return

        # Look if all the jobs are failed
        if (
            (not monitoring_result.get("completed_jobs") or len(monitoring_result.get("completed_jobs", [])) == 0)
            and monitoring_result.get("failed_jobs")
            and len(monitoring_result.get("failed_jobs", [])) > 0
        ):
            # All jobs failed - extract error details
            failed_job_ids = monitoring_result.get("failed_jobs", [])
            job_details = monitoring_result.get("job_details", {})

            # Collect error details from all failed jobs
            error_summaries = []
            for job_id in failed_job_ids:
                job_info = job_details.get(job_id, {})
                error_details = job_info.get("error_details", {})

                error_summaries.append(
                    {
                        "job_id": job_id,
                        "category": error_details.get("category", "unknown"),
                        "error_type": error_details.get("error_type", "UnknownError"),
                        "message": error_details.get("actionable_message")
                        or error_details.get("error_message", "Unknown error"),
                        "file": error_details.get("file"),
                        "line": error_details.get("line"),
                    }
                )

            # Build user-friendly error message
            primary_error = error_summaries[0] if error_summaries else None
            if primary_error:
                category_messages = {
                    "dataset_missing": f"Dataset Error: {primary_error['message']}",
                    "out_of_memory": f"Out of Memory: {primary_error['message']}",
                    "gpu_error": f"GPU Error: {primary_error['message']}",
                    "configuration": f"Configuration Error: {primary_error['message']}",
                    "network_error": f"Network Error: {primary_error['message']}",
                }
                user_message = category_messages.get(
                    primary_error["category"], f"Evaluation Failed: {primary_error['message']}"
                )
            else:
                user_message = f"All {len(failed_job_ids)} evaluation job(s) failed"

            notification_req.payload.event = "opencompass_evaluation_failed"
            notification_req.payload.content = NotificationContent(
                title="OpenCompass Evaluation Failed",
                message=user_message,
                status=WorkflowStatus.FAILED,
                result={
                    "evaluation_id": str(evaluate_model_request_json.eval_id),
                    "failed_jobs": len(failed_job_ids),
                    "error_category": primary_error["category"] if primary_error else "unknown",
                    "error_details": error_summaries,
                },
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=evaluate_model_request_json.source_topic,
                target_name=evaluate_model_request_json.source,
            )

            return

        # Notify that all jobs are completed
        notification_req.payload.event = "monitor_eval_job_progress"
        notification_req.payload.content = NotificationContent(
            title="All evaluation jobs completed",
            message="All evaluation jobs completed successfully",
            status=WorkflowStatus.COMPLETED,
        )

        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=evaluate_model_request_json.source_topic,
            target_name=evaluate_model_request_json.source,
        )

        # ETA
        notification_req.payload.event = "eta"
        notification_req.payload.content = NotificationContent(
            title="Estimated time to completion",
            message=f"{(eta_minutes + 2) - eta_minutes}",
            status=WorkflowStatus.RUNNING,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=evaluate_model_request_json.source_topic,
            target_name=evaluate_model_request_json.source,
        )

        extraction_input = {
            "eval_id": str(evaluate_model_request_json.eval_id),  # Convert UUID to string
            "completed_jobs": monitoring_result.get("completed_jobs", []),
            "job_timing_map": monitoring_result.get("job_details", {}),
        }

        extraction_result = yield ctx.call_activity(
            EvaluationWorkflow.extract_eval_results,
            input=json.dumps(extraction_input),
        )

        logger.debug(f"Extraction result: {extraction_result}")

        if extraction_result.get("success"):
            update_workflow_data_in_statestore(
                instance_id,
                {
                    "extraction_results": extraction_result.get("results", []),
                    "extraction_status": "completed",
                },
            )

            # Build results summary for notification
            total_scores = sum(len(r.get("scores", [])) for r in extraction_result.get("results", []))
            results_summary = f"Extracted {total_scores} scores from {len(extraction_result.get('results', []))} runs"

            logger.info(f"Results Summary: {results_summary}")
            logger.info(f"Extraction Results: {extraction_result.get('results', [])}")

            notification_req.payload.event = "results"
            notification_req.payload.content = NotificationContent(
                title="Evaluation Results",
                message="Evaluation completed successfully",
                status=WorkflowStatus.COMPLETED,
                result={
                    "results": extraction_result.get("results", []),
                    "evaluation_id": str(evaluate_model_request_json.eval_id),
                },
            )

            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=evaluate_model_request_json.source_topic,
                target_name=evaluate_model_request_json.source,
            )

            # Final Completion Notification
            notification_req.payload.event = "evaluate_model_status"
            notification_req.payload.content = NotificationContent(
                title="Evaluation Completed Successfully",
                message=results_summary,
                status=WorkflowStatus.COMPLETED,
                metadata={
                    "results": extraction_result.get("results", []),
                    "evaluation_id": str(evaluate_model_request_json.eval_id),
                },  # Include results in notification
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=evaluate_model_request_json.source_topic,
                target_name=evaluate_model_request_json.source,
            )

        else:
            logger.debug("Extraction failed")

            notification_req.payload.event = "evaluate_model_status"
            notification_req.payload.content = NotificationContent(
                title="Result extraction failed",
                message=extraction_result.get("error", "Unknown error"),
                status=WorkflowStatus.FAILED,
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=evaluate_model_request_json.source_topic,
                target_name=evaluate_model_request_json.source,
            )

        # ====================  Result Extraction   ====================

        return {
            "workflow_id": instance_id,
            "status": "completed",
        }

    @dapr_workflows.register_activity  # type: ignore [reportUnknownReturnType,reportArgumentType] # noqa
    @staticmethod
    def extract_eval_results(
        ctx: wf.WorkflowActivityContext,
        extract_request: str,
    ) -> dict:
        """Extract evaluation results from completed jobs.

        Args:
            ctx: Workflow activity context
            extract_request: JSON string with:
                {
                    "eval_id": "...",
                    "completed_jobs": ["job1", "job2", ...],
                    "job_timing_map": {"job1": {"startTime": "...", "completionTime": "..."}, ...}
                }

        Returns:
            {
                "success": bool,
                "results": [...]
            }
        """
        logger = logging.getLogger("::EVAL:: ExtractEvalResults")

        workflow_id = ctx.workflow_id
        request = json.loads(extract_request)

        eval_id = request.get("eval_id")
        completed_jobs = request.get("completed_jobs", [])
        kubeconfig = request.get("kubeconfig")
        job_timing_map = request.get("job_timing_map", {})

        logger.info(f"Extracting results for {len(completed_jobs)} completed jobs")

        try:
            results = AnsibleOrchestrator().extract_job_results(
                eval_id=eval_id,
                run_ids=completed_jobs,
                kubeconfig=kubeconfig,
                job_timing_map=job_timing_map,
            )

            return results

        except Exception as e:
            error_msg = f"Error extracting results for workflow_id: {workflow_id}, error: {e}"
            logger.error(error_msg)
            return {"success": False, "results": [], "error": str(e)}

    @dapr_workflows.register_activity  # type: ignore [reportUnknownReturnType,reportArgumentType] # noqa
    @staticmethod
    def deploy_eval_job_v2(
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

        workflow_id = ctx.workflow_id
        deploy_request_json = json.loads(deploy_request)
        logger.debug(f"Deploying evaluation job with request: {deploy_request_json}")

        logger.debug(f"::workflow_id:: {workflow_id}")

        try:
            response = AnsibleOrchestrator().deploy_evaluation_jobs(deploy_request)

            if response:
                return SuccessResponse(
                    code=HTTPStatus.OK.value,
                    message="Jobs Created Successfully",
                    param={"job_ids": response},
                ).model_dump(mode="json")
            else:
                return ErrorResponse(
                    code=HTTPStatus.BAD_REQUEST.value,
                    message="Job Submission Failed",
                ).model_dump(mode="json")

        except Exception as e:
            error_msg = f"Error verifying cluster connection for workflow_id: {workflow_id} error: {e}"
            logger.error(error_msg)
            return ErrorResponse(
                message="Job Submission Failed",
                code=HTTPStatus.BAD_REQUEST.value,
            ).model_dump(mode="json")  # type: ignore # noqa

    @dapr_workflows.register_activity  # type: ignore [reportUnknownReturnType,reportArgumentType] # noqa
    @staticmethod
    def check_job_status(
        ctx: wf.WorkflowActivityContext,
        check_request: str,
    ) -> dict:
        """Check status of Kubernetes jobs.

        Args:
            check_request: JSON string with {"job_ids": ["job1", "job2"]}

        Returns:
            {
                "jobs": {
                    "job1": {
                        "status": "Running|Succeeded|Failed",
                        "phase": "Pending|Running|Succeeded|Failed",
                        "message": "Error message if failed",
                        "completionTime": "2025-10-17T00:10:00Z"
                    },
                    "job2": {...}
                }
            }
        """
        logger = logging.getLogger("::EVAL:: CheckJobStatus")

        workflow_id = ctx.workflow_id
        request = json.loads(check_request)
        job_ids = request.get("job_ids", [])

        logger.info(f"Checking status for jobs: {job_ids}")

        try:
            job_statuses = AnsibleOrchestrator().check_jobs_status(job_ids)

            return SuccessResponse(
                code=HTTPStatus.OK.value,
                message="Job status retrieved",
                param={"jobs": job_statuses},
            ).model_dump(mode="json")

        except Exception as e:
            error_msg = f"Error checking job status for workflow_id: {workflow_id}, error: {e}"
            logger.error(error_msg)
            return ErrorResponse(
                message="Failed to check job status",
                code=HTTPStatus.INTERNAL_SERVER_ERROR.value,
            ).model_dump(mode="json")

    @dapr_workflows.register_activity  # type: ignore [reportUnknownReturnType,reportArgumentType] # noqa
    @staticmethod
    def extract_job_error(
        ctx: wf.WorkflowActivityContext,
        extract_request: str,
    ) -> dict:
        """Extract error information from a failed job.

        Args:
            ctx (WorkflowActivityContext): The context of the Dapr workflow, providing
                access to workflow instance information.
            extract_request (str): A JSON string containing the job_id and kubeconfig.

        Returns:
            dict: Result containing success status and error_info.
        """
        logger = logging.getLogger("::EVAL:: ExtractJobError")
        request = json.loads(extract_request)
        job_id = request.get("job_id")
        kubeconfig = request.get("kubeconfig")

        try:
            orchestrator = AnsibleOrchestrator()
            error_info = orchestrator.extract_job_error(job_id, kubeconfig)
            return {"success": True, "error_info": error_info}
        except Exception as e:
            logger.error(f"Error extracting error info: {e}", exc_info=True)
            return {"success": False, "error_info": {"category": "unknown", "error_message": str(e)}}

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

        try:
            is_cluster_verified = AnsibleOrchestrator().verify_cluster_connection()

            if is_cluster_verified:
                return SuccessResponse(
                    code=HTTPStatus.OK.value,
                    message="Cluster connection verified successfully",
                    param={"cluster_verified": is_cluster_verified},
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

        try:
            evaluate_model_request_json = EvaluationRequest.model_validate_json(evaluate_model_request)
        except Exception as e:
            logger.error(f"Error parsing cluster create request: {e}", exc_info=True)
            return ErrorResponse(
                message="Invalid request format",
                code=HTTPStatus.BAD_REQUEST.value,
            ).model_dump(mode="json")

        # ====== Here we need to build the config map as well as the cli arguments for opencompas
        try:
            prepared_details = OpencompassTransformer().transform(evaluate_model_request_json)

            logger.info(f"Prepared details: {prepared_details}")

            return SuccessResponse(
                code=HTTPStatus.CREATED.value,
                message="Configuration created successfully",
                param={
                    "transformed_data": prepared_details,
                },
            ).model_dump(mode="json")
        except Exception as e:
            logger.error(f"Error creating engine config: {e}", exc_info=True)
            return ErrorResponse(
                message="Error creating engine configuration",
                code=HTTPStatus.INTERNAL_SERVER_ERROR.value,
            ).model_dump(mode="json")

    async def __call__(
        self, eval_request: EvaluationRequest, workflow_id: str | None = None
    ) -> WorkflowMetadataResponse | ErrorResponse:
        """Evaluate a model with the given name."""
        logger = logging.getLogger("::EVAL:: EvaluateModelCall")

        # Workflow ID
        workflow_id = str(workflow_id or uuid.uuid4())

        logger.debug(f"Evaluating model {eval_request.eval_model_info.model_name} for request {eval_request.eval_id}")
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
                title="Deploying Evaluation Jobs",
                description="Deploy the evaluation job to the cluster",
            ),
            WorkflowStep(
                id="monitor_eval_job_progress",
                title="Monitoring Evaluation Job Progress",
                description="Monitor the progress of the evaluation job",
            ),
        ]

        total_datasets = len(eval_request.eval_datasets)

        eta = 30 * 60 * total_datasets
        # Schedule the workflow
        try:
            response = await dapr_workflows.schedule_workflow(
                workflow_name="evaluate_model",
                workflow_input=eval_request.model_dump_json(),
                workflow_id=workflow_id,
                workflow_steps=workflow_steps,
                eta=eta,
                target_topic_name=eval_request.source_topic,
                target_name=eval_request.source,
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
