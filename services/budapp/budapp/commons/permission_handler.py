from functools import WRAPPER_ASSIGNMENTS, update_wrapper, wraps
from typing import Callable, List, Optional, Union

from fastapi import Depends, HTTPException, status
from keycloak.exceptions import KeycloakAuthenticationError
from sqlalchemy.orm import Session

from budapp.commons import logging
from budapp.commons.constants import PermissionEnum, UserRoleEnum
from budapp.commons.dependencies import get_current_active_user, get_current_active_user_or_internal, get_session
from budapp.commons.keycloak import KeycloakManager
from budapp.permissions.schemas import CheckUserResourceScope
from budapp.permissions.service import PermissionService
from budapp.user_ops.crud import UserDataManager
from budapp.user_ops.models import Tenant, TenantClient
from budapp.user_ops.schemas import TenantClientSchema, User

from .config import app_settings


logger = logging.get_logger(__name__)


async def check_resource_based_permissions(
    user: User,
    session: Session,
    permissions: List[PermissionEnum],
    resource_type: str,
    entity_id: Optional[str],
) -> bool:
    """Check resource-based permissions for a user.

    Args:
        user: The current user
        session: Database session
        permissions: List of required permissions
        resource_type: Type of resource (e.g., "project")
        entity_id: ID of the specific resource

    Returns:
        True if user has permission, False otherwise
    """
    permission_service = PermissionService(session)

    # Check permissions in order of precedence
    for perm in permissions:
        module, scope = perm.value.split(":")

        # If checking endpoint permissions and resource type is project
        if module == "endpoint" and resource_type == "project":
            # First check if user has global project:manage permission
            try:
                has_project_manage = await permission_service.check_resource_permission_by_user(
                    user=user,
                    payload=CheckUserResourceScope(
                        resource_type="project",
                        entity_id=None,  # Global permission
                        scope="manage",
                    ),
                )

                if has_project_manage:
                    logger.debug("::PERMISSION:: User has global project:manage permission")
                    return True
            except Exception as e:
                logger.debug(f"::PERMISSION:: Failed to check global project:manage: {e}")

            # If no global project:manage, check specific project permission
            if entity_id:
                try:
                    has_permission = await permission_service.check_resource_permission_by_user(
                        user=user,
                        payload=CheckUserResourceScope(
                            resource_type=resource_type,
                            entity_id=entity_id,
                            scope=scope,  # view or manage from endpoint:view/manage
                        ),
                    )

                    if has_permission:
                        logger.debug(f"::PERMISSION:: User has {scope} permission on {resource_type} {entity_id}")
                        return True
                except Exception as e:
                    logger.debug(f"::PERMISSION:: Failed to check resource permission: {e}")

        # For other resource types, check the specific permission
        elif entity_id:
            try:
                has_permission = await permission_service.check_resource_permission_by_user(
                    user=user,
                    payload=CheckUserResourceScope(resource_type=resource_type, entity_id=entity_id, scope=scope),
                )

                if has_permission:
                    logger.debug(f"::PERMISSION:: User has {scope} permission on {resource_type} {entity_id}")
                    return True
            except Exception as e:
                logger.debug(f"::PERMISSION:: Failed to check resource permission: {e}")

    return False


def require_permissions(
    permissions: Union[PermissionEnum, List[PermissionEnum]] | None = None,
    roles: Union[UserRoleEnum, List[UserRoleEnum]] | None = None,
):
    """Decorator to check if user has required Keycloak roles or authorization scopes.

    Args:
        permissions: List of PermissionEnum (mapped to Keycloak resources/scopes)
        roles: List of UserRoleEnum (mapped to realm roles)

    Example:
        @require_permissions(roles=UserRoleEnum.ADMIN)
        @require_permissions(permissions=[PermissionEnum.CLUSTER_VIEW]).
    """  # noqa: D401
    if isinstance(permissions, PermissionEnum):
        permissions = [permissions]
    if isinstance(roles, UserRoleEnum):
        roles = [roles]

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(
            current_user: User = Depends(get_current_active_user),
            session: Session = Depends(get_session),
            *args,
            **kwargs,
        ):
            x_resource_type = kwargs.get("x_resource_type")
            x_entity_id = kwargs.get("x_entity_id")

            logger.debug(f"::PERMISSION::Checking permissions for user: {current_user.id}")
            logger.debug(f"::PERMISSION::Resource headers - Type: {x_resource_type}, Entity ID: {x_entity_id}")

            # Superuser shortcut
            if current_user.is_superuser:
                return await func(current_user=current_user, session=session, *args, **kwargs)

            if permissions == [PermissionEnum.CLIENT_ACCESS]:
                return await func(current_user=current_user, session=session, *args, **kwargs)

            # Check if resource-based permission check is needed
            if x_resource_type and permissions:
                has_permission = await check_resource_based_permissions(
                    user=current_user,
                    session=session,
                    permissions=permissions,
                    resource_type=x_resource_type,
                    entity_id=x_entity_id,
                )

                if has_permission:
                    return await func(current_user=current_user, session=session, *args, **kwargs)
                else:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions for this operation"
                    )

            # Fall back to global permission check if no resource headers
            else:
                # Keycloak Manager
                keycloak_manager = KeycloakManager()

                # TenantClientSchema
                realm_name = app_settings.default_realm_name
                tenant = await UserDataManager(session).retrieve_by_fields(
                    Tenant, {"realm_name": realm_name}, missing_ok=True
                )
                tenant_client = await UserDataManager(session).retrieve_by_fields(
                    TenantClient, {"tenant_id": tenant.id}, missing_ok=True
                )

                # Decrypt client secret for use
                decrypted_secret = await tenant_client.get_decrypted_client_secret()
                credentials = TenantClientSchema(
                    id=tenant_client.id,
                    client_id=tenant_client.client_id,
                    client_named_id=tenant_client.client_named_id,
                    client_secret=decrypted_secret,
                )
                openid = keycloak_manager.get_keycloak_openid_client(realm_name, credentials)

                permission_strings = []
                if permissions:
                    for perm in permissions:
                        module, scope = perm.value.split(":")
                        resource = f"module_{module}"
                        permission_strings.append(f"{resource}#{scope}")
                permissions_str = ",".join(permission_strings)
                logger.debug(f"::PERMISSION:: Permission Params: {permissions_str}")
                if permissions_str:
                    try:
                        # Check if user has all required permissions
                        uma_permissions = openid.uma_permissions(
                            token=current_user.raw_token,
                            permissions=permissions_str,
                            resource_server_id=credentials.client_id,
                            submit_request=False,
                        )

                        logger.debug(f"::PERMISSION:: UMA Permissions: {uma_permissions}")

                        # If we get here without an exception, the user has the required permissions
                        logger.debug(f"::PERMISSION:: User {current_user.id} has the required permissions")

                    except KeycloakAuthenticationError as e:
                        logger.warning(f"::PERMISSION:: User {current_user.id} found invalid bearer token: {str(e)}")
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid authentication credentials",
                            headers={"WWW-Authenticate": "Bearer"},
                        )

                    except Exception as e:
                        logger.warning(f"::PERMISSION:: User {current_user.id} lacks required permissions: {str(e)}")
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions for this operation"
                        )

            return await func(current_user=current_user, session=session, *args, **kwargs)

        return wrapper

    return decorator


def require_permissions_or_internal(
    permissions: Union[PermissionEnum, List[PermissionEnum]] | None = None,
    roles: Union[UserRoleEnum, List[UserRoleEnum]] | None = None,
):
    """Decorator to check permissions for JWT users or allow Dapr-internal calls."""
    if isinstance(permissions, PermissionEnum):
        permissions = [permissions]
    if isinstance(roles, UserRoleEnum):
        roles = [roles]

    def decorator(func: Callable) -> Callable:
        async def wrapper(
            current_user: User = Depends(get_current_active_user_or_internal),
            session: Session = Depends(get_session),
            *args,
            **kwargs,
        ):
            if getattr(current_user, "_is_internal", False):
                return await func(current_user=current_user, session=session, *args, **kwargs)

            x_resource_type = kwargs.get("x_resource_type")
            x_entity_id = kwargs.get("x_entity_id")

            logger.debug(f"::PERMISSION::Checking permissions for user: {current_user.id}")
            logger.debug(f"::PERMISSION::Resource headers - Type: {x_resource_type}, Entity ID: {x_entity_id}")

            if current_user.is_superuser:
                return await func(current_user=current_user, session=session, *args, **kwargs)

            if permissions == [PermissionEnum.CLIENT_ACCESS]:
                return await func(current_user=current_user, session=session, *args, **kwargs)

            if x_resource_type and permissions:
                has_permission = await check_resource_based_permissions(
                    user=current_user,
                    session=session,
                    permissions=permissions,
                    resource_type=x_resource_type,
                    entity_id=x_entity_id,
                )

                if has_permission:
                    return await func(current_user=current_user, session=session, *args, **kwargs)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions for this operation"
                )

            keycloak_manager = KeycloakManager()
            realm_name = app_settings.default_realm_name
            tenant = await UserDataManager(session).retrieve_by_fields(
                Tenant, {"realm_name": realm_name}, missing_ok=True
            )
            tenant_client = await UserDataManager(session).retrieve_by_fields(
                TenantClient, {"tenant_id": tenant.id}, missing_ok=True
            )

            decrypted_secret = await tenant_client.get_decrypted_client_secret()
            credentials = TenantClientSchema(
                id=tenant_client.id,
                client_id=tenant_client.client_id,
                client_named_id=tenant_client.client_named_id,
                client_secret=decrypted_secret,
            )
            openid = keycloak_manager.get_keycloak_openid_client(realm_name, credentials)

            permission_strings = []
            if permissions:
                for perm in permissions:
                    module, scope = perm.value.split(":")
                    resource = f"module_{module}"
                    permission_strings.append(f"{resource}#{scope}")
            permissions_str = ",".join(permission_strings)
            logger.debug(f"::PERMISSION:: Permission Params: {permissions_str}")
            if permissions_str:
                try:
                    openid.uma_permissions(
                        token=current_user.raw_token,
                        permissions=permissions_str,
                        resource_server_id=credentials.client_id,
                        submit_request=False,
                    )

                    logger.debug(f"::PERMISSION:: User {current_user.id} has the required permissions")

                except KeycloakAuthenticationError as e:
                    logger.warning(f"::PERMISSION:: User {current_user.id} found invalid bearer token: {str(e)}")
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid authentication credentials",
                        headers={"WWW-Authenticate": "Bearer"},
                    )

                except Exception as e:
                    logger.warning(f"::PERMISSION:: User {current_user.id} lacks required permissions: {str(e)}")
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions for this operation"
                    )

            return await func(current_user=current_user, session=session, *args, **kwargs)

        # Copy function metadata without __wrapped__ to prevent FastAPI from using original signature
        wrapper_assignments = tuple(a for a in WRAPPER_ASSIGNMENTS if a != "__wrapped__")
        update_wrapper(wrapper, func, assigned=wrapper_assignments)
        return wrapper

    return decorator
