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

from datetime import datetime

from fastapi import APIRouter, Response, status

from notify.commons import logging
from notify.commons.config import app_settings
from notify.commons.schemas import SuccessResponse


logger = logging.get_logger(__name__)

meta_router = APIRouter()


@meta_router.get(
    "/",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    description="Get microservice details.",
    tags=["Metadata"],
)
async def ping() -> Response:
    r"""Handle the endpoint to return details about the microservice.

    Calculate and return information including service name, version, description, environment, debugging status,
    deployment time, and uptime. The response is modeled using `SuccessResponse`.

    Returns:
        Response: A `SuccessResponse` containing the service information and HTTP status code 200.

    Example:
        >>> response = await ping()
        >>> response.status_code
        200
        >>> response.json()
        {
            "object": "info",
            "message": "Microservice: MyService v1.0\nDescription: A sample service\nEnvironment: DEVELOPMENT\nDebugging: Enabled\nDeployed at: 2024-01-01 12:00:00\nUptime: 1h:30m:45s"
        }
    """
    uptime_in_seconds = int((datetime.now(tz=app_settings.tzone) - app_settings.deployed_at).total_seconds())
    hours, remainder = divmod(uptime_in_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    info = (
        f"Microservice: {app_settings.name} v{app_settings.version}\n"
        f"Description: {app_settings.description}\n"
        f"Environment: {app_settings.env}\n"
        f"Debugging: {'Enabled' if app_settings.debug else 'Disabled'}\n"
        f"Deployed at: {app_settings.deployed_at}\n"
        f"Uptime: {hours}h:{minutes}m:{seconds}s"
    )

    return SuccessResponse(message=info, code=status.HTTP_200_OK).to_http_response()


@meta_router.get(
    "/health",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    description="Get microservice health.",
    tags=["Metadata"],
)
async def health() -> Response:
    """Handle the endpoint to return the health status of the microservice.

    Provides a simple acknowledgment response to indicate that the microservice is running and healthy.
    The response is modeled using `SuccessResponse`.

    Returns:
        Response: A `SuccessResponse` containing an acknowledgment message and HTTP status code 200.

    Example:
        >>> response = await health()
        >>> response.status_code
        200
        >>> response.json()
        {
            "object": "info",
            "message": "ack"
        }
    """
    return SuccessResponse(message="ack", code=status.HTTP_200_OK).to_http_response()
