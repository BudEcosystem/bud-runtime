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
from jinja2 import Environment, meta
from pydantic import BaseModel, Field

from budprompt.commons.exceptions import PromptExecutionException
from budprompt.prompt.schemas import Message


logger = logging.get_logger(__name__)


def strip_none_values(data: Any) -> Any:
    """Recursively remove keys with None values from dicts and process lists.

    When users pass null for a variable, we want Pydantic to use schema defaults
    instead of treating null as an explicit value. This function strips None values
    from dictionaries and recursively processes lists to handle nested structures.

    Args:
        data: Data structure (dict, list, or other) that may contain None values.

    Returns:
        New data structure with None values removed from dictionaries at all nesting levels.
    """
    if isinstance(data, dict):
        return {k: strip_none_values(v) for k, v in data.items() if v is not None}
    if isinstance(data, list):
        return [strip_none_values(item) for item in data]
    return data


def apply_schema_defaults(data: Any) -> Any:
    """Apply defaults from Pydantic model to its dict representation.

    Gets defaults directly from the model's field definitions instead of
    parsing JSON schema. This avoids complexity with $ref/$defs resolution.

    Args:
        data: Pydantic model instance or dict

    Returns:
        Dict with None/missing values replaced by model defaults
    """
    # If it's a Pydantic model, get defaults from model_fields
    if hasattr(data, "model_dump") and hasattr(data, "model_fields"):
        from pydantic_core import PydanticUndefined

        result = data.model_dump()

        for field_name, field_info in data.model_fields.items():
            # Apply default if value is None and field has a default
            if result.get(field_name) is None and field_info.default is not PydanticUndefined:
                result[field_name] = field_info.default

        return result

    # Fallback: just convert to dict if possible
    if hasattr(data, "model_dump"):
        return data.model_dump()

    return data


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


def validate_input_data_type(input_schema: Dict[str, Any] = None, variables: Optional[Dict[str, Any]] = None) -> None:
    """Validate variables/schema relationship.

    Args:
        input_schema: The input schema (None for unstructured)
        variables: Template variables for structured input validation

    Raises:
        PromptExecutionException: If variables provided without input_schema
    """
    # Validate variables/input_schema relationship
    if variables and input_schema is None:
        logger.error("Variables provided but input_schema is missing")
        raise PromptExecutionException(
            message="Variables provided but input structure not predefined",
            status_code=400,
            err_type="invalid_request_error",
            param="input_schema",
            code="schema_required",
        )


def validate_template_variables(
    variables: Optional[Dict[str, Any]],
    system_prompt: Optional[str],
    messages: Optional[List[Message]],
) -> None:
    """Validate that template variables match what's used in templates.

    Performs bidirectional validation:
    1. All provided variables are used in templates (no unknown variables)
    2. All template variables have values provided (no missing variables)

    Args:
        variables: Dictionary of variable values to use in templates
        system_prompt: Optional system prompt template
        messages: Optional list of message templates

    Raises:
        PromptExecutionException: If validation fails with specific error codes:
            - code="prompt_variable_missing": Template uses variables not provided
            - code="prompt_variable_unknown": Variables provided but not used in templates
    """
    # If no variables provided, check if templates need any
    provided_variables = set(variables.keys()) if variables else set()

    # Extract all template variables from system_prompt and messages
    env = Environment()  # nosec B701 - Only used for parsing/AST analysis, not rendering
    used_variables = set()

    # Check system_prompt for template variables
    if system_prompt:
        try:
            ast = env.parse(system_prompt)
            used_variables.update(meta.find_undeclared_variables(ast))
        except Exception as e:
            logger.warning(f"Failed to parse system_prompt template: {e}")

    # Check messages for template variables
    if messages:
        for msg in messages:
            if msg.content:
                try:
                    ast = env.parse(msg.content)
                    used_variables.update(meta.find_undeclared_variables(ast))
                except Exception as e:
                    logger.warning(f"Failed to parse message template: {e}")

    # Validation 1: Check for missing variables (used in templates but not provided)
    missing_variables = used_variables - provided_variables
    if missing_variables:
        missing_vars_str = ", ".join(sorted(missing_variables))
        error_message = f"Missing prompt variables: {missing_vars_str}"
        logger.error(error_message)
        raise PromptExecutionException(
            message=error_message,
            status_code=400,
            err_type="invalid_request_error",
            param="prompt.variables",
            code="prompt_variable_missing",
        )

    # Validation 2: Check for unknown variables (provided but not used in templates)
    unknown_variables = provided_variables - used_variables
    if unknown_variables:
        unknown_vars_str = ", ".join(sorted(unknown_variables))
        error_message = f"Variables {unknown_vars_str} not specified in templates"
        logger.error(error_message)
        raise PromptExecutionException(
            message=error_message,
            status_code=400,
            err_type="invalid_request_error",
            param="prompt.variables",
            code="prompt_variable_unknown",
        )


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
