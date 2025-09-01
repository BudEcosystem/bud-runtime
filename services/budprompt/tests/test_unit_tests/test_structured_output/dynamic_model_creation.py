from pydantic import (
    BaseModel, create_model, Field,
    EmailStr, UUID4, IPvAnyAddress,
    constr, conint, confloat, conlist
)
from typing import Dict, Any, Type, Optional, List, Union, Literal, ForwardRef
from datetime import datetime, date, time, timedelta
from decimal import Decimal
import re
from uuid import UUID


# Mapping of JSON Schema format to Python/Pydantic types
FORMAT_TYPE_MAP = {
    'email': EmailStr,
    'date-time': datetime,
    'date': date,
    'time': time,
    'duration': timedelta,
    'uuid': UUID,
    'ipv4': IPvAnyAddress,
    'ipv6': IPvAnyAddress,
    'ipvanyaddress': IPvAnyAddress,
    'hostname': str,  # Will use pattern validation
}


def json_schema_to_pydantic_model(
    schema: Dict[str, Any],
    model_name: str = "DynamicModel",
    validators: Dict[str, Any] | None = None,
    existing_models: Dict[str, Type[BaseModel]] | None = None
) -> Type[BaseModel]:
    """
    Convert a JSON schema to a Pydantic model using create_model.

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
                nested_model = json_schema_to_pydantic_model(
                    def_schema,
                    f"Dynamic{def_name}",
                    validators,
                    existing_models
                )
                existing_models[def_name] = nested_model

    # Build field definitions for create_model
    field_definitions = {}

    for field_name, field_schema in properties.items():
        python_type = determine_field_type(field_schema, existing_models, field_name)

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


def determine_field_type(field_schema: Dict[str, Any], existing_models: Dict[str, Type[BaseModel]], field_name: str = "") -> Any:
    """
    Determine the Python type for a field based on its JSON schema.
    Supports all OpenAI structured output features.

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
            opt_type = determine_field_type(option, existing_models, field_name)
            if opt_type == type(None):
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
                types.append(determine_field_type(simple_schema, existing_models, field_name))

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
        item_type = determine_field_type(items_schema, existing_models, f"{field_name}_item")

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
                inline_model = json_schema_to_pydantic_model(
                    field_schema,
                    inline_model_name,
                    None,  # No validators for inline models (for now)
                    existing_models
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
                value_type = determine_field_type(
                    field_schema["additionalProperties"],
                    existing_models,
                    f"{field_name}_value"
                )
                return Dict[str, value_type]

        return dict

    # Default to string type
    return str
