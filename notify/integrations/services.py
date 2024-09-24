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


"""Implements provider services and business logic that power the microservices, including key functionality and integrations."""

from typing import List

from novu.dto.integration import IntegrationDto

from notify.commons import logging
from notify.commons.config import secrets_settings
from notify.commons.exceptions import NovuApiClientException
from notify.shared.novu_service import NovuService

from .schemas import IntegrationListItem, IntegrationRequest


logger = logging.get_logger(__name__)


class IntegrationsService(NovuService):
    """Implements integration services and business logic that power the microservices, including key functionality and providers."""

    async def create_novu_integration(self, data: IntegrationRequest) -> IntegrationDto:
        """Create a new integration for a specified channel and provider in Novu.

        If there are no active integrations for the specified channel, the newly created
        integration will be marked as the primary one. Otherwise, it will just be created.

        Args:
            data (IntegrationRequest): The data for creating the integration, including the provider,
                                       channel, and credentials.

        Returns:
            IntegrationDto: The newly created integration data.
        """
        # Fetch active integrations and filter those matching the requested channel
        try:
            active_integrations = await self.get_active_integrations()
        except NovuApiClientException as err:
            logger.error(err.message)
            raise

        active_channel_integrations = [
            integration for integration in active_integrations if integration.channel == data.channel.value
        ]

        logger.debug(f"Active {data.channel.value} integrations: {len(active_channel_integrations)}")

        # Prepare integration data
        integration_data = IntegrationDto(
            provider_id=data.provider_id.value,
            channel=data.channel.value,
            active=data.active,
            credentials=data.credentials,
            _environment_id=secrets_settings.novu_prod_env_id,
        )

        # Create the integration in Novu
        try:
            db_integration = await self.create_integration(integration_data, check=data.check, environment="prod")
            logger.debug(f"Created {data.provider_id.value} integration: {db_integration._id}")
        except NovuApiClientException as err:
            logger.error(err.message)
            raise

        # If no active integrations exist for this channel, mark the new one as primary
        if len(active_channel_integrations) == 0:
            _ = await self.set_integration_as_primary(db_integration._id, environment="prod")
            logger.debug(f"Marked {data.provider_id} integration as primary")

        return db_integration

    async def list_novu_integrations(self) -> List[IntegrationListItem]:
        """Return a list of all Novu integrations.

        Returns:
            List[IntegrationListItem]: A list of integration items containing the details of each integration.

        Raises:
            NovuApiClientException: If the API call to retrieve integrations fails.
        """
        try:
            db_integrations = await self.get_integrations_curl(environment="prod")
            logger.debug(f"Found {len(db_integrations)} integrations")
        except NovuApiClientException as err:
            logger.error(err.message)
            raise

        # Convert the raw integration data into IntegrationListItem objects
        integrations = [
            IntegrationListItem(
                id=integration["_id"],
                provider_id=integration["providerId"],
                channel=integration["channel"],
                active=integration["active"],
                created_at=integration["createdAt"],
                updated_at=integration["updatedAt"],
                deleted=integration["deleted"],
                primary=integration["primary"],
                credentials=integration["credentials"],
            )
            for integration in db_integrations
            if integration["channel"] != "in_app"
        ]

        return integrations

    async def update_novu_integration(self, integration_id: str, data: IntegrationRequest) -> IntegrationDto:
        """Update a Novu integration with the given integration ID and new data.

        Args:
            integration_id (str): The ID of the integration to be updated.
            data (IntegrationRequest): The data for updating the integration.

        Returns:
            IntegrationDto: The updated integration object.

        Raises:
            NovuApiClientException: If the update operation fails.
        """
        # Prepare integration data
        integration_data = IntegrationDto(
            provider_id=data.provider_id.value,
            channel=data.channel.value,
            active=data.active,
            credentials=data.credentials,
            _environment_id=secrets_settings.novu_prod_env_id,
            _id=integration_id,
        )

        # Create the integration in Novu
        try:
            db_integration = await self.update_integration(integration_data, check=data.check, environment="prod")
            logger.debug(f"Updated integration {data.provider_id.value} successfully")
            return db_integration
        except NovuApiClientException as err:
            logger.error(err.message)
            raise

    async def delete_novu_integration(self, integration_id: str) -> None:
        """Delete a Novu integration with the given integration ID.

        Args:
            integration_id (str): The ID of the integration to be deleted.

        Raises:
            NovuApiClientException: If the deletion fails.
        """
        try:
            await self.delete_integration(integration_id, environment="prod")
            logger.debug(f"Integration id {integration_id} deleted successfully")
            return
        except NovuApiClientException as err:
            logger.error(err.message)
            raise

    async def set_novu_integration_as_primary(self, integration_id: str) -> IntegrationDto:
        """Mark the specified integration as the primary integration in the Novu system.

        Args:
            integration_id (str): The ID of the integration to be marked as primary.

        Returns:
            IntegrationDto: The updated integration details marked as primary.
        """
        try:
            db_integration = await self.set_integration_as_primary(integration_id=integration_id, environment="prod")
            logger.debug("Successfully set integration as primary")
            return db_integration
        except NovuApiClientException as err:
            logger.error(err.message)
            raise
