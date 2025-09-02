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

"""OAuth services with proxied Keycloak URLs."""

from typing import Optional
from urllib.parse import urlencode

from budapp.commons import logging
from budapp.commons.config import app_settings


logger = logging.get_logger(__name__)


class ProxiedOAuthURLGenerator:
    """Generate proxied OAuth URLs that hide Keycloak from clients."""

    @staticmethod
    def get_proxied_authorization_url(
        base_url: str,
        realm_name: str,
        provider: str,
        redirect_uri: str,
        state: str,
        client_id: str = None,
    ) -> str:
        """Generate proxied OAuth authorization URL.

        Args:
            base_url: The application's base URL (e.g., http://localhost:9081)
            realm_name: The Keycloak realm name
            provider: The OAuth provider alias (e.g., 'google', 'github')
            redirect_uri: The redirect URI after successful authentication
            state: The state parameter for CSRF protection
            client_id: Optional client ID (defaults to 'default-internal-client')

        Returns:
            The proxied OAuth authorization URL that goes through our backend
        """
        if not client_id:
            client_id = "default-internal-client"

        # Build params for our proxy endpoint
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "realm_name": realm_name,
        }

        # Add provider hint if using identity brokering
        if provider:
            params["kc_idp_hint"] = provider

        # Generate URL that points to our proxy endpoint
        # Note: The proxy routes are registered at /oauth/proxy/* not /api/v1/auth/oauth/proxy/*
        proxy_url = f"{base_url}/oauth/proxy/authorize?{urlencode(params)}"

        logger.debug(f"Generated proxied OAuth URL: {proxy_url}")
        return proxy_url

    @staticmethod
    def get_proxied_token_url(base_url: str) -> str:
        """Get proxied token exchange URL.

        Args:
            base_url: The application's base URL

        Returns:
            The proxied token exchange URL
        """
        return f"{base_url}/oauth/proxy/token"

    @staticmethod
    def get_proxied_userinfo_url(base_url: str) -> str:
        """Get proxied userinfo URL.

        Args:
            base_url: The application's base URL

        Returns:
            The proxied userinfo URL
        """
        return f"{base_url}/oauth/proxy/userinfo"

    @staticmethod
    def get_proxied_logout_url(base_url: str) -> str:
        """Get proxied logout URL.

        Args:
            base_url: The application's base URL

        Returns:
            The proxied logout URL
        """
        return f"{base_url}/oauth/proxy/logout"
