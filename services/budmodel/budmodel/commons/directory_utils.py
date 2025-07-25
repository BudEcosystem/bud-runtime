import os
import shutil
import tempfile
import zipfile
from pathlib import Path

from budmicroframe.commons import logging

from .exceptions import CompressionException, DirectoryOperationException


logger = logging.get_logger(__name__)


class DirectoryOperations:
    """Directory operations class."""

    def validate_path(self, path: Path | str, create: bool = False):
        """Validate a path.

        Args:
            path (Path | str): The path to validate.
            create (bool, optional): Whether to create the path if it doesn't exist. Defaults to False.
        """
        path = Path(path) if isinstance(path, str) else path

        if not path.is_dir():
            if create:
                path.mkdir(parents=True, exist_ok=True)
            else:
                logger.error("Path %s is not a directory", path)
                raise DirectoryOperationException("Path is not a directory")

        return path

    def copy_directory(
        self, source_directory: str | Path, destination_directory: str | Path, overwrite: bool = False
    ) -> Path:
        """Copy a directory from source to destination.

        Args:
            source_directory (str | Path): The source directory to copy.
            destination_directory (str | Path): The destination directory to copy to.
            overwrite (bool, optional): Whether to overwrite the destination directory if it already exists. Defaults to False.
        """
        source_directory = self.validate_path(source_directory, create=False)
        destination_directory = self.validate_path(destination_directory, create=True)

        # Check if there's enough disk space
        self.check_disk_space(source_directory, destination_directory)

        if overwrite:
            try:
                self.remove_directory(destination_directory)
            except DirectoryOperationException as e:
                logger.error("Failed to Overwrite destination directory")
                raise DirectoryOperationException("Failed to Overwrite destination directory") from e

        try:
            shutil.copytree(source_directory, destination_directory, dirs_exist_ok=True)
        except Exception as e:
            logger.error("Failed to copy directory %s to %s, error: %s", source_directory, destination_directory, e)
            raise DirectoryOperationException("Failed to copy directory") from e

        return destination_directory

    def remove_directory(self, directory: Path | str):
        """Remove a directory.

        Args:
            directory (Path | str): The directory to remove.
        """
        directory = self.validate_path(directory, create=False)
        try:
            shutil.rmtree(directory, ignore_errors=True)
        except FileNotFoundError:
            logger.warning("Directory %s not found", directory)
        except Exception as e:
            logger.error("Failed to remove directory %s, error: %s", directory, e)
            raise DirectoryOperationException("Failed to remove directory") from e

    def check_disk_space(self, source_directory: Path | str, destination_directory: Path | str) -> None:
        """Check if there's enough disk space.

        Args:
            source_directory (Path | str): The source directory to check.
            destination_directory (Path | str): The destination directory to check.
        """
        source_directory = self.validate_path(source_directory, create=False)
        destination_directory = self.validate_path(destination_directory, create=False)

        try:
            source_size = self.get_directory_size(source_directory)
            free_space = shutil.disk_usage(str(destination_directory.parent)).free
            logger.debug("Source directory size: %s bytes", source_size)
            logger.debug("Free space on %s: %s bytes", destination_directory.parent, free_space)

            if free_space < source_size:
                logger.error(
                    "Not enough disk space. Need %s bytes, but only %s bytes available", source_size, free_space
                )
                raise DirectoryOperationException(
                    f"Not enough disk space. Need {source_size} bytes, " f"but only {free_space} bytes available"
                )
        except Exception as e:
            logger.error(f"Disk space check failed: {str(e)}")
            raise DirectoryOperationException("Disk space check failed") from e

    def move_directory(
        self, source_directory: str | Path, destination_directory: str | Path, overwrite: bool = False
    ) -> Path:
        """Move a directory from source to destination.

        Args:
            source_directory (str | Path): The source directory to move.
            destination_directory (str | Path): The destination directory to move to.
            overwrite (bool, optional): Whether to overwrite the destination directory if it already exists. Defaults to False.
        """
        source_directory = self.validate_path(source_directory, create=False)
        destination_directory = self.validate_path(destination_directory, create=True)

        if overwrite:
            try:
                self.remove_directory(destination_directory)
            except DirectoryOperationException as e:
                logger.error("Failed to Overwrite destination directory")
                raise DirectoryOperationException("Failed to Overwrite destination directory") from e
        try:
            shutil.move(source_directory, destination_directory)
        except Exception as e:
            logger.error("Failed to move directory %s to %s, error: %s", source_directory, destination_directory, e)
            raise DirectoryOperationException("Failed to move directory") from e

        return destination_directory

    def get_directory_size(self, directory: Path | str) -> int:
        """Get the size of a directory."""
        directory = self.validate_path(directory, create=False)
        total = 0
        with os.scandir(directory) as it:
            for entry in it:
                if entry.is_file():
                    total += entry.stat().st_size
                elif entry.is_dir():
                    total += self.get_directory_size(entry.path)
        return total


class CompressionManager:
    """Compression manager class."""

    def extract_all(self, zip_path: str | Path, extract_to: str | Path, overwrite: bool = False):
        """Extract all contents from a zip archive."""
        zip_path = Path(zip_path) if isinstance(zip_path, str) else zip_path
        extract_to = Path(extract_to) if isinstance(extract_to, str) else extract_to

        if not zip_path.exists() or not zip_path.is_file():
            logger.error("Zip file does not exist: %s", zip_path)
            raise CompressionException("Zip file does not exist")

        if extract_to.exists() and not overwrite:
            logger.error("Destination directory already exists and overwrite is False: %s", extract_to)
            raise CompressionException("Destination directory already exists")

        try:
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(extract_to)
            logger.info("Successfully extracted zip: %s to %s", zip_path, extract_to)
        except Exception as e:
            logger.error("Failed to extract zip: %s, error: %s", zip_path, e)
            raise CompressionException("Failed to extract zip") from e

    def extract_all_without_root_directory(
        self, zip_path: str | Path, extract_to: str | Path, overwrite: bool = False
    ):
        """Extract all contents from a zip archive, removing the root directory if present."""
        zip_path = Path(zip_path) if isinstance(zip_path, str) else zip_path
        extract_to = Path(extract_to) if isinstance(extract_to, str) else extract_to

        if not zip_path.exists() or not zip_path.is_file():
            logger.error("Zip file does not exist: %s", zip_path)
            raise CompressionException("Zip file does not exist")

        if extract_to.exists() and not overwrite:
            logger.error("Destination directory already exists and overwrite is False: %s", extract_to)
            raise CompressionException("Destination directory already exists")

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_extract_dir = Path(temp_dir)
                # Extract to temporary directory
                with zipfile.ZipFile(zip_path, "r") as zip_ref:
                    zip_ref.extractall(temp_extract_dir)

                # Identify root directory in temp extraction
                extracted_items = list(temp_extract_dir.iterdir())

                if len(extracted_items) == 1 and extracted_items[0].is_dir():
                    root_folder = extracted_items[0]
                    for item in root_folder.iterdir():
                        shutil.move(str(item), str(extract_to))
                else:
                    extract_to.mkdir(parents=True, exist_ok=True)
                    for item in extracted_items:
                        shutil.move(str(item), str(extract_to))

            logger.info("Successfully extracted zip: %s to %s", zip_path, extract_to)
        except Exception as e:
            logger.error("Failed to extract zip: %s, error: %s", zip_path, e)
            raise CompressionException("Failed to extract zip") from e
