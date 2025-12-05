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
    GuardrailDeploymentCreate,
    GuardrailDeploymentDetailResponse,
    GuardrailDeploymentResponse,
    GuardrailDeploymentWorkflowRequest,
    GuardrailDeploymentWorkflowSteps,
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
    ProxyGuardrailConfig,
)
from budapp.model_ops.crud import ProviderDataManager
from budapp.model_ops.models import Provider
from budapp.project_ops.crud import ProjectDataManager
from budapp.project_ops.models import Project
from budapp.shared.notification_service import BudNotifyService, NotificationBuilder
from budapp.shared.redis_service import RedisService
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
