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


"""Implements services and business logic for local models."""

import json
import os
import re
import shutil
import tempfile
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple

from aria2p.downloads import Download
from budmicroframe.commons import logging
from budmicroframe.shared.dapr_service import DaprService

from ..commons.config import app_settings
from ..commons.constants import ModelDownloadStatus
from ..commons.directory_utils import DirectoryOperations
from ..commons.exceptions import (
    Aria2Exception,
    CompressionException,
    DirectoryOperationException,
    ModelDownloadException,
    ModelExtractionException,
)
from ..commons.helpers import get_size_in_bytes, is_zip_file, is_zip_url, list_directory_files, safe_delete
from ..model_info.schemas import LicenseInfo, ModelInfo
from ..shared.aria2p_service import Aria2Downloader
from .download_history import DownloadHistory
from .exceptions import SpaceNotAvailableException
from .helper import mapped_licenses
from .huggingface import HuggingFaceModelInfo, HuggingfaceUtils
from .license import LocalModelLicenseExtractor
from .parser import generate_license_details, get_model_analysis, normalize_license_identifier
from .store import measure_minio_upload_speed


logger = logging.get_logger(__name__)


class LocalModelDownloadService:
    """Service class for model download."""

    def download_model_from_url(self, url: str, directory_name: str, workflow_id: Optional[str] = None) -> str:
        """Download a model from a URL and return the path to the downloaded file.

        If the file is zip file, extract it to a temporary directory and return the path to the extracted directory.
        else download the file/folder and return the path to the downloaded file
        """
        logger.debug("Downloading model from: %s", url)
        destination = os.path.join(app_settings.model_download_dir, directory_name)

        try:
            is_archived = is_zip_url(url)

            # Initialize aria2 downloader
            aria2_downloader = Aria2Downloader()

            # Calculate free space
            free_space_gb = DownloadHistory.get_available_space()

            if is_archived:
                # Download the zip file to a temporary directory and extract to destination
                with tempfile.TemporaryDirectory() as temp_dir:
                    # Specify aria2p options (download directory)
                    aria2p_options = {
                        "dir": temp_dir,
                    }

                    # Download the file
                    aria2_download = aria2_downloader.download_from_any_url(url, aria2p_options)[0]

                    try:
                        # sleep for update aria2p download object
                        time.sleep(5)
                        aria2_download.update()
                        model_size_bytes = aria2_download.total_length
                        model_size_gb = model_size_bytes / (1024 * 1024 * 1024)
                        logger.debug("Space available: %s GB, Space required: %s GB", free_space_gb, model_size_gb)

                        if model_size_gb > free_space_gb:
                            logger.error("Space not available to download. Removing download record")
                            try:
                                aria2_downloader.remove_download(aria2_download, force=True, remove_files=True)
                            except Aria2Exception:
                                logger.error("Aria2 download cleanup failed")
                            raise SpaceNotAvailableException("Space not available to download")

                        # Create a new download record with `running` status
                        DownloadHistory.create_download_history(directory_name, model_size_gb)

                        # Track download
                        self.listen_to_aria2p_download(
                            aria2_download, is_archived=is_archived, workflow_id=workflow_id
                        )

                        # Extract the zip file to a directory
                        self.extract_zip(
                            os.path.join(temp_dir, aria2_download.name), destination, workflow_id=workflow_id
                        )
                    except Exception as e:
                        # Remove aria2 download record
                        try:
                            aria2_downloader.remove_download(aria2_download, force=True, remove_files=True)
                            logger.debug("Performed Aria2 download cleanup")
                        except Aria2Exception:
                            logger.error("Aria2 download cleanup failed")
                        raise e
            else:
                # Specify aria2p options (download directory)
                aria2p_options = {
                    "dir": destination,
                }

                # Download the file
                aria2_download = aria2_downloader.download_from_any_url(url, aria2p_options)[0]

                try:
                    # sleep for update aria2p download object
                    time.sleep(5)
                    aria2_download.update()
                    model_size_bytes = aria2_download.total_length
                    model_size_gb = model_size_bytes / (1024 * 1024 * 1024)
                    logger.debug("Space available: %s GB, Space required: %s GB", free_space_gb, model_size_gb)

                    if model_size_gb > free_space_gb:
                        logger.error("Space not available to download. Removing download record")
                        try:
                            aria2_downloader.remove_download(aria2_download, force=True, remove_files=True)
                        except Aria2Exception:
                            logger.error("Aria2 download cleanup failed")
                        raise SpaceNotAvailableException("Space not available to download")

                    # Create a new download record with `running` status
                    DownloadHistory.create_download_history(directory_name, model_size_gb)

                    # Track download
                    self.listen_to_aria2p_download(aria2_download, is_archived=is_archived, workflow_id=workflow_id)
                except Exception as e:
                    # Remove aria2 download record
                    try:
                        aria2_downloader.remove_download(aria2_download, force=True, remove_files=True)
                        logger.debug("Performed Aria2 download cleanup")
                    except Aria2Exception:
                        logger.error("Aria2 download cleanup failed")
                    raise e

                if workflow_id:
                    self.update_save_to_registry_details(workflow_id, destination)
                    logger.debug("Updated save to registry details")

            # Update the record to `completed` and set the path
            DownloadHistory.update_download_status(directory_name, ModelDownloadStatus.COMPLETED)

            return directory_name
        except (CompressionException, Aria2Exception, SpaceNotAvailableException, DirectoryOperationException) as e:
            safe_delete(destination)
            DownloadHistory.delete_download_history(directory_name)
            raise e
        except Exception as e:
            safe_delete(destination)
            DownloadHistory.delete_download_history(directory_name)
            raise e

    def transfer_model_from_disk(self, uri: str, directory_name: str, workflow_id: Optional[str] = None) -> str:
        """Transfer a model from the local disk to the model storage directory.

        If the source is a zip file, extract it to the destination.
        If the source is a regular file or directory, copy it directly.

        Args:
            source_path (str): Path to the source file or directory.
            directory_name (str): Target directory name in model storage.

        Returns:
            str: The name of the final directory containing the model.
        """
        source_path = os.path.join(app_settings.add_model_dir, uri)
        destination = os.path.join(app_settings.model_download_dir, directory_name)

        directory_operations = DirectoryOperations()

        # Calculate free space
        free_space_gb = DownloadHistory.get_available_space()
        model_size_bytes = get_size_in_bytes(source_path)
        model_size_gb = model_size_bytes / (1024 * 1024 * 1024)
        logger.debug("Space available: %s GB, Space required: %s GB", free_space_gb, model_size_gb)

        if model_size_gb > free_space_gb:
            logger.error("Space not available to download.")
            raise SpaceNotAvailableException("Space not available to download")

        try:
            # Create a new download record with `running` status
            DownloadHistory.create_download_history(directory_name, model_size_gb)

            if is_zip_file(source_path):
                logger.debug("Extracting zip file from: %s to: %s", source_path, destination)

                # Extract the zip file
                self.extract_zip(source_path, destination, workflow_id=workflow_id)
            else:
                logger.debug("Copying model from: %s to: %s", source_path, destination)

                self.transfer_directory(source_path, destination, workflow_id=workflow_id)

            # Update the record to `completed` and set the path
            DownloadHistory.update_download_status(directory_name, ModelDownloadStatus.COMPLETED)

            return directory_name
        except (CompressionException, SpaceNotAvailableException, DirectoryOperationException) as e:
            safe_delete(destination)
            DownloadHistory.delete_download_history(directory_name)
            raise e
        except Exception as e:
            safe_delete(destination)
            DownloadHistory.delete_download_history(directory_name)
            raise e

    def extract_zip(
        self,
        zip_path: str | Path,
        extract_path: str | Path,
        password: Optional[bytes] = None,
        workflow_id: Optional[str] = None,
    ) -> bool:
        """Extract ZIP file contents with progress tracking.

        Args:
            zip_path: Path to ZIP file
            extract_path: Destination directory
            password: ZIP password if encrypted

        Returns:
            bool: True if successful, False otherwise
        """
        # Update Unarchive start time
        try:
            # Update state store workflow eta
            state_store_key = f"eta_{workflow_id}"
            eta_ttl = 86400  # 24 hours
            logger.debug("Updating unarchive start time in state store: %s", state_store_key)

            dapr_service = DaprService()
            state_store_data = dapr_service.get_state(
                store_name=app_settings.statestore_name,
                key=state_store_key,
            ).json()

            state_store_data["steps_data"]["model_download"]["is_archived"] = True
            state_store_data["steps_data"]["model_download"]["current_process"] = "extraction"
            state_store_data["steps_data"]["model_download"]["start_time"] = datetime.now(timezone.utc).isoformat()

            # Save state store data
            dapr_service.save_to_statestore(
                store_name=app_settings.statestore_name,
                key=state_store_key,
                value=state_store_data,
                ttl=eta_ttl,
            )
        except Exception as e:
            logger.exception("Error updating unarchive start time in state store: %s", e)

        try:
            # Convert paths to Path objects
            zip_path = Path(zip_path)
            extract_path = Path(extract_path)

            # Ensure extract directory exists
            extract_path.mkdir(parents=True, exist_ok=True)

            # Open ZIP file
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                # Get the base directory name from the first file
                first_path = Path(zip_ref.filelist[0].filename)
                base_dir = first_path.parts[0]

                # Get total size and file count
                total_size = sum(info.file_size for info in zip_ref.filelist)
                total_files = len(zip_ref.filelist)
                extracted_size = 0

                logger.debug("Extracting: %s", zip_path.name)
                logger.debug("Total files: %d", total_files)
                logger.debug("Total size: %.2f MB", total_size / (1024 * 1024))

                # Extract each file
                for i, file_info in enumerate(zip_ref.filelist, 1):
                    if workflow_id:
                        # Update state store workflow eta
                        self.update_zip_progress(
                            workflow_id,
                            total_size,
                            file_info.file_size,
                            file_info.filename,
                            extract_path,
                            total_files,
                            i,
                        )
                    try:
                        # Get file details
                        filename = file_info.filename
                        file_size = file_info.file_size

                        # Skip if it's the base directory itself
                        if filename.endswith("/"):
                            continue

                        # Remove the base directory from the path
                        relative_path = Path(filename)
                        if relative_path.parts[0] == base_dir:
                            relative_path = Path(*relative_path.parts[1:])

                        # Create the target path
                        target_path = extract_path / relative_path
                        target_path.parent.mkdir(parents=True, exist_ok=True)

                        # Extract file with password if provided
                        if password:
                            zip_ref.extract(file_info, extract_path, pwd=password)
                            if target_path != (extract_path / filename):
                                os.rename(extract_path / filename, target_path)
                        else:
                            # Read the file from zip and write to target path
                            with zip_ref.open(file_info) as source, open(target_path, "wb") as target:
                                target.write(source.read())

                        # Update progress
                        extracted_size += file_size
                        progress = (extracted_size / total_size) * 100

                        logger.debug(
                            f"[{i}/{total_files}] {progress:.1f}% | "
                            f"Extracted: {filename} "
                            f"({file_size / (1024 * 1024):.2f} MB)"
                        )

                    except Exception as e:
                        logger.error("Error extracting %s: %s", filename, e)
                        raise CompressionException(f"Error extracting {filename}") from e

                logger.debug("\nExtraction completed:")
                logger.debug("Files extracted: %s", total_files)
                logger.debug("Total size: %.2f MB", total_size / (1024 * 1024))
                logger.debug("Destination: %s", extract_path)

                if workflow_id:
                    self.update_save_to_registry_details(workflow_id, extract_path)
                    logger.debug("Updated save to registry details")
        except zipfile.BadZipFile as e:
            logger.error("Invalid or corrupted ZIP file")
            raise CompressionException("Invalid or corrupted ZIP file") from e
        except CompressionException as e:
            raise e
        except Exception as e:
            logger.exception("Error extracting ZIP: %s", e)
            raise CompressionException(f"Error extracting ZIP: {e}") from e

    def listen_to_aria2p_download(
        self,
        download: Download,
        timeout_seconds: int = 5,
        is_archived: bool = False,
        workflow_id: Optional[str] = None,
    ) -> Download:
        """Listen to download events.

        Args:
            download: Download to listen to
            timeout_seconds: Timeout in seconds

        Returns:
            Download
        """
        aria2_downloader = Aria2Downloader()
        while True:
            download.update()

            # download statuses are: active, waiting, paused, error, complete or removed.
            download_status = download.status

            if download_status == "complete":
                return download
            elif download_status == "error":
                logger.debug(f"Download failed: {download.error_message}")
                aria2_downloader.purge_download(download)
                raise Aria2Exception("Download failed")
            elif download_status == "removed":
                aria2_downloader.purge_download(download)
                raise Aria2Exception("Download removed")
            else:
                if workflow_id:
                    try:
                        # Update state store workflow eta
                        state_store_key = f"eta_{workflow_id}"
                        eta_ttl = 86400  # 24 hours
                        logger.debug("Updating workflow eta in state store: %s", state_store_key)

                        dapr_service = DaprService()
                        state_store_data = dapr_service.get_state(
                            store_name=app_settings.statestore_name,
                            key=state_store_key,
                        ).json()

                        state_store_data["steps_data"]["model_download"]["is_archived"] = is_archived
                        state_store_data["steps_data"]["model_download"]["current_file"] = download.files[0].index
                        state_store_data["steps_data"]["model_download"]["current_file_name"] = download.name
                        state_store_data["steps_data"]["model_download"]["current_file_size"] = download.piece_length
                        state_store_data["steps_data"]["model_download"]["output_path"] = str(download.dir)
                        state_store_data["steps_data"]["model_download"]["total_files"] = len(download.files)
                        state_store_data["steps_data"]["model_download"]["download_eta"] = download.eta.total_seconds()

                        # Save state store data
                        dapr_service.save_to_statestore(
                            store_name=app_settings.statestore_name,
                            key=state_store_key,
                            value=state_store_data,
                            ttl=eta_ttl,
                        )

                    except Exception as e:
                        logger.exception("Error updating workflow eta in state store: %s", e)

                logger.debug(f"Downloading {download.name}")
                logger.debug(f"Download status: {download_status}")
                logger.debug(f"Download total size: {download.total_length_string()}")
                logger.debug(f"Download completed size: {download.completed_length_string()}")
                logger.debug(f"Download progress: {download.progress_string()}")
                logger.debug(f"Download ETA: {download.eta_string()}")
                logger.debug(f"Download speed: {download.download_speed_string()}")
                logger.debug("================================================")

                time.sleep(timeout_seconds)

    @staticmethod
    def update_zip_progress(
        workflow_id: str,
        total_size: int,
        current_file_size: int,
        current_file_name: str,
        output_path: str,
        total_files: int,
        current_file: int,
    ):
        """Update the progress of the zip file.

        Args:
            workflow_id: Workflow ID
            total_size: Total size of the zip file
            current_file_size: Size of the current file
            current_file_name: Name of the current file
            output_path: Path to the output directory
            total_files: Total number of files in the zip file
            current_file: Current file index
        """
        try:
            # Update state store workflow eta
            state_store_key = f"eta_{workflow_id}"
            eta_ttl = 86400  # 24 hours
            logger.debug("Updating workflow eta in state store: %s", state_store_key)

            dapr_service = DaprService()
            state_store_data = dapr_service.get_state(
                store_name=app_settings.statestore_name,
                key=state_store_key,
            ).json()

            state_store_data["steps_data"]["model_download"]["is_archived"] = True
            state_store_data["steps_data"]["model_download"]["current_process"] = "extraction"
            state_store_data["steps_data"]["model_download"]["current_file"] = current_file
            state_store_data["steps_data"]["model_download"]["current_file_name"] = current_file_name
            state_store_data["steps_data"]["model_download"]["current_file_size"] = current_file_size
            state_store_data["steps_data"]["model_download"]["output_path"] = str(output_path)
            state_store_data["steps_data"]["model_download"]["total_files"] = total_files
            state_store_data["steps_data"]["model_download"]["total_size"] = total_size

            # Save state store data
            dapr_service.save_to_statestore(
                store_name=app_settings.statestore_name,
                key=state_store_key,
                value=state_store_data,
                ttl=eta_ttl,
            )

        except Exception as e:
            logger.exception("Error updating workflow eta in state store: %s", e)

    def transfer_directory(
        self,
        source_dir: str | Path,
        dest_dir: str | Path,
        workflow_id: Optional[str] = None,
    ):
        """Transfer files from source to destination directory individually while preserving directory structure.

        Args:
            source_dir: Source directory path
            dest_dir: Destination directory path

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Convert to Path objects
            source_dir = Path(source_dir)
            dest_dir = Path(dest_dir)

            # Create destination if it doesn't exist
            os.makedirs(dest_dir, exist_ok=True)

            # Calculate total size and files first
            total_size = 0
            total_files = 0
            for root, _, files in os.walk(source_dir):
                for file in files:
                    file_path = Path(root) / file
                    total_size += file_path.stat().st_size
                    total_files += 1

            transferred_size = 0
            file_count = 0

            logger.debug("Starting transfer:")
            logger.debug("Source: %s", source_dir)
            logger.debug("Destination: %s", dest_dir)
            logger.debug("Total files: %d", total_files)
            logger.debug("Total size: %.2f MB", total_size / (1024 * 1024))

            # Walk through source directory
            for root, _dirs, files in os.walk(source_dir):
                # Convert to Path objects
                source_root = Path(root)
                relative_path = source_root.relative_to(source_dir)

                # Create destination directory
                dest_path = Path(os.path.join(dest_dir, relative_path))
                os.makedirs(dest_path, exist_ok=True)

                # Copy each file
                for file in files:
                    source_file = Path(os.path.join(source_root, file))
                    dest_file = Path(os.path.join(dest_path, file))
                    # Copy file
                    file_size = source_file.stat().st_size
                    logger.debug("Copying: %s", relative_path / file)
                    logger.debug("Size: %.2f MB", file_size / (1024 * 1024))

                    if workflow_id:
                        self.update_disk_transfer_progress(
                            workflow_id,
                            total_size,
                            file_size,
                            str(file),
                            str(dest_dir),
                            total_files,
                            file_count,
                        )

                    shutil.copy2(source_file, dest_file)

                    # Update progress
                    transferred_size += file_size
                    file_count += 1
                    progress = (transferred_size / total_size) * 100

                    logger.debug(
                        "Progress: [%d/%d] %.1f%% | Transferred: %.2f MB",
                        file_count,
                        total_files,
                        progress,
                        transferred_size / (1024 * 1024),
                    )

            logger.debug("Transfer completed:")
            logger.debug("Files transferred: %d", file_count)
            logger.debug("Total size: %.2f MB", transferred_size / (1024 * 1024))
            logger.debug("Destination: %s", dest_dir)
        except Exception as e:
            logger.exception(f"Transfer failed: {e}")
            raise ModelDownloadException("Transfer from disk failed") from e

    @staticmethod
    def update_disk_transfer_progress(
        workflow_id: str,
        total_size: int,
        current_file_size: int,
        current_file_name: str,
        output_path: str,
        total_files: int,
        current_file: int,
    ):
        """Update the progress of the disk transfer.

        Args:
            workflow_id: Workflow ID
            total_size: Total size of the disk transfer
            current_file_size: Size of the current file
            current_file_name: Name of the current file
            output_path: Path to the output directory
            total_files: Total number of files in the disk transfer
            current_file: Current file index
        """
        try:
            # Update state store workflow eta
            state_store_key = f"eta_{workflow_id}"
            eta_ttl = 86400  # 24 hours
            logger.debug("Updating workflow eta in state store: %s", state_store_key)

            dapr_service = DaprService()
            state_store_data = dapr_service.get_state(
                store_name=app_settings.statestore_name,
                key=state_store_key,
            ).json()

            state_store_data["steps_data"]["model_download"]["current_file"] = current_file
            state_store_data["steps_data"]["model_download"]["current_file_name"] = current_file_name
            state_store_data["steps_data"]["model_download"]["current_file_size"] = current_file_size
            state_store_data["steps_data"]["model_download"]["output_path"] = str(output_path)
            state_store_data["steps_data"]["model_download"]["total_files"] = total_files
            state_store_data["steps_data"]["model_download"]["total_size"] = total_size

            # Save state store data
            dapr_service.save_to_statestore(
                store_name=app_settings.statestore_name,
                key=state_store_key,
                value=state_store_data,
                ttl=eta_ttl,
            )

        except Exception as e:
            logger.exception("Error updating workflow eta in state store: %s", e)

    @staticmethod
    def update_save_to_registry_details(workflow_id: str, source_path: str):
        """Update the details of the model to be saved to the registry.

        Args:
            workflow_id: Workflow ID
            source_path: Path to the source model
        """
        files, _ = list_directory_files(source_path)

        # Analyze large files
        large_files_info = HuggingfaceUtils().analyze_large_files(files)
        save_to_registry_total_files = large_files_info["large_file_count"]
        save_to_registry_total_size = large_files_info["total_size_bytes"]

        # Estimate minio upload speed
        minio_upload_speed = measure_minio_upload_speed()
        logger.debug("Minio upload speed: %s", minio_upload_speed)

        # Estimate save to registry eta
        try:
            save_to_registry_eta = save_to_registry_total_size / minio_upload_speed
            logger.debug("Save to registry eta: %s", save_to_registry_eta)
        except ZeroDivisionError as e:
            logger.exception("Error calculating Save to registry eta: %s", e)
            save_to_registry_eta = 120

        try:
            # Update state store workflow eta
            state_store_key = f"eta_{workflow_id}"
            eta_ttl = 86400  # 24 hours
            logger.debug("Updating workflow eta in state store: %s", state_store_key)

            dapr_service = DaprService()
            state_store_data = dapr_service.get_state(
                store_name=app_settings.statestore_name,
                key=state_store_key,
            ).json()

            state_store_data["steps_data"]["save_model"]["total_files"] = save_to_registry_total_files
            state_store_data["steps_data"]["save_model"]["total_size"] = save_to_registry_total_size
            state_store_data["steps_data"]["save_model"]["eta"] = save_to_registry_eta

            # Save state store data
            dapr_service.save_to_statestore(
                store_name=app_settings.statestore_name,
                key=state_store_key,
                value=state_store_data,
                ttl=eta_ttl,
            )

        except Exception as e:
            logger.exception("Error updating workflow eta in state store: %s", e)


class LocalModelExtraction:
    """Service class for model extraction."""

    def __init__(self, model_uri: str, directory_name: str) -> None:
        """Initialize the LocalModelExtraction class."""
        self.model_uri = model_uri
        self.directory_name = directory_name
        self.model_path = os.path.join(app_settings.model_download_dir, directory_name)

    def extract_model_info(self) -> ModelInfo:
        """Extract model info from local model."""
        # Validate local model
        root_file_names = ["config.json"]
        root_file_extensions = ["safetensors"]
        self.validate_local_model(self.model_path, root_file_names, root_file_extensions)

        readme_content = LocalModelExtraction.get_readme_content(self.model_path)
        if readme_content:
            model_analysis = get_model_analysis(readme_content)
            model_info = ModelInfo(
                uri=self.model_uri,
                tasks=[],
                author="",
                modality="",
                description=model_analysis.get("description", ""),
                use_cases=model_analysis.get("usecases", []),
                strengths=model_analysis.get("advantages", []),
                limitations=model_analysis.get("disadvantages", []),
            )
        else:
            model_info = ModelInfo(uri=self.model_uri, tasks=[], author="", description="", modality="")

        license_details = LocalModelLicenseExtractor().extract_license(self.model_path)
        if license_details:
            license_info = LicenseInfo(
                id=license_details.id,
                license_id=license_details.license_id,
                name=license_details.name,
                url=license_details.url,
                faqs=license_details.faqs,
                type=license_details.type,
                description=license_details.description,
                suitability=license_details.suitability,
            )
            model_info.license = license_info

        config_data = HuggingFaceModelInfo.parse_transformers_config(self.model_path)

        model_name_or_path = LocalModelExtraction.get_uri_from_model_config(self.model_path)

        hf_author = HuggingfaceUtils.get_hf_logo(model_name_or_path) if model_name_or_path else ""

        if not config_data["modality"]:
            logger.error("Unable to extract modality.")
            raise ModelExtractionException("Unable to extract modality.")

        model_info.architecture = config_data["architecture"]
        model_info.modality = config_data["modality"]
        model_info.logo_url = hf_author

        return model_info

    @staticmethod
    def validate_local_model(folder_path: str | Path, filenames: list[str], extensions: list[str]):
        """Check if the given list of files and regex extensions exist in the root of a folder.

        Args:
            folder_path (str | Path): The root folder path.
            filenames (list[str]): List of filenames to check.
            extensions (list[str]): List of regex patterns for extensions to check.

        Returns:
            dict[str, bool]: Dictionary with filenames/extensions as keys and existence as values.
        """
        folder_path = Path(folder_path) if isinstance(folder_path, str) else folder_path

        root_files = {file.name for file in folder_path.iterdir() if file.is_file()}

        # Identify missing files
        missing_files = [name for name in filenames if name not in root_files]

        # Identify missing extensions
        missing_extensions = []
        for ext in extensions:
            try:
                pattern = re.compile(rf".*\.{ext}$", re.IGNORECASE)
                if not any(pattern.match(file) for file in root_files):
                    missing_extensions.append(ext)
            except re.error:
                logger.error(f"Invalid regex pattern: {ext}")

        error_messages = ""
        if missing_files:
            error_messages += f"Missing files: {', '.join(missing_files)}"
        if missing_extensions:
            error_messages += ". "
            error_messages += f"Missing extensions: {', '.join(missing_extensions)}."

        if error_messages:
            raise ModelExtractionException(error_messages)

    @staticmethod
    def get_readme_content(model_path: str) -> str:
        """Get the content of the readme file."""
        try:
            readme_files = ["README.md", "README.txt", "README.rst", "README"]
            for readme_file in readme_files:
                readme_path = os.path.join(model_path, readme_file)
                if os.path.exists(readme_path):
                    with open(readme_path, "r") as f:
                        return f.read()

            logger.warning("No readme file found in %s", model_path)
            return ""
        except Exception as e:
            logger.exception("Error getting readme content: %s", e)
            return ""

    @staticmethod
    def get_uri_from_model_config(model_path: str) -> str:
        """Extract the URI from config.json in the specified model path.

        Args:
            model_path (str): Path to the model directory.

        Returns:
            str: URI extracted from the "_name_or_path" field in config.json.

        Raises:
            FileNotFoundError: If config.json is missing.
            ValueError: If "_name_or_path" is not found.
        """
        config_file = os.path.join(model_path, "config.json")

        if not os.path.exists(config_file):
            logger.error("config.json not found in model path.")
            return None

        with open(config_file, "r") as f:
            config_data = json.load(f)

        uri = config_data.get("_name_or_path")
        if not uri:
            logger.error("Unable to extract _name_or_path from config.json.")
            return None

        return uri

    @staticmethod
    def get_license_data(model_path: str) -> Tuple[str, str]:
        """Get the license data from the model path."""
        # Common license directories
        directories = [".", "docs", "legal", "LICENSE", "licenses"]

        # Common license files
        file_names = [
            "LICENSE",
            "LICENSE.txt",
            "LICENSE.md",
            "LICENSE.rst",
        ]

        for directory in directories:
            directory_path = model_path if directory == "." else os.path.join(model_path, directory)

            if not os.path.exists(directory_path):
                continue

            # Get list of files in directory (case-insensitive)
            dir_files = [f.lower() for f in os.listdir(directory_path)]

            for file_name in file_names:
                if file_name.lower() in dir_files:
                    # Get the actual filename with correct case
                    actual_filename = os.listdir(directory_path)[dir_files.index(file_name.lower())]
                    license_path = os.path.join(directory_path, actual_filename)

                    if os.path.isfile(license_path):
                        # exclude app_settings.model_download_dir from license path
                        license_relative_path = os.path.relpath(license_path, app_settings.model_download_dir)
                        with open(license_path, "r") as f:
                            return f.read(), license_relative_path

        return "", ""

    @staticmethod
    def get_license_info(model_path: str) -> Optional[Dict]:
        """Get the license info from the license data."""
        # Get license data
        license_data, license_path = LocalModelExtraction.get_license_data(model_path)

        if not license_data:
            return None

        # Get mapped licenses
        existing_licenses_mapper = mapped_licenses()

        license_details = generate_license_details(os.path.join(app_settings.model_download_dir, license_path))
        extracted_license = {}
        license_name = license_details.get("name", "")
        if license_name:
            # Check if license_name is in existing_licenses_mapper
            for mapped_license in existing_licenses_mapper:
                key_words = [mapped_license["license_id"]] + mapped_license["potential_names"]
                normalized_key_words = [normalize_license_identifier(keyword) for keyword in key_words]
                normalized_license_name = normalize_license_identifier(license_name)
                if any(keyword in normalized_license_name for keyword in normalized_key_words):
                    extracted_license["license_id"] = mapped_license["license_id"]
                    extracted_license["license_name"] = license_name
                    extracted_license["license_url"] = mapped_license["license_url"]
                    break
            else:
                extracted_license["license_id"] = "unknown"
                extracted_license["license_name"] = license_name
                extracted_license["license_url"] = license_path
        else:
            extracted_license["license_id"] = "unknown"
            extracted_license["license_name"] = "Unknown"
            extracted_license["license_url"] = license_path

        extracted_license["license_faqs"] = license_details.get("faqs", [])
        extracted_license["type"] = license_details.get("type", "")
        extracted_license["suitability"] = license_details.get("type_suitability", "")
        extracted_license["description"] = license_details.get("type_description", "")

        return extracted_license
