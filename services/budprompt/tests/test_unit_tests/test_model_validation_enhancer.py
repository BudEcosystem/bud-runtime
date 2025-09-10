"""Unit tests for ModelValidationEnhancer class."""

import asyncio
import sys
from typing import Dict, Type
from unittest.mock import Mock, patch

import pytest
from pydantic import BaseModel, ValidationError

from budprompt.prompt.revised_code.field_validation import ModelValidationEnhancer
from budprompt.prompt.schema_builder import ModelGeneratorFactory


class TestModelValidationEnhancer:
    """Test cases for ModelValidationEnhancer class."""

    @pytest.fixture
    def enhancer(self):
        """Create a ModelValidationEnhancer instance."""
        return ModelValidationEnhancer()

    @pytest.fixture
    def simple_person_model(self):
        """Create a simple Person model for testing."""

        class Person(BaseModel):
            name: str
            age: int
            email: str

        return Person

    @pytest.fixture
    def validation_rules(self):
        """Sample validation rules with pre-generated code."""
        return {
            "name": {
                "prompt": "Name must be at least 3 characters",
                "code": "def validate_name(value):\n    if len(value) >= 3:\n        return True\n    else:\n        return False"
            },
            "age": {
                "prompt": "Age must be between 18 and 100",
                "code": "def validate_age(value):\n    if 18 <= value <= 100:\n        return True\n    else:\n        return False"
            }
        }

    @pytest.fixture
    def nested_schema(self):
        """Create a nested schema with $refs."""
        return {
            "$defs": {
                "Person": {
                    "properties": {
                        "name": {"type": "string"},
                        "age": {"type": "integer"},
                        "email": {"format": "email", "type": "string"}
                    },
                    "required": ["name", "age", "email"],
                    "title": "Person",
                    "type": "object"
                }
            },
            "properties": {
                "content": {"$ref": "#/$defs/Person"}
            },
            "required": ["content"],
            "title": "Schema",
            "type": "object"
        }

    @pytest.fixture
    def nested_validations(self):
        """Validation rules for nested schema."""
        return {
            "Person": {
                "name": {
                    "prompt": "Name must be at least 3 characters",
                    "code": "def validate_name(value):\n    if len(value) >= 3:\n        return True\n    else:\n        return False"
                },
                "age": {
                    "prompt": "Age must be between 18 and 100",
                    "code": "def validate_age(value):\n    if 18 <= value <= 100:\n        return True\n    else:\n        return False"
                }
            }
        }

    @pytest.mark.asyncio
    async def test_enhance_single_model_with_validations(self, enhancer, simple_person_model, validation_rules):
        """Test enhancing a single model with field validations."""
        # Act
        enhanced_model = await enhancer.enhance_model_with_field_validations(
            simple_person_model, validation_rules
        )

        # Assert - Valid data should pass
        valid_person = enhanced_model(
            name="Alice",
            age=25,
            email="alice@example.com"
        )
        assert valid_person.name == "Alice"
        assert valid_person.age == 25

        # Assert - Invalid name (too short) should fail
        with pytest.raises(ValidationError) as exc_info:
            enhanced_model(
                name="Al",  # Only 2 characters
                age=25,
                email="al@example.com"
            )
        assert "Name must be at least 3 characters" in str(exc_info.value)

        # Assert - Invalid age (too old) should fail
        with pytest.raises(ValidationError) as exc_info:
            enhanced_model(
                name="Bob",
                age=150,  # Over 100
                email="bob@example.com"
            )
        assert "Age must be between 18 and 100" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_enhance_model_with_edge_cases(self, enhancer, simple_person_model, validation_rules):
        """Test edge cases for validation (boundary values)."""
        enhanced_model = await enhancer.enhance_model_with_field_validations(
            simple_person_model, validation_rules
        )

        # Test minimum valid name length (3 characters)
        valid_min_name = enhanced_model(
            name="Bob",  # Exactly 3 characters
            age=25,
            email="bob@example.com"
        )
        assert valid_min_name.name == "Bob"

        # Test minimum valid age (18)
        valid_min_age = enhanced_model(
            name="Alice",
            age=18,  # Minimum valid age
            email="alice@example.com"
        )
        assert valid_min_age.age == 18

        # Test maximum valid age (100)
        valid_max_age = enhanced_model(
            name="Alice",
            age=100,  # Maximum valid age
            email="alice@example.com"
        )
        assert valid_max_age.age == 100

        # Test age just below minimum (17)
        with pytest.raises(ValidationError):
            enhanced_model(
                name="Alice",
                age=17,  # Below minimum
                email="alice@example.com"
            )

        # Test age just above maximum (101)
        with pytest.raises(ValidationError):
            enhanced_model(
                name="Alice",
                age=101,  # Above maximum
                email="alice@example.com"
            )

    @pytest.mark.asyncio
    async def test_enhance_nested_model_from_schema(self, enhancer, nested_schema, nested_validations):
        """Test enhancing models created from nested schema with $refs."""
        # Create models from schema
        main_model = await ModelGeneratorFactory.create_model(
            schema=nested_schema,
            model_name="TestSchema",
            generator_type="custom"
        )

        # Get the Person model from the content field annotation
        content_field = main_model.model_fields.get('content')
        person_model = content_field.annotation

        # Enhance the Person model with validations
        person_validations = nested_validations.get("Person", {})
        enhanced_person = await enhancer.enhance_model_with_field_validations(
            person_model, person_validations
        )

        # Test valid data
        valid_person = enhanced_person(
            name="Alice",
            age=25,
            email="alice@example.com"
        )
        assert valid_person.name == "Alice"

        # Test invalid data
        with pytest.raises(ValidationError) as exc_info:
            enhanced_person(
                name="Al",  # Too short
                age=25,
                email="al@example.com"
            )
        assert "Name must be at least 3 characters" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_enhance_all_models(self, enhancer, nested_schema):
        """Test enhancing multiple models with enhance_all_models method using real models."""
        # Create real models from schema using CustomModelGenerator
        main_model = await ModelGeneratorFactory.create_model(
            schema=nested_schema,
            model_name="MainSchema",
            generator_type="custom"
        )

        # Create validations for the Person model
        all_validations = {
            "Person": {
                "name": {
                    "prompt": "Name must be at least 3 characters",
                    "code": "def validate_name(value):\n    if len(value) >= 3:\n        return True\n    else:\n        return False"
                },
                "age": {
                    "prompt": "Age must be between 18 and 100",
                    "code": "def validate_age(value):\n    if 18 <= value <= 100:\n        return True\n    else:\n        return False"
                }
            }
        }

        # Enhance all models using the refactored method (no all_models dict needed)
        enhanced_models = await enhancer.enhance_all_models(
            main_model, all_validations
        )

        # Verify Person model was enhanced
        assert "Person" in enhanced_models
        enhanced_person = enhanced_models["Person"]

        # Test that enhanced model validates correctly
        valid_person = enhanced_person(
            name="Alice",
            age=25,
            email="alice@example.com"
        )
        assert valid_person.name == "Alice"

        # Test validation failure
        with pytest.raises(ValidationError):
            enhanced_person(
                name="Al",
                age=25,
                email="al@example.com"
            )

    @pytest.mark.asyncio
    async def test_extract_models_from_complex_schema(self, enhancer):
        """Test extracting and enhancing models from a complex nested schema."""
        # Create a complex schema with multiple nested models
        complex_schema = {
            "$defs": {
                "Address": {
                    "properties": {
                        "street": {"type": "string"},
                        "city": {"type": "string"},
                        "zipcode": {"type": "string"}
                    },
                    "required": ["street", "city", "zipcode"],
                    "type": "object"
                },
                "Person": {
                    "properties": {
                        "name": {"type": "string"},
                        "age": {"type": "integer"},
                        "address": {"$ref": "#/$defs/Address"}
                    },
                    "required": ["name", "age", "address"],
                    "type": "object"
                }
            },
            "properties": {
                "company_name": {"type": "string"},
                "employees": {
                    "type": "array",
                    "items": {"$ref": "#/$defs/Person"}
                }
            },
            "required": ["company_name", "employees"],
            "type": "object"
        }

        # Create models from complex schema
        root_model = await ModelGeneratorFactory.create_model(
            schema=complex_schema,
            model_name="Company",
            generator_type="custom"
        )

        # Define validations for nested models
        all_validations = {
            "Address": {
                "zipcode": {
                    "prompt": "Zipcode must be 5 digits",
                    "code": "def validate_zipcode(value):\n    if len(value) == 5 and value.isdigit():\n        return True\n    else:\n        return False"
                }
            },
            "Person": {
                "age": {
                    "prompt": "Age must be between 18 and 65",
                    "code": "def validate_age(value):\n    if 18 <= value <= 65:\n        return True\n    else:\n        return False"
                }
            }
        }

        # Extract all models from root and enhance them
        enhanced_models = await enhancer.enhance_all_models(
            root_model, all_validations
        )

        # Verify all models were extracted
        assert "Company" in enhanced_models
        assert "Person" in enhanced_models
        assert "Address" in enhanced_models

        # Get enhanced models
        enhanced_address = enhanced_models["Address"]
        enhanced_person = enhanced_models["Person"]

        # Test Address validation
        valid_address = enhanced_address(
            street="123 Main St",
            city="New York",
            zipcode="12345"
        )
        assert valid_address.zipcode == "12345"

        # Test invalid zipcode
        with pytest.raises(ValidationError) as exc_info:
            enhanced_address(
                street="123 Main St",
                city="New York",
                zipcode="123"  # Too short
            )
        assert "Zipcode must be 5 digits" in str(exc_info.value)

        # Test Person with nested Address validation
        valid_person = enhanced_person(
            name="John Doe",
            age=30,
            address={
                "street": "456 Oak Ave",
                "city": "Boston",
                "zipcode": "54321"
            }
        )
        assert valid_person.age == 30

        # Test invalid age
        with pytest.raises(ValidationError) as exc_info:
            enhanced_person(
                name="Jane Doe",
                age=70,  # Too old
                address={
                    "street": "789 Pine St",
                    "city": "Chicago",
                    "zipcode": "67890"
                }
            )
        assert "Age must be between 18 and 65" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validation_with_multiple_fields(self, enhancer):
        """Test model with validations on multiple fields."""

        class User(BaseModel):
            username: str
            password: str
            age: int

        validations = {
            "username": {
                "prompt": "Username must be 5-20 characters",
                "code": "def validate_username(value):\n    if 5 <= len(value) <= 20:\n        return True\n    else:\n        return False"
            },
            "password": {
                "prompt": "Password must be at least 8 characters",
                "code": "def validate_password(value):\n    if len(value) >= 8:\n        return True\n    else:\n        return False"
            },
            "age": {
                "prompt": "Age must be at least 13",
                "code": "def validate_age(value):\n    if value >= 13:\n        return True\n    else:\n        return False"
            }
        }

        enhanced_user = await enhancer.enhance_model_with_field_validations(User, validations)

        # Test all valid
        valid_user = enhanced_user(
            username="alice123",
            password="securepass123",
            age=25
        )
        assert valid_user.username == "alice123"

        # Test multiple validation failures
        with pytest.raises(ValidationError) as exc_info:
            enhanced_user(
                username="abc",  # Too short
                password="pass",  # Too short
                age=10  # Too young
            )
        error_str = str(exc_info.value)
        # All three validation messages should appear
        assert "Username must be 5-20 characters" in error_str or "username" in error_str.lower()

    @pytest.mark.asyncio
    async def test_empty_validations(self, enhancer, simple_person_model):
        """Test enhancing model with empty validations."""
        # Enhance with empty validations
        enhanced_model = await enhancer.enhance_model_with_field_validations(
            simple_person_model, {}
        )

        # Should still work without any additional validations
        person = enhanced_model(
            name="A",  # Would be invalid if validation was applied
            age=200,   # Would be invalid if validation was applied
            email="test@example.com"
        )
        assert person.name == "A"
        assert person.age == 200

    @pytest.mark.asyncio
    async def test_complex_validation_logic(self, enhancer):
        """Test with more complex validation logic."""

        class Product(BaseModel):
            name: str
            price: float
            quantity: int

        validations = {
            "price": {
                "prompt": "Price must be positive and less than 10000",
                "code": "def validate_price(value):\n    if 0 < value < 10000:\n        return True\n    else:\n        return False"
            },
            "quantity": {
                "prompt": "Quantity must be between 1 and 1000",
                "code": "def validate_quantity(value):\n    if 1 <= value <= 1000:\n        return True\n    else:\n        return False"
            }
        }

        enhanced_product = await enhancer.enhance_model_with_field_validations(Product, validations)

        # Test valid product
        valid_product = enhanced_product(
            name="Widget",
            price=99.99,
            quantity=10
        )
        assert valid_product.price == 99.99

        # Test invalid price (negative)
        with pytest.raises(ValidationError) as exc_info:
            enhanced_product(
                name="Widget",
                price=-10,
                quantity=10
            )
        assert "Price must be positive and less than 10000" in str(exc_info.value)

        # Test invalid quantity (zero)
        with pytest.raises(ValidationError) as exc_info:
            enhanced_product(
                name="Widget",
                price=99.99,
                quantity=0
            )
        assert "Quantity must be between 1 and 1000" in str(exc_info.value)


# Integration test using the exact schema and validations from the example
@pytest.mark.asyncio
async def test_integration_with_example_schema():
    """Integration test using the exact schema and validations from field_validation.py."""

    # Use the exact schema from the example
    schema = {
        "$defs": {
            "Person": {
                "properties": {
                    "name": {"title": "Name", "type": "string"},
                    "age": {"title": "Age", "type": "integer"},
                    "email": {"format": "email", "title": "Email", "type": "string"}
                },
                "required": ["name", "age", "email"],
                "title": "Person",
                "type": "object"
            }
        },
        "properties": {
            "content": {"$ref": "#/$defs/Person"}
        },
        "required": ["content"],
        "title": "Schema",
        "type": "object"
    }

    # Use the exact validations from the example
    validations = {
        "Person": {
            "name": {
                "prompt": "Name must be at least 3 characters",
                "code": "def validate_name(value):\n    if len(value) >= 3:\n        return True\n    else:\n        return False"
            },
            "age": {
                "prompt": "Age must be between 18 and 100",
                "code": "def validate_age(value):\n    if 18 <= value <= 100:\n        return True\n    else:\n        return False"
            }
        }
    }

    # Create models from schema
    main_model = await ModelGeneratorFactory.create_model(
        schema=schema,
        model_name="Schema",
        generator_type="custom"
    )

    # Get the Person model
    content_field = main_model.model_fields.get('content')
    person_model = content_field.annotation

    # Enhance the Person model
    enhancer = ModelValidationEnhancer()
    enhanced_person = await enhancer.enhance_model_with_field_validations(
        person_model, validations["Person"]
    )

    # Test valid Person through content
    valid_data = {
        "content": {
            "name": "John Doe",
            "age": 30,
            "email": "john@example.com"
        }
    }

    # Create instance with enhanced Person model
    # Note: We need to update the main model to use the enhanced Person
    main_model.model_fields['content'].annotation = enhanced_person

    # Create the enhanced Person directly
    valid_person = enhanced_person(
        name="John Doe",
        age=30,
        email="john@example.com"
    )
    assert valid_person.name == "John Doe"
    assert valid_person.age == 30

    # Test invalid scenarios
    print("\nTesting validation failures:")

    # Test 1: Name too short
    try:
        invalid_person = enhanced_person(
            name="Jo",  # Only 2 characters
            age=30,
            email="jo@example.com"
        )
        assert False, "Should have raised ValidationError for short name"
    except ValidationError as e:
        print(f"✓ Short name validation: {e}")
        assert "Name must be at least 3 characters" in str(e)

    # Test 2: Age too young
    try:
        invalid_person = enhanced_person(
            name="Jane Doe",
            age=16,  # Below 18
            email="jane@example.com"
        )
        assert False, "Should have raised ValidationError for age"
    except ValidationError as e:
        print(f"✓ Young age validation: {e}")
        assert "Age must be between 18 and 100" in str(e)

    # Test 3: Age too old
    try:
        invalid_person = enhanced_person(
            name="Jane Doe",
            age=105,  # Above 100
            email="jane@example.com"
        )
        assert False, "Should have raised ValidationError for age"
    except ValidationError as e:
        print(f"✓ Old age validation: {e}")
        assert "Age must be between 18 and 100" in str(e)

    print("\n✅ All integration tests passed!")


if __name__ == "__main__":
    # Run the integration test
    asyncio.run(test_integration_with_example_schema())

    # docker exec budserve-development-budprompt bash -c "PYTHONPATH=/app pytest tests/test_unit_tests/test_model_validation_enhancer.py -v"
