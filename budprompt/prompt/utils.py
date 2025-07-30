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

import importlib.util
import json
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, Type

from datamodel_code_generator import DataModelType, InputFileType, generate
from pydantic import BaseModel, Field

from budprompt.commons.exceptions import InputValidationError, SchemaConversionError


def convert_json_schema_to_pydantic(json_schema: Dict[str, Any], model_name: str = "GeneratedModel") -> str:
    """Convert JSON schema to Pydantic model code.

    Args:
        json_schema: JSON schema dictionary
        model_name: Name for the generated model class

    Returns:
        Generated Pydantic model code as string

    Raises:
        SchemaConversionError: If conversion fails
    """
    try:
        # Create temporary files for input and output
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as input_file:
            json.dump(json_schema, input_file)
            input_path = Path(input_file.name)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as output_file:
            output_path = Path(output_file.name)

        # Generate Pydantic model
        generate(
            input_=input_path,
            input_file_type=InputFileType.JsonSchema,
            output=output_path,
            output_model_type=DataModelType.PydanticV2BaseModel,
            use_standard_collections=True,
            field_constraints=True,
            use_annotated=True,
            class_name=model_name,
        )

        # Read generated code
        with open(output_path, "r") as f:
            generated_code = f.read()

        return generated_code

    except Exception as e:
        raise SchemaConversionError(f"Failed to convert JSON schema to Pydantic model: {str(e)}")
    finally:
        # Clean up temporary files
        if "input_path" in locals():
            input_path.unlink(missing_ok=True)
        if "output_path" in locals():
            output_path.unlink(missing_ok=True)


def load_pydantic_model_from_code(generated_code: str, model_name: str = None) -> Type[BaseModel]:
    """Load a Pydantic model from generated Python code.

    Args:
        generated_code: Python code containing Pydantic model definition
        model_name: Name of the model class to load (auto-detect if None)

    Returns:
        Pydantic model class

    Raises:
        SchemaConversionError: If loading fails
    """
    try:
        # Generate unique module name to avoid conflicts
        module_name = f"temp_models_{uuid.uuid4().hex[:8]}"

        # Create module spec
        spec = importlib.util.spec_from_loader(module_name, loader=None)
        if spec is None:
            raise SchemaConversionError("Failed to create module spec")

        module = importlib.util.module_from_spec(spec)

        # Register in sys.modules
        sys.modules[module_name] = module

        try:
            # Execute the code in module context
            exec(generated_code, module.__dict__)

            if model_name:
                # Get specific model by name
                if not hasattr(module, model_name):
                    raise SchemaConversionError(f"Model '{model_name}' not found in generated code")
                model_class = getattr(module, model_name)
            else:
                # Auto-detect model class
                model_class = None
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, BaseModel)
                        and attr != BaseModel
                        and not attr_name.startswith("_")
                    ):
                        model_class = attr
                        break

                if model_class is None:
                    raise SchemaConversionError("No Pydantic model found in generated code")

            return model_class

        finally:
            # Clean up - remove from sys.modules
            if module_name in sys.modules:
                del sys.modules[module_name]

    except SchemaConversionError:
        raise
    except Exception as e:
        raise SchemaConversionError(f"Failed to load Pydantic model from code: {str(e)}")


def validate_json_schema(schema: Dict[str, Any]) -> None:
    """Validate that the provided dictionary is a valid JSON schema.

    Args:
        schema: JSON schema dictionary to validate

    Raises:
        SchemaConversionError: If schema is invalid
    """
    required_fields = {"type", "properties"}
    schema_type = schema.get("type")

    if schema_type == "object":
        if not all(field in schema for field in required_fields):
            raise SchemaConversionError(f"Object schema must contain: {required_fields}. Got: {set(schema.keys())}")
    elif schema_type not in ["string", "number", "integer", "boolean", "array", "object"]:
        raise SchemaConversionError(f"Invalid schema type: {schema_type}")


def clean_model_cache():
    """Clean up any temporary modules from sys.modules."""
    modules_to_remove = [key for key in sys.modules.keys() if key.startswith("temp_models_")]
    for module_name in modules_to_remove:
        del sys.modules[module_name]


def create_string_model(model_name: str = "StringModel") -> Type[BaseModel]:
    """Create a simple Pydantic model for string input/output.

    Args:
        model_name: Name for the model class

    Returns:
        Pydantic model class with a single string field
    """
    # Dynamically create a Pydantic model with a single string field
    model_attrs = {
        "content": Field(..., description="String content"),
        "__module__": f"temp_models_{uuid.uuid4().hex[:8]}",
    }

    return type(model_name, (BaseModel,), model_attrs)


def validate_input_data_type(input_data: Any, input_schema: Dict[str, Any] = None) -> None:
    """Validate that input_data type matches the schema presence.

    Args:
        input_data: The input data to validate
        input_schema: The input schema (None for unstructured)

    Raises:
        InputValidationError: If input_data type doesn't match schema presence
    """
    if input_schema is not None:
        # Structured input expected
        if not isinstance(input_data, dict):
            raise InputValidationError(
                "Structured input expected (input_schema provided) but got non-dict input_data. "
                f"Got type: {type(input_data).__name__}"
            )
    else:
        # Unstructured input expected
        if input_data is not None and not isinstance(input_data, str):
            raise InputValidationError(
                "Unstructured input expected (input_schema is None) but got non-string input_data. "
                f"Got type: {type(input_data).__name__}"
            )
