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

"""Validation-aware V4 formatter for streaming with field-level validation.

This module provides OpenAIStreamingValidationFormatter_V4 which extends
OpenAIStreamingFormatter_V4 to add validation for structured output fields.
"""

from typing import Any, Dict, List, Optional

from budmicroframe.commons import logging
from openai.types.responses import ResponseStreamEvent
from pydantic import ValidationError
from pydantic_ai.messages import AgentStreamEvent, PartDeltaEvent, ToolCallPartDelta

from ...prompt.schemas import MCPToolConfig, Message, ModelSettings
from .openai_streaming_formatter import OpenAIStreamingFormatter_V4
from .streaming_json_validator import StreamingJSONValidator


logger = logging.get_logger(__name__)


class OpenAIStreamingValidationFormatter_V4(OpenAIStreamingFormatter_V4):
    """V4 formatter with integrated validation for structured output.

    This class extends OpenAIStreamingFormatter_V4 to add field-level validation
    during streaming. It inherits all V4 capabilities (MCP tools, function calls,
    reasoning) while adding validation logic for structured output fields.

    The validator integrates with V4's event mapping system to validate fields
    before emitting them to the client, enabling retry with preserved valid fields.
    """

    def __init__(
        self,
        validator: StreamingJSONValidator,
        deployment_name: str,
        model_settings: Optional[ModelSettings],
        messages: List[Message],
        tools: Optional[List[MCPToolConfig]] = None,
        output_schema: Optional[Dict[str, Any]] = None,
    ):
        """Initialize validation formatter.

        Args:
            validator: Streaming JSON validator for field-level validation
            deployment_name: Name of the model deployment
            model_settings: Model configuration settings
            messages: Original input messages
            tools: Optional list of tool configurations (MCP, etc.)
            output_schema: Optional JSON schema for structured output
        """
        # Initialize parent V4 formatter with all its capabilities
        super().__init__(
            deployment_name=deployment_name,
            model_settings=model_settings,
            messages=messages,
            tools=tools,
            output_schema=output_schema,
        )

        # Validation-specific state
        self.validator = validator
        self.validated_fields: Dict[str, Any] = {}  # Fields that passed validation
        self.failed_fields: Dict[str, Any] = {}  # Fields that failed validation
        self.validation_error: Optional[str] = None  # Last validation error message
        self.last_sent_fields: Dict[str, Any] = {}  # Track what we've sent for delta computation

        # Text item ID for output_text delta events
        import uuid

        self.text_item_id = f"msg_{uuid.uuid4().hex}"

        # Flag to control sequence assignment (for lazy sequence assignment)
        self.should_assign_sequence = True  # Default: always assign sequences

    def _next_sequence(self) -> int:
        """Override parent's _next_sequence to support conditional assignment.

        When should_assign_sequence is False, returns -1 (placeholder) without
        incrementing the counter. This prevents sequence gaps when events are
        generated but not yielded to the client.

        Returns:
            Next sequence number (0, 1, 2...) or -1 if not assigning
        """
        if not self.should_assign_sequence:
            return -1  # Don't increment counter, return placeholder

        # Call parent's increment logic
        return super()._next_sequence()

    async def map_event(self, event: AgentStreamEvent, assign_sequence: bool = True) -> List[ResponseStreamEvent]:
        """Override parent's map_event to control sequence assignment via flag.

        Sets the should_assign_sequence flag before calling parent's map_event,
        which causes all _next_sequence() calls in the parent to respect the flag.

        Args:
            event: Pydantic-ai stream event (PartStartEvent, PartDeltaEvent, etc.)
            assign_sequence: If False, events are generated without sequence numbers
                             (sequence_number=-1). If True, sequences are assigned normally.

        Returns:
            List of OpenAI SDK ResponseStreamEvent instances
        """
        # Set flag before calling parent
        self.should_assign_sequence = assign_sequence

        try:
            # Call parent's map_event - it will use our overridden _next_sequence()
            events = await super().map_event(event)
            return events
        finally:
            # Reset flag to default (always reset even if exception occurs)
            self.should_assign_sequence = True

    def _format_sse(self, event_type: str, data: Dict[str, Any]) -> str:
        r"""Format as Server-Sent Event with event and data lines.

        Args:
            event_type: The event type name (e.g., "response.created")
            data: The event data dictionary

        Returns:
            SSE-formatted string: "event: {type}\\ndata: {json}\\n\\n"
        """
        import json

        # Use compact JSON format (no spaces) matching OpenAI
        return f"event: {event_type}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"

    async def map_event_with_validation(self, event: AgentStreamEvent) -> List[ResponseStreamEvent]:
        """Map pydantic-ai event to OpenAI events with validation.

        This method extends the parent's map_event() by adding validation
        for structured output fields. Non-structured events (reasoning, tools,
        MCP) pass through unchanged.

        Args:
            event: Pydantic-ai stream event

        Returns:
            List of validated OpenAI response events

        Raises:
            ValidationError: If structured output validation fails
        """
        # Let parent handle ALL event mapping (MCP, tools, reasoning, text)
        openai_events = await self.map_event(event)

        # Check if this is a PartDeltaEvent with ToolCallPartDelta (potential structured output)
        if isinstance(event, PartDeltaEvent) and isinstance(event.delta, ToolCallPartDelta):
            output_index = event.index

            # Get state for this part
            if output_index in self.parts_state:
                state = self.parts_state[output_index]

                # Only validate if this is structured output (final_result tool)
                if state.is_final_result_tool and event.delta.args_delta:
                    logger.debug(f"Validating structured output delta: {event.delta.args_delta[:100]}...")

                    # Extract JSON content from args_delta
                    json_chunk = self._extract_json_from_tool_delta(event.delta.args_delta)

                    if json_chunk:
                        # Create a simple message object that validator expects
                        # Validator expects message.parts[0].content to contain JSON
                        from types import SimpleNamespace

                        validator_message = SimpleNamespace()
                        part = SimpleNamespace()
                        # Use accumulated args (full JSON so far) for validation
                        part.content = state.accumulated_args
                        validator_message.parts = [part]

                        # Process through validator
                        try:
                            async for validation_result in self.validator.process_streaming_message(validator_message):
                                if validation_result["valid"]:
                                    # Get validated data
                                    current_validated = validation_result.get("validated_data", {})

                                    # Update our validated fields
                                    self.validated_fields.update(current_validated)

                                    logger.debug(f"Validated fields: {list(current_validated.keys())}")
                                # If not valid, validator will raise ValidationError

                        except (ValueError, ValidationError) as e:
                            # Capture validation state before re-raising
                            self.validated_fields = self.validator.validated_data.copy()
                            self.failed_fields = {
                                k: v
                                for k, v in self.validator.attempted_data.items()
                                if k not in self.validator.validated_data
                            }
                            self.validation_error = str(e)
                            logger.error(f"Validation failed: {str(e)}")
                            logger.debug(f"Validated fields: {list(self.validated_fields.keys())}")
                            logger.debug(f"Failed fields: {list(self.failed_fields.keys())}")
                            # Re-raise to trigger retry
                            raise

        return openai_events

    def _compute_field_delta(self, current_validated: Dict[str, Any]) -> Dict[str, Any]:
        """Compute fields that are new or changed since last send.

        Args:
            current_validated: Currently validated fields from validator

        Returns:
            Dict containing only new/changed fields
        """
        delta = {}

        for field_name, field_value in current_validated.items():
            # Include if field is new or value changed
            if field_name not in self.last_sent_fields or self.last_sent_fields[field_name] != field_value:
                delta[field_name] = field_value

        return delta

    def _extract_json_from_tool_delta(self, args_delta: str) -> Optional[str]:
        """Extract JSON content from tool call args delta.

        Args:
            args_delta: The JSON delta from ToolCallPartDelta.args_delta

        Returns:
            Extracted JSON string or None if not applicable
        """
        # The args_delta is already JSON string representing the structured output
        # For final_result tool, it contains the incremental JSON content
        return args_delta if args_delta else None

    def format_output_text_delta(self, cumulative_text: str) -> Optional[str]:
        """Emit response.output_text.delta - incremental text chunk.

        Args:
            cumulative_text: The cumulative text (contains all text from start, not just the delta)

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
                "item_id": self.text_item_id,
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
                "item_id": self.text_item_id,
                "output_index": 0,
                "content_index": 0,
                "delta": cumulative_text,
                "logprobs": [],
            }
            return self._format_sse("response.output_text.delta", event_data)

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
                "id": self.text_item_id,
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
            "item_id": self.text_item_id,
            "output_index": 0,
            "content_index": 0,
            "part": {"type": "output_text", "annotations": [], "logprobs": [], "text": ""},
        }
        return self._format_sse("response.content_part.added", event_data)

    def format_output_text_done(self) -> str:
        """Emit response.output_text.done - text content finalized.

        Returns:
            SSE-formatted response.output_text.done event
        """
        event_data = {
            "type": "response.output_text.done",
            "sequence_number": self._next_sequence(),
            "item_id": self.text_item_id,
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
            "item_id": self.text_item_id,
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
                "id": self.text_item_id,
                "type": "message",
                "status": "completed",
                "content": [{"type": "output_text", "annotations": [], "logprobs": [], "text": self.accumulated_text}],
                "role": "assistant",
            },
        }
        return self._format_sse("response.output_item.done", event_data)

    def reset_validation_state(self):
        """Reset validation state for a new attempt."""
        self.validated_fields = {}
        self.failed_fields = {}
        self.validation_error = None
        self.last_sent_fields = {}
        self.validator.reset()

    def reset_for_retry(self):
        """Reset formatter state for retry attempt.

        This resets the formatter's internal state (parts, sequences, etc.)
        while preserving validation context for the retry prompt.

        NOTE: sequence_number is NOT reset - it continues monotonically increasing
        across retry attempts to ensure proper event ordering on client side.
        """
        # Reset parent formatter state
        self.parts_state.clear()
        # DON'T reset sequence_number - keep it monotonically increasing across retries
        self.accumulated_text = ""
        self.accumulated_thinking = []
        self.accumulated_reasoning = ""
        self.reasoning_started = False
        self.mcp_tools_emitted = False

        # Reset validator but preserve validation fields for retry prompt
        self.validator.reset()
        self.last_sent_fields = {}
