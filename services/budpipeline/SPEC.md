# budpipeline Service Specification

## 1. Service Overview

### Purpose
`budpipeline` is a dedicated workflow orchestration service for the bud-stack platform. It handles job scheduling, DAG-based workflow execution, and coordination of actions across multiple services.

### Scope
- **In Scope**: Job scheduling, workflow execution, step orchestration, status monitoring, log aggregation
- **Out of Scope**: Job/workflow definitions (budapp), K8s operations (budcluster), credentials storage (budapp)

### Key Responsibilities
1. **Scheduling**: Trigger jobs based on cron, interval, one-time, or webhook triggers
2. **Orchestration**: Execute multi-step DAG workflows with dependencies
3. **Execution**: Dispatch actions to appropriate services (internal or external)
4. **Monitoring**: Track execution status, aggregate logs, handle failures
5. **State Management**: Maintain workflow state using Dapr workflow actors

---

## 2. Architecture

### High-Level Design

```
                                    ┌─────────────────────┐
                                    │      budapp         │
                                    │  (definitions/API)  │
                                    └──────────┬──────────┘
                                               │
                         ┌─────────────────────┼─────────────────────┐
                         │                     │                     │
                         ▼                     ▼                     ▼
              ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
              │   Trigger Job    │  │  Get Status      │  │  Stream Logs     │
              │   POST /execute  │  │  GET /status     │  │  WS /logs        │
              └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘
                       │                     │                     │
                       ▼                     ▼                     ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                              budpipeline                                      │
│                                                                              │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐                 │
│  │   Scheduler    │  │   DAG Engine   │  │    Monitor     │                 │
│  │                │  │                │  │                │                 │
│  │ • Dapr Jobs    │  │ • Parse DAG    │  │ • Status Poll  │                 │
│  │ • Cron Parse   │  │ • Resolve Deps │  │ • Log Stream   │                 │
│  │ • Trigger Mgmt │  │ • Step Exec    │  │ • K8s Watch    │                 │
│  └───────┬────────┘  └───────┬────────┘  └───────┬────────┘                 │
│          │                   │                   │                          │
│          └───────────────────┼───────────────────┘                          │
│                              ▼                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                    Dapr Pipeline Runtime                              │  │
│  │                                                                       │  │
│  │  PipelineActor ──► Activity: InternalAction                          │  │
│  │       │        ──► Activity: K8sJob                                  │  │
│  │       │        ──► Activity: HelmDeploy                              │  │
│  │       │        ──► Activity: GitDeploy                               │  │
│  │       ▼                                                              │  │
│  │  State Store (Redis) - Durable execution state                       │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                              │                                              │
└──────────────────────────────┼──────────────────────────────────────────────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         │                     │                     │
         ▼                     ▼                     ▼
  ┌─────────────┐       ┌─────────────┐       ┌─────────────┐
  │ budcluster  │       │  budmodel   │       │   budsim    │
  │             │       │             │       │             │
  │ • K8s Jobs  │       │ • Onboard   │       │ • Simulate  │
  │ • Helm      │       │ • Register  │       │ • Optimize  │
  │ • Scale     │       │             │       │             │
  └─────────────┘       └─────────────┘       └─────────────┘
```

### Technology Stack
- **Language**: Python 3.10+
- **Framework**: FastAPI + budmicroframe
- **Pipeline Engine**: Dapr Pipelines (Python SDK)
- **State Store**: Redis (via Dapr)
- **Message Queue**: Dapr Pub/Sub (for events)
- **Scheduling**: Dapr Jobs API

---

## 3. Core Features

### 3.1 Job Scheduler

#### Trigger Types
| Type | Description | Example |
|------|-------------|---------|
| `cron` | Cron expression schedule | `0 9 * * 1-5` (9 AM weekdays) |
| `interval` | Fixed interval | `@every 30m`, `@every 1h` |
| `one_time` | Single execution at time | `2025-01-15T10:00:00Z` |
| `manual` | No auto-trigger, API only | User clicks "Run Now" |
| `webhook` | HTTP trigger with payload | External system callback |
| `event` | Dapr pub/sub event | Model onboarded event |

#### Scheduler Features
- Register/unregister jobs with Dapr Jobs API
- Parse and validate cron expressions
- Handle timezone conversions
- Manage job lifecycle (pause, resume, delete)
- Track next run time
- Support for job dependencies (run job B after job A)

### 3.2 DAG Pipeline Engine

#### DAG Definition Schema
```yaml
name: "model-deployment-pipeline"
version: "1.0"
description: "End-to-end model deployment workflow"

# Pipeline-level parameters
parameters:
  - name: model_uri
    type: string
    required: true
  - name: cluster_id
    type: cluster_ref
    required: true
  - name: replicas
    type: integer
    default: 1

# Execution settings
settings:
  timeout_seconds: 7200
  fail_fast: true
  max_parallel_steps: 5
  retry_policy:
    max_attempts: 3
    backoff_seconds: 60

# DAG steps
steps:
  - id: onboard
    name: "Onboard Model"
    action: internal.model.onboard
    params:
      model_uri: "{{ params.model_uri }}"
      source_type: huggingface
    outputs:
      - model_id

  - id: simulate
    name: "Run Simulation"
    action: internal.budsim.simulate
    depends_on: [onboard]
    params:
      model_id: "{{ steps.onboard.outputs.model_id }}"
      cluster_id: "{{ params.cluster_id }}"
    outputs:
      - recommended_config
    on_failure: continue  # Don't fail workflow if simulation fails

  - id: deploy
    name: "Deploy Model"
    action: internal.deployment.deploy
    depends_on: [onboard]  # Can run without simulation
    condition: "{{ steps.onboard.status == 'completed' }}"
    params:
      model_id: "{{ steps.onboard.outputs.model_id }}"
      cluster_id: "{{ params.cluster_id }}"
      replicas: "{{ params.replicas }}"
      config: "{{ steps.simulate.outputs.recommended_config | default({}) }}"
    outputs:
      - endpoint_id
      - endpoint_url
    retry:
      max_attempts: 2
      backoff_seconds: 30

  - id: notify
    name: "Send Notification"
    action: internal.notify.send
    depends_on: [deploy]
    params:
      template: deployment_complete
      data:
        endpoint_url: "{{ steps.deploy.outputs.endpoint_url }}"
    on_failure: continue

# Pipeline outputs
outputs:
  endpoint_url: "{{ steps.deploy.outputs.endpoint_url }}"
  model_id: "{{ steps.onboard.outputs.model_id }}"
```

#### DAG Engine Features
| Feature | Description |
|---------|-------------|
| **Dependency Resolution** | Topological sort, parallel execution of independent steps |
| **Parameter Templating** | Jinja2-style templates for dynamic params |
| **Output Mapping** | Pass outputs from one step to next |
| **Conditional Execution** | Skip steps based on conditions |
| **Failure Handling** | `fail`, `continue`, `retry` per step |
| **Timeout Management** | Per-step and workflow-level timeouts |
| **Fan-out/Fan-in** | `for_each` for parallel iterations |

### 3.3 Action Handlers

#### Action Categories
```
┌─────────────────────────────────────────────────────────────┐
│                      Action Types                            │
├─────────────────────────────────────────────────────────────┤
│  INTERNAL ACTIONS (Dapr Service Invocation)                 │
│  ├── internal.model.onboard      → budmodel                 │
│  ├── internal.model.deploy       → budcluster               │
│  ├── internal.deployment.scale   → budcluster               │
│  ├── internal.deployment.delete  → budcluster               │
│  ├── internal.budsim.simulate    → budsim                   │
│  ├── internal.notify.send        → budnotify                │
│  └── internal.metrics.query      → budmetrics               │
├─────────────────────────────────────────────────────────────┤
│  EXTERNAL ACTIONS (K8s Operations via budcluster)           │
│  ├── external.k8s.job            → Run K8s Job              │
│  ├── external.k8s.cronjob        → Create K8s CronJob       │
│  ├── external.helm.install       → Helm install/upgrade     │
│  ├── external.helm.uninstall     → Helm uninstall           │
│  └── external.git.run            → Clone repo & run         │
├─────────────────────────────────────────────────────────────┤
│  UTILITY ACTIONS (Built-in)                                 │
│  ├── util.wait                   → Wait for duration        │
│  ├── util.http                   → HTTP request             │
│  ├── util.condition              → Evaluate condition       │
│  └── util.transform              → Transform data           │
└─────────────────────────────────────────────────────────────┘
```

#### Handler Interface
```python
class ActionHandler(ABC):
    """Base class for action handlers."""

    @property
    @abstractmethod
    def action_type(self) -> str:
        """Return the action type ID (e.g., 'internal.model.deploy')."""
        pass

    @abstractmethod
    async def validate(self, params: Dict[str, Any]) -> List[str]:
        """Validate parameters. Return list of errors."""
        pass

    @abstractmethod
    async def execute(
        self,
        execution_id: UUID,
        params: Dict[str, Any],
        context: ExecutionContext
    ) -> ActionResult:
        """Execute the action and return result."""
        pass

    @abstractmethod
    async def get_status(self, execution_id: UUID) -> ActionStatus:
        """Get current status of action execution."""
        pass

    async def cancel(self, execution_id: UUID) -> bool:
        """Cancel a running action. Return True if successful."""
        return False  # Default: not cancellable
```

### 3.4 Execution Monitor

#### Monitoring Capabilities
| Capability | Description |
|------------|-------------|
| **Status Tracking** | Real-time status for workflow and steps |
| **Log Aggregation** | Collect logs from all steps, K8s pods |
| **Progress Reporting** | Percentage complete, ETA |
| **Event Streaming** | WebSocket for live updates |
| **K8s Job Watching** | Poll/watch K8s job status |
| **Metrics Collection** | Duration, success rate, resource usage |

#### Execution States
```
                    ┌──────────┐
                    │ PENDING  │
                    └────┬─────┘
                         │
                    ┌────▼─────┐
              ┌─────│ RUNNING  │─────┐
              │     └────┬─────┘     │
              │          │           │
         ┌────▼────┐ ┌───▼────┐ ┌────▼─────┐
         │COMPLETED│ │ FAILED │ │CANCELLED │
         └─────────┘ └───┬────┘ └──────────┘
                         │
                    ┌────▼────┐
                    │RETRYING │
                    └────┬────┘
                         │
                    (back to RUNNING)
```

### 3.5 State Management

#### State Types
| State | Storage | Purpose |
|-------|---------|---------|
| **Pipeline State** | Dapr State Store (Redis) | Durable execution state |
| **Step State** | Dapr State Store | Per-step status, outputs |
| **Schedule State** | Dapr Jobs API | Next run, job metadata |
| **Execution History** | budapp PostgreSQL | Long-term history, queries |
| **Logs** | budmetrics ClickHouse | Time-series log storage |

---

## 4. API Design

### 4.1 Execution APIs

```yaml
# Trigger a job/workflow execution
POST /api/v1/execute
Request:
  job_id: UUID           # Scheduled job ID (from budapp)
  workflow_id: UUID      # Or workflow ID (from budapp)
  params: object         # Override parameters
  triggered_by: UUID     # User ID
  trigger_type: string   # 'manual', 'scheduled', 'webhook', 'event'
Response:
  execution_id: UUID
  status: string
  started_at: timestamp

# Get execution status
GET /api/v1/executions/{execution_id}
Response:
  execution_id: UUID
  job_id: UUID
  workflow_id: UUID
  status: string         # pending, running, completed, failed, cancelled
  started_at: timestamp
  completed_at: timestamp
  duration_ms: integer
  progress: object       # { completed: 3, total: 5, percentage: 60 }
  current_step: string   # Current step ID
  steps: array           # Step statuses
  result: object         # Final outputs
  error: object          # Error details if failed

# Get execution logs
GET /api/v1/executions/{execution_id}/logs
Query:
  step_id: string        # Filter by step
  level: string          # Filter by log level
  since: timestamp       # Logs after this time
  tail: integer          # Last N lines
Response:
  logs: array
    - timestamp: timestamp
      level: string
      step_id: string
      message: string
      metadata: object

# Stream execution logs (WebSocket)
WS /api/v1/executions/{execution_id}/logs/stream
Messages:
  - type: log
    data: { timestamp, level, step_id, message }
  - type: status
    data: { step_id, status, progress }
  - type: complete
    data: { status, result }

# Cancel execution
POST /api/v1/executions/{execution_id}/cancel
Response:
  status: string         # 'cancelling' or 'cancelled'

# Retry failed execution
POST /api/v1/executions/{execution_id}/retry
Request:
  from_step: string      # Optional: retry from specific step
Response:
  execution_id: UUID     # New execution ID
  status: string
```

### 4.2 Scheduler APIs

```yaml
# Register a scheduled job
POST /api/v1/scheduler/jobs
Request:
  job_id: UUID           # Job ID from budapp
  name: string
  schedule:
    type: string         # cron, interval, one_time
    expression: string   # Cron expression or interval
    timezone: string     # e.g., 'America/New_York'
  callback:
    type: string         # 'workflow' or 'action'
    workflow_id: UUID
    action_type: string
    params: object
Response:
  schedule_id: string
  next_run_at: timestamp

# Update schedule
PUT /api/v1/scheduler/jobs/{job_id}
Request:
  schedule: object
  enabled: boolean
Response:
  next_run_at: timestamp

# Delete schedule
DELETE /api/v1/scheduler/jobs/{job_id}

# Pause schedule
POST /api/v1/scheduler/jobs/{job_id}/pause

# Resume schedule
POST /api/v1/scheduler/jobs/{job_id}/resume

# Get schedule status
GET /api/v1/scheduler/jobs/{job_id}
Response:
  job_id: UUID
  schedule: object
  enabled: boolean
  next_run_at: timestamp
  last_run_at: timestamp
  run_count: integer
```

### 4.3 Webhook APIs

```yaml
# Webhook trigger endpoint
POST /api/v1/webhooks/{webhook_id}/trigger
Headers:
  X-Webhook-Secret: string
Request:
  payload: object        # Passed to workflow as params
Response:
  execution_id: UUID
  status: string

# Validate webhook configuration
POST /api/v1/webhooks/validate
Request:
  webhook_id: string
  secret: string
Response:
  valid: boolean
  job_id: UUID
```

### 4.4 Health & Metrics APIs

```yaml
# Service health
GET /api/v1/health
Response:
  status: string
  dapr_connected: boolean
  active_workflows: integer
  scheduler_status: string

# Execution metrics
GET /api/v1/metrics
Response:
  executions:
    total: integer
    running: integer
    completed_24h: integer
    failed_24h: integer
  workflows:
    avg_duration_ms: integer
    success_rate: float
  scheduler:
    active_jobs: integer
    next_run_in_seconds: integer
```

---

## 5. Dapr Pipeline Design

### 5.1 Pipeline Definition

```python
# budpipeline/workflows/dag_workflow.py

from dapr.ext.workflow import (
    DaprPipelineContext,
    PipelineActivityContext,
    when_all,
    when_any,
)
from typing import Any, Dict, List
import json

from ..engine.dag_parser import DAGParser
from ..engine.param_resolver import ParamResolver
from ..handlers import get_handler


async def dag_workflow(ctx: DaprPipelineContext, input: Dict[str, Any]):
    """
    Main DAG workflow that orchestrates step execution.

    Input:
        execution_id: UUID
        workflow_definition: Dict (DAG YAML as dict)
        params: Dict (workflow parameters)
        project_id: UUID
        triggered_by: UUID
    """
    execution_id = input["execution_id"]
    dag = DAGParser.parse(input["workflow_definition"])
    params = input["params"]

    # Initialize step outputs storage
    step_outputs: Dict[str, Any] = {}
    step_statuses: Dict[str, str] = {}

    # Get execution order (topologically sorted)
    execution_order = dag.get_execution_order()

    # Track running steps for parallel execution
    running_tasks = {}

    for batch in execution_order:
        # Each batch contains steps that can run in parallel
        batch_tasks = []

        for step in batch:
            # Check if dependencies are met
            if not _dependencies_met(step, step_statuses, dag.settings.fail_fast):
                step_statuses[step.id] = "skipped"
                continue

            # Evaluate condition if present
            if step.condition:
                condition_met = yield ctx.call_activity(
                    evaluate_condition,
                    input={
                        "condition": step.condition,
                        "step_outputs": step_outputs,
                        "params": params,
                    }
                )
                if not condition_met:
                    step_statuses[step.id] = "skipped"
                    continue

            # Resolve parameters (template substitution)
            resolved_params = ParamResolver.resolve(
                step.params,
                workflow_params=params,
                step_outputs=step_outputs,
            )

            # Create activity task
            task = ctx.call_activity(
                execute_step,
                input={
                    "execution_id": execution_id,
                    "step_id": step.id,
                    "step_name": step.name,
                    "action_type": step.action,
                    "params": resolved_params,
                    "retry_policy": step.retry,
                    "timeout_seconds": step.timeout_seconds,
                }
            )
            batch_tasks.append((step.id, task))

        # Wait for all tasks in batch to complete
        if batch_tasks:
            results = yield when_all([t[1] for t in batch_tasks])

            # Process results
            for i, (step_id, _) in enumerate(batch_tasks):
                result = results[i]
                step_statuses[step_id] = result["status"]

                if result["status"] == "completed":
                    step_outputs[step_id] = result["outputs"]
                elif result["status"] == "failed":
                    if dag.settings.fail_fast:
                        # Record failure and exit
                        yield ctx.call_activity(
                            update_execution_status,
                            input={
                                "execution_id": execution_id,
                                "status": "failed",
                                "error": result["error"],
                            }
                        )
                        return {
                            "status": "failed",
                            "failed_step": step_id,
                            "error": result["error"],
                            "step_outputs": step_outputs,
                        }

    # Resolve final outputs
    final_outputs = ParamResolver.resolve(
        dag.outputs,
        workflow_params=params,
        step_outputs=step_outputs,
    )

    # Update final status
    yield ctx.call_activity(
        update_execution_status,
        input={
            "execution_id": execution_id,
            "status": "completed",
            "outputs": final_outputs,
        }
    )

    return {
        "status": "completed",
        "outputs": final_outputs,
        "step_statuses": step_statuses,
    }


def _dependencies_met(step, statuses: Dict[str, str], fail_fast: bool) -> bool:
    """Check if all dependencies are satisfied."""
    for dep_id in step.depends_on:
        dep_status = statuses.get(dep_id)
        if dep_status is None:
            return False  # Dependency not yet executed
        if dep_status == "failed" and fail_fast:
            return False
        if dep_status not in ("completed", "skipped"):
            return False
    return True
```

### 5.2 Activities

```python
# budpipeline/workflows/activities.py

from dapr.ext.workflow import PipelineActivityContext
from typing import Any, Dict
import asyncio

from ..handlers import get_handler, ActionResult
from ..monitor.status_tracker import StatusTracker


async def execute_step(ctx: PipelineActivityContext, input: Dict[str, Any]) -> Dict:
    """
    Execute a single workflow step.

    This is a Dapr activity that handles:
    - Action dispatch to appropriate handler
    - Retry logic
    - Timeout enforcement
    - Status updates
    """
    execution_id = input["execution_id"]
    step_id = input["step_id"]
    action_type = input["action_type"]
    params = input["params"]
    retry_policy = input.get("retry_policy", {})
    timeout_seconds = input.get("timeout_seconds", 300)

    tracker = StatusTracker()
    handler = get_handler(action_type)

    # Update status to running
    await tracker.update_step_status(
        execution_id=execution_id,
        step_id=step_id,
        status="running",
    )

    max_attempts = retry_policy.get("max_attempts", 1)
    backoff_seconds = retry_policy.get("backoff_seconds", 60)

    last_error = None

    for attempt in range(max_attempts):
        try:
            # Execute with timeout
            result = await asyncio.wait_for(
                handler.execute(
                    execution_id=execution_id,
                    step_id=step_id,
                    params=params,
                ),
                timeout=timeout_seconds,
            )

            if result.success:
                await tracker.update_step_status(
                    execution_id=execution_id,
                    step_id=step_id,
                    status="completed",
                    outputs=result.outputs,
                )
                return {
                    "status": "completed",
                    "outputs": result.outputs,
                }
            else:
                last_error = result.error

        except asyncio.TimeoutError:
            last_error = {"message": f"Step timed out after {timeout_seconds}s"}
        except Exception as e:
            last_error = {"message": str(e), "type": type(e).__name__}

        # Retry logic
        if attempt < max_attempts - 1:
            await tracker.update_step_status(
                execution_id=execution_id,
                step_id=step_id,
                status="retrying",
                attempt=attempt + 1,
            )
            await asyncio.sleep(backoff_seconds * (2 ** attempt))

    # All attempts failed
    await tracker.update_step_status(
        execution_id=execution_id,
        step_id=step_id,
        status="failed",
        error=last_error,
    )

    return {
        "status": "failed",
        "error": last_error,
    }


async def evaluate_condition(
    ctx: PipelineActivityContext,
    input: Dict[str, Any]
) -> bool:
    """Evaluate a step condition."""
    from ..engine.condition_evaluator import ConditionEvaluator

    return ConditionEvaluator.evaluate(
        condition=input["condition"],
        step_outputs=input["step_outputs"],
        params=input["params"],
    )


async def update_execution_status(
    ctx: PipelineActivityContext,
    input: Dict[str, Any]
) -> None:
    """Update execution status in budapp."""
    from ..services.budapp_client import BudAppClient

    client = BudAppClient()
    await client.update_execution_status(
        execution_id=input["execution_id"],
        status=input["status"],
        outputs=input.get("outputs"),
        error=input.get("error"),
    )
```

### 5.3 Pipeline Registration

```python
# budpipeline/workflows/__init__.py

from dapr.ext.workflow import PipelineRuntime

from .dag_workflow import dag_workflow
from .simple_job_workflow import simple_job_workflow
from .activities import (
    execute_step,
    evaluate_condition,
    update_execution_status,
)


def register_workflows(runtime: PipelineRuntime):
    """Register all workflows and activities with Dapr runtime."""

    # Register workflows
    runtime.register_workflow(dag_workflow)
    runtime.register_workflow(simple_job_workflow)

    # Register activities
    runtime.register_activity(execute_step)
    runtime.register_activity(evaluate_condition)
    runtime.register_activity(update_execution_status)
```

---

## 6. Action Handlers

### 6.1 Internal Action Handler

```python
# budpipeline/handlers/internal.py

from typing import Any, Dict, List
from uuid import UUID

from budmicroframe.shared.dapr_service import DaprServiceInvoker
from budmicroframe.commons.logging import get_logger

from .base import ActionHandler, ActionResult, ExecutionContext


logger = get_logger(__name__)


class InternalActionHandler(ActionHandler):
    """
    Handler for internal platform actions.
    Invokes other bud-stack services via Dapr.
    """

    # Action type to service/endpoint mapping
    ACTION_MAP = {
        "internal.model.onboard": {
            "app_id": "budmodel",
            "endpoint": "/api/v1/models/onboard",
            "method": "POST",
        },
        "internal.model.deploy": {
            "app_id": "budcluster",
            "endpoint": "/api/v1/deployments",
            "method": "POST",
        },
        "internal.deployment.scale": {
            "app_id": "budcluster",
            "endpoint": "/api/v1/deployments/{endpoint_id}/scale",
            "method": "POST",
        },
        "internal.deployment.delete": {
            "app_id": "budcluster",
            "endpoint": "/api/v1/deployments/{endpoint_id}",
            "method": "DELETE",
        },
        "internal.budsim.simulate": {
            "app_id": "budsim",
            "endpoint": "/api/v1/simulations",
            "method": "POST",
            "async": True,  # Long-running, poll for status
        },
        "internal.notify.send": {
            "app_id": "budnotify",
            "endpoint": "/api/v1/notifications",
            "method": "POST",
        },
    }

    def __init__(self):
        self.invoker = DaprServiceInvoker()

    @property
    def action_type(self) -> str:
        return "internal.*"  # Handles all internal actions

    def handles(self, action_type: str) -> bool:
        return action_type.startswith("internal.")

    async def validate(self, action_type: str, params: Dict[str, Any]) -> List[str]:
        """Validate parameters for internal action."""
        if action_type not in self.ACTION_MAP:
            return [f"Unknown action type: {action_type}"]

        # TODO: Fetch action schema from budapp and validate
        return []

    async def execute(
        self,
        execution_id: UUID,
        step_id: str,
        action_type: str,
        params: Dict[str, Any],
        context: ExecutionContext = None,
    ) -> ActionResult:
        """Execute internal action via Dapr service invocation."""

        if action_type not in self.ACTION_MAP:
            return ActionResult(
                success=False,
                error={"message": f"Unknown action type: {action_type}"},
            )

        config = self.ACTION_MAP[action_type]
        app_id = config["app_id"]
        endpoint = config["endpoint"]
        method = config["method"]

        # Substitute path parameters
        for key, value in params.items():
            if f"{{{key}}}" in endpoint:
                endpoint = endpoint.replace(f"{{{key}}}", str(value))

        logger.info(
            f"Executing internal action",
            extra={
                "execution_id": str(execution_id),
                "step_id": step_id,
                "action_type": action_type,
                "app_id": app_id,
                "endpoint": endpoint,
            }
        )

        try:
            # Invoke service
            response = await self.invoker.invoke(
                app_id=app_id,
                method=endpoint,
                http_method=method,
                data=params,
                headers={
                    "X-Execution-Id": str(execution_id),
                    "X-Step-Id": step_id,
                }
            )

            # Handle async actions (poll for completion)
            if config.get("async"):
                response = await self._poll_for_completion(
                    app_id=app_id,
                    workflow_id=response.get("workflow_id"),
                    timeout_seconds=context.timeout_seconds if context else 3600,
                )

            return ActionResult(
                success=True,
                outputs=response,
            )

        except Exception as e:
            logger.error(
                f"Internal action failed",
                extra={
                    "execution_id": str(execution_id),
                    "step_id": step_id,
                    "error": str(e),
                }
            )
            return ActionResult(
                success=False,
                error={"message": str(e), "type": type(e).__name__},
            )

    async def _poll_for_completion(
        self,
        app_id: str,
        workflow_id: str,
        timeout_seconds: int,
        poll_interval: int = 10,
    ) -> Dict[str, Any]:
        """Poll for async workflow completion."""
        import asyncio
        import time

        start_time = time.time()

        while time.time() - start_time < timeout_seconds:
            response = await self.invoker.invoke(
                app_id=app_id,
                method=f"/api/v1/workflows/{workflow_id}/status",
                http_method="GET",
            )

            status = response.get("status")
            if status == "COMPLETED":
                return response.get("result", {})
            elif status in ("FAILED", "CANCELLED"):
                raise Exception(f"Pipeline {workflow_id} {status}: {response.get('error')}")

            await asyncio.sleep(poll_interval)

        raise Exception(f"Pipeline {workflow_id} timed out after {timeout_seconds}s")
```

### 6.2 K8s Job Handler

```python
# budpipeline/handlers/k8s_job.py

from typing import Any, Dict, List
from uuid import UUID
import asyncio

from budmicroframe.shared.dapr_service import DaprServiceInvoker
from budmicroframe.commons.logging import get_logger

from .base import ActionHandler, ActionResult, ExecutionContext


logger = get_logger(__name__)


class K8sJobHandler(ActionHandler):
    """
    Handler for external Kubernetes Job actions.
    Delegates to budcluster for K8s operations.
    """

    def __init__(self):
        self.invoker = DaprServiceInvoker()

    @property
    def action_type(self) -> str:
        return "external.k8s.job"

    def handles(self, action_type: str) -> bool:
        return action_type == "external.k8s.job"

    async def validate(self, action_type: str, params: Dict[str, Any]) -> List[str]:
        """Validate K8s job parameters."""
        errors = []

        required = ["cluster_id", "image"]
        for field in required:
            if field not in params:
                errors.append(f"Missing required parameter: {field}")

        if "job_name" in params:
            # Validate K8s naming conventions
            import re
            if not re.match(r'^[a-z0-9]([-a-z0-9]*[a-z0-9])?$', params["job_name"]):
                errors.append("job_name must be a valid K8s name (lowercase, alphanumeric, hyphens)")

        return errors

    async def execute(
        self,
        execution_id: UUID,
        step_id: str,
        action_type: str,
        params: Dict[str, Any],
        context: ExecutionContext = None,
    ) -> ActionResult:
        """Create and monitor a Kubernetes Job."""

        cluster_id = params["cluster_id"]
        job_name = params.get("job_name", f"bud-job-{execution_id}-{step_id}"[:63])
        namespace = params.get("namespace", "bud-jobs")

        logger.info(
            f"Creating K8s job",
            extra={
                "execution_id": str(execution_id),
                "step_id": step_id,
                "cluster_id": cluster_id,
                "job_name": job_name,
            }
        )

        try:
            # Request budcluster to create the K8s job
            create_response = await self.invoker.invoke(
                app_id="budcluster",
                method="/api/v1/k8s/jobs",
                http_method="POST",
                data={
                    "cluster_id": cluster_id,
                    "job_name": job_name,
                    "namespace": namespace,
                    "image": params["image"],
                    "command": params.get("command"),
                    "args": params.get("args"),
                    "env_vars": params.get("env_vars", {}),
                    "resources": params.get("resources"),
                    "gpu_count": params.get("gpu_count", 0),
                    "node_selector": params.get("node_selector"),
                    "tolerations": params.get("tolerations"),
                    "backoff_limit": params.get("backoff_limit", 3),
                    "active_deadline_seconds": params.get("timeout_seconds", 3600),
                    "ttl_seconds_after_finished": params.get("ttl_seconds", 86400),
                    "labels": {
                        "bud-execution-id": str(execution_id),
                        "bud-step-id": step_id,
                    },
                },
                headers={
                    "X-Execution-Id": str(execution_id),
                    "X-Step-Id": step_id,
                }
            )

            k8s_job_uid = create_response["job_uid"]

            # Poll for job completion
            result = await self._wait_for_job(
                cluster_id=cluster_id,
                job_name=job_name,
                namespace=namespace,
                timeout_seconds=params.get("timeout_seconds", 3600),
            )

            if result["status"] == "completed":
                return ActionResult(
                    success=True,
                    outputs={
                        "job_uid": k8s_job_uid,
                        "job_name": job_name,
                        "namespace": namespace,
                        "logs": result.get("logs", ""),
                    },
                )
            else:
                return ActionResult(
                    success=False,
                    error={
                        "message": f"K8s job failed: {result.get('error', 'Unknown error')}",
                        "logs": result.get("logs", ""),
                    },
                )

        except Exception as e:
            logger.error(
                f"K8s job execution failed",
                extra={
                    "execution_id": str(execution_id),
                    "step_id": step_id,
                    "error": str(e),
                }
            )
            return ActionResult(
                success=False,
                error={"message": str(e), "type": type(e).__name__},
            )

    async def _wait_for_job(
        self,
        cluster_id: str,
        job_name: str,
        namespace: str,
        timeout_seconds: int,
        poll_interval: int = 10,
    ) -> Dict[str, Any]:
        """Poll for K8s job completion."""
        import time

        start_time = time.time()

        while time.time() - start_time < timeout_seconds:
            response = await self.invoker.invoke(
                app_id="budcluster",
                method=f"/api/v1/k8s/jobs/{job_name}/status",
                http_method="GET",
                data={
                    "cluster_id": cluster_id,
                    "namespace": namespace,
                },
            )

            status = response.get("status")

            if status == "completed":
                # Fetch logs
                logs_response = await self.invoker.invoke(
                    app_id="budcluster",
                    method=f"/api/v1/k8s/jobs/{job_name}/logs",
                    http_method="GET",
                    data={
                        "cluster_id": cluster_id,
                        "namespace": namespace,
                        "tail_lines": 1000,
                    },
                )
                return {
                    "status": "completed",
                    "logs": logs_response.get("logs", ""),
                }

            elif status == "failed":
                logs_response = await self.invoker.invoke(
                    app_id="budcluster",
                    method=f"/api/v1/k8s/jobs/{job_name}/logs",
                    http_method="GET",
                    data={
                        "cluster_id": cluster_id,
                        "namespace": namespace,
                        "tail_lines": 1000,
                    },
                )
                return {
                    "status": "failed",
                    "error": response.get("error", "Job failed"),
                    "logs": logs_response.get("logs", ""),
                }

            await asyncio.sleep(poll_interval)

        return {
            "status": "timeout",
            "error": f"Job timed out after {timeout_seconds}s",
        }

    async def cancel(self, execution_id: UUID, step_id: str, params: Dict) -> bool:
        """Cancel a running K8s job."""
        try:
            await self.invoker.invoke(
                app_id="budcluster",
                method=f"/api/v1/k8s/jobs/{params['job_name']}",
                http_method="DELETE",
                data={
                    "cluster_id": params["cluster_id"],
                    "namespace": params.get("namespace", "bud-jobs"),
                },
            )
            return True
        except Exception as e:
            logger.error(f"Failed to cancel K8s job: {e}")
            return False
```

### 6.3 Handler Registry

```python
# budpipeline/handlers/__init__.py

from typing import Dict, Type
from .base import ActionHandler
from .internal import InternalActionHandler
from .k8s_job import K8sJobHandler
from .helm import HelmActionHandler
from .git_deploy import GitDeployHandler
from .utility import (
    WaitHandler,
    HttpHandler,
    TransformHandler,
)


class HandlerRegistry:
    """Registry for action handlers."""

    _handlers: Dict[str, ActionHandler] = {}
    _initialized = False

    @classmethod
    def initialize(cls):
        """Initialize all handlers."""
        if cls._initialized:
            return

        handlers = [
            InternalActionHandler(),
            K8sJobHandler(),
            HelmActionHandler(),
            GitDeployHandler(),
            WaitHandler(),
            HttpHandler(),
            TransformHandler(),
        ]

        for handler in handlers:
            cls._handlers[handler.action_type] = handler

        cls._initialized = True

    @classmethod
    def get_handler(cls, action_type: str) -> ActionHandler:
        """Get handler for action type."""
        cls.initialize()

        # Check for exact match
        if action_type in cls._handlers:
            return cls._handlers[action_type]

        # Check for wildcard handlers
        for pattern, handler in cls._handlers.items():
            if handler.handles(action_type):
                return handler

        raise ValueError(f"No handler registered for action type: {action_type}")


def get_handler(action_type: str) -> ActionHandler:
    """Convenience function to get handler."""
    return HandlerRegistry.get_handler(action_type)
```

---

## 7. Monitoring & Observability

### 7.1 Status Tracker

```python
# budpipeline/monitor/status_tracker.py

from typing import Any, Dict, Optional
from uuid import UUID
from datetime import datetime, timezone

from budmicroframe.shared.dapr_state import DaprStateStore
from budmicroframe.commons.logging import get_logger


logger = get_logger(__name__)


class StatusTracker:
    """Tracks execution and step status in real-time."""

    STATE_STORE = "statestore"  # Dapr state store name

    def __init__(self):
        self.state_store = DaprStateStore(self.STATE_STORE)

    def _execution_key(self, execution_id: UUID) -> str:
        return f"execution:{execution_id}"

    def _step_key(self, execution_id: UUID, step_id: str) -> str:
        return f"execution:{execution_id}:step:{step_id}"

    async def initialize_execution(
        self,
        execution_id: UUID,
        workflow_id: UUID,
        params: Dict[str, Any],
        steps: list,
    ):
        """Initialize execution tracking state."""
        state = {
            "execution_id": str(execution_id),
            "workflow_id": str(workflow_id),
            "status": "pending",
            "params": params,
            "steps": {s["id"]: {"status": "pending"} for s in steps},
            "started_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        await self.state_store.save(
            key=self._execution_key(execution_id),
            value=state,
        )

    async def update_execution_status(
        self,
        execution_id: UUID,
        status: str,
        outputs: Optional[Dict] = None,
        error: Optional[Dict] = None,
    ):
        """Update overall execution status."""
        state = await self.state_store.get(self._execution_key(execution_id))
        if not state:
            logger.warning(f"Execution {execution_id} not found in state store")
            return

        state["status"] = status
        state["updated_at"] = datetime.now(timezone.utc).isoformat()

        if status in ("completed", "failed", "cancelled"):
            state["completed_at"] = datetime.now(timezone.utc).isoformat()

        if outputs:
            state["outputs"] = outputs
        if error:
            state["error"] = error

        await self.state_store.save(
            key=self._execution_key(execution_id),
            value=state,
        )

        # Publish status change event
        await self._publish_status_event(execution_id, status, state)

    async def update_step_status(
        self,
        execution_id: UUID,
        step_id: str,
        status: str,
        outputs: Optional[Dict] = None,
        error: Optional[Dict] = None,
        attempt: Optional[int] = None,
    ):
        """Update step status."""
        state = await self.state_store.get(self._execution_key(execution_id))
        if not state:
            return

        step_state = state["steps"].get(step_id, {})
        step_state["status"] = status
        step_state["updated_at"] = datetime.now(timezone.utc).isoformat()

        if status == "running":
            step_state["started_at"] = datetime.now(timezone.utc).isoformat()
        elif status in ("completed", "failed", "skipped"):
            step_state["completed_at"] = datetime.now(timezone.utc).isoformat()

        if outputs:
            step_state["outputs"] = outputs
        if error:
            step_state["error"] = error
        if attempt is not None:
            step_state["attempt"] = attempt

        state["steps"][step_id] = step_state
        state["current_step"] = step_id
        state["updated_at"] = datetime.now(timezone.utc).isoformat()

        await self.state_store.save(
            key=self._execution_key(execution_id),
            value=state,
        )

        # Publish step status event
        await self._publish_step_event(execution_id, step_id, status, step_state)

    async def get_execution_status(self, execution_id: UUID) -> Optional[Dict]:
        """Get current execution status."""
        return await self.state_store.get(self._execution_key(execution_id))

    async def _publish_status_event(
        self,
        execution_id: UUID,
        status: str,
        state: Dict,
    ):
        """Publish execution status change to pub/sub."""
        from budmicroframe.shared.dapr_pubsub import DaprPubSub

        pubsub = DaprPubSub()
        await pubsub.publish(
            pubsub_name="pubsub",
            topic="workflow.execution.status",
            data={
                "execution_id": str(execution_id),
                "status": status,
                "updated_at": state["updated_at"],
            },
        )

    async def _publish_step_event(
        self,
        execution_id: UUID,
        step_id: str,
        status: str,
        step_state: Dict,
    ):
        """Publish step status change to pub/sub."""
        from budmicroframe.shared.dapr_pubsub import DaprPubSub

        pubsub = DaprPubSub()
        await pubsub.publish(
            pubsub_name="pubsub",
            topic="workflow.step.status",
            data={
                "execution_id": str(execution_id),
                "step_id": step_id,
                "status": status,
                "updated_at": step_state.get("updated_at"),
            },
        )
```

### 7.2 Log Aggregator

```python
# budpipeline/monitor/log_aggregator.py

from typing import AsyncGenerator, List, Optional
from uuid import UUID
from datetime import datetime
import asyncio

from budmicroframe.shared.dapr_service import DaprServiceInvoker
from budmicroframe.commons.logging import get_logger


logger = get_logger(__name__)


class LogAggregator:
    """Aggregates logs from workflow executions."""

    def __init__(self):
        self.invoker = DaprServiceInvoker()

    async def get_logs(
        self,
        execution_id: UUID,
        step_id: Optional[str] = None,
        level: Optional[str] = None,
        since: Optional[datetime] = None,
        tail: int = 1000,
    ) -> List[dict]:
        """Get logs for an execution."""

        # Query budmetrics for stored logs
        response = await self.invoker.invoke(
            app_id="budmetrics",
            method="/api/v1/logs/query",
            http_method="POST",
            data={
                "filters": {
                    "execution_id": str(execution_id),
                    "step_id": step_id,
                    "level": level,
                    "since": since.isoformat() if since else None,
                },
                "limit": tail,
                "order": "desc",
            },
        )

        return response.get("logs", [])

    async def stream_logs(
        self,
        execution_id: UUID,
        step_id: Optional[str] = None,
    ) -> AsyncGenerator[dict, None]:
        """Stream logs in real-time via pub/sub."""
        from budmicroframe.shared.dapr_pubsub import DaprPubSub

        pubsub = DaprPubSub()
        topic = f"workflow.logs.{execution_id}"

        if step_id:
            topic = f"{topic}.{step_id}"

        async for message in pubsub.subscribe(
            pubsub_name="pubsub",
            topic=topic,
        ):
            yield message

    async def write_log(
        self,
        execution_id: UUID,
        step_id: str,
        level: str,
        message: str,
        metadata: Optional[dict] = None,
    ):
        """Write a log entry."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "execution_id": str(execution_id),
            "step_id": step_id,
            "level": level,
            "message": message,
            "metadata": metadata or {},
        }

        # Store in budmetrics
        await self.invoker.invoke(
            app_id="budmetrics",
            method="/api/v1/logs/ingest",
            http_method="POST",
            data=log_entry,
        )

        # Publish for real-time streaming
        from budmicroframe.shared.dapr_pubsub import DaprPubSub
        pubsub = DaprPubSub()
        await pubsub.publish(
            pubsub_name="pubsub",
            topic=f"workflow.logs.{execution_id}.{step_id}",
            data=log_entry,
        )
```

---

## 8. Service Structure

Following the bud-stack module-wise pattern (similar to budapp/budcluster), where each module contains its own routes, schemas, services, and models.

```
services/budpipeline/
├── budpipeline/
│   ├── __init__.py
│   ├── __about__.py                 # Version info
│   ├── main.py                      # FastAPI application entry
│   │
│   ├── commons/                     # Shared utilities & config
│   │   ├── __init__.py
│   │   ├── config.py               # Configuration settings
│   │   ├── exceptions.py           # Custom exceptions
│   │   └── constants.py            # Constants and enums
│   │
│   ├── core/                        # Core database & app setup
│   │   ├── __init__.py
│   │   ├── database.py             # Database session
│   │   └── dependencies.py         # FastAPI dependencies
│   │
│   ├── scheduler/                   # Job Scheduling Module
│   │   ├── __init__.py
│   │   ├── routes.py               # Scheduler API endpoints
│   │   ├── schemas.py              # Scheduler request/response schemas
│   │   ├── services.py             # Scheduler business logic
│   │   ├── dapr_jobs.py            # Dapr Jobs API wrapper
│   │   ├── cron_parser.py          # Cron expression parsing
│   │   └── triggers.py             # Trigger type handlers
│   │
│   ├── execution/                   # Execution Management Module
│   │   ├── __init__.py
│   │   ├── routes.py               # Execution API endpoints
│   │   ├── schemas.py              # Execution request/response schemas
│   │   ├── services.py             # Execution business logic
│   │   ├── status_tracker.py       # Real-time status tracking (Dapr state)
│   │   └── budapp_client.py        # Client for budapp status updates
│   │
│   ├── engine/                      # DAG Pipeline Engine Module
│   │   ├── __init__.py
│   │   ├── schemas.py              # DAG/Step schemas
│   │   ├── dag_parser.py           # Parse DAG YAML/JSON
│   │   ├── dag_validator.py        # Validate DAG structure
│   │   ├── dependency_resolver.py  # Topological sort, execution order
│   │   ├── param_resolver.py       # Jinja2 template substitution
│   │   ├── condition_evaluator.py  # Conditional expression evaluation
│   │   ├── dag_workflow.py         # Dapr Pipeline: DAG execution
│   │   ├── simple_workflow.py      # Dapr Pipeline: Single action
│   │   └── activities.py           # Dapr Activities (execute_step, etc.)
│   │
│   ├── handlers/                    # Action Handlers Module
│   │   ├── __init__.py
│   │   ├── schemas.py              # Handler schemas (ActionResult, etc.)
│   │   ├── registry.py             # Handler registry & discovery
│   │   ├── base.py                 # Base ActionHandler interface
│   │   ├── internal.py             # Internal service actions (Dapr invoke)
│   │   ├── k8s_job.py              # Kubernetes Job handler
│   │   ├── helm.py                 # Helm deploy/upgrade handler
│   │   ├── git_deploy.py           # Git clone & run handler
│   │   └── utility.py              # Utility handlers (wait, http, transform)
│   │
│   ├── monitor/                     # Monitoring & Logs Module
│   │   ├── __init__.py
│   │   ├── routes.py               # Logs/metrics API endpoints
│   │   ├── schemas.py              # Log/metrics schemas
│   │   ├── services.py             # Monitoring business logic
│   │   ├── log_aggregator.py       # Log collection & storage
│   │   ├── metrics_collector.py    # Execution metrics
│   │   └── websocket_manager.py    # WebSocket for live streaming
│   │
│   ├── webhook/                     # Webhook Triggers Module
│   │   ├── __init__.py
│   │   ├── routes.py               # Webhook API endpoints
│   │   ├── schemas.py              # Webhook schemas
│   │   └── services.py             # Webhook validation & dispatch
│   │
│   └── shared/                      # Shared utilities across modules
│       ├── __init__.py
│       ├── dapr_client.py          # Dapr service invoker wrapper
│       ├── dapr_state.py           # Dapr state store wrapper
│       └── dapr_pubsub.py          # Dapr pub/sub wrapper
│
├── deploy/
│   ├── Dockerfile
│   ├── docker-compose.yaml
│   ├── docker-compose-dev.yaml
│   ├── start_dev.sh
│   └── stop_dev.sh
│
├── dapr/
│   ├── components/
│   │   ├── statestore.yaml         # Redis state store
│   │   ├── pubsub.yaml             # Pub/sub component
│   │   └── scheduler.yaml          # Scheduler binding
│   └── config.yaml                 # Dapr configuration
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                 # Pytest fixtures
│   ├── test_scheduler/             # Scheduler module tests
│   │   ├── test_routes.py
│   │   ├── test_services.py
│   │   └── test_cron_parser.py
│   ├── test_execution/             # Execution module tests
│   │   ├── test_routes.py
│   │   └── test_services.py
│   ├── test_engine/                # Engine module tests
│   │   ├── test_dag_parser.py
│   │   ├── test_dependency_resolver.py
│   │   ├── test_param_resolver.py
│   │   └── test_condition_evaluator.py
│   ├── test_handlers/              # Handler tests
│   │   ├── test_internal.py
│   │   ├── test_k8s_job.py
│   │   └── test_helm.py
│   └── test_integration/           # Integration tests
│       ├── test_full_dag_execution.py
│       └── test_scheduled_job.py
│
├── pyproject.toml
├── .env.sample
├── SPEC.md                          # This file
└── README.md
```

### Module Summary

| Module | Purpose | Key Files |
|--------|---------|-----------|
| `scheduler/` | Job scheduling (cron, interval, triggers) | routes, services, dapr_jobs, cron_parser |
| `execution/` | Execution lifecycle management | routes, services, status_tracker |
| `engine/` | DAG parsing, validation, Dapr workflows | dag_parser, dag_workflow, activities |
| `handlers/` | Action type implementations | internal, k8s_job, helm, git_deploy |
| `monitor/` | Logs, metrics, WebSocket streaming | log_aggregator, websocket_manager |
| `webhook/` | External webhook triggers | routes, services |
| `commons/` | Config, exceptions, constants | config, exceptions |
| `shared/` | Dapr wrappers, shared utilities | dapr_client, dapr_state |

---

## 9. Testing Strategy

### 9.1 Unit Tests

| Component | Test Focus |
|-----------|------------|
| `dag_parser` | Parse valid/invalid DAGs, edge cases |
| `dependency_resolver` | Topological sort, cycle detection |
| `param_resolver` | Template substitution, nested values |
| `condition_evaluator` | Boolean logic, comparisons |
| `handlers/*` | Parameter validation, mock responses |

### 9.2 Integration Tests

| Test | Description |
|------|-------------|
| `test_simple_execution` | Single action execution end-to-end |
| `test_dag_execution` | Multi-step DAG with dependencies |
| `test_parallel_steps` | Parallel step execution |
| `test_retry_logic` | Retry on failure |
| `test_conditional_skip` | Skip steps based on conditions |
| `test_scheduler_trigger` | Scheduled job triggers execution |

### 9.3 E2E Tests

| Test | Description |
|------|-------------|
| `test_model_deployment_pipeline` | Full onboard → simulate → deploy flow |
| `test_k8s_job_execution` | Create and monitor K8s job |
| `test_webhook_trigger` | External webhook triggers workflow |

### 9.4 Test Fixtures

```python
# tests/conftest.py

import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def sample_dag():
    return {
        "name": "test-workflow",
        "version": "1.0",
        "parameters": [
            {"name": "input_value", "type": "string", "required": True}
        ],
        "steps": [
            {
                "id": "step1",
                "name": "First Step",
                "action": "internal.test.action",
                "params": {"value": "{{ params.input_value }}"},
                "outputs": ["result"],
            },
            {
                "id": "step2",
                "name": "Second Step",
                "action": "internal.test.action",
                "depends_on": ["step1"],
                "params": {"input": "{{ steps.step1.outputs.result }}"},
            },
        ],
        "outputs": {
            "final_result": "{{ steps.step2.outputs.result }}",
        },
    }

@pytest.fixture
def mock_dapr_invoker():
    invoker = AsyncMock()
    invoker.invoke.return_value = {"status": "success", "result": "test"}
    return invoker

@pytest.fixture
def mock_state_store():
    store = AsyncMock()
    store.get.return_value = None
    store.save.return_value = None
    return store
```

---

## 10. Development Phases

### Phase 1: Core Infrastructure (Week 1-2)

**Goals:**
- Service skeleton with FastAPI + budmicroframe
- Basic DAG parser and validator
- Dapr workflow integration
- Simple execution (single action)

**Deliverables:**
- [ ] Service structure created
- [ ] DAG parser with YAML/JSON support
- [ ] Dependency resolver (topological sort)
- [ ] Dapr workflow registration
- [ ] Single action execution working
- [ ] Unit tests for parser/resolver

**Test:**
```bash
# Trigger simple execution
curl -X POST http://localhost:8010/api/v1/execute \
  -H "Content-Type: application/json" \
  -d '{
    "action_type": "util.wait",
    "params": {"seconds": 5}
  }'
```

### Phase 2: DAG Execution Engine (Week 3-4)

**Goals:**
- Full DAG workflow execution
- Parameter templating (Jinja2)
- Conditional execution
- Error handling and retries

**Deliverables:**
- [ ] Multi-step DAG execution
- [ ] Parameter resolver with templates
- [ ] Condition evaluator
- [ ] Retry logic per step
- [ ] fail_fast / continue modes
- [ ] Integration tests for DAG execution

**Test:**
```bash
# Execute multi-step workflow
curl -X POST http://localhost:8010/api/v1/execute \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_definition": {...},
    "params": {"model_uri": "meta-llama/Llama-2-7b"}
  }'
```

### Phase 3: Action Handlers (Week 5-6)

**Goals:**
- Internal action handler (Dapr service invocation)
- K8s Job handler
- Helm handler
- Git deploy handler

**Deliverables:**
- [ ] InternalActionHandler with service mapping
- [ ] K8sJobHandler with budcluster integration
- [ ] HelmActionHandler
- [ ] GitDeployHandler
- [ ] Utility handlers (wait, http, transform)
- [ ] Handler tests with mocks

**Test:**
```bash
# Execute K8s job action
curl -X POST http://localhost:8010/api/v1/execute \
  -H "Content-Type: application/json" \
  -d '{
    "action_type": "external.k8s.job",
    "params": {
      "cluster_id": "...",
      "image": "python:3.11",
      "command": ["python", "-c", "print(\"hello\")"]
    }
  }'
```

### Phase 4: Scheduling (Week 7)

**Goals:**
- Dapr Jobs integration
- Cron expression support
- Job lifecycle management

**Deliverables:**
- [ ] Dapr Jobs wrapper
- [ ] Cron parser with timezone support
- [ ] Schedule CRUD APIs
- [ ] Pause/resume functionality
- [ ] Webhook triggers
- [ ] Scheduler tests

**Test:**
```bash
# Create scheduled job
curl -X POST http://localhost:8010/api/v1/scheduler/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "...",
    "schedule": {
      "type": "cron",
      "expression": "0 9 * * 1-5",
      "timezone": "America/New_York"
    }
  }'
```

### Phase 5: Monitoring & Observability (Week 8)

**Goals:**
- Real-time status tracking
- Log aggregation
- WebSocket streaming
- Metrics collection

**Deliverables:**
- [ ] StatusTracker with Dapr state
- [ ] LogAggregator with budmetrics
- [ ] WebSocket manager for live updates
- [ ] Pub/sub for status events
- [ ] Grafana dashboard
- [ ] E2E tests

**Test:**
```bash
# Stream execution logs
wscat -c ws://localhost:8010/api/v1/executions/{id}/logs/stream
```

### Phase 6: Integration & Polish (Week 9-10)

**Goals:**
- budapp integration
- Error handling improvements
- Performance optimization
- Documentation

**Deliverables:**
- [ ] budapp client for status updates
- [ ] Credentials resolution (from budapp)
- [ ] Rate limiting
- [ ] Circuit breakers
- [ ] API documentation (OpenAPI)
- [ ] Deployment guide

---

## 11. Configuration

### Environment Variables

```bash
# .env.sample

# Service
SERVICE_NAME=budpipeline
SERVICE_PORT=8010
LOG_LEVEL=INFO

# Dapr
DAPR_HTTP_PORT=3510
DAPR_GRPC_PORT=50010

# State Store
STATE_STORE_NAME=statestore

# Pub/Sub
PUBSUB_NAME=pubsub

# Service Discovery
BUDAPP_APP_ID=budapp
BUDCLUSTER_APP_ID=budcluster
BUDMODEL_APP_ID=budmodel
BUDSIM_APP_ID=budsim
BUDNOTIFY_APP_ID=budnotify
BUDMETRICS_APP_ID=budmetrics

# Pipeline Settings
WORKFLOW_DEFAULT_TIMEOUT=7200
WORKFLOW_MAX_PARALLEL_STEPS=10
WORKFLOW_RETRY_MAX_ATTEMPTS=3
WORKFLOW_RETRY_BACKOFF_SECONDS=60

# Scheduler
SCHEDULER_POLL_INTERVAL=60
SCHEDULER_MAX_CONCURRENT_JOBS=100
```

### Dapr Components

```yaml
# dapr/components/statestore.yaml
apiVersion: dapr.io/v1alpha1
kind: Component
metadata:
  name: statestore
spec:
  type: state.redis
  version: v1
  metadata:
    - name: redisHost
      value: redis:6379
    - name: actorStateStore
      value: "true"
```

```yaml
# dapr/components/pubsub.yaml
apiVersion: dapr.io/v1alpha1
kind: Component
metadata:
  name: pubsub
spec:
  type: pubsub.redis
  version: v1
  metadata:
    - name: redisHost
      value: redis:6379
```

---

## 12. Success Metrics

| Metric | Target |
|--------|--------|
| Execution start latency | < 500ms |
| Step dispatch latency | < 100ms |
| Status update latency | < 200ms |
| Pipeline success rate | > 95% |
| Scheduler accuracy | < 1 minute drift |
| API response time (p95) | < 200ms |
| Concurrent executions | > 100 |

---

## 13. Future Enhancements

1. **Visual Pipeline Editor** - Drag-and-drop DAG builder in budadmin
2. **Pipeline Versioning** - Git-like versioning for workflows
3. **Approval Gates** - Manual approval steps in workflows
4. **Cost Tracking** - Track resource costs per execution
5. **SLA Monitoring** - Alert on execution time violations
6. **Pipeline Templates Marketplace** - Share workflows across teams
7. **Multi-cluster Orchestration** - Execute steps across different clusters
8. **Event-driven Pipelines** - Trigger on model performance degradation
