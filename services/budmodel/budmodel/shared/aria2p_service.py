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
from typing import List, Optional

import aria2p
from aria2p.api import OptionsType
from aria2p.client import ClientException
from aria2p.downloads import Download
from budmicroframe.commons import logging

from ..commons.config import app_settings
from ..commons.exceptions import Aria2Exception


logger = logging.get_logger(__name__)


class Aria2Downloader:
    def __init__(
        self,
        host: str = app_settings.Aria2p_host,
        port: int = app_settings.Aria2p_port,
    ):
        """Initialize Aria2 downloader.

        Args:
            host: Aria2 RPC host
            port: Aria2 RPC port
            secret: Aria2 RPC secret token
        """
        # NOTE: Secret removed since helm does not support secrets
        self.aria2 = aria2p.API(aria2p.Client(host=host, port=port))

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

    def listen_to_download(self, download: Download, timeout_seconds: int = 5) -> Download:
        """Listen to download events.

        Args:
            download: Download to listen to
            timeout_seconds: Timeout in seconds

        Returns:
            Download
        """
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
