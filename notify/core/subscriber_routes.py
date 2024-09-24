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

"""Defines metadata routes for the microservices, providing endpoints for retrieving subscriber information."""

from typing import List

from fastapi import APIRouter, Response, status
from fastapi.exceptions import HTTPException

from notify.commons import logging
from notify.commons.exceptions import NovuApiClientException
from notify.commons.schemas import SuccessResponse

from .schemas import (
    SubscriberBulkResponse,
    SubscriberListResponse,
    SubscriberRequest,
    SubscriberResponse,
    SubscriberUpdateRequest,
)
from .services import SubscriberService


logger = logging.get_logger(__name__)

subscriber_router = APIRouter()


@subscriber_router.post(
    "/subscribers",
    response_model=SubscriberResponse,
    status_code=status.HTTP_201_CREATED,
    description="Create a new subscriber. Can be used for both API and PubSub. Refer to SubscriberRequest schema for details.",
    tags=["Subscribers"],
)
async def create_subscriber(subscriber: SubscriberRequest) -> Response:
    """Create a new subscriber in the Novu system.

    This endpoint processes a request to create a new subscriber based on
    the provided subscriber data. It returns a response indicating the
    result of the creation operation.

    Args:
        subscriber (SubscriberRequest): The subscriber data to create,
                                         including details like email,
                                         first name, last name, etc.

    Returns:
        Response: An HTTP response indicating the status of the operation,
                  along with the created subscriber's details.

    Raises:
        HTTPException: Raises an HTTP 400 error if subscriber creation fails
                       due to client-related issues, or raises an HTTP 500 error
                       for unexpected server errors.
    """
    logger.debug("Received request to create a new subscriber")

    try:
        db_subscriber = await SubscriberService().create_novu_subscriber(subscriber)
        logger.info("Subscriber created successfully")
        return SubscriberResponse(
            object="info",
            message="Subscriber created successfully.",
            code=status.HTTP_201_CREATED,
            subscriber_id=db_subscriber.subscriber_id,
            email=db_subscriber.email,
            first_name=db_subscriber.first_name,
            last_name=db_subscriber.last_name,
            phone=db_subscriber.phone,
            avatar=db_subscriber.avatar,
            locale=db_subscriber.locale,
            id=db_subscriber._id,
            channels=db_subscriber.channels,
            created_at=db_subscriber.created_at,
            updated_at=db_subscriber.updated_at,
            is_online=db_subscriber.is_online,
            last_online_at=db_subscriber.last_online_at,
            data=db_subscriber.data,
        ).to_http_response()
    except NovuApiClientException:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to create subscriber") from None
    except Exception as err:
        logger.exception(f"Unexpected error occurred while creating subscriber. {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error occurred while creating subscriber.",
        ) from None


@subscriber_router.post(
    "/subscribers/bulk",
    response_model=SubscriberResponse,
    status_code=status.HTTP_201_CREATED,
    description="Create bulk subscribers. Can be used for both API and PubSub. Refer to SubscriberRequest schema for details.",
    tags=["Subscribers"],
)
async def create_bulk_subscribers(subscribers: List[SubscriberRequest]) -> Response:
    """Create multiple subscribers in bulk within the Novu system.

    This endpoint processes a request to create multiple subscribers based on
    the provided list of subscriber data. It returns a response indicating the
    results of the bulk creation operation.

    Args:
        subscribers (List[SubscriberRequest]): A list of subscriber data
                                                objects to create.

    Returns:
        Response: An HTTP response indicating the status of the bulk
                  creation operation, along with details of created,
                  updated, and failed subscribers.

    Raises:
        HTTPException: Raises an HTTP 400 error if bulk creation fails due
                       to client-related issues, or raises an HTTP 500 error
                       for unexpected server errors.
    """
    logger.debug("Received request to create a new subscriber")

    try:
        db_subscriber = await SubscriberService().bulk_create_novu_subscriber(subscribers)
        logger.info("Subscriber bulk created successfully")
        return SubscriberBulkResponse(
            object="info",
            message="Subscriber bulk created successfully.",
            code=status.HTTP_201_CREATED,
            created=db_subscriber.get("created", []),
            updated=db_subscriber.get("updated", []),
            failed=db_subscriber.get("failed", []),
        ).to_http_response()
    except NovuApiClientException:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to create subscribers") from None
    except Exception as err:
        logger.exception(f"Unexpected error occurred while creating subscribers. {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error occurred while creating subscribers.",
        ) from None


@subscriber_router.get(
    "/subscribers",
    response_model=SubscriberListResponse,
    status_code=status.HTTP_200_OK,
    description="List all subscribers. Can be used for both API and PubSub. Refer to SubscriberRequest schema for details.",
    tags=["Subscribers"],
)
async def get_all_subscribers(page: int = 0, limit: int = 10) -> Response:
    """Retrieve a list of all subscribers from the Novu system.

    This endpoint lists subscribers with pagination support. It returns
    a response containing the details of the subscribers retrieved.

    Args:
        page (int, optional): The page number for pagination. Defaults to 0.
        limit (int, optional): The number of subscribers to return per page.
                               Defaults to 10.

    Returns:
        Response: An HTTP response containing the list of subscribers along
                  with relevant metadata.

    Raises:
        HTTPException: Raises an HTTP 400 error if the listing fails due to
                       client-related issues, or raises an HTTP 500 error for
                       unexpected server errors.
    """
    logger.debug("Received request to list all subscribers")

    try:
        db_subscribers = await SubscriberService().list_novu_subscribers(page=page, limit=limit)
        logger.info("Successfully retrieved the list of subscribers")
        return SubscriberListResponse(
            object="info",
            message="Successfully retrieved the subscribers list",
            subscribers=db_subscribers,
            code=status.HTTP_200_OK,
        ).to_http_response()
    except NovuApiClientException:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to list subscribers") from None
    except Exception as err:
        logger.exception(f"Unexpected error while listing subscribers. {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error while listing subscribers.",
        ) from None


@subscriber_router.get(
    "/subscribers/{subscriber_id}",
    response_model=SubscriberResponse,
    status_code=status.HTTP_200_OK,
    description="Retrieves the specified subscriber. Can be used for both API and PubSub. Refer to SubscriberRequest schema for details.",
    tags=["Subscribers"],
)
async def retrieve_subscriber(
    subscriber_id: str,
) -> Response:
    """Retrieve a specific subscriber by their unique identifier from the Novu system.

    This endpoint allows for fetching detailed information about a subscriber
    based on their subscriber ID.

    Args:
        subscriber_id (str): The unique identifier of the subscriber to retrieve.

    Returns:
        Response: An HTTP response containing the details of the requested
                  subscriber.

    Raises:
        HTTPException: Raises an HTTP 400 error if the retrieval fails due to
                       client-related issues, or raises an HTTP 500 error for
                       unexpected server errors.
    """
    logger.debug("Received request to retrieve subscriber")

    try:
        db_subscriber = await SubscriberService().retrieve_novu_subscriber(subscriber_id)
        logger.info("Successfully retrieved the subscriber")
        return SubscriberResponse(
            object="info",
            message="Successfully retrieved the subscriber",
            code=status.HTTP_201_CREATED,
            subscriber_id=db_subscriber.subscriber_id,
            email=db_subscriber.email,
            first_name=db_subscriber.first_name,
            last_name=db_subscriber.last_name,
            phone=db_subscriber.phone,
            avatar=db_subscriber.avatar,
            locale=db_subscriber.locale,
            id=db_subscriber._id,
            channels=db_subscriber.channels,
            created_at=db_subscriber.created_at,
            updated_at=db_subscriber.updated_at,
            is_online=db_subscriber.is_online,
            last_online_at=db_subscriber.last_online_at,
            data=db_subscriber.data,
        ).to_http_response()
    except NovuApiClientException:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to retrieve subscriber") from None
    except Exception as err:
        logger.exception(f"Unexpected error while retrieving subscriber. {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error while retrieving subscriber.",
        ) from None


@subscriber_router.put(
    "/subscribers/{subscriber_id}",
    response_model=SubscriberResponse,
    status_code=status.HTTP_200_OK,
    description="Updates the specified subscriber. Can be used for both API and PubSub. Refer to SubscriberRequest schema for details.",
    tags=["Subscribers"],
)
async def update_subscriber(subscriber_id: str, subscriber: SubscriberUpdateRequest) -> Response:
    """Update the details of a specific subscriber in the Novu system.

    This endpoint allows for modifying the information of an existing subscriber
    based on their unique subscriber ID.

    Args:
        subscriber_id (str): The unique identifier of the subscriber to update.
        subscriber (SubscriberUpdateRequest): The updated information for the subscriber.

    Returns:
        Response: An HTTP response containing the updated details of the subscriber.

    Raises:
        HTTPException: Raises an HTTP 400 error if the update fails due to
                       client-related issues, or raises an HTTP 500 error for
                       unexpected server errors.
    """
    logger.debug("Received request to update subscriber")

    try:
        db_subscriber = await SubscriberService().update_novu_subscriber(subscriber_id, subscriber)
        logger.info("Subscriber updated successfully.")
        return SubscriberResponse(
            object="info",
            message="Subscriber updated successfully.",
            code=status.HTTP_201_CREATED,
            subscriber_id=db_subscriber.subscriber_id,
            email=db_subscriber.email,
            first_name=db_subscriber.first_name,
            last_name=db_subscriber.last_name,
            phone=db_subscriber.phone,
            avatar=db_subscriber.avatar,
            locale=db_subscriber.locale,
            id=db_subscriber._id,
            channels=db_subscriber.channels,
            created_at=db_subscriber.created_at,
            updated_at=db_subscriber.updated_at,
            is_online=db_subscriber.is_online,
            last_online_at=db_subscriber.last_online_at,
            data=db_subscriber.data,
        ).to_http_response()
    except NovuApiClientException:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to update the subscriber."
        ) from None
    except Exception as err:
        logger.exception(f"Unexpected error occurred while updating subscriber. {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while trying to update the subscriber.",
        ) from None


@subscriber_router.delete(
    "/subscribers/{subscriber_id}",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    description="Deletes the specified subscriber. Can be used for both API and PubSub. Refer to SubscriberRequest schema for details.",
    tags=["Subscribers"],
)
async def delete_subscriber(subscriber_id: str) -> Response:
    """Delete a specific subscriber from the Novu system.

    This endpoint removes a subscriber identified by their unique subscriber ID
    from the system.

    Args:
        subscriber_id (str): The unique identifier of the subscriber to delete.

    Returns:
        Response: An HTTP response indicating successful deletion of the subscriber.

    Raises:
        HTTPException: Raises an HTTP 400 error if the deletion fails due to
                       client-related issues, or raises an HTTP 500 error for
                       unexpected server errors.
    """
    logger.debug("Received request to delete subscriber.")

    try:
        await SubscriberService().delete_novu_subscriber(subscriber_id)
        logger.info("Subscriber deleted successfully.")
        return SuccessResponse(
            object="info",
            message="Subscriber deleted successfully",
            code=status.HTTP_204_NO_CONTENT,
        ).to_http_response()
    except NovuApiClientException:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to delete the subscriber."
        ) from None
    except Exception as err:
        logger.exception(f"Unexpected error occurred while deleting subscriber. {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while trying to delete the subscriber.",
        ) from None
