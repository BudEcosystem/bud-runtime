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

"""Dynamic disk throttling detection based on real-time performance indicators."""

import os
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Deque, Dict, Optional

import numpy as np
import psutil
from budmicroframe.commons import logging


logger = logging.get_logger(__name__)


@dataclass
class ThrottlingStatus:
    """Current throttling status with detailed metrics."""

    is_throttling: bool
    throttling_severity: float  # 0.0 (none) to 1.0 (severe)

    # Individual indicators
    latency_spike: bool
    high_busy_time: bool
    queue_congestion: bool
    write_stalls: bool

    # Metrics
    current_latency_ms: float
    baseline_latency_ms: float
    busy_percent: float
    in_flight_io: int
    max_queue_depth: int

    # Recommendations
    recommended_action: str  # "continue", "reduce_speed", "pause"
    recommended_speed_factor: float  # 0.0 to 1.0 multiplier for max speed


@dataclass
class DeviceMetrics:
    """Metrics for a specific storage device."""

    device_name: str
    timestamp: float

    # From psutil
    write_count: int
    write_bytes: int
    write_time: int  # milliseconds
    busy_time: int  # milliseconds

    # Calculated
    avg_write_latency_ms: float
    write_rate_mbps: float
    busy_percent: float

    # From /sys/block/*/stat
    in_flight_io: int = 0


class ThrottleDetector:
    """Detect actual disk throttling using real-time performance indicators."""

    def __init__(
        self,
        history_window: int = 60,  # Keep 60 seconds of history
        sample_interval: float = 1.0,  # Sample every second
        latency_spike_threshold: float = 2.0,  # 2x baseline = spike
        busy_time_threshold: float = 80.0,  # 80% busy
        busy_time_duration: float = 3.0,  # Sustained for 3 seconds
        queue_congestion_factor: float = 0.5,  # 50% of max queue
    ):
        """Initialize throttle detector.

        Args:
            history_window: Seconds of history to maintain
            sample_interval: Seconds between metric samples
            latency_spike_threshold: Multiplier for baseline latency to detect spikes
            busy_time_threshold: Disk busy percentage threshold
            busy_time_duration: Duration busy time must be sustained
            queue_congestion_factor: Factor of max queue depth for congestion
        """
        self.history_window = history_window
        self.sample_interval = sample_interval
        self.latency_spike_threshold = latency_spike_threshold
        self.busy_time_threshold = busy_time_threshold
        self.busy_time_duration = busy_time_duration
        self.queue_congestion_factor = queue_congestion_factor

        # History tracking per device
        self._device_history: Dict[str, Deque[DeviceMetrics]] = {}
        self._last_sample_time: Dict[str, float] = {}
        self._last_io_counters: Dict[str, Any] = {}

        # Baseline latency tracking
        self._baseline_latency: Dict[str, float] = {}
        self._baseline_update_time: Dict[str, float] = {}

    def get_device_for_path(self, path: str) -> Optional[str]:
        """Get the device name for a given path.

        Args:
            path: File system path

        Returns:
            Device name (e.g., "sdb") or None
        """
        try:
            # Get mount point for the path
            path_obj = Path(path).resolve()
            partitions = psutil.disk_partitions(all=True)

            # Find the partition containing this path
            best_match = None
            best_match_len = 0

            for partition in partitions:
                mountpoint = partition.mountpoint
                if str(path_obj).startswith(mountpoint) and len(mountpoint) > best_match_len:
                    best_match = partition
                    best_match_len = len(mountpoint)

            if best_match:
                # Extract device name (e.g., /dev/sdb1 -> sdb)
                device = best_match.device
                if device.startswith("/dev/"):
                    device = device[5:]  # Remove /dev/
                    # Remove partition number
                    import re

                    device = re.sub(r"\d+$", "", device)
                    return str(device)

        except Exception as e:
            logger.debug(f"Error getting device for path {path}: {e}")

        return None

    def _get_in_flight_io(self, device: str) -> int:
        """Get current in-flight I/O requests from /sys/block/*/stat.

        Args:
            device: Device name (e.g., "sdb")

        Returns:
            Number of in-flight I/O requests
        """
        try:
            stat_path = f"/sys/block/{device}/stat"
            if os.path.exists(stat_path):
                with open(stat_path, "r") as f:
                    fields = f.read().strip().split()
                    # Field 9 (index 8) is in-flight I/O
                    return int(fields[8]) if len(fields) > 8 else 0
        except Exception as e:
            logger.debug(f"Error reading in-flight I/O for {device}: {e}")

        return 0

    def _get_max_queue_depth(self, device: str) -> int:
        """Get maximum queue depth for device.

        Args:
            device: Device name

        Returns:
            Maximum queue depth
        """
        try:
            queue_path = f"/sys/block/{device}/queue/nr_requests"
            if os.path.exists(queue_path):
                with open(queue_path, "r") as f:
                    return int(f.read().strip())
        except Exception as e:
            logger.debug(f"Error reading queue depth for {device}: {e}")

        # Default queue depth
        return 128

    def collect_device_metrics(self, device: str) -> Optional[DeviceMetrics]:
        """Collect current metrics for a device.

        Args:
            device: Device name (e.g., "sdb")

        Returns:
            DeviceMetrics or None if collection failed
        """
        try:
            current_time = time.time()

            # Get per-device I/O counters
            disk_io_counters = psutil.disk_io_counters(perdisk=True)
            if device not in disk_io_counters:
                return None

            current_io = disk_io_counters[device]

            # Calculate rates if we have previous data
            avg_latency = 0.0
            write_rate = 0.0
            busy_percent = 0.0

            if device in self._last_io_counters and device in self._last_sample_time:
                prev_io = self._last_io_counters[device]
                time_delta = current_time - self._last_sample_time[device]

                if time_delta > 0:
                    # Calculate write rate
                    write_bytes_delta = current_io.write_bytes - prev_io.write_bytes
                    write_rate = (write_bytes_delta / (1024 * 1024)) / time_delta  # MB/s

                    # Calculate average write latency
                    write_count_delta = current_io.write_count - prev_io.write_count
                    write_time_delta = current_io.write_time - prev_io.write_time

                    if write_count_delta > 0:
                        avg_latency = write_time_delta / write_count_delta

                    # Calculate busy percentage
                    if hasattr(current_io, "busy_time") and hasattr(prev_io, "busy_time"):
                        busy_time_delta = current_io.busy_time - prev_io.busy_time
                        busy_percent = (busy_time_delta / (time_delta * 1000)) * 100  # Convert to percentage

            # Store current values for next calculation
            self._last_io_counters[device] = current_io
            self._last_sample_time[device] = current_time

            # Get in-flight I/O
            in_flight = self._get_in_flight_io(device)

            metrics = DeviceMetrics(
                device_name=device,
                timestamp=current_time,
                write_count=current_io.write_count,
                write_bytes=current_io.write_bytes,
                write_time=current_io.write_time,
                busy_time=getattr(current_io, "busy_time", 0),
                avg_write_latency_ms=avg_latency,
                write_rate_mbps=write_rate,
                busy_percent=min(busy_percent, 100.0),  # Cap at 100%
                in_flight_io=in_flight,
            )

            # Update history
            if device not in self._device_history:
                self._device_history[device] = deque(maxlen=self.history_window)
            self._device_history[device].append(metrics)

            # Update baseline latency during low activity
            if write_rate < 10.0 and busy_percent < 20.0:  # Low activity
                self._update_baseline_latency(device, avg_latency)

            return metrics

        except Exception as e:
            logger.error(f"Error collecting metrics for device {device}: {e}")
            return None

    def _update_baseline_latency(self, device: str, latency: float) -> None:
        """Update baseline latency for a device during low activity.

        Args:
            device: Device name
            latency: Current latency in milliseconds
        """
        current_time = time.time()

        # Only update if latency is valid and not too frequent
        if latency > 0 and (
            device not in self._baseline_update_time or current_time - self._baseline_update_time[device] > 10.0
        ):
            if device not in self._baseline_latency:
                self._baseline_latency[device] = latency
            else:
                # Exponential moving average
                self._baseline_latency[device] = 0.9 * self._baseline_latency[device] + 0.1 * latency

            self._baseline_update_time[device] = current_time
            logger.debug(f"Updated baseline latency for {device}: {self._baseline_latency[device]:.2f}ms")

    def _detect_latency_spike(self, device: str, current_latency: float) -> bool:
        """Detect if there's a latency spike.

        Args:
            device: Device name
            current_latency: Current latency in milliseconds

        Returns:
            True if latency spike detected
        """
        if device not in self._baseline_latency or current_latency <= 0:
            return False

        baseline = self._baseline_latency[device]
        if baseline <= 0:
            return False

        return current_latency > baseline * self.latency_spike_threshold

    def _detect_high_busy_time(self, device: str) -> bool:
        """Detect sustained high busy time.

        Args:
            device: Device name

        Returns:
            True if sustained high busy time detected
        """
        if device not in self._device_history:
            return False

        history = self._device_history[device]
        if len(history) < self.busy_time_duration:
            return False

        # Check last N seconds - optimized with numpy
        recent_samples = list(history)[-int(self.busy_time_duration) :]
        busy_percentages = np.array([m.busy_percent for m in recent_samples])
        high_busy_count = np.sum(busy_percentages > self.busy_time_threshold)

        return high_busy_count >= len(recent_samples) * 0.8  # 80% of samples

    def _detect_queue_congestion(self, device: str, in_flight: int) -> bool:
        """Detect I/O queue congestion.

        Args:
            device: Device name
            in_flight: Current in-flight I/O count

        Returns:
            True if queue is congested
        """
        max_queue = self._get_max_queue_depth(device)
        return in_flight > max_queue * self.queue_congestion_factor

    def _detect_write_stalls(self, device: str) -> bool:
        """Detect write stalls (latency increasing faster than throughput).

        Args:
            device: Device name

        Returns:
            True if write stalls detected
        """
        if device not in self._device_history:
            return False

        history = list(self._device_history[device])
        if len(history) < 5:
            return False

        # Compare recent vs older samples - optimized with numpy
        recent = history[-3:]
        older = history[-6:-3]

        recent_latencies = np.array([m.avg_write_latency_ms for m in recent])
        older_latencies = np.array([m.avg_write_latency_ms for m in older])

        recent_rates = np.array([m.write_rate_mbps for m in recent])
        older_rates = np.array([m.write_rate_mbps for m in older])

        recent_avg_latency = np.mean(recent_latencies)
        older_avg_latency = np.mean(older_latencies)

        recent_avg_rate = np.mean(recent_rates)
        older_avg_rate = np.mean(older_rates)

        # Stall if latency increased significantly but throughput didn't
        if older_avg_latency > 0 and older_avg_rate > 0:
            latency_increase = recent_avg_latency / older_avg_latency
            rate_increase = recent_avg_rate / older_avg_rate if older_avg_rate > 0 else 1.0

            # Stall if latency increased >50% but throughput increased <20%
            return latency_increase > 1.5 and rate_increase < 1.2

        return False

    def detect_throttling(self, path: str) -> ThrottlingStatus:
        """Detect if disk is currently throttling for the given path.

        Args:
            path: File system path to check

        Returns:
            ThrottlingStatus with detailed information
        """
        # Get device for path
        device = self.get_device_for_path(path)
        if not device:
            # Can't detect throttling without device info
            return ThrottlingStatus(
                is_throttling=False,
                throttling_severity=0.0,
                latency_spike=False,
                high_busy_time=False,
                queue_congestion=False,
                write_stalls=False,
                current_latency_ms=0.0,
                baseline_latency_ms=0.0,
                busy_percent=0.0,
                in_flight_io=0,
                max_queue_depth=128,
                recommended_action="continue",
                recommended_speed_factor=1.0,
            )

        # Collect current metrics
        metrics = self.collect_device_metrics(device)
        if not metrics:
            return ThrottlingStatus(
                is_throttling=False,
                throttling_severity=0.0,
                latency_spike=False,
                high_busy_time=False,
                queue_congestion=False,
                write_stalls=False,
                current_latency_ms=0.0,
                baseline_latency_ms=0.0,
                busy_percent=0.0,
                in_flight_io=0,
                max_queue_depth=128,
                recommended_action="continue",
                recommended_speed_factor=1.0,
            )

        # Detect individual throttling indicators
        latency_spike = self._detect_latency_spike(device, metrics.avg_write_latency_ms)
        high_busy_time = self._detect_high_busy_time(device)
        queue_congestion = self._detect_queue_congestion(device, metrics.in_flight_io)
        write_stalls = self._detect_write_stalls(device)

        # Calculate throttling severity (0.0 to 1.0)
        severity_scores = []

        if latency_spike:
            # Weight latency spikes heavily
            baseline = self._baseline_latency.get(device, 1.0)
            if baseline > 0:
                spike_ratio = metrics.avg_write_latency_ms / baseline
                severity_scores.append(min(spike_ratio / 5.0, 1.0) * 0.4)  # 40% weight
        else:
            severity_scores.append(0.0)

        if high_busy_time:
            # High busy time is significant
            severity_scores.append(min(metrics.busy_percent / 100.0, 1.0) * 0.3)  # 30% weight
        else:
            severity_scores.append(0.0)

        if queue_congestion:
            # Queue congestion indicates pressure
            max_queue = self._get_max_queue_depth(device)
            severity_scores.append(min(metrics.in_flight_io / max_queue, 1.0) * 0.2)  # 20% weight
        else:
            severity_scores.append(0.0)

        if write_stalls:
            # Write stalls are concerning
            severity_scores.append(0.1)  # 10% weight

        # Calculate overall severity
        throttling_severity = sum(severity_scores)
        is_throttling = throttling_severity > 0.1  # Any significant indicator

        # Determine recommended action
        if throttling_severity >= 0.7:
            recommended_action = "pause"
            recommended_speed_factor = 0.0
        elif throttling_severity >= 0.5:
            recommended_action = "reduce_speed"
            recommended_speed_factor = 0.3  # 30% of max speed
        elif throttling_severity >= 0.3:
            recommended_action = "reduce_speed"
            recommended_speed_factor = 0.5  # 50% of max speed
        elif throttling_severity >= 0.1:
            recommended_action = "reduce_speed"
            recommended_speed_factor = 0.7  # 70% of max speed
        else:
            recommended_action = "continue"
            recommended_speed_factor = 1.0  # Full speed

        status = ThrottlingStatus(
            is_throttling=is_throttling,
            throttling_severity=throttling_severity,
            latency_spike=latency_spike,
            high_busy_time=high_busy_time,
            queue_congestion=queue_congestion,
            write_stalls=write_stalls,
            current_latency_ms=metrics.avg_write_latency_ms,
            baseline_latency_ms=self._baseline_latency.get(device, 0.0),
            busy_percent=metrics.busy_percent,
            in_flight_io=metrics.in_flight_io,
            max_queue_depth=self._get_max_queue_depth(device),
            recommended_action=recommended_action,
            recommended_speed_factor=recommended_speed_factor,
        )

        # Log significant throttling
        if is_throttling:
            logger.info(
                f"Throttling detected on {device}: severity={throttling_severity:.2f}, "
                f"latency={metrics.avg_write_latency_ms:.1f}ms, busy={metrics.busy_percent:.1f}%, "
                f"queue={metrics.in_flight_io}/{self._get_max_queue_depth(device)}, "
                f"action={recommended_action}"
            )

        return status

    def get_throttling_score(self, path: str) -> float:
        """Get a simple throttling score (0.0 to 1.0) for the path.

        Args:
            path: File system path

        Returns:
            Throttling score from 0.0 (no throttling) to 1.0 (severe throttling)
        """
        status = self.detect_throttling(path)
        return status.throttling_severity


# Singleton instance
_throttle_detector: Optional[ThrottleDetector] = None


def get_throttle_detector() -> ThrottleDetector:
    """Get or create the global throttle detector instance.

    Returns:
        Global ThrottleDetector instance
    """
    global _throttle_detector

    if _throttle_detector is None:
        _throttle_detector = ThrottleDetector()

    return _throttle_detector
