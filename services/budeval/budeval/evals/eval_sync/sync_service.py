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

"""Service for syncing evaluation dataset metadata from manifest."""

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import aiohttp
from budmicroframe.shared.psql_service import Database
from sqlalchemy import select
from sqlalchemy.orm import Session

from budeval.commons import logging
from budeval.commons.config import app_settings

from .manifest_schemas import Dataset, EvalDataManifest
from .models import EvalSyncState, ExpDataset, ExpDatasetVersion, ExpTrait, ExpTraitsDatasetPivot


logger = logging.get_logger(__name__)


class EvalDataSyncService:
    """Service for managing evaluation dataset metadata synchronization."""

    def __init__(self):
        """Initialize the sync service."""
        self.db = Database()
        self.db.connect()

    async def fetch_manifest(self, manifest_url: str) -> EvalDataManifest:
        """Fetch and parse the manifest from the cloud repository or local file.

        Args:
            manifest_url: URL of the manifest file or local file path in local mode

        Returns:
            Parsed manifest object
        """
        # Check if local mode is enabled
        if app_settings.eval_sync_local_mode:
            # In local mode, treat manifest_url as a filename in the data directory
            current_file_path = os.path.dirname(os.path.abspath(__file__))
            parent_dir = os.path.dirname(current_file_path)
            local_manifest_path = os.path.join(parent_dir, "..", "..", "data", "eval_manifest.json")

            logger.info(f"Local mode enabled, loading manifest from: {local_manifest_path}")

            try:
                with open(local_manifest_path, "r") as f:
                    manifest_data = json.load(f)
                    return EvalDataManifest(**manifest_data)
            except FileNotFoundError as e:
                raise FileNotFoundError(f"Local manifest file not found: {local_manifest_path}") from e
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in local manifest file: {local_manifest_path}") from e

        # Cloud mode - fetch from URL
        async with aiohttp.ClientSession() as session, session.get(manifest_url) as response:
            response.raise_for_status()
            manifest_data = await response.json()
            return EvalDataManifest(**manifest_data)

    def get_current_version(self, db: Session) -> Optional[str]:
        """Get the current version from the database.

        Args:
            db: Database session

        Returns:
            Current version string or None if not set
        """
        # Query for the most recent successful sync
        stmt = (
            select(EvalSyncState)
            .where(EvalSyncState.sync_status == "completed")
            .order_by(EvalSyncState.created_at.desc())
            .limit(1)
        )

        result = db.execute(stmt)
        sync_state = result.scalar_one_or_none()

        if sync_state:
            logger.info(f"Current sync version: {sync_state.manifest_version}")
            return sync_state.manifest_version

        logger.info("No previous sync found")
        return None

    def import_dataset(self, dataset: Dataset, db: Session):
        """Import dataset metadata into the database.

        Args:
            dataset: Dataset metadata from manifest
            db: Database session
        """
        logger.info(f"Importing dataset metadata for {dataset.id}")
        logger.debug(f"Dataset details: name={dataset.name}, version={dataset.version}, traits={dataset.traits}")

        # 1. Get or create ExpDataset
        existing_dataset = db.query(ExpDataset).filter_by(name=dataset.name).first()

        # Prepare dataset fields from manifest
        dataset_fields = {
            "name": dataset.name,  # Use dataset name
            "description": dataset.description,
            "meta_links": {"manifest_id": dataset.id},  # Store the manifest ID
            "estimated_input_tokens": None,
            "estimated_output_tokens": None,
            "language": None,
            "domains": None,
            "concepts": None,
            "humans_vs_llm_qualifications": None,
            "task_type": None,
            "modalities": ["text"],  # Default to text, can be extended based on metadata
            "sample_questions_answers": {"sample_count": dataset.sample_count} if dataset.sample_count else None,
            "advantages_disadvantages": None,
        }

        # Extract creator info and links from original_data if available
        if hasattr(dataset, "original_data") and dataset.original_data:
            original_data = (
                dataset.original_data if isinstance(dataset.original_data, dict) else dataset.original_data.__dict__
            )

            # Update meta_links with GitHub, paper, website links and creator info
            # Always set github, paper, and website to empty string if not present
            dataset_fields["meta_links"]["github"] = original_data.get("github_link", "")
            dataset_fields["meta_links"]["paper"] = original_data.get("paper_link", "")
            dataset_fields["meta_links"]["website"] = original_data.get("official_website_link", "")

            if original_data.get("creator_info"):
                creator_info = original_data["creator_info"]
                # Convert CreatorInfo Pydantic model to dict for JSON serialization
                if hasattr(creator_info, "model_dump"):
                    dataset_fields["meta_links"]["creator"] = creator_info.model_dump()
                elif hasattr(creator_info, "__dict__"):
                    dataset_fields["meta_links"]["creator"] = creator_info.__dict__
                else:
                    dataset_fields["meta_links"]["creator"] = creator_info
            if original_data.get("create_date"):
                dataset_fields["meta_links"]["create_date"] = original_data["create_date"]
            if original_data.get("update_date"):
                dataset_fields["meta_links"]["update_date"] = original_data["update_date"]
        else:
            # If no original_data, still ensure empty strings for URL fields
            dataset_fields["meta_links"]["github"] = ""
            dataset_fields["meta_links"]["paper"] = ""
            dataset_fields["meta_links"]["website"] = ""

        # Extract metadata fields if available
        if dataset.metadata:
            # Handle languages
            if hasattr(dataset.metadata, "languages") and dataset.metadata.languages:
                dataset_fields["language"] = dataset.metadata.languages
            elif hasattr(dataset.metadata, "language") and dataset.metadata.language:
                dataset_fields["language"] = [dataset.metadata.language]

            # Handle domain
            if hasattr(dataset.metadata, "domain") and dataset.metadata.domain:
                dataset_fields["domains"] = [dataset.metadata.domain]

            # Handle token estimates if present
            if hasattr(dataset.metadata, "estimated_input_tokens") and dataset.metadata.estimated_input_tokens:
                dataset_fields["estimated_input_tokens"] = dataset.metadata.estimated_input_tokens
            if hasattr(dataset.metadata, "estimated_output_tokens") and dataset.metadata.estimated_output_tokens:
                dataset_fields["estimated_output_tokens"] = dataset.metadata.estimated_output_tokens

            # Handle difficulty as task_type
            if hasattr(dataset.metadata, "difficulty") and dataset.metadata.difficulty:
                dataset_fields["task_type"] = [f"difficulty:{dataset.metadata.difficulty}"]

            # Handle programming language as concept
            if hasattr(dataset.metadata, "programming_language") and dataset.metadata.programming_language:
                dataset_fields["concepts"] = [f"programming:{dataset.metadata.programming_language}"]

            # Handle format in sample_questions_answers
            if hasattr(dataset.metadata, "format") and dataset.metadata.format:
                if dataset_fields["sample_questions_answers"]:
                    dataset_fields["sample_questions_answers"]["format"] = dataset.metadata.format
                else:
                    dataset_fields["sample_questions_answers"] = {"format": dataset.metadata.format}

        if existing_dataset:
            # Update existing dataset
            for key, value in dataset_fields.items():
                if value is not None:
                    setattr(existing_dataset, key, value)
            db_dataset = existing_dataset
            logger.info(f"Updated existing dataset {dataset.id}")
        else:
            # Create new dataset
            db_dataset = ExpDataset(**dataset_fields)
            db.add(db_dataset)
            try:
                db.flush()  # Get the dataset ID
                logger.info(f"Created new dataset {dataset.id}")
            except Exception:
                # Handle race condition - another thread may have created it
                db.rollback()
                existing_dataset = db.query(ExpDataset).filter_by(name=dataset.name).first()
                if existing_dataset:
                    logger.warning(f"Dataset {dataset.name} was created by another thread, using existing")
                    db_dataset = existing_dataset
                    # Update with our fields
                    for key, value in dataset_fields.items():
                        if value is not None:
                            setattr(existing_dataset, key, value)
                else:
                    raise  # Re-raise if it's not a duplicate issue

        # 2. Create ExpDatasetVersion
        existing_version = (
            db.query(ExpDatasetVersion).filter_by(dataset_id=db_dataset.id, version=dataset.version).first()
        )

        if not existing_version:
            dataset_version = ExpDatasetVersion(
                dataset_id=db_dataset.id,
                version=dataset.version,
                meta={
                    "url": dataset.url,
                    "size_mb": dataset.size_mb,
                    "checksum": dataset.checksum,
                    "sample_count": dataset.sample_count,
                    "metadata": dataset.metadata.model_dump() if dataset.metadata else None,
                },
            )
            db.add(dataset_version)
            logger.info(f"Created dataset version {dataset.version} for {dataset.id}")
        else:
            logger.info(f"Dataset version {dataset.version} already exists for {dataset.id}")

        # 3. Handle traits through pivot table
        if dataset.traits:
            # Get all traits with case-insensitive lookup
            all_traits = db.query(ExpTrait).all()
            traits_by_name = {trait.name: trait for trait in all_traits}
            traits_by_name_lower = {trait.name.lower(): trait for trait in all_traits}

            # Get existing pivots for this dataset
            existing_pivots = {
                str(pivot.trait_id)
                for pivot in db.query(ExpTraitsDatasetPivot).filter_by(dataset_id=db_dataset.id).all()
            }

            for trait_name in dataset.traits:
                # Try exact match first, then case-insensitive
                trait = None
                if trait_name in traits_by_name:
                    trait = traits_by_name[trait_name]
                elif trait_name.lower() in traits_by_name_lower:
                    trait = traits_by_name_lower[trait_name.lower()]
                    logger.info(f"Found case-insensitive match for trait '{trait_name}' -> '{trait.name}'")

                if trait is None:
                    logger.warning(
                        f"Trait '{trait_name}' not found in database (available traits: {list(traits_by_name.keys())}), skipping for dataset {dataset.id}"
                    )
                    continue

                # Create pivot if it doesn't exist
                if str(trait.id) not in existing_pivots:
                    pivot = ExpTraitsDatasetPivot(trait_id=trait.id, dataset_id=db_dataset.id)
                    db.add(pivot)
                    logger.info(f"Linked dataset {dataset.id} with trait {trait.name}")

        # Don't commit here - let the caller handle transaction
        logger.info(f"Prepared dataset metadata for {dataset.id}")

    async def sync_datasets(
        self, manifest: EvalDataManifest, current_version: Optional[str], force_sync: bool = False
    ) -> Dict[str, Any]:
        """Sync dataset metadata from manifest into database.

        Args:
            manifest: Dataset manifest
            current_version: Current local version
            force_sync: Force sync even if versions match

        Returns:
            Sync results dictionary
        """
        logger.info("Starting dataset metadata sync")

        results = {
            "synced_datasets": [],
            "failed_datasets": [],
            "total_datasets": 0,
        }

        # Check if sync is needed
        if not force_sync and current_version and manifest.version_info.current_version == current_version:
            logger.info("Versions match, no sync needed")
            return results

        # Import traits first (they're needed for dataset associations)
        with self.db.get_session() as db:
            trait_results = await self.import_traits(manifest, db)
            logger.info(f"Imported traits: {trait_results}")

        # Import dataset metadata
        with self.db.get_session() as db:
            batch_size = app_settings.eval_sync_batch_size
            batch_count = 0

            for collection_name, collection in manifest.datasets.items():
                dataset_count = len(collection.datasets)
                logger.info(f"Processing {collection_name} dataset collection with {dataset_count} datasets")

                for i, dataset in enumerate(collection.datasets):
                    results["total_datasets"] += 1

                    # Log progress every 10 datasets
                    if i % 10 == 0 and i > 0:
                        logger.info(f"Progress: {i}/{dataset_count} datasets processed in {collection_name}")

                    try:
                        self.import_dataset(dataset, db)
                        results["synced_datasets"].append(dataset.id)
                        batch_count += 1

                        # Commit in batches to avoid memory issues with large datasets
                        if batch_count >= batch_size:
                            db.commit()
                            logger.info(f"Committed batch of {batch_count} datasets")
                            batch_count = 0

                    except Exception as e:
                        logger.error(f"Failed to import dataset {dataset.id}: {e}")
                        results["failed_datasets"].append({"dataset_id": dataset.id, "error": str(e)})
                        # Rollback the session to clear the error state
                        db.rollback()

            # Commit any remaining dataset changes
            if batch_count > 0:
                try:
                    db.commit()
                    logger.info(f"Committed final batch of {batch_count} datasets")
                except Exception as e:
                    db.rollback()
                    logger.error(f"Failed to commit final batch: {e}")
                    # Only mark the last batch as failed
                    last_batch_ids = results["synced_datasets"][-batch_count:]
                    for ds_id in last_batch_ids:
                        results["failed_datasets"].append({"dataset_id": ds_id, "error": "Commit failed"})
                    results["synced_datasets"] = results["synced_datasets"][:-batch_count]

        logger.info(
            f"Dataset sync completed: {len(results['synced_datasets'])} succeeded, {len(results['failed_datasets'])} failed"
        )
        return results

    def record_sync_results(
        self, db: Session, manifest_version: str, sync_status: str, sync_metadata: Optional[Dict] = None
    ) -> None:
        """Record sync results in the database.

        Args:
            db: Database session
            manifest_version: Version that was synced
            sync_status: Status of the sync ('completed', 'failed', 'in_progress')
            sync_metadata: Additional metadata about the sync
        """
        sync_state = EvalSyncState(
            manifest_version=manifest_version,
            sync_timestamp=datetime.now(timezone.utc).isoformat(),
            sync_status=sync_status,
            sync_metadata=sync_metadata or {},
        )

        db.add(sync_state)
        db.commit()

        logger.info(f"Recorded sync state: version={manifest_version}, status={sync_status}")

    async def import_traits(self, manifest: EvalDataManifest, db: Session) -> Dict[str, Any]:
        """Import traits from manifest into the database.

        Args:
            manifest: The evaluation data manifest
            db: Database session

        Returns:
            Dictionary with import results
        """
        results = {
            "created": 0,
            "updated": 0,
            "total": 0,
        }

        # Check if manifest has traits information
        if not manifest.traits:
            logger.info("No traits information in manifest")
            return results

        logger.info(f"Importing traits from manifest (version: {manifest.traits.version})")

        # Get existing traits by name for efficient lookup
        existing_traits = {trait.name: trait for trait in db.query(ExpTrait).all()}
        logger.debug(f"Found {len(existing_traits)} existing traits in database")

        # Check if manifest has trait definitions in the new format
        trait_definitions = []
        if hasattr(manifest.traits, "definitions") and manifest.traits.definitions:
            trait_definitions = manifest.traits.definitions
        elif hasattr(manifest.traits, "categories") and manifest.traits.categories:
            # Fallback to old format - collect all unique traits from categories
            all_trait_names = set()
            for category in manifest.traits.categories:
                for trait_name in category.traits:
                    all_trait_names.add(trait_name)
            # Convert to definition format
            for trait_name in sorted(all_trait_names):
                trait_definitions.append(
                    {
                        "name": trait_name,
                        "description": f"Evaluation trait: {trait_name}",
                        "icon": f"icons/traits/{trait_name.lower().replace(' ', '_') if trait_name else 'default'}.png",
                    }
                )

        # Process each trait definition
        for trait_def in trait_definitions:
            results["total"] += 1

            trait_name = trait_def.get("name") if isinstance(trait_def, dict) else trait_def.name
            trait_desc = (
                trait_def.get("description", f"Evaluation trait: {trait_name}")
                if isinstance(trait_def, dict)
                else trait_def.description
            )
            default_icon = (
                f"icons/traits/{trait_name.lower().replace(' ', '_')}.png"
                if trait_name
                else "icons/traits/default.png"
            )
            trait_icon = trait_def.get("icon", default_icon) if isinstance(trait_def, dict) else trait_def.icon

            if trait_name in existing_traits:
                # Update existing trait
                existing_trait = existing_traits[trait_name]
                existing_trait.description = trait_desc
                existing_trait.icon = trait_icon
                logger.debug(f"Updated trait '{trait_name}'")
                results["updated"] += 1
            else:
                # Create new trait
                new_trait = ExpTrait(name=trait_name, description=trait_desc, icon=trait_icon)
                db.add(new_trait)
                logger.info(f"Created new trait '{trait_name}'")
                results["created"] += 1

        # Commit all changes
        db.commit()

        logger.info(
            f"Trait import completed: {results['created']} created, {results['updated']} existing, {results['total']} total"
        )
        return results


# Global service instance
_sync_service: EvalDataSyncService | None = None


def get_sync_service() -> EvalDataSyncService:
    """Get the global sync service instance."""
    global _sync_service
    if _sync_service is None:
        _sync_service = EvalDataSyncService()
    return _sync_service
