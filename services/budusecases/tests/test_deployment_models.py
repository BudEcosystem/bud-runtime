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

"""TDD Tests for Deployment Models and CRUD operations.

These tests follow TDD methodology - written BEFORE implementation.
Tests are expected to fail until the implementation is complete.
"""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

# ============================================================================
# Deployment Enums Tests
# ============================================================================


class TestDeploymentEnums:
    """Tests for deployment-related enums."""

    def test_deployment_status_enum(self) -> None:
        """Test DeploymentStatus enum values."""
        from budusecases.deployments.enums import DeploymentStatus

        assert DeploymentStatus.PENDING == "pending"
        assert DeploymentStatus.PROVISIONING == "provisioning"
        assert DeploymentStatus.DEPLOYING == "deploying"
        assert DeploymentStatus.RUNNING == "running"
        assert DeploymentStatus.FAILED == "failed"
        assert DeploymentStatus.STOPPED == "stopped"
        assert DeploymentStatus.DELETING == "deleting"

    def test_component_deployment_status_enum(self) -> None:
        """Test ComponentDeploymentStatus enum values."""
        from budusecases.deployments.enums import ComponentDeploymentStatus

        assert ComponentDeploymentStatus.PENDING == "pending"
        assert ComponentDeploymentStatus.DEPLOYING == "deploying"
        assert ComponentDeploymentStatus.RUNNING == "running"
        assert ComponentDeploymentStatus.FAILED == "failed"
        assert ComponentDeploymentStatus.STOPPED == "stopped"


# ============================================================================
# Deployment Model Tests
# ============================================================================


class TestUseCaseDeploymentModel:
    """Tests for UseCaseDeployment SQLAlchemy model."""

    def test_deployment_model_creation(self) -> None:
        """Test creating a UseCaseDeployment model instance."""
        from budusecases.deployments.enums import DeploymentStatus
        from budusecases.deployments.models import UseCaseDeployment

        deployment_id = uuid4()
        template_id = uuid4()
        cluster_id = uuid4()
        user_id = uuid4()

        deployment = UseCaseDeployment(
            id=deployment_id,
            name="my-rag-deployment",
            template_id=template_id,
            cluster_id=cluster_id,
            user_id=user_id,
            status=DeploymentStatus.PENDING,
            parameters={
                "chunk_size": 512,
                "retrieval_k": 5,
            },
            metadata_={
                "project_id": str(uuid4()),
            },
        )

        assert deployment.id == deployment_id
        assert deployment.name == "my-rag-deployment"
        assert deployment.template_id == template_id
        assert deployment.cluster_id == cluster_id
        assert deployment.status == DeploymentStatus.PENDING
        assert deployment.parameters["chunk_size"] == 512

    def test_deployment_model_default_values(self) -> None:
        """Test UseCaseDeployment model default values."""
        from budusecases.deployments.enums import DeploymentStatus
        from budusecases.deployments.models import UseCaseDeployment

        deployment = UseCaseDeployment(
            name="test-deployment",
            template_id=uuid4(),
            cluster_id=uuid4(),
            user_id=uuid4(),
        )

        assert deployment.status == DeploymentStatus.PENDING
        assert deployment.parameters == {}
        assert deployment.metadata_ == {}
        assert deployment.error_message is None


class TestComponentDeploymentModel:
    """Tests for ComponentDeployment SQLAlchemy model."""

    def test_component_deployment_creation(self) -> None:
        """Test creating a ComponentDeployment model instance."""
        from budusecases.deployments.enums import ComponentDeploymentStatus
        from budusecases.deployments.models import ComponentDeployment

        component_id = uuid4()
        deployment_id = uuid4()
        job_id = uuid4()

        component = ComponentDeployment(
            id=component_id,
            usecase_deployment_id=deployment_id,
            component_name="llm",
            component_type="model",
            selected_component="llama-3-8b",
            job_id=job_id,
            status=ComponentDeploymentStatus.PENDING,
            config={
                "model_id": "meta-llama/Meta-Llama-3-8B-Instruct",
            },
        )

        assert component.id == component_id
        assert component.usecase_deployment_id == deployment_id
        assert component.component_name == "llm"
        assert component.job_id == job_id
        assert component.status == ComponentDeploymentStatus.PENDING

    def test_component_deployment_relationship(self) -> None:
        """Test ComponentDeployment relationship to UseCaseDeployment."""
        from budusecases.deployments.enums import ComponentDeploymentStatus
        from budusecases.deployments.models import (
            ComponentDeployment,
            UseCaseDeployment,
        )

        deployment_id = uuid4()

        # These would normally be managed by SQLAlchemy ORM
        deployment = UseCaseDeployment(
            id=deployment_id,
            name="test",
            template_id=uuid4(),
            cluster_id=uuid4(),
            user_id=uuid4(),
        )

        component = ComponentDeployment(
            usecase_deployment_id=deployment_id,
            component_name="embedder",
            component_type="embedder",
            selected_component="bge-large-en",
            status=ComponentDeploymentStatus.PENDING,
        )

        assert component.usecase_deployment_id == deployment.id


# ============================================================================
# Deployment Schema Tests
# ============================================================================


class TestDeploymentSchemas:
    """Tests for Deployment Pydantic schemas."""

    def test_deployment_create_schema(self) -> None:
        """Test DeploymentCreateSchema validation."""
        from budusecases.deployments.schemas import DeploymentCreateSchema

        data = {
            "name": "my-deployment",
            "template_name": "simple-rag",
            "cluster_id": str(uuid4()),
            "components": {
                "llm": "llama-3-8b",
                "embedder": "bge-large-en",
                "vector_db": "qdrant",
            },
            "parameters": {
                "chunk_size": 512,
                "retrieval_k": 5,
            },
        }
        schema = DeploymentCreateSchema.model_validate(data)

        assert schema.name == "my-deployment"
        assert schema.template_name == "simple-rag"
        assert schema.components["llm"] == "llama-3-8b"
        assert schema.parameters["chunk_size"] == 512

    def test_deployment_create_schema_minimal(self) -> None:
        """Test DeploymentCreateSchema with minimal fields."""
        from budusecases.deployments.schemas import DeploymentCreateSchema

        data = {
            "name": "minimal-deployment",
            "template_name": "chatbot",
            "cluster_id": str(uuid4()),
        }
        schema = DeploymentCreateSchema.model_validate(data)

        assert schema.name == "minimal-deployment"
        assert schema.components == {}
        assert schema.parameters == {}

    def test_deployment_response_schema(self) -> None:
        """Test DeploymentResponseSchema."""
        from budusecases.deployments.schemas import DeploymentResponseSchema

        data = {
            "id": str(uuid4()),
            "name": "test-deployment",
            "template_id": str(uuid4()),
            "template_name": "simple-rag",
            "cluster_id": str(uuid4()),
            "status": "running",
            "parameters": {"chunk_size": 512},
            "components": [],
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }
        schema = DeploymentResponseSchema.model_validate(data)

        assert schema.status == "running"
        assert schema.template_name == "simple-rag"

    def test_component_deployment_response_schema(self) -> None:
        """Test ComponentDeploymentResponseSchema."""
        from budusecases.deployments.schemas import ComponentDeploymentResponseSchema

        data = {
            "id": str(uuid4()),
            "component_name": "llm",
            "component_type": "model",
            "selected_component": "llama-3-8b",
            "job_id": str(uuid4()),
            "status": "running",
            "endpoint_url": "http://llm.example.com",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }
        schema = ComponentDeploymentResponseSchema.model_validate(data)

        assert schema.component_name == "llm"
        assert schema.status == "running"
        assert schema.endpoint_url == "http://llm.example.com"


# ============================================================================
# Deployment CRUD Tests
# ============================================================================


class TestDeploymentCRUD:
    """Tests for Deployment CRUD operations."""

    @pytest.fixture
    def mock_session(self) -> MagicMock:
        """Create a mock database session."""
        return MagicMock()

    def test_create_deployment(self, mock_session: MagicMock) -> None:
        """Test creating a deployment."""
        from budusecases.deployments.crud import DeploymentDataManager

        manager = DeploymentDataManager(session=mock_session)

        manager.create_deployment(
            name="new-deployment",
            template_id=uuid4(),
            cluster_id=uuid4(),
            user_id=uuid4(),
            parameters={"chunk_size": 512},
            metadata_={"project_id": str(uuid4())},
        )

        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    def test_get_deployment(self, mock_session: MagicMock) -> None:
        """Test getting a deployment by ID."""
        from budusecases.deployments.crud import DeploymentDataManager
        from budusecases.deployments.models import UseCaseDeployment

        deployment_id = uuid4()
        mock_deployment = MagicMock(spec=UseCaseDeployment)
        mock_deployment.id = deployment_id
        mock_session.get.return_value = mock_deployment

        manager = DeploymentDataManager(session=mock_session)
        result = manager.get_deployment(deployment_id)

        assert result == mock_deployment

    def test_list_deployments(self, mock_session: MagicMock) -> None:
        """Test listing deployments with filters."""
        from budusecases.deployments.crud import DeploymentDataManager
        from budusecases.deployments.models import UseCaseDeployment

        mock_deployments = [MagicMock(spec=UseCaseDeployment) for _ in range(3)]
        mock_session.execute.return_value.scalars.return_value.all.return_value = mock_deployments

        manager = DeploymentDataManager(session=mock_session)
        results = manager.list_deployments(page=1, page_size=10)

        assert len(results) == 3

    def test_list_deployments_by_user(self, mock_session: MagicMock) -> None:
        """Test listing deployments filtered by user."""
        from budusecases.deployments.crud import DeploymentDataManager
        from budusecases.deployments.models import UseCaseDeployment

        user_id = uuid4()
        mock_deployments = [MagicMock(spec=UseCaseDeployment)]
        mock_session.execute.return_value.scalars.return_value.all.return_value = mock_deployments

        manager = DeploymentDataManager(session=mock_session)
        results = manager.list_deployments(user_id=user_id)

        assert len(results) == 1

    def test_list_deployments_by_cluster(self, mock_session: MagicMock) -> None:
        """Test listing deployments filtered by cluster."""
        from budusecases.deployments.crud import DeploymentDataManager

        cluster_id = uuid4()
        mock_session.execute.return_value.scalars.return_value.all.return_value = []

        manager = DeploymentDataManager(session=mock_session)
        results = manager.list_deployments(cluster_id=cluster_id)

        assert len(results) == 0

    def test_update_deployment_status(self, mock_session: MagicMock) -> None:
        """Test updating a deployment's status."""
        from budusecases.deployments.crud import DeploymentDataManager
        from budusecases.deployments.enums import DeploymentStatus
        from budusecases.deployments.models import UseCaseDeployment

        deployment_id = uuid4()
        mock_deployment = MagicMock(spec=UseCaseDeployment)
        mock_deployment.id = deployment_id
        mock_session.get.return_value = mock_deployment

        manager = DeploymentDataManager(session=mock_session)
        manager.update_deployment_status(
            deployment_id=deployment_id,
            status=DeploymentStatus.RUNNING,
        )

        assert mock_deployment.status == DeploymentStatus.RUNNING

    def test_update_deployment_error(self, mock_session: MagicMock) -> None:
        """Test updating a deployment with error message."""
        from budusecases.deployments.crud import DeploymentDataManager
        from budusecases.deployments.enums import DeploymentStatus
        from budusecases.deployments.models import UseCaseDeployment

        deployment_id = uuid4()
        mock_deployment = MagicMock(spec=UseCaseDeployment)
        mock_session.get.return_value = mock_deployment

        manager = DeploymentDataManager(session=mock_session)
        manager.update_deployment_status(
            deployment_id=deployment_id,
            status=DeploymentStatus.FAILED,
            error_message="Deployment failed due to insufficient resources",
        )

        assert mock_deployment.status == DeploymentStatus.FAILED
        assert mock_deployment.error_message == "Deployment failed due to insufficient resources"

    def test_delete_deployment(self, mock_session: MagicMock) -> None:
        """Test deleting a deployment."""
        from budusecases.deployments.crud import DeploymentDataManager
        from budusecases.deployments.models import UseCaseDeployment

        deployment_id = uuid4()
        mock_deployment = MagicMock(spec=UseCaseDeployment)
        mock_session.get.return_value = mock_deployment

        manager = DeploymentDataManager(session=mock_session)
        result = manager.delete_deployment(deployment_id)

        assert result is True
        mock_session.delete.assert_called_once()

    def test_create_component_deployment(self, mock_session: MagicMock) -> None:
        """Test creating a component deployment."""
        from budusecases.deployments.crud import DeploymentDataManager

        manager = DeploymentDataManager(session=mock_session)

        manager.create_component_deployment(
            usecase_deployment_id=uuid4(),
            component_name="llm",
            component_type="model",
            selected_component="llama-3-8b",
            config={"model_id": "meta-llama/Meta-Llama-3-8B-Instruct"},
        )

        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    def test_get_component_deployments(self, mock_session: MagicMock) -> None:
        """Test getting component deployments for a usecase deployment."""
        from budusecases.deployments.crud import DeploymentDataManager
        from budusecases.deployments.models import ComponentDeployment

        deployment_id = uuid4()
        mock_components = [MagicMock(spec=ComponentDeployment) for _ in range(3)]
        mock_session.execute.return_value.scalars.return_value.all.return_value = mock_components

        manager = DeploymentDataManager(session=mock_session)
        results = manager.get_component_deployments(deployment_id)

        assert len(results) == 3

    def test_update_component_deployment_status(self, mock_session: MagicMock) -> None:
        """Test updating a component deployment's status."""
        from budusecases.deployments.crud import DeploymentDataManager
        from budusecases.deployments.enums import ComponentDeploymentStatus
        from budusecases.deployments.models import ComponentDeployment

        component_id = uuid4()
        mock_component = MagicMock(spec=ComponentDeployment)
        mock_session.get.return_value = mock_component

        manager = DeploymentDataManager(session=mock_session)
        manager.update_component_deployment_status(
            component_id=component_id,
            status=ComponentDeploymentStatus.RUNNING,
            endpoint_url="http://llm.example.com",
        )

        assert mock_component.status == ComponentDeploymentStatus.RUNNING
        assert mock_component.endpoint_url == "http://llm.example.com"

    def test_update_component_deployment_job(self, mock_session: MagicMock) -> None:
        """Test linking a component deployment to a job."""
        from budusecases.deployments.crud import DeploymentDataManager
        from budusecases.deployments.models import ComponentDeployment

        component_id = uuid4()
        job_id = uuid4()
        mock_component = MagicMock(spec=ComponentDeployment)
        mock_session.get.return_value = mock_component

        manager = DeploymentDataManager(session=mock_session)
        manager.update_component_deployment_job(
            component_id=component_id,
            job_id=job_id,
        )

        assert mock_component.job_id == job_id
