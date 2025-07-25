from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, model_validator

from budapp.commons.schemas import PaginatedSuccessResponse, Tag


class RouterFilter(BaseModel):
    """Router filter schema."""

    name: Optional[str] = None
    project_id: Optional[UUID] = None


class RouterEndpoints(BaseModel):
    endpoint_id: UUID
    fallback_endpoint_ids: Optional[List[UUID]] = None
    tpm: Optional[float] = None
    rpm: Optional[float] = None
    weight: Optional[float] = None
    cool_down_period: Optional[int] = None

    @model_validator(mode="before")
    @classmethod
    def validate_fallback_endpoint_ids(cls, data):
        if (
            isinstance(data.get("fallback_endpoint_ids"), list)
            and data["endpoint_id"] in data["fallback_endpoint_ids"]
        ):
            raise ValueError("endpoint_id cannot be in fallback_endpoint_ids")
        return data


class RouterRequest(BaseModel):
    project_id: UUID
    name: str
    description: str
    tags: Optional[List[Tag]] = None
    routing_strategy: Optional[List[Dict[str, Any]]] = None
    endpoints: List[RouterEndpoints]


class RouterResponse(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    description: str
    tags: Optional[List[Tag]] = None
    routing_strategy: Optional[List[Dict[str, Any]]] = None
    endpoints: List[RouterEndpoints]


class PaginatedRouterResponse(PaginatedSuccessResponse):
    """Paginated Router response schema."""

    routers: List[RouterResponse]
