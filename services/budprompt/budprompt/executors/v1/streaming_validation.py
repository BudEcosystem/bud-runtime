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

"""Streaming validation module for dynamic field validator generation using natural language prompts."""

from typing import Tuple, Type

from budmicroframe.commons import logging
from pydantic import BaseModel, Field, field_validator
from pydantic_ai import Agent
from pydantic_ai.output import NativeOutput
from pydantic_ai.settings import ModelSettings

from budprompt.shared.providers import BudServeProvider


logger = logging.get_logger(__name__)

# Model name for validator code generation
VALIDATION_MODEL_NAME = "qwen3-32b"


class FieldValidatorOutput(BaseModel):
    """Structured output for field validator generation."""

    field_name: str = Field(description="The name of the field to validate")
    validator_code: str = Field(description="The complete validator method code including @classmethod decorator")


def format_schema_for_llm(model_class: Type[BaseModel]) -> str:
    """Format the model schema in a way the LLM can understand.

    Args:
        model_class: The Pydantic model class

    Returns:
        Formatted string describing the schema structure
    """
    schema = model_class.model_json_schema()
    definitions = schema.get("$defs", {})

    def resolve_ref(ref_string):
        """Resolve $ref references to actual type information."""
        if ref_string.startswith("#/$defs/"):
            def_name = ref_string.replace("#/$defs/", "")
            return definitions.get(def_name, {})
        return {}

    def format_field_info(properties, required_fields, prefix=""):
        field_descriptions = []
        for field_name, field_info in properties.items():
            is_required = field_name in required_fields
            access_path = f"{prefix}{field_name}"

            # Handle $ref references
            if "$ref" in field_info:
                ref_info = resolve_ref(field_info["$ref"])
                ref_name = field_info["$ref"].split("/")[-1]
                field_descriptions.append(
                    f"  - self.{access_path} (nested object: {ref_name}, required: {is_required})"
                )

                # Add nested fields
                if "properties" in ref_info:
                    nested_required = set(ref_info.get("required", []))
                    nested_fields = format_field_info(ref_info["properties"], nested_required, f"{access_path}.")
                    field_descriptions.extend(nested_fields)

            else:
                field_type = field_info.get("type", "unknown")

                # Handle different field types
                if field_type == "object" and "properties" in field_info:
                    # Nested object
                    field_descriptions.append(f"  - self.{access_path} (nested object, required: {is_required})")
                    nested_required = set(field_info.get("required", []))
                    nested_fields = format_field_info(field_info["properties"], nested_required, f"{access_path}.")
                    field_descriptions.extend(nested_fields)
                elif field_type == "array":
                    # Array field
                    items_info = field_info.get("items", {})
                    if "$ref" in items_info:
                        ref_name = items_info["$ref"].split("/")[-1]
                        field_descriptions.append(
                            f"  - self.{access_path} (list of {ref_name} objects, required: {is_required})"
                        )
                    else:
                        items_type = items_info.get("type", "unknown")
                        field_descriptions.append(
                            f"  - self.{access_path} (list of {items_type}, required: {is_required})"
                        )
                else:
                    # Simple field
                    field_descriptions.append(f"  - self.{access_path} (type: {field_type}, required: {is_required})")

        return field_descriptions

    # Get the main properties and required fields
    properties = schema.get("properties", {})
    required_fields = set(schema.get("required", []))

    # Format the schema information
    schema_info = [
        f"Model: {model_class.__name__}",
        f"Description: {schema.get('description', 'No description available')}",
        "",
        "Available fields you can access in the validator:",
    ]

    field_descriptions = format_field_info(properties, required_fields)
    schema_info.extend(field_descriptions)

    return "\n".join(schema_info)


async def generate_field_validator_code(validation_prompt: str, model_class: Type[BaseModel]) -> Tuple[str, str]:
    """Use LLM to generate field validator method from prompt.

    Args:
        validation_prompt: Natural language validation rule
        model_class: The Pydantic model class to generate validator for

    Returns:
        Tuple of (field_name, validator_code)
    """
    # Get schema information for the LLM
    schema_info = format_schema_for_llm(model_class)

    # Create provider and model with consistent temperature for reliable generation
    provider = BudServeProvider()
    # model = provider.get_model(
    #     model_name=app_settings.bud_default_model_name,
    #     settings=ModelSettings(temperature=0.1),  # Lower temperature for consistent code generation
    # )
    model = provider.get_model(
        model_name=VALIDATION_MODEL_NAME,
        settings=ModelSettings(temperature=0.1),  # Lower temperature for consistent code generation
    )

    # Create a code generation agent with structured output
    code_gen_agent = Agent(
        model=model,
        output_type=NativeOutput(FieldValidatorOutput),
        system_prompt=f"""You are a Python code generator. Generate a Pydantic field validator method based on the requirements.

    SCHEMA INFORMATION:
    {schema_info}

    Validation requirement: {validation_prompt}

    Analyze which field needs validation based on the requirement and generate a field validator.

    The method should:
    1. Be a classmethod named 'validate_<field_name>'
    2. Be decorated with @classmethod (this is part of the method definition, NOT a separate decorator)
    3. Take 'cls' and 'v' (value) as parameters
    4. Return the value if validation passes
    5. Raise ValueError with a descriptive message if validation fails

    IMPORTANT INSTRUCTIONS:
    - Do NOT include @field_validator decorator - it will be added programmatically
    - Do NOT include imports
    - Return ONLY the method code, no explanations, no markdown
    - Start the code with @classmethod on its own line
    - The method definition should immediately follow @classmethod

    The code MUST follow this EXACT indentation pattern (no extra spaces before def):

    @classmethod
    def validate_<field_name>(cls, v):
        # validation logic here with 4-space indentation
        return v

    CRITICAL: The 'def' line must start at column 1 (no spaces before it), NOT indented after @classmethod.

    Example output for "Person name should start with 'John'":
    field_name: name
    validator_code:
@classmethod
def validate_name(cls, v):
    if not v.startswith('John'):
        raise ValueError("Name must start with 'John'")
    return v

    Generate the field_name and validator_code. The validator_code must start with @classmethod at column 1.""",
    )

    try:
        result = await code_gen_agent.run(validation_prompt)
        output = result.output
        logger.debug(f"Generated field validator output: field_name={output.field_name}")
        logger.debug(f"Generated validator code:\n{output.validator_code}")
        return output.field_name, output.validator_code
    except Exception as e:
        logger.error(f"ERROR in generate_field_validator_code: {e}")
        raise


async def add_field_validator_to_model(model_class: Type[BaseModel], validation_prompt: str) -> Type[BaseModel]:
    """Add a dynamic field validator to a Pydantic model class.

    Args:
        model_class: The original Pydantic model class
        validation_prompt: Natural language validation rule

    Returns:
        A new model class with the field validator added
    """
    # Try to generate field validator for early validation
    try:
        logger.debug(f"Generating field validator for: {validation_prompt}")
        field_name, validator_code = await generate_field_validator_code(validation_prompt, model_class)
        logger.debug(f"Target field: {field_name}")
        logger.debug(f"Generated field validator code:\n{validator_code}")

        # Create namespace for execution
        namespace = {"field_validator": field_validator, "ValueError": ValueError}

        # Execute the validator code to get the function
        exec(validator_code, namespace)  # nosec B102 - Dynamic validator code execution for streaming validation is required
        # The function name should be validate_<field_name>
        func_name = f"validate_{field_name}"
        if func_name not in namespace:
            # Try to find any function that starts with validate_
            for key in namespace:
                if key.startswith("validate_"):
                    func_name = key
                    break

        if func_name not in namespace:
            raise ValueError(f"Could not find validator function {func_name} in generated code")

        validator_func = namespace[func_name]

        # Apply the field_validator decorator manually
        decorated_validator = field_validator(field_name, mode="after")(validator_func)

        # Create a new class that inherits from the original with the field validator
        enhanced_model = type(
            f"{model_class.__name__}WithFieldValidator",
            (model_class,),
            {func_name: decorated_validator, "__module__": model_class.__module__},
        )

        logger.debug(f"Successfully created model with field validator for '{field_name}'")
        return enhanced_model

    except Exception as e:
        import traceback

        logger.error(f"Failed to create field validator: {e}")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise Exception("Failed to create field validator") from e
