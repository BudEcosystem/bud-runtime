"""
Unit tests for deployment endpoint validation logic.

Tests the new endpoint validation that requires at least one functional endpoint
before marking deployments as ready.
"""

import json
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from http import HTTPStatus

# Add the parent directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock dependencies before importing
sys.modules['budmicroframe.shared.psql_service'] = Mock()
sys.modules['budmicroframe.commons.logging'] = Mock()

def test_endpoint_validation_with_no_functional_endpoints():
    """Test that deployment fails when no endpoints are functional."""
    from budcluster.deployment.workflows import CreateDeploymentWorkflow
    from budcluster.deployment.schemas import VerifyDeploymentHealthRequest
    from budcluster.commons.constants import ClusterPlatformEnum
    from uuid import uuid4

    # Mock the workflow context
    mock_ctx = Mock()
    mock_ctx.workflow_id = str(uuid4())
    mock_ctx.task_id = str(uuid4())

    # Create request with test data
    request = VerifyDeploymentHealthRequest(
        cluster_id=uuid4(),
        cluster_config='{"test": "config"}',
        namespace="test-namespace",
        ingress_url="http://test.example.com",
        platform=ClusterPlatformEnum.KUBERNETES,
        add_worker=False,
    )

    # Mock deployment handler with no functional endpoints
    with patch('budcluster.deployment.workflows.DeploymentHandler') as mock_handler:
        mock_handler_instance = Mock()
        mock_handler.return_value = mock_handler_instance

        # Mock deployment status as ready
        mock_handler_instance.get_deployment_status.return_value = {
            "status": "ready",
            "ingress_health": True,
            "worker_data_list": [{"name": "test-worker"}]
        }

        # Mock supported endpoints - all endpoints are non-functional
        mock_handler_instance.identify_supported_endpoints.return_value = {
            "/v1/embeddings": False,
            "/v1/chat/completions": False,
            "/v1/classify": False
        }

        # Mock logging
        with patch('budcluster.deployment.workflows.logging') as mock_logging:
            mock_logger = Mock()
            mock_logging.get_logger.return_value = mock_logger

            # Call the activity
            result = CreateDeploymentWorkflow.verify_deployment_health(
                mock_ctx, request.model_dump_json()
            )

            # Parse the result
            result_dict = json.loads(result)

            # Verify that the deployment failed
            assert result_dict["code"] == HTTPStatus.BAD_REQUEST.value
            assert "No functional endpoints available" in result_dict["message"]

            # Verify that delete was called (since add_worker=False)
            mock_handler_instance.delete.assert_called_once()

            # Verify error logging
            mock_logger.error.assert_called_once()


def test_endpoint_validation_with_functional_endpoints():
    """Test that deployment succeeds when at least one endpoint is functional."""
    from budcluster.deployment.workflows import CreateDeploymentWorkflow
    from budcluster.deployment.schemas import VerifyDeploymentHealthRequest
    from budcluster.commons.constants import ClusterPlatformEnum
    from uuid import uuid4

    # Mock the workflow context
    mock_ctx = Mock()
    mock_ctx.workflow_id = str(uuid4())
    mock_ctx.task_id = str(uuid4())

    # Create request with test data
    request = VerifyDeploymentHealthRequest(
        cluster_id=uuid4(),
        cluster_config='{"test": "config"}',
        namespace="test-namespace",
        ingress_url="http://test.example.com",
        platform=ClusterPlatformEnum.KUBERNETES,
        add_worker=False,
    )

    # Mock deployment handler with one functional endpoint
    with patch('budcluster.deployment.workflows.DeploymentHandler') as mock_handler:
        mock_handler_instance = Mock()
        mock_handler.return_value = mock_handler_instance

        # Mock deployment status as ready
        mock_handler_instance.get_deployment_status.return_value = {
            "status": "ready",
            "ingress_health": True,
            "worker_data_list": [{"name": "test-worker"}]
        }

        # Mock supported endpoints - one endpoint is functional
        mock_handler_instance.identify_supported_endpoints.return_value = {
            "/v1/embeddings": False,
            "/v1/chat/completions": True,  # This one works
            "/v1/classify": False
        }

        # Mock logging
        with patch('budcluster.deployment.workflows.logging') as mock_logging:
            mock_logger = Mock()
            mock_logging.get_logger.return_value = mock_logger

            # Call the activity
            result = CreateDeploymentWorkflow.verify_deployment_health(
                mock_ctx, request.model_dump_json()
            )

            # Parse the result
            result_dict = json.loads(result)

            # Verify that the deployment succeeded
            assert result_dict["code"] == HTTPStatus.OK.value
            assert "Engine health verified successfully" in result_dict["message"]

            # Verify that delete was NOT called
            mock_handler_instance.delete.assert_not_called()

            # Verify the supported endpoints list contains only functional ones
            supported_endpoints = result_dict["param"]["supported_endpoints"]
            assert supported_endpoints == ["/v1/chat/completions"]


def test_endpoint_validation_with_add_worker_true():
    """Test that deployment with add_worker=True doesn't delete on endpoint failure."""
    from budcluster.deployment.workflows import CreateDeploymentWorkflow
    from budcluster.deployment.schemas import VerifyDeploymentHealthRequest
    from budcluster.commons.constants import ClusterPlatformEnum
    from uuid import uuid4

    # Mock the workflow context
    mock_ctx = Mock()
    mock_ctx.workflow_id = str(uuid4())
    mock_ctx.task_id = str(uuid4())

    # Create request with add_worker=True
    request = VerifyDeploymentHealthRequest(
        cluster_id=uuid4(),
        cluster_config='{"test": "config"}',
        namespace="test-namespace",
        ingress_url="http://test.example.com",
        platform=ClusterPlatformEnum.KUBERNETES,
        add_worker=True,  # This is the key difference
    )

    # Mock deployment handler with no functional endpoints
    with patch('budcluster.deployment.workflows.DeploymentHandler') as mock_handler:
        mock_handler_instance = Mock()
        mock_handler.return_value = mock_handler_instance

        # Mock deployment status as ready
        mock_handler_instance.get_deployment_status.return_value = {
            "status": "ready",
            "ingress_health": True,
            "worker_data_list": [{"name": "test-worker"}]
        }

        # Mock supported endpoints - no functional endpoints
        mock_handler_instance.identify_supported_endpoints.return_value = {
            "/v1/embeddings": False,
            "/v1/chat/completions": False,
            "/v1/classify": False
        }

        # Mock logging and database dependencies
        with patch('budcluster.deployment.workflows.logging') as mock_logging:
            mock_logger = Mock()
            mock_logging.get_logger.return_value = mock_logger

            # Call the activity
            result = CreateDeploymentWorkflow.verify_deployment_health(
                mock_ctx, request.model_dump_json()
            )

            # Parse the result
            result_dict = json.loads(result)

            # Verify that the deployment failed
            assert result_dict["code"] == HTTPStatus.BAD_REQUEST.value
            assert "No functional endpoints available" in result_dict["message"]

            # Verify that delete was NOT called (since add_worker=True)
            mock_handler_instance.delete.assert_not_called()


def test_endpoint_validation_with_classify_endpoint():
    """Test that deployment succeeds when only classify endpoint is functional (classifier models)."""
    from budcluster.deployment.workflows import CreateDeploymentWorkflow
    from budcluster.deployment.schemas import VerifyDeploymentHealthRequest
    from budcluster.commons.constants import ClusterPlatformEnum
    from uuid import uuid4

    # Mock the workflow context
    mock_ctx = Mock()
    mock_ctx.workflow_id = str(uuid4())
    mock_ctx.task_id = str(uuid4())

    # Create request with test data
    request = VerifyDeploymentHealthRequest(
        cluster_id=uuid4(),
        cluster_config='{"test": "config"}',
        namespace="test-classifier-namespace",
        ingress_url="http://test.example.com",
        platform=ClusterPlatformEnum.KUBERNETES,
        add_worker=False,
    )

    # Mock deployment handler with only classify endpoint functional
    with patch('budcluster.deployment.workflows.DeploymentHandler') as mock_handler:
        mock_handler_instance = Mock()
        mock_handler.return_value = mock_handler_instance

        # Mock deployment status as ready
        mock_handler_instance.get_deployment_status.return_value = {
            "status": "ready",
            "ingress_health": True,
            "worker_data_list": [{"name": "test-worker"}]
        }

        # Mock supported endpoints - only classify endpoint is functional (classifier model)
        mock_handler_instance.identify_supported_endpoints.return_value = {
            "/v1/embeddings": False,
            "/v1/chat/completions": False,
            "/v1/classify": True  # Classifier model only supports this
        }

        # Mock logging
        with patch('budcluster.deployment.workflows.logging') as mock_logging:
            mock_logger = Mock()
            mock_logging.get_logger.return_value = mock_logger

            # Call the activity
            result = CreateDeploymentWorkflow.verify_deployment_health(
                mock_ctx, request.model_dump_json()
            )

            # Parse the result
            result_dict = json.loads(result)

            # Verify that the deployment succeeded
            assert result_dict["code"] == HTTPStatus.OK.value
            assert "Engine health verified successfully" in result_dict["message"]

            # Verify that delete was NOT called
            mock_handler_instance.delete.assert_not_called()

            # Verify the supported endpoints list contains only functional ones
            supported_endpoints = result_dict["param"]["supported_endpoints"]
            assert supported_endpoints == ["/v1/classify"]


if __name__ == "__main__":
    print("Running endpoint validation tests...")
    test_endpoint_validation_with_no_functional_endpoints()
    print("✓ Test passed: Deployment fails with no functional endpoints")

    test_endpoint_validation_with_functional_endpoints()
    print("✓ Test passed: Deployment succeeds with functional endpoints")

    test_endpoint_validation_with_add_worker_true()
    print("✓ Test passed: No deletion when add_worker=True")

    test_endpoint_validation_with_classify_endpoint()
    print("✓ Test passed: Deployment succeeds with classify endpoint (classifier models)")

    print("All endpoint validation tests passed!")
