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

"""The guardrails scheduler. Contains business logic for syncing guardrail probes and rules."""

import hashlib
import json
from typing import Dict, List
from uuid import UUID

import aiohttp
from budmicroframe.commons import logging
from sqlalchemy.orm import Session

from budapp.initializers.provider_seeder import PROVIDERS_SEEDER_FILE_PATH

from ..commons.config import app_settings
from ..commons.constants import GuardrailProviderTypeEnum, GuardrailStatusEnum
from ..commons.database import engine
from ..commons.schemas import Tag
from .crud import GuardrailsProbeRulesDataManager
from .models import GuardrailProbe as GuardrailProbeModel
from .models import GuardrailRule as GuardrailRuleModel
from .schemas import GuardrailProbeCreate, GuardrailRuleCreate


logger = logging.get_logger(__name__)


class GuardrailSyncScheduler:
    """Schedule guardrail probe and rule sync with cloud service."""

    @staticmethod
    def generate_color_from_string(tag_name: str) -> str:
        """Generate a consistent hex color code from a string.

        Args:
            tag_name: The tag name to generate color for.

        Returns:
            str: A hex color code (e.g., #FF0000).
        """
        # Use hash to generate consistent color for each tag name
        hash_object = hashlib.md5(tag_name.encode(), usedforsecurity=False)
        hash_hex = hash_object.hexdigest()

        # Use first 6 characters of hash for color
        color = f"#{hash_hex[:6].upper()}"
        return color

    @staticmethod
    def convert_string_tags_to_tag_objects(tag_strings: List[str]) -> List[Tag]:
        """Convert list of tag strings to list of Tag objects with generated colors.

        Args:
            tag_strings: List of tag name strings.

        Returns:
            List[Tag]: List of Tag objects with names and colors.
        """
        tags = []
        for tag_name in tag_strings:
            if tag_name:  # Skip empty strings
                color = GuardrailSyncScheduler.generate_color_from_string(tag_name)
                tag = Tag(name=tag_name, color=color)
                tags.append(tag)
        return tags

    @staticmethod
    async def get_latest_compatible_guardrails() -> List[Dict]:
        """Get the latest compatible guardrails from the cloud service.

        Returns:
            List[Dict]: List of compatible guardrails with their probes.
        """
        PAGE_LIMIT = 5
        api_endpoint = f"{app_settings.bud_connect_base_url}guardrail/get-compatible-guardrails"
        params = {
            "limit": PAGE_LIMIT,
            "engine": app_settings.cloud_model_seeder_engine,
        }

        try:
            data = []

            async with aiohttp.ClientSession() as session:
                # First request to get total pages
                params["page"] = 1
                async with session.get(api_endpoint, params=params) as response:
                    response_data = await response.json()
                    total_pages = response_data.get("total_pages", 0)
                    logger.debug("Total pages: %s", total_pages)
                    data.extend(response_data.get("items", []))

                # Fetch remaining pages
                for page in range(2, total_pages + 1):
                    params["page"] = page
                    async with session.get(api_endpoint, params=params) as response:
                        response_data = await response.json()
                        guardrail_providers = response_data.get("items", [])
                        logger.debug("Found %s providers on page %s", len(guardrail_providers), page)
                        data.extend(guardrail_providers)

            # Filter out None probes
            final_data = []
            for provider in data:
                if provider.get("probes"):
                    filtered_probes = [probe for probe in provider["probes"] if probe is not None]
                    provider["probes"] = filtered_probes
                final_data.append(provider)

            return final_data
        except Exception as e:
            logger.error("Error getting latest compatible guardrails: %s", e)
            return []

    @staticmethod
    async def get_probe_rules(probe_id: str) -> List[Dict]:
        """Get rules for a specific probe from the cloud service.

        Args:
            probe_id: The probe ID to fetch rules for.

        Returns:
            List[Dict]: List of rules for the probe.
        """
        PAGE_LIMIT = 5
        api_endpoint = f"{app_settings.bud_connect_base_url}guardrail/probes/{probe_id}/rules"
        params = {
            "limit": PAGE_LIMIT,
        }

        try:
            rules = []

            async with aiohttp.ClientSession() as session:
                # First request to get total pages
                params["page"] = 1
                async with session.get(api_endpoint, params=params) as response:
                    response_data = await response.json()
                    total_pages = response_data.get("total_pages", 0)
                    logger.debug("Total pages for probe %s rules: %s", probe_id, total_pages)
                    rules.extend(response_data.get("items", []))

                # Fetch remaining pages
                for page in range(2, total_pages + 1):
                    params["page"] = page
                    async with session.get(api_endpoint, params=params) as response:
                        response_data = await response.json()
                        probe_rules = response_data.get("items", [])
                        logger.debug("Found %s rules on page %s for probe %s", len(probe_rules), page, probe_id)
                        rules.extend(probe_rules)

            return rules
        except Exception as e:
            logger.error("Error getting rules for probe %s: %s", probe_id, e)
            return []

    async def sync_data(self):
        """Sync guardrail probes and rules from the cloud service."""
        providers = await self.get_latest_compatible_guardrails()
        logger.debug("Found %s guardrail providers from cloud service", len(providers))

        if not providers:
            logger.error("No guardrail providers found from cloud service")
            return

        # Collect all probe URIs and data
        probe_uris = []
        probe_data_by_uri = {}
        provider_id_by_type = {}

        # Get or create provider IDs from the Provider table
        with Session(engine) as session:
            from ..model_ops.crud import ProviderDataManager
            from ..model_ops.models import Provider
            from ..model_ops.schemas import ProviderCreate

            for provider in providers:
                provider_type = provider.get("provider_type", "")

                # Create provider data for upsert
                provider_data = ProviderCreate(
                    name=provider.get("name", provider_type),
                    description=provider.get("description", f"Provider for {provider_type}"),
                    type=provider_type,
                    icon=provider.get("icon", ""),
                    capabilities=provider.get("capabilities", []),
                ).model_dump()

                # Upsert provider (create if doesn't exist, update if exists)
                db_provider = await ProviderDataManager(session).upsert_one(Provider, provider_data, ["type"])
                session.commit()

                provider_id_by_type[provider_type] = str(db_provider.id)
                logger.debug("Upserted provider %s with ID %s", provider_type, db_provider.id)

        # Save guardrail providers to json file similar to model_ops scheduler
        # NOTE: this json is used in proprietary/credentials/provider-info api
        providers_data = {}
        with open(PROVIDERS_SEEDER_FILE_PATH, "r") as f:
            providers_data = json.load(f)

        # Update with guardrail providers
        for provider in providers:
            provider_type = provider.get("provider_type", "")
            # Only add if not already present (don't override existing model providers)
            if provider_type not in providers_data:
                providers_data[provider_type] = {
                    "name": provider.get("name", provider_type),
                    "type": provider_type,
                    "description": provider.get("description", f"Provider for {provider_type}"),
                    "icon": provider.get("icon", ""),
                    "credentials": provider.get("credentials", []),
                    "capabilities": provider.get("capabilities", []),
                }

        # Write back to file
        with open(PROVIDERS_SEEDER_FILE_PATH, "w") as f:
            json.dump(providers_data, f, indent=4)
        logger.debug("Updated providers seeder file with guardrail providers")

        # Process probes from each provider
        for provider in providers:
            provider_type = provider.get("provider_type", "")
            provider_id = provider_id_by_type.get(provider_type)

            if not provider_id:
                logger.error("Provider ID not found for type %s after upsert, skipping probes", provider_type)
                continue

            for probe in provider.get("probes", []):
                if not probe:
                    continue

                probe_uri = probe.get("uri", "")
                if not probe_uri:
                    continue

                probe_uris.append(probe_uri)
                probe_data_by_uri[probe_uri] = {
                    "provider_id": provider_id,
                    "provider_type": provider_type,
                    "probe": probe,
                }

        if not probe_uris:
            logger.error("No valid probes found from cloud service")
            return

        # Get existing probe IDs to check which ones are deprecated
        stale_probe_ids = []
        with Session(engine) as session:
            data_manager = GuardrailsProbeRulesDataManager(session)
            # Get all active probes
            existing_probes, _ = await data_manager.get_all_probes(
                offset=0,
                limit=10000,  # Large limit to get all
                filters={"status": GuardrailStatusEnum.ACTIVE, "created_by": None},
            )
            stale_probe_ids = [str(probe[0].id) for probe in existing_probes if probe[0].uri not in probe_uris]
            logger.debug("Found %s existing probes, %s to be deprecated", len(existing_probes), len(stale_probe_ids))

        # Soft delete deprecated probes (this will also soft delete their rules)
        if stale_probe_ids:
            with Session(engine) as session:
                data_manager = GuardrailsProbeRulesDataManager(session)
                await data_manager.soft_delete_deprecated_probes(stale_probe_ids)
                logger.debug("Soft deleted %s deprecated probes", len(stale_probe_ids))

        # Upsert probes and their rules
        for probe_uri, probe_info in probe_data_by_uri.items():
            probe = probe_info["probe"]
            provider_id = probe_info["provider_id"]
            provider_type = (
                GuardrailProviderTypeEnum.BUD
                if probe_info["provider_type"] == "bud_sentinel"
                else GuardrailProviderTypeEnum.CLOUD
            )

            # Convert string tags to Tag objects
            tag_strings = probe.get("tags", [])
            tag_objects = GuardrailSyncScheduler.convert_string_tags_to_tag_objects(tag_strings)

            # Create probe data
            probe_data = GuardrailProbeCreate(
                name=probe.get("name", ""),
                uri=probe_uri,
                description=probe.get("description"),
                icon=probe.get("icon"),
                provider_id=UUID(provider_id),
                provider_type=provider_type,
                status=GuardrailStatusEnum.ACTIVE,
                tags=tag_objects,
            ).model_dump(mode="json", exclude_none=True)

            # Upsert probe
            with Session(engine) as session:
                data_manager = GuardrailsProbeRulesDataManager(session)
                db_probe = await data_manager.upsert_one(GuardrailProbeModel, probe_data, ["uri"])
                session.commit()
                probe_id = str(db_probe.id)
                logger.debug("Upserted probe: %s (ID: %s)", probe_uri, probe_id)

            # Fetch and sync rules for this probe
            rules = await self.get_probe_rules(probe.get("id", ""))
            logger.debug("Found %s rules for probe %s", len(rules), probe_uri)

            if rules:
                # Get rule URIs to identify deprecated rules
                rule_uris = [rule.get("uri", "") for rule in rules if rule.get("uri")]

                # Get existing rules for this probe
                stale_rule_ids = []
                with Session(engine) as session:
                    data_manager = GuardrailsProbeRulesDataManager(session)
                    existing_rules, _ = await data_manager.get_all_probe_rules(
                        probe_id=UUID(probe_id),
                        offset=0,
                        limit=10000,
                        filters={"status": GuardrailStatusEnum.ACTIVE, "created_by": None},
                    )
                    stale_rule_ids = [str(rule[0].id) for rule in existing_rules if rule[0].uri not in rule_uris]
                    logger.debug(
                        "Found %s existing rules for probe %s, %s to be deprecated",
                        len(existing_rules),
                        probe_uri,
                        len(stale_rule_ids),
                    )

                # Soft delete deprecated rules
                if stale_rule_ids:
                    with Session(engine) as session:
                        data_manager = GuardrailsProbeRulesDataManager(session)
                        await data_manager.soft_delete_deprecated_rules(stale_rule_ids)
                        logger.debug("Soft deleted %s deprecated rules for probe %s", len(stale_rule_ids), probe_uri)

                # Upsert rules
                for rule in rules:
                    rule_uri = rule.get("uri", "")
                    if not rule_uri:
                        continue

                    # Log raw rule data from bud connect for debugging
                    logger.debug(
                        "Raw rule from bud connect: scanner_type=%s, model_id=%s, model_provider_type=%s, is_gated=%s",
                        rule.get("scanner_type"),
                        rule.get("model_id"),
                        rule.get("model_provider_type"),
                        rule.get("is_gated"),
                    )

                    rule_data = GuardrailRuleCreate(
                        name=rule.get("name", ""),
                        uri=rule_uri,
                        description=rule.get("description"),
                        icon=rule.get("icon"),
                        probe_id=UUID(probe_id),
                        status=GuardrailStatusEnum.ACTIVE,
                        guard_types=rule.get("guard_types", []),
                        modality_types=rule.get("modality_types", []),
                        examples=rule.get("examples", []),
                        # Model-based rule fields
                        scanner_type=rule.get("scanner_type"),
                        model_uri=rule.get("model_id"),  # bud connect uses model_id for the URI
                        model_provider_type=rule.get("model_provider_type"),
                        is_gated=rule.get("is_gated", False),
                        model_config_json=rule.get("model_config_json"),
                    ).model_dump(mode="json", exclude_none=True)

                    logger.debug("Rule data after model_dump: %s", rule_data)

                    with Session(engine) as session:
                        data_manager = GuardrailsProbeRulesDataManager(session)
                        await data_manager.upsert_one(GuardrailRuleModel, rule_data, ["uri"])
                        session.commit()
                        logger.debug("Upserted rule: %s for probe %s", rule_uri, probe_uri)

        logger.info("Guardrail sync completed successfully")


if __name__ == "__main__":
    import asyncio

    asyncio.run(GuardrailSyncScheduler().sync_data())

    # python -m budapp.guardrails.scheduler
