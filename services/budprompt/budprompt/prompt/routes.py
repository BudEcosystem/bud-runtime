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

"""API routes for the prompt module."""

import logging
import uuid
from typing import Optional, Union

from budmicroframe.commons.api_utils import pubsub_api_endpoint
from budmicroframe.commons.schemas import ErrorResponse, SuccessResponse
from fastapi import APIRouter, Query, Request, Response, status
from fastapi.responses import StreamingResponse

from ..commons.exceptions import ClientException
from .schemas import (
    PromptCleanupRequest,
    PromptConfigCopyRequest,
    PromptConfigCopyResponse,
    PromptConfigGetRawResponse,
    PromptConfigGetResponse,
    PromptConfigRequest,
    PromptConfigResponse,
    PromptExecuteRequest,
    PromptExecuteResponse,
    PromptSchemaRequest,
    PromptSetDefaultVersionRequest,
)
from .services import PromptCleanupService, PromptConfigurationService, PromptExecutorService, PromptService
from .workflows import PromptCleanupWorkflow, PromptSchemaWorkflow


logger = logging.getLogger(__name__)

# Create a global service instance
prompt_service = PromptExecutorService()

# Prompt Router
prompt_router = APIRouter(
    prefix="/v1/prompt",
    tags=["prompt"],
)


@prompt_router.post(
    "/execute",
    response_model=Union[PromptExecuteResponse, ErrorResponse],
    summary="Execute a prompt",
    description="Execute a prompt with structured input and output schemas",
    responses={
        200: {
            "description": "Successful execution",
            "model": PromptExecuteResponse,
        },
        400: {"description": "Invalid request"},
        422: {"description": "Unprocessable entity"},
        500: {"description": "Internal server error"},
    },
)
async def execute_prompt(
    request: PromptExecuteRequest,
) -> Union[PromptExecuteResponse, ErrorResponse, StreamingResponse]:
    """Execute a prompt with structured input and output.

    Args:
        request: The prompt execution request
        service: The prompt executor service

    Returns:
        The prompt execution response (regular or streaming)

    Raises:
        HTTPException: If the request is invalid or execution fails
    """
    try:
        logger.info("Received prompt execution request")

        # Execute the prompt (handles both streaming and non-streaming)
        result = await prompt_service.execute_prompt_deprecated(request)

        # Check if streaming is requested
        if request.stream:
            logger.info("Streaming response requested")
            return StreamingResponse(
                result,
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",  # Disable Nginx buffering
                },
            )
        else:
            return PromptExecuteResponse(
                code=status.HTTP_200_OK,
                message="Prompt executed successfully",
                data=result,
            ).to_http_response()

    except ClientException as e:
        return ErrorResponse(
            code=e.status_code,
            message=e.message,
            param=e.params,
        ).to_http_response()
    except Exception as e:
        logger.error(f"Unexpected error during prompt execution: {str(e)}")
        return ErrorResponse(
            code=500,
            message="An unexpected error occurred during prompt execution",
        ).to_http_response()


@prompt_router.post("/prompt-schema")
@pubsub_api_endpoint(request_model=PromptSchemaRequest)
async def perform_prompt_schema(request: PromptSchemaRequest) -> Response:
    """Run a prompt schema validation workflow.

    This endpoint processes the prompt schema request, validates the schema,
    generates validation codes, and stores the configuration in Redis.

    Args:
        request (PromptSchemaRequest): The prompt schema request
        containing schema and validation prompts.

    Returns:
        HTTP response containing the prompt schema validation results.
    """
    response: Union[SuccessResponse, ErrorResponse]

    # Set default uuid
    if request.prompt_id is None:
        request.prompt_id = str(uuid.uuid4())

    if request.debug:
        try:
            logger.debug("Running prompt schema validation in debug mode", request.model_dump())
            response = PromptConfigurationService().__call__(request, workflow_id=str(uuid.uuid4()))
        except Exception as e:
            logger.exception("Error running prompt schema validation: %s", str(e))
            response = ErrorResponse(message="Error running prompt schema validation", code=500)
    else:
        response = await PromptSchemaWorkflow().__call__(request)

    return response.to_http_response()


@prompt_router.post("/prompt-cleanup")
@pubsub_api_endpoint(request_model=PromptCleanupRequest)
async def perform_prompt_cleanup(request: PromptCleanupRequest) -> Response:
    """Run a prompt cleanup workflow.

    This endpoint processes MCP resource cleanup for temporary prompts.
    It can cleanup specific prompts or scan for expired prompts.

    Args:
        request (PromptCleanupRequest): The cleanup request containing
        optional list of prompts to cleanup. Empty list means cleanup expired prompts.

    Returns:
        HTTP response containing the cleanup results.
    """
    response: Union[SuccessResponse, ErrorResponse]

    if request.debug:
        try:
            logger.debug("Running prompt cleanup in debug mode", request.model_dump())
            response = PromptCleanupService().__call__(request, workflow_id=str(uuid.uuid4()))
        except Exception as e:
            logger.exception("Error running prompt cleanup: %s", str(e))
            response = ErrorResponse(message="Error running prompt cleanup", code=500)
    else:
        response = await PromptCleanupWorkflow().__call__(request)

    return response.to_http_response()


@prompt_router.post(
    "/prompt-cleanup-cron",
    response_model=Union[SuccessResponse, ErrorResponse],
    summary="Scheduled prompt cleanup (Dapr cron trigger)",
    description="Periodic cleanup of expired MCP resources triggered by Dapr cron binding",
    responses={
        200: {
            "description": "Cleanup executed successfully",
            "model": SuccessResponse,
        },
        500: {"description": "Internal server error"},
    },
)
async def perform_prompt_cleanup_cron(request: Request) -> Response:
    """Run scheduled prompt cleanup workflow triggered by Dapr cron binding.

    This endpoint is invoked periodically by the Dapr cron scheduler to cleanup
    expired MCP resources. It automatically scans for and removes temporary
    prompts that have exceeded their TTL.

    The endpoint accepts an empty POST request from the Dapr cron binding.
    For manual testing, you can also call this endpoint directly.

    Returns:
        HTTP response containing the cleanup results.
    """
    response: Union[SuccessResponse, ErrorResponse]

    try:
        logger.info("Scheduled prompt cleanup triggered by Dapr cron binding")

        # Create request with empty prompts list = cleanup expired prompts
        cleanup_request = PromptCleanupRequest(prompts=[])

        # Execute cleanup workflow
        response = await PromptCleanupWorkflow().__call__(cleanup_request)

    except Exception as e:
        logger.exception("Error running scheduled prompt cleanup: %s", str(e))
        response = ErrorResponse(message="Error running scheduled prompt cleanup", code=500)

    return response.to_http_response()


@prompt_router.post(
    "/prompt-config",
    response_model=Union[PromptConfigResponse, ErrorResponse],
    summary="Save or update prompt configuration",
    description="Save or update prompt configuration in Redis with partial updates support",
    responses={
        200: {
            "description": "Configuration saved successfully",
            "model": PromptConfigResponse,
        },
        400: {"description": "Invalid request"},
        500: {"description": "Internal server error"},
    },
)
async def save_prompt_config(
    request: PromptConfigRequest,
) -> Union[PromptConfigResponse, ErrorResponse]:
    """Save or update prompt configuration.

    Args:
        request: The prompt configuration request

    Returns:
        The prompt configuration response with prompt_id

    Raises:
        HTTPException: If the request is invalid or saving fails
    """
    # Set default uuid
    if request.prompt_id is None:
        request.prompt_id = str(uuid.uuid4())

    try:
        logger.info(f"Received prompt configuration request for prompt_id: {request.prompt_id}")

        # Create service instance
        prompt_service = PromptService()

        # Save the configuration
        result = await prompt_service.save_prompt_config(request)

        return result.to_http_response()

    except ClientException as e:
        return ErrorResponse(
            code=e.status_code,
            message=e.message,
            param=e.params,
        ).to_http_response()
    except Exception as e:
        logger.error(f"Unexpected error during prompt configuration: {str(e)}")
        return ErrorResponse(
            code=500,
            message="An unexpected error occurred during prompt configuration",
        ).to_http_response()


@prompt_router.get(
    "/prompt-config/{prompt_id}",
    response_model=Union[PromptConfigGetResponse, ErrorResponse],
    summary="Get prompt configuration",
    description="Retrieve prompt configuration from Redis by prompt_id",
    responses={
        200: {
            "description": "Configuration retrieved successfully",
            "model": PromptConfigGetResponse,
        },
        404: {"description": "Configuration not found"},
        500: {"description": "Internal server error"},
    },
)
async def get_prompt_config(
    prompt_id: str,
    version: Optional[int] = Query(None, description="Version of the configuration to retrieve", ge=1),
    raw_data: bool = Query(False, description="Return raw Redis data without Pydantic processing"),
) -> Union[PromptConfigGetResponse, PromptConfigGetRawResponse, ErrorResponse]:
    """Get prompt configuration by ID.

    Args:
        prompt_id: The unique identifier of the prompt configuration
        version: Optional version number to retrieve specific version

    Returns:
        The prompt configuration data

    Raises:
        HTTPException: If configuration not found or retrieval fails
    """
    try:
        logger.info(f"Retrieving prompt configuration for prompt_id: {prompt_id}, version: {version}")

        # Create service instance
        prompt_service = PromptService()

        # Get the configuration
        result = await prompt_service.get_prompt_config(prompt_id, version, raw_data)

        return result.to_http_response()

    except ClientException as e:
        return ErrorResponse(
            code=e.status_code,
            message=e.message,
            param=e.params,
        ).to_http_response()
    except Exception as e:
        logger.error(f"Unexpected error during prompt configuration retrieval: {str(e)}")
        return ErrorResponse(
            code=500,
            message="An unexpected error occurred during prompt configuration retrieval",
        ).to_http_response()


@prompt_router.post(
    "/copy-config",
    response_model=Union[PromptConfigCopyResponse, ErrorResponse],
    summary="Copy prompt configuration",
    description="Copy a specific version of prompt configuration with replace or merge options",
    responses={
        200: {
            "description": "Configuration copied successfully",
            "model": PromptConfigCopyResponse,
        },
        400: {"description": "Invalid request"},
        404: {"description": "Source configuration not found"},
        500: {"description": "Internal server error"},
    },
)
async def copy_prompt_config(
    request: PromptConfigCopyRequest,
) -> Union[PromptConfigCopyResponse, ErrorResponse]:
    """Copy a specific version of prompt configuration from source to target prompt_id.

    Supports two modes:
    - replace=true: Complete replacement of target configuration
    - replace=false: Merge only fields present in source into existing target

    Args:
        request: The copy configuration request

    Returns:
        The copy configuration response

    Raises:
        HTTPException: If source not found or copy fails
    """
    try:
        logger.info(
            f"Copying prompt config from {request.source_prompt_id}:v{request.source_version} "
            f"to {request.target_prompt_id}:v{request.target_version} (replace={request.replace})"
        )

        # Create service instance
        prompt_service = PromptService()

        # Copy the configuration
        result = await prompt_service.copy_prompt_config(request)

        return result.to_http_response()

    except ClientException as e:
        return ErrorResponse(
            code=e.status_code,
            message=e.message,
        ).to_http_response()
    except Exception as e:
        logger.error(f"Unexpected error during prompt configuration copy: {str(e)}")
        return ErrorResponse(
            code=500,
            message="An unexpected error occurred during prompt configuration copy",
        ).to_http_response()


@prompt_router.post(
    "/set-default-version",
    response_model=Union[SuccessResponse, ErrorResponse],
    summary="Set default version for prompt configuration",
    description="Set a specific version as the default for a prompt configuration",
    responses={
        200: {
            "description": "Default version set successfully",
            "model": SuccessResponse,
        },
        400: {"description": "Invalid request"},
        404: {"description": "Version not found"},
        500: {"description": "Internal server error"},
    },
)
async def set_default_version(
    request: PromptSetDefaultVersionRequest,
) -> Union[SuccessResponse, ErrorResponse]:
    """Set a specific version as the default for a prompt configuration.

    Validates that the specified version exists before setting it as default.

    Args:
        request: The set default version request

    Returns:
        Success response indicating the operation completed

    Raises:
        HTTPException: If version not found or operation fails
    """
    try:
        logger.debug(f"Setting version {request.version} as default for prompt_id: {request.prompt_id}")

        # Create service instance
        prompt_service = PromptService()

        # Set the default version
        result = await prompt_service.set_default_version(request.prompt_id, request.version)

        return result.to_http_response()

    except ClientException as e:
        return ErrorResponse(
            code=e.status_code,
            message=e.message,
        ).to_http_response()
    except Exception as e:
        logger.error(f"Unexpected error during set default version: {str(e)}")
        return ErrorResponse(
            code=500,
            message="An unexpected error occurred during set default version",
        ).to_http_response()


@prompt_router.delete(
    "/prompt-config/{prompt_id}",
    response_model=Union[SuccessResponse, ErrorResponse],
    summary="Delete prompt configuration",
    description="Delete a specific version or all versions of a prompt configuration",
    responses={
        200: {
            "description": "Configuration deleted successfully",
            "model": SuccessResponse,
        },
        400: {"description": "Cannot delete default version"},
        404: {"description": "Configuration not found"},
        500: {"description": "Internal server error"},
    },
)
async def delete_prompt_config(
    prompt_id: str,
    version: Optional[int] = Query(
        None, description="Specific version to delete. If not provided, deletes all versions", ge=1
    ),
) -> Union[SuccessResponse, ErrorResponse]:
    """Delete prompt configuration(s).

    If version is provided, deletes only that specific version (unless it's the default).
    If version is not provided, deletes all versions and the default pointer.

    Args:
        prompt_id: The prompt ID to delete
        version: Optional specific version to delete

    Returns:
        Success response indicating what was deleted

    Raises:
        HTTPException: If configuration not found or trying to delete default version
    """
    try:
        if version:
            logger.debug(f"Deleting version {version} for prompt_id: {prompt_id}")
        else:
            logger.debug(f"Deleting all configurations for prompt_id: {prompt_id}")

        # Create service instance
        prompt_service = PromptService()

        # Delete the configuration(s)
        result = await prompt_service.delete_prompt_config(prompt_id, version)

        return result.to_http_response()

    except ClientException as e:
        return ErrorResponse(
            code=e.status_code,
            message=e.message,
        ).to_http_response()
    except Exception as e:
        logger.error(f"Unexpected error during delete prompt configuration: {str(e)}")
        return ErrorResponse(
            code=500,
            message="An unexpected error occurred during delete prompt configuration",
        ).to_http_response()
