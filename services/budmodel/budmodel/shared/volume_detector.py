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

"""Volume detection and storage type identification for accurate I/O monitoring."""

import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

import psutil
from budmicroframe.commons import logging


logger = logging.get_logger(__name__)


class StorageType(Enum):
    """Types of storage systems."""

    LOCAL_DISK = "local_disk"  # Local HDD/SSD
    BLOCK_DEVICE = "block_device"  # Attached block storage (EBS, Azure Disk)
    NETWORK_FS = "network_fs"  # Network filesystems (NFS, CIFS, etc.)
    TMPFS = "tmpfs"  # In-memory filesystem
    OVERLAY = "overlay"  # Container overlay filesystem
    UNKNOWN = "unknown"  # Unable to determine


@dataclass
class VolumeInfo:
    """Information about a storage volume."""

    path: str
    device: str
    mountpoint: str
    fstype: str
    storage_type: StorageType
    is_remote: bool
    device_name: Optional[str] = None  # For device-specific I/O monitoring

    def __str__(self) -> str:
        """Return string representation of VolumeInfo."""
        return f"VolumeInfo(path={self.path}, device={self.device}, type={self.storage_type.value}, remote={self.is_remote})"


class VolumeDetector:
    """Detects volume information and storage types for paths."""

    # Network filesystem types
    NETWORK_FS_TYPES = {
        "nfs",
        "nfs4",
        "cifs",
        "smb",
        "smb2",
        "smbfs",
        "fuse.sshfs",
        "fuse.s3fs",
        "fuse.gcsfuse",
        "afs",
        "glusterfs",
        "lustre",
    }

    # In-memory filesystem types
    MEMORY_FS_TYPES = {"tmpfs", "ramfs", "devtmpfs"}

    # Container/overlay filesystem types
    OVERLAY_FS_TYPES = {"overlay", "aufs", "devicemapper", "zfs"}

    # Block device patterns (common cloud storage)
    BLOCK_DEVICE_PATTERNS = {
        "/dev/nvme",  # AWS EBS NVMe
        "/dev/xvd",  # AWS EBS Xen
        "/dev/sd",  # Azure/GCP persistent disks
        "/dev/vd",  # Virtio block devices
        "/dev/loop",  # Loop devices
    }

    def __init__(self) -> None:
        """Initialize volume detector."""
        self._partition_cache: Optional[Dict[str, Any]] = None
        self._cache_time = 0.0
        self.cache_ttl = 30.0  # Cache partitions for 30 seconds

    def _get_disk_partitions(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Get disk partitions with caching."""
        import time

        current_time = time.time()

        if self._partition_cache is None or current_time - self._cache_time > self.cache_ttl or force_refresh:
            try:
                partitions = psutil.disk_partitions(all=True)
                self._partition_cache = {p.mountpoint: p for p in partitions}
                self._cache_time = current_time
                logger.debug(f"Refreshed partition cache with {len(partitions)} partitions")
            except Exception as e:
                logger.warning(f"Failed to get disk partitions: {e}")
                if self._partition_cache is None:
                    self._partition_cache = {}

        return self._partition_cache

    def detect_volume(self, path: str) -> VolumeInfo:
        """Detect volume information for a given path.

        Args:
            path: Path to analyze

        Returns:
            VolumeInfo object with detected storage information
        """
        try:
            # Resolve path to absolute path
            abs_path = os.path.abspath(path)

            # Find the partition that contains this path
            partition = self._find_partition_for_path(abs_path)
            if not partition:
                return self._create_unknown_volume_info(abs_path)

            # Determine storage type
            storage_type = self._classify_storage_type(partition)
            is_remote = storage_type == StorageType.NETWORK_FS

            # Get device name for I/O monitoring
            device_name = self._get_device_name(partition)

            volume_info = VolumeInfo(
                path=abs_path,
                device=partition.device,
                mountpoint=partition.mountpoint,
                fstype=partition.fstype,
                storage_type=storage_type,
                is_remote=is_remote,
                device_name=device_name,
            )

            logger.debug(f"Detected volume: {volume_info}")
            return volume_info

        except Exception as e:
            logger.warning(f"Error detecting volume for {path}: {e}")
            return self._create_unknown_volume_info(path)

    def _find_partition_for_path(self, path: str) -> Optional[Any]:
        """Find the partition that contains the given path."""
        partitions = self._get_disk_partitions()

        # Find the longest matching mountpoint
        best_match = None
        best_match_len = 0

        for mountpoint, partition in partitions.items():
            # Check if path starts with this mountpoint
            if path.startswith(mountpoint) and len(mountpoint) > best_match_len:
                best_match = partition
                best_match_len = len(mountpoint)

        return best_match

    def _classify_storage_type(self, partition: Any) -> StorageType:
        """Classify the storage type based on filesystem and device information."""
        fstype = partition.fstype.lower()
        device = partition.device.lower()

        # Check for network filesystems
        if fstype in self.NETWORK_FS_TYPES:
            return StorageType.NETWORK_FS

        # Check for memory filesystems
        if fstype in self.MEMORY_FS_TYPES:
            return StorageType.TMPFS

        # Check for overlay/container filesystems
        if fstype in self.OVERLAY_FS_TYPES:
            return StorageType.OVERLAY

        # Check for block devices (cloud storage patterns)
        for pattern in self.BLOCK_DEVICE_PATTERNS:
            if device.startswith(pattern):
                return StorageType.BLOCK_DEVICE

        # Check if it's a regular disk device
        if device.startswith("/dev/sd") or device.startswith("/dev/hd"):
            return StorageType.LOCAL_DISK

        # Default to local disk for standard filesystem types
        if fstype in {"ext4", "ext3", "ext2", "xfs", "btrfs", "ntfs", "vfat"}:
            return StorageType.LOCAL_DISK

        return StorageType.UNKNOWN

    def _get_device_name(self, partition: Any) -> Optional[str]:
        """Extract device name for I/O monitoring."""
        device = partition.device

        # Handle different device naming patterns
        if device.startswith("/dev/"):
            device_name = device[5:]  # Remove '/dev/' prefix

            # Handle partition numbers (e.g., sda1 -> sda, nvme0n1p1 -> nvme0n1)
            if device_name.endswith("p1") or device_name.endswith("p2"):
                # NVMe style partitions (nvme0n1p1)
                device_name = device_name[:-2]
            elif device_name[-1].isdigit() and device_name[-2].isalpha():
                # Traditional partitions (sda1, xvdf1)
                device_name = device_name[:-1]

            return str(device_name)

        return None

    def _create_unknown_volume_info(self, path: str) -> VolumeInfo:
        """Create a VolumeInfo for unknown/error cases."""
        return VolumeInfo(
            path=path,
            device="unknown",
            mountpoint="/",
            fstype="unknown",
            storage_type=StorageType.UNKNOWN,
            is_remote=False,
            device_name=None,
        )

    def get_available_devices(self) -> Dict[str, Dict[str, str]]:
        """Get all available devices for I/O monitoring.

        Returns:
            Dictionary mapping device names to their info
        """
        try:
            devices = {}

            # Get per-disk I/O counters to see available devices
            disk_io = psutil.disk_io_counters(perdisk=True)
            partitions = self._get_disk_partitions()

            for device_name, io_counters in disk_io.items():
                # Find corresponding partition info
                device_path = f"/dev/{device_name}"
                partition_info = None

                for partition in partitions.values():
                    if partition.device.startswith(device_path):
                        partition_info = partition
                        break

                devices[device_name] = {
                    "device_path": device_path,
                    "mountpoint": partition_info.mountpoint if partition_info else "unknown",
                    "fstype": partition_info.fstype if partition_info else "unknown",
                    "read_bytes": io_counters.read_bytes,
                    "write_bytes": io_counters.write_bytes,
                    "read_count": io_counters.read_count,
                    "write_count": io_counters.write_count,
                }

            return devices

        except Exception as e:
            logger.warning(f"Failed to get available devices: {e}")
            return {}

    def is_high_performance_storage(self, volume_info: VolumeInfo) -> bool:
        """Determine if the storage is high-performance (SSD, NVMe, etc.)."""
        device = volume_info.device.lower()

        # NVMe devices are typically high performance
        if "nvme" in device:
            return True

        # Check for SSD indicators in device name
        if any(pattern in device for pattern in ["ssd", "nvme", "flash"]):
            return True

        # Block devices in cloud environments are often high performance
        return volume_info.storage_type == StorageType.BLOCK_DEVICE


# Global instance for caching
_volume_detector_instance: Optional[VolumeDetector] = None


def get_volume_detector() -> VolumeDetector:
    """Get or create the global volume detector instance."""
    global _volume_detector_instance

    if _volume_detector_instance is None:
        _volume_detector_instance = VolumeDetector()

    return _volume_detector_instance
