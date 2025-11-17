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

"""Prompt executors for running AI prompts."""

import json
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional, Type, Union

from budmicroframe.commons import logging
from pydantic import BaseModel, ValidationError
from pydantic_ai import Agent
from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    UserPromptPart,
)
from pydantic_ai.models.openai import ModelSettings as OpenAIModelSettings
from pydantic_ai.output import NativeOutput

from budprompt.commons.exceptions import (
    PromptExecutionException,
    SchemaGenerationException,
    TemplateRenderingException,
)
from budprompt.shared.providers import BudServeProvider

from ...prompt.schemas import Message, ModelSettings
from .schema_builder import DataModelGenerator
from .streaming_executors import execute_streaming_validation
from .streaming_validation import add_field_validator_to_model
from .template_renderer import render_template
from .utils import contains_pydantic_model, validate_input_data_type
from .validation import add_validator_to_model_async


logger = logging.get_logger(__name__)


class SimplePromptExecutorDeprecated:
    """Executor for simple prompt execution with Pydantic AI.

    This executor handles the conversion of JSON schemas to Pydantic models,
    creates AI agents, and executes prompts with structured input/output.
    """

    def __init__(self):
        """Initialize the SimplePromptExecutor."""
        self.provider = BudServeProvider()
        self.model_generator = DataModelGenerator()

    async def execute(
        self,
        deployment_name: str,
        model_settings: ModelSettings,
        input_schema: Optional[Dict[str, Any]],
        output_schema: Optional[Dict[str, Any]],
        messages: List[Message],
        input_data: Optional[Union[Dict[str, Any], str]] = None,
        stream: bool = False,
        output_validation_prompt: Optional[str] = None,
        input_validation_prompt: Optional[str] = None,
        llm_retry_limit: Optional[int] = 3,
        enable_tools: bool = False,
        allow_multiple_calls: bool = True,
        system_prompt_role: Optional[str] = None,
    ) -> Union[Dict[str, Any], str, AsyncGenerator[str, None]]:
        """Execute a prompt with structured or unstructured input and output.

        Args:
            deployment_name: Name of the model deployment
            model_settings: Model configuration settings
            input_schema: JSON schema for input validation (None for unstructured)
            output_schema: JSON schema for output structure (None for unstructured)
            messages: List of messages for context (can include system/developer messages)
            input_data: Input data to process (Dict for structured, str for unstructured)
            stream: Whether to stream the response
            output_validation_prompt: Natural language validation rules for output
            input_validation_prompt: Natural language validation rules for input
            llm_retry_limit: Number of LLM retries when validation fails
            enable_tools: Enable tool calling capability (requires allow_multiple_calls=true)
            allow_multiple_calls: Allow multiple LLM calls for retries and tools
            system_prompt_role: Role for system prompts (system/developer/user)

        Returns:
            Output data (Dict for structured, str for unstructured) or AsyncGenerator for streaming

        Raises:
            SchemaGenerationException: If schema conversion fails
            ValidationError: If input validation fails
            PromptExecutionException: If prompt execution fails
        """
        try:
            # Validate input data type matches schema presence
            validate_input_data_type(input_data, input_schema)

            # Handle input validation
            validated_input = None
            if input_schema is not None and input_data is not None:
                # Structured input: create model with validation and validate
                input_model = await self._get_input_model_with_validation(input_schema, input_validation_prompt)
                try:
                    validated_input = input_model.model_validate(input_data)
                except ValidationError:
                    # Let the ValidationError bubble up directly
                    raise
            else:
                # Unstructured input: use string directly
                validated_input = input_data

            # Prepare context for template rendering
            context = self._prepare_template_context(validated_input, input_schema is not None)

            # Handle output type and validation (only for non-streaming with Pydantic models)
            output_type = await self._get_output_type(output_schema, output_validation_prompt, stream)

            # Create AI agent with appropriate output type and retry configuration
            agent = await self._create_agent(
                deployment_name,
                model_settings,
                output_type,
                llm_retry_limit if output_validation_prompt and not stream else None,
                allow_multiple_calls,
                system_prompt_role,
            )

            # Build message history from all messages
            message_history = self._build_message_history(messages, context)

            # Get user prompt from input_data
            user_prompt = self._prepare_user_prompt(input_data)

            # Check if streaming is requested
            if stream:
                # Check if streaming validation is needed
                if output_validation_prompt and output_schema and contains_pydantic_model(output_type):
                    logger.debug(f"Using streaming validation for: {output_validation_prompt}")
                    # Use streaming validation executor with the enhanced model
                    # The model already has field validators added in _get_output_type
                    return execute_streaming_validation(
                        enhanced_model=output_type,  # Pass the already enhanced model
                        pydantic_schema=output_schema,
                        prompt=user_prompt or "",
                        validation_prompt=output_validation_prompt,
                        deployment_name=deployment_name,
                        model_settings=model_settings.model_dump(exclude_none=True) if model_settings else None,
                        llm_retry_limit=llm_retry_limit or 3,
                        messages=message_history,
                        system_prompt_role=system_prompt_role,
                    )
                else:
                    # Regular streaming without validation
                    logger.debug(
                        f"Using regular streaming - validation_prompt={bool(output_validation_prompt)}, schema={bool(output_schema)}, contains_pydantic={contains_pydantic_model(output_type) if output_type else False}"
                    )
                    return self._run_agent_stream(agent, user_prompt, message_history, output_schema)
            else:
                # Execute the agent with both history and current prompt
                return await self._run_agent(agent, user_prompt, message_history, output_schema)

        except (SchemaGenerationException, ValidationError, PromptExecutionException, TemplateRenderingException):
            raise
        except Exception as e:
            logger.error(f"Prompt execution failed: {str(e)}")
            raise PromptExecutionException("Failed to execute prompt") from e

    async def _get_output_type(
        self,
        output_schema: Optional[Dict[str, Any]],
        output_validation_prompt: Optional[str] = None,
        stream: bool = False,
    ) -> Any:
        """Extract output type from schema's content field and apply validation if needed.

        Args:
            output_schema: JSON schema with content field
            output_validation_prompt: Natural language validation rules
            stream: Whether streaming is enabled

        Returns:
            The type of the content field, potentially enhanced with validation,
            wrapped in NativeOutput if it contains BaseModel
        """
        if output_schema is None:
            return str

        # Generate Pydantic model from schema
        output_model = await self._get_pydantic_model(output_schema, "OutputModel")

        # Extract type from content field using Pydantic v2 field access
        output_type = output_model.__pydantic_fields__["content"].annotation

        # Check if we should add validation for both streaming and non-streaming
        if output_validation_prompt and contains_pydantic_model(output_type):
            logger.debug(f"Adding validation to output model: {output_validation_prompt}")

            # If output_type is a Pydantic model, enhance it with validation
            if isinstance(output_type, type) and issubclass(output_type, BaseModel):
                if stream:
                    # For streaming, use field validators for early validation
                    output_type = await add_field_validator_to_model(output_type, output_validation_prompt)
                    logger.debug(f"Enhanced model with field validator for streaming: {output_type.__name__}")
                else:
                    # For non-streaming, use model validators
                    output_type = await add_validator_to_model_async(output_type, output_validation_prompt)
                    logger.debug(f"Enhanced model with model validator: {output_type.__name__}")

        # Return NativeOutput if type contains BaseModel, otherwise return raw type
        if contains_pydantic_model(output_type):
            return NativeOutput(output_type)
        else:
            return output_type

    async def _get_input_model_with_validation(
        self,
        input_schema: Dict[str, Any],
        input_validation_prompt: Optional[str] = None,
    ) -> Type[BaseModel]:
        """Get input model with optional validation enhancement.

        Args:
            input_schema: JSON schema for input validation
            input_validation_prompt: Natural language validation rules

        Returns:
            Input model class, potentially enhanced with validation
        """
        # Generate base model from schema
        input_model = await self._get_pydantic_model(input_schema, "InputModel")
        input_model = input_model.__pydantic_fields__["content"].annotation

        # Check if we should add validation
        if input_validation_prompt:
            logger.debug(f"Adding validation to input model: {input_validation_prompt}")
            # Enhance with validation using existing function
            input_model = await add_validator_to_model_async(input_model, input_validation_prompt)
            logger.debug(f"Enhanced input model with validation: {input_model.__name__}")

        return input_model

    async def _get_pydantic_model(self, schema: Dict[str, Any], model_name: str) -> Type[BaseModel]:
        """Convert JSON schema to Pydantic model.

        Args:
            schema: JSON schema dictionary
            model_name: Name for the generated model

        Returns:
            Pydantic model class

        Raises:
            SchemaGenerationException: If conversion fails
        """
        # Use the model generator to create Pydantic model from schema
        return self.model_generator.from_json_schema(schema, model_name)

    def _convert_to_openai_settings(self, model_settings: ModelSettings) -> OpenAIModelSettings:
        """Convert ModelSettings to OpenAIModelSettings with automatic extra_body routing.

        Parameters not in OpenAIModelSettings are automatically routed to extra_body.

        Args:
            model_settings: Our ModelSettings with all parameters

        Returns:
            OpenAIModelSettings with BudEcosystem params in extra_body
        """
        # Get all fields from OpenAIModelSettings using the __annotations__
        openai_fields = set(OpenAIModelSettings.__annotations__.keys())

        # Get our settings as dict, excluding None values
        all_settings = model_settings.model_dump(exclude_none=True)

        # Separate OpenAI settings from extra settings
        openai_settings = {}
        extra_settings = {}

        for key, value in all_settings.items():
            if key == "stop_sequences":
                # Special case: rename to 'stop' for OpenAI
                openai_settings["stop"] = value
            elif key in openai_fields:
                openai_settings[key] = value
            else:
                # Everything else goes to extra_body
                extra_settings[key] = value

        # Add extra settings to extra_body if any exist
        if extra_settings:
            openai_settings["extra_body"] = extra_settings

        return OpenAIModelSettings(**openai_settings)

    async def _create_agent(
        self,
        deployment_name: str,
        model_settings: ModelSettings,
        output_type: Union[Type[BaseModel], Type[str], NativeOutput],
        llm_retry_limit: Optional[int] = None,
        allow_multiple_calls: bool = True,
        system_prompt_role: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> Agent:
        """Create Pydantic AI agent with automatic parameter routing.

        Args:
            deployment_name: Model deployment name
            model_settings: Model configuration with all parameters
            output_type: Output type (Pydantic model for structured, str for unstructured)
            llm_retry_limit: Number of retries for validation failures
            allow_multiple_calls: Whether to allow multiple LLM calls
            system_prompt_role: Role for system prompts (system/developer/user)
            api_key: Optional API key for authorization

        Returns:
            Configured AI agent
        """
        # Convert our ModelSettings to OpenAIModelSettings
        # This automatically routes BudEcosystem parameters to extra_body
        openai_settings = self._convert_to_openai_settings(model_settings)

        # Create provider with api_key (handles None internally)
        provider = BudServeProvider(api_key=api_key)

        # Create model using BudServeProvider with system_prompt_role
        model = provider.get_model(
            model_name=deployment_name, system_prompt_role=system_prompt_role, settings=openai_settings
        )

        # Create agent with output type and optional retry configuration
        # Note: system_prompt is not passed here - it will be added to message_history instead
        # This is because pydantic-ai ignores system_prompt when message_history is provided
        agent_kwargs = {
            "model": model,
            "output_type": output_type,
        }

        # Add retries if validation is enabled
        if llm_retry_limit is not None:
            agent_kwargs["retries"] = llm_retry_limit
            logger.debug(f"Agent configured with {llm_retry_limit} retries for validation")
        # Override to force no retries if multiple calls are not allowed
        if not allow_multiple_calls:
            agent_kwargs["retries"] = 0
            logger.debug("Agent configured with 0 retries (allow_multiple_calls=False, overriding any retry settings)")

        agent = Agent(**agent_kwargs)

        return agent

    def _prepare_template_context(self, input_data: Any, is_structured: bool) -> Dict[str, Any]:
        """Prepare context for Jinja2 template rendering.

        Args:
            input_data: Validated input data
            is_structured: Whether the input is structured

        Returns:
            Context dictionary for template rendering
        """
        context = {}

        if input_data is not None:
            if is_structured and hasattr(input_data, "model_dump"):
                # Structured input: use model fields as context
                context = input_data.model_dump()
            elif isinstance(input_data, dict):
                # Direct dict input
                context = input_data
            elif isinstance(input_data, str):
                # Unstructured string input
                context["input"] = input_data

        return context

    def _build_message_history(self, messages: List[Message], context: Dict[str, Any]) -> List[ModelMessage]:
        """Build message history from messages list.

        Args:
            messages: List of messages with roles and content
            context: Context for template rendering

        Returns:
            List of Pydantic AI ModelMessage objects
        """
        message_history = []

        # Process all messages
        for msg in messages:
            # Render message content with Jinja2
            rendered_content = render_template(msg.content, context)

            if msg.role in ["system", "developer"]:
                # System and developer messages both use SystemPromptPart
                # The actual OpenAI role (system/developer) is controlled by system_prompt_role
                message_history.append(ModelRequest(parts=[SystemPromptPart(content=rendered_content)]))
            elif msg.role == "user":
                # Create user message
                message_history.append(ModelRequest(parts=[UserPromptPart(content=rendered_content)]))
            elif msg.role == "assistant":
                # Create assistant message
                message_history.append(
                    ModelResponse(
                        parts=[TextPart(content=rendered_content)],
                        timestamp=datetime.now(timezone.utc),
                    )
                )

        return message_history

    def _prepare_user_prompt(self, input_data: Optional[Union[Dict[str, Any], str]]) -> Optional[str]:
        """Prepare the user prompt from input data.

        Args:
            input_data: The input data from the request (string or dict)

        Returns:
            The user prompt as a string, or None if no input data
        """
        if input_data is None:
            return None
        elif isinstance(input_data, str):
            return input_data
        else:
            # Convert dict to JSON string for structured input
            return json.dumps(input_data)

    async def _run_agent(
        self,
        agent: Agent,
        user_prompt: Optional[str],
        message_history: List[ModelMessage],
        output_schema: Optional[Dict[str, Any]],
    ) -> Any:
        """Run the agent with message history and current prompt.

        Args:
            agent: Configured AI agent
            user_prompt: Current user prompt from input_data
            message_history: Conversation history from messages
            output_schema: Output schema to determine result processing

        Returns:
            Agent execution result (dict for structured, string for unstructured)

        Raises:
            PromptExecutionException: If execution fails
        """
        try:
            # Always pass both user_prompt and message_history
            # Pydantic AI will handle None user_prompt appropriately
            result = await agent.run(
                user_prompt=user_prompt,
                message_history=message_history,
            )
            logger.debug("================================================")
            logger.debug("Pydantic AI execution result: %s", result.all_messages())
            logger.debug("================================================")

            # Process and return result based on output schema
            if output_schema is not None:
                # Structured output: return as dict
                return result.output.model_dump() if hasattr(result.output, "model_dump") else result.output
            else:
                # Unstructured output: return as string
                return result.output
        except UnexpectedModelBehavior as e:
            # Handle validation retry exhaustion with specific message
            error_msg = str(e)
            if "Exceeded maximum retries" in error_msg:
                # Extract retry count from error message if possible
                logger.error(f"Output validation failed after maximum retries: {error_msg}")
                raise PromptExecutionException(f"Output validation failed: {error_msg}") from e
            else:
                logger.error(f"Unexpected model behavior: {error_msg}")
                raise PromptExecutionException(f"Unexpected model behavior: {error_msg}") from e
        except Exception as e:
            logger.error(f"Agent execution failed: {str(e)}")
            raise PromptExecutionException("Agent execution failed") from e

    async def _run_agent_stream(
        self,
        agent: Agent,
        user_prompt: Optional[str],
        message_history: List[ModelMessage],
        output_schema: Optional[Dict[str, Any]],
    ) -> AsyncGenerator[str, None]:
        """Run agent with streaming and yield SSE-formatted chunks.

        Args:
            agent: Configured AI agent
            user_prompt: Current user prompt from input_data
            message_history: Conversation history from messages
            output_schema: Output schema to determine streaming type

        Yields:
            SSE-formatted string chunks with data: prefix and double newlines
        """
        try:
            # Use async context manager for run_stream
            async with agent.run_stream(user_prompt=user_prompt, message_history=message_history) as stream_result:
                logger.debug("Starting streaming with stream_structured()...")

                # Use stream_structured() for getting structured messages
                # This works for both structured and unstructured outputs
                async for message, last_message in stream_result.stream_structured():
                    logger.debug(f"Received message type: {type(message)}, last_message: {last_message}")

                    # Handle ModelResponse dataclass
                    if isinstance(message, ModelResponse):
                        # Convert ModelResponse to dict using asdict
                        message_dict = asdict(message)
                        message_dict["timestamp"] = datetime.now().isoformat()
                        message_dict["end"] = last_message

                        # Format as SSE with proper data prefix and newlines
                        yield f"data: {json.dumps(message_dict)}\n\n"

        except Exception as e:
            logger.error(f"Error during streaming: {str(e)}")
            # Send error in SSE format
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
