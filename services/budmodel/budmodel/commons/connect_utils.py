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

import contextlib
from typing import Any, Dict, List, Optional

import httpx
from budmicroframe.commons import logging

from .config import app_settings
from .constants import HUGGINGFACE_PROVIDER_ID_FALLBACK, ModelExtractionStatus
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
        # Cache for provider IDs to avoid repeated API calls
        self._provider_cache: Dict[str, str] = {}

    async def fetch_model_details(self, model_uri: str) -> Optional[Dict[str, Any]]:
        """Fetch model details from BudConnect.

        Args:
            model_uri: URI of the model to fetch details for.

        Returns:
            Dictionary containing model details from BudConnect, or None if not found.

        Raises:
            ModelExtractionException: If fetching fails with non-404 error.
        """
        # Try direct details endpoint first
        url = f"{self.base_url}/model/models/{model_uri}/details"
        logger.info("Fetching model details from BudConnect: %s", model_uri)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers={"accept": "application/json"}, timeout=self.timeout)

                if response.status_code == 404:
                    logger.info("Model not found via details endpoint, trying search API: %s", model_uri)
                    return await self._fetch_model_via_search(model_uri)

                response.raise_for_status()
                result = response.json()
                logger.info("Successfully fetched model from BudConnect: %s", model_uri)
                return result
        except httpx.HTTPError as e:
            # If details endpoint fails, try search API as fallback
            logger.warning("Details endpoint failed, trying search API fallback: %s", str(e))
            try:
                return await self._fetch_model_via_search(model_uri)
            except Exception as search_error:
                logger.exception("Both details and search APIs failed: %s", str(search_error))
                raise ModelExtractionException(f"Failed to fetch model details: {str(e)}") from e
        except Exception as e:
            logger.exception("Unexpected error fetching model details from BudConnect: %s", str(e))
            raise ModelExtractionException(f"Unexpected error: {str(e)}") from e

    async def _fetch_model_via_search(self, model_uri: str) -> Optional[Dict[str, Any]]:
        """Fetch model via search API as fallback.

        Args:
            model_uri: URI of the model to search for.

        Returns:
            Dictionary containing model details, or None if not found.
        """
        search_url = f"{self.base_url}/model/?search={model_uri}"

        async with httpx.AsyncClient() as client:
            response = await client.get(search_url, headers={"accept": "application/json"}, timeout=self.timeout)
            response.raise_for_status()
            result = response.json()

            models = result.get("models", [])
            if not models:
                logger.info("Model not found via search API: %s", model_uri)
                return None

            # Find exact match
            for model in models:
                if model.get("uri") == model_uri:
                    logger.info("Found model via search API: %s", model_uri)
                    return model

            logger.info("No exact match found in search results for: %s", model_uri)
            return None

    async def get_provider_id(self, provider_name: str) -> Optional[str]:
        """Fetch provider ID from BudConnect by provider name.

        Args:
            provider_name: Name of the provider (e.g., "Huggingface", "OpenAI").

        Returns:
            Provider ID if found, None otherwise.
        """
        # Check cache first
        cache_key = provider_name.lower()
        if cache_key in self._provider_cache:
            return self._provider_cache[cache_key]

        # Fetch from API
        url = f"{self.base_url}/providers/"
        params = {"search": provider_name}

        logger.info("Fetching provider ID for: %s", provider_name)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url, params=params, headers={"accept": "application/json"}, timeout=self.timeout
                )
                response.raise_for_status()
                result = response.json()

                providers = result.get("providers", [])
                if not providers:
                    logger.warning("No provider found with name: %s", provider_name)
                    return None

                # Find exact match (case-insensitive)
                for provider in providers:
                    if provider.get("name", "").lower() == provider_name.lower():
                        provider_id = provider.get("id")
                        if provider_id:
                            logger.info("Found provider ID for %s: %s", provider_name, provider_id)
                            # Cache the result
                            self._provider_cache[cache_key] = provider_id
                            return provider_id

                # If no exact match, use the first result as fallback
                first_provider = providers[0]
                provider_id = first_provider.get("id")
                if provider_id:
                    logger.warning(
                        "No exact match for provider %s, using first result: %s (ID: %s)",
                        provider_name,
                        first_provider.get("name"),
                        provider_id,
                    )
                    # Cache the result
                    self._provider_cache[cache_key] = provider_id
                    return provider_id

                logger.warning("No valid provider ID found for: %s", provider_name)
                return None

        except httpx.HTTPError as e:
            logger.error("Failed to fetch provider ID for %s: %s", provider_name, str(e))
            return None
        except Exception as e:
            logger.exception("Unexpected error fetching provider ID: %s", str(e))
            return None

    async def save_model_details(self, model_data: Dict[str, Any]) -> Dict[str, Any]:
        """Save model details to BudConnect.

        Args:
            model_data: Dictionary containing model information to save.

        Returns:
            Dictionary containing the response from BudConnect.

        Raises:
            ModelExtractionException: If saving fails.
        """
        url = f"{self.base_url}/model/"
        logger.info("Saving model to BudConnect: %s", model_data.get("uri"))

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json=model_data,
                    headers={"accept": "application/json", "content-type": "application/json"},
                    timeout=self.timeout,
                )

                # Log error response if status is not successful
                if response.status_code >= 400:
                    logger.error("BudConnect API error (status %s): %s", response.status_code, response.text[:500])

                response.raise_for_status()
                result = response.json()
                logger.info("Successfully saved model to BudConnect: %s", model_data.get("uri"))
                return result
        except httpx.HTTPError as e:
            logger.exception("HTTP error saving model details to BudConnect: %s", str(e))
            # Try to log response body if available
            if hasattr(e, "response") and e.response is not None:
                with contextlib.suppress(Exception):
                    logger.error("Error response body: %s", e.response.text)
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

        logger.info("Fetching compatible models from BudConnect (page=%s, limit=%s)", page, limit)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url, params=params, headers={"accept": "application/json"}, timeout=self.timeout
                )

                response.raise_for_status()
                result = response.json()
                return result
        except httpx.HTTPError as e:
            logger.exception("HTTP error fetching compatible models from BudConnect: %s", str(e))
            raise ModelExtractionException(f"Failed to fetch compatible models: {str(e)}") from e
        except Exception as e:
            logger.exception("Unexpected error fetching compatible models from BudConnect: %s", str(e))
            raise ModelExtractionException(f"Unexpected error: {str(e)}") from e


class BudConnectMapper:
    """Maps BudConnect API responses to internal schemas and vice versa."""

    @staticmethod
    async def model_info_to_budconnect(
        model_info: Dict[str, Any],
        model_evals: Optional[List[Dict[str, Any]]] = None,
        client: Optional[BudConnectClient] = None,
    ) -> Dict[str, Any]:
        """Convert ModelInfo to BudConnect format for saving.

        Args:
            model_info: ModelInfo data dictionary.
            model_evals: Optional list of model evaluation data.
            client: Optional BudConnect client for fetching provider IDs.

        Returns:
            Dictionary formatted for BudConnect API.
        """
        # Parse modality string back to list and map to BudConnect enum values
        modality_str = model_info.get("modality", "")
        modality_list = [m.strip() for m in modality_str.split(",")] if modality_str else []

        # Map modality values to BudConnect enum values
        # BudConnect expects: text_input, text_output, image_input, image_output, audio_input, audio_output
        budconnect_modality = []
        for modality in modality_list:
            if modality.lower() in ["llm", "text", "text_input", "text-generation"]:
                # LLMs typically support both text input and output
                if "text_input" not in budconnect_modality:
                    budconnect_modality.append("text_input")
                if "text_output" not in budconnect_modality:
                    budconnect_modality.append("text_output")
            elif modality.lower() in ["vision", "image", "image_input"]:
                if "image_input" not in budconnect_modality:
                    budconnect_modality.append("image_input")
            elif modality.lower() in ["image_output", "image-generation"]:
                if "image_output" not in budconnect_modality:
                    budconnect_modality.append("image_output")
            elif modality.lower() in ["audio", "audio_input", "speech"]:
                if "audio_input" not in budconnect_modality:
                    budconnect_modality.append("audio_input")
            elif modality.lower() in ["audio_output", "tts", "text-to-speech"]:
                if "audio_output" not in budconnect_modality:
                    budconnect_modality.append("audio_output")
            elif modality.lower() in ["speech_to_text", "speech-to-text", "asr"]:
                # Speech-to-text models (e.g., Whisper): audio input, text output
                if "audio_input" not in budconnect_modality:
                    budconnect_modality.append("audio_input")
                if "text_output" not in budconnect_modality:
                    budconnect_modality.append("text_output")
            elif modality.lower() in ["audio_llm", "audio-llm"]:
                # Audio LLM hybrids (e.g., Qwen2-Audio): audio + text input/output
                if "audio_input" not in budconnect_modality:
                    budconnect_modality.append("audio_input")
                if "text_input" not in budconnect_modality:
                    budconnect_modality.append("text_input")
                if "text_output" not in budconnect_modality:
                    budconnect_modality.append("text_output")
            elif modality.lower() == "omni":
                # Omni models (e.g., Qwen2.5-Omni): audio + vision + text
                if "audio_input" not in budconnect_modality:
                    budconnect_modality.append("audio_input")
                if "image_input" not in budconnect_modality:
                    budconnect_modality.append("image_input")
                if "text_input" not in budconnect_modality:
                    budconnect_modality.append("text_input")
                if "text_output" not in budconnect_modality:
                    budconnect_modality.append("text_output")
            elif modality.lower() == "mllm":
                # Multi-modal LLM with vision: image + text input/output
                if "image_input" not in budconnect_modality:
                    budconnect_modality.append("image_input")
                if "text_input" not in budconnect_modality:
                    budconnect_modality.append("text_input")
                if "text_output" not in budconnect_modality:
                    budconnect_modality.append("text_output")
            else:
                # Default to text for unknown modalities
                logger.warning("Unknown modality '%s', defaulting to text_input/text_output", modality)
                if "text_input" not in budconnect_modality:
                    budconnect_modality.append("text_input")
                if "text_output" not in budconnect_modality:
                    budconnect_modality.append("text_output")

        # If no modality mapping succeeded, default to text
        if not budconnect_modality:
            budconnect_modality = ["text_input", "text_output"]

        # Get provider ID dynamically
        provider_id = None
        if client:
            # Try to get provider ID from BudConnect
            provider_name = model_info.get("author", "Huggingface")
            if provider_name.lower() in ["huggingface", "hugging face", "hf"]:
                provider_name = "Huggingface"
            provider_id = await client.get_provider_id(provider_name)

        # Fallback to known provider IDs if API call fails
        if not provider_id:
            # Use the known Huggingface provider ID as fallback
            provider_id = HUGGINGFACE_PROVIDER_ID_FALLBACK
            logger.warning("Using fallback provider ID for Huggingface: %s", provider_id)

        # Map HuggingFace tasks/pipeline_tags to BudConnect API endpoints
        # Based on model capabilities, determine which OpenAI-compatible endpoints it supports
        tasks = model_info.get("tasks", [])
        endpoints = []

        for task in tasks:
            task_lower = task.lower() if isinstance(task, str) else ""

            # Text generation models -> chat completions and/or completions
            if any(
                keyword in task_lower
                for keyword in ["text-generation", "text2text-generation", "conversational", "chat"]
            ):
                if "/v1/chat/completions" not in endpoints:
                    endpoints.append("/v1/chat/completions")
                if "/v1/completions" not in endpoints:
                    endpoints.append("/v1/completions")

            # Image generation models
            elif any(keyword in task_lower for keyword in ["text-to-image", "image-generation"]):
                if "/v1/images/generations" not in endpoints:
                    endpoints.append("/v1/images/generations")

            # Image editing models
            elif "image-to-image" in task_lower or "image-editing" in task_lower:
                if "/v1/images/edits" not in endpoints:
                    endpoints.append("/v1/images/edits")

            # Audio transcription models
            elif "automatic-speech-recognition" in task_lower or "speech-recognition" in task_lower:
                if "/v1/audio/transcriptions" not in endpoints:
                    endpoints.append("/v1/audio/transcriptions")

            # Audio translation models
            elif "audio-translation" in task_lower or "speech-translation" in task_lower:
                if "/v1/audio/translations" not in endpoints:
                    endpoints.append("/v1/audio/translations")

            # Text-to-speech models
            elif "text-to-speech" in task_lower or "tts" in task_lower:
                if "/v1/audio/speech" not in endpoints:
                    endpoints.append("/v1/audio/speech")

            # Embedding models
            elif any(keyword in task_lower for keyword in ["feature-extraction", "sentence-similarity", "embedding"]):
                if "/v1/embeddings" not in endpoints:
                    endpoints.append("/v1/embeddings")

        # If no endpoints were mapped but it's a text model, default to completions
        if not endpoints and budconnect_modality and "text_output" in budconnect_modality:
            endpoints = ["/v1/chat/completions", "/v1/completions"]

        budconnect_data = {
            "uri": model_info.get("uri", ""),
            "provider_id": provider_id,  # Required field - dynamically fetched
            "provider_name": model_info.get("author", "Unknown"),
            "description": model_info.get("description", ""),
            "modality": budconnect_modality,
            "endpoints": endpoints,  # Mapped from tasks to API endpoints
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
            modality_list = cloud_data.get("modality") or []
            modality_str = ", ".join(modality_list) if modality_list else "text_input,text_output"

            model_info_data = {
                "uri": cloud_data.get("uri", ""),
                "author": cloud_data.get("provider_name") or "Unknown",
                "description": cloud_data.get("description") or "",
                "modality": modality_str,
                "tags": cloud_data.get("tags") or [],
                "tasks": cloud_data.get("tasks") or [],
                "use_cases": cloud_data.get("use_cases") or [],
                "strengths": cloud_data.get("advantages") or [],
                "limitations": cloud_data.get("disadvantages") or [],
                "languages": cloud_data.get("languages") or [],
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
        evaluations = cloud_data.get("evaluations") or []
        formatted_evals = []

        for eval_item in evaluations:
            formatted_eval = {
                "name": eval_item.get("name", ""),
                "score": eval_item.get("score", 0),
                "metric_type": "accuracy",  # Default metric type
            }
            formatted_evals.append(formatted_eval)

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
