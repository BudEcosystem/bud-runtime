# Data Model: Rename budworkflow to budpipeline

**Feature**: [spec.md](./spec.md) | [plan.md](./plan.md)
**Date**: 2026-01-15

---

## Overview

This rename operation does **NOT introduce any data model changes**. All existing entities, relationships, and data structures remain identical—only naming conventions change.

---

## Existing Entities (Unchanged)

The budworkflow/budpipeline service manages these entities. Their structure remains identical after the rename:

### Pipeline (formerly Workflow)

**Purpose**: Represents a DAG-based orchestration definition

**Key Attributes**:
- Unique identifier
- Name and description
- DAG structure (nodes, edges, dependencies)
- Configuration parameters
- Owner/creator information
- Creation and modification timestamps

**State**: Stored in Dapr state store (Valkey/Redis)

**Note**: After rename, new pipelines will be stored with "budpipeline" key prefix. Existing workflows with "budworkflow" prefix will be abandoned per user requirement.

---

### Pipeline Execution (formerly Workflow Execution)

**Purpose**: Represents a running or completed instance of a pipeline

**Key Attributes**:
- Execution identifier
- Parent pipeline reference
- Current status (pending, running, completed, failed)
- Start and end timestamps
- Step-by-step execution log
- Output results
- Error information (if failed)

**State**: Stored in Dapr state store

---

### Schedule

**Purpose**: Cron-based trigger for automated pipeline execution

**Key Attributes**:
- Schedule identifier
- Pipeline reference
- Cron expression
- Enabled/disabled status
- Next execution time
- Last execution results

**State**: Stored in Dapr state store

---

### Webhook

**Purpose**: HTTP endpoint that triggers pipeline execution from external events

**Key Attributes**:
- Webhook identifier
- Pipeline reference
- Secret token for authentication
- Endpoint URL
- Creation timestamp

**State**: Stored in Dapr state store

---

### Event Trigger

**Purpose**: Dapr pub/sub subscription that starts pipeline execution when events occur

**Key Attributes**:
- Trigger identifier
- Pipeline reference
- Subscribed topic name
- Event filter conditions
- Transformation rules

**State**: Configured via Dapr subscription components

---

## Data Migration Strategy

### User Decision: No Data Migration

Per user requirements (Question 1 response):
- Existing Dapr state with "budworkflow" key prefix will be **ignored**
- No migration scripts required
- New pipeline data will use "budpipeline" prefix
- This is a **clean cutover** with data loss accepted

### Implications

**What will be lost**:
- Existing pipeline definitions
- Historical execution records
- Active schedules
- Webhook configurations
- Event trigger mappings

**Rationale**: Simplifies migration, avoids complex state store key migration, aligns with breaking change approach.

### Alternative (If Data Preservation Required)

If future requirements dictate preserving data, use this approach:

```python
# Migration script to copy state store keys
import redis

r = redis.Redis(host='redis', port=6379)

for key in r.scan_iter(match="budworkflow||*"):
    value = r.get(key)
    new_key = key.replace(b"budworkflow||", b"budpipeline||")
    r.set(new_key, value)
    # Keep old key for backward compat
    # Or delete after verification: r.delete(key)
```

---

## Database Schema (No Changes)

The budworkflow/budpipeline service does NOT use PostgreSQL or ClickHouse. All state is stored in:
- **Dapr State Store**: Valkey/Redis key-value store
- **Kubernetes ConfigMaps**: Dapr component configurations
- **Helm Values**: Deployment configuration

No database migrations required.

---

## API Response Schemas (Unchanged)

All Pydantic schemas remain structurally identical. Only naming changes:

### Before
```python
class WorkflowSchema(BaseModel):
    workflow_id: str
    name: str
    dag: Dict[str, Any]
    # ...

class WorkflowExecutionSchema(BaseModel):
    execution_id: str
    workflow_id: str
    status: ExecutionStatus
    # ...
```

### After
```python
class PipelineSchema(BaseModel):
    pipeline_id: str  # Field name may change
    name: str
    dag: Dict[str, Any]
    # ...

class PipelineExecutionSchema(BaseModel):
    execution_id: str
    pipeline_id: str  # Field name may change
    status: ExecutionStatus
    # ...
```

**Decision Point**: Should internal field names like `workflow_id` → `pipeline_id` change?
- **Recommendation**: Keep field names unchanged for API compatibility
- **Rationale**: Minimizes external consumer impact, focuses rename on service/endpoint level only
- **Alternative**: Change field names if full semantic renaming desired (requires more extensive external coordination)

---

## State Store Key Patterns

### Current Pattern (before rename)
```
budworkflow||pipelines:{pipeline_id}
budworkflow||executions:{execution_id}
budworkflow||schedules:{schedule_id}
budworkflow||webhooks:{webhook_id}
```

### Future Pattern (after rename, with new data)
```
budpipeline||pipelines:{pipeline_id}
budpipeline||executions:{execution_id}
budpipeline||schedules:{schedule_id}
budpipeline||webhooks:{webhook_id}
```

### If Fixed Prefix Applied (alternative approach)
```
budworkflow||pipelines:{pipeline_id}  # Stays the same
budworkflow||executions:{execution_id}
budworkflow||schedules:{schedule_id}
budworkflow||webhooks:{webhook_id}
```
- Uses fixed `keyPrefix: "budworkflow"` in state store config
- Allows both old and new app-ids to access same data
- **Not chosen** per user requirement for clean cutover

---

## Summary

This rename operation is **purely cosmetic at the data layer**:
- No schema changes
- No entity relationship changes
- No new fields or attributes
- No database migrations

The only data-related impact is the **abandonment of existing state store data** per user requirements.
