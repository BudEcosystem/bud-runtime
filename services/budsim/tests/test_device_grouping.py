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

"""Unit tests for device grouping functionality."""

import pytest
from typing import List, Dict, Any


class TestDeviceGrouping:
    """Test device grouping logic without full service dependencies."""

    @staticmethod
    def _group_devices_by_type_across_cluster(
        cluster_info: List[Dict[str, Any]], cluster_topology: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        """Minimal implementation of device grouping for testing."""
        device_groups = {}

        for cluster in cluster_info:
            cluster_id = cluster.get("cluster_id", "unknown")

            for node in cluster.get("nodes", []):
                node_id = node.get("node_id", "unknown")

                for device in node.get("devices", []):
                    device_type = device["type"]

                    if device_type not in device_groups:
                        device_groups[device_type] = {
                            "devices": [],
                            "cluster_id": cluster_id,
                            "node_distribution": {},
                            "devices_by_node": {},
                            "max_devices_per_node": 0,
                            "type": device_type,
                        }

                    # Add device to group
                    device_groups[device_type]["devices"].append(device)

                    # Update node distribution
                    if node_id not in device_groups[device_type]["node_distribution"]:
                        device_groups[device_type]["node_distribution"][node_id] = 0
                        device_groups[device_type]["devices_by_node"][node_id] = []

                    device_groups[device_type]["node_distribution"][node_id] += 1
                    device_groups[device_type]["devices_by_node"][node_id].append(device)

        # Calculate max devices per node for each type
        for device_type, group_info in device_groups.items():
            if group_info["node_distribution"]:
                group_info["max_devices_per_node"] = max(group_info["node_distribution"].values())

        return device_groups

    def test_homogeneous_cluster(self):
        """Test grouping in a homogeneous cluster (all same device type)."""
        cluster_info = [
            {
                "cluster_id": "cluster1",
                "nodes": [
                    {
                        "node_id": "node1",
                        "devices": [
                            {"id": f"gpu{i}", "type": "cuda", "memory_in_GB": 80}
                            for i in range(8)
                        ],
                    },
                    {
                        "node_id": "node2",
                        "devices": [
                            {"id": f"gpu{i}", "type": "cuda", "memory_in_GB": 80}
                            for i in range(8, 16)
                        ],
                    },
                ],
            }
        ]

        device_groups = self._group_devices_by_type_across_cluster(cluster_info, {})

        assert "cuda" in device_groups
        assert len(device_groups) == 1
        assert len(device_groups["cuda"]["devices"]) == 16
        assert device_groups["cuda"]["node_distribution"] == {"node1": 8, "node2": 8}
        assert device_groups["cuda"]["max_devices_per_node"] == 8

    def test_heterogeneous_cluster(self):
        """Test grouping in a heterogeneous cluster (mixed device types)."""
        cluster_info = [
            {
                "cluster_id": "cluster1",
                "nodes": [
                    {
                        "node_id": "node1",
                        "devices": [
                            {"id": f"gpu{i}", "type": "cuda", "memory_in_GB": 80}
                            for i in range(8)
                        ],
                    },
                    {
                        "node_id": "node2",
                        "devices": [
                            {"id": f"hpu{i}", "type": "hpu", "memory_in_GB": 96}
                            for i in range(8)
                        ],
                    },
                    {
                        "node_id": "node3",
                        "devices": [
                            {"id": f"cpu{i}", "type": "cpu", "memory_in_GB": 256}
                            for i in range(32)
                        ],
                    },
                ],
            }
        ]

        device_groups = self._group_devices_by_type_across_cluster(cluster_info, {})

        assert len(device_groups) == 3
        assert "cuda" in device_groups
        assert "hpu" in device_groups
        assert "cpu" in device_groups

        assert len(device_groups["cuda"]["devices"]) == 8
        assert device_groups["cuda"]["node_distribution"] == {"node1": 8}
        assert device_groups["cuda"]["max_devices_per_node"] == 8

        assert len(device_groups["hpu"]["devices"]) == 8
        assert device_groups["hpu"]["node_distribution"] == {"node2": 8}

        assert len(device_groups["cpu"]["devices"]) == 32
        assert device_groups["cpu"]["node_distribution"] == {"node3": 32}
        assert device_groups["cpu"]["max_devices_per_node"] == 32

    def test_uneven_distribution(self):
        """Test grouping with uneven device distribution across nodes."""
        cluster_info = [
            {
                "cluster_id": "cluster1",
                "nodes": [
                    {
                        "node_id": "node1",
                        "devices": [
                            {"id": f"gpu{i}", "type": "cuda", "memory_in_GB": 80}
                            for i in range(8)
                        ],
                    },
                    {
                        "node_id": "node2",
                        "devices": [
                            {"id": f"gpu{i}", "type": "cuda", "memory_in_GB": 80}
                            for i in range(8, 12)
                        ],
                    },
                    {
                        "node_id": "node3",
                        "devices": [
                            {"id": f"gpu{i}", "type": "cuda", "memory_in_GB": 40}
                            for i in range(12, 14)
                        ],
                    },
                ],
            }
        ]

        device_groups = self._group_devices_by_type_across_cluster(cluster_info, {})

        assert "cuda" in device_groups
        assert len(device_groups["cuda"]["devices"]) == 14
        assert device_groups["cuda"]["node_distribution"] == {"node1": 8, "node2": 4, "node3": 2}
        assert device_groups["cuda"]["max_devices_per_node"] == 8

    def test_empty_cluster(self):
        """Test grouping with empty cluster."""
        cluster_info = []
        device_groups = self._group_devices_by_type_across_cluster(cluster_info, {})
        assert len(device_groups) == 0

    def test_nodes_without_devices(self):
        """Test grouping when some nodes have no devices."""
        cluster_info = [
            {
                "cluster_id": "cluster1",
                "nodes": [
                    {
                        "node_id": "node1",
                        "devices": [
                            {"id": f"gpu{i}", "type": "cuda", "memory_in_GB": 80}
                            for i in range(8)
                        ],
                    },
                    {
                        "node_id": "node2",
                        "devices": [],  # Empty node
                    },
                ],
            }
        ]

        device_groups = self._group_devices_by_type_across_cluster(cluster_info, {})

        assert "cuda" in device_groups
        assert len(device_groups["cuda"]["devices"]) == 8
        assert device_groups["cuda"]["node_distribution"] == {"node1": 8}
        assert "node2" not in device_groups["cuda"]["node_distribution"]
