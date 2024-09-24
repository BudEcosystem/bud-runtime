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
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple, Union

import aiohttp
from aiohttp import client_exceptions
from novu.api import (
    ChangeApi,
    EventApi,
    IntegrationApi,
    LayoutApi,
    NotificationGroupApi,
    NotificationTemplateApi,
    SubscriberApi,
)
from novu.dto.change import ChangeDto
from novu.dto.event import EventDto
from novu.dto.integration import IntegrationDto
from novu.dto.layout import LayoutDto
from novu.dto.notification_group import NotificationGroupDto
from novu.dto.notification_template import (
    NotificationTemplateDto,
    NotificationTemplateFormDto,
)
from novu.dto.subscriber import BulkResultSubscriberDto, SubscriberDto
from requests.exceptions import HTTPError

from notify.commons import logging
from notify.commons.config import app_settings
from notify.commons.exceptions import NovuApiClientException

from .novu_schemas import NovuLayout


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

    @_handle_exception
    async def get_changes(self, api_key: Optional[str] = None, environment: str = "dev") -> Iterable[ChangeDto]:
        """Fetch the list of changes from the Novu API.

        This method retrieves changes from the Novu API for the specified environment.

        Args:
            api_key (Optional[str]): An optional API key to authenticate the request. If not provided,
                it will be fetched using the `_resolve_api_key` method.
            environment (str): The environment to fetch changes for. Default is "dev".

        Returns:
            Iterable[ChangeDto]: A list of changes from the API.

        Raises:
            NovuApiClientException: If an error occurs while fetching changes from the API.
        """
        novu_api_key = await self._resolve_api_key(api_key=api_key, environment=environment)

        try:
            # Fetch the list of changes using the Novu API
            response = ChangeApi(self.base_url, api_key=novu_api_key).list()
            return response.data
        except HTTPError as err:
            error_message = err.response.json().get("message", "Unknown error occurred")
            raise NovuApiClientException(f"Failed to get changes: {error_message}") from None

    @_handle_exception
    async def apply_bulk_changes(
        self,
        change_ids: List[str],
        api_key: Optional[str] = None,
        environment: str = "dev",
    ) -> Iterable[ChangeDto]:
        """Apply a list of changes in bulk using the Novu API.

        Args:
        change_ids (List[str]): A list of change IDs to apply.
        api_key (Optional[str]): The API key to authenticate with Novu. Defaults to `None`.
        env (str): The environment in which to apply the changes (e.g., 'dev' or 'prod'). Defaults to 'dev'.

        Returns:
        Iterable[ChangeDto]: A collection of applied changes.

        Raises:
        NovuApiClientException: If an error occurs during the change application.
        """
        novu_api_key = await self._resolve_api_key(api_key=api_key, environment=environment)
        try:
            response = ChangeApi(self.base_url, api_key=novu_api_key).bulk_apply(change_ids)
            return response
        except HTTPError as err:
            error_message = err.response.json().get("message", "Unknown error occurred")
            raise NovuApiClientException(f"Failed to apply changes: {error_message}") from None

    @_handle_exception
    async def fetch_and_apply_changes(self, api_key: Optional[str] = None, environment: str = "dev") -> None:
        """Fetch and apply changes from the Novu API.

        This function first retrieves all changes using the `get_changes` method,
        collects their IDs, and then applies them using the `apply_changes` method.

        Args:
        api_key (Optional[str]): The API key to authenticate with Novu. Defaults to `None`.
        env (str): The environment from which to fetch and apply changes (e.g., 'dev' or 'prod'). Defaults to 'dev'.

        Returns:
        None

        Raises:
        NovuApiClientException: If an error occurs during the process of fetching or applying changes.
        """
        all_changes = await self.get_changes(api_key, environment)
        change_ids = [change._id for change in all_changes]
        logger.debug(f"Found {len(change_ids)} changes to apply")

        if change_ids:
            applied_changes = await self.apply_bulk_changes(change_ids, api_key, environment)
            for change in applied_changes:
                logger.debug(f"Applied change: {change._id}")

    async def _resolve_api_key(self, api_key: Optional[str] = None, environment: str = "dev") -> Optional[str]:
        """Resolve the API key based on the input or environment.

        This method returns the provided API key if given, otherwise it resolves
        the key based on the specified environment ('dev' or 'prod').

        Args:
        api_key (Optional[str]): A manually provided API key. Defaults to `None`.
        environment (str): The environment from which to resolve the API key ('dev' or 'prod'). Defaults to 'dev'.

        Returns:
        Optional[str]: The resolved API key, or `None` if no API key is available for the environment.

        Raises:
        None
        """
        if api_key:
            return api_key

        return (
            app_settings.novu_dev_api_key
            if environment == "dev"
            else app_settings.novu_prod_api_key
            if environment == "prod"
            else None
        )

    @_handle_exception
    async def get_workflow_groups(
        self, api_key: Optional[str] = None, environment: str = "dev"
    ) -> Iterable[NotificationGroupDto]:
        """Fetch the list of workflow groups from the Novu API.

        Args:
        api_key (Optional[str]): The API key to use for authentication. Defaults to `None`.
        environment (str): The environment to use for fetching the API key, either 'dev' or 'prod'. Defaults to 'dev'.

        Returns:
        Iterable[NotificationGroupDto]: A list of notification groups.

        Raises:
        NovuApiClientException: If the API request fails.
        """
        novu_api_key = await self._resolve_api_key(api_key=api_key, environment=environment)

        try:
            # Fetch the list of workflow groups using the Novu API
            response = NotificationGroupApi(self.base_url, api_key=novu_api_key).list()
            return response.data
        except HTTPError as err:
            error_message = err.response.json().get("message", "Unknown error occurred")
            raise NovuApiClientException(f"Failed to get workflow groups: {error_message}") from None

    @_handle_exception
    async def get_active_integrations(
        self, api_key: Optional[str] = None, environment: str = "dev"
    ) -> Iterable[IntegrationDto]:
        """Fetch the list of active integrations from the Novu API.

        Args:
        api_key (Optional[str]): The API key to use for authentication. If not provided, it resolves based on the environment.
        environment (str): The environment to fetch the API key from ('dev' or 'prod'). Defaults to 'dev'.

        Returns:
        Iterable[IntegrationDto]: A list of active integrations.

        Raises:
        NovuApiClientException: If the API request fails.
        """
        novu_api_key = await self._resolve_api_key(api_key=api_key, environment=environment)

        try:
            # Fetch the list of active integrations using the Novu API
            response = IntegrationApi(self.base_url, api_key=novu_api_key).list(only_active=True)
            return response
        except HTTPError as err:
            error_message = err.response.json().get("message", "Unknown error occurred")
            raise NovuApiClientException(f"Failed to get active integrations: {error_message}") from None

    @_handle_exception
    async def create_integration(
        self,
        integration_data: IntegrationDto,
        check: bool = True,
        api_key: Optional[str] = None,
        environment: str = "dev",
    ) -> IntegrationDto:
        """Create a new integration in the Novu system.

        Args:
        integration_data (IntegrationDto): The integration data to be created, containing provider ID, channel, active status, and credentials.
        check (bool): Whether to check if the integration is already active. Defaults to True.
        api_key (Optional[str]): The API key to use for authentication. If not provided, resolves based on the environment.
        environment (str): The environment to fetch the API key from ('dev' or 'prod'). Defaults to 'dev'.

        Returns:
        IntegrationDto: The created integration object.

        Raises:
        NovuApiClientException: If the API request to create the integration fails.
        """
        novu_api_key = await self._resolve_api_key(api_key=api_key, environment=environment)

        try:
            # Create the integration using the Novu API
            response = IntegrationApi(self.base_url, api_key=novu_api_key).create(
                integration=integration_data, check=check
            )
            return response
        except HTTPError as err:
            error_message = err.response.json().get("message", "Unknown error occurred")
            raise NovuApiClientException(f"Failed to create integration: {error_message}") from None

    @_handle_exception
    async def get_workflows(
        self, api_key: Optional[str] = None, environment: str = "dev"
    ) -> Iterable[NotificationTemplateDto]:
        """Fetch the list of workflows (notification templates) from the Novu API.

        Args:
        api_key (Optional[str]): The API key to use for authentication. If not provided, resolves based on the environment.
        environment (str): The environment to fetch the API key from ('dev' or 'prod'). Defaults to 'dev'.

        Returns:
        Iterable[NotificationTemplateDto]: A list of notification templates (workflows) retrieved from the Novu API.

        Raises:
        NovuApiClientException: If the API request to fetch workflows fails.
        """
        novu_api_key = await self._resolve_api_key(api_key=api_key, environment=environment)

        try:
            # Fetch the list of workflows using the Novu API
            response = NotificationTemplateApi(self.base_url, api_key=novu_api_key).list()
            return response.data
        except HTTPError as err:
            error_message = err.response.json().get("message", "Unknown error occurred")
            raise NovuApiClientException(f"Failed to get workflows: {error_message}") from None

    @_handle_exception
    async def create_workflow(
        self,
        workflow_data: NotificationTemplateFormDto,
        api_key: Optional[str] = None,
        environment: str = "dev",
    ) -> NotificationTemplateDto:
        """Create a new workflow (notification template) in the Novu system.

        Args:
        workflow_data (NotificationTemplateFormDto): The metadata for the workflow including `name`, `description`, and `active` status.
        api_key (Optional[str]): The API key to use for authentication. If not provided, resolves based on the environment.
        environment (str): The environment to fetch the API key from ('dev' or 'prod'). Defaults to 'dev'.

        Returns:
        NotificationTemplateDto: The created workflow as returned by the Novu API.

        Raises:
        NovuApiClientException: If the API request to create the workflow fails.
        """
        novu_api_key = await self._resolve_api_key(api_key=api_key, environment=environment)
        try:
            # Fetch the list of workflows using the Novu API
            response = NotificationTemplateApi(self.base_url, api_key=novu_api_key).create(
                notification_template=workflow_data
            )
            return response
        except HTTPError as err:
            error_message = err.response.json().get("message", "Unknown error occurred")
            raise NovuApiClientException(f"Failed to create workflow: {error_message}") from None

    @_handle_exception
    async def create_layout(
        self, layout_data: NovuLayout, api_key: Optional[str] = None, environment: str = "dev"
    ) -> Dict[str, Any]:
        """Create a new layout using the Novu API.

        Args:
        layout_data (NovuLayout): A pydantic schema containing layout information such as name, description, content file name, is_default, identifier, and variables.
        api_key (Optional[str]): The API key for the Novu environment. If not provided, it will be resolved based on the environment.
        environment (str): The environment in which to operate (e.g., 'dev' or 'prod'). Defaults to 'dev'.

        Returns:
        Dict[str, Any]: A dictionary containing the newly created layout's data.

        Raises:
        NovuApiClientException: If the layout creation fails or there is an issue with reading the content file.
        """
        novu_api_key = await self._resolve_api_key(api_key=api_key, environment=environment)

        url = f"{self.base_url}/v1/layouts"
        headers = {"Authorization": f"ApiKey {novu_api_key}"}
        payload = layout_data.model_dump()

        async with aiohttp.ClientSession() as session, session.post(url, headers=headers, json=payload) as response:
            is_success, response = await self._handle_response(response)
            if is_success:
                return response["data"]
            else:
                raise NovuApiClientException(f"Failed to create layout: {response}")

    @_handle_exception
    async def get_layouts(
        self,
        page: int = 0,
        limit: int = 100,
        api_key: Optional[str] = None,
        environment: str = "dev",
    ) -> Iterable[LayoutDto]:
        """Fetch a list of layouts from the Novu API.

        Args:
        page (int): The page number of results to retrieve. Defaults to 0.
        limit (int): The maximum number of layouts to retrieve per request. Defaults to 100.
        api_key (Optional[str]): The API key for the Novu environment. If not provided, it will be resolved based on the environment.
        environment (str): The environment in which to operate (e.g., 'dev' or 'prod'). Defaults to 'dev'.

        Returns:
        List[LayoutDto]: A list of LayoutDto objects representing the layouts.

        Raises:
        NovuApiClientException: If there is an error while fetching layouts from the Novu API.
        """
        novu_api_key = await self._resolve_api_key(api_key=api_key, environment=environment)

        try:
            # Fetch the list of layouts using the Novu API
            response = LayoutApi(self.base_url, api_key=novu_api_key).list(page=page, limit=limit)
            return response.data
        except HTTPError as err:
            error_message = err.response.json().get("message", "Unknown error occurred")
            raise NovuApiClientException(f"Failed to get layouts: {error_message}") from None

    @_handle_exception
    async def set_integration_as_primary(
        self, integration_id: str, api_key: Optional[str] = None, environment: str = "dev"
    ) -> Dict[str, Any]:
        """Set the specified integration as the primary integration for the given environment.

        Args:
            integration_id (str): The ID of the integration to set as primary.
            api_key (Optional[str], optional): The API key to authenticate with Novu. Defaults to None,
                                               in which case the key will be resolved based on the environment.
            environment (str, optional): The environment in which the integration is being set as primary. Defaults to "dev".

        Returns:
            Dict[str, Any]: The data of the integration marked as primary.

        Raises:
            NovuApiClientException: If the request to mark the integration as primary fails.
        """
        novu_api_key = await self._resolve_api_key(api_key=api_key, environment=environment)

        url = f"{self.base_url}/v1/integrations/{integration_id}/set-primary"
        headers = {"Authorization": f"ApiKey {novu_api_key}"}

        async with aiohttp.ClientSession() as session, session.post(url, headers=headers) as response:
            is_success, response = await self._handle_response(response)
            if is_success:
                return response["data"]
            else:
                raise NovuApiClientException(f"Failed to mark integration as primary: {response}")

    @_handle_exception
    async def get_integrations_curl(self, api_key: Optional[str] = None, environment: str = "dev") -> Dict[str, Any]:
        """Fetch the list of integrations from Novu for a specified environment.

        Args:
            api_key (Optional[str], optional): The API key to authenticate with Novu. Defaults to None,
                                               in which case the key will be resolved based on the environment.
            environment (str, optional): The environment for which the integrations are being fetched. Defaults to "dev".

        Returns:
            Dict[str, Any]: A dictionary containing the list of integrations.

        Raises:
            NovuApiClientException: If the request to list integrations fails.
        """
        novu_api_key = await self._resolve_api_key(api_key=api_key, environment=environment)

        url = f"{self.base_url}/v1/integrations/"
        headers = {"Authorization": f"ApiKey {novu_api_key}"}

        async with aiohttp.ClientSession() as session, session.get(url, headers=headers) as response:
            is_success, response = await self._handle_response(response)
            if is_success:
                return response["data"]
            else:
                raise NovuApiClientException(f"Failed to list integrations: {response}")

    @_handle_exception
    async def update_integration(
        self,
        integration_data: IntegrationDto,
        check: bool = True,
        api_key: Optional[str] = None,
        environment: str = "dev",
    ) -> IntegrationDto:
        """Update an existing integration in Novu with the provided integration data.

        Args:
            integration_data (IntegrationDto): The integration data to be updated.
            check (bool, optional): Whether to perform a pre-check before updating the integration. Defaults to True.
            api_key (Optional[str], optional): API key for authentication. Defaults to None, in which case it's resolved based on the environment.
            environment (str, optional): The environment in which the integration exists (e.g., "dev", "prod"). Defaults to "dev".

        Returns:
            IntegrationDto: The updated integration data.

        Raises:
            NovuApiClientException: If the integration update fails due to an HTTP error.
        """
        novu_api_key = await self._resolve_api_key(api_key=api_key, environment=environment)

        try:
            # Update the integration using the Novu API
            response = IntegrationApi(self.base_url, api_key=novu_api_key).update(
                integration=integration_data, check=check
            )
            return response
        except HTTPError as err:
            error_message = err.response.json().get("message", "Unknown error occurred")
            raise NovuApiClientException(f"Failed to update integration: {error_message}") from None

    @_handle_exception
    async def delete_integration(
        self,
        integration_id: str,
        api_key: Optional[str] = None,
        environment: str = "dev",
    ) -> None:
        """Delete an integration from Novu based on the given integration ID.

        Args:
            integration_id (str): The ID of the integration to be deleted.
            api_key (Optional[str], optional): API key for authentication. Defaults to None, in which case it's resolved based on the environment.
            environment (str, optional): The environment in which the integration exists (e.g., "dev", "prod"). Defaults to "dev".

        Returns:
            IntegrationDto: The deleted integration data if successful.

        Raises:
            NovuApiClientException: If the integration deletion fails due to an HTTP error.
        """
        novu_api_key = await self._resolve_api_key(api_key=api_key, environment=environment)

        try:
            # Delete the integration using the Novu API
            _ = IntegrationApi(self.base_url, api_key=novu_api_key).delete(integration_id=integration_id)
            return
        except HTTPError as err:
            error_message = err.response.json().get("message", "Unknown error occurred")
            raise NovuApiClientException(f"Failed to delete integration: {error_message}") from None

    @_handle_exception
    async def create_subscriber(
        self,
        subscriber_data: SubscriberDto,
        api_key: Optional[str] = None,
        environment: str = "dev",
    ) -> SubscriberDto:
        """Create a new subscriber within the Novu system.

        Args:
            subscriber_data (SubscriberDto): The data for the subscriber to be created.
            api_key (Optional[str]): The API key for Novu. If not provided, it will be resolved based on the environment.
            environment (str): The environment to use for the API call. Defaults to "dev".

        Raises:
            NovuApiClientException: If the creation of the subscriber fails due to an API error.

        Returns:
            SubscriberDto: The created subscriber's data.
        """
        novu_api_key = await self._resolve_api_key(api_key=api_key, environment=environment)
        try:
            response = SubscriberApi(self.base_url, api_key=novu_api_key).create(subscriber=subscriber_data)
            return response
        except HTTPError as err:
            error_message = err.response.json().get("message", "Unknown error occurred")
            raise NovuApiClientException(f"Failed to create subscriber: {error_message}") from None

    @_handle_exception
    async def bulk_create_subscribers(
        self,
        subscriber_data: Iterable[SubscriberDto],
        api_key: Optional[str] = None,
        environment: str = "dev",
    ) -> BulkResultSubscriberDto:
        """Create multiple subscribers in bulk within the Novu system.

        Args:
            subscriber_data (Iterable[SubscriberDto]): An iterable of subscriber data to be created.
            api_key (Optional[str]): The API key for Novu. If not provided, it will be resolved based on the environment.
            environment (str): The environment to use for the API call. Defaults to "dev".

        Raises:
            NovuApiClientException: If the bulk creation of subscribers fails due to an API error.

        Returns:
            BulkResultSubscriberDto: The result of the bulk creation process.
        """
        # The bulk API is limited to 500 subscribers per request.
        if len(subscriber_data) > 500:
            raise NovuApiClientException("Cannot create more than 500 subscribers at once")

        novu_api_key = await self._resolve_api_key(api_key=api_key, environment=environment)
        try:
            response = SubscriberApi(self.base_url, api_key=novu_api_key).bulk_create(subscribers=subscriber_data)
            return response
        except HTTPError as err:
            error_message = err.response.json().get("message", "Unknown error occurred")
            raise NovuApiClientException(f"Failed to create subscribers: {error_message}") from None

    @_handle_exception
    async def get_all_subscribers(
        self,
        page: int = 0,
        limit: int = 10,
        api_key: Optional[str] = None,
        environment: str = "dev",
    ) -> List:
        """Retrieve a paginated list of all subscribers from the Novu system.

        Args:
            page (int): The page number to retrieve. Defaults to 0.
            limit (int): The maximum number of subscribers to return per page. Defaults to 10.
            api_key (Optional[str]): The API key for Novu. If not provided, it will be resolved based on the environment.
            environment (str): The environment to use for the API call. Defaults to "dev".

        Raises:
            NovuApiClientException: If listing subscribers fails due to an API error.

        Returns:
            List: A paginated list of subscribers.
        """
        novu_api_key = await self._resolve_api_key(api_key=api_key, environment=environment)

        url = f"{self.base_url}/v1/subscribers?page={page}&limit={limit}"
        headers = {"Authorization": f"ApiKey {novu_api_key}"}

        async with aiohttp.ClientSession() as session, session.get(url, headers=headers) as response:
            is_success, response = await self._handle_response(response)
            if is_success:
                return response["data"]
            else:
                raise NovuApiClientException(f"Failed to list subscribers: {response}")

    @_handle_exception
    async def retrieve_subscriber(
        self,
        subscriber_id: str,
        api_key: Optional[str] = None,
        environment: str = "dev",
    ) -> SubscriberDto:
        """Retrieve a subscriber's details from the Novu system.

        Args:
            subscriber_id (str): The ID of the subscriber to retrieve.
            api_key (Optional[str]): The API key for Novu. If not provided, it will be resolved based on the environment.
            environment (str): The environment to use for the API call. Defaults to "dev".

        Raises:
            NovuApiClientException: If the subscriber retrieval fails due to an API error.

        Returns:
            SubscriberDto: The retrieved subscriber data from the Novu API.
        """
        novu_api_key = await self._resolve_api_key(api_key=api_key, environment=environment)
        try:
            response = SubscriberApi(self.base_url, api_key=novu_api_key).get(subscriber_id=subscriber_id)
            return response
        except HTTPError as err:
            error_message = err.response.json().get("message", "Unknown error occurred")
            raise NovuApiClientException(f"Failed to retrieve subscriber: {error_message}") from None

    @_handle_exception
    async def update_subscriber(
        self,
        subscriber_data: SubscriberDto,
        api_key: Optional[str] = None,
        environment: str = "dev",
    ) -> SubscriberDto:
        """Update a subscriber's information in the Novu system.

        Args:
            subscriber_data (SubscriberDto): The data of the subscriber to be updated.
            api_key (Optional[str]): The API key for Novu. If not provided, it will be resolved based on the environment.
            environment (str): The environment to use for the API call. Defaults to "dev".

        Raises:
            NovuApiClientException: If the subscriber update fails due to an API error.

        Returns:
            SubscriberDto: The updated subscriber data returned by the Novu API.
        """
        novu_api_key = await self._resolve_api_key(api_key=api_key, environment=environment)
        try:
            response = SubscriberApi(self.base_url, api_key=novu_api_key).put(subscriber=subscriber_data)
            return response
        except HTTPError as err:
            error_message = err.response.json().get("message", "Unknown error occurred")
            raise NovuApiClientException(f"Failed to update subscriber: {error_message}") from None

    @_handle_exception
    async def delete_subscriber(
        self,
        subscriber_id: str,
        api_key: Optional[str] = None,
        environment: str = "dev",
    ) -> None:
        """Delete a subscriber from the Novu system.

        Args:
            subscriber_id (str): The ID of the subscriber to be deleted.
            api_key (Optional[str]): The API key for Novu. If not provided, it will be resolved based on the environment.
            environment (str): The environment to use for the API call. Defaults to "dev".

        Raises:
            NovuApiClientException: If the subscriber deletion fails due to an API error.

        Returns:
            None: This method does not return any value.
        """
        novu_api_key = await self._resolve_api_key(api_key=api_key, environment=environment)
        try:
            _ = SubscriberApi(self.base_url, api_key=novu_api_key).delete(subscriber_id=subscriber_id)
            return
        except HTTPError as err:
            error_message = err.response.json().get("message", "Unknown error occurred")
            raise NovuApiClientException(f"Failed to delete subscriber: {error_message}") from None

    @_handle_exception
    async def trigger_event(
        self,
        name: str,
        recipients: Union[str, List[str]],
        payload: dict = None,
        api_key: Optional[str] = None,
        environment: str = "dev",
    ) -> EventDto:
        """Triggers a notification event in Novu based on the provided notification data.

        This method sends a notification event to Novu using the specified notification name,
        recipients, and payload.

        Args:
            notification_data (NotificationRequest): The request object containing the notification
                name, recipients, and payload data.

        Returns:
            EventDto: An object containing details about the triggered event, including its status.

        Raises:
            NovuApiClientException: If there is an issue with triggering the event via Novu.
        """
        novu_api_key = await self._resolve_api_key(api_key=api_key, environment=environment)

        # Set the payload to an empty dictionary if it's None
        if payload is None:
            payload = {}

        try:
            event_data = EventApi(self.base_url, api_key=novu_api_key).trigger(
                name=name, recipients=recipients, payload=payload
            )
            return event_data
        except HTTPError as err:
            error_message = err.response.json().get("message", "Unknown error occurred")
            raise NovuApiClientException(f"Failed to trigger event: {error_message}") from None
