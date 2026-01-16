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

"""Provides shared functions for managing notification service."""

import asyncio
from typing import Any, Callable, Dict, List, Optional, Union

import aiohttp
from aiohttp import client_exceptions

from ..commons import logging
from ..commons.config import app_settings
from ..commons.constants import BUD_NOTIFICATION_WORKFLOW, NotificationCategory, NotificationStatus
from ..commons.exceptions import BudNotifyException
from ..core.schemas import (
    NotificationContent,
    NotificationPayload,
    NotificationRequest,
    NotificationTrigger,
    SubscriberCreate,
    SubscriberUpdate,
)


logger = logging.get_logger(__name__)


class NotificationBuilder:
    """Builder class for notification."""

    def __init__(self):
        """Initialize the builder."""
        self.content = None
        self.payload = None
        self.notification_request = None

    def set_content(
        self,
        *,
        title: Optional[str] = None,
        message: Optional[str] = None,
        icon: Optional[str] = None,
        tag: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
        status: NotificationStatus = NotificationStatus.COMPLETED,
        content: dict = None,
    ) -> "NotificationBuilder":
        """Set the content for the notification."""
        if content:
            self.content = content
        else:
            self.content = NotificationContent(
                title=title, message=message, icon=icon, tag=tag, status=status, result=result
            )
        return self

    def set_payload(
        self,
        *,
        category: NotificationCategory = NotificationCategory.INAPP,
        type: str = None,
        source: str = app_settings.source_topic,
        workflow_id: str = None,
    ) -> "NotificationBuilder":
        """Set the payload for the notification."""
        self.payload = NotificationPayload(
            category=category, type=type, source=source, content=self.content, workflow_id=workflow_id
        )
        return self

    def set_notification_request(
        self, *, subscriber_ids: Union[str, List[str]], name: str = BUD_NOTIFICATION_WORKFLOW
    ) -> "NotificationBuilder":
        """Build the notification request."""
        self.notification_request = NotificationRequest.model_construct(
            name=name, subscriber_ids=subscriber_ids, payload=self.payload
        )
        return self

    def build(self) -> NotificationRequest:
        """Build the notification request."""
        notification = self.notification_request
        self.reset()
        return notification

    def reset(self) -> "NotificationBuilder":
        """Reset the builder."""
        self.content = None
        self.payload = None
        self.notification_request = None
        return self


class BudNotifyService:
    """Service for sending notifications."""

    def __init__(self):
        """Initialize the notification service."""
        self.notification_endpoint = (
            f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_notify_app_id}/method/notifications"
        )

    async def send_notification(self, notification: NotificationRequest) -> dict:
        """Send a notification.

        Args:
            notification (NotificationRequest): The notification to send

        Returns:
            dict: The response from the notification service
        """
        payload = notification.model_dump(exclude_none=True, mode="json")
        logger.debug(f"Sending notification with payload {payload}")

        try:
            async with (
                aiohttp.ClientSession() as session,
                session.post(self.notification_endpoint, json=payload) as response,
            ):
                response_data = await response.json()
                if response.status != 200:
                    logger.error(f"Failed to send notification: {response.status} {response_data}")
                    return response_data

                # Check if the response contains an error from budnotify
                if isinstance(response_data, dict) and response_data.get("object") == "error":
                    logger.error(f"Budnotify returned error: {response_data}")
                else:
                    logger.debug("Successfully sent notification")

                return response_data
        except Exception as e:
            logger.exception(f"Failed to send notification: {e}")


class BudNotifyHandler:
    """BudNotifyHandler sends notifications to the BudNotify server."""

    def __init__(self):
        self.base_url = f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_notify_app_id}/method/"

    @staticmethod
    def _handle_exception(func: Callable[..., Any]) -> Callable[..., Any]:
        """Handle exceptions for both synchronous and asynchronous functions.

        This decorator wraps a function to handle exceptions, converting them into a
        custom `NovuApiClientException` with a specific message. It distinguishes between
        asynchronous and synchronous functions, applying appropriate handling for each.

        Args:
        func (Callable[..., Any]): The function to be wrapped by the decorator.

        Returns:
        Callable[..., Any]: The wrapped function with added exception handling.

        Raises:
        NovuApiClientException: If a `ClientConnectionError` or any other exception occurs.
        """
        if asyncio.iscoroutinefunction(func):

            async def async_wrapper(self, *args: Any, **kwargs: Any) -> Any:
                try:
                    return await func(self, *args, **kwargs)
                except client_exceptions.ClientConnectionError:
                    raise BudNotifyException("Failed to connect to server") from None
                except BudNotifyException as err:
                    raise err
                except Exception as err:
                    logger.exception(err)
                    raise BudNotifyException("Unexpected error occurred") from None

            return async_wrapper
        else:

            def sync_wrapper(self, *args: Any, **kwargs: Any) -> Any:
                try:
                    return func(self, *args, **kwargs)
                except client_exceptions.ClientConnectionError:
                    raise BudNotifyException("Failed to connect to server") from None
                except BudNotifyException as err:
                    raise err
                except Exception as err:
                    logger.exception(err)
                    raise BudNotifyException("Unexpected error occurred") from None

            return sync_wrapper

    @_handle_exception
    async def trigger_notification(self, data: NotificationTrigger) -> Dict:
        """Trigger notification in BudNotify."""
        payload = data.model_dump_json(exclude_none=True)
        url = f"{self.base_url}notification"

        headers = {"accept": "application/json", "Content-Type": "application/json"}

        async with aiohttp.ClientSession() as session, session.post(url, data=payload, headers=headers) as response:
            if response.status != 200:
                logger.error("Failed to trigger notification")
                raise BudNotifyException(f"Failed to trigger notification: {response.status} {response.reason}")
            else:
                response_data = await response.json()
                if "code" in response_data and response_data["code"] != 200:
                    raise BudNotifyException(f"Failed to trigger notification: {response.status} {response.reason}")
                logger.info(f"Triggered notification: {response.status} {response.reason}")
                return response_data

    @_handle_exception
    async def create_subscriber(self, data: SubscriberCreate) -> Dict:
        """Create subscriber in BudNotify."""
        payload = data.model_dump(exclude_none=True)
        url = f"{self.base_url}subscribers"

        async with aiohttp.ClientSession() as session, session.post(url, json=payload) as response:
            if response.status != 201:
                logger.error(f"Failed to create subscriber: {response.status} {response.reason}")
                raise BudNotifyException("Failed to create subscriber")
            else:
                response_data = await response.json()
                if "code" in response_data and response_data["code"] != 200:
                    raise BudNotifyException("Failed to create subscriber")

                logger.info("Created subscriber in BudNotify")
                return response_data

    @_handle_exception
    async def get_all_subscribers(self, page: int = 0, limit: int = 10) -> Dict:
        """Get all subscribers in BudNotify."""
        url = f"{self.base_url}subscribers?page={page}&limit={limit}"

        async with aiohttp.ClientSession() as session, session.get(url) as response:
            if response.status != 200:
                logger.error(f"Failed to get subscribers: {response.status} {response.reason}")
                raise BudNotifyException("Failed to get subscribers")
            else:
                response_data = await response.json()
                if "code" in response_data and response_data["code"] != 200:
                    raise BudNotifyException("Failed to get subscribers")

                logger.info("Get subscribers from BudNotify")
                return response_data

    @_handle_exception
    async def retrieve_subscriber(self, subscriber_id: str) -> Dict:
        """Retrieve subscriber from BudNotify by id."""
        url = f"{self.base_url}subscribers/{subscriber_id}"

        async with aiohttp.ClientSession() as session, session.get(url) as response:
            if response.status != 200:
                logger.error(f"Failed to get subscriber: {response.status} {response.reason}")
                raise BudNotifyException("Failed to retrieve subscriber")
            else:
                response_data = await response.json()
                if "code" in response_data and response_data["code"] != 200:
                    raise BudNotifyException("Failed to retrieve subscriber")

                logger.info("Successfully retrieve subscriber from BudNotify")
                return response_data

    @_handle_exception
    async def update_subscriber(self, subscriber_id: str, data: SubscriberUpdate) -> Dict:
        """Update subscriber in BudNotify by using subscriber id."""
        url = f"{self.base_url}subscribers/{subscriber_id}"
        payload = data.model_dump(exclude_none=True)

        async with aiohttp.ClientSession() as session, session.put(url, json=payload) as response:
            if response.status != 200:
                logger.error(f"Failed to update subscriber: {response.status} {response.reason}")
                raise BudNotifyException("Failed to update subscriber.")
            else:
                response_data = await response.json()
                if "code" in response_data and response_data["code"] != 200:
                    raise BudNotifyException("Failed to update subscriber.")

                logger.info("Successfully update subscriber in BudNotify")
                return response_data

    @_handle_exception
    async def delete_subscriber(self, subscriber_id: str) -> None:
        """Delete subscriber in BudNotify by using subscriber id."""
        url = f"{self.base_url}subscribers/{subscriber_id}"

        async with aiohttp.ClientSession() as session, session.delete(url) as response:
            if response.status != 200:
                logger.error(f"Failed to delete subscriber: {response.status} {response.reason}")
                raise BudNotifyException("Failed to delete subscriber")
            else:
                response_data = await response.json()
                if "code" in response_data and response_data["code"] != 200:
                    raise BudNotifyException("Failed to delete subscriber")

                logger.info("Successfully delete subscriber from BudNotify")
                return response_data

    @_handle_exception
    async def bulk_create_subscribers(self, subscribers: List[SubscriberCreate]) -> Dict:
        """Bulk create subscribers in BudNotify."""
        url = f"{self.base_url}subscribers/bulk-create"
        payload = [data.model_dump(exclude_none=True) for data in subscribers]

        async with aiohttp.ClientSession() as session, session.post(url, json=payload) as response:
            if response.status != 200:
                logger.error(f"Failed to bulk create subscriber: {response.status} {response.reason}")
                raise BudNotifyException("Failed to bulk create subscribers")
            else:
                response_data = await response.json()
                if "code" in response_data and response_data["code"] != 200:
                    raise BudNotifyException("Failed to bulk create subscribers")

                logger.info("Successfully create multiple subscribers")
                return response_data


async def publish_workflow_completion_event(
    callback_topic: str,
    workflow_id: str,
    workflow_type: str,
    status: str,
    result_data: Dict[str, Any],
    reason: Optional[str] = None,
) -> None:
    """Publish workflow completion event to the specified callback topic.

    This function is used for budpipeline integration. It publishes a completion
    event when a workflow (model add, benchmark, etc.) completes, allowing
    budpipeline to receive real-time notifications.

    Only called when callback_topic was provided in the original request.

    Args:
        callback_topic: The Dapr pub/sub topic to publish to (e.g., "budpipelineEvents")
        workflow_id: The budapp workflow ID that completed
        workflow_type: Type of workflow (e.g., "model_add", "benchmark")
        status: Completion status ("COMPLETED" or "FAILED")
        result_data: Result data including IDs (e.g., {"model_id": "...", "model_name": "..."})
        reason: Optional failure reason if status is FAILED
    """
    from .dapr_service import DaprService

    try:
        dapr_service = DaprService()
        await dapr_service.publish_to_topic(
            data={
                "category": "INTERNAL",
                "type": "workflow_completed",
                "workflow_id": workflow_id,
                "workflow_type": workflow_type,
                "status": status,
                "result": result_data,
                "reason": reason,
            },
            target_topic_name=callback_topic,
            event_type="workflow_completed",
        )
        logger.info(
            f"Published workflow completion event: workflow_id={workflow_id}, "
            f"type={workflow_type}, status={status}, topic={callback_topic}"
        )
    except Exception as e:
        logger.exception(f"Failed to publish workflow completion event: {e}")
