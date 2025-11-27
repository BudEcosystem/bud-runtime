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

"""Clean streaming validation executor with OpenAI formatting and simple retry logic."""

import json
from typing import Any, AsyncGenerator, Dict, List, Optional

from budmicroframe.commons import logging
from openai.types.responses import (
    ResponseCompletedEvent,
    ResponseCreatedEvent,
    ResponseFailedEvent,
    ResponseInProgressEvent,
)
from pydantic import ValidationError
from pydantic_ai import Agent
from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_ai.messages import (
    ModelMessage,
    PartDeltaEvent,
    PartStartEvent,
    TextPartDelta,
    ToolCallPart,
    ToolCallPartDelta,
)
from pydantic_ai.output import NativeOutput
from pydantic_ai.run import AgentRunResultEvent

from ...prompt.schemas import MCPToolConfig, Message
from ...prompt.schemas import ModelSettings as ModelSettingsSchema
from .openai_streaming_validation_formatter_v4 import OpenAIStreamingValidationFormatter_V4
from .streaming_json_validator import StreamingJSONValidator, extract_field_validators


logger = logging.get_logger(__name__)


class StreamingValidationExecutor:
    """Execute streaming with validation using OpenAI format and simple retry logic.

    This class provides a cleaner alternative to execute_streaming_validation with:
    - Simple for-loop retry instead of recursion
    - Single universal retry prompt instead of 3 different templates
    - OpenAI formatting integrated from the start
    - Better separation of concerns
    """

    def __init__(
        self,
        output_type: Any,
        prompt: str,
        validation_prompt: Dict[str, Dict[str, Dict[str, str]]],
        messages: Optional[List[Message]] = None,
        message_history: Optional[List[ModelMessage]] = None,
        api_key: Optional[str] = None,
        agent_kwargs: Optional[Dict[str, Any]] = None,
        deployment_name: str = "unknown",
        model_settings: Optional[ModelSettingsSchema] = None,
        tools: Optional[List[MCPToolConfig]] = None,
        output_schema: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None,
    ):
        """Initialize the streaming validation executor.

        Args:
            output_type: Output type (NativeOutput wrapper or raw Pydantic model with field validators)
            prompt: Original user prompt
            validation_prompt: Nested dict with validation rules {ModelName: {field: {prompt: "..."}}}
            messages: Original Message objects for formatter context
            message_history: ModelMessage list for agent conversation history
            api_key: Optional API key for authorization
            agent_kwargs: Agent configuration dict from _create_agent()
            deployment_name: Model deployment name for formatter
            model_settings: Model configuration settings for formatter
            tools: Optional list of tool configurations (MCP, etc.)
            output_schema: Optional JSON schema for structured output
        """
        # Store the full output_type for agent creation
        self.output_type = output_type

        # Extract Pydantic model from NativeOutput wrapper if needed
        if isinstance(output_type, NativeOutput):
            # It's wrapped in NativeOutput
            self.output_model = output_type.outputs
        else:
            # It's raw Pydantic model (or ToolOutput, etc.)
            self.output_model = output_type

        self.original_prompt = prompt
        self.validation_prompt = validation_prompt
        self.messages = messages or []
        self.system_prompt = system_prompt
        self.message_history = message_history or []
        self.api_key = api_key

        # Extract retry count BEFORE popping (determine external loop count)
        configured_retries = agent_kwargs.get("retries", 0)

        # Set external loop count based on configured retries
        if configured_retries == 0:
            self.retry_limit = 1  # Single attempt when agent has no retries
        else:
            self.retry_limit = configured_retries  # Use agent's retry count for external loop
        logger.debug("Set retry_limit to %s for streaming validation executor", self.retry_limit)

        # Pop retries from the argument dict (mutate in place)
        if agent_kwargs:
            agent_kwargs.pop("retries", None)

        # Save the mutated dict
        self.agent_kwargs = agent_kwargs

        # Extract field validators
        self.field_validators = extract_field_validators(self.output_model)

        # Create streaming JSON validator
        self.validator = StreamingJSONValidator(self.output_model, self.field_validators)

        # Initialize V4 validation formatter with full context
        self.formatter = OpenAIStreamingValidationFormatter_V4(
            validator=self.validator,
            deployment_name=deployment_name,
            model_settings=model_settings or ModelSettingsSchema(),
            messages=self.messages,
            tools=tools,
            output_schema=output_schema,
        )

        # Track attempts and errors
        self.validation_errors: List[str] = []
        self.last_attempted_data: Optional[Dict] = None
        self.final_usage: Optional[Any] = None
        self.final_result: Optional[Any] = None  # Track AgentRunResult for output building

        # Track validation state for retry prompt
        self.validated_fields: Dict[str, Any] = {}  # Fields that passed validation
        self.failed_fields: Dict[str, Any] = {}  # Fields that failed validation

        # Track what we've sent to client for delta computation
        self.last_sent_fields: Dict[str, Any] = {}

        # Track whether message item lifecycle has been emitted
        self.message_item_started = False

    async def stream(self) -> AsyncGenerator[str, None]:
        """Execute streaming with validation and retry.

        Yields:
            OpenAI-formatted SSE event strings
        """
        # Emit pre-events (ONCE, before any attempts)
        # Build instructions from messages (for response.created/in_progress events)
        instructions = self.formatter.build_instructions(self.messages, self.system_prompt)

        # EVENT 1: response.created (MUST be first event)
        yield self.formatter.format_sse_from_event(
            ResponseCreatedEvent(
                type="response.created",
                sequence_number=self.formatter._next_sequence(),
                response=self.formatter.build_response_object(
                    status="in_progress",
                    instructions=instructions,
                ),
            )
        )

        # EVENT 2: response.in_progress (MUST be second event)
        yield self.formatter.format_sse_from_event(
            ResponseInProgressEvent(
                type="response.in_progress",
                sequence_number=self.formatter._next_sequence(),
                response=self.formatter.build_response_object(
                    status="in_progress",
                    instructions=instructions,
                ),
            )
        )

        # EVENTS 3+: MCP tool lists (if any MCP tools configured)
        if self.formatter.tools_config:
            mcp_events = await self.formatter.emit_mcp_tool_list_events()
            for event in mcp_events:
                yield self.formatter.format_sse_from_event(event)

        # Note: Message item lifecycle events (output_item.added, content_part.added)
        # will be emitted on-demand before field deltas in AgentRunResultEvent handler

        # Try streaming up to retry_limit times
        for attempt in range(self.retry_limit):
            try:
                logger.debug(f"Streaming validation attempt {attempt + 1}/{self.retry_limit}")

                # Attempt streaming with validation
                success = False
                async for event in self._attempt_stream(attempt):
                    if isinstance(event, str):
                        # OpenAI event - yield it
                        yield event
                    elif isinstance(event, dict) and event.get("success"):
                        # Streaming completed successfully
                        success = True
                        break

                if success:
                    # === MESSAGE ITEM FINALIZATION EVENTS ===
                    # Incremental deltas were already emitted during streaming in _attempt_stream()
                    # Now emit the done events to close out the message item

                    # Emit response.output_text.done
                    yield self.formatter.format_output_text_done()

                    # Emit response.content_part.done
                    yield self.formatter.format_content_part_done()

                    # Emit response.output_item.done for message
                    yield self.formatter.format_output_item_done()

                    # Build output_items array manually for validation mode
                    # We only include our upfront-created message item, not tool results
                    output_items = []
                    message_item = {
                        "id": self.formatter.text_item_id,
                        "type": "message",
                        "status": "completed",
                        "content": [
                            {
                                "type": "output_text",
                                "annotations": [],
                                "logprobs": [],
                                "text": self.formatter.accumulated_text,
                            }
                        ],
                        "role": "assistant",
                    }
                    output_items.append(message_item)

                    # Emit final response.completed event with instructions and output
                    yield self.formatter.format_sse_from_event(
                        ResponseCompletedEvent(
                            type="response.completed",
                            sequence_number=self.formatter._next_sequence(),
                            response=self.formatter.build_response_object(
                                status="completed",
                                instructions=instructions,
                                output_items=output_items,
                                usage=self.final_usage,
                            ),
                        )
                    )
                    return

            except (ValueError, ValidationError, UnexpectedModelBehavior) as e:
                # Validation failed (ValueError from field validators, ValidationError from Pydantic,
                # or UnexpectedModelBehavior from pydantic-ai when retries=0)
                self.validation_errors.append(str(e))
                logger.debug(f"Attempt {attempt + 1} validation failed: {str(e)}")

                # If not last attempt, retry
                if attempt < self.retry_limit - 1:
                    # Reset formatter state for retry
                    self.formatter.reset_for_retry()
                    # Reset flag to allow lifecycle events on retry
                    self.message_item_started = False
                    # Note: Don't reset validated_fields/failed_fields - they're used in retry prompt
                    continue
                else:
                    # Max retries exhausted
                    logger.error(f"Validation failed after {self.retry_limit} attempts")
                    break

            except Exception as e:
                # Unexpected error
                logger.error(f"Streaming error on attempt {attempt + 1}: {str(e)}")
                self.validation_errors.append(f"Unexpected error: {str(e)}")

                # If not last attempt, retry
                if attempt < self.retry_limit - 1:
                    self.formatter.reset_for_retry()
                    # Reset flag to allow lifecycle events on retry
                    self.message_item_started = False
                    # Note: Don't reset validated_fields/failed_fields - they're used in retry prompt
                    continue
                else:
                    break

        # If we reach here, all attempts failed
        error_message = f"Validation failed after {self.retry_limit} attempts"
        if self.validation_errors:
            error_message += f": {self.validation_errors[-1]}"

        # Emit response.failed event
        yield self.formatter.format_sse_from_event(
            ResponseFailedEvent(
                type="response.failed",
                sequence_number=self.formatter._next_sequence(),
                response=self.formatter.build_response_object(
                    status="failed",
                    instructions=None,
                    output_items=[],
                    usage=self.final_usage,
                    error={"code": "server_error", "message": error_message},
                ),
            )
        )

    async def _attempt_stream(self, attempt_number: int) -> AsyncGenerator:
        """Attempt streaming with validation using backup algorithm.

        This replicates the exact validation algorithm from backup_streaming_validation_executor.py
        but uses run_stream_events() API and V4 OpenAI formatter.

        Args:
            attempt_number: Current attempt (0-indexed)

        Yields:
            OpenAI event strings or success dict

        Raises:
            ValidationError: If validation fails
            Exception: On other errors
        """
        # Build prompt for this attempt
        current_prompt = self._build_prompt(attempt_number)

        # Create agent for this attempt using agent_kwargs
        # Note: We always override retries=0 because we handle retries externally via for-loop
        agent = Agent(**self.agent_kwargs, retries=0)

        # Create validator for this attempt
        validator = StreamingJSONValidator(self.output_model, self.field_validators)

        # Stream events using run_stream_events() for full MCP support
        async for event in agent.run_stream_events(user_prompt=current_prompt, message_history=self.message_history):
            logger.debug(
                f"Received pydantic-ai event: {type(event).__name__}, is PartDeltaEvent: {isinstance(event, PartDeltaEvent)}"
            )

            # ===== FINAL RESULT EVENT (equivalent to is_last=True in backup) =====
            if isinstance(event, AgentRunResultEvent):
                final_result = event.result
                self.final_result = final_result
                logger.debug("Received final AgentRunResultEvent - validating completely")

                # Final chunk - validate completely (same as backup lines 337-400)
                try:
                    if final_result:
                        # Extract the final validated data
                        # For structured output, the data is in final_result.output (NativeOutput or direct value)
                        if hasattr(final_result, "output") and final_result.output is not None:
                            # Extract from output attribute (pydantic-ai's AgentRunResult.output)
                            if hasattr(final_result.output, "model_dump"):
                                final_validated_data = final_result.output.model_dump()
                            elif isinstance(final_result.output, dict):
                                final_validated_data = final_result.output
                            else:
                                # Output is the raw Pydantic model instance
                                final_validated_data = final_result.output
                                if hasattr(final_validated_data, "model_dump"):
                                    final_validated_data = final_validated_data.model_dump()
                        elif hasattr(final_result, "model_dump"):
                            final_validated_data = final_result.model_dump()
                        else:
                            final_validated_data = final_result if isinstance(final_result, dict) else {}

                        logger.debug(f"Final validated data: {final_validated_data}")

                        # Merge validated fields from previous attempts (preserve validated fields)
                        # This ensures LLM doesn't change already-validated fields during retry
                        if self.validated_fields:
                            final_validated_data = {**final_validated_data, **self.validated_fields}

                        # EMIT lifecycle events ONCE before first field delta
                        # This ensures they appear immediately after MCP tools and before validated output
                        if not self.message_item_started:
                            logger.debug("Emitting message item lifecycle events before field deltas")

                            # Emit lifecycle events with proper sequences
                            yield self.formatter.format_output_item_added()
                            yield self.formatter.format_content_part_added()

                            self.message_item_started = True

                        logger.debug(f"Emitting field-by-field deltas for {len(final_validated_data)} fields")

                        # Emit field-by-field validated deltas (for MCP + structured output)
                        # This provides incremental streaming even though tool already completed
                        for field_name, field_value in final_validated_data.items():
                            logger.debug(f"Processing field: {field_name} = {field_value}")
                            # Skip if already sent (for retry scenarios)
                            if (
                                field_name in self.last_sent_fields
                                and self.last_sent_fields[field_name] == field_value
                            ):
                                continue

                            # Emit single field as delta
                            field_delta = {field_name: field_value}
                            delta_json = json.dumps(field_delta, separators=(",", ":"))

                            # Emit as text delta using V4 formatter
                            delta_event = self.formatter.format_output_text_delta(delta_json)
                            if delta_event:
                                yield delta_event

                            # Update what we've sent
                            self.last_sent_fields[field_name] = field_value

                        # Set accumulated_text to complete final JSON for done events
                        complete_json = json.dumps(final_validated_data, separators=(",", ":"))
                        self.formatter.accumulated_text = complete_json

                        # Store for retry context
                        self.last_attempted_data = final_validated_data
                        # All fields passed validation on success
                        self.validated_fields = final_validated_data
                        self.failed_fields = {}

                        # Capture usage
                        if final_result.usage():
                            usage_info = final_result.usage()
                            details = getattr(usage_info, "details", {})
                            reasoning_tokens = details.get("reasoning_tokens", 0) if isinstance(details, dict) else 0
                            self.final_usage = {
                                "input_tokens": getattr(usage_info, "request_tokens", 0),
                                "input_tokens_details": {"cached_tokens": 0},
                                "output_tokens": getattr(usage_info, "response_tokens", 0),
                                "output_tokens_details": {"reasoning_tokens": reasoning_tokens},
                                "total_tokens": getattr(usage_info, "total_tokens", 0),
                            }

                        # Success! Signal completion
                        yield {"success": True}
                        return

                except (ValueError, ValidationError) as e:
                    # Validation failed - capture state before re-raising
                    self.validated_fields = validator.validated_data.copy()
                    self.failed_fields = {
                        k: v for k, v in validator.attempted_data.items() if k not in validator.validated_data
                    }
                    self.validation_error = str(e)
                    logger.error(f"Final validation failed: {str(e)}")
                    raise

            # ===== STREAMING EVENTS (equivalent to is_last=False in backup) =====

            # Handle PartStartEvent to populate formatter state (required for validation)
            if isinstance(event, PartStartEvent):
                # Let formatter process to populate parts_state
                # Don't assign sequences initially - we need to check if we should suppress
                openai_events = await self.formatter.map_event(event, assign_sequence=False)

                # Check if this is a ToolCallPart (potential MCP tool)
                if isinstance(event.part, ToolCallPart):
                    output_index = event.index
                    if output_index in self.formatter.parts_state:
                        state = self.formatter.parts_state[output_index]

                        # Only suppress if this is final_result tool (structured output)
                        if state.is_final_result_tool:
                            logger.debug("Suppressing final_result tool lifecycle events")
                            # Suppress final_result tool lifecycle - we'll emit validated output later
                            continue

                        # Regular MCP tool - need to emit lifecycle events
                        # Reassign sequences and yield the events
                        logger.debug(f"Emitting MCP tool lifecycle events for {state.tool_name}")
                        events_with_sequences = []
                        for openai_event in openai_events:
                            event_dict = openai_event.model_dump()
                            event_dict["sequence_number"] = self.formatter._next_sequence()
                            events_with_sequences.append(type(openai_event)(**event_dict))

                        for event_with_seq in events_with_sequences:
                            yield self.formatter.format_sse_from_event(event_with_seq)

                        continue

                # TextPart or ThinkingPart - suppress, we'll emit validated deltas later
                continue

            # For structured output validation, intercept PartDeltaEvent with text content (JSON)
            if isinstance(event, PartDeltaEvent) and isinstance(event.delta, TextPartDelta):
                output_index = event.index
                logger.debug(
                    f"TextPartDelta: index={output_index}, content_delta={event.delta.content_delta[:50] if event.delta.content_delta else None}"
                )

                # CRITICAL: Let formatter accumulate the delta WITHOUT assigning sequences
                # This populates state.accumulated_content with the latest JSON
                openai_events = await self.formatter.map_event(event, assign_sequence=False)

                # NOW get state and validate accumulated content
                if output_index in self.formatter.parts_state:
                    state = self.formatter.parts_state[output_index]

                    # Get accumulated content (JSON so far)
                    if hasattr(state, "accumulated_content") and state.accumulated_content:
                        logger.debug(f"Streaming: validating structured output: {state.accumulated_content[:100]}...")

                        # Create a simple message object that validator expects
                        from types import SimpleNamespace

                        validator_message = SimpleNamespace()
                        part = SimpleNamespace()
                        # Use accumulated content (full JSON so far) for validation
                        part.content = state.accumulated_content
                        validator_message.parts = [part]

                        # Validate incrementally - capture state on failure (same as backup lines 290-334)
                        try:
                            async for validation_result in validator.process_streaming_message(validator_message):
                                if validation_result["valid"]:
                                    # Get current validated data
                                    current_validated = validation_result.get("validated_data", {})

                                    # Compute delta (only changed fields)
                                    field_delta = self._compute_field_delta(current_validated)

                                    if field_delta:
                                        # EMIT lifecycle events ONCE before first field delta
                                        if not self.message_item_started:
                                            logger.debug("Emitting message item lifecycle events before field deltas")
                                            yield self.formatter.format_output_item_added()
                                            yield self.formatter.format_content_part_added()
                                            self.message_item_started = True

                                        # Convert delta to JSON string
                                        delta_json = json.dumps(field_delta, separators=(",", ":"))

                                        # Emit as text delta using V4 formatter
                                        delta_event = self.formatter.format_output_text_delta(delta_json)
                                        if delta_event:
                                            yield delta_event

                                        # Update what we've sent
                                        self.last_sent_fields.update(field_delta)

                                    # Update our validated fields
                                    self.validated_fields.update(current_validated)

                                    logger.debug(f"Streaming: validated fields: {list(current_validated.keys())}")

                        except (ValueError, ValidationError) as e:
                            # Capture validation state before re-raising (same as backup lines 328-334)
                            self.validated_fields = validator.validated_data.copy()
                            self.failed_fields = {
                                k: v for k, v in validator.attempted_data.items() if k not in validator.validated_data
                            }
                            self.validation_error = str(e)
                            logger.error(f"Streaming validation failed: {str(e)}")
                            logger.debug(f"Validated fields: {list(self.validated_fields.keys())}")
                            logger.debug(f"Failed fields: {list(self.failed_fields.keys())}")
                            # Re-raise to trigger retry
                            raise

                        # Always skip formatter events - we only emit validated deltas or nothing
                        # During validation, we buffer until fields are complete and valid
                        continue

            # Suppress final_result tool streaming (structured output in MCP context)
            # We'll validate and emit field deltas after tool completes in AgentRunResultEvent
            if isinstance(event, PartDeltaEvent) and isinstance(event.delta, ToolCallPartDelta):
                output_index = event.index
                logger.debug(
                    f"ToolCallPartDelta: index={output_index}, tool_name={event.delta.tool_name if hasattr(event.delta, 'tool_name') else 'unknown'}"
                )

                # Let formatter accumulate the delta WITHOUT sequences (needed for state tracking)
                openai_events = await self.formatter.map_event(event, assign_sequence=False)

                # Check if this is final_result tool (structured output)
                if output_index in self.formatter.parts_state:
                    state = self.formatter.parts_state[output_index]

                    if state.is_final_result_tool:
                        logger.debug(
                            "Suppressing final_result tool streaming - will validate and emit after completion"
                        )
                        # Suppress - don't emit mcp_call_arguments.delta events
                        # We'll validate and emit field deltas in AgentRunResultEvent handler
                        continue

                # Not final_result tool - need to assign sequences now and emit
                # Reassign sequences to the events we just generated
                events_with_sequences = []
                for openai_event in openai_events:
                    # Recreate event with proper sequence number
                    event_dict = openai_event.model_dump()
                    event_dict["sequence_number"] = self.formatter._next_sequence()
                    events_with_sequences.append(type(openai_event)(**event_dict))

                # Emit events with proper sequences
                for event_with_seq in events_with_sequences:
                    yield self.formatter.format_sse_from_event(event_with_seq)
                continue

            # For all other events (reasoning, text, etc), pass through V4 formatter
            openai_events = await self.formatter.map_event(event)

            # Emit each OpenAI event
            for openai_event in openai_events:
                yield self.formatter.format_sse_from_event(openai_event)

    def _build_prompt(self, attempt: int) -> str:
        """Build prompt for this attempt.

        Args:
            attempt: Attempt number (0 = first, 1+ = retries)

        Returns:
            Prompt string (original or enhanced retry prompt)
        """
        if attempt == 0:
            # First attempt - use original prompt
            return self.original_prompt

        # Retry attempt - build enhanced prompt with error context
        last_error = self.validation_errors[-1] if self.validation_errors else "Validation failed"
        model_name = self.output_model.__name__ if hasattr(self.output_model, "__name__") else "Model"
        validation_rules = self._format_validation_rules()

        # Format field status information
        fields_passed = json.dumps(self.validated_fields, indent=2) if self.validated_fields else "None"
        fields_failed = json.dumps(self.failed_fields, indent=2) if self.failed_fields else "None"

        # Improved retry prompt with explicit field status
        retry_prompt = f"""Your previous attempt failed validation. Fix only what's broken.

Fields that PASSED validation (keep these exactly):
{fields_passed}

Fields that FAILED validation (fix these):
{fields_failed}

Validation error:
{last_error}

Validation requirements:
{validation_rules}

Original request:
{self.original_prompt}

IMPORTANT: Keep the fields that passed validation exactly as they are. Only regenerate the fields that failed validation.
Generate the complete corrected {model_name} object with all fields."""

        return retry_prompt

    def _format_validation_rules(self) -> str:
        """Format all validation rules as readable string.

        Returns:
            Formatted validation rules string
        """
        model_name = self.output_model.__name__ if hasattr(self.output_model, "__name__") else "Model"

        if model_name not in self.validation_prompt:
            return "No specific validation rules"

        rules = []
        for field_name, field_validation in self.validation_prompt[model_name].items():
            if "prompt" in field_validation:
                rules.append(f"- {field_name}: {field_validation['prompt']}")

        return "\n".join(rules) if rules else "No specific validation rules"

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
