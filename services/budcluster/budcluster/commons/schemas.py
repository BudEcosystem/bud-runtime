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

import math
from typing import Any, Dict, List

from budmicroframe.commons.schemas import NotificationContent, NotificationRequest, ResponseBase, SuccessResponse
from pydantic import (
    BaseModel,
    StringConstraints,
    computed_field,
)
from typing_extensions import Annotated


lowercase_string = Annotated[str, StringConstraints(to_lower=True)]


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


class WorkflowResponse(ResponseBase):
    object: str = "workflow"
    workflow_id: str
    steps: List[Dict[str, Any]]
    eta: int


class NotificationActivityRequest(BaseModel):
    notification_request: NotificationRequest
    activity_event: str
    content: NotificationContent
    source_topic: str | list[str] | None  # Supports multi-topic notification (D-001)
    source: str | None
