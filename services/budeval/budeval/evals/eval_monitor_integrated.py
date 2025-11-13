#!/usr/bin/env python3
"""Integrated evaluation monitor that emits progress events via Dapr pub/sub.

This version can be called from the workflow to track and emit real-time progress.
"""

import glob
import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from budmicroframe.commons.constants import WorkflowStatus
from budmicroframe.commons.schemas import NotificationContent, NotificationRequest
from budmicroframe.shared.dapr_workflow import DaprWorkflow

from budeval.commons.logging import logging


logger = logging.getLogger(__name__)
dapr_workflows = DaprWorkflow()


class IntegratedEvalMonitor:
    """Evaluation monitor that tracks progress and emits Dapr notifications.

    This monitor:
    1. Tracks evaluation progress by parsing logs and counting completed tasks
    2. Emits 3 types of events: EVAL_STARTED, EVAL_PROGRESS, EVAL_COMPLETED
    3. Publishes events via Dapr pub/sub for budapp to consume
    """

    def __init__(
        self,
        log_file: str,
        results_dir: str,
        experiment_id: str,
        evaluation_id: str,
        workflow_id: str,
        source_topic: str,
        source: str,
        dataset_config: Optional[str] = None,
    ):
        """Initialize the integrated monitor.

        Args:
            log_file: Path to evaluation log file (e.g., nohup.out)
            results_dir: Path to results directory
            experiment_id: UUID of the experiment
            evaluation_id: UUID of the evaluation
            workflow_id: Dapr workflow instance ID
            source_topic: Dapr topic to publish to (e.g., "budapp-events")
            source: Source service name (e.g., "budapp")
            dataset_config: Optional dataset name for task estimation
        """
        self.log_file = log_file
        self.results_dir = results_dir
        self.experiment_id = experiment_id
        self.evaluation_id = evaluation_id
        self.workflow_id = workflow_id
        self.source_topic = source_topic
        self.source = source
        self.dataset_config = dataset_config
        self.initial_task_estimate = None

        # Track if we've emitted STARTED event
        self.started_emitted = False
        self.start_time = datetime.now(timezone.utc)

        # If dataset config provided, try to get initial estimate
        if dataset_config:
            self.initial_task_estimate = self._get_dataset_task_estimate(dataset_config)

    def _get_dataset_task_estimate(self, dataset_name):
        """Get initial task count estimate using OpenCompass library."""
        try:
            import importlib.util

            from mmengine.config import Config

            config_patterns = [
                f"{dataset_name}_gen",
                f"{dataset_name}_ppl",
                f"{dataset_name}",
            ]

            for pattern in config_patterns:
                try:
                    config_module = f"opencompass.configs.datasets.{dataset_name}.{pattern}"
                    spec = importlib.util.find_spec(config_module)
                    if spec and spec.origin:
                        cfg = Config.fromfile(spec.origin)

                        dataset_var_names = [
                            f"{dataset_name}_datasets",
                            "datasets",
                            f"{pattern}_datasets",
                        ]
                        for var_name in dataset_var_names:
                            if var_name in cfg:
                                datasets = cfg[var_name]
                                if isinstance(datasets, list):
                                    return len(datasets)

                        if hasattr(cfg, "__dict__"):
                            for key, value in cfg.__dict__.items():
                                if key.endswith("_datasets") and isinstance(value, list):
                                    return len(value)
                except Exception:
                    continue

            try:
                module_name = f"opencompass.configs.datasets.{dataset_name}"
                module = importlib.import_module(module_name)

                for attr_name in dir(module):
                    if attr_name.endswith("_datasets") and not attr_name.startswith("_"):
                        datasets = getattr(module, attr_name)
                        if isinstance(datasets, list):
                            return len(datasets)
            except Exception:
                pass

        except Exception:
            pass

        return None

    def _detect_dataset_from_log(self):
        """Detect dataset from log file by looking for 'Loading X_gen:' lines."""
        try:
            with open(self.log_file, "r") as f:
                for line in f:
                    if "Loading" in line and "_gen:" in line:
                        match = re.search(r"Loading (\w+)_gen:", line)
                        if match:
                            return match.group(1)
        except Exception:
            pass
        return None

    def get_status(self) -> Dict[str, Any]:
        """Get current evaluation status.

        Returns dict with:
            - total_tasks: Total number of tasks
            - completed_tasks: Number of completed tasks
            - in_progress: Number of in-progress tasks
            - progress: Progress percentage
            - eta: Estimated time remaining
            - evaluation_complete: Whether evaluation is complete
            - current_task: Current task name
            - sub_progress: Sub-task progress info
        """
        status = {}

        # Extract current run directory, total tasks, and completion status
        run_dir = None
        evaluation_complete = False
        in_current_run = False
        total_tasks_found = False

        with open(self.log_file, "r") as f:
            for line in f:
                if "Current exp folder:" in line:
                    folder = line.split("Current exp folder:")[1].strip()
                    if run_dir != folder:
                        run_dir = folder
                        in_current_run = True
                        total_tasks_found = False

                if in_current_run and not total_tasks_found and "Task [" in line:
                    task_str = line.split("Task [")[1].split("]")[0]
                    tasks = [t.strip() for t in task_str.split(",")]
                    status["total_tasks"] = len(tasks)
                    total_tasks_found = True

                if in_current_run and (
                    "write summary to" in line or "write csv to" in line or "write markdown summary to" in line
                ):
                    evaluation_complete = True

        status["evaluation_complete"] = evaluation_complete

        # If no Task line found yet, try to get estimate from dataset config
        if "total_tasks" not in status:
            if not self.initial_task_estimate:
                detected_dataset = self._detect_dataset_from_log()
                if detected_dataset:
                    self.initial_task_estimate = self._get_dataset_task_estimate(detected_dataset)
                    if self.initial_task_estimate:
                        status["dataset_detected"] = detected_dataset

            if self.initial_task_estimate:
                status["total_tasks"] = self.initial_task_estimate
                status["estimate_source"] = "config"

        if "total_tasks" not in status:
            status["total_tasks"] = 0

        # Count completed tasks from CURRENT run only
        if run_dir and os.path.exists(run_dir):
            pattern = os.path.join(run_dir, "predictions/**/*.json")
            all_files = glob.glob(pattern, recursive=True)
            completed_files = [f for f in all_files if not os.path.basename(f).startswith("tmp_")]
            status["completed_tasks"] = len(completed_files)
            status["in_progress"] = len(all_files) - len(completed_files)

            actual_files = status["completed_tasks"] + status["in_progress"]
            if actual_files > status.get("total_tasks", 0):
                status["total_tasks"] = actual_files
                status["total_is_estimate"] = True
        else:
            pattern = os.path.join(self.results_dir, "**/predictions/**/*.json")
            all_files = glob.glob(pattern, recursive=True)
            completed_files = [f for f in all_files if not os.path.basename(f).startswith("tmp_")]
            status["completed_tasks"] = len(completed_files)
            status["in_progress"] = len(all_files) - len(completed_files)

        # Extract batch ETA and sub-progress
        batch_eta = None
        sub_progress = None
        current_task_name = None

        with open(self.log_file, "r") as f:
            for line in f:
                if "Start inferencing" in line:
                    task_match = re.search(r"\[(.*?)\]", line)
                    if task_match:
                        current_task_name = task_match.group(1)

                if "|" in line and ("it/s]" in line or "s/it]" in line):
                    progress_match = re.search(r"(\d+)%.*?(\d+)/(\d+).*?\[.*?<([\d:]+)", line)
                    if progress_match:
                        remaining_time_str = progress_match.group(4)
                        time_parts = remaining_time_str.split(":")
                        if len(time_parts) == 2:
                            minutes = int(time_parts[0])
                            seconds = int(time_parts[1])
                            batch_eta = minutes * 60 + seconds
                        elif len(time_parts) == 3:
                            hours = int(time_parts[0])
                            minutes = int(time_parts[1])
                            seconds = int(time_parts[2])
                            batch_eta = hours * 3600 + minutes * 60 + seconds

                        sub_progress = {
                            "percent": int(progress_match.group(1)),
                            "current": int(progress_match.group(2)),
                            "total": int(progress_match.group(3)),
                        }

        status["current_task"] = current_task_name
        status["sub_progress"] = sub_progress
        status["batch_eta_seconds"] = batch_eta

        # Extract task durations for completed tasks
        durations = []
        current_task = None
        start_time = None

        def parse_ts(ts_str):
            year = datetime.now().year
            return datetime.strptime(f"{year}/{ts_str}", "%Y/%m/%d %H:%M:%S")

        with open(self.log_file, "r") as f:
            for line in f:
                if "Start inferencing" in line:
                    ts_str = line.split(" -")[0]
                    task_match = re.search(r"\[(.*?)\]", line)
                    if not task_match:
                        continue

                    task_name = task_match.group(1)
                    timestamp = parse_ts(ts_str)

                    if current_task and start_time:
                        duration = (timestamp - start_time).total_seconds()
                        durations.append(duration)

                    current_task = task_name
                    start_time = timestamp

        # Calculate statistics
        if durations:
            import numpy as np

            status["median_time"] = np.median(durations)
            status["avg_time"] = np.mean(durations)

            remaining = status["total_tasks"] - status["completed_tasks"]
            est_seconds = remaining * status["median_time"]
        else:
            est_seconds = None

        # Calculate ETA
        if status.get("batch_eta_seconds") is not None:
            if est_seconds:
                total_est_seconds = est_seconds + status["batch_eta_seconds"]
            else:
                total_est_seconds = status["batch_eta_seconds"]

            status["eta_seconds"] = int(total_est_seconds)
            hours = int(total_est_seconds // 3600)
            minutes = int((total_est_seconds % 3600) // 60)
            secs = int(total_est_seconds % 60)

            if hours > 0:
                status["eta"] = f"{hours}h {minutes}m {secs}s"
            elif minutes > 0:
                status["eta"] = f"{minutes}m {secs}s"
            else:
                status["eta"] = f"{secs}s"
        elif est_seconds:
            status["eta_seconds"] = int(est_seconds)
            hours = int(est_seconds // 3600)
            minutes = int((est_seconds % 3600) // 60)
            secs = int(est_seconds % 60)

            if hours > 0:
                status["eta"] = f"{hours}h {minutes}m {secs}s"
            elif minutes > 0:
                status["eta"] = f"{minutes}m {secs}s"
            else:
                status["eta"] = f"{secs}s"
        else:
            status["eta"] = "Calculating..."
            status["eta_seconds"] = None

        # Calculate progress
        if status.get("total_tasks", 0) > 0:
            base_progress = (status["completed_tasks"] / status["total_tasks"]) * 100

            if status["in_progress"] > 0 and sub_progress:
                task_contribution = 100 / status["total_tasks"]
                sub_contribution = (sub_progress["percent"] / 100) * task_contribution
                status["progress"] = base_progress + sub_contribution
            else:
                status["progress"] = base_progress
        else:
            status["progress"] = 0

        # Calculate elapsed time
        elapsed = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        status["time_elapsed_seconds"] = int(elapsed)

        return status

    def emit_event(self, event_type: str, status: Dict[str, Any]) -> bool:
        """Emit a Dapr notification event to eval_progress topic.

        Args:
            event_type: One of "eval.started", "eval.progress", "eval.completed"
            status: Status dict from get_status()

        Returns:
            True if successful, False otherwise
        """
        try:
            # Build notification request for eval_progress topic
            notification_req = NotificationRequest(
                workflow_id=self.workflow_id, payload={"event": event_type, "content": {}}
            )

            # Build content based on event type
            if event_type == "eval.started":
                notification_req.payload.content = NotificationContent(
                    title="Evaluation Started",
                    message=f"Starting evaluation with {status.get('total_tasks', 0)} tasks",
                    status=WorkflowStatus.STARTED,
                    metadata={
                        "experiment_id": str(self.experiment_id),
                        "evaluation_id": str(self.evaluation_id),
                        "total_tasks": status.get("total_tasks", 0),
                        "estimated_time_seconds": status.get("eta_seconds"),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )

            elif event_type == "eval.progress":
                notification_req.payload.content = NotificationContent(
                    title="Evaluation Progress",
                    message=f"Completed {status.get('completed_tasks', 0)}/{status.get('total_tasks', 0)} tasks ({status.get('progress', 0):.1f}%)",
                    status=WorkflowStatus.RUNNING,
                    metadata={
                        "experiment_id": str(self.experiment_id),
                        "evaluation_id": str(self.evaluation_id),
                        "total_tasks": status.get("total_tasks", 0),
                        "completed_tasks": status.get("completed_tasks", 0),
                        "failed_tasks": 0,  # TODO: Track failed tasks
                        "in_progress_tasks": status.get("in_progress", 0),
                        "progress_percentage": round(status.get("progress", 0), 1),
                        "time_elapsed_seconds": status.get("time_elapsed_seconds", 0),
                        "time_remaining_seconds": status.get("eta_seconds"),
                        "current_task": status.get("current_task", "N/A"),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )

            elif event_type == "eval.completed":
                success_rate = (
                    (status.get("completed_tasks", 0) / status.get("total_tasks", 1)) * 100
                    if status.get("total_tasks", 0) > 0
                    else 0
                )

                notification_req.payload.content = NotificationContent(
                    title="Evaluation Completed",
                    message=f"Completed {status.get('completed_tasks', 0)}/{status.get('total_tasks', 0)} tasks",
                    status=WorkflowStatus.COMPLETED,
                    metadata={
                        "experiment_id": str(self.experiment_id),
                        "evaluation_id": str(self.evaluation_id),
                        "total_tasks": status.get("total_tasks", 0),
                        "completed_tasks": status.get("completed_tasks", 0),
                        "failed_tasks": 0,  # TODO: Track failed tasks
                        "total_time_seconds": status.get("time_elapsed_seconds", 0),
                        "success_rate": round(success_rate, 1),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )

            # Publish notification via Dapr to eval_progress topic
            dapr_workflows.publish_notification(
                workflow_id=self.workflow_id,
                notification=notification_req,
                target_topic_name="eval_progress",  # Dedicated topic for eval progress
                target_name=self.source,
            )

            logger.info(
                f"✅ Emitted {event_type} to topic 'eval_progress': {notification_req.payload.content.message}"
            )
            return True

        except Exception as e:
            logger.error(f"⚠️ Failed to emit {event_type} event: {e}", exc_info=True)
            return False

    def check_once(self) -> Dict[str, Any]:
        """Check evaluation status once and emit appropriate event.

        Useful for:
        - Manual status checks
        - Testing event emission
        - One-time progress snapshots

        Returns:
            Current status dict
        """
        logger.info("📊 Checking evaluation status once...")

        status = self.get_status()

        # Determine which event to emit based on state
        if not self.started_emitted:
            # First check - emit STARTED
            self.emit_event("eval.started", status)
            self.started_emitted = True
        elif status.get("evaluation_complete"):
            # Evaluation done - emit COMPLETED
            self.emit_event("eval.completed", status)
        else:
            # In progress - emit PROGRESS
            self.emit_event("eval.progress", status)

        # Log status
        logger.info("=" * 80)
        logger.info(f"Experiment ID:    {self.experiment_id}")
        logger.info(f"Evaluation ID:    {self.evaluation_id}")
        logger.info(f"Total tasks:      {status.get('total_tasks', 0)}")
        logger.info(f"Completed:        {status.get('completed_tasks', 0)}")
        logger.info(f"Progress:         {status.get('progress', 0):.1f}%")
        logger.info(f"ETA:              {status.get('eta', 'Unknown')}")
        logger.info(f"Status:           {status.get('evaluation_complete') and 'COMPLETE' or 'RUNNING'}")
        logger.info("=" * 80)

        return status

    def monitor_with_events(self, interval: int = 30, max_iterations: Optional[int] = None) -> Dict[str, Any]:
        """Monitor evaluation progress and emit events via Dapr.

        Args:
            interval: Polling interval in seconds (default: 30)
            max_iterations: Max iterations before stopping (default: None = unlimited)

        Returns:
            Final status dict
        """
        logger.info("🔍 Starting Integrated Evaluation Monitor")
        logger.info("=" * 80)
        logger.info(f"Experiment ID: {self.experiment_id}")
        logger.info(f"Evaluation ID: {self.evaluation_id}")
        logger.info(f"Log file: {self.log_file}")
        logger.info(f"Results: {self.results_dir}")
        logger.info(f"Update interval: {interval} seconds")
        logger.info("Publishing to topic: eval_progress")
        logger.info("=" * 80)

        iteration = 0
        try:
            while True:
                status = self.get_status()

                # Emit EVAL_STARTED on first iteration
                if not self.started_emitted:
                    self.emit_event("eval.started", status)
                    self.started_emitted = True

                # Emit EVAL_PROGRESS
                self.emit_event("eval.progress", status)

                # Log progress locally
                logger.info(
                    f"Progress: {status.get('progress', 0):.1f}% | "
                    f"{status.get('completed_tasks', 0)}/{status.get('total_tasks', 0)} | "
                    f"ETA: {status.get('eta', 'Unknown')}"
                )

                # Check if complete
                if status.get("evaluation_complete"):
                    logger.info("\n✅ Evaluation complete!")
                    self.emit_event("eval.completed", status)
                    break

                iteration += 1
                if max_iterations and iteration >= max_iterations:
                    logger.info(f"⏰ Reached max iterations ({max_iterations})")
                    break

                time.sleep(interval)

        except KeyboardInterrupt:
            logger.info("\n👋 Monitoring stopped by user")
            status = self.get_status()

        except Exception as e:
            logger.error(f"❌ Monitor error: {e}", exc_info=True)
            status = self.get_status()

        return status


# Convenience functions to use from workflow


def check_status_once(
    log_file: str,
    results_dir: str,
    experiment_id: str,
    evaluation_id: str,
    workflow_id: str,
    source_topic: str,
    source: str,
    dataset_config: Optional[str] = None,
) -> Dict[str, Any]:
    """Check evaluation status once and emit appropriate event.

    Use this for:
    - Manual status checks
    - Testing event emission
    - Periodic snapshots from external scheduler

    Args:
        log_file: Path to evaluation log file
        results_dir: Path to results directory
        experiment_id: UUID of experiment
        evaluation_id: UUID of evaluation
        workflow_id: Dapr workflow instance ID
        source_topic: Dapr topic name
        source: Source service name
        dataset_config: Optional dataset name

    Returns:
        Current status dict

    Example:
        >>> status = check_status_once(
        ...     log_file="/path/to/nohup.out",
        ...     results_dir="/path/to/results",
        ...     experiment_id="exp-123",
        ...     evaluation_id="eval-456",
        ...     workflow_id="workflow-789",
        ...     source_topic="budapp-events",
        ...     source="budapp",
        ... )
        >>> print(f"Progress: {status['progress']:.1f}%")
    """
    monitor = IntegratedEvalMonitor(
        log_file=log_file,
        results_dir=results_dir,
        experiment_id=experiment_id,
        evaluation_id=evaluation_id,
        workflow_id=workflow_id,
        source_topic=source_topic,
        source=source,
        dataset_config=dataset_config,
    )

    return monitor.check_once()


def start_monitoring(
    log_file: str,
    results_dir: str,
    experiment_id: str,
    evaluation_id: str,
    workflow_id: str,
    source_topic: str,
    source: str,
    interval: int = 30,
    max_iterations: Optional[int] = None,
    dataset_config: Optional[str] = None,
) -> Dict[str, Any]:
    """Start continuous monitoring and emitting events.

    This runs in a loop, checking status every `interval` seconds
    and emitting progress events.

    Args:
        log_file: Path to evaluation log file
        results_dir: Path to results directory
        experiment_id: UUID of experiment
        evaluation_id: UUID of evaluation
        workflow_id: Dapr workflow instance ID
        source_topic: Dapr topic name
        source: Source service name
        interval: Polling interval in seconds (default: 30)
        max_iterations: Max iterations before stopping (default: None = unlimited)
        dataset_config: Optional dataset name

    Returns:
        Final status dict

    Example:
        >>> final_status = start_monitoring(
        ...     log_file="/path/to/nohup.out",
        ...     results_dir="/path/to/results",
        ...     experiment_id="exp-123",
        ...     evaluation_id="eval-456",
        ...     workflow_id="workflow-789",
        ...     source_topic="budapp-events",
        ...     source="budapp",
        ...     interval=30,  # Check every 30 seconds
        ... )
        >>> print(f"Final progress: {final_status['progress']:.1f}%")
    """
    monitor = IntegratedEvalMonitor(
        log_file=log_file,
        results_dir=results_dir,
        experiment_id=experiment_id,
        evaluation_id=evaluation_id,
        workflow_id=workflow_id,
        source_topic=source_topic,
        source=source,
        dataset_config=dataset_config,
    )

    return monitor.monitor_with_events(interval=interval, max_iterations=max_iterations)
