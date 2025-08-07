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

"""Defines metadata routes for the microservices, providing endpoints for retrieving settings."""

from fastapi import APIRouter, Response, status

from notify.commons import logging
from notify.commons.config import secrets_settings
from notify.commons.schemas import ErrorResponse

from .schemas import (
    CredentialsResponse,
)


logger = logging.get_logger(__name__)

settings_router = APIRouter(prefix="/settings", tags=["Settings"])


@settings_router.get(
    "/credentials",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_200_OK: {
            "model": CredentialsResponse,
            "description": "Successfully retrieved credentials",
        },
    },
    status_code=status.HTTP_200_OK,
    description="Retrieve credentials for the current environment. Can be used for Novu frontend integration.",
)
async def get_credentials() -> Response:
    """Retrieve credentials for the current environment.

    Returns:
        Response: The HTTP response containing the credentials.
    """
    logger.debug("Received request to retrieve credentials")

    try:
        return CredentialsResponse(
            object="credentials",
            message="Credentials retrieved successfully",
            prod_app_id=secrets_settings.novu_prod_app_id,
            code=status.HTTP_200_OK,
        ).to_http_response()
    except Exception as err:
        logger.exception(f"Unexpected error while retrieving credentials. {err}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            type="InternalServerError",
            message="Unexpected error while retrieving credentials.",
        )
