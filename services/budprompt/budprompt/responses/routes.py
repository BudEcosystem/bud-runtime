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
from fastapi import APIRouter

from ..prompt.schemas import PromptExecuteResponse
from .schemas import ResponseCreateRequest
from .services import ResponsesService


logger = logging.getLogger(__name__)

# Responses Router
responses_router = APIRouter(
    prefix="/v1/responses",
    tags=["responses"],
)


@responses_router.post(
    "/",
    response_model=Union[PromptExecuteResponse, ErrorResponse],
    summary="Create response using prompt template",
    description="Execute a prompt template with variables (OpenAI-compatible)",
    responses={
        200: {
            "description": "Prompt executed successfully",
            "model": PromptExecuteResponse,
        },
        400: {"description": "Bad request - invalid parameters"},
        404: {"description": "Prompt template not found"},
        500: {"description": "Internal server error"},
    },
)
async def create_response(
    request: ResponseCreateRequest,
) -> Union[PromptExecuteResponse, ErrorResponse]:
    """Create a response using a prompt template.

    This endpoint is compatible with OpenAI's responses API format.
    It fetches prompt templates from Redis and executes them with
    the provided variables.

    Args:
        request: The prompt request containing id, variables, and optional version

    Returns:
        PromptExecuteResponse with execution result or ErrorResponse on failure
    """
    logger.info(f"Received response creation request for prompt: {request.prompt.id}")

    # Create service instance
    service = ResponsesService()

    # Execute the prompt
    result = await service.execute_prompt(
        prompt_params=request.prompt,
        input=request.input,
    )

    return result
