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

from typing import Dict, List, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from budapp.commons.exceptions import BadRequestException, ForbiddenException, NotFoundException
from budapp.guardrails import crud
from budapp.commons.constants import GuardrailProviderEnum
from budapp.guardrails.models import GuardrailDeployment
from budapp.guardrails.schemas import (
    GuardrailDeploymentCreate,
    GuardrailDeploymentListRequestSchema,
    GuardrailDeploymentResponse,
    GuardrailDeploymentRuleConfigResponse,
    GuardrailDeploymentUpdate,
    GuardrailGuardTypeResponse,
    GuardrailModalityTypeResponse,
    GuardrailProbeCreate,
    GuardrailProbeListRequestSchema,
    GuardrailProbeResponse,
    GuardrailProbeUpdate,
    GuardrailRuleCreate,
    GuardrailRuleResponse,
    GuardrailRuleUpdate,
    GuardrailScannerTypeResponse,
)


class GuardrailProbeService:
    """Service for guardrail probe operations."""

    @staticmethod
    def _format_probe_response(probe) -> GuardrailProbeResponse:
        """Convert probe model to response format."""
        return GuardrailProbeResponse(
            id=probe.id,
            name=probe.name,
            description=probe.description,
            tags=probe.tags,
            provider_id=probe.provider_id,
            provider=probe.provider,
            is_custom=probe.is_custom,
            created_by=probe.created_by,
            user_id=probe.user_id,
            project_id=probe.project_id,
            created_at=probe.created_at,
            updated_at=probe.updated_at,
            rules=[GuardrailRuleService._format_rule_response(rule) for rule in probe.rules] if probe.rules else [],
        )

    @staticmethod
    async def create_probe(
        db: AsyncSession, probe_data: GuardrailProbeCreate, user_id: UUID
    ) -> GuardrailProbeResponse:
        """Create a new guardrail probe."""
        # Get provider to check if it's custom
        provider = await crud.get_provider(db, probe_data.provider_id)
        if not provider:
            raise NotFoundException("Provider not found")

        # Only allow creating probes for custom providers
        if provider.provider_type != GuardrailProviderEnum.CUSTOM:
            raise ForbiddenException("Can only create probes for custom providers")

        probe = await crud.create_probe(db, probe_data, user_id)
        # Reload with rules
        probe = await crud.get_probe(db, probe.id)
        return GuardrailProbeService._format_probe_response(probe)

    @staticmethod
    async def get_probe(db: AsyncSession, probe_id: UUID, user_id: UUID) -> GuardrailProbeResponse:
        """Get a probe by ID."""
        probe = await crud.get_probe(db, probe_id)
        if not probe:
            raise NotFoundException("Probe not found")

        # Check access permissions
        if probe.is_custom and probe.user_id != user_id:
            raise ForbiddenException("Access denied to this probe")

        return GuardrailProbeService._format_probe_response(probe)

    @staticmethod
    async def get_probes(
        db: AsyncSession, filters: GuardrailProbeListRequestSchema, user_id: UUID
    ) -> Tuple[List[GuardrailProbeResponse], int]:
        """Get probes with filtering and pagination."""
        probes, total = await crud.get_probes(db, filters, user_id)
        probe_responses = [GuardrailProbeResponse.model_validate(probe) for probe in probes]
        return probe_responses, total

    @staticmethod
    async def update_probe(
        db: AsyncSession, probe_id: UUID, probe_data: GuardrailProbeUpdate, user_id: UUID
    ) -> GuardrailProbeResponse:
        """Update a probe."""
        probe = await crud.update_probe(db, probe_id, probe_data, user_id)
        if not probe:
            raise NotFoundException("Probe not found or access denied")

        # Reload with rules
        probe = await crud.get_probe(db, probe_id)
        return GuardrailProbeService._format_probe_response(probe)

    @staticmethod
    async def delete_probe(db: AsyncSession, probe_id: UUID, user_id: UUID) -> bool:
        """Delete a probe."""
        success = await crud.delete_probe(db, probe_id, user_id)
        if not success:
            raise NotFoundException("Probe not found or access denied")

        return True

    @staticmethod
    async def search_probe_tags(
        db: AsyncSession, search_term: str, offset: int, limit: int
    ) -> Tuple[List[Dict[str, str]], int]:
        """Search for tags used in guardrail probes."""
        from sqlalchemy import func, select
        from budapp.guardrails.models import GuardrailProbe

        # Subquery to extract individual tags from JSONB array
        subquery = (
            select(func.jsonb_array_elements(GuardrailProbe.tags).label("tag")).where(GuardrailProbe.tags.isnot(None))
        ).subquery()

        # Group by 'name' to ensure only one instance of each tag
        final_query = (
            select(
                func.jsonb_extract_path_text(subquery.c.tag, "name").label("name"),
                func.min(func.jsonb_extract_path_text(subquery.c.tag, "color")).label("color"),
            )
            .where(func.jsonb_extract_path_text(subquery.c.tag, "name").ilike(f"{search_term}%"))
            .group_by("name")
            .order_by("name")
        )

        # Count query
        count_query = select(func.count()).select_from(final_query.subquery())
        count_result = await db.execute(count_query)
        total_count = count_result.scalar() or 0

        # Apply pagination
        final_query = final_query.offset(offset).limit(limit)

        result = await db.execute(final_query)
        tags = [{"name": row.name, "color": row.color} for row in result.all()]

        return tags, total_count


class GuardrailRuleService:
    """Service for guardrail rule operations."""

    @staticmethod
    def _format_rule_response(rule) -> GuardrailRuleResponse:
        """Convert rule model to response format with associated types."""
        return GuardrailRuleResponse(
            id=rule.id,
            probe_id=rule.probe_id,
            name=rule.name,
            description=rule.description,
            scanner_types=[
                GuardrailScannerTypeResponse.model_validate(assoc.scanner_type) for assoc in rule.scanner_associations
            ],
            modality_types=[
                GuardrailModalityTypeResponse.model_validate(assoc.modality_type)
                for assoc in rule.modality_associations
            ],
            guard_types=[
                GuardrailGuardTypeResponse.model_validate(assoc.guard_type) for assoc in rule.guard_type_associations
            ],
            examples=rule.examples,
            configuration=rule.configuration,
            is_enabled=rule.is_enabled,
            is_custom=rule.is_custom,
            created_at=rule.created_at,
            updated_at=rule.updated_at,
        )

    @staticmethod
    async def create_rule(db: AsyncSession, rule_data: GuardrailRuleCreate, user_id: UUID) -> GuardrailRuleResponse:
        """Create a new guardrail rule."""
        # Validate that user owns the probe
        probe = await crud.get_probe(db, rule_data.probe_id)
        if not probe:
            raise NotFoundException("Probe not found")

        if not probe.is_custom or probe.user_id != user_id:
            raise ForbiddenException("Cannot add rules to this probe")

        rule = await crud.create_rule(db, rule_data, user_id)
        # Need to reload with associations
        rule = await crud.get_rule(db, rule.id)
        return GuardrailRuleService._format_rule_response(rule)

    @staticmethod
    async def get_rule(db: AsyncSession, rule_id: UUID, user_id: UUID) -> GuardrailRuleResponse:
        """Get a rule by ID."""
        rule = await crud.get_rule(db, rule_id)
        if not rule:
            raise NotFoundException("Rule not found")

        # Check access permissions via probe
        if rule.probe.is_custom and rule.probe.user_id != user_id:
            raise ForbiddenException("Access denied to this rule")

        return GuardrailRuleService._format_rule_response(rule)

    @staticmethod
    async def update_rule(
        db: AsyncSession, rule_id: UUID, rule_data: GuardrailRuleUpdate, user_id: UUID
    ) -> GuardrailRuleResponse:
        """Update a rule."""
        rule = await crud.get_rule(db, rule_id)
        if not rule:
            raise NotFoundException("Rule not found")

        # Check permissions via probe
        if not rule.probe.is_custom or rule.probe.user_id != user_id:
            raise ForbiddenException("Cannot update this rule")

        updated_rule = await crud.update_rule(db, rule_id, rule_data)
        # Need to reload with associations
        updated_rule = await crud.get_rule(db, rule_id)
        return GuardrailRuleService._format_rule_response(updated_rule)

    @staticmethod
    async def delete_rule(db: AsyncSession, rule_id: UUID, user_id: UUID) -> bool:
        """Delete a rule."""
        rule = await crud.get_rule(db, rule_id)
        if not rule:
            raise NotFoundException("Rule not found")

        # Check permissions via probe
        if not rule.probe.is_custom or rule.probe.user_id != user_id:
            raise ForbiddenException("Cannot delete this rule")

        success = await crud.delete_rule(db, rule_id)
        return success


class GuardrailDeploymentService:
    """Service for guardrail deployment operations."""

    @staticmethod
    async def create_deployment(
        db: AsyncSession, deployment_data: GuardrailDeploymentCreate, user_id: UUID
    ) -> GuardrailDeploymentResponse:
        """Create a new guardrail deployment."""
        # Validate probe access
        await GuardrailDeploymentService._validate_probe_access(db, deployment_data.probes, user_id)

        # Validate deployment configuration
        await GuardrailDeploymentService._validate_deployment_config(deployment_data)

        deployment = await crud.create_deployment(db, deployment_data, user_id)
        return await GuardrailDeploymentService._build_deployment_response(db, deployment)

    @staticmethod
    async def get_deployment(db: AsyncSession, deployment_id: UUID, user_id: UUID) -> GuardrailDeploymentResponse:
        """Get a deployment by ID."""
        deployment = await crud.get_deployment(db, deployment_id)
        if not deployment or deployment.user_id != user_id:
            raise NotFoundException("Deployment not found")

        return await GuardrailDeploymentService._build_deployment_response(db, deployment)

    @staticmethod
    async def get_deployments(
        db: AsyncSession, filters: GuardrailDeploymentListRequestSchema, user_id: UUID
    ) -> Tuple[List[Dict], int]:
        """Get deployments with filtering and pagination."""
        deployments, total = await crud.get_deployments(db, filters, user_id)

        # Build list response with counts
        deployment_list = []
        for deployment in deployments:
            probe_count = len(deployment.probe_associations)
            enabled_probe_count = len([p for p in deployment.probe_associations if p.is_enabled])

            deployment_list.append(
                {
                    "id": deployment.id,
                    "name": deployment.name,
                    "deployment_type": deployment.deployment_type,
                    "endpoint_id": deployment.endpoint_id,
                    "status": deployment.status,
                    "probe_count": probe_count,
                    "enabled_probe_count": enabled_probe_count,
                    "created_at": deployment.created_at,
                }
            )

        return deployment_list, total

    @staticmethod
    async def update_deployment(
        db: AsyncSession, deployment_id: UUID, deployment_data: GuardrailDeploymentUpdate, user_id: UUID
    ) -> GuardrailDeploymentResponse:
        """Update a deployment."""
        # Validate probe access if probes are being updated
        if deployment_data.probes is not None:
            await GuardrailDeploymentService._validate_probe_access(db, deployment_data.probes, user_id)

        deployment = await crud.update_deployment(db, deployment_id, deployment_data, user_id)
        if not deployment:
            raise NotFoundException("Deployment not found")

        return await GuardrailDeploymentService._build_deployment_response(db, deployment)

    @staticmethod
    async def delete_deployment(db: AsyncSession, deployment_id: UUID, user_id: UUID) -> bool:
        """Delete a deployment."""
        success = await crud.delete_deployment(db, deployment_id, user_id)
        if not success:
            raise NotFoundException("Deployment not found")

        return True

    @staticmethod
    async def get_deployments_by_endpoint(
        db: AsyncSession, endpoint_id: UUID, user_id: UUID
    ) -> List[GuardrailDeploymentResponse]:
        """Get all active deployments for an endpoint."""
        deployments = await crud.get_deployments_by_endpoint(db, endpoint_id, user_id)

        responses = []
        for deployment in deployments:
            response = await GuardrailDeploymentService._build_deployment_response(db, deployment)
            responses.append(response)

        return responses

    @staticmethod
    async def get_deployments_by_project(
        db: AsyncSession, project_id: UUID, user_id: UUID
    ) -> List[GuardrailDeploymentResponse]:
        """Get all active deployments for a project."""
        deployments = await crud.get_deployments_by_project(db, project_id, user_id)

        responses = []
        for deployment in deployments:
            response = await GuardrailDeploymentService._build_deployment_response(db, deployment)
            responses.append(response)

        return responses

    @staticmethod
    async def _validate_probe_access(db: AsyncSession, probe_configs: List, user_id: UUID) -> None:
        """Validate that user has access to all probes in the deployment."""
        for probe_config in probe_configs:
            probe = await crud.get_probe(db, probe_config.probe_id)
            if not probe:
                raise BadRequestException(f"Probe {probe_config.probe_id} not found")

            # Check access permissions
            if probe.is_custom and probe.user_id != user_id:
                raise ForbiddenException(f"Access denied to probe {probe.name}")

    @staticmethod
    async def _validate_deployment_config(deployment_data: GuardrailDeploymentCreate) -> None:
        """Validate deployment configuration."""
        # Validate execution order uniqueness
        execution_orders = [probe.execution_order for probe in deployment_data.probes]
        if len(execution_orders) != len(set(execution_orders)):
            raise BadRequestException("Probe execution orders must be unique")

        # Validate probe uniqueness
        probe_ids = [probe.probe_id for probe in deployment_data.probes]
        if len(probe_ids) != len(set(probe_ids)):
            raise BadRequestException("Each probe can only be added once per deployment")

    @staticmethod
    async def _build_deployment_response(
        db: AsyncSession, deployment: GuardrailDeployment
    ) -> GuardrailDeploymentResponse:
        """Build a complete deployment response with enriched data."""
        # Get all rules for the probes to build effective configurations
        probe_responses = []

        for deployment_probe in deployment.probe_associations:
            probe = deployment_probe.probe

            # Get all rules for the probe
            all_rules = await crud.get_rules_by_probe(db, probe.id)

            # Build rule configurations with effective settings
            rule_responses = []
            for rule in all_rules:
                # Find override configuration if exists
                override_config = None
                for rule_config in deployment_probe.rule_configs:
                    if rule_config.rule_id == rule.id:
                        override_config = rule_config
                        break

                # Build effective configuration
                effective_config = rule.configuration or {}
                is_enabled = rule.is_enabled
                is_overridden = False
                threshold_override = None

                if override_config:
                    is_enabled = override_config.is_enabled
                    is_overridden = True
                    threshold_override = override_config.threshold_override

                    # Merge configurations
                    if override_config.configuration:
                        effective_config = {**effective_config, **override_config.configuration}

                rule_response = GuardrailDeploymentRuleConfigResponse(
                    id=override_config.id if override_config else rule.id,
                    deployment_probe_id=deployment_probe.id,
                    rule_id=rule.id,
                    rule_name=rule.name,
                    is_enabled=is_enabled,
                    is_overridden=is_overridden,
                    configuration=override_config.configuration if override_config else None,
                    threshold_override=threshold_override,
                    effective_configuration=effective_config,
                    created_at=override_config.created_at if override_config else rule.created_at,
                    updated_at=override_config.updated_at if override_config else rule.updated_at,
                )
                rule_responses.append(rule_response)

            # Build probe response
            from budapp.guardrails.schemas import GuardrailDeploymentProbeResponse

            probe_response = GuardrailDeploymentProbeResponse(
                id=deployment_probe.id,
                deployment_id=deployment_probe.deployment_id,
                probe_id=deployment_probe.probe_id,
                probe_name=probe.name,
                execution_order=deployment_probe.execution_order,
                is_enabled=deployment_probe.is_enabled,
                configuration=deployment_probe.configuration,
                rules=rule_responses,
                created_at=deployment_probe.created_at,
                updated_at=deployment_probe.updated_at,
            )
            probe_responses.append(probe_response)

        # Sort probes by execution order
        probe_responses.sort(key=lambda p: p.execution_order)

        return GuardrailDeploymentResponse(
            id=deployment.id,
            name=deployment.name,
            description=deployment.description,
            deployment_type=deployment.deployment_type,
            endpoint_id=deployment.endpoint_id,
            deployment_endpoint_url=deployment.deployment_endpoint_url,
            status=deployment.status,
            configuration=deployment.configuration,
            user_id=deployment.user_id,
            project_id=deployment.project_id,
            probes=probe_responses,
            created_at=deployment.created_at,
            updated_at=deployment.updated_at,
        )
