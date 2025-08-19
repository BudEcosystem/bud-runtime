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

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from budapp.commons import logging
from budapp.commons.constants import APP_ICONS, GuardrailDeploymentStatusEnum, GuardrailProviderEnum, WorkflowTypeEnum
from budapp.commons.db_utils import SessionMixin
from budapp.guardrails import crud
from budapp.guardrails.models import GuardrailDeployment
from budapp.guardrails.schemas import (
    CreateGuardrailDeploymentWorkflowRequest,
    GuardrailDeploymentCreate,
    GuardrailDeploymentListRequestSchema,
    GuardrailDeploymentProbeCreate,
    GuardrailDeploymentResponse,
    GuardrailDeploymentRuleConfigCreate,
    GuardrailDeploymentRuleConfigResponse,
    GuardrailDeploymentUpdate,
    GuardrailDeploymentWorkflowStepData,
    GuardrailGuardTypeResponse,
    GuardrailModalityTypeResponse,
    GuardrailProbeCreate,
    GuardrailProbeListRequestSchema,
    GuardrailProbeListResponse,
    GuardrailProbeResponse,
    GuardrailProbeUpdate,
    GuardrailRuleCreate,
    GuardrailRuleListRequestSchema,
    GuardrailRuleResponse,
    GuardrailRuleUpdate,
    GuardrailScannerTypeResponse,
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

        # Only allow creating probes for custom providers
        if provider.provider_type != GuardrailProviderEnum.CUSTOM:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Can only create probes for custom providers"
            )

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
            provider_name=probe.provider.display_name if probe.provider else None,
            provider_type=probe.provider.provider_type if probe.provider else None,
            is_custom=probe.is_custom,
            rule_count=len(probe.rules) if probe.rules else 0,
        )

    @staticmethod
    async def get_probes(
        db: Session, filters: GuardrailProbeListRequestSchema, user_id: UUID
    ) -> Tuple[List[GuardrailProbeListResponse], int]:
        """Get probes with filtering and pagination."""
        probes, total = await crud.get_probes(db, filters, user_id)
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
        db: Session, probe_id: UUID, filters: GuardrailRuleListRequestSchema, user_id: UUID
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
        rules, total = await crud.get_rules_paginated(db, probe_id, filters)
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
        if deployment_data.probe_selections is not None:
            # Convert sparse selections to deployment probe configs
            deployment_data.probes = await GuardrailDeploymentService._process_sparse_selections(
                db, deployment_data.probe_selections, deployment_data.provider_ids, user_id
            )

        # Validate probe access
        await GuardrailDeploymentService._validate_probe_access(db, deployment_data.probes, user_id)

        # Validate deployment configuration
        await GuardrailDeploymentService._validate_deployment_config(deployment_data)

        deployment = await crud.create_deployment(db, deployment_data, user_id)
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
        db: Session, filters: GuardrailDeploymentListRequestSchema, user_id: UUID
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
        db: Session, deployment_id: UUID, deployment_data: GuardrailDeploymentUpdate, user_id: UUID
    ) -> GuardrailDeploymentResponse:
        """Update a deployment."""
        # Validate probe access if probes are being updated
        if deployment_data.probes is not None:
            await GuardrailDeploymentService._validate_probe_access(db, deployment_data.probes, user_id)

        deployment = await crud.update_deployment(db, deployment_id, deployment_data, user_id)
        if not deployment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found")

        return await GuardrailDeploymentService._build_deployment_response(db, deployment)

    @staticmethod
    async def delete_deployment(db: Session, deployment_id: UUID, user_id: UUID) -> bool:
        """Delete a deployment."""
        success = await crud.delete_deployment(db, deployment_id, user_id)
        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found")

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
        db: Session, probe_selections: List[ProbeSelection], provider_ids: List[UUID], user_id: UUID
    ) -> List[GuardrailDeploymentProbeCreate]:
        """Process sparse probe selections into deployment probe configs.

        Args:
            probe_selections: List of probe selections (empty = all enabled)
            provider_ids: Provider IDs to fetch all probes from when selections is empty
            user_id: Current user ID for access control

        Returns:
            List of deployment probe configurations
        """
        from budapp.guardrails.schemas import ProbeSelection

        deployment_probes = []

        if not probe_selections:
            # Empty selections = enable all probes from specified providers
            if not provider_ids:
                return []

            for provider_id in provider_ids:
                # Get all probes for this provider
                provider_probes = await crud.get_probes_by_provider(db, provider_id)

                for probe in provider_probes:
                    # Check access for custom probes
                    if probe.is_custom and probe.user_id != user_id:
                        continue

                    # Create deployment probe with all rules enabled
                    deployment_probe = GuardrailDeploymentProbeCreate(
                        probe_id=probe.id,
                        is_enabled=True,
                        rule_configs=[],  # Empty = all rules enabled
                    )
                    deployment_probes.append(deployment_probe)
        else:
            # Process explicit selections
            for selection in probe_selections:
                if not selection.enabled:
                    continue  # Skip disabled probes

                # Convert rule selections to rule configs
                rule_configs = []
                if selection.rule_selections:
                    for rule_selection in selection.rule_selections:
                        if rule_selection.enabled:
                            rule_config = GuardrailDeploymentRuleConfigCreate(
                                rule_id=rule_selection.rule_id, is_enabled=True
                            )
                            rule_configs.append(rule_config)

                deployment_probe = GuardrailDeploymentProbeCreate(
                    probe_id=selection.probe_id, is_enabled=True, rule_configs=rule_configs
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
    async def _validate_deployment_config(deployment_data: GuardrailDeploymentCreate) -> None:
        """Validate deployment configuration."""
        # Validate probe uniqueness
        probe_ids = [probe.probe_id for probe in deployment_data.probes]
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
                    modified_at=override_config.modified_at if override_config else rule.modified_at,
                )
                rule_responses.append(rule_response)

            # Build probe response
            from budapp.guardrails.schemas import GuardrailDeploymentProbeResponse

            probe_response = GuardrailDeploymentProbeResponse(
                id=deployment_probe.id,
                deployment_id=deployment_probe.deployment_id,
                probe_id=deployment_probe.probe_id,
                probe_name=probe.name,
                is_enabled=deployment_probe.is_enabled,
                configuration=deployment_probe.configuration,
                rules=rule_responses,
                created_at=deployment_probe.created_at,
                modified_at=deployment_probe.modified_at,
            )
            probe_responses.append(probe_response)

        # No need to sort probes anymore as execution_order is removed

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
            modified_at=deployment.modified_at,
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
        await self.session.commit()

        # If this is the final step and trigger_workflow is True, complete the workflow
        if step_number == workflow_total_steps and trigger_workflow:
            await self.complete_workflow_and_deploy(db_workflow.id, current_user_id)

        return db_workflow

    async def _prepare_step_data(self, step_number: int, request: CreateGuardrailDeploymentWorkflowRequest) -> Dict:
        """Prepare step data based on the current step number."""
        step_data = {}

        if step_number == 1:
            # Step 1: Probe selection
            # Handle new sparse selection format
            if request.probe_selections is not None:
                step_data["probe_selections"] = [sel.model_dump() for sel in request.probe_selections]
            if request.provider_ids:
                step_data["provider_ids"] = [str(p) for p in request.provider_ids]
            # Legacy support
            if request.selected_probes:
                step_data["selected_probes"] = [str(p) for p in request.selected_probes]
            if request.selected_rules:
                step_data["selected_rules"] = {str(k): [str(r) for r in v] for k, v in request.selected_rules.items()}

        elif step_number == 2:
            # Step 2: Deployment type
            if request.deployment_type:
                step_data["deployment_type"] = request.deployment_type.value

        elif step_number == 3:
            # Step 3: Project selection
            if request.project_id:
                step_data["project_id"] = str(request.project_id)

        elif step_number == 4:
            # Step 4: Endpoint selection
            if request.endpoint_id:
                step_data["endpoint_id"] = str(request.endpoint_id)
            if request.deployment_endpoint_url:
                step_data["deployment_endpoint_url"] = request.deployment_endpoint_url

        elif step_number == 5:
            # Step 5: Configuration
            if request.guard_types:
                step_data["guard_types"] = {str(k): [str(g) for g in v] for k, v in request.guard_types.items()}
            if request.thresholds:
                step_data["thresholds"] = {str(k): v for k, v in request.thresholds.items()}
            if request.probe_configs:
                step_data["probe_configs"] = {str(k): v for k, v in request.probe_configs.items()}
            if request.rule_configs:
                step_data["rule_configs"] = request.rule_configs

        elif step_number == 6:
            # Step 6: ETA
            step_data["estimated_deployment_time"] = 30  # 30 seconds placeholder
            step_data["deployment_name"] = request.deployment_name or "Guardrail Deployment"
            step_data["deployment_description"] = request.deployment_description

        elif step_number == 7:
            # Step 7: Deployment status
            step_data["deployment_status"] = "deploying"
            step_data["deployment_message"] = "Initiating guardrail deployment..."

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
        provider_ids = [UUID(p) for p in workflow_data.get("provider_ids", [])]

        # Convert probe selections back to ProbeSelection objects
        probe_selections = []
        if probe_selections_data:
            for sel_data in probe_selections_data:
                rule_selections = [RuleSelection(**rs) for rs in sel_data.get("rule_selections", [])]
                probe_selection = ProbeSelection(
                    probe_id=sel_data["probe_id"], enabled=sel_data["enabled"], rule_selections=rule_selections
                )
                probe_selections.append(probe_selection)

        # Legacy support
        selected_probes = [UUID(p) for p in workflow_data.get("selected_probes", [])]
        selected_rules = workflow_data.get("selected_rules", {})
        # guard_types = workflow_data.get("guard_types", {})  # Reserved for future use
        thresholds = workflow_data.get("thresholds", {})
        probe_configs = workflow_data.get("probe_configs", {})
        rule_configs = workflow_data.get("rule_configs", {})

        # Prepare deployment probes
        deployment_probes = []

        # Use new sparse selection format if available
        if probe_selections:
            # Already have ProbeSelection objects, just need to enrich with configs
            for selection in probe_selections:
                if not selection.enabled:
                    continue

                probe_id_str = str(selection.probe_id)
                probe_threshold = thresholds.get(probe_id_str)
                probe_config = probe_configs.get(probe_id_str)

                # Prepare rule configurations
                rule_configurations = []
                if selection.rule_selections:
                    for rule_sel in selection.rule_selections:
                        if rule_sel.enabled:
                            rule_key = f"{selection.probe_id}:{rule_sel.rule_id}"
                            rule_config = rule_configs.get(rule_key, {})
                            rule_configurations.append(
                                GuardrailDeploymentRuleConfigCreate(
                                    rule_id=rule_sel.rule_id,
                                    is_enabled=True,
                                    configuration=rule_config,
                                )
                            )

                deployment_probes.append(
                    GuardrailDeploymentProbeCreate(
                        probe_id=selection.probe_id,
                        is_enabled=True,
                        configuration=probe_config,
                        threshold_override=probe_threshold,
                        rule_configs=rule_configurations,
                    )
                )
        else:
            # Legacy format
            for probe_id in selected_probes:
                probe_rules = selected_rules.get(str(probe_id), [])
                probe_threshold = thresholds.get(str(probe_id))
                probe_config = probe_configs.get(str(probe_id))

                # Prepare rule configurations
                rule_configurations = []
                for rule_id in probe_rules:
                    rule_key = f"{probe_id}:{rule_id}"
                    rule_config = rule_configs.get(rule_key, {})
                    rule_configurations.append(
                        GuardrailDeploymentRuleConfigCreate(
                            rule_id=UUID(rule_id),
                            is_enabled=True,
                            configuration=rule_config,
                        )
                    )

                deployment_probes.append(
                    GuardrailDeploymentProbeCreate(
                        probe_id=probe_id,
                        is_enabled=True,
                        configuration=probe_config,
                        threshold_override=probe_threshold,
                        rule_configs=rule_configurations,
                    )
                )

        # Create deployment
        deployment_create = GuardrailDeploymentCreate(
            name=workflow_data.get("deployment_name", "Guardrail Deployment"),
            description=workflow_data.get("deployment_description"),
            deployment_type=deployment_type,
            endpoint_id=UUID(workflow_data["endpoint_id"]) if workflow_data.get("endpoint_id") else None,
            deployment_endpoint_url=workflow_data.get("deployment_endpoint_url"),
            project_id=project_id,
            probes=deployment_probes if deployment_probes else None,
            probe_selections=probe_selections if probe_selections else None,
            provider_ids=provider_ids if provider_ids else None,
        )

        # Create deployment using existing service
        deployment = await GuardrailDeploymentService.create_deployment(
            self.session, deployment_create, current_user_id
        )

        # Set deployment status to active (since we're not doing actual deployment)
        update_data = GuardrailDeploymentUpdate(status=GuardrailDeploymentStatusEnum.ACTIVE)
        await crud.update_deployment(self.session, deployment.id, update_data, current_user_id)
        await self.session.commit()

        return deployment
