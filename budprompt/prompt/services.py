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

"""Services for the prompt module."""

import logging
from typing import Any, AsyncGenerator, Dict, Union

from budmicroframe.commons.exceptions import ClientException
from pydantic import ValidationError

from budprompt.commons.exceptions import PromptExecutionException, SchemaGenerationException

from .executors import SimplePromptExecutor
from .schemas import PromptExecuteRequest
from .utils import clean_model_cache


logger = logging.getLogger(__name__)


class PromptExecutorService:
    """Service for orchestrating prompt execution.

    This service handles the high-level logic for executing prompts,
    including request validation, executor management, and response formatting.
    """

    def __init__(self):
        """Initialize the PromptExecutorService."""
        self.executor = SimplePromptExecutor()

    async def execute_prompt(
        self, request: PromptExecuteRequest
    ) -> Union[Dict[str, Any], str, AsyncGenerator[str, None]]:
        """Execute a prompt based on the request.

        Args:
            request: Prompt execution request

        Returns:
            The result of the prompt execution or a generator for streaming

        Raises:
            ClientException: If validation or execution fails
        """
        try:
            # Validate content field exists in schemas
            if (
                request.output_schema
                and "properties" in request.output_schema
                and "content" not in request.output_schema["properties"]
            ):
                raise ClientException(status_code=400, message="Output schema must contain a 'content' field")

            if (
                request.input_schema
                and "properties" in request.input_schema
                and "content" not in request.input_schema["properties"]
            ):
                raise ClientException(status_code=400, message="Input schema must contain a 'content' field")

            # Execute the prompt with input_data from request and stream parameter
            result = await self.executor.execute(
                deployment_name=request.deployment_name,
                model_settings=request.model_settings,
                input_schema=request.input_schema,
                output_schema=request.output_schema,
                system_prompt=request.system_prompt,
                messages=request.messages,
                input_data=request.input_data,
                stream=request.stream,
                output_validation_prompt=request.output_validation_prompt,
                llm_retry_limit=request.llm_retry_limit,
            )

            return result

        except ValidationError as e:
            # Input validation errors -> 400 Bad Request
            logger.error(f"Input validation failed: {str(e)}")
            raise ClientException(status_code=400, message="Invalid input data") from e

        except SchemaGenerationException as e:
            # Schema generation errors -> 400 Bad Request
            logger.error(f"Schema generation failed: {str(e)}")
            raise ClientException(
                status_code=400,
                message=e.message,  # Use the custom exception's message
            ) from e

        except PromptExecutionException as e:
            # Prompt execution errors -> 500 Internal Server Error
            logger.error(f"Prompt execution failed: {str(e)}")
            raise ClientException(
                status_code=500,
                message=e.message,  # Use the custom exception's message
            ) from e

        except Exception as e:
            # Let unhandled exceptions bubble up
            logger.error(f"Unexpected error: {str(e)}")
            raise
        finally:
            # Always clean up temporary modules
            clean_model_cache()
