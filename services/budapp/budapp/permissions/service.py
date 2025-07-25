from typing import List

from fastapi import status

from budapp.auth.schemas import DeletePermissionRequest, ResourceCreate
from budapp.commons import logging
from budapp.commons.config import app_settings
from budapp.commons.constants import PermissionEnum, ProjectStatusEnum, UserStatusEnum
from budapp.commons.db_utils import SessionMixin
from budapp.commons.exceptions import ClientException
from budapp.commons.keycloak import KeycloakManager
from budapp.permissions.schemas import CheckUserResourceScope, PermissionList
from budapp.user_ops.crud import UserDataManager
from budapp.user_ops.models import Tenant, TenantClient
from budapp.user_ops.models import User as UserModel
from budapp.user_ops.schemas import TenantClientSchema

from ..project_ops.crud import ProjectDataManager
from .schemas import PermissionList, ProjectPermissionUpdate, UserProjectPermission


logger = logging.get_logger(__name__)


class PermissionService(SessionMixin):
    """Keycloak Permission Service."""

    async def create_resource_permission_by_user(self, user: UserModel, resource: ResourceCreate) -> None:
        """Create a resource permission for a user."""
        # Get the default tenant
        tenant = await UserDataManager(self.session).retrieve_by_fields(
            Tenant, {"realm_name": app_settings.default_realm_name}, missing_ok=True
        )

        # Get the default tenant client
        tenant_client = await UserDataManager(self.session).retrieve_by_fields(
            TenantClient, {"tenant_id": tenant.id}, missing_ok=True
        )

        logger.debug(f"::PERMISSION:: Tenant client: {tenant_client.client_named_id}")

        if not tenant_client:
            raise ClientException("Tenant client not found")

        try:
            # Keycloak Manager
            kc_manager = KeycloakManager()
            _ = await kc_manager.create_resource_with_permissions(
                realm_name=app_settings.default_realm_name,
                client_id=str(tenant_client.client_id),
                resource=resource,
                user_auth_id=user.auth_id,
            )
        except Exception as e:
            logger.error(f"Error creating resource permission: {e}")
            raise

    async def delete_permission_for_resource(self, resource: DeletePermissionRequest) -> None:
        """Delete a resource permission for a user."""
        # Get the default tenant
        tenant = await UserDataManager(self.session).retrieve_by_fields(
            Tenant, {"realm_name": app_settings.default_realm_name}, missing_ok=True
        )

        tenant_client = await UserDataManager(self.session).retrieve_by_fields(
            TenantClient, {"tenant_id": tenant.id}, missing_ok=True
        )

        if not tenant_client:
            raise ClientException("Tenant client not found")

        try:
            # Keycloak Manager
            kc_manager = KeycloakManager()
            _ = await kc_manager.delete_permission_for_resource(
                realm_name=app_settings.default_realm_name,
                client_id=str(tenant_client.client_id),
                resource_type=resource.resource_type,
                resource_id=resource.resource_id,
                delete_resource=resource.delete_resource,
            )
        except Exception as e:
            logger.error(f"Error deleting resource permission: {e}")
            raise

    async def check_resource_permission_by_user(self, user: UserModel, payload: CheckUserResourceScope) -> bool:
        """Check if a user has a resource permission."""
        logger.debug(f"::PERMISSION::Checking permissions for user: {user.raw_token}")

        # if user.is_superuser:
        #     return True

        # Keycloak Manager
        keycloak_manager = KeycloakManager()

        # TenantClientSchema
        realm_name = app_settings.default_realm_name
        tenant = await UserDataManager(self.session).retrieve_by_fields(
            Tenant, {"realm_name": realm_name}, missing_ok=True
        )
        tenant_client = await UserDataManager(self.session).retrieve_by_fields(
            TenantClient, {"tenant_id": tenant.id}, missing_ok=True
        )

        # Credentials
        credentials = TenantClientSchema(
            id=tenant_client.id,
            client_named_id=tenant_client.client_named_id,
            client_id=tenant_client.client_id,
            client_secret=tenant_client.client_secret,
        )

        try:
            result = await keycloak_manager.get_user_roles_and_permissions(
                user.auth_id,
                realm_name,
                tenant_client.client_id,
                credentials,
                user.raw_token,
            )

            logger.debug(f"::KEYCLOAK::User {user.auth_id} roles and permissions: {result}")

            if payload.entity_id is None:
                # Global Permission
                for permission in result["permissions"]:
                    if (
                        permission["rsname"] == f"module_{payload.resource_type}"
                        and payload.scope in permission["scopes"]
                    ):
                        return True
            else:
                # Individual Resource Permission
                for permission in result["permissions"]:
                    if (
                        permission["rsname"] == f"URN::{payload.resource_type}::{payload.entity_id}"
                        and payload.scope in permission["scopes"]
                    ):
                        return True

            return False
        except Exception as e:
            logger.error(f"Error checking resource permission: {e}")
            raise

    async def remove_user_from_project_permissions(self, user: UserModel, project_id: str) -> None:
        """Remove a user from a project's permissions in Keycloak.

        This method removes the user's access to a specific project by removing
        their policy from all project permissions.

        Args:
            user: The user model to remove from the project
            project_id: The project UUID
        """
        # Get the default tenant
        tenant = await UserDataManager(self.session).retrieve_by_fields(
            Tenant, {"realm_name": app_settings.default_realm_name}, missing_ok=True
        )

        if not tenant:
            raise ClientException("Default tenant not found")

        # Get the default tenant client
        tenant_client = await UserDataManager(self.session).retrieve_by_fields(
            TenantClient, {"tenant_id": tenant.id}, missing_ok=True
        )

        if not tenant_client:
            raise ClientException("Tenant client not found")

        try:
            # Use KeycloakManager to remove user policy from project permissions
            kc_manager = KeycloakManager()
            await kc_manager.remove_user_policy_from_resource_permissions(
                realm_name=app_settings.default_realm_name,
                client_id=str(tenant_client.client_id),
                resource_type="project",
                resource_id=str(project_id),
                user_auth_id=str(user.auth_id),
            )
            logger.debug(f"Removed user {user.auth_id} from project {project_id} permissions")
        except Exception as e:
            logger.error(f"Error removing user from project permissions: {e}")
            raise ClientException("Failed to remove user from project permissions")

    async def add_user_to_project_permissions(
        self, user: UserModel, project_id: str, scopes: List[str] = None
    ) -> None:
        """Add a user to an existing project's permissions in Keycloak.

        This method is used when adding users to an existing project. The project
        resource and permissions already exist in Keycloak, so we only need to
        associate the user's policy with them.

        Args:
            user: The user model to add to the project
            project_id: The project UUID
            scopes: List of scopes to grant (defaults to ["view", "manage"])
        """
        # Get the default tenant
        tenant = await UserDataManager(self.session).retrieve_by_fields(
            Tenant, {"realm_name": app_settings.default_realm_name}, missing_ok=True
        )

        if not tenant:
            raise ClientException("Default tenant not found")

        # Get the default tenant client
        tenant_client = await UserDataManager(self.session).retrieve_by_fields(
            TenantClient, {"tenant_id": tenant.id}, missing_ok=True
        )

        if not tenant_client:
            raise ClientException("Tenant client not found")

        try:
            # Extract actual scopes from format like "endpoint:view" -> "view"
            if scopes:
                extracted_scopes = []
                for scope in scopes:
                    if ":" in scope:
                        # Split by ':' and take the last part (view/manage)
                        extracted_scopes.append(scope.split(":")[-1])
                    else:
                        # If no ':', use as is
                        extracted_scopes.append(scope)

                # Remove duplicates and filter to valid scopes
                valid_scopes = {"view", "manage"}
                keycloak_scopes = list(set(extracted_scopes) & valid_scopes)

                if not keycloak_scopes:
                    logger.warning(f"No valid scopes found in {scopes}, using defaults")
                    keycloak_scopes = ["view", "manage"]

                # If user has manage permission, ensure they also have view permission
                if "manage" in keycloak_scopes and "view" not in keycloak_scopes:
                    keycloak_scopes.append("view")
            else:
                keycloak_scopes = ["view", "manage"]

            # Use KeycloakManager to add user policy to existing project permissions
            kc_manager = KeycloakManager()
            await kc_manager.add_user_policy_to_resource_permissions(
                realm_name=app_settings.default_realm_name,
                client_id=str(tenant_client.client_id),
                resource_type="project",
                resource_id=str(project_id),
                user_auth_id=str(user.auth_id),
                scopes=keycloak_scopes,
            )
            logger.debug(
                f"Added user {user.auth_id} to project {project_id} permissions with scopes {keycloak_scopes}"
            )
        except Exception as e:
            logger.error(f"Error adding user to project permissions: {e}")
            raise ClientException("Failed to add user to project permissions")

    async def update_global_permissions(self, user_id: str, permissions: List[PermissionList]) -> List[PermissionList]:
        """Update global permissions for a specific user.

        Args:
            user_id: The ID of the user to update permissions for
            permissions: List of permissions to update

        Returns:
            List[PermissionList]: Updated list of permissions
        """
        # Get the default tenant
        tenant = await UserDataManager(self.session).retrieve_by_fields(
            Tenant, {"realm_name": app_settings.default_realm_name}, missing_ok=True
        )

        if not tenant:
            raise ClientException("Default tenant not found")

        # Get the default tenant client
        tenant_client = await UserDataManager(self.session).retrieve_by_fields(
            TenantClient, {"tenant_id": tenant.id}, missing_ok=True
        )

        if not tenant_client:
            raise ClientException("Tenant client not found")

        try:
            # Get the user - only retrieve active users
            db_user = await UserDataManager(self.session).retrieve_by_fields(
                UserModel, {"id": user_id, "status": UserStatusEnum.ACTIVE}
            )

            # Restrict update permission on super user
            if db_user.is_superuser:
                raise ClientException(
                    "Cannot update permissions for super user", status_code=status.HTTP_400_BAD_REQUEST
                )

            # Validate permissions against PermissionEnum
            valid_permissions = PermissionEnum.get_global_permissions()
            for permission in permissions:
                if permission.name not in valid_permissions:
                    raise ClientException(
                        f"Invalid permission: {permission.name}.", status_code=status.HTTP_400_BAD_REQUEST
                    )

            # Process permissions to add implicit view permissions for manage permissions
            permission_dict = {p.name: p for p in permissions}
            manage_to_view_mapping = PermissionEnum.get_manage_to_view_mapping()

            # Add implicit view permissions for manage permissions
            for permission in permissions:
                if permission.has_permission and permission.name in manage_to_view_mapping:
                    view_permission_name = manage_to_view_mapping[permission.name]
                    # Explicitly upsert the view permission
                    permission_dict[view_permission_name] = PermissionList(
                        name=view_permission_name, has_permission=True
                    )
                    logger.debug("Upsert %s for %s", view_permission_name, permission.name)

            processed_permissions = list(permission_dict.values())

            # Use KeycloakManager to update permissions
            kc_manager = KeycloakManager()
            await kc_manager.update_user_global_permissions(
                user_auth_id=db_user.auth_id,
                permissions=[p.model_dump() for p in processed_permissions],
                realm_name=app_settings.default_realm_name,
                client_id=str(tenant_client.client_id),
            )

            logger.info(f"Updated global permissions for user {user_id}")

            # Return the updated permissions
            return processed_permissions

        except ClientException:
            raise
        except Exception as e:
            logger.error(f"Error updating global permissions: {str(e)}")
            raise ClientException(
                "Failed to update global permissions", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    async def update_project_permissions(self, user_project_permissions: List[ProjectPermissionUpdate]) -> None:
        """Update project permissions for a specific user.

        Args:
            user_project_permissions: List of user project permissions to update
        """
        # Collect all user ids from request body
        user_ids = [permission.user_id for permission in user_project_permissions]
        db_users = await UserDataManager(self.session).get_active_invited_users_by_ids(user_ids)
        db_user_ids = [db_user.id for db_user in db_users]

        if len(set(user_ids)) != len(set(db_user_ids)):
            logger.debug(f"Invalid user ids in: {user_ids}")
            raise ClientException("Invalid user ids found", status_code=status.HTTP_400_BAD_REQUEST)

        # NOTE: Cannot update permissions for superuser
        for db_user in db_users:
            if db_user.is_superuser:
                logger.debug(f"Cannot modify permissions for superuser: {db_user.id}")
                raise ClientException(
                    "Cannot modify permissions for superuser.", status_code=status.HTTP_400_BAD_REQUEST
                )

        # validate project ids
        project_ids = [permission.project_id for permission in user_project_permissions]

        db_projects = await ProjectDataManager(self.session).get_active_projects_by_ids(project_ids)
        db_project_ids = [db_project.id for db_project in db_projects]

        if len(set(project_ids)) != len(set(db_project_ids)):
            logger.debug(f"Invalid project ids in: {project_ids}")
            raise ClientException("Invalid project ids found", status_code=status.HTTP_400_BAD_REQUEST)

        all_project_scopes = PermissionEnum.get_project_level_scopes()
        # protected_project_scopes = PermissionEnum.get_project_protected_scopes()
        data = []

        # Validate individual user input of project level permission scopes
        for user_project_permission in user_project_permissions:
            logger.debug(
                f"Validating permissions of user {user_project_permission.user_id} in project {user_project_permission.project_id}"
            )
            user_update_scopes = [
                permission.name for permission in user_project_permission.permissions if permission.has_permission
            ]

            # Check scope string is valid
            for scope in user_update_scopes:
                if scope not in all_project_scopes:
                    logger.debug(f"Invalid scope: {scope}")
                    raise ClientException(f"Invalid scope: {scope}", status_code=status.HTTP_400_BAD_REQUEST)

            if len(user_update_scopes) != len(set(user_update_scopes)):
                logger.debug(f"Duplicate scopes found: {user_update_scopes}")
                raise ClientException("Duplicate scopes found", status_code=status.HTTP_400_BAD_REQUEST)

            # missing_scopes = set(protected_project_scopes) - set(user_update_scopes)

            # if missing_scopes:
            #     missing_scopes_str = ", ".join(missing_scopes)
            #     raise ClientException(
            #         f"Missing required scopes: {missing_scopes_str}", status_code=status.HTTP_400_BAD_REQUEST
            #     )

            data.append(
                {
                    "user_id": user_project_permission.user_id,
                    "project_id": user_project_permission.project_id,
                    "scopes": user_update_scopes,
                }
            )

        # Map db user instance to user id key dict. (Auth id required in project permission table)
        db_user_instances = {str(db_user.id): db_user for db_user in db_users}

        # After validation, performing Keycloak updates
        for update_entry in data:
            user_id_str = str(update_entry["user_id"])
            db_user = db_user_instances[user_id_str]
            project_id = update_entry["project_id"]
            project_id_str = str(project_id)
            scopes = update_entry["scopes"]

            # Check if user is already a member of the project using association table
            is_project_member = await ProjectDataManager(self.session).is_user_in_project(
                user_id=db_user.id, project_id=project_id
            )

            # Process scopes to extract actual Keycloak scopes and add implicit view permissions
            keycloak_scopes = []
            for scope in scopes:
                # Extract actual scope from format like "endpoint:view" -> "view"
                actual_scope = scope.split(":")[-1] if ":" in scope else scope

                if actual_scope in ["view", "manage"]:
                    keycloak_scopes.append(actual_scope)

            # Ensure view permission is included if manage is present
            if "manage" in keycloak_scopes and "view" not in keycloak_scopes:
                keycloak_scopes.append("view")

            # Remove duplicates
            keycloak_scopes = list(set(keycloak_scopes))

            # Handle different scenarios
            if not keycloak_scopes:
                # No scopes provided
                if is_project_member:
                    # Remove user from project using ProjectService
                    logger.info(f"Removing user {db_user.id} from project {project_id}")
                    from ..project_ops.services import ProjectService

                    project_service = ProjectService(self.session)
                    await project_service.remove_users_from_project(
                        project_id=project_id,
                        user_ids=[db_user.id],
                        remove_credential=True,  # Remove credentials when removing from project
                    )
                    # Note: remove_users_from_project already handles Keycloak permission removal
                else:
                    # User not in project and no scopes - nothing to do
                    logger.debug(f"User {db_user.id} not in project {project_id} and no scopes provided - skipping")
                    continue
            else:
                # Scopes provided
                if not is_project_member:
                    # Add user to project using ProjectService
                    logger.info(f"Adding user {db_user.id} to project {project_id}")
                    from ..project_ops.schemas import ProjectUserAdd
                    from ..project_ops.services import ProjectService

                    project_service = ProjectService(self.session)
                    add_user_data = ProjectUserAdd(
                        user_id=db_user.id,
                        scopes=scopes,  # Pass the original scopes (e.g., ["endpoint:view", "endpoint:manage"])
                    )
                    await project_service.add_users_to_project(project_id=project_id, users_to_add=[add_user_data])
                    # Note: add_users_to_project already handles Keycloak permission setup
                else:
                    # User already in project, just update permissions in Keycloak
                    logger.debug(
                        f"Updating permissions for user {db_user.id} on project {project_id} with scopes: {keycloak_scopes}"
                    )
                    await self._update_user_project_permissions_in_keycloak(db_user, project_id_str, keycloak_scopes)

        return

    async def _update_user_project_permissions_in_keycloak(
        self, user: UserModel, project_id: str, scopes: List[str]
    ) -> None:
        """Update user permissions for a specific project in Keycloak.

        This method handles both adding and removing permissions based on the provided scopes.
        If scopes list is empty, all permissions for the user on this project will be removed.

        Args:
            user: The user model
            project_id: The project UUID as string
            scopes: List of scopes to grant (e.g., ["view", "manage"])
        """
        # Get the default tenant
        tenant = await UserDataManager(self.session).retrieve_by_fields(
            Tenant, {"realm_name": app_settings.default_realm_name}, missing_ok=True
        )

        if not tenant:
            raise ClientException("Default tenant not found")

        # Get the default tenant client
        tenant_client = await UserDataManager(self.session).retrieve_by_fields(
            TenantClient, {"tenant_id": tenant.id}, missing_ok=True
        )

        if not tenant_client:
            raise ClientException("Tenant client not found")

        try:
            kc_manager = KeycloakManager()

            # First, remove user from all project permissions
            await kc_manager.remove_user_policy_from_resource_permissions(
                realm_name=app_settings.default_realm_name,
                client_id=str(tenant_client.client_id),
                resource_type="project",
                resource_id=str(project_id),
                user_auth_id=str(user.auth_id),
            )

            # Then, if there are scopes to add, add the user back with new permissions
            if scopes:
                await kc_manager.add_user_policy_to_resource_permissions(
                    realm_name=app_settings.default_realm_name,
                    client_id=str(tenant_client.client_id),
                    resource_type="project",
                    resource_id=str(project_id),
                    user_auth_id=str(user.auth_id),
                    scopes=scopes,
                )

            logger.debug(f"Updated permissions for user {user.auth_id} on project {project_id} with scopes: {scopes}")

        except Exception as e:
            logger.error(f"Error updating user project permissions in Keycloak: {e}")
            raise

    async def get_user_project_permissions(
        self,
        user_id: str,
        offset: int = 0,
        limit: int = 10,
        filters: dict = None,
        order_by: list = None,
        search: bool = False,
    ) -> tuple[list, int]:
        """Get all project permissions for a specific user.

        Args:
            user_id: The ID of the user to get permissions for
            offset: Pagination offset
            limit: Pagination limit
            filters: Additional filters
            order_by: Order by fields
            search: Whether to use search

        Returns:
            Tuple of (projects with permissions, total count)
        """
        # Handle None defaults
        if filters is None:
            filters = {}
        if order_by is None:
            order_by = []

        # Get the user we're checking permissions for
        db_user = await UserDataManager(self.session).retrieve_by_fields(
            UserModel, {"id": user_id, "status": UserStatusEnum.ACTIVE}
        )

        # Set up filters for active projects
        filters_dict = filters.copy()
        filters_dict["status"] = ProjectStatusEnum.ACTIVE
        filters_dict["benchmark"] = False

        # Get all active projects
        db_projects, count = await ProjectDataManager(self.session).get_all_projects(
            offset, limit, filters_dict, order_by, search
        )

        # Get tenant and client info
        tenant = await UserDataManager(self.session).retrieve_by_fields(
            Tenant, {"realm_name": app_settings.default_realm_name}, missing_ok=True
        )
        if not tenant:
            raise ClientException("Default tenant not found")

        tenant_client = await UserDataManager(self.session).retrieve_by_fields(
            TenantClient, {"tenant_id": tenant.id}, missing_ok=True
        )
        if not tenant_client:
            raise ClientException("Tenant client not found")

        # Initialize Keycloak manager
        kc_manager = KeycloakManager()

        # Check if the target user has global project:manage permission
        try:
            target_user_global_permissions = await kc_manager.get_user_permissions_for_resource(
                realm_name=app_settings.default_realm_name,
                client_id=str(tenant_client.client_id),
                user_auth_id=str(db_user.auth_id),
                resource_type="project",
                resource_id=None,  # None for global permissions
            )
            target_user_has_global_manage = "manage" in target_user_global_permissions
            logger.debug(f"User {db_user.id} has global project:manage permission: {target_user_has_global_manage}")
        except Exception as e:
            logger.debug(f"Failed to get global permissions for user {db_user.id}: {e}")
            target_user_has_global_manage = False

        # Process each project
        result = []
        for db_project in db_projects:
            permissions = []

            # If target user has global project:manage, they have all permissions
            if target_user_has_global_manage:
                permissions = [
                    PermissionList(name=PermissionEnum.ENDPOINT_VIEW.value, has_permission=True),
                    PermissionList(name=PermissionEnum.ENDPOINT_MANAGE.value, has_permission=True),
                ]
            else:
                # Get user's permissions for this specific project from Keycloak
                try:
                    user_permissions = await kc_manager.get_user_permissions_for_resource(
                        realm_name=app_settings.default_realm_name,
                        client_id=str(tenant_client.client_id),
                        user_auth_id=str(db_user.auth_id),
                        resource_type="project",
                        resource_id=str(db_project.id),
                    )

                    # If user_permissions is empty list, user is not participating in the project
                    if not user_permissions:
                        permissions = []
                    else:
                        # Check endpoint permissions based on project permissions
                        has_view = "view" in user_permissions
                        has_manage = "manage" in user_permissions

                        permissions = [
                            PermissionList(name=PermissionEnum.ENDPOINT_VIEW.value, has_permission=has_view),
                            PermissionList(name=PermissionEnum.ENDPOINT_MANAGE.value, has_permission=has_manage),
                        ]
                except Exception as e:
                    logger.debug(f"Failed to get permissions for user {db_user.id} on project {db_project.id}: {e}")
                    # Default to no permissions if error
                    permissions = [
                        PermissionList(name=PermissionEnum.ENDPOINT_VIEW.value, has_permission=False),
                        PermissionList(name=PermissionEnum.ENDPOINT_MANAGE.value, has_permission=False),
                    ]

            result.append(
                UserProjectPermission(
                    id=db_project.id,
                    name=db_project.name,
                    status=db_project.status,
                    permissions=permissions,
                )
            )

        return result, count
