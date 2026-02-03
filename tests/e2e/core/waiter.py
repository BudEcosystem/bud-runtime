"""
Generic workflow waiter for long-running operations.

Provides a reusable pattern for polling async workflows until completion.
Supports different workflow types with configurable timeouts and status checks.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    Callable,
    Coroutine,
    Dict,
    Generic,
    Optional,
    TypeVar,
    Union,
)

from .config import get_config


logger = logging.getLogger(__name__)

T = TypeVar("T")


class WorkflowStatus(str, Enum):
    """Standard workflow status values."""

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ERROR = "ERROR"
    CANCELLED = "CANCELLED"
    TIMEOUT = "TIMEOUT"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def is_terminal(cls, status: Union[str, "WorkflowStatus"]) -> bool:
        """Check if status is terminal (workflow is done)."""
        terminal_statuses = {
            cls.SUCCESS,
            cls.COMPLETED,
            cls.FAILED,
            cls.ERROR,
            cls.CANCELLED,
            cls.TIMEOUT,
        }

        if isinstance(status, str):
            status = status.upper()
            return status in {s.value for s in terminal_statuses}

        return status in terminal_statuses

    @classmethod
    def is_success(cls, status: Union[str, "WorkflowStatus"]) -> bool:
        """Check if status indicates success."""
        success_statuses = {cls.SUCCESS, cls.COMPLETED}

        if isinstance(status, str):
            status = status.upper()
            return status in {s.value for s in success_statuses}

        return status in success_statuses

    @classmethod
    def is_failure(cls, status: Union[str, "WorkflowStatus"]) -> bool:
        """Check if status indicates failure."""
        failure_statuses = {cls.FAILED, cls.ERROR, cls.CANCELLED, cls.TIMEOUT}

        if isinstance(status, str):
            status = status.upper()
            return status in {s.value for s in failure_statuses}

        return status in failure_statuses

    @classmethod
    def normalize(cls, status: Union[str, "WorkflowStatus"]) -> "WorkflowStatus":
        """Normalize a status string to WorkflowStatus enum."""
        if isinstance(status, cls):
            return status

        status_upper = status.upper()

        # Direct match
        for ws in cls:
            if ws.value == status_upper:
                return ws

        # Alias mappings
        aliases = {
            "DONE": cls.SUCCESS,
            "COMPLETE": cls.COMPLETED,
            "FINISHED": cls.SUCCESS,
            "ACTIVE": cls.IN_PROGRESS,
            "PROCESSING": cls.IN_PROGRESS,
            "QUEUED": cls.PENDING,
            "WAITING": cls.PENDING,
            "ABORTED": cls.CANCELLED,
            "STOPPED": cls.CANCELLED,
        }

        return aliases.get(status_upper, cls.UNKNOWN)


@dataclass
class WorkflowResult(Generic[T]):
    """Result of a workflow wait operation."""

    success: bool
    status: WorkflowStatus
    data: Optional[T] = None
    error: Optional[str] = None
    elapsed_seconds: float = 0.0
    poll_count: int = 0
    workflow_id: Optional[str] = None

    # Additional context
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress_percent: Optional[float] = None
    current_step: Optional[int] = None
    total_steps: Optional[int] = None

    def __bool__(self) -> bool:
        """Allow using result in boolean context."""
        return self.success


@dataclass
class WaiterConfig:
    """Configuration for workflow waiter."""

    # Timeout in seconds
    timeout: int = 300

    # Polling interval in seconds
    poll_interval: int = 5

    # Minimum polling interval (won't go below this even with adaptive polling)
    min_poll_interval: int = 2

    # Maximum polling interval
    max_poll_interval: int = 30

    # Use adaptive polling (increase interval over time)
    adaptive_polling: bool = True

    # Adaptive polling increase factor
    adaptive_factor: float = 1.2

    # Callback for progress updates
    on_progress: Optional[Callable[[WorkflowResult], None]] = None

    # Callback for status changes
    on_status_change: Optional[Callable[[WorkflowStatus, WorkflowStatus], None]] = None

    # Whether to log progress
    log_progress: bool = True

    # Custom status extraction function
    status_extractor: Optional[Callable[[Dict[str, Any]], str]] = None

    # Custom success check function
    success_checker: Optional[Callable[[Dict[str, Any]], bool]] = None


# Type alias for status check function
StatusCheckFunc = Callable[[], Coroutine[Any, Any, Dict[str, Any]]]


class WorkflowWaiter:
    """
    Generic waiter for long-running workflows.

    Usage:
        waiter = WorkflowWaiter(
            check_func=lambda: api.get_workflow_status(workflow_id),
            config=WaiterConfig(timeout=600, poll_interval=10),
        )

        result = await waiter.wait()
        if result.success:
            print(f"Workflow completed in {result.elapsed_seconds}s")
        else:
            print(f"Workflow failed: {result.error}")
    """

    def __init__(
        self,
        check_func: StatusCheckFunc,
        config: Optional[WaiterConfig] = None,
        workflow_id: Optional[str] = None,
        workflow_type: str = "workflow",
    ):
        """
        Initialize the waiter.

        Args:
            check_func: Async function that returns workflow status dict
            config: Waiter configuration
            workflow_id: Optional workflow ID for logging
            workflow_type: Type of workflow for logging
        """
        self.check_func = check_func
        self.config = config or WaiterConfig()
        self.workflow_id = workflow_id
        self.workflow_type = workflow_type

        self._current_interval = self.config.poll_interval
        self._poll_count = 0
        self._last_status: Optional[WorkflowStatus] = None
        self._started_at: Optional[datetime] = None

    def _extract_status(self, data: Dict[str, Any]) -> WorkflowStatus:
        """Extract status from response data."""
        if self.config.status_extractor:
            status_str = self.config.status_extractor(data)
        else:
            # Try common status field names
            status_str = (
                data.get("status")
                or data.get("workflow_status")
                or data.get("state")
                or data.get("phase")
                or "UNKNOWN"
            )

        return WorkflowStatus.normalize(status_str)

    def _extract_progress(
        self, data: Dict[str, Any]
    ) -> tuple[Optional[float], Optional[int], Optional[int]]:
        """Extract progress information from response data."""
        progress_percent = data.get("progress") or data.get("progress_percent")

        current_step = data.get("current_step") or data.get("step")
        total_steps = data.get("total_steps") or data.get("steps")

        # Calculate percent from steps if not provided
        if progress_percent is None and current_step and total_steps:
            progress_percent = (current_step / total_steps) * 100

        return progress_percent, current_step, total_steps

    def _check_success(self, data: Dict[str, Any], status: WorkflowStatus) -> bool:
        """Check if workflow completed successfully."""
        if self.config.success_checker:
            return self.config.success_checker(data)

        return WorkflowStatus.is_success(status)

    def _update_poll_interval(self) -> None:
        """Update polling interval for adaptive polling."""
        if not self.config.adaptive_polling:
            return

        # Increase interval over time
        self._current_interval = min(
            self._current_interval * self.config.adaptive_factor,
            self.config.max_poll_interval,
        )

    def _log_progress(self, result: WorkflowResult) -> None:
        """Log progress if enabled."""
        if not self.config.log_progress:
            return

        progress_str = ""
        if result.progress_percent is not None:
            progress_str = f" ({result.progress_percent:.1f}%)"
        elif result.current_step and result.total_steps:
            progress_str = f" (step {result.current_step}/{result.total_steps})"

        logger.info(
            f"[{self.workflow_type}] {self.workflow_id or 'unknown'}: "
            f"status={result.status.value}{progress_str} "
            f"elapsed={result.elapsed_seconds:.1f}s"
        )

    async def wait(self) -> WorkflowResult:
        """
        Wait for workflow completion.

        Returns:
            WorkflowResult with final status and data
        """
        self._started_at = datetime.now()
        self._poll_count = 0
        self._current_interval = self.config.poll_interval

        deadline = self._started_at + timedelta(seconds=self.config.timeout)

        while datetime.now() < deadline:
            self._poll_count += 1

            try:
                # Check workflow status
                data = await self.check_func()

                # Extract status and progress
                status = self._extract_status(data)
                progress_percent, current_step, total_steps = self._extract_progress(
                    data
                )

                # Calculate elapsed time
                elapsed = (datetime.now() - self._started_at).total_seconds()

                # Build result
                result = WorkflowResult(
                    success=False,  # Will be set below
                    status=status,
                    data=data,
                    elapsed_seconds=elapsed,
                    poll_count=self._poll_count,
                    workflow_id=self.workflow_id,
                    started_at=self._started_at,
                    progress_percent=progress_percent,
                    current_step=current_step,
                    total_steps=total_steps,
                )

                # Notify status change
                if self._last_status != status:
                    if self.config.on_status_change:
                        self.config.on_status_change(self._last_status, status)
                    self._last_status = status

                # Notify progress
                if self.config.on_progress:
                    self.config.on_progress(result)

                # Log progress
                self._log_progress(result)

                # Check if terminal
                if WorkflowStatus.is_terminal(status):
                    result.success = self._check_success(data, status)
                    result.completed_at = datetime.now()

                    if not result.success:
                        result.error = (
                            data.get("error")
                            or data.get("message")
                            or f"Workflow {status.value}"
                        )

                    return result

                # Update polling interval
                self._update_poll_interval()

                # Wait before next poll
                await asyncio.sleep(self._current_interval)

            except Exception as e:
                logger.error(f"Error checking {self.workflow_type} status: {e}")

                # Don't fail immediately on transient errors
                if self._poll_count < 3:
                    await asyncio.sleep(self._current_interval)
                    continue

                elapsed = (datetime.now() - self._started_at).total_seconds()
                return WorkflowResult(
                    success=False,
                    status=WorkflowStatus.ERROR,
                    error=str(e),
                    elapsed_seconds=elapsed,
                    poll_count=self._poll_count,
                    workflow_id=self.workflow_id,
                    started_at=self._started_at,
                    completed_at=datetime.now(),
                )

        # Timeout
        elapsed = (datetime.now() - self._started_at).total_seconds()
        return WorkflowResult(
            success=False,
            status=WorkflowStatus.TIMEOUT,
            error=f"Timeout after {self.config.timeout}s ({self._poll_count} polls)",
            elapsed_seconds=elapsed,
            poll_count=self._poll_count,
            workflow_id=self.workflow_id,
            started_at=self._started_at,
            completed_at=datetime.now(),
        )


async def wait_for_workflow(
    check_func: StatusCheckFunc,
    timeout: Optional[int] = None,
    poll_interval: Optional[int] = None,
    workflow_id: Optional[str] = None,
    workflow_type: str = "workflow",
    on_progress: Optional[Callable[[WorkflowResult], None]] = None,
) -> WorkflowResult:
    """
    Convenience function for waiting on a workflow.

    Usage:
        result = await wait_for_workflow(
            check_func=lambda: api.get_status(id),
            timeout=600,
            poll_interval=10,
            workflow_id=id,
        )
    """
    config = WaiterConfig(
        timeout=timeout or get_config().timeouts.model_local_workflow,
        poll_interval=poll_interval or get_config().timeouts.poll_interval,
        on_progress=on_progress,
    )

    waiter = WorkflowWaiter(
        check_func=check_func,
        config=config,
        workflow_id=workflow_id,
        workflow_type=workflow_type,
    )

    return await waiter.wait()


# Preset waiters for common workflow types
def create_model_workflow_waiter(
    check_func: StatusCheckFunc,
    workflow_id: Optional[str] = None,
    local: bool = False,
) -> WorkflowWaiter:
    """Create a waiter configured for model workflows."""
    timeouts = get_config().timeouts

    config = WaiterConfig(
        timeout=timeouts.model_local_workflow
        if local
        else timeouts.model_cloud_workflow,
        poll_interval=timeouts.poll_interval_slow if local else timeouts.poll_interval,
        adaptive_polling=local,  # Use adaptive for long local workflows
    )

    return WorkflowWaiter(
        check_func=check_func,
        config=config,
        workflow_id=workflow_id,
        workflow_type="local-model" if local else "cloud-model",
    )


def create_cluster_workflow_waiter(
    check_func: StatusCheckFunc,
    workflow_id: Optional[str] = None,
) -> WorkflowWaiter:
    """Create a waiter configured for cluster provisioning."""
    timeouts = get_config().timeouts

    config = WaiterConfig(
        timeout=timeouts.cluster_provision,
        poll_interval=timeouts.poll_interval_slow,
        adaptive_polling=True,
    )

    return WorkflowWaiter(
        check_func=check_func,
        config=config,
        workflow_id=workflow_id,
        workflow_type="cluster-provision",
    )


def create_deployment_waiter(
    check_func: StatusCheckFunc,
    workflow_id: Optional[str] = None,
) -> WorkflowWaiter:
    """Create a waiter configured for deployments."""
    timeouts = get_config().timeouts

    config = WaiterConfig(
        timeout=timeouts.deployment_create,
        poll_interval=timeouts.poll_interval,
        adaptive_polling=True,
    )

    return WorkflowWaiter(
        check_func=check_func,
        config=config,
        workflow_id=workflow_id,
        workflow_type="deployment",
    )
