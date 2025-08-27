import json
import uuid
from datetime import datetime
from enum import IntEnum
from typing import Annotated, Any, Dict, List, Optional, Union
from uuid import UUID

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    confloat,
    field_validator,
    model_validator,
)

from budapp.commons import logging
from budapp.commons.config import app_settings
from budapp.commons.constants import ApiCredentialTypeEnum, CredentialTypeEnum
from budapp.commons.schemas import PaginatedSuccessResponse, SuccessResponse
from budapp.initializers.provider_seeder import ProviderSeeder


logger = logging.get_logger(__name__)

PROPRIETARY_CREDENTIAL_DATA = ProviderSeeder._get_providers_data()

model_budget_type = Annotated[
    Dict[UUID, confloat(gt=0)], "A dictionary with UUID keys and float values greater than 0"
]


class CredentialBase(BaseModel):
    """Credential base schema."""

    encrypted_key: str


class CredentialCreate(CredentialBase):
    """Create credential schema."""

    user_id: UUID


class CredentialFilter(BaseModel):
    """Credential filter schema."""

    name: Optional[str] = None
    project_id: Optional[UUID] = None


class BudCredentialCreate(BaseModel):
    """Create credential schema."""

    user_id: UUID
    encrypted_key: str
    name: str
    project_id: UUID
    expiry: datetime | None
    max_budget: float | None
    model_budgets: Optional[model_budget_type] = None
    credential_type: Optional[ApiCredentialTypeEnum] = ApiCredentialTypeEnum.CLIENT_APP
    ip_whitelist: Optional[List[str]] = None

    model_config = ConfigDict(protected_namespaces=())


class ExpiryEnum(IntEnum):
    """Expiry enum."""

    NO_EXPIRY = 0
    THIRTY_DAYS = 30
    SIXTY_DAYS = 60
    NINETY_DAYS = 90


class CredentialRequest(BaseModel):
    """Credential request schema."""

    model_config = ConfigDict(protected_namespaces=())

    name: str
    project_id: UUID
    expiry: Optional[ExpiryEnum] = None
    max_budget: Optional[float] = Field(
        default=None, gt=0, description="Max budget must be greater than 0 if specified"
    )
    model_budgets: Optional[model_budget_type] = None
    credential_type: Optional[ApiCredentialTypeEnum] = None
    ip_whitelist: Optional[List[str]] = Field(
        default=None, description="List of allowed IP addresses for this credential"
    )

    @model_validator(mode="after")
    def validate_key(self) -> "CredentialRequest":
        if self.max_budget and self.model_budgets and (sum(self.model_budgets.values()) > self.max_budget):
            raise ValueError("Sum of model budgets should not exceed max budget")
        return self


class Credential(BudCredentialCreate):
    """Credential schema."""

    id: UUID
    created_at: datetime
    modified_at: datetime


class CredentialResponse(BaseModel):
    """Credential response schema."""

    name: str
    key: str
    project_id: UUID
    expiry: datetime | None
    max_budget: float | None
    model_budgets: Optional[model_budget_type] = None
    id: UUID
    created_at: datetime
    last_used_at: datetime | None
    credential_type: ApiCredentialTypeEnum
    ip_whitelist: Optional[List[str]] = None

    model_config = ConfigDict(protected_namespaces=())


class CredentialProject(BaseModel):
    """Credential project schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str


class CredentialDetails(BaseModel):
    """BudServe credential details."""

    model_config = ConfigDict(protected_namespaces=())

    name: str
    project: CredentialProject
    key: str
    expiry: datetime | None
    max_budget: float | None
    model_budgets: Optional[model_budget_type] = None
    id: UUID
    created_at: datetime
    last_used_at: datetime | None
    credential_type: ApiCredentialTypeEnum
    ip_whitelist: Optional[List[str]] = None


class CredentialUpdate(BaseModel):
    """Credential Update schema."""

    model_config = ConfigDict(protected_namespaces=())

    name: str | None = None
    expiry: Optional[ExpiryEnum] = None
    max_budget: float | None = None
    model_budgets: Optional[model_budget_type] = None
    ip_whitelist: Optional[List[str]] = None

    @model_validator(mode="after")
    def validate_key(self) -> "CredentialUpdate":
        if self.max_budget and self.model_budgets and (sum(self.model_budgets.values()) > self.max_budget):
            raise ValueError("Sum of model budgets should not exceed max budget")
        return self


class ProprietaryCredentialRequest(BaseModel):
    """Proprietary credential request schema."""

    name: str
    type: CredentialTypeEnum
    provider_id: Optional[UUID] = None
    other_provider_creds: Optional[dict] = {}

    @field_validator("other_provider_creds")
    @classmethod
    def validate_other_provider_creds(cls, v, info: ValidationInfo):
        # Validate the proprietary credentials using the common validator
        v = common_validator_for_provider_creds(v, info)

        return v


class ProprietaryCredentialResponse(BaseModel):
    """Proprietary Credential response schema."""

    model_config = ConfigDict(protected_namespaces=(), from_attributes=True)

    name: str
    type: CredentialTypeEnum
    other_provider_creds: dict | None
    id: UUID


class ProprietaryCredentialFilter(BaseModel):
    """Filter proprietary credential schema."""

    name: str | None = None
    type: CredentialTypeEnum | None = None
    id: UUID | None = None


class ProprietaryCredentialUpdate(BaseModel):
    """Proprietary Credential update schema."""

    name: str | None = None
    type: CredentialTypeEnum
    other_provider_creds: dict | None = None
    endpoint_id: UUID | None = None

    @field_validator("other_provider_creds")
    @classmethod
    def validate_other_provider_creds(cls, v, info: ValidationInfo):
        # Validate the proprietary credentials using the common validator
        v = common_validator_for_provider_creds(v, info)

        return v


class ProprietaryCredentialResponseList(ProprietaryCredentialResponse):
    """Proprietary Credential response list schema."""

    created_at: datetime
    num_of_endpoints: int
    provider_icon: str


class ProprietaryCredentialDetailedView(ProprietaryCredentialResponseList):
    """Proprietary Credential detailed view schema."""

    endpoints: list


class PaginatedCredentialResponse(PaginatedSuccessResponse):
    """Paginated Credential response schema."""

    credentials: List[Union[ProprietaryCredentialResponseList, CredentialDetails]]


def common_validator_for_provider_creds(v, info: ValidationInfo):
    """Common validator for provider credentials."""
    credential_type = info.data.get("type")
    if not credential_type:
        raise ValueError("Credential type must be specified")

    credential_data = PROPRIETARY_CREDENTIAL_DATA[credential_type.value]
    expected_fields = credential_data.get("credentials", [])

    # Check if invalid fields are provided
    expected_fields_names = [field["field"] for field in expected_fields]
    for key in v:
        if key not in expected_fields_names:
            raise ValueError(f"Unexpected field: {key}")

    for field in expected_fields:
        field_name = field["field"]

        # Check if the field is required
        if field["required"] and field_name not in v:
            raise ValueError(f"Missing required field: {field_name}")

        if field_name in v:
            value = v[field_name]
            field_type = field["type"]

            # Check if the field is a dependency
            field_dependencies = field.get("dependencies", [])
            for dependency in field_dependencies:
                if dependency not in v:
                    raise ValueError(f"Missing dependency: {dependency}")

            # Type validation
            if field_type in ["text", "password", "textarea"]:
                if not isinstance(value, str):
                    raise ValueError(f"Field {field_name} must be a string")
            elif field_type == "url":
                AnyHttpUrl(value)
            # TODO: Add more type validations here

    return v


# Cloud Providers
class CloudProvidersSchema(BaseModel):
    """Schema for cloud providers.

    Attributes:
        id: Unique identifier for the cloud provider
        name: Display name of the cloud provider
        description: Detailed description of the cloud provider
        logo_url: URL to the provider's logo image
        schema_definition: JSON schema defining the configuration options for this provider
    """

    model_config = ConfigDict(extra="allow")

    id: Union[str, uuid.UUID] = Field(..., description="Unique identifier for the cloud provider")
    name: str = Field(..., description="Display name of the cloud provider")
    description: str = Field(..., description="Detailed description of the cloud provider")
    logo_url: str = Field(..., description="URL to the provider's logo image")
    schema_definition: Union[str, Dict[str, Any]] = Field(
        ..., description="JSON schema defining the configuration options for this provider"
    )

    @field_validator("schema_definition")
    @classmethod
    def validate_schema_definition(cls, v: Union[str, Dict[str, Any]]) -> str:
        """Validates the schema_definition field, ensuring it's in the correct format.

        If a dictionary is provided, it's converted to a JSON string.
        If a string is provided, it's validated as valid JSON.

        Args:
            v: The schema definition value to validate

        Returns:
            A JSON string representing the schema definition

        Raises:
            ValueError: If the provided value is not valid JSON
        """
        if isinstance(v, dict):
            return json.dumps(v)
        elif isinstance(v, str):
            try:
                # Validate string is proper JSON by trying to parse it
                json.loads(v)
                return v
            except json.JSONDecodeError:
                raise ValueError("schema_definition must be valid JSON")
        else:
            raise ValueError("schema_definition must be a JSON string or a dictionary")

    @model_validator(mode="after")
    def validate_schema(self) -> "CloudProvidersSchema":
        """Validates the entire model after all fields have been processed.

        This can be used for cross-field validation or additional schema validation.

        Returns:
            The validated model
        """
        # Example: Ensure the schema is valid by checking if it can be parsed as JSON
        try:
            if isinstance(self.schema_definition, str):
                schema_dict = json.loads(self.schema_definition)
                # Add any additional schema validation logic here
                # For example, check if required fields exist
                if "type" not in schema_dict:
                    raise ValueError("Schema must specify a 'type' field")
        except Exception as e:
            raise ValueError(f"Invalid schema_definition: {str(e)}")
        return self

    def get_schema_as_dict(self) -> Dict[str, Any]:
        """Helper method to get the schema definition as a Python dictionary.

        Returns:
            The schema definition as a dictionary
        """
        if isinstance(self.schema_definition, str):
            return json.loads(self.schema_definition)
        return self.schema_definition


class CloudProvidersListResponse(SuccessResponse):
    """Response to list the cloud providers."""

    providers: list[CloudProvidersSchema]


class CloudProvidersCreateRequest(BaseModel):
    """Request to create a new cloud provider."""

    provider_id: str  # TODO: Probably we need to use UUID, test and replace
    credential_values: dict[str, str]  # JSON Structure
    credential_name: str


class CloudCredentialSchema(BaseModel):
    """Schema for cloud credential.

    Attributes:
        id: Unique identifier for the credential
        provider_id: ID of the provider this credential is for
        provider_name: Display name of the provider
        created_at: When the credential was created
        credential_summary: Summary of credential values with sensitive information masked
    """

    id: str = Field(..., description="Unique identifier for the credential")
    provider_id: str = Field(..., description="ID of the provider this credential is for")
    provider_name: str = Field(..., description="Display name of the provider")
    icon: str = Field(..., description="Icon URL for the provider")
    provider_description: str = Field(..., description="Description of the provider")
    created_at: datetime = Field(..., description="When the credential was created")
    credential_name: str = Field(..., description="Name of the credential")
    credential_summary: Dict[str, Any] = Field(
        ..., description="Summary of credential values with sensitive information masked"
    )


class CloudCredentialResponse(SuccessResponse):
    """Response containing cloud credentials."""

    credentials: list[CloudCredentialSchema]


class CloudProviderRegionsResponse(SuccessResponse):
    """Response model for cloud provider regions.

    Attributes:
        provider_id: Unique identifier of the cloud provider
        provider_name: Name of the cloud provider
        regions: List of regions supported by the provider
        code: HTTP status code
        message: Status message
    """

    provider_id: str = Field(..., description="Unique identifier of the cloud provider")
    regions: List[Dict[str, Any]] = Field(..., description="List of regions supported by the provider")
