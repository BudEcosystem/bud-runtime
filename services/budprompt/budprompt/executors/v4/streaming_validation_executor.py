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
from pydantic import ValidationError
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage, ModelResponse, ThinkingPart, ToolCallPart
from pydantic_ai.output import NativeOutput
from pydantic_ai.settings import ModelSettings

from budprompt.shared.providers import BudServeProvider

from ...prompt.schemas import Message
from ...prompt.schemas import ModelSettings as ModelSettingsSchema
from .openai_streaming_formatter_v3 import OpenAIStreamingFormatter_V3
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
        deployment_name: str,
        model_settings: Optional[Dict[str, Any]],
        validation_prompt: Dict[str, Dict[str, Dict[str, str]]],
        retry_limit: int = 3,
        messages: Optional[List[Message]] = None,
        message_history: Optional[List[ModelMessage]] = None,
        api_key: Optional[str] = None,
    ):
        """Initialize the streaming validation executor.

        Args:
            output_type: Output type (NativeOutput wrapper or raw Pydantic model with field validators)
            prompt: Original user prompt
            deployment_name: Model deployment name
            model_settings: Model configuration dict
            validation_prompt: Nested dict with validation rules {ModelName: {field: {prompt: "..."}}}
            retry_limit: Maximum retry attempts
            messages: Original Message objects for formatter context (consistency with _run_agent_stream)
            message_history: ModelMessage list for agent conversation history
            api_key: Optional API key for authorization
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
        self.deployment_name = deployment_name
        self.validation_prompt = validation_prompt
        self.retry_limit = retry_limit
        self.messages = messages or []
        self.message_history = message_history or []
        self.api_key = api_key

        # Convert model_settings dict to ModelSettings object
        if model_settings:
            self.model_settings = ModelSettingsSchema(**model_settings)
        else:
            self.model_settings = ModelSettingsSchema()

        # Initialize OpenAI streaming formatter
        self.formatter = OpenAIStreamingFormatter_V3(
            deployment_name=deployment_name,
            model_settings=self.model_settings,
            messages=self.messages,  # Pass messages for consistency with _run_agent_stream
        )

        # Extract field validators
        self.field_validators = extract_field_validators(self.output_model)

        # Track attempts and errors
        self.validation_errors: List[str] = []
        self.last_attempted_data: Optional[Dict] = None
        self.final_usage: Optional[Any] = None

        # Track validation state for retry prompt
        self.validated_fields: Dict[str, Any] = {}  # Fields that passed validation
        self.failed_fields: Dict[str, Any] = {}  # Fields that failed validation

        # Track what we've sent to client for delta computation
        self.last_sent_fields: Dict[str, Any] = {}

        # Create provider
        self.provider = BudServeProvider(api_key=api_key)

        # Get model instance
        settings = ModelSettings(**model_settings) if model_settings else ModelSettings(temperature=0.1)

        self.model = self.provider.get_model(model_name=deployment_name, settings=settings)

    async def stream(self) -> AsyncGenerator[str, None]:
        """Execute streaming with validation and retry.

        Yields:
            OpenAI-formatted SSE event strings
        """
        # Emit pre-events (ONCE, before any attempts)
        yield self.formatter.format_response_created()
        yield self.formatter.format_response_in_progress()
        yield self.formatter.format_output_item_added()
        yield self.formatter.format_content_part_added()

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
                    # Emit final events
                    if self.formatter.reasoning_started:
                        yield self.formatter.format_reasoning_summary_text_done()
                        yield self.formatter.format_reasoning_summary_part_done()

                    yield self.formatter.format_output_text_done()
                    yield self.formatter.format_content_part_done()
                    yield self.formatter.format_output_item_done()
                    yield self.formatter.format_response_completed(self.final_usage)
                    return

            except ValidationError as e:
                # Validation failed
                self.validation_errors.append(str(e))
                logger.debug(f"Attempt {attempt + 1} validation failed: {str(e)}")

                # If not last attempt, retry
                if attempt < self.retry_limit - 1:
                    # Reset formatter text accumulation for retry
                    self.formatter.accumulated_text = ""
                    self.formatter.accumulated_reasoning = ""
                    # Don't reset last_sent_fields - keep delta tracking across retries
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
                    self.formatter.accumulated_text = ""
                    self.formatter.accumulated_reasoning = ""
                    # Don't reset last_sent_fields - keep delta tracking across retries
                    # Note: Don't reset validated_fields/failed_fields - they're used in retry prompt
                    continue
                else:
                    break

        # If we reach here, all attempts failed
        error_message = f"Validation failed after {self.retry_limit} attempts"
        if self.validation_errors:
            error_message += f": {self.validation_errors[-1]}"

        yield self.formatter.format_response_failed(error_message=error_message, error_code="validation_error")

    async def _attempt_stream(self, attempt_number: int) -> AsyncGenerator:
        """Attempt streaming with validation.

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

        # Create agent for this attempt
        agent = Agent(
            model=self.model,
            output_type=self.output_type,  # Use the stored output_type (could be NativeOutput or raw)
            system_prompt="You are a helpful assistant that generates valid structured data.",
            retries=0,  # We handle retries ourselves
        )

        # Create validator for this attempt
        validator = StreamingJSONValidator(self.output_model, self.field_validators)

        # Stream with validation
        async with agent.run_stream(user_prompt=current_prompt, message_history=self.message_history) as result:
            async for message, is_last in result.stream_structured(debounce_by=0.01):
                if not isinstance(message, ModelResponse):
                    continue

                # Update model name if available
                if message.model_name:
                    self.formatter.update_model_name(message.model_name)

                # For non-final chunks: validate and stream if valid
                if not is_last:
                    # Validate incrementally - capture state on failure
                    try:
                        async for validation_result in validator.process_streaming_message(message):
                            if validation_result["valid"]:
                                # Get current validated data
                                current_validated = validation_result.get("validated_data", {})

                                # Compute delta (only changed fields)
                                field_delta = self._compute_field_delta(current_validated)

                                if field_delta:
                                    # Convert delta to JSON string
                                    delta_json = json.dumps(field_delta, separators=(",", ":"))

                                    # Emit as text delta
                                    delta_event = self.formatter.format_output_text_delta(delta_json)
                                    if delta_event:
                                        yield delta_event

                                    # Update what we've sent
                                    self.last_sent_fields.update(field_delta)

                                # Handle reasoning/thinking parts
                                for part in message.parts:
                                    if isinstance(part, ThinkingPart) and part.content:
                                        # Handle reasoning
                                        if not self.formatter.reasoning_started:
                                            yield self.formatter.format_reasoning_summary_part_added()
                                            self.formatter.reasoning_started = True

                                        delta_event = self.formatter.format_reasoning_summary_text_delta(part.content)
                                        if delta_event:
                                            yield delta_event

                                        self.formatter.add_thinking_content(part.content)

                                    elif isinstance(part, ToolCallPart):
                                        logger.debug(f"Tool call: {part.tool_name}")
                            # If not valid, ValidationError will be raised by process_streaming_message
                    except (ValueError, ValidationError):
                        # Capture validation state before re-raising
                        self.validated_fields = validator.validated_data.copy()
                        self.failed_fields = {
                            k: v for k, v in validator.attempted_data.items() if k not in validator.validated_data
                        }
                        raise

                else:
                    # Final chunk - validate completely
                    validated_result = await result.validate_structured_output(message, allow_partial=False)

                    # Validation passed - merge previously validated fields to preserve them
                    # This ensures LLM doesn't change already-validated fields during retry
                    if hasattr(validated_result, "model_dump"):
                        final_validated_data = validated_result.model_dump()
                    else:
                        final_validated_data = validated_result if isinstance(validated_result, dict) else {}

                    # Merge validated fields from previous attempts (overwrite any LLM changes)
                    if self.validated_fields:
                        final_validated_data = {**final_validated_data, **self.validated_fields}

                    # Compute delta (only new or changed fields since last send)
                    final_delta = self._compute_field_delta(final_validated_data)

                    if final_delta:
                        # Convert delta to JSON string
                        delta_json = json.dumps(final_delta, separators=(",", ":"))

                        # Emit as text delta
                        delta_event = self.formatter.format_output_text_delta(delta_json)
                        if delta_event:
                            yield delta_event

                        # Update what we've sent
                        self.last_sent_fields.update(final_delta)

                    # Set accumulated_text to complete final JSON for done events
                    complete_json = json.dumps(final_validated_data, separators=(",", ":"))
                    self.formatter.accumulated_text = complete_json

                    # Handle reasoning/thinking parts
                    for part in message.parts:
                        if isinstance(part, ThinkingPart) and part.content:
                            # Handle any final reasoning content
                            if not self.formatter.reasoning_started:
                                yield self.formatter.format_reasoning_summary_part_added()
                                self.formatter.reasoning_started = True

                            delta_event = self.formatter.format_reasoning_summary_text_delta(part.content)
                            if delta_event:
                                yield delta_event

                            self.formatter.add_thinking_content(part.content)

                        elif isinstance(part, ToolCallPart):
                            logger.debug(f"Tool call: {part.tool_name}")

                    # Store attempted data for retry context
                    # Use the merged final_validated_data (with preserved fields) not raw validated_result
                    self.last_attempted_data = final_validated_data
                    # All fields passed validation on success
                    self.validated_fields = final_validated_data
                    self.failed_fields = {}

                    # Capture usage
                    if message.usage:
                        self.final_usage = message.usage

                    # Success! Signal completion
                    yield {"success": True}
                    return

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
