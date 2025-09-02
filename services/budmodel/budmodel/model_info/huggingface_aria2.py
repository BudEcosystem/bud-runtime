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

import asyncio
import contextlib
import hashlib
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

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

    # Allowed domains for downloads
    ALLOWED_DOMAINS = {
        "huggingface.co",
        "cdn-lfs.huggingface.co",
        "cdn-lfs-us.huggingface.co",
        "huggingface.ai",
        "hf.co",
    }

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

    @staticmethod
    def _calculate_file_checksum(file_path: Path, algorithm: str = "sha256") -> str:
        """Calculate checksum of a file.

        Args:
            file_path: Path to the file
            algorithm: Hash algorithm to use (sha256, sha1, md5)

        Returns:
            Hex digest of the file
        """
        hash_func = getattr(hashlib, algorithm)()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hash_func.update(chunk)
        return hash_func.hexdigest()

    def _verify_file_integrity(
        self, file_path: Path, expected_checksum: Optional[str] = None, expected_size: Optional[int] = None
    ) -> Tuple[bool, str]:
        """Verify file integrity using checksum and/or size.

        Args:
            file_path: Path to the downloaded file
            expected_checksum: Expected checksum (if available)
            expected_size: Expected file size in bytes (if available)

        Returns:
            Tuple of (is_valid, message)
        """
        if not file_path.exists():
            return False, f"File does not exist: {file_path}"

        # Check file size if expected size is provided
        if expected_size is not None:
            actual_size = file_path.stat().st_size
            if actual_size != expected_size:
                return False, f"Size mismatch: expected {expected_size}, got {actual_size}"
            logger.debug(f"File size verified: {actual_size} bytes")

        # Check checksum if provided
        if expected_checksum:
            # Determine algorithm from checksum length
            checksum_len = len(expected_checksum)
            if checksum_len == 64:
                algorithm = "sha256"
            elif checksum_len == 40:
                algorithm = "sha1"
            elif checksum_len == 32:
                algorithm = "md5"
            else:
                logger.warning(f"Unknown checksum format (length {checksum_len}), skipping verification")
                return True, "Checksum format unknown, skipped verification"

            logger.debug(f"Calculating {algorithm} checksum for {file_path.name}")
            actual_checksum = self._calculate_file_checksum(file_path, algorithm)

            if actual_checksum.lower() != expected_checksum.lower():
                return False, f"Checksum mismatch: expected {expected_checksum}, got {actual_checksum}"
            logger.debug(f"Checksum verified: {actual_checksum}")

        return True, "File integrity verified"

    @staticmethod
    def _sanitize_for_logging(text: str) -> str:
        """Remove sensitive information like tokens from text for logging.

        Args:
            text: Text that may contain sensitive information

        Returns:
            Sanitized text safe for logging
        """
        # Remove Bearer tokens
        text = re.sub(r"Bearer\s+[\w\-\.]+", "Bearer [REDACTED]", text)
        # Remove potential API keys (common patterns)
        text = re.sub(
            r"(?:api[_\-]?key|token|secret|password)[\s=:]+[\w\-\.]+", "[REDACTED]", text, flags=re.IGNORECASE
        )
        # Remove hf_ prefixed tokens
        text = re.sub(r"hf_[\w]+", "hf_[REDACTED]", text)
        return text

    def _validate_url(self, url: str) -> bool:
        """Validate that URL is from an allowed domain.

        Args:
            url: URL to validate

        Returns:
            True if URL is from allowed domain

        Raises:
            Aria2Exception: If URL is not from allowed domain
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()

            # Remove port if present
            if ":" in domain:
                domain = domain.split(":")[0]

            # Check if domain is in allowed list
            if not any(domain.endswith(allowed) for allowed in self.ALLOWED_DOMAINS):
                raise Aria2Exception(
                    f"URL domain '{domain}' is not in allowed domains. "
                    f"Allowed domains: {', '.join(self.ALLOWED_DOMAINS)}"
                )
            return True
        except Exception as e:
            raise Aria2Exception(f"Invalid URL '{self._sanitize_for_logging(url)}': {e}") from e

    def download_file(
        self,
        repo_id: str,
        filename: str,
        local_dir: str,
        token: Optional[str] = None,
        revision: str = "main",
        workflow_id: Optional[str] = None,
        expected_checksum: Optional[str] = None,
        expected_size: Optional[int] = None,
    ) -> str:
        """Download a single file from HuggingFace using aria2.

        Args:
            repo_id: Repository ID (e.g., "meta-llama/Llama-3.3-70B-Instruct")
            filename: File to download (e.g., "model-00001-of-00061.safetensors")
            local_dir: Local directory to save the file
            token: HuggingFace API token for private repos
            revision: Git revision (branch/tag/commit)
            workflow_id: Workflow ID for progress tracking
            expected_checksum: Optional expected checksum for verification
            expected_size: Optional expected file size for verification

        Returns:
            Path to the downloaded file
        """
        # Create the download URL
        url = hf_hub_url(repo_id=repo_id, filename=filename, revision=revision)

        # Validate URL before proceeding
        self._validate_url(url)

        # Add authentication header if token provided (don't log the actual token)
        headers = []
        if token:
            headers.append(f"Authorization: Bearer {token}")
            logger.debug(f"Using authentication token for {self._sanitize_for_logging(repo_id)}")

        # Prepare the local file path
        local_path = Path(local_dir) / filename
        local_path.parent.mkdir(parents=True, exist_ok=True)

        # Check if file already exists and is complete
        if local_path.exists():
            logger.debug(f"File already exists: {local_path}")
            # Could add size verification here if needed
            return str(local_path)

        # Prepare aria2 options (sanitize headers for logging)
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
            logger.info(f"Downloading {filename} from {self._sanitize_for_logging(repo_id)} using aria2")

            # Start the download (URL already validated)
            downloads = self.aria2_downloader.download_from_any_url(url, aria2_options)
            if not downloads:
                raise Aria2Exception(f"Failed to start download for {filename}")

            download = downloads[0]

            # Monitor the download with I/O throttling
            download = self._monitor_download(download, filename, workflow_id)

            # Verify the file exists after download
            if not local_path.exists():
                raise Aria2Exception(f"File not found after download: {local_path}")

            # Verify file integrity if checksums or expected size provided
            if expected_checksum or expected_size:
                is_valid, message = self._verify_file_integrity(local_path, expected_checksum, expected_size)
                if not is_valid:
                    logger.error(f"File integrity check failed: {message}")
                    # Clean up corrupted file
                    with contextlib.suppress(Exception):
                        local_path.unlink()
                    raise Aria2Exception(f"File integrity verification failed: {message}")
                logger.info(f"File integrity verified: {message}")

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

    async def _monitor_download_async(
        self,
        download: Download,
        filename: str,
        workflow_id: Optional[str] = None,
    ) -> Download:
        """Async version: Monitor download with I/O throttling and progress updates.

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
                    await self._update_workflow_progress_async(
                        workflow_id,
                        filename,
                        download,
                    )
                    last_progress_update = current_time

                # I/O monitoring and throttling with async
                if self.aria2_downloader.enable_io_monitoring:
                    # Check if we should pause due to I/O stress
                    if await self._should_pause_for_io_async():
                        logger.warning(f"Pausing download of {filename} due to high I/O stress")
                        self.aria2_downloader.pause_download(download)

                        # Wait for recovery
                        if await self._wait_for_io_recovery_async():
                            logger.info(f"I/O stress recovered, resuming download of {filename}")
                            self.aria2_downloader.resume_download(download)
                    else:
                        # Adjust speed based on I/O metrics
                        new_speed, stress_level = await self._adjust_speed_based_on_io_async()
                        if stress_level > 0.5:
                            logger.debug(
                                f"Throttling {filename} to %.1f MB/s (I/O stress: %.2f)",
                                new_speed / (1024 * 1024),
                                stress_level,
                            )

                # Log progress periodically
                if download.total_length > 0:
                    progress = (download.completed_length / download.total_length) * 100
                    logger.debug(
                        f"Download progress for {filename}: {progress:.1f}% "
                        f"Speed: {download.download_speed_string()} "
                        f"ETA: {download.eta_string()}"
                    )

                await asyncio.sleep(2)  # Check every 2 seconds

    async def _should_pause_for_io_async(self) -> bool:
        """Async check if download should be paused for I/O stress."""
        return await asyncio.get_event_loop().run_in_executor(None, self.aria2_downloader.should_pause_for_io)

    async def _wait_for_io_recovery_async(self) -> bool:
        """Async wait for I/O stress to recover."""
        return await asyncio.get_event_loop().run_in_executor(None, self.aria2_downloader.wait_for_io_recovery)

    async def _adjust_speed_based_on_io_async(self):
        """Async adjust download speed based on I/O metrics."""
        return await asyncio.get_event_loop().run_in_executor(None, self.aria2_downloader.adjust_speed_based_on_io)

    async def _update_workflow_progress_async(
        self,
        workflow_id: str,
        filename: str,
        download: Download,
    ) -> None:
        """Async update workflow progress in state store.

        Args:
            workflow_id: Workflow ID
            filename: Current file being downloaded
            download: Aria2 download object
        """
        # Run the sync version in executor to avoid blocking
        await asyncio.get_event_loop().run_in_executor(
            None, self._update_workflow_progress, workflow_id, filename, download
        )

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
