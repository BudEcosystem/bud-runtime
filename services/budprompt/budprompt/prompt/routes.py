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
from typing import Union

from budmicroframe.commons.schemas import ErrorResponse
from fastapi import APIRouter, status
from fastapi.responses import StreamingResponse

from ..commons.exceptions import ClientException
from .schemas import PromptExecuteRequest, PromptExecuteResponse
from .services import PromptExecutorService


logger = logging.getLogger(__name__)

# Create a global service instance
prompt_service = PromptExecutorService()

# Prompt Router
prompt_router = APIRouter(
    prefix="/prompt",
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
        result = await prompt_service.execute_prompt(request)

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
