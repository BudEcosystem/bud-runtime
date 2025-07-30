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
from typing import Any, Dict, Union

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

    async def execute_prompt(self, request: PromptExecuteRequest) -> Union[Dict[str, Any], str]:
        """Execute a prompt based on the request.

        Args:
            request: Prompt execution request

        Returns:
            The result of the prompt execution

        Raises:
            PromptExecutionError: If execution fails
        """
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

        # Clean up temporary modules
        clean_model_cache()

        return result
