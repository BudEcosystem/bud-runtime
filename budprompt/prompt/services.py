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
import time

from .executors import SimplePromptExecutor
from .schemas import PromptExecuteRequest, PromptExecuteResponse
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

    async def execute_prompt(self, request: PromptExecuteRequest) -> PromptExecuteResponse:
        """Execute a prompt based on the request.

        Args:
            request: Prompt execution request

        Returns:
            Prompt execution response

        Raises:
            PromptExecutionError: If execution fails
        """
        start_time = time.time()
        metadata = {}

        try:
            # Execute the prompt with input_data from request
            result = await self.executor.execute(
                deployment_name=request.deployment_name,
                model_settings=request.model_settings,
                input_schema=request.input_schema,
                output_schema=request.output_schema,
                system_prompt=request.system_prompt,
                messages=request.messages,
                input_data=request.input_data,
            )

            # Calculate execution time
            execution_time = time.time() - start_time
            metadata["execution_time_seconds"] = round(execution_time, 3)
            metadata["deployment_name"] = request.deployment_name

            # Clean up temporary modules
            clean_model_cache()

            logger.info(f"Prompt executed successfully in {execution_time:.3f}s")

            return PromptExecuteResponse(success=True, data=result, error=None, metadata=metadata)

        except Exception as e:
            # Calculate execution time even on failure
            execution_time = time.time() - start_time
            metadata["execution_time_seconds"] = round(execution_time, 3)
            metadata["deployment_name"] = request.deployment_name

            logger.error(f"Prompt execution failed: {str(e)}")

            # Clean up temporary modules even on failure
            clean_model_cache()

            return PromptExecuteResponse(success=False, data=None, error=str(e), metadata=metadata)
