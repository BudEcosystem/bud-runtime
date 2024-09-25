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

"""Defines metadata routes for the microservices, providing endpoints for retrieving service-level information."""

from fastapi import APIRouter, Response, status
from fastapi.exceptions import HTTPException

from notify.commons import logging
from notify.commons.api_utils import pubsub_api_endpoint
from notify.commons.exceptions import NovuApiClientException

from .schemas import NotificationRequest, NotificationResponse
from .services import NotificationService


logger = logging.get_logger(__name__)

notify_router = APIRouter()


@notify_router.post(
    "/notification",
    response_model=NotificationResponse,
    status_code=status.HTTP_201_CREATED,
    description="Triggers a notification. Can be used for both API and PubSub. Refer to NotificationRequest schema for details.",
    tags=["Notifications"],
)
@pubsub_api_endpoint(NotificationRequest)
async def trigger_notification(notification: NotificationRequest) -> Response:
    """Triggers a notification using the provided notification data.

    This method processes a request to trigger a notification and interacts with the
    NotificationService to send the event through Novu. The response includes the status,
    transaction ID, and acknowledgment of the triggered notification.

    Args:
        notification (NotificationRequest): The request object containing notification details
            such as name, recipients, and payload.

    Returns:
        Response: A response object containing the status of the notification triggering
        process and related information.

    Raises:
        HTTPException: Raised with a 400 status code if the notification fails to trigger.
        HTTPException: Raised with a 500 status code for unexpected errors during processing.
    """
    logger.debug("Received request to trigger a notification")
    try:
        event_data = await NotificationService().trigger_novu_notification_event(notification)
        logger.info(f"Triggered notification successfully. Status: {event_data.status}")
        return NotificationResponse(
            object="notification",
            message="",
            acknowledged=event_data.acknowledged,
            status=event_data.status,
            transaction_id=event_data.transaction_id,
            code=status.HTTP_200_OK,
        ).to_http_response()
    except NovuApiClientException:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to trigger notification") from None
    except Exception as err:
        logger.exception(f"Unexpected error occurred while triggering notification. {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error occurred while triggering notification.",
        ) from None
