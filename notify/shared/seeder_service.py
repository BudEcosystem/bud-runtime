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

import os

from novu.dto.integration import IntegrationDto
from novu.dto.notification_template import (
    NotificationStepDto,
    NotificationTemplateFormDto,
)

from notify.commons import logging
from notify.commons.config import app_settings, secrets_settings
from notify.commons.exceptions import NovuApiClientException, NovuSeederException
from notify.commons.helpers import read_file_content, read_json_file
from notify.shared.novu_schemas import NovuLayout

from .novu_service import NovuService


logger = logging.get_logger(__name__)

# Default path of seeding data sources
INITIAL_SEEDER_PATH = os.path.join(app_settings.seeder_path, "initial_data.json")
WORKFLOW_SEEDER_PATH = os.path.join(app_settings.seeder_path, "workflows.json")
INTEGRATION_SEEDER_PATH = os.path.join(app_settings.seeder_path, "integrations.json")
HTML_CONTENT_PATH = os.path.join(app_settings.seeder_path, "html")


class NovuInitialSeeder(NovuService):
    """Class to handle initial seeding of data for the application.

    This class performs a series of steps to ensure that necessary data (user, organization, environments)
    is created or updated during the application's startup process.
    """

    def __init__(self) -> None:
        """Initialize the InitialSeeder instance with the provided data."""
        super().__init__()
        self.data = read_json_file(INITIAL_SEEDER_PATH)
        self.dev_session_token = None
        self.prod_session_token = None

    async def execute(self) -> None:
        """Execute the initial seeding process.

        Validates data, ensures user and organization are created or retrieved, logs in the user, and applies
        environment details.

        Raises:
            NovuSeederException: If any step of the seeding process fails.
        """
        logger.info("Initial seeding started")

        await self._validate_data()
        await self._ensure_user()
        await self._ensure_organization()
        await self._login_user()  # Re-login required to get environment details
        await self._ensure_apply_envs()
        await self._validate_modify_layout_content()
        await self._ensure_layouts()
        await self._apply_changes_to_production()

        logger.info("Initial seeding completed")

    async def _login_user(self) -> None:
        """Log in the user and store the session token.

        Attempts to log in with the configured email and password. On success, sets the
        session token. Raises an exception if the login fails.

        Raises:
        NovuSeederException: If the login fails due to an API client exception.
        """
        logger.debug("Logging in user")
        try:
            # Attempt to log in and obtain the session token
            session_token = await self.login_user(
                secrets_settings.novu_user_email, secrets_settings.novu_user_password
            )
            logger.debug("User logged in successfully")
            self.dev_session_token = session_token
        except NovuApiClientException as err:
            logger.error(err.message)
            raise NovuSeederException("User login failed") from None

    async def _ensure_user(self) -> None:
        """Ensure the user exists by creating or logging in.

        Attempts to create a user with the provided details. If the user already exists
        and creation fails, it will try to log in with the existing user credentials.
        Updates the session token on successful login or creation.

        Raises:
        NovuSeederException: If user creation and login fail.
        """
        logger.debug("Ensuring user exists or logging in")
        first_name = self.data["user"]["first_name"]
        last_name = self.data["user"]["last_name"]
        try:
            # Attempt to create the user
            session_token = await self.create_user(
                first_name,
                last_name,
                secrets_settings.novu_user_email,
                secrets_settings.novu_user_password,
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
        NovuSeederException: If there is an error during the organization
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
            raise NovuSeederException("Organization seeding failed") from None

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
            secrets_settings.novu_dev_api_key = dev_env_details["Development"]["api_keys"][0]
            secrets_settings.novu_prod_api_key = prod_env_details["Production"]["api_keys"][0]

            secrets_settings.novu_dev_env_id = dev_env_details["Development"]["environment_id"]
            secrets_settings.novu_prod_env_id = prod_env_details["Production"]["environment_id"]

            secrets_settings.novu_dev_app_id = dev_env_details["Development"]["app_identifier"]
            secrets_settings.novu_prod_app_id = prod_env_details["Production"]["app_identifier"]

            # Export it to the system environment
            os.environ["NOVU_PROD_APP_ID"] = prod_env_details["Production"]["app_identifier"]

            logger.debug("Environment details applied successfully")
        except NovuApiClientException as err:
            logger.error(f"Error during environment retrieval or application settings update: {err.message}")
            raise NovuSeederException("Unable to retrieve environment details") from None

    async def _validate_data(self) -> None:
        """Validate the seeder data to ensure it is properly defined and in the correct format.

        Raises:
        NovuSeederException: If the seeder data is not defined or not a dictionary.
        """
        logger.debug("Validating seeder data")
        if self.data is None:
            raise NovuSeederException("Seeder data is not defined")
        elif not isinstance(self.data, dict):
            raise NovuSeederException(f"Seeder data must be a dictionary, got {type(self.data).__name__}")

    async def _apply_changes_to_production(self) -> None:
        """Apply changes to the production environment.

        Fetches and applies changes in the production environment by using
        the development API key. If any errors occur during the process,
        they are caught and handled gracefully.

        Raises:
        NovuSeederException: If the changes cannot be applied.
        """
        # To apply changes in production environment, use dev api key
        logger.debug("Fetching and applying changes to production environment")
        try:
            await self.fetch_and_apply_changes()
        except NovuApiClientException as err:
            logger.error(err.message)
            raise NovuSeederException("Unable to apply changes to production") from None

    async def _ensure_layouts(self) -> None:
        """Ensure that the required layouts are present in Novu.

        This method compares the layouts fetched from the Novu API with the layouts defined in the seeder data.
        If a layout is missing in Novu, it is created via the `create_layout` method.

        Raises:
        NovuSeederException: If there is an issue fetching or creating layouts.
        """
        logger.debug("Ensuring layouts are seeded")

        # Fetch existing layouts from Novu
        try:
            existing_novu_layouts = await self.get_layouts()
            logger.debug("Fetched all layouts from novu")
        except NovuApiClientException as err:
            logger.error(err.message)
            raise NovuSeederException("Unable to get layouts") from None

        existing_layout_names = [layout.name for layout in existing_novu_layouts]
        existing_layout_name_to_id = {layout.name: layout._id for layout in existing_novu_layouts}
        seeder_layouts = self.data["layouts"]

        for seeder_layout in seeder_layouts:
            # Create layout data
            layout_data = NovuLayout(
                name=seeder_layout["name"],
                description=seeder_layout["description"],
                content=seeder_layout["content"],
                is_default=seeder_layout["is_default"],
                identifier=seeder_layout["identifier"],
                variables=seeder_layout["variables"],
            )
            # Check if the layout already exists in Novu
            if seeder_layout["name"] in existing_layout_names:
                logger.debug(f"Layout {seeder_layout['name']} already exists, updating")
                try:
                    await self.update_layout(existing_layout_name_to_id[seeder_layout["name"]], layout_data)
                except NovuApiClientException as err:
                    logger.error(err.message)
                    raise NovuSeederException(f"Unable to create layout {seeder_layout['name']}") from None
            else:
                # If not, create the layout
                logger.debug(f"Layout {seeder_layout['name']} does not exist, creating")
                try:
                    await self.create_layout(layout_data)
                except NovuApiClientException as err:
                    logger.error(err.message)
                    raise NovuSeederException(f"Unable to create layout {seeder_layout['name']}") from None

    async def _validate_modify_layout_content(self) -> None:
        """Validate and modify the layout seeder data.

        This method read specified content files and update seeder data.

        If layout content path is invalid, an exception is raised.

        Raises:
            NovuSeederException: If layout content path is invalid.
        """
        logger.debug("Validating and modifying layout content")
        # Iterate over layouts to validate and modify content
        for layout in self.data["layouts"]:
            # Read the HTML content from the specified file
            html_content = read_file_content(f"{HTML_CONTENT_PATH}/{layout['content']}")
            if not html_content:
                raise NovuSeederException(f"Failed to read HTML content from layout: {layout['content']}")

        logger.debug(f"HTML content for layout '{layout['content']}' loaded successfully.")
        # NOTE: Replace the old content with the new content
        layout["content"] = html_content

        logger.debug("Layout content data validation and modification complete.")


class NovuWorkflowSeeder(NovuService):
    """Class to handle initial seeding of workflow for the application.

    This class performs a series of steps to ensure that necessary data (workflow, steps)
    is created or updated during the application's startup process.
    """

    def __init__(self) -> None:
        """Initialize the NovuWorkflowSeeder instance with the provided data."""
        super().__init__()
        self.data = read_json_file(WORKFLOW_SEEDER_PATH)
        self.workflow_group_id = None

    async def execute(self) -> None:
        """Execute the workflow seeding process.

        Applies the workflow data to the production environment.

        Raises:
        NovuSeederException: If any step of the seeding process fails.
        """
        logger.info("Workflow seeding started")

        await self._validate_data()
        await self._get_default_workflow_group()
        await self._validate_modify_template_data()
        await self._ensure_workflows()
        await self._apply_changes_to_production()

        logger.info("Workflow seeding completed")

    async def _validate_data(self) -> None:
        """Validate the seeder data to ensure it is properly defined and in the correct format.

        Raises:
        NovuSeederException: If the seeder data is not defined or not a dictionary.
        """
        logger.debug("Validating seeder data")
        if self.data is None:
            raise NovuSeederException("Seeder data is not defined")
        elif not isinstance(self.data, list):
            raise NovuSeederException(f"Seeder data must be a list, got {type(self.data).__name__}")

    async def _validate_modify_template_data(self) -> None:
        """Validate and modify the workflow seeder data.

        This method fetches the existing layouts from Novu, validates if the
        layout IDs in the workflow steps match the existing layouts, and
        update seeder data if necessary.

        If a layout ID or content is invalid, an exception is raised.

        Raises:
            NovuSeederException: If the layout ID in the template is invalid.
        """
        # Fetch existing layouts from Novu
        try:
            existing_novu_layouts = await self.get_layouts()
            logger.debug("Fetched all layouts from novu")
        except NovuApiClientException as err:
            logger.error(err.message)
            raise NovuSeederException("Unable to get layouts") from None

        # Map layout names to layout IDs for quick lookup
        layout_details = {layout.name: layout._id for layout in existing_novu_layouts}

        # Iterate over workflows to validate and modify email templates
        for workflow in self.data:
            for step in workflow["steps"]:
                template = step["template"]
                if template["type"] == "email":
                    layout_name = template["layoutId"]
                    logger.debug(f"Validating email layout for {workflow['name']} workflow")

                    # Validate layout ID
                    if layout_name not in layout_details:
                        raise NovuSeederException(
                            f"Invalid email layout {layout_name} found for {workflow['name']} workflow"
                        )

                    # NOTE: Replace the old layout ID(name) with the new layout ID(id)
                    template["layoutId"] = layout_details[layout_name]

                    # Read the HTML content from the specified file
                    html_content = read_file_content(f"{HTML_CONTENT_PATH}/{template['content']}")
                    if not html_content:
                        raise NovuSeederException(f"Failed to read HTML content: {template['content']}")

                    logger.debug(f"HTML content for template '{template['content']}' loaded successfully.")
                    # NOTE: Replace the old content with the new content
                    template["content"] = html_content

        logger.debug("Workflow template data validation and modification complete.")

    async def _get_default_workflow_group(self) -> None:
        """Fetch and sets the default workflow group ID for the notification system.

        This method retrieves the list of workflow groups from the Novu API and sets the
        `workflow_group_id` to the ID of the first group in the list.

        Raises:
        NovuSeederException: If there is an error retrieving the workflow groups.
        """
        try:
            workflow_groups = await self.get_workflow_groups()

            if workflow_groups:
                self.workflow_group_id = workflow_groups[0]._id
                logger.debug("Found default workflow group details")
            else:
                raise NovuSeederException("No workflow groups found")

        except NovuApiClientException as err:
            logger.error(err.message)
            raise NovuSeederException("Unable to get default workflow group details") from None

    async def _ensure_workflows(self) -> None:
        """Ensure that all required workflows are present in the system.

        This method checks if the workflows defined in the seeder data are already present.
        If a workflow is not found, it is created with its corresponding steps.

        Raises:
        NovuSeederException: If there is an error fetching or creating workflows.
        """
        try:
            present_workflows = await self.get_workflows()
            logger.debug("Fetched all present workflows")
        except NovuApiClientException as err:
            logger.error(err.message)
            raise NovuSeederException("Unable to get workflows") from None

        present_workflow_names = [workflow.name for workflow in present_workflows]
        present_workflow_name_to_id = {workflow.name: workflow._id for workflow in present_workflows}

        for seeder_workflow in self.data:
            # Collect workflow steps
            seeder_workflow_steps = seeder_workflow.pop("steps")

            # Create workflow steps
            workflow_steps = []
            for seeder_workflow_step in seeder_workflow_steps:
                workflow_step = NotificationStepDto(
                    active=seeder_workflow_step["active"],
                    template=seeder_workflow_step["template"],
                )
                workflow_steps.append(workflow_step)

            # Create workflow
            workflow_template_data = NotificationTemplateFormDto(
                active=seeder_workflow["active"],
                name=seeder_workflow["name"],
                description=seeder_workflow.get("description", ""),
                steps=workflow_steps,
                notification_group_id=self.workflow_group_id,
                tags=seeder_workflow.get("tags", []),
            )
            if seeder_workflow["name"] in present_workflow_names:
                logger.debug(f"Workflow '{seeder_workflow['name']}' found, updating")
                try:
                    await self.update_workflow(
                        present_workflow_name_to_id[seeder_workflow["name"]], workflow_template_data
                    )
                except NovuApiClientException as err:
                    logger.error(err.message)
                    raise NovuSeederException("Unable to update workflow") from None
            else:
                logger.debug(f"Workflow '{seeder_workflow['name']}' not found, creating")

                try:
                    created_workflow = await self.create_workflow(workflow_template_data)
                    logger.debug(f"Workflow created successfully {created_workflow._id}")
                except NovuApiClientException as err:
                    logger.error(err.message)
                    raise NovuSeederException("Unable to create workflow") from None

    async def _apply_changes_to_production(self) -> None:
        """Apply changes to the production environment.

        Fetches and applies changes in the production environment by using
        the development API key. If any errors occur during the process,
        they are caught and handled gracefully.

        Raises:
        NovuSeederException: If the changes cannot be applied.
        """
        # To apply changes in production environment, use dev api key
        logger.debug("Fetching and applying changes to production environment")
        try:
            await self.fetch_and_apply_changes()
        except NovuApiClientException as err:
            logger.error(err.message)
            raise NovuSeederException("Unable to apply changes to production") from None


class NovuIntegrationSeeder(NovuService):
    """Class to handle initial seeding of integrations for the application.

    This class performs a series of steps to ensure that integrations are created
    during the application's startup process.
    """

    def __init__(self) -> None:
        """Initialize the NovuIntegrationSeeder instance with the provided data."""
        super().__init__()
        self.data = read_json_file(INTEGRATION_SEEDER_PATH)

    async def execute(self) -> None:
        """Execute the integration seeding process.

        Applies the integration data to the production environment.

        Raises:
        NovuSeederException: If any step of the seeding process fails.
        """
        logger.info("Integration seeding started")

        await self._validate_data()
        await self._ensure_integrations()

        logger.info("Integration seeding completed")

    async def _validate_data(self) -> None:
        """Validate the seeder data to ensure it is properly defined and in the correct format.

        Raises:
        NovuSeederException: If the seeder data is not defined or not a dictionary.
        """
        logger.debug("Validating seeder data")
        if self.data is None:
            raise NovuSeederException("Seeder data is not defined")
        elif not isinstance(self.data, list):
            raise NovuSeederException(f"Seeder data must be a list, got {type(self.data).__name__}")

    async def _ensure_integrations(self) -> None:
        """Ensure that required integrations are present.

        This method checks the active integrations by fetching them from Novu, compares
        them with the integration data provided, and creates any missing integrations
        in the production environment.

        If an integration is already present, its creation is skipped. If any error occurs
        during fetching or creation, appropriate exceptions are raised.

        Raises:
        NovuSeederException: If fetching or creating integrations fails.
        """
        # Fetch active integrations from Novu
        try:
            present_integrations = await self.get_active_integrations(environment="prod")
            logger.debug("Fetched all active integrations")
        except NovuApiClientException as err:
            logger.error(err.message)
            raise NovuSeederException("Unable to get integrations") from None

        # Create a list of present integration provider IDs for quick lookup
        present_integration_providers = [integration.provider_id for integration in present_integrations]

        # Iterate through the seeder integration data
        for seeder_integration in self.data:
            provider_id = seeder_integration["providerId"]

            # Check if the integration already exists, and skip creation if found
            if provider_id in present_integration_providers:
                logger.debug(f"Integration of '{provider_id}' found, skipping creation")
                continue

            # Create the missing integration
            logger.debug(f"Integration of '{provider_id}' not found, creating")
            try:
                integration_data = IntegrationDto(
                    provider_id=seeder_integration["providerId"],
                    channel=seeder_integration["channel"],
                    active=seeder_integration["active"],
                    _environment_id=secrets_settings.novu_prod_env_id,
                    credentials=seeder_integration["credentials"],
                )
                created_integration = await self.create_integration(integration_data, environment="prod")
                logger.debug(f"Integration {created_integration.provider_id} created successfully in production")
            except NovuApiClientException as err:
                logger.error(err.message)
                raise NovuSeederException(f"Unable to create {provider_id} integration") from None
