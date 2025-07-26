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

"""Common schemas for the Bud Metrics service."""

from typing import Any, Dict, Optional, Set, Union
from uuid import UUID

from budmicroframe.commons.schemas import ResponseBase
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from ..commons.constants import EntryStatus


class CloudEventMetaData(BaseModel):
    """Metadata model for cloud events."""

    cloudevent_id: Optional[str] = Field(None, alias="cloudevent.id")
    cloudevent_type: Optional[str] = Field(None, alias="cloudevent.type")


class CloudEventEntry(BaseModel):
    """Entry model for cloud events."""

    event: dict[str, Any]
    entryId: str
    metadata: CloudEventMetaData
    content_type: str = Field(alias="contentType")


class BulkCloudEventBase(BaseModel):
    """Base class for handling bulk HTTP requests with cloud event compatible validation."""

    model_config = ConfigDict(protected_namespaces=((),))

    entries: list[CloudEventEntry]
    id: UUID
    metadata: dict
    pubsubname: str
    topic: str
    type: str


class EntryStatusResponse(BaseModel):
    """Status model for bulk cloud events."""

    entryId: UUID
    status: EntryStatus


class BulkCloudEventResponse(ResponseBase):
    """Response model for bulk cloud events."""

    object: str | None = None  # Override the default value

    statuses: list[EntryStatusResponse] = Field(..., default_factory=list)

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
        details = self.model_dump(
            mode="json",
            include=include,
            exclude=exclude,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
        )
        status_code = self.code

        # Exclude object from the response
        details.pop("object", None)

        return JSONResponse(content=details, status_code=status_code)
