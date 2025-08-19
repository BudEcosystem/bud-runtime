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

"""Business logic services for the prompt ops module."""

from uuid import UUID

from fastapi import status

from ..commons import logging
from ..commons.constants import (
    APP_ICONS,
    ModelProviderTypeEnum,
    PromptStatusEnum,
    PromptTypeEnum,
    PromptVersionStatusEnum,
    RateLimitTypeEnum,
    WorkflowStatusEnum,
    WorkflowTypeEnum,
    EndpointStatusEnum,
    ProjectStatusEnum,
)
from ..commons.db_utils import SessionMixin
from ..commons.exceptions import ClientException
from ..endpoint_ops.crud import EndpointDataManager
from ..endpoint_ops.models import Endpoint as EndpointModel
from ..model_ops.crud import ProviderDataManager
from ..model_ops.models import Provider as ProviderModel
from ..project_ops.crud import ProjectDataManager
from ..project_ops.models import Project as ProjectModel
from ..workflow_ops.crud import WorkflowDataManager, WorkflowStepDataManager
from ..workflow_ops.models import Workflow as WorkflowModel
from ..workflow_ops.schemas import WorkflowUtilCreate
from ..workflow_ops.services import WorkflowService, WorkflowStepService
from .crud import PromptDataManager, PromptVersionDataManager
from .models import Prompt as PromptModel
from .models import PromptVersion as PromptVersionModel
from .schemas import CreatePromptWorkflowRequest, CreatePromptWorkflowSteps


logger = logging.get_logger(__name__)


class PromptWorkflowService(SessionMixin):
    """Service for managing prompt workflows."""

    async def create_prompt_workflow(self, current_user_id: UUID, request: CreatePromptWorkflowRequest) -> WorkflowModel:
        """Create a prompt workflow with validation."""
        # Get request data
        current_step_number = request.step_number
        workflow_id = request.workflow_id
        workflow_total_steps = request.workflow_total_steps
        trigger_workflow = request.trigger_workflow
        project_id = request.project_id
        endpoint_id = request.endpoint_id
        name = request.name
        description = request.description
        tags = request.tags
        prompt_type = request.prompt_type or PromptTypeEnum.SIMPLE_PROMPT
        auto_scale = request.auto_scale or False
        caching = request.caching or False
        concurrency = request.concurrency
        rate_limit_type = request.rate_limit_type or RateLimitTypeEnum.DISABLED
        rate_limit_value = request.rate_limit_value
        prompt_schema = request.prompt_schema

        # Retrieve or create workflow
        workflow_create = WorkflowUtilCreate(
            workflow_type=WorkflowTypeEnum.PROMPT_CREATION,
            title="Prompt Creation",
            total_steps=workflow_total_steps,
            icon=APP_ICONS["general"]["deployment_mono"],  # TODO: Add appropriate icon
            tag="Prompt Creation",
        )
        db_workflow = await WorkflowService(self.session).retrieve_or_create_workflow(
            workflow_id, workflow_create, current_user_id
        )

        # Validate and extract entities if endpoint_id is provided
        model_id = None
        cluster_id = None
        if endpoint_id:
            db_endpoint = await EndpointDataManager(self.session).retrieve_by_fields(
                EndpointModel, {"id": endpoint_id}, exclude_fields={"status": EndpointStatusEnum.DELETED}, missing_ok=True
            )
            if not db_endpoint:
                raise ClientException(
                    message="Endpoint not found", status_code=status.HTTP_404_NOT_FOUND
                )
            model_id = db_endpoint.model_id
            cluster_id = db_endpoint.cluster_id

            # Update workflow icon
            if db_endpoint.model.provider_type in [ModelProviderTypeEnum.HUGGING_FACE, ModelProviderTypeEnum.CLOUD_MODEL]:
                db_provider = await ProviderDataManager(self.session).retrieve_by_fields(
                    ProviderModel, {"id": db_endpoint.model.provider_id}
                )
                model_icon = db_provider.icon
            else:
                model_icon = db_endpoint.model.icon

            db_workflow = await WorkflowDataManager(self.session).update_by_fields(
                db_workflow, {"icon": model_icon, "title": db_endpoint.model.name}
            )

        if project_id:
            db_project = await ProjectDataManager(self.session).retrieve_by_fields(
                ProjectModel, {"id": project_id, "status": ProjectStatusEnum.ACTIVE}, missing_ok=True
            )
            if not db_project:
                raise ClientException(
                    message="Project not found", status_code=status.HTTP_404_NOT_FOUND
                )

            # Update workflow tag
            db_workflow = await WorkflowDataManager(self.session).update_by_fields(
                db_workflow, {"tag": db_project.name}
            )

        if name:
            db_prompt = await PromptDataManager(self.session).retrieve_by_fields(
                PromptModel, {"name": name, "status": PromptStatusEnum.ACTIVE}, missing_ok=True
            )
            if db_prompt:
                raise ClientException(
                    message="Prompt with this name already exists", status_code=status.HTTP_400_BAD_REQUEST
                )

        # Prepare workflow step data
        workflow_step_data = CreatePromptWorkflowSteps(
            project_id=str(project_id) if project_id else None,
            endpoint_id=str(endpoint_id) if endpoint_id else None,
            model_id=str(model_id) if model_id else None,
            cluster_id=str(cluster_id) if cluster_id else None,
            name=name,
            description=description,
            tags=tags,
            prompt_type=prompt_type.value if prompt_type else PromptTypeEnum.SIMPLE_PROMPT.value,
            auto_scale=auto_scale,
            caching=caching,
            concurrency=concurrency,
            rate_limit_type=rate_limit_type.value if rate_limit_type else RateLimitTypeEnum.DISABLED.value,
            rate_limit_value=rate_limit_value,
            prompt_schema=prompt_schema
        ).model_dump(exclude_none=True, exclude_unset=True, mode="json")

        # Create or update workflow step
        await WorkflowStepService(self.session).create_or_update_next_workflow_step(
            db_workflow.id, current_step_number, workflow_step_data
        )

        # Update workflow current step
        await WorkflowDataManager(self.session).update_by_fields(db_workflow, {"current_step": current_step_number})

        # If trigger_workflow is True, create the prompt and version
        if trigger_workflow:
            logger.info("Workflow triggered")

            # Retrieve all step data
            db_workflow_steps = await WorkflowStepDataManager(self.session).get_all_workflow_steps(
                {"workflow_id": db_workflow.id}
            )

            # Define the keys required for model deployment
            keys_of_interest = [
                "name",
                "description",
                "tags",
                "project_id",
                "endpoint_id",
                "model_id",
                "cluster_id",
                "prompt_type",
                "auto_scale",
                "caching",
                "concurrency",
                "rate_limit_type",
                "rate_limit_value",
            ]

            # from workflow steps extract necessary information
            required_data = {}
            for db_workflow_step in db_workflow_steps:
                for key in keys_of_interest:
                    if key in db_workflow_step.data:
                        required_data[key] = db_workflow_step.data[key]

            # Check if all required keys are present
            required_keys = ["name", "project_id", "endpoint_id", "concurrency", "model_id", "cluster_id"]
            missing_keys = [key for key in required_keys if key not in required_data]
            if missing_keys:
                raise ClientException(f"Missing required data: {', '.join(missing_keys)}")

            # Merge all step data
            merged_data = {}
            for step in db_workflow_steps:
                if step.data:
                    merged_data.update(step.data)

            # Create prompt
            db_prompt = await PromptDataManager(self.session).insert_one(
                PromptModel(
                    name=merged_data.get("name"),
                    description=merged_data.get("description"),
                    tags=merged_data.get("tags"),
                    project_id=UUID(merged_data.get("project_id")),
                    endpoint_id=UUID(merged_data.get("endpoint_id")),
                    model_id=UUID(merged_data.get("model_id")),
                    cluster_id=UUID(merged_data.get("cluster_id")),
                    prompt_type=merged_data.get("prompt_type", PromptTypeEnum.SIMPLE_PROMPT.value),
                    auto_scale=merged_data.get("auto_scale", False),
                    caching=merged_data.get("caching", False),
                    concurrency=merged_data.get("concurrency"),
                    rate_limit_type=merged_data.get("rate_limit_type", RateLimitTypeEnum.DISABLED.value),
                    rate_limit_value=merged_data.get("rate_limit_value"),
                    status=PromptStatusEnum.ACTIVE,
                    created_by=current_user_id,
                )
            )

            # Create first version
            db_version = await PromptVersionDataManager(self.session).insert_one(
                PromptVersionModel(
                    prompt_id=db_prompt.id,
                    version=1,  # First version
                    prompt_schema=prompt_schema.model_dump() if prompt_schema else {},
                    status=PromptVersionStatusEnum.ACTIVE,
                    created_by=current_user_id,
                )
            )

            # Update prompt with default version
            await PromptDataManager(self.session).update_by_fields(
                db_prompt, {"default_version_id": db_version.id}
            )

            # Store final result in workflow step
            # NOTE: increment step to display success message
            final_step_data = {"prompt_id": str(db_prompt.id), "version_id": str(db_version.id)}
            await WorkflowStepService(self.session).create_or_update_next_workflow_step(
                db_workflow.id, current_step_number + 1, final_step_data
            )

            # Complete workflow
            await WorkflowDataManager(self.session).update_by_fields(
                db_workflow, {"current_step": current_step_number + 1, "status": WorkflowStatusEnum.COMPLETED}
            )

        return db_workflow
