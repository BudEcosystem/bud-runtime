# Audit Trail Module

## Overview

The `audit_ops` module provides comprehensive audit trail functionality for tracking all user actions and system events in the budapp service. This module is designed for compliance, security, and debugging purposes.

## Key Features

- **Immutable Audit Logs**: Audit records cannot be updated or deleted once created
- **Comprehensive Tracking**: Tracks user actions, resource changes, and system events
- **Admin Actions Support**: Includes `actioned_by` field to track when admins perform actions on behalf of users
- **State Tracking**: Captures previous and new states for resource changes
- **Performance Optimized**: Multiple indexes for efficient querying
- **Flexible Metadata**: JSONB fields for storing additional context

## Architecture

### Components

1. **Models** (`models.py`)
   - `AuditTrail`: SQLAlchemy model for audit records
   - Includes relationships to User table for both `user_id` and `actioned_by`
   - Event listener to prevent updates (immutability)

2. **Schemas** (`schemas.py`)
   - `AuditRecordCreate`: For creating new audit records
   - `AuditRecordEntry`: For API responses
   - `AuditRecordFilter`: For query filtering
   - `AuditRecordListResponse`: Paginated response format

3. **CRUD Operations** (`crud.py`)
   - `AuditTrailDataManager`: Database operations
   - Consolidated `get_audit_records` method with flexible filtering
   - Methods for creating records and getting summaries
   - No update/delete methods (immutability)

4. **Service Layer** (`services.py`)
   - `AuditService`: Business logic and helper methods
   - Specialized methods for different audit scenarios
   - Data sanitization for sensitive information

5. **API Routes** (`audit_routes.py`)
   - RESTful endpoints for querying audit logs
   - Admin-only access for most endpoints
   - Users can view their own audit records

## Database Schema

```sql
CREATE TABLE audit_trail (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES user(id) ON DELETE SET NULL,
    actioned_by UUID REFERENCES user(id) ON DELETE SET NULL,
    action VARCHAR(50) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id UUID,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    details JSONB,
    ip_address VARCHAR(45),
    previous_state JSONB,
    new_state JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    modified_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
```

### Indexes

- `(timestamp, user_id)` - User activity queries
- `(resource_type, resource_id)` - Resource history queries
- `(timestamp)` - Time-based queries
- `(action)` - Action type filtering
- Individual indexes on `user_id`, `actioned_by`, `resource_type`, `resource_id`

### Constraints

- Trigger to prevent UPDATE operations
- Foreign key constraints with SET NULL on delete

## Usage Examples

### Creating Audit Records

```python
from budapp.audit_ops.services import AuditService
from budapp.commons.constants import AuditActionEnum, AuditResourceTypeEnum

# Initialize service
service = AuditService(session)

# Audit a resource creation
service.audit_create(
    resource_type=AuditResourceTypeEnum.PROJECT,
    resource_id=project_id,
    resource_data=project_data,
    user_id=current_user.id,
    actioned_by=admin_user.id,  # If admin created on behalf
    ip_address=request.client.host
)

# Audit an update
service.audit_update(
    resource_type=AuditResourceTypeEnum.ENDPOINT,
    resource_id=endpoint_id,
    previous_data=old_endpoint_data,
    new_data=new_endpoint_data,
    user_id=current_user.id,
    ip_address=request.client.host
)

# Audit a deletion
service.audit_delete(
    resource_type=AuditResourceTypeEnum.MODEL,
    resource_id=model_id,
    resource_data=model_data,
    user_id=current_user.id,
    ip_address=request.client.host
)

# Audit authentication events
service.audit_authentication(
    action=AuditActionEnum.LOGIN,
    user_id=user.id,
    ip_address=request.client.host,
    success=True
)
```

### Querying Audit Records

```python
from budapp.audit_ops.schemas import AuditRecordFilter

# Query with filters using the consolidated method
filter_params = AuditRecordFilter(
    user_id=user_id,
    actioned_by=admin_id,  # Filter by who performed the action on behalf
    action=AuditActionEnum.UPDATE,
    resource_type=AuditResourceTypeEnum.CLUSTER,
    resource_id=cluster_id,
    start_date=start_date,
    end_date=end_date,
    ip_address=ip_address
)

records, total = service.get_audit_records(
    filter_params=filter_params,
    offset=0,
    limit=20
)

# Or use the data manager directly for more control
records, total = data_manager.get_audit_records(
    user_id=user_id,
    actioned_by=admin_id,
    action=AuditActionEnum.CREATE,
    resource_type=AuditResourceTypeEnum.PROJECT,
    resource_id=project_id,
    start_date=start_date,
    end_date=end_date,
    ip_address=ip_address,
    offset=0,
    limit=50,
    include_user=True
)

# Get audit summary
summary = service.get_audit_summary(
    start_date=start_date,
    end_date=end_date
)
```

## API Endpoints

### Query Endpoints (Admin Only)

- `GET /audit/records` - Get audit records with filtering (supports filters for user_id, resource_type, resource_id, etc.)
- `GET /audit/records/{audit_id}` - Get specific audit record
- `GET /audit/summary` - Get audit statistics

### Query Parameters

- `user_id` - Filter by user
- `action` - Filter by action type
- `resource_type` - Filter by resource type
- `resource_id` - Filter by specific resource
- `start_date` - Start date for filtering
- `end_date` - End date for filtering
- `ip_address` - Filter by IP address
- `offset` - Pagination offset
- `limit` - Pagination limit

## Security Considerations

1. **Immutability**: Audit records cannot be modified or deleted
2. **Access Control**: API endpoints require admin permissions
3. **Data Sanitization**: Sensitive data is redacted before storage
4. **Encryption**: Consider encrypting sensitive audit data at rest
5. **Retention**: Plan for data retention policies

## Performance Considerations

1. **Indexing**: Multiple indexes for common query patterns
2. **Pagination**: All list endpoints support pagination
3. **Background Processing**: Consider using background tasks for audit logging
4. **Partitioning**: For large-scale deployments, consider table partitioning

## Best Practices

1. **Always Audit Critical Operations**
   - User authentication events
   - Resource creation/modification/deletion
   - Permission changes
   - Configuration changes

2. **Include Relevant Context**
   - Use the `details` field for additional metadata
   - Include IP addresses for security tracking
   - Track both previous and new states for updates

3. **Use Appropriate Action Types**
   - Use predefined action types from `AuditActionEnum`
   - Be consistent with resource type naming

4. **Handle Admin Actions**
   - Use `actioned_by` field when admins act on behalf of users
   - This helps users understand who performed actions

5. **Monitor and Alert**
   - Set up alerts for suspicious patterns
   - Regular review of audit logs
   - Monitor for failed authentication attempts

## Testing

Run tests with:
```bash
pytest tests/test_audit_ops.py --dapr-http-port 3510 --dapr-api-token <TOKEN>
```

Tests cover:
- Model validation
- Schema validation
- CRUD operations
- Service methods
- Immutability constraints
- Performance benchmarks

## Migration

Apply the database migration:
```bash
alembic -c ./budapp/alembic.ini upgrade head
```

The migration creates:
- The `audit_trail` table
- All necessary indexes
- Immutability trigger
- Foreign key constraints

## Future Enhancements

1. **Middleware Integration**: Automatic audit logging via FastAPI middleware
2. **Bulk Operations**: Batch audit record creation for performance
3. **Archive Strategy**: Move old records to archive tables
4. **Analytics Dashboard**: Visual analytics for audit data
5. **SIEM Integration**: Export to security information and event management systems
6. **Compliance Reports**: Automated compliance reporting features
