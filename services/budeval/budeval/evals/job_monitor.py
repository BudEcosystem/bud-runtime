# job_monitor.py
import json
from datetime import timedelta
from typing import Optional, TypedDict

import dapr.ext.workflow as wf
import requests
from budmicroframe.shared.dapr_workflow import DaprWorkflow

from budeval.commons.config import app_settings
from budeval.commons.logging import logging
from budeval.evals.schema import EvaluationRequest


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
    last_notification: dict  # Track last sent notification for deduplication


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


# ---- Helper: determine if notification should be sent ------------------------
def should_send_notification(
    current_progress: float,
    current_remaining_min: int,
    current_completed: int,
    last_notification: dict,
    attempt: int,
) -> tuple[bool, str]:
    """Determine if an ETA notification should be sent.

    Pure function - safe for Dapr workflow determinism.

    Rules:
    0. NEVER send 0%/0min notifications - skip all zeros
    1. Job completed (completed count changed) - send
    2. Progress went from 0 to non-zero (job started) - send
    3. Progress increased by >= 5% - send
    4. No notification for 10+ cycles (5 min) - send keepalive
    5. Otherwise - skip
    """
    PROGRESS_THRESHOLD = 5.0
    KEEPALIVE_CYCLES = 10  # 5 minutes at 30s intervals

    # Rule 0: NEVER send 0% / 0min notifications
    if current_progress == 0 and current_remaining_min == 0:
        return False, "skip_zeros"

    # Job completed (always notify completions)
    last_completed = last_notification.get("completed_jobs", 0) if last_notification else 0
    if current_completed > last_completed:
        return True, "job_completed"

    # First meaningful notification (has actual progress data)
    if not last_notification:
        return True, "first_meaningful"

    last_progress = last_notification.get("progress_percentage", 0)
    last_attempt = last_notification.get("attempt_sent", 0)

    # Job started (0 -> non-zero)
    if last_progress == 0 and current_progress > 0:
        return True, "job_started"

    # Significant progress (>= 5%)
    if current_progress - last_progress >= PROGRESS_THRESHOLD:
        return True, f"progress_{current_progress - last_progress:.1f}pct"

    # Keepalive (5 minutes)
    if attempt - last_attempt >= KEEPALIVE_CYCLES:
        return True, "keepalive"

    return False, "no_change"


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

        # Get evaluate_model_request from data (already a dict, not JSON string)
        evaluate_model_request_dict = data.get("evaluate_model_request_json_raw", {})
        if not evaluate_model_request_dict:
            logger_local.error("Missing evaluate_model_request_json_raw in notification data")
            return {"success": False, "error": "Missing evaluate_model_request_json_raw"}

        evaluate_model_request = EvaluationRequest.model_validate(evaluate_model_request_dict)

        message = f"{remaining_min}"  # Send minutes as integer string

        # Notifications
        # Set up notification
        workflow_name = "evaluate_model"

        # Notification Request
        notification_request = NotificationRequest.from_cloud_event(
            cloud_event=evaluate_model_request,
            name=workflow_name,
            workflow_id=data["workflow_id"],
        )

        notification_req = notification_request.model_copy(deep=True)

        notification_req.payload.event = "eta"
        notification_req.payload.content = NotificationContent(
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
        )

        dapr_workflows.publish_notification(
            workflow_id=data["workflow_id"],
            notification=notification_req,
            target_topic_name=evaluate_model_request.source_topic or data.get("source_topic"),
            target_name=evaluate_model_request.source or data.get("source") or "budeval",
        )

        # # Create notification
        # notification_req = NotificationRequest(
        #     payload={
        #         "event": "eta",  # Use existing eta event
        #         "content": NotificationContent(
        #             title=f"Evaluation Progress: {progress_pct:.1f}%",
        #             message=message,
        #             status=WorkflowStatus.RUNNING,
        #             metadata={
        #                 "progress_percentage": progress_pct,
        #                 "remaining_seconds": remaining_sec,
        #                 "remaining_minutes": remaining_min,
        #                 "completed_jobs": completed,
        #                 "running_jobs": running,
        #                 "total_jobs": total,
        #             },
        #         ),
        #     }
        # )

        # dapr_workflows.publish_notification(
        #     workflow_id=data["workflow_id"],
        #     notification=notification_req,
        #     target_topic_name=data["source_topic"],
        #     target_name=data["source"],
        # )

        logger_local.info(f"Sent ETA notification: {progress_pct:.1f}%, {remaining_min}m remaining")

        # Update ETA in budapp database via Dapr service invocation
        eval_id = evaluate_model_request_dict.get("eval_id")
        if eval_id and remaining_sec > 0:
            try:
                eta_url = (
                    f"http://localhost:{app_settings.dapr_http_port}/v1.0/invoke/{app_settings.bud_app_id}"
                    f"/method/experiments/internal/evaluations/eta"
                )
                requests.patch(
                    eta_url,
                    json={"evaluation_id": str(eval_id), "eta_seconds": remaining_sec},
                    timeout=5,
                )
                logger_local.debug(f"Updated ETA in budapp: {remaining_sec}s for evaluation {eval_id}")
            except Exception as eta_err:
                # Non-critical - log warning and continue
                logger_local.warning(f"Failed to update ETA in budapp: {eta_err}")

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
    if remaining_jobs:
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

                status = progress_info.get("status", "unknown")

                if status == "pending":
                    # Pod not ready yet (ContainerCreating, etc.)
                    pod_state = progress_info.get("pod_state", "unknown")
                    pod_phase = progress_info.get("pod_phase", "unknown")
                    logger_local.info(f"Job {job_id}: Pod not ready yet (phase={pod_phase}, container={pod_state})")
                elif progress_info.get("latest_progress"):
                    pct = progress_info.get("progress_percentage", 0)
                    remaining_sec = progress_info["latest_progress"].get("remaining_seconds", 0)
                    logger_local.info(f"Job {job_id}: {pct:.1f}% complete, ~{remaining_sec}s remaining")
                elif progress_info.get("eta_data"):
                    # Job has started but no progress yet
                    total_eta = progress_info["eta_data"].get("total_eta_seconds", 0)
                    logger_local.info(f"Job {job_id}: Started (estimated {total_eta}s total)")
                else:
                    logger_local.debug(f"Job {job_id}: No progress data yet")

    # Send notification with progress update (smart deduplication)
    if workflow_id and source_topic:
        # Calculate aggregate progress (only for jobs that have started)
        total_progress = 0
        max_remaining = 0  # Use MAX instead of average (user waits for slowest job)
        jobs_with_progress = 0
        pending_jobs = 0

        for job_id in remaining_jobs:
            if job_id in job_progress_map:
                progress_info = job_progress_map[job_id]
                status = progress_info.get("status", "unknown")

                # Skip pending jobs (container not ready yet)
                if status == "pending":
                    pending_jobs += 1
                    continue

                # Count progress for running/starting jobs
                total_progress += progress_info.get("progress_percentage", 0)

                latest = progress_info.get("latest_progress")
                if latest:
                    remaining_sec = latest.get("remaining_seconds", 0)
                    max_remaining = max(max_remaining, remaining_sec)  # Track slowest job
                    jobs_with_progress += 1

        # Calculate average progress (excluding pending jobs)
        running_jobs_count = len(remaining_jobs) - pending_jobs
        avg_progress = total_progress / running_jobs_count if running_jobs_count > 0 else 0

        # Smart notification: only send when there's meaningful change
        last_notification = data.get("last_notification", {})
        should_send, reason = should_send_notification(
            current_progress=round(avg_progress, 1),
            current_remaining_min=int(max_remaining / 60),
            current_completed=len(completed_jobs),
            last_notification=last_notification,
            attempt=attempt,
        )

        if should_send:
            notification_data = {
                "workflow_id": workflow_id,
                "source_topic": source_topic,
                "source": source or "budeval",
                "remaining_seconds": int(max_remaining),  # Use max (slowest job)
                "progress_percentage": round(avg_progress, 1),
                "completed_jobs": len(completed_jobs),
                "total_jobs": len(job_ids),
                "running_jobs": len(remaining_jobs),
                "failed_jobs": len(failed_jobs),
                "evaluate_model_request_json_raw": data.get("evaluate_model_request_json_raw"),
            }

            yield ctx.call_activity(send_eta_notification, input=json.dumps(notification_data))

            # Update last notification state for next cycle
            data["last_notification"] = {
                "progress_percentage": round(avg_progress, 1),
                "remaining_minutes": int(max_remaining / 60),
                "completed_jobs": len(completed_jobs),
                "attempt_sent": attempt,
            }

            if not ctx.is_replaying:
                logger_local.info(
                    f"Sent ETA notification ({reason}): {avg_progress:.1f}%, {int(max_remaining / 60)}m remaining"
                )
        else:
            if not ctx.is_replaying:
                logger_local.debug(
                    f"Skipped notification ({reason}): {avg_progress:.1f}%, {int(max_remaining / 60)}m remaining"
                )

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
    data["job_progress_map"] = job_progress_map  # Persist progress
    data["last_notification"] = data.get("last_notification", {})  # Persist notification state for deduplication
    # CRITICAL: Persist notification parameters across continue_as_new cycles
    data["workflow_id"] = workflow_id
    data["source_topic"] = source_topic
    data["source"] = source or "budeval"  # Ensure source is never None
    data["evaluate_model_request_json_raw"] = data.get("evaluate_model_request_json_raw")  # Persist for notifications
    yield ctx.create_timer(fire_at=ctx.current_utc_datetime + timedelta(seconds=poll_interval))
    ctx.continue_as_new(json.dumps(data))
    return
