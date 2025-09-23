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
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Dict, ForwardRef, List, Literal, Optional, Type, Union

from budmicroframe.commons import logging
from datamodel_code_generator import DataModelType, InputFileType, generate
from pydantic import BaseModel, EmailStr, confloat, conint, conlist, constr, create_model
from pydantic.networks import IPv4Address, IPv6Address

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


# Mapping of JSON Schema format to Python/Pydantic types
FORMAT_TYPE_MAP = {
    "email": EmailStr,
    "date-time": datetime,
    "date": date,
    "time": time,
    "duration": timedelta,
    "uuid": uuid.UUID,
    "ipv4": IPv4Address,
    "ipv6": IPv6Address,
    "hostname": str,  # Will use pattern validation
}


class CustomModelGenerator:
    """Custom Generator for creating Pydantic models from JSON schemas.

    This class encapsulates all logic for converting JSON schemas into
    Pydantic model classes that can be used for validation and serialization.
    """

    async def from_json_schema(
        self,
        schema: Dict[str, Any],
        model_name: str = "DynamicModel",
        validators: Dict[str, Any] | None = None,
        existing_models: Dict[str, Type[BaseModel]] | None = None,
    ) -> Type[BaseModel]:
        """Convert a JSON schema to a Pydantic model using create_model.

        Args:
            schema: JSON schema dictionary
            model_name: Name for the generated model
            validators: Dictionary of validators for the model
            existing_models: Dictionary of already created models to handle references

        Returns:
            Dynamically created Pydantic model class
        """
        if existing_models is None:
            existing_models = {}

        # Extract properties from the JSON schema
        properties = schema.get("properties", {})
        required_fields = set(schema.get("required", []))
        definitions = schema.get("$defs", {})

        # Process nested definitions first
        for def_name, def_schema in definitions.items():
            if def_name not in existing_models:
                # Check if this is an enum definition
                if "enum" in def_schema:
                    # For enums, create a Literal type with the enum values
                    enum_values = def_schema["enum"]
                    if len(enum_values) == 1:
                        existing_models[def_name] = Literal[enum_values[0]]
                    else:
                        # Use Union of Literals for multiple values
                        existing_models[def_name] = Union[tuple(Literal[v] for v in enum_values)]
                else:
                    # It's a regular model
                    nested_model = await self.from_json_schema(def_schema, def_name, validators, existing_models)
                    existing_models[def_name] = nested_model

        # Build field definitions for create_model
        field_definitions = {}

        for field_name, field_schema in properties.items():
            python_type = await self.determine_field_type(field_schema, existing_models, field_name)

            # Handle self-references for recursive schemas
            if python_type == "self":
                python_type = ForwardRef(model_name)

            # Handle required vs optional fields
            if field_name in required_fields:
                field_definitions[field_name] = (python_type, ...)  # Required field
            else:
                # Make the type Optional if it's not required
                # Don't wrap None type in Optional
                if python_type is not type(None):
                    field_definitions[field_name] = (Optional[python_type], None)
                else:
                    field_definitions[field_name] = (type(None), None)

        # Create base model first
        base_model = create_model(model_name, **field_definitions)

        # Add validators if they exist for this model
        if validators and model_name in validators:
            model_validators = validators[model_name]

            # Create a new class that inherits from the base model and adds validators
            class_dict = {"__module__": __name__}
            class_dict.update(model_validators)

            # Create the final model with validators
            dynamic_model = type(model_name, (base_model,), class_dict)
            return dynamic_model

        return base_model

    async def determine_field_type(
        self, field_schema: Dict[str, Any], existing_models: Dict[str, Type[BaseModel]], field_name: str = ""
    ) -> Any:
        """Determine the Python type for a field based on its JSON schema.

        Args:
            field_schema: JSON schema for the field
            existing_models: Dictionary of already created models
            field_name: Name of the field (for creating inline models)

        Returns:
            Python type or constrained type for the field
        """
        # Handle references to other models
        if "$ref" in field_schema:
            ref_path = field_schema["$ref"]
            # Handle root recursion
            if ref_path == "#":
                # This will be handled by forward references
                return "self"
            # Extract model name from reference (e.g., "#/$defs/Person" -> "Person")
            model_name = ref_path.split("/")[-1]
            if model_name in existing_models:
                return existing_models[model_name]
            # Fallback to dict if reference not found
            return dict

        # Handle const (literal values)
        if "const" in field_schema:
            const_value = field_schema["const"]
            return Literal[const_value]

        # Handle enum fields
        if "enum" in field_schema:
            enum_values = field_schema["enum"]
            # Create a Literal type with all enum values
            if len(enum_values) == 1:
                return Literal[enum_values[0]]
            else:
                # Use Union of Literals for multiple values
                return Union[tuple(Literal[v] for v in enum_values)]

        # Handle anyOf (unions and nullable fields)
        if "anyOf" in field_schema:
            types = []
            for option in field_schema["anyOf"]:
                opt_type = await self.determine_field_type(option, existing_models, field_name)
                if opt_type == type(None):  # noqa
                    types.append(None)
                else:
                    types.append(opt_type)

            if len(types) == 1:
                return types[0]
            elif len(types) == 2 and None in types:
                # This is a nullable field
                other_type = [t for t in types if t is not None][0]
                return Optional[other_type]
            else:
                # Create a Union of all types
                return Union[tuple(types)]

        # Handle type arrays (e.g., ["string", "null"] for nullable)
        if isinstance(field_schema.get("type"), list):
            types = []
            for type_str in field_schema["type"]:
                if type_str == "null":
                    types.append(None)
                else:
                    # Create a simple schema for this type
                    simple_schema = {**field_schema, "type": type_str}
                    types.append(await self.determine_field_type(simple_schema, existing_models, field_name))

            if len(types) == 2 and None in types:
                # This is a nullable field
                other_type = [t for t in types if t is not None][0]
                return Optional[other_type]
            else:
                return Union[tuple(types)]

        # Get the base type
        field_type = field_schema.get("type", "string")

        # Handle string type with constraints
        if field_type == "string":
            # Check for format first
            if "format" in field_schema:
                format_type = field_schema["format"]
                if format_type in FORMAT_TYPE_MAP:
                    return FORMAT_TYPE_MAP[format_type]

            # Check for pattern constraint
            if "pattern" in field_schema:
                return constr(pattern=field_schema["pattern"])

            # Check for length constraints (if supported)
            min_length = field_schema.get("minLength")
            max_length = field_schema.get("maxLength")
            if min_length is not None or max_length is not None:
                return constr(min_length=min_length, max_length=max_length)

            return str

        # Handle integer type with constraints
        elif field_type == "integer":
            constraints = {}

            if "minimum" in field_schema:
                constraints["ge"] = field_schema["minimum"]
            if "maximum" in field_schema:
                constraints["le"] = field_schema["maximum"]
            if "exclusiveMinimum" in field_schema:
                constraints["gt"] = field_schema["exclusiveMinimum"]
            if "exclusiveMaximum" in field_schema:
                constraints["lt"] = field_schema["exclusiveMaximum"]
            if "multipleOf" in field_schema:
                constraints["multiple_of"] = field_schema["multipleOf"]

            if constraints:
                return conint(**constraints)
            return int

        # Handle number/float type with constraints
        elif field_type == "number":
            constraints = {}

            if "minimum" in field_schema:
                constraints["ge"] = field_schema["minimum"]
            if "maximum" in field_schema:
                constraints["le"] = field_schema["maximum"]
            if "exclusiveMinimum" in field_schema:
                constraints["gt"] = field_schema["exclusiveMinimum"]
            if "exclusiveMaximum" in field_schema:
                constraints["lt"] = field_schema["exclusiveMaximum"]
            if "multipleOf" in field_schema:
                constraints["multiple_of"] = field_schema["multipleOf"]

            if constraints:
                return confloat(**constraints)
            return float

        # Handle boolean type
        elif field_type == "boolean":
            return bool

        # Handle null type
        elif field_type == "null":
            return type(None)

        # Handle arrays with constraints
        elif field_type == "array":
            items_schema = field_schema.get("items", {})
            item_type = await self.determine_field_type(items_schema, existing_models, f"{field_name}_item")

            # Check for array constraints
            min_items = field_schema.get("minItems")
            max_items = field_schema.get("maxItems")

            if min_items is not None or max_items is not None:
                return conlist(item_type, min_length=min_items, max_length=max_items)

            return List[item_type]

        # Handle objects (could be dict or nested model)
        elif field_type == "object":
            # If it has properties, create an inline nested model
            if "properties" in field_schema:
                # Create an inline nested model
                inline_model_name = f"Dynamic{field_name.title()}"
                if inline_model_name not in existing_models:
                    inline_model = await self.from_json_schema(
                        field_schema,
                        inline_model_name,
                        None,  # No validators for inline models (for now)
                        existing_models,
                    )
                    existing_models[inline_model_name] = inline_model
                return existing_models[inline_model_name]

            # Check if additionalProperties is defined
            if "additionalProperties" in field_schema:
                if field_schema["additionalProperties"] is False:
                    # Strict object with no additional properties
                    return dict
                elif isinstance(field_schema["additionalProperties"], dict):
                    # Object with typed additional properties
                    value_type = await self.determine_field_type(
                        field_schema["additionalProperties"], existing_models, f"{field_name}_value"
                    )
                    return Dict[str, value_type]

            return dict

        # Default to string type
        return str


class ModelGeneratorFactory:
    """Factory class for choosing the appropriate model generator.

    This factory provides a unified interface for selecting between
    DataModelGenerator and CustomModelGenerator based on the use case.
    """

    @staticmethod
    def get_generator(generator_type: str = "custom") -> Union[DataModelGenerator, CustomModelGenerator]:
        """Get the appropriate model generator instance.

        Args:
            generator_type: Type of generator to use ("datamodel" or "custom")

        Returns:
            Instance of the requested generator

        Raises:
            ValueError: If unknown generator type is requested
        """
        if generator_type == "datamodel":
            return DataModelGenerator()
        elif generator_type == "custom":
            return CustomModelGenerator()
        else:
            raise ValueError(f"Unknown generator type: {generator_type}. Use 'datamodel' or 'custom'")

    @staticmethod
    async def create_model(
        schema: Dict[str, Any],
        model_name: str = "DynamicModel",
        generator_type: str = "custom",
        validators: Dict[str, Any] | None = None,
        existing_models: Dict[str, Type[BaseModel]] | None = None,
    ) -> Type[BaseModel]:
        """Create a Pydantic model using the specified generator.

        This is a convenience method that gets the generator and creates the model
        in a single call.

        Args:
            schema: JSON schema dictionary
            model_name: Name for the generated model
            generator_type: Type of generator to use ("datamodel" or "custom")
            validators: Dictionary of validators (only used with custom generator)
            existing_models: Dictionary of already created models (only used with custom generator)

        Returns:
            Generated Pydantic model class
        """
        generator = ModelGeneratorFactory.get_generator(generator_type)

        if generator_type == "datamodel":
            # DataModelGenerator doesn't support validators or existing_models
            return generator.from_json_schema(schema, model_name)
        else:
            # CustomModelGenerator supports additional parameters
            return await generator.from_json_schema(
                schema=schema, model_name=model_name, validators=validators, existing_models=existing_models
            )
