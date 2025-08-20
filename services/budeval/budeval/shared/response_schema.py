from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel


T = TypeVar("T")


class Response(BaseModel, Generic[T]):
    success: bool
    message: str
    data: Optional[T] = None
    error: Optional[str] = None
    status_code: int = 200

    @classmethod
    def success_response(cls, data: T, message: str = "Success", status_code: int = 200) -> "Response[T]":
        """Create a success response with the given data, message, and status code.

        Args:
            data: The data to be included in the response.
            message: The message to be included in the response.
        """
        return cls(success=True, message=message, data=data, status_code=status_code)

    @classmethod
    def error_response(cls, message: str, error: str, status_code: int = 400) -> "Response[Any]":
        """Create an error response with the given message, error, and status code.

        Args:
            message: The message to be included in the response.
            error: The error to be included in the response.
        """
        return cls(success=False, message=message, error=error, status_code=status_code)
