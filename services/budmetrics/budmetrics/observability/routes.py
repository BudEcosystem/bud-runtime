from typing import Union

import orjson
from budmicroframe.commons import logging
from budmicroframe.commons.schemas import ErrorResponse, SuccessResponse
from fastapi import APIRouter, Response
from pydantic import ValidationError

from budmetrics.commons.schemas import BulkCloudEventBase
from budmetrics.observability.schemas import (
    InferenceDetailsMetrics,
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
                    response_analysis_str = orjson.dumps(
                        inference_metric.response_analysis
                    ).decode("utf-8")

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
            message_parts.append(
                f"Successfully inserted {insertion_results['inserted']} new records"
            )

        if insertion_results["duplicates"] > 0:
            message_parts.append(
                f"Skipped {insertion_results['duplicates']} duplicate records"
            )

        if validation_errors:
            message_parts.append(f"Failed to validate {len(validation_errors)} entries")

        # Determine overall status
        if (
            insertion_results["inserted"] == 0
            and insertion_results["duplicates"] == 0
            and not validation_errors
        ):
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
                    response_data["details"][
                        "note"
                    ] = f"Showing first 10 of {len(insertion_results['duplicate_ids'])} duplicate IDs"

            if validation_errors:
                response_data["details"]["validation_errors"] = validation_errors[:10]
                if len(validation_errors) > 10:
                    response_data["details"][
                        "validation_note"
                    ] = f"Showing first 10 of {len(validation_errors)} validation errors"

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
