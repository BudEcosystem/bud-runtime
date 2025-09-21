"""
Test cases for array properties in OpenAI Structured Output.
Tests: minItems, maxItems constraints for arrays
"""

import sys
import os
# Add both parent directory and current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from pydantic import BaseModel, Field, ValidationError, conlist
from typing import List, Optional, Set
from .dynamic_model_creation import json_schema_to_pydantic_model


class Tag(BaseModel):
    """Nested model for testing arrays of objects."""
    name: str
    value: str


class ArrayPropertiesModel(BaseModel):
    """Model containing all array constraint types."""

    # Basic array constraints
    tags: conlist(str, min_length=1, max_length=10) = Field(
        description="Array of tags with min 1 and max 10 items"
    )

    # Array with exact length
    coordinates: conlist(float, min_length=2, max_length=2) = Field(
        description="Array with exactly 2 coordinates (lat, lon)"
    )

    # Array with only minimum
    items: conlist(str, min_length=3) = Field(
        description="Array with at least 3 items"
    )

    # Array with only maximum
    top_five: conlist(int, max_length=5) = Field(
        description="Array with at most 5 items"
    )

    # Arrays of different types
    numbers: conlist(float, min_length=1, max_length=100) = Field(
        description="Array of numbers"
    )

    booleans: conlist(bool, min_length=1, max_length=3) = Field(
        description="Array of booleans"
    )

    # Array of objects
    metadata: conlist(Tag, min_length=0, max_length=5) = Field(
        description="Array of tag objects"
    )

    # Nested arrays
    matrix: conlist(
        conlist(int, min_length=2, max_length=2),
        min_length=2,
        max_length=3
    ) = Field(
        description="2D matrix with 2-3 rows, each with exactly 2 columns"
    )

    # Arrays without constraints (for comparison)
    unconstrained_array: List[str] = Field(
        description="Array without size constraints"
    )

    # Optional arrays
    optional_tags: Optional[conlist(str, min_length=1, max_length=5)] = None
    optional_empty_allowed: Optional[conlist(str, min_length=0)] = None


# Create fixture for the dynamic model
@pytest.fixture
def dynamic_model():
    """Create dynamic model from the array properties schema."""
    schema = ArrayPropertiesModel.model_json_schema()
    return json_schema_to_pydantic_model(schema, "DynamicArrayProperties")


# ============================================================================
# SUCCESS TEST CASES - BASIC CONSTRAINTS
# ============================================================================

def test_valid_array_within_bounds(dynamic_model):
    """Test arrays within min and max bounds."""
    valid_data = {
        "tags": ["tag1", "tag2", "tag3"],  # Between 1 and 10
        "coordinates": [40.7128, -74.0060],  # Exactly 2
        "items": ["item1", "item2", "item3", "item4"],  # At least 3
        "top_five": [1, 2, 3],  # At most 5
        "numbers": [1.0, 2.5, 3.14],
        "booleans": [True, False],
        "metadata": [{"name": "key1", "value": "val1"}],
        "matrix": [[1, 2], [3, 4]],
        "unconstrained_array": ["a", "b", "c"]
    }

    instance = dynamic_model.model_validate(valid_data)
    assert len(instance.tags) == 3
    assert len(instance.coordinates) == 2
    assert len(instance.items) == 4


def test_minimum_items_boundary(dynamic_model):
    """Test arrays at minimum boundary."""
    valid_data = {
        "tags": ["single"],  # Minimum 1 item
        "coordinates": [0.0, 0.0],  # Exactly 2 (min and max)
        "items": ["a", "b", "c"],  # Minimum 3 items
        "top_five": [],  # No minimum constraint
        "numbers": [42.0],  # Minimum 1
        "booleans": [True],  # Minimum 1
        "metadata": [],  # Minimum 0 (empty allowed)
        "matrix": [[1, 2], [3, 4]],  # Minimum 2 rows
        "unconstrained_array": []
    }

    instance = dynamic_model.model_validate(valid_data)
    assert len(instance.tags) == 1
    assert len(instance.items) == 3
    assert len(instance.metadata) == 0


def test_maximum_items_boundary(dynamic_model):
    """Test arrays at maximum boundary."""
    valid_data = {
        "tags": ["t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8", "t9", "t10"],  # Maximum 10
        "coordinates": [1.0, 2.0],  # Exactly 2
        "items": ["a", "b", "c", "d", "e", "f"],  # No maximum
        "top_five": [1, 2, 3, 4, 5],  # Maximum 5
        "numbers": [float(i) for i in range(100)],  # Maximum 100
        "booleans": [True, False, True],  # Maximum 3
        "metadata": [
            {"name": "k1", "value": "v1"},
            {"name": "k2", "value": "v2"},
            {"name": "k3", "value": "v3"},
            {"name": "k4", "value": "v4"},
            {"name": "k5", "value": "v5"}
        ],  # Maximum 5
        "matrix": [[1, 2], [3, 4], [5, 6]],  # Maximum 3 rows
        "unconstrained_array": ["x" * 100 for _ in range(1000)]  # No limit
    }

    instance = dynamic_model.model_validate(valid_data)
    assert len(instance.tags) == 10
    assert len(instance.top_five) == 5
    assert len(instance.metadata) == 5


# ============================================================================
# SUCCESS TEST CASES - COMPLEX ARRAYS
# ============================================================================

def test_array_of_objects(dynamic_model):
    """Test arrays containing objects."""
    valid_data = {
        "tags": ["tag1"],
        "coordinates": [0.0, 0.0],
        "items": ["a", "b", "c"],
        "top_five": [1],
        "numbers": [1.0],
        "booleans": [True],
        "metadata": [
            {"name": "author", "value": "John Doe"},
            {"name": "version", "value": "1.0.0"},
            {"name": "date", "value": "2024-01-01"}
        ],
        "matrix": [[1, 2], [3, 4]],
        "unconstrained_array": []
    }

    instance = dynamic_model.model_validate(valid_data)
    assert len(instance.metadata) == 3
    assert instance.metadata[0]["name"] == "author" if isinstance(instance.metadata[0], dict) else instance.metadata[0].name == "author"


def test_nested_arrays(dynamic_model):
    """Test nested array structures."""
    valid_data = {
        "tags": ["tag1"],
        "coordinates": [0.0, 0.0],
        "items": ["a", "b", "c"],
        "top_five": [1],
        "numbers": [1.0],
        "booleans": [True],
        "metadata": [],
        "matrix": [
            [10, 20],
            [30, 40],
            [50, 60]
        ],  # 3 rows (max), each with 2 columns (exact)
        "unconstrained_array": []
    }

    instance = dynamic_model.model_validate(valid_data)
    assert len(instance.matrix) == 3
    assert all(len(row) == 2 for row in instance.matrix)
    assert instance.matrix[0][0] == 10


def test_empty_arrays_where_allowed(dynamic_model):
    """Test that empty arrays are accepted where min_length=0 or unspecified."""
    valid_data = {
        "tags": ["required"],  # Can't be empty (min=1)
        "coordinates": [0.0, 0.0],  # Must have exactly 2
        "items": ["a", "b", "c"],  # Must have at least 3
        "top_five": [],  # Can be empty (no min constraint)
        "numbers": [1.0],  # Can't be empty (min=1)
        "booleans": [True],  # Can't be empty (min=1)
        "metadata": [],  # Can be empty (min=0)
        "matrix": [[1, 2], [3, 4]],  # Can't be empty (min=2)
        "unconstrained_array": []  # Can be empty (no constraints)
    }

    instance = dynamic_model.model_validate(valid_data)
    assert len(instance.top_five) == 0
    assert len(instance.metadata) == 0
    assert len(instance.unconstrained_array) == 0


# ============================================================================
# ERROR TEST CASES - MINIMUM VIOLATIONS
# ============================================================================

def test_below_minimum_items(dynamic_model):
    """Test that arrays below minimum items are rejected."""
    invalid_data = {
        "tags": [],  # Below minimum 1
        "coordinates": [0.0, 0.0],
        "items": ["a", "b", "c"],
        "top_five": [1],
        "numbers": [1.0],
        "booleans": [True],
        "metadata": [],
        "matrix": [[1, 2], [3, 4]],
        "unconstrained_array": []
    }

    with pytest.raises(ValidationError) as exc_info:
        dynamic_model.model_validate(invalid_data)
    assert "tags" in str(exc_info.value)


def test_coordinates_too_few(dynamic_model):
    """Test that coordinates with too few items are rejected."""
    invalid_data = {
        "tags": ["tag"],
        "coordinates": [0.0],  # Below minimum 2
        "items": ["a", "b", "c"],
        "top_five": [1],
        "numbers": [1.0],
        "booleans": [True],
        "metadata": [],
        "matrix": [[1, 2], [3, 4]],
        "unconstrained_array": []
    }

    with pytest.raises(ValidationError) as exc_info:
        dynamic_model.model_validate(invalid_data)
    assert "coordinates" in str(exc_info.value)


def test_items_too_few(dynamic_model):
    """Test that items with too few elements are rejected."""
    invalid_data = {
        "tags": ["tag"],
        "coordinates": [0.0, 0.0],
        "items": ["a", "b"],  # Below minimum 3
        "top_five": [1],
        "numbers": [1.0],
        "booleans": [True],
        "metadata": [],
        "matrix": [[1, 2], [3, 4]],
        "unconstrained_array": []
    }

    with pytest.raises(ValidationError) as exc_info:
        dynamic_model.model_validate(invalid_data)
    assert "items" in str(exc_info.value)


def test_matrix_too_few_rows(dynamic_model):
    """Test that matrix with too few rows is rejected."""
    invalid_data = {
        "tags": ["tag"],
        "coordinates": [0.0, 0.0],
        "items": ["a", "b", "c"],
        "top_five": [1],
        "numbers": [1.0],
        "booleans": [True],
        "metadata": [],
        "matrix": [[1, 2]],  # Below minimum 2 rows
        "unconstrained_array": []
    }

    with pytest.raises(ValidationError) as exc_info:
        dynamic_model.model_validate(invalid_data)
    assert "matrix" in str(exc_info.value)


# ============================================================================
# ERROR TEST CASES - MAXIMUM VIOLATIONS
# ============================================================================

def test_above_maximum_items(dynamic_model):
    """Test that arrays above maximum items are rejected."""
    invalid_data = {
        "tags": [f"tag{i}" for i in range(11)],  # Above maximum 10
        "coordinates": [0.0, 0.0],
        "items": ["a", "b", "c"],
        "top_five": [1],
        "numbers": [1.0],
        "booleans": [True],
        "metadata": [],
        "matrix": [[1, 2], [3, 4]],
        "unconstrained_array": []
    }

    with pytest.raises(ValidationError) as exc_info:
        dynamic_model.model_validate(invalid_data)
    assert "tags" in str(exc_info.value)


def test_coordinates_too_many(dynamic_model):
    """Test that coordinates with too many items are rejected."""
    invalid_data = {
        "tags": ["tag"],
        "coordinates": [0.0, 0.0, 0.0],  # Above maximum 2
        "items": ["a", "b", "c"],
        "top_five": [1],
        "numbers": [1.0],
        "booleans": [True],
        "metadata": [],
        "matrix": [[1, 2], [3, 4]],
        "unconstrained_array": []
    }

    with pytest.raises(ValidationError) as exc_info:
        dynamic_model.model_validate(invalid_data)
    assert "coordinates" in str(exc_info.value)


def test_top_five_too_many(dynamic_model):
    """Test that top_five with too many items is rejected."""
    invalid_data = {
        "tags": ["tag"],
        "coordinates": [0.0, 0.0],
        "items": ["a", "b", "c"],
        "top_five": [1, 2, 3, 4, 5, 6],  # Above maximum 5
        "numbers": [1.0],
        "booleans": [True],
        "metadata": [],
        "matrix": [[1, 2], [3, 4]],
        "unconstrained_array": []
    }

    with pytest.raises(ValidationError) as exc_info:
        dynamic_model.model_validate(invalid_data)
    assert "top_five" in str(exc_info.value)


def test_matrix_too_many_rows(dynamic_model):
    """Test that matrix with too many rows is rejected."""
    invalid_data = {
        "tags": ["tag"],
        "coordinates": [0.0, 0.0],
        "items": ["a", "b", "c"],
        "top_five": [1],
        "numbers": [1.0],
        "booleans": [True],
        "metadata": [],
        "matrix": [[1, 2], [3, 4], [5, 6], [7, 8]],  # Above maximum 3 rows
        "unconstrained_array": []
    }

    with pytest.raises(ValidationError) as exc_info:
        dynamic_model.model_validate(invalid_data)
    assert "matrix" in str(exc_info.value)


def test_matrix_wrong_column_count(dynamic_model):
    """Test that matrix rows with wrong column count are rejected."""
    invalid_data = {
        "tags": ["tag"],
        "coordinates": [0.0, 0.0],
        "items": ["a", "b", "c"],
        "top_five": [1],
        "numbers": [1.0],
        "booleans": [True],
        "metadata": [],
        "matrix": [[1, 2, 3], [4, 5]],  # First row has 3 columns instead of 2
        "unconstrained_array": []
    }

    with pytest.raises(ValidationError) as exc_info:
        dynamic_model.model_validate(invalid_data)
    assert "matrix" in str(exc_info.value)


# ============================================================================
# ERROR TEST CASES - TYPE VIOLATIONS
# ============================================================================

def test_wrong_item_type_in_array(dynamic_model):
    """Test that arrays with wrong item types are rejected."""
    invalid_data = {
        "tags": ["tag1", 123, "tag3"],  # Contains integer in string array
        "coordinates": [0.0, 0.0],
        "items": ["a", "b", "c"],
        "top_five": [1],
        "numbers": [1.0],
        "booleans": [True],
        "metadata": [],
        "matrix": [[1, 2], [3, 4]],
        "unconstrained_array": []
    }

    with pytest.raises(ValidationError) as exc_info:
        dynamic_model.model_validate(invalid_data)
    assert "tags" in str(exc_info.value)


def test_wrong_object_structure_in_array(dynamic_model):
    """Test that arrays with wrong object structure are rejected."""
    invalid_data = {
        "tags": ["tag"],
        "coordinates": [0.0, 0.0],
        "items": ["a", "b", "c"],
        "top_five": [1],
        "numbers": [1.0],
        "booleans": [True],
        "metadata": [
            {"name": "key1", "value": "val1"},
            {"name": "key2"},  # Missing 'value' field
        ],
        "matrix": [[1, 2], [3, 4]],
        "unconstrained_array": []
    }

    with pytest.raises(ValidationError) as exc_info:
        dynamic_model.model_validate(invalid_data)
    assert "metadata" in str(exc_info.value) or "value" in str(exc_info.value)


# ============================================================================
# OPTIONAL FIELD TESTS
# ============================================================================

def test_optional_arrays_with_none(dynamic_model):
    """Test that optional arrays can be None."""
    valid_data = {
        "tags": ["tag"],
        "coordinates": [0.0, 0.0],
        "items": ["a", "b", "c"],
        "top_five": [1],
        "numbers": [1.0],
        "booleans": [True],
        "metadata": [],
        "matrix": [[1, 2], [3, 4]],
        "unconstrained_array": [],
        "optional_tags": None,
        "optional_empty_allowed": None
    }

    instance = dynamic_model.model_validate(valid_data)
    assert instance.optional_tags is None
    assert instance.optional_empty_allowed is None


def test_optional_arrays_with_valid_values(dynamic_model):
    """Test that optional arrays can have valid values."""
    valid_data = {
        "tags": ["tag"],
        "coordinates": [0.0, 0.0],
        "items": ["a", "b", "c"],
        "top_five": [1],
        "numbers": [1.0],
        "booleans": [True],
        "metadata": [],
        "matrix": [[1, 2], [3, 4]],
        "unconstrained_array": [],
        "optional_tags": ["opt1", "opt2"],
        "optional_empty_allowed": []
    }

    instance = dynamic_model.model_validate(valid_data)
    assert len(instance.optional_tags) == 2
    assert len(instance.optional_empty_allowed) == 0


def test_optional_arrays_still_enforce_constraints(dynamic_model):
    """Test that optional arrays still enforce constraints when provided."""
    # Test too many items in optional array
    invalid_data = {
        "tags": ["tag"],
        "coordinates": [0.0, 0.0],
        "items": ["a", "b", "c"],
        "top_five": [1],
        "numbers": [1.0],
        "booleans": [True],
        "metadata": [],
        "matrix": [[1, 2], [3, 4]],
        "unconstrained_array": [],
        "optional_tags": ["t1", "t2", "t3", "t4", "t5", "t6"],  # Above max 5
        "optional_empty_allowed": []
    }

    with pytest.raises(ValidationError) as exc_info:
        dynamic_model.model_validate(invalid_data)
    assert "optional_tags" in str(exc_info.value)


# ============================================================================
# EDGE CASES
# ============================================================================

def test_large_unconstrained_array(dynamic_model):
    """Test that unconstrained arrays can be very large."""
    valid_data = {
        "tags": ["tag"],
        "coordinates": [0.0, 0.0],
        "items": ["a", "b", "c"],
        "top_five": [1],
        "numbers": [1.0],
        "booleans": [True],
        "metadata": [],
        "matrix": [[1, 2], [3, 4]],
        "unconstrained_array": [f"item{i}" for i in range(10000)]  # Very large array
    }

    instance = dynamic_model.model_validate(valid_data)
    assert len(instance.unconstrained_array) == 10000


def test_arrays_with_duplicate_values(dynamic_model):
    """Test that arrays can contain duplicate values."""
    valid_data = {
        "tags": ["dup", "dup", "dup"],  # Duplicates allowed
        "coordinates": [0.0, 0.0],  # Same values allowed
        "items": ["same", "same", "same"],
        "top_five": [1, 1, 1, 1],
        "numbers": [3.14, 3.14, 3.14],
        "booleans": [True, True, True],
        "metadata": [
            {"name": "key", "value": "val"},
            {"name": "key", "value": "val"}  # Duplicate objects
        ],
        "matrix": [[1, 1], [1, 1]],
        "unconstrained_array": ["x"] * 100
    }

    instance = dynamic_model.model_validate(valid_data)
    assert all(tag == "dup" for tag in instance.tags)
    assert all(val == 1 for val in instance.top_five)


def test_mixed_numeric_types_in_number_array(dynamic_model):
    """Test that mixed numeric types are handled correctly."""
    valid_data = {
        "tags": ["tag"],
        "coordinates": [40, -74.0],  # Mix of int and float
        "items": ["a", "b", "c"],
        "top_five": [1, 2, 3],
        "numbers": [1, 2.5, 3.0, 4],  # Mix of int and float
        "booleans": [True],
        "metadata": [],
        "matrix": [[1, 2], [3, 4]],
        "unconstrained_array": []
    }

    instance = dynamic_model.model_validate(valid_data)
    assert instance.coordinates[0] == 40
    assert instance.coordinates[1] == -74.0
    assert 2.5 in instance.numbers


if __name__ == "__main__":
    # Run tests with pytest
    # pytest test_openai_structured_output/test_array_properties.py -v -s
    pytest.main([__file__, "-v"])
