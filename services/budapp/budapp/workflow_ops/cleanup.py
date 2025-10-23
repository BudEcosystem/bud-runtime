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

"""The workflow cleanup scheduler. Contains business logic for purging old completed workflows from Dapr state store."""

from datetime import UTC, datetime, timedelta
from typing import Dict, List
from uuid import UUID

import aiohttp

from ..commons import logging
from ..commons.config import app_settings
from ..commons.constants import WorkflowStatusEnum
from ..commons.database import SessionLocal
from .crud import WorkflowDataManager
from .models import Workflow


logger = logging.get_logger(__name__)


class WorkflowCleanupScheduler:
    """Schedule cleanup of old completed workflows from Dapr state store.

    This scheduler purges workflow state from Redis/Dapr to prevent unbounded
    storage growth. It only purges workflows that are in terminal states
    (COMPLETED, FAILED) and older than the configured retention period.
    """

    @staticmethod
    async def get_old_workflows(
        session,
        cutoff_date: datetime,
        batch_size: int = 100,
    ) -> List[Workflow]:
        """Get workflows older than cutoff date that are in terminal states.

        Args:
            session: Database session
            cutoff_date: Only return workflows updated before this date
            batch_size: Maximum number of workflows to return

        Returns:
            List[Workflow]: List of workflows eligible for purging
        """
        # Query workflows in COMPLETED or FAILED state
        # We need to check both statuses separately since filters doesn't support list values
        workflows_completed, count_completed = await WorkflowDataManager(session).get_all_workflows(
            offset=0,
            limit=batch_size,
            filters={"status": WorkflowStatusEnum.COMPLETED},
        )

        workflows_failed, count_failed = await WorkflowDataManager(session).get_all_workflows(
            offset=0,
            limit=batch_size,
            filters={"status": WorkflowStatusEnum.FAILED},
        )

        # Combine results
        all_workflows = workflows_completed + workflows_failed

        # Filter by updated_at to get only old workflows
        old_workflows = [w for w in all_workflows if w.updated_at and w.updated_at < cutoff_date]

        # Sort by updated_at and limit to batch_size
        old_workflows = sorted(old_workflows, key=lambda w: w.updated_at or datetime.min.replace(tzinfo=UTC))
        old_workflows = old_workflows[:batch_size]

        logger.debug(
            "Found %s workflows in terminal states (completed=%s, failed=%s), %s older than %s",
            count_completed + count_failed,
            count_completed,
            count_failed,
            len(old_workflows),
            cutoff_date,
        )

        return old_workflows

    @staticmethod
    async def purge_workflow_from_dapr(workflow_id: UUID) -> bool:
        """Purge a workflow from Dapr state store.

        This calls the Dapr workflow purge API to remove all workflow state
        including metadata, inbox, and history entries from Redis.

        Args:
            workflow_id: The workflow instance ID to purge

        Returns:
            bool: True if purge was successful, False otherwise
        """
        # Dapr workflow purge endpoint
        # Format: POST /v1.0/workflows/<workflowComponentName>/<instanceId>/purge
        purge_url = f"{app_settings.dapr_base_url}/v1.0/workflows/dapr/{workflow_id}/purge"

        try:
            async with aiohttp.ClientSession() as session:
                headers = {}
                if app_settings.dapr_api_token:
                    headers["dapr-api-token"] = app_settings.dapr_api_token

                async with session.post(purge_url, headers=headers) as response:
                    if response.status == 204:
                        # 204 No Content indicates successful purge
                        logger.debug("Successfully purged workflow %s from Dapr", workflow_id)
                        return True
                    elif response.status == 404:
                        # Workflow not found in Dapr - may have already been purged
                        logger.warning("Workflow %s not found in Dapr state store", workflow_id)
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(
                            "Failed to purge workflow %s: HTTP %s - %s",
                            workflow_id,
                            response.status,
                            error_text,
                        )
                        return False
        except aiohttp.ClientError as e:
            logger.error("Network error purging workflow %s: %s", workflow_id, e)
            return False
        except Exception as e:
            logger.exception("Unexpected error purging workflow %s: %s", workflow_id, e)
            return False

    async def cleanup_old_workflows(
        self,
        retention_days: int = 30,
        batch_size: int = 100,
        delete_from_db: bool = False,
    ) -> Dict[str, int]:
        """Clean up old completed workflows from Dapr state store.

        This method:
        1. Queries database for workflows in terminal states older than retention period
        2. Calls Dapr purge API for each workflow to remove state from Redis
        3. Optionally deletes workflow records from database

        Args:
            retention_days: Keep workflows for this many days after completion
            batch_size: Maximum number of workflows to process in one run
            delete_from_db: If True, also delete workflow records from database

        Returns:
            Dict with counts of processed, succeeded, and failed workflows
        """
        cutoff_date = datetime.now(UTC) - timedelta(days=retention_days)
        logger.info(
            "Starting workflow cleanup: retention_days=%s, cutoff_date=%s, batch_size=%s",
            retention_days,
            cutoff_date,
            batch_size,
        )

        result = {
            "processed": 0,
            "purged_from_dapr": 0,
            "failed_purge": 0,
            "deleted_from_db": 0,
        }

        with SessionLocal() as session:
            # Get old workflows eligible for cleanup
            workflows = await self.get_old_workflows(
                session=session,
                cutoff_date=cutoff_date,
                batch_size=batch_size,
            )

            if not workflows:
                logger.info("No workflows found for cleanup")
                return result

            logger.info("Found %s workflows to clean up", len(workflows))

            # Process each workflow
            for workflow in workflows:
                result["processed"] += 1

                try:
                    # Purge from Dapr state store
                    purge_success = await self.purge_workflow_from_dapr(workflow.id)

                    if purge_success:
                        result["purged_from_dapr"] += 1
                        logger.info(
                            "Purged workflow %s (type=%s, status=%s, updated=%s)",
                            workflow.id,
                            workflow.workflow_type,
                            workflow.status,
                            workflow.updated_at,
                        )

                        # Optionally delete from database
                        if delete_from_db:
                            try:
                                session.delete(workflow)
                                session.commit()
                                result["deleted_from_db"] += 1
                                logger.debug("Deleted workflow %s from database", workflow.id)
                            except Exception as e:
                                logger.error("Failed to delete workflow %s from database: %s", workflow.id, e)
                                session.rollback()
                    else:
                        result["failed_purge"] += 1

                except Exception as e:
                    logger.exception("Error processing workflow %s: %s", workflow.id, e)
                    result["failed_purge"] += 1

        logger.info(
            "Workflow cleanup completed: processed=%s, purged=%s, failed=%s, deleted_from_db=%s",
            result["processed"],
            result["purged_from_dapr"],
            result["failed_purge"],
            result["deleted_from_db"],
        )

        return result


if __name__ == "__main__":
    import asyncio

    # For manual testing
    scheduler = WorkflowCleanupScheduler()
    result = asyncio.run(scheduler.cleanup_old_workflows(retention_days=30, batch_size=100))
    print(f"Cleanup result: {result}")

    # python -m budapp.workflow_ops.cleanup
