# Eval Monitor Quick Start

## TL;DR - Two Ways to Use

### 1. Check Once (Single Event)
```python
from budeval.evals.eval_monitor_integrated import check_status_once

status = check_status_once(
    log_file="/path/to/nohup.out",
    results_dir="/path/to/results",
    experiment_id="exp-uuid",
    evaluation_id="eval-uuid",
    workflow_id="wf-uuid",
    source_topic="budapp-events",
    source="budapp",
)
# Returns: {"progress": 50.0, "completed_tasks": 5, ...}
# Emits: 1 event to Dapr
```

### 2. Continuous Monitoring (Multiple Events)
```python
from budeval.evals.eval_monitor_integrated import start_monitoring

final_status = start_monitoring(
    log_file="/path/to/nohup.out",
    results_dir="/path/to/results",
    experiment_id="exp-uuid",
    evaluation_id="eval-uuid",
    workflow_id="wf-uuid",
    source_topic="budapp-events",
    source="budapp",
    interval=30,  # Check every 30 seconds
)
# Returns: Final status when evaluation completes
# Emits: Events every 30 seconds until done
```

---

## Initialization Parameters

Both functions use the same parameters:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `log_file` | str | ✅ | Path to evaluation log file (e.g., `nohup.out`) |
| `results_dir` | str | ✅ | Path to results directory |
| `experiment_id` | str | ✅ | UUID of experiment |
| `evaluation_id` | str | ✅ | UUID of evaluation |
| `workflow_id` | str | ✅ | Dapr workflow instance ID |
| `source_topic` | str | ✅ | Dapr topic name (e.g., `"budapp-events"`) |
| `source` | str | ✅ | Source service name (e.g., `"budapp"`) |
| `interval` | int | ❌ | *Continuous only:* Check interval in seconds (default: 30) |
| `max_iterations` | int | ❌ | *Continuous only:* Max checks before stopping (default: None) |
| `dataset_config` | str | ❌ | Dataset name for task estimation (default: None) |

---

## Events Emitted

### Event 1: eval.started
```json
{
  "event": "eval.started",
  "content": {
    "title": "Evaluation Started",
    "message": "Starting evaluation with 10 tasks",
    "status": "STARTED",
    "metadata": {
      "experiment_id": "uuid",
      "evaluation_id": "uuid",
      "total_tasks": 10,
      "estimated_time_seconds": 600,
      "timestamp": "2025-01-13T10:00:00+00:00"
    }
  }
}
```

### Event 2: eval.progress (every N seconds)
```json
{
  "event": "eval.progress",
  "content": {
    "title": "Evaluation Progress",
    "message": "Completed 5/10 tasks (50.0%)",
    "status": "RUNNING",
    "metadata": {
      "experiment_id": "uuid",
      "evaluation_id": "uuid",
      "total_tasks": 10,
      "completed_tasks": 5,
      "failed_tasks": 0,
      "in_progress_tasks": 5,
      "progress_percentage": 50.0,
      "time_elapsed_seconds": 300,
      "time_remaining_seconds": 300,
      "current_task": "mmlu_gen_0",
      "timestamp": "2025-01-13T10:05:00+00:00"
    }
  }
}
```

### Event 3: eval.completed
```json
{
  "event": "eval.completed",
  "content": {
    "title": "Evaluation Completed",
    "message": "Completed 10/10 tasks",
    "status": "COMPLETED",
    "metadata": {
      "experiment_id": "uuid",
      "evaluation_id": "uuid",
      "total_tasks": 10,
      "completed_tasks": 10,
      "failed_tasks": 0,
      "total_time_seconds": 600,
      "success_rate": 100.0,
      "timestamp": "2025-01-13T10:10:00+00:00"
    }
  }
}
```

---

## Common Usage Patterns

### Pattern 1: From Dapr Workflow Activity
```python
@dapr_workflows.register_activity
def check_progress_activity(ctx: wf.WorkflowActivityContext, config: str):
    from budeval.evals.eval_monitor_integrated import check_status_once

    params = json.loads(config)
    return check_status_once(**params)
```

### Pattern 2: Continuous Monitoring in Workflow
```python
# Call as child workflow
monitoring_result = yield ctx.call_child_workflow(
    workflow=monitor_progress_workflow,
    input=json.dumps({
        "log_file": "/path/to/log",
        "results_dir": "/path/to/results",
        "experiment_id": "exp-123",
        "evaluation_id": "eval-456",
        "workflow_id": ctx.instance_id,
        "source_topic": "budapp-events",
        "source": "budapp",
        "interval": 30,
    }),
    instance_id=f"{ctx.instance_id}_monitor",
)
```

### Pattern 3: Direct API Call
```python
@router.post("/evaluations/{eval_id}/progress")
async def get_progress(eval_id: UUID, request: ProgressRequest):
    from budeval.evals.eval_monitor_integrated import check_status_once

    status = check_status_once(
        log_file=request.log_file,
        results_dir=request.results_dir,
        experiment_id=str(request.experiment_id),
        evaluation_id=str(eval_id),
        workflow_id=request.workflow_id,
        source_topic="budapp-events",
        source="budapp",
    )

    return {"status": status}
```

---

## Testing

### Test Event Emission
```python
# Test that events are emitted correctly
from budeval.evals.eval_monitor_integrated import check_status_once

status = check_status_once(
    log_file="/workspace/test-eval/nohup.out",
    results_dir="/workspace/test-eval/results",
    experiment_id="test-exp-123",
    evaluation_id="test-eval-456",
    workflow_id="test-wf-789",
    source_topic="budapp-events",
    source="budapp",
)

print(f"✅ Event emitted!")
print(f"Progress: {status['progress']:.1f}%")
print(f"Status: {status}")
```

### Subscribe to Events (Terminal)
```bash
# In one terminal, subscribe to see events
dapr subscribe --app-id budapp --topic budapp-events

# In another terminal, run the test above
# You'll see the events in the first terminal
```

---

## Troubleshooting

### Issue: No events received
**Check:**
1. Dapr is running: `dapr list`
2. Pub/sub component exists: `dapr components list`
3. Topic name is correct: `budapp-events`
4. Log file path is correct and accessible

### Issue: Events emitted but budapp not receiving
**Check:**
1. BudApp has Dapr subscription configured
2. Route exists: `/api/v1/experiments/dapr/subscribe/eval-progress`
3. Handler function exists: `handle_eval_progress_notification()`
4. Database table exists: `eval_progress_snapshots`

### Issue: Progress shows 0%
**Check:**
1. Log file contains evaluation logs
2. Results directory has prediction files
3. Log file format matches expected pattern
4. File paths are absolute (not relative)

---

## Quick Decision Tree

**Q: Do you need real-time updates throughout the evaluation?**
- Yes → Use `start_monitoring()` (continuous mode)
- No → Continue below

**Q: Do you need a single progress snapshot?**
- Yes → Use `check_status_once()` (once mode)
- No → You probably don't need the monitor

**Q: Are you testing event emission?**
- Yes → Use `check_status_once()` (faster)

**Q: Are you integrating into production workflow?**
- Yes → Use `start_monitoring()` (more robust)

---

## Minimal Working Example

```python
#!/usr/bin/env python3
"""Minimal example of using the integrated eval monitor."""

from budeval.evals.eval_monitor_integrated import check_status_once

# Replace with actual paths
LOG_FILE = "/path/to/your/evaluation/nohup.out"
RESULTS_DIR = "/path/to/your/evaluation/results"

# Replace with actual UUIDs
EXPERIMENT_ID = "550e8400-e29b-41d4-a716-446655440000"
EVALUATION_ID = "660e8400-e29b-41d4-a716-446655440001"
WORKFLOW_ID = "770e8400-e29b-41d4-a716-446655440002"

def main():
    print("Checking evaluation progress...")

    status = check_status_once(
        log_file=LOG_FILE,
        results_dir=RESULTS_DIR,
        experiment_id=EXPERIMENT_ID,
        evaluation_id=EVALUATION_ID,
        workflow_id=WORKFLOW_ID,
        source_topic="budapp-events",
        source="budapp",
    )

    print(f"\n✅ Status Check Complete!")
    print(f"Progress: {status['progress']:.1f}%")
    print(f"Completed: {status['completed_tasks']}/{status['total_tasks']}")
    print(f"ETA: {status['eta']}")
    print(f"\n📡 Event emitted to Dapr topic: budapp-events")

if __name__ == "__main__":
    main()
```

---

**Ready to use!** Choose `check_status_once()` for single checks or `start_monitoring()` for continuous monitoring.
