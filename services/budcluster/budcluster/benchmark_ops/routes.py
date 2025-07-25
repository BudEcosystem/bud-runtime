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

"""Defines metadata routes for the microservices, providing endpoints for retrieving service-level information."""

from uuid import UUID

from budmicroframe.commons import logging
from budmicroframe.commons.schemas import ErrorResponse, SuccessResponse, WorkflowMetadataResponse
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..commons.dependencies import get_session
from .schemas import (
    RunBenchmarkRequest,
)
from .services import BenchmarkService


logger = logging.get_logger(__name__)

benchmark_router = APIRouter(prefix="/benchmark")


@benchmark_router.post(
    "/run",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_200_OK: {
            "model": WorkflowMetadataResponse,
            "description": "Benchmark workflow created successfully",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Cluster not found",
        },
    },
    status_code=status.HTTP_200_OK,
    description="Creates a benchmark workflow",
    tags=["Benchmarks"],
)
async def create_benchmark_workflow(request: RunBenchmarkRequest, session: Session = Depends(get_session)):  # noqa: B008
    """Create a benchmark workflow."""
    try:
        response = await BenchmarkService(session).create_benchmark(request)
    except Exception as e:
        response = ErrorResponse(message=str(e))
    return response.to_http_response()


@benchmark_router.get(
    "/result",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_200_OK: {
            "model": SuccessResponse,
            "description": "Benchmark results fetched successfully",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Benchmark not found",
        },
    },
    status_code=status.HTTP_200_OK,
    description="Fetches benchmark result",
    tags=["Benchmarks"],
)
async def get_benchmark_result(benchmark_id: UUID, session: Session = Depends(get_session)):  # noqa: B008
    """Create a benchmark workflow."""
    try:
        benchmark_result = await BenchmarkService(session).get_benchmark_result(benchmark_id)
        response = SuccessResponse(
            object="benchmark.result",
            message="Successfully fetched benchmark result",
            param={"result": benchmark_result},
        )
    except HTTPException as e:
        response = ErrorResponse(message=str(e), code=e.status_code)
    except Exception as e:
        response = ErrorResponse(message=str(e))
    return response.to_http_response()
