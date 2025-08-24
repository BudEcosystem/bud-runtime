# Audit Trail Resource Name Implementation Guide

## Overview
This document outlines the changes made to support storing and searching by resource names in audit logs, making audit trails more user-friendly and searchable.

## Changes Implemented

### 1. Database Schema Changes
- Added `resource_name` field to `AuditTrail` model (VARCHAR(255), nullable, indexed)
- Created migration: `add_resource_name_to_audit_trail.py`

### 2. Model and Schema Updates
- **Models** (`audit_ops/models.py`): Added `resource_name` field to AuditTrail model
- **Schemas** (`audit_ops/schemas.py`): 
  - Added `resource_name` to `AuditRecordBase`, `AuditRecordEntry`, and `AuditRecordFilter`
  - Filter supports partial match search using ILIKE

### 3. CRUD and Service Layer
- **CRUD** (`audit_ops/crud.py`): 
  - Updated `create_audit_record` to accept and store `resource_name`
  - Updated `get_audit_records` to filter by `resource_name` with partial match
- **Services** (`audit_ops/services.py`): 
  - Updated `get_audit_records` to pass through `resource_name` filter
- **Hash Utils** (`audit_ops/hash_utils.py`): 
  - Updated hash generation to include `resource_name` for integrity

### 4. API and Export Updates
- **Routes** (`audit_ops/audit_routes.py`): 
  - Added `resource_name` query parameter for filtering
- **Export** (`audit_ops/export_utils.py`): 
  - Added "Resource Name" column to CSV exports
- **Logger** (`audit_ops/audit_logger.py`): 
  - Updated `log_audit` function to accept `resource_name` parameter

## How to Update Existing Audit Calls

### Simple Update Pattern

For most audit logging calls, simply add the `resource_name` parameter:

#### Before:
```python
log_audit(
    session=self.session,
    action=AuditActionEnum.CREATE,
    resource_type=AuditResourceTypeEnum.PROJECT,
    resource_id=db_project.id,
    user_id=current_user_id,
    details={"project_name": db_project.name},
    request=request,
    success=True,
)
```

#### After:
```python
log_audit(
    session=self.session,
    action=AuditActionEnum.CREATE,
    resource_type=AuditResourceTypeEnum.PROJECT,
    resource_id=db_project.id,
    resource_name=db_project.name,  # <-- Added this line
    user_id=current_user_id,
    details={"project_name": db_project.name},
    request=request,
    success=True,
)
```

### Resource Name Mapping by Type

| Resource Type | Resource Name Source | Example |
|--------------|---------------------|---------|
| PROJECT | `db_project.name` | `resource_name=db_project.name` |
| MODEL | `db_model.name` or `db_model.display_name` | `resource_name=db_model.display_name` |
| ENDPOINT | `db_endpoint.name` | `resource_name=db_endpoint.name` |
| API_KEY | `db_credential.name` | `resource_name=db_credential.name` |
| USER | `db_user.name` or `db_user.email` | `resource_name=db_user.name or db_user.email` |
| CLUSTER | `db_cluster.name` | `resource_name=db_cluster.name` |
| DATASET | `db_dataset.name` | `resource_name=db_dataset.name` |

### Handling None Values

The `resource_name` field is nullable, so it's safe to pass None if the name is not available:

```python
# Safe with null check
resource_name=db_project.name if db_project else None

# Or with getattr
resource_name=getattr(db_object, 'name', None)
```

## Migration Steps

1. **Run the database migration** to add the column:
   ```bash
   alembic upgrade head
   ```

2. **Update audit calls incrementally** - The system will work with both old (without resource_name) and new (with resource_name) audit records

3. **Optional: Backfill existing records** - You can optionally write a script to populate resource_name for existing audit records by looking up the resources

## API Usage Examples

### Filtering by Resource Name
```bash
# Search for audit records by resource name (partial match)
GET /audit/records?resource_name=MyProject

# Combine with other filters
GET /audit/records?resource_type=PROJECT&resource_name=Test&start_date=2024-01-01
```

### CSV Export with Resource Name
```bash
# Export audit records to CSV (includes Resource Name column)
GET /audit/records?export_csv=true&resource_name=Production
```

## Benefits

1. **Improved Search**: Users can search audit logs by resource name without knowing the UUID
2. **Better Display**: UI can show meaningful names instead of just IDs
3. **Enhanced Export**: CSV exports include resource names for easier analysis
4. **Backward Compatible**: Existing code continues to work; resource_name is optional

## Testing

When testing the new functionality:

1. Create audit records with resource_name
2. Search/filter by resource_name 
3. Export to CSV and verify the Resource Name column
4. Verify that old audit records (without resource_name) still work correctly

## Example Implementation in Services

Here's a complete example of updating a service method:

```python
def create_project(self, project_data, current_user_id, request):
    # Create the project
    db_project = self.crud.create_project(project_data)
    
    # Log audit with resource_name
    log_audit(
        session=self.session,
        action=AuditActionEnum.CREATE,
        resource_type=AuditResourceTypeEnum.PROJECT,
        resource_id=db_project.id,
        resource_name=db_project.name,  # <-- Include resource name
        user_id=current_user_id,
        details={
            "project_name": db_project.name,
            "description": db_project.description,
        },
        request=request,
        success=True,
    )
    
    return db_project
```

## Notes

- The resource_name field is indexed for performance
- It supports case-insensitive partial matching (using PostgreSQL ILIKE)
- The field is included in the audit record hash for integrity verification
- Maximum length is 255 characters (names longer than this will be truncated)