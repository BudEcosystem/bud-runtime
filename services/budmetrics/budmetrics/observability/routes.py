from datetime import datetime
from typing import Optional, Union
from uuid import UUID

import orjson
from budmicroframe.commons import logging
from budmicroframe.commons.schemas import ErrorResponse, SuccessResponse
from fastapi import APIRouter, Path, Query, Response
from fastapi.responses import ORJSONResponse
from pydantic import ValidationError

from budmetrics.commons.schemas import BulkCloudEventBase
from budmetrics.observability.schemas import (
    AggregatedMetricsRequest,
    AggregatedMetricsResponse,
    CredentialUsageRequest,
    CredentialUsageResponse,
    EnhancedInferenceDetailResponse,
    GatewayAnalyticsRequest,
    GeographicDataRequest,
    GeographicDataResponse,
    InferenceDetailsMetrics,
    InferenceFeedbackResponse,
    InferenceListRequest,
    InferenceListResponse,
    LatencyDistributionRequest,
    LatencyDistributionResponse,
    MetricsSyncRequest,
    MetricsSyncResponse,
    ObservabilityMetricsRequest,
    ObservabilityMetricsResponse,
    TimeSeriesRequest,
    TimeSeriesResponse,
    TraceDetailResponse,
    TraceListResponse,
    TraceResourceType,
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

    # Enforce batch size limit
    MAX_BATCH_SIZE = 1000
    if len(entries) > MAX_BATCH_SIZE:
        return ErrorResponse(
            message=f"Batch size exceeds maximum limit of {MAX_BATCH_SIZE} entries",
            details={"received": len(entries), "max_allowed": MAX_BATCH_SIZE},
        ).to_http_response()

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
                    inference_metric.api_key_id,  # api_key_id (auth metadata)
                    inference_metric.user_id,  # user_id (auth metadata)
                    inference_metric.api_key_project_id,  # api_key_project_id (auth metadata)
                    inference_metric.error_code,  # error_code
                    inference_metric.error_message,  # error_message
                    inference_metric.error_type,  # error_type
                    inference_metric.status_code,  # status_code
                )
                batch_data.append(inference_data)
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


# New Aggregated Metrics Endpoints
@observability_router.post("/metrics/aggregated", tags=["Aggregated Metrics"])
async def get_aggregated_metrics(request: AggregatedMetricsRequest) -> Response:
    """Get aggregated metrics with server-side calculations.

    This endpoint provides pre-aggregated metrics calculated directly in ClickHouse for
    high performance. Supports grouping by model, project, endpoint, or user and
    includes formatted values with proper units.

    Available metrics:
    - total_requests: Total number of inference requests
    - success_rate: Percentage of successful requests
    - avg_latency, p95_latency, p99_latency: Response time statistics
    - total_tokens, avg_tokens: Token usage statistics
    - total_cost, avg_cost: Cost analysis
    - ttft_avg, ttft_p95, ttft_p99: Time to first token statistics
    - cache_hit_rate: Cache effectiveness
    - throughput_avg: Average tokens per second
    - error_rate: Percentage of failed requests
    - unique_users: Count of distinct users

    Args:
        request (AggregatedMetricsRequest): The aggregation request parameters.

    Returns:
        HTTP response containing aggregated metrics with formatting.
    """
    response: Union[AggregatedMetricsResponse, ErrorResponse]

    try:
        response = await service.get_aggregated_metrics(request)
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        response = ErrorResponse(message=f"Validation error: {str(e)}")
    except Exception as e:
        logger.error(f"Error getting aggregated metrics: {e}")
        response = ErrorResponse(message=f"Error getting aggregated metrics: {str(e)}")

    return response.to_http_response()


@observability_router.post("/metrics/time-series", tags=["Aggregated Metrics"])
async def get_time_series_data(request: TimeSeriesRequest) -> Response:
    """Get time-series data for chart visualization.

    This endpoint provides time-bucketed metrics data optimized for charts and graphs.
    Uses efficient ClickHouse time bucketing functions and supports gap filling for
    smooth chart rendering.

    Supported intervals: 1m, 5m, 15m, 30m, 1h, 6h, 12h, 1d, 1w

    Available metrics:
    - requests: Request count per time bucket
    - success_rate: Success rate percentage over time
    - avg_latency, p95_latency, p99_latency: Latency trends
    - tokens: Token usage over time
    - cost: Cost trends
    - ttft_avg: Time to first token trends
    - cache_hit_rate: Cache performance over time
    - throughput: Throughput trends
    - error_rate: Error rate trends

    Args:
        request (TimeSeriesRequest): The time-series request parameters.

    Returns:
        HTTP response containing time-series data points.
    """
    response: Union[TimeSeriesResponse, ErrorResponse]

    try:
        response = await service.get_time_series_data(request)
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        response = ErrorResponse(message=f"Validation error: {str(e)}")
    except Exception as e:
        logger.error(f"Error getting time-series data: {e}")
        response = ErrorResponse(message=f"Error getting time-series data: {str(e)}")

    return response.to_http_response()


@observability_router.get("/metrics/geography", tags=["Aggregated Metrics"])
async def get_geographic_distribution(
    from_date: datetime = Query(..., description="Start date for the analysis"),
    to_date: Optional[datetime] = Query(None, description="End date for the analysis"),
    group_by: str = Query("country", description="Group by: country, region, city"),
    limit: int = Query(50, description="Maximum number of locations to return"),
    project_id: Optional[UUID] = Query(None, description="Filter by project ID"),
    api_key_project_id: Optional[UUID] = Query(None, description="Filter by API key's project ID (for CLIENT users)"),
    country_codes: Optional[str] = Query(None, description="Comma-separated country codes to filter by"),
) -> Response:
    """Get geographic distribution data from gateway analytics.

    This endpoint analyzes request patterns by geographic location using data from
    the GatewayAnalytics table. Provides insights into where requests are coming
    from and performance by location.

    Grouping options:
    - country: Group by country code
    - region: Group by country and region/state
    - city: Group by country, region, and city

    Args:
        from_date (datetime): Start date for analysis.
        to_date (Optional[datetime]): End date for analysis.
        group_by (str): Geographic grouping level.
        limit (int): Maximum locations to return.
        project_id (Optional[UUID]): Filter by specific project.
        country_codes (Optional[str]): Filter by specific countries.

    Returns:
        HTTP response containing geographic distribution data.
    """
    response: Union[GeographicDataResponse, ErrorResponse]

    try:
        # Build request object
        filters = {}
        if project_id:
            filters["project_id"] = project_id
        if api_key_project_id:
            filters["api_key_project_id"] = api_key_project_id
        if country_codes:
            filters["country_code"] = [code.strip() for code in country_codes.split(",")]

        request = GeographicDataRequest(
            from_date=from_date, to_date=to_date, group_by=group_by, limit=limit, filters=filters if filters else None
        )

        response = await service.get_geographic_data(request)
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        response = ErrorResponse(message=f"Validation error: {str(e)}")
    except Exception as e:
        logger.error(f"Error getting geographic data: {e}")
        response = ErrorResponse(message=f"Error getting geographic data: {str(e)}")

    return response.to_http_response()


@observability_router.post("/metrics/geography", tags=["Aggregated Metrics"])
async def get_geographic_distribution_post(request: GeographicDataRequest) -> Response:
    """Get geographic distribution data from gateway analytics (POST version).

    This endpoint is the POST version that properly handles complex filters including
    lists of project IDs and api_key_project_ids for CLIENT users.

    Args:
        request (GeographicDataRequest): The geographic data request with filters.

    Returns:
        HTTP response containing geographic distribution data.
    """
    response: Union[GeographicDataResponse, ErrorResponse]

    try:
        response = await service.get_geographic_data(request)
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        response = ErrorResponse(message=f"Validation error: {str(e)}")
    except Exception as e:
        logger.error(f"Error getting geographic data: {e}")
        response = ErrorResponse(message=f"Error getting geographic data: {str(e)}")

    return response.to_http_response()


@observability_router.post("/metrics/latency-distribution", tags=["Aggregated Metrics"])
async def get_latency_distribution(request: LatencyDistributionRequest) -> Response:
    """Get latency distribution data with server-side calculations.

    This endpoint provides latency distribution analysis calculated directly in ClickHouse for
    high performance. Supports grouping by model, project, endpoint, or user with
    customizable latency buckets.

    Default latency buckets:
    - 0-100ms: Very fast responses
    - 100-500ms: Fast responses
    - 500-1000ms: Moderate responses
    - 1-2s: Slow responses
    - 2-5s: Very slow responses
    - 5-10s: Extremely slow responses
    - >10s: Timeout-prone responses

    Args:
        request (LatencyDistributionRequest): The latency distribution request parameters.

    Returns:
        HTTP response containing latency distribution data with optional grouping.
    """
    response: Union[LatencyDistributionResponse, ErrorResponse]

    try:
        response = await service.get_latency_distribution(request)
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        response = ErrorResponse(message=f"Validation error: {str(e)}")
    except Exception as e:
        logger.error(f"Error getting latency distribution: {e}")
        response = ErrorResponse(message=f"Error getting latency distribution: {str(e)}")

    return response.to_http_response()


@observability_router.post("/credential-usage", tags=["Observability"])
async def get_credential_usage(request: CredentialUsageRequest) -> Response:
    """Get credential usage statistics.

    This endpoint retrieves usage statistics for API credentials (API keys) including:
    - Last used timestamp for each credential
    - Request count within the specified time window

    Used by budapp to update the last_used_at field for credentials.

    Args:
        request (CredentialUsageRequest): Request with time window and optional credential IDs.

    Returns:
        HTTP response containing credential usage statistics.
    """
    response: Union[CredentialUsageResponse, ErrorResponse]

    try:
        response = await service.get_credential_usage(request)
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        response = ErrorResponse(message=f"Validation error: {str(e)}")
    except Exception as e:
        logger.error(f"Error getting credential usage: {e}")
        response = ErrorResponse(message=f"Error getting credential usage: {str(e)}")

    return response.to_http_response()


@observability_router.post("/metrics-sync", tags=["Observability"])
async def get_metrics_sync(request: MetricsSyncRequest) -> Response:
    """Get unified metrics sync data for both credentials and users.

    This endpoint provides a unified way to sync both credential usage and user usage data.
    It supports two modes:
    - incremental: Returns only entities with recent activity (based on threshold)
    - full: Returns all entities regardless of activity

    Used by budapp to efficiently sync both credential and user usage data in a single call.

    Args:
        request (MetricsSyncRequest): Request with sync mode and parameters.

    Returns:
        HTTP response containing unified metrics sync data.
    """
    response: Union[MetricsSyncResponse, ErrorResponse]

    try:
        response = await service.get_metrics_sync(request)
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        response = ErrorResponse(message=f"Validation error: {str(e)}")
    except Exception as e:
        logger.error(f"Error getting metrics sync: {e}")
        response = ErrorResponse(message=f"Error getting metrics sync: {str(e)}")

    return response.to_http_response()


# OTel Traces Routes
@observability_router.get("/traces", tags=["Traces"])
async def list_traces(
    resource_type: TraceResourceType = Query(..., description="Resource type to filter by"),
    resource_id: str = Query(..., description="Resource ID to filter traces"),
    project_id: UUID = Query(..., description="Project ID to filter traces"),
    from_date: datetime = Query(..., description="Start date for filtering"),
    to_date: datetime = Query(..., description="End date for filtering"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(50, ge=1, le=1000, description="Number of results to return"),
    flatten: bool = Query(False, description="If true, return all spans (root + children) sorted by time"),
) -> Response:
    """List OTel traces filtered by resource type/id and project_id.

    This endpoint retrieves traces from the otel_traces table with support for:
    - Filtering by resource_type and resource_id (from SpanAttributes)
    - Filtering by project_id
    - Date range filtering
    - Pagination (offset/limit)
    - Flatten mode to return all spans (root + children) sorted by time

    Returns root spans (gateway_analytics) matching the filter criteria with
    full trace details including all 22 columns from the otel_traces table.
    When flatten=true, returns all spans for matching traces sorted by timestamp.

    Args:
        resource_type: Type of resource to filter by (e.g., 'prompt')
        resource_id: ID of the resource to filter traces
        project_id: Project ID to filter traces (from SpanAttributes['gateway_analytics.project_id'])
        from_date: Start date for filtering
        to_date: End date for filtering
        offset: Pagination offset (default: 0)
        limit: Number of results to return (default: 50, max: 1000)
        flatten: If true, return all spans (root + children) sorted by time (default: false)

    Returns:
        HTTP response containing paginated trace list with all span details.
    """
    response: Union[TraceListResponse, ErrorResponse]

    try:
        response = await service.list_traces(
            resource_type=resource_type,
            resource_id=resource_id,
            project_id=project_id,
            from_date=from_date,
            to_date=to_date,
            offset=offset,
            limit=limit,
            flatten=flatten,
        )
    except Exception as e:
        logger.error(f"Error listing traces: {e}")
        response = ErrorResponse(message=f"Error listing traces: {str(e)}")

    return response.to_http_response()


@observability_router.get("/traces/{trace_id}", tags=["Traces"])
async def get_trace(
    trace_id: str = Path(..., description="Trace ID to retrieve"),
) -> Response:
    """Get all spans for a single trace.

    This endpoint retrieves all spans for a given trace_id from the otel_traces table.
    Returns spans ordered by timestamp ascending to show trace flow.

    Args:
        trace_id: The trace ID to retrieve all spans for

    Returns:
        HTTP response containing all spans for the trace.
    """
    response: Union[TraceDetailResponse, ErrorResponse]

    try:
        response = await service.get_trace(trace_id=trace_id)
    except Exception as e:
        logger.error(f"Error getting trace: {e}")
        response = ErrorResponse(message=f"Error getting trace: {str(e)}")

    return response.to_http_response()
