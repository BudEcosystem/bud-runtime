"""
Unit tests for deployment type detection logic.

Isolated unit tests that don't require full application setup.
"""

import sys
import os
from uuid import uuid4
from unittest.mock import Mock, patch

# Add the parent directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock the database session before importing
sys.modules['budmicroframe.shared.psql_service'] = Mock()

# Create a minimal deployment service for testing
class MockDeploymentService:
    """Mock deployment service with only the method we want to test."""

    def _is_cloud_deployment(self, deployment) -> bool:
        """Determine if deployment is for cloud model based on provider and credential_id."""
        cloud_providers = {"OPENAI", "ANTHROPIC", "AZURE_OPENAI", "BEDROCK", "COHERE", "GROQ"}
        local_providers = {"HUGGING_FACE", "URL", "DISK"}

        if deployment.provider:
            provider_upper = deployment.provider.upper()
            if provider_upper in cloud_providers:
                return True
            elif provider_upper in local_providers:
                return False

        # Fallback: If credential_id is provided and required, it's likely a cloud deployment
        if deployment.credential_id is not None:
            return deployment.provider not in local_providers if deployment.provider else True

        return False


class MockDeploymentRequest:
    """Mock deployment request object."""
    def __init__(self, provider=None, credential_id=None, **kwargs):
        self.provider = provider
        self.credential_id = credential_id
        for key, value in kwargs.items():
            setattr(self, key, value)


def test_cloud_provider_detection():
    """Test that cloud providers are correctly detected."""
    service = MockDeploymentService()
    cloud_providers = ["OPENAI", "ANTHROPIC", "AZURE_OPENAI", "BEDROCK", "COHERE", "GROQ"]

    for provider in cloud_providers:
        deployment = MockDeploymentRequest(
            provider=provider,
            credential_id=uuid4()
        )

        result = service._is_cloud_deployment(deployment)
        assert result is True, f"Provider {provider} should be detected as cloud deployment"

    print("✓ Cloud provider detection test passed")


def test_local_provider_detection():
    """Test that local providers are correctly detected as local."""
    service = MockDeploymentService()
    local_providers = ["HUGGING_FACE", "URL", "DISK"]

    for provider in local_providers:
        deployment = MockDeploymentRequest(
            provider=provider,
            credential_id=None
        )

        result = service._is_cloud_deployment(deployment)
        assert result is False, f"Provider {provider} should be detected as local deployment"

    print("✓ Local provider detection test passed")


def test_huggingface_with_credential_id():
    """Test that HuggingFace with credential_id is still local deployment."""
    service = MockDeploymentService()
    deployment = MockDeploymentRequest(
        provider="HUGGING_FACE",
        credential_id=uuid4()
    )

    result = service._is_cloud_deployment(deployment)
    assert result is False, "HuggingFace with credential_id should still be local deployment"

    print("✓ HuggingFace with credential test passed")


def test_case_insensitive_provider_detection():
    """Test that provider detection is case insensitive."""
    service = MockDeploymentService()
    test_cases = [
        ("openai", True),
        ("OpenAI", True),
        ("OPENAI", True),
        ("hugging_face", False),
        ("Hugging_Face", False),
        ("HUGGING_FACE", False),
    ]

    for provider, expected_cloud in test_cases:
        deployment = MockDeploymentRequest(
            provider=provider,
            credential_id=uuid4() if expected_cloud else None
        )

        result = service._is_cloud_deployment(deployment)
        assert result is expected_cloud, f"Provider {provider} cloud detection failed"

    print("✓ Case insensitive provider detection test passed")


def test_fallback_logic():
    """Test fallback logic for edge cases."""
    service = MockDeploymentService()

    # No provider with credential_id
    deployment = MockDeploymentRequest(provider=None, credential_id=uuid4())
    result = service._is_cloud_deployment(deployment)
    assert result is True, "Deployment with credential_id but no provider should default to cloud"

    # No provider, no credential_id
    deployment = MockDeploymentRequest(provider=None, credential_id=None)
    result = service._is_cloud_deployment(deployment)
    assert result is False, "Deployment with no provider and no credential_id should default to local"

    # Unknown provider with credential
    deployment = MockDeploymentRequest(provider="UNKNOWN_PROVIDER", credential_id=uuid4())
    result = service._is_cloud_deployment(deployment)
    assert result is True, "Unknown provider with credential_id should default to cloud"

    # Unknown provider without credential
    deployment = MockDeploymentRequest(provider="UNKNOWN_PROVIDER", credential_id=None)
    result = service._is_cloud_deployment(deployment)
    assert result is False, "Unknown provider without credential_id should default to local"

    print("✓ Fallback logic test passed")


def run_all_tests():
    """Run all tests."""
    print("Running deployment type detection tests...")
    print()

    test_functions = [
        test_cloud_provider_detection,
        test_local_provider_detection,
        test_huggingface_with_credential_id,
        test_case_insensitive_provider_detection,
        test_fallback_logic,
    ]

    passed = 0
    failed = 0

    for test_func in test_functions:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"✗ {test_func.__name__}: {e}")
            failed += 1

    print()
    print(f"Tests completed: {passed} passed, {failed} failed")

    if failed == 0:
        print("🎉 All tests passed!")
        return True
    else:
        print("❌ Some tests failed!")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
