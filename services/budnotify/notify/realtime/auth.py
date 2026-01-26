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

"""Keycloak JWT validation for real-time WebSocket authentication."""

from typing import Any, Optional

import jwt
from cachetools import TTLCache
from jwt import PyJWKClient
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

from notify.commons import logging
from notify.commons.config import app_settings

from .schemas import UserInfo


logger = logging.get_logger(__name__)

_jwks_client_cache: TTLCache[str, PyJWKClient] = TTLCache(maxsize=10, ttl=3600)
_public_key_cache: TTLCache[str, Any] = TTLCache(maxsize=100, ttl=300)


def _get_jwks_client(keycloak_url: str, realm: str) -> PyJWKClient:
    """Get or create a cached JWKS client for the specified realm.

    Args:
        keycloak_url: Base Keycloak server URL.
        realm: Keycloak realm name.

    Returns:
        PyJWKClient instance for fetching public keys.
    """
    cache_key = f"{keycloak_url}:{realm}"

    if cache_key in _jwks_client_cache:
        return _jwks_client_cache[cache_key]

    jwks_url = f"{keycloak_url}/realms/{realm}/protocol/openid-connect/certs"
    client = PyJWKClient(jwks_url)
    _jwks_client_cache[cache_key] = client

    return client


async def validate_keycloak_token(token: str) -> Optional[UserInfo]:
    """Validate a Keycloak JWT token and return user information.

    This function validates the token against Keycloak's JWKS endpoint,
    verifying the signature, expiration, and issuer claims.

    Args:
        token: The JWT access token to validate.

    Returns:
        UserInfo if the token is valid, None otherwise.
    """
    keycloak_url = app_settings.keycloak_url
    realm = app_settings.keycloak_realm

    if not keycloak_url or not realm:
        logger.error("Keycloak URL or realm not configured")
        return None

    try:
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")

        if not kid:
            logger.warning("Token missing 'kid' header")
            return None

        cache_key = f"{keycloak_url}:{realm}:{kid}"

        if cache_key in _public_key_cache:
            public_key = _public_key_cache[cache_key]
        else:
            jwks_client = _get_jwks_client(keycloak_url, realm)
            signing_key = jwks_client.get_signing_key_from_jwt(token)
            public_key = signing_key.key
            _public_key_cache[cache_key] = public_key

        expected_issuer = f"{keycloak_url}/realms/{realm}"

        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            issuer=expected_issuer,
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_iss": True,
                "verify_aud": False,
            },
        )

        user_id = payload.get("sub")
        if not user_id:
            logger.warning("Token missing 'sub' claim")
            return None

        return UserInfo(
            id=user_id,
            email=payload.get("email"),
            username=payload.get("preferred_username"),
            realm=realm,
        )

    except ExpiredSignatureError:
        logger.warning("Token has expired")
        return None

    except InvalidTokenError as e:
        logger.warning(f"Invalid token: {e}")
        return None

    except Exception as e:
        logger.error(f"Unexpected error validating token: {e}")
        return None


async def refresh_jwks_cache(keycloak_url: str, realm: str) -> bool:
    """Force refresh of the JWKS cache for a realm.

    This can be called when token validation fails due to key rotation.

    Args:
        keycloak_url: Base Keycloak server URL.
        realm: Keycloak realm name.

    Returns:
        True if cache was refreshed successfully.
    """
    cache_key = f"{keycloak_url}:{realm}"

    try:
        if cache_key in _jwks_client_cache:
            del _jwks_client_cache[cache_key]

        keys_to_remove = [k for k in _public_key_cache if k.startswith(f"{keycloak_url}:{realm}:")]
        for key in keys_to_remove:
            del _public_key_cache[key]

        _get_jwks_client(keycloak_url, realm)

        logger.debug(f"JWKS cache refreshed for realm {realm}")
        return True

    except Exception as e:
        logger.error(f"Failed to refresh JWKS cache: {e}")
        return False
