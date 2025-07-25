"""Cloud Provider Seeder."""

import json
import os
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from budapp.commons import logging
from budapp.commons.config import app_settings
from budapp.commons.constants import UserStatusEnum
from budapp.commons.database import engine
from budapp.credential_ops.crud import CloudProviderDataManager
from budapp.credential_ops.models import CloudProviders
from budapp.user_ops.crud import UserDataManager
from budapp.user_ops.models import User as UserModel

from .base_seeder import BaseSeeder


logger = logging.get_logger(__name__)

CURRENT_FILE_PATH = os.path.dirname(os.path.abspath(__file__))
# seeder file path
PROVIDERS_SEEDER_FILE_PATH = os.path.join(CURRENT_FILE_PATH, "data", "cloud_providers.json")


class CloudProviderSeeder(BaseSeeder):
    """Seeder for cloud providers."""

    async def seed(self) -> None:
        """Seed Providers to the database."""
        with Session(engine) as session:
            try:
                await self._seed_cloud_providers(session)
            except Exception as e:
                logger.exception(f"Failed to seed clous providers: {e}")

    @staticmethod
    async def _seed_cloud_providers(session: Session) -> None:
        """Seed cloud providers to the database."""
        db_user = await UserDataManager(session).retrieve_by_fields(
            UserModel,
            {"email": app_settings.superuser_email, "status": UserStatusEnum.ACTIVE, "is_superuser": True},
            missing_ok=True,
        )

        if db_user:
            # load the providers from the file
            for cloud_provider in await CloudProviderSeeder._get_cloud_provider_data():
                # Check if the provider already exists
                existing_provider = await CloudProviderDataManager(session).retrieve_by_fields(
                    CloudProviders,
                    {"unique_id": cloud_provider["unique_id"]},
                    missing_ok=True,
                )

                if existing_provider:
                    # Update the provider
                    update_data = {
                        "name": cloud_provider["name"],
                        "description": cloud_provider["description"],
                        "logo_url": cloud_provider["logo_url"],
                        "schema_definition": cloud_provider["schema"],
                    }
                    await CloudProviderDataManager(session).update_by_fields(existing_provider, update_data)
                    logger.info(f"Provider {cloud_provider['unique_id']} updated successfully.")
                    continue

                # Create the provider
                cloud_provider_data = CloudProviders(
                    name=cloud_provider["name"],
                    description=cloud_provider["description"],
                    logo_url=cloud_provider["logo_url"],
                    unique_id=cloud_provider["unique_id"],
                    schema_definition=cloud_provider["schema"],
                )

                await CloudProviderDataManager(session).insert_one(cloud_provider_data)

                logger.info(f"Provider {cloud_provider['unique_id']} created successfully.")

        else:
            logger.error("Super user not found. Skipping cloud provider seeding.")

    @staticmethod
    async def _get_cloud_provider_data() -> List[Dict[str, Any]]:
        """Get cloud_provider data from the database."""
        try:
            with open(PROVIDERS_SEEDER_FILE_PATH, "r") as file:
                return json.load(file)
        except FileNotFoundError as e:
            raise FileNotFoundError(f"File not found: {PROVIDERS_SEEDER_FILE_PATH}") from e
