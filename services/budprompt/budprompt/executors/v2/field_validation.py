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

"""OpenAI Response Formatter for converting pydantic-ai responses to OpenAI format."""

from typing import Any, Dict, List, Type, Union

from budmicroframe.commons import logging
from pydantic import BaseModel, field_validator
from pydantic_ai import Agent
from pydantic_ai.settings import ModelSettings

from budprompt.commons.config import app_settings
from budprompt.shared.providers import BudServeProvider


logger = logging.get_logger(__name__)


async def generate_validation_function(
    field_name: str, validation_prompt: str, deployment_name: str, access_token: str = None
) -> str:
    """Generate a validation function for a specific field using LLM.

    Args:
        field_name: The name of the field to validate
        validation_prompt: Natural language description of validation rule
        deployment_name: The name of the model deployment to use
        access_token: The access token to use for authentication (if not provided, uses default)

    Returns:
        Python code string containing the validation function
    """
    # Use access token if provided, otherwise fall back to a default (for testing)
    api_key = access_token if access_token else "sk_"

    # Create provider and model using BudServeProvider
    provider = BudServeProvider(base_url=app_settings.bud_gateway_base_url, api_key=api_key)
    model = provider.get_model(deployment_name, settings=ModelSettings(temperature=0.1))

    code_gen_agent = Agent(
        model=model,
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
            exec(validation_code, validation_namespace)  # nosec B102 - Dynamic validation code generation is required
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

    def _rebuild_model_with_enhanced_refs(
        self, model_class: Type[BaseModel], enhanced_models: Dict[str, Type[BaseModel]]
    ) -> Type[BaseModel]:
        """Rebuild a model with enhanced child model references.

        Args:
            model_class: The model to rebuild
            enhanced_models: Dictionary of enhanced models to use as references

        Returns:
            Rebuilt model with enhanced references
        """
        from typing import get_args, get_origin

        # Create new field annotations with enhanced models
        new_annotations = {}
        for field_name, field_info in model_class.model_fields.items():
            field_type = field_info.annotation

            # Handle Optional types
            origin = get_origin(field_type)
            if origin is Union:
                args = get_args(field_type)
                # Check if the non-None type is one of our enhanced models
                for i, arg in enumerate(args):
                    if arg is not type(None):
                        for enhanced_name, enhanced_class in enhanced_models.items():
                            # Check if this arg matches the original model
                            if hasattr(arg, "__name__") and arg.__name__ == enhanced_name:
                                # Replace with enhanced version
                                new_args = list(args)
                                new_args[i] = enhanced_class
                                field_type = Union[tuple(new_args)]
                                break
            # Handle List types
            elif origin in [list, List]:
                args = get_args(field_type)
                if args:
                    inner_type = args[0]
                    for enhanced_name, enhanced_class in enhanced_models.items():
                        if hasattr(inner_type, "__name__") and inner_type.__name__ == enhanced_name:
                            field_type = List[enhanced_class]
                            break
            # Handle direct model references
            else:
                for enhanced_name, enhanced_class in enhanced_models.items():
                    if hasattr(field_type, "__name__") and field_type.__name__ == enhanced_name:
                        field_type = enhanced_class
                        break

            new_annotations[field_name] = field_type

        # Create a new model with the updated annotations
        from pydantic import create_model

        # Get field definitions with defaults
        field_definitions = {}
        for field_name, field_info in model_class.model_fields.items():
            # Use the new annotation
            annotation = new_annotations[field_name]

            # Preserve field info (default, description, etc.)
            if field_info.default is not None:
                field_definitions[field_name] = (annotation, field_info.default)
            elif field_info.default_factory is not None:
                field_definitions[field_name] = (annotation, field_info.default_factory())
            else:
                # Required field
                field_definitions[field_name] = (annotation, ...)

        # Create the new model
        rebuilt_model = create_model(model_class.__name__, **field_definitions)

        return rebuilt_model

    def _extract_all_models(
        self, root_model: Type[BaseModel], models_dict: Dict[str, Type[BaseModel]] = None
    ) -> Dict[str, Type[BaseModel]]:
        """Extract all models from a root model by traversing its fields.

        Args:
            root_model: The root Pydantic model to extract from
            models_dict: Dictionary to accumulate models (used for recursion)

        Returns:
            Dictionary mapping model names to model classes
        """
        if models_dict is None:
            models_dict = {}

        # Add the root model itself
        model_name = root_model.__name__
        if model_name not in models_dict and hasattr(root_model, "model_fields"):
            models_dict[model_name] = root_model

            # Traverse all fields to find nested models
            for _field_name, field_info in root_model.model_fields.items():
                field_type = field_info.annotation

                # Handle Optional types
                import typing

                origin = typing.get_origin(field_type)
                if origin is Union:
                    # Get the non-None type from Optional
                    args = typing.get_args(field_type)
                    field_type = next((arg for arg in args if arg is not type(None)), field_type)

                # Handle List types
                if origin in [list, List]:
                    args = typing.get_args(field_type)
                    if args:
                        field_type = args[0]

                # Check if this is a Pydantic model
                if isinstance(field_type, type) and issubclass(field_type, BaseModel):
                    # Recursively extract models from this nested model
                    self._extract_all_models(field_type, models_dict)

        return models_dict

    async def enhance_all_models(
        self, root_model: Type[BaseModel], all_validations: Dict[str, Dict[str, Dict[str, str]]], module=None
    ) -> Dict[str, Type[BaseModel]]:
        """Enhance all models with their respective validations.

        Models are enhanced in dependency order: leaf models first,
        then models that reference them.

        Args:
            root_model: The root Pydantic model containing all nested models
            all_validations: Dictionary of model name to field validations
            module: Optional module to update with enhanced models

        Returns:
            Dictionary of enhanced models
        """
        # Extract all models from the root model
        all_models = self._extract_all_models(root_model)
        logger.debug(f"Extracted models: {list(all_models.keys())}")

        # Determine model dependencies
        def has_model_references(model_class):
            """Check if a model references other models."""
            if hasattr(model_class, "model_fields"):
                for field_info in model_class.model_fields.values():
                    field_type = field_info.annotation

                    # Handle Optional and List types
                    import typing

                    origin = typing.get_origin(field_type)
                    if origin is Union:
                        args = typing.get_args(field_type)
                        field_type = next((arg for arg in args if arg is not type(None)), field_type)
                    elif origin in [list, List]:
                        args = typing.get_args(field_type)
                        if args:
                            field_type = args[0]

                    # Check if field type is one of our models
                    for other_model in all_models.values():
                        if field_type == other_model and field_type != model_class:
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

        # First, enhance leaf models
        for model_name, model_class in leaf_models.items():
            if model_name in all_validations:
                logger.debug(f"Enhancing leaf model: {model_name}")
                field_validations = all_validations[model_name]
                enhanced = await self.enhance_model_with_field_validations(model_class, field_validations)
                enhanced_models[model_name] = enhanced

                # Update module if provided
                if module:
                    setattr(module, model_name, enhanced)
                logger.debug(f"Enhanced model: {model_name}")
            else:
                enhanced_models[model_name] = model_class

        # Then, enhance referencing models
        # We need to rebuild referencing models with enhanced child models
        for model_name, model_class in referencing_models.items():
            # First, rebuild the model with enhanced child references
            rebuilt_model = self._rebuild_model_with_enhanced_refs(model_class, enhanced_models)

            # Then apply any validations for this model
            if model_name in all_validations:
                logger.debug(f"Enhancing referencing model: {model_name}")
                field_validations = all_validations[model_name]
                enhanced = await self.enhance_model_with_field_validations(rebuilt_model, field_validations)
                enhanced_models[model_name] = enhanced

                # Update module if provided
                if module:
                    setattr(module, model_name, enhanced)
                logger.debug(f"Enhanced model: {model_name}")
            else:
                enhanced_models[model_name] = rebuilt_model

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
