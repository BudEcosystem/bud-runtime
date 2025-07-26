"""
Unit tests for deployment type detection logic in DeploymentService.

Tests the _is_cloud_deployment method to ensure proper routing between
local and cloud deployment workflows.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from uuid import UUID, uuid4

from budcluster.deployment.services import DeploymentService
from budcluster.deployment.schemas import DeploymentCreateRequest


class TestDeploymentTypeDetection:
    """Test class for deployment type detection logic."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = DeploymentService()
        self.base_deployment_data = {
            "cluster_id": uuid4(),
            "endpoint_name": "test-endpoint",
            "model": "test-model",
            "concurrency": 1,
            "user_id": uuid4(),
        }

    def test_cloud_provider_detection(self):
        """Test that cloud providers are correctly detected."""
        cloud_providers = ["OPENAI", "ANTHROPIC", "AZURE_OPENAI", "BEDROCK", "COHERE", "GROQ"]

        for provider in cloud_providers:
            deployment = DeploymentCreateRequest(
                **self.base_deployment_data,
                provider=provider,
                credential_id=uuid4()
            )

            result = self.service._is_cloud_deployment(deployment)
            assert result is True, f"Provider {provider} should be detected as cloud deployment"

    def test_local_provider_detection(self):
        """Test that local providers are correctly detected as local."""
        local_providers = ["HUGGING_FACE", "URL", "DISK"]

        for provider in local_providers:
            deployment = DeploymentCreateRequest(
                **self.base_deployment_data,
                provider=provider,
                credential_id=None  # Local providers can have None credential_id
            )

            result = self.service._is_cloud_deployment(deployment)
            assert result is False, f"Provider {provider} should be detected as local deployment"

    def test_huggingface_with_credential_id(self):
        """Test that HuggingFace with credential_id is still local deployment."""
        deployment = DeploymentCreateRequest(
            **self.base_deployment_data,
            provider="HUGGING_FACE",
            credential_id=uuid4()  # HF token for private models
        )

        result = self.service._is_cloud_deployment(deployment)
        assert result is False, "HuggingFace with credential_id should still be local deployment"

    def test_case_insensitive_provider_detection(self):
        """Test that provider detection is case insensitive."""
        test_cases = [
            ("openai", True),
            ("OpenAI", True),
            ("OPENAI", True),
            ("hugging_face", False),
            ("Hugging_Face", False),
            ("HUGGING_FACE", False),
        ]

        for provider, expected_cloud in test_cases:
            deployment = DeploymentCreateRequest(
                **self.base_deployment_data,
                provider=provider,
                credential_id=uuid4() if expected_cloud else None
            )

            result = self.service._is_cloud_deployment(deployment)
            assert result is expected_cloud, f"Provider {provider} cloud detection failed"

    def test_no_provider_with_credential_fallback(self):
        """Test fallback logic when provider is None but credential_id exists."""
        deployment = DeploymentCreateRequest(
            **self.base_deployment_data,
            provider=None,
            credential_id=uuid4()
        )

        result = self.service._is_cloud_deployment(deployment)
        assert result is True, "Deployment with credential_id but no provider should default to cloud"

    def test_no_provider_no_credential_fallback(self):
        """Test fallback logic when both provider and credential_id are None."""
        deployment = DeploymentCreateRequest(
            **self.base_deployment_data,
            provider=None,
            credential_id=None
        )

        result = self.service._is_cloud_deployment(deployment)
        assert result is False, "Deployment with no provider and no credential_id should default to local"

    def test_unknown_provider_with_credential(self):
        """Test unknown provider with credential_id defaults to cloud."""
        deployment = DeploymentCreateRequest(
            **self.base_deployment_data,
            provider="UNKNOWN_PROVIDER",
            credential_id=uuid4()
        )

        result = self.service._is_cloud_deployment(deployment)
        assert result is True, "Unknown provider with credential_id should default to cloud"

    def test_unknown_provider_without_credential(self):
        """Test unknown provider without credential_id defaults to local."""
        deployment = DeploymentCreateRequest(
            **self.base_deployment_data,
            provider="UNKNOWN_PROVIDER",
            credential_id=None
        )

        result = self.service._is_cloud_deployment(deployment)
        assert result is False, "Unknown provider without credential_id should default to local"

    def test_edge_cases(self):
        """Test edge cases and boundary conditions."""
        # Empty string provider
        deployment = DeploymentCreateRequest(
            **self.base_deployment_data,
            provider="",
            credential_id=None
        )
        result = self.service._is_cloud_deployment(deployment)
        assert result is False, "Empty provider should default to local"

        # Whitespace provider
        deployment = DeploymentCreateRequest(
            **self.base_deployment_data,
            provider="   ",
            credential_id=None
        )
        result = self.service._is_cloud_deployment(deployment)
        assert result is False, "Whitespace provider should default to local"


if __name__ == "__main__":
    # Run tests directly
    test_instance = TestDeploymentTypeDetection()
    test_instance.setup_method()

    # Run all test methods
    test_methods = [method for method in dir(test_instance) if method.startswith('test_')]

    print("Running deployment type detection tests...")
    for method_name in test_methods:
        try:
            method = getattr(test_instance, method_name)
            method()
            print(f"✓ {method_name}")
        except Exception as e:
            print(f"✗ {method_name}: {e}")

    print("Tests completed!")
