"""Tracks workflow completions for handlers waiting on long-running operations.

This module provides a singleton CompletionTracker that allows workflow handlers
to wait for completion events from budapp. When budapp workflows complete (model add,
benchmark, etc.), they publish events that are received via Dapr pub/sub and
signaled through this tracker.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CompletionResult:
    """Result of a workflow completion event.

    Attributes:
        status: Completion status ("COMPLETED" or "FAILED")
        result: Result data (e.g., {"model_id": "...", "model_name": "..."})
        reason: Optional failure reason if status is FAILED
    """

    status: str
    result: dict[str, Any]
    reason: str | None = None


class CompletionTracker:
    """Tracks pending workflow completions and signals waiting handlers.

    This singleton class coordinates between:
    1. Handlers that start budapp workflows and wait for completion
    2. The callback endpoint that receives completion events from budapp

    Usage:
        # In handler:
        result = await completion_tracker.wait_for_completion(workflow_id)

        # In callback endpoint:
        await completion_tracker.signal_completion(workflow_id, status, result)
    """

    def __init__(self):
        """Initialize the completion tracker."""
        self._pending: dict[str, asyncio.Future] = {}
        self._lock = asyncio.Lock()

    def register_wait(self, workflow_id: str) -> asyncio.Future:
        """Register a handler waiting for workflow completion.

        Args:
            workflow_id: The budapp workflow ID to wait for

        Returns:
            Future that will be resolved when completion event is received
        """
        if workflow_id not in self._pending:
            loop = asyncio.get_event_loop()
            self._pending[workflow_id] = loop.create_future()
            logger.debug(f"Registered wait for workflow {workflow_id}")
        return self._pending[workflow_id]

    async def signal_completion(
        self,
        workflow_id: str,
        status: str,
        result: dict[str, Any],
        reason: str | None = None,
    ) -> None:
        """Signal that a workflow has completed.

        Called by the callback endpoint when a completion event is received.

        Args:
            workflow_id: The budapp workflow ID that completed
            status: Completion status ("COMPLETED" or "FAILED")
            result: Result data with IDs (e.g., model_id, benchmark_id)
            reason: Optional failure reason
        """
        async with self._lock:
            if workflow_id in self._pending:
                future = self._pending.pop(workflow_id)
                if not future.done():
                    completion_result = CompletionResult(
                        status=status, result=result, reason=reason
                    )
                    future.set_result(completion_result)
                    logger.info(
                        f"Signaled completion for workflow {workflow_id}: "
                        f"status={status}, result={result}"
                    )
            else:
                logger.warning(
                    f"Received completion for unknown workflow {workflow_id}. "
                    "No handler was waiting for this workflow."
                )

    async def wait_for_completion(self, workflow_id: str, timeout: int = 1800) -> CompletionResult:
        """Wait for workflow completion with timeout.

        Blocks until the workflow completes or times out.

        Args:
            workflow_id: The budapp workflow ID to wait for
            timeout: Maximum wait time in seconds (default 30 minutes)

        Returns:
            CompletionResult with status and result data

        Raises:
            asyncio.TimeoutError: If timeout is exceeded
        """
        future = self.register_wait(workflow_id)
        try:
            logger.info(f"Waiting for completion of workflow {workflow_id} (timeout={timeout}s)")
            result = await asyncio.wait_for(future, timeout=timeout)
            logger.info(f"Workflow {workflow_id} completed: {result.status}")
            return result
        except asyncio.TimeoutError:
            # Clean up the pending future on timeout
            async with self._lock:
                self._pending.pop(workflow_id, None)
            logger.error(f"Timeout waiting for workflow {workflow_id} after {timeout}s")
            raise

    def cancel_wait(self, workflow_id: str) -> bool:
        """Cancel a pending wait for a workflow.

        Args:
            workflow_id: The workflow ID to cancel

        Returns:
            True if a pending wait was cancelled, False if no wait was pending
        """
        if workflow_id in self._pending:
            future = self._pending.pop(workflow_id)
            if not future.done():
                future.cancel()
            logger.debug(f"Cancelled wait for workflow {workflow_id}")
            return True
        return False

    @property
    def pending_count(self) -> int:
        """Get the number of pending workflow completions."""
        return len(self._pending)


# Global singleton instance
completion_tracker = CompletionTracker()
