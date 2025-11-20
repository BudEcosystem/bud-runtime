# job_monitor.py
import json
from datetime import timedelta
from typing import Optional, TypedDict

import dapr.ext.workflow as wf
from budmicroframe.shared.dapr_workflow import DaprWorkflow

from budeval.commons.logging import logging


logger = logging.getLogger(__name__)


dapr_workflows = DaprWorkflow()


# ---- Wire types (optional, for clarity) --------------------------------------
class MonitorRequest(TypedDict, total=False):
    job_ids: list[str]  # FIXED: was job_id
    kubeconfig: Optional[str]
    namespace: Optional[str]
    poll_interval: int  # seconds; default 30
    max_attempts: int  # hard cap; default 240 (~2h @30s)
    attempt: int  # internal: incremented each tick
    completed_jobs: list[str]  # Track completed jobs
    failed_jobs: list[str]  # Track failed jobs
    job_timing_map: dict[str, dict]  # Track job timing: {job_id: {startTime, completionTime, status}}
    passthrough: dict  # caller-defined bag (not used here)


class MonitorResult(TypedDict, total=False):
    status: str  # 'completed' | 'timeout' | 'error'
    completed_jobs: list[str]
    failed_jobs: list[str]
    attempts: int
    job_details: dict  # Timing and status info: {job_id: {startTime, completionTime, status}}


# ---- Activity: one-shot poll (SYNC, keep it simple) --------------------------
@dapr_workflows.register_activity  # FIXED: was @wf.WorkflowActivity
def monitor_job_simple(ctx: wf.WorkflowActivityContext, monitor_request: str) -> dict:
    """Monitor jobs and return their statuses.

    Returns:
        {
          "success": bool,
          "job_statuses": {"job1": {"status": "..."}, ...},
          "error": Optional[str]
        }
    """
    logger_local = logging.getLogger("::MONITOR:: SimplePoll")
    try:
        req = json.loads(monitor_request)
        job_ids = req["job_ids"]  # FIXED: was job_id
        kubeconfig = req.get("kubeconfig")

        # Use your existing orchestrator
        from .ansible_orchestrator import AnsibleOrchestrator

        orch = AnsibleOrchestrator()

        result = orch.check_jobs_status(job_ids, kubeconfig)

        return {"success": True, "job_statuses": result}

    except Exception as e:
        logger_local.error(f"monitor_job_simple error: {e}", exc_info=True)
        return {"success": False, "job_statuses": {}, "error": str(e)}


# ---- Activity: parse job logs for ETA/progress -------------------------------
@dapr_workflows.register_activity
def parse_job_logs_activity(ctx: wf.WorkflowActivityContext, parse_request: str) -> dict:
    """Parse pod logs for ETA and progress data.

    Args:
        parse_request: JSON string with {
            "job_ids": ["job1", "job2"],
            "kubeconfig": "...",
            "namespace": "..."
        }

    Returns:
        {
            "success": bool,
            "log_data": {
                "job_id": {
                    "eta_data": {...},
                    "latest_progress": {...},
                    "progress_percentage": 68.18
                }
            },
            "error": Optional[str]
        }
    """
    logger_local = logging.getLogger("::MONITOR:: LogParser")
    try:
        req = json.loads(parse_request)
        job_ids = req.get("job_ids", [])
        kubeconfig = req.get("kubeconfig")

        from .ansible_orchestrator import AnsibleOrchestrator

        orch = AnsibleOrchestrator()
        result = orch.parse_job_logs(job_ids, kubeconfig)

        return {"success": True, "log_data": result}

    except Exception as e:
        logger_local.error(f"parse_job_logs_activity error: {e}", exc_info=True)
        return {"success": False, "log_data": {}, "error": str(e)}


# ---- Activity: send ETA notification -----------------------------------------
@dapr_workflows.register_activity
def send_eta_notification(ctx: wf.WorkflowActivityContext, notification_data: str) -> dict:
    """Send ETA notification using existing notification infrastructure.

    Args:
        notification_data: JSON with {
            "workflow_id": "...",
            "source_topic": "...",
            "source": "...",
            "remaining_seconds": 158,
            "progress_percentage": 68.1,
            "completed_jobs": 1,
            "total_jobs": 3,
            "running_jobs": 2,
            "failed_jobs": 0
        }
    """
    logger_local = logging.getLogger("::MONITOR:: ETANotification")

    try:
        data = json.loads(notification_data)

        from budmicroframe.commons.constants import WorkflowStatus
        from budmicroframe.commons.schemas import NotificationContent, NotificationRequest

        # Format remaining time
        remaining_sec = data.get("remaining_seconds", 0)
        remaining_min = int(remaining_sec / 60)

        # Build message
        progress_pct = data.get("progress_percentage", 0)
        completed = data.get("completed_jobs", 0)
        total = data.get("total_jobs", 0)
        running = data.get("running_jobs", 0)

        message = f"{remaining_sec}"  # Send seconds for compatibility

        # Create notification
        notification_req = NotificationRequest(
            payload={
                "event": "eta",  # Use existing eta event
                "content": NotificationContent(
                    title=f"Evaluation Progress: {progress_pct:.1f}%",
                    message=message,
                    status=WorkflowStatus.RUNNING,
                    metadata={
                        "progress_percentage": progress_pct,
                        "remaining_seconds": remaining_sec,
                        "remaining_minutes": remaining_min,
                        "completed_jobs": completed,
                        "running_jobs": running,
                        "total_jobs": total,
                    },
                ),
            }
        )

        dapr_workflows.publish_notification(
            workflow_id=data["workflow_id"],
            notification=notification_req,
            target_topic_name=data["source_topic"],
            target_name=data["source"],
        )

        logger_local.info(f"Sent ETA notification: {progress_pct:.1f}%, {remaining_min}m remaining")
        return {"success": True}

    except Exception as e:
        logger_local.error(f"Failed to send ETA notification: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


# ---- Child Workflow: periodic poll + continue_as_new -------------------------
@dapr_workflows.register_workflow  # FIXED: was @wf.Workflow
def monitor_job_workflow(ctx: wf.DaprWorkflowContext, monitor_request: str):
    """Poll multiple jobs until they reach terminal status.

    Uses create_timer + continue_as_new to keep history small.
    Now includes:
    - Log parsing for ETA/progress
    - Real-time notifications every 30s via callback
    """
    logger_local = logging.getLogger("::MONITOR:: Workflow")

    # Parse and default
    try:
        data: MonitorRequest = json.loads(monitor_request)
    except Exception as e:
        logger_local.error(f"Bad monitor_request: {e}", exc_info=True)
        return {"status": "error", "completed_jobs": [], "failed_jobs": [], "attempts": 0}

    job_ids = data.get("job_ids", [])
    if not job_ids:
        return {"status": "error", "completed_jobs": [], "failed_jobs": [], "attempts": 0}

    poll_interval = int(data.get("poll_interval", 30))
    max_attempts = int(data.get("max_attempts", 240))
    attempt = int(data.get("attempt", 1))

    completed_jobs = data.get("completed_jobs", [])
    failed_jobs = data.get("failed_jobs", [])
    job_timing_map = data.get("job_timing_map", {})
    job_progress_map = data.get("job_progress_map", {})  # NEW: Track progress

    # Get notification passthrough data
    workflow_id = data.get("workflow_id")
    source_topic = data.get("source_topic")
    source = data.get("source")

    # Log monitoring progress
    if not ctx.is_replaying:
        logger_local.info(
            f"Monitor check #{attempt}: tracking {len(job_ids)} jobs, {len(completed_jobs)} completed, {len(failed_jobs)} failed"
        )

    # Single poll
    poll_result = yield ctx.call_activity(monitor_job_simple, input=json.dumps(data))

    if not (isinstance(poll_result, dict) and poll_result.get("success")):
        # Non-fatal: retry until max_attempts
        if attempt >= max_attempts:
            return {
                "status": "timeout",
                "completed_jobs": completed_jobs,
                "failed_jobs": failed_jobs,
                "attempts": attempt,
            }
        data["attempt"] = attempt + 1
        yield ctx.create_timer(fire_at=ctx.current_utc_datetime + timedelta(seconds=poll_interval))
        ctx.continue_as_new(json.dumps(data))
        return

    # Process job statuses
    job_statuses = poll_result.get("job_statuses", {})

    for job_id, status_info in job_statuses.items():
        status = status_info.get("status", "").lower()

        # Store timing info for all jobs
        job_timing_map[job_id] = status_info

        if status == "succeeded" and job_id not in completed_jobs:
            completed_jobs.append(job_id)
            if not ctx.is_replaying:
                logger_local.info(f"Job {job_id} completed successfully")

        elif status == "failed" and job_id not in failed_jobs:
            failed_jobs.append(job_id)
            if not ctx.is_replaying:
                logger_local.error(f"Job {job_id} failed")

    # Check if all jobs are done
    remaining_jobs = [j for j in job_ids if j not in completed_jobs and j not in failed_jobs]

    # NEW: Parse logs for progress/ETA (only for running jobs)
    if remaining_jobs and not ctx.is_replaying:
        log_parse_result = yield ctx.call_activity(
            parse_job_logs_activity,
            input=json.dumps(
                {"job_ids": remaining_jobs, "kubeconfig": data.get("kubeconfig"), "namespace": data.get("namespace")}
            ),
        )

        if log_parse_result.get("success"):
            log_data = log_parse_result.get("log_data", {})

            # Update progress map
            for job_id, progress_info in log_data.items():
                job_progress_map[job_id] = progress_info

                if progress_info.get("latest_progress"):
                    pct = progress_info.get("progress_percentage", 0)
                    remaining_sec = progress_info["latest_progress"].get("remaining_seconds", 0)
                    logger_local.info(f"Job {job_id}: {pct:.1f}% complete, ~{remaining_sec}s remaining")

    # NEW: Send notification with progress update (EVERY CYCLE)
    if workflow_id and source_topic and source and not ctx.is_replaying:
        # Calculate aggregate progress
        total_progress = 0
        total_remaining = 0
        jobs_with_progress = 0

        for job_id in remaining_jobs:
            if job_id in job_progress_map:
                progress_info = job_progress_map[job_id]
                total_progress += progress_info.get("progress_percentage", 0)

                latest = progress_info.get("latest_progress")
                if latest:
                    total_remaining += latest.get("remaining_seconds", 0)
                    jobs_with_progress += 1

        # Calculate averages
        avg_progress = total_progress / len(remaining_jobs) if remaining_jobs else 100
        avg_remaining = total_remaining / jobs_with_progress if jobs_with_progress > 0 else 0

        # Trigger notification via external activity
        notification_data = {
            "workflow_id": workflow_id,
            "source_topic": source_topic,
            "source": source,
            "remaining_seconds": int(avg_remaining),
            "progress_percentage": round(avg_progress, 1),
            "completed_jobs": len(completed_jobs),
            "total_jobs": len(job_ids),
            "running_jobs": len(remaining_jobs),
            "failed_jobs": len(failed_jobs),
        }

        yield ctx.call_activity(send_eta_notification, input=json.dumps(notification_data))

    if not remaining_jobs:
        if not ctx.is_replaying:
            logger_local.info(f"All jobs completed: {len(completed_jobs)} succeeded, {len(failed_jobs)} failed")
        return {
            "status": "completed",
            "completed_jobs": completed_jobs,
            "failed_jobs": failed_jobs,
            "job_details": job_timing_map,
            "job_progress_map": job_progress_map,
            "attempts": attempt,
        }

    # Still have jobs running
    if attempt >= max_attempts:
        if not ctx.is_replaying:
            logger_local.warning(f"Monitoring timeout after {attempt} attempts. Remaining jobs: {remaining_jobs}")
        return {
            "status": "timeout",
            "completed_jobs": completed_jobs,
            "failed_jobs": failed_jobs,
            "job_details": job_timing_map,
            "job_progress_map": job_progress_map,
            "remaining_jobs": remaining_jobs,
            "attempts": attempt,
        }

    # Continue monitoring
    data["attempt"] = attempt + 1
    data["completed_jobs"] = completed_jobs
    data["failed_jobs"] = failed_jobs
    data["job_timing_map"] = job_timing_map
    data["job_progress_map"] = job_progress_map  # NEW: Persist progress
    yield ctx.create_timer(fire_at=ctx.current_utc_datetime + timedelta(seconds=poll_interval))
    ctx.continue_as_new(json.dumps(data))
    return
