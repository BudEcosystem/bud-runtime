"""Data schemas for node information collection."""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class NodeInfoCollectionStatus(str, Enum):
    """Status of node info collection."""

    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    IN_PROGRESS = "in_progress"


class GPUInfo(BaseModel):
    """GPU information from NFD labels."""

    nvidia_present: bool = False
    nvidia_gpus: int = 0
    gpu_product: str = ""
    gpu_memory: str = ""
    gpu_family: str = ""
    cuda_version: str = ""
    compute_capability: str = ""
    amd_present: bool = False
    intel_hpu_present: bool = False

    # Additional fields for detailed GPU info
    pci_vendor_id: Optional[str] = None
    pci_device_id: Optional[str] = None
    driver_version: Optional[str] = None


class CPUInfo(BaseModel):
    """CPU information from NFD labels."""

    architecture: str = ""
    cpu_family: str = ""
    cpu_model_id: str = ""
    cpu_model_raw: str = ""
    cpu_name: str = ""
    cpu_vendor: str = ""
    cores: int = 0
    threads: int = 0


class NodeInfo(BaseModel):
    """Information about a single node."""

    node_name: str
    node_id: str
    node_status: bool = False

    # Hardware information
    gpu_info: GPUInfo
    cpu_info: CPUInfo

    # Capacity and allocatable resources
    capacity: Dict[str, str] = Field(default_factory=dict)
    allocatable: Dict[str, str] = Field(default_factory=dict)

    # Network addresses
    addresses: List[Dict[str, str]] = Field(default_factory=list)

    # Labels (for debugging/reference)
    labels: Dict[str, str] = Field(default_factory=dict)

    # Devices (formatted for compatibility with existing code)
    devices: str = "{}"  # JSON string of device information


class ClusterNodeInfo(BaseModel):
    """Node information collection result for a cluster."""

    cluster_id: str
    cluster_name: str
    status: NodeInfoCollectionStatus
    node_count: int = 0
    nodes: List[NodeInfo] = Field(default_factory=list)
    error: Optional[str] = None
    collection_time: Optional[datetime] = None
    nfd_available: bool = False


class NodeInfoCollectionResult(BaseModel):
    """Result of collecting node info from multiple clusters."""

    total_clusters: int
    successful: int
    failed: int
    skipped: int
    cluster_results: List[ClusterNodeInfo] = Field(default_factory=list)
    collection_time: datetime = Field(default_factory=datetime.utcnow)
