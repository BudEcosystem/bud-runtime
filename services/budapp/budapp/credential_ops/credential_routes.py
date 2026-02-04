import json
import uuid
from typing import Annotated, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, Request, status
from sqlalchemy.orm import Session
from typing_extensions import Union

from budapp.commons import logging
from budapp.commons.constants import ApiCredentialTypeEnum, CredentialTypeEnum
from budapp.commons.dependencies import get_current_active_user, get_session, parse_ordering_fields
from budapp.commons.exceptions import ClientException
from budapp.commons.schemas import (
    ErrorResponse,
    SingleResponse,
    SuccessResponse,
)
from budapp.commons.security import RSAHandler
from budapp.user_ops.schemas import User

from ..commons.async_utils import get_user_from_auth_header
from .crud import CloudProviderCredentialDataManager, CloudProviderDataManager, CredentialDataManager
from .models import CloudCredentials, CloudProviders, Credential
from .schemas import (
    PROPRIETARY_CREDENTIAL_DATA,
    CloudCredentialResponse,
    CloudCredentialSchema,
    CloudProviderRegionsResponse,
    CloudProvidersCreateRequest,
    CloudProvidersListResponse,
    CloudProvidersSchema,
    CredentialFilter,
    CredentialRequest,
    CredentialResponse,
    CredentialUpdate,
    PaginatedCredentialResponse,
    ProprietaryCredentialDetailedView,
    ProprietaryCredentialFilter,
    ProprietaryCredentialRequest,
    ProprietaryCredentialResponse,
    ProprietaryCredentialUpdate,
)
from .services import ClusterProviderService, CredentialService, ProprietaryCredentialService


logger = logging.get_logger(__name__)

credential_router = APIRouter(prefix="/credentials", tags=["credential"])
proprietary_credential_router = APIRouter(prefix="/proprietary/credentials", tags=["proprietary credential"])
error_responses = {
    401: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


@credential_router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=SingleResponse[CredentialResponse],
    responses={
        **error_responses,
        500: {"model": ErrorResponse},
    },
    description=f"""Add or generate a new credential for user. Valid credential types:
    {", ".join([value.value for value in ApiCredentialTypeEnum])}.
    Project_id and expiry(None, 0, 30, 60, or 90) are required. 0 or None means no expiry.""",
)
async def add_credential(
    request: Request,
    credential: CredentialRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    credential_response = await CredentialService(session).add_credential(current_user.id, credential, request)
    logger.info(f"API-Key credential added: {credential_response.id}")

    return SingleResponse(message="Credential added successfully", result=credential_response)


@credential_router.get(
    "/",
    response_model=PaginatedCredentialResponse,
    responses=error_responses,
    description="Get saved credentials of user",
)
async def retrieve_credentials(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],  # noqa: B008
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=0),
    filters: CredentialFilter = Depends(),  # noqa: B008
    order_by: Optional[List[str]] = Depends(parse_ordering_fields),  # noqa: B008
    search: bool = False,
):
    # Calculate offset
    offset = (page - 1) * limit

    # Convert Filter to dictionary
    filters_dict = filters.model_dump(exclude_none=True)
    filters_dict["user_id"] = current_user.id
    results, count = await CredentialService(session).get_credentials(
        current_user, offset, limit, filters_dict, order_by, search
    )

    return PaginatedCredentialResponse(
        message="Credentials listed successfully",
        credentials=results,
        total_record=count,
        page=page,
        limit=limit,
    )


@credential_router.put(
    "/{credential_id}",
    response_model=SingleResponse[CredentialResponse],
    response_model_exclude_none=True,
    responses={
        **error_responses,
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
    description="Update saved credential of user.",
)
async def update_credential(
    request: Request,
    credential_id: UUID,
    credential_data: CredentialUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    db_credential = await CredentialService(session).update_credential(
        credential_data, credential_id, current_user.id, request
    )
    logger.info(f"Credential updated: {db_credential.id}")

    credential_response = CredentialResponse(
        name=db_credential.name,
        project_id=db_credential.project_id,
        key=db_credential.encrypted_key,  # Already encrypted, no need to encrypt again
        expiry=db_credential.expiry,
        max_budget=db_credential.max_budget,
        model_budgets=db_credential.model_budgets,
        id=db_credential.id,
        created_at=db_credential.created_at,
        last_used_at=db_credential.last_used_at,
        credential_type=db_credential.credential_type,
        ip_whitelist=db_credential.ip_whitelist,
    )

    return SingleResponse(message="Credential updated successfully", result=credential_response)


@credential_router.delete(
    "/{credential_id}",
    response_model=SuccessResponse,
    responses={
        **error_responses,
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
    description="Delete saved credential of user",
)
async def delete_credential(
    request: Request,
    credential_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    await CredentialService(session).delete_credential(credential_id, current_user.id, request)
    logger.info("Credential deleted")

    return SuccessResponse(message="Credential deleted successfully")


@proprietary_credential_router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=SingleResponse[ProprietaryCredentialResponse],
    responses={
        **error_responses,
        500: {"model": ErrorResponse},
    },
    description=f"""Add or generate a new credential for proprietary models.
    Valid credential types: {", ".join([value.value for value in CredentialTypeEnum])}.
    For budserve credential type, project_id, expiry(None, 0, 30, 60, or 90) are required. 0 or None means no expiry.""",
)
async def add_proprietary_credential(
    request: Request,
    credential: ProprietaryCredentialRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    credential_response = await ProprietaryCredentialService(session).add_credential(
        current_user.id, credential, request
    )
    logger.info(f"{credential.type.value} credential added: {credential_response}")

    return SingleResponse(message="Credential added successfully", result=credential_response)


@proprietary_credential_router.get(
    "/",
    response_model=PaginatedCredentialResponse,
    responses=error_responses,
    description="Get proprietary credentials of user",
)
async def retrieve_proprietary_credentials(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],  # noqa: B008
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=0),
    filters: ProprietaryCredentialFilter = Depends(),  # noqa: B008
    order_by: Optional[List[str]] = Depends(parse_ordering_fields),  # noqa: B008
    search: bool = False,
):
    # Calculate offset
    offset = (page - 1) * limit

    # Convert Filter to dictionary
    filters_dict = filters.model_dump(exclude_none=True)
    filters_dict["user_id"] = current_user.id
    results, count = await ProprietaryCredentialService(session).get_all_credentials(
        offset, limit, filters_dict, order_by, search
    )

    return PaginatedCredentialResponse(
        message="Proprietary credentials listed successfully",
        credentials=results,
        total_record=count,
        page=page,
        limit=limit,
    )


@proprietary_credential_router.put(
    "/{credential_id}",
    response_model=SingleResponse[ProprietaryCredentialResponse],
    response_model_exclude_none=True,
    responses={
        **error_responses,
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
    description="Update saved proprietary credential of user.",
)
async def update_proprietary_credential(
    request: Request,
    credential_id: UUID,
    credential_data: ProprietaryCredentialUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    db_credential = await ProprietaryCredentialService(session).update_credential(
        credential_id, credential_data, current_user.id, request
    )
    logger.info(f"Credential updated: {db_credential.id}")

    return SingleResponse(message="Credential updated successfully", result=db_credential)


@proprietary_credential_router.delete(
    "/{credential_id}",
    response_model=SuccessResponse,
    responses={
        **error_responses,
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
    description="Delete saved proprietary credential of user",
)
async def delete_proprietary_credential(
    request: Request,
    credential_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    await ProprietaryCredentialService(session).delete_credential(credential_id, current_user.id, request)
    logger.info("Credential deleted")

    return SuccessResponse(message="Credential deleted successfully")


@proprietary_credential_router.get(
    "/provider-info",
    response_model=SingleResponse,
    responses={
        **error_responses,
        500: {"model": ErrorResponse},
    },
    description="Different proprietary provider information",
)
async def get_provider_info(
    current_user: Annotated[User, Depends(get_current_active_user)],
    provider_name: CredentialTypeEnum,
):
    result = PROPRIETARY_CREDENTIAL_DATA.get(
        provider_name.value if provider_name else None, PROPRIETARY_CREDENTIAL_DATA
    )
    return SingleResponse(
        message="Provider info retrieved successfully",
        result=result,
    )


@proprietary_credential_router.get(
    "/{credential_id}/detailed-view",
    response_model=SingleResponse[ProprietaryCredentialDetailedView],
    responses=error_responses,
    description="Get details of a proprietary credential",
)
async def get_proprietary_credential_detailed_view(
    credential_id: UUID,
    _: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    credential_details = await ProprietaryCredentialService(session).get_credential_details(
        credential_id, detailed_view=True
    )
    return SingleResponse(message="Credential details fetched successfully", result=credential_details)


@proprietary_credential_router.get(
    "/{credential_id}/details",
    response_model=SingleResponse[ProprietaryCredentialResponse],
    responses=error_responses,
    description="Get details of a proprietary credential",
)
async def get_proprietary_credential_details(credential_id: UUID, session: Annotated[Session, Depends(get_session)]):
    credential_details = await ProprietaryCredentialService(session).get_credential_details(credential_id)
    return SingleResponse(message="Credential details fetched successfully", result=credential_details)


@credential_router.get(
    "/cloud-providers",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_401_UNAUTHORIZED: {
            "model": ErrorResponse,
            "description": "User is not authenticated",
        },
        status.HTTP_200_OK: {
            "model": CloudProvidersListResponse,
            "description": "Successfully retrieved cloud providers",
        },
    },
    description="Get all available cloud providers",
)
async def get_cloud_providers(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Union[CloudProvidersListResponse, ErrorResponse]:
    """Get all cloud providers - requires authentication."""
    logger.debug(f"User {current_user.id} getting all the cloud providers")
    try:
        # Use CloudProviderDataManager to get all providers
        providers = await CloudProviderDataManager(session).get_all_providers()

        # Convert SQLAlchemy objects to CloudProvidersSchema objects
        provider_schemas = []
        for provider in providers:
            provider_dict = {
                column.name: str(getattr(provider, column.name))
                if isinstance(getattr(provider, column.name), uuid.UUID)
                else getattr(provider, column.name)
                for column in provider.__table__.columns
            }

            # Ensure schema_definition is a valid JSON string
            if "schema_definition" in provider_dict and not isinstance(provider_dict["schema_definition"], str):
                provider_dict["schema_definition"] = json.dumps(provider_dict["schema_definition"])

            # Ensure `id` is always a string before validation
            if isinstance(provider_dict.get("id"), uuid.UUID):
                provider_dict["id"] = str(provider_dict["id"])

            try:
                schema = CloudProvidersSchema(**provider_dict)
                provider_schemas.append(schema)
            except Exception as e:
                logger.error(f"Failed to create schema for provider {provider_dict.get('id', 'unknown')}: {e}")
                continue

        # Create response
        response = CloudProvidersListResponse(
            providers=provider_schemas, code=status.HTTP_200_OK, message="Cloud providers retrieved successfully"
        )
        return response
    except Exception as e:
        logger.exception(f"Failed to get cloud providers: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get cloud providers"
        ).to_http_response()


@credential_router.post("/cloud-providers")
async def create_cloud_provider(
    current_user: Annotated[User, Depends(get_current_active_user)],
    cloud_provider_requst: CloudProvidersCreateRequest,
    session: Annotated[Session, Depends(get_session)],
):
    """Create a new cloud provider credential."""
    logger.debug(f"Creating cloud provider: {cloud_provider_requst}")

    try:
        # Validate the provider id in the database
        provider = await CloudProviderDataManager(session).retrieve_by_fields(
            CloudProviders, {"id": cloud_provider_requst.provider_id}
        )
        if not provider:
            return ErrorResponse(code=status.HTTP_400_BAD_REQUEST, message="Provider ID is invalid").to_http_response()

        # Save credentials via service
        await ClusterProviderService(session).create_provider_credential(cloud_provider_requst, current_user.id)

        return SuccessResponse(
            code=status.HTTP_201_CREATED, message="Cloud provider created successfully"
        ).to_http_response()

    except Exception as e:
        logger.exception(f"Failed to create cloud provider: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to create cloud provider"
        ).to_http_response()


@credential_router.get("/cloud-providers/credentials", response_model=CloudCredentialResponse)
async def get_user_cloud_credentials(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    provider_id: Annotated[
        Optional[str],
        Query(title="Provider ID", description="Filter credentials by cloud provider ID", required=False),
    ] = None,
):
    """Retrieve cloud provider credentials for the current user.

    Args:
        provider_id: Optional parameter to filter credentials by provider ID

    Returns:
        CloudCredentialResponse: List of cloud provider credentials for the user,
            filtered by provider_id if specified.
    """
    logger.debug(
        f"Retrieving cloud credentials for user: {current_user.id}"
        + (f" filtered by provider: {provider_id}" if provider_id else "")
    )
    try:
        # Convert provider_id to UUID if provided
        provider_uuid = None
        if provider_id:
            try:
                provider_uuid = UUID(provider_id)
            except ValueError:
                return ErrorResponse(
                    code=status.HTTP_400_BAD_REQUEST, message="Invalid provider ID format"
                ).to_http_response()

        # Use the CloudProviderCredentialDataManager to get user credentials
        credentials = await CloudProviderCredentialDataManager(session).get_credentials_by_user(
            current_user.id, provider_uuid
        )

        # Convert database models to response schemas
        credential_schemas = []
        for cred in credentials:
            # Get provider information
            provider = await CloudProviderDataManager(session).retrieve_by_fields(
                CloudProviders, {"id": cred.provider_id}
            )

            # Create credential schema with masked sensitive data
            credential_schema = CloudCredentialSchema(
                id=str(cred.id),
                provider_id=str(cred.provider_id),
                provider_name=provider.name if provider else "Unknown Provider",
                icon=provider.logo_url,  # type: ignore
                provider_description=provider.description if provider else "No Description Available",
                created_at=cred.created_at,
                credential_name=cred.credential_name,
                # Mask sensitive information in credential values
                credential_summary=_get_masked_credential_summary(
                    cred.encrypted_credential, provider.schema_definition if provider else {}
                ),
            )
            credential_schemas.append(credential_schema)

        # Sort credentials by created_at in descending order (newest first)
        credential_schemas.sort(key=lambda x: x.created_at, reverse=True)

        return CloudCredentialResponse(
            credentials=credential_schemas,
            code=status.HTTP_200_OK,
            message="Cloud provider credentials retrieved successfully",
        )
    except Exception as e:
        logger.exception(f"Failed to retrieve cloud credentials: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to retrieve cloud provider credentials"
        ).to_http_response()


@credential_router.get("/cloud-providers/credentials/{credential_id}", response_model=CloudCredentialResponse)
async def get_user_cloud_credential(
    credential_id: Annotated[str, Path(title="The ID of the credential to retrieve")],
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Retrieve a specific cloud provider credential for the current user.

    Args:
        credential_id: ID of the credential to retrieve

    Returns:
        CloudCredentialResponse: The requested cloud provider credential.
    """
    logger.debug(f"Retrieving cloud credential {credential_id} for user: {current_user.id}")

    try:
        # Convert string ID to UUID
        try:
            cred_uuid = UUID(credential_id)
        except ValueError:
            return ErrorResponse(
                code=status.HTTP_400_BAD_REQUEST, message="Invalid credential ID format"
            ).to_http_response()

        # Query the specific credential
        credential = await CloudProviderDataManager(session).retrieve_by_fields(CloudCredentials, {"id": cred_uuid})

        if not credential:
            return ErrorResponse(code=status.HTTP_404_NOT_FOUND, message="Credential not found").to_http_response()

        # Verify the credential belongs to the current user
        if credential.user_id != current_user.id:
            return ErrorResponse(
                code=status.HTTP_403_FORBIDDEN, message="You don't have permission to access this credential"
            ).to_http_response()

        # Get provider information
        provider = await CloudProviderDataManager(session).retrieve_by_fields(
            CloudProviders, {"id": credential.provider_id}
        )

        # Create credential schema
        credential_schema = CloudCredentialSchema(
            id=str(credential.id),
            icon=provider.logo_url,  # type: ignore
            provider_id=str(credential.provider_id),
            credential_name=credential.credential_name,
            provider_description=provider.description if provider else "No Description Available",
            provider_name=provider.name if provider else "Unknown Provider",
            created_at=credential.created_at,
            # For individual credential view, provide more detailed but still masked info
            credential_summary=_get_masked_credential_summary(
                credential.encrypted_credential, provider.schema_definition if provider else {}, detailed=True
            ),
        )

        return CloudCredentialResponse(
            credentials=[credential_schema],
            code=status.HTTP_200_OK,
            message="Cloud provider credential retrieved successfully",
        )
    except Exception as e:
        logger.exception(f"Failed to retrieve cloud credential: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to retrieve cloud provider credential"
        ).to_http_response()


# Regions Listing
@credential_router.get("/cloud-providers/{provider_id}/regions", response_model=CloudProviderRegionsResponse)
async def get_provider_regions(
    provider_id: Annotated[str, Path(title="The ID of the cloud provider")],
    session: Annotated[Session, Depends(get_session)],
):
    """Retrieve the regions supported by a specific cloud provider.

    Args:
        provider_id: The UUID of the cloud provider.

    Returns:`
        CloudProviderRegionsResponse: List of regions supported by the provider.

    Raises:
        HTTPException: If the provider is not found.
    """
    logger.debug(f"Retrieving regions for cloud provider: {provider_id}")

    try:
        # Convert string ID to UUID
        try:
            provider_uuid = UUID(provider_id)
        except ValueError:
            return ErrorResponse(
                code=status.HTTP_400_BAD_REQUEST, message="Invalid provider ID format"
            ).to_http_response()

        # Get the provider from the database
        provider = await CloudProviderDataManager(session).retrieve_by_fields(CloudProviders, {"id": provider_uuid})

        if not provider:
            return ErrorResponse(code=status.HTTP_404_NOT_FOUND, message="Cloud provider not found").to_http_response()

        # Use provider service to get regions for this specific provider
        regions = await ClusterProviderService(session).get_provider_regions(provider.unique_id)  # type: ignore

        return CloudProviderRegionsResponse(
            provider_id=str(provider.id),  # type: ignore
            regions=regions,
            code=status.HTTP_200_OK,
            message=f"Retrieved {len(regions)} regions for {provider.name}",  # type: ignore
        )

    except Exception as e:
        logger.error(f"Failed to retrieve regions for cloud provider: {provider_id} {e}", exc_info=True)
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to retrieve cloud provider credential"
        ).to_http_response()


# Helper function for masking sensitive data
def _get_masked_credential_summary(credential_values: dict, schema_definition: dict, detailed: bool = False) -> dict:
    """Create a summary of credential values with sensitive information masked.

    Args:
        credential_values: The raw credential values
        schema_definition: The schema definition from the provider
        detailed: Whether to include more details (for individual credential view)

    Returns:
        Dict with masked sensitive values
    """
    result = {}

    # If we don't have a schema definition, just mask everything
    if not schema_definition:
        return dict.fromkeys(credential_values, "********")

    # Get the schema properties
    properties = schema_definition.get("properties", {})

    for key, value in credential_values.items():
        property_info = properties.get(key, {})
        # Check if this is a secret field (look for hints in the schema)
        is_secret = (
            property_info.get("format") == "password"
            or property_info.get("x-sensitive")
            or "secret" in key.lower()
            or "password" in key.lower()
            or "key" in key.lower()
            or "token" in key.lower()
        )

        if is_secret:
            # For secrets, show only "********"
            result[key] = "********"
        elif detailed:
            # For detailed view, include non-sensitive values
            result[key] = value
        else:
            # For list view, include a simplified view
            if isinstance(value, str) and len(value) > 10:
                result[key] = value[:4] + "..." + value[-4:]
            else:
                result[key] = value

    return result
