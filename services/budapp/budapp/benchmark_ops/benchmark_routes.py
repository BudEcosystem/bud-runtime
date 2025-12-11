# budapp/cluster_ops/cluster_routes.py
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

"""The benchmark ops package, containing essential business logic, services, and routing configurations for the benchmark ops."""

from typing import List, Optional, Union
from uuid import UUID

from budmicroframe.commons.schemas import PaginatedResponse, SuccessResponse
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing_extensions import Annotated

from budapp.commons import logging
from budapp.commons.constants import PermissionEnum
from budapp.commons.dependencies import (
    get_current_active_user,
    get_session,
    parse_ordering_fields,
)
from budapp.commons.exceptions import ClientException
from budapp.commons.permission_handler import require_permissions
from budapp.commons.schemas import ErrorResponse
from budapp.endpoint_ops.schemas import ModelClusterDetailResponse
from budapp.user_ops.schemas import User
from budapp.workflow_ops.schemas import RetrieveWorkflowDataResponse
from budapp.workflow_ops.services import WorkflowService

from ..commons.constants import BenchmarkFilterResourceEnum
from .schemas import (
    AddRequestMetricsRequest,
    BenchmarkFilter,
    BenchmarkFilterFields,
    BenchmarkFilterValueResponse,
    BenchmarkPaginatedResponse,
    NodeConfigurationProxyRequest,
    NodeConfigurationProxyResponse,
    RunBenchmarkWorkflowRequest,
)
from .services import BenchmarkRequestMetricsService, BenchmarkService


logger = logging.get_logger(__name__)

benchmark_router = APIRouter(prefix="/benchmark", tags=["benchmark"])


@benchmark_router.post(
    "/run-workflow",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_200_OK: {
            "model": RetrieveWorkflowDataResponse,
            "description": "Run benchmark workflow executed successfully",
        },
    },
    description="Run benchmark workflow",
)
@require_permissions(permissions=[PermissionEnum.BENCHMARK_MANAGE])
async def run_benchmark_workflow(
    request: RunBenchmarkWorkflowRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Union[RetrieveWorkflowDataResponse, ErrorResponse]:
    """Run benchmark workflow."""
    try:
        db_workflow = await BenchmarkService(session).run_benchmark_workflow(
            current_user_id=current_user.id,
            request=request,
        )

        return await WorkflowService(session).retrieve_workflow_data(db_workflow.id)
    except ClientException as e:
        logger.exception(f"Failed to run benchmark workflow: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to run benchmark workflow: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to run benchmark workflow"
        ).to_http_response()


@benchmark_router.get(
    "",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_200_OK: {
            "model": BenchmarkPaginatedResponse,
            "description": "Successfully list all benchmarks",
        },
    },
    description="List all benchmarks. \n\n order_by fields are: name, status, created_at, cluster_name, model_name",
)
@require_permissions(permissions=[PermissionEnum.BENCHMARK_VIEW])
async def list_all_benchmarks(
    current_user: Annotated[User, Depends(get_current_active_user)],  # noqa: B008
    session: Annotated[Session, Depends(get_session)],
    filters: Annotated[BenchmarkFilter, Depends()],
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=0),
    order_by: Optional[List[str]] = Depends(parse_ordering_fields),
    search: bool = False,
) -> Union[BenchmarkPaginatedResponse, ErrorResponse]:
    """List all benchmarks."""
    # Calculate offset
    offset = (page - 1) * limit

    # Construct filters
    filters_dict = filters.model_dump(exclude_none=True, exclude_unset=True)

    try:
        db_benchmarks, count = await BenchmarkService(session).get_benchmarks(
            offset, limit, filters_dict, order_by, search
        )
    except ClientException as e:
        logger.exception(f"Failed to get all benchmarks: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get all benchmarks: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get all benchmarks"
        ).to_http_response()

    return BenchmarkPaginatedResponse(
        benchmarks=db_benchmarks,
        total_record=count,
        page=page,
        limit=limit,
        object="benchmarks.list",
        code=status.HTTP_200_OK,
        message="Successfully list all benchmarks",
    ).to_http_response()


@benchmark_router.get(
    "/filters",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_200_OK: {
            "model": BenchmarkFilterValueResponse,
            "description": "Successfully list all benchmark filters",
        },
    },
    description="List unique benchmark filter values",
)
@require_permissions(permissions=[PermissionEnum.BENCHMARK_VIEW])
async def list_all_benchmark_filters(
    current_user: Annotated[User, Depends(get_current_active_user)],  # noqa: B008
    session: Annotated[Session, Depends(get_session)],
    filters: Annotated[BenchmarkFilterFields, Depends()],
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=0),
    search: bool = False,
) -> Union[BenchmarkFilterValueResponse, ErrorResponse]:
    """List unique benchmark filter values."""
    offset = (page - 1) * limit

    # Get the name to filter by
    if filters.resource == BenchmarkFilterResourceEnum.MODEL:
        name = filters.model_name or None
    else:
        name = filters.cluster_name or None

    result, count = await BenchmarkService(session).list_benchmark_filter_values(
        filters.resource, name, search, offset, limit
    )

    return BenchmarkFilterValueResponse(
        result=result,
        total_record=count,
        page=page,
        limit=limit,
        object="benchmarks.filters.list",
        code=status.HTTP_200_OK,
    ).to_http_response()


@benchmark_router.get(
    "/result",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_200_OK: {
            "model": SuccessResponse,
            "description": "Successfully fetch benchmark result",
        },
    },
    description="Fetch benchmark result",
)
@require_permissions(permissions=[PermissionEnum.BENCHMARK_VIEW])
async def get_benchmark_result(
    benchmark_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],  # noqa: B008
    session: Annotated[Session, Depends(get_session)],
) -> Union[SuccessResponse, ErrorResponse]:
    """Fetch benchmark result."""
    try:
        db_benchmark_result = await BenchmarkService(session).get_benchmark_result(benchmark_id)
        response = SuccessResponse(
            object="benchmark.result",
            param=db_benchmark_result,
            message="Successfully fetched benchmark result",
        )
    except HTTPException as e:
        logger.exception(f"Failed to get benchmark result: {e}")
        response = ErrorResponse(code=e.status_code, message=e.detail)
    except ClientException as e:
        logger.exception(f"Failed to get benchmark result: {e}")
        response = ErrorResponse(code=e.status_code, message=e.message)
    except Exception as e:
        logger.exception(f"Failed to get benchmark result: {e}")
        response = ErrorResponse(code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get benchmark result")

    return response.to_http_response()


@benchmark_router.get(
    "/{benchmark_id}/model-cluster-detail",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_200_OK: {
            "model": ModelClusterDetailResponse,
            "description": "Successfully fetch benchmark's model and cluster details",
        },
    },
    description="Fetch benchmark's model and cluster details",
)
@require_permissions(permissions=[PermissionEnum.BENCHMARK_VIEW])
async def get_benchmark_model_cluster_detail(
    benchmark_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],  # noqa: B008
    session: Annotated[Session, Depends(get_session)],
) -> Union[ModelClusterDetailResponse, ErrorResponse]:
    """Fetch benchmark result."""
    try:
        model_cluster_detail = await BenchmarkService(session).get_benchmark_model_cluster_detail(benchmark_id)
        response = ModelClusterDetailResponse(
            object="benchmark.model.cluster.detail",
            result=model_cluster_detail,
            message="Successfully fetched model cluster detail for the benchmark.",
        )
    except HTTPException as e:
        logger.exception(f"Failed to get benchmark's model cluster detail': {e}")
        response = ErrorResponse(code=e.status_code, message=e.detail)
    except ClientException as e:
        logger.exception(f"Failed to get benchmark's model cluster detail: {e}")
        response = ErrorResponse(code=e.status_code, message=e.message)
    except Exception as e:
        logger.exception(f"Failed to get benchmark's model cluster detail: {e}")
        response = ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get benchmark's model cluster detail"
        )

    return response.to_http_response()


@benchmark_router.post(
    "/analysis/field1_vs_field2",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_200_OK: {
            "model": SuccessResponse,
            "description": "Successfully fetched analysis data",
        },
    },
    description="Fetchetched analysis data",
)
@require_permissions(permissions=[PermissionEnum.BENCHMARK_VIEW])
async def get_field1_vs_field2_data(
    current_user: Annotated[User, Depends(get_current_active_user)],  # noqa: B008
    session: Annotated[Session, Depends(get_session)],
    field1: str,
    field2: str,
    model_ids: Optional[List[UUID]] = None,
) -> Union[SuccessResponse, ErrorResponse]:
    """Fetch field1 vs field2 analysis."""
    try:
        field1_vs_field2_data = BenchmarkService(session).get_field1_vs_field2_data(field1, field2, model_ids)
        response = SuccessResponse(
            object="benchmark.model.cluster.detail",
            param={"result": field1_vs_field2_data},
            message=f"Successfully fetched {field1} vs {field2} analysis data.",
        )
    except Exception as e:
        logger.exception(f"Failed to fetch {field1} vs {field2} data: {e}")
        response = ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message=f"Failed to fetch {field1} vs {field2} data: {e}"
        )

    return response.to_http_response()


@benchmark_router.post(
    "/{benchmark_id}/analysis/field1_vs_field2",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_200_OK: {
            "model": SuccessResponse,
            "description": "Successfully fetched analysis data",
        },
    },
    description="Fetchetched analysis data",
)
@require_permissions(permissions=[PermissionEnum.BENCHMARK_VIEW])
async def get_field1_vs_field2_benchmark_data(
    current_user: Annotated[User, Depends(get_current_active_user)],  # noqa: B008
    session: Annotated[Session, Depends(get_session)],
    benchmark_id: UUID,
    field1: str,
    field2: str,
) -> Union[SuccessResponse, ErrorResponse]:
    """Fetch field1 vs field2 analysis."""
    try:
        field1_vs_field2_data = BenchmarkRequestMetricsService(session).get_field1_vs_field2_data(
            field1, field2, benchmark_id
        )
        response = SuccessResponse(
            object="benchmark.request.metrics.detail",
            param={"result": field1_vs_field2_data},
            message=f"Successfully fetched {field1} vs {field2} analysis data for benchmark : {benchmark_id}.",
        )
    except Exception as e:
        logger.exception(f"Failed to fetch {field1} vs {field2} data for benchmark : {benchmark_id} : {e}")
        response = ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=f"Failed to fetch {field1} vs {field2} data for benchmark : {benchmark_id} : {e}",
        )

    return response.to_http_response()


@benchmark_router.post(
    "/request-metrics",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_200_OK: {
            "model": SuccessResponse,
            "description": "Successfully added request metrics",
        },
    },
    description="Add request metrics (Internal endpoint for service-to-service calls via Dapr)",
    tags=["internal"],
)
async def add_request_metrics_internal(
    session: Annotated[Session, Depends(get_session)],
    request: AddRequestMetricsRequest,
) -> Union[SuccessResponse, ErrorResponse]:
    """Add request metrics - Internal endpoint for budcluster service."""
    try:
        await BenchmarkRequestMetricsService(session).add_request_metrics(request)
        response = SuccessResponse(
            object="benchmark.request.metrics",
            param=None,
            message="Successfully added request metrics",
        )
    except ValueError as e:
        logger.exception(f"Failed to add request metrics: {e}")
        response = ErrorResponse(code=status.HTTP_400_BAD_REQUEST, message=str(e))
    except Exception as e:
        logger.exception(f"Failed to add request metrics: {e}")
        response = ErrorResponse(code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to add request metrics")

    return response.to_http_response()


@benchmark_router.post(
    "/add-request-metrics",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_200_OK: {
            "model": SuccessResponse,
            "description": "Successfully added request metrics",
        },
    },
    description="Add request metrics (Authenticated endpoint for external use)",
)
@require_permissions(permissions=[PermissionEnum.BENCHMARK_MANAGE])
async def add_request_metrics(
    session: Annotated[Session, Depends(get_session)],
    request: AddRequestMetricsRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> Union[SuccessResponse, ErrorResponse]:
    """Add request metrics - Authenticated endpoint."""
    try:
        await BenchmarkRequestMetricsService(session).add_request_metrics(request)
        response = SuccessResponse(
            object="benchmark.request.metrics",
            param=None,
            message="Successfully added request metrics",
        )
    except ValueError as e:
        logger.exception(f"Failed to add request metrics: {e}")
        response = ErrorResponse(code=status.HTTP_400_BAD_REQUEST, message=str(e))
    except Exception as e:
        logger.exception(f"Failed to add request metrics: {e}")
        response = ErrorResponse(code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to add request metrics")

    return response.to_http_response()


@benchmark_router.post(
    "/dataset/input-distribution",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_200_OK: {
            "model": SuccessResponse,
            "description": "Successfully fetched dataset metrics",
        },
    },
    description="Get dataset vs input-distribution",
)
@require_permissions(permissions=[PermissionEnum.BENCHMARK_VIEW])
async def get_dataset_input_distribution(
    dataset_ids: List[UUID],
    current_user: Annotated[User, Depends(get_current_active_user)],  # noqa: B008
    session: Annotated[Session, Depends(get_session)],
    benchmark_id: Optional[UUID] = None,
    num_bins: int = 10,
) -> Union[SuccessResponse, ErrorResponse]:
    """Get dataset input distribution."""
    try:
        dataset_input_distribution = await BenchmarkRequestMetricsService(session).get_dataset_distribution_metrics(
            distribution_type="prompt_len", dataset_ids=dataset_ids, benchmark_id=benchmark_id, num_bins=num_bins
        )
        response = SuccessResponse(
            object="benchmark.dataset.input.distribution",
            param={"result": dataset_input_distribution},
            message="Successfully fetched dataset input distribution",
        )
    except HTTPException as http_exc:
        logger.exception(f"Failed to fetch dataset input distribution: {http_exc}")
        response = ErrorResponse(code=http_exc.status_code, message=http_exc.detail)
    except Exception as e:
        logger.exception(f"Failed to fetch dataset input distribution: {e}")
        response = ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to fetch dataset input distribution"
        )

    return response.to_http_response()


@benchmark_router.post(
    "/dataset/output-distribution",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_200_OK: {
            "model": SuccessResponse,
            "description": "Successfully fetched dataset metrics",
        },
    },
    description="Get dataset vs output-distribution",
)
@require_permissions(permissions=[PermissionEnum.BENCHMARK_VIEW])
async def get_dataset_output_distribution(
    dataset_ids: List[UUID],
    current_user: Annotated[User, Depends(get_current_active_user)],  # noqa: B008
    session: Annotated[Session, Depends(get_session)],
    benchmark_id: Optional[UUID] = None,
    num_bins: int = 10,
) -> Union[SuccessResponse, ErrorResponse]:
    """Get dataset output distribution."""
    try:
        dataset_output_distribution = await BenchmarkRequestMetricsService(session).get_dataset_distribution_metrics(
            distribution_type="output_len", dataset_ids=dataset_ids, benchmark_id=benchmark_id, num_bins=num_bins
        )
        response = SuccessResponse(
            object="benchmark.dataset.input.distribution",
            param={"result": dataset_output_distribution},
            message="Successfully fetched dataset output distribution",
        )
    except HTTPException as http_exc:
        logger.exception(f"Failed to fetch dataset output distribution: {http_exc}")
        response = ErrorResponse(code=http_exc.status_code, message=http_exc.detail)
    except Exception as e:
        logger.exception(f"Failed to fetch dataset output distribution: {e}")
        response = ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to fetch dataset output distribution"
        )

    return response.to_http_response()


@benchmark_router.get(
    "/request-metrics",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_200_OK: {
            "model": SuccessResponse,
            "description": "Successfully fetched benchmark request metrics",
        },
    },
    description="Get benchmark request metrics",
)
@require_permissions(permissions=[PermissionEnum.BENCHMARK_VIEW])
async def get_request_metrics(
    benchmark_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],  # noqa: B008
    session: Annotated[Session, Depends(get_session)],
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=0),
) -> Union[SuccessResponse, ErrorResponse]:
    """Get benchmark request metrics."""
    try:
        request_metrics, count = await BenchmarkRequestMetricsService(session).get_request_metrics(
            benchmark_id=benchmark_id, offset=(page - 1) * limit, limit=limit
        )
        response = PaginatedResponse(
            object="benchmark.request.metrics.list",
            items=request_metrics,
            page=page,
            limit=limit,
            total_items=count,
        )
    except Exception as e:
        logger.exception(f"Failed to fetch benchmark request metricsn: {e}")
        response = ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to fetch benchmark request metrics"
        )

    return response.to_http_response()


@benchmark_router.post(
    "/node-configurations",
    responses={
        status.HTTP_200_OK: {
            "model": NodeConfigurationProxyResponse,
            "description": "Successfully retrieved node configuration options",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Invalid request parameters",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
    },
    description="Get valid TP/PP configuration options for selected nodes by proxying to budsim",
)
@require_permissions(permissions=[PermissionEnum.BENCHMARK_MANAGE])
async def get_node_configurations(
    request: NodeConfigurationProxyRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Union[NodeConfigurationProxyResponse, ErrorResponse]:
    """Get node configuration options by proxying to budsim service.

    This endpoint:
    1. Validates user has access to the cluster and model
    2. Enriches the request with model URI from the database
    3. Proxies the request to budsim service
    4. Returns the configuration options with model display name
    """
    try:
        result = await BenchmarkService(session).get_node_configurations(request)
        return NodeConfigurationProxyResponse(**result).to_http_response()
    except ClientException as e:
        logger.exception(f"Failed to get node configurations: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get node configurations: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to get node configurations",
        ).to_http_response()
