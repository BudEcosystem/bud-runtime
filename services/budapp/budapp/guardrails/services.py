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

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID, uuid4

from fastapi import status as HTTPStatus
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from budapp.commons import logging
from budapp.commons.config import app_settings
from budapp.commons.constants import (
    APP_ICONS,
    EndpointStatusEnum,
    GuardrailDeploymentStatusEnum,
    GuardrailProviderTypeEnum,
    GuardrailStatusEnum,
    ModelEndpointEnum,
    NotificationTypeEnum,
    ProjectStatusEnum,
    ProviderCapabilityEnum,
    ProxyProviderEnum,
    WorkflowStatusEnum,
    WorkflowTypeEnum,
)
from budapp.commons.db_utils import SessionMixin
from budapp.commons.exceptions import ClientException, DatabaseException
from budapp.commons.schemas import ErrorResponse, SuccessResponse, Tag
from budapp.core.schemas import NotificationResult
from budapp.credential_ops.crud import ProprietaryCredentialDataManager
from budapp.credential_ops.models import ProprietaryCredential
from budapp.credential_ops.services import CredentialService
from budapp.endpoint_ops.crud import EndpointDataManager
from budapp.endpoint_ops.models import Endpoint
from budapp.endpoint_ops.schemas import ProxyModelPricing
from budapp.endpoint_ops.services import EndpointService
from budapp.guardrails.crud import (
    GuardrailsDeploymentDataManager,
    GuardrailsProbeRulesDataManager,
)
from budapp.guardrails.models import (
    GuardrailDeployment,
    GuardrailProbe,
    GuardrailProfile,
    GuardrailProfileProbe,
    GuardrailProfileRule,
    GuardrailRule,
)
from budapp.guardrails.schemas import (
    BudSentinelConfig,
    CustomProbeWorkflowRequest,
    CustomProbeWorkflowSteps,
    GuardrailCustomProbeCreate,
    GuardrailCustomProbeUpdate,
    GuardrailDeploymentCreate,
    GuardrailDeploymentDetailResponse,
    GuardrailDeploymentResponse,
    GuardrailDeploymentWorkflowRequest,
    GuardrailDeploymentWorkflowSteps,
    GuardrailModelStatus,
    GuardrailModelStatusResponse,
    GuardrailProbeDetailResponse,
    GuardrailProbeResponse,
    GuardrailProbeRuleSelection,
    GuardrailProfileDetailResponse,
    GuardrailProfileProbeResponse,
    GuardrailProfileProbeSelection,
    GuardrailProfileResponse,
    GuardrailProfileRuleResponse,
    GuardrailRuleDetailResponse,
    GuardrailRuleResponse,
    LLMConfig,
    ModelDeploymentStatus,
    PolicyConfig,
    ProxyGuardrailConfig,
)
from budapp.model_ops.crud import ProviderDataManager
from budapp.model_ops.models import Provider
from budapp.project_ops.crud import ProjectDataManager
from budapp.project_ops.models import Project
from budapp.shared.notification_service import BudNotifyService, NotificationBuilder
from budapp.shared.redis_service import RedisService
from budapp.workflow_ops.budpipeline_service import BudPipelineService
from budapp.workflow_ops.crud import WorkflowDataManager, WorkflowStepDataManager
from budapp.workflow_ops.models import Workflow as WorkflowModel
from budapp.workflow_ops.models import WorkflowStep as WorkflowStepModel
from budapp.workflow_ops.schemas import WorkflowUtilCreate
from budapp.workflow_ops.services import WorkflowService, WorkflowStepService


logger = logging.get_logger(__name__)


@dataclass
class ProbeTypeConfig:
    """Configuration for a custom probe type.

    Maps probe type options to their model configurations.
    """

    model_uri: str
    scanner_type: str
    handler: str
    model_provider_type: str


PROBE_TYPE_CONFIGS: dict[str, ProbeTypeConfig] = {
    "llm_policy": ProbeTypeConfig(
        model_uri="openai/gpt-oss-safeguard-20b",
        scanner_type="llm",
        handler="gpt_safeguard",
        model_provider_type="cloud_model",
    ),
}


class GuardrailDeploymentWorkflowService(SessionMixin):
    """Guardrail deployment service."""

    async def add_guardrail_deployment_workflow(
        self, current_user_id: UUID, request: GuardrailDeploymentWorkflowRequest
    ):
        # Get request data
        step_number = request.step_number
        workflow_id = request.workflow_id
        workflow_total_steps = request.workflow_total_steps
        provider_type = request.provider_type
        provider_id = request.provider_id
        guardrail_profile_id = request.guardrail_profile_id
        name = request.name
        description = request.description
        tags = request.tags
        project_id = request.project_id
        endpoint_ids = request.endpoint_ids
        credential_id = request.credential_id
        is_standalone = request.is_standalone
        probe_selections = request.probe_selections
        guard_types = request.guard_types
        severity_threshold = request.severity_threshold
        trigger_workflow = request.trigger_workflow
        callback_topics = request.callback_topics
        hardware_mode = request.hardware_mode
        deploy_config = request.deploy_config
        per_model_deployment_configs = request.per_model_deployment_configs
        cluster_id = request.cluster_id  # Global cluster_id

        # Debug: Log per_model_deployment_configs to trace data flow
        if per_model_deployment_configs:
            logger.info(f"Received per_model_deployment_configs: {per_model_deployment_configs}")
            for idx, pmc in enumerate(per_model_deployment_configs):
                logger.info(f"  pmc[{idx}] keys: {pmc.keys()}, has cluster_id: {'cluster_id' in pmc}")

        current_step_number = step_number

        # Retrieve or create workflow
        workflow_create = WorkflowUtilCreate(
            workflow_type=WorkflowTypeEnum.CLOUD_MODEL_ONBOARDING,
            title="Guardrail Deployment",
            total_steps=workflow_total_steps,
            icon=APP_ICONS["general"]["deployment_mono"],
            tag="Guardrail Deployment",
        )
        db_workflow = await WorkflowService(self.session).retrieve_or_create_workflow(
            workflow_id, workflow_create, current_user_id
        )

        if provider_id:
            db_provider = await ProviderDataManager(self.session).retrieve_by_fields(Provider, {"id": provider_id})
            if ProviderCapabilityEnum.MODERATION not in db_provider.capabilities:
                raise ClientException(
                    f"Guardrail is only supported by providers with {ProviderCapabilityEnum.MODERATION.value} capabilitiy."
                )

            # Update icon on workflow
            db_workflow = await WorkflowDataManager(self.session).update_by_fields(
                db_workflow,
                {"icon": db_provider.icon, "title": db_provider.name},
            )

        if provider_type == GuardrailProviderTypeEnum.CLOUD:
            db_workflow = await WorkflowDataManager(self.session).update_by_fields(
                db_workflow,
                {"title": "Cloud Guardrail"},
            )

        # Validate project
        if project_id:
            db_project = await ProjectDataManager(self.session).retrieve_by_fields(
                Project, {"id": project_id, "status": ProjectStatusEnum.ACTIVE}
            )

            # Update workflow tag
            db_workflow = await WorkflowDataManager(self.session).update_by_fields(
                db_workflow, {"tag": db_project.name}
            )

        if endpoint_ids:
            # Validate all endpoint IDs belong to the project
            invalid_endpoint_ids = await EndpointDataManager(self.session).get_missing_endpoints(
                endpoint_ids, project_id
            )
            if invalid_endpoint_ids:
                raise ClientException(
                    f"Invalid endpoint IDs: {', '.join(str(eid) for eid in invalid_endpoint_ids)}. Endpoints must belong to the specified project and not be deleted."
                )

            # Check if any endpoints already have guardrail deployments
            existing_deployments = await GuardrailsDeploymentDataManager(
                self.session
            ).get_existing_deployments_for_endpoints(endpoint_ids)

            if existing_deployments:
                # Build error message with endpoint names and their existing guardrail profiles
                conflicting_endpoints = []
                for endpoint_id, deployment in existing_deployments.items():
                    endpoint_name = deployment.endpoint.name if deployment.endpoint else str(endpoint_id)
                    profile_name = deployment.profile.name if deployment.profile else "Unknown Profile"
                    conflicting_endpoints.append(f"'{endpoint_name}' (guardrail: {profile_name})")

                raise ClientException(
                    f"The following endpoints already have guardrail deployments: {', '.join(conflicting_endpoints)}. "
                    "Please remove or update existing deployments before adding new ones."
                )

        # Validate credential
        if credential_id:
            await ProprietaryCredentialDataManager(self.session).retrieve_by_fields(
                ProprietaryCredential, {"id": credential_id}
            )

        if guardrail_profile_id:
            db_profile = await GuardrailsDeploymentDataManager(self.session).retrieve_by_fields(
                GuardrailProfile, {"id": guardrail_profile_id, "status": GuardrailStatusEnum.ACTIVE}
            )

            # Update title on workflow
            db_workflow = await WorkflowDataManager(self.session).update_by_fields(
                db_workflow,
                {"title": db_profile.name},
            )

        if probe_selections:
            probe_ids = [probe.id for probe in probe_selections]
            if probe_ids:
                # Build rule selections mapping
                rule_selections = {}
                for probe in probe_selections:
                    if probe.rules:
                        rule_ids = [rule.id for rule in probe.rules]
                        rule_selections[probe.id] = rule_ids

                # Validate all probe and rule IDs in a single efficient operation
                invalid_probe_ids, invalid_rule_ids = await GuardrailsProbeRulesDataManager(
                    self.session
                ).get_missing_probes_and_rules(
                    probe_ids=probe_ids,
                    provider_id=provider_id,
                    rule_selections=rule_selections,
                )

                # Raise exceptions if invalid IDs found
                if invalid_probe_ids:
                    raise ClientException(
                        f"Invalid probe IDs: {', '.join(str(pid) for pid in invalid_probe_ids)}. Probes must be active and belong to the specified provider."
                    )

                if invalid_rule_ids:
                    raise ClientException(
                        f"Invalid rule IDs: {', '.join(str(rid) for rid in invalid_rule_ids)}. Rules must be active and belong to their respective probes."
                    )

        if name:
            db_profile = await GuardrailsDeploymentDataManager(self.session).retrieve_by_fields(
                GuardrailProfile, {"name": name, "status": GuardrailStatusEnum.ACTIVE}, missing_ok=True
            )
            if db_profile:
                raise ClientException("Guardrail profile already exists")

            # Update title on workflow
            db_workflow = await WorkflowDataManager(self.session).update_by_fields(
                db_workflow,
                {"title": name},
            )

        # Prepare workflow step data
        workflow_step_data = GuardrailDeploymentWorkflowSteps(
            provider_id=provider_id,
            provider_type=provider_type,
            guardrail_profile_id=guardrail_profile_id,
            name=name,
            description=description,
            tags=tags,
            project_id=project_id,
            endpoint_ids=endpoint_ids,
            credential_id=credential_id,
            is_standalone=is_standalone,
            probe_selections=probe_selections,
            guard_types=guard_types,
            severity_threshold=severity_threshold,
            hardware_mode=hardware_mode,
            deploy_config=deploy_config,
            per_model_deployment_configs=per_model_deployment_configs,
            cluster_id=cluster_id,
        ).model_dump(exclude_none=True, exclude_unset=True, mode="json")

        # Debug: Log workflow_step_data after model_dump
        if "per_model_deployment_configs" in workflow_step_data:
            logger.info(
                f"After model_dump, per_model_deployment_configs: {workflow_step_data['per_model_deployment_configs']}"
            )
            for idx, pmc in enumerate(workflow_step_data["per_model_deployment_configs"]):
                logger.info(f"  stored pmc[{idx}] keys: {pmc.keys()}, has cluster_id: {'cluster_id' in pmc}")

        # Get workflow steps first to check for existing data
        db_workflow_steps = await WorkflowStepDataManager(self.session).get_all_workflow_steps(
            {"workflow_id": db_workflow.id}
        )

        # For avoiding another db call for record retrieval, storing db object while iterating over db_workflow_steps
        db_current_workflow_step = None

        if db_workflow_steps:
            for db_step in db_workflow_steps:
                # Get current workflow step
                if db_step.step_number == current_step_number:
                    db_current_workflow_step = db_step

        if db_current_workflow_step:
            logger.info(f"Workflow {db_workflow.id} step {current_step_number} already exists")

            # Merge new data with existing step data to preserve fields like
            # onboarding_events, simulation_events that were previously stored
            existing_data = db_current_workflow_step.data or {}
            merged_data = {**existing_data, **workflow_step_data}
            workflow_step_data = merged_data

            # Update workflow step data in db
            db_workflow_step = await WorkflowStepDataManager(self.session).update_by_fields(
                db_current_workflow_step,
                {"data": workflow_step_data},
            )
            logger.info(f"Workflow {db_workflow.id} step {current_step_number} updated")
        else:
            logger.info(f"Creating workflow step {current_step_number} for workflow {db_workflow.id}")

            # Insert step details in db
            db_workflow_step = await WorkflowStepDataManager(self.session).insert_one(
                WorkflowStepModel(
                    workflow_id=db_workflow.id,
                    step_number=current_step_number,
                    data=workflow_step_data,
                )
            )

        # Update workflow current step as the highest step_number
        db_max_workflow_step_number = max(step.step_number for step in db_workflow_steps) if db_workflow_steps else 0
        workflow_current_step = max(current_step_number, db_max_workflow_step_number)
        logger.info(f"The current step of workflow {db_workflow.id} is {workflow_current_step}")

        # Initialize model_statuses_data (will be populated when probe_selections available)
        model_statuses_data: list[dict] | None = None

        # Get probe_selections from request or workflow data
        workflow_probe_selections = probe_selections
        workflow_project_id = project_id
        if not workflow_probe_selections:
            for db_step in db_workflow_steps:
                step_data = db_step.data or {}
                if step_data.get("probe_selections"):
                    workflow_probe_selections = [
                        GuardrailProfileProbeSelection(**ps) for ps in step_data["probe_selections"]
                    ]
                    break
        if not workflow_project_id:
            for db_step in db_workflow_steps:
                step_data = db_step.data or {}
                if step_data.get("project_id"):
                    workflow_project_id = UUID(step_data["project_id"])
                    break

        # Derive model statuses only when BOTH project_id AND probe_selections are available
        # Project is required to accurately check if models are already deployed in that project
        if workflow_probe_selections and workflow_project_id:
            logger.info(f"Deriving model statuses for workflow {db_workflow.id} in project {workflow_project_id}")
            model_status_response = await self.derive_model_statuses(workflow_probe_selections, workflow_project_id)

            # Update model status data in workflow step data
            workflow_step_data["model_statuses"] = [
                model.model_dump(mode="json") for model in model_status_response.models
            ]
            workflow_step_data["total_models"] = model_status_response.total_models
            workflow_step_data["models_requiring_onboarding"] = model_status_response.models_requiring_onboarding
            workflow_step_data["models_requiring_deployment"] = model_status_response.models_requiring_deployment
            workflow_step_data["models_reusable"] = model_status_response.models_reusable
            workflow_step_data["skip_to_step"] = model_status_response.skip_to_step
            workflow_step_data["credential_required"] = model_status_response.credential_required
            model_statuses_data = workflow_step_data["model_statuses"]

            logger.info(
                f"Model status derived: {model_status_response.total_models} models, "
                f"{model_status_response.models_requiring_onboarding} need onboarding, "
                f"{model_status_response.models_requiring_deployment} need deployment"
            )

            # Update the workflow step with fresh model statuses
            await WorkflowStepDataManager(self.session).update_by_fields(
                db_workflow_step, {"data": workflow_step_data}
            )

        # Get credential_id from request or workflow data
        onboarding_credential_id = credential_id
        if not onboarding_credential_id:
            for db_step in db_workflow_steps:
                step_data = db_step.data or {}
                if step_data.get("credential_id"):
                    onboarding_credential_id = UUID(step_data["credential_id"])
                    break

        # Check if onboarding should be triggered
        # Simple check: if onboarding_events.execution_id exists, skip (user creates new workflow to retry)
        should_trigger_onboarding = False
        existing_onboarding_events = workflow_step_data.get("onboarding_events", {})
        existing_execution_id = existing_onboarding_events.get("execution_id") if existing_onboarding_events else None
        if not existing_execution_id:
            # Also check previous steps for existing execution
            for db_step in db_workflow_steps:
                step_data = db_step.data or {}
                onboarding_events = step_data.get("onboarding_events", {})
                if onboarding_events and onboarding_events.get("execution_id"):
                    existing_execution_id = onboarding_events["execution_id"]
                    break

        if onboarding_credential_id and model_statuses_data:
            models_requiring_onboarding = [m for m in model_statuses_data if m.get("requires_onboarding")]
            if models_requiring_onboarding and not existing_execution_id:
                should_trigger_onboarding = True
            elif existing_execution_id:
                logger.info(f"Skipping onboarding - using existing execution_id: {existing_execution_id}")

        if should_trigger_onboarding:
            logger.info(f"Auto-triggering model onboarding for workflow {db_workflow.id}")
            models_to_onboard = [
                {
                    "rule_id": str(m["rule_id"]),
                    "model_uri": m["model_uri"],
                    "model_provider_type": m.get("model_provider_type", "hugging_face"),
                    "tags": m.get("tags"),
                }
                for m in model_statuses_data
                if m.get("requires_onboarding")
            ]

            try:
                onboarding_result = await self.trigger_model_onboarding(
                    models=models_to_onboard,
                    credential_id=onboarding_credential_id,
                    user_id=current_user_id,
                    callback_topics=callback_topics,
                )
                execution_id = onboarding_result.get("execution_id")
                if execution_id:
                    workflow_step_data["onboarding_events"] = {
                        "execution_id": execution_id,
                        "status": "running",
                        "results": onboarding_result,
                    }
                else:
                    workflow_step_data["onboarding_events"] = {
                        "status": "failed",
                        "results": onboarding_result,
                    }
                logger.info(f"Model onboarding triggered: execution_id={execution_id}")
            except Exception as e:
                logger.error(f"Failed to trigger model onboarding: {e}", exc_info=True)
                workflow_step_data["onboarding_events"] = {
                    "status": "failed",
                    "results": {"error": str(e)},
                }

            await WorkflowStepDataManager(self.session).update_by_fields(
                db_workflow_step, {"data": workflow_step_data}
            )

        # Auto-trigger cluster recommendation when hardware_mode/deploy_config provided and models need deployment
        # Get hardware_mode from request or workflow data
        sim_hardware_mode = hardware_mode
        if not sim_hardware_mode:
            for db_step in db_workflow_steps:
                step_data = db_step.data or {}
                if step_data.get("hardware_mode"):
                    sim_hardware_mode = step_data["hardware_mode"]
                    break

        # Get deploy_config from request or workflow data
        default_deploy_config = deploy_config
        if not default_deploy_config:
            for db_step in db_workflow_steps:
                step_data = db_step.data or {}
                if step_data.get("deploy_config"):
                    default_deploy_config = step_data["deploy_config"]
                    break

        # Validate global deploy_config doesn't contain endpoint_name
        # endpoint_name must be unique per model, so it should only be in per_model_deployment_configs
        if default_deploy_config and default_deploy_config.get("endpoint_name"):
            raise ClientException(
                "endpoint_name cannot be specified in global deploy_config. "
                "Use per_model_deployment_configs to specify unique endpoint names per model."
            )

        # Get per_model_deployment_configs from request or workflow data
        per_model_configs = per_model_deployment_configs
        if not per_model_configs:
            for db_step in db_workflow_steps:
                step_data = db_step.data or {}
                if step_data.get("per_model_deployment_configs"):
                    per_model_configs = step_data["per_model_deployment_configs"]
                    break

        # Validate cluster assignment if any cluster_id is specified
        # cluster_id can be at global level or per-model level (per-model overrides global)
        has_global_cluster = cluster_id is not None
        has_per_model_clusters = per_model_configs and any(pmc.get("cluster_id") for pmc in per_model_configs)

        if (has_global_cluster or has_per_model_clusters) and model_statuses_data:
            models_requiring_deployment = [m for m in model_statuses_data if m.get("requires_deployment")]
            if models_requiring_deployment:
                validation_result = await self.validate_cluster_assignment(
                    models=models_requiring_deployment,
                    global_cluster_id=cluster_id,
                    per_model_configs=per_model_configs,
                )
                # Store validation result in workflow step
                workflow_step_data["cluster_validation"] = validation_result
                if not validation_result["valid"]:
                    await WorkflowStepDataManager(self.session).update_by_fields(
                        db_workflow_step, {"data": workflow_step_data}
                    )
                    raise ClientException(
                        f"Cluster capacity validation failed: {'; '.join(validation_result['errors'])}"
                    )

        # Get simulation_events from current step or previous steps
        # simulation_events.results contains [{model_id, model_uri, workflow_id, status}]
        existing_sim_events = workflow_step_data.get("simulation_events", {})
        existing_sim_results = existing_sim_events.get("results", []) if existing_sim_events else []
        if not existing_sim_results:
            for db_step in db_workflow_steps:
                step_data = db_step.data or {}
                sim_events = step_data.get("simulation_events", {})
                if sim_events and sim_events.get("results"):
                    existing_sim_events = sim_events
                    existing_sim_results = sim_events["results"]
                    break

        # Refresh simulation status if there are running simulations
        if existing_sim_events and existing_sim_results:
            running_sims = [r for r in existing_sim_results if r.get("status") == "running"]
            if running_sims:
                logger.info(f"Refreshing status for {len(running_sims)} running simulations")
                refreshed_events = await self.refresh_simulation_status(existing_sim_events)
                workflow_step_data["simulation_events"] = refreshed_events
                existing_sim_results = refreshed_events.get("results", [])

                # Update the workflow step with refreshed simulation status
                await WorkflowStepDataManager(self.session).update_by_fields(
                    db_workflow_step, {"data": workflow_step_data}
                )

        # Get deployment_events from current step or previous steps
        existing_deploy_events = workflow_step_data.get("deployment_events", {})
        if not existing_deploy_events:
            for db_step in db_workflow_steps:
                step_data = db_step.data or {}
                deploy_events = step_data.get("deployment_events", {})
                if deploy_events and deploy_events.get("results"):
                    existing_deploy_events = deploy_events
                    break

        # Refresh deployment status if there are running deployments
        if existing_deploy_events and existing_deploy_events.get("results"):
            running_deploys = [r for r in existing_deploy_events.get("results", []) if r.get("status") == "running"]
            if running_deploys:
                logger.info(f"Refreshing status for {len(running_deploys)} running deployments")
                refreshed_deploy_events = await self.refresh_deployment_status(existing_deploy_events)
                workflow_step_data["deployment_events"] = refreshed_deploy_events

                # Update the workflow step with refreshed deployment status
                await WorkflowStepDataManager(self.session).update_by_fields(
                    db_workflow_step, {"data": workflow_step_data}
                )

                # Check if all deployments completed - finalize profile creation
                if refreshed_deploy_events.get("running", 0) == 0:
                    db_workflow = await WorkflowDataManager(self.session).retrieve_by_fields(
                        WorkflowModel, {"id": db_workflow.id}
                    )
                    if db_workflow.status == WorkflowStatusEnum.IN_PROGRESS:
                        # Check for pending profile data
                        pending_profile_data = workflow_step_data.get("pending_profile_data")
                        if not pending_profile_data:
                            for db_step in db_workflow_steps:
                                step_data = db_step.data or {}
                                if step_data.get("pending_profile_data"):
                                    pending_profile_data = step_data["pending_profile_data"]
                                    break

                        if refreshed_deploy_events.get("failed", 0) > 0:
                            # Some deployments failed - don't create profile
                            await WorkflowDataManager(self.session).update_by_fields(
                                db_workflow,
                                {"status": WorkflowStatusEnum.FAILED, "reason": "Some model deployments failed"},
                            )
                            logger.warning(f"Workflow {db_workflow.id} failed - model deployments failed")
                        elif pending_profile_data:
                            # All deployments succeeded - create the guardrail profile now
                            logger.info(
                                f"All deployments completed - finalizing guardrail profile for workflow {db_workflow.id}"
                            )

                            # Extract endpoint_ids from successful deployments
                            deployed_endpoint_ids = []
                            for result in refreshed_deploy_events.get("results", []):
                                if result.get("status") == "success" and result.get("endpoint_id"):
                                    endpoint_id_str = result["endpoint_id"]
                                    try:
                                        deployed_endpoint_ids.append(UUID(endpoint_id_str))
                                    except (ValueError, TypeError):
                                        logger.warning(f"Invalid endpoint_id in deployment result: {endpoint_id_str}")

                            # Update pending_profile_data with the newly created endpoint_ids
                            if deployed_endpoint_ids:
                                pending_profile_data["endpoint_ids"] = deployed_endpoint_ids
                                # Mark these as deployed endpoints for rollback cleanup
                                pending_profile_data["deployed_endpoint_ids"] = [
                                    str(eid) for eid in deployed_endpoint_ids
                                ]
                                pending_profile_data["models_requiring_deployment"] = True  # Flag for rollback logic
                                logger.info(
                                    f"Adding {len(deployed_endpoint_ids)} endpoint_ids to profile: {deployed_endpoint_ids}"
                                )

                            user_id = (
                                UUID(pending_profile_data.get("user_id"))
                                if pending_profile_data.get("user_id")
                                else db_workflow.created_by
                            )
                            provider_id = pending_profile_data.get("provider_id")
                            if provider_id:
                                pending_profile_data["provider_id"] = UUID(provider_id)

                            await self._finalize_guardrail_profile_creation(
                                data=pending_profile_data,
                                workflow_id=db_workflow.id,
                                current_user_id=user_id,
                                db_workflow=db_workflow,
                                db_latest_workflow_step=db_workflow_step,
                                guardrail_profile_id=UUID(pending_profile_data["guardrail_profile_id"])
                                if pending_profile_data.get("guardrail_profile_id")
                                else None,
                            )
                            logger.info(f"Workflow {db_workflow.id} completed - guardrail profile created")
                        else:
                            # No pending profile data - just mark as completed (shouldn't happen normally)
                            await WorkflowDataManager(self.session).update_by_fields(
                                db_workflow,
                                {"status": WorkflowStatusEnum.COMPLETED},
                            )
                            logger.info(f"Workflow {db_workflow.id} completed - all deployments finished")

        # Check if cluster recommendation should be triggered
        # Simple check: if simulation_events.results exists, skip (user creates new workflow to retry)
        should_trigger_cluster_rec = False
        if (sim_hardware_mode or default_deploy_config) and model_statuses_data:
            models_requiring_deployment = [m for m in model_statuses_data if m.get("requires_deployment")]
            if models_requiring_deployment and not existing_sim_results:
                should_trigger_cluster_rec = True
            elif existing_sim_results:
                logger.info(
                    f"Skipping simulation - using existing simulation_events: {len(existing_sim_results)} models"
                )

        if should_trigger_cluster_rec:
            logger.info(f"Auto-triggering cluster recommendation for workflow {db_workflow.id}")
            sim_hardware_mode = sim_hardware_mode or "dedicated"
            models_requiring_deployment = [m for m in model_statuses_data if m.get("requires_deployment")]

            # Build models with merged deploy configs
            models_for_simulation = self.build_models_with_deploy_configs(
                model_statuses=models_requiring_deployment,
                default_config=default_deploy_config,
                per_model_configs=per_model_configs,
            )

            try:
                simulation_result = await self.trigger_simulation(
                    models=models_for_simulation,
                    hardware_mode=sim_hardware_mode,
                    user_id=current_user_id,
                    workflow_id=db_workflow.id,
                )
                # Store full results with model mapping: [{model_id, model_uri, workflow_id, status}]
                sim_results = simulation_result.get("results", [])
                if sim_results:
                    workflow_step_data["simulation_events"] = {
                        "results": sim_results,
                        "total_models": len(sim_results),
                        "successful": len([r for r in sim_results if r.get("status") == "success"]),
                        "failed": len([r for r in sim_results if r.get("status") == "failed"]),
                    }
                else:
                    workflow_step_data["simulation_events"] = {
                        "results": [],
                        "total_models": 0,
                        "successful": 0,
                        "failed": 0,
                        "status": "failed",
                    }
                logger.info(f"Cluster recommendation triggered: {len(sim_results)} simulations started")
            except Exception as e:
                logger.error(f"Failed to trigger cluster recommendation: {e}", exc_info=True)
                workflow_step_data["simulation_events"] = {
                    "results": [],
                    "total_models": 0,
                    "successful": 0,
                    "failed": 0,
                    "status": "failed",
                    "error": str(e),
                }

            await WorkflowStepDataManager(self.session).update_by_fields(
                db_workflow_step, {"data": workflow_step_data}
            )

        # Create next step if workflow is triggered
        if trigger_workflow:
            # Increment step number of workflow and workflow step
            current_step_number = current_step_number + 1
            workflow_current_step = current_step_number

            # Update or create next workflow step
            db_workflow_step = await self._create_or_update_next_workflow_step(db_workflow.id, current_step_number, {})

        # Update workflow step data in db
        db_workflow = await WorkflowDataManager(self.session).update_by_fields(
            db_workflow,
            {"current_step": workflow_current_step},
        )

        # Execute workflow
        if trigger_workflow:
            logger.info("Workflow triggered")

            # TODO: Currently querying workflow steps again by ordering steps in ascending order
            # To ensure the latest step update is fetched, Consider excluding it later
            db_workflow_steps = await WorkflowStepDataManager(self.session).get_all_workflow_steps(
                {"workflow_id": db_workflow.id}
            )

            # Define the keys required for guardrail deployment
            keys_of_interest = [
                "provider_id",
                "provider_type",
                "guardrail_profile_id",
                "name",
                "description",
                "tags",
                "project_id",
                "endpoint_ids",
                "credential_id",
                "is_standalone",
                "probe_selections",
                "guard_types",
                "severity_threshold",
                # Model deployment fields
                "cluster_id",
                "hardware_mode",
                "deploy_config",
                "per_model_deployment_configs",
                "model_statuses",
                # Simulation results (contains simulator_id for each model)
                "simulation_events",
                # Deployment tracking (to prevent duplicate triggers)
                "deployment_events",
            ]

            # from workflow steps extract necessary information
            required_data = {}
            for db_workflow_step in db_workflow_steps:
                for key in keys_of_interest:
                    if key in db_workflow_step.data:
                        required_data[key] = db_workflow_step.data[key]

            required_keys = ["provider_type", "provider_id", "project_id", "probe_selections"]
            if not required_data.get("guardrail_profile_id"):
                required_keys.extend(["name", "probe_selections", "guard_types", "severity_threshold"])

            missing_keys = [key for key in required_keys if key not in required_data]
            if not ("endpoint_ids" in required_data or "is_standalone" in required_data):
                missing_keys.append("endpoint_ids/is_standalone")
            elif required_data.get("provider_type") == GuardrailProviderTypeEnum.CLOUD.value and not required_data.get(
                "credential_id"
            ):
                missing_keys.append("credential_id")
            if missing_keys:
                raise ClientException(f"Missing required data: {', '.join(missing_keys)}")

            # Check duplicate name exist in profile
            if not required_data.get("guardrail_profile_id"):
                db_profile = await GuardrailsDeploymentDataManager(self.session).retrieve_by_fields(
                    GuardrailProfile,
                    {"name": required_data["name"], "status": GuardrailStatusEnum.ACTIVE},
                    missing_ok=True,
                    case_sensitive=False,
                )
                if db_profile:
                    raise ClientException("Guardrail profile already exists")

                if not required_data["probe_selections"]:
                    raise ClientException("Guardrail profile needs atleast one probe for deployment")

            # Trigger deploy guardrail by step
            # Note: Profile creation may be deferred if model deployment is required
            await self._execute_add_guardrail_deployment_workflow(required_data, db_workflow.id, current_user_id)

        return db_workflow

    async def _execute_add_guardrail_deployment_workflow(
        self, data: Dict[str, Any], workflow_id: UUID, current_user_id: UUID
    ) -> None:
        """Execute add guardrail deployment workflow.

        Profile creation is deferred until all model deployments complete successfully.
        This ensures the profile is only saved when all validations and deployments succeed.
        """
        db_workflow_steps = await WorkflowStepDataManager(self.session).get_all_workflow_steps(
            {"workflow_id": workflow_id}
        )

        # Latest step
        db_latest_workflow_step = db_workflow_steps[-1]

        # Mark workflow completed
        logger.debug(f"Updating workflow status: {workflow_id}")
        db_workflow = await WorkflowDataManager(self.session).retrieve_by_fields(WorkflowModel, {"id": workflow_id})

        guardrail_profile_id = data.get("guardrail_profile_id")
        db_profile = None

        # Check if we're updating an existing profile
        if guardrail_profile_id:
            db_profile = await GuardrailsDeploymentDataManager(self.session).retrieve_by_fields(
                GuardrailProfile, {"id": guardrail_profile_id, "status": GuardrailStatusEnum.ACTIVE}, missing_ok=True
            )
            if not db_profile:
                logger.error(f"Failed to locate guardrail profile '{guardrail_profile_id}' in the repository")
                execution_status_data = {
                    "workflow_execution_status": {
                        "status": "error",
                        "message": "Failed to locate guardrail profile in the repository",
                    },
                    "profile_id": None,
                }
                await WorkflowStepDataManager(self.session).update_by_fields(
                    db_latest_workflow_step, {"data": execution_status_data}
                )
                await WorkflowDataManager(self.session).update_by_fields(
                    db_workflow, {"status": WorkflowStatusEnum.FAILED, "reason": "Profile not found"}
                )
                return
        else:
            # Check for duplicate profile name before proceeding
            existing_profile = await GuardrailsDeploymentDataManager(self.session).retrieve_by_fields(
                GuardrailProfile,
                {"name": data["name"], "status": GuardrailStatusEnum.ACTIVE},
                missing_ok=True,
                case_sensitive=False,
            )
            if existing_profile:
                raise ClientException("Guardrail profile name already exists")

        # Check if there are models requiring deployment
        model_statuses = data.get("model_statuses", [])
        models_requiring_deployment = [m for m in model_statuses if m.get("requires_deployment")]
        deployment_events = data.get("deployment_events")

        # Check if deployments are already running - skip triggering new deployments
        existing_running_deploys = []
        if deployment_events and deployment_events.get("results"):
            existing_running_deploys = [
                r for r in deployment_events.get("results", []) if r.get("status") == "running"
            ]
            if existing_running_deploys:
                logger.info(
                    f"Skipping deployment trigger - {len(existing_running_deploys)} deployments already running"
                )
                # Update workflow status and return (status refresh already happened above)
                await WorkflowDataManager(self.session).update_by_fields(
                    db_workflow, {"status": WorkflowStatusEnum.IN_PROGRESS}
                )
                return

        # If models need deployment, trigger deployment first and defer profile creation
        if models_requiring_deployment:
            cluster_id = data.get("cluster_id")
            per_model_configs = data.get("per_model_deployment_configs", [])

            # Check if we have cluster assignment (global or per-model)
            has_global_cluster = cluster_id is not None
            has_per_model_clusters = per_model_configs and any(pmc.get("cluster_id") for pmc in per_model_configs)

            if not has_global_cluster and not has_per_model_clusters:
                logger.warning("Models require deployment but no cluster_id specified (global or per-model)")
                execution_status_data = {
                    "workflow_execution_status": {
                        "status": "error",
                        "message": "Models require deployment but no cluster specified",
                    },
                    "profile_id": None,
                }
                await WorkflowStepDataManager(self.session).update_by_fields(
                    db_latest_workflow_step, {"data": execution_status_data}
                )
                await WorkflowDataManager(self.session).update_by_fields(
                    db_workflow, {"status": WorkflowStatusEnum.FAILED, "reason": "No cluster specified for deployment"}
                )
                return

            logger.info(f"Triggering model deployment for {len(models_requiring_deployment)} models")

            # Build models for deployment with merged deploy configs
            models_for_deployment = self.build_models_with_deploy_configs(
                model_statuses=models_requiring_deployment,
                default_config=data.get("deploy_config"),
                per_model_configs=data.get("per_model_deployment_configs"),
            )

            try:
                deployment_result = await self.trigger_deployment(
                    models=models_for_deployment,
                    cluster_id=UUID(cluster_id) if isinstance(cluster_id, str) else cluster_id,
                    project_id=UUID(data["project_id"]) if isinstance(data["project_id"], str) else data["project_id"],
                    user_id=current_user_id,
                    callback_topics=data.get("callback_topics"),
                    hardware_mode=data.get("hardware_mode", "dedicated"),
                    simulation_events=data.get("simulation_events"),  # Pass simulator_ids from earlier simulation
                )

                # Build deployment_events structure from trigger_deployment results
                # The new direct deployment returns detailed results for each model
                deploy_results = deployment_result.get("results", [])
                deployment_events = {
                    "execution_id": deployment_result.get("execution_id"),
                    "results": [
                        {
                            "model_id": r.get("model_id"),
                            "model_uri": next(
                                (
                                    m.get("model_uri")
                                    for m in models_for_deployment
                                    if str(m.get("model_id")) == r.get("model_id")
                                ),
                                None,
                            ),
                            "cluster_id": r.get("cluster_id") or str(cluster_id),
                            "status": r.get("status", "running"),
                            "endpoint_id": None,
                            "endpoint_name": r.get("endpoint_name"),
                            "error": r.get("error"),
                            "workflow_id": r.get("workflow_id"),
                        }
                        for r in deploy_results
                    ]
                    if deploy_results
                    else [
                        {
                            "model_id": str(m.get("model_id")),
                            "model_uri": m.get("model_uri"),
                            "cluster_id": str(m.get("cluster_id") or cluster_id),
                            "status": "running",
                            "endpoint_id": None,
                            "endpoint_name": m.get("deploy_config", {}).get("endpoint_name"),
                            "error": None,
                        }
                        for m in models_for_deployment
                    ],
                    "total_models": deployment_result.get("total_models", len(models_for_deployment)),
                    "successful": deployment_result.get("successful", 0),
                    "failed": deployment_result.get("failed", 0),
                    "running": deployment_result.get("total_models", len(models_for_deployment))
                    - deployment_result.get("failed", 0),
                }

                # Store pending profile data for creation after deployment completes
                pending_profile_data = {
                    "name": data.get("name"),
                    "description": data.get("description"),
                    "tags": data.get("tags"),
                    "severity_threshold": data.get("severity_threshold"),
                    "guard_types": data.get("guard_types"),
                    "project_id": data.get("project_id"),
                    "probe_selections": data.get("probe_selections", []),
                    "is_standalone": data.get("is_standalone", False),
                    "endpoint_ids": data.get("endpoint_ids", []),
                    "credential_id": data.get("credential_id"),
                    "provider_id": str(data["provider_id"]),
                    "user_id": str(current_user_id),
                }
                if guardrail_profile_id:
                    pending_profile_data["guardrail_profile_id"] = str(guardrail_profile_id)

                end_step_number = db_latest_workflow_step.step_number + 1
                db_workflow_step = await self._create_or_update_next_workflow_step(workflow_id, end_step_number, {})

                execution_status_data = {
                    "workflow_execution_status": {
                        "status": "running",
                        "message": f"Deploying {len(models_for_deployment)} guardrail model(s)...",
                    },
                    "deployment_events": deployment_events,
                    "pending_profile_data": pending_profile_data,
                    "profile_id": None,
                }

                await WorkflowStepDataManager(self.session).update_by_fields(
                    db_workflow_step, {"data": execution_status_data}
                )
                await WorkflowDataManager(self.session).update_by_fields(
                    db_workflow,
                    {"current_step": end_step_number, "status": WorkflowStatusEnum.IN_PROGRESS},
                )
                logger.info(f"Model deployment pipeline started: {deployment_result.get('execution_id')}")
                return

            except Exception as e:
                logger.exception(f"Failed to trigger model deployment: {e}")
                execution_status_data = {
                    "workflow_execution_status": {
                        "status": "error",
                        "message": f"Failed to trigger model deployment: {e}",
                    },
                    "deployment_events": {
                        "execution_id": None,
                        "results": [],
                        "total_models": len(models_requiring_deployment),
                        "successful": 0,
                        "failed": len(models_requiring_deployment),
                        "running": 0,
                        "error": str(e),
                    },
                    "profile_id": None,
                }
                await WorkflowStepDataManager(self.session).update_by_fields(
                    db_latest_workflow_step, {"data": execution_status_data}
                )
                await WorkflowDataManager(self.session).update_by_fields(
                    db_workflow, {"status": WorkflowStatusEnum.FAILED, "reason": str(e)}
                )
                return

        # No models need deployment - create profile immediately
        await self._finalize_guardrail_profile_creation(
            data=data,
            workflow_id=workflow_id,
            current_user_id=current_user_id,
            db_workflow=db_workflow,
            db_latest_workflow_step=db_latest_workflow_step,
            guardrail_profile_id=guardrail_profile_id,
        )

    async def _finalize_guardrail_profile_creation(
        self,
        data: Dict[str, Any],
        workflow_id: UUID,
        current_user_id: UUID,
        db_workflow: WorkflowModel,
        db_latest_workflow_step,
        guardrail_profile_id: UUID | None = None,
    ) -> None:
        """Finalize guardrail profile creation after all validations/deployments succeed.

        This method is called either:
        1. Immediately if no models need deployment (all reusable)
        2. After model deployments complete successfully
        """
        execution_status_data = {
            "workflow_execution_status": {
                "status": "success",
                "message": "Guardrail Profile successfully added to the repository",
            },
            "profile_id": None,
        }

        db_profile = None
        err_reason = None

        if guardrail_profile_id:
            # Updating existing profile
            db_profile = await GuardrailsDeploymentDataManager(self.session).retrieve_by_fields(
                GuardrailProfile, {"id": guardrail_profile_id, "status": GuardrailStatusEnum.ACTIVE}, missing_ok=True
            )
            if db_profile:
                execution_status_data["profile_id"] = str(db_profile.id)
        else:
            # Create new profile
            try:
                db_profile = await GuardrailsDeploymentDataManager(self.session).add_profile_with_selections(
                    name=data["name"],
                    current_user_id=current_user_id,
                    probe_selections=data.get("probe_selections", []),
                    description=data.get("description"),
                    tags=data.get("tags"),
                    severity_threshold=data.get("severity_threshold"),
                    guard_types=data.get("guard_types"),
                    project_id=data.get("project_id"),
                )
                execution_status_data["profile_id"] = str(db_profile.id)
            except Exception as e:
                logger.exception(f"Failed to add guardrail profile to the repository {e}")
                execution_status_data["workflow_execution_status"]["status"] = "error"
                execution_status_data["workflow_execution_status"]["message"] = (
                    "Failed to add guardrail profile to the repository"
                )
                err_reason = str(e)

        # Update step and check for errors
        await WorkflowStepDataManager(self.session).update_by_fields(
            db_latest_workflow_step, {"data": execution_status_data}
        )

        if execution_status_data["workflow_execution_status"]["status"] == "error":
            await WorkflowDataManager(self.session).update_by_fields(
                db_workflow, {"status": WorkflowStatusEnum.FAILED, "reason": err_reason}
            )
            return

        # Profile created successfully - now create guardrail deployments
        deployment_data = []

        if data.get("is_standalone", False):
            # For standalone deployments, use the guardrail profile name
            deployment_data.append(
                GuardrailDeploymentCreate(
                    name=db_profile.name,
                    description=db_profile.description,
                    status=GuardrailDeploymentStatusEnum.RUNNING,
                    profile_id=db_profile.id,
                    project_id=data["project_id"],
                    endpoint_id=None,
                    credential_id=data.get("credential_id"),
                )
            )
        else:
            # For endpoint deployments, fetch endpoint names
            endpoint_ids = data.get("endpoint_ids", [])
            if endpoint_ids:
                # Fetch endpoints to get their names
                endpoints = await EndpointDataManager(self.session).get_endpoints(endpoint_ids)
                endpoint_map = {ep.id: ep.name for ep in endpoints}

                for endpoint_id in endpoint_ids:
                    # Use endpoint name if available, otherwise use endpoint ID as fallback
                    deployment_name = endpoint_map.get(endpoint_id, str(endpoint_id))
                    deployment_data.append(
                        GuardrailDeploymentCreate(
                            name=deployment_name,
                            description=db_profile.description,
                            status=GuardrailDeploymentStatusEnum.RUNNING,
                            profile_id=db_profile.id,
                            project_id=data["project_id"],
                            endpoint_id=endpoint_id,
                            credential_id=data.get("credential_id"),
                        )
                    )

        end_step_number = db_latest_workflow_step.step_number + 1
        db_workflow_step = await self._create_or_update_next_workflow_step(workflow_id, end_step_number, {})

        # Store endpoint_ids for rollback support
        # These are endpoints created by model deployments triggered by this guardrail workflow
        deployed_endpoint_ids = data.get("deployed_endpoint_ids", [])
        if not deployed_endpoint_ids and data.get("endpoint_ids"):
            # For model deployments, endpoint_ids are newly created endpoints
            # Only consider them as "deployed" if they came from model deployment results
            # (indicated by is_standalone being False and models_requiring_deployment existing)
            if not data.get("is_standalone", False) and data.get("models_requiring_deployment"):
                deployed_endpoint_ids = [str(eid) for eid in data.get("endpoint_ids", [])]

        execution_status_data = {
            "workflow_execution_status": {
                "status": "success",
                "message": "Guardrail profile successfully deployed.",
            },
            "deployment": [entry.model_dump(mode="json") for entry in deployment_data],
            "profile_id": str(db_profile.id),
            "endpoint_ids": [str(eid) for eid in data.get("endpoint_ids", [])],
            "deployed_endpoint_ids": deployed_endpoint_ids,  # For rollback cleanup
        }

        err_reason = None
        try:
            await self._create_guardrail_endpoint_deployment(
                deployment_data, current_user_id, data["provider_id"], data.get("is_standalone", False)
            )
        except Exception as e:
            logger.exception(f"Failed to deploy guardrail profile endpoint(s) {e}")
            execution_status_data["workflow_execution_status"]["status"] = "error"
            execution_status_data["workflow_execution_status"]["message"] = (
                "Failed to deploy guardrail profile endpoint(s)"
            )
            err_reason = str(e)

        await WorkflowStepDataManager(self.session).update_by_fields(db_workflow_step, {"data": execution_status_data})

        if execution_status_data["workflow_execution_status"]["status"] == "error":
            await WorkflowDataManager(self.session).update_by_fields(
                db_workflow, {"status": WorkflowStatusEnum.FAILED, "reason": err_reason}
            )
        else:
            # Update workflow current step and status
            db_workflow = await WorkflowDataManager(self.session).update_by_fields(
                db_workflow,
                {"current_step": end_step_number, "status": WorkflowStatusEnum.COMPLETED},
            )

            # Send notification to workflow creator
            db_provider = await ProviderDataManager(self.session).retrieve_by_fields(
                Provider, {"id": data["provider_id"]}
            )
            notification_request = (
                NotificationBuilder()
                .set_content(
                    title=db_profile.name,
                    message="Profile deployed for selected endpoint(s)",
                    icon=db_provider.icon,
                    result=NotificationResult(target_id=db_profile.id, target_type="guardrail").model_dump(
                        exclude_none=True, exclude_unset=True
                    ),
                )
                .set_payload(
                    workflow_id=str(db_workflow.id), type=NotificationTypeEnum.GUARDRAIL_DEPLOYMENT_SUCCESS.value
                )
                .set_notification_request(subscriber_ids=[str(db_workflow.created_by)])
                .build()
            )
            await BudNotifyService().send_notification(notification_request)

            # Update credential proxy cache for the project
            await CredentialService(self.session).update_proxy_cache(data["project_id"])

    async def _create_guardrail_endpoint_deployment(
        self, data: list[GuardrailDeploymentCreate], current_user_id: UUID, provider_id: UUID, is_standalone: bool
    ) -> list[GuardrailDeployment]:
        db_deployments = await GuardrailsDeploymentDataManager(self.session).insert_all(
            [GuardrailDeployment(**deployment.model_dump(), created_by=current_user_id) for deployment in data]
        )

        db_provider = await ProviderDataManager(self.session).retrieve_by_fields(Provider, {"id": provider_id})

        encrypted_credential_data = None
        for db_deployment in db_deployments:
            # For standalone deployments, endpoint_id might be None initially
            # In that case, use the deployment ID as a temporary endpoint ID
            endpoint_id = db_deployment.endpoint_id if db_deployment.endpoint_id else db_deployment.id

            if (
                encrypted_credential_data is None
                and db_deployment.credential
                and hasattr(db_deployment.credential, "other_provider_creds")
            ):
                encrypted_credential_data = db_deployment.credential.other_provider_creds

            await self.add_guardrail_deployment_to_proxy_cache(
                endpoint_id=endpoint_id,
                profile_id=db_deployment.profile_id,
                provider_type=db_provider.type,
                api_base="budproxy-service.svc.cluster.local",
                supported_endpoints=["/v1/moderations"],
                encrypted_credential_data=encrypted_credential_data,
                include_pricing=False,
            )

        # Cache the profile data with all deployments, probes, and rules
        # Note: Profile is already cached in add_guardrail_deployment_to_proxy_cache

        return db_deployments

    async def add_guardrail_deployment_to_proxy_cache(
        self,
        endpoint_id: UUID,
        profile_id: UUID,
        provider_type: str,
        api_base: str,
        supported_endpoints: Union[List[str], Dict[str, bool]],
        encrypted_credential_data: Optional[dict] = None,
        include_pricing: bool = True,
    ) -> None:
        """Add guardrail configuration to proxy cache.

        This method performs two operations:
        1. Calls add_guardrail_profile_to_cache to save profile to guardrail_table:{profile_id}
        2. Updates model_table:{endpoint_id} to include guardrail_profile reference

        Args:
            endpoint_id: The endpoint ID (can be None for standalone)
            profile_id: The guardrail profile ID
            provider_type: The provider type (e.g., "openai", "azure-content-safety")
            api_base: The base API URL
            supported_endpoints: List of supported endpoints
            encrypted_credential_data: Optional encrypted credential data from ProprietaryCredential.other_provider_creds
            include_pricing: Whether to include pricing information in the cache
        """
        redis_service = RedisService()

        # Step 1: Use add_guardrail_profile_to_cache to populate guardrail_table
        # Pass the raw encrypted credential data and provider type - the method will handle provider-specific logic
        await self.add_guardrail_profile_to_cache(profile_id, encrypted_credential_data, provider_type)

        # Step 2: Update model_table for the endpoint
        if endpoint_id:
            # For existing endpoints, fetch current config and add guardrail_profile
            model_table_key = f"model_table:{endpoint_id}"
            existing_config = await redis_service.get(model_table_key)

            if existing_config:
                # Update existing endpoint configuration
                model_config = json.loads(existing_config)
                if str(endpoint_id) in model_config:
                    model_config[str(endpoint_id)]["guardrail_profile"] = str(profile_id)
                else:
                    # If the specific endpoint key doesn't exist, create it
                    model_config[str(endpoint_id)] = {"guardrail_profile": str(profile_id)}

                await redis_service.set(model_table_key, json.dumps(model_config))
            else:
                # For standalone guardrail endpoints, create a minimal entry
                standalone_config = {
                    str(endpoint_id): {
                        "routing": [],
                        "endpoints": ["moderation"],  # Default to moderation endpoint
                        "providers": {},
                        "guardrail_profile": str(profile_id),
                    }
                }
                await redis_service.set(model_table_key, json.dumps(standalone_config))

    async def delete_guardrail_deployment_from_proxy_cache(self, endpoint_id: UUID) -> None:
        """Delete guardrail configuration from proxy cache.

        This method removes the guardrail_profile reference from model_table:{endpoint_id}
        """
        redis_service = RedisService()

        # Remove guardrail_profile reference from model_table
        if endpoint_id:
            model_table_key = f"model_table:{endpoint_id}"
            existing_config = await redis_service.get(model_table_key)

            if existing_config:
                model_config = json.loads(existing_config)
                if str(endpoint_id) in model_config:
                    # Remove guardrail_profile key if it exists
                    model_config[str(endpoint_id)].pop("guardrail_profile", None)

                    # Save back to Redis
                    await redis_service.set(model_table_key, json.dumps(model_config))

    async def add_guardrail_profile_to_cache(
        self,
        profile_id: UUID,
        credential_data: Optional[dict] = None,
        provider_type: str = None,
        model_config: Optional[dict] = None,
    ) -> None:
        """Add guardrail profile data to cache with the correct schema format.

        This method creates the guardrail_table:{profile_id} cache entry with provider configurations.

        Cache structure:
        - guardrail_table:{profile_id} -> guardrail profile with providers and probe configs

        Args:
            profile_id: The guardrail profile ID to cache
            credential_data: Optional raw encrypted credential data from ProprietaryCredential.other_provider_creds
            provider_type: The actual provider type (e.g., "openai", "azure-content-safety")
            model_config: Optional dict with custom_rules, metadata_json, rule_overrides_json for model-based rules
        """
        redis_service = RedisService()
        # 1. Get the profile
        db_profile = await GuardrailsDeploymentDataManager(self.session).retrieve_by_fields(
            GuardrailProfile, {"id": profile_id, "status": GuardrailStatusEnum.ACTIVE}
        )

        # 2. Get all enabled probes for this profile with their overrides
        profile_probes = await GuardrailsDeploymentDataManager(self.session).get_all_by_fields(
            GuardrailProfileProbe,
            {"profile_id": profile_id},
        )

        # 3. Build providers configuration based on probes
        providers = {}
        if provider_type == "openai":
            provider_config = {
                "type": "openai",
                "probe_config": {},
                "api_key_location": f"dynamic::store_{profile_id}"
                if credential_data and credential_data.get("api_key")
                else "none",
            }
            # Add optional OpenAI-specific fields
            if credential_data:
                if api_base := credential_data.get("api_base"):
                    provider_config["api_base"] = api_base
                if org := credential_data.get("organization"):
                    provider_config["organization"] = org
            providers["openai"] = provider_config

        elif provider_type in ["azure-content-safety", "azure_content_safety"]:
            providers["azure_content_safety"] = {
                "type": "azure_content_safety",
                "probe_config": {},
                "endpoint": credential_data.get("api_base", "") if credential_data else "",
                "api_key_location": f"dynamic::store_{profile_id}"
                if credential_data and credential_data.get("api_key")
                else "none",
            }

        elif provider_type in ["aws-comprehend", "aws_comprehend"]:
            provider_config = {
                "type": "aws_comprehend",
                "probe_config": {},
                "region": credential_data.get("aws_region_name", "us-east-1") if credential_data else "us-east-1",
                "api_key_location": f"dynamic::store_{profile_id}"
                if credential_data and credential_data.get("aws_access_key_id")
                else "none",
            }
            # Add AWS-specific fields if available
            if credential_data:
                if access_key := credential_data.get("aws_access_key_id"):
                    provider_config["aws_access_key_id"] = access_key
                if secret_key := credential_data.get("aws_secret_access_key"):
                    provider_config["aws_secret_access_key"] = secret_key
                if session_token := credential_data.get("aws_session_token"):
                    provider_config["aws_session_token"] = session_token
            providers["aws-comprehend"] = provider_config

        elif provider_type == "bud_sentinel":
            bud_sentinel_config = {
                "type": "bud_sentinel",
                "probe_config": {},
                "endpoint": app_settings.bud_sentinel_base_url,
                "api_key_location": "none",  # Bud sentinel doesn't require credentials
            }
            # Add model-based rule config if provided (custom_rules, metadata_json, rule_overrides_json)
            if model_config:
                if model_config.get("custom_rules"):
                    bud_sentinel_config["custom_rules"] = model_config["custom_rules"]
                if model_config.get("metadata_json"):
                    bud_sentinel_config["metadata_json"] = model_config["metadata_json"]
                if model_config.get("rule_overrides_json"):
                    bud_sentinel_config["rule_overrides_json"] = model_config["rule_overrides_json"]
            providers["bud_sentinel"] = bud_sentinel_config

        else:
            # Default case for any other providers
            providers[provider_type] = {
                "type": provider_type,
                "probe_config": {},
                "api_key_location": f"dynamic::store_{profile_id}"
                if credential_data and credential_data.get("api_key")
                else "none",
            }

        for profile_probe in profile_probes:
            probe = profile_probe.probe

            # Get rules for this probe
            profile_rules = await GuardrailsDeploymentDataManager(self.session).get_all_by_fields(
                GuardrailProfileRule, {"profile_probe_id": profile_probe.id}
            )

            # Determine which rules to include based on the logic:
            # 1. If there are any active rules, use only active rules
            # 2. If no rules defined, use empty list (all enabled)
            # 3. If only disabled rules, get all rules except disabled ones

            active_rules = [rule for rule in profile_rules if rule.status == GuardrailStatusEnum.ACTIVE]
            disabled_rules = [rule for rule in profile_rules if rule.status == GuardrailStatusEnum.DISABLED]

            if active_rules:
                # Case 1: Use only active rules
                rules = [rule.rule.uri for rule in active_rules]
            elif not profile_rules:
                # Case 2: No rules defined, use empty (all enabled)
                rules = []
            elif disabled_rules and not active_rules:
                # Case 3: Only disabled rules, get all probe rules except disabled
                all_probe_rules = await GuardrailsDeploymentDataManager(self.session).get_all_by_fields(
                    GuardrailRule, {"probe_id": probe.id, "status": GuardrailStatusEnum.ACTIVE}
                )
                disabled_rule_ids = {rule.rule_id for rule in disabled_rules}
                rules = [rule.uri for rule in all_probe_rules if rule.id not in disabled_rule_ids]
            else:
                # Default: empty
                rules = []

            # Add to probe config
            if probe.uri:
                providers[provider_type]["probe_config"][probe.uri] = rules

        # 4. Build the guardrail profile configuration
        guardrail_profile_config = {
            "name": db_profile.name,
            "providers": providers,
            "severity_threshold": db_profile.severity_threshold if db_profile.severity_threshold else 0.75,
            "guard_types": db_profile.guard_types if db_profile.guard_types else ["input"],
        }

        # Add API key if provided (handle different credential types)
        if credential_data:
            if credential_data.get("api_key"):
                # For providers that use standard api_key field
                guardrail_profile_config["api_key"] = credential_data["api_key"]
            elif credential_data.get("aws_access_key_id"):
                # For AWS providers, store the access key as the api_key
                guardrail_profile_config["api_key"] = credential_data["aws_access_key_id"]
        elif provider_type == "bud_sentinel":
            # Bud sentinel doesn't require credentials - add empty api_key for gateway compatibility
            guardrail_profile_config["api_key"] = ""

        # 5. Save to guardrail_table:{profile_id}
        await redis_service.set(
            f"guardrail_table:{profile_id}",
            json.dumps({str(profile_id): guardrail_profile_config}),
        )

        logger.info(f"Successfully cached guardrail profile {profile_id} with {len(providers)} providers")

    async def update_guardrail_profile_cache(self, profile_id: UUID) -> None:
        """Update the cache for a guardrail profile by clearing and re-caching.

        This should be called when:
        - A profile is updated
        - Profile probes are modified
        - Profile rules are changed
        - An endpoint deployment is updated

        Args:
            profile_id: The guardrail profile ID to update
        """
        redis_service = RedisService()

        # Clear existing cache entries
        # 1. Clear deployment caches
        db_deployments = await GuardrailsDeploymentDataManager(self.session).get_all_by_fields(
            GuardrailDeployment, {"profile_id": profile_id}
        )

        for deployment in db_deployments:
            if deployment.endpoint_id:
                await redis_service.delete(f"guardrail_deployment:{deployment.endpoint_id}")

        # 2. Clear guardrail table cache
        await redis_service.delete(f"guardrail_table:{profile_id}")

        # Re-cache the profile data
        # Get raw encrypted credential data and provider type from deployments
        encrypted_credential_data = None
        provider_type = None

        if db_deployments:
            # Get the first probe from the profile to determine provider
            profile_probes = await GuardrailsDeploymentDataManager(self.session).get_all_by_fields(
                GuardrailProfileProbe,
                {"profile_id": profile_id},
            )

            if profile_probes and profile_probes[0].probe.provider_id:
                # Get provider type from the probe's provider
                db_provider = await ProviderDataManager(self.session).retrieve_by_fields(
                    Provider, {"id": profile_probes[0].probe.provider_id}
                )
                provider_type = db_provider.type

            # Get credential data from deployments
            for deployment in db_deployments:
                if deployment.credential and hasattr(deployment.credential, "other_provider_creds"):
                    encrypted_credential_data = deployment.credential.other_provider_creds
                    if encrypted_credential_data:
                        break

        await self.add_guardrail_profile_to_cache(profile_id, encrypted_credential_data, provider_type)

    async def delete_guardrail_profile_cache(self, profile_id: UUID) -> None:
        """Delete all cache entries for a guardrail profile.

        This should be called when a profile is deleted.

        Args:
            profile_id: The guardrail profile ID to delete from cache
        """
        redis_service = RedisService()

        # Clear deployment caches
        db_deployments = await GuardrailsDeploymentDataManager(self.session).get_all_by_fields(
            GuardrailDeployment, {"profile_id": profile_id}
        )

        for deployment in db_deployments:
            if deployment.endpoint_id:
                await redis_service.delete(f"guardrail_deployment:{deployment.endpoint_id}")

        # Clear guardrail table cache
        await redis_service.delete(f"guardrail_table:{profile_id}")

    async def _create_or_update_next_workflow_step(
        self, workflow_id: UUID, step_number: int, data: Dict[str, Any]
    ) -> None:
        """Create or update next workflow step."""
        # Check for workflow step exist or not
        db_workflow_step = await WorkflowStepDataManager(self.session).retrieve_by_fields(
            WorkflowStepModel,
            {"workflow_id": workflow_id, "step_number": step_number},
            missing_ok=True,
        )

        if db_workflow_step:
            db_workflow_step = await WorkflowStepDataManager(self.session).update_by_fields(
                db_workflow_step,
                {
                    "workflow_id": workflow_id,
                    "step_number": step_number,
                    "data": data,
                },
            )
        else:
            # Create a new workflow step
            db_workflow_step = await WorkflowStepDataManager(self.session).insert_one(
                WorkflowStepModel(
                    workflow_id=workflow_id,
                    step_number=step_number,
                    data=data,
                )
            )

        return db_workflow_step

    async def get_deployment_progress(
        self,
        deployment_id: UUID,
        detail: str = "summary",
    ) -> dict:
        """Get progress of a guardrail deployment via BudPipeline.

        Args:
            deployment_id: ID of the guardrail deployment
            detail: Detail level - 'summary', 'steps', or 'full'

        Returns:
            Progress information dict with status, progress percentage, and optionally steps/events

        Raises:
            ClientException: If deployment not found
        """
        # Retrieve the deployment to get its execution info
        db_deployment = await GuardrailsDeploymentDataManager(self.session).retrieve_by_fields(
            GuardrailDeployment,
            {"id": deployment_id},
            exclude_fields={"status": GuardrailDeploymentStatusEnum.DELETED},
        )
        if not db_deployment:
            raise ClientException(
                message="Deployment not found",
                status_code=HTTPStatus.HTTP_404_NOT_FOUND,
            )

        # Build progress response
        progress: dict[str, Any] = {
            "deployment_id": str(deployment_id),
            "status": db_deployment.status.value,
            "progress_percentage": 0,
        }

        # Calculate progress based on deployment status
        if db_deployment.status == GuardrailDeploymentStatusEnum.RUNNING:
            progress["progress_percentage"] = 100
        elif db_deployment.status == GuardrailDeploymentStatusEnum.FAILURE:
            progress["progress_percentage"] = 0
            progress["error"] = "Deployment failed"
        elif db_deployment.status == GuardrailDeploymentStatusEnum.DEPLOYING:
            # For in-progress, estimate based on endpoint statuses from rule deployments
            rule_deployments = await GuardrailsDeploymentDataManager(self.session).get_rule_deployments_for_guardrail(
                deployment_id
            )
            if rule_deployments:
                from budapp.endpoint_ops.models import Endpoint

                running_count = 0
                for rd in rule_deployments:
                    endpoint = await self.session.get(Endpoint, rd.endpoint_id)
                    if endpoint and endpoint.status == EndpointStatusEnum.RUNNING:
                        running_count += 1
                progress["progress_percentage"] = int((running_count / len(rule_deployments)) * 100)
            else:
                progress["progress_percentage"] = 50  # Default estimate

        # Add steps detail if requested
        if detail in ("steps", "full"):
            rule_deployments = await GuardrailsDeploymentDataManager(self.session).get_rule_deployments_for_guardrail(
                deployment_id
            )
            from budapp.endpoint_ops.models import Endpoint

            steps = []
            for rd in rule_deployments:
                endpoint = await self.session.get(Endpoint, rd.endpoint_id)
                steps.append(
                    {
                        "rule_id": str(rd.rule_id),
                        "endpoint_id": str(rd.endpoint_id),
                        "endpoint_status": endpoint.status.value if endpoint else "unknown",
                    }
                )
            progress["steps"] = steps

        return progress

    def build_models_with_deploy_configs(
        self,
        model_statuses: list[dict],
        default_config: dict | None = None,
        per_model_configs: list[dict] | None = None,
    ) -> list[dict]:
        """Build unique models list with merged deploy configurations.

        Models are deduplicated by model_uri. Merges default deploy_config with per-model overrides.

        Args:
            model_statuses: List of model status dicts from derive_model_statuses
            default_config: Default deploy config applied to all models
            per_model_configs: Per-model overrides, keyed by model_id or model_uri:
                [{model_id: "...", deploy_config: {...}}] or
                [{model_uri: "...", deploy_config: {...}}]

        Returns:
            List of unique model dicts with deploy_config for each model
        """
        # Build lookup for per-model configs (by model_id or model_uri)
        # Each entry can have: deploy_config, cluster_id
        config_by_model_id: dict[str, dict] = {}
        config_by_model_uri: dict[str, dict] = {}

        if per_model_configs:
            for pmc in per_model_configs:
                # Store the full per-model config (deploy_config + cluster_id)
                pmc_data = {
                    "deploy_config": pmc.get("deploy_config", {}),
                    "cluster_id": pmc.get("cluster_id"),
                }
                if pmc.get("model_id"):
                    config_by_model_id[str(pmc["model_id"])] = pmc_data
                if pmc.get("model_uri"):
                    config_by_model_uri[pmc["model_uri"]] = pmc_data

        # Deduplicate by model_uri
        seen_model_uris: set[str] = set()
        models = []

        for model_status in model_statuses:
            model_uri = model_status.get("model_uri")
            if not model_uri or model_uri in seen_model_uris:
                continue
            seen_model_uris.add(model_uri)

            model_id = str(model_status.get("model_id", "")) if model_status.get("model_id") else ""

            # Start with default config
            merged_config = dict(default_config) if default_config else {}
            per_model_cluster_id = None

            # Override with per-model config (model_id takes precedence over model_uri)
            if model_uri in config_by_model_uri:
                pmc_data = config_by_model_uri[model_uri]
                merged_config.update(pmc_data.get("deploy_config", {}))
                per_model_cluster_id = pmc_data.get("cluster_id")
            if model_id and model_id in config_by_model_id:
                pmc_data = config_by_model_id[model_id]
                merged_config.update(pmc_data.get("deploy_config", {}))
                # model_id lookup takes precedence for cluster_id too
                if pmc_data.get("cluster_id"):
                    per_model_cluster_id = pmc_data["cluster_id"]

            models.append(
                {
                    "model_id": model_id or None,
                    "model_uri": model_uri,
                    "local_path": model_status.get("local_path"),  # For budsim simulation
                    "supported_endpoints": model_status.get("supported_endpoints"),  # For budsim engine selection
                    "model_provider_type": model_status.get("model_provider_type"),
                    "deploy_config": merged_config,
                    "cluster_id": per_model_cluster_id,  # Per-model cluster override
                }
            )

        return models

    async def derive_model_statuses(
        self,
        probe_selections: list[GuardrailProfileProbeSelection],
        project_id: UUID,
    ) -> GuardrailModelStatusResponse:
        """Derive deployment status for all models required by selected probes/rules.

        This method examines each rule that requires a model (has model_uri) and determines:
        - If model needs onboarding (model_id is NULL)
        - If model is onboarded but not deployed in this project
        - If model is already deployed and running in this project
        - If model deployment has issues (unhealthy, failed, etc.)

        Args:
            probe_selections: List of selected probes with optional rule selections
            project_id: Project ID to check for existing deployments (required for accurate status)

        Returns:
            GuardrailModelStatusResponse with model statuses and summary counts
        """
        model_statuses: list[GuardrailModelStatus] = []
        seen_model_uris: set[str] = set()  # Track unique models

        # Collect all probe IDs and build rule selections mapping
        probe_ids = [probe.id for probe in probe_selections]
        rule_selections: dict[UUID, list[UUID]] = {}
        for probe in probe_selections:
            if probe.rules:
                rule_selections[probe.id] = [rule.id for rule in probe.rules]

        # Fetch all probes with their rules in one query
        probes = await GuardrailsProbeRulesDataManager(self.session).get_probes_with_rules(probe_ids)

        for db_probe in probes:
            # Determine which rules to check
            selected_rule_ids = rule_selections.get(db_probe.id)

            for db_rule in db_probe.rules:
                # Skip if rule not selected (when specific rules are selected)
                if selected_rule_ids and db_rule.id not in selected_rule_ids:
                    continue

                # Skip rules without model_uri (cloud/API-based rules)
                if not db_rule.model_uri:
                    continue

                # Skip duplicate model URIs (same model used by multiple rules)
                if db_rule.model_uri in seen_model_uris:
                    continue
                seen_model_uris.add(db_rule.model_uri)

                # Derive status based on model_id and endpoint state
                status, endpoint_info = await self._derive_single_model_status(db_rule, project_id)

                model_statuses.append(
                    GuardrailModelStatus(
                        rule_id=db_rule.id,
                        rule_name=db_rule.name,
                        probe_id=db_probe.id,
                        probe_name=db_probe.name,
                        model_uri=db_rule.model_uri,
                        # Use model_id from endpoint_info (looked up by URI) or fall back to rule.model_id
                        model_id=endpoint_info.get("model_id") or db_rule.model_id,
                        model_provider_type=db_rule.model_provider_type,
                        tags=db_rule.tags if hasattr(db_rule, "tags") and db_rule.tags else None,
                        local_path=endpoint_info.get("local_path"),  # For budsim simulation
                        supported_endpoints=endpoint_info.get("supported_endpoints"),  # For budsim engine selection
                        status=status,
                        endpoint_id=endpoint_info.get("endpoint_id"),
                        endpoint_name=endpoint_info.get("endpoint_name"),
                        endpoint_url=endpoint_info.get("endpoint_url"),
                        cluster_id=endpoint_info.get("cluster_id"),
                        cluster_name=endpoint_info.get("cluster_name"),
                        requires_onboarding=status == ModelDeploymentStatus.NOT_ONBOARDED,
                        requires_deployment=status
                        in (
                            ModelDeploymentStatus.NOT_ONBOARDED,
                            ModelDeploymentStatus.ONBOARDED,
                        ),
                        can_reuse=status == ModelDeploymentStatus.RUNNING,
                        show_warning=status == ModelDeploymentStatus.UNHEALTHY,
                    )
                )

        # Calculate summary counts
        models_requiring_onboarding = sum(1 for m in model_statuses if m.requires_onboarding)
        models_requiring_deployment = sum(1 for m in model_statuses if m.requires_deployment)
        models_reusable = sum(1 for m in model_statuses if m.can_reuse)

        # Determine skip logic
        skip_to_step = None
        if models_requiring_onboarding == 0 and models_requiring_deployment == 0:
            # All models already deployed and running - can skip to profile config
            skip_to_step = 12  # Step 12 is profile configuration
        elif models_requiring_onboarding == 0:
            # All models onboarded but some need deployment - skip to cluster selection
            skip_to_step = 8  # Step 8 is cluster recommendation

        # Check if credential is required (any model needs onboarding and is gated)
        credential_required = any(m.requires_onboarding for m in model_statuses)

        return GuardrailModelStatusResponse(
            message="OK",
            models=model_statuses,
            total_models=len(model_statuses),
            models_requiring_onboarding=models_requiring_onboarding,
            models_requiring_deployment=models_requiring_deployment,
            models_reusable=models_reusable,
            skip_to_step=skip_to_step,
            credential_required=credential_required,
        )

    async def _derive_single_model_status(
        self,
        rule: GuardrailRule,
        project_id: UUID | None = None,
    ) -> tuple[ModelDeploymentStatus, dict]:
        """Derive status for a single model/rule.

        Args:
            rule: The guardrail rule with model info
            project_id: Optional project ID to check for existing deployments

        Returns:
            Tuple of (ModelDeploymentStatus, endpoint_info_dict)
        """
        from budapp.commons.constants import ModelStatusEnum
        from budapp.model_ops.models import Model

        endpoint_info: dict = {}
        model_id = rule.model_id

        # Check if model is onboarded - first try rule.model_id, then look up by URI
        if not model_id and rule.model_uri:
            # Look up model by URI in the Model table
            stmt = select(Model).where(
                Model.uri == rule.model_uri,
                Model.status == ModelStatusEnum.ACTIVE,
            )
            result = self.session.execute(stmt)
            model = result.scalar_one_or_none()
            if model:
                model_id = model.id
                endpoint_info["model_id"] = model_id
                # Store local_path for simulation (budsim needs cached model path)
                if model.local_path:
                    endpoint_info["local_path"] = model.local_path
                # Store supported_endpoints for budsim engine selection
                if model.supported_endpoints:
                    endpoint_info["supported_endpoints"] = model.supported_endpoints

        if not model_id:
            return ModelDeploymentStatus.NOT_ONBOARDED, endpoint_info

        # Model is onboarded, check for existing endpoint deployment
        # Query for endpoints using this model
        stmt = select(Endpoint).where(
            Endpoint.model_id == model_id,
            Endpoint.status != EndpointStatusEnum.DELETED,
        )
        if project_id:
            stmt = stmt.where(Endpoint.project_id == project_id)

        result = self.session.execute(stmt)
        endpoints = result.scalars().all()

        if not endpoints:
            # Model onboarded but no endpoint deployed
            endpoint_info["model_id"] = model_id
            return ModelDeploymentStatus.ONBOARDED, endpoint_info

        # Find best endpoint (prefer RUNNING, then others)
        best_endpoint = None
        for ep in endpoints:
            if ep.status == EndpointStatusEnum.RUNNING:
                best_endpoint = ep
                break
            if best_endpoint is None or ep.status == EndpointStatusEnum.DEPLOYING:
                best_endpoint = ep

        if best_endpoint:
            endpoint_info = {
                "model_id": model_id,
                "endpoint_id": best_endpoint.id,
                "endpoint_name": best_endpoint.name,
                "endpoint_url": best_endpoint.url,
                "cluster_id": best_endpoint.cluster_id,
                "cluster_name": best_endpoint.cluster.name if best_endpoint.cluster else None,
            }

            # Map endpoint status to ModelDeploymentStatus
            status_mapping = {
                EndpointStatusEnum.RUNNING: ModelDeploymentStatus.RUNNING,
                EndpointStatusEnum.UNHEALTHY: ModelDeploymentStatus.UNHEALTHY,
                EndpointStatusEnum.DEPLOYING: ModelDeploymentStatus.DEPLOYING,
                EndpointStatusEnum.PENDING: ModelDeploymentStatus.PENDING,
                EndpointStatusEnum.FAILURE: ModelDeploymentStatus.FAILURE,
                EndpointStatusEnum.DELETING: ModelDeploymentStatus.DELETING,
            }
            return status_mapping.get(best_endpoint.status, ModelDeploymentStatus.ONBOARDED), endpoint_info

        return ModelDeploymentStatus.ONBOARDED, endpoint_info

    async def get_workflow_model_statuses(
        self,
        workflow_id: UUID,
        refresh: bool = False,
    ) -> GuardrailModelStatusResponse:
        """Get model statuses for an existing workflow.

        This method retrieves or re-computes model statuses for a workflow by:
        1. If refresh=False and model_statuses exist in step data, return cached data
        2. Otherwise, extract probe_selections from workflow steps and derive fresh statuses

        Args:
            workflow_id: The workflow ID
            refresh: If True, re-derive statuses even if cached

        Returns:
            GuardrailModelStatusResponse with model statuses
        """
        from budapp.guardrails.schemas import GuardrailProbeRuleSelection, GuardrailProfileProbeSelection

        # Get workflow steps
        db_workflow_steps = await WorkflowStepDataManager(self.session).get_all_workflow_steps(
            {"workflow_id": workflow_id}
        )

        if not db_workflow_steps:
            return GuardrailModelStatusResponse(
                message="No workflow steps found",
                models=[],
                total_models=0,
                models_requiring_onboarding=0,
                models_requiring_deployment=0,
                models_reusable=0,
            )

        # Collect data from all workflow steps
        probe_selections_data = None
        project_id = None
        cached_model_statuses = None

        for db_step in db_workflow_steps:
            step_data = db_step.data or {}
            if step_data.get("probe_selections"):
                probe_selections_data = step_data["probe_selections"]
            if step_data.get("project_id"):
                project_id = step_data["project_id"]
            # Check for cached model statuses
            if step_data.get("model_statuses") and not refresh:
                cached_model_statuses = step_data

        # Return cached statuses if available and refresh not requested
        if cached_model_statuses and not refresh:
            return GuardrailModelStatusResponse(
                message="OK",
                models=[GuardrailModelStatus(**status) for status in cached_model_statuses.get("model_statuses", [])],
                total_models=cached_model_statuses.get("total_models", 0),
                models_requiring_onboarding=cached_model_statuses.get("models_requiring_onboarding", 0),
                models_requiring_deployment=cached_model_statuses.get("models_requiring_deployment", 0),
                models_reusable=cached_model_statuses.get("models_reusable", 0),
                skip_to_step=cached_model_statuses.get("skip_to_step"),
                credential_required=cached_model_statuses.get("credential_required", False),
            )

        # Re-derive model statuses - require both probe_selections and project_id
        if not probe_selections_data:
            return GuardrailModelStatusResponse(
                message="No probe selections found",
                models=[],
                total_models=0,
                models_requiring_onboarding=0,
                models_requiring_deployment=0,
                models_reusable=0,
            )

        if not project_id:
            return GuardrailModelStatusResponse(
                message="Project ID required for model status derivation",
                models=[],
                total_models=0,
                models_requiring_onboarding=0,
                models_requiring_deployment=0,
                models_reusable=0,
            )

        # Convert probe_selections_data to GuardrailProfileProbeSelection objects
        probe_selections = []
        for probe_data in probe_selections_data:
            rules = None
            if probe_data.get("rules"):
                rules = [GuardrailProbeRuleSelection(**rule) for rule in probe_data["rules"]]
            probe_selections.append(GuardrailProfileProbeSelection(id=probe_data["id"], rules=rules))

        # Convert project_id string to UUID if needed
        project_uuid = UUID(project_id) if isinstance(project_id, str) else project_id

        return await self.derive_model_statuses(probe_selections, project_uuid)

    # =========================================================================
    # Pipeline Integration for Cross-Service Calls
    # =========================================================================

    async def trigger_model_onboarding(
        self,
        models: list[dict],
        credential_id: UUID | None = None,
        user_id: UUID | None = None,
        callback_topics: list[str] | None = None,
    ) -> dict:
        """Trigger BudPipeline to onboard multiple models using model_add action.

        Creates a DAG with parallel model_add steps for each model that needs onboarding.
        Auto-derives name and author from model_uri, and includes default guardrail tag plus rule tags.

        Args:
            models: List of model info dicts with keys:
                - rule_id: UUID of the guardrail rule
                - model_uri: HuggingFace model URI (e.g., "meta-llama/Llama-3.1-8B")
                - model_provider_type: Provider type (default: "hugging_face")
                - tags: Optional list of rule tags to include
            credential_id: Optional credential ID for gated models
            user_id: User ID initiating the operation
            callback_topics: Optional callback topics for real-time updates

        Returns:
            Dict with execution_id and step mapping for tracking
        """
        if not models:
            return {"execution_id": None, "message": "No models to onboard"}

        # Build DAG steps - one model_add step per model
        steps = []
        for i, model in enumerate(models):
            step_id = f"onboard_{i}"
            model_uri = model["model_uri"]
            uri_parts = model_uri.split("/")

            # Auto-derive name and author from model_uri
            # Format: "author/model-name" -> author="author", name="model-name"
            model_name = uri_parts[-1] if uri_parts else model_uri
            model_author = uri_parts[0] if len(uri_parts) > 1 else None

            # Default guardrail tag + any tags from the rule
            tags = [{"name": "guardrail", "color": "#6366f1"}]
            if model.get("tags"):
                tags.extend(model["tags"])

            step_params = {
                "model_uri": model_uri,
                "model_name": model_name,
                "model_source": model.get("model_provider_type", "hugging_face"),
                "author": model_author,
                "description": f"Guardrail model for rule {model.get('rule_id', 'unknown')}",
                "max_wait_seconds": 86400,
            }
            # Add credential_id if provided (required for gated models)
            if credential_id:
                step_params["credential_id"] = str(credential_id)

            steps.append(
                {
                    "id": step_id,
                    "name": f"Onboard {model_name}",
                    "action": "model_add",
                    "params": step_params,
                    "depends_on": [],  # All steps run in parallel
                }
            )

        # Build the DAG definition (matching SDK structure)
        dag = {
            "name": "guardrail-model-onboarding",
            "description": f"Onboard {len(models)} models for guardrail deployment",
            "steps": steps,
            "outputs": {},
            "parameters": [],
        }

        logger.info(f"Triggering model onboarding pipeline for {len(models)} models")

        # Execute via BudPipeline
        pipeline_service = BudPipelineService(self.session)
        result = await pipeline_service.run_ephemeral_execution(
            pipeline_definition=dag,
            params={"user_id": str(user_id)} if user_id else {},
            callback_topics=callback_topics,
            user_id=str(user_id) if user_id else None,
        )

        execution_id = result.get("execution_id")
        logger.info(f"Model onboarding pipeline started: execution_id={execution_id}")

        return {
            "execution_id": execution_id,
            "step_mapping": {model["rule_id"]: f"onboard_{i}" for i, model in enumerate(models)},
            "total_models": len(models),
        }

    async def trigger_deployment(
        self,
        models: list[dict],
        cluster_id: UUID | None,
        project_id: UUID,
        user_id: UUID | None = None,
        callback_topics: list[str] | None = None,
        hardware_mode: str = "dedicated",
        simulation_events: dict | None = None,
    ) -> dict:
        """Trigger model deployments by calling ModelService.deploy_model_by_step directly.

        Calls ModelService directly (no HTTP overhead), passing simulator_id from
        simulation_events to skip redundant simulation.

        Args:
            models: List of model info dicts with keys: model_id, model_name, deploy_config, cluster_id (optional)
            cluster_id: Global target cluster for deployment (can be None if per-model cluster_ids provided)
            project_id: Project ID for the deployments
            user_id: User ID initiating the operation
            callback_topics: Optional callback topics for real-time updates
            hardware_mode: Hardware allocation mode ("dedicated" or "shared")
            simulation_events: Optional simulation results containing simulator_id (workflow_id) for each model

        Returns:
            Dict with workflow_ids and deployment info for tracking
        """
        import asyncio
        import re

        if not models:
            return {"execution_id": None, "message": "No models to deploy"}

        # Build lookup map from model_id to simulator_id (workflow_id) from simulation_events
        # simulation_events.results contains [{model_id, model_uri, workflow_id, status}]
        simulator_id_map: dict[str, str] = {}
        if simulation_events:
            for sim_result in simulation_events.get("results", []):
                model_id = sim_result.get("model_id")
                workflow_id = sim_result.get("workflow_id")  # This is the simulator_id
                if model_id and workflow_id:
                    simulator_id_map[str(model_id)] = str(workflow_id)
            if simulator_id_map:
                logger.info(f"Using simulator_ids from simulation_events for {len(simulator_id_map)} models")

        # Build deployment requests for each model
        deployment_requests = []
        for i, model in enumerate(models):
            deploy_config = model.get("deploy_config", {})
            model_name = model.get("model_name", f"model_{i}")

            # Generate unique endpoint name if not provided
            endpoint_name = deploy_config.get("endpoint_name")
            if not endpoint_name:
                sanitized_name = re.sub(r"[^a-zA-Z0-9]", "-", model_name).lower().strip("-")
                sanitized_name = sanitized_name[:60]
                short_uuid = str(uuid4())[:8]
                endpoint_name = f"{sanitized_name}-guardrail-{short_uuid}"

            # Use per-model cluster_id if available, otherwise fall back to global
            model_cluster_id = model.get("cluster_id") or cluster_id
            if not model_cluster_id:
                raise ValueError(f"No cluster_id specified for model {model_name} (model_id={model.get('model_id')})")

            # Build deploy request payload matching ModelDeployStepRequest schema
            # NOTE: input_tokens/output_tokens defaults MUST match trigger_simulation defaults (1024/128)
            # to ensure simulation and deployment use consistent values
            request_data = {
                "workflow_total_steps": 1,
                "step_number": 1,
                "trigger_workflow": True,
                "model_id": str(model["model_id"]),
                "project_id": str(project_id),
                "cluster_id": str(model_cluster_id),
                "endpoint_name": endpoint_name,
                "hardware_mode": hardware_mode,
                "deploy_config": {
                    "concurrent_requests": deploy_config.get("concurrency", 10),
                    "avg_sequence_length": deploy_config.get("output_tokens", 128),
                    "avg_context_length": deploy_config.get("input_tokens", 1024),
                },
            }

            # Add callback_topic if provided
            if callback_topics:
                request_data["callback_topic"] = callback_topics[0]

            # Add simulator_id if available from simulation_events (allows budapp to skip redundant simulation)
            model_id_str = str(model["model_id"])
            if model_id_str in simulator_id_map:
                request_data["simulator_id"] = simulator_id_map[model_id_str]
                logger.debug(f"Using simulator_id {simulator_id_map[model_id_str]} for model {model_id_str}")

            deployment_requests.append(
                {
                    "model_id": str(model["model_id"]),
                    "model_name": model_name,
                    "endpoint_name": endpoint_name,
                    "cluster_id": str(model_cluster_id),
                    "request_data": request_data,
                }
            )

        logger.info(f"Triggering direct deployment for {len(models)} models to cluster {cluster_id}")

        # Import ModelService and schema for direct service call (avoid HTTP overhead)
        from budapp.model_ops.schemas import DeploymentTemplateCreate
        from budapp.model_ops.services import ModelService

        async def deploy_single_model(deployment_req: dict) -> dict:
            """Deploy a single model by calling ModelService directly."""
            try:
                req_data = deployment_req["request_data"]
                deploy_config_dict = req_data.get("deploy_config", {})

                # Convert deploy_config dict to DeploymentTemplateCreate schema
                deploy_config = DeploymentTemplateCreate(
                    concurrent_requests=deploy_config_dict.get("concurrent_requests", 10),
                    avg_sequence_length=deploy_config_dict.get("avg_sequence_length", 128),
                    avg_context_length=deploy_config_dict.get("avg_context_length", 1024),
                    per_session_tokens_per_sec=deploy_config_dict.get("per_session_tokens_per_sec"),
                    ttft=deploy_config_dict.get("ttft"),
                    e2e_latency=deploy_config_dict.get("e2e_latency"),
                )

                # Extract simulator_id
                simulator_id_str = req_data.get("simulator_id")
                simulator_id = UUID(simulator_id_str) if simulator_id_str else None
                logger.info(f"Deploying model {req_data['model_id']} with simulator_id={simulator_id_str}")

                # Call ModelService.deploy_model_by_step directly
                model_service = ModelService(self.session)
                db_workflow = await model_service.deploy_model_by_step(
                    current_user_id=user_id,
                    step_number=req_data.get("step_number", 1),
                    workflow_id=None,  # Create new workflow
                    workflow_total_steps=req_data.get("workflow_total_steps", 1),
                    model_id=UUID(req_data["model_id"]),
                    project_id=UUID(req_data["project_id"]),
                    cluster_id=UUID(req_data["cluster_id"]) if req_data.get("cluster_id") else None,
                    endpoint_name=req_data["endpoint_name"],
                    deploy_config=deploy_config,
                    trigger_workflow=req_data.get("trigger_workflow", True),
                    hardware_mode=req_data.get("hardware_mode", "dedicated"),
                    simulator_id=simulator_id,
                    callback_topic=req_data.get("callback_topic"),
                )

                workflow_id = db_workflow.id if db_workflow else None
                logger.info(f"Deployment started for model {deployment_req['model_id']}: workflow_id={workflow_id}")
                return {
                    "model_id": deployment_req["model_id"],
                    "model_name": deployment_req["model_name"],
                    "endpoint_name": deployment_req["endpoint_name"],
                    "cluster_id": deployment_req["cluster_id"],
                    "status": "running",
                    "error": None,
                    "workflow_id": str(workflow_id) if workflow_id else None,
                }
            except Exception as e:
                logger.exception(f"Failed to deploy model {deployment_req['model_id']}: {e}")
                return {
                    "model_id": deployment_req["model_id"],
                    "model_name": deployment_req["model_name"],
                    "endpoint_name": deployment_req["endpoint_name"],
                    "cluster_id": deployment_req["cluster_id"],
                    "status": "failed",
                    "error": str(e),
                    "workflow_id": None,
                }

        # Run all deployments in parallel
        results = await asyncio.gather(*[deploy_single_model(req) for req in deployment_requests])

        # Build response
        successful = sum(1 for r in results if r["status"] == "running")
        failed = sum(1 for r in results if r["status"] == "failed")

        # Use first workflow_id as execution_id for tracking (for compatibility)
        execution_id = next((r["workflow_id"] for r in results if r["workflow_id"]), None)

        logger.info(f"Deployment triggered: {successful} running, {failed} failed")

        return {
            "execution_id": execution_id,
            "results": results,
            "step_mapping": {r["model_id"]: f"deploy_{i}" for i, r in enumerate(results)},
            "total_models": len(models),
            "successful": successful,
            "failed": failed,
            "cluster_id": str(cluster_id) if cluster_id else None,
        }

    async def trigger_simulation(
        self,
        models: list[dict],
        hardware_mode: str = "dedicated",
        user_id: UUID | None = None,
        workflow_id: UUID | None = None,
    ) -> dict:
        """Trigger budsim simulations for multiple models.

        Calls budsim service directly via Dapr to run simulations for cluster recommendations.

        Args:
            models: List of model info dicts with keys: model_id, model_uri, deploy_config
            hardware_mode: "dedicated" or "shared" hardware mode
            user_id: User ID initiating the operation
            workflow_id: Workflow ID for tracking notifications

        Returns:
            Dict with simulation workflow IDs for tracking
        """
        from budapp.commons.config import app_settings
        from budapp.commons.constants import BUD_INTERNAL_WORKFLOW
        from budapp.commons.schemas import BudNotificationMetadata
        from budapp.shared.dapr_service import DaprService

        if not models:
            return {"workflow_ids": [], "message": "No models to simulate"}

        workflow_ids = []
        results = []

        for model in models:
            deploy_config = model.get("deploy_config", {})

            # Build notification metadata for workflow tracking
            notification_metadata = BudNotificationMetadata(
                workflow_id=str(workflow_id) if workflow_id else "",
                subscriber_ids=str(user_id) if user_id else "",
                name=BUD_INTERNAL_WORKFLOW,
            )

            try:
                # Use local_path if available (after onboarding), otherwise use model_uri
                # local_path is the cached model path that budsim can access without HF credentials
                pretrained_model_uri = model.get("local_path") or model.get("model_uri", "")

                # Convert supported_endpoints to format expected by budsim (uppercase type names)
                # supported_endpoints contains paths like "/v1/embeddings", budsim expects "EMBEDDING"
                endpoint_path_to_type = {
                    "/v1/embeddings": "EMBEDDING",
                    "/v1/chat/completions": "LLM",
                    "/v1/completions": "LLM",
                    "/v1/audio/transcriptions": "AUDIO",
                    "/v1/audio/translations": "AUDIO",
                    "/v1/audio/speech": "AUDIO",
                    "/v1/classify": "CLASSIFY",
                    "/v1/rerank": "RERANK",
                }
                model_endpoints = None
                supported_endpoints = model.get("supported_endpoints")
                if supported_endpoints:
                    endpoint_values = []
                    for endpoint in supported_endpoints:
                        endpoint_str = endpoint.value if hasattr(endpoint, "value") else str(endpoint)
                        # Convert path to type name
                        endpoint_type = endpoint_path_to_type.get(endpoint_str.lower(), endpoint_str.upper())
                        if endpoint_type not in endpoint_values:
                            endpoint_values.append(endpoint_type)
                    model_endpoints = ",".join(endpoint_values) if endpoint_values else None

                response = await DaprService.invoke_service(
                    app_id=app_settings.bud_simulator_app_id,
                    method_path="simulator/run",
                    method="POST",
                    data={
                        "pretrained_model_uri": pretrained_model_uri,
                        "input_tokens": deploy_config.get("input_tokens", 1024),
                        "output_tokens": deploy_config.get("output_tokens", 128),
                        "concurrency": deploy_config.get("concurrency", 10),
                        "target_ttft": deploy_config.get("target_ttft", 0),
                        "target_throughput_per_user": deploy_config.get("target_throughput_per_user", 0),
                        "target_e2e_latency": deploy_config.get("target_e2e_latency", 0),
                        "notification_metadata": notification_metadata.model_dump(),
                        "source_topic": app_settings.source_topic,
                        "hardware_mode": hardware_mode,
                        "is_proprietary_model": False,
                        "model_endpoints": model_endpoints,
                    },
                )

                sim_workflow_id = response.get("workflow_id")
                workflow_ids.append(str(sim_workflow_id))
                results.append(
                    {
                        "model_id": str(model.get("model_id", "")),
                        "model_uri": model.get("model_uri", ""),
                        "workflow_id": str(sim_workflow_id),
                        "status": "running",
                    }
                )

            except Exception as e:
                logger.error(f"Failed to trigger simulation for model {model.get('model_uri')}: {e}")
                results.append(
                    {
                        "model_id": str(model.get("model_id", "")),
                        "model_uri": model.get("model_uri", ""),
                        "workflow_id": None,
                        "status": "failed",
                        "error": str(e),
                    }
                )

        logger.info(f"Triggered {len(workflow_ids)} simulations for cluster recommendation")

        return {
            "workflow_ids": workflow_ids,
            "results": results,
            "total_models": len(models),
            "successful": len(workflow_ids),
            "failed": len(models) - len(workflow_ids),
        }

    async def refresh_simulation_status(
        self,
        simulation_events: dict,
    ) -> dict:
        """Refresh simulation status by checking budsim recommendations for each running simulation.

        Args:
            simulation_events: Current simulation_events dict with results

        Returns:
            Updated simulation_events with refreshed statuses
        """
        import aiohttp

        from budapp.commons.config import app_settings

        results = simulation_events.get("results", [])
        if not results:
            return simulation_events

        updated_results = []
        successful_count = 0
        failed_count = 0

        for result in results:
            sim_workflow_id = result.get("workflow_id")
            current_status = result.get("status")

            # Only check running simulations
            if current_status != "running" or not sim_workflow_id:
                updated_results.append(result)
                if current_status == "success":
                    successful_count += 1
                elif current_status == "failed":
                    failed_count += 1
                continue

            # Query budsim for recommendations
            try:
                recommendations_endpoint = (
                    f"{app_settings.dapr_base_url}/v1.0/invoke/"
                    f"{app_settings.bud_simulator_app_id}/method/simulator/recommendations"
                )
                query_params = {"workflow_id": str(sim_workflow_id), "limit": 20}

                async with aiohttp.ClientSession() as session:
                    async with session.get(recommendations_endpoint, params=query_params) as response:
                        if response.status == 200:
                            response_data = await response.json()
                            if response_data.get("object") != "error" and response_data.get("items"):
                                # Simulation completed successfully - has recommendations
                                updated_result = {
                                    **result,
                                    "status": "success",
                                    "recommendations": response_data.get("items", []),
                                }
                                updated_results.append(updated_result)
                                successful_count += 1
                                logger.info(
                                    f"Simulation {sim_workflow_id} completed with "
                                    f"{len(response_data.get('items', []))} recommendations"
                                )
                            else:
                                # No recommendations yet - still running or no results
                                updated_results.append(result)
                        else:
                            # Error response - keep as running (may be still processing)
                            updated_results.append(result)
            except Exception as e:
                logger.warning(f"Failed to check simulation status for {sim_workflow_id}: {e}")
                updated_results.append(result)

        # Count remaining running
        running_count = len([r for r in updated_results if r.get("status") == "running"])

        result = {
            "results": updated_results,
            "total_models": len(updated_results),
            "successful": successful_count,
            "failed": failed_count,
            "running": running_count,
        }

        # If all simulations complete, compute resource summary (top-level only)
        if running_count == 0 and successful_count > 0:
            resource_summary = await self._compute_cluster_resource_summary(updated_results)
            result["deployable"] = resource_summary["deployable"]
            result["warnings"] = resource_summary["warnings"]
            result["cluster_summary"] = resource_summary["cluster_summary"]

        return result

    async def _compute_cluster_resource_summary(
        self,
        results: list[dict],
    ) -> dict:
        """Compute cluster resource summary for simulation results.

        Uses assignment algorithm to find if a valid model→cluster distribution exists
        where each model is assigned to exactly one cluster without exceeding capacity.

        Args:
            results: List of simulation results with recommendations

        Returns:
            Dict with deployable flag, warnings list, and cluster_summary
        """
        from budapp.cluster_ops.crud import ClusterDataManager

        warnings: list[str] = []
        cluster_summary: dict[str, dict] = {}
        cluster_capacities: dict[str, dict] = {}  # Cache cluster lookups

        # Build model options: {model_uri: [{cluster_id, requirements}, ...]}
        model_options: dict[str, list[dict]] = {}
        all_cluster_ids: set[str] = set()

        for result in results:
            if result.get("status") != "success" or not result.get("recommendations"):
                continue

            model_uri = result.get("model_uri", "unknown")
            if model_uri not in model_options:
                model_options[model_uri] = []

            for rec in result.get("recommendations", []):
                cluster_id = rec.get("cluster_id")
                if not cluster_id:
                    continue

                cluster_id_str = str(cluster_id)
                all_cluster_ids.add(cluster_id_str)

                devices_by_type = self._extract_device_requirements(rec)
                model_options[model_uri].append(
                    {
                        "cluster_id": cluster_id_str,
                        "requirements": devices_by_type,
                    }
                )

        if not model_options:
            return {"deployable": False, "warnings": ["No models with recommendations"], "cluster_summary": {}}

        # Fetch cluster capacities
        if all_cluster_ids:
            try:
                clusters, _ = await ClusterDataManager(self.session).get_available_clusters_by_cluster_ids(
                    [UUID(cid) for cid in all_cluster_ids]
                )

                for cluster in clusters:
                    cluster_id_str = str(cluster.cluster_id)
                    cluster_capacities[cluster_id_str] = {
                        "name": cluster.name,
                        "gpu_available": cluster.gpu_available_workers,
                        "cpu_available": cluster.cpu_available_workers,
                        "hpu_available": cluster.hpu_available_workers,
                    }
            except Exception as e:
                logger.warning(f"Failed to fetch cluster capacities: {e}", exc_info=True)
                warnings.append("Failed to fetch cluster capacity information")

        # Check for models with no valid cluster options
        for model_uri, options in model_options.items():
            valid_options = [opt for opt in options if opt["cluster_id"] in cluster_capacities]
            if not valid_options:
                warnings.append(f"Model '{model_uri}' has no available cluster options")

        # Try to find valid assignment using greedy algorithm
        # Sort models by number of options (ascending) - fewer options = higher priority
        sorted_models = sorted(model_options.items(), key=lambda x: len(x[1]))

        # Track remaining capacity per cluster
        remaining_capacity: dict[str, dict] = {}
        for cluster_id, cap in cluster_capacities.items():
            remaining_capacity[cluster_id] = {
                "gpu": cap["gpu_available"],
                "cpu": cap["cpu_available"],
                "hpu": cap["hpu_available"],
            }

        # Try greedy assignment
        assignment: dict[str, str] = {}  # model_uri → cluster_id
        unassigned_models: list[str] = []

        for model_uri, options in sorted_models:
            assigned = False
            for opt in options:
                cluster_id = opt["cluster_id"]
                if cluster_id not in remaining_capacity:
                    continue

                req = opt["requirements"]
                cap = remaining_capacity[cluster_id]

                # Check if this cluster can fit this model
                if req["gpu"] <= cap["gpu"] and req["cpu"] <= cap["cpu"] and req["hpu"] <= cap["hpu"]:
                    # Assign model to this cluster
                    assignment[model_uri] = cluster_id
                    # Deduct capacity
                    cap["gpu"] -= req["gpu"]
                    cap["cpu"] -= req["cpu"]
                    cap["hpu"] -= req["hpu"]
                    assigned = True
                    break

            if not assigned:
                unassigned_models.append(model_uri)

        # Build cluster summary
        for cluster_id in all_cluster_ids:
            cap = cluster_capacities.get(cluster_id)
            if not cap:
                continue

            assigned_models = [m for m, c in assignment.items() if c == cluster_id]
            total_req = {"gpu": 0, "cpu": 0, "hpu": 0}

            for model_uri in assigned_models:
                for opt in model_options.get(model_uri, []):
                    if opt["cluster_id"] == cluster_id:
                        for dev_type in ["gpu", "cpu", "hpu"]:
                            total_req[dev_type] += opt["requirements"].get(dev_type, 0)
                        break

            cluster_summary[cluster_id] = {
                "cluster_name": cap["name"],
                "assigned_models": assigned_models,
                "total_required": total_req,
                "available": {
                    "gpu": cap["gpu_available"],
                    "cpu": cap["cpu_available"],
                    "hpu": cap["hpu_available"],
                },
            }

        # Determine deployability
        all_deployable = len(unassigned_models) == 0 and len(model_options) > 0

        if unassigned_models:
            warnings.append(
                f"Insufficient cluster resources for {len(unassigned_models)} model(s): {', '.join(unassigned_models)}"
            )

        return {
            "deployable": all_deployable,
            "warnings": warnings,
            "cluster_summary": cluster_summary,
            "suggested_assignment": assignment if all_deployable else None,
        }

    def _extract_device_requirements(self, recommendation: dict) -> dict:
        """Extract device requirements from a recommendation.

        Handles both budsim structures:
        1. New: metrics.device_types[].device_type, metrics.device_types[].num_replicas
        2. Legacy: config.node_groups[].type, config.node_groups[].replicas, tp_size, pp_size

        Args:
            recommendation: A single recommendation dict

        Returns:
            Dict with gpu, cpu, hpu counts
        """
        devices_by_type = {"gpu": 0, "cpu": 0, "hpu": 0}

        metrics = recommendation.get("metrics", {})
        device_types = metrics.get("device_types", [])

        if device_types:
            # New structure from budsim recommendations
            for dt in device_types:
                device_type = dt.get("device_type", "cuda").lower()
                num_replicas = dt.get("num_replicas", 1)

                if device_type in ("cuda", "gpu"):
                    devices_by_type["gpu"] += num_replicas
                elif device_type in ("hpu",):
                    devices_by_type["hpu"] += num_replicas
                else:  # cpu, cpu_high
                    devices_by_type["cpu"] += num_replicas
        else:
            # Legacy structure with config.node_groups
            config = recommendation.get("config", {})
            node_groups = config.get("node_groups", [])
            for ng in node_groups:
                device_type = ng.get("type", "cuda").lower()
                replicas = ng.get("replicas", 1)
                tp_size = ng.get("tp_size", 1)
                pp_size = ng.get("pp_size", 1)
                devices_needed = replicas * tp_size * pp_size

                if device_type in ("cuda", "gpu"):
                    devices_by_type["gpu"] += devices_needed
                elif device_type in ("hpu",):
                    devices_by_type["hpu"] += devices_needed
                else:  # cpu, cpu_high
                    devices_by_type["cpu"] += devices_needed

        return devices_by_type

    async def refresh_deployment_status(
        self,
        deployment_events: dict,
    ) -> dict:
        """Refresh deployment status by checking model deployment workflow statuses.

        Each model deployment creates its own workflow via ModelService.deploy_model_by_step.
        This method queries those workflows directly to get their completion status.

        Args:
            deployment_events: Current deployment_events dict with results containing workflow_id

        Returns:
            Updated deployment_events with refreshed statuses
        """
        results = deployment_events.get("results", [])
        if not results:
            return deployment_events

        # Check if there are any running deployments
        running_deployments = [r for r in results if r.get("status") == "running"]
        if not running_deployments:
            return deployment_events

        # Query each running deployment's workflow status
        updated_results = []
        successful_count = 0
        failed_count = 0

        for result in results:
            if result.get("status") != "running" or not result.get("workflow_id"):
                # Already completed or no workflow_id - keep as is
                if result.get("status") == "success":
                    successful_count += 1
                elif result.get("status") == "failed":
                    failed_count += 1
                updated_results.append(result)
                continue

            try:
                workflow_id = UUID(result["workflow_id"])
                db_workflow = await WorkflowDataManager(self.session).retrieve_by_fields(
                    WorkflowModel, {"id": workflow_id}, missing_ok=True
                )

                if not db_workflow:
                    # Workflow not found - keep as running
                    logger.warning(f"Model deployment workflow {workflow_id} not found")
                    updated_results.append(result)
                    continue

                logger.info(
                    f"Model deployment workflow {workflow_id} status: {db_workflow.status}, "
                    f"result endpoint_name: {result.get('endpoint_name')}"
                )

                if db_workflow.status == WorkflowStatusEnum.COMPLETED:
                    # Workflow completed - find the created endpoint
                    endpoint_id = None
                    endpoint_url = None

                    # Query the endpoint by name (stored in result)
                    endpoint_name = result.get("endpoint_name")
                    if endpoint_name:
                        from budapp.endpoint_ops.crud import EndpointDataManager
                        from budapp.endpoint_ops.models import Endpoint as EndpointModel

                        # First, try to find the endpoint created by this deployment
                        # Use workflow progress if available (contains endpoint_id for cloud models)
                        progress = db_workflow.progress or {}
                        if progress.get("endpoint_id"):
                            endpoint_id = progress["endpoint_id"]
                            endpoint_url = progress.get("endpoint_url")
                            logger.info(f"Found endpoint from workflow progress: endpoint_id={endpoint_id}")
                        else:
                            # Query by name - should be globally unique
                            db_endpoint = await EndpointDataManager(self.session).retrieve_by_fields(
                                EndpointModel,
                                {"name": endpoint_name},
                                missing_ok=True,
                            )
                            if db_endpoint:
                                endpoint_id = str(db_endpoint.id)
                                endpoint_url = db_endpoint.url
                                logger.info(f"Found endpoint by name '{endpoint_name}': endpoint_id={endpoint_id}")
                            else:
                                logger.warning(
                                    f"Workflow {workflow_id} completed but endpoint '{endpoint_name}' not found. "
                                    f"Endpoint creation may have failed."
                                )

                    updated_results.append(
                        {
                            **result,
                            "status": "success",
                            "error": None,
                            "endpoint_id": endpoint_id,
                            "endpoint_url": endpoint_url,
                        }
                    )
                    successful_count += 1
                    logger.info(f"Model deployment workflow {workflow_id} completed: endpoint_id={endpoint_id}")

                elif db_workflow.status == WorkflowStatusEnum.FAILED:
                    # Workflow failed
                    updated_results.append(
                        {
                            **result,
                            "status": "failed",
                            "error": db_workflow.reason or "Deployment failed",
                        }
                    )
                    failed_count += 1
                    logger.warning(f"Model deployment workflow {workflow_id} failed: {db_workflow.reason}")

                else:
                    # Still in progress
                    logger.info(
                        f"Model deployment workflow {workflow_id} still in progress "
                        f"(status={db_workflow.status}, current_step={db_workflow.current_step})"
                    )
                    updated_results.append(result)

            except Exception as e:
                logger.warning(f"Failed to check workflow status for {result.get('workflow_id')}: {e}")
                updated_results.append(result)

        running_count = len([r for r in updated_results if r.get("status") == "running"])

        # Determine overall execution status
        if running_count > 0:
            execution_status = "running"
        elif failed_count > 0:
            execution_status = "completed"  # Some failed but all done
        else:
            execution_status = "completed"

        return {
            "execution_id": deployment_events.get("execution_id"),
            "results": updated_results,
            "total_models": len(updated_results),
            "successful": successful_count,
            "failed": failed_count,
            "running": running_count,
            "execution_status": execution_status,
        }

    async def validate_cluster_assignment(
        self,
        models: list[dict],
        global_cluster_id: UUID | None = None,
        per_model_configs: list[dict] | None = None,
    ) -> dict:
        """Validate that selected clusters have capacity for the models.

        Handles both global cluster_id and per-model cluster overrides.
        Per-model cluster_id takes precedence over global.

        Args:
            models: List of model status dicts (must have model_id or model_uri)
            global_cluster_id: Global cluster_id applied to all models by default
            per_model_configs: Per-model configs with optional cluster_id overrides

        Returns:
            Dict with:
                valid: bool - True if all models can be deployed
                errors: list[str] - Error messages if invalid
                warnings: list[str] - Warning messages
                cluster_assignments: dict - {model_uri: cluster_id} mapping
        """
        from budapp.cluster_ops.crud import ClusterDataManager

        errors: list[str] = []
        warnings: list[str] = []

        # Build per-model config lookup
        config_by_model_id: dict[str, dict] = {}
        config_by_model_uri: dict[str, dict] = {}
        if per_model_configs:
            for pmc in per_model_configs:
                if pmc.get("model_id"):
                    config_by_model_id[str(pmc["model_id"])] = pmc
                if pmc.get("model_uri"):
                    config_by_model_uri[pmc["model_uri"]] = pmc

        # Debug: Log the lookup keys
        logger.debug(f"validate_cluster_assignment: config_by_model_id keys: {list(config_by_model_id.keys())}")
        logger.debug(f"validate_cluster_assignment: config_by_model_uri keys: {list(config_by_model_uri.keys())}")
        logger.debug(f"validate_cluster_assignment: global_cluster_id: {global_cluster_id}")

        # Determine cluster assignment for each model
        # {cluster_id: [{model_uri, requirements}]}
        cluster_models: dict[str, list[dict]] = {}
        model_assignments: dict[str, str] = {}  # model_uri → cluster_id
        models_without_cluster: list[dict] = []  # Store more info for better error messages

        for model in models:
            model_id = model.get("model_id")
            model_uri = model.get("model_uri", "unknown")
            model_id_str = str(model_id) if model_id else None

            # Debug: Log model lookup
            logger.debug(f"validate_cluster_assignment: checking model_id={model_id_str}, model_uri={model_uri}")

            # Determine target cluster (per-model override > global)
            target_cluster_id = None

            # Check per-model config first
            if model_id_str and model_id_str in config_by_model_id:
                target_cluster_id = config_by_model_id[model_id_str].get("cluster_id")
                logger.debug(f"  Found via model_id, cluster_id={target_cluster_id}")
            if not target_cluster_id and model_uri in config_by_model_uri:
                target_cluster_id = config_by_model_uri[model_uri].get("cluster_id")
                logger.debug(f"  Found via model_uri, cluster_id={target_cluster_id}")

            # Fall back to global
            if not target_cluster_id:
                target_cluster_id = global_cluster_id
                if target_cluster_id:
                    logger.debug(f"  Using global cluster_id={target_cluster_id}")

            if not target_cluster_id:
                models_without_cluster.append(
                    {
                        "model_id": model_id_str,
                        "model_uri": model_uri,
                    }
                )
                logger.debug("  No cluster found for model")
                continue

            cluster_id_str = str(target_cluster_id)
            model_assignments[model_uri] = cluster_id_str

            # Track model requirements per cluster
            # Use default requirements (1 CPU) if no simulation data available
            # In real scenario, this should come from simulation results
            requirements = {"gpu": 0, "cpu": 1, "hpu": 0}

            if cluster_id_str not in cluster_models:
                cluster_models[cluster_id_str] = []
            cluster_models[cluster_id_str].append(
                {
                    "model_uri": model_uri,
                    "requirements": requirements,
                }
            )

        # Models without cluster assignment
        if models_without_cluster:
            # Build a helpful error message
            model_details = []
            for m in models_without_cluster:
                if m["model_id"]:
                    model_details.append(f"{m['model_uri']} (id: {m['model_id']})")
                else:
                    model_details.append(m["model_uri"])

            # Check if the issue is model_id mismatch
            if per_model_configs and config_by_model_id:
                # User provided per-model configs but they didn't match
                provided_ids = list(config_by_model_id.keys())
                expected_ids = [m["model_id"] for m in models_without_cluster if m["model_id"]]
                errors.append(
                    f"Cluster assignment failed for {len(models_without_cluster)} model(s): {', '.join(model_details)}. "
                    f"per_model_deployment_configs model_ids {provided_ids} don't match expected model_ids {expected_ids}. "
                    f"Use model_ids from model_statuses or specify model_uri in per_model_deployment_configs."
                )
            else:
                errors.append(
                    f"No cluster specified for {len(models_without_cluster)} model(s): {', '.join(model_details)}. "
                    f"Provide cluster_id globally or in per_model_deployment_configs."
                )

        # Fetch cluster capacities
        cluster_capacities: dict[str, dict] = {}
        all_cluster_ids = list(cluster_models.keys())

        if all_cluster_ids:
            try:
                clusters, _ = await ClusterDataManager(self.session).get_available_clusters_by_cluster_ids(
                    [UUID(cid) for cid in all_cluster_ids]
                )

                for cluster in clusters:
                    cluster_id_str = str(cluster.cluster_id)
                    cluster_capacities[cluster_id_str] = {
                        "name": cluster.name,
                        "gpu_available": cluster.gpu_available_workers,
                        "cpu_available": cluster.cpu_available_workers,
                        "hpu_available": cluster.hpu_available_workers,
                    }
            except Exception as e:
                logger.warning(f"Failed to fetch cluster capacities: {e}", exc_info=True)
                errors.append("Failed to fetch cluster capacity information")

        # Check for missing clusters
        for cluster_id_str in all_cluster_ids:
            if cluster_id_str not in cluster_capacities:
                model_uris = [m["model_uri"] for m in cluster_models[cluster_id_str]]
                errors.append(
                    f"Cluster {cluster_id_str} not found or unavailable (assigned to: {', '.join(model_uris)})"
                )

        # Validate capacity for each cluster
        for cluster_id_str, models_list in cluster_models.items():
            capacity = cluster_capacities.get(cluster_id_str)
            if not capacity:
                continue

            cluster_name = capacity["name"]

            # Sum total requirements
            total_gpu = sum(m["requirements"].get("gpu", 0) for m in models_list)
            total_cpu = sum(m["requirements"].get("cpu", 0) for m in models_list)
            total_hpu = sum(m["requirements"].get("hpu", 0) for m in models_list)

            # Check capacity
            shortfalls = []
            if total_gpu > capacity["gpu_available"]:
                shortfalls.append(f"GPU: need {total_gpu}, have {capacity['gpu_available']}")
            if total_cpu > capacity["cpu_available"]:
                shortfalls.append(f"CPU: need {total_cpu}, have {capacity['cpu_available']}")
            if total_hpu > capacity["hpu_available"]:
                shortfalls.append(f"HPU: need {total_hpu}, have {capacity['hpu_available']}")

            if shortfalls:
                model_uris = [m["model_uri"] for m in models_list]
                errors.append(
                    f"Cluster '{cluster_name}' has insufficient resources for {len(models_list)} model(s) "
                    f"({', '.join(model_uris)}): {', '.join(shortfalls)}"
                )

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "cluster_assignments": model_assignments,
        }

    async def get_pipeline_execution_progress(
        self,
        execution_id: str,
    ) -> dict:
        """Get progress of a pipeline execution.

        Args:
            execution_id: The pipeline execution ID

        Returns:
            Dict with execution status, progress percentage, and step details
        """
        pipeline_service = BudPipelineService(self.session)
        return await pipeline_service.get_execution_progress(execution_id)

    # =========================================================================
    # Workflow Cancellation with Rollback
    # =========================================================================

    async def cancel_workflow_with_rollback(
        self,
        workflow_id: UUID,
        reason: str = "User cancelled",
    ) -> dict:
        """Cancel a guardrail deployment workflow and rollback any partial deployments.

        This method performs cleanup in the following order:
        1. Mark workflow as CANCELLED
        2. Delete GuardrailDeployment records created by the workflow
        3. Remove guardrail config from Redis (guardrail_table, model_table)
        4. Delete endpoints created by the workflow (if any)
        5. Keep onboarded models (models are NOT deleted)

        Args:
            workflow_id: The workflow ID to cancel
            reason: Reason for cancellation

        Returns:
            Dict with rollback status and cleanup details
        """
        rollback_result = {
            "workflow_id": str(workflow_id),
            "status": "success",
            "reason": reason,
            "cleaned_up": {
                "deployments": 0,
                "redis_keys": 0,
                "endpoints": 0,
            },
            "preserved": {
                "onboarded_models": 0,
            },
            "errors": [],
        }

        try:
            # Get workflow and verify it exists
            db_workflow = await WorkflowDataManager(self.session).retrieve_by_fields(
                WorkflowModel, {"id": workflow_id}
            )

            if not db_workflow:
                return {"status": "error", "message": "Workflow not found"}

            # Get workflow steps to find what was deployed
            db_workflow_steps = await WorkflowStepDataManager(self.session).get_all_workflow_steps(
                {"workflow_id": workflow_id}
            )

            # Collect deployed resources from step data
            profile_id = None
            endpoint_ids = []
            deployment_ids = []
            deployed_endpoint_ids = []

            for db_step in db_workflow_steps:
                step_data = db_step.data or {}
                if step_data.get("profile_id"):
                    profile_id = step_data["profile_id"]
                if step_data.get("endpoint_ids"):
                    endpoint_ids.extend(step_data["endpoint_ids"])
                if step_data.get("deployment"):
                    for dep in step_data["deployment"]:
                        if dep.get("id"):
                            deployment_ids.append(dep["id"])
                if step_data.get("deployed_endpoint_ids"):
                    deployed_endpoint_ids.extend(step_data["deployed_endpoint_ids"])

            # 1. Delete GuardrailDeployment records
            if profile_id:
                try:
                    deployments = await GuardrailsDeploymentDataManager(self.session).get_all_by_fields(
                        GuardrailDeployment, {"profile_id": profile_id}
                    )
                    for deployment in deployments:
                        await GuardrailsDeploymentDataManager(self.session).update_by_fields(
                            deployment, {"status": GuardrailDeploymentStatusEnum.DELETED}
                        )
                        rollback_result["cleaned_up"]["deployments"] += 1
                except Exception as e:
                    rollback_result["errors"].append(f"Failed to delete deployments: {e}")
                    logger.error(f"Rollback: Failed to delete deployments for profile {profile_id}: {e}")

            # 2. Remove guardrail config from Redis
            if profile_id:
                try:
                    redis_service = RedisService()

                    # Delete guardrail_table entry
                    guardrail_key = f"guardrail_table:{profile_id}"
                    await redis_service.delete(guardrail_key)
                    rollback_result["cleaned_up"]["redis_keys"] += 1

                    # Remove guardrail_profile reference from model_table entries
                    for endpoint_id in endpoint_ids:
                        model_key = f"model_table:{endpoint_id}"
                        existing_config = await redis_service.get(model_key)
                        if existing_config:
                            import json

                            model_config = json.loads(existing_config)
                            if str(endpoint_id) in model_config:
                                model_config[str(endpoint_id)].pop("guardrail_profile", None)
                                await redis_service.set(model_key, json.dumps(model_config))
                                rollback_result["cleaned_up"]["redis_keys"] += 1

                except Exception as e:
                    rollback_result["errors"].append(f"Failed to clean Redis: {e}")
                    logger.error(f"Rollback: Failed to clean Redis for profile {profile_id}: {e}")

            # 3. Delete endpoints that were created by this workflow
            # Only delete endpoints that are specifically from guardrail deployment
            if deployed_endpoint_ids:
                try:
                    for endpoint_id in deployed_endpoint_ids:
                        endpoint_uuid = UUID(endpoint_id) if isinstance(endpoint_id, str) else endpoint_id
                        endpoint = await EndpointDataManager(self.session).retrieve_by_fields(
                            Endpoint, {"id": endpoint_uuid}, missing_ok=True
                        )
                        if endpoint:
                            await EndpointDataManager(self.session).update_by_fields(
                                endpoint, {"status": EndpointStatusEnum.DELETED}
                            )
                            rollback_result["cleaned_up"]["endpoints"] += 1
                except Exception as e:
                    rollback_result["errors"].append(f"Failed to delete endpoints: {e}")
                    logger.error(f"Rollback: Failed to delete endpoints: {e}")

            # 4. Mark workflow as FAILED (no CANCELLED status exists - cancelled workflows use FAILED)
            await WorkflowDataManager(self.session).update_by_fields(
                db_workflow,
                {"status": WorkflowStatusEnum.FAILED, "reason": reason or "Cancelled by user"},
            )

            # Note: Onboarded models are intentionally NOT deleted (J2 option)
            # Count models that were onboarded and will be preserved
            for db_step in db_workflow_steps:
                step_data = db_step.data or {}
                if step_data.get("model_statuses"):
                    for model_status in step_data["model_statuses"]:
                        if model_status.get("model_id"):
                            rollback_result["preserved"]["onboarded_models"] += 1

            logger.info(
                f"Workflow {workflow_id} cancelled with rollback: "
                f"deleted {rollback_result['cleaned_up']['deployments']} deployments, "
                f"cleaned {rollback_result['cleaned_up']['redis_keys']} redis keys, "
                f"preserved {rollback_result['preserved']['onboarded_models']} onboarded models"
            )

            if rollback_result["errors"]:
                rollback_result["status"] = "partial"

            return rollback_result

        except Exception as e:
            logger.exception(f"Rollback failed for workflow {workflow_id}: {e}")
            return {
                "workflow_id": str(workflow_id),
                "status": "error",
                "message": str(e),
                "errors": [str(e)],
            }


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
            raise ClientException(status_code=HTTPStatus.HTTP_403_FORBIDDEN, message="Preset probes cannot be edited")

        # Check if user has permission to edit (must be the creator)
        if user_id and db_probe.created_by != user_id:
            raise ClientException(
                status_code=HTTPStatus.HTTP_403_FORBIDDEN, message="You do not have permission to edit this probe"
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
            raise ClientException(status_code=HTTPStatus.HTTP_403_FORBIDDEN, message="Preset probes cannot be deleted")

        # Check if user has permission to delete (must be the creator)
        if user_id and db_probe.created_by != user_id:
            raise ClientException(
                status_code=HTTPStatus.HTTP_403_FORBIDDEN, message="You do not have permission to delete this probe"
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
            raise ClientException(status_code=HTTPStatus.HTTP_403_FORBIDDEN, message="Preset rules cannot be edited")

        # Check if user has permission to edit (must be the creator)
        if user_id and db_rule.created_by != user_id:
            raise ClientException(
                status_code=HTTPStatus.HTTP_403_FORBIDDEN, message="You do not have permission to edit this rule"
            )

        # Prepare update data
        update_data = {}
        if name is not None:
            update_data["name"] = name
        if description is not None:
            update_data["description"] = description
        if status is not None:
            update_data["status"] = status
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
            raise ClientException(status_code=HTTPStatus.HTTP_403_FORBIDDEN, message="Preset rules cannot be deleted")

        # Check if user has permission to delete (must be the creator)
        if user_id and db_rule.created_by != user_id:
            raise ClientException(
                status_code=HTTPStatus.HTTP_403_FORBIDDEN, message="You do not have permission to delete this rule"
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

        if not db_profiles:
            return [], count

        profile_ids = [db_profile[0].id for db_profile in db_profiles]

        # Bulk fetch probe counts to avoid N+1 queries
        probe_counts_q = (
            select(GuardrailProfileProbe.profile_id, func.count(GuardrailProfileProbe.id).label("probe_count"))
            .where(GuardrailProfileProbe.profile_id.in_(profile_ids))
            .group_by(GuardrailProfileProbe.profile_id)
        )
        probe_counts_result = self.session.execute(probe_counts_q)
        probe_counts = {row.profile_id: row.probe_count for row in probe_counts_result.all()}

        # Bulk fetch deployment counts and standalone status
        deployment_counts_q = (
            select(
                GuardrailDeployment.profile_id,
                func.count(GuardrailDeployment.id).label("deployment_count"),
                func.bool_or(GuardrailDeployment.endpoint_id.is_(None)).label("is_standalone"),
            )
            .where(GuardrailDeployment.profile_id.in_(profile_ids))
            .where(GuardrailDeployment.status != GuardrailDeploymentStatusEnum.DELETED)
            .group_by(GuardrailDeployment.profile_id)
        )
        deployment_counts_result = self.session.execute(deployment_counts_q)
        deployment_counts = {
            row.profile_id: (row.deployment_count, bool(row.is_standalone)) for row in deployment_counts_result.all()
        }

        db_profiles_response = []
        for db_profile in db_profiles:
            profile_id = db_profile[0].id
            probe_count = probe_counts.get(profile_id, 0)
            deployment_count, is_standalone = deployment_counts.get(profile_id, (0, False))

            profile_response = GuardrailProfileResponse.model_validate(db_profile[0]).model_copy(
                update={
                    "probe_count": probe_count,
                    "deployment_count": deployment_count,
                    "is_standalone": is_standalone,
                }
            )
            db_profiles_response.append(profile_response)

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
        project_id: Optional[UUID] = None,
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
                project_id=project_id,
            )
        )

        profile_response = GuardrailProfileResponse.model_validate(db_profile).model_copy(
            update={"probe_count": 0, "deployment_count": 0, "is_standalone": False}
        )

        return GuardrailProfileDetailResponse(
            profile=profile_response,
            message="Profile created successfully",
            code=HTTPStatus.HTTP_201_CREATED,
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
            raise ClientException(
                status_code=HTTPStatus.HTTP_403_FORBIDDEN, message="Preset profiles cannot be deleted"
            )

        # Check if user has permission to delete (must be the creator)
        if user_id and db_profile.created_by != user_id:
            raise ClientException(
                status_code=HTTPStatus.HTTP_403_FORBIDDEN, message="You do not have permission to delete this profile"
            )

        # Soft delete the profile
        try:
            await GuardrailsDeploymentDataManager(self.session).soft_delete_profile(profile_id)
        except ValueError as e:
            # Convert DatabaseException to ClientException for proper API error handling
            raise ClientException(message=getattr(e, "message", str(e)), status_code=HTTPStatus.HTTP_403_FORBIDDEN)

        # Delete profile cache
        await GuardrailDeploymentWorkflowService(self.session).delete_guardrail_profile_cache(profile_id)

        return SuccessResponse(
            message="Profile deleted successfully", code=HTTPStatus.HTTP_200_OK, object="guardrail.profile.delete"
        )

    async def update_profile_with_probes(
        self,
        profile_id: UUID,
        user_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[list[Tag]] = None,
        severity_threshold: Optional[float] = None,
        guard_types: Optional[list[str]] = None,
        probe_selections: Optional[list[GuardrailProfileProbeSelection]] = None,
    ) -> GuardrailProfileDetailResponse:
        """Update a guardrail profile with probe selections.

        This method updates both profile fields and probe/rule selections.
        Users can only update profiles they created.
        Preset profiles (created_by is None) cannot be edited.
        """
        # Retrieve the profile
        db_profile = await GuardrailsDeploymentDataManager(self.session).retrieve_by_fields(
            GuardrailProfile, {"id": profile_id}
        )

        # Check if profile is a preset profile (no creator)
        if db_profile.created_by is None:
            raise ClientException(
                status_code=HTTPStatus.HTTP_403_FORBIDDEN, message="Preset profiles cannot be edited"
            )

        # Check if user has permission to edit (must be the creator)
        if user_id and db_profile.created_by != user_id:
            raise ClientException(
                status_code=HTTPStatus.HTTP_403_FORBIDDEN, message="You do not have permission to edit this profile"
            )

        # Start a transaction
        savepoint = self.session.begin_nested()

        try:
            # Update basic profile fields
            update_data = {}
            if name is not None:
                update_data["name"] = name
            if description is not None:
                update_data["description"] = description
            if tags is not None:
                update_data["tags"] = [{"name": tag.name, "color": tag.color} for tag in tags]
            if severity_threshold is not None:
                update_data["severity_threshold"] = severity_threshold
            if guard_types is not None:
                update_data["guard_types"] = guard_types

            # Update the profile if there are changes
            if update_data:
                # Don't use update_by_fields as it commits and breaks the savepoint
                for field, value in update_data.items():
                    setattr(db_profile, field, value)
                updated_profile = db_profile
            else:
                updated_profile = db_profile

            # Handle probe selections if provided
            if probe_selections is not None:
                # Get existing profile probes
                existing_probes_stmt = select(GuardrailProfileProbe).where(
                    GuardrailProfileProbe.profile_id == profile_id
                )
                existing_probes = self.session.execute(existing_probes_stmt).scalars().all()
                existing_probe_ids = {probe.probe_id: probe for probe in existing_probes}

                # Get new probe IDs from selections
                new_probe_ids = {selection.id for selection in probe_selections}

                # Delete probes that are no longer selected
                probes_to_delete = set(existing_probe_ids.keys()) - new_probe_ids
                if probes_to_delete:
                    # Delete associated rules first
                    for probe_id in probes_to_delete:
                        profile_probe = existing_probe_ids[probe_id]
                        delete_rules_stmt = delete(GuardrailProfileRule).where(
                            GuardrailProfileRule.profile_probe_id == profile_probe.id
                        )
                        self.session.execute(delete_rules_stmt)

                    # Delete the profile probes
                    delete_probes_stmt = (
                        delete(GuardrailProfileProbe)
                        .where(GuardrailProfileProbe.profile_id == profile_id)
                        .where(GuardrailProfileProbe.probe_id.in_(probes_to_delete))
                    )
                    self.session.execute(delete_probes_stmt)

                # Process each probe selection
                for probe_selection in probe_selections:
                    probe_id = probe_selection.id

                    if probe_id in existing_probe_ids:
                        # Update existing probe
                        profile_probe = existing_probe_ids[probe_id]
                        probe_update = {}
                        if probe_selection.severity_threshold is not None:
                            probe_update["severity_threshold"] = probe_selection.severity_threshold
                        if probe_selection.guard_types is not None:
                            probe_update["guard_types"] = probe_selection.guard_types

                        if probe_update:
                            # Don't use update_by_fields as it commits and breaks the savepoint
                            for field, value in probe_update.items():
                                setattr(profile_probe, field, value)

                        # Handle rule updates for this probe
                        if probe_selection.rules:
                            await self._update_profile_probe_rules(profile_probe.id, probe_selection.rules, user_id)
                    else:
                        # Add new probe
                        db_profile_probe = GuardrailProfileProbe(
                            profile_id=profile_id,
                            probe_id=probe_id,
                            severity_threshold=probe_selection.severity_threshold,
                            guard_types=probe_selection.guard_types,
                            created_by=user_id,
                        )
                        self.session.add(db_profile_probe)
                        self.session.flush()

                        # Add rule overrides if specified
                        if probe_selection.rules:
                            for rule_selection in probe_selection.rules:
                                # Only create rule override if it has specific settings
                                if (
                                    rule_selection.status == GuardrailStatusEnum.DISABLED
                                    or rule_selection.severity_threshold is not None
                                    or rule_selection.guard_types is not None
                                ):
                                    db_profile_rule = GuardrailProfileRule(
                                        profile_probe_id=db_profile_probe.id,
                                        rule_id=rule_selection.id,
                                        status=rule_selection.status,
                                        severity_threshold=rule_selection.severity_threshold,
                                        guard_types=rule_selection.guard_types,
                                        created_by=user_id,
                                    )
                                    self.session.add(db_profile_rule)

            # Commit the transaction
            savepoint.commit()

            # Update the cache after profile update
            await GuardrailDeploymentWorkflowService(self.session).update_guardrail_profile_cache(profile_id)

            probe_count, deployment_count, is_standalone = await GuardrailsDeploymentDataManager(
                self.session
            ).get_profile_counts(profile_id)

            profile_response = GuardrailProfileResponse.model_validate(updated_profile).model_copy(
                update={
                    "probe_count": probe_count,
                    "deployment_count": deployment_count,
                    "is_standalone": is_standalone,
                }
            )

            return GuardrailProfileDetailResponse(
                profile=profile_response,
                message="Profile updated successfully",
                code=HTTPStatus.HTTP_200_OK,
            )

        except Exception as e:
            # Rollback on error
            if savepoint and savepoint.is_active:
                savepoint.rollback()
            logger.exception(f"Failed to update profile with probes: {e}")
            raise ClientException(
                status_code=HTTPStatus.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to update profile"
            )

    async def _update_profile_probe_rules(
        self,
        profile_probe_id: UUID,
        rule_selections: List[GuardrailProbeRuleSelection],
        user_id: UUID,
    ) -> None:
        """Update rules for a specific probe in a profile."""
        # Get existing rules for this profile probe
        existing_rules_stmt = select(GuardrailProfileRule).where(
            GuardrailProfileRule.profile_probe_id == profile_probe_id
        )
        existing_rules = self.session.execute(existing_rules_stmt).scalars().all()
        existing_rule_ids = {rule.rule_id: rule for rule in existing_rules}

        # Get new rule IDs
        new_rule_ids = {selection.id for selection in rule_selections}

        # Delete rules that are no longer overridden
        rules_to_delete = set(existing_rule_ids.keys()) - new_rule_ids
        if rules_to_delete:
            delete_rules_stmt = (
                delete(GuardrailProfileRule)
                .where(GuardrailProfileRule.profile_probe_id == profile_probe_id)
                .where(GuardrailProfileRule.rule_id.in_(rules_to_delete))
            )
            self.session.execute(delete_rules_stmt)

        # Process each rule selection
        for rule_selection in rule_selections:
            rule_id = rule_selection.id

            # Only process if rule has specific overrides
            if (
                rule_selection.status == GuardrailStatusEnum.DISABLED
                or rule_selection.severity_threshold is not None
                or rule_selection.guard_types is not None
            ):
                if rule_id in existing_rule_ids:
                    # Update existing rule override
                    rule_override = existing_rule_ids[rule_id]
                    rule_update = {}
                    if rule_selection.status is not None:
                        rule_update["status"] = rule_selection.status
                    if rule_selection.severity_threshold is not None:
                        rule_update["severity_threshold"] = rule_selection.severity_threshold
                    if rule_selection.guard_types is not None:
                        rule_update["guard_types"] = rule_selection.guard_types

                    if rule_update:
                        # Don't use update_by_fields as it commits and breaks the savepoint
                        for field, value in rule_update.items():
                            setattr(rule_override, field, value)
                else:
                    # Add new rule override
                    db_profile_rule = GuardrailProfileRule(
                        profile_probe_id=profile_probe_id,
                        rule_id=rule_id,
                        status=rule_selection.status,
                        severity_threshold=rule_selection.severity_threshold,
                        guard_types=rule_selection.guard_types,
                        created_by=user_id,
                    )
                    self.session.add(db_profile_rule)
            elif rule_id in existing_rule_ids:
                # Remove rule override if it no longer has specific settings
                delete_rule_stmt = (
                    delete(GuardrailProfileRule)
                    .where(GuardrailProfileRule.profile_probe_id == profile_probe_id)
                    .where(GuardrailProfileRule.rule_id == rule_id)
                )
                self.session.execute(delete_rule_stmt)

    async def retrieve_profile(self, profile_id: UUID) -> GuardrailProfileDetailResponse:
        """Retrieve a specific profile by ID."""
        deployment_data_manager = GuardrailsDeploymentDataManager(self.session)
        db_profile = await deployment_data_manager.retrieve_by_fields(
            GuardrailProfile, {"id": profile_id, "status": GuardrailStatusEnum.ACTIVE}
        )
        probe_count, deployment_count, is_standalone = await deployment_data_manager.get_profile_counts(profile_id)

        profile_response = GuardrailProfileResponse.model_validate(db_profile).model_copy(
            update={
                "probe_count": probe_count,
                "deployment_count": deployment_count,
                "is_standalone": is_standalone,
            }
        )

        return GuardrailProfileDetailResponse(
            profile=profile_response,
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

    async def list_deployments(
        self,
        offset: int = 0,
        limit: int = 10,
        filters: dict[str, Any] = {},
        order_by: list = [],
        search: bool = False,
    ) -> Tuple[list[GuardrailDeploymentResponse], int]:
        """List guardrail deployments with pagination.

        Args:
            offset: Number of records to skip
            limit: Maximum number of records to return
            filters: Dictionary of filters to apply
            order_by: List of fields to order by
            search: Whether to use search filters

        Returns:
            Tuple of list of deployments and total count
        """
        db_deployments, count = await GuardrailsDeploymentDataManager(self.session).get_all_deployments(
            offset, limit, filters, order_by, search
        )

        if not db_deployments:
            return [], count

        endpoint_ids = [deployment[0].endpoint_id for deployment in db_deployments if deployment[0].endpoint_id]
        endpoint_names: dict[UUID, str] = {}

        if endpoint_ids:
            endpoint_rows = self.session.execute(
                select(Endpoint.id, Endpoint.name).where(Endpoint.id.in_(endpoint_ids))
            ).all()
            endpoint_names = {row.id: row.name for row in endpoint_rows}

        db_deployments_response = [
            GuardrailDeploymentResponse.model_validate(db_deployment[0]).model_copy(
                update={"endpoint_name": endpoint_names.get(db_deployment[0].endpoint_id)}
            )
            for db_deployment in db_deployments
        ]

        return db_deployments_response, count

    async def retrieve_deployment(self, deployment_id: UUID) -> GuardrailDeploymentDetailResponse:
        """Retrieve a specific deployment by ID."""
        # First get the deployment by ID
        db_deployment = await GuardrailsDeploymentDataManager(self.session).retrieve_by_fields(
            GuardrailDeployment, {"id": deployment_id}, exclude_fields={"status": GuardrailStatusEnum.DELETED}
        )

        if not db_deployment:
            raise ClientException(message="Deployment not found", status_code=HTTPStatus.HTTP_404_NOT_FOUND)

        endpoint_name = None
        if db_deployment.endpoint_id:
            endpoint_name = self.session.execute(
                select(Endpoint.name).where(Endpoint.id == db_deployment.endpoint_id)
            ).scalar_one_or_none()

        deployment_response = GuardrailDeploymentResponse.model_validate(db_deployment).model_copy(
            update={"endpoint_name": endpoint_name}
        )

        return GuardrailDeploymentDetailResponse(
            deployment=deployment_response, message="Deployment retrieved successfully", code=HTTPStatus.HTTP_200_OK
        )

    async def edit_deployment(
        self,
        deployment_id: UUID,
        user_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        severity_threshold: Optional[float] = None,
        guard_types: Optional[list[str]] = None,
    ) -> GuardrailDeploymentDetailResponse:
        """Edit an existing guardrail deployment.

        Users can only edit deployments they created.
        Only specific fields can be updated: name, description, severity_threshold, guard_types
        """
        # Retrieve the deployment
        db_deployment = await GuardrailsDeploymentDataManager(self.session).retrieve_by_fields(
            GuardrailDeployment, {"id": deployment_id}, exclude_fields={"status": GuardrailStatusEnum.DELETED}
        )

        if not db_deployment:
            raise ClientException(message="Deployment not found", status_code=HTTPStatus.HTTP_404_NOT_FOUND)

        # Check if user has permission to edit (must be the creator)
        if user_id and db_deployment.created_by != user_id:
            raise ClientException(
                status_code=HTTPStatus.HTTP_403_FORBIDDEN, message="You do not have permission to edit this deployment"
            )

        # Prepare update data
        update_data = {}
        if name is not None:
            update_data["name"] = name
        if description is not None:
            update_data["description"] = description
        if severity_threshold is not None:
            update_data["severity_threshold"] = severity_threshold
        if guard_types is not None:
            update_data["guard_types"] = guard_types

        # Update the deployment
        if update_data:
            updated_deployment = await GuardrailsDeploymentDataManager(self.session).update_by_fields(
                db_deployment, update_data
            )
            # Update the cache after deployment update
            await GuardrailDeploymentWorkflowService(self.session).update_guardrail_profile_cache(
                db_deployment.profile_id
            )
        else:
            updated_deployment = db_deployment

        return GuardrailDeploymentDetailResponse(
            deployment=updated_deployment,
            message="Deployment updated successfully",
            code=HTTPStatus.HTTP_200_OK,
        )

    async def delete_deployment(self, deployment_id: UUID, user_id: UUID) -> dict:
        """Delete (soft delete) a guardrail deployment.

        Users can only delete deployments they created.
        """
        # Retrieve the deployment
        db_deployment = await GuardrailsDeploymentDataManager(self.session).retrieve_by_fields(
            GuardrailDeployment, {"id": deployment_id}, exclude_fields={"status": GuardrailStatusEnum.DELETED}
        )

        if not db_deployment:
            raise ClientException(message="Deployment not found", status_code=HTTPStatus.HTTP_404_NOT_FOUND)

        # Check if user has permission to delete (must be the creator)
        if user_id and db_deployment.created_by != user_id:
            raise ClientException(
                status_code=HTTPStatus.HTTP_403_FORBIDDEN,
                message="You do not have permission to delete this deployment",
            )

        # Soft delete the deployment
        await GuardrailsDeploymentDataManager(self.session).soft_delete_deployment(deployment_id)

        # Delete from proxy cache
        if db_deployment.endpoint_id:
            await GuardrailDeploymentWorkflowService(self.session).delete_guardrail_deployment_from_proxy_cache(
                db_deployment.endpoint_id
            )

        # Delete profile cache
        await GuardrailDeploymentWorkflowService(self.session).delete_guardrail_profile_cache(db_deployment.profile_id)

        return SuccessResponse(
            message="Deployment deleted successfully",
            code=HTTPStatus.HTTP_200_OK,
            object="guardrail.deployment.delete",
        )


class GuardrailCustomProbeService(SessionMixin):
    """Service for managing custom model-based guardrail probes."""

    async def create_custom_probe(
        self,
        request: GuardrailCustomProbeCreate,
        project_id: UUID,
        user_id: UUID,
    ) -> GuardrailProbe:
        """Create a custom model-based probe with a single rule.

        Args:
            request: Custom probe creation request
            project_id: Project ID for the probe
            user_id: User ID of the creator

        Returns:
            The created GuardrailProbe instance

        Raises:
            ClientException: If model not found or validation fails
        """
        from budapp.model_ops.crud import ModelDataManager
        from budapp.model_ops.models import Model

        # Get the model to extract URI and other details
        model_data_manager = ModelDataManager(self.session)
        db_model = await model_data_manager.retrieve_by_fields(Model, {"id": request.model_id})
        if not db_model:
            raise ClientException(
                message=f"Model {request.model_id} not found",
                status_code=HTTPStatus.HTTP_404_NOT_FOUND,
            )

        # Get the BudSentinel provider for custom probes
        provider = await ProviderDataManager(self.session).retrieve_by_fields(Provider, {"type": "bud_sentinel"})
        if not provider:
            raise ClientException(
                message="BudSentinel provider not found",
                status_code=HTTPStatus.HTTP_404_NOT_FOUND,
            )

        # Extract model config as dict
        model_config = request.model_config_data.model_dump()

        # Create the custom probe with its rule
        probe = await GuardrailsDeploymentDataManager(self.session).create_custom_probe_with_rule(
            name=request.name,
            description=request.description,
            scanner_type=request.scanner_type.value,
            model_id=request.model_id,
            model_config=model_config,
            model_uri=db_model.uri or f"model://{db_model.id}",
            model_provider_type=db_model.provider_type,
            is_gated=False,
            user_id=user_id,
            provider_id=provider.id,
        )

        return probe

    async def update_custom_probe(
        self,
        probe_id: UUID,
        request: GuardrailCustomProbeUpdate,
        user_id: UUID,
    ) -> GuardrailProbe:
        """Update a custom probe (user must be owner).

        Args:
            probe_id: ID of the probe to update
            request: Update request with fields to modify
            user_id: User ID making the request

        Returns:
            The updated GuardrailProbe instance

        Raises:
            ClientException: If probe not found or user not authorized
        """
        data_manager = GuardrailsDeploymentDataManager(self.session)

        # Retrieve the probe
        db_probe = await data_manager.retrieve_by_fields(
            GuardrailProbe, {"id": probe_id, "status": GuardrailStatusEnum.ACTIVE}
        )
        if not db_probe:
            raise ClientException(
                message="Custom probe not found",
                status_code=HTTPStatus.HTTP_404_NOT_FOUND,
            )

        # Check ownership
        if db_probe.created_by != user_id:
            raise ClientException(
                message="You do not have permission to update this probe",
                status_code=HTTPStatus.HTTP_403_FORBIDDEN,
            )

        # Prepare update data
        update_data = {}
        if request.name is not None:
            update_data["name"] = request.name
        if request.description is not None:
            update_data["description"] = request.description

        # Update probe
        if update_data:
            db_probe = await data_manager.update_by_fields(db_probe, update_data)

        # Update the rule's model_config if provided
        if request.model_config_data is not None:
            rule_stmt = select(GuardrailRule).where(GuardrailRule.probe_id == probe_id)
            db_rule = self.session.scalars(rule_stmt).first()
            if db_rule:
                db_rule.model_config_json = request.model_config_data.model_dump()
                if request.name is not None:
                    db_rule.name = request.name
                if request.description is not None:
                    db_rule.description = request.description
                self.session.add(db_rule)
                self.session.commit()

        return db_probe

    async def delete_custom_probe(
        self,
        probe_id: UUID,
        user_id: UUID,
    ) -> None:
        """Delete a custom probe (soft delete, user must be owner).

        Args:
            probe_id: ID of the probe to delete
            user_id: User ID making the request

        Raises:
            ClientException: If probe not found or user not authorized
        """
        data_manager = GuardrailsDeploymentDataManager(self.session)

        # Retrieve the probe
        db_probe = await data_manager.retrieve_by_fields(
            GuardrailProbe, {"id": probe_id, "status": GuardrailStatusEnum.ACTIVE}
        )
        if not db_probe:
            raise ClientException(
                message="Custom probe not found",
                status_code=HTTPStatus.HTTP_404_NOT_FOUND,
            )

        # Check ownership
        if db_probe.created_by != user_id:
            raise ClientException(
                message="You do not have permission to delete this probe",
                status_code=HTTPStatus.HTTP_403_FORBIDDEN,
            )

        # Soft delete the probe and its rules
        await GuardrailsProbeRulesDataManager(self.session).soft_delete_deprecated_probes([str(probe_id)])

    async def add_custom_probe_workflow(
        self,
        current_user_id: UUID,
        request: CustomProbeWorkflowRequest,
    ) -> WorkflowModel:
        """Add custom probe workflow (multi-step).

        Similar to add_guardrail_deployment_workflow but for creating custom probes.

        Step 1: Select probe type -> auto-derive model_uri, scanner_type, etc.
        Step 2: Configure policy
        Step 3: Probe metadata + trigger_workflow -> create probe

        Args:
            current_user_id: ID of the user creating the workflow
            request: Custom probe workflow request with step data

        Returns:
            The workflow model instance
        """
        step_number = request.step_number
        workflow_id = request.workflow_id
        workflow_total_steps = request.workflow_total_steps
        trigger_workflow = request.trigger_workflow

        current_step_number = step_number

        # Retrieve or create workflow
        workflow_create = WorkflowUtilCreate(
            workflow_type=WorkflowTypeEnum.CUSTOM_PROBE_CREATION,
            title="Custom Probe Creation",
            total_steps=workflow_total_steps,
            icon=APP_ICONS["general"]["deployment_mono"],
            tag="Custom Probe",
        )

        db_workflow = await WorkflowService(self.session).retrieve_or_create_workflow(
            workflow_id, workflow_create, current_user_id
        )

        # Get workflow steps to check for existing data
        db_workflow_steps = await WorkflowStepDataManager(self.session).get_all_workflow_steps(
            {"workflow_id": db_workflow.id}
        )

        # Find current workflow step or create one
        db_current_workflow_step = None
        for db_step in db_workflow_steps:
            if db_step.step_number == current_step_number:
                db_current_workflow_step = db_step
                break

        # Get existing step data or initialize empty
        workflow_step_data: Dict[str, Any] = {}

        # Merge data from all previous steps
        for db_step in db_workflow_steps:
            if db_step.data:
                workflow_step_data.update(db_step.data)

        # Step 1 validation: probe_type_option is required at step 1
        if step_number == 1 and not request.probe_type_option:
            raise ClientException(
                message="probe_type_option is required at step 1",
                status_code=HTTPStatus.HTTP_400_BAD_REQUEST,
            )

        # Process all provided request fields (not gated by step_number)
        if request.probe_type_option:
            config = PROBE_TYPE_CONFIGS.get(request.probe_type_option.value)
            if not config:
                raise ClientException(
                    message=f"Unsupported probe type: {request.probe_type_option.value}",
                    status_code=HTTPStatus.HTTP_400_BAD_REQUEST,
                )
            workflow_step_data["probe_type_option"] = request.probe_type_option.value
            workflow_step_data["model_uri"] = config.model_uri
            workflow_step_data["scanner_type"] = config.scanner_type
            workflow_step_data["handler"] = config.handler
            workflow_step_data["model_provider_type"] = config.model_provider_type

        if request.policy:
            workflow_step_data["policy"] = request.policy.model_dump()

        if request.name:
            workflow_step_data["name"] = request.name
            await WorkflowDataManager(self.session).update_by_fields(db_workflow, {"title": request.name})
        if request.description:
            workflow_step_data["description"] = request.description
        if request.guard_types:
            workflow_step_data["guard_types"] = request.guard_types
        if request.modality_types:
            workflow_step_data["modality_types"] = request.modality_types

        # Create or update workflow step
        if db_current_workflow_step:
            # Merge new data with existing step data
            existing_data = db_current_workflow_step.data or {}
            merged_data = {**existing_data, **workflow_step_data}
            workflow_step_data = merged_data

            await WorkflowStepDataManager(self.session).update_by_fields(
                db_current_workflow_step, {"data": workflow_step_data}
            )
        else:
            db_current_workflow_step = await WorkflowStepDataManager(self.session).insert_one(
                WorkflowStepModel(
                    workflow_id=db_workflow.id,
                    step_number=current_step_number,
                    data=workflow_step_data,
                )
            )

        # Update workflow current step
        db_max_workflow_step_number = max(step.step_number for step in db_workflow_steps) if db_workflow_steps else 0
        workflow_current_step = max(current_step_number, db_max_workflow_step_number)
        await WorkflowDataManager(self.session).update_by_fields(db_workflow, {"current_step": workflow_current_step})

        # Execute workflow if triggered at step 3
        if trigger_workflow and step_number == 3:
            # Validate required fields before workflow execution
            required_keys = ["name", "scanner_type", "policy"]
            missing_keys = [key for key in required_keys if key not in workflow_step_data]
            if missing_keys:
                raise ClientException(
                    message=f"Missing required data for custom probe workflow: {', '.join(missing_keys)}",
                    status_code=HTTPStatus.HTTP_400_BAD_REQUEST,
                )
            await self._execute_custom_probe_workflow(
                data=workflow_step_data,
                workflow_id=db_workflow.id,
                current_user_id=current_user_id,
            )

        return db_workflow

    async def _execute_custom_probe_workflow(
        self,
        data: Dict[str, Any],
        workflow_id: UUID,
        current_user_id: UUID,
    ) -> None:
        """Execute custom probe workflow - create the probe.

        This method is called when trigger_workflow=True at step 3.

        Args:
            data: Accumulated workflow step data
            workflow_id: ID of the workflow
            current_user_id: ID of the user executing the workflow
        """
        from budapp.commons.constants import ModelStatusEnum
        from budapp.model_ops.crud import ModelDataManager
        from budapp.model_ops.models import Model

        db_workflow = await WorkflowDataManager(self.session).retrieve_by_fields(WorkflowModel, {"id": workflow_id})
        db_workflow_steps = await WorkflowStepDataManager(self.session).get_all_workflow_steps(
            {"workflow_id": workflow_id}
        )
        db_latest_workflow_step = db_workflow_steps[-1] if db_workflow_steps else None

        execution_status_data: Dict[str, Any] = {
            "workflow_execution_status": {
                "status": "success",
                "message": "Custom probe created successfully",
            },
            "probe_id": None,
        }

        try:
            # Look up model by URI - assign model_id if found
            model_id = None
            model_uri = data.get("model_uri")
            if model_uri:
                model_data_manager = ModelDataManager(self.session)
                existing_model = await model_data_manager.retrieve_by_fields(
                    Model,
                    {"uri": model_uri, "status": ModelStatusEnum.ACTIVE},
                    missing_ok=True,
                )
                if existing_model:
                    model_id = existing_model.id

            # Get BudSentinel provider
            provider = await ProviderDataManager(self.session).retrieve_by_fields(Provider, {"type": "bud_sentinel"})
            if not provider:
                raise ClientException(
                    message="BudSentinel provider not found",
                    status_code=HTTPStatus.HTTP_404_NOT_FOUND,
                )

            # Build LLMConfig with handler and policy
            model_config = LLMConfig(
                handler=data.get("handler", "gpt_safeguard"),
                policy=PolicyConfig(**data["policy"]),
            ).model_dump()

            # Create probe via CRUD method
            probe = await GuardrailsDeploymentDataManager(self.session).create_custom_probe_with_rule(
                name=data["name"],
                description=data.get("description"),
                scanner_type=data["scanner_type"],
                model_id=model_id,
                model_config=model_config,
                model_uri=model_uri,
                model_provider_type=data.get("model_provider_type", "cloud_model"),
                is_gated=False,
                user_id=current_user_id,
                provider_id=provider.id,
                guard_types=data.get("guard_types"),
                modality_types=data.get("modality_types"),
            )

            execution_status_data["probe_id"] = str(probe.id)
            execution_status_data["model_id"] = str(model_id) if model_id else None

            # Mark workflow COMPLETED
            await WorkflowDataManager(self.session).update_by_fields(
                db_workflow, {"status": WorkflowStatusEnum.COMPLETED}
            )

        except Exception as e:
            logger.exception(f"Failed to create custom probe: {e}")
            execution_status_data["workflow_execution_status"] = {
                "status": "error",
                "message": str(e),
            }

            # Mark workflow FAILED
            await WorkflowDataManager(self.session).update_by_fields(
                db_workflow, {"status": WorkflowStatusEnum.FAILED, "reason": str(e)}
            )

        # Update step data with execution status
        if db_latest_workflow_step:
            await WorkflowStepDataManager(self.session).update_by_fields(
                db_latest_workflow_step, {"data": {**data, **execution_status_data}}
            )
