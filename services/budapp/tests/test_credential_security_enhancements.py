"""Tests for enhanced API key security features."""

import pytest
from datetime import datetime, timedelta, UTC
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from budapp.commons.constants import ApiCredentialTypeEnum, UserTypeEnum
from budapp.credential_ops.helpers import generate_secure_api_key
from budapp.credential_ops.models import Credential
from budapp.credential_ops.schemas import CredentialRequest
from budapp.credential_ops.services import CredentialService


class TestSecureKeyGeneration:
    """Test secure API key generation."""

    def test_generate_secure_api_key_format(self):
        """Test that generated keys have the correct format."""
        # Test client app key
        key = generate_secure_api_key("client_app")
        assert key.startswith("bud_client_")
        assert len(key) > 50  # Should be long enough

        # Test admin app key
        key = generate_secure_api_key("admin_app")
        assert key.startswith("bud_admin_")

    def test_generate_secure_api_key_uniqueness(self):
        """Test that generated keys are unique."""
        keys = set()
        for _ in range(100):
            key = generate_secure_api_key("client_app")
            assert key not in keys
            keys.add(key)

    def test_generate_secure_api_key_url_safe(self):
        """Test that generated keys are URL-safe."""
        key = generate_secure_api_key("client_app")
        # Remove the prefix to test the random part
        random_part = key.split("_", 2)[2]
        # URL-safe base64 should not contain +, /, or =
        assert "+" not in random_part
        assert "/" not in random_part
        assert "=" not in random_part




class TestCredentialValidation:
    """Test enhanced credential validation."""


    @pytest.mark.asyncio
    async def test_is_credential_valid_with_expired(self):
        """Test validation fails for expired credential."""
        session = MagicMock(spec=Session)
        service = CredentialService(session)

        # Mock expired credential
        mock_credential = MagicMock(spec=Credential)
        mock_credential.expiry = datetime.now(UTC) - timedelta(days=1)  # Expired yesterday
        mock_credential.ip_whitelist = None

        with patch("budapp.credential_ops.services.RedisService") as mock_redis:
            mock_redis_instance = mock_redis.return_value
            mock_redis_instance.get = AsyncMock(return_value=None)

            with patch("budapp.credential_ops.services.CredentialDataManager") as mock_dm:
                mock_dm.return_value.retrieve_by_fields = AsyncMock(return_value=mock_credential)

                result = await service.is_credential_valid("test_hashed_key")
                assert result is False

    @pytest.mark.asyncio
    async def test_is_credential_valid_with_ip_whitelist(self):
        """Test validation with IP whitelist."""
        session = MagicMock(spec=Session)
        service = CredentialService(session)

        # Mock credential with IP whitelist
        mock_credential = MagicMock(spec=Credential)
        mock_credential.expiry = None
        mock_credential.ip_whitelist = ["192.168.1.1", "10.0.0.1"]
        mock_credential.id = uuid4()

        with patch("budapp.credential_ops.services.RedisService") as mock_redis:
            mock_redis_instance = mock_redis.return_value
            mock_redis_instance.get = AsyncMock(return_value=None)

            with patch("budapp.credential_ops.services.CredentialDataManager") as mock_dm:
                mock_dm.return_value.retrieve_by_fields = AsyncMock(return_value=mock_credential)

                # Test with allowed IP
                result = await service.is_credential_valid("test_hashed_key", "192.168.1.1")
                assert result is True

                # Test with disallowed IP
                result = await service.is_credential_valid("test_hashed_key", "192.168.2.1")
                assert result is False


class TestCredentialTypeMapping:
    """Test automatic credential type mapping based on user type."""

    @pytest.mark.asyncio
    async def test_client_user_creates_client_credential(self):
        """Test that client users automatically get client_app credentials."""
        session = MagicMock(spec=Session)
        service = CredentialService(session)

        # Mock user with CLIENT type
        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_user.user_type = UserTypeEnum.CLIENT

        # Mock credential request
        request = CredentialRequest(
            name="Test Key",
            project_id=uuid4(),
            credential_type=ApiCredentialTypeEnum.ADMIN_APP  # Try to request admin type
        )

        with patch("budapp.credential_ops.services.UserDataManager") as mock_user_dm:
            mock_user_dm.return_value.retrieve_user_by_fields = AsyncMock(return_value=mock_user)

            with patch("budapp.credential_ops.services.CredentialDataManager") as mock_cred_dm:
                mock_cred_dm.return_value.create_credential = AsyncMock()

                # Call add_or_generate_credential
                result = await service.add_or_generate_credential(request, mock_user.id)

                # Verify credential was created with client_app type
                create_call = mock_cred_dm.return_value.create_credential.call_args[0][0]
                assert create_call.credential_type == ApiCredentialTypeEnum.CLIENT_APP

    @pytest.mark.asyncio
    async def test_admin_user_can_create_any_credential(self):
        """Test that admin users can create any credential type."""
        session = MagicMock(spec=Session)
        service = CredentialService(session)

        # Mock user with ADMIN type
        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_user.user_type = UserTypeEnum.ADMIN

        # Test admin can create admin_app credential
        request = CredentialRequest(
            name="Test Admin Key",
            project_id=uuid4(),
            credential_type=ApiCredentialTypeEnum.ADMIN_APP
        )

        with patch("budapp.credential_ops.services.UserDataManager") as mock_user_dm:
            mock_user_dm.return_value.retrieve_user_by_fields = AsyncMock(return_value=mock_user)

            with patch("budapp.credential_ops.services.CredentialDataManager") as mock_cred_dm:
                mock_cred_dm.return_value.create_credential = AsyncMock()

                # Call add_or_generate_credential
                result = await service.add_or_generate_credential(request, mock_user.id)

                # Verify credential was created with requested type
                create_call = mock_cred_dm.return_value.create_credential.call_args[0][0]
                assert create_call.credential_type == ApiCredentialTypeEnum.ADMIN_APP
