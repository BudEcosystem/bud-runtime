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

"""User onboarding service for new user setup."""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import Session

from budapp.auth.schemas import ResourceCreate
from budapp.billing_ops.models import BillingPlan, UserBilling
from budapp.commons import logging
from budapp.commons.constants import (
    PermissionEnum,
    ProjectStatusEnum,
    ProjectTypeEnum,
    UserTypeEnum,
)
from budapp.commons.keycloak import KeycloakManager
from budapp.permissions.schemas import PermissionList
from budapp.permissions.service import PermissionService
from budapp.project_ops.models import Project as ProjectModel
from budapp.project_ops.schemas import ProjectUserAdd
from budapp.user_ops.crud import UserDataManager
from budapp.user_ops.models import Tenant, TenantClient, User


logger = logging.get_logger(__name__)


class UserOnboardingService:
    """Service for handling new user onboarding tasks."""

    def __init__(self, session: Session):
        """Initialize the user onboarding service.

        Args:
            session: Database session
        """
        self.session = session
        self.data_manager = UserDataManager(session)
        self.permission_service = PermissionService(session)

    async def setup_new_client_user(
        self,
        user: User,
        tenant: Tenant,
        tenant_client: Optional[TenantClient] = None,
    ) -> None:
        """Set up billing, projects, and permissions for new users.

        This method handles onboarding for both CLIENT and ADMIN users:
        - CLIENT users: billing + default project + permissions
        - ADMIN users: only permissions (no billing, no project)

        Args:
            user: The newly created user
            tenant: The tenant the user belongs to
            tenant_client: The tenant client configuration (optional)
        """
        logger.info(f"Starting onboarding for {user.user_type} user {user.email}")

        if user.user_type == UserTypeEnum.CLIENT:
            # CLIENT user setup: billing + project + permissions
            # Step 1: Assign default billing plan
            await self._assign_default_billing_plan(user)

            # Step 2: Create default project
            project = await self._create_default_project(user)

            # Step 3: Set up project permissions in Keycloak
            if project and tenant_client and user.auth_id:
                await self._setup_project_permissions(
                    user=user,
                    project=project,
                    tenant=tenant,
                    tenant_client=tenant_client,
                )

        elif user.user_type == UserTypeEnum.ADMIN:
            # ADMIN user setup: only permissions (no billing, no project)
            if tenant_client and user.auth_id:
                await self._setup_admin_permissions(
                    user=user,
                    tenant=tenant,
                    tenant_client=tenant_client,
                )
        else:
            logger.warning(f"Unknown user type {user.user_type} for user {user.email}, skipping onboarding")
            return

        logger.info(f"Completed onboarding for {user.user_type} user {user.email}")

    async def _assign_default_billing_plan(self, user: User) -> Optional[UserBilling]:
        """Assign the default free billing plan to a new user.

        Args:
            user: The user to assign billing to

        Returns:
            The created UserBilling record, or None if failed
        """
        try:
            # Check if user already has billing
            existing_billing = await self.data_manager.retrieve_by_fields(
                UserBilling, {"user_id": user.id}, missing_ok=True
            )

            if existing_billing:
                logger.info(f"User {user.email} already has billing plan, skipping assignment")
                return existing_billing

            # Get the default free plan by name
            free_plan = await self.data_manager.retrieve_by_fields(BillingPlan, {"name": "Free"}, missing_ok=True)

            if not free_plan:
                # Try with a default UUID (backward compatibility)
                free_plan_id = UUID("00000000-0000-0000-0000-000000000001")
                logger.warning(f"Free plan not found by name, using default ID: {free_plan_id}")
            else:
                free_plan_id = free_plan.id

            # Calculate billing period (monthly)
            now = datetime.now(timezone.utc)
            billing_period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            # Calculate next month using dateutil for proper month handling
            billing_period_end = billing_period_start + relativedelta(months=1)

            # Create user billing with free plan
            user_billing = UserBilling(
                id=uuid4(),
                user_id=user.id,
                billing_plan_id=free_plan_id,
                billing_period_start=billing_period_start,
                billing_period_end=billing_period_end,
                is_active=True,
                is_suspended=False,
            )

            self.data_manager.add_one(user_billing)
            self.session.commit()
            logger.info(f"Free billing plan assigned to user: {user.email}")
            return user_billing

        except Exception as e:
            logger.error(f"Failed to assign billing plan to user {user.email}: {e}")
            self.session.rollback()
            return None

    async def _create_default_project(self, user: User) -> Optional[ProjectModel]:
        """Create a default project for a new user.

        Args:
            user: The user to create a project for

        Returns:
            The created project, or None if failed
        """
        try:
            # Create default project for the client user
            default_project = ProjectModel(
                name="My First Project",
                description="This is your default project. You can start by creating models and endpoints here.",
                created_by=user.id,
                status=ProjectStatusEnum.ACTIVE,
                benchmark=False,
                project_type=ProjectTypeEnum.CLIENT_APP.value,
            )

            # Insert the project into database
            self.data_manager.add_one(default_project)
            logger.info(f"Default project created for user: {user.email}")

            # Associate the user with the project
            default_project.users.append(user)
            self.session.commit()

            logger.info(f"User {user.email} associated with default project {default_project.id}")
            return default_project

        except Exception as e:
            logger.error(f"Failed to create default project for user {user.email}: {e}")
            self.session.rollback()
            return None

    async def _setup_project_permissions(
        self,
        user: User,
        project: ProjectModel,
        tenant: Tenant,
        tenant_client: TenantClient,
    ) -> None:
        """Set up module and project permissions in Keycloak for a JIT provisioned user.

        This method sets up permissions for users created via JIT (Just-In-Time) provisioning
        from Keycloak. Since these users already exist in Keycloak but lack application permissions,
        we need to:
        1. Create/update module-level permissions (CLIENT_ACCESS, PROJECT_VIEW, PROJECT_MANAGE)
        2. Create project-specific resource permissions in Keycloak

        Args:
            user: The user to grant permissions to
            project: The project to set permissions for
            tenant: The tenant
            tenant_client: The tenant client configuration
        """
        try:
            keycloak_manager = KeycloakManager()

            # Step 1: Set up module-level permissions for CLIENT users
            # These are the same default permissions assigned during registration
            logger.info(f"Setting up module-level permissions for user {user.email}")

            module_permissions = [
                {"name": "client:access", "has_permission": True},  # CLIENT_ACCESS
                {"name": "project:view", "has_permission": True},  # PROJECT_VIEW
                {"name": "project:manage", "has_permission": True},  # PROJECT_MANAGE
            ]

            await keycloak_manager.update_user_global_permissions(
                user_auth_id=str(user.auth_id),
                permissions=module_permissions,
                realm_name=tenant.realm_name,
                client_id=tenant_client.client_id,
            )

            logger.info(f"Module-level permissions set for user {user.email}")

            # Step 2: Create project-specific resource permissions
            # This creates the project resource in Keycloak and links it to the user's policy
            logger.info(f"Creating project resource permissions for user {user.email} on project {project.id}")

            payload = ResourceCreate(
                resource_id=str(project.id),
                resource_type="project",
                scopes=["view", "manage"],
            )

            # Use the working method from PermissionService (same as registration flow)
            await self.permission_service.create_resource_permission_by_user(user, payload)

            logger.info(
                f"Permissions successfully set up for user {user.email}: "
                f"module permissions (CLIENT_ACCESS, PROJECT_VIEW, PROJECT_MANAGE) and "
                f"project {project.id} permissions (view, manage)"
            )

        except Exception as e:
            logger.error(f"Failed to set up permissions for user {user.email}: {e}", exc_info=True)
            # Re-raise to alert that permissions failed - this is critical for user functionality
            raise RuntimeError(
                f"Permission setup failed for user {user.email}. "
                f"User cannot access the application without proper permissions. Error: {str(e)}"
            )

    async def _setup_admin_permissions(
        self,
        user: User,
        tenant: Tenant,
        tenant_client: TenantClient,
    ) -> None:
        """Set up module permissions in Keycloak for ADMIN users.

        This method grants ADMIN users all module-level permissions they need to
        manage the application, including models, projects, endpoints, clusters,
        users, and benchmarks.

        Args:
            user: The ADMIN user to grant permissions to
            tenant: The tenant
            tenant_client: The tenant client configuration
        """
        try:
            keycloak_manager = KeycloakManager()

            logger.info(f"Setting up ADMIN permissions for user {user.email}")

            # Grant all module permissions for ADMIN users
            admin_permissions = [
                {"name": "model:view", "has_permission": True},
                {"name": "model:manage", "has_permission": True},
                {"name": "project:view", "has_permission": True},
                {"name": "project:manage", "has_permission": True},
                {"name": "endpoint:view", "has_permission": True},
                {"name": "endpoint:manage", "has_permission": True},
                {"name": "cluster:view", "has_permission": True},
                {"name": "cluster:manage", "has_permission": True},
                {"name": "user:view", "has_permission": True},
                {"name": "user:manage", "has_permission": True},
                {"name": "benchmark:view", "has_permission": True},
                {"name": "benchmark:manage", "has_permission": True},
            ]

            await keycloak_manager.update_user_global_permissions(
                user_auth_id=str(user.auth_id),
                permissions=admin_permissions,
                realm_name=tenant.realm_name,
                client_id=tenant_client.client_id,
            )

            logger.info(
                f"ADMIN permissions successfully set up for user {user.email}: "
                f"All module permissions (model, project, endpoint, cluster, user, benchmark)"
            )

        except Exception as e:
            logger.error(f"Failed to set up ADMIN permissions for user {user.email}: {e}", exc_info=True)
            # Re-raise to alert that permissions failed - this is critical for user functionality
            raise RuntimeError(
                f"ADMIN permission setup failed for user {user.email}. "
                f"User cannot access the application without proper permissions. Error: {str(e)}"
            )

    async def onboard_user_by_email(
        self,
        user_email: str,
        tenant_realm: Optional[str] = None,
    ) -> bool:
        """Onboard a user by email address.

        This is a convenience method for onboarding users after they've been created,
        such as in OAuth flows where the user is created first and then onboarded.

        Args:
            user_email: Email address of the user to onboard
            tenant_realm: Optional tenant realm name (defaults to default realm)

        Returns:
            True if onboarding was successful, False otherwise
        """
        try:
            # Get the user
            user = await self.data_manager.retrieve_by_fields(User, {"email": user_email}, missing_ok=True)

            if not user:
                logger.error(f"User not found for onboarding: {user_email}")
                return False

            # Get tenant
            if tenant_realm:
                tenant = await self.data_manager.retrieve_by_fields(
                    Tenant, {"realm_name": tenant_realm}, missing_ok=True
                )
            else:
                # Use default tenant
                from budapp.commons.config import app_settings

                tenant = await self.data_manager.retrieve_by_fields(
                    Tenant, {"realm_name": app_settings.default_realm_name}, missing_ok=True
                )

            if not tenant:
                logger.error(f"Tenant not found for onboarding user {user_email}")
                return False

            # Get tenant client if available
            tenant_client = await self.data_manager.retrieve_by_fields(
                TenantClient, {"tenant_id": tenant.id}, missing_ok=True
            )

            # Run onboarding
            await self.setup_new_client_user(user, tenant, tenant_client)
            return True

        except Exception as e:
            logger.error(f"Failed to onboard user {user_email}: {e}")
            return False
