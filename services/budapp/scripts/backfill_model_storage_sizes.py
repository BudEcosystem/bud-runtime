#!/usr/bin/env python3
"""Backfill script to calculate and update storage_size_gb for existing models.

This script:
1. Finds all models that have a local_path but no storage_size_gb
2. Calculates the storage size from MinIO for each model
3. Updates the database with the calculated size

Usage:
    python scripts/backfill_model_storage_sizes.py [--dry-run] [--batch-size=10]
"""

import argparse
import asyncio
import sys
from pathlib import Path


# Add parent directory to path to import budapp modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import and_

from budapp.commons import logging
from budapp.commons.config import app_settings
from budapp.commons.database import SessionLocal
from budapp.model_ops.crud import ModelDataManager
from budapp.model_ops.models import Model
from budapp.shared.minio_store import ModelStore


logger = logging.get_logger(__name__)


async def backfill_storage_sizes(dry_run: bool = False, batch_size: int = 10) -> None:
    """Backfill storage_size_gb for existing models.

    Args:
        dry_run: If True, only report what would be done without making changes
        batch_size: Number of models to process in each batch
    """
    logger.info("Starting storage size backfill process...")
    logger.info(f"Dry run mode: {dry_run}")
    logger.info(f"Batch size: {batch_size}")

    # Initialize MinIO store
    model_store = ModelStore()
    session = SessionLocal()

    try:
        # Get all models that have a local_path but no storage_size_gb
        model_dm = ModelDataManager(session)

        # First, get the total count without loading all models
        total_models = (
            session.query(Model).filter(and_(Model.local_path.isnot(None), Model.storage_size_gb.is_(None))).count()
        )

        logger.info(f"Found {total_models} models needing storage size calculation")

        if total_models == 0:
            logger.info("No models need backfilling. Exiting.")
            return

        # Process models in batches using pagination
        successful = 0
        failed = 0
        skipped = 0

        for offset in range(0, total_models, batch_size):
            # Fetch only one batch at a time using limit and offset
            batch = (
                session.query(Model)
                .filter(and_(Model.local_path.isnot(None), Model.storage_size_gb.is_(None)))
                .limit(batch_size)
                .offset(offset)
                .all()
            )
            logger.info(f"\nProcessing batch {offset // batch_size + 1} ({len(batch)} models)...")

            for model in batch:
                try:
                    logger.info(f"  Processing model: {model.name} (ID: {model.id})")
                    logger.info(f"    Local path: {model.local_path}")

                    # Calculate storage size from MinIO
                    storage_size_gb = model_store.get_folder_size(app_settings.minio_bucket, model.local_path)

                    logger.info(f"    Calculated size: {storage_size_gb:.2f} GB")

                    if storage_size_gb == 0:
                        logger.warning("    WARNING: Model has 0 GB size - may indicate missing files")
                        skipped += 1
                        continue

                    if not dry_run:
                        # Update the model
                        await model_dm.update_by_fields(model, {"storage_size_gb": storage_size_gb})
                        logger.info("    ✓ Updated successfully")
                        successful += 1
                    else:
                        logger.info(f"    [DRY RUN] Would update storage_size_gb to {storage_size_gb:.2f} GB")
                        successful += 1

                except Exception as e:
                    logger.error(f"    ✗ Failed to process model {model.name}: {e}")
                    failed += 1
                    continue

        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("Backfill Summary:")
        logger.info(f"  Total models found: {total_models}")
        logger.info(f"  Successfully processed: {successful}")
        logger.info(f"  Failed: {failed}")
        logger.info(f"  Skipped (0 GB size): {skipped}")

        if dry_run:
            logger.info("\n  This was a DRY RUN - no changes were made to the database")
            logger.info("  Run without --dry-run to apply changes")
        else:
            logger.info("\n  Database has been updated")

        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"Fatal error during backfill: {e}", exc_info=True)
        raise
    finally:
        session.close()


def main():
    """Main entry point for the backfill script."""
    parser = argparse.ArgumentParser(
        description="Backfill storage_size_gb for existing models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run to see what would be updated
  python scripts/backfill_model_storage_sizes.py --dry-run

  # Actually update the models
  python scripts/backfill_model_storage_sizes.py

  # Process in smaller batches
  python scripts/backfill_model_storage_sizes.py --batch-size=5
        """,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run in dry-run mode without making changes",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Number of models to process in each batch (default: 10)",
    )

    args = parser.parse_args()

    try:
        asyncio.run(backfill_storage_sizes(dry_run=args.dry_run, batch_size=args.batch_size))
    except KeyboardInterrupt:
        logger.info("\nBackfill interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Backfill failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
