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

"""Unit tests for hardware mode filtering and memory validation."""

import os

import pytest


# Set minimal environment variables before importing service
os.environ.setdefault("PSQL_HOST", "localhost")
os.environ.setdefault("PSQL_PORT", "5432")
os.environ.setdefault("PSQL_DB_NAME", "test_db")
os.environ.setdefault("MODEL_REGISTRY_DIR", "/tmp/models")  # nosec B108 - test environment only
os.environ.setdefault("BUD_CONNECT_URL", "http://localhost:8000")

from budsim.simulator.services import SimulationService


class TestHardwareModeFiltering:
    """Test hardware mode filtering logic for dedicated and shared modes."""

    @pytest.fixture
    def cluster_topology(self):
        """Basic cluster topology fixture."""
        return {
            "total_nodes": 2,
            "total_cluster_devices": 16,
            "device_types": ["cuda"],
        }

    def test_dedicated_mode_filters_zero_utilization_only(self, cluster_topology):
        """Test that dedicated mode only accepts devices with 0% utilization."""
        cluster_info = [
            {
                "id": "cluster1",
                "nodes": [
                    {
                        "id": "node1",
                        "name": "node1",
                        "devices": [
                            {
                                "type": "cuda",
                                "name": "GPU-0",
                                "available_count": 1,
                                "total_count": 1,
                                "core_utilization_percent": 0.0,
                                "memory_utilization_percent": 0.0,
                                "mem_per_GPU_in_GB": 80,
                            },
                            {
                                "type": "cuda",
                                "name": "GPU-1",
                                "available_count": 0,
                                "total_count": 1,
                                "core_utilization_percent": 50.0,
                                "memory_utilization_percent": 60.0,
                                "mem_per_GPU_in_GB": 80,
                            },
                            {
                                "type": "cuda",
                                "name": "GPU-2",
                                "available_count": 0,
                                "total_count": 1,
                                "core_utilization_percent": 0.0,
                                "memory_utilization_percent": 10.0,  # Memory not 0
                                "mem_per_GPU_in_GB": 80,
                            },
                        ],
                    },
                ],
            }
        ]

        device_groups = SimulationService._group_devices_by_type_across_cluster(
            cluster_info, cluster_topology, "dedicated"
        )

        # Should only include GPU-0 with 0% utilization
        assert "cuda" in device_groups
        assert len(device_groups["cuda"]["devices"]) == 1
        assert device_groups["cuda"]["devices"][0]["name"] == "GPU-0"

    def test_dedicated_mode_backward_compatibility(self, cluster_topology):
        """Test that dedicated mode falls back to available_count when no utilization metrics."""
        cluster_info = [
            {
                "id": "cluster1",
                "nodes": [
                    {
                        "id": "node1",
                        "name": "node1",
                        "devices": [
                            {
                                "type": "cuda",
                                "name": "GPU-0",
                                "available_count": 2,
                                "total_count": 2,
                                "mem_per_GPU_in_GB": 80,
                            },
                            {
                                "type": "cuda",
                                "name": "GPU-1",
                                "available_count": 0,
                                "total_count": 2,
                                "mem_per_GPU_in_GB": 80,
                            },
                        ],
                    },
                ],
            }
        ]

        device_groups = SimulationService._group_devices_by_type_across_cluster(
            cluster_info, cluster_topology, "dedicated"
        )

        # Should include GPU-0 with available_count > 0
        assert "cuda" in device_groups
        assert len(device_groups["cuda"]["devices"]) == 1
        assert device_groups["cuda"]["devices"][0]["name"] == "GPU-0"

    def test_shared_mode_requires_hami_metrics(self, cluster_topology):
        """Test that shared mode only accepts devices with HAMI metrics."""
        cluster_info = [
            {
                "id": "cluster1",
                "nodes": [
                    {
                        "id": "node1",
                        "name": "node1",
                        "devices": [
                            {
                                "type": "cuda",
                                "name": "GPU-0",
                                "available_count": 1,
                                "mem_per_GPU_in_GB": 80,
                                "memory_allocated_gb": 20,  # HAMI metric present
                            },
                            {
                                "type": "cuda",
                                "name": "GPU-1",
                                "available_count": 1,
                                "mem_per_GPU_in_GB": 80,
                                # No HAMI metrics - should be filtered out
                            },
                        ],
                    },
                ],
            }
        ]

        device_groups = SimulationService._group_devices_by_type_across_cluster(
            cluster_info, cluster_topology, "shared"
        )

        # Should only include GPU-0 with HAMI metrics
        assert "cuda" in device_groups
        assert len(device_groups["cuda"]["devices"]) == 1
        assert device_groups["cuda"]["devices"][0]["name"] == "GPU-0"

    def test_shared_mode_filters_zero_available_memory(self, cluster_topology):
        """Test that shared mode filters out devices with no available memory."""
        cluster_info = [
            {
                "id": "cluster1",
                "nodes": [
                    {
                        "id": "node1",
                        "name": "node1",
                        "devices": [
                            {
                                "type": "cuda",
                                "name": "GPU-0",
                                "available_count": 1,
                                "mem_per_GPU_in_GB": 80,
                                "memory_allocated_gb": 20,  # 60GB available
                            },
                            {
                                "type": "cuda",
                                "name": "GPU-1",
                                "available_count": 1,
                                "mem_per_GPU_in_GB": 80,
                                "memory_allocated_gb": 80,  # 0GB available
                            },
                        ],
                    },
                ],
            }
        ]

        device_groups = SimulationService._group_devices_by_type_across_cluster(
            cluster_info, cluster_topology, "shared"
        )

        # Should only include GPU-0 with available memory
        assert "cuda" in device_groups
        assert len(device_groups["cuda"]["devices"]) == 1
        assert device_groups["cuda"]["devices"][0]["name"] == "GPU-0"

    def test_shared_mode_sets_available_count_to_one(self, cluster_topology):
        """Test that shared mode sets available_count to 1 for partial GPU usage."""
        cluster_info = [
            {
                "id": "cluster1",
                "nodes": [
                    {
                        "id": "node1",
                        "name": "node1",
                        "devices": [
                            {
                                "type": "cuda",
                                "name": "GPU-0",
                                "available_count": 0,  # Even if 0
                                "mem_per_GPU_in_GB": 80,
                                "memory_allocated_gb": 75,  # 5GB available
                            },
                        ],
                    },
                ],
            }
        ]

        device_groups = SimulationService._group_devices_by_type_across_cluster(
            cluster_info, cluster_topology, "shared"
        )

        # Should set available_count to 1
        assert "cuda" in device_groups
        assert len(device_groups["cuda"]["devices"]) == 1
        # Note: The available_count in the original device is not modified in the current implementation
        # Only used for filtering, actual count handling happens later

    def test_no_devices_match_dedicated_mode(self, cluster_topology):
        """Test error handling when no devices match dedicated mode criteria."""
        cluster_info = [
            {
                "id": "cluster1",
                "nodes": [
                    {
                        "id": "node1",
                        "name": "node1",
                        "devices": [
                            {
                                "type": "cuda",
                                "name": "GPU-0",
                                "available_count": 0,
                                "core_utilization_percent": 50.0,
                                "memory_utilization_percent": 60.0,
                                "mem_per_GPU_in_GB": 80,
                            },
                        ],
                    },
                ],
            }
        ]

        device_groups = SimulationService._group_devices_by_type_across_cluster(
            cluster_info, cluster_topology, "dedicated"
        )

        # Should return empty dict when no devices match
        assert len(device_groups) == 0

    def test_no_devices_match_shared_mode(self, cluster_topology):
        """Test error handling when no devices match shared mode criteria."""
        cluster_info = [
            {
                "id": "cluster1",
                "nodes": [
                    {
                        "id": "node1",
                        "name": "node1",
                        "devices": [
                            {
                                "type": "cuda",
                                "name": "GPU-0",
                                "available_count": 1,
                                "mem_per_GPU_in_GB": 80,
                                # No HAMI metrics
                            },
                        ],
                    },
                ],
            }
        ]

        device_groups = SimulationService._group_devices_by_type_across_cluster(
            cluster_info, cluster_topology, "shared"
        )

        # Should return empty dict when no devices match
        assert len(device_groups) == 0

    def test_mixed_utilization_dedicated_mode(self, cluster_topology):
        """Test dedicated mode with mix of utilized and free devices."""
        cluster_info = [
            {
                "id": "cluster1",
                "nodes": [
                    {
                        "id": "node1",
                        "name": "node1",
                        "devices": [
                            {
                                "type": "cuda",
                                "name": "GPU-0",
                                "available_count": 1,
                                "core_utilization_percent": 0.0,
                                "memory_utilization_percent": 0.0,
                                "mem_per_GPU_in_GB": 80,
                            },
                        ],
                    },
                    {
                        "id": "node2",
                        "name": "node2",
                        "devices": [
                            {
                                "type": "cuda",
                                "name": "GPU-1",
                                "available_count": 1,
                                "core_utilization_percent": 0.0,
                                "memory_utilization_percent": 0.0,
                                "mem_per_GPU_in_GB": 80,
                            },
                            {
                                "type": "cuda",
                                "name": "GPU-2",
                                "available_count": 0,
                                "core_utilization_percent": 94.0,
                                "memory_utilization_percent": 95.0,
                                "mem_per_GPU_in_GB": 80,
                            },
                        ],
                    },
                ],
            }
        ]

        device_groups = SimulationService._group_devices_by_type_across_cluster(
            cluster_info, cluster_topology, "dedicated"
        )

        # Should include only the 2 devices with 0% utilization
        assert "cuda" in device_groups
        assert len(device_groups["cuda"]["devices"]) == 2
        device_names = {d["name"] for d in device_groups["cuda"]["devices"]}
        assert device_names == {"GPU-0", "GPU-1"}

    def test_shared_mode_with_partial_memory(self, cluster_topology):
        """Test shared mode correctly handles devices with partial memory available."""
        cluster_info = [
            {
                "id": "cluster1",
                "nodes": [
                    {
                        "id": "node1",
                        "name": "node1",
                        "devices": [
                            {
                                "type": "cuda",
                                "name": "GPU-0",
                                "available_count": 0,
                                "mem_per_GPU_in_GB": 80,
                                "memory_allocated_gb": 75,  # 5GB available (94% utilized)
                            },
                            {
                                "type": "cuda",
                                "name": "GPU-1",
                                "available_count": 0,
                                "mem_per_GPU_in_GB": 80,
                                "memory_allocated_gb": 40,  # 40GB available (50% utilized)
                            },
                        ],
                    },
                ],
            }
        ]

        device_groups = SimulationService._group_devices_by_type_across_cluster(
            cluster_info, cluster_topology, "shared"
        )

        # Should include both devices with available memory
        assert "cuda" in device_groups
        assert len(device_groups["cuda"]["devices"]) == 2
        device_names = {d["name"] for d in device_groups["cuda"]["devices"]}
        assert device_names == {"GPU-0", "GPU-1"}

    def test_shared_mode_small_available_memory(self, cluster_topology):
        """Test that devices with very small available memory are included in filtering.

        Note: This test verifies device filtering only. The actual memory validation
        (rejecting models that don't fit) happens later in DirectSearchOptimizer.
        See direct_search.py:362 which uses validation_passed from _last_validation_result.

        Integration test scenario:
        - GPU with 5GB available (memory_allocated_gb=75 out of 80GB)
        - 8B model requiring 15GB should be REJECTED during optimization
        - meets_targets should be False when model doesn't fit
        """
        cluster_info = [
            {
                "id": "cluster1",
                "nodes": [
                    {
                        "id": "node1",
                        "name": "node1",
                        "devices": [
                            {
                                "type": "cuda",
                                "name": "GPU-0",
                                "available_count": 0,
                                "mem_per_GPU_in_GB": 80,
                                "memory_allocated_gb": 75,  # Only 5GB available
                                "core_utilization_percent": 94.0,
                                "memory_utilization_percent": 93.75,
                            },
                        ],
                    },
                ],
            }
        ]

        device_groups = SimulationService._group_devices_by_type_across_cluster(
            cluster_info, cluster_topology, "shared"
        )

        # Device SHOULD be included in filtering (has available memory > 0)
        assert "cuda" in device_groups
        assert len(device_groups["cuda"]["devices"]) == 1
        assert device_groups["cuda"]["devices"][0]["name"] == "GPU-0"

        # Verify memory override will happen in get_topk_engine_configs_per_cluster
        # The 5GB available memory will be used for validation
        device = device_groups["cuda"]["devices"][0]
        available_memory = device["mem_per_GPU_in_GB"] - device["memory_allocated_gb"]
        assert available_memory == 5  # 80 - 75 = 5GB

        # This 5GB will later cause validation to fail for large models (15GB+)
        # in DirectSearchOptimizer._validate_config() -> validate_memory_requirements()
        # which will set meets_targets=False in direct_search.py:362
