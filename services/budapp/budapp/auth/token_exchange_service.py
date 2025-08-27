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

import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Dict, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from budapp.auth.token import TokenService
from budapp.commons import logging
from budapp.commons.config import app_settings
from budapp.commons.constants import UserRoleEnum, UserStatusEnum, UserTypeEnum
from budapp.commons.exceptions import ClientException
from budapp.commons.keycloak import KeycloakManager
from budapp.user_ops.crud import UserDataManager
from budapp.user_ops.models import Tenant, TenantClient, User
from budapp.user_ops.schemas import TenantClientSchema


logger = logging.get_logger(__name__)

# Store exchange tokens in memory with their associated data
# In production, use Redis or database for distributed systems
exchange_token_store: Dict[str, Dict] = {}


class TokenExchangeService:
    """Service for secure token exchange after OAuth authentication."""

    def __init__(self, session: Session):
        self.session = session
        self.token_service = TokenService(session)
        self.keycloak_manager = KeycloakManager()

    def create_exchange_token(
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

        # Store token data with expiration
        exchange_token_store[exchange_token] = {
            "user_id": str(user_id),
            "email": email,
            "is_new_user": is_new_user,
            "provider": provider,
            "created_at": datetime.now(UTC),
            "expires_at": datetime.now(UTC) + timedelta(seconds=ttl_seconds),
            "used": False,  # Ensure single use
        }

        logger.info(f"Created exchange token for user {email} (expires in {ttl_seconds}s)")

        return exchange_token

    def cleanup_expired_tokens(self):
        """Remove expired tokens from the store."""
        current_time = datetime.now(UTC)
        expired_tokens = [token for token, data in exchange_token_store.items() if data["expires_at"] < current_time]

        for token in expired_tokens:
            del exchange_token_store[token]

        if expired_tokens:
            logger.debug(f"Cleaned up {len(expired_tokens)} expired exchange tokens")

    async def exchange_token_for_jwt(self, exchange_token: str) -> Dict:
        """Exchange a temporary token for JWT tokens.

        Args:
            exchange_token: The temporary exchange token

        Returns:
            Dict containing access_token, refresh_token, and user info

        Raises:
            ClientException: If token is invalid, expired, or already used
        """
        # Cleanup expired tokens
        self.cleanup_expired_tokens()

        # Validate exchange token
        if exchange_token not in exchange_token_store:
            logger.warning("Invalid exchange token attempted")
            raise ClientException("Invalid or expired exchange token")

        exchange_data = exchange_token_store[exchange_token]

        # Check if token has expired
        if exchange_data["expires_at"] < datetime.now(UTC):
            del exchange_token_store[exchange_token]
            logger.warning(f"Expired exchange token attempted for user {exchange_data['email']}")
            raise ClientException("Exchange token has expired")

        # Check if token has already been used (prevent replay attacks)
        if exchange_data["used"]:
            logger.warning(f"Reused exchange token attempted for user {exchange_data['email']}")
            # Delete the token to prevent further attempts
            del exchange_token_store[exchange_token]
            raise ClientException("Exchange token has already been used")

        # Mark token as used
        exchange_data["used"] = True

        # Get user from database
        user_id = UUID(exchange_data["user_id"])
        user = await UserDataManager(self.session).retrieve_by_fields(User, {"id": user_id})

        if not user:
            del exchange_token_store[exchange_token]
            raise ClientException("User not found")

        # Get tenant for the user (default tenant for now)
        tenant = await UserDataManager(self.session).retrieve_by_fields(
            Tenant, {"realm_name": app_settings.default_realm_name}, missing_ok=True
        )
        if not tenant:
            del exchange_token_store[exchange_token]
            raise ClientException("Default tenant not found")

        # Get tenant client credentials
        tenant_client = await UserDataManager(self.session).retrieve_by_fields(
            TenantClient, {"tenant_id": tenant.id}, missing_ok=True
        )
        if not tenant_client:
            del exchange_token_store[exchange_token]
            raise ClientException("Tenant client configuration not found")

        # Prepare credentials
        decrypted_secret = await tenant_client.get_decrypted_client_secret()
        credentials = TenantClientSchema(
            id=tenant_client.id,
            client_id=tenant_client.client_id,
            client_named_id=tenant_client.client_named_id,
            client_secret=decrypted_secret,
        )

        # Generate tokens through Keycloak
        # For OAuth users, we have different approaches based on how they were created
        try:
            # Check if user has auth_id (Keycloak user ID)
            if not user.auth_id:
                logger.error(f"User {user.email} has no auth_id (Keycloak ID)")
                # Try to find user in Keycloak by email
                try:
                    from python_keycloak import KeycloakAdmin

                    realm_admin = self.keycloak_manager.get_realm_admin(tenant.realm_name)
                    keycloak_users = realm_admin.get_users(query={"email": user.email})
                    if keycloak_users:
                        user.auth_id = UUID(keycloak_users[0]["id"])
                        self.session.commit()
                        logger.info(f"Found and updated auth_id for user {user.email}")
                    else:
                        logger.error(f"User {user.email} not found in Keycloak")
                        # Create user in Keycloak if not exists
                        from budapp.user_ops.schemas import UserCreate

                        # Get user permissions from database
                        user_permissions = user.permissions if user.permissions else []

                        # Create UserCreate object for Keycloak
                        user_create_data = UserCreate(
                            name=user.name,
                            email=user.email,
                            password=secrets.token_urlsafe(32),  # Random password for OAuth users
                            role=user.role or UserRoleEnum.DEVELOPER,
                            user_type=user.user_type or UserTypeEnum.CLIENT,
                            permissions=user_permissions,
                            status=user.status or UserStatusEnum.ACTIVE,
                        )

                        # Create user in Keycloak with permissions
                        keycloak_user_id = await self.keycloak_manager.create_user_with_permissions(
                            user_create_data,
                            realm_name=tenant.realm_name,
                            client_id=tenant_client.client_id,  # We already have tenant_client from above
                        )
                        user.auth_id = UUID(keycloak_user_id)
                        self.session.commit()
                        logger.info(f"Created user {user.email} in Keycloak with permissions")
                except Exception as lookup_error:
                    logger.error(f"Failed to lookup/create user in Keycloak: {lookup_error}")
                    # Don't raise here - continue with fallback logic

            # Now we should have auth_id, proceed with token generation
            # Generate a secure temporary password
            temp_password = f"Temp_{uuid.uuid4().hex}@2024"

            logger.debug(f"Updating password for user {user.email} with auth_id {user.auth_id}")

            # Update user's password in Keycloak
            await self.keycloak_manager.update_user_password(
                user_id=str(user.auth_id), password=temp_password, realm_name=tenant.realm_name
            )

            logger.debug(f"Password updated, authenticating user {user.email}")

            # Authenticate with the temporary password
            auth_token_data = await self.keycloak_manager.authenticate_user(
                username=user.email, password=temp_password, realm_name=tenant.realm_name, credentials=credentials
            )

            # Prepare token data from Keycloak response
            token_data = {
                "access_token": auth_token_data.get("access_token"),
                "refresh_token": auth_token_data.get("refresh_token"),
                "expires_in": auth_token_data.get("expires_in", 3600),
                "token_type": auth_token_data.get("token_type", "Bearer"),
            }

            logger.info(f"Successfully generated tokens through Keycloak for user {user.email}")

        except Exception as e:
            logger.error(f"Failed to generate tokens through Keycloak: {e}")
            logger.error(f"User details - email: {user.email}, auth_id: {user.auth_id}, id: {user.id}")

            # As a fallback, try to use local token generation if Keycloak fails
            # This is not ideal but allows the user to login
            try:
                logger.warning(f"Falling back to local token generation for user {user.email}")
                auth_token = await self.token_service.create_auth_token(str(user.id))
                token_data = {
                    "access_token": auth_token.access_token,
                    "refresh_token": auth_token.refresh_token,
                    "expires_in": app_settings.access_token_expire_minutes * 60,
                    "token_type": auth_token.token_type,
                }
                logger.info(f"Generated local tokens for user {user.email}")
            except Exception as local_error:
                logger.error(f"Local token generation also failed: {local_error}")
                del exchange_token_store[exchange_token]
                raise ClientException(f"Failed to generate authentication tokens: {str(e)}")

        # Delete the exchange token after successful use
        del exchange_token_store[exchange_token]

        logger.info(f"Successfully exchanged token for user {user.email}")

        # Return tokens and user info
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
