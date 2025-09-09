"""
Wrapper for test compatibility with the new ModelGeneratorFactory.
This module provides a synchronous interface for tests.
"""

import asyncio
from typing import Any, Dict, Type
from pydantic import BaseModel
from budprompt.prompt.schema_builder import ModelGeneratorFactory
from budprompt.commons.helpers import run_async


def json_schema_to_pydantic_model(
    schema: Dict[str, Any],
    model_name: str = "DynamicModel",
    validators: Dict[str, Any] | None = None,
    existing_models: Dict[str, Type[BaseModel]] | None = None
) -> Type[BaseModel]:
    """
    Synchronous wrapper for ModelGeneratorFactory for test compatibility.

    Args:
        schema: JSON schema dictionary
        model_name: Name for the generated model
        validators: Dictionary of validators for the model
        existing_models: Dictionary of already created models to handle references

    Returns:
        Dynamically created Pydantic model class
    """
    # Run the async factory method synchronously for test compatibility
    return run_async(
        ModelGeneratorFactory.create_model(
            schema=schema,
            model_name=model_name,
            generator_type="custom",
            validators=validators,
            existing_models=existing_models
        )
    )

#  docker exec budserve-development-budprompt bash -c "PYTHONPATH=/app pytest tests/test_unit_tests/test_structured_output -v -s"
