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

"""TDD Tests for Deployment Orchestration Service.

These tests follow TDD methodology - written BEFORE implementation.
Tests are expected to fail until the implementation is complete.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

# ============================================================================
# Orchestration Service Tests
# ============================================================================


class TestDeploymentOrchestrationService:
    """Tests for DeploymentOrchestrationService."""

    @pytest.fixture
    def mock_session(self) -> MagicMock:
        """Create a mock database session."""
        session = MagicMock()
        session.commit = MagicMock()
        session.rollback = MagicMock()
        return session

    @pytest.fixture
    def mock_budcluster_client(self) -> AsyncMock:
        """Create a mock BudCluster client."""
        client = AsyncMock()
        return client

    @pytest.fixture
    def service(self, mock_session: MagicMock, mock_budcluster_client: AsyncMock) -> Any:
        """Create a DeploymentOrchestrationService instance."""
        from budusecases.deployments.services import DeploymentOrchestrationService

        with patch(
            "budusecases.deployments.services.BudClusterClient",
            return_value=mock_budcluster_client,
        ):
            return DeploymentOrchestrationService(session=mock_session)

    @pytest.mark.asyncio
    async def test_create_deployment(
        self,
        service: Any,
        mock_session: MagicMock,
    ) -> None:
        """Test creating a new deployment."""
        from budusecases.deployments.schemas import DeploymentCreateSchema

        # Mock template lookup
        mock_template = MagicMock()
        mock_template.id = uuid4()
        mock_template.name = "simple-rag"
        mock_template.components = []
        mock_template.access = None

        with patch.object(service, "_get_template", return_value=mock_template):
            with patch.object(service, "_validate_components"):
                with patch.object(service, "_create_deployment_record") as mock_create:
                    mock_deployment = MagicMock()
                    mock_deployment.id = uuid4()
                    mock_create.return_value = mock_deployment

                    request = DeploymentCreateSchema(
                        name="my-deployment",
                        template_name="simple-rag",
                        cluster_id=str(uuid4()),
                        components={"llm": "llama-3-8b"},
                        parameters={"chunk_size": 512},
                    )

                    result = await service.create_deployment(
                        request=request,
                        user_id=uuid4(),
                    )

                    assert result is not None
                    mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_deployment_invalid_template(
        self,
        service: Any,
    ) -> None:
        """Test creating deployment with invalid template fails."""
        from budusecases.deployments.exceptions import TemplateNotFoundError
        from budusecases.deployments.schemas import DeploymentCreateSchema

        with patch.object(service, "_get_template", return_value=None):
            request = DeploymentCreateSchema(
                name="my-deployment",
                template_name="nonexistent-template",
                cluster_id=str(uuid4()),
            )

            with pytest.raises(TemplateNotFoundError):
                await service.create_deployment(
                    request=request,
                    user_id=uuid4(),
                )

    @pytest.mark.asyncio
    async def test_start_deployment(
        self,
        service: Any,
        mock_budcluster_client: AsyncMock,
    ) -> None:
        """Test starting a deployment."""
        from budusecases.clients.budcluster.schemas import JobResponse, JobStatus
        from budusecases.deployments.enums import DeploymentStatus

        deployment_id = uuid4()
        cluster_id = uuid4()
        component_id = uuid4()

        # Create mock component with all required attributes
        mock_component = MagicMock()
        mock_component.id = component_id
        mock_component.component_name = "llm"
        mock_component.component_type = "model"
        mock_component.config = {}  # Must be a dict, not MagicMock

        mock_deployment = MagicMock()
        mock_deployment.id = deployment_id
        mock_deployment.cluster_id = cluster_id  # Must be a UUID, not MagicMock
        mock_deployment.status = DeploymentStatus.PENDING
        mock_deployment.component_deployments = [mock_component]

        # Mock job creation response
        mock_job = JobResponse(
            id=uuid4(),
            name="deploy-llm",
            job_type="model_deployment",
            status=JobStatus.PENDING,
            cluster_id=cluster_id,
            config={},
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
        )
        mock_budcluster_client.create_job.return_value = mock_job

        with (
            patch.object(service, "_get_deployment", return_value=mock_deployment),
            patch("budusecases.deployments.services.app_settings") as mock_settings,
        ):
            mock_settings.use_pipeline_orchestration = False
            result = await service.start_deployment(deployment_id)

            assert result is not None
            mock_budcluster_client.create_job.assert_called()

    @pytest.mark.asyncio
    async def test_start_deployment_not_found(
        self,
        service: Any,
    ) -> None:
        """Test starting a nonexistent deployment fails."""
        from budusecases.deployments.exceptions import DeploymentNotFoundError

        with patch.object(service, "_get_deployment", return_value=None):
            with pytest.raises(DeploymentNotFoundError):
                await service.start_deployment(uuid4())

    @pytest.mark.asyncio
    async def test_start_deployment_wrong_status(
        self,
        service: Any,
    ) -> None:
        """Test starting a deployment in wrong status fails."""
        from budusecases.deployments.enums import DeploymentStatus
        from budusecases.deployments.exceptions import InvalidDeploymentStateError

        mock_deployment = MagicMock()
        mock_deployment.status = DeploymentStatus.RUNNING

        with patch.object(service, "_get_deployment", return_value=mock_deployment):
            with pytest.raises(InvalidDeploymentStateError):
                await service.start_deployment(uuid4())

    @pytest.mark.asyncio
    async def test_stop_deployment(
        self,
        service: Any,
        mock_budcluster_client: AsyncMock,
    ) -> None:
        """Test stopping a running deployment."""
        from budusecases.deployments.enums import DeploymentStatus

        deployment_id = uuid4()
        mock_deployment = MagicMock()
        mock_deployment.id = deployment_id
        mock_deployment.status = DeploymentStatus.RUNNING
        mock_deployment.pipeline_execution_id = None
        mock_deployment.access_config = None
        mock_deployment.component_deployments = [
            MagicMock(id=uuid4(), job_id=uuid4()),
        ]

        with patch.object(service, "_get_deployment", return_value=mock_deployment):
            result = await service.stop_deployment(deployment_id)

            assert result is not None
            mock_budcluster_client.cancel_job.assert_called()

    @pytest.mark.asyncio
    async def test_delete_deployment(
        self,
        service: Any,
        mock_session: MagicMock,
        mock_budcluster_client: AsyncMock,
    ) -> None:
        """Test deleting a stopped deployment returns cleanup context and deletes DB records."""
        from budusecases.deployments.enums import DeploymentStatus

        deployment_id = uuid4()
        cluster_id = uuid4()
        mock_deployment = MagicMock()
        mock_deployment.id = deployment_id
        mock_deployment.cluster_id = cluster_id
        mock_deployment.status = DeploymentStatus.STOPPED
        mock_deployment.pipeline_execution_id = None
        mock_deployment.component_deployments = []

        with patch.object(service, "_get_deployment", return_value=mock_deployment):
            result = await service.delete_deployment(deployment_id)

            assert result["cluster_id"] == cluster_id
            assert result["pipeline_execution_id"] is None
            assert result["job_ids"] == []
            mock_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_cleanup_deployment_resources_deletes_namespaces(
        self,
        service: Any,
        mock_session: MagicMock,
        mock_budcluster_client: AsyncMock,
    ) -> None:
        """Test background cleanup cancels pipeline and deletes namespaces."""
        from budusecases.deployments.services import DeploymentOrchestrationService

        cluster_id = uuid4()
        execution_id = "exec-123"

        mock_pipeline_client = AsyncMock()
        mock_pipeline_client.cancel_execution = AsyncMock()
        mock_pipeline_client.get_execution_progress = AsyncMock(
            return_value={
                "steps": [
                    {"outputs": {"namespace": "test-ns", "release_name": "test-release"}},
                ]
            }
        )

        cleanup_context = {
            "cluster_id": cluster_id,
            "pipeline_execution_id": execution_id,
            "job_ids": [],
        }

        with (
            patch(
                "budusecases.deployments.services.BudPipelineClient",
                return_value=mock_pipeline_client,
            ),
            patch(
                "budusecases.deployments.services.BudClusterClient",
                return_value=mock_budcluster_client,
            ),
        ):
            await DeploymentOrchestrationService.cleanup_deployment_resources(cleanup_context)

            mock_pipeline_client.cancel_execution.assert_called_once_with(execution_id)
            mock_budcluster_client.delete_namespace.assert_called_once_with(cluster_id=cluster_id, namespace="test-ns")

    @pytest.mark.asyncio
    async def test_sync_deployment_status(
        self,
        service: Any,
        mock_budcluster_client: AsyncMock,
    ) -> None:
        """Test syncing deployment status from BudCluster jobs."""
        from budusecases.clients.budcluster.schemas import JobResponse, JobStatus
        from budusecases.deployments.enums import ComponentDeploymentStatus, DeploymentStatus

        deployment_id = uuid4()
        job_id = uuid4()

        mock_deployment = MagicMock()
        mock_deployment.id = deployment_id
        mock_deployment.status = DeploymentStatus.DEPLOYING
        mock_deployment.pipeline_execution_id = None
        mock_deployment.component_deployments = [
            MagicMock(id=uuid4(), job_id=job_id, status=ComponentDeploymentStatus.DEPLOYING),
        ]

        # Mock job status as completed
        mock_job = JobResponse(
            id=job_id,
            name="deploy-llm",
            job_type="model_deployment",
            status=JobStatus.COMPLETED,
            cluster_id=uuid4(),
            config={},
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
        )
        mock_budcluster_client.get_job.return_value = mock_job

        with patch.object(service, "_get_deployment", return_value=mock_deployment):
            result = await service.sync_deployment_status(deployment_id)

            assert result is not None
            mock_budcluster_client.get_job.assert_called_with(job_id)

    @pytest.mark.asyncio
    async def test_get_deployment_details(
        self,
        service: Any,
    ) -> None:
        """Test getting full deployment details."""
        from budusecases.deployments.enums import DeploymentStatus

        deployment_id = uuid4()
        mock_deployment = MagicMock()
        mock_deployment.id = deployment_id
        mock_deployment.name = "my-deployment"
        mock_deployment.status = DeploymentStatus.RUNNING
        mock_deployment.component_deployments = []

        with patch.object(service, "_get_deployment", return_value=mock_deployment):
            result = await service.get_deployment_details(deployment_id)

            assert result is not None
            assert result.id == deployment_id


# ============================================================================
# Orchestration Component Deployment Tests
# ============================================================================


class TestComponentDeploymentOrchestration:
    """Tests for component deployment orchestration."""

    @pytest.fixture
    def mock_session(self) -> MagicMock:
        """Create a mock database session."""
        return MagicMock()

    @pytest.fixture
    def mock_budcluster_client(self) -> AsyncMock:
        """Create a mock BudCluster client."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_deploy_component_model(
        self,
        mock_session: MagicMock,
        mock_budcluster_client: AsyncMock,
    ) -> None:
        """Test deploying a model component."""
        from budusecases.clients.budcluster.schemas import JobResponse, JobStatus, JobType
        from budusecases.deployments.services import DeploymentOrchestrationService

        with patch(
            "budusecases.deployments.services.BudClusterClient",
            return_value=mock_budcluster_client,
        ):
            service = DeploymentOrchestrationService(session=mock_session)

            mock_job = JobResponse(
                id=uuid4(),
                name="deploy-llama-3-8b",
                job_type=JobType.MODEL_DEPLOYMENT,
                status=JobStatus.PENDING,
                cluster_id=uuid4(),
                config={},
                created_at="2024-01-01T00:00:00Z",
                updated_at="2024-01-01T00:00:00Z",
            )
            mock_budcluster_client.create_job.return_value = mock_job

            component = MagicMock()
            component.id = uuid4()
            component.component_name = "llm"
            component.component_type = "model"
            component.config = {}  # Must be a dict, not MagicMock

            job = await service._deploy_component(
                component=component,
                cluster_id=uuid4(),
                deployment_id=uuid4(),
            )

            assert job is not None
            mock_budcluster_client.create_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_deploy_component_embedding_model(
        self,
        mock_session: MagicMock,
        mock_budcluster_client: AsyncMock,
    ) -> None:
        """Test deploying an embedding model component (uses MODEL_DEPLOYMENT)."""
        from budusecases.clients.budcluster.schemas import JobResponse, JobStatus, JobType
        from budusecases.deployments.services import DeploymentOrchestrationService

        with patch(
            "budusecases.deployments.services.BudClusterClient",
            return_value=mock_budcluster_client,
        ):
            service = DeploymentOrchestrationService(session=mock_session)

            mock_job = JobResponse(
                id=uuid4(),
                name="deploy-bge-large",
                job_type=JobType.MODEL_DEPLOYMENT,
                status=JobStatus.PENDING,
                cluster_id=uuid4(),
                config={},
                created_at="2024-01-01T00:00:00Z",
                updated_at="2024-01-01T00:00:00Z",
            )
            mock_budcluster_client.create_job.return_value = mock_job

            component = MagicMock()
            component.id = uuid4()
            component.component_name = "bge-large-en"
            component.component_type = "model"
            component.config = {}  # Must be a dict, not MagicMock

            job = await service._deploy_component(
                component=component,
                cluster_id=uuid4(),
                deployment_id=uuid4(),
            )

            assert job is not None
            # Verify correct job type - all models use MODEL_DEPLOYMENT
            call_args = mock_budcluster_client.create_job.call_args
            request = call_args[0][0]
            assert request.job_type == JobType.MODEL_DEPLOYMENT


# ============================================================================
# Deployment Validation Tests
# ============================================================================


class TestDeploymentValidation:
    """Tests for deployment validation logic."""

    @pytest.fixture
    def mock_session(self) -> MagicMock:
        """Create a mock database session."""
        return MagicMock()

    def test_validate_required_components(
        self,
        mock_session: MagicMock,
    ) -> None:
        """Test validation of required components."""
        from budusecases.deployments.exceptions import MissingRequiredComponentError
        from budusecases.deployments.services import DeploymentOrchestrationService

        with patch(
            "budusecases.deployments.services.BudClusterClient",
        ):
            service = DeploymentOrchestrationService(session=mock_session)

            # Note: MagicMock(name=...) doesn't set .name attribute, need to set separately
            llm_comp = MagicMock(component_type="model", required=True)
            llm_comp.name = "llm"
            embedder_comp = MagicMock(component_type="embedder", required=True)
            embedder_comp.name = "embedder"
            reranker_comp = MagicMock(component_type="reranker", required=False)
            reranker_comp.name = "reranker"

            template_components = [llm_comp, embedder_comp, reranker_comp]

            # Missing required embedder
            selected_components = {"llm": "llama-3-8b"}

            with pytest.raises(MissingRequiredComponentError):
                service._validate_required_components(
                    template_components=template_components,
                    selected_components=selected_components,
                )

    def test_validate_required_components_success(
        self,
        mock_session: MagicMock,
    ) -> None:
        """Test validation passes with all required components."""
        from budusecases.deployments.services import DeploymentOrchestrationService

        with patch(
            "budusecases.deployments.services.BudClusterClient",
        ):
            service = DeploymentOrchestrationService(session=mock_session)

            # Note: MagicMock(name=...) doesn't set .name attribute, need to set separately
            llm_comp = MagicMock(component_type="model", required=True)
            llm_comp.name = "llm"
            embedder_comp = MagicMock(component_type="embedder", required=True)
            embedder_comp.name = "embedder"

            template_components = [llm_comp, embedder_comp]

            selected_components = {
                "llm": "llama-3-8b",
                "embedder": "bge-large-en",
            }

            # Should not raise
            service._validate_required_components(
                template_components=template_components,
                selected_components=selected_components,
            )

    def test_validate_component_compatibility(
        self,
        mock_session: MagicMock,
    ) -> None:
        """Test validation of component compatibility."""
        from budusecases.deployments.exceptions import IncompatibleComponentError
        from budusecases.deployments.services import DeploymentOrchestrationService

        with patch(
            "budusecases.deployments.services.BudClusterClient",
        ):
            service = DeploymentOrchestrationService(session=mock_session)

            # Note: MagicMock(name=...) doesn't set .name attribute, need to set separately
            template_component = MagicMock(
                component_type="model",
                compatible_components=["llama-3-8b", "mistral-7b"],
            )
            template_component.name = "llm"

            # Incompatible component
            with pytest.raises(IncompatibleComponentError):
                service._validate_component_compatibility(
                    template_component=template_component,
                    selected_component_name="gpt-4",  # Not in compatible list
                )


# ============================================================================
# Deployment Exceptions Tests
# ============================================================================


class TestDeploymentExceptions:
    """Tests for deployment exception classes."""

    def test_deployment_not_found_error(self) -> None:
        """Test DeploymentNotFoundError exception."""
        from budusecases.deployments.exceptions import DeploymentNotFoundError

        error = DeploymentNotFoundError("Deployment xyz not found")
        assert str(error) == "Deployment xyz not found"

    def test_template_not_found_error(self) -> None:
        """Test TemplateNotFoundError exception."""
        from budusecases.deployments.exceptions import TemplateNotFoundError

        error = TemplateNotFoundError("Template simple-rag not found")
        assert str(error) == "Template simple-rag not found"

    def test_invalid_deployment_state_error(self) -> None:
        """Test InvalidDeploymentStateError exception."""
        from budusecases.deployments.exceptions import InvalidDeploymentStateError

        error = InvalidDeploymentStateError("Cannot start deployment in RUNNING state")
        assert "RUNNING" in str(error)

    def test_missing_required_component_error(self) -> None:
        """Test MissingRequiredComponentError exception."""
        from budusecases.deployments.exceptions import MissingRequiredComponentError

        error = MissingRequiredComponentError("Missing required component: embedder")
        assert "embedder" in str(error)

    def test_incompatible_component_error(self) -> None:
        """Test IncompatibleComponentError exception."""
        from budusecases.deployments.exceptions import IncompatibleComponentError

        error = IncompatibleComponentError("Component gpt-4 is not compatible with template")
        assert "gpt-4" in str(error)
