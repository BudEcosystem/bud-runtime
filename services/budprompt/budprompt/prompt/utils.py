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

import sys
from typing import Any, Dict, Union, get_args, get_origin

from budmicroframe.commons import logging
from pydantic import BaseModel

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
