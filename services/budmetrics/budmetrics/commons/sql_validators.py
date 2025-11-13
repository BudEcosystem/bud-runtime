"""SQL injection prevention utilities for ClickHouse queries.

This module provides validation functions and custom Pydantic types to prevent SQL injection
by validating identifiers (metric names, field names, table names, column names) and UUIDs
before they are used in dynamic SQL query construction.

Key Features:
- Validates identifiers contain only safe characters (alphanumeric, underscore, hyphen, colon, period)
- Validates UUIDs match expected format
- Provides reusable Pydantic types for automatic validation in FastAPI endpoints
- Safely constructs SQL IN clause lists with proper escaping

Usage:
    # Option 1: Use validation functions directly
    from budmetrics.commons.sql_validators import validate_identifier, safe_sql_list

    metric_name = validate_identifier(user_input, "metric_name")
    query = f"SELECT * FROM metrics WHERE name IN ({safe_sql_list(validated_list)})"

    # Option 2: Use Pydantic types in schemas (recommended)
    from budmetrics.commons.sql_validators import ClusterUUID, SafeIdentifierList

    class MyRequest(BaseModel):
        cluster_id: ClusterUUID  # Automatically validated!
        metric_names: SafeIdentifierList  # Automatically validated!
"""

import re
from typing import Annotated, List, Optional

from fastapi import HTTPException
from pydantic import AfterValidator
from starlette.status import HTTP_400_BAD_REQUEST


# ============================================================================
# Regex Patterns
# ============================================================================

# SQL injection prevention: Pattern for validating identifiers (metric names, field names, cluster IDs)
# Allows alphanumeric characters, underscores, hyphens, colons (for metric names), and periods (for nested fields)
SAFE_IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z0-9_:\.\-]+$")

# UUID pattern for cluster IDs
UUID_PATTERN = re.compile(r"^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$")


# ============================================================================
# Core Validation Functions
# ============================================================================


def validate_identifier(value: str, field_name: str = "identifier") -> str:
    """Validate that a string is safe to use as an SQL identifier.

    Prevents SQL injection by ensuring only alphanumeric characters,
    underscores, hyphens, colons, and periods are allowed.

    Args:
        value: The identifier to validate
        field_name: Name of the field for error messages

    Returns:
        The validated identifier

    Raises:
        HTTPException: If the identifier contains unsafe characters
    """
    if not value or not SAFE_IDENTIFIER_PATTERN.match(value):
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field_name}: '{value}'. Only alphanumeric characters, "
            "underscores, hyphens, colons, and periods are allowed.",
        )
    return value


def validate_identifiers(values: List[str], field_name: str = "identifiers") -> List[str]:
    """Validate a list of identifiers.

    Args:
        values: List of identifiers to validate
        field_name: Name of the field for error messages

    Returns:
        List of validated identifiers

    Raises:
        HTTPException: If any identifier contains unsafe characters
    """
    return [validate_identifier(v, field_name) for v in values]


def validate_cluster_id(cluster_id: str) -> str:
    """Validate that a cluster ID is a valid UUID.

    Args:
        cluster_id: The cluster ID to validate

    Returns:
        The validated cluster ID

    Raises:
        HTTPException: If the cluster ID is not a valid UUID
    """
    if not UUID_PATTERN.match(cluster_id):
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST, detail=f"Invalid cluster_id: '{cluster_id}'. Must be a valid UUID."
        )
    return cluster_id


def safe_sql_list(values: List[str], field_name: str = "values") -> str:
    """Safely construct an SQL IN clause list from validated values.

    Args:
        values: List of pre-validated values
        field_name: Name of the field for validation error messages (unused, kept for compatibility)

    Returns:
        SQL-safe comma-separated quoted list

    Note:
        Values MUST be validated before calling this function.
        This function adds an additional safety layer by escaping single quotes.

    Example:
        >>> safe_sql_list(["metric1", "metric2"])
        "'metric1', 'metric2'"
    """
    # Additional safety: escape any single quotes in values
    escaped = [v.replace("'", "''") for v in values]
    # Return comma-separated quoted list
    return ", ".join([f"'{v}'" for v in escaped])


# ============================================================================
# Pydantic Validator Functions
# ============================================================================
# These functions are designed to work with Pydantic's AfterValidator
# They raise HTTPException instead of ValueError for FastAPI compatibility


def _validate_safe_identifier(v: str) -> str:
    """Pydantic validator for a single safe identifier.

    Args:
        v: Value to validate

    Returns:
        Validated identifier

    Raises:
        HTTPException: If validation fails
    """
    return validate_identifier(v, "identifier")


def _validate_safe_identifiers(v: List[str]) -> List[str]:
    """Pydantic validator for a list of safe identifiers.

    Args:
        v: List of values to validate

    Returns:
        List of validated identifiers

    Raises:
        HTTPException: If any validation fails
    """
    return [validate_identifier(item, "identifier") for item in v]


def _validate_cluster_uuid(v: str) -> str:
    """Pydantic validator for a cluster UUID.

    Args:
        v: Value to validate

    Returns:
        Validated UUID

    Raises:
        HTTPException: If validation fails
    """
    return validate_cluster_id(v)


def _validate_cluster_uuids(v: List[str]) -> List[str]:
    """Pydantic validator for a list of cluster UUIDs.

    Args:
        v: List of values to validate

    Returns:
        List of validated UUIDs

    Raises:
        HTTPException: If any validation fails
    """
    return [validate_cluster_id(item) for item in v]


def _validate_optional_safe_identifiers(v: Optional[List[str]]) -> Optional[List[str]]:
    """Pydantic validator for an optional list of safe identifiers.

    Args:
        v: Optional list of values to validate

    Returns:
        List of validated identifiers, or None if input is None

    Raises:
        HTTPException: If any validation fails
    """
    return _validate_safe_identifiers(v) if v is not None else None


# ============================================================================
# Custom Pydantic Types (Annotated)
# ============================================================================
# These types can be used directly in Pydantic models for automatic validation
# Example: cluster_id: ClusterUUID = Field(..., description="Cluster ID")

SafeIdentifier = Annotated[str, AfterValidator(_validate_safe_identifier)]
"""A string validated to contain only safe SQL identifier characters.

Use this type in Pydantic models for fields like metric names, table names,
column names, or any other identifier used in SQL queries.

Example:
    class MySchema(BaseModel):
        metric_name: SafeIdentifier
"""

SafeIdentifierList = Annotated[List[str], AfterValidator(_validate_safe_identifiers)]
"""A list of strings validated to contain only safe SQL identifier characters.

Use this type in Pydantic models for fields like lists of metric names,
field names, or any other list of identifiers used in SQL queries.

Example:
    class MySchema(BaseModel):
        metric_names: SafeIdentifierList
"""

ClusterUUID = Annotated[str, AfterValidator(_validate_cluster_uuid)]
"""A string validated to be a properly formatted UUID (cluster ID).

Use this type in Pydantic models for cluster ID fields.

Example:
    class MySchema(BaseModel):
        cluster_id: ClusterUUID
"""

ClusterUUIDList = Annotated[List[str], AfterValidator(_validate_cluster_uuids)]
"""A list of strings validated to be properly formatted UUIDs (cluster IDs).

Use this type in Pydantic models for fields that accept multiple cluster IDs.

Example:
    class MySchema(BaseModel):
        cluster_ids: ClusterUUIDList
"""

OptionalSafeIdentifierList = Annotated[Optional[List[str]], AfterValidator(_validate_optional_safe_identifiers)]
"""An optional list of strings validated to contain only safe SQL identifier characters.

Use this type in Pydantic models for optional fields like optional grouping fields.

Example:
    class MySchema(BaseModel):
        group_by: OptionalSafeIdentifierList = None
"""
