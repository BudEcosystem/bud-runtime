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

"""Cloud model extraction service for fetching model information from external APIs."""

from budmicroframe.commons import logging

from ..commons.connect_utils import BudConnectClient, BudConnectMapper
from ..commons.exceptions import ModelExtractionException
from .models import ModelInfoCRUD
from .schemas import CloudModelExtractionRequest, CloudModelExtractionResponse, ModelInfo


logger = logging.get_logger(__name__)


class CloudModelExtractionService:
    """Service class for cloud model extraction from external APIs."""

    def __init__(self):
        """Initialize the cloud model extraction service."""
        self.client = BudConnectClient()
        self.mapper = BudConnectMapper()

    async def __call__(self, request: CloudModelExtractionRequest) -> CloudModelExtractionResponse:
        """Execute cloud model extraction process."""
        logger.info("Starting cloud model extraction for URI: %s", request.model_uri)

        try:
            # Use custom URL if provided, otherwise use default client
            if request.external_service_url:
                client = BudConnectClient(base_url=request.external_service_url)
            else:
                client = self.client

            # Fetch data from external service
            cloud_data = await client.fetch_model_details(request.model_uri)

            if cloud_data is None:
                raise ModelExtractionException(f"Model '{request.model_uri}' not found in BudConnect.")

            # Map to ModelInfo schema
            model_info_data = self.mapper.map_to_model_info(cloud_data)
            model_info = ModelInfo.model_validate(model_info_data)

            # Extract evaluation data
            model_evals = self.mapper.extract_evaluation_data(cloud_data)

            # Save to database
            model_info_dict = model_info.model_dump(mode="json", exclude={"license"})

            with ModelInfoCRUD() as crud:
                existing_model = crud.fetch_one(conditions={"uri": model_info.uri})
                if existing_model:
                    crud.update(data=model_info_dict, conditions={"uri": model_info.uri})
                    logger.debug("Cloud model info updated for uri %s", model_info.uri)
                    # Fetch the updated model to get the full object
                    db_model_info = crud.fetch_one(conditions={"uri": model_info.uri})
                else:
                    crud.insert(data=model_info_dict, raise_on_error=False)
                    logger.debug("Cloud model info inserted for uri %s", model_info.uri)
                    # Fetch the inserted model to get the full object
                    db_model_info = crud.fetch_one(conditions={"uri": model_info.uri})

            # Save evaluation data if available
            if model_evals and db_model_info:
                from ..leaderboard.crud import LeaderboardCRUD
                from ..leaderboard.services import LeaderboardService

                leaderboard_data = LeaderboardService().format_llm_leaderboard_data(model_evals, db_model_info.id)
                with LeaderboardCRUD() as crud:
                    crud.update_or_insert_leaderboards(db_model_info.id, leaderboard_data)
                    logger.debug("Leaderboard data inserted for cloud model %s", model_info.uri)

            logger.info("Successfully extracted cloud model: %s", request.model_uri)
            return CloudModelExtractionResponse(model_info=model_info)

        except Exception as e:
            logger.exception("Error in cloud model extraction: %s", str(e))
            raise e
