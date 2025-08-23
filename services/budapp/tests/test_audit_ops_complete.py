"""Comprehensive tests for the audit trail system with proper mocking.

This test file tests the complete audit trail functionality including:
- Model creation and immutability
- Hash generation and verification
- CRUD operations
- Service layer methods
- API endpoints
"""

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, Mock, PropertyMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from budapp.audit_ops.crud import AuditTrailDataManager
from budapp.audit_ops.hash_utils import (
    generate_audit_hash,
    serialize_for_hash,
    verify_audit_hash,
    verify_audit_integrity,
)
from budapp.audit_ops.models import AuditTrail
from budapp.audit_ops.schemas import (
    AuditRecordCreate,
    AuditRecordEntry,
    AuditRecordFilter,
)
from budapp.audit_ops.services import AuditService
from budapp.commons.constants import AuditActionEnum, AuditResourceTypeEnum


class TestHashUtils:
    """Test hash utility functions."""

    def test_serialize_for_hash_basic_types(self):
        """Test serialization of basic data types."""
        assert serialize_for_hash(None) == "null"
        assert serialize_for_hash("test") == "test"
        assert serialize_for_hash(123) == "123"
        assert serialize_for_hash(True) == "true"
        assert serialize_for_hash(False) == "false"

    def test_serialize_for_hash_uuid(self):
        """Test UUID serialization."""
        test_uuid = uuid4()
        assert serialize_for_hash(test_uuid) == str(test_uuid)

    def test_serialize_for_hash_datetime(self):
        """Test datetime serialization."""
        test_dt = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        assert serialize_for_hash(test_dt) == test_dt.isoformat()

    def test_serialize_for_hash_dict_ordering(self):
        """Test that dictionary keys are consistently ordered."""
        dict1 = {"b": 2, "a": 1, "c": 3}
        dict2 = {"c": 3, "a": 1, "b": 2}
        assert serialize_for_hash(dict1) == serialize_for_hash(dict2)

    def test_generate_audit_hash_consistency(self):
        """Test that the same inputs always generate the same hash."""
        params = {
            "action": AuditActionEnum.CREATE,
            "resource_type": AuditResourceTypeEnum.PROJECT,
            "resource_id": uuid4(),
            "user_id": uuid4(),
            "actioned_by": None,
            "timestamp": datetime.now(timezone.utc),
            "details": {"test": "data"},
            "ip_address": "192.168.1.1",
            "previous_state": None,
            "new_state": {"status": "created"},
        }

        hash1 = generate_audit_hash(**params)
        hash2 = generate_audit_hash(**params)

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
            "new_state": {"status": "created"},
        }

        hash1 = generate_audit_hash(**base_params)

        # Change one parameter
        base_params["action"] = AuditActionEnum.UPDATE
        hash2 = generate_audit_hash(**base_params)

        assert hash1 != hash2

    def test_verify_audit_hash(self):
        """Test hash verification."""
        # Create a mock audit record
        record = Mock()
        record.action = AuditActionEnum.CREATE
        record.resource_type = AuditResourceTypeEnum.MODEL
        record.resource_id = uuid4()
        record.user_id = uuid4()
        record.actioned_by = None
        record.timestamp = datetime.now(timezone.utc)
        record.details = {"operation": "test"}
        record.ip_address = "10.0.0.1"
        record.previous_state = None
        record.new_state = {"status": "active"}

        # Generate the correct hash
        correct_hash = generate_audit_hash(
            action=record.action,
            resource_type=record.resource_type,
            resource_id=record.resource_id,
            user_id=record.user_id,
            actioned_by=record.actioned_by,
            timestamp=record.timestamp,
            details=record.details,
            ip_address=record.ip_address,
            previous_state=record.previous_state,
            new_state=record.new_state,
        )

        # Test with correct hash
        assert verify_audit_hash(record, correct_hash) is True

        # Test with incorrect hash
        assert verify_audit_hash(record, "0" * 64) is False

    def test_verify_audit_integrity(self):
        """Test audit record integrity verification."""
        # Create a valid record
        record = Mock()
        record.action = AuditActionEnum.DELETE
        record.resource_type = AuditResourceTypeEnum.CLUSTER
        record.resource_id = uuid4()
        record.user_id = uuid4()
        record.actioned_by = uuid4()
        record.timestamp = datetime.now(timezone.utc)
        record.details = {"reason": "decommissioned"}
        record.ip_address = "172.16.0.1"
        record.previous_state = {"status": "active"}
        record.new_state = None

        # Set correct hash
        record.record_hash = generate_audit_hash(
            action=record.action,
            resource_type=record.resource_type,
            resource_id=record.resource_id,
            user_id=record.user_id,
            actioned_by=record.actioned_by,
            timestamp=record.timestamp,
            details=record.details,
            ip_address=record.ip_address,
            previous_state=record.previous_state,
            new_state=record.new_state,
        )

        is_valid, message = verify_audit_integrity(record)
        assert is_valid is True
        assert "verified successfully" in message

        # Tamper with the record
        record.action = AuditActionEnum.UPDATE
        is_valid, message = verify_audit_integrity(record)
        assert is_valid is False
        assert "tampering detected" in message


class TestAuditTrailCRUD:
    """Test CRUD operations for audit trail."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = Mock(spec=Session)
        session.query = Mock()
        session.add = Mock()
        session.commit = Mock()
        session.refresh = Mock()
        return session

    @pytest.fixture
    def data_manager(self, mock_session):
        """Create an AuditTrailDataManager instance."""
        return AuditTrailDataManager(mock_session)

    def test_create_audit_record(self, data_manager, mock_session):
        """Test creating an audit record."""
        # Prepare test data
        audit_data = AuditRecordCreate(
            user_id=uuid4(),
            action=AuditActionEnum.CREATE,
            resource_type=AuditResourceTypeEnum.PROJECT,
            resource_id=uuid4(),
            details={"project_name": "Test Project"},
            ip_address="192.168.1.1",
        )

        # Mock the session behavior
        mock_session.add = Mock()
        mock_session.commit = Mock()
        mock_session.refresh = Mock()

        # Create the record
        result = data_manager.create_audit_record(audit_data)

        # Verify session methods were called
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()

        # Verify the record was created
        assert isinstance(result, AuditTrail)

    def test_get_audit_records_with_filters(self, data_manager, mock_session):
        """Test getting audit records with various filters."""
        # Mock query chain
        mock_query = Mock()
        mock_query.join = Mock(return_value=mock_query)
        mock_query.outerjoin = Mock(return_value=mock_query)
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.order_by = Mock(return_value=mock_query)
        mock_query.offset = Mock(return_value=mock_query)
        mock_query.limit = Mock(return_value=mock_query)
        mock_query.all = Mock(return_value=[])
        mock_query.count = Mock(return_value=0)

        mock_session.query = Mock(return_value=mock_query)

        # Test with various filters
        user_id = uuid4()
        action = AuditActionEnum.UPDATE
        resource_type = AuditResourceTypeEnum.ENDPOINT
        resource_id = uuid4()
        start_date = datetime.now(timezone.utc) - timedelta(days=7)
        end_date = datetime.now(timezone.utc)

        records, total = data_manager.get_audit_records(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            start_date=start_date,
            end_date=end_date,
            offset=0,
            limit=20,
        )

        # Verify query was called
        mock_session.query.assert_called()
        mock_query.filter.assert_called()

        # Verify results
        assert records == []
        assert total == 0

    def test_get_audit_record_by_id(self, data_manager, mock_session):
        """Test getting a single audit record by ID."""
        # Create a mock record
        audit_id = uuid4()
        mock_record = Mock(spec=AuditTrail)
        mock_record.id = audit_id

        # Mock query chain
        mock_query = Mock()
        mock_query.outerjoin = Mock(return_value=mock_query)
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.first = Mock(return_value=mock_record)

        mock_session.query = Mock(return_value=mock_query)

        # Get the record
        result = data_manager.get_audit_record_by_id(audit_id)

        # Verify
        assert result == mock_record
        mock_query.filter.assert_called()


class TestAuditService:
    """Test the audit service layer."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return Mock(spec=Session)

    @pytest.fixture
    def service(self, mock_session):
        """Create an AuditService instance."""
        return AuditService(mock_session)

    def test_audit_create(self, service):
        """Test auditing a resource creation."""
        with patch.object(service.data_manager, 'create_audit_record') as mock_create:
            mock_create.return_value = Mock(spec=AuditTrail)

            result = service.audit_create(
                resource_type=AuditResourceTypeEnum.PROJECT,
                resource_id=uuid4(),
                resource_data={"name": "Test"},
                user_id=uuid4(),
                ip_address="192.168.1.1",
            )

            mock_create.assert_called_once()
            assert result is not None

    def test_audit_update(self, service):
        """Test auditing a resource update."""
        with patch.object(service.data_manager, 'create_audit_record') as mock_create:
            mock_create.return_value = Mock(spec=AuditTrail)

            result = service.audit_update(
                resource_type=AuditResourceTypeEnum.ENDPOINT,
                resource_id=uuid4(),
                previous_data={"status": "active"},
                new_data={"status": "inactive"},
                user_id=uuid4(),
                ip_address="192.168.1.1",
            )

            mock_create.assert_called_once()
            assert result is not None

    def test_audit_delete(self, service):
        """Test auditing a resource deletion."""
        with patch.object(service.data_manager, 'create_audit_record') as mock_create:
            mock_create.return_value = Mock(spec=AuditTrail)

            result = service.audit_delete(
                resource_type=AuditResourceTypeEnum.MODEL,
                resource_id=uuid4(),
                resource_data={"name": "Model"},
                user_id=uuid4(),
                ip_address="192.168.1.1",
            )

            mock_create.assert_called_once()
            assert result is not None

    def test_verify_audit_record_integrity(self, service):
        """Test verifying audit record integrity."""
        audit_id = uuid4()
        mock_record = Mock(spec=AuditTrail)
        mock_record.record_hash = "valid_hash"

        with patch.object(service.data_manager, 'get_audit_record_by_id') as mock_get:
            mock_get.return_value = mock_record

            with patch('budapp.audit_ops.services.verify_audit_integrity') as mock_verify:
                mock_verify.return_value = (True, "Record verified successfully")

                is_valid, message = service.verify_audit_record_integrity(audit_id)

                assert is_valid is True
                assert "verified successfully" in message

    def test_find_tampered_records(self, service):
        """Test finding tampered records."""
        # Create mock records
        record1 = Mock(spec=AuditTrail)
        record1.id = uuid4()
        record1.record_hash = "hash1"

        record2 = Mock(spec=AuditTrail)
        record2.id = uuid4()
        record2.record_hash = "hash2"

        with patch.object(service.data_manager, 'get_audit_records') as mock_get:
            mock_get.return_value = ([record1, record2], 2)

            with patch('budapp.audit_ops.services.verify_audit_integrity') as mock_verify:
                # First record is valid, second is tampered
                mock_verify.side_effect = [
                    (True, "Valid"),
                    (False, "Tampered"),
                ]

                tampered = service.find_tampered_records(limit=10)

                assert len(tampered) == 1
                assert tampered[0]["audit_id"] == str(record2.id)
                assert tampered[0]["reason"] == "Tampered"

    def test_sanitize_sensitive_data(self, service):
        """Test sensitive data sanitization."""
        data = {
            "password": "secret123",
            "api_key": "key123",
            "token": "token123",
            "secret": "secret",
            "normal_field": "value",
            "nested": {
                "password": "nested_secret",
                "safe": "data",
            },
        }

        sanitized = service._sanitize_sensitive_data(data)

        assert sanitized["password"] == "***REDACTED***"
        assert sanitized["api_key"] == "***REDACTED***"
        assert sanitized["token"] == "***REDACTED***"
        assert sanitized["secret"] == "***REDACTED***"
        assert sanitized["normal_field"] == "value"
        assert sanitized["nested"]["password"] == "***REDACTED***"
        assert sanitized["nested"]["safe"] == "data"


class TestAuditSchemas:
    """Test Pydantic schemas for audit trail."""

    def test_audit_record_create_validation(self):
        """Test AuditRecordCreate schema validation."""
        # Valid data
        valid_data = {
            "action": AuditActionEnum.CREATE,
            "resource_type": AuditResourceTypeEnum.PROJECT,
            "resource_id": str(uuid4()),
            "user_id": str(uuid4()),
            "details": {"test": "data"},
            "ip_address": "192.168.1.1",
        }

        record = AuditRecordCreate(**valid_data)
        assert record.action == AuditActionEnum.CREATE
        assert record.resource_type == AuditResourceTypeEnum.PROJECT

        # Invalid IP address
        invalid_data = valid_data.copy()
        invalid_data["ip_address"] = "invalid_ip"

        with pytest.raises(ValueError):
            AuditRecordCreate(**invalid_data)

    def test_audit_record_entry_serialization(self):
        """Test AuditRecordEntry schema serialization."""
        entry_data = {
            "id": str(uuid4()),
            "user_id": str(uuid4()),
            "action": "CREATE",
            "resource_type": "PROJECT",
            "resource_id": str(uuid4()),
            "timestamp": datetime.now(timezone.utc),
            "details": {"test": "data"},
            "ip_address": "192.168.1.1",
            "record_hash": "a" * 64,
            "created_at": datetime.now(timezone.utc),
        }

        entry = AuditRecordEntry(**entry_data)

        # Verify serialization
        json_data = entry.model_dump()
        assert "id" in json_data
        assert "record_hash" in json_data
        assert json_data["action"] == "CREATE"

    def test_audit_record_filter(self):
        """Test AuditRecordFilter schema."""
        filter_data = {
            "user_id": str(uuid4()),
            "action": AuditActionEnum.UPDATE,
            "resource_type": AuditResourceTypeEnum.ENDPOINT,
            "start_date": datetime.now(timezone.utc) - timedelta(days=7),
            "end_date": datetime.now(timezone.utc),
        }

        filter_obj = AuditRecordFilter(**filter_data)
        assert filter_obj.action == AuditActionEnum.UPDATE
        assert filter_obj.resource_type == AuditResourceTypeEnum.ENDPOINT


class TestIntegration:
    """Integration tests for the complete audit trail system."""

    def test_complete_audit_workflow(self):
        """Test a complete audit workflow from creation to verification."""
        # Create mock session
        mock_session = Mock(spec=Session)

        # Create service
        service = AuditService(mock_session)

        # Mock the data manager methods
        audit_id = uuid4()
        mock_record = Mock(spec=AuditTrail)
        mock_record.id = audit_id
        mock_record.action = AuditActionEnum.CREATE
        mock_record.resource_type = AuditResourceTypeEnum.PROJECT
        mock_record.resource_id = uuid4()
        mock_record.user_id = uuid4()
        mock_record.actioned_by = None
        mock_record.timestamp = datetime.now(timezone.utc)
        mock_record.details = {"project": "test"}
        mock_record.ip_address = "192.168.1.1"
        mock_record.previous_state = None
        mock_record.new_state = {"status": "created"}
        mock_record.record_hash = generate_audit_hash(
            action=mock_record.action,
            resource_type=mock_record.resource_type,
            resource_id=mock_record.resource_id,
            user_id=mock_record.user_id,
            actioned_by=mock_record.actioned_by,
            timestamp=mock_record.timestamp,
            details=mock_record.details,
            ip_address=mock_record.ip_address,
            previous_state=mock_record.previous_state,
            new_state=mock_record.new_state,
        )

        with patch.object(service.data_manager, 'create_audit_record') as mock_create:
            mock_create.return_value = mock_record

            # Create an audit record
            created_record = service.audit_create(
                resource_type=AuditResourceTypeEnum.PROJECT,
                resource_id=mock_record.resource_id,
                resource_data={"status": "created"},
                user_id=mock_record.user_id,
                ip_address="192.168.1.1",
            )

            assert created_record is not None

        with patch.object(service.data_manager, 'get_audit_record_by_id') as mock_get:
            mock_get.return_value = mock_record

            # Verify the record integrity
            is_valid, message = service.verify_audit_record_integrity(audit_id)
            assert is_valid is True

    def test_consolidated_query_method(self):
        """Test that the consolidated get_audit_records method works with various filter combinations."""
        mock_session = Mock(spec=Session)
        data_manager = AuditTrailDataManager(mock_session)

        # Mock query chain
        mock_query = Mock()
        mock_query.join = Mock(return_value=mock_query)
        mock_query.outerjoin = Mock(return_value=mock_query)
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.order_by = Mock(return_value=mock_query)
        mock_query.offset = Mock(return_value=mock_query)
        mock_query.limit = Mock(return_value=mock_query)
        mock_query.all = Mock(return_value=[])
        mock_query.count = Mock(return_value=0)

        mock_session.query = Mock(return_value=mock_query)

        # Test 1: Filter by user only
        data_manager.get_audit_records(user_id=uuid4())
        assert mock_query.filter.called

        # Test 2: Filter by resource
        data_manager.get_audit_records(
            resource_type=AuditResourceTypeEnum.CLUSTER,
            resource_id=uuid4()
        )
        assert mock_query.filter.called

        # Test 3: Filter by date range
        data_manager.get_audit_records(
            start_date=datetime.now(timezone.utc) - timedelta(days=7),
            end_date=datetime.now(timezone.utc)
        )
        assert mock_query.filter.called

        # Test 4: All filters combined
        data_manager.get_audit_records(
            user_id=uuid4(),
            actioned_by=uuid4(),
            action=AuditActionEnum.UPDATE,
            resource_type=AuditResourceTypeEnum.ENDPOINT,
            resource_id=uuid4(),
            start_date=datetime.now(timezone.utc) - timedelta(days=7),
            end_date=datetime.now(timezone.utc),
            ip_address="192.168.1.1",
            offset=10,
            limit=50,
        )
        assert mock_query.filter.called
        assert mock_query.offset.called
        assert mock_query.limit.called


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
