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
import logging
import time
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional, Set, Union

from openai.types.responses import (
    Response,
    ResponseContentPartAddedEvent,
    ResponseContentPartDoneEvent,
    ResponseFunctionCallArgumentsDeltaEvent,
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
    ResponseTextDeltaEvent,
    ResponseTextDoneEvent,
    ResponseUsage,
)
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
)

from .schemas import MCPToolConfig, Message, ModelSettings


logger = logging.getLogger(__name__)


class OpenAIStreamingFormatter:
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
    ):
        """Initialize streaming formatter with request context.

        Args:
            deployment_name: Name of the model deployment
            model_settings: Model configuration settings
            messages: Original input messages
            tools: Optional list of tool configurations (MCP, etc.)
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

        # State tracking for SSE formatting
        self.sequence_number = -1  # Start at -1 so first increment returns 0
        self.accumulated_text = ""
        self.accumulated_thinking: List[str] = []
        self.accumulated_reasoning = ""  # For incremental reasoning deltas
        self.reasoning_started = False  # Track if we've emitted reasoning events
        self.model_name = deployment_name
        self.usage: Optional[Dict[str, Any]] = None

        # Event mapping state
        self.mcp_tool_names = self._build_mcp_tool_names_set(tools)
        self.output_index = 0
        self.pending_tool_calls: Dict[str, Dict[str, Any]] = {}
        self.current_text_item_id: Optional[str] = None
        self.current_reasoning_item_id: Optional[str] = None
        self.text_part_started = False
        self.reasoning_part_started = False

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

        # Extract event type from the dict
        event_type = event_dict.get("type", "unknown")

        # Format as SSE (compact JSON)
        return f"event: {event_type}\ndata: {json.dumps(event_dict, separators=(',', ':'))}\n\n"

    # ============================================================================
    # Event Mapping Methods (from pydantic_to_openai_event_mapper.py)
    # ============================================================================

    async def map_event(self, event: AgentStreamEvent) -> List[ResponseStreamEvent]:
        """Map a single pydantic-ai event to OpenAI SDK events.

        Args:
            event: Pydantic-ai stream event (PartStartEvent, PartDeltaEvent, etc.)

        Returns:
            List of OpenAI SDK ResponseStreamEvent instances
        """
        events: List[ResponseStreamEvent] = []

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

        return events

    async def _map_part_start_event(self, event: PartStartEvent) -> List[ResponseStreamEvent]:
        """Map PartStartEvent to OpenAI events.

        PartStartEvent indicates a new part started (text, thinking, or tool call).

        Args:
            event: PartStartEvent from pydantic-ai

        Returns:
            List of OpenAI events to emit
        """
        events: List[ResponseStreamEvent] = []

        # TextPart - Start of text output message
        if isinstance(event.part, TextPart):
            events.extend(await self._start_text_output(event.part))

        # ThinkingPart - Start of reasoning item
        elif isinstance(event.part, ThinkingPart):
            events.extend(await self._start_reasoning_output(event.part))

        # ToolCallPart - Tool call initiated by model
        elif isinstance(event.part, ToolCallPart):
            events.extend(await self._start_tool_call(event.part))

        return events

    async def _map_part_delta_event(self, event: PartDeltaEvent) -> List[ResponseStreamEvent]:
        """Map PartDeltaEvent to OpenAI delta events.

        PartDeltaEvent contains incremental updates to existing parts.

        Args:
            event: PartDeltaEvent from pydantic-ai

        Returns:
            List of OpenAI delta events
        """
        events: List[ResponseStreamEvent] = []

        # TextPartDelta - Incremental text content
        if isinstance(event.delta, TextPartDelta):
            delta_event = await self._compute_text_delta(event.delta)
            if delta_event:
                events.append(delta_event)

        # ThinkingPartDelta - Incremental reasoning content
        elif isinstance(event.delta, ThinkingPartDelta):
            delta_event = await self._compute_reasoning_delta(event.delta)
            if delta_event:
                events.append(delta_event)

        return events

    async def _map_function_tool_call_event(self, event: FunctionToolCallEvent) -> List[ResponseStreamEvent]:
        """Map FunctionToolCallEvent to OpenAI tool call events.

        This is emitted when a tool starts executing. At this point, the complete
        tool call with full arguments is available. We emit the arguments delta/done
        events here since we now have the complete arguments.

        Args:
            event: FunctionToolCallEvent from pydantic-ai

        Returns:
            List of OpenAI events for arguments delta/done
        """
        events: List[ResponseStreamEvent] = []

        tool_call_id = event.part.tool_call_id
        if tool_call_id not in self.pending_tool_calls:
            logger.warning(f"Received tool call event for unknown tool call: {tool_call_id}")
            return events

        # Get complete arguments from the tool call event
        arguments = event.part.args_as_json_str()
        tool_info = self.pending_tool_calls[tool_call_id]
        output_index = tool_info["output_index"]
        is_mcp = tool_info["is_mcp"]

        # Update stored arguments
        self.pending_tool_calls[tool_call_id]["args"] = arguments

        # Emit arguments delta and done events with complete arguments
        if is_mcp:
            # Emit response.mcp_call_arguments.delta
            events.append(
                ResponseMcpCallArgumentsDeltaEvent(
                    type="response.mcp_call_arguments.delta",
                    sequence_number=self._next_sequence(),
                    output_index=output_index,
                    item_id=tool_call_id,
                    delta=arguments,
                )
            )

            # Emit response.mcp_call_arguments.done
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
            # Emit response.function_call_arguments.delta
            events.append(
                ResponseFunctionCallArgumentsDeltaEvent(
                    type="response.function_call_arguments.delta",
                    sequence_number=self._next_sequence(),
                    output_index=output_index,
                    item_id=tool_call_id,
                    delta=arguments,
                )
            )

            # Emit response.function_call_arguments.done
            events.append(
                ResponseFunctionCallArgumentsDoneEvent(
                    type="response.function_call_arguments.done",
                    sequence_number=self._next_sequence(),
                    output_index=output_index,
                    item_id=tool_call_id,
                    arguments=arguments,
                )
            )

        logger.debug(f"Tool execution started with arguments: {event.part.tool_name} (call_id: {tool_call_id})")
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

        # Get pending tool call info
        if tool_call_id not in self.pending_tool_calls:
            logger.warning(f"Received tool result for unknown tool call: {tool_call_id}")
            return events

        tool_info = self.pending_tool_calls[tool_call_id]
        output_index = tool_info["output_index"]
        is_mcp = tool_info["is_mcp"]
        tool_name = tool_info["name"]
        arguments = tool_info["args"]

        # Format tool result as string
        if hasattr(tool_result, "model_dump_json"):
            result_str = tool_result.model_dump_json()
        elif hasattr(tool_result, "model_dump"):
            result_str = json.dumps(tool_result.model_dump())
        elif isinstance(tool_result, dict):
            result_str = json.dumps(tool_result)
        elif hasattr(tool_result, "content"):
            # Handle ToolReturnPart - extract just the content field
            result_str = tool_result.content
        else:
            result_str = str(tool_result)

        if is_mcp:
            # MCP tool completion
            server_label = tool_info["server_label"] or "unknown"

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
                        name=tool_name,
                        server_label=server_label,
                        arguments=arguments,
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
                        name=tool_name,
                        arguments=arguments,
                        id=f"fc_{uuid.uuid4().hex}",
                    ),
                )
            )

        # Remove from pending
        del self.pending_tool_calls[tool_call_id]

        return events

    # ============================================================================
    # Text Output Helper Methods
    # ============================================================================

    async def _start_text_output(self, part: TextPart) -> List[ResponseStreamEvent]:
        """Start a new text output message.

        If there's already a text output in progress, finalize it first.

        Args:
            part: TextPart from pydantic-ai

        Returns:
            List containing output_item.added and content_part.added events
        """
        events: List[ResponseStreamEvent] = []

        # Finalize any existing text output before starting a new one
        if self.text_part_started and self.current_text_item_id:
            events.extend(await self._finalize_text_output())

        # Generate unique item ID
        self.current_text_item_id = part.id or f"msg_{uuid.uuid4().hex}"
        current_output_index = self.output_index
        self.output_index += 1

        # Emit response.output_item.added
        events.append(
            ResponseOutputItemAddedEvent(
                type="response.output_item.added",
                sequence_number=self._next_sequence(),
                output_index=current_output_index,
                item=ResponseOutputMessage(
                    id=self.current_text_item_id,
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
                item_id=self.current_text_item_id,
                output_index=current_output_index,
                content_index=0,
                part=ResponseOutputText(
                    type="output_text",
                    text="",
                    annotations=[],
                    logprobs=[],
                ),
            )
        )

        self.text_part_started = True
        return events

    async def _compute_text_delta(self, delta: TextPartDelta) -> Optional[ResponseTextDeltaEvent]:
        """Compute text delta from cumulative content.

        Pydantic-AI provides cumulative content, but OpenAI expects individual deltas.

        Args:
            delta: TextPartDelta with cumulative content

        Returns:
            ResponseTextDeltaEvent with actual delta, or None if no new content
        """
        if not self.current_text_item_id:
            logger.warning("Received text delta without text output started")
            return None

        # Get cumulative content
        cumulative_content = delta.content_delta

        # Compute actual delta
        if cumulative_content.startswith(self.accumulated_text):
            actual_delta = cumulative_content[len(self.accumulated_text) :]
            if not actual_delta:
                return None  # No new content

            # Update accumulated text
            self.accumulated_text = cumulative_content

            # Get current output index (the one used when starting text output)
            current_output_index = self.output_index - 1

            return ResponseTextDeltaEvent(
                type="response.output_text.delta",
                sequence_number=self._next_sequence(),
                item_id=self.current_text_item_id,
                output_index=current_output_index,
                content_index=0,
                delta=actual_delta,
                logprobs=[],
            )
        else:
            # Non-incremental content (unexpected)
            logger.warning(f"Non-incremental text content: {cumulative_content[:50]}...")
            self.accumulated_text = cumulative_content
            current_output_index = self.output_index - 1

            return ResponseTextDeltaEvent(
                type="response.output_text.delta",
                sequence_number=self._next_sequence(),
                item_id=self.current_text_item_id,
                output_index=current_output_index,
                content_index=0,
                delta=cumulative_content,
                logprobs=[],
            )

    async def _finalize_text_output(self) -> List[ResponseStreamEvent]:
        """Finalize text output with .done events.

        Returns:
            List containing output_text.done, content_part.done, output_item.done
        """
        events: List[ResponseStreamEvent] = []

        if not self.current_text_item_id:
            return events

        current_output_index = self.output_index - 1

        # Emit response.output_text.done
        events.append(
            ResponseTextDoneEvent(
                type="response.output_text.done",
                sequence_number=self._next_sequence(),
                item_id=self.current_text_item_id,
                output_index=current_output_index,
                content_index=0,
                text=self.accumulated_text,
                logprobs=[],
            )
        )

        # Emit response.content_part.done
        events.append(
            ResponseContentPartDoneEvent(
                type="response.content_part.done",
                sequence_number=self._next_sequence(),
                item_id=self.current_text_item_id,
                output_index=current_output_index,
                content_index=0,
                part=ResponseOutputText(
                    type="output_text",
                    text=self.accumulated_text,
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
                output_index=current_output_index,
                item=ResponseOutputMessage(
                    id=self.current_text_item_id,
                    type="message",
                    status="completed",
                    content=[
                        ResponseOutputText(
                            type="output_text",
                            text=self.accumulated_text,
                            annotations=[],
                            logprobs=[],
                        )
                    ],
                    role="assistant",
                ),
            )
        )

        self.text_part_started = False
        return events

    # ============================================================================
    # Reasoning/Thinking Output Helper Methods
    # ============================================================================

    async def _start_reasoning_output(self, part: ThinkingPart) -> List[ResponseStreamEvent]:
        """Start a new reasoning output item.

        If there's already a reasoning output in progress, finalize it first.

        Args:
            part: ThinkingPart from pydantic-ai

        Returns:
            List containing output_item.added and reasoning_summary_part.added events
        """
        events: List[ResponseStreamEvent] = []

        # Finalize any existing reasoning output before starting a new one
        if self.reasoning_part_started and self.current_reasoning_item_id:
            events.extend(await self._finalize_reasoning_output())

        # Generate unique item ID
        self.current_reasoning_item_id = part.id or f"rs_{uuid.uuid4().hex}"
        current_output_index = self.output_index
        self.output_index += 1

        # Emit response.output_item.added (type: reasoning)
        events.append(
            ResponseOutputItemAddedEvent(
                type="response.output_item.added",
                sequence_number=self._next_sequence(),
                output_index=current_output_index,
                item=ResponseReasoningItem(
                    id=self.current_reasoning_item_id,
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
                item_id=self.current_reasoning_item_id,
                output_index=current_output_index,
                summary_index=0,
                part=ReasoningSummaryPart(type="summary_text", text=""),
            )
        )

        self.reasoning_part_started = True
        return events

    async def _compute_reasoning_delta(
        self, delta: ThinkingPartDelta
    ) -> Optional[ResponseReasoningSummaryTextDeltaEvent]:
        """Compute reasoning delta from cumulative content.

        Args:
            delta: ThinkingPartDelta with cumulative content

        Returns:
            ResponseReasoningSummaryTextDeltaEvent with actual delta, or None if no new content
        """
        if not self.current_reasoning_item_id:
            logger.warning("Received reasoning delta without reasoning output started")
            return None

        # Get cumulative content
        cumulative_content = delta.content_delta

        # Compute actual delta
        if cumulative_content.startswith(self.accumulated_reasoning):
            actual_delta = cumulative_content[len(self.accumulated_reasoning) :]
            if not actual_delta:
                return None

            self.accumulated_reasoning = cumulative_content
            current_output_index = self.output_index - 1

            return ResponseReasoningSummaryTextDeltaEvent(
                type="response.reasoning_summary_text.delta",
                sequence_number=self._next_sequence(),
                item_id=self.current_reasoning_item_id,
                output_index=current_output_index,
                summary_index=0,
                delta=actual_delta,
            )
        else:
            # Non-incremental
            logger.warning(f"Non-incremental reasoning content: {cumulative_content[:50]}...")
            self.accumulated_reasoning = cumulative_content
            current_output_index = self.output_index - 1

            return ResponseReasoningSummaryTextDeltaEvent(
                type="response.reasoning_summary_text.delta",
                sequence_number=self._next_sequence(),
                item_id=self.current_reasoning_item_id,
                output_index=current_output_index,
                summary_index=0,
                delta=cumulative_content,
            )

    async def _finalize_reasoning_output(self) -> List[ResponseStreamEvent]:
        """Finalize reasoning output with .done events.

        Returns:
            List containing reasoning_summary_text.done, reasoning_summary_part.done, output_item.done
        """
        events: List[ResponseStreamEvent] = []

        if not self.current_reasoning_item_id:
            return events

        current_output_index = self.output_index - 1

        # Emit response.reasoning_summary_text.done
        events.append(
            ResponseReasoningSummaryTextDoneEvent(
                type="response.reasoning_summary_text.done",
                sequence_number=self._next_sequence(),
                item_id=self.current_reasoning_item_id,
                output_index=current_output_index,
                summary_index=0,
                text=self.accumulated_reasoning,
            )
        )

        # Emit response.reasoning_summary_part.done
        events.append(
            ResponseReasoningSummaryPartDoneEvent(
                type="response.reasoning_summary_part.done",
                sequence_number=self._next_sequence(),
                item_id=self.current_reasoning_item_id,
                output_index=current_output_index,
                summary_index=0,
                part=ReasoningSummaryPartDone(type="summary_text", text=self.accumulated_reasoning),
            )
        )

        # Emit response.output_item.done
        events.append(
            ResponseOutputItemDoneEvent(
                type="response.output_item.done",
                sequence_number=self._next_sequence(),
                output_index=current_output_index,
                item=ResponseReasoningItem(
                    id=self.current_reasoning_item_id,
                    type="reasoning",
                    status="completed",
                    summary=[Summary(type="summary_text", text=self.accumulated_reasoning)],
                ),
            )
        )

        self.reasoning_part_started = False
        return events

    # ============================================================================
    # Tool Call Helper Methods
    # ============================================================================

    async def _start_tool_call(self, part: ToolCallPart) -> List[ResponseStreamEvent]:
        """Start a tool call (MCP or function).

        Args:
            part: ToolCallPart from pydantic-ai

        Returns:
            List containing output_item.added and tool call in_progress events
        """
        events: List[ResponseStreamEvent] = []

        # Determine if MCP or function tool
        is_mcp_tool = part.tool_name in self.mcp_tool_names

        # Get tool call details
        tool_call_id = part.tool_call_id
        tool_name = part.tool_name
        arguments = part.args_as_json_str()

        # Store in pending tools
        current_output_index = self.output_index
        self.pending_tool_calls[tool_call_id] = {
            "output_index": current_output_index,
            "name": tool_name,
            "args": arguments,
            "is_mcp": is_mcp_tool,
            "server_label": self._get_server_label(tool_name) if is_mcp_tool else None,
        }
        self.output_index += 1

        if is_mcp_tool:
            # MCP tool call
            server_label = self._get_server_label(tool_name) or "unknown"

            # Emit response.output_item.added (mcp_call)
            events.append(
                ResponseOutputItemAddedEvent(
                    type="response.output_item.added",
                    sequence_number=self._next_sequence(),
                    output_index=current_output_index,
                    item=ResponseOutputMcpCall(
                        id=tool_call_id,
                        type="mcp_call",
                        status="in_progress",
                        name=tool_name,
                        server_label=server_label,
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
                    output_index=current_output_index,
                    item_id=tool_call_id,
                )
            )

            # Note: mcp_call_arguments.delta and .done events are emitted later
            # in _map_function_tool_call_event() when we have complete arguments
        else:
            # Function tool call
            # Emit response.output_item.added (function_call)
            events.append(
                ResponseOutputItemAddedEvent(
                    type="response.output_item.added",
                    sequence_number=self._next_sequence(),
                    output_index=current_output_index,
                    item=ResponseFunctionToolCall(
                        type="function_call",
                        call_id=tool_call_id,
                        name=tool_name,
                        arguments="",  # Will be filled in later
                        id=f"fc_{uuid.uuid4().hex}",
                    ),
                )
            )

            # Note: function_call_arguments.delta and .done events are emitted later
            # in _map_function_tool_call_event() when we have complete arguments

        return events

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
    ) -> Response:
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

        return Response(
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
            text={"format": ResponseFormatText(type="text"), "verbosity": "medium"},
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
        and build a complete output array including MCP tools, calls, and text.

        Args:
            final_result: The AgentRunResult from pydantic-ai
            tools: MCP tool configurations

        Returns:
            List of output items for final response.completed event
        """
        from .openai_response_formatter import OpenAIResponseFormatter

        # Use the non-streaming formatter to extract output items from all messages
        formatter = OpenAIResponseFormatter()
        all_messages = final_result.all_messages()
        output_items, _ = await formatter._format_output_items(all_messages, tools)

        return output_items

    def build_final_output_items(self) -> List[Any]:
        """Build final output items array from accumulated state (fallback).

        This is a fallback method when AgentRunResult is not available.
        It only includes reasoning and text from the accumulated streaming state.

        Returns:
            List of output items for final response.completed event
        """
        output_items: List[Any] = []

        # Add reasoning item if present
        if self.accumulated_reasoning:
            output_items.append(
                ResponseReasoningItem(
                    id=self.current_reasoning_item_id or f"rs_{uuid.uuid4().hex}",
                    type="reasoning",
                    status="completed",
                    summary=[Summary(type="summary_text", text=self.accumulated_reasoning)],
                )
            )

        # Add text message if present
        if self.accumulated_text:
            output_items.append(
                ResponseOutputMessage(
                    id=self.current_text_item_id or f"msg_{uuid.uuid4().hex}",
                    type="message",
                    status="completed",
                    role="assistant",
                    content=[
                        ResponseOutputText(
                            type="output_text",
                            text=self.accumulated_text,
                            annotations=[],
                            logprobs=[],
                        )
                    ],
                )
            )

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
