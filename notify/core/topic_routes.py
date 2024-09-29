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

"""Defines metadata routes for the microservices, providing endpoints for retrieving topic information."""

from dataclasses import asdict
from typing import Optional

from fastapi import APIRouter, Response, status
from fastapi.exceptions import HTTPException

from notify.commons import logging
from notify.commons.exceptions import NovuApiClientException
from notify.commons.schemas import SuccessResponse

from .schemas import (
    PaginatedTopicResponse,
    TopicAddSubscriberResponse,
    TopicCheckSubscriberResponse,
    TopicRequest,
    TopicResponse,
    TopicSubscriberRequest,
    TopicUpdateRequest,
)
from .services import TopicService


logger = logging.get_logger(__name__)

topic_router = APIRouter(prefix="/topics", tags=["Topics"])


@topic_router.post(
    "",
    response_model=TopicResponse,
    status_code=status.HTTP_201_CREATED,
    description="Create a new topic. Can be used for both API and PubSub. Refer to TopicRequest schema for details.",
)
async def create_topic(topic: TopicRequest) -> Response:
    """Create a new topic.

    Args:
        topic (TopicRequest): The topic details to create.

    Returns:
        Response: The HTTP response containing the created topic details.

    Raises:
        HTTPException: If the topic creation fails due to a Novu API client error (400 Bad Request).
        HTTPException: If an unexpected error occurs during the topic creation process (500 Internal Server Error).
    """
    logger.debug("Received request to create a new topic")

    try:
        db_topic = await TopicService().create_novu_topic(topic)
        logger.info("Topic created successfully")
        return TopicResponse(
            object="topic",
            message="",
            code=status.HTTP_201_CREATED,
            **asdict(db_topic),
        ).to_http_response()
    except NovuApiClientException:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to create topic") from None
    except Exception as err:
        logger.exception(f"Unexpected error occurred while creating topic. {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error occurred while creating topic.",
        ) from None


@topic_router.get(
    "",
    response_model=PaginatedTopicResponse,
    status_code=status.HTTP_200_OK,
    description="List all topics. Can be used for both API and PubSub. Refer to TopicRequest schema for details.",
)
async def get_all_topics(page: int = 0, limit: int = 10, key: Optional[str] = None) -> Response:
    """Retrieve a list of all topics with pagination.

    Args:
        page (int, optional): The page number to retrieve. Defaults to 0.
        limit (int, optional): The maximum number of topics to return per page. Defaults to 10.
        key (Optional[str], optional): An optional key to filter topics. Defaults to None.

    Returns:
        Response: The HTTP response containing the list of topics and pagination details.

    Raises:
        HTTPException: If the topic listing fails due to a Novu API client error (400 Bad Request).
        HTTPException: If an unexpected error occurs during the topic listing process (500 Internal Server Error).
    """
    logger.debug("Received request to list all topics")

    try:
        db_topics = await TopicService().list_novu_topics(page=page, limit=limit, key=key)
        logger.info("Successfully retrieved the list of topics")
        return PaginatedTopicResponse(
            object="topic.list",
            message="",
            topics=db_topics,
            code=status.HTTP_200_OK,
            page=page,
            limit=limit,
        ).to_http_response()
    except NovuApiClientException:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to list topics") from None
    except Exception as err:
        logger.exception(f"Unexpected error while listing topics. {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error while listing topics.",
        ) from None


@topic_router.get(
    "/{key}",
    response_model=TopicResponse,
    status_code=status.HTTP_200_OK,
    description="Retrieves the specified topic. Can be used for both API and PubSub. Refer to TopicRequest schema for details.",
)
async def retrieve_topic(
    key: str,
) -> Response:
    """Retrieve a specific topic by its key.

    Args:
        key (str): The unique identifier of the topic to retrieve.

    Returns:
        Response: The HTTP response containing the details of the retrieved topic.

    Raises:
        HTTPException: If the topic retrieval fails due to a Novu API client error (400 Bad Request).
        HTTPException: If an unexpected error occurs during the topic retrieval process (500 Internal Server Error).
    """
    logger.debug("Received request to retrieve topic")

    try:
        db_topic = await TopicService().retrieve_novu_topic(key)
        logger.info("Successfully retrieved the topic")
        return TopicResponse(
            object="topic",
            message="",
            code=status.HTTP_200_OK,
            **asdict(db_topic),
        ).to_http_response()
    except NovuApiClientException:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to retrieve topic") from None
    except Exception as err:
        logger.exception(f"Unexpected error while retrieving topic. {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error while retrieving topic.",
        ) from None


@topic_router.put(
    "/{key}",
    response_model=TopicResponse,
    status_code=status.HTTP_200_OK,
    description="Updates the specified topic. Can be used for both API and PubSub. Refer to TopicRequest schema for details.",
    tags=["Topics"],
)
async def update_topic(key: str, topic: TopicUpdateRequest) -> Response:
    """Update a specific topic identified by its key.

    Args:
        key (str): The unique identifier of the topic to update.
        topic (TopicUpdateRequest): The updated topic data.

    Returns:
        Response: The HTTP response containing the details of the updated topic.

    Raises:
        HTTPException: If the topic update fails due to a Novu API client error (400 Bad Request).
        HTTPException: If an unexpected error occurs during the topic update process (500 Internal Server Error).
    """
    logger.debug("Received request to update topic")

    try:
        db_topic = await TopicService().update_novu_topic(key, topic)
        logger.info("Topic updated successfully.")
        return TopicResponse(
            object="topic",
            message="",
            code=status.HTTP_200_OK,
            **asdict(db_topic),
        ).to_http_response()
    except NovuApiClientException:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to update the topic.") from None
    except Exception as err:
        logger.exception(f"Unexpected error occurred while updating topic. {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while trying to update the topic.",
        ) from None


@topic_router.delete(
    "/{key}",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    description="Deletes the specified topic. Can be used for both API and PubSub. Refer to TopicRequest schema for details.",
    tags=["Topics"],
)
async def delete_topic(key: str) -> Response:
    """Delete a specific topic identified by its key.

    Args:
        key (str): The unique identifier of the topic to delete.

    Returns:
        Response: The HTTP response confirming the deletion of the topic.

    Raises:
        HTTPException: If the topic deletion fails due to a Novu API client error (400 Bad Request).
        HTTPException: If an unexpected error occurs during the topic deletion process (500 Internal Server Error).
    """
    logger.debug("Received request to delete topic.")

    try:
        await TopicService().delete_novu_topic(key)
        logger.info("Topic deleted successfully.")
        return SuccessResponse(
            object="info",
            message="",
            code=status.HTTP_200_OK,
        ).to_http_response()
    except NovuApiClientException:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to delete the topic.") from None
    except Exception as err:
        logger.exception(f"Unexpected error occurred while deleting topic. {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while trying to delete the topic.",
        ) from None


@topic_router.post(
    "{key}/add-subscribers",
    response_model=TopicAddSubscriberResponse,
    status_code=status.HTTP_200_OK,
    description="Adds a subscriber to the specified topic. Can be used for both API and PubSub. Refer to TopicRequest schema for details.",
)
async def add_subscriber_to_topic(key: str, topic: TopicSubscriberRequest) -> Response:
    """Add subscribers to a specific topic identified by its key.

    Args:
        key (str): The unique identifier of the topic to which subscribers will be added.
        topic (TopicSubscriberRequest): The request object containing subscriber details.

    Returns:
        Response: The HTTP response indicating the result of adding subscribers to the topic, including
                  lists of successfully added and failed subscribers.

    Raises:
        HTTPException: If adding subscribers fails due to a Novu API client error (400 Bad Request).
        HTTPException: If an unexpected error occurs during the process of adding subscribers (500 Internal Server Error).
    """
    logger.debug("Received request to add subscribers to topic")

    try:
        response = await TopicService().add_subscribers_to_novu_topic(key, topic)
        logger.info("Subscriber added to topic successfully")
        return TopicAddSubscriberResponse(
            object="topic.subscribers.add",
            message="",
            code=status.HTTP_200_OK,
            success=response["success"],
            failed=response["failed"],
        ).to_http_response()
    except NovuApiClientException:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to add subscribers to topic"
        ) from None
    except Exception as err:
        logger.exception(f"Unexpected error occurred while adding subscribers to topic. {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error occurred while adding subscribers to topic.",
        ) from None


@topic_router.post(
    "{key}/remove-subscribers",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    description="Removes a subscriber from the specified topic. Can be used for both API and PubSub. Refer to TopicRequest schema for details.",
)
async def remove_subscriber_from_topic(key: str, topic: TopicSubscriberRequest) -> Response:
    """Remove subscribers from a specific topic identified by its key.

    Args:
        key (str): The unique identifier of the topic from which subscribers will be removed.
        topic (TopicSubscriberRequest): The request object containing subscriber details to be removed.

    Returns:
        Response: The HTTP response indicating the result of removing subscribers from the topic.

    Raises:
        HTTPException: If removing subscribers fails due to a Novu API client error (400 Bad Request).
        HTTPException: If an unexpected error occurs during the process of removing subscribers (500 Internal Server Error).
    """
    logger.debug("Received request to remove subscribers from topic")

    try:
        await TopicService().remove_subscribers_from_novu_topic(key, topic)
        logger.info("Subscriber removed from topic successfully")
        return SuccessResponse(object="info", message="", code=status.HTTP_200_OK).to_http_response()
    except NovuApiClientException:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to remove subscribers from topic"
        ) from None
    except Exception as err:
        logger.exception(f"Unexpected error occurred while removing subscribers from topic. {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error occurred while removing subscribers from topic.",
        ) from None


@topic_router.get(
    "/{key}/subscribers/{subscriber_id}",
    response_model=TopicCheckSubscriberResponse,
    status_code=status.HTTP_200_OK,
    description="Checks if a subscriber is subscribed to the specified topic. Can be used for both API and PubSub. Refer to TopicRequest schema for details.",
)
async def check_subscriber_in_topic(
    key: str,
    subscriber_id: str,
) -> Response:
    """Check if a subscriber is subscribed to a specific topic identified by its key.

    Args:
        key (str): The unique identifier of the topic to check.
        subscriber_id (str): The unique identifier of the subscriber to check for.

    Returns:
        Response: The HTTP response indicating whether the subscriber is subscribed to the topic.

    Raises:
        HTTPException: If checking the subscriber status fails due to a Novu API client error (400 Bad Request).
        HTTPException: If an unexpected error occurs during the check process (500 Internal Server Error).
    """
    logger.debug("Received request to check if subscriber is subscribed to topic")

    try:
        is_subscribed = await TopicService().check_subscriber_exists_in_novu_topic(key, subscriber_id)
        logger.info("Successfully checked if subscriber is subscribed to topic")
        return TopicCheckSubscriberResponse(
            object="info", message="", code=status.HTTP_200_OK, is_subscribed=is_subscribed
        ).to_http_response()
    except NovuApiClientException:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to check if subscriber is subscribed"
        ) from None
    except Exception as err:
        logger.exception(f"Unexpected error while checking if subscriber is subscribed. {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error while checking if subscriber is subscribed.",
        ) from None
