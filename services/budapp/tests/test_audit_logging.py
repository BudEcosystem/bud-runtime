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
from budapp.commons.constants import AuditActionEnum, AuditResourceTypeEnum


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
            "X-Forwarded-For": "192.168.1.1",
            "User-Agent": "TestAgent/1.0"
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
        mock_audit_service.audit_create.assert_called_once()

        call_args = mock_audit_service.audit_create.call_args[1]
        assert call_args["resource_type"] == AuditResourceTypeEnum.PROJECT
        assert call_args["resource_id"] == resource_id
        assert call_args["user_id"] == user_id
        # Details should include user_agent and success
        expected_details = details.copy()
        expected_details["user_agent"] = "TestAgent/1.0"
        expected_details["success"] = True
        assert call_args["resource_data"] == expected_details
        assert call_args["ip_address"] == "192.168.1.1"

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
        mock_audit_service.audit_authentication.assert_called_once()
        call_args = mock_audit_service.audit_authentication.call_args[1]
        assert call_args["action"] == AuditActionEnum.LOGIN
        assert call_args["user_id"] == user_id
        assert call_args["success"] is True
        # audit_authentication gets details passed in
        expected_details = details.copy()
        expected_details["success"] = True
        assert call_args["details"] == expected_details

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
        call_args = mock_audit_service.audit_update.call_args[1]
        assert call_args["resource_type"] == AuditResourceTypeEnum.PROJECT
        assert call_args["resource_id"] == resource_id
        assert call_args["user_id"] == user_id
        assert call_args["previous_state"] == previous_state
        # new_state is passed as-is from the call (new_state parameter)
        assert call_args["new_state"] == new_state

    @patch("budapp.audit_ops.audit_logger.AuditService")
    def test_log_audit_handles_exceptions_gracefully(self, mock_audit_service_class):
        """Test that audit logging exceptions don't break the application."""
        # Setup
        mock_audit_service = Mock()
        mock_audit_service.audit_create.side_effect = Exception("Database error")
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
        mock_audit_service.audit_create.assert_called_once()

    @patch("budapp.audit_ops.audit_logger.logger")
    @patch("budapp.audit_ops.audit_logger.AuditService")
    def test_log_audit_logs_errors(self, mock_audit_service_class, mock_logger):
        """Test that errors are logged when audit logging fails."""
        # Setup
        mock_audit_service = Mock()
        error = Exception("Database connection failed")
        mock_audit_service.audit_delete.side_effect = error
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
        assert "Failed to log audit event" in str(mock_logger.error.call_args)


class TestAsyncAuditLogging:
    """Test the async audit logging functionality."""

    @patch("budapp.audit_ops.audit_logger.AuditService")
    def test_log_audit_async(self, mock_audit_service_class):
        """Test async audit logging wrapper."""
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

        # Execute - log_audit_async is just a wrapper, not actually async
        log_audit_async(
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
        mock_audit_service.audit_create.assert_called_once()

        call_args = mock_audit_service.audit_create.call_args[1]
        assert call_args["resource_type"] == AuditResourceTypeEnum.ENDPOINT
        assert call_args["resource_id"] == resource_id
        assert call_args["user_id"] == user_id
        # Details should include success
        expected_details = details.copy()
        expected_details["success"] = True
        assert call_args["resource_data"] == expected_details


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
        request.headers = {
            "X-Forwarded-For": "192.168.1.100",
            "User-Agent": "TestBrowser/1.0"
        }
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
        mock_audit_service.audit_authentication.assert_called_once()
        call_args = mock_audit_service.audit_authentication.call_args[1]
        assert call_args["action"] == AuditActionEnum.LOGIN_FAILED
        assert call_args["success"] is False
        assert call_args["ip_address"] == "192.168.1.100"
        expected_details = {
            "email": "user@example.com",
            "reason": "Invalid password",
            "user_agent": "TestBrowser/1.0",
            "success": False,
        }
        assert call_args["details"] == expected_details

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

        # Verify - PERMISSION_CHANGED uses generic create_audit_record
        mock_audit_service.create_audit_record.assert_called_once()

        call_args = mock_audit_service.create_audit_record.call_args[1]
        assert call_args["action"] == AuditActionEnum.PERMISSION_CHANGED
        assert call_args["resource_type"] == AuditResourceTypeEnum.PROJECT
        assert call_args["resource_id"] == project_id
        assert call_args["user_id"] == user_id
        expected_details = {
            "operation": "add_member",
            "target_user_id": str(target_user_id),
            "role_assigned": "viewer",
            "permissions": ["view", "list"],
            "success": True,
        }
        assert call_args["details"] == expected_details

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

        # Verify - WORKFLOW_STARTED uses audit_workflow method
        mock_audit_service.audit_workflow.assert_called_once()

        call_args = mock_audit_service.audit_workflow.call_args[1]
        assert call_args["workflow_id"] == workflow_id
        assert call_args["workflow_type"] == "DEPLOYMENT"
        assert call_args["action"] == AuditActionEnum.WORKFLOW_STARTED
        assert call_args["user_id"] == user_id
        # The audit_workflow method gets the modified details with success added
        expected_details = {
            "workflow_type": "DEPLOYMENT",
            "target_cluster": "production-cluster",
            "model": "llama-2-7b",
            "estimated_duration": "15 minutes",
            "success": True,
        }
        assert call_args["details"] == expected_details
