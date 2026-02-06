"""
Retry utilities for E2E tests.

Provides decorators and utilities for handling transient failures
in API calls and long-running operations.
"""

import asyncio
import functools
import logging
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    List,
    Optional,
    Type,
    TypeVar,
)

import httpx


logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    # Maximum number of retry attempts
    max_attempts: int = 3

    # Base delay between retries (seconds)
    base_delay: float = 1.0

    # Maximum delay between retries (seconds)
    max_delay: float = 30.0

    # Exponential backoff multiplier
    backoff_multiplier: float = 2.0

    # Add jitter to delays to avoid thundering herd
    jitter: bool = True

    # Exception types to retry on
    retry_on: List[Type[Exception]] = field(
        default_factory=lambda: [
            httpx.TimeoutException,
            httpx.ConnectError,
            httpx.ReadError,
            ConnectionError,
            TimeoutError,
        ]
    )

    # HTTP status codes to retry on
    retry_on_status: List[int] = field(
        default_factory=lambda: [
            408,  # Request Timeout
            429,  # Too Many Requests
            500,  # Internal Server Error
            502,  # Bad Gateway
            503,  # Service Unavailable
            504,  # Gateway Timeout
        ]
    )

    # Whether to retry on all 5xx errors
    retry_on_5xx: bool = True


class RetryExhausted(Exception):
    """Raised when all retry attempts have been exhausted."""

    def __init__(
        self,
        message: str,
        attempts: int,
        last_exception: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.attempts = attempts
        self.last_exception = last_exception


def _calculate_delay(
    attempt: int,
    config: RetryConfig,
) -> float:
    """Calculate delay before next retry attempt."""
    import random

    delay = config.base_delay * (config.backoff_multiplier ** (attempt - 1))
    delay = min(delay, config.max_delay)

    if config.jitter:
        # Add up to 25% jitter
        jitter = delay * 0.25 * random.random()
        delay = delay + jitter

    return delay


def _should_retry_exception(
    exception: Exception,
    config: RetryConfig,
) -> bool:
    """Check if we should retry based on the exception type."""
    for exc_type in config.retry_on:
        if isinstance(exception, exc_type):
            return True
    return False


def _should_retry_response(
    response: httpx.Response,
    config: RetryConfig,
) -> bool:
    """Check if we should retry based on the HTTP response."""
    if response.status_code in config.retry_on_status:
        return True

    if config.retry_on_5xx and 500 <= response.status_code < 600:
        return True

    return False


def retry(
    config: Optional[RetryConfig] = None,
    max_attempts: Optional[int] = None,
    base_delay: Optional[float] = None,
    retry_on: Optional[List[Type[Exception]]] = None,
) -> Callable:
    """
    Decorator for retrying async functions on transient failures.

    Usage:
        @retry()
        async def my_api_call():
            ...

        @retry(max_attempts=5, base_delay=2.0)
        async def my_slow_api_call():
            ...

        @retry(retry_on=[ConnectionError, TimeoutError])
        async def my_network_call():
            ...
    """
    if config is None:
        config = RetryConfig()

    # Override config with explicit parameters
    if max_attempts is not None:
        config.max_attempts = max_attempts
    if base_delay is not None:
        config.base_delay = base_delay
    if retry_on is not None:
        config.retry_on = retry_on

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Optional[Exception] = None

            for attempt in range(1, config.max_attempts + 1):
                try:
                    result = await func(*args, **kwargs)

                    # Check if result is an httpx Response that should be retried
                    if isinstance(result, httpx.Response):
                        if _should_retry_response(result, config):
                            if attempt < config.max_attempts:
                                delay = _calculate_delay(attempt, config)
                                logger.warning(
                                    f"Retry {attempt}/{config.max_attempts} for {func.__name__}: "
                                    f"HTTP {result.status_code}, waiting {delay:.1f}s"
                                )
                                await asyncio.sleep(delay)
                                continue

                    return result

                except Exception as e:
                    last_exception = e

                    if not _should_retry_exception(e, config):
                        raise

                    if attempt < config.max_attempts:
                        delay = _calculate_delay(attempt, config)
                        logger.warning(
                            f"Retry {attempt}/{config.max_attempts} for {func.__name__}: "
                            f"{type(e).__name__}: {e}, waiting {delay:.1f}s"
                        )
                        await asyncio.sleep(delay)
                    else:
                        raise RetryExhausted(
                            f"All {config.max_attempts} retry attempts exhausted for {func.__name__}",
                            attempts=config.max_attempts,
                            last_exception=last_exception,
                        ) from e

            # Should not reach here, but just in case
            raise RetryExhausted(
                f"Retry logic error for {func.__name__}",
                attempts=config.max_attempts,
                last_exception=last_exception,
            )

        return wrapper

    return decorator


async def retry_async(
    func: Callable[..., T],
    *args: Any,
    config: Optional[RetryConfig] = None,
    **kwargs: Any,
) -> T:
    """
    Retry an async function call with the given config.

    Usage:
        result = await retry_async(
            my_api_call,
            arg1, arg2,
            config=RetryConfig(max_attempts=5),
            kwarg1=value1,
        )
    """
    if config is None:
        config = RetryConfig()

    @retry(config=config)
    async def wrapped() -> T:
        return await func(*args, **kwargs)

    return await wrapped()


class RetryContext:
    """
    Context manager for retry logic with custom handling.

    Usage:
        async with RetryContext(max_attempts=3) as ctx:
            while ctx.should_continue():
                try:
                    result = await my_api_call()
                    ctx.success()
                    break
                except TransientError as e:
                    await ctx.handle_failure(e)
    """

    def __init__(
        self,
        config: Optional[RetryConfig] = None,
        max_attempts: Optional[int] = None,
    ):
        self.config = config or RetryConfig()
        if max_attempts is not None:
            self.config.max_attempts = max_attempts

        self._attempt = 0
        self._succeeded = False
        self._last_exception: Optional[Exception] = None

    async def __aenter__(self) -> "RetryContext":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        # Don't suppress exceptions
        return False

    @property
    def attempt(self) -> int:
        """Current attempt number (1-based)."""
        return self._attempt

    @property
    def attempts_remaining(self) -> int:
        """Number of attempts remaining."""
        return self.config.max_attempts - self._attempt

    def should_continue(self) -> bool:
        """Check if we should continue retrying."""
        if self._succeeded:
            return False
        if self._attempt >= self.config.max_attempts:
            return False
        self._attempt += 1
        return True

    def success(self) -> None:
        """Mark the operation as successful."""
        self._succeeded = True

    async def handle_failure(
        self,
        exception: Optional[Exception] = None,
        should_retry: bool = True,
    ) -> None:
        """
        Handle a failure and wait before next retry.

        Args:
            exception: The exception that occurred
            should_retry: Whether to continue retrying
        """
        self._last_exception = exception

        if not should_retry:
            self._attempt = self.config.max_attempts  # Force stop

        if self._attempt < self.config.max_attempts:
            delay = _calculate_delay(self._attempt, self.config)
            logger.warning(
                f"Retry {self._attempt}/{self.config.max_attempts}: "
                f"{exception}, waiting {delay:.1f}s"
            )
            await asyncio.sleep(delay)

    def raise_if_exhausted(self) -> None:
        """Raise RetryExhausted if all attempts failed."""
        if not self._succeeded and self._attempt >= self.config.max_attempts:
            raise RetryExhausted(
                f"All {self.config.max_attempts} retry attempts exhausted",
                attempts=self.config.max_attempts,
                last_exception=self._last_exception,
            )
