#!/usr/bin/env python3
"""Simple demo of the evaluation monitor with your actual files.

This is a standalone version that doesn't need OpenCompass imports.
"""

import glob
import os
import re
import time
from datetime import datetime

from budeval.commons.logging import logging


logger = logging.getLogger(__name__)


class SimpleMonitor:
    """Simplified monitor for demo purposes."""

    def __init__(self, log_file, results_dir, dataset_config=None):
        """Initialize the SimpleMonitor.

        Args:
            log_file: Path to the evaluation log file
            results_dir: Path to the results directory
            dataset_config: Optional dataset configuration
        """
        self.log_file = log_file
        self.results_dir = results_dir
        self.dataset_config = dataset_config
        self.initial_task_estimate = None

        # If dataset config provided, try to get initial estimate
        if dataset_config:
            self.initial_task_estimate = self._get_dataset_task_estimate(dataset_config)

    def _get_dataset_task_estimate(self, dataset_name):
        """Get initial task count estimate using OpenCompass library."""
        try:
            # Try to use mmengine to load the dataset config
            import importlib.util

            from mmengine.config import Config

            # Try common config file patterns
            config_patterns = [
                f"{dataset_name}_gen",
                f"{dataset_name}_ppl",
                f"{dataset_name}",
            ]

            for pattern in config_patterns:
                try:
                    # Use OpenCompass's config system to load dataset
                    # This works even if the file structure is different
                    config_module = f"opencompass.configs.datasets.{dataset_name}.{pattern}"

                    # Try to import the module
                    spec = importlib.util.find_spec(config_module)
                    if spec and spec.origin:
                        # Load config using mmengine
                        cfg = Config.fromfile(spec.origin)

                        # Look for dataset list in config
                        # Common patterns: {dataset_name}_datasets, datasets
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

                        # If cfg is a dict-like object, try direct access
                        if hasattr(cfg, "__dict__"):
                            for key, value in cfg.__dict__.items():
                                if key.endswith("_datasets") and isinstance(value, list):
                                    return len(value)

                except Exception:
                    continue

            # Fallback: Try to import and introspect the module directly
            try:
                module_name = f"opencompass.configs.datasets.{dataset_name}"
                module = importlib.import_module(module_name)

                # Look for dataset variables
                for attr_name in dir(module):
                    if attr_name.endswith("_datasets") and not attr_name.startswith("_"):
                        datasets = getattr(module, attr_name)
                        if isinstance(datasets, list):
                            return len(datasets)
            except Exception:
                pass

        except Exception:
            # Silently fail - will fallback to log-based detection
            pass

        return None

    def _detect_dataset_from_log(self):
        """Detect dataset from log file by looking for 'Loading X_gen:' lines."""
        try:
            with open(self.log_file, "r") as f:
                for line in f:
                    # Look for "Loading <dataset>_gen:" pattern
                    if "Loading" in line and "_gen:" in line:
                        match = re.search(r"Loading (\w+)_gen:", line)
                        if match:
                            return match.group(1)
        except Exception:
            pass
        return None

    def get_status(self):
        """Get current status."""
        status = {}

        # Extract current run directory, total tasks, and completion status
        run_dir = None
        evaluation_complete = False
        in_current_run = False
        total_tasks_found = False

        with open(self.log_file, "r") as f:
            for line in f:
                # Get current run directory - marks the start of a new run
                if "Current exp folder:" in line:
                    folder = line.split("Current exp folder:")[1].strip()
                    # If this is a new run, reset tracking
                    if run_dir != folder:
                        run_dir = folder
                        in_current_run = True
                        total_tasks_found = False

                # Get total tasks from "Task [...]" line at the start (contains all tasks comma-separated)
                # This line appears right after "Current exp folder" and lists ALL tasks
                if in_current_run and not total_tasks_found and "Task [" in line:
                    task_str = line.split("Task [")[1].split("]")[0]
                    # Split by comma to get all task names
                    tasks = [t.strip() for t in task_str.split(",")]
                    status["total_tasks"] = len(tasks)
                    total_tasks_found = True

                # Check if evaluation completed (summary writing indicates completion)
                if in_current_run and (
                    "write summary to" in line or "write csv to" in line or "write markdown summary to" in line
                ):
                    evaluation_complete = True

        status["evaluation_complete"] = evaluation_complete

        # If no Task line found yet, try to get estimate from dataset config
        if "total_tasks" not in status:
            # First, try to auto-detect dataset from log
            if not self.initial_task_estimate:
                detected_dataset = self._detect_dataset_from_log()
                if detected_dataset:
                    self.initial_task_estimate = self._get_dataset_task_estimate(detected_dataset)
                    if self.initial_task_estimate:
                        status["dataset_detected"] = detected_dataset

            # Use the estimate if we have one
            if self.initial_task_estimate:
                status["total_tasks"] = self.initial_task_estimate
                status["estimate_source"] = "config"

        # Fallback if no task list found
        if "total_tasks" not in status:
            status["total_tasks"] = 0

        # Count completed tasks from CURRENT run only
        if run_dir and os.path.exists(run_dir):
            pattern = os.path.join(run_dir, "predictions/**/*.json")
            all_files = glob.glob(pattern, recursive=True)
            # Filter out temporary files (tmp_*.json indicate in-progress tasks)
            completed_files = [f for f in all_files if not os.path.basename(f).startswith("tmp_")]
            status["completed_tasks"] = len(completed_files)
            status["in_progress"] = len(all_files) - len(completed_files)

            # Adjust total_tasks if we have more files than expected
            # (happens when tasks get partitioned into multiple output files)
            # Keep total as "at least" the current number of files
            actual_files = status["completed_tasks"] + status["in_progress"]
            if actual_files > status.get("total_tasks", 0):
                status["total_tasks"] = actual_files
                status["total_is_estimate"] = True  # Flag that total may still grow
        else:
            # Fallback
            pattern = os.path.join(self.results_dir, "**/predictions/**/*.json")
            all_files = glob.glob(pattern, recursive=True)
            completed_files = [f for f in all_files if not os.path.basename(f).startswith("tmp_")]
            status["completed_tasks"] = len(completed_files)
            status["in_progress"] = len(all_files) - len(completed_files)

        # First pass: Extract batch ETA and sub-progress (needed for ETA calculation)
        batch_eta = None
        sub_progress = None
        current_task_name = None

        with open(self.log_file, "r") as f:
            for line in f:
                if "Start inferencing" in line:
                    task_match = re.search(r"\[(.*?)\]", line)
                    if task_match:
                        current_task_name = task_match.group(1)

                # Extract sub-task progress like "32/33 [05:27<00:10, 10.75s/it]"
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

        # Second pass: Extract task durations for completed tasks
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

            # Estimate remaining time based on completed tasks
            remaining = status["total_tasks"] - status["completed_tasks"]
            est_seconds = remaining * status["median_time"]
        else:
            est_seconds = None

        # Now calculate ETA (batch_eta_seconds is already set above)
        if status.get("batch_eta_seconds") is not None:
            # Add batch ETA to task-based estimate
            if est_seconds:
                total_est_seconds = est_seconds + status["batch_eta_seconds"]
            else:
                # Only batch ETA available (first task)
                total_est_seconds = status["batch_eta_seconds"]

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
            # No batch ETA, use task-based estimate
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

        # Calculate progress
        if status.get("total_tasks", 0) > 0:
            base_progress = (status["completed_tasks"] / status["total_tasks"]) * 100

            # Add sub-task progress if available
            if status["in_progress"] > 0 and sub_progress:
                # Each task contributes 1/total_tasks to overall progress
                task_contribution = 100 / status["total_tasks"]
                sub_contribution = (sub_progress["percent"] / 100) * task_contribution
                status["progress"] = base_progress + sub_contribution
            else:
                status["progress"] = base_progress
        else:
            status["progress"] = 0

        return status

    def display_progress(self, status):
        """Display progress bar."""
        progress = status.get("progress", 0)
        completed = status.get("completed_tasks", 0)
        total = status.get("total_tasks", 0)
        eta = status.get("eta", "Unknown")

        # Progress bar
        bar_width = 40
        filled = int(bar_width * progress / 100)
        bar = "█" * filled + "░" * (bar_width - filled)

        # Current task (truncated)
        current = status.get("current_task", "N/A")
        if len(current) > 40:
            current = current[:37] + "..."

        # Sub-progress info
        sub_info = ""
        sub_progress = status.get("sub_progress")
        if sub_progress:
            sub_info = f" [{sub_progress['current']}/{sub_progress['total']} batches]"

        # Log update (use \r for overwriting in terminal, but logger will handle it)
        progress_msg = f"[{bar}] {progress:.1f}% | {completed}/{total} | ETA: {eta:>10}{sub_info} | {current}"
        logger.info(progress_msg)

    def monitor(self, interval=10, max_iterations=None):
        """Monitor with live updates."""
        logger.info("🔍 OpenCompass Evaluation Monitor")
        logger.info("=" * 80)
        logger.info(f"Log file: {self.log_file}")
        logger.info(f"Results: {self.results_dir}")
        logger.info(f"Update interval: {interval} seconds")
        logger.info("=" * 80)
        logger.info("\nPress Ctrl+C to stop\n")

        iteration = 0
        try:
            while True:
                status = self.get_status()
                self.display_progress(status)

                # Check if complete (using the reliable completion marker)
                if status.get("evaluation_complete"):
                    logger.info("\n\n✅ Evaluation complete!")
                    logger.info("   Summary written to results folder")
                    break

                iteration += 1
                if max_iterations and iteration >= max_iterations:
                    break

                time.sleep(interval)

        except KeyboardInterrupt:
            logger.info("\n\n👋 Monitoring stopped by user")
            status = self.get_status()
            logger.info("\nFinal Status:")
            logger.info(f"  Progress: {status.get('progress', 0):.1f}%")
            logger.info(f"  Completed: {status.get('completed_tasks', 0)}/{status.get('total_tasks', 0)}")
            logger.info(f"  ETA: {status.get('eta', 'Unknown')}")


def main():
    """Run the demo."""
    import argparse

    parser = argparse.ArgumentParser(description="Demo: OpenCompass Evaluation Monitor")
    parser.add_argument("--log", default="nohup.out", help="Path to log file (default: nohup.out)")
    parser.add_argument("--results", default="results/", help="Path to results directory (default: results/)")
    parser.add_argument("--interval", type=int, default=10, help="Update interval in seconds (default: 10)")
    parser.add_argument("--once", action="store_true", help="Check status once and exit")
    parser.add_argument(
        "--dataset",
        type=str,
        default=None,
        help="Dataset name (e.g., mmlu, gsm8k) for better task count estimation. If not provided, will auto-detect from log.",
    )

    args = parser.parse_args()

    monitor = SimpleMonitor(args.log, args.results, dataset_config=args.dataset)

    if args.once:
        # Single status check
        logger.info("📊 Checking evaluation status...\n")
        status = monitor.get_status()

        logger.info("=" * 80)
        if status.get("evaluation_complete"):
            logger.info("✅ OpenCompass Evaluation COMPLETE")
        else:
            logger.info("OpenCompass Evaluation Status")
        logger.info("=" * 80)

        # Show total with indicator if it's still growing
        total_str = str(status.get("total_tasks", 0))
        if status.get("total_is_estimate") and not status.get("evaluation_complete"):
            total_str += "+"  # Indicates "at least this many, may grow"

        # Show dataset info if detected
        if status.get("dataset_detected"):
            logger.info(f"Dataset:          {status.get('dataset_detected')} (auto-detected)")

        logger.info(f"Total tasks:      {total_str}")

        # Show note if estimate is from config
        if status.get("estimate_source") == "config" and status.get("total_tasks") > 0:
            logger.info(
                f"                  (base datasets: {status.get('total_tasks')}, actual tasks typically 2-3x due to partitioning)"
            )

        logger.info(f"Completed:        {status.get('completed_tasks', 0)}")
        logger.info(f"Remaining:        {status.get('total_tasks', 0) - status.get('completed_tasks', 0)}")
        logger.info(f"Progress:         {status.get('progress', 0):.1f}%")

        if status.get("evaluation_complete"):
            logger.info("Status:           ✅ COMPLETE")
        else:
            logger.info(f"ETA:              {status.get('eta', 'Unknown')}")

        if "avg_time" in status:
            logger.info("\nTiming Statistics:")
            logger.info(f"  Average:        {status.get('avg_time', 0):.1f}s per task")
            logger.info(f"  Median:         {status.get('median_time', 0):.1f}s per task")

        if not status.get("evaluation_complete"):
            current = status.get("current_task", "N/A")
            logger.info(f"\nCurrent task:     {current}")

            # Show sub-progress if available
            sub_progress = status.get("sub_progress")
            if sub_progress:
                logger.info(
                    f"Task progress:    {sub_progress['current']}/{sub_progress['total']} batches ({sub_progress['percent']}%)"
                )

            # Show in-progress count
            if status.get("in_progress", 0) > 0:
                logger.info(f"In progress:      {status.get('in_progress')} task(s)")

        logger.info("=" * 80)
    else:
        # Continuous monitoring
        monitor.monitor(interval=args.interval)


if __name__ == "__main__":
    main()
