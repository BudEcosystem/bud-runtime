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

"""CRUD operations for prompt storage."""

import logging
from typing import Optional
from uuid import UUID, uuid4

from budmicroframe.shared.psql_service import CRUDMixin

from .models import Prompt, PromptVersion
from .schemas import PromptConfigurationData


logger = logging.getLogger(__name__)


class PromptCRUD(CRUDMixin[Prompt, None, None]):
    """CRUD operations for Prompt model."""

    __model__ = Prompt

    def __init__(self):
        """Initialize PromptCRUD.

        Args:
            database: Optional database instance. If not provided, uses singleton.
        """
        super().__init__(self.__model__)

    def upsert_prompt(self, prompt_id: str, default_version_id: Optional[UUID] = None) -> Prompt:
        """Upsert a prompt record.

        Creates a new prompt if it doesn't exist, or returns existing one.
        The prompt_id string is used as the unique name field.

        Args:
            prompt_id: String identifier used as prompt name
            default_version_id: Optional UUID of the default version

        Returns:
            Prompt record (new or existing)

        Raises:
            SQLAlchemyError: If database operation fails
        """
        session = self.get_session()

        try:
            # Check if prompt exists by name
            existing_prompt = session.query(Prompt).filter(Prompt.name == prompt_id).first()

            if existing_prompt:
                # Update default_version_id if provided
                if default_version_id is not None:
                    existing_prompt.default_version_id = default_version_id
                    session.commit()
                    logger.debug(f"Updated default_version_id for prompt {prompt_id}")

                return existing_prompt
            else:
                # Create new prompt
                new_prompt = Prompt(
                    id=uuid4(),
                    name=prompt_id,
                    default_version_id=default_version_id,
                )
                session.add(new_prompt)
                session.commit()
                session.refresh(new_prompt)
                logger.debug(f"Created new prompt {prompt_id} with id {new_prompt.id}")

                return new_prompt

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to upsert prompt {prompt_id}: {str(e)}")
            raise


class PromptVersionCRUD(CRUDMixin[PromptVersion, None, None]):
    """CRUD operations for PromptVersion model."""

    __model__ = PromptVersion

    def __init__(self):
        """Initialize PromptVersionCRUD.

        Args:
            database: Optional database instance. If not provided, uses singleton.
        """
        super().__init__(self.__model__)

    def upsert_prompt_version(
        self, prompt_db_id: UUID, version: int, config_data: PromptConfigurationData
    ) -> PromptVersion:
        """Upsert a prompt version record.

        Creates a new version if (prompt_id, version) doesn't exist, or updates existing.

        Args:
            prompt_db_id: UUID of the parent Prompt record
            version: Version number
            config_data: Configuration data to store

        Returns:
            PromptVersion record (new or updated)

        Raises:
            SQLAlchemyError: If database operation fails
        """
        session = self.get_session()

        try:
            # Check if version exists
            existing_version = (
                session.query(PromptVersion)
                .filter(PromptVersion.prompt_id == prompt_db_id, PromptVersion.version == version)
                .first()
            )

            # Convert config data to dict
            version_data = config_data.model_dump()

            if existing_version:
                # Update existing version
                for key, value in version_data.items():
                    setattr(existing_version, key, value)

                session.commit()
                session.refresh(existing_version)
                logger.debug(f"Updated prompt version {prompt_db_id}:v{version}")

                return existing_version
            else:
                # Create new version
                new_version = PromptVersion(
                    id=uuid4(),
                    prompt_id=prompt_db_id,
                    version=version,
                    **version_data,
                )
                session.add(new_version)
                session.commit()
                session.refresh(new_version)
                logger.debug(f"Created new prompt version {prompt_db_id}:v{version} with id {new_version.id}")

                return new_version

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to upsert prompt version {prompt_db_id}:v{version}: {str(e)}")
            raise
