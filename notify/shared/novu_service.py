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

"""Provides utility functions and wrappers for interacting with Novu components."""

import asyncio
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import aiohttp
from aiohttp import client_exceptions

from notify.commons import logging
from notify.commons.config import app_settings
from notify.commons.exceptions import NovuApiClientException


logger = logging.get_logger(__name__)


class NovuBaseApiClient:
    """Base API client for interacting with Novu services."""

    async def _handle_response(
        self, response: aiohttp.ClientResponse, json: bool = True
    ) -> Tuple[bool, Union[Dict[str, Any], str]]:
        """Handle the API response and return a success status and corresponding data.

        Args:
        response (aiohttp.ClientResponse): The response object from an API request.
        json (bool, optional): Whether to parse the response as JSON. If False, returns the raw text. Defaults to True.

        Returns:
        Tuple[bool, Union[Dict[str, Any], str]]: A tuple where the first element indicates success (True/False),
        and the second element is either the parsed response data (JSON or text) on success or an error message on failure.

        Raises:
        aiohttp.ClientResponseError: Raised when the response status code is 4xx or 5xx.
        aiohttp.ClientError: Raised for client-side errors during the request.
        ValueError: Raised if there is an error in JSON decoding.
        Exception: Raised for any other unexpected errors.

        """
        try:
            # Raise exception for bad responses (4xx, 5xx)
            if response.status >= 400:
                raise aiohttp.ClientResponseError(response.request_info, response.history, status=response.status)
            if json:
                return True, await response.json()
            else:
                return True, await response.text()
        except aiohttp.ClientResponseError as http_err:
            json_body = await response.json()
            message = json_body.get("message", str(http_err))
            error_message = message[0] if isinstance(message, list) else message
            logger.error(error_message)
        except aiohttp.ClientError as request_error:
            logger.exception(request_error)
            error_message = "Bad request to server"
        except (ValueError, client_exceptions.ContentTypeError) as value_err:
            logger.exception(value_err)
            error_message = "Invalid response from server"
        except Exception as e:
            logger.exception(e)
            error_message = "Unexpected error occurred"
        return False, error_message


class NovuService(NovuBaseApiClient):
    """A service class for interacting with Novu services."""

    def __init__(self) -> None:
        """Initialize the NovuService with the base URL for Novu API."""
        self.base_url = app_settings.novu_api_base_url

    @staticmethod
    def _handle_exception(func: Callable[..., Any]) -> Callable[..., Any]:
        """Handle exceptions for both synchronous and asynchronous functions.

        This decorator wraps a function to handle exceptions, converting them into a
        custom `NovuApiClientException` with a specific message. It distinguishes between
        asynchronous and synchronous functions, applying appropriate handling for each.

        Args:
        func (Callable[..., Any]): The function to be wrapped by the decorator.

        Returns:
        Callable[..., Any]: The wrapped function with added exception handling.

        Raises:
        NovuApiClientException: If a `ClientConnectionError` or any other exception occurs.
        """
        if asyncio.iscoroutinefunction(func):

            async def async_wrapper(self, *args: Any, **kwargs: Any) -> Any:
                try:
                    return await func(self, *args, **kwargs)
                except client_exceptions.ClientConnectionError:
                    raise NovuApiClientException("Failed to connect to server") from None
                except Exception as err:
                    logger.exception(err)
                    raise NovuApiClientException("Unexpected error occurred") from None

            return async_wrapper
        else:

            def sync_wrapper(self, *args: Any, **kwargs: Any) -> Any:
                try:
                    return func(self, *args, **kwargs)
                except client_exceptions.ClientConnectionError:
                    raise NovuApiClientException("Failed to connect to server") from None
                except Exception as err:
                    logger.exception(err)
                    raise NovuApiClientException("Unexpected error occurred") from None

            return sync_wrapper

    @_handle_exception
    async def create_user(self, first_name: str, last_name: str, email: str, password: str) -> Optional[str]:
        """Create a new user in the Novu service.

        Args:
            first_name (str): The first name of the user.
            last_name (str): The last name of the user.
            email (str): The email address of the user.
            password (str): The password for the user.

        Returns:
            Optional[str]: The session token of the created user if successful, or None if an error occurs.

        Raises:
            NovuApiClientException: If the user creation fails.
        """
        url = f"{self.base_url}/v1/auth/register"
        payload = {
            "firstName": first_name,
            "lastName": last_name,
            "email": email,
            "password": password,
        }
        async with aiohttp.ClientSession() as session, session.post(url, json=payload) as response:
            is_success, response = await self._handle_response(response)
            if is_success:
                return response["data"]["token"]
            else:
                raise NovuApiClientException(f"Failed to create user: {response}")

    @_handle_exception
    async def login_user(self, email: str, password: str) -> Optional[str]:
        """Log in a user and retrieve the authentication token.

        Args:
            email (str): The email address of the user.
            password (str): The password of the user.

        Returns:
            Optional[str]: The authentication token if login is successful, or None if an error occurs.

        Raises:
            NovuApiClientException: If the login attempt fails.
        """
        url = f"{self.base_url}/v1/auth/login"
        payload = {"email": email, "password": password}
        async with aiohttp.ClientSession() as session, session.post(url, json=payload) as response:
            is_success, response = await self._handle_response(response)
            if is_success:
                return response["data"]["token"]
            else:
                raise NovuApiClientException(f"Failed to login user: {response}")

    @_handle_exception
    async def list_organizations(self, token: str) -> Optional[List[Dict]]:
        """Retrieve a list of organizations associated with the authenticated user.

        Args:
            token (str): The authentication token for the API request.

        Returns:
            Optional[List[Dict]]: A list of organizations if the request is successful, or None if an error occurs.

        Raises:
            NovuApiClientException: If the request to retrieve organizations fails.
        """
        url = f"{self.base_url}/v1/organizations"
        headers = {"Authorization": f"Bearer {token}"}
        async with aiohttp.ClientSession() as session, session.get(url, headers=headers) as response:
            is_success, response = await self._handle_response(response)
            if is_success:
                return response["data"]
            else:
                raise NovuApiClientException(f"Failed to list organizations: {response}")

    @_handle_exception
    async def create_organization(
        self,
        token: str,
        name: str,
        job_title: str,
        domain: str,
    ) -> Optional[Dict]:
        """Create a new organization in Novu.

        Args:
            token (str): The authentication token for the API request.
            name (str): The name of the new organization.
            job_title (str): The job title of the user creating the organization.
            domain (str): The domain of the organization.

        Returns:
            Optional[Dict]: The response data containing organization details if the request is successful, or None if an error occurs.

        Raises:
            NovuApiClientException: If the request to create the organization fails.
        """
        url = f"{self.base_url}/v1/organizations"
        headers = {"Authorization": f"Bearer {token}"}
        payload = {
            "jobTitle": job_title,
            "domain": domain,
            "productUseCases": {
                "in_app": True,
                "multi_channel": True,
                "digest": True,
                "delay": True,
                "translation": True,
            },
            "name": name,
        }
        async with aiohttp.ClientSession() as session, session.post(url, headers=headers, json=payload) as response:
            is_success, response = await self._handle_response(response)
            if is_success:
                return response
            else:
                raise NovuApiClientException(f"Failed to create organization: {response}")

    @_handle_exception
    async def get_environments(self, token: str) -> Optional[List]:
        """Retrieve environment details from Novu.

        Args:
            token (str): The authentication token for the API request.

        Returns:
            Optional[List]: A dictionary containing environment details, such as API keys, app identifiers, and environment IDs,
            if the request is successful. Returns None if an error occurs.

        Raises:
            NovuApiClientException: If the request to retrieve environments fails.
        """
        url = f"{self.base_url}/v1/environments"
        headers = {"Authorization": f"Bearer {token}"}
        async with aiohttp.ClientSession() as session, session.get(url, headers=headers) as response:
            is_success, response = await self._handle_response(response)
            if is_success:
                environment_details = {}
                for environment in response["data"]:
                    environment_details[environment["name"]] = {
                        "api_keys": [api_key["key"] for api_key in environment.get("apiKeys", [])],
                        "app_identifier": environment.get("identifier", None),
                        "environment_id": environment.get("_id", None),
                    }
                return environment_details
            else:
                raise NovuApiClientException(f"Failed to get environments: {response}")

    @_handle_exception
    async def get_prod_session_token(self, prod_env_id: str, dev_token: str) -> Optional[str]:
        """Switch to a production environment and retrieve a session token.

        Args:
            prod_env_id (str): The ID of the production environment.
            dev_token (str): The development environment token.

        Returns:
            Optional[str]: The session token for the production environment if the request is successful.
            Returns None if an error occurs.

        Raises:
            NovuApiClientException: If the request to switch environments fails.
        """
        url = f"{self.base_url}/v1/auth/environments/{prod_env_id}/switch"
        headers = {"Authorization": f"Bearer {dev_token}"}
        async with aiohttp.ClientSession() as session, session.post(url, headers=headers, json={}) as response:
            is_success, response = await self._handle_response(response)
            if is_success:
                return response["data"]["token"]
            else:
                raise NovuApiClientException(f"Failed to switch environments: {response}")

    @_handle_exception
    async def health_check(self) -> Optional[str]:
        """Perform a health check on the API endpoint.

        Returns:
            Optional[str]: The raw response content from the health check endpoint if the request is successful.
            Returns None if an error occurs.

        Raises:
            NovuApiClientException: If the health check request fails.
        """
        url = f"{self.base_url}/api"
        async with aiohttp.ClientSession() as session, session.get(url) as response:
            is_success, response = await self._handle_response(response, json=False)
            if is_success:
                return response
            else:
                raise NovuApiClientException(f"Failed to perform health check: {response}")
