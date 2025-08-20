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

from typing import Any
from uuid import UUID

from fastapi import status

from ..commons import logging
from ..commons.constants import (
    APP_ICONS,
    EndpointStatusEnum,
    ModelProviderTypeEnum,
    ProjectStatusEnum,
    PromptStatusEnum,
    PromptTypeEnum,
    PromptVersionStatusEnum,
    RateLimitTypeEnum,
    WorkflowStatusEnum,
    WorkflowTypeEnum,
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
from .schemas import (
    CreatePromptWorkflowRequest,
    CreatePromptWorkflowSteps,
    PromptFilter,
    PromptListItem,
    PromptResponse,
)


logger = logging.get_logger(__name__)


class PromptService(SessionMixin):
    """Service for managing prompts."""

    async def get_all_prompts(
        self,
        offset: int = 0,
        limit: int = 10,
        filters: dict = {},
        order_by: list = [],
        search: bool = False,
    ) -> tuple[list[PromptModel], int]:
        """Get all active prompts with their related data."""
        # Fetch active prompts
        filters["status"] = PromptStatusEnum.ACTIVE

        # Fetch prompts with related data
        db_prompts, count = await PromptDataManager(self.session).get_all_active_prompts(
            offset, limit, filters, order_by, search
        )

        # Transform to response format
        prompts_list = []
        for prompt in db_prompts:
            endpoint = prompt.endpoint
            model = endpoint.model if endpoint else None
            default_version_obj = prompt.default_version

            prompt_item = PromptListItem(
                id=prompt.id,
                name=prompt.name,
                description=prompt.description,
                tags=prompt.tags,
                created_at=prompt.created_at,
                modified_at=prompt.modified_at,
                prompt_type=prompt.prompt_type,
                model_icon=model.icon if model else None,
                model_name=model.name if model else "",
                default_version=default_version_obj.version if default_version_obj else None,
                modality=model.modality if model else None,
                status=endpoint.status if endpoint else "",
            )
            prompts_list.append(prompt_item)

        return prompts_list, count

    async def delete_active_prompt(self, prompt_id: UUID) -> PromptModel:
        """Delete an active prompt by updating its status to DELETED."""
        # Retrieve and validate prompt
        db_prompt = await PromptDataManager(self.session).retrieve_by_fields(
            PromptModel, fields={"id": prompt_id, "status": PromptStatusEnum.ACTIVE}
        )

        # Update prompt status to DELETED
        await PromptDataManager(self.session).update_by_fields(db_prompt, {"status": PromptStatusEnum.DELETED})

        # Soft delete all associated prompt versions
        deleted_count = await PromptVersionDataManager(self.session).soft_delete_by_prompt_id(prompt_id)
        logger.debug(f"Soft deleted {deleted_count} prompt versions for prompt {prompt_id}")

        return db_prompt

    async def edit_prompt(self, prompt_id: UUID, data: dict[str, Any]) -> PromptModel:
        """Edit prompt by validating and updating specific fields."""
        # Retrieve existing prompt
        db_prompt = await PromptDataManager(self.session).retrieve_by_fields(
            PromptModel, fields={"id": prompt_id, "status": PromptStatusEnum.ACTIVE}
        )

        # Validate name uniqueness if name is provided
        if "name" in data:
            duplicate_prompt = await PromptDataManager(self.session).retrieve_by_fields(
                PromptModel,
                fields={"name": data["name"]},
                exclude_fields={"id": prompt_id, "status": PromptStatusEnum.DELETED},
                missing_ok=True,
                case_sensitive=False,
            )
            if duplicate_prompt:
                raise ClientException(message="Prompt name already exists", status_code=status.HTTP_400_BAD_REQUEST)

        # Validate default_version_id if provided
        if "default_version_id" in data and data["default_version_id"]:
            # Check if the version exists and belongs to this prompt
            db_version = await PromptVersionDataManager(self.session).retrieve_by_fields(
                PromptVersionModel,
                fields={
                    "id": data["default_version_id"],
                    "prompt_id": prompt_id,
                },
                exclude_fields={"status": PromptVersionStatusEnum.DELETED},
                missing_ok=True,
            )
            if not db_version:
                raise ClientException(
                    message="Invalid default version. Version does not exist or does not belong to this prompt.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

        # Update the prompt
        db_prompt = await PromptDataManager(self.session).update_by_fields(db_prompt, data)

        # Convert to response model
        prompt_response = PromptResponse.model_validate(db_prompt)

        return prompt_response


class PromptWorkflowService(SessionMixin):
    """Service for managing prompt workflows."""

    async def create_prompt_workflow(
        self, current_user_id: UUID, request: CreatePromptWorkflowRequest
    ) -> WorkflowModel:
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
        prompt_type = request.prompt_type
        auto_scale = request.auto_scale
        caching = request.caching
        concurrency = request.concurrency
        rate_limit_type = request.rate_limit_type
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

        # If workflow_id exists, check previous steps for project_id and endpoint_id
        previous_project_id = None
        previous_endpoint_id = None
        if workflow_id:
            db_workflow_steps = await WorkflowStepDataManager(self.session).get_all_workflow_steps(
                {"workflow_id": workflow_id}
            )
            for step in db_workflow_steps:
                if step.data:
                    if "project_id" in step.data and step.data["project_id"]:
                        previous_project_id = UUID(step.data["project_id"])
                    if "endpoint_id" in step.data and step.data["endpoint_id"]:
                        previous_endpoint_id = UUID(step.data["endpoint_id"])

        # Validate and extract entities if endpoint_id is provided
        model_id = None
        cluster_id = None
        if endpoint_id:
            db_endpoint = await EndpointDataManager(self.session).retrieve_by_fields(
                EndpointModel,
                {"id": endpoint_id},
                exclude_fields={"status": EndpointStatusEnum.DELETED},
                missing_ok=True,
            )
            if not db_endpoint:
                raise ClientException(message="Endpoint not found", status_code=status.HTTP_404_NOT_FOUND)
            model_id = db_endpoint.model_id
            cluster_id = db_endpoint.cluster_id

            # Validate project-endpoint consistency
            if previous_project_id and db_endpoint.project_id != previous_project_id:
                raise ClientException(
                    message="Endpoint does not belong to the specified project.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            # Case 2: Current has both endpoint_id and project_id
            if project_id and db_endpoint.project_id != project_id:
                raise ClientException(
                    message="Endpoint does not belong to the specified project.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            # Update workflow icon
            if db_endpoint.model.provider_type in [
                ModelProviderTypeEnum.HUGGING_FACE,
                ModelProviderTypeEnum.CLOUD_MODEL,
            ]:
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
                raise ClientException(message="Project not found", status_code=status.HTTP_404_NOT_FOUND)

            # Validate project-endpoint consistency
            # Case 3: Current has project_id, previous steps have endpoint_id
            if previous_endpoint_id and not endpoint_id:
                # Fetch the previous endpoint to validate
                db_previous_endpoint = await EndpointDataManager(self.session).retrieve_by_fields(
                    EndpointModel,
                    {"id": previous_endpoint_id},
                    exclude_fields={"status": EndpointStatusEnum.DELETED},
                    missing_ok=True,
                )
                if db_previous_endpoint and db_previous_endpoint.project_id != project_id:
                    raise ClientException(
                        message="Endpoint from previous step belongs to different project",
                        status_code=status.HTTP_400_BAD_REQUEST,
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
            prompt_type=prompt_type.value if prompt_type else None,
            auto_scale=auto_scale,
            caching=caching,
            concurrency=concurrency,
            rate_limit_type=rate_limit_type.value if rate_limit_type else None,
            rate_limit_value=rate_limit_value,
            prompt_schema=prompt_schema,
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
            await PromptDataManager(self.session).update_by_fields(db_prompt, {"default_version_id": db_version.id})

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
