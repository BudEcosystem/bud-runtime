"""Tests for the simple audit logging functionality."""

import json
from datetime import datetime, timezone
from typing import Dict, Any
from unittest.mock import Mock, patch, MagicMock
from uuid import uuid4

import pytest
from fastapi import Request
from sqlalchemy.orm import Session

from budapp.audit_ops import log_audit, log_audit_async
from budapp.audit_ops.audit_logger import (
    extract_ip_from_request,
    extract_user_agent_from_request,
    mask_sensitive_data,
)
from budapp.commons.constants import AuditActionEnum, AuditResourceTypeEnum


class TestAuditLoggingUtilities:
    """Test utility functions for audit logging."""

    def test_mask_sensitive_data(self):
        """Test that sensitive data is properly masked."""
        input_data = {
            "username": "john.doe",
            "password": "secret123",
            "api_key": "sk-1234567890",
            "token": "bearer-token-xyz",
            "secret": "my-secret",
            "credit_card": "4111111111111111",
            "normal_field": "normal_value",
            "nested": {
                "password": "nested_password",
                "data": "nested_data",
            }
        }

        result = mask_sensitive_data(input_data)

        assert result["username"] == "john.doe"
        assert result["password"] == "***REDACTED***"
        assert result["api_key"] == "***REDACTED***"
        assert result["token"] == "***REDACTED***"
        assert result["secret"] == "***REDACTED***"
        assert result["credit_card"] == "***REDACTED***"
        assert result["normal_field"] == "normal_value"
        assert result["nested"]["password"] == "***REDACTED***"
        assert result["nested"]["data"] == "nested_data"

    def test_extract_ip_from_request(self):
        """Test IP address extraction from request."""
        # Test with X-Forwarded-For header
        request = Mock(spec=Request)
        request.headers = {"x-forwarded-for": "192.168.1.1, 10.0.0.1"}
        request.client = Mock(host="127.0.0.1")

        ip = extract_ip_from_request(request)
        assert ip == "192.168.1.1"

        # Test without X-Forwarded-For header
        request = Mock(spec=Request)
        request.headers = {}
        request.client = Mock(host="10.0.0.2")

        ip = extract_ip_from_request(request)
        assert ip == "10.0.0.2"

        # Test with no client
        request = Mock(spec=Request)
        request.headers = {}
        request.client = None

        ip = extract_ip_from_request(request)
        assert ip is None

    def test_extract_user_agent_from_request(self):
        """Test user agent extraction from request."""
        request = Mock(spec=Request)
        request.headers = {"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

        user_agent = extract_user_agent_from_request(request)
        assert user_agent == "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

        # Test without user-agent header
        request = Mock(spec=Request)
        request.headers = {}

        user_agent = extract_user_agent_from_request(request)
        assert user_agent is None


class TestAuditLogging:
    """Test the main audit logging functions."""

    @patch("budapp.audit_ops.audit_logger.AuditService")
    def test_log_audit_success(self, mock_audit_service_class):
        """Test successful audit logging."""
        # Setup
        mock_audit_service = Mock()
        mock_audit_service_class.return_value = mock_audit_service

        session = Mock(spec=Session)
        user_id = uuid4()
        resource_id = uuid4()
        request = Mock(spec=Request)
        request.headers = {
            "x-forwarded-for": "192.168.1.1",
            "user-agent": "TestAgent/1.0"
        }
        request.client = Mock(host="127.0.0.1")

        details = {
            "project_name": "Test Project",
            "description": "Test Description",
        }

        # Execute
        log_audit(
            session=session,
            action=AuditActionEnum.CREATE,
            resource_type=AuditResourceTypeEnum.PROJECT,
            resource_id=resource_id,
            user_id=user_id,
            details=details,
            request=request,
            success=True,
        )

        # Verify
        mock_audit_service_class.assert_called_once_with(session)
        mock_audit_service.create_audit_record.assert_called_once()

        call_args = mock_audit_service.create_audit_record.call_args[1]
        assert call_args["action"] == AuditActionEnum.CREATE
        assert call_args["resource_type"] == AuditResourceTypeEnum.PROJECT
        assert call_args["resource_id"] == resource_id
        assert call_args["user_id"] == user_id
        assert call_args["details"] == details
        assert call_args["ip_address"] == "192.168.1.1"
        assert call_args["user_agent"] == "TestAgent/1.0"
        assert call_args["success"] is True

    @patch("budapp.audit_ops.audit_logger.AuditService")
    def test_log_audit_with_sensitive_data(self, mock_audit_service_class):
        """Test that sensitive data is masked before logging."""
        # Setup
        mock_audit_service = Mock()
        mock_audit_service_class.return_value = mock_audit_service

        session = Mock(spec=Session)
        user_id = uuid4()

        details = {
            "username": "john.doe",
            "password": "secret123",
            "api_key": "sk-1234567890",
        }

        # Execute
        log_audit(
            session=session,
            action=AuditActionEnum.LOGIN,
            resource_type=AuditResourceTypeEnum.USER,
            user_id=user_id,
            details=details,
            success=True,
        )

        # Verify
        call_args = mock_audit_service.create_audit_record.call_args[1]
        assert call_args["details"]["username"] == "john.doe"
        assert call_args["details"]["password"] == "***REDACTED***"
        assert call_args["details"]["api_key"] == "***REDACTED***"

    @patch("budapp.audit_ops.audit_logger.AuditService")
    def test_log_audit_with_previous_and_new_state(self, mock_audit_service_class):
        """Test audit logging with state changes."""
        # Setup
        mock_audit_service = Mock()
        mock_audit_service_class.return_value = mock_audit_service

        session = Mock(spec=Session)
        user_id = uuid4()
        resource_id = uuid4()

        previous_state = {
            "name": "Old Project",
            "description": "Old Description",
        }

        new_state = {
            "name": "New Project",
            "description": "New Description",
        }

        # Execute
        log_audit(
            session=session,
            action=AuditActionEnum.UPDATE,
            resource_type=AuditResourceTypeEnum.PROJECT,
            resource_id=resource_id,
            user_id=user_id,
            previous_state=previous_state,
            new_state=new_state,
            success=True,
        )

        # Verify
        call_args = mock_audit_service.create_audit_record.call_args[1]
        assert call_args["previous_state"] == previous_state
        assert call_args["new_state"] == new_state

    @patch("budapp.audit_ops.audit_logger.AuditService")
    def test_log_audit_handles_exceptions_gracefully(self, mock_audit_service_class):
        """Test that audit logging exceptions don't break the application."""
        # Setup
        mock_audit_service = Mock()
        mock_audit_service.create_audit_record.side_effect = Exception("Database error")
        mock_audit_service_class.return_value = mock_audit_service

        session = Mock(spec=Session)

        # Execute - should not raise exception
        log_audit(
            session=session,
            action=AuditActionEnum.CREATE,
            resource_type=AuditResourceTypeEnum.PROJECT,
            success=True,
        )

        # Verify no exception was raised
        mock_audit_service.create_audit_record.assert_called_once()

    @patch("budapp.audit_ops.audit_logger.logger")
    @patch("budapp.audit_ops.audit_logger.AuditService")
    def test_log_audit_logs_errors(self, mock_audit_service_class, mock_logger):
        """Test that errors are logged when audit logging fails."""
        # Setup
        mock_audit_service = Mock()
        error = Exception("Database connection failed")
        mock_audit_service.create_audit_record.side_effect = error
        mock_audit_service_class.return_value = mock_audit_service

        session = Mock(spec=Session)

        # Execute
        log_audit(
            session=session,
            action=AuditActionEnum.DELETE,
            resource_type=AuditResourceTypeEnum.CLUSTER,
            success=False,
        )

        # Verify error was logged
        mock_logger.error.assert_called_once()
        assert "Failed to create audit record" in str(mock_logger.error.call_args)


class TestAsyncAuditLogging:
    """Test the async audit logging functionality."""

    @pytest.mark.asyncio
    @patch("budapp.audit_ops.audit_logger.AuditService")
    async def test_log_audit_async(self, mock_audit_service_class):
        """Test async audit logging."""
        # Setup
        mock_audit_service = Mock()
        mock_audit_service_class.return_value = mock_audit_service

        session = Mock(spec=Session)
        user_id = uuid4()
        resource_id = uuid4()

        details = {
            "endpoint_name": "test-endpoint",
            "model": "gpt-4",
        }

        # Execute
        await log_audit_async(
            session=session,
            action=AuditActionEnum.CREATE,
            resource_type=AuditResourceTypeEnum.ENDPOINT,
            resource_id=resource_id,
            user_id=user_id,
            details=details,
            success=True,
        )

        # Verify
        mock_audit_service_class.assert_called_once_with(session)
        mock_audit_service.create_audit_record.assert_called_once()

        call_args = mock_audit_service.create_audit_record.call_args[1]
        assert call_args["action"] == AuditActionEnum.CREATE
        assert call_args["resource_type"] == AuditResourceTypeEnum.ENDPOINT
        assert call_args["resource_id"] == resource_id
        assert call_args["user_id"] == user_id
        assert call_args["details"] == details


class TestIntegrationScenarios:
    """Test real-world integration scenarios."""

    @patch("budapp.audit_ops.audit_logger.AuditService")
    def test_failed_login_audit(self, mock_audit_service_class):
        """Test audit logging for failed login attempts."""
        # Setup
        mock_audit_service = Mock()
        mock_audit_service_class.return_value = mock_audit_service

        session = Mock(spec=Session)
        request = Mock(spec=Request)
        request.headers = {"x-forwarded-for": "192.168.1.100"}
        request.client = Mock(host="192.168.1.100")

        # Execute
        log_audit(
            session=session,
            action=AuditActionEnum.LOGIN_FAILED,
            resource_type=AuditResourceTypeEnum.USER,
            details={
                "email": "user@example.com",
                "reason": "Invalid password",
            },
            request=request,
            success=False,
        )

        # Verify
        call_args = mock_audit_service.create_audit_record.call_args[1]
        assert call_args["action"] == AuditActionEnum.LOGIN_FAILED
        assert call_args["success"] is False
        assert call_args["ip_address"] == "192.168.1.100"
        assert call_args["details"]["reason"] == "Invalid password"

    @patch("budapp.audit_ops.audit_logger.AuditService")
    def test_permission_change_audit(self, mock_audit_service_class):
        """Test audit logging for permission changes."""
        # Setup
        mock_audit_service = Mock()
        mock_audit_service_class.return_value = mock_audit_service

        session = Mock(spec=Session)
        user_id = uuid4()
        project_id = uuid4()
        target_user_id = uuid4()

        # Execute
        log_audit(
            session=session,
            action=AuditActionEnum.PERMISSION_CHANGED,
            resource_type=AuditResourceTypeEnum.PROJECT,
            resource_id=project_id,
            user_id=user_id,
            details={
                "operation": "add_member",
                "target_user_id": str(target_user_id),
                "role_assigned": "viewer",
                "permissions": ["view", "list"],
            },
            success=True,
        )

        # Verify
        call_args = mock_audit_service.create_audit_record.call_args[1]
        assert call_args["action"] == AuditActionEnum.PERMISSION_CHANGED
        assert call_args["resource_type"] == AuditResourceTypeEnum.PROJECT
        assert call_args["details"]["operation"] == "add_member"
        assert call_args["details"]["role_assigned"] == "viewer"

    @patch("budapp.audit_ops.audit_logger.AuditService")
    def test_workflow_audit(self, mock_audit_service_class):
        """Test audit logging for workflow events."""
        # Setup
        mock_audit_service = Mock()
        mock_audit_service_class.return_value = mock_audit_service

        session = Mock(spec=Session)
        user_id = uuid4()
        workflow_id = uuid4()

        # Execute
        log_audit(
            session=session,
            action=AuditActionEnum.WORKFLOW_STARTED,
            resource_type=AuditResourceTypeEnum.WORKFLOW,
            resource_id=workflow_id,
            user_id=user_id,
            details={
                "workflow_type": "DEPLOYMENT",
                "target_cluster": "production-cluster",
                "model": "llama-2-7b",
                "estimated_duration": "15 minutes",
            },
            success=True,
        )

        # Verify
        call_args = mock_audit_service.create_audit_record.call_args[1]
        assert call_args["action"] == AuditActionEnum.WORKFLOW_STARTED
        assert call_args["resource_type"] == AuditResourceTypeEnum.WORKFLOW
        assert call_args["details"]["workflow_type"] == "DEPLOYMENT"
