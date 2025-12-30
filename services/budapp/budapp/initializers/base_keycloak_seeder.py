from keycloak.exceptions import KeycloakPostError
from sqlalchemy.orm import Session

from budapp.commons import logging
from budapp.commons.config import app_settings
from budapp.commons.constants import UserColorEnum, UserRoleEnum, UserStatusEnum, UserTypeEnum
from budapp.commons.database import engine
from budapp.commons.exceptions import DatabaseException
from budapp.commons.keycloak import KeycloakManager
from budapp.initializers.base_seeder import BaseSeeder
from budapp.user_ops.crud import UserDataManager
from budapp.user_ops.models import Tenant, TenantClient, TenantUserMapping
from budapp.user_ops.models import User as UserModel


logger = logging.get_logger(__name__)


class BaseKeycloakSeeder(BaseSeeder):
    """Base class for keycloak seeder."""

    async def seed(self):
        """Seed the keycloak."""
        with Session(engine) as session:
            try:
                await self._seed_keycloak(session)
            except Exception as e:
                import traceback

                logger.error(f"Error during seeding: {traceback.format_exc()}")
                logger.error(f"Failed to complete seeding. Error: {e}")

    @staticmethod
    async def _seed_keycloak(session: Session) -> None:
        """Seed the keycloak."""
        # Get the keycloak admin client
        keycloak_manager = KeycloakManager()

        # Get the default realm name
        default_realm_name = app_settings.default_realm_name
        default_client_id = app_settings.default_client_name

        # Check if realm exists in Keycloak
        keycloak_realm_exists = keycloak_manager.realm_exists(default_realm_name)

        # Check if user exists in DB
        db_user = await UserDataManager(session).retrieve_by_fields(
            UserModel,
            {"email": app_settings.superuser_email, "status": UserStatusEnum.ACTIVE, "is_superuser": True},
            missing_ok=True,
        )

        # If both exist, we still need to sync permissions
        if keycloak_realm_exists and db_user:
            logger.info(
                f"::KEYCLOAK::Realm {default_realm_name} and user {app_settings.superuser_email} both exist. Syncing permissions..."
            )

            # Sync realm settings (token lifespans, session timeouts) for existing realm
            await keycloak_manager.sync_realm_settings(default_realm_name)

            # Get tenant client info to sync permissions
            tenant_client = await UserDataManager(session).retrieve_by_fields(
                TenantClient,
                {"tenant_id": db_user.id, "client_named_id": default_client_id},
                missing_ok=True,
            )

            if not tenant_client:
                # Try to get tenant info first
                tenant = await UserDataManager(session).retrieve_by_fields(
                    Tenant,
                    {"realm_name": default_realm_name},
                    missing_ok=True,
                )

                if tenant:
                    tenant_client = await UserDataManager(session).retrieve_by_fields(
                        TenantClient,
                        {"tenant_id": tenant.id, "client_named_id": default_client_id},
                        missing_ok=True,
                    )

            if tenant_client:
                # Verify client exists in Keycloak before syncing permissions
                if not keycloak_manager.client_exists(tenant_client.client_id, default_realm_name):
                    logger.warning(
                        f"::KEYCLOAK::Client {default_client_id} record exists in DB but not in Keycloak. Creating..."
                    )
                    # Create the client in Keycloak
                    new_client_id, client_secret = await keycloak_manager.create_client(
                        default_client_id, default_realm_name
                    )
                    # Update the tenant_client record with new client info
                    tenant_client.client_id = new_client_id
                    await tenant_client.set_client_secret(client_secret)
                    UserDataManager(session).update_one(tenant_client)
                    logger.info(f"::KEYCLOAK::Client created with ID {new_client_id}")

                # Verify user exists in Keycloak before syncing permissions
                if not keycloak_manager.user_exists_in_realm(str(db_user.auth_id), default_realm_name):
                    logger.warning(
                        f"::KEYCLOAK::User {db_user.email} (auth_id: {db_user.auth_id}) exists in DB but not in Keycloak. Creating..."
                    )

                    # Ensure realm has required roles before creating admin user
                    await keycloak_manager.ensure_realm_roles_exist(default_realm_name)

                    # Create user in Keycloak
                    decrypted_secret = await tenant_client.get_decrypted_client_secret()
                    keycloak_user_id = await keycloak_manager.create_realm_admin(
                        username=db_user.email,
                        email=db_user.email,
                        password=app_settings.superuser_password,
                        realm_name=default_realm_name,
                        client_id=tenant_client.client_id,
                        client_secret=decrypted_secret,
                    )
                    # Update the user record with new Keycloak ID
                    db_user.auth_id = keycloak_user_id
                    UserDataManager(session).update_one(db_user)
                    logger.info(f"::KEYCLOAK::User created in Keycloak with new auth_id {keycloak_user_id}")

                # Sync permissions for the super user
                await keycloak_manager.sync_user_permissions(
                    user_id=db_user.auth_id,
                    realm_name=default_realm_name,
                    client_id=tenant_client.client_id,
                )
                logger.info("::KEYCLOAK::Permissions synced for super user")
            else:
                logger.warning("::KEYCLOAK::Could not find tenant client info to sync permissions")

            return

        # Create realm in Keycloak if it doesn't exist
        if not keycloak_realm_exists:
            logger.debug(f"::KEYCLOAK::Realm {default_realm_name} does not exist. Creating...")
            await keycloak_manager.create_realm(default_realm_name)

        # Check if tenant exists in database
        tenant = await UserDataManager(session).retrieve_by_fields(
            Tenant,
            {"realm_name": default_realm_name},
            missing_ok=True,
        )

        if not tenant:
            # Save The Tenant in DB if it doesn't exist
            tenant = Tenant(
                name="Default Tenant",
                realm_name=default_realm_name,
                tenant_identifier=default_realm_name,
                description="Default tenant for superuser",
                is_active=True,
            )
            tenant = await UserDataManager(session).insert_one(tenant)
            logger.info(f"::KEYCLOAK::Tenant created in DB with ID {tenant.id}")
        else:
            logger.info(f"::KEYCLOAK::Tenant already exists in DB with ID {tenant.id}")

        # Check if the client exists for the tenant
        tenant_client = await UserDataManager(session).retrieve_by_fields(
            TenantClient,
            {"tenant_id": tenant.id, "client_named_id": default_client_id},
            missing_ok=True,
        )

        # Check if TenantClient needs to be created
        if not tenant_client:
            # Client doesn't exist in DB - need to create it
            if not keycloak_realm_exists:
                # Realm was just created - create client in Keycloak
                logger.debug(f"::KEYCLOAK::Creating client {default_client_id} in newly created realm")
                new_client_id, client_secret = await keycloak_manager.create_client(
                    default_client_id, default_realm_name
                )
            else:
                # Realm already exists - try to create client in Keycloak
                logger.info(
                    "::KEYCLOAK::Realm exists but no client record in DB. Attempting to create client in Keycloak..."
                )

                try:
                    # Try to create the client - this will fail if client already exists
                    new_client_id, client_secret = await keycloak_manager.create_client(
                        default_client_id, default_realm_name
                    )
                    logger.info(f"::KEYCLOAK::Client {default_client_id} created in existing realm")
                except KeycloakPostError as e:
                    # Check if error is due to client already existing
                    error_message = str(e)
                    if (
                        "409" in error_message
                        or "Conflict" in error_message
                        or "already exists" in error_message.lower()
                    ):
                        # Client already exists in Keycloak but not in DB - inconsistent state
                        logger.error(
                            f"::KEYCLOAK::Client {default_client_id} already exists in Keycloak but not in database. "
                            "This is an inconsistent state. Cannot retrieve existing client secret from Keycloak."
                        )
                        raise DatabaseException(
                            f"Client '{default_client_id}' exists in Keycloak but not in database. "
                            "Please delete the client in Keycloak admin console and restart the application, "
                            "or manually sync the client credentials to the database."
                        )
                    else:
                        # Some other error - re-raise it
                        logger.error(f"::KEYCLOAK::Failed to create client in Keycloak: {e}")
                        raise

            # Create TenantClient record in DB with encrypted secret
            tenant_client = TenantClient(
                tenant_id=tenant.id,
                client_named_id=default_client_id,
                client_id=new_client_id,
            )
            # Encrypt the client secret before storage
            await tenant_client.set_client_secret(client_secret)
            await UserDataManager(session).insert_one(tenant_client)
            logger.info(f"::KEYCLOAK::Client created in DB with ID {tenant_client.id} and encrypted secret")
        else:
            # TenantClient already exists in DB
            logger.info(f"::KEYCLOAK::Client already exists in DB with ID {tenant_client.id}")

            # If realm was just created but client exists in DB, update with new Keycloak credentials
            if not keycloak_realm_exists:
                logger.warning(
                    "::KEYCLOAK::Client record exists in DB but realm was just created. "
                    "Creating client in Keycloak and updating DB record..."
                )
                new_client_id, client_secret = await keycloak_manager.create_client(
                    default_client_id, default_realm_name
                )
                tenant_client.client_id = new_client_id
                await tenant_client.set_client_secret(client_secret)
                UserDataManager(session).update_one(tenant_client)
                logger.info(f"::KEYCLOAK::Client updated in DB with ID {tenant_client.id} and encrypted secret")

        # If realm was just created or user doesn't exist, create user in Keycloak
        if not keycloak_realm_exists or not db_user:
            if keycloak_realm_exists and not db_user:
                logger.info(
                    f"::KEYCLOAK::Realm exists but user {app_settings.superuser_email} doesn't exist. Creating user..."
                )

            # Create user in Keycloak
            # Decrypt client secret for Keycloak API call
            decrypted_secret = await tenant_client.get_decrypted_client_secret()
            keycloak_user_id = await keycloak_manager.create_realm_admin(
                username=app_settings.superuser_email,
                email=app_settings.superuser_email,
                password=app_settings.superuser_password,
                realm_name=default_realm_name,
                client_id=tenant_client.client_id,
                client_secret=decrypted_secret,
            )

            if not db_user:
                # Create new user record in DB
                db_user = UserModel(
                    name="admin",
                    auth_id=keycloak_user_id,
                    email=app_settings.superuser_email,
                    is_superuser=True,
                    color=UserColorEnum.get_random_color(),
                    is_reset_password=False,
                    first_login=True,
                    status=UserStatusEnum.ACTIVE.value,
                    role=UserRoleEnum.SUPER_ADMIN.value,
                    user_type=UserTypeEnum.ADMIN.value,
                )
                db_user = await UserDataManager(session).insert_one(db_user)
                logger.info(f"::KEYCLOAK::User created in DB with ID {db_user.id}")

                # Add user to tenant mapping
                tenant_user_mapping = await UserDataManager(session).retrieve_by_fields(
                    TenantUserMapping,
                    {"tenant_id": tenant.id, "user_id": db_user.id},
                    missing_ok=True,
                )

                if not tenant_user_mapping:
                    tenant_user_mapping = TenantUserMapping(
                        tenant_id=tenant.id,
                        user_id=db_user.id,
                    )
                    await UserDataManager(session).insert_one(tenant_user_mapping)
                    logger.info("::KEYCLOAK::User-Tenant mapping created")
            else:
                # Update existing user record with new Keycloak ID
                db_user.auth_id = keycloak_user_id
                UserDataManager(session).update_one(db_user)
                logger.info("::KEYCLOAK::User updated in DB with new auth_id")

        logger.info("::KEYCLOAK::Seeding completed successfully")
