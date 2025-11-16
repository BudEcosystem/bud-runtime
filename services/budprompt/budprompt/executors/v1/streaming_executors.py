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

"""Streaming executors with validation and retry logic for prompt execution."""

import json
import re
from typing import Any, AsyncGenerator, Dict, List, Optional

from budmicroframe.commons import logging
from pydantic import ValidationError
from pydantic_ai import Agent
from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_ai.messages import ModelMessage
from pydantic_ai.output import NativeOutput
from pydantic_ai.settings import ModelSettings

from budprompt.shared.providers import BudServeProvider

from .streaming_json_validator import StreamingJSONValidator, extract_field_validators


logger = logging.get_logger(__name__)


async def execute_streaming_validation(
    enhanced_model: Any,  # The model with validators already added
    pydantic_schema: dict,
    prompt: str,
    validation_prompt: Dict[str, Dict[str, Dict[str, str]]],
    deployment_name: str,
    model_settings: Optional[Dict[str, Any]] = None,
    llm_retry_limit: int = 3,
    messages: Optional[List[ModelMessage]] = None,
    system_prompt_role: str = "system",
    api_key: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """Stream structured output with recursive retry mechanism using partial data.

    This function demonstrates:
    1. Dynamic validator generation from natural language
    2. Streaming partial results as they arrive
    3. Recursive retry with partial data continuation on validation failure
    4. Accumulating context for intelligent retry attempts

    Args:
        enhanced_model: The Pydantic model with validators already added (NativeOutput wrapper)
        pydantic_schema: JSON schema for the output structure
        prompt: User prompt for generation
        validation_prompt: Validation rules dict with model/field/prompt structure
        deployment_name: Model deployment name to use
        model_settings: Optional model settings
        llm_retry_limit: Maximum number of retries
        messages: Optional message history
        system_prompt_role: Role for system prompts
        api_key: Optional API key for authorization

    Yields:
        SSE-formatted string chunks with validation events
    """

    # Helper function to get specific field validation
    def get_field_validation_prompt(model_name: str, field_name: str) -> str:
        """Get validation prompt for a specific field."""
        # First try the specific model name
        if model_name in validation_prompt and field_name in validation_prompt[model_name]:
            return validation_prompt[model_name][field_name].get("prompt", "")

        # If not found, try to find in any model (for cases where model name isn't exact)
        # for model_fields in validation_prompt.values():
        #     if field_name in model_fields:
        #         return model_fields[field_name].get("prompt", "")

        return ""

    # Helper to format validation prompts for a specific model
    def format_all_validation_prompts(model_name: str) -> str:
        """Format validation prompts for a specific model."""
        prompts = []
        if model_name in validation_prompt:
            fields = validation_prompt[model_name]
            for field_name, field_validation in fields.items():
                if "prompt" in field_validation:
                    prompts.append(f"- {field_name}: {field_validation['prompt']}")
        return "\n".join(prompts) if prompts else f"No validation requirements for {model_name}"

    # Extract the actual model from NativeOutput wrapper if needed
    if hasattr(enhanced_model, "outputs"):
        # It's a NativeOutput wrapper, extract the actual model
        input_model_simple_with_validator = enhanced_model.outputs
    else:
        # It's already the model
        input_model_simple_with_validator = enhanced_model

    # Create provider with api_key (handles None internally)
    provider = BudServeProvider(api_key=api_key)

    # Prepare model settings
    model_kwargs = {}
    if model_settings:
        # Convert model settings to ModelSettings
        model_kwargs["settings"] = ModelSettings(**model_settings)
    else:
        # Use default settings with consistent temperature
        model_kwargs["settings"] = ModelSettings(temperature=0.1)

    model = provider.get_model(model_name=deployment_name, **model_kwargs)

    # Track if we've already sent a complete event
    complete_sent = False

    # Recursive retry function
    async def attempt_stream_with_retry(
        prompt: str,
        retry_count: int = 0,
        max_retries: int = llm_retry_limit,
        partial_data: dict = None,
        validation_errors: list = None,
        original_valid_partial: dict = None,
    ):
        """Recursively attempt streaming with retry on validation failure.

        Continues from partial data on retry.

        Args:
            prompt: The user prompt
            retry_count: Current retry attempt number
            max_retries: Maximum number of retries allowed
            partial_data: The last attempted data (may be invalid) for context
            validation_errors: List of validation errors accumulated
            original_valid_partial: The original valid partial data to preserve
        """
        nonlocal complete_sent

        if retry_count >= max_retries:
            # Max retries exhausted
            # Use original_valid_partial if available, otherwise partial_data
            final_data = original_valid_partial if original_valid_partial is not None else partial_data
            error_msg = {
                "type": "error",
                "message": f"Max retries ({max_retries}) exhausted",
                "final_partial_data": final_data,
                "all_errors": validation_errors,
            }
            yield f"data: {json.dumps(error_msg)}\n\n"
            if not complete_sent:
                yield f"data: {json.dumps({'type': 'complete', 'status': 'max_retries_exceeded'})}\n\n"
                complete_sent = True
            return

        # Build context-aware prompt if retrying
        if retry_count > 0 and partial_data:
            # Create continuation prompt with partial data and error context
            error_summary = validation_errors[-1] if validation_errors else "Validation failed"

            # Extract model name and schema requirements
            model_name = (
                input_model_simple_with_validator.__name__
                if hasattr(input_model_simple_with_validator, "__name__")
                else "Model"
            )
            schema = (
                input_model_simple_with_validator.model_json_schema()
                if hasattr(input_model_simple_with_validator, "model_json_schema")
                else {}
            )
            required_fields = schema.get("required", [])
            properties = schema.get("properties", {})

            # Build field descriptions
            field_descriptions = []
            for field, info in properties.items():
                field_type = info.get("type", "any")
                is_required = field in required_fields
                if "$ref" in info:
                    # Handle nested objects
                    ref_name = info["$ref"].split("/")[-1]
                    field_descriptions.append(f"- {field}: {ref_name} object (required: {is_required})")
                else:
                    field_descriptions.append(f"- {field}: {field_type} (required: {is_required})")

            fields_description = "\n".join(field_descriptions)

            # Check if this is a field validation failure
            if (
                "Field '" in error_summary
                and "' validation failed" in error_summary
                and isinstance(partial_data, dict)
            ):
                # Extract field name from error message
                field_match = re.search(r"Field '(\w+)' validation failed", error_summary)
                if field_match:
                    failed_field = field_match.group(1)
                    invalid_value = partial_data.get(failed_field, "unknown")

                    # Get the specific validation prompt for this field
                    field_validation_prompt = get_field_validation_prompt(model_name, failed_field)

                    enhanced_prompt = f"""The previously generated data failed validation.

Invalid data generated:
{json.dumps(partial_data, indent=2)}

SPECIFIC ISSUE: The {failed_field} field with value "{invalid_value}" does not satisfy the validation requirement.

Validation requirement for {failed_field}: {field_validation_prompt}

IMPORTANT: Generate a COMPLETE {model_name} object with ALL required fields:
{fields_description}

Original request: {prompt}

Requirements:
1. Ensure the {failed_field} field satisfies the specific requirement: "{field_validation_prompt}"
2. Include ALL required fields with actual, meaningful data
3. For array fields, populate with actual items (DO NOT leave arrays empty)
4. Follow the original request intent to create meaningful data

Generate the complete corrected object with all fields populated:"""
                else:
                    # Fallback if we can't extract the field name
                    enhanced_prompt = f"""The previously generated data failed validation.

Invalid data generated:
{json.dumps(partial_data, indent=2)}

Validation error: {error_summary}
Validation requirement: {format_all_validation_prompts(model_name)}

IMPORTANT: Generate a COMPLETE {model_name} object with ALL required fields:
{fields_description}

Original request: {prompt}

Requirements:
1. Ensure all validation requirements are satisfied
2. Include ALL required fields with actual, meaningful data
3. For array fields, populate with actual items (DO NOT leave arrays empty)
4. Follow the original request intent to create meaningful data

Generate the complete corrected object with all fields populated:"""
            else:
                # Extract model schema for generic handling
                model_name = (
                    input_model_simple_with_validator.__name__
                    if hasattr(input_model_simple_with_validator, "__name__")
                    else "Model"
                )
                schema = (
                    input_model_simple_with_validator.model_json_schema()
                    if hasattr(input_model_simple_with_validator, "model_json_schema")
                    else {}
                )
                required_fields_schema = set(schema.get("required", []))
                properties = schema.get("properties", {})

                # Analyze what fields are missing or need correction
                missing_fields = []
                if isinstance(partial_data, dict):
                    # Check for missing required fields based on actual schema
                    missing_fields = list(required_fields_schema - set(partial_data.keys()))

                    # Check nested objects for completeness
                    for field_name, field_value in partial_data.items():
                        if field_name in properties:
                            field_info = properties[field_name]
                            if "$ref" in field_info or (  # noqa: SIM102
                                field_info.get("type") == "object" and "properties" in field_info
                            ):
                                # This is a nested object
                                if isinstance(field_value, dict):
                                    # Get nested schema
                                    if "$ref" in field_info:
                                        # Would need to resolve $ref, simplified for now
                                        pass
                                    elif "properties" in field_info:
                                        nested_required = set(field_info.get("required", []))
                                        nested_missing = list(nested_required - set(field_value.keys()))
                                        if nested_missing:
                                            for nm in nested_missing:
                                                missing_fields.append(f"{field_name}.{nm}")

                # Build field descriptions for prompt
                field_descriptions = []
                for field, info in properties.items():
                    field_type = info.get("type", "any")
                    is_required = field in required_fields_schema
                    if "$ref" in info:
                        ref_name = info["$ref"].split("/")[-1]
                        field_descriptions.append(f"- {field}: {ref_name} object (required: {is_required})")
                    else:
                        field_descriptions.append(f"- {field}: {field_type} (required: {is_required})")

                fields_description = "\n".join(field_descriptions)

                # Build the enhanced prompt
                if missing_fields:
                    fields_str = ", ".join(missing_fields)
                    enhanced_prompt = f"""Complete the partially generated {model_name} data.

Current data:
{json.dumps(partial_data, indent=2)}

Missing fields that need to be added: {fields_str}

Validation requirement: {format_all_validation_prompts(model_name)}

IMPORTANT: Generate a COMPLETE {model_name} object with ALL required fields:
{fields_description}

Original request: {prompt}

Requirements:
1. Include the missing fields: {fields_str}
2. Ensure the validation requirement is satisfied
3. Include ALL required fields with actual, meaningful data
4. For array fields, populate with actual items (DO NOT leave arrays empty)
5. Follow the original request intent to create meaningful data

Generate the complete object with all fields populated:"""
                else:
                    # All fields present but validation failed - need correction
                    enhanced_prompt = f"""Correct the generated {model_name} data to meet validation requirements.

Current data:
{json.dumps(partial_data, indent=2)}

Validation error: {error_summary}

Validation requirement: {format_all_validation_prompts(model_name)}

IMPORTANT: Generate a CORRECTED {model_name} with ALL fields properly populated:
{fields_description}

Original request: {prompt}

Requirements:
1. Fix the fields that cause validation failure
2. Maintain ALL required fields with actual, meaningful data
3. For array fields, ensure they contain actual items (DO NOT make arrays empty)
4. Follow the original request intent

Generate the corrected object with all fields properly populated:"""
        else:
            enhanced_prompt = prompt

        # Create agent for this attempt
        agent = Agent(
            model=model,
            output_type=NativeOutput(input_model_simple_with_validator),
            system_prompt="You are a helpful assistant that generates valid structured data.",
            retries=0,  # Disable internal retries, we handle it ourselves
        )

        # Track partial data for this attempt
        latest_partial = {}  # noqa: F841
        last_valid_partial = partial_data or {}

        # Preserve the original valid partial data for final error reporting
        # If this is the first attempt, use partial_data as the original
        if original_valid_partial is None and partial_data:
            original_valid_partial = partial_data

        # Extract field validators for incremental validation
        field_validators = extract_field_validators(input_model_simple_with_validator)
        logger.debug(f"Extracted field validators: {list(field_validators.keys())}")

        # Create streaming validator
        stream_validator = StreamingJSONValidator(input_model_simple_with_validator, field_validators)

        try:
            # Prepare message history
            message_history = messages or []

            async with agent.run_stream(user_prompt=enhanced_prompt, message_history=message_history) as result:
                # Stream and validate incrementally
                async for message, is_last in result.stream_structured(debounce_by=0.01):
                    # For non-final chunks, use incremental validation
                    if not is_last:
                        try:
                            # Process through streaming validator
                            async for validation_result in stream_validator.process_streaming_message(message):
                                if validation_result["valid"]:
                                    # Only stream validated data
                                    last_valid_partial = validation_result.get("validated_data", {})

                                    # Stream validated partial data to client
                                    # Wrap in content field to match the expected schema structure
                                    stream_msg = {"type": "partial", "content": {"content": last_valid_partial}}
                                    yield f"data: {json.dumps(stream_msg)}\n\n"
                                else:
                                    # Field validation failed - this will trigger retry
                                    logger.debug(f"Field validation failed: {validation_result}")
                                    # The ValidationError is raised inside process_streaming_message

                        except (ValidationError, ValueError) as e:
                            # Early field validation failed - trigger retry immediately
                            validation_errors = validation_errors or []
                            validation_errors.append(str(e))

                            # Get the attempted data (including invalid fields) for context
                            attempted_data = {}
                            if hasattr(stream_validator, "attempted_data"):
                                attempted_data = dict(stream_validator.attempted_data)

                            logger.debug(f"Early validation failed on attempt {retry_count + 1}: {str(e)}")
                            logger.debug(f"Attempted data (including invalid): {attempted_data}")
                            logger.debug(f"Validated data so far: {stream_validator.validated_data}")

                            # Reset validator for retry
                            stream_validator.reset()

                            # Recursive retry with attempted data as context
                            # Preserve the first valid partial through retries
                            async for event in attempt_stream_with_retry(
                                prompt=prompt,
                                retry_count=retry_count + 1,
                                max_retries=max_retries,
                                partial_data=attempted_data,  # Pass attempted data for context
                                validation_errors=validation_errors,
                                original_valid_partial=original_valid_partial or last_valid_partial,
                            ):
                                yield event
                            return

                    else:
                        # Final chunk - validate before streaming
                        try:
                            # Validate the complete output
                            validated_result = await result.validate_structured_output(message, allow_partial=False)

                            # Convert to dict for streaming
                            if hasattr(validated_result, "model_dump"):
                                output_data = validated_result.model_dump()
                            else:
                                output_data = validated_result

                            # Stream final validated data
                            # Wrap in content field to match the expected schema structure
                            stream_msg = {"type": "final", "content": {"content": output_data}}
                            yield f"data: {json.dumps(stream_msg)}\n\n"

                            # Final validation passed!
                            if not complete_sent:
                                complete_msg = {
                                    "type": "complete",
                                    "status": "success",
                                    "retry_count": retry_count,
                                    # "validation_prompts": validation_prompt,
                                }
                                yield f"data: {json.dumps(complete_msg)}\n\n"
                                complete_sent = True
                            return  # Success, exit recursion

                        except ValidationError as e:
                            # Final validation failed - prepare for retry
                            validation_errors = validation_errors or []
                            validation_errors.append(str(e))

                            # Try to extract what was generated (invalid data)
                            invalid_data = {}
                            if isinstance(message, dict):
                                invalid_data = message
                            elif hasattr(message, "model_dump"):
                                invalid_data = message.model_dump()

                            # Log retry attempt internally (not sent to client)
                            logger.debug(f"Validation failed on attempt {retry_count + 1}: {str(e)}")
                            logger.debug(f"Generated data before validation: {invalid_data}")

                            # Recursive retry with invalid data as context but preserve original valid partial
                            async for event in attempt_stream_with_retry(
                                prompt=prompt,
                                retry_count=retry_count + 1,
                                max_retries=max_retries,
                                partial_data=invalid_data,  # Pass invalid data for context
                                validation_errors=validation_errors,
                                original_valid_partial=original_valid_partial or last_valid_partial,
                            ):
                                yield event
                            return

        except UnexpectedModelBehavior as e:
            # Handle model behavior errors
            validation_errors = validation_errors or []
            validation_errors.append(f"Model behavior error: {str(e)}")

            # Recursive retry if attempts remaining
            if retry_count < max_retries - 1:
                async for event in attempt_stream_with_retry(
                    prompt=prompt,
                    retry_count=retry_count + 1,
                    max_retries=max_retries,
                    partial_data=last_valid_partial,
                    validation_errors=validation_errors,
                    original_valid_partial=original_valid_partial or last_valid_partial,
                ):
                    yield event
            else:
                error_msg = {
                    "type": "error",
                    "message": f"Model behavior error: {e.message if hasattr(e, 'message') else str(e)}",
                }
                yield f"data: {json.dumps(error_msg)}\n\n"
                if not complete_sent:
                    yield f"data: {json.dumps({'type': 'complete', 'status': 'error'})}\n\n"
                    complete_sent = True

        except Exception as e:
            # Handle unexpected errors
            validation_errors = validation_errors or []
            validation_errors.append(f"Unexpected error: {str(e)}")

            # Recursive retry if attempts remaining
            if retry_count < max_retries - 1:
                async for event in attempt_stream_with_retry(
                    prompt=prompt,
                    retry_count=retry_count + 1,
                    max_retries=max_retries,
                    partial_data=last_valid_partial,
                    validation_errors=validation_errors,
                    original_valid_partial=original_valid_partial or last_valid_partial,
                ):
                    yield event
            else:
                error_msg = {"type": "error", "message": str(e)}
                yield f"data: {json.dumps(error_msg)}\n\n"
                if not complete_sent:
                    yield f"data: {json.dumps({'type': 'complete', 'status': 'error'})}\n\n"
                    complete_sent = True

    # Start the recursive streaming process
    try:
        async for event in attempt_stream_with_retry(prompt):
            yield event
    except RuntimeError as e:
        # Ignore "anext(): asynchronous generator is already running" errors
        # which can occur when the recursive function has already completed
        if "asynchronous generator" not in str(e):
            # Re-raise other runtime errors
            raise
