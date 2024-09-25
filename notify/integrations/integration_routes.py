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

"""Defines metadata routes for the microservices, providing endpoints for retrieving integration information."""

from dataclasses import asdict

from fastapi import APIRouter, Response, status
from fastapi.exceptions import HTTPException

from notify.commons import logging
from notify.commons.exceptions import NovuApiClientException
from notify.commons.schemas import SuccessResponse

from .schemas import (
    IntegrationCurlResponse,
    IntegrationListResponse,
    IntegrationRequest,
    IntegrationResponse,
)
from .services import IntegrationsService


logger = logging.get_logger(__name__)

integration_router = APIRouter(prefix="/integrations", tags=["Integrations"])


@integration_router.post(
    "",
    response_model=IntegrationResponse,
    status_code=status.HTTP_201_CREATED,
    description="Create a new integration. Can be used for both API and PubSub. Refer to IntegrationRequest schema for details.",
)
async def create_integration(integration: IntegrationRequest) -> Response:
    """Create a new integration in the Novu service.

    This endpoint allows users to create an integration by providing the necessary
    details in the request body. Upon successful creation, it returns the
    details of the created integration. In case of an error, appropriate HTTP
    exceptions will be raised.

    Args:
        integration (IntegrationRequest): The integration details to create.

    Returns:
        Response: A response containing the details of the created integration or an error message.
    """
    logger.debug("Received request to create a new integration")

    try:
        db_integration = await IntegrationsService().create_novu_integration(integration)
        logger.info("Integration created successfully")
        return IntegrationResponse(
            object="integration",
            message="",
            **asdict(db_integration),
            code=status.HTTP_200_OK,
        ).to_http_response()
    except NovuApiClientException:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to create integration") from None
    except Exception as err:
        logger.exception(f"Unexpected error occurred while creating integration. {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error occurred while creating integration.",
        ) from None


@integration_router.get(
    "",
    response_model=IntegrationListResponse,
    status_code=status.HTTP_200_OK,
    description="List all integrations. Can be used for both API and PubSub. Refer to IntegrationRequest schema for details.",
)
async def get_all_integrations() -> Response:
    """Fetch and return a list of all integrations.

    This endpoint retrieves integrations from the Novu service. It is suitable for
    both API and PubSub contexts. If successful, it will return a list of integrations
    along with a success message. In case of errors, appropriate HTTP exceptions
    will be raised.

    Returns:
        Response: A response containing the list of integrations or an error message.
    """
    logger.debug("Received request to list all integrations")

    try:
        db_integrations = await IntegrationsService().list_novu_integrations()
        logger.info("Successfully retrieved the list of integrations")
        return IntegrationListResponse(
            object="integration.list",
            message="",
            integrations=db_integrations,
            code=status.HTTP_200_OK,
        ).to_http_response()
    except NovuApiClientException:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to list integrations") from None
    except Exception as err:
        logger.exception(f"Unexpected error while listing integrations. {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error while listing integrations.",
        ) from None


@integration_router.put(
    "/{integration_id}",
    response_model=IntegrationResponse,
    status_code=status.HTTP_200_OK,
    description="Updates the specified integration. Can be used for both API and PubSub. Refer to IntegrationRequest schema for details.",
)
async def update_integration(integration_id: str, integration: IntegrationRequest) -> Response:
    """Update an existing integration in the Novu system.

    Args:
        integration_id (str): The ID of the integration to update.
        integration (IntegrationRequest): The updated integration data.

    Returns:
        Response: A response containing the updated integration information.

    Raises:
        HTTPException: If the operation fails due to a client or server error.
    """
    logger.debug("Received request to update integration")

    try:
        db_integration = await IntegrationsService().update_novu_integration(integration_id, integration)
        logger.info("Integration updated successfully.")
        return IntegrationResponse(
            object="integration",
            message="",
            code=status.HTTP_200_OK,
            **asdict(db_integration),
        ).to_http_response()
    except NovuApiClientException:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to update the integration."
        ) from None
    except Exception as err:
        logger.exception(f"Unexpected error occurred while updating integration. {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while trying to update the integration.",
        ) from None


@integration_router.delete(
    "/{integration_id}",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    description="Deletes the specified integration. Can be used for both API and PubSub. Refer to IntegrationRequest schema for details.",
)
async def delete_integration(integration_id: str) -> Response:
    """Delete an integration from the Novu system.

    Args:
        integration_id (str): The ID of the integration to delete.

    Returns:
        Response: A response indicating the success of the operation.

    Raises:
        HTTPException: If the operation fails due to a client or server error.
    """
    logger.debug("Received request to delete integration.")

    try:
        await IntegrationsService().delete_integration(integration_id)
        logger.info("Integration deleted successfully.")
        return SuccessResponse(
            object="info",
            message="",
            code=status.HTTP_200_OK,
        ).to_http_response()
    except NovuApiClientException:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to delete the integration."
        ) from None
    except Exception as err:
        logger.exception(f"Unexpected error occurred while deleting integration. {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while trying to delete the integration.",
        ) from None


@integration_router.post(
    "/{integration_id}/set-primary",
    response_model=IntegrationResponse,
    status_code=status.HTTP_200_OK,
    description="Sets the specified integration as primary. Can be used for both API and PubSub. Refer to IntegrationRequest schema for details.",
)
async def set_integration_as_primary(integration_id: str) -> Response:
    """Set an integration as primary in the Novu system.

    Args:
        integration_id (str): The ID of the integration to set as primary.

    Returns:
        Response: A response indicating the success of the operation, including integration details.

    Raises:
        HTTPException: If the operation fails due to a client or server error.
    """
    logger.debug(f"Received request to set integration {integration_id} as primary.")

    try:
        db_integration = await IntegrationsService().set_novu_integration_as_primary(integration_id)
        logger.info("Successfully set integration as primary.")
        return IntegrationCurlResponse(
            object="integration",
            message="",
            code=status.HTTP_200_OK,
            **db_integration,
        ).to_http_response()
    except NovuApiClientException:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to set integration as primary"
        ) from None
    except Exception as err:
        logger.exception(f"Unexpected error occurred while setting integration as primary. {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while trying to set the integration as primary.",
        ) from None
