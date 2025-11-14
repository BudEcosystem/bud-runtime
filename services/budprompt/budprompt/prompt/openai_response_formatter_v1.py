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

"""OpenAI Response Formatter for converting pydantic-ai responses to OpenAI format."""

import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from budmicroframe.commons import logging
from openai.types.responses import (
    ResponseTextConfig,
    ResponseUsage,
)
from openai.types.responses.response_format_text_json_schema_config import ResponseFormatTextJSONSchemaConfig
from openai.types.responses.response_function_tool_call import ResponseFunctionToolCall
from openai.types.responses.response_input_item import (
    FunctionCallOutput,
)
from openai.types.responses.response_input_item import (
    McpCall as ResponseInputMcpCall,  # MCP tool call/return for instructions field
)
from openai.types.responses.response_input_item import (
    Message as ResponseInputMessage,  # Use alias to avoid conflict with local Message class
)
from openai.types.responses.response_input_text import ResponseInputText
from openai.types.responses.response_output_item import (
    McpCall as ResponseOutputMcpCall,  # MCP tool call for output field
)
from openai.types.responses.response_output_item import (
    McpListTools,
    McpListToolsTool,
)
from openai.types.responses.response_output_message import ResponseOutputMessage
from openai.types.responses.response_output_text import ResponseOutputText
from openai.types.responses.response_reasoning_item import (
    ResponseReasoningItem,
    Summary,
)
from openai.types.responses.tool import Tool
from openai.types.shared.reasoning import Reasoning
from openai.types.shared.response_format_text import ResponseFormatText
from pydantic import ValidationError
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    SystemPromptPart,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.run import AgentRunResult

from ..commons.constants import STRUCTURED_OUTPUT_TOOL_NAME, STRUCTURED_PUTOUT_TOOL_DESCRIPTION
from ..responses.schemas import OpenAIResponse
from .schemas import MCPToolConfig, Message, ModelSettings


logger = logging.get_logger(__name__)

__all__ = [
    "OpenAIResponseFormatter_V1",
    "extract_validation_error_details",
]


class OpenAIResponseFormatter_V1:
    """Formatter for converting pydantic-ai responses to OpenAI format."""

    def __init__(self) -> None:
        """Initialize the formatter with tool call arguments mapper."""
        self._tool_call_args_map: Dict[str, str] = {}

    async def format_response(
        self,
        pydantic_result: AgentRunResult[Any],
        model_settings: Optional[ModelSettings] = None,
        messages: Optional[List[Message]] = None,
        deployment_name: Optional[str] = None,
        tools: Optional[List[MCPToolConfig]] = None,
        output_schema: Optional[Dict[str, Any]] = None,
    ) -> OpenAIResponse:
        """Format pydantic-ai result to OpenAI Response structure.

        Args:
            pydantic_result: The result from pydantic-ai agent.run()
            model_settings: Model configuration settings
            messages: Original input messages
            deployment_name: Model deployment name
            tools: MCP tool configurations for server_label mapping

        Returns:
            Response object matching official OpenAI Responses API structure
        """
        try:
            # Generate unique response ID
            response_id = f"resp_{uuid.uuid4().hex}"

            # Get messages from pydantic-ai result
            all_messages = pydantic_result.all_messages()

            # Extract output items and add structured output if present
            output_items, mcp_tool_call_ids = await self.build_complete_output_items(
                all_messages, pydantic_result, tools
            )

            # Extract input items (system prompts, user prompts, tool returns, retry prompts)
            # Pass MCP tool call IDs to identify MCP tool returns
            input_items = await self._format_input_items(all_messages, mcp_tool_call_ids, tools)

            # Get usage information
            usage = self._format_usage(pydantic_result.usage())

            # Get model name from last response or use deployment_name
            model_name = deployment_name or "unknown"
            for msg in all_messages:
                if isinstance(msg, ModelResponse) and msg.model_name:
                    model_name = msg.model_name
                    break

            # Format tools array (returns List[Tool])
            formatted_tools = self._format_tools(tools)

            # Format text configuration based on output schema
            text_config = self._format_text_config(output_schema)

            # Build response using custom OpenAIResponse type with int serialization
            return OpenAIResponse(
                id=response_id,
                object="response",
                created_at=int(time.time()),
                model=model_name,
                output=output_items,
                instructions=input_items if input_items else None,
                usage=usage,
                status="completed",
                parallel_tool_calls=True,
                tool_choice="auto",
                tools=formatted_tools,
                temperature=model_settings.temperature if model_settings else None,
                top_p=model_settings.top_p if model_settings else None,
                max_output_tokens=model_settings.max_tokens if model_settings else None,
                background=False,
                reasoning=Reasoning(),
                text=text_config,
            )

        except Exception as e:
            logger.error(f"Error formatting OpenAI response: {str(e)}")
            raise

    async def _format_output_items(
        self,
        all_messages: List[ModelMessage],
        tools: Optional[List[MCPToolConfig]] = None,
    ) -> tuple[List[Any], set]:
        """Convert pydantic-ai messages to OpenAI ResponseOutputItem list.

        Args:
            all_messages: All messages from pydantic-ai result (ModelMessage objects)
            tools: MCP tool configurations for server_label mapping

        Returns:
            Tuple of (List of ResponseOutputItem, set of MCP tool call IDs)
        """
        output_items: List[Any] = []
        mcp_tool_call_ids: set = set()

        # Step 1: Fetch and add MCP tool lists at the beginning
        mcp_list_items = await self._fetch_mcp_tool_lists(tools)
        if mcp_list_items:
            output_items.extend(mcp_list_items)

        # Step 2: Build MCP tool names set for efficient lookup
        mcp_tool_names = self._build_mcp_tool_names_set(tools)

        # Step 3: Build tool returns lookup
        tool_returns = self._build_tool_returns_lookup(all_messages)

        # Step 3: Process messages in chronological order
        for message in all_messages:
            if isinstance(message, ModelResponse):
                for part in message.parts:
                    # TextPart → ResponseOutputMessage
                    if isinstance(part, TextPart):
                        output_items.append(
                            ResponseOutputMessage(
                                id=part.id or f"msg_{uuid.uuid4().hex}",
                                type="message",
                                status="completed",
                                content=[
                                    ResponseOutputText(
                                        type="output_text",
                                        text=part.content,
                                        annotations=[],
                                    )
                                ],
                                role="assistant",
                            )
                        )

                    # ThinkingPart → ResponseReasoningItem
                    # Setting summary based on referring .venv/lib/python3.11/site-packages/pydantic_ai/models/openai.py L1562 (pydantic_ai==1.4.0)
                    elif isinstance(part, ThinkingPart):
                        if part.content:  # Only add if there's actual content
                            output_items.append(
                                ResponseReasoningItem(
                                    id=part.id or f"rs_{uuid.uuid4().hex}",
                                    type="reasoning",
                                    summary=[
                                        Summary(
                                            type="summary_text",
                                            text=part.content,
                                        )
                                    ],
                                    encrypted_content=part.signature if hasattr(part, "signature") else None,
                                    status="completed",
                                )
                            )

                    # ToolCallPart → ResponseOutputMcpCall or ResponseFunctionToolCall
                    elif isinstance(part, ToolCallPart):
                        # Store tool call arguments for later use (ALL tool calls - MCP and regular)
                        self._tool_call_args_map[part.tool_call_id] = part.args_as_json_str()

                        # Check if this is an MCP tool using the tool names set
                        if part.tool_name in mcp_tool_names:
                            # MCP tool call - track ID and get server label
                            mcp_tool_call_ids.add(part.tool_call_id)
                            server_label = self._get_server_label_for_tool(part.tool_name, tools)
                            return_data = tool_returns.get(part.tool_call_id)

                            output_items.append(
                                ResponseOutputMcpCall(
                                    id=part.tool_call_id,
                                    type="mcp_call",
                                    name=part.tool_name,
                                    server_label=server_label or "unknown",
                                    arguments=part.args_as_json_str(),
                                    status="completed" if return_data else "in_progress",
                                    output=return_data.get("content") if return_data else None,
                                    error=None,
                                )
                            )
                        else:
                            # Regular function call
                            output_items.append(
                                ResponseFunctionToolCall(
                                    type="function_call",
                                    call_id=part.tool_call_id,
                                    name=part.tool_name,
                                    arguments=part.args_as_json_str(),
                                    id=part.id if hasattr(part, "id") and part.id else None,
                                )
                            )

        return output_items, mcp_tool_call_ids

    async def build_complete_output_items(
        self,
        all_messages: List[ModelMessage],
        agent_result: AgentRunResult,
        tools: Optional[List[MCPToolConfig]] = None,
    ) -> tuple[List[Any], set]:
        """Format output items from messages and add structured output if present.

        This wrapper around _format_output_items also checks for and adds
        structured output from final_result tool returns.

        Args:
            all_messages: All messages from agent execution
            agent_result: The AgentRunResult from pydantic-ai
            tools: Optional MCP tool configurations

        Returns:
            Tuple of (output_items list, mcp_tool_call_ids set)
        """
        # Get base output items
        output_items, mcp_tool_call_ids = await self._format_output_items(all_messages, tools)

        # Check if we should add structured output text from result.output
        if self._has_final_result_tool_return(agent_result, all_messages):
            structured_output = agent_result.output

            output_items.append(
                ResponseOutputMessage(
                    id=f"msg_{uuid.uuid4().hex}",
                    type="message",
                    status="completed",
                    content=[
                        ResponseOutputText(
                            type="output_text",
                            text=(
                                structured_output.model_dump_json()
                                if hasattr(structured_output, "model_dump_json")
                                else str(structured_output)
                            ),
                            annotations=[],
                        )
                    ],
                    role="assistant",
                )
            )
            logger.debug("Added structured output text from result.output (final_result tool return detected)")

        return output_items, mcp_tool_call_ids

    def _has_final_result_tool_return(
        self,
        result: AgentRunResult,
        all_messages: List[ModelMessage],
    ) -> bool:
        """Check if result has a final_result tool return indicating structured output.

        Verifies:
        1. result.output has a value (not None or empty)
        2. result._output_tool_name is "final_result"
        3. Any message contains a ToolReturnPart for "final_result"
        4. Tool return content is "Final result processed."

        Args:
            result: The AgentRunResult from execution
            all_messages: All messages from result.all_messages()

        Returns:
            True if final_result tool return is present with expected content
        """
        # Check if result.output has a value
        if not result.output:
            return False

        # Check if Tool Output mode with final_result
        if not result._output_tool_name or result._output_tool_name != STRUCTURED_OUTPUT_TOOL_NAME:
            return False

        # Check if messages exist
        if not all_messages:
            return False

        # Search through all messages for the final_result ToolReturnPart
        for message in all_messages:
            if not hasattr(message, "parts") or not message.parts:
                continue

            for part in message.parts:
                # Check if this is the final_result ToolReturnPart with expected content
                if (
                    isinstance(part, ToolReturnPart)
                    and part.tool_name == STRUCTURED_OUTPUT_TOOL_NAME
                    and part.content == STRUCTURED_PUTOUT_TOOL_DESCRIPTION
                ):
                    return True

        return False

    async def _format_input_items(
        self,
        all_messages: List[ModelMessage],
        mcp_tool_call_ids: set,
        tools: Optional[List[MCPToolConfig]] = None,
    ) -> List[Any]:
        """Convert pydantic-ai ModelRequest messages to OpenAI ResponseInputItem list.

        Text-only implementation for LLM interactions.

        Args:
            all_messages: All messages from pydantic-ai result (ModelMessage objects)
            mcp_tool_call_ids: Set of tool call IDs that are MCP tools
            tools: MCP tool configurations for server_label mapping

        Returns:
            List of ResponseInputItem (system prompts, user prompts, tool returns, retry prompts)
        """
        input_items: List[Any] = []

        for message in all_messages:
            if isinstance(message, ModelRequest):
                for part in message.parts:
                    # SystemPromptPart → ResponseInputMessage with role='system'
                    if isinstance(part, SystemPromptPart):
                        input_items.append(
                            ResponseInputMessage(
                                role="system",
                                content=[
                                    ResponseInputText(
                                        type="input_text",
                                        text=part.content,
                                    )
                                ],
                                type="message",
                                status="completed",
                            )
                        )

                    # UserPromptPart → ResponseInputMessage with role='user'
                    elif isinstance(part, UserPromptPart):
                        # Convert to string if needed (text-only for now)
                        content_str = part.content if isinstance(part.content, str) else str(part.content)
                        input_items.append(
                            ResponseInputMessage(
                                role="user",
                                content=[
                                    ResponseInputText(
                                        type="input_text",
                                        text=content_str,
                                    )
                                ],
                                type="message",
                                status="completed",
                            )
                        )

                    # ToolReturnPart → ResponseInputMcpCall or FunctionCallOutput
                    elif isinstance(part, ToolReturnPart):
                        if not part.tool_call_id:
                            logger.warning(f"ToolReturnPart missing tool_call_id, skipping: {part.tool_name}")
                            continue

                        # Check if this is an MCP tool return by checking tool_call_id
                        if part.tool_call_id in mcp_tool_call_ids:
                            # MCP tool return - get server label from tool name
                            server_label = self._get_server_label_for_tool(part.tool_name, tools)
                            # Get arguments from mapper (populated during _format_output_items)
                            arguments = self._tool_call_args_map.get(part.tool_call_id, "{}")
                            input_items.append(
                                ResponseInputMcpCall(
                                    id=part.tool_call_id,
                                    type="mcp_call",
                                    name=part.tool_name,
                                    server_label=server_label or "unknown",
                                    arguments=arguments,
                                    output=part.model_response_str(),
                                    status="completed",
                                )
                            )
                        else:
                            # Regular function call output
                            input_items.append(
                                FunctionCallOutput(
                                    type="function_call_output",
                                    call_id=part.tool_call_id,
                                    output=part.model_response_str(),
                                )
                            )

                    # RetryPromptPart → ResponseInputMessage or FunctionCallOutput
                    elif isinstance(part, RetryPromptPart):
                        # Always use model_response() to get string (handles str and list[ErrorDetails])
                        retry_text = part.model_response()

                        if part.tool_name is None:
                            # Retry without tool → user message
                            input_items.append(
                                ResponseInputMessage(
                                    role="user",
                                    content=[
                                        ResponseInputText(
                                            type="input_text",
                                            text=retry_text,
                                        )
                                    ],
                                    type="message",
                                    status="completed",
                                )
                            )
                        else:
                            # Retry with tool → function call output
                            input_items.append(
                                FunctionCallOutput(
                                    type="function_call_output",
                                    call_id=part.tool_call_id,
                                    output=retry_text,
                                )
                            )

        return input_items

    def _build_tool_returns_lookup(self, all_messages: List[ModelMessage]) -> Dict[str, Dict]:
        """Build a lookup dictionary of tool returns by tool_call_id.

        Args:
            all_messages: All messages from pydantic-ai result

        Returns:
            Dictionary mapping tool_call_id to return data
        """
        tool_returns = {}

        for msg in all_messages:
            if isinstance(msg, ModelRequest):
                for part in msg.parts:
                    if isinstance(part, ToolReturnPart):
                        tool_returns[part.tool_call_id] = {
                            "content": part.model_response_str(),
                            "tool_name": part.tool_name,
                        }

        return tool_returns

    def _build_mcp_tool_names_set(self, tools: Optional[List[MCPToolConfig]]) -> set:
        """Build a set of all MCP tool names for fast lookup.

        Args:
            tools: List of MCP tool configurations

        Returns:
            Set of tool names that are MCP tools
        """
        if not tools:
            return set()

        mcp_tool_names = set()
        for tool_config in tools:
            if tool_config.type == "mcp":
                mcp_tool_names.update(tool_config.allowed_tool_names)

        return mcp_tool_names

    def _get_server_label_for_tool(self, tool_name: str, tools: Optional[List[MCPToolConfig]] = None) -> Optional[str]:
        """Get server_label for a tool if it's an MCP tool.

        Args:
            tool_name: Name of the tool
            tools: MCP tool configurations

        Returns:
            Server label if MCP tool, None otherwise
        """
        if not tools:
            return None

        for tool_config in tools:
            if tool_config.type == "mcp" and tool_name in tool_config.allowed_tool_names:
                return tool_config.server_label

        return None

    def _format_tools(self, tools: Optional[List[MCPToolConfig]]) -> List[Tool]:
        """Convert MCPToolConfig objects to OpenAI Tool format.

        Args:
            tools: List of MCP tool configurations from prompt config

        Returns:
            List of Tool objects (currently returns empty list as we handle MCP via output items)
        """
        # Note: In OpenAI Responses API, tools are typically defined at request time
        # and MCP tool calls appear in the output items, not in the tools array.
        # For now, return empty list. Can be extended if needed.
        return []

    async def _fetch_mcp_tool_lists(self, tools: Optional[List[MCPToolConfig]]) -> List[McpListTools]:
        """Fetch tool lists from all MCP servers.

        Args:
            tools: List of MCP tool configurations

        Returns:
            List of McpListTools output items (official type)
        """
        if not tools:
            return []

        from .tool_loaders import MCPToolLoader

        loader = MCPToolLoader()
        mcp_list_items: List[McpListTools] = []

        for tool_config in tools:
            if tool_config.type == "mcp":
                # Load the MCP server
                mcp_server = await loader.load_tools(tool_config)
                if not mcp_server:
                    continue

                # Fetch tool list from server
                tool_list_data = await loader.get_tool_list(mcp_server, tool_config.server_label or "unknown")

                if tool_list_data:
                    # Parse tools from MCP response
                    tools_list: List[McpListToolsTool] = []
                    for tool_info in tool_list_data.get("tools", []):
                        # tool_info is a Pydantic Tool object from pydantic-ai
                        # Access attributes directly
                        tools_list.append(
                            McpListToolsTool(
                                name=tool_info.name,
                                description=getattr(tool_info, "description", None),
                                input_schema=tool_info.inputSchema
                                if hasattr(tool_info, "inputSchema")
                                else tool_info.input_schema,
                                annotations=getattr(tool_info, "annotations", None),
                            )
                        )

                    # Create mcp_list_tools output item using official type
                    mcp_list_items.append(
                        McpListTools(
                            id=f"mcpl_{uuid.uuid4().hex}",
                            type="mcp_list_tools",
                            server_label=tool_list_data["server_label"],
                            tools=tools_list,
                            error=tool_list_data.get("error"),
                        )
                    )

        return mcp_list_items

    def _format_usage(self, usage_info: Any) -> ResponseUsage:
        """Format usage information to official ResponseUsage type.

        Args:
            usage_info: Usage information from pydantic-ai result

        Returns:
            ResponseUsage object with token counts
        """
        if not usage_info:
            return ResponseUsage(
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
            )

        # Extract token counts from pydantic-ai usage object
        request_tokens = getattr(usage_info, "request_tokens", 0)
        response_tokens = getattr(usage_info, "response_tokens", 0)
        total_tokens = getattr(usage_info, "total_tokens", 0)

        # Extract reasoning tokens from details if available
        details = getattr(usage_info, "details", {})
        reasoning_tokens = details.get("reasoning_tokens", 0) if isinstance(details, dict) else 0

        return ResponseUsage(
            input_tokens=request_tokens,
            output_tokens=response_tokens,
            total_tokens=total_tokens,
            input_tokens_details={"cached_tokens": 0},
            output_tokens_details={"reasoning_tokens": reasoning_tokens},
        )

    def _format_text_config(
        self,
        output_schema: Optional[Dict[str, Any]],
    ) -> Optional[ResponseTextConfig]:
        """Format text configuration based on output schema.

        Args:
            output_schema: Output schema from prompt config

        Returns:
            ResponseTextConfig with appropriate format (text or json_schema)
        """
        if output_schema:
            # Structured output with JSON schema
            # Use model_validate to properly handle the aliased field
            json_schema_config = ResponseFormatTextJSONSchemaConfig.model_validate(
                {
                    "type": "json_schema",
                    "name": output_schema.get("title", "response_schema"),
                    "schema": output_schema,  # Use alias name "schema" in dict
                    "strict": True,
                }
            )
            return ResponseTextConfig(format=json_schema_config)
        else:
            # Plain text output
            return ResponseTextConfig(format=ResponseFormatText(type="text"))


# Error Mapping Utilities
def extract_validation_error_details(e: ValidationError) -> Tuple[str, Optional[str], Optional[str]]:
    """Extract error details from Pydantic ValidationError.

    Args:
        e: Pydantic ValidationError

    Returns:
        Tuple of (message, param, code)
    """
    # Get the first error for simplicity (could be enhanced to handle multiple)
    if e.errors():
        first_error = e.errors()[0]

        # Build parameter path (e.g., 'prompt.variables.amount')
        param_parts = []
        for loc_item in first_error.get("loc", []):
            if loc_item != "__root__":  # Skip root markers
                param_parts.append(str(loc_item))
        param = ".".join(param_parts) if param_parts else None

        # Get error message
        message = first_error.get("msg", str(e))

        # Map Pydantic error type to our error codes
        error_type = first_error.get("type", "")
        code_map = {
            "missing": "required",
            "value_error": "invalid_value",
            "type_error": "invalid_type",
            "string_too_short": "invalid_length",
            "string_too_long": "invalid_length",
            "string_pattern_mismatch": "invalid_format",
            "enum": "invalid_choice",
        }

        # Try to find matching code
        code = None
        for pattern, mapped_code in code_map.items():
            if pattern in error_type:
                code = mapped_code
                break

        # Default to invalid_type if no match
        if not code:
            code = "invalid_type" if "type" in error_type else "invalid_value"

        return message, param, code

    # Fallback if no errors found
    return str(e), None, "validation_error"
