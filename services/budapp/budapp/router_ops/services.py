from typing import Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException, status

from budapp.commons import logging
from budapp.commons.constants import ProjectStatusEnum
from budapp.commons.db_utils import SessionMixin
from budapp.commons.schemas import Tag
from budapp.endpoint_ops.crud import EndpointDataManager
from budapp.project_ops.crud import ProjectDataManager
from budapp.project_ops.models import Project

from .crud import RouterDataManager, RouterEndpointDataManager
from .models import Router, RouterEndpoint
from .schemas import RouterEndpoints, RouterRequest, RouterResponse


logger = logging.get_logger(__name__)


class RouterService(SessionMixin):
    async def _check_duplicate_router(self, router: dict) -> bool:
        db_router = await RouterDataManager(self.session).retrieve_by_fields(
            {"name": router["name"], "project_id": router["project_id"]}, missing_ok=True
        )
        return db_router is not None

    async def create_router(self, current_user_id: UUID, request: RouterRequest) -> RouterResponse:
        # Validate project id
        await ProjectDataManager(self.session).retrieve_project_by_fields(
            {"id": request.project_id, "status": ProjectStatusEnum.ACTIVE}
        )

        if await self._check_duplicate_router({"name": request.name, "project_id": request.project_id}):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Router already exists with the same name",
            )

        if request.endpoints:
            # Build set of all endpoint IDs (primary + fallback) in one pass
            endpoint_ids = {
                ep_id
                for endpoint in request.endpoints
                for ep_id in ([endpoint.endpoint_id] + (endpoint.fallback_endpoint_ids or []))
            }

            missing_endpoints = await EndpointDataManager(self.session).get_missing_endpoints(list(endpoint_ids))

            if missing_endpoints:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Endpoint(s) {', '.join(str(ep) for ep in missing_endpoints)} do not exist",
                )

        router_data = request.model_dump()
        router_data["routing_strategy"] = router_data["routing_strategy"] or []
        router_data["tags"] = router_data["tags"] or []
        router_endpoints_data = router_data.pop("endpoints") or []

        router = Router(**router_data)
        db_router = await RouterDataManager(self.session).create_router(router)

        router_endpoints = []
        for endpoint_data in router_endpoints_data:
            endpoint_data["router_id"] = db_router.id
            endpoint_data["endpoint_id"] = str(endpoint_data["endpoint_id"])
            if endpoint_data.get("fallback_endpoint_ids", None):
                endpoint_data["fallback_endpoint_ids"] = [str(_id) for _id in endpoint_data["fallback_endpoint_ids"]]
            router_endpoint = RouterEndpoint(**endpoint_data)
            router_endpoints.append(router_endpoint)

        db_router_endpoints = await RouterEndpointDataManager(self.session).create_router_endpoints(router_endpoints)
        logger.info(f"Router inserted to database: {db_router.id}")

        router_response = RouterResponse(
            id=db_router.id,
            project_id=db_router.project_id,
            name=db_router.name,
            description=db_router.description,
            tags=[Tag(**tag) for tag in db_router.tags] if db_router.tags else [],
            routing_strategy=db_router.routing_strategy,
            endpoints=[
                RouterEndpoints(
                    endpoint_id=endpoint.endpoint_id,
                    fallback_endpoint_ids=endpoint.fallback_endpoint_ids,
                    tpm=endpoint.tpm,
                    rpm=endpoint.rpm,
                    weight=endpoint.weight,
                    cool_down_period=endpoint.cool_down_period,
                )
                for endpoint in db_router_endpoints
            ],
        )
        return router_response

    async def get_routers(
        self,
        project_id: UUID,
        offset: int = 0,
        limit: int = 10,
        filters: Optional[Dict] = None,
        order_by: Optional[List[str]] = None,
        search: bool = False,
    ) -> List[RouterResponse]:
        # Validate project_id
        await ProjectDataManager(self.session).retrieve_by_fields(Project, {"id": project_id})

        filters = filters or {}
        order_by = order_by or []
        db_routers, count = await RouterDataManager(self.session).get_all_routers(
            project_id, offset, limit, filters, order_by, search
        )

        result = []
        for router in db_routers:
            result.append(
                RouterResponse(
                    id=router.id,
                    project_id=router.project_id,
                    name=router.name,
                    description=router.description,
                    tags=router.tags,
                    routing_strategy=router.routing_strategy,
                    endpoints=[
                        RouterEndpoints(
                            endpoint_id=endpoint.endpoint_id,
                            fallback_endpoint_ids=endpoint.fallback_endpoint_ids,
                            tpm=endpoint.tpm,
                            rpm=endpoint.rpm,
                            weight=endpoint.weight,
                            cool_down_period=endpoint.cool_down_period,
                        )
                        for endpoint in router.endpoints
                    ],
                )
            )

        return result, count

    async def update_router(self, router_id: UUID, request: RouterRequest, current_user_id: UUID) -> Router:
        """Update a router and its endpoints."""
        db_router = await RouterDataManager(self.session).retrieve_by_fields({"id": router_id})

        router_data = request.model_dump()
        router_data["routing_strategy"] = router_data["routing_strategy"] or []
        router_endpoints_data = router_data.pop("endpoints") or []

        if router_data.get("name", None):
            # Check duplicate router exists with same name
            db_router_by_name = await RouterDataManager(self.session).retrieve_by_fields(
                {"name": router_data["name"], "project_id": router_data.get("project_id", db_router.project_id)},
                missing_ok=True,
            )

            # Raise error if router already exists with same name
            if db_router_by_name and db_router_by_name.id != router_id:
                error_msg = "Update failed : Router already exists with the same name"
                logger.error(error_msg)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error_msg,
                )

        if request.endpoints:
            # Build set of all endpoint IDs (primary + fallback) in one pass
            endpoint_ids = {
                ep_id
                for endpoint in request.endpoints
                for ep_id in ([endpoint.endpoint_id] + (endpoint.fallback_endpoint_ids or []))
            }

            missing_endpoints = await EndpointDataManager(self.session).get_missing_endpoints(list(endpoint_ids))

            if missing_endpoints:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Endpoint(s) {', '.join(str(ep) for ep in missing_endpoints)} do not exist",
                )

        db_router = await RouterDataManager(self.session).update_router_by_fields(db_router, router_data)

        # 2. Handle endpoint updates
        router_endpoint_manager = RouterEndpointDataManager(self.session)

        # Get existing endpoint IDs for this router
        existing_endpoints = {ep.endpoint_id: ep for ep in db_router.endpoints}
        update_endpoint_ids = {ep["endpoint_id"] for ep in router_endpoints_data}

        # Delete endpoints that are no longer present
        endpoints_to_delete = set(existing_endpoints.keys()) - update_endpoint_ids
        for endpoint_id in endpoints_to_delete:
            await router_endpoint_manager.delete_router_endpoint(existing_endpoints[endpoint_id])

        # Update or create endpoints
        for endpoint_data in router_endpoints_data:
            endpoint_data["endpoint_id"] = str(endpoint_data["endpoint_id"])
            if endpoint_data.get("fallback_endpoint_ids", None):
                endpoint_data["fallback_endpoint_ids"] = [str(_id) for _id in endpoint_data["fallback_endpoint_ids"]]
            if endpoint_data["endpoint_id"] in existing_endpoints:
                # Update existing endpoint
                existing_endpoint = existing_endpoints[endpoint_data["endpoint_id"]]
                await router_endpoint_manager.update_router_endpoint_by_fields(existing_endpoint, endpoint_data)
            else:
                # Create new endpoint
                endpoint_data["router_id"] = db_router.id
                new_endpoint = RouterEndpoint(**endpoint_data)
                await router_endpoint_manager.create_router_endpoint(new_endpoint)

        updated_db_router = await RouterDataManager(self.session).retrieve_by_fields({"id": db_router.id})

        return RouterResponse(
            id=updated_db_router.id,
            project_id=updated_db_router.project_id,
            name=updated_db_router.name,
            description=updated_db_router.description,
            tags=updated_db_router.tags,
            routing_strategy=updated_db_router.routing_strategy,
            endpoints=[
                RouterEndpoints(
                    endpoint_id=endpoint.endpoint_id,
                    fallback_endpoint_ids=endpoint.fallback_endpoint_ids,
                    tpm=endpoint.tpm,
                    rpm=endpoint.rpm,
                    weight=endpoint.weight,
                    cool_down_period=endpoint.cool_down_period,
                )
                for endpoint in updated_db_router.endpoints
            ],
        )

    async def delete_router(self, router_id: UUID, user_id: UUID) -> None:
        """Delete the router from the database."""
        # Retrieve the router from the database
        db_router = await RouterDataManager(self.session).retrieve_by_fields({"id": router_id})
        db_router_endpoints = await RouterEndpointDataManager(self.session).retrieve_all_by_fields(
            {"router_id": router_id}
        )

        router_endpoint_manager = RouterEndpointDataManager(self.session)
        for router_endpoint in db_router_endpoints:
            await router_endpoint_manager.delete_router_endpoint(router_endpoint)

        await RouterDataManager(self.session).delete_router(db_router)

        return
