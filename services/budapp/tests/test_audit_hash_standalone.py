#!/usr/bin/env python3
"""Standalone test for audit hash functionality.

This test can be run independently without requiring environment variables
or database setup. It tests the core hash generation and verification logic.
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID, uuid4


def serialize_for_hash(value: Any) -> str:
    """Serialize a value for consistent hashing."""
    if value is None:
        return "null"
    elif isinstance(value, bool):
        # Handle boolean before other types since bool is a subclass of int
        return "true" if value else "false"
    elif isinstance(value, (UUID, str, int, float)):
        return str(value)
    elif isinstance(value, datetime):
        return value.isoformat()
    elif isinstance(value, dict):
        # Sort keys for consistent ordering
        return json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    elif isinstance(value, (list, tuple)):
        return json.dumps(value, default=str, separators=(",", ":"))
    else:
        return str(value)


def generate_audit_hash(
    action: str,
    resource_type: str,
    resource_id: Optional[UUID],
    user_id: Optional[UUID],
    actioned_by: Optional[UUID],
    timestamp: datetime,
    details: Optional[Dict[str, Any]],
    ip_address: Optional[str],
    previous_state: Optional[Dict[str, Any]],
    new_state: Optional[Dict[str, Any]],
    resource_name: Optional[str] = None,
) -> str:
    """Generate a SHA256 hash of audit record data."""
    # Create a dictionary of all fields
    data = {
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "user_id": user_id,
        "actioned_by": actioned_by,
        "timestamp": timestamp,
        "details": details,
        "ip_address": ip_address,
        "previous_state": previous_state,
        "new_state": new_state,
        "resource_name": resource_name,
    }

    # Serialize the data
    serialized = serialize_for_hash(data)

    # Generate SHA256 hash
    hash_obj = hashlib.sha256(serialized.encode())
    return hash_obj.hexdigest()


def test_serialize_basic_types():
    """Test serialization of basic data types."""
    assert serialize_for_hash(None) == "null"
    assert serialize_for_hash(True) == "true"
    assert serialize_for_hash(False) == "false"
    assert serialize_for_hash("test") == "test"
    assert serialize_for_hash(123) == "123"
    assert serialize_for_hash(45.67) == "45.67"
    print("✓ Basic type serialization tests passed")


def test_serialize_uuid():
    """Test UUID serialization."""
    test_uuid = uuid4()
    assert serialize_for_hash(test_uuid) == str(test_uuid)
    print("✓ UUID serialization test passed")


def test_serialize_datetime():
    """Test datetime serialization."""
    test_dt = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
    expected = "2024-01-15T10:30:00+00:00"
    assert serialize_for_hash(test_dt) == expected
    print("✓ Datetime serialization test passed")


def test_serialize_dict_ordering():
    """Test that dictionary serialization maintains consistent ordering."""
    dict1 = {"b": 2, "a": 1, "c": 3}
    dict2 = {"c": 3, "a": 1, "b": 2}
    dict3 = {"a": 1, "b": 2, "c": 3}

    result1 = serialize_for_hash(dict1)
    result2 = serialize_for_hash(dict2)
    result3 = serialize_for_hash(dict3)

    assert result1 == result2 == result3
    assert result1 == '{"a":1,"b":2,"c":3}'
    print("✓ Dictionary ordering test passed")


def test_hash_consistency():
    """Test that the same inputs always generate the same hash."""
    # Create test data
    action = "CREATE"
    resource_type = "PROJECT"
    resource_id = uuid4()
    user_id = uuid4()
    timestamp = datetime.now(timezone.utc)
    details = {"project_name": "Test Project", "description": "A test"}

    # Generate hash multiple times
    hash1 = generate_audit_hash(
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        user_id=user_id,
        actioned_by=None,
        timestamp=timestamp,
        details=details,
        ip_address="192.168.1.1",
        previous_state=None,
        new_state={"status": "created"},
        resource_name="Test Project",
    )

    hash2 = generate_audit_hash(
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        user_id=user_id,
        actioned_by=None,
        timestamp=timestamp,
        details=details,
        ip_address="192.168.1.1",
        previous_state=None,
        new_state={"status": "created"},
        resource_name="Test Project",
    )

    assert hash1 == hash2
    assert len(hash1) == 64  # SHA256 produces 64 character hex string
    print(f"✓ Hash consistency test passed (hash: {hash1[:16]}...)")


def test_hash_uniqueness():
    """Test that different inputs generate different hashes."""
    base_params = {
        "action": "CREATE",
        "resource_type": "PROJECT",
        "resource_id": uuid4(),
        "user_id": uuid4(),
        "actioned_by": None,
        "timestamp": datetime.now(timezone.utc),
        "details": {"test": "data"},
        "ip_address": "192.168.1.1",
        "previous_state": None,
        "new_state": {"status": "created"},
        "resource_name": "Test Project",
    }

    # Generate base hash
    hash1 = generate_audit_hash(**base_params)

    # Change action and generate new hash
    params2 = base_params.copy()
    params2["action"] = "UPDATE"
    hash2 = generate_audit_hash(**params2)

    # Change user_id and generate new hash
    params3 = base_params.copy()
    params3["user_id"] = uuid4()
    hash3 = generate_audit_hash(**params3)

    # Change details and generate new hash
    params4 = base_params.copy()
    params4["details"] = {"test": "different_data"}
    hash4 = generate_audit_hash(**params4)

    # Change resource_name and generate new hash
    params5 = base_params.copy()
    params5["resource_name"] = "Different Project"
    hash5 = generate_audit_hash(**params5)

    # All hashes should be different
    hashes = [hash1, hash2, hash3, hash4, hash5]
    assert len(set(hashes)) == len(hashes), "Hashes should be unique for different inputs"
    print("✓ Hash uniqueness test passed")


def test_hash_with_complex_data():
    """Test hash generation with complex nested data structures."""
    complex_details = {
        "level1": {
            "level2": {
                "level3": "deep_value",
                "array": [1, 2, 3, {"nested": "object"}],
            },
            "unicode": "测试 テスト 🚀",
            "numbers": [1.5, 2.7, 3.14159],
        },
        "metadata": {
            "created_by": "system",
            "tags": ["important", "audit", "test"],
        },
    }

    hash_result = generate_audit_hash(
        action="UPDATE",
        resource_type="ENDPOINT",
        resource_id=uuid4(),
        user_id=uuid4(),
        actioned_by=uuid4(),
        timestamp=datetime.now(timezone.utc),
        details=complex_details,
        ip_address="::1",  # IPv6 address
        previous_state={"version": 1, "status": "active"},
        new_state={"version": 2, "status": "updated", "data": complex_details},
        resource_name="Complex Endpoint 🚀",
    )

    assert len(hash_result) == 64
    assert all(c in "0123456789abcdef" for c in hash_result)
    print("✓ Complex data hash test passed")


def test_hash_with_admin_action():
    """Test hash generation when admin performs action on behalf of user."""
    user_id = uuid4()
    admin_id = uuid4()

    hash_result = generate_audit_hash(
        action="DELETE",
        resource_type="MODEL",
        resource_id=uuid4(),
        user_id=user_id,
        actioned_by=admin_id,  # Admin acting on behalf
        timestamp=datetime.now(timezone.utc),
        details={"reason": "Policy violation", "approved_by": "security_team"},
        ip_address="10.0.0.1",
        previous_state={"status": "active", "size": 1024},
        new_state=None,  # Deleted, so no new state
        resource_name="Deleted Model v2.1",
    )

    assert len(hash_result) == 64
    print("✓ Admin action hash test passed")


def test_verify_integrity():
    """Test integrity verification by comparing hashes."""
    # Create audit data
    audit_data = {
        "action": "ACCESS_GRANTED",
        "resource_type": "CLUSTER",
        "resource_id": uuid4(),
        "user_id": uuid4(),
        "actioned_by": None,
        "timestamp": datetime.now(timezone.utc),
        "details": {"cluster_name": "prod-cluster-01", "access_level": "read"},
        "ip_address": "192.168.100.50",
        "previous_state": None,
        "new_state": {"permissions": ["read", "list"]},
        "resource_name": "Production Cluster 01",
    }

    # Generate original hash
    original_hash = generate_audit_hash(**audit_data)

    # Verify with same data (should match)
    verification_hash = generate_audit_hash(**audit_data)
    assert original_hash == verification_hash, "Hash should match for same data"

    # Tamper with data (change action)
    tampered_data = audit_data.copy()
    tampered_data["action"] = "ACCESS_DENIED"
    tampered_hash = generate_audit_hash(**tampered_data)
    assert original_hash != tampered_hash, "Hash should not match for tampered data"

    print("✓ Integrity verification test passed")


def test_resource_name_hash_impact():
    """Test that resource_name affects hash generation."""
    base_data = {
        "action": "CREATE",
        "resource_type": "PROJECT",
        "resource_id": uuid4(),
        "user_id": uuid4(),
        "actioned_by": None,
        "timestamp": datetime.now(timezone.utc),
        "details": {"test": "data"},
        "ip_address": "192.168.1.1",
        "previous_state": None,
        "new_state": {"status": "created"},
    }

    # Hash without resource_name
    hash_without = generate_audit_hash(**base_data)

    # Hash with resource_name
    hash_with_name = generate_audit_hash(**base_data, resource_name="Test Project")

    # Hash with different resource_name
    hash_different_name = generate_audit_hash(**base_data, resource_name="Another Project")

    # Hash with None resource_name (explicit)
    hash_with_none = generate_audit_hash(**base_data, resource_name=None)

    # Verify all hashes are different where they should be
    assert hash_without == hash_with_none, "Hash without resource_name should match hash with None"
    assert hash_with_name != hash_without, "Hash with resource_name should differ from hash without"
    assert hash_different_name != hash_with_name, "Different resource names should produce different hashes"
    assert hash_different_name != hash_without, "Different resource name should differ from no resource name"

    print("✓ Resource name hash impact test passed")


def main():
    """Run all tests."""
    print("Running Audit Trail Hash Tests")
    print("=" * 50)

    test_serialize_basic_types()
    test_serialize_uuid()
    test_serialize_datetime()
    test_serialize_dict_ordering()
    test_hash_consistency()
    test_hash_uniqueness()
    test_hash_with_complex_data()
    test_hash_with_admin_action()
    test_verify_integrity()
    test_resource_name_hash_impact()

    print("=" * 50)
    print("✅ All tests passed successfully!")
    print("\nThe audit trail hash functionality is working correctly:")
    print("- Consistent serialization of all data types")
    print("- Deterministic hash generation")
    print("- Unique hashes for different inputs")
    print("- Support for complex nested data structures")
    print("- Integrity verification capability")


if __name__ == "__main__":
    main()
