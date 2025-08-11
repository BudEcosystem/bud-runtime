from datetime import datetime
from typing import Optional, Union
from uuid import UUID

import orjson
from budmicroframe.commons import logging
from budmicroframe.commons.schemas import ErrorResponse, SuccessResponse
from fastapi import APIRouter, Query, Response
from fastapi.responses import ORJSONResponse
from pydantic import ValidationError

from budmetrics.commons.schemas import BulkCloudEventBase
from budmetrics.observability.schemas import (
    EnhancedInferenceDetailResponse,
    GatewayAnalyticsRequest,
    InferenceDetailsMetrics,
    InferenceFeedbackResponse,
    InferenceListRequest,
    InferenceListResponse,
    ObservabilityMetricsRequest,
    ObservabilityMetricsResponse,
)
from budmetrics.observability.services import ObservabilityMetricsService


logger = logging.get_logger(__name__)

observability_router = APIRouter(prefix="/observability")

service = ObservabilityMetricsService()


@observability_router.post("/add", tags=["Observability"])
async def add_metrics(request: BulkCloudEventBase) -> Response:
    """Add metrics to ClickHouse.

    This endpoint processes incoming metrics and saves them to ClickHouse.

    Args:
        request (BulkCloudEventBase): The metrics to save.

    Returns:
        HTTP response containing the result of the operation.
    """
    response: Union[SuccessResponse, ErrorResponse]
    entries = request.entries
    logger.info(f"Received {len(entries)} entries")

    try:
        batch_data = []
        validation_errors = []

        for idx, entry in enumerate(entries):
            try:
                # Parse the incoming inference details metrics
                inference_metric = InferenceDetailsMetrics.model_validate(entry.event["data"])

                # Map InferenceDetailsMetrics to ModelInferenceDetails table fields
                # Serialize response_analysis JSON to string for ClickHouse
                response_analysis_str = None
                if inference_metric.response_analysis is not None:
                    response_analysis_str = orjson.dumps(inference_metric.response_analysis).decode("utf-8")

                inference_data = (
                    inference_metric.inference_id,  # inference_id
                    inference_metric.request_ip,  # request_ip
                    inference_metric.project_id,  # project_id
                    inference_metric.endpoint_id,  # endpoint_id
                    inference_metric.model_id,  # model_id
                    inference_metric.cost,  # cost
                    response_analysis_str,  # response_analysis (serialized JSON string)
                    inference_metric.is_success,  # is_success
                    inference_metric.request_arrival_time,  # request_arrival_time
                    inference_metric.request_forward_time,  # request_forward_time
                )
                batch_data.append(inference_data)
                # logger.debug(
                #     f"Processing metric for inference_id: {inference_metric.inference_id}"
                # )
            except ValidationError as e:
                validation_errors.append(
                    {
                        "index": idx,
                        "inference_id": (
                            str(entry.event.get("inference_id", "unknown"))
                            if hasattr(entry.event, "get")
                            else "unknown"
                        ),
                        "error": str(e),
                    }
                )
                logger.error(f"Validation error for entry {idx}: {e}")

        # If all entries failed validation, return error
        if validation_errors and len(validation_errors) == len(entries):
            return ErrorResponse(
                message=f"All {len(entries)} entries failed validation",
                details={"validation_errors": validation_errors},
            ).to_http_response()

        # Insert batch data into ClickHouse and get results
        insertion_results = {
            "total_records": 0,
            "inserted": 0,
            "duplicates": 0,
            "duplicate_ids": [],
        }
        if batch_data:
            insertion_results = await service.insert_inference_details(batch_data)

        # Build comprehensive response message
        message_parts = []

        if insertion_results["inserted"] > 0:
            message_parts.append(f"Successfully inserted {insertion_results['inserted']} new records")

        if insertion_results["duplicates"] > 0:
            message_parts.append(f"Skipped {insertion_results['duplicates']} duplicate records")

        if validation_errors:
            message_parts.append(f"Failed to validate {len(validation_errors)} entries")

        # Determine overall status
        if insertion_results["inserted"] == 0 and insertion_results["duplicates"] == 0 and not validation_errors:
            message = "No records to process"
        else:
            message = ". ".join(message_parts)

        # Build response with detailed information
        response_data = {
            "message": message,
            "summary": {
                "total_entries": len(entries),
                "successfully_inserted": insertion_results["inserted"],
                "duplicates_skipped": insertion_results["duplicates"],
                "validation_failures": len(validation_errors),
            },
        }

        # Add details if there were issues
        if insertion_results["duplicates"] > 0 or validation_errors:
            response_data["details"] = {}

            if insertion_results["duplicates"] > 0:
                # Limit duplicate IDs shown to avoid huge responses
                shown_duplicates = insertion_results["duplicate_ids"][:10]
                response_data["details"]["duplicate_inference_ids"] = shown_duplicates
                if len(insertion_results["duplicate_ids"]) > 10:
                    response_data["details"]["note"] = (
                        f"Showing first 10 of {len(insertion_results['duplicate_ids'])} duplicate IDs"
                    )

            if validation_errors:
                response_data["details"]["validation_errors"] = validation_errors[:10]
                if len(validation_errors) > 10:
                    response_data["details"]["validation_note"] = (
                        f"Showing first 10 of {len(validation_errors)} validation errors"
                    )

        response = SuccessResponse(
            message=response_data["message"],
            param={
                "summary": response_data["summary"],
                "details": response_data.get("details", {}),
            },
        )
    except Exception as e:
        logger.error(f"Error processing metrics: {e}")
        response = ErrorResponse(message=f"Error processing metrics: {str(e)}")
    # finally:
    # await service.close()

    return response.to_http_response()


@observability_router.post("/analytics", tags=["Observability"])
async def get_analytics(request: ObservabilityMetricsRequest) -> Response:
    """Get analytics for various metrics.

    This unified endpoint handles all analytics requests including:
    - Request counts
    - Success/failure rates
    - Performance metrics (TTFT, latency, throughput)
    - Cache metrics
    - Concurrent requests
    - Token usage
    - Queuing time

    Args:
        request (ObservabilityMetricsRequest): The analytics request parameters.

    Returns:
        HTTP response containing the analytics results.
    """
    response: Union[ObservabilityMetricsResponse, ErrorResponse]

    try:
        response = await service.get_metrics(request)
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        response = ErrorResponse(message=f"Validation error: {str(e)}")
    except Exception as e:
        logger.error(f"Error getting analytics: {e}")
        response = ErrorResponse(message=f"Error getting analytics: {str(e)}")
    # finally:
    #     await service.close()

    return response.to_http_response()


@observability_router.post("/inferences/list", tags=["Observability"])
async def list_inference_requests(request: InferenceListRequest) -> Response:
    """List inference requests with pagination and filtering.

    This endpoint retrieves inference requests from ClickHouse with support for:
    - Pagination (offset/limit)
    - Filtering by project, endpoint, model, date range, success status
    - Token range and latency filtering
    - Sorting by timestamp, tokens, latency, or cost

    Args:
        request (InferenceListRequest): The list request parameters.

    Returns:
        HTTP response containing paginated inference list.
    """
    response: Union[InferenceListResponse, ErrorResponse]

    try:
        response = await service.list_inferences(request)
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        response = ErrorResponse(message=f"Validation error: {str(e)}")
    except Exception as e:
        logger.error(f"Error listing inferences: {e}")
        response = ErrorResponse(message=f"Error listing inferences: {str(e)}")

    return response.to_http_response()


@observability_router.get("/inferences/{inference_id}", tags=["Observability"])
async def get_inference_details(inference_id: str) -> Response:
    """Get complete details for a single inference.

    This endpoint retrieves full inference details including:
    - Complete prompt and response content
    - Model and provider information
    - Performance metrics (latency, TTFT, tokens)
    - Request metadata and timestamps
    - Feedback summary

    Args:
        inference_id (str): The UUID of the inference to retrieve.

    Returns:
        HTTP response containing detailed inference information.
    """
    response: Union[EnhancedInferenceDetailResponse, ErrorResponse]

    try:
        response = await service.get_inference_details(inference_id)
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        response = ErrorResponse(message=f"Validation error: {str(e)}")
    except Exception as e:
        logger.error(f"Error getting inference details: {e}")
        response = ErrorResponse(message=f"Error getting inference details: {str(e)}")

    return response.to_http_response()


@observability_router.get("/inferences/{inference_id}/feedback", tags=["Observability"])
async def get_inference_feedback(inference_id: str) -> Response:
    """Get all feedback associated with an inference.

    This endpoint retrieves all feedback types for an inference:
    - Boolean metrics
    - Float metrics
    - Comment feedback
    - Demonstration feedback

    Args:
        inference_id (str): The UUID of the inference.

    Returns:
        HTTP response containing aggregated feedback data.
    """
    response: Union[InferenceFeedbackResponse, ErrorResponse]

    try:
        response = await service.get_inference_feedback(inference_id)
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        response = ErrorResponse(message=f"Validation error: {str(e)}")
    except Exception as e:
        logger.error(f"Error getting inference feedback: {e}")
        response = ErrorResponse(message=f"Error getting inference feedback: {str(e)}")

    return response.to_http_response()


# Gateway Analytics Routes
@observability_router.post("/gateway/analytics", tags=["Gateway Analytics"])
async def get_gateway_analytics(
    request: GatewayAnalyticsRequest,
) -> Response:
    """Get gateway analytics metrics."""
    try:
        response = await service.get_gateway_metrics(request)
        return response.to_http_response()
    except Exception as e:
        error_response = ErrorResponse(
            object="error",
            code=500,
            message=f"Failed to fetch gateway analytics: {str(e)}",
        )
        return error_response.to_http_response()


@observability_router.get("/gateway/geographical-stats", tags=["Gateway Analytics"])
async def get_geographical_stats(
    from_date: datetime = Query(..., description="Start date for the analysis"),
    to_date: Optional[datetime] = Query(None, description="End date for the analysis"),
    project_id: Optional[UUID] = Query(None, description="Filter by project ID"),
) -> Response:
    """Get geographical distribution statistics."""
    try:
        response = await service.get_geographical_stats(from_date=from_date, to_date=to_date, project_id=project_id)
        return response.to_http_response()
    except Exception as e:
        error_response = ErrorResponse(
            object="error",
            code=500,
            message=f"Failed to fetch geographical stats: {str(e)}",
        )
        return error_response.to_http_response()


@observability_router.get("/gateway/blocking-stats", tags=["Gateway Analytics"])
async def get_blocking_stats(
    from_date: datetime = Query(..., description="Start date for the analysis"),
    to_date: Optional[datetime] = Query(None, description="End date for the analysis"),
    project_id: Optional[UUID] = Query(None, description="Filter by project ID"),
) -> Response:
    """Get blocking rule statistics."""
    try:
        response = await service.get_blocking_stats(from_date=from_date, to_date=to_date, project_id=project_id)
        return response.to_http_response()
    except Exception as e:
        error_response = ErrorResponse(
            object="error",
            code=500,
            message=f"Failed to fetch blocking stats: {str(e)}",
        )
        return error_response.to_http_response()


@observability_router.get("/gateway/top-routes", tags=["Gateway Analytics"])
async def get_top_routes(
    from_date: datetime = Query(..., description="Start date for the analysis"),
    to_date: Optional[datetime] = Query(None, description="End date for the analysis"),
    limit: int = Query(10, description="Number of top routes to return"),
    project_id: Optional[UUID] = Query(None, description="Filter by project ID"),
) -> Response:
    """Get top API routes by request count."""
    try:
        routes = await service.get_top_routes(from_date=from_date, to_date=to_date, limit=limit, project_id=project_id)
        return ORJSONResponse(content={"routes": routes}, status_code=200)
    except Exception as e:
        error_response = ErrorResponse(
            object="error",
            code=500,
            message=f"Failed to fetch top routes: {str(e)}",
        )
        return error_response.to_http_response()


@observability_router.get("/gateway/client-analytics", tags=["Gateway Analytics"])
async def get_client_analytics(
    from_date: datetime = Query(..., description="Start date for the analysis"),
    to_date: Optional[datetime] = Query(None, description="End date for the analysis"),
    group_by: str = Query("device_type", description="Group by: device_type, browser, os"),
    project_id: Optional[UUID] = Query(None, description="Filter by project ID"),
) -> Response:
    """Get client analytics (device, browser, OS distribution)."""
    try:
        response = await service.get_client_analytics(
            from_date=from_date, to_date=to_date, group_by=group_by, project_id=project_id
        )
        return ORJSONResponse(content=response, status_code=200)
    except Exception as e:
        error_response = ErrorResponse(
            object="error",
            code=500,
            message=f"Failed to fetch client analytics: {str(e)}",
        )
        return error_response.to_http_response()
