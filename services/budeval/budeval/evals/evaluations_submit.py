"""Additional evaluations endpoint for /evaluations/submit path."""

from typing import Any, Dict

from fastapi import HTTPException

from budeval.evals.routes import evaluations_routes, logger
from budeval.evals.schemas import EvaluationRequest
from budeval.evals.workflows import EvaluationWorkflow


@evaluations_routes.post("/submit")
async def submit_evaluation(request: EvaluationRequest) -> Dict[str, Any]:
    """Submit an evaluation job and return workflow metadata.

    Args:
        request: Evaluation request

    Returns:
        Dictionary with workflow metadata in standard format matching budcluster
    """
    try:
        workflow = EvaluationWorkflow()
        result = await workflow(request)

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
        logger.error(f"Error submitting evaluation: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}") from e
