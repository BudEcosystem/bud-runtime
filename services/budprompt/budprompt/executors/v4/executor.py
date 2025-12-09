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
import time
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional, Type, Union

from budmicroframe.commons import logging
from httpx import ConnectTimeout
from openai.types.responses import (
    EasyInputMessage,
    ResponseCodeInterpreterToolCall,
    ResponseCompletedEvent,
    ResponseComputerToolCall,
    ResponseCreatedEvent,
    ResponseCustomToolCall,
    ResponseFailedEvent,
    ResponseFileSearchToolCall,
    ResponseFunctionToolCall,
    ResponseFunctionWebSearch,
    ResponseInProgressEvent,
    ResponseInputItem,
    ResponseOutputMessage,
    ResponseReasoningItem,
)
from openai.types.responses.response_custom_tool_call_output import ResponseCustomToolCallOutput
from openai.types.responses.response_input_item import (
    ComputerCallOutput,
    FunctionCallOutput,
    ImageGenerationCall,
    ItemReference,
    LocalShellCall,
    LocalShellCallOutput,
    McpApprovalRequest,
    McpApprovalResponse,
    McpCall,
    McpListTools,
)
from openai.types.responses.response_input_item import (
    Message as ResponseInputMessage,
)
from openai.types.responses.response_output_message import ResponseOutputText
from pydantic import BaseModel, ValidationError
from pydantic_ai import Agent
from pydantic_ai.builtin_tools import MCPServerTool
from pydantic_ai.exceptions import ModelHTTPError, UnexpectedModelBehavior
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ModelResponsePart,
    SystemPromptPart,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
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

from ...prompt.schemas import MCPToolConfig, Message, ModelSettings
from .field_validation import ModelValidationEnhancer
from .openai_response_formatter import OpenAIResponseFormatter_V4, extract_validation_error_details
from .openai_streaming_formatter import OpenAIStreamingFormatter_V4
from .schema_builder import CustomModelGenerator
from .streaming_validation_executor import StreamingValidationExecutor
from .template_renderer import render_template
from .tool_loaders import ToolRegistry
from .utils import contains_pydantic_model, validate_input_data_type, validate_template_variables


logger = logging.get_logger(__name__)


class SimplePromptExecutor_V4:
    """Executor for simple prompt execution with Pydantic AI.

    This executor handles the conversion of JSON schemas to Pydantic models,
    creates AI agents, and executes prompts with structured input/output.
    """

    def __init__(self):
        """Initialize the SimplePromptExecutor."""
        self.model_generator = CustomModelGenerator()
        self.response_formatter = OpenAIResponseFormatter_V4()

    async def execute(
        self,
        deployment_name: str,
        model_settings: ModelSettings,
        input_schema: Optional[Dict[str, Any]],
        output_schema: Optional[Dict[str, Any]],
        messages: List[Message],
        input_data: Optional[Union[str, List[ResponseInputItem]]] = None,
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
        variables: Optional[Dict[str, Any]] = None,
        req_id: Optional[str] = None,
        start_time: Optional[float] = None,
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
        # [CP6] Performance checkpoint - Executor entry
        if req_id and start_time:
            elapsed = (time.time() - start_time) * 1000
            logger.info(f"[CP6] Executor.execute start | req_id={req_id} | elapsed={elapsed:.1f}ms")

        try:
            # Validate variables/schema relationship
            validate_input_data_type(input_schema, variables)

            # Validate template variables match what's used in templates
            validate_template_variables(variables, system_prompt, messages)

            # Initialize validated_variables with raw variables as default
            validated_variables = variables

            # Handle input validation
            if input_schema is not None and variables:
                # Structured input: create model with validation and validate
                input_model = await self._get_input_model_with_validation(input_schema, input_validation)
                try:
                    validated_input = input_model.model_validate(variables, extra="forbid")
                    validated_variables = validated_input.model_dump()
                except ValidationError as e:
                    # Extract validation error details (message, param, code)
                    message, param, code = extract_validation_error_details(e)
                    logger.error(f"Input validation failed: {message}")
                    raise PromptExecutionException(
                        message=message,
                        status_code=400,
                        err_type="invalid_request_error",
                        param=f"prompt.variables.{param}" if param else "prompt.variables",
                        code=code,
                    ) from e

            if variables:
                rendered_system_prompt = render_template(system_prompt, validated_variables) if system_prompt else None
                # Preserve Message structure while rendering content
                rendered_messages = [
                    Message(role=message.role, content=render_template(message.content, validated_variables))
                    for message in messages
                ]
            else:
                rendered_system_prompt = system_prompt
                rendered_messages = messages

            # Build message history from all messages
            message_history = self._build_message_history(rendered_messages, rendered_system_prompt)

            # Handle input_data: either convert to history or use as prompt
            if isinstance(input_data, list):
                # Scenario 1: ResponseInputParam - convert to message history and append
                logger.debug(f"Converting ResponseInputParam with {len(input_data)} items to message history")
                input_message_history = self._convert_response_input_to_message_history(input_data)
                message_history.extend(input_message_history)
                user_prompt = None
            else:
                # Scenario 2 & 3: String or None - use directly
                user_prompt = input_data

            # Handle output type and validation
            output_type = await self._get_output_type(output_schema, output_validation, tools)

            # Load toolsets from tools configuration (only if tools are present)
            toolsets = await self._load_toolsets(tools)

            # [CP7] Performance checkpoint - Creating Agent
            if req_id and start_time:
                elapsed = (time.time() - start_time) * 1000
                logger.info(f"[CP7] Creating Agent start | req_id={req_id} | elapsed={elapsed:.1f}ms")

            # Create AI agent with appropriate output type and retry configuration
            agent, agent_kwargs = await self._create_agent(
                deployment_name,
                model_settings,
                output_type,
                llm_retry_limit,
                allow_multiple_calls,
                system_prompt_role,
                api_key=api_key,
                toolsets=toolsets,
            )

            if req_id and start_time:
                elapsed = (time.time() - start_time) * 1000
                logger.info(f"[CP7] Creating Agent done | req_id={req_id} | elapsed={elapsed:.1f}ms")

            # Check if streaming is requested
            if stream:
                # Check if streaming validation is needed
                if output_validation and output_schema and contains_pydantic_model(output_type):
                    logger.debug("Performing streaming with structured output")

                    executor = StreamingValidationExecutor(
                        output_type=output_type,
                        # prompt=user_prompt or "",
                        prompt=user_prompt,
                        validation_prompt=output_validation,
                        messages=rendered_messages,
                        message_history=message_history,
                        api_key=api_key,
                        agent_kwargs=agent_kwargs,
                        deployment_name=deployment_name,
                        model_settings=model_settings,
                        tools=tools,
                        output_schema=output_schema,
                    )

                    return executor.stream()
                else:
                    logger.debug("Performing streaming with unstructured output")
                    return self._run_agent_stream(
                        agent,
                        user_prompt,
                        message_history,
                        output_schema,
                        deployment_name,
                        model_settings,
                        rendered_messages,
                        tools,
                        rendered_system_prompt,
                    )
            else:
                # [CP8] Performance checkpoint - Agent.run
                if req_id and start_time:
                    elapsed = (time.time() - start_time) * 1000
                    logger.info(f"[CP8] Agent.run start | req_id={req_id} | elapsed={elapsed:.1f}ms")

                # Execute the agent with both history and current prompt
                result = await self._run_agent(
                    agent,
                    user_prompt,
                    message_history,
                    output_schema,
                )

                if req_id and start_time:
                    elapsed = (time.time() - start_time) * 1000
                    logger.info(f"[CP8] Agent.run done | req_id={req_id} | elapsed={elapsed:.1f}ms")

                # Format to official OpenAI Response
                openai_response = await self.response_formatter.format_response(
                    pydantic_result=result,
                    model_settings=model_settings,
                    messages=rendered_messages,
                    deployment_name=deployment_name,
                    tools=tools,
                    output_schema=output_schema,
                    system_prompt=rendered_system_prompt,
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
        if contains_pydantic_model(output_type) and not (tools):
            logger.debug("Wrapping output model with NativeOutput")
            return NativeOutput(output_type)
        else:
            if tools:
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
    ) -> tuple[Agent, Dict[str, Any]]:
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
            Tuple of (configured AI agent, agent_kwargs dict)
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

        # Build agent kwargs
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

        # Return both agent and kwargs for reuse by other executors
        return agent, agent_kwargs

    def _build_message_history(
        self, messages: List[Message], system_prompt: Optional[str] = None
    ) -> List[ModelMessage]:
        """Build message history from messages list.

        Args:
            messages: List of messages with roles and content (already rendered)
            system_prompt: Optional system prompt to prepend as first message

        Returns:
            List of Pydantic AI ModelMessage objects
        """
        message_history = []

        # Prepend system_prompt as first message if provided
        if system_prompt:
            message_history.append(ModelRequest(parts=[SystemPromptPart(content=system_prompt)]))

        # Process all messages
        if messages:
            for msg in messages:
                if msg.role in ["system", "developer"]:
                    # System and developer messages both use SystemPromptPart
                    # The actual OpenAI role (system/developer) is controlled by system_prompt_role
                    message_history.append(ModelRequest(parts=[SystemPromptPart(content=msg.content)]))
                elif msg.role == "user":
                    # Create user message
                    message_history.append(ModelRequest(parts=[UserPromptPart(content=msg.content)]))
                elif msg.role == "assistant":
                    # Create assistant message
                    message_history.append(
                        ModelResponse(
                            parts=[TextPart(content=msg.content)],
                            timestamp=datetime.now(timezone.utc),
                        )
                    )

        return message_history

    def _convert_response_input_to_message_history(
        self, response_input: List[ResponseInputItem]
    ) -> List[ModelMessage]:
        """Convert ResponseInputItem list to pydantic-ai message history.

        This method closely follows pydantic-ai's _process_response() logic
        using Pydantic BaseModel types with proper isinstance() checks.

        Args:
            response_input: List of ResponseInputItem from OpenAI API

        Returns:
            List of ModelMessage (ModelRequest/ModelResponse) objects
        """
        input_message_history: List[ModelMessage] = []
        provider_name = "openai"

        for item in response_input:
            if isinstance(item, ResponseReasoningItem):
                parts: List[ModelResponsePart] = []
                signature = item.encrypted_content
                if item.summary:
                    for summary in item.summary:
                        parts.append(
                            ThinkingPart(
                                content=summary.text,
                                id=item.id,
                                signature=signature,
                                provider_name=provider_name if signature else None,
                            )
                        )
                        signature = None
                elif signature:
                    parts.append(
                        ThinkingPart(
                            content="",
                            id=item.id,
                            signature=signature,
                            provider_name=provider_name,
                        )
                    )
                if parts:
                    input_message_history.append(ModelResponse(parts=parts))

            elif isinstance(item, ResponseOutputMessage):
                parts = []
                for content in item.content:
                    if isinstance(content, ResponseOutputText):
                        parts.append(TextPart(content.text, id=item.id))
                if parts:
                    input_message_history.append(ModelResponse(parts=parts))

            elif isinstance(item, ResponseFunctionToolCall):
                logger.warning("ResponseFunctionToolCall input conversion history not supported")

            elif isinstance(item, ResponseCodeInterpreterToolCall):
                logger.warning("ResponseCodeInterpreterToolCall input conversion history not supported")

            elif isinstance(item, ResponseFunctionWebSearch):
                logger.warning("ResponseFunctionWebSearch input conversion history not supported")

            elif isinstance(item, ImageGenerationCall):
                logger.warning("ImageGenerationCall input conversion history not supported")

            elif isinstance(item, ResponseComputerToolCall):
                logger.warning("ResponseComputerToolCall input conversion history not supported")

            elif isinstance(item, ResponseCustomToolCall):
                logger.warning("ResponseCustomToolCall input conversion history not supported")

            elif isinstance(item, ResponseCustomToolCallOutput):
                logger.warning("ResponseCustomToolCallOutput input conversion history not supported")

            elif isinstance(item, LocalShellCall):
                logger.warning("LocalShellCall input conversion history not supported")

            elif isinstance(item, ResponseFileSearchToolCall):
                logger.warning("ResponseFileSearchToolCall input conversion history not supported")

            elif isinstance(item, McpCall):
                # NOTE: commented out since built-in tool not considering chat history
                # from pydantic_ai.models.openai import _map_mcp_call
                # call_part, return_part = _map_mcp_call(item, provider_name)

                # Custom code
                tool_name = "-".join([MCPServerTool.kind, item.server_label])
                call_part = ToolCallPart(
                    tool_name=tool_name,
                    tool_call_id=item.id,
                    args={
                        "action": "call_tool",
                        "tool_name": item.name,
                        "tool_args": json.loads(item.arguments) if item.arguments else {},
                    },
                )
                input_message_history.append(ModelResponse(parts=[call_part]))

                return_part = ToolReturnPart(
                    tool_name=tool_name,
                    tool_call_id=item.id,
                    content={
                        "output": item.output,
                        "error": item.error,
                    },
                )
                input_message_history.append(ModelRequest(parts=[return_part]))

            elif isinstance(item, McpListTools):
                # NOTE: commented out since built-in tool not considering chat history
                # To resolve this used ToolCallPart and ToolReturnPart
                #  from pydantic_ai.models.openai import _map_mcp_list_tools
                # call_part, return_part = _map_mcp_list_tools(item, provider_name)

                # Custom code
                # NOTE: Code commented out since mcp server is connected to agent and tool list always available in every agent execution
                # tool_name = '-'.join([MCPServerTool.kind, item.server_label])
                # call_part = ToolCallPart(
                #         tool_name=tool_name,
                #         tool_call_id=item.id,
                #         args={'action': 'list_tools'},
                #     )
                # input_message_history.append(ModelResponse(parts=[call_part]))

                # return_part = ToolReturnPart(
                #         tool_name=tool_name,
                #         tool_call_id=item.id,
                #         content=item.model_dump(mode='json', include={'tools', 'error'}),
                # )
                # input_message_history.append(ModelRequest(parts=[return_part]))
                logger.debug("Skipping McpListTools to add from input conversion history")
            elif isinstance(item, McpApprovalRequest):
                logger.warning("ResponseFileSearchToolCall input conversion history not supported")

            # === Input-only types (not in pydantic-ai's _process_response) ===

            elif isinstance(item, EasyInputMessage):
                # Simplified message format - content can be str or list
                role = item.role
                content = item.content

                # EasyInputMessage.content can be str or list of content parts
                if isinstance(content, str):
                    text_content = content
                else:
                    # List of content parts - extract text from input_text items
                    text_parts = []
                    for content_item in content:
                        if content_item.type == "input_text":
                            text_parts.append(content_item.text)
                    text_content = "\n".join(text_parts) if text_parts else ""

                if role in ["system", "developer"]:
                    input_message_history.append(ModelRequest(parts=[SystemPromptPart(content=text_content)]))
                elif role == "user":
                    input_message_history.append(ModelRequest(parts=[UserPromptPart(content=text_content)]))
                elif role == "assistant":
                    input_message_history.append(ModelResponse(parts=[TextPart(content=text_content)]))

            elif isinstance(item, ResponseInputMessage):
                # Message with typed content list
                role = item.role
                content_list = item.content

                # Extract text from input_text content items
                text_parts = []
                for content_item in content_list:
                    if content_item.type == "input_text":
                        text_parts.append(content_item.text)
                text_content = "\n".join(text_parts) if text_parts else ""

                if role in ["system", "developer"]:
                    input_message_history.append(ModelRequest(parts=[SystemPromptPart(content=text_content)]))
                elif role == "user":
                    input_message_history.append(ModelRequest(parts=[UserPromptPart(content=text_content)]))

            elif isinstance(item, FunctionCallOutput):
                logger.warning("FunctionCallOutput input conversion history not supported")

            elif isinstance(item, ComputerCallOutput):
                logger.warning("ComputerCallOutput input conversion history not supported")

            elif isinstance(item, LocalShellCallOutput):
                logger.warning("LocalShellCallOutput input conversion history not supported")

            elif isinstance(item, McpApprovalResponse):
                logger.warning("McpApprovalResponse input conversion history not supported")

            elif isinstance(item, ItemReference):
                logger.warning("ItemReference input conversion history not supported")

            else:
                logger.warning(f"Unsupported item type in ResponseInputItem: {type(item).__name__}")

        logger.debug(
            f"Converted {len(response_input)} ResponseInputItem items to {len(input_message_history)} messages"
        )
        return input_message_history

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
                raise PromptExecutionException(error_msg, status_code=500) from e
            else:
                logger.error(f"Unexpected model behavior: {error_msg}")
                raise PromptExecutionException(f"Unexpected model behavior: {error_msg}") from e
        except ModelHTTPError as e:
            # HTTP errors from MCP servers or model providers
            logger.error(f"Received error from model: {str(e)}")
            raise PromptExecutionException(e.message, status_code=e.status_code, param=e.model_name) from e
        except ConnectTimeout as e:
            logger.error(f"Connection timed out: {str(e)}")
            raise PromptExecutionException("Connection timed out to model", status_code=500) from e
        except Exception as e:
            logger.error(f"Agent execution failed: {str(e)}")
            raise PromptExecutionException(f"Agent execution failed: {str(e)}", status_code=500) from e

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
        system_prompt: Optional[str] = None,
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
        formatter = OpenAIStreamingFormatter_V4(
            deployment_name=deployment_name,
            model_settings=model_settings,
            messages=messages,
            tools=tools,
            output_schema=output_schema,
        )

        try:
            # Build instructions from messages and system prompt
            instructions = formatter.build_instructions(messages, system_prompt)

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
            else:
                output_items = formatter.build_final_output_items()  # Fallback to accumulated state

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
                        instructions=instructions,
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
