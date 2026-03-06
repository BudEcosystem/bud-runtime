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

"""The crud package, containing essential business logic, services, and routing configurations for the workflow ops."""

from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, func, select

from budapp.commons import logging
from budapp.commons.db_utils import DataManagerUtils

from .models import Workflow as WorkflowModel
from .models import WorkflowStep as WorkflowStepModel


logger = logging.get_logger(__name__)


class WorkflowDataManager(DataManagerUtils):
    """Data manager for the Workflow model."""

    async def get_all_workflows(
        self,
        offset: int,
        limit: int,
        filters: Dict = {},  # endpoint count need to consider in future
        order_by: List = [],
        search: bool = False,
    ) -> Tuple[List[WorkflowModel], int]:
        """List all workflows from the database."""
        await self.validate_fields(WorkflowModel, filters)

        # Generate statements based on search or filters
        if search:
            search_conditions = await self.generate_search_stmt(WorkflowModel, filters)
            stmt = select(WorkflowModel).filter(and_(*search_conditions))
            count_stmt = select(func.count()).select_from(WorkflowModel).filter(and_(*search_conditions))
        else:
            stmt = select(WorkflowModel).filter_by(**filters)
            count_stmt = select(func.count()).select_from(WorkflowModel).filter_by(**filters)

        # Calculate count before applying limit and offset
        count = self.execute_scalar(count_stmt)

        # Apply limit and offset
        stmt = stmt.limit(limit).offset(offset)

        # Apply sorting
        if order_by:
            sort_conditions = await self.generate_sorting_stmt(WorkflowModel, order_by)
            stmt = stmt.order_by(*sort_conditions)

        result = self.scalars_all(stmt)

        return result, count

    def find_workflow_by_deployment_id(
        self,
        deployment_id: str,
        workflow_type: str,
    ) -> Optional[WorkflowModel]:
        """Find the most recent workflow whose progress JSONB contains the given deployment_id."""
        stmt = (
            select(WorkflowModel)
            .filter(
                WorkflowModel.workflow_type == workflow_type,
                WorkflowModel.progress.op("->>")(  # type: ignore[union-attr]
                    "deployment_id"
                )
                == deployment_id,
            )
            .order_by(WorkflowModel.created_at.desc())
            .limit(1)
        )
        return self.scalar_one_or_none(stmt)

    def find_workflows_by_deployment_ids(
        self,
        deployment_ids: List[str],
        workflow_type: str,
    ) -> Dict[str, UUID]:
        """Find the most recent workflow for each deployment_id.

        Returns a dict mapping deployment_id -> workflow.id.

        Uses a SQL window function (ROW_NUMBER) to select only the most
        recent record per deployment_id in the database, avoiding
        over-fetching and Python-side deduplication.
        """
        if not deployment_ids:
            return {}

        dep_id_expr = WorkflowModel.progress.op("->>")(  # type: ignore[union-attr]
            "deployment_id"
        )
        subquery = (
            select(
                dep_id_expr.label("deployment_id"),
                WorkflowModel.id,
                func.row_number()
                .over(
                    partition_by=dep_id_expr,
                    order_by=WorkflowModel.created_at.desc(),
                )
                .label("rn"),
            )
            .filter(
                WorkflowModel.workflow_type == workflow_type,
                dep_id_expr.in_(deployment_ids),
            )
            .subquery()
        )

        stmt = select(subquery.c.deployment_id, subquery.c.id).where(subquery.c.rn == 1)
        rows = self.session.execute(stmt).all()

        return {str(row.deployment_id): row.id for row in rows}


class WorkflowStepDataManager(DataManagerUtils):
    """Data manager for the WorkflowStep model."""

    async def get_all_workflow_steps(self, filters: dict) -> List[WorkflowStepModel]:
        """Get all workflow steps from the database."""
        stmt = select(WorkflowStepModel).filter_by(**filters).order_by(WorkflowStepModel.step_number)
        return self.scalars_all(stmt)

    async def get_all_workflow_steps_by_data(self, data_key: str, workflow_id: str) -> List[WorkflowStepModel]:
        """Get all workflow steps from the database by data key and workflow id."""
        stmt = (
            select(WorkflowStepModel)
            .filter(
                WorkflowStepModel.data.op("->>")(data_key).isnot(None), WorkflowStepModel.workflow_id == workflow_id
            )
            .order_by(WorkflowStepModel.step_number)
        )
        return self.scalars_all(stmt)
