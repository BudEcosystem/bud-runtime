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

"""HuggingFace model extraction with BudConnect integration."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from budmicroframe.commons import logging

from ..commons.connect_utils import BudConnectClient, BudConnectMapper
from ..commons.constants import ModelExtractionStatus
from .huggingface import HuggingFaceModelInfo
from .models import ModelInfoCRUD
from .schemas import ModelInfo


logger = logging.get_logger(__name__)


class HuggingFaceWithBudConnect:
    """HuggingFace model extraction with BudConnect caching."""

    def __init__(self):
        """Initialize HuggingFace with BudConnect integration."""
        self.client = BudConnectClient()
        self.mapper = BudConnectMapper()
        self.hf_extractor = HuggingFaceModelInfo()

    async def extract_model_info(
        self, model_uri: str, hf_token: Optional[str] = None, force_extract: bool = False
    ) -> Tuple[ModelInfo, List[Dict], bool]:
        """Extract model information with BudConnect caching.

        Args:
            model_uri: HuggingFace model URI (e.g., "meta-llama/Llama-2-7b").
            hf_token: Optional HuggingFace token for private models.
            force_extract: If True, skip BudConnect check and force extraction.

        Returns:
            Tuple of (ModelInfo, evaluations list, from_cache flag).
            - ModelInfo: The extracted model information.
            - evaluations: List of model evaluation/benchmark data.
            - from_cache: True if data was retrieved from BudConnect, False if freshly extracted.
        """
        model_evals = []
        from_cache = False

        # Step 1: Check BudConnect for existing model information
        if not force_extract:
            logger.info("Checking BudConnect for existing model info: %s", model_uri)
            try:
                budconnect_data = await self.client.fetch_model_details(model_uri)

                if budconnect_data:
                    logger.info("Found model in BudConnect: %s", model_uri)

                    # Map BudConnect data to ModelInfo
                    model_info_data = self.mapper.map_to_model_info(budconnect_data)
                    model_info = ModelInfo.model_validate(model_info_data)

                    # Extract evaluations
                    model_evals = self.mapper.extract_evaluation_data(budconnect_data)

                    from_cache = True
                    return model_info, model_evals, from_cache
                else:
                    logger.info("Model not found in BudConnect, will extract from HuggingFace: %s", model_uri)

            except Exception as e:
                logger.warning("Failed to check BudConnect, will extract from HuggingFace: %s", str(e))

        # Step 2: Extract from HuggingFace if not in BudConnect
        logger.info("Extracting model info from HuggingFace: %s", model_uri)
        model_info, model_evals = self.hf_extractor.from_pretrained(model_uri, hf_token)

        # Step 3: Save to BudConnect for future use
        try:
            await self._save_to_budconnect(model_info, model_evals)
        except Exception as e:
            logger.error("Failed to save model to BudConnect: %s", str(e))
            # Continue even if save fails - we have the data

        return model_info, model_evals, from_cache

    async def _save_to_budconnect(self, model_info: ModelInfo, model_evals: List[Dict]) -> None:
        """Save extracted model information to BudConnect.

        Args:
            model_info: ModelInfo object with extracted data.
            model_evals: List of evaluation/benchmark data.
        """
        logger.info("Saving model to BudConnect: %s", model_info.uri)

        # Convert ModelInfo to dict for mapping
        model_info_dict = model_info.model_dump(mode="json")

        # Map to BudConnect format
        budconnect_data = self.mapper.model_info_to_budconnect(model_info_dict, model_evals)

        # Save to BudConnect
        await self.client.save_model_details(budconnect_data)
        logger.info("Successfully saved model to BudConnect: %s", model_info.uri)

    async def sync_with_database(self, model_info: ModelInfo, model_evals: List[Dict], from_cache: bool) -> None:
        """Sync model information with local database.

        Args:
            model_info: ModelInfo object.
            model_evals: List of evaluation data.
            from_cache: Whether data came from BudConnect cache.
        """
        model_info_dict = model_info.model_dump(mode="json", exclude={"license"})

        if model_info.license is not None:
            model_info_dict["license_id"] = model_info.license.id

        # Update extraction status based on source
        if from_cache:
            model_info_dict["extraction_status"] = ModelExtractionStatus.CACHED
        else:
            model_info_dict["extraction_status"] = ModelExtractionStatus.COMPLETED

        # Save to local database
        with ModelInfoCRUD() as crud:
            existing_model = crud.fetch_one(conditions={"uri": model_info.uri})
            if existing_model:
                db_model_info = crud.update(data=model_info_dict, conditions={"uri": model_info.uri})
                logger.debug("Model info updated in database for uri %s", model_info.uri)
            else:
                crud.insert(data=model_info_dict, raise_on_error=False)
                logger.debug("Model info inserted in database for uri %s", model_info.uri)
                db_model_info = crud.fetch_one(conditions={"uri": model_info.uri})

        # Save evaluation data if available
        if model_evals and db_model_info:
            from ..leaderboard.crud import LeaderboardCRUD
            from ..leaderboard.services import LeaderboardService

            leaderboard_data = LeaderboardService().format_llm_leaderboard_data(model_evals, db_model_info.id)
            with LeaderboardCRUD() as crud:
                crud.update_or_insert_leaderboards(db_model_info.id, leaderboard_data)
                logger.debug("Leaderboard data saved for model %s", model_info.uri)


# Convenience function for backward compatibility
async def extract_huggingface_with_budconnect(
    model_uri: str, hf_token: Optional[str] = None, force_extract: bool = False
) -> Tuple[ModelInfo, List[Dict]]:
    """Extract HuggingFace model with BudConnect integration.

    Args:
        model_uri: HuggingFace model URI.
        hf_token: Optional HuggingFace token.
        force_extract: Force extraction even if cached.

    Returns:
        Tuple of (ModelInfo, evaluations list).
    """
    extractor = HuggingFaceWithBudConnect()
    model_info, model_evals, from_cache = await extractor.extract_model_info(model_uri, hf_token, force_extract)

    # Sync with database
    await extractor.sync_with_database(model_info, model_evals, from_cache)

    return model_info, model_evals
