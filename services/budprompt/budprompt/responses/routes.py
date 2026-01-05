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

from typing import Any, Dict, Union

from budmicroframe.commons import logging
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from opentelemetry.propagate import extract

from budprompt.commons.exceptions import OpenAIResponseException

from .schemas import OpenAIError, OpenAIResponse, OpenAIResponsesError, ResponseCreateRequest
from .services import ResponsesService


logger = logging.get_logger(__name__)

# NOTE: Optional Bearer token security (auto_error=False makes it optional)
security = HTTPBearer()

# Responses Router
responses_router = APIRouter(
    prefix="/v1/responses",
    tags=["responses"],
)


@responses_router.post(
    "/",
    response_model=Union[OpenAIResponse, OpenAIResponsesError, Dict[str, Any]],
    summary="Create response using prompt template",
    description="Execute a prompt template with variables (OpenAI-compatible)",
    responses={
        200: {
            "description": "Prompt executed successfully - returns OpenAI-compatible response format",
        },
        400: {"description": "Bad request - invalid parameters"},
        404: {"description": "Prompt template not found"},
        500: {"description": "Internal server error"},
    },
)
async def create_response(
    http_request: Request,
    request: ResponseCreateRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),  # noqa: B008
) -> Union[OpenAIResponse, OpenAIResponsesError, Dict[str, Any]]:
    """Create a response using a prompt template.

    This endpoint is compatible with OpenAI's responses API format.
    It fetches prompt templates from Redis and executes them with
    the provided variables.

    Args:
        http_request: The FastAPI request object for accessing headers
        request: The prompt request containing id, variables, and optional version
        credentials: Optional bearer token credentials for API authentication

    Returns:
        OpenAIResponse on success or JSONResponse with error status code and
        OpenAI-compatible error format on failure
    """
    logger.debug("Received response creation request: %s", request.model_dump(mode="json"))

    # Extract trace context from incoming request headers for distributed tracing
    # This enables parent-child span relationships with upstream services (e.g., budgateway)
    carrier = dict(http_request.headers)
    trace_context = extract(carrier)

    # Extract bearer token from credentials if present
    api_key = credentials.credentials if credentials else None

    # Create service instance
    service = ResponsesService()

    try:
        # Execute the prompt with optional authorization and trace context
        result = await service.execute_prompt(
            prompt_params=request.prompt,
            input=request.input,
            api_key=api_key,
            trace_context=trace_context,
        )
        return result

    except OpenAIResponseException as e:
        # Build OpenAI-compatible error response
        error_response = OpenAIResponsesError(
            error=OpenAIError(
                message=e.message,
                type=e.type,
                param=e.param,
                code=e.code,
            )
        )
        return JSONResponse(status_code=e.status_code, content=error_response.model_dump(mode="json"))
