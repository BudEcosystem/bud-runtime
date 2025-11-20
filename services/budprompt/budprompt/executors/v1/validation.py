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

"""Validation module for dynamic model validation using natural language prompts."""

from typing import Type

from budmicroframe.commons import logging
from pydantic import BaseModel, model_validator
from pydantic_ai import Agent
from pydantic_ai.settings import ModelSettings

from budprompt.shared.providers import BudServeProvider


logger = logging.get_logger(__name__)

# Model name for validator code generation
VALIDATION_MODEL_NAME = "qwen3-32b"


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


async def generate_model_validator_code_async(validation_prompt: str, model_class: Type[BaseModel]) -> str:
    """Use LLM to generate model validator method from prompt.

    Args:
        validation_prompt: Natural language validation rule
        model_class: The Pydantic model class to generate validator for

    Returns:
        Python code string containing model validator method
    """
    # Get schema information for the LLM
    schema_info = format_schema_for_llm(model_class)

    # Create provider and model using default model from config
    provider = BudServeProvider()
    # model = provider.get_model(model_name=app_settings.bud_default_model_name, settings=ModelSettings(temperature=0.1))
    model = provider.get_model(model_name=VALIDATION_MODEL_NAME, settings=ModelSettings(temperature=0.1))

    # Create a code generation agent
    code_gen_agent = Agent(
        model=model,
        output_type=str,
        system_prompt=f"""You are a Python code generator. Generate a Pydantic model validator method based on the requirements.

SCHEMA INFORMATION:
{schema_info}

The method should:
1. Be named 'validate_model'
2. Be decorated with @model_validator(mode='after')
3. Take 'self' as parameter
4. Return 'self' if validation passes
5. Raise ValueError with a descriptive message if validation fails
6. Handle the validation rule: {validation_prompt}

Use the field access patterns shown in the schema above (e.g., self.field_name for simple fields, self.nested.field for nested fields).

IMPORTANT: Do NOT include the decorator in the code. Just the method definition.
Do NOT include imports. Do NOT include type hints except for the return type which should be 'Self'.

Return ONLY the method code, no explanations, no markdown, just pure Python code.

Example for a Person model with name, age, email fields:
def validate_model(self) -> 'Self':
    if not (self.age < 18):
        raise ValueError('Age must be less than 18')
    return self""",
    )

    logger.debug(f"Generated prompt for validator code: {validation_prompt}")
    result = await code_gen_agent.run(validation_prompt)
    generated_code = result.output.strip()
    logger.debug(f"Generated validator code:\n{generated_code}")

    return generated_code


async def enhance_validator_error_messages_async(
    validator_code: str, validation_prompt: str, model_class: Type[BaseModel]
) -> str:
    """Analyze and enhance ValueError messages in validator code for better LLM retry feedback.

    Args:
        validator_code: Generated validator code with ValueError exceptions
        validation_prompt: Original validation requirement
        model_class: The model being validated

    Returns:
        Enhanced validator code with improved error messages
    """
    schema_info = format_schema_for_llm(model_class)

    provider = BudServeProvider()
    # model = provider.get_model(model_name=app_settings.bud_default_model_name, settings=ModelSettings(temperature=0.1))
    model = provider.get_model(model_name=VALIDATION_MODEL_NAME, settings=ModelSettings(temperature=0.1))

    enhancement_agent = Agent(
        model=model,
        output_type=str,
        system_prompt=f"""You are a code reviewer specializing in validation error messages.

Your task: Review the validator code and enhance ValueError messages to be more helpful for LLM retry context.

SCHEMA INFORMATION:
{schema_info}

ORIGINAL VALIDATION REQUIREMENT:
{validation_prompt}

GUIDELINES FOR ENHANCEMENT:
1. Check each ValueError message in the code
2. If a message is too generic (e.g., "All names must be Varun"), enhance it to:
   - Specify what was found vs what was expected
   - Include specific field paths that failed
   - Provide clear correction instructions
   - Add examples if helpful

3. Good error message examples:
   Instead of: ValueError("All individuals must be named 'Varun'")
   Use: ValueError("Validation failed: Found people with names ['John', 'Jane'] at indices [0, 1]. All people.name fields must be 'Varun'. Please regenerate with name='Varun' for all person objects.")

   Instead of: ValueError("Age must be greater than 18")
   Use: ValueError(f"Validation failed: Age is {{self.age}} but must be greater than 18. Please regenerate with an age value > 18.")

4. If the error messages are already clear and specific, return the code unchanged.
5. Maintain the exact same validation logic, only enhance the error messages.
6. Use f-strings to include actual values in error messages where possible.

Return ONLY the enhanced Python code, no explanations, no markdown.""",
    )

    logger.debug("Enhancing error messages in validator code")
    result = await enhancement_agent.run(
        f"Review and enhance the error messages in this validator code:\n\n{validator_code}"
    )

    enhanced_code = result.output.strip()

    # Remove markdown code blocks if LLM added them despite instructions
    if enhanced_code.startswith("```python"):
        enhanced_code = enhanced_code[9:]
    if enhanced_code.startswith("```"):
        enhanced_code = enhanced_code[3:]
    if enhanced_code.endswith("```"):
        enhanced_code = enhanced_code[:-3]
    enhanced_code = enhanced_code.strip()

    logger.debug(f"Enhanced validator code:\n{enhanced_code}")

    return enhanced_code


async def add_validator_to_model_async(model_class: Type[BaseModel], validation_prompt: str) -> Type[BaseModel]:
    """Add a dynamic validator to a Pydantic model class.

    Args:
        model_class: The original Pydantic model class
        validation_prompt: Natural language validation rule

    Returns:
        A new model class with the validator added
    """
    # Generate validator code
    validator_code = await generate_model_validator_code_async(validation_prompt, model_class)

    # Enhance error messages if needed for better LLM retry feedback
    # NOTE: Commented out for now as it is not working as expected
    # try:
    #     enhanced_validator_code = await enhance_validator_error_messages_async(
    #         validator_code, validation_prompt, model_class
    #     )
    #     validator_code = enhanced_validator_code
    # except Exception as e:
    #     # If enhancement fails, use original code
    #     logger.warning(f"Failed to enhance validator error messages: {e}. Using original code.")

    # Create namespace for execution
    namespace = {"model_validator": model_validator, "ValueError": ValueError}

    # Execute the validator code to get the function
    try:
        exec(validator_code, namespace)  # nosec B102 - Dynamic validator generation for Pydantic models is required
        validator_func = namespace["validate_model"]
    except Exception as e:
        logger.error(f"Error in generated validator code: {e}")
        raise ValueError(f"Failed to create validator function: {e}") from e

    # Apply the decorator manually
    decorated_validator = model_validator(mode="after")(validator_func)

    # Create a new class that inherits from the original with the validator
    enhanced_model = type(
        f"{model_class.__name__}WithValidator",
        (model_class,),
        {"validate_model": decorated_validator, "__module__": model_class.__module__},
    )

    logger.debug(f"Created enhanced model: {enhanced_model.__name__}")
    return enhanced_model
