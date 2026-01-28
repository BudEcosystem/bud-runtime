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
    ModelDeploymentStatus,
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
        derive_statuses = request.derive_model_statuses

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
        ).model_dump(exclude_none=True, exclude_unset=True, mode="json")

        # Derive model statuses if requested and probe_selections provided
        if derive_statuses and probe_selections:
            logger.info(f"Deriving model statuses for workflow step {current_step_number}")
            model_status_response = await self.derive_model_statuses(probe_selections, project_id)

            # Add model status data to workflow step data
            workflow_step_data["model_statuses"] = [
                model.model_dump(mode="json") for model in model_status_response.models
            ]
            workflow_step_data["total_models"] = model_status_response.total_models
            workflow_step_data["models_requiring_onboarding"] = model_status_response.models_requiring_onboarding
            workflow_step_data["models_requiring_deployment"] = model_status_response.models_requiring_deployment
            workflow_step_data["models_reusable"] = model_status_response.models_reusable
            workflow_step_data["skip_to_step"] = model_status_response.skip_to_step
            workflow_step_data["credential_required"] = model_status_response.credential_required

            logger.info(
                f"Model status derived: {model_status_response.total_models} models, "
                f"{model_status_response.models_requiring_onboarding} need onboarding, "
                f"{model_status_response.models_requiring_deployment} need deployment, "
                f"skip_to_step={model_status_response.skip_to_step}"
            )

        # Get workflow steps
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
            db_profile = await self._execute_add_guardrail_deployment_workflow(
                required_data, db_workflow.id, current_user_id
            )
            logger.debug(f"Successfully created guardrail deployment profile {db_profile.id}")

        return db_workflow

    async def _execute_add_guardrail_deployment_workflow(
        self, data: Dict[str, Any], workflow_id: UUID, current_user_id: UUID
    ) -> None:
        """Execute add guardrail deployment workflow."""
        db_workflow_steps = await WorkflowStepDataManager(self.session).get_all_workflow_steps(
            {"workflow_id": workflow_id}
        )

        # Latest step
        db_latest_workflow_step = db_workflow_steps[-1]

        # Mark workflow completed
        logger.debug(f"Updating workflow status: {workflow_id}")
        db_workflow = await WorkflowDataManager(self.session).retrieve_by_fields(WorkflowModel, {"id": workflow_id})
        execution_status_data = {
            "workflow_execution_status": {
                "status": "success",
                "message": "Guardrail Profile successfully added to the repository",
            },
            "profile_id": None,
        }

        guardrail_profile_id = data.get("guardrail_profile_id")
        db_profile = None
        if guardrail_profile_id:
            db_profile = await GuardrailsDeploymentDataManager(self.session).retrieve_by_fields(
                GuardrailProfile, {"id": guardrail_profile_id, "status": GuardrailStatusEnum.ACTIVE}, missing_ok=True
            )
            if not db_profile:
                logger.error(f"Failed to locate guardrail profile '{guardrail_profile_id}' in the repository")
                execution_status_data["workflow_execution_status"]["status"] = "error"
                execution_status_data["workflow_execution_status"]["message"] = (
                    "Failed to locate guardrail profile in the repository"
                )
                execution_status_data["profile_id"] = None
        else:
            db_profile = await GuardrailsDeploymentDataManager(self.session).retrieve_by_fields(
                GuardrailProfile,
                {"name": data["name"], "status": GuardrailStatusEnum.ACTIVE},
                missing_ok=True,
                case_sensitive=False,
            )
            if db_profile:
                raise ClientException("Guardrail profile name already exists")

            # Create the profile with probe selections atomically
            err_reason = None
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
                execution_status_data["profile_id"] = None
                err_reason = str(e)

        db_workflow_step = await WorkflowStepDataManager(self.session).update_by_fields(
            db_latest_workflow_step, {"data": execution_status_data}
        )
        if execution_status_data["workflow_execution_status"]["status"] == "error":
            await WorkflowDataManager(self.session).update_by_fields(
                db_workflow, {"status": WorkflowStatusEnum.FAILED, "reason": err_reason}
            )
        else:
            # Determine deployment names based on endpoint or standalone mode
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

            end_step_number = db_workflow_step.step_number + 1
            db_workflow_step = await self._create_or_update_next_workflow_step(workflow_id, end_step_number, {})

            execution_status_data = {
                "workflow_execution_status": {
                    "status": "success",
                    "message": "Guardrail profile successfully deployed.",
                },
                "deployment": [entry.model_dump(mode="json") for entry in deployment_data],
                "profile_id": str(db_profile.id),
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

            db_workflow_step = await WorkflowStepDataManager(self.session).update_by_fields(
                db_workflow_step, {"data": execution_status_data}
            )
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

        return db_profile

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
        self, profile_id: UUID, credential_data: Optional[dict] = None, provider_type: str = None
    ) -> None:
        """Add guardrail profile data to cache with the correct schema format.

        This method creates the guardrail_table:{profile_id} cache entry with provider configurations.

        Cache structure:
        - guardrail_table:{profile_id} -> guardrail profile with providers and probe configs

        Args:
            profile_id: The guardrail profile ID to cache
            credential_data: Optional raw encrypted credential data from ProprietaryCredential.other_provider_creds
            provider_type: The actual provider type (e.g., "openai", "azure-content-safety")
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
            providers["bud_sentinel"] = {
                "type": "bud_sentinel",
                "probe_config": {},
                "endpoint": app_settings.bud_sentinel_base_url,
                "api_key_location": "none",  # Bud sentinel doesn't require credentials
            }

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

    async def derive_model_statuses(
        self,
        probe_selections: list[GuardrailProfileProbeSelection],
        project_id: UUID | None = None,
    ) -> GuardrailModelStatusResponse:
        """Derive deployment status for all models required by selected probes/rules.

        This method examines each rule that requires a model (has model_uri) and determines:
        - If model needs onboarding (model_id is NULL)
        - If model is onboarded but not deployed
        - If model is already deployed and running
        - If model deployment has issues (unhealthy, failed, etc.)

        Args:
            probe_selections: List of selected probes with optional rule selections
            project_id: Optional project ID to check for existing deployments

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
                        model_id=db_rule.model_id,
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
        endpoint_info: dict = {}

        # Check if model is onboarded
        if not rule.model_id:
            return ModelDeploymentStatus.NOT_ONBOARDED, endpoint_info

        # Model is onboarded, check for existing endpoint deployment
        # Query for endpoints using this model
        stmt = select(Endpoint).where(
            Endpoint.model_id == rule.model_id,
            Endpoint.status != EndpointStatusEnum.DELETED,
        )
        if project_id:
            stmt = stmt.where(Endpoint.project_id == project_id)

        result = await self.session.execute(stmt)
        endpoints = result.scalars().all()

        if not endpoints:
            # Model onboarded but no endpoint deployed
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
                "endpoint_id": best_endpoint.id,
                "endpoint_name": best_endpoint.name,
                "endpoint_url": best_endpoint.endpoint,
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

        # Re-derive model statuses
        if not probe_selections_data:
            return GuardrailModelStatusResponse(
                message="No probe selections found",
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

        Args:
            models: List of model info dicts with keys: rule_id, model_uri, model_provider_type
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
            steps.append(
                {
                    "id": step_id,
                    "action": "model_add",
                    "params": {
                        "uri": model["model_uri"],
                        "name": model["model_uri"].split("/")[-1],
                        "provider_type": model.get("model_provider_type", "hugging_face"),
                        "credential_id": str(credential_id) if credential_id else None,
                    },
                    "depends_on": [],  # All steps run in parallel
                }
            )

        # Build the DAG definition
        dag = {
            "name": "guardrail-model-onboarding",
            "version": "1.0",
            "description": f"Onboard {len(models)} models for guardrail deployment",
            "steps": steps,
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
        cluster_id: UUID,
        project_id: UUID,
        user_id: UUID | None = None,
        callback_topics: list[str] | None = None,
    ) -> dict:
        """Trigger BudPipeline to deploy multiple models using deployment_create action.

        Creates a DAG with parallel deployment_create steps for each model.

        Args:
            models: List of model info dicts with keys: model_id, model_name, deployment_config
            cluster_id: Target cluster for deployment
            project_id: Project ID for the deployments
            user_id: User ID initiating the operation
            callback_topics: Optional callback topics for real-time updates

        Returns:
            Dict with execution_id and step mapping for tracking
        """
        if not models:
            return {"execution_id": None, "message": "No models to deploy"}

        # Build DAG steps - one deployment_create step per model
        steps = []
        for i, model in enumerate(models):
            step_id = f"deploy_{i}"
            deploy_config = model.get("deployment_config", {})

            steps.append(
                {
                    "id": step_id,
                    "action": "deployment_create",
                    "params": {
                        "model_id": str(model["model_id"]),
                        "model_name": model.get("model_name", ""),
                        "cluster_id": str(cluster_id),
                        "project_id": str(project_id),
                        "replica": deploy_config.get("replica", 1),
                        "tp": deploy_config.get("tensor_parallelism", 1),
                        "pp": deploy_config.get("pipeline_parallelism", 1),
                        "max_model_len": deploy_config.get("max_model_len"),
                        "gpu_memory_utilization": deploy_config.get("gpu_memory_utilization", 0.9),
                    },
                    "depends_on": [],  # All steps run in parallel
                }
            )

        # Build the DAG definition
        dag = {
            "name": "guardrail-model-deployment",
            "version": "1.0",
            "description": f"Deploy {len(models)} models for guardrail",
            "steps": steps,
        }

        logger.info(f"Triggering model deployment pipeline for {len(models)} models to cluster {cluster_id}")

        # Execute via BudPipeline
        pipeline_service = BudPipelineService(self.session)
        result = await pipeline_service.run_ephemeral_execution(
            pipeline_definition=dag,
            params={
                "user_id": str(user_id) if user_id else None,
                "project_id": str(project_id),
                "cluster_id": str(cluster_id),
            },
            callback_topics=callback_topics,
            user_id=str(user_id) if user_id else None,
        )

        execution_id = result.get("execution_id")
        logger.info(f"Model deployment pipeline started: execution_id={execution_id}")

        return {
            "execution_id": execution_id,
            "step_mapping": {str(model["model_id"]): f"deploy_{i}" for i, model in enumerate(models)},
            "total_models": len(models),
            "cluster_id": str(cluster_id),
        }

    async def trigger_simulation(
        self,
        models: list[dict],
        hardware_mode: str = "dedicated",
        user_id: UUID | None = None,
    ) -> dict:
        """Trigger budsim simulations for multiple models.

        Calls budsim service directly via Dapr to run simulations for cluster recommendations.

        Args:
            models: List of model info dicts with keys: model_id, model_uri, deployment_config
            hardware_mode: "dedicated" or "shared" hardware mode
            user_id: User ID initiating the operation

        Returns:
            Dict with simulation workflow IDs for tracking
        """
        from budapp.commons.config import app_settings
        from budapp.shared.dapr_service import DaprService

        if not models:
            return {"workflow_ids": [], "message": "No models to simulate"}

        workflow_ids = []
        results = []

        for model in models:
            deploy_config = model.get("deployment_config", {})

            try:
                response = await DaprService.invoke_service(
                    app_id=app_settings.budsim_app_id,
                    method_path="simulator/run",
                    method="POST",
                    data={
                        "pretrained_model_uri": model.get("model_uri", ""),
                        "model_uri": model.get("model_uri", ""),
                        "input_tokens": deploy_config.get("input_tokens", 1024),
                        "output_tokens": deploy_config.get("output_tokens", 128),
                        "concurrency": deploy_config.get("concurrency", 10),
                        "target_ttft": deploy_config.get("target_ttft"),
                        "target_e2e_latency": deploy_config.get("target_e2e_latency"),
                        "hardware_mode": hardware_mode,
                        "is_proprietary_model": False,
                    },
                )

                workflow_id = response.get("workflow_id")
                workflow_ids.append(str(workflow_id))
                results.append(
                    {
                        "model_id": str(model.get("model_id", "")),
                        "model_uri": model.get("model_uri", ""),
                        "workflow_id": str(workflow_id),
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
            project_id=project_id,
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
