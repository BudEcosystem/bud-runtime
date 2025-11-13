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

"""Services for responses module - OpenAI-compatible API."""

import json
import logging
from typing import Any, Dict, Optional

from fastapi.responses import StreamingResponse
from openai.types.responses import ResponsePrompt
from pydantic import ValidationError

from budprompt.commons.exceptions import ClientException, OpenAIResponseException
from budprompt.shared.redis_service import RedisService

from ..prompt.openai_response_formatter import extract_validation_error_details
from ..prompt.schemas import PromptExecuteData
from ..prompt.services import PromptExecutorService
from .schemas import ResponsePromptParam


logger = logging.getLogger(__name__)


class ResponsesService:
    """Service for handling responses API operations.

    This service provides OpenAI-compatible API functionality for
    executing prompt templates stored in Redis.
    """

    def __init__(self):
        """Initialize the ResponsesService."""
        self.redis_service = RedisService()

    async def execute_prompt(
        self, prompt_params: ResponsePromptParam, input: Optional[str] = None, api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute prompt using template from Redis.

        Args:
            prompt_params: Prompt parameters including id, version, and variables
            input: Optional input text for the prompt
            api_key: Optional API key for authorization

        Returns:
            Dictionary containing the execution result

        Raises:
            OpenAIResponseException: OpenAI-compatible exception with status code and error details
        """
        try:
            if prompt_params.variables and input:
                raise OpenAIResponseException(
                    status_code=400,
                    message="Please provide either variables or input.",
                    code="invalid_request",
                )

            # Extract parameters
            prompt_id = prompt_params.id
            version = prompt_params.version

            # Determine Redis key based on version
            if version:
                # Get specific version
                redis_key = f"prompt:{prompt_id}:v{version}"
            else:
                # Get default version
                default_key = f"prompt:{prompt_id}:default_version"
                redis_key = await self.redis_service.get(default_key)

                if not redis_key:
                    logger.debug(f"Default version not found for prompt_id: {prompt_id}")
                    raise OpenAIResponseException(
                        status_code=404,
                        message=f"Prompt template not found: {prompt_id}",
                        code="not_found",
                    )

            # Fetch prompt configuration from Redis
            config_json = await self.redis_service.get(redis_key)

            if not config_json:
                logger.debug(f"Prompt configuration not found for key: {redis_key}")
                raise OpenAIResponseException(
                    status_code=404,
                    message=f"Prompt template not found: {prompt_id}" + (f" version {version}" if version else ""),
                    code="not_found",
                )

            # Parse the configuration
            try:
                config_data = json.loads(config_json)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse prompt configuration: {str(e)}")
                raise OpenAIResponseException(
                    status_code=500,
                    message="Invalid prompt configuration format",
                    code="internal_error",
                ) from e

            # Execute the prompt
            prompt_execute_data = PromptExecuteData.model_validate(config_data)
            logger.debug(f"Config data for prompt: {prompt_id}: {prompt_execute_data}")

            input_data = prompt_params.variables if prompt_params.variables else input

            result = await PromptExecutorService().execute_prompt(
                prompt_execute_data,
                input_data,
                api_key=api_key,
            )

            # Log successful execution
            logger.info(f"Successfully executed prompt: {prompt_id}")

            if prompt_execute_data.stream:
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
                # Add prompt info to non-streaming OpenAI-formatted response
                result = result.model_copy(
                    update={
                        "prompt": ResponsePrompt(
                            id=prompt_id,
                            variables=prompt_params.variables,
                            version=version,
                        )
                    }
                )
                return result

        except ValidationError as e:
            logger.warning(f"Validation error during response creation: {str(e)}")
            message, param, code = extract_validation_error_details(e)
            raise OpenAIResponseException(
                status_code=400,
                message=message,
                param=param,
                code=code,
            ) from e

        except ClientException as e:
            logger.warning(f"Client error during response creation: {e.message}")
            # Extract param and code from ClientException params if available
            param = None
            code = None
            if e.params:
                if isinstance(e.params, dict):
                    param = e.params.get("param")
                    code = e.params.get("code")
                elif isinstance(e.params, str):
                    param = e.params

            raise OpenAIResponseException(
                status_code=e.status_code,
                message=e.message,
                param=param,
                code=code,
            ) from e

        except OpenAIResponseException:
            # Re-raise OpenAIResponseException as-is (from our own code above)
            raise

        except Exception as e:
            logger.error(f"Unexpected error during prompt execution: {str(e)}")
            raise OpenAIResponseException(
                status_code=500,
                message="An unexpected error occurred during prompt execution",
                code="internal_error",
            ) from e
