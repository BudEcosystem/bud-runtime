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
import time
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, Optional, Union

from budmicroframe.commons import logging
from budmicroframe.commons.constants import WorkflowStatus
from budmicroframe.commons.schemas import (
    NotificationContent,
    NotificationRequest,
    SuccessResponse,
)
from budmicroframe.shared.dapr_workflow import DaprWorkflow
from openai.types.responses.response_input_param import ResponseInputParam
from pydantic import ValidationError

from ..commons.config import app_settings
from ..commons.constants import CLEANUP_REGISTRY_KEY
from ..commons.exceptions import (
    ClientException,
    PromptExecutionException,
    SchemaGenerationException,
    TemplateRenderingException,
)
from ..commons.helpers import run_async
from ..commons.security import HashManager
from ..executors import PromptExecutorFactory
from ..shared.mcp_foundry_service import mcp_foundry_service
from ..shared.redis_service import RedisService, TensorZeroRedisService
from .crud import PromptCRUD, PromptVersionCRUD
from .revised_code.field_validation import generate_validation_function
from .schema_builder import ModelGeneratorFactory
from .schemas import (
    MCPCleanupRegistryEntry,
    PromptCleanupRequest,
    PromptCleanupResponse,
    PromptConfigCopyRequest,
    PromptConfigCopyResponse,
    PromptConfigGetRawResponse,
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


logger = logging.get_logger(__name__)

dapr_workflow = DaprWorkflow()


class PromptExecutorService:
    """Service for orchestrating prompt execution.

    This service handles the high-level logic for executing prompts,
    including request validation, executor management, and response formatting.
    """

    def __init__(self):
        """Initialize the PromptExecutorService."""
        self.executor = PromptExecutorFactory.get_executor()

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
        self,
        request: PromptExecuteData,
        input_data: Optional[Union[str, ResponseInputParam]] = None,
        variables: Optional[Dict[str, Any]] = None,
        api_key: Optional[str] = None,
    ) -> Union[Dict[str, Any], str, AsyncGenerator[str, None]]:
        """Execute a prompt based on the request.

        Args:
            request: Prompt execution request
            input_data: Input data for the prompt
            api_key: Optional API key for authorization

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
                api_key=api_key,
                tools=request.tools,
                system_prompt=request.system_prompt,
                variables=variables,
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
                status_code=e.status_code,
                message=e.message,
                params={"param": e.param},
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
        validations: Dict[str, Dict[str, str]],
        deployment_name: str,
        max_concurrent: int = 10,
        access_token: str = None,
    ) -> Dict[str, Dict[str, Dict[str, str]]]:
        """Generate validation codes asynchronously for all fields.

        Args:
            validations: Field validation prompts by model name
            deployment_name: The name of the model deployment to use
            max_concurrent: Maximum number of concurrent LLM calls
            access_token: The access token to use for authentication

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
                return await generate_validation_function(field_name, prompt, deployment_name, access_token)

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
    def _store_api_key_bypass(
        hashed_token: str,
        deployment_name: str,
        endpoint_id: Optional[str],
        model_id: Optional[str],
        project_id: Optional[str],
        user_id: Optional[str],
        api_key_project_id: Optional[str],
        ttl: int = 3600,
    ) -> None:
        """Store API key bypass data in Redis for validation process.

        Args:
            hashed_token: The hashed JWT token
            deployment_name: The deployment name for the cache entry
            endpoint_id: The endpoint ID
            model_id: The model ID
            project_id: The project ID
            user_id: The user ID
            api_key_project_id: The API key project ID
            ttl: Time to live in seconds (default 3600 seconds = 1 hour)
        """
        redis_service = TensorZeroRedisService()

        # Build cache data structure matching budapp format
        cache_data = {
            deployment_name: {
                "endpoint_id": str(endpoint_id) if endpoint_id else None,
                "model_id": str(model_id) if model_id else None,
                "project_id": str(project_id) if project_id else None,
            },
            "__metadata__": {
                "api_key_id": None,  # Not applicable for JWT
                "user_id": str(user_id) if user_id else None,
                "api_key_project_id": str(api_key_project_id) if api_key_project_id else None,
            },
        }

        redis_key = f"api_key:{hashed_token}"
        cache_json = json.dumps(cache_data)

        # Store in Redis with TTL
        run_async(redis_service.set(redis_key, cache_json, ex=ttl))
        logger.debug(f"Stored API key bypass for deployment {deployment_name} with TTL {ttl} seconds")

    @staticmethod
    def _remove_api_key_bypass(hashed_token: str) -> None:
        """Remove API key bypass data from Redis after validation.

        Args:
            hashed_token: The hashed JWT token
        """
        redis_service = TensorZeroRedisService()
        redis_key = f"api_key:{hashed_token}"

        run_async(redis_service.delete(redis_key))
        logger.debug("Removed API key bypass from Redis after validation")

    @staticmethod
    def generate_validation_codes(
        workflow_id: str,
        notification_request: NotificationRequest,
        validations: Optional[Dict[str, Dict[str, str]]],
        deployment_name: str,
        target_topic_name: Optional[str] = None,
        target_name: Optional[str] = None,
        max_concurrent: int = 10,
        access_token: Optional[str] = None,
        endpoint_id: Optional[str] = None,
        model_id: Optional[str] = None,
        project_id: Optional[str] = None,
        user_id: Optional[str] = None,
        api_key_project_id: Optional[str] = None,
    ) -> Optional[Dict[str, Dict[str, Dict[str, str]]]]:
        """Generate validation code for all fields using LLM in parallel.

        Args:
            workflow_id: Workflow identifier for tracking
            notification_request: Notification request for status updates
            validations: Field validation prompts by model name
            deployment_name: The name of the model deployment to use
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
            hashed_token = None

            if validations:
                # Store API key bypass in Redis if access_token is provided
                if access_token:
                    # Hash the JWT token using the same pattern as budapp
                    hashed_token = HashManager().create_sha_256_hash(f"bud-{access_token}")
                    PromptConfigurationService._store_api_key_bypass(
                        hashed_token=hashed_token,
                        deployment_name=deployment_name,
                        endpoint_id=endpoint_id,
                        model_id=model_id,
                        project_id=project_id,
                        user_id=user_id,
                        api_key_project_id=api_key_project_id,
                        ttl=3600,  # Fixed 1 hour TTL for validation process
                    )
                    logger.debug("Stored API key bypass for validation generation with TTL 3600 seconds")

                validation_codes = run_async(
                    PromptConfigurationService._generate_codes_async(
                        validations, deployment_name, max_concurrent, access_token
                    )
                )

                # Remove API key bypass after validation code generation
                if hashed_token:
                    PromptConfigurationService._remove_api_key_bypass(hashed_token)

                if not validation_codes:
                    raise Exception("Failed to generate validation codes")

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

            # Store deployment_name if provided in request
            if "deployment_name" in request_dict and request_dict["deployment_name"]:
                config_data.deployment_name = request.deployment_name

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

            # Determine TTL: None for permanent storage, configured TTL otherwise
            permanent = request_dict.get("permanent", False)
            ttl = None if permanent else app_settings.prompt_config_redis_ttl
            storage_type = "permanent" if permanent else f"with {ttl}s TTL"

            # Convert to JSON and store in Redis with determined TTL
            config_json = config_data.model_dump_json(exclude_none=True, exclude_unset=True)
            run_async(redis_service.set(redis_key, config_json, ex=ttl))

            # Only set default version pointer if set_default is True
            set_default = request_dict.get("set_default", False)
            if set_default:
                default_version_key = f"prompt:{prompt_id}:default_version"
                run_async(redis_service.set(default_version_key, redis_key, ex=ttl))
                logger.debug(
                    f"Stored {storage_type} prompt configuration for prompt_id: {prompt_id}, type: {request.type}, updated default to v{version}"
                )
            else:
                logger.debug(
                    f"Stored {storage_type} prompt configuration for prompt_id: {prompt_id}, type: {request.type}, v{version} without updating default"
                )

            # Add to cleanup registry for all temporary prompts
            if not permanent:
                # Create service instance to access instance methods
                prompt_service = PromptService()

                # Extract MCP resources (will be empty if no tools)
                mcp_resources = prompt_service._extract_mcp_resources(config_data.tools or [])

                run_async(
                    prompt_service._add_to_cleanup_registry(
                        prompt_id=prompt_id,
                        version=version,
                        redis_key=redis_key,
                        ttl=ttl,
                        mcp_resources=mcp_resources,
                    )
                )
            else:
                # Remove from cleanup registry if exists (permanent prompts don't need cleanup)
                prompt_service = PromptService()
                run_async(prompt_service._remove_from_cleanup_registry(redis_key))

            # Persist to database for permanent prompts
            if permanent:
                try:
                    # Use context managers for CRUD operations
                    with PromptCRUD() as prompt_crud:
                        prompt_record = prompt_crud.upsert_prompt(prompt_id=prompt_id, default_version_id=None)

                    with PromptVersionCRUD() as version_crud:
                        version_record = version_crud.upsert_prompt_version(
                            prompt_db_id=prompt_record.id,
                            version=version,
                            version_data=config_data.model_dump(exclude_none=True, exclude_unset=True),
                        )

                    # Update default_version_id if requested
                    if set_default:
                        with PromptCRUD() as prompt_crud:
                            prompt_record.default_version_id = version_record.id
                            prompt_crud.update(data=prompt_record, conditions={"id": prompt_record.id})

                        logger.debug(
                            f"Database: Stored permanent prompt {prompt_id}:v{version} "
                            f"and set as default (version_id: {version_record.id})"
                        )
                    else:
                        logger.debug(f"Database: Stored permanent prompt {prompt_id}:v{version}")

                except Exception as db_error:
                    # Log warning but don't fail the request (eventual consistency)
                    logger.warning(
                        f"Failed to persist permanent prompt to database: {str(db_error)}. "
                        f"Redis operation succeeded, but database sync failed for {prompt_id}:v{version}"
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

        workflow_name = "perform_prompt_schema"
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
            request.deployment_name,
            request.source_topic,
            request.source,
            max_concurrent=10,
            access_token=request.access_token,
            endpoint_id=request.endpoint_id,
            model_id=request.model_id,
            project_id=request.project_id,
            user_id=request.user_id,
            api_key_project_id=request.api_key_project_id,
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

        # Extract version from request, default to 1 if not provided
        request_dict = request.model_dump(exclude_unset=True)
        version = request_dict.get("version", 1)

        response = PromptSchemaResponse(workflow_id=workflow_id, prompt_id=request.prompt_id, version=version)

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

    def _extract_mcp_resources(self, tools: list[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract MCP resource IDs from tools configuration.

        Args:
            tools: List of tool configurations

        Returns:
            Dictionary with virtual_server_id and gateways
        """
        mcp_resources = {"virtual_server_id": None, "gateways": {}}

        for tool in tools:
            # Convert Pydantic model to dict if needed
            if hasattr(tool, "model_dump"):
                tool = tool.model_dump()

            if tool.get("type") == "mcp":
                # Extract virtual server ID
                if tool.get("server_url"):
                    mcp_resources["virtual_server_id"] = tool.get("server_url")

                # Extract gateway IDs
                gateway_config = tool.get("gateway_config", {})
                for connector_id, gateway_id in gateway_config.items():
                    if gateway_id:
                        mcp_resources["gateways"][connector_id] = gateway_id

        return mcp_resources

    async def _add_to_cleanup_registry(
        self, prompt_id: str, version: int, redis_key: str, ttl: int, mcp_resources: Dict[str, Any]
    ) -> None:
        """Add or update entry in cleanup registry using Redis Hash (atomic).

        Uses Redis Hash for atomic per-prompt operations, eliminating race conditions.

        Args:
            prompt_id: Prompt identifier
            version: Version number
            redis_key: Full Redis key (used as hash field)
            ttl: TTL in seconds
            mcp_resources: Extracted MCP resource IDs
        """
        # Read single field atomically (O(1))
        existing_entry_json = await self.redis_service.hget(CLEANUP_REGISTRY_KEY, redis_key)

        # Calculate timestamps
        now = datetime.now(timezone.utc)
        expires_at = datetime.fromtimestamp(now.timestamp() + ttl, tz=timezone.utc)

        # Create or update entry
        if existing_entry_json:
            # Decode bytes if needed
            if isinstance(existing_entry_json, bytes):
                existing_entry_json = existing_entry_json.decode("utf-8")
            existing_entry = json.loads(existing_entry_json)

            entry_data = MCPCleanupRegistryEntry(
                prompt_id=prompt_id,
                version=version,
                created_at=existing_entry["created_at"],
                expires_at=expires_at.isoformat(),
                cleanup_failed=False,  # Reset on update
                reason=None,
                mcp_resources=mcp_resources,
            )
            logger.debug(f"Updated cleanup registry entry for {redis_key}")
        else:
            entry_data = MCPCleanupRegistryEntry(
                prompt_id=prompt_id,
                version=version,
                created_at=now.isoformat(),
                expires_at=expires_at.isoformat(),
                cleanup_failed=False,
                reason=None,
                mcp_resources=mcp_resources,
            )
            logger.debug(f"Added cleanup registry entry for {redis_key}")

        # Write single field atomically
        entry_json = json.dumps(entry_data.model_dump())
        await self.redis_service.hset(CLEANUP_REGISTRY_KEY, redis_key, entry_json)

        logger.debug(f"Cleanup registry entry for {redis_key} stored atomically")

    async def _remove_from_cleanup_registry(self, redis_key: str) -> None:
        """Remove entry from cleanup registry using Redis Hash (atomic).

        Args:
            redis_key: Full Redis key to remove
        """
        # Atomic delete operation
        deleted_count = await self.redis_service.hdel(CLEANUP_REGISTRY_KEY, redis_key)

        if deleted_count > 0:
            logger.debug(f"Removed {redis_key} from cleanup registry (now permanent)")
        else:
            logger.debug(f"Entry {redis_key} not found in cleanup registry, nothing to remove")

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
                    "permanent",
                ]:
                    setattr(config_data, field_name, value)

            # Convert to JSON and store in Redis with configured TTL
            config_json = config_data.model_dump_json(exclude_none=True, exclude_unset=True)

            # Validation
            if config_data.enable_tools is True and config_data.allow_multiple_calls is False:
                raise ClientException(
                    status_code=400,
                    message="Enabling tools requires multiple LLM calls.",
                )

            # Determine TTL: None for permanent storage, configured TTL otherwise
            ttl = None if request.permanent else app_settings.prompt_config_redis_ttl
            storage_type = "permanent" if request.permanent else f"with {ttl}s TTL"

            # Store in Redis
            await self.redis_service.set(redis_key, config_json, ex=ttl)

            if request.set_default:
                default_version_key = f"prompt:{request.prompt_id}:default_version"
                await self.redis_service.set(default_version_key, redis_key, ex=ttl)
                logger.debug(
                    f"Stored {storage_type} prompt configuration for prompt_id: {request.prompt_id} "
                    f"and updated default to v{version}"
                )
            else:
                logger.debug(
                    f"Stored {storage_type} prompt configuration for prompt_id: {request.prompt_id} v{version} "
                    f"without updating default"
                )

            # Add to cleanup registry for all temporary prompts
            if not request.permanent:
                # Extract MCP resources (will be empty if no tools)
                mcp_resources = self._extract_mcp_resources(config_data.tools or [])

                await self._add_to_cleanup_registry(
                    prompt_id=request.prompt_id,
                    version=version,
                    redis_key=redis_key,
                    ttl=ttl,
                    mcp_resources=mcp_resources,
                )
            else:
                # Remove from cleanup registry if exists (permanent prompts don't need cleanup)
                await self._remove_from_cleanup_registry(redis_key)

            # Persist to database for permanent prompts
            if request.permanent:
                try:
                    # Use context manager for CRUD operations
                    with PromptCRUD() as prompt_crud:
                        prompt_record = prompt_crud.upsert_prompt(prompt_id=request.prompt_id, default_version_id=None)

                    with PromptVersionCRUD() as version_crud:
                        version_record = version_crud.upsert_prompt_version(
                            prompt_db_id=prompt_record.id,
                            version=version,
                            version_data=config_data.model_dump(exclude_none=True, exclude_unset=True),
                        )

                    # Update default_version_id if requested
                    if request.set_default:
                        with PromptCRUD() as prompt_crud:
                            prompt_record.default_version_id = version_record.id
                            prompt_crud.update(data=prompt_record, conditions={"id": prompt_record.id})

                        logger.debug(
                            f"Database: Stored permanent prompt {request.prompt_id}:v{version} "
                            f"and set as default (version_id: {version_record.id})"
                        )
                    else:
                        logger.debug(f"Database: Stored permanent prompt {request.prompt_id}:v{version}")

                except Exception as db_error:
                    # Log warning but don't fail the request (eventual consistency)
                    logger.warning(
                        f"Failed to persist permanent prompt to database: {str(db_error)}. "
                        f"Redis operation succeeded, but database sync failed for {request.prompt_id}:v{version}"
                    )

            return PromptConfigResponse(
                code=200,
                message="Prompt configuration saved successfully",
                prompt_id=request.prompt_id,
                version=version,
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

    async def get_prompt_config(
        self, prompt_id: str, version: Optional[int] = None, raw_data: bool = False
    ) -> Union[PromptConfigGetResponse, PromptConfigGetRawResponse]:
        """Get prompt configuration from Redis.

        This method retrieves the prompt configuration stored in Redis
        for the given prompt_id and optional version.

        Args:
            prompt_id: The unique identifier of the prompt configuration
            version: Optional version number to retrieve specific version
            raw_data: If True, return raw Redis JSON without Pydantic processing

        Returns:
            PromptConfigGetResponse with validated data or PromptConfigGetRawResponse with raw data

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

                # Decode bytes to string if needed
                if isinstance(redis_key, bytes):
                    redis_key = redis_key.decode("utf-8")

            # Extract version from redis_key (format: prompt:{prompt_id}:v{version})
            retrieved_version = int(redis_key.split(":v")[-1])

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

            # Return raw data or validated data based on raw_data flag
            if raw_data:
                # Parse as raw dict without Pydantic validation
                config_dict = json.loads(config_json)
                return PromptConfigGetRawResponse(
                    code=200,
                    message="Raw prompt configuration retrieved successfully",
                    prompt_id=prompt_id,
                    version=retrieved_version,
                    data=config_dict,
                )
            else:
                # Parse and validate the data with Pydantic
                config_data = PromptConfigurationData.model_validate_json(config_json)
                return PromptConfigGetResponse(
                    code=200,
                    message="Prompt configuration retrieved successfully",
                    prompt_id=prompt_id,
                    version=retrieved_version,
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

            # Persist to database (copy operation always creates permanent storage)
            try:
                # Use context manager for CRUD operations
                with PromptCRUD() as prompt_crud:
                    prompt_record = prompt_crud.upsert_prompt(
                        prompt_id=request.target_prompt_id, default_version_id=None
                    )

                with PromptVersionCRUD() as version_crud:
                    version_record = version_crud.upsert_prompt_version(
                        prompt_db_id=prompt_record.id,
                        version=request.target_version,
                        version_data=final_data,
                    )

                # Update default_version_id if requested
                if request.set_as_default:
                    with PromptCRUD() as prompt_crud:
                        prompt_record.default_version_id = version_record.id
                        prompt_crud.update(data=prompt_record, conditions={"id": prompt_record.id})

                    logger.debug(
                        f"Database: Stored copied prompt {request.target_prompt_id}:v{request.target_version} "
                        f"and set as default (version_id: {version_record.id})"
                    )
                else:
                    logger.debug(
                        f"Database: Stored copied prompt {request.target_prompt_id}:v{request.target_version}"
                    )

            except Exception as db_error:
                # Log warning but don't fail the request (eventual consistency)
                logger.warning(
                    f"Failed to persist copied prompt to database: {str(db_error)}. "
                    f"Redis operation succeeded, but database sync failed for "
                    f"{request.target_prompt_id}:v{request.target_version}"
                )

            # Remove target from cleanup registry if exists (permanent prompts don't need cleanup)
            await self._remove_from_cleanup_registry(target_key)

            # Check if source is in cleanup registry
            source_registry_entry_json = await self.redis_service.hget(CLEANUP_REGISTRY_KEY, source_key)

            # If source is temporary, remove MCP resources from cleanup registry
            # This preserves shared MCP resources while allowing prompt config cleanup
            if source_registry_entry_json:
                # Decode bytes if needed
                if isinstance(source_registry_entry_json, bytes):
                    source_registry_entry_json = source_registry_entry_json.decode("utf-8")

                # Load and validate using Pydantic model
                source_registry_entry = MCPCleanupRegistryEntry.model_validate_json(source_registry_entry_json)

                # Clear mcp_resources to prevent cleanup from deleting shared resources
                source_registry_entry.mcp_resources = {"virtual_server_id": None, "gateways": {}}

                # Serialize using Pydantic and update registry
                updated_entry_json = source_registry_entry.model_dump_json()
                await self.redis_service.hset(CLEANUP_REGISTRY_KEY, source_key, updated_entry_json)

                logger.debug(
                    "Cleared mcp_resources from cleanup registry for %s - resources now shared with target %s",
                    source_key,
                    target_key,
                )

            # Parse final_data as PromptConfigurationData for response
            final_config_data = PromptConfigurationData.model_validate(final_data)

            return PromptConfigCopyResponse(
                source_prompt_id=request.source_prompt_id,
                source_version=request.source_version,
                target_prompt_id=request.target_prompt_id,
                target_version=request.target_version,
                data=final_config_data,
            )

        except ClientException:
            raise
        except Exception as e:
            logger.exception(f"Failed to copy prompt configuration: {str(e)}")
            raise ClientException(status_code=500, message="Failed to copy prompt configuration") from e

    async def set_default_version(self, prompt_id: str, version: int) -> SuccessResponse:
        """Set a specific version as the default for a prompt configuration.

        Args:
            prompt_id: The prompt ID to set default version for
            version: The version number to set as default

        Returns:
            SuccessResponse indicating successful operation

        Raises:
            ClientException: If the specified version doesn't exist
        """
        # Initialize Redis service
        self.redis_service = RedisService()

        try:
            # Construct the versioned key to check if it exists
            versioned_key = f"prompt:{prompt_id}:v{version}"

            # Check if the specified version exists
            version_data = await self.redis_service.get(versioned_key)
            if not version_data:
                logger.error(f"Version {version} not found for prompt_id: {prompt_id}")
                raise ClientException(
                    status_code=404, message=f"Version {version} not found for prompt_id: {prompt_id}"
                )

            # Set the default version pointer
            default_key = f"prompt:{prompt_id}:default_version"
            await self.redis_service.set(default_key, versioned_key)
            logger.debug(f"Set version key {versioned_key} as default for prompt_id: {prompt_id}")

            # Update database if this is a permanent prompt (exists in database)
            try:
                with PromptCRUD() as prompt_crud:
                    prompt_record = prompt_crud.fetch_one(conditions={"name": prompt_id})

                if prompt_record:
                    # This is a permanent prompt, validate version exists in database
                    with PromptVersionCRUD() as version_crud:
                        version_record = version_crud.fetch_one(
                            conditions={"prompt_id": prompt_record.id, "version": version}
                        )

                    if version_record:
                        # Update default_version_id in database
                        with PromptCRUD() as prompt_crud:
                            prompt_record.default_version_id = version_record.id
                            prompt_crud.update(data=prompt_record, conditions={"id": prompt_record.id})

                        logger.debug(
                            f"Database: Updated default version for {prompt_id} to v{version} "
                            f"(version_id: {version_record.id})"
                        )
                    else:
                        logger.warning(
                            f"Version {version} exists in Redis but not in database for {prompt_id}. "
                            f"Skipping database update (inconsistent state)."
                        )
                else:
                    # Temporary prompt (not in database), skip database update
                    logger.debug(
                        f"Prompt {prompt_id} not found in database, skipping database update (temporary prompt)"
                    )

            except Exception as db_error:
                # Log warning but don't fail the request (eventual consistency)
                logger.warning(
                    f"Failed to update default version in database: {str(db_error)}. "
                    f"Redis operation succeeded for {prompt_id}:v{version}"
                )

            return SuccessResponse(message=f"Successfully set version {version} as default for prompt_id: {prompt_id}")

        except ClientException:
            raise
        except Exception as e:
            logger.exception(f"Failed to set default version: {str(e)}")
            raise ClientException(status_code=500, message="Failed to set default version") from e

    async def delete_prompt_config(self, prompt_id: str, version: Optional[int] = None) -> SuccessResponse:
        """Delete prompt configuration(s) from Redis.

        Args:
            prompt_id: The prompt ID to delete
            version: Optional specific version to delete. If not provided, deletes all versions.

        Returns:
            SuccessResponse indicating successful deletion

        Raises:
            ClientException: If configuration not found or if trying to delete default version
        """
        # Initialize Redis service
        self.redis_service = RedisService()

        try:
            if version is not None:
                # Delete specific version
                versioned_key = f"prompt:{prompt_id}:v{version}"

                # Check if the version exists
                version_data = await self.redis_service.get(versioned_key)
                if not version_data:
                    logger.error(f"Version {version} not found for prompt_id: {prompt_id}")
                    raise ClientException(
                        status_code=404, message=f"Version {version} not found for prompt_id: {prompt_id}"
                    )

                # Check if this version is the current default
                default_key = f"prompt:{prompt_id}:default_version"
                current_default = await self.redis_service.get(default_key)

                if current_default and current_default.decode("utf-8") == versioned_key:
                    logger.error(
                        f"Cannot delete version {version} as it is the current default for prompt_id: {prompt_id}"
                    )
                    raise ClientException(
                        status_code=400,
                        message=f"Cannot delete version {version} as it is the current default version",
                    )

                # Delete the specific version
                await self.redis_service.delete(versioned_key)
                logger.debug(f"Deleted version {version} for prompt_id: {prompt_id}")

                # Delete from database if permanent prompt
                try:
                    with PromptCRUD() as prompt_crud:
                        prompt_record = prompt_crud.fetch_one(conditions={"name": prompt_id})

                    if prompt_record:
                        with PromptVersionCRUD() as version_crud:
                            version_crud.delete(conditions={"prompt_id": prompt_record.id, "version": version})

                        logger.debug(f"Database: Deleted version {version} for prompt '{prompt_id}'")

                        # Check if any versions remain for this prompt
                        with PromptVersionCRUD() as version_crud:
                            remaining_versions = version_crud.count_versions(prompt_record.id)

                        if remaining_versions == 0:
                            with PromptCRUD() as prompt_crud:
                                prompt_crud.delete(conditions={"id": prompt_record.id})

                            logger.info(f"Database: Auto-deleted prompt '{prompt_id}' as it had no remaining versions")
                    else:
                        logger.debug(f"Prompt '{prompt_id}' not found in database, skipping database deletion ")

                except Exception as db_error:
                    logger.warning(
                        f"Failed to delete version {version} from database for prompt '{prompt_id}': {str(db_error)}. "
                    )

                return SuccessResponse(message=f"Successfully deleted version {version} for prompt_id: {prompt_id}")

            else:
                # Delete all versions and default key
                pattern = f"prompt:{prompt_id}:v*"
                deleted_count = await self.redis_service.delete_keys_by_pattern(pattern)

                # Also delete the default version key
                default_key = f"prompt:{prompt_id}:default_version"
                default_deleted = await self.redis_service.delete(default_key)

                total_deleted = deleted_count + default_deleted

                if total_deleted == 0:
                    logger.error(f"No configurations found for prompt_id: {prompt_id}")
                    raise ClientException(
                        status_code=404, message=f"No configurations found for prompt_id: {prompt_id}"
                    )

                logger.debug(f"Deleted all {total_deleted} configurations for prompt_id: {prompt_id}")

                # Delete from database if permanent prompt
                try:
                    with PromptCRUD() as prompt_crud:
                        prompt_record = prompt_crud.fetch_one(conditions={"name": prompt_id})

                    if prompt_record:
                        with PromptCRUD() as prompt_crud:
                            prompt_crud.delete(conditions={"id": prompt_record.id})

                        logger.debug(f"Database: Deleted prompt '{prompt_id}' and all associated versions ")
                    else:
                        logger.debug(f"Prompt '{prompt_id}' not found in database, skipping database deletion ")

                except Exception as db_error:
                    logger.warning(f"Failed to delete prompt '{prompt_id}' from database: {str(db_error)}. ")

                return SuccessResponse(message=f"Successfully deleted all configurations for prompt_id: {prompt_id}")

        except ClientException:
            raise
        except Exception as e:
            logger.exception(f"Failed to delete prompt configuration: {str(e)}")
            raise ClientException(status_code=500, message="Failed to delete prompt configuration") from e


class PromptCleanupService:
    """Service for cleaning up MCP resources from expired prompts."""

    @staticmethod
    def get_cleanup_targets(
        workflow_id: str,
        notification_request: NotificationRequest,
        prompts: Optional[list[Dict[str, Any]]],
        target_topic_name: Optional[str] = None,
        target_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Determine which prompts need cleanup.

        If prompts list is None/empty, scan registry for expired prompts.
        If prompts list provided, use those specific prompts.

        Returns dict with cleanup_targets list.
        """
        redis_service = RedisService()

        # Send notification
        notification_req = notification_request.model_copy(deep=True)
        notification_req.payload.event = "identifying_targets"
        notification_req.payload.content = NotificationContent(
            title="Identifying Cleanup Targets",
            message="Determining which prompts need cleanup",
            status=WorkflowStatus.STARTED,
        )
        dapr_workflow.publish_notification(
            workflow_id=workflow_id,
            notification=notification_req,
            target_topic_name=target_topic_name,
            target_name=target_name,
        )

        # Condition 1: Specific prompts provided
        if prompts:
            cleanup_targets = []
            for prompt in prompts:
                prompt_id = prompt["prompt_id"]
                version = prompt.get("version", 1)
                redis_key = f"prompt:{prompt_id}:v{version}"

                cleanup_targets.append({"prompt_key": redis_key, "prompt_id": prompt_id, "version": version})

            logger.debug(f"Cleanup targets: {len(cleanup_targets)} specific prompts")
            return cleanup_targets

        # Condition 2: Cleanup expired prompts
        # Read all hash fields atomically
        registry_hash = run_async(redis_service.hgetall(CLEANUP_REGISTRY_KEY))
        if not registry_hash:
            logger.debug("No cleanup registry found")
            return []

        # Iterate hash and decode
        now = datetime.now(timezone.utc)
        expired_targets = []

        for prompt_key_bytes, entry_json_bytes in registry_hash.items():
            # Decode bytes to strings
            prompt_key = prompt_key_bytes.decode("utf-8") if isinstance(prompt_key_bytes, bytes) else prompt_key_bytes
            entry_json = entry_json_bytes.decode("utf-8") if isinstance(entry_json_bytes, bytes) else entry_json_bytes

            # Parse entry
            entry = json.loads(entry_json)
            expires_at = datetime.fromisoformat(entry["expires_at"])

            if expires_at < now:
                expired_targets.append(
                    {
                        "prompt_key": prompt_key,
                        "prompt_id": entry["prompt_id"],
                        "version": entry["version"],
                    }
                )

        logger.debug(f"Cleanup targets: {len(expired_targets)} expired prompts")
        return expired_targets

    @staticmethod
    def cleanup_resources(
        workflow_id: str,
        notification_request: NotificationRequest,
        cleanup_targets: list[Dict[str, Any]],
        target_topic_name: Optional[str] = None,
        target_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Cleanup MCP resources for target prompts.

        For each target:
        1. Check if registry entry exists
        2. If not exists: log error, mark success, continue
        3. If exists: extract mcp_resources
        4. Delete gateways (if any)
        5. Delete virtual server (if exists)
        6. Delete Redis prompt config
        7. Remove from registry on success, mark failed on error
        """
        redis_service = RedisService()
        results = {"success": [], "failed": []}

        # Send notification
        notification_req = notification_request.model_copy(deep=True)
        notification_req.payload.event = "cleaning_resources"
        notification_req.payload.content = NotificationContent(
            title="Cleaning Up Resources",
            message=f"Processing {len(cleanup_targets)} prompts",
            status=WorkflowStatus.STARTED,
        )
        dapr_workflow.publish_notification(
            workflow_id=workflow_id,
            notification=notification_req,
            target_topic_name=target_topic_name,
            target_name=target_name,
        )

        # Process each prompt with atomic operations (no upfront registry load)
        for target in cleanup_targets:
            prompt_key = target["prompt_key"]
            prompt_id = target["prompt_id"]
            version = target["version"]
            cleanup_errors = []

            try:
                # Atomic read of single entry
                registry_entry_json = run_async(redis_service.hget(CLEANUP_REGISTRY_KEY, prompt_key))

                if not registry_entry_json:
                    logger.error(f"Cleanup registry entry not found for {prompt_key}")
                    results["success"].append({"prompt_id": prompt_id, "version": version})
                    continue

                # Decode and parse
                if isinstance(registry_entry_json, bytes):
                    registry_entry_json = registry_entry_json.decode("utf-8")
                registry_entry = json.loads(registry_entry_json)

                # Extract MCP resources
                mcp_resources = registry_entry.get("mcp_resources", {})

                # Delete gateways
                if mcp_resources.get("gateways"):
                    for _connector_id, gateway_id in mcp_resources["gateways"].items():
                        try:
                            mcp_foundry_service.delete_gateway_sync(gateway_id)
                            logger.debug(f"Deleted gateway {gateway_id} for {prompt_key}")
                        except Exception as e:
                            logger.error(f"Failed to delete gateway {gateway_id}: {e}")
                            cleanup_errors.append(f"gateway_{gateway_id}: {str(e)}")

                # Delete virtual server
                if mcp_resources.get("virtual_server_id"):
                    try:
                        mcp_foundry_service.delete_virtual_server_sync(mcp_resources["virtual_server_id"])
                        logger.debug(f"Deleted virtual server {mcp_resources['virtual_server_id']}")
                    except Exception as e:
                        logger.error(f"Failed to delete virtual server: {e}")
                        cleanup_errors.append(f"virtual_server: {str(e)}")

                # Delete prompt config
                prompt_exists = run_async(redis_service.get(prompt_key))
                if prompt_exists:
                    run_async(redis_service.delete(prompt_key))
                    logger.debug(f"Deleted Redis key {prompt_key}")

                # Atomic update based on outcome
                if cleanup_errors:
                    # Update entry with error info
                    registry_entry["cleanup_failed"] = True
                    registry_entry["reason"] = "; ".join(cleanup_errors)
                    updated_entry_json = json.dumps(registry_entry)
                    run_async(redis_service.hset(CLEANUP_REGISTRY_KEY, prompt_key, updated_entry_json))

                    logger.error(f"Cleanup failed for {prompt_key}: {'; '.join(cleanup_errors)}")
                    results["failed"].append(
                        {"prompt_id": prompt_id, "version": version, "reason": "; ".join(cleanup_errors)}
                    )
                else:
                    # Atomic delete on success
                    run_async(redis_service.hdel(CLEANUP_REGISTRY_KEY, prompt_key))

                    logger.info(f"Cleaned up {prompt_key} successfully")
                    results["success"].append({"prompt_id": prompt_id, "version": version})

            except Exception as e:
                logger.error(f"Cleanup failed for {prompt_key}: {e}")

                # Try to mark as failed in registry
                try:
                    current_entry_json = run_async(redis_service.hget(CLEANUP_REGISTRY_KEY, prompt_key))
                    if current_entry_json:
                        if isinstance(current_entry_json, bytes):
                            current_entry_json = current_entry_json.decode("utf-8")
                        current_entry = json.loads(current_entry_json)
                        current_entry["cleanup_failed"] = True
                        current_entry["reason"] = str(e)
                        updated_entry_json = json.dumps(current_entry)
                        run_async(redis_service.hset(CLEANUP_REGISTRY_KEY, prompt_key, updated_entry_json))
                except Exception as update_error:
                    logger.error(f"Failed to update registry for {prompt_key}: {update_error}")

                results["failed"].append({"prompt_id": prompt_id, "version": version, "reason": str(e)})

        logger.info(f"Cleanup complete. Success: {len(results['success'])}, Failed: {len(results['failed'])}")
        return results

    def __call__(self, request: PromptCleanupRequest, workflow_id: Optional[str] = None) -> PromptCleanupResponse:
        """Execute the prompt cleanup process.

        This method provides synchronous execution for debug mode.
        Follows the same pattern as PromptConfigurationService.__call__.

        Args:
            request: The cleanup request
            workflow_id: Optional workflow ID for tracking

        Returns:
            PromptCleanupResponse with cleanup results
        """
        if not workflow_id:
            workflow_id = str(uuid.uuid4())

        workflow_name = "perform_prompt_cleanup"
        notification_request = NotificationRequest.from_cloud_event(
            cloud_event=request,
            name=workflow_name,
            workflow_id=workflow_id,
        )

        prompts_list = [p.model_dump() for p in request.prompts] if request.prompts else None
        cleanup_data = self.get_cleanup_targets(
            workflow_id,
            notification_request,
            prompts_list,
            request.source_topic,
            request.source,
        )

        # 4. Call cleanup_resources
        results = self.cleanup_resources(
            workflow_id,
            notification_request,
            cleanup_data,
            request.source_topic,
            request.source,
        )

        # 5. Create response
        response = PromptCleanupResponse(
            workflow_id=workflow_id,
            cleaned=results["success"],
            failed=results["failed"],
        )

        # 6. Send final notification
        notification_request.payload.event = "results"
        notification_request.payload.content = NotificationContent(
            title="Prompt Cleanup Results",
            message=f"Cleaned {len(results['success'])} prompts, {len(results['failed'])} failed",
            result=response.model_dump(mode="json"),
            status=WorkflowStatus.COMPLETED,
        )

        dapr_workflow.publish_notification(
            workflow_id=workflow_id,
            notification=notification_request,
            target_topic_name=request.source_topic,
            target_name=request.source,
        )

        return response
