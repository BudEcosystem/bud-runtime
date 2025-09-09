"""
Test cases for all supported types in OpenAI Structured Output.
Tests: String, Number, Boolean, Integer, Object, Array, Enum, anyOf
"""

import sys
import os

import pytest
from pydantic import BaseModel, ValidationError
from typing import Optional, List, Union, Literal
from enum import Enum
from .dynamic_model_creation import json_schema_to_pydantic_model


# Define comprehensive model with all supported types
class Color(str, Enum):
    """String enum for testing."""
    RED = "red"
    GREEN = "green"
    BLUE = "blue"


class Priority(int, Enum):
    """Integer enum for testing."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3


class Address(BaseModel):
    """Nested object for testing."""
    street: str
    city: str
    zipcode: str


class UserProfile(BaseModel):
    """Alternative model for anyOf testing."""
    username: str
    age: int


class ComprehensiveTypesModel(BaseModel):
    """Model containing all supported OpenAI types."""
    # Basic types
    string_field: str
    number_field: float
    boolean_field: bool
    integer_field: int

    # Object type (nested model)
    object_field: Address

    # Array types
    array_field: List[str]
    integer_array: List[int]

    # Enum types
    string_enum: Color
    integer_enum: Priority

    # anyOf (Union type)
    any_of_field: Union[str, int]
    complex_any_of: Union[Address, UserProfile]

    # Optional fields for null testing
    optional_string: Optional[str] = None
    optional_object: Optional[Address] = None


# Create fixture for the dynamic model
@pytest.fixture
def dynamic_model():
    """Create dynamic model from the comprehensive schema."""
    schema = ComprehensiveTypesModel.model_json_schema()
    return json_schema_to_pydantic_model(schema, "DynamicComprehensiveTypes")


# ============================================================================
# SUCCESS TEST CASES
# ============================================================================

def test_all_valid_types(dynamic_model):
    """Test that all valid type values are accepted."""
    valid_data = {
        "string_field": "test string",
        "number_field": 3.14,
        "boolean_field": True,
        "integer_field": 42,
        "object_field": {
            "street": "123 Main St",
            "city": "Boston",
            "zipcode": "02101"
        },
        "array_field": ["item1", "item2", "item3"],
        "integer_array": [1, 2, 3, 4, 5],
        "string_enum": "red",
        "integer_enum": 2,
        "any_of_field": "string value",
        "complex_any_of": {
            "username": "john_doe",
            "age": 30
        },
        "optional_string": "optional value",
        "optional_object": {
            "street": "456 Oak Ave",
            "city": "New York",
            "zipcode": "10001"
        }
    }

    instance = dynamic_model.model_validate(valid_data)
    assert instance.string_field == "test string"
    assert instance.number_field == 3.14
    assert instance.boolean_field is True
    assert instance.integer_field == 42
    assert instance.string_enum == "red"
    assert instance.integer_enum == 2


def test_optional_fields_with_none(dynamic_model):
    """Test that optional fields can be None."""
    valid_data = {
        "string_field": "test",
        "number_field": 1.0,
        "boolean_field": False,
        "integer_field": 1,
        "object_field": {"street": "123 St", "city": "City", "zipcode": "12345"},
        "array_field": ["test"],
        "integer_array": [1],
        "string_enum": "blue",
        "integer_enum": 1,
        "any_of_field": 42,
        "complex_any_of": {"street": "St", "city": "City", "zipcode": "12345"},
        "optional_string": None,
        "optional_object": None
    }

    instance = dynamic_model.model_validate(valid_data)
    assert instance.optional_string is None
    assert instance.optional_object is None


def test_any_of_alternative_types(dynamic_model):
    """Test anyOf field with different valid types."""
    # Test with string
    data_with_string = {
        "string_field": "test",
        "number_field": 1.0,
        "boolean_field": True,
        "integer_field": 1,
        "object_field": {"street": "St", "city": "City", "zipcode": "12345"},
        "array_field": ["test"],
        "integer_array": [1],
        "string_enum": "green",
        "integer_enum": 3,
        "any_of_field": "string value",
        "complex_any_of": {"street": "St", "city": "City", "zipcode": "12345"}
    }

    instance = dynamic_model.model_validate(data_with_string)
    assert instance.any_of_field == "string value"

    # Test with integer
    data_with_integer = {**data_with_string, "any_of_field": 999}
    instance = dynamic_model.model_validate(data_with_integer)
    assert instance.any_of_field == 999


def test_empty_arrays(dynamic_model):
    """Test that empty arrays are valid when allowed."""
    valid_data = {
        "string_field": "test",
        "number_field": 1.0,
        "boolean_field": True,
        "integer_field": 1,
        "object_field": {"street": "St", "city": "City", "zipcode": "12345"},
        "array_field": [],  # Empty array
        "integer_array": [],  # Empty array
        "string_enum": "red",
        "integer_enum": 1,
        "any_of_field": 1,
        "complex_any_of": {"username": "user", "age": 25}
    }

    instance = dynamic_model.model_validate(valid_data)
    assert instance.array_field == []
    assert instance.integer_array == []


# ============================================================================
# ERROR TEST CASES
# ============================================================================

def test_invalid_string_type(dynamic_model):
    """Test that invalid string type raises validation error."""
    invalid_data = {
        "string_field": 123,  # Should be string
        "number_field": 1.0,
        "boolean_field": True,
        "integer_field": 1,
        "object_field": {"street": "St", "city": "City", "zipcode": "12345"},
        "array_field": ["test"],
        "integer_array": [1],
        "string_enum": "red",
        "integer_enum": 1,
        "any_of_field": 1,
        "complex_any_of": {"username": "user", "age": 25}
    }

    with pytest.raises(ValidationError) as exc_info:
        dynamic_model.model_validate(invalid_data)
    print(f"\nValidation Error: {exc_info.value}")
    assert "string_field" in str(exc_info.value)

def test_invalid_number_type(dynamic_model):
    """Test that invalid string type raises validation error."""
    invalid_data = {
        "string_field": "string",
        "number_field": "1z",  # Should be float
        "boolean_field": True,
        "integer_field": 1,
        "object_field": {"street": "St", "city": "City", "zipcode": "12345"},
        "array_field": ["test"],
        "integer_array": [1],
        "string_enum": "red",
        "integer_enum": 1,
        "any_of_field": 1,
        "complex_any_of": {"username": "user", "age": 25}
    }

    with pytest.raises(ValidationError) as exc_info:
        dynamic_model.model_validate(invalid_data)
    print(f"\nValidation Error: {exc_info.value}")
    assert "number_field" in str(exc_info.value)


def test_invalid_boolean_type(dynamic_model):
    """Test that invalid boolean type raises validation error."""
    invalid_data = {
        "string_field": "test",
        "number_field": 1.0,
        "boolean_field": "trues",  # Should be boolean, not string
        "integer_field": 1,
        "object_field": {"street": "St", "city": "City", "zipcode": "12345"},
        "array_field": ["test"],
        "integer_array": [1],
        "string_enum": "red",
        "integer_enum": 1,
        "any_of_field": 1,
        "complex_any_of": {"username": "user", "age": 25}
    }

    with pytest.raises(ValidationError) as exc_info:
        dynamic_model.model_validate(invalid_data)
    print(f"\nValidation Error: {exc_info.value}")
    assert "boolean_field" in str(exc_info.value)


def test_invalid_integer_type(dynamic_model):
    """Test that invalid integer type raises validation error."""
    invalid_data = {
        "string_field": "test",
        "number_field": 1.0,
        "boolean_field": True,
        "integer_field": "42z",  # Should be integer, not string
        "object_field": {"street": "St", "city": "City", "zipcode": "12345"},
        "array_field": ["test"],
        "integer_array": [1],
        "string_enum": "red",
        "integer_enum": 1,
        "any_of_field": 1,
        "complex_any_of": {"username": "user", "age": 25}
    }

    with pytest.raises(ValidationError) as exc_info:
        dynamic_model.model_validate(invalid_data)
    print(f"\nValidation Error: {exc_info.value}")
    assert "integer_field" in str(exc_info.value)


def test_invalid_enum_value(dynamic_model):
    """Test that invalid enum values raise validation error."""
    invalid_data = {
        "string_field": "test",
        "number_field": 1.0,
        "boolean_field": True,
        "integer_field": 1,
        "object_field": {"street": "St", "city": "City", "zipcode": "12345"},
        "array_field": ["test"],
        "integer_array": [1],
        "string_enum": "yellow",  # Invalid enum value
        "integer_enum": 1,
        "any_of_field": 1,
        "complex_any_of": {"username": "user", "age": 25}
    }

    with pytest.raises(ValidationError) as exc_info:
        dynamic_model.model_validate(invalid_data)
    print(f"\nValidation Error: {exc_info.value}")
    assert "string_enum" in str(exc_info.value)


def test_invalid_integer_enum_value(dynamic_model):
    """Test that invalid integer enum values raise validation error."""
    invalid_data = {
        "string_field": "test",
        "number_field": 1.0,
        "boolean_field": True,
        "integer_field": 1,
        "object_field": {"street": "St", "city": "City", "zipcode": "12345"},
        "array_field": ["test"],
        "integer_array": [1],
        "string_enum": "red",
        "integer_enum": 5,  # Invalid enum value (only 1, 2, 3 are valid)
        "any_of_field": 1,
        "complex_any_of": {"username": "user", "age": 25}
    }

    with pytest.raises(ValidationError) as exc_info:
        dynamic_model.model_validate(invalid_data)
    print(f"\nValidation Error: {exc_info.value}")
    assert "integer_enum" in str(exc_info.value)


def test_invalid_object_structure(dynamic_model):
    """Test that invalid object structure raises validation error."""
    invalid_data = {
        "string_field": "test",
        "number_field": 1.0,
        "boolean_field": True,
        "integer_field": 1,
        "object_field": {
            "street": "St",
            "city": "City"
            # Missing required 'zipcode' field
        },
        "array_field": ["test"],
        "integer_array": [1],
        "string_enum": "red",
        "integer_enum": 1,
        "any_of_field": 1,
        "complex_any_of": {"username": "user", "age": 25}
    }

    with pytest.raises(ValidationError) as exc_info:
        dynamic_model.model_validate(invalid_data)
    print(f"\nValidation Error: {exc_info.value}")
    assert "zipcode" in str(exc_info.value)


def test_invalid_array_item_type(dynamic_model):
    """Test that arrays with wrong item types raise validation error."""
    invalid_data = {
        "string_field": "test",
        "number_field": 1.0,
        "boolean_field": True,
        "integer_field": 1,
        "object_field": {"street": "St", "city": "City", "zipcode": "12345"},
        "array_field": ["valid", 123, "string"],  # Contains integer in string array
        "integer_array": [1],
        "string_enum": "red",
        "integer_enum": 1,
        "any_of_field": 1,
        "complex_any_of": {"username": "user", "age": 25}
    }

    with pytest.raises(ValidationError) as exc_info:
        dynamic_model.model_validate(invalid_data)
    print(f"\nValidation Error: {exc_info.value}")
    assert "array_field" in str(exc_info.value)


def test_missing_required_field(dynamic_model):
    """Test that missing required fields raise validation error."""
    invalid_data = {
        # Missing string_field
        "number_field": 1.0,
        "boolean_field": True,
        "integer_field": 1,
        "object_field": {"street": "St", "city": "City", "zipcode": "12345"},
        "array_field": ["test"],
        "integer_array": [1],
        "string_enum": "red",
        "integer_enum": 1,
        "any_of_field": 1,
        "complex_any_of": {"username": "user", "age": 25}
    }

    with pytest.raises(ValidationError) as exc_info:
        dynamic_model.model_validate(invalid_data)
    print(f"\nValidation Error: {exc_info.value}")
    assert "string_field" in str(exc_info.value)


def test_invalid_any_of_type(dynamic_model):
    """Test that invalid anyOf types raise validation error."""
    invalid_data = {
        "string_field": "test",
        "number_field": 1.0,
        "boolean_field": True,
        "integer_field": 1,
        "object_field": {"street": "St", "city": "City", "zipcode": "12345"},
        "array_field": ["test"],
        "integer_array": [1],
        "string_enum": "red",
        "integer_enum": 1,
        "any_of_field": [1, 2, 3],  # Should be string or int, not list
        "complex_any_of": {"username": "user", "age": 25}
    }

    with pytest.raises(ValidationError) as exc_info:
        dynamic_model.model_validate(invalid_data)
    print(f"\nValidation Error: {exc_info.value}")
    assert "any_of_field" in str(exc_info.value)


def test_invalid_integer_array_item_type(dynamic_model):
    """Test that integer arrays with wrong item types raise validation error."""
    invalid_data = {
        "string_field": "test",
        "number_field": 1.0,
        "boolean_field": True,
        "integer_field": 1,
        "object_field": {"street": "St", "city": "City", "zipcode": "12345"},
        "array_field": ["test"],
        "integer_array": [1, "two", 3],  # Contains string in integer array
        "string_enum": "red",
        "integer_enum": 1,
        "any_of_field": 1,
        "complex_any_of": {"username": "user", "age": 25}
    }

    with pytest.raises(ValidationError) as exc_info:
        dynamic_model.model_validate(invalid_data)
    print(f"\nValidation Error: {exc_info.value}")
    assert "integer_array" in str(exc_info.value)


def test_invalid_complex_any_of_type(dynamic_model):
    """Test that complex_any_of rejects invalid union types."""
    invalid_data = {
        "string_field": "test",
        "number_field": 1.0,
        "boolean_field": True,
        "integer_field": 1,
        "object_field": {"street": "St", "city": "City", "zipcode": "12345"},
        "array_field": ["test"],
        "integer_array": [1],
        "string_enum": "red",
        "integer_enum": 1,
        "any_of_field": 1,
        "complex_any_of": {"invalid_field": "value"}  # Neither Address nor UserProfile
    }

    with pytest.raises(ValidationError) as exc_info:
        dynamic_model.model_validate(invalid_data)
    print(f"\nValidation Error: {exc_info.value}")
    assert "complex_any_of" in str(exc_info.value)


def test_invalid_optional_string_type(dynamic_model):
    """Test that optional_string rejects non-string values when provided."""
    invalid_data = {
        "string_field": "test",
        "number_field": 1.0,
        "boolean_field": True,
        "integer_field": 1,
        "object_field": {"street": "St", "city": "City", "zipcode": "12345"},
        "array_field": ["test"],
        "integer_array": [1],
        "string_enum": "red",
        "integer_enum": 1,
        "any_of_field": 1,
        "complex_any_of": {"username": "user", "age": 25},
        "optional_string": 123,  # Should be string or None, not integer
        "optional_object": None
    }

    with pytest.raises(ValidationError) as exc_info:
        dynamic_model.model_validate(invalid_data)
    assert "optional_string" in str(exc_info.value)


def test_invalid_optional_object_structure(dynamic_model):
    """Test that optional_object rejects invalid Address structure when provided."""
    invalid_data = {
        "string_field": "test",
        "number_field": 1.0,
        "boolean_field": True,
        "integer_field": 1,
        "object_field": {"street": "St", "city": "City", "zipcode": "12345"},
        "array_field": ["test"],
        "integer_array": [1],
        "string_enum": "red",
        "integer_enum": 1,
        "any_of_field": 1,
        "complex_any_of": {"username": "user", "age": 25},
        "optional_string": None,
        "optional_object": {"street": "St", "city": "City"}  # Missing zipcode
    }

    with pytest.raises(ValidationError) as exc_info:
        dynamic_model.model_validate(invalid_data)
    assert "optional_object" in str(exc_info.value) or "zipcode" in str(exc_info.value)


# ============================================================================
# EDGE CASES
# ============================================================================

def test_float_as_integer(dynamic_model):
    """Test that float values for integer fields are handled correctly."""
    data = {
        "string_field": "test",
        "number_field": 1.0,
        "boolean_field": True,
        "integer_field": 42.0,  # Float that can be converted to int
        "object_field": {"street": "St", "city": "City", "zipcode": "12345"},
        "array_field": ["test"],
        "integer_array": [1],
        "string_enum": "red",
        "integer_enum": 1,
        "any_of_field": 1,
        "complex_any_of": {"username": "user", "age": 25}
    }

    instance = dynamic_model.model_validate(data)
    assert instance.integer_field == 42


def test_numeric_string_coercion(dynamic_model):
    """Test that numeric strings are not automatically coerced."""
    invalid_data = {
        "string_field": "test",
        "number_field": "3.14s",  # String that looks like number
        "boolean_field": True,
        "integer_field": 1,
        "object_field": {"street": "St", "city": "City", "zipcode": "12345"},
        "array_field": ["test"],
        "integer_array": [1],
        "string_enum": "red",
        "integer_enum": 1,
        "any_of_field": 1,
        "complex_any_of": {"username": "user", "age": 25}
    }

    with pytest.raises(ValidationError) as exc_info:
        dynamic_model.model_validate(invalid_data)
    print(f"\nValidation Error: {exc_info.value}")
    assert "number_field" in str(exc_info.value)


if __name__ == "__main__":
    # Run tests with pytest
    # pytest test_openai_structured_output/test_supported_types.py -v -s
    pytest.main([__file__, "-v"])
