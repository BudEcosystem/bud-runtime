from datetime import datetime
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from budmicroframe.commons.logging import get_logger
from fastapi import status
from fastapi.exceptions import HTTPException
from sqlalchemy import and_, func, select

from ..commons.base_crud import BaseDataManager
from .models import WorkerInfo as WorkerInfoModel
from .schemas import DeploymentStatusEnum


logger = get_logger(__name__)


class WorkerInfoDataManager(BaseDataManager):
    """Worker info data manager class responsible for operations over worker_info database table."""

    async def add_worker_info(self, workers_info: List[WorkerInfoModel]) -> List[WorkerInfoModel]:
        """Create a new worker info in the database."""
        return await self.add_all(workers_info)

    async def retrieve_workers_by_fields(self, fields: Dict, missing_ok: bool = False) -> Optional[WorkerInfoModel]:
        """Retrieve worker info by fields."""
        await self.validate_fields(WorkerInfoModel, fields)

        stmt = select(WorkerInfoModel).filter_by(**fields)
        db_worker_info = await self.get_one_or_none(stmt)

        if not missing_ok and db_worker_info is None:
            logger.info("Worker info not found in database")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker info not found")

        return db_worker_info if db_worker_info else None

    async def get_all_workers(
        self,
        filters: Optional[Dict] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
        order_by: Optional[List] = None,
        search: bool = False,
    ) -> Tuple[List[WorkerInfoModel], int]:
        """List all workers from the database."""
        filters = filters or {}
        order_by = order_by or []

        utilization_filters = []
        logger.info(f"filters: {filters}")
        if filters.get("utilization_min"):
            utilization_min = filters.pop("utilization_min")
            utilization_filters.append(WorkerInfoModel.utilization >= utilization_min)
        if filters.get("utilization_max"):
            utilization_max = filters.pop("utilization_max")
            utilization_filters.append(WorkerInfoModel.utilization <= utilization_max)

        await self.validate_fields(WorkerInfoModel, filters)

        # Generate statements according to search or filters
        if search:
            search_conditions = await self.generate_search_stmt(WorkerInfoModel, filters)
            stmt = select(WorkerInfoModel).filter(and_(*search_conditions, *utilization_filters))
            count_stmt = (
                select(func.count())
                .select_from(WorkerInfoModel)
                .filter(and_(*search_conditions, *utilization_filters))
            )
        else:
            stmt = select(WorkerInfoModel).filter_by(**filters)
            if utilization_filters:
                stmt = stmt.filter(and_(*utilization_filters))
            count_stmt = select(func.count()).select_from(WorkerInfoModel).filter_by(**filters)
            if utilization_filters:
                count_stmt = count_stmt.filter(and_(*utilization_filters))

        # Calculate count before applying limit and offset
        count = await self.execute_scalar_stmt(count_stmt)

        # Apply limit and offset
        if offset is not None or limit is not None:
            stmt = stmt.limit(limit).offset(offset)

        # Apply sorting
        if order_by:
            sort_conditions = await self.generate_sorting_stmt(WorkerInfoModel, order_by)
            stmt = stmt.order_by(*sort_conditions)

        result = await self.get_all(stmt)

        return result, count  # type: ignore

    async def delete_worker_info(self, workers_info: List[WorkerInfoModel]) -> None:
        """Delete a worker info in the database."""
        await self.delete_all(workers_info)

    async def delete_worker_info_by_id(self, worker_id: UUID) -> None:
        """Delete a worker info in the database by worker id."""
        stmt = select(WorkerInfoModel).filter_by(id=worker_id)
        db_worker_info = await self.get_one_or_none(stmt)
        if db_worker_info is None:
            logger.info("Worker info not found in database")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker info not found")
        await self.delete_one(db_worker_info)

    async def update_worker_info(self, worker_info: WorkerInfoModel) -> None:
        """Update a worker info in the database."""
        return await self.update_one(worker_info)

    async def get_active_deployments(self) -> List[Tuple[UUID, str]]:
        """Get distinct active deployments from worker_info table.

        Returns deployments where deployment_status is not FAILED.

        Returns:
            List of (cluster_id, deployment_name) tuples for active deployments.
        """
        stmt = (
            select(
                WorkerInfoModel.cluster_id,
                WorkerInfoModel.deployment_name,
            )
            .where(WorkerInfoModel.deployment_status != DeploymentStatusEnum.FAILED.value)
            .distinct()
        )

        result = await self.get_all(stmt, scalar=False)
        return [(row.cluster_id, row.deployment_name) for row in result]

    async def get_failed_deployments_due_for_retry(self, cutoff_time: datetime) -> List[Tuple[UUID, str]]:
        """Get FAILED deployments not updated since cutoff_time.

        Returns deployments that have been in FAILED status for longer than
        the retry threshold, allowing them to be retried.

        Args:
            cutoff_time: Only return deployments not updated since this time.

        Returns:
            List of (cluster_id, deployment_name) tuples for failed deployments due for retry.
        """
        stmt = (
            select(
                WorkerInfoModel.cluster_id,
                WorkerInfoModel.deployment_name,
            )
            .where(
                and_(
                    WorkerInfoModel.deployment_status == DeploymentStatusEnum.FAILED.value,
                    WorkerInfoModel.last_updated_datetime < cutoff_time,
                )
            )
            .distinct()
        )

        result = await self.get_all(stmt, scalar=False)
        return [(row.cluster_id, row.deployment_name) for row in result]
