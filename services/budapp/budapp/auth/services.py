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

from typing import Dict, Optional
from uuid import UUID

from fastapi import status
from keycloak.exceptions import KeycloakAuthenticationError, KeycloakPostError

from budapp.audit_ops import log_audit
from budapp.auth.user_onboarding_service import UserOnboardingService
from budapp.commons import logging
from budapp.commons.config import app_settings, secrets_settings
from budapp.commons.constants import (
    AuditActionEnum,
    AuditResourceTypeEnum,
    UserColorEnum,
    UserRoleEnum,
    UserStatusEnum,
    UserTypeEnum,
)
from budapp.commons.db_utils import SessionMixin
from budapp.commons.exceptions import ClientException
from budapp.commons.keycloak import KeycloakManager
from budapp.commons.security import HashManager
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
from ..shared.jwt_blacklist_service import JWTBlacklistService
from ..shared.notification_service import BudNotifyHandler
from .schemas import LogoutRequest, RefreshTokenRequest, RefreshTokenResponse, ResourceCreate, UserLogin, UserLoginData


logger = logging.get_logger(__name__)


class AuthService(SessionMixin):
    async def login_user(self, user: UserLogin, request=None) -> UserLoginData:
        """Login a user with email and password."""
        # Get user
        db_user = await UserDataManager(self.session).retrieve_by_fields(
            UserModel, {"email": user.email}, missing_ok=True
        )

        logger.info(f"LOGIN ATTEMPT: User {user.email} found in database: {db_user is not None}")

        # Check if user exists
        if not db_user:
            logger.info(f"User {user.email} not in database. Attempting JIT provisioning from Keycloak...")

            # Try to get tenant and client for JIT provisioning
            realm_name = app_settings.default_realm_name
            tenant, tenant_client = await self._get_tenant_and_client_for_jit(realm_name)

            if not tenant_client:
                log_audit(
                    session=self.session,
                    action=AuditActionEnum.LOGIN_FAILED,
                    resource_type=AuditResourceTypeEnum.USER,
                    resource_name=user.email,
                    details={"email": user.email, "reason": "No tenant found for JIT provisioning"},
                    request=request,
                    success=False,
                )
                raise ClientException("This email is not registered")

            try:
                # Authenticate with Keycloak to verify credentials
                keycloak_manager = KeycloakManager()
                decrypted_secret = await tenant_client.get_decrypted_client_secret()
                credentials = TenantClientSchema(
                    id=tenant_client.id,
                    client_id=tenant_client.client_id,
                    client_named_id=tenant_client.client_named_id,
                    client_secret=decrypted_secret,
                )

                # This will raise exception if auth fails
                await keycloak_manager.authenticate_user(
                    username=user.email,
                    password=user.password,
                    realm_name=realm_name,
                    credentials=credentials,
                )

                # Fetch user details from Keycloak
                keycloak_user = keycloak_manager.get_keycloak_user_by_email(user.email, realm_name)
                if not keycloak_user:
                    raise ClientException("User found in Keycloak but unable to fetch details")

                # Create user in database (pass tenant to avoid redundant DB query)
                db_user = await self._create_user_from_keycloak(
                    keycloak_user=keycloak_user,
                    tenant_client=tenant_client,
                    tenant=tenant,
                    realm_name=realm_name,
                )

                logger.info(f"JIT provisioning successful for user {user.email}")
                log_audit(
                    session=self.session,
                    action=AuditActionEnum.LOGIN,
                    resource_type=AuditResourceTypeEnum.USER,
                    resource_id=db_user.id,
                    resource_name=db_user.email,
                    user_id=db_user.id,
                    details={"email": user.email, "keycloak_sync": True},
                    request=request,
                    success=True,
                )

            except KeycloakPostError as e:
                # Handle Keycloak account setup errors during JIT provisioning
                error_msg = str(e)
                logger.error(f"Keycloak account setup error for {user.email} during JIT provisioning: {error_msg}")

                # Parse error to provide user-friendly message
                user_message = "Incorrect email or password"
                reason = f"Keycloak error: {error_msg}"

                # Check for specific account setup issues
                if "not fully set up" in error_msg.lower():
                    user_message = "Account setup incomplete. Please verify your email and complete required actions."
                    reason = "Account not fully set up in Keycloak"
                elif "invalid_grant" in error_msg.lower():
                    user_message = "Unable to login. Please contact administrator to complete account setup."
                    reason = "Invalid grant - account setup issue"
                elif "account disabled" in error_msg.lower() or "account is disabled" in error_msg.lower():
                    user_message = "This account has been disabled. Please contact administrator."
                    reason = "Account disabled in Keycloak"

                log_audit(
                    session=self.session,
                    action=AuditActionEnum.LOGIN_FAILED,
                    resource_type=AuditResourceTypeEnum.USER,
                    resource_name=user.email,
                    details={"email": user.email, "reason": reason, "keycloak_error": error_msg},
                    request=request,
                    success=False,
                )
                raise ClientException(user_message)
            except KeycloakAuthenticationError as e:
                error_msg = str(e)
                logger.error(
                    f"Keycloak authentication failed for {user.email} during JIT provisioning: {error_msg}. "
                    f"Check Keycloak Admin Console: Users > {user.email} > Credentials tab for temporary password flag"
                )
                log_audit(
                    session=self.session,
                    action=AuditActionEnum.LOGIN_FAILED,
                    resource_type=AuditResourceTypeEnum.USER,
                    resource_name=user.email,
                    details={"email": user.email, "reason": f"Authentication failed: {error_msg}"},
                    request=request,
                    success=False,
                )
                raise ClientException("Incorrect email or password")
            except Exception as e:
                logger.error(f"Keycloak user sync failed for {user.email}: {str(e)}", exc_info=True)
                log_audit(
                    session=self.session,
                    action=AuditActionEnum.LOGIN_FAILED,
                    resource_type=AuditResourceTypeEnum.USER,
                    resource_name=user.email,
                    details={"email": user.email, "reason": f"JIT provisioning failed: {str(e)}"},
                    request=request,
                    success=False,
                )
                raise ClientException("Could not complete account setup. Please contact support.")

        # Get tenant information
        logger.info(f"LOGIN ATTEMPT: Getting tenant for {user.email} (tenant_id: {user.tenant_id})")
        tenant = None
        if user.tenant_id:
            tenant = await UserDataManager(self.session).retrieve_by_fields(
                Tenant, {"id": user.tenant_id}, missing_ok=True
            )
            if not tenant:
                # Log failed login attempt - invalid tenant
                log_audit(
                    session=self.session,
                    action=AuditActionEnum.LOGIN_FAILED,
                    resource_type=AuditResourceTypeEnum.USER,
                    resource_id=db_user.id,
                    resource_name=db_user.email,
                    user_id=db_user.id,
                    details={"email": user.email, "reason": "Invalid tenant ID", "tenant_id": str(user.tenant_id)},
                    request=request,
                    success=False,
                )
                raise ClientException("Invalid tenant ID")

            # Verify user belongs to tenant
            tenant_mapping = await UserDataManager(self.session).retrieve_by_fields(
                TenantUserMapping, {"tenant_id": user.tenant_id, "user_id": db_user.id}, missing_ok=True
            )
            if not tenant_mapping:
                # Log failed login attempt - user not in tenant
                log_audit(
                    session=self.session,
                    action=AuditActionEnum.LOGIN_FAILED,
                    resource_type=AuditResourceTypeEnum.USER,
                    resource_id=db_user.id,
                    resource_name=db_user.email,
                    user_id=db_user.id,
                    details={
                        "email": user.email,
                        "reason": "User does not belong to this tenant",
                        "tenant_id": str(user.tenant_id),
                    },
                    request=request,
                    success=False,
                )
                raise ClientException("User does not belong to this tenant")
        else:
            # Get the default tenant
            tenant = await UserDataManager(self.session).retrieve_by_fields(
                Tenant, {"realm_name": app_settings.default_realm_name}, missing_ok=True
            )
            if not tenant:
                # Log failed login attempt - default tenant not found
                log_audit(
                    session=self.session,
                    action=AuditActionEnum.LOGIN_FAILED,
                    resource_type=AuditResourceTypeEnum.USER,
                    resource_id=db_user.id,
                    resource_name=db_user.email,
                    user_id=db_user.id,
                    details={"email": user.email, "reason": "Default tenant not found"},
                    request=request,
                    success=False,
                )
                raise ClientException("Default tenant not found")

            # # If no tenant specified, get the first tenant the user belongs to
            # tenant_mapping = await UserDataManager(self.session).retrieve_by_fields(
            #     TenantUserMapping, {"user_id": db_user.id}, missing_ok=True
            # )
            # if tenant_mapping:
            #     tenant = await UserDataManager(self.session).retrieve_by_fields(
            #         Tenant, {"id": tenant_mapping.tenant_id}, missing_ok=True
            #  )

        if not tenant:
            # Log failed login attempt - no tenant association
            log_audit(
                session=self.session,
                action=AuditActionEnum.LOGIN_FAILED,
                resource_type=AuditResourceTypeEnum.USER,
                resource_id=db_user.id,
                resource_name=db_user.email,
                user_id=db_user.id,
                details={"email": user.email, "reason": "User does not belong to any tenant"},
                request=request,
                success=False,
            )
            raise ClientException("User does not belong to any tenant")

        # Get tenant client credentials
        tenant_client = await UserDataManager(self.session).retrieve_by_fields(
            TenantClient, {"tenant_id": tenant.id}, missing_ok=True
        )
        if not tenant_client:
            # Log failed login attempt - tenant client config missing
            log_audit(
                session=self.session,
                action=AuditActionEnum.LOGIN_FAILED,
                resource_type=AuditResourceTypeEnum.USER,
                resource_id=db_user.id,
                resource_name=db_user.email,
                user_id=db_user.id,
                details={
                    "email": user.email,
                    "reason": "Tenant client configuration not found",
                    "tenant": tenant.realm_name,
                },
                request=request,
                success=False,
            )
            raise ClientException("Tenant client configuration not found")

        logger.info(f"LOGIN ATTEMPT: About to authenticate {user.email} with Keycloak in realm {tenant.realm_name}")

        # Authenticate with Keycloak
        keycloak_manager = KeycloakManager()
        # Decrypt client secret for use
        decrypted_secret = await tenant_client.get_decrypted_client_secret()
        credentials = TenantClientSchema(
            id=tenant_client.id,
            client_id=tenant_client.client_id,
            client_named_id=tenant_client.client_named_id,
            client_secret=decrypted_secret,
        )

        try:
            token_data = await keycloak_manager.authenticate_user(
                username=user.email,
                password=user.password,
                realm_name=tenant.realm_name,  # default realm name
                credentials=credentials,
            )
        except KeycloakPostError as e:
            # Handle Keycloak account setup errors (400 errors from token endpoint)
            error_msg = str(e)
            logger.error(f"Keycloak account setup error for user {user.email}: {error_msg}")

            # Parse error to provide user-friendly message
            user_message = "Incorrect email or password"
            reason = f"Keycloak error: {error_msg}"

            # Check for specific account setup issues
            if "not fully set up" in error_msg.lower():
                user_message = "Account setup incomplete. Please verify your email and complete required actions."
                reason = "Account not fully set up in Keycloak"
            elif "invalid_grant" in error_msg.lower():
                user_message = "Unable to login. Please contact administrator to complete account setup."
                reason = "Invalid grant - account setup issue"
            elif "account disabled" in error_msg.lower() or "account is disabled" in error_msg.lower():
                user_message = "This account has been disabled. Please contact administrator."
                reason = "Account disabled in Keycloak"

            # Log failed login attempt
            log_audit(
                session=self.session,
                action=AuditActionEnum.LOGIN_FAILED,
                resource_type=AuditResourceTypeEnum.USER,
                resource_id=db_user.id,
                resource_name=db_user.email,
                user_id=db_user.id,
                details={
                    "email": user.email,
                    "reason": reason,
                    "keycloak_error": error_msg,
                    "tenant": tenant.realm_name,
                },
                request=request,
                success=False,
            )
            raise ClientException(user_message)
        except KeycloakAuthenticationError as e:
            error_msg = str(e)
            logger.error(
                f"Keycloak authentication failed for existing user {user.email}: {error_msg}. "
                f"Check Keycloak Admin Console: Users > {user.email} > Credentials tab"
            )
            # Log failed login attempt - authentication failed
            log_audit(
                session=self.session,
                action=AuditActionEnum.LOGIN_FAILED,
                resource_type=AuditResourceTypeEnum.USER,
                resource_id=db_user.id,
                resource_name=db_user.email,
                user_id=db_user.id,
                details={
                    "email": user.email,
                    "reason": f"Authentication failed: {error_msg}",
                    "tenant": tenant.realm_name,
                },
                request=request,
                success=False,
            )
            raise ClientException("Incorrect email or password")

        # Sync user roles from Keycloak to ensure database is up-to-date
        # This ensures that role changes in Keycloak are reflected on next login
        logger.info(f"Syncing roles from Keycloak for existing user {user.email}")
        try:
            realm_roles = keycloak_manager.get_user_realm_roles(str(db_user.auth_id), tenant.realm_name)

            # Check if role fetch was successful (None indicates error, empty list is valid)
            if realm_roles is not None:
                logger.info(f"User {user.email} current Keycloak roles: {realm_roles}")

                # Determine current permissions from Keycloak roles
                current_user_type, current_role, current_is_superuser = self._determine_user_permissions_from_roles(
                    realm_roles
                )

                # Update database if roles have changed
                if (
                    db_user.user_type != current_user_type
                    or db_user.role != current_role
                    or db_user.is_superuser != current_is_superuser
                ):
                    logger.info(
                        f"Updating user {user.email} roles: "
                        f"user_type {db_user.user_type} -> {current_user_type}, "
                        f"role {db_user.role} -> {current_role}, "
                        f"is_superuser {db_user.is_superuser} -> {current_is_superuser}"
                    )

                    db_user.user_type = current_user_type
                    db_user.role = current_role
                    db_user.is_superuser = current_is_superuser

                    # Update the user record
                    updated_user = UserDataManager(self.session).update_one(db_user)
                    if updated_user:
                        db_user = updated_user
                        logger.info(f"Successfully synced roles for user {user.email}")
                else:
                    logger.debug(f"User {user.email} roles are already up-to-date")
            else:
                # Role fetch failed - skip sync to prevent privilege de-escalation
                logger.warning(
                    f"Skipping role sync for {user.email} due to Keycloak error. Using existing database roles."
                )

        except Exception as e:
            # Log error but don't fail login - use existing database roles
            logger.warning(
                f"Failed to sync roles from Keycloak for {user.email}: {str(e)}. Continuing with database roles.",
                exc_info=True,
            )

        # Validate user_type AFTER role sync: Prevent clients from logging in as admin
        # This validation now uses the freshly synced user_type from Keycloak
        logger.info(
            f"LOGIN ATTEMPT: Validating user_type for {user.email} "
            f"(requested: {user.user_type}, actual: {db_user.user_type})"
        )
        if user.user_type == UserTypeEnum.ADMIN and db_user.user_type == UserTypeEnum.CLIENT:
            logger.warning(f"Client user attempting to login as admin: {user.email}")
            # Log failed login attempt - unauthorized user_type
            log_audit(
                session=self.session,
                action=AuditActionEnum.LOGIN_FAILED,
                resource_type=AuditResourceTypeEnum.USER,
                resource_id=db_user.id,
                resource_name=db_user.email,
                user_id=db_user.id,
                details={
                    "email": user.email,
                    "reason": "Client users cannot login with admin user_type",
                    "requested_user_type": user.user_type.value,
                    "actual_user_type": db_user.user_type,
                },
                request=request,
                success=False,
            )
            raise ClientException("Access denied: This account does not have admin privileges")

        if db_user.status == UserStatusEnum.DELETED:
            logger.warning(f"Login attempt for inactive account: {user.email} (status: {db_user.status})")
            # Log failed login attempt - account deleted/inactive
            log_audit(
                session=self.session,
                action=AuditActionEnum.LOGIN_FAILED,
                resource_type=AuditResourceTypeEnum.USER,
                resource_id=db_user.id,
                resource_name=db_user.email,
                user_id=db_user.id,
                details={
                    "email": user.email,
                    "reason": "User account is not active",
                    "status": db_user.status,
                    "tenant": tenant.realm_name,
                },
                request=request,
                success=False,
            )
            raise ClientException("User account is not active")

        # Log successful login
        log_audit(
            session=self.session,
            action=AuditActionEnum.LOGIN,
            resource_type=AuditResourceTypeEnum.USER,
            resource_id=db_user.id,
            resource_name=db_user.email,
            user_id=db_user.id,
            details={"email": user.email, "tenant": tenant.realm_name if tenant else None},
            request=request,
            success=True,
        )

        # Create auth token
        # token = await TokenService(self.session).create_auth_token(str(db_user.auth_id))

        return UserLoginData(
            token=token_data,
            first_login=db_user.first_login,
            is_reset_password=db_user.is_reset_password,
        )

    def _determine_user_permissions_from_roles(self, realm_roles: list[str]) -> tuple[str, str, bool]:
        """Determine user_type, role, and is_superuser from Keycloak realm roles.

        This logic is shared between JIT provisioning and role synchronization
        to ensure consistency.

        Args:
            realm_roles: List of Keycloak realm role names (e.g., ['admin', 'developer'])

        Returns:
            Tuple of (user_type, role, is_superuser)
        """
        # Determine user_type based on realm roles
        # If user has super_admin or admin role, they are ADMIN type
        # Otherwise, they are CLIENT type
        if "super_admin" in realm_roles or "admin" in realm_roles:
            user_type = UserTypeEnum.ADMIN.value
            is_superuser = "super_admin" in realm_roles
        else:
            user_type = UserTypeEnum.CLIENT.value
            is_superuser = False

        # Determine role based on realm roles (priority order)
        if "super_admin" in realm_roles:
            role = UserRoleEnum.SUPER_ADMIN.value
        elif "admin" in realm_roles:
            role = UserRoleEnum.ADMIN.value
        elif "devops" in realm_roles:
            role = UserRoleEnum.DEVOPS.value
        elif "tester" in realm_roles:
            role = UserRoleEnum.TESTER.value
        elif "developer" in realm_roles:
            role = UserRoleEnum.DEVELOPER.value
        else:
            role = UserRoleEnum.DEVELOPER.value  # Safe default

        return user_type, role, is_superuser

    async def _get_tenant_and_client_for_jit(self, realm_name: str) -> tuple[Optional[Tenant], Optional[TenantClient]]:
        """Get tenant and tenant client for JIT provisioning based on realm.

        Args:
            realm_name: Realm name

        Returns:
            A tuple of (Tenant, TenantClient) if found, otherwise (None, None)
        """
        # Get tenant by realm name
        tenant = await UserDataManager(self.session).retrieve_by_fields(
            Tenant,
            {"realm_name": realm_name},
            missing_ok=True,
        )

        if not tenant:
            logger.warning(f"No tenant found for realm {realm_name}")
            return None, None

        # Get default client for this tenant
        tenant_client = await UserDataManager(self.session).retrieve_by_fields(
            TenantClient,
            {"tenant_id": tenant.id, "client_named_id": app_settings.default_client_name},
            missing_ok=True,
        )

        return tenant, tenant_client

    async def _create_user_from_keycloak(
        self,
        keycloak_user: Dict,
        tenant_client: TenantClient,
        tenant: Tenant,
        realm_name: str,
    ) -> UserModel:
        """Create database user from Keycloak user data.

        Similar to _create_user_from_oauth() but for Keycloak-native users.
        Derives user_type and role from Keycloak realm roles.

        Args:
            keycloak_user: User data from Keycloak
            tenant_client: Tenant client for the realm
            tenant: Tenant object for the realm (passed to avoid redundant DB query)
            realm_name: Realm name

        Returns:
            Created UserModel instance
        """
        email = keycloak_user.get("email")
        keycloak_user_id = keycloak_user.get("id")
        first_name = keycloak_user.get("firstName", "")
        last_name = keycloak_user.get("lastName", "")
        name = f"{first_name} {last_name}".strip() or email.split("@")[0]

        # Fetch user's Keycloak realm roles to determine permissions
        keycloak_manager = KeycloakManager()
        realm_roles = keycloak_manager.get_user_realm_roles(keycloak_user_id, realm_name)
        logger.info(f"Keycloak user {email} has roles: {realm_roles}")

        # Use helper method to determine permissions from roles
        # Handle case where role fetch returns None (error case)
        if realm_roles is not None:
            user_type, role, is_superuser = self._determine_user_permissions_from_roles(realm_roles)
        else:
            # Default to CLIENT/DEVELOPER on error (safe default for new users)
            logger.warning(f"Failed to fetch roles for {email} during JIT provisioning, using default permissions")
            user_type = UserTypeEnum.CLIENT.value
            role = UserRoleEnum.DEVELOPER.value
            is_superuser = False

        logger.info(
            f"JIT provisioning user {email} as user_type={user_type}, role={role}, is_superuser={is_superuser}"
        )

        # Create user with derived permissions
        new_user = UserModel(
            name=name,
            email=email,
            auth_id=keycloak_user_id,
            user_type=user_type,
            role=role,
            status=UserStatusEnum.ACTIVE.value,
            color=UserColorEnum.get_random_color(),
            first_login=True,
            is_reset_password=False,  # Keycloak manages password
            is_superuser=is_superuser,
        )

        created_user = await UserDataManager(self.session).insert_one(new_user)
        logger.info(f"Created user {email} via JIT provisioning with ID {created_user.id}")

        # Create tenant-user mapping (using passed tenant to avoid redundant query)

        tenant_user_mapping = TenantUserMapping(
            tenant_id=tenant.id,
            user_id=created_user.id,
        )
        await UserDataManager(self.session).insert_one(tenant_user_mapping)
        logger.info(f"Created tenant-user mapping for {email}")

        # Create notification subscriber
        try:
            subscriber_data = SubscriberCreate(
                subscriber_id=str(created_user.id),
                email=created_user.email,
                first_name=created_user.name,
            )
            await BudNotifyHandler().create_subscriber(subscriber_data)
            logger.info(f"User {created_user.email} added to budnotify subscriber")

            _ = await UserDataManager(self.session).update_subscriber_status(
                user_ids=[created_user.id], is_subscriber=True
            )
        except Exception as e:
            logger.error(f"Failed to create subscriber for {created_user.email}: {e}")
            # Don't fail JIT if subscriber creation fails

        # Use UserOnboardingService for billing, project, and permissions
        onboarding_service = UserOnboardingService(self.session)
        await onboarding_service.setup_new_client_user(
            user=created_user,
            tenant=tenant,
            tenant_client=tenant_client,
        )
        logger.info(f"Completed onboarding setup for {created_user.email}")

        return created_user

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

            keycloak_manager = KeycloakManager()
            # Decrypt client secret for use
            decrypted_secret = await tenant_client.get_decrypted_client_secret()
            credentials = TenantClientSchema(
                id=tenant_client.id,
                client_id=tenant_client.client_id,
                client_named_id=tenant_client.client_named_id,
                client_secret=decrypted_secret,
            )

            # Refresh Token
            token_data = await keycloak_manager.refresh_token(
                realm_name=tenant.realm_name,
                credentials=credentials,
                refresh_token=token.refresh_token,
            )

            return RefreshTokenResponse(
                code=status.HTTP_200_OK,
                message="Token refreshed successfully",
                token=token_data,
            )
        except Exception as e:
            logger.error(f"Failed to refresh token: {e}")
            raise ClientException("Failed to refresh token") from e

    async def logout_user(self, logout_data: LogoutRequest, access_token: str | None = None) -> None:
        """Logout a user by invalidating their refresh token and blacklisting access token."""
        # Blacklist the access token if provided
        if access_token:
            try:
                jwt_blacklist_service = JWTBlacklistService()
                import time

                # Try to decode the token to get its expiration
                ttl = 3600  # Default 1 hour TTL

                try:
                    # Get default tenant for token validation
                    default_tenant = await UserDataManager(self.session).retrieve_by_fields(
                        Tenant, {"realm_name": app_settings.default_realm_name, "is_active": True}, missing_ok=True
                    )
                    if default_tenant:
                        tenant_client = await UserDataManager(self.session).retrieve_by_fields(
                            TenantClient, {"tenant_id": default_tenant.id}, missing_ok=True
                        )
                        if tenant_client:
                            # Decrypt client secret for use
                            decrypted_secret = await tenant_client.get_decrypted_client_secret()
                            credentials = TenantClientSchema(
                                id=tenant_client.id,
                                client_named_id=tenant_client.client_named_id,
                                client_id=tenant_client.client_id,
                                client_secret=decrypted_secret,
                            )
                            keycloak_manager = KeycloakManager()
                            decoded = await keycloak_manager.validate_token(
                                access_token, default_tenant.realm_name, credentials
                            )
                            # Calculate TTL based on token expiration
                            exp = decoded.get("exp", 0)
                            current_time = int(time.time())
                            if exp > current_time:
                                ttl = exp - current_time
                except Exception as e:
                    logger.warning(f"Could not decode access token for TTL calculation: {e}")
                    # Continue with default TTL

                # Add token to blacklist with TTL using Dapr state store
                await jwt_blacklist_service.blacklist_token(access_token, ttl=ttl)
                logger.info(f"Access token blacklisted with TTL {ttl} seconds")
            except Exception as e:
                logger.error(f"Failed to blacklist access token: {e}")
                # Continue with logout even if blacklisting fails
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
        # Decrypt client secret for use
        decrypted_secret = await tenant_client.get_decrypted_client_secret()
        credentials = TenantClientSchema(
            id=tenant_client.id,
            client_id=tenant_client.client_id,
            client_named_id=tenant_client.client_named_id,
            client_secret=decrypted_secret,
        )

        success = await keycloak_manager.logout_user(
            refresh_token=logout_data.refresh_token, realm_name=tenant.realm_name, credentials=credentials
        )

        if not success:
            raise ClientException("Failed to logout user")

    async def register_user(self, user: UserCreate, is_self_registration: bool = False) -> UserModel:
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
                # Assign all client permissions
                client_permissions = [
                    PermissionList(name=PermissionEnum.CLIENT_ACCESS, has_permission=True),
                    PermissionList(name=PermissionEnum.PROJECT_VIEW, has_permission=True),
                    PermissionList(name=PermissionEnum.PROJECT_MANAGE, has_permission=True),
                ]

                if user.permissions:
                    # Add to existing permissions if not already present
                    existing_permission_names = {p.name for p in user.permissions}
                    for client_perm in client_permissions:
                        if client_perm.name not in existing_permission_names:
                            user.permissions.append(client_perm)
                else:
                    # Set client permissions for client users
                    user.permissions = client_permissions
                logger.debug(
                    "Assigned client permissions (CLIENT_ACCESS, PROJECT_VIEW, PROJECT_MANAGE) to client user: %s",
                    user.email,
                )

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

            # Hash password - CRITICAL: Never store plain text passwords!
            if hasattr(user, "password") and user.password:
                salted_password = user.password + secrets_settings.password_salt
                hashed_password = await HashManager().get_hash(salted_password)
                logger.info(f"Password hashed for {user.email}")
            else:
                hashed_password = None

            user_data = user.model_dump(exclude={"permissions", "password"})
            if hashed_password:
                user_data["password"] = hashed_password
            user_data["color"] = UserColorEnum.get_random_color()

            # Self-registered users are active immediately, admin-created users are invited
            user_data["status"] = UserStatusEnum.ACTIVE if is_self_registration else UserStatusEnum.INVITED

            user_model = UserModel(**user_data)
            user_model.auth_id = user_auth_id

            # Users who register themselves set their own password, so no reset needed
            # Admin-created users should reset their password on first login
            user_model.is_reset_password = not is_self_registration

            # NOTE: first_login will be set to True by default
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

            # Assign free billing plan for CLIENT users
            if user.user_type == UserTypeEnum.CLIENT:
                try:
                    from datetime import datetime, timezone
                    from uuid import uuid4

                    from budapp.billing_ops.models import UserBilling

                    # Calculate billing period (monthly)
                    now = datetime.now(timezone.utc)
                    billing_period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

                    # Get next month
                    if billing_period_start.month == 12:
                        billing_period_end = billing_period_start.replace(year=billing_period_start.year + 1, month=1)
                    else:
                        billing_period_end = billing_period_start.replace(month=billing_period_start.month + 1)

                    # Create user billing with free plan
                    user_billing = UserBilling(
                        id=uuid4(),
                        user_id=db_user.id,
                        billing_plan_id=UUID("00000000-0000-0000-0000-000000000001"),  # Free plan ID
                        billing_period_start=billing_period_start,
                        billing_period_end=billing_period_end,
                        is_active=True,
                        is_suspended=False,
                    )

                    await UserDataManager(self.session).insert_one(user_billing)
                    logger.info(f"Free billing plan assigned to client user: {db_user.email}")

                except Exception as billing_error:
                    logger.error(f"Failed to assign billing plan to user {db_user.email}: {billing_error}")
                    # Don't fail the registration if billing assignment fails

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
                    self.session.commit()

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

            try:
                await BudNotifyHandler().create_subscriber(subscriber_data)
                logger.info("User added to budnotify subscriber")

                _ = await UserDataManager(self.session).update_subscriber_status(
                    user_ids=[db_user.id], is_subscriber=True
                )
            except BudNotifyException as e:
                logger.error(
                    f"Failed to add user to budnotify subscribers for {db_user.email}, but user registration is successful: {e}"
                )

            return db_user

        except Exception as e:
            logger.error(f"Failed to register user: {e}")
            raise ClientException(message="Failed to register user")

        except BudNotifyException as e:
            logger.error(f"Failed to add user to budnotify subscribers: {e}")
