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

from typing import Dict, List, Optional, Tuple
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from budapp.commons import logging
from budapp.commons.constants import (
    APP_ICONS,
    GuardrailDeploymentStatusEnum,
    GuardrailDeploymentTypeEnum,
    WorkflowTypeEnum,
)
from budapp.commons.db_utils import SessionMixin
from budapp.commons.schemas import ProxyGuardrailConfig
from budapp.guardrails import crud
from budapp.guardrails.models import GuardrailDeployment
from budapp.guardrails.schemas import (
    CreateGuardrailDeploymentWorkflowRequest,
    GuardrailDeploymentCreate,
    GuardrailDeploymentListRequestSchema,
    GuardrailDeploymentProbeCreate,
    GuardrailDeploymentResponse,
    GuardrailDeploymentRuleCreate,
    GuardrailDeploymentRuleResponse,
    GuardrailDeploymentUpdate,
    GuardrailProbeCreate,
    GuardrailProbeListRequestSchema,
    GuardrailProbeListResponse,
    GuardrailProbeResponse,
    GuardrailProbeUpdate,
    GuardrailRuleCreate,
    GuardrailRuleListRequestSchema,
    GuardrailRuleResponse,
    GuardrailRuleUpdate,
    ProbeSelection,
    RuleSelection,
)
from budapp.workflow_ops.crud import WorkflowStepDataManager
from budapp.workflow_ops.models import Workflow as WorkflowModel
from budapp.workflow_ops.schemas import WorkflowUtilCreate
from budapp.workflow_ops.services import WorkflowService, WorkflowStepService


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
            provider_type=probe.provider_type,
            provider=probe.provider,
            is_custom=probe.is_custom,
            created_by=probe.created_by,
            user_id=probe.user_id,
            project_id=probe.project_id,
            created_at=probe.created_at,
            modified_at=probe.modified_at,
            rules=[GuardrailRuleService._format_rule_response(rule) for rule in probe.rules] if probe.rules else [],
        )

    @staticmethod
    async def create_probe(db: Session, probe_data: GuardrailProbeCreate, user_id: UUID) -> GuardrailProbeResponse:
        """Create a new guardrail probe."""
        # Get provider to check if it's custom
        provider = await crud.get_provider(db, probe_data.provider_id)
        if not provider:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")

        probe = await crud.create_probe(db, probe_data, user_id)
        # Reload with rules
        probe = await crud.get_probe(db, probe.id)
        return GuardrailProbeService._format_probe_response(probe)

    @staticmethod
    async def get_probe(
        db: Session, probe_id: UUID, user_id: UUID, include_rules: bool = True
    ) -> GuardrailProbeResponse:
        """Get a probe by ID."""
        probe = await crud.get_probe(db, probe_id)
        if not probe:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Probe not found")

        # Check access permissions
        if probe.is_custom and probe.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this probe")

        response = GuardrailProbeService._format_probe_response(probe)

        # Optionally exclude rules
        if not include_rules:
            response.rules = []

        return response

    @staticmethod
    def _format_probe_list_response(probe) -> GuardrailProbeListResponse:
        """Convert probe model to list response format."""
        return GuardrailProbeListResponse(
            id=probe.id,
            name=probe.name,
            description=probe.description,
            tags=probe.tags,
            provider_id=probe.provider_id,
            provider_name=probe.provider.name if probe.provider else None,
            provider_type=probe.provider_type,
            is_custom=probe.is_custom,
            rule_count=len(probe.rules) if probe.rules else 0,
        )

    @staticmethod
    async def get_probes(
        db: Session, filters: GuardrailProbeListRequestSchema, user_id: UUID, page: int, page_size: int
    ) -> Tuple[List[GuardrailProbeListResponse], int]:
        """Get probes with filtering and pagination."""
        probes, total = await crud.get_probes(db, filters, user_id, page, page_size)
        probe_responses = [GuardrailProbeService._format_probe_list_response(probe) for probe in probes]
        return probe_responses, total

    @staticmethod
    async def update_probe(
        db: Session, probe_id: UUID, probe_data: GuardrailProbeUpdate, user_id: UUID
    ) -> GuardrailProbeResponse:
        """Update a probe."""
        probe = await crud.update_probe(db, probe_id, probe_data, user_id)
        if not probe:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Probe not found or access denied")

        # Reload with rules
        probe = await crud.get_probe(db, probe_id)
        return GuardrailProbeService._format_probe_response(probe)

    @staticmethod
    async def delete_probe(db: Session, probe_id: UUID, user_id: UUID) -> bool:
        """Delete a probe."""
        success = await crud.delete_probe(db, probe_id, user_id)
        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Probe not found or access denied")

        return True

    @staticmethod
    async def search_probe_tags(
        db: Session, search_term: str, offset: int, limit: int
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
        """Convert rule model to response format."""
        return GuardrailRuleResponse(
            id=rule.id,
            probe_id=rule.probe_id,
            name=rule.name,
            description=rule.description,
            scanner_types=rule.scanner_types,
            modality_types=rule.modality_types,
            guard_types=rule.guard_types,
            examples=rule.examples,
            configuration=rule.configuration,
            is_enabled=rule.is_enabled,
            is_custom=rule.is_custom,
            created_at=rule.created_at,
            modified_at=rule.modified_at,
        )

    @staticmethod
    async def create_rule(db: Session, rule_data: GuardrailRuleCreate, user_id: UUID) -> GuardrailRuleResponse:
        """Create a new guardrail rule."""
        # Validate that user owns the probe
        probe = await crud.get_probe(db, rule_data.probe_id)
        if not probe:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Probe not found")

        if not probe.is_custom or probe.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot add rules to this probe")

        rule = await crud.create_rule(db, rule_data, user_id)
        # Need to reload with associations
        rule = await crud.get_rule(db, rule.id)
        return GuardrailRuleService._format_rule_response(rule)

    @staticmethod
    async def get_rule(db: Session, rule_id: UUID, user_id: UUID) -> GuardrailRuleResponse:
        """Get a rule by ID."""
        rule = await crud.get_rule(db, rule_id)
        if not rule:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")

        # Check access permissions via probe
        if rule.probe.is_custom and rule.probe.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this rule")

        return GuardrailRuleService._format_rule_response(rule)

    @staticmethod
    async def update_rule(
        db: Session, rule_id: UUID, rule_data: GuardrailRuleUpdate, user_id: UUID
    ) -> GuardrailRuleResponse:
        """Update a rule."""
        rule = await crud.get_rule(db, rule_id)
        if not rule:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")

        # Check permissions via probe
        if not rule.probe.is_custom or rule.probe.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot update this rule")

        updated_rule = await crud.update_rule(db, rule_id, rule_data)
        # Need to reload with associations
        updated_rule = await crud.get_rule(db, rule_id)
        return GuardrailRuleService._format_rule_response(updated_rule)

    @staticmethod
    async def delete_rule(db: Session, rule_id: UUID, user_id: UUID) -> bool:
        """Delete a rule."""
        rule = await crud.get_rule(db, rule_id)
        if not rule:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")

        # Check permissions via probe
        if not rule.probe.is_custom or rule.probe.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot delete this rule")

        success = await crud.delete_rule(db, rule_id)
        return success

    @staticmethod
    async def get_rules_paginated(
        db: Session, probe_id: UUID, filters: GuardrailRuleListRequestSchema, user_id: UUID, page: int, page_size: int
    ) -> Tuple[List[GuardrailRuleResponse], int]:
        """Get paginated rules for a probe."""
        # First check if probe exists and user has access
        probe = await crud.get_probe(db, probe_id)
        if not probe:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Probe not found")

        # Check access permissions
        if probe.is_custom and probe.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this probe")

        # Get paginated rules
        rules, total = await crud.get_rules_paginated(db, probe_id, filters, page, page_size)
        rule_responses = [GuardrailRuleService._format_rule_response(rule) for rule in rules]

        return rule_responses, total


class GuardrailDeploymentService:
    """Service for guardrail deployment operations."""

    @staticmethod
    async def create_deployment(
        db: Session, deployment_data: GuardrailDeploymentCreate, user_id: UUID
    ) -> GuardrailDeploymentResponse:
        """Create a new guardrail deployment."""
        # Handle new sparse selection format
        probes = []
        if deployment_data.probe_selections is not None:
            # Convert sparse selections to deployment probe configs
            probes = await GuardrailDeploymentService._process_sparse_selections(
                db, deployment_data.probe_selections, user_id
            )

        # Validate probe access
        await GuardrailDeploymentService._validate_probe_access(db, probes, user_id)

        # Validate deployment configuration
        await GuardrailDeploymentService._validate_deployment_config_with_probes(probes)

        # Pass probes separately to crud
        deployment = await crud.create_deployment(db, deployment_data, user_id, probes)

        # Update proxy cache if this is an endpoint deployment
        if deployment.endpoint_id:
            await GuardrailDeploymentService._update_endpoint_proxy_cache(db, deployment.endpoint_id, deployment)

        return await GuardrailDeploymentService._build_deployment_response(db, deployment)

    @staticmethod
    async def get_deployment(db: Session, deployment_id: UUID, user_id: UUID) -> GuardrailDeploymentResponse:
        """Get a deployment by ID."""
        deployment = await crud.get_deployment(db, deployment_id)
        if not deployment or deployment.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found")

        return await GuardrailDeploymentService._build_deployment_response(db, deployment)

    @staticmethod
    async def get_deployments(
        db: Session, filters: GuardrailDeploymentListRequestSchema, user_id: UUID, page: int, page_size: int
    ) -> Tuple[List[Dict], int]:
        """Get deployments with filtering and pagination."""
        deployments, total = await crud.get_deployments(db, filters, user_id, page, page_size)

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
                    "guardrail_types": deployment.guardrail_types,
                    "probe_count": probe_count,
                    "enabled_probe_count": enabled_probe_count,
                    "created_at": deployment.created_at,
                }
            )

        return deployment_list, total

    @staticmethod
    async def update_deployment(
        db: Session, deployment_id: UUID, deployment_data: GuardrailDeploymentUpdate, user_id: UUID
    ) -> GuardrailDeploymentResponse:
        """Update a deployment."""
        # Validate probe access if probes are being updated
        if deployment_data.probes is not None:
            await GuardrailDeploymentService._validate_probe_access(db, deployment_data.probes, user_id)

        deployment = await crud.update_deployment(db, deployment_id, deployment_data, user_id)
        if not deployment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found")

        # Update proxy cache if this is an endpoint deployment
        if deployment.endpoint_id:
            await GuardrailDeploymentService._update_endpoint_proxy_cache(db, deployment.endpoint_id, deployment)

        return await GuardrailDeploymentService._build_deployment_response(db, deployment)

    @staticmethod
    async def delete_deployment(db: Session, deployment_id: UUID, user_id: UUID) -> bool:
        """Delete a deployment."""
        # Get deployment first to capture endpoint_id
        deployment = await crud.get_deployment(db, deployment_id)

        success = await crud.delete_deployment(db, deployment_id, user_id)
        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found")

        # Clear guardrails from proxy cache
        if deployment and deployment.endpoint_id:
            # Update status to deleted first
            deployment.status = GuardrailDeploymentStatusEnum.DELETED
            await GuardrailDeploymentService._update_endpoint_proxy_cache(db, deployment.endpoint_id, deployment)

        return True

    @staticmethod
    async def get_deployments_by_endpoint(
        db: Session, endpoint_id: UUID, user_id: UUID
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
        db: Session, project_id: UUID, user_id: UUID
    ) -> List[GuardrailDeploymentResponse]:
        """Get all active deployments for a project."""
        deployments = await crud.get_deployments_by_project(db, project_id, user_id)

        responses = []
        for deployment in deployments:
            response = await GuardrailDeploymentService._build_deployment_response(db, deployment)
            responses.append(response)

        return responses

    @staticmethod
    async def _process_sparse_selections(
        db: Session, probe_selections: List[ProbeSelection], user_id: UUID
    ) -> List[GuardrailDeploymentProbeCreate]:
        """Process sparse probe selections into deployment probe configs.

        Args:
            probe_selections: List of probe selections (empty = all enabled)
            provider_id: Provider ID to fetch all probes from when selections is empty
            user_id: Current user ID for access control

        Returns:
            List of deployment probe configurations
        """
        deployment_probes = []

        if not probe_selections:
            return []

        # Process explicit selections
        for selection in probe_selections:
            rules = []
            for rule_selection in selection.rule_selections or []:
                rules.append(
                    GuardrailDeploymentRuleCreate(rule_id=rule_selection.rule_id, is_enabled=rule_selection.enabled)
                )

            deployment_probe = GuardrailDeploymentProbeCreate(
                probe_id=selection.probe_id, is_enabled=selection.enabled, rules=rules
            )
            deployment_probes.append(deployment_probe)

        return deployment_probes

    @staticmethod
    async def _validate_probe_access(db: Session, probe_configs: List, user_id: UUID) -> None:
        """Validate that user has access to all probes in the deployment."""
        for probe_config in probe_configs:
            probe = await crud.get_probe(db, probe_config.probe_id)
            if not probe:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=f"Probe {probe_config.probe_id} not found"
                )

            # Check access permissions
            if probe.is_custom and probe.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail=f"Access denied to probe {probe.name}"
                )

    @staticmethod
    async def _validate_deployment_config_with_probes(probes: List[GuardrailDeploymentProbeCreate]) -> None:
        """Validate deployment configuration."""
        # Validate probe uniqueness
        probe_ids = [probe.probe_id for probe in probes]
        if len(probe_ids) != len(set(probe_ids)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Each probe can only be added once per deployment"
            )

    @staticmethod
    async def _build_deployment_response(db: Session, deployment: GuardrailDeployment) -> GuardrailDeploymentResponse:
        """Build a complete deployment response with enriched data."""
        # Get all rules for the probes to build effective configurations
        probe_responses = []

        for deployment_probe in deployment.probe_associations:
            # Build rule configurations with effective settings
            rule_responses = []
            for rule_config in deployment_probe.rule:
                # Find override configuration if exists

                rule_response = GuardrailDeploymentRuleResponse(
                    id=rule_config.id,
                    rule_id=rule_config.rule_id,
                    rule_name=rule_config.rule.name,
                    is_enabled=rule_config.is_enabled,
                    configuration=rule_config.configuration,
                    threshold_override=rule_config.threshold_override,
                )
                rule_responses.append(rule_response)

            # Build probe response
            from budapp.guardrails.schemas import GuardrailDeploymentProbeResponse

            probe_response = GuardrailDeploymentProbeResponse(
                id=deployment_probe.id,
                deployment_id=deployment_probe.deployment_id,
                probe_id=deployment_probe.probe_id,
                probe_name=deployment_probe.probe.name,
                is_enabled=deployment_probe.is_enabled,
                configuration=deployment_probe.configuration,
                threshold_override=deployment_probe.threshold_override,
                rules=rule_responses,
            )
            probe_responses.append(probe_response)

        # No need to sort probes anymore as execution_order is removed

        return GuardrailDeploymentResponse(
            id=deployment.id,
            name=deployment.name,
            description=deployment.description,
            deployment_type=deployment.deployment_type,
            endpoint_id=deployment.endpoint_id,
            status=deployment.status,
            configuration=deployment.configuration,
            default_threshold=deployment.default_threshold,
            guardrail_types=deployment.guardrail_types,
            user_id=deployment.user_id,
            project_id=deployment.project_id,
            probes=probe_responses,
            created_at=deployment.created_at,
            modified_at=deployment.modified_at,
        )

    @staticmethod
    async def _update_endpoint_proxy_cache(db: Session, endpoint_id: UUID, deployment: GuardrailDeployment) -> None:
        """Update the proxy cache for an endpoint with guardrail information."""
        import json

        from budapp.endpoint_ops.services import EndpointService
        from budapp.shared.redis_service import RedisService

        redis_service = RedisService()
        cache_key = f"model_table:{endpoint_id}"

        # Get existing cache data
        try:
            existing_data = await redis_service.get(cache_key)
            if not existing_data:
                logging.get_logger(__name__).warning(f"No cache entry found for endpoint {endpoint_id}")
                return
        except Exception as e:
            logging.get_logger(__name__).error(f"Error getting cache for endpoint {endpoint_id}: {e}")
            return

        # Parse existing config
        model_data = json.loads(existing_data)
        endpoint_config_dict = model_data.get(str(endpoint_id))
        if not endpoint_config_dict:
            return

        # Build guardrail configuration if deployment is active
        guardrail_config = GuardrailDeploymentService._build_guardrail_config_for_proxy(deployment)
        endpoint_config_dict["guardrails"] = guardrail_config.model_dump() if guardrail_config else None

        # Save updated config back to cache
        await redis_service.set(cache_key, json.dumps(model_data))

    @staticmethod
    def _build_guardrail_config_for_proxy(deployment: GuardrailDeployment) -> Optional[ProxyGuardrailConfig]:
        """Build guardrail configuration for proxy from deployment."""
        from budapp.commons.schemas import ProxyGuardrailConfig, ProxyGuardrailProbeConfig, ProxyGuardrailRuleConfig

        # if not deployment.probe_associations:
        #     return None

        probe_configs = []
        for dep_probe in deployment.probe_associations or []:
            probe = dep_probe.probe

            # Build rule configurations
            rule_configs = []
            for rule_config in dep_probe.rule:
                rule_config = ProxyGuardrailRuleConfig(
                    rule_id=rule_config.rule_id,
                    rule_name=rule_config.rule.name,
                    sentinel_id=rule_config.rule.sentinel_id,
                    is_enabled=rule_config.is_enabled,
                    configuration=rule_config.configuration,
                    threshold_override=rule_config.threshold_override,
                )
                rule_configs.append(rule_config)

            probe_config = ProxyGuardrailProbeConfig(
                probe_id=probe.id,
                probe_name=probe.name,
                sentinel_id=probe.sentinel_id,
                is_enabled=dep_probe.is_enabled,
                configuration=dep_probe.configuration,
                threshold_override=dep_probe.threshold_override,
                rules=rule_configs,
            )
            probe_configs.append(probe_config)

        return ProxyGuardrailConfig(
            name=deployment.name,
            configuration=deployment.configuration,
            default_threshold=deployment.default_threshold,
            probes=probe_configs,
        )


logger = logging.get_logger(__name__)


class GuardrailDeploymentWorkflowService(SessionMixin):
    """Service for guardrail deployment workflow operations."""

    async def create_guardrail_deployment_workflow(
        self, current_user_id: UUID, request: CreateGuardrailDeploymentWorkflowRequest
    ) -> WorkflowModel:
        """Create or update a guardrail deployment workflow."""
        # Get request data
        step_number = request.step_number
        workflow_id = request.workflow_id
        workflow_total_steps = request.workflow_total_steps
        trigger_workflow = request.trigger_workflow

        # Retrieve or create workflow
        workflow_create = WorkflowUtilCreate(
            workflow_type=WorkflowTypeEnum.GUARDRAIL_DEPLOYMENT,
            title="Guardrail Deployment Configuration",
            total_steps=workflow_total_steps,
            icon=APP_ICONS.get("general", {}).get("shield", "🛡️"),
            tag="Guardrail Deployment",
        )
        db_workflow = await WorkflowService(self.session).retrieve_or_create_workflow(
            workflow_id, workflow_create, current_user_id
        )

        # Prepare step data based on current step
        step_data = await self._prepare_step_data(step_number, request)

        # Update workflow step
        await WorkflowStepService(self.session).create_or_update_next_workflow_step(
            workflow_id=db_workflow.id,
            step_number=step_number,
            data=step_data,
        )

        # Update workflow current step
        db_workflow.current_step = step_number
        self.session.commit()

        # If this is the final step and trigger_workflow is True, complete the workflow
        if step_number == workflow_total_steps and trigger_workflow:
            await self.complete_workflow_and_deploy(db_workflow.id, current_user_id)

        return db_workflow

    async def _prepare_step_data(self, step_number: int, request: CreateGuardrailDeploymentWorkflowRequest) -> Dict:
        """Prepare step data based on the current step number."""
        step_data = {}

        if step_number == 1:
            if request.provider_id:
                step_data["provider_id"] = str(request.provider_id)

        elif step_number == 2:
            # Step 2: Probe selection
            # Handle new sparse selection format
            if request.probe_selections is not None:
                step_data["probe_selections"] = [sel.model_dump(mode="json") for sel in request.probe_selections]

        elif step_number == 3:
            # Step 3: Deployment type
            if request.deployment_type:
                step_data["deployment_type"] = request.deployment_type.value

        elif step_number == 4:
            # Step 3: Project selection
            if request.project_id:
                step_data["project_id"] = str(request.project_id)

        elif step_number == 5:
            # Step 4: Endpoint selection
            if request.endpoint_id:
                step_data["endpoint_id"] = str(request.endpoint_id)

        elif step_number == 6:
            # Step 5: Configuration
            if request.guard_types:
                step_data["guard_types"] = request.guard_types
            if request.threshold:
                step_data["threshold"] = request.threshold

        # elif step_number == 7:
        #     # Step 6: ETA
        #     step_data["estimated_deployment_time"] = 30  # 30 seconds placeholder
        #     step_data["deployment_name"] = request.deployment_name or "Guardrail Deployment"
        #     step_data["deployment_description"] = request.deployment_description

        return step_data

    async def complete_workflow_and_deploy(self, workflow_id: UUID, current_user_id: UUID) -> GuardrailDeployment:
        """Complete the workflow and create the guardrail deployment."""
        # Get all workflow steps
        workflow_steps = await WorkflowStepDataManager(self.session).get_all_workflow_steps(
            {"workflow_id": workflow_id}
        )

        # Extract data from workflow steps
        workflow_data = {}
        for step in workflow_steps:
            if step.data:
                workflow_data.update(step.data)

        # Create deployment from workflow data
        deployment = await self._create_deployment_from_workflow(workflow_data, current_user_id)

        # Update final step with deployment details
        await WorkflowStepService(self.session).create_or_update_next_workflow_step(
            workflow_id=workflow_id,
            step_number=7,
            data={
                "deployment_status": "success",
                "deployment_message": "Guardrail deployment completed successfully",
                "deployment_id": str(deployment.id),
            },
        )

        # Mark workflow as completed
        await WorkflowService(self.session).mark_workflow_as_completed(workflow_id, current_user_id)

        # Update proxy cache after deployment is active
        if deployment.endpoint_id:
            await GuardrailDeploymentService._update_endpoint_proxy_cache(
                self.session, deployment.endpoint_id, deployment
            )

        return deployment

    async def _create_deployment_from_workflow(
        self, workflow_data: Dict, current_user_id: UUID
    ) -> GuardrailDeployment:
        """Create a guardrail deployment from workflow data."""
        # Extract deployment data
        deployment_type = GuardrailDeploymentTypeEnum(workflow_data.get("deployment_type"))
        project_id = UUID(workflow_data.get("project_id"))

        # Handle new sparse selection format
        probe_selections_data = workflow_data.get("probe_selections", [])
        provider_id_str = workflow_data.get("provider_id")
        provider_id = UUID(provider_id_str) if provider_id_str else None

        if not provider_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="provider_id is required for deployment creation"
            )

        # Convert probe selections back to ProbeSelection objects
        probe_selections = []
        if probe_selections_data:
            for sel_data in probe_selections_data:
                rule_selections = [RuleSelection(**rs) for rs in sel_data.get("rule_selections", [])]
                probe_selection = ProbeSelection(
                    probe_id=sel_data["probe_id"], enabled=sel_data["enabled"], rule_selections=rule_selections
                )
                probe_selections.append(probe_selection)

        guard_types = workflow_data.get("guard_types", [])  # Reserved for future use

        # Prepare deployment probes
        deployment_probes = []

        # Use new sparse selection format if available
        if probe_selections:
            # Already have ProbeSelection objects, just need to enrich with configs
            for selection in probe_selections:
                # Prepare rule configurations
                rule_configurations = []
                if selection.rule_selections:
                    for rule_sel in selection.rule_selections:
                        rule_configurations.append(
                            GuardrailDeploymentRuleCreate(
                                rule_id=rule_sel.rule_id,
                                is_enabled=rule_sel.enabled,
                            )
                        )

                deployment_probes.append(
                    GuardrailDeploymentProbeCreate(
                        probe_id=selection.probe_id,
                        is_enabled=selection.enabled,
                        rules=rule_configurations,
                    )
                )

        # Create deployment
        deployment_create = GuardrailDeploymentCreate(
            name=workflow_data.get("deployment_name", "Guardrail Deployment"),
            description=workflow_data.get("deployment_description"),
            deployment_type=deployment_type,
            endpoint_id=UUID(workflow_data["endpoint_id"]) if workflow_data.get("endpoint_id") else None,
            project_id=project_id,
            # provider_id=provider_id,
            default_threshold=workflow_data.get("threshold"),
            guardrail_types=guard_types if guard_types else None,
            probe_selections=probe_selections if probe_selections else None,
        )

        # Create deployment using existing service
        deployment = await GuardrailDeploymentService.create_deployment(
            self.session, deployment_create, current_user_id
        )

        # # Set deployment status to active (since we're not doing actual deployment)
        # update_data = GuardrailDeploymentUpdate(status=GuardrailDeploymentStatusEnum.RUNNING)
        # await crud.update_deployment(self.session, deployment.id, update_data, current_user_id)
        # await self.session.commit()

        return deployment
