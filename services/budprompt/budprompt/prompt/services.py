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

from ..commons.config import app_settings
from ..commons.exceptions import (
    ClientException,
    PromptExecutionException,
    SchemaGenerationException,
    TemplateRenderingException,
)
from ..commons.helpers import run_async
from ..shared.redis_service import RedisService
from .executors import SimplePromptExecutor
from .revised_code.field_validation import generate_validation_function
from .schema_builder import ModelGeneratorFactory
from .schemas import (
    PromptConfigCopyRequest,
    PromptConfigCopyResponse,
    PromptConfigGetResponse,
    PromptConfigRequest,
    PromptConfigResponse,
    PromptConfigurationData,
    PromptExecuteData,
    PromptExecuteRequest,
    PromptSchemaRequest,
    PromptSchemaResponse,
)
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

    async def execute_prompt_deprecated(
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

    async def execute_prompt(
        self, request: PromptExecuteData, input_data: Optional[Union[Dict[str, Any], str]]
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
            # Execute the prompt with input_data from request and stream parameter
            result = await self.executor.execute(
                deployment_name=request.deployment_name,
                model_settings=request.model_settings,
                input_schema=request.input_schema,
                output_schema=request.output_schema,
                messages=request.messages,
                input_data=input_data,
                stream=request.stream,
                input_validation=request.input_validation,
                output_validation=request.output_validation,
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
            # First, try to find the model to validate against
            target_model = None

            # Check if model_name matches the main model's name
            if (
                hasattr(model, "__name__")
                and model.__name__ == model_name
                or model_name in ["root", ""]
                or model_name == getattr(model, "__name__", None)
            ):
                target_model = model
            else:
                # Try to find nested model by inspecting field annotations
                if hasattr(model, "model_fields"):
                    for _field_name, field_info in model.model_fields.items():
                        # Get the field's annotation/type
                        field_type = field_info.annotation

                        # Handle Optional types
                        import typing

                        origin = typing.get_origin(field_type)
                        if origin is Union:
                            # Get the non-None type from Optional
                            args = typing.get_args(field_type)
                            field_type = next((arg for arg in args if arg is not type(None)), field_type)

                        # Check if this field's type matches the model_name we're looking for
                        if (
                            hasattr(field_type, "__name__")
                            and field_type.__name__ == model_name
                            or hasattr(field_type, "__name__")
                            and model_name in field_type.__name__
                        ):
                            target_model = field_type
                            break

            # If we found a target model, validate the fields
            if target_model and hasattr(target_model, "model_fields"):
                model_fields = set(target_model.model_fields.keys())
                for field_name in field_validations:
                    if field_name not in model_fields:
                        raise ValueError(
                            f"{schema_type.capitalize()} schema: Field '{field_name}' not found in model '{model_name}'"
                        )
            else:
                # If model not found, raise an error
                raise ValueError(
                    f"{schema_type.capitalize()} schema: Model '{model_name}' not found in schema structure."
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
        request_json: str,
        validation_codes: Optional[Dict[str, Dict[str, Dict[str, str]]]] = None,
        target_topic_name: Optional[str] = None,
        target_name: Optional[str] = None,
    ) -> str:
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
            # Convert to request object
            request = PromptSchemaRequest.model_validate_json(request_json)
            request_dict = json.loads(request_json)

            # Extract version from request, default to 1 if not provided
            version = request_dict.get("version", 1)

            # Create Redis service instance
            redis_service = RedisService()

            # Construct Redis key with prompt: prefix and version
            redis_key = f"prompt:{prompt_id}:v{version}"

            # Fetch existing data if it exists
            existing_data_json = run_async(redis_service.get(redis_key))
            if existing_data_json:
                existing_data = json.loads(existing_data_json)
                config_data = PromptConfigurationData.model_validate(existing_data)
            else:
                config_data = PromptConfigurationData()

            # Update configuration based on type
            if request.type == "input":
                # Store input schema
                if "schema" in request_dict["schema"]:
                    config_data.input_schema = request.schema.schema

                # Store input validation codes
                if "validations" in request_dict["schema"]:
                    config_data.input_validation = validation_codes

            elif request.type == "output":
                # Store output schema
                if "schema" in request_dict["schema"]:
                    config_data.output_schema = request.schema.schema

                # Store output validation codes
                if "validations" in request_dict["schema"]:
                    config_data.output_validation = validation_codes

            # Convert to JSON and store in Redis with configured TTL
            config_json = config_data.model_dump_json(exclude_none=True, exclude_unset=True)
            run_async(redis_service.set(redis_key, config_json, ex=app_settings.prompt_config_redis_ttl))

            # Only set default version pointer if set_default is True
            set_default = request_dict.get("set_default", False)
            if set_default:
                default_version_key = f"prompt:{prompt_id}:default_version"
                run_async(redis_service.set(default_version_key, redis_key, ex=app_settings.prompt_config_redis_ttl))
                logger.debug(
                    f"Stored prompt configuration for prompt_id: {prompt_id}, type: {request.type}, updated default to v{version}"
                )
            else:
                logger.debug(
                    f"Stored prompt configuration for prompt_id: {prompt_id}, type: {request.type}, v{version} without updating default"
                )

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

            return prompt_id

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
            if schema and "properties" in schema and "content" not in schema["properties"]:
                logger.error("Schema is invalid: missing content field")
                raise SchemaGenerationException("Schema must contain a 'content' field")

            # Validate schema if present
            if schema is not None:
                model_name = f"{schema_type.capitalize()}Schema"
                model = run_async(ModelGeneratorFactory.create_model(schema, model_name))

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
        request_json = request.model_dump_json(exclude_unset=True)

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
        redis_key = self.store_prompt_configuration(  # noqa: F841
            workflow_id,
            notification_request,
            request.prompt_id,
            request_json,
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


class PromptService:
    """Service for managing prompt configurations.

    This service handles saving and updating prompt configurations
    that include model settings and runtime parameters.
    """

    def __init__(self):
        """Initialize the PromptService."""
        self.redis_service = RedisService()

    async def save_prompt_config(self, request: PromptConfigRequest) -> PromptConfigResponse:
        """Save or update prompt configuration in Redis.

        This method stores/updates prompt configuration including model settings,
        messages, and other runtime parameters. It performs partial updates,
        only modifying fields provided by the client.

        Args:
            request: The prompt configuration request containing settings to save

        Returns:
            PromptConfigResponse with the prompt_id

        Raises:
            RedisException: If Redis operation fails
        """
        try:
            # Extract version from request, default to 1 if not provided
            version = request.version or 1

            # Construct Redis key with prompt: prefix and version
            redis_key = f"prompt:{request.prompt_id}:v{version}"

            # Fetch existing data if it exists
            existing_data_json = await self.redis_service.get(redis_key)
            if existing_data_json:
                existing_data = json.loads(existing_data_json)
                config_data = PromptConfigurationData.model_validate(existing_data)
            else:
                config_data = PromptConfigurationData()

            # Get only the fields that were explicitly set in the request
            updates = request.model_dump(exclude_unset=True)

            # Validate that deployment_name is not being set to null
            if "deployment_name" in updates and updates["deployment_name"] is None:
                raise ClientException(status_code=400, message="deployment_name cannot be set to null.")

            # Update configuration with provided fields (partial update)
            for field_name, value in updates.items():
                if field_name not in [
                    "prompt_id",
                    "version",
                    "set_default",
                ]:  # Skip prompt_id, version, and set_default as they're not part of config_data
                    setattr(config_data, field_name, value)

            # Convert to JSON and store in Redis with configured TTL
            config_json = config_data.model_dump_json(exclude_none=True, exclude_unset=True)

            # Validation
            if config_data.enable_tools is True and config_data.allow_multiple_calls is False:
                raise ClientException(
                    status_code=400,
                    message="Enabling tools requires multiple LLM calls.",
                )

            # Store in Redis
            await self.redis_service.set(redis_key, config_json, ex=app_settings.prompt_config_redis_ttl)

            if request.set_default:
                default_version_key = f"prompt:{request.prompt_id}:default_version"
                await self.redis_service.set(default_version_key, redis_key, ex=app_settings.prompt_config_redis_ttl)
                logger.debug(
                    f"Stored prompt configuration for prompt_id: {request.prompt_id} and updated default to v{version}"
                )
            else:
                logger.debug(
                    f"Stored prompt configuration for prompt_id: {request.prompt_id} v{version} without updating default"
                )

            return PromptConfigResponse(
                code=200,
                message="Prompt configuration saved successfully",
                prompt_id=request.prompt_id,
            )

        except json.JSONDecodeError as e:
            logger.exception(f"Failed to parse existing Redis data for prompt_id {request.prompt_id}: {str(e)}")
            raise ClientException(
                status_code=500,
                message=f"Invalid data format in Redis for prompt_id {request.prompt_id}",
            ) from e
        except ClientException:
            # Re-raise client exceptions as-is
            raise
        except Exception as e:
            logger.exception(f"Failed to store prompt configuration: {str(e)}")
            raise ClientException(
                status_code=500,
                message="Failed to store prompt configuration",
            ) from e

    async def get_prompt_config(self, prompt_id: str, version: Optional[int] = None) -> PromptConfigGetResponse:
        """Get prompt configuration from Redis.

        This method retrieves the prompt configuration stored in Redis
        for the given prompt_id and optional version.

        Args:
            prompt_id: The unique identifier of the prompt configuration
            version: Optional version number to retrieve specific version

        Returns:
            PromptConfigGetResponse with the configuration data

        Raises:
            ClientException: If configuration not found or Redis operation fails
        """
        try:
            # Determine which Redis key to use based on version
            if version:
                # Get specific version
                redis_key = f"prompt:{prompt_id}:v{version}"
            else:
                # Get default version
                default_key = f"prompt:{prompt_id}:default_version"
                redis_key = await self.redis_service.get(default_key)

                if not redis_key:
                    logger.debug(f"Default version not found for prompt_id: {prompt_id}")
                    raise ClientException(
                        status_code=404,
                        message=f"Default version not found for prompt_id: {prompt_id}",
                    )

            # Fetch data from Redis using the determined key
            config_json = await self.redis_service.get(redis_key)

            if not config_json:
                if version:
                    message = f"Version {version} not found for prompt_id: {prompt_id}"
                else:
                    message = f"Configuration not found for prompt_id: {prompt_id}"
                logger.debug(message)
                raise ClientException(
                    status_code=404,
                    message=message,
                )

            # Parse and validate the data
            config_data = PromptConfigurationData.model_validate_json(config_json)

            return PromptConfigGetResponse(
                code=200,
                message="Prompt configuration retrieved successfully",
                prompt_id=prompt_id,
                data=config_data,
            )

        except ClientException:
            # Re-raise client exceptions as-is
            raise
        except json.JSONDecodeError as e:
            logger.exception(f"Failed to parse Redis data for prompt_id {prompt_id}: {str(e)}")
            raise ClientException(
                status_code=500,
                message=f"Invalid data format in Redis for prompt_id {prompt_id}",
            ) from e
        except Exception as e:
            logger.exception(f"Failed to retrieve prompt configuration: {str(e)}")
            raise ClientException(
                status_code=500,
                message="Failed to retrieve prompt configuration",
            ) from e

    async def copy_prompt_config(self, request: PromptConfigCopyRequest) -> PromptConfigCopyResponse:
        """Copy a specific version of prompt configuration from one ID to another.

        This method:
        1. Validates source prompt and version exist
        2. Either replaces or merges with target configuration based on replace flag
        3. Removes TTL (permanent storage)
        4. Optionally sets as default for target prompt

        Args:
            request: The copy configuration request

        Returns:
            PromptConfigCopyResponse with copy details

        Raises:
            ClientException: If source not found or copy fails
        """
        try:
            # Validate source and target are different
            if (
                request.source_prompt_id == request.target_prompt_id
                and request.source_version == request.target_version
            ):
                raise ClientException(status_code=400, message="Cannot copy to same prompt ID and version")

            # Construct source Redis key
            source_key = f"prompt:{request.source_prompt_id}:v{request.source_version}"

            # Get source configuration
            source_data_json = await self.redis_service.get(source_key)
            if not source_data_json:
                raise ClientException(
                    status_code=404,
                    message=f"Source prompt configuration not found: {request.source_prompt_id} v{request.source_version}",
                )

            source_data = json.loads(source_data_json)

            # Construct target Redis key
            target_key = f"prompt:{request.target_prompt_id}:v{request.target_version}"

            # Determine operation: replace or merge
            if request.replace:
                # Complete replacement - use source data as is
                final_data = source_data
                logger.debug("Replacing target config with source data")
            else:
                # Merge mode - get existing target data if it exists
                target_data_json = await self.redis_service.get(target_key)
                if target_data_json:
                    target_data = json.loads(target_data_json)
                    # Merge: Update target with only fields present in source
                    final_data = target_data.copy()
                    for key, value in source_data.items():
                        if value is not None:  # Only update non-null fields from source
                            final_data[key] = value
                    logger.debug("Merging source fields into existing target config")
                else:
                    # No existing target, use source data
                    final_data = source_data
                    logger.debug("No existing target, using source data")

            # Save to target without TTL (permanent storage)
            final_data_json = json.dumps(final_data)
            await self.redis_service.set(target_key, final_data_json, ex=None)

            # Set as default if requested
            if request.set_as_default:
                default_key = f"prompt:{request.target_prompt_id}:default_version"
                await self.redis_service.set(default_key, target_key, ex=None)
                logger.debug(f"Set {target_key} as default for {request.target_prompt_id}")

            logger.debug(
                f"Copied prompt config from {request.source_prompt_id}:v{request.source_version} "
                f"to {request.target_prompt_id}:v{request.target_version}"
            )

            return PromptConfigCopyResponse(
                source_prompt_id=request.source_prompt_id,
                source_version=request.source_version,
                target_prompt_id=request.target_prompt_id,
                target_version=request.target_version,
            )

        except ClientException:
            raise
        except Exception as e:
            logger.exception(f"Failed to copy prompt configuration: {str(e)}")
            raise ClientException(status_code=500, message="Failed to copy prompt configuration") from e
