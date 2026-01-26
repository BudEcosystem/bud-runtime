"""Tests for integration actions."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from budpipeline.actions.base import ActionContext
from budpipeline.actions.integration import (
    HttpRequestAction,
    HttpRequestExecutor,
    NotificationAction,
    NotificationExecutor,
)


def make_context(**params) -> ActionContext:
    """Create a test ActionContext."""
    return ActionContext(
        step_id="test_step",
        execution_id="test_execution",
        params=params,
        workflow_params={},
        step_outputs={},
    )


class TestHttpRequestAction:
    """Tests for HttpRequestAction."""

    def test_meta_attributes(self) -> None:
        """Test action metadata attributes."""
        meta = HttpRequestAction.meta
        assert meta.type == "http_request"
        assert meta.name == "HTTP Request"
        assert meta.category == "Integration"
        assert meta.execution_mode.value == "sync"
        assert meta.idempotent is False

    def test_validate_params_missing_url(self) -> None:
        """Test validation catches missing url."""
        executor = HttpRequestExecutor()
        errors = executor.validate_params({})
        assert any("url" in e for e in errors)

    def test_validate_params_invalid_url(self) -> None:
        """Test validation catches invalid URL format."""
        executor = HttpRequestExecutor()
        errors = executor.validate_params({"url": "not-a-url"})
        assert any("http://" in e or "https://" in e for e in errors)

    def test_validate_params_invalid_method(self) -> None:
        """Test validation catches invalid HTTP method."""
        executor = HttpRequestExecutor()
        errors = executor.validate_params({"url": "https://example.com", "method": "INVALID"})
        assert any("method" in e for e in errors)

    def test_validate_params_valid(self) -> None:
        """Test validation passes with valid params."""
        executor = HttpRequestExecutor()
        errors = executor.validate_params(
            {"url": "https://api.example.com/endpoint", "method": "POST"}
        )
        assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_execute_get_success(self) -> None:
        """Test successful GET request execution."""
        executor = HttpRequestExecutor()
        context = make_context(url="https://api.example.com/data", method="GET")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = {"data": "test"}
        mock_response.headers = {"content-type": "application/json"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(
                return_value=MagicMock(request=AsyncMock(return_value=mock_response))
            )
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await executor.execute(context)

        assert result.success is True
        assert result.outputs["status_code"] == 200
        assert result.outputs["body"] == {"data": "test"}

    @pytest.mark.asyncio
    async def test_execute_post_with_body(self) -> None:
        """Test POST request with JSON body."""
        executor = HttpRequestExecutor()
        context = make_context(
            url="https://api.example.com/items",
            method="POST",
            body={"name": "test item"},
        )

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.is_success = True
        mock_response.json.return_value = {"id": "123", "name": "test item"}
        mock_response.headers = {"content-type": "application/json"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.request = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await executor.execute(context)

        assert result.success is True
        assert result.outputs["status_code"] == 201

    @pytest.mark.asyncio
    async def test_execute_timeout(self) -> None:
        """Test request timeout handling."""
        executor = HttpRequestExecutor()
        context = make_context(url="https://api.example.com/slow", timeout_seconds=5)

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.request = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await executor.execute(context)

        assert result.success is False
        assert "timed out" in result.error.lower()
        assert result.outputs["status_code"] == 0

    @pytest.mark.asyncio
    async def test_execute_http_error(self) -> None:
        """Test HTTP error status handling."""
        executor = HttpRequestExecutor()
        context = make_context(url="https://api.example.com/not-found")

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.is_success = False
        mock_response.json.return_value = {"error": "Not found"}
        mock_response.headers = {}

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.request = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await executor.execute(context)

        assert result.success is False
        assert result.outputs["status_code"] == 404

    @pytest.mark.asyncio
    async def test_execute_connection_error(self) -> None:
        """Test connection error handling."""
        executor = HttpRequestExecutor()
        context = make_context(url="https://api.example.com/data")

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.request = AsyncMock(side_effect=httpx.ConnectError("Connection failed"))
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await executor.execute(context)

        assert result.success is False
        assert "failed" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_ssrf_blocked_localhost(self) -> None:
        """Test SSRF protection blocks localhost."""
        executor = HttpRequestExecutor()
        context = make_context(url="http://localhost:8080/admin")

        result = await executor.execute(context)

        assert result.success is False
        assert "ssrf" in result.error.lower() or "blocked" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_ssrf_blocked_private_ip(self) -> None:
        """Test SSRF protection blocks private IP ranges."""
        executor = HttpRequestExecutor()
        context = make_context(url="http://192.168.1.1/admin")

        result = await executor.execute(context)

        assert result.success is False
        assert "blocked" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_ssrf_blocked_internal_ip(self) -> None:
        """Test SSRF protection blocks 10.x.x.x internal IPs."""
        executor = HttpRequestExecutor()
        context = make_context(url="http://10.0.0.1:3000/internal")

        result = await executor.execute(context)

        assert result.success is False
        assert "blocked" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_ssrf_blocked_loopback(self) -> None:
        """Test SSRF protection blocks 127.x.x.x loopback."""
        executor = HttpRequestExecutor()
        context = make_context(url="http://127.0.0.1:9000/secret")

        result = await executor.execute(context)

        assert result.success is False
        assert "blocked" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_ssrf_blocked_metadata(self) -> None:
        """Test SSRF protection blocks cloud metadata endpoints."""
        executor = HttpRequestExecutor()
        context = make_context(url="http://169.254.169.254/latest/meta-data")

        result = await executor.execute(context)

        assert result.success is False
        assert "blocked" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_with_metadata(self) -> None:
        """Test HTTP request includes workflow metadata when enabled."""
        executor = HttpRequestExecutor()
        context = make_context(
            url="https://webhook.example.com/trigger",
            method="POST",
            body={"data": "test"},
            include_metadata=True,
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = {"ok": True}
        mock_response.headers = {"content-type": "application/json"}

        captured_payload = None

        async def capture_request(method, url, **kwargs):
            nonlocal captured_payload
            captured_payload = kwargs.get("json")
            return mock_response

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.request = AsyncMock(side_effect=capture_request)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await executor.execute(context)

        assert result.success is True
        assert "_workflow_metadata" in captured_payload
        assert captured_payload["_workflow_metadata"]["execution_id"] == "test_execution"
        assert captured_payload["_workflow_metadata"]["step_id"] == "test_step"

    @pytest.mark.asyncio
    async def test_execute_without_metadata(self) -> None:
        """Test HTTP request excludes metadata when disabled (default)."""
        executor = HttpRequestExecutor()
        context = make_context(
            url="https://api.example.com/data",
            method="POST",
            body={"data": "test"},
            include_metadata=False,
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = {"ok": True}
        mock_response.headers = {"content-type": "application/json"}

        captured_payload = None

        async def capture_request(method, url, **kwargs):
            nonlocal captured_payload
            captured_payload = kwargs.get("json")
            return mock_response

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.request = AsyncMock(side_effect=capture_request)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await executor.execute(context)

        assert result.success is True
        assert "_workflow_metadata" not in captured_payload


class TestNotificationAction:
    """Tests for NotificationAction."""

    def test_meta_attributes(self) -> None:
        """Test action metadata attributes."""
        meta = NotificationAction.meta
        assert meta.type == "notification"
        assert meta.name == "Send Notification"
        assert meta.category == "Integration"
        assert meta.execution_mode.value == "sync"
        assert "budnotify" in meta.required_services

    def test_validate_params_missing_channel(self) -> None:
        """Test validation catches missing channel."""
        executor = NotificationExecutor()
        errors = executor.validate_params({"message": "Test message"})
        assert any("channel" in e for e in errors)

    def test_validate_params_missing_message(self) -> None:
        """Test validation catches missing message."""
        executor = NotificationExecutor()
        errors = executor.validate_params({"channel": "email"})
        assert any("message" in e for e in errors)

    def test_validate_params_invalid_channel(self) -> None:
        """Test validation catches invalid channel."""
        executor = NotificationExecutor()
        errors = executor.validate_params({"channel": "invalid_channel", "message": "Test"})
        assert any("channel" in e for e in errors)

    def test_validate_params_invalid_severity(self) -> None:
        """Test validation catches invalid severity."""
        executor = NotificationExecutor()
        errors = executor.validate_params(
            {"channel": "email", "message": "Test", "severity": "invalid"}
        )
        assert any("severity" in e for e in errors)

    def test_validate_params_valid(self) -> None:
        """Test validation passes with valid params."""
        executor = NotificationExecutor()
        errors = executor.validate_params(
            {"channel": "slack", "message": "Test notification", "severity": "warning"}
        )
        assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_execute_success(self) -> None:
        """Test successful notification send."""
        executor = NotificationExecutor()
        context = make_context(
            channel="email",
            message="Test notification",
            title="Test Title",
            severity="info",
        )

        with patch(
            "budpipeline.actions.integration.notification.publish_to_pubsub",
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = await executor.execute(context)

        assert result.success is True
        assert result.outputs["sent"] is True
        assert "notification_id" in result.outputs

    @pytest.mark.asyncio
    async def test_execute_with_recipients(self) -> None:
        """Test notification with recipients."""
        executor = NotificationExecutor()
        context = make_context(
            channel="slack",
            message="Test message",
            recipients=["#general", "@user"],
        )

        with patch(
            "budpipeline.actions.integration.notification.publish_to_pubsub",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_publish:
            result = await executor.execute(context)

        assert result.success is True
        # Verify recipients were included in the publish call
        call_args = mock_publish.call_args
        assert call_args[1]["data"]["recipients"] == ["#general", "@user"]

    @pytest.mark.asyncio
    async def test_execute_publish_failure(self) -> None:
        """Test handling of publish failure."""
        executor = NotificationExecutor()
        context = make_context(channel="email", message="Test")

        with patch(
            "budpipeline.actions.integration.notification.publish_to_pubsub",
            new_callable=AsyncMock,
            side_effect=httpx.HTTPStatusError(
                "Error",
                request=MagicMock(),
                response=MagicMock(status_code=500),
            ),
        ):
            result = await executor.execute(context)

        assert result.success is False
        assert result.outputs["sent"] is False

    @pytest.mark.asyncio
    async def test_execute_timeout(self) -> None:
        """Test handling of publish timeout."""
        executor = NotificationExecutor()
        context = make_context(channel="teams", message="Test")

        with patch(
            "budpipeline.actions.integration.notification.publish_to_pubsub",
            new_callable=AsyncMock,
            side_effect=httpx.TimeoutException("Timeout"),
        ):
            result = await executor.execute(context)

        assert result.success is False
        assert "timed out" in result.error.lower()


class TestIntegrationActionsRegistration:
    """Tests for action registration."""

    def test_all_actions_have_executor_class(self) -> None:
        """Test all integration actions have executor_class defined."""
        assert hasattr(HttpRequestAction, "executor_class")
        assert hasattr(NotificationAction, "executor_class")

    def test_all_actions_have_meta(self) -> None:
        """Test all integration actions have meta defined."""
        assert hasattr(HttpRequestAction, "meta")
        assert hasattr(NotificationAction, "meta")

    def test_executor_classes_are_correct_type(self) -> None:
        """Test executor classes are subclasses of BaseActionExecutor."""
        from budpipeline.actions.base import BaseActionExecutor

        assert issubclass(HttpRequestExecutor, BaseActionExecutor)
        assert issubclass(NotificationExecutor, BaseActionExecutor)

    def test_unique_action_types(self) -> None:
        """Test all actions have unique type identifiers."""
        types = [
            HttpRequestAction.meta.type,
            NotificationAction.meta.type,
        ]
        assert len(types) == len(set(types))

    def test_all_actions_have_params_defined(self) -> None:
        """Test all actions have parameters defined."""
        assert len(HttpRequestAction.meta.params) > 0
        assert len(NotificationAction.meta.params) > 0

    def test_all_actions_have_outputs_defined(self) -> None:
        """Test all actions have outputs defined."""
        assert len(HttpRequestAction.meta.outputs) > 0
        assert len(NotificationAction.meta.outputs) > 0
