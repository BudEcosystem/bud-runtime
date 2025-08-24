# Simple Audit Logging Guide

## Overview

This guide documents the simple, direct audit logging approach for the BudApp service. Instead of using complex middleware and decorators, this approach gives full control to the resource APIs to decide what needs to be audited based on their context and business logic.

## Key Principle

**Control at the source**: The resource APIs that have full context about the operation decide:
- What to log
- When to log it
- What details to include
- Whether the operation succeeded or failed

## Basic Usage

### Import the Function

```python
from budapp.audit_ops import log_audit
from budapp.commons.constants import AuditActionEnum, AuditResourceTypeEnum
```

### Simple Synchronous Logging

```python
def create_project(session, project_data, current_user_id, request):
    # Create the project
    project = crud.create_project(project_data)

    # Log the audit entry with full control over what gets logged
    log_audit(
        session=session,
        action=AuditActionEnum.CREATE,
        resource_type=AuditResourceTypeEnum.PROJECT,
        resource_id=project.id,
        user_id=current_user_id,
        details={
            "project_name": project.name,
            "project_type": project.type,
            "team_size": len(project.members),
            "created_with_template": project.template_id is not None
        },
        request=request  # Optional - extracts IP and user agent
    )

    return project
```

### Background Logging (Non-blocking)

For performance-critical operations, use background tasks:

```python
from fastapi import BackgroundTasks
from budapp.audit_ops import log_audit_async

async def create_endpoint(
    session: Session,
    endpoint_data: dict,
    current_user_id: UUID,
    request: Request,
    background_tasks: BackgroundTasks
):
    # Create endpoint
    endpoint = await crud.create_endpoint(endpoint_data)

    # Log audit in background (non-blocking)
    background_tasks.add_task(
        log_audit_async,
        session=session,
        action=AuditActionEnum.CREATE,
        resource_type=AuditResourceTypeEnum.ENDPOINT,
        resource_id=endpoint.id,
        user_id=current_user_id,
        details={"endpoint_name": endpoint.name, "model": endpoint.model_id},
        request=request
    )

    return endpoint
```

## Common Patterns

### Authentication Events

```python
# Failed login
if not db_user:
    log_audit(
        session=session,
        action=AuditActionEnum.LOGIN_FAILED,
        resource_type=AuditResourceTypeEnum.USER,
        details={"email": email, "reason": "Email not registered"},
        request=request,
        success=False
    )
    raise ClientException("This email is not registered")

# Successful login
log_audit(
    session=session,
    action=AuditActionEnum.LOGIN,
    resource_type=AuditResourceTypeEnum.USER,
    resource_id=user.id,
    user_id=user.id,
    details={
        "email": user.email,
        "tenant": tenant.name,
        "first_login": user.first_login,
        "mfa_used": user.mfa_enabled
    },
    request=request,
    success=True
)
```

### Update Operations

```python
def update_model(session, model_id, updates, current_user_id, request):
    # Get current state
    model = crud.get_model(model_id)
    previous_state = {
        "name": model.name,
        "version": model.version,
        "status": model.status
    }

    # Apply updates
    updated_model = crud.update_model(model_id, updates)

    # Log with before/after states
    log_audit(
        session=session,
        action=AuditActionEnum.UPDATE,
        resource_type=AuditResourceTypeEnum.MODEL,
        resource_id=model_id,
        user_id=current_user_id,
        previous_state=previous_state,
        new_state={
            "name": updated_model.name,
            "version": updated_model.version,
            "status": updated_model.status
        },
        details={"fields_updated": list(updates.keys())},
        request=request
    )

    return updated_model
```

### Delete Operations

```python
def delete_cluster(session, cluster_id, current_user_id, request):
    # Get cluster details before deletion
    cluster = crud.get_cluster(cluster_id)
    cluster_info = {
        "name": cluster.name,
        "provider": cluster.provider,
        "active_deployments": cluster.deployment_count
    }

    # Perform deletion
    crud.delete_cluster(cluster_id)

    # Log deletion with context
    log_audit(
        session=session,
        action=AuditActionEnum.DELETE,
        resource_type=AuditResourceTypeEnum.CLUSTER,
        resource_id=cluster_id,
        user_id=current_user_id,
        details={
            **cluster_info,
            "reason": "Decommissioned",
            "cascaded_deletions": cluster.deployment_count > 0
        },
        request=request
    )
```

### Permission Changes

```python
def add_project_member(session, project_id, new_member_id, role, current_user_id, request):
    # Add member
    crud.add_project_member(project_id, new_member_id, role)

    # Log permission change
    log_audit(
        session=session,
        action=AuditActionEnum.PERMISSION_CHANGED,
        resource_type=AuditResourceTypeEnum.PROJECT,
        resource_id=project_id,
        user_id=current_user_id,
        details={
            "operation": "add_member",
            "target_user_id": str(new_member_id),
            "role_assigned": role,
            "permissions": get_role_permissions(role)
        },
        request=request
    )
```

### Workflow Events

```python
def start_deployment_workflow(session, workflow_id, config, current_user_id, request):
    # Start workflow
    workflow = workflow_service.start(workflow_id, config)

    # Log workflow start
    log_audit(
        session=session,
        action=AuditActionEnum.WORKFLOW_STARTED,
        resource_type=AuditResourceTypeEnum.WORKFLOW,
        resource_id=workflow_id,
        user_id=current_user_id,
        details={
            "workflow_type": "DEPLOYMENT",
            "target_cluster": config.get("cluster_id"),
            "model": config.get("model_id"),
            "estimated_duration": "15 minutes"
        },
        request=request
    )

    return workflow
```

## Function Parameters

### Required Parameters

- `session`: Database session for audit logging
- `action`: The action being performed (from `AuditActionEnum`)
- `resource_type`: The type of resource (from `AuditResourceTypeEnum`)

### Optional Parameters

- `resource_id`: UUID of the resource being acted upon
- `user_id`: UUID of the user performing the action
- `details`: Dictionary with additional context (automatically sanitized)
- `request`: FastAPI Request object (for IP and user agent extraction)
- `previous_state`: Previous state for update operations
- `new_state`: New state for update operations
- `success`: Whether the operation succeeded (default: True)

## Available Actions

```python
class AuditActionEnum(str, Enum):
    # CRUD Operations
    CREATE = "CREATE"
    READ = "READ"
    UPDATE = "UPDATE"
    DELETE = "DELETE"

    # Authentication
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    LOGIN_FAILED = "LOGIN_FAILED"
    TOKEN_REFRESH = "TOKEN_REFRESH"
    PASSWORD_CHANGE = "PASSWORD_CHANGE"
    PASSWORD_RESET = "PASSWORD_RESET"

    # Access Control
    ACCESS_GRANTED = "ACCESS_GRANTED"
    ACCESS_DENIED = "ACCESS_DENIED"
    PERMISSION_CHANGED = "PERMISSION_CHANGED"
    ROLE_ASSIGNED = "ROLE_ASSIGNED"
    ROLE_REMOVED = "ROLE_REMOVED"

    # Model/Endpoint Operations
    MODEL_DEPLOYED = "MODEL_DEPLOYED"
    MODEL_UNDEPLOYED = "MODEL_UNDEPLOYED"
    ENDPOINT_PUBLISHED = "ENDPOINT_PUBLISHED"
    ENDPOINT_UNPUBLISHED = "ENDPOINT_UNPUBLISHED"

    # Workflows
    WORKFLOW_STARTED = "WORKFLOW_STARTED"
    WORKFLOW_COMPLETED = "WORKFLOW_COMPLETED"
    WORKFLOW_FAILED = "WORKFLOW_FAILED"

    # System
    CONFIG_CHANGED = "CONFIG_CHANGED"
    SYSTEM_ERROR = "SYSTEM_ERROR"
```

## Available Resource Types

```python
class AuditResourceTypeEnum(str, Enum):
    USER = "USER"
    PROJECT = "PROJECT"
    MODEL = "MODEL"
    ENDPOINT = "ENDPOINT"
    DEPLOYMENT = "DEPLOYMENT"
    DATASET = "DATASET"
    CLUSTER = "CLUSTER"
    WORKFLOW = "WORKFLOW"
    API_KEY = "API_KEY"
    BILLING = "BILLING"
    SYSTEM = "SYSTEM"
    # ... and more
```

## Best Practices

### 1. Log at the Right Level

Log where you have the most context:
```python
# Good - Service layer has full context
def project_service.create_project(data, user_id):
    project = crud.create_project(data)
    log_audit(...)  # Service knows all business logic

# Less ideal - Route layer has limited context
@router.post("/projects")
def create_project_route():
    result = service.create_project()
    log_audit(...)  # Route doesn't know internal logic
```

### 2. Include Meaningful Details

```python
# Good - Provides context
details={
    "project_name": project.name,
    "team_size": len(project.members),
    "budget": project.budget,
    "department": project.department
}

# Less helpful
details={"id": project.id}
```

### 3. Handle Failures Gracefully

The audit function never throws exceptions:
```python
# This is safe - audit failures won't break your operation
log_audit(session, action, resource_type, ...)
return result  # Will return even if audit fails
```

### 4. Use Background Tasks for Performance

For high-frequency operations:
```python
# Use background tasks
background_tasks.add_task(
    log_audit_async,
    session, action, resource_type, ...
)
```

### 5. Capture Both Success and Failure

```python
try:
    result = perform_operation()
    log_audit(..., success=True, details={"result": "completed"})
    return result
except Exception as e:
    log_audit(..., success=False, details={"error": str(e)})
    raise
```

## Security Features

### Automatic Sensitive Data Masking

The following fields are automatically redacted:
- `password`, `secret`, `token`, `key`, `api_key`
- `credit_card`, `ssn`, `pin`
- Any field containing these substrings

```python
# Input
details = {
    "username": "john",
    "password": "secret123",
    "api_key": "sk-123456"
}

# Stored as
{
    "username": "john",
    "password": "***REDACTED***",
    "api_key": "***REDACTED***"
}
```

### IP Address Extraction

When `request` is provided:
- Handles `X-Forwarded-For` for proxied requests
- Falls back to direct client IP
- Stores first IP in forwarding chain

## Querying Audit Logs

### Via API (Admin only)

```python
GET /audit/records?user_id=<uuid>&action=CREATE&resource_type=PROJECT&resource_id=<uuid>
GET /audit/records/<audit_id>
```

### Direct Service Access

```python
from budapp.audit_ops import AuditService

audit_service = AuditService(session)

# Get user's audit trail
records = audit_service.get_user_audit_trail(user_id)

# Get resource history
history = audit_service.get_resource_audit_trail(
    resource_type=AuditResourceTypeEnum.PROJECT,
    resource_id=project_id
)

# Search with filters
results = audit_service.get_audit_records(
    action=AuditActionEnum.DELETE,
    start_date=datetime.now() - timedelta(days=7)
)
```

## Migration from Complex Approach

If migrating from decorator/middleware approach:

1. **Remove decorators**: Replace `@audit_event` with direct `log_audit()` calls
2. **Remove middleware**: No need for request context middleware
3. **Add explicit calls**: Add `log_audit()` where you have business context
4. **Pass request**: Include request parameter for IP tracking

## Performance Considerations

- **Synchronous calls**: Add ~2-3ms overhead
- **Background calls**: No impact on response time
- **Batch operations**: Consider aggregating for bulk operations
- **High-frequency**: Use background tasks or sampling

## Summary

The simple audit logging approach provides:
- ✅ **Full control** - You decide what and when to log
- ✅ **Clear code** - Explicit audit calls where they happen
- ✅ **Better context** - Log with complete business knowledge
- ✅ **Flexibility** - Adapt logging to specific needs
- ✅ **Simplicity** - No complex decorators or middleware
- ✅ **Reliability** - Failures don't break operations

Use `log_audit()` directly in your service methods where you have the most context about what's happening and what's important to track.
