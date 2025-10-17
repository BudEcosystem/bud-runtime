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

from dataclasses import asdict
from typing import Dict, List, Optional

from novu.dto.event import EventDto
from novu.dto.subscriber import SubscriberDto
from novu.dto.topic import TopicDto

from notify.commons import logging
from notify.commons.constants import NotificationType
from notify.commons.exceptions import NovuApiClientException
from notify.shared.novu_service import NovuService

from .schemas import (
    NotificationRequest,
    SubscriberBase,
    SubscriberRequest,
    SubscriberUpdateRequest,
    TopicBase,
    TopicRequest,
    TopicSubscriberRequest,
    TopicUpdateRequest,
)
from .ttl_service import TTLTrackingService


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

    async def list_novu_subscribers(self, page: int = 0, limit: int = 10) -> List[SubscriberBase]:
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

        subscribers = [SubscriberBase(**subscriber) for subscriber in db_subscribers["data"]]

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


class TopicService(NovuService):
    """Implements topic services for managing topics."""

    async def create_novu_topic(self, data: TopicRequest) -> TopicDto:
        """Create a new topic in Novu.

        Args:
            data (TopicRequest): The topic request object containing `topic_key` and `topic_name`.

        Returns:
            TopicDto: The created topic details.

        Raises:
            NovuApiClientException: If the topic creation fails.
        """
        try:
            db_topic = await self.create_topic(data.topic_key, data.topic_name, environment="prod")
            logger.debug(f"Created Novu topic: {db_topic._id}")
        except NovuApiClientException as err:
            logger.error(err.message)
            raise

        return db_topic

    async def list_novu_topics(self, page: int = 0, limit: int = 10, key: Optional[str] = None) -> List[TopicBase]:
        """List topics in Novu.

        Args:
            page (int, optional): The page number for pagination. Defaults to 0.
            limit (int, optional): The maximum number of topics to return. Defaults to 10.
            key (Optional[str], optional): A filter key for the topics. Defaults to None.

        Returns:
            List[TopicBase]: A list of topic details.

        Raises:
            NovuApiClientException: If the topic listing fails.
        """
        try:
            db_topics = await self.get_all_topics(page=page, limit=limit, topic_key=key, environment="prod")
            logger.debug(f"Found {len(db_topics.data)} topics")
        except NovuApiClientException as err:
            logger.error(err.message)
            raise

        topics = [TopicBase(**asdict(topic)) for topic in db_topics.data]

        return topics

    async def retrieve_novu_topic(self, topic_key: str) -> TopicDto:
        """Retrieve a topic from Novu by its key.

        Args:
            topic_key (str): The key of the topic to retrieve.

        Returns:
            TopicDto: The retrieved topic details.

        Raises:
            NovuApiClientException: If the topic retrieval fails.
        """
        try:
            db_topic = await self.retrieve_topic(topic_key, environment="prod")
            logger.debug("Retrieved topic successfully")
            return db_topic
        except NovuApiClientException as err:
            logger.error(err.message)
            raise

    async def update_novu_topic(self, topic_key: str, data: TopicUpdateRequest) -> TopicDto:
        """Update an existing topic in Novu.

        Args:
            topic_key (str): The key of the topic to update.
            data (TopicUpdateRequest): The updated topic details.

        Returns:
            TopicDto: The updated topic details.

        Raises:
            NovuApiClientException: If the topic update fails.
        """
        try:
            db_topic = await self.update_topic(topic_key, data.topic_name, environment="prod")
            logger.debug("Updated topic successfully")
            return db_topic
        except NovuApiClientException as err:
            logger.error(err.message)
            raise

    async def delete_novu_topic(self, topic_key: str) -> None:
        """Delete a topic from Novu by its key.

        Args:
            topic_key (str): The key of the topic to delete.

        Returns:
            None

        Raises:
            NovuApiClientException: If the topic deletion fails.
        """
        try:
            await self.delete_topic(topic_key, environment="prod")
            logger.debug("Deleted topic successfully")
        except NovuApiClientException as err:
            logger.error(err.message)
            raise

    async def add_subscribers_to_novu_topic(self, topic_key: str, data: TopicSubscriberRequest) -> Dict[str, List]:
        """Add subscribers to a Novu topic.

        Args:
            topic_key (str): The key of the topic to which subscribers will be added.
            data (TopicSubscriberRequest): The subscribers to add to the topic.

        Returns:
            Dict[str, List]: A dictionary with lists of successful and failed subscriber IDs.

        Raises:
            NovuApiClientException: If adding subscribers to the topic fails.
        """
        try:
            response = await self.add_subscribers_to_topic(topic_key, data.subscribers, environment="prod")
            logger.debug("Added subscribers to topic successfully")
            success_subscribers = response[0]
            failed_subscribers = [sub_id for failure_reason in response[1].values() for sub_id in failure_reason]
            return {
                "success": success_subscribers,
                "failed": failed_subscribers,
            }
        except NovuApiClientException as err:
            logger.error(err.message)
            raise

    async def remove_subscribers_from_novu_topic(self, topic_key: str, data: TopicSubscriberRequest) -> None:
        """Remove subscribers from a Novu topic.

        Args:
            topic_key (str): The key of the topic from which subscribers will be removed.
            data (TopicSubscriberRequest): The subscribers to remove from the topic.

        Returns:
            None

        Raises:
            NovuApiClientException: If an error occurs while removing subscribers from the topic.
        """
        try:
            await self.remove_subscribers_from_topic(topic_key, data.subscribers, environment="prod")
            logger.debug("Removed subscribers from topic successfully")
            return
        except NovuApiClientException as err:
            logger.error(err.message)
            raise

    async def check_subscriber_exists_in_novu_topic(self, topic_key: str, subscriber_id: str) -> bool:
        """Check if a subscriber exists in a Novu topic.

        Args:
            topic_key (str): The key of the topic to check.
            subscriber_id (str): The ID of the subscriber to check.

        Returns:
            bool: True if the subscriber exists in the topic, False otherwise.

        Raises:
            NovuApiClientException: If an error occurs while checking the subscriber's existence in the topic.
        """
        try:
            is_subscribed = await self.check_subscribers_in_topic(topic_key, subscriber_id, environment="prod")
            logger.debug(f"Result of checking subscriber {subscriber_id} in topic {topic_key}: {is_subscribed}")
            return is_subscribed
        except NovuApiClientException as err:
            logger.error(err.message)
            raise


class NotificationService(NovuService):
    """Implements notification services for sending notifications."""

    def __init__(self) -> None:
        """Initialize the notification service."""
        super().__init__()
        self.ttl_service = TTLTrackingService()

    async def trigger_novu_notification_event(self, notification_data: NotificationRequest) -> EventDto:
        """Triggers a notification event in Novu based on the provided notification data.

        This method sends a notification event to Novu using the specified notification name,
        recipients, and payload. If TTL is specified in the payload, it tracks the notification
        for automatic cleanup.

        Args:
            notification_data (NotificationRequest): The request object containing the notification
                name, recipients, and payload data.

        Returns:
            EventDto: An object containing details about the triggered event, including its status.

        Raises:
            NovuApiClientException: If there is an issue with triggering the event via Novu.
        """
        try:
            if notification_data.notification_type == NotificationType.EVENT:
                event_data = await self.trigger_event(
                    notification_data.name,
                    notification_data.subscriber_ids,
                    notification_data.payload,
                    notification_data.actor,
                    environment="prod",
                )
            elif notification_data.notification_type == NotificationType.TOPIC:
                event_data = await self.trigger_topic_event(
                    notification_data.name,
                    notification_data.topic_keys,
                    notification_data.payload,
                    notification_data.actor,
                    environment="prod",
                )
            elif notification_data.notification_type == NotificationType.BROADCAST:
                event_data = await self.trigger_broadcast(
                    notification_data.name,
                    notification_data.payload,
                    notification_data.actor,
                    environment="prod",
                )
            else:
                raise NovuApiClientException(
                    message=f"Notification type {notification_data.notification_type.value} is not supported."
                )
            logger.debug(f"Triggered notification successfully. Status: {event_data.status}")

            # Track TTL if specified in payload
            ttl_seconds = notification_data.payload.get("ttl_seconds")
            if ttl_seconds or notification_data.payload:
                # Extract metadata for tracking
                metadata = {
                    "notification_type": notification_data.notification_type.value,
                    "notification_name": notification_data.name,
                    "category": notification_data.payload.get("category"),
                    "source": notification_data.payload.get("source"),
                }
                await self.ttl_service.track_notification_ttl(
                    transaction_id=event_data.transaction_id, ttl_seconds=ttl_seconds, metadata=metadata
                )

            return event_data
        except NovuApiClientException as err:
            logger.error(err.message)
            raise
