# BudPipeline API Reference

This document provides comprehensive API documentation for integrating with the BudPipeline service.

## Overview

BudPipeline is a FastAPI-based microservice for pipeline orchestration. It provides:
- **Pipeline Management**: Create, update, delete, and list DAG-based pipelines
- **Execution Management**: Start executions, track progress, and query historical runs
- **Scheduling**: Cron-based, interval-based, and one-time schedules
- **Webhooks**: HTTP-triggered pipeline executions
- **Event Triggers**: Event-driven pipeline triggers
- **Actions API**: Discover available pipeline actions

## Base URL

```
http://<host>:8010
```

When accessed via the budapp proxy (recommended):
```
http://<host>:9081/budpipeline
```

## Authentication

### Direct Access (Service-to-Service)
BudPipeline uses Dapr service invocation. Include the Dapr API token:

```http
dapr-api-token: <your-dapr-api-token>
```

### Via BudApp Proxy
Use JWT authentication through budapp. The proxy forwards requests to budpipeline.

### User Isolation
Include the `X-User-ID` header to scope pipelines to a specific user:

```http
X-User-ID: <user-uuid>
```

Without this header, all pipelines are visible (backwards compatible).

---

## Pipeline Management

### Create Pipeline

Creates a new pipeline from a DAG definition.

```http
POST /pipelines
Content-Type: application/json
X-User-ID: <user-uuid>  # Optional: for user isolation
```

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `dag` | object | Yes | The DAG definition |
| `name` | string | No | Optional pipeline name override |
| `user_id` | string | No | User ID for ownership (overrides header) |
| `system_owned` | boolean | No | If true, visible to all users (default: false) |

**Example Request:**

```json
{
  "dag": {
    "name": "my-pipeline",
    "version": "1.0",
    "steps": [
      {
        "id": "step1",
        "name": "Log Message",
        "action": "log",
        "params": {
          "message": "Hello, World!"
        }
      },
      {
        "id": "step2",
        "name": "Second Step",
        "action": "log",
        "params": {
          "message": "Step 2"
        },
        "depends_on": ["step1"]
      }
    ]
  },
  "name": "My First Pipeline"
}
```

**Response:** `201 Created`

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "My First Pipeline",
  "version": "1.0",
  "status": "draft",
  "created_at": "2024-01-15T10:30:00Z",
  "step_count": 2,
  "user_id": "11111111-1111-1111-1111-111111111111",
  "system_owned": false
}
```

**Error Responses:**

| Status | Description |
|--------|-------------|
| `400 Bad Request` | Invalid DAG definition |
| `500 Internal Server Error` | Server error |

---

### List Pipelines

Lists all pipelines accessible to the user.

```http
GET /pipelines?include_system=false
X-User-ID: <user-uuid>  # Optional: for user isolation
```

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `include_system` | boolean | `false` | Include system-owned pipelines |

**Response:** `200 OK`

```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "My Pipeline",
    "version": "1.0",
    "status": "active",
    "created_at": "2024-01-15T10:30:00Z",
    "step_count": 3,
    "user_id": "11111111-1111-1111-1111-111111111111",
    "system_owned": false
  }
]
```

---

### Get Pipeline

Retrieves a pipeline by ID including the full DAG definition.

```http
GET /pipelines/{pipeline_id}
X-User-ID: <user-uuid>  # Optional: for user isolation
```

**Response:** `200 OK`

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "My Pipeline",
  "version": "1.0",
  "status": "active",
  "dag": {
    "name": "my-pipeline",
    "version": "1.0",
    "steps": [...]
  },
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z",
  "step_count": 3,
  "user_id": "11111111-1111-1111-1111-111111111111",
  "system_owned": false
}
```

**Error Responses:**

| Status | Description |
|--------|-------------|
| `404 Not Found` | Pipeline not found or not accessible |

---

### Update Pipeline

Updates an existing pipeline's DAG definition.

```http
PUT /pipelines/{pipeline_id}
Content-Type: application/json
X-User-ID: <user-uuid>
```

**Request Body:** Same as Create Pipeline

**Response:** `200 OK` (same as Create Pipeline response)

**Error Responses:**

| Status | Description |
|--------|-------------|
| `400 Bad Request` | Invalid DAG definition |
| `404 Not Found` | Pipeline not found |
| `409 Conflict` | Concurrent modification detected |

---

### Delete Pipeline

Deletes a pipeline.

```http
DELETE /pipelines/{pipeline_id}
X-User-ID: <user-uuid>
```

**Response:** `204 No Content`

**Error Responses:**

| Status | Description |
|--------|-------------|
| `404 Not Found` | Pipeline not found |

---

### Validate DAG

Validates a DAG definition without creating a pipeline.

```http
POST /validate
Content-Type: application/json
```

**Request Body:**

```json
{
  "dag": {
    "name": "test-pipeline",
    "version": "1.0",
    "steps": [...]
  }
}
```

**Response:** `200 OK`

```json
{
  "valid": true,
  "errors": [],
  "warnings": ["Step 'step1' has no depends_on - will run first"],
  "step_count": 3,
  "has_cycles": false
}
```

---

## Execution Management

### Create Execution

Starts a new execution of a saved pipeline.

```http
POST /executions
Content-Type: application/json
```

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `workflow_id` | string | Yes | Pipeline ID to execute |
| `params` | object | No | Input parameters |
| `callback_topics` | array | No | Dapr pub/sub topics for progress events |
| `user_id` | string | No | User ID for tracking |
| `initiator` | string | No | Initiator identifier (default: "api") |

**Example Request:**

```json
{
  "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
  "params": {
    "input_data": "value",
    "model_id": "model-123"
  },
  "callback_topics": ["my-progress-topic"],
  "initiator": "my-service"
}
```

**Response:** `201 Created`

```json
{
  "execution_id": "660e8400-e29b-41d4-a716-446655440001",
  "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
  "workflow_name": "My Pipeline",
  "status": "running",
  "started_at": "2024-01-15T10:35:00Z",
  "completed_at": null,
  "params": {
    "input_data": "value",
    "model_id": "model-123"
  },
  "outputs": {},
  "error": null
}
```

---

### Run Ephemeral Execution

Executes a pipeline definition without saving it. Useful for one-off or testing.

```http
POST /executions/run
Content-Type: application/json
```

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `pipeline_definition` | object | Yes | Complete DAG definition |
| `params` | object | No | Input parameters |
| `user_id` | string | No | User ID for tracking |
| `initiator` | string | No | Initiator identifier |
| `callback_topics` | array | No | Progress event topics |

**Example Request:**

```json
{
  "pipeline_definition": {
    "name": "temp-pipeline",
    "version": "1.0",
    "steps": [
      {
        "id": "s1",
        "name": "Quick Test",
        "action": "log",
        "params": {
          "message": "Testing..."
        }
      }
    ]
  },
  "params": {
    "test_input": "value"
  }
}
```

**Response:** `201 Created` (same as Create Execution response)

---

### List Executions

Lists executions with filtering and pagination.

```http
GET /executions?page=1&page_size=20
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `start_date` | datetime | Filter by created_at >= start_date |
| `end_date` | datetime | Filter by created_at <= end_date |
| `status` | string | Filter by status (pending, running, completed, failed, cancelled) |
| `initiator` | string | Filter by initiator |
| `workflow_id` | UUID | Filter by pipeline ID |
| `page` | integer | Page number (default: 1) |
| `page_size` | integer | Items per page (1-100, default: 20) |

**Response:** `200 OK`

```json
{
  "executions": [
    {
      "id": "660e8400-e29b-41d4-a716-446655440001",
      "version": 2,
      "pipeline_definition": {...},
      "initiator": "api",
      "start_time": "2024-01-15T10:35:00Z",
      "end_time": "2024-01-15T10:36:00Z",
      "status": "completed",
      "progress_percentage": "100.00",
      "final_outputs": {"result": "success"},
      "error_info": null,
      "created_at": "2024-01-15T10:35:00Z",
      "updated_at": "2024-01-15T10:36:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total_count": 42,
    "total_pages": 3
  }
}
```

---

### Get Execution

Retrieves execution details.

```http
GET /executions/{execution_id}
X-Correlation-ID: <correlation-id>  # Optional: for tracing
```

**Response:** `200 OK`

```json
{
  "id": "660e8400-e29b-41d4-a716-446655440001",
  "version": 2,
  "pipeline_definition": {...},
  "initiator": "api",
  "start_time": "2024-01-15T10:35:00Z",
  "end_time": "2024-01-15T10:36:00Z",
  "status": "completed",
  "progress_percentage": "100.00",
  "final_outputs": {"result": "success"},
  "error_info": null,
  "created_at": "2024-01-15T10:35:00Z",
  "updated_at": "2024-01-15T10:36:00Z"
}
```

**Response Headers:**

| Header | Description |
|--------|-------------|
| `X-Correlation-ID` | Correlation ID for tracing |
| `X-Data-Staleness` | Present if serving from fallback cache |

---

### Get Execution Progress

Gets detailed progress with step information.

```http
GET /executions/{execution_id}/progress?detail=full&include_events=true&events_limit=20
```

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `detail` | string | `full` | Level of detail: `summary`, `steps`, or `full` |
| `include_events` | boolean | `true` | Include recent progress events |
| `events_limit` | integer | `20` | Max events to include (1-100) |

**Response:** `200 OK`

```json
{
  "execution": {
    "id": "660e8400-e29b-41d4-a716-446655440001",
    "status": "running",
    "progress_percentage": "45.00",
    ...
  },
  "steps": [
    {
      "id": "step-uuid-1",
      "execution_id": "660e8400-e29b-41d4-a716-446655440001",
      "step_id": "step1",
      "step_name": "First Step",
      "status": "completed",
      "start_time": "2024-01-15T10:35:01Z",
      "end_time": "2024-01-15T10:35:05Z",
      "progress_percentage": "100.00",
      "outputs": {"key": "value"},
      "error_message": null,
      "sequence_number": 1,
      "awaiting_event": false
    },
    {
      "id": "step-uuid-2",
      "step_id": "step2",
      "step_name": "Second Step",
      "status": "running",
      "progress_percentage": "40.00",
      "sequence_number": 2,
      "awaiting_event": true,
      "external_workflow_id": "external-123"
    }
  ],
  "recent_events": [
    {
      "id": "event-uuid",
      "execution_id": "660e8400-e29b-41d4-a716-446655440001",
      "event_type": "step_progress",
      "data": {"step_id": "step2", "progress": 40},
      "timestamp": "2024-01-15T10:35:30Z"
    }
  ],
  "aggregated_progress": {
    "overall_progress": "45.00",
    "eta_seconds": 120,
    "completed_steps": 1,
    "total_steps": 3,
    "current_step": "Second Step"
  }
}
```

---

### Get Execution Steps

Gets all steps for an execution.

```http
GET /executions/{execution_id}/steps
```

**Response:** `200 OK`

```json
{
  "steps": [
    {
      "id": "step-uuid",
      "execution_id": "execution-uuid",
      "step_id": "step1",
      "step_name": "First Step",
      "status": "completed",
      "progress_percentage": "100.00",
      "sequence_number": 1,
      ...
    }
  ]
}
```

---

### Get Execution Events

Gets progress events for an execution with filtering.

```http
GET /executions/{execution_id}/events?event_type=step_progress&limit=100&offset=0
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `event_type` | string | Filter by event type |
| `start_time` | datetime | Filter by timestamp >= start_time |
| `end_time` | datetime | Filter by timestamp <= end_time |
| `limit` | integer | Max events (1-1000, default: 100) |
| `offset` | integer | Events to skip (default: 0) |

**Response:** `200 OK`

```json
{
  "events": [
    {
      "id": "event-uuid",
      "execution_id": "execution-uuid",
      "event_type": "step_progress",
      "data": {...},
      "timestamp": "2024-01-15T10:35:30Z"
    }
  ],
  "total_count": 42,
  "limit": 100,
  "offset": 0
}
```

---

## Schedules

### Create Schedule

Creates a cron-based, interval-based, or one-time schedule.

```http
POST /schedules
Content-Type: application/json
```

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Schedule name |
| `workflow_id` | string | Yes | Pipeline to trigger |
| `schedule_type` | string | Yes | `cron`, `interval`, or `once` |
| `cron_expression` | string | Conditional | Cron expression (for type=cron) |
| `interval_seconds` | integer | Conditional | Interval in seconds (for type=interval) |
| `run_at` | datetime | Conditional | Run time (for type=once) |
| `params` | object | No | Parameters to pass to pipeline |
| `enabled` | boolean | No | Enable schedule (default: true) |
| `timezone` | string | No | Timezone (default: UTC) |

**Example Request (Cron):**

```json
{
  "name": "Daily Backup",
  "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
  "schedule_type": "cron",
  "cron_expression": "0 3 * * *",
  "params": {
    "backup_type": "full"
  },
  "timezone": "America/New_York"
}
```

**Response:** `201 Created`

```json
{
  "id": "schedule-uuid",
  "name": "Daily Backup",
  "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
  "schedule_type": "cron",
  "cron_expression": "0 3 * * *",
  "next_run": "2024-01-16T03:00:00Z",
  "last_run": null,
  "enabled": true,
  "status": "active",
  "created_at": "2024-01-15T10:30:00Z"
}
```

---

### List Schedules

```http
GET /schedules?workflow_id=<uuid>&enabled=true&status=active
```

---

### Get Schedule

```http
GET /schedules/{schedule_id}
```

---

### Update Schedule

```http
PUT /schedules/{schedule_id}
Content-Type: application/json
```

---

### Delete Schedule

```http
DELETE /schedules/{schedule_id}
```

**Response:** `204 No Content`

---

### Pause Schedule

```http
POST /schedules/{schedule_id}/pause
```

---

### Resume Schedule

```http
POST /schedules/{schedule_id}/resume
```

---

### Trigger Schedule Immediately

Manually triggers a schedule execution.

```http
POST /schedules/{schedule_id}/trigger
Content-Type: application/json
```

**Request Body (Optional):**

```json
{
  "override_param": "value"
}
```

---

### Preview Next Runs

```http
GET /schedules/{schedule_id}/next-runs?count=10
```

**Response:** `200 OK`

```json
{
  "schedule_id": "schedule-uuid",
  "next_runs": [
    "2024-01-16T03:00:00Z",
    "2024-01-17T03:00:00Z",
    "2024-01-18T03:00:00Z"
  ]
}
```

---

## Webhooks

### Create Webhook

```http
POST /webhooks
Content-Type: application/json
```

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Webhook name |
| `workflow_id` | string | Yes | Pipeline to trigger |
| `params` | object | No | Default parameters |
| `enabled` | boolean | No | Enable webhook (default: true) |
| `ip_whitelist` | array | No | Allowed IP addresses |
| `headers_to_include` | array | No | Request headers to pass as params |

**Response:** `201 Created`

```json
{
  "id": "webhook-uuid",
  "name": "GitHub Push",
  "workflow_id": "pipeline-uuid",
  "endpoint_url": "http://host:8010/trigger/webhook-uuid",
  "secret": "generated-secret-keep-safe",
  "enabled": true,
  "created_at": "2024-01-15T10:30:00Z"
}
```

> **Note:** The `secret` is only returned once. Store it securely.

---

### Trigger Webhook

```http
POST /trigger/{webhook_id}
Content-Type: application/json
X-Webhook-Secret: <webhook-secret>
```

**Request Body (Optional):**

```json
{
  "params": {
    "custom_param": "value"
  }
}
```

**Response:** `200 OK`

```json
{
  "execution_id": "execution-uuid",
  "workflow_id": "pipeline-uuid",
  "status": "running"
}
```

---

### Rotate Webhook Secret

```http
POST /webhooks/{webhook_id}/rotate-secret
```

---

## Event Triggers

### Create Event Trigger

```http
POST /event-triggers
Content-Type: application/json
```

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Trigger name |
| `workflow_id` | string | Yes | Pipeline to trigger |
| `event_type` | string | Yes | Event type to listen for |
| `filter` | object | No | Event filter conditions |
| `params` | object | No | Default parameters |
| `enabled` | boolean | No | Enable trigger (default: true) |

---

### List Supported Event Types

```http
GET /event-triggers/event-types
```

**Response:** `200 OK`

```json
[
  {"type": "model.added", "description": "Triggered when a model is added"},
  {"type": "cluster.ready", "description": "Triggered when cluster is ready"},
  {"type": "deployment.completed", "description": "Triggered when deployment completes"}
]
```

---

## Actions API

### List All Actions

Lists all available pipeline actions with metadata.

```http
GET /actions
```

**Response:** `200 OK`

```json
{
  "actions": [
    {
      "type": "log",
      "version": "1.0.0",
      "name": "Log",
      "description": "Log a message",
      "category": "Control Flow",
      "icon": "message",
      "color": "#8c8c8c",
      "params": [
        {
          "name": "message",
          "label": "Message",
          "type": "template",
          "description": "Message to log",
          "required": true
        },
        {
          "name": "level",
          "label": "Log Level",
          "type": "select",
          "required": false,
          "default": "info",
          "options": [
            {"value": "debug", "label": "Debug"},
            {"value": "info", "label": "Info"},
            {"value": "warning", "label": "Warning"},
            {"value": "error", "label": "Error"}
          ]
        }
      ],
      "outputs": [
        {
          "name": "logged_at",
          "type": "string",
          "description": "Timestamp when message was logged"
        }
      ],
      "executionMode": "sync",
      "idempotent": true,
      "requiredServices": [],
      "requiredPermissions": ["pipeline:execute"]
    }
  ],
  "categories": [
    {
      "name": "Control Flow",
      "icon": "git-branch",
      "actions": [...]
    },
    {
      "name": "Model",
      "icon": "cpu",
      "actions": [...]
    }
  ],
  "total": 15
}
```

---

### Get Action Details

```http
GET /actions/{action_type}
```

**Response:** `200 OK` (single action metadata)

---

### Validate Action Parameters

```http
POST /actions/validate
Content-Type: application/json
```

**Request Body:**

```json
{
  "action_type": "log",
  "params": {
    "message": "Hello"
  }
}
```

**Response:** `200 OK`

```json
{
  "valid": true,
  "errors": []
}
```

---

## DAG Structure

### Step Schema

```json
{
  "id": "unique-step-id",
  "name": "Human Readable Name",
  "action": "action_type",
  "params": {
    "param1": "value1",
    "param2": "{{ inputs.variable }}"
  },
  "depends_on": ["previous-step-id"],
  "condition": "{{ steps.prev.outputs.success == true }}",
  "retry": {
    "max_attempts": 3,
    "backoff_multiplier": 2
  },
  "timeout_seconds": 300
}
```

### Template Syntax

Parameters support Jinja2 templating:

```
{{ inputs.param_name }}        - Input parameters
{{ steps.step_id.outputs.key }} - Previous step outputs
{{ env.VAR_NAME }}              - Environment variables
```

### Conditional Execution

```json
{
  "id": "conditional-step",
  "action": "conditional",
  "params": {
    "branches": [
      {
        "condition": "{{ inputs.env == 'production' }}",
        "next_step": "prod-deploy"
      },
      {
        "condition": "{{ inputs.env == 'staging' }}",
        "next_step": "staging-deploy"
      }
    ],
    "default_step": "dev-deploy"
  }
}
```

---

## Status Enums

### Pipeline Status
- `draft` - Not yet active
- `active` - Ready for execution
- `archived` - No longer in use

### Execution Status
- `pending` - Queued for execution
- `running` - Currently executing
- `completed` - Successfully finished
- `failed` - Failed with error
- `cancelled` - Manually cancelled

### Step Status
- `pending` - Not yet started
- `running` - Currently executing
- `completed` - Successfully finished
- `failed` - Failed with error
- `skipped` - Skipped due to condition
- `cancelled` - Cancelled

---

## Error Responses

All errors follow this format:

```json
{
  "detail": {
    "error": {
      "code": "ERROR_CODE",
      "message": "Human readable message"
    },
    "correlation_id": "correlation-uuid"
  }
}
```

### Common Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `NOT_FOUND` | 404 | Resource not found |
| `VALIDATION_ERROR` | 400 | Invalid request data |
| `CONFLICT` | 409 | Concurrent modification |
| `UNAUTHORIZED` | 401 | Invalid credentials |
| `FORBIDDEN` | 403 | Insufficient permissions |

---

## Rate Limiting

Default rate limits:
- 100 requests/minute per client
- 1000 requests/minute globally

Rate limit headers:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1704067200
```

---

## Observability

### Correlation IDs

Include `X-Correlation-ID` header for request tracing:

```http
X-Correlation-ID: my-unique-correlation-id
```

The same ID is returned in responses and logged with all related operations.

### Resilience

When the database is unavailable, some endpoints serve cached data with:

```
X-Data-Staleness: stale
```

---

## Callback Topics (Real-time Updates)

When starting an execution with `callback_topics`, progress events are published via Dapr pub/sub:

```json
{
  "workflow_id": "execution-uuid",
  "params": {...},
  "callback_topics": ["my-progress-topic"]
}
```

### Event Types Published

| Event Type | Description |
|------------|-------------|
| `execution.started` | Execution began |
| `execution.progress` | Overall progress update |
| `step.started` | Step began |
| `step.progress` | Step progress update |
| `step.completed` | Step finished |
| `execution.completed` | Execution finished |

### Event Payload

```json
{
  "execution_id": "execution-uuid",
  "event_type": "step.completed",
  "correlation_id": "correlation-uuid",
  "data": {
    "step_id": "step1",
    "step_name": "First Step",
    "status": "completed",
    "outputs": {...}
  },
  "timestamp": "2024-01-15T10:35:30Z"
}
```

---

## SDK Examples

### Python (aiohttp)

```python
import aiohttp

async def create_pipeline(dag: dict, user_id: str):
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "http://localhost:8010/pipelines",
            json={"dag": dag},
            headers={
                "X-User-ID": user_id,
                "Content-Type": "application/json"
            }
        ) as resp:
            return await resp.json()

async def execute_pipeline(pipeline_id: str, params: dict):
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "http://localhost:8010/executions",
            json={
                "workflow_id": pipeline_id,
                "params": params
            }
        ) as resp:
            return await resp.json()
```

### cURL

```bash
# Create pipeline
curl -X POST http://localhost:8010/pipelines \
  -H "Content-Type: application/json" \
  -H "X-User-ID: 11111111-1111-1111-1111-111111111111" \
  -d '{
    "dag": {
      "name": "my-pipeline",
      "version": "1.0",
      "steps": [{"id": "s1", "name": "Log", "action": "log", "params": {"message": "Hello"}}]
    }
  }'

# Execute pipeline
curl -X POST http://localhost:8010/executions \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "pipeline-uuid",
    "params": {"key": "value"}
  }'

# Get execution progress
curl http://localhost:8010/executions/execution-uuid/progress?detail=full
```

---

## OpenAPI/Swagger

Interactive API documentation is available at:

```
http://<host>:8010/docs       # Swagger UI
http://<host>:8010/redoc      # ReDoc
http://<host>:8010/openapi.json  # OpenAPI spec
```
