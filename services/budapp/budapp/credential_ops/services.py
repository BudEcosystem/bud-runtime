import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

import httpx
from fastapi import HTTPException, Request, status
from fastapi.exceptions import HTTPException

from budapp.audit_ops import log_audit
from budapp.commons import logging
from budapp.commons.config import app_settings
from budapp.commons.constants import (
    ApiCredentialTypeEnum,
    AuditActionEnum,
    AuditResourceTypeEnum,
    EndpointStatusEnum,
    GuardrailDeploymentStatusEnum,
    ModelProviderTypeEnum,
    NotificationCategory,
    NotificationStatus,
    PermissionEnum,
    ProjectStatusEnum,
    ProjectTypeEnum,
    UserTypeEnum,
)
from budapp.commons.db_utils import SessionMixin
from budapp.commons.security import RSAHandler
from budapp.endpoint_ops.crud import AdapterDataManager, EndpointDataManager
from budapp.endpoint_ops.models import Endpoint as EndpointModel
from budapp.guardrails.crud import GuardrailsDeploymentDataManager
from budapp.guardrails.models import GuardrailDeployment
from budapp.model_ops.crud import ProviderDataManager

# from ..models import Route as RouteModel
from budapp.model_ops.models import Model
from budapp.model_ops.models import Provider as ProviderModel
from budapp.permissions.crud import PermissionDataManager, ProjectPermissionDataManager
from budapp.project_ops.crud import ProjectDataManager
from budapp.project_ops.services import ProjectService
from budapp.prompt_ops.crud import PromptDataManager
from budapp.shared.notification_service import BudNotifyService, NotificationBuilder
from budapp.shared.redis_service import RedisService, cache
from budapp.user_ops.crud import UserDataManager
from budapp.user_ops.models import User as UserModel

from ..project_ops.models import Project as ProjectModel
from .crud import CloudProviderDataManager, CredentialDataManager, ProprietaryCredentialDataManager
from .helpers import generate_secure_api_key, validate_ip_whitelist
from .models import CloudCredentials, CloudProviders
from .models import Credential as CredentialModel
from .models import ProprietaryCredential as ProprietaryCredentialModel
from .schemas import (
    BudCredentialCreate,
    CloudProvidersCreateRequest,
    CredentialDetails,
    CredentialRequest,
    CredentialResponse,
    CredentialUpdate,
    ProprietaryCredentialDetailedView,
    ProprietaryCredentialRequest,
    ProprietaryCredentialResponse,
    ProprietaryCredentialResponseList,
    ProprietaryCredentialUpdate,
)


logger = logging.get_logger(__name__)


class CredentialService(SessionMixin):
    async def _check_duplicate_credential(self, credential: dict) -> bool:
        db_credential = await CredentialDataManager(self.session).retrieve_credential_by_fields(
            {"name": credential["name"], "project_id": credential["project_id"]}, missing_ok=True
        )
        return db_credential is not None

    async def add_credential(
        self, current_user_id: UUID, credential: CredentialRequest, request: Optional[Request] = None
    ) -> CredentialResponse:
        # Validate project id
        db_project = await ProjectDataManager(self.session).retrieve_project_by_fields(
            {"id": credential.project_id, "status": ProjectStatusEnum.ACTIVE}
        )

        if await self._check_duplicate_credential({"name": credential.name, "project_id": credential.project_id}):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Credential already exists with the same name",
            )
        # Check user has authority to create credential for project
        db_permission = await PermissionDataManager(self.session).retrieve_permission_by_fields(
            {"user_id": current_user_id}, missing_ok=True
        )
        user_scopes = db_permission.scopes_list if db_permission else []

        # NOTE: user with project:manage scope can create credential for any project. Otherwise user must be a project member
        if PermissionEnum.PROJECT_MANAGE.value not in user_scopes:
            # Check user has access to project
            await ProjectService(self.session).check_project_membership(db_project.id, current_user_id)

        # Add or generate credential
        db_credential = await self.add_or_generate_credential(credential, current_user_id)

        # Decrypt the key for cache update
        decrypted_key = await RSAHandler().decrypt(db_credential.encrypted_key)
        await self.update_proxy_cache(db_credential.project_id, decrypted_key, db_credential.expiry)

        # Log successful credential creation
        audit_details = {
            "credential_name": db_credential.name,
            "project_name": db_project.name,
            "expiry": str(db_credential.expiry) if db_credential.expiry else None,
        }
        if db_credential.max_budget is not None:
            audit_details["max_budget"] = db_credential.max_budget

        log_audit(
            session=self.session,
            action=AuditActionEnum.CREATE,
            resource_type=AuditResourceTypeEnum.API_KEY,
            resource_id=db_credential.id,
            resource_name=db_credential.name,
            user_id=current_user_id,
            details=audit_details,
            request=request,
            success=True,
        )

        # Use the encrypted key directly
        credential_response = CredentialResponse(
            name=db_credential.name,
            project_id=db_credential.project_id,
            key=db_credential.encrypted_key,  # Already encrypted
            expiry=db_credential.expiry,
            max_budget=db_credential.max_budget,
            model_budgets=db_credential.model_budgets,
            id=db_credential.id,
            created_at=db_credential.created_at,
            last_used_at=db_credential.last_used_at,
            credential_type=db_credential.credential_type,
            ip_whitelist=db_credential.ip_whitelist,
        )

        return credential_response

    async def add_or_generate_credential(self, request: CredentialRequest, user_id: UUID) -> CredentialModel:
        # Get user information to determine credential type
        db_user = await UserDataManager(self.session).retrieve_by_fields(UserModel, {"id": user_id})

        # Get project information to validate credential type compatibility
        db_project = await ProjectDataManager(self.session).retrieve_by_fields(
            ProjectModel, {"id": request.project_id, "status": ProjectStatusEnum.ACTIVE}
        )

        # Automatically set credential_type based on user_type if not explicitly provided
        credential_type = request.credential_type
        if db_user.user_type == UserTypeEnum.CLIENT:
            # Client users should only create client_app credentials
            credential_type = ApiCredentialTypeEnum.CLIENT_APP
        elif db_user.user_type == UserTypeEnum.ADMIN:
            # Admin users can create any type - use what they requested or default to admin_app
            if request.credential_type is None:
                credential_type = ApiCredentialTypeEnum.ADMIN_APP
            else:
                credential_type = request.credential_type

        # Validate that credential type matches project type
        if (
            credential_type == ApiCredentialTypeEnum.CLIENT_APP
            and db_project.project_type != ProjectTypeEnum.CLIENT_APP
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CLIENT_APP credentials can only be created for CLIENT_APP projects",
            )
        elif (
            credential_type == ApiCredentialTypeEnum.ADMIN_APP and db_project.project_type != ProjectTypeEnum.ADMIN_APP
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ADMIN_APP credentials can only be created for ADMIN_APP projects",
            )

        # Validate IP whitelist if provided
        if request.ip_whitelist:
            try:
                validate_ip_whitelist(request.ip_whitelist)
            except ValueError as e:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        # Generate new credential using secure method
        api_key = generate_secure_api_key(credential_type.value)

        # Handle expiry: 0 means no expiry, None means no expiry, others are days
        if request.expiry is None or request.expiry == 0:
            expiry = None
        else:
            expiry = datetime.now(UTC) + timedelta(days=request.expiry)

        # Encrypt the API key for storage
        encrypted_api_key = await RSAHandler().encrypt(api_key)

        credential_data = BudCredentialCreate(
            name=request.name,
            user_id=user_id,
            project_id=request.project_id,
            expiry=expiry,
            encrypted_key=encrypted_api_key,
            max_budget=request.max_budget,
            model_budgets=request.model_budgets,
            credential_type=credential_type,
            ip_whitelist=request.ip_whitelist,
        )

        # Insert credential in to database
        credential_model = CredentialModel(**credential_data.model_dump())
        credential_model.hashed_key = CredentialModel.set_hashed_key(api_key)
        db_credential = await CredentialDataManager(self.session).create_credential(credential_model)
        logger.info(f"Credential inserted to database: {db_credential.id}")

        # Send notification for CLIENT_APP credential creation
        if credential_type == ApiCredentialTypeEnum.CLIENT_APP:
            try:
                notification = (
                    NotificationBuilder()
                    .set_content(
                        title="Client App API Key Created",
                        message=f"API key '{db_credential.name}' has been successfully created for your client app project",
                        status=NotificationStatus.COMPLETED,
                        icon="key",
                        result={
                            "credential_id": str(db_credential.id),
                            "credential_name": db_credential.name,
                            "project_id": str(db_credential.project_id),
                            "project_name": db_project.name,
                        },
                    )
                    .set_payload(
                        category=NotificationCategory.INAPP,
                        type="credential_creation",
                        source=app_settings.source_topic,
                    )
                    .set_notification_request(subscriber_ids=str(user_id))
                    .build()
                )
                await BudNotifyService().send_notification(notification)
                logger.info(f"Notification sent for CLIENT_APP credential creation: {db_credential.id}")
            except Exception as e:
                logger.error(f"Failed to send notification for CLIENT_APP credential creation: {e}")
                # Don't fail the credential creation if notification fails

        return db_credential

    async def update_proxy_cache(
        self, project_id: UUID, api_key: Optional[str] = None, expiry: Optional[datetime] = None
    ):
        """Update the proxy cache in Redis with the latest endpoints and adapters for a given project.

        This method collects all active endpoints and adapters associated with the specified project,
        maps their names to their IDs with additional metadata (model_id, project_id), and updates
        the Redis cache with this information. Now includes authentication metadata for API usage tracking.

        Args:
            api_key (str): The API key to associate with the project and its models.
            project_id (UUID): The unique identifier of the project whose endpoints and adapters are to be cached.

        Returns:
            None
        """
        keys_to_update = []
        if api_key is None:
            db_credentials, count = await CredentialDataManager(self.session).get_all_credentials(
                filters={"project_id": project_id}
            )
            for credential in db_credentials:
                # Decrypt API key from encrypted storage
                decrypted_key = await RSAHandler().decrypt(credential.encrypted_key)

                keys_to_update.append(
                    {
                        "api_key": decrypted_key,
                        "expiry": credential.expiry,
                        "credential_id": credential.id,
                        "user_id": credential.user_id,  # Using existing user_id field
                    }
                )
        else:
            # Fetch credential details for single key update using hashed key
            hashed_key = CredentialModel.set_hashed_key(api_key)
            credential = await CredentialDataManager(self.session).retrieve_credential_by_fields(
                {"hashed_key": hashed_key, "project_id": project_id}, missing_ok=True
            )
            keys_to_update.append(
                {
                    "api_key": api_key,
                    "expiry": expiry,
                    "credential_id": credential.id if credential else None,
                    "user_id": credential.user_id if credential else None,
                }
            )

        models = {}

        # Get endpoints with their model_id and project_id
        endpoints = await EndpointDataManager(self.session).get_all_running_endpoints(project_id)
        for endpoint in endpoints:
            models[endpoint.name] = {
                "endpoint_id": str(endpoint.id),
                "model_id": str(endpoint.model_id),
                "project_id": str(endpoint.project_id),
            }

        # Get adapters with their model_id and project_id
        adapters, _ = await AdapterDataManager(self.session).get_all_adapters_in_project(project_id)
        for adapter in adapters:
            # For adapters, endpoint_id refers to the adapter id itself
            models[adapter.name] = {
                "endpoint_id": str(adapter.id),
                "model_id": str(adapter.model_id),
                "project_id": str(project_id),  # Adapters don't have direct project_id, use the passed project_id
            }

        # Get standalone guardrail deployments (where endpoint_id is None)
        guardrail_deployments, _ = await GuardrailsDeploymentDataManager(self.session).get_all_deployments(
            offset=0,
            limit=1000,  # Get all deployments for the project
            filters={"project_id": project_id, "endpoint_id": None},
        )
        for deployment in guardrail_deployments:
            # Skip deleted deployments
            if deployment[0].status == GuardrailDeploymentStatusEnum.DELETED:
                continue
            # For standalone guardrail deployments, use deployment name as key
            # endpoint_id is the deployment id itself, model_id is the guardrail profile id
            models[deployment[0].name] = {
                "endpoint_id": str(deployment[0].id),
                "model_id": str(deployment[0].profile_id),  # Using profile_id as model_id
                "project_id": str(deployment[0].project_id),
            }

        # Get active prompts with ALL their versions for version-specific caching
        # This enables the gateway to look up endpoint_id and model_id for each prompt version
        prompt_versions_data = await PromptDataManager(self.session).get_all_active_prompt_versions_for_projects(
            [project_id]
        )
        for prompt, versions in prompt_versions_data:
            # Store each version with version-specific key
            for version in versions:
                versioned_key = f"prompt:{prompt.name}:v{version.version}"
                is_default = prompt.default_version_id == version.id

                version_data = {
                    "prompt_id": str(prompt.id),
                    "prompt_version_id": str(version.id),
                    "endpoint_id": str(version.endpoint_id),
                    "model_id": str(version.model_id),
                    "project_id": str(project_id),
                    "version": version.version,
                }
                models[versioned_key] = version_data

                # Also store default version without version suffix for backward compatibility
                # When a request doesn't specify a version, it should use the default
                if is_default:
                    default_key = f"prompt:{prompt.name}"
                    models[default_key] = {**version_data, "is_default": True}

        redis_service = RedisService()

        for key_info in keys_to_update:
            # Create cache data with models and metadata
            cache_data = models.copy()  # Copy to avoid modifying original

            # Always add metadata - even with None values for consistency
            cache_data["__metadata__"] = {
                "api_key_id": str(key_info["credential_id"]) if key_info.get("credential_id") else None,
                "user_id": str(key_info["user_id"]) if key_info.get("user_id") else None,
                "api_key_project_id": str(project_id),  # project_id is always available
            }

            ttl = None
            if key_info["expiry"]:
                ttl = int((key_info["expiry"] - datetime.now()).total_seconds())
                # Skip caching for expired credentials (negative or zero TTL)
                if ttl <= 0:
                    logger.warning(f"Skipping cache for credential with invalid TTL: {ttl}s")
                    logger.debug(
                        f"Credential cache skip details: credential_id={key_info.get('credential_id')}, "
                        f"expiry={key_info['expiry']}, ttl={ttl}s"
                    )
                    continue

            # Hash the API key before storing in Redis (consistent with database storage)
            hashed_key = CredentialModel.set_hashed_key(key_info["api_key"])
            # Store with flat structure including metadata using hashed key
            await redis_service.set(f"api_key:{hashed_key}", json.dumps(cache_data), ex=ttl)

        logger.info(f"Updated {len(keys_to_update)} api keys in proxy cache with metadata")

    async def get_credentials(
        self,
        current_user: UserModel,
        offset: int = 0,
        limit: int = 10,
        filters: Optional[Dict] = None,
        order_by: Optional[List[str]] = None,
        search: bool = False,
    ) -> List[CredentialDetails]:
        filters = filters or {}
        order_by = order_by or []

        # Set default credential_type filter based on logged-in user's type if not explicitly provided
        if "credential_type" not in filters:
            if current_user.user_type == UserTypeEnum.CLIENT:
                filters["credential_type"] = ApiCredentialTypeEnum.CLIENT_APP.value
            elif current_user.user_type == UserTypeEnum.ADMIN:
                filters["credential_type"] = ApiCredentialTypeEnum.ADMIN_APP.value

        db_credentials, count = await CredentialDataManager(self.session).get_all_credentials(
            offset, limit, filters, order_by, search
        )
        return await self.parse_credentials(db_credentials), count

    async def parse_credentials(
        self,
        db_credentials: List[CredentialModel],
    ) -> List[CredentialDetails]:
        # Store bud serve credentials in a list
        bud_serve_credentials = []

        # Iterate over credentials and append as per type
        for db_credential in db_credentials:
            if db_credential.project and db_credential.project.benchmark:
                continue
            # Use encrypted key directly
            encrypted_key = db_credential.encrypted_key

            bud_serve_credentials.append(
                CredentialDetails(
                    name=db_credential.name,
                    project=db_credential.project,
                    key=encrypted_key,  # Already encrypted
                    expiry=db_credential.expiry,
                    max_budget=db_credential.max_budget,
                    model_budgets=db_credential.model_budgets,
                    id=db_credential.id,
                    created_at=db_credential.created_at,
                    last_used_at=db_credential.last_used_at,
                    credential_type=db_credential.credential_type,
                    ip_whitelist=db_credential.ip_whitelist,
                )
            )
        return bud_serve_credentials

    async def delete_credential(self, credential_id: UUID, user_id: UUID, request: Optional[Request] = None) -> None:
        """Delete the credential from the database."""
        # Retrieve the credential from the database
        db_credential = await CredentialDataManager(self.session).retrieve_credential_by_fields(
            {"id": credential_id, "user_id": user_id}
        )

        if db_credential.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User does not have permission to update this credential",
            )

        # Get project name for audit log
        db_project = await ProjectDataManager(self.session).retrieve_project_by_fields(
            {"id": db_credential.project_id}, missing_ok=True
        )
        project_name = db_project.name if db_project else None

        # project_id = db_credential.project_id
        # # Check user permissions for viewing credentials
        # db_permission = await PermissionDataManager(self.session).retrieve_permission_by_fields({"user_id": user_id}, missing_ok=True)
        # user_scopes = db_permission.scopes_list if db_permission else []
        # if PermissionEnum.PROJECT_MANAGE.value not in user_scopes:
        #     # Check user has access to project
        #     await ProjectService(self.session).check_project_membership(project_id, user_id)

        # delete proxy cache related to this credential
        # Decrypt API key from encrypted storage
        api_key = await RSAHandler().decrypt(db_credential.encrypted_key)

        # Hash the API key before deleting from Redis (consistent with storage)
        hashed_key = CredentialModel.set_hashed_key(api_key)

        redis_service = RedisService()
        await redis_service.delete_keys_by_pattern(f"api_key:{hashed_key}*")

        # Store credential details before deletion
        credential_name = db_credential.name
        credential_expiry = str(db_credential.expiry) if db_credential.expiry else None

        # Delete the credential from the database
        await CredentialDataManager(self.session).delete_credential(db_credential)

        # Log successful credential deletion
        audit_details = {
            "credential_name": credential_name,
            "project_name": project_name,
            "expiry": credential_expiry,
        }
        if db_credential.max_budget is not None:
            audit_details["max_budget"] = db_credential.max_budget

        log_audit(
            session=self.session,
            action=AuditActionEnum.DELETE,
            resource_type=AuditResourceTypeEnum.API_KEY,
            resource_id=credential_id,
            resource_name=db_credential.name,
            user_id=user_id,
            details=audit_details,
            request=request,
            success=True,
        )

        return

    async def update_credential(
        self, data: CredentialUpdate, credential_id: UUID, user_id: UUID, request: Optional[Request] = None
    ) -> CredentialModel:
        """Update the OpenAI or HuggingFace credential in the database."""
        # Check if credential exists
        db_credential = await CredentialDataManager(self.session).retrieve_credential_by_fields({"id": credential_id})

        if db_credential.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User does not have permission to update this credential",
            )

        # project_id = db_credential.project_id

        # # Check user permissions for viewing credentials
        # db_permission = await PermissionDataManager(self.session).retrieve_permission_by_fields({"user_id": user_id}, missing_ok=True)
        # user_scopes = db_permission.scopes_list if db_permission else []
        # if PermissionEnum.PROJECT_MANAGE.value not in user_scopes:
        #     # Check user has access to project
        #     await ProjectService(self.session).check_project_membership(project_id, user_id)

        credential_update_data = data.model_dump(exclude_none=True)
        if credential_update_data.get("name", None):
            if await self._check_duplicate_credential(
                {"name": credential_update_data["name"], "project_id": db_credential.project_id}
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Credential already exists with the same name",
                )
            db_credential.name = credential_update_data["name"]

        if "expiry" in credential_update_data:
            # Handle expiry: 0 means no expiry, None means no expiry, others are days
            if data.expiry is None or data.expiry == 0:
                credential_update_data["expiry"] = None
            else:
                credential_update_data["expiry"] = datetime.now(UTC) + timedelta(days=data.expiry)

        if credential_update_data.get("max_budget", None):
            if (
                credential_update_data.get("model_budgets", None) is not None
                and db_credential.model_budgets
                and sum(db_credential.model_budgets.values()) > data.max_budget
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Sum of model budgets - {db_credential.model_budgets} - should not exceed max budget - {data.max_budget}",
                )
        elif db_credential.max_budget is not None:
            credential_update_data["max_budget"] = None

        if credential_update_data.get("model_budgets", None):
            if (
                credential_update_data.get("max_budget", None) is not None
                and db_credential.max_budget
                and sum(credential_update_data["model_budgets"].values()) > db_credential.max_budget
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"""Sum of model budgets - {credential_update_data["model_budgets"]}
                        should not exceed max budget - {db_credential.max_budget}""",
                )
            credential_update_data["model_budgets"] = {
                str(k): v for k, v in credential_update_data["model_budgets"].items()
            }

        # Validate IP whitelist if provided in update
        if credential_update_data.get("ip_whitelist", None):
            try:
                validate_ip_whitelist(credential_update_data["ip_whitelist"])
            except ValueError as e:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        # Capture previous state for audit
        previous_state = {
            "credential_name": db_credential.name,
            "expiry": str(db_credential.expiry) if db_credential.expiry else None,
        }
        if db_credential.max_budget is not None:
            previous_state["max_budget"] = db_credential.max_budget

        # Update the credential in the database
        db_credential = await CredentialDataManager(self.session).update_credential_by_fields(
            db_credential, credential_update_data
        )

        # Get project name for audit log
        db_project = await ProjectDataManager(self.session).retrieve_project_by_fields(
            {"id": db_credential.project_id}, missing_ok=True
        )
        project_name = db_project.name if db_project else None

        # Build new state for audit
        new_state = {
            "credential_name": db_credential.name,
            "expiry": str(db_credential.expiry) if db_credential.expiry else None,
        }
        if db_credential.max_budget is not None:
            new_state["max_budget"] = db_credential.max_budget

        # Log credential update
        log_audit(
            session=self.session,
            action=AuditActionEnum.UPDATE,
            resource_type=AuditResourceTypeEnum.API_KEY,
            resource_id=credential_id,
            resource_name=db_credential.name,
            user_id=user_id,
            previous_state=previous_state,
            new_state=new_state,
            details={
                "project_name": project_name,
            },
            request=request,
            success=True,
        )

        return db_credential

    async def validate_api_key(self, api_key: str, client_ip: Optional[str] = None) -> bool:
        """Validate an API key including expiry and IP whitelist checks.

        Args:
            api_key: The plain API key to validate
            client_ip: The client's IP address (optional, for IP whitelist validation)

        Returns:
            bool: True if the credential is valid, False otherwise
        """
        # Hash the API key to match what's stored in the database
        hashed_key = CredentialModel.set_hashed_key(api_key)
        return await self.is_credential_valid(hashed_key, client_ip)

    async def is_credential_valid(self, hashed_key: str, client_ip: Optional[str] = None) -> bool:
        """Validate a credential including expiry and IP whitelist checks.

        Args:
            hashed_key: The hashed API key to validate
            client_ip: The client's IP address (optional, for IP whitelist validation)

        Returns:
            bool: True if the credential is valid, False otherwise
        """
        try:
            # Check if credential exists in cache first
            redis_service = RedisService()
            cached_result = await redis_service.get(f"credential_valid:{hashed_key}")
            if cached_result is not None:
                # If cached and has IP whitelist, we still need to validate the IP
                if cached_result == "valid_no_ip_whitelist":
                    return True
                elif cached_result == "valid_with_ip_whitelist":
                    # Continue to IP validation below
                    pass
                else:
                    return False

            # Retrieve credential from database
            db_credential = await CredentialDataManager(self.session).retrieve_by_fields(
                CredentialModel, {"hashed_key": hashed_key}, missing_ok=True
            )

            if not db_credential:
                return False

            # Check if credential is expired
            if db_credential.expiry and db_credential.expiry < datetime.now(UTC):
                logger.info(f"Credential {db_credential.id} is expired")
                await redis_service.set(f"credential_valid:{hashed_key}", "invalid", ex=300)  # Cache for 5 minutes
                return False

            # Check IP whitelist if configured
            if db_credential.ip_whitelist and isinstance(db_credential.ip_whitelist, list):
                if not client_ip:
                    logger.warning(f"Credential {db_credential.id} requires IP whitelist but no client IP provided")
                    return False

                if client_ip not in db_credential.ip_whitelist:
                    logger.info(f"Client IP {client_ip} not in whitelist for credential {db_credential.id}")
                    return False

                # Valid credential with IP whitelist - cache briefly since IP might change
                await redis_service.set(f"credential_valid:{hashed_key}", "valid_with_ip_whitelist", ex=60)
            else:
                # Valid credential without IP whitelist - cache for longer
                await redis_service.set(f"credential_valid:{hashed_key}", "valid_no_ip_whitelist", ex=300)

            # Update last used timestamp
            await CredentialDataManager(self.session).update_credential_by_fields(
                db_credential, {"last_used_at": datetime.now(UTC)}
            )

            return True

        except Exception as e:
            logger.error(f"Error validating credential: {e}")
            return False

    async def update_credential_last_used(self, credential_usage: Dict[UUID, datetime]) -> Dict:
        """Update last_used_at timestamps for credentials.

        Args:
            credential_usage: Dictionary mapping credential IDs to last used timestamps

        Returns:
            Dictionary with update statistics
        """
        if not credential_usage:
            return {"updated_count": 0, "failed_count": 0, "errors": []}

        logger.info(f"Updating last_used_at for {len(credential_usage)} credentials")

        try:
            credential_dm = CredentialDataManager(self.session)
            result = await credential_dm.batch_update_last_used(credential_usage)

            logger.info(f"Successfully updated {result['updated_count']} credentials")
            return result

        except Exception as e:
            logger.error(f"Failed to update credential usage: {e}")
            return {"updated_count": 0, "failed_count": len(credential_usage), "errors": [str(e)]}

    async def fetch_recent_credential_usage(self, since_minutes: int = 10) -> Dict[UUID, datetime]:
        """Fetch recent credential usage data from budmetrics service.

        Args:
            since_minutes: How many minutes back to query for usage data

        Returns:
            Dictionary mapping credential IDs to their last used timestamps
        """
        try:
            # Calculate since timestamp
            since = datetime.now(UTC) - timedelta(minutes=since_minutes)

            # Prepare request payload
            payload = {"since": since.isoformat()}

            # Use Dapr service invocation to call budmetrics
            dapr_url = f"{app_settings.dapr_base_url}/v1.0/invoke/budmetrics/method/observability/credential-usage"

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(dapr_url, json=payload)
                response.raise_for_status()

                data = response.json()

                # Parse the response into a dictionary
                credential_usage = {}
                for item in data.get("credentials", []):
                    credential_id = UUID(item["credential_id"])
                    # Handle different datetime formats
                    last_used_str = item["last_used_at"]
                    if isinstance(last_used_str, str):
                        # Handle ISO format with Z or timezone
                        if last_used_str.endswith("Z"):
                            last_used_at = datetime.fromisoformat(last_used_str.replace("Z", "+00:00"))
                        else:
                            last_used_at = datetime.fromisoformat(last_used_str)
                    else:
                        # If it's already a datetime object or something else
                        last_used_at = last_used_str
                    credential_usage[credential_id] = last_used_at

                logger.info(f"Retrieved usage data for {len(credential_usage)} credentials")
                return credential_usage

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching credential usage: {e}")
            return {}
        except Exception as e:
            logger.error(f"Error fetching credential usage: {e}")
            return {}

    async def sync_credential_usage_from_metrics(self) -> Dict:
        """Sync credential usage data from budmetrics and update local database.

        Returns:
            Dictionary with sync statistics
        """
        try:
            # Fetch recent usage data from budmetrics
            usage_data = await self.fetch_recent_credential_usage(since_minutes=10)

            if not usage_data:
                return {"total_credentials": 0, "updated_count": 0, "failed_count": 0, "errors": []}

            # Update credentials with usage data
            result = await self.update_credential_last_used(usage_data)
            result["total_credentials"] = len(usage_data)

            logger.info(f"Credential usage sync complete: {result}")
            return result

        except Exception as e:
            logger.error(f"Failed to sync credential usage: {e}")
            return {"total_credentials": 0, "updated_count": 0, "failed_count": 0, "errors": [str(e)]}


class ProprietaryCredentialService(SessionMixin):
    async def add_credential(
        self, current_user_id: UUID, credential: ProprietaryCredentialRequest, request: Optional[Request] = None
    ) -> ProprietaryCredentialResponse:
        # Check duplicate credential exists with same name and type for user_id
        db_credential = await ProprietaryCredentialDataManager(self.session).retrieve_credential_by_fields(
            {"name": credential.name, "type": credential.type.value, "user_id": current_user_id}, missing_ok=True
        )

        # Raise error if credential already exists with same name and type
        if db_credential:
            error_msg = f"{credential.type.value.capitalize()} credential already exists with the same name, change name or update existing credential"
            logger.error(error_msg)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg,
            )

        # Encrypt credential and add in db
        db_credential = await self.add_encrypted_credential(credential, current_user_id)

        # Log successful proprietary credential creation
        log_audit(
            session=self.session,
            action=AuditActionEnum.CREATE,
            resource_type=AuditResourceTypeEnum.API_KEY,
            resource_id=db_credential.id,
            resource_name=db_credential.name,
            user_id=current_user_id,
            details={
                "credential_name": db_credential.name,
                "credential_type": db_credential.type.value,
            },
            request=request,
            success=True,
        )

        credential_response = ProprietaryCredentialResponse(
            name=db_credential.name,
            type=db_credential.type,
            id=db_credential.id,
            other_provider_creds=db_credential.other_provider_creds,
        )

        return credential_response

    async def add_encrypted_credential(
        self, credential: ProprietaryCredentialRequest, user_id: UUID
    ) -> ProprietaryCredentialModel:
        # Encrypt proprietary credentials
        if credential.other_provider_creds:
            for key, value in credential.other_provider_creds.items():
                credential.other_provider_creds[key] = await RSAHandler().encrypt(value)

        # get provider id
        if not credential.provider_id:
            db_provider = await ProviderDataManager(self.session).retrieve_by_fields(
                ProviderModel, {"type": credential.type.value}
            )
            credential.provider_id = db_provider.id

        # Insert credential in to database
        credential_model = ProprietaryCredentialModel(**credential.model_dump(), user_id=user_id)
        credential_model.type = credential_model.type.value
        db_credential = await ProprietaryCredentialDataManager(self.session).create_credential(credential_model)
        logger.info(f"Proprietary Credential inserted to database: {db_credential.id}")

        return db_credential

    async def get_all_credentials(
        self,
        offset: int = 0,
        limit: int = 10,
        filters: Optional[Dict] = None,
        order_by: Optional[List[str]] = None,
        search: bool = False,
    ) -> tuple[list[ProprietaryCredentialResponseList], int]:
        filters = filters or {}
        order_by = order_by or []

        num_of_endpoint_sort = None
        for field, direction in order_by:
            if field == "num_of_endpoints":
                num_of_endpoint_sort = (field, direction)
                order_by.remove(num_of_endpoint_sort)
                break

        if filters.get("type"):
            filters["type"] = filters["type"].value

        db_credentials, count = await ProprietaryCredentialDataManager(self.session).get_all_credentials(
            offset, limit, filters, order_by, search
        )
        cred_list = await self.parse_credentials(db_credentials)
        if num_of_endpoint_sort:
            cred_list.sort(key=lambda x: x.num_of_endpoints, reverse=num_of_endpoint_sort[1] == "desc")
        return cred_list, count

    async def parse_credentials(
        self,
        db_credentials: List[ProprietaryCredentialModel],
    ) -> List[ProprietaryCredentialResponseList]:
        # Parse credentials to a common format
        result = []

        # Iterate over credentials and append as per type
        for db_credential in db_credentials:
            # if db_credential.other_provider_creds:
            #     for key, value in db_credential.other_provider_creds.items():
            #         db_credential.other_provider_creds[key] = await RSAHandler().decrypt(value)
            running_endpoints = [
                endpoint for endpoint in db_credential.endpoints if endpoint.status == EndpointStatusEnum.RUNNING
            ]
            result.append(
                ProprietaryCredentialResponseList(
                    name=db_credential.name,
                    type=db_credential.type,
                    other_provider_creds=db_credential.other_provider_creds,
                    id=db_credential.id,
                    created_at=db_credential.created_at,
                    num_of_endpoints=len(running_endpoints),
                    provider_icon=db_credential.provider.icon,
                )
            )

        return result

    async def update_credential(
        self,
        credential_id: UUID,
        data: ProprietaryCredentialUpdate,
        current_user_id: UUID,
        request: Optional[Request] = None,
    ) -> ProprietaryCredentialResponse:
        # Check if credential exists
        db_credential = await ProprietaryCredentialDataManager(self.session).retrieve_credential_by_fields(
            {"id": credential_id}
        )

        if db_credential.user_id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User does not have permission to update this credential",
            )

        # Check data type
        if data.type != db_credential.type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Credential type cannot be changed from {db_credential.type} to {data.type.value}",
            )

        proprietary_update_data = data.model_dump(exclude_none=True, exclude={"type"})
        # Handle name
        if proprietary_update_data.get("name", None):
            # Check duplicate credential exists with same name and type for user_id
            db_credential_by_name = await ProprietaryCredentialDataManager(self.session).retrieve_credential_by_fields(
                {"name": data.name, "type": db_credential.type, "user_id": current_user_id}, missing_ok=True
            )

            # Raise error if credential already exists with same name and type
            if db_credential_by_name:
                error_msg = f"Update failed : {db_credential.type} credential already exists with the same name"
                logger.error(error_msg)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error_msg,
                )

        if proprietary_update_data.get("other_provider_creds", None) and data.other_provider_creds:
            # if proprietary_update_data has other_provider_creds,
            # then data will also have attribute other_provider_creds
            # the data.other_provider_creds clause is added to resolve mypy error
            for key, value in data.other_provider_creds.items():
                proprietary_update_data["other_provider_creds"][key] = await RSAHandler().encrypt(value)

        # Handle endpoint
        if proprietary_update_data.get("endpoint_id", None):
            credential_endpoints = db_credential.endpoints
            endpoint_id = data.endpoint_id
            del proprietary_update_data["endpoint_id"]

            # check if endpoint exists in credential endpoints
            for endpoint in credential_endpoints:
                if endpoint.id == endpoint_id:
                    break
            else:
                # Check if endpoint exists
                db_endpoint = await EndpointDataManager(self.session).retrieve_endpoint_by_fields({"id": endpoint_id})
                project_id = db_endpoint.project_id
                # Check user has authority to create credential for project
                db_permission = await PermissionDataManager(self.session).retrieve_permission_by_fields(
                    {"user_id": current_user_id}, missing_ok=True
                )
                global_user_scopes = db_permission.scopes_list if db_permission else []
                if PermissionEnum.PROJECT_MANAGE.value not in global_user_scopes:
                    db_project_permission = await ProjectPermissionDataManager(
                        self.session
                    ).retrieve_project_permission_by_fields(
                        {"user_id": current_user_id, "project_id": project_id},
                        missing_ok=True,
                    )
                    project_user_scopes = db_project_permission.scopes_list if db_project_permission else []

                    # Check user has access to endpoint
                    if PermissionEnum.ENDPOINT_MANAGE.value not in project_user_scopes:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="User does not have permission to update credential for this endpoint",
                        )
                db_credential.endpoints.append(db_endpoint)

        # Capture previous state for audit
        previous_state = {
            "credential_name": db_credential.name,
        }

        # Update the credential in the database
        db_credential = await ProprietaryCredentialDataManager(self.session).update_credential_by_fields(
            db_credential, proprietary_update_data
        )

        # Log credential update
        log_audit(
            session=self.session,
            action=AuditActionEnum.UPDATE,
            resource_type=AuditResourceTypeEnum.API_KEY,
            resource_id=credential_id,
            resource_name=db_credential.name,
            user_id=current_user_id,
            previous_state=previous_state,
            new_state={
                "credential_name": db_credential.name,
            },
            details={
                "credential_type": db_credential.type.value,
            },
            request=request,
            success=True,
        )

        return db_credential

    async def delete_credential(self, credential_id: UUID, current_user_id: UUID, request: Optional[Request] = None):
        """Delete the proprietary credential from the database."""
        # Retrieve the credential from the database
        db_credential = await ProprietaryCredentialDataManager(self.session).retrieve_credential_by_fields(
            {"id": credential_id}
        )

        if db_credential.user_id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User does not have permission to delete this credential",
            )

        endpoints = db_credential.endpoints
        if endpoints:
            project_names = [endpoint.project.name for endpoint in endpoints]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"""Credential is associated with deployed models in the below projects :
                {", ".join(project_names)}.
                Please delete the deployed models first or link other credentials to those models for deleting this credential""",
            )

        # Store credential details before deletion
        credential_name = db_credential.name
        credential_type = db_credential.type.value

        # Delete the credential from the database
        await ProprietaryCredentialDataManager(self.session).delete_credential(db_credential)

        # Log successful credential deletion
        log_audit(
            session=self.session,
            action=AuditActionEnum.DELETE,
            resource_type=AuditResourceTypeEnum.API_KEY,
            resource_id=credential_id,
            resource_name=credential_name,
            user_id=current_user_id,
            details={
                "credential_name": credential_name,
                "credential_type": credential_type,
            },
            request=request,
            success=True,
        )

    async def get_credential_details(
        self, credential_id: UUID, detailed_view: bool = False
    ) -> Union[ProprietaryCredentialModel, ProprietaryCredentialDetailedView]:
        """Get details of a proprietary credential."""
        db_credential = await ProprietaryCredentialDataManager(self.session).retrieve_credential_by_fields(
            {"id": credential_id}
        )
        # Decrypt proprietary credentials
        if not detailed_view and db_credential.other_provider_creds:
            for key, value in db_credential.other_provider_creds.items():
                db_credential.other_provider_creds[key] = await RSAHandler().decrypt(value)
        if detailed_view:
            endpoints = []
            for endpoint in db_credential.endpoints:
                if endpoint.status == EndpointStatusEnum.RUNNING.value:
                    endpoints.append(
                        {
                            "id": str(endpoint.id),
                            "name": endpoint.name,
                            "status": endpoint.status.value,
                            "project_info": {
                                "id": str(endpoint.project.id),
                                "name": endpoint.project.name,
                            },
                            "model_info": {
                                "id": str(endpoint.model.id),
                                "name": endpoint.model.name,
                                "icon": endpoint.model.provider.icon,
                                "modality": endpoint.model.modality,  # This is already a list of strings
                            },
                            "created_at": endpoint.created_at,
                        }
                    )
            return ProprietaryCredentialDetailedView(
                name=db_credential.name,
                type=db_credential.type,
                other_provider_creds=db_credential.other_provider_creds,
                id=db_credential.id,
                created_at=db_credential.created_at,
                endpoints=endpoints,
                num_of_endpoints=len(db_credential.endpoints),
                provider_icon=db_credential.provider.icon,
            )
        return db_credential


class ClusterProviderService(SessionMixin):
    """ClusterProviderService is a service class that provides cluster-related operations."""

    async def create_provider_credential(self, req: CloudProvidersCreateRequest, current_user_id: UUID) -> None:
        """Create a new credential for a provider.

        Args:
            req: CloudProvidersCreateRequest containing provider_id and credential_values

        Raises:
            ValueError: If provider is not found or required fields are missing
            HTTPException: If there are validation errors
        """
        try:
            # Convert provider_id string to UUID if needed
            provider_id = req.provider_id
            if not isinstance(provider_id, uuid.UUID):
                try:
                    provider_id = uuid.UUID(provider_id)
                except ValueError:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid provider_id format: {provider_id}"
                    ) from None

            # Get the provider from the database
            provider = await CloudProviderDataManager(self.session).retrieve_by_fields(
                CloudProviders, {"id": provider_id}
            )

            # Validate the provider
            if not provider:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail=f"Provider with id {provider_id} not found"
                )

            # Handle schema_definition which might be a dict or a JSON string
            schema = self._get_schema_definition(provider.schema_definition)

            # Get the required fields from the schema
            required_fields = schema.get("required", [])

            # Validate the required fields
            for field in required_fields:
                if field not in req.credential_values:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Required field '{field}' is missing in the credential values",
                    )

            # Encrypt credential values before saving
            encrypted_credential_values = {}
            for key, value in req.credential_values.items():
                # Encrypt each credential value
                encrypted_credential_values[key] = await RSAHandler().encrypt(str(value))

            # Save the credential values
            cloud_credential = CloudCredentials(
                user_id=current_user_id,
                provider_id=provider_id,
                encrypted_credential=encrypted_credential_values,  # Store encrypted version only
                credential_name=req.credential_name,
            )
            await CloudProviderDataManager(self.session).insert_one(cloud_credential)

            logger.debug(f"Created credential for provider {cloud_credential.id}")
        except HTTPException:
            # Re-raise HTTP exceptions without additional logging
            raise
        except Exception as e:
            logger.error(f"Failed to create credential for provider {req.provider_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create credential: {str(e)}"
            ) from None

    def _get_schema_definition(self, schema_definition: Union[Dict[str, Any], str]) -> Dict[str, Any]:
        """Parse the schema_definition which could be a dict or a JSON string.

        Args:
            schema_definition: The schema definition as either a dict or JSON string

        Returns:
            Dict containing the parsed schema

        Raises:
            ValueError: If the schema_definition is invalid
        """
        if isinstance(schema_definition, dict):
            return schema_definition
        elif isinstance(schema_definition, str):
            try:
                return json.loads(schema_definition)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid schema_definition JSON: {e}")
                raise ValueError(f"Invalid schema_definition: {e}")
        else:
            logger.error(f"Unexpected schema_definition type: {type(schema_definition)}")
            return {}  # Return empty dict as fallback

    async def get_provider_regions(self, unique_id: str) -> List[Dict[str, Any]]:
        """Get the regions supported by a specific cloud provider.

        Args:
            provider: The cloud provider entity

        Returns:
            List of regions as dictionaries with at least 'id' and 'name' keys
        """
        provider_regions = {
            "aws": [
                {"id": "us-east-1", "name": "US East (N. Virginia)"},
                {"id": "us-east-2", "name": "US East (Ohio)"},
                {"id": "us-west-1", "name": "US West (N. California)"},
                {"id": "us-west-2", "name": "US West (Oregon)"},
                {"id": "ca-central-1", "name": "Canada (Central)"},
                {"id": "ca-west-1", "name": "Canada West (Calgary)"},
                {"id": "sa-east-1", "name": "South America (São Paulo)"},
                {"id": "eu-west-1", "name": "Europe (Ireland)"},
                {"id": "eu-west-2", "name": "Europe (London)"},
                {"id": "eu-west-3", "name": "Europe (Paris)"},
                {"id": "eu-central-1", "name": "Europe (Frankfurt)"},
                {"id": "eu-north-1", "name": "Europe (Stockholm)"},
                {"id": "eu-south-1", "name": "Europe (Milan)"},
                {"id": "eu-central-2", "name": "Europe (Zurich)"},
                {"id": "eu-south-2", "name": "Europe (Spain)"},
                {"id": "ap-northeast-1", "name": "Asia Pacific (Tokyo)"},
                {"id": "ap-northeast-2", "name": "Asia Pacific (Seoul)"},
                {"id": "ap-northeast-3", "name": "Asia Pacific (Osaka)"},
                {"id": "ap-southeast-1", "name": "Asia Pacific (Singapore)"},
                {"id": "ap-southeast-2", "name": "Asia Pacific (Sydney)"},
                {"id": "ap-east-1", "name": "Asia Pacific (Hong Kong)"},
                {"id": "ap-south-1", "name": "Asia Pacific (Mumbai)"},
                {"id": "ap-southeast-3", "name": "Asia Pacific (Jakarta)"},
                {"id": "ap-southeast-4", "name": "Asia Pacific (Melbourne)"},
                {"id": "ap-south-2", "name": "Asia Pacific (Hyderabad)"},
                {"id": "ap-southeast-5", "name": "Asia Pacific (Malaysia)"},
                {"id": "me-south-1", "name": "Middle East (Bahrain)"},
                {"id": "me-central-1", "name": "Middle East (UAE)"},
                {"id": "il-central-1", "name": "Israel (Tel Aviv)"},
                {"id": "af-south-1", "name": "Africa (Cape Town)"},
                {"id": "cn-north-1", "name": "China (Beijing)"},
                {"id": "cn-northwest-1", "name": "China (Ningxia)"},
                {"id": "us-gov-west-1", "name": "AWS GovCloud (US-West)"},
                {"id": "us-gov-east-1", "name": "AWS GovCloud (US-East)"},
            ],
            "azure": [
                {"id": "eastus", "name": "East US"},
                {"id": "eastus2", "name": "East US 2"},
                {"id": "southcentralus", "name": "South Central US"},
                {"id": "westus", "name": "West US"},
                {"id": "westus2", "name": "West US 2"},
                {"id": "westus3", "name": "West US 3"},
                {"id": "centralus", "name": "Central US"},
                {"id": "canadacentral", "name": "Canada Central"},
                {"id": "canadaeast", "name": "Canada East"},
                {"id": "brazilsouth", "name": "Brazil South"},
                {"id": "uksouth", "name": "UK South"},
                {"id": "ukwest", "name": "UK West"},
                {"id": "francecentral", "name": "France Central"},
                {"id": "francesouth", "name": "France South"},
                {"id": "germanywestcentral", "name": "Germany West Central"},
                {"id": "germanynorth", "name": "Germany North"},
                {"id": "switzerlandnorth", "name": "Switzerland North"},
                {"id": "switzerlandwest", "name": "Switzerland West"},
                {"id": "norwayeast", "name": "Norway East"},
                {"id": "norwaywest", "name": "Norway West"},
                {"id": "australiaeast", "name": "Australia East"},
                {"id": "australiasoutheast", "name": "Australia Southeast"},
                {"id": "australiacentral", "name": "Australia Central"},
                {"id": "australiacentral2", "name": "Australia Central 2"},
                {"id": "japaneast", "name": "Japan East"},
                {"id": "japanwest", "name": "Japan West"},
                {"id": "koreacentral", "name": "Korea Central"},
                {"id": "koreasouth", "name": "Korea South"},
                {"id": "southeastasia", "name": "Southeast Asia"},
                {"id": "eastasia", "name": "East Asia"},
                {"id": "centralindia", "name": "Central India"},
                {"id": "southindia", "name": "South India"},
                {"id": "westindia", "name": "West India"},
                {"id": "uaenorth", "name": "UAE North"},
                {"id": "uaecentral", "name": "UAE Central"},
                {"id": "southafricanorth", "name": "South Africa North"},
                {"id": "southafricawest", "name": "South Africa West"},
                {"id": "qatarcentral", "name": "Qatar Central"},
                {"id": "israelcentral", "name": "Israel Central"},
            ],
        }

        # Match based on the unique_id
        if unique_id in provider_regions:
            return provider_regions[unique_id]

        return []
