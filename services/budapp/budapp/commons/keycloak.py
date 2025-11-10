# budapp/commons/keycloak.py

import base64
import json
import sys
from typing import Dict, List, Optional, Tuple, Union

import requests
from jwt.exceptions import ExpiredSignatureError
from jwt.exceptions import PyJWTError as JWTError
from keycloak import (
    KeycloakAdmin,
    KeycloakAuthenticationError,
    KeycloakGetError,
    KeycloakInvalidTokenError,
    KeycloakOpenID,
    KeycloakPostError,
)

from budapp.auth.schemas import ResourceCreate, UserCreate
from budapp.commons.constants import UserRoleEnum
from budapp.user_ops.schemas import TenantClientSchema

from . import logging
from .config import app_settings


logger = logging.get_logger(__name__)


class KeycloakManager:
    """Class to manage Keycloak operations including realms, clients, and users."""

    _instance: Optional["KeycloakManager"] = None
    _admin_client: Optional[KeycloakAdmin] = None

    def __new__(cls) -> "KeycloakManager":
        """Implement singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize the Keycloak manager with a singleton admin client."""
        if self._admin_client is None:
            self._admin_client = KeycloakAdmin(
                server_url=app_settings.keycloak_server_url,
                username=app_settings.keycloak_admin_username,
                password=app_settings.keycloak_admin_password,
                realm_name=app_settings.keycloak_realm_name,
                user_realm_name=app_settings.keycloak_realm_name,
                verify=app_settings.keycloak_verify_ssl,
            )

    @property
    def admin_client(self) -> KeycloakAdmin:
        """Get the admin client instance."""
        if self._admin_client is None:
            raise ValueError("KeycloakAdmin client not initialized")
        return self._admin_client

    def _get_base_url(self) -> str:
        """Get the base URL based on environment."""
        protocol = "https" if app_settings.env != "development" else "http"
        return f"{protocol}://{app_settings.api_root}"

    def get_realm_admin(self, realm_name: str) -> KeycloakAdmin:
        """Get the realm admin client.

        Args:
            realm_name: Name of the realm

        Returns:
            KeycloakAdmin instance for the specified realm
        """
        try:
            return KeycloakAdmin(
                server_url=app_settings.keycloak_server_url,
                username=app_settings.keycloak_admin_username,
                password=app_settings.keycloak_admin_password,
                realm_name=realm_name,
                user_realm_name=app_settings.keycloak_realm_name,
                verify=app_settings.keycloak_verify_ssl,
            )
        except Exception as e:
            logger.error(f"Failed to create realm admin for realm {realm_name}: {str(e)}")
            raise

    def get_keycloak_openid_client(self, realm_name: str, credentials: TenantClientSchema) -> KeycloakOpenID:
        """Get the keycloak openid client.

        Args:
            realm_name: Name of the realm
            credentials: The client credentials schema containing client_id and client_secret
        """
        return KeycloakOpenID(
            server_url=app_settings.keycloak_server_url,
            client_id=str(credentials.client_named_id),
            realm_name=realm_name,
            client_secret_key=credentials.client_secret,
            verify=app_settings.keycloak_verify_ssl,
        )

    async def update_user_password(self, user_id: str, password: str, realm_name: str) -> None:
        """Update a user's password in Keycloak.

        Args:
            user_id: The ID of the user to update
            password: The new password for the user

        Returns:
            None
        """
        try:
            realm_admin = self.get_realm_admin(realm_name)
            realm_admin.set_user_password(user_id=user_id, password=password, temporary=False)
        except Exception as e:
            logger.error(f"Error updating user password: {str(e)}")
            raise

    async def create_realm(self, realm_name: str) -> dict:
        """Create a new realm in Keycloak.

        Args:
            realm_name: Name of the realm to create

        Returns:
            dict: Created realm representation
        """
        realm_name = realm_name.lower()
        realm_representation = {
            "realm": realm_name,
            "enabled": True,
            "sslRequired": "external",
            "registrationAllowed": False,
            "loginWithEmailAllowed": True,
            "duplicateEmailsAllowed": False,
            "resetPasswordAllowed": True,
            "editUsernameAllowed": False,
            "bruteForceProtected": True,
            "refreshTokenMaxReuse": 0,  # Allow unlimited reuse of refresh tokens
            "ssoSessionIdleTimeout": 3600,  # 1 hour in seconds
            "ssoSessionMaxLifespan": 3600,  # 1 hour in seconds
            "offlineSessionIdleTimeout": 2592000,  # 30 days in seconds
            "offlineSessionMaxLifespan": 2592000,  # 30 days in seconds
        }

        try:
            self.admin_client.create_realm(payload=realm_representation, skip_exists=True)
            logger.info(f"Realm {realm_name} created successfully")

            # MAP Roles ad Groups
            relam_admin = self.get_realm_admin(realm_name)
            roles = [
                UserRoleEnum.ADMIN.value,
                UserRoleEnum.DEVELOPER.value,
                UserRoleEnum.TESTER.value,
                UserRoleEnum.DEVOPS.value,
                UserRoleEnum.SUPER_ADMIN.value,
            ]

            for role_name in roles:
                relam_admin.create_realm_role(
                    {"name": role_name, "description": f" Role: {role_name}"}, skip_exists=True
                )

            # Fetch Relm Info
            realm_info = self.admin_client.get_realm(realm_name)
            logger.info(f"Realm {realm_name} created successfully with info: {realm_info}")

            return realm_info

        except Exception as e:
            logger.error(f"Failed to create realm {realm_name}: {str(e)}")
            raise

    async def _create_module_resource(self, realm_admin, client_id: str, module_name: str, realm_name: str) -> str:
        """Create a module-level resource in Keycloak Authorization.

        Args:
            realm_admin: Instance of realm_admin
            client_id: Internal client UUID
            module_name: e.g. "cluster", "model"

        Returns:
            ID of the created resource
        """
        resource = {
            "name": f"module_{module_name}",
            "type": "module",
            "owner": {"id": client_id},
            "ownerManagedAccess": True,
            "displayName": f"{module_name.capitalize()} Module",
            "scopes": [{"name": "view"}, {"name": "manage"}],
        }

        resource_data = None
        existing_resources = realm_admin.get_client_authz_resources(client_id)
        for r in existing_resources:
            if r["name"] == resource["name"]:
                resource_data = r["_id"]
                break

        if not resource_data:
            resource_data = realm_admin.create_client_authz_resource(client_id, resource)

        # Create Permission For The Resource
        kc_scopes = realm_admin.get_client_authz_scopes(client_id)
        logger.debug(f"KC Scopes: {kc_scopes}")
        for scope in kc_scopes:
            permission = {
                "name": f"urn:bud:permission:{module_name}:module:{scope['name']}",
                "description": f"Permission for {module_name} to {scope['name']}",
                "resources": [resource_data["_id"]],
                "policies": [],
                "type": "scope",
                "logic": "POSITIVE",
                "scopes": [scope["id"]],
                "decisionStrategy": "AFFIRMATIVE",
            }
            logger.debug(f"Creating permission: {json.dumps(permission, indent=4)}")
            permission_url = f"{app_settings.keycloak_server_url}/admin/realms/{realm_name}/clients/{client_id}/authz/resource-server/permission/scope"
            data_raw = realm_admin.connection.raw_post(
                permission_url,
                data=json.dumps(permission),
                max=-1,
                permission=False,
            )

            logger.debug(f"Permission response: {data_raw.json()}")
            _ = data_raw.json()["id"]  # Permission created successfully

    def client_exists(self, client_id: str, realm_name: str) -> bool:
        """Check if a client exists in Keycloak by its internal UUID.

        Args:
            client_id: The internal UUID of the client to check
            realm_name: Name of the realm to check in

        Returns:
            bool: True if client exists, False otherwise
        """
        try:
            realm_admin = self.get_realm_admin(realm_name)
            realm_admin.get_client(client_id)
            return True
        except KeycloakGetError:
            return False

    def user_exists_in_realm(self, user_id: str, realm_name: str) -> bool:
        """Check if a user exists in Keycloak by their UUID.

        Args:
            user_id: The UUID of the user to check
            realm_name: Name of the realm to check in

        Returns:
            bool: True if user exists, False otherwise
        """
        try:
            realm_admin = self.get_realm_admin(realm_name)
            realm_admin.get_user(user_id)
            return True
        except KeycloakGetError:
            return False

    async def ensure_realm_roles_exist(self, realm_name: str) -> None:
        """Ensure all required realm roles exist, creating them if missing.

        This is useful when working with externally created realms that may not
        have the standard roles that budapp expects.

        Args:
            realm_name: Name of the realm to check and update
        """
        realm_admin = self.get_realm_admin(realm_name)

        required_roles = [
            UserRoleEnum.ADMIN.value,
            UserRoleEnum.DEVELOPER.value,
            UserRoleEnum.TESTER.value,
            UserRoleEnum.DEVOPS.value,
            UserRoleEnum.SUPER_ADMIN.value,
        ]

        for role_name in required_roles:
            realm_admin.create_realm_role(
                {"name": role_name, "description": f"Role: {role_name}"},
                skip_exists=True,  # Won't error if role already exists
            )

        logger.info(f"Ensured all required realm roles exist in {realm_name}")

    def get_keycloak_user_by_email(self, email: str, realm_name: str) -> Optional[Dict]:
        """Get Keycloak user details by email address.

        This is useful for JIT provisioning to fetch user details from Keycloak.

        Args:
            email: User email to search for
            realm_name: Name of the realm

        Returns:
            User dict if found, None otherwise
        """
        try:
            realm_admin = self.get_realm_admin(realm_name)
            users = realm_admin.get_users({"email": email})
            if users and len(users) > 0:
                return users[0]  # Return first match
            return None
        except Exception as e:
            logger.error(f"Error fetching Keycloak user by email {email}: {str(e)}")
            return None

    def get_user_realm_roles(self, user_id: str, realm_name: str) -> list[str]:
        """Get realm roles assigned to a user in Keycloak.

        This is useful for JIT provisioning to determine user permissions.

        Args:
            user_id: Keycloak user ID (UUID)
            realm_name: Name of the realm

        Returns:
            List of realm role names (e.g., ['admin', 'developer'])
        """
        try:
            realm_admin = self.get_realm_admin(realm_name)
            roles = realm_admin.get_realm_roles_of_user(user_id)
            role_names = [role.get("name") for role in roles if role.get("name")]
            logger.info(f"User {user_id} has realm roles: {role_names}")
            return role_names
        except Exception as e:
            logger.error(f"Error fetching realm roles for user {user_id}: {str(e)}")
            return []

    async def create_client(self, client_id: str, realm_name: str) -> Tuple[str, str]:
        """Create a new client in Keycloak.

        Args:
            client_id: ID of the client to create
            realm_name: Name of the realm to create the client in

        Returns:
            Tuple[str, str]: Tuple containing (client_id, client_secret)
        """
        self._get_base_url()
        client_representation = {
            "clientId": client_id,
            "enabled": True,
            "protocol": "openid-connect",
            "publicClient": False,
            "redirectUris": ["*"],
            "webOrigins": ["*"],
            "authorizationServicesEnabled": True,
            "serviceAccountsEnabled": True,
        }

        try:
            realm_admin = self.get_realm_admin(realm_name)
            new_client_id = realm_admin.create_client(payload=client_representation)
            secrets = realm_admin.get_client_secrets(new_client_id)
            client_secret = secrets.get("value", "")  # type: ignore
            if not client_secret:
                raise ValueError(f"Client secret not found for client {new_client_id}")

            # Create Resources / Scopes / Policies / Roles
            modules = [
                "cluster",
                "model",
                "project",
                "user",
                "benchmark",
            ]
            for module in modules:
                await self._create_module_resource(realm_admin, new_client_id, module, realm_name)

            return new_client_id, client_secret
        except Exception as e:
            logger.error(f"Error creating client {client_id} in realm {realm_name}: {str(e)}")
            raise e

    async def create_user(self, username: str, email: str, password: str, realm_name: str, role: UserRoleEnum) -> str:
        """Create a new user in Keycloak.

        Args:
            username: Username of the user to create
            email: Email of the user to create
            password: Password of the user to create
            realm_name: Name of the realm to create the user in
            role: Role of the user to create
        Returns:
            str: User ID of the created user
        """
        user_representation = {
            "username": username,  # email is treated as username
            "email": email,
            "enabled": True,
            "emailVerified": True,
            "credentials": [{"type": "password", "value": password, "temporary": False}],
        }

        try:
            realm_admin = self.get_realm_admin(realm_name)
            user_id = realm_admin.create_user(payload=user_representation)
            logger.info(f"User {username} created successfully")

            # Assign role to user
            realm_admin.assign_realm_roles(user_id=user_id, roles=[role.value])
            logger.info(f"Role {role.value} assigned to user {username}")

            return user_id
        except Exception as e:
            logger.error(f"Error creating user {username} in realm {realm_name}: {str(e)}")
            raise

    async def create_user_with_permissions(self, user: UserCreate, realm_name: str, client_id: str) -> str:
        """Create a new user with permissions in Keycloak.

        Args:
            user: UserCreate object
            realm_name: Name of the realm to create the user in


        Returns:
            str: User ID of the created user
        """
        user_representation = {
            "username": user.email,
            "email": user.email,
            "firstName": user.name,
            "lastName": user.name,
            "enabled": True,
            "emailVerified": True,
            "credentials": [{"type": "password", "value": user.password, "temporary": False}],
            "attributes": {
                "company": [user.company] if user.company else [],
                "purpose": [user.purpose] if user.purpose else [],
                "user_type": [user.user_type.value] if user.user_type else [],
            },
        }

        try:
            realm_admin = self.get_realm_admin(realm_name)
            user_id = realm_admin.create_user(payload=user_representation)
            logger.info(f"User {(user.email,)} created successfully")

            roles = realm_admin.get_realm_roles()
            admin_role = next((r for r in roles if r["name"] == user.role.value), None)

            if not admin_role:
                raise ValueError(f"Realm role {user.role.value} not found in realm {realm_name}")

            # Step 2: Assign the role to the user
            realm_admin.assign_realm_roles(user_id=user_id, roles=[admin_role])

            logger.debug(f"Role {user.role.value} assigned to user {user.email}")

            user_permission_map = {}
            if user.permissions:
                for permission in user.permissions:
                    if permission.has_permission:
                        parts = permission.name.split(":", 1)
                        if len(parts) == 2:
                            key, scope_name = parts
                        else:
                            # Handle permissions without colon separator
                            key = permission.name
                            scope_name = "default"
                        if key not in user_permission_map:
                            user_permission_map[key] = []
                        user_permission_map[key].append(scope_name)

            # User Policy Name
            policy_name = f"urn:bud:policy:{user_id}"

            for module, scopes in user_permission_map.items():
                resource_name = f"module_{module}"
                resources = realm_admin.get_client_authz_resources(client_id)
                module_resource = next((r for r in resources if r["name"] == resource_name), None)

                if not module_resource:
                    logger.warning(f"Resource {resource_name} not found for client {client_id}")
                    continue

                existing_policies = realm_admin.get_client_authz_policies(client_id)

                user_policy = next((p for p in existing_policies if p["name"] == policy_name), None)

                if not user_policy:
                    user_policy = {
                        "name": policy_name,
                        "description": f"User policy for {user_id}",
                        "logic": "POSITIVE",
                        "users": [user_id],
                    }

                    policy_url = f"{app_settings.keycloak_server_url}/admin/realms/{realm_name}/clients/{client_id}/authz/resource-server/policy/user"

                    data_raw = realm_admin.connection.raw_post(
                        policy_url,
                        data=json.dumps(user_policy),
                        max=-1,
                        permission=False,
                    )

                    user_policy_id = data_raw.json()["id"]
                else:
                    user_policy_id = user_policy["id"]

                # Get the permission associated for the resource
                for scope_name in scopes:
                    all_permissions = f"{app_settings.keycloak_server_url}/admin/realms/{realm_name}/clients/{client_id}/authz/resource-server/permission?name=urn%3Abud%3Apermission%3A{module}%3Amodule%3A{scope_name}&scope={scope_name}&type=scope"
                    data_raw = realm_admin.connection.raw_get(
                        all_permissions,
                        max=-1,
                        permission=False,
                    )

                    permission_id = data_raw.json()[0]["id"]

                    # Get The Permission
                    permission_url = f"{app_settings.keycloak_server_url}/admin/realms/{realm_name}/clients/{client_id}/authz/resource-server/permission/scope/{permission_id}"
                    permission_data_raw = realm_admin.connection.raw_get(
                        permission_url,
                        max=-1,
                        permission=False,
                    )

                    permission_resources_url = f"{app_settings.keycloak_server_url}/admin/realms/{realm_name}/clients/{client_id}/authz/resource-server/policy/{permission_id}/resources"
                    permission_resources_data_raw = realm_admin.connection.raw_get(
                        permission_resources_url,
                        max=-1,
                        permission=False,
                    )

                    # get the scopes
                    permission_scopes_url = f"{app_settings.keycloak_server_url}/admin/realms/{realm_name}/clients/{client_id}/authz/resource-server/policy/{permission_id}/scopes"
                    permission_scopes_data_raw = realm_admin.connection.raw_get(
                        permission_scopes_url,
                        max=-1,
                        permission=False,
                    )

                    permission_policies_url = f"{app_settings.keycloak_server_url}/admin/realms/{realm_name}/clients/{client_id}/authz/resource-server/policy/{permission_id}/associatedPolicies"
                    permission_policies_data_raw = realm_admin.connection.raw_get(
                        permission_policies_url,
                        max=-1,
                        permission=False,
                    )

                    update_policy = []
                    for policy in permission_policies_data_raw.json():
                        if policy["name"] != policy_name:
                            update_policy.append(policy["id"])

                    # add policy id to the update policy if not already in the list
                    if user_policy_id not in update_policy:
                        update_policy.append(user_policy_id)

                    # Update
                    permission_update_payload = {
                        "id": permission_data_raw.json()["id"],
                        "name": permission_data_raw.json()["name"],
                        "description": permission_data_raw.json()["description"],
                        "type": permission_data_raw.json()["type"],
                        "logic": permission_data_raw.json()["logic"],
                        "decisionStrategy": permission_data_raw.json()["decisionStrategy"],
                        "resources": [permission_resources_data_raw.json()[0]["_id"]],
                        "policies": update_policy,
                        "scopes": [permission_scopes_data_raw.json()[0]["id"]],
                    }

                    # Update the permission
                    permission_update_url = f"{app_settings.keycloak_server_url}/admin/realms/{realm_name}/clients/{client_id}/authz/resource-server/permission/scope/{permission_id}"
                    realm_admin.connection.raw_put(
                        permission_update_url,
                        data=json.dumps(permission_update_payload),
                        max=-1,
                        permission=False,
                    )

            return user_id
        except KeycloakPostError as e:
            # A 409 Conflict status code typically indicates that the user already exists.
            if e.response_code == 409:
                logger.error(f"User with email {user.email} already exists in Keycloak realm {realm_name}")
                from budapp.commons.exceptions import ClientException

                raise ClientException(message="Email already registered")
            logger.error(f"Keycloak error creating user {user.email} in realm {realm_name}: {error_msg}")
            raise
        except Exception as e:
            logger.error(f"Error creating realm admin {(user.email,)} in realm {realm_name}: {str(e)}", exc_info=True)
            raise

    async def create_realm_admin(
        self, username: str, email: str, password: str, realm_name: str, client_id: str, client_secret: str
    ) -> str:
        """Create a new realm admin user in Keycloak.

        Args:
            username: Username of the realm admin to create
            email: Email of the realm admin to create
            password: Password of the realm admin to create
            realm_name: Name of the realm to create the realm admin in

        Returns:
            str: User ID of the created realm admin
        """
        user_representation = {
            "username": username,
            "email": email,
            "firstName": "Admin",  # TODO Update this to be dynamic
            "lastName": "Admin",  # TODO Update this to be dynamic
            "enabled": True,
            "emailVerified": True,
            "credentials": [{"type": "password", "value": password, "temporary": False}],
        }

        try:
            realm_admin = self.get_realm_admin(realm_name)
            user_id = realm_admin.create_user(payload=user_representation, exist_ok=True)
            logger.info(f"Realm admin {username} created successfully")

            # Step 1: Get all realm roles
            roles = realm_admin.get_realm_roles()
            super_admin_role = next((r for r in roles if r["name"] == "super_admin"), None)

            if not super_admin_role:
                raise ValueError(f"Realm role 'super_admin' not found in realm {realm_name}")

            # Step 2: Assign the role to the user
            realm_admin.assign_realm_roles(user_id=user_id, roles=[super_admin_role])
            logger.info(f"Assigned 'super_admin' role to user {username}")

            # Step 3: Assign policies to the user
            modules = [
                "cluster",
                "model",
                "project",
                "user",
                "benchmark",
            ]
            for module in modules:
                resource_name = f"module_{module}"
                resources = realm_admin.get_client_authz_resources(client_id=client_id)
                module_resource = next((r for r in resources if r["name"] == resource_name), None)

                if not module_resource:
                    logger.warning(f"Resource {resource_name} not found for client {client_id}")
                    continue

                module_resource["_id"]
                policy_name = f"urn:bud:policy:{user_id}"
                existing_policies = realm_admin.get_client_authz_policies(client_id)
                logger.debug(f"Found {len(existing_policies)} existing policies")
                user_policy = next((p for p in existing_policies if p["name"] == policy_name), None)

                if not user_policy:
                    user_policy = {
                        "name": policy_name,
                        "description": f"User policy for {user_id}",
                        "logic": "POSITIVE",
                        "users": [str(user_id)],
                    }

                    logger.debug(f"Creating user policy: {json.dumps(user_policy, indent=4)}")

                    policy_url = f"{app_settings.keycloak_server_url}/admin/realms/{realm_name}/clients/{client_id}/authz/resource-server/policy/user"

                    data_raw = realm_admin.connection.raw_post(
                        policy_url,
                        data=json.dumps(user_policy),
                        max=-1,
                        permission=False,
                    )

                    logger.debug(f"User policy response: {data_raw.json()}")
                    user_policy_id = data_raw.json()["id"]
                else:
                    user_policy_id = user_policy["id"]

                # Get the permission associated for the resource
                scopes = ["view", "manage"]
                for scope in scopes:
                    all_permissions = f"{app_settings.keycloak_server_url}/admin/realms/{realm_name}/clients/{client_id}/authz/resource-server/permission?name=urn%3Abud%3Apermission%3A{module}%3Amodule%3A{scope}&scope={scope}&type=scope"
                    data_raw = realm_admin.connection.raw_get(
                        all_permissions,
                        max=-1,
                        permission=False,
                    )

                    logger.debug(f"All permissions response: {data_raw.json()}")
                    permission_id = data_raw.json()[0]["id"]

                    # Get The Permission
                    permission_url = f"{app_settings.keycloak_server_url}/admin/realms/{realm_name}/clients/{client_id}/authz/resource-server/permission/scope/{permission_id}"
                    permission_data_raw = realm_admin.connection.raw_get(
                        permission_url,
                        max=-1,
                        permission=False,
                    )

                    logger.debug(f"Permission response: {permission_data_raw.json()}")

                    # {
                    #     "id": "3697f5d3-5104-4172-a716-cb20e7567383",
                    #     "name": "urn:bud:permission:cluster:manage",
                    #     "description": "Permission for cluster to manage",
                    #     "type": "scope",
                    #     "logic": "POSITIVE",
                    #     "decisionStrategy": "UNANIMOUS"
                    # }

                    # Get the assosciated resource
                    permission_resources_url = f"{app_settings.keycloak_server_url}/admin/realms/{realm_name}/clients/{client_id}/authz/resource-server/policy/{permission_id}/resources"
                    permission_resources_data_raw = realm_admin.connection.raw_get(
                        permission_resources_url,
                        max=-1,
                        permission=False,
                    )

                    # get the scopes
                    permission_scopes_url = f"{app_settings.keycloak_server_url}/admin/realms/{realm_name}/clients/{client_id}/authz/resource-server/policy/{permission_id}/scopes"
                    permission_scopes_data_raw = realm_admin.connection.raw_get(
                        permission_scopes_url,
                        max=-1,
                        permission=False,
                    )

                    # get associated policies and check if our policy is one of them
                    permission_policies_url = f"{app_settings.keycloak_server_url}/admin/realms/{realm_name}/clients/{client_id}/authz/resource-server/policy/{permission_id}/associatedPolicies"
                    permission_policies_data_raw = realm_admin.connection.raw_get(
                        permission_policies_url,
                        max=-1,
                        permission=False,
                    )

                    # Check if the user policy is one of the associated policies
                    # user_policy_id = next((p["id"] for p in permission_policies_data_raw.json() if p["name"] == policy_name), None)

                    # if not user_policy_id:
                    #     logger.warning(f"User policy {policy_name} not found in associated policies")
                    #     continue

                    update_policy = []
                    for policy in permission_policies_data_raw.json():
                        if policy["name"] == policy_name:
                            update_policy.append(policy["id"])

                    # add policy id to the update policy if not already in the list
                    if user_policy_id not in update_policy:
                        update_policy.append(user_policy_id)

                    #                     [
                    #     {
                    #         "id": "41149b8f-dac0-4fc2-8fa6-02d18f6c71b0",
                    #         "name": "urn:bud:policy:b04b78dd-d6a1-4f05-a9e4-85e10f9e6c58",
                    #         "description": "User policy for b04b78dd-d6a1-4f05-a9e4-85e10f9e6c58",
                    #         "type": "user",
                    #         "logic": "POSITIVE",
                    #         "decisionStrategy": "UNANIMOUS",
                    #         "config": {}
                    #     }
                    # ]

                    # Update the permission
                    # {
                    #     "id": "3697f5d3-5104-4172-a716-cb20e7567383",
                    #     "name": "urn:bud:permission:cluster:manage",
                    #     "description": "Permission for cluster to manage",
                    #     "type": "scope",
                    #     "logic": "POSITIVE",
                    #     "decisionStrategy": "UNANIMOUS",
                    #     "resources": [
                    #         "b6be1355-d4d6-4271-aa71-1f6986b11419"
                    #     ],
                    #     "policies": [
                    #         "41149b8f-dac0-4fc2-8fa6-02d18f6c71b0"
                    #     ],
                    #     "scopes": [
                    #         "370c6c54-1471-4728-97d7-fd8d97b6b4c2"
                    #     ]
                    # }

                    permission_update_payload = {
                        "id": permission_data_raw.json()["id"],
                        "name": permission_data_raw.json()["name"],
                        "description": permission_data_raw.json()["description"],
                        "type": permission_data_raw.json()["type"],
                        "logic": permission_data_raw.json()["logic"],
                        "decisionStrategy": permission_data_raw.json()["decisionStrategy"],
                        "resources": [permission_resources_data_raw.json()[0]["_id"]],
                        "policies": update_policy,
                        "scopes": [permission_scopes_data_raw.json()[0]["id"]],
                    }

                    logger.debug(f"Permission update payload: {json.dumps(permission_update_payload, indent=4)}")

                    # Update the permission
                    permission_update_url = f"{app_settings.keycloak_server_url}/admin/realms/{realm_name}/clients/{client_id}/authz/resource-server/permission/scope/{permission_id}"
                    realm_admin.connection.raw_put(
                        permission_update_url,
                        data=json.dumps(permission_update_payload),
                        max=-1,
                        permission=False,
                    )

                    # logger.debug(f"Permission update response: {permission_update_data_raw.json()}")

                    # logger.info(f"Permission {permission_data_raw.json()['name']} assigned to user {username} for module {module}")

                # Step 3b: Create permission (if not exists)
                # permission_name = f"user-{user_id}-module-{module}"
                # existing_permissions = realm_admin.get_client_authz_permissions(client_id)
                # if any(p["name"] == permission_name for p in existing_permissions):
                #     logger.info(f"Permission {permission_name} already exists — skipping.")
                #     continue

                # # Scope from keycloak
                # kc_scopes = realm_admin.get_client_authz_scopes(client_id)
                # logger.debug(f"KC Scopes: {kc_scopes}")

                # permission = {
                #     "name": permission_name,
                #     "decisionStrategy": "UNANIMOUS",
                #     "description": f"Permission for {user_id} to view and manage {module}",
                #     "resources": [resource_id],
                #     "policies": [policy_id],
                #     "scopes": [scope["id"] for scope in kc_scopes],
                #     "type": "scope",
                #     "logic": "POSITIVE",
                # }

                # logger.debug(f"Creating permission: {json.dumps(permission, indent=4)}")
                # permission_url = f"{app_settings.keycloak_server_url}/admin/realms/{realm_name}/clients/{client_id}/authz/resource-server/permission/scope"
                # data_raw = realm_admin.connection.raw_post(
                #     permission_url,
                #     data=json.dumps(permission),
                #     max=-1,
                #     permission=False,
                # )

                # logger.debug(f"Permission response: {data_raw.json()}")
                # permission_id = data_raw.json()["id"]

                # logger.debug(f"Permission ID: {permission_id}")

                # # realm_admin.create_client_authz_permission(client_id, permission)
                # logger.info(f"Permission {permission_name} assigned to user {username} for module {module}")

            return user_id
        except Exception as e:
            logger.error(f"Error creating realm admin {username} in realm {realm_name}: {str(e)}")
            raise

    async def sync_user_permissions(self, user_id: str, realm_name: str, client_id: str) -> None:
        """Sync permissions for an existing user to ensure they have all current module permissions.

        This is useful when new modules are added to the system and existing users need
        to have their permissions updated.

        Args:
            user_id: The Keycloak user ID
            realm_name: Name of the realm
            client_id: The Keycloak internal client UUID
        """
        try:
            realm_admin = self.get_realm_admin(realm_name)

            # Get all current modules
            modules = [
                "cluster",
                "model",
                "project",
                "user",
                "benchmark",
            ]

            # Get or create user policy
            policy_name = f"urn:bud:policy:{user_id}"
            existing_policies = realm_admin.get_client_authz_policies(client_id)
            user_policy = next((p for p in existing_policies if p["name"] == policy_name), None)

            if not user_policy:
                # Create user policy if it doesn't exist
                user_policy = {
                    "name": policy_name,
                    "description": f"User policy for {user_id}",
                    "logic": "POSITIVE",
                    "users": [str(user_id)],
                }

                policy_url = f"{app_settings.keycloak_server_url}/admin/realms/{realm_name}/clients/{client_id}/authz/resource-server/policy/user"

                try:
                    data_raw = realm_admin.connection.raw_post(
                        policy_url,
                        data=json.dumps(user_policy),
                        max=-1,
                        permission=False,
                    )
                    logger.debug(f"User policy creation response: {data_raw.json()}")

                    response_json = data_raw.json()
                    if "id" not in response_json:
                        logger.error(f"User policy creation failed. Response: {response_json}")
                        raise ValueError(f"Failed to create user policy {policy_name}. Response: {response_json}")

                    user_policy_id = response_json["id"]
                    logger.info(f"Created user policy {policy_name} with ID {user_policy_id}")
                except KeycloakPostError as e:
                    if e.response_code == 409:
                        # Policy might already exist - try to refetch
                        logger.warning(
                            f"User policy {policy_name} might already exist (409 Conflict). Retrying fetch..."
                        )
                        existing_policies = realm_admin.get_client_authz_policies(client_id)
                        user_policy = next((p for p in existing_policies if p["name"] == policy_name), None)
                        if user_policy:
                            user_policy_id = user_policy["id"]
                            logger.info(f"Found existing user policy {policy_name} with ID {user_policy_id}")
                        else:
                            logger.error(f"User policy {policy_name} not found even after 409 Conflict")
                            raise
                    else:
                        logger.error(f"Keycloak error creating user policy {policy_name}: {str(e)}")
                        raise
            else:
                user_policy_id = user_policy["id"]

            # Sync permissions for each module
            for module in modules:
                resource_name = f"module_{module}"
                resources = realm_admin.get_client_authz_resources(client_id)
                module_resource = next((r for r in resources if r["name"] == resource_name), None)

                if not module_resource:
                    logger.warning(f"Resource {resource_name} not found for client {client_id}. Creating it...")
                    # Create the missing module resource
                    await self._create_module_resource(realm_admin, client_id, module, realm_name)

                    # Fetch the resource again after creation
                    resources = realm_admin.get_client_authz_resources(client_id)
                    module_resource = next((r for r in resources if r["name"] == resource_name), None)

                    if not module_resource:
                        logger.error(f"Failed to create resource {resource_name}")
                        continue

                    logger.info(f"Successfully created resource {resource_name}")

                # Get scopes for this module
                kc_scopes = realm_admin.get_client_authz_scopes(client_id)

                for scope in kc_scopes:
                    permission_name = f"urn:bud:permission:{module}:module:{scope['name']}"

                    # Check if permission exists
                    all_permissions_url = f"{app_settings.keycloak_server_url}/admin/realms/{realm_name}/clients/{client_id}/authz/resource-server/permission?name={permission_name}&scope={scope['name']}&type=scope"

                    try:
                        data_raw = realm_admin.connection.raw_get(
                            all_permissions_url,
                            max=-1,
                            permission=False,
                        )

                        if data_raw.json():
                            permission_id = data_raw.json()[0]["id"]

                            # Get current permission details
                            permission_url = f"{app_settings.keycloak_server_url}/admin/realms/{realm_name}/clients/{client_id}/authz/resource-server/permission/scope/{permission_id}"
                            permission_data_raw = realm_admin.connection.raw_get(
                                permission_url,
                                max=-1,
                                permission=False,
                            )

                            # Get associated policies
                            permission_policies_url = f"{app_settings.keycloak_server_url}/admin/realms/{realm_name}/clients/{client_id}/authz/resource-server/policy/{permission_id}/associatedPolicies"
                            permission_policies_data_raw = realm_admin.connection.raw_get(
                                permission_policies_url,
                                max=-1,
                                permission=False,
                            )

                            # Check if user policy is already associated
                            associated_policies = permission_policies_data_raw.json()
                            policy_ids = [p["id"] for p in associated_policies]

                            if user_policy_id not in policy_ids:
                                # Add user policy to the permission
                                policy_ids.append(user_policy_id)

                                # Get resources and scopes
                                permission_resources_url = f"{app_settings.keycloak_server_url}/admin/realms/{realm_name}/clients/{client_id}/authz/resource-server/policy/{permission_id}/resources"
                                permission_resources_data_raw = realm_admin.connection.raw_get(
                                    permission_resources_url,
                                    max=-1,
                                    permission=False,
                                )

                                permission_scopes_url = f"{app_settings.keycloak_server_url}/admin/realms/{realm_name}/clients/{client_id}/authz/resource-server/policy/{permission_id}/scopes"
                                permission_scopes_data_raw = realm_admin.connection.raw_get(
                                    permission_scopes_url,
                                    max=-1,
                                    permission=False,
                                )

                                # Update permission with user policy
                                permission_update_payload = {
                                    "id": permission_data_raw.json()["id"],
                                    "name": permission_data_raw.json()["name"],
                                    "description": permission_data_raw.json()["description"],
                                    "type": permission_data_raw.json()["type"],
                                    "logic": permission_data_raw.json()["logic"],
                                    "decisionStrategy": permission_data_raw.json()["decisionStrategy"],
                                    "resources": [permission_resources_data_raw.json()[0]["_id"]],
                                    "policies": policy_ids,
                                    "scopes": [permission_scopes_data_raw.json()[0]["id"]],
                                }

                                permission_update_url = f"{app_settings.keycloak_server_url}/admin/realms/{realm_name}/clients/{client_id}/authz/resource-server/permission/scope/{permission_id}"
                                realm_admin.connection.raw_put(
                                    permission_update_url,
                                    data=json.dumps(permission_update_payload),
                                    max=-1,
                                    permission=False,
                                )

                                logger.debug(f"Added user policy to permission {permission_name}")
                            else:
                                logger.debug(f"User policy already associated with permission {permission_name}")
                    except Exception as e:
                        logger.warning(f"Permission {permission_name} might not exist or error occurred: {str(e)}")
                        continue

            logger.info(f"Completed permission sync for user {user_id}")

        except Exception as e:
            logger.error(f"Error syncing permissions for user {user_id}: {str(e)}")
            raise

    def realm_exists(self, realm_name: str) -> bool:
        """Check if a realm exists in Keycloak.

        Args:
            realm_name: Name of the realm to check

        Returns:
            bool: True if the realm exists, False otherwise
        """
        try:
            realms = self.admin_client.get_realms()
            return any(realm["realm"] == realm_name for realm in realms)
        except Exception as e:
            logger.error(f"Error checking if realm {realm_name} exists: {str(e)}")
            return False

    async def refresh_token(self, realm_name: str, credentials: TenantClientSchema, refresh_token: str) -> dict:
        """Refresh the access token using the refresh token.

        Args:
            realm_name: Name of the Keycloak realm
            credentials: TenantClientSchema with client_id and client_secret
            refresh_token: The refresh token string

        Returns:
            dict: New token response from Keycloak
        """
        try:
            openid_client = self.get_keycloak_openid_client(realm_name, credentials)
            new_token = openid_client.refresh_token(refresh_token)
            return new_token
        except KeycloakAuthenticationError as e:
            logger.warning(f"Failed to refresh token due to invalid credentials or expired token: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error while refreshing token: {str(e)}")
            raise

    async def authenticate_user(
        self, username: str, password: str, realm_name: str, credentials: TenantClientSchema
    ) -> dict:
        """Authenticate a user and return access & refresh tokens.

        Args:
            username: Username of the user to authenticate
            password: Password of the user to authenticate
            realm_name: Name of the realm to authenticate the user in
            credentials: Contains client_id and (optional) client_secret

        Returns:
            dict: Contains access_token, refresh_token, etc.

        Raises:
            KeycloakAuthenticationError: If authentication fails

        Example:
            {
                "access_token": "eyJhbGciOiJSUzI1NiIsInR...",
                "expires_in": 300,
                "refresh_expires_in": 1800,
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR...",
                "token_type": "Bearer",
                "not-before-policy": 0,
                "session_state": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                "scope": "email profile"
            }
        """
        try:
            openid_client = self.get_keycloak_openid_client(realm_name, credentials)

            # Log authentication attempt details (without sensitive info)
            logger.info(
                f"Attempting Keycloak authentication: username={username}, realm={realm_name}, "
                f"client_id={credentials.client_named_id}"
            )

            token = openid_client.token(username, password, scope="openid profile email roles")
            logger.info(f"Successfully authenticated user {username} in realm {realm_name}")
            return token
        except KeycloakAuthenticationError as e:
            # Log detailed error information from Keycloak
            error_message = str(e)

            # Try to extract additional error details from exception
            error_details = {
                "error_message": error_message,
                "exception_type": type(e).__name__,
            }

            # Check for response_code attribute
            if hasattr(e, "response_code"):
                error_details["response_code"] = e.response_code

            # Check for response_body attribute
            if hasattr(e, "response_body"):
                error_details["response_body"] = e.response_body

            # Check for error attribute
            if hasattr(e, "error"):
                error_details["error"] = e.error

            # Log all exception attributes for debugging
            from contextlib import suppress

            with suppress(Exception):
                error_details["all_attributes"] = {k: v for k, v in vars(e).items() if not k.startswith("_")}

            logger.error(
                f"Keycloak authentication failed for user {username} in realm {realm_name}. "
                f"Error details: {error_details}. "
                f"Common causes: 1) Temporary password not reset, 2) Account disabled, "
                f"3) Email not verified, 4) Invalid credentials"
            )
            # Re-raise the exception to be handled by the caller
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error during authentication for user {username} in realm {realm_name}: "
                f"{type(e).__name__}: {str(e)}"
            )
            raise

    async def logout_user(self, refresh_token: str, realm_name: str, credentials: TenantClientSchema) -> bool:
        """Log out a user by invalidating the refresh token.

        Args:
            refresh_token: The refresh token to invalidate
            realm_name: The realm the user belongs to
            credentials: Contains client_id and (optional) client_secret

        Returns:
            bool: True if logout was successful, False otherwise
        """
        try:
            openid_client = self.get_keycloak_openid_client(realm_name, credentials)
            openid_client.logout(refresh_token)
            logger.info(f"User successfully logged out from realm {realm_name}")
            return True
        except Exception as e:
            logger.error(f"Error logging out user from realm {realm_name}: {str(e)}")
            return False

    async def get_user_roles_and_permissions(
        self,
        user_id: str,
        realm_name: str,
        client_id: str,
        credentials: TenantClientSchema,
        token: str,
    ) -> Dict[str, List[str]]:
        """Get user roles and permissions from Keycloak.

        Args:
            user_id: The ID of the user to get roles and permissions for
            realm_name: The name of the realm to get roles and permissions for
            client_id: The ID of the client to get roles and permissions for
            credentials: The credentials of the client to get roles and permissions for
            token: The token of the user to get roles and permissions for

        Returns:
            Dict[str, List[str]]: A dictionary containing the user's roles and permissions
        """
        try:
            keycloak_openid = self.get_keycloak_openid_client(realm_name, credentials)

            # Validate the endpoint is correct
            try:
                oidc_config = keycloak_openid.well_known()
                token_endpoint = oidc_config.get("token_endpoint")
                if not token_endpoint:
                    raise ValueError("Could not retrieve token_endpoint from OIDC well-known configuration.")
            except Exception as e:
                logger.error(f"Failed to get OIDC configuration: {str(e)}")
                raise ValueError(f"Failed to connect to Keycloak: {str(e)}")

            # access token = token
            if not token:
                logger.error("Access token not provided")
                raise KeycloakAuthenticationError("Access token not found.")

            # Request the RPT
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/x-www-form-urlencoded",
            }
            payload = {
                "grant_type": "urn:ietf:params:oauth:grant-type:uma-ticket",
                "audience": credentials.client_named_id,
            }

            try:
                response = requests.post(
                    token_endpoint,
                    headers=headers,
                    data=payload,
                    timeout=30,
                    verify=app_settings.keycloak_verify_ssl,
                )
                response.raise_for_status()
            except requests.exceptions.Timeout:
                logger.error("Timeout while requesting RPT from Keycloak")
                raise ValueError("Request to Keycloak timed out")
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 401:
                    logger.error("Token expired or invalid")
                    raise KeycloakAuthenticationError("Token expired or invalid")
                elif e.response.status_code == 403:
                    logger.error("Insufficient permissions to access resources")
                    raise KeycloakAuthenticationError("Insufficient permissions")
                else:
                    logger.error(f"HTTP error from Keycloak: {e.response.status_code} - {e.response.text}")
                    raise ValueError(f"Keycloak error: {e.response.status_code}")
            except requests.exceptions.RequestException as e:
                logger.error(f"Network error communicating with Keycloak: {str(e)}")
                raise ValueError(f"Failed to communicate with Keycloak: {str(e)}")

            # RPT Response
            try:
                rpt_response_data = response.json()
            except json.JSONDecodeError:
                logger.error("Invalid JSON response from Keycloak")
                raise ValueError("Invalid response format from Keycloak")

            requesting_party_token = rpt_response_data.get("access_token")

            if not requesting_party_token:
                logger.error(f"RPT not found in response: {json.dumps(rpt_response_data)}")
                raise ValueError("Failed to obtain permission token from Keycloak")

            # Decode RPT Payload
            rpt_payload = self._decode_jwt_payload(requesting_party_token)
            if not rpt_payload:
                logger.error("Failed to decode RPT")
                raise ValueError("Failed to decode permission token")

            # Extract and format permissions
            raw_permissions = rpt_payload.get("authorization", {}).get("permissions", [])

            formatted_permissions = []
            for perm in raw_permissions:
                # Ensure we only include the desired fields and handle missing scopes
                formatted_perm = {
                    "rsid": perm.get("rsid"),  # Get rsid or None if missing
                    "rsname": perm.get("rsname"),  # Get rsname or None if missing
                    "scopes": perm.get("scopes", []),  # Get scopes or default to empty list
                }
                formatted_permissions.append(formatted_perm)

            # Prepare final output structure
            final_output = {"permissions": formatted_permissions}

            return final_output

        except KeycloakAuthenticationError:
            # Re-raise authentication errors as-is
            raise
        except ValueError:
            # Re-raise value errors as-is
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting user roles and permissions: {str(e)}", exc_info=True)
            raise ValueError(f"Failed to retrieve user permissions: {str(e)}")

    def _decode_jwt_payload(self, token: str) -> dict:
        """Safely decodes the payload of a JWT using base64."""
        try:
            # Split token into parts: header, payload, signature
            parts = token.split(".")
            if len(parts) != 3:
                print("[ERROR] Invalid JWT format: Incorrect number of segments.", file=sys.stderr)
                return None

            payload_encoded = parts[1]
            # Add padding if necessary for base64 decoding
            payload_encoded += "=" * (-len(payload_encoded) % 4)
            # Use urlsafe_b64decode for JWT compatibility
            payload_decoded_bytes = base64.urlsafe_b64decode(payload_encoded)
            payload_json = json.loads(payload_decoded_bytes.decode("utf-8"))
            return payload_json
        except IndexError:
            # This case should be caught by len(parts) check now, but keep for safety
            print("[ERROR] Invalid JWT format: Could not split segments.", file=sys.stderr)
        except (TypeError, base64.binascii.Error, UnicodeDecodeError, json.JSONDecodeError) as e:
            print(f"[ERROR] Failed to decode JWT payload: {e}", file=sys.stderr)
            print(f"Encoded payload segment was: {payload_encoded}", file=sys.stderr)
        return None

    async def remove_resource_with_permissions(
        self, realm_name: str, client_id: str, resource: ResourceCreate, user_auth_id: str
    ) -> None:
        """Remove a resource with permissions."""
        try:
            if resource.scopes is None:
                logger.info(f"Resource {resource.resource_type} does not have any scopes — skipping.")
                return

            self.get_realm_admin(realm_name)

            # for scope in resource.scopes:
            # logger.info(f"Removing resource {resource.resource_type} with scope {scope} — skipping.")

            # resource_name = f"URN::{resource.resource_type}::{resource.resource_id}::{scope}"

            # resources = realm_admin.get_client_authz_resources(client_id)
            # module_resource = next((r for r in resources if r["name"] == resource_name), None)

            # if not module_resource:
            #     logger.info(f"Resource {resource_name} does not exist — skipping.")
            #     continue

            # resource_id = module_resource["_id"]

            # permission_url = f"{app_settings.keycloak_server_url}/admin/realms/{realm_name}/clients/{client_id}/authz/resource-server/permission/resource"

            # permissions = realm_admin.get_client_authz_permissions(client_id)
            # permission = next((p for p in permissions if p["resource"] == resource_id), None)

            # if not permission:
            #     logger.info(f"Permission for resource {resource_name} does not exist — skipping.")
            #     continue

            # realm_admin.delete_client_authz_permission(client_id, permission["id"])
            # logger.info(f"Permission for resource {resource_name} deleted successfully")

        except Exception as e:
            logger.error(f"Error getting realm admin: {str(e)}")
            raise

    async def delete_permission_for_resource(
        self,
        realm_name: str,
        client_id: str,
        resource_type: str,
        resource_id: str,
        delete_resource: bool = False,
    ) -> None:
        """Deletes all permissions and associated scopes for a given user and resource.

        Args:
            realm_name (str): Keycloak realm name
            client_id (str): Internal Keycloak client UUID
            user_id (str): User's Keycloak ID (sub)
            resource_type (str): Type of the resource (e.g., "cluster", "project")
            resource_id (str): Entity-specific resource ID.
        """  # noqa: D401
        try:
            realm_admin = self.get_realm_admin(realm_name)
            resource_name = f"URN::{resource_type}::{resource_id}"
            permission_prefix = f"urn:bud:permission:{resource_type}:{resource_id}:"

            # 1. Locate the resource
            resources = realm_admin.get_client_authz_resources(client_id)
            resource_obj = next((r for r in resources if r["name"] == resource_name), None)
            if not resource_obj:
                logger.warning(f"Resource {resource_name} not found — skipping.")
                return

            resource_id_internal = resource_obj["_id"]

            # 2. Delete matching permissions
            permissions = realm_admin.get_client_authz_permissions(client_id)
            for perm in permissions:
                if (
                    perm.get("resources")
                    and resource_id_internal in perm["resources"]
                    and perm["name"].startswith(permission_prefix)
                ):
                    logger.info(f"Deleting permission: {perm['name']}")
                    realm_admin.delete_client_authz_permission(client_id, perm["id"])

            # 3. Delete associated scopes if needed
            # Assuming scopes are not reused across resources — otherwise skip this
            # scopes_to_check = ["view", "manage"]
            # kc_scopes = realm_admin.get_client_authz_scopes(client_id)
            # for s in kc_scopes:
            #     if s["name"] in scopes_to_check:
            #         # Optional: Only remove custom scopes if not in default
            #         logger.info(f"Checking if scope {s['name']} is removable — skipping (shared scope)")

            # 4. Delete resource itself
            if delete_resource:
                realm_admin.delete_client_authz_resource(client_id, resource_id_internal)
                logger.info(f"Deleted resource {resource_name}")

            # 5. (Optional) Delete user policy if no more permissions reference it
            # policies = realm_admin.get_client_authz_policies(client_id)
            # user_policy = next((p for p in policies if p["name"] == policy_name), None)
            # if user_policy:
            #     realm_admin.delete_client_authz_policy(client_id, user_policy["id"])
            #     logger.info(f"Deleted user policy: {policy_name}")

        except Exception as e:
            logger.error(f"Failed to delete permission for user, resource {resource_type}:{resource_id} — {str(e)}")
            raise

    # ----------------------------------------------------------------------
    # FINE-GRAINED  ►  one concrete entity (Project, Cluster, …)
    # ----------------------------------------------------------------------
    async def remove_user_policy_from_resource_permissions(
        self,
        realm_name: str,
        client_id: str,
        resource_type: str,
        resource_id: str,
        user_auth_id: str,
    ) -> None:
        """Remove a user's policy from existing resource permissions.

        This method removes a user's access to a resource by removing their
        policy from all permissions associated with that resource.

        Args:
            realm_name: Name of the realm
            client_id: The Keycloak internal client UUID
            resource_type: Type of resource (e.g., "project", "cluster")
            resource_id: The resource UUID
            user_auth_id: The Keycloak user ID to remove access from
        """
        try:
            realm_admin = self.get_realm_admin(realm_name)

            # Get user policy
            policy_name = f"urn:bud:policy:{user_auth_id}"
            existing_policies = realm_admin.get_client_authz_policies(client_id)
            user_policy = next((p for p in existing_policies if p["name"] == policy_name), None)

            if not user_policy:
                logger.warning(f"User policy {policy_name} not found, nothing to remove")
                return

            user_policy_id = user_policy["id"]

            # Check if resource exists
            resource_name = f"URN::{resource_type}::{resource_id}"
            resources = realm_admin.get_client_authz_resources(client_id)
            resource_obj = next((r for r in resources if r["name"] == resource_name), None)

            if not resource_obj:
                logger.warning(f"Resource {resource_name} not found, nothing to remove")
                return

            # Get all permissions for this resource
            scopes = ["view", "manage"]
            for scope in scopes:
                permission_name = f"urn:bud:permission:{resource_type}:{resource_id}:{scope}"

                # Get existing permissions
                permissions_url = f"{app_settings.keycloak_server_url}/admin/realms/{realm_name}/clients/{client_id}/authz/resource-server/permission"
                permissions_data_raw = realm_admin.connection.raw_get(
                    permissions_url,
                    max=-1,
                    permission=False,
                )
                permissions = permissions_data_raw.json()

                # Find the permission for this resource and scope
                permission = next((p for p in permissions if p["name"] == permission_name), None)

                if not permission:
                    logger.debug(f"Permission {permission_name} not found, skipping")
                    continue

                permission_id = permission["id"]

                # Get current associated policies
                permission_policies_url = f"{app_settings.keycloak_server_url}/admin/realms/{realm_name}/clients/{client_id}/authz/resource-server/policy/{permission_id}/associatedPolicies"
                permission_policies_data_raw = realm_admin.connection.raw_get(
                    permission_policies_url,
                    max=-1,
                    permission=False,
                )

                # Build list of policy IDs without the user's policy
                update_policy = []
                for policy in permission_policies_data_raw.json():
                    if policy["id"] != user_policy_id:
                        update_policy.append(policy["id"])

                # Only update if user policy was actually removed
                if len(update_policy) < len(permission_policies_data_raw.json()):
                    # Get permission details for update
                    permission_url = f"{app_settings.keycloak_server_url}/admin/realms/{realm_name}/clients/{client_id}/authz/resource-server/permission/scope/{permission_id}"
                    permission_data_raw = realm_admin.connection.raw_get(
                        permission_url,
                        max=-1,
                        permission=False,
                    )

                    # Get resources and scopes
                    permission_resources_url = f"{app_settings.keycloak_server_url}/admin/realms/{realm_name}/clients/{client_id}/authz/resource-server/policy/{permission_id}/resources"
                    permission_resources_data_raw = realm_admin.connection.raw_get(
                        permission_resources_url,
                        max=-1,
                        permission=False,
                    )

                    permission_scopes_url = f"{app_settings.keycloak_server_url}/admin/realms/{realm_name}/clients/{client_id}/authz/resource-server/policy/{permission_id}/scopes"
                    permission_scopes_data_raw = realm_admin.connection.raw_get(
                        permission_scopes_url,
                        max=-1,
                        permission=False,
                    )

                    # Update the permission without the user's policy
                    permission_update_payload = {
                        "id": permission_data_raw.json()["id"],
                        "name": permission_data_raw.json()["name"],
                        "description": permission_data_raw.json()["description"],
                        "type": permission_data_raw.json()["type"],
                        "logic": permission_data_raw.json()["logic"],
                        "decisionStrategy": permission_data_raw.json()["decisionStrategy"],
                        "resources": [permission_resources_data_raw.json()[0]["_id"]],
                        "policies": update_policy,
                        "scopes": [permission_scopes_data_raw.json()[0]["id"]],
                    }

                    permission_update_url = f"{app_settings.keycloak_server_url}/admin/realms/{realm_name}/clients/{client_id}/authz/resource-server/permission/scope/{permission_id}"
                    realm_admin.connection.raw_put(
                        permission_update_url,
                        data=json.dumps(permission_update_payload),
                        max=-1,
                        permission=False,
                    )

                    logger.debug(f"Removed user {user_auth_id} from permission {permission_name}")
                else:
                    logger.debug(f"User {user_auth_id} was not associated with permission {permission_name}")

        except Exception as e:
            logger.error(f"Error removing user policy from resource permissions: {str(e)}")
            raise

    async def add_user_policy_to_resource_permissions(
        self,
        realm_name: str,
        client_id: str,
        resource_type: str,
        resource_id: str,
        user_auth_id: str,
        scopes: List[str] = None,
    ) -> None:
        """Add a user's policy to existing resource permissions.

        This method is used when a resource already exists and we need to grant
        a new user access to it. It associates the user's policy with the
        existing resource permissions.

        Args:
            realm_name: Name of the realm
            client_id: The Keycloak internal client UUID
            resource_type: Type of resource (e.g., "project", "cluster")
            resource_id: The resource UUID
            user_auth_id: The Keycloak user ID to grant access to
            scopes: List of scopes to grant (defaults to ["view", "manage"])
        """
        try:
            realm_admin = self.get_realm_admin(realm_name)

            # Default scopes if not provided
            if scopes is None:
                scopes = ["view", "manage"]

            # Get or create user policy
            policy_name = f"urn:bud:policy:{user_auth_id}"
            existing_policies = realm_admin.get_client_authz_policies(client_id)
            user_policy = next((p for p in existing_policies if p["name"] == policy_name), None)

            if not user_policy:
                # Create user policy if it doesn't exist
                user_policy = {
                    "name": policy_name,
                    "description": f"User policy for {user_auth_id}",
                    "type": "user",
                    "logic": "POSITIVE",
                    "decisionStrategy": "UNANIMOUS",
                    "users": [user_auth_id],
                }

                policy_url = f"{app_settings.keycloak_server_url}/admin/realms/{realm_name}/clients/{client_id}/authz/resource-server/policy/user"
                data_raw = realm_admin.connection.raw_post(
                    policy_url,
                    data=json.dumps(user_policy),
                    max=-1,
                    permission=False,
                )
                user_policy_id = data_raw.json()["id"]
                logger.info(f"Created user policy {policy_name}")
            else:
                user_policy_id = user_policy["id"]
                logger.debug(f"Using existing user policy {policy_name}")

            # Check if resource exists
            resource_name = f"URN::{resource_type}::{resource_id}"
            resources = realm_admin.get_client_authz_resources(client_id)
            resource_obj = next((r for r in resources if r["name"] == resource_name), None)

            if not resource_obj:
                logger.error(f"Resource {resource_name} not found")
                raise ValueError(f"Resource {resource_name} does not exist")

            # For each scope, update the corresponding permission to include the user's policy
            for scope in scopes:
                permission_name = f"urn:bud:permission:{resource_type}:{resource_id}:{scope}"

                # Get existing permissions
                permissions_url = f"{app_settings.keycloak_server_url}/admin/realms/{realm_name}/clients/{client_id}/authz/resource-server/permission"
                permissions_data_raw = realm_admin.connection.raw_get(
                    permissions_url,
                    max=-1,
                    permission=False,
                )
                permissions = permissions_data_raw.json()

                # Find the permission for this resource and scope
                permission = next((p for p in permissions if p["name"] == permission_name), None)

                if not permission:
                    logger.warning(f"Permission {permission_name} not found, skipping")
                    continue

                permission_id = permission["id"]

                # Get current associated policies
                permission_policies_url = f"{app_settings.keycloak_server_url}/admin/realms/{realm_name}/clients/{client_id}/authz/resource-server/policy/{permission_id}/associatedPolicies"
                permission_policies_data_raw = realm_admin.connection.raw_get(
                    permission_policies_url,
                    max=-1,
                    permission=False,
                )

                # Build list of policy IDs to update
                update_policy = []
                for policy in permission_policies_data_raw.json():
                    update_policy.append(policy["id"])

                # Add user policy if not already in the list
                if user_policy_id not in update_policy:
                    update_policy.append(user_policy_id)

                    # Get permission details for update
                    permission_url = f"{app_settings.keycloak_server_url}/admin/realms/{realm_name}/clients/{client_id}/authz/resource-server/permission/scope/{permission_id}"
                    permission_data_raw = realm_admin.connection.raw_get(
                        permission_url,
                        max=-1,
                        permission=False,
                    )

                    # Get resources and scopes
                    permission_resources_url = f"{app_settings.keycloak_server_url}/admin/realms/{realm_name}/clients/{client_id}/authz/resource-server/policy/{permission_id}/resources"
                    permission_resources_data_raw = realm_admin.connection.raw_get(
                        permission_resources_url,
                        max=-1,
                        permission=False,
                    )

                    permission_scopes_url = f"{app_settings.keycloak_server_url}/admin/realms/{realm_name}/clients/{client_id}/authz/resource-server/policy/{permission_id}/scopes"
                    permission_scopes_data_raw = realm_admin.connection.raw_get(
                        permission_scopes_url,
                        max=-1,
                        permission=False,
                    )

                    # Update the permission with the new policy list
                    permission_update_payload = {
                        "id": permission_data_raw.json()["id"],
                        "name": permission_data_raw.json()["name"],
                        "description": permission_data_raw.json()["description"],
                        "type": permission_data_raw.json()["type"],
                        "logic": permission_data_raw.json()["logic"],
                        "decisionStrategy": permission_data_raw.json()["decisionStrategy"],
                        "resources": [permission_resources_data_raw.json()[0]["_id"]],
                        "policies": update_policy,
                        "scopes": [permission_scopes_data_raw.json()[0]["id"]],
                    }

                    permission_update_url = f"{app_settings.keycloak_server_url}/admin/realms/{realm_name}/clients/{client_id}/authz/resource-server/permission/scope/{permission_id}"
                    realm_admin.connection.raw_put(
                        permission_update_url,
                        data=json.dumps(permission_update_payload),
                        max=-1,
                        permission=False,
                    )

                    logger.debug(f"Added user {user_auth_id} to permission {permission_name}")
                else:
                    logger.debug(f"User {user_auth_id} already has permission {permission_name}")

        except Exception as e:
            logger.error(f"Error adding user policy to resource permissions: {str(e)}")
            raise

    async def get_user_permissions_for_resource(
        self,
        realm_name: str,
        client_id: str,
        user_auth_id: str,
        resource_type: str,
        resource_id: str = None,
    ) -> List[str]:
        """Get all permissions a user has for a specific resource.

        Args:
            realm_name: Name of the realm
            client_id: The Keycloak internal client UUID
            user_auth_id: The Keycloak user ID
            resource_type: Type of resource (e.g., "project", "cluster")
            resource_id: The resource UUID (None for global permissions)

        Returns:
            List of scopes the user has for this resource
        """
        try:
            realm_admin = self.get_realm_admin(realm_name)
            user_scopes = []

            # Check if user policy exists
            policy_name = f"urn:bud:policy:{user_auth_id}"
            existing_policies = realm_admin.get_client_authz_policies(client_id)
            user_policy = next((p for p in existing_policies if p["name"] == policy_name), None)

            if not user_policy:
                return user_scopes  # User has no policy, so no permissions

            user_policy_id = user_policy["id"]

            # Get all permissions
            permissions_url = f"{app_settings.keycloak_server_url}/admin/realms/{realm_name}/clients/{client_id}/authz/resource-server/permission"
            permissions_data_raw = realm_admin.connection.raw_get(
                permissions_url,
                max=-1,
                permission=False,
            )
            permissions = permissions_data_raw.json()

            # Check permissions for this resource
            if resource_id:
                # Specific resource permissions
                for permission in permissions:
                    if permission["name"].startswith(f"urn:bud:permission:{resource_type}:{resource_id}:"):
                        # Check if user policy is associated
                        permission_id = permission["id"]
                        permission_policies_url = f"{app_settings.keycloak_server_url}/admin/realms/{realm_name}/clients/{client_id}/authz/resource-server/policy/{permission_id}/associatedPolicies"
                        permission_policies_data_raw = realm_admin.connection.raw_get(
                            permission_policies_url,
                            max=-1,
                            permission=False,
                        )

                        # Check if user policy is in the list
                        for policy in permission_policies_data_raw.json():
                            if policy["id"] == user_policy_id:
                                # Extract scope from permission name
                                scope = permission["name"].split(":")[-1]
                                user_scopes.append(scope)
                                break
            else:
                # Global permissions (module level)
                for permission in permissions:
                    if (
                        permission["name"] == f"urn:bud:permission:{resource_type}:module:view"
                        or permission["name"] == f"urn:bud:permission:{resource_type}:module:manage"
                    ):
                        # Check if user policy is associated
                        permission_id = permission["id"]
                        permission_policies_url = f"{app_settings.keycloak_server_url}/admin/realms/{realm_name}/clients/{client_id}/authz/resource-server/policy/{permission_id}/associatedPolicies"
                        permission_policies_data_raw = realm_admin.connection.raw_get(
                            permission_policies_url,
                            max=-1,
                            permission=False,
                        )

                        # Check if user policy is in the list
                        for policy in permission_policies_data_raw.json():
                            if policy["id"] == user_policy_id:
                                # Extract scope from permission name
                                scope = permission["name"].split(":")[-1]
                                user_scopes.append(scope)
                                break

            return user_scopes

        except Exception as e:
            logger.error(f"Error getting user permissions for resource: {str(e)}")
            return []

    async def create_resource_with_permissions(
        self,
        realm_name: str,
        client_id: str,  # internal KC UUID (returned by create_client)
        resource: ResourceCreate,  # {resource_type, resource_id, scopes=[view,manage]}
        user_auth_id: str,  # Keycloak user UUID (the "sub" claim)
    ) -> None:
        """1, Create *one* Resource Server "resource" named
            URN::<rtype>::<rid>::<scope>
        2,Create (or reuse) a *user* policy for `user_auth_id`
        3,Create (or reuse) a *permission* that ties the resource + policy
        so Keycloak can later answer:  Does this user have <scope> on this object?

        The helper is **idempotent**  calling it twice won't duplicate anything.
        """  # noqa: D205
        try:
            realm_admin = self.get_realm_admin(realm_name)

            # ----------
            # ACCEPTED SCOPES
            # ----------
            #  - If caller sent an empty list we fallback to the canonical pair
            #  - Everything else is validated against the module-level scopes
            module_scopes = {"view", "manage"}
            scopes = set(resource.scopes or module_scopes)  # insure not empty
            unknown = scopes - module_scopes
            if unknown:
                raise ValueError(f"Unknown scope(s) {unknown} - supported: {module_scopes}")

            # ----------------------------------------------------------
            # 1. RESOURCE  (one per scope so that the RPT carries it)
            # ----------------------------------------------------------
            res_name = f"URN::{resource.resource_type}::{resource.resource_id}"
            payload = {
                "name": res_name,
                "type": resource.resource_type.capitalize(),
                "owner": {"id": client_id},
                "ownerManagedAccess": True,
                "displayName": f"{resource.resource_type.capitalize()} {resource.resource_id}",
                "scopes": [
                    {"name": "view"},
                    {"name": "manage"},
                ],
            }
            resource_data = realm_admin.create_client_authz_resource(client_id, payload)

            # Scoped From Keycloak
            kc_scopes = realm_admin.get_client_authz_scopes(client_id)

            # Get The User Policy
            policy_name = f"urn:bud:policy:{user_auth_id}"
            policy_data = next(
                (p for p in realm_admin.get_client_authz_policies(client_id) if p["name"] == policy_name),
                None,
            )
            user_policy_id = policy_data["id"]

            for scope in scopes:
                scope_id = next(s["id"] for s in kc_scopes if s["name"] == scope)

                logger.debug(f"Scope ID: {scope_id}")

                permission = {
                    "name": f"urn:bud:permission:{resource.resource_type}:{resource.resource_id}:{scope}",
                    "description": f"Permission for {resource.resource_type} {resource.resource_id} to {scope}",
                    "resources": [resource_data["_id"]],
                    "policies": [user_policy_id],
                    "type": "scope",
                    "logic": "POSITIVE",
                    "scopes": [scope_id],
                    "decisionStrategy": "AFFIRMATIVE",
                }

                logger.debug(f"Creating permission: {json.dumps(permission, indent=4)}")
                permission_url = f"{app_settings.keycloak_server_url}/admin/realms/{realm_name}/clients/{client_id}/authz/resource-server/permission/scope"
                data_raw = realm_admin.connection.raw_post(
                    permission_url,
                    data=json.dumps(permission),
                    max=-1,
                    permission=False,
                )

                logger.debug(f"Permission response: {data_raw.json()}")
                _ = data_raw.json()["id"]  # Permission created successfully

        except Exception as e:
            logger.error(f"Error creating resource with permissions: {str(e)}", exc_info=True)
            raise

    def annotate_resources_with_permissions(self, resources: List[Dict], user_permissions: List[Dict]) -> List[Dict]:
        user_permission_names = {perm["name"] for perm in user_permissions}

        for resource in resources:
            scopes = resource.get("scopes", [])
            resource_name = resource.get("name")
            resource.get("type")

            # Skip if resource doesn't have scopes
            if not scopes:
                resource["has_permission"] = False
                continue

            # Generate possible permission names to match against user permissions
            matched = False
            for scope in scopes:
                scope_name = scope["name"]

                # Handle dynamic and static permission formats
                if resource_name.startswith("URN::project::"):
                    project_id = resource_name.split("::")[-1]
                    permission_urn = f"urn:bud:permission:project:{project_id}:{scope_name}"
                elif resource_name.startswith("module_"):
                    module_type = resource_name.split("module_")[-1]
                    permission_urn = f"urn:bud:permission:{module_type}:module:{scope_name}"
                else:
                    continue

                if permission_urn in user_permission_names:
                    matched = True
                    break

            resource["has_permission"] = matched

        return resources

    def format_permissions_output(self, resources, user_permissions):
        user_permission_names = {perm["name"] for perm in user_permissions}

        global_scopes = []
        project_scopes = []
        user_scopes = []
        model_scopes = []
        cluster_scopes = []
        endpoint_scopes = []
        benchmark_scopes = []

        for resource in resources:
            resource_name = resource["name"]
            display_name = resource.get("displayName", resource_name)
            resource_id = resource.get("_id")

            scoped_permissions = []

            for scope in resource.get("scopes", []):
                scope_name = scope["name"]

                # Determine permission URN
                if resource_name.startswith("URN::project::"):
                    project_uuid = resource_name.split("::")[-1]
                    perm_name = f"endpoint:{scope_name}"
                    urn = f"urn:bud:permission:project:{project_uuid}:{scope_name}"
                elif resource_name.startswith("URN::user::"):
                    user_uuid = resource_name.split("::")[-1]
                    perm_name = f"user:{scope_name}"
                    urn = f"urn:bud:permission:user:{user_uuid}:{scope_name}"
                elif resource_name.startswith("URN::model::"):
                    model_uuid = resource_name.split("::")[-1]
                    perm_name = f"model:{scope_name}"
                    urn = f"urn:bud:permission:model:{model_uuid}:{scope_name}"
                elif resource_name.startswith("URN::cluster::"):
                    cluster_uuid = resource_name.split("::")[-1]
                    perm_name = f"cluster:{scope_name}"
                    urn = f"urn:bud:permission:cluster:{cluster_uuid}:{scope_name}"
                elif resource_name.startswith("URN::endpoint::"):
                    endpoint_uuid = resource_name.split("::")[-1]
                    perm_name = f"endpoint:{scope_name}"
                    urn = f"urn:bud:permission:endpoint:{endpoint_uuid}:{scope_name}"
                elif resource_name.startswith("URN::benchmark::"):
                    benchmark_uuid = resource_name.split("::")[-1]
                    perm_name = f"benchmark:{scope_name}"
                    urn = f"urn:bud:permission:benchmark:{benchmark_uuid}:{scope_name}"
                elif resource_name.startswith("module_"):
                    module_name = resource_name.replace("module_", "")
                    perm_name = f"{module_name}:{scope_name}"
                    urn = f"urn:bud:permission:{module_name}:module:{scope_name}"
                else:
                    continue  # skip unknown patterns

                has_permission = urn in user_permission_names

                scoped_permissions.append({"name": perm_name, "has_permission": has_permission})

            # Separate global module scopes from resource-specific ones
            if resource_name.startswith("module_"):
                global_scopes.extend(scoped_permissions)
            elif resource_name.startswith("URN::project::"):
                project_scopes.append(
                    {"id": project_uuid, "rs_id": resource_id, "name": display_name, "permissions": scoped_permissions}
                )
            elif resource_name.startswith("URN::user::"):
                user_scopes.append(
                    {"id": user_uuid, "rs_id": resource_id, "name": display_name, "permissions": scoped_permissions}
                )
            elif resource_name.startswith("URN::model::"):
                model_scopes.append(
                    {"id": model_uuid, "rs_id": resource_id, "name": display_name, "permissions": scoped_permissions}
                )
            elif resource_name.startswith("URN::cluster::"):
                cluster_scopes.append(
                    {"id": cluster_uuid, "rs_id": resource_id, "name": display_name, "permissions": scoped_permissions}
                )
            elif resource_name.startswith("URN::endpoint::"):
                endpoint_scopes.append(
                    {
                        "id": endpoint_uuid,
                        "rs_id": resource_id,
                        "name": display_name,
                        "permissions": scoped_permissions,
                    }
                )
            elif resource_name.startswith("URN::benchmark::"):
                benchmark_scopes.append(
                    {
                        "id": benchmark_uuid,
                        "rs_id": resource_id,
                        "name": display_name,
                        "permissions": scoped_permissions,
                    }
                )

        return {
            "result": {
                "global_scopes": global_scopes,
                "project_scopes": project_scopes,
                "user_scopes": user_scopes,
                "model_scopes": model_scopes,
                "cluster_scopes": cluster_scopes,
                "endpoint_scopes": endpoint_scopes,
                "benchmark_scopes": benchmark_scopes,
            }
        }

    async def get_user_permissions_via_admin(
        self,
        user_id: str,
        realm_name: str,
        client_id: str,
    ) -> Dict[str, List[str]]:
        """Get the fine-grained permissions assigned to a user (without needing a token).

        Args:
            user_id: The Keycloak user ID
            realm_name: The name of the realm
            client_id: The Keycloak internal client UUID

        Returns:
            Dict[str, List[str]]: A dictionary of resource names and allowed scopes
        """
        try:
            realm_admin = self.get_realm_admin(realm_name)
            policy_name = f"urn:bud:policy:{user_id}"

            logger.debug(f"Retrieving permissions for policy: {policy_name}")

            # 1. Find the user's policy
            policies = realm_admin.get_client_authz_policies(client_id)
            user_policy = next((p for p in policies if p["name"] == policy_name), None)
            if not user_policy:
                logger.warning(f"No policy found for user {user_id}")
                return {"permissions": []}

            user_policy_id = user_policy["id"]

            # call the the keycloak using api
            url = f"{app_settings.keycloak_server_url}/admin/realms/{realm_name}/clients/{client_id}/authz/resource-server/policy/{user_policy_id}/dependentPolicies"
            data_raw = realm_admin.connection.raw_get(
                url,
                max=-1,
                permission=False,
            )

            logger.debug(f"Retrieved {len(data_raw.json())} permissions for user {user_id}")

            # Get all the permissions
            _ = realm_admin.get_client_authz_permissions(client_id)

            # Get all the resources
            resources = realm_admin.get_client_authz_resources(client_id)

            _ = self.annotate_resources_with_permissions(resources=resources, user_permissions=data_raw.json())

            # formatted
            formatted = self.format_permissions_output(resources=resources, user_permissions=data_raw.json())

            logger.debug(f"Formatted {len(formatted.get('permissions', []))} permissions for user {user_id}")

            return formatted

        except Exception as e:
            logger.error(f"Failed to retrieve permissions for user {user_id}: {str(e)}", exc_info=True)
            raise

    async def update_user_global_permissions(
        self,
        user_auth_id: str,
        permissions: List[Dict[str, Union[str, bool]]],
        realm_name: str,
        client_id: str,
    ) -> None:
        """Update global permissions for a user in Keycloak.

        Args:
            user_auth_id: The Keycloak user auth ID
            permissions: List of permissions dicts with 'name' (str) and 'has_permission' (bool) fields
            realm_name: The realm name
            client_id: The client ID
        """
        try:
            realm_admin = self.get_realm_admin(realm_name)

            # Get or create user policy
            policy_name = f"urn:bud:policy:{user_auth_id}"
            existing_policies = realm_admin.get_client_authz_policies(client_id)
            user_policy = next((p for p in existing_policies if p["name"] == policy_name), None)

            if not user_policy:
                # Create user policy
                user_policy_data = {
                    "name": policy_name,
                    "description": f"User policy for {user_auth_id}",
                    "logic": "POSITIVE",
                    "users": [str(user_auth_id)],
                }

                policy_url = f"{app_settings.keycloak_server_url}/admin/realms/{realm_name}/clients/{client_id}/authz/resource-server/policy/user"

                data_raw = realm_admin.connection.raw_post(
                    policy_url,
                    data=json.dumps(user_policy_data),
                    max=-1,
                    permission=False,
                )

                user_policy_id = data_raw.json()["id"]
            else:
                user_policy_id = user_policy["id"]

            # Process each permission update
            for permission in permissions:
                # Parse permission name (e.g., "cluster:view" -> module="cluster", scope="view")
                parts = permission["name"].split(":")
                if len(parts) != 2:
                    logger.warning(f"Invalid permission format: {permission['name']}")
                    continue

                module_name, scope_name = parts

                # Get the permission URL
                permission_search_url = f"{app_settings.keycloak_server_url}/admin/realms/{realm_name}/clients/{client_id}/authz/resource-server/permission?name=urn%3Abud%3Apermission%3A{module_name}%3Amodule%3A{scope_name}&scope={scope_name}&type=scope"

                try:
                    data_raw = realm_admin.connection.raw_get(
                        permission_search_url,
                        max=-1,
                        permission=False,
                    )

                    if not data_raw.json():
                        logger.warning(f"Permission not found: {permission['name']}")
                        continue

                    permission_id = data_raw.json()[0]["id"]

                    # Get current permission details
                    permission_url = f"{app_settings.keycloak_server_url}/admin/realms/{realm_name}/clients/{client_id}/authz/resource-server/permission/scope/{permission_id}"
                    permission_data_raw = realm_admin.connection.raw_get(
                        permission_url,
                        max=-1,
                        permission=False,
                    )

                    # Get associated resources
                    permission_resources_url = f"{app_settings.keycloak_server_url}/admin/realms/{realm_name}/clients/{client_id}/authz/resource-server/policy/{permission_id}/resources"
                    permission_resources_data_raw = realm_admin.connection.raw_get(
                        permission_resources_url,
                        max=-1,
                        permission=False,
                    )

                    # Get scopes
                    permission_scopes_url = f"{app_settings.keycloak_server_url}/admin/realms/{realm_name}/clients/{client_id}/authz/resource-server/policy/{permission_id}/scopes"
                    permission_scopes_data_raw = realm_admin.connection.raw_get(
                        permission_scopes_url,
                        max=-1,
                        permission=False,
                    )

                    # Get associated policies
                    permission_policies_url = f"{app_settings.keycloak_server_url}/admin/realms/{realm_name}/clients/{client_id}/authz/resource-server/policy/{permission_id}/associatedPolicies"
                    permission_policies_data_raw = realm_admin.connection.raw_get(
                        permission_policies_url,
                        max=-1,
                        permission=False,
                    )

                    # Update policy list based on has_permission
                    update_policies = []
                    for policy in permission_policies_data_raw.json():
                        if policy["name"] != policy_name:
                            update_policies.append(policy["id"])

                    if permission["has_permission"]:
                        # Add user policy if not already present
                        if user_policy_id not in update_policies:
                            update_policies.append(user_policy_id)
                    else:
                        # Remove user policy if present
                        if user_policy_id in update_policies:
                            update_policies.remove(user_policy_id)

                    # Update the permission
                    permission_update_payload = {
                        "id": permission_data_raw.json()["id"],
                        "name": permission_data_raw.json()["name"],
                        "description": permission_data_raw.json()["description"],
                        "type": permission_data_raw.json()["type"],
                        "logic": permission_data_raw.json()["logic"],
                        "decisionStrategy": permission_data_raw.json()["decisionStrategy"],
                        "resources": [r["_id"] for r in permission_resources_data_raw.json()],
                        "policies": update_policies,
                        "scopes": [s["id"] for s in permission_scopes_data_raw.json()],
                    }

                    # Update the permission
                    permission_update_url = f"{app_settings.keycloak_server_url}/admin/realms/{realm_name}/clients/{client_id}/authz/resource-server/permission/scope/{permission_id}"
                    realm_admin.connection.raw_put(
                        permission_update_url,
                        data=json.dumps(permission_update_payload),
                        max=-1,
                        permission=False,
                    )

                    logger.debug(f"Updated permission {permission['name']} for user {user_auth_id}")

                except Exception as e:
                    logger.error(f"Error updating permission {permission['name']}: {str(e)}")
                    continue

        except Exception as e:
            logger.error(f"Error updating global permissions for user {user_auth_id}: {str(e)}", exc_info=True)
            raise

    async def validate_token(self, token: str, realm_name: str, credentials: TenantClientSchema) -> dict:
        """Validate a JWT token and return the decoded claims if valid.

        Args:
            token: JWT access token
            realm_name: Realm name the token belongs to
            credentials: Client info (used to initialize OpenID client)

        Returns:
            dict: Decoded token claims if valid, else raises exception

        Example:
        {
            "exp": 1712180647,
            "iat": 1712180347,
            "auth_time": 1712180345,
            "jti": "abc123-def456",
            "iss": "https://keycloak.example.com/realms/myrealm",
            "aud": "my-client-id",
            "sub": "bf7acff1-2b9c-4936-bde2-3f607f3e3c67",
            "typ": "Bearer",
            "azp": "my-client-id",
            "session_state": "b928e15b-b3ff-4f18-9ff9-f19dd29d5142",
            "acr": "1",
            "realm_access": {
                "roles": [
                "user",
                "admin"
                ]
            },
            "resource_access": {
                "my-client-id": {
                "roles": ["reader", "writer"]
                }
            },
            "scope": "email profile",
            "email_verified": True,
            "preferred_username": "john.doe"
            }
        """
        try:
            openid_client = self.get_keycloak_openid_client(realm_name, credentials)

            decoded_token = openid_client.decode_token(
                token,
            )

            logger.info(f"Token successfully validated for realm {realm_name}")
            return decoded_token

        except (KeycloakAuthenticationError, KeycloakGetError) as e:
            logger.error(f"Keycloak error during token validation: {str(e)}")
            raise

        except ExpiredSignatureError:
            logger.warning("Token has expired")
            raise

        except JWTError as e:
            logger.warning(f"General JWT error: {str(e)}")
            raise

        except KeycloakInvalidTokenError as e:
            logger.warning(f"Keycloak invalid token error: {str(e)}")
            raise

        except Exception as e:
            logger.error(f"Unexpected error validating token: {str(e)}")
            raise

    async def get_multiple_users_permissions_via_admin(
        self,
        user_ids: List[str],
        realm_name: str,
        client_id: str,
    ) -> Dict[str, Dict[str, List[str]]]:
        """Fetch fine-grained permissions for multiple users via admin API.

        Args:
            user_ids (List[str]): List of Keycloak user IDs
            realm_name (str): Name of the realm
            client_id (str): Keycloak internal client UUID

        Returns:
            Dict[str, Dict[str, List[str]]]: Permissions per user, keyed by user ID
        """
        results = {}

        for user_id in user_ids:
            try:
                permissions = await self.get_user_permissions_via_admin(
                    user_id=user_id,
                    realm_name=realm_name,
                    client_id=client_id,
                )
                results[user_id] = permissions
            except Exception as e:
                logger.warning(f"Failed to fetch permissions for user {user_id}: {str(e)}")
                results[user_id] = {"error": str(e)}

        return results

    async def assign_user_to_resource(self, user_id: str, resource_id: str, realm_name: str, client_id: str) -> None:
        """Assign a user to a resource in Keycloak.

        Args:
            user_id: The Keycloak user ID
            resource_id: The Keycloak resource ID
            realm_name: The name of the realm
            client_id: The Keycloak internal client UUID

        Returns:
            None
        """
        pass

    async def create_identity_provider_mapper(self, realm_name: str, provider_alias: str, mapper_config: dict) -> None:
        """Create an identity provider mapper in Keycloak.

        Args:
            realm_name: The name of the realm
            provider_alias: The alias of the identity provider
            mapper_config: Configuration dictionary containing mapper details

        Returns:
            None
        """
        try:
            # realm_admin = self.get_realm_admin(realm_name)

            # Create the mapper for the identity provider
            # Note: This is a placeholder implementation as Keycloak Admin API
            # for identity provider mappers requires specific endpoint handling
            logger.debug(f"Creating identity provider mapper for {provider_alias}: {mapper_config.get('name')}")

            # In a full implementation, this would call:
            # realm_admin.create_identity_provider_mapper(provider_alias, mapper_config)
            # But since this method might not be available in all Keycloak Python clients,
            # we'll just log and continue

        except Exception as e:
            logger.warning(f"Failed to create identity provider mapper: {e}")
            # Don't raise - mappers are optional for OAuth to work

    async def configure_identity_provider(self, realm_name: str, provider_config: dict) -> None:
        """Configure an identity provider in Keycloak.

        Args:
            realm_name: The name of the realm
            provider_config: Configuration dictionary containing provider details

        Returns:
            None
        """
        try:
            realm_admin = self.get_realm_admin(realm_name)

            # Extract provider details from config
            alias = provider_config.get("alias")
            provider_id = provider_config.get("providerId")
            client_id = provider_config.get("clientId")
            client_secret = provider_config.get("clientSecret")
            config = provider_config.get("config", {})

            if not all([alias, provider_id, client_id, client_secret]):
                raise ValueError("Missing required provider configuration fields")

            # Build the identity provider representation
            idp_representation = {
                "alias": alias,
                "providerId": provider_id,
                "enabled": True,
                "storeToken": False,
                "trustEmail": True,
                "linkOnly": False,
                "firstBrokerLoginFlowAlias": "first broker login",
                "config": {
                    "clientId": client_id,
                    "clientSecret": client_secret,
                    "syncMode": "IMPORT",
                    "useJwksUrl": "true",
                    **config,  # Merge provider-specific config
                },
            }

            # Create or update the identity provider
            try:
                realm_admin.create_idp(payload=idp_representation)
                logger.info(f"Identity provider {alias} created successfully in realm {realm_name}")
            except Exception as e:
                if "409" in str(e):  # Provider already exists
                    # Update existing provider
                    realm_admin.update_idp(alias=alias, payload=idp_representation)
                    logger.info(f"Identity provider {alias} updated successfully in realm {realm_name}")
                else:
                    raise

        except Exception as e:
            logger.error(f"Failed to configure identity provider in realm {realm_name}: {str(e)}")
            raise

    def get_broker_login_url(
        self, realm_name: str, provider: str, redirect_uri: str, state: str, client_id: str = None
    ) -> str:
        """Generate OAuth broker login URL for Keycloak.

        Args:
            realm_name: The Keycloak realm name
            provider: The OAuth provider alias (e.g., 'google', 'github')
            redirect_uri: The redirect URI after successful authentication
            state: The state parameter for CSRF protection
            client_id: Optional client ID (defaults to 'default-internal-client')

        Returns:
            The complete OAuth broker login URL
        """
        from urllib.parse import urlencode

        # Use the default client if not specified
        if not client_id:
            client_id = "default-internal-client"

        # Construct the Keycloak broker login URL
        base_url = app_settings.keycloak_server_url.rstrip("/")

        # Convert host.docker.internal to 127.0.0.1 for browser access (matches GitHub OAuth)
        if "host.docker.internal" in base_url:
            base_url = base_url.replace("host.docker.internal", "127.0.0.1")

        # Use the standard Keycloak authorization endpoint with identity provider hint
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "kc_idp_hint": provider,  # This tells Keycloak to use the specified identity provider
        }

        auth_url = f"{base_url}/realms/{realm_name}/protocol/openid-connect/auth?{urlencode(params)}"

        logger.debug(f"Generated broker login URL for provider {provider} in realm {realm_name}")
        return auth_url
