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

"""Contains Pydantic schemas used for data validation and serialization within the microservices."""

import datetime
import math
import re
from http import HTTPStatus
from typing import Any, ClassVar, Dict, Generic, List, Optional, Set, Tuple, Type, TypeVar, Union
from uuid import UUID

from fastapi.responses import JSONResponse
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    computed_field,
    create_model,
    field_validator,
    model_validator,
)
from typing_extensions import Annotated


lowercase_string = Annotated[str, StringConstraints(to_lower=True)]

ContentType = TypeVar("ContentType")


def to_camel(string: str) -> str:
    """Convert snake_case to camelCase."""
    components = string.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


class CamelCaseModel(BaseModel):
    """Base model with camelCase field aliases."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


class CloudEventBase(BaseModel):
    """Base class for handling HTTP requests with cloud event compatible validation.

    Configures the model to forbid extra fields not defined in the model schema.

    Attributes:
        id (str): The id of the cloud event, excluded from serialization.
        specversion (str): The spec version of the cloud event, excluded from serialization.
        datacontenttype (str): The data content type of the cloud event, excluded from serialization.
        topic (str): The topic of the cloud event, excluded from serialization.
        pubsubname (str): The pubsub name of the cloud event, excluded from serialization.
        source (str): The source of the cloud event, excluded from serialization.
        data (dict): The data of the cloud event, excluded from serialization.
        traceid (str): The trace id of the cloud event, excluded from serialization.
        tracestate (str): The trace state of the cloud event, excluded from serialization.
        traceparent (str): The trace parent of the cloud event, excluded from serialization.
        type (str): The type of the cloud event
        time (str): The time of the cloud event
    """

    model_config = ConfigDict(extra="forbid")

    excluded_fields_in_api: ClassVar[Tuple[str, ...]] = (
        "specversion",
        "topic",
        "pubsubname",
        "source",
        "out_topic",
        "data",
        "traceid",
        "tracestate",
        "traceparent",
    )

    specversion: Optional[str] = None

    topic: Optional[str] = None
    pubsubname: Optional[str] = None
    source: Optional[str] = None
    source_topic: Optional[str] = None

    data: Optional[Dict[str, Any]] = None

    traceid: Optional[str] = None
    tracestate: Optional[str] = None
    traceparent: Optional[str] = None

    type: Optional[str] = None
    time: str = Field(default_factory=lambda: datetime.datetime.now(datetime.UTC).isoformat() + "Z")  # type: ignore
    debug: bool = Field(default=False)

    def is_pubsub(self) -> bool:
        """Check if the event is a PubSub event."""
        return self.topic is not None and self.pubsubname is not None

    @classmethod
    def create_pubsub_model(cls) -> Type[BaseModel]:
        """Create a model for PubSub with data field containing the data model.

        This method generates a new Pydantic model specifically for PubSub events. It includes all the fields
        from the CloudEventBase class as outer fields, and creates an inner model (DataModel) containing
        the fields specific to the inheriting class. The resulting model has a 'data' field that uses
        the inner model as its type.

        Returns:
            Type[BaseModel]: A new Pydantic model class for PubSub events, with a name in the format
            '{ClassName}PubSub'. This model includes all CloudEventBase fields and a 'data' field
            containing the custom fields of the inheriting class.
        """
        # Fields for the outer model (CloudEventBase fields)
        outer_fields = {
            field_name: (field_info.annotation, field_info)
            for field_name, field_info in cls.model_fields.items()
            if field_name in CloudEventBase.model_fields
        }

        # Fields for the inner model (fields specific to the inheriting class)
        inner_fields = {
            field_name: (field_info.annotation, field_info)
            for field_name, field_info in cls.model_fields.items()
            if field_name not in CloudEventBase.model_fields
        }

        # Create the inner model
        DataModel = create_model(f"{cls.__name__}Schema", **inner_fields)  # type: ignore

        # Add the data field with the inner model
        outer_fields["data"] = (DataModel, Field(...))
        return create_model(f"{cls.__name__}PubSub", **outer_fields)  # type: ignore

    @classmethod
    def create_api_model(cls) -> Type[BaseModel]:
        """Create a model for API requests.

        This method generates a new Pydantic model for API requests by excluding
        certain fields from the current class. The resulting model is suitable
        for validating and serializing API request data.

        Returns:
            Type[BaseModel]: A new Pydantic model class for API requests, with
            a name in the format '{ClassName}API'.
        """
        outer_fields = {}
        fields = {}
        for field_name, field_info in cls.model_fields.items():
            if field_name in CloudEventBase.model_fields and field_name not in cls.excluded_fields_in_api:
                outer_fields[field_name] = (field_info.annotation, field_info)
            elif field_name not in cls.excluded_fields_in_api:
                fields[field_name] = (field_info.annotation, field_info)

        fields.update(outer_fields)

        return create_model(f"{cls.__name__}Schema", **fields)  # type: ignore

    @model_validator(mode="before")
    @classmethod
    def root_validator(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and adjust the input data.

        If the `id` field and the `data` field is set, then the data field key-value pairs will be added to the instance.

        Args:
            data (dict): The input data to validate and adjust.

        Returns:
            dict: The validated and potentially adjusted data.
        """
        if all(data.get(key) is not None for key in ("topic", "pubsubname", "data")):
            data.update({k: v for k, v in data["data"].items() if k not in data})

        return data


class ResponseBase(BaseModel):
    """Base class for handling HTTP responses with customizable serialization.

    Configures the model to forbid extra fields not defined in the model schema.

    Attributes:
        object (str): The type of response object, converted to lowercase.
        code (int): The HTTP status code for the response, excluded from serialization.
    """

    model_config = ConfigDict(extra="forbid")

    # TODO: Add snake case validation
    object: lowercase_string
    code: int = Field(HTTPStatus.OK.value, exclude=True)

    @staticmethod
    def to_pascal_case(string: str, prefix: Optional[str] = None, suffix: Optional[str] = None) -> str:
        """Convert a string to Pascal case.

        Transform the input string to Pascal case, with optional prefix and suffix.

        Args:
            string (str): The string to convert.
            prefix (Optional[str]): Optional prefix to add before the string.
            suffix (Optional[str]): Optional suffix to add after the string.

        Returns:
            str: The Pascal case representation of the input string.
        """
        string = (prefix or "") + string + (suffix or "")
        return re.sub(r"([_\-])+", " ", string).title().replace(" ", "")

    def to_http_response(
        self,
        include: Union[Set[int], Set[str], Dict[int, Any], Dict[str, Any], None] = None,
        exclude: Union[Set[int], Set[str], Dict[int, Any], Dict[str, Any], None] = None,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
    ) -> JSONResponse:
        """Convert the model instance to an HTTP response.

        Serializes the model instance into a JSON response, with options to include or exclude specific fields
        and customize the response based on various parameters.

        Args:
            include (set[int] | set[str] | dict[int, Any] | dict[str, Any] | None): Fields to include in the response.
            exclude (set[int] | set[str] | dict[int, Any] | dict[str, Any] | None): Fields to exclude from the response.
            exclude_unset (bool): Whether to exclude unset fields from the response.
            exclude_defaults (bool): Whether to exclude default values from the response.
            exclude_none (bool): Whether to exclude fields with None values from the response.

        Returns:
            JSONResponse: The serialized JSON response with the appropriate status code.
        """
        if getattr(self, "object", "") == "error":
            details = self.model_dump(mode="json")
            status_code = details["code"]
        else:
            details = self.model_dump(
                include=include,
                exclude=exclude,
                exclude_unset=exclude_unset,
                exclude_defaults=exclude_defaults,
                exclude_none=exclude_none,
                mode="json",
            )
            status_code = self.code

        return JSONResponse(content=details, status_code=status_code)


class SingleResponse(BaseModel, Generic[ContentType]):
    """Single Response Schema."""

    success: bool = True
    result: Union[ContentType, list[ContentType]]
    message: Optional[str] = None


class SuccessResponse(ResponseBase):
    """Define a success response with optional message and parameters.

    Inherits from `ResponseBase` and specifies default values and validation for success responses.

    Attributes:
        object (str): The type of response object, defaulting to "info".
        message (Optional[str]): An optional message for the response.
    """

    object: str = "info"
    message: Optional[str]

    @model_validator(mode="before")
    @classmethod
    def root_validator(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and set default message for the response data.

        Ensure that the `message` field is set to a default value if not provided, based on the HTTP status code.

        Args:
            data (dict): The input data to validate and adjust.

        Returns:
            dict: The validated and potentially adjusted data.
        """
        # Handle case where data is already a model instance (e.g., during Union type validation)
        if not isinstance(data, dict):
            return data

        if data.get("code") is not None and data.get("message") is None:
            data["message"] = HTTPStatus(data["code"]).description

        return data


class PaginatedSuccessResponse(SuccessResponse):
    """Define a paginated success response with optional message and parameters.

    Inherits from `SuccessResponse` and specifies default values and validation for success responses.

    Attributes:
        page (int): The current page number.
        limit (int): The number of items per page.
        total_record (int): The total number of records.
    """

    page: int
    limit: int
    total_record: int = 0

    @computed_field
    @property
    def total_pages(self) -> int:
        """Calculate the total number of pages based on the total number of records and the limit.

        Args:
            self (PaginatedSuccessResponse): The paginated success response instance.

        Returns:
            int: The total number of pages.
        """
        if self.limit > 0:
            return math.ceil(self.total_record / self.limit) or 1
        else:
            return 1


class ErrorResponse(ResponseBase):
    """Define an error response with a code and type derived from the status code.

    Inherits from `ResponseBase` and specifies the default values and validation for error responses.

    Attributes:
        object (str): The type of response object, defaulting to "error".
        message (Optional[str]): An optional message for the response.
        type (Optional[str]): The type of the error.
        param (Optional[str]): An optional parameter for additional context.
        code (int): The HTTP status code for the error.
    """

    object: lowercase_string = "error"
    message: Optional[str]
    type: Optional[str] = "InternalServerError"
    param: Optional[str] = None
    code: int = HTTPStatus.INTERNAL_SERVER_ERROR.value

    @model_validator(mode="before")
    @classmethod
    def root_validator(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and set default values for the error response data.

        Set the `type` and `message` fields based on the HTTP status code if not provided.
        The `type` is derived from the status code's phrase and suffixed with "Error" if applicable.

        Args:
            data (dict): The input data to validate and adjust.

        Returns:
            dict: The validated and potentially adjusted data.
        """
        # Handle case where data is already a model instance (e.g., during Union type validation)
        if not isinstance(data, dict):
            return data

        # Use default code if not provided
        code = data.get("code", HTTPStatus.INTERNAL_SERVER_ERROR.value)
        data["code"] = code

        data["type"] = data.get("type") or cls.to_pascal_case(HTTPStatus(code).phrase, suffix="Error")
        data["message"] = data.get("message") or HTTPStatus(code).description

        return data


# Schemas related to Tag


class Tag(BaseModel):
    """Tag schema with name and color."""

    name: str = Field(..., min_length=1)
    color: str = Field(..., pattern="^#[0-9A-Fa-f]{6}$")

    @field_validator("color")
    def validate_hex_color(cls, v: str) -> str:
        """Validate that color is a valid hex color code."""
        if not re.match(r"^#[0-9A-Fa-f]{6}$", v):
            raise ValueError("Color must be a valid hex color code (e.g., #FF0000)")
        return v.upper()


# Schemas related to task


class Task(Tag):
    """Task schema with name and description."""

    pass


class BudNotificationMetadata(BaseModel):
    """Recommended cluster notification metadata."""

    workflow_id: str
    subscriber_ids: str
    name: str
