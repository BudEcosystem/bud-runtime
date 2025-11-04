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

"""Defines custom exceptions to handle specific error cases gracefully."""

from functools import wraps
from typing import Any, Callable, Optional

from . import logging
from .async_utils import dispatch_async
from .types import Logger


logger = logging.get_logger(__name__)


class SuppressAndLog:
    """Suppress specified exceptions and log error messages.

    This context manager and decorator handle exceptions by suppressing them and logging an error message.
    Use it to prevent certain exceptions from propagating and ensure that relevant error information is logged.

    Attributes:
        exceptions (tuple): Tuple of exception types to be suppressed.
        logger (Optional[logging.BoundLogger]): Logger instance used to log error messages.
        default_return (Any): Default value returned when an exception is suppressed.
        log_msg (str): Custom message to log when an exception is suppressed.

    Args:
        *exceptions: Exception types to be suppressed.
        _logger (Optional[logging.BoundLogger], default=None): Logger instance for logging errors.
        default_return (Any, default=None): Default return value when an exception is suppressed.
        log_msg (str, default=None): Custom error message for logging.
    """

    def __init__(
        self,
        *exceptions: Any,
        _logger: Optional[Logger] = None,
        default_return: Any = None,
        log_msg: Optional[str] = None,
    ):
        """Initialize the SuppressAndLog instance with exception types, a logger, a default return value, and a log message.

        Args:
            *exceptions: Exception types to be suppressed.
            _logger (Optional[logging.BoundLogger], default=None): Logger instance for logging errors.
            default_return (Any, default=None): Default return value when an exception is suppressed.
            log_msg (str, default=None): Custom error message for logging.
        """
        self.exceptions = exceptions
        self.logger = _logger or logger
        self.default_return = default_return
        self.log_msg = log_msg or "An error occurred"

    def __enter__(self) -> None:
        """Prepare the context for exception suppression and logging.

        This method is a no-op for this context manager.
        """
        pass

    def __exit__(self, exc_type: type, exc_value: Exception, traceback: Any) -> bool:
        """Handle exceptions that occur within the context, log the error message, and suppress the specified exceptions.

        Args:
            exc_type (type): The type of the exception raised.
            exc_value (Exception): The exception instance raised.
            traceback (Any): The traceback object.

        Returns:
            bool: `True` to suppress the exception, `False` otherwise.
        """
        if exc_type is not None and issubclass(exc_type, self.exceptions):
            if self.logger is not None:
                self.logger.error(self.log_msg + ": %s:'%s'", exc_type.__name__, exc_value)
            return True  # Suppresses the exception

        # Do not suppress the exception if it's not one of the specified types
        return False

    def __call__(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Decorate a function to suppress specified exceptions and log errors.

        Args:
            func (Callable): The function to be decorated.

        Returns:
            Callable: The decorated function that suppresses specified exceptions and logs errors.
        """

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            self.log_msg = f"An error occurred in {func.__name__}"
            result = self.default_return
            with self:
                result = dispatch_async(func, *args, **kwargs)

            return result

        return wrapper


class DatabaseException(Exception):
    """A custom exception class for database-related errors.

    This exception can be raised when database operations fail or encounter issues.

    Attributes:
        message (str): A human-readable string describing the database error.

    Args:
        message (str): The error message describing the database issue.
    """

    def __init__(self, message: str):
        """Initialize the DatabaseException with a message."""
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        """Return a string representation of the database exception."""
        return f"DatabaseException: {self.message}"


class ClientException(Exception):
    """A custom exception class for client-related errors.

    This exception can be raised when client requests fail or encounter issues.

    Attributes:
        message (str): A human-readable string describing the database error.

    Args:
        message (str): The error message describing the database issue.
    """

    def __init__(self, message: str, status_code: int = 400):
        """Initialize the ClientException with a message."""
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

    def __str__(self):
        """Return a string representation of the database exception."""
        return f"ClientException: {self.message}"


class RedisException(Exception):
    """A custom exception class for Redis-related errors.

    This exception can be raised when Redis operations fail or encounter issues.

    Attributes:
        message (str): A human-readable string describing the Redis error.

    Args:
        message (str): The error message describing the Redis issue.
    """

    def __init__(self, message: str):
        """Initialize the RedisException with a message."""
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        """Return a string representation of the Redis exception."""
        return f"RedisException: {self.message}"


class MinioException(Exception):
    """A custom exception class for minio-related errors.

    This exception can be raised when minio operations fail or encounter issues.

    Attributes:
        message (str): A human-readable string describing the minio error.

    Args:
        message (str): The error message describing the Redis issue.
    """

    def __init__(self, message: str):
        """Initialize the MinioException with a message."""
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        """Return a string representation of the Redis exception."""
        return f"MinioException: {self.message}"


class BudNotifyException(Exception):
    """BudNotifyException is raised when there is an error in the budnotify server."""

    def __init__(self, message: str = "Error found from budnotify server"):
        self.message = message


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
