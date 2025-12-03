from datetime import datetime
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from budmicroframe.commons.logging import get_logger
from fastapi import status
from fastapi.exceptions import HTTPException
from sqlalchemy import and_, func, select, update

from ..commons.base_crud import BaseDataManager
from .models import Deployment as DeploymentModel
from .models import WorkerInfo as WorkerInfoModel
from .schemas import DeploymentRecordCreate, DeploymentRecordUpdate, DeploymentStatusEnum


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


class DeploymentDataManager(BaseDataManager):
    """Deployment data manager class responsible for operations over deployment database table."""

    async def create_deployment(self, data: DeploymentRecordCreate) -> DeploymentModel:
        """Create a new deployment record in the database."""
        deployment = DeploymentModel(**data.model_dump())
        return await self.add_one(deployment)

    async def get_deployment_by_id(self, deployment_id: UUID, missing_ok: bool = False) -> Optional[DeploymentModel]:
        """Retrieve deployment by ID."""
        stmt = select(DeploymentModel).filter_by(id=deployment_id)
        db_deployment = await self.get_one_or_none(stmt)

        if not missing_ok and db_deployment is None:
            logger.info("Deployment not found in database")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found")

        return db_deployment

    async def get_deployment_by_namespace(self, namespace: str, missing_ok: bool = False) -> Optional[DeploymentModel]:
        """Retrieve deployment by namespace."""
        stmt = select(DeploymentModel).filter_by(namespace=namespace)
        db_deployment = await self.get_one_or_none(stmt)

        if not missing_ok and db_deployment is None:
            logger.info(f"Deployment not found for namespace: {namespace}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found")

        return db_deployment

    async def get_deployment_by_fields(self, fields: Dict, missing_ok: bool = False) -> Optional[DeploymentModel]:
        """Retrieve deployment by arbitrary fields."""
        await self.validate_fields(DeploymentModel, fields)
        stmt = select(DeploymentModel).filter_by(**fields)
        db_deployment = await self.get_one_or_none(stmt)

        if not missing_ok and db_deployment is None:
            logger.info("Deployment not found in database")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found")

        return db_deployment

    async def update_deployment(
        self, deployment: DeploymentModel, update_data: DeploymentRecordUpdate
    ) -> DeploymentModel:
        """Update a deployment record."""
        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(deployment, field, value)
        return await self.update_one(deployment)

    async def delete_deployment(self, deployment: DeploymentModel) -> None:
        """Delete a deployment record."""
        await self.delete_one(deployment)

    async def delete_deployment_by_namespace(self, namespace: str) -> None:
        """Delete a deployment by namespace."""
        deployment = await self.get_deployment_by_namespace(namespace)
        await self.delete_one(deployment)

    async def get_active_deployments(self) -> List[Tuple[UUID, str]]:
        """Get deployments that should be monitored.

        Returns all deployments except those in terminal ERROR state.
        This includes READY, PENDING, INGRESS_FAILED, ENDPOINTS_FAILED, and FAILED.

        Returns:
            List of (cluster_id, namespace) tuples for deployments to monitor.
        """
        stmt = select(
            DeploymentModel.cluster_id,
            DeploymentModel.namespace,
        ).where(DeploymentModel.status != DeploymentStatusEnum.ERROR.value)

        result = await self.get_all(stmt, scalar=False)
        return [(row.cluster_id, row.namespace) for row in result]

    async def get_deployments_to_mark_error(self, cutoff_time: datetime) -> List[Tuple[UUID, str]]:
        """Get FAILED deployments that should be marked as ERROR.

        Returns deployments that have been in FAILED status for longer than
        the threshold (e.g., 24 hours), indicating they need manual intervention.

        Args:
            cutoff_time: Only return deployments with last_status_check before this time.

        Returns:
            List of (cluster_id, namespace) tuples for deployments to mark as ERROR.
        """
        stmt = select(
            DeploymentModel.cluster_id,
            DeploymentModel.namespace,
        ).where(
            and_(
                DeploymentModel.status == DeploymentStatusEnum.FAILED.value,
                DeploymentModel.last_status_check < cutoff_time,
            )
        )

        result = await self.get_all(stmt, scalar=False)
        return [(row.cluster_id, row.namespace) for row in result]

    async def get_all_deployments(
        self,
        filters: Optional[Dict] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> Tuple[List[DeploymentModel], int]:
        """List all deployments with optional filtering and pagination."""
        filters = filters or {}
        await self.validate_fields(DeploymentModel, filters)

        stmt = select(DeploymentModel).filter_by(**filters)
        count_stmt = select(func.count()).select_from(DeploymentModel).filter_by(**filters)

        count = await self.execute_scalar_stmt(count_stmt)

        if offset is not None or limit is not None:
            stmt = stmt.limit(limit).offset(offset)

        result = await self.get_all(stmt)
        return result, count  # type: ignore

    async def link_workers_to_deployment(self, deployment_id: UUID, worker_ids: List[UUID]) -> None:
        """Link existing workers to a deployment by updating their deployment_id."""
        if not worker_ids:
            return

        stmt = update(WorkerInfoModel).where(WorkerInfoModel.id.in_(worker_ids)).values(deployment_id=deployment_id)
        await self.execute_commit(stmt)
