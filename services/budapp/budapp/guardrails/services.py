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

"""Business logic services for guardrail operations."""

from typing import Any, Optional, Tuple
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from budapp.commons import logging
from budapp.commons.constants import (
    APP_ICONS,
    GuardrailDeploymentStatusEnum,
    GuardrailProviderTypeEnum,
    GuardrailStatusEnum,
    WorkflowTypeEnum,
)
from budapp.commons.db_utils import SessionMixin
from budapp.commons.schemas import ErrorResponse, ProxyGuardrailConfig, SuccessResponse, Tag
from budapp.guardrails import (
    GuardrailsDeploymentDataManager,
    GuardrailsProbeRulesDataManager,
    GuardrailsProfilesDataManager,
)
from budapp.guardrails.models import GuardrailProbes, GuardrailRules
from budapp.guardrails.schemas import (
    GuardrailProbeDetailResponse,
    GuardrailProbeResponse,
    GuardrailRuleDetailResponse,
    GuardrailRuleResponse,
)


class GuardrailProbeRuleService(SessionMixin):
    async def list_probe_tags(self, name: str, offset: int = 0, limit: int = 10) -> tuple[list[Tag], int]:
        """Search probe tags by name with pagination."""
        tags_result, count = await GuardrailsProbeRulesDataManager(self.session).list_probe_tags(name, offset, limit)
        tags = [Tag(name=row.name, color=row.color) for row in tags_result]

        return tags, count

    async def create_probe(
        self,
        name: str,
        provider_id: UUID,
        user_id: UUID,
        status: GuardrailStatusEnum,
        description: Optional[str] = None,
        tags: Optional[list[Tag]] = None,
    ) -> GuardrailProbeDetailResponse:
        """Create a new guardrail probe."""
        # Convert tags to dict format for storage
        tags_data = [{"name": tag.name, "color": tag.color} for tag in tags] if tags else None

        # Create the probe
        db_probe = await GuardrailsProbeRulesDataManager(self.session).create(
            GuardrailProbes,
            name=name,
            provider_id=provider_id,
            created_by=user_id,
            status=status,
            description=description,
            tags=tags_data,
            uri=f"probe_{name.lower().replace(' ', '_')}_{uuid4().hex[:8]}",  # Generate unique URI
            provider_type=GuardrailProviderTypeEnum.BUD,  # Default provider type
        )

        return GuardrailProbeDetailResponse(
            probe=GuardrailProbeResponse.model_validate(db_probe),
            rule_count=0,
            message="Probe created successfully",
            code=status.HTTP_201_CREATED,
        )

    async def edit_probe(
        self,
        probe_id: UUID,
        user_id: Optional[UUID] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[list[Tag]] = None,
        status: Optional[GuardrailStatusEnum] = None,
    ) -> GuardrailProbeDetailResponse:
        """Edit an existing guardrail probe.

        Users can only edit probes they created.
        Preset probes (created_by is None) cannot be edited.
        """
        # Retrieve the probe
        db_probe = await GuardrailsProbeRulesDataManager(self.session).retrieve_by_fields(
            GuardrailProbes, {"id": probe_id}
        )

        # Check if probe is a preset probe (no creator)
        if db_probe.created_by is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Preset probes cannot be edited")

        # Check if user has permission to edit (must be the creator)
        if user_id and db_probe.created_by != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to edit this probe"
            )

        # Prepare update data
        update_data = {}
        if name is not None:
            update_data["name"] = name
        if description is not None:
            update_data["description"] = description
        if tags is not None:
            update_data["tags"] = [{"name": tag.name, "color": tag.color} for tag in tags]
        if status is not None:
            update_data["status"] = status

        # Update the probe
        if update_data:
            await GuardrailsProbeRulesDataManager(self.session).update(
                GuardrailProbes, {"id": probe_id}, **update_data
            )

        # Retrieve updated probe with rule count
        updated_probe = await GuardrailsProbeRulesDataManager(self.session).retrieve_by_fields(
            GuardrailProbes, {"id": probe_id}
        )

        db_rule_count = await GuardrailsProbeRulesDataManager(self.session).get_count_by_fields(
            GuardrailRules, fields={"probe_id": probe_id}, exclude_fields={"status": GuardrailStatusEnum.DELETED}
        )

        return GuardrailProbeDetailResponse(
            probe=GuardrailProbeResponse.model_validate(updated_probe),
            rule_count=db_rule_count,
            message="Probe updated successfully",
            code=status.HTTP_200_OK,
        )

    async def delete_probe(self, probe_id: UUID, user_id: UUID) -> dict:
        """Delete (soft delete) a guardrail probe.

        Users can only delete probes they created.
        Preset probes (created_by is None) cannot be deleted.
        """
        # Retrieve the probe
        db_probe = await GuardrailsProbeRulesDataManager(self.session).retrieve_by_fields(
            GuardrailProbes, {"id": probe_id}
        )

        # Check if probe is a preset probe (no creator)
        if db_probe.created_by is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Preset probes cannot be deleted")

        # Check if user has permission to delete (must be the creator)
        if user_id and db_probe.created_by != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to delete this probe"
            )

        # Soft delete the probe and its rules
        await GuardrailsProbeRulesDataManager(self.session).soft_delete_deprecated_probes([probe_id])

        return SuccessResponse(
            message="Probe deleted successfully", code=status.HTTP_200_OK, object="guardrail.probe.delete"
        )

    async def get_all_probes(
        self,
        offset: int = 0,
        limit: int = 10,
        filters: dict[str, Any] = {},
        order_by: list = [],
        search: bool = False,
    ) -> Tuple[list[GuardrailProbeResponse], int]:
        db_probes, count = await GuardrailsProbeRulesDataManager(self.session).get_all_probes(
            offset, limit, filters, order_by, search
        )

        db_probes_response = [GuardrailProbeResponse.model_validate(db_probe) for db_probe in db_probes]
        return db_probes_response, count

    async def retrieve_probe(self, probe_id: UUID) -> GuardrailProbeDetailResponse:
        db_probe = await GuardrailsProbeRulesDataManager(self.session).retrieve_by_fields(
            GuardrailProbes, {"id": probe_id, "status": GuardrailStatusEnum.ACTIVE}
        )

        db_rule_count = await GuardrailsProbeRulesDataManager(self.session).get_count_by_fields(
            GuardrailRules, fields={"probe_id": probe_id}, exclude_fields={"status": GuardrailStatusEnum.DELETED}
        )

        return GuardrailProbeDetailResponse(
            probe=db_probe,
            rule_count=db_rule_count,
            message="Probe retrieved successfully",
            code=status.HTTP_200_OK,
        )

    async def create_rule(
        self,
        probe_id: UUID,
        name: str,
        user_id: UUID,
        status: GuardrailStatusEnum,
        description: Optional[str] = None,
        tags: Optional[list[Tag]] = None,
        scanner_types: Optional[list[str]] = None,
        modality_types: Optional[list[str]] = None,
        guard_types: Optional[list[str]] = None,
        examples: Optional[list[str]] = None,
    ) -> GuardrailRuleDetailResponse:
        """Create a new guardrail rule for a specific probe."""
        # Verify the probe exists
        await GuardrailsProbeRulesDataManager(self.session).retrieve_by_fields(
            GuardrailProbes, {"id": probe_id, "status": GuardrailStatusEnum.ACTIVE}
        )

        # Convert tags to dict format for storage
        tags_data = [{"name": tag.name, "color": tag.color} for tag in tags] if tags else None

        # Create the rule
        db_rule = await GuardrailsProbeRulesDataManager(self.session).create(
            GuardrailRules,
            probe_id=probe_id,
            name=name,
            created_by=user_id,
            status=status,
            description=description,
            tags=tags_data,
            scanner_types=scanner_types,
            modality_types=modality_types,
            guard_types=guard_types,
            examples=examples,
            uri=f"rule_{name.lower().replace(' ', '_')}_{uuid4().hex[:8]}",  # Generate unique URI
        )

        return GuardrailRuleDetailResponse(
            rule=GuardrailRuleResponse.model_validate(db_rule),
            message="Rule created successfully",
            code=status.HTTP_201_CREATED,
        )

    async def edit_rule(
        self,
        rule_id: UUID,
        user_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[list[Tag]] = None,
        status: Optional[GuardrailStatusEnum] = None,
        scanner_types: Optional[list[str]] = None,
        modality_types: Optional[list[str]] = None,
        guard_types: Optional[list[str]] = None,
        examples: Optional[list[str]] = None,
    ) -> GuardrailRuleDetailResponse:
        """Edit an existing guardrail rule.

        Users can only edit rules they created.
        Preset rules (created_by is None) cannot be edited.
        """
        # Retrieve the rule
        db_rule = await GuardrailsProbeRulesDataManager(self.session).retrieve_by_fields(
            GuardrailRules, {"id": rule_id}
        )

        # Check if rule is a preset rule (no creator)
        if db_rule.created_by is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Preset rules cannot be edited")

        # Check if user has permission to edit (must be the creator)
        if user_id and db_rule.created_by != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to edit this rule"
            )

        # Prepare update data
        update_data = {}
        if name is not None:
            update_data["name"] = name
        if description is not None:
            update_data["description"] = description
        if tags is not None:
            update_data["tags"] = [{"name": tag.name, "color": tag.color} for tag in tags]
        if status is not None:
            update_data["status"] = status
        if scanner_types is not None:
            update_data["scanner_types"] = scanner_types
        if modality_types is not None:
            update_data["modality_types"] = modality_types
        if guard_types is not None:
            update_data["guard_types"] = guard_types
        if examples is not None:
            update_data["examples"] = examples

        # Update the rule
        if update_data:
            await GuardrailsProbeRulesDataManager(self.session).update(GuardrailRules, {"id": rule_id}, **update_data)

        # Retrieve updated rule
        updated_rule = await GuardrailsProbeRulesDataManager(self.session).retrieve_by_fields(
            GuardrailRules, {"id": rule_id}
        )

        return GuardrailRuleDetailResponse(
            rule=GuardrailRuleResponse.model_validate(updated_rule),
            message="Rule updated successfully",
            code=status.HTTP_200_OK,
        )

    async def delete_rule(self, rule_id: UUID, user_id: UUID) -> dict:
        """Delete (soft delete) a guardrail rule.

        Users can only delete rules they created.
        Preset rules (created_by is None) cannot be deleted.
        """
        # Retrieve the rule
        db_rule = await GuardrailsProbeRulesDataManager(self.session).retrieve_by_fields(
            GuardrailRules, {"id": rule_id}
        )

        # Check if rule is a preset rule (no creator)
        if db_rule.created_by is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Preset rules cannot be deleted")

        # Check if user has permission to delete (must be the creator)
        if user_id and db_rule.created_by != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to delete this rule"
            )

        # Soft delete the rule
        await GuardrailsProbeRulesDataManager(self.session).soft_delete_deprecated_rules([rule_id])

        return SuccessResponse(
            message="Rule deleted successfully", code=status.HTTP_200_OK, object="guardrail.rule.delete"
        )

    async def get_all_probe_rules(
        self,
        probe_id: UUID,
        offset: int = 0,
        limit: int = 10,
        filters: dict[str, Any] = {},
        order_by: list = [],
        search: bool = False,
    ) -> Tuple[list[GuardrailRuleResponse], int]:
        """Get all rules for a specific probe."""
        db_rules, count = await GuardrailsProbeRulesDataManager(self.session).get_all_probe_rules(
            probe_id, offset, limit, filters, order_by, search
        )

        db_rules_response = [GuardrailRuleResponse.model_validate(db_rule) for db_rule in db_rules]
        return db_rules_response, count

    async def retrieve_rule(self, rule_id: UUID) -> GuardrailRuleDetailResponse:
        """Retrieve a specific rule by ID."""
        db_rule = await GuardrailsProbeRulesDataManager(self.session).retrieve_by_fields(
            GuardrailRules, {"id": rule_id, "status": GuardrailStatusEnum.ACTIVE}
        )

        return GuardrailRuleDetailResponse(
            rule=db_rule,
            message="Rule retrieved successfully",
            code=status.HTTP_200_OK,
        )


class GuardrailProfileDeploymentService(SessionMixin):
    pass
