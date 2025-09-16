"""Simplified evaluation services focused on core functionality."""

import logging
from typing import Any, Dict, Optional

from budeval.commons.config import app_settings
from budeval.evals.kubernetes import KubernetesManager
from budeval.evals.schemas import EvaluationRequest, JobStatus, JobStatusResponse
from budeval.evals.storage.factory import get_storage_adapter, initialize_storage


logger = logging.getLogger(__name__)


class EvaluationService:
    """Core evaluation service - simplified and focused."""

    def __init__(self):
        """Initialize the evaluation service."""
        self.k8s_manager = KubernetesManager()

    async def start_evaluation(self, request: EvaluationRequest) -> Dict[str, Any]:
        """Start an evaluation job.

        Args:
            request: Evaluation request with model and dataset configuration

        Returns:
            Dictionary with job status and details
        """
        job_id = f"eval-{request.eval_request_id}"

        try:
            # 1. Verify cluster connectivity
            logger.info(f"Verifying cluster connectivity for namespace: {request.namespace}")

            cluster_ok = self.k8s_manager.verify_cluster(namespace=request.namespace, kubeconfig=request.kubeconfig)

            if not cluster_ok:
                return {"job_id": job_id, "status": "failed", "error": "Cluster verification failed"}

            # 2. Deploy evaluation job
            logger.info(f"Deploying evaluation job: {job_id}")

            deployment_result = self.k8s_manager.deploy_evaluation_job(request)

            if deployment_result.get("status") == "deployed":
                # 3. Create initial job record in storage
                await self._create_initial_job_record(request, job_id)

                return {
                    "job_id": job_id,
                    "status": "started",
                    "message": "Evaluation job deployed successfully",
                    "namespace": request.namespace,
                }
            else:
                return {
                    "job_id": job_id,
                    "status": "failed",
                    "error": deployment_result.get("error", "Deployment failed"),
                }

        except Exception as e:
            logger.error(f"Error starting evaluation {job_id}: {e}")
            return {"job_id": job_id, "status": "error", "error": str(e)}

    async def get_job_status(
        self, job_id: str, namespace: Optional[str] = None, kubeconfig: Optional[str] = None
    ) -> JobStatusResponse:
        """Get the status of an evaluation job.

        Args:
            job_id: Job identifier
            namespace: Kubernetes namespace (optional)
            kubeconfig: Kubernetes config (optional)

        Returns:
            JobStatusResponse with current status
        """
        if not namespace:
            namespace = app_settings.get_current_namespace()

        try:
            # Get status from Kubernetes
            k8s_status = self.k8s_manager.get_job_status(job_id=job_id, namespace=namespace, kubeconfig=kubeconfig)

            status_str = k8s_status.get("status", "unknown")
            status = JobStatus(status_str) if status_str in JobStatus.__members__.values() else JobStatus.PENDING

            return JobStatusResponse(
                job_id=job_id,
                status=status,
                message=k8s_status.get("message"),
                # Add timing info if available from k8s details
            )

        except Exception as e:
            logger.error(f"Error getting job status for {job_id}: {e}")
            return JobStatusResponse(
                job_id=job_id, status=JobStatus.FAILED, message=f"Error retrieving status: {str(e)}"
            )

    async def cleanup_job(
        self, job_id: str, namespace: Optional[str] = None, kubeconfig: Optional[str] = None
    ) -> Dict[str, Any]:
        """Clean up an evaluation job.

        Args:
            job_id: Job identifier
            namespace: Kubernetes namespace (optional)
            kubeconfig: Kubernetes config (optional)

        Returns:
            Dictionary with cleanup status
        """
        if not namespace:
            namespace = app_settings.get_current_namespace()

        try:
            success = self.k8s_manager.cleanup_job(job_id=job_id, namespace=namespace, kubeconfig=kubeconfig)

            return {
                "job_id": job_id,
                "cleanup_success": success,
                "message": "Job cleanup completed" if success else "Job cleanup failed",
            }

        except Exception as e:
            logger.error(f"Error cleaning up job {job_id}: {e}")
            return {"job_id": job_id, "cleanup_success": False, "error": str(e)}

    async def extract_and_process_results(
        self,
        job_id: str,
        model_name: str,
        namespace: Optional[str] = None,
        kubeconfig: Optional[str] = None,
        experiment_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Extract results from PVC and process them.

        Args:
            job_id: Job identifier
            model_name: Model name for results
            namespace: Kubernetes namespace (optional)
            kubeconfig: Kubernetes config (optional)
            experiment_id: Associated experiment ID (optional)

        Returns:
            Dictionary with processing results
        """
        if not namespace:
            namespace = app_settings.get_current_namespace()

        try:
            # 1. Extract results from PVC
            logger.info(f"Extracting results for job: {job_id}")

            extraction_result = self.k8s_manager.extract_results(
                job_id=job_id, namespace=namespace, kubeconfig=kubeconfig
            )

            if not extraction_result.get("success"):
                return {
                    "job_id": job_id,
                    "success": False,
                    "error": extraction_result.get("error", "Extraction failed"),
                }

            # 2. Process results and store in ClickHouse
            logger.info(f"Processing results for job: {job_id}")

            from budeval.evals.results_processor import ResultsProcessor

            storage = get_storage_adapter()
            await initialize_storage(storage)

            processor = ResultsProcessor(storage)

            processed_results = await processor.process_opencompass_results(
                extracted_path=extraction_result["local_path"],
                job_id=job_id,
                model_name=model_name,
                experiment_id=experiment_id,
            )

            # 3. Store results
            success = await storage.save_results(job_id, processed_results.model_dump())

            if success:
                return {
                    "job_id": job_id,
                    "success": True,
                    "results_summary": {
                        "overall_accuracy": processed_results.summary.overall_accuracy,
                        "total_datasets": processed_results.summary.total_datasets,
                        "total_examples": processed_results.summary.total_examples,
                    },
                }
            else:
                return {"job_id": job_id, "success": False, "error": "Failed to store results"}

        except Exception as e:
            logger.error(f"Error processing results for {job_id}: {e}")
            return {"job_id": job_id, "success": False, "error": str(e)}

    async def _create_initial_job_record(self, request: EvaluationRequest, job_id: str) -> None:
        """Create initial job record in storage."""
        try:
            storage = get_storage_adapter()
            await initialize_storage(storage)

            # Create initial record with "running" status
            if hasattr(storage, "create_initial_job_record"):
                await storage.create_initial_job_record(
                    job_id=job_id,
                    model_name=request.model.name,
                    engine="opencompass",
                    experiment_id=str(request.experiment_id) if request.experiment_id else None,
                )

        except Exception as e:
            logger.warning(f"Failed to create initial job record for {job_id}: {e}")
            # Don't fail the evaluation start for this


class EvaluationOpsService:
    """Operations service for evaluation management."""

    @classmethod
    async def get_job_status(
        cls, job_id: str, kubeconfig: Optional[str], namespace: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get job status - static method for compatibility."""
        service = EvaluationService()
        result = await service.get_job_status(job_id, namespace, kubeconfig)
        return result.model_dump()

    @classmethod
    async def cleanup_job(
        cls, job_id: str, kubeconfig: Optional[str], namespace: Optional[str] = None
    ) -> Dict[str, Any]:
        """Clean up job - static method for compatibility."""
        service = EvaluationService()
        return await service.cleanup_job(job_id, namespace, kubeconfig)
