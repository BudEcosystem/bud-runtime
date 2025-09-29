"""
Test LLM structured output generation using existing test models.
This demonstrates using json_schema_to_pydantic_model with actual LLM calls
to generate structured outputs that match our comprehensive test schemas.
"""

import sys
import os

import pytest
from pydantic import ValidationError
from pydantic_ai import Agent

# Import all needed components from the consolidated test file
from test_structured_output import (
    json_schema_to_pydantic_model,
    ComprehensiveTypesModel,
    StringPropertiesModel,
    NumberPropertiesModel,
    ArrayPropertiesModel
)


# ============================================================================
# TEST FUNCTIONS
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.llm
async def test_comprehensive_types(llm_model):
    """Test comprehensive types model with LLM generation.

    Args:
        llm_model: Fixture providing configured LLM model from conftest.py
    """

    # Convert Pydantic model to JSON schema
    schema = ComprehensiveTypesModel.model_json_schema()

    # Create dynamic model from schema
    DynamicModel = json_schema_to_pydantic_model(schema, "DynamicComprehensiveTypes")

    # Create agent with dynamic model
    agent = Agent(
        model=llm_model,
        output_type=DynamicModel,
        system_prompt="You are a structured output generator. Generate valid random data that matches the exact schema provided.",
        retries=3
    )

    # Generate structured output
    result = await agent.run("Generate random data")

    print(f"\nGenerated Output: {result.output.model_dump()}")

    # Validate against original model
    _ = ComprehensiveTypesModel.model_validate(result.output.model_dump())


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.llm
async def test_string_properties(llm_model):
    """Test string properties model with LLM generation.

    Args:
        llm_model: Fixture providing configured LLM model from conftest.py
    """
    # Convert to JSON schema
    schema = StringPropertiesModel.model_json_schema()

    # Create dynamic model
    DynamicModel = json_schema_to_pydantic_model(schema, "DynamicStringProperties")

    # Create agent
    agent = Agent(
        model=llm_model,
        output_type=DynamicModel,
        system_prompt="""Generate valid data for all string fields:
        - username: 3-20 alphanumeric characters with underscores
        - phone: US phone format +1XXXXXXXXXX
        - postal_code: 5-digit US postal code
        - email: valid email address
        - uuid_field: valid UUID v4
        - datetime_field: ISO 8601 datetime
        - date_field: YYYY-MM-DD date
        - time_field: HH:MM:SS time
        - duration_field: ISO 8601 duration (e.g., PT1H30M)
        - hostname: valid hostname
        - ipv4_address: valid IPv4 address
        - ipv6_address: valid IPv6 address""",
        retries=3
    )

    # Generate structured output
    result = await agent.run("Generate random data with valid string formats")

    print(f"\nGenerated Output: {result.output.model_dump()}")

    # Validate against original model
    _ = StringPropertiesModel.model_validate(result.output.model_dump())


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.llm
async def test_number_properties(llm_model):
    """Test number properties model with LLM generation.

    Args:
        llm_model: Fixture providing configured LLM model from conftest.py
    """
    # Convert to JSON schema
    schema = NumberPropertiesModel.model_json_schema()

    # Create dynamic model
    DynamicModel = json_schema_to_pydantic_model(schema, "DynamicNumberProperties")

    # Create agent
    agent = Agent(
        model=llm_model,
        output_type=DynamicModel,
        system_prompt="""Generate valid numeric data:
        - age: 0-150 inclusive
        - score: greater than 0, less than 100 (exclusive)
        - multiple_of_five: any multiple of 5
        - temperature: -273.15 to 1000 Celsius
        - percentage: 0-100 inclusive
        - ratio: between 0 and 1 (exclusive)
        - step_value: multiple of 0.25
        - even_between_10_and_100: even number from 10-100
        - quarter_percentage: 0-100, multiple of 0.25
        - optional_age and optional_temperature can be null or valid values""",
        retries=3
    )

    # Generate structured output
    result = await agent.run("Generate random numeric data")

    print(f"\nGenerated Output: {result.output.model_dump()}")

    # Validate
    _ = NumberPropertiesModel.model_validate(result.output.model_dump())


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.llm
async def test_array_properties(llm_model):
    """Test array properties model with LLM generation.

    Args:
        llm_model: Fixture providing configured LLM model from conftest.py
    """
    # Convert to JSON schema
    schema = ArrayPropertiesModel.model_json_schema()

    # Create dynamic model
    DynamicModel = json_schema_to_pydantic_model(schema, "DynamicArrayProperties")

    # Create agent
    agent = Agent(
        model=llm_model,
        output_type=DynamicModel,
        system_prompt="""Generate valid array data:
        - tags: 1-10 string items
        - coordinates: exactly 2 float values (latitude, longitude)
        - items: at least 3 string items
        - top_five: at most 5 integer items
        - numbers: 1-100 float values
        - booleans: 1-3 boolean values
        - metadata: 0-5 objects with 'name' and 'value' fields
        - matrix: 2D array (list of lists of numbers)
        - optional_list can be null or a list of strings""",
        retries=3
    )

    # Generate structured output
    result = await agent.run("Generate random array data")

    print(f"\nGenerated Output: {result.output.model_dump()}")

    _ = ArrayPropertiesModel.model_validate(result.output.model_dump())
