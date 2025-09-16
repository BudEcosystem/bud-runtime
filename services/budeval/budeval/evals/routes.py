"""Simplified API routes for evaluation operations."""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from budeval.evals.schemas import JobStatusResponse, LegacyEvaluationRequest
from budeval.evals.services import EvaluationOpsService
from budeval.evals.storage.factory import get_storage_adapter, initialize_storage
from budeval.evals.workflows import EvaluationWorkflow


logger = logging.getLogger(__name__)

# Create router
evals_routes = APIRouter(prefix="/evals", tags=["Evaluations"])

# Also create a router for /evaluations prefix to support both paths
evaluations_routes = APIRouter(prefix="/evaluations", tags=["Evaluations"])


@evals_routes.post("/start")
async def start_evaluation(request: LegacyEvaluationRequest) -> Dict[str, Any]:
    """Start an evaluation job.

    Args:
        request: Legacy evaluation request for backward compatibility

    Returns:
        Dictionary with workflow metadata in standard format
    """
    try:
        # Convert legacy request to new format
        new_request = request.to_new_format()

        workflow = EvaluationWorkflow()
        result = await workflow(new_request)

        # Handle different response types
        from budmicroframe.commons.schemas import ErrorResponse, WorkflowMetadataResponse

        if isinstance(result, WorkflowMetadataResponse):
            # Return the workflow metadata response directly as dict
            return result.to_http_response()
        elif isinstance(result, ErrorResponse):
            raise HTTPException(status_code=result.code, detail=f"Failed to start evaluation: {result.message}")
        else:
            # Fallback for unexpected response types
            logger.warning(f"Unexpected response type: {type(result)}")
            raise HTTPException(status_code=500, detail="Unexpected response from workflow")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting evaluation: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}") from e


@evals_routes.get("/status/{job_id}")
async def get_job_status(
    job_id: str,
    kubeconfig: Optional[str] = Query(None, description="Kubernetes config as JSON string"),
    namespace: Optional[str] = Query(None, description="Kubernetes namespace"),
) -> JobStatusResponse:
    """Get the status of an evaluation job.

    Args:
        job_id: Job identifier
        kubeconfig: Optional Kubernetes configuration
        namespace: Optional Kubernetes namespace

    Returns:
        JobStatusResponse with current status
    """
    try:
        result = await EvaluationOpsService.get_job_status(job_id=job_id, kubeconfig=kubeconfig, namespace=namespace)

        return JobStatusResponse(**result)

    except Exception as e:
        logger.error(f"Error getting job status for {job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get job status: {str(e)}") from e


@evals_routes.delete("/cleanup/{job_id}")
async def cleanup_job(
    job_id: str,
    kubeconfig: Optional[str] = Query(None, description="Kubernetes config as JSON string"),
    namespace: Optional[str] = Query(None, description="Kubernetes namespace"),
) -> Dict[str, Any]:
    """Clean up an evaluation job and its resources.

    Args:
        job_id: Job identifier
        kubeconfig: Optional Kubernetes configuration
        namespace: Optional Kubernetes namespace

    Returns:
        Dictionary with cleanup status
    """
    try:
        result = await EvaluationOpsService.cleanup_job(job_id=job_id, kubeconfig=kubeconfig, namespace=namespace)

        return result

    except Exception as e:
        logger.error(f"Error cleaning up job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cleanup job: {str(e)}") from e


@evals_routes.get("/results/{job_id}")
async def get_evaluation_results(job_id: str) -> Dict[str, Any]:
    """Get complete evaluation results for a job.

    Args:
        job_id: Job identifier

    Returns:
        Dictionary with complete evaluation results
    """
    try:
        storage = get_storage_adapter()
        await initialize_storage(storage)

        results = await storage.get_results(job_id)

        if not results:
            raise HTTPException(status_code=404, detail=f"Results not found for job: {job_id}")

        return results

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting results for {job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get results: {str(e)}") from e


@evals_routes.get("/results/{job_id}/summary")
async def get_evaluation_summary(job_id: str) -> Dict[str, Any]:
    """Get evaluation summary for a job.

    Args:
        job_id: Job identifier

    Returns:
        Dictionary with evaluation summary
    """
    try:
        storage = get_storage_adapter()
        await initialize_storage(storage)

        results = await storage.get_results(job_id)

        if not results:
            raise HTTPException(status_code=404, detail=f"Results not found for job: {job_id}")

        # Extract summary from results
        summary = results.get("summary", {})

        return {
            "job_id": job_id,
            "model_name": summary.get("model_name", "unknown"),
            "overall_accuracy": summary.get("overall_accuracy", 0.0),
            "total_datasets": summary.get("total_datasets", 0),
            "total_examples": summary.get("total_examples", 0),
            "total_correct": summary.get("total_correct", 0),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting summary for {job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get summary: {str(e)}") from e


@evals_routes.get("/results/{job_id}/datasets/{dataset_name}")
async def get_dataset_results(job_id: str, dataset_name: str) -> Dict[str, Any]:
    """Get results for a specific dataset.

    Args:
        job_id: Job identifier
        dataset_name: Dataset name

    Returns:
        Dictionary with dataset-specific results
    """
    try:
        storage = get_storage_adapter()
        await initialize_storage(storage)

        results = await storage.get_results(job_id)

        if not results:
            raise HTTPException(status_code=404, detail=f"Results not found for job: {job_id}")

        # Find the specific dataset
        datasets = results.get("datasets", [])
        dataset_result = next((d for d in datasets if d.get("dataset_name") == dataset_name), None)

        if not dataset_result:
            raise HTTPException(status_code=404, detail=f"Dataset '{dataset_name}' not found in job results")

        return dataset_result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting dataset results for {job_id}/{dataset_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get dataset results: {str(e)}") from e


@evals_routes.get("/results")
async def list_evaluation_results() -> Dict[str, Any]:
    """List all available evaluation results.

    Returns:
        Dictionary with list of job IDs and metadata
    """
    try:
        storage = get_storage_adapter()
        await initialize_storage(storage)

        job_ids = await storage.list_results()

        # Get basic metadata for each job
        results_list = []
        for job_id in job_ids:
            try:
                # Try to get basic info from storage
                if hasattr(storage, "get_metadata"):
                    metadata = await storage.get_metadata(job_id)
                    if metadata:
                        results_list.append({"job_id": job_id, **metadata})
                        continue

                # Fallback: just the job ID
                results_list.append({"job_id": job_id})

            except Exception as e:
                logger.warning(f"Failed to get metadata for {job_id}: {e}")
                results_list.append({"job_id": job_id})

        return {"total_jobs": len(job_ids), "jobs": results_list}

    except Exception as e:
        logger.error(f"Error listing evaluation results: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list results: {str(e)}") from e


@evals_routes.delete("/results/{job_id}")
async def delete_evaluation_results(job_id: str) -> Dict[str, Any]:
    """Delete evaluation results for a job.

    Args:
        job_id: Job identifier

    Returns:
        Dictionary with deletion status
    """
    try:
        storage = get_storage_adapter()
        await initialize_storage(storage)

        # Check if results exist
        exists = await storage.exists(job_id)
        if not exists:
            raise HTTPException(status_code=404, detail=f"Results not found for job: {job_id}")

        # Delete results
        success = await storage.delete_results(job_id)

        if success:
            return {"job_id": job_id, "deleted": True, "message": "Results deleted successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to delete results")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting results for {job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete results: {str(e)}") from e


# Health check endpoint
@evals_routes.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint for the evaluation service.

    Returns:
        Dictionary with service health status
    """
    try:
        # Check storage connectivity
        storage = get_storage_adapter()
        await initialize_storage(storage)

        storage_health = {"status": "unknown"}

        if hasattr(storage, "health_check"):
            storage_healthy = await storage.health_check()
            storage_health = {
                "status": "healthy" if storage_healthy else "unhealthy",
                "backend": storage.__class__.__name__,
            }

        return {
            "service": "budeval",
            "status": "healthy",
            "storage": storage_health,
            "timestamp": "2024-01-15T00:00:00Z",  # Would use real timestamp
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "service": "budeval",
            "status": "unhealthy",
            "error": str(e),
            "timestamp": "2024-01-15T00:00:00Z",  # Would use real timestamp
        }
