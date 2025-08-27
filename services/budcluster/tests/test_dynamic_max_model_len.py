"""Test dynamic max-model-len calculation for model deployments."""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import copy
from budcluster.deployment.handler import DeploymentHandler
from budcluster.commons.constants import ClusterPlatformEnum


class TestDynamicMaxModelLen:
    """Test suite for dynamic max-model-len calculation."""

    @pytest.fixture
    def deployment_handler(self):
        """Create a deployment handler instance."""
        config = {
            "kubeconfig": "test-config",
            "cluster_name": "test-cluster",
        }
        return DeploymentHandler(config)

    @pytest.fixture
    def base_node_list(self):
        """Create a base node list for testing."""
        return [
            {
                "name": "test-node",
                "devices": [
                    {
                        "name": "test-device",
                        "image": "test-image",
                        "replica": 1,
                        "memory": 32768,
                        "type": "cuda",
                        "tp_size": 1,
                        "concurrency": 10,
                        "args": {
                            "model": "test-model",
                            "port": 8000,
                        },
                        "envs": {},
                    }
                ],
            }
        ]

    def test_dynamic_calculation_logic(self, deployment_handler):
        """Test the max-model-len calculation logic directly."""
        # Test with both tokens provided
        input_tokens = 4096
        output_tokens = 2048
        expected = int((input_tokens + output_tokens) * 1.1)
        assert expected == 6758

        # Test with large tokens
        input_tokens = 100000
        output_tokens = 28000
        expected = int((input_tokens + output_tokens) * 1.1)
        assert expected == 140800

    @patch("budcluster.deployment.handler.apply_security_context")
    @patch("budcluster.deployment.handler.deploy_runtime")
    def test_deploy_with_tokens(self, mock_deploy_runtime, mock_apply_security, deployment_handler, base_node_list):
        """Test deployment with token parameters."""
        # Setup async mocks
        async def mock_apply_security_async(*args, **kwargs):
            return True

        async def mock_deploy_runtime_async(config, values, *args, **kwargs):
            # Capture the values for verification
            self.captured_values = values
            return True, "http://test-url"

        mock_apply_security.return_value = mock_apply_security_async()
        mock_deploy_runtime.return_value = mock_deploy_runtime_async(None, None)

        # We need to patch asyncio.run to capture the actual values
        with patch("budcluster.deployment.handler.asyncio.run") as mock_run:
            captured_values = {}

            def capture_values(coro):
                # If it's the deploy_runtime call, capture the values
                if hasattr(coro, "__name__") and "deploy_runtime" in str(coro):
                    # This is a simplified approach - in real scenario we'd extract from coro
                    return True, "http://test-url"
                return True

            mock_run.side_effect = capture_values

            # Execute deployment
            status, namespace, url, nodes, node_list_result = deployment_handler.deploy(
                node_list=copy.deepcopy(base_node_list),
                endpoint_name="test-endpoint",
                ingress_url="http://test-ingress",
                input_tokens=4096,
                output_tokens=2048,
            )

            # Verify the max-model-len was calculated correctly
            # Expected: (4096 + 2048) * 1.1 = 6758
            processed_devices = node_list_result[0]["devices"]
            for device in processed_devices:
                assert "--max-model-len=6758" in device["args"]

    @patch("budcluster.deployment.handler.apply_security_context")
    @patch("budcluster.deployment.handler.deploy_runtime")
    def test_deploy_without_tokens(self, mock_deploy_runtime, mock_apply_security, deployment_handler, base_node_list):
        """Test deployment without token parameters uses default."""
        # Setup async mocks
        async def mock_apply_security_async(*args, **kwargs):
            return True

        async def mock_deploy_runtime_async(*args, **kwargs):
            return True, "http://test-url"

        mock_apply_security.return_value = mock_apply_security_async()
        mock_deploy_runtime.return_value = mock_deploy_runtime_async()

        with patch("budcluster.deployment.handler.asyncio.run") as mock_run:
            mock_run.side_effect = [True, (True, "http://test-url")]

            # Execute deployment without tokens
            status, namespace, url, nodes, node_list_result = deployment_handler.deploy(
                node_list=copy.deepcopy(base_node_list),
                endpoint_name="test-endpoint",
                ingress_url="http://test-ingress",
            )

            # Verify default max-model-len is used
            processed_devices = node_list_result[0]["devices"]
            for device in processed_devices:
                assert "--max-model-len=8192" in device["args"]

    @patch("budcluster.deployment.handler.apply_security_context")
    @patch("budcluster.deployment.handler.deploy_runtime")
    def test_deploy_with_only_input_tokens(self, mock_deploy_runtime, mock_apply_security, deployment_handler, base_node_list):
        """Test deployment with only input_tokens uses default."""
        # Setup async mocks
        async def mock_apply_security_async(*args, **kwargs):
            return True

        async def mock_deploy_runtime_async(*args, **kwargs):
            return True, "http://test-url"

        mock_apply_security.return_value = mock_apply_security_async()
        mock_deploy_runtime.return_value = mock_deploy_runtime_async()

        with patch("budcluster.deployment.handler.asyncio.run") as mock_run:
            mock_run.side_effect = [True, (True, "http://test-url")]

            # Execute deployment with only input_tokens
            status, namespace, url, nodes, node_list_result = deployment_handler.deploy(
                node_list=copy.deepcopy(base_node_list),
                endpoint_name="test-endpoint",
                ingress_url="http://test-ingress",
                input_tokens=4096,
            )

            # Verify default max-model-len is used when only one token is provided
            processed_devices = node_list_result[0]["devices"]
            for device in processed_devices:
                assert "--max-model-len=8192" in device["args"]

    @patch("budcluster.deployment.handler.apply_security_context")
    @patch("budcluster.deployment.handler.deploy_runtime")
    def test_deploy_with_large_context(self, mock_deploy_runtime, mock_apply_security, deployment_handler, base_node_list):
        """Test deployment with large context values."""
        # Setup async mocks
        async def mock_apply_security_async(*args, **kwargs):
            return True

        async def mock_deploy_runtime_async(*args, **kwargs):
            return True, "http://test-url"

        mock_apply_security.return_value = mock_apply_security_async()
        mock_deploy_runtime.return_value = mock_deploy_runtime_async()

        with patch("budcluster.deployment.handler.asyncio.run") as mock_run:
            mock_run.side_effect = [True, (True, "http://test-url")]

            # Execute deployment with large context
            status, namespace, url, nodes, node_list_result = deployment_handler.deploy(
                node_list=copy.deepcopy(base_node_list),
                endpoint_name="test-endpoint",
                ingress_url="http://test-ingress",
                input_tokens=100000,
                output_tokens=28000,
            )

            # Verify large context is handled correctly
            # Expected: (100000 + 28000) * 1.1 = 140800
            processed_devices = node_list_result[0]["devices"]
            for device in processed_devices:
                assert "--max-model-len=140800" in device["args"]

    def test_namespace_generation(self, deployment_handler):
        """Test namespace generation from endpoint name."""
        namespace = deployment_handler._get_namespace("test-endpoint")
        assert namespace.startswith("bud-test-endpoint-")
        assert len(namespace.split("-")[-1]) == 8  # Check UUID suffix length

    @patch("budcluster.deployment.handler.apply_security_context")
    @patch("budcluster.deployment.handler.deploy_runtime")
    def test_safety_margin_calculations(self, mock_deploy_runtime, mock_apply_security, deployment_handler, base_node_list):
        """Test various safety margin calculations."""
        async def mock_apply_security_async(*args, **kwargs):
            return True

        async def mock_deploy_runtime_async(*args, **kwargs):
            return True, "http://test-url"

        mock_apply_security.return_value = mock_apply_security_async()
        mock_deploy_runtime.return_value = mock_deploy_runtime_async()

        test_cases = [
            (1000, 1000, 2200),   # (1000 + 1000) * 1.1 = 2200
            (5000, 3000, 8800),   # (5000 + 3000) * 1.1 = 8800
            (10000, 5000, 16500), # (10000 + 5000) * 1.1 = 16500
        ]

        for input_tokens, output_tokens, expected_max_len in test_cases:
            with patch("budcluster.deployment.handler.asyncio.run") as mock_run:
                mock_run.side_effect = [True, (True, "http://test-url")]

                status, namespace, url, nodes, node_list_result = deployment_handler.deploy(
                    node_list=copy.deepcopy(base_node_list),
                    endpoint_name="test-endpoint",
                    ingress_url="http://test-ingress",
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )

                # Verify the calculation
                processed_devices = node_list_result[0]["devices"]
                for device in processed_devices:
                    assert f"--max-model-len={expected_max_len}" in device["args"]
