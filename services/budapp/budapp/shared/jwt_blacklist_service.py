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

"""JWT Blacklist service using Dapr state store."""

import time
from typing import Optional

from budapp.commons import logging
from budapp.commons.config import app_settings

from .dapr_service import DaprService
from .singleton import SingletonMeta


logger = logging.get_logger(__name__)


class JWTBlacklistService(metaclass=SingletonMeta):
    """Service for managing JWT blacklist using Dapr state store."""

    def __init__(self):
        """Initialize the JWT blacklist service."""
        self.dapr_client = DaprService()
        self.prefix = "jwt_blacklist:"

    async def blacklist_token(self, token: str, ttl: Optional[int] = None) -> None:
        """Add a JWT token to the blacklist with optional TTL.

        Args:
            token: The JWT token to blacklist
            ttl: Time-to-live in seconds. If None, defaults to 1 hour
        """
        try:
            if ttl is None:
                ttl = 3600  # Default 1 hour TTL

            key = f"{self.prefix}{token}"
            value = {
                "blacklisted": True,
                "timestamp": int(time.time()),
            }

            await self.dapr_client.save_to_statestore(
                key=key,
                value=value,
                ttl=ttl,
                store_name=app_settings.statestore_name,
                skip_etag_if_unset=True,
            )
            logger.info(f"Token blacklisted successfully with TTL {ttl} seconds")
        except Exception as e:
            logger.error(f"Failed to blacklist token: {e}")
            raise

    async def is_token_blacklisted(self, token: str) -> bool:
        """Check if a JWT token is blacklisted.

        Args:
            token: The JWT token to check

        Returns:
            bool: True if the token is blacklisted, False otherwise
        """
        try:
            key = f"{self.prefix}{token}"
            store_name = app_settings.statestore_name

            if not store_name:
                logger.warning("State store not configured, skipping blacklist check")
                return False

            response = self.dapr_client.get_state(store_name=store_name, key=key)

            if response.data:
                logger.debug("Token found in blacklist")
                return True

            return False
        except Exception as e:
            logger.warning(f"Failed to check token blacklist: {e}")
            # In case of error, we don't want to block the request
            return False

    async def remove_from_blacklist(self, token: str) -> None:
        """Remove a token from the blacklist.

        Args:
            token: The JWT token to remove from blacklist
        """
        try:
            key = f"{self.prefix}{token}"
            store_name = app_settings.statestore_name

            if not store_name:
                logger.warning("State store not configured")
                return

            self.dapr_client.delete_state(store_name=store_name, key=key)
            logger.info("Token removed from blacklist")
        except Exception as e:
            logger.error(f"Failed to remove token from blacklist: {e}")
            raise
