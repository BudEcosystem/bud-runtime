from dataclasses import dataclass

from budmicroframe.commons import logging
from sqlalchemy import func

from ..commons.config import app_settings
from ..commons.constants import ModelDownloadStatus
from .exceptions import SpaceNotAvailableException
from .models import ModelDownloadHistory, ModelDownloadHistoryCRUD


logger = logging.get_logger(__name__)


@dataclass
class ExistingDownload:
    """Represents an existing download record."""

    directory_name: str
    status: ModelDownloadStatus


@dataclass
class DownloadRecord:
    """Represents a download record status."""

    status: ModelDownloadStatus


class DownloadHistory:
    @staticmethod
    def create_download_history(path, size):
        """Create a new download history record."""
        with ModelDownloadHistoryCRUD() as crud:
            return crud.insert(
                {
                    "path": path,
                    "size": size,
                    "status": ModelDownloadStatus.RUNNING,
                },
                raise_on_error=True,
            )

    @staticmethod
    def atomic_space_reservation(path: str, required_size: float) -> bool:
        """Atomically check and reserve space for download.

        Args:
            path: The download path identifier
            required_size: Required size in bytes

        Returns:
            bool: True if space was successfully reserved

        Raises:
            SpaceNotAvailableException: If not enough space available
        """
        with ModelDownloadHistoryCRUD() as crud:
            try:
                # Start a transaction
                # Check if record exists and lock it
                existing_record = (
                    crud.session.query(ModelDownloadHistory)
                    .filter(ModelDownloadHistory.path == path)
                    .with_for_update()
                    .first()
                )

                if existing_record and existing_record.status in [
                    ModelDownloadStatus.RUNNING,
                    ModelDownloadStatus.COMPLETED,
                ]:
                    logger.info(f"Download already exists for {path} with status {existing_record.status}")
                    return True

                # Check available space within the transaction (only count RUNNING and COMPLETED)
                used_space = (
                    crud.session.query(func.sum(ModelDownloadHistory.size))
                    .filter(
                        ModelDownloadHistory.status.in_([ModelDownloadStatus.RUNNING, ModelDownloadStatus.COMPLETED])
                    )
                    .scalar()
                    or 0
                )
                available_space = app_settings.model_download_dir_max_size - used_space

                logger.debug(
                    f"Atomic space check - Required: {required_size}, Available: {available_space}, Used: {used_space}"
                )

                if required_size > available_space:
                    logger.error(f"Space not available. Required: {required_size}, Available: {available_space}")
                    raise SpaceNotAvailableException(
                        f"Space not available. Required: {required_size} bytes, Available: {available_space} bytes"
                    )

                if existing_record:
                    # Update existing record (e.g. if it was FAILED)
                    existing_record.status = ModelDownloadStatus.RUNNING
                    existing_record.size = required_size
                    existing_record.modified_at = func.now()
                else:
                    # Reserve the space by creating the record
                    crud.insert(
                        {
                            "path": path,
                            "size": required_size,
                            "status": ModelDownloadStatus.RUNNING,
                        },
                        raise_on_error=True,
                    )

                # Commit the transaction
                crud.session.commit()
                logger.info(f"Successfully reserved {required_size} bytes for {path}")
                return True

            except SpaceNotAvailableException:
                # Rollback on space error
                crud.session.rollback()
                raise
            except Exception as e:
                # Rollback on any other error
                crud.session.rollback()
                logger.error(f"Error during atomic space reservation: {e}")
                raise

    @staticmethod
    def update_download_status(path: str, status: ModelDownloadStatus):
        """Update the download status for a given path."""
        with ModelDownloadHistoryCRUD() as crud:
            crud.update({"status": status}, conditions={"path": path}, raise_on_error=True)

    @staticmethod
    def delete_download_history(path):
        """Delete download history record for a given path."""
        with ModelDownloadHistoryCRUD() as crud:
            crud.delete(conditions={"path": path}, raise_on_error=False)

    @staticmethod
    def get_total_space_usage():
        """Get total space usage of all downloaded models (excluding uploaded ones)."""
        with ModelDownloadHistoryCRUD() as crud:
            # Only count RUNNING and COMPLETED records, not UPLOADED
            return (
                crud.session.query(func.sum(ModelDownloadHistory.size))
                .filter(ModelDownloadHistory.status.in_([ModelDownloadStatus.RUNNING, ModelDownloadStatus.COMPLETED]))
                .scalar()
                or 0
            )

    @staticmethod
    def get_available_space():
        """Get available space remaining for model downloads."""
        used_space = DownloadHistory.get_total_space_usage()
        return app_settings.model_download_dir_max_size - used_space

    @staticmethod
    def check_existing_download(model_uri: str):
        """Check if a download already exists for the given model URI.

        Args:
            model_uri: The model URI/path to check

        Returns:
            Object with directory_name and status if found, None otherwise
        """
        with ModelDownloadHistoryCRUD() as crud:
            # Extract directory name from model_uri (e.g., "Qwen/Qwen2.5-0.5B" -> "Qwen_Qwen2.5-0.5B")
            directory_name = model_uri.replace("/", "_")
            path = directory_name  # In our case, path is the directory name

            record = crud.session.query(ModelDownloadHistory).filter(ModelDownloadHistory.path == path).first()

            if record:
                return ExistingDownload(directory_name=directory_name, status=record.status)
            return None

    @staticmethod
    def is_download_active(directory_name: str) -> bool:
        """Check if a download is actively running (recently updated).

        Args:
            directory_name: The directory name to check

        Returns:
            True if download is active (updated within last 5 minutes), False otherwise
        """
        from datetime import datetime, timedelta

        with ModelDownloadHistoryCRUD() as crud:
            record = (
                crud.session.query(ModelDownloadHistory)
                .filter(
                    ModelDownloadHistory.path == directory_name,
                    ModelDownloadHistory.status == ModelDownloadStatus.RUNNING,
                )
                .first()
            )

            if record and record.modified_at:
                # Check if updated within last 5 minutes
                cutoff_time = datetime.utcnow() - timedelta(minutes=5)
                return record.modified_at > cutoff_time
            return False

    @staticmethod
    def get_download_by_directory(directory_name: str):
        """Get download record by directory name.

        Args:
            directory_name: The directory name to lookup

        Returns:
            Object with status if found, None otherwise
        """
        with ModelDownloadHistoryCRUD() as crud:
            record = (
                crud.session.query(ModelDownloadHistory).filter(ModelDownloadHistory.path == directory_name).first()
            )

            if record:
                return DownloadRecord(status=record.status)
            return None

    @staticmethod
    def mark_download_failed(directory_name: str):
        """Mark a download as failed.

        Args:
            directory_name: The directory name to mark as failed
        """
        with ModelDownloadHistoryCRUD() as crud:
            crud.update(
                {"status": ModelDownloadStatus.FAILED}, conditions={"path": directory_name}, raise_on_error=False
            )
            logger.warning(f"Marked download as failed: {directory_name}")
