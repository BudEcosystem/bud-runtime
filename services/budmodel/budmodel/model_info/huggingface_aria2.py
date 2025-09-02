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

"""HuggingFace download adapter using aria2 for I/O-aware throttling."""

import contextlib
import time
from pathlib import Path
from typing import Any, Dict, Optional

from aria2p.downloads import Download
from budmicroframe.commons import logging
from budmicroframe.shared.dapr_service import DaprService
from huggingface_hub import hf_hub_url

from ..commons.config import app_settings
from ..commons.exceptions import Aria2Exception
from ..shared.aria2p_service import Aria2Downloader


logger = logging.get_logger(__name__)


class HuggingFaceAria2Downloader:
    """Download HuggingFace models using aria2 with I/O monitoring."""

    def __init__(
        self,
        enable_io_monitoring: bool = True,
        io_check_interval: float = 5.0,
        min_speed: int = 1 * 1024 * 1024,  # 1 MB/s
        max_speed: int = 0,  # 0 = unlimited (no artificial cap)
    ):
        """Initialize HuggingFace aria2 downloader.

        Args:
            enable_io_monitoring: Enable I/O-based speed control
            io_check_interval: Interval to check I/O metrics
            min_speed: Minimum download speed in bytes/sec
            max_speed: Maximum download speed in bytes/sec (0 = unlimited)
        """
        self.aria2_downloader = Aria2Downloader(
            enable_io_monitoring=enable_io_monitoring,
            io_check_interval=io_check_interval,
            min_speed=min_speed,
            max_speed=max_speed,
        )
        self.dapr_service = DaprService()

    def download_file(
        self,
        repo_id: str,
        filename: str,
        local_dir: str,
        token: Optional[str] = None,
        revision: str = "main",
        workflow_id: Optional[str] = None,
    ) -> str:
        """Download a single file from HuggingFace using aria2.

        Args:
            repo_id: Repository ID (e.g., "meta-llama/Llama-3.3-70B-Instruct")
            filename: File to download (e.g., "model-00001-of-00061.safetensors")
            local_dir: Local directory to save the file
            token: HuggingFace API token for private repos
            revision: Git revision (branch/tag/commit)
            workflow_id: Workflow ID for progress tracking

        Returns:
            Path to the downloaded file
        """
        # Create the download URL
        url = hf_hub_url(repo_id=repo_id, filename=filename, revision=revision)

        # Add authentication header if token provided
        headers = []
        if token:
            headers.append(f"Authorization: Bearer {token}")

        # Prepare the local file path
        local_path = Path(local_dir) / filename
        local_path.parent.mkdir(parents=True, exist_ok=True)

        # Check if file already exists and is complete
        if local_path.exists():
            logger.debug(f"File already exists: {local_path}")
            # Could add size verification here if needed
            return str(local_path)

        # Prepare aria2 options
        aria2_options = {
            "dir": str(local_path.parent),
            "out": local_path.name,
            "header": headers,
            "allow-overwrite": "true",
            "auto-file-renaming": "false",
            "continue": "true",
            "max-tries": "5",
            "retry-wait": "10",
            "timeout": "600",
            "connect-timeout": "60",
            "check-integrity": "true",
        }

        try:
            logger.info(f"Downloading {filename} from {repo_id} using aria2")

            # Start the download
            downloads = self.aria2_downloader.download_from_any_url(url, aria2_options)
            if not downloads:
                raise Aria2Exception(f"Failed to start download for {filename}")

            download = downloads[0]

            # Monitor the download with I/O throttling
            download = self._monitor_download(download, filename, workflow_id)

            # Verify the file exists after download
            if not local_path.exists():
                raise Aria2Exception(f"File not found after download: {local_path}")

            logger.info(f"Successfully downloaded {filename} to {local_path}")
            return str(local_path)

        except Exception as e:
            logger.error(f"Failed to download {filename}: {str(e)}")
            # Clean up partial download if exists
            if local_path.exists():
                with contextlib.suppress(Exception):
                    local_path.unlink()
            raise

    def _monitor_download(
        self,
        download: Download,
        filename: str,
        workflow_id: Optional[str] = None,
    ) -> Download:
        """Monitor download with I/O throttling and progress updates.

        Args:
            download: Aria2 download object
            filename: Name of the file being downloaded
            workflow_id: Workflow ID for progress tracking

        Returns:
            Completed download object
        """
        last_progress_update = time.time()
        progress_update_interval = 5.0  # Update progress every 5 seconds

        while True:
            download.update()
            status = download.status

            if status == "complete":
                logger.debug(f"Download completed: {filename}")
                return download
            elif status == "error":
                error_msg = download.error_message or "Unknown error"
                logger.error(f"Download failed for {filename}: {error_msg}")
                self.aria2_downloader.purge_download(download)
                raise Aria2Exception(f"Download failed: {error_msg}")
            elif status == "removed":
                logger.error(f"Download was removed: {filename}")
                raise Aria2Exception("Download was removed")
            else:
                # Update progress in state store for workflow tracking
                current_time = time.time()
                if workflow_id and current_time - last_progress_update >= progress_update_interval:
                    self._update_workflow_progress(
                        workflow_id,
                        filename,
                        download,
                    )
                    last_progress_update = current_time

                # I/O monitoring and throttling is handled by the enhanced listen_to_download
                # But we'll do a simplified version here for single file
                if self.aria2_downloader.enable_io_monitoring:
                    # Check if we should pause due to I/O stress
                    if self.aria2_downloader.should_pause_for_io():
                        logger.warning(f"Pausing download of {filename} due to high I/O stress")
                        self.aria2_downloader.pause_download(download)

                        # Wait for recovery
                        if self.aria2_downloader.wait_for_io_recovery():
                            logger.info(f"I/O stress recovered, resuming download of {filename}")
                            self.aria2_downloader.resume_download(download)
                    else:
                        # Adjust speed based on I/O metrics
                        new_speed, stress_level = self.aria2_downloader.adjust_speed_based_on_io()
                        if stress_level > 0.5:
                            logger.debug(
                                f"Throttling {filename} to %.1f MB/s (I/O stress: %.2f)",
                                new_speed / (1024 * 1024),
                                stress_level,
                            )

                # Log progress periodically
                if download.total_length > 0:
                    progress = download.completed_length / download.total_length * 100
                    logger.debug(
                        f"Downloading {filename}: {progress:.1f}% "
                        f"({download.completed_length_string()}/{download.total_length_string()}) "
                        f"Speed: {download.download_speed_string()} "
                        f"ETA: {download.eta_string()}"
                    )

                time.sleep(2)  # Check every 2 seconds

    def _update_workflow_progress(
        self,
        workflow_id: str,
        filename: str,
        download: Download,
    ) -> None:
        """Update workflow progress in state store.

        Args:
            workflow_id: Workflow ID
            filename: Current file being downloaded
            download: Aria2 download object
        """
        try:
            state_store_key = f"eta_{workflow_id}"
            eta_ttl = 86400  # 24 hours

            # Get existing state
            if app_settings.statestore_name:
                response = self.dapr_service.get_state(
                    store_name=app_settings.statestore_name,
                    key=state_store_key,
                )
                state_data: Dict[str, Any] = response.json()

                # Update download progress
                if "steps_data" not in state_data:
                    state_data["steps_data"] = {}
                if "model_download" not in state_data["steps_data"]:
                    state_data["steps_data"]["model_download"] = {}

                state_data["steps_data"]["model_download"].update(
                    {
                        "current_file_name": filename,
                        "current_file_size": download.total_length,
                        "current_file_progress": download.progress,
                        "download_speed": download.download_speed,
                        "eta_seconds": download.eta.total_seconds() if download.eta else 0,
                        "using_aria2": True,
                        "io_monitoring_enabled": self.aria2_downloader.enable_io_monitoring,
                    }
                )

                # Save updated state
                self.dapr_service.save_to_statestore(
                    store_name=app_settings.statestore_name,
                    key=state_store_key,
                    value=state_data,
                    ttl=eta_ttl,
                )
        except Exception as e:
            logger.debug(f"Failed to update workflow progress: {str(e)}")

    def download_files(
        self,
        repo_id: str,
        filenames: list[str],
        local_dir: str,
        token: Optional[str] = None,
        revision: str = "main",
        workflow_id: Optional[str] = None,
        max_parallel: int = 3,  # Conservative parallel downloads
    ) -> list[str]:
        """Download multiple files from HuggingFace using aria2.

        Args:
            repo_id: Repository ID
            filenames: List of files to download
            local_dir: Local directory to save files
            token: HuggingFace API token
            revision: Git revision
            workflow_id: Workflow ID for progress tracking
            max_parallel: Maximum parallel downloads (limited for I/O)

        Returns:
            List of downloaded file paths
        """
        downloaded_files = []

        # Download files with limited parallelism to avoid I/O overload
        # For now, we'll do sequential downloads for maximum I/O control
        # This can be enhanced later for smart parallel downloads
        for i, filename in enumerate(filenames, 1):
            logger.info(f"Downloading file {i}/{len(filenames)}: {filename}")

            try:
                file_path = self.download_file(
                    repo_id=repo_id,
                    filename=filename,
                    local_dir=local_dir,
                    token=token,
                    revision=revision,
                    workflow_id=workflow_id,
                )
                downloaded_files.append(file_path)
            except Exception as e:
                logger.error(f"Failed to download {filename}: {str(e)}")
                # Clean up any partial downloads
                for downloaded in downloaded_files:
                    with contextlib.suppress(Exception):
                        Path(downloaded).unlink()
                raise

        return downloaded_files
