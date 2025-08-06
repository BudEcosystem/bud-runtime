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


"""Contains core Pydantic schemas used for data validation and serialization within the project ops services."""

from datetime import datetime
from typing import List, Literal

from pydantic import (
    UUID4,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from budapp.commons.schemas import PaginatedSuccessResponse, SuccessResponse, Tag

from ..commons.constants import ClusterStatusEnum, PermissionEnum, ProjectTypeEnum, UserStatusEnum
from ..commons.helpers import validate_icon
from ..permissions.schemas import PermissionList
from ..user_ops.schemas import UserInfo


class ProjectBase(BaseModel):
    name: str
    description: str | None = None
    tags: List[Tag] | None = None
    icon: str | None = None
    project_type: ProjectTypeEnum = Field(default=ProjectTypeEnum.CLIENT_APP)


# class ProjectRequest(ProjectBase):
#     benchmark: bool = False

#     @field_validator("icon", mode="before")
#     @classmethod
#     def icon_validate(cls, value: str | None) -> str | None:
#         """Validate the icon."""
#         if value is not None and not validate_icon(value):
#             raise ValueError("invalid icon")
#         return value


# class ProjectCreate(ProjectRequest):
#     created_by: UUID4


class EditProjectRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=400)
    tags: List[Tag] | None = None
    icon: str | None = None
    project_type: ProjectTypeEnum | None = None

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        """Ensure the name is not empty or only whitespace."""
        if value is not None and not value.strip():
            raise ValueError("Project name cannot be empty or only whitespace.")
        return value

    @field_validator("icon", mode="before")
    @classmethod
    def icon_validate(cls, value: str | None) -> str | None:
        """Validate the icon."""
        if value is not None and not validate_icon(value):
            raise ValueError("invalid icon")
        return value


class ProjectUserAdd(BaseModel):
    """User to add to project."""

    user_id: UUID4 | None = None
    email: EmailStr | None = None
    scopes: list[str]

    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, v: list[str]) -> list[str]:
        valid_scopes = {
            PermissionEnum.ENDPOINT_VIEW.value,
            PermissionEnum.ENDPOINT_MANAGE.value,
        }
        if not all(scope in valid_scopes for scope in v):
            raise ValueError(f"Found invalid scopes. Valid scopes are: {valid_scopes}")

        # If ENDPOINT_MANAGE is present, ensure ENDPOINT_VIEW is also included
        if PermissionEnum.ENDPOINT_MANAGE.value in v:
            v = list(set(v + [PermissionEnum.ENDPOINT_VIEW.value]))

        return v

    @model_validator(mode="after")
    def check_user_id_or_email(self) -> "ProjectUserAdd":
        user_id = self.user_id
        email = self.email
        if user_id is not None and email is not None:
            raise ValueError("Either user_id or email must be provided, but not both")
        elif user_id is None and email is None:
            raise ValueError("Either user_id or email must be provided")
        return self


class ProjectResponse(ProjectBase):
    """Project response to client schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID4


class SingleProjectResponse(SuccessResponse):
    project: ProjectResponse


class ProjectClusterListResponse(BaseModel):
    """Project cluster list response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID4
    name: str
    endpoint_count: int
    hardware_type: list[Literal["CPU", "GPU", "HPU"]]
    node_count: int
    worker_count: int
    status: ClusterStatusEnum
    created_at: datetime
    modified_at: datetime


class ProjectClusterPaginatedResponse(PaginatedSuccessResponse):
    """Project cluster paginated response schema."""

    clusters: list[ProjectClusterListResponse] = []


class ProjectClusterFilter(BaseModel):
    """Filter project cluster schema for filtering clusters based on specific criteria."""

    name: str | None = None
    status: ClusterStatusEnum | None = None


class Project(ProjectBase):
    """Project response to client schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID4
    created_by: UUID4 | None = None
    created_at: datetime
    modified_at: datetime


class ProjectCreateRequest(ProjectBase):
    benchmark: bool = False
    project_type: ProjectTypeEnum = Field(default=ProjectTypeEnum.CLIENT_APP)


class ProjectFilter(BaseModel):
    name: str | None = None


class PaginatedTagsResponse(PaginatedSuccessResponse):
    """Paginated tags response schema."""

    tags: list[Tag] = []


class ProjectSuccessResopnse(SuccessResponse):
    """Project success response schema."""

    project: Project


class ProjectListResponse(BaseModel):
    """Project list response to client schema."""

    project: Project
    users_count: int
    endpoints_count: int
    profile_colors: list

    # Convert users_count and endpoints_count to int if they are None
    @field_validator("users_count", "endpoints_count", mode="before")
    @classmethod
    def convert_none_to_zero(cls, v):
        if not isinstance(v, int):
            return 0
        return v


class PaginatedProjectsResponse(PaginatedSuccessResponse):
    """Paginated projects response schema."""

    projects: list[ProjectListResponse] = []


class ProjectDetailResponse(SuccessResponse):
    """Project response to client schema."""

    project: ProjectResponse
    endpoints_count: int


class ProjectUserAddList(BaseModel):
    """List of users to add to project."""

    users: list[ProjectUserAdd]


class ProjectUserUpdate(BaseModel):
    user_ids: list[UUID4]


class ProjectUserList(UserInfo):
    """List of users assigned to a project."""

    permissions: List[PermissionList]
    project_role: str
    status: UserStatusEnum


class PagenatedProjectUserResponse(PaginatedSuccessResponse):
    """Paginated response for project users."""

    users: List[ProjectUserList]
