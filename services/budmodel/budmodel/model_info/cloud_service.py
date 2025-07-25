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

from typing import Any, Dict, List, Optional

from budmicroframe.commons import logging

from ..commons.config import app_settings
from ..commons.constants import ModelExtractionStatus
from ..commons.exceptions import ModelExtractionException
from .models import ModelInfoCRUD
from .schemas import CloudModelExtractionRequest, CloudModelExtractionResponse, ModelInfo


logger = logging.get_logger(__name__)


class CloudModelExtractionService:
    """Service class for cloud model extraction from external APIs."""

    @staticmethod
    async def fetch_cloud_model_data(model_uri: str, external_service_url: Optional[str] = None) -> Dict[str, Any]:
        """Fetch cloud model data from external service."""
        import httpx

        # Use configured service URL if no external URL provided
        base_url = external_service_url or app_settings.budconnect_url
        url = f"{base_url}/model/models/{model_uri}/details"

        logger.info("Fetching cloud model data from: %s", url)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers={"accept": "application/json"},
                    timeout=app_settings.budconnect_timeout
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.exception("HTTP error fetching cloud model data: %s", str(e))
            raise ModelExtractionException(f"Failed to fetch cloud model data: {str(e)}") from e
        except Exception as e:
            logger.exception("Unexpected error fetching cloud model data: %s", str(e))
            raise ModelExtractionException(f"Unexpected error: {str(e)}") from e

    @staticmethod
    def map_budconnect_to_model_info(cloud_data: Dict[str, Any]) -> ModelInfo:
        """Map BudConnect API response to ModelInfo schema."""
        try:
            # Map basic fields
            # Convert modality list to string - join with comma if multiple
            modality_list = cloud_data.get("modality", [])
            modality_str = ", ".join(modality_list) if modality_list else "text_input,text_output"

            model_info_data = {
                "uri": cloud_data.get("uri", ""),
                "author": cloud_data.get("provider_name", "Unknown"),
                "description": cloud_data.get("description", ""),
                "modality": modality_str,
                "tags": cloud_data.get("tags", []),
                "tasks": cloud_data.get("tasks", []),
                "use_cases": cloud_data.get("use_cases", []),
                "strengths": cloud_data.get("advantages", []),
                "limitations": cloud_data.get("disadvantages", []),
                "languages": cloud_data.get("languages", []),
                "github_url": cloud_data.get("github_url"),
                "website_url": cloud_data.get("website_url"),
                "logo_url": cloud_data.get("logo_url"),
                "extraction_status": ModelExtractionStatus.COMPLETED,
            }

            # Map papers if available
            if cloud_data.get("papers"):
                papers = []
                for paper in cloud_data["papers"]:
                    papers.append({
                        "title": paper.get("title", ""),
                        "authors": paper.get("authors", []),
                        "url": paper.get("url", "")
                    })
                model_info_data["papers"] = papers

            # Map architecture information if available
            if cloud_data.get("architecture"):
                arch = cloud_data["architecture"]
                model_info_data["architecture"] = {
                    "type": arch.get("type"),
                    "family": arch.get("family"),
                    "num_params": arch.get("num_params"),
                    "model_weights_size": arch.get("model_weights_size"),
                    "text_config": arch.get("text_config"),
                    "vision_config": arch.get("vision_config"),
                    "embedding_config": arch.get("embedding_config")
                }

            # Map model tree/derivatives if available
            if cloud_data.get("model_tree"):
                tree = cloud_data["model_tree"]
                model_info_data["model_tree"] = {
                    "base_model": tree.get("base_model"),
                    "is_finetune": tree.get("is_finetune"),
                    "is_adapter": tree.get("is_adapter"),
                    "is_quantization": tree.get("is_quantization"),
                    "is_merge": tree.get("is_merge")
                }

            return ModelInfo.model_validate(model_info_data)

        except Exception as e:
            logger.exception("Error mapping BudConnect data to ModelInfo: %s", str(e))
            raise ModelExtractionException(f"Failed to map cloud model data: {str(e)}") from e

    @staticmethod
    def extract_evaluation_data(cloud_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract evaluation/benchmark data from cloud model response."""
        evaluations = cloud_data.get("evaluations", [])
        formatted_evals = []

        for eval_item in evaluations:
            formatted_evals.append({
                "name": eval_item.get("name", ""),  # Changed from benchmark_name to name
                "score": eval_item.get("score", 0),
                "metric_type": "accuracy",  # Default metric type
            })

        return formatted_evals

    async def __call__(self, request: CloudModelExtractionRequest) -> CloudModelExtractionResponse:
        """Execute cloud model extraction process."""
        logger.info("Starting cloud model extraction for URI: %s", request.model_uri)

        try:
            # Fetch data from external service
            cloud_data = await self.fetch_cloud_model_data(request.model_uri, request.external_service_url)

            # Map to ModelInfo schema
            model_info = self.map_budconnect_to_model_info(cloud_data)

            # Extract evaluation data
            model_evals = self.extract_evaluation_data(cloud_data)

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

                leaderboard_data = LeaderboardService().format_llm_leaderboard_data(
                    model_evals, db_model_info.id
                )
                with LeaderboardCRUD() as crud:
                    crud.update_or_insert_leaderboards(db_model_info.id, leaderboard_data)
                    logger.debug("Leaderboard data inserted for cloud model %s", model_info.uri)

            logger.info("Successfully extracted cloud model: %s", request.model_uri)
            return CloudModelExtractionResponse(model_info=model_info)

        except Exception as e:
            logger.exception("Error in cloud model extraction: %s", str(e))
            raise e

