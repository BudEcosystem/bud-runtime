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

import asyncio
import json
import logging
import time
import uuid
from typing import Any, AsyncGenerator, Dict, Optional, Union

from budmicroframe.commons.constants import WorkflowStatus
from budmicroframe.commons.schemas import (
    NotificationContent,
    NotificationRequest,
)
from budmicroframe.shared.dapr_workflow import DaprWorkflow
from pydantic import ValidationError

from budprompt.commons.exceptions import (
    PromptExecutionException,
    SchemaGenerationException,
    TemplateRenderingException,
)

from ..commons.exceptions import ClientException
from ..commons.helpers import run_async
from ..shared.redis_service import RedisService
from .executors import SimplePromptExecutor
from .revised_code.dynamic_model_creation import json_schema_to_pydantic_model
from .revised_code.field_validation import generate_validation_function
from .schemas import PromptConfigurationData, PromptExecuteRequest, PromptSchemaRequest, PromptSchemaResponse
from .utils import clean_model_cache


logger = logging.getLogger(__name__)

dapr_workflow = DaprWorkflow()


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

            # Validate tool and multiple calls configuration
            if request.enable_tools and not request.allow_multiple_calls:
                raise ClientException(
                    status_code=400,
                    message="Enabling tools requires multiple LLM calls.",
                )

            # Execute the prompt with input_data from request and stream parameter
            result = await self.executor.execute(
                deployment_name=request.deployment_name,
                model_settings=request.model_settings,
                input_schema=request.input_schema,
                output_schema=request.output_schema,
                messages=request.messages,
                input_data=request.input_data,
                stream=request.stream,
                output_validation_prompt=request.output_validation_prompt,
                input_validation_prompt=request.input_validation_prompt,
                llm_retry_limit=request.llm_retry_limit,
                enable_tools=request.enable_tools,
                allow_multiple_calls=request.allow_multiple_calls,
                system_prompt_role=request.system_prompt_role,
            )

            return result

        except ValidationError as e:
            # Input validation errors -> 422 Unprocessable Entity
            logger.error(f"Input validation failed: {str(e)}")
            raise ClientException(
                status_code=422, message="Invalid input data", params={"errors": json.loads(e.json())}
            ) from e

        except SchemaGenerationException as e:
            # Schema generation errors -> 400 Bad Request
            logger.error(f"Schema generation failed: {str(e)}")
            raise ClientException(
                status_code=400,
                message=e.message,  # Use the custom exception's message
            ) from e

        except TemplateRenderingException as e:
            # Prompt execution errors -> 500 Internal Server Error
            logger.error(f"Template rendering failed: {str(e)}")
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


class PromptConfigurationService:
    """Service for validating and processing prompt configuration schemas.

    This service handles validation of JSON schemas and their associated
    field-level validation prompts for structured prompt execution.
    """

    def __init__(self):
        """Initialize the PromptConfigurationService."""
        self.redis_service = RedisService()

    @staticmethod
    def _validate_field_references(model: Any, validations: Dict[str, Dict[str, str]], schema_type: str) -> None:
        """Validate that field names in validations exist in the model.

        Args:
            model: The Pydantic model to validate against
            validations: Dictionary of model names to field validations
            schema_type: Type of schema ('input' or 'output') for error messages

        Raises:
            ValueError: If a field is not found in the model
        """
        for model_name, field_validations in validations.items():
            # Check if this model exists (could be nested)
            if hasattr(model, "model_fields"):
                model_fields = set(model.model_fields.keys())
                for field_name in field_validations:
                    if field_name not in model_fields:
                        raise ValueError(
                            f"{schema_type.capitalize()} schema: Field '{field_name}' not found in model '{model_name}'"
                        )

    @staticmethod
    async def _generate_codes_async(
        validations: Dict[str, Dict[str, str]], max_concurrent: int = 10
    ) -> Dict[str, Dict[str, Dict[str, str]]]:
        """Generate validation codes asynchronously for all fields.

        Args:
            validations: Field validation prompts by model name
            max_concurrent: Maximum number of concurrent LLM calls

        Returns:
            Dictionary with validation codes structure
        """
        result = {}
        tasks = []
        task_metadata = []  # To track which task belongs to which field

        # Create semaphore for concurrent limit
        semaphore = asyncio.Semaphore(max_concurrent)

        async def generate_with_semaphore(field_name: str, prompt: str):
            """Generate validation code with semaphore limit."""
            async with semaphore:
                return await generate_validation_function(field_name, prompt)

        # Process validations
        if validations:
            for model_name, field_validations in validations.items():
                result[model_name] = {}
                for field_name, validation_prompt in field_validations.items():
                    task = generate_with_semaphore(field_name, validation_prompt)
                    tasks.append(task)
                    task_metadata.append((model_name, field_name, validation_prompt))

        # Execute all tasks in parallel
        if tasks:
            # Use gather to run all tasks - if any fails, all fail
            generated_codes = await asyncio.gather(*tasks)

            # Map results back to the structure
            for i, code in enumerate(generated_codes):
                model_name, field_name, prompt = task_metadata[i]
                result[model_name][field_name] = {"prompt": prompt, "code": code}

        return result

    @staticmethod
    def generate_validation_codes(
        workflow_id: str,
        notification_request: NotificationRequest,
        validations: Optional[Dict[str, Dict[str, str]]],
        target_topic_name: Optional[str] = None,
        target_name: Optional[str] = None,
        max_concurrent: int = 10,
    ) -> Optional[Dict[str, Dict[str, Dict[str, str]]]]:
        """Generate validation code for all fields using LLM in parallel.

        Args:
            workflow_id: Workflow identifier for tracking
            notification_request: Notification request for status updates
            validations: Field validation prompts by model name
            target_topic_name: Optional target topic for notifications
            target_name: Optional target name for notifications
            max_concurrent: Maximum number of concurrent LLM calls

        Returns:
            Dictionary with structure:
            {
                "ModelName": {
                    "field1": {"prompt": "...", "code": "..."},
                    "field2": {"prompt": "...", "code": "..."}
                }
            }

        Raises:
            Exception: If any LLM call fails
        """
        notification_req = notification_request.model_copy(deep=True)
        notification_req.payload.event = "code_generation"
        notification_req.payload.content = NotificationContent(
            title="Generating validation codes",
            message="Generating LLM-based validation functions for fields",
            status=WorkflowStatus.STARTED,
        )
        dapr_workflow.publish_notification(
            workflow_id=workflow_id,
            notification=notification_req,
            target_topic_name=target_topic_name,
            target_name=target_name,
        )

        try:
            # Run the async code generation only if there are validations
            validation_codes = None
            if validations:
                validation_codes = run_async(
                    PromptConfigurationService._generate_codes_async(validations, max_concurrent)
                )

            notification_req.payload.content = NotificationContent(
                title="Successfully generated validation codes",
                message="All validation functions have been generated",
                status=WorkflowStatus.COMPLETED,
            )
            dapr_workflow.publish_notification(
                workflow_id=workflow_id,
                notification=notification_req,
                target_topic_name=target_topic_name,
                target_name=target_name,
            )

            if validation_codes:
                """Validation code structure after generation
                {
                    "InputSchema": {
                        "email": {
                            "prompt": "Email must be a valid email address format",
                            "code": "def validate_email(value):"
                        },
                    },
                    "OutputSchema": {
                        "token": {
                            "prompt": "Token must be a non-empty string with at least 20 characters",
                            "code": "def validate_token(value):"
                        },
                    }
                }
                """
                logger.debug("Generated validation codes for %d schemas", len(validation_codes))

            return validation_codes

        except Exception as e:
            logger.exception(f"Failed to generate validation code: {str(e)}")
            notification_req.payload.content = NotificationContent(
                title="Failed to generate validation codes",
                message=f"LLM code generation failed: {str(e)}",
                status=WorkflowStatus.FAILED,
            )
            dapr_workflow.publish_notification(
                workflow_id=workflow_id,
                notification=notification_req,
                target_topic_name=target_topic_name,
                target_name=target_name,
            )
            raise e

    @staticmethod
    def store_prompt_configuration(
        workflow_id: str,
        notification_request: NotificationRequest,
        prompt_id: str,
        schema: Optional[Dict[str, Any]],
        schema_type: str,
        validation_codes: Optional[Dict[str, Dict[str, Dict[str, str]]]] = None,
        target_topic_name: Optional[str] = None,
        target_name: Optional[str] = None,
    ) -> None:
        """Store prompt configuration data in Redis.

        This method stores/updates prompt configuration data including schemas and
        validation codes based on the schema type (input/output).

        Args:
            workflow_id: Workflow identifier for tracking
            notification_request: Notification request for status updates
            prompt_id: Unique identifier for the prompt configuration
            schema: The JSON schema to store (None for unstructured)
            schema_type: Type of schema ('input' or 'output')
            validation_codes: Generated validation codes for the schema
            target_topic_name: Optional target topic for notifications
            target_name: Optional target name for notifications

        Raises:
            RedisException: If Redis operation fails
        """
        notification_req = notification_request.model_copy(deep=True)
        notification_req.payload.event = "save_prompt_configuration"
        notification_req.payload.content = NotificationContent(
            title="Storing prompt configuration",
            message="Storing prompt configuration in Redis",
            status=WorkflowStatus.STARTED,
        )
        dapr_workflow.publish_notification(
            workflow_id=workflow_id,
            notification=notification_req,
            target_topic_name=target_topic_name,
            target_name=target_name,
        )

        try:
            # Create Redis service instance
            redis_service = RedisService()

            # Construct Redis key
            redis_key = f"prompt:{prompt_id}"

            # Fetch existing data if it exists
            existing_data_json = run_async(redis_service.get(redis_key))
            if existing_data_json:
                existing_data = json.loads(existing_data_json)
                config_data = PromptConfigurationData.model_validate(existing_data)
            else:
                config_data = PromptConfigurationData()

            # Update configuration based on type
            if schema_type == "input":
                # Store input schema
                if schema:
                    config_data.input_schema = schema

                # Store input validation codes
                if validation_codes:
                    config_data.input_validation = validation_codes

            elif schema_type == "output":
                # Store output schema
                if schema:
                    config_data.output_schema = schema

                # Store output validation codes
                if validation_codes:
                    config_data.output_validation = validation_codes

            # Convert to JSON and store in Redis with 24-hour TTL
            config_json = config_data.model_dump_json(exclude_none=True, exclude_unset=True)
            run_async(redis_service.set(redis_key, config_json, ex=86400))  # 24 hours = 86400 seconds

            logger.debug(f"Stored prompt configuration for prompt_id: {prompt_id}, type: {schema_type}")

            notification_req.payload.content = NotificationContent(
                title="Successfully stored prompt configuration",
                message="Prompt configuration has been stored in Redis",
                status=WorkflowStatus.COMPLETED,
            )
            dapr_workflow.publish_notification(
                workflow_id=workflow_id,
                notification=notification_req,
                target_topic_name=target_topic_name,
                target_name=target_name,
            )

            return None

        except json.JSONDecodeError as e:
            logger.exception(f"Failed to parse existing Redis data for prompt_id {prompt_id}: {str(e)}")
            notification_req.payload.content = NotificationContent(
                title="Failed to store prompt configuration",
                message=f"Invalid data format in Redis for prompt_id {prompt_id}",
                status=WorkflowStatus.FAILED,
            )
            dapr_workflow.publish_notification(
                workflow_id=workflow_id,
                notification=notification_req,
                target_topic_name=target_topic_name,
                target_name=target_name,
            )
            raise e

        except Exception as e:
            logger.exception(f"Failed to store prompt configuration in Redis: {str(e)}")
            notification_req.payload.content = NotificationContent(
                title="Failed to store prompt configuration",
                message=f"Redis storage failed: {str(e)}",
                status=WorkflowStatus.FAILED,
            )
            dapr_workflow.publish_notification(
                workflow_id=workflow_id,
                notification=notification_req,
                target_topic_name=target_topic_name,
                target_name=target_name,
            )
            raise e

    @staticmethod
    def validate_schema(
        workflow_id: str,
        notification_request: NotificationRequest,
        schema: Optional[Dict[str, Any]],
        validations: Optional[Dict[str, Dict[str, str]]],
        schema_type: str,
        target_topic_name: Optional[str] = None,
        target_name: Optional[str] = None,
    ) -> None:
        """Validate prompt configuration schemas and their field validations.

        Args:
            workflow_id: Workflow identifier for tracking
            notification_request: Notification request for status updates
            schema: The JSON schema to validate (None for unstructured)
            validations: Field validation prompts by model name
            schema_type: Type of schema ('input' or 'output')
            target_topic_name: Optional target topic for notifications
            target_name: Optional target name for notifications

        Returns:
            None - validation only
        """
        notification_req = notification_request.model_copy(deep=True)
        notification_req.payload.event = "validation"

        notification_req.payload.content = NotificationContent(
            title="Validating prompt configuration schemas",
            message="Validating input/output schemas and field validations",
            status=WorkflowStatus.STARTED,
        )
        dapr_workflow.publish_notification(
            workflow_id=workflow_id,
            notification=notification_req,
            target_topic_name=target_topic_name,
            target_name=target_name,
        )

        try:
            # Validate schema if present
            if schema is not None:
                model_name = f"{schema_type.capitalize()}Schema"
                model = run_async(json_schema_to_pydantic_model(schema, model_name))

                # Validate field references in validations
                if validations:
                    PromptConfigurationService._validate_field_references(model, validations, schema_type)

            # Added sleep to avoid workflow registration failure
            time.sleep(3)

            notification_req.payload.content = NotificationContent(
                title="Successfully validated schemas",
                message="All prompt configuration schemas are valid",
                status=WorkflowStatus.COMPLETED,
            )
            dapr_workflow.publish_notification(
                workflow_id=workflow_id,
                notification=notification_req,
                target_topic_name=target_topic_name,
                target_name=target_name,
            )

            return None  # No validation codes generated in validate_schema

        except Exception as e:
            logger.exception("Error validating schemas: %s", str(e))
            notification_req.payload.content = NotificationContent(
                title="Failed to validate schemas",
                message="Fix: Check the schema structure and field references",
                status=WorkflowStatus.FAILED,
            )
            dapr_workflow.publish_notification(
                workflow_id=workflow_id,
                notification=notification_req,
                target_topic_name=target_topic_name,
                target_name=target_name,
            )
            raise e

    def __call__(self, request: PromptSchemaRequest, workflow_id: Optional[str] = None) -> PromptSchemaResponse:
        """Execute the prompt schema validation process.

        This method validates the schema along with field-level
        validation prompts for structured prompt execution and stores
        the configuration in Redis.

        Args:
            request (PromptSchemaRequest): The prompt schema request containing
                schema and validation prompts.
            workflow_id (Optional[str]): An optional workflow ID for tracking the
                validation process.

        Raises:
            ValueError: If schema validation fails or field references are invalid.
            RedisException: If storing to Redis fails.

        Returns:
            PromptSchemaResponse: The validation response containing the
                workflow ID and timestamp.
        """
        if not workflow_id:
            workflow_id = str(uuid.uuid4())

        workflow_name = "prompt_schema"
        notification_request = NotificationRequest.from_cloud_event(
            cloud_event=request,
            name=workflow_name,
            workflow_id=workflow_id,
        )

        # Validate schema
        self.validate_schema(
            workflow_id,
            notification_request,
            request.schema.schema,
            request.schema.validations,
            request.type,
            request.source_topic,
            request.source,
        )

        # Generate validation codes after successful validation
        validation_codes = self.generate_validation_codes(
            workflow_id,
            notification_request,
            request.schema.validations,
            request.source_topic,
            request.source,
        )

        # Store prompt configuration in Redis
        self.store_prompt_configuration(
            workflow_id,
            notification_request,
            request.prompt_id,
            request.schema.schema,
            request.type,
            validation_codes,
            request.source_topic,
            request.source,
        )

        response = PromptSchemaResponse(workflow_id=workflow_id, prompt_id=request.prompt_id)

        notification_request.payload.event = "results"
        notification_request.payload.content = NotificationContent(
            title="Prompt Schema Validation Results",
            message="The prompt schema validation is complete",
            result=response.model_dump(),
            status=WorkflowStatus.COMPLETED,
        )

        dapr_workflow.publish_notification(
            workflow_id=workflow_id,
            notification=notification_request,
            target_topic_name=request.source_topic,
            target_name=request.source,
        )

        return response
