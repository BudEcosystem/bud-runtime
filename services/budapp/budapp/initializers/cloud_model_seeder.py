import json
import os
from typing import Any, Dict

from sqlalchemy.orm import Session

from budapp.commons import logging
from budapp.commons.config import app_settings
from budapp.commons.constants import ModelProviderTypeEnum, ModelSourceEnum, UserStatusEnum
from budapp.commons.database import engine
from budapp.model_ops.crud import CloudModelDataManager, ProviderDataManager
from budapp.model_ops.models import CloudModel
from budapp.model_ops.models import Provider as ProviderModel
from budapp.user_ops.crud import UserDataManager
from budapp.user_ops.models import User as UserModel

from .base_seeder import BaseSeeder


logger = logging.get_logger(__name__)

# current file path
CURRENT_FILE_PATH = os.path.dirname(os.path.abspath(__file__))

# seeder file path
CLOUD_MODEL_SEEDER_FILE_PATH = os.path.join(CURRENT_FILE_PATH, "data", "cloud_model_seeder.json")


MODEL_SOURCES = [member.value for member in ModelSourceEnum]


class CloudModelSeeder(BaseSeeder):
    """Cloud model seeder."""

    async def seed(self):
        """Seed the cloud models."""
        with Session(engine) as session:
            try:
                await self._seed_cloud_models(session)
            except Exception as e:
                logger.exception(f"Failed to seed cloud models: {e}")

    @staticmethod
    async def _seed_cloud_models(session: Session) -> None:
        """Seed the cloud models."""
        db_user = await UserDataManager(session).retrieve_by_fields(
            UserModel,
            {"email": app_settings.superuser_email, "status": UserStatusEnum.ACTIVE, "is_superuser": True},
            missing_ok=True,
        )

        if db_user:
            cloud_model_data = await CloudModelSeeder._get_cloud_model_data()
            logger.debug(f"Seeding cloud models for {len(cloud_model_data)} providers")

            for provider, model_data in cloud_model_data.items():
                if provider not in MODEL_SOURCES:
                    continue
                db_provider = await ProviderDataManager(session).retrieve_by_fields(
                    ProviderModel,
                    {"type": provider},
                    missing_ok=True,
                )
                # URI as key and details as value
                provider_model = {}
                for model in model_data["models"]:
                    provider_model[model["uri"]] = model

                # Check if the models already exist
                existing_models = await CloudModelDataManager(session).get_all_cloud_models_by_source_uris(
                    provider, list(provider_model.keys())
                )
                logger.debug(f"Found {len(existing_models)} existing models for provider {provider}. Updating...")

                # Update the existing models
                for existing_model in existing_models:
                    update_data = {
                        "name": provider_model[existing_model.uri]["name"],
                        "modality": provider_model[existing_model.uri]["modality"],
                        "source": provider_model[existing_model.uri]["source"],
                        "uri": provider_model[existing_model.uri]["uri"],
                        "provider_type": ModelProviderTypeEnum.CLOUD_MODEL.value,
                        "provider_id": db_provider.id,
                        "max_input_tokens": provider_model[existing_model.uri]["max_input_tokens"],
                        "input_cost": provider_model[existing_model.uri]["input_cost"],
                        "output_cost": provider_model[existing_model.uri]["output_cost"],
                    }

                    # Update existing model in the database
                    await CloudModelDataManager(session).update_by_fields(existing_model, update_data)

                    # Remove the model from the provider_model
                    del provider_model[existing_model.uri]

                # Bulk insert the new models
                new_models = [
                    CloudModel(
                        **model, provider_type=ModelProviderTypeEnum.CLOUD_MODEL.value, provider_id=db_provider.id
                    )
                    for model in provider_model.values()
                ]
                await CloudModelDataManager(session).insert_all(new_models)
                logger.debug(f"Seeded {len(new_models)} new models for provider {provider}")
        else:
            logger.error("Super user not found. Skipping cloud model seeding.")

    @staticmethod
    async def _get_cloud_model_data() -> Dict[str, Any]:
        """Get cloud_model data from the database."""
        try:
            with open(CLOUD_MODEL_SEEDER_FILE_PATH, "r") as file:
                return json.load(file)
        except FileNotFoundError as e:
            raise FileNotFoundError(f"File not found: {CLOUD_MODEL_SEEDER_FILE_PATH}") from e
