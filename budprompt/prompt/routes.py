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

from fastapi import APIRouter, HTTPException, status

from .schemas import PromptExecuteRequest, PromptExecuteResponse
from .services import PromptExecutorService


logger = logging.getLogger(__name__)

# Prompt Router
prompt_router = APIRouter(
    prefix="/prompt",
    tags=["prompt"],
)


@prompt_router.post(
    "/execute",
    response_model=PromptExecuteResponse,
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
) -> PromptExecuteResponse:
    """Execute a prompt with structured input and output.

    Args:
        request: The prompt execution request
        service: The prompt executor service

    Returns:
        The prompt execution response

    Raises:
        HTTPException: If the request is invalid or execution fails
    """
    try:
        logger.info("Received prompt execution request")

        # Execute the prompt
        response = await PromptExecutorService().execute_prompt(request)

        # If execution failed, return appropriate status
        if not response.success:
            logger.error(f"Prompt execution failed: {response.error}")
            # Still return 200 OK with success=false in response
            # This allows client to handle structured error

        return response

    except ValueError as e:
        logger.error(f"Invalid request: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during prompt execution: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during prompt execution",
        )
