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

"""The model ops package, containing essential business logic, services, and routing configurations for the model ops."""

import json
from json.decoder import JSONDecodeError
from typing import List, Literal, Optional, Union
from uuid import UUID

from fastapi import APIRouter, Depends, Form, Header, Query, Request, UploadFile, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.orm import Session
from typing_extensions import Annotated

from budapp.commons import logging
from budapp.commons.constants import ModalityEnum, ModelEndpointEnum, PermissionEnum
from budapp.commons.dependencies import (
    get_current_active_user,
    get_current_active_user_or_internal,
    get_session,
    parse_ordering_fields,
)
from budapp.commons.exceptions import ClientException
from budapp.commons.schemas import ErrorResponse, SuccessResponse
from budapp.user_ops.schemas import User
from budapp.workflow_ops.schemas import RetrieveWorkflowDataResponse
from budapp.workflow_ops.services import WorkflowService

from ..commons.permission_handler import require_permissions, require_permissions_or_internal
from .quantization_services import QuantizationService
from .schemas import (
    CancelDeploymentWorkflowRequest,
    CreateCloudModelWorkflowRequest,
    CreateCloudModelWorkflowResponse,
    CreateLocalModelWorkflowRequest,
    EditModel,
    LeaderboardTableResponse,
    LocalModelScanRequest,
    ModelAuthorFilter,
    ModelAuthorResponse,
    ModelCatalogFilter,
    ModelCatalogItem,
    ModelCatalogResponse,
    ModelDeployStepRequest,
    ModelDetailSuccessResponse,
    ModelFilter,
    ModelPaginatedResponse,
    ProviderFilter,
    ProviderResponse,
    QuantizationMethodFilter,
    QuantizationMethodResponse,
    QuantizeModelWorkflowRequest,
    RecommendedTagsResponse,
    TagsListResponse,
    TasksListResponse,
    TopLeaderboardRequest,
    TopLeaderboardResponse,
)
from .services import (
    CloudModelService,
    CloudModelWorkflowService,
    LocalModelWorkflowService,
    ModelCatalogService,
    ModelService,
    ProviderService,
)


logger = logging.get_logger(__name__)

model_router = APIRouter(prefix="/models", tags=["model"])


@model_router.get(
    "/",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_200_OK: {
            "model": ModelPaginatedResponse,
            "description": "Successfully list all models",
        },
    },
    description="List all models",
)
@require_permissions(permissions=[PermissionEnum.MODEL_VIEW])
async def list_all_models(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    filters: Annotated[ModelFilter, Depends()],
    author: List[str] = Query(default=[]),
    modality: List[ModalityEnum] = Query(default=[]),
    supported_endpoints: List[ModelEndpointEnum] = Query(default=[]),
    tags: List[str] = Query(default=[]),
    tasks: List[str] = Query(default=[]),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=0),
    order_by: Optional[List[str]] = Depends(parse_ordering_fields),
    search: bool = False,
) -> Union[ModelPaginatedResponse, ErrorResponse]:
    """List all models."""
    # Calculate offset
    offset = (page - 1) * limit

    # Convert UserFilter to dictionary
    filters_dict = filters.model_dump(exclude_none=True, exclude={"table_source"})

    # Update filters_dict only for non-empty lists
    filter_updates = {
        "tags": tags,
        "tasks": tasks,
        "author": author,
        "modality": modality,
        "supported_endpoints": supported_endpoints,
    }
    filters_dict.update({k: v for k, v in filter_updates.items() if v})

    # Perform router level validation
    if filters.table_source == "cloud_model" and filter_updates["author"]:
        return ErrorResponse(
            code=status.HTTP_400_BAD_REQUEST,
            message="Author is not allowed for cloud models.",
        ).to_http_response()

    if filters.table_source == "cloud_model" and (filters.base_model or filters.base_model_relation):
        return ErrorResponse(
            code=status.HTTP_400_BAD_REQUEST,
            message="Base model and base model relation are not allowed for cloud models.",
        ).to_http_response()

    if filters.model_size_min and filters.model_size_max and filters.model_size_min > filters.model_size_max:
        return ErrorResponse(
            code=status.HTTP_400_BAD_REQUEST,
            message="Model size min is greater than model size max.",
        ).to_http_response()

    try:
        if filters.table_source == "cloud_model":
            db_models, count = await CloudModelService(session).get_all_cloud_models(
                offset, limit, filters_dict, order_by, search
            )
        else:
            db_models, count = await ModelService(session).get_all_active_models(
                offset, limit, filters_dict, order_by, search
            )
    except ClientException as e:
        logger.exception(f"Failed to get all models: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get all models: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get all cloud models"
        ).to_http_response()

    return ModelPaginatedResponse(
        models=db_models,
        total_record=count,
        page=page,
        limit=limit,
        object="models.list",
        code=status.HTTP_200_OK,
    ).to_http_response()


@model_router.post(
    "/top-leaderboards",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_200_OK: {
            "model": TopLeaderboardResponse,
            "description": "Successfully listed top leaderboards",
        },
    },
    description="List top leaderboards",
)
async def list_top_leaderboards(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    request: TopLeaderboardRequest,
) -> Union[TopLeaderboardResponse, ErrorResponse]:
    """List top leaderboards."""
    try:
        leaderboards = await ModelService(session).get_top_leaderboards(request.benchmarks, request.k)
        return TopLeaderboardResponse(
            leaderboards=leaderboards,
            code=status.HTTP_200_OK,
            object="leaderboard.top",
            message="Successfully listed top leaderboards",
        ).to_http_response()
    except ClientException as e:
        logger.error(f"Failed to list top leaderboards: {e.message}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to list top leaderboards: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to list top leaderboards",
        ).to_http_response()


@model_router.get(
    "/providers",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_200_OK: {
            "model": ProviderResponse,
            "description": "Successfully list all providers",
        },
    },
    description="List all model providers",
)
async def list_providers(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    filters: ProviderFilter = Depends(),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=0),
    order_by: Optional[List[str]] = Depends(parse_ordering_fields),
    search: bool = False,
) -> Union[ProviderResponse, ErrorResponse]:
    """List all model providers."""
    # Calculate offset
    offset = (page - 1) * limit

    # Convert UserFilter to dictionary
    filters_dict = filters.model_dump(exclude_none=True)

    try:
        db_providers, count = await ProviderService(session).get_all_providers(
            offset, limit, filters_dict, order_by, search
        )
    except Exception as e:
        logger.exception(f"Failed to get all providers: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get all providers"
        ).to_http_response()

    return ProviderResponse(
        providers=db_providers,
        total_record=count,
        page=page,
        limit=limit,
        object="providers.list",
        code=status.HTTP_200_OK,
    ).to_http_response()


@model_router.post(
    "/cloud-model-workflow",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_200_OK: {
            "model": RetrieveWorkflowDataResponse,
            "description": "Successfully add cloud model workflow",
        },
    },
    description="Add cloud model workflow",
)
@require_permissions_or_internal(permissions=[PermissionEnum.MODEL_MANAGE])
async def add_cloud_model_workflow(
    current_user: Annotated[User, Depends(get_current_active_user_or_internal)],
    session: Annotated[Session, Depends(get_session)],
    request: CreateCloudModelWorkflowRequest,
) -> Union[RetrieveWorkflowDataResponse, ErrorResponse]:
    """Add cloud model workflow.

    This endpoint supports both JWT authentication (for external API calls)
    and internal Dapr service-to-service calls (using dapr-api-token header).
    """
    try:
        db_workflow = await CloudModelWorkflowService(session).add_cloud_model_workflow(
            current_user_id=current_user.id,
            request=request,
        )

        return await WorkflowService(session).retrieve_workflow_data(db_workflow.id)
    except ClientException as e:
        logger.exception(f"Failed to add cloud model workflow: {e}")
        return ErrorResponse(code=status.HTTP_400_BAD_REQUEST, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to add cloud model workflow: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to add cloud model workflow"
        ).to_http_response()


@model_router.post(
    "/local-model-workflow",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_200_OK: {
            "model": RetrieveWorkflowDataResponse,
            "description": "Successfully add local model workflow",
        },
    },
    description="Add local model workflow",
)
@require_permissions_or_internal(permissions=[PermissionEnum.MODEL_MANAGE])
async def add_local_model_workflow(
    current_user: Annotated[User, Depends(get_current_active_user_or_internal)],
    session: Annotated[Session, Depends(get_session)],
    request: CreateLocalModelWorkflowRequest,
) -> Union[RetrieveWorkflowDataResponse, ErrorResponse]:
    """Add local model workflow."""
    try:
        db_workflow = await LocalModelWorkflowService(session).add_local_model_workflow(
            current_user_id=current_user.id,
            request=request,
        )

        return await WorkflowService(session).retrieve_workflow_data(db_workflow.id)
    except ClientException as e:
        logger.exception(f"Failed to add local model workflow: {e}")
        return ErrorResponse(code=status.HTTP_400_BAD_REQUEST, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to add local model workflow: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to add local model workflow"
        ).to_http_response()


@model_router.patch(
    "/{model_id}",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_200_OK: {
            "model": CreateCloudModelWorkflowResponse,
            "description": "Successfully edited cloud model",
        },
    },
    description="Edit cloud model",
)
@require_permissions(permissions=[PermissionEnum.MODEL_MANAGE])
async def edit_model(
    model_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    name: str | None = Form(None),
    description: str | None = Form(None),
    tags: str | None = Form(None),
    tasks: str | None = Form(None),
    icon: str | None = Form(None),
    paper_urls: str | None = Form(None),
    github_url: str | None = Form(None),
    huggingface_url: str | None = Form(None),
    website_url: str | None = Form(None),
    license_file: UploadFile | None = None,
    license_url: str | None = Form(None),
    remove_license: bool = Form(False),
) -> Union[SuccessResponse, ErrorResponse]:
    """Edit cloud model with file upload."""
    logger.debug(
        f"Received data: name={name}, description={description}, tags={tags}, tasks={tasks}, paper_urls={paper_urls}, github_url={github_url}, huggingface_url={huggingface_url}, website_url={website_url}, license_file={license_file}, license_url={license_url}"
    )

    try:
        tags = [] if isinstance(tags, str) and len(tags) == 0 else json.loads(tags) if tags else None

        tasks = [] if isinstance(tasks, str) and len(tasks) == 0 else json.loads(tasks) if tasks else None

        if isinstance(tags, str) and len(paper_urls) == 0:
            paper_urls = []
        elif isinstance(paper_urls, str) and len(paper_urls) > 0:
            # Split the first element into a list of URLs and validate each URL in loop
            paper_urls = [url.strip() for url in paper_urls.split(",")]

        edit_model = EditModel(
            name=name if name else None,
            description=description if description else None,
            tags=tags if isinstance(tags, list) else None,
            tasks=tasks if isinstance(tasks, list) else None,
            icon=icon if icon else None,
            paper_urls=paper_urls if isinstance(paper_urls, list) else None,
            github_url=github_url if github_url else None,
            huggingface_url=huggingface_url if huggingface_url else None,
            website_url=website_url if website_url else None,
            license_url=license_url if license_url else None,
            license_file=license_file if license_file else None,
            remove_license=remove_license,
        )

        # Pass file and edit_model data to your service
        await ModelService(session).edit_model(
            current_user_id=current_user.id,
            model_id=model_id,
            data=edit_model.model_dump(exclude_none=True, exclude_unset=True),
        )

        return SuccessResponse(message="Model edited successfully", code=status.HTTP_200_OK).to_http_response()
    except ClientException as e:
        logger.exception(f"Failed to edit Model: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except ValidationError as e:
        logger.exception(f"ValidationErrors: {str(e)}")
        raise RequestValidationError(e.errors())
    except JSONDecodeError as e:
        logger.exception(f"Failed to edit model: {e}")
        return ErrorResponse(
            code=status.HTTP_422_UNPROCESSABLE_ENTITY, message="Failed to edit model. Invalid input format."
        ).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to edit model: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to edit model"
        ).to_http_response()


# @model_router.get(
#     "/cloud-model-workflow/{workflow_id}",
#     responses={
#         status.HTTP_500_INTERNAL_SERVER_ERROR: {
#             "model": ErrorResponse,
#             "description": "Service is unavailable due to server error",
#         },
#         status.HTTP_400_BAD_REQUEST: {
#             "model": ErrorResponse,
#             "description": "Service is unavailable due to client error",
#         },
#         status.HTTP_200_OK: {
#             "model": CreateCloudModelWorkflowResponse,
#             "description": "Successfully add cloud model workflow",
#         },
#     },
#     description="Get cloud model workflow",
# )
# async def get_cloud_model_workflow(
#     current_user: Annotated[User, Depends(get_current_active_user)],
#     session: Annotated[Session, Depends(get_session)],
#     workflow_id: UUID,
# ) -> Union[CreateCloudModelWorkflowResponse, ErrorResponse]:
#     """Get cloud model workflow."""
#     try:
#         return await CloudModelWorkflowService(session).get_cloud_model_workflow(workflow_id)
#     except ClientException as e:
#         logger.exception(f"Failed to get cloud model workflow: {e}")
#         return ErrorResponse(code=status.HTTP_400_BAD_REQUEST, message=e.message).to_http_response()
#     except Exception as e:
#         logger.exception(f"Failed to get cloud model workflow: {e}")
#         return ErrorResponse(
#             code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get cloud model workflow"
#         ).to_http_response()


# @model_router.get(
#     "/cloud-models",
#     responses={
#         status.HTTP_500_INTERNAL_SERVER_ERROR: {
#             "model": ErrorResponse,
#             "description": "Service is unavailable due to server error",
#         },
#         status.HTTP_400_BAD_REQUEST: {
#             "model": ErrorResponse,
#             "description": "Service is unavailable due to client error",
#         },
#         status.HTTP_200_OK: {
#             "model": ProviderResponse,
#             "description": "Successfully list all providers",
#         },
#     },
#     description="List all cloud models",
# )
# async def list_cloud_models(
#     current_user: Annotated[User, Depends(get_current_active_user)],
#     session: Annotated[Session, Depends(get_session)],
#     filters: Annotated[CloudModelFilter, Depends()],
#     tags: List[str] = Query(default_factory=list),
#     tasks: List[str] = Query(default_factory=list),
#     page: int = Query(1, ge=1),
#     limit: int = Query(10, ge=0),
#     order_by: Optional[List[str]] = Depends(parse_ordering_fields),
#     search: bool = False,
# ) -> Union[CloudModelResponse, ErrorResponse]:
#     """List all cloud models."""
#     # Calculate offset
#     offset = (page - 1) * limit

#     # Convert UserFilter to dictionary
#     filters_dict = filters.model_dump(exclude_none=True)
#     if tags:
#         filters_dict["tags"] = tags
#     if tasks:
#         filters_dict["tasks"] = tasks

#     try:
#         db_models, count = await CloudModelService(session).get_all_cloud_models(
#             offset, limit, filters_dict, order_by, search
#         )
#     except Exception as e:
#         logger.exception(f"Failed to get all cloud models: {e}")
#         return ErrorResponse(
#             code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get all cloud models"
#         ).to_http_response()

#     return CloudModelResponse(
#         cloud_models=db_models,
#         total_record=count,
#         page=page,
#         limit=limit,
#         object="cloud_models.list",
#         code=status.HTTP_200_OK,
#     ).to_http_response()


@model_router.get(
    "/cloud-models/recommended-tags",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_200_OK: {
            "model": RecommendedTagsResponse,
            "description": "Successfully list all recommended tags",
        },
    },
    description="List all cloud model recommended tags",
)
@require_permissions(permissions=[PermissionEnum.MODEL_VIEW])
async def list_cloud_model_recommended_tags(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=0),
) -> Union[RecommendedTagsResponse, ErrorResponse]:
    """List all most used tags."""
    # Calculate offset
    offset = (page - 1) * limit

    try:
        db_tags, count = await CloudModelService(session).get_all_recommended_tags(offset, limit)
    except Exception as e:
        logger.exception(f"Failed to get all recommended tags: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get all recommended tags"
        ).to_http_response()

    return RecommendedTagsResponse(
        tags=db_tags,
        total_record=count,
        page=page,
        limit=limit,
        object="recommended_tags.list",
        code=status.HTTP_200_OK,
    ).to_http_response()


@model_router.get(
    "/tags",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_200_OK: {
            "model": TagsListResponse,
            "description": "Successfully searched tags by name",
        },
    },
    description="Search model tags by name with pagination",
)
@require_permissions(permissions=[PermissionEnum.MODEL_VIEW])
async def list_model_tags(
    session: Annotated[Session, Depends(get_session)],
    name: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_active_user),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1),
) -> Union[TagsListResponse, ErrorResponse]:
    """List tags by name with pagination support."""
    offset = (page - 1) * limit

    try:
        db_tags, count = await ModelService(session).list_model_tags(name or "", offset, limit)
    except Exception as e:
        return ErrorResponse(code=status.HTTP_500_INTERNAL_SERVER_ERROR, message=str(e)).to_http_response()

    return TagsListResponse(
        tags=db_tags,
        total_record=count,
        page=page,
        limit=limit,
        object="tags.search",
        code=status.HTTP_200_OK,
    ).to_http_response()


@model_router.get(
    "/tasks",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_200_OK: {
            "model": TasksListResponse,
            "description": "Successfully listed tasks",
        },
    },
    description="Search model tags by name with pagination",
)
@require_permissions(permissions=[PermissionEnum.MODEL_VIEW])
async def list_model_tasks(
    session: Annotated[Session, Depends(get_session)],
    name: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_active_user),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1),
) -> Union[TasksListResponse, ErrorResponse]:
    """List tasks by name with pagination support."""
    offset = (page - 1) * limit

    try:
        db_tasks, count = await ModelService(session).list_model_tasks(name or "", offset, limit)
    except Exception as e:
        return ErrorResponse(code=status.HTTP_500_INTERNAL_SERVER_ERROR, message=str(e)).to_http_response()

    return TasksListResponse(
        tasks=db_tasks,
        total_record=count,
        page=page,
        limit=limit,
        object="tasks.list",
        code=status.HTTP_200_OK,
    ).to_http_response()


@model_router.get(
    "/authors",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_200_OK: {
            "model": ModelAuthorResponse,
            "description": "Successfully searched author by name",
        },
    },
    description="Search model author by name with pagination",
)
@require_permissions(permissions=[PermissionEnum.MODEL_VIEW])
async def list_all_model_authors(
    session: Annotated[Session, Depends(get_session)],
    filters: Annotated[ModelAuthorFilter, Depends()],
    current_user: User = Depends(get_current_active_user),
    search: bool = False,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=0),
    order_by: Optional[List[str]] = Depends(parse_ordering_fields),
) -> Union[ModelAuthorResponse, ErrorResponse]:
    """Search author by name with pagination support."""
    offset = (page - 1) * limit

    filters_dict = filters.model_dump(exclude_none=True)

    try:
        db_authors, count = await ModelService(session).list_all_model_authors(
            offset, limit, filters_dict, order_by, search
        )
    except Exception as e:
        return ErrorResponse(code=status.HTTP_500_INTERNAL_SERVER_ERROR, message=str(e)).to_http_response()

    return ModelAuthorResponse(
        authors=db_authors,
        total_record=count,
        page=page,
        limit=limit,
        object="author.list",
        code=status.HTTP_200_OK,
    ).to_http_response()


@model_router.get(
    "/quantization-methods",
    responses={
        status.HTTP_200_OK: {
            "model": QuantizationMethodResponse,
            "description": "Successfully listed quantization methods",
        },
    },
    description="List quantization methods",
)
@require_permissions(permissions=[PermissionEnum.MODEL_VIEW])
async def list_quantization_methods(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    filters: Annotated[QuantizationMethodFilter, Depends()],
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1),
    order_by: Optional[List[str]] = Depends(parse_ordering_fields),
    search: bool = Query(False, description="Whether to search for quantization methods"),
) -> Union[QuantizationMethodResponse, ErrorResponse]:
    """List quantization methods."""
    # Calculate offset
    offset = (page - 1) * limit

    # Convert UserFilter to dictionary
    filters_dict = filters.model_dump(exclude_none=True)

    try:
        db_quantization_methods, count = await QuantizationService(session).get_quantization_methods(
            offset, limit, filters_dict, order_by, search
        )
        logger.info(f"db_quantization_methods: {db_quantization_methods[0]}")
        logger.info(f"count: {count}")
    except Exception as e:
        logger.exception(f"Failed to get all quantization methods: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get all quantization methods"
        ).to_http_response()

    return QuantizationMethodResponse(
        quantization_methods=db_quantization_methods,
        total_record=count,
        page=page,
        limit=limit,
        object="quantization_methods.list",
        code=status.HTTP_200_OK,
    ).to_http_response()


@model_router.get(
    "/catalog",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_200_OK: {
            "model": ModelCatalogResponse,
            "description": "Successfully listed published models",
        },
    },
    description="List published models available in the catalog with optional search and filtering",
)
@require_permissions(permissions=[PermissionEnum.CLIENT_ACCESS])
async def list_catalog_models(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    filters: Annotated[ModelCatalogFilter, Depends()],
    modality: Optional[List[ModalityEnum]] = Query(None, description="Filter by modality"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    order_by: Optional[List[str]] = Depends(parse_ordering_fields),
    search: Optional[str] = Query(None, description="Search term for full-text search", min_length=2),
) -> Union[ModelCatalogResponse, ErrorResponse]:
    """List published models available for CLIENT users with optional filtering and search."""
    try:
        # Calculate offset
        offset = (page - 1) * limit

        # Convert filter to dictionary and add modality
        filters_dict = filters.model_dump(exclude_none=True)
        if modality:
            filters_dict["modality"] = modality

        # Get models from catalog service
        db_models, count = await ModelCatalogService(session).get_published_models(
            offset=offset,
            limit=limit,
            filters=filters_dict,
            order_by=order_by or [("published_date", "desc")],
            search_term=search,
        )

        return ModelCatalogResponse(
            models=db_models,
            total_record=count,
            page=page,
            limit=limit,
            object="catalog.models.list",
            code=status.HTTP_200_OK,
        ).to_http_response()
    except ClientException as e:
        logger.exception(f"Failed to list catalog models: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to list catalog models: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to list catalog models",
        ).to_http_response()


@model_router.get(
    "/catalog/{endpoint_id}",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Model not found",
        },
        status.HTTP_200_OK: {
            "model": ModelDetailSuccessResponse,
            "description": "Successfully retrieved model details",
        },
    },
    description="Get detailed information about a published model",
)
@require_permissions(permissions=[PermissionEnum.CLIENT_ACCESS])
async def get_catalog_model_details(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    endpoint_id: UUID,
) -> Union[ModelDetailSuccessResponse, ErrorResponse]:
    """Get detailed information about a specific published model."""
    try:
        return await ModelCatalogService(session).get_catalog_model_details(endpoint_id)
    except ClientException as e:
        logger.exception(f"Failed to get catalog model details: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get catalog model details: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to get catalog model details",
        ).to_http_response()


@model_router.get(
    "/{model_id}",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Model not found",
        },
        status.HTTP_200_OK: {
            "model": ModelDetailSuccessResponse,
            "description": "Successfully retrieved model details",
        },
    },
    description="Retrieve details of a model by ID",
)
@require_permissions(permissions=[PermissionEnum.MODEL_VIEW])
async def retrieve_model(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    model_id: UUID,
) -> Union[ModelDetailSuccessResponse, ErrorResponse]:
    """Retrieve details of a model by its ID."""
    try:
        return await ModelService(session).retrieve_model(model_id)
    except ClientException as e:
        logger.exception(f"Failed to get model details: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get model details: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve model details",
        ).to_http_response()


@model_router.post(
    "/security-scan",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_200_OK: {
            "model": RetrieveWorkflowDataResponse,
            "description": "Successfully scan local model",
        },
    },
    description="Scan local model",
)
@require_permissions(permissions=[PermissionEnum.MODEL_MANAGE])
async def scan_local_model_workflow(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    request: LocalModelScanRequest,
) -> Union[RetrieveWorkflowDataResponse, ErrorResponse]:
    """Scan local model."""
    try:
        db_workflow = await LocalModelWorkflowService(session).scan_local_model_workflow(
            current_user_id=current_user.id,
            request=request,
        )

        return await WorkflowService(session).retrieve_workflow_data(db_workflow.id)
    except ClientException as e:
        logger.exception(f"Failed to scan local model: {e}")
        return ErrorResponse(code=status.HTTP_400_BAD_REQUEST, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to scan local model: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to scan local model"
        ).to_http_response()


@model_router.post(
    "/cancel-deployment",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_200_OK: {
            "model": SuccessResponse,
            "description": "Successfully cancel model deployment",
        },
    },
    description="Cancel model deployment",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_MANAGE])
async def cancel_model_deployment(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    cancel_request: CancelDeploymentWorkflowRequest,
    x_resource_type: Annotated[Optional[str], Header()] = None,
    x_entity_id: Annotated[Optional[str], Header()] = None,
) -> Union[SuccessResponse, ErrorResponse]:
    """Cancel model deployment."""
    try:
        await ModelService(session).cancel_model_deployment_workflow(cancel_request.workflow_id)
        return SuccessResponse(
            message="Model deployment cancelled successfully",
            code=status.HTTP_200_OK,
            object="model.cancel_deployment",
        )
    except ClientException as e:
        logger.exception(f"Failed to cancel model deployment: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to cancel model deployment: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to cancel model deployment"
        ).to_http_response()


@model_router.delete(
    "/{model_id}",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Model not found",
        },
        status.HTTP_200_OK: {
            "model": SuccessResponse,
            "description": "Successfully deleted model",
        },
    },
    description="Delete an active model from the database",
)
@require_permissions_or_internal(permissions=[PermissionEnum.MODEL_MANAGE])
async def delete_model(
    current_user: Annotated[User, Depends(get_current_active_user_or_internal)],
    session: Annotated[Session, Depends(get_session)],
    model_id: UUID,
) -> Union[SuccessResponse, ErrorResponse]:
    """Delete a model by its ID."""
    _ = await ModelService(session).delete_active_model(model_id)
    logger.debug(f"Model deleted: {model_id}")

    return SuccessResponse(message="Model deleted successfully", code=status.HTTP_200_OK, object="model.delete")


@model_router.get(
    "/{model_id}/leaderboards",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Model not found",
        },
        status.HTTP_200_OK: {
            "model": LeaderboardTableResponse,
            "description": "Successfully listed leaderboards",
        },
    },
    description="List leaderboards of specific model by uri",
)
@require_permissions(permissions=[PermissionEnum.MODEL_VIEW])
async def list_leaderboards(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    model_id: UUID,
    table_source: Literal["cloud_model", "model"] = Query(default="model", description="The source of the model"),
    k: int = Query(10, ge=0, description="The maximum number of leaderboards to return"),
) -> Union[LeaderboardTableResponse, ErrorResponse]:
    """List leaderboards of specific model by uri."""
    try:
        db_leaderboards = await ModelService(session).list_leaderboards(model_id, table_source, k)
        return LeaderboardTableResponse(
            leaderboards=db_leaderboards,
            code=status.HTTP_200_OK,
            object="leaderboard.list",
            message="Successfully listed leaderboards",
        ).to_http_response()
    except ClientException as e:
        logger.error(f"Failed to list leaderboards: {e.message}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to list leaderboards: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to list leaderboards",
        ).to_http_response()


@model_router.post(
    "/quantize-model-workflow",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_200_OK: {
            "model": RetrieveWorkflowDataResponse,
            "description": "Successfully quantize model workflow",
        },
    },
    description="Quantize model workflow",
)
@require_permissions(permissions=[PermissionEnum.MODEL_MANAGE])
async def quantize_model_workflow(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    request: QuantizeModelWorkflowRequest,
) -> Union[RetrieveWorkflowDataResponse, ErrorResponse]:
    """Quantize model workflow."""
    try:
        db_workflow = await QuantizationService(session).quantize_model_workflow(
            current_user_id=current_user.id,
            request=request,
        )

        return await WorkflowService(session).retrieve_workflow_data(db_workflow.id)
    except ClientException as e:
        logger.exception(f"Failed to quantize model workflow: {e}")
        return ErrorResponse(code=status.HTTP_400_BAD_REQUEST, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to quantize model workflow: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to quantize model workflow"
        ).to_http_response()


@model_router.post(
    "/cancel-quantization",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_200_OK: {
            "model": SuccessResponse,
            "description": "Successfully cancel model quantization",
        },
    },
    description="Cancel model quantization",
)
@require_permissions(permissions=[PermissionEnum.MODEL_MANAGE])
async def cancel_model_quantization(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    cancel_request: CancelDeploymentWorkflowRequest,
) -> Union[SuccessResponse, ErrorResponse]:
    """Cancel model quantization."""
    try:
        await QuantizationService(session).cancel_model_quantization_workflow(cancel_request.workflow_id)
        return SuccessResponse(
            message="Model quantization cancelled successfully",
            code=status.HTTP_200_OK,
            object="model.cancel_quantization",
        )
    except ClientException as e:
        logger.exception(f"Failed to cancel model quantization: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to cancel model quantization: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to cancel model quantization"
        ).to_http_response()


@model_router.post(
    "/deploy-workflow",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_200_OK: {
            "model": RetrieveWorkflowDataResponse,
            "description": "Successfully deploy a model in server for a specified project by step",
        },
    },
    description="Deploy a model in server for a specified project by step",
)
@require_permissions_or_internal(permissions=[PermissionEnum.ENDPOINT_MANAGE])
async def deploy_model_by_step(
    current_user: Annotated[User, Depends(get_current_active_user_or_internal)],
    session: Annotated[Session, Depends(get_session)],
    deploy_request: ModelDeployStepRequest,
    x_resource_type: Annotated[Optional[str], Header()] = None,
    x_entity_id: Annotated[Optional[str], Header()] = None,
) -> Union[RetrieveWorkflowDataResponse, ErrorResponse]:
    """Deploy a model in server for a specified project by step."""
    try:
        db_workflow = await ModelService(session).deploy_model_by_step(
            current_user_id=current_user.id,
            step_number=deploy_request.step_number,
            workflow_id=deploy_request.workflow_id,
            workflow_total_steps=deploy_request.workflow_total_steps,
            model_id=deploy_request.model_id,
            project_id=deploy_request.project_id,
            cluster_id=deploy_request.cluster_id,
            endpoint_name=deploy_request.endpoint_name,
            deploy_config=deploy_request.deploy_config,
            template_id=deploy_request.template_id,
            trigger_workflow=deploy_request.trigger_workflow,
            credential_id=deploy_request.credential_id,
            budaiscaler_specification=deploy_request.budaiscaler_specification,
            hardware_mode=deploy_request.hardware_mode,
            enable_tool_calling=deploy_request.enable_tool_calling,
            enable_reasoning=deploy_request.enable_reasoning,
            tool_calling_parser_type=deploy_request.tool_calling_parser_type,
            reasoning_parser_type=deploy_request.reasoning_parser_type,
            chat_template=deploy_request.chat_template,
            supports_lora=deploy_request.supports_lora,
            supports_pipeline_parallelism=deploy_request.supports_pipeline_parallelism,
        )

        return await WorkflowService(session).retrieve_workflow_data(db_workflow.id)
    except ClientException as e:
        logger.exception(f"Failed to deploy model: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to deploy model: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to deploy model"
        ).to_http_response()
