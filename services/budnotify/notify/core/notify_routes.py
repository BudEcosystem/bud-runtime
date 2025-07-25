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

from notify.commons import logging
from notify.commons.api_utils import pubsub_api_endpoint

from .schemas import NotificationRequest, NotificationResponse


logger = logging.get_logger(__name__)

notify_router = APIRouter()


@notify_router.post(
    "/notifications",
    response_model=NotificationResponse,
    status_code=status.HTTP_201_CREATED,
    description="Create a notification. Can be used for both API and PubSub. Refer to NotificationRequest schema for details.",
    tags=["Notifications"],
)
@pubsub_api_endpoint(NotificationRequest)
async def create_notification(notification: NotificationRequest) -> Response:
    """Create a new notification based on the provided request.

    This function processes the incoming notification request, creates a new notification,
    and returns a response with the created notification's details.

    Args:
        notification (NotificationRequest): The notification request object containing
                                            the details of the notification to be created.

    Returns:
        Response: A `NotificationResponse` with the created notification's ID and a success message,
        with HTTP status code 201 (Created).

    Raises:
        HTTPException: If there's an error during the notification creation process.

    Example:
        >>> notification_request = NotificationRequest(...)
        >>> response = await create_notification(notification_request)
        >>> response.status_code
        201
        >>> response.json()
        {
            "object": "info",
            "message": "Notification created",
            "notification_id": "1234567890"
        }
    """
    # TODO: Implement bulk subscription support
    logger.debug("Creating notification: %s", notification)

    return NotificationResponse(
        object="info", message="Notification created", notification_id="", code=status.HTTP_200_OK
    ).to_http_response()
