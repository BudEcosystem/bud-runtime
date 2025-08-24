"""Unit tests for audit trail hash functionality.

This module contains tests for the audit record hashing and integrity verification features.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock
from uuid import uuid4

import pytest

from budapp.audit_ops.hash_utils import (
    generate_audit_hash,
    serialize_for_hash,
    verify_audit_hash,
    verify_audit_integrity,
)
from budapp.audit_ops.models import AuditTrail
from budapp.commons.constants import AuditActionEnum, AuditResourceTypeEnum


class TestHashUtilities:
    """Tests for hash generation and verification utilities."""

    def test_serialize_for_hash_none(self):
        """Test serialization of None value."""
        assert serialize_for_hash(None) == "null"

    def test_serialize_for_hash_uuid(self):
        """Test serialization of UUID."""
        test_uuid = uuid4()
        assert serialize_for_hash(test_uuid) == str(test_uuid)

    def test_serialize_for_hash_datetime(self):
        """Test serialization of datetime."""
        test_dt = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        assert serialize_for_hash(test_dt) == test_dt.isoformat()

    def test_serialize_for_hash_dict(self):
        """Test serialization of dictionary with consistent ordering."""
        test_dict = {"b": 2, "a": 1, "c": 3}
        result = serialize_for_hash(test_dict)
        assert result == '{"a":1,"b":2,"c":3}'  # Compact JSON format

    def test_generate_audit_hash_consistency(self):
        """Test that the same inputs always generate the same hash."""
        action = AuditActionEnum.CREATE
        resource_type = AuditResourceTypeEnum.PROJECT
        resource_id = uuid4()
        user_id = uuid4()
        timestamp = datetime.now(timezone.utc)
        details = {"test": "data"}

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
            new_state={"created": True},
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
            new_state={"created": True},
            resource_name="Test Project",
        )

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 produces 64 character hex string

    def test_generate_audit_hash_different_inputs(self):
        """Test that different inputs generate different hashes."""
        base_params = {
            "action": AuditActionEnum.CREATE,
            "resource_type": AuditResourceTypeEnum.PROJECT,
            "resource_id": uuid4(),
            "user_id": uuid4(),
            "actioned_by": None,
            "timestamp": datetime.now(timezone.utc),
            "details": {"test": "data"},
            "ip_address": "192.168.1.1",
            "previous_state": None,
            "new_state": {"created": True},
            "resource_name": "Test Project",
        }

        hash1 = generate_audit_hash(**base_params)

        # Change one parameter
        base_params["action"] = AuditActionEnum.UPDATE
        hash2 = generate_audit_hash(**base_params)

        assert hash1 != hash2

    def test_verify_audit_hash_valid(self):
        """Test verification of a valid audit hash."""
        # Create a mock audit record
        audit_record = Mock()
        audit_record.action = AuditActionEnum.CREATE
        audit_record.resource_type = AuditResourceTypeEnum.MODEL
        audit_record.resource_id = uuid4()
        audit_record.user_id = uuid4()
        audit_record.actioned_by = None
        audit_record.timestamp = datetime.now(timezone.utc)
        audit_record.details = {"operation": "test"}
        audit_record.ip_address = "10.0.0.1"
        audit_record.previous_state = None
        audit_record.new_state = {"status": "active"}
        audit_record.resource_name = "Test Model"

        # Generate the expected hash
        expected_hash = generate_audit_hash(
            action=audit_record.action,
            resource_type=audit_record.resource_type,
            resource_id=audit_record.resource_id,
            user_id=audit_record.user_id,
            actioned_by=audit_record.actioned_by,
            timestamp=audit_record.timestamp,
            details=audit_record.details,
            ip_address=audit_record.ip_address,
            previous_state=audit_record.previous_state,
            new_state=audit_record.new_state,
            resource_name=audit_record.resource_name,
        )

        # Verify the hash
        assert verify_audit_hash(audit_record, expected_hash) is True

    def test_verify_audit_hash_invalid(self):
        """Test verification of an invalid audit hash."""
        # Create a mock audit record
        audit_record = Mock()
        audit_record.action = AuditActionEnum.CREATE
        audit_record.resource_type = AuditResourceTypeEnum.ENDPOINT
        audit_record.resource_id = uuid4()
        audit_record.user_id = uuid4()
        audit_record.actioned_by = None
        audit_record.timestamp = datetime.now(timezone.utc)
        audit_record.details = {"operation": "test"}
        audit_record.ip_address = "10.0.0.1"
        audit_record.previous_state = None
        audit_record.new_state = {"status": "active"}
        audit_record.resource_name = "Test Endpoint"

        # Use an incorrect hash
        invalid_hash = "0" * 64

        # Verify the hash
        assert verify_audit_hash(audit_record, invalid_hash) is False

    def test_verify_audit_integrity_valid(self):
        """Test integrity verification of a valid audit record."""
        # Create a mock audit record with correct hash
        audit_record = Mock()
        audit_record.action = AuditActionEnum.DELETE
        audit_record.resource_type = AuditResourceTypeEnum.CLUSTER
        audit_record.resource_id = uuid4()
        audit_record.user_id = uuid4()
        audit_record.actioned_by = uuid4()  # Admin action
        audit_record.timestamp = datetime.now(timezone.utc)
        audit_record.details = {"reason": "decommissioned"}
        audit_record.ip_address = "172.16.0.1"
        audit_record.previous_state = {"status": "active"}
        audit_record.new_state = None
        audit_record.resource_name = "Production Cluster"

        # Generate and set the correct hash
        audit_record.record_hash = generate_audit_hash(
            action=audit_record.action,
            resource_type=audit_record.resource_type,
            resource_id=audit_record.resource_id,
            user_id=audit_record.user_id,
            actioned_by=audit_record.actioned_by,
            timestamp=audit_record.timestamp,
            details=audit_record.details,
            ip_address=audit_record.ip_address,
            previous_state=audit_record.previous_state,
            new_state=audit_record.new_state,
            resource_name=audit_record.resource_name,
        )

        is_valid, message = verify_audit_integrity(audit_record)
        assert is_valid is True
        assert "verified successfully" in message

    def test_verify_audit_integrity_tampered(self):
        """Test integrity verification of a tampered audit record."""
        # Create a mock audit record
        audit_record = Mock()
        audit_record.action = AuditActionEnum.UPDATE
        audit_record.resource_type = AuditResourceTypeEnum.USER
        audit_record.resource_id = uuid4()
        audit_record.user_id = uuid4()
        audit_record.actioned_by = None
        audit_record.timestamp = datetime.now(timezone.utc)
        audit_record.details = {"field": "email"}
        audit_record.ip_address = "192.168.1.100"
        audit_record.previous_state = {"email": "old@example.com"}
        audit_record.new_state = {"email": "new@example.com"}
        audit_record.resource_name = "User Profile"

        # Generate hash for original state
        audit_record.record_hash = generate_audit_hash(
            action=audit_record.action,
            resource_type=audit_record.resource_type,
            resource_id=audit_record.resource_id,
            user_id=audit_record.user_id,
            actioned_by=audit_record.actioned_by,
            timestamp=audit_record.timestamp,
            details=audit_record.details,
            ip_address=audit_record.ip_address,
            previous_state=audit_record.previous_state,
            new_state=audit_record.new_state,
            resource_name=audit_record.resource_name,
        )

        # Tamper with the record (change the action)
        audit_record.action = AuditActionEnum.DELETE

        is_valid, message = verify_audit_integrity(audit_record)
        assert is_valid is False
        assert "tampering detected" in message

    def test_verify_audit_integrity_missing_hash(self):
        """Test integrity verification when hash field is missing."""
        # Create a mock audit record without record_hash attribute
        audit_record = Mock(spec=[])  # No attributes

        is_valid, message = verify_audit_integrity(audit_record)
        assert is_valid is False
        assert "does not have a record_hash field" in message


class TestHashWithComplexData:
    """Tests for hash generation with complex data structures."""

    def test_hash_with_nested_dict(self):
        """Test hash generation with nested dictionary data."""
        nested_data = {
            "level1": {
                "level2": {
                    "level3": "value",
                    "array": [1, 2, 3],
                },
                "another": "field",
            }
        }

        hash1 = generate_audit_hash(
            action=AuditActionEnum.CREATE,
            resource_type=AuditResourceTypeEnum.PROJECT,
            resource_id=uuid4(),
            user_id=uuid4(),
            actioned_by=None,
            timestamp=datetime.now(timezone.utc),
            details=nested_data,
            ip_address=None,
            previous_state=None,
            new_state=None,
            resource_name="Complex Project",
        )

        assert len(hash1) == 64

    def test_hash_with_unicode_data(self):
        """Test hash generation with Unicode characters."""
        unicode_data = {
            "name": "测试项目",
            "description": "テスト説明",
            "emoji": "🚀🔒📊",
        }

        hash1 = generate_audit_hash(
            action=AuditActionEnum.UPDATE,
            resource_type=AuditResourceTypeEnum.MODEL,
            resource_id=uuid4(),
            user_id=uuid4(),
            actioned_by=None,
            timestamp=datetime.now(timezone.utc),
            details=unicode_data,
            ip_address="::1",  # IPv6 address
            previous_state={"name": "old"},
            new_state=unicode_data,
            resource_name="测试项目",  # Unicode resource name
        )

        assert len(hash1) == 64

    def test_hash_with_all_fields_populated(self):
        """Test hash generation with all possible fields populated."""
        full_data = generate_audit_hash(
            action=AuditActionEnum.ACCESS_GRANTED,
            resource_type=AuditResourceTypeEnum.ENDPOINT,
            resource_id=uuid4(),
            user_id=uuid4(),
            actioned_by=uuid4(),
            timestamp=datetime.now(timezone.utc),
            details={
                "method": "POST",
                "path": "/api/v1/models",
                "status_code": 200,
            },
            ip_address="203.0.113.42",
            previous_state={
                "permissions": ["read"],
                "last_access": "2024-01-01T00:00:00Z",
            },
            new_state={
                "permissions": ["read", "write"],
                "last_access": "2024-01-15T10:30:00Z",
            },
            resource_name="API Endpoint v1/models",
        )

        assert len(full_data) == 64
        assert all(c in "0123456789abcdef" for c in full_data)  # Valid hex string

    def test_hash_resource_name_affects_result(self):
        """Test that different resource_name values generate different hashes."""
        base_params = {
            "action": AuditActionEnum.CREATE,
            "resource_type": AuditResourceTypeEnum.PROJECT,
            "resource_id": uuid4(),
            "user_id": uuid4(),
            "actioned_by": None,
            "timestamp": datetime.now(timezone.utc),
            "details": {"test": "data"},
            "ip_address": "192.168.1.1",
            "previous_state": None,
            "new_state": {"created": True},
        }

        # Generate hash with first resource name
        hash1 = generate_audit_hash(**base_params, resource_name="Project Alpha")

        # Generate hash with different resource name
        hash2 = generate_audit_hash(**base_params, resource_name="Project Beta")

        # Generate hash with None resource name
        hash3 = generate_audit_hash(**base_params, resource_name=None)

        # All hashes should be different
        assert hash1 != hash2
        assert hash1 != hash3
        assert hash2 != hash3
        assert len({hash1, hash2, hash3}) == 3  # All unique
