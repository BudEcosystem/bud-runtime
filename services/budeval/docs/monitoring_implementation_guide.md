# Implementation Guide: Kubernetes Job Monitoring with Dapr Workflows

## Overview
Based on Dapr's Monitor Pattern documentation, here's the complete implementation for monitoring Kubernetes evaluation jobs.

---

## 1. Add Job Status Check Activity

**File**: `budeval/evals/workflows.py`

Add this new activity after the `deploy_eval_job_v2` activity (around line 380):

```python
@dapr_workflows.register_activity
@staticmethod
def check_job_status(
    ctx: wf.WorkflowActivityContext,
    check_request: str,
) -> dict:
    """Check status of Kubernetes jobs.

    Args:
        check_request: JSON string with {"job_ids": ["job1", "job2"]}

    Returns:
        {
            "jobs": {
                "job1": {
                    "status": "Running|Succeeded|Failed",
                    "phase": "Pending|Running|Succeeded|Failed",
                    "message": "Error message if failed",
                    "completionTime": "2025-10-17T00:10:00Z"
                },
                "job2": {...}
            }
        }
    """
    logger = logging.getLogger("::EVAL:: CheckJobStatus")

    workflow_id = ctx.workflow_id
    request = json.loads(check_request)
    job_ids = request.get("job_ids", [])

    logger.info(f"Checking status for jobs: {job_ids}")

    try:
        job_statuses = AnsibleOrchestrator().check_jobs_status(job_ids)

        return SuccessResponse(
            code=HTTPStatus.OK.value,
            message="Job status retrieved",
            param={"jobs": job_statuses},
        ).model_dump(mode="json")

    except Exception as e:
        error_msg = f"Error checking job status for workflow_id: {workflow_id}, error: {e}"
        logger.error(error_msg)
        return ErrorResponse(
            message="Failed to check job status",
            code=HTTPStatus.INTERNAL_SERVER_ERROR.value,
        ).model_dump(mode="json")
```

---

## 2. Add Result Extraction Activity

**File**: `budeval/evals/workflows.py`

Add after `check_job_status` activity:

```python
@dapr_workflows.register_activity
@staticmethod
def extract_job_results(
    ctx: wf.WorkflowActivityContext,
    extract_request: str,
) -> dict:
    """Extract results from completed jobs.

    Args:
        extract_request: JSON string with {
            "eval_id": "...",
            "job_ids": ["job1", "job2"]
        }

    Returns:
        {
            "results": {
                "job1": {
                    "dataset": "demo_gsm8k",
                    "metric": "accuracy",
                    "score": 65.62,
                    "summary_files": {...}
                },
                "job2": {...}
            }
        }
    """
    logger = logging.getLogger("::EVAL:: ExtractJobResults")

    workflow_id = ctx.workflow_id
    request = json.loads(extract_request)
    eval_id = request.get("eval_id")
    job_ids = request.get("job_ids", [])

    logger.info(f"Extracting results for eval_id: {eval_id}, jobs: {job_ids}")

    try:
        # Import results processor
        from budeval.evals.results_processor import ResultsProcessor

        processor = ResultsProcessor()
        all_results = {}

        for job_id in job_ids:
            try:
                results = processor.extract_eval_results(eval_id, job_id)
                all_results[job_id] = results
                logger.info(f"Extracted results for job {job_id}")
            except Exception as e:
                logger.error(f"Failed to extract results for job {job_id}: {e}")
                all_results[job_id] = {"error": str(e)}

        return SuccessResponse(
            code=HTTPStatus.OK.value,
            message="Results extracted successfully",
            param={"results": all_results},
        ).model_dump(mode="json")

    except Exception as e:
        error_msg = f"Error extracting results for workflow_id: {workflow_id}, error: {e}"
        logger.error(error_msg)
        return ErrorResponse(
            message="Failed to extract results",
            code=HTTPStatus.INTERNAL_SERVER_ERROR.value,
        ).model_dump(mode="json")
```

---

## 3. Add Monitor Loop Activity (Dapr Monitor Pattern)

**File**: `budeval/evals/workflows.py`

Add this new activity after `extract_job_results`:

```python
@dapr_workflows.register_activity
@staticmethod
def monitor_jobs_loop(
    ctx: wf.WorkflowActivityContext,
    monitor_state: str,
) -> dict:
    """Monitor jobs using Dapr monitor pattern.

    This activity implements a single check iteration.
    The workflow will call this repeatedly with updated state.

    Args:
        monitor_state: JSON string with monitoring state

    Returns:
        Status and updated state
    """
    logger = logging.getLogger("::EVAL:: MonitorJobsLoop")

    state = json.loads(monitor_state)
    run_ids = state.get("run_ids", [])
    completed_jobs = state.get("completed_jobs", [])
    failed_jobs = state.get("failed_jobs", [])
    check_count = state.get("check_count", 0)
    max_checks = state.get("max_checks", 240)

    logger.info(f"Monitor check #{check_count}: tracking {len(run_ids)} jobs")

    # Check if we've exceeded max monitoring time
    if check_count >= max_checks:
        logger.warning(f"Max monitoring checks reached ({max_checks})")
        return ErrorResponse(
            code=HTTPStatus.REQUEST_TIMEOUT.value,
            message=f"Monitoring timeout: exceeded {max_checks} checks",
        ).model_dump(mode="json")

    # Get remaining jobs to monitor
    remaining_jobs = [
        job for job in run_ids
        if job not in completed_jobs and job not in failed_jobs
    ]

    if not remaining_jobs:
        logger.info("All jobs completed or failed")
        return SuccessResponse(
            code=HTTPStatus.OK.value,
            message="All jobs finished",
            param={
                "completed_jobs": completed_jobs,
                "failed_jobs": failed_jobs,
                "monitoring_complete": True,
            },
        ).model_dump(mode="json")

    # Check status of remaining jobs
    try:
        job_statuses = AnsibleOrchestrator().check_jobs_status(remaining_jobs)

        # Process each job status
        for job_id, status_info in job_statuses.items():
            job_status = status_info.get("status")

            if job_status == "Succeeded":
                if job_id not in completed_jobs:
                    completed_jobs.append(job_id)
                    logger.info(f"Job {job_id} completed successfully")

            elif job_status == "Failed":
                if job_id not in failed_jobs:
                    failed_jobs.append(job_id)
                    error_msg = status_info.get("message", "Unknown error")
                    logger.error(f"Job {job_id} failed: {error_msg}")

        # Update state
        state["completed_jobs"] = completed_jobs
        state["failed_jobs"] = failed_jobs
        state["check_count"] = check_count + 1

        # Return status indicating we need to continue monitoring
        return SuccessResponse(
            code=HTTPStatus.ACCEPTED.value,  # 202 = continue monitoring
            message=f"Monitoring in progress: {len(remaining_jobs)} jobs remaining",
            param={
                "completed_jobs": completed_jobs,
                "failed_jobs": failed_jobs,
                "remaining_jobs": remaining_jobs,
                "continue_monitoring": True,
                "updated_state": state,
            },
        ).model_dump(mode="json")

    except Exception as e:
        logger.error(f"Error checking job status: {e}", exc_info=True)
        return ErrorResponse(
            code=HTTPStatus.INTERNAL_SERVER_ERROR.value,
            message=f"Error checking job status: {str(e)}",
        ).model_dump(mode="json")
```

---

## 4. Implement Monitoring Loop in Main Workflow

**File**: `budeval/evals/workflows.py`

Replace the section after line 348 `# ====================  Start Monitoring For Each Job   ====================`:

```python
# ====================  Start Monitoring For Each Job   ====================

# Initialize monitoring state
monitoring_state = {
    "run_ids": run_ids,
    "eval_id": str(evaluate_model_request_json.eval_id),
    "completed_jobs": [],
    "failed_jobs": [],
    "check_count": 0,
    "max_checks": 240,  # 2 hours with 30-second intervals
}

# Monitoring loop using continue-as-new pattern
while True:
    # Check job status
    monitor_result = yield ctx.call_activity(
        EvaluationWorkflow.monitor_jobs_loop,
        input=json.dumps(monitoring_state),
    )

    result_code = monitor_result.get("code", HTTPStatus.OK.value)
    param = monitor_result.get("param", {})

    # Check if monitoring is complete
    if result_code == HTTPStatus.OK.value:
        # All jobs finished
        logger.info("All jobs completed")
        break

    elif result_code == HTTPStatus.ACCEPTED.value:
        # Continue monitoring - update state and sleep
        monitoring_state = param.get("updated_state", monitoring_state)

        # Notify progress every 10 checks (5 minutes)
        if monitoring_state["check_count"] % 10 == 0:
            notification_req.payload.event = "monitor_eval_job_progress"
            notification_req.payload.content = NotificationContent(
                title="Evaluation in progress",
                message=f"Jobs: {len(param.get('completed_jobs', []))} completed, {len(param.get('remaining_jobs', []))} running",
                status=WorkflowStatus.RUNNING,
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=evaluate_model_request_json.source_topic,
                target_name=evaluate_model_request_json.source,
            )

        # Sleep for 30 seconds before next check
        yield ctx.create_timer(fire_at=ctx.current_utc_datetime + timedelta(seconds=30))

    else:
        # Error or timeout
        logger.error(f"Monitoring failed: {monitor_result.get('message')}")

        notification_req.payload.event = "monitor_eval_job_progress"
        notification_req.payload.content = NotificationContent(
            title="Monitoring failed",
            message=monitor_result.get("message", "Unknown error"),
            status=WorkflowStatus.FAILED,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=evaluate_model_request_json.source_topic,
            target_name=evaluate_model_request_json.source,
        )
        return

# Extract results from completed jobs
completed_jobs = monitoring_state.get("completed_jobs", [])
if completed_jobs:
    logger.info(f"Extracting results from {len(completed_jobs)} completed jobs")

    extract_result = yield ctx.call_activity(
        EvaluationWorkflow.extract_job_results,
        input=json.dumps({
            "eval_id": str(evaluate_model_request_json.eval_id),
            "job_ids": completed_jobs,
        }),
    )

    logger.debug(f"Results extracted: {extract_result}")

    # Notify completion
    notification_req.payload.event = "evaluate_model_status"
    notification_req.payload.content = NotificationContent(
        title="Evaluation completed",
        message=f"Successfully completed {len(completed_jobs)} evaluations",
        status=WorkflowStatus.COMPLETED,
    )
    dapr_workflows.publish_notification(
        workflow_id=instance_id,
        notification=notification_req,
        target_topic_name=evaluate_model_request_json.source_topic,
        target_name=evaluate_model_request_json.source,
    )

# ====================  End Monitoring For Each Job   ====================
```

---

## 5. Add Job Status Check Method to AnsibleOrchestrator

**File**: `budeval/evals/ansible_orchestrator.py`

Add this method to the `AnsibleOrchestrator` class (after `verify_cluster_connection`):

```python
def check_jobs_status(self, job_ids: list[str], kubeconfig: Optional[str] = None) -> dict:
    """Check status of multiple Kubernetes jobs.

    Args:
        job_ids: List of job names to check
        kubeconfig: Optional kubeconfig JSON

    Returns:
        {
            "job1": {
                "status": "Running|Succeeded|Failed",
                "phase": "Pending|Running|Succeeded|Failed",
                "message": "Error message if failed",
                "completionTime": "2025-10-17T00:10:00Z"
            },
            "job2": {...}
        }
    """
    temp_id = f"check-status-{uuid.uuid4().hex}"
    playbook = "check_job_status_k8s.yml"

    files, extravars = self._parse_kubeconfig(kubeconfig, temp_id)

    # Build Extra Args
    namespace = StorageConfig.get_current_namespace()
    extravars["namespace"] = namespace
    extravars["job_names"] = ",".join(job_ids)  # Pass as comma-separated string

    # Run The Playbook
    try:
        self._run_ansible_playbook(playbook, temp_id, files, extravars)

        # Read results from temporary file created by playbook
        results_file = Path(tempfile.gettempdir()) / f"job_status_{temp_id}.json"

        if results_file.exists():
            with open(results_file, 'r') as f:
                job_statuses = json.load(f)
            results_file.unlink()  # Clean up

            logger.info(f"Retrieved status for {len(job_statuses)} jobs")
            return job_statuses
        else:
            logger.error("Job status results file not found")
            return {}

    except Exception as e:
        logger.error(f"Failed to check job status: {e}", exc_info=True)
        # Return empty dict on error - monitoring will retry
        return {}
```

---

## 6. Create Ansible Playbook for Job Status Checking

**File**: `budeval/ansible/playbooks/check_job_status_k8s.yml`

Create new playbook:

```yaml
---
- name: Check Kubernetes Job Status
  hosts: localhost
  connection: local
  gather_facts: false

  vars:
    kubeconfig_path: ""
    namespace: "default"
    job_names: ""  # Comma-separated job names

  tasks:
    - name: Ensure required variables are provided
      ansible.builtin.assert:
        that:
          - namespace is defined
          - namespace | length > 0
          - job_names is defined
          - job_names | length > 0
        fail_msg: "namespace and job_names must be provided"

    - name: Split job names into list
      ansible.builtin.set_fact:
        job_list: "{{ job_names.split(',') }}"

    - name: Initialize results dictionary
      ansible.builtin.set_fact:
        job_statuses: {}

    - name: Check each job status
      kubernetes.core.k8s_info:
        api_version: batch/v1
        kind: Job
        name: "{{ item }}"
        namespace: "{{ namespace }}"
        kubeconfig: "{{ kubeconfig_path if kubeconfig_path else omit }}"
      register: job_info
      loop: "{{ job_list }}"
      ignore_errors: true

    - name: Process job statuses
      ansible.builtin.set_fact:
        job_statuses: >-
          {{
            job_statuses | combine({
              item.item: {
                'status': 'Succeeded' if (item.resources[0].status.succeeded | default(0)) > 0
                         else 'Failed' if (item.resources[0].status.failed | default(0)) > 0
                         else 'Running' if (item.resources[0].status.active | default(0)) > 0
                         else 'Pending',
                'active': item.resources[0].status.active | default(0),
                'succeeded': item.resources[0].status.succeeded | default(0),
                'failed': item.resources[0].status.failed | default(0),
                'startTime': item.resources[0].status.startTime | default(''),
                'completionTime': item.resources[0].status.completionTime | default(''),
                'message': item.resources[0].status.conditions[0].message | default('') if item.resources[0].status.conditions is defined else ''
              }
            })
          }}
      loop: "{{ job_info.results }}"
      when: item.resources | length > 0

    - name: Write results to temporary file
      ansible.builtin.copy:
        content: "{{ job_statuses | to_nice_json }}"
        dest: "/tmp/job_status_{{ lookup('env', 'ANSIBLE_TEMP_ID') }}.json"
      vars:
        ansible_temp_id: "{{ kubeconfig_path | basename | regex_replace('_kubeconfig.yaml$', '') }}"
```

---

## 7. Add Required Import

**File**: `budeval/evals/workflows.py`

Add to imports at the top:

```python
from datetime import timedelta
```

---

## Testing Steps

1. **Start the service**:
```bash
dapr run --run-file ./app.yaml
```

2. **Submit an evaluation**:
```bash
curl -X POST http://localhost:8099/evals/start \
  -H "Content-Type: application/json" \
  -d '{
    "eval_id": "444e4567-e89b-12d3-a456-426614174020",
    "experiment_id": "123e4567-e89b-12d3-a456-426614174000",
    "eval_model_info": {
      "model_name": "gpt-oss-20b",
      "endpoint": "http://20.66.97.208/v1",
      "api_key": "sk-BudLiteLLMMasterKey_123",
      "extra_args": {
        "query_per_second": "50",
        "max_out_len": "2048",
        "max_seq_len": "4096"
      }
    },
    "eval_datasets": [
      {
        "dataset_id": "demo_gsm8k_chat_gen",
        "run_id": "test-monitor-pattern-001"
      }
    ],
    "eval_configs": [],
    "engine": "opencompass",
    "source": "budapp",
    "source_topic": "budapp-notifications"
  }'
```

3. **Monitor logs for**:
- "All jobs deployed, starting monitoring step"
- "Monitor check #0: tracking 1 jobs"
- "Monitoring in progress: 1 jobs remaining"
- "Job test-monitor-pattern-001 completed successfully"
- "All jobs completed"
- "Extracting results from 1 completed jobs"

4. **Verify job completion**:
```bash
kubectl get jobs -n development | grep test-monitor-pattern
```

---

## Key Features Implemented

✅ **Dapr Monitor Pattern**: Uses continue-as-new for long-running monitoring
✅ **Configurable Polling**: 30-second intervals, adjustable based on needs
✅ **Multiple Job Tracking**: Monitors all jobs simultaneously
✅ **Progress Notifications**: Updates every 5 minutes
✅ **Timeout Handling**: Maximum 2-hour monitoring period
✅ **Result Extraction**: Automatic extraction when jobs complete
✅ **Error Handling**: Graceful handling of failures and retries

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                 Dapr Workflow (evaluate_model)              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. verify_cluster_connection                               │
│  2. create_engine_config                                    │
│  3. deploy_eval_job_v2  ──────► [Jobs Created]             │
│                                                             │
│  4. MONITORING LOOP (while True):                           │
│     ┌─────────────────────────────────────────────┐        │
│     │ monitor_jobs_loop (activity)                │        │
│     │   ├─ Check job status (Ansible)             │        │
│     │   ├─ Update completed_jobs list             │        │
│     │   └─ Return: Continue (202) or Done (200)   │        │
│     └─────────────────────────────────────────────┘        │
│            │                                                │
│            ├─ If ACCEPTED (202): Sleep 30s, repeat         │
│            ├─ If OK (200): Break loop, extract results     │
│            └─ If ERROR: Notify failure, exit               │
│                                                             │
│  5. extract_job_results  ──────► [Results Stored]          │
│  6. Notify completion                                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Dapr Monitor Pattern Reference

From Dapr Documentation:

> The monitor pattern is recurring process that typically:
> 1. Checks the status of a system
> 2. Takes some action based on that status - e.g. send a notification
> 3. Sleeps for some period of time
> 4. Repeat

Our implementation follows this pattern with:
- **Check**: `monitor_jobs_loop` activity queries Kubernetes job status
- **Action**: Notifications sent on status changes, results extracted on completion
- **Sleep**: 30-second timer between checks (`ctx.create_timer`)
- **Repeat**: While loop continues until all jobs finish

---

## Configuration Options

### Adjust Polling Interval

In the monitoring loop section, change:
```python
yield ctx.create_timer(fire_at=ctx.current_utc_datetime + timedelta(seconds=30))
```

To faster polling (15 seconds):
```python
yield ctx.create_timer(fire_at=ctx.current_utc_datetime + timedelta(seconds=15))
```

### Adjust Max Monitoring Time

In the monitoring state initialization:
```python
"max_checks": 240,  # 2 hours with 30-second intervals
```

For 4 hours:
```python
"max_checks": 480,  # 4 hours with 30-second intervals
```

### Adjust Progress Notification Frequency

In the monitoring loop:
```python
if monitoring_state["check_count"] % 10 == 0:  # Every 10 checks (5 minutes)
```

For every minute:
```python
if monitoring_state["check_count"] % 2 == 0:  # Every 2 checks (1 minute)
```

---

## Troubleshooting

### Issue: Monitoring loop never exits
**Solution**: Check if `check_jobs_status` is returning correct status format. Verify Ansible playbook output.

### Issue: Notifications not received
**Solution**: Verify Redis pub/sub is working, check topic names match configuration.

### Issue: Result extraction fails
**Solution**: Verify PVC mount path, check result files exist in expected location.

### Issue: Jobs timeout
**Solution**: Increase `max_checks` or adjust polling interval. Check if jobs are actually running.

---

**Document Version**: 1.0
**Last Updated**: 2025-10-17
**Author**: Claude Code
**Status**: Ready for Implementation
