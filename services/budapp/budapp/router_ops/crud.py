from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import JSONB

from budapp.commons import logging
from budapp.commons.constants import EndpointStatusEnum
from budapp.commons.db_utils import DataManagerUtils
from budapp.endpoint_ops.models import Endpoint

from .models import Router, RouterEndpoint


logger = logging.get_logger(__name__)


class RouterDataManager(DataManagerUtils):
    """Data manager for the Router model."""

    async def create_router(self, router: Router) -> Router:
        """Create a new router in the database."""
        return await self.insert_one(router)

    async def retrieve_by_fields(self, fields: Dict, missing_ok: bool = False) -> Optional[Router]:
        """Retrieve router by fields."""
        await self.validate_fields(Router, fields)

        stmt = select(Router).filter_by(**fields)
        db_router = self.scalar_one_or_none(stmt)

        if not missing_ok and db_router is None:
            logger.info("Router not found in database")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Router not found")

        return db_router if db_router else None

    async def get_all_routers(
        self,
        project_id: UUID,
        offset: int = 0,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[List[Tuple[str, str]]] = None,
        search: bool = False,
    ) -> List[Router]:
        """Get all routers from the database."""
        filters = filters or {}
        order_by = order_by or []

        # Tags are not filterable
        # Also remove from filters dict
        explicit_conditions = []
        json_filters = {"tags": filters.pop("tags", [])}

        # Validate the remaining filters
        await self.validate_fields(Router, filters)

        if json_filters["tags"]:
            # Either TagA or TagB exist in tag field
            tag_conditions = or_(
                *[Router.tags.cast(JSONB).contains([{"name": tag_name}]) for tag_name in json_filters["tags"]]
            )
            explicit_conditions.append(tag_conditions)

        # Generate statements according to search or filters
        if search:
            search_conditions = await self.generate_search_stmt(Router, filters)
            stmt = (
                select(Router)
                .filter(or_(*search_conditions, *explicit_conditions))
                .filter(and_(Endpoint.status != EndpointStatusEnum.DELETED, Router.project_id == project_id))
                .outerjoin(RouterEndpoint, RouterEndpoint.router_id == Router.id)
                .group_by(Router.id)
            )
            count_stmt = (
                select(func.count())
                .select_from(Router)
                .filter(or_(*search_conditions, *explicit_conditions))
                .filter(Router.project_id == project_id)
            )
        else:
            stmt = (
                select(Router)
                .filter_by(**filters)
                .filter(and_(Endpoint.status != EndpointStatusEnum.DELETED, Router.project_id == project_id))
                .where(and_(*explicit_conditions))
                .outerjoin(RouterEndpoint, RouterEndpoint.router_id == Router.id)
                .group_by(Router.id)
            )
            count_stmt = (
                select(func.count())
                .select_from(Router)
                .filter_by(**filters)
                .filter(Router.project_id == project_id)
                .where(and_(*explicit_conditions))
            )

        # Calculate count before applying limit and offset
        count = self.execute_scalar(count_stmt)

        # Apply limit and offset
        stmt = stmt.limit(limit).offset(offset)

        # Apply sorting
        if order_by:
            sort_conditions = await self.generate_sorting_stmt(Router, order_by)
            stmt = stmt.order_by(*sort_conditions)

        result = self.scalars_all(stmt)

        return result, count

    async def update_router_by_fields(self, db_router: Router, fields: Dict) -> Router:
        """Update a router in the database."""
        await self.validate_fields(Router, fields)

        for field, value in fields.items():
            setattr(db_router, field, value)

        return self.update_one(db_router)

    async def delete_router(self, db_router: Router) -> None:
        """Delete a router from the database."""
        await self.delete_one(db_router)
        return


class RouterEndpointDataManager(DataManagerUtils):
    """Data manager for the RouterEndpoint model."""

    async def create_router_endpoint(self, router_endpoint: RouterEndpoint) -> RouterEndpoint:
        """Create a new router endpoint in the database."""
        return await self.insert_one(router_endpoint)

    async def create_router_endpoints(self, router_endpoints: List[RouterEndpoint]) -> List[RouterEndpoint]:
        """Create multiple router endpoints in the database."""
        return await self.insert_all(router_endpoints)

    async def retrieve_all_by_fields(self, fields: Dict, missing_ok: bool = False) -> List[RouterEndpoint]:
        """Retrieve all router endpoints by fields."""
        await self.validate_fields(RouterEndpoint, fields)

        stmt = select(RouterEndpoint).filter_by(**fields)
        db_router_endpoints = self.scalars_all(stmt)

        if not missing_ok and not db_router_endpoints:
            logger.info("Router endpoints not found in database")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Router endpoints not found")

        return db_router_endpoints or []

    async def update_router_endpoint_by_fields(
        self, db_router_endpoint: RouterEndpoint, fields: Dict
    ) -> RouterEndpoint:
        """Update a router endpoint in the database."""
        await self.validate_fields(RouterEndpoint, fields)

        for field, value in fields.items():
            setattr(db_router_endpoint, field, value)

        return self.update_one(db_router_endpoint)

    async def delete_router_endpoint(self, db_router_endpoint: RouterEndpoint) -> None:
        """Delete a router endpoint from the database."""
        await self.delete_one(db_router_endpoint)
        return
