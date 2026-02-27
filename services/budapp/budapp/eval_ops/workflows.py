#  -----------------------------------------------------------------------------
#  Copyright (c) 2025 Bud Ecosystem Inc.
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

"""This file contains the workflows for evaluation data synchronization."""

import asyncio
import uuid
from datetime import timedelta
from typing import Any, Dict, Optional

import dapr.ext.workflow as wf
from budmicroframe.commons.schemas import WorkflowStep
from budmicroframe.shared.dapr_workflow import DaprWorkflow
from sqlalchemy.orm import Session

from ..commons import logging


logger = logging.get_logger(__name__)

dapr_workflow = DaprWorkflow()

retry_policy = wf.RetryPolicy(
    first_retry_interval=timedelta(seconds=1),
    max_number_of_attempts=3,
    backoff_coefficient=2,
    max_retry_interval=timedelta(seconds=10),
    retry_timeout=timedelta(seconds=100),
)


class EvalDataSyncWorkflows:
    """Workflows for synchronizing evaluation datasets and traits from cloud repository."""

    def __init__(self) -> None:
        """Initialize the EvalDataSyncWorkflows class."""
        self.dapr_workflow = DaprWorkflow()

    @dapr_workflow.register_activity  # type: ignore
    @staticmethod
    def check_and_sync_eval_data(ctx: wf.WorkflowActivityContext, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Check cloud repository for updated evaluation data and sync if needed.

        This activity will:
        1. Check a cloud URL for the latest version of eval datasets and traits
        2. Compare with current local version
        3. Download and migrate if a newer version is available

        Args:
            ctx: Workflow activity context
            kwargs: Dictionary containing sync parameters

        Returns:
            Dictionary with sync results
        """
        from ..commons.config import app_settings
        from ..commons.database import engine
        from .sync_service import EvalDataSyncService

        repository_url = kwargs.get("repository_url", app_settings.eval_manifest_url)
        force_sync = kwargs.get("force_sync", False)

        try:
            if app_settings.eval_sync_local_mode:
                logger.info("Running in LOCAL MODE - using local manifest and dataset files")
            else:
                logger.info("Checking cloud repository for evaluation data updates: %s", repository_url)

            sync_service = EvalDataSyncService()

            # Fetch manifest (async operation)
            manifest = asyncio.run(sync_service.fetch_manifest(repository_url))
            logger.info(f"Fetched manifest version: {manifest.version_info.current_version}")

            # Get current version from database and record sync start if needed
            with Session(engine) as db:
                current_version = sync_service.get_current_version(db)

                result = {
                    "checked": True,
                    "repository_url": repository_url,
                    "current_version": current_version or "none",
                    "latest_version": manifest.version_info.current_version,
                    "updated": False,
                    "message": "No updates available",
                    "manifest": {
                        "total_datasets": len(manifest.get_all_datasets()),
                        "total_size_mb": manifest.get_total_size_mb(),
                        "sources": list(manifest.datasets.keys()),
                    },
                }

                logger.info(f"Current version: {current_version}")
                logger.info(f"Manifest version: {manifest.version_info.current_version}")

                # Check if sync is needed — record start within same session
                if force_sync or current_version != manifest.version_info.current_version:
                    sync_service.record_sync_results(
                        db,
                        manifest.version_info.current_version,
                        "in_progress",
                        {"source": "local" if app_settings.eval_sync_local_mode else "cloud"},
                    )

            # Perform sync outside the session (long-running async operations)
            if force_sync or current_version != manifest.version_info.current_version:
                logger.info(
                    "Sync required: current=%s, latest=%s", current_version, manifest.version_info.current_version
                )

                # Run migrations if needed
                if manifest.requires_migration(current_version):
                    asyncio.run(sync_service.run_migrations(manifest, current_version))

                # Sync dataset metadata
                sync_results = asyncio.run(sync_service.sync_datasets(manifest, current_version, force_sync))

                # Record sync completion
                with Session(engine) as db:
                    sync_service.record_sync_results(
                        db,
                        manifest.version_info.current_version,
                        "completed",
                        {
                            "synced_datasets": sync_results["synced_datasets"],
                            "failed_datasets": sync_results["failed_datasets"],
                            "total_datasets": sync_results.get("total_datasets", 0),
                            "source": "local" if app_settings.eval_sync_local_mode else "cloud",
                        },
                    )

                result.update(
                    {
                        "updated": True,
                        "message": f"Synced {len(sync_results['synced_datasets'])} datasets",
                        "sync_results": sync_results,
                    }
                )

            logger.info("Evaluation data sync check completed: %s", result)
            return result

        except Exception as e:
            logger.exception("Failed to check/sync evaluation data: %s", e)

            # Record sync failure if we have a manifest version
            try:
                if "manifest" in locals() and manifest:
                    with Session(engine) as db:
                        sync_service.record_sync_results(
                            db,
                            manifest.version_info.current_version,
                            "failed",
                            {"error": str(e), "source": "local" if app_settings.eval_sync_local_mode else "cloud"},
                        )
            except Exception as record_error:
                logger.error(f"Failed to record sync failure: {record_error}")

            return {"checked": False, "error": str(e), "message": "Failed to sync evaluation data"}

    @dapr_workflow.register_workflow  # type: ignore
    @staticmethod
    def run_eval_data_sync(ctx: wf.DaprWorkflowContext, payload: Dict[str, Any]):
        """Run the evaluation data synchronization workflow.

        Args:
            ctx: Dapr workflow context
            payload: Dictionary containing workflow parameters
        """
        logger.info("Evaluation data sync workflow started")
        logger.info("Is workflow replaying: %s", ctx.is_replaying)

        workflow_name = "eval_data_sync_workflow"
        workflow_id = ctx.instance_id

        from ..commons.config import app_settings

        repository_url = payload.get("repository_url", app_settings.eval_manifest_url)
        force_sync = payload.get("force_sync", False)

        result = yield ctx.call_activity(
            EvalDataSyncWorkflows.check_and_sync_eval_data,
            input={"repository_url": repository_url, "force_sync": force_sync},
            retry_policy=retry_policy,
        )

        logger.info("Evaluation data sync workflow completed with result: %s", result)
        logger.info("Workflow %s with id %s completed", workflow_name, workflow_id)

        return result

    def __call__(
        self, repository_url: Optional[str] = None, force_sync: bool = False, workflow_id: Optional[str] = None
    ):
        """Trigger the evaluation data sync workflow.

        Args:
            repository_url: URL of the cloud repository to check
            force_sync: Force synchronization even if versions match
            workflow_id: Optional workflow ID

        Returns:
            Workflow scheduling response
        """
        from ..commons.config import app_settings

        logger.info("Scheduling evaluation data sync workflow")
        logger.info("Repository URL: %s", repository_url or app_settings.eval_manifest_url)
        logger.info("Force sync: %s", force_sync)
        logger.info("Workflow ID: %s", workflow_id)

        response = dapr_workflow.schedule_workflow(
            workflow_name="run_eval_data_sync",
            workflow_input={
                "repository_url": repository_url or app_settings.eval_manifest_url,
                "force_sync": force_sync,
            },
            workflow_id=str(workflow_id or uuid.uuid4()),
            workflow_steps=[
                WorkflowStep(
                    id="eval_data_sync",
                    title="Evaluation Data Synchronization",
                    description="Check and sync evaluation datasets and traits from cloud repository",
                )
            ],
        )

        return response
