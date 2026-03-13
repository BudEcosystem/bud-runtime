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

"""Pydantic schemas for Template System."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class HelmChartConfig(BaseModel):
    """Configuration for a Helm chart component."""

    model_config = ConfigDict(extra="forbid")

    ref: str | None = Field(None, description="Chart reference (OCI registry, HTTPS URL, or local path)")
    version: str | None = Field(None, description="Chart version constraint")
    values: dict[str, Any] = Field(default_factory=dict, description="Default Helm values")
    git_repo: str | None = Field(None, description="Git repository URL containing the Helm chart")
    git_ref: str = Field("main", description="Git branch, tag, or commit to checkout")
    chart_subpath: str = Field(".", description="Path within the git repo to the Helm chart directory")

    @field_validator("ref")
    @classmethod
    def validate_chart_ref(cls, v: str | None) -> str | None:
        if v is None:
            return v
        import re

        allowed_patterns = [
            r"^oci://",  # OCI registry
            r"^https?://",  # HTTP(S) URL
            r"^charts/",  # Local chart directory
            r"^\./",  # Relative path
            r"^\.\./",  # Relative parent path
        ]
        if not any(re.match(pattern, v) for pattern in allowed_patterns):
            raise ValueError(f"Invalid chart reference '{v}'. Must start with oci://, https://, charts/, ./, or ../")
        return v

    @model_validator(mode="after")
    def validate_chart_source(self) -> "HelmChartConfig":
        if not self.ref and not self.git_repo:
            raise ValueError("Either 'ref' or 'git_repo' must be provided")
        return self


class AccessUIConfig(BaseModel):
    """UI access mode configuration."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(False, description="Whether UI access is available")
    port: int = Field(80, description="Container port serving the UI")
    path: str = Field("/", description="Root path of the UI on the service")
    service_suffix: str = Field("", description="Suffix appended to the Helm release service name for routing")


class ApiEndpointSpec(BaseModel):
    """OpenAPI-style endpoint spec for documentation."""

    model_config = ConfigDict(extra="forbid")

    path: str = Field(..., description="API endpoint path")
    method: str = Field("POST", description="HTTP method")
    description: str = Field("", description="Endpoint description")
    request_body: dict[str, Any] | None = Field(None)
    response: dict[str, Any] | None = Field(None)


class AccessAPIConfig(BaseModel):
    """API access mode configuration."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(False, description="Whether API access is available")
    port: int = Field(8080, description="Container port serving the API")
    base_path: str = Field("/", description="API base path on the service")
    service_suffix: str = Field("", description="Suffix appended to the Helm release service name for routing")
    spec: list[ApiEndpointSpec] = Field(default_factory=list, description="API endpoints for documentation")


class AccessConfig(BaseModel):
    """Access mode configuration for a template."""

    model_config = ConfigDict(extra="forbid")

    ui: AccessUIConfig = Field(default_factory=AccessUIConfig)
    api: AccessAPIConfig = Field(default_factory=AccessAPIConfig)


class TemplateComponentSchema(BaseModel):
    """Schema for a template component definition."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., description="Component identifier within the template")
    display_name: str = Field(..., description="Human-readable component name")
    description: str | None = Field(None, description="Component description")
    type: str = Field(..., description="Component type (model, embedder, reranker, helm)")
    required: bool = Field(True, description="Whether this component is required")
    default_component: str | None = Field(None, description="Default component name from registry")
    compatible_components: list[str] = Field(default_factory=list, description="List of compatible component names")
    chart: HelmChartConfig | None = Field(None, description="Helm chart configuration (required for helm type)")

    @model_validator(mode="after")
    def validate_chart_for_helm_type(self) -> "TemplateComponentSchema":
        if self.type == "helm" and self.chart is None:
            raise ValueError("'chart' configuration is required for helm type components")
        if self.type != "helm" and self.chart is not None:
            raise ValueError("'chart' configuration is only allowed for helm type components")
        return self


class TemplateParameterSchema(BaseModel):
    """Schema for a template parameter definition."""

    model_config = ConfigDict(extra="forbid")

    type: str = Field(..., description="Parameter type (integer, float, string, boolean)")
    default: Any = Field(..., description="Default value for the parameter")
    min: float | None = Field(None, description="Minimum value for numeric types")
    max: float | None = Field(None, description="Maximum value for numeric types")
    description: str = Field(..., description="Parameter description")


class TemplateResourcesSchema(BaseModel):
    """Schema for template resource requirements."""

    model_config = ConfigDict(extra="forbid")

    minimum: dict[str, Any] = Field(..., description="Minimum resource requirements")
    recommended: dict[str, Any] = Field(..., description="Recommended resource requirements")


class TemplateSchema(BaseModel):
    """Schema for a complete template definition."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., description="Template identifier")
    display_name: str = Field(..., description="Human-readable template name")
    version: str = Field(..., description="Template version")
    description: str = Field(..., description="Template description")
    category: str | None = Field(None, description="Template category (rag, conversational, etc.)")
    tags: list[str] = Field(default_factory=list, description="Template tags for filtering")
    components: list[TemplateComponentSchema] = Field(..., description="Components required by this template")
    parameters: dict[str, TemplateParameterSchema] = Field(default_factory=dict, description="Configurable parameters")
    resources: TemplateResourcesSchema | None = Field(None, description="Resource requirements")
    deployment_order: list[str] = Field(
        default_factory=list, description="Order in which components should be deployed"
    )
    access: AccessConfig | None = Field(None, description="Access mode configuration")


class TemplateCreateSchema(BaseModel):
    """Schema for creating a template (internal use by sync)."""

    model_config = ConfigDict(extra="forbid")

    name: str
    display_name: str
    version: str
    description: str
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    resources: dict[str, Any] | None = None
    deployment_order: list[str] = Field(default_factory=list)
    access: AccessConfig | None = None


class CustomTemplateCreateSchema(BaseModel):
    """Schema for creating a custom user template via API."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        pattern=r"^[a-z0-9][a-z0-9-]*$",
        description="Template identifier (lowercase alphanumeric with hyphens)",
    )
    display_name: str = Field(..., min_length=1, max_length=255, description="Human-readable template name")
    version: str = Field("1.0.0", description="Template version")
    description: str = Field(..., min_length=1, description="Template description")
    category: str | None = Field(None, max_length=100, description="Template category")
    tags: list[str] = Field(default_factory=list, description="Template tags for filtering")
    components: list[TemplateComponentSchema] = Field(
        ..., min_length=1, description="Components required by this template"
    )
    parameters: dict[str, TemplateParameterSchema] = Field(default_factory=dict, description="Configurable parameters")
    resources: TemplateResourcesSchema | None = Field(None, description="Resource requirements")
    deployment_order: list[str] = Field(
        default_factory=list, description="Order in which components should be deployed"
    )
    is_public: bool = Field(False, description="Whether this template is publicly visible")
    access: AccessConfig | None = Field(None, description="Access mode configuration")

    @field_validator("name")
    @classmethod
    def validate_name_not_reserved(cls, v: str) -> str:
        if v.startswith("system-"):
            raise ValueError("Template names starting with 'system-' are reserved")
        return v


class CustomTemplateUpdateSchema(BaseModel):
    """Schema for updating a custom user template (partial update)."""

    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(None, min_length=1, max_length=255)
    version: str | None = None
    description: str | None = Field(None, min_length=1)
    category: str | None = Field(None, max_length=100)
    tags: list[str] | None = None
    components: list[TemplateComponentSchema] | None = Field(None, min_length=1)
    parameters: dict[str, TemplateParameterSchema] | None = None
    resources: TemplateResourcesSchema | None = None
    deployment_order: list[str] | None = None
    is_public: bool | None = None
    access: AccessConfig | None = None


class TemplateResponseSchema(BaseModel):
    """Schema for template API response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    display_name: str
    version: str
    description: str
    category: str | None
    tags: list[str]
    parameters: dict[str, Any]
    resources: dict[str, Any] | None
    deployment_order: list[str]
    access: dict[str, Any] | None = None
    source: str
    user_id: str | None
    is_public: bool
    created_at: str
    updated_at: str


class TemplateComponentResponseSchema(BaseModel):
    """Schema for template component API response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    template_id: str
    name: str
    display_name: str
    description: str | None
    component_type: str
    required: bool
    default_component: str | None
    compatible_components: list[str]
    chart: dict[str, Any] | None = None
    sort_order: int
