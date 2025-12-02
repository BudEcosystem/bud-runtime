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


"""Implements core services and business logic that power the microservices, including key functionality and integrations."""

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Union
from uuid import UUID

from budmicroframe.commons.constants import WorkflowStatus
from budmicroframe.commons.logging import get_logger
from budmicroframe.commons.schemas import (
    ErrorResponse,
    NotificationCategory,
    NotificationContent,
    NotificationPayload,
    NotificationRequest,
    NotificationType,
    SuccessResponse,
    WorkflowMetadataResponse,
)
from budmicroframe.shared.dapr_service import DaprService, DaprServiceCrypto
from budmicroframe.shared.dapr_workflow import DaprWorkflow

# from ..commons.database import SessionLocal
from budmicroframe.shared.psql_service import DBSession
from fastapi import BackgroundTasks, HTTPException, status

from ..commons.base_crud import SessionMixin
from ..commons.config import app_settings
from ..commons.constants import ClusterPlatformEnum, ClusterStatusEnum
from ..commons.utils import (
    get_workflow_data_from_statestore,
    save_workflow_status_in_statestore,
)
from . import (
    delete_cluster,
    determine_cluster_platform,
    get_node_info,
    get_node_wise_events,
    get_node_wise_events_count,
    initial_setup,
    verify_cluster_connection,
)
from .crud import ClusterDataManager, ClusterNodeInfoDataManager
from .device_extractor import DeviceExtractor
from .models import Cluster as ClusterModel
from .models import ClusterNodeInfo as ClusterNodeInfoModel
from .nfd_handler import NFDSchedulableResourceDetector
from .schemas import (
    ClusterCreate,
    ClusterCreateRequest,
    ClusterDeleteRequest,
    ClusterNodeInfo,
    ClusterNodeInfoResponse,
    ClusterStatusUpdate,
    ConfigureCluster,
    FetchClusterInfo,
    NodeEventsCountSuccessResponse,
    NodeEventsResponse,
    VerifyClusterConnection,
)


logger = get_logger(__name__)


class ClusterOpsService:
    @classmethod
    async def determine_cluster_platform(cls, config_dict: Dict[str, Any], task_id: str, workflow_id: str):
        """Determine the cluster platform."""
        logger.info(f"Determining cluster platform for workflow_id: {workflow_id} and task_id: {task_id}")
        return await determine_cluster_platform(config_dict)

    @classmethod
    async def verify_cluster_connection(
        cls, verify_cluster_connection_request: VerifyClusterConnection, task_id: str, workflow_id: str
    ):
        """Verify cluster connection."""
        logger.info(f"Verifying cluster connection for workflow_id: {workflow_id} and task_id: {task_id}")
        cluster_config = verify_cluster_connection_request.config_dict
        platform = verify_cluster_connection_request.platform
        return await verify_cluster_connection(cluster_config, platform)

    @classmethod
    async def configure_cluster(cls, configure_cluster_request: ConfigureCluster, task_id: str, workflow_id: str):
        """Configure cluster."""
        logger.info(f"Configuring cluster for workflow_id: {workflow_id} and task_id: {task_id}")
        platform = configure_cluster_request.platform
        hostname = configure_cluster_request.hostname
        enable_master_node = configure_cluster_request.enable_master_node
        ingress_url = configure_cluster_request.ingress_url
        server_url = configure_cluster_request.server_url
        # Encrypt configuration
        with DaprServiceCrypto() as dapr_service:
            configuration_encrypted = dapr_service.encrypt_data(json.dumps(configure_cluster_request.config_dict))
            logger.info("Encrypted cluster configuration file")

        # Create cluster
        cluster_data = ClusterCreate(
            platform=platform,
            configuration=configuration_encrypted,
            host=hostname,
            status=ClusterStatusEnum.REGISTERING,
            enable_master_node=enable_master_node,
            ingress_url=ingress_url,
            server_url=server_url,
        )
        cluster_model = ClusterModel(**cluster_data.model_dump())
        with DBSession() as session:
            db_cluster = await ClusterDataManager(session).create_cluster(cluster_model)
            cluster_id = db_cluster.id
        # Pass The Cluster ID to the next step
        status = await initial_setup(configure_cluster_request.config_dict, cluster_id, platform)
        with DBSession() as session:
            db_cluster = await ClusterDataManager(session).retrieve_cluster_by_fields({"id": cluster_id})
            if status != "successful":
                # Mark as failed instead of deleting, so duplicate check can clean it up
                await ClusterDataManager(session).update_cluster_by_fields(
                    db_cluster, {"status": ClusterStatusEnum.NOT_AVAILABLE}
                )
                cluster_id = None
            else:
                await ClusterDataManager(session).update_cluster_by_fields(
                    db_cluster, {"status": ClusterStatusEnum.AVAILABLE}
                )
        return status, cluster_id

    @classmethod
    async def fetch_cluster_info(cls, fetch_cluster_info_request: FetchClusterInfo, task_id: str, workflow_id: str):
        """Fetch cluster info."""
        logger.info(f"Fetching cluster info for workflow_id: {workflow_id} and task_id: {task_id}")
        try:
            cluster_name = fetch_cluster_info_request.name
            # cluster_config = fetch_cluster_info_request.config_dict
            platform = fetch_cluster_info_request.platform
            # hostname = fetch_cluster_info_request.hostname
            # enable_master_node = fetch_cluster_info_request.enable_master_node
            # ingress_url = fetch_cluster_info_request.ingress_url
            # server_url = fetch_cluster_info_request.server_url
            cluster_id = fetch_cluster_info_request.cluster_id

            node_info = await get_node_info(fetch_cluster_info_request.config_dict, platform)
            logger.info(f"Node info: {node_info}")

            cluster_status = any(node["node_status"] for node in node_info)

            with DBSession() as session:
                db_cluster = await ClusterDataManager(session).retrieve_cluster_by_fields({"id": cluster_id})
                await ClusterDataManager(session).update_cluster_by_fields(
                    db_cluster,
                    {"status": ClusterStatusEnum.AVAILABLE if cluster_status else ClusterStatusEnum.NOT_AVAILABLE},
                )

            # Capture is_master for each node before DB operations (not stored in DB, passed to state store)
            node_is_master_map = {node["node_name"]: node.get("is_master", False) for node in node_info}

            node_objects = []
            for node in node_info:
                devices_data = json.loads(node.get("devices", "{}"))

                # Extract and format devices with proper structure for budsim and llm-memory-calculator
                formatted_devices = []
                device_type = "cpu"  # Default to CPU

                if isinstance(devices_data, dict):
                    # Process GPUs
                    for gpu in devices_data.get("gpus", []):
                        # Determine GPU type based on vendor
                        gpu_vendor = gpu.get("vendor", "").lower()
                        if "nvidia" in gpu_vendor:
                            gpu_type = "cuda"
                        elif "amd" in gpu_vendor or "ati" in gpu_vendor:
                            gpu_type = "rocm"
                        elif "intel" in gpu_vendor:
                            gpu_type = "hpu"  # Intel GPUs might be Arc GPUs
                        else:
                            # Default to cuda for unknown vendors (most common)
                            gpu_type = "cuda"
                            logger.warning(f"Unknown GPU vendor '{gpu_vendor}', defaulting to cuda")

                        # Build formatted device dict
                        formatted_device = {
                            "device_config": {
                                "type": gpu_type,
                                "name": gpu.get("raw_name", "Unknown GPU"),
                                "vendor": gpu.get("vendor", ""),
                                "model": gpu.get("model", ""),
                                "memory_gb": gpu.get("memory_gb", 0),
                                "mem_per_GPU_in_GB": gpu.get("memory_gb", 0),  # Required for budsim Evolution
                                "raw_name": gpu.get("raw_name", ""),  # Required for llm-memory-calculator
                                "pci_vendor": gpu.get("pci_vendor_id"),
                                "pci_device": gpu.get("pci_device_id"),
                                "cuda_version": gpu.get("cuda_version"),
                                "count": gpu.get("count", 1),
                                "inter_node_bandwidth_in_GB_per_sec": 200,
                                "intra_node_bandwidth_in_GB_per_sec": 300,
                            },
                            # Store both total_count and available_count
                            # available_count will be calculated separately if NFD is enabled
                            "total_count": gpu.get("count", 1),
                            "available_count": gpu.get("available_count", gpu.get("count", 1)),
                            "type": gpu_type,
                        }

                        # Add HAMI fields if present (for time-slicing GPU sharing)
                        _add_hami_fields_to_device(gpu, formatted_device)

                        formatted_devices.append(formatted_device)
                        device_type = gpu_type

                    # Process HPUs
                    for hpu in devices_data.get("hpus", []):
                        formatted_devices.append(
                            {
                                "device_config": {
                                    "type": "hpu",
                                    "name": hpu.get("raw_name", "Unknown HPU"),
                                    "vendor": hpu.get("vendor", "Intel"),
                                    "model": hpu.get("model", ""),
                                    "generation": hpu.get("generation"),
                                    "memory_gb": hpu.get("memory_gb", 0),
                                    "mem_per_GPU_in_GB": hpu.get("memory_gb", 0),  # Required for budsim
                                    "raw_name": hpu.get("raw_name", ""),
                                    "pci_vendor": hpu.get("pci_vendor_id"),
                                    "pci_device": hpu.get("pci_device_id"),
                                    "count": hpu.get("count", 1),
                                    "inter_node_bandwidth_in_GB_per_sec": 200,
                                    "intra_node_bandwidth_in_GB_per_sec": 300,
                                },
                                "available_count": hpu.get("count", 1),
                                "type": "hpu",
                            }
                        )
                        if device_type != "gpu":  # GPU takes priority
                            device_type = "hpu"

                    # Process CPUs
                    for cpu in devices_data.get("cpus", []):
                        formatted_devices.append(
                            {
                                "device_config": {
                                    "type": "cpu",
                                    "name": cpu.get("raw_name", "CPU"),
                                    "vendor": cpu.get("vendor", ""),
                                    "model": cpu.get("model", ""),
                                    "family": cpu.get("family", ""),
                                    "generation": cpu.get("generation", ""),
                                    "physical_cores": cpu.get("physical_cores", cpu.get("cores", 0)),
                                    "cores": cpu.get("cores", 0),
                                    "threads": cpu.get("threads", 0),
                                    "architecture": cpu.get("architecture", "x86_64"),
                                    "raw_name": cpu.get("raw_name", ""),
                                    "frequency_ghz": cpu.get("frequency_ghz"),
                                    "cache_mb": cpu.get("cache_mb"),
                                    "socket_count": cpu.get("socket_count", 1),
                                    "instruction_sets": cpu.get("instruction_sets", []),
                                    "memory_gb": cpu.get("memory_gb", 0),  # System memory from DeviceExtractor
                                    "mem_per_GPU_in_GB": cpu.get("memory_gb", 0),  # System memory
                                    "inter_node_bandwidth_in_GB_per_sec": 100,
                                    "intra_node_bandwidth_in_GB_per_sec": 200,
                                    "utilized_cores": cpu.get("utilized_cores", 0.0),
                                    "utilized_memory_gb": cpu.get("utilized_memory_gb", 0.0),
                                },
                                "available_count": 1,  # CPUs are counted differently
                                "type": "cpu",
                            }
                        )

                elif isinstance(devices_data, list):
                    # Legacy format support
                    for device in devices_data:
                        device_info = device.get("device_info", {})
                        dev_type = device.get("type", "cpu")
                        formatted_devices.append(
                            {
                                "device_config": {
                                    **device_info,
                                    "type": dev_type,
                                    "mem_per_GPU_in_GB": device_info.get("memory_gb", 0),
                                    "inter_node_bandwidth_in_GB_per_sec": device_info.get(
                                        "inter_node_bandwidth_in_GB_per_sec", 200
                                    ),
                                    "intra_node_bandwidth_in_GB_per_sec": device_info.get(
                                        "intra_node_bandwidth_in_GB_per_sec", 300
                                    ),
                                },
                                "available_count": device.get("available_count", 1),
                                "type": dev_type,
                            }
                        )
                        if dev_type == "gpu":
                            device_type = "gpu"
                        elif dev_type == "hpu" and device_type != "gpu":
                            device_type = "hpu"

                # Use formatted devices or create default CPU device
                if formatted_devices:
                    hardware_info = formatted_devices
                else:
                    # Fallback to CPU if no devices detected
                    cpu_info = node.get("cpu_info", {})
                    cpu_cores = int(cpu_info.get("cpu_cores", 0) or 0)
                    hardware_info = [
                        {
                            "device_config": {
                                "type": "cpu",
                                "name": cpu_info.get("cpu_name", "CPU"),
                                "vendor": cpu_info.get("cpu_vendor", "Unknown"),
                                "physical_cores": cpu_cores,
                                "cores": cpu_cores,
                                "architecture": cpu_info.get("architecture", "x86_64"),
                                "raw_name": cpu_info.get("cpu_name", "CPU"),
                                "mem_per_GPU_in_GB": 0,
                                "inter_node_bandwidth_in_GB_per_sec": 100,
                                "intra_node_bandwidth_in_GB_per_sec": 200,
                            },
                            "available_count": 1,
                            "type": "cpu",
                        }
                    ]
                    device_type = "cpu"

                # Extract core count for the node
                core_count = 0
                if hardware_info and hardware_info[0].get("device_config", {}).get("type") == "cpu":
                    core_count = hardware_info[0].get("device_config", {}).get("cores", 0)
                if core_count == 0:
                    core_count = int(node.get("cpu_info", {}).get("cpu_cores", 0) or 0)

                # Ensure node_status is properly converted to boolean
                node_status_value = node.get("node_status", False)
                if isinstance(node_status_value, bool):
                    node_status = node_status_value
                elif isinstance(node_status_value, str):
                    # Handle string booleans from Ansible
                    node_status = node_status_value.lower() in ("true", "1", "yes")
                else:
                    node_status = bool(node_status_value)

                logger.debug(f"Node {node['node_name']}: raw_status={node_status_value}, converted={node_status}")

                node_objects.append(
                    ClusterNodeInfo(
                        cluster_id=cluster_id,
                        name=node["node_name"],
                        internal_ip=node.get("internal_ip"),
                        type=device_type,
                        hardware_info=hardware_info,
                        status=node_status,
                        status_sync_at=node.get("timestamp", datetime.now(timezone.utc)),
                        threads_per_core=hardware_info[0].get("device_config", {}).get("threads_per_core", 0)
                        if hardware_info
                        else 0,
                        core_count=core_count,
                    )
                )

            # add node info to db
            with DBSession() as session:
                db_nodes = await ClusterNodeInfoDataManager(session).create_cluster_node_info(node_objects)
            logger.info("Added node info to db")
            nodes = await cls.transform_db_nodes(db_nodes)
            logger.info("Transformed db nodes")

            # Add is_master to state store output (not persisted in DB)
            for node in nodes:
                node["is_master"] = node_is_master_map.get(node["name"], False)

            result = {
                "id": str(cluster_id),
                "name": cluster_name,
                "nodes": nodes,
            }

            logger.info("Fetched cluster info result inside services")
            return json.dumps(result)
        except Exception as e:
            import traceback

            logger.error(
                f"Error fetching cluster info for workflow_id: {workflow_id} and task_id: {task_id}, error: {e}\n"
                f"Stacktrace:\n{traceback.format_exc()}"
            )
            raise e

    @classmethod
    async def delete_cluster(cls, delete_cluster_request: ClusterDeleteRequest, task_id: str, workflow_id: str):
        """Delete cluster resources."""
        logger.info(f"Deleting cluster resources for workflow_id: {workflow_id} and task_id: {task_id}")
        cluster_config = delete_cluster_request.cluster_config
        platform = delete_cluster_request.platform
        return await delete_cluster(cluster_config, platform)

    @classmethod
    async def transform_db_nodes(cls, db_nodes: List[ClusterNodeInfoModel]):
        """Transform db nodes to response."""
        result = []
        for node in db_nodes:
            hardware_info = node.hardware_info
            devices = []
            seen_device_uuids = set()  # Track seen device UUIDs to prevent duplicates

            for each_info in hardware_info:
                device_config = each_info.get("device_config", {})
                # Get both total_count and available_count from hardware_info
                # total_count represents the total devices on the node
                # available_count represents the currently unallocated devices
                total_count = each_info.get("total_count", each_info.get("available_count", 0))
                available_count = each_info.get("available_count", 0)

                # If node is not ready/schedulable, available_count should be 0
                if not node.status:
                    available_count = 0

                # Build device dict with flattened device_config
                device = {
                    **device_config,
                    "total_count": total_count,
                    "available_count": available_count,
                }

                # Add HAMI fields if present (for time-slicing GPU sharing)
                _add_hami_fields_to_device(each_info, device)

                # Deduplicate devices by device_uuid (for HAMI-enriched GPUs)
                if _should_skip_duplicate_device(device, seen_device_uuids, node.name):
                    continue

                devices.append(device)

            logger.debug(
                f"Node {node.name}: transformed {len(devices)} devices from {len(hardware_info)} hardware_info entries"
            )
            result.append(
                {
                    "name": node.name,
                    "id": str(node.id),
                    "status": node.status,
                    "devices": devices,
                }
            )
        return result

    @classmethod
    async def transform_db_nodes_enhanced(cls, db_nodes: List[ClusterNodeInfoModel]):
        """Enhanced node transformation with schedulability info and NFD features."""
        result = []
        for node in db_nodes:
            hardware_info = node.hardware_info
            devices = []
            seen_device_uuids = set()  # Track seen device UUIDs to prevent duplicates

            for each_info in hardware_info:
                device_config = each_info.get("device_config", {})

                # Enhanced device information
                enhanced_device = {
                    **device_config,
                    "available_count": each_info.get("available_count", 0),
                    "total_count": each_info.get("total_count", each_info.get("available_count", 0)),
                    "schedulable": each_info.get("schedulable", True),
                    # Enhanced NFD fields (optional, backward compatible)
                    "kernel_support": each_info.get("kernel_support", {}),
                    "driver_info": each_info.get("driver_info", {}),
                    "features": each_info.get("features", []),
                    "product_name": each_info.get("product_name", "Unknown"),
                }

                # Add HAMI fields if present (for time-slicing GPU sharing)
                _add_hami_fields_to_device(each_info, enhanced_device)

                # Deduplicate devices by device_uuid (for HAMI-enriched GPUs)
                if _should_skip_duplicate_device(enhanced_device, seen_device_uuids, node.name):
                    continue

                devices.append(enhanced_device)

            logger.debug(
                f"Node {node.name}: transformed {len(devices)} enhanced devices from {len(hardware_info)} hardware_info entries"
            )
            node_result = {
                "name": node.name,
                "id": str(node.id),
                "status": node.status,
                "devices": devices,
                # Enhanced schedulability information
                "schedulable": getattr(node, "schedulable", True),
                "unschedulable": getattr(node, "unschedulable", False),
                "taints": getattr(node, "taints", []),
                "conditions": getattr(node, "conditions", []),
                "pressure": getattr(node, "pressure_conditions", {}),
                "ready": node.status,
                # NFD detection info
                "nfd_detected": getattr(node, "nfd_detected", False),
                "detection_method": getattr(node, "detection_method", "configmap"),
            }
            result.append(node_result)

        return result

    @classmethod
    async def fetch_cluster_info_enhanced(
        cls, fetch_cluster_info_request: FetchClusterInfo, task_id: str, workflow_id: str, use_nfd: bool = True
    ):
        """Enhanced cluster info fetching with NFD-based schedulable resource detection."""
        logger.info(
            f"Fetching enhanced cluster info (NFD={use_nfd}) for workflow_id: {workflow_id} and task_id: {task_id}"
        )

        try:
            cluster_name = fetch_cluster_info_request.name
            cluster_id = fetch_cluster_info_request.cluster_id
            cluster_config = fetch_cluster_info_request.config_dict

            # Try NFD-based detection first
            if use_nfd:
                try:
                    nfd_detector = NFDSchedulableResourceDetector(cluster_config)
                    schedulable_nodes = await nfd_detector.get_schedulable_nodes()

                    # Convert NFD results to database format
                    node_objects = []
                    for node_info in schedulable_nodes:
                        hardware_info = cls._convert_nfd_to_hardware_info(node_info)

                        # Extract structured device information for llm-memory-calculator
                        structured_devices = node_info.get("devices", {})

                        node_objects.append(
                            ClusterNodeInfo(
                                cluster_id=cluster_id,
                                name=node_info["name"],
                                internal_ip=node_info.get("internal_ip"),
                                type=cls._determine_primary_device_type(node_info["devices"]),
                                hardware_info=hardware_info,
                                status=node_info["status"],
                                status_sync_at=node_info["timestamp"],
                                # Enhanced NFD fields
                                schedulable=node_info["schedulability"]["schedulable"],
                                unschedulable=node_info["schedulability"]["unschedulable"],
                                taints=node_info["schedulability"]["taints"],
                                conditions=node_info["schedulability"]["conditions"],
                                pressure_conditions=node_info["schedulability"]["pressure"],
                                nfd_detected=True,
                                detection_method="nfd",
                                nfd_labels=node_info.get("nfd_labels", {}),
                                threads_per_core=cls._extract_threads_per_core(node_info),
                                core_count=cls._extract_core_count(node_info),
                                # Structured device information for llm-memory-calculator
                                extracted_devices=structured_devices,
                            )
                        )

                    logger.info(f"NFD detection successful: {len(node_objects)} nodes found")

                except Exception as e:
                    logger.warning(f"NFD detection failed, falling back to ConfigMap method: {e}")
                    return await cls.fetch_cluster_info(fetch_cluster_info_request, task_id, workflow_id)
            else:
                # Use existing ConfigMap method
                return await cls.fetch_cluster_info(fetch_cluster_info_request, task_id, workflow_id)

            # Determine cluster status based on schedulable nodes
            cluster_status = (
                ClusterStatusEnum.AVAILABLE
                if any(node.schedulable for node in node_objects)
                else ClusterStatusEnum.NOT_AVAILABLE
            )

            with DBSession() as session:
                db_cluster = await ClusterDataManager(session).retrieve_cluster_by_fields({"id": cluster_id})
                await ClusterDataManager(session).update_cluster_by_fields(db_cluster, {"status": cluster_status})

                # Store enhanced node information
                db_nodes = await ClusterNodeInfoDataManager(session).create_cluster_node_info(node_objects)

            logger.info("Added enhanced node info to db")
            nodes = await cls.transform_db_nodes_enhanced(db_nodes)

            result = {
                "id": str(cluster_id),
                "name": cluster_name,
                "nodes": nodes,
                "enhanced": True,  # Flag to indicate NFD enhancement
                "detection_method": "nfd",
            }

            logger.info("Enhanced cluster info fetched successfully")
            return json.dumps(result)

        except Exception as e:
            logger.error(f"Error fetching enhanced cluster info: {e}")
            # Fallback to existing method
            logger.info("Falling back to existing cluster info method")
            return await cls.fetch_cluster_info(fetch_cluster_info_request, task_id, workflow_id)

    @classmethod
    def get_device_info_for_llm_calculator(cls, cluster_id: UUID) -> Dict[str, Any]:
        """Get structured device information for llm-memory-calculator.

        Returns device information in a format that can be used by llm-memory-calculator
        for matching against its configuration database.
        """
        with DBSession() as session:
            nodes = session.query(ClusterNodeInfoModel).filter_by(cluster_id=cluster_id).all()

            device_info = {"cluster_id": str(cluster_id), "nodes": []}

            for node in nodes:
                node_devices = {"node_name": node.name, "devices": {"gpus": [], "cpus": [], "hpus": []}}

                # Extract device info from extracted_devices field if available
                if hasattr(node, "extracted_devices") and node.extracted_devices:
                    node_devices["devices"] = node.extracted_devices
                elif node.hardware_info:
                    # Fallback to parsing hardware_info
                    device_extractor = DeviceExtractor()
                    for hw in node.hardware_info:
                        if hw.get("device_config", {}).get("device_type") == "GPU":
                            gpu_info = {
                                "raw_name": hw.get("device_config", {}).get("device_name", ""),
                                "memory_gb": hw.get("device_config", {}).get("device_memory_in_gb"),
                                "count": hw.get("available_count", 1),
                            }
                            # Parse the name for more details
                            parsed = device_extractor.parse_gpu_name(gpu_info["raw_name"])
                            gpu_info.update(parsed)
                            node_devices["devices"]["gpus"].append(gpu_info)
                        elif hw.get("device_config", {}).get("device_type") == "CPU":
                            cpu_info = {
                                "raw_name": hw.get("device_config", {}).get("device_name", ""),
                                "cores": hw.get("device_config", {}).get("device_cores"),
                                "threads": hw.get("device_config", {}).get("device_threads"),
                                "socket_count": hw.get("available_count", 1),
                                "frequency_ghz": hw.get("device_config", {}).get("device_frequency_ghz"),
                                "architecture": hw.get("device_config", {}).get("device_architecture", "x86_64"),
                            }
                            # Parse the name for more details
                            parsed = device_extractor.parse_cpu_name(cpu_info["raw_name"])
                            cpu_info.update(parsed)

                            # Extract frequency from name if not provided
                            if not cpu_info.get("frequency_ghz") and cpu_info["raw_name"]:
                                import re

                                freq_match = re.search(r"(\d+\.?\d*)\s*GHz", cpu_info["raw_name"], re.IGNORECASE)
                                if freq_match:
                                    cpu_info["frequency_ghz"] = float(freq_match.group(1))

                            node_devices["devices"]["cpus"].append(cpu_info)

                device_info["nodes"].append(node_devices)

            return device_info

    @classmethod
    def _convert_nfd_to_hardware_info(cls, node_info: Dict) -> List[Dict]:
        """Convert NFD node info to existing hardware_info format."""
        devices = node_info.get("devices", {})
        hardware_info = []

        # Handle new structured format
        if isinstance(devices, dict) and "legacy_devices" in devices:
            # Use legacy format for backward compatibility
            for device in devices.get("legacy_devices", []):
                device_info = {
                    "device_config": {
                        "name": device.get("name", "unknown"),
                        "type": device.get("type", "cpu"),
                        "mem_per_gpu_in_gb": device.get("mem_per_gpu_in_gb", 0),
                        "physical_cores": device.get("physical_cores", device.get("cores", 0)),
                        "cores": device.get("cores", 0),
                        "utilized_cores": device.get("utilized_cores", 0.0),
                        "utilized_memory_gb": device.get("utilized_memory_gb", 0.0),
                    },
                    "available_count": device.get("available_count", 0),
                    "total_count": device.get("total_count", 0),
                    "schedulable": device.get("schedulable", True),
                    # Enhanced information
                    "product_name": device.get("product_name", "Unknown"),
                    "features": device.get("features", []),
                    "kernel_support": device.get("kernel_support", {}),
                    "driver_info": device.get("driver_support", {}),
                    "cuda_version": device.get("cuda_version", ""),
                    "compute_capability": device.get("compute_capability", ""),
                }
                # FIX: Move append inside the loop to capture all devices
                hardware_info.append(device_info)

        return hardware_info

    @classmethod
    def _determine_primary_device_type(cls, devices: Any) -> str:
        """Determine the primary device type for the node.

        Handles both legacy list format and new structured dict format.
        """
        if not devices:
            return "cpu"

        device_types = []

        # Handle new structured format (dict with gpus, cpus, hpus, legacy_devices)
        if isinstance(devices, dict):
            # Check structured device lists
            if devices.get("gpus"):
                device_types.append("cuda")
            if devices.get("hpus"):
                device_types.append("hpu")
            if devices.get("cpus"):
                device_types.append("cpu")

            # Also check legacy_devices if present
            if "legacy_devices" in devices:
                for device in devices.get("legacy_devices", []):
                    device_type = device.get("type", "cpu")
                    if device_type not in device_types:
                        device_types.append(device_type)

        # Handle legacy list format
        elif isinstance(devices, list):
            device_types = [device.get("type", "cpu") for device in devices]

        # Priority: cuda/gpu > hpu > cpu
        if "cuda" in device_types or "gpu" in device_types:
            return "cuda"
        elif "hpu" in device_types:
            return "hpu"
        else:
            return "cpu"

    @classmethod
    def _extract_threads_per_core(cls, node_info: Dict) -> int:
        """Extract threads per core from NFD node info.

        Handles both legacy list format and new structured dict format.
        """
        devices = node_info.get("devices", {})

        # Handle new structured format
        if isinstance(devices, dict):
            # Check cpus list first
            if devices.get("cpus"):
                return devices["cpus"][0].get("threads_per_core", 2)

            # Fall back to legacy_devices
            if "legacy_devices" in devices:
                cpu_devices = [d for d in devices["legacy_devices"] if d.get("type") == "cpu"]
                if cpu_devices:
                    return cpu_devices[0].get("threads_per_core", 2)

        # Handle legacy list format
        elif isinstance(devices, list):
            cpu_devices = [d for d in devices if d.get("type") == "cpu"]
            if cpu_devices:
                return cpu_devices[0].get("threads_per_core", 2)

        return 2

    @classmethod
    def _extract_core_count(cls, node_info: Dict) -> int:
        """Extract core count from NFD node info.

        Handles both legacy list format and new structured dict format.
        """
        devices = node_info.get("devices", {})

        # Handle new structured format
        if isinstance(devices, dict):
            # Check cpus list first
            if devices.get("cpus"):
                return devices["cpus"][0].get("cores", 1)

            # Fall back to legacy_devices
            if "legacy_devices" in devices:
                cpu_devices = [d for d in devices["legacy_devices"] if d.get("type") == "cpu"]
                if cpu_devices:
                    return cpu_devices[0].get("cores", 1)

        # Handle legacy list format
        elif isinstance(devices, list):
            cpu_devices = [d for d in devices if d.get("type") == "cpu"]
            if cpu_devices:
                return cpu_devices[0].get("cores", 1)

        return 1

    @classmethod
    async def update_node_status_enhanced(cls, cluster_id: UUID) -> ClusterStatusEnum:
        """Enhanced node status update with NFD schedulability detection."""
        logger.info(f"Updating node status (NFD-enhanced) for cluster_id: {cluster_id}")

        with DBSession() as session:
            db_cluster = await ClusterDataManager(session).retrieve_cluster_by_fields(
                {"id": cluster_id}, missing_ok=True
            )

            if not db_cluster:
                logger.debug(f"Cluster not found: {cluster_id}")
                return ClusterStatusEnum.NOT_AVAILABLE

            try:
                # Use NFD detector for real-time schedulability if enabled
                if app_settings.enable_nfd_detection:
                    try:
                        nfd_detector = NFDSchedulableResourceDetector(db_cluster.config_file_dict)
                        schedulable_nodes = await nfd_detector.get_schedulable_nodes()

                        # Update database with latest schedulability info
                        await cls._update_node_schedulability(session, cluster_id, schedulable_nodes)

                        # Determine cluster status based on schedulable nodes
                        cluster_status = (
                            ClusterStatusEnum.AVAILABLE
                            if any(node["schedulability"]["schedulable"] for node in schedulable_nodes)
                            else ClusterStatusEnum.NOT_AVAILABLE
                        )

                        # Update cluster status if changed
                        if cluster_status != db_cluster.status:
                            await ClusterDataManager(session).update_cluster_by_fields(
                                db_cluster, {"status": cluster_status}
                            )
                            logger.info(f"Cluster {cluster_id} status updated to {cluster_status}")

                        # Store in state store for budapp consumption
                        nodes = await cls.transform_db_nodes_enhanced(db_cluster.nodes)

                        # Add is_master from schedulable_nodes to output
                        schedulable_nodes_map = {n["name"]: n.get("is_master", False) for n in schedulable_nodes}
                        for node in nodes:
                            node["is_master"] = schedulable_nodes_map.get(node["name"], False)

                        result = {"id": str(cluster_id), "nodes": nodes, "enhanced": True, "detection_method": "nfd"}
                        await cls.update_node_info_in_statestore(json.dumps(result))

                        logger.info(f"Enhanced cluster {cluster_id} status: {cluster_status}")
                        return cluster_status

                    except Exception as e:
                        logger.warning(f"Enhanced node status update failed: {e}")
                        # NFD is now the only detection method - no fallback available
                        logger.error("NFD-based node status update failed and no fallback is available")
                        raise e
                else:
                    # Use existing ConfigMap approach
                    return await cls.update_node_status(cluster_id)

            except Exception as e:
                logger.error(f"Node status update failed: {e}")
                return ClusterStatusEnum.NOT_AVAILABLE

    @classmethod
    async def _update_node_schedulability(cls, session, cluster_id: UUID, schedulable_nodes: List[Dict]):
        """Update node schedulability information in database."""
        node_updates = []

        for node_info in schedulable_nodes:
            # Convert NFD data to database format
            hardware_info = cls._convert_nfd_to_hardware_info(node_info)

            node_update = {
                "cluster_id": cluster_id,
                "name": node_info["name"],
                "internal_ip": node_info.get("internal_ip"),
                "type": cls._determine_primary_device_type(node_info["devices"]),
                "hardware_info": hardware_info,
                "status": node_info["status"],
                "status_sync_at": node_info["timestamp"],
                # Enhanced NFD fields
                "schedulable": node_info["schedulability"]["schedulable"],
                "unschedulable": node_info["schedulability"]["unschedulable"],
                "taints": node_info["schedulability"]["taints"],
                "conditions": node_info["schedulability"]["conditions"],
                "pressure_conditions": node_info["schedulability"]["pressure"],
                "nfd_detected": True,
                "detection_method": "nfd",
                "nfd_labels": node_info.get("nfd_labels", {}),
                "threads_per_core": cls._extract_threads_per_core(node_info),
                "core_count": cls._extract_core_count(node_info),
            }
            node_updates.append(node_update)

        # Batch update nodes
        for node_data in node_updates:
            existing_node = await ClusterNodeInfoDataManager(session).retrieve_cluster_node_info_by_fields(
                {"cluster_id": cluster_id, "name": node_data["name"]}, missing_ok=True
            )

            if existing_node:
                await ClusterNodeInfoDataManager(session).update_cluster_node_info_by_fields(existing_node, node_data)
            else:
                new_node = ClusterNodeInfo(**node_data)
                await ClusterNodeInfoDataManager(session).create_cluster_node_info([new_node])

    @classmethod
    async def update_node_status(cls, cluster_id: UUID, config_dict: dict = None) -> ClusterStatusEnum:
        """Update node status.

        Args:
            cluster_id: The cluster ID to update
            config_dict: Optional pre-decrypted config dictionary. If not provided, will decrypt from db_cluster.
        """
        logger.info(f"Updating node status for cluster_id: {cluster_id}")
        with DBSession() as session:
            # Get cluster info
            db_cluster = await ClusterDataManager(session).retrieve_cluster_by_fields(
                {"id": cluster_id}, missing_ok=True
            )

            if not db_cluster:
                logger.debug(f"Cluster not found: {cluster_id}")
                return

            node_status_change = False
            prev_node_status_map = {each.name: each.status for each in db_cluster.nodes}

            # Use provided config or handle missing config
            if config_dict is None or not config_dict:
                logger.warning(f"No config provided for cluster {cluster_id}, cannot check node status")
                # Return tuple with default values when config is missing
                current_status = db_cluster.status if db_cluster.status else ClusterStatusEnum.NOT_AVAILABLE
                return current_status, False, {"id": str(cluster_id), "nodes": []}, False

            # Get node info
            node_info = await get_node_info(config_dict, db_cluster.platform)

            # Capture is_master for each node before DB operations (not stored in DB)
            node_is_master_map = {node["node_name"]: node.get("is_master", False) for node in node_info}

            # Create node objects
            node_objects = []
            for node in node_info:
                devices_data = json.loads(node.get("devices", "{}"))

                # Extract and format devices with proper structure for budsim and llm-memory-calculator
                formatted_devices = []
                device_type = "cpu"  # Default to CPU

                if isinstance(devices_data, dict):
                    # Process GPUs
                    for gpu in devices_data.get("gpus", []):
                        # Determine GPU type based on vendor
                        gpu_vendor = gpu.get("vendor", "").lower()
                        if "nvidia" in gpu_vendor:
                            gpu_type = "cuda"
                        elif "amd" in gpu_vendor or "ati" in gpu_vendor:
                            gpu_type = "rocm"
                        elif "intel" in gpu_vendor:
                            gpu_type = "hpu"  # Intel GPUs might be Arc GPUs
                        else:
                            # Default to cuda for unknown vendors (most common)
                            gpu_type = "cuda"
                            logger.warning(f"Unknown GPU vendor '{gpu_vendor}', defaulting to cuda")

                        # Build formatted device dict
                        formatted_device = {
                            "device_config": {
                                "type": gpu_type,
                                "name": gpu.get("raw_name", "Unknown GPU"),
                                "vendor": gpu.get("vendor", ""),
                                "model": gpu.get("model", ""),
                                "memory_gb": gpu.get("memory_gb", 0),
                                "mem_per_GPU_in_GB": gpu.get("memory_gb", 0),  # Required for budsim Evolution
                                "raw_name": gpu.get("raw_name", ""),  # Required for llm-memory-calculator
                                "pci_vendor": gpu.get("pci_vendor_id"),
                                "pci_device": gpu.get("pci_device_id"),
                                "cuda_version": gpu.get("cuda_version"),
                                "count": gpu.get("count", 1),
                                "inter_node_bandwidth_in_GB_per_sec": 200,
                                "intra_node_bandwidth_in_GB_per_sec": 300,
                            },
                            # Store both total_count and available_count
                            # The get_node_info in kubernetes.py already calculated real available_count
                            "total_count": gpu.get("total_count", gpu.get("count", 1)),
                            "available_count": gpu.get("available_count", gpu.get("count", 1)),
                            "type": gpu_type,
                        }

                        # Add HAMI fields if present (for time-slicing GPU sharing)
                        _add_hami_fields_to_device(gpu, formatted_device)

                        formatted_devices.append(formatted_device)
                        device_type = gpu_type

                    # Process HPUs
                    for hpu in devices_data.get("hpus", []):
                        formatted_devices.append(
                            {
                                "device_config": {
                                    "type": "hpu",
                                    "name": hpu.get("raw_name", "Unknown HPU"),
                                    "vendor": hpu.get("vendor", "Intel"),
                                    "model": hpu.get("model", ""),
                                    "generation": hpu.get("generation"),
                                    "memory_gb": hpu.get("memory_gb", 0),
                                    "mem_per_GPU_in_GB": hpu.get("memory_gb", 0),  # Required for budsim
                                    "raw_name": hpu.get("raw_name", ""),
                                    "pci_vendor": hpu.get("pci_vendor_id"),
                                    "pci_device": hpu.get("pci_device_id"),
                                    "count": hpu.get("count", 1),
                                    "inter_node_bandwidth_in_GB_per_sec": 200,
                                    "intra_node_bandwidth_in_GB_per_sec": 300,
                                },
                                "available_count": hpu.get("count", 1),
                                "type": "hpu",
                            }
                        )
                        if device_type != "gpu":  # GPU takes priority
                            device_type = "hpu"

                    # Process CPUs
                    for cpu in devices_data.get("cpus", []):
                        # Get CPU type from the device data (cpu or cpu_high)
                        cpu_type = cpu.get("type", "cpu")
                        formatted_devices.append(
                            {
                                "device_config": {
                                    "type": cpu_type,
                                    "name": cpu.get("name", cpu.get("raw_name", "CPU")),
                                    "vendor": cpu.get("vendor", ""),
                                    "model": cpu.get("model", ""),
                                    "family": cpu.get("family", ""),
                                    "generation": cpu.get("generation", ""),
                                    "physical_cores": cpu.get("physical_cores", cpu.get("cores", 0)),
                                    "cores": cpu.get("cores", 0),
                                    "threads": cpu.get("threads", 0),
                                    "architecture": cpu.get("architecture", "x86_64"),
                                    "raw_name": cpu.get("raw_name", ""),
                                    "frequency_ghz": cpu.get("frequency_ghz"),
                                    "cache_mb": cpu.get("cache_mb"),
                                    "socket_count": cpu.get("socket_count", 1),
                                    "instruction_sets": cpu.get("instruction_sets", []),
                                    "memory_gb": cpu.get("memory_gb", 0),  # System memory from DeviceExtractor
                                    "mem_per_GPU_in_GB": cpu.get("memory_gb", 0),  # System memory
                                    "inter_node_bandwidth_in_GB_per_sec": 100,
                                    "intra_node_bandwidth_in_GB_per_sec": 200,
                                    "utilized_cores": cpu.get("utilized_cores", 0.0),
                                    "utilized_memory_gb": cpu.get("utilized_memory_gb", 0.0),
                                },
                                "available_count": 1,  # CPUs are counted differently
                                "type": cpu_type,
                            }
                        )

                elif isinstance(devices_data, list):
                    # Legacy format support
                    for device in devices_data:
                        device_info = device.get("device_info", {})
                        dev_type = device.get("type", "cpu")
                        formatted_devices.append(
                            {
                                "device_config": {
                                    **device_info,
                                    "type": dev_type,
                                    "mem_per_GPU_in_GB": device_info.get("memory_gb", 0),
                                    "inter_node_bandwidth_in_GB_per_sec": device_info.get(
                                        "inter_node_bandwidth_in_GB_per_sec", 200
                                    ),
                                    "intra_node_bandwidth_in_GB_per_sec": device_info.get(
                                        "intra_node_bandwidth_in_GB_per_sec", 300
                                    ),
                                },
                                "available_count": device.get("available_count", 1),
                                "type": dev_type,
                            }
                        )
                        if dev_type == "gpu":
                            device_type = "gpu"
                        elif dev_type == "hpu" and device_type != "gpu":
                            device_type = "hpu"

                # Use formatted devices or create default CPU device
                if formatted_devices:
                    hardware_info = formatted_devices
                else:
                    # Fallback to CPU if no devices detected
                    cpu_info = node.get("cpu_info", {})
                    cpu_cores = int(cpu_info.get("cpu_cores", 0) or 0)
                    hardware_info = [
                        {
                            "device_config": {
                                "type": "cpu",
                                "name": cpu_info.get("cpu_name", "CPU"),
                                "vendor": cpu_info.get("cpu_vendor", "Unknown"),
                                "physical_cores": cpu_cores,
                                "cores": cpu_cores,
                                "architecture": cpu_info.get("architecture", "x86_64"),
                                "raw_name": cpu_info.get("cpu_name", "CPU"),
                                "mem_per_GPU_in_GB": 0,
                                "inter_node_bandwidth_in_GB_per_sec": 100,
                                "intra_node_bandwidth_in_GB_per_sec": 200,
                            },
                            "available_count": 1,
                            "type": "cpu",
                        }
                    ]
                    device_type = "cpu"

                # Extract core count for the node
                core_count = 0
                if hardware_info and hardware_info[0].get("device_config", {}).get("type") == "cpu":
                    core_count = hardware_info[0].get("device_config", {}).get("cores", 0)
                if core_count == 0:
                    core_count = int(node.get("cpu_info", {}).get("cpu_cores", 0) or 0)

                if (
                    node["node_name"] in prev_node_status_map
                    and prev_node_status_map[node["node_name"]] != node["node_status"]
                ):
                    node_status_change = True

                # Ensure node_status is properly converted to boolean
                node_status_value = node.get("node_status", False)
                if isinstance(node_status_value, bool):
                    node_status = node_status_value
                elif isinstance(node_status_value, str):
                    # Handle string booleans from Ansible
                    node_status = node_status_value.lower() in ("true", "1", "yes")
                else:
                    node_status = bool(node_status_value)

                logger.debug(f"Node {node['node_name']}: raw_status={node_status_value}, converted={node_status}")

                node_objects.append(
                    ClusterNodeInfo(
                        cluster_id=cluster_id,
                        name=node["node_name"],
                        internal_ip=node.get("internal_ip"),
                        type=device_type,
                        hardware_info=hardware_info,
                        status=node_status,
                        status_sync_at=node.get("timestamp", datetime.now(timezone.utc)),
                        threads_per_core=hardware_info[0].get("device_config", {}).get("threads_per_core", 0)
                        if hardware_info
                        else 0,
                        core_count=core_count,
                    )
                )

            nodes_info_present = len(node_objects) > 0 and len(db_cluster.nodes) == len(node_objects)

            node_map = {node.name: node for node in node_objects}

            # Group existing nodes by name to detect duplicates
            nodes_by_name = {}
            for node in db_cluster.nodes:
                if node.name not in nodes_by_name:
                    nodes_by_name[node.name] = []
                nodes_by_name[node.name].append(node)

            # Handle duplicates - keep most recent, mark others for deletion
            duplicates_to_delete = []
            db_node_map = {}
            for name, nodes in nodes_by_name.items():
                if len(nodes) > 1:
                    # Sort by modified_at (most recent first), fallback to created_at, then id
                    nodes.sort(
                        key=lambda n: (
                            n.modified_at or n.created_at or datetime.min.replace(tzinfo=timezone.utc),
                            str(n.id),
                        ),
                        reverse=True,
                    )
                    db_node_map[name] = nodes[0]  # Keep the most recent
                    duplicates_to_delete.extend(nodes[1:])  # Delete older duplicates
                    logger.warning(
                        f"Found {len(nodes)} duplicate nodes for '{name}' in cluster {cluster_id}. "
                        f"Keeping node {nodes[0].id}, deleting {len(nodes) - 1} duplicates."
                    )
                else:
                    db_node_map[name] = nodes[0]

            # Identify nodes to update, add, or delete
            update_nodes = []
            add_nodes = []
            delete_nodes = []
            for node in node_map:
                if node in db_node_map:
                    for field, value in node_map[node].model_dump(mode="json").items():
                        setattr(db_node_map[node], field, value)
                    update_nodes.append(db_node_map[node])
                else:
                    add_nodes.append(node_map[node])

            # Add duplicates to delete list
            delete_nodes = [db_node_map[name] for name in db_node_map if name not in node_map]
            delete_nodes.extend(duplicates_to_delete)

            if add_nodes or delete_nodes:
                node_status_change = True

            if update_nodes:
                # Merge nodes back into session to ensure they're properly attached
                merged_nodes = [session.merge(node) for node in update_nodes]
                await ClusterNodeInfoDataManager(session).update_cluster_node_info(merged_nodes)

            if add_nodes:
                await ClusterNodeInfoDataManager(session).create_cluster_node_info(add_nodes)

            if delete_nodes:
                await ClusterNodeInfoDataManager(session).delete_cluster_node_info(delete_nodes)

            db_nodes = await ClusterNodeInfoDataManager(session).get_cluster_node_info_by_cluster_id(cluster_id)

            cluster_status = (
                ClusterStatusEnum.AVAILABLE
                if any(node.status for node in node_objects)
                else ClusterStatusEnum.NOT_AVAILABLE
            )

            # Prepare and store results in statestore
            nodes = await cls.transform_db_nodes(db_nodes)

            # Add is_master to state store output (not persisted in DB)
            for node in nodes:
                node["is_master"] = node_is_master_map.get(node["name"], False)

            result = {
                "id": str(cluster_id),
                "nodes": nodes,
            }

            logger.info(f"Cluster status: {cluster_status} Nodes info present: {nodes_info_present}")
            if cluster_status != db_cluster.status:
                # Merge cluster back into session to ensure it's properly attached
                merged_cluster = session.merge(db_cluster)
                await ClusterDataManager(session).update_cluster_by_fields(merged_cluster, {"status": cluster_status})

            await cls.update_node_info_in_statestore(json.dumps(result))
            return cluster_status, nodes_info_present, result, node_status_change

    @classmethod
    async def update_node_info_in_statestore(cls, input_data: str):
        """Update node info in state store."""
        data = json.loads(input_data)
        cluster_id = data["id"]

        with DaprService() as dapr_service:
            key = "cluster_info"
            response = dapr_service.get_state(store_name=app_settings.statestore_name, key=key)
            all_cluster_info = json.loads(response.data) if response.data else []
            filtered_cluster_info = [info for info in all_cluster_info if info["id"] != cluster_id]
            filtered_cluster_info.append(data)
            dapr_service.save_to_statestore(
                store_name=app_settings.statestore_name, key=key, value=json.dumps(filtered_cluster_info)
            )

    @classmethod
    async def delete_node_info_from_statestore(cls, cluster_id: str):
        """Delete node info from state store."""
        with DaprService() as dapr_service:
            key = "cluster_info"
            response = dapr_service.get_state(store_name=app_settings.statestore_name, key=key)
            all_cluster_info = json.loads(response.data) if response.data else []
            filtered_cluster_info = [info for info in all_cluster_info if info["id"] != cluster_id]
            dapr_service.save_to_statestore(
                store_name=app_settings.statestore_name, key=key, value=json.dumps(filtered_cluster_info)
            )

    @classmethod
    def cancel_cluster_registration(cls, workflow_id: UUID) -> Union[SuccessResponse, ErrorResponse]:
        """Cancel a cluster registration."""
        workflow_status_dict = get_workflow_data_from_statestore(str(workflow_id))
        if not workflow_status_dict:
            return ErrorResponse(message="Workflow not found")
        if "cluster_id" in workflow_status_dict:
            cluster_id = workflow_status_dict["cluster_id"]
            with DBSession() as session:
                db_cluster = asyncio.run(ClusterService(session)._get_cluster(cluster_id, missing_ok=True))

                if db_cluster is None:
                    return ErrorResponse(message="Cluster not found")

                asyncio.run(ClusterDataManager(session).delete_cluster(db_cluster=db_cluster))

            asyncio.run(ClusterOpsService.delete_node_info_from_statestore(str(cluster_id)))
        # cleanup resources create deployment workflow
        if "namespace" in workflow_status_dict:
            from ..commons.constants import ClusterPlatformEnum
            from ..deployment.handler import DeploymentHandler

            platform_str = workflow_status_dict.get("platform")
            platform = ClusterPlatformEnum(platform_str) if platform_str else None
            deployment_handler = DeploymentHandler(config=workflow_status_dict["cluster_config_dict"])
            deployment_handler.delete(workflow_status_dict["namespace"], platform)
        return SuccessResponse(message="Create deployment resources cleaned up")

    @classmethod
    async def trigger_update_node_status_workflow(cls, cluster_id: UUID):
        """Trigger update node status workflow."""
        from .workflows import UpdateClusterStatusWorkflow

        # Just pass cluster_id, let workflow handle decryption
        response = await UpdateClusterStatusWorkflow().__call__(str(cluster_id))
        return response

    @classmethod
    def _send_cluster_status_update_notification(
        cls,
        cluster_id: str,
        new_status: ClusterStatusEnum,
        message: str,
    ) -> None:
        """Send cluster-status-update notification to budapp.

        This method is designed to be called OUTSIDE of database transactions
        to ensure DB changes are committed before attempting to send notifications.

        Args:
            cluster_id: The cluster UUID as string
            new_status: The new cluster status enum value
            message: Human-readable message describing the change
        """
        try:
            event_name = "cluster-status-update"
            content = NotificationContent(
                title="Cluster status updated",
                message=message,
                status=WorkflowStatus.COMPLETED,
                result={
                    "cluster_id": cluster_id,
                    "status": new_status.value,
                    "node_info": {"id": cluster_id, "nodes": []},
                },
            )
            notification_request = NotificationRequest(
                notification_type=NotificationType.EVENT,
                name=event_name,
                payload=NotificationPayload(
                    category=NotificationCategory.INTERNAL,
                    type=event_name,
                    event="results",
                    content=content,
                    workflow_id="",
                ),
                topic_keys=["budAppMessages"],
            )
            with DaprService() as dapr_service:
                dapr_service.publish_to_topic(
                    data=notification_request.model_dump(mode="json"),
                    target_topic_name="budAppMessages",
                    target_name=None,
                    event_type=notification_request.payload.type,
                )
            logger.info(f"Sent {new_status.value} notification for cluster {cluster_id}")
        except Exception as e:
            # Log error but don't raise - notification failure shouldn't affect callers
            logger.error(f"Failed to send cluster status notification for {cluster_id}: {e}")

    @classmethod
    async def _check_and_move_to_error(cls, threshold_hours: int = 24):
        """Check NOT_AVAILABLE clusters and move to ERROR if threshold exceeded.

        Args:
            threshold_hours: Hours in NOT_AVAILABLE before moving to ERROR
        """
        from datetime import timedelta

        cutoff_time = datetime.utcnow() - timedelta(hours=threshold_hours)

        # Collect notifications to send after transaction commits
        notifications_to_send = []

        try:
            with DBSession() as session:
                # Get clusters that have been NOT_AVAILABLE for > threshold
                clusters = await ClusterDataManager(session).get_all_clusters_by_status(
                    [ClusterStatusEnum.NOT_AVAILABLE]
                )

                moved_count = 0
                for cluster in clusters:
                    # Check if not_available_since is set and older than cutoff
                    if cluster.not_available_since and cluster.not_available_since < cutoff_time:
                        await ClusterDataManager(session).update_cluster_by_fields(
                            cluster,
                            {
                                "status": ClusterStatusEnum.ERROR,
                                "last_retry_time": datetime.utcnow(),
                            },
                        )
                        moved_count += 1
                        logger.warning(
                            f"Cluster {cluster.id} moved to ERROR state after {threshold_hours}h in NOT_AVAILABLE"
                        )

                        # Collect notification info to send after transaction commits
                        notifications_to_send.append(
                            {
                                "cluster_id": str(cluster.id),
                                "new_status": ClusterStatusEnum.ERROR,
                                "message": f"Cluster {cluster.host} moved to ERROR state after {threshold_hours}h in NOT_AVAILABLE",
                            }
                        )

                if moved_count > 0:
                    logger.info(f"Moved {moved_count} clusters from NOT_AVAILABLE to ERROR")

            # Send notifications AFTER transaction commits successfully
            for notification in notifications_to_send:
                cls._send_cluster_status_update_notification(**notification)

        except Exception as e:
            logger.error(f"Failed to check and move clusters to ERROR: {e}")

    @classmethod
    async def _get_error_clusters_due_for_retry(cls, retry_hours: int = 24) -> list:
        """Get ERROR clusters that haven't been retried recently.

        Args:
            retry_hours: Hours between retries for ERROR clusters

        Returns:
            List of ERROR clusters due for retry
        """
        from datetime import timedelta

        cutoff_time = datetime.utcnow() - timedelta(hours=retry_hours)

        try:
            with DBSession() as session:
                # Get ERROR clusters due for retry using optimized DB query
                clusters_to_retry = await ClusterDataManager(session).get_error_clusters_due_for_retry(
                    ClusterStatusEnum.ERROR, cutoff_time
                )

                if clusters_to_retry:
                    logger.info(f"Found {len(clusters_to_retry)} ERROR clusters due for retry")

                return clusters_to_retry

        except Exception as e:
            logger.error(f"Failed to get ERROR clusters for retry: {e}")
            return []

    @classmethod
    async def _handle_cluster_failure(cls, cluster_id: UUID):
        """Handle cluster connection failure and update state.

        Args:
            cluster_id: ID of the cluster that failed
        """
        notification_data = None  # Track what to notify after transaction

        try:
            with DBSession() as session:
                cluster = await ClusterDataManager(session).retrieve_cluster_by_fields({"id": cluster_id})

                if not cluster:
                    logger.error(f"Cluster {cluster_id} not found for failure handling")
                    return

                cluster_id_str = str(cluster_id)

                # If currently AVAILABLE, move to NOT_AVAILABLE and record timestamp
                if cluster.status == ClusterStatusEnum.AVAILABLE:
                    await ClusterDataManager(session).update_cluster_by_fields(
                        cluster,
                        {
                            "status": ClusterStatusEnum.NOT_AVAILABLE,
                            "not_available_since": datetime.utcnow(),
                        },
                    )
                    notification_data = {
                        "cluster_id": cluster_id_str,
                        "new_status": ClusterStatusEnum.NOT_AVAILABLE,
                        "message": f"Cluster {cluster_id_str} status: NOT_AVAILABLE",
                    }
                    logger.info(f"Cluster {cluster_id} moved to NOT_AVAILABLE")

                # If ERROR, update retry time and keep status as ERROR
                elif cluster.status == ClusterStatusEnum.ERROR:
                    await ClusterDataManager(session).update_cluster_by_fields(
                        cluster,
                        {
                            "last_retry_time": datetime.utcnow(),
                        },
                    )
                    notification_data = {
                        "cluster_id": cluster_id_str,
                        "new_status": ClusterStatusEnum.ERROR,
                        "message": f"Cluster {cluster_id_str} status: ERROR",
                    }
                    logger.debug(f"Updated retry time for ERROR cluster {cluster_id}")

            # Send notification AFTER transaction commits successfully
            if notification_data:
                cls._send_cluster_status_update_notification(**notification_data)

        except Exception as e:
            logger.error(f"Failed to handle cluster failure for {cluster_id}: {e}")

    @classmethod
    async def _handle_cluster_success(cls, cluster_id: UUID):
        """Handle successful cluster connection and update state.

        Args:
            cluster_id: ID of the cluster that succeeded
        """
        notification_data = None  # Track what to notify after transaction

        try:
            with DBSession() as session:
                cluster = await ClusterDataManager(session).retrieve_cluster_by_fields({"id": cluster_id})

                if not cluster:
                    logger.error(f"Cluster {cluster_id} not found for success handling")
                    return

                # Reset to AVAILABLE and clear timestamps
                previous_status = cluster.status
                cluster_id_str = str(cluster_id)

                await ClusterDataManager(session).update_cluster_by_fields(
                    cluster,
                    {
                        "status": ClusterStatusEnum.AVAILABLE,
                        "not_available_since": None,
                        "last_retry_time": None,
                    },
                )

                if previous_status in [ClusterStatusEnum.NOT_AVAILABLE, ClusterStatusEnum.ERROR]:
                    logger.info(f"Cluster {cluster_id} recovered from {previous_status} to AVAILABLE")
                    notification_data = {
                        "cluster_id": cluster_id_str,
                        "new_status": ClusterStatusEnum.AVAILABLE,
                        "message": f"Cluster {cluster_id_str} recovered to AVAILABLE",
                    }

            # Send notification AFTER transaction commits successfully
            if notification_data:
                cls._send_cluster_status_update_notification(**notification_data)

        except Exception as e:
            logger.error(f"Failed to handle cluster success for {cluster_id}: {e}")

    @classmethod
    async def trigger_periodic_node_status_update(cls) -> Union[SuccessResponse, ErrorResponse]:
        """Trigger node status update for all active clusters.

        This method is called by a periodic job to keep cluster node information
        up-to-date in the state store. Implements state management and batch
        processing to prevent resource exhaustion.

        Returns:
            SuccessResponse: If updates were triggered successfully
            ErrorResponse: If there was an error triggering updates
        """
        from datetime import UTC, datetime, timedelta

        from budmicroframe.shared.dapr_service import DaprService

        # Configuration
        BATCH_SIZE = 2  # Process max 2 clusters concurrently (reduced from 5 to prevent OOM)
        STALE_THRESHOLD_MINUTES = 20  # Consider sync stale after 20 minutes
        STATE_STORE_KEY = "cluster_node_sync_state"
        ERROR_RETRY_HOURS = 24  # Retry ERROR clusters every 24 hours
        NOT_AVAILABLE_THRESHOLD_HOURS = 24  # Move to ERROR after 24h in NOT_AVAILABLE

        try:
            # Initialize state management (optional - gracefully handle if not available)
            sync_state = {"active_syncs": {}, "last_sync_times": {}, "failed_clusters": {}}
            use_state_store = False

            try:
                dapr_service = DaprService()
                if hasattr(app_settings, "statestore_name") and app_settings.statestore_name:
                    # Try to get existing state
                    try:
                        sync_state = dapr_service.get_state(
                            store_name=app_settings.statestore_name, key=STATE_STORE_KEY
                        ).json()
                        use_state_store = True
                        logger.debug(f"Retrieved sync state from state store: {sync_state}")
                    except Exception as e:
                        logger.debug(f"State store not available or empty, using in-memory state: {e}")
                else:
                    logger.debug("State store not configured, using in-memory state")
            except Exception as e:
                logger.debug(f"DaprService not available, using in-memory state: {e}")

            # Clean up stale active syncs (older than threshold)
            current_time = datetime.now(UTC)
            stale_time = current_time - timedelta(minutes=STALE_THRESHOLD_MINUTES)

            for cluster_id, sync_info in list(sync_state.get("active_syncs", {}).items()):
                sync_time = datetime.fromisoformat(sync_info.get("started_at", ""))
                if sync_time < stale_time:
                    logger.warning(f"Removing stale sync for cluster {cluster_id}")
                    del sync_state["active_syncs"][cluster_id]

            # Check if any NOT_AVAILABLE clusters should move to ERROR
            await cls._check_and_move_to_error(threshold_hours=NOT_AVAILABLE_THRESHOLD_HOURS)

            # Get all active clusters from database
            with DBSession() as session:
                active_clusters = await ClusterDataManager(session).get_all_clusters_by_status(
                    [ClusterStatusEnum.AVAILABLE, ClusterStatusEnum.NOT_AVAILABLE]
                )

            # Get ERROR clusters that are due for retry
            error_clusters = await cls._get_error_clusters_due_for_retry(retry_hours=ERROR_RETRY_HOURS)

            # Combine active and error clusters
            all_clusters = active_clusters + error_clusters

            logger.info(
                f"Found {len(active_clusters)} active clusters + {len(error_clusters)} ERROR clusters "
                f"for node status update (total: {len(all_clusters)})"
            )

            # Filter out clusters that are already being synced
            clusters_to_sync = []
            for cluster in all_clusters:
                cluster_id_str = str(cluster.id)

                # Skip if already being synced
                if cluster_id_str in sync_state.get("active_syncs", {}):
                    logger.debug(f"Skipping cluster {cluster_id_str} - already being synced")
                    continue

                # Add to sync list
                clusters_to_sync.append(cluster)

            logger.info(
                f"Will sync {len(clusters_to_sync)} clusters (excluding {len(active_clusters) - len(clusters_to_sync)} already in progress)"
            )

            # Process clusters in batches
            update_count = 0
            failed_count = 0

            for i in range(0, len(clusters_to_sync), BATCH_SIZE):
                batch = clusters_to_sync[i : i + BATCH_SIZE]
                logger.info(f"Processing batch {i // BATCH_SIZE + 1} with {len(batch)} clusters")

                # Process batch concurrently
                batch_tasks = []
                for cluster in batch:
                    cluster_id_str = str(cluster.id)

                    # Mark as active in state
                    sync_state["active_syncs"][cluster_id_str] = {
                        "started_at": current_time.isoformat(),
                        "workflow_id": None,
                    }

                    # Create async task for this cluster
                    batch_tasks.append(cls._sync_single_cluster(cluster, sync_state))

                # Execute batch concurrently and collect results
                import asyncio

                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

                # Process batch results
                for cluster, result in zip(batch, batch_results, strict=False):
                    cluster_id_str = str(cluster.id)

                    # Remove from active syncs
                    sync_state["active_syncs"].pop(cluster_id_str, None)

                    if isinstance(result, Exception):
                        logger.error(f"Failed to sync cluster {cluster_id_str}: {result}")
                        failed_count += 1
                        sync_state["failed_clusters"][cluster_id_str] = {
                            "error": str(result),
                            "failed_at": current_time.isoformat(),
                        }
                    else:
                        update_count += 1
                        sync_state["last_sync_times"][cluster_id_str] = current_time.isoformat()
                        # Clear from failed if it was there
                        sync_state["failed_clusters"].pop(cluster_id_str, None)

                # Save state after each batch (if state store is available)
                if use_state_store:
                    try:
                        await dapr_service.save_to_statestore(
                            store_name=app_settings.statestore_name, key=STATE_STORE_KEY, value=sync_state
                        )
                    except Exception as e:
                        logger.debug(f"Could not save sync state to state store: {e}")

            # Final state save (if state store is available)
            if use_state_store:
                try:
                    await dapr_service.save_to_statestore(
                        store_name=app_settings.statestore_name, key=STATE_STORE_KEY, value=sync_state
                    )
                    logger.debug("Sync state saved successfully to state store")
                except Exception as e:
                    logger.debug(f"Could not save final sync state to state store: {e}")

            message = f"Triggered node status update for {update_count} clusters"
            if failed_count > 0:
                message += f" ({failed_count} failed)"

            logger.info(message)
            return SuccessResponse(
                message=message,
                param={
                    "total": len(active_clusters),
                    "updated": update_count,
                    "failed": failed_count,
                    "skipped": len(active_clusters) - len(clusters_to_sync),
                    "batch_size": BATCH_SIZE,
                },
            )

        except Exception as e:
            logger.exception("Failed to trigger periodic node status update")
            return ErrorResponse(message=f"Failed to trigger periodic node status update: {str(e)}")

    @classmethod
    async def _sync_single_cluster(cls, cluster, sync_state: dict) -> bool:
        """Sync a single cluster's node status by directly calling update_node_status.

        This method performs synchronous updates instead of spawning workflows,
        ensuring true batch processing with controlled concurrency.

        Args:
            cluster: The cluster to sync
            sync_state: The current sync state dictionary

        Returns:
            bool: True if successful, raises exception on failure
        """
        from budmicroframe.commons.schemas import (
            NotificationCategory,
            NotificationContent,
            NotificationPayload,
            NotificationRequest,
            NotificationType,
            WorkflowStatus,
        )
        from budmicroframe.shared.dapr_service import DaprService, DaprServiceCrypto

        cluster_id_str = str(cluster.id)
        logger.debug(f"Updating node status for cluster {cluster_id_str}")

        try:
            # Decrypt config if needed
            config_dict = {}
            if cluster.configuration:
                try:
                    with DaprServiceCrypto() as dapr_service:
                        configuration_decrypted = dapr_service.decrypt_data(cluster.configuration)
                        config_dict = json.loads(configuration_decrypted)
                except Exception as e:
                    logger.error(f"Failed to decrypt config for cluster {cluster_id_str}: {e}")
                    raise

            # Call update_node_status directly (synchronous within this batch)
            cluster_status, nodes_info_present, node_info, node_status_change = await cls.update_node_status(
                cluster.id, config_dict
            )

            # Send notification if status changed
            if cluster_status != cluster.status or not nodes_info_present or node_status_change:
                logger.info(f"Cluster {cluster_id_str} status changed, sending notification")

                event_name = "cluster-status-update"
                content = NotificationContent(
                    title="Cluster status updated",
                    message=f"Cluster {cluster_id_str} status updated",
                    status=WorkflowStatus.COMPLETED,
                    result={"cluster_id": cluster_id_str, "status": cluster_status, "node_info": node_info},
                )
                notification_request = NotificationRequest(
                    notification_type=NotificationType.EVENT,
                    name=event_name,
                    payload=NotificationPayload(
                        category=NotificationCategory.INTERNAL,
                        type=event_name,
                        event="results",
                        content=content,
                        workflow_id="",  # No workflow for periodic updates
                    ),
                    topic_keys=["budAppMessages"],
                )
                with DaprService() as dapr_service:
                    dapr_service.publish_to_topic(
                        data=notification_request.model_dump(mode="json"),
                        target_topic_name="budAppMessages",
                        target_name=None,
                        event_type=notification_request.payload.type,
                    )

            # Handle successful cluster connection
            await cls._handle_cluster_success(cluster.id)

            logger.debug(f"Successfully updated cluster {cluster_id_str}")
            return True
        except Exception as e:
            logger.error(f"Failed to update cluster {cluster_id_str}: {e}")

            # Handle cluster failure
            await cls._handle_cluster_failure(cluster.id)

            raise


def _should_skip_duplicate_device(device: Dict[str, Any], seen_device_uuids: set, node_name: str) -> bool:
    """Check if device should be skipped due to duplicate UUID.

    This helper function centralizes device deduplication logic to prevent
    duplicate devices when multiple hardware_info entries reference the same
    physical device (common with HAMI GPU time-slicing).

    Args:
        device: Device dictionary to check
        seen_device_uuids: Set of UUIDs already seen (modified in-place if new UUID found)
        node_name: Name of the node (for logging)

    Returns:
        True if device should be skipped (duplicate), False otherwise
    """
    device_uuid = device.get("device_uuid")
    if device_uuid:
        if device_uuid in seen_device_uuids:
            logger.warning(f"Skipping duplicate device with UUID {device_uuid} on node {node_name}")
            return True
        seen_device_uuids.add(device_uuid)
    return False


def _add_hami_fields_to_device(source: Dict[str, Any], target: Dict[str, Any]) -> None:
    """Add HAMI-specific fields from source dict to target dict if present.

    This helper function centralizes the logic for adding GPU time-slicing
    metrics from HAMI to device dictionaries. It copies the following fields
    if they exist in the source:
    - core_utilization_percent: GPU compute allocated (%)
    - memory_utilization_percent: GPU memory allocated (%)
    - memory_allocated_gb: Allocated GPU memory in GB
    - cores_allocated_percent: Allocated GPU cores (%)
    - shared_containers_count: Number of containers sharing the GPU
    - hardware_mode: GPU hardware mode (dedicated/shared)
    - device_uuid: Unique GPU device identifier
    - last_metrics_update: Timestamp of last metrics update

    Args:
        source: Source dictionary containing HAMI fields
        target: Target dictionary to add HAMI fields to (modified in-place)
    """
    hami_fields = [
        "core_utilization_percent",
        "memory_utilization_percent",
        "memory_allocated_gb",
        "cores_allocated_percent",
        "shared_containers_count",
        "hardware_mode",
        "device_uuid",
        "last_metrics_update",
    ]

    for field in hami_fields:
        if field in source:
            target[field] = source[field]


class ClusterService(SessionMixin):
    async def _get_cluster(self, cluster_id: UUID, missing_ok: bool = False) -> ClusterModel:
        """Get cluster details from db."""
        return await ClusterDataManager(self.session).retrieve_cluster_by_fields(
            {"id": cluster_id}, missing_ok=missing_ok
        )

    async def _check_duplicate_config(
        self, server_url: str, platform: ClusterPlatformEnum
    ) -> Union[SuccessResponse, ErrorResponse]:
        """Check duplicate config.

        1. check if cluster is registering, give notification try again later.
        2. check if cluster is not_available, give notification delete and try again later.

        Args:
            server_url (str): The server URL of the cluster.
            platform (ClusterPlatformEnum): The platform of the cluster.

        Returns:
            Union[SuccessResponse, ErrorResponse]: A response object containing the success or error message.
        """
        # Handle the case where multiple clusters might exist with same server_url and platform
        # This shouldn't happen normally but can occur due to failed cleanups
        try:
            # Use a direct query to handle multiple results
            from sqlalchemy import select

            from .models import Cluster as ClusterModel

            stmt = select(ClusterModel).filter_by(server_url=server_url, platform=platform)
            result = self.session.execute(stmt)
            db_clusters = result.scalars().all()

            if not db_clusters:
                return SuccessResponse(message="No duplicate cluster found")

            # If multiple clusters found, clean up all NOT_AVAILABLE ones
            if len(db_clusters) > 1:
                logger.warning(f"Found {len(db_clusters)} clusters with same server_url and platform, cleaning up")
                clusters_to_delete = []
                available_cluster = None
                registering_cluster = None

                for cluster in db_clusters:
                    if cluster.status == ClusterStatusEnum.AVAILABLE:
                        available_cluster = cluster
                    elif cluster.status == ClusterStatusEnum.REGISTERING:
                        registering_cluster = cluster
                    elif cluster.status == ClusterStatusEnum.NOT_AVAILABLE:
                        clusters_to_delete.append(cluster)

                # Delete all NOT_AVAILABLE clusters
                for cluster in clusters_to_delete:
                    try:
                        await ClusterDataManager(self.session).delete_cluster(cluster.id)
                        logger.info(f"Deleted duplicate cluster {cluster.id} with status NOT_AVAILABLE")
                    except Exception as e:
                        logger.error(f"Failed to delete duplicate cluster {cluster.id}: {e}")

                # Check if there's still a blocking cluster
                if registering_cluster:
                    # Check if REGISTERING cluster is stuck (older than 15 minutes)
                    from datetime import datetime, timedelta, timezone

                    registration_timeout_minutes = 15  # Timeout for stuck registrations
                    timeout_threshold = datetime.now(timezone.utc) - timedelta(minutes=registration_timeout_minutes)

                    if registering_cluster.created_at < timeout_threshold:
                        # Cluster has been in REGISTERING state too long, clean it up
                        logger.warning(
                            f"Found stuck REGISTERING cluster {registering_cluster.id} created at {registering_cluster.created_at}, "
                            f"cleaning up for re-registration (timeout: {registration_timeout_minutes} minutes)"
                        )
                        try:
                            await ClusterDataManager(self.session).delete_cluster(registering_cluster.id)
                            logger.info(f"Successfully deleted stuck REGISTERING cluster {registering_cluster.id}")
                            # Continue with registration since blocking cluster is removed
                        except Exception as e:
                            logger.error(f"Failed to delete stuck REGISTERING cluster {registering_cluster.id}: {e}")
                            # Fall through to return the original error
                            return ErrorResponse(
                                message="This cluster is already registering. Please try again later.",
                                code=status.HTTP_400_BAD_REQUEST,
                                param={"cluster_id": str(registering_cluster.id)},
                            )
                    else:
                        return ErrorResponse(
                            message="This cluster is already registering. Please try again later.",
                            code=status.HTTP_400_BAD_REQUEST,
                            param={"cluster_id": str(registering_cluster.id)},
                        )
                elif available_cluster:
                    return ErrorResponse(
                        message="This cluster is already registered. Please delete it and try again.",
                        code=status.HTTP_400_BAD_REQUEST,
                        param={"cluster_id": str(available_cluster.id)},
                    )
                else:
                    return SuccessResponse(
                        message="Cleaned up duplicate failed registrations, proceeding with new registration"
                    )

            # Single cluster found, handle as before
            db_cluster = db_clusters[0]
            if db_cluster.status == ClusterStatusEnum.REGISTERING:
                # Check if REGISTERING cluster is stuck (older than 15 minutes)
                from datetime import datetime, timedelta, timezone

                registration_timeout_minutes = 15  # Timeout for stuck registrations
                timeout_threshold = datetime.now(timezone.utc) - timedelta(minutes=registration_timeout_minutes)

                if db_cluster.created_at < timeout_threshold:
                    # Cluster has been in REGISTERING state too long, clean it up
                    logger.warning(
                        f"Found stuck REGISTERING cluster {db_cluster.id} created at {db_cluster.created_at}, "
                        f"cleaning up for re-registration (timeout: {registration_timeout_minutes} minutes)"
                    )
                    try:
                        await ClusterDataManager(self.session).delete_cluster(db_cluster.id)
                        logger.info(f"Successfully deleted stuck REGISTERING cluster {db_cluster.id}")
                        return SuccessResponse(
                            message="Cleaned up stuck registration, proceeding with new registration"
                        )
                    except Exception as e:
                        logger.error(f"Failed to delete stuck REGISTERING cluster {db_cluster.id}: {e}")
                        # Fall through to return the original error

                return ErrorResponse(
                    message="This cluster is already registering. Please try again later.",
                    code=status.HTTP_400_BAD_REQUEST,
                    param={"cluster_id": str(db_cluster.id)},
                )
            elif db_cluster.status == ClusterStatusEnum.AVAILABLE:
                return ErrorResponse(
                    message="This cluster is already registered. Please delete it and try again.",
                    code=status.HTTP_400_BAD_REQUEST,
                    param={"cluster_id": str(db_cluster.id)},
                )
            elif db_cluster.status == ClusterStatusEnum.NOT_AVAILABLE:
                # Allow re-registration by deleting the failed cluster entry
                logger.info(
                    f"Found failed cluster {db_cluster.id} with status NOT_AVAILABLE, cleaning up for re-registration"
                )
                try:
                    await ClusterDataManager(self.session).delete_cluster(db_cluster.id)
                    logger.info(f"Successfully deleted failed cluster {db_cluster.id}")
                    return SuccessResponse(
                        message="Cleaned up previous failed registration, proceeding with new registration"
                    )
                except Exception as e:
                    logger.error(f"Failed to clean up cluster {db_cluster.id}: {e}")
                    return ErrorResponse(
                        message="Failed to clean up previous registration. Please manually delete the cluster and try again.",
                        code=status.HTTP_400_BAD_REQUEST,
                        param={"cluster_id": str(db_cluster.id)},
                    )

        except Exception as e:
            logger.error(f"Error checking duplicate config: {e}")
            return ErrorResponse(
                message="Error checking for duplicate clusters. Please try again.",
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return SuccessResponse(message="No duplicate cluster found")

    async def register_cluster(self, cluster: ClusterCreateRequest) -> Union[WorkflowMetadataResponse, ErrorResponse]:
        """Register cluster.

        This function triggers the process of registering a new cluster.

        Args:
            cluster (ClusterCreateRequest): The request object contains metadata for the cluster.

        Returns:
            Union[WorkflowMetadataResponse, ErrorResponse]: A response object containing the workflow id and steps.
        """
        logger.info(f"Registering cluster: {cluster.name}")

        response: Union[WorkflowMetadataResponse, ErrorResponse]

        from .workflows import RegisterClusterWorkflow

        try:
            if cluster.cluster_type == "ON_PERM":
                cluster.ingress_url = str(cluster.ingress_url)
            response = await RegisterClusterWorkflow().__call__(cluster)
        except Exception as e:
            logger.error(f"Error registering cluster: {e}")
            # Return ErrorResponse instead of raising it since it's not an Exception
            return ErrorResponse(message=f"Error registering cluster: {e}")
        return response

    async def update_cluster_registration_status(self, cluster_id: UUID, data: ClusterStatusUpdate) -> None:
        """Update cluster registration status."""
        logger.info(f"Updating cluster registration status for cluster_id: {cluster_id}, data: {data}")
        db_cluster = await ClusterDataManager(self.session).retrieve_cluster_by_fields(
            {"id": cluster_id}, missing_ok=False
        )
        await ClusterDataManager(self.session).update_cluster_by_fields(db_cluster, data.model_dump(exclude_none=True))
        logger.info(f"Cluster: {db_cluster.id} updated in database")

    async def delete_cluster(
        self, cluster_delete_request: ClusterDeleteRequest
    ) -> Union[WorkflowMetadataResponse, ErrorResponse]:
        """Delete a cluster from the system."""
        logger.info(f"Deleting cluster with id: {cluster_delete_request.cluster_id}")

        from .workflows import DeleteClusterWorkflow

        try:
            db_cluster = await self._get_cluster(cluster_delete_request.cluster_id, missing_ok=True)
            cluster_delete_request.cluster_config = db_cluster.config_file_dict if db_cluster else None
            cluster_delete_request.platform = db_cluster.platform if db_cluster else None
            response = await DeleteClusterWorkflow().__call__(cluster_delete_request)
        except Exception as e:
            logger.error(f"Error deleting cluster: {e}")
            if isinstance(e, HTTPException):
                raise e
            # Return ErrorResponse instead of raising it since it's not an Exception
            return ErrorResponse(message=f"Error deleting cluster: {e}")
        return response

    def cancel_cluster_registration(
        self, workflow_id: UUID, background_tasks: BackgroundTasks
    ) -> Union[SuccessResponse, ErrorResponse]:
        """Cancel a cluster registration."""
        stop_workflow_response = asyncio.run(DaprWorkflow().stop_workflow(str(workflow_id)))
        if stop_workflow_response.code == 200:
            save_workflow_status_in_statestore(str(workflow_id), WorkflowStatus.TERMINATED.value)
            background_tasks.add_task(ClusterOpsService.cancel_cluster_registration, workflow_id)
        return stop_workflow_response

    # Get Cluster Events Count By Node With Cluster ID
    async def get_cluster_events_count_by_node(
        self, cluster_id: UUID
    ) -> Union[NodeEventsCountSuccessResponse, ErrorResponse]:
        """Get cluster events count by node."""
        logger.info(f"Collecting Node Events Count for Cluster: {cluster_id}")

        with DBSession() as session:
            # Get Cluster Info
            db_cluster = await ClusterDataManager(session).retrieve_cluster_by_fields(
                {"id": cluster_id}, missing_ok=False
            )
            if db_cluster is None:
                return ErrorResponse(message="Cluster not found")

            node_metrics = await get_node_wise_events_count(db_cluster.config_file_dict, db_cluster.platform)
            logger.info(f"Node metrics: {node_metrics}")

            # node_info = await get_node_info(db_cluster.config_file_dict, db_cluster.platform)
            # logger.info(f"Node info: {node_info}")

            return NodeEventsCountSuccessResponse(message="Node events count collected", data=node_metrics)

    # Get Node Wise Events with Cluster ID
    async def get_node_wise_events(
        self, cluster_id: UUID, node_hostname: str
    ) -> Union[NodeEventsResponse, ErrorResponse]:
        """Get node-wise events with pagination and total event count for the cluster."""
        logger.info(f"Collecting Node Events for Cluster: {cluster_id} and Node: {node_hostname}")

        with DBSession() as session:
            # Get Cluster Info
            db_cluster = await ClusterDataManager(session).retrieve_cluster_by_fields(
                {"id": cluster_id}, missing_ok=False
            )

            logger.info(f"DB Cluster: {db_cluster.platform}")

            if db_cluster is None:
                return ErrorResponse(message="Cluster not found")

            node_events = await get_node_wise_events(
                config=db_cluster.config_file_dict, node_hostname=node_hostname, platform=db_cluster.platform
            )
            logger.info(f"Node events: {node_events}")

            return NodeEventsResponse(message="Node events collected", data=node_events)

    async def edit_cluster(self, cluster_id: UUID, data: Dict[str, Any]) -> ClusterModel:
        """Edit cloud model by validating and updating specific fields, and saving an uploaded file if provided."""
        # Retrieve existing model
        db_cluster = await self._get_cluster(cluster_id, missing_ok=False)
        db_cluster = await ClusterDataManager(self.session).update_cluster_by_fields(db_cluster, data)
        return db_cluster

    async def get_cluster_nodes(self, cluster_id: UUID) -> Union[SuccessResponse, ErrorResponse]:
        """Get cluster nodes."""
        nodes = await ClusterNodeInfoDataManager(self.session).get_cluster_node_info_by_cluster_id(cluster_id)
        nodes_list = [ClusterNodeInfoResponse.model_validate(node) for node in nodes]
        return SuccessResponse(param={"nodes": nodes_list}, message="Cluster nodes fetched successfully")

    async def get_cluster_config(self, cluster_id: UUID) -> Union[SuccessResponse, ErrorResponse]:
        """Get all clusters."""
        db_cluster = await ClusterDataManager(self.session).retrieve_cluster_by_fields(
            {"id": cluster_id, "status": ClusterStatusEnum.AVAILABLE}
        )

        logger.info(f"DB Clusters: {db_cluster}")
        cluster_details = {
            "platform": db_cluster.platform,
            "status": db_cluster.status,
            "configuration": db_cluster.configuration,
            "ingress_url": db_cluster.ingress_url,
        }
        return SuccessResponse(
            param={"cluster_details": cluster_details}, message="Cluster details fetched successfully"
        )

    async def get_cluster_storage_classes(self, cluster_id: UUID) -> Union[SuccessResponse, ErrorResponse]:
        """Get all storage classes available in the cluster.

        Args:
            cluster_id: The ID of the cluster to get storage classes from.

        Returns:
            SuccessResponse: A response object containing the list of storage classes.
            ErrorResponse: A response object containing the error message.
        """
        try:
            # Get cluster details from database
            db_cluster = await ClusterDataManager(self.session).retrieve_cluster_by_fields(
                {"id": cluster_id, "status": ClusterStatusEnum.AVAILABLE}
            )
            if db_cluster is None:
                return ErrorResponse(message="Cluster not found or not available")

            # Get storage classes from the cluster using KubernetesHandler
            from .kubernetes import KubernetesHandler

            k8s_handler = KubernetesHandler(db_cluster.config_file_dict, db_cluster.ingress_url)
            storage_classes = k8s_handler.get_storage_classes()

            logger.info(f"Found {len(storage_classes)} storage classes for cluster {cluster_id}")

            return SuccessResponse(
                param={"storage_classes": storage_classes}, message="Storage classes fetched successfully"
            )

        except Exception as e:
            logger.error(f"Error fetching storage classes for cluster {cluster_id}: {e}")
            return ErrorResponse(message=f"Failed to fetch storage classes: {str(e)}")
