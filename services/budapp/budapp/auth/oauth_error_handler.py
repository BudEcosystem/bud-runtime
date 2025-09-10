#  -----------------------------------------------------------------------------
#  Copyright (c) 2024 Bud Ecosystem Inc.
#  #
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#  #
#      http://www.apache.org/licenses/LICENSE-2.0
#  #
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#  -----------------------------------------------------------------------------

"""OAuth error handling utilities."""

from enum import Enum
from typing import Dict, List, Optional

from budapp.commons import logging


logger = logging.get_logger(__name__)


class OAuthErrorCode(str, Enum):
    """OAuth error codes."""

    # Provider errors
    PROVIDER_ERROR = "provider_error"
    PROVIDER_NOT_CONFIGURED = "provider_not_configured"
    PROVIDER_DISABLED = "provider_disabled"

    # Authentication errors
    INVALID_STATE = "invalid_state"
    STATE_EXPIRED = "state_expired"
    INVALID_CODE = "invalid_code"

    # Account errors
    ACCOUNT_EXISTS = "account_exists"
    ACCOUNT_NOT_FOUND = "account_not_found"
    ACCOUNT_ALREADY_LINKED = "account_already_linked"
    EMAIL_NOT_VERIFIED = "email_not_verified"
    DOMAIN_NOT_ALLOWED = "domain_not_allowed"

    # Configuration errors
    CONFIG_ERROR = "configuration_error"
    ENCRYPTION_ERROR = "encryption_error"

    # General errors
    INTERNAL_ERROR = "internal_error"
    NETWORK_ERROR = "network_error"
    TIMEOUT_ERROR = "timeout_error"


class OAuthError(Exception):
    """Base OAuth error class."""

    def __init__(
        self, code: OAuthErrorCode, message: str, provider: Optional[str] = None, details: Optional[Dict] = None
    ):
        """Initialize OAuth error.

        Args:
            code: Error code
            message: Error message
            provider: OAuth provider name
            details: Additional error details
        """
        self.code = code
        self.message = message
        self.provider = provider
        self.details = details or {}
        super().__init__(message)


# User-friendly error messages
OAUTH_ERROR_MESSAGES = {
    OAuthErrorCode.PROVIDER_ERROR: "We couldn't connect to {provider}. Please try again later.",
    OAuthErrorCode.PROVIDER_NOT_CONFIGURED: "{provider} login is not configured for your organization.",
    OAuthErrorCode.PROVIDER_DISABLED: "{provider} login has been disabled for your organization.",
    OAuthErrorCode.INVALID_STATE: "Your login session has expired. Please try logging in again.",
    OAuthErrorCode.STATE_EXPIRED: "Your login session has expired. Please try logging in again.",
    OAuthErrorCode.INVALID_CODE: "The authorization code is invalid or has expired. Please try logging in again.",
    OAuthErrorCode.ACCOUNT_EXISTS: "An account with this email already exists. Please log in with your existing account to link {provider}.",
    OAuthErrorCode.ACCOUNT_NOT_FOUND: "No account found. Please register first or contact your administrator.",
    OAuthErrorCode.ACCOUNT_ALREADY_LINKED: "Your account is already linked to {provider}.",
    OAuthErrorCode.EMAIL_NOT_VERIFIED: "Please verify your email address with {provider} before logging in.",
    OAuthErrorCode.DOMAIN_NOT_ALLOWED: "Email domain '{domain}' is not allowed. Please use an authorized email address.",
    OAuthErrorCode.CONFIG_ERROR: "OAuth configuration error. Please contact your administrator.",
    OAuthErrorCode.ENCRYPTION_ERROR: "Security configuration error. Please contact your administrator.",
    OAuthErrorCode.INTERNAL_ERROR: "An unexpected error occurred. Please try again later.",
    OAuthErrorCode.NETWORK_ERROR: "Network connection failed. Please check your internet connection and try again.",
    OAuthErrorCode.TIMEOUT_ERROR: "The request timed out. Please try again.",
}


def get_user_friendly_message(code: OAuthErrorCode, provider: Optional[str] = None, **kwargs) -> str:
    """Get user-friendly error message.

    Args:
        code: Error code
        provider: OAuth provider name
        **kwargs: Additional format parameters

    Returns:
        User-friendly error message
    """
    template = OAUTH_ERROR_MESSAGES.get(code, "An error occurred during login.")

    # Format message with provider and additional parameters
    format_params = {"provider": provider or "the provider"}
    format_params.update(kwargs)

    try:
        return template.format(**format_params)
    except Exception:
        return template


def handle_oauth_error(error: Exception, provider: Optional[str] = None) -> OAuthError:
    """Convert various exceptions to OAuthError.

    Args:
        error: Original exception
        provider: OAuth provider name

    Returns:
        OAuthError instance
    """
    # Already an OAuthError
    if isinstance(error, OAuthError):
        return error

    # Map common exceptions
    error_mapping = {
        "ConnectionError": OAuthErrorCode.NETWORK_ERROR,
        "TimeoutError": OAuthErrorCode.TIMEOUT_ERROR,
        "KeycloakAuthenticationError": OAuthErrorCode.PROVIDER_ERROR,
        "KeycloakGetError": OAuthErrorCode.CONFIG_ERROR,
    }

    error_type = type(error).__name__
    code = error_mapping.get(error_type, OAuthErrorCode.INTERNAL_ERROR)

    # Log the original error
    logger.error(f"OAuth error for provider {provider}: {error_type} - {str(error)}")

    return OAuthError(
        code=code,
        message=get_user_friendly_message(code, provider),
        provider=provider,
        details={"original_error": str(error)},
    )


class OAuthSessionValidator:
    """Validate OAuth session parameters."""

    @staticmethod
    def validate_email_domain(email: str, allowed_domains: Optional[List[str]]) -> bool:
        """Validate email domain against allowed domains.

        Args:
            email: Email address
            allowed_domains: List of allowed domains

        Returns:
            True if valid, False otherwise
        """
        if not allowed_domains:
            return True

        domain = email.split("@")[-1].lower()
        return any(domain == allowed.lower() for allowed in allowed_domains)

    @staticmethod
    def validate_state_parameter(state: str) -> bool:
        """Validate OAuth state parameter format.

        Args:
            state: State parameter

        Returns:
            True if valid, False otherwise
        """
        # State should be URL-safe base64 encoded and at least 32 characters
        if not state or len(state) < 32:
            return False

        # Check if it's URL-safe base64
        import re

        return bool(re.match(r"^[A-Za-z0-9_-]+$", state))

    @staticmethod
    def sanitize_redirect_uri(redirect_uri: str, allowed_origins: List[str]) -> Optional[str]:
        """Sanitize and validate redirect URI.

        Args:
            redirect_uri: Redirect URI to validate
            allowed_origins: List of allowed origins

        Returns:
            Sanitized URI if valid, None otherwise
        """
        from urllib.parse import urlparse, urlunparse

        try:
            parsed = urlparse(redirect_uri)

            # Check if origin is allowed
            origin = f"{parsed.scheme}://{parsed.netloc}"
            if origin not in allowed_origins:
                logger.warning(f"Redirect URI origin not allowed: {origin}")
                return None

            # Rebuild URL with only allowed components
            sanitized = urlunparse(
                (
                    parsed.scheme,
                    parsed.netloc,
                    parsed.path,
                    "",  # No params
                    parsed.query,
                    "",  # No fragment
                )
            )

            return sanitized
        except Exception as e:
            logger.error(f"Failed to sanitize redirect URI: {e}")
            return None
