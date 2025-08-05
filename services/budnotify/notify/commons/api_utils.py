"""Utility functions and decorators for API handling."""

import asyncio
from functools import wraps
from typing import Any, Callable, Protocol, Tuple, Type, TypeVar, runtime_checkable

from pydantic import BaseModel


T = TypeVar("T")


@runtime_checkable
class PubSubAPIEndpoint(Protocol):
    is_pubsub_api: bool
    request_model: Type[BaseModel]
    __call__: Callable[..., Any]


def pubsub_api_endpoint(request_model: Type[BaseModel]) -> Callable[[Callable[..., T]], PubSubAPIEndpoint]:
    """Mark a function as a pubsub API endpoint.

    Args:
        request_model (Type[BaseModel]): Pydantic model representing the request data.

    Returns:
        Callable: Decorated function.
    """

    def decorator(func: Callable[..., Any]) -> PubSubAPIEndpoint:
        func.is_pubsub_api = True  # type: ignore
        func.request_model = request_model  # type: ignore

        @wraps(func)
        async def wrapper(*args: Tuple[Any], **kwargs: Any) -> Any:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            return func(*args, **kwargs)

        return wrapper  # type: ignore

    return decorator
