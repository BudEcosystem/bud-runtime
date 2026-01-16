# BudPipeline DAG Structure

This document describes the DAG (Directed Acyclic Graph) structure used by budpipeline for defining and executing pipelines.

## Table of Contents

- [Overview](#overview)
- [Core Schema](#core-schema)
- [Data Flow](#data-flow)
- [Control Flow](#control-flow)
- [Sample DAGs](#sample-dags)

---

## Overview

BudPipeline uses a DAG-based execution model where:
- **Nodes** represent pipeline steps (actions to execute)
- **Edges** represent dependencies (`depends_on` relationships)
- **Execution** proceeds in topological order with parallel execution of independent steps

### Key Characteristics

| Feature | Description |
|---------|-------------|
| **Execution Model** | Topological sort with parallel batching |
| **Data Passing** | Jinja2 templates referencing `params` and `steps.*.outputs` |
| **Control Flow** | Condition-based step execution, fan-out/fan-in |
| **Error Handling** | Per-step failure actions with retry support |

---

## Core Schema

### PipelineDAG (Root)

```json
{
  "name": "string (required)",
  "version": "string (default: 1.0)",
  "description": "string (optional)",
  "parameters": [PipelineParameter],
  "settings": PipelineSettings,
  "steps": [PipelineStep],
  "outputs": { "key": "{{ template }}" }
}
```

### PipelineParameter

```json
{
  "name": "string (required)",
  "type": "string|integer|float|boolean|array|object|cluster_ref|model_ref|endpoint_ref|project_ref|credential_ref",
  "description": "string (optional)",
  "required": true,
  "default": "any (optional)"
}
```

### PipelineSettings

```json
{
  "timeout_seconds": 7200,
  "fail_fast": true,
  "max_parallel_steps": 10,
  "retry_policy": RetryConfig
}
```

### PipelineStep

```json
{
  "id": "string (required, unique)",
  "name": "string (required)",
  "action": "string (required, handler name)",
  "params": { "key": "value or {{ template }}" },
  "depends_on": ["step_id", ...],
  "outputs": ["output_name", ...],
  "condition": "{{ boolean_expression }}",
  "on_failure": "fail|continue|retry",
  "timeout_seconds": 300,
  "retry": RetryConfig
}
```

### RetryConfig

```json
{
  "max_attempts": 3,
  "backoff_seconds": 60,
  "backoff_multiplier": 2.0,
  "max_backoff_seconds": 3600
}
```

---

## Data Flow

### Parameter Templates

BudPipeline uses Jinja2 templates for dynamic parameter resolution:

```
{{ params.parameter_name }}              # Pipeline input parameter
{{ steps.step_id.outputs.output_name }}  # Previous step output
{{ steps.step_id.outputs.result | default('fallback') }}  # With default
```

### Template Context

| Variable | Description |
|----------|-------------|
| `params` | Pipeline input parameters |
| `steps` | Dict of completed step outputs: `{ step_id: { outputs: {...} } }` |
| `true`, `false`, `none` | Boolean/None literals |

### Supported Jinja2 Features

- **Filters**: `default`, `length`, `lower`, `upper`, `int`, `float`, `string`
- **Operators**: `==`, `!=`, `<`, `>`, `<=`, `>=`, `and`, `or`, `not`, `in`
- **Conditionals**: `{{ value if condition else other }}`

---

## Control Flow

### 1. Sequential Execution

Steps execute in dependency order. A step waits for all `depends_on` steps to complete.

```
┌─────────┐     ┌─────────┐     ┌─────────┐
│ Step A  │────▶│ Step B  │────▶│ Step C  │
└─────────┘     └─────────┘     └─────────┘
```

```json
{
  "steps": [
    { "id": "a", "action": "log", "params": {} },
    { "id": "b", "action": "transform", "depends_on": ["a"] },
    { "id": "c", "action": "log", "depends_on": ["b"] }
  ]
}
```

### 2. Fan-Out (Parallel Branches)

Multiple steps depending on the same parent execute in parallel.

```
                ┌─────────┐
           ┌───▶│ Branch A│
┌─────────┐│    └─────────┘
│  Start  │├───▶┌─────────┐
└─────────┘│    │ Branch B│
           │    └─────────┘
           └───▶┌─────────┐
                │ Branch C│
                └─────────┘
```

```json
{
  "steps": [
    { "id": "start", "action": "log" },
    { "id": "branch_a", "action": "process", "depends_on": ["start"] },
    { "id": "branch_b", "action": "process", "depends_on": ["start"] },
    { "id": "branch_c", "action": "process", "depends_on": ["start"] }
  ]
}
```

### 3. Fan-In (Merge/Join)

A step depending on multiple parents waits for ALL to complete.

```
┌─────────┐
│ Branch A│───┐
└─────────┘   │    ┌─────────┐
┌─────────┐   ├───▶│  Merge  │
│ Branch B│───┤    └─────────┘
└─────────┘   │
┌─────────┐   │
│ Branch C│───┘
└─────────┘
```

```json
{
  "steps": [
    { "id": "branch_a", "action": "process" },
    { "id": "branch_b", "action": "process" },
    { "id": "branch_c", "action": "process" },
    { "id": "merge", "action": "aggregate", "depends_on": ["branch_a", "branch_b", "branch_c"] }
  ]
}
```

### 4. Conditional Execution (If)

Steps with `condition` only execute if the condition evaluates to true.

```
┌─────────┐     ┌─────────────────┐
│  Start  │────▶│ Transform       │
└─────────┘     │ condition:      │
                │ {{ params.run }}│
                └─────────────────┘
```

```json
{
  "steps": [
    { "id": "start", "action": "log" },
    {
      "id": "transform",
      "action": "transform",
      "depends_on": ["start"],
      "condition": "{{ params.run_transform }}"
    }
  ]
}
```

### 5. Conditional Branching (If/Else)

Two conditional steps with mutually exclusive conditions.

```
                    ┌───────────────────┐
               ┌───▶│ Fast Path         │
               │    │ condition:        │
               │    │ {{ mode == fast }}│
┌─────────┐    │    └─────────┬─────────┘
│ Classify│────┤              │
└─────────┘    │              ▼
               │    ┌─────────────────┐
               └───▶│ Slow Path       │───▶┌─────────┐
                    │ condition:      │    │  Merge  │
                    │ {{ mode != fast}}│    └─────────┘
                    └─────────────────┘
```

```json
{
  "steps": [
    { "id": "classify", "action": "classify_input" },
    {
      "id": "fast_path",
      "action": "fast_process",
      "depends_on": ["classify"],
      "condition": "{{ steps.classify.outputs.mode == 'fast' }}"
    },
    {
      "id": "slow_path",
      "action": "slow_process",
      "depends_on": ["classify"],
      "condition": "{{ steps.classify.outputs.mode != 'fast' }}"
    },
    {
      "id": "merge",
      "action": "aggregate",
      "depends_on": ["fast_path", "slow_path"]
    }
  ]
}
```

### 6. Switch/Multi-way Conditional

Multiple conditional branches based on different values.

```
                ┌─────────────────┐
           ┌───▶│ Urgent Handler  │───┐
           │    │ cond: urgent    │   │
           │    └─────────────────┘   │
┌─────────┐│    ┌─────────────────┐   │    ┌─────────┐
│ Router  │├───▶│ Normal Handler  │───┼───▶│ Complete│
└─────────┘│    │ cond: normal    │   │    └─────────┘
           │    └─────────────────┘   │
           │    ┌─────────────────┐   │
           └───▶│ Low Handler     │───┘
                │ cond: low       │
                └─────────────────┘
```

```json
{
  "steps": [
    { "id": "router", "action": "classify_priority" },
    {
      "id": "urgent_handler",
      "action": "handle_urgent",
      "depends_on": ["router"],
      "condition": "{{ steps.router.outputs.priority == 'urgent' }}"
    },
    {
      "id": "normal_handler",
      "action": "handle_normal",
      "depends_on": ["router"],
      "condition": "{{ steps.router.outputs.priority == 'normal' }}"
    },
    {
      "id": "low_handler",
      "action": "handle_low",
      "depends_on": ["router"],
      "condition": "{{ steps.router.outputs.priority == 'low' }}"
    },
    {
      "id": "complete",
      "action": "finalize",
      "depends_on": ["urgent_handler", "normal_handler", "low_handler"]
    }
  ]
}
```

### 7. For-Each (Parallel Iteration)

Use the `for_each` action handler to process items in parallel.

```
┌─────────┐     ┌─────────────────────┐     ┌─────────┐
│Get Items│────▶│ For Each            │────▶│ Summary │
└─────────┘     │ ┌─────────────────┐ │     └─────────┘
                │ │ item[0]→process │ │
                │ │ item[1]→process │ │
                │ │ item[2]→process │ │
                │ └─────────────────┘ │
                └─────────────────────┘
```

```json
{
  "steps": [
    { "id": "get_items", "action": "list_items" },
    {
      "id": "process_items",
      "action": "for_each",
      "depends_on": ["get_items"],
      "params": {
        "items": "{{ steps.get_items.outputs.items }}",
        "action": "process_item",
        "action_params": {
          "item_id": "{{ item.id }}",
          "item_data": "{{ item.data }}"
        },
        "parallel": true,
        "max_concurrency": 5
      }
    },
    {
      "id": "summary",
      "action": "aggregate",
      "depends_on": ["process_items"],
      "params": {
        "results": "{{ steps.process_items.outputs.results }}"
      }
    }
  ]
}
```

### 8. While Loop (Polling/Retry)

Use the `while` action handler for conditional looping.

```
┌─────────┐     ┌─────────────────────┐     ┌─────────┐
│Start Job│────▶│ While               │────▶│ Process │
└─────────┘     │ ┌─────────────────┐ │     │ Result  │
                │ │ Poll status     │ │     └─────────┘
                │ │ until complete  │ │
                │ │ max: 100 iter   │ │
                │ └─────────────────┘ │
                └─────────────────────┘
```

```json
{
  "steps": [
    { "id": "start_job", "action": "submit_job" },
    {
      "id": "wait_completion",
      "action": "while",
      "depends_on": ["start_job"],
      "params": {
        "condition": "{{ result.status != 'complete' and result.status != 'failed' }}",
        "action": "check_job_status",
        "action_params": {
          "job_id": "{{ steps.start_job.outputs.job_id }}"
        },
        "max_iterations": 100,
        "delay_seconds": 30
      }
    },
    {
      "id": "process_result",
      "action": "handle_result",
      "depends_on": ["wait_completion"],
      "params": {
        "status": "{{ steps.wait_completion.outputs.result.status }}",
        "data": "{{ steps.wait_completion.outputs.result.data }}"
      }
    }
  ]
}
```

### 9. Error Handling

Configure per-step error behavior with `on_failure` and `retry`.

```json
{
  "id": "risky_operation",
  "action": "external_api_call",
  "on_failure": "retry",
  "retry": {
    "max_attempts": 3,
    "backoff_seconds": 10,
    "backoff_multiplier": 2.0,
    "max_backoff_seconds": 120
  }
}
```

**Failure Actions:**
| Action | Behavior |
|--------|----------|
| `fail` | Stop pipeline immediately (default) |
| `continue` | Skip step, continue with dependents |
| `retry` | Retry with backoff, then fail |

---

## Sample DAGs

### Sample 1: Simple Linear Pipeline

```json
{
  "name": "simple-linear",
  "version": "1.0",
  "description": "Simple linear pipeline with three steps",
  "parameters": [
    {
      "name": "message",
      "type": "string",
      "default": "Hello"
    }
  ],
  "steps": [
    {
      "id": "step1",
      "name": "Log Input",
      "action": "log",
      "params": {
        "message": "Input: {{ params.message }}",
        "level": "info"
      }
    },
    {
      "id": "step2",
      "name": "Transform",
      "action": "transform",
      "depends_on": ["step1"],
      "params": {
        "input": "{{ params.message }}",
        "operation": "uppercase"
      }
    },
    {
      "id": "step3",
      "name": "Log Output",
      "action": "log",
      "depends_on": ["step2"],
      "params": {
        "message": "Output: {{ steps.step2.outputs.result }}",
        "level": "info"
      }
    }
  ],
  "outputs": {
    "result": "{{ steps.step2.outputs.result }}"
  }
}
```

### Sample 2: Fan-Out/Fan-In Parallel Processing

```json
{
  "name": "parallel-processing",
  "version": "1.0",
  "description": "Parallel processing with fan-out and fan-in",
  "parameters": [
    {
      "name": "input_data",
      "type": "object",
      "required": true
    }
  ],
  "settings": {
    "max_parallel_steps": 5
  },
  "steps": [
    {
      "id": "validate",
      "name": "Validate Input",
      "action": "validate",
      "params": {
        "data": "{{ params.input_data }}",
        "schema": "input_schema_v1"
      }
    },
    {
      "id": "process_text",
      "name": "Process Text",
      "action": "text_processor",
      "depends_on": ["validate"],
      "params": {
        "text": "{{ params.input_data.text }}"
      }
    },
    {
      "id": "process_images",
      "name": "Process Images",
      "action": "image_processor",
      "depends_on": ["validate"],
      "params": {
        "images": "{{ params.input_data.images }}"
      }
    },
    {
      "id": "process_metadata",
      "name": "Process Metadata",
      "action": "metadata_processor",
      "depends_on": ["validate"],
      "params": {
        "metadata": "{{ params.input_data.metadata }}"
      }
    },
    {
      "id": "aggregate",
      "name": "Aggregate Results",
      "action": "aggregate",
      "depends_on": ["process_text", "process_images", "process_metadata"],
      "params": {
        "text_result": "{{ steps.process_text.outputs.result }}",
        "image_result": "{{ steps.process_images.outputs.result }}",
        "metadata_result": "{{ steps.process_metadata.outputs.result }}"
      }
    },
    {
      "id": "store",
      "name": "Store Results",
      "action": "store",
      "depends_on": ["aggregate"],
      "params": {
        "data": "{{ steps.aggregate.outputs.combined }}"
      }
    }
  ],
  "outputs": {
    "stored_id": "{{ steps.store.outputs.id }}",
    "summary": "{{ steps.aggregate.outputs.summary }}"
  }
}
```

### Sample 3: Conditional Branching with Switch

```json
{
  "name": "priority-router",
  "version": "1.0",
  "description": "Route tasks based on priority classification",
  "parameters": [
    {
      "name": "task",
      "type": "object",
      "required": true
    }
  ],
  "steps": [
    {
      "id": "classify",
      "name": "Classify Priority",
      "action": "classify_priority",
      "params": {
        "task": "{{ params.task }}"
      }
    },
    {
      "id": "urgent_path",
      "name": "Handle Urgent",
      "action": "urgent_processor",
      "depends_on": ["classify"],
      "condition": "{{ steps.classify.outputs.priority == 'urgent' }}",
      "params": {
        "task": "{{ params.task }}",
        "sla_minutes": 15
      }
    },
    {
      "id": "high_path",
      "name": "Handle High Priority",
      "action": "high_priority_processor",
      "depends_on": ["classify"],
      "condition": "{{ steps.classify.outputs.priority == 'high' }}",
      "params": {
        "task": "{{ params.task }}",
        "sla_minutes": 60
      }
    },
    {
      "id": "normal_path",
      "name": "Handle Normal",
      "action": "standard_processor",
      "depends_on": ["classify"],
      "condition": "{{ steps.classify.outputs.priority == 'normal' }}",
      "params": {
        "task": "{{ params.task }}",
        "sla_minutes": 240
      }
    },
    {
      "id": "low_path",
      "name": "Handle Low Priority",
      "action": "batch_processor",
      "depends_on": ["classify"],
      "condition": "{{ steps.classify.outputs.priority == 'low' }}",
      "params": {
        "task": "{{ params.task }}",
        "batch_delay_minutes": 60
      }
    },
    {
      "id": "notify",
      "name": "Send Notification",
      "action": "notify",
      "depends_on": ["urgent_path", "high_path", "normal_path", "low_path"],
      "params": {
        "task_id": "{{ params.task.id }}",
        "priority": "{{ steps.classify.outputs.priority }}",
        "processed_at": "{{ steps.urgent_path.outputs.completed_at | default(steps.high_path.outputs.completed_at) | default(steps.normal_path.outputs.completed_at) | default(steps.low_path.outputs.completed_at) }}"
      }
    }
  ],
  "outputs": {
    "task_id": "{{ params.task.id }}",
    "priority": "{{ steps.classify.outputs.priority }}",
    "status": "completed"
  }
}
```

### Sample 4: Complex Pipeline with Control Flow

```json
{
  "name": "model-deployment-pipeline",
  "version": "1.0",
  "description": "Complete model deployment pipeline with validation, parallel checks, and conditional rollback",
  "parameters": [
    {
      "name": "model_id",
      "type": "model_ref",
      "required": true,
      "description": "Model to deploy"
    },
    {
      "name": "cluster_id",
      "type": "cluster_ref",
      "required": true,
      "description": "Target cluster"
    },
    {
      "name": "endpoint_name",
      "type": "string",
      "required": true
    },
    {
      "name": "replicas",
      "type": "integer",
      "default": 2
    },
    {
      "name": "run_load_test",
      "type": "boolean",
      "default": true
    },
    {
      "name": "auto_rollback",
      "type": "boolean",
      "default": true
    }
  ],
  "settings": {
    "timeout_seconds": 3600,
    "fail_fast": false,
    "max_parallel_steps": 5
  },
  "steps": [
    {
      "id": "validate_model",
      "name": "Validate Model",
      "action": "validate_model",
      "params": {
        "model_id": "{{ params.model_id }}"
      }
    },
    {
      "id": "validate_cluster",
      "name": "Validate Cluster",
      "action": "validate_cluster",
      "params": {
        "cluster_id": "{{ params.cluster_id }}"
      }
    },
    {
      "id": "check_resources",
      "name": "Check Available Resources",
      "action": "check_cluster_resources",
      "depends_on": ["validate_cluster"],
      "params": {
        "cluster_id": "{{ params.cluster_id }}",
        "required_gpus": "{{ steps.validate_model.outputs.required_gpus }}",
        "required_memory_gb": "{{ steps.validate_model.outputs.required_memory_gb }}"
      }
    },
    {
      "id": "run_simulation",
      "name": "Run Performance Simulation",
      "action": "run_budsim",
      "depends_on": ["validate_model", "validate_cluster"],
      "params": {
        "model_id": "{{ params.model_id }}",
        "cluster_id": "{{ params.cluster_id }}",
        "replicas": "{{ params.replicas }}"
      }
    },
    {
      "id": "prepare_deployment",
      "name": "Prepare Deployment Config",
      "action": "prepare_deployment",
      "depends_on": ["check_resources", "run_simulation"],
      "params": {
        "model_id": "{{ params.model_id }}",
        "cluster_id": "{{ params.cluster_id }}",
        "endpoint_name": "{{ params.endpoint_name }}",
        "replicas": "{{ params.replicas }}",
        "optimization_config": "{{ steps.run_simulation.outputs.optimal_config }}"
      }
    },
    {
      "id": "backup_existing",
      "name": "Backup Existing Deployment",
      "action": "backup_deployment",
      "depends_on": ["prepare_deployment"],
      "condition": "{{ params.auto_rollback }}",
      "on_failure": "continue",
      "params": {
        "endpoint_name": "{{ params.endpoint_name }}",
        "cluster_id": "{{ params.cluster_id }}"
      }
    },
    {
      "id": "deploy_model",
      "name": "Deploy Model",
      "action": "deploy_to_cluster",
      "depends_on": ["backup_existing"],
      "params": {
        "deployment_config": "{{ steps.prepare_deployment.outputs.config }}"
      },
      "on_failure": "continue",
      "retry": {
        "max_attempts": 2,
        "backoff_seconds": 30
      }
    },
    {
      "id": "health_check",
      "name": "Run Health Check",
      "action": "health_check",
      "depends_on": ["deploy_model"],
      "condition": "{{ steps.deploy_model.outputs.success }}",
      "params": {
        "endpoint_url": "{{ steps.deploy_model.outputs.endpoint_url }}",
        "timeout_seconds": 120
      },
      "on_failure": "continue"
    },
    {
      "id": "load_test",
      "name": "Run Load Test",
      "action": "load_test",
      "depends_on": ["health_check"],
      "condition": "{{ params.run_load_test and steps.health_check.outputs.healthy }}",
      "params": {
        "endpoint_url": "{{ steps.deploy_model.outputs.endpoint_url }}",
        "requests_per_second": 10,
        "duration_seconds": 60
      },
      "on_failure": "continue"
    },
    {
      "id": "rollback",
      "name": "Rollback Deployment",
      "action": "rollback_deployment",
      "depends_on": ["health_check", "load_test"],
      "condition": "{{ params.auto_rollback and (not steps.health_check.outputs.healthy or (steps.load_test.outputs.success is defined and not steps.load_test.outputs.success)) }}",
      "params": {
        "backup_id": "{{ steps.backup_existing.outputs.backup_id }}",
        "cluster_id": "{{ params.cluster_id }}"
      }
    },
    {
      "id": "update_registry",
      "name": "Update Endpoint Registry",
      "action": "update_registry",
      "depends_on": ["health_check", "load_test", "rollback"],
      "condition": "{{ steps.health_check.outputs.healthy and (steps.load_test.outputs.success | default(true)) and not steps.rollback.outputs.rolled_back | default(false) }}",
      "params": {
        "endpoint_name": "{{ params.endpoint_name }}",
        "endpoint_url": "{{ steps.deploy_model.outputs.endpoint_url }}",
        "model_id": "{{ params.model_id }}"
      }
    },
    {
      "id": "notify_result",
      "name": "Send Notification",
      "action": "notify",
      "depends_on": ["update_registry", "rollback"],
      "params": {
        "channel": "deployments",
        "status": "{{ 'success' if steps.update_registry.outputs.updated else 'failed' }}",
        "model_id": "{{ params.model_id }}",
        "endpoint": "{{ params.endpoint_name }}",
        "details": {
          "deployed": "{{ steps.deploy_model.outputs.success | default(false) }}",
          "healthy": "{{ steps.health_check.outputs.healthy | default(false) }}",
          "load_test_passed": "{{ steps.load_test.outputs.success | default('skipped') }}",
          "rolled_back": "{{ steps.rollback.outputs.rolled_back | default(false) }}"
        }
      }
    }
  ],
  "outputs": {
    "success": "{{ steps.update_registry.outputs.updated | default(false) }}",
    "endpoint_url": "{{ steps.deploy_model.outputs.endpoint_url if steps.update_registry.outputs.updated else none }}",
    "rolled_back": "{{ steps.rollback.outputs.rolled_back | default(false) }}",
    "simulation_results": "{{ steps.run_simulation.outputs }}"
  }
}
```

---

## Visual Representation

### DAG Visualization Key

```
┌─────────────────┐
│   Step Name     │    Regular step (action node)
│ [action: name]  │
└─────────────────┘

┌─────────────────┐
│   Step Name     │    Conditional step
│ condition: ...  │    (condition badge shown)
│ [action: name]  │
└─────────────────┘

┌─────────────────┐
│   For Each      │    Iteration compound node
│  ┌───────────┐  │    (internal loop visualized)
│  │ items[*]  │  │
│  │ → action  │  │
│  └───────────┘  │
└─────────────────┘

┌─────────────────┐
│   While         │    Loop compound node
│  ┌───────────┐  │    (polling/retry pattern)
│  │ condition │  │
│  │ → action  │  │
│  └───────────┘  │
└─────────────────┘

─────▶    Dependency edge (depends_on)

─ ─ ─▶    Conditional edge (may not execute)
```

### Sample 4 Visualization

```
┌────────────────┐   ┌─────────────────┐
│ Validate Model │   │ Validate Cluster│
└───────┬────────┘   └────────┬────────┘
        │                     │
        │            ┌────────▼────────┐
        │            │ Check Resources │
        │            └────────┬────────┘
        │                     │
        └────────┬────────────┘
                 │
        ┌────────▼────────┐
        │ Run Simulation  │
        └────────┬────────┘
                 │
        ┌────────▼────────┐
        │Prepare Deployment│
        └────────┬────────┘
                 │
        ┌────────▼────────┐
        │ Backup Existing │  condition: auto_rollback
        └────────┬────────┘
                 │
        ┌────────▼────────┐
        │  Deploy Model   │  retry: 2 attempts
        └────────┬────────┘
                 │
        ┌────────▼────────┐
        │  Health Check   │  condition: deploy success
        └────────┬────────┘
                 │
        ┌────────▼────────┐
        │   Load Test     │  condition: healthy & run_load_test
        └────────┬────────┘
                 │
    ┌────────────┼────────────┐
    │            │            │
┌───▼───┐  ┌─────▼─────┐  ┌───▼────┐
│Rollback│  │Update Reg │  │ (skip) │
│cond:   │  │cond:      │  │        │
│failed  │  │success    │  │        │
└───┬────┘  └─────┬─────┘  └────────┘
    │             │
    └──────┬──────┘
           │
    ┌──────▼──────┐
    │   Notify    │
    └─────────────┘
```

---

## Action Handlers Reference

### Built-in Actions

| Action | Description | Outputs |
|--------|-------------|---------|
| `log` | Log a message | `logged: bool` |
| `transform` | Transform data | `result: any` |
| `aggregate` | Combine multiple inputs | `combined: object` |
| `conditional` | Evaluate condition | `branch: string` |
| `delay` | Wait for duration | `waited_seconds: int` |
| `set_output` | Set pipeline outputs | `outputs: object` |
| `http_request` | Make HTTP call | `response: object` |

### Control Flow Actions

| Action | Description | Outputs |
|--------|-------------|---------|
| `for_each` | Iterate over list | `results: array` |
| `while` | Loop until condition | `result: any, iterations: int` |
| `switch` | Multi-way branch | `branch: string, result: any` |

### Platform Actions

| Action | Description | Service |
|--------|-------------|---------|
| `deploy_model` | Deploy ML model | budcluster |
| `run_simulation` | Performance simulation | budsim |
| `validate_cluster` | Check cluster health | budcluster |
| `notify` | Send notification | budnotify |

---

## Best Practices

1. **Use meaningful step IDs**: Use descriptive, snake_case IDs like `validate_input`, `process_data`

2. **Keep conditions simple**: Complex logic should be in action handlers, not conditions

3. **Handle failures gracefully**: Use `on_failure: continue` for non-critical steps

4. **Limit parallel steps**: Set `max_parallel_steps` based on resource constraints

5. **Use parameters for flexibility**: Externalize configuration as pipeline parameters

6. **Document outputs**: List expected outputs in step definitions

7. **Test conditions**: Ensure conditional branches cover all cases (including defaults)
