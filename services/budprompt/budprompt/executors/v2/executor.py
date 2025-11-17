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
    ThinkingPart,
    ToolCallPart,
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

from ...prompt.schemas import MCPToolConfig, Message, ModelSettings
from .field_validation import ModelValidationEnhancer
from .openai_response_formatter import OpenAIResponseFormatter
from .openai_streaming_formatter import OpenAIStreamingFormatter
from .schema_builder import CustomModelGenerator
from .streaming_validation_executor import StreamingValidationExecutor
from .template_renderer import render_template
from .tool_loaders import ToolRegistry
from .utils import contains_pydantic_model, validate_input_data_type


logger = logging.get_logger(__name__)


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
