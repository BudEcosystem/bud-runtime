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

import uuid
from typing import Union

from budmicroframe.commons import logging
from budmicroframe.commons.api_utils import pubsub_api_endpoint
from budmicroframe.commons.schemas import ErrorResponse, SuccessResponse
from fastapi import APIRouter, Query, Response

from .cloud_service import CloudModelExtractionService
from .schemas import (
    CloudModelExtractionRequest,
    CloudModelExtractionResponse,
    LicenseFAQRequest,
    ModelExtractionRequest,
    ModelSecurityScanRequest,
)
from .services import LicenseFAQService, ModelDeleteService, ModelExtractionService, ModelSecurityScanService
from .workflows import (  # noqa
    LicenseFAQWorkflows,
    ModelExtractionETAObserverWorkflows,
    ModelExtractionWorkflows,
    ModelSecurityScanWorkflows,
)


logger = logging.get_logger(__name__)

model_info_router = APIRouter(prefix="/model-info")


@model_info_router.post("/extract", tags=["Model Extraction"])
@pubsub_api_endpoint(request_model=ModelExtractionRequest)
async def perform_model_extraction(request: ModelExtractionRequest) -> Response:
    """Run a model extraction workflow based on the provided configuration.

    This endpoint processes the model extraction request and returns
    recommendations for deployment strategies based on the specified
    parameters.

    Args:
        request (ModelExtractionRequest): The model extraction request
        containing model URI, input/output tokens, concurrency,
        and target performance metrics.

    Returns:
        HTTP response containing the model extraction results.
    """
    response: Union[SuccessResponse, ErrorResponse]
    if request.debug:
        try:
            logger.info("Running model extraction in debug mode", request.model_dump())
            response = ModelExtractionService().__call__(request, workflow_id=str(uuid.uuid4()))
        except Exception as e:
            logger.exception("Error running model extraction: %s", str(e))
            response = ErrorResponse(message="Error running model extraction", code=500)
    else:
        response = await ModelExtractionWorkflows().__call__(request)

    return response.to_http_response()


@model_info_router.post("/scan", tags=["Model Security Scan"])
@pubsub_api_endpoint(request_model=ModelSecurityScanRequest)
async def perform_model_security_scan(request: ModelSecurityScanRequest) -> Response:
    """Run a model security scan workflow based on the provided configuration.

    This endpoint processes the model security scan request and returns
    recommendations for deployment strategies based on the specified
    parameters.

    Args:
        request (ModelSecurityScanRequest): The model security scan request
        containing model path.

    Returns:
        HTTP response containing the model security scan results.
    """
    response: Union[SuccessResponse, ErrorResponse]
    if request.debug:
        try:
            logger.info("Running model security scan in debug mode", request.model_dump())
            response = ModelSecurityScanService().__call__(request, workflow_id=str(uuid.uuid4()))
        except Exception as e:
            logger.exception("Error running model security scan: %s", str(e))
            response = ErrorResponse(message="Error running model security scan", code=500)
    else:
        response = await ModelSecurityScanWorkflows().__call__(request)

    return response.to_http_response()


@model_info_router.post("/cloud-model/extract", tags=["Cloud Model Extraction"])
async def perform_cloud_model_extraction(request: CloudModelExtractionRequest) -> Response:
    """Extract cloud model information from external service.

    This endpoint fetches model details from an external service (like BudConnect)
    and saves the information to the database immediately without workflows.

    Args:
        request (CloudModelExtractionRequest): The cloud model extraction request
        containing model URI and optional external service URL.

    Returns:
        HTTP response containing the cloud model extraction results.
    """
    response: Union[CloudModelExtractionResponse, ErrorResponse]
    try:
        logger.info("Performing cloud model extraction for: %s", request.model_uri)
        response = await CloudModelExtractionService().__call__(request)
    except Exception as e:
        logger.exception("Error extracting cloud model: %s", str(e))
        response = ErrorResponse(message=f"Error extracting cloud model: {str(e)}", code=500)

    return response.to_http_response()


@model_info_router.delete("/local-models", tags=["Model Delete"])
async def delete_model(
    path: str = Query(..., description="The path to the model to delete"),
) -> Response:
    """Delete a model from the local filesystem.

    Args:
        path (str): The path to the model to delete.

    Returns:
        HTTP response containing the result of the model deletion.
    """
    response: Union[SuccessResponse, ErrorResponse]
    try:
        is_deleted = ModelDeleteService().delete_model(path)
        if is_deleted:
            response = SuccessResponse(message="Model deleted successfully")
        else:
            response = ErrorResponse(message="Failed to delete the model", code=500)
    except Exception as e:
        logger.exception("Error deleting model: %s", str(e))
        response = ErrorResponse(message="Error deleting model", code=500)

    return response.to_http_response()


@model_info_router.post("/license-faq", tags=["License FAQ"])
@pubsub_api_endpoint(request_model=LicenseFAQRequest)
async def fetch_license_faqs(request: LicenseFAQRequest) -> Response:
    """Fetch license FAQs based on the provided license source.

    This endpoint processes the license FAQ request and returns
    the FAQs retrieved from the specified source (URL or file path).

    Args:
        request (LicenseFAQRequest): The request containing the license source.

    Returns:
        HTTP response containing the license FAQs.
    """
    response: Union[SuccessResponse, ErrorResponse]
    if request.debug:
        try:
            logger.info("Fetching license FAQs in debug mode", request.model_dump())
            response = LicenseFAQService().__call__(request, workflow_id=str(uuid.uuid4()))
        except Exception as e:
            logger.exception("Error fetching license FAQs: %s", str(e))
            response = ErrorResponse(message="Error fetching license FAQs", code=500)
    else:
        response = await LicenseFAQWorkflows().__call__(request)

    return response.to_http_response()
