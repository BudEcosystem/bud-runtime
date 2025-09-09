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

"""API routes for responses module - OpenAI-compatible API."""

import logging
from typing import Union

from budmicroframe.commons.schemas import ErrorResponse
from fastapi import APIRouter, status

from budprompt.commons.exceptions import ClientException

from .schemas import ResponseCreateRequest, ResponsePromptResponse
from .services import ResponsesService


logger = logging.getLogger(__name__)

# Responses Router
responses_router = APIRouter(
    prefix="/v1/responses",
    tags=["responses"],
)


@responses_router.post(
    "/",
    response_model=Union[ResponsePromptResponse, ErrorResponse],
    summary="Create response using prompt template",
    description="Execute a prompt template with variables (OpenAI-compatible)",
    responses={
        200: {
            "description": "Prompt executed successfully",
            "model": ResponsePromptResponse,
        },
        400: {"description": "Bad request - invalid parameters"},
        404: {"description": "Prompt template not found"},
        500: {"description": "Internal server error"},
    },
)
async def create_response(
    request: ResponseCreateRequest,
) -> Union[ResponsePromptResponse, ErrorResponse]:
    """Create a response using a prompt template.

    This endpoint is compatible with OpenAI's responses API format.
    It fetches prompt templates from Redis and executes them with
    the provided variables.

    Args:
        request: The prompt request containing id, variables, and optional version

    Returns:
        ResponsePromptResponse with execution result or ErrorResponse on failure
    """
    try:
        logger.info(f"Received response creation request for prompt: {request.prompt.id}")

        # Create service instance
        service = ResponsesService()

        # Execute the prompt
        result = await service.execute_prompt(
            prompt_params=request.prompt,
            input=request.input,
        )

        return ResponsePromptResponse(
            code=status.HTTP_200_OK, message="Prompt executed successfully", data=result
        ).to_http_response()

    except ClientException as e:
        logger.warning(f"Client error during response creation: {e.message}")
        return ErrorResponse(
            code=e.status_code,
            message=e.message,
            param=e.params,
        ).to_http_response()

    except Exception as e:
        logger.error(f"Unexpected error during response creation: {str(e)}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="An unexpected error occurred during response creation",
        ).to_http_response()
