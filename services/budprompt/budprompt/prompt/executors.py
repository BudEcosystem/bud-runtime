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
import logging
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional, Type, Union

from openai.types.responses import (
    ResponseCompletedEvent,
    ResponseCreatedEvent,
    ResponseFailedEvent,
    ResponseInProgressEvent,
)
from pydantic import BaseModel, ValidationError
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelHTTPError, UnexpectedModelBehavior
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    UserPromptPart,
)
from pydantic_ai.models.openai import ModelSettings as OpenAIModelSettings
from pydantic_ai.output import NativeOutput
from pydantic_ai.run import AgentRunResult, AgentRunResultEvent

from budprompt.commons.exceptions import (
    PromptExecutionException,
    SchemaGenerationException,
    TemplateRenderingException,
)
from budprompt.shared.providers import BudServeProvider

from .openai_response_formatter import OpenAIResponseFormatter
from .openai_response_formatter_v1 import OpenAIResponseFormatter_V1
from .openai_streaming_formatter import OpenAIStreamingFormatter
from .openai_streaming_formatter_v1 import OpenAIStreamingFormatter_V1
from .revised_code.field_validation import ModelValidationEnhancer
from .schema_builder import CustomModelGenerator, DataModelGenerator
from .schemas import MCPToolConfig, Message, ModelSettings
from .streaming_executors import execute_streaming_validation
from .streaming_validation import add_field_validator_to_model
from .streaming_validation_executor import StreamingValidationExecutor
from .template_renderer import render_template
from .tool_loaders import ToolRegistry
from .utils import PydanticResultSerializer, contains_pydantic_model, validate_input_data_type
from .validation import add_validator_to_model_async


logger = logging.getLogger(__name__)


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


class SimplePromptExecutor:
    """Executor for simple prompt execution with Pydantic AI.

    This executor handles the conversion of JSON schemas to Pydantic models,
    creates AI agents, and executes prompts with structured input/output.
    """

    def __init__(self):
        """Initialize the SimplePromptExecutor."""
        self.model_generator = CustomModelGenerator()
        self.response_formatter = OpenAIResponseFormatter()

    async def execute(
        self,
        deployment_name: str,
        model_settings: ModelSettings,
        input_schema: Optional[Dict[str, Any]],
        output_schema: Optional[Dict[str, Any]],
        messages: List[Message],
        input_data: Optional[Union[Dict[str, Any], str]] = None,
        stream: bool = False,
        output_validation: Optional[Dict[str, Any]] = None,
        input_validation: Optional[Dict[str, Any]] = None,
        llm_retry_limit: Optional[int] = 3,
        enable_tools: bool = False,
        allow_multiple_calls: bool = True,
        system_prompt_role: Optional[str] = None,
        api_key: Optional[str] = None,
        tools: Optional[List[MCPToolConfig]] = None,
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
            output_validation: Natural language validation rules for output with generated code
            input_validation: Natural language validation rules for input with generated code
            llm_retry_limit: Number of LLM retries when validation fails
            enable_tools: Enable tool calling capability (requires allow_multiple_calls=true)
            allow_multiple_calls: Allow multiple LLM calls for retries and tools
            system_prompt_role: Role for system prompts (system/developer/user)
            api_key: Optional API key for authorization
            tools: Optional list of tool configurations (MCP tools, etc.)

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
                input_model = await self._get_input_model_with_validation(input_schema, input_validation)
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

            # Handle output type and validation
            output_type = await self._get_output_type(output_schema, output_validation)

            # Load toolsets from tools configuration (only if tools are present)
            toolsets = await self._load_toolsets(tools)

            # Create AI agent with appropriate output type and retry configuration
            agent = await self._create_agent(
                deployment_name,
                model_settings,
                output_type,
                llm_retry_limit if output_validation and not stream else None,
                allow_multiple_calls,
                system_prompt_role,
                api_key=api_key,
                toolsets=toolsets,
            )

            # Build message history from all messages
            message_history = self._build_message_history(messages, context)

            # Get user prompt from input_data
            user_prompt = self._prepare_user_prompt(input_data)

            # Check if streaming is requested
            if stream:
                # Check if streaming validation is needed
                if output_validation and output_schema and contains_pydantic_model(output_type):
                    logger.debug("Performing streaming with validation")

                    # # Use streaming validation executor with the enhanced model
                    # # The model already has field validators added in _get_output_type
                    # NOTE: Commented out older implementation (Non openai format)
                    # return execute_streaming_validation(
                    #     enhanced_model=output_type,  # Pass the already enhanced model
                    #     pydantic_schema=output_schema,
                    #     prompt=user_prompt or "",
                    #     validation_prompt=output_validation,
                    #     deployment_name=deployment_name,
                    #     model_settings=model_settings.model_dump(exclude_none=True) if model_settings else None,
                    #     llm_retry_limit=llm_retry_limit or 3,
                    #     messages=message_history,
                    #     system_prompt_role=system_prompt_role,
                    #     api_key=api_key,
                    # )

                    # Extract model from NativeOutput wrapper
                    model_with_validators = output_type.outputs if hasattr(output_type, "outputs") else output_type

                    # Use new clean streaming validation executor
                    executor = StreamingValidationExecutor(
                        output_model=model_with_validators,
                        prompt=user_prompt or "",
                        deployment_name=deployment_name,
                        model_settings=model_settings.model_dump(exclude_none=True) if model_settings else None,
                        validation_prompt=output_validation,
                        retry_limit=llm_retry_limit or 3,
                        messages=messages,
                        message_history=message_history,
                        api_key=api_key,
                    )

                    return executor.stream()
                else:
                    # Regular streaming without validation
                    logger.debug(
                        f"Using regular streaming - validation={bool(output_validation)}, schema={bool(output_schema)}, contains_pydantic={contains_pydantic_model(output_type) if output_type else False}"
                    )
                    return self._run_agent_stream(
                        agent,
                        user_prompt,
                        message_history,
                        output_schema,
                        deployment_name,
                        model_settings,
                        messages,
                    )
            else:
                # Execute the agent with both history and current prompt
                result = await self._run_agent(
                    agent,
                    user_prompt,
                    message_history,
                    output_schema,
                )

                # Format to OpenAI response for non-streaming
                return self.response_formatter.format_response(
                    pydantic_result=result,
                    model_settings=model_settings,
                    messages=messages,
                    deployment_name=deployment_name,
                    tools=tools,
                )

        except (SchemaGenerationException, ValidationError, PromptExecutionException, TemplateRenderingException):
            raise
        except Exception as e:
            logger.exception(f"Prompt execution failed: {str(e)}")
            raise PromptExecutionException("Failed to execute prompt") from e

    async def _get_output_type(
        self,
        output_schema: Optional[Dict[str, Any]],
        output_validation: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Extract output type from schema's content field and apply validation if needed.

        Args:
            output_schema: JSON schema with content field
            output_validation: Natural language validation rules with generated codes
            stream: Whether streaming is enabled

        Returns:
            The type of the content field, potentially enhanced with validation,
            wrapped in NativeOutput if it contains BaseModel
        """
        if output_schema is None:
            return str

        # Generate Pydantic model from schema
        output_model = await self._get_pydantic_model(output_schema, "OutputModel")

        # If we have validation, enhance the entire model hierarchy
        if output_validation:
            logger.debug("Enhancing output model with validation")
            enhanced_models = await ModelValidationEnhancer().enhance_all_models(output_model, output_validation)

            # Get the enhanced OutputModel (the wrapper model)
            output_model = enhanced_models.get("OutputModel", output_model)

        # Extract type from content field using Pydantic v2 field access
        output_type = output_model.__pydantic_fields__["content"].annotation

        # Return NativeOutput if type contains BaseModel, otherwise return raw type
        if contains_pydantic_model(output_type):
            return NativeOutput(output_type)
        else:
            return output_type

    async def _get_input_model_with_validation(
        self,
        input_schema: Dict[str, Any],
        input_validation: Optional[Dict[str, Any]] = None,
    ) -> Type[BaseModel]:
        """Get input model with optional validation enhancement.

        Args:
            input_schema: JSON schema for input validation
            input_validation: Natural language validation rules with generated codes

        Returns:
            Input model class, potentially enhanced with validation
        """
        # Generate base model from schema
        input_model = await self._get_pydantic_model(input_schema, "InputModel")

        # If we have validation, enhance the model
        if input_validation:
            logger.debug("Enhancing input model with validation")
            enhanced_models = await ModelValidationEnhancer().enhance_all_models(input_model, input_validation)

            # Get the enhanced InputModel
            input_model = enhanced_models.get("InputModel", input_model)

        # Extract the content field type (the actual model to validate input against)
        input_model = input_model.__pydantic_fields__["content"].annotation  # noqa: F841

        return input_model  # NOTE: input schema should none for unstructured input, content field required for structured input

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
        return await self.model_generator.from_json_schema(schema, model_name)

    async def _load_toolsets(self, tools: Optional[List[MCPToolConfig]]) -> List[Any]:
        """Load toolsets from tools configuration.

        Args:
            tools: List of tool configurations (MCP, custom, etc.)

        Returns:
            List of loaded toolset objects ready for Agent
        """
        if not tools:
            logger.debug("No tools configuration provided, skipping toolset loading")
            return []

        try:
            # Create tool registry (gets config from app_settings)
            registry = ToolRegistry()

            # Load all tools using registry
            toolsets = await registry.load_all_tools(tools)

            logger.info(f"Successfully loaded {len(toolsets)} toolsets for agent")
            return toolsets

        except Exception as e:
            logger.error(f"Failed to load toolsets: {str(e)}")
            # Don't fail execution if tools can't be loaded - continue without tools
            return []

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
        toolsets: Optional[List[Any]] = None,
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
            toolsets: Optional list of toolsets (e.g., MCP servers) for the agent

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

        # Add toolsets if provided
        if toolsets:
            agent_kwargs["toolsets"] = toolsets
            logger.debug(f"Agent configured with {len(toolsets)} toolsets")

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
            Tuple of (result object, raw output) for further processing

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

            return result
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
        deployment_name: str,
        model_settings: ModelSettings,
        messages: List[Message],
    ) -> AsyncGenerator[str, None]:
        """Run agent with OpenAI-compatible streaming.

        Args:
            agent: Configured AI agent
            user_prompt: Current user prompt from input_data
            message_history: Conversation history from messages
            output_schema: Output schema to determine streaming type
            deployment_name: Model deployment name for response metadata
            model_settings: Model settings for response metadata
            messages: Original input messages for response metadata

        Yields:
            SSE-formatted string chunks matching OpenAI Responses API format
        """
        # Initialize OpenAI streaming formatter
        formatter = OpenAIStreamingFormatter(
            deployment_name=deployment_name, model_settings=model_settings, messages=messages
        )

        try:
            # EVENT 1: response.created (sequence 0)
            yield formatter.format_response_created()

            # EVENT 2: response.in_progress (sequence 1)
            yield formatter.format_response_in_progress()

            # EVENT 3: response.output_item.added (sequence 2)
            yield formatter.format_output_item_added()

            # EVENT 4: response.content_part.added (sequence 3)
            yield formatter.format_content_part_added()

            # Track final usage
            final_usage = None

            # Stream pydantic-ai responses
            async with agent.run_stream(user_prompt=user_prompt, message_history=message_history) as stream_result:
                logger.debug("Starting OpenAI-compatible streaming...")

                async for message, last_message in stream_result.stream_structured():
                    logger.debug(f"Received message type: {type(message)}, last_message: {last_message}")

                    if isinstance(message, ModelResponse):
                        # Update model name if available
                        if message.model_name:
                            formatter.update_model_name(message.model_name)

                        # Process each part in the ModelResponse
                        for part in message.parts:
                            if isinstance(part, TextPart):
                                # EVENTS 5+: response.output_text.delta (multiple)
                                if part.content:
                                    delta_event = formatter.format_output_text_delta(part.content)
                                    if delta_event:  # Only yield if there's new content
                                        yield delta_event

                            elif isinstance(part, ThinkingPart):
                                # Handle reasoning/thinking streaming
                                if part.content:
                                    # First time seeing thinking? Emit .added event
                                    if not formatter.reasoning_started:
                                        yield formatter.format_reasoning_summary_part_added()
                                        formatter.reasoning_started = True

                                    # Emit delta event for thinking content
                                    delta_event = formatter.format_reasoning_summary_text_delta(part.content)
                                    if delta_event:
                                        yield delta_event

                                    # Also accumulate for final response.completed summary
                                    formatter.add_thinking_content(part.content)

                            elif isinstance(part, ToolCallPart):
                                # TODO: Handle tool calls in future
                                # Would emit response.function_call_arguments.delta
                                logger.debug(f"Tool call detected: {part.tool_name} (not yet streamed)")

                        # Capture final usage from last message
                        if last_message and message.usage:
                            final_usage = message.usage

            # If we had reasoning, emit done events
            if formatter.reasoning_started:
                # REASONING EVENT 1: response.reasoning_summary_text.done
                yield formatter.format_reasoning_summary_text_done()

                # REASONING EVENT 2: response.reasoning_summary_part.done
                yield formatter.format_reasoning_summary_part_done()

            # EVENT N+1: response.output_text.done
            yield formatter.format_output_text_done()

            # EVENT N+2: response.content_part.done
            yield formatter.format_content_part_done()

            # EVENT N+3: response.output_item.done
            yield formatter.format_output_item_done()

            # EVENT N+4: response.completed (with usage)
            yield formatter.format_response_completed(final_usage)

        except Exception as e:
            logger.error(f"Error during streaming: {str(e)}")
            # ERROR EVENT: response.failed
            yield formatter.format_response_failed(str(e))


class SimplePromptExecutor_V1:
    """Executor for simple prompt execution with Pydantic AI.

    This executor handles the conversion of JSON schemas to Pydantic models,
    creates AI agents, and executes prompts with structured input/output.
    """

    def __init__(self):
        """Initialize the SimplePromptExecutor."""
        self.model_generator = CustomModelGenerator()
        self.response_formatter = OpenAIResponseFormatter_V1()

    async def execute(
        self,
        deployment_name: str,
        model_settings: ModelSettings,
        input_schema: Optional[Dict[str, Any]],
        output_schema: Optional[Dict[str, Any]],
        messages: List[Message],
        input_data: Optional[Union[Dict[str, Any], str]] = None,
        stream: bool = False,
        output_validation: Optional[Dict[str, Any]] = None,
        input_validation: Optional[Dict[str, Any]] = None,
        llm_retry_limit: Optional[int] = 3,
        enable_tools: bool = False,
        allow_multiple_calls: bool = True,
        system_prompt_role: Optional[str] = None,
        api_key: Optional[str] = None,
        tools: Optional[List[MCPToolConfig]] = None,
        system_prompt: Optional[str] = None,
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
            output_validation: Natural language validation rules for output with generated code
            input_validation: Natural language validation rules for input with generated code
            llm_retry_limit: Number of LLM retries when validation fails
            enable_tools: Enable tool calling capability (requires allow_multiple_calls=true)
            allow_multiple_calls: Allow multiple LLM calls for retries and tools
            system_prompt_role: Role for system prompts (system/developer/user)
            api_key: Optional API key for authorization
            tools: Optional list of tool configurations (MCP tools, etc.)
            system_prompt: Optional system prompt with Jinja2 template support

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
                input_model = await self._get_input_model_with_validation(input_schema, input_validation)
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

            # Render system_prompt if provided
            rendered_system_prompt = render_template(system_prompt, context) if system_prompt else None

            # Handle output type and validation
            output_type = await self._get_output_type(output_schema, output_validation, tools)

            # Load toolsets from tools configuration (only if tools are present)
            toolsets = await self._load_toolsets(tools)

            # Create AI agent with appropriate output type and retry configuration
            agent = await self._create_agent(
                deployment_name,
                model_settings,
                output_type,
                llm_retry_limit if output_validation and not stream else None,
                allow_multiple_calls,
                system_prompt_role,
                api_key=api_key,
                toolsets=toolsets,
            )

            # Build message history from all messages
            message_history = self._build_message_history(messages, context, rendered_system_prompt)

            # Get user prompt from input_data
            user_prompt = self._prepare_user_prompt(input_data)

            # Check if streaming is requested
            if stream:
                return self._run_agent_stream(
                    agent,
                    user_prompt,
                    message_history,
                    output_schema,
                    deployment_name,
                    model_settings,
                    messages,
                    tools,
                )
            else:
                # Execute the agent with both history and current prompt
                result = await self._run_agent(
                    agent,
                    user_prompt,
                    message_history,
                    output_schema,
                )

                # Serialize to debug file using custom serializer (for debugging)
                serializer = PydanticResultSerializer()
                serialized_result = serializer.serialize(result)
                with open("latest_pydantic.json", "w") as fp:
                    fp.write(serialized_result.model_dump_json(indent=4))

                # Format to official OpenAI Response
                openai_response = await self.response_formatter.format_response(
                    pydantic_result=result,
                    model_settings=model_settings,
                    messages=messages,
                    deployment_name=deployment_name,
                    tools=tools,
                    output_schema=output_schema,
                )

                return openai_response

        except (SchemaGenerationException, ValidationError, PromptExecutionException, TemplateRenderingException):
            raise
        except Exception as e:
            logger.exception(f"Prompt execution failed: {str(e)}")
            raise PromptExecutionException("Failed to execute prompt") from e

    async def _get_output_type(
        self,
        output_schema: Optional[Dict[str, Any]],
        output_validation: Optional[Dict[str, Any]] = None,
        tools: Optional[List[MCPToolConfig]] = None,
    ) -> Any:
        """Extract output type from schema's content field and apply validation if needed.

        Args:
            output_schema: JSON schema with content field
            output_validation: Natural language validation rules with generated codes
            tools: Optional list of tool configurations (MCP tools, etc.)

        Returns:
            The type of the content field, potentially enhanced with validation,
            wrapped in NativeOutput if it contains BaseModel (unless tools are present)
        """
        if output_schema is None:
            return str

        # Generate Pydantic model from schema
        output_model = await self._get_pydantic_model(output_schema, "OutputModel")

        # If we have validation, enhance the entire model hierarchy
        if output_validation:
            logger.debug("Enhancing output model with validation")
            enhanced_models = await ModelValidationEnhancer().enhance_all_models(output_model, output_validation)

            # Get the enhanced OutputModel (the wrapper model)
            output_model = enhanced_models.get("OutputModel", output_model)

        # Extract type from content field using Pydantic v2 field access
        output_type = output_model.__pydantic_fields__["content"].annotation

        # Return NativeOutput if type contains BaseModel and tools are not present
        # When tools are present, return raw Pydantic model for proper tool handling
        if contains_pydantic_model(output_type) and not (tools and len(tools) > 0):
            logger.debug("Wrapping output model with NativeOutput")
            return NativeOutput(output_type)
        else:
            if tools and len(tools) > 0:
                logger.debug("Tools detected, returning raw Pydantic model without NativeOutput")
                # By default, Pydantic ai use Tool Output https://ai.pydantic.dev/output/#tool-output
            return output_type

    async def _get_input_model_with_validation(
        self,
        input_schema: Dict[str, Any],
        input_validation: Optional[Dict[str, Any]] = None,
    ) -> Type[BaseModel]:
        """Get input model with optional validation enhancement.

        Args:
            input_schema: JSON schema for input validation
            input_validation: Natural language validation rules with generated codes

        Returns:
            Input model class, potentially enhanced with validation
        """
        # Generate base model from schema
        input_model = await self._get_pydantic_model(input_schema, "InputModel")

        # If we have validation, enhance the model
        if input_validation:
            logger.debug("Enhancing input model with validation")
            enhanced_models = await ModelValidationEnhancer().enhance_all_models(input_model, input_validation)

            # Get the enhanced InputModel
            input_model = enhanced_models.get("InputModel", input_model)

        # Extract the content field type (the actual model to validate input against)
        input_model = input_model.__pydantic_fields__["content"].annotation  # noqa: F841

        return input_model  # NOTE: input schema should none for unstructured input, content field required for structured input

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
        return await self.model_generator.from_json_schema(schema, model_name)

    async def _load_toolsets(self, tools: Optional[List[MCPToolConfig]]) -> List[Any]:
        """Load toolsets from tools configuration.

        Args:
            tools: List of tool configurations (MCP, custom, etc.)

        Returns:
            List of loaded toolset objects ready for Agent
        """
        if not tools:
            logger.debug("No tools configuration provided, skipping toolset loading")
            return []

        try:
            # Create tool registry (gets config from app_settings)
            registry = ToolRegistry()

            # Load all tools using registry
            toolsets = await registry.load_all_tools(tools)

            logger.info(f"Successfully loaded {len(toolsets)} toolsets for agent")
            return toolsets

        except Exception as e:
            logger.error(f"Failed to load toolsets: {str(e)}")
            # Don't fail execution if tools can't be loaded - continue without tools
            return []

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
        toolsets: Optional[List[Any]] = None,
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
            toolsets: Optional list of toolsets (e.g., MCP servers) for the agent

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

        # Add toolsets if provided
        if toolsets:
            agent_kwargs["toolsets"] = toolsets
            logger.debug(f"Agent configured with {len(toolsets)} toolsets")

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

    def _build_message_history(
        self, messages: List[Message], context: Dict[str, Any], system_prompt: Optional[str] = None
    ) -> List[ModelMessage]:
        """Build message history from messages list.

        Args:
            messages: List of messages with roles and content
            context: Context for template rendering
            system_prompt: Optional system prompt to prepend as first message

        Returns:
            List of Pydantic AI ModelMessage objects
        """
        message_history = []

        # Prepend system_prompt as first message if provided
        if system_prompt:
            message_history.append(ModelRequest(parts=[SystemPromptPart(content=system_prompt)]))

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
    ) -> AgentRunResult[Any]:
        """Run the agent with message history and current prompt.

        Args:
            agent: Configured AI agent
            user_prompt: Current user prompt from input_data
            message_history: Conversation history from messages
            output_schema: Output schema to determine result processing

        Returns:
            Tuple of (result object, raw output) for further processing

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

            return result
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
        except ModelHTTPError as e:
            # HTTP errors from MCP servers or model providers
            logger.error(f"Received error from model: {str(e)}")
            raise PromptExecutionException(f"Received error from model: {e.message}") from e
        except Exception as e:
            logger.error(f"Agent execution failed: {str(e)}")
            raise PromptExecutionException("Agent execution failed") from e

    async def _run_agent_stream(
        self,
        agent: Agent,
        user_prompt: Optional[str],
        message_history: List[ModelMessage],
        output_schema: Optional[Dict[str, Any]],
        deployment_name: str,
        model_settings: ModelSettings,
        messages: List[Message],
        tools: Optional[List[MCPToolConfig]] = None,
    ) -> AsyncGenerator[str, None]:
        """Run agent with OpenAI-compatible streaming using run_stream_events().

        This implementation uses pydantic-ai's run_stream_events() which executes
        the agent to completion (including all tool calls) while streaming events.

        Args:
            agent: Configured AI agent
            user_prompt: Current user prompt from input_data
            message_history: Conversation history from messages
            output_schema: Output schema to determine streaming type
            deployment_name: Model deployment name for response metadata
            model_settings: Model settings for response metadata
            messages: Original input messages for response metadata
            tools: Optional list of tool configurations (MCP, etc.)

        Yields:
            SSE-formatted string chunks matching OpenAI Responses API format
        """
        # Initialize OpenAI streaming formatter (handles all event mapping and response building)
        formatter = OpenAIStreamingFormatter_V1(
            deployment_name=deployment_name,
            model_settings=model_settings,
            messages=messages,
            tools=tools,
            output_schema=output_schema,
        )

        try:
            # Build instructions from messages
            instructions = formatter.build_instructions_from_messages(messages)

            # EVENT 1: response.created (sequence 0)
            yield formatter.format_sse_from_event(
                ResponseCreatedEvent(
                    type="response.created",
                    sequence_number=formatter._next_sequence(),
                    response=formatter.build_response_object(
                        status="in_progress",
                        instructions=instructions,
                    ),
                )
            )

            # EVENT 2: response.in_progress (sequence 1)
            yield formatter.format_sse_from_event(
                ResponseInProgressEvent(
                    type="response.in_progress",
                    sequence_number=formatter._next_sequence(),
                    response=formatter.build_response_object(
                        status="in_progress",
                        instructions=instructions,
                    ),
                )
            )

            # EVENTS 3+: MCP tool lists (if any MCP tools configured)
            if tools:
                mcp_events = await formatter.emit_mcp_tool_list_events()
                for mcp_event in mcp_events:
                    yield formatter.format_sse_from_event(mcp_event)

            # Track final result for usage
            final_result = None

            # Stream events using run_stream_events()
            async for event in agent.run_stream_events(user_prompt=user_prompt, message_history=message_history):
                logger.debug(f"Received pydantic-ai event: {type(event).__name__}")

                # Check if this is the final result event
                if isinstance(event, AgentRunResultEvent):
                    final_result = event.result
                    logger.debug("Received final AgentRunResultEvent")
                    continue  # Don't map this event, we'll handle completion separately

                # Map pydantic-ai event to OpenAI events
                openai_events = await formatter.map_event(event)

                # Emit each OpenAI event as SSE
                for openai_event in openai_events:
                    yield formatter.format_sse_from_event(openai_event)

            # Get final usage
            final_usage = None
            if final_result and final_result.usage():
                usage_info = final_result.usage()
                request_tokens = getattr(usage_info, "request_tokens", 0)
                response_tokens = getattr(usage_info, "response_tokens", 0)
                total_tokens = getattr(usage_info, "total_tokens", 0)
                details = getattr(usage_info, "details", {})
                reasoning_tokens = details.get("reasoning_tokens", 0) if isinstance(details, dict) else 0

                final_usage = {
                    "input_tokens": request_tokens,
                    "input_tokens_details": {"cached_tokens": 0},
                    "output_tokens": response_tokens,
                    "output_tokens_details": {"reasoning_tokens": reasoning_tokens},
                    "total_tokens": total_tokens,
                }

            # Finalize all unfinalized parts before response.completed
            # This handles any text, reasoning, or tool parts that were streaming but not completed
            finalization_events = await formatter.finalize_all_parts()
            for event in finalization_events:
                yield formatter.format_sse_from_event(event)

            # Build complete output array from final result (includes MCP tools, calls, text)
            if final_result:
                output_items = await formatter.build_final_output_items_from_result(final_result, tools)
                # Build complete instructions from final result (includes tool returns, retry prompts)
                final_instructions = await formatter.build_final_instructions_from_result(final_result, tools)
            else:
                output_items = formatter.build_final_output_items()  # Fallback to accumulated state
                final_instructions = instructions  # Use initial instructions as fallback

            # When final tool call is complete, it won't execute the FunctionToolResultEvent we need to internally handle
            final_tool_call_events = await formatter._map_post_final_result_event()

            # Emit each OpenAI event as SSE
            for openai_event in final_tool_call_events:
                yield formatter.format_sse_from_event(openai_event)

            # FINAL EVENT: response.completed (with usage and complete response)
            yield formatter.format_sse_from_event(
                ResponseCompletedEvent(
                    type="response.completed",
                    sequence_number=formatter._next_sequence(),
                    response=formatter.build_response_object(
                        status="completed",
                        instructions=final_instructions,
                        output_items=output_items,
                        usage=final_usage,
                    ),
                )
            )

        except Exception as e:
            logger.error(f"Error during streaming: {str(e)}")
            # ERROR EVENT: response.failed
            yield formatter.format_sse_from_event(
                ResponseFailedEvent(
                    type="response.failed",
                    sequence_number=formatter._next_sequence(),
                    response=formatter.build_response_object(
                        status="failed",
                        error={"code": "server_error", "message": str(e)},
                    ),
                )
            )
