"""Data sanitization utilities for budpipeline.

This module provides output sanitization and log masking utilities
to prevent credential exposure (002-pipeline-event-persistence - T027, T028).
"""

import re
from typing import Any

from budpipeline.commons.observability import get_logger

logger = get_logger(__name__)

# Sensitive data patterns (FR-039)
SENSITIVE_PATTERNS = [
    # Common credential patterns
    (r"(?i)(password|passwd|pwd)\s*[:=]\s*['\"]?([^'\"\s,}]+)", r"\1=***REDACTED***"),
    (r"(?i)(secret|token|api[_-]?key|apikey)\s*[:=]\s*['\"]?([^'\"\s,}]+)", r"\1=***REDACTED***"),
    (r"(?i)(auth|authorization)\s*[:=]\s*['\"]?([^'\"\s,}]+)", r"\1=***REDACTED***"),
    (r"(?i)(credential|credentials)\s*[:=]\s*['\"]?([^'\"\s,}]+)", r"\1=***REDACTED***"),
    # Connection strings
    (r"(?i)(mongodb|postgres|mysql|redis|amqp)://[^@]+@", r"\1://***:***@"),
    (r"(?i)Server=([^;]+);.*Password=([^;]+)", r"Server=\1;...Password=***REDACTED***"),
    # Cloud provider keys
    (r"AKIA[0-9A-Z]{16}", "***AWS_KEY_REDACTED***"),  # AWS Access Key
    (
        r"(?i)aws[_-]?secret[_-]?access[_-]?key\s*[:=]\s*['\"]?([^'\"\s,}]+)",
        "aws_secret_access_key=***REDACTED***",
    ),
    # API keys with common formats
    (r"sk-[A-Za-z0-9]{32,}", "***OPENAI_KEY_REDACTED***"),  # OpenAI
    (r"sk_live_[A-Za-z0-9]{24,}", "***STRIPE_KEY_REDACTED***"),  # Stripe live
    (r"sk_test_[A-Za-z0-9]{24,}", "***STRIPE_KEY_REDACTED***"),  # Stripe test
    (r"ghp_[A-Za-z0-9]{36,}", "***GITHUB_PAT_REDACTED***"),  # GitHub PAT
    (r"gho_[A-Za-z0-9]{36,}", "***GITHUB_OAUTH_REDACTED***"),  # GitHub OAuth
    (r"glpat-[A-Za-z0-9]{20,}", "***GITLAB_PAT_REDACTED***"),  # GitLab PAT
    # Bearer tokens
    (
        r"(?i)bearer\s+[A-Za-z0-9\-_=]+\.[A-Za-z0-9\-_=]+\.[A-Za-z0-9\-_=]+",
        "Bearer ***JWT_REDACTED***",
    ),
    (r"(?i)bearer\s+[A-Za-z0-9\-_]{20,}", "Bearer ***TOKEN_REDACTED***"),
    # Base64-encoded secrets (long strings that might be secrets)
    (r"['\"]?[A-Za-z0-9+/]{40,}={0,2}['\"]?(?=\s*[,}\]])", "***BASE64_REDACTED***"),
    # Private keys
    (
        r"-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |DSA )?PRIVATE KEY-----",
        "***PRIVATE_KEY_REDACTED***",
    ),
    (r"-----BEGIN CERTIFICATE-----[\s\S]*?-----END CERTIFICATE-----", "***CERTIFICATE_REDACTED***"),
]

# Keys that should have their values redacted entirely
SENSITIVE_KEYS = {
    "password",
    "passwd",
    "pwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "api-key",
    "auth_token",
    "access_token",
    "refresh_token",
    "private_key",
    "secret_key",
    "credential",
    "credentials",
    "bearer",
    "authorization",
    "aws_secret_access_key",
    "aws_session_token",
    "db_password",
    "database_password",
    "connection_string",
}


def sanitize_string(value: str) -> str:
    """Sanitize a string by redacting sensitive patterns.

    Args:
        value: String to sanitize.

    Returns:
        Sanitized string with sensitive data redacted.
    """
    result = value
    for pattern, replacement in SENSITIVE_PATTERNS:
        result = re.sub(pattern, replacement, result)
    return result


def sanitize_outputs(outputs: dict[str, Any] | None) -> dict[str, Any] | None:
    """Sanitize step outputs to remove credentials and secrets.

    Recursively processes nested dictionaries and lists, redacting
    values for sensitive keys and applying pattern matching to strings (FR-039).

    Args:
        outputs: Dictionary of step outputs.

    Returns:
        Sanitized dictionary with sensitive data redacted.
    """
    if outputs is None:
        return None

    return _sanitize_value(outputs)


def _sanitize_value(value: Any) -> Any:
    """Recursively sanitize a value.

    Args:
        value: Value to sanitize (can be any type).

    Returns:
        Sanitized value.
    """
    if value is None:
        return None

    if isinstance(value, dict):
        return _sanitize_dict(value)

    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]

    if isinstance(value, str):
        return sanitize_string(value)

    # For other types (int, float, bool, etc.), return as-is
    return value


def _sanitize_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Sanitize a dictionary.

    Args:
        data: Dictionary to sanitize.

    Returns:
        Sanitized dictionary.
    """
    result = {}
    for key, value in data.items():
        key_lower = key.lower().replace("-", "_")

        # Check if key is sensitive
        if key_lower in SENSITIVE_KEYS:
            result[key] = "***REDACTED***"
        else:
            result[key] = _sanitize_value(value)

    return result


def mask_sensitive_data(data: Any, depth: int = 0, max_depth: int = 10) -> Any:
    """Mask sensitive data in logs and error messages.

    Similar to sanitize_outputs but more aggressive for logging purposes (FR-038).

    Args:
        data: Data to mask (any type).
        depth: Current recursion depth.
        max_depth: Maximum recursion depth.

    Returns:
        Masked data.
    """
    if depth > max_depth:
        return "***MAX_DEPTH_EXCEEDED***"

    if data is None:
        return None

    if isinstance(data, dict):
        return {
            key: (
                "***REDACTED***"
                if key.lower().replace("-", "_") in SENSITIVE_KEYS
                else mask_sensitive_data(value, depth + 1, max_depth)
            )
            for key, value in data.items()
        }

    if isinstance(data, list):
        return [mask_sensitive_data(item, depth + 1, max_depth) for item in data]

    if isinstance(data, str):
        return sanitize_string(data)

    return data


def sanitize_error_message(error: str | Exception) -> str:
    """Sanitize error message to remove sensitive data.

    Args:
        error: Error string or exception.

    Returns:
        Sanitized error message string.
    """
    message = str(error) if isinstance(error, Exception) else error
    return sanitize_string(message)


def create_safe_log_context(**kwargs: Any) -> dict[str, Any]:
    """Create a safe logging context with masked sensitive data.

    Useful for structured logging where you want to include
    context that might contain sensitive data.

    Args:
        **kwargs: Key-value pairs for log context.

    Returns:
        Dictionary with sensitive data masked.
    """
    return mask_sensitive_data(kwargs)


def is_sensitive_key(key: str) -> bool:
    """Check if a key name indicates sensitive data.

    Args:
        key: Key name to check.

    Returns:
        True if key is sensitive, False otherwise.
    """
    return key.lower().replace("-", "_") in SENSITIVE_KEYS


def redact_in_json(json_str: str) -> str:
    """Redact sensitive values in a JSON string.

    Uses pattern matching since the string might not be valid JSON.

    Args:
        json_str: JSON string to redact.

    Returns:
        Redacted JSON string.
    """
    return sanitize_string(json_str)


# Log filter for structlog
def sanitize_log_processor(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Structlog processor to sanitize log events.

    Add this to structlog processors to automatically mask sensitive data (FR-038).

    Args:
        logger: Logger instance.
        method_name: Log method name.
        event_dict: Event dictionary.

    Returns:
        Sanitized event dictionary.
    """
    return mask_sensitive_data(event_dict)
