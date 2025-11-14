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
        """Upsert a prompt record using CRUDMixin's methods.

        Creates a new prompt if it doesn't exist, or updates existing one.
        The prompt_id string is used as the unique name field.

        Args:
            prompt_id: String identifier used as prompt name
            default_version_id: Optional UUID of the default version

        Returns:
            Prompt record (new or existing)
        """
        # Check if prompt exists by name
        existing_prompt = self.fetch_one(conditions={"name": prompt_id})

        if existing_prompt:
            # Update default_version_id if provided
            if default_version_id is not None:
                existing_prompt.default_version_id = default_version_id
                self.update(data=existing_prompt, conditions={"id": existing_prompt.id})
                logger.debug(f"Updated default_version_id for prompt {prompt_id}")
            return existing_prompt
        else:
            # Create new prompt using insert method
            new_prompt = Prompt(
                id=uuid4(),
                name=prompt_id,
                default_version_id=default_version_id,
            )
            result = self.insert(data=new_prompt)
            logger.debug(f"Created new prompt {prompt_id} with id {result.id}")
            return result


class PromptVersionCRUD(CRUDMixin[PromptVersion, None, None]):
    """CRUD operations for PromptVersion model."""

    __model__ = PromptVersion

    def __init__(self):
        """Initialize PromptVersionCRUD.

        Args:
            database: Optional database instance. If not provided, uses singleton.
        """
        super().__init__(self.__model__)

    def upsert_prompt_version(self, prompt_db_id: UUID, version: int, version_data: dict) -> PromptVersion:
        """Upsert a prompt version record using CRUDMixin's methods.

        Creates a new version if (prompt_id, version) doesn't exist, or updates existing.

        Args:
            prompt_db_id: UUID of the parent Prompt record
            version: Version number
            config_data: Configuration data to store

        Returns:
            PromptVersion record (new or updated)
        """
        # Check if version exists
        existing_version = self.fetch_one(conditions={"prompt_id": prompt_db_id, "version": version})

        if existing_version:
            # Update existing version
            for key, value in version_data.items():
                setattr(existing_version, key, value)
            self.update(data=existing_version, conditions={"id": existing_version.id})
            logger.debug(f"Updated prompt version {prompt_db_id}:v{version}")
            # Fetch updated version to return
            return self.fetch_one(conditions={"id": existing_version.id})
        else:
            # Create new version using insert method
            new_version = PromptVersion(
                id=uuid4(),
                prompt_id=prompt_db_id,
                version=version,
                **version_data,
            )
            result = self.insert(data=new_version)
            logger.debug(f"Created new prompt version {prompt_db_id}:v{version} with id {result.id}")
            return result

    def count_versions(self, prompt_db_id: UUID) -> int:
        """Count remaining versions for a prompt.

        Args:
            prompt_db_id: UUID of the parent Prompt record

        Returns:
            Number of versions remaining
        """
        _session = self.get_session()
        return _session.query(PromptVersion).filter_by(prompt_id=prompt_db_id).count()
