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

"""Password Reset Token Service using Dapr State Store."""

import json
import secrets
import time
from datetime import UTC, datetime, timedelta
from typing import Dict, Optional
from uuid import UUID

from budapp.commons import logging
from budapp.commons.config import app_settings
from budapp.shared.dapr_service import DaprService


logger = logging.get_logger(__name__)


class PasswordResetTokenService:
    """Service for managing password reset tokens using Dapr state store."""

    def __init__(self):
        """Initialize the password reset token service."""
        self.dapr_client = DaprService()
        self.prefix = "password_reset_token:"
        self.user_prefix = "user_reset_tokens:"
        self.token_ttl = 3600  # 1 hour in seconds

    def _generate_token(self) -> str:
        """Generate a secure reset token."""
        return secrets.token_urlsafe(32)

    def _get_token_key(self, token: str) -> str:
        """Get the key for storing token data."""
        return f"{self.prefix}{token}"

    def _get_user_tokens_key(self, user_id: UUID) -> str:
        """Get the key for storing user's active tokens."""
        return f"{self.user_prefix}{user_id}"

    async def create_reset_token(
        self, user_id: UUID, email: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None
    ) -> str:
        """Create a new password reset token and invalidate existing ones.

        Args:
            user_id: User ID
            email: User email
            ip_address: Request IP address
            user_agent: Request user agent

        Returns:
            str: The generated reset token
        """
        try:
            # Generate new token
            token = self._generate_token()

            # Invalidate existing tokens for this user
            await self._invalidate_user_tokens(user_id)

            # Create token data
            token_data = {
                "user_id": str(user_id),
                "email": email,
                "created_at": datetime.now(UTC).isoformat(),
                "expires_at": (datetime.now(UTC) + timedelta(seconds=self.token_ttl)).isoformat(),
                "is_used": False,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "timestamp": int(time.time()),
            }

            # Store token with TTL
            await self.dapr_client.save_to_statestore(
                key=self._get_token_key(token),
                value=token_data,
                ttl=self.token_ttl,
                store_name=app_settings.statestore_name,
                skip_etag_if_unset=True,
            )

            # Update user's active tokens list
            user_tokens_data = {
                "active_tokens": [token],
                "last_created": datetime.now(UTC).isoformat(),
                "timestamp": int(time.time()),
            }

            await self.dapr_client.save_to_statestore(
                key=self._get_user_tokens_key(user_id),
                value=user_tokens_data,
                ttl=self.token_ttl,
                store_name=app_settings.statestore_name,
                skip_etag_if_unset=True,
            )

            logger.info(f"Password reset token created for user {user_id}")
            return token

        except Exception as e:
            logger.error(f"Failed to create password reset token: {e}")
            raise

    async def validate_token(self, token: str) -> Dict:
        """Validate a password reset token.

        Args:
            token: The reset token to validate

        Returns:
            Dict with validation result and token data
        """
        try:
            key = self._get_token_key(token)
            response = await self.dapr_client.get_state(store_name=app_settings.statestore_name, key=key)

            if not response.data:
                return {
                    "is_valid": False,
                    "error": "Token not found",
                    "email": None,
                    "user_id": None,
                    "expires_at": None,
                }

            # Parse token data
            try:
                token_data = json.loads(response.data.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                logger.error(f"Failed to decode token data: {e}")
                return {
                    "is_valid": False,
                    "error": "Invalid token format",
                    "email": None,
                    "user_id": None,
                    "expires_at": None,
                }

            # Check if token is already used
            if token_data.get("is_used", False):
                return {
                    "is_valid": False,
                    "error": "Token already used",
                    "email": token_data.get("email"),
                    "user_id": token_data.get("user_id"),
                    "expires_at": token_data.get("expires_at"),
                }

            # Check if token is expired (additional check beyond TTL)
            expires_at = datetime.fromisoformat(token_data["expires_at"].replace("Z", "+00:00"))
            if datetime.now(UTC) > expires_at:
                return {
                    "is_valid": False,
                    "error": "Token expired",
                    "email": token_data.get("email"),
                    "user_id": token_data.get("user_id"),
                    "expires_at": token_data.get("expires_at"),
                }

            return {
                "is_valid": True,
                "error": None,
                "email": token_data.get("email"),
                "user_id": token_data.get("user_id"),
                "expires_at": token_data.get("expires_at"),
                "token_data": token_data,
            }

        except Exception as e:
            logger.error(f"Failed to validate password reset token: {e}")
            return {
                "is_valid": False,
                "error": f"Validation error: {str(e)}",
                "email": None,
                "user_id": None,
                "expires_at": None,
            }

    async def use_token(self, token: str) -> bool:
        """Mark a token as used.

        Args:
            token: The reset token to mark as used

        Returns:
            bool: True if successfully marked as used
        """
        try:
            # First validate the token
            validation_result = await self.validate_token(token)
            if not validation_result["is_valid"]:
                logger.warning("Attempted to use invalid token")
                return False

            # Get current token data
            token_data = validation_result["token_data"]
            token_data["is_used"] = True
            token_data["used_at"] = datetime.now(UTC).isoformat()

            # Update token data (keep existing TTL)
            await self.dapr_client.save_to_statestore(
                key=self._get_token_key(token),
                value=token_data,
                store_name=app_settings.statestore_name,
                skip_etag_if_unset=True,
            )

            logger.info("Password reset token marked as used")
            return True

        except Exception as e:
            logger.error(f"Failed to mark token as used: {e}")
            return False

    async def _invalidate_user_tokens(self, user_id: UUID) -> None:
        """Invalidate all existing tokens for a user.

        Args:
            user_id: User ID
        """
        try:
            user_tokens_key = self._get_user_tokens_key(user_id)
            response = self.dapr_client.get_state(store_name=app_settings.statestore_name, key=user_tokens_key)

            if response.data:
                try:
                    user_tokens_data = json.loads(response.data.decode("utf-8"))
                    active_tokens = user_tokens_data.get("active_tokens", [])

                    # Mark all existing tokens as used
                    for old_token in active_tokens:
                        try:
                            old_token_key = self._get_token_key(old_token)
                            old_response = self.dapr_client.get_state(
                                store_name=app_settings.statestore_name, key=old_token_key
                            )

                            if old_response.data:
                                old_token_data = json.loads(old_response.data.decode("utf-8"))
                                old_token_data["is_used"] = True
                                old_token_data["invalidated_at"] = datetime.now(UTC).isoformat()

                                await self.dapr_client.save_to_statestore(
                                    key=old_token_key,
                                    value=old_token_data,
                                    store_name=app_settings.statestore_name,
                                    skip_etag_if_unset=True,
                                )

                        except Exception as e:
                            logger.warning(f"Failed to invalidate token {old_token}: {e}")
                            continue

                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    logger.warning(f"Failed to decode user tokens data: {e}")

        except Exception as e:
            logger.warning(f"Failed to invalidate user tokens: {e}")
            # Don't raise here as this is a cleanup operation

    async def cleanup_expired_tokens(self) -> int:
        """Clean up expired tokens (mainly for monitoring).

        Note: With TTL enabled, Dapr/Redis will automatically clean up expired entries.
        This method is mainly for monitoring and could be used for manual cleanup if needed.

        Returns:
            int: Number of tokens that would be cleaned up (informational)
        """
        # With TTL, Dapr/Redis automatically cleans up expired entries
        # This method could be enhanced to query and report on cleanup stats
        logger.info("Token cleanup is handled automatically by Dapr state store TTL")
        return 0
