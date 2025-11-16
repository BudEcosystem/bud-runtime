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

"""Utility functions for prompt execution."""

import json
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union, get_args, get_origin

from budmicroframe.commons import logging
from pydantic import BaseModel, Field

from budprompt.commons.exceptions import SchemaGenerationException


logger = logging.get_logger(__name__)


def clean_model_cache():
    """Clean up any temporary modules from sys.modules."""
    modules_to_remove = [key for key in sys.modules if key.startswith("temp_models_")]
    for module_name in modules_to_remove:
        logger.debug("Removing module from sys.modules: %s", module_name)
        del sys.modules[module_name]


def contains_pydantic_model(output_type: Any) -> bool:
    """Check if a type contains a Pydantic BaseModel.

    Handles:
    - Direct BaseModel: MyModel
    - List of BaseModel: List[MyModel]
    - Union with BaseModel: Union[str, MyModel]
    - Nested combinations: List[Union[str, MyModel]]
    - NativeOutput wrapper: NativeOutput(MyModel)

    Args:
        output_type: The type to check

    Returns:
        True if the type contains a Pydantic BaseModel, False otherwise
    """
    # Handle NativeOutput wrapper (from pydantic-ai)
    if hasattr(output_type, "outputs") and hasattr(output_type.outputs, "__mro__"):
        # NativeOutput has an outputs attribute that contains the actual type
        return contains_pydantic_model(output_type.outputs)

    # Direct BaseModel check
    if isinstance(output_type, type) and issubclass(output_type, BaseModel):
        return True

    # Get origin and args for generic types
    origin = get_origin(output_type)
    args = get_args(output_type)

    if origin is list and args:
        # List[SomeType] - check the item type
        return contains_pydantic_model(args[0])

    if origin is Union and args:
        # Union[Type1, Type2, ...] - check if any type is BaseModel
        return any(contains_pydantic_model(arg) for arg in args)

    return False


def validate_input_data_type(input_data: Any, input_schema: Dict[str, Any] = None) -> None:
    """Validate that input_data type matches the schema presence.

    Args:
        input_data: The input data to validate
        input_schema: The input schema (None for unstructured)

    Raises:
        SchemaGenerationException: If input_data type doesn't match schema presence
    """
    if input_schema is not None:
        # Structured input expected
        if not isinstance(input_data, dict):
            logger.error(f"Expected dict for structured input, got {type(input_data).__name__}")
            raise SchemaGenerationException("Input data must be a dictionary when input_schema is provided")
    else:
        # Unstructured input expected
        if input_data is not None and not isinstance(input_data, str):
            logger.error(f"Expected string for unstructured input, got {type(input_data).__name__}")
            raise SchemaGenerationException("Input data must be a string when input_schema is not provided")


class SerializedPydanticResult(BaseModel):
    """Root schema for serialized Pydantic AI result.

    This schema provides a consistent structure for Pydantic AI execution results,
    including all messages, token usage, timestamp, and the final response.
    """

    all_messages: List[Dict[str, Any]] = Field(
        ..., description="All conversation messages with string content in parts"
    )
    usage: Dict[str, Any] = Field(..., description="Token usage information")
    timestamp: str = Field(..., description="ISO format timestamp of serialization")
    response: Optional[Any] = Field(None, description="Final response output")


class PydanticResultSerializer:
    """Serializes Pydantic AI results to a structured, JSON-safe format.

    This class handles the conversion of Pydantic AI result objects into a
    consistent, serializable format suitable for logging, debugging, and
    client consumption.
    """

    def serialize(self, result) -> SerializedPydanticResult:
        """Serialize pydantic-ai result to structured format.

        Args:
            result: Pydantic AI result object with all_messages(), usage(), and output

        Returns:
            SerializedPydanticResult with all data in JSON-safe format
        """
        # Get and process messages
        messages = result.all_messages()
        sanitized_messages = self._sanitize_for_json(messages)
        client_ready_messages = self._ensure_parts_content_is_string(sanitized_messages)

        # Extract and sanitize usage
        usage = result.usage()
        usage_dict = self._sanitize_for_json(usage)

        # Build final structure
        return SerializedPydanticResult(
            all_messages=client_ready_messages,
            usage=usage_dict,
            timestamp=datetime.now(timezone.utc).isoformat(),
            response=result.output if hasattr(result, "output") else None,
        )

    def _sanitize_for_json(self, obj):
        """Recursively sanitize objects for JSON serialization.

        Converts non-serializable types to their string representation.

        Args:
            obj: Any Python object to sanitize

        Returns:
            JSON-serializable version of the object
        """
        if isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        elif isinstance(obj, dict):
            return {k: self._sanitize_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._sanitize_for_json(item) for item in obj]
        elif isinstance(obj, Exception):
            # Convert exceptions to their string representation
            return str(obj)
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif hasattr(obj, "__dict__"):
            # For dataclasses and other objects with __dict__
            return self._sanitize_for_json(obj.__dict__)
        else:
            # Fallback: convert to string
            return str(obj)

    def _ensure_parts_content_is_string(self, messages):
        """Ensure all 'content' fields in message parts are strings.

        Iterates through messages and their parts, converting any non-string
        content to a string representation. This ensures the output is
        client-ready for LLM requests where content must be a string.

        Args:
            messages: List of message dictionaries

        Returns:
            Updated messages with all part content as strings
        """
        if not isinstance(messages, list):
            return messages

        for message in messages:
            if not isinstance(message, dict):
                continue

            # Check if message has parts
            if "parts" in message and isinstance(message["parts"], list):
                for part in message["parts"]:
                    if not isinstance(part, dict):
                        continue

                    # Convert content to string if it's not already
                    if "content" in part and not isinstance(part["content"], str):
                        # Convert to JSON string for complex types (like validation error arrays)
                        part["content"] = json.dumps(part["content"])

        return messages
