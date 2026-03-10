"""Tests for shared MCP Foundry credential transformation and DCR enrichment."""

import pytest

from budapp.prompt_ops.schemas import HeadersCredentials, OAuthCredentials, OpenCredentials
from budapp.shared.mcp_foundry_utils import (
    detect_transport_from_url,
    enrich_oauth_credentials_with_dcr,
    transform_credentials_to_mcp_format,
)


# ─── detect_transport_from_url ──────────────────────────────────────────────


class TestDetectTransport:
    def test_sse_url(self):
        assert detect_transport_from_url("https://example.com/sse") == "SSE"

    def test_sse_url_trailing_slash(self):
        assert detect_transport_from_url("https://example.com/sse/") == "SSE"

    def test_streamable_url(self):
        assert detect_transport_from_url("https://example.com/mcp") == "STREAMABLEHTTP"

    def test_plain_url(self):
        assert detect_transport_from_url("https://example.com") == "STREAMABLEHTTP"


# ─── transform_credentials_to_mcp_format: OAuth ────────────────────────────


class TestTransformOAuth:
    def test_oauth_with_client_credentials(self):
        creds = OAuthCredentials(
            grant_type="client_credentials",
            client_id="my-id",
            client_secret="my-secret",
            token_url="https://example.com/token",
        )
        result = transform_credentials_to_mcp_format(creds)

        assert result["auth_type"] == "oauth"
        oauth = result["oauth_config"]
        assert oauth["client_id"] == "my-id"
        assert oauth["client_secret"] == "my-secret"
        assert oauth["token_url"] == "https://example.com/token"
        assert oauth["grant_type"] == "client_credentials"
        assert oauth["token_management"]["store_tokens"] is True
        assert "supports_dcr" not in oauth

    def test_oauth_without_client_credentials(self):
        """When no client_id/secret, they should NOT appear in oauth_config."""
        creds = OAuthCredentials(
            grant_type="client_credentials",
            token_url="https://example.com/token",
            supports_dcr=True,
            registration_url="https://example.com/register",
        )
        result = transform_credentials_to_mcp_format(creds)

        oauth = result["oauth_config"]
        assert "client_id" not in oauth
        assert "client_secret" not in oauth
        assert oauth["supports_dcr"] is True
        assert oauth["registration_url"] == "https://example.com/register"

    def test_oauth_dcr_without_registration_url(self):
        creds = OAuthCredentials(
            grant_type="client_credentials",
            token_url="https://example.com/token",
            supports_dcr=True,
        )
        result = transform_credentials_to_mcp_format(creds)

        oauth = result["oauth_config"]
        assert oauth["supports_dcr"] is True
        assert "registration_url" not in oauth

    def test_oauth_no_dcr_fields_when_supports_dcr_false(self):
        creds = OAuthCredentials(
            grant_type="client_credentials",
            client_id="id",
            client_secret="secret",
            token_url="https://example.com/token",
            supports_dcr=False,
        )
        result = transform_credentials_to_mcp_format(creds)

        oauth = result["oauth_config"]
        assert "supports_dcr" not in oauth
        assert "registration_url" not in oauth

    def test_oauth_with_scopes(self):
        creds = OAuthCredentials(
            grant_type="client_credentials",
            client_id="id",
            client_secret="secret",
            token_url="https://example.com/token",
            scopes=["read", "write"],
        )
        result = transform_credentials_to_mcp_format(creds)

        assert result["oauth_config"]["scopes"] == ["read", "write"]

    def test_oauth_without_scopes(self):
        creds = OAuthCredentials(
            grant_type="client_credentials",
            client_id="id",
            client_secret="secret",
            token_url="https://example.com/token",
        )
        result = transform_credentials_to_mcp_format(creds)

        assert "scopes" not in result["oauth_config"]

    def test_oauth_with_passthrough_headers(self):
        creds = OAuthCredentials(
            grant_type="client_credentials",
            client_id="id",
            client_secret="secret",
            token_url="https://example.com/token",
            passthrough_headers=["X-Custom"],
        )
        result = transform_credentials_to_mcp_format(creds)

        assert result["passthrough_headers"] == ["X-Custom"]


# ─── transform_credentials_to_mcp_format: Headers ──────────────────────────


class TestTransformHeaders:
    def test_headers_credentials(self):
        creds = HeadersCredentials(
            auth_headers=[{"key": "Authorization", "value": "Bearer token"}],
        )
        result = transform_credentials_to_mcp_format(creds)

        assert result["auth_type"] == "authheaders"
        assert result["auth_headers"] == [{"key": "Authorization", "value": "Bearer token"}]
        assert result["oauth_grant_type"] == "client_credentials"

    def test_headers_with_passthrough(self):
        creds = HeadersCredentials(
            auth_headers=[{"key": "X-Key", "value": "val"}],
            passthrough_headers=["X-Forward"],
        )
        result = transform_credentials_to_mcp_format(creds)

        assert result["passthrough_headers"] == ["X-Forward"]


# ─── transform_credentials_to_mcp_format: Open ─────────────────────────────


class TestTransformOpen:
    def test_open_credentials(self):
        creds = OpenCredentials()
        result = transform_credentials_to_mcp_format(creds)

        assert "auth_type" not in result
        assert result["oauth_grant_type"] == "client_credentials"
        assert result["oauth_store_tokens"] is True
        assert result["oauth_auto_refresh"] is True


# ─── enrich_oauth_credentials_with_dcr ──────────────────────────────────────


class TestEnrichDCR:
    def test_enriches_when_dcr_supported_and_no_client_id(self):
        creds = OAuthCredentials(
            grant_type="client_credentials",
            token_url="https://example.com/token",
            supports_dcr=True,  # Will pass validator since we set it
        )
        connector_oauth_cfg = {
            "supports_dcr": True,
            "registration_url": "https://example.com/register",
        }

        enrich_oauth_credentials_with_dcr(creds, connector_oauth_cfg)

        assert creds.supports_dcr is True
        assert creds.registration_url == "https://example.com/register"

    def test_skips_when_client_id_provided(self):
        creds = OAuthCredentials(
            grant_type="client_credentials",
            client_id="my-id",
            client_secret="my-secret",
            token_url="https://example.com/token",
        )
        connector_oauth_cfg = {
            "supports_dcr": True,
            "registration_url": "https://example.com/register",
        }

        enrich_oauth_credentials_with_dcr(creds, connector_oauth_cfg)

        assert creds.supports_dcr is False
        assert creds.registration_url is None

    def test_skips_when_connector_dcr_false(self):
        creds = OAuthCredentials(
            grant_type="client_credentials",
            token_url="https://example.com/token",
            supports_dcr=True,
        )
        connector_oauth_cfg = {
            "supports_dcr": False,
        }

        enrich_oauth_credentials_with_dcr(creds, connector_oauth_cfg)

        # supports_dcr stays as it was (True from creds), but registration_url not set
        assert creds.registration_url is None

    def test_preserves_existing_registration_url(self):
        creds = OAuthCredentials(
            grant_type="client_credentials",
            token_url="https://example.com/token",
            supports_dcr=True,
            registration_url="https://custom.com/register",
        )
        connector_oauth_cfg = {
            "supports_dcr": True,
            "registration_url": "https://example.com/register",
        }

        enrich_oauth_credentials_with_dcr(creds, connector_oauth_cfg)

        # Should keep the existing user-provided registration_url
        assert creds.registration_url == "https://custom.com/register"

    def test_handles_empty_oauth_config(self):
        creds = OAuthCredentials(
            grant_type="client_credentials",
            token_url="https://example.com/token",
            supports_dcr=True,
        )

        enrich_oauth_credentials_with_dcr(creds, {})

        assert creds.registration_url is None
