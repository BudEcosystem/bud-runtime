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

from fastapi import HTTPException
from fastapi import status as HTTPStatus
from sqlalchemy import func, select
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
from budapp.guardrails.crud import (
    GuardrailsDeploymentDataManager,
    GuardrailsProbeRulesDataManager,
)
from budapp.guardrails.models import (
    GuardrailProbe,
    GuardrailProfile,
    GuardrailProfileProbe,
    GuardrailProfileRule,
    GuardrailRule,
)
from budapp.guardrails.schemas import (
    GuardrailProbeDetailResponse,
    GuardrailProbeResponse,
    GuardrailProfileDetailResponse,
    GuardrailProfileProbeResponse,
    GuardrailProfileResponse,
    GuardrailProfileRuleResponse,
    GuardrailRuleDetailResponse,
    GuardrailRuleResponse,
)


logger = logging.get_logger(__name__)


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
        provider_type: GuardrailProviderTypeEnum,
        user_id: UUID,
        status: GuardrailStatusEnum,
        description: Optional[str] = None,
        tags: Optional[list[Tag]] = None,
    ) -> GuardrailProbeDetailResponse:
        """Create a new guardrail probe."""
        # Convert tags to dict format for storage
        tags_data = [{"name": tag.name, "color": tag.color} for tag in tags] if tags else None

        # Create the probe
        db_probe = await GuardrailsProbeRulesDataManager(self.session).insert_one(
            GuardrailProbe(
                name=name,
                provider_id=provider_id,
                created_by=user_id,
                status=status,
                description=description,
                tags=tags_data,
                uri=f"probe_{name.lower().replace(' ', '_')}_{uuid4().hex[:8]}",  # Generate unique URI
                provider_type=provider_type,
            )
        )

        return GuardrailProbeDetailResponse(
            probe=GuardrailProbeResponse.model_validate(db_probe),
            rule_count=0,
            message="Probe created successfully",
            code=HTTPStatus.HTTP_201_CREATED,
        )

    async def edit_probe(
        self,
        probe_id: UUID,
        user_id: UUID,
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
            GuardrailProbe, {"id": probe_id}
        )

        # Check if probe is a preset probe (no creator)
        if db_probe.created_by is None:
            raise HTTPException(status_code=HTTPStatus.HTTP_403_FORBIDDEN, detail="Preset probes cannot be edited")

        # Check if user has permission to edit (must be the creator)
        if user_id and db_probe.created_by != user_id:
            raise HTTPException(
                status_code=HTTPStatus.HTTP_403_FORBIDDEN, detail="You do not have permission to edit this probe"
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
            await GuardrailsProbeRulesDataManager(self.session).update_by_fields(db_probe, update_data)
        else:
            updated_probe = db_probe

        # Retrieve updated probe with rule count
        # updated_probe = await GuardrailsProbeRulesDataManager(self.session).retrieve_by_fields(
        #     GuardrailProbe, {"id": probe_id}
        # )

        db_rule_count = await GuardrailsProbeRulesDataManager(self.session).get_count_by_fields(
            GuardrailRule, fields={"probe_id": probe_id}, exclude_fields={"status": GuardrailStatusEnum.DELETED}
        )

        return GuardrailProbeDetailResponse(
            probe=GuardrailProbeResponse.model_validate(updated_probe),
            rule_count=db_rule_count,
            message="Probe updated successfully",
            code=HTTPStatus.HTTP_200_OK,
        )

    async def delete_probe(self, probe_id: UUID, user_id: UUID) -> dict:
        """Delete (soft delete) a guardrail probe.

        Users can only delete probes they created.
        Preset probes (created_by is None) cannot be deleted.
        """
        # Retrieve the probe
        db_probe = await GuardrailsProbeRulesDataManager(self.session).retrieve_by_fields(
            GuardrailProbe, {"id": probe_id}
        )

        # Check if probe is a preset probe (no creator)
        if db_probe.created_by is None:
            raise HTTPException(status_code=HTTPStatus.HTTP_403_FORBIDDEN, detail="Preset probes cannot be deleted")

        # Check if user has permission to delete (must be the creator)
        if user_id and db_probe.created_by != user_id:
            raise HTTPException(
                status_code=HTTPStatus.HTTP_403_FORBIDDEN, detail="You do not have permission to delete this probe"
            )

        # Soft delete the probe and its rules
        await GuardrailsProbeRulesDataManager(self.session).soft_delete_deprecated_probes([probe_id])

        return SuccessResponse(
            message="Probe deleted successfully", code=HTTPStatus.HTTP_200_OK, object="guardrail.probe.delete"
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

        db_probes_response = [GuardrailProbeResponse.model_validate(db_probe[0]) for db_probe in db_probes]
        return db_probes_response, count

    async def retrieve_probe(self, probe_id: UUID) -> GuardrailProbeDetailResponse:
        db_probe = await GuardrailsProbeRulesDataManager(self.session).retrieve_by_fields(
            GuardrailProbe, {"id": probe_id, "status": GuardrailStatusEnum.ACTIVE}
        )

        db_rule_count = await GuardrailsProbeRulesDataManager(self.session).get_count_by_fields(
            GuardrailRule, fields={"probe_id": probe_id}, exclude_fields={"status": GuardrailStatusEnum.DELETED}
        )

        return GuardrailProbeDetailResponse(
            probe=db_probe,
            rule_count=db_rule_count,
            message="Probe retrieved successfully",
            code=HTTPStatus.HTTP_200_OK,
        )

    async def create_rule(
        self,
        probe_id: UUID,
        name: str,
        user_id: UUID,
        status: GuardrailStatusEnum,
        description: Optional[str] = None,
        scanner_types: Optional[list[str]] = None,
        modality_types: Optional[list[str]] = None,
        guard_types: Optional[list[str]] = None,
        examples: Optional[list[str]] = None,
    ) -> GuardrailRuleDetailResponse:
        """Create a new guardrail rule for a specific probe."""
        # Verify the probe exists
        await GuardrailsProbeRulesDataManager(self.session).retrieve_by_fields(
            GuardrailProbe, {"id": probe_id, "status": GuardrailStatusEnum.ACTIVE}
        )

        # Create the rule
        db_rule = await GuardrailsProbeRulesDataManager(self.session).insert_one(
            GuardrailRule(
                probe_id=probe_id,
                name=name,
                created_by=user_id,
                status=status,
                description=description,
                scanner_types=scanner_types,
                modality_types=modality_types,
                guard_types=guard_types,
                examples=examples,
                uri=f"rule_{name.lower().replace(' ', '_')}_{uuid4().hex[:8]}",  # Generate unique URI
            )
        )

        return GuardrailRuleDetailResponse(
            rule=GuardrailRuleResponse.model_validate(db_rule),
            message="Rule created successfully",
            code=HTTPStatus.HTTP_201_CREATED,
        )

    async def edit_rule(
        self,
        rule_id: UUID,
        user_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
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
            GuardrailRule, {"id": rule_id}
        )

        # Check if rule is a preset rule (no creator)
        if db_rule.created_by is None:
            raise HTTPException(status_code=HTTPStatus.HTTP_403_FORBIDDEN, detail="Preset rules cannot be edited")

        # Check if user has permission to edit (must be the creator)
        if user_id and db_rule.created_by != user_id:
            raise HTTPException(
                status_code=HTTPStatus.HTTP_403_FORBIDDEN, detail="You do not have permission to edit this rule"
            )

        # Prepare update data
        update_data = {}
        if name is not None:
            update_data["name"] = name
        if description is not None:
            update_data["description"] = description
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
            updated_rule = await GuardrailsProbeRulesDataManager(self.session).update_by_fields(db_rule, update_data)
        else:
            updated_rule = db_rule

        # Retrieve updated rule
        # updated_rule = await GuardrailsProbeRulesDataManager(self.session).retrieve_by_fields(
        #     GuardrailRule, {"id": rule_id}
        # )

        return GuardrailRuleDetailResponse(
            rule=GuardrailRuleResponse.model_validate(updated_rule),
            message="Rule updated successfully",
            code=HTTPStatus.HTTP_200_OK,
        )

    async def delete_rule(self, rule_id: UUID, user_id: UUID) -> dict:
        """Delete (soft delete) a guardrail rule.

        Users can only delete rules they created.
        Preset rules (created_by is None) cannot be deleted.
        """
        # Retrieve the rule
        db_rule = await GuardrailsProbeRulesDataManager(self.session).retrieve_by_fields(
            GuardrailRule, {"id": rule_id}
        )

        # Check if rule is a preset rule (no creator)
        if db_rule.created_by is None:
            raise HTTPException(status_code=HTTPStatus.HTTP_403_FORBIDDEN, detail="Preset rules cannot be deleted")

        # Check if user has permission to delete (must be the creator)
        if user_id and db_rule.created_by != user_id:
            raise HTTPException(
                status_code=HTTPStatus.HTTP_403_FORBIDDEN, detail="You do not have permission to delete this rule"
            )

        # Soft delete the rule
        await GuardrailsProbeRulesDataManager(self.session).soft_delete_deprecated_rules([rule_id])

        return SuccessResponse(
            message="Rule deleted successfully", code=HTTPStatus.HTTP_200_OK, object="guardrail.rule.delete"
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

        db_rules_response = [GuardrailRuleResponse.model_validate(db_rule[0]) for db_rule in db_rules]
        return db_rules_response, count

    async def retrieve_rule(self, rule_id: UUID) -> GuardrailRuleDetailResponse:
        """Retrieve a specific rule by ID."""
        db_rule = await GuardrailsProbeRulesDataManager(self.session).retrieve_by_fields(
            GuardrailRule, {"id": rule_id, "status": GuardrailStatusEnum.ACTIVE}
        )

        return GuardrailRuleDetailResponse(
            rule=db_rule,
            message="Rule retrieved successfully",
            code=HTTPStatus.HTTP_200_OK,
        )


class GuardrailProfileDeploymentService(SessionMixin):
    async def list_profile_tags(self, name: str, offset: int = 0, limit: int = 10) -> tuple[list[Tag], int]:
        """Search profile tags by name with pagination."""
        tags_result, count = await GuardrailsDeploymentDataManager(self.session).list_profile_tags(name, offset, limit)
        tags = [Tag(name=row.name, color=row.color) for row in tags_result]

        return tags, count

    async def list_active_profiles(
        self,
        offset: int = 0,
        limit: int = 10,
        filters: dict[str, Any] = {},
        order_by: list = [],
        search: bool = False,
    ) -> Tuple[list[GuardrailProfileResponse], int]:
        """List active guardrail profiles with pagination.

        Args:
            offset: Number of records to skip
            limit: Maximum number of records to return
            filters: Dictionary of filters to apply
            order_by: List of fields to order by
            search: Whether to use search filters

        Returns:
            Tuple of list of profiles and total count
        """
        # Add active status filter
        filters["status"] = GuardrailStatusEnum.ACTIVE

        db_profiles, count = await GuardrailsDeploymentDataManager(self.session).get_all_profiles(
            offset, limit, filters, order_by, search
        )

        db_profiles_response = [GuardrailProfileResponse.model_validate(db_profile) for db_profile in db_profiles]
        return db_profiles_response, count

    async def create_profile(
        self,
        name: str,
        user_id: UUID,
        status: GuardrailStatusEnum,
        description: Optional[str] = None,
        tags: Optional[list[Tag]] = None,
        severity_threshold: Optional[float] = None,
        guard_types: Optional[list[str]] = None,
    ) -> GuardrailProfileDetailResponse:
        """Create a new guardrail profile."""
        # Convert tags to dict format for storage
        tags_data = [{"name": tag.name, "color": tag.color} for tag in tags] if tags else None

        # Create the profile
        db_profile = await GuardrailsDeploymentDataManager(self.session).insert_one(
            GuardrailProfile(
                name=name,
                created_by=user_id,
                status=status,
                description=description,
                tags=tags_data,
                severity_threshold=severity_threshold,
                guard_types=guard_types,
            )
        )

        return GuardrailProfileDetailResponse(
            profile=GuardrailProfileResponse.model_validate(db_profile),
            probe_count=0,
            message="Profile created successfully",
            code=HTTPStatus.HTTP_201_CREATED,
        )

    async def edit_profile(
        self,
        profile_id: UUID,
        user_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[list[Tag]] = None,
        status: Optional[GuardrailStatusEnum] = None,
        severity_threshold: Optional[float] = None,
        guard_types: Optional[list[str]] = None,
    ) -> GuardrailProfileDetailResponse:
        """Edit an existing guardrail profile.

        Users can only edit profiles they created.
        Preset profiles (created_by is None) cannot be edited.
        """
        # Retrieve the profile
        db_profile = await GuardrailsDeploymentDataManager(self.session).retrieve_by_fields(
            GuardrailProfile, {"id": profile_id}
        )

        # Check if profile is a preset profile (no creator)
        if db_profile.created_by is None:
            raise HTTPException(status_code=HTTPStatus.HTTP_403_FORBIDDEN, detail="Preset profiles cannot be edited")

        # Check if user has permission to edit (must be the creator)
        if user_id and db_profile.created_by != user_id:
            raise HTTPException(
                status_code=HTTPStatus.HTTP_403_FORBIDDEN, detail="You do not have permission to edit this profile"
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
        if severity_threshold is not None:
            update_data["severity_threshold"] = severity_threshold
        if guard_types is not None:
            update_data["guard_types"] = guard_types

        # Update the profile
        if update_data:
            updated_profile = await GuardrailsDeploymentDataManager(self.session).update_by_fields(
                db_profile, update_data
            )
        else:
            updated_profile = db_profile

        # Retrieve updated profile with probe count
        # updated_profile = await GuardrailsDeploymentDataManager(self.session).retrieve_by_fields(
        #     GuardrailProfile, {"id": profile_id}
        # )

        # Get probe count (enabled probes for this profile)
        db_probe_count = await GuardrailsDeploymentDataManager(self.session).get_count_by_fields(
            GuardrailProfileProbe, fields={"profile_id": profile_id}
        )

        return GuardrailProfileDetailResponse(
            profile=GuardrailProfileResponse.model_validate(updated_profile),
            probe_count=db_probe_count,
            message="Profile updated successfully",
            code=HTTPStatus.HTTP_200_OK,
        )

    async def delete_profile(self, profile_id: UUID, user_id: UUID) -> dict:
        """Delete (soft delete) a guardrail profile.

        Users can only delete profiles they created.
        Preset profiles (created_by is None) cannot be deleted.
        """
        # Retrieve the profile
        db_profile = await GuardrailsDeploymentDataManager(self.session).retrieve_by_fields(
            GuardrailProfile, {"id": profile_id}
        )

        # Check if profile is a preset profile (no creator)
        if db_profile.created_by is None:
            raise HTTPException(status_code=HTTPStatus.HTTP_403_FORBIDDEN, detail="Preset profiles cannot be deleted")

        # Check if user has permission to delete (must be the creator)
        if user_id and db_profile.created_by != user_id:
            raise HTTPException(
                status_code=HTTPStatus.HTTP_403_FORBIDDEN, detail="You do not have permission to delete this profile"
            )

        # Soft delete the profile
        await GuardrailsDeploymentDataManager(self.session).soft_delete_profile(profile_id)

        return SuccessResponse(
            message="Profile deleted successfully", code=HTTPStatus.HTTP_200_OK, object="guardrail.profile.delete"
        )

    async def retrieve_profile(self, profile_id: UUID) -> GuardrailProfileDetailResponse:
        """Retrieve a specific profile by ID."""
        db_profile = await GuardrailsDeploymentDataManager(self.session).retrieve_by_fields(
            GuardrailProfile, {"id": profile_id, "status": GuardrailStatusEnum.ACTIVE}
        )

        db_probe_count = await GuardrailsDeploymentDataManager(self.session).get_count_by_fields(
            GuardrailProfileProbe, fields={"profile_id": profile_id}
        )

        return GuardrailProfileDetailResponse(
            profile=db_profile,
            probe_count=db_probe_count,
            message="Profile retrieved successfully",
            code=HTTPStatus.HTTP_200_OK,
        )

    async def list_profile_probes(
        self,
        profile_id: UUID,
        offset: int = 0,
        limit: int = 10,
        filters: dict[str, Any] = {},
        order_by: list = [],
        search: bool = False,
    ) -> Tuple[list[GuardrailProfileProbeResponse], int]:
        """List probes in a profile with pagination.

        Returns probes that are enabled in the profile with their profile-specific overrides.
        """
        # Use the new CRUD method for efficient join query
        results, count = await GuardrailsDeploymentDataManager(self.session).get_profile_probes(
            profile_id=profile_id,
            offset=offset,
            limit=limit,
            filters=filters,
            order_by=order_by,
            search=search,
        )

        # Build response with profile-specific overrides
        probes_response = []
        for profile_probe, probe in results:
            # Create response combining probe data with profile overrides
            probe_dict = GuardrailProbeResponse.model_validate(probe).model_dump()
            # Override with profile-specific values if they exist
            if profile_probe.severity_threshold is not None:
                probe_dict["severity_threshold"] = profile_probe.severity_threshold
            if profile_probe.guard_types is not None:
                probe_dict["guard_types"] = profile_probe.guard_types

            probes_response.append(GuardrailProfileProbeResponse(**probe_dict))

        return probes_response, count

    async def list_profile_probe_rules(
        self,
        profile_id: UUID,
        probe_id: UUID,
        offset: int = 0,
        limit: int = 10,
        filters: dict[str, Any] = {},
        order_by: list = [],
        search: bool = False,
    ) -> Tuple[list[GuardrailProfileRuleResponse], int]:
        """List enabled rules for a probe in a profile with status override.

        Returns all rules for the probe, but overrides their status based on profile configuration.
        Rules that are disabled in the profile will have status overridden to DISABLED.
        """
        # Use the new CRUD method for efficient join query
        results, count = await GuardrailsDeploymentDataManager(self.session).get_profile_probe_rules(
            profile_id=profile_id,
            probe_id=probe_id,
            offset=offset,
            limit=limit,
            filters=filters,
            order_by=order_by,
            search=search,
        )

        # Handle empty results (probe not enabled in profile)
        if count == 0 and not results:
            return [], 0

        # Build response with status override
        rules_response = []
        for rule, profile_rule in results:
            # Convert to response model
            rule_dict = GuardrailRuleResponse.model_validate(rule).model_dump()

            # Check if this rule has profile-specific overrides
            if profile_rule:
                # Override status to show it's disabled in this profile
                rule_dict["status"] = GuardrailStatusEnum.DISABLED
                # Apply profile-specific overrides
                if profile_rule.severity_threshold is not None:
                    rule_dict["severity_threshold"] = profile_rule.severity_threshold
                if profile_rule.guard_types is not None:
                    rule_dict["guard_types"] = profile_rule.guard_types

            rules_response.append(GuardrailProfileRuleResponse(**rule_dict))

        return rules_response, count
