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


# ---- Child Workflow: periodic poll + continue_as_new -------------------------
@dapr_workflows.register_workflow  # FIXED: was @wf.Workflow
def monitor_job_workflow(ctx: wf.DaprWorkflowContext, monitor_request: str):
    """Poll multiple jobs until they reach terminal status.

    Uses create_timer + continue_as_new to keep history small.
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

    if not remaining_jobs:
        if not ctx.is_replaying:
            logger_local.info(f"All jobs completed: {len(completed_jobs)} succeeded, {len(failed_jobs)} failed")
        return {
            "status": "completed",
            "completed_jobs": completed_jobs,
            "failed_jobs": failed_jobs,
            "job_details": job_timing_map,
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
            "remaining_jobs": remaining_jobs,
            "attempts": attempt,
        }

    # Continue monitoring
    data["attempt"] = attempt + 1
    data["completed_jobs"] = completed_jobs
    data["failed_jobs"] = failed_jobs
    data["job_timing_map"] = job_timing_map
    yield ctx.create_timer(fire_at=ctx.current_utc_datetime + timedelta(seconds=poll_interval))
    ctx.continue_as_new(json.dumps(data))
    return
