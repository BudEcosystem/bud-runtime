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


"""Implements auth services and business logic that power the microservices, including key functionality and integrations."""

from fastapi import status

from budapp.commons import logging
from budapp.commons.config import app_settings
from budapp.commons.constants import UserColorEnum, UserStatusEnum, UserTypeEnum
from budapp.commons.db_utils import SessionMixin
from budapp.commons.exceptions import ClientException
from budapp.commons.keycloak import KeycloakManager
from budapp.user_ops.crud import UserDataManager
from budapp.user_ops.models import Tenant, TenantClient, TenantUserMapping
from budapp.user_ops.models import User as UserModel
from budapp.user_ops.schemas import TenantClientSchema, UserCreate

from ..commons.constants import PermissionEnum, ProjectStatusEnum, ProjectTypeEnum
from ..commons.exceptions import BudNotifyException
from ..core.schemas import SubscriberCreate
from ..permissions.schemas import PermissionList
from ..permissions.service import PermissionService
from ..project_ops.models import Project as ProjectModel
from ..project_ops.schemas import ProjectUserAdd
from ..shared.notification_service import BudNotifyHandler
from .schemas import LogoutRequest, RefreshTokenRequest, RefreshTokenResponse, ResourceCreate, UserLogin, UserLoginData


logger = logging.get_logger(__name__)


class AuthService(SessionMixin):
    async def login_user(self, user: UserLogin) -> UserLoginData:
        """Login a user with email and password."""
        logger.debug(f"::USER:: User: {user}")

        # Get user
        db_user = await UserDataManager(self.session).retrieve_by_fields(
            UserModel, {"email": user.email}, missing_ok=True
        )

        # Check if user exists
        if not db_user:
            logger.debug(f"User not found in database: {user.email}")
            raise ClientException("This email is not registered")

        # Get tenant information
        tenant = None
        if user.tenant_id:
            tenant = await UserDataManager(self.session).retrieve_by_fields(
                Tenant, {"id": user.tenant_id}, missing_ok=True
            )
            if not tenant:
                raise ClientException("Invalid tenant ID")

            # Verify user belongs to tenant
            tenant_mapping = await UserDataManager(self.session).retrieve_by_fields(
                TenantUserMapping, {"tenant_id": user.tenant_id, "user_id": db_user.id}, missing_ok=True
            )
            if not tenant_mapping:
                raise ClientException("User does not belong to this tenant")
        else:
            # Get the default tenant
            tenant = await UserDataManager(self.session).retrieve_by_fields(
                Tenant, {"realm_name": app_settings.default_realm_name}, missing_ok=True
            )
            if not tenant:
                raise ClientException("Default tenant not found")

            # # If no tenant specified, get the first tenant the user belongs to
            # tenant_mapping = await UserDataManager(self.session).retrieve_by_fields(
            #     TenantUserMapping, {"user_id": db_user.id}, missing_ok=True
            # )
            # if tenant_mapping:
            #     tenant = await UserDataManager(self.session).retrieve_by_fields(
            #         Tenant, {"id": tenant_mapping.tenant_id}, missing_ok=True
            #  )

        logger.debug(f"::USER:: Tenant: {tenant.realm_name}")

        if not tenant:
            raise ClientException("User does not belong to any tenant")

        # Get tenant client credentials
        tenant_client = await UserDataManager(self.session).retrieve_by_fields(
            TenantClient, {"tenant_id": tenant.id}, missing_ok=True
        )
        if not tenant_client:
            raise ClientException("Tenant client configuration not found")

        logger.debug(f"::USER:: Tenant client: {tenant_client.id} {tenant_client.client_id}")

        # Authenticate with Keycloak
        keycloak_manager = KeycloakManager()
        credentials = TenantClientSchema(
            id=tenant_client.id,
            client_id=tenant_client.client_id,
            client_named_id=tenant_client.client_named_id,
            client_secret=tenant_client.client_secret,
        )

        token_data = await keycloak_manager.authenticate_user(
            username=user.email,
            password=user.password,
            realm_name=tenant.realm_name,  # default realm name
            credentials=credentials,
        )

        logger.debug(f"Token data: {token_data}")

        if not token_data:
            logger.debug(f"Invalid credentials for user: {user.email}")
            raise ClientException("Incorrect email or password")

        if db_user.status == UserStatusEnum.DELETED:
            logger.debug(f"User account is not active: {user.email}")
            raise ClientException("User account is not active")

        logger.debug(f"User Retrieved: {user.email}")

        # Create auth token
        # token = await TokenService(self.session).create_auth_token(str(db_user.auth_id))

        return UserLoginData(
            token=token_data,
            first_login=db_user.first_login,
            is_reset_password=db_user.is_reset_password,
        )

    async def refresh_token(self, token: RefreshTokenRequest) -> RefreshTokenResponse:
        """Refresh a user's access token using their refresh token."""
        try:
            # realm_name = app_settings.default_realm_name

            # Get default tenant with realm_name
            tenant = await UserDataManager(self.session).retrieve_by_fields(
                Tenant, {"realm_name": app_settings.default_realm_name}, missing_ok=True
            )
            if not tenant:
                raise ClientException("Default tenant not found")

            # Get user
            # db_user = await UserDataManager(self.session).retrieve_by_fields(
            #     UserModel, {"email": current_user.email}, missing_ok=True
            # )

            # tenant = None
            # # if current_user.tenant_id:
            # #     tenant = await UserDataManager(self.session).retrieve_by_fields(
            # #         Tenant, {"id": current_user.tenant_id}, missing_ok=True
            # #     )
            # #     if not tenant:
            # #         raise ClientException("Invalid tenant ID")

            # #     # Verify user belongs to tenant
            # #     tenant_mapping = await UserDataManager(self.session).retrieve_by_fields(
            # #         TenantUserMapping, {"tenant_id": current_user.tenant_id, "user_id": db_user.id}, missing_ok=True
            # #     )
            # #     if not tenant_mapping:
            # #         raise ClientException("User does not belong to this tenant")
            # # else:
            # # If no tenant specified, get the first tenant the user belongs to
            # tenant_mapping = await UserDataManager(self.session).retrieve_by_fields(
            #     TenantUserMapping, {"user_id": db_user.id}, missing_ok=True
            # )
            # if tenant_mapping:
            #     tenant = await UserDataManager(self.session).retrieve_by_fields(
            #         Tenant, {"id": tenant_mapping.tenant_id}, missing_ok=True
            #     )

            # logger.debug(f"::USER:: Tenant: {tenant.realm_name} {tenant_mapping.id}")

            # Get tenant client credentials
            tenant_client = await UserDataManager(self.session).retrieve_by_fields(
                TenantClient, {"tenant_id": tenant.id}, missing_ok=True
            )

            logger.debug(f"::USER:: Tenant client: {tenant_client.id} {tenant_client.client_id}")

            keycloak_manager = KeycloakManager()
            credentials = TenantClientSchema(
                id=tenant_client.id,
                client_id=tenant_client.client_id,
                client_named_id=tenant_client.client_named_id,
                client_secret=tenant_client.client_secret,
            )

            # Refresh Token
            token_data = await keycloak_manager.refresh_token(
                realm_name=tenant.realm_name,
                credentials=credentials,
                refresh_token=token.refresh_token,
            )

            logger.debug(f"Token data: {token_data}")

            return RefreshTokenResponse(
                code=status.HTTP_200_OK,
                message="Token refreshed successfully",
                token=token_data,
            )
        except Exception as e:
            logger.error(f"Failed to refresh token: {e}")
            raise ClientException("Failed to refresh token") from e

    async def logout_user(self, logout_data: LogoutRequest) -> None:
        """Logout a user by invalidating their refresh token."""
        # Get tenant information
        tenant = None
        if logout_data.tenant_id:
            tenant = await UserDataManager(self.session).retrieve_by_fields(
                Tenant, {"id": logout_data.tenant_id}, missing_ok=True
            )
            if not tenant:
                raise ClientException("Invalid tenant ID")
        else:
            # fetch default tenant
            tenant = await UserDataManager(self.session).retrieve_by_fields(
                Tenant, {"realm_name": app_settings.default_realm_name}, missing_ok=True
            )
            if not tenant:
                raise ClientException("Default tenant not found")

        # Get tenant client credentials
        tenant_client = await UserDataManager(self.session).retrieve_by_fields(
            TenantClient, {"tenant_id": tenant.id}, missing_ok=True
        )
        if not tenant_client:
            raise ClientException("Tenant client configuration not found")

        # Logout from Keycloak
        keycloak_manager = KeycloakManager()
        credentials = TenantClientSchema(
            id=tenant_client.id, client_id=tenant_client.client_id, client_secret=tenant_client.client_secret
        )

        success = await keycloak_manager.logout_user(
            refresh_token=logout_data.refresh_token, realm_name=tenant.realm_name, credentials=credentials
        )

        if not success:
            raise ClientException("Failed to logout user")

    async def register_user(self, user: UserCreate) -> UserModel:
        # Check if email is already registered
        email_exists = await UserDataManager(self.session).retrieve_by_fields(
            UserModel, {"email": user.email}, missing_ok=True
        )

        # Raise exception if email is already registered
        if email_exists:
            logger.info(f"Email already registered: {user.email}")
            raise ClientException("Email already registered")

        try:
            # Keycloak Integration
            keycloak_manager = KeycloakManager()

            # get the default tenant
            tenant = await UserDataManager(self.session).retrieve_by_fields(
                Tenant, {"realm_name": app_settings.default_realm_name}, missing_ok=True
            )
            if not tenant:
                raise ClientException("Default tenant not found")

            # get the default tenant client
            tenant_client = await UserDataManager(self.session).retrieve_by_fields(
                TenantClient, {"tenant_id": tenant.id}, missing_ok=True
            )
            if not tenant_client:
                raise ClientException("Default tenant client not found")

            # Set default permissions for CLIENT users
            if user.user_type == UserTypeEnum.CLIENT:
                # Assign CLIENT_ACCESS permission to client users
                client_permission = PermissionList(name=PermissionEnum.CLIENT_ACCESS, has_permission=True)
                if user.permissions:
                    # Add to existing permissions if not already present
                    permission_names = {p.name for p in user.permissions}
                    if PermissionEnum.CLIENT_ACCESS not in permission_names:
                        user.permissions.append(client_permission)
                else:
                    # Set as the only permission for client users
                    user.permissions = [client_permission]
                logger.debug("Assigned CLIENT_ACCESS permission to client user: %s", user.email)

            # Process permissions to add implicit view permissions for manage permissions
            if user.permissions:
                permission_dict = {p.name: p for p in user.permissions}
                manage_to_view_mapping = PermissionEnum.get_manage_to_view_mapping()

                # Add implicit view permissions for manage permissions
                for permission in user.permissions:
                    if permission.has_permission and permission.name in manage_to_view_mapping:
                        view_permission_name = manage_to_view_mapping[permission.name]
                        # Explicitly upsert the view permission
                        permission_dict[view_permission_name] = PermissionList(
                            name=view_permission_name, has_permission=True
                        )
                        logger.debug("Upsert %s for %s", view_permission_name, permission.name)

                # Update user object with processed permissions
                user.permissions = list(permission_dict.values())

            user_auth_id = await keycloak_manager.create_user_with_permissions(
                user, app_settings.default_realm_name, tenant_client.client_id
            )

            # Hash password
            # salted_password = user.password + secrets_settings.password_salt
            # user.password = await HashManager().get_hash(salted_password)
            # logger.info(f"Password hashed for {user.email}")

            user_data = user.model_dump(exclude={"permissions"})
            user_data["color"] = UserColorEnum.get_random_color()

            user_data["status"] = UserStatusEnum.INVITED

            user_model = UserModel(**user_data)
            user_model.auth_id = user_auth_id

            # NOTE: is_reset_password, first_login will be set to True by default |  # TODO
            # NOTE: status wil be invited by default
            # Create user
            db_user = await UserDataManager(self.session).insert_one(user_model)

            subscriber_data = SubscriberCreate(
                subscriber_id=str(db_user.id),
                email=db_user.email,
                first_name=db_user.name,
            )

            tenant_user_mapping = TenantUserMapping(
                tenant_id=tenant.id,
                user_id=db_user.id,
            )

            await UserDataManager(self.session).insert_one(tenant_user_mapping)
            logger.info(f"User {db_user.email} mapped to tenant {tenant.name}")

            await BudNotifyHandler().create_subscriber(subscriber_data)
            logger.info("User added to budnotify subscriber")

            _ = await UserDataManager(self.session).update_subscriber_status(user_ids=[db_user.id], is_subscriber=True)

            # Create a default project for CLIENT users
            if user.user_type == UserTypeEnum.CLIENT:
                try:
                    # Create default project for the client user
                    default_project = ProjectModel(
                        name="My First Project",
                        description="This is your default project.",
                        created_by=db_user.id,
                        status=ProjectStatusEnum.ACTIVE,
                        benchmark=False,
                        project_type=ProjectTypeEnum.CLIENT_APP.value,
                    )

                    # Insert the project into database
                    await UserDataManager(self.session).insert_one(default_project)
                    logger.info(f"Default project created for client user: {db_user.email}")

                    # Associate the user with the project
                    default_project.users.append(db_user)
                    await self.session.commit()

                    # Create permissions for the project in Keycloak
                    permission_service = PermissionService(self.session)
                    payload = ResourceCreate(
                        resource_id=str(default_project.id),
                        resource_type="project",
                        scopes=["view", "manage"],
                    )
                    await permission_service.create_resource_permission_by_user(db_user, payload)

                    logger.info(
                        f"User {db_user.email} associated with default project: {default_project.name} with full permissions"
                    )

                except Exception as project_error:
                    logger.error(f"Failed to create default project for user {db_user.email}: {project_error}")
                    # Don't fail the registration if project creation fails
                    # The user can create projects manually later

            return db_user

        except BudNotifyException as e:
            logger.error(f"Failed to add user to budnotify subscribers: {e}")
        except Exception as e:
            logger.error(f"Failed to register user: {e}")
            raise e
