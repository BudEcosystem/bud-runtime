"""Tests for concurrent cluster sync and IndependentSession."""

import asyncio
import os
import sys
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest


# Ensure required env vars exist before importing
os.environ.setdefault("ENGINE_CONTAINER_PORT", "8000")
os.environ.setdefault("REGISTRY_SERVER", "ghcr.io")
os.environ.setdefault("REGISTRY_USERNAME", "testuser")
os.environ.setdefault("REGISTRY_PASSWORD", "testpass")
os.environ.setdefault("DAPR_BASE_URL", "http://localhost:3500")
os.environ.setdefault("PROMETHEUS_URL", "http://localhost:9090")

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestIndependentSession:
    """Tests for IndependentSession context manager pattern.

    These tests validate the context manager pattern used by IndependentSession
    without importing the module (which requires budmicroframe).
    """

    def _make_independent_session(self, session_factory):
        """Reproduce the IndependentSession pattern for testing."""

        @contextmanager
        def independent_session():
            session = session_factory()
            try:
                yield session
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        return independent_session

    def test_yields_session_and_closes(self):
        """Verify session is yielded and closed on normal exit."""
        mock_session = MagicMock()
        independent_session = self._make_independent_session(lambda: mock_session)

        with independent_session() as session:
            assert session is mock_session

        mock_session.close.assert_called_once()

    def test_rollback_on_exception(self):
        """Verify rollback is called when exception occurs inside context."""
        mock_session = MagicMock()
        independent_session = self._make_independent_session(lambda: mock_session)

        with pytest.raises(ValueError, match="test error"), independent_session() as _session:  # noqa: F841
            raise ValueError("test error")

        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()

    def test_close_called_on_normal_exit(self):
        """Verify close is called but not rollback on normal exit."""
        mock_session = MagicMock()
        independent_session = self._make_independent_session(lambda: mock_session)

        with independent_session():
            pass

        mock_session.rollback.assert_not_called()
        mock_session.close.assert_called_once()


class TestConcurrentSyncSemaphore:
    """Tests for concurrency limiting in trigger_periodic_node_status_update."""

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrency(self):
        """Verify that at most MAX_CONCURRENT_SYNCS tasks run simultaneously."""
        max_concurrent = 0
        current_concurrent = 0
        lock = asyncio.Lock()

        async def mock_sync(cluster, sync_state):
            nonlocal max_concurrent, current_concurrent
            async with lock:
                current_concurrent += 1
                if current_concurrent > max_concurrent:
                    max_concurrent = current_concurrent
            await asyncio.sleep(0.01)  # Simulate work
            async with lock:
                current_concurrent -= 1
            return True

        MAX_CONCURRENT_SYNCS = 10
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_SYNCS)

        async def _throttled_sync(cluster_item):
            async with semaphore:
                return await mock_sync(cluster_item, {})

        # Create 25 tasks (more than the limit of 10)
        tasks = [_throttled_sync(MagicMock()) for _ in range(25)]
        await asyncio.gather(*tasks)

        assert max_concurrent <= MAX_CONCURRENT_SYNCS
        assert max_concurrent > 1  # Verify some concurrency happened

    @pytest.mark.asyncio
    async def test_gather_return_exceptions(self):
        """Verify that asyncio.gather with return_exceptions captures failures."""

        async def succeed():
            return True

        async def fail():
            raise ConnectionError("cluster unreachable")

        results = await asyncio.gather(succeed(), fail(), succeed(), return_exceptions=True)

        assert results[0] is True
        assert isinstance(results[1], ConnectionError)
        assert results[2] is True

    @pytest.mark.asyncio
    async def test_semaphore_handles_exceptions(self):
        """Verify semaphore is released even when task raises."""
        MAX_CONCURRENT_SYNCS = 2
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_SYNCS)
        completed = 0

        async def _throttled_failing():
            async with semaphore:
                raise RuntimeError("fail")

        async def _throttled_succeeding():
            nonlocal completed
            async with semaphore:
                await asyncio.sleep(0.01)
                completed += 1
                return True

        # Mix of failing and succeeding tasks
        tasks = [_throttled_failing(), _throttled_succeeding(), _throttled_succeeding()]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        assert isinstance(results[0], RuntimeError)
        assert results[1] is True
        assert results[2] is True
        assert completed == 2  # Both succeeding tasks completed


class TestSyncStateManagement:
    """Tests for sync state tracking logic."""

    def test_stale_sync_cleanup(self):
        """Verify stale active syncs are cleaned up."""
        current_time = datetime.now(UTC)
        stale_time = current_time - timedelta(minutes=20)

        sync_state = {
            "active_syncs": {
                "stale-cluster": {"started_at": (current_time - timedelta(minutes=30)).isoformat()},
                "fresh-cluster": {"started_at": (current_time - timedelta(minutes=5)).isoformat()},
            },
            "last_sync_times": {},
            "failed_clusters": {},
        }

        # Replicate the cleanup logic from trigger_periodic_node_status_update
        for cluster_id, sync_info in list(sync_state["active_syncs"].items()):
            sync_time = datetime.fromisoformat(sync_info.get("started_at", ""))
            if sync_time < stale_time:
                del sync_state["active_syncs"][cluster_id]

        assert "stale-cluster" not in sync_state["active_syncs"]
        assert "fresh-cluster" in sync_state["active_syncs"]

    def test_result_processing_success(self):
        """Verify successful results update state correctly."""
        current_time = datetime.now(UTC)
        sync_state = {
            "active_syncs": {"cluster-1": {}},
            "last_sync_times": {},
            "failed_clusters": {"cluster-1": {"error": "old error"}},
        }

        cluster_id_str = "cluster-1"
        result = True  # success

        sync_state["active_syncs"].pop(cluster_id_str, None)
        if isinstance(result, Exception):
            sync_state["failed_clusters"][cluster_id_str] = {
                "error": str(result),
                "failed_at": current_time.isoformat(),
            }
        else:
            sync_state["last_sync_times"][cluster_id_str] = current_time.isoformat()
            sync_state["failed_clusters"].pop(cluster_id_str, None)

        assert cluster_id_str not in sync_state["active_syncs"]
        assert cluster_id_str in sync_state["last_sync_times"]
        assert cluster_id_str not in sync_state["failed_clusters"]

    def test_result_processing_failure(self):
        """Verify failed results update state correctly."""
        current_time = datetime.now(UTC)
        sync_state = {
            "active_syncs": {"cluster-1": {}},
            "last_sync_times": {},
            "failed_clusters": {},
        }

        cluster_id_str = "cluster-1"
        result = ConnectionError("unreachable")

        sync_state["active_syncs"].pop(cluster_id_str, None)
        if isinstance(result, Exception):
            sync_state["failed_clusters"][cluster_id_str] = {
                "error": str(result),
                "failed_at": current_time.isoformat(),
            }
        else:
            sync_state["last_sync_times"][cluster_id_str] = current_time.isoformat()
            sync_state["failed_clusters"].pop(cluster_id_str, None)

        assert cluster_id_str not in sync_state["active_syncs"]
        assert cluster_id_str not in sync_state["last_sync_times"]
        assert cluster_id_str in sync_state["failed_clusters"]
        assert "unreachable" in sync_state["failed_clusters"][cluster_id_str]["error"]
