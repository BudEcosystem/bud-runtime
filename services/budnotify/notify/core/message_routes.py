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

"""Defines API routes for message management and TTL operations."""

from dataclasses import asdict
from typing import Optional

from fastapi import APIRouter, Query, Response, status

from notify.commons import logging
from notify.commons.exceptions import NovuApiClientException
from notify.commons.schemas import ErrorResponse, SuccessResponse
from notify.shared.novu_service import NovuService

from .schemas import MessageDeleteResponse, MessageDto, PaginatedMessageResponse
from .ttl_service import NotificationCleanupService


logger = logging.get_logger(__name__)

message_router = APIRouter()


@message_router.get(
    "/messages",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_200_OK: {
            "model": PaginatedMessageResponse,
            "description": "Successfully retrieved messages",
        },
    },
    status_code=status.HTTP_200_OK,
    description="Retrieves a paginated list of messages with optional filtering by channel, subscriber, or transaction ID.",
    tags=["Messages"],
)
async def list_messages(
    page: int = Query(0, ge=0, description="Page number for pagination"),
    limit: int = Query(10, ge=1, le=100, description="Number of messages per page"),
    channel: Optional[str] = Query(None, description="Filter by notification channel"),
    subscriber_id: Optional[str] = Query(None, description="Filter by subscriber ID"),
    transaction_id: Optional[str] = Query(None, description="Filter by transaction ID"),
    environment: str = Query("prod", description="Novu environment (dev or prod)"),
) -> Response:
    """Retrieve a list of messages from Novu.

    Args:
        page (int): Page number for pagination (default: 0).
        limit (int): Number of messages per page (default: 10, max: 100).
        channel (Optional[str]): Filter by notification channel.
        subscriber_id (Optional[str]): Filter by subscriber ID.
        transaction_id (Optional[str]): Filter by transaction ID.
        environment (str): Novu environment (dev or prod, default: prod).

    Returns:
        Response: Paginated list of messages.
    """
    logger.debug(f"Received request to list messages (page={page}, limit={limit})")
    try:
        novu_service = NovuService()
        messages = await novu_service.get_all_messages(
            page=page,
            limit=limit,
            channel=channel,
            subscriber_id=subscriber_id,
            transaction_id=transaction_id,
            environment=environment,
        )

        # Convert Novu DTOs to our response schema
        message_dtos = [MessageDto(**asdict(msg)) for msg in messages.data]

        return PaginatedMessageResponse(
            object="message",
            message="Messages retrieved successfully",
            code=status.HTTP_200_OK,
            page=messages.page,
            total_count=messages.total_count,
            page_size=messages.page_size,
            messages=message_dtos,
        ).to_http_response()
    except NovuApiClientException as err:
        logger.error(f"Novu API error: {err.message}")
        return ErrorResponse(
            code=status.HTTP_400_BAD_REQUEST,
            type="BadRequest",
            message=f"Failed to list messages: {err.message}",
        ).to_http_response()
    except Exception as err:
        logger.exception(f"Unexpected error while listing messages: {err}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            type="InternalServerError",
            message="Unexpected error occurred while listing messages",
        ).to_http_response()


@message_router.delete(
    "/messages/{message_id}",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_200_OK: {
            "model": MessageDeleteResponse,
            "description": "Successfully deleted message",
        },
    },
    status_code=status.HTTP_200_OK,
    description="Deletes a specific message by its ID.",
    tags=["Messages"],
)
async def delete_message(
    message_id: str,
    environment: str = Query("prod", description="Novu environment (dev or prod)"),
) -> Response:
    """Delete a message from Novu.

    Args:
        message_id (str): The ID of the message to delete.
        environment (str): Novu environment (dev or prod, default: prod).

    Returns:
        Response: Confirmation of message deletion.
    """
    logger.debug(f"Received request to delete message {message_id}")
    try:
        novu_service = NovuService()
        success = await novu_service.delete_message(message_id=message_id, environment=environment)

        return MessageDeleteResponse(
            object="message",
            message=f"Message {message_id} deleted successfully",
            code=status.HTTP_200_OK,
            acknowledged=success,
            status="deleted" if success else "failed",
        ).to_http_response()
    except NovuApiClientException as err:
        logger.error(f"Novu API error: {err.message}")
        return ErrorResponse(
            code=status.HTTP_400_BAD_REQUEST,
            type="BadRequest",
            message=f"Failed to delete message: {err.message}",
        ).to_http_response()
    except Exception as err:
        logger.exception(f"Unexpected error while deleting message: {err}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            type="InternalServerError",
            message="Unexpected error occurred while deleting message",
        ).to_http_response()


@message_router.post(
    "/cleanup/run",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_200_OK: {
            "model": SuccessResponse,
            "description": "Successfully triggered cleanup",
        },
    },
    status_code=status.HTTP_200_OK,
    description="Manually triggers the notification cleanup process for expired notifications.",
    tags=["Cleanup"],
)
async def run_cleanup(
    environment: str = Query("prod", description="Novu environment (dev or prod)"),
) -> Response:
    """Manually trigger the notification cleanup process.

    Args:
        environment (str): Novu environment (dev or prod, default: prod).

    Returns:
        Response: Cleanup statistics.
    """
    logger.info("Received request to manually trigger notification cleanup")
    try:
        cleanup_service = NotificationCleanupService()
        stats = await cleanup_service.cleanup_expired_notifications(environment=environment)

        return SuccessResponse(
            object="cleanup",
            message=f"Cleanup completed. Checked: {stats['checked']}, Deleted: {stats['deleted']}, Failed: {stats['failed']}, Not found: {stats['not_found']}",
            code=status.HTTP_200_OK,
        ).to_http_response()
    except Exception as err:
        logger.exception(f"Unexpected error during cleanup: {err}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            type="InternalServerError",
            message="Unexpected error occurred during cleanup",
        ).to_http_response()
