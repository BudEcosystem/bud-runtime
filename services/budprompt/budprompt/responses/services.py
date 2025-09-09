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

from budprompt.commons.exceptions import ClientException
from budprompt.shared.redis_service import RedisService

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

    async def execute_prompt(self, prompt_params: ResponsePromptParam, input: Optional[str] = None) -> Dict[str, Any]:
        """Execute prompt using template from Redis.

        Args:
            prompt_params: Prompt parameters including id, version, and variables
            input: Optional input text for the prompt

        Returns:
            Dictionary containing the execution result

        Raises:
            ClientException: If prompt template not found or execution fails
        """
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
                    logger.debug(f"Default version not found for prompt_id: {prompt_id}")
                    raise ClientException(status_code=404, message=f"Prompt template not found: {prompt_id}")

            # Fetch prompt configuration from Redis
            config_json = await self.redis_service.get(redis_key)

            if not config_json:
                logger.debug(f"Prompt configuration not found for key: {redis_key}")
                raise ClientException(
                    status_code=404,
                    message=f"Prompt template not found: {prompt_id}" + (f" version {version}" if version else ""),
                )

            # Parse the configuration
            try:
                config_data = json.loads(config_json)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse prompt configuration: {str(e)}")
                raise ClientException(status_code=500, message="Invalid prompt configuration format") from e

            # For now, return success message with basic info
            # In future, this will perform actual prompt execution with variable substitution
            result = {
                "status": "success",
                "prompt_id": prompt_id,
                "version": version or "default",
                "message": "Prompt template retrieved successfully",
                "template_info": {
                    "deployment_name": config_data.get("deployment_name"),
                    "has_messages": bool(config_data.get("messages")),
                    "has_input_schema": bool(config_data.get("input_schema")),
                    "has_output_schema": bool(config_data.get("output_schema")),
                    "variables_provided": list(prompt_params.variables.keys()) if prompt_params.variables else [],
                    "input_provided": bool(input),
                },
            }

            # Log successful execution
            logger.info(f"Successfully executed prompt: {prompt_id}")

            return result

        except ClientException:
            # Re-raise client exceptions as-is
            raise
        except Exception as e:
            logger.exception(f"Unexpected error executing prompt: {str(e)}")
            raise ClientException(status_code=500, message="Failed to execute prompt template") from e
