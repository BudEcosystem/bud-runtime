"""Utility functions and decorators for API handling."""

import asyncio
from functools import wraps
from typing import Any, Callable, Protocol, Tuple, Type, TypeVar, runtime_checkable

from fastapi import Request
from pydantic import BaseModel

from .config import app_settings


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


def get_oauth_base_url(request: Request) -> str:
    """Get base URL for OAuth operations with HTTPS/HTTP logic.

    Args:
        request: FastAPI Request object

    Returns:
        str: Base URL with proper scheme (http/https)
    """
    base_url = str(request.base_url).rstrip("/")

    # Check if we should force HTTP for OAuth operations
    if app_settings.use_http_only_oauth:
        # Replace https with http if present
        base_url = base_url.replace("https://", "http://")
    else:
        # Default behavior: force HTTPS for OAuth security
        base_url = base_url.replace("http://", "https://")

    return base_url
