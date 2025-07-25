import asyncio
import random
from dataclasses import dataclass
from datetime import timedelta

import dapr.ext.workflow as wf

from budcluster.shared.dapr_service import DaprWorkflows

dapr_workflows = DaprWorkflows()

global_counter = 0

@dataclass
class JobStatus:
    job_id: str
    is_healthy: bool

@dapr_workflows.register_workflow
def status_monitor_workflow(ctx: wf.DaprWorkflowContext, job: JobStatus):
    # poll a status endpoint associated with this job
    global global_counter
    global_counter += 1
    status = yield ctx.call_activity(check_status, input=job)
    if not ctx.is_replaying:
        print(f"Job '{job.job_id}' is {status}.")

    if status == "healthy":
        job.is_healthy = True
        next_sleep_interval = 60  # check less frequently when healthy
    else:
        if job.is_healthy:
            job.is_healthy = False
            ctx.call_activity(send_alert, input=f"Job '{job.job_id}' is unhealthy!")
        next_sleep_interval = 5  # check more frequently when unhealthy

    yield ctx.create_timer(fire_at=ctx.current_utc_datetime + timedelta(minutes=next_sleep_interval))

    # restart from the beginning with a new JobStatus input
    if global_counter < 10:
        ctx.continue_as_new(job)
    else:
        return

@dapr_workflows.register_activity
def check_status(ctx, _) -> str:
    return random.choice(["healthy", "unhealthy"])

@dapr_workflows.register_activity
def send_alert(ctx, message: str):
    print(f'*** Alert: {message}')


if __name__ == "__main__":
    asyncio.run(dapr_workflows.schedule_workflow(
        workflow_name="status_monitor_workflow",
        workflow_input=JobStatus(job_id="123", is_healthy=False),
    ))
