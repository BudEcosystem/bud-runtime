import json
import os
from typing import Any, Dict

from sqlalchemy.orm import Session

from budapp.commons import logging
from budapp.commons.database import engine
from budapp.core.crud import ModelTemplateDataManager
from budapp.core.models import ModelTemplate
from budapp.core.schemas import ModelTemplateCreate, ModelTemplateUpdate

from .base_seeder import BaseSeeder


logger = logging.get_logger(__name__)

# current file path
CURRENT_FILE_PATH = os.path.dirname(os.path.abspath(__file__))

# seeder file path
TEMPLATES_SEEDER_FILE_PATH = os.path.join(CURRENT_FILE_PATH, "data", "template_seeder.json")


class TemplateSeeder(BaseSeeder):
    """Seeder for the Provider model."""

    async def seed(self) -> None:
        """Seed providers to the database."""
        with Session(engine) as session:
            try:
                await self._seed_templates(session)
            except Exception as e:
                logger.exception(f"Failed to seed templates: {e}")

    @staticmethod
    async def _seed_templates(session: Session) -> None:
        """Seed templates into the database. Updates existing templates if they already exist."""
        # Get all existing templates from database
        existing_db_templates = []
        offset = 0
        limit = 100

        while True:
            db_templates, count = await ModelTemplateDataManager(session).get_all_model_templates(
                offset=offset, limit=limit
            )

            if not db_templates:
                break

            existing_db_templates.extend(db_templates)
            offset += limit

            logger.info(f"Fetched {count} templates. Total templates found: {len(existing_db_templates)}")

            if count < limit:
                break

            logger.info(f"Finished fetching templates. Total templates found: {len(existing_db_templates)}")

        template_seeder_data = await TemplateSeeder._get_templates_data()
        # Store new templates model for bulk creation
        template_data_to_seed = []

        # Map template seeder data by template type for quick lookup
        template_seeder_data_mapping = {template["template_type"]: template for template in template_seeder_data}

        # Update existing template with seeder data
        for db_template in existing_db_templates:
            if db_template.template_type in template_seeder_data_mapping:
                update_template_data = ModelTemplateUpdate(**template_seeder_data_mapping[db_template.template_type])
                db_updated_template = await ModelTemplateDataManager(session).update_by_fields(
                    db_template, update_template_data.model_dump(exclude_unset=True)
                )
                logger.debug(f"Updated template: {db_updated_template.template_type}")

                # Remove the updated template from the mapping
                del template_seeder_data_mapping[db_template.template_type]

        # Remaining templates are new and need to be created
        for template_type, template_data in template_seeder_data_mapping.items():
            # Store new template data for bulk creation
            create_template_data = ModelTemplateCreate(**template_data)
            template_data_to_seed.append(ModelTemplate(**create_template_data.model_dump(exclude_unset=True)))
            logger.info(f"Added template: {template_type} to seed")

        # Create new templates in the database
        created_templates = await ModelTemplateDataManager(session).insert_all(template_data_to_seed)
        logger.info(f"Created {len(created_templates)} templates")

    @staticmethod
    async def _get_templates_data() -> Dict[str, Any]:
        """Get providers data from the database."""
        try:
            with open(TEMPLATES_SEEDER_FILE_PATH, "r") as file:
                return json.load(file)
        except FileNotFoundError as e:
            raise FileNotFoundError(f"File not found: {TEMPLATES_SEEDER_FILE_PATH}") from e
