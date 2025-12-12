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
from typing import Any, Dict, List, Optional, Union

from budmicroframe.commons import logging
from fastapi.responses import StreamingResponse
from openai.types.responses import ResponseInputItem
from opentelemetry import context, trace
from opentelemetry.trace import Status, StatusCode
from pydantic import ValidationError

from budprompt.commons.constants import ErrorAttributes, GenAIAttributes
from budprompt.commons.exceptions import ClientException, OpenAIResponseException
from budprompt.shared.otel import otel_manager
from budprompt.shared.redis_service import RedisService

from ..prompt.openai_response_formatter import extract_validation_error_details
from ..prompt.schemas import PromptExecuteData
from ..prompt.services import PromptExecutorService
from .schemas import BudResponsePrompt


logger = logging.get_logger(__name__)


class ResponsesService:
    """Service for handling responses API operations.

    This service provides OpenAI-compatible API functionality for
    executing prompt templates stored in Redis.
    """

    def __init__(self):
        """Initialize the ResponsesService."""
        self.redis_service = RedisService()

    async def _create_streaming_generator(self, result, span, context_token):
        """Wrap streaming generator to manage span lifecycle.

        The span stays open during streaming and closes when the generator
        is exhausted or encounters an error.

        Args:
            result: The async generator from prompt execution
            span: The OpenTelemetry span to manage
            context_token: The context token from context.attach()

        Yields:
            Chunks from the original generator
        """
        try:
            async for chunk in result:
                yield chunk
        except Exception as e:
            span.record_exception(e)
            span.set_attribute(ErrorAttributes.TYPE, type(e).__name__)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            raise
        finally:
            context.detach(context_token)
            span.end()

    async def execute_prompt(
        self,
        prompt_params: BudResponsePrompt,
        input: Optional[Union[str, List[ResponseInputItem]]] = None,
        api_key: Optional[str] = None,
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
        tracer = otel_manager.get_tracer(__name__)

        # NOTE: Use manual span management to support streaming
        # For streaming, we need the span to stay open until streaming completes
        span = tracer.start_span("invoke_agent budprompt")

        # Set span as current context so child spans (Pydantic AI) attach to it
        ctx = trace.set_span_in_context(span)
        context_token = context.attach(ctx)

        # Set attributes using semantic conventions
        span.set_attribute(GenAIAttributes.OPERATION_NAME, "invoke_agent")
        span.set_attribute(GenAIAttributes.PROMPT_ID, prompt_params.id)
        span.set_attribute(GenAIAttributes.PROMPT_VERSION, prompt_params.version or "default")
        span.set_attribute(
            GenAIAttributes.PROMPT_VARIABLES,
            json.dumps(prompt_params.variables) if prompt_params.variables else "null",
        )
        span.set_attribute(
            GenAIAttributes.INPUT_MESSAGES,
            json.dumps(input)
            if isinstance(input, str)
            else json.dumps([item.model_dump() for item in input])
            if input
            else "null",
        )

        # Track if streaming (span cleanup handled by generator)
        is_streaming = False

        try:
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
                    logger.error("Default version not found for prompt_id: %s", prompt_id)
                    raise OpenAIResponseException(
                        status_code=404,
                        message=f"Prompt template not found: {prompt_id}",
                        code="not_found",
                    )

            # Fetch prompt configuration from Redis
            config_json = await self.redis_service.get(redis_key)

            if not config_json:
                logger.error("Prompt configuration not found for key: %s", redis_key)
                raise OpenAIResponseException(
                    status_code=404,
                    message=f"Prompt template not found: {prompt_id}" + (f" version {version}" if version else ""),
                    code="not_found",
                )

            # Parse the configuration
            try:
                config_data = json.loads(config_json)
            except json.JSONDecodeError as e:
                logger.error("Failed to parse prompt configuration: %s", str(e))
                raise OpenAIResponseException(
                    status_code=500,
                    message="Invalid prompt configuration format",
                    code="internal_error",
                ) from e

            # Execute the prompt
            prompt_execute_data = PromptExecuteData.model_validate(config_data)
            logger.debug("Config data for prompt: %s: %s", prompt_id, prompt_execute_data)

            variables = prompt_params.variables

            result = await PromptExecutorService().execute_prompt(
                prompt_execute_data,
                input,
                variables=variables,
                api_key=api_key,
            )

            # Log successful execution
            logger.debug("Successfully executed prompt: %s", prompt_id)

            if prompt_execute_data.stream:
                # For streaming: wrap generator to manage span lifecycle
                # Span will close when streaming completes (in _create_streaming_generator)
                is_streaming = True
                logger.debug("Streaming response requested")
                return StreamingResponse(
                    self._create_streaming_generator(result, span, context_token),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "X-Accel-Buffering": "no",  # Disable Nginx buffering
                    },
                )
            else:
                # Add prompt info to non-streaming OpenAI-formatted response
                logger.debug("Non Streaming response requested")
                return result.model_copy(
                    update={
                        "prompt": BudResponsePrompt(
                            id=prompt_id,
                            variables=prompt_params.variables,
                            version=version,
                        )
                    }
                )

        except ValidationError as e:
            span.record_exception(e)
            span.set_attribute(ErrorAttributes.TYPE, "ValidationError")
            span.set_status(Status(StatusCode.ERROR, "Validation error"))
            logger.exception("Validation error during response creation")
            message, param, code = extract_validation_error_details(e)
            raise OpenAIResponseException(
                status_code=400,
                message=message,
                param=param,
                code=code,
            ) from e

        except ClientException as e:
            span.record_exception(e)
            span.set_attribute(ErrorAttributes.TYPE, "ClientException")
            span.set_status(Status(StatusCode.ERROR, e.message))
            logger.error("Client error during response creation: %s", e.message)
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

        except OpenAIResponseException as e:
            span.record_exception(e)
            span.set_attribute(ErrorAttributes.TYPE, "OpenAIResponseException")
            span.set_status(Status(StatusCode.ERROR, e.message))
            # Re-raise OpenAIResponseException as-is (from our own code above)
            raise

        except Exception as e:
            span.record_exception(e)
            span.set_attribute(ErrorAttributes.TYPE, type(e).__name__)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            logger.error("Unexpected error during prompt execution: %s", str(e))
            raise OpenAIResponseException(
                status_code=500,
                message="An unexpected error occurred during prompt execution",
                code="internal_error",
            ) from e

        finally:
            # Only cleanup here for non-streaming requests
            # For streaming, cleanup happens in _create_streaming_generator
            if not is_streaming:
                context.detach(context_token)
                span.end()
