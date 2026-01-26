#  -----------------------------------------------------------------------------
#  Copyright (c) 2024 Bud Ecosystem Inc.
#  #
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#  #
#      http://www.apache.org/licenses/LICENSE-2.0
#  #
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#  -----------------------------------------------------------------------------

"""Tests for realtime authentication module."""

from unittest.mock import MagicMock, patch

import pytest


class TestValidateKeycloakToken:
    """Tests for validate_keycloak_token function."""

    @pytest.mark.asyncio
    async def test_returns_none_when_disabled(self) -> None:
        """Test that validation returns None when realtime is disabled."""
        with patch("notify.realtime.auth.app_settings") as mock_settings:
            mock_settings.realtime_enabled = False

            from notify.realtime.auth import validate_keycloak_token

            result = await validate_keycloak_token("some-token")
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_keycloak_not_configured(self) -> None:
        """Test that validation returns None when Keycloak is not configured."""
        with patch("notify.realtime.auth.app_settings") as mock_settings:
            mock_settings.realtime_enabled = True
            mock_settings.keycloak_url = None
            mock_settings.keycloak_realm = "bud"

            from notify.realtime.auth import validate_keycloak_token

            result = await validate_keycloak_token("some-token")
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_token_without_kid(self) -> None:
        """Test that validation returns None for tokens without kid header."""
        with patch("notify.realtime.auth.app_settings") as mock_settings:
            mock_settings.realtime_enabled = True
            mock_settings.keycloak_url = "http://keycloak:8080"
            mock_settings.keycloak_realm = "bud"

            with patch("notify.realtime.auth.jwt") as mock_jwt:
                mock_jwt.get_unverified_header.return_value = {}

                from notify.realtime.auth import validate_keycloak_token

                result = await validate_keycloak_token("some-token")
                assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_token_without_sub(self) -> None:
        """Test that validation returns None for tokens without sub claim."""
        with patch("notify.realtime.auth.app_settings") as mock_settings:
            mock_settings.realtime_enabled = True
            mock_settings.keycloak_url = "http://keycloak:8080"
            mock_settings.keycloak_realm = "bud"

            with patch("notify.realtime.auth.jwt") as mock_jwt:
                mock_jwt.get_unverified_header.return_value = {"kid": "key-123"}

                mock_public_key = MagicMock()

                with patch("notify.realtime.auth._get_jwks_client") as mock_get_jwks:
                    mock_jwks_client = MagicMock()
                    mock_signing_key = MagicMock()
                    mock_signing_key.key = mock_public_key
                    mock_jwks_client.get_signing_key_from_jwt.return_value = mock_signing_key
                    mock_get_jwks.return_value = mock_jwks_client

                    mock_jwt.decode.return_value = {"email": "test@example.com"}

                    from notify.realtime.auth import validate_keycloak_token

                    result = await validate_keycloak_token("some-token")
                    assert result is None

    @pytest.mark.asyncio
    async def test_returns_user_info_for_valid_token(self) -> None:
        """Test that validation returns UserInfo for valid tokens."""
        with patch("notify.realtime.auth.app_settings") as mock_settings:
            mock_settings.realtime_enabled = True
            mock_settings.keycloak_url = "http://keycloak:8080"
            mock_settings.keycloak_realm = "bud"

            with patch("notify.realtime.auth.jwt") as mock_jwt:
                mock_jwt.get_unverified_header.return_value = {"kid": "key-123"}

                mock_public_key = MagicMock()

                with patch("notify.realtime.auth._get_jwks_client") as mock_get_jwks:
                    mock_jwks_client = MagicMock()
                    mock_signing_key = MagicMock()
                    mock_signing_key.key = mock_public_key
                    mock_jwks_client.get_signing_key_from_jwt.return_value = mock_signing_key
                    mock_get_jwks.return_value = mock_jwks_client

                    mock_jwt.decode.return_value = {
                        "sub": "user-123",
                        "email": "test@example.com",
                        "preferred_username": "testuser",
                    }

                    from notify.realtime.auth import validate_keycloak_token

                    result = await validate_keycloak_token("some-token")

                    assert result is not None
                    assert result.id == "user-123"
                    assert result.email == "test@example.com"
                    assert result.username == "testuser"
                    assert result.realm == "bud"

    @pytest.mark.asyncio
    async def test_returns_none_for_expired_token(self) -> None:
        """Test that validation returns None for expired tokens."""
        from jwt.exceptions import ExpiredSignatureError

        with patch("notify.realtime.auth.app_settings") as mock_settings:
            mock_settings.realtime_enabled = True
            mock_settings.keycloak_url = "http://keycloak:8080"
            mock_settings.keycloak_realm = "bud"

            with patch("notify.realtime.auth.jwt") as mock_jwt:
                mock_jwt.get_unverified_header.return_value = {"kid": "key-123"}

                mock_public_key = MagicMock()

                with patch("notify.realtime.auth._get_jwks_client") as mock_get_jwks:
                    mock_jwks_client = MagicMock()
                    mock_signing_key = MagicMock()
                    mock_signing_key.key = mock_public_key
                    mock_jwks_client.get_signing_key_from_jwt.return_value = mock_signing_key
                    mock_get_jwks.return_value = mock_jwks_client

                    mock_jwt.decode.side_effect = ExpiredSignatureError("Token expired")

                    from notify.realtime.auth import validate_keycloak_token

                    result = await validate_keycloak_token("expired-token")
                    assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_invalid_token(self) -> None:
        """Test that validation returns None for invalid tokens."""
        from jwt.exceptions import InvalidTokenError

        with patch("notify.realtime.auth.app_settings") as mock_settings:
            mock_settings.realtime_enabled = True
            mock_settings.keycloak_url = "http://keycloak:8080"
            mock_settings.keycloak_realm = "bud"

            with patch("notify.realtime.auth.jwt") as mock_jwt:
                mock_jwt.get_unverified_header.return_value = {"kid": "key-123"}

                mock_public_key = MagicMock()

                with patch("notify.realtime.auth._get_jwks_client") as mock_get_jwks:
                    mock_jwks_client = MagicMock()
                    mock_signing_key = MagicMock()
                    mock_signing_key.key = mock_public_key
                    mock_jwks_client.get_signing_key_from_jwt.return_value = mock_signing_key
                    mock_get_jwks.return_value = mock_jwks_client

                    mock_jwt.decode.side_effect = InvalidTokenError("Invalid token")

                    from notify.realtime.auth import validate_keycloak_token

                    result = await validate_keycloak_token("invalid-token")
                    assert result is None


class TestRefreshJwksCache:
    """Tests for refresh_jwks_cache function."""

    @pytest.mark.asyncio
    async def test_refresh_clears_cache(self) -> None:
        """Test that refresh_jwks_cache clears the cache."""
        from notify.realtime.auth import _jwks_client_cache, _public_key_cache, refresh_jwks_cache

        _jwks_client_cache["http://keycloak:8080:bud"] = MagicMock()
        _public_key_cache["http://keycloak:8080:bud:key-123"] = MagicMock()

        with patch("notify.realtime.auth._get_jwks_client") as mock_get_jwks:
            mock_get_jwks.return_value = MagicMock()

            result = await refresh_jwks_cache("http://keycloak:8080", "bud")

            assert result is True
