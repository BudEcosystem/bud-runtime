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

"""Secure token exchange service for OAuth authentication."""

import json
import secrets
import uuid
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from typing import Dict, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from budapp.commons import logging
from budapp.commons.config import app_settings
from budapp.commons.constants import UserRoleEnum, UserStatusEnum, UserTypeEnum
from budapp.commons.exceptions import ClientException
from budapp.commons.keycloak import KeycloakManager
from budapp.shared.dapr_service import DaprService
from budapp.user_ops.crud import UserDataManager
from budapp.user_ops.models import Tenant, TenantClient, User
from budapp.user_ops.schemas import TenantClientSchema


logger = logging.get_logger(__name__)

# Prefix for exchange token keys in state store
EXCHANGE_TOKEN_PREFIX = "exchange_token:"


class TokenExchangeService:
    """Service for secure token exchange after OAuth authentication."""

    def __init__(self, session: Session):
        self.session = session
        self.keycloak_manager = KeycloakManager()
        self.dapr_service = DaprService()

    async def create_exchange_token(
        self,
        user_id: UUID,
        email: str,
        is_new_user: bool = False,
        provider: str = None,
        ttl_seconds: int = 60,  # Short-lived: 1 minute default
    ) -> str:
        """Create a short-lived exchange token for secure token retrieval.

        Args:
            user_id: The authenticated user's ID
            email: User's email
            is_new_user: Whether this is a new user registration
            provider: OAuth provider used for authentication
            ttl_seconds: Time to live for exchange token (default 60 seconds)

        Returns:
            A secure random exchange token
        """
        # Generate a cryptographically secure random token
        exchange_token = secrets.token_urlsafe(32)

        # Create state store key
        state_key = f"{EXCHANGE_TOKEN_PREFIX}{exchange_token}"

        # Store token data with expiration
        token_data = {
            "user_id": str(user_id),
            "email": email,
            "is_new_user": is_new_user,
            "provider": provider,
            "created_at": datetime.now(UTC).isoformat(),
            "expires_at": (datetime.now(UTC) + timedelta(seconds=ttl_seconds)).isoformat(),
            "used": False,  # Ensure single use
        }

        # Save to Dapr state store with TTL
        await self.dapr_service.save_to_statestore(
            key=state_key,
            value=token_data,
            store_name=app_settings.statestore_name,
            ttl=ttl_seconds,  # Use TTL for automatic expiration
            skip_etag_if_unset=True,
        )

        logger.info(f"Created exchange token for user {email} (expires in {ttl_seconds}s)")

        return exchange_token

    async def exchange_token_for_jwt(self, exchange_token: str) -> Dict:
        """Exchange a temporary token for JWT tokens.

        Args:
            exchange_token: The temporary exchange token

        Returns:
            Dict containing access_token, refresh_token, and user info

        Raises:
            ClientException: If token is invalid, expired, or already used
        """
        # Create state store key
        state_key = f"{EXCHANGE_TOKEN_PREFIX}{exchange_token}"

        # Retrieve token data from Dapr state store
        try:
            response = self.dapr_service.get_state(store_name=app_settings.statestore_name, key=state_key)

            if not response.data:
                logger.warning("Invalid exchange token attempted")
                raise ClientException("Invalid or expired exchange token")

            exchange_data = json.loads(response.data.decode("utf-8"))

        except Exception as e:
            logger.warning(f"Failed to retrieve exchange token: {e}")
            raise ClientException("Invalid or expired exchange token")

        # Check if token has expired (backup check, TTL should handle this)
        expires_at = datetime.fromisoformat(exchange_data["expires_at"])
        if expires_at < datetime.now(UTC):
            # Delete the expired token
            with suppress(Exception):
                self.dapr_service.delete_state(store_name=app_settings.statestore_name, key=state_key)
            logger.warning(f"Expired exchange token attempted for user {exchange_data['email']}")
            raise ClientException("Exchange token has expired")

        # Check if token has already been used (prevent replay attacks)
        if exchange_data["used"]:
            logger.warning(f"Reused exchange token attempted for user {exchange_data['email']}")
            # Delete the token to prevent further attempts
            with suppress(Exception):
                self.dapr_service.delete_state(store_name=app_settings.statestore_name, key=state_key)
            raise ClientException("Exchange token has already been used")

        # Mark token as used by updating the state
        exchange_data["used"] = True
        try:
            await self.dapr_service.save_to_statestore(
                key=state_key,
                value=exchange_data,
                store_name=app_settings.statestore_name,
                etag=response.etag,  # Use etag for optimistic concurrency
                concurrency="first_write",  # Prevent concurrent updates
            )
        except Exception as e:
            logger.error(f"Failed to mark token as used: {e}")
            # Continue anyway, but log the error

        # Get user from database
        user_id = UUID(exchange_data["user_id"])
        user = await UserDataManager(self.session).retrieve_by_fields(User, {"id": user_id})

        if not user:
            # Delete the token
            with suppress(Exception):
                self.dapr_service.delete_state(store_name=app_settings.statestore_name, key=state_key)
            raise ClientException("User not found")

        # Get tenant for the user (default tenant for now)
        tenant = await UserDataManager(self.session).retrieve_by_fields(
            Tenant, {"realm_name": app_settings.default_realm_name}, missing_ok=True
        )
        if not tenant:
            # Delete the token
            with suppress(Exception):
                self.dapr_service.delete_state(store_name=app_settings.statestore_name, key=state_key)
            raise ClientException("Default tenant not found")

        # Get tenant client credentials
        tenant_client = await UserDataManager(self.session).retrieve_by_fields(
            TenantClient, {"tenant_id": tenant.id}, missing_ok=True
        )
        if not tenant_client:
            # Delete the token
            with suppress(Exception):
                self.dapr_service.delete_state(store_name=app_settings.statestore_name, key=state_key)
            raise ClientException("Tenant client configuration not found")

        # Generate tokens for OAuth users using Keycloak
        # We'll set a secure random password for the OAuth user in Keycloak
        # and use it to authenticate and get proper Keycloak-signed tokens

        logger.info(f"Generating tokens for OAuth user {user.email} using Keycloak")

        try:
            # Generate a secure random password for this OAuth session
            # This password is only used internally and never exposed to the user
            oauth_session_password = secrets.token_urlsafe(32)

            # Check if user needs to be created in Keycloak (for permission management)
            if not user.auth_id:
                logger.info(f"User {user.email} has no auth_id, attempting to sync with Keycloak")
                try:
                    from python_keycloak import KeycloakAdmin

                    realm_admin = self.keycloak_manager.get_realm_admin(tenant.realm_name)
                    keycloak_users = realm_admin.get_users(query={"email": user.email})

                    if keycloak_users:
                        # User exists in Keycloak, just update our record
                        user.auth_id = UUID(keycloak_users[0]["id"])
                        self.session.commit()
                        logger.info(f"Found and synced auth_id for existing user {user.email}")
                    else:
                        # User doesn't exist in Keycloak, create them
                        logger.info(f"Creating user {user.email} in Keycloak for permission management")
                        from budapp.user_ops.schemas import UserCreate

                        # Get user permissions from database
                        user_permissions = user.permissions if user.permissions else []

                        # Create UserCreate object for Keycloak
                        # Use the session password for this OAuth user
                        user_create_data = UserCreate(
                            name=user.name,
                            email=user.email,
                            password=oauth_session_password,  # Use the session password
                            role=user.role or UserRoleEnum.DEVELOPER,
                            user_type=user.user_type or UserTypeEnum.CLIENT,
                            permissions=user_permissions,
                            status=user.status or UserStatusEnum.ACTIVE,
                        )

                        # Create user in Keycloak with permissions
                        keycloak_user_id = await self.keycloak_manager.create_user_with_permissions(
                            user_create_data,
                            realm_name=tenant.realm_name,
                            client_id=tenant_client.client_id,
                        )
                        user.auth_id = UUID(keycloak_user_id)
                        self.session.commit()
                        logger.info(f"Created user {user.email} in Keycloak with permissions")

                except Exception as keycloak_error:
                    # Non-critical error - user can still login even without Keycloak sync
                    logger.warning(f"Failed to sync user with Keycloak (non-critical): {keycloak_error}")
                    raise ClientException(f"Failed to sync user with authentication service: {str(keycloak_error)}")

            # If user already has auth_id, update their password in Keycloak for this session
            if user.auth_id:
                logger.info(f"Updating password for OAuth user {user.email} in Keycloak")
                await self.keycloak_manager.update_user_password(
                    user_id=str(user.auth_id), password=oauth_session_password, realm_name=tenant.realm_name
                )

            # Decrypt client secret for authentication
            decrypted_secret = await tenant_client.get_decrypted_client_secret()
            credentials = TenantClientSchema(
                id=tenant_client.id,
                client_id=tenant_client.client_id,
                client_named_id=tenant_client.client_named_id,
                client_secret=decrypted_secret,
            )

            # Authenticate with Keycloak using the session password to get proper tokens
            token_data = await self.keycloak_manager.authenticate_user(
                username=user.email,
                password=oauth_session_password,
                realm_name=tenant.realm_name,
                credentials=credentials,
            )

            if not token_data:
                raise ClientException("Failed to generate authentication tokens")

            logger.info(f"Successfully generated Keycloak tokens for OAuth user {user.email}")

        except Exception as e:
            logger.error(f"Failed to generate tokens for user {user.email}: {e}")
            # Delete the exchange token on failure
            with suppress(Exception):
                self.dapr_service.delete_state(store_name=app_settings.statestore_name, key=state_key)
            raise ClientException(f"Failed to generate authentication tokens: {str(e)}")

        # Delete the exchange token after successful use
        try:
            self.dapr_service.delete_state(store_name=app_settings.statestore_name, key=state_key)
        except Exception as delete_error:
            logger.warning(f"Failed to delete exchange token: {delete_error}")
            # Don't fail the request if deletion fails

        logger.info(f"Successfully exchanged token for user {user.email}")

        # Return Keycloak tokens and user info
        return {
            "access_token": token_data.get("access_token"),
            "refresh_token": token_data.get("refresh_token"),
            "token_type": token_data.get("token_type", "Bearer"),
            "expires_in": token_data.get("expires_in", 3600),
            "user": {
                "id": str(user.id),
                "email": user.email,
                "name": user.name,
                "is_new_user": exchange_data["is_new_user"],
                "provider": exchange_data["provider"],
            },
        }
