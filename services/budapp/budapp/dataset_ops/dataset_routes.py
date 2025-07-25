# budapp/cluster_ops/cluster_routes.py
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

"""The benchmark ops package, containing essential business logic, services, and routing configurations for the benchmark ops."""

from typing import List, Optional, Union

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from typing_extensions import Annotated

from budapp.commons import logging
from budapp.commons.dependencies import (
    get_current_active_user,
    get_session,
    parse_ordering_fields,
)
from budapp.commons.schemas import ErrorResponse
from budapp.user_ops.schemas import User

from .schemas import DatasetFilter, DatasetPaginatedResponse
from .services import DatasetService


logger = logging.get_logger(__name__)

dataset_router = APIRouter(prefix="/dataset", tags=["dataset"])


@dataset_router.get(
    "",
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
            "model": DatasetPaginatedResponse,
            "description": "Successfully list all datasets",
        },
    },
    description="List all datasets. Filter by fields are: name, tags",
)
async def list_all_datasets(
    _: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    filters: Annotated[DatasetFilter, Depends()],
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=0),
    order_by: Optional[List[str]] = Depends(parse_ordering_fields),  # noqa: B008
    search: bool = False,
) -> Union[DatasetPaginatedResponse, ErrorResponse]:
    """List all datasets."""
    # Calculate offset
    offset = (page - 1) * limit

    # Construct filters
    filters_dict = filters.model_dump(exclude_none=True, exclude_unset=True)

    try:
        db_datasets, count = await DatasetService(session).get_datasets(offset, limit, filters_dict, order_by, search)
    except Exception as e:
        logger.exception(f"Failed to get all datasets: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get all datasets"
        ).to_http_response()

    return DatasetPaginatedResponse(
        datasets=db_datasets,
        total_record=count,
        page=page,
        limit=limit,
        object="datasets.list",
        code=status.HTTP_200_OK,
        message="Successfully list all datasets",
    ).to_http_response()
