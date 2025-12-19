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

"""This file contains the routes for the leaderboard API."""

from datetime import datetime
from typing import Annotated, List, Union

from budmicroframe.commons import logging
from budmicroframe.commons.schemas import ErrorResponse, SuccessResponse
from fastapi import APIRouter, Query, Request, Response, status
from fastapi.exceptions import HTTPException

from .schemas import LeaderboardListResponse, LeaderboardModelCompareResponse, LeaderboardModelUrisListResponse
from .services import LeaderboardService
from .workflows import LeaderboardExtractionWorkflow


logger = logging.get_logger(__name__)

leaderboard_router = APIRouter(prefix="/leaderboard", tags=["Leaderboard"])


@leaderboard_router.get("/model-params")
async def get_leaderboard_table(
    model_uri: str = Query(description="Model URI"),
    k: int = Query(5, description="Number of leaderboard entries to return"),
) -> Response:
    """Get the leaderboard table.

    This endpoint processes the model extraction request and returns
    recommendations for deployment strategies based on the specified
    parameters.

    Args:
        request (ModelExtractionRequest): The model extraction request
        containing model URI, input/output tokens, concurrency,
        and target performance metrics.

    Returns:
        HTTP response containing the leaderboard table.
    """
    response: Union[LeaderboardListResponse, ErrorResponse]
    try:
        logger.info("Getting leaderboard table for model %s", model_uri)
        db_results = await LeaderboardService().get_leaderboard_table(model_uri, k)
        return LeaderboardListResponse(
            code=status.HTTP_200_OK,
            message=f"Leaderboard table fetched successfully for model {model_uri}",
            object="leaderboard.model-params",
            leaderboards=db_results,
        )
    except HTTPException as e:
        return ErrorResponse(message=e.detail, code=e.status_code)
    except Exception as e:
        logger.exception("Error getting leaderboard table: %s", str(e))
        response = ErrorResponse(message="Error getting leaderboard table", code=500)

    return response.to_http_response()


@leaderboard_router.get("/models/compare")
async def get_leaderboard_by_models(
    model_uris: Annotated[List[str] | None, Query(description="List of model URIs to filter by")] = None,
    benchmark_fields: Annotated[
        List[str] | None,
        Query(description="List of benchmark fields to filter by"),
    ] = None,
    k: Annotated[int, Query(description="Number of leaderboards to return", ge=1)] = 5,
) -> Response:
    """Get the leaderboards for the given model URIs.

    This endpoint processes the leaderboards for the given model URIs.

    Args:
        model_uris (List[str]): List of model URIs to filter by
        k (int): Number of leaderboards to return

    Returns:
        HTTP response containing the leaderboards.
    """
    response: Union[LeaderboardModelCompareResponse, ErrorResponse]
    try:
        model_uris = model_uris or []
        benchmark_fields = benchmark_fields or []
        logger.debug("Getting leaderboards for %s models", len(model_uris))
        db_results = await LeaderboardService().get_leaderboards_by_models(model_uris, benchmark_fields, k)
        return LeaderboardModelCompareResponse(
            code=status.HTTP_200_OK,
            message=f"Leaderboards fetched successfully for {len(model_uris)} models",
            object="leaderboard.model-compare",
            leaderboards=db_results,
        )
    except HTTPException as e:
        return ErrorResponse(message=e.detail, code=e.status_code)
    except Exception as e:
        logger.exception("Error getting leaderboards: %s", str(e))
        response = ErrorResponse(message="Error getting leaderboards", code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return response.to_http_response()


@leaderboard_router.get("/models-uris")
async def get_leaderboard_by_model_uris(
    model_uris: Annotated[List[str] | None, Query(description="List of model URIs to filter by")] = None,
) -> Response:
    """Get the leaderboards for the given model URIs.

    This endpoint processes the leaderboards for the given model URIs.

    Args:
        model_uris (List[str]): List of model URIs to filter by

    Returns:
        HTTP response containing the leaderboards.
    """
    response: Union[LeaderboardModelUrisListResponse, ErrorResponse]
    try:
        model_uris = model_uris or []
        logger.debug("Getting leaderboards for %s models", len(model_uris))
        db_results = await LeaderboardService().get_model_evals_by_uris(model_uris)
        return LeaderboardModelUrisListResponse(
            code=status.HTTP_200_OK,
            message=f"Leaderboards fetched successfully for {len(model_uris)} models",
            object="leaderboard.model-uris",
            leaderboards=db_results,
        )
    except HTTPException as e:
        return ErrorResponse(message=e.detail, code=e.status_code)
    except Exception as e:
        logger.exception("Error getting leaderboards: %s", str(e))
        response = ErrorResponse(message="Error getting leaderboards", code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return response.to_http_response()


@leaderboard_router.post(
    "/extraction-cron",
    response_model=Union[SuccessResponse, ErrorResponse],
    summary="Scheduled leaderboard extraction (Dapr cron trigger)",
    description="Periodic extraction of leaderboard data from all sources triggered by Dapr cron binding",
    responses={
        200: {
            "description": "Extraction workflow triggered successfully",
            "model": SuccessResponse,
        },
        500: {"description": "Internal server error"},
    },
)
async def perform_leaderboard_extraction_cron(request: Request) -> Response:
    """Run scheduled leaderboard extraction triggered by Dapr cron binding.

    This endpoint is invoked every 7 days by the Dapr cron scheduler to extract
    and update leaderboard data from all configured sources.

    The endpoint triggers a Dapr workflow and returns immediately without blocking.
    The actual extraction runs asynchronously in the background.

    Returns:
        HTTP response indicating workflow was triggered successfully.
    """
    response: Union[SuccessResponse, ErrorResponse]

    try:
        logger.info("Scheduled leaderboard extraction triggered by Dapr cron binding")

        # Track last extraction time for health monitoring
        if not hasattr(perform_leaderboard_extraction_cron, "last_extraction_time"):
            perform_leaderboard_extraction_cron.last_extraction_time = None

        perform_leaderboard_extraction_cron.last_extraction_time = datetime.utcnow().isoformat()

        # Trigger workflow asynchronously (non-blocking)
        await LeaderboardExtractionWorkflow().__call__()

        response = SuccessResponse(
            message="Leaderboard extraction workflow triggered successfully",
            code=200,
        )

    except Exception as e:
        logger.exception("Error triggering leaderboard extraction workflow: %s", str(e))
        response = ErrorResponse(
            message="Error triggering leaderboard extraction workflow",
            code=500,
        )

    return response.to_http_response()


@leaderboard_router.get(
    "/extraction-cron/health",
    summary="Health check for leaderboard extraction scheduler",
    description="Verify periodic extraction is configured and check last execution status",
)
async def leaderboard_extraction_health():
    """Health check endpoint to verify periodic extraction is configured.

    Returns:
        dict: Status of the periodic extraction configuration including:
            - binding_configured: Whether the Dapr binding file exists
            - schedule: The configured schedule (@every 168h)
            - last_extraction_time: ISO timestamp of last extraction
            - is_stale: Whether extraction hasn't run in > 8 days
            - status: Overall health status (healthy/initializing/stale/unhealthy)
    """
    import os
    from datetime import timedelta

    binding_file = ".dapr/components/binding.yaml"
    binding_exists = os.path.exists(binding_file)

    # Get last extraction time from the cron endpoint function attribute
    last_extraction_time = None
    if hasattr(perform_leaderboard_extraction_cron, "last_extraction_time"):
        last_extraction_time = perform_leaderboard_extraction_cron.last_extraction_time

    # Check if extraction is stale (hasn't run in > 8 days)
    is_stale = False
    if last_extraction_time:
        last_extraction = datetime.fromisoformat(last_extraction_time)
        if datetime.utcnow() - last_extraction > timedelta(days=8):
            is_stale = True

    health_status = "healthy"
    if not binding_exists:
        health_status = "unhealthy"
    elif last_extraction_time is None:
        health_status = "initializing"
    elif is_stale:
        health_status = "stale"

    return {
        "binding_configured": binding_exists,
        "schedule": "@every 168h",
        "last_extraction_time": last_extraction_time,
        "is_stale": is_stale,
        "status": health_status,
    }


@leaderboard_router.post(
    "/extraction-cron/trigger",
    response_model=Union[SuccessResponse, ErrorResponse],
    summary="Manually trigger leaderboard extraction",
    description="Trigger leaderboard extraction workflow on-demand without waiting for the scheduled cron",
)
async def trigger_manual_extraction():
    """Manually trigger leaderboard extraction without waiting for the cron.

    This endpoint allows operators to trigger extraction on-demand, useful for:
    - Testing the extraction process
    - Forcing an update before the scheduled time
    - Recovery from failed scheduled extractions

    The endpoint triggers a Dapr workflow and returns immediately without blocking.
    The actual extraction runs asynchronously in the background.

    Returns:
        SuccessResponse or ErrorResponse
    """
    response: Union[SuccessResponse, ErrorResponse]

    try:
        logger.info("Manual leaderboard extraction triggered via API")

        # Track last extraction time for health monitoring
        if not hasattr(perform_leaderboard_extraction_cron, "last_extraction_time"):
            perform_leaderboard_extraction_cron.last_extraction_time = None

        perform_leaderboard_extraction_cron.last_extraction_time = datetime.utcnow().isoformat()

        # Trigger workflow asynchronously (non-blocking)
        await LeaderboardExtractionWorkflow().__call__()

        response = SuccessResponse(
            message="Manual leaderboard extraction workflow triggered successfully",
            code=200,
        )

    except Exception as e:
        logger.exception("Error triggering manual extraction workflow: %s", str(e))
        response = ErrorResponse(
            message=f"Error triggering manual extraction workflow: {str(e)}",
            code=500,
        )

    return response.to_http_response()
