import json

from sqlalchemy.orm import Session

from budapp.commons import logging
from budapp.commons.config import app_settings, secrets_settings
from budapp.commons.constants import (
    PermissionEnum,
    UserColorEnum,
    UserRoleEnum,
    UserStatusEnum,
)
from budapp.commons.database import engine
from budapp.commons.security import HashManager
from budapp.permissions.crud import PermissionDataManager
from budapp.permissions.models import Permission as PermissionModel
from budapp.user_ops.crud import UserDataManager
from budapp.user_ops.models import User as UserModel

from .base_seeder import BaseSeeder


logger = logging.get_logger(__name__)


class UserSeeder(BaseSeeder):
    """User seeder."""

    async def seed(self) -> None:
        """Seed admin user to the database."""
        with Session(engine) as session:
            try:
                await self._create_manage_super_user(session)
            except Exception as e:
                logger.error(f"Failed to create super user. Error: {e}")

    @staticmethod
    async def _create_manage_super_user(session: Session) -> None:
        """Create super user if it doesn't exist. Add permissions to super user if it doesn't added."""
        # Check whether super user exists or not
        db_user = await UserDataManager(session).retrieve_by_fields(
            UserModel,
            {"email": app_settings.superuser_email, "status": UserStatusEnum.ACTIVE, "is_superuser": True},
            missing_ok=True,
        )

        if not db_user:
            # Create super user
            salted_password = app_settings.superuser_password + secrets_settings.password_salt
            hashed_password = await HashManager().get_hash(salted_password)
            super_user = UserModel(
                name="admin",
                email=app_settings.superuser_email,
                password=hashed_password,
                is_superuser=True,
                color=UserColorEnum.get_random_color(),
                is_reset_password=False,
                first_login=True,
                status=UserStatusEnum.ACTIVE.value,
                role=UserRoleEnum.SUPER_ADMIN.value,
            )
            db_user = await UserDataManager(session).insert_one(super_user)
            logger.debug("Inserted super user in database")

            # Add permissions to super user
            scopes = PermissionEnum.get_global_permissions()
            permissions = PermissionModel(
                user_id=super_user.id,
                auth_id=super_user.auth_id,
                scopes=json.dumps(scopes),
            )
            db_permissions = await PermissionDataManager(session).insert_one(permissions)
            logger.debug("Inserted permissions to super user in database")
        else:
            logger.debug("Found super user in database")
            scopes = PermissionEnum.get_global_permissions()

            # Check whether super user permissions are added or not
            db_permissions = await PermissionDataManager(session).retrieve_by_fields(
                PermissionModel,
                {"user_id": db_user.id, "auth_id": db_user.auth_id},
                missing_ok=True,
            )

            if db_permissions:
                logger.debug("Found permissions of super user in database")

                # Update super user permissions
                db_permissions = await PermissionDataManager(session).update_by_fields(
                    db_permissions, {"scopes": json.dumps(scopes)}
                )

                logger.debug("Updated permissions of super user in database")
            else:
                logger.debug("Permissions of super user not found in database")
                permissions = PermissionModel(
                    user_id=db_user.id,
                    auth_id=db_user.auth_id,
                    scopes=json.dumps(scopes),
                )

                # Add permissions to super user
                db_permissions = await PermissionDataManager(session).insert_one(permissions)
                logger.debug("Added permissions to super user")
