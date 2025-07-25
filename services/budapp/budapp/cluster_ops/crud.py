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

"""The crud package, containing essential business logic, services, and routing configurations for the cluster ops."""

from typing import Any, Dict, List, Tuple
from uuid import UUID

from sqlalchemy import and_, asc, case, desc, distinct, func, select

from budapp.cluster_ops.models import Cluster
from budapp.commons import logging
from budapp.commons.db_utils import DataManagerUtils

from ..commons.constants import ClusterStatusEnum, EndpointStatusEnum
from ..endpoint_ops.models import Endpoint


logger = logging.get_logger(__name__)


class ClusterDataManager(DataManagerUtils):
    """Data manager for the Cluster model."""

    async def get_all_clusters(
        self,
        offset: int,
        limit: int,
        filters: Dict = {},  # endpoint count need to consider in future
        order_by: List = [],
        search: bool = False,
    ) -> Tuple[List[Cluster], int]:
        """List all clusters from the database."""
        await self.validate_fields(Cluster, filters)

        # Subquery to count endpoints per cluster
        endpoint_count_subquery = (
            select(
                Endpoint.cluster_id,
                func.count(Endpoint.id.distinct()).label("endpoint_count"),
            )
            .where(Endpoint.status != EndpointStatusEnum.DELETED)
            .group_by(Endpoint.cluster_id)
            .alias("endpoint_count_subquery")
        )

        # Generate statements based on search or filters
        if search:
            search_conditions = await self.generate_search_stmt(Cluster, filters)
            stmt = (
                select(
                    Cluster,
                    func.coalesce(endpoint_count_subquery.c.endpoint_count, 0).label("endpoint_count"),
                )
                .filter(and_(*search_conditions))
                .select_from(Cluster)
                .join(
                    endpoint_count_subquery,
                    Cluster.id == endpoint_count_subquery.c.cluster_id,
                    isouter=True,
                )
            )
            count_stmt = select(func.count()).select_from(Cluster).filter(and_(*search_conditions))
        else:
            stmt = (
                select(
                    Cluster,
                    func.coalesce(endpoint_count_subquery.c.endpoint_count, 0).label("endpoint_count"),
                )
                .filter_by(**filters)
                .select_from(Cluster)
                .join(
                    endpoint_count_subquery,
                    Cluster.id == endpoint_count_subquery.c.cluster_id,
                    isouter=True,
                )
            )
            count_stmt = select(func.count()).select_from(Cluster).filter_by(**filters)

        # Exclude deleted clusters
        stmt = stmt.filter(Cluster.status != ClusterStatusEnum.DELETED)
        count_stmt = count_stmt.filter(Cluster.status != ClusterStatusEnum.DELETED)

        # Calculate count before applying limit and offset
        count = self.execute_scalar(count_stmt)

        # Apply limit and offset
        stmt = stmt.limit(limit).offset(offset)

        # Apply sorting
        if order_by:
            sort_conditions = await self.generate_sorting_stmt(Cluster, order_by)
            stmt = stmt.order_by(*sort_conditions)

        result = self.execute_all(stmt)

        return result, count

    async def get_available_clusters_by_cluster_ids(self, cluster_ids: List[UUID]) -> Tuple[List[Cluster], int]:
        """Get active clusters by cluster ids."""
        stmt = select(Cluster).filter(
            Cluster.cluster_id.in_(cluster_ids), Cluster.status == ClusterStatusEnum.AVAILABLE
        )
        count_stmt = (
            select(func.count())
            .select_from(Cluster)
            .filter(Cluster.cluster_id.in_(cluster_ids), Cluster.status == ClusterStatusEnum.AVAILABLE)
        )

        count = self.execute_scalar(count_stmt)
        result = self.scalars_all(stmt)

        return result, count

    async def get_inactive_clusters(self) -> Tuple[List[Cluster], int]:
        """Retrieve a list of inactive clusters and count."""
        stmt = select(Cluster).filter(
            Cluster.status.in_([ClusterStatusEnum.NOT_AVAILABLE, ClusterStatusEnum.ERROR, ClusterStatusEnum.DELETING])
        )
        count_stmt = (
            select(func.count())
            .select_from(Cluster)
            .filter(
                Cluster.status.in_(
                    [ClusterStatusEnum.NOT_AVAILABLE, ClusterStatusEnum.ERROR, ClusterStatusEnum.DELETING]
                )
            )
        )

        count = self.execute_scalar(count_stmt)
        result = self.scalars_all(stmt)

        return result, count

    async def get_all_clusters_in_project(
        self, project_id: UUID, offset: int, limit: int, filters: Dict[str, Any], order_by: List[str], search: bool
    ) -> Tuple[List[Cluster], int, int, int]:
        """Get all clusters in a project."""
        await self.validate_fields(Cluster, filters)

        # Generate statements based on search or filters
        base_conditions = [
            Endpoint.project_id == project_id,
            Cluster.status != ClusterStatusEnum.DELETED,
            Endpoint.status != EndpointStatusEnum.DELETED,
        ]
        # Subquery to get distinct nodes
        unique_nodes_subq = (
            select(Endpoint.cluster_id, func.jsonb_array_elements_text(Endpoint.node_list).label("node"))
            .distinct()  # Ensure unique (cluster_id, node) pairs
            .subquery()
        )
        if search:
            search_conditions = await self.generate_search_stmt(Cluster, filters)

            stmt = (
                select(
                    Cluster,
                    func.count(Endpoint.id).label("endpoint_count"),
                    # func.coalesce(func.sum(Endpoint.number_of_nodes), 0).label("total_nodes"),
                    func.coalesce(func.count(func.distinct(unique_nodes_subq.c.node)), 0).label(
                        "total_nodes"
                    ),  # Count unique nodes
                    func.coalesce(func.sum(Endpoint.total_replicas), 0).label("total_replicas"),
                )
                .join(Endpoint, Endpoint.cluster_id == Cluster.id)
                .filter(*base_conditions)
                .filter(and_(*search_conditions))
                .group_by(Cluster.id)
            )
            count_stmt = (
                select(func.count(distinct(Cluster.id)))
                .select_from(Cluster)
                .join(Endpoint, Endpoint.cluster_id == Cluster.id)
                .filter(*base_conditions)
                .filter(and_(*search_conditions))
            )
        else:
            filter_conditions = [getattr(Cluster, field) == value for field, value in filters.items()]
            stmt = (
                select(
                    Cluster,
                    func.count(Endpoint.id).label("endpoint_count"),
                    # func.coalesce(func.sum(Endpoint.number_of_nodes), 0).label("total_nodes"),
                    func.coalesce(func.count(func.distinct(unique_nodes_subq.c.node)), 0).label(
                        "total_nodes"
                    ),  # Count unique nodes
                    func.coalesce(func.sum(Endpoint.total_replicas), 0).label("total_replicas"),
                )
                .join(Endpoint, Endpoint.cluster_id == Cluster.id)
                .filter(*base_conditions)
                .filter(*filter_conditions)
                .group_by(Cluster.id)
            )
            count_stmt = (
                select(func.count(distinct(Cluster.id)))
                .select_from(Cluster)
                .join(Endpoint, Endpoint.cluster_id == Cluster.id)
                .filter(*base_conditions)
                .filter(*filter_conditions)
            )

        # Calculate count before applying limit and offset
        count = self.execute_scalar(count_stmt)

        # Apply limit and offset
        stmt = stmt.limit(limit).offset(offset)

        # Apply sorting
        if order_by:
            sort_conditions = await self.generate_sorting_stmt(Cluster, order_by)

            # Handle endpoint_count sorting
            for field, direction in order_by:
                if field == "endpoint_count":
                    sort_func = asc if direction == "asc" else desc
                    stmt = stmt.order_by(sort_func("endpoint_count"))
                elif field == "node_count":
                    sort_func = asc if direction == "asc" else desc
                    stmt = stmt.order_by(sort_func("total_nodes"))
                elif field == "worker_count":
                    sort_func = asc if direction == "asc" else desc
                    stmt = stmt.order_by(sort_func("total_replicas"))
                elif field == "hardware_type":
                    # Sorting by hardware type
                    hardware_type_expr = (
                        case((Cluster.cpu_count > 0, 1), else_=0)
                        + case((Cluster.gpu_count > 0, 1), else_=0)
                        + case((Cluster.hpu_count > 0, 1), else_=0)
                    ).label("hardware_type")
                    sort_func = asc if direction == "asc" else desc
                    stmt = stmt.order_by(sort_func(hardware_type_expr))

            stmt = stmt.order_by(*sort_conditions)

        result = self.session.execute(stmt)

        return result, count


class ModelClusterRecommendedDataManager(DataManagerUtils):
    """Data manager for the ModelClusterRecommended model."""

    pass
