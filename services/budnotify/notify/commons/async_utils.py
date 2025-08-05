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
from typing import Any, Callable, Tuple


def dispatch_async(func: Callable[..., Any], *args: Tuple[Any], **kwargs: Any) -> Any:
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
