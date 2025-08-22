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

"""API routes for evaluation dataset metadata."""

from __future__ import annotations

from typing import Annotated, Any

from budmicroframe.commons import logging
from fastapi import APIRouter, HTTPException, Query

from .manifest_schemas import Dataset, TraitDefinition
from .repository import get_eval_dataset_repository


logger = logging.get_logger(__name__)

router = APIRouter(prefix="/eval-datasets", tags=["eval-datasets"])


@router.get("/datasets", response_model=list[Dataset])
async def list_datasets(
    traits: Annotated[list[str] | None, Query(description="Filter by traits")] = None,
    source: Annotated[str | None, Query(description="Filter by source")] = None,
) -> list[Dataset]:
    """List all available evaluation datasets."""
    try:
        repo = get_eval_dataset_repository()
        return await repo.list_datasets(traits=traits, source=source)
    except Exception as e:
        logger.error(f"Failed to list datasets: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve datasets") from e


@router.get("/datasets/{dataset_id}", response_model=Dataset)
async def get_dataset(dataset_id: str) -> Dataset:
    """Get a specific dataset by ID."""
    try:
        repo = get_eval_dataset_repository()
        dataset = await repo.get_dataset(dataset_id)
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")
        return dataset
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get dataset {dataset_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve dataset") from e


@router.get("/datasets/search", response_model=list[Dataset])
async def search_datasets(q: str = Query(..., description="Search query")) -> list[Dataset]:
    """Search datasets by name or description."""
    try:
        repo = get_eval_dataset_repository()
        return await repo.search_datasets(q)
    except Exception as e:
        logger.error(f"Failed to search datasets: {e}")
        raise HTTPException(status_code=500, detail="Failed to search datasets") from e


@router.get("/traits", response_model=list[TraitDefinition])
async def list_traits() -> list[TraitDefinition]:
    """List all available evaluation traits."""
    try:
        repo = get_eval_dataset_repository()
        return await repo.list_traits()
    except Exception as e:
        logger.error(f"Failed to list traits: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve traits") from e


@router.get("/traits/{trait_name}", response_model=TraitDefinition)
async def get_trait(trait_name: str) -> TraitDefinition:
    """Get a specific trait by name."""
    try:
        repo = get_eval_dataset_repository()
        trait = await repo.get_trait(trait_name)
        if not trait:
            raise HTTPException(status_code=404, detail="Trait not found")
        return trait
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get trait {trait_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve trait") from e


@router.get("/traits/{trait_name}/datasets", response_model=list[Dataset])
async def get_datasets_by_trait(trait_name: str) -> list[Dataset]:
    """Get all datasets that evaluate a specific trait."""
    try:
        repo = get_eval_dataset_repository()
        return await repo.get_datasets_by_trait(trait_name)
    except Exception as e:
        logger.error(f"Failed to get datasets for trait {trait_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve datasets") from e


@router.get("/sources", response_model=list[str])
async def get_dataset_sources() -> list[str]:
    """Get all available dataset sources."""
    try:
        repo = get_eval_dataset_repository()
        return await repo.get_dataset_sources()
    except Exception as e:
        logger.error(f"Failed to get dataset sources: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve sources") from e


@router.get("/sources/{source}/datasets", response_model=list[Dataset])
async def get_datasets_by_source(source: str) -> list[Dataset]:
    """Get all datasets from a specific source."""
    try:
        repo = get_eval_dataset_repository()
        return await repo.get_datasets_by_source(source)
    except Exception as e:
        logger.error(f"Failed to get datasets for source {source}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve datasets") from e


@router.post("/sync")
async def sync_datasets(force: bool = Query(False, description="Force sync even if versions match")) -> dict[str, Any]:
    """Manually trigger dataset synchronization from manifest."""
    try:
        from budeval.commons.config import app_settings

        from .sync_service import get_sync_service

        sync_service = get_sync_service()

        # Fetch manifest
        manifest = await sync_service.fetch_manifest(app_settings.eval_manifest_url)

        # Get current version
        with sync_service.db.get_session() as db:
            current_version = sync_service.get_current_version(db)

        # Sync datasets
        sync_results = await sync_service.sync_datasets(manifest, current_version, force_sync=force)

        # Record sync results
        with sync_service.db.get_session() as db:
            sync_service.record_sync_results(
                db,
                manifest.version_info.current_version,
                "completed",
                {
                    "synced_datasets": sync_results["synced_datasets"],
                    "failed_datasets": sync_results["failed_datasets"],
                    "total_datasets": sync_results.get("total_datasets", 0),
                    "source": "cloud" if not app_settings.eval_sync_local_mode else "local",
                },
            )

        return {
            "message": f"Sync completed: {len(sync_results['synced_datasets'])} datasets synced",
            "version": manifest.version_info.current_version,
            "sync_results": sync_results,
        }
    except Exception as e:
        logger.error(f"Failed to sync datasets: {e}")
        raise HTTPException(status_code=500, detail="Failed to sync datasets") from e


@router.get("/sync/status")
async def get_sync_status() -> dict[str, Any]:
    """Get the current synchronization status and history."""
    try:
        from sqlalchemy import select

        from .models import EvalSyncState
        from .sync_service import get_sync_service

        sync_service = get_sync_service()

        with sync_service.db.get_session() as session:
            # Get latest sync state
            stmt = select(EvalSyncState).order_by(EvalSyncState.created_at.desc()).limit(1)
            latest_sync = session.execute(stmt).scalar_one_or_none()

            # Get sync history (last 10)
            history_stmt = select(EvalSyncState).order_by(EvalSyncState.created_at.desc()).limit(10)
            sync_history = session.execute(history_stmt).scalars().all()

            return {
                "latest_sync": {
                    "version": latest_sync.manifest_version if latest_sync else None,
                    "status": latest_sync.sync_status if latest_sync else None,
                    "timestamp": latest_sync.sync_timestamp if latest_sync else None,
                    "metadata": latest_sync.sync_metadata if latest_sync else None,
                }
                if latest_sync
                else None,
                "history": [
                    {
                        "version": sync.manifest_version,
                        "status": sync.sync_status,
                        "timestamp": sync.sync_timestamp,
                        "metadata": sync.sync_metadata,
                    }
                    for sync in sync_history
                ],
            }
    except Exception as e:
        logger.error(f"Failed to get sync status: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve sync status") from e


@router.post("/sync/local")
async def sync_local_manifest() -> dict[str, Any]:
    """Sync from local manifest file (for development/testing)."""
    try:
        from budeval.commons.config import app_settings

        from .sync_service import get_sync_service

        # Temporarily enable local mode for this operation
        original_local_mode = app_settings.eval_sync_local_mode
        app_settings.eval_sync_local_mode = True

        try:
            sync_service = get_sync_service()

            # Use a dummy URL since we're in local mode
            manifest = await sync_service.fetch_manifest("local_manifest.json")

            # Get current version
            with sync_service.db.get_session() as db:
                current_version = sync_service.get_current_version(db)

            # Force sync for local development
            sync_results = await sync_service.sync_datasets(manifest, current_version, force_sync=True)

            # Record sync results
            with sync_service.db.get_session() as db:
                sync_service.record_sync_results(
                    db,
                    manifest.version_info.current_version,
                    "completed",
                    {
                        "synced_datasets": sync_results["synced_datasets"],
                        "failed_datasets": sync_results["failed_datasets"],
                        "total_datasets": sync_results.get("total_datasets", 0),
                        "source": "local",
                    },
                )

            return {
                "message": f"Local sync completed: {len(sync_results['synced_datasets'])} datasets synced",
                "version": manifest.version_info.current_version,
                "sync_results": sync_results,
            }
        finally:
            # Restore original local mode setting
            app_settings.eval_sync_local_mode = original_local_mode

    except Exception as e:
        logger.error(f"Failed to sync local manifest: {e}")
        raise HTTPException(status_code=500, detail="Failed to sync local manifest") from e
