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

from typing import Annotated, List, Union

from budmicroframe.commons import logging
from budmicroframe.commons.schemas import ErrorResponse
from fastapi import APIRouter, Query, Response, status
from fastapi.exceptions import HTTPException

from ..commons.constants import LEADERBOARD_FIELDS
from .schemas import LeaderboardListResponse, LeaderboardModelCompareResponse, LeaderboardModelUrisListResponse
from .services import LeaderboardService
from .workflows import LeaderboardCronWorkflows  # noqa: F401


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
    model_uris: Annotated[
        List[str] | None, Query(..., description="List of model URIs to filter by", default_factory=list)
    ] = None,
    benchmark_fields: Annotated[
        List[str] | None,
        Query(..., description="List of benchmark fields to filter by", default_factory=list),
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
    model_uris: Annotated[
        List[str] | None, Query(..., description="List of model URIs to filter by", default_factory=list)
    ] = None
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
