"""Tests for Actions API endpoints."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from budpipeline.actions import action_registry
from budpipeline.main import app


@pytest.fixture(autouse=True)
def setup_actions():
    """Ensure actions are discovered before tests."""
    action_registry.reset()
    action_registry.discover_actions()
    yield
    action_registry.reset()


class TestActionsListEndpoint:
    """Tests for GET /actions endpoint."""

    @pytest.mark.asyncio
    async def test_list_actions_returns_all_actions(self) -> None:
        """Test that GET /actions returns all registered actions."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/actions")

        assert response.status_code == 200
        data = response.json()

        assert "actions" in data
        assert "categories" in data
        assert "total" in data

        # Should have at least the 17 built-in actions
        assert data["total"] >= 17
        assert len(data["actions"]) >= 17

    @pytest.mark.asyncio
    async def test_list_actions_includes_categories(self) -> None:
        """Test that categories are properly grouped."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/actions")

        data = response.json()
        categories = data["categories"]

        # Should have categories
        assert len(categories) > 0

        # Each category should have name, icon, and actions
        for category in categories:
            assert "name" in category
            assert "icon" in category
            assert "actions" in category
            assert len(category["actions"]) > 0

    @pytest.mark.asyncio
    async def test_list_actions_includes_param_definitions(self) -> None:
        """Test that action params are properly serialized."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/actions")

        data = response.json()

        # Find an action with params
        log_action = next((a for a in data["actions"] if a["type"] == "log"), None)
        assert log_action is not None

        # Should have params
        assert "params" in log_action
        assert len(log_action["params"]) > 0

        # Check param structure
        message_param = next((p for p in log_action["params"] if p["name"] == "message"), None)
        assert message_param is not None
        assert "name" in message_param
        assert "label" in message_param
        assert "type" in message_param

    @pytest.mark.asyncio
    async def test_list_actions_includes_outputs(self) -> None:
        """Test that action outputs are properly serialized."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/actions")

        data = response.json()

        # Find an action with outputs (http_request has outputs)
        http_action = next((a for a in data["actions"] if a["type"] == "http_request"), None)
        assert http_action is not None

        # Should have outputs
        assert "outputs" in http_action
        assert len(http_action["outputs"]) > 0

        # Check output structure
        status_code_output = next(
            (o for o in http_action["outputs"] if o["name"] == "status_code"), None
        )
        assert status_code_output is not None
        assert "name" in status_code_output
        assert "type" in status_code_output


class TestActionsGetEndpoint:
    """Tests for GET /actions/{action_type} endpoint."""

    @pytest.mark.asyncio
    async def test_get_action_returns_action(self) -> None:
        """Test that GET /actions/{type} returns action metadata."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/actions/log")

        assert response.status_code == 200
        data = response.json()

        assert data["type"] == "log"
        assert "name" in data
        assert "description" in data
        assert "category" in data
        assert "params" in data
        assert "outputs" in data
        assert "executionMode" in data
        assert "timeoutSeconds" in data

    @pytest.mark.asyncio
    async def test_get_action_returns_404_for_unknown(self) -> None:
        """Test that GET /actions/{type} returns 404 for unknown action."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/actions/unknown_action_type")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_action_returns_event_driven_mode(self) -> None:
        """Test that event-driven actions return correct execution mode."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/actions/model_add")

        assert response.status_code == 200
        data = response.json()

        assert data["executionMode"] == "event_driven"

    @pytest.mark.asyncio
    async def test_get_action_returns_sync_mode(self) -> None:
        """Test that sync actions return correct execution mode."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/actions/log")

        assert response.status_code == 200
        data = response.json()

        assert data["executionMode"] == "sync"


class TestActionsValidateEndpoint:
    """Tests for POST /actions/validate endpoint."""

    @pytest.mark.asyncio
    async def test_validate_valid_params(self) -> None:
        """Test that validation passes for valid params."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/actions/validate",
                json={
                    "actionType": "log",
                    "params": {"message": "test message", "level": "info"},
                },
            )

        assert response.status_code == 200
        data = response.json()

        assert data["valid"] is True
        assert len(data["errors"]) == 0

    @pytest.mark.asyncio
    async def test_validate_missing_required_param(self) -> None:
        """Test that validation fails for missing required params."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/actions/validate",
                json={
                    "actionType": "http_request",
                    "params": {},  # Missing required 'url'
                },
            )

        assert response.status_code == 200
        data = response.json()

        assert data["valid"] is False
        assert len(data["errors"]) > 0
        # Should mention missing url
        assert any("url" in err.lower() for err in data["errors"])

    @pytest.mark.asyncio
    async def test_validate_invalid_param_value(self) -> None:
        """Test that validation fails for invalid param values."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/actions/validate",
                json={
                    "actionType": "delay",
                    "params": {"duration_seconds": -10},  # Invalid: negative duration
                },
            )

        assert response.status_code == 200
        data = response.json()

        assert data["valid"] is False
        assert len(data["errors"]) > 0

    @pytest.mark.asyncio
    async def test_validate_unknown_action_type(self) -> None:
        """Test that validation returns 404 for unknown action."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/actions/validate",
                json={
                    "actionType": "unknown_action",
                    "params": {},
                },
            )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_validate_with_executor_validation(self) -> None:
        """Test that executor's validate_params is called."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/actions/validate",
                json={
                    "actionType": "http_request",
                    "params": {"url": "not-a-valid-url"},  # Invalid URL format
                },
            )

        assert response.status_code == 200
        data = response.json()

        assert data["valid"] is False
        # Should have error about URL format
        assert any("http" in err.lower() for err in data["errors"])


class TestActionsApiV1Prefix:
    """Tests for /api/v1/actions endpoints."""

    @pytest.mark.asyncio
    async def test_api_v1_list_actions(self) -> None:
        """Test that /api/v1/actions works."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/actions")

        assert response.status_code == 200
        data = response.json()
        assert "actions" in data

    @pytest.mark.asyncio
    async def test_api_v1_get_action(self) -> None:
        """Test that /api/v1/actions/{type} works."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/actions/log")

        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "log"

    @pytest.mark.asyncio
    async def test_api_v1_validate(self) -> None:
        """Test that /api/v1/actions/validate works."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/actions/validate",
                json={
                    "actionType": "log",
                    "params": {"message": "test"},
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
