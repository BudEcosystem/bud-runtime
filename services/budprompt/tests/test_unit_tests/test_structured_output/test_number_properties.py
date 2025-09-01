"""
Test cases for number properties in OpenAI Structured Output.
Tests: multipleOf, minimum, maximum, exclusiveMinimum, exclusiveMaximum for both integer and float types
"""

import sys
import os

import pytest
from pydantic import BaseModel, Field, ValidationError, conint, confloat
from typing import Optional
from decimal import Decimal
from test_openai_structured_output.dynamic_model_creation import json_schema_to_pydantic_model


class NumberPropertiesModel(BaseModel):
    """Model containing all number constraint types."""

    # Integer constraints
    age: conint(ge=0, le=150) = Field(
        description="Age with minimum 0 and maximum 150"
    )
    score: conint(gt=0, lt=100) = Field(
        description="Score with exclusive minimum 0 and exclusive maximum 100"
    )
    multiple_of_five: conint(multiple_of=5) = Field(
        description="Integer that must be multiple of 5"
    )

    # Float constraints
    temperature: confloat(ge=-273.15, le=1000.0) = Field(
        description="Temperature in Celsius with physical bounds"
    )
    percentage: confloat(ge=0.0, le=100.0) = Field(
        description="Percentage between 0 and 100 inclusive"
    )
    ratio: confloat(gt=0.0, lt=1.0) = Field(
        description="Ratio with exclusive bounds between 0 and 1"
    )
    step_value: confloat(multiple_of=0.25) = Field(
        description="Float that must be multiple of 0.25"
    )

    # Combined constraints
    even_between_10_and_100: conint(ge=10, le=100, multiple_of=2) = Field(
        description="Even number between 10 and 100"
    )
    quarter_percentage: confloat(ge=0.0, le=100.0, multiple_of=0.25) = Field(
        description="Percentage in quarter increments"
    )

    # Optional fields for testing null handling
    optional_age: Optional[conint(ge=0, le=150)] = None
    optional_temperature: Optional[confloat(ge=-273.15)] = None


# Create fixture for the dynamic model
@pytest.fixture
def dynamic_model():
    """Create dynamic model from the number properties schema."""
    schema = NumberPropertiesModel.model_json_schema()
    return json_schema_to_pydantic_model(schema, "DynamicNumberProperties")


# ============================================================================
# SUCCESS TEST CASES - INTEGER CONSTRAINTS
# ============================================================================

def test_valid_integer_minimum_maximum(dynamic_model):
    """Test integers within minimum and maximum bounds."""
    valid_data = {
        "age": 25,  # Between 0 and 150
        "score": 50,  # Between exclusive 0 and 100
        "multiple_of_five": 15,
        "temperature": 20.5,
        "percentage": 75.5,
        "ratio": 0.5,
        "step_value": 0.75,
        "even_between_10_and_100": 50,
        "quarter_percentage": 25.25
    }

    instance = dynamic_model.model_validate(valid_data)
    assert instance.age == 25
    assert instance.score == 50


def test_integer_boundary_values(dynamic_model):
    """Test integer values at boundaries."""
    # Test minimum boundary for age (inclusive)
    data1 = {
        "age": 0,  # Minimum inclusive
        "score": 1,  # Just above exclusive minimum
        "multiple_of_five": 0,
        "temperature": 20.0,
        "percentage": 50.0,
        "ratio": 0.5,
        "step_value": 0.25,
        "even_between_10_and_100": 10,
        "quarter_percentage": 0.0
    }
    instance = dynamic_model.model_validate(data1)
    assert instance.age == 0
    assert instance.even_between_10_and_100 == 10

    # Test maximum boundary for age (inclusive)
    data2 = {
        "age": 150,  # Maximum inclusive
        "score": 99,  # Just below exclusive maximum
        "multiple_of_five": 100,
        "temperature": 20.0,
        "percentage": 50.0,
        "ratio": 0.5,
        "step_value": 0.25,
        "even_between_10_and_100": 100,
        "quarter_percentage": 100.0
    }
    instance = dynamic_model.model_validate(data2)
    assert instance.age == 150
    assert instance.even_between_10_and_100 == 100


def test_multiple_of_constraint_integers(dynamic_model):
    """Test multipleOf constraint for integers."""
    valid_multiples_of_five = [0, 5, 10, 15, 20, 100, -5, -10]

    base_data = {
        "age": 30,
        "score": 50,
        "temperature": 20.0,
        "percentage": 50.0,
        "ratio": 0.5,
        "step_value": 0.5,
        "even_between_10_and_100": 20,
        "quarter_percentage": 50.0
    }

    for multiple in valid_multiples_of_five:
        data = {**base_data, "multiple_of_five": multiple}
        instance = dynamic_model.model_validate(data)
        assert instance.multiple_of_five == multiple


# ============================================================================
# SUCCESS TEST CASES - FLOAT CONSTRAINTS
# ============================================================================

def test_valid_float_minimum_maximum(dynamic_model):
    """Test floats within minimum and maximum bounds."""
    valid_data = {
        "age": 30,
        "score": 75,
        "multiple_of_five": 20,
        "temperature": -100.5,  # Between -273.15 and 1000
        "percentage": 99.99,  # Between 0 and 100
        "ratio": 0.618,  # Between exclusive 0 and 1
        "step_value": 1.25,
        "even_between_10_and_100": 50,
        "quarter_percentage": 75.75
    }

    instance = dynamic_model.model_validate(valid_data)
    assert instance.temperature == -100.5
    assert instance.percentage == 99.99
    assert instance.ratio == 0.618


def test_float_boundary_values(dynamic_model):
    """Test float values at boundaries."""
    # Test minimum boundary for temperature (inclusive)
    data1 = {
        "age": 30,
        "score": 50,
        "multiple_of_five": 10,
        "temperature": -273.15,  # Absolute zero
        "percentage": 0.0,  # Minimum inclusive
        "ratio": 0.001,  # Just above exclusive minimum
        "step_value": 0.0,
        "even_between_10_and_100": 20,
        "quarter_percentage": 0.0
    }
    instance = dynamic_model.model_validate(data1)
    assert instance.temperature == -273.15
    assert instance.percentage == 0.0

    # Test maximum boundary for temperature (inclusive)
    data2 = {
        "age": 30,
        "score": 50,
        "multiple_of_five": 10,
        "temperature": 1000.0,  # Maximum
        "percentage": 100.0,  # Maximum inclusive
        "ratio": 0.999,  # Just below exclusive maximum
        "step_value": 100.0,
        "even_between_10_and_100": 20,
        "quarter_percentage": 100.0
    }
    instance = dynamic_model.model_validate(data2)
    assert instance.temperature == 1000.0
    assert instance.percentage == 100.0


def test_multiple_of_constraint_floats(dynamic_model):
    """Test multipleOf constraint for floats."""
    valid_multiples_of_quarter = [0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 10.75, -0.25]

    base_data = {
        "age": 30,
        "score": 50,
        "multiple_of_five": 10,
        "temperature": 20.0,
        "percentage": 50.0,
        "ratio": 0.5,
        "even_between_10_and_100": 20,
        "quarter_percentage": 50.0
    }

    for multiple in valid_multiples_of_quarter:
        data = {**base_data, "step_value": multiple}
        instance = dynamic_model.model_validate(data)
        assert instance.step_value == multiple


def test_combined_constraints(dynamic_model):
    """Test fields with multiple constraints combined."""
    # Test even numbers between 10 and 100
    valid_even_numbers = [10, 12, 20, 50, 88, 100]

    base_data = {
        "age": 30,
        "score": 50,
        "multiple_of_five": 10,
        "temperature": 20.0,
        "percentage": 50.0,
        "ratio": 0.5,
        "step_value": 0.5,
        "even_between_10_and_100": 20,
        "quarter_percentage": 50.0
    }

    for even_num in valid_even_numbers:
        data = {**base_data, "even_between_10_and_100": even_num}
        instance = dynamic_model.model_validate(data)
        assert instance.even_between_10_and_100 == even_num

    # Test quarter percentages
    valid_quarters = [0.0, 0.25, 25.0, 50.25, 75.5, 99.75, 100.0]

    for quarter in valid_quarters:
        data = {**base_data, "quarter_percentage": quarter}
        instance = dynamic_model.model_validate(data)
        assert instance.quarter_percentage == quarter


# ============================================================================
# ERROR TEST CASES - INTEGER CONSTRAINTS
# ============================================================================

def test_invalid_integer_below_minimum(dynamic_model):
    """Test that integers below minimum are rejected."""
    invalid_data = {
        "age": -1,  # Below minimum 0
        "score": 50,
        "multiple_of_five": 10,
        "temperature": 20.0,
        "percentage": 50.0,
        "ratio": 0.5,
        "step_value": 0.5,
        "even_between_10_and_100": 20,
        "quarter_percentage": 50.0
    }

    with pytest.raises(ValidationError) as exc_info:
        dynamic_model.model_validate(invalid_data)
    print(f"\nValidation Error: {exc_info.value}")
    assert "age" in str(exc_info.value)


def test_invalid_integer_above_maximum(dynamic_model):
    """Test that integers above maximum are rejected."""
    invalid_data = {
        "age": 151,  # Above maximum 150
        "score": 50,
        "multiple_of_five": 10,
        "temperature": 20.0,
        "percentage": 50.0,
        "ratio": 0.5,
        "step_value": 0.5,
        "even_between_10_and_100": 20,
        "quarter_percentage": 50.0
    }

    with pytest.raises(ValidationError) as exc_info:
        dynamic_model.model_validate(invalid_data)
    print(f"\nValidation Error: {exc_info.value}")
    assert "age" in str(exc_info.value)


def test_invalid_exclusive_boundaries_integer(dynamic_model):
    """Test that exclusive boundaries are properly enforced for integers."""
    # Test exclusive minimum (score > 0)
    invalid_data1 = {
        "age": 30,
        "score": 0,  # Should be > 0
        "multiple_of_five": 10,
        "temperature": 20.0,
        "percentage": 50.0,
        "ratio": 0.5,
        "step_value": 0.5,
        "even_between_10_and_100": 20,
        "quarter_percentage": 50.0
    }

    with pytest.raises(ValidationError) as exc_info:
        dynamic_model.model_validate(invalid_data1)
    print(f"\nValidation Error: {exc_info.value}")
    assert "score" in str(exc_info.value)

    # Test exclusive maximum (score < 100)
    invalid_data2 = {
        "age": 30,
        "score": 100,  # Should be < 100
        "multiple_of_five": 10,
        "temperature": 20.0,
        "percentage": 50.0,
        "ratio": 0.5,
        "step_value": 0.5,
        "even_between_10_and_100": 20,
        "quarter_percentage": 50.0
    }

    with pytest.raises(ValidationError) as exc_info:
        dynamic_model.model_validate(invalid_data2)
    print(f"\nValidation Error: {exc_info.value}")
    assert "score" in str(exc_info.value)


def test_invalid_multiple_of_integer(dynamic_model):
    """Test that non-multiples are rejected for integers."""
    invalid_data = {
        "age": 30,
        "score": 50,
        "multiple_of_five": 7,  # Not a multiple of 5
        "temperature": 20.0,
        "percentage": 50.0,
        "ratio": 0.5,
        "step_value": 0.5,
        "even_between_10_and_100": 20,
        "quarter_percentage": 50.0
    }

    with pytest.raises(ValidationError) as exc_info:
        dynamic_model.model_validate(invalid_data)
    print(f"\nValidation Error: {exc_info.value}")
    assert "multiple_of_five" in str(exc_info.value)


# ============================================================================
# ERROR TEST CASES - FLOAT CONSTRAINTS
# ============================================================================

def test_invalid_float_below_minimum(dynamic_model):
    """Test that floats below minimum are rejected."""
    invalid_data = {
        "age": 30,
        "score": 50,
        "multiple_of_five": 10,
        "temperature": -300.0,  # Below absolute zero (-273.15)
        "percentage": 50.0,
        "ratio": 0.5,
        "step_value": 0.5,
        "even_between_10_and_100": 20,
        "quarter_percentage": 50.0
    }

    with pytest.raises(ValidationError) as exc_info:
        dynamic_model.model_validate(invalid_data)
    print(f"\nValidation Error: {exc_info.value}")
    assert "temperature" in str(exc_info.value)


def test_invalid_float_above_maximum(dynamic_model):
    """Test that floats above maximum are rejected."""
    invalid_data = {
        "age": 30,
        "score": 50,
        "multiple_of_five": 10,
        "temperature": 1001.0,  # Above maximum 1000
        "percentage": 50.0,
        "ratio": 0.5,
        "step_value": 0.5,
        "even_between_10_and_100": 20,
        "quarter_percentage": 50.0
    }

    with pytest.raises(ValidationError) as exc_info:
        dynamic_model.model_validate(invalid_data)
    print(f"\nValidation Error: {exc_info.value}")
    assert "temperature" in str(exc_info.value)


def test_invalid_exclusive_boundaries_float(dynamic_model):
    """Test that exclusive boundaries are properly enforced for floats."""
    # Test exclusive minimum (ratio > 0.0)
    invalid_data1 = {
        "age": 30,
        "score": 50,
        "multiple_of_five": 10,
        "temperature": 20.0,
        "percentage": 50.0,
        "ratio": 0.0,  # Should be > 0.0
        "step_value": 0.5,
        "even_between_10_and_100": 20,
        "quarter_percentage": 50.0
    }

    with pytest.raises(ValidationError) as exc_info:
        dynamic_model.model_validate(invalid_data1)
    print(f"\nValidation Error: {exc_info.value}")
    assert "ratio" in str(exc_info.value)

    # Test exclusive maximum (ratio < 1.0)
    invalid_data2 = {
        "age": 30,
        "score": 50,
        "multiple_of_five": 10,
        "temperature": 20.0,
        "percentage": 50.0,
        "ratio": 1.0,  # Should be < 1.0
        "step_value": 0.5,
        "even_between_10_and_100": 20,
        "quarter_percentage": 50.0
    }

    with pytest.raises(ValidationError) as exc_info:
        dynamic_model.model_validate(invalid_data2)
    print(f"\nValidation Error: {exc_info.value}")
    assert "ratio" in str(exc_info.value)


def test_invalid_multiple_of_float(dynamic_model):
    """Test that non-multiples are rejected for floats."""
    invalid_data = {
        "age": 30,
        "score": 50,
        "multiple_of_five": 10,
        "temperature": 20.0,
        "percentage": 50.0,
        "ratio": 0.5,
        "step_value": 0.33,  # Not a multiple of 0.25
        "even_between_10_and_100": 20,
        "quarter_percentage": 50.0
    }

    with pytest.raises(ValidationError) as exc_info:
        dynamic_model.model_validate(invalid_data)
    print(f"\nValidation Error: {exc_info.value}")
    assert "step_value" in str(exc_info.value)


def test_invalid_combined_constraints(dynamic_model):
    """Test that combined constraints are all enforced."""
    # Test odd number for even_between_10_and_100
    invalid_data1 = {
        "age": 30,
        "score": 50,
        "multiple_of_five": 10,
        "temperature": 20.0,
        "percentage": 50.0,
        "ratio": 0.5,
        "step_value": 0.5,
        "even_between_10_and_100": 11,  # Odd number
        "quarter_percentage": 50.0
    }

    with pytest.raises(ValidationError) as exc_info:
        dynamic_model.model_validate(invalid_data1)
    print(f"\nValidation Error: {exc_info.value}")
    assert "even_between_10_and_100" in str(exc_info.value)

    # Test out of range for even_between_10_and_100
    invalid_data2 = {
        "age": 30,
        "score": 50,
        "multiple_of_five": 10,
        "temperature": 20.0,
        "percentage": 50.0,
        "ratio": 0.5,
        "step_value": 0.5,
        "even_between_10_and_100": 102,  # Above 100
        "quarter_percentage": 50.0
    }

    with pytest.raises(ValidationError) as exc_info:
        dynamic_model.model_validate(invalid_data2)
    print(f"\nValidation Error: {exc_info.value}")
    assert "even_between_10_and_100" in str(exc_info.value)


# ============================================================================
# OPTIONAL FIELD TESTS
# ============================================================================

def test_optional_fields_with_none(dynamic_model):
    """Test that optional fields can be None."""
    valid_data = {
        "age": 30,
        "score": 50,
        "multiple_of_five": 10,
        "temperature": 20.0,
        "percentage": 50.0,
        "ratio": 0.5,
        "step_value": 0.5,
        "even_between_10_and_100": 20,
        "quarter_percentage": 50.0,
        "optional_age": None,
        "optional_temperature": None
    }

    instance = dynamic_model.model_validate(valid_data)
    assert instance.optional_age is None
    assert instance.optional_temperature is None


def test_optional_fields_with_valid_values(dynamic_model):
    """Test that optional fields can have valid values."""
    valid_data = {
        "age": 30,
        "score": 50,
        "multiple_of_five": 10,
        "temperature": 20.0,
        "percentage": 50.0,
        "ratio": 0.5,
        "step_value": 0.5,
        "even_between_10_and_100": 20,
        "quarter_percentage": 50.0,
        "optional_age": 65,
        "optional_temperature": 37.5
    }

    instance = dynamic_model.model_validate(valid_data)
    assert instance.optional_age == 65
    assert instance.optional_temperature == 37.5


def test_optional_fields_with_invalid_values(dynamic_model):
    """Test that optional fields still enforce constraints when provided."""
    # Test invalid age in optional field
    invalid_data = {
        "age": 30,
        "score": 50,
        "multiple_of_five": 10,
        "temperature": 20.0,
        "percentage": 50.0,
        "ratio": 0.5,
        "step_value": 0.5,
        "even_between_10_and_100": 20,
        "quarter_percentage": 50.0,
        "optional_age": 200,  # Above maximum
        "optional_temperature": 20.0
    }

    with pytest.raises(ValidationError) as exc_info:
        dynamic_model.model_validate(invalid_data)
    print(f"\nValidation Error: {exc_info.value}")
    assert "optional_age" in str(exc_info.value)


# ============================================================================
# EDGE CASES
# ============================================================================

def test_floating_point_precision(dynamic_model):
    """Test floating point precision edge cases."""
    valid_data = {
        "age": 30,
        "score": 50,
        "multiple_of_five": 10,
        "temperature": 999.9999999,  # Very close to maximum
        "percentage": 99.9999999,  # Very close to maximum
        "ratio": 0.9999999,  # Very close to exclusive maximum
        "step_value": 10.25,  # Large multiple of 0.25
        "even_between_10_and_100": 20,
        "quarter_percentage": 99.75
    }

    instance = dynamic_model.model_validate(valid_data)
    assert instance.temperature < 1000.0
    assert instance.percentage < 100.0 or instance.percentage == 100.0
    assert instance.ratio < 1.0


def test_negative_multiples(dynamic_model):
    """Test negative values with multipleOf constraint."""
    valid_data = {
        "age": 30,
        "score": 50,
        "multiple_of_five": -15,  # Negative multiple of 5
        "temperature": 20.0,
        "percentage": 50.0,
        "ratio": 0.5,
        "step_value": -1.25,  # Negative multiple of 0.25
        "even_between_10_and_100": 20,
        "quarter_percentage": 50.0
    }

    instance = dynamic_model.model_validate(valid_data)
    assert instance.multiple_of_five == -15
    assert instance.step_value == -1.25


if __name__ == "__main__":
    # Run tests with pytest
    # pytest test_openai_structured_output/test_number_properties.py -v -s
    pytest.main([__file__, "-v"])
