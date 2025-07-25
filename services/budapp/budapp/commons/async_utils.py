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

"""Provides utility functions for managing asynchronous tasks."""

import asyncio
import re
from typing import Any, Awaitable, Callable, List, Tuple, TypeVar, Union

from fastapi import Header, status
from fastapi.security.http import HTTPAuthorizationCredentials, get_authorization_scheme_param
from sqlalchemy.orm import Session
from typing_extensions import Annotated

from ..user_ops.schemas import User


T = TypeVar("T")


def dispatch_async(func: Callable[..., Any], *args: Tuple[Any], **kwargs: Any) -> Union[T, Awaitable[T]]:
    """Dispatch a function call asynchronously, ensuring compatibility with both synchronous and asynchronous functions.

    Wrap the given function in an asynchronous wrapper if it is a coroutine function. Execute the wrapped function
    asynchronously if the event loop is running; otherwise, run the function using `asyncio.run`. For non-coroutine
    functions, execute them normally.

    Args:
        func (Callable): The function to dispatch. Can be either a coroutine function or a regular function.
        *args: Positional arguments to pass to the function.
        **kwargs: Keyword arguments to pass to the function.

    Returns:
        Any: The result of the function call.

    Example:
        ```python
        async def async_func(x):
            return x + 1


        def sync_func(x):
            return x + 1


        result_async = dispatch_async(async_func, 10)  # Asynchronous call
        result_sync = dispatch_async(sync_func, 10)  # Synchronous call
        ```
    """

    async def async_wrapper() -> Any:
        return await func(*args, **kwargs)

    if asyncio.iscoroutinefunction(func):
        try:
            event_loop = asyncio.get_running_loop()
            result = async_wrapper() if event_loop.is_running() else asyncio.run(func(*args, **kwargs))
        except RuntimeError:
            event_loop = asyncio.get_event_loop()
            result = event_loop.run_until_complete(func(*args, **kwargs))
    else:
        result = func(*args, **kwargs)

    return result


async def check_file_extension(filename: str, allowed_extensions: List[str]) -> bool:
    """Check if the file has an allowed extension.

    Args:
        filename (str): Name of the file to validate.
        allowed_extensions (list[str]): List of allowed extensions (without dot, e.g. ['yaml', 'yml']).

    Returns:
        bool: True if file extension is allowed, False otherwise.
    """
    if not filename or "." not in filename:
        return False

    # Get the file extension from the filename
    file_extension = filename.split(".")[-1].lower()

    # Convert allowed extensions to lowercase for case-insensitive comparison
    allowed_extensions = [ext.lower() for ext in allowed_extensions]

    return file_extension in allowed_extensions


async def get_user_from_auth_header(authorization: Annotated[str, Header()], session: Session) -> User:
    """Get the user from the authorization header.

    Args:
        authorization (str): The authorization header.
        session (Session): The database session.

    Returns:
        User: The user.
    """
    from .dependencies import get_current_active_user, get_current_user
    from .exceptions import ClientException

    try:
        scheme, credentials = get_authorization_scheme_param(authorization)
        token = HTTPAuthorizationCredentials(scheme=scheme, credentials=credentials)
        db_user = await get_current_user(token, session)
        current_user = await get_current_active_user(db_user)
        return current_user
    except ClientException as e:
        raise e
    except Exception as e:
        raise ClientException(
            status_code=status.HTTP_401_UNAUTHORIZED, message="Invalid authentication credentials"
        ) from e


async def get_range_label(
    value: float, target: Union[int, List[int]], tolerance: float = 0, higher_is_better: bool = True
) -> str:
    """Determine if a value matches the target or is within the target range.

    Args:
        value: The float value to check
        target: Either a single integer target or list of two integers defining a range [min, max]
        tolerance: Percentage tolerance for single target comparison (default: 10%)

    Returns:
        str: "Better Range"/"Worse Range"/"Expected Range" based on comparison

    Raises:
        ValueError: If target is neither an integer nor a list of exactly 2 integers
    """
    # Handle single target value
    if isinstance(target, (int, float)):
        tolerance_range = target * tolerance
        min_value = target - tolerance_range
        max_value = target + tolerance_range

    # Handle target range
    elif isinstance(target, list) and len(target) == 2:
        min_value, max_value = target

    else:
        raise ValueError("Target must be either a single number or a list of two numbers")

    if value < min_value:
        return "Worse" if higher_is_better else "Better"
    elif value > max_value:
        return "Better" if higher_is_better else "Worse"
    else:
        return "Expected"


async def count_words(source_text: str) -> int:
    """Count words in license file."""
    text = re.findall(r"\b\w+\b", re.sub(r"[\n\r\t\s]+", " ", source_text.strip()))
    return len(text)
