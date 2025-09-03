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

"""Aria2 daemon management for the application."""

import os
import socket
import subprocess
import time
from typing import Any, Dict, Optional

import aria2p
from budmicroframe.commons import logging

from ..commons.config import app_settings


logger = logging.get_logger(__name__)


class Aria2DaemonManager:
    """Manages the aria2c daemon lifecycle."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6800,
        download_dir: Optional[str] = None,
        max_concurrent_downloads: int = 5,
        max_connection_per_server: int = 10,
        split: int = 10,
        min_split_size: str = "10M",
        max_overall_download_limit: str = "50M",  # Conservative 50MB/s initial limit
        max_download_limit: str = "50M",  # Per-download limit
        continue_downloads: bool = True,
        auto_file_renaming: bool = True,
        disk_cache: str = "64M",
    ):
        """Initialize aria2 daemon manager.

        Args:
            host: RPC host
            port: RPC port
            download_dir: Default download directory
            max_concurrent_downloads: Maximum concurrent downloads
            max_connection_per_server: Maximum connections per server
            split: Number of parallel connections for each download
            min_split_size: Minimum size to split files
            max_overall_download_limit: Global download speed limit
            max_download_limit: Per-download speed limit
            continue_downloads: Whether to continue partial downloads
            auto_file_renaming: Whether to auto-rename files on conflict
            disk_cache: Disk cache size for downloads
        """
        self.host = host
        self.port = port
        self.download_dir = download_dir or app_settings.model_download_dir
        self.max_concurrent_downloads = max_concurrent_downloads
        self.max_connection_per_server = max_connection_per_server
        self.split = split
        self.min_split_size = min_split_size
        self.max_overall_download_limit = max_overall_download_limit
        self.max_download_limit = max_download_limit
        self.continue_downloads = continue_downloads
        self.auto_file_renaming = auto_file_renaming
        self.disk_cache = disk_cache

        self._process: Optional[subprocess.Popen[bytes]] = None

    def is_daemon_running(self) -> bool:
        """Check if aria2 daemon is already running.

        Returns:
            True if daemon is accessible, False otherwise
        """
        try:
            # Try to connect to the daemon
            # Handle both cases: with and without http:// prefix
            host = self.host if self.host.startswith("http") else f"http://{self.host}"
            client = aria2p.Client(host=host, port=self.port)
            api = aria2p.API(client)
            # Try to get global stats to verify connection
            api.get_stats()
            logger.debug("Aria2 daemon already running")
            return True
        except Exception:
            return False

    def _is_port_available(self) -> bool:
        """Check if the RPC port is available.

        Returns:
            True if port is available, False if in use
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((self.host, self.port))
                return True
            except OSError:
                return False

    def start_daemon(self, force_restart: bool = False) -> bool:
        """Start the aria2c daemon if not already running.

        Args:
            force_restart: Force restart even if already running

        Returns:
            True if daemon was started or already running, False on error
        """
        # Check if already running
        if not force_restart and self.is_daemon_running():
            logger.info("Aria2 daemon already running on %s:%d", self.host, self.port)
            return True

        # Stop existing process if force restart
        if force_restart:
            self.stop_daemon()

        # Check port availability
        if not self._is_port_available():
            logger.error("Port %d is already in use", self.port)
            return False

        # Ensure download directory exists
        os.makedirs(self.download_dir, exist_ok=True)

        # Build aria2c command
        cmd = [
            "aria2c",
            "--enable-rpc",
            f"--rpc-listen-port={self.port}",
            "--rpc-listen-all=false",  # Only listen on localhost for security
            f"--dir={self.download_dir}",
            f"--max-concurrent-downloads={self.max_concurrent_downloads}",
            f"--max-connection-per-server={self.max_connection_per_server}",
            f"--split={self.split}",
            f"--min-split-size={self.min_split_size}",
            f"--max-overall-download-limit={self.max_overall_download_limit}",
            # f"--max-download-limit={self.max_download_limit}",
            f"--disk-cache={self.disk_cache}",
            "--file-allocation=falloc",  # Faster file allocation
            "--log-level=warn",  # Reduce log verbosity
            "--console-log-level=warn",
            f"--auto-file-renaming={'true' if self.auto_file_renaming else 'false'}",
            f"--continue={'true' if self.continue_downloads else 'false'}",
            "--allow-overwrite=true",
            "--always-resume=true",
            "--max-resume-failure-tries=5",
            "--max-file-not-found=5",
            "--max-tries=5",
            "--retry-wait=10",
            "--timeout=600",  # 10 minute timeout
            "--connect-timeout=60",
            "--piece-length=1M",  # 1MB pieces for better progress tracking
            "--check-integrity=true",  # Verify downloads
            "--realtime-chunk-checksum=true",  # Verify chunks in realtime
        ]

        try:
            # Start daemon in background
            logger.info("Starting aria2c daemon with command: %s", " ".join(cmd))
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,  # Detach from parent process
            )

            # Wait for daemon to start
            max_wait = 10  # seconds
            start_time = time.time()

            while time.time() - start_time < max_wait:
                if self.is_daemon_running():
                    logger.info("Aria2 daemon started successfully on %s:%d", self.host, self.port)
                    return True
                time.sleep(0.5)

            logger.error("Aria2 daemon failed to start within %d seconds", max_wait)
            self.stop_daemon()
            return False

        except FileNotFoundError:
            logger.error("aria2c not found. Please ensure aria2 is installed.")
            return False
        except Exception as e:
            logger.error("Failed to start aria2 daemon: %s", str(e))
            return False

    def stop_daemon(self) -> bool:
        """Stop the aria2c daemon.

        Returns:
            True if daemon was stopped, False otherwise
        """
        stopped = False

        # Try to shutdown via RPC first
        if self.is_daemon_running():
            try:
                client = aria2p.Client(host=f"http://{self.host}", port=self.port)
                api = aria2p.API(client)
                api.shutdown()  # type: ignore[attr-defined]
                stopped = True
                logger.info("Aria2 daemon shutdown via RPC")
            except Exception as e:
                logger.warning("Failed to shutdown via RPC: %s", str(e))

        # Kill the process if we started it
        if self._process and self._process.poll() is None:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
                stopped = True
                logger.info("Aria2 daemon process terminated")
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait()
                stopped = True
                logger.warning("Aria2 daemon process killed forcefully")
            except Exception as e:
                logger.error("Failed to stop daemon process: %s", str(e))

        self._process = None
        return stopped

    def restart_daemon(self) -> bool:
        """Restart the aria2c daemon.

        Returns:
            True if daemon was restarted successfully, False otherwise
        """
        logger.info("Restarting aria2 daemon")
        self.stop_daemon()
        time.sleep(1)  # Brief pause before restart
        return self.start_daemon()

    def update_global_speed_limit(self, speed_bytes_per_sec: int) -> bool:
        """Update the global download speed limit.

        Args:
            speed_bytes_per_sec: Speed limit in bytes per second (0 = unlimited)

        Returns:
            True if limit was updated, False otherwise
        """
        try:
            # Handle both cases: with and without http:// prefix
            host = self.host if self.host.startswith("http") else f"http://{self.host}"
            client = aria2p.Client(host=host, port=self.port)
            api = aria2p.API(client)

            # Handle unlimited speed (0 means no limit in aria2)
            if speed_bytes_per_sec == 0:
                speed_str = "0"  # aria2 interprets "0" as unlimited
                logger.debug("Setting download speed to unlimited")
            else:
                # Convert to string with unit (aria2 expects format like "50M" or "1024K")
                if speed_bytes_per_sec >= 1024 * 1024:
                    speed_str = f"{speed_bytes_per_sec // (1024 * 1024)}M"
                else:
                    speed_str = f"{speed_bytes_per_sec // 1024}K"

            # Update global option
            api.set_global_options({"max-overall-download-limit": speed_str})

            logger.debug("Updated global download speed limit to %s", "unlimited" if speed_str == "0" else speed_str)
            return True
        except Exception as e:
            logger.error("Failed to update speed limit: %s", str(e))
            return False

    def get_global_stats(self) -> Optional[Dict[str, Any]]:
        """Get global statistics from aria2 daemon.

        Returns:
            Dictionary with global stats or None if daemon not running
        """
        try:
            client = aria2p.Client(host=f"http://{self.host}", port=self.port)
            api = aria2p.API(client)
            stats = api.get_global_stat()  # type: ignore[attr-defined]
            return dict(stats)
        except Exception as e:
            logger.error("Failed to get global stats: %s", str(e))
            return None

    def __enter__(self) -> "Aria2DaemonManager":
        """Context manager entry - start daemon."""
        self.start_daemon()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit - stop daemon."""
        self.stop_daemon()


# Global instance
_daemon_manager: Optional[Aria2DaemonManager] = None


def get_aria2_daemon_manager(**kwargs: Any) -> Aria2DaemonManager:
    """Get or create the global aria2 daemon manager.

    Args:
        **kwargs: Arguments for Aria2DaemonManager constructor (used only on first call)

    Returns:
        Global Aria2DaemonManager instance
    """
    global _daemon_manager

    if _daemon_manager is None:
        # Use settings from config
        kwargs.setdefault("host", app_settings.Aria2p_host.replace("http://", ""))
        kwargs.setdefault("port", app_settings.Aria2p_port)
        kwargs.setdefault("download_dir", str(app_settings.model_download_dir))

        _daemon_manager = Aria2DaemonManager(**kwargs)

    return _daemon_manager


def ensure_aria2_daemon_running() -> bool:
    """Ensure aria2 daemon is running, starting it if necessary.

    Returns:
        True if daemon is running, False otherwise
    """
    manager = get_aria2_daemon_manager()
    return manager.start_daemon()
