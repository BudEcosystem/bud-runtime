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

"""Provides a service class for seeding data."""

from notify.commons import logging
from notify.commons.config import app_settings
from notify.commons.exceptions import NovuApiClientException, NovuInitialSeederException
from notify.commons.helpers import read_json_file

from .novu_service import NovuService


logger = logging.get_logger(__name__)


class InitialSeeder(NovuService):
    """Class to handle initial seeding of data for the application.

    This class performs a series of steps to ensure that necessary data (user, organization, environments)
    is created or updated during the application's startup process.
    """

    def __init__(self) -> None:
        """Initialize the InitialSeeder instance with the provided data."""
        super().__init__()
        self.data = read_json_file(app_settings.initial_data_path)
        self.dev_session_token = None
        self.prod_session_token = None

    async def execute(self) -> None:
        """Execute the initial seeding process.

        Validates data, ensures user and organization are created or retrieved, logs in the user, and applies
        environment details.

        Raises:
            NovuInitialSeederException: If any step of the seeding process fails.
        """
        logger.debug("Initial seeding started")

        await self._validate_data()
        await self._ensure_user()
        await self._ensure_organization()
        await self._login_user()  # Re-login required to get environment details
        await self._ensure_apply_envs()

        logger.debug("Initial seeding completed")

    async def _login_user(self) -> None:
        """Log in the user and store the session token.

        Attempts to log in with the configured email and password. On success, sets the
        session token. Raises an exception if the login fails.

        Raises:
        NovuInitialSeederException: If the login fails due to an API client exception.
        """
        logger.debug("Logging in user")
        try:
            # Attempt to log in and obtain the session token
            session_token = await self.login_user(app_settings.novu_user_email, app_settings.novu_user_password)
            logger.debug("User logged in successfully")
            self.dev_session_token = session_token
        except NovuApiClientException as err:
            logger.error(err.message)
            raise NovuInitialSeederException("User login failed") from None

    async def _ensure_user(self) -> None:
        """Ensure the user exists by creating or logging in.

        Attempts to create a user with the provided details. If the user already exists
        and creation fails, it will try to log in with the existing user credentials.
        Updates the session token on successful login or creation.

        Raises:
        NovuInitialSeederException: If user creation and login fail.
        """
        logger.debug("Ensuring user exists or logging in")
        first_name = self.data["user"]["first_name"]
        last_name = self.data["user"]["last_name"]
        try:
            # Attempt to create the user
            session_token = await self.create_user(
                first_name,
                last_name,
                app_settings.novu_user_email,
                app_settings.novu_user_password,
            )
            logger.debug("User created successfully")
            self.dev_session_token = session_token
        except NovuApiClientException as err:
            logger.error(err.message)
            # Attempt to log in if creation fails
            await self._login_user()

    async def _ensure_organization(self) -> None:
        """Ensure the specified organization exists by creating it if necessary.

        Checks if the organization specified in `self.data` exists in the list of
        organizations. If the organization does not exist, it will be created.

        Raises:
        NovuInitialSeederException: If there is an error during the organization
        listing or creation process.
        """
        logger.debug("Ensuring organization exists")
        organization_name = self.data["organization"]["name"]
        job_title = self.data["organization"]["job_title"]
        domain = self.data["organization"]["domain"]
        try:
            # List all organizations and check if the required one exists
            organizations = await self.list_organizations(self.dev_session_token)
            if any(org["name"] == organization_name for org in organizations):
                logger.debug("Organization exists")
                return

            # Create organization if it doesn't exist
            await self.create_organization(
                self.dev_session_token,
                organization_name,
                job_title,
                domain,
            )
            logger.debug("Organization created successfully")
        except NovuApiClientException as err:
            logger.error(err.message)
            raise NovuInitialSeederException("Organization seeding failed") from None

    async def _ensure_apply_envs(self) -> None:
        logger.debug("Applying environment details")
        try:
            # Retrieve development environment details
            dev_env_details = await self.get_environments(self.dev_session_token)
            logger.debug("Nouv development environment details retrieved")

            # Retrieve production environment details
            self.prod_session_token = await self.get_prod_session_token(
                dev_env_details["Production"]["environment_id"],
                self.dev_session_token,
            )
            logger.debug("switched to Nouv production environment")
            prod_env_details = await self.get_environments(self.prod_session_token)
            logger.debug("Nouv production environment details retrieved")

            # Update application settings with environment details
            app_settings.novu_dev_api_key = dev_env_details["Development"]["api_keys"][0]
            app_settings.novu_prod_api_key = prod_env_details["Production"]["api_keys"][0]

            app_settings.novu_dev_env_id = dev_env_details["Development"]["environment_id"]
            app_settings.novu_prod_env_id = prod_env_details["Production"]["environment_id"]

            app_settings.novu_dev_env_id = dev_env_details["Development"]["app_identifier"]
            app_settings.novu_prod_env_id = prod_env_details["Production"]["app_identifier"]

            logger.debug("Environment details applied successfully")
        except NovuApiClientException as err:
            logger.error(f"Error during environment retrieval or application settings update: {err.message}")
            raise NovuInitialSeederException("Unable to retrieve environment details") from None

    async def _validate_data(self) -> None:
        """Validate the seeder data to ensure it is properly defined and in the correct format.

        Raises:
        NovuInitialSeederException: If the seeder data is not defined or not a dictionary.
        """
        logger.debug("Validating seeder data")
        if self.data is None:
            raise NovuInitialSeederException("Seeder data is not defined")
        elif not isinstance(self.data, dict):
            raise NovuInitialSeederException(f"Seeder data must be a dictionary, got {type(self.data).__name__}")
