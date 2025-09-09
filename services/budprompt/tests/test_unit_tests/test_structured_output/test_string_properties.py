"""
Test cases for string properties in OpenAI Structured Output.
Tests: pattern, format (date-time, time, date, duration, email, hostname, ipv4, ipv6, uuid)
"""

import sys
import os

import pytest
from pydantic import BaseModel, Field, ValidationError, EmailStr, constr, IPvAnyAddress
from ipaddress import IPv4Address, IPv6Address
from datetime import datetime, date, time, timedelta
from typing import Optional
from .dynamic_model_creation import json_schema_to_pydantic_model
from uuid import UUID


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
    ipv4_address: IPvAnyAddress = Field(description="IPv4 address")
    ipv6_address: IPvAnyAddress = Field(description="IPv6 address")

    # Optional fields for testing null handling
    optional_email: Optional[EmailStr] = None
    optional_pattern: Optional[constr(pattern=r"^[A-Z]{2,4}$")] = None


# Create fixture for the dynamic model
@pytest.fixture
def dynamic_model():
    """Create dynamic model from the string properties schema."""
    schema = StringPropertiesModel.model_json_schema()
    return json_schema_to_pydantic_model(schema, "DynamicStringProperties")


# ============================================================================
# SUCCESS TEST CASES - PATTERN
# ============================================================================

def test_valid_patterns(dynamic_model):
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

    instance = dynamic_model.model_validate(valid_data)
    assert instance.username == "john_doe_123"
    assert instance.phone == "+14155552671"
    assert instance.postal_code == "94105"


def test_extended_postal_code(dynamic_model):
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

    instance = dynamic_model.model_validate(valid_data)
    assert instance.postal_code == "94105-1234"


# ============================================================================
# SUCCESS TEST CASES - FORMATS
# ============================================================================

def test_valid_email_formats(dynamic_model):
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
        instance = dynamic_model.model_validate(data)
        assert instance.email == email


def test_valid_datetime_formats(dynamic_model):
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
        instance = dynamic_model.model_validate(data)
        assert instance.datetime_field


def test_valid_ipv4_addresses(dynamic_model):
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
        instance = dynamic_model.model_validate(data)
        assert str(instance.ipv4_address) == ip


def test_valid_ipv6_addresses(dynamic_model):
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
        instance = dynamic_model.model_validate(data)
        # IPv6Address normalizes the address, so we compare the normalized forms
        from pydantic import IPvAnyAddress
        assert str(instance.ipv6_address) == str(IPvAnyAddress(ip))


def test_valid_hostnames(dynamic_model):
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
        instance = dynamic_model.model_validate(data)
        assert instance.hostname == hostname


# ============================================================================
# ERROR TEST CASES - PATTERN
# ============================================================================

def test_invalid_username_pattern(dynamic_model):
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
        dynamic_model.model_validate(invalid_data)
    assert "username" in str(exc_info.value)


def test_invalid_phone_pattern(dynamic_model):
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
        dynamic_model.model_validate(invalid_data)
    assert "phone" in str(exc_info.value)


def test_invalid_postal_code_pattern(dynamic_model):
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
        dynamic_model.model_validate(invalid_data)
    assert "postal_code" in str(exc_info.value)


# ============================================================================
# ERROR TEST CASES - FORMATS
# ============================================================================

def test_invalid_email_format(dynamic_model):
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
            dynamic_model.model_validate(data)
        assert "email" in str(exc_info.value)


def test_invalid_uuid_format(dynamic_model):
    """Test that invalid UUID formats are rejected."""
    invalid_uuids = [
        "not-a-uuid",
        "550e8400-e29b-41d4-a716",
        "550e8400-e29b-41d4-a716-446655440000-extra",
        "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
        # Note: "550e8400e29b41d4a716446655440000" (UUID without hyphens) is accepted by Pydantic
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
            dynamic_model.model_validate(data)
        print(f"\nValidation Error for {uuid}: {exc_info.value}")
        assert "uuid_field" in str(exc_info.value)


def test_invalid_datetime_format(dynamic_model):
    """Test that invalid datetime formats are rejected."""
    invalid_datetimes = [
        # Note: "2024-01-15" (date only) is accepted by Pydantic and converted to datetime with 00:00:00
        # Note: "2024-01-15 10:30:00" (space instead of T) is also accepted by Pydantic
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
            dynamic_model.model_validate(data)
        print(f"\nValidation Error for {dt}: {exc_info.value}")
        assert "datetime_field" in str(exc_info.value)


def test_invalid_ipv4_format(dynamic_model):
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
            dynamic_model.model_validate(data)
        print(f"\nValidation Error: {exc_info.value}")
        assert "ipv4_address" in str(exc_info.value)


# ============================================================================
# OPTIONAL FIELD TESTS
# ============================================================================

def test_optional_fields_with_none(dynamic_model):
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

    instance = dynamic_model.model_validate(valid_data)
    assert instance.optional_email is None
    assert instance.optional_pattern is None


def test_optional_fields_with_values(dynamic_model):
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

    instance = dynamic_model.model_validate(valid_data)
    assert instance.optional_email == "optional@example.com"
    assert instance.optional_pattern == "ABC"


if __name__ == "__main__":
    # Run tests with pytest
    # pytest test_openai_structured_output/test_string_properties.py -v -s
    pytest.main([__file__, "-v"])
