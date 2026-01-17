"""Resilience infrastructure for budpipeline.

This module provides in-memory fallback storage, database retry with exponential
backoff, circuit breaker pattern, and staleness indicators
(002-pipeline-event-persistence - T023, T024, T025, T026).
"""

import asyncio
import time
from collections import OrderedDict
from collections.abc import Callable
from datetime import datetime
from threading import Lock
from typing import Any, TypeVar
from uuid import UUID

import pybreaker
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from budpipeline.commons.config import settings
from budpipeline.commons.observability import (
    get_logger,
    record_db_error,
    set_fallback_active,
)

logger = get_logger(__name__)

T = TypeVar("T")


# ============================================================================
# In-Memory Fallback Storage (T023, FR-041)
# ============================================================================


class InMemoryFallbackStorage:
    """Thread-safe in-memory storage for database fallback.

    Used when database is unavailable to maintain service availability.
    Data is eventually synced back to database when connection restored.
    """

    def __init__(self, max_size: int = 10000) -> None:
        """Initialize fallback storage.

        Args:
            max_size: Maximum number of items to store (LRU eviction).
        """
        self._executions: OrderedDict[UUID, dict[str, Any]] = OrderedDict()
        self._steps: dict[UUID, dict[UUID, dict[str, Any]]] = {}  # execution_id -> step_id -> data
        self._events: dict[UUID, list[dict[str, Any]]] = {}  # execution_id -> events
        self._lock = Lock()
        self._max_size = max_size
        self._last_db_write: datetime | None = None
        self._active = False

    def is_active(self) -> bool:
        """Check if fallback mode is active."""
        return self._active

    def activate(self) -> None:
        """Activate fallback mode."""
        with self._lock:
            self._active = True
            self._last_db_write = datetime.utcnow()
            set_fallback_active(True)
            logger.warning("Fallback mode activated - using in-memory storage")

    def deactivate(self) -> None:
        """Deactivate fallback mode."""
        with self._lock:
            self._active = False
            set_fallback_active(False)
            logger.info("Fallback mode deactivated - database restored")

    def get_staleness_seconds(self) -> int | None:
        """Get seconds since last database write.

        Returns:
            Seconds since last DB write, or None if not in fallback mode.
        """
        if not self._active or self._last_db_write is None:
            return None
        return int((datetime.utcnow() - self._last_db_write).total_seconds())

    def _evict_if_needed(self) -> None:
        """Evict oldest items if storage is full."""
        while len(self._executions) > self._max_size:
            oldest_id, _ = self._executions.popitem(last=False)
            self._steps.pop(oldest_id, None)
            self._events.pop(oldest_id, None)
            logger.debug("Evicted execution from fallback storage", execution_id=str(oldest_id))

    def save_execution(
        self,
        execution_id: UUID,
        data: dict[str, Any],
    ) -> None:
        """Save execution to fallback storage.

        Args:
            execution_id: Execution UUID.
            data: Execution data dictionary.
        """
        with self._lock:
            self._executions[execution_id] = data
            self._executions.move_to_end(execution_id)
            self._evict_if_needed()

    def get_execution(self, execution_id: UUID) -> dict[str, Any] | None:
        """Get execution from fallback storage.

        Args:
            execution_id: Execution UUID.

        Returns:
            Execution data dictionary or None if not found.
        """
        with self._lock:
            return self._executions.get(execution_id)

    def save_step(
        self,
        execution_id: UUID,
        step_id: UUID,
        data: dict[str, Any],
    ) -> None:
        """Save step execution to fallback storage.

        Args:
            execution_id: Parent execution UUID.
            step_id: Step UUID.
            data: Step data dictionary.
        """
        with self._lock:
            if execution_id not in self._steps:
                self._steps[execution_id] = {}
            self._steps[execution_id][step_id] = data

    def get_steps(self, execution_id: UUID) -> list[dict[str, Any]]:
        """Get all steps for an execution from fallback storage.

        Args:
            execution_id: Execution UUID.

        Returns:
            List of step data dictionaries.
        """
        with self._lock:
            steps = self._steps.get(execution_id, {})
            return list(steps.values())

    def save_event(
        self,
        execution_id: UUID,
        data: dict[str, Any],
    ) -> None:
        """Save progress event to fallback storage.

        Args:
            execution_id: Execution UUID.
            data: Event data dictionary.
        """
        with self._lock:
            if execution_id not in self._events:
                self._events[execution_id] = []
            self._events[execution_id].append(data)

    def get_events(self, execution_id: UUID) -> list[dict[str, Any]]:
        """Get progress events for an execution from fallback storage.

        Args:
            execution_id: Execution UUID.

        Returns:
            List of event data dictionaries.
        """
        with self._lock:
            return self._events.get(execution_id, [])

    def get_pending_sync_data(self) -> dict[str, Any]:
        """Get all data pending database sync.

        Returns:
            Dictionary with executions, steps, and events to sync.
        """
        with self._lock:
            return {
                "executions": dict(self._executions),
                "steps": dict(self._steps),
                "events": dict(self._events),
            }

    def clear_synced_data(self, execution_ids: list[UUID]) -> None:
        """Clear data that has been synced to database.

        Args:
            execution_ids: List of execution IDs that have been synced.
        """
        with self._lock:
            for exec_id in execution_ids:
                self._executions.pop(exec_id, None)
                self._steps.pop(exec_id, None)
                self._events.pop(exec_id, None)


# Global fallback storage instance
fallback_storage = InMemoryFallbackStorage()


# ============================================================================
# Database Retry Queue with Exponential Backoff (T024, FR-043)
# ============================================================================


class DatabaseRetryError(Exception):
    """Raised when database operation fails after all retries."""

    def __init__(self, operation: str, original_error: Exception) -> None:
        self.operation = operation
        self.original_error = original_error
        super().__init__(f"Database operation '{operation}' failed: {original_error}")


async def with_db_retry(
    operation: Callable[..., T],
    operation_name: str,
    *args: Any,
    max_attempts: int | None = None,
    **kwargs: Any,
) -> T:
    """Execute database operation with retry and exponential backoff.

    Args:
        operation: Async callable to execute.
        operation_name: Name for logging/metrics.
        *args: Positional arguments for operation.
        max_attempts: Override default max retry attempts.
        **kwargs: Keyword arguments for operation.

    Returns:
        Result of the operation.

    Raises:
        DatabaseRetryError: If all retry attempts fail.
    """
    attempts = max_attempts or settings.db_retry_max_attempts

    try:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(attempts),
            wait=wait_exponential(
                multiplier=1,
                min=1,
                max=30,
                exp_base=settings.db_retry_exponential_base,
            ),
            retry=retry_if_exception_type((ConnectionError, TimeoutError, OSError)),
            reraise=True,
        ):
            with attempt:
                logger.debug(
                    "Executing database operation",
                    operation=operation_name,
                    attempt=attempt.retry_state.attempt_number,
                )
                return await operation(*args, **kwargs)
    except RetryError as e:
        record_db_error(operation_name, type(e.last_attempt.exception()).__name__)
        logger.error(
            "Database operation failed after retries",
            operation=operation_name,
            attempts=attempts,
            error=str(e.last_attempt.exception()),
        )
        raise DatabaseRetryError(operation_name, e.last_attempt.exception()) from e


# ============================================================================
# Circuit Breaker for Database Connections (T025)
# ============================================================================


class DatabaseCircuitBreaker:
    """Circuit breaker for database operations.

    Prevents cascading failures when database is unavailable by failing fast
    after detecting repeated failures.
    """

    def __init__(
        self,
        failure_threshold: int | None = None,
        recovery_timeout: int | None = None,
    ) -> None:
        """Initialize circuit breaker.

        Args:
            failure_threshold: Failures before opening circuit.
            recovery_timeout: Seconds before attempting recovery.
        """
        self._breaker = pybreaker.CircuitBreaker(
            fail_max=failure_threshold or settings.circuit_breaker_failure_threshold,
            reset_timeout=recovery_timeout or settings.circuit_breaker_recovery_timeout,
            name="database",
        )
        self._breaker.add_listener(CircuitBreakerListener())

    @property
    def state(self) -> str:
        """Get current circuit breaker state."""
        return self._breaker.current_state

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (failing fast)."""
        return self._breaker.current_state == "open"

    async def call(
        self,
        operation: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Execute operation through circuit breaker.

        Args:
            operation: Async callable to execute.
            *args: Positional arguments.
            **kwargs: Keyword arguments.

        Returns:
            Result of the operation.

        Raises:
            pybreaker.CircuitBreakerError: If circuit is open.
        """

        # pybreaker doesn't natively support async, so we wrap it
        def sync_wrapper() -> T:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(operation(*args, **kwargs))

        return self._breaker.call(sync_wrapper)

    async def call_async(
        self,
        operation: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Execute async operation through circuit breaker.

        Args:
            operation: Async callable to execute.
            *args: Positional arguments.
            **kwargs: Keyword arguments.

        Returns:
            Result of the operation.

        Raises:
            pybreaker.CircuitBreakerError: If circuit is open.
        """
        if self._breaker.current_state == "open":
            raise pybreaker.CircuitBreakerError(self._breaker)

        try:
            result = await operation(*args, **kwargs)
            self._breaker._success_count += 1
            if self._breaker.current_state == "half-open":
                self._breaker._state = self._breaker._state_storage.state("closed")
            return result
        except Exception:
            self._breaker._failure_count += 1
            if self._breaker._failure_count >= self._breaker.fail_max:
                self._breaker._state = self._breaker._state_storage.state("open")
            raise

    def reset(self) -> None:
        """Reset circuit breaker to closed state."""
        self._breaker._failure_count = 0
        self._breaker._success_count = 0
        self._breaker._state = self._breaker._state_storage.state("closed")


class CircuitBreakerListener(pybreaker.CircuitBreakerListener):
    """Listener for circuit breaker state changes."""

    def state_change(self, cb: pybreaker.CircuitBreaker, old_state: str, new_state: str) -> None:
        """Handle circuit breaker state change.

        Args:
            cb: The circuit breaker instance.
            old_state: Previous state.
            new_state: New state.
        """
        logger.warning(
            "Circuit breaker state changed",
            circuit=cb.name,
            old_state=old_state,
            new_state=new_state,
        )
        if new_state == "open":
            fallback_storage.activate()
        elif new_state == "closed" and old_state == "half-open":
            fallback_storage.deactivate()


# Global circuit breaker instance
db_circuit_breaker = DatabaseCircuitBreaker()


# ============================================================================
# Staleness Indicator Utility (T026, FR-047)
# ============================================================================


def get_staleness_header() -> dict[str, str]:
    """Get X-Data-Staleness header value if in fallback mode.

    Returns:
        Dictionary with header if in fallback mode, empty otherwise.
    """
    staleness = fallback_storage.get_staleness_seconds()
    if staleness is not None:
        return {"X-Data-Staleness": str(staleness)}
    return {}


def add_staleness_to_response(response: Any) -> Any:
    """Add staleness header to response if in fallback mode.

    Args:
        response: FastAPI Response object.

    Returns:
        Response with staleness header added if needed.
    """
    staleness = fallback_storage.get_staleness_seconds()
    if staleness is not None and hasattr(response, "headers"):
        response.headers["X-Data-Staleness"] = str(staleness)
    return response


class ResilienceContext:
    """Context manager for resilient database operations.

    Combines circuit breaker, retry logic, and fallback storage.
    """

    def __init__(self, operation_name: str) -> None:
        """Initialize resilience context.

        Args:
            operation_name: Name of the operation for logging/metrics.
        """
        self.operation_name = operation_name
        self.start_time: float = 0
        self.used_fallback = False

    async def __aenter__(self) -> "ResilienceContext":
        """Enter context, record start time."""
        self.start_time = time.time()
        return self

    async def __aexit__(
        self, exc_type: type | None, exc_val: Exception | None, exc_tb: Any
    ) -> bool:
        """Exit context, handle exceptions.

        Returns:
            True if exception was handled (fallback used), False otherwise.
        """
        duration = time.time() - self.start_time

        if exc_val is not None:
            logger.error(
                "Database operation failed",
                operation=self.operation_name,
                duration_seconds=duration,
                error=str(exc_val),
            )
            record_db_error(self.operation_name, type(exc_val).__name__)

            # If circuit breaker trips, activate fallback
            if isinstance(exc_val, pybreaker.CircuitBreakerError):
                fallback_storage.activate()
                self.used_fallback = True
                return True  # Suppress exception, caller should use fallback

        return False  # Don't suppress exception
