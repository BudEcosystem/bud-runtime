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
        """Set up billing and create default project for new CLIENT users.

        This method consolidates the common logic for setting up new CLIENT users,
        including:
        - Assigning the default free billing plan
        - Creating a default project
        - Setting up project permissions in Keycloak

        Args:
            user: The newly created user
            tenant: The tenant the user belongs to
            tenant_client: The tenant client configuration (optional)
        """
        # Only process CLIENT users
        if user.user_type != UserTypeEnum.CLIENT:
            logger.info(f"Skipping onboarding for non-CLIENT user {user.email} (type: {user.user_type})")
            return

        logger.info(f"Starting onboarding for CLIENT user {user.email}")

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

        logger.info(f"Completed onboarding for CLIENT user {user.email}")

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
        """Set up project permissions in Keycloak for a user.

        Args:
            user: The user to grant permissions to
            project: The project to set permissions for
            tenant: The tenant
            tenant_client: The tenant client configuration
        """
        try:
            # Create permissions for the project in Keycloak
            payload = ResourceCreate(
                resource_id=str(project.id),
                resource_type="project",
                scopes=["view", "manage"],
            )

            await self.permission_service.create_resource(
                payload,
                str(user.auth_id),
                tenant.realm_name,
                tenant_client.client_id,
            )

            # Grant permissions to the user
            project_users = ProjectUserAdd(
                project_id=project.id,
                user_id=user.id,
                permissions=[
                    PermissionList(name=PermissionEnum.PROJECT_VIEW, has_permission=True),
                    PermissionList(name=PermissionEnum.PROJECT_MANAGE, has_permission=True),
                ],
            )

            await self.permission_service.grant_permissions(
                project_users,
                str(user.auth_id),
                tenant.realm_name,
                tenant_client.client_id,
            )

            logger.info(f"Project permissions granted for user: {user.email} on project: {project.id}")

        except Exception as e:
            logger.error(f"Failed to set up project permissions for user {user.email}: {e}")
            # Don't rollback here as the project is already created
            # Permissions can be fixed manually if needed

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
