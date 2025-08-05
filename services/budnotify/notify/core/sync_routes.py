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

"""Defines synchronization routes for the microservices, handling the syncing of configurations and secrets with external stores."""

from fastapi import APIRouter, Response, status

from notify.commons import logging
from notify.commons.config import app_settings, secrets_settings
from notify.commons.schemas import ErrorResponse, SuccessResponse
from notify.shared.dapr_service import DaprService


logger = logging.get_logger(__name__)

sync_router = APIRouter()


@sync_router.get(
    "/sync/configurations",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to a misconfigured configuration store",
        }
    },
    description="Sync microservice configuration from a supported configstore.",
    tags=["Sync"],
)
async def sync_configurations() -> Response:
    """Synchronize the microservice configuration from a supported configstore.

    Check if a configstore is configured and syncs the microservice configuration fields from it.
    The configurations are fetched from the configstore, updated in the application settings,
    and a success message with the count of configurations synced is returned.

    Returns:
        Response: A `SuccessResponse` with the count of configurations synced and HTTP status code 200,
        or an `ErrorResponse` if the configstore is not configured, with HTTP status code 503.

    Raises:
        HTTPException: If the configstore is not configured, an HTTP 503 Service Unavailable error is returned.

    Example:
        >>> response = await sync_configurations()
        >>> response.status_code
        200
        >>> response.json()
        {
            "object": "info",
            "message": "5/10 configuration(s) synced."
        }
    """
    if app_settings.configstore_name:
        fields_to_sync = app_settings.get_fields_to_sync()

        with DaprService() as dapr_service:
            values, _ = await dapr_service.sync_configurations(fields_to_sync)

        app_settings.update_fields(values)

        return SuccessResponse(
            message=f"{len(values)}/{len(fields_to_sync)} configuration(s) synced.",
            code=status.HTTP_200_OK,
        ).to_http_response()
    else:
        return ErrorResponse(
            message="Config store is not configured.",
            code=status.HTTP_503_SERVICE_UNAVAILABLE,
        ).to_http_response()


@sync_router.get(
    "/sync/secrets",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to a misconfigured secret store",
        }
    },
    description="Sync microservice secrets from a supported secret store.",
    tags=["Sync"],
)
async def sync_secrets() -> Response:
    """Synchronize microservice secrets from a supported secret store.

    Check if a secret store is configured and syncs the microservice secret fields from it.
    The secrets are fetched from the secret store, updated in the application settings,
    and a success message with the count of secrets synced is returned.

    Returns:
        Response: A `SuccessResponse` with the count of secrets synced and HTTP status code 200,
        or an `ErrorResponse` if the secret store is not configured, with HTTP status code 503.

    Raises:
        HTTPException: If the secret store is not configured, an HTTP 503 Service Unavailable error is returned.

    Example:
        >>> response = await sync_secrets()
        >>> response.status_code
        200
        >>> response.json()
        {
            "object": "info",
            "message": "7/10 secret(s) synced."
        }
    """
    if app_settings.secretstore_name:
        fields_to_sync = secrets_settings.get_fields_to_sync()

        with DaprService() as dapr_service:
            values = await dapr_service.sync_secrets(fields_to_sync)

        secrets_settings.update_fields(values)

        return SuccessResponse(
            message=f"{len(values)}/{len(fields_to_sync)} secret(s) synced.",
            code=status.HTTP_200_OK,
        ).to_http_response()
    else:
        return ErrorResponse(
            message="Secret store is not configured.",
            code=status.HTTP_503_SERVICE_UNAVAILABLE,
        ).to_http_response()
