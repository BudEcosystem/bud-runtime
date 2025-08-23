# Testing Guidelines for BudApp Services

## Purpose
This document captures testing best practices and common pitfalls discovered during the audit trail implementation. Following these guidelines will prevent common testing errors and ensure consistent, maintainable tests.

## Common Testing Pitfalls and Solutions

### 1. SQLAlchemy Query Mocking

#### ❌ Wrong Approach
```python
# Old-style mocking that doesn't work with modern SQLAlchemy
mock_query = Mock()
mock_session.query = Mock(return_value=mock_query)
mock_query.filter = Mock(return_value=mock_query)
mock_query.all = Mock(return_value=[])
```

#### ✅ Correct Approach
```python
# Mock DataManagerUtils methods directly
data_manager.execute_scalar = Mock(return_value=5)  # For COUNT queries
data_manager.scalars_all = Mock(return_value=[])   # For SELECT queries returning multiple rows
data_manager.scalar_one_or_none = Mock(return_value=record)  # For single record queries
```

#### Why This Matters
- Modern SQLAlchemy uses `select()` statements, not `session.query()`
- DataManagerUtils provides wrapper methods that should be mocked
- The old query chain mocking pattern won't be called by the actual code

### 2. CRUD Method Parameters

#### ❌ Wrong Approach
```python
# Passing Pydantic schema objects to CRUD methods
from budapp.audit_ops.schemas import AuditRecordCreate

audit_data = AuditRecordCreate(
    user_id=uuid4(),
    action=AuditActionEnum.CREATE,
    resource_type=AuditResourceTypeEnum.PROJECT,
    details={"test": "data"}
)
data_manager.create_audit_record(audit_data)  # This will fail!
```

#### ✅ Correct Approach
```python
# Pass individual parameters
data_manager.create_audit_record(
    action=AuditActionEnum.CREATE,
    resource_type=AuditResourceTypeEnum.PROJECT,
    resource_id=uuid4(),
    user_id=uuid4(),
    details={"test": "data"},
    ip_address="192.168.1.1"
)
```

#### Why This Matters
- CRUD methods expect individual parameters, not schema objects
- Schemas are for API validation, not internal data access
- Passing a schema object will result in missing required positional arguments

### 3. Mock Records for Pydantic Validation

#### ❌ Wrong Approach
```python
# Incomplete mock that will fail Pydantic validation
record = Mock(spec=AuditTrail)
record.id = uuid4()
record.record_hash = "hash"
# Missing many required fields!

# This will fail when passed to Pydantic schema
entry = AuditRecordEntry.model_validate(record)  # ValidationError!
```

#### ✅ Correct Approach
```python
# Complete mock with ALL required fields
record = Mock(spec=AuditTrail)
record.id = uuid4()
record.user_id = uuid4()
record.actioned_by = None
record.action = "CREATE"
record.resource_type = "PROJECT"
record.resource_id = uuid4()
record.timestamp = datetime.now(timezone.utc)
record.details = {}
record.ip_address = "192.168.1.1"
record.previous_state = None
record.new_state = None
record.record_hash = "a" * 64
record.created_at = datetime.now(timezone.utc)
record.user = None
record.actioned_by_user = None

# Now this will work
entry = AuditRecordEntry.model_validate(record)  # Success!
```

#### Why This Matters
- Pydantic performs strict validation and requires all non-optional fields
- Mock objects must have all attributes that the schema expects
- Missing fields will cause validation errors even in tests

### 4. JSON Serialization Format

#### ❌ Wrong Approach
```python
# Expecting JSON with spaces
test_dict = {"b": 2, "a": 1, "c": 3}
result = serialize_for_hash(test_dict)
assert result == '{"a": 1, "b": 2, "c": 3}'  # Wrong format!
```

#### ✅ Correct Approach
```python
# Expect compact JSON format (no spaces)
test_dict = {"b": 2, "a": 1, "c": 3}
result = serialize_for_hash(test_dict)
assert result == '{"a":1,"b":2,"c":3}'  # Compact format
```

#### Why This Matters
- Compact JSON ensures consistent hashing
- Reduces data size for better performance
- Eliminates formatting variations between JSON libraries

### 5. Boolean Serialization

#### ❌ Wrong Approach
```python
# Expecting Python string representation
assert serialize_for_hash(True) == "True"   # Python format
assert serialize_for_hash(False) == "False"  # Python format
```

#### ✅ Correct Approach
```python
# Expect JSON format (lowercase)
assert serialize_for_hash(True) == "true"   # JSON format
assert serialize_for_hash(False) == "false"  # JSON format
```

#### Why This Matters
- JSON standard uses lowercase booleans
- Ensures compatibility across different systems
- Critical for consistent hash generation

### 6. Return Structure Keys

#### ❌ Wrong Approach
```python
# Assuming field names without checking implementation
tampered = service.find_tampered_records(limit=10)
assert tampered[0]["audit_id"] == str(record_id)  # Wrong key!
assert tampered[0]["reason"] == "message"         # Wrong key!
```

#### ✅ Correct Approach
```python
# Use actual keys from service implementation
tampered = service.find_tampered_records(limit=10)
assert tampered[0]["id"] == str(record_id)                      # Correct key
assert tampered[0]["verification_message"] == "message"         # Correct key
```

#### Why This Matters
- Service methods define their own return structures
- Keys might differ from database field names
- Always check the actual implementation

## Best Practices Checklist

### Before Writing Tests
- [ ] Check if the code uses modern SQLAlchemy (`select()`) or old style (`query()`)
- [ ] Review the actual method signatures in the implementation
- [ ] Identify all required fields for any Pydantic schemas involved
- [ ] Check the exact return structure of service methods

### When Mocking
- [ ] Mock DataManagerUtils methods, not `session.query`
- [ ] Include ALL required fields when creating mock objects for Pydantic
- [ ] Use the correct data types for mock attributes
- [ ] Mock at the appropriate level (don't mock too deep or too shallow)

### When Asserting
- [ ] Use compact JSON format in assertions
- [ ] Use lowercase for boolean string representations
- [ ] Verify the actual keys in returned dictionaries
- [ ] Check that counts and lists match expected values

## Example: Complete Test Template

```python
import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch
from uuid import uuid4
from sqlalchemy.orm import Session

def test_complete_example():
    """Example test following all best practices."""

    # 1. Setup mock session
    mock_session = Mock(spec=Session)

    # 2. Create data manager with correct mocking
    from budapp.audit_ops.crud import AuditTrailDataManager
    data_manager = AuditTrailDataManager(mock_session)

    # Mock DataManagerUtils methods (not session.query!)
    data_manager.execute_scalar = Mock(return_value=10)
    data_manager.scalars_all = Mock(return_value=[])

    # 3. Create complete mock records for Pydantic
    mock_record = Mock()
    mock_record.id = uuid4()
    mock_record.user_id = uuid4()
    mock_record.action = "CREATE"
    mock_record.resource_type = "PROJECT"
    mock_record.timestamp = datetime.now(timezone.utc)
    mock_record.record_hash = "a" * 64
    mock_record.created_at = datetime.now(timezone.utc)
    # ... include ALL required fields

    # 4. Test CRUD operations with individual parameters
    from budapp.commons.constants import AuditActionEnum, AuditResourceTypeEnum

    result = data_manager.create_audit_record(
        action=AuditActionEnum.CREATE,
        resource_type=AuditResourceTypeEnum.PROJECT,
        resource_id=uuid4(),
        user_id=uuid4(),
        details={"key": "value"}  # Will be serialized as {"key":"value"}
    )

    # 5. Assert with correct formats
    # Compact JSON
    assert json.dumps({"a": 1}) == '{"a":1}'

    # Lowercase booleans
    assert json.dumps(True) == 'true'

    # Correct return structure keys
    response = {"id": "123", "verification_message": "success"}
    assert response["id"] == "123"  # Not "audit_id"
    assert response["verification_message"] == "success"  # Not "reason"
```

## Debugging Test Failures

### Common Error Messages and Solutions

1. **`AttributeError: 'DataManagerUtils' object has no attribute 'query'`**
   - Solution: Mock `execute_scalar`, `scalars_all`, or `scalar_one_or_none` instead

2. **`TypeError: create_audit_record() missing 1 required positional argument`**
   - Solution: Pass individual parameters, not a schema object

3. **`pydantic_core._pydantic_core.ValidationError: Field required`**
   - Solution: Add all required fields to your mock object

4. **`AssertionError: '{"a": 1}' != '{"a":1}'`**
   - Solution: Use compact JSON format (no spaces)

5. **`KeyError: 'audit_id'`**
   - Solution: Check the actual implementation for correct field names

## Conclusion

Following these guidelines will help you:
- Write tests that actually test the code (not just the mocks)
- Avoid common pitfalls that cause test failures
- Create maintainable tests that don't break with implementation updates
- Save time debugging test issues

Remember: **Always check the actual implementation** before writing tests!
