"""Tests for notification workflow handlers.

Tests NotificationHandler and WebhookHandler functionality.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from budpipeline.handlers.base import HandlerContext
from budpipeline.handlers.notification_handlers import (
    NotificationHandler,
    WebhookHandler,
    publish_to_pubsub,
)


@pytest.fixture
def notification_handler() -> NotificationHandler:
    """Create a NotificationHandler instance."""
    return NotificationHandler()


@pytest.fixture
def webhook_handler() -> WebhookHandler:
    """Create a WebhookHandler instance."""
    return WebhookHandler()


@pytest.fixture
def notification_context() -> HandlerContext:
    """Create a context for notification testing."""
    return HandlerContext(
        step_id="notify",
        execution_id="test-exec-001",
        params={
            "channel": "slack",
            "message": "Test notification message",
            "title": "Test Title",
            "severity": "info",
        },
        workflow_params={},
        step_outputs={},
    )


@pytest.fixture
def webhook_context() -> HandlerContext:
    """Create a context for webhook testing."""
    return HandlerContext(
        step_id="webhook",
        execution_id="test-exec-001",
        params={
            "url": "https://example.com/webhook",
            "payload": {"key": "value"},
            "method": "POST",
        },
        workflow_params={},
        step_outputs={},
    )


class TestNotificationHandler:
    """Tests for NotificationHandler."""

    def test_handler_metadata(self, notification_handler: NotificationHandler) -> None:
        """Should have correct metadata."""
        assert notification_handler.action_type == "notification"
        assert notification_handler.name == "Send Notification"
        assert notification_handler.description is not None

    def test_get_required_params(self, notification_handler: NotificationHandler) -> None:
        """Should require channel and message parameters."""
        required = notification_handler.get_required_params()
        assert "channel" in required
        assert "message" in required

    def test_get_optional_params(self, notification_handler: NotificationHandler) -> None:
        """Should have title, severity, metadata, and recipients as optional."""
        optional = notification_handler.get_optional_params()
        assert "title" in optional
        assert "severity" in optional
        assert "metadata" in optional
        assert "recipients" in optional

    def test_get_output_names(self, notification_handler: NotificationHandler) -> None:
        """Should output sent and notification_id."""
        outputs = notification_handler.get_output_names()
        assert "sent" in outputs
        assert "notification_id" in outputs

    def test_validate_params_missing_channel(
        self, notification_handler: NotificationHandler
    ) -> None:
        """Should fail validation without channel."""
        errors = notification_handler.validate_params({"message": "test"})
        assert any("channel" in e for e in errors)

    def test_validate_params_missing_message(
        self, notification_handler: NotificationHandler
    ) -> None:
        """Should fail validation without message."""
        errors = notification_handler.validate_params({"channel": "slack"})
        assert any("message" in e for e in errors)

    def test_validate_params_valid(self, notification_handler: NotificationHandler) -> None:
        """Should pass validation with channel and message."""
        errors = notification_handler.validate_params(
            {
                "channel": "slack",
                "message": "test message",
            }
        )
        assert len(errors) == 0

    def test_validate_params_invalid_channel(
        self, notification_handler: NotificationHandler
    ) -> None:
        """Should fail validation with invalid channel."""
        errors = notification_handler.validate_params(
            {
                "channel": "invalid_channel",
                "message": "test",
            }
        )
        assert any("channel" in e for e in errors)

    def test_validate_params_valid_channels(
        self, notification_handler: NotificationHandler
    ) -> None:
        """Should accept all valid channels."""
        valid_channels = ["email", "slack", "teams", "webhook"]
        for channel in valid_channels:
            errors = notification_handler.validate_params(
                {
                    "channel": channel,
                    "message": "test",
                }
            )
            assert len(errors) == 0, f"Channel {channel} should be valid"

    def test_validate_params_invalid_severity(
        self, notification_handler: NotificationHandler
    ) -> None:
        """Should fail validation with invalid severity."""
        errors = notification_handler.validate_params(
            {
                "channel": "slack",
                "message": "test",
                "severity": "invalid_severity",
            }
        )
        assert any("severity" in e for e in errors)

    def test_validate_params_valid_severities(
        self, notification_handler: NotificationHandler
    ) -> None:
        """Should accept all valid severities."""
        valid_severities = ["info", "warning", "error", "critical"]
        for severity in valid_severities:
            errors = notification_handler.validate_params(
                {
                    "channel": "slack",
                    "message": "test",
                    "severity": severity,
                }
            )
            assert len(errors) == 0, f"Severity {severity} should be valid"

    @pytest.mark.asyncio
    async def test_execute_success(
        self,
        notification_handler: NotificationHandler,
        notification_context: HandlerContext,
    ) -> None:
        """Should execute successfully when pubsub publish succeeds."""
        with patch(
            "budpipeline.handlers.notification_handlers.publish_to_pubsub",
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = await notification_handler.execute(notification_context)

        assert result.success is True
        assert result.outputs["sent"] is True
        assert result.outputs["notification_id"] is not None
        assert "test-exec-001" in result.outputs["notification_id"]

    @pytest.mark.asyncio
    async def test_execute_pubsub_failure(
        self,
        notification_handler: NotificationHandler,
        notification_context: HandlerContext,
    ) -> None:
        """Should handle pubsub failure gracefully."""
        import httpx

        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch(
            "budpipeline.handlers.notification_handlers.publish_to_pubsub",
            new_callable=AsyncMock,
            side_effect=httpx.HTTPStatusError("Error", request=MagicMock(), response=mock_response),
        ):
            result = await notification_handler.execute(notification_context)

        assert result.success is False
        assert result.outputs["sent"] is False
        assert result.error is not None
        assert "500" in result.error

    @pytest.mark.asyncio
    async def test_execute_timeout(
        self,
        notification_handler: NotificationHandler,
        notification_context: HandlerContext,
    ) -> None:
        """Should handle timeout gracefully."""
        import httpx

        with patch(
            "budpipeline.handlers.notification_handlers.publish_to_pubsub",
            new_callable=AsyncMock,
            side_effect=httpx.TimeoutException("Timeout"),
        ):
            result = await notification_handler.execute(notification_context)

        assert result.success is False
        assert result.outputs["sent"] is False
        assert "timed out" in result.error.lower()


class TestWebhookHandler:
    """Tests for WebhookHandler."""

    def test_handler_metadata(self, webhook_handler: WebhookHandler) -> None:
        """Should have correct metadata."""
        assert webhook_handler.action_type == "webhook"
        assert webhook_handler.name == "Trigger Webhook"
        assert webhook_handler.description is not None

    def test_get_required_params(self, webhook_handler: WebhookHandler) -> None:
        """Should require url parameter."""
        required = webhook_handler.get_required_params()
        assert "url" in required

    def test_get_optional_params(self, webhook_handler: WebhookHandler) -> None:
        """Should have payload, headers, method, and timeout as optional."""
        optional = webhook_handler.get_optional_params()
        assert "payload" in optional
        assert "headers" in optional
        assert "method" in optional
        assert "timeout_seconds" in optional

    def test_get_output_names(self, webhook_handler: WebhookHandler) -> None:
        """Should output success, status_code, and response."""
        outputs = webhook_handler.get_output_names()
        assert "success" in outputs
        assert "status_code" in outputs
        assert "response" in outputs

    def test_validate_params_missing_url(self, webhook_handler: WebhookHandler) -> None:
        """Should fail validation without url."""
        errors = webhook_handler.validate_params({})
        assert any("url" in e for e in errors)

    def test_validate_params_invalid_url(self, webhook_handler: WebhookHandler) -> None:
        """Should fail validation with non-http URL."""
        errors = webhook_handler.validate_params({"url": "ftp://example.com"})
        assert any("http" in e.lower() for e in errors)

    def test_validate_params_valid_http(self, webhook_handler: WebhookHandler) -> None:
        """Should accept http URL."""
        errors = webhook_handler.validate_params({"url": "http://example.com"})
        assert len(errors) == 0

    def test_validate_params_valid_https(self, webhook_handler: WebhookHandler) -> None:
        """Should accept https URL."""
        errors = webhook_handler.validate_params({"url": "https://example.com"})
        assert len(errors) == 0

    def test_validate_params_invalid_method(self, webhook_handler: WebhookHandler) -> None:
        """Should fail validation with invalid HTTP method."""
        errors = webhook_handler.validate_params(
            {
                "url": "https://example.com",
                "method": "INVALID",
            }
        )
        assert any("method" in e for e in errors)

    def test_validate_params_valid_methods(self, webhook_handler: WebhookHandler) -> None:
        """Should accept all valid HTTP methods."""
        valid_methods = ["GET", "POST", "PUT", "PATCH", "DELETE"]
        for method in valid_methods:
            errors = webhook_handler.validate_params(
                {
                    "url": "https://example.com",
                    "method": method,
                }
            )
            assert len(errors) == 0, f"Method {method} should be valid"

    @pytest.mark.asyncio
    async def test_execute_post_success(
        self, webhook_handler: WebhookHandler, webhook_context: HandlerContext
    ) -> None:
        """Should execute POST webhook successfully."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "ok"}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.request.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await webhook_handler.execute(webhook_context)

        assert result.success is True
        assert result.outputs["success"] is True
        assert result.outputs["status_code"] == 200
        assert result.outputs["response"] == {"result": "ok"}

    @pytest.mark.asyncio
    async def test_execute_get_success(self, webhook_handler: WebhookHandler) -> None:
        """Should execute GET webhook successfully."""
        context = HandlerContext(
            step_id="webhook",
            execution_id="test-exec-002",
            params={
                "url": "https://example.com/api",
                "method": "GET",
                "payload": {"query": "test"},
            },
            workflow_params={},
            step_outputs={},
        )

        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "result"}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.request.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await webhook_handler.execute(context)

        assert result.success is True
        assert result.outputs["status_code"] == 200

    @pytest.mark.asyncio
    async def test_execute_http_error(
        self, webhook_handler: WebhookHandler, webhook_context: HandlerContext
    ) -> None:
        """Should handle HTTP errors gracefully."""
        mock_response = MagicMock()
        mock_response.is_success = False
        mock_response.status_code = 500
        mock_response.json.return_value = {"error": "Server error"}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.request.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await webhook_handler.execute(webhook_context)

        # Even if the HTTP response indicates failure, the handler execution succeeds
        # The success field in outputs reflects the HTTP response status
        assert result.outputs["success"] is False
        assert result.outputs["status_code"] == 500

    @pytest.mark.asyncio
    async def test_execute_timeout(
        self, webhook_handler: WebhookHandler, webhook_context: HandlerContext
    ) -> None:
        """Should handle timeout gracefully."""
        import httpx

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.request.side_effect = httpx.TimeoutException("Timeout")
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await webhook_handler.execute(webhook_context)

        assert result.success is False
        assert result.outputs["success"] is False
        assert result.outputs["status_code"] == 0
        assert "timed out" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_includes_workflow_metadata(
        self, webhook_handler: WebhookHandler, webhook_context: HandlerContext
    ) -> None:
        """Should include workflow metadata in payload."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.status_code = 200
        mock_response.json.return_value = {}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.request.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            await webhook_handler.execute(webhook_context)

            # Verify the enriched payload includes workflow metadata
            call_kwargs = mock_client.request.call_args.kwargs
            payload = call_kwargs.get("json", {})
            assert "_workflow_metadata" in payload
            assert payload["_workflow_metadata"]["execution_id"] == "test-exec-001"
            assert payload["_workflow_metadata"]["step_id"] == "webhook"


class TestPublishToPubsub:
    """Tests for the publish_to_pubsub helper function."""

    @pytest.mark.asyncio
    async def test_publish_success(self) -> None:
        """Should publish successfully."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await publish_to_pubsub(
                pubsub_name="pubsub",
                topic_name="notifications",
                data={"message": "test"},
            )

        assert result is True

    @pytest.mark.asyncio
    async def test_publish_includes_dapr_token(self) -> None:
        """Should include Dapr API token in headers when configured."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        with patch("budpipeline.handlers.notification_handlers.settings") as mock_settings:
            mock_settings.dapr_http_endpoint = "http://localhost:3500"
            mock_settings.dapr_api_token = "test-token"
            mock_settings.pubsub_name = "pubsub"

            with patch("httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.post.return_value = mock_response
                mock_client_class.return_value.__aenter__.return_value = mock_client

                await publish_to_pubsub(
                    pubsub_name="pubsub",
                    topic_name="test-topic",
                    data={"test": "data"},
                )

                call_kwargs = mock_client.post.call_args.kwargs
                assert "dapr-api-token" in call_kwargs.get("headers", {})
                assert call_kwargs["headers"]["dapr-api-token"] == "test-token"
