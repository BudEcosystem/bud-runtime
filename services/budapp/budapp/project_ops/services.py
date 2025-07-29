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

"""The project ops services. Contains business logic for project ops."""

from typing import Any, Dict, List, Tuple, Union
from uuid import UUID

from fastapi import HTTPException, status

from budapp.auth.schemas import DeletePermissionRequest, ResourceCreate
from budapp.commons import logging
from budapp.commons.db_utils import SessionMixin
from budapp.commons.exceptions import ClientException
from budapp.permissions.service import PermissionService

from ..auth.services import AuthService
from ..cluster_ops.crud import ClusterDataManager
from ..commons.config import app_settings
from ..commons.constants import (
    PROJECT_INVITATION_WORKFLOW,
    EndpointStatusEnum,
    NotificationCategory,
    NotificationTypeEnum,
    PermissionEnum,
    ProjectStatusEnum,
    UserRoleEnum,
)
from ..commons.exceptions import BudNotifyException
from ..commons.helpers import generate_valid_password, get_hardware_types
from ..commons.keycloak import KeycloakManager
from ..core.schemas import NotificationResult
from ..credential_ops.crud import CredentialDataManager
from ..credential_ops.models import Credential as CredentialModel
from ..endpoint_ops.crud import EndpointDataManager
from ..endpoint_ops.models import Endpoint as EndpointModel
from ..permissions.crud import ProjectPermissionDataManager
from ..permissions.models import Permission, ProjectPermission
from ..permissions.schemas import CheckUserResourceScope, PermissionList
from ..shared.notification_service import BudNotifyService, NotificationBuilder
from ..user_ops.crud import UserDataManager
from ..user_ops.models import Tenant, TenantClient
from ..user_ops.models import User as UserModel
from ..user_ops.schemas import User, UserCreate
from .crud import ProjectDataManager
from .models import Project as ProjectModel
from .schemas import (
    ProjectClusterListResponse,
    ProjectListResponse,
    # ProjectCreate,
    # ProjectRequest,
    ProjectResponse,
    ProjectUserAdd,
    ProjectUserList,
)


logger = logging.get_logger(__name__)


class ProjectService(SessionMixin):
    """Project service."""

    async def create_project(self, project_data: Dict[str, Any], current_user_id: UUID) -> ProjectModel:
        """Create a project."""
        # Permission check
        permission_service = PermissionService(self.session)

        if await ProjectDataManager(self.session).retrieve_by_fields(
            ProjectModel,
            {"name": project_data["name"], "status": ProjectStatusEnum.ACTIVE},
            missing_ok=True,
            case_sensitive=False,
        ):
            raise ClientException("Project already exist with same name")

        project_data["created_by"] = current_user_id
        project_model = ProjectModel(**project_data)
        db_project = await ProjectDataManager(self.session).insert_one(project_model)

        # Get user with id
        db_user = await UserDataManager(self.session).retrieve_by_fields(
            UserModel, {"id": current_user_id}, missing_ok=True
        )

        try:
            # Update Permission in Keycloak
            payload: ResourceCreate = ResourceCreate(
                resource_id=str(db_project.id),
                resource_type="project",
                scopes=["view", "manage"],
            )
            await permission_service.create_resource_permission_by_user(db_user, payload)

            # Add current user to project
            default_project_level_scopes = PermissionEnum.get_project_level_scopes()
            add_users_data = ProjectUserAdd(user_id=current_user_id, scopes=default_project_level_scopes)
            db_project = await self.add_users_to_project(db_project.id, [add_users_data])
        except Exception as e:
            logger.error(f"Failed to update permission in Keycloak: {e}")
            raise ClientException("Failed to update permission in Keycloak")

        return db_project

    async def edit_project(self, project_id: UUID, data: Dict[str, Any]) -> ProjectResponse:
        """Edit project by validating and updating specific fields."""
        # Retrieve existing model
        db_project = await ProjectDataManager(self.session).retrieve_by_fields(
            model=ProjectModel,
            fields={"id": project_id, "status": ProjectStatusEnum.ACTIVE},
        )

        if "name" in data:
            duplicate_project = await ProjectDataManager(self.session).retrieve_by_fields(
                model=ProjectModel,
                fields={"name": data["name"], "status": ProjectStatusEnum.ACTIVE},
                exclude_fields={"id": project_id},
                missing_ok=True,
                case_sensitive=False,
            )
            if duplicate_project:
                raise ClientException("Project name already exists")

        db_project = await ProjectDataManager(self.session).update_by_fields(db_project, data)

        return db_project

    async def get_all_clusters_in_project(
        self, project_id: UUID, offset: int, limit: int, filters: Dict[str, Any], order_by: List[str], search: bool
    ) -> Tuple[List[ProjectClusterListResponse], int]:
        """Get all clusters in a project."""
        db_results, count = await ClusterDataManager(self.session).get_all_clusters_in_project(
            project_id, offset, limit, filters, order_by, search
        )

        result = []
        for db_result in db_results:
            db_cluster = db_result[0]
            endpoint_count = db_result[1]
            total_nodes = db_result[2]
            total_replicas = db_result[3]
            result.append(
                ProjectClusterListResponse(
                    id=db_cluster.id,
                    name=db_cluster.name,
                    endpoint_count=endpoint_count,
                    hardware_type=get_hardware_types(db_cluster.cpu_count, db_cluster.gpu_count, db_cluster.hpu_count),
                    node_count=total_nodes,
                    worker_count=total_replicas,
                    status=db_cluster.status,
                    created_at=db_cluster.created_at,
                    modified_at=db_cluster.modified_at,
                )
            )

        return result, count

    async def check_project_membership(self, project_id: UUID, user_id: UUID) -> None:
        user_ids_list = await ProjectDataManager(self.session).get_active_user_ids_in_project(project_id)

        if user_id not in user_ids_list:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is not a member of the project",
            )

    async def search_project_tags(self, search_term: str, offset: int = 0, limit: int = 10) -> Tuple[List[Dict], int]:
        """Search project tags by name."""
        db_tags, count = await ProjectDataManager(self.session).search_tags_by_name(search_term, offset, limit)
        return db_tags, count

    async def get_project_tags(self) -> Tuple[List[Dict], int]:
        db_tags, count = await ProjectDataManager(self.session).get_all_tags()
        return db_tags, count

    async def add_users_to_project(
        self,
        project_id: UUID,
        users_to_add: List[ProjectUserAdd],
    ) -> ProjectModel:
        """Function to add users to project.

        - For existing budserve users, user_id must be provided.
            - App, Email notification will be sent to the users.
        - For non budserve users, email must be provided.
            - New user will be created and email notification will be send to user with temporary password.
        - Specified permissions will be added to the users.
        """
        # Validate project id
        db_project = await ProjectDataManager(self.session).retrieve_by_fields(
            ProjectModel, {"id": project_id, "status": ProjectStatusEnum.ACTIVE}
        )
        logger.info("Project retrieved successfully")

        # Extract user ids, emails from add users schema
        user_ids = [user.user_id for user in users_to_add if user.user_id is not None]
        emails = [user.email for user in users_to_add if user.email is not None]

        # Check if any of the email is already in the database
        # If exists, Remove email from emails and add related id to user_ids
        db_user_emails = await UserDataManager(self.session).get_users_by_emails(emails)
        email_user_id_mapping = {}
        if db_user_emails:
            logger.info(f"Found {len(db_user_emails)} users which already exist")
            for db_user_email in db_user_emails:
                emails.remove(db_user_email.email)
                user_ids.append(db_user_email.id)
                email_user_id_mapping[db_user_email.email] = db_user_email.id

        # Remove duplicate user ids and emails
        user_ids = list(set(user_ids))
        emails = list(set(emails))
        logger.info(f"Found {len(user_ids)} user ids and {len(emails)} emails")

        # Create a permission mapping with user_id or email as key and scopes as value
        # This mapping will be used to add default permissions to the users
        project_permission_mapping = {}
        for user in users_to_add:
            if user.user_id is not None:
                project_permission_mapping[user.user_id] = user.scopes
            elif user.email is not None:
                project_permission_mapping[user.email] = user.scopes

            # if user email is already in the database, add user id to the permission mapping
            if user.email is not None and user.email in email_user_id_mapping:
                project_permission_mapping[email_user_id_mapping[user.email]] = user.scopes

        # NOTE: Commented out since Keycloak handles permissions
        # Store project permissions to be added in database
        # project_permissions = []

        # Store email notification payloads
        email_notification_payloads = []
        project_notification_payload = {
            "name": db_project.name,
            "description": db_project.description,
            "url": f"{app_settings.frontend_url}/projects/{db_project.id}",
        }

        # Initialize permission service
        permission_service = PermissionService(self.session)

        # Handle existing budserve users
        if user_ids:
            # Fetch all related user ids
            existing_user_ids = [user.id for user in db_project.users]

            # Check if any of the user ids are already in the project
            if any(user_id in existing_user_ids for user_id in user_ids):
                raise ClientException("User already in project")

            # Fetch active invited users by ids
            db_users = await UserDataManager(self.session).get_active_invited_users_by_ids(user_ids)

            # If queried user id count is not equal to db user id count, it means some users are not active
            if len(user_ids) != len(db_users):
                raise ClientException("Found non active users in request")

            for db_user in db_users:
                # Add user to project instance
                db_project.users.append(db_user)

                # Add user to project permissions in Keycloak
                try:
                    await permission_service.add_user_to_project_permissions(
                        user=db_user,
                        project_id=str(db_project.id),
                        scopes=project_permission_mapping[db_user.id],
                    )
                except Exception as e:
                    logger.error(f"Failed to add user {db_user.id} to project permissions: {e}")
                    raise ClientException("Failed to add user to project permissions")

                # NOTE: Commented out since Keycloak handles permissions
                # project_permission_data = ProjectPermissionCreate(
                #     project_id=db_project.id,
                #     user_id=db_user.id,
                #     auth_id=db_user.auth_id,
                #     scopes=project_permission_mapping[db_user.id],
                # )
                # project_permissions.append(ProjectPermission(**project_permission_data.model_dump()))

                # Store email notification payload
                email_notification_payloads.append(
                    {
                        "subscriber_id": str(db_user.id),
                        "user": {"name": db_user.name, "is_budserve_user": True},
                        "project": project_notification_payload,
                    }
                )

        # Store newly created user ids
        new_user_ids = []

        # Handle non budserve users
        if emails:
            # User name, role will be static
            user_name = "Bud User"
            user_role = UserRoleEnum.DEVELOPER

            for new_email in emails:
                # User name will be get from email
                user_name = new_email.split("@")[0]

                password = generate_valid_password()

                # NOTE: New user created with help of auth service, it will handle different scenarios like notification, permission, etc.
                user_data = UserCreate(name=user_name, email=new_email, password=password, role=user_role)
                db_user = await AuthService(self.session).register_user(user_data)

                # Add user to project
                db_project.users.append(db_user)

                # Add user to project permissions in Keycloak
                try:
                    await permission_service.add_user_to_project_permissions(
                        user=db_user,
                        project_id=str(db_project.id),
                        scopes=project_permission_mapping[db_user.email],
                    )
                except Exception as e:
                    logger.error(f"Failed to add new user {db_user.id} to project permissions: {e}")
                    raise ClientException("Failed to add new user to project permissions")

                # NOTE: Commented out since Keycloak handles permissions
                # project_permission_data = ProjectPermissionCreate(
                #     project_id=db_project.id,
                #     user_id=db_user.id,
                #     auth_id=db_user.auth_id,
                #     scopes=project_permission_mapping[db_user.email],
                # )
                # project_permissions.append(ProjectPermission(**project_permission_data.model_dump()))

                new_user_ids.append(db_user.id)

                # Store email notification payload
                email_notification_payloads.append(
                    {
                        "subscriber_id": str(db_user.id),
                        "user": {
                            "name": db_user.name,
                            "is_budserve_user": False,
                            "password": password,
                        },
                        "project": project_notification_payload,
                    }
                )

        # Update project to reflect changes in db
        db_project = ProjectDataManager(self.session).update_one(db_project)
        logger.info(f"{len(user_ids)} BudServe users added to project")
        logger.info(f"{len(emails)} Non BudServe users added to project")

        # NOTE: Commented out since Keycloak handles permissions
        # Add project level permissions
        # _ = ProjectPermissionDataManager(self.session).add_all(project_permissions)
        # logger.info(f"Added project level permissions to {len(project_permissions)} users")

        # Send app notification for budserve users
        if user_ids:
            user_ids_str = [str(user_id) for user_id in user_ids]
            # Commented out old implementation
            # _ = await NotificaitonService(self.session).send_app_notification_to_users(
            #     {"Content": f"You have been added to {db_project.name} project"},
            #     user_ids_str,
            # )

            notification_request = (
                NotificationBuilder()
                .set_content(
                    title=db_project.name,
                    message="Project Invite",
                    icon=db_project.icon,
                    result=NotificationResult(target_id=db_project.id, target_type="project").model_dump(
                        exclude_none=True, exclude_unset=True
                    ),
                )
                .set_payload(
                    type=NotificationTypeEnum.PROJECT_INVITATION_SUCCESS.value,
                )
                .set_notification_request(subscriber_ids=user_ids_str)
                .build()
            )
            await BudNotifyService().send_notification(notification_request)
        # NOTE: Email Notification sent sequentially because user name in payload is different

        # Commented out old implementation
        # for payload in email_notification_payloads:
        #     subscriber_id = payload.pop("subscriber_id")
        #     notification_data = NotificationTrigger(
        #         notification_type=NotificationType.EVENT,
        #         name=PROJECT_INVITATION_WORKFLOW,
        #         subscriber_ids=[subscriber_id],
        #         payload=payload,
        #     )
        #     try:
        #         await BudNotifyHandler().trigger_notification(notification_data)
        #         logger.info(f"Sent email notification to {subscriber_id}")
        #     except BudNotifyException as e:
        #         logger.error(f"Failed to trigger notification {e.message}")

        for content in email_notification_payloads:
            subscriber_id = content.pop("subscriber_id")
            # notification_request = (
            #     NotificationBuilder()
            #     .set_payload(content=content, category=NotificationCategory.INTERNAL)
            #     .set_notification_request(subscriber_ids=[subscriber_id], name=PROJECT_INVITATION_WORKFLOW)
            #     .build()
            # )
            notification_request = (
                NotificationBuilder()
                .set_content(
                    content=content,
                )
                .set_payload(category=NotificationCategory.INTERNAL)
                .set_notification_request(subscriber_ids=[subscriber_id], name=PROJECT_INVITATION_WORKFLOW)
                .build()
            )
            try:
                await BudNotifyService().send_notification(notification_request)
                logger.info(f"Sent email notification to {subscriber_id}")
            except BudNotifyException as err:
                logger.error(f"Failed to send email notification {err.message}")

        return db_project

    async def get_all_active_projects(
        self,
        current_user: User,
        offset: int = 0,
        limit: int = 10,
        filters: Dict = {},
        order_by: List = [],
        search: bool = False,
    ) -> Tuple[List[ProjectModel], int]:
        filters_dict = filters
        filters_dict["status"] = ProjectStatusEnum.ACTIVE
        filters_dict["benchmark"] = False

        permission_manager = PermissionService(self.session)

        permission_payload = CheckUserResourceScope(resource_type="project", scope="manage")

        is_allowed = await permission_manager.check_resource_permission_by_user(current_user, permission_payload)
        logger.debug(f"User {current_user.id} has project:manage permission: {is_allowed}")

        # Only users with project:manage permission can list all projects
        # Otherwise, list only participated projects
        if is_allowed:
            result, count = await ProjectDataManager(self.session).get_all_active_projects(
                offset, limit, filters_dict, order_by, search
            )
        else:
            result, count = await ProjectDataManager(self.session).get_all_participated_projects(
                current_user.id, offset, limit, filters_dict, order_by, search
            )

        return await self.parse_project_list_results(result), count

    async def parse_project_list_results(self, db_results: List) -> List[ProjectListResponse]:
        result = []

        for db_result in db_results:
            db_project, users_count, profile_colors, endpoints_count = db_result
            profile_colors = profile_colors.split(",") if profile_colors else []
            result.append(
                ProjectListResponse(
                    project=db_project,
                    endpoints_count=endpoints_count,
                    users_count=users_count,
                    profile_colors=profile_colors[:3],
                )
            )

        return result

    async def retrieve_active_project_details(self, project_id: UUID) -> Union[Tuple[ProjectModel, int], None]:
        db_project, endpoints_count = await ProjectDataManager(self.session).retrieve_project_details(
            project_id=project_id
        )

        return db_project, endpoints_count

    async def delete_active_project(
        self,
        project_id: UUID,
        remove_credential: bool = False,
        is_benchmark: bool = False,
    ) -> ProjectModel:
        """Delete a project from the database."""
        db_project = await ProjectDataManager(self.session).retrieve_by_fields(
            ProjectModel, {"id": project_id, "status": ProjectStatusEnum.ACTIVE}
        )

        # Check active endpoint exists
        db_endpoints = await EndpointDataManager(self.session).get_all_by_fields(
            EndpointModel,
            fields={"project_id": project_id},
            exclude_fields={"status": EndpointStatusEnum.DELETED},
        )

        if db_endpoints:
            raise ClientException("Cannot delete the project because it has an active endpoint.")

        db_credentials = await CredentialDataManager(self.session).get_all_by_fields(
            CredentialModel, fields={"project_id": project_id}
        )

        if db_credentials and not remove_credential:
            logger.info("Found user created credentials related to project")
            raise ClientException("Credentials need to be removed")
        else:
            # Delete all credentials related to the project
            await CredentialDataManager(self.session).delete_by_fields(CredentialModel, {"project_id": project_id})
            logger.info("Deleted all credentials related to project")

        # NOTE: keep project level permissions instead of deleting it on project deletion
        # Remove project permissions on benchmark
        if is_benchmark:
            _ = await ProjectPermissionDataManager(self.session).delete_by_fields(
                ProjectPermission, {"project_id": project_id}
            )
            logger.info("Deleted all project level permissions")

        # Delete the project resource from Keycloak
        try:
            permission_service = PermissionService(self.session)
            await permission_service.delete_permission_for_resource(
                DeletePermissionRequest(
                    resource_type="project",
                    resource_id=str(project_id),
                    delete_resource=True,  # Delete the resource itself
                )
            )
            logger.info(f"Deleted project resource from Keycloak for project {project_id}")
        except Exception as e:
            logger.error(f"Failed to delete project resource from Keycloak: {e}")
            # Continue with project deletion even if Keycloak deletion fails

        if db_project.benchmark:
            return await ProjectDataManager(self.session).delete_one(db_project)

        data = {"status": ProjectStatusEnum.DELETED}
        return await ProjectDataManager(self.session).update_by_fields(db_project, data)

    async def remove_users_from_project(
        self, project_id: UUID, user_ids: List[UUID], remove_credential: bool
    ) -> ProjectModel:
        db_project = await ProjectDataManager(self.session).retrieve_by_fields(
            ProjectModel, {"id": project_id, "status": ProjectStatusEnum.ACTIVE}
        )

        # Fetch all related user ids
        existing_user_ids = [user.id for user in db_project.users]

        # Check if any of the user ids are already in the project
        if not any(user_id in existing_user_ids for user_id in user_ids):
            raise ClientException("User not in project")

        # Cannot remove all users from project
        if len(existing_user_ids) == len(user_ids):
            raise ClientException(detail="Cannot remove all users from project")

        # Initialize permission service
        permission_service = PermissionService(self.session)

        # Fetch active invited users by ids
        db_users = await UserDataManager(self.session).get_active_invited_users_by_ids(user_ids)

        for db_user in db_users:
            db_credentials = await CredentialDataManager(self.session).get_all_by_fields(
                CredentialModel,
                fields={
                    "user_id": db_user.id,
                    "project_id": project_id,
                },
            )

            # Credential related to project need to be removed
            if db_credentials and not remove_credential:
                raise ClientException("Credentials need to be removed")

            # Remove credentials
            if db_credentials:
                await CredentialDataManager(self.session).delete_by_fields(
                    CredentialModel,
                    fields={
                        "user_id": db_user.id,
                        "project_id": project_id,
                    },
                )
                logger.info("Deleted project credentials related to user")

            # Remove user from project
            db_project.users.remove(db_user)

            # Remove user permissions from Keycloak
            try:
                await permission_service.remove_user_from_project_permissions(
                    user=db_user,
                    project_id=str(project_id),
                )
                logger.debug(f"Removed user {db_user.id} from project permissions in Keycloak")
            except Exception as e:
                logger.error(f"Failed to remove user {db_user.id} from project permissions in Keycloak: {e}")
                raise ClientException("Failed to remove user from project permissions")

        # update project
        db_project = ProjectDataManager(self.session).update_one(db_project)
        logger.info(f"{len(user_ids)} users removed from project")

        # NOTE: Commented out since Keycloak handles permissions
        # delete project permissions
        # await ProjectPermissionDataManager(self.session).delete_project_permissions_by_user_ids(user_ids, project_id)
        # logger.info(f"Deleted project permissions of {len(user_ids)} users")

        return db_project

    async def get_all_project_users(
        self,
        project_id: UUID,
        offset: int = 0,
        limit: int = 10,
        filters: Dict = {},
        order_by: List = [],
        search: bool = False,
    ) -> Tuple[List[ProjectUserList], int]:
        filters_dict = filters

        # Get users from database (without permission tables)
        db_users, count = await ProjectDataManager(self.session).get_all_project_users_without_permissions(
            project_id, offset, limit, filters_dict, order_by, search
        )

        # Get permissions from Keycloak for each user
        return await self._get_parsed_project_user_permissions_from_keycloak(db_users, project_id), count

    async def _get_parsed_project_user_permissions_from_keycloak(
        self,
        results: List[Tuple[UserModel, str]],  # User and project_role
        project_id: UUID,
    ) -> List[ProjectUserList]:
        """Get parsed project user list response with permissions from Keycloak."""
        data = []
        project_level_permissions = PermissionEnum.get_project_level_scopes()
        global_project_permissions = [
            PermissionEnum.PROJECT_MANAGE.value,
            PermissionEnum.PROJECT_VIEW.value,
        ]

        # Get tenant and client info once
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

        for user, project_role in results:
            permissions = []

            # Get user's permissions for this project from Keycloak
            try:
                user_permissions = await kc_manager.get_user_permissions_for_resource(
                    realm_name=app_settings.default_realm_name,
                    client_id=str(tenant_client.client_id),
                    user_auth_id=str(user.auth_id),
                    resource_type="project",
                    resource_id=str(project_id),
                )

            except Exception as e:
                logger.debug(f"Failed to get permissions for user {user.id} from Keycloak: {e}")
                user_permissions = []

            # Check global project permissions first to determine if user has project:manage
            try:
                # Get user's global permissions
                global_permissions = await kc_manager.get_user_permissions_for_resource(
                    realm_name=app_settings.default_realm_name,
                    client_id=str(tenant_client.client_id),
                    user_auth_id=str(user.auth_id),
                    resource_type="project",
                    resource_id=None,  # Global permissions
                )

            except Exception as e:
                logger.debug(f"Failed to get global permissions for user {user.id} from Keycloak: {e}")
                global_permissions = []

            # Check if user has global project:manage permission
            has_global_project_manage = "manage" in global_permissions

            # Check project-level permissions
            for permission in project_level_permissions:
                # Extract scope from permission (e.g., "endpoint:view" -> "view")
                scope = permission.split(":")[-1] if ":" in permission else permission

                # Check if user has this scope
                has_permission = scope in user_permissions

                # If user has global project:manage, they automatically get endpoint:manage and endpoint:view
                if has_global_project_manage and permission in [
                    PermissionEnum.ENDPOINT_MANAGE.value,
                    PermissionEnum.ENDPOINT_VIEW.value,
                ]:
                    has_permission = True

                permissions.append(
                    PermissionList(
                        name=permission,
                        has_permission=has_permission,
                    )
                )

            # Add global project permissions
            for permission in global_project_permissions:
                # Extract scope from permission
                scope = permission.split(":")[-1] if ":" in permission else permission

                # Check if user has this global scope
                has_permission = scope in global_permissions

                permissions.append(
                    PermissionList(
                        name=permission,
                        has_permission=has_permission,
                    )
                )

            data.append(
                ProjectUserList(
                    name=user.name,
                    email=user.email,
                    id=user.id,
                    color=user.color,
                    role=user.role,
                    status=user.status,
                    user_type=user.user_type,
                    permissions=permissions,
                    project_role=project_role,
                )
            )

        return data

    # Keep the old method for backward compatibility if needed
    async def _get_parsed_project_user_permissions(
        self,
        results: List[Tuple[UserModel, str, ProjectPermission, Permission]],
    ) -> List[ProjectUserList]:
        """Get parsed project user list response."""
        data = []
        project_level_permissions = PermissionEnum.get_project_level_scopes()
        global_project_permissions = [
            PermissionEnum.PROJECT_MANAGE.value,
            PermissionEnum.PROJECT_VIEW.value,
        ]

        for result in results:
            permissions = []
            # Add project level permissions to specific user
            for permission in project_level_permissions:
                permissions.append(
                    PermissionList(
                        name=permission,
                        has_permission=permission in result[2].scopes_list,
                    )
                )
            # Add project-related global level permissions to specific user
            for permission in global_project_permissions:
                permissions.append(
                    PermissionList(
                        name=permission,
                        has_permission=permission in result[3].scopes_list,
                    )
                )
            data.append(
                ProjectUserList(
                    name=result[0].name,
                    email=result[0].email,
                    id=result[0].id,
                    color=result[0].color,
                    role=result[0].role,
                    status=result[0].status,
                    user_type=result[0].user_type,
                    permissions=permissions,
                    project_role=result[1],
                )
            )

        return data
