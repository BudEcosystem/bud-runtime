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

"""Disk I/O monitoring module for dynamic download throttling."""

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import psutil
from budmicroframe.commons import logging

from .throttle_detector import get_throttle_detector
from .volume_detector import StorageType, VolumeInfo, get_volume_detector


logger = logging.get_logger(__name__)


@dataclass
class IOMetrics:
    """Container for I/O metrics."""

    iowait_percent: float
    write_bytes_per_sec: float
    write_count_per_sec: float
    disk_usage_percent: float
    io_stress_level: float  # 0.0 (no stress) to 1.0 (high stress)

    # Volume-specific metrics
    volume_info: Optional[VolumeInfo] = None
    is_volume_specific: bool = False
    network_latency_ms: Optional[float] = None  # For network storage


class IOMonitor:
    """Monitor disk I/O performance and provide throttling recommendations."""

    def __init__(
        self,
        sample_interval: float = 1.0,  # seconds between samples
        enable_volume_specific: bool = True,  # Enable volume-specific monitoring
        enable_dynamic_throttling: bool = True,  # Use dynamic throttling detection
        # Legacy thresholds (kept for compatibility, not used with dynamic throttling)
        iowait_threshold: float = 30.0,  # % CPU waiting for I/O
        write_rate_threshold: float = 100 * 1024 * 1024,  # 100 MB/s
        disk_usage_threshold: float = 90.0,  # % disk usage
        network_latency_threshold: float = 100.0,  # ms for network storage
    ):
        """Initialize I/O monitor with dynamic throttling detection.

        Args:
            sample_interval: Time between metric samples in seconds
            enable_volume_specific: Enable volume-specific I/O monitoring
            enable_dynamic_throttling: Use dynamic throttling detection instead of static thresholds
            iowait_threshold: Legacy - Maximum acceptable iowait percentage
            write_rate_threshold: Legacy - Maximum acceptable write rate in bytes/sec
            disk_usage_threshold: Legacy - Maximum acceptable disk usage percentage
            network_latency_threshold: Legacy - Maximum acceptable network latency in ms
        """
        self.sample_interval = sample_interval
        self.enable_volume_specific = enable_volume_specific
        self.enable_dynamic_throttling = enable_dynamic_throttling

        # Legacy thresholds (for backward compatibility)
        self.iowait_threshold = iowait_threshold
        self.write_rate_threshold = write_rate_threshold
        self.disk_usage_threshold = disk_usage_threshold
        self.network_latency_threshold = network_latency_threshold

        # Volume detector for path analysis
        self.volume_detector = get_volume_detector()

        # Dynamic throttle detector
        self.throttle_detector = get_throttle_detector() if enable_dynamic_throttling else None

        # Cache for previous disk I/O counters (system-wide and per-device)
        self._last_disk_io: Optional[psutil._psutil_common.sdiskio] = None
        self._last_disk_io_time: Optional[float] = None
        self._last_device_io: Dict[str, Tuple[psutil._psutil_common.sdiskio, float]] = {}

        # Cache for volume information
        self._volume_cache: Dict[str, VolumeInfo] = {}

        # Cache for network I/O (for network storage monitoring)
        self._last_net_io: Optional[psutil._psutil_common.snetio] = None
        self._last_net_io_time: float = 0.0

    def get_volume_info(self, disk_path: str) -> VolumeInfo:
        """Get volume information for a path with caching."""
        if disk_path not in self._volume_cache:
            self._volume_cache[disk_path] = self.volume_detector.detect_volume(disk_path)
        return self._volume_cache[disk_path]

    def get_current_metrics(self, disk_path: str = "/") -> IOMetrics:
        """Get current I/O metrics for the system with volume-aware monitoring.

        Args:
            disk_path: Path to check disk usage for

        Returns:
            IOMetrics object with current system metrics
        """
        # Get volume information
        volume_info = self.get_volume_info(disk_path)

        # Choose monitoring strategy based on volume type and settings
        if self.enable_volume_specific and volume_info.storage_type != StorageType.UNKNOWN:
            try:
                return self._get_volume_specific_metrics(disk_path, volume_info)
            except Exception as e:
                logger.warning(f"Volume-specific monitoring failed for {disk_path}: {e}")
                # Fall back to system-wide monitoring

        # System-wide monitoring (fallback)
        return self._get_system_wide_metrics(disk_path, volume_info)

    def _get_volume_specific_metrics(self, disk_path: str, volume_info: VolumeInfo) -> IOMetrics:
        """Get I/O metrics specific to the volume containing the path."""
        current_time = time.time()

        # Handle different storage types
        if volume_info.storage_type == StorageType.NETWORK_FS:
            return self._get_network_storage_metrics(disk_path, volume_info, current_time)
        elif volume_info.device_name and volume_info.storage_type in {
            StorageType.LOCAL_DISK,
            StorageType.BLOCK_DEVICE,
        }:
            return self._get_device_specific_metrics(disk_path, volume_info, current_time)
        else:
            # Fall back to system-wide for other types
            return self._get_system_wide_metrics(disk_path, volume_info)

    def _get_device_specific_metrics(self, disk_path: str, volume_info: VolumeInfo, current_time: float) -> IOMetrics:
        """Get I/O metrics for a specific device."""
        device_name = volume_info.device_name

        try:
            # Get per-device I/O counters
            disk_io_devices = psutil.disk_io_counters(perdisk=True)

            if device_name not in disk_io_devices:
                logger.debug(f"Device {device_name} not found in I/O counters, using system-wide")
                return self._get_system_wide_metrics(disk_path, volume_info)

            device_io = disk_io_devices[device_name]

            # Calculate device-specific write rates
            write_bytes_per_sec = 0.0
            write_count_per_sec = 0.0

            if device_name in self._last_device_io:
                last_io, last_time = self._last_device_io[device_name]
                time_delta = current_time - last_time
                if time_delta > 0:
                    write_bytes_per_sec = (device_io.write_bytes - last_io.write_bytes) / time_delta
                    write_count_per_sec = (device_io.write_count - last_io.write_count) / time_delta

            # Cache current values
            if device_name:  # device_name should always be non-None here, but check for type safety
                self._last_device_io[device_name] = (device_io, current_time)

            # Get CPU iowait (still system-wide, but weighted by device activity)
            cpu_times = psutil.cpu_times_percent(interval=0.1)  # Shorter interval for device-specific
            iowait_percent = getattr(cpu_times, "iowait", 0.0)

            # Get disk usage for the specific path
            disk_usage = psutil.disk_usage(disk_path)
            disk_usage_percent = disk_usage.percent

            # Calculate stress level
            if self.enable_dynamic_throttling and self.throttle_detector:
                # Use dynamic throttling detection
                io_stress_level = self.throttle_detector.get_throttling_score(disk_path)
            else:
                # Legacy: Use static thresholds
                stress_factors = []

                # Adjust thresholds for high-performance storage
                write_threshold = self.write_rate_threshold
                if self.volume_detector.is_high_performance_storage(volume_info):
                    write_threshold *= 2  # Higher threshold for SSD/NVMe

                # Factor 1: iowait stress (system-wide, but consider device activity)
                device_activity_ratio = min(write_bytes_per_sec / max(write_threshold * 0.1, 1), 1.0)
                adjusted_iowait = iowait_percent * device_activity_ratio
                if self.iowait_threshold > 0:
                    stress_factors.append(min(adjusted_iowait / self.iowait_threshold, 1.0))

                # Factor 2: device write rate stress
                if write_threshold > 0:
                    stress_factors.append(min(write_bytes_per_sec / write_threshold, 1.0))

                # Factor 3: disk usage stress
                if self.disk_usage_threshold > 0:
                    stress_factors.append(min(disk_usage_percent / self.disk_usage_threshold, 1.0))

                # Use the maximum stress factor as overall stress level
                io_stress_level = max(stress_factors) if stress_factors else 0.0

            metrics = IOMetrics(
                iowait_percent=iowait_percent,
                write_bytes_per_sec=write_bytes_per_sec,
                write_count_per_sec=write_count_per_sec,
                disk_usage_percent=disk_usage_percent,
                io_stress_level=io_stress_level,
                volume_info=volume_info,
                is_volume_specific=True,
                network_latency_ms=None,
            )

            logger.debug(
                "Device-specific I/O Metrics [%s] - iowait: %.1f%%, write_rate: %.1f MB/s, "
                "disk_usage: %.1f%%, stress: %.2f",
                device_name,
                metrics.iowait_percent,
                metrics.write_bytes_per_sec / (1024 * 1024),
                metrics.disk_usage_percent,
                metrics.io_stress_level,
            )

            return metrics

        except Exception as e:
            logger.warning(f"Error getting device-specific metrics for {device_name}: {e}")
            return self._get_system_wide_metrics(disk_path, volume_info)

    def _get_network_storage_metrics(self, disk_path: str, volume_info: VolumeInfo, current_time: float) -> IOMetrics:
        """Get I/O metrics for network-attached storage."""
        try:
            # For network storage, monitor network I/O instead of disk I/O
            net_io = psutil.net_io_counters()

            # Calculate network write rates
            write_bytes_per_sec = 0.0
            write_count_per_sec = 0.0

            if self._last_net_io is not None and self._last_net_io_time > 0:
                time_delta = current_time - self._last_net_io_time
                if time_delta > 0:
                    write_bytes_per_sec = (net_io.bytes_sent - self._last_net_io.bytes_sent) / time_delta
                    write_count_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta

            # Cache current values
            self._last_net_io = net_io
            self._last_net_io_time = current_time

            # Measure network latency to storage (simplified)
            network_latency_ms = self._estimate_network_latency(volume_info)

            # Get disk usage
            disk_usage = psutil.disk_usage(disk_path)
            disk_usage_percent = disk_usage.percent

            # Calculate stress level for network storage
            if self.enable_dynamic_throttling and self.throttle_detector:
                # Use dynamic throttling detection (will handle network storage appropriately)
                io_stress_level = self.throttle_detector.get_throttling_score(disk_path)
            else:
                # Legacy: Calculate stress factors for network storage
                stress_factors = []

                # Factor 1: Network latency stress
                if network_latency_ms and self.network_latency_threshold > 0:
                    stress_factors.append(min(network_latency_ms / self.network_latency_threshold, 1.0))

                # Factor 2: Network write rate stress (using network threshold)
                network_threshold = self.write_rate_threshold * 0.5  # Network is typically slower
                if network_threshold > 0:
                    stress_factors.append(min(write_bytes_per_sec / network_threshold, 1.0))

                # Factor 3: Disk usage stress
                if self.disk_usage_threshold > 0:
                    stress_factors.append(min(disk_usage_percent / self.disk_usage_threshold, 1.0))

                # Use the maximum stress factor as overall stress level
                io_stress_level = max(stress_factors) if stress_factors else 0.0

            metrics = IOMetrics(
                iowait_percent=0.0,  # Not relevant for network storage
                write_bytes_per_sec=write_bytes_per_sec,
                write_count_per_sec=write_count_per_sec,
                disk_usage_percent=disk_usage_percent,
                io_stress_level=io_stress_level,
                volume_info=volume_info,
                is_volume_specific=True,
                network_latency_ms=network_latency_ms,
            )

            logger.debug(
                "Network storage I/O Metrics [%s] - latency: %.1fms, write_rate: %.1f MB/s, "
                "disk_usage: %.1f%%, stress: %.2f",
                volume_info.fstype,
                network_latency_ms or 0.0,
                metrics.write_bytes_per_sec / (1024 * 1024),
                metrics.disk_usage_percent,
                metrics.io_stress_level,
            )

            return metrics

        except Exception as e:
            logger.warning(f"Error getting network storage metrics: {e}")
            return self._get_system_wide_metrics(disk_path, volume_info)

    def _get_system_wide_metrics(self, disk_path: str, volume_info: VolumeInfo) -> IOMetrics:
        """Get system-wide I/O metrics (fallback method)."""
        # Get CPU times for iowait calculation
        cpu_times = psutil.cpu_times_percent(interval=self.sample_interval)
        iowait_percent = getattr(cpu_times, "iowait", 0.0)

        # Get disk I/O statistics
        disk_io = psutil.disk_io_counters()
        current_time = time.time()

        # Calculate write rate
        write_bytes_per_sec = 0.0
        write_count_per_sec = 0.0

        if self._last_disk_io is not None and self._last_disk_io_time is not None:
            time_delta = current_time - self._last_disk_io_time
            if time_delta > 0:
                write_bytes_per_sec = (disk_io.write_bytes - self._last_disk_io.write_bytes) / time_delta
                write_count_per_sec = (disk_io.write_count - self._last_disk_io.write_count) / time_delta

        self._last_disk_io = disk_io
        self._last_disk_io_time = current_time

        # Get disk usage
        disk_usage = psutil.disk_usage(disk_path)
        disk_usage_percent = disk_usage.percent

        # Calculate overall I/O stress level
        if self.enable_dynamic_throttling and self.throttle_detector:
            # Use dynamic throttling detection
            io_stress_level = self.throttle_detector.get_throttling_score(disk_path)
        else:
            # Legacy: Calculate stress factors
            stress_factors = []

            # Factor 1: iowait stress
            if self.iowait_threshold > 0:
                stress_factors.append(min(iowait_percent / self.iowait_threshold, 1.0))

            # Factor 2: write rate stress
            if self.write_rate_threshold > 0:
                stress_factors.append(min(write_bytes_per_sec / self.write_rate_threshold, 1.0))

            # Factor 3: disk usage stress
            if self.disk_usage_threshold > 0:
                stress_factors.append(min(disk_usage_percent / self.disk_usage_threshold, 1.0))

            # Use the maximum stress factor as overall stress level
            io_stress_level = max(stress_factors) if stress_factors else 0.0

        metrics = IOMetrics(
            iowait_percent=iowait_percent,
            write_bytes_per_sec=write_bytes_per_sec,
            write_count_per_sec=write_count_per_sec,
            disk_usage_percent=disk_usage_percent,
            io_stress_level=io_stress_level,
            volume_info=volume_info,
            is_volume_specific=False,
            network_latency_ms=None,
        )

        logger.debug(
            "System-wide I/O Metrics - iowait: %.1f%%, write_rate: %.1f MB/s, disk_usage: %.1f%%, stress: %.2f",
            metrics.iowait_percent,
            metrics.write_bytes_per_sec / (1024 * 1024),
            metrics.disk_usage_percent,
            metrics.io_stress_level,
        )

        return metrics

    def _estimate_network_latency(self, volume_info: VolumeInfo) -> Optional[float]:
        """Estimate network latency for network storage (simplified implementation)."""
        try:
            # This is a simplified implementation
            # In a real scenario, you might ping the storage server or measure actual I/O latency
            import re
            import subprocess

            # Try to extract server from device path (e.g., server:/path)
            device = volume_info.device
            if ":" in device:
                server = device.split(":")[0]

                # Simple ping test (not perfect but gives an indication)
                result = subprocess.run(
                    ["ping", "-c", "1", "-W", "1", server], capture_output=True, text=True, timeout=2
                )

                if result.returncode == 0:
                    # Extract latency from ping output
                    match = re.search(r"time=(\d+(?:\.\d+)?).*ms", result.stdout)
                    if match:
                        return float(match.group(1))

        except Exception as e:
            logger.debug(f"Failed to estimate network latency: {e}")

        return None

    def calculate_download_speed_limit(
        self,
        current_metrics: Optional[IOMetrics] = None,
        min_speed: int = 1 * 1024 * 1024,  # 1 MB/s minimum
        max_speed: int = 100 * 1024 * 1024,  # 100 MB/s maximum
        disk_path: str = "/",
    ) -> Tuple[int, float]:
        """Calculate recommended download speed based on I/O metrics.

        Args:
            current_metrics: Pre-calculated metrics (if None, will fetch current)
            min_speed: Minimum download speed in bytes/sec
            max_speed: Maximum download speed in bytes/sec
            disk_path: Path to check disk usage for

        Returns:
            Tuple of (recommended_speed_bytes_per_sec, stress_level)
        """
        if current_metrics is None:
            current_metrics = self.get_current_metrics(disk_path)

        stress_level = current_metrics.io_stress_level

        # If max_speed is 0 (unlimited) and stress is low, return unlimited
        if max_speed == 0 and stress_level < 0.1:
            recommended_speed = 0  # Unlimited
        elif self.enable_dynamic_throttling and self.throttle_detector:
            # Use dynamic throttling recommendations
            throttle_status = self.throttle_detector.detect_throttling(disk_path)

            # If max_speed is unlimited (0), only apply throttling when needed
            if max_speed == 0:
                if throttle_status.is_throttling:
                    # Apply throttling - use a reasonable max (e.g., 500 MB/s) for calculation
                    effective_max = 500 * 1024 * 1024
                    recommended_speed = int(min_speed + effective_max * throttle_status.recommended_speed_factor)
                else:
                    # No throttling needed - unlimited
                    recommended_speed = 0
            else:
                # Apply speed factor from throttle detector with configured max
                recommended_speed = int(min_speed + (max_speed - min_speed) * throttle_status.recommended_speed_factor)

            # Log detailed throttling info if throttling detected
            if throttle_status.is_throttling:
                logger.debug(
                    "Dynamic throttling: action=%s, speed_factor=%.2f, "
                    "latency_spike=%s, high_busy=%s, queue_congestion=%s",
                    throttle_status.recommended_action,
                    throttle_status.recommended_speed_factor,
                    throttle_status.latency_spike,
                    throttle_status.high_busy_time,
                    throttle_status.queue_congestion,
                )
        else:
            # Legacy: Calculate speed based on stress level
            # If max_speed is unlimited (0), handle it specially
            if max_speed == 0:
                if stress_level < 0.1:
                    # Very low stress - unlimited
                    recommended_speed = 0
                else:
                    # Apply throttling with a reasonable max (e.g., 500 MB/s)
                    effective_max = 500 * 1024 * 1024
                    if stress_level >= 0.9:
                        recommended_speed = min_speed
                    elif stress_level >= 0.7:
                        speed_factor = 1.0 - (stress_level - 0.7) * 3.0
                        recommended_speed = int(min_speed + effective_max * speed_factor * 0.2)
                    elif stress_level >= 0.5:
                        speed_factor = 1.0 - (stress_level - 0.5) * 2.0
                        recommended_speed = int(min_speed + effective_max * speed_factor * 0.5)
                    else:
                        speed_factor = 1.0 - stress_level
                        recommended_speed = int(min_speed + effective_max * speed_factor)
            else:
                # Use configured max_speed
                if stress_level >= 0.9:
                    recommended_speed = min_speed
                elif stress_level >= 0.7:
                    speed_factor = 1.0 - (stress_level - 0.7) * 3.0
                    recommended_speed = int(min_speed + (max_speed - min_speed) * speed_factor * 0.2)
                elif stress_level >= 0.5:
                    speed_factor = 1.0 - (stress_level - 0.5) * 2.0
                    recommended_speed = int(min_speed + (max_speed - min_speed) * speed_factor * 0.5)
                else:
                    speed_factor = 1.0 - stress_level
                    recommended_speed = int(min_speed + (max_speed - min_speed) * speed_factor)

        # Ensure speed is within bounds (only if max_speed is not unlimited)
        if max_speed > 0:
            recommended_speed = max(min_speed, min(max_speed, recommended_speed))
        elif recommended_speed > 0:
            # If we're throttling but max was unlimited, ensure at least min_speed
            recommended_speed = max(min_speed, recommended_speed)

        logger.debug(
            "Download speed recommendation: %s (stress: %.2f)",
            "Unlimited" if recommended_speed == 0 else f"{recommended_speed / (1024 * 1024):.1f} MB/s",
            stress_level,
        )

        return recommended_speed, stress_level

    def calculate_upload_speed_limit(
        self,
        current_metrics: Optional[IOMetrics] = None,
        min_speed: int = 5 * 1024 * 1024,  # 5 MB/s minimum
        max_speed: int = 0,  # 0 = unlimited (auto-detect)
        disk_path: str = "/",
    ) -> Tuple[int, float]:
        """Calculate recommended upload speed based on I/O metrics.

        Uses same logic as downloads but with upload-specific defaults.
        Adapts to any disk speed (SATA, NVMe, cloud) automatically.

        Args:
            current_metrics: Pre-calculated metrics (if None, will fetch current)
            min_speed: Minimum upload speed in bytes/sec (default 5 MB/s)
            max_speed: Maximum upload speed in bytes/sec (0 = unlimited, auto-detect)
            disk_path: Path to check disk usage for

        Returns:
            Tuple of (recommended_speed_bytes_per_sec, stress_level)
        """
        if current_metrics is None:
            current_metrics = self.get_current_metrics(disk_path)

        stress_level = current_metrics.io_stress_level

        # Auto-detect max speed from disk if unlimited
        # Use a reasonable baseline that will be throttled based on stress
        # This adapts to actual disk capacity
        effective_max = 500 * 1024 * 1024 if max_speed == 0 else max_speed

        # Use dynamic throttling if available
        if self.enable_dynamic_throttling and self.throttle_detector:
            throttle_status = self.throttle_detector.detect_throttling(disk_path)

            if throttle_status.is_throttling:
                # Apply throttling factor
                recommended_speed = int(
                    min_speed + (effective_max - min_speed) * throttle_status.recommended_speed_factor
                )
                logger.debug(
                    "Upload throttling: factor=%.2f, latency_spike=%s, high_busy=%s",
                    throttle_status.recommended_speed_factor,
                    throttle_status.latency_spike,
                    throttle_status.high_busy_time,
                )
            else:
                # No throttling needed
                recommended_speed = effective_max if max_speed > 0 else 0  # 0 = unlimited
        else:
            # Legacy: Calculate based on stress level
            if stress_level >= 0.9:
                # Critical stress - minimum speed
                recommended_speed = min_speed
            elif stress_level >= 0.7:
                # High stress - 20% of max
                speed_factor = 1.0 - (stress_level - 0.7) * 3.0
                recommended_speed = int(min_speed + (effective_max - min_speed) * speed_factor * 0.2)
            elif stress_level >= 0.5:
                # Medium stress - 50% of max
                speed_factor = 1.0 - (stress_level - 0.5) * 2.0
                recommended_speed = int(min_speed + (effective_max - min_speed) * speed_factor * 0.5)
            elif stress_level >= 0.3:
                # Low-medium stress - 75% of max
                speed_factor = 1.0 - (stress_level - 0.3) * 2.5
                recommended_speed = int(min_speed + (effective_max - min_speed) * speed_factor * 0.75)
            else:
                # Very low stress - full speed
                recommended_speed = effective_max if max_speed > 0 else 0  # 0 = unlimited

        # Ensure within bounds
        if max_speed > 0:
            recommended_speed = max(min_speed, min(max_speed, recommended_speed))
        elif recommended_speed > 0:
            recommended_speed = max(min_speed, recommended_speed)

        logger.debug(
            "Upload speed recommendation: %s (stress: %.2f)",
            "Unlimited" if recommended_speed == 0 else f"{recommended_speed / (1024 * 1024):.1f} MB/s",
            stress_level,
        )

        return recommended_speed, stress_level

    def should_pause_downloads(self, current_metrics: Optional[IOMetrics] = None, disk_path: str = "/") -> bool:
        """Determine if downloads should be paused due to extreme I/O stress.

        Args:
            current_metrics: Pre-calculated metrics (if None, will fetch current)
            disk_path: Path to check for throttling

        Returns:
            True if downloads should be paused, False otherwise
        """
        if self.enable_dynamic_throttling and self.throttle_detector:
            # Use dynamic throttling detection
            throttle_status = self.throttle_detector.detect_throttling(disk_path)
            should_pause = throttle_status.recommended_action == "pause"

            if should_pause:
                logger.warning(
                    "Dynamic throttling detected pause condition - severity=%.2f, latency=%.1fms, busy=%.1f%%",
                    throttle_status.throttling_severity,
                    throttle_status.current_latency_ms,
                    throttle_status.busy_percent,
                )

            return should_pause
        else:
            # Legacy: Use stress level threshold
            if current_metrics is None:
                current_metrics = self.get_current_metrics(disk_path)

            # Pause if stress level is critical (>= 0.95)
            should_pause = current_metrics.io_stress_level >= 0.95

            if should_pause:
                logger.warning(
                    "Critical I/O stress detected (%.2f) - downloads should be paused",
                    current_metrics.io_stress_level,
                )

            return should_pause

    def wait_for_io_recovery(
        self,
        target_stress_level: float = 0.5,
        max_wait_time: float = 60.0,
        check_interval: float = 2.0,
    ) -> bool:
        """Wait for I/O stress to decrease to acceptable levels.

        Args:
            target_stress_level: Target stress level to wait for (0.0 to 1.0)
            max_wait_time: Maximum time to wait in seconds
            check_interval: Time between checks in seconds

        Returns:
            True if stress decreased to target level, False if timeout
        """
        start_time = time.time()

        logger.info("Waiting for I/O stress to decrease to %.2f", target_stress_level)

        while time.time() - start_time < max_wait_time:
            metrics = self.get_current_metrics()

            if metrics.io_stress_level <= target_stress_level:
                logger.info(
                    "I/O stress decreased to acceptable level (%.2f)",
                    metrics.io_stress_level,
                )
                return True

            logger.debug(
                "Waiting for I/O recovery - current stress: %.2f, target: %.2f",
                metrics.io_stress_level,
                target_stress_level,
            )

            time.sleep(check_interval)

        logger.warning(
            "Timeout waiting for I/O recovery - current stress: %.2f",
            metrics.io_stress_level,
        )
        return False


# Singleton instance for global access
_io_monitor_instance: Optional[IOMonitor] = None


def get_io_monitor(**kwargs: Any) -> IOMonitor:
    """Get or create the global I/O monitor instance.

    Args:
        **kwargs: Arguments for IOMonitor constructor (used only on first call)

    Returns:
        Global IOMonitor instance
    """
    global _io_monitor_instance

    if _io_monitor_instance is None:
        # Import here to avoid circular imports
        from ..commons.config import app_settings

        # Use config defaults if not overridden
        kwargs.setdefault("enable_volume_specific", app_settings.enable_volume_specific_monitoring)
        kwargs.setdefault("enable_dynamic_throttling", getattr(app_settings, "enable_dynamic_throttling", True))

        # Legacy thresholds (for backward compatibility)
        kwargs.setdefault("iowait_threshold", app_settings.iowait_threshold)
        kwargs.setdefault("write_rate_threshold", app_settings.write_rate_threshold)
        kwargs.setdefault("disk_usage_threshold", app_settings.disk_usage_threshold)
        kwargs.setdefault("network_latency_threshold", app_settings.network_storage_latency_threshold)

        _io_monitor_instance = IOMonitor(**kwargs)

    return _io_monitor_instance
