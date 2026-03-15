"""Tests for the skip_if_running decorator."""

import asyncio
import functools
import logging

import pytest
from starlette.responses import JSONResponse


# Inline the decorator to avoid importing budcluster (which requires internal deps).
# This is a faithful copy of budcluster.commons.utils.skip_if_running.
_logger = logging.getLogger(__name__)


def _skip_if_running(job_name: str):
    def decorator(func):
        lock = asyncio.Lock()

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            if not lock.locked():
                async with lock:
                    return await func(*args, **kwargs)
            else:
                _logger.warning("Skipping duplicate cron invocation for '%s'", job_name)
                return JSONResponse(content={"message": f"Skipped: '{job_name}' is already running"}, status_code=200)

        return wrapper

    return decorator


# Re-export so tests read naturally
skip_if_running = _skip_if_running


@pytest.mark.asyncio
async def test_normal_execution_succeeds():
    """Decorated function executes normally when no concurrent invocation."""

    @skip_if_running("test-job")
    async def handler():
        return {"status": "done"}

    result = await handler()
    assert result == {"status": "done"}


@pytest.mark.asyncio
async def test_concurrent_invocation_is_skipped():
    """Second invocation is skipped while the first is still running."""
    entered = asyncio.Event()
    release = asyncio.Event()

    @skip_if_running("test-job")
    async def handler():
        entered.set()
        await release.wait()
        return {"status": "done"}

    # Start first invocation — it will block on release.wait()
    task1 = asyncio.create_task(handler())
    await entered.wait()

    # Second invocation should be skipped immediately
    result2 = await handler()
    assert isinstance(result2, JSONResponse)
    assert result2.status_code == 200
    assert b"already running" in result2.body

    # Release first invocation and verify it completed normally
    release.set()
    result1 = await task1
    assert result1 == {"status": "done"}


@pytest.mark.asyncio
async def test_lock_released_after_exception():
    """Lock is released even if the handler raises, so next call succeeds."""
    call_count = 0

    @skip_if_running("test-job")
    async def handler():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("boom")
        return {"status": "recovered"}

    with pytest.raises(RuntimeError, match="boom"):
        await handler()

    # Lock should be released — next call must succeed
    result = await handler()
    assert result == {"status": "recovered"}
    assert call_count == 2


@pytest.mark.asyncio
async def test_independent_locks_across_handlers():
    """Each decorated function gets its own lock — blocking one doesn't affect another."""
    release = asyncio.Event()

    @skip_if_running("job-a")
    async def handler_a():
        await release.wait()
        return {"handler": "a"}

    @skip_if_running("job-b")
    async def handler_b():
        return {"handler": "b"}

    # Start handler_a — it will block on release.wait()
    task_a = asyncio.create_task(handler_a())
    await asyncio.sleep(0)  # yield to let task_a start

    # handler_b should still execute normally despite handler_a holding its lock
    result_b = await handler_b()
    assert result_b == {"handler": "b"}

    release.set()
    result_a = await task_a
    assert result_a == {"handler": "a"}
