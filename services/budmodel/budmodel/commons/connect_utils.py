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

"""Utilities for interacting with BudConnect service."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx
from budmicroframe.commons import logging

from .config import app_settings
from .constants import ModelExtractionStatus
from .exceptions import ModelExtractionException


logger = logging.get_logger(__name__)


class BudConnectClient:
    """Client for interacting with BudConnect API."""

    def __init__(self, base_url: Optional[str] = None, timeout: Optional[int] = None):
        """Initialize BudConnect client.

        Args:
            base_url: Base URL for BudConnect service. Defaults to app_settings.budconnect_url.
            timeout: Request timeout in seconds. Defaults to app_settings.budconnect_timeout.
        """
        self.base_url = base_url or app_settings.budconnect_url
        self.timeout = timeout or app_settings.budconnect_timeout

    async def fetch_model_details(self, model_uri: str) -> Optional[Dict[str, Any]]:
        """Fetch model details from BudConnect.

        Args:
            model_uri: URI of the model to fetch details for.

        Returns:
            Dictionary containing model details from BudConnect, or None if not found.

        Raises:
            ModelExtractionException: If fetching fails with non-404 error.
        """
        url = f"{self.base_url}/model/models/{model_uri}/details"
        logger.info("Fetching model details from BudConnect: %s", url)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers={"accept": "application/json"}, timeout=self.timeout)
                if response.status_code == 404:
                    logger.info("Model not found in BudConnect: %s", model_uri)
                    return None
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.exception("HTTP error fetching model details from BudConnect: %s", str(e))
            raise ModelExtractionException(f"Failed to fetch model details: {str(e)}") from e
        except Exception as e:
            logger.exception("Unexpected error fetching model details from BudConnect: %s", str(e))
            raise ModelExtractionException(f"Unexpected error: {str(e)}") from e

    async def save_model_details(self, model_data: Dict[str, Any]) -> Dict[str, Any]:
        """Save model details to BudConnect.

        Args:
            model_data: Dictionary containing model information to save.

        Returns:
            Dictionary containing the response from BudConnect.

        Raises:
            ModelExtractionException: If saving fails.
        """
        url = f"{self.base_url}/model/models"
        logger.info("Saving model details to BudConnect: %s", model_data.get("uri"))

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json=model_data,
                    headers={"accept": "application/json", "content-type": "application/json"},
                    timeout=self.timeout,
                )
                response.raise_for_status()
                logger.info("Successfully saved model to BudConnect: %s", model_data.get("uri"))
                return response.json()
        except httpx.HTTPError as e:
            logger.exception("HTTP error saving model details to BudConnect: %s", str(e))
            raise ModelExtractionException(f"Failed to save model details: {str(e)}") from e
        except Exception as e:
            logger.exception("Unexpected error saving model details to BudConnect: %s", str(e))
            raise ModelExtractionException(f"Unexpected error: {str(e)}") from e

    async def fetch_compatible_models(
        self, page: int = 1, limit: int = 100, engine: Optional[str] = None
    ) -> Dict[str, Any]:
        """Fetch compatible models from BudConnect.

        Args:
            page: Page number for pagination.
            limit: Number of items per page.
            engine: Optional engine filter.

        Returns:
            Dictionary containing compatible models and pagination info.

        Raises:
            ModelExtractionException: If fetching fails.
        """
        url = f"{self.base_url}/model/get-compatible-models"
        params = {"page": page, "limit": limit}
        if engine:
            params["engine"] = engine

        logger.info("Fetching compatible models from BudConnect: %s (page=%s, limit=%s)", url, page, limit)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url, params=params, headers={"accept": "application/json"}, timeout=self.timeout
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.exception("HTTP error fetching compatible models from BudConnect: %s", str(e))
            raise ModelExtractionException(f"Failed to fetch compatible models: {str(e)}") from e
        except Exception as e:
            logger.exception("Unexpected error fetching compatible models from BudConnect: %s", str(e))
            raise ModelExtractionException(f"Unexpected error: {str(e)}") from e


class BudConnectMapper:
    """Maps BudConnect API responses to internal schemas and vice versa."""

    @staticmethod
    def model_info_to_budconnect(
        model_info: Dict[str, Any], model_evals: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Convert ModelInfo to BudConnect format for saving.

        Args:
            model_info: ModelInfo data dictionary.
            model_evals: Optional list of model evaluation data.

        Returns:
            Dictionary formatted for BudConnect API.
        """
        # Parse modality string back to list
        modality_str = model_info.get("modality", "")
        modality_list = [m.strip() for m in modality_str.split(",")] if modality_str else []

        budconnect_data = {
            "uri": model_info.get("uri", ""),
            "provider_name": model_info.get("author", "Unknown"),
            "description": model_info.get("description", ""),
            "modality": modality_list,
            "tags": model_info.get("tags", []),
            "tasks": model_info.get("tasks", []),
            "use_cases": model_info.get("use_cases", []),
            "advantages": model_info.get("strengths", []),
            "disadvantages": model_info.get("limitations", []),
            "languages": model_info.get("languages", []),
            "github_url": model_info.get("github_url"),
            "website_url": model_info.get("website_url"),
            "logo_url": model_info.get("logo_url"),
            "provider_url": model_info.get("provider_url"),
        }

        # Add papers if available
        if model_info.get("papers"):
            papers = []
            for paper in model_info["papers"]:
                papers.append(
                    {
                        "title": paper.get("title", ""),
                        "authors": paper.get("authors", []),
                        "url": paper.get("url", ""),
                    }
                )
            budconnect_data["papers"] = papers

        # Add architecture if available
        if model_info.get("architecture"):
            arch = model_info["architecture"]
            budconnect_data["architecture"] = {
                "type": arch.get("type"),
                "family": arch.get("family"),
                "num_params": arch.get("num_params"),
                "model_weights_size": arch.get("model_weights_size"),
                "text_config": arch.get("text_config"),
                "vision_config": arch.get("vision_config"),
                "embedding_config": arch.get("embedding_config"),
            }

        # Add model tree if available
        if model_info.get("model_tree"):
            tree = model_info["model_tree"]
            budconnect_data["model_tree"] = {
                "base_model": tree.get("base_model"),
                "is_finetune": tree.get("is_finetune"),
                "is_adapter": tree.get("is_adapter"),
                "is_quantization": tree.get("is_quantization"),
                "is_merge": tree.get("is_merge"),
            }

        # Add evaluations if provided
        if model_evals:
            evaluations = []
            for eval_item in model_evals:
                evaluations.append(
                    {
                        "name": eval_item.get("name", ""),
                        "score": eval_item.get("score", 0),
                        "metric_type": eval_item.get("metric_type", "accuracy"),
                    }
                )
            budconnect_data["evaluations"] = evaluations

        # Add license information if available
        if model_info.get("license"):
            license_data = model_info["license"]
            budconnect_data["license"] = {
                "id": license_data.get("id"),
                "license_id": license_data.get("license_id"),
                "name": license_data.get("name"),
                "url": license_data.get("url"),
                "type": license_data.get("type"),
                "description": license_data.get("description"),
                "suitability": license_data.get("suitability"),
            }

        # Add source type (e.g., "huggingface")
        budconnect_data["source_type"] = "huggingface"

        return budconnect_data

    @staticmethod
    def map_to_model_info(cloud_data: Dict[str, Any]) -> Dict[str, Any]:
        """Map BudConnect model response to ModelInfo schema format.

        Args:
            cloud_data: Raw model data from BudConnect API.

        Returns:
            Dictionary formatted for ModelInfo schema.

        Raises:
            ModelExtractionException: If mapping fails.
        """
        try:
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
                    papers.append(
                        {
                            "title": paper.get("title", ""),
                            "authors": paper.get("authors", []),
                            "url": paper.get("url", ""),
                        }
                    )
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
                    "embedding_config": arch.get("embedding_config"),
                }

            # Map model tree/derivatives if available
            if cloud_data.get("model_tree"):
                tree = cloud_data["model_tree"]
                model_info_data["model_tree"] = {
                    "base_model": tree.get("base_model"),
                    "is_finetune": tree.get("is_finetune"),
                    "is_adapter": tree.get("is_adapter"),
                    "is_quantization": tree.get("is_quantization"),
                    "is_merge": tree.get("is_merge"),
                }

            return model_info_data

        except Exception as e:
            logger.exception("Error mapping BudConnect data to ModelInfo: %s", str(e))
            raise ModelExtractionException(f"Failed to map cloud model data: {str(e)}") from e

    @staticmethod
    def extract_evaluation_data(cloud_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract evaluation/benchmark data from BudConnect model response.

        Args:
            cloud_data: Raw model data from BudConnect API.

        Returns:
            List of formatted evaluation data dictionaries.
        """
        evaluations = cloud_data.get("evaluations", [])
        formatted_evals = []

        for eval_item in evaluations:
            formatted_evals.append(
                {
                    "name": eval_item.get("name", ""),
                    "score": eval_item.get("score", 0),
                    "metric_type": "accuracy",  # Default metric type
                }
            )

        return formatted_evals

    @staticmethod
    def map_provider_data(provider_data: Dict[str, Any]) -> Dict[str, Any]:
        """Map BudConnect provider data to internal provider schema.

        Args:
            provider_data: Raw provider data from BudConnect API.

        Returns:
            Dictionary formatted for Provider schema.
        """
        return {
            "name": provider_data.get("name"),
            "description": provider_data.get("description"),
            "type": provider_data.get("provider_type"),
            "icon": provider_data.get("icon"),
            "capabilities": provider_data.get("capabilities", {}),
            "credentials": provider_data.get("credentials", []),
        }

    @staticmethod
    def map_cloud_model_data(cloud_model: Dict[str, Any], provider_id: str) -> Dict[str, Any]:
        """Map BudConnect cloud model data to internal CloudModel schema.

        Args:
            cloud_model: Raw cloud model data from BudConnect API.
            provider_id: ID of the provider this model belongs to.

        Returns:
            Dictionary formatted for CloudModel schema.
        """
        max_input_tokens = cloud_model["tokens"].get("max_input_tokens") if cloud_model.get("tokens") else None
        max_output_tokens = cloud_model["tokens"].get("max_output_tokens") if cloud_model.get("tokens") else None

        return {
            "uri": cloud_model["uri"],
            "engine": cloud_model.get("engine"),
            "deployment_name": cloud_model.get("deployment_name"),
            "provider_id": provider_id,
            "is_default": cloud_model.get("is_default", False),
            "max_input_tokens": max_input_tokens,
            "max_output_tokens": max_output_tokens,
        }
