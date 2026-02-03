"""
Custom assertions for E2E tests.

Provides reusable assertion functions for common validation patterns.
"""

from typing import Any, Dict, Optional
import httpx


def assert_success_response(
    response: httpx.Response,
    expected_status: int = 200,
    message: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Assert that a response is successful.

    Args:
        response: HTTP response
        expected_status: Expected status code (default 200)
        message: Optional custom error message

    Returns:
        Response JSON data

    Raises:
        AssertionError: If response is not successful
    """
    error_msg = message or f"Expected {expected_status}, got {response.status_code}"
    assert response.status_code == expected_status, f"{error_msg}: {response.text}"
    return response.json()


def assert_error_response(
    response: httpx.Response,
    expected_status: int,
    expected_error: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Assert that a response is an error with expected status.

    Args:
        response: HTTP response
        expected_status: Expected error status code
        expected_error: Optional expected error message substring

    Returns:
        Response JSON data (if available)

    Raises:
        AssertionError: If response status doesn't match
    """
    assert response.status_code == expected_status, (
        f"Expected {expected_status}, got {response.status_code}: {response.text}"
    )

    if expected_error and response.text:
        assert expected_error.lower() in response.text.lower(), (
            f"Expected error containing '{expected_error}', got: {response.text}"
        )

    try:
        return response.json()
    except Exception:
        return {}


def assert_token_valid(data: Dict[str, Any]) -> None:
    """
    Assert that token data contains valid tokens.

    Args:
        data: Response data containing tokens (may be nested under 'token' key)

    Raises:
        AssertionError: If tokens are missing or invalid
    """
    # Handle nested token structure
    token_data = data.get("token", data)

    assert "access_token" in token_data, "Response missing access_token"
    assert token_data["access_token"], "access_token is empty"
    assert isinstance(token_data["access_token"], str), "access_token must be a string"

    assert "refresh_token" in token_data, "Response missing refresh_token"
    assert token_data["refresh_token"], "refresh_token is empty"
    assert isinstance(token_data["refresh_token"], str), (
        "refresh_token must be a string"
    )


def assert_user_data_valid(
    data: Dict[str, Any],
    expected_email: str,
    expected_name: Optional[str] = None,
    expected_role: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Assert that user data is valid and matches expected values.

    Args:
        data: Response data (may have 'user' nested key)
        expected_email: Expected user email
        expected_name: Optional expected user name
        expected_role: Optional expected user role

    Returns:
        Extracted user data dict

    Raises:
        AssertionError: If user data is invalid or doesn't match
    """
    # Handle nested user data (API returns {"user": {...}})
    user_data = data.get("user", data)

    # Required fields
    assert "id" in user_data, "Response missing 'id' field"
    assert user_data["id"] is not None, "User ID should not be None"

    assert "email" in user_data, "Response missing 'email' field"
    assert user_data["email"] == expected_email, (
        f"Email mismatch: expected {expected_email}, got {user_data['email']}"
    )

    # Optional field validations
    if expected_name is not None:
        assert "name" in user_data, "Response missing 'name' field"
        assert user_data["name"] == expected_name, (
            f"Name mismatch: expected {expected_name}, got {user_data.get('name')}"
        )

    if expected_role is not None:
        assert "role" in user_data, "Response missing 'role' field"
        assert user_data["role"] == expected_role, (
            f"Role mismatch: expected {expected_role}, got {user_data.get('role')}"
        )

    return user_data


def assert_user_profile_complete(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Assert that user profile contains all expected fields.

    Args:
        data: Response data (may have 'user' nested key)

    Returns:
        Extracted user data dict

    Raises:
        AssertionError: If required fields are missing
    """
    # Handle nested user data
    user_data = data.get("user", data)

    # Required profile fields
    required_fields = ["id", "email", "name", "role", "status"]
    for field in required_fields:
        assert field in user_data, f"Profile missing required field: {field}"
        assert user_data[field] is not None, f"Field '{field}' should not be None"

    # Validate field types
    assert isinstance(user_data["id"], str), "User ID should be a string (UUID)"
    assert isinstance(user_data["email"], str), "Email should be a string"
    assert isinstance(user_data["name"], str), "Name should be a string"
    assert isinstance(user_data["role"], str), "Role should be a string"
    assert isinstance(user_data["status"], str), "Status should be a string"

    return user_data


def assert_unauthorized(response: httpx.Response) -> None:
    """
    Assert that a response is 401 Unauthorized.

    Args:
        response: HTTP response

    Raises:
        AssertionError: If response is not 401
    """
    assert response.status_code == 401, (
        f"Expected 401 Unauthorized, got {response.status_code}: {response.text}"
    )


def assert_forbidden(response: httpx.Response) -> None:
    """
    Assert that a response is 403 Forbidden.

    Args:
        response: HTTP response

    Raises:
        AssertionError: If response is not 403
    """
    assert response.status_code == 403, (
        f"Expected 403 Forbidden, got {response.status_code}: {response.text}"
    )


def assert_rate_limited(response: httpx.Response) -> None:
    """
    Assert that a response is 429 Too Many Requests.

    Args:
        response: HTTP response

    Raises:
        AssertionError: If response is not 429
    """
    assert response.status_code == 429, (
        f"Expected 429 Too Many Requests, got {response.status_code}: {response.text}"
    )


def assert_validation_error(response: httpx.Response) -> Dict[str, Any]:
    """
    Assert that a response is 422 Validation Error.

    Args:
        response: HTTP response

    Returns:
        Error details from response

    Raises:
        AssertionError: If response is not 422
    """
    assert response.status_code == 422, (
        f"Expected 422 Validation Error, got {response.status_code}: {response.text}"
    )
    return response.json()


def assert_conflict(response: httpx.Response) -> Dict[str, Any]:
    """
    Assert that a response is 409 Conflict.

    Args:
        response: HTTP response

    Returns:
        Error details from response

    Raises:
        AssertionError: If response is not 409
    """
    assert response.status_code == 409, (
        f"Expected 409 Conflict, got {response.status_code}: {response.text}"
    )
    try:
        return response.json()
    except Exception:
        return {}
