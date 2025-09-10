from typing import Any, Dict, Type

from budmicroframe.commons import logging
from pydantic import BaseModel, field_validator
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings


logger = logging.get_logger(__name__)


# Bud LLM setup
bud_provider = OpenAIProvider(
    base_url="http://20.66.97.208/v1",
    api_key="sk_",
)
settings = ModelSettings(temperature=0.1)
bud_model = OpenAIModel(model_name="qwen3-32b", provider=bud_provider, settings=settings)


async def generate_validation_function(field_name: str, validation_prompt: str) -> str:
    """Generate a validation function for a specific field using LLM.

    Args:
        field_name: The name of the field to validate
        validation_prompt: Natural language description of validation rule

    Returns:
        Python code string containing the validation function
    """
    code_gen_agent = Agent(
        model=bud_model,
        output_type=str,
        system_prompt="""You are a Python validation function generator.

Generate a simple validation function based on the requirements.
The function should:
1. Be named 'validate_{field_name}'
2. Take a single parameter 'value'
3. Return True if validation passes
4. Return False if validation fails
5. Handle the validation rule described in the prompt

Return ONLY the function code, no explanations, no markdown, just pure Python code.

Example for "Name must be exactly 'Alice'":
def validate_name(value):
    if value == 'Alice':
        return True
    else:
        return False

Example for "Age must be greater than 30":
def validate_age(value):
    if value > 30:
        return True
    else:
        return False
""",
    )

    prompt = f"Generate a validation function for field '{field_name}': {validation_prompt}"
    result = await code_gen_agent.run(prompt)
    return result.output.strip()


class ModelValidationEnhancer:
    """Enhances Pydantic models with custom field validators based on validation rules."""

    async def enhance_model_with_field_validations(
        self, model_class: Type[BaseModel], field_validations: Dict[str, Dict[str, str]]
    ) -> Type[BaseModel]:
        """Enhance a Pydantic model by adding field validators.

        This creates a new subclass with validators since dynamically adding
        validators to existing Pydantic v2 models doesn't work properly.

        Args:
            model_class: The Pydantic model class to enhance
            field_validations: Dictionary mapping field names to validation info with 'prompt' and 'code' keys

        Returns:
            Enhanced model class with validators
        """
        # Generate validation functions for each field
        validation_functions = {}
        validation_namespace = {}

        for field_name, validation_info in field_validations.items():
            # Use pre-generated validation code
            validation_code = validation_info["code"]
            validation_prompt = validation_info["prompt"]
            logger.debug(f"\nUsing validation for '{field_name}': {validation_prompt}")
            logger.debug(f"Code:\n{validation_code}\n")

            # Execute the validation function and store it
            exec(validation_code, validation_namespace)
            func_name = f"validate_{field_name}"
            if func_name in validation_namespace:
                validation_functions[field_name] = validation_namespace[func_name]

        # Create a new class with validators
        class_attrs = {}

        # Add field validators for each field
        for field_name, validation_info in field_validations.items():
            validation_prompt = validation_info["prompt"]
            if field_name in validation_functions:
                # Create the Pydantic field validator method
                def create_validator(fname, fprompt, vfunc):
                    @field_validator(fname, mode="after")
                    def validator(cls, value: Any) -> Any:
                        # Call the generated validation function
                        _ = cls  # Suppress unused variable warning
                        if not vfunc(value):
                            raise ValueError(fprompt)
                        return value

                    return validator

                # Add the validator to class attributes
                validator_method = create_validator(field_name, validation_prompt, validation_functions[field_name])
                class_attrs[f"validate_{field_name}"] = validator_method

        # Create enhanced model as a subclass
        enhanced_model = type(
            model_class.__name__,  # Keep the same name
            (model_class,),  # Inherit from original
            class_attrs,  # Add validators
        )

        # Replace the original model in its module
        if hasattr(model_class, "__module__"):
            import sys

            module = sys.modules.get(model_class.__module__)
            if module and hasattr(module, model_class.__name__):
                setattr(module, model_class.__name__, enhanced_model)

        return enhanced_model

    async def enhance_all_models(
        self, all_models: Dict[str, Type[BaseModel]], all_validations: Dict[str, Dict[str, str]], module
    ) -> Dict[str, Type[BaseModel]]:
        """Enhance all models with their respective validations.

        Models are enhanced in dependency order: leaf models first (Address, Employee),
        then models that reference them (CompanyModel).

        Args:
            all_models: Dictionary of model name to model class
            all_validations: Dictionary of model name to field validations
            module: The module containing the models

        Returns:
            Dictionary of enhanced models
        """

        # Determine model dependencies
        def has_model_references(model_class):
            """Check if a model references other models."""
            if hasattr(model_class, "model_fields"):
                for field_info in model_class.model_fields.values():
                    field_type = field_info.annotation
                    # Check if field type is one of our models
                    for other_model in all_models.values():
                        if field_type == other_model:
                            return True
                        # Check for List[Model]
                        if hasattr(field_type, "__origin__") and hasattr(field_type, "__args__"):  # noqa SIM102
                            if field_type.__args__ and field_type.__args__[0] == other_model:  # noqa SIM102
                                return True
            return False

        # Separate models into two groups: leaf models and referencing models
        leaf_models = {}
        referencing_models = {}

        for model_name, model_class in all_models.items():
            if has_model_references(model_class):
                referencing_models[model_name] = model_class
            else:
                leaf_models[model_name] = model_class

        enhanced_models = {}

        # First, enhance leaf models (Address, Employee)
        for model_name, model_class in leaf_models.items():
            if model_name in all_validations:
                logger.debug(f"Enhancing leaf model: {model_name}")

                field_validations = all_validations[model_name]
                enhanced = await self.enhance_model_with_field_validations(model_class, field_validations)
                enhanced_models[model_name] = enhanced
                # Update module immediately
                setattr(module, model_name, enhanced)
                logger.debug(f"Enhanced model: {model_name}")
            else:
                enhanced_models[model_name] = model_class

        # Then, enhance referencing models (CompanyModel)
        for model_name, model_class in referencing_models.items():
            if model_name in all_validations:
                logger.debug(f"Enhancing referencing model: {model_name}")

                field_validations = all_validations[model_name]
                enhanced = await self.enhance_model_with_field_validations(model_class, field_validations)
                enhanced_models[model_name] = enhanced
                # Update module
                setattr(module, model_name, enhanced)
                logger.debug(f"Enhanced model: {model_name}")
            else:
                enhanced_models[model_name] = model_class

        return enhanced_models


if __name__ == "__main__":
    schema = {
        "$defs": {
            "Person": {
                "properties": {
                    "name": {"title": "Name", "type": "string"},
                    "age": {"title": "Age", "type": "integer"},
                    "email": {"format": "email", "title": "Email", "type": "string"},
                },
                "required": ["name", "age", "email"],
                "title": "Person",
                "type": "object",
            }
        },
        "properties": {"content": {"$ref": "#/$defs/Person"}},
        "required": ["content"],
        "title": "Schema",
        "type": "object",
    }

    validations = {
        "Person": {
            "name": {
                "prompt": "Name must be at least 3 characters",
                "code": "def validate_name(value):\n    if len(value) >= 3:\n        return True\n    else:\n        return False",
            },
            "age": {
                "prompt": "Age must be between 18 and 100",
                "code": "def validate_age(value):\n    if 18 <= value <= 100:\n        return True\n    else:\n        return False",
            },
        }
    }
