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

"""Tests for node group configuration schemas and validation."""

import pytest
from pydantic import ValidationError

from budsim.simulator.schemas import (
    DeploymentConfigurationResponse,
    NodeGroupConfiguration,
    NodeGroupConfigurationValidator,
)


class TestNodeGroupConfiguration:
    """Test cases for NodeGroupConfiguration schema."""

    def test_valid_node_group_config(self):
        """Test creation of valid node group configuration."""
        config = NodeGroupConfiguration(
            config_id="test-123",
            name="A100",
            labels={"device_name": "A100", "concurrency": "1"},
            type="cuda",
            tp_size=2,
            pp_size=1,
            envs={"CUDA_VISIBLE_DEVICES": "0,1"},
            args={"model": "test-model"},
            replicas=1,
            image="vllm/vllm-openai:v0.7.1",
            memory=1024.0,
            ttft=0.5,
            throughput_per_user=100.0,
            e2e_latency=2.0,
            error_rate=0.01,
            cost_per_million_tokens=5.0,
            device_name="A100",
            device_model="NVIDIA-A100-SXM4-80GB",
            raw_name="nvidia_a100_sxm4_80gb",
        )

        assert config.name == "A100"
        assert config.type == "cuda"
        assert config.tp_size == 2
        assert config.pp_size == 1

    def test_invalid_pp_size_for_cpu(self):
        """Test that PP > 1 is rejected for CPU devices."""
        with pytest.raises(ValidationError) as exc_info:
            NodeGroupConfiguration(
                config_id="test-123",
                name="CPU",
                type="cpu",
                tp_size=1,
                pp_size=2,  # Invalid for CPU
                replicas=1,
                image="vllm/vllm-openai:v0.7.1",
                memory=1024.0,
                ttft=0.5,
                throughput_per_user=100.0,
                e2e_latency=2.0,
                error_rate=0.01,
                cost_per_million_tokens=5.0,
            )

        assert "Pipeline parallelism (PP) is not supported for CPU devices" in str(exc_info.value)

    def test_invalid_pp_size_for_hpu(self):
        """Test that PP > 1 is rejected for HPU devices."""
        with pytest.raises(ValidationError) as exc_info:
            NodeGroupConfiguration(
                config_id="test-123",
                name="Gaudi2",
                type="hpu",
                tp_size=1,
                pp_size=2,  # Invalid for HPU
                replicas=1,
                image="gaudi-vllm:latest",
                memory=1024.0,
                ttft=0.5,
                throughput_per_user=100.0,
                e2e_latency=2.0,
                error_rate=0.01,
                cost_per_million_tokens=5.0,
            )

        assert "Multi-node pipeline parallelism requires CUDA devices" in str(exc_info.value)


class TestNodeGroupConfigurationValidator:
    """Test cases for NodeGroupConfigurationValidator."""

    def test_valid_parallelism_combination(self):
        """Test valid TP/PP combinations."""
        # Should not raise any exception
        NodeGroupConfigurationValidator.validate_parallelism_combination(
            tp_size=2, pp_size=2, available_devices=8
        )

    def test_invalid_tp_size(self):
        """Test invalid TP size."""
        with pytest.raises(ValueError) as exc_info:
            NodeGroupConfigurationValidator.validate_parallelism_combination(
                tp_size=0, pp_size=1, available_devices=8
            )
        assert "tp_size must be at least 1" in str(exc_info.value)

    def test_invalid_pp_size(self):
        """Test invalid PP size."""
        with pytest.raises(ValueError) as exc_info:
            NodeGroupConfigurationValidator.validate_parallelism_combination(
                tp_size=1, pp_size=0, available_devices=8
            )
        assert "pp_size must be at least 1" in str(exc_info.value)

    def test_insufficient_devices(self):
        """Test that insufficient devices are detected."""
        with pytest.raises(ValueError) as exc_info:
            NodeGroupConfigurationValidator.validate_parallelism_combination(
                tp_size=4, pp_size=3, available_devices=8
            )
        assert "Required devices (12 = 4*3) exceeds available devices (8)" in str(exc_info.value)

    def test_cpu_device_type_validation(self):
        """Test CPU device type validation."""
        # Should work for PP=1
        NodeGroupConfigurationValidator.validate_device_type_compatibility("cpu", 1)

        # Should fail for PP>1
        with pytest.raises(ValueError) as exc_info:
            NodeGroupConfigurationValidator.validate_device_type_compatibility("cpu", 2)
        assert "Pipeline parallelism (PP) is not supported for CPU devices" in str(exc_info.value)

    def test_cuda_device_type_validation(self):
        """Test CUDA device type validation."""
        # Should work for any PP size
        NodeGroupConfigurationValidator.validate_device_type_compatibility("cuda", 1)
        NodeGroupConfigurationValidator.validate_device_type_compatibility("cuda", 4)

    def test_hpu_device_type_validation(self):
        """Test HPU device type validation."""
        # Should work for PP=1
        NodeGroupConfigurationValidator.validate_device_type_compatibility("hpu", 1)

        # Should fail for PP>1
        with pytest.raises(ValueError) as exc_info:
            NodeGroupConfigurationValidator.validate_device_type_compatibility("hpu", 2)
        assert "Multi-node pipeline parallelism requires CUDA devices" in str(exc_info.value)


class TestDeploymentConfigurationResponse:
    """Test cases for updated DeploymentConfigurationResponse schema."""

    def test_legacy_nodes_structure(self):
        """Test backward compatibility with legacy nodes structure."""
        response = DeploymentConfigurationResponse(
            id="test-cluster",
            nodes=[],  # Legacy structure
            node_groups=None,
            replica=1,
            concurrency=10,
            ttft=0.5,
            throughput_per_user=100.0,
            e2e_latency=2.0,
            error_rate=0.01,
            cost_per_million_tokens=5.0,
        )

        assert response.nodes == []
        assert response.node_groups is None

    def test_new_node_groups_structure(self):
        """Test new node groups structure."""
        node_group = NodeGroupConfiguration(
            config_id="test-123",
            name="A100",
            type="cuda",
            tp_size=2,
            pp_size=1,
            replicas=1,
            image="vllm/vllm-openai:v0.7.1",
            memory=1024.0,
            ttft=0.5,
            throughput_per_user=100.0,
            e2e_latency=2.0,
            error_rate=0.01,
            cost_per_million_tokens=5.0,
        )

        response = DeploymentConfigurationResponse(
            id="test-cluster",
            nodes=None,
            node_groups=[node_group],  # New structure
            replica=1,
            concurrency=10,
            ttft=0.5,
            throughput_per_user=100.0,
            e2e_latency=2.0,
            error_rate=0.01,
            cost_per_million_tokens=5.0,
        )

        assert response.nodes is None
        assert len(response.node_groups) == 1
        assert response.node_groups[0].name == "A100"

    def test_missing_both_structures_validation(self):
        """Test that validation fails when both structures are missing."""
        with pytest.raises(ValidationError) as exc_info:
            DeploymentConfigurationResponse(
                id="test-cluster",
                nodes=None,
                node_groups=None,  # Both are None
                replica=1,
                concurrency=10,
                ttft=0.5,
                throughput_per_user=100.0,
                e2e_latency=2.0,
                error_rate=0.01,
                cost_per_million_tokens=5.0,
            )

        assert "Either nodes or node_groups must be provided" in str(exc_info.value)

    def test_reset_functionality(self):
        """Test reset functionality for both structures."""
        response = DeploymentConfigurationResponse(
            id="test-cluster",
            nodes=[],
            node_groups=[],
            replica=5,
            concurrency=100,
            ttft=1.5,
            throughput_per_user=200.0,
            e2e_latency=5.0,
            error_rate=0.1,
            cost_per_million_tokens=15.0,
        )

        response.reset()

        assert response.nodes == []
        assert response.node_groups == []
        assert response.replica == 0
        assert response.concurrency == 0
        assert response.ttft == 0
        assert response.throughput_per_user == 0
        assert response.e2e_latency == 0
        assert response.error_rate == 0
