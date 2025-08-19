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

"""CRUD operations for the prompt ops module."""

from uuid import UUID

from sqlalchemy import func, select

from budapp.commons.db_utils import DataManagerUtils

from .models import Prompt as PromptModel
from .models import PromptVersion as PromptVersionModel


class PromptDataManager(DataManagerUtils):
    """CRUD operations for Prompt model."""

    pass


class PromptVersionDataManager(DataManagerUtils):
    """CRUD operations for PromptVersion model."""

    async def get_next_version(self, prompt_id: UUID) -> int:
        """Get the next version number for a prompt."""
        result = await self.session.execute(
            select(func.max(PromptVersionModel.version)).where(PromptVersionModel.prompt_id == prompt_id)
        )
        max_version = result.scalar()
        return (max_version or 0) + 1
