"""Tests for audit export functionality."""

import csv
import io
from datetime import datetime, timezone
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from budapp.audit_ops.export_utils import (
    generate_csv_from_audit_records,
    generate_export_filename,
    sanitize_for_csv,
)
from budapp.audit_ops.models import AuditTrail
from budapp.commons.constants import AuditActionEnum, AuditResourceTypeEnum


class TestExportUtils:
    """Test export utility functions."""

    def test_generate_csv_from_audit_records(self):
        """Test CSV generation from audit records."""
        # Create mock audit records
        user_id = uuid4()
        resource_id = uuid4()

        record1 = Mock(spec=AuditTrail)
        record1.id = uuid4()
        record1.timestamp = datetime.now(timezone.utc)
        record1.user_id = user_id
        record1.actioned_by = None
        record1.action = AuditActionEnum.CREATE.value
        record1.resource_type = AuditResourceTypeEnum.PROJECT.value
        record1.resource_id = resource_id
        record1.resource_name = "Test Project"
        record1.ip_address = "192.168.1.1"
        record1.details = {"key": "value"}
        record1.previous_state = None
        record1.new_state = {"name": "New Project"}
        record1.record_hash = "a" * 64

        # Add user info
        record1.user = Mock()
        record1.user.email = "user@example.com"
        record1.user.name = "Test User"
        record1.actioned_by_user = None

        records = [record1]

        # Generate CSV
        csv_content = generate_csv_from_audit_records(records, include_user_info=True)

        # Parse CSV to verify content
        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)

        assert len(rows) == 1
        row = rows[0]

        assert row["User ID"] == str(user_id)
        assert row["User Email"] == "user@example.com"
        assert row["User Name"] == "Test User"
        assert row["Action"] == AuditActionEnum.CREATE.value
        assert row["Resource Type"] == AuditResourceTypeEnum.PROJECT.value
        assert row["Resource ID"] == str(resource_id)
        assert row["Resource Name"] == "Test Project"
        assert row["IP Address"] == "192.168.1.1"
        assert row["Record Hash"] == "a" * 64

    def test_generate_csv_without_user_info(self):
        """Test CSV generation without user info."""
        record = Mock(spec=AuditTrail)
        record.id = uuid4()
        record.timestamp = datetime.now(timezone.utc)
        record.user_id = uuid4()
        record.actioned_by = None
        record.action = AuditActionEnum.LOGIN.value
        record.resource_type = AuditResourceTypeEnum.USER.value
        record.resource_id = uuid4()
        record.resource_name = "User Login"
        record.ip_address = "10.0.0.1"
        record.details = {}
        record.previous_state = None
        record.new_state = None
        record.record_hash = "b" * 64

        records = [record]

        # Generate CSV without user info
        csv_content = generate_csv_from_audit_records(records, include_user_info=False)

        # Parse CSV
        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)

        assert len(rows) == 1
        row = rows[0]

        # User email and name should be empty
        assert row["User Email"] == ""
        assert row["User Name"] == ""

    def test_generate_csv_with_actioned_by(self):
        """Test CSV generation with actioned_by user."""
        record = Mock(spec=AuditTrail)
        record.id = uuid4()
        record.timestamp = datetime.now(timezone.utc)
        record.user_id = uuid4()
        record.actioned_by = uuid4()
        record.action = AuditActionEnum.UPDATE.value
        record.resource_type = AuditResourceTypeEnum.MODEL.value
        record.resource_id = uuid4()
        record.resource_name = "ML Model v2.1"
        record.ip_address = "172.16.0.1"
        record.details = {"field": "updated"}
        record.previous_state = {"status": "old"}
        record.new_state = {"status": "new"}
        record.record_hash = "c" * 64

        # Add actioned_by user info
        record.user = Mock()
        record.user.email = "user@example.com"
        record.user.name = "User"
        record.actioned_by_user = Mock()
        record.actioned_by_user.email = "admin@example.com"
        record.actioned_by_user.name = "Admin User"

        records = [record]

        csv_content = generate_csv_from_audit_records(records, include_user_info=True)

        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)

        assert len(rows) == 1
        row = rows[0]

        assert row["Actioned By ID"] == str(record.actioned_by)
        assert row["Actioned By Email"] == "admin@example.com"
        assert row["Actioned By Name"] == "Admin User"

    def test_sanitize_for_csv(self):
        """Test CSV value sanitization."""
        assert sanitize_for_csv(None) == ""
        assert sanitize_for_csv("normal text") == "normal text"
        assert sanitize_for_csv("text\x00with\x00nulls") == "textwith nulls"
        assert sanitize_for_csv(123) == "123"
        assert sanitize_for_csv({"key": "value"}) == "{'key': 'value'}"

    def test_generate_export_filename(self):
        """Test export filename generation."""
        filename = generate_export_filename(prefix="audit_export", extension="csv")

        assert filename.startswith("audit_export_")
        assert filename.endswith(".csv")

        # Check timestamp format
        parts = filename.split("_")
        assert len(parts) == 3  # prefix, date, time.extension

        # Different prefix and extension
        filename2 = generate_export_filename(prefix="test", extension="json")
        assert filename2.startswith("test_")
        assert filename2.endswith(".json")


class TestAuditExportEndpoint:
    """Test audit export endpoint functionality."""

    @pytest.fixture
    def mock_audit_service(self):
        """Mock audit service for testing."""
        with patch("budapp.audit_ops.audit_routes.AuditService") as mock_service:
            yield mock_service

    @pytest.fixture
    def mock_user(self):
        """Create a mock user."""
        user = Mock()
        user.id = uuid4()
        user.email = "test@example.com"
        user.name = "Test User"
        user.user_type = "ADMIN"
        user.permissions = ["USER_MANAGE"]
        return user

    @pytest.fixture
    def mock_records(self):
        """Create mock audit records."""
        records = []
        for i in range(3):
            record = Mock(spec=AuditTrail)
            record.id = uuid4()
            record.timestamp = datetime.now(timezone.utc)
            record.user_id = uuid4()
            record.actioned_by = None
            record.action = AuditActionEnum.CREATE.value
            record.resource_type = AuditResourceTypeEnum.PROJECT.value
            record.resource_id = uuid4()
            record.resource_name = f"Project {i}"
            record.ip_address = f"192.168.1.{i+1}"
            record.details = {"index": i}
            record.previous_state = None
            record.new_state = {"status": "active"}
            record.record_hash = f"{'a' * 63}{i}"

            # Add user info
            record.user = Mock()
            record.user.email = f"user{i}@example.com"
            record.user.name = f"User {i}"
            record.actioned_by_user = None

            records.append(record)

        return records

    def test_export_csv_parameter(self, mock_audit_service, mock_user, mock_records):
        """Test that export_csv parameter triggers CSV download."""
        from budapp.main import app

        # Mock the service to return records
        mock_service_instance = Mock()
        mock_service_instance.get_audit_records.return_value = (mock_records, len(mock_records))
        mock_audit_service.return_value = mock_service_instance

        with patch("budapp.audit_ops.audit_routes.get_current_active_user", return_value=mock_user):
            with patch("budapp.audit_ops.audit_routes.get_session"):
                client = TestClient(app)

                # Request with export_csv=true
                response = client.get(
                    "/audit/records?export_csv=true",
                    headers={"Authorization": "Bearer fake-token"}
                )

                assert response.status_code == status.HTTP_200_OK
                assert response.headers["content-type"] == "text/csv; charset=utf-8"
                assert "attachment" in response.headers.get("content-disposition", "")
                assert "audit_export" in response.headers.get("content-disposition", "")

                # Verify CSV content
                csv_content = response.text
                reader = csv.DictReader(io.StringIO(csv_content))
                rows = list(reader)

                assert len(rows) == 3
                for i, row in enumerate(rows):
                    assert row["User Email"] == f"user{i}@example.com"
                    assert row["Resource Name"] == f"Project {i}"
                    assert row["IP Address"] == f"192.168.1.{i+1}"

    def test_regular_json_response(self, mock_audit_service, mock_user, mock_records):
        """Test that without export_csv, JSON is returned."""
        from budapp.main import app

        # Mock the service
        mock_service_instance = Mock()
        mock_service_instance.get_audit_records.return_value = (mock_records, len(mock_records))
        mock_audit_service.return_value = mock_service_instance

        with patch("budapp.audit_ops.audit_routes.get_current_active_user", return_value=mock_user):
            with patch("budapp.audit_ops.audit_routes.get_session"):
                client = TestClient(app)

                # Request without export_csv
                response = client.get(
                    "/audit/records",
                    headers={"Authorization": "Bearer fake-token"}
                )

                assert response.status_code == status.HTTP_200_OK
                assert "application/json" in response.headers["content-type"]

                # Should return JSON response
                data = response.json()
                assert "data" in data
                assert "message" in data

    def test_csv_export_with_filters(self, mock_audit_service, mock_user, mock_records):
        """Test CSV export with filters applied."""
        from budapp.main import app

        # Mock the service
        mock_service_instance = Mock()
        mock_service_instance.get_audit_records.return_value = ([mock_records[0]], 1)
        mock_audit_service.return_value = mock_service_instance

        with patch("budapp.audit_ops.audit_routes.get_current_active_user", return_value=mock_user):
            with patch("budapp.audit_ops.audit_routes.get_session"):
                client = TestClient(app)

                # Request with filters and export
                response = client.get(
                    f"/audit/records?export_csv=true&action={AuditActionEnum.CREATE.value}",
                    headers={"Authorization": "Bearer fake-token"}
                )

                assert response.status_code == status.HTTP_200_OK
                assert response.headers["content-type"] == "text/csv; charset=utf-8"

                # Verify filtered content
                csv_content = response.text
                reader = csv.DictReader(io.StringIO(csv_content))
                rows = list(reader)

                assert len(rows) == 1

    def test_csv_export_client_user(self, mock_audit_service, mock_user, mock_records):
        """Test CSV export for CLIENT users only shows their records."""
        from budapp.main import app

        # Make user a CLIENT
        mock_user.user_type = "CLIENT"

        # Mock the service
        mock_service_instance = Mock()
        mock_service_instance.get_audit_records.return_value = ([mock_records[0]], 1)
        mock_audit_service.return_value = mock_service_instance

        with patch("budapp.audit_ops.audit_routes.get_current_active_user", return_value=mock_user):
            with patch("budapp.audit_ops.audit_routes.get_session"):
                client = TestClient(app)

                response = client.get(
                    "/audit/records?export_csv=true",
                    headers={"Authorization": "Bearer fake-token"}
                )

                assert response.status_code == status.HTTP_200_OK

                # Verify the service was called with user_id filter
                call_args = mock_service_instance.get_audit_records.call_args
                filter_params = call_args[1]["filter_params"]
                assert filter_params.user_id == mock_user.id

    def test_csv_export_includes_resource_name_column(self, mock_audit_service, mock_user, mock_records):
        """Test that CSV export includes resource_name column."""
        from budapp.main import app

        # Mock the service
        mock_service_instance = Mock()
        mock_service_instance.get_audit_records.return_value = (mock_records, len(mock_records))
        mock_audit_service.return_value = mock_service_instance

        with patch("budapp.audit_ops.audit_routes.get_current_active_user", return_value=mock_user):
            with patch("budapp.audit_ops.audit_routes.get_session"):
                client = TestClient(app)

                response = client.get(
                    "/audit/records?export_csv=true",
                    headers={"Authorization": "Bearer fake-token"}
                )

                assert response.status_code == status.HTTP_200_OK
                
                # Parse CSV and verify resource_name column exists
                csv_content = response.text
                reader = csv.DictReader(io.StringIO(csv_content))
                headers = reader.fieldnames
                
                assert "Resource Name" in headers
                
                # Verify resource_name values are populated
                rows = list(reader)
                for i, row in enumerate(rows):
                    assert row["Resource Name"] == f"Project {i}"

    def test_generate_csv_with_resource_name_filtering(self):
        """Test CSV generation when filtering by resource_name."""
        # Create records with different resource names
        records = []
        for i, name in enumerate(["Alpha Project", "Beta Project", "Alpha Model"]):
            record = Mock(spec=AuditTrail)
            record.id = uuid4()
            record.timestamp = datetime.now(timezone.utc)
            record.user_id = uuid4()
            record.actioned_by = None
            record.action = AuditActionEnum.CREATE.value
            record.resource_type = AuditResourceTypeEnum.PROJECT.value
            record.resource_id = uuid4()
            record.resource_name = name
            record.ip_address = f"192.168.1.{i+1}"
            record.details = {}
            record.previous_state = None
            record.new_state = None
            record.record_hash = f"{'a' * 63}{i}"
            
            record.user = Mock()
            record.user.email = f"user{i}@example.com"
            record.user.name = f"User {i}"
            record.actioned_by_user = None
            
            records.append(record)

        # Generate CSV
        csv_content = generate_csv_from_audit_records(records, include_user_info=True)
        
        # Parse and verify
        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)
        
        assert len(rows) == 3
        assert rows[0]["Resource Name"] == "Alpha Project"
        assert rows[1]["Resource Name"] == "Beta Project" 
        assert rows[2]["Resource Name"] == "Alpha Model"
