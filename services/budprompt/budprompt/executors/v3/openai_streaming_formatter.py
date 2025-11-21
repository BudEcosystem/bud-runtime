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

"""Streaming formatter for OpenAI Responses API SSE events.

This module provides OpenAIStreamingFormatter which converts pydantic-ai
streaming responses to OpenAI-compatible Server-Sent Events format.

This formatter handles:
- Event mapping from pydantic-ai to OpenAI SDK events
- SSE formatting
- State tracking across streaming session
- MCP tool list pre-fetching
- Response object building
"""

import json
import time
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional, Set, Union

from budmicroframe.commons import logging
from openai.types.responses import (
    ResponseContentPartAddedEvent,
    ResponseContentPartDoneEvent,
    ResponseFunctionCallArgumentsDoneEvent,
    ResponseMcpCallArgumentsDeltaEvent,
    ResponseMcpCallArgumentsDoneEvent,
    ResponseMcpCallCompletedEvent,
    ResponseMcpCallInProgressEvent,
    ResponseMcpListToolsCompletedEvent,
    ResponseMcpListToolsInProgressEvent,
    ResponseOutputItemAddedEvent,
    ResponseOutputItemDoneEvent,
    ResponseReasoningSummaryPartAddedEvent,
    ResponseReasoningSummaryPartDoneEvent,
    ResponseReasoningSummaryTextDeltaEvent,
    ResponseReasoningSummaryTextDoneEvent,
    ResponseStreamEvent,
    ResponseTextConfig,
    ResponseTextDeltaEvent,
    ResponseTextDoneEvent,
    ResponseUsage,
)
from openai.types.responses.response_format_text_json_schema_config import ResponseFormatTextJSONSchemaConfig
from openai.types.responses.response_function_tool_call import ResponseFunctionToolCall
from openai.types.responses.response_input_item import Message as ResponseInputMessage
from openai.types.responses.response_input_text import ResponseInputText
from openai.types.responses.response_output_item import McpCall as ResponseOutputMcpCall
from openai.types.responses.response_output_item import McpListTools, McpListToolsTool
from openai.types.responses.response_output_message import ResponseOutputMessage
from openai.types.responses.response_output_text import ResponseOutputText
from openai.types.responses.response_reasoning_item import ResponseReasoningItem, Summary
from openai.types.responses.response_reasoning_summary_part_added_event import Part as ReasoningSummaryPart
from openai.types.responses.response_reasoning_summary_part_done_event import Part as ReasoningSummaryPartDone
from openai.types.responses.tool import Mcp, Tool
from openai.types.shared.reasoning import Reasoning
from openai.types.shared.response_format_text import ResponseFormatText
from pydantic import BaseModel
from pydantic_ai.messages import (
    AgentStreamEvent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
    ThinkingPart,
    ThinkingPartDelta,
    ToolCallPart,
    ToolCallPartDelta,
)

from ...commons.constants import STRUCTURED_OUTPUT_TOOL_NAME
from ...prompt.schemas import MCPToolConfig, Message, ModelSettings
from ...responses.schemas import OpenAIResponse


logger = logging.get_logger(__name__)


class PartState(BaseModel):
    """State tracking for a single part at a specific index.

    This class tracks the streaming state for each part (text, reasoning, or tool call)
    identified by its index in the pydantic-ai event stream.
    """

    part_type: str  # "text", "reasoning", or "tool_call"
    item_id: str  # Unique ID for this part
    output_index: int  # The index from pydantic-ai events
    accumulated_content: str = ""  # For text and reasoning parts
    accumulated_args: str = ""  # For tool call parts
    is_delta_streaming: bool = False  # True when receiving delta events
    tool_name: Optional[str] = None  # For tool calls
    server_label: Optional[str] = None  # For MCP tools
    is_mcp: bool = False  # Whether this is an MCP tool
    is_final_result_tool: bool = False  # Whether this is the final_result tool (streamed as text)
    stored_deltas: List[str] = []  # Store argument deltas for final_result tool
    finalized: bool = False  # Whether done events have been emitted


class OpenAIStreamingFormatter_V1:
    """Streaming formatter for OpenAI Responses API SSE events.

    This formatter maintains state across the streaming session and handles:
    - Event mapping from pydantic-ai to OpenAI SDK events
    - SSE formatting with proper event types and data
    - Output index tracking across all items
    - Delta computation from cumulative pydantic-ai content
    - Tool call lifecycle management (MCP and function tools)
    - Reasoning/thinking streaming
    - Response object building for OpenAI compatibility
    """

    def __init__(
        self,
        deployment_name: str,
        model_settings: Optional[ModelSettings],
        messages: List[Message],
        tools: Optional[List[MCPToolConfig]] = None,
        output_schema: Optional[Dict[str, Any]] = None,
    ):
        """Initialize streaming formatter with request context.

        Args:
            deployment_name: Name of the model deployment
            model_settings: Model configuration settings
            messages: Original input messages
            tools: Optional list of tool configurations (MCP, etc.)
            output_schema: Optional JSON schema for structured output
        """
        # Generate unique IDs
        self.response_id = f"resp_{uuid.uuid4().hex}"
        self.item_id = f"msg_{uuid.uuid4().hex}"
        self.reasoning_item_id = f"rs_{uuid.uuid4().hex}"
        self.created_at = int(time.time())

        # Store request context
        self.deployment_name = deployment_name
        self.model_settings = model_settings
        self.messages = messages
        self.tools_config = tools or []
        self.output_schema = output_schema

        # State tracking for SSE formatting
        self.sequence_number = -1  # Start at -1 so first increment returns 0
        self.model_name = deployment_name
        self.usage: Optional[Dict[str, Any]] = None

        # Per-index state tracking for all parts (text, reasoning, tool calls)
        self.parts_state: Dict[int, PartState] = {}

        # Event tracking for completion detection
        self.previous_event: Optional[AgentStreamEvent] = None

        # MCP tool list emission tracking
        self.mcp_tools_emitted = False
        self.mcp_tool_names = self._build_mcp_tool_names_set(tools)

    def _format_text_config(self) -> Optional[ResponseTextConfig]:
        """Format text configuration based on output schema.

        Returns:
            ResponseTextConfig with json_schema format if structured output,
            or text format if unstructured output
        """
        if self.output_schema:
            # Structured output with JSON schema
            json_schema_config = ResponseFormatTextJSONSchemaConfig.model_validate(
                {
                    "type": "json_schema",
                    "name": self.output_schema.get("title", "response_schema"),
                    "schema": self.output_schema,
                    "strict": True,
                }
            )
            return ResponseTextConfig(format=json_schema_config, verbosity="medium")
        else:
            # Plain text output
            return ResponseTextConfig(format=ResponseFormatText(type="text"), verbosity="medium")

    def _build_mcp_tool_names_set(self, tools: Optional[List[MCPToolConfig]]) -> Set[str]:
        """Build set of MCP tool names from tools configuration.

        Args:
            tools: List of tool configurations

        Returns:
            Set of MCP tool names
        """
        mcp_tool_names: Set[str] = set()
        if not tools:
            return mcp_tool_names

        for tool_config in tools:
            if tool_config.type == "mcp" and tool_config.allowed_tool_names:
                mcp_tool_names.update(tool_config.allowed_tool_names)

        return mcp_tool_names

    def _next_sequence(self) -> int:
        """Increment and return next sequence number.

        Returns:
            Next sequence number (starts from 0)
        """
        self.sequence_number += 1
        return self.sequence_number

    def _format_sse(self, event_type: str, data: Dict[str, Any]) -> str:
        r"""Format as Server-Sent Event with event and data lines.

        Args:
            event_type: The event type name (e.g., "response.created")
            data: The event data dictionary

        Returns:
            SSE-formatted string: "event: {type}\ndata: {json}\n\n"
        """
        # Use compact JSON format (no spaces) matching OpenAI
        return f"event: {event_type}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"

    def format_sse_from_event(self, event: Union[ResponseStreamEvent, BaseModel]) -> str:
        r"""Format OpenAI SDK event instance as Server-Sent Event.

        This method takes an official OpenAI SDK event instance and formats it
        as an SSE string. The event type is extracted from the event's 'type' field.

        Args:
            event: OpenAI SDK ResponseStreamEvent instance (or any Pydantic BaseModel)

        Returns:
            SSE-formatted string: "event: {type}\ndata: {json}\n\n"

        Example:
            >>> event = ResponseTextDeltaEvent(type="response.output_text.delta", ...)
            >>> sse_str = formatter.format_sse_from_event(event)
            >>> # Returns: "event: response.output_text.delta\ndata: {...}\n\n"
        """
        # Serialize the Pydantic model to dict
        event_dict = event.model_dump(mode="json", exclude_none=True)

        # NOTE: Post-process: Convert response.created_at from float to int
        # This is necessary because Pydantic serializes nested Response objects using
        # the parent class type (Response), not the runtime subclass type (OpenAIResponse),
        # which means our custom field_serializer is bypassed. Direct post-processing
        # is the most reliable solution for this OpenAI SDK compatibility issue.
        if (
            "response" in event_dict
            and isinstance(event_dict["response"], dict)
            and "created_at" in event_dict["response"]
        ):
            event_dict["response"]["created_at"] = int(event_dict["response"]["created_at"])

        # Extract event type from the dict
        event_type = event_dict.get("type", "unknown")

        # Format as SSE (compact JSON)
        return f"event: {event_type}\ndata: {json.dumps(event_dict, separators=(',', ':'))}\n\n"

    async def emit_mcp_tool_list_events(self) -> List[ResponseStreamEvent]:
        """Emit MCP tool list events for all MCP tools if present.

        This method should be called once after response.in_progress event.
        It fetches MCP tool lists and emits the complete lifecycle:
        output_item.added → mcp_list_tools.in_progress → mcp_list_tools.completed → output_item.done

        Returns:
            List of OpenAI ResponseStreamEvent instances for MCP tool lists
        """
        events: List[ResponseStreamEvent] = []

        if not self.tools_config or self.mcp_tools_emitted:
            return events

        # Check if any MCP tools are present
        has_mcp_tools = any(tool.type == "mcp" for tool in self.tools_config)
        if not has_mcp_tools:
            return events

        from .tool_loaders import MCPToolLoader

        loader = MCPToolLoader()

        for tool_config in self.tools_config:
            if tool_config.type != "mcp":
                continue

            try:
                # Load MCP server
                mcp_server = await loader.load_tools(tool_config)
                if not mcp_server:
                    logger.warning(f"Failed to load MCP server: {tool_config.server_label}")
                    continue

                # Fetch tool list
                tool_list_data = await loader.get_tool_list(mcp_server, tool_config.server_label or "unknown")
                if not tool_list_data:
                    logger.warning(f"No tool list data from MCP server: {tool_config.server_label}")
                    continue

                # Generate unique item ID
                item_id = f"mcpl_{uuid.uuid4().hex}"
                output_index = 0  # Static output_index for MCP tool lists

                # Parse tools from MCP response
                tools_list: List[McpListToolsTool] = []
                for tool_info in tool_list_data.get("tools", []):
                    tools_list.append(
                        McpListToolsTool(
                            name=tool_info.name,
                            description=getattr(tool_info, "description", None),
                            input_schema=(
                                tool_info.inputSchema if hasattr(tool_info, "inputSchema") else tool_info.input_schema
                            ),
                            annotations=getattr(tool_info, "annotations", None),
                        )
                    )

                # EVENT 1: response.output_item.added
                events.append(
                    ResponseOutputItemAddedEvent(
                        type="response.output_item.added",
                        sequence_number=self._next_sequence(),
                        output_index=output_index,
                        item=McpListTools(
                            id=item_id,
                            type="mcp_list_tools",
                            server_label=tool_list_data["server_label"],
                            tools=[],  # Empty initially
                        ),
                    )
                )

                # EVENT 2: response.mcp_list_tools.in_progress
                events.append(
                    ResponseMcpListToolsInProgressEvent(
                        type="response.mcp_list_tools.in_progress",
                        sequence_number=self._next_sequence(),
                        output_index=output_index,
                        item_id=item_id,
                    )
                )

                # EVENT 3: response.mcp_list_tools.completed
                events.append(
                    ResponseMcpListToolsCompletedEvent(
                        type="response.mcp_list_tools.completed",
                        sequence_number=self._next_sequence(),
                        output_index=output_index,
                        item_id=item_id,
                    )
                )

                # EVENT 4: response.output_item.done (with full tool list)
                events.append(
                    ResponseOutputItemDoneEvent(
                        type="response.output_item.done",
                        sequence_number=self._next_sequence(),
                        output_index=output_index,
                        item=McpListTools(
                            id=item_id,
                            type="mcp_list_tools",
                            server_label=tool_list_data["server_label"],
                            tools=tools_list,
                            error=tool_list_data.get("error"),
                        ),
                    )
                )

            except Exception as e:
                logger.error(f"Error fetching MCP tool list for {tool_config.server_label}: {str(e)}")
                continue

        # Mark as emitted
        self.mcp_tools_emitted = True
        return events

    # ============================================================================
    # Event Mapping Methods (from pydantic_to_openai_event_mapper.py)
    # ============================================================================

    async def map_event(self, event: AgentStreamEvent) -> List[ResponseStreamEvent]:
        """Map a single pydantic-ai event to OpenAI SDK events.

        This method also handles completion detection: when a PartDeltaEvent is followed
        by any non-PartDeltaEvent, it automatically finalizes the previous part.

        Args:
            event: Pydantic-ai stream event (PartStartEvent, PartDeltaEvent, etc.)

        Returns:
            List of OpenAI SDK ResponseStreamEvent instances
        """
        events: List[ResponseStreamEvent] = []

        # COMPLETION DETECTION: If previous event was PartDeltaEvent and current is not,
        # finalize the previous part
        if self.previous_event is not None and isinstance(self.previous_event, PartDeltaEvent):  # noqa: SIM102
            if not isinstance(event, PartDeltaEvent):
                # Finalize the previous part if it was streaming deltas
                prev_index = self.previous_event.index
                if prev_index in self.parts_state and self.parts_state[prev_index].is_delta_streaming:
                    finalization_events = await self._finalize_part(prev_index)
                    events.extend(finalization_events)

        # Handle PartStartEvent
        if isinstance(event, PartStartEvent):
            events.extend(await self._map_part_start_event(event))

        # Handle PartDeltaEvent
        elif isinstance(event, PartDeltaEvent):
            events.extend(await self._map_part_delta_event(event))

        # Handle FunctionToolCallEvent
        elif isinstance(event, FunctionToolCallEvent):
            events.extend(await self._map_function_tool_call_event(event))

        # Handle FunctionToolResultEvent
        elif isinstance(event, FunctionToolResultEvent):
            events.extend(await self._map_function_tool_result_event(event))

        # Note: FinalResultEvent is never sent by run_stream_events()
        # Only AgentRunResultEvent is sent, which is handled in the executor

        # Store current event for next iteration's completion detection
        self.previous_event = event

        return events

    async def _map_part_start_event(self, event: PartStartEvent) -> List[ResponseStreamEvent]:
        """Map PartStartEvent to OpenAI events.

        PartStartEvent indicates a new part started (text, thinking, or tool call).
        Uses event.index directly as output_index.

        Args:
            event: PartStartEvent from pydantic-ai

        Returns:
            List of OpenAI events to emit
        """
        events: List[ResponseStreamEvent] = []
        output_index = event.index

        # TextPart - Start of text output message
        if isinstance(event.part, TextPart):
            # Generate unique item ID
            item_id = event.part.id or f"msg_{uuid.uuid4().hex}"

            # Create state entry for this text part
            self.parts_state[output_index] = PartState(
                part_type="text",
                item_id=item_id,
                output_index=output_index,
                accumulated_content=event.part.content,
            )

            # Emit response.output_item.added
            events.append(
                ResponseOutputItemAddedEvent(
                    type="response.output_item.added",
                    sequence_number=self._next_sequence(),
                    output_index=output_index,
                    item=ResponseOutputMessage(
                        id=item_id,
                        type="message",
                        status="in_progress",
                        content=[],
                        role="assistant",
                    ),
                )
            )

            # Emit response.content_part.added
            events.append(
                ResponseContentPartAddedEvent(
                    type="response.content_part.added",
                    sequence_number=self._next_sequence(),
                    item_id=item_id,
                    output_index=output_index,
                    content_index=0,
                    part=ResponseOutputText(
                        type="output_text",
                        text="",
                        annotations=[],
                        logprobs=[],
                    ),
                )
            )

            # If TextPart has initial content, emit delta immediately
            if event.part.content:
                events.append(
                    ResponseTextDeltaEvent(
                        type="response.output_text.delta",
                        sequence_number=self._next_sequence(),
                        item_id=item_id,
                        output_index=output_index,
                        content_index=0,
                        delta=event.part.content,
                        logprobs=[],
                    )
                )
                # Mark that this part is streaming deltas for completion detection
                self.parts_state[output_index].is_delta_streaming = True

        # ThinkingPart - Start of reasoning item
        elif isinstance(event.part, ThinkingPart):
            # Generate unique item ID
            item_id = event.part.id or f"rs_{uuid.uuid4().hex}"

            # Create state entry for this reasoning part
            self.parts_state[output_index] = PartState(
                part_type="reasoning",
                item_id=item_id,
                output_index=output_index,
                accumulated_content=event.part.content,
            )

            # Emit response.output_item.added (type: reasoning)
            events.append(
                ResponseOutputItemAddedEvent(
                    type="response.output_item.added",
                    sequence_number=self._next_sequence(),
                    output_index=output_index,
                    item=ResponseReasoningItem(
                        id=item_id,
                        type="reasoning",
                        status="in_progress",
                        summary=[],
                    ),
                )
            )

            # Emit response.reasoning_summary_part.added
            events.append(
                ResponseReasoningSummaryPartAddedEvent(
                    type="response.reasoning_summary_part.added",
                    sequence_number=self._next_sequence(),
                    item_id=item_id,
                    output_index=output_index,
                    summary_index=0,
                    part=ReasoningSummaryPart(type="summary_text", text=""),
                )
            )

            # If ThinkingPart has initial content, emit delta immediately
            if event.part.content:
                events.append(
                    ResponseReasoningSummaryTextDeltaEvent(
                        type="response.reasoning_summary_text.delta",
                        sequence_number=self._next_sequence(),
                        item_id=item_id,
                        output_index=output_index,
                        summary_index=0,
                        delta=event.part.content,
                    )
                )
                # Mark that this part is streaming deltas for completion detection
                self.parts_state[output_index].is_delta_streaming = True

        # ToolCallPart - Tool call initiated by model
        elif isinstance(event.part, ToolCallPart):
            # IMPORTANT: Finalize any previous part that was streaming deltas
            # This handles the case where a tool call starts immediately after text/reasoning deltas
            for idx, state in self.parts_state.items():
                if idx < output_index and state.is_delta_streaming and not state.finalized:
                    finalization_events = await self._finalize_part(idx)
                    events.extend(finalization_events)

            # Determine if MCP or function tool
            is_mcp_tool = event.part.tool_name in self.mcp_tool_names
            tool_call_id = event.part.tool_call_id
            tool_name = event.part.tool_name
            arguments = event.part.args_as_json_str() if event.part.has_content() else ""

            # Detect if this is final_result tool for later processing
            is_final_result = tool_name == STRUCTURED_OUTPUT_TOOL_NAME
            if is_final_result:
                # Consider final_result tool used to build structured output as internal mcp call
                is_mcp_tool = True

            # Get server label for MCP tools
            server_label = self._get_server_label(tool_name) if is_mcp_tool else None

            # Create state entry for this tool call
            self.parts_state[output_index] = PartState(
                part_type="tool_call",
                item_id=tool_call_id,
                output_index=output_index,
                accumulated_args=arguments,
                tool_name=tool_name,
                server_label=server_label,
                is_mcp=is_mcp_tool,
                is_final_result_tool=is_final_result,
                stored_deltas=[],  # Initialize empty list for storing deltas
            )

            if is_mcp_tool:
                # MCP tool call
                # Emit response.output_item.added (mcp_call)
                events.append(
                    ResponseOutputItemAddedEvent(
                        type="response.output_item.added",
                        sequence_number=self._next_sequence(),
                        output_index=output_index,
                        item=ResponseOutputMcpCall(
                            id=tool_call_id,
                            type="mcp_call",
                            status="in_progress",
                            name=tool_name,
                            server_label=server_label or "unknown",
                            arguments="",
                            output=None,
                            error=None,
                        ),
                    )
                )

                # Emit response.mcp_call.in_progress
                events.append(
                    ResponseMcpCallInProgressEvent(
                        type="response.mcp_call.in_progress",
                        sequence_number=self._next_sequence(),
                        output_index=output_index,
                        item_id=tool_call_id,
                    )
                )
            else:
                # Function tool call
                # Emit response.output_item.added (function_call)
                events.append(
                    ResponseOutputItemAddedEvent(
                        type="response.output_item.added",
                        sequence_number=self._next_sequence(),
                        output_index=output_index,
                        item=ResponseFunctionToolCall(
                            type="function_call",
                            call_id=tool_call_id,
                            name=tool_name,
                            arguments="",  # Will be filled in later
                            id=f"fc_{uuid.uuid4().hex}",
                        ),
                    )
                )

        return events

    async def _map_part_delta_event(self, event: PartDeltaEvent) -> List[ResponseStreamEvent]:
        """Map PartDeltaEvent to OpenAI delta events.

        PartDeltaEvent contains incremental updates to existing parts.
        Uses event.index to track which part is being updated.

        Args:
            event: PartDeltaEvent from pydantic-ai

        Returns:
            List of OpenAI delta events
        """
        events: List[ResponseStreamEvent] = []
        output_index = event.index

        # Get state for this part
        if output_index not in self.parts_state:
            logger.warning(f"Received delta event for unknown part index: {output_index}")
            return events

        state = self.parts_state[output_index]
        state.is_delta_streaming = True  # Mark that deltas are being streamed

        # TextPartDelta - Incremental text content
        if isinstance(event.delta, TextPartDelta):
            # Pydantic-AI already provides incremental deltas in content_delta
            delta_content = event.delta.content_delta

            if delta_content:
                # Accumulate the delta into state
                state.accumulated_content += delta_content

                # Emit delta event with the incremental content
                events.append(
                    ResponseTextDeltaEvent(
                        type="response.output_text.delta",
                        sequence_number=self._next_sequence(),
                        item_id=state.item_id,
                        output_index=output_index,
                        content_index=0,
                        delta=delta_content,
                        logprobs=[],
                    )
                )

        # ThinkingPartDelta - Incremental reasoning content
        elif isinstance(event.delta, ThinkingPartDelta):
            # Pydantic-AI already provides incremental deltas in content_delta
            delta_content = event.delta.content_delta

            if delta_content:
                # Accumulate the delta into state
                state.accumulated_content += delta_content

                # Emit delta event with the incremental content
                events.append(
                    ResponseReasoningSummaryTextDeltaEvent(
                        type="response.reasoning_summary_text.delta",
                        sequence_number=self._next_sequence(),
                        item_id=state.item_id,
                        output_index=output_index,
                        summary_index=0,
                        delta=delta_content,
                    )
                )

        # ToolCallPartDelta - Incremental tool call arguments (NEW)
        elif isinstance(event.delta, ToolCallPartDelta):
            # Extract args_delta from the delta
            if event.delta.args_delta:
                args_delta_str = (
                    json.dumps(event.delta.args_delta)
                    if isinstance(event.delta.args_delta, dict)
                    else str(event.delta.args_delta)
                )

                # Accumulate arguments
                state.accumulated_args += args_delta_str

                # Store delta if this is final_result tool (for later text emission)
                if state.is_final_result_tool:
                    state.stored_deltas.append(args_delta_str)

                # Emit mcp_call_arguments.delta
                events.append(
                    ResponseMcpCallArgumentsDeltaEvent(
                        type="response.mcp_call_arguments.delta",
                        sequence_number=self._next_sequence(),
                        output_index=output_index,
                        item_id=state.item_id,
                        delta=args_delta_str,
                    )
                )

        return events

    async def _finalize_part(self, output_index: int) -> List[ResponseStreamEvent]:
        """Finalize a part by emitting done events.

        This is called when delta streaming ends for a part (when a PartDeltaEvent
        is followed by a non-PartDeltaEvent with the same index).

        Args:
            output_index: The index of the part to finalize

        Returns:
            List of done events for the part
        """
        events: List[ResponseStreamEvent] = []

        if output_index not in self.parts_state:
            return events

        state = self.parts_state[output_index]

        # Skip if already finalized
        if state.finalized:
            return events

        # Finalize based on part type
        if state.part_type == "text":
            # Emit response.output_text.done
            events.append(
                ResponseTextDoneEvent(
                    type="response.output_text.done",
                    sequence_number=self._next_sequence(),
                    item_id=state.item_id,
                    output_index=output_index,
                    content_index=0,
                    text=state.accumulated_content,
                    logprobs=[],
                )
            )

            # Emit response.content_part.done
            events.append(
                ResponseContentPartDoneEvent(
                    type="response.content_part.done",
                    sequence_number=self._next_sequence(),
                    item_id=state.item_id,
                    output_index=output_index,
                    content_index=0,
                    part=ResponseOutputText(
                        type="output_text",
                        text=state.accumulated_content,
                        annotations=[],
                        logprobs=[],
                    ),
                )
            )

            # Emit response.output_item.done
            events.append(
                ResponseOutputItemDoneEvent(
                    type="response.output_item.done",
                    sequence_number=self._next_sequence(),
                    output_index=output_index,
                    item=ResponseOutputMessage(
                        id=state.item_id,
                        type="message",
                        status="completed",
                        content=[
                            ResponseOutputText(
                                type="output_text",
                                text=state.accumulated_content,
                                annotations=[],
                                logprobs=[],
                            )
                        ],
                        role="assistant",
                    ),
                )
            )

        elif state.part_type == "reasoning":
            # Emit response.reasoning_summary_text.done
            events.append(
                ResponseReasoningSummaryTextDoneEvent(
                    type="response.reasoning_summary_text.done",
                    sequence_number=self._next_sequence(),
                    item_id=state.item_id,
                    output_index=output_index,
                    summary_index=0,
                    text=state.accumulated_content,
                )
            )

            # Emit response.reasoning_summary_part.done
            events.append(
                ResponseReasoningSummaryPartDoneEvent(
                    type="response.reasoning_summary_part.done",
                    sequence_number=self._next_sequence(),
                    item_id=state.item_id,
                    output_index=output_index,
                    summary_index=0,
                    part=ReasoningSummaryPartDone(type="summary_text", text=state.accumulated_content),
                )
            )

            # Emit response.output_item.done
            events.append(
                ResponseOutputItemDoneEvent(
                    type="response.output_item.done",
                    sequence_number=self._next_sequence(),
                    output_index=output_index,
                    item=ResponseReasoningItem(
                        id=state.item_id,
                        type="reasoning",
                        status="completed",
                        summary=[Summary(type="summary_text", text=state.accumulated_content)],
                    ),
                )
            )

        # Tool calls are finalized in _map_function_tool_result_event
        # so we don't handle them here

        # Mark as finalized
        state.finalized = True

        return events

    async def finalize_all_parts(self) -> List[ResponseStreamEvent]:
        """Finalize all parts that have been streaming but not yet finalized.

        This should be called at the end of streaming (before response.completed)
        to ensure all parts are properly closed.

        Returns:
            List of all done events for unfinalized parts
        """
        events: List[ResponseStreamEvent] = []

        # Iterate through all parts and finalize any that are still streaming
        for output_index, state in self.parts_state.items():
            if state.is_delta_streaming and not state.finalized:
                finalization_events = await self._finalize_part(output_index)
                events.extend(finalization_events)

        return events

    async def _map_function_tool_call_event(self, event: FunctionToolCallEvent) -> List[ResponseStreamEvent]:
        """Map FunctionToolCallEvent to OpenAI tool call events.

        This is emitted when a tool starts executing. We emit the arguments.done
        event using accumulated arguments from the state.

        Args:
            event: FunctionToolCallEvent from pydantic-ai

        Returns:
            List of OpenAI events for arguments.done
        """
        events: List[ResponseStreamEvent] = []

        tool_call_id = event.part.tool_call_id

        # Find the tool call state by item_id
        tool_state = None
        output_index = None
        for idx, state in self.parts_state.items():
            if state.part_type == "tool_call" and state.item_id == tool_call_id:
                tool_state = state
                output_index = idx
                break

        if tool_state is None:
            logger.warning(f"Received tool call event for unknown tool call: {tool_call_id}")
            return events

        # Use accumulated arguments from state
        arguments = tool_state.accumulated_args or event.part.args_as_json_str()

        # Emit arguments.done event
        if tool_state.is_mcp:
            # MCP tool
            events.append(
                ResponseMcpCallArgumentsDoneEvent(
                    type="response.mcp_call_arguments.done",
                    sequence_number=self._next_sequence(),
                    output_index=output_index,
                    item_id=tool_call_id,
                    arguments=arguments,
                )
            )
        else:
            # Function tool call
            events.append(
                ResponseFunctionCallArgumentsDoneEvent(
                    type="response.function_call_arguments.done",
                    sequence_number=self._next_sequence(),
                    output_index=output_index,
                    item_id=tool_call_id,
                    name=tool_state.tool_name,
                    arguments=arguments,
                )
            )

        logger.debug(f"Tool execution started: {tool_state.tool_name} (call_id: {tool_call_id})")
        return events

    async def _map_function_tool_result_event(self, event: FunctionToolResultEvent) -> List[ResponseStreamEvent]:
        """Map FunctionToolResultEvent to OpenAI tool completion events.

        This is emitted when a tool finishes executing with results.

        Args:
            event: FunctionToolResultEvent from pydantic-ai

        Returns:
            List of OpenAI tool completion events
        """
        events: List[ResponseStreamEvent] = []

        tool_call_id = event.tool_call_id
        tool_result = event.result

        # Find the tool call state by item_id
        tool_state = None
        output_index = None
        for idx, state in self.parts_state.items():
            if state.part_type == "tool_call" and state.item_id == tool_call_id:
                tool_state = state
                output_index = idx
                break

        if tool_state is None:
            logger.warning(f"Received tool result for unknown tool call: {tool_call_id}")
            return events

        # Format tool result as string
        if hasattr(tool_result, "model_response_str"):
            # Handle ToolReturnPart - use model_response_str() to properly serialize content
            # This method handles both string and non-string content (lists, dicts) correctly
            result_str = tool_result.model_response_str()
        elif hasattr(tool_result, "model_dump_json"):
            result_str = tool_result.model_dump_json()
        elif hasattr(tool_result, "model_dump"):
            result_str = json.dumps(tool_result.model_dump())
        elif isinstance(tool_result, dict):
            result_str = json.dumps(tool_result)
        else:
            result_str = str(tool_result)

        if tool_state.is_mcp:
            # MCP tool completion
            # Emit response.mcp_call.completed
            events.append(
                ResponseMcpCallCompletedEvent(
                    type="response.mcp_call.completed",
                    sequence_number=self._next_sequence(),
                    output_index=output_index,
                    item_id=tool_call_id,
                )
            )

            # Emit response.output_item.done with result
            events.append(
                ResponseOutputItemDoneEvent(
                    type="response.output_item.done",
                    sequence_number=self._next_sequence(),
                    output_index=output_index,
                    item=ResponseOutputMcpCall(
                        id=tool_call_id,
                        type="mcp_call",
                        status="completed",
                        name=tool_state.tool_name,
                        server_label=tool_state.server_label or "unknown",
                        arguments=tool_state.accumulated_args,
                        output=result_str,
                        error=None,
                    ),
                )
            )
        else:
            # Function tool completion
            # Note: OpenAI SDK doesn't have specific function_call.completed event
            # Just emit output_item.done

            # Emit response.output_item.done
            events.append(
                ResponseOutputItemDoneEvent(
                    type="response.output_item.done",
                    sequence_number=self._next_sequence(),
                    output_index=output_index,
                    item=ResponseFunctionToolCall(
                        type="function_call",
                        call_id=tool_call_id,
                        name=tool_state.tool_name,
                        arguments=tool_state.accumulated_args,
                        id=f"fc_{uuid.uuid4().hex}",
                    ),
                )
            )

        # Mark as finalized
        tool_state.finalized = True

        return events

    async def _map_post_final_result_event(self) -> List[ResponseStreamEvent]:
        events: List[ResponseStreamEvent] = []

        # Find the tool call state by item_id
        tool_state = None
        output_index = None
        for idx, state in self.parts_state.items():
            if state.is_final_result_tool and state.stored_deltas:
                tool_state = state
                output_index = idx
                break

        logger.debug("Found tool state: %s", tool_state)

        # If this is final_result tool, emit stored deltas as output_text
        if tool_state:
            # First, emit MCP tool completion events (that were skipped during normal flow)

            # 1. Emit response.mcp_call_arguments.done
            events.append(
                ResponseMcpCallArgumentsDoneEvent(
                    type="response.mcp_call_arguments.done",
                    sequence_number=self._next_sequence(),
                    output_index=output_index,
                    item_id=tool_state.item_id,
                    arguments=tool_state.accumulated_args,
                )
            )

            # 2. Emit response.mcp_call.completed
            events.append(
                ResponseMcpCallCompletedEvent(
                    type="response.mcp_call.completed",
                    sequence_number=self._next_sequence(),
                    output_index=output_index,
                    item_id=tool_state.item_id,
                )
            )

            # 3. Emit response.output_item.done (for the mcp_call)
            events.append(
                ResponseOutputItemDoneEvent(
                    type="response.output_item.done",
                    sequence_number=self._next_sequence(),
                    output_index=output_index,
                    item=ResponseOutputMcpCall(
                        id=tool_state.item_id,
                        type="mcp_call",
                        status="completed",
                        name=tool_state.tool_name,
                        server_label=tool_state.server_label or "unknown",
                        arguments=tool_state.accumulated_args,
                        output="",  # Empty output for final_result internal tool
                        error=None,
                    ),
                )
            )

            # Now emit the text output representation
            # Create a new message output item for text representation
            message_id = f"msg_{uuid.uuid4().hex}"
            next_output_index = output_index + 1  # Use next output index

            # 4. Emit response.output_item.added (message)
            events.append(
                ResponseOutputItemAddedEvent(
                    type="response.output_item.added",
                    sequence_number=self._next_sequence(),
                    output_index=next_output_index,
                    item=ResponseOutputMessage(
                        id=message_id,
                        type="message",
                        role="assistant",
                        status="in_progress",
                        content=[],
                    ),
                )
            )

            # 5. Emit response.content_part.added (text part)
            events.append(
                ResponseContentPartAddedEvent(
                    type="response.content_part.added",
                    sequence_number=self._next_sequence(),
                    output_index=next_output_index,
                    item_id=message_id,
                    content_index=0,
                    part=ResponseOutputText(
                        type="output_text",
                        text="",
                        annotations=[],
                    ),
                )
            )

            # 6. Emit response.output_text.delta for each stored delta
            for delta_str in tool_state.stored_deltas:
                events.append(
                    ResponseTextDeltaEvent(
                        type="response.output_text.delta",
                        sequence_number=self._next_sequence(),
                        item_id=message_id,
                        output_index=next_output_index,
                        content_index=0,
                        delta=delta_str,
                        logprobs=[],
                    )
                )

            # 7. Emit response.output_text.done
            complete_text = "".join(tool_state.stored_deltas)
            events.append(
                ResponseTextDoneEvent(
                    type="response.output_text.done",
                    sequence_number=self._next_sequence(),
                    item_id=message_id,
                    output_index=next_output_index,
                    content_index=0,
                    text=complete_text,
                    logprobs=[],
                )
            )

            # 8. Emit response.content_part.done
            events.append(
                ResponseContentPartDoneEvent(
                    type="response.content_part.done",
                    sequence_number=self._next_sequence(),
                    item_id=message_id,
                    output_index=next_output_index,
                    content_index=0,
                    part=ResponseOutputText(
                        type="output_text",
                        text=complete_text,
                        annotations=[],
                        logprobs=[],
                    ),
                )
            )

            # 9. Emit response.output_item.done (message)
            events.append(
                ResponseOutputItemDoneEvent(
                    type="response.output_item.done",
                    sequence_number=self._next_sequence(),
                    output_index=next_output_index,
                    item=ResponseOutputMessage(
                        id=message_id,
                        type="message",
                        role="assistant",
                        status="completed",
                        content=[
                            ResponseOutputText(
                                type="output_text",
                                text=complete_text,
                                annotations=[],
                                logprobs=[],
                            )
                        ],
                    ),
                )
            )

        return events

    # ============================================================================
    # Helper Methods
    # ============================================================================

    def _get_server_label(self, tool_name: str) -> Optional[str]:
        """Get server label for an MCP tool.

        Args:
            tool_name: Name of the MCP tool

        Returns:
            Server label if found, None otherwise
        """
        for tool_config in self.tools_config:
            if tool_config.type == "mcp" and tool_name in tool_config.allowed_tool_names:
                return tool_config.server_label
        return None

    # ============================================================================
    # Response Building Helper Methods (from executors.py)
    # ============================================================================

    def build_instructions_from_messages(self, messages: List[Message]) -> List[ResponseInputMessage]:
        """Build instructions array from input messages.

        Args:
            messages: List of input messages with roles and content

        Returns:
            List of ResponseInputMessage for instructions field
        """
        instructions: List[ResponseInputMessage] = []

        for msg in messages:
            # Only include system and user messages as instructions
            if msg.role in ["system", "user", "developer"]:
                instructions.append(
                    ResponseInputMessage(
                        type="message",
                        role=msg.role,
                        content=[
                            ResponseInputText(
                                type="input_text",
                                text=msg.content,
                            )
                        ],
                        status="completed",
                    )
                )

        return instructions

    def build_response_object(
        self,
        status: str,
        instructions: Optional[List[ResponseInputMessage]] = None,
        output_items: Optional[List[Any]] = None,
        usage: Optional[Dict[str, Any]] = None,
        error: Optional[Dict[str, str]] = None,
    ) -> OpenAIResponse:
        """Build Response object for OpenAI streaming events.

        Args:
            status: Response status (in_progress, completed, failed)
            instructions: List of input messages
            output_items: List of output items
            usage: Usage information
            error: Error information if failed

        Returns:
            Response object matching OpenAI schema
        """
        # Format tools array
        formatted_tools: List[Tool] = []
        if self.tools_config:
            for tool_config in self.tools_config:
                if tool_config.type == "mcp":
                    formatted_tools.append(
                        Mcp(
                            type="mcp",
                            server_label=tool_config.server_label,
                            server_url=tool_config.server_url,
                            allowed_tools=list(tool_config.allowed_tools) if tool_config.allowed_tools else None,
                            headers=None,
                            require_approval=tool_config.require_approval or "never",
                        )
                    )

        # Format usage
        usage_obj = None
        if usage:
            usage_obj = ResponseUsage(**usage)

        # Format text config based on output schema
        text_config = self._format_text_config()

        return OpenAIResponse(
            id=self.response_id,
            object="response",
            created_at=self.created_at,
            status=status,
            model=self.model_name,
            output=output_items or [],
            instructions=instructions or [],
            usage=usage_obj,
            background=False,
            error=error,
            incomplete_details=None,
            max_output_tokens=self.model_settings.max_tokens if self.model_settings else None,
            max_tool_calls=None,
            parallel_tool_calls=True,
            previous_response_id=None,
            prompt_cache_key=None,
            reasoning=Reasoning(effort=None, summary=None),
            safety_identifier=None,
            service_tier="default",
            store=True,
            temperature=self.model_settings.temperature if self.model_settings else None,
            text=text_config,
            tool_choice="auto",
            tools=formatted_tools,
            top_logprobs=0,
            top_p=self.model_settings.top_p if self.model_settings else None,
            truncation="disabled",
            user=None,
            metadata={},
        )

    async def build_final_output_items_from_result(
        self,
        final_result,  # AgentRunResult type
        tools: Optional[List[MCPToolConfig]] = None,
    ) -> List[Any]:
        """Build complete output items from AgentRunResult.

        This reuses the non-streaming formatter's logic to parse all messages
        and build a complete output array including MCP tools, calls, text, and
        structured output from final_result tool returns.

        Args:
            final_result: The AgentRunResult from pydantic-ai
            tools: MCP tool configurations

        Returns:
            List of output items for final response.completed event
        """
        from .openai_response_formatter import OpenAIResponseFormatter_V1

        # Use the non-streaming formatter to build complete output items (includes structured output)
        formatter = OpenAIResponseFormatter_V1()
        all_messages = final_result.all_messages()
        output_items, _ = await formatter.build_complete_output_items(all_messages, final_result, tools)

        return output_items

    async def build_final_instructions_from_result(
        self,
        final_result,  # AgentRunResult type
        tools: Optional[List[MCPToolConfig]] = None,
    ) -> List[Any]:
        """Build complete instructions from AgentRunResult.

        This reuses the non-streaming formatter's logic to parse all messages
        and build a complete instructions array including system/user messages,
        tool returns, and retry prompts.

        Args:
            final_result: The AgentRunResult from pydantic-ai
            tools: MCP tool configurations

        Returns:
            List of instruction items (ResponseInputMessage) for final response
        """
        from .openai_response_formatter import OpenAIResponseFormatter_V1

        # Use the non-streaming formatter to extract instructions from all messages
        formatter = OpenAIResponseFormatter_V1()
        all_messages = final_result.all_messages()

        # First get output items to extract MCP tool call IDs
        _, mcp_tool_call_ids = await formatter._format_output_items(all_messages, tools)

        # Then format input items (instructions) with the MCP tool call IDs
        input_items = await formatter._format_input_items(all_messages, mcp_tool_call_ids, tools)

        return input_items

    def build_final_output_items(self) -> List[Any]:
        """Build final output items array from parts_state (fallback).

        This is a fallback method when AgentRunResult is not available.
        It iterates through all parts_state and builds output items.

        Returns:
            List of output items for final response.completed event
        """
        output_items: List[Any] = []

        # Iterate through parts_state and build output items
        # Sort by output_index to maintain correct order
        for output_index in sorted(self.parts_state.keys()):
            state = self.parts_state[output_index]

            if state.part_type == "reasoning":
                output_items.append(
                    ResponseReasoningItem(
                        id=state.item_id,
                        type="reasoning",
                        status="completed",
                        summary=[Summary(type="summary_text", text=state.accumulated_content)],
                    )
                )

            elif state.part_type == "text":
                output_items.append(
                    ResponseOutputMessage(
                        id=state.item_id,
                        type="message",
                        status="completed",
                        role="assistant",
                        content=[
                            ResponseOutputText(
                                type="output_text",
                                text=state.accumulated_content,
                                annotations=[],
                                logprobs=[],
                            )
                        ],
                    )
                )

            elif state.part_type == "tool_call":
                # Tool calls are already handled via FunctionToolResultEvent
                # They're finalized during streaming, not here
                pass

        return output_items

    async def fetch_and_emit_mcp_tool_lists(self) -> AsyncGenerator[str, None]:
        """Pre-fetch MCP tool lists and emit as SSE events.

        This method loads all MCP servers, fetches their tool lists, and emits
        the complete lifecycle events for each tool list (added → in_progress → completed → done).

        Yields:
            SSE-formatted event strings for MCP tool list lifecycle
        """
        if not self.tools_config:
            return

        from .tool_loaders import MCPToolLoader

        loader = MCPToolLoader()

        for tool_config in self.tools_config:
            if tool_config.type != "mcp":
                continue

            try:
                # Load MCP server
                mcp_server = await loader.load_tools(tool_config)
                if not mcp_server:
                    logger.warning(f"Failed to load MCP server: {tool_config.server_label}")
                    continue

                # Fetch tool list
                tool_list_data = await loader.get_tool_list(mcp_server, tool_config.server_label or "unknown")
                if not tool_list_data:
                    logger.warning(f"No tool list data from MCP server: {tool_config.server_label}")
                    continue

                # Generate unique item ID
                item_id = f"mcpl_{uuid.uuid4().hex}"
                current_output_index = self.output_index
                self.output_index += 1

                # Parse tools from MCP response
                tools_list: List[McpListToolsTool] = []
                for tool_info in tool_list_data.get("tools", []):
                    tools_list.append(
                        McpListToolsTool(
                            name=tool_info.name,
                            description=getattr(tool_info, "description", None),
                            input_schema=(
                                tool_info.inputSchema if hasattr(tool_info, "inputSchema") else tool_info.input_schema
                            ),
                            annotations=getattr(tool_info, "annotations", None),
                        )
                    )

                # EVENT 1: response.output_item.added
                yield self.format_sse_from_event(
                    ResponseOutputItemAddedEvent(
                        type="response.output_item.added",
                        sequence_number=self._next_sequence(),
                        output_index=current_output_index,
                        item=McpListTools(
                            id=item_id,
                            type="mcp_list_tools",
                            server_label=tool_list_data["server_label"],
                            tools=[],  # Empty initially
                        ),
                    )
                )

                # EVENT 2: response.mcp_list_tools.in_progress
                yield self.format_sse_from_event(
                    ResponseMcpListToolsInProgressEvent(
                        type="response.mcp_list_tools.in_progress",
                        sequence_number=self._next_sequence(),
                        output_index=current_output_index,
                        item_id=item_id,
                    )
                )

                # EVENT 3: response.mcp_list_tools.completed
                yield self.format_sse_from_event(
                    ResponseMcpListToolsCompletedEvent(
                        type="response.mcp_list_tools.completed",
                        sequence_number=self._next_sequence(),
                        output_index=current_output_index,
                        item_id=item_id,
                    )
                )

                # EVENT 4: response.output_item.done (with full tool list)
                yield self.format_sse_from_event(
                    ResponseOutputItemDoneEvent(
                        type="response.output_item.done",
                        sequence_number=self._next_sequence(),
                        output_index=current_output_index,
                        item=McpListTools(
                            id=item_id,
                            type="mcp_list_tools",
                            server_label=tool_list_data["server_label"],
                            tools=tools_list,
                            error=tool_list_data.get("error"),
                        ),
                    )
                )

            except Exception as e:
                logger.error(f"Error fetching MCP tool list for {tool_config.server_label}: {str(e)}")
                continue

    def add_thinking_content(self, thinking_text: str):
        """Accumulate thinking/reasoning content for final summary.

        Args:
            thinking_text: Thinking content from ThinkingPart
        """
        if thinking_text:
            self.accumulated_thinking.append(thinking_text)

    def update_model_name(self, model_name: str):
        """Update model name from ModelResponse if available.

        Args:
            model_name: The model name from streaming response
        """
        if model_name:
            self.model_name = model_name
