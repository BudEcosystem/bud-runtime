"""Unit tests for client tag constants and legacy mapping in connector_ops/services.py.

These tests verify the tag rename (dashboard→studio, chat→prompt) and the
legacy compatibility mapping that allows existing gateways with old tags to
continue working during the migration period.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ─── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _mock_imports():
    """Mock heavy dependencies so the module can be imported without Dapr/Redis."""
    with (
        patch("budapp.connector_ops.services._redis_service", new_callable=MagicMock),
        patch("budapp.connector_ops.services.mcp_foundry_service", new_callable=MagicMock),
    ):
        yield


# ─── Tag constant tests ───────────────────────────────────────────────────


class TestTagConstants:
    """Verify tag constants were renamed correctly."""

    def test_studio_tag_value(self):
        from budapp.connector_ops.services import TAG_CLIENT_STUDIO

        assert TAG_CLIENT_STUDIO == "client:studio"

    def test_prompt_tag_value(self):
        from budapp.connector_ops.services import TAG_CLIENT_PROMPT

        assert TAG_CLIENT_PROMPT == "client:prompt"

    def test_default_client_tags(self):
        from budapp.connector_ops.services import DEFAULT_CLIENT_TAGS

        assert "client:studio" in DEFAULT_CLIENT_TAGS
        assert "client:prompt" in DEFAULT_CLIENT_TAGS
        assert len(DEFAULT_CLIENT_TAGS) == 2

    def test_old_constants_removed(self):
        """Ensure old TAG_CLIENT_DASHBOARD / TAG_CLIENT_CHAT no longer exist."""
        import budapp.connector_ops.services as svc

        assert not hasattr(svc, "TAG_CLIENT_DASHBOARD")
        assert not hasattr(svc, "TAG_CLIENT_CHAT")


# ─── Legacy mapping tests ─────────────────────────────────────────────────


class TestLegacyClientMapping:
    """Verify _LEGACY_CLIENT_TAGS maps old tag values to new."""

    def test_studio_maps_to_dashboard(self):
        from budapp.connector_ops.services import _LEGACY_CLIENT_TAGS

        assert _LEGACY_CLIENT_TAGS["studio"] == "client:dashboard"

    def test_prompt_maps_to_chat(self):
        from budapp.connector_ops.services import _LEGACY_CLIENT_TAGS

        assert _LEGACY_CLIENT_TAGS["prompt"] == "client:chat"

    def test_no_extra_mappings(self):
        from budapp.connector_ops.services import _LEGACY_CLIENT_TAGS

        assert set(_LEGACY_CLIENT_TAGS.keys()) == {"studio", "prompt"}


# ─── list_configured client filter tests ──────────────────────────────────


class TestListConfiguredClientFilter:
    """Test that list_configured filters correctly with new and legacy tags."""

    @pytest.mark.asyncio
    async def test_filter_by_studio_matches_new_tag(self):
        """Gateway with client:studio tag should match client='studio'."""
        from budapp.connector_ops.services import ConnectorService, mcp_foundry_service

        gateway = {
            "id": "gw-1",
            "enabled": True,
            "tags": ["connector-id:c1", "client:studio", "source:budapp"],
            "tools": [],
        }
        connector = {"id": "c1", "name": "Test", "auth_type": "Open"}

        mcp_foundry_service.list_gateways = AsyncMock(return_value=([gateway], 1))
        mcp_foundry_service.list_connectors = AsyncMock(return_value=([connector], 1))
        mcp_foundry_service.get_gateway_by_id = AsyncMock(return_value=gateway)
        mcp_foundry_service.get_oauth_status = AsyncMock(return_value={"oauth_enabled": False})

        results, total = await ConnectorService().list_configured(client="studio")
        assert total == 1
        assert results[0]["connector_id"] == "c1"

    @pytest.mark.asyncio
    async def test_filter_by_studio_matches_legacy_dashboard_tag(self):
        """Gateway with old client:dashboard tag should still match client='studio'."""
        from budapp.connector_ops.services import ConnectorService, mcp_foundry_service

        gateway = {
            "id": "gw-2",
            "enabled": True,
            "tags": ["connector-id:c2", "client:dashboard", "source:budapp"],
            "tools": [],
        }
        connector = {"id": "c2", "name": "Legacy", "auth_type": "Open"}

        mcp_foundry_service.list_gateways = AsyncMock(return_value=([gateway], 1))
        mcp_foundry_service.list_connectors = AsyncMock(return_value=([connector], 1))
        mcp_foundry_service.get_gateway_by_id = AsyncMock(return_value=gateway)
        mcp_foundry_service.get_oauth_status = AsyncMock(return_value={"oauth_enabled": False})

        results, total = await ConnectorService().list_configured(client="studio")
        assert total == 1
        assert results[0]["connector_id"] == "c2"

    @pytest.mark.asyncio
    async def test_filter_by_prompt_matches_legacy_chat_tag(self):
        """Gateway with old client:chat tag should still match client='prompt'."""
        from budapp.connector_ops.services import ConnectorService, mcp_foundry_service

        gateway = {
            "id": "gw-3",
            "enabled": True,
            "tags": ["connector-id:c3", "client:chat", "source:budapp"],
            "tools": [],
        }
        connector = {"id": "c3", "name": "ChatLegacy", "auth_type": "Open"}

        mcp_foundry_service.list_gateways = AsyncMock(return_value=([gateway], 1))
        mcp_foundry_service.list_connectors = AsyncMock(return_value=([connector], 1))
        mcp_foundry_service.get_gateway_by_id = AsyncMock(return_value=gateway)
        mcp_foundry_service.get_oauth_status = AsyncMock(return_value={"oauth_enabled": False})

        results, total = await ConnectorService().list_configured(client="prompt")
        assert total == 1
        assert results[0]["connector_id"] == "c3"

    @pytest.mark.asyncio
    async def test_no_client_filter_returns_all(self):
        """No client filter should return all configured gateways."""
        from budapp.connector_ops.services import ConnectorService, mcp_foundry_service

        gw1 = {"id": "gw-1", "enabled": True, "tags": ["connector-id:c1", "client:studio"], "tools": []}
        gw2 = {"id": "gw-2", "enabled": True, "tags": ["connector-id:c2", "client:dashboard"], "tools": []}
        connector1 = {"id": "c1", "name": "A"}
        connector2 = {"id": "c2", "name": "B"}

        mcp_foundry_service.list_gateways = AsyncMock(return_value=([gw1, gw2], 2))
        mcp_foundry_service.list_connectors = AsyncMock(return_value=([connector1, connector2], 2))
        mcp_foundry_service.get_gateway_by_id = AsyncMock(side_effect=lambda gid: gw1 if gid == "gw-1" else gw2)
        mcp_foundry_service.get_oauth_status = AsyncMock(return_value={"oauth_enabled": False})

        results, total = await ConnectorService().list_configured(client=None)
        assert total == 2

    @pytest.mark.asyncio
    async def test_filter_excludes_non_matching(self):
        """Gateway with only client:prompt should not match client='studio'."""
        from budapp.connector_ops.services import ConnectorService, mcp_foundry_service

        gateway = {
            "id": "gw-4",
            "enabled": True,
            "tags": ["connector-id:c4", "client:prompt"],
            "tools": [],
        }

        mcp_foundry_service.list_gateways = AsyncMock(return_value=([gateway], 1))

        results, total = await ConnectorService().list_configured(client="studio")
        assert total == 0


# ─── list_tools legacy tag tests ──────────────────────────────────────────


class TestListToolsLegacyTag:
    """Test that list_tools accepts both new and legacy studio tags."""

    @pytest.mark.asyncio
    async def test_accepts_new_studio_tag(self):
        from budapp.connector_ops.services import ConnectorService, mcp_foundry_service

        gateway = {
            "id": "gw-1",
            "enabled": True,
            "tags": ["client:studio"],
            "tools": [{"name": "tool1"}],
        }
        mcp_foundry_service.get_gateway_by_id = AsyncMock(return_value=gateway)

        tools, total = await ConnectorService().list_tools("gw-1")
        assert total == 1

    @pytest.mark.asyncio
    async def test_accepts_legacy_dashboard_tag(self):
        from budapp.connector_ops.services import ConnectorService, mcp_foundry_service

        gateway = {
            "id": "gw-2",
            "enabled": True,
            "tags": ["client:dashboard"],
            "tools": [{"name": "tool1"}, {"name": "tool2"}],
        }
        mcp_foundry_service.get_gateway_by_id = AsyncMock(return_value=gateway)

        tools, total = await ConnectorService().list_tools("gw-2")
        assert total == 2

    @pytest.mark.asyncio
    async def test_rejects_gateway_without_studio_or_dashboard(self):
        from budapp.commons.exceptions import ClientException
        from budapp.connector_ops.services import ConnectorService, mcp_foundry_service

        gateway = {
            "id": "gw-3",
            "enabled": True,
            "tags": ["client:prompt"],
            "tools": [],
        }
        mcp_foundry_service.get_gateway_by_id = AsyncMock(return_value=gateway)

        with pytest.raises(ClientException, match="not accessible to the studio client"):
            await ConnectorService().list_tools("gw-3")

    @pytest.mark.asyncio
    async def test_rejects_disabled_gateway(self):
        from budapp.commons.exceptions import ClientException
        from budapp.connector_ops.services import ConnectorService, mcp_foundry_service

        gateway = {
            "id": "gw-4",
            "enabled": False,
            "tags": ["client:studio"],
            "tools": [],
        }
        mcp_foundry_service.get_gateway_by_id = AsyncMock(return_value=gateway)

        with pytest.raises(ClientException, match="Gateway is disabled"):
            await ConnectorService().list_tools("gw-4")
