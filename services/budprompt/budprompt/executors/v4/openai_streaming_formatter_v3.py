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

Similar to OpenAIResponseFormatter but for incremental streaming output.
"""

import json
import time
import uuid
from typing import Any, Dict, List, Optional

from budmicroframe.commons import logging

from ...prompt.schemas import Message, ModelSettings


logger = logging.get_logger(__name__)


class OpenAIStreamingFormatter_V3:
    """Streaming formatter for OpenAI Responses API SSE events.

    This formatter maintains state across the streaming session and emits
    properly formatted SSE events matching OpenAI's Responses API specification.

    It mirrors the structure of OpenAIResponseFormatter but for incremental output.
    """

    def __init__(
        self,
        deployment_name: str,
        model_settings: Optional[ModelSettings],
        messages: List[Message],
    ):
        """Initialize streaming formatter with request context.

        Args:
            deployment_name: Name of the model deployment
            model_settings: Model configuration settings
            messages: Original input messages
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

        # State tracking
        self.sequence_number = -1  # Start at -1 so first increment returns 0
        self.accumulated_text = ""
        self.accumulated_thinking: List[str] = []
        self.accumulated_reasoning = ""  # For incremental reasoning deltas
        self.reasoning_started = False  # Track if we've emitted reasoning events
        self.model_name = deployment_name
        self.usage: Optional[Dict[str, Any]] = None

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

    def _build_base_response(self, status: str, output: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """Build base response object matching OpenAI Response schema.

        This reuses the same structure as OpenAIResponseSchema for consistency.

        Args:
            status: Response status (in_progress, completed, failed, etc.)
            output: Optional output items array

        Returns:
            Dictionary matching OpenAI Response object structure
        """
        return {
            "id": self.response_id,
            "object": "response",
            "created_at": self.created_at,
            "status": status,
            "background": False,
            "error": None,
            "incomplete_details": None,
            "instructions": None,
            "max_output_tokens": self.model_settings.max_tokens if self.model_settings else None,
            "max_tool_calls": None,
            "model": self.model_name,
            "output": output or [],
            "parallel_tool_calls": True,
            "previous_response_id": None,
            "prompt_cache_key": None,
            "reasoning": {"effort": None, "summary": None},
            "safety_identifier": None,
            "service_tier": "default",
            "store": True,
            "temperature": self.model_settings.temperature if self.model_settings else 1.0,
            "text": {"format": {"type": "text"}, "verbosity": "medium"},
            "tool_choice": "auto",
            "tools": [],
            "top_logprobs": 0,
            "top_p": self.model_settings.top_p if self.model_settings else 1.0,
            "truncation": "disabled",
            "usage": self.usage,
            "user": None,
            "metadata": {},
        }

    def format_response_created(self) -> str:
        """Emit response.created event - first event in stream.

        Returns:
            SSE-formatted response.created event
        """
        response = self._build_base_response(status="in_progress")

        event_data = {"type": "response.created", "sequence_number": self._next_sequence(), "response": response}
        return self._format_sse("response.created", event_data)

    def format_response_in_progress(self) -> str:
        """Emit response.in_progress event - indicates streaming has started.

        Returns:
            SSE-formatted response.in_progress event
        """
        response = self._build_base_response(status="in_progress")

        event_data = {"type": "response.in_progress", "sequence_number": self._next_sequence(), "response": response}
        return self._format_sse("response.in_progress", event_data)

    def format_output_item_added(self) -> str:
        """Emit response.output_item.added - output message starts.

        Returns:
            SSE-formatted response.output_item.added event
        """
        event_data = {
            "type": "response.output_item.added",
            "sequence_number": self._next_sequence(),
            "output_index": 0,
            "item": {
                "id": self.item_id,
                "type": "message",
                "status": "in_progress",
                "content": [],
                "role": "assistant",
            },
        }
        return self._format_sse("response.output_item.added", event_data)

    def format_content_part_added(self) -> str:
        """Emit response.content_part.added - content part starts.

        Returns:
            SSE-formatted response.content_part.added event
        """
        event_data = {
            "type": "response.content_part.added",
            "sequence_number": self._next_sequence(),
            "item_id": self.item_id,
            "output_index": 0,
            "content_index": 0,
            "part": {"type": "output_text", "annotations": [], "logprobs": [], "text": ""},
        }
        return self._format_sse("response.content_part.added", event_data)

    def format_output_text_delta(self, cumulative_text: str) -> Optional[str]:
        """Emit response.output_text.delta - incremental text chunk.

        Args:
            cumulative_text: The cumulative text from pydantic-ai TextPart
                            (contains all text from start, not just the delta)

        Returns:
            SSE-formatted response.output_text.delta event, or None if no new content
        """
        # Calculate the actual delta (difference from previous content)
        if cumulative_text.startswith(self.accumulated_text):
            # Extract only the new part
            actual_delta = cumulative_text[len(self.accumulated_text) :]
            if not actual_delta:
                # No new content, skip this event
                return None

            # Update accumulated text
            self.accumulated_text = cumulative_text

            event_data = {
                "type": "response.output_text.delta",
                "sequence_number": self._next_sequence(),
                "item_id": self.item_id,
                "output_index": 0,
                "content_index": 0,
                "delta": actual_delta,
                "logprobs": [],
            }
            return self._format_sse("response.output_text.delta", event_data)
        else:
            # Content doesn't build on previous (unexpected), use full content as delta
            logger.warning(f"Non-incremental content detected: {cumulative_text[:50]}...")
            self.accumulated_text = cumulative_text

            event_data = {
                "type": "response.output_text.delta",
                "sequence_number": self._next_sequence(),
                "item_id": self.item_id,
                "output_index": 0,
                "content_index": 0,
                "delta": cumulative_text,
                "logprobs": [],
            }
            return self._format_sse("response.output_text.delta", event_data)

    def format_output_text_done(self) -> str:
        """Emit response.output_text.done - text content finalized.

        Returns:
            SSE-formatted response.output_text.done event
        """
        event_data = {
            "type": "response.output_text.done",
            "sequence_number": self._next_sequence(),
            "item_id": self.item_id,
            "output_index": 0,
            "content_index": 0,
            "text": self.accumulated_text,
            "logprobs": [],
        }
        return self._format_sse("response.output_text.done", event_data)

    def format_content_part_done(self) -> str:
        """Emit response.content_part.done - content part complete.

        Returns:
            SSE-formatted response.content_part.done event
        """
        event_data = {
            "type": "response.content_part.done",
            "sequence_number": self._next_sequence(),
            "item_id": self.item_id,
            "output_index": 0,
            "content_index": 0,
            "part": {"type": "output_text", "annotations": [], "logprobs": [], "text": self.accumulated_text},
        }
        return self._format_sse("response.content_part.done", event_data)

    def format_output_item_done(self) -> str:
        """Emit response.output_item.done - output message complete.

        Returns:
            SSE-formatted response.output_item.done event
        """
        event_data = {
            "type": "response.output_item.done",
            "sequence_number": self._next_sequence(),
            "output_index": 0,
            "item": {
                "id": self.item_id,
                "type": "message",
                "status": "completed",
                "content": [{"type": "output_text", "annotations": [], "logprobs": [], "text": self.accumulated_text}],
                "role": "assistant",
            },
        }
        return self._format_sse("response.output_item.done", event_data)

    def format_response_completed(self, final_usage: Any) -> str:
        """Emit response.completed - final event with complete response.

        Args:
            final_usage: Usage information from pydantic-ai ModelResponse

        Returns:
            SSE-formatted response.completed event
        """
        # Format usage information
        if final_usage:
            usage_dict = final_usage if isinstance(final_usage, dict) else final_usage.__dict__
            self.usage = {
                "input_tokens": usage_dict.get("request_tokens", 0),
                "input_tokens_details": {"cached_tokens": 0, "reasoning_tokens": 0},
                "output_tokens": usage_dict.get("response_tokens", 0),
                "output_tokens_details": {"reasoning_tokens": 0},
                "total_tokens": usage_dict.get("total_tokens", 0),
            }

        # Build output array - reasoning item first (if exists), then message item
        output_items = []

        # Add reasoning output item if we had thinking/reasoning content
        if self.reasoning_started and self.accumulated_reasoning:
            reasoning_item = {
                "type": "reasoning",
                "id": self.reasoning_item_id,
                "status": "completed",
                "content": [{"type": "reasoning_text", "text": self.accumulated_reasoning}],
                "summary": [{"type": "summary_text", "text": self.accumulated_reasoning}],
            }
            output_items.append(reasoning_item)

        # Add message output item
        message_item = {
            "id": self.item_id,
            "type": "message",
            "status": "completed",
            "content": [{"type": "output_text", "annotations": [], "logprobs": [], "text": self.accumulated_text}],
            "role": "assistant",
        }
        output_items.append(message_item)

        # Build complete response with proper output
        response = self._build_base_response(status="completed", output=output_items)

        # reasoning field stays null (request-level config, not output)
        # Already handled in _build_base_response as {"effort": null, "summary": null}

        event_data = {"type": "response.completed", "sequence_number": self._next_sequence(), "response": response}
        return self._format_sse("response.completed", event_data)

    def format_response_failed(self, error_message: str, error_code: str = "server_error") -> str:
        """Emit response.failed - error event.

        Args:
            error_message: The error message
            error_code: The error code (default: server_error)

        Returns:
            SSE-formatted response.failed event
        """
        response = self._build_base_response(status="failed")
        response["error"] = {"code": error_code, "message": error_message}

        event_data = {"type": "response.failed", "sequence_number": self._next_sequence(), "response": response}
        return self._format_sse("response.failed", event_data)

    def format_reasoning_summary_part_added(self) -> str:
        """Emit response.reasoning_summary_part.added - reasoning starts.

        Returns:
            SSE-formatted response.reasoning_summary_part.added event
        """
        event_data = {
            "type": "response.reasoning_summary_part.added",
            "sequence_number": self._next_sequence(),
            "item_id": self.reasoning_item_id,
            "output_index": 0,
            "summary_index": 0,
            "part": {"type": "summary_text", "text": ""},
        }
        return self._format_sse("response.reasoning_summary_part.added", event_data)

    def format_reasoning_summary_text_delta(self, cumulative_thinking: str) -> Optional[str]:
        """Emit response.reasoning_summary_text.delta - incremental reasoning chunk.

        Args:
            cumulative_thinking: The cumulative thinking text from pydantic-ai ThinkingPart

        Returns:
            SSE-formatted response.reasoning_summary_text.delta event, or None if no new content
        """
        # Calculate actual delta (same pattern as text deltas)
        if cumulative_thinking.startswith(self.accumulated_reasoning):
            actual_delta = cumulative_thinking[len(self.accumulated_reasoning) :]
            if not actual_delta:
                return None

            self.accumulated_reasoning = cumulative_thinking

            event_data = {
                "type": "response.reasoning_summary_text.delta",
                "sequence_number": self._next_sequence(),
                "item_id": self.reasoning_item_id,
                "output_index": 0,
                "summary_index": 0,
                "delta": actual_delta,
            }
            return self._format_sse("response.reasoning_summary_text.delta", event_data)
        else:
            # Non-incremental, use full content
            logger.warning(f"Non-incremental reasoning content detected: {cumulative_thinking[:50]}...")
            self.accumulated_reasoning = cumulative_thinking

            event_data = {
                "type": "response.reasoning_summary_text.delta",
                "sequence_number": self._next_sequence(),
                "item_id": self.reasoning_item_id,
                "output_index": 0,
                "summary_index": 0,
                "delta": cumulative_thinking,
            }
            return self._format_sse("response.reasoning_summary_text.delta", event_data)

    def format_reasoning_summary_text_done(self) -> str:
        """Emit response.reasoning_summary_text.done - reasoning text finalized.

        Returns:
            SSE-formatted response.reasoning_summary_text.done event
        """
        event_data = {
            "type": "response.reasoning_summary_text.done",
            "sequence_number": self._next_sequence(),
            "item_id": self.reasoning_item_id,
            "output_index": 0,
            "summary_index": 0,
            "text": self.accumulated_reasoning,
        }
        return self._format_sse("response.reasoning_summary_text.done", event_data)

    def format_reasoning_summary_part_done(self) -> str:
        """Emit response.reasoning_summary_part.done - reasoning part complete.

        Returns:
            SSE-formatted response.reasoning_summary_part.done event
        """
        event_data = {
            "type": "response.reasoning_summary_part.done",
            "sequence_number": self._next_sequence(),
            "item_id": self.reasoning_item_id,
            "output_index": 0,
            "summary_index": 0,
            "part": {"type": "summary_text", "text": self.accumulated_reasoning},
        }
        return self._format_sse("response.reasoning_summary_part.done", event_data)

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
