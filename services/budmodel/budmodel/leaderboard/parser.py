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

"""The parser for leaderboard module."""

import re
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse

from budmicroframe.commons import logging

from ..commons.async_utils import extract_hf_model_uri
from ..commons.constants import ModelExtractionStatus, SourceType
from ..commons.exceptions import SourceParserException
from ..model_info.exceptions import RepoAccessException
from ..model_info.huggingface import HuggingFaceModelInfo, HuggingfaceUtils
from ..model_info.schemas import LLMConfig, ModelArchitecture, ModelInfoBase
from .base import BaseSourceParser
from .helper import (
    upsert_license_details,
)
from .schemas import LeaderboardBase


logger = logging.get_logger(__name__)


class BaseSourceMixin(BaseSourceParser):
    """Mixin class for leaderboard parser."""

    async def parse_data(self, data: Union[List[Dict[str, Any]], Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parse the data from the source.

        Args:
            data: The data to parse.

        Returns:
            List[Dict[str, Any]]: The parsed data.
        """
        result = []
        for entry in data:
            try:
                parsed_data = await self.parse_entry(entry)
                result.append(parsed_data)
            except Exception as e:
                logger.error("Error parsing entry: %s", str(e))
                continue
        return result


class ChatbotArenaSourceParser(BaseSourceMixin):
    """Chatbot arena leaderboard parser."""

    @staticmethod
    async def parse_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
        """Parse the entry from the source.

        Args:
            entry: The entry to parse.

        Returns:
            Dict[str, Any]: The parsed entry.
        """
        entry["lmsys_areana"] = entry["arena_score"]

        provider_url = None
        website_url = None
        license_details = None

        try:
            if entry["url"].startswith("https://huggingface.co/"):
                uri = await extract_hf_model_uri(entry["url"])
                provider_type = "hugging_face"
                provider_url = entry["url"]
            else:
                uri = entry["name"]
                provider_type = "cloud_model"
                website_url = entry["url"]
                if entry["license"] != "Proprietary":
                    input_license = entry.get("license")
                else:
                    input_license = entry.get("organization")

                license_details = upsert_license_details(input_license)

        except Exception as general_error:
            logger.error(f"Unexpected error while parsing entry: {general_error}")

        model_info = ModelInfoBase(
            uri=uri,
            provider_url=provider_url,
            website_url=website_url,
            author=entry.get("organization"),
            license=license_details,
        )
        leaderboard = LeaderboardBase(**entry)

        return {
            "model_info": model_info,
            "leaderboard": leaderboard,
            "provider_type": provider_type,
        }


class BerkeleySourceParser(BaseSourceMixin):
    """Berkeley leaderboard parser."""

    @staticmethod
    async def parse_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
        """Parse the entry from the source.

        Args:
            entry: The entry to parse.

        Returns:
            Dict[str, Any]: The parsed entry.
        """
        # Convert overall_accuracy to float
        entry["bcfl"] = float(entry["overall_accuracy"])

        # Sanitize the name
        entry["name"] = entry["name"].replace(" (Prompt)", "").replace(" (FC)", "")
        entry["name"] = entry["name"].strip()

        provider_url = None
        website_url = None
        license_details = None

        try:
            if entry["url"].startswith("https://huggingface.co/"):
                uri = await extract_hf_model_uri(entry["url"])
                provider_type = "hugging_face"
                provider_url = entry["url"]
            else:
                uri = entry["name"]
                provider_type = "cloud_model"
                website_url = entry["url"]

                if entry["multi_miss_param"] != "Proprietary":
                    input_license = entry.get("multi_miss_func")
                else:
                    input_license = entry.get("multi_miss_param")

                license_details = upsert_license_details(input_license)

        except Exception as general_error:
            logger.exception(f"Unexpected error while parsing entry: {general_error}")

        model_info = ModelInfoBase(
            uri=uri, provider_url=provider_url, website_url=website_url, license=license_details
        )
        leaderboard = LeaderboardBase(**entry)

        return {
            "model_info": model_info,
            "leaderboard": leaderboard,
            "provider_type": provider_type,
        }


class LiveCodeBenchSourceParser(BaseSourceMixin):
    """LiveCodeBench leaderboard parser."""

    @staticmethod
    async def parse_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
        """Parse the entry from the source.

        Args:
            entry: The entry to parse.

        Returns:
            Dict[str, Any]: The parsed entry.
        """
        # Convert pass_1 to float
        entry["live_code_bench"] = float(entry["pass_1"])

        # Sanitize the name
        pattern = r"\s*\([^)]*\)"
        entry["name"] = re.sub(pattern, "", entry["name"]).strip()

        provider_url = None
        website_url = None

        if entry["url"].startswith("https://huggingface.co/"):
            uri = await extract_hf_model_uri(entry["url"])
            provider_type = "hugging_face"
            provider_url = entry["url"]
        else:
            uri = entry["name"]
            provider_type = "cloud_model"
            website_url = entry["url"]

        model_info = ModelInfoBase(
            uri=uri,
            provider_url=provider_url,
            website_url=website_url,
        )
        leaderboard = LeaderboardBase(**entry)

        return {
            "model_info": model_info,
            "leaderboard": leaderboard,
            "provider_type": provider_type,
        }


class MtebSourceParser(BaseSourceMixin):
    """Mteb leaderboard parser."""

    @staticmethod
    async def parse_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
        """Parse the entry from the source.

        Args:
            entry: The entry to parse.

        Returns:
            Dict[str, Any]: The parsed entry.
        """
        # Convert to float
        entry["classification"] = (
            float(entry["classification_average_12_datasets"])
            if entry["classification_average_12_datasets"] != ""
            else None
        )
        entry["clustering"] = (
            float(entry["clustering_average_11_datasets"]) if entry["clustering_average_11_datasets"] != "" else None
        )
        entry["pair_classification"] = (
            float(entry["pair_classification_average_3_datasets"])
            if entry["pair_classification_average_3_datasets"] != ""
            else None
        )
        entry["reranking"] = (
            float(entry["reranking_average_4_datasets"]) if entry["reranking_average_4_datasets"] != "" else None
        )
        entry["retrieval"] = (
            float(entry["retrieval_average_15_datasets"]) if entry["retrieval_average_15_datasets"] != "" else None
        )
        entry["semantic"] = float(entry["sts_average_10_datasets"]) if entry["sts_average_10_datasets"] != "" else None
        entry["summarization"] = (
            float(entry["summarization_average_1_datasets"])
            if entry["summarization_average_1_datasets"] != ""
            else None
        )

        model_info = ModelInfoBase(
            uri=entry["name"],
        )
        leaderboard = LeaderboardBase(**entry)

        # Since url is not available for mteb leaderboard, consider it as cloud model
        return {
            "model_info": model_info,
            "leaderboard": leaderboard,
            "provider_type": "cloud_model",
        }


class VLLMSourceParser(BaseSourceMixin):
    """VLLM leaderboard parser."""

    @staticmethod
    async def parse_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
        """Parse the entry from the source.

        Args:
            entry: The entry to parse.

        Returns:
            Dict[str, Any]: The parsed entry.
        """
        # Convert to float, int
        entry["mmbench"] = float(entry["mmbench_v11"])
        entry["mmstar"] = float(entry["mmstar"])
        entry["mmmu"] = float(entry["mmmu_val"])
        entry["math_vista"] = float(entry["mathvista"])
        entry["ocr_bench"] = float(entry["ocrbench"])
        entry["ai2d"] = int(entry["ai2d"])
        entry["hallucination_bench"] = float(entry["hallusionbench"])
        entry["mmvet"] = float(entry["mmvet"])

        # Sanitize the name
        pattern = r"\s*\([^)]*\)"
        entry["name"] = re.sub(pattern, "", entry["name"]).strip().replace(" ", "-")

        provider_url = None
        website_url = None

        if entry["url"].startswith("https://huggingface.co/"):
            uri = await extract_hf_model_uri(entry["url"])
            provider_type = "hugging_face"
            provider_url = entry["url"]
        else:
            uri = entry["name"]
            provider_type = "cloud_model"
            website_url = entry["url"]

        model_info = ModelInfoBase(
            uri=uri,
            provider_url=provider_url,
            website_url=website_url,
        )
        leaderboard = LeaderboardBase(**entry)

        return {
            "model_info": model_info,
            "leaderboard": leaderboard,
            "provider_type": provider_type,
        }


class AlpacaSourceParser(BaseSourceMixin):
    """The Alpaca source parser."""

    @staticmethod
    async def parse_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
        """Implementation of required abstract method."""
        return entry

    @staticmethod
    async def parse_data(data: Union[List[Dict[str, Any]], Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parse the data from the source directly.

        Args:
            data: The data to parse.

        Returns:
            List[Dict[str, Any]]: The parsed data.
        """
        import math

        result = []

        for entry in data:
            try:
                parsed_extracted_data = []
                provider_url = None
                website_url = None

                extracted_data = AlpacaSourceParser.parse_alpacasource_csv(entry["url"])

                for data_item in extracted_data:
                    if isinstance(data_item["link"], str) and data_item["link"].startswith("https://huggingface.co/"):
                        try:
                            uri = await extract_hf_model_uri(data_item["link"])
                            provider_type = "hugging_face"
                            provider_url = data_item["link"]
                        except Exception:
                            uri = data_item["name"]
                            provider_type = "hugging_face"
                            provider_url = data_item["link"]
                    else:
                        uri = data_item["name"]
                        provider_type = "cloud_model"
                        if isinstance(data_item["link"], str):
                            website_url = data_item["link"]
                        elif isinstance(data_item["link"], float) and math.isnan(data_item["link"]):
                            website_url = None
                        else:
                            website_url = data_item["link"]

                    model_info = ModelInfoBase(
                        uri=uri,
                        provider_url=provider_url,
                        website_url=website_url,
                    )
                    leaderboard = LeaderboardBase(**data_item)

                    parsed_extracted_data.append(
                        {
                            "model_info": model_info,
                            "leaderboard": leaderboard,
                            "provider_type": provider_type,
                        }
                    )

                result.extend(parsed_extracted_data)
            except Exception as e:
                logger.error("Error parsing entry: %s", str(e))
                continue

        return result

    @staticmethod
    def parse_alpacasource_csv(csv_url):
        """Extracts the alpaca source data from CSV URL."""
        import numpy as np
        import pandas as pd

        df = pd.read_csv(
            csv_url,
            converters={
                "length_controlled_winrate": lambda x: float(x.strip()) if x.strip() else np.nan,
                "win_rate": lambda x: float(x.strip()) if x.strip() else np.nan,
            },
        )

        extracted_data = (
            df[df["filter"].isin(["verified", "minimal"])]
            .assign(
                lc_win_rate=lambda x: x["length_controlled_winrate"].round(2).astype(str),
                win_rate=lambda x: x["win_rate"].round(2).astype(str),
                rank=lambda x: x["win_rate"].rank(ascending=False, method="first").astype("Int64"),
            )[["name", "lc_win_rate", "win_rate", "link", "avg_length", "samples", "rank"]]
            .sort_values("rank")
            .to_dict(orient="records")
        )

        return extracted_data


class UGISourceParser(BaseSourceMixin):
    """The UGI source parser."""

    @staticmethod
    async def parse_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
        """Parses an entry from the UGI source."""
        provider_url = None
        website_url = None

        entry["ugi_score"] = float(entry["UGI_score"])
        entry["w_10_score"] = float(entry["W_10_score"])
        entry["unruly_score"] = float(entry["Unruly"])
        entry["internet_score"] = float(entry["Internet"])
        entry["polcontro_score"] = float(entry["PolContro"])

        if entry["url"].startswith("https://huggingface.co/"):
            uri = await extract_hf_model_uri(entry["url"])
            provider_type = "hugging_face"
            provider_url = entry["url"]
        else:
            uri = entry["name"]
            provider_type = "cloud_model"
            website_url = entry["url"]

        model_info = ModelInfoBase(
            uri=uri,
            provider_url=provider_url,
            website_url=website_url,
        )
        leaderboard = LeaderboardBase(**entry)

        return {
            "model_info": model_info,
            "leaderboard": leaderboard,
            "provider_type": provider_type,
        }


class LLMStatsSourceParser(BaseSourceMixin):
    """The LLM Stats source parser."""

    @staticmethod
    async def parse_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
        """Parses an entry from the UGI source."""
        provider_url = None
        license_details = None
        website_url = None
        architecture = None
        papers = None
        entry["gpqa"] = float(entry["gpqa"].strip("%")) / 100 if entry["gpqa"] != "-" else None
        entry["mmlu"] = float(entry["mmlu"].strip("%")) / 100 if entry["mmlu"] != "-" else None
        entry["mmlu_pro"] = float(entry["mmlu_pro"].strip("%")) / 100 if entry["mmlu_pro"] != "-" else None
        entry["drop"] = float(entry["drop"].strip("%")) / 100 if entry["drop"] != "-" else None
        entry["humaneval"] = float(entry["humaneval"].strip("%")) / 100 if entry["humaneval"] != "-" else None
        entry["num_params"] = (
            int(entry["num_params"])
            if entry["num_params"] and str(entry["num_params"]).lower() not in ["-", "null", "none", ""]
            else None
        )
        entry["max_input_tokens"] = (
            int(entry["max_input_tokens"])
            if entry["max_input_tokens"] and str(entry["max_input_tokens"]).lower() not in ["-", "null", "none", ""]
            else None
        )

        if entry["weights_link"].startswith("https://huggingface.co/") or entry["repo_link"].startswith(
            "https://huggingface.co/"
        ):
            model_link = (
                entry["weights_link"]
                if entry["weights_link"].startswith("https://huggingface.co/")
                else entry["repo_link"]
            )
            model_norm = re.sub(r"[^a-z0-9]", "", entry["model"].lower()) if entry.get("model") else ""
            uri_path = urlparse(model_link).path.lstrip("/")
            uri_norm = re.sub(r"[^a-z0-9]", "", uri_path.lower())

            if model_norm and model_norm in uri_norm:
                uri = uri_path
            else:
                uri = entry["model"]

            provider_type = "hugging_face"
            provider_url = model_link
        else:
            uri = entry["model"]
            provider_type = "cloud_model"
            website_url = entry["repo_link"] if entry["repo_link"] else entry["weights_link"]
            if entry["num_params"] or entry.get("max_input_tokens"):
                architecture = ModelArchitecture(
                    num_params=entry.get("num_params"),
                    text_config=LLMConfig(context_length=entry.get("max_input_tokens")),
                )
        if entry["license"] != "Proprietary":
            input_license = entry.get("license")
        else:
            input_license = entry.get("organization")

        license_details = upsert_license_details(input_license)

        if entry.get("paper_link"):
            papers = HuggingFaceModelInfo.get_publication_info(entry["paper_link"])

        model_info = ModelInfoBase(
            author=entry["organization"],
            description=entry["description"],
            papers=papers,
            license=license_details,
            architecture=architecture,
            uri=uri,
            provider_url=provider_url,
            website_url=website_url,
        )
        leaderboard = LeaderboardBase(**entry)
        return {
            "model_info": model_info,
            "leaderboard": leaderboard,
            "provider_type": provider_type,
        }


class SourceParserFactory:
    """Factory class to create different types of leaderboard parsers."""

    _parsers = {
        SourceType.CHATBOT_ARENA: ChatbotArenaSourceParser,
        SourceType.BERKELEY: BerkeleySourceParser,
        SourceType.LIVE_CODEBENCH: LiveCodeBenchSourceParser,
        SourceType.METB: MtebSourceParser,
        SourceType.VLLM: VLLMSourceParser,
        SourceType.ALPACA: AlpacaSourceParser,
        SourceType.UGI: UGISourceParser,
        SourceType.LLM_STATS: LLMStatsSourceParser,
    }

    @classmethod
    def get_parser(cls, source_name: str) -> BaseSourceMixin:
        """Get a parser instance based on the leaderboard type.

        Args:
            source_type (SourceType): The type of leaderboard to create.

        Returns:
            BaseSourceMixin: An instance of the specified leaderboard type.

        Raises:
            SourceParserException: If the specified leaderboard type is not supported.
        """
        # from leaderboard name to leaderboard type
        try:
            source_type = SourceType(source_name)
        except ValueError as e:
            raise SourceParserException(f"Unsupported leaderboard name: {source_name}") from e

        parser_class = cls._parsers.get(source_type)
        if not parser_class:
            raise SourceParserException(f"Unsupported leaderboard name: {source_name}")

        return parser_class()


class ModelInfoEnricher:
    """The model info enricher which extends the model info with the extracted model info from the provider."""

    SUPPORTED_PROVIDERS = ["hugging_face", "cloud_model"]

    def __init__(self, provider_type: str):
        """Initialize the model info enricher.

        Args:
            provider_type (str): The provider type.

        Raises:
            ValueError: If the provider type is not supported.
        """
        self.provider_type = provider_type
        if provider_type not in self.SUPPORTED_PROVIDERS:
            raise ValueError(f"Provider type {provider_type} is not supported")

    async def enrich_model_info(
        self, model_info: ModelInfoBase, current_extraction_status: Optional[ModelExtractionStatus] = None
    ) -> Tuple[ModelInfoBase, bool, Optional[List[Dict]]]:
        """Enrich the model info with the extracted model info from the provider.

        Args:
            model_info (ModelInfoBase): The model info to enrich.

        Returns:
            Tuple[ModelInfoBase, bool]: (enriched/original model info, was_enriched flag)
        """
        # If model info is already completed, return False to not insert into DB
        if current_extraction_status == ModelExtractionStatus.COMPLETED:
            logger.debug("Model enrichment is already completed for uri %s", model_info.uri)
            return model_info, False, []

        try:
            if self.provider_type == "hugging_face":
                return await self._enrich_hugging_face_model_info(model_info, current_extraction_status)
            elif self.provider_type == "cloud_model":
                model_info, was_enriched = await self._enrich_cloud_model_info(model_info, current_extraction_status)
                return model_info, was_enriched, []
        except Exception as e:
            logger.exception("Error enriching model info: %s", e)
            return model_info, False, []

    async def _enrich_hugging_face_model_info(
        self, model_info: ModelInfoBase, current_extraction_status: Optional[ModelExtractionStatus] = None
    ) -> Tuple[ModelInfoBase, bool, List[Dict]]:
        """Enrich the model info with the extracted model info from the hugging face provider."""
        from ..model_info.services import ModelExtractionService

        # Check the model is public or not
        has_access = False
        try:
            has_access = HuggingfaceUtils.has_access_to_repo(model_info.uri)
        except (RepoAccessException, Exception):
            logger.error("Hf model %s is not public", model_info.uri)
            has_access = False
        logger.debug("Hf model %s has access: %s", model_info.uri, has_access)

        if current_extraction_status == ModelExtractionStatus.PARTIAL and not has_access:
            # If model is already enriched and not public, skip enrichment
            logger.debug("Hf model %s is already enriched and not public. skipping enrichment", model_info.uri)
            return model_info, False, []

        if not current_extraction_status or (
            current_extraction_status == ModelExtractionStatus.PARTIAL and has_access
        ):
            # Either new model or partial extracted model with public access
            try:
                extracted_model_info, model_evals = HuggingFaceModelInfo().from_pretrained(model_info.uri)
                # Fill missing fields in extracted_model_info with available values from model_info.
                extracted_model_info = extracted_model_info.model_copy(
                    update={
                        k: v
                        for k, v in model_info.model_dump(exclude_unset=False).items()
                        if not getattr(extracted_model_info, k, None) and v is not None
                    }
                )

                # is_modality_set = True if extracted_model_info.modality else False
                # # Set extraction status based on the access
                # extracted_model_info.extraction_status = (
                #     ModelExtractionStatus.COMPLETED if has_access and is_modality_set else ModelExtractionStatus.PARTIAL
                # )
                ModelExtractionService.validate_model_extraction(extracted_model_info, model_evals, True)

            except Exception:
                logger.exception("Error extracting model info from Hugging Face for uri %s", model_info.uri)
                model_info.extraction_status = ModelExtractionStatus.PARTIAL
                return model_info, False, []

            model_info = ModelInfoBase.model_validate(extracted_model_info)

            return model_info, True, model_evals

    async def _enrich_cloud_model_info(
        self, model_info: ModelInfoBase, current_extraction_status: Optional[ModelExtractionStatus] = None
    ) -> Tuple[ModelInfoBase, bool]:
        """Enrich the model info with the extracted model info from the cloud model provider."""
        # TODO: implement cloud model enrichment
        if current_extraction_status is None:
            # New model info - set initial status and return True to insert into DB
            model_info.extraction_status = ModelExtractionStatus.PARTIAL
            return model_info, True
        else:
            # Existing model info - return False to not insert into DB
            return model_info, False
