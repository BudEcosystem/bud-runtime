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

"""Guardrails seeder module."""

import json
import os
from typing import Any, Dict
from uuid import uuid4

from sqlalchemy.orm import Session

from budapp.commons import logging
from budapp.commons.constants import GuardrailProviderTypeEnum
from budapp.commons.database import engine
from budapp.guardrails.models import (
    GuardrailProbe,
    GuardrailRule,
)
from budapp.model_ops.models import Provider

from .base_seeder import BaseSeeder


logger = logging.get_logger(__name__)

# Current file path
CURRENT_FILE_PATH = os.path.dirname(os.path.abspath(__file__))

# Seeder file path
GUARDRAILS_SEEDER_FILE_PATH = os.path.join(CURRENT_FILE_PATH, "data", "guardrails_seeder.json")


class GuardrailsSeeder(BaseSeeder):
    """Seeder for guardrails data."""

    async def seed(self) -> None:
        """Seed guardrails data to the database."""
        with Session(engine) as session:
            try:
                await self._seed_guardrails(session)
            except Exception as e:
                logger.exception(f"Failed to seed guardrails: {e}")

    async def _seed_guardrails(self, session: Session) -> None:
        """Seed all guardrails data."""
        data = await self._load_seeder_data()

        # Seed providers and their probes/rules
        await self._seed_providers_and_probes(session, data)

    async def _seed_providers_and_probes(self, session: Session, providers_data: list) -> None:
        """Seed providers, probes, and rules."""
        # First, ensure the Bud Sentinel provider exists
        for provider_data in providers_data:
            provider = session.query(Provider).filter_by(type=provider_data["provider_type"]).first()
            if not provider:
                logger.error(
                    f"{provider_data['provider_type']} provider not found. Please run the provider seeder first."
                )
                continue

            provider_type = (
                GuardrailProviderTypeEnum.BUD_SENTINEL
                if hasattr(GuardrailProviderTypeEnum, provider_data["provider_type"].upper())
                else GuardrailProviderTypeEnum.CLOUD_PROVIDER
            )

            # Seed probes and rules
            for probe_info in provider_data.get("probes", []):
                probe = session.query(GuardrailProbe).filter_by(sentinel_id=probe_info["id"]).first()
                if not probe:
                    probe = GuardrailProbe(
                        id=uuid4(),
                        sentinel_id=probe_info["id"],
                        name=probe_info["title"],
                        description=probe_info["description"],
                        provider_id=provider.id,
                        provider_type=provider_type,
                        is_custom=False,
                        tags=[{"name": "Data Loss Prevention (DLP)", "color": "#1E90FF"}],
                    )
                    session.add(probe)
                    session.flush()
                    logger.info(f"Created probe: {probe_info['title']}")

                # Seed rules for this probe
                for rule_info in probe_info.get("rules", []):
                    rule = session.query(GuardrailRule).filter_by(sentinel_id=rule_info["id"]).first()
                    if not rule:
                        rule = GuardrailRule(
                            id=uuid4(),
                            probe_id=probe.id,
                            sentinel_id=rule_info["id"],
                            name=rule_info["title"],
                            description=rule_info.get("description", rule_info.get("title", "")),
                            examples=rule_info.get("examples", []),
                            is_enabled=True,
                            is_custom=False,
                            # Set scanner and modality types directly as arrays
                            scanner_types=rule_info.get("scanners", []),
                            modality_types=rule_info.get("modalities", []),
                            guard_types=rule_info.get("guard_types", []),
                        )
                        session.add(rule)
                        session.flush()
                        logger.info(f"Created rule: {rule_info['title']}")

        session.commit()

    async def _load_seeder_data(self) -> Dict[str, Any]:
        """Load guardrails seeder data from JSON file."""
        try:
            with open(GUARDRAILS_SEEDER_FILE_PATH, "r") as file:
                return json.load(file)
        except FileNotFoundError as e:
            raise FileNotFoundError(f"File not found: {GUARDRAILS_SEEDER_FILE_PATH}") from e
