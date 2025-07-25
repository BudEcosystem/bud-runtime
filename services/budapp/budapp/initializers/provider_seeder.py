import json
import os
from typing import Any, Dict

from sqlalchemy.orm import Session

from budapp.commons import logging
from budapp.commons.constants import ModelSourceEnum
from budapp.commons.database import engine
from budapp.model_ops.crud import ProviderDataManager
from budapp.model_ops.models import Provider as ProviderModel

from .base_seeder import BaseSeeder


logger = logging.get_logger(__name__)

# current file path
CURRENT_FILE_PATH = os.path.dirname(os.path.abspath(__file__))

# seeder file path
PROVIDERS_SEEDER_FILE_PATH = os.path.join(CURRENT_FILE_PATH, "data", "providers_seeder.json")

MODEL_SOURCES = [member.value for member in ModelSourceEnum]


class ProviderSeeder(BaseSeeder):
    """Seeder for the Provider model."""

    async def seed(self) -> None:
        """Seed providers to the database."""
        with Session(engine) as session:
            try:
                await self._seed_providers(session)
            except Exception as e:
                logger.exception(f"Failed to seed providers: {e}")

    @staticmethod
    async def _seed_providers(session: Session) -> None:
        """Seed providers to the database."""
        # providers_data = ProviderSeeder._get_providers_data() # Commented out after credential module migration
        providers_data = await ProviderSeeder._async_get_providers_data()
        logger.debug(f"Found {len(providers_data)} providers in the seeder file")

        providers_data_keys = [each for each in MODEL_SOURCES if each in list(providers_data.keys())]

        all_providers = await ProviderDataManager(session).get_all_providers_by_type(providers_data_keys)
        logger.debug(f"Found {len(all_providers)} providers in the database")

        for provider in all_providers:
            values = {
                "name": providers_data[provider.type.value]["name"],
                "description": providers_data[provider.type.value]["description"],
                "icon": providers_data[provider.type.value]["icon"],
            }
            await ProviderDataManager(session).update_by_fields(provider, values)
            logger.info(f"Updated provider {provider.name} with id {provider.id}")

            # Remove the provider from the data after it has been seeded
            providers_data.pop(provider.type.value)

        if providers_data:
            logger.debug(f"Found {len(providers_data)} new providers")
            create_providers_data = []
            for provider in providers_data:
                if providers_data[provider]["type"] in MODEL_SOURCES:
                    provider_create_data = providers_data[provider]

                    # Remove credentials from the provider data
                    provider_create_data.pop("credentials")

                    create_providers_data.append(ProviderModel(**provider_create_data))

            db_providers = await ProviderDataManager(session).insert_all(create_providers_data)
            logger.debug(f"Seeded {len(db_providers)} new providers")

    @staticmethod
    async def _async_get_providers_data() -> Dict[str, Any]:
        """Get providers data from the database."""
        try:
            with open(PROVIDERS_SEEDER_FILE_PATH, "r") as file:
                return json.load(file)
        except FileNotFoundError as e:
            raise FileNotFoundError(f"File not found: {PROVIDERS_SEEDER_FILE_PATH}") from e

    @staticmethod
    def _get_providers_data() -> Dict[str, Any]:
        """Get providers data from the database."""
        try:
            with open(PROVIDERS_SEEDER_FILE_PATH, "r") as file:
                return json.load(file)
        except FileNotFoundError as e:
            raise FileNotFoundError(f"File not found: {PROVIDERS_SEEDER_FILE_PATH}") from e
