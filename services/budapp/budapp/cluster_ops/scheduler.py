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

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import List, Optional
from uuid import UUID

import aiohttp
from fastapi import status
from sqlalchemy.orm import Session

from ..commons import logging
from ..commons.config import app_settings
from ..commons.constants import (
    BUD_INTERNAL_WORKFLOW,
    RECOMMENDED_CLUSTER_SCHEDULER_STATE_STORE_KEY,
    ModelProviderTypeEnum,
    ModelStatusEnum,
)
from ..commons.database import engine
from ..commons.exceptions import ClientException
from ..commons.schemas import BudNotificationMetadata
from ..model_ops.crud import ModelDataManager
from ..model_ops.models import Model
from ..shared.dapr_service import DaprService
from .schemas import BudSimulatorRequest


logger = logging.get_logger(__name__)


RECOMMENDED_CLUSTER_SCHEDULER_INTERVAL_HOURS = 24


class RecommendedClusterScheduler:
    """The recommended cluster scheduler. Contains business logic for recommended cluster per model."""

    @staticmethod
    def get_models(session: Session, model_id: Optional[UUID] = None) -> List[Model]:
        """Get the models."""
        if model_id:
            db_model = asyncio.run(
                ModelDataManager(session).retrieve_by_fields(
                    Model, {"id": model_id, "status": ModelStatusEnum.ACTIVE}, missing_ok=True
                )
            )
            if db_model:
                return [db_model]
            else:
                logger.error("Model with id %s not found in database", model_id)
                return []
        else:
            current_time = datetime.now(UTC)
            older_than = current_time - timedelta(hours=RECOMMENDED_CLUSTER_SCHEDULER_INTERVAL_HOURS)
            logger.debug("Getting model cluster recommendation sync older than %s", older_than)
            db_model = asyncio.run(ModelDataManager(session).get_stale_model_recommendation(older_than))
            if db_model:
                return [db_model]
            else:
                logger.debug("No stale model cluster recommendation found in db")
                return []

    def execute_cluster_recommendation(self, model_id: Optional[UUID] = None) -> None:
        """Execute the cluster recommendation."""
        from .workflows import ClusterRecommendedSchedulerWorkflows

        dapr_service = DaprService()
        state_store_key = RECOMMENDED_CLUSTER_SCHEDULER_STATE_STORE_KEY

        # Create default state store if it doesn't exist
        try:
            recommended_cluster_scheduler_state = dapr_service.get_state(
                store_name=app_settings.statestore_name, key=state_store_key
            ).json()
            logger.debug("State store %s already exists", state_store_key)
        except Exception as e:
            logger.error("Failed to get state store %s", e)
            try:
                asyncio.run(
                    dapr_service.save_to_statestore(
                        store_name=app_settings.statestore_name,
                        key=state_store_key,
                        value={},
                    )
                )
                logger.debug("Created default state store %s", state_store_key)
            except Exception as e:
                logger.error("Failed to save state store %s", e)

        with Session(engine) as session:
            db_models = self.get_models(session, model_id)
            logger.debug("Found %s models to execute cluster recommendation", len(db_models))

            if not db_models:
                logger.debug("All models are up to date with recommended clusters")
                return

            total_models = len(db_models)
            remaining_models = total_models
            for db_model in db_models:
                remaining_models -= 1
                logger.debug("Executing cluster recommendation for model %s", db_model.id)

                try:
                    # Create Bud Simulator Request for cloud/local models
                    workflow_id = str(uuid.uuid4())
                    bud_simulator_request = self._build_bud_simulator_request(db_model)
                    bud_simulator_request.notification_metadata = BudNotificationMetadata(
                        workflow_id=workflow_id,
                        name=BUD_INTERNAL_WORKFLOW,
                        subscriber_ids=str(db_model.created_by),
                    )

                    try:
                        response = asyncio.run(self._perform_bud_simulator_request(bud_simulator_request))
                    except ClientException as e:
                        logger.error("Failed to initiate bud simulator workflow %s", workflow_id)
                        raise e

                    if isinstance(response, dict) and "workflow_id" in response:
                        logger.debug("Successfully initiated bud simulator workflow %s", workflow_id)

                        # Get existing workflow details from state store
                        try:
                            recommended_cluster_scheduler_state = dapr_service.get_state(
                                store_name=app_settings.statestore_name, key=state_store_key
                            ).json()
                            logger.debug("State store %s already exists", state_store_key)
                        except Exception as e:
                            logger.exception("Failed to get state store %s", e)
                            raise e

                        # Save workflow details in state store
                        recommended_cluster_scheduler_state[str(workflow_id)] = {
                            "model_id": str(db_model.id),
                        }

                        try:
                            dapr_service = DaprService()
                            asyncio.run(
                                dapr_service.save_to_statestore(
                                    store_name=app_settings.statestore_name,
                                    key=state_store_key,
                                    value=recommended_cluster_scheduler_state,
                                )
                            )
                            logger.debug("State store %s updated", state_store_key)
                        except Exception as e:
                            logger.exception("Failed to save state store %s", e)
                            raise e

                        logger.debug("data pushed to dapr state store %s", recommended_cluster_scheduler_state)

                        # Update model recommended cluster sync at
                        db_model = asyncio.run(
                            ModelDataManager(session).update_by_fields(
                                db_model, {"recommended_cluster_sync_at": datetime.now(UTC)}
                            )
                        )
                        logger.debug(
                            "Updated model recommended cluster sync at %s", db_model.recommended_cluster_sync_at
                        )
                    else:
                        logger.error("Failed to initiate bud simulator workflow")
                        raise ClientException("Failed to initiate bud simulator workflow")
                except Exception:
                    logger.error("Error occurred while executing cluster recommendation for model %s", db_model.id)

                    # Update model recommended cluster sync at
                    db_model = asyncio.run(
                        ModelDataManager(session).update_by_fields(
                            db_model, {"recommended_cluster_sync_at": datetime.now(UTC)}
                        )
                    )
                    logger.debug("Updated model recommended cluster sync at %s", db_model.recommended_cluster_sync_at)

                    if remaining_models == 0:
                        # Trigger recommended cluster scheduler workflow
                        asyncio.run(ClusterRecommendedSchedulerWorkflows().__call__())
                        logger.debug("Recommended cluster scheduler workflow re-triggered")

    @staticmethod
    async def _perform_bud_simulator_request(bud_simulator_request: BudSimulatorRequest) -> None:
        """Perform the bud simulator request."""
        bud_simulator_endpoint = (
            f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_simulator_app_id}/method/simulator/run"
        )

        payload = bud_simulator_request.model_dump()

        logger.debug(f"Performing bud simulator request {payload}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(bud_simulator_endpoint, json=payload) as response:
                    response_data = await response.json()
                    if response.status != 200:
                        logger.error(f"Failed to fetch bud simulator response: {response.status} {response_data}")
                        raise ClientException(
                            "Failed to fetch bud simulator response", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                        )

                    logger.debug(f"Successfully fetched bud simulator response{response_data}")
                    return response_data
        except Exception as e:
            logger.exception(f"Failed to send bud simulator request: {e}")
            raise ClientException(
                "Failed to send bud simulator request", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            ) from e

    @staticmethod
    def _build_bud_simulator_request(db_model: Model) -> BudSimulatorRequest:
        """Build the bud simulator request.

        Args:
            db_model (Model): The model to build the bud simulator request for.

        Returns:
            BudSimulatorRequest: The bud simulator request.
        """
        if db_model.provider_type == ModelProviderTypeEnum.CLOUD_MODEL:
            bud_simulator_request = BudSimulatorRequest(
                pretrained_model_uri=db_model.uri,
                model_uri=db_model.uri,  # Cloud models use URI for both
                input_tokens=1024,  # context length
                output_tokens=128,  # sequence length
                concurrency=10,  # concurrent requests
                target_throughput_per_user=0,  # minimum ttft
                target_ttft=0,  # maximum per session tokens/second
                target_e2e_latency=0,  # min e2e latency
                notification_metadata=None,
                source_topic=app_settings.source_topic,
                is_proprietary_model=True,
            )
        else:
            bud_simulator_request = BudSimulatorRequest(
                pretrained_model_uri=db_model.local_path if db_model.local_path else db_model.uri,
                model_uri=db_model.uri,  # Always pass the original URI
                input_tokens=1024,
                output_tokens=128,
                concurrency=10,
                target_throughput_per_user=7,
                target_ttft=1000,
                target_e2e_latency=10,
                notification_metadata=None,
                source_topic=app_settings.source_topic,
                is_proprietary_model=False,
            )

        return bud_simulator_request


if __name__ == "__main__":
    recommended_cluster_scheduler = RecommendedClusterScheduler()
    recommended_cluster_scheduler.execute_cluster_recommendation()

    # python -m budapp.cluster_ops.scheduler
