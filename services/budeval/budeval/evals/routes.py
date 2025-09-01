#  -----------------------------------------------------------------------------
#  Copyright (c) 2024 Bud Ecosystem Inc.
#  #
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#  #
#      http://www.apache.org/licenses/LICENSE-2.0
#  #
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#  -----------------------------------------------------------------------------

from typing import Optional

from budmicroframe.commons import logging
from fastapi import APIRouter, HTTPException, Query

from budeval.evals.schemas import StartEvaluationRequest
from budeval.evals.services import EvaluationOpsService, EvaluationService

from .schemas import EvaluationRequest, EvaluationScoresResponse


logger = logging.get_logger(__name__)

evals_routes = APIRouter(prefix="/evals", tags=["Evals"])


@evals_routes.post("/start")
async def start_eval(request: EvaluationRequest):
    """Start an evaluation.

    Args:
        request (EvaluationRequest): The evaluation request.

    Returns:
        dict: A simple hello world message
    """
    try:
        response = await EvaluationService().evaluate_model(StartEvaluationRequest(**request.model_dump()))
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save evaluation request: {str(e)}") from e


@evals_routes.get("/status/{job_id}")
async def get_job_status(
    job_id: str,
    kubeconfig: Optional[str] = Query(None, description="Kubernetes configuration as JSON string (optional)"),
):
    """Get the status of an evaluation job.

    Args:
        job_id (str): The unique identifier of the job.
        kubeconfig (Optional[str]): Kubernetes configuration as JSON string (optional, uses in-cluster config if not provided).

    Returns:
        dict: Job status information
    """
    try:
        response = await EvaluationOpsService.get_job_status(job_id, kubeconfig)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get job status: {str(e)}") from e


@evals_routes.delete("/cleanup/{job_id}")
async def cleanup_job(
    job_id: str,
    kubeconfig: Optional[str] = Query(None, description="Kubernetes configuration as JSON string (optional)"),
):
    """Clean up an evaluation job and its resources.

    Args:
        job_id (str): The unique identifier of the job.
        kubeconfig (Optional[str]): Kubernetes configuration as JSON string (optional, uses in-cluster config if not provided).

    Returns:
        dict: Cleanup status information
    """
    try:
        response = await EvaluationOpsService.cleanup_job(job_id, kubeconfig)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cleanup job: {str(e)}") from e


@evals_routes.get("/results/{job_id}")
async def get_evaluation_results(job_id: str):
    """Get complete evaluation results for a job.

    Args:
        job_id (str): The job ID to retrieve results for.

    Returns:
        dict: Complete evaluation results
    """
    try:
        from budeval.evals.storage.factory import get_storage_adapter, initialize_storage

        storage = get_storage_adapter()
        if hasattr(storage, "initialize"):
            await initialize_storage(storage)
        results = await storage.get_results(job_id)

        if not results:
            raise HTTPException(status_code=404, detail=f"Results not found for job: {job_id}")

        return {"status": "success", "data": results}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve results: {str(e)}") from e


@evals_routes.get("/results/{job_id}/summary")
async def get_evaluation_summary(job_id: str):
    """Get evaluation summary for a job.

    Args:
        job_id (str): The job ID to retrieve summary for.

    Returns:
        dict: Evaluation summary
    """
    try:
        from budeval.evals.storage.factory import get_storage_adapter, initialize_storage

        storage = get_storage_adapter()
        if hasattr(storage, "initialize"):
            await initialize_storage(storage)
        results = await storage.get_results(job_id)

        if not results:
            raise HTTPException(status_code=404, detail=f"Results not found for job: {job_id}")

        # Extract summary from results
        summary = results.get("summary", {})
        return {"status": "success", "data": summary}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve summary: {str(e)}") from e


@evals_routes.get("/results/{job_id}/datasets/{dataset_name}")
async def get_dataset_results(job_id: str, dataset_name: str):
    """Get results for a specific dataset.

    Args:
        job_id (str): The job ID to retrieve results for.
        dataset_name (str): The name of the dataset.

    Returns:
        dict: Dataset-specific results
    """
    try:
        from budeval.evals.storage.factory import get_storage_adapter, initialize_storage

        storage = get_storage_adapter()
        if hasattr(storage, "initialize"):
            await initialize_storage(storage)
        results = await storage.get_results(job_id)

        if not results:
            raise HTTPException(status_code=404, detail=f"Results not found for job: {job_id}")

        # Find the specific dataset
        datasets = results.get("datasets", [])
        for dataset in datasets:
            if dataset.get("dataset_name") == dataset_name:
                return {"status": "success", "data": dataset}

        raise HTTPException(status_code=404, detail=f"Dataset '{dataset_name}' not found in job results")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve dataset results: {str(e)}") from e


@evals_routes.get("/results/{job_id}/metrics")
async def get_evaluation_metrics(job_id: str):
    """Get aggregated metrics for a job.

    Args:
        job_id (str): The job ID to retrieve metrics for.

    Returns:
        dict: Aggregated evaluation metrics
    """
    try:
        from budeval.evals.storage.factory import get_storage_adapter, initialize_storage

        storage = get_storage_adapter()
        if hasattr(storage, "initialize"):
            await initialize_storage(storage)
        results = await storage.get_results(job_id)

        if not results:
            raise HTTPException(status_code=404, detail=f"Results not found for job: {job_id}")

        # Extract metrics from summary
        summary = results.get("summary", {})
        metrics = {
            "overall_accuracy": summary.get("overall_accuracy", 0.0),
            "total_datasets": summary.get("total_datasets", 0),
            "total_examples": summary.get("total_examples", 0),
            "total_correct": summary.get("total_correct", 0),
            "dataset_accuracies": summary.get("dataset_accuracies", {}),
            "model_name": summary.get("model_name", "unknown"),
        }

        return {"status": "success", "data": metrics}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve metrics: {str(e)}") from e


@evals_routes.get("/results")
async def list_evaluation_results():
    """List all available evaluation results.

    Returns:
        dict: List of job IDs with available results
    """
    try:
        from budeval.evals.storage.factory import get_storage_adapter, initialize_storage

        storage = get_storage_adapter()
        if hasattr(storage, "initialize"):
            await initialize_storage(storage)
        job_ids = await storage.list_results()

        # Get metadata for each job
        results_list = []
        for job_id in job_ids:
            # Try to get metadata if supported by storage adapter
            if hasattr(storage, "get_metadata"):
                metadata = await storage.get_metadata(job_id)
                if metadata:
                    results_list.append(
                        {
                            "job_id": job_id,
                            "stored_at": metadata.get("stored_at"),
                            "storage_type": metadata.get("storage_type"),
                        }
                    )
            else:
                # For storage adapters without metadata, use basic info
                results_list.append({"job_id": job_id, "stored_at": None, "storage_type": storage.__class__.__name__})

        return {"status": "success", "data": {"total_results": len(job_ids), "results": results_list}}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list results: {str(e)}") from e


@evals_routes.delete("/results/{job_id}")
async def delete_evaluation_results(job_id: str):
    """Delete evaluation results for a job.

    Args:
        job_id (str): The job ID to delete results for.

    Returns:
        dict: Deletion result
    """
    try:
        from budeval.evals.storage.factory import get_storage_adapter, initialize_storage

        storage = get_storage_adapter()
        if hasattr(storage, "initialize"):
            await initialize_storage(storage)

        # Check if results exist
        if not await storage.exists(job_id):
            raise HTTPException(status_code=404, detail=f"Results not found for job: {job_id}")

        # Delete results
        success = await storage.delete_results(job_id)

        if success:
            return {"status": "success", "message": f"Results deleted successfully for job: {job_id}"}
        else:
            raise HTTPException(status_code=500, detail=f"Failed to delete results for job: {job_id}")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete results: {str(e)}") from e


@evals_routes.get("/evaluations/{evaluation_id}/scores", response_model=EvaluationScoresResponse)
async def get_evaluation_scores(evaluation_id: str):
    """Get dataset scores for a specific evaluation.

    Args:
        evaluation_id: The evaluation job ID

    Returns:
        EvaluationScoresResponse with model info and dataset scores

    Raises:
        404: If evaluation results are not found
        500: If an error occurs while retrieving results
    """
    try:
        from budeval.evals.storage.factory import get_storage_adapter, initialize_storage

        # Get storage adapter based on configuration
        storage = get_storage_adapter()

        # Initialize if needed
        if hasattr(storage, "initialize"):
            await initialize_storage(storage)

        # Check if we're using ClickHouse
        if storage.__class__.__name__ != "ClickHouseStorage":
            # Fallback for non-ClickHouse storage
            results = await storage.get_results(evaluation_id)
            if not results:
                raise HTTPException(status_code=404, detail=f"Evaluation results not found for ID: {evaluation_id}")

            # Transform to match response schema
            response = EvaluationScoresResponse(
                evaluation_id=evaluation_id,
                model_name=results.get("model_name", "unknown"),
                engine=results.get("engine", "opencompass"),
                overall_accuracy=results.get("summary", {}).get("overall_accuracy", 0.0),
                datasets=[
                    {
                        "dataset_name": ds.get("dataset_name"),
                        "accuracy": ds.get("accuracy", 0.0),
                        "total_examples": ds.get("total_examples", 0),
                        "correct_examples": ds.get("correct_examples", 0),
                    }
                    for ds in results.get("datasets", [])
                ],
            )
            return response

        # For ClickHouse storage, use the optimized method
        scores = await storage.get_evaluation_scores(evaluation_id)

        if not scores:
            raise HTTPException(status_code=404, detail=f"Evaluation results not found for ID: {evaluation_id}")

        return EvaluationScoresResponse(**scores)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get evaluation scores for {evaluation_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve evaluation scores: {str(e)}") from e
