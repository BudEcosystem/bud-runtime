# API Contract Changes: budworkflow → budpipeline

**Feature**: [spec.md](../spec.md) | [plan.md](../plan.md)
**Date**: 2026-01-15

---

## Overview

This document details all API endpoint changes resulting from the budworkflow → budpipeline rename. All endpoints are accessed via the budapp service, which proxies requests to the pipeline service.

**Base URL**: `http://localhost:9081/api/v1` (development)

**Breaking Change**: All `/budworkflow` endpoints will be removed and replaced with `/budpipeline` endpoints. No backward compatibility layer.

---

## Endpoint Mappings

| Old Endpoint | New Endpoint | Method | Description |
|--------------|--------------|--------|-------------|
| `/budworkflow/validate` | `/budpipeline/validate` | POST | Validate pipeline DAG structure |
| `/budworkflow` | `/budpipeline` | POST | Create new pipeline |
| `/budworkflow` | `/budpipeline` | GET | List all pipelines |
| `/budworkflow/{workflow_id}` | `/budpipeline/{pipeline_id}` | GET | Get pipeline by ID |
| `/budworkflow/{workflow_id}` | `/budpipeline/{pipeline_id}` | PUT | Update existing pipeline |
| `/budworkflow/{workflow_id}` | `/budpipeline/{pipeline_id}` | DELETE | Delete pipeline |
| `/budworkflow/{workflow_id}/execute` | `/budpipeline/{pipeline_id}/execute` | POST | Execute pipeline |
| `/budworkflow/executions` | `/budpipeline/executions` | GET | List all executions |
| `/budworkflow/executions/{execution_id}` | `/budpipeline/executions/{execution_id}` | GET | Get execution details |
| `/budworkflow/schedules` | `/budpipeline/schedules` | GET | List all schedules |
| `/budworkflow/schedules` | `/budpipeline/schedules` | POST | Create schedule |
| `/budworkflow/schedules/{schedule_id}` | `/budpipeline/schedules/{schedule_id}` | GET | Get schedule by ID |
| `/budworkflow/schedules/{schedule_id}` | `/budpipeline/schedules/{schedule_id}` | PUT | Update schedule |
| `/budworkflow/schedules/{schedule_id}` | `/budpipeline/schedules/{schedule_id}` | DELETE | Delete schedule |
| `/budworkflow/schedules/{schedule_id}/pause` | `/budpipeline/schedules/{schedule_id}/pause` | POST | Pause schedule |
| `/budworkflow/schedules/{schedule_id}/resume` | `/budpipeline/schedules/{schedule_id}/resume` | POST | Resume schedule |
| `/budworkflow/schedules/{schedule_id}/trigger` | `/budpipeline/schedules/{schedule_id}/trigger` | POST | Manually trigger schedule |
| `/budworkflow/webhooks` | `/budpipeline/webhooks` | GET | List all webhooks |
| `/budworkflow/webhooks` | `/budpipeline/webhooks` | POST | Create webhook |
| `/budworkflow/webhooks/{webhook_id}` | `/budpipeline/webhooks/{webhook_id}` | DELETE | Delete webhook |
| `/budworkflow/webhooks/{webhook_id}/rotate-secret` | `/budpipeline/webhooks/{webhook_id}/rotate-secret` | POST | Rotate webhook secret |
| `/budworkflow/event-triggers` | `/budpipeline/event-triggers` | GET | List event triggers |
| `/budworkflow/event-triggers` | `/budpipeline/event-triggers` | POST | Create event trigger |
| `/budworkflow/event-triggers/{trigger_id}` | `/budpipeline/event-triggers/{trigger_id}` | DELETE | Delete event trigger |

**Total Endpoints Affected**: 22

---

## Request/Response Schemas (Unchanged)

All request and response body schemas remain identical. Only the endpoint paths change.

### Example: Create Pipeline

**Old Endpoint**: `POST /api/v1/budworkflow`
**New Endpoint**: `POST /api/v1/budpipeline`

**Request Body** (unchanged):
```json
{
  "name": "Example Pipeline",
  "description": "Process user data",
  "dag": {
    "nodes": [
      {"id": "start", "type": "start"},
      {"id": "process", "type": "action", "handler": "process_data"},
      {"id": "end", "type": "end"}
    ],
    "edges": [
      {"from": "start", "to": "process"},
      {"from": "process", "to": "end"}
    ]
  },
  "parameters": {
    "timeout": 300
  }
}
```

**Response** (unchanged):
```json
{
  "id": "pipeline-001",
  "name": "Example Pipeline",
  "description": "Process user data",
  "status": "created",
  "created_at": "2026-01-15T10:00:00Z",
  "created_by": "user-123"
}
```

---

## Authentication & Authorization (Unchanged)

All endpoints continue to require:
- **Authentication**: Bearer token via Keycloak
- **Authorization**: RBAC permissions unchanged
- **Multi-tenancy**: Project-level isolation maintained

No changes to security model.

---

## HTTP Status Codes (Unchanged)

All endpoints maintain existing status code patterns:
- `200 OK`: Successful GET/PUT operations
- `201 Created`: Successful POST creation
- `204 No Content`: Successful DELETE
- `400 Bad Request`: Validation errors
- `401 Unauthorized`: Missing or invalid auth token
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource doesn't exist
- `409 Conflict`: Duplicate resource
- `500 Internal Server Error`: Server-side error

---

## Error Response Format (Unchanged)

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid DAG structure",
    "details": {
      "field": "dag.nodes",
      "reason": "Missing required start node"
    }
  }
}
```

---

## Pagination (Unchanged)

List endpoints continue to support:
```
GET /api/v1/budpipeline?page=1&limit=20&sort=created_at&order=desc
```

Response format:
```json
{
  "data": [ /* array of items */ ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 150,
    "total_pages": 8
  }
}
```

---

## Filtering & Search (Unchanged)

```
GET /api/v1/budpipeline?status=active&created_by=user-123&search=data
```

---

## Rate Limiting (Unchanged)

All endpoints maintain existing rate limits:
- 100 requests per minute per user
- 1000 requests per minute per project

---

## WebSocket Events (Unchanged)

Real-time execution updates continue via Socket.IO:
```javascript
// Client subscribes to execution events
socket.emit('subscribe', { execution_id: 'exec-001' });

// Server emits status updates
socket.on('execution:update', (data) => {
  // { execution_id, status, progress, logs }
});
```

No changes to event names or payload structure.

---

## Migration Guide for External Consumers

### Step 1: Update Base URL
```javascript
// Before
const BASE_URL = 'https://api.bud.ai/api/v1/budworkflow';

// After
const BASE_URL = 'https://api.bud.ai/api/v1/budpipeline';
```

### Step 2: Update Route Configurations
```python
# Python example
PIPELINE_API = f"{BASE_URL}/budpipeline"  # Change from /budworkflow

# JavaScript example
const ENDPOINTS = {
  list: '/api/v1/budpipeline',  // Change from /budworkflow
  create: '/api/v1/budpipeline',
  detail: (id) => `/api/v1/budpipeline/${id}`,
  execute: (id) => `/api/v1/budpipeline/${id}/execute`,
};
```

### Step 3: Update API Client Libraries
```typescript
// Before
import { BudWorkflowClient } from '@bud/sdk';
const client = new BudWorkflowClient();

// After
import { BudPipelineClient } from '@bud/sdk';
const client = new BudPipelineClient();
```

### Step 4: Update Documentation & Environment Configs
- API documentation
- OpenAPI/Swagger specs
- Environment variable files (`.env`, `.env.production`)
- CI/CD configuration
- Postman/Insomnia collections

---

## Testing Checklist

After migration, verify each endpoint:

### Core CRUD Operations
- [ ] `POST /budpipeline` - Create pipeline returns 201
- [ ] `GET /budpipeline` - List pipelines returns 200 with data
- [ ] `GET /budpipeline/{id}` - Get pipeline returns 200
- [ ] `PUT /budpipeline/{id}` - Update pipeline returns 200
- [ ] `DELETE /budpipeline/{id}` - Delete pipeline returns 204

### Execution Operations
- [ ] `POST /budpipeline/{id}/execute` - Trigger execution returns 202
- [ ] `GET /budpipeline/executions` - List executions returns 200
- [ ] `GET /budpipeline/executions/{id}` - Get execution details returns 200
- [ ] Execution completes successfully
- [ ] WebSocket events received for execution progress

### Schedule Operations
- [ ] `POST /budpipeline/schedules` - Create schedule returns 201
- [ ] `GET /budpipeline/schedules` - List schedules returns 200
- [ ] `PUT /budpipeline/schedules/{id}` - Update schedule returns 200
- [ ] `POST /budpipeline/schedules/{id}/pause` - Pause works
- [ ] `POST /budpipeline/schedules/{id}/resume` - Resume works
- [ ] `DELETE /budpipeline/schedules/{id}` - Delete returns 204

### Webhook Operations
- [ ] `POST /budpipeline/webhooks` - Create webhook returns 201
- [ ] `GET /budpipeline/webhooks` - List webhooks returns 200
- [ ] Webhook triggers pipeline execution
- [ ] `POST /budpipeline/webhooks/{id}/rotate-secret` - Rotate works
- [ ] `DELETE /budpipeline/webhooks/{id}` - Delete returns 204

### Event Trigger Operations
- [ ] `POST /budpipeline/event-triggers` - Create trigger returns 201
- [ ] `GET /budpipeline/event-triggers` - List triggers returns 200
- [ ] Event pub/sub triggers pipeline execution
- [ ] `DELETE /budpipeline/event-triggers/{id}` - Delete returns 204

### Error Handling
- [ ] 404 for non-existent pipeline ID
- [ ] 400 for invalid DAG structure
- [ ] 401 for missing authentication
- [ ] 403 for insufficient permissions
- [ ] 409 for duplicate resource creation

---

## OpenAPI Specification Changes

**File**: `/services/budapp/openapi.yaml` (if exists)

Update all occurrences:
```yaml
# Before
paths:
  /api/v1/budworkflow:
    get:
      summary: List workflows
      tags: [budworkflow]

# After
paths:
  /api/v1/budpipeline:
    get:
      summary: List pipelines
      tags: [budpipeline]
```

---

## FastAPI Auto-Generated Docs

**URL Changes**:
- Before: `http://localhost:9081/docs#/budworkflow`
- After: `http://localhost:9081/docs#/budpipeline`

**Tag Rename**:
- Tags in FastAPI router update from `["budworkflow"]` to `["budpipeline"]`
- Documentation groups remain organized by tag

---

## Deprecation Notice Template

For external consumers, send this notice 7 days before deployment:

```
Subject: [ACTION REQUIRED] API Breaking Change - budworkflow → budpipeline

Dear API Consumer,

On [DEPLOYMENT_DATE], we will rename the budworkflow service to budpipeline.
This is a BREAKING CHANGE requiring updates to your integration.

WHAT'S CHANGING:
- All API endpoints: /budworkflow → /budpipeline
- Dapr service invocation: app-id "budworkflow" → "budpipeline"
- Pub/sub topics: "budworkflowEvents" → "budpipelineEvents"

WHAT'S NOT CHANGING:
- Request/response formats
- Authentication methods
- Status codes
- WebSocket events

ACTION REQUIRED:
1. Update all API calls to use /budpipeline endpoints
2. Update environment variables and configuration
3. Test integration in staging environment

TIMELINE:
- Today: Notification sent
- [7 days from now]: Deployment to production
- Old /budworkflow endpoints will be removed (no backward compatibility)

SUPPORT:
Contact us at support@bud.ai for migration assistance.
```

---

## Summary

**Total Endpoints**: 22
**Breaking Changes**: All endpoints
**Request/Response**: No changes
**Authentication**: No changes
**Migration Effort**: Low (simple find/replace in consumer code)
**Risk Level**: Medium (requires coordinated external consumer updates)
