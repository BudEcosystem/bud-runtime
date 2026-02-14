"""Unit tests for OAuth return_url utilities in connector_ops/services.py.

These tests target the standalone utility functions (validate_return_url,
store_return_url, pop_return_url) which don't require database or Dapr.
We import them lazily to avoid triggering the full application import chain
during collection.  Redis is mocked so no running Redis instance is needed.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status


# ─── Redis mock fixtures ────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _mock_redis():
    """Mock RedisService to use an in-memory dict instead of real Redis."""
    store: dict[str, bytes] = {}

    async def fake_set(name, value, ex=None, **kwargs):
        store[str(name)] = value.encode("utf-8") if isinstance(value, str) else value

    async def fake_get(name):
        return store.get(str(name))

    async def fake_delete(*names):
        for name in names:
            store.pop(str(name), None)

    with patch("budapp.connector_ops.services._redis_service") as mock_svc:
        mock_svc.set = AsyncMock(side_effect=fake_set)
        mock_svc.get = AsyncMock(side_effect=fake_get)
        mock_svc.delete = AsyncMock(side_effect=fake_delete)
        mock_svc._store = store  # expose for tests that need direct access
        yield mock_svc


# ─── validate_return_url ─────────────────────────────────────────────────────


class TestValidateReturnUrl:
    """Tests for validate_return_url."""

    def test_valid_https_url(self):
        from budapp.connector_ops.services import validate_return_url

        url = "https://admin.dev.bud.studio/callback"
        assert validate_return_url(url) == url

    def test_valid_localhost_http(self):
        from budapp.connector_ops.services import validate_return_url

        url = "http://localhost:3000/callback"
        assert validate_return_url(url) == url

    def test_valid_127_0_0_1_http(self):
        from budapp.connector_ops.services import validate_return_url

        url = "http://127.0.0.1:8080/callback"
        assert validate_return_url(url) == url

    def test_rejects_missing_scheme(self):
        from budapp.commons.exceptions import ClientException
        from budapp.connector_ops.services import validate_return_url

        with pytest.raises(ClientException) as exc_info:
            validate_return_url("admin.dev.bud.studio/callback")
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    def test_rejects_disallowed_domain(self):
        from budapp.commons.exceptions import ClientException
        from budapp.connector_ops.services import validate_return_url

        with pytest.raises(ClientException) as exc_info:
            validate_return_url("https://evil.example.com/steal")
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "not in the allowed list" in str(exc_info.value.message)

    def test_rejects_http_for_non_localhost(self):
        from budapp.commons.exceptions import ClientException
        from budapp.connector_ops.services import validate_return_url

        with pytest.raises(ClientException) as exc_info:
            validate_return_url("http://admin.dev.bud.studio/callback")
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "HTTPS" in str(exc_info.value.message)

    def test_rejects_javascript_scheme(self):
        from budapp.commons.exceptions import ClientException
        from budapp.connector_ops.services import validate_return_url

        with pytest.raises(ClientException) as exc_info:
            validate_return_url("javascript://localhost/%0aalert(1)")
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "HTTP or HTTPS" in str(exc_info.value.message)

    def test_rejects_data_scheme(self):
        from budapp.commons.exceptions import ClientException
        from budapp.connector_ops.services import validate_return_url

        with pytest.raises(ClientException) as exc_info:
            validate_return_url("data://localhost/text/html,<script>alert(1)</script>")
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    def test_rejects_ftp_scheme(self):
        from budapp.commons.exceptions import ClientException
        from budapp.connector_ops.services import validate_return_url

        with pytest.raises(ClientException) as exc_info:
            validate_return_url("ftp://admin.dev.bud.studio/file")
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    def test_custom_allowed_domains(self):
        from budapp.connector_ops.services import validate_return_url

        with patch("budapp.connector_ops.services.app_settings") as mock_settings:
            mock_settings.oauth_return_url_allowed_domains = "custom.example.com,localhost"
            url = "https://custom.example.com/cb"
            assert validate_return_url(url) == url

    def test_empty_url(self):
        from budapp.commons.exceptions import ClientException
        from budapp.connector_ops.services import validate_return_url

        with pytest.raises(ClientException):
            validate_return_url("")

    def test_preserves_query_params_and_fragments(self):
        from budapp.connector_ops.services import validate_return_url

        url = "https://admin.dev.bud.studio/callback?foo=bar#section"
        assert validate_return_url(url) == url

    def test_url_with_port(self):
        from budapp.connector_ops.services import validate_return_url

        url = "https://admin.dev.bud.studio:8443/callback"
        assert validate_return_url(url) == url

    def test_case_insensitive_domain_match(self):
        from budapp.connector_ops.services import validate_return_url

        url = "https://Admin.Dev.Bud.Studio/callback"
        assert validate_return_url(url) == url


# ─── store_return_url / pop_return_url ────────────────────────────────────────


class TestReturnUrlCache:
    """Tests for store_return_url and pop_return_url (Redis-backed)."""

    @pytest.mark.asyncio
    async def test_store_and_pop(self):
        from budapp.connector_ops.services import pop_return_url, store_return_url

        await store_return_url("state-abc", "https://example.com/cb")
        result = await pop_return_url("state-abc")
        assert result == "https://example.com/cb"

    @pytest.mark.asyncio
    async def test_pop_removes_entry(self):
        from budapp.connector_ops.services import pop_return_url, store_return_url

        await store_return_url("state-abc", "https://example.com/cb")
        await pop_return_url("state-abc")
        assert await pop_return_url("state-abc") is None

    @pytest.mark.asyncio
    async def test_pop_nonexistent_state(self):
        from budapp.connector_ops.services import pop_return_url

        assert await pop_return_url("no-such-state") is None

    @pytest.mark.asyncio
    async def test_multiple_states(self):
        from budapp.connector_ops.services import pop_return_url, store_return_url

        await store_return_url("s1", "https://one.com")
        await store_return_url("s2", "https://two.com")
        assert await pop_return_url("s1") == "https://one.com"
        assert await pop_return_url("s2") == "https://two.com"

    @pytest.mark.asyncio
    async def test_overwrite_same_state(self):
        from budapp.connector_ops.services import pop_return_url, store_return_url

        await store_return_url("s1", "https://first.com")
        await store_return_url("s1", "https://second.com")
        assert await pop_return_url("s1") == "https://second.com"

    @pytest.mark.asyncio
    async def test_redis_set_called_with_ttl(self, _mock_redis):
        from budapp.connector_ops.services import store_return_url

        await store_return_url("state-ttl", "https://example.com/cb")
        _mock_redis.set.assert_called_once()
        call_kwargs = _mock_redis.set.call_args
        assert call_kwargs[1].get("ex") == 600 or call_kwargs[0][2] == 600

    @pytest.mark.asyncio
    async def test_pop_deletes_from_redis(self, _mock_redis):
        from budapp.connector_ops.services import pop_return_url, store_return_url

        await store_return_url("state-del", "https://example.com/cb")
        await pop_return_url("state-del")
        _mock_redis.delete.assert_called_once()
