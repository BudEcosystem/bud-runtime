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
from notify.commons.config import app_settings, secrets_settings
from notify.commons.schemas import ErrorResponse, SuccessResponse
from notify.shared.dapr_service import DaprService, WorkflowNotFoundException


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


@meta_router.get(
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


@meta_router.get(
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


@meta_router.get(
    "/register",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service registration failures due to internal issues.",
        }
    },
    description="Register the microservice to the ecosystem.",
    tags=["Sync"],
)
async def register_service() -> Response:
    """Register the microservice to the ecosystem.

    This endpoint attempts to register the current microservice with the ecosystem
    using the DaprService. If successful, it returns a SuccessResponse. In case of
    any failures during the registration process, it returns an ErrorResponse.

    Returns:
        Response: A SuccessResponse with HTTP status code 200 if registration is successful,
                  or an ErrorResponse with HTTP status code 500 if registration fails.

    Raises:
        HTTPException: Implicitly raised with status code 500 if an exception occurs during registration.

    Example:
        >>> response = await register_service()
        >>> response.status_code
        200
        >>> response.json()
        {
            "object": "info",
            "message": "Service registration successful."
        }
    """
    try:
        with DaprService() as dapr_service:
            await dapr_service.register_service()

        return SuccessResponse(
            message="Service registration successful.",
            code=status.HTTP_200_OK,
        ).to_http_response()
    except Exception as e:
        logger.exception("Service registration failed with %s", str(e))

        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Service registration failed."
        ).to_http_response()


@meta_router.get("/status/{workflow_id}", tags=["Metadata"])
async def get_workflow_status(workflow_id: str) -> Response:
    """Retrieve the status of a specific workflow.

    This endpoint allows clients to check the current status of a workflow
    identified by the provided workflow ID. It returns the status information
    which can be used to determine if the workflow is still running, completed,
    or has encountered an error.

    Args:
        workflow_id (str): The unique identifier of the workflow whose status
        is to be retrieved.

    Returns:
        HTTP response containing the status of the specified workflow.
    """
    try:
        with DaprService() as dapr_service:
            result = await dapr_service.get_workflow_details(workflow_id=workflow_id)
            response = SuccessResponse(message="ack", param={"status": result["status"]}, code=200)
    except WorkflowNotFoundException:
        response = ErrorResponse(message="No such workflow exists", code=404)
    except Exception as err:
        logger.exception("Couldn't resolve workflow status: %s", str(err))
        response = ErrorResponse(message="Couldn't resolve workflow status", code=500)
    return response.to_http_response()
