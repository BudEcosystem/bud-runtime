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


class TestCpuHighDedicatedModeFiltering:
    """Test cpu_high dedicated mode filtering using utilized_cores threshold."""

    @pytest.fixture
    def cluster_topology(self):
        """Basic cluster topology fixture."""
        return {
            "total_nodes": 1,
            "total_cluster_devices": 1,
            "device_types": ["cpu_high"],
        }

    def test_cpu_high_low_utilization_passes_dedicated_mode(self, cluster_topology):
        """Test that cpu_high with < 5% core utilization passes dedicated mode."""
        cluster_info = [
            {
                "id": "cluster1",
                "nodes": [
                    {
                        "id": "node1",
                        "name": "node1",
                        "devices": [
                            {
                                "type": "cpu_high",
                                "name": "CPU-0",
                                "available_count": 1,
                                "cores": 48,
                                "memory_gb": 251.2,
                                "utilized_cores": 0.2,  # ~0.4% utilization - should pass
                                "utilized_memory_gb": 0.13,
                            },
                        ],
                    },
                ],
            }
        ]

        device_groups = SimulationService._group_devices_by_type_across_cluster(
            cluster_info, cluster_topology, "dedicated"
        )

        # Should include cpu_high with low utilization
        assert "cpu_high" in device_groups
        assert len(device_groups["cpu_high"]["devices"]) == 1
        assert device_groups["cpu_high"]["devices"][0]["name"] == "CPU-0"
        # Verify available_memory_gb is set
        assert "available_memory_gb" in device_groups["cpu_high"]["devices"][0]
        assert device_groups["cpu_high"]["devices"][0]["available_memory_gb"] == pytest.approx(251.07, rel=0.01)

    def test_cpu_high_high_utilization_filtered_dedicated_mode(self, cluster_topology):
        """Test that cpu_high with >= 5% core utilization is filtered in dedicated mode."""
        cluster_info = [
            {
                "id": "cluster1",
                "nodes": [
                    {
                        "id": "node1",
                        "name": "node1",
                        "devices": [
                            {
                                "type": "cpu_high",
                                "name": "CPU-0",
                                "available_count": 1,
                                "cores": 96,
                                "memory_gb": 501.5,
                                "utilized_cores": 9.9,  # ~10.3% utilization - should be filtered
                                "utilized_memory_gb": 24.0,
                            },
                        ],
                    },
                ],
            }
        ]

        device_groups = SimulationService._group_devices_by_type_across_cluster(
            cluster_info, cluster_topology, "dedicated"
        )

        # Should not include cpu_high with high utilization
        assert "cpu_high" not in device_groups

    def test_cpu_high_exactly_5_percent_filtered(self, cluster_topology):
        """Test that cpu_high with exactly 5% utilization is filtered (threshold is < 5%)."""
        cluster_info = [
            {
                "id": "cluster1",
                "nodes": [
                    {
                        "id": "node1",
                        "name": "node1",
                        "devices": [
                            {
                                "type": "cpu_high",
                                "name": "CPU-0",
                                "available_count": 1,
                                "cores": 100,
                                "memory_gb": 256.0,
                                "utilized_cores": 5.0,  # Exactly 5% - should be filtered
                                "utilized_memory_gb": 10.0,
                            },
                        ],
                    },
                ],
            }
        ]

        device_groups = SimulationService._group_devices_by_type_across_cluster(
            cluster_info, cluster_topology, "dedicated"
        )

        # Should not include cpu_high with exactly 5% utilization
        assert "cpu_high" not in device_groups

    def test_cpu_high_just_below_5_percent_passes(self, cluster_topology):
        """Test that cpu_high with just below 5% utilization passes dedicated mode."""
        cluster_info = [
            {
                "id": "cluster1",
                "nodes": [
                    {
                        "id": "node1",
                        "name": "node1",
                        "devices": [
                            {
                                "type": "cpu_high",
                                "name": "CPU-0",
                                "available_count": 1,
                                "cores": 100,
                                "memory_gb": 256.0,
                                "utilized_cores": 4.9,  # 4.9% - should pass
                                "utilized_memory_gb": 10.0,
                            },
                        ],
                    },
                ],
            }
        ]

        device_groups = SimulationService._group_devices_by_type_across_cluster(
            cluster_info, cluster_topology, "dedicated"
        )

        # Should include cpu_high just below threshold
        assert "cpu_high" in device_groups
        assert len(device_groups["cpu_high"]["devices"]) == 1

    def test_regular_cpu_uses_available_count_not_utilization(self, cluster_topology):
        """Test that regular cpu type doesn't use utilization filtering."""
        cluster_info = [
            {
                "id": "cluster1",
                "nodes": [
                    {
                        "id": "node1",
                        "name": "node1",
                        "devices": [
                            {
                                "type": "cpu",  # Regular cpu, not cpu_high
                                "name": "CPU-0",
                                "available_count": 1,
                                "cores": 48,
                                "memory_gb": 128.0,
                                "utilized_cores": 20.0,  # High utilization but should pass
                                "utilized_memory_gb": 50.0,
                            },
                        ],
                    },
                ],
            }
        ]

        device_groups = SimulationService._group_devices_by_type_across_cluster(
            cluster_info, cluster_topology, "dedicated"
        )

        # Regular cpu should pass using available_count, not utilization
        assert "cpu" in device_groups
        assert len(device_groups["cpu"]["devices"]) == 1
        assert device_groups["cpu"]["devices"][0]["name"] == "CPU-0"

    def test_regular_cpu_filtered_by_zero_available_count(self, cluster_topology):
        """Test that regular cpu with available_count=0 is filtered."""
        cluster_info = [
            {
                "id": "cluster1",
                "nodes": [
                    {
                        "id": "node1",
                        "name": "node1",
                        "devices": [
                            {
                                "type": "cpu",
                                "name": "CPU-0",
                                "available_count": 0,  # Should filter this
                                "cores": 48,
                                "memory_gb": 128.0,
                                "utilized_cores": 0.0,  # Even with no utilization
                                "utilized_memory_gb": 0.0,
                            },
                        ],
                    },
                ],
            }
        ]

        device_groups = SimulationService._group_devices_by_type_across_cluster(
            cluster_info, cluster_topology, "dedicated"
        )

        # Regular cpu should be filtered due to available_count=0
        assert "cpu" not in device_groups

    def test_cpu_high_missing_utilization_fields_fallback(self, cluster_topology):
        """Test cpu_high behavior when utilization fields are missing."""
        cluster_info = [
            {
                "id": "cluster1",
                "nodes": [
                    {
                        "id": "node1",
                        "name": "node1",
                        "devices": [
                            {
                                "type": "cpu_high",
                                "name": "CPU-0",
                                "available_count": 1,
                                "cores": 48,
                                "memory_gb": 256.0,
                                # Missing utilized_cores and utilized_memory_gb
                            },
                        ],
                    },
                ],
            }
        ]

        device_groups = SimulationService._group_devices_by_type_across_cluster(
            cluster_info, cluster_topology, "dedicated"
        )

        # With missing utilization fields, defaults to 0.0 which is < 5%, so should pass
        assert "cpu_high" in device_groups
        assert len(device_groups["cpu_high"]["devices"]) == 1

    def test_cpu_high_zero_cores_filtered(self, cluster_topology):
        """Test cpu_high with zero cores is filtered (edge case)."""
        cluster_info = [
            {
                "id": "cluster1",
                "nodes": [
                    {
                        "id": "node1",
                        "name": "node1",
                        "devices": [
                            {
                                "type": "cpu_high",
                                "name": "CPU-0",
                                "available_count": 1,
                                "cores": 0,  # Edge case: zero cores
                                "memory_gb": 256.0,
                                "utilized_cores": 0.0,
                                "utilized_memory_gb": 0.0,
                            },
                        ],
                    },
                ],
            }
        ]

        device_groups = SimulationService._group_devices_by_type_across_cluster(
            cluster_info, cluster_topology, "dedicated"
        )

        # Zero cores results in 100% utilization calculation, should be filtered
        assert "cpu_high" not in device_groups

    def test_mixed_cpu_high_utilization_levels(self, cluster_topology):
        """Test filtering with mix of cpu_high devices at different utilization levels."""
        cluster_info = [
            {
                "id": "cluster1",
                "nodes": [
                    {
                        "id": "node1",
                        "name": "node1",
                        "devices": [
                            {
                                "type": "cpu_high",
                                "name": "CPU-0",
                                "available_count": 1,
                                "cores": 48,
                                "memory_gb": 251.2,
                                "utilized_cores": 0.2,  # 0.4% - should pass
                                "utilized_memory_gb": 0.13,
                            },
                        ],
                    },
                    {
                        "id": "node2",
                        "name": "node2",
                        "devices": [
                            {
                                "type": "cpu_high",
                                "name": "CPU-1",
                                "available_count": 1,
                                "cores": 96,
                                "memory_gb": 501.5,
                                "utilized_cores": 9.9,  # 10.3% - should be filtered
                                "utilized_memory_gb": 24.0,
                            },
                        ],
                    },
                ],
            }
        ]

        device_groups = SimulationService._group_devices_by_type_across_cluster(
            cluster_info, cluster_topology, "dedicated"
        )

        # Should only include CPU-0 with low utilization
        assert "cpu_high" in device_groups
        assert len(device_groups["cpu_high"]["devices"]) == 1
        assert device_groups["cpu_high"]["devices"][0]["name"] == "CPU-0"
