import asyncio
import time
from functools import wraps
from typing import Any, Awaitable, Callable, Dict, Optional, Tuple, Type, TypeVar, Union, cast

from . import logging
from .async_utils import dispatch_async


logger = logging.get_logger(__name__)

T = TypeVar("T")


class RetryWithModifiedParams(Exception):
    """Exception raised to signal that a retry should be attempted with modified parameters.

    This exception can be used to indicate that a function should be retried with different
    parameters than the original call.

    Attributes:
        message (str): The error message.
        details (dict): Additional details about the exception, defaulting to an empty dictionary.
    """

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Initialize the RetryWithModifiedParams exception.

        Args:
            message (str): The error message.
            details (dict, optional): Additional details about the exception. Defaults to None.
        """
        super().__init__(message)
        self.details: Dict[str, Any] = details or {}


class AbortRetry(Exception):
    """Exception raised to signal that retry attempts should be aborted.

    This exception can be used to immediately stop any further retry attempts and
    propagate the exception up the call stack.
    """

    pass


def retry(
    max_attempts: Optional[int] = 3,
    max_elapsed_time: Optional[float] = None,
    delay: Optional[float] = None,
    backoff_factor: Optional[float] = 2,
    max_delay: Optional[float] = None,
    exceptions_to_retry: Union[Type[Exception], Tuple[Type[Exception], ...]] = Exception,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Retry a function with exponential backoff.

    Args:
        max_attempts (int, optional): Maximum number of retry attempts. Defaults to 3.
        max_elapsed_time (float, optional): Maximum total time allowed for retries. Defaults to None.
        delay (float, optional): Initial delay between retries in seconds. Defaults to None.
        backoff_factor (float, optional): Multiplier applied to delay between attempts. Defaults to 2.
        max_delay (float, optional): Maximum delay between retries in seconds. Defaults to None.
        exceptions_to_retry (Union[Type[Exception], Tuple[Type[Exception], ...]], optional):
            Exceptions that trigger a retry. Defaults to Exception.

    Returns:
        Callable: Decorated function with retry logic.
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            return cast(T, _retry_logic(func, False, *args, **kwargs))

        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            return await cast(Awaitable[T], _retry_logic(func, True, *args, **kwargs))

        return cast(Callable[..., T], async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper)

    def _retry_logic(
        func: Callable[..., Union[T, Awaitable[T]]], is_async: bool, *args: Any, **kwargs: Any
    ) -> Union[T, Awaitable[T]]:
        """Implement the retry logic for both synchronous and asynchronous functions.

        Args:
            func (Callable): The function to be retried.
            is_async (bool): Whether the function is asynchronous.
            *args: Positional arguments for the function.
            **kwargs: Keyword arguments for the function.

        Returns:
            Union[T, Awaitable[T]]: The result of the function call.

        Raises:
            Exception: If the retry limit is reached.
        """
        retry_config: Dict[str, Any] = kwargs.pop("retry_config", {})
        local_max_attempts: Optional[int] = retry_config.get("max_attempts", max_attempts)
        local_max_elapsed_time: Optional[float] = retry_config.get("max_elapsed_time", max_elapsed_time)
        local_delay: Optional[float] = retry_config.get("delay", delay)
        local_backoff_factor: Optional[float] = retry_config.get("backoff_factor", backoff_factor)
        local_max_delay: Optional[float] = retry_config.get("max_delay", max_delay)
        local_exceptions_to_retry: Union[Type[Exception], Tuple[Type[Exception], ...]] = retry_config.get(
            "exceptions_to_retry", exceptions_to_retry
        )

        if local_max_attempts == 0:
            return dispatch_async(func, *args, **kwargs)

        wait_for: float = local_delay or (1 if local_backoff_factor is not None else 0)
        start_time: float = time.monotonic()

        async def async_retry() -> T:
            """Retry asynchronously."""
            nonlocal wait_for
            attempt: int = 0
            while True:
                try:
                    return await cast(Awaitable[T], func(*args, **kwargs))
                except local_exceptions_to_retry as e:
                    attempt += 1
                    elapsed_time: float = time.monotonic() - start_time

                    if isinstance(e, AbortRetry):
                        raise e from None
                    if isinstance(e, RetryWithModifiedParams) and "kwargs" in e.details:
                        kwargs.update(e.details["kwargs"])

                    if (local_max_attempts and attempt >= local_max_attempts) or (
                        local_max_elapsed_time and elapsed_time >= local_max_elapsed_time
                    ):
                        raise Exception(
                            f"Retry limit reached for {func.__name__}. "
                            f"Attempts: {attempt}, Elapsed time: {elapsed_time:.2f}s"
                        ) from None

                    logger.error(
                        f"Attempt {attempt} failed with {str(e)}. "
                        f"Retrying {func.__name__} in {wait_for:.2f} seconds..."
                    )
                    await asyncio.sleep(wait_for)
                    if local_backoff_factor is not None:
                        wait_for = min(wait_for * local_backoff_factor, local_max_delay or float("inf"))

        def sync_retry() -> T:
            """Retry synchronously."""
            nonlocal wait_for
            attempt: int = 0
            while True:
                try:
                    return cast(T, func(*args, **kwargs))
                except local_exceptions_to_retry as e:
                    attempt += 1
                    elapsed_time: float = time.monotonic() - start_time

                    if isinstance(e, AbortRetry):
                        raise e from None
                    if isinstance(e, RetryWithModifiedParams) and "kwargs" in e.details:
                        kwargs.update(e.details["kwargs"])

                    if (local_max_attempts and attempt >= local_max_attempts) or (
                        local_max_elapsed_time and elapsed_time >= local_max_elapsed_time
                    ):
                        raise Exception(
                            f"Retry limit reached for {func.__name__}. "
                            f"Attempts: {attempt}, Elapsed time: {elapsed_time:.2f}s"
                        ) from None

                    logger.error(
                        f"Attempt {attempt} failed with {str(e)}. "
                        f"Retrying {func.__name__} in {wait_for:.2f} seconds..."
                    )
                    time.sleep(wait_for)
                    if local_backoff_factor is not None:
                        wait_for = min(wait_for * local_backoff_factor, local_max_delay or float("inf"))

        return async_retry() if is_async else sync_retry()

    return decorator
