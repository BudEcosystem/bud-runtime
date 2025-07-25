import os

from sqlalchemy.orm import Session

from budapp.commons import logging
from budapp.commons.config import app_settings
from budapp.commons.database import engine
from budapp.commons.helpers import replicate_dir
from budapp.core.crud import IconDataManager
from budapp.core.models import Icon as IconModel
from budapp.core.schemas import IconCreate, IconUpdate

from .base_seeder import BaseSeeder


logger = logging.get_logger(__name__)

ALLOWED_EXTENSIONS = ("png",)
ICON_DIR_NAME = os.path.basename(app_settings.icon_dir)


class IconSeeder(BaseSeeder):
    """Seeder for the Icon model."""

    async def seed(self) -> None:
        """Seed icons to the database."""
        with Session(engine) as session:
            try:
                await self._seed_icons(session)
            except Exception as e:
                logger.exception(f"Failed to seed icons: {e}")

    @staticmethod
    async def _process_icon_name(filename: str) -> str:
        """Process icon name to be used as the name of the icon
        - Remove file extension
        - Replace underscores with spaces
        - Convert to title case (camel case for multi-word names).
        """
        name = os.path.splitext(filename)[0]
        name = name.replace("_", " ")
        return name.title()

    async def _seed_icons(self, session: Session) -> None:
        """Seed icons into the database."""
        # Store new icons as a list for bulk creation
        icons_to_create = []
        if app_settings.static_dir != os.path.join(str(app_settings.base_dir), "static"):
            default_icons_path = os.path.join(str(app_settings.base_dir), "static", "icons")
            replicate_dir(default_icons_path, app_settings.icon_dir, is_override=True)

        for category in os.listdir(app_settings.icon_dir):
            category_dir = os.path.join(app_settings.icon_dir, category)

            # Extract icon files from the category directory
            if os.path.isdir(category_dir):
                logger.debug(f"Extracting icons from {category}")

                for icon_file in os.listdir(category_dir):
                    # Check if the file is an icon
                    if icon_file.endswith(ALLOWED_EXTENSIONS):
                        file_path = os.path.join(ICON_DIR_NAME, category, icon_file)
                        name = await self._process_icon_name(icon_file)

                        db_icon = await IconDataManager(session).retrieve_by_fields(
                            IconModel, {"file_path": file_path}, missing_ok=True
                        )

                        if db_icon:
                            icon_update_data = IconUpdate(name=name, category=category).model_dump(
                                exclude_unset=True, exclude_none=True
                            )

                            # Update icon in the database
                            db_updated_icon = await IconDataManager(session).update_by_fields(
                                db_icon, icon_update_data
                            )
                            logger.debug(f"Updated icon {db_updated_icon.id}")
                        else:
                            icon_create_data = IconCreate(name=name, category=category, file_path=file_path)

                            # Add to list of icons to create
                            icons_to_create.append(IconModel(**icon_create_data.model_dump()))

                # Bulk create icons with batch size of 100
                BATCH_SIZE = 100
                for i in range(0, len(icons_to_create), BATCH_SIZE):
                    batch = icons_to_create[i : i + BATCH_SIZE]
                    await IconDataManager(session).insert_all(batch)
                    logger.debug(f"Created {len(batch)} icons")
