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

"""Dapr service invocation utilities for budmetrics."""

import json
from typing import List
from uuid import UUID

from budmicroframe.commons import logging
from dapr.clients import DaprClient


logger = logging.get_logger(__name__)


class DaprServiceClient:
    """Dapr client for service-to-service communication."""

    def __init__(self):
        """Initialize the Dapr client."""
        self._client = None

    async def __aenter__(self):
        """Async context manager entry."""
        self._client = DaprClient()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._client:
            self._client.close()

    async def get_users_with_active_billing(self) -> List[str]:
        """Get all user IDs that have active billing records from budapp.

        Returns:
            List[str]: List of user ID strings with active billing records
        """
        try:
            if not self._client:
                raise RuntimeError("DaprServiceClient not initialized. Use within async context manager.")

            logger.info("Requesting users with active billing from budapp service")

            # Note: This call is currently unauthenticated. The 'budapp' endpoint relies on
            # an admin user check for authorization. Proper service-to-service authentication
            # (e.g., using OAuth2 client credentials with Dapr) should be implemented for production.
            response = await self._client.invoke_method(
                app_id="budapp",
                method_name="billing/users-with-billing",
                http_verb="GET",
                content_type="application/json",
            )

            if response.status_code != 200:
                logger.error(f"Failed to get users with billing from budapp: {response.status_code}")
                return []

            # Parse the response
            response_data = json.loads(response.data)
            if response_data.get("success") and "result" in response_data:
                user_ids = response_data["result"]
                logger.info(f"Retrieved {len(user_ids)} users with active billing from budapp")
                return user_ids
            else:
                logger.error(f"Invalid response format from budapp: {response_data}")
                return []

        except Exception as e:
            logger.error(f"Error calling budapp for users with billing: {e}")
            return []


async def get_users_with_active_billing() -> List[UUID]:
    """Get users with active billing records.

    Returns:
        List[UUID]: List of user UUIDs with active billing records
    """
    try:
        async with DaprServiceClient() as client:
            user_id_strings = await client.get_users_with_active_billing()

            # Convert strings back to UUIDs
            user_ids = []
            for user_id_str in user_id_strings:
                try:
                    user_ids.append(UUID(user_id_str))
                except ValueError as e:
                    logger.warning(f"Invalid UUID format from budapp: {user_id_str}, error: {e}")
                    continue

            logger.info(f"Converted {len(user_ids)} user IDs to UUID format")
            return user_ids

    except Exception as e:
        logger.error(f"Error in get_users_with_active_billing: {e}")
        return []
