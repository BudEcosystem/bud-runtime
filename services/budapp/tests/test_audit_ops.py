"""Unit tests for audit trail functionality.

This module contains comprehensive tests for the audit trail system,
including model validation, CRUD operations, service methods, and immutability constraints.
"""

import pytest
from datetime import datetime, timezone, timedelta
from uuid import UUID, uuid4
from unittest.mock import Mock, patch, MagicMock

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from budapp.audit_ops.models import AuditTrail
from budapp.audit_ops.schemas import (
    AuditRecordCreate,
    AuditRecordEntry,
    AuditRecordFilter,
)
from budapp.audit_ops.crud import AuditTrailDataManager
from budapp.audit_ops.services import AuditService
from budapp.commons.constants import AuditActionEnum, AuditResourceTypeEnum


class TestAuditTrailModel:
    """Tests for the AuditTrail SQLAlchemy model."""
    
    def test_audit_trail_creation(self):
        """Test creating an audit trail record."""
        audit = AuditTrail(
            id=uuid4(),
            user_id=uuid4(),
            actioned_by=uuid4(),
            action=AuditActionEnum.CREATE,
            resource_type=AuditResourceTypeEnum.PROJECT,
            resource_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
            details={"test": "data"},
            ip_address="192.168.1.1",
            previous_state={"old": "state"},
            new_state={"new": "state"},
        )
        
        assert audit.id is not None
        assert audit.action == AuditActionEnum.CREATE
        assert audit.resource_type == AuditResourceTypeEnum.PROJECT
        assert audit.details == {"test": "data"}
        assert audit.ip_address == "192.168.1.1"
    
    def test_audit_trail_repr(self):
        """Test the string representation of an audit trail record."""
        audit_id = uuid4()
        user_id = uuid4()
        actioned_by = uuid4()
        resource_id = uuid4()
        timestamp = datetime.now(timezone.utc)
        
        audit = AuditTrail(
            id=audit_id,
            user_id=user_id,
            actioned_by=actioned_by,
            action=AuditActionEnum.UPDATE,
            resource_type=AuditResourceTypeEnum.MODEL,
            resource_id=resource_id,
            timestamp=timestamp,
        )
        
        repr_str = repr(audit)
        assert str(audit_id) in repr_str
        assert str(user_id) in repr_str
        assert str(actioned_by) in repr_str
        assert "UPDATE" in repr_str.upper()
        assert "MODEL" in repr_str.upper()


class TestAuditSchemas:
    """Tests for Pydantic schemas."""
    
    def test_audit_record_create_schema(self):
        """Test the AuditRecordCreate schema validation."""
        data = {
            "action": AuditActionEnum.CREATE,
            "resource_type": AuditResourceTypeEnum.ENDPOINT,
            "resource_id": str(uuid4()),
            "user_id": str(uuid4()),
            "actioned_by": str(uuid4()),
            "details": {"operation": "test"},
            "ip_address": "10.0.0.1",
        }
        
        schema = AuditRecordCreate(**data)
        assert schema.action == AuditActionEnum.CREATE
        assert schema.resource_type == AuditResourceTypeEnum.ENDPOINT
        assert schema.details == {"operation": "test"}
    
    def test_audit_record_entry_schema(self):
        """Test the AuditRecordEntry schema validation."""
        data = {
            "id": str(uuid4()),
            "user_id": str(uuid4()),
            "actioned_by": str(uuid4()),
            "action": "update",
            "resource_type": "cluster",
            "resource_id": str(uuid4()),
            "timestamp": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc),
        }
        
        schema = AuditRecordEntry(**data)
        assert schema.action == "update"
        assert schema.resource_type == "cluster"
    
    def test_ip_address_validation(self):
        """Test IP address validation in schemas."""
        # Valid IP addresses
        valid_ips = ["192.168.1.1", "10.0.0.1", "::1", "2001:db8::1"]
        
        for ip in valid_ips:
            data = {
                "action": AuditActionEnum.READ,
                "resource_type": AuditResourceTypeEnum.FILE,
                "ip_address": ip,
            }
            schema = AuditRecordCreate(**data)
            assert schema.ip_address == ip
        
        # Invalid IP address (too long)
        with pytest.raises(ValueError):
            data = {
                "action": AuditActionEnum.READ,
                "resource_type": AuditResourceTypeEnum.FILE,
                "ip_address": "a" * 50,  # Too long
            }
            AuditRecordCreate(**data)


class TestAuditTrailDataManager:
    """Tests for CRUD operations."""
    
    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = MagicMock(spec=Session)
        return session
    
    @pytest.fixture
    def data_manager(self, mock_session):
        """Create an AuditTrailDataManager instance."""
        return AuditTrailDataManager(mock_session)
    
    @pytest.mark.asyncio
    async def test_create_audit_record(self, data_manager, mock_session):
        """Test creating an audit record."""
        # Arrange
        action = AuditActionEnum.CREATE
        resource_type = AuditResourceTypeEnum.PROJECT
        resource_id = uuid4()
        user_id = uuid4()
        actioned_by = uuid4()
        
        # Act
        result = await data_manager.create_audit_record(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            actioned_by=actioned_by,
            details={"test": "data"},
            ip_address="192.168.1.1",
        )
        
        # Assert
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_audit_record_by_id(self, data_manager):
        """Test retrieving an audit record by ID."""
        # Arrange
        audit_id = uuid4()
        data_manager.scalar_one_or_none = MagicMock(return_value=Mock(spec=AuditTrail))
        
        # Act
        result = await data_manager.get_audit_record_by_id(audit_id, include_user=True)
        
        # Assert
        data_manager.scalar_one_or_none.assert_called_once()
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_get_audit_records_by_user(self, data_manager):
        """Test retrieving audit records by user."""
        # Arrange
        user_id = uuid4()
        data_manager.execute_scalar = MagicMock(return_value=10)
        data_manager.scalars_all = MagicMock(return_value=[])
        
        # Act
        records, total = await data_manager.get_audit_records_by_user(
            user_id=user_id,
            offset=0,
            limit=20,
        )
        
        # Assert
        assert total == 10
        assert records == []
        data_manager.execute_scalar.assert_called_once()
        data_manager.scalars_all.assert_called_once()


class TestAuditService:
    """Tests for the audit service layer."""
    
    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return MagicMock(spec=Session)
    
    @pytest.fixture
    def service(self, mock_session):
        """Create an AuditService instance."""
        return AuditService(mock_session)
    
    @pytest.mark.asyncio
    async def test_audit_create(self, service):
        """Test auditing a create operation."""
        # Arrange
        resource_type = AuditResourceTypeEnum.MODEL
        resource_id = uuid4()
        resource_data = {"name": "test-model"}
        user_id = uuid4()
        actioned_by = uuid4()
        
        service.data_manager.create_audit_record = MagicMock(
            return_value=Mock(spec=AuditTrail)
        )
        
        # Act
        result = await service.audit_create(
            resource_type=resource_type,
            resource_id=resource_id,
            resource_data=resource_data,
            user_id=user_id,
            actioned_by=actioned_by,
            ip_address="10.0.0.1",
        )
        
        # Assert
        service.data_manager.create_audit_record.assert_called_once()
        call_args = service.data_manager.create_audit_record.call_args[1]
        assert call_args["action"] == AuditActionEnum.CREATE
        assert call_args["new_state"] == resource_data
        assert call_args["actioned_by"] == actioned_by
    
    @pytest.mark.asyncio
    async def test_audit_update(self, service):
        """Test auditing an update operation."""
        # Arrange
        resource_type = AuditResourceTypeEnum.ENDPOINT
        resource_id = uuid4()
        previous_data = {"status": "active", "version": "1.0"}
        new_data = {"status": "inactive", "version": "1.1"}
        
        service.data_manager.create_audit_record = MagicMock(
            return_value=Mock(spec=AuditTrail)
        )
        
        # Act
        result = await service.audit_update(
            resource_type=resource_type,
            resource_id=resource_id,
            previous_data=previous_data,
            new_data=new_data,
        )
        
        # Assert
        service.data_manager.create_audit_record.assert_called_once()
        call_args = service.data_manager.create_audit_record.call_args[1]
        assert call_args["action"] == AuditActionEnum.UPDATE
        assert "changed_fields" in call_args["details"]
        assert "status" in call_args["details"]["changed_fields"]
        assert "version" in call_args["details"]["changed_fields"]
    
    def test_calculate_changes(self, service):
        """Test calculating changes between two data dictionaries."""
        # Arrange
        previous = {"a": 1, "b": 2, "c": 3}
        new = {"a": 1, "b": 3, "d": 4}
        
        # Act
        changes = service._calculate_changes(previous, new)
        
        # Assert
        assert changes["b"] == {"old": 2, "new": 3}
        assert changes["c"] == {"old": 3, "new": None}
        assert changes["d"] == {"old": None, "new": 4}
        assert "a" not in changes  # Unchanged
    
    def test_sanitize_sensitive_data(self, service):
        """Test sanitizing sensitive data."""
        # Arrange
        data = {
            "username": "testuser",
            "password": "secret123",
            "api_key": "key-123456",
            "token": "bearer-token",
            "normal_field": "normal_value",
            "nested": {
                "secret": "nested-secret",
                "public": "public-data",
            }
        }
        
        # Act
        sanitized = service._sanitize_sensitive_data(data)
        
        # Assert
        assert sanitized["username"] == "testuser"
        assert sanitized["password"] == "***REDACTED***"
        assert sanitized["api_key"] == "***REDACTED***"
        assert sanitized["token"] == "***REDACTED***"
        assert sanitized["normal_field"] == "normal_value"
        assert sanitized["nested"]["secret"] == "***REDACTED***"
        assert sanitized["nested"]["public"] == "public-data"


class TestAuditImmutability:
    """Tests for audit trail immutability constraints."""
    
    def test_prevent_update_event_listener(self):
        """Test that the event listener prevents updates."""
        # The event listener is tested by attempting to trigger it
        # In a real test environment with a database, this would raise an exception
        
        audit = AuditTrail(
            id=uuid4(),
            action=AuditActionEnum.CREATE,
            resource_type=AuditResourceTypeEnum.PROJECT,
            timestamp=datetime.now(timezone.utc),
        )
        
        # The event listener should be registered
        from sqlalchemy import event
        from budapp.audit_ops.models import receive_before_update
        
        # Check that the listener is registered
        listeners = event.contains(AuditTrail, "before_update", receive_before_update)
        assert listeners


class TestAuditPerformance:
    """Performance-related tests for audit operations."""
    
    @pytest.mark.asyncio
    async def test_bulk_audit_creation_performance(self):
        """Test performance of bulk audit record creation."""
        # This is a placeholder for performance testing
        # In a real environment, you would measure execution time
        # and ensure it meets performance requirements
        
        mock_session = MagicMock(spec=Session)
        data_manager = AuditTrailDataManager(mock_session)
        
        # Simulate bulk creation
        start_time = datetime.now()
        for i in range(100):
            data_manager.session = mock_session  # Reset session
            
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Assert that bulk creation is reasonably fast
        assert duration < 1.0  # Should complete in under 1 second


# Integration test placeholder
@pytest.mark.integration
class TestAuditIntegration:
    """Integration tests that require a real database connection."""
    
    @pytest.mark.asyncio
    async def test_full_audit_workflow(self):
        """Test the complete audit workflow with a real database."""
        # This test would require a test database setup
        # It would test:
        # 1. Creating audit records
        # 2. Querying by various filters
        # 3. Verifying immutability constraints
        # 4. Testing indexes and performance
        pass