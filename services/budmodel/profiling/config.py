import asyncio
import cProfile
import functools
import io
import pstats
import time
import tracemalloc
from typing import Any, Callable

from budmicroframe.commons import logging
from memory_profiler import profile


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

        print(f"Total execution time: {total_time:.4f} seconds")
        print(f"Detailed cProfile results:\n{s.getvalue()}")

        # Perform and log memory profiling
        print(f"Peak memory usage as per tracemalloc: {mem_usage_mb:.4f} MB")
        await memory_profiler_exec(func, *args, **kwargs)

        return result

    return wrapper
