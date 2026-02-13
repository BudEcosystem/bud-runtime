"""Unit tests for OAuth return_url utilities in connector_ops/services.py.

These tests target the standalone utility functions (validate_return_url,
store_return_url, pop_return_url) which don't require database or Dapr.
We import them lazily to avoid triggering the full application import chain
during collection.
"""

import time
from unittest.mock import patch

import pytest
from fastapi import status


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear the return URL cache before and after each test."""
    from budapp.connector_ops.services import _return_url_cache

    _return_url_cache.clear()
    yield
    _return_url_cache.clear()


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
    """Tests for store_return_url and pop_return_url."""

    def test_store_and_pop(self):
        from budapp.connector_ops.services import pop_return_url, store_return_url

        store_return_url("state-abc", "https://example.com/cb")
        result = pop_return_url("state-abc")
        assert result == "https://example.com/cb"

    def test_pop_removes_entry(self):
        from budapp.connector_ops.services import pop_return_url, store_return_url

        store_return_url("state-abc", "https://example.com/cb")
        pop_return_url("state-abc")
        assert pop_return_url("state-abc") is None

    def test_pop_nonexistent_state(self):
        from budapp.connector_ops.services import pop_return_url

        assert pop_return_url("no-such-state") is None

    def test_expired_entry_returns_none(self):
        from budapp.connector_ops.services import _return_url_cache, pop_return_url, store_return_url

        store_return_url("state-exp", "https://example.com/cb")
        # Manually set expiry to the past
        url, _ = _return_url_cache["state-exp"]
        _return_url_cache["state-exp"] = (url, time.monotonic() - 1)
        assert pop_return_url("state-exp") is None

    def test_lazy_cleanup_of_expired_entries(self):
        from budapp.connector_ops.services import _return_url_cache, store_return_url

        # Store an entry that's already expired
        _return_url_cache["old"] = ("https://old.com", time.monotonic() - 1)
        # Storing a new entry should clean up the expired one
        store_return_url("new", "https://new.com")
        assert "old" not in _return_url_cache
        assert "new" in _return_url_cache

    def test_multiple_states(self):
        from budapp.connector_ops.services import pop_return_url, store_return_url

        store_return_url("s1", "https://one.com")
        store_return_url("s2", "https://two.com")
        assert pop_return_url("s1") == "https://one.com"
        assert pop_return_url("s2") == "https://two.com"

    def test_overwrite_same_state(self):
        from budapp.connector_ops.services import pop_return_url, store_return_url

        store_return_url("s1", "https://first.com")
        store_return_url("s1", "https://second.com")
        assert pop_return_url("s1") == "https://second.com"
