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

"""The model ops scheduler. Contains business logic for model ops."""

import json
from typing import Dict, List

import aiohttp
from budmicroframe.commons import logging
from sqlalchemy.orm import Session

from budapp.initializers.provider_seeder import PROVIDERS_SEEDER_FILE_PATH

from ..commons.config import app_settings
from ..commons.constants import ModelEndpointEnum
from ..commons.database import engine
from ..endpoint_ops.crud import EndpointDataManager
from ..endpoint_ops.services import EndpointService
from ..model_ops.crud import CloudModelDataManager, ModelDataManager, ProviderDataManager
from ..model_ops.models import CloudModel as CloudModelModel
from ..model_ops.models import Provider as ProviderModel
from ..model_ops.schemas import CloudModelCreate, ProviderCreate


logger = logging.get_logger(__name__)


class CloudModelSyncScheduler:
    """Schedule cloud model db with cloud service."""

    @staticmethod
    async def get_latest_compatible_models() -> List[Dict]:
        """Get the latest compatible models from the cloud service.

        Returns:
            List[Dict]: List of compatible models.
        """
        PAGE_LIMIT = 5
        api_endpoint = f"{app_settings.bud_connect_base_url}model/get-compatible-models"
        params = {
            "limit": PAGE_LIMIT,
            # "engine": app_settings.cloud_model_seeder_engine,
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
                        cloud_providers = response_data.get("items", [])
                        logger.debug("Found %s providers on page %s", len(cloud_providers), page)
                        data.extend(cloud_providers)

            # Make sure models are not None, Checking OpenApi in budconnect gives non null models
            final_data = []
            for provider in data:
                for model in provider["models"]:
                    if model is None:
                        provider["models"].remove(model)
                final_data.append(provider)

            return final_data
        except Exception as e:
            logger.error("Error getting latest compatible models: %s", e)
            return []

    async def sync_data(self):
        """Sync the data from the cloud service."""
        providers = await self.get_latest_compatible_models()
        logger.debug("Found %s providers from cloud service", len(providers))

        if not providers:
            logger.error("No providers found from cloud service")
            return

        # Set is_active to False for previous version of providers
        provider_types = [provider["provider_type"] for provider in providers]
        logger.debug("Provider types: %s", provider_types)

        # Update is_active to False for previous version of providers, then upsert new providers
        provider_type_id_mapper = {}
        with Session(engine) as session:
            await ProviderDataManager(session).soft_delete_non_supported_providers(provider_types)
            logger.debug("Soft deleted non-supported providers")

            for provider in providers:
                provider_data = ProviderCreate(
                    name=provider["name"],
                    description=provider["description"],
                    type=provider["provider_type"],
                    icon=provider["icon"],
                    capabilities=provider["capabilities"],
                ).model_dump()
                db_provider = await ProviderDataManager(session).upsert_one(ProviderModel, provider_data, ["type"])
                provider_type_id_mapper[provider["provider_type"]] = str(db_provider.id)
                logger.debug("Upserted provider: %s", db_provider.id)

        # Save to json file by following earlier implementation
        # NOTE: this json is used in proprietary/credentials/provider-info api
        # TODO: Move this implementation to db
        providers_data = {}
        for provider in providers:
            providers_data[provider["provider_type"]] = {
                "name": provider["name"],
                "type": provider["provider_type"],
                "description": provider["description"],
                "icon": provider["icon"],
                "credentials": provider["credentials"],
                "capabilities": provider["capabilities"],
            }
        with open(PROVIDERS_SEEDER_FILE_PATH, "w") as f:
            json.dump(providers_data, f, indent=4)
        logger.debug("Saved providers to %s", PROVIDERS_SEEDER_FILE_PATH)

        # Get all valid endpoint values from the enum
        valid_endpoint_values = {endpoint.value for endpoint in ModelEndpointEnum}

        # Get all cloud model uris
        cloud_model_uris = []
        cloud_model_data = []
        for provider in providers:
            cloud_models = provider["models"]
            for cloud_model in cloud_models:
                cloud_model_uris.append(cloud_model["uri"])
                max_input_tokens = (
                    cloud_model["tokens"].get("max_input_tokens", None) if cloud_model["tokens"] is not None else None
                )

                # Filter out unsupported endpoints from external source
                # Partition endpoints into supported and unsupported
                raw_endpoints = cloud_model.get("endpoints") or []
                supported_endpoints = []
                unsupported_endpoints = []
                for ep in raw_endpoints:
                    if ep in valid_endpoint_values:
                        supported_endpoints.append(ep)
                    else:
                        unsupported_endpoints.append(ep)

                # Log if any endpoints were filtered out
                if unsupported_endpoints:
                    logger.warning(
                        "Filtered out unsupported endpoints for model %s: %s",
                        cloud_model["uri"],
                        unsupported_endpoints,
                    )

                cloud_model_data.append(
                    CloudModelCreate(
                        provider_id=provider_type_id_mapper[provider["provider_type"]],
                        uri=cloud_model["uri"],
                        name=cloud_model["uri"].split("/")[-1],
                        modality=cloud_model["modality"],
                        source=provider["provider_type"],
                        max_input_tokens=max_input_tokens,
                        input_cost=cloud_model["input_cost"],
                        output_cost=cloud_model["output_cost"],
                        supported_endpoints=supported_endpoints,
                        deprecation_date=cloud_model["deprecation_date"],
                    )
                )

        if not cloud_model_data:
            logger.error("No cloud model data found from cloud service")
            return

        # Deprecate, clean up, upsert cloud models, and refresh inference costs — single session
        with Session(engine) as session:
            # Get model ids from model zoo of deprecated cloud models
            deprecated_models = await ModelDataManager(session).get_deprecated_cloud_models(cloud_model_uris)
            deprecated_model_ids = [db_model.id for db_model in deprecated_models]
            logger.debug("Found %s deprecated cloud models", deprecated_model_ids)

            # Mark endpoints as deprecated
            await EndpointDataManager(session).mark_as_deprecated(deprecated_model_ids)
            logger.debug("Marked endpoints as deprecated")

            # Remove deprecated cloud models
            await CloudModelDataManager(session).remove_non_supported_cloud_models(cloud_model_uris)
            logger.debug("Removed non-supported cloud models")

            # Upsert new cloud models
            for cloud_model in cloud_model_data:
                await CloudModelDataManager(session).upsert_one(CloudModelModel, cloud_model.model_dump(), ["uri"])
                logger.debug("Upserted cloud model: %s", cloud_model)
            logger.debug("Upserted %s cloud models", len(cloud_model_data))

            # Refresh inference costs on active endpoints affected by the sync
            synced_uris = {cm.uri for cm in cloud_model_data}
            if synced_uris:
                checked = 0
                updated = 0
                endpoints = await EndpointDataManager(session).get_active_endpoints_by_cloud_model_uris(synced_uris)

                endpoint_svc = EndpointService(session)
                for endpoint in endpoints:
                    checked += 1
                    try:
                        new_cost = await endpoint_svc.get_inference_cost(endpoint.id)
                        if new_cost is None:
                            continue

                        if endpoint.inference_cost == new_cost:
                            continue

                        await EndpointDataManager(session).update_by_fields(endpoint, {"inference_cost": new_cost})
                        await endpoint_svc.update_inference_cost_in_proxy_cache(endpoint.id, new_cost)
                        updated += 1
                    except Exception:
                        logger.exception("Failed to refresh inference cost for endpoint %s", endpoint.id)

                logger.debug(
                    "Inference cost refresh complete: checked %d endpoints, updated %d",
                    checked,
                    updated,
                )


if __name__ == "__main__":
    import asyncio

    asyncio.run(CloudModelSyncScheduler().sync_data())

    # python -m budapp.model_ops.scheduler
