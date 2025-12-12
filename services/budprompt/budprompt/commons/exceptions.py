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

"""The exceptions used in the budprompt module."""

from http import HTTPStatus
from typing import Any, Dict, Optional


class BaseException(Exception):
    """Base exception class for BudPrompt."""

    def __init__(self, message: str) -> None:
        """Initialize the base exception.

        Args:
            message: Error message
        """
        self.message = message
        super().__init__(self.message)

    def __str__(self) -> str:
        """Return string representation of the exception.

        Returns:
            Formatted error message with exception class name
        """
        return f"{self.__class__.__name__}: {self.message}"


class SchemaGenerationException(BaseException):
    """Exception raised when JSON schema to Pydantic model generation fails."""

    pass


class PromptExecutionException(Exception):
    """Exception raised when prompt execution fails.

    This exception encapsulates prompt execution errors with HTTP status codes
    and OpenAI-compatible error information for proper API responses.
    """

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        err_type: Optional[str] = None,
        param: Optional[str] = None,
        code: Optional[str] = None,
    ):
        """Initialize the PromptExecutionException.

        Args:
            message: Human-readable error message
            status_code: HTTP status code (default: 500 for server errors)
            err_type: Optional OpenAI error type
            param: Optional parameter path that caused the error
            code: Optional specific error code (e.g., "invalid_schema", "execution_failed")
        """
        self.message = message
        self.status_code = status_code
        self.type = err_type
        self.param = param
        self.code = code
        super().__init__(self.message)


class TemplateRenderingException(BaseException):
    """Exception raised when template rendering fails."""

    pass


class RedisException(BaseException):
    """Exception raised when template rendering fails."""

    pass


class ClientException(Exception):
    """A custom exception class for client-related errors.

    This exception can be raised when client requests fail or encounter issues.

    Attributes:
        message (str): A human-readable string describing the error.
        status_code (int): HTTP status code for the error.
        params (dict): Optional additional parameters.
    """

    def __init__(self, message: str, status_code: int = 400, params: Optional[Dict[str, Any]] = None):
        """Initialize the ClientException with a message."""
        self.message = message
        self.status_code = status_code
        self.params = params
        super().__init__(self.message)

    def __str__(self):
        """Return just the message (no class name prefix for cleaner OTEL traces)."""
        return self.message


class OpenAIResponseException(Exception):
    """Exception for OpenAI-compatible error responses.

    This exception encapsulates all necessary information to return
    an OpenAI-compatible error response with proper HTTP status codes.

    The error type is automatically derived from the HTTP status code
    using Python's http.HTTPStatus if not explicitly provided.
    """

    def __init__(
        self,
        status_code: int,
        message: str,
        type: Optional[str] = None,
        param: Optional[str] = None,
        code: Optional[str] = None,
    ):
        """Initialize the OpenAIResponseException.

        Args:
            status_code: HTTP status code (400, 404, 500, etc.)
            message: Human-readable error message
            type: OpenAI error type (auto-derived from status_code if not provided)
            param: Optional parameter path that caused the error
            code: Optional specific error code (required, invalid_type, etc.)
        """
        self.status_code = status_code
        self.message = message
        self.type = type or self._status_to_type(status_code)
        self.param = param
        self.code = code
        super().__init__(self.message)

    @staticmethod
    def _status_to_type(status_code: int) -> str:
        """Convert HTTP status code to OpenAI error type.

        Uses Python's http.HTTPStatus to get the standard phrase and converts it
        to snake_case format expected by OpenAI.

        Args:
            status_code: HTTP status code

        Returns:
            Error type string (e.g., 'bad_request', 'not_found', 'internal_server_error')

        Examples:
            400 -> "Bad Request" -> "bad_request"
            404 -> "Not Found" -> "not_found"
            500 -> "Internal Server Error" -> "internal_server_error"
        """
        status = HTTPStatus(status_code)
        # Convert phrase to snake_case: "Not Found" -> "not_found"
        return status.phrase.lower().replace(" ", "_").replace("-", "_")


class MCPFoundryException(Exception):
    """Exception raised when there is an error with MCP Foundry service.

    This exception can be raised when MCP Foundry API calls fail or encounter issues.

    Attributes:
        message (str): A human-readable string describing the MCP Foundry error.
        status_code (int): HTTP status code from the MCP Foundry response.

    Args:
        message (str): The error message describing the MCP Foundry issue.
        status_code (int): HTTP status code (default 500).
    """

    def __init__(self, message: str, status_code: int = 500):
        """Initialize the MCPFoundryException with a message and status code."""
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

    def __str__(self):
        """Return a string representation of the MCP Foundry exception."""
        return f"MCPFoundryException (status={self.status_code}): {self.message}"
