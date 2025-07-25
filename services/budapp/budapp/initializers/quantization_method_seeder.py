import json
import os
from typing import Any, Dict

from sqlalchemy.orm import Session

from budapp.commons import logging
from budapp.commons.database import engine
from budapp.model_ops.crud import QuantizationMethodDataManager
from budapp.model_ops.models import QuantizationMethod as QuantizationMethodModel
from budapp.model_ops.schemas import QuantizationMethod

from .base_seeder import BaseSeeder


logger = logging.get_logger(__name__)

# current file path
CURRENT_FILE_PATH = os.path.dirname(os.path.abspath(__file__))

# seeder file path
QUANTIZATION_METHODS_SEEDER_FILE_PATH = os.path.join(CURRENT_FILE_PATH, "data", "quantization_method_seeder.json")


class QuantizationMethodSeeder(BaseSeeder):
    """Seeder for the QuantizationMethod model."""

    async def seed(self) -> None:
        """Seed quantization methods to the database."""
        with Session(engine) as session:
            try:
                await self._seed_quantization_methods(session)
            except Exception as e:
                logger.exception(f"Failed to seed quantization methods: {e}")

    @staticmethod
    async def _seed_quantization_methods(session: Session) -> None:
        """Seed quantization methods into the database. Updates existing quantization methods if they already exist."""
        # Get all existing quantization methods from database
        existing_db_quantization_methods = []
        offset = 0
        limit = 100

        while True:
            db_quantization_methods, count = await QuantizationMethodDataManager(session).get_all_quantization_methods(
                offset=offset, limit=limit
            )

            if not db_quantization_methods:
                break

            existing_db_quantization_methods.extend(db_quantization_methods)
            offset += limit

            logger.info(
                f"Fetched {count} quantization methods. Total quantization methods found: {len(existing_db_quantization_methods)}"
            )

            if count < limit:
                break

            logger.info(
                f"Finished fetching quantization methods. Total quantization methods found: {len(existing_db_quantization_methods)}"
            )

        quantization_method_seeder_data = await QuantizationMethodSeeder._get_quantization_methods_data()

        # Store new quantization methods for bulk creation
        quantization_method_data_to_seed = []

        # Map quantization method seeder data by name for quick lookup
        quantization_method_seeder_data_mapping = {
            quantization_method["name"]: quantization_method for quantization_method in quantization_method_seeder_data
        }

        # Update existing quantization methods with seeder data
        for db_quantization_method in existing_db_quantization_methods:
            if db_quantization_method.name in quantization_method_seeder_data_mapping:
                update_quantization_method_data = QuantizationMethod(
                    **quantization_method_seeder_data_mapping[db_quantization_method.name]
                )
                db_updated_quantization_method = await QuantizationMethodDataManager(session).update_by_fields(
                    db_quantization_method, update_quantization_method_data.model_dump(exclude_unset=True)
                )
                logger.debug(f"Updated quantization method: {db_updated_quantization_method.name}")

                # Remove the updated quantization method from the mapping
                del quantization_method_seeder_data_mapping[db_quantization_method.name]

        # Remaining quantization methods are new and need to be created
        for quantization_method_name, quantization_method_data in quantization_method_seeder_data_mapping.items():
            # Store new quantization method data for bulk creation
            create_quantization_method_data = QuantizationMethod(**quantization_method_data)
            quantization_method_data_to_seed.append(
                QuantizationMethodModel(**create_quantization_method_data.model_dump(exclude_unset=True))
            )
            logger.info(f"Added quantization method: {quantization_method_name} to seed")

        # Bulk create new quantization methods
        created_quantization_methods = await QuantizationMethodDataManager(session).insert_all(
            quantization_method_data_to_seed
        )
        logger.info(f"Created {len(created_quantization_methods)} quantization methods")

    @staticmethod
    async def _get_quantization_methods_data() -> Dict[str, Any]:
        """Get quantization methods data from the database."""
        try:
            with open(QUANTIZATION_METHODS_SEEDER_FILE_PATH, "r") as file:
                return json.load(file)
        except FileNotFoundError as e:
            raise FileNotFoundError(f"File not found: {QUANTIZATION_METHODS_SEEDER_FILE_PATH}") from e
