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

"""The workflow ops services. Contains business logic for workflow ops."""

from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from fastapi import status

from budapp.cluster_ops.crud import ClusterDataManager
from budapp.cluster_ops.models import Cluster as ClusterModel
from budapp.commons import logging
from budapp.commons.constants import (
    WORKFLOW_DELETE_MESSAGES,
    BudServeWorkflowStepEventName,
    VisibilityEnum,
    WorkflowStatusEnum,
    WorkflowTypeEnum,
)
from budapp.commons.db_utils import SessionMixin
from budapp.commons.exceptions import ClientException
from budapp.core.crud import ModelTemplateDataManager
from budapp.core.models import ModelTemplate as ModelTemplateModel
from budapp.credential_ops.crud import ProprietaryCredentialDataManager
from budapp.credential_ops.models import ProprietaryCredential as ProprietaryCredentialModel
from budapp.endpoint_ops.crud import EndpointDataManager
from budapp.endpoint_ops.models import Endpoint as EndpointModel
from budapp.endpoint_ops.schemas import AddAdapterWorkflowStepData
from budapp.guardrails.crud import GuardrailsDeploymentDataManager
from budapp.guardrails.models import GuardrailProfile
from budapp.guardrails.schemas import GuardrailProfileResponse
from budapp.model_ops.crud import (
    CloudModelDataManager,
    ModelDataManager,
    ModelSecurityScanResultDataManager,
    ProviderDataManager,
)
from budapp.model_ops.models import CloudModel, Model
from budapp.model_ops.models import ModelSecurityScanResult as ModelSecurityScanResultModel
from budapp.model_ops.models import Provider as ProviderModel
from budapp.model_ops.schemas import QuantizeModelWorkflowStepData
from budapp.project_ops.crud import ProjectDataManager
from budapp.project_ops.models import Project as ProjectModel
from budapp.workflow_ops.crud import WorkflowDataManager, WorkflowStepDataManager
from budapp.workflow_ops.models import Workflow as WorkflowModel
from budapp.workflow_ops.models import WorkflowStep as WorkflowStepModel
from budapp.workflow_ops.schemas import RetrieveWorkflowDataResponse, RetrieveWorkflowStepData, WorkflowUtilCreate


logger = logging.get_logger(__name__)


class WorkflowService(SessionMixin):
    """Workflow service."""

    async def retrieve_workflow_data(self, workflow_id: UUID) -> RetrieveWorkflowDataResponse:
        """Retrieve workflow data."""
        db_workflow = await WorkflowDataManager(self.session).retrieve_by_fields(WorkflowModel, {"id": workflow_id})

        db_workflow_steps = await WorkflowStepDataManager(self.session).get_all_workflow_steps(
            {"workflow_id": workflow_id}
        )

        # Extract required data from workflow steps
        required_data = await self._extract_required_data_from_workflow_steps(db_workflow_steps)

        # Parse workflow step data response
        return await self._parse_workflow_step_data_response(required_data, db_workflow)

    async def _extract_required_data_from_workflow_steps(
        self, db_workflow_steps: List[WorkflowStepModel]
    ) -> Dict[str, Any]:
        """Get required data from workflow steps.

        Args:
            db_workflow_steps: List of workflow steps.

        Returns:
            Dict of required data.
        """
        # Define the keys required data retrieval
        keys_of_interest = await self._get_keys_of_interest()

        # from workflow steps extract necessary information
        required_data = {}
        for db_workflow_step in db_workflow_steps:
            for key in keys_of_interest:
                if key in db_workflow_step.data:
                    required_data[key] = db_workflow_step.data[key]

        return required_data

    async def _parse_workflow_step_data_response(
        self, required_data: Dict[str, Any], db_workflow: WorkflowModel
    ) -> RetrieveWorkflowDataResponse:
        """Parse workflow step data response.

        Args:
            required_data: Dict of required data.
            db_workflow: DB workflow.

        Returns:
            RetrieveWorkflowDataResponse: Retrieve workflow data response.
        """
        if required_data:
            # Collect necessary info according to required data
            provider_type = required_data.get("provider_type")
            provider_id = required_data.get("provider_id")
            cloud_model_id = required_data.get("cloud_model_id")
            model_id = required_data.get("model_id")
            workflow_execution_status = required_data.get("workflow_execution_status")
            leaderboard = required_data.get("leaderboard")
            name = required_data.get("name")
            ingress_url = required_data.get("ingress_url")
            create_cluster_events = required_data.get(BudServeWorkflowStepEventName.CREATE_CLUSTER_EVENTS.value)
            delete_cluster_events = required_data.get(BudServeWorkflowStepEventName.DELETE_CLUSTER_EVENTS.value)
            delete_endpoint_events = required_data.get(BudServeWorkflowStepEventName.DELETE_ENDPOINT_EVENTS.value)
            delete_worker_events = required_data.get(BudServeWorkflowStepEventName.DELETE_WORKER_EVENTS.value)
            model_extraction_events = required_data.get(BudServeWorkflowStepEventName.MODEL_EXTRACTION_EVENTS.value)
            evaluation_events = required_data.get(BudServeWorkflowStepEventName.EVALUATION_EVENTS.value)
            bud_serve_cluster_events = required_data.get(BudServeWorkflowStepEventName.BUDSERVE_CLUSTER_EVENTS.value)
            model_security_scan_events = required_data.get(
                BudServeWorkflowStepEventName.MODEL_SECURITY_SCAN_EVENTS.value
            )
            bud_simulator_events = required_data.get(BudServeWorkflowStepEventName.BUD_SIMULATOR_EVENTS.value)
            quantization_deployment_events = required_data.get(
                BudServeWorkflowStepEventName.QUANTIZATION_DEPLOYMENT_EVENTS.value
            )
            quantization_simulation_events = required_data.get(
                BudServeWorkflowStepEventName.QUANTIZATION_SIMULATION_EVENTS.value
            )
            adapter_deployment_events = required_data.get(
                BudServeWorkflowStepEventName.ADAPTER_DEPLOYMENT_EVENTS.value
            )
            security_scan_result_id = required_data.get("security_scan_result_id")
            icon = required_data.get("icon")
            uri = required_data.get("uri")
            author = required_data.get("author")
            tags = required_data.get("tags")
            description = required_data.get("description")
            additional_concurrency = required_data.get("additional_concurrency")
            quantized_model_name = required_data.get("quantized_model_name")
            eval_with = required_data.get("eval_with")
            max_input_tokens = required_data.get("max_input_tokens")
            max_output_tokens = required_data.get("max_output_tokens")
            datasets = required_data.get("datasets")
            dataset_ids = required_data.get("dataset_ids")
            nodes = required_data.get("nodes")
            credential_id = required_data.get("credential_id")
            user_confirmation = required_data.get("user_confirmation")
            run_as_simulation = required_data.get("run_as_simulation")
            adapter_model_id = required_data.get("adapter_model_id")
            endpoint_name = required_data.get("endpoint_name")
            deploy_config = required_data.get("deploy_config")
            scaling_specification = required_data.get("scaling_specification")
            simulator_id = required_data.get("simulator_id")
            template_id = required_data.get("template_id")
            endpoint_details = required_data.get("endpoint_details")
            add_model_modality = required_data.get("add_model_modality")
            guardrail_profile_id = required_data.get("guardrail_profile_id")
            endpoint_ids = required_data.get("endpoint_ids")
            is_standalone = required_data.get("is_standalone")
            probe_selections = required_data.get("probe_selections")
            guard_types = required_data.get("guard_types")
            severity_threshold = required_data.get("severity_threshold")

            quantization_config = (
                QuantizeModelWorkflowStepData(
                    model_id=model_id,
                    quantized_model_name=required_data.get("quantized_model_name"),
                    target_type=required_data.get("target_type"),
                    target_device=required_data.get("target_device"),
                    method=required_data.get("method"),
                    weight_config=required_data.get("weight_config"),
                    activation_config=required_data.get("activation_config"),
                    cluster_id=required_data.get("cluster_id"),
                    simulation_id=required_data.get("simulation_id"),
                    quantization_data=required_data.get("quantization_data"),
                    quantized_model_id=required_data.get("quantized_model_id"),
                )
                if quantized_model_name
                else None
            )

            adapter_config = (
                AddAdapterWorkflowStepData(
                    adapter_model_id=adapter_model_id,
                    adapter_name=required_data.get("adapter_name"),
                    endpoint_id=required_data.get("endpoint_id"),
                    adapter_id=required_data.get("adapter_id"),
                )
                if adapter_model_id
                else None
            )
            prompt_type = required_data.get("prompt_type")
            prompt_schema = required_data.get("prompt_schema")
            auto_scale = required_data.get("auto_scale")
            caching = required_data.get("caching")
            concurrency = required_data.get("concurrency")
            rate_limit = required_data.get("rate_limit")
            rate_limit_value = required_data.get("rate_limit_value")
            bud_prompt_id = required_data.get("bud_prompt_id")
            bud_prompt_version = required_data.get("bud_prompt_version")
            discarded_prompt_ids = required_data.get("discarded_prompt_ids")
            prompt_schema_events = required_data.get(BudServeWorkflowStepEventName.PROMPT_SCHEMA_EVENTS.value)

            # Extract parser metadata
            tool_calling_parser_type = required_data.get("tool_calling_parser_type")
            reasoning_parser_type = required_data.get("reasoning_parser_type")
            chat_template = required_data.get("chat_template")
            enable_tool_calling = required_data.get("enable_tool_calling")
            enable_reasoning = required_data.get("enable_reasoning")

            # Extract hardware mode
            hardware_mode = required_data.get("hardware_mode")

            # Handle experiment_id extraction with UUID conversion
            experiment_id_str = required_data.get("experiment_id")
            experiment_id = None
            if experiment_id_str:
                try:
                    experiment_id = UUID(str(experiment_id_str))
                except (ValueError, TypeError):
                    experiment_id = None

            # Handle trait_ids extraction with UUID conversion
            trait_ids_raw = required_data.get("trait_ids")
            trait_ids = None
            if trait_ids_raw:
                trait_ids = []
                if isinstance(trait_ids_raw, list):
                    for tid in trait_ids_raw:
                        try:
                            trait_ids.append(UUID(str(tid)))
                        except (ValueError, TypeError):
                            continue
                if not trait_ids:
                    trait_ids = None

            # Extract traits_details directly
            traits_details = required_data.get("traits_details")

            db_provider = (
                await ProviderDataManager(self.session).retrieve_by_fields(
                    ProviderModel, {"id": required_data["provider_id"]}, missing_ok=True
                )
                if "provider_id" in required_data
                else None
            )

            db_cloud_model = (
                await CloudModelDataManager(self.session).retrieve_by_fields(
                    CloudModel, {"id": required_data["cloud_model_id"]}, missing_ok=True
                )
                if "cloud_model_id" in required_data
                else None
            )

            db_model = (
                await ModelDataManager(self.session).retrieve_by_fields(
                    Model, {"id": UUID(required_data["model_id"])}, missing_ok=True
                )
                if "model_id" in required_data
                else None
            )

            db_model_security_scan_result = (
                await ModelSecurityScanResultDataManager(self.session).retrieve_by_fields(
                    ModelSecurityScanResultModel, {"id": UUID(security_scan_result_id)}, missing_ok=True
                )
                if "security_scan_result_id" in required_data
                else None
            )

            db_endpoint = (
                await EndpointDataManager(self.session).retrieve_by_fields(
                    EndpointModel, {"id": UUID(required_data["endpoint_id"])}, missing_ok=True
                )
                if "endpoint_id" in required_data
                else None
            )

            db_project = (
                await ProjectDataManager(self.session).retrieve_by_fields(
                    ProjectModel, {"id": UUID(required_data["project_id"])}, missing_ok=True
                )
                if "project_id" in required_data
                else None
            )

            db_cluster = (
                await ClusterDataManager(self.session).retrieve_by_fields(
                    ClusterModel, {"id": UUID(required_data["cluster_id"])}, missing_ok=True
                )
                if "cluster_id" in required_data
                else None
            )

            db_credential = (
                await ProprietaryCredentialDataManager(self.session).retrieve_by_fields(
                    ProprietaryCredentialModel, {"id": UUID(required_data["credential_id"])}, missing_ok=True
                )
                if "credential_id" in required_data
                else None
            )

            db_template = (
                await ModelTemplateDataManager(self.session).retrieve_by_fields(
                    ModelTemplateModel, {"id": UUID(required_data["template_id"])}, missing_ok=True
                )
                if "template_id" in required_data
                else None
            )

            db_guardrail_profile = (
                await GuardrailsDeploymentDataManager(self.session).retrieve_by_fields(
                    GuardrailProfile, {"id": UUID(required_data["guardrail_profile_id"])}, missing_ok=True
                )
                if "guardrail_profile_id" in required_data
                else None
            )

            guardrail_profile = None
            if db_guardrail_profile:
                probe_count, deployment_count, is_standalone = await GuardrailsDeploymentDataManager(
                    self.session
                ).get_profile_counts(db_guardrail_profile.id)
                guardrail_profile = GuardrailProfileResponse.model_validate(
                    db_guardrail_profile,
                    update={
                        "probe_count": probe_count,
                        "deployment_count": deployment_count,
                        "is_standalone": is_standalone,
                    },
                )

            db_endpoints = (
                await EndpointDataManager(self.session).get_endpoints(
                    [UUID(endpoint_id) for endpoint_id in required_data["endpoint_ids"]]
                )
                if "endpoint_ids" in required_data
                else None
            )

            workflow_steps = RetrieveWorkflowStepData(
                experiment_id=experiment_id if experiment_id else None,
                trait_ids=trait_ids if trait_ids else None,
                traits_details=traits_details if traits_details else None,
                provider_type=provider_type if provider_type else None,
                provider=db_provider if db_provider else None,
                provider_id=provider_id if provider_id else None,
                cloud_model=db_cloud_model if db_cloud_model else None,
                cloud_model_id=cloud_model_id if cloud_model_id else None,
                model=db_model if db_model else None,
                model_id=model_id if model_id else None,
                workflow_execution_status=workflow_execution_status if workflow_execution_status else None,
                leaderboard=leaderboard if leaderboard else None,
                name=name if name else None,
                icon=icon if icon else None,
                ingress_url=ingress_url if ingress_url else None,
                create_cluster_events=create_cluster_events if create_cluster_events else None,
                uri=uri if uri else None,
                author=author if author else None,
                tags=tags if tags else None,
                model_extraction_events=model_extraction_events if model_extraction_events else None,
                evaluation_events=evaluation_events if evaluation_events else None,
                description=description if description else None,
                security_scan_result_id=security_scan_result_id if security_scan_result_id else None,
                model_security_scan_events=model_security_scan_events if model_security_scan_events else None,
                budserve_cluster_events=bud_serve_cluster_events if bud_serve_cluster_events else None,
                security_scan_result=db_model_security_scan_result if db_model_security_scan_result else None,
                delete_cluster_events=delete_cluster_events if delete_cluster_events else None,
                delete_endpoint_events=delete_endpoint_events if delete_endpoint_events else None,
                delete_worker_events=delete_worker_events if delete_worker_events else None,
                endpoint=db_endpoint if db_endpoint else None,
                additional_concurrency=additional_concurrency if additional_concurrency else None,
                bud_simulator_events=bud_simulator_events if bud_simulator_events else None,
                project=db_project if db_project else None,
                cluster=db_cluster if db_cluster else None,
                quantization_config=quantization_config if quantization_config else None,
                quantization_deployment_events=quantization_deployment_events
                if quantization_deployment_events
                else None,
                quantization_simulation_events=quantization_simulation_events
                if quantization_simulation_events
                else None,
                eval_with=eval_with,
                max_input_tokens=max_input_tokens,
                max_output_tokens=max_output_tokens,
                datasets=datasets,
                nodes=nodes,
                credential_id=credential_id,
                user_confirmation=user_confirmation,
                run_as_simulation=run_as_simulation,
                adapter_config=adapter_config if adapter_config else None,
                adapter_deployment_events=adapter_deployment_events if adapter_deployment_events else None,
                credential=db_credential if db_credential else None,
                endpoint_name=endpoint_name if endpoint_name else None,
                deploy_config=deploy_config if deploy_config else None,
                scaling_specification=scaling_specification if scaling_specification else None,
                simulator_id=simulator_id if simulator_id else None,
                template_id=template_id if template_id else None,
                endpoint_details=endpoint_details if endpoint_details else None,
                template=db_template if db_template else None,
                add_model_modality=add_model_modality if add_model_modality else None,
                guardrail_profile_id=guardrail_profile_id if guardrail_profile_id else None,
                guardrail_profile=guardrail_profile if guardrail_profile else None,
                endpoint_ids=endpoint_ids if endpoint_ids else None,
                endpoints=db_endpoints if db_endpoints else None,
                is_standalone=is_standalone,
                probe_selections=probe_selections if probe_selections else None,
                guard_types=guard_types if guard_types else None,
                severity_threshold=severity_threshold if severity_threshold else None,
                prompt_type=prompt_type if prompt_type else None,
                prompt_schema=prompt_schema if prompt_schema else None,
                auto_scale=auto_scale if auto_scale else None,
                caching=caching if caching else None,
                concurrency=concurrency if concurrency else None,
                rate_limit=rate_limit if rate_limit else None,
                rate_limit_value=rate_limit_value if rate_limit_value else None,
                bud_prompt_id=bud_prompt_id if bud_prompt_id else None,
                bud_prompt_version=bud_prompt_version if bud_prompt_version else None,
                discarded_prompt_ids=discarded_prompt_ids if discarded_prompt_ids else None,
                prompt_schema_events=prompt_schema_events if prompt_schema_events else None,
                tool_calling_parser_type=tool_calling_parser_type if tool_calling_parser_type else None,
                reasoning_parser_type=reasoning_parser_type if reasoning_parser_type else None,
                chat_template=chat_template if chat_template else None,
                enable_tool_calling=enable_tool_calling if enable_tool_calling else None,
                enable_reasoning=enable_reasoning if enable_reasoning else None,
                hardware_mode=hardware_mode if hardware_mode else None,
                dataset_ids=dataset_ids,
            )
        else:
            workflow_steps = RetrieveWorkflowStepData()

        return RetrieveWorkflowDataResponse(
            workflow_id=db_workflow.id,
            status=db_workflow.status,
            current_step=db_workflow.current_step,
            total_steps=db_workflow.total_steps,
            reason=db_workflow.reason,
            workflow_steps=workflow_steps,
            code=status.HTTP_200_OK,
            object="workflow.get",
            message="Workflow data retrieved successfully",
        )

    @staticmethod
    async def _get_keys_of_interest() -> List[str]:
        """Get keys of interest as per different workflows."""
        workflow_keys = {
            "add_cloud_model": [
                "source",
                "name",
                "modality",
                "uri",
                "tags",
                "icon",
                "provider_type",
                "provider_id",
                "cloud_model_id",
                "description",
                "model_id",
                "workflow_execution_status",
                "leaderboard",
                "add_model_modality",
            ],
            "create_cluster": [
                "name",
                "icon",
                "ingress_url",
                BudServeWorkflowStepEventName.CREATE_CLUSTER_EVENTS.value,
                "cluster_id",
            ],
            "add_local_model": [
                "name",
                "uri",
                "author",
                "tags",
                "icon",
                "provider_type",
                "provider_id",
                BudServeWorkflowStepEventName.MODEL_EXTRACTION_EVENTS.value,
                "model_id",
                "description",
                "add_model_modality",
            ],
            "scan_local_model": [
                "model_id",
                "security_scan_result_id",
                "leaderboard",
                BudServeWorkflowStepEventName.MODEL_SECURITY_SCAN_EVENTS.value,
            ],
            "delete_cluster": [
                BudServeWorkflowStepEventName.DELETE_CLUSTER_EVENTS.value,
            ],
            "delete_endpoint": [
                BudServeWorkflowStepEventName.DELETE_ENDPOINT_EVENTS.value,
            ],
            "delete_worker": [
                BudServeWorkflowStepEventName.DELETE_WORKER_EVENTS.value,
            ],
            "add_worker_to_endpoint": [
                BudServeWorkflowStepEventName.BUD_SIMULATOR_EVENTS.value,
                BudServeWorkflowStepEventName.BUDSERVE_CLUSTER_EVENTS.value,
                "endpoint_id",
                "additional_concurrency",
                "cluster_id",
                "project_id",
            ],
            "local_model_quantization": [
                "model_id",
                "target_type",
                "target_device",
                "quantized_model_name",
                "method",
                "weight_config",
                "activation_config",
                BudServeWorkflowStepEventName.QUANTIZATION_DEPLOYMENT_EVENTS.value,
                BudServeWorkflowStepEventName.QUANTIZATION_SIMULATION_EVENTS.value,
                "cluster_id",
                "simulation_id",
                "quantization_data",
                "quantized_model_id",
            ],
            "model_benchmark": [
                "name",
                "tags",
                "description",
                "concurrent_requests",
                "eval_with",
                "datasets",
                "max_input_tokens",
                "max_output_tokens",
                "cluster_id",
                "bud_cluster_id",
                "nodes",
                "model_id",
                "model",
                "provider_type",
                "credential_id",
                "user_confirmation",
                "run_as_simulation",
            ],
            "evaluation": [BudServeWorkflowStepEventName.EVALUATION_EVENTS.value, "dataset_ids"],
            "add_adapter": [
                "adapter_model_id",
                "adapter_name",
                "endpoint_id",
                BudServeWorkflowStepEventName.ADAPTER_DEPLOYMENT_EVENTS.value,
                "adapter_id",
            ],
            "deploy_model": [
                "model_id",
                "project_id",
                "cluster_id",
                "endpoint_name",
                "hardware_mode",
                "budserve_cluster_events",
                "bud_simulator_events",
                "deploy_config",
                "template_id",
                "simulator_id",
                "credential_id",
                "endpoint_details",
                "scaling_specification",
                "tool_calling_parser_type",
                "reasoning_parser_type",
                "chat_template",
                "enable_tool_calling",
                "enable_reasoning",
            ],
            "guardrail_deployment": [
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
            ],
            "prompt_creation": [
                "model_id",
                "project_id",
                "cluster_id",
                "endpoint_id",
                "name",
                "description",
                "tags",
                "prompt_type",
                "auto_scale",
                "caching",
                "concurrency",
                "rate_limit",
                "rate_limit_value",
                "prompt_schema",
                "discarded_prompt_ids",
            ],
            "prompt_schema_creation": [
                "bud_prompt_id",
                "bud_prompt_version",
                BudServeWorkflowStepEventName.PROMPT_SCHEMA_EVENTS.value,
            ],
        }

        # Combine all lists using set union
        all_keys = set().union(*workflow_keys.values())

        # Add evaluation workflow specific keys
        all_keys.add("experiment_id")
        all_keys.add("trait_ids")
        all_keys.add("traits_details")

        return list(all_keys)

    async def retrieve_or_create_workflow(
        self, workflow_id: Optional[UUID], workflow_data: WorkflowUtilCreate, current_user_id: UUID
    ) -> None:
        """Retrieve or create workflow."""
        workflow_data = workflow_data.model_dump(exclude_none=True, exclude_unset=True)

        if workflow_id:
            db_workflow = await WorkflowDataManager(self.session).retrieve_by_fields(
                WorkflowModel, {"id": workflow_id}
            )

            if db_workflow.status != WorkflowStatusEnum.IN_PROGRESS:
                logger.error(f"Workflow {workflow_id} is not in progress")
                raise ClientException("Workflow is not in progress")

            if db_workflow.created_by != current_user_id:
                logger.error(f"User {current_user_id} is not the creator of workflow {workflow_id}")
                raise ClientException("User is not authorized to perform this action")
        elif "total_steps" in workflow_data:
            db_workflow = await WorkflowDataManager(self.session).insert_one(
                WorkflowModel(**workflow_data, created_by=current_user_id),
            )
        else:
            raise ClientException("Either workflow_id or total_steps should be provided")

        return db_workflow

    async def mark_workflow_as_completed(self, workflow_id: UUID, current_user_id: UUID) -> WorkflowModel:
        """Mark workflow as completed."""
        db_workflow = await WorkflowDataManager(self.session).retrieve_by_fields(
            WorkflowModel, {"id": workflow_id, "created_by": current_user_id}
        )
        logger.debug(f"Workflow found: {db_workflow.id}")

        # Update status to completed only if workflow is not failed
        if db_workflow.status == WorkflowStatusEnum.FAILED:
            logger.error(f"Workflow {workflow_id} is failed")
            raise ClientException("Workflow is failed")

        return await WorkflowDataManager(self.session).update_by_fields(
            db_workflow, {"status": WorkflowStatusEnum.COMPLETED}
        )

    async def delete_workflow(self, workflow_id: UUID, current_user_id: UUID) -> None:
        """Delete workflow."""
        db_workflow = await WorkflowDataManager(self.session).retrieve_by_fields(
            WorkflowModel, {"id": workflow_id, "created_by": current_user_id}
        )

        if db_workflow.status != WorkflowStatusEnum.IN_PROGRESS:
            logger.error("Unable to delete failed or completed workflow")
            raise ClientException("Workflow is not in progress state")

        # Cleanup for PROMPT_CREATION workflows
        if db_workflow.workflow_type == WorkflowTypeEnum.PROMPT_CREATION:
            try:
                cleanup_service = WorkflowCleanupService(self.session)
                await cleanup_service.cleanup_prompt_creation_workflow(workflow_id)
            except Exception as e:
                # Log warning but continue with deletion
                logger.warning(f"Cleanup failed for workflow {workflow_id} but continuing with deletion: {e}")

        # Define success messages for different workflow types
        success_response = WORKFLOW_DELETE_MESSAGES.get(db_workflow.workflow_type, "Workflow deleted successfully")

        # Delete workflow
        await WorkflowDataManager(self.session).delete_one(db_workflow)

        return success_response

    async def get_all_active_workflows(
        self,
        offset: int = 0,
        limit: int = 10,
        filters: Dict = {},
        order_by: List = [],
        search: bool = False,
    ) -> Tuple[List[WorkflowModel], int]:
        """Get all active worflows."""
        filters_dict = filters

        # Filter by in progress status
        filters_dict["status"] = WorkflowStatusEnum.IN_PROGRESS
        filters_dict["visibility"] = VisibilityEnum.PUBLIC

        return await WorkflowDataManager(self.session).get_all_workflows(offset, limit, filters_dict, order_by, search)


class WorkflowCleanupService(SessionMixin):
    """Service for handling post-deletion cleanup of workflows."""

    async def cleanup_prompt_creation_workflow(self, workflow_id: UUID) -> None:
        """Cleanup discarded prompts from a PROMPT_CREATION workflow.

        Args:
            workflow_id: The workflow UUID to cleanup

        This method:
        1. Fetches all workflow steps for the given workflow_id
        2. Extracts discarded_prompt_ids from step data
        3. Calls budprompt service to cleanup MCP resources
        4. Logs errors but does not raise exceptions (best-effort cleanup)
        """
        try:
            # Get all workflow steps
            db_workflow_steps = await WorkflowStepDataManager(self.session).get_all_workflow_steps(
                {"workflow_id": workflow_id}
            )

            # Define keys to extract from workflow steps
            keys_of_interest = ["discarded_prompt_ids"]

            # Extract necessary information from workflow steps
            required_data = {}
            for db_workflow_step in db_workflow_steps:
                for key in keys_of_interest:
                    if key in db_workflow_step.data:
                        required_data[key] = db_workflow_step.data[key]

            # Get discarded_prompt_ids
            discarded_prompt_ids = required_data.get("discarded_prompt_ids", [])

            # Only proceed if there are prompts to cleanup
            if not discarded_prompt_ids or len(discarded_prompt_ids) == 0:
                logger.debug(f"No discarded prompts to cleanup for workflow {workflow_id}")
                return

            # Call cleanup via PromptService
            logger.debug(
                f"Triggering cleanup for {len(discarded_prompt_ids)} discarded prompts from workflow {workflow_id}"
            )

            from budapp.prompt_ops.services import PromptService

            prompt_service = PromptService(self.session)
            await prompt_service._perform_cleanup_request(discarded_prompt_ids)

            logger.debug(f"Successfully cleaned up {len(discarded_prompt_ids)} prompts from workflow {workflow_id}")

        except Exception as e:
            # Log error but don't raise - cleanup is best-effort
            logger.warning(
                f"Failed to cleanup discarded prompts from workflow {workflow_id}: {e}",
                exc_info=True,
            )


class WorkflowStepService(SessionMixin):
    """Workflow step service."""

    async def create_or_update_next_workflow_step(
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
