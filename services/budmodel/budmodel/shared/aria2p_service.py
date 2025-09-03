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

"""This file contains the services for interact with an aria2c daemon process through JSON-RPC."""

import os
import time
from typing import List, Optional, Tuple

import aria2p
from aria2p.api import OptionsType
from aria2p.client import ClientException
from aria2p.downloads import Download
from budmicroframe.commons import logging

from ..commons.config import app_settings
from ..commons.exceptions import Aria2Exception
from .aria2_daemon import ensure_aria2_daemon_running, get_aria2_daemon_manager
from .io_monitor import get_io_monitor


logger = logging.get_logger(__name__)


class Aria2Downloader:
    def __init__(
        self,
        host: str = app_settings.Aria2p_host,
        port: int = app_settings.Aria2p_port,
        enable_io_monitoring: bool = True,
        io_check_interval: float = 5.0,
        min_speed: int = 1 * 1024 * 1024,  # 1 MB/s minimum
        max_speed: int = 0,  # 0 = unlimited (no cap)
    ):
        """Initialize Aria2 downloader.

        Args:
            host: Aria2 RPC host
            port: Aria2 RPC port
            enable_io_monitoring: Whether to enable I/O-based speed control
            io_check_interval: Interval in seconds to check I/O metrics
            min_speed: Minimum download speed in bytes/sec
            max_speed: Maximum download speed in bytes/sec (0 = unlimited)
        """
        # Get max speed from environment or use default (0 = unlimited)
        env_max_speed = os.getenv("ARIA2_MAX_SPEED_MBPS")
        if env_max_speed is not None:
            max_speed = int(env_max_speed) * 1024 * 1024 if int(env_max_speed) > 0 else 0

        # Get min speed from environment or use default
        env_min_speed = os.getenv("ARIA2_MIN_SPEED_MBPS")
        if env_min_speed is not None:
            min_speed = int(env_min_speed) * 1024 * 1024
        # Ensure daemon is running
        if not ensure_aria2_daemon_running():
            raise Aria2Exception("Failed to start aria2 daemon")

        # NOTE: Secret removed since helm does not support secrets
        # Handle both cases: with and without http:// prefix
        aria2_host = host if host.startswith("http") else f"http://{host}"
        self.aria2 = aria2p.API(aria2p.Client(host=aria2_host, port=port))

        # I/O monitoring settings
        self.enable_io_monitoring = enable_io_monitoring
        self.io_check_interval = io_check_interval
        self.min_speed = min_speed
        self.max_speed = max_speed

        logger.info(
            "Aria2 downloader initialized with speed limits - Min: %.1f MB/s, Max: %s",
            self.min_speed / (1024 * 1024),
            "Unlimited" if self.max_speed == 0 else f"{self.max_speed / (1024 * 1024):.1f} MB/s",
        )

        # Get I/O monitor and daemon manager instances
        self.io_monitor = get_io_monitor() if enable_io_monitoring else None
        self.daemon_manager = get_aria2_daemon_manager()

        # Track last speed adjustment time
        self._last_speed_adjustment = 0.0

    def download_from_any_url(self, url: str, options: Optional[OptionsType] = None) -> List[Download]:
        """Download from any URL.

        Args:
            url: Download URL
            options: Additional download options for aria2c
        """
        return self.aria2.add(url, options=options)

    def download_from_magnet(self, magnet: str, options: Optional[OptionsType] = None) -> Download:
        """Download from magnet link.

        Args:
            magnet: Magnet link
            options: Additional download options for aria2c
        """
        return self.aria2.add_magnet(magnet, options=options)

    def download_from_metalink_file_path(
        self, metalink_file_path: str, options: Optional[OptionsType] = None
    ) -> List[Download]:
        """Download from metalink file path.

        Args:
            metalink_file_path: Metalink file path
            options: Additional download options for aria2c
        """
        return self.aria2.add_metalink(metalink_file_path, options=options)

    def download_from_torrent_file_path(
        self, torrent_file_path: str, uris: Optional[list[str]] = None, options: Optional[OptionsType] = None
    ) -> Download:
        """Download from torrent file path.

        Args:
            torrent_file_path: Torrent file path
            uris: URIs to download from
            options: Additional download options for aria2c
        """
        return self.aria2.add_torrent(torrent_file_path, uris=uris, options=options)

    def download_from_urls(self, urls: list[str], options: Optional[OptionsType] = None) -> Download:
        """Add a new download.

        Args:
            urls: Download URLs
            options: Additional download options for aria2c

        Returns:
            Download GID
        """
        return self.aria2.add_uris(urls, options=options)

    def adjust_speed_based_on_io(self) -> Tuple[int, float]:
        """Adjust download speed based on current I/O metrics.

        Returns:
            Tuple of (new_speed_bytes_per_sec, stress_level)
        """
        if not self.enable_io_monitoring or not self.io_monitor:
            # If monitoring disabled, return max_speed (which could be 0 for unlimited)
            return self.max_speed, 0.0

        # Get current I/O metrics
        metrics = self.io_monitor.get_current_metrics(str(app_settings.model_download_dir))

        # Calculate recommended speed
        recommended_speed, stress_level = self.io_monitor.calculate_download_speed_limit(
            current_metrics=metrics,
            min_speed=self.min_speed,
            max_speed=self.max_speed,
            disk_path=str(app_settings.model_download_dir),
        )

        # Update global speed limit in aria2
        self.daemon_manager.update_global_speed_limit(recommended_speed)

        return recommended_speed, stress_level

    def should_pause_for_io(self) -> bool:
        """Check if downloads should be paused due to I/O stress.

        Returns:
            True if downloads should be paused
        """
        if not self.enable_io_monitoring or not self.io_monitor:
            return False

        # Check using the download directory path
        download_path = str(app_settings.model_download_dir)
        return self.io_monitor.should_pause_downloads(disk_path=download_path)

    def wait_for_io_recovery(self, target_stress: float = 0.5, max_wait: float = 60.0) -> bool:
        """Wait for I/O stress to recover.

        Args:
            target_stress: Target stress level to wait for
            max_wait: Maximum time to wait in seconds

        Returns:
            True if recovered, False if timeout
        """
        if not self.enable_io_monitoring or not self.io_monitor:
            return True

        return self.io_monitor.wait_for_io_recovery(
            target_stress_level=target_stress,
            max_wait_time=max_wait,
        )

    def listen_to_download(self, download: Download, timeout_seconds: int = 5) -> Download:
        """Listen to download events with I/O monitoring.

        Args:
            download: Download to listen to
            timeout_seconds: Timeout in seconds

        Returns:
            Download
        """
        last_io_check = time.time()

        while True:
            download.update()

            # download statuses are: active, waiting, paused, error, complete or removed.
            download_status = download.status

            if download_status == "complete":
                return download
            elif download_status == "error":
                logger.debug(f"Download failed: {download.error_message}")
                self.purge_download(download)
                raise Aria2Exception("Download failed")
            elif download_status == "removed":
                self.purge_download(download)
                raise Aria2Exception("Download removed")
            else:
                # Check and adjust I/O throttling
                current_time = time.time()
                if self.enable_io_monitoring and current_time - last_io_check >= self.io_check_interval:
                    # Check if we should pause
                    if self.should_pause_for_io():
                        logger.warning("Pausing download due to high I/O stress")
                        self.pause_download(download)

                        # Wait for recovery
                        if self.wait_for_io_recovery():
                            logger.info("I/O stress recovered, resuming download")
                            self.resume_download(download)
                        else:
                            logger.warning("I/O recovery timeout, resuming anyway")
                            self.resume_download(download)
                    else:
                        # Adjust speed based on I/O
                        new_speed, stress_level = self.adjust_speed_based_on_io()
                        logger.debug(
                            "Adjusted download speed to %.1f MB/s (stress: %.2f)",
                            new_speed / (1024 * 1024),
                            stress_level,
                        )

                    last_io_check = current_time

                # Log download progress
                logger.debug(f"Downloading {download.name}")
                logger.debug(f"Download status: {download_status}")
                logger.debug(f"Download total size: {download.total_length_string()}")
                logger.debug(f"Download completed size: {download.completed_length_string()}")
                logger.debug(f"Download progress: {download.progress_string()}")
                logger.debug(f"Download ETA: {download.eta_string()}")
                logger.debug(f"Download speed: {download.download_speed_string()}")
                logger.debug("================================================")

                time.sleep(timeout_seconds)

    def purge_download(self, download: Download) -> bool:
        """Purge all downloads.

        Args:
            force: Force purge
            remove_files: Remove files

        Returns:
            True if purge was successful, False otherwise
        """
        return self.aria2.purge()

    def pause_download(self, download: Download, force: bool = False) -> bool:
        """Pause a download.

        Args:
            download: Download to pause
            force: Force pause

        Returns:
            True if pause was successful, False otherwise
        """
        try:
            return download.pause(force=force)
        except ClientException as e:
            logger.error(f"Error pausing download: {e}")
            raise Aria2Exception("Error pausing download") from e

    def resume_download(self, download: Download) -> bool:
        """Resume a download.

        Args:
            download: Download to resume
            force: Force resume

        Returns:
            True if resume was successful, False otherwise
        """
        try:
            return download.resume()
        except ClientException as e:
            logger.error(f"Error resuming download: {e}")
            raise Aria2Exception("Error resuming download") from e

    def remove_download(self, download: Download, force: bool = False, remove_files: bool = False) -> bool:
        """Remove a download.

        Args:
            download: Download to remove
            force: Force remove
            remove_files: Remove files

        Returns:
            True if remove was successful, False otherwise
        """
        try:
            return download.remove(force=force, files=remove_files)
        except ClientException as e:
            logger.error(f"Error removing download: {e}")
            raise Aria2Exception("Error removing download") from e

    def move_files(self, download: Download, path: str) -> bool:
        """Move files.

        Args:
            download: Download to move
            path: Path to move files to
        """
        # Create directory if it doesn't exist
        os.makedirs(path, exist_ok=True)
        try:
            return download.move_files(path)
        except Exception as e:
            self.remove_download(download, force=True, remove_files=True)
            logger.error(f"Error saving files: {e}")
            raise Aria2Exception("Error saving files") from e


# Command to start aria2c
# aria2c --enable-rpc --rpc-listen-all --rpc-listen-port PORT --rpc-secret SECRET --dir DIR --max-concurrent-downloads INT(5)
