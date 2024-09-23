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


"""Implements core services and business logic that power the microservices, including key functionality and integrations."""

from typing import Dict, List

from novu.dto.subscriber import SubscriberDto

from notify.commons import logging
from notify.commons.exceptions import NovuApiClientException
from notify.shared.novu_service import NovuService

from .schemas import (
    SubscriberItem,
    SubscriberRequest,
    SubscriberUpdateRequest,
)


logger = logging.get_logger(__name__)


class SubscriberService(NovuService):
    """Implements subscriber services and business logic that power the microservices, including key functionality and providers."""

    async def create_novu_subscriber(self, data: SubscriberRequest) -> SubscriberDto:
        """Create a new subscriber in the Novu system.

        This method takes in subscriber data, prepares it in the appropriate format,
        and creates the subscriber in Novu. It logs the action and handles any
        NovuApiClientException that occurs during the process.

        Args:
            data (SubscriberRequest): The subscriber data to be created, including details
                                      such as subscriber_id, email, first_name, last_name,
                                      phone, avatar, channels, and other metadata.

        Returns:
            SubscriberDto: The created subscriber object returned by the Novu API.

        Raises:
            NovuApiClientException: If an error occurs while trying to create the subscriber
                                    in Novu, the exception is logged and re-raised.
        """
        # Prepare subscriber data
        subscriber_data = SubscriberDto(
            subscriber_id=data.subscriber_id,
            email=data.email,
            first_name=data.first_name,
            last_name=data.last_name,
            phone=data.phone,
            avatar=data.avatar,
            channels=data.channels,
            data=data.data,
        )

        # Create the subscriber in Novu
        try:
            db_subscriber = await self.create_subscriber(subscriber_data, environment="prod")
            logger.debug(f"Created Novu subscriber: {data.subscriber_id}")
        except NovuApiClientException as err:
            logger.error(err.message)
            raise

        return db_subscriber

    async def bulk_create_novu_subscriber(self, data: List[SubscriberRequest]) -> Dict:
        """Bulk create subscribers in the Novu system.

        This method takes a list of subscriber data, prepares each entry in the
        appropriate format, and creates them in Novu. It logs the results of
        the operation, including counts of created, updated, and failed subscribers.

        Args:
            data (List[SubscriberRequest]): A list of subscriber data to be created,
                                            each containing details such as
                                            subscriber_id, email, first_name,
                                            last_name, phone, avatar, channels,
                                            and other metadata.

        Returns:
            Dict: A dictionary containing the counts of created, updated, and failed
                subscribers. The keys are:
                - "created": A list of IDs for successfully created subscribers.
                - "updated": A list of IDs for subscribers that were updated.
                - "failed": A list of IDs for subscribers that failed to be created.

        Raises:
            NovuApiClientException: If an error occurs while trying to bulk create
                                    the subscribers in Novu, the exception is logged
                                    and re-raised.
        """
        # Prepare subscriber data
        subscriber_data = [
            SubscriberDto(
                subscriber_id=subscriber_data.subscriber_id,
                email=subscriber_data.email,
                first_name=subscriber_data.first_name,
                last_name=subscriber_data.last_name,
                phone=subscriber_data.phone,
                avatar=subscriber_data.avatar,
                channels=subscriber_data.channels,
                data=subscriber_data.data,
            )
            for subscriber_data in data
        ]

        # Create subscribers in Novu
        try:
            db_subscribers = await self.bulk_create_subscribers(subscriber_data, environment="prod")
        except NovuApiClientException as err:
            logger.error(err.message)
            raise

        created = [subscriber.subscriber_id for subscriber in db_subscribers.created]
        updated = [subscriber.subscriber_id for subscriber in db_subscribers.updated]
        failed = [subscriber.subscriber_id for subscriber in db_subscribers.failed]
        logger.debug(f"Created {len(created)} Novu subscribers")
        logger.debug(f"Updated {len(updated)} Novu subscribers")
        logger.debug(f"Failed to create {len(failed)} Novu subscribers")

        return {
            "created": created,
            "updated": updated,
            "failed": failed,
        }

    async def list_novu_subscribers(self, page: int = 0, limit: int = 10) -> List[SubscriberItem]:
        """Retrieve a list of subscribers from the Novu system.

        This method fetches subscribers in a paginated manner, allowing for
        retrieval of a specified number of subscribers per request. It logs the
        total number of subscribers found and handles any errors during the
        fetching process.

        Args:
            page (int, optional): The page number for pagination, starting from 0.
                                Default is 0.
            limit (int, optional): The maximum number of subscribers to retrieve
                                per page. Default is 10.

        Returns:
            List[SubscriberItem]: A list of SubscriberItem instances, each
                                representing a subscriber's details.

        Raises:
            NovuApiClientException: If an error occurs while trying to fetch the
                                    subscribers, the exception is logged and re-raised.
        """
        try:
            db_subscribers = await self.get_all_subscribers(page=page, limit=limit, environment="prod")
            logger.debug(f"Found {len(db_subscribers)} subscribers")
        except NovuApiClientException as err:
            logger.error(err.message)
            raise

        subscribers = [
            SubscriberItem(
                subscriber_id=subscriber.get("subscriberId"),
                email=subscriber.get("email"),
                first_name=subscriber.get("firstName"),
                last_name=subscriber.get("lastName"),
                phone=subscriber.get("phone"),
                avatar=subscriber.get("avatar"),
                locale=subscriber.get("locale"),
                id=subscriber.get("_id"),
                channels=subscriber.get("channels", []),
                created_at=subscriber.get("createdAt"),
                updated_at=subscriber.get("updatedAt"),
                is_online=subscriber.get("isOnline"),
                last_online_at=subscriber.get("lastOnlineAt"),
                data=subscriber.get("data", {}),
            )
            for subscriber in db_subscribers
        ]

        return subscribers

    async def retrieve_novu_subscriber(self, subscriber_id: str) -> SubscriberDto:
        """Retrieve a specific subscriber from the Novu system using their subscriber ID.

        This method attempts to fetch the details of a subscriber identified by
        the provided subscriber ID. If successful, it logs the retrieval and
        returns the subscriber's information encapsulated in a SubscriberSdk object.

        Args:
            subscriber_id (str): The unique identifier of the subscriber to retrieve.

        Returns:
            SubscriberDto: An instance of SubscriberDto containing the subscriber's
                            details.

        Raises:
            NovuApiClientException: If an error occurs during the retrieval process,
                                    the exception is logged and re-raised.
        """
        # Retrieve the subscriber from Novu
        try:
            db_subscriber = await self.retrieve_subscriber(subscriber_id, environment="prod")
            logger.debug("Retrieved subscriber successfully")
            return db_subscriber
        except NovuApiClientException as err:
            logger.error(err.message)
            raise

    async def update_novu_subscriber(self, subscriber_id: str, data: SubscriberUpdateRequest) -> SubscriberDto:
        """Update the details of a specific subscriber in the Novu system.

        This method takes a subscriber ID and a request object containing the new
        subscriber data, updates the subscriber's information in Novu, and returns
        the updated subscriber details.

        Args:
            subscriber_id (str): The unique identifier of the subscriber to update.
            data (SubscriberUpdateRequest): An object containing the updated subscriber
                                            information.

        Returns:
            SubscriberDto: An instance of SubscriberDto containing the updated subscriber's
                            details.

        Raises:
            NovuApiClientException: If an error occurs during the update process,
                                    the exception is logged and re-raised.
        """
        # Prepare subscriber data
        subscriber_data = SubscriberDto(
            subscriber_id=subscriber_id,
            email=data.email,
            first_name=data.first_name,
            last_name=data.last_name,
            phone=data.phone,
            avatar=data.avatar,
            channels=data.channels,
            data=data.data,
        )

        # Update the subscriber in Novu
        try:
            db_subscriber = await self.update_subscriber(subscriber_data, environment="prod")
            logger.debug("Updated subscriber successfully")
            return db_subscriber
        except NovuApiClientException as err:
            logger.error(err.message)
            raise

    async def delete_novu_subscriber(self, subscriber_id: str) -> None:
        """Delete a specific subscriber from the Novu system.

        This method takes a subscriber ID and deletes the corresponding subscriber
        from Novu.

        Args:
            subscriber_id (str): The unique identifier of the subscriber to delete.

        Returns:
            None: This method does not return any value.

        Raises:
            NovuApiClientException: If an error occurs during the deletion process,
                                    the exception is logged and re-raised.
        """
        try:
            await self.delete_subscriber(subscriber_id, environment="prod")
            logger.debug("Deleted subscriber successfully")
        except NovuApiClientException as err:
            logger.error(err.message)
            raise
