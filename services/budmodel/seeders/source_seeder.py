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

"""Seeds the sources from the seeder data."""

import json
import os

from budmicroframe.commons import logging

from budmodel.commons.config import app_settings
from budmodel.leaderboard.crud import SourceCRUD
from budmodel.leaderboard.schemas import SourceCreate

from .base_seeder import BaseSeeder


logger = logging.get_logger(__name__)

SEEDER_DATA_PATH = os.path.join(app_settings.base_dir, "seeders", "source_data.json")


class SourceSeeder(BaseSeeder):
    async def seed(self):
        """Seeds the sources from the seeder data.

        Args:
            None

        Returns:
            None
        """
        logger.info(f"Seeding sources from {SEEDER_DATA_PATH}")

        # Load the seeder data
        with open(SEEDER_DATA_PATH, "r") as f:
            sources_data = json.load(f)

        # Insert or update sources data in the Sources table
        for _source_key, source_data in sources_data.items():
            source_name = source_data.get("name")
            source_js_code = source_data.get("js_code", "")
            if source_js_code:
                source_js_code = source_js_code[0]

            source_data = SourceCreate(
                name=source_name,
                url=source_data.get("url"),
                wait_for=source_data.get("wait_for", ""),
                js_code=source_js_code,
                schema=json.dumps(source_data.get("schema", {})),
                css_base_selector=source_data.get("baseSelector", ""),
            )

            # Check if the source already exists in the database
            existing_source = SourceCRUD().fetch_one(conditions={"name": source_name})

            if existing_source:
                # Update the existing source
                logger.debug(f"Source {source_name} already exists in the database. Updating...")
                SourceCRUD().update(data=source_data.model_dump(), conditions={"id": existing_source.id})
            else:
                # Insert new source
                logger.debug(f"Source {source_name} does not exist in the database. Inserting...")
                SourceCRUD().insert(data=source_data.model_dump())


if __name__ == "__main__":
    SourceSeeder().seed()

# Command to run the seeder
# python -m seeders.source
