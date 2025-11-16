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

"""Streaming JSON Validator for incremental field validation.

Parses JSON as it streams and validates fields immediately when complete.
"""

import io
import json
from typing import Any, AsyncGenerator, Callable, Dict, Optional, Type

import ijson
from pydantic import BaseModel, ValidationError


class StreamingJSONValidator:
    """Validates JSON fields incrementally as they stream.

    Buffers data until fields are valid before sending to client.
    """

    def __init__(self, model_class: Type[BaseModel], field_validators: Dict[str, Callable]):
        """Initialize the streaming validator.

        Args:
            model_class: The Pydantic model class with validators
            field_validators: Dictionary of field_name -> validator_function
        """
        self.model_class = model_class
        self.field_validators = field_validators
        self.validated_data = {}  # Only successfully validated fields
        self.attempted_data = {}  # All attempted fields (including invalid)
        self.current_buffer = ""

    def extract_json_content(self, message) -> str:
        """Extract raw JSON text from ModelResponse or similar objects."""
        if hasattr(message, "parts"):
            for part in message.parts:
                if hasattr(part, "content"):
                    content = part.content
                    # Extract JSON from content that looks like '{"name": "John...'
                    if isinstance(content, str) and "{" in content:
                        # Find the JSON part (everything from first { onwards)
                        json_start = content.find("{")
                        if json_start >= 0:
                            return content[json_start:]
        elif isinstance(message, str):
            return message
        return ""

    async def process_streaming_message(self, message) -> AsyncGenerator[Dict[str, Any], None]:
        """Process a streaming message and yield validated field updates.

        Args:
            message: The streaming message (could be ModelResponse or other format)

        Yields:
            Dictionary with validated field updates or validation errors
        """
        # Extract JSON content from the message
        json_chunk = self.extract_json_content(message)

        if not json_chunk:
            return

        # Add to buffer
        self.current_buffer = json_chunk  # For streaming, we replace buffer with latest

        # Try to parse the current buffer as JSON
        try:
            # Attempt to parse the incomplete JSON to extract completed fields
            partial_data = self._parse_partial_json(self.current_buffer)

            if partial_data:
                # Check each field in the partial data
                for field_name, field_value in partial_data.items():
                    # Always track attempted data
                    self.attempted_data[field_name] = field_value

                    # Skip if we've already validated this field with this value
                    if field_name in self.validated_data and self.validated_data[field_name] == field_value:
                        continue

                    # Check if this field needs validation
                    if field_name in self.field_validators:
                        try:
                            # Run the field validator
                            validator_func = self.field_validators[field_name]

                            # Create ValidationInfo for multi-field validators
                            # We'll create a mock ValidationInfo object with the data available so far
                            from types import SimpleNamespace

                            validation_info = SimpleNamespace()
                            validation_info.data = dict(self.validated_data)  # Available validated data
                            validation_info.field_name = field_name

                            # Field validators in Pydantic are classmethods
                            # Multi-field validators need info parameter
                            if hasattr(validator_func, "__self__"):
                                # It's a bound method - try with info parameter first
                                try:
                                    validated_value = validator_func(field_value, validation_info)
                                except TypeError:
                                    # Fallback to single-field validator
                                    validated_value = validator_func(field_value)
                            else:
                                # It's an unbound method, need to pass cls and info
                                try:
                                    validated_value = validator_func(self.model_class, field_value, validation_info)
                                except TypeError:
                                    # Fallback to single-field validator
                                    validated_value = validator_func(self.model_class, field_value)

                            # Validation passed!
                            self.validated_data[field_name] = validated_value

                            yield {
                                "type": "field_validated",
                                "field": field_name,
                                "value": validated_value,
                                "valid": True,
                                "validated_data": dict(self.validated_data),
                            }

                        except (ValueError, ValidationError) as e:
                            # Field validation failed
                            yield {
                                "type": "field_validation_error",
                                "field": field_name,
                                "value": field_value,
                                "attempted_data": dict(self.attempted_data),  # Include all attempted data
                                "error": str(e),
                                "valid": False,
                            }
                            # Don't add to validated_data
                            # This should trigger a retry with context
                            raise ValueError(f"Field '{field_name}' validation failed: {str(e)}") from e
                    else:
                        # No validator for this field, accept it
                        self.validated_data[field_name] = field_value
                        yield {
                            "type": "field_accepted",
                            "field": field_name,
                            "value": field_value,
                            "valid": True,
                            "validated_data": dict(self.validated_data),
                        }

        except json.JSONDecodeError:
            # Incomplete JSON, wait for more data
            pass

    def _parse_partial_json(self, json_str: str) -> Optional[Dict[str, Any]]:
        """Try to parse potentially incomplete JSON and extract completed fields.

        Args:
            json_str: Potentially incomplete JSON string

        Returns:
            Dictionary of completed fields or None if parsing fails
        """
        if not json_str.strip():
            return None

        try:
            # Try regular JSON parsing first (in case it's complete)
            return json.loads(json_str)
        except json.JSONDecodeError:
            # Use ijson for incremental parsing
            result = {}

            try:
                # Create a bytes buffer for ijson
                json_bytes = json_str.encode("utf-8")
                parser = ijson.parse(io.BytesIO(json_bytes))

                current_key = None
                for prefix, event, value in parser:
                    if event == "map_key":
                        current_key = value
                    elif event in ("string", "number", "boolean", "null"):
                        if current_key and "." not in prefix:  # Top-level field
                            result[current_key] = value
                    elif event == "start_map" and current_key and prefix.endswith(f".{current_key}"):
                        # Beginning of nested object, skip for now
                        # Could implement nested validation here
                        pass

                return result if result else None

            except (ijson.JSONError, ijson.IncompleteJSONError):
                # Even ijson couldn't parse it, truly incomplete
                return None

    def reset(self):
        """Reset the validator state for a new stream."""
        self.validated_data = {}
        self.attempted_data = {}
        self.current_buffer = ""


def extract_field_validators(model_class_with_validators: Type[BaseModel]) -> Dict[str, Callable]:
    """Extract all field validators from the enhanced model class.

    Args:
        model_class_with_validators: Pydantic model class with validators

    Returns:
        Dictionary mapping field names to validator functions
    """
    field_validators = {}

    # Check for field validators (they start with validate_<field_name>)
    for attr_name in dir(model_class_with_validators):
        if attr_name.startswith("validate_") and attr_name != "validate_model":
            # Extract field name from validator method name
            field_name = attr_name.replace("validate_", "", 1)

            # Get the validator method
            validator_method = getattr(model_class_with_validators, attr_name)

            # Store it
            field_validators[field_name] = validator_method

    return field_validators
