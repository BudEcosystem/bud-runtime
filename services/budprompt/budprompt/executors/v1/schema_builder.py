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

"""Pydantic model generator from JSON schemas."""

import importlib.util
import json
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, Type

from budmicroframe.commons import logging
from datamodel_code_generator import DataModelType, InputFileType, generate
from pydantic import BaseModel

from budprompt.commons.exceptions import SchemaGenerationException


logger = logging.get_logger(__name__)


class DataModelGenerator:
    """Generator for creating Pydantic models from JSON schemas.

    This class encapsulates all logic for converting JSON schemas into
    Pydantic model classes that can be used for validation and serialization.
    """

    def from_json_schema(self, schema: Dict[str, Any], model_name: str = "GeneratedModel") -> Type[BaseModel]:
        """Generate a Pydantic model from JSON schema.

        Args:
            schema: JSON schema dictionary
            model_name: Name for the generated model class

        Returns:
            Pydantic model class

        Raises:
            SchemaGenerationException: If schema validation or conversion fails
        """
        # Validate the schema first
        self._validate_schema(schema)

        # Generate Pydantic code from schema
        generated_code = self._generate_code(schema, model_name)

        # Load the generated code as a Pydantic model
        return self._load_model(generated_code, model_name)

    def _validate_schema(self, schema: Dict[str, Any]) -> None:
        """Validate that the provided dictionary is a valid JSON schema.

        Args:
            schema: JSON schema dictionary to validate

        Raises:
            SchemaGenerationException: If schema is invalid
        """
        required_fields = {"type", "properties"}
        schema_type = schema.get("type")

        if schema_type == "object":
            if not all(field in schema for field in required_fields):
                logger.error("Schema is invalid: missing required fields")
                raise SchemaGenerationException(
                    f"Object schema must contain: {required_fields}. Got: {set(schema.keys())}"
                )
        elif schema_type not in ["string", "number", "integer", "boolean", "array", "object"]:
            logger.error("Schema is invalid: unsupported type %s", schema_type)
            raise SchemaGenerationException(f"Invalid schema type: {schema_type}")

    def _generate_code(self, schema: Dict[str, Any], model_name: str) -> str:
        """Generate Pydantic model code from JSON schema.

        Args:
            schema: JSON schema dictionary
            model_name: Name for the generated model

        Returns:
            Generated Python code as string

        Raises:
            SchemaGenerationException: If code generation fails
        """
        input_path = None
        output_path = None

        try:
            # Create temporary files for input and output
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as input_file:
                json.dump(schema, input_file)
                input_path = Path(input_file.name)
            logger.debug("JSON schema saved to temp file: %s", input_path)

            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as output_file:
                output_path = Path(output_file.name)
            logger.debug("Output path for generated code: %s", output_path)

            # Generate Pydantic model using datamodel-code-generator
            generate(
                input_=input_path,
                input_file_type=InputFileType.JsonSchema,
                output=output_path,
                output_model_type=DataModelType.PydanticV2BaseModel,
                use_standard_collections=True,
                field_constraints=True,
                use_annotated=False,
                class_name=model_name,
            )

            # Read generated code
            with open(output_path, "r") as f:
                generated_code = f.read()

            logger.debug("Successfully generated Pydantic code for model: %s", model_name)
            return generated_code

        except Exception as e:
            logger.error("Failed to generate Pydantic code: %s", str(e))
            raise SchemaGenerationException("Invalid JSON schema format") from e

        finally:
            # Clean up temporary files
            if input_path and input_path.exists():
                logger.debug("Deleting temp input file: %s", input_path)
                input_path.unlink(missing_ok=True)
            if output_path and output_path.exists():
                logger.debug("Deleting temp output file: %s", output_path)
                output_path.unlink(missing_ok=True)

    def _load_model(self, generated_code: str, model_name: str) -> Type[BaseModel]:
        """Load a Pydantic model from generated Python code.

        Args:
            generated_code: Python code containing Pydantic model definition
            model_name: Name of the model class to load

        Returns:
            Pydantic model class

        Raises:
            SchemaGenerationException: If loading fails
        """
        # Generate unique module name to avoid conflicts
        module_name = f"temp_models_{uuid.uuid4().hex[:8]}"
        logger.debug("Creating temporary module: %s", module_name)

        try:
            # Create module spec
            spec = importlib.util.spec_from_loader(module_name, loader=None)
            if spec is None:
                logger.error("Failed to create module spec")
                raise SchemaGenerationException("Failed to create module spec")

            module = importlib.util.module_from_spec(spec)

            # Register in sys.modules temporarily
            sys.modules[module_name] = module

            try:
                # Execute the generated code in module context
                exec(generated_code, module.__dict__)  # nosec B102 - Dynamic Pydantic model generation from JSON schema is required

                # Get the model class by name
                if not hasattr(module, model_name):
                    # If exact name not found, try to find any BaseModel subclass
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
                            logger.debug("Found model class: %s", attr_name)
                            break

                    if model_class is None:
                        logger.error("No Pydantic model found in generated code")
                        raise SchemaGenerationException("No Pydantic model found in generated code")
                else:
                    model_class = getattr(module, model_name)
                    logger.debug("Successfully loaded model: %s", model_name)

                return model_class

            finally:
                # Always clean up - remove from sys.modules
                if module_name in sys.modules:
                    logger.debug("Removing temporary module from sys.modules: %s", module_name)
                    del sys.modules[module_name]

        except SchemaGenerationException:
            raise
        except Exception as e:
            logger.error("Failed to load Pydantic model from code: %s", str(e))
            raise SchemaGenerationException("Unable to process schema") from e
