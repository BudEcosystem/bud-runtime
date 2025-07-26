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

"""The leaderboard services, containing essential data structures for the leaderboard microservice."""

import json
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import List

from budmicroframe.commons import logging
from sqlalchemy import UUID

from budmodel.commons.config import app_settings  # noqa

from ..commons.async_utils import get_param_range
from ..commons.constants import CrawlerType, LeaderboardDataOrigin
from ..commons.exceptions import CrawlerException, SourceParserException
from ..model_info.models import ModelInfoCRUD
from .crud import LeaderboardCRUD, SourceCRUD
from .parser import ModelInfoEnricher, SourceParserFactory
from .schemas import (
    Crawl4aiConfig,
    LeaderboardCreate,
    LeaderboardModelUrisListResponse,
    ModelParamsResponse,
)
from .web_crawler import CrawlerFactory


logger = logging.get_logger(__name__)


class LeaderboardService:
    """Leaderboard service."""

    def __init__(self):
        """Initialize the leaderboard service."""

    async def upsert_leaderboard_from_all_sources(self) -> None:
        """Upsert model info and leaderboard from all sources."""
        # Fetch all active sources
        db_sources, db_sources_count = SourceCRUD().fetch_many(conditions={"is_active": True})
        logger.debug("Found %s active sources", db_sources_count)

        for db_source in db_sources:
            logger.info("Processing source %s", db_source.name)

            # Check if the source should be extracted
            last_extracted_at = db_source.last_extracted_at
            should_extract = last_extracted_at is None or datetime.utcnow().replace(
                tzinfo=timezone.utc
            ) - last_extracted_at >= timedelta(days=7)

            if not should_extract:
                logger.info("Skipping source %s (last extracted at: %s)", db_source.name, last_extracted_at)
                continue
            schema = json.loads(db_source.schema)
            wait_for = db_source.wait_for or ""
            js_code = db_source.js_code or ""
            css_selector = db_source.css_base_selector or ""

            try:
                crawler = CrawlerFactory.get_crawler(CrawlerType.CRAWL4AI, db_source.url)
                extracted_data = await crawler.extract_data(
                    Crawl4aiConfig(
                        schema=schema,
                        wait_for=wait_for,
                        js_code=js_code,
                        css_selector=css_selector,
                    )
                )
                logger.info("Extracted %s data entries from source %s", len(extracted_data), db_source.name)
            except CrawlerException as e:
                logger.error("Error processing source %s: %s", db_source.name, str(e))
                logger.info("Skipping source %s", db_source.name)
                continue
            except Exception as e:
                logger.exception("Error processing source %s: %s", db_source.name, str(e))
                logger.info("Skipping source %s", db_source.name)
                continue

            # parse the extracted data
            try:
                parsed_data = await SourceParserFactory.get_parser(db_source.name).parse_data(extracted_data)
            except (SourceParserException, Exception) as e:
                logger.error("Error parsing source %s: %s", db_source.name, str(e))
                logger.info("Skipping source %s", db_source.name)
                continue
            logger.debug("Parsed %s data entries from source %s", len(parsed_data), db_source.name)

            for parsed_entry in parsed_data:
                model_info = parsed_entry["model_info"]
                leaderboard = parsed_entry["leaderboard"]
                leaderboard_data = leaderboard.model_dump(exclude_none=True, exclude_unset=True)
                provider_type = parsed_entry["provider_type"]

                # Check model info is already exists
                db_model_info = ModelInfoCRUD().fetch_one(conditions={"uri": model_info.uri})

                if db_model_info:
                    # Try to enrich, Enricher will handle completion state scenario
                    enricher = ModelInfoEnricher(provider_type)
                    enriched_info, was_enriched, enriched_model_evals = await enricher.enrich_model_info(
                        model_info, db_model_info.extraction_status
                    )

                    # Update only if enrichment occurred
                    if was_enriched:
                        model_info_data = enriched_info.model_dump(exclude="license")
                        _ = ModelInfoCRUD().update(data=model_info_data, conditions={"id": db_model_info.id})
                        logger.debug(
                            "Model info updated for uri %s with extraction status %s",
                            model_info.uri,
                            enriched_info.extraction_status,
                        )
                    else:
                        logger.debug("No enrichment occurred for uri %s, skipping model info update", model_info.uri)

                    # format leaderboard data
                    formatted_scraped_leaderboard_data = LeaderboardService().format_scraped_leaderboard_data(
                        leaderboard_data, db_model_info.id, db_source.id
                    )
                    formatted_llm_leaderboard_data = LeaderboardService().format_llm_leaderboard_data(
                        enriched_model_evals, db_model_info.id
                    )

                    scraped_normalised_eval_names = {
                        item.normalised_eval_name for item in formatted_scraped_leaderboard_data
                    }
                    # Filter llm_read items only if their eval_name is not already in scraped
                    final_leaderboard_data = formatted_scraped_leaderboard_data + [
                        item
                        for item in formatted_llm_leaderboard_data
                        if item.normalised_eval_name not in scraped_normalised_eval_names
                    ]
                    with LeaderboardCRUD() as crud:
                        crud.update_or_insert_leaderboards(db_model_info.id, final_leaderboard_data)
                        logger.debug("Leaderboard data updated/inserted for model %s", db_model_info.uri)
                    # # Check leaderboard exists
                    # for entry in formatted_leaderboard_data:
                    #     conditions = {
                    #         "model_info_id": entry["model_info_id"],
                    #         "eval_name": entry["eval_name"],
                    #     }

                    #     db_existing_leaderboard = LeaderboardCRUD().fetch_one(conditions=conditions)

                    #     if db_existing_leaderboard:
                    #         _ = LeaderboardCRUD().update(data=entry, conditions={"id": db_existing_leaderboard.id})
                    #         logger.debug("Leaderboard updated for id %s (eval: %s)", db_existing_leaderboard.id, entry["eval_name"])
                    #     else:
                    #         _ = LeaderboardCRUD().insert(data=entry)
                    #         logger.debug("Leaderboard created for model_info_id %s (eval: %s)", entry["model_info_id"], entry["eval_name"])
                else:
                    logger.debug("Model info does not exist for uri %s", model_info.uri)

                    # Try to enrich
                    enricher = ModelInfoEnricher(provider_type)
                    enriched_info, was_enriched, enriched_model_evals = await enricher.enrich_model_info(model_info)
                    if enriched_info is not None:
                        model_info_dict = enriched_info.model_dump(exclude={"license"})

                        if enriched_info.license is not None:
                            model_info_dict["license_id"] = enriched_info.license.id

                    # Create new model info
                    try:
                        db_model_info = ModelInfoCRUD().insert(data=model_info_dict)
                        logger.debug(
                            "Model info created for uri %s with extraction status %s",
                            model_info_dict.get("uri"),
                            enriched_info.extraction_status,
                        )
                    except Exception as e:
                        logger.exception("Failed to insert data for uri %s: %s", model_info_dict.get("uri"), str(e))

                    # format leaderboard data
                    formatted_scraped_leaderboard_data = LeaderboardService().format_scraped_leaderboard_data(
                        leaderboard_data, db_model_info.id, db_source.id
                    )
                    formatted_llm_leaderboard_data = LeaderboardService().format_llm_leaderboard_data(
                        enriched_model_evals, db_model_info.id
                    )

                    scraped_normalised_eval_names = {
                        item.normalised_eval_name for item in formatted_scraped_leaderboard_data
                    }
                    # Filter llm_read items only if their eval_name is not already in scraped
                    final_leaderboard_data = formatted_scraped_leaderboard_data + [
                        item
                        for item in formatted_llm_leaderboard_data
                        if item.normalised_eval_name not in scraped_normalised_eval_names
                    ]
                    with LeaderboardCRUD() as crud:
                        crud.update_or_insert_leaderboards(db_model_info.id, final_leaderboard_data)
                        logger.debug("Leaderboard data updated/inserted for model %s", db_model_info.uri)

            # Update the `last_extracted_at` timestamp for the source
            SourceCRUD().update(data={"last_extracted_at": datetime.utcnow()}, conditions={"id": db_source.id})

            logger.info("Upserted leaderboard from source %s", db_source.name)
        logger.info("Upserted leaderboard from all sources")

    @staticmethod
    def format_scraped_leaderboard_data(
        leaderboard_data: dict, model_info_id: UUID, source_id: UUID
    ) -> list[LeaderboardCreate]:
        """Convert old-style leaderboard dictionary to a list of row dicts
        compatible with the new schema.
        """
        formatted_leaderboard_data = []
        for metric_name, score in leaderboard_data.items():
            if score is not None:
                row = LeaderboardCreate(
                    **{
                        "eval_name": LeaderboardService().prettify_eval_name(metric_name),
                        "normalised_eval_name": LeaderboardService().normalize_eval_name(metric_name),
                        "eval_score": score,
                        "model_info_id": model_info_id,
                        "source_id": source_id,
                        "data_origin": LeaderboardDataOrigin.SCRAPED,
                    }
                )
                formatted_leaderboard_data.append(row)
        return formatted_leaderboard_data

    @staticmethod
    def format_llm_leaderboard_data(
        data: List[dict],
        model_info_id: UUID,
    ) -> List[LeaderboardCreate]:
        return [
            LeaderboardCreate(
                eval_name=LeaderboardService().prettify_eval_name(item["name"]),
                normalised_eval_name=LeaderboardService().normalize_eval_name(item["name"]),
                eval_score=item["score"],
                model_info_id=model_info_id,
                data_origin=LeaderboardDataOrigin.README_LLM,
                source_id=None,
            )
            for item in data
        ]

    @staticmethod
    def prettify_eval_name(name: str) -> str:
        """Converts raw LLM name to a display-friendly format:
        - Removes non-alphanumeric characters
        - Replaces separators with a space
        - Capitalizes each word
        """
        name = re.sub(r"[_\-]+", " ", name)  # underscores/dashes → space
        name = re.sub(r"[^\w\s]", "", name)  # remove non-word characters
        return " ".join(word.capitalize() for word in name.split())

    @staticmethod
    def normalize_eval_name(name: str) -> str:
        """Converts name to normalized format:
        - Lowercase
        - Removes all special characters and spaces
        """
        return re.sub(r"[\W_]+", "", name).lower()

    @staticmethod
    def build_leaderboard_result(model_row, current_eval_names, model_benchmarks):
        """Build a single leaderboard entry from raw DB rows."""
        model_scores = model_benchmarks.get(model_row.model_info_id, [])

        existing = {s["eval_name"] for s in model_scores}
        for eval_name in current_eval_names:
            if eval_name not in existing:
                model_scores.append(
                    {
                        "eval_name": eval_name,
                        "eval_score": None,
                        "eval_label": eval_name,
                    }
                )

        # Priority to average_score from db query
        avg_score = getattr(model_row, "average_score", None)

        # Calculate average score if it is not present
        if avg_score is None:
            scores_only = [s["eval_score"] for s in model_scores if s["eval_score"] is not None]
            avg_score = sum(scores_only) / len(scores_only) if scores_only else None

        return {
            "model_info": {
                "uri": model_row.uri,
                "num_params": model_row.num_params,
            },
            "benchmarks": model_scores,
            "average_score": avg_score,
        }

    async def get_leaderboard_table(self, model_uri: str, limit: int) -> List[dict]:
        """Get the leaderboard table.

        Args:
            model_uri: The URI of the model to get the leaderboard table for.
            limit: The limit of the number of models to return.

        Returns:
            The leaderboard table.
        """
        # Get model info
        db_model_info = ModelInfoCRUD().fetch_one(conditions={"uri": model_uri})

        if not db_model_info:
            logger.error("Model info not found for uri %s", model_uri)
            return []

        # Fetch leaderboard for respective model info
        current_leaderboard, _ = LeaderboardCRUD().fetch_many(conditions={"model_info_id": db_model_info.id})

        if not current_leaderboard:
            logger.warning("No leaderboard found for uri %s", model_uri)
            return []

        # Get model size in million of parameters
        model_architecture = db_model_info.architecture or {}
        num_params = model_architecture.get("num_params")
        if not num_params or not isinstance(num_params, int):
            logger.error("Model architecture not found for uri %s", model_uri)
            result = await self._parse_single_leaderboard_result(db_model_info, current_leaderboard)
            return [result]

        # Get parameter range for leaderboard query
        min_num_params, max_num_params = await get_param_range(num_params)

        # Update limit to exclude current leaderboard count
        limit = limit - 1

        # Fetch raw leaderboard data
        benchmarks, current_eval_names, top_models = LeaderboardCRUD().get_leaderboard_with_current_model(
            db_model_info.id, min_num_params, max_num_params, limit
        )

        if not benchmarks:
            return []

        model_benchmarks = defaultdict(list)
        for row in benchmarks:
            model_benchmarks[row.model_info_id].append(
                {
                    "eval_name": row.normalised_eval_name,
                    "eval_score": row.eval_score,
                    "eval_label": row.eval_name,
                }
            )

        current_row = SimpleNamespace(
            model_info_id=db_model_info.id,
            uri=db_model_info.uri,
            num_params=num_params,
        )

        results = [self.build_leaderboard_result(current_row, current_eval_names, model_benchmarks)]

        for row in top_models:
            results.append(self.build_leaderboard_result(row, current_eval_names, model_benchmarks))

        return results

    @staticmethod
    async def _parse_single_leaderboard_result(db_model_info, leaderboard_entries) -> dict:
        """Parse database results into LeaderboardResponse schema."""
        model_architecture = db_model_info.architecture or {}
        num_params = model_architecture.get("num_params")
        model_info = ModelParamsResponse(uri=db_model_info.uri, num_params=num_params).model_dump()

        result = {
            "model_info": model_info,
        }
        benchmarks = []
        for entry in leaderboard_entries:
            if entry.eval_score is not None:
                benchmarks.append(
                    {
                        "eval_name": entry.normalised_eval_name,
                        "eval_score": entry.eval_score,
                        "eval_label": entry.eval_name,
                    }
                )
        result["benchmarks"] = benchmarks
        return result if len(benchmarks) > 0 else {}

    async def get_leaderboards_by_models(
        self, model_uris: List[str], benchmark_fields: List[str], limit: int
    ) -> List[dict]:
        """Get the leaderboards for the given model URIs.

        Args:
            model_uris: The URIs of the models to get the leaderboards for.
            limit: The limit of the number of models to return.

        Returns:
            The leaderboards for the given model URIs.
        """
        # Fetch leaderboards by models
        db_leaderboards = LeaderboardCRUD().get_leaderboards_by_models(model_uris, benchmark_fields, limit)

        return db_leaderboards

    async def get_model_evals_by_uris(self, model_uris: List[str]) -> LeaderboardModelUrisListResponse:
        """Get the leaderboards for the given model URIs.

        Args:
            model_uris: The URIs of the models to get the leaderboards for.
            limit: The limit of the number of models to return.

        Returns:
            The leaderboards for the given model URIs.
        """
        # Fetch leaderboards by models
        db_leaderboards = LeaderboardCRUD().get_model_evals_by_uris(model_uris)
        # Group by model uri
        model_map = {}
        for uri, eval_name, normalised_eval_name, eval_score in db_leaderboards:
            if uri not in model_map:
                model_map[uri] = {"uri": uri, "benchmarks": []}
            model_map[uri]["benchmarks"].append(
                {
                    "eval_label": eval_name,
                    "eval_score": eval_score,
                    "eval_name": normalised_eval_name,
                }
            )
        return model_map.values()


if __name__ == "__main__":
    import asyncio

    leaderboard_service = LeaderboardService()
    asyncio.run(leaderboard_service.upsert_leaderboard_from_all_sources())
#     model_evals=[
#     {
#       "name": "MMLU",
#       "score": 45.4
#     },
#     {
#       "name": "BBH",
#       "score": 8.4
#     },
#     {
#       "name": "HellaSwag",
#       "score": 49.3
#     },
#     {
#       "name": "Winogrande",
#       "score": 56.8
#     },
#     {
#       "name": "ARC-C",
#       "score": 31.5
#     },
#     {
#       "name": "TruthfulQA",
#       "score": 39.7
#     },
#     {
#       "name": "win_rate",
#       "score": 58.2
#     },
#     {
#       "name": "lc_win_rate",
#       "score": 5
#     }
#   ]
#     leaderboard_data= LeaderboardService().format_llm_leaderboard_data(model_evals, uuid.UUID("88da5a26-b666-4dd1-94b0-39a82cbe76b0"))
#     with LeaderboardCRUD() as crud:
#         crud.update_or_insert_leaderboards(uuid.UUID("88da5a26-b666-4dd1-94b0-39a82cbe76b0"), leaderboard_data)
#         logger.debug("Leaderboard data inserted for model")
# Command to run leaderboard scraper
# xvfb-run python3 -m budmodel.leaderboard.services
