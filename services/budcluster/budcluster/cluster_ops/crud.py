from typing import Dict, List, Optional, Tuple
from uuid import UUID

from budmicroframe.commons.logging import get_logger
from fastapi import status
from fastapi.exceptions import HTTPException
from sqlalchemy import and_, func, select

from ..commons.base_crud import BaseDataManager
from .models import Cluster as ClusterModel
from .models import ClusterNodeInfo as ClusterNodeInfoModel
from .schemas import ClusterNodeInfo


logger = get_logger(__name__)


class ClusterDataManager(BaseDataManager):
    """Cluster data manager class responsible for operations over database."""

    async def create_cluster(self, cluster: ClusterModel) -> ClusterModel:
        """Create a new cluster in the database."""
        return await self.add_one(cluster)

    async def retrieve_cluster_by_fields(self, fields: Dict, missing_ok: bool = False) -> Optional[ClusterModel]:
        """Retrieve cluster by fields."""
        await self.validate_fields(ClusterModel, fields)

        stmt = select(ClusterModel).filter_by(**fields)
        db_cluster = await self.get_one_or_none(stmt)

        if not missing_ok and db_cluster is None:
            logger.info("Cluster not found in database")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cluster not found")

        return db_cluster if db_cluster else None

    async def get_all_clusters(
        self,
        offset: int,
        limit: int,
        filters: Optional[Dict] = None,
        order_by: Optional[List] = None,
        search: bool = False,
    ) -> Tuple[List[ClusterModel], int]:
        """List all clusters from the database."""
        filters = filters or {}
        order_by = order_by or []

        await self.validate_fields(ClusterModel, filters)

        # Generate statements according to search or filters
        if search:
            search_conditions = await self.generate_search_stmt(ClusterModel, filters)
            stmt = select(ClusterModel).filter(and_(*search_conditions))
            count_stmt = select(func.count()).select_from(ClusterModel).filter(and_(*search_conditions))
        else:
            stmt = select(ClusterModel).filter_by(**filters)
            count_stmt = select(func.count()).select_from(ClusterModel).filter_by(**filters)

        # Calculate count before applying limit and offset
        count = await self.execute_scalar_stmt(count_stmt)

        # Apply limit and offset
        stmt = stmt.limit(limit).offset(offset)

        # Apply sorting
        if order_by:
            sort_conditions = await self.generate_sorting_stmt(ClusterModel, order_by)
            stmt = stmt.order_by(*sort_conditions)

        result = await self.get_all(stmt)

        return result, count  # type: ignore

    async def update_cluster_by_fields(self, db_cluster: ClusterModel, fields: Dict) -> ClusterModel:
        """Update a cluster in the database."""
        await self.validate_fields(ClusterModel, fields)

        for field, value in fields.items():
            setattr(db_cluster, field, value)

        return await self.update_one(db_cluster)

    async def delete_cluster(self, id: Optional[UUID] = None, db_cluster: Optional[ClusterModel] = None) -> None:
        """Delete a cluster in the database."""
        if not id and not db_cluster:
            raise ValueError("Either id or db_cluster must be provided")

        if not db_cluster:
            db_cluster = await self.retrieve_cluster_by_fields({"id": id})

        if db_cluster:
            await self.delete_one(db_cluster)


class ClusterNodeInfoDataManager(BaseDataManager):
    """Cluster node info data manager class responsible for operations over database."""

    async def create_cluster_node_info(self, nodes: list[ClusterNodeInfo]) -> list[ClusterNodeInfoModel]:
        """Create a new cluster node info in the database."""
        models = []
        for node_info in nodes:
            models.append(ClusterNodeInfoModel(**node_info.model_dump()))
        return await self.add_all(models)

    async def get_cluster_node_info_by_cluster_id(self, cluster_id: UUID) -> List[ClusterNodeInfoModel]:
        """Get cluster node info by cluster id."""
        stmt = select(ClusterNodeInfoModel).filter_by(cluster_id=cluster_id)
        return await self.get_all(stmt)

    async def delete_cluster_node_info_by_cluster_id(self, cluster_id: UUID) -> None:
        """Delete cluster node info by cluster id."""
        stmt = select(ClusterNodeInfoModel).filter_by(cluster_id=cluster_id)
        models = await self.get_all(stmt)
        if models:
            await self.delete_all(models)

    async def update_cluster_node_info(self, nodes: list[ClusterNodeInfoModel]) -> list[ClusterNodeInfoModel]:
        """Update cluster node info."""
        updated_nodes = []
        for node in nodes:
            updated_nodes.append(await self.update_one(node))
        return updated_nodes

    async def delete_cluster_node_info(self, nodes: list[ClusterNodeInfoModel]) -> None:
        """Delete cluster node info."""
        await self.delete_all(nodes)
