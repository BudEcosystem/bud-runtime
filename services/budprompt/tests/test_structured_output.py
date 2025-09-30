"""
Comprehensive test cases for OpenAI Structured Output validation.
Combines tests for:
- String properties (pattern, format validations)
- Array properties (minItems, maxItems constraints)
- Number properties (multipleOf, minimum, maximum, exclusive bounds)
- All supported types (String, Number, Boolean, Integer, Object, Array, Enum, anyOf)
"""

import sys
import os
import asyncio
import pytest
from pydantic import BaseModel, Field, ValidationError, EmailStr, constr, conint, confloat, conlist
from pydantic.networks import IPv4Address, IPv6Address, IPvAnyAddress
from datetime import datetime, date, time, timedelta
from typing import Optional, List, Union, Literal, Set, Any, Dict, Type
from decimal import Decimal
from enum import Enum
from uuid import UUID
from budprompt.prompt.schema_builder import ModelGeneratorFactory
from budprompt.commons.helpers import run_async


# ============================================================================
# DYNAMIC MODEL CREATION HELPER
# ============================================================================

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


# ============================================================================
# MODEL DEFINITIONS - STRING PROPERTIES
# ============================================================================

class StringPropertiesModel(BaseModel):
    """Model containing all string constraint types."""

    # Pattern validation
    username: constr(pattern=r"^[a-zA-Z0-9_]{3,20}$") = Field(
        description="Username with pattern validation"
    )
    phone: constr(pattern=r"^\+?[1-9]\d{1,14}$") = Field(
        description="Phone number in E.164 format"
    )
    postal_code: constr(pattern=r"^\d{5}(-\d{4})?$") = Field(
        description="US postal code"
    )

    # Format validations
    email: EmailStr = Field(description="Email address")
    uuid_field: UUID = Field(description="UUID version 4")
    datetime_field: datetime = Field(description="ISO 8601 datetime")
    date_field: date = Field(description="ISO date")
    time_field: time = Field(description="ISO time")
    duration_field: timedelta = Field(description="ISO 8601 duration")

    # Network formats
    hostname: constr(pattern=r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$') = Field(description="Valid hostname")
    ipv4_address: IPv4Address = Field(description="IPv4 address")
    ipv6_address: IPv6Address = Field(description="IPv6 address")

    # Optional fields for testing null handling
    optional_email: Optional[EmailStr] = None
    optional_pattern: Optional[constr(pattern=r"^[A-Z]{2,4}$")] = None


# ============================================================================
# MODEL DEFINITIONS - ARRAY PROPERTIES
# ============================================================================

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


# ============================================================================
# MODEL DEFINITIONS - NUMBER PROPERTIES
# ============================================================================

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


# ============================================================================
# MODEL DEFINITIONS - SUPPORTED TYPES
# ============================================================================

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


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def string_dynamic_model():
    """Create dynamic model from the string properties schema."""
    schema = StringPropertiesModel.model_json_schema()
    return json_schema_to_pydantic_model(schema, "DynamicStringProperties")


@pytest.fixture
def array_dynamic_model():
    """Create dynamic model from the array properties schema."""
    schema = ArrayPropertiesModel.model_json_schema()
    return json_schema_to_pydantic_model(schema, "DynamicArrayProperties")


@pytest.fixture
def number_dynamic_model():
    """Create dynamic model from the number properties schema."""
    schema = NumberPropertiesModel.model_json_schema()
    return json_schema_to_pydantic_model(schema, "DynamicNumberProperties")


@pytest.fixture
def types_dynamic_model():
    """Create dynamic model from the comprehensive types schema."""
    schema = ComprehensiveTypesModel.model_json_schema()
    return json_schema_to_pydantic_model(schema, "DynamicComprehensiveTypes")


# ============================================================================
# STRING PROPERTIES - SUCCESS TEST CASES
# ============================================================================

@pytest.mark.ci_cd
def test_success_string_valid_patterns(string_dynamic_model):
    """Test that valid patterns are accepted."""
    valid_data = {
        "username": "john_doe_123",
        "phone": "+14155552671",
        "postal_code": "94105",
        "email": "test@example.com",
        "uuid_field": "550e8400-e29b-41d4-a716-446655440000",
        "datetime_field": "2024-01-15T10:30:00Z",
        "date_field": "2024-01-15",
        "time_field": "10:30:00",
        "duration_field": "P1DT2H30M",  # 1 day, 2 hours, 30 minutes
        "hostname": "example.com",
        "ipv4_address": "192.168.1.1",
        "ipv6_address": "2001:0db8:85a3:0000:0000:8a2e:0370:7334"
    }

    instance = string_dynamic_model.model_validate(valid_data)
    assert instance.username == "john_doe_123"
    assert instance.phone == "+14155552671"
    assert instance.postal_code == "94105"


@pytest.mark.ci_cd
def test_success_string_extended_postal_code(string_dynamic_model):
    """Test extended postal code format."""
    valid_data = {
        "username": "user123",
        "phone": "+11234567890",
        "postal_code": "94105-1234",  # Extended format
        "email": "test@example.com",
        "uuid_field": "550e8400-e29b-41d4-a716-446655440000",
        "datetime_field": "2024-01-15T10:30:00Z",
        "date_field": "2024-01-15",
        "time_field": "10:30:00",
        "duration_field": "PT30M",
        "hostname": "example.com",
        "ipv4_address": "10.0.0.1",
        "ipv6_address": "::1"
    }

    instance = string_dynamic_model.model_validate(valid_data)
    assert instance.postal_code == "94105-1234"


@pytest.mark.ci_cd
def test_success_string_valid_email_formats(string_dynamic_model):
    """Test various valid email formats."""
    base_data = {
        "username": "user123",
        "phone": "+11234567890",
        "postal_code": "12345",
        "uuid_field": "550e8400-e29b-41d4-a716-446655440000",
        "datetime_field": "2024-01-15T10:30:00Z",
        "date_field": "2024-01-15",
        "time_field": "10:30:00",
        "duration_field": "PT1H",
        "hostname": "example.com",
        "ipv4_address": "127.0.0.1",
        "ipv6_address": "::1"
    }

    email_tests = [
        "simple@example.com",
        "user.name@example.com",
        "user+tag@example.co.uk",
        "user_123@sub.example.org"
    ]

    for email in email_tests:
        data = {**base_data, "email": email}
        instance = string_dynamic_model.model_validate(data)
        assert instance.email == email


@pytest.mark.ci_cd
def test_success_string_valid_datetime_formats(string_dynamic_model):
    """Test various valid datetime formats."""
    base_data = {
        "username": "user123",
        "phone": "+11234567890",
        "postal_code": "12345",
        "email": "test@example.com",
        "uuid_field": "550e8400-e29b-41d4-a716-446655440000",
        "date_field": "2024-01-15",
        "time_field": "10:30:00",
        "duration_field": "PT1H",
        "hostname": "example.com",
        "ipv4_address": "127.0.0.1",
        "ipv6_address": "::1"
    }

    datetime_tests = [
        "2024-01-15T10:30:00Z",
        "2024-01-15T10:30:00+00:00",
        "2024-01-15T10:30:00.123Z",
        "2024-12-31T23:59:59Z"
    ]

    for dt in datetime_tests:
        data = {**base_data, "datetime_field": dt}
        instance = string_dynamic_model.model_validate(data)
        assert instance.datetime_field


@pytest.mark.ci_cd
def test_success_string_valid_ipv4_addresses(string_dynamic_model):
    """Test various valid IPv4 addresses."""
    base_data = {
        "username": "user123",
        "phone": "+11234567890",
        "postal_code": "12345",
        "email": "test@example.com",
        "uuid_field": "550e8400-e29b-41d4-a716-446655440000",
        "datetime_field": "2024-01-15T10:30:00Z",
        "date_field": "2024-01-15",
        "time_field": "10:30:00",
        "duration_field": "PT1H",
        "hostname": "example.com",
        "ipv6_address": "::1"
    }

    ipv4_tests = [
        "0.0.0.0",
        "127.0.0.1",
        "192.168.1.1",
        "255.255.255.255",
        "10.0.0.1",
        "172.16.0.1"
    ]

    for ip in ipv4_tests:
        data = {**base_data, "ipv4_address": ip}
        instance = string_dynamic_model.model_validate(data)
        assert str(instance.ipv4_address) == ip


@pytest.mark.ci_cd
def test_success_string_valid_ipv6_addresses(string_dynamic_model):
    """Test various valid IPv6 addresses."""
    base_data = {
        "username": "user123",
        "phone": "+11234567890",
        "postal_code": "12345",
        "email": "test@example.com",
        "uuid_field": "550e8400-e29b-41d4-a716-446655440000",
        "datetime_field": "2024-01-15T10:30:00Z",
        "date_field": "2024-01-15",
        "time_field": "10:30:00",
        "duration_field": "PT1H",
        "hostname": "example.com",
        "ipv4_address": "127.0.0.1"
    }

    ipv6_tests = [
        "::1",
        "::",
        "2001:db8::8a2e:370:7334",
        "2001:0db8:85a3:0000:0000:8a2e:0370:7334",
        "fe80::1"
    ]

    for ip in ipv6_tests:
        data = {**base_data, "ipv6_address": ip}
        instance = string_dynamic_model.model_validate(data)
        # IPv6Address normalizes the address, so we compare the normalized forms
        assert str(instance.ipv6_address) == str(IPvAnyAddress(ip))


@pytest.mark.ci_cd
def test_success_string_valid_hostnames(string_dynamic_model):
    """Test various valid hostnames."""
    base_data = {
        "username": "user123",
        "phone": "+11234567890",
        "postal_code": "12345",
        "email": "test@example.com",
        "uuid_field": "550e8400-e29b-41d4-a716-446655440000",
        "datetime_field": "2024-01-15T10:30:00Z",
        "date_field": "2024-01-15",
        "time_field": "10:30:00",
        "duration_field": "PT1H",
        "ipv4_address": "127.0.0.1",
        "ipv6_address": "::1"
    }

    hostname_tests = [
        "example.com",
        "sub.example.com",
        "my-server.example.org",
        "localhost",
        "server123.test"
    ]

    for hostname in hostname_tests:
        data = {**base_data, "hostname": hostname}
        instance = string_dynamic_model.model_validate(data)
        assert instance.hostname == hostname


# ============================================================================
# STRING PROPERTIES - ERROR TEST CASES
# ============================================================================

@pytest.mark.ci_cd
def test_failure_string_invalid_username_pattern(string_dynamic_model):
    """Test that invalid username patterns are rejected."""
    invalid_data = {
        "username": "ab",  # Too short (min 3 chars)
        "phone": "+11234567890",
        "postal_code": "12345",
        "email": "test@example.com",
        "uuid_field": "550e8400-e29b-41d4-a716-446655440000",
        "datetime_field": "2024-01-15T10:30:00Z",
        "date_field": "2024-01-15",
        "time_field": "10:30:00",
        "duration_field": "PT1H",
        "hostname": "example.com",
        "ipv4_address": "127.0.0.1",
        "ipv6_address": "::1"
    }

    with pytest.raises(ValidationError) as exc_info:
        string_dynamic_model.model_validate(invalid_data)
    assert "username" in str(exc_info.value)


@pytest.mark.ci_cd
def test_failure_string_invalid_phone_pattern(string_dynamic_model):
    """Test that invalid phone patterns are rejected."""
    invalid_data = {
        "username": "user123",
        "phone": "123-456-7890",  # Invalid format (not E.164)
        "postal_code": "12345",
        "email": "test@example.com",
        "uuid_field": "550e8400-e29b-41d4-a716-446655440000",
        "datetime_field": "2024-01-15T10:30:00Z",
        "date_field": "2024-01-15",
        "time_field": "10:30:00",
        "duration_field": "PT1H",
        "hostname": "example.com",
        "ipv4_address": "127.0.0.1",
        "ipv6_address": "::1"
    }

    with pytest.raises(ValidationError) as exc_info:
        string_dynamic_model.model_validate(invalid_data)
    assert "phone" in str(exc_info.value)


@pytest.mark.ci_cd
def test_failure_string_invalid_postal_code_pattern(string_dynamic_model):
    """Test that invalid postal codes are rejected."""
    invalid_data = {
        "username": "user123",
        "phone": "+11234567890",
        "postal_code": "ABCDE",  # Letters instead of numbers
        "email": "test@example.com",
        "uuid_field": "550e8400-e29b-41d4-a716-446655440000",
        "datetime_field": "2024-01-15T10:30:00Z",
        "date_field": "2024-01-15",
        "time_field": "10:30:00",
        "duration_field": "PT1H",
        "hostname": "example.com",
        "ipv4_address": "127.0.0.1",
        "ipv6_address": "::1"
    }

    with pytest.raises(ValidationError) as exc_info:
        string_dynamic_model.model_validate(invalid_data)
    assert "postal_code" in str(exc_info.value)


@pytest.mark.ci_cd
def test_failure_string_invalid_email_format(string_dynamic_model):
    """Test that invalid email formats are rejected."""
    invalid_emails = [
        "notanemail",
        "@example.com",
        "user@",
        "user..name@example.com",
        "user@.com",
        "user@example"
    ]

    base_data = {
        "username": "user123",
        "phone": "+11234567890",
        "postal_code": "12345",
        "uuid_field": "550e8400-e29b-41d4-a716-446655440000",
        "datetime_field": "2024-01-15T10:30:00Z",
        "date_field": "2024-01-15",
        "time_field": "10:30:00",
        "duration_field": "PT1H",
        "hostname": "example.com",
        "ipv4_address": "127.0.0.1",
        "ipv6_address": "::1"
    }

    for email in invalid_emails:
        data = {**base_data, "email": email}
        with pytest.raises(ValidationError) as exc_info:
            string_dynamic_model.model_validate(data)
        assert "email" in str(exc_info.value)


@pytest.mark.ci_cd
def test_failure_string_invalid_uuid_format(string_dynamic_model):
    """Test that invalid UUID formats are rejected."""
    invalid_uuids = [
        "not-a-uuid",
        "550e8400-e29b-41d4-a716",
        "550e8400-e29b-41d4-a716-446655440000-extra",
        "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    ]

    base_data = {
        "username": "user123",
        "phone": "+11234567890",
        "postal_code": "12345",
        "email": "test@example.com",
        "datetime_field": "2024-01-15T10:30:00Z",
        "date_field": "2024-01-15",
        "time_field": "10:30:00",
        "duration_field": "PT1H",
        "hostname": "example.com",
        "ipv4_address": "127.0.0.1",
        "ipv6_address": "::1"
    }

    for uuid in invalid_uuids:
        data = {**base_data, "uuid_field": uuid}
        with pytest.raises(ValidationError) as exc_info:
            string_dynamic_model.model_validate(data)
        assert "uuid_field" in str(exc_info.value)


@pytest.mark.ci_cd
def test_failure_string_invalid_datetime_format(string_dynamic_model):
    """Test that invalid datetime formats are rejected."""
    invalid_datetimes = [
        "10:30:00",  # Time only, no date
        "2024-13-01T10:30:00Z",  # Invalid month
        "2024-01-32T10:30:00Z",  # Invalid day
        "not-a-datetime"
    ]

    base_data = {
        "username": "user123",
        "phone": "+11234567890",
        "postal_code": "12345",
        "email": "test@example.com",
        "uuid_field": "550e8400-e29b-41d4-a716-446655440000",
        "date_field": "2024-01-15",
        "time_field": "10:30:00",
        "duration_field": "PT1H",
        "hostname": "example.com",
        "ipv4_address": "127.0.0.1",
        "ipv6_address": "::1"
    }

    for dt in invalid_datetimes:
        data = {**base_data, "datetime_field": dt}
        with pytest.raises(ValidationError) as exc_info:
            string_dynamic_model.model_validate(data)
        assert "datetime_field" in str(exc_info.value)


@pytest.mark.ci_cd
def test_failure_string_invalid_ipv4_format(string_dynamic_model):
    """Test that invalid IPv4 addresses are rejected."""
    invalid_ips = [
        "256.256.256.256",  # Out of range
        "192.168.1",  # Missing octet
        "192.168.1.1.1",  # Extra octet
        "192.168.1.a",  # Non-numeric
        "not-an-ip"
    ]

    base_data = {
        "username": "user123",
        "phone": "+11234567890",
        "postal_code": "12345",
        "email": "test@example.com",
        "uuid_field": "550e8400-e29b-41d4-a716-446655440000",
        "datetime_field": "2024-01-15T10:30:00Z",
        "date_field": "2024-01-15",
        "time_field": "10:30:00",
        "duration_field": "PT1H",
        "hostname": "example.com",
        "ipv6_address": "::1"
    }

    for ip in invalid_ips:
        data = {**base_data, "ipv4_address": ip}
        with pytest.raises(ValidationError) as exc_info:
            string_dynamic_model.model_validate(data)
        assert "ipv4_address" in str(exc_info.value)


@pytest.mark.ci_cd
def test_success_string_optional_fields_with_none(string_dynamic_model):
    """Test that optional fields can be None."""
    valid_data = {
        "username": "user123",
        "phone": "+11234567890",
        "postal_code": "12345",
        "email": "test@example.com",
        "uuid_field": "550e8400-e29b-41d4-a716-446655440000",
        "datetime_field": "2024-01-15T10:30:00Z",
        "date_field": "2024-01-15",
        "time_field": "10:30:00",
        "duration_field": "PT1H",
        "hostname": "example.com",
        "ipv4_address": "127.0.0.1",
        "ipv6_address": "::1",
        "optional_email": None,
        "optional_pattern": None
    }

    instance = string_dynamic_model.model_validate(valid_data)
    assert instance.optional_email is None
    assert instance.optional_pattern is None


@pytest.mark.ci_cd
def test_success_string_optional_fields_with_values(string_dynamic_model):
    """Test that optional fields can have valid values."""
    valid_data = {
        "username": "user123",
        "phone": "+11234567890",
        "postal_code": "12345",
        "email": "test@example.com",
        "uuid_field": "550e8400-e29b-41d4-a716-446655440000",
        "datetime_field": "2024-01-15T10:30:00Z",
        "date_field": "2024-01-15",
        "time_field": "10:30:00",
        "duration_field": "PT1H",
        "hostname": "example.com",
        "ipv4_address": "127.0.0.1",
        "ipv6_address": "::1",
        "optional_email": "optional@example.com",
        "optional_pattern": "ABC"
    }

    instance = string_dynamic_model.model_validate(valid_data)
    assert instance.optional_email == "optional@example.com"
    assert instance.optional_pattern == "ABC"


# ============================================================================
# ARRAY PROPERTIES - SUCCESS TEST CASES
# ============================================================================

@pytest.mark.ci_cd
def test_success_array_valid_within_bounds(array_dynamic_model):
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

    instance = array_dynamic_model.model_validate(valid_data)
    assert len(instance.tags) == 3
    assert len(instance.coordinates) == 2
    assert len(instance.items) == 4


@pytest.mark.ci_cd
def test_success_array_minimum_items_boundary(array_dynamic_model):
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

    instance = array_dynamic_model.model_validate(valid_data)
    assert len(instance.tags) == 1
    assert len(instance.items) == 3
    assert len(instance.metadata) == 0


@pytest.mark.ci_cd
def test_success_array_maximum_items_boundary(array_dynamic_model):
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

    instance = array_dynamic_model.model_validate(valid_data)
    assert len(instance.tags) == 10
    assert len(instance.top_five) == 5
    assert len(instance.metadata) == 5


@pytest.mark.ci_cd
def test_success_array_of_objects(array_dynamic_model):
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

    instance = array_dynamic_model.model_validate(valid_data)
    assert len(instance.metadata) == 3
    assert instance.metadata[0]["name"] == "author" if isinstance(instance.metadata[0], dict) else instance.metadata[0].name == "author"


@pytest.mark.ci_cd
def test_success_array_nested_arrays(array_dynamic_model):
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

    instance = array_dynamic_model.model_validate(valid_data)
    assert len(instance.matrix) == 3
    assert all(len(row) == 2 for row in instance.matrix)
    assert instance.matrix[0][0] == 10


@pytest.mark.ci_cd
def test_success_array_empty_arrays_where_allowed(array_dynamic_model):
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

    instance = array_dynamic_model.model_validate(valid_data)
    assert len(instance.top_five) == 0
    assert len(instance.metadata) == 0
    assert len(instance.unconstrained_array) == 0


# ============================================================================
# ARRAY PROPERTIES - ERROR TEST CASES
# ============================================================================

@pytest.mark.ci_cd
def test_failure_array_below_minimum_items(array_dynamic_model):
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
        array_dynamic_model.model_validate(invalid_data)
    assert "tags" in str(exc_info.value)


@pytest.mark.ci_cd
def test_failure_array_coordinates_too_few(array_dynamic_model):
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
        array_dynamic_model.model_validate(invalid_data)
    assert "coordinates" in str(exc_info.value)


@pytest.mark.ci_cd
def test_failure_array_items_too_few(array_dynamic_model):
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
        array_dynamic_model.model_validate(invalid_data)
    assert "items" in str(exc_info.value)


@pytest.mark.ci_cd
def test_failure_array_matrix_too_few_rows(array_dynamic_model):
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
        array_dynamic_model.model_validate(invalid_data)
    assert "matrix" in str(exc_info.value)


@pytest.mark.ci_cd
def test_failure_array_above_maximum_items(array_dynamic_model):
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
        array_dynamic_model.model_validate(invalid_data)
    assert "tags" in str(exc_info.value)


@pytest.mark.ci_cd
def test_failure_array_coordinates_too_many(array_dynamic_model):
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
        array_dynamic_model.model_validate(invalid_data)
    assert "coordinates" in str(exc_info.value)


@pytest.mark.ci_cd
def test_failure_array_top_five_too_many(array_dynamic_model):
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
        array_dynamic_model.model_validate(invalid_data)
    assert "top_five" in str(exc_info.value)


@pytest.mark.ci_cd
def test_failure_array_matrix_too_many_rows(array_dynamic_model):
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
        array_dynamic_model.model_validate(invalid_data)
    assert "matrix" in str(exc_info.value)


@pytest.mark.ci_cd
def test_failure_array_matrix_wrong_column_count(array_dynamic_model):
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
        array_dynamic_model.model_validate(invalid_data)
    assert "matrix" in str(exc_info.value)


@pytest.mark.ci_cd
def test_failure_array_wrong_item_type_in_array(array_dynamic_model):
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
        array_dynamic_model.model_validate(invalid_data)
    assert "tags" in str(exc_info.value)


@pytest.mark.ci_cd
def test_failure_array_wrong_object_structure_in_array(array_dynamic_model):
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
        array_dynamic_model.model_validate(invalid_data)
    assert "metadata" in str(exc_info.value) or "value" in str(exc_info.value)


@pytest.mark.ci_cd
def test_success_array_optional_arrays_with_none(array_dynamic_model):
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

    instance = array_dynamic_model.model_validate(valid_data)
    assert instance.optional_tags is None
    assert instance.optional_empty_allowed is None


@pytest.mark.ci_cd
def test_success_array_optional_arrays_with_valid_values(array_dynamic_model):
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

    instance = array_dynamic_model.model_validate(valid_data)
    assert len(instance.optional_tags) == 2
    assert len(instance.optional_empty_allowed) == 0


@pytest.mark.ci_cd
def test_failure_array_optional_arrays_still_enforce_constraints(array_dynamic_model):
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
        array_dynamic_model.model_validate(invalid_data)
    assert "optional_tags" in str(exc_info.value)


@pytest.mark.ci_cd
def test_success_array_large_unconstrained_array(array_dynamic_model):
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

    instance = array_dynamic_model.model_validate(valid_data)
    assert len(instance.unconstrained_array) == 10000


@pytest.mark.ci_cd
def test_success_array_arrays_with_duplicate_values(array_dynamic_model):
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

    instance = array_dynamic_model.model_validate(valid_data)
    assert all(tag == "dup" for tag in instance.tags)
    assert all(val == 1 for val in instance.top_five)


@pytest.mark.ci_cd
def test_success_array_mixed_numeric_types_in_number_array(array_dynamic_model):
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

    instance = array_dynamic_model.model_validate(valid_data)
    assert instance.coordinates[0] == 40
    assert instance.coordinates[1] == -74.0
    assert 2.5 in instance.numbers


# ============================================================================
# NUMBER PROPERTIES - SUCCESS TEST CASES
# ============================================================================

@pytest.mark.ci_cd
def test_success_number_valid_integer_minimum_maximum(number_dynamic_model):
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

    instance = number_dynamic_model.model_validate(valid_data)
    assert instance.age == 25
    assert instance.score == 50


@pytest.mark.ci_cd
def test_success_number_integer_boundary_values(number_dynamic_model):
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
    instance = number_dynamic_model.model_validate(data1)
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
    instance = number_dynamic_model.model_validate(data2)
    assert instance.age == 150
    assert instance.even_between_10_and_100 == 100


@pytest.mark.ci_cd
def test_success_number_multiple_of_constraint_integers(number_dynamic_model):
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
        instance = number_dynamic_model.model_validate(data)
        assert instance.multiple_of_five == multiple


@pytest.mark.ci_cd
def test_success_number_valid_float_minimum_maximum(number_dynamic_model):
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

    instance = number_dynamic_model.model_validate(valid_data)
    assert instance.temperature == -100.5
    assert instance.percentage == 99.99
    assert instance.ratio == 0.618


@pytest.mark.ci_cd
def test_success_number_float_boundary_values(number_dynamic_model):
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
    instance = number_dynamic_model.model_validate(data1)
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
    instance = number_dynamic_model.model_validate(data2)
    assert instance.temperature == 1000.0
    assert instance.percentage == 100.0


@pytest.mark.ci_cd
def test_success_number_multiple_of_constraint_floats(number_dynamic_model):
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
        instance = number_dynamic_model.model_validate(data)
        assert instance.step_value == multiple


@pytest.mark.ci_cd
def test_success_number_combined_constraints(number_dynamic_model):
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
        instance = number_dynamic_model.model_validate(data)
        assert instance.even_between_10_and_100 == even_num

    # Test quarter percentages
    valid_quarters = [0.0, 0.25, 25.0, 50.25, 75.5, 99.75, 100.0]

    for quarter in valid_quarters:
        data = {**base_data, "quarter_percentage": quarter}
        instance = number_dynamic_model.model_validate(data)
        assert instance.quarter_percentage == quarter


# ============================================================================
# NUMBER PROPERTIES - ERROR TEST CASES
# ============================================================================

@pytest.mark.ci_cd
def test_failure_number_invalid_integer_below_minimum(number_dynamic_model):
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
        number_dynamic_model.model_validate(invalid_data)
    assert "age" in str(exc_info.value)


@pytest.mark.ci_cd
def test_failure_number_invalid_integer_above_maximum(number_dynamic_model):
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
        number_dynamic_model.model_validate(invalid_data)
    assert "age" in str(exc_info.value)


@pytest.mark.ci_cd
def test_failure_number_invalid_exclusive_boundaries_integer(number_dynamic_model):
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
        number_dynamic_model.model_validate(invalid_data1)
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
        number_dynamic_model.model_validate(invalid_data2)
    assert "score" in str(exc_info.value)


@pytest.mark.ci_cd
def test_failure_number_invalid_multiple_of_integer(number_dynamic_model):
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
        number_dynamic_model.model_validate(invalid_data)
    assert "multiple_of_five" in str(exc_info.value)


@pytest.mark.ci_cd
def test_failure_number_invalid_float_below_minimum(number_dynamic_model):
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
        number_dynamic_model.model_validate(invalid_data)
    assert "temperature" in str(exc_info.value)


@pytest.mark.ci_cd
def test_failure_number_invalid_float_above_maximum(number_dynamic_model):
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
        number_dynamic_model.model_validate(invalid_data)
    assert "temperature" in str(exc_info.value)


@pytest.mark.ci_cd
def test_failure_number_invalid_exclusive_boundaries_float(number_dynamic_model):
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
        number_dynamic_model.model_validate(invalid_data1)
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
        number_dynamic_model.model_validate(invalid_data2)
    assert "ratio" in str(exc_info.value)


@pytest.mark.ci_cd
def test_failure_number_invalid_multiple_of_float(number_dynamic_model):
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
        number_dynamic_model.model_validate(invalid_data)
    assert "step_value" in str(exc_info.value)


@pytest.mark.ci_cd
def test_failure_number_invalid_combined_constraints(number_dynamic_model):
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
        number_dynamic_model.model_validate(invalid_data1)
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
        number_dynamic_model.model_validate(invalid_data2)
    assert "even_between_10_and_100" in str(exc_info.value)


@pytest.mark.ci_cd
def test_success_number_optional_fields_with_none(number_dynamic_model):
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

    instance = number_dynamic_model.model_validate(valid_data)
    assert instance.optional_age is None
    assert instance.optional_temperature is None


@pytest.mark.ci_cd
def test_success_number_optional_fields_with_valid_values(number_dynamic_model):
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

    instance = number_dynamic_model.model_validate(valid_data)
    assert instance.optional_age == 65
    assert instance.optional_temperature == 37.5


@pytest.mark.ci_cd
def test_failure_number_optional_fields_with_invalid_values(number_dynamic_model):
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
        number_dynamic_model.model_validate(invalid_data)
    assert "optional_age" in str(exc_info.value)


@pytest.mark.ci_cd
def test_success_number_floating_point_precision(number_dynamic_model):
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

    instance = number_dynamic_model.model_validate(valid_data)
    assert instance.temperature < 1000.0
    assert instance.percentage < 100.0 or instance.percentage == 100.0
    assert instance.ratio < 1.0


@pytest.mark.ci_cd
def test_success_number_negative_multiples(number_dynamic_model):
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

    instance = number_dynamic_model.model_validate(valid_data)
    assert instance.multiple_of_five == -15
    assert instance.step_value == -1.25


# ============================================================================
# SUPPORTED TYPES - SUCCESS TEST CASES
# ============================================================================

@pytest.mark.ci_cd
def test_success_types_all_valid_types(types_dynamic_model):
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

    instance = types_dynamic_model.model_validate(valid_data)
    assert instance.string_field == "test string"
    assert instance.number_field == 3.14
    assert instance.boolean_field is True
    assert instance.integer_field == 42
    assert instance.string_enum == "red"
    assert instance.integer_enum == 2


@pytest.mark.ci_cd
def test_success_types_optional_fields_with_none(types_dynamic_model):
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

    instance = types_dynamic_model.model_validate(valid_data)
    assert instance.optional_string is None
    assert instance.optional_object is None


@pytest.mark.ci_cd
def test_success_types_any_of_alternative_types(types_dynamic_model):
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

    instance = types_dynamic_model.model_validate(data_with_string)
    assert instance.any_of_field == "string value"

    # Test with integer
    data_with_integer = {**data_with_string, "any_of_field": 999}
    instance = types_dynamic_model.model_validate(data_with_integer)
    assert instance.any_of_field == 999


@pytest.mark.ci_cd
def test_success_types_empty_arrays(types_dynamic_model):
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

    instance = types_dynamic_model.model_validate(valid_data)
    assert instance.array_field == []
    assert instance.integer_array == []


# ============================================================================
# SUPPORTED TYPES - ERROR TEST CASES
# ============================================================================

@pytest.mark.ci_cd
def test_failure_types_invalid_string_type(types_dynamic_model):
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
        types_dynamic_model.model_validate(invalid_data)
    assert "string_field" in str(exc_info.value)


@pytest.mark.ci_cd
def test_failure_types_invalid_number_type(types_dynamic_model):
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
        types_dynamic_model.model_validate(invalid_data)
    assert "number_field" in str(exc_info.value)


@pytest.mark.ci_cd
def test_failure_types_invalid_boolean_type(types_dynamic_model):
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
        types_dynamic_model.model_validate(invalid_data)
    assert "boolean_field" in str(exc_info.value)


@pytest.mark.ci_cd
def test_failure_types_invalid_integer_type(types_dynamic_model):
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
        types_dynamic_model.model_validate(invalid_data)
    assert "integer_field" in str(exc_info.value)


@pytest.mark.ci_cd
def test_failure_types_invalid_enum_value(types_dynamic_model):
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
        types_dynamic_model.model_validate(invalid_data)
    assert "string_enum" in str(exc_info.value)


@pytest.mark.ci_cd
def test_failure_types_invalid_integer_enum_value(types_dynamic_model):
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
        types_dynamic_model.model_validate(invalid_data)
    assert "integer_enum" in str(exc_info.value)


@pytest.mark.ci_cd
def test_failure_types_invalid_object_structure(types_dynamic_model):
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
        types_dynamic_model.model_validate(invalid_data)
    assert "zipcode" in str(exc_info.value)


@pytest.mark.ci_cd
def test_failure_types_invalid_array_item_type(types_dynamic_model):
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
        types_dynamic_model.model_validate(invalid_data)
    assert "array_field" in str(exc_info.value)


@pytest.mark.ci_cd
def test_failure_types_missing_required_field(types_dynamic_model):
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
        types_dynamic_model.model_validate(invalid_data)
    assert "string_field" in str(exc_info.value)


@pytest.mark.ci_cd
def test_failure_types_invalid_any_of_type(types_dynamic_model):
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
        types_dynamic_model.model_validate(invalid_data)
    assert "any_of_field" in str(exc_info.value)


@pytest.mark.ci_cd
def test_failure_types_invalid_integer_array_item_type(types_dynamic_model):
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
        types_dynamic_model.model_validate(invalid_data)
    assert "integer_array" in str(exc_info.value)


@pytest.mark.ci_cd
def test_failure_types_invalid_complex_any_of_type(types_dynamic_model):
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
        types_dynamic_model.model_validate(invalid_data)
    assert "complex_any_of" in str(exc_info.value)


@pytest.mark.ci_cd
def test_failure_types_invalid_optional_string_type(types_dynamic_model):
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
        types_dynamic_model.model_validate(invalid_data)
    assert "optional_string" in str(exc_info.value)


@pytest.mark.ci_cd
def test_failure_types_invalid_optional_object_structure(types_dynamic_model):
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
        types_dynamic_model.model_validate(invalid_data)
    assert "optional_object" in str(exc_info.value) or "zipcode" in str(exc_info.value)


@pytest.mark.ci_cd
def test_success_types_float_as_integer(types_dynamic_model):
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

    instance = types_dynamic_model.model_validate(data)
    assert instance.integer_field == 42


@pytest.mark.ci_cd
def test_failure_types_numeric_string_coercion(types_dynamic_model):
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
        types_dynamic_model.model_validate(invalid_data)
    assert "number_field" in str(exc_info.value)


if __name__ == "__main__":
    # Run tests with pytest
    # pytest test_structured_output_comprehensive.py -v -s
    pytest.main([__file__, "-v"])
