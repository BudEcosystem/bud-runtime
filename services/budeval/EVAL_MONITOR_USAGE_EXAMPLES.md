# Eval Monitor Usage Examples

## Overview
The integrated eval monitor can be used in two modes:
1. **Once Mode**: Check status once and emit single event
2. **Continuous Mode**: Monitor continuously with periodic updates

---

## Mode 1: Once - Single Status Check

### Use Cases
- Manual progress checks
- Testing event emission
- Scheduled snapshots (e.g., every 5 minutes from external cron)
- API endpoint to get current status

### Example 1: From Workflow Activity

```python
# File: budeval/evals/workflows.py

@dapr_workflows.register_activity
@staticmethod
def check_eval_progress_once(
    ctx: wf.WorkflowActivityContext,
    check_request: str,
) -> dict:
    """
    Activity to check evaluation progress once.

    Called periodically from workflow to emit progress snapshots.
    """
    logger = logging.getLogger("::EVAL:: CheckProgressOnce")

    try:
        config = json.loads(check_request)

        from budeval.evals.eval_monitor_integrated import check_status_once

        status = check_status_once(
            log_file=config.get("log_file"),
            results_dir=config.get("results_dir"),
            experiment_id=config.get("experiment_id"),
            evaluation_id=config.get("evaluation_id"),
            workflow_id=ctx.workflow_id,
            source_topic=config.get("source_topic"),
            source=config.get("source"),
            dataset_config=config.get("dataset_config"),
        )

        return {
            "success": True,
            "status": status,
        }

    except Exception as e:
        logger.error(f"Error checking progress: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
        }
```

### Example 2: Call from Workflow (Periodic Checks)

```python
# File: budeval/evals/workflows.py

# Inside evaluate_model workflow, after job deployment:

# Start periodic progress checks (every 5 minutes)
check_interval_minutes = 5
max_checks = 24  # 2 hours max

for i in range(max_checks):
    # Wait 5 minutes
    yield ctx.create_timer(
        fire_at=ctx.current_utc_datetime + timedelta(minutes=check_interval_minutes)
    )

    # Check progress once
    progress_check_input = {
        "log_file": "/path/to/nohup.out",
        "results_dir": "/path/to/results",
        "experiment_id": str(evaluate_model_request_json.experiment_id),
        "evaluation_id": str(evaluate_model_request_json.eval_id),
        "source_topic": evaluate_model_request_json.source_topic,
        "source": evaluate_model_request_json.source,
    }

    progress_result = yield ctx.call_activity(
        check_eval_progress_once,
        input=json.dumps(progress_check_input),
    )

    # Check if complete
    if progress_result.get("status", {}).get("evaluation_complete"):
        logger.info("Evaluation completed!")
        break
```

### Example 3: Direct Python Call (Testing)

```python
# File: test_eval_monitor.py

from budeval.evals.eval_monitor_integrated import check_status_once

# Test event emission
status = check_status_once(
    log_file="/workspace/eval-job-123/nohup.out",
    results_dir="/workspace/eval-job-123/results",
    experiment_id="550e8400-e29b-41d4-a716-446655440000",
    evaluation_id="660e8400-e29b-41d4-a716-446655440001",
    workflow_id="wf-123",
    source_topic="budapp-events",
    source="budapp",
)

print(f"Progress: {status['progress']:.1f}%")
print(f"Completed: {status['completed_tasks']}/{status['total_tasks']}")
print(f"ETA: {status['eta']}")

# Event has been emitted to Dapr!
```

### Example 4: API Endpoint

```python
# File: budeval/evals/routes.py

@router.post("/evaluations/{evaluation_id}/check-progress")
async def check_evaluation_progress(
    evaluation_id: UUID,
    request: CheckProgressRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Check evaluation progress once and emit event.

    Useful for manual progress checks or testing.
    """
    try:
        from budeval.evals.eval_monitor_integrated import check_status_once

        status = check_status_once(
            log_file=request.log_file,
            results_dir=request.results_dir,
            experiment_id=str(request.experiment_id),
            evaluation_id=str(evaluation_id),
            workflow_id=request.workflow_id,
            source_topic="budapp-events",
            source="budapp",
        )

        return {
            "success": True,
            "status": status,
            "message": f"Progress: {status['progress']:.1f}%"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

---

## Mode 2: Continuous - Monitor with Loop

### Use Cases
- Long-running monitoring during evaluation
- Real-time progress updates
- Automatic event emission every N seconds

### Example 1: From Workflow Activity

```python
# File: budeval/evals/workflows.py

@dapr_workflows.register_activity
@staticmethod
def monitor_eval_progress_continuous(
    ctx: wf.WorkflowActivityContext,
    monitor_request: str,
) -> dict:
    """
    Activity to continuously monitor evaluation progress.

    This runs until evaluation completes or max time reached.
    Emits events every 30 seconds.
    """
    logger = logging.getLogger("::EVAL:: MonitorContinuous")

    try:
        config = json.loads(monitor_request)

        from budeval.evals.eval_monitor_integrated import start_monitoring

        final_status = start_monitoring(
            log_file=config.get("log_file"),
            results_dir=config.get("results_dir"),
            experiment_id=config.get("experiment_id"),
            evaluation_id=config.get("evaluation_id"),
            workflow_id=ctx.workflow_id,
            source_topic=config.get("source_topic"),
            source=config.get("source"),
            interval=config.get("interval", 30),  # Check every 30 seconds
            max_iterations=config.get("max_iterations", 240),  # Max 2 hours
            dataset_config=config.get("dataset_config"),
        )

        return {
            "success": True,
            "final_status": final_status,
        }

    except Exception as e:
        logger.error(f"Error monitoring progress: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
        }
```

### Example 2: Call from Workflow (Parallel Monitoring)

```python
# File: budeval/evals/workflows.py

# Inside evaluate_model workflow, after job deployment:

# Start continuous monitoring in parallel with job execution
monitoring_config = {
    "log_file": "/path/to/nohup.out",
    "results_dir": "/path/to/results",
    "experiment_id": str(evaluate_model_request_json.experiment_id),
    "evaluation_id": str(evaluate_model_request_json.eval_id),
    "source_topic": evaluate_model_request_json.source_topic,
    "source": evaluate_model_request_json.source,
    "interval": 30,  # Emit event every 30 seconds
    "max_iterations": 240,  # 2 hours max (240 * 30s = 7200s)
}

# Run monitor as child workflow (parallel execution)
monitoring_result = yield ctx.call_child_workflow(
    workflow=monitor_progress_workflow_continuous,
    input=json.dumps(monitoring_config),
    instance_id=f"{instance_id}_progress_monitor",
)

logger.info(f"Monitoring completed: {monitoring_result}")
```

### Example 3: Direct Python Call

```python
# File: scripts/monitor_evaluation.py

from budeval.evals.eval_monitor_integrated import start_monitoring

# Monitor evaluation with continuous updates
final_status = start_monitoring(
    log_file="/workspace/eval-job-123/nohup.out",
    results_dir="/workspace/eval-job-123/results",
    experiment_id="550e8400-e29b-41d4-a716-446655440000",
    evaluation_id="660e8400-e29b-41d4-a716-446655440001",
    workflow_id="wf-123",
    source_topic="budapp-events",
    source="budapp",
    interval=30,  # Check every 30 seconds
)

print(f"Evaluation completed!")
print(f"Final progress: {final_status['progress']:.1f}%")
print(f"Total tasks: {final_status['total_tasks']}")
print(f"Completed: {final_status['completed_tasks']}")
```

### Example 4: Standalone Script

```python
#!/usr/bin/env python3
"""
Standalone script to monitor evaluation.

Usage:
    python monitor_eval.py \
        --log /path/to/nohup.out \
        --results /path/to/results \
        --experiment-id 550e8400-e29b-41d4-a716-446655440000 \
        --evaluation-id 660e8400-e29b-41d4-a716-446655440001 \
        --interval 30
"""

import argparse
from budeval.evals.eval_monitor_integrated import start_monitoring

def main():
    parser = argparse.ArgumentParser(description='Monitor evaluation progress')
    parser.add_argument('--log', required=True, help='Path to log file')
    parser.add_argument('--results', required=True, help='Path to results directory')
    parser.add_argument('--experiment-id', required=True, help='Experiment UUID')
    parser.add_argument('--evaluation-id', required=True, help='Evaluation UUID')
    parser.add_argument('--workflow-id', required=True, help='Workflow UUID')
    parser.add_argument('--interval', type=int, default=30, help='Check interval in seconds')
    parser.add_argument('--max-iterations', type=int, default=None, help='Max iterations')

    args = parser.parse_args()

    final_status = start_monitoring(
        log_file=args.log,
        results_dir=args.results,
        experiment_id=args.experiment_id,
        evaluation_id=args.evaluation_id,
        workflow_id=args.workflow_id,
        source_topic="budapp-events",
        source="budapp",
        interval=args.interval,
        max_iterations=args.max_iterations,
    )

    print(f"\n✅ Monitoring completed!")
    print(f"Final progress: {final_status['progress']:.1f}%")

if __name__ == "__main__":
    main()
```

---

## Comparison: Once vs Continuous

| Feature | Once Mode | Continuous Mode |
|---------|-----------|-----------------|
| **Function** | `check_status_once()` | `start_monitoring()` |
| **Checks** | Single check | Loop until complete |
| **Events Emitted** | 1 event | Multiple (every interval) |
| **Use Case** | Manual/scheduled checks | Real-time monitoring |
| **Blocking** | No (returns immediately) | Yes (runs until done) |
| **Best For** | Testing, snapshots | Production monitoring |

---

## Recommended Usage Pattern

### For Production Workflow

**Option A: Continuous Monitoring (Recommended)**
```python
# Start continuous monitor as child workflow
# Runs in parallel with job execution
# Emits progress every 30 seconds automatically

monitoring_result = yield ctx.call_child_workflow(
    workflow=monitor_progress_workflow_continuous,
    input=json.dumps(config),
    instance_id=f"{instance_id}_monitor",
)
```

**Option B: Periodic Snapshots**
```python
# Check progress every 5 minutes
# Less frequent updates, lighter load

for i in range(24):  # 2 hours max
    yield ctx.create_timer(fire_at=ctx.current_utc_datetime + timedelta(minutes=5))
    progress = yield ctx.call_activity(check_eval_progress_once, input=json.dumps(config))
    if progress.get("status", {}).get("evaluation_complete"):
        break
```

### For Testing

```python
# Quick test: check once and verify event emission
from budeval.evals.eval_monitor_integrated import check_status_once

status = check_status_once(
    log_file="/path/to/nohup.out",
    results_dir="/path/to/results",
    experiment_id="test-exp",
    evaluation_id="test-eval",
    workflow_id="test-wf",
    source_topic="budapp-events",
    source="budapp",
)

assert status['progress'] >= 0
assert status['total_tasks'] > 0
print("✅ Event emitted successfully!")
```

---

## Event Flow Diagram

### Once Mode
```
User/Workflow calls check_status_once()
    ↓
Monitor reads logs once
    ↓
Calculates progress
    ↓
Emits 1 event (STARTED/PROGRESS/COMPLETED)
    ↓
Returns status dict
    ↓
Done (immediate return)
```

### Continuous Mode
```
User/Workflow calls start_monitoring()
    ↓
Monitor starts loop
    ↓
┌─────────────────────┐
│ Read logs           │
│ Calculate progress  │
│ Emit event          │
│ Wait 30 seconds     │ ← Loop repeats
└─────────────────────┘
    ↓
Evaluation completes
    ↓
Emit COMPLETED event
    ↓
Return final status
```

---

## Summary

### Once Mode (`check_status_once`)
- ✅ Single status check
- ✅ One event emission
- ✅ Returns immediately
- ✅ Great for testing
- ✅ Manual progress checks
- ✅ Scheduled snapshots

### Continuous Mode (`start_monitoring`)
- ✅ Loop until completion
- ✅ Events every N seconds
- ✅ Real-time monitoring
- ✅ Automatic progress tracking
- ✅ Production-ready
- ✅ Parallel execution support

**Recommendation**: Use **Continuous Mode** in production workflows for automatic real-time updates. Use **Once Mode** for testing, debugging, or manual progress checks.

---

**Date**: 2025-01-13
**Implementation**: Complete ✅
