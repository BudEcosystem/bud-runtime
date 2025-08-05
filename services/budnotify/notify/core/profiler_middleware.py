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

"""Defines a middleware for profiling the application."""

import asyncio
import cProfile
import functools
import io
import pstats
import time
import tracemalloc
from typing import Any, Callable

from fastapi import Request
from memory_profiler import profile
from starlette.middleware.base import BaseHTTPMiddleware

from notify.commons import logging


logger = logging.get_logger(__name__)


@profile
async def memory_profiler_exec(func: Callable, *args: Any, **kwargs: Any) -> Any:
    """Execute a function while profiling memory usage.

    Args:
        func (Callable): The function to be profiled.
        *args: Variable length argument list for the function.
        **kwargs: Arbitrary keyword arguments for the function.

    Returns:
        Any: The result of the function execution.
    """
    logger.debug("Performing memory profiling with memory_profiler package")
    if asyncio.iscoroutinefunction(func):
        return await func(*args, **kwargs)
    else:
        return func(*args, **kwargs)


def common_profiler(func: Callable) -> Callable:
    """Profile both time and memory usage of a function.

    Args:
        func (Callable): The function to be profiled.

    Returns:
        Callable: Wrapped function with profiling capabilities.
    """

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any):
        """Wrap a function for profiling."""
        # Initialize profilers
        profiler = cProfile.Profile()
        profiler.enable()
        start_time = time.time()
        tracemalloc.start()
        start_mem = tracemalloc.get_traced_memory()[1]

        # Handle both async and sync functions
        result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)

        # Collect profiling data
        peak_mem = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()
        end_time = time.time()
        profiler.disable()

        # Process profiling results
        s = io.StringIO()
        ps = pstats.Stats(profiler, stream=s).sort_stats("cumulative")
        ps.print_stats(10)
        total_time = end_time - start_time
        mem_usage_bytes = peak_mem - start_mem
        mem_usage_mb = mem_usage_bytes / (1024 * 1024)

        logger.debug(f"Total execution time: {total_time:.4f} seconds")
        logger.debug(f"Detailed cProfile results:\n{s.getvalue()}")

        # Perform and log memory profiling
        logger.debug(f"Peak memory usage as per tracemalloc: {mem_usage_mb:.4f} MB")
        await memory_profiler_exec(func, *args, **kwargs)

        return result

    return wrapper


class ProfilerMiddleware(BaseHTTPMiddleware):
    """Middleware for applying profiling to FastAPI requests."""

    @common_profiler
    async def dispatch(self, request: Request, call_next):
        """Dispatch method to handle incoming requests with profiling.

        Args:
            request (Request): The incoming FastAPI request.
            call_next (Callable): The next callable in the middleware chain.

        Returns:
            Any: The response from the next callable.
        """
        logger.debug(f"Profiling request: {request.method} {request.url.path}")
        response = await call_next(request)
        logger.debug(f"Completed profiling for request: {request.method} {request.url.path}")
        return response
