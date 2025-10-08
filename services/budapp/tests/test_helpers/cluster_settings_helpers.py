"""Common test utilities for cluster settings tests."""

import uuid
from datetime import datetime, timezone
from typing import Optional, Any
from unittest.mock import Mock
from uuid import UUID


class MockFactory:
    """Factory for creating consistent mock objects for testing."""

    @staticmethod
    def create_mock_user(
        user_id: Optional[UUID] = None,
        email: str = "test@example.com"
    ) -> Mock:
        """Create a mock user object."""
        user = Mock()
        user.id = user_id or uuid.uuid4()
        user.email = email
        return user

    @staticmethod
    def create_mock_cluster(
        cluster_id: Optional[UUID] = None,
        name: str = "test-cluster",
        platform: str = "eks",
        created_by: Optional[UUID] = None
    ) -> Mock:
        """Create a mock cluster object."""
        cluster = Mock()
        cluster.id = cluster_id or uuid.uuid4()
        cluster.name = name
        cluster.platform = platform
        cluster.created_by = created_by or uuid.uuid4()
        cluster.created_at = datetime.now(timezone.utc)
        cluster.modified_at = datetime.now(timezone.utc)
        return cluster

    @staticmethod
    def create_mock_cluster_settings(
        settings_id: Optional[UUID] = None,
        cluster_id: Optional[UUID] = None,
        default_storage_class: Optional[str] = "gp2",
        default_access_mode: Optional[str] = None,
        created_by: Optional[UUID] = None
    ) -> Mock:
        """Create a mock cluster settings object."""
        settings = Mock()
        settings.id = settings_id or uuid.uuid4()
        settings.cluster_id = cluster_id or uuid.uuid4()
        settings.default_storage_class = default_storage_class
        settings.default_access_mode = default_access_mode
        settings.created_by = created_by or uuid.uuid4()
        settings.created_at = datetime.now(timezone.utc)
        settings.modified_at = datetime.now(timezone.utc)
        return settings

    @staticmethod
    def create_cluster_settings_response(
        settings_id: Optional[UUID] = None,
        cluster_id: Optional[UUID] = None,
        default_storage_class: Optional[str] = "gp2",
        default_access_mode: Optional[str] = None,
        created_by: Optional[UUID] = None
    ) -> dict:
        """Create a ClusterSettingsResponse dict for API tests."""
        now = datetime.now(timezone.utc)
        return {
            "id": settings_id or uuid.uuid4(),
            "cluster_id": cluster_id or uuid.uuid4(),
            "default_storage_class": default_storage_class,
            "default_access_mode": default_access_mode,
            "created_by": created_by or uuid.uuid4(),
            "created_at": now,
            "modified_at": now
        }


class TestDataBuilder:
    """Builder for creating consistent test data."""

    @staticmethod
    def create_storage_class_options():
        """Create a standard set of storage class options for testing."""
        return [
            {"name": "gp2", "provisioner": "kubernetes.io/aws-ebs", "default": True},
            {"name": "gp3", "provisioner": "ebs.csi.aws.com", "default": False},
            {"name": "fast-ssd", "provisioner": "kubernetes.io/aws-ebs", "default": False},
            {"name": "nfs-storage", "provisioner": "nfs.csi.k8s.io", "default": False},
        ]

    @staticmethod
    def create_access_mode_options():
        """Create standard access mode options for testing."""
        return [
            {"mode": "ReadWriteOnce", "description": "Single node read/write"},
            {"mode": "ReadWriteMany", "description": "Multiple nodes read/write"},
            {"mode": "ReadOnlyMany", "description": "Multiple nodes read-only"},
            {"mode": "ReadWriteOncePod", "description": "Single pod read/write"},
        ]

    @staticmethod
    def create_helm_values_with_storage(
        storage_class: Optional[str] = None,
        access_mode: Optional[str] = None
    ) -> dict:
        """Create Helm values dict with storage configuration."""
        values = {
            "global": {
                "storageClass": storage_class or "",
            },
            "persistence": {
                "enabled": True,
            }
        }

        if access_mode:
            values["persistence"]["accessMode"] = access_mode

        return values


class AssertionHelpers:
    """Common assertion helpers for cluster settings tests."""

    @staticmethod
    def assert_cluster_settings_equal(actual: Any, expected: Any):
        """Assert that two cluster settings objects are equal."""
        assert actual.id == expected.id
        assert actual.cluster_id == expected.cluster_id
        assert actual.default_storage_class == expected.default_storage_class
        assert actual.default_access_mode == expected.default_access_mode
        assert actual.created_by == expected.created_by

    @staticmethod
    def assert_api_response_success(response: dict, expected_code: int = 200):
        """Assert that an API response indicates success."""
        assert response.get("success") is True
        assert response.get("code") == expected_code
        assert "data" in response

    @staticmethod
    def assert_storage_class_resolution(
        resolved_class: str,
        expected_class: str,
        message: str = None
    ):
        """Assert storage class resolution is correct."""
        assert resolved_class == expected_class, (
            message or f"Expected storage class '{expected_class}', got '{resolved_class}'"
        )
