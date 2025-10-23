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

import json
import logging
import time
import uuid
from typing import Any, Dict, List, Literal, Optional, Tuple, Union

from pydantic import BaseModel, Field, ValidationError

from .schemas import MCPToolConfig, Message, ModelSettings


logger = logging.getLogger(__name__)

__all__ = [
    "OpenAIResponseSchema",
    "OpenAIPromptInfo",
    "OpenAIResponseFormatter",
    "extract_validation_error_details",
]


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


# OpenAI Response Models
class OpenAIContentPart(BaseModel):
    """Content part for OpenAI messages."""

    type: Literal["input_text", "output_text", "thinking"]
    text: str
    annotations: Optional[List[Any]] = Field(default_factory=list)
    logprobs: Optional[List[Any]] = Field(default_factory=list)


class OpenAIInstructionMessage(BaseModel):
    """Instruction message structure for system/user messages."""

    type: Literal["message"] = "message"
    content: List[OpenAIContentPart]
    role: Literal["system", "developer", "user", "assistant"]


class OpenAIOutputMessage(BaseModel):
    """Output message structure for assistant responses."""

    id: str
    type: Literal["message"] = "message"
    status: Literal["completed", "failed", "in_progress"] = "completed"
    content: List[OpenAIContentPart]
    role: Literal["assistant"] = "assistant"


class OpenAIMCPCall(BaseModel):
    """MCP tool call output item."""

    type: Literal["mcp_call"] = "mcp_call"
    id: str  # tool_call_id from pydantic-ai
    name: str  # actual tool name (parsed from tool_name)
    server_label: str  # from MCPToolConfig
    arguments: str  # JSON string from tool-call args
    status: Literal["in_progress", "completed", "incomplete", "calling", "failed"]
    output: Optional[str] = None  # from tool-return content
    error: Optional[str] = None
    approval_request_id: Optional[str] = None


class OpenAIMCPTool(BaseModel):
    """OpenAI MCP tool configuration format."""

    type: Literal["mcp"] = "mcp"
    server_label: str = Field(..., description="A label for this MCP server, used to identify it in tool calls")
    allowed_tools: List[str] = Field(..., description="List of allowed tool names")
    connector_id: Optional[str] = Field(None, description="Identifier for service connectors")
    server_url: Optional[str] = Field(None, description="The URL for the MCP server")
    server_description: Optional[str] = Field(None, description="Optional description of the MCP server")
    require_approval: Literal["always", "never", "auto"] = Field(
        default="never", description="Specify which tools require approval"
    )
    authorization: Optional[str] = Field(None, description="OAuth access token for the MCP server")
    headers: Optional[Dict[str, str]] = Field(None, description="Optional HTTP headers to send to the MCP server")


class OpenAIUsageDetails(BaseModel):
    """Token usage details."""

    cached_tokens: int = 0
    reasoning_tokens: int = 0


class OpenAIUsage(BaseModel):
    """Token usage information."""

    input_tokens: int
    input_tokens_details: OpenAIUsageDetails
    output_tokens: int
    output_tokens_details: OpenAIUsageDetails
    total_tokens: int


class OpenAITextFormat(BaseModel):
    """Text format configuration."""

    type: Literal["text", "json"] = "text"


class OpenAITextConfig(BaseModel):
    """Text configuration."""

    format: OpenAITextFormat
    verbosity: Optional[Literal["low", "medium", "high"]] = "medium"


class OpenAIReasoning(BaseModel):
    """Reasoning configuration."""

    effort: Optional[Literal["low", "medium", "high"]] = None
    summary: Optional[str] = None


class OpenAIPromptInfo(BaseModel):
    """Prompt template information."""

    id: str
    variables: Optional[Dict[str, Any]] = None
    version: Optional[str] = None


class OpenAIResponseSchema(BaseModel):
    """Complete OpenAI response structure."""

    id: str
    object: Literal["response"] = "response"
    created_at: int
    status: Literal["completed", "failed", "in_progress", "cancelled", "queued", "incomplete"] = "completed"
    background: bool = False
    billing: Optional[Dict[str, str]] = None
    error: Optional[Dict[str, Any]] = None
    incomplete_details: Optional[Dict[str, Any]] = None
    instructions: List[OpenAIInstructionMessage]
    max_output_tokens: Optional[int] = None
    max_tool_calls: Optional[int] = None
    model: str
    output: List[Union[OpenAIMCPCall, OpenAIOutputMessage, Dict[str, Any]]]
    parallel_tool_calls: bool = True
    previous_response_id: Optional[str] = None
    prompt: Optional[OpenAIPromptInfo] = None
    prompt_cache_key: Optional[str] = None
    reasoning: OpenAIReasoning
    safety_identifier: Optional[str] = None
    service_tier: Literal["auto", "default", "flex", "priority"] = "default"
    store: bool = True
    temperature: float = 1.0
    text: OpenAITextConfig
    tool_choice: Union[Literal["auto", "none", "required"], Dict[str, Any]] = "auto"
    tools: List[Dict[str, Any]] = Field(default_factory=list)
    top_logprobs: int = 0
    top_p: float = 1.0
    truncation: Literal["auto", "disabled"] = "disabled"
    usage: OpenAIUsage
    user: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OpenAIResponseFormatter:
    """Formatter for converting pydantic-ai responses to OpenAI format."""

    def format_response(
        self,
        pydantic_result: Any,
        model_settings: Optional[ModelSettings] = None,
        messages: Optional[List[Message]] = None,
        deployment_name: Optional[str] = None,
        tools: Optional[List[MCPToolConfig]] = None,
    ) -> OpenAIResponseSchema:
        """Format pydantic-ai result to OpenAI response structure.

        Args:
            pydantic_result: The result from pydantic-ai agent.run()
            model_settings: Model configuration settings
            messages: Original input messages
            deployment_name: Model deployment name
            tools: MCP tool configurations for server_label mapping

        Returns:
            OpenAIResponseSchema object matching OpenAI response structure
        """
        try:
            # Generate unique response ID
            response_id = f"resp_{uuid.uuid4().hex}"

            # Parse messages from result
            all_messages = json.loads(pydantic_result.all_messages_json())

            # Extract instructions from input messages
            instructions = self._format_instructions(messages or [], all_messages)

            # Extract output items (includes MCP calls and message items)
            output = self._format_output_with_tools(all_messages, response_id, tools)

            # Get usage information
            usage = self._format_usage(pydantic_result.usage())

            # Get model name
            model_name = deployment_name or "unknown"
            # Try to get from all_messages if available
            if all_messages and len(all_messages) > 1:
                for msg in all_messages:
                    if msg.get("kind") == "response" and msg.get("model_name"):
                        model_name = msg["model_name"]
                        break

            # Build reasoning object (request-level config, always null for us)
            reasoning = OpenAIReasoning(effort=None, summary=None)

            # Format tools array
            formatted_tools = self._format_tools(tools)

            # Build response
            response = OpenAIResponseSchema(
                id=response_id,
                created_at=int(time.time()),
                instructions=instructions,
                model=model_name,
                output=output,
                temperature=model_settings.temperature if model_settings else 1.0,
                top_p=model_settings.top_p if model_settings else 1.0,
                max_output_tokens=model_settings.max_tokens if model_settings else None,
                text=OpenAITextConfig(
                    format=OpenAITextFormat(type="json" if self._is_json_output(pydantic_result) else "text")
                ),
                reasoning=reasoning,
                usage=usage,
                tools=formatted_tools,
            )

            return response

        except Exception as e:
            logger.error(f"Error formatting OpenAI response: {str(e)}")
            raise

    def _format_instructions(self, messages: List[Message], all_messages: List[Dict]) -> List[Dict]:
        """Format instruction messages from input."""
        instructions = []

        # Always extract ALL messages from pydantic-ai messages (they contain everything)
        if all_messages:
            for msg in all_messages:
                if msg.get("kind") == "request":
                    parts = msg.get("parts", [])
                    for part in parts:
                        part_kind = part.get("part_kind", "")
                        if part_kind == "system-prompt":
                            instructions.append(
                                {
                                    "type": "message",
                                    "content": [{"type": "input_text", "text": part.get("content", "")}],
                                    "role": "system",
                                }
                            )
                        elif part_kind == "user-prompt":
                            instructions.append(
                                {
                                    "type": "message",
                                    "content": [{"type": "input_text", "text": part.get("content", "")}],
                                    "role": "user",
                                }
                            )

        # Fallback to original messages only if no pydantic-ai messages available
        if not instructions and messages:
            for msg in messages:
                if msg.role in ["system", "developer", "user"]:
                    instructions.append(
                        {
                            "type": "message",
                            "content": [{"type": "input_text", "text": msg.content}],
                            "role": msg.role,
                        }
                    )

        return instructions

    def _format_output_with_tools(
        self,
        all_messages: List[Dict],
        response_id: str,
        tools: Optional[List[MCPToolConfig]] = None,
    ) -> List[Dict]:
        """Format output items in chronological order.

        Processing logic:
        1. Build lookup dict of tool returns by tool_call_id
        2. Iterate through messages in order
        3. For each part, add corresponding output item:
           - thinking → reasoning
           - text → message
           - tool-call → mcp_call (correlated with tool-return)

        Args:
            all_messages: All messages from pydantic-ai result
            response_id: The response ID
            tools: MCP tool configurations for server_label

        Returns:
            List of output items in chronological order
        """
        output_items = []

        # Build tool returns lookup
        tool_returns_lookup = self._build_tool_returns_lookup(all_messages)

        # Get server_label from MCP tool config
        server_label = "unknown"
        if tools:
            for tool_config in tools:
                if tool_config.type == "mcp":
                    server_label = tool_config.server_label
                    break

        # Process messages in chronological order
        for msg in all_messages:
            kind = msg.get("kind")
            parts = msg.get("parts", [])

            # Skip request messages (system-prompt, user-prompt, tool-return are not output)
            if kind == "request":
                continue

            # Process response messages
            if kind == "response":
                for part in parts:
                    part_kind = part.get("part_kind")

                    # Add reasoning for thinking parts
                    if part_kind == "thinking":
                        content = part.get("content", "")
                        if content:
                            reasoning_item = {
                                "type": "reasoning",
                                "id": f"rs_{uuid.uuid4().hex}",
                                "status": "completed",
                                "content": [{"type": "reasoning_text", "text": content}],
                                "summary": [{"type": "summary_text", "text": None}],
                            }
                            output_items.append(reasoning_item)

                    # Add message for text parts
                    elif part_kind == "text":
                        content = part.get("content", "")
                        message_item = {
                            "id": f"msg_{uuid.uuid4().hex}",
                            "type": "message",
                            "status": "completed",
                            "content": [{"type": "output_text", "text": content, "annotations": [], "logprobs": []}],
                            "role": "assistant",
                        }
                        output_items.append(message_item)

                    # Add mcp_call for tool-call parts
                    elif part_kind == "tool-call":
                        tool_call_id = part.get("tool_call_id")
                        tool_name = part.get("tool_name")
                        args = part.get("args")

                        # Get correlated tool return
                        return_data = tool_returns_lookup.get(tool_call_id)

                        mcp_call = {
                            "type": "mcp_call",
                            "id": tool_call_id,
                            "name": tool_name,
                            "server_label": server_label,
                            "arguments": args,
                            "status": "completed" if return_data else "in_progress",
                            "output": return_data["content"] if return_data else None,
                            "error": None,
                            "approval_request_id": None,
                        }
                        output_items.append(mcp_call)

        return output_items

    def _build_tool_returns_lookup(self, all_messages: List[Dict]) -> Dict[str, Dict]:
        """Build a lookup dictionary of tool returns by tool_call_id.

        Args:
            all_messages: All messages from pydantic-ai result

        Returns:
            Dictionary mapping tool_call_id to return data
        """
        tool_returns = {}

        for msg in all_messages:
            if msg.get("kind") == "request":
                for part in msg.get("parts", []):
                    if part.get("part_kind") == "tool-return":
                        tool_call_id = part.get("tool_call_id")
                        tool_returns[tool_call_id] = {
                            "content": part.get("content"),
                            "tool_name": part.get("tool_name"),
                        }

        return tool_returns

    def _format_tools(self, tools: Optional[List[MCPToolConfig]]) -> List[Dict[str, Any]]:
        """Convert MCPToolConfig objects to OpenAI MCP tool format.

        Args:
            tools: List of MCP tool configurations from prompt config

        Returns:
            List of tool dictionaries in OpenAI format
        """
        if not tools:
            return []

        formatted_tools = []
        for tool in tools:
            if tool.type == "mcp":
                openai_tool = OpenAIMCPTool(
                    type="mcp",
                    server_label=tool.server_label or "unknown",
                    allowed_tools=tool.allowed_tools,
                    connector_id=tool.connector_id,
                    server_url=tool.server_url,
                    server_description=tool.server_description,
                    require_approval=tool.require_approval,
                )
                formatted_tools.append(openai_tool.model_dump(exclude_none=True))

        return formatted_tools

    def _format_usage(self, usage_info: Any) -> Dict:
        """Format usage information."""
        if not usage_info:
            return {
                "input_tokens": 0,
                "input_tokens_details": {"cached_tokens": 0},
                "output_tokens": 0,
                "output_tokens_details": {"reasoning_tokens": 0},
                "total_tokens": 0,
            }

        # Handle dict-like usage info
        usage_dict = usage_info if isinstance(usage_info, dict) else usage_info.__dict__

        return {
            "input_tokens": usage_dict.get("request_tokens", 0),
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens": usage_dict.get("response_tokens", 0),
            "output_tokens_details": {"reasoning_tokens": 0},
            "total_tokens": usage_dict.get("total_tokens", 0),
        }

    def _is_json_output(self, result: Any) -> bool:
        """Check if the output is JSON formatted."""
        try:
            if hasattr(result, "output"):
                output = result.output
                if hasattr(output, "model_dump"):
                    # It's a Pydantic model, so it's structured/JSON
                    return True
                elif isinstance(output, dict):
                    return True
            return False
        except Exception:
            return False
