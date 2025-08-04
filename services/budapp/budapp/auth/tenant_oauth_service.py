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

"""Service for managing tenant-specific OAuth configurations."""

import base64
from typing import List, Optional
from uuid import UUID

from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from budapp.commons import logging
from budapp.commons.config import app_settings
from budapp.commons.constants import OAuthProviderEnum
from budapp.commons.db_utils import SessionMixin
from budapp.commons.exceptions import ClientException
from budapp.commons.keycloak import KeycloakManager
from budapp.user_ops.crud import UserDataManager
from budapp.user_ops.models import Tenant
from budapp.user_ops.oauth_models import TenantOAuthConfig


logger = logging.get_logger(__name__)


class TenantOAuthService(SessionMixin):
    """Service for managing tenant OAuth configurations."""

    def __init__(self, session: Session):
        """Initialize tenant OAuth service."""
        super().__init__(session)
        self.keycloak_manager = KeycloakManager()
        self._encryption_key = self._get_or_create_encryption_key()
        self._cipher_suite = Fernet(self._encryption_key)

    def _get_or_create_encryption_key(self) -> bytes:
        """Get or create encryption key for OAuth secrets."""
        # In production, this should be stored securely (e.g., in a key vault)
        # For now, use a key from environment or generate one
        key_str = app_settings.oauth_encryption_key if hasattr(app_settings, "oauth_encryption_key") else None
        if key_str:
            return base64.urlsafe_b64decode(key_str)
        else:
            # Generate a new key (in production, store this securely)
            return Fernet.generate_key()

    def _encrypt_secret(self, secret: str) -> str:
        """Encrypt OAuth client secret."""
        return self._cipher_suite.encrypt(secret.encode()).decode()

    def _decrypt_secret(self, encrypted_secret: str) -> str:
        """Decrypt OAuth client secret."""
        return self._cipher_suite.decrypt(encrypted_secret.encode()).decode()

    async def configure_oauth_provider(
        self,
        tenant_id: UUID,
        provider: OAuthProviderEnum,
        client_id: str,
        client_secret: str,
        enabled: bool = True,
        allowed_domains: Optional[List[str]] = None,
        auto_create_users: bool = False,
        config_data: Optional[dict] = None,
    ) -> TenantOAuthConfig:
        """Configure OAuth provider for a tenant.

        Args:
            tenant_id: Tenant ID
            provider: OAuth provider
            client_id: OAuth client ID
            client_secret: OAuth client secret
            enabled: Whether provider is enabled
            allowed_domains: List of allowed email domains
            auto_create_users: Whether to auto-create users on first login
            config_data: Additional provider-specific configuration

        Returns:
            TenantOAuthConfig object
        """
        # Get tenant
        tenant = await UserDataManager(self.session).retrieve_by_fields(Tenant, {"id": tenant_id})

        # Check if configuration already exists
        existing_config = await UserDataManager(self.session).retrieve_by_fields(
            TenantOAuthConfig, {"tenant_id": tenant_id, "provider": provider.value}, missing_ok=True
        )

        # Encrypt client secret
        encrypted_secret = self._encrypt_secret(client_secret)

        if existing_config:
            # Update existing configuration
            existing_config.client_id = client_id
            existing_config.client_secret_encrypted = encrypted_secret
            existing_config.enabled = enabled
            existing_config.allowed_domains = allowed_domains
            existing_config.auto_create_users = auto_create_users
            existing_config.config_data = config_data or {}
            oauth_config = existing_config
        else:
            # Create new configuration
            oauth_config = TenantOAuthConfig(
                tenant_id=tenant_id,
                provider=provider.value,
                client_id=client_id,
                client_secret_encrypted=encrypted_secret,
                enabled=enabled,
                allowed_domains=allowed_domains,
                auto_create_users=auto_create_users,
                config_data=config_data or {},
            )
            UserDataManager(self.session).add_one(oauth_config)

        # Configure in Keycloak
        await self._configure_keycloak_identity_provider(
            tenant.realm_name, provider, client_id, client_secret, config_data
        )

        self.session.commit()
        return oauth_config

    async def _configure_keycloak_identity_provider(
        self,
        realm_name: str,
        provider: OAuthProviderEnum,
        client_id: str,
        client_secret: str,
        config_data: Optional[dict] = None,
    ) -> None:
        """Configure identity provider in Keycloak."""
        provider_configs = {
            OAuthProviderEnum.GOOGLE: {
                "alias": "google",
                "providerId": "google",
                "config": {
                    "hostedDomain": config_data.get("hostedDomain") if config_data else None,
                    "userIp": "true",
                    "offlineAccess": "false",
                },
            },
            OAuthProviderEnum.LINKEDIN: {"alias": "linkedin", "providerId": "linkedin", "config": {}},
            OAuthProviderEnum.GITHUB: {"alias": "github", "providerId": "github", "config": {}},
            OAuthProviderEnum.MICROSOFT: {
                "alias": "microsoft",
                "providerId": "microsoft",
                "config": {
                    # Microsoft provider expects "tenant" field in Keycloak config
                    # Support both "tenantId" and "tenant" in config_data for flexibility
                    "tenant": config_data.get("tenantId", config_data.get("tenant", "common"))
                    if config_data
                    else "common",
                },
            },
        }

        provider_config = provider_configs.get(provider)
        if not provider_config:
            raise ClientException(f"Unsupported OAuth provider: {provider}")

        # Merge with base configuration
        full_config = {
            **provider_config,
            "clientId": client_id,
            "clientSecret": client_secret,
        }

        # Configure in Keycloak
        await self.keycloak_manager.configure_identity_provider(realm_name, full_config)

        # Configure attribute mappers for consistent user data
        await self._configure_attribute_mappers(realm_name, provider_config["alias"], provider)

    async def _configure_attribute_mappers(
        self, realm_name: str, provider_alias: str, provider: OAuthProviderEnum
    ) -> None:
        """Configure attribute mappers for identity provider."""
        # Common mappers for all providers
        mappers = [
            {
                "name": f"{provider_alias}-email-mapper",
                "identityProviderAlias": provider_alias,
                "identityProviderMapper": "oidc-user-attribute-idp-mapper",
                "config": {"claim": "email", "user.attribute": "email", "syncMode": "INHERIT"},
            },
            {
                "name": f"{provider_alias}-username-mapper",
                "identityProviderAlias": provider_alias,
                "identityProviderMapper": "oidc-username-idp-mapper",
                "config": {"template": "${CLAIM.email}", "syncMode": "INHERIT"},
            },
        ]

        # Provider-specific mappers
        if provider == OAuthProviderEnum.GOOGLE:
            mappers.extend(
                [
                    {
                        "name": f"{provider_alias}-given-name-mapper",
                        "identityProviderAlias": provider_alias,
                        "identityProviderMapper": "oidc-user-attribute-idp-mapper",
                        "config": {"claim": "given_name", "user.attribute": "firstName", "syncMode": "INHERIT"},
                    },
                    {
                        "name": f"{provider_alias}-family-name-mapper",
                        "identityProviderAlias": provider_alias,
                        "identityProviderMapper": "oidc-user-attribute-idp-mapper",
                        "config": {"claim": "family_name", "user.attribute": "lastName", "syncMode": "INHERIT"},
                    },
                ]
            )

        # Create mappers in Keycloak
        for mapper in mappers:
            try:
                await self.keycloak_manager.create_identity_provider_mapper(realm_name, provider_alias, mapper)
            except Exception as e:
                logger.warning(f"Failed to create mapper {mapper['name']}: {str(e)}")

    async def get_oauth_configurations(self, tenant_id: UUID, enabled_only: bool = True) -> List[TenantOAuthConfig]:
        """Get OAuth configurations for a tenant.

        Args:
            tenant_id: Tenant ID
            enabled_only: Whether to return only enabled configurations

        Returns:
            List of TenantOAuthConfig objects
        """
        filters = {"tenant_id": tenant_id}
        if enabled_only:
            filters["enabled"] = True

        return await UserDataManager(self.session).retrieve_by_fields_all(TenantOAuthConfig, filters)

    async def disable_oauth_provider(self, tenant_id: UUID, provider: OAuthProviderEnum) -> bool:
        """Disable OAuth provider for a tenant.

        Args:
            tenant_id: Tenant ID
            provider: OAuth provider to disable

        Returns:
            bool: Success status
        """
        config = await UserDataManager(self.session).retrieve_by_fields(
            TenantOAuthConfig, {"tenant_id": tenant_id, "provider": provider.value}, missing_ok=True
        )

        if not config:
            raise ClientException(f"OAuth provider {provider.value} not configured for tenant")

        config.enabled = False
        self.session.commit()

        return True

    async def get_decrypted_config(self, tenant_id: UUID, provider: OAuthProviderEnum) -> Optional[dict]:
        """Get decrypted OAuth configuration for a tenant and provider.

        Args:
            tenant_id: Tenant ID
            provider: OAuth provider

        Returns:
            dict with decrypted configuration or None
        """
        config = await UserDataManager(self.session).retrieve_by_fields(
            TenantOAuthConfig, {"tenant_id": tenant_id, "provider": provider.value}, missing_ok=True
        )

        if not config:
            return None

        return {
            "provider": config.provider,
            "client_id": config.client_id,
            "client_secret": self._decrypt_secret(config.client_secret_encrypted),
            "enabled": config.enabled,
            "allowed_domains": config.allowed_domains,
            "auto_create_users": config.auto_create_users,
            "config_data": config.config_data,
        }
