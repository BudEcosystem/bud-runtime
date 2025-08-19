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
from budapp.commons.constants import GuardrailProviderEnum
from budapp.commons.database import engine
from budapp.guardrails.models import (
    GuardrailGuardType,
    GuardrailModalityType,
    GuardrailProbe,
    GuardrailProvider,
    GuardrailRule,
    GuardrailRuleGuardType,
    GuardrailRuleModality,
    GuardrailRuleScanner,
    GuardrailScannerType,
)

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

        # Seed in order of dependencies
        await self._seed_modalities(session, data.get("modalities", {}))
        await self._seed_guard_types(session, data.get("guard_type", {}))
        await self._seed_providers_and_scanners(session, data.get("providers", []))

    async def _seed_modalities(self, session: Session, modalities_data: Dict[str, Any]) -> None:
        """Seed modality types."""
        # Get existing modalities
        existing_modalities = session.query(GuardrailModalityType).all()
        existing_names = {m.name for m in existing_modalities}

        for key, modality_info in modalities_data.items():
            if key not in existing_names:
                modality = GuardrailModalityType(
                    id=uuid4(),
                    name=key,
                    display_name=modality_info["name"],
                    description=modality_info["description"],
                )
                session.add(modality)
                logger.info(f"Created modality: {key}")

        session.commit()

    async def _seed_guard_types(self, session: Session, guard_types_data: Dict[str, Any]) -> None:
        """Seed guard types."""
        # Get existing guard types
        existing_guard_types = session.query(GuardrailGuardType).all()
        existing_names = {g.name for g in existing_guard_types}

        for key, guard_info in guard_types_data.items():
            if key not in existing_names:
                guard_type = GuardrailGuardType(
                    id=uuid4(),
                    name=key,
                    display_name=guard_info["name"],
                    description=guard_info["description"],
                )
                session.add(guard_type)
                logger.info(f"Created guard type: {key}")

        session.commit()

    async def _seed_providers_and_scanners(self, session: Session, providers_data: list) -> None:
        """Seed providers, scanners, probes, and rules."""
        for provider_data in providers_data:
            # Check if provider exists
            provider_name = provider_data["name"]
            provider = session.query(GuardrailProvider).filter_by(name=provider_name).first()

            if not provider:
                # Create provider
                provider = GuardrailProvider(
                    id=uuid4(),
                    name=provider_name,
                    display_name=provider_name,
                    provider_type=GuardrailProviderEnum.BUD_SENTINEL,
                    description=provider_data.get("description", ""),
                    is_active=True,
                )
                session.add(provider)
                session.flush()  # Flush to get the ID
                logger.info(f"Created provider: {provider_name}")

            # Seed scanners for this provider
            scanners_map = {}
            for scanner_key, scanner_info in provider_data.get("scanners", {}).items():
                scanner = session.query(GuardrailScannerType).filter_by(name=scanner_key).first()
                if not scanner:
                    scanner = GuardrailScannerType(
                        id=uuid4(),
                        name=scanner_key,
                        display_name=scanner_info["name"],
                        description=scanner_info["description"],
                        supported_modalities=["text"],  # From the JSON, all scanners support text
                    )
                    session.add(scanner)
                    session.flush()
                    logger.info(f"Created scanner: {scanner_key}")
                scanners_map[scanner_key] = scanner

            # Seed probes and rules
            for probe_key, probe_info in provider_data.get("probes", {}).items():
                probe = session.query(GuardrailProbe).filter_by(name=probe_key).first()
                if not probe:
                    probe = GuardrailProbe(
                        id=uuid4(),
                        name=probe_key,
                        description=probe_info["description"],
                        provider_id=provider.id,
                        tags=[
                            {"name": "Data Loss Prevention (DLP)", "color": "#1E90FF"}
                        ],
                    )
                    session.add(probe)
                    session.flush()
                    logger.info(f"Created probe: {probe_key}")

                # Seed rules for this probe
                for rule_key, rule_info in probe_info.get("rules", {}).items():
                    rule = session.query(GuardrailRule).filter_by(name=rule_key).first()
                    if not rule:
                        rule = GuardrailRule(
                            id=uuid4(),
                            probe_id=probe.id,
                            name=rule_key,
                            description=rule_info.get("description", rule_info.get("title", "")),
                            examples=rule_info.get("examples", []),
                            is_enabled=True,
                            is_custom=False,
                        )
                        session.add(rule)
                        session.flush()
                        logger.info(f"Created rule: {rule_key}")

                        # Link rule to scanners
                        for scanner_name in rule_info.get("scanners", []):
                            if scanner_name in scanners_map:
                                rule_scanner = GuardrailRuleScanner(
                                    id=uuid4(),
                                    rule_id=rule.id,
                                    scanner_type_id=scanners_map[scanner_name].id,
                                )
                                session.add(rule_scanner)

                        # Link rule to modalities
                        for modality_name in rule_info.get("modalities", []):
                            modality = session.query(GuardrailModalityType).filter_by(name=modality_name).first()
                            if modality:
                                rule_modality = GuardrailRuleModality(
                                    id=uuid4(),
                                    rule_id=rule.id,
                                    modality_type_id=modality.id,
                                )
                                session.add(rule_modality)

                        # For now, link all rules to both input and output guard types
                        for guard_type_name in ["input", "output"]:
                            guard_type = session.query(GuardrailGuardType).filter_by(name=guard_type_name).first()
                            if guard_type:
                                rule_guard_type = GuardrailRuleGuardType(
                                    id=uuid4(),
                                    rule_id=rule.id,
                                    guard_type_id=guard_type.id,
                                )
                                session.add(rule_guard_type)

        session.commit()

    async def _load_seeder_data(self) -> Dict[str, Any]:
        """Load guardrails seeder data from JSON file."""
        try:
            with open(GUARDRAILS_SEEDER_FILE_PATH, "r") as file:
                return json.load(file)
        except FileNotFoundError as e:
            raise FileNotFoundError(f"File not found: {GUARDRAILS_SEEDER_FILE_PATH}") from e
