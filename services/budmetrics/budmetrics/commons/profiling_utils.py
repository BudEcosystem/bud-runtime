import asyncio
import time
from functools import wraps
from typing import Any, Literal, Optional
import logging

from budmetrics.commons.config import app_settings

logger = logging.getLogger(__name__)


class PerformanceMetrics:
    """Track performance metrics for queries and operations."""

    def __init__(self):
        self.metrics = {
            "query_execution": [],
            "query_building": [],
            "result_processing": [],
            "cache_hits": 0,
            "cache_misses": 0,
            "total_queries": 0,
        }

    def record_timing(
        self,
        operation: Literal["query_building", "query_execution", "result_processing"],
        duration: float,
        metadata: Optional[dict[str, Any]] = None,
    ):
        """Record timing for an operation."""
        record = {
            "timestamp": time.time(),
            "duration_ms": duration * 1000,
            "metadata": metadata or {},
        }
        if operation in self.metrics:
            self.metrics[operation].append(record)

    def increment_counter(
        self, counter: Literal["cache_hits", "cache_misses", "total_queries"]
    ):
        """Increment a counter metric."""
        if counter in self.metrics:
            self.metrics[counter] += 1

    def get_summary(self) -> dict[str, Any]:
        """Get summary statistics."""
        summary = {}

        for operation in ["query_execution", "query_building", "result_processing"]:
            timings: list[dict[str, Any]] = self.metrics[operation]
            if timings:
                durations = [t["duration_ms"] for t in timings]
                summary[operation] = {
                    "count": len(durations),
                    "total_ms": sum(durations),
                    "avg_ms": sum(durations) / len(durations),
                    "min_ms": min(durations),
                    "max_ms": max(durations),
                    "p50_ms": (
                        sorted(durations)[len(durations) // 2] if durations else 0
                    ),
                    "p95_ms": (
                        sorted(durations)[int(len(durations) * 0.95)]
                        if durations
                        else 0
                    ),
                    "p99_ms": (
                        sorted(durations)[int(len(durations) * 0.99)]
                        if durations
                        else 0
                    ),
                }

        summary["cache"] = {
            "hits": self.metrics["cache_hits"],
            "misses": self.metrics["cache_misses"],
            "hit_rate": self.metrics["cache_hits"]
            / max(1, self.metrics["cache_hits"] + self.metrics["cache_misses"]),
        }
        summary["total_queries"] = self.metrics["total_queries"]

        return summary


def profile_async(operation_name: str):
    """Profile async functions."""

    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            if app_settings.debug:
                start_time = time.time()
                try:
                    result = await func(self, *args, **kwargs)
                    duration = time.time() - start_time

                    # Record metrics if instance has performance_metrics
                    if getattr(self, "performance_metrics", None) is not None:
                        metadata = {}
                        if operation_name == "query_execution" and args:
                            # First arg is usually the query
                            query = str(args[0])[:100]  # Truncate long queries
                            metadata["query_preview"] = query
                        self.performance_metrics.record_timing(
                            operation_name, duration, metadata
                        )

                    return result
                except Exception as e:
                    duration = time.time() - start_time
                    if getattr(self, "performance_metrics", None) is not None:
                        self.performance_metrics.record_timing(
                            operation_name, duration, {"error": str(e)}
                        )
                    raise
            else:
                return await func(self, *args, **kwargs)

        return wrapper

    return decorator


def profile_sync(operation_name: str):
    """Profile sync functions."""

    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if app_settings.debug:
                start_time = time.time()
                try:
                    result = func(self, *args, **kwargs)
                    duration = time.time() - start_time

                    # Record metrics if instance has performance_metrics
                    if getattr(self, "performance_metrics", None) is not None:
                        metadata = {"args_count": len(args)}
                        self.performance_metrics.record_timing(
                            operation_name, duration, metadata
                        )

                    return result
                except Exception as e:
                    duration = time.time() - start_time
                    if getattr(self, "performance_metrics", None) is not None:
                        self.performance_metrics.record_timing(
                            operation_name, duration, {"error": str(e)}
                        )
                    raise
            else:
                return func(self, *args, **kwargs)

        return wrapper

    return decorator


class PerformanceLogger:
    """Singleton that logs aggregated performance metrics periodically in debug mode."""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, interval_seconds: int = 10):
        # Only initialize once
        if PerformanceLogger._initialized:
            return

        self.interval = interval_seconds
        self.performance_metrics = PerformanceMetrics() if app_settings.debug else None
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._last_log_time = time.time()
        PerformanceLogger._initialized = True

    async def _log_metrics_periodically(self):
        """Background task to log metrics periodically."""
        while self._running:
            try:
                await asyncio.sleep(self.interval)

                if self.performance_metrics:
                    summary = self.performance_metrics.get_summary()

                    # Only log if there's actual activity
                    total_queries = summary.get("total_queries", 0)
                    if total_queries > 0:
                        logger.info(
                            "Performance metrics summary (last %d seconds): %d queries processed",
                            self.interval,
                            total_queries,
                            extra={
                                "period_seconds": self.interval,
                                "metrics_summary": summary,
                                "timestamp": time.time(),
                            },
                        )

                        # Reset metrics after logging to avoid accumulation
                        self.performance_metrics = PerformanceMetrics()

            except asyncio.CancelledError:
                logger.debug("Performance logger task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in performance logger: {e}")

    async def start(self):
        """Start the periodic logging task."""
        if app_settings.debug and not self._running:
            self._running = True
            self._task = asyncio.create_task(self._log_metrics_periodically())
            logger.info(f"Performance logger started (interval: {self.interval}s)")

    async def stop(self):
        """Stop the periodic logging task."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            logger.info("Performance logger stopped")

    def get_metrics(self) -> Optional[PerformanceMetrics]:
        """Get the current performance metrics instance."""
        return self.performance_metrics


# Global singleton instance
performance_logger = PerformanceLogger()
