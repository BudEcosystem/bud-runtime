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

"""CRUD operations for Deployment models."""

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .enums import ComponentDeploymentStatus, DeploymentStatus
from .models import ComponentDeployment, UseCaseDeployment


class DeploymentDataManager:
    """Data manager for Deployment CRUD operations."""

    def __init__(self, session: Session) -> None:
        """Initialize the data manager.

        Args:
            session: SQLAlchemy database session.
        """
        self.session = session

    def create_deployment(
        self,
        name: str,
        template_id: UUID,
        cluster_id: UUID,
        user_id: UUID,
        project_id: UUID | None = None,
        parameters: dict[str, Any] | None = None,
        metadata_: dict[str, Any] | None = None,
        access_config: dict[str, Any] | None = None,
    ) -> UseCaseDeployment:
        """Create a new use case deployment.

        Args:
            name: Deployment name.
            template_id: Template UUID.
            cluster_id: Target cluster UUID.
            user_id: User UUID.
            project_id: Project UUID for API access scoping.
            parameters: Deployment parameters.
            metadata_: Additional metadata.
            access_config: Snapshot of the template's access configuration.

        Returns:
            Created UseCaseDeployment instance.
        """
        deployment = UseCaseDeployment(
            name=name,
            template_id=template_id,
            cluster_id=cluster_id,
            user_id=user_id,
            project_id=project_id,
            status=DeploymentStatus.PENDING,
            parameters=parameters or {},
            metadata_=metadata_ or {},
            access_config=access_config,
        )
        self.session.add(deployment)
        self.session.flush()
        return deployment

    def get_deployment(self, deployment_id: UUID) -> UseCaseDeployment | None:
        """Get a deployment by ID.

        Args:
            deployment_id: Deployment UUID.

        Returns:
            UseCaseDeployment if found, None otherwise.
        """
        return self.session.get(UseCaseDeployment, deployment_id)

    def get_deployment_by_pipeline_execution(self, execution_id: str) -> UseCaseDeployment | None:
        """Get a deployment by pipeline execution ID.

        Args:
            execution_id: Pipeline execution ID.

        Returns:
            UseCaseDeployment if found, None otherwise.
        """
        stmt = (
            select(UseCaseDeployment)
            .where(UseCaseDeployment.pipeline_execution_id == execution_id)
            .options(selectinload(UseCaseDeployment.component_deployments))
        )
        result = self.session.execute(stmt).scalar_one_or_none()
        return result

    def list_deployments(
        self,
        page: int = 1,
        page_size: int = 20,
        user_id: UUID | None = None,
        cluster_id: UUID | None = None,
        template_id: UUID | None = None,
        status: DeploymentStatus | None = None,
        project_id: UUID | None = None,
    ) -> Sequence[UseCaseDeployment]:
        """List deployments with optional filtering and pagination.

        Args:
            page: Page number (1-indexed).
            page_size: Number of items per page.
            user_id: Filter by user ID.
            cluster_id: Filter by cluster ID.
            template_id: Filter by template ID.
            status: Filter by status.
            project_id: Filter by project ID.

        Returns:
            List of deployments matching the criteria.
        """
        stmt = select(UseCaseDeployment)

        if user_id:
            stmt = stmt.where(UseCaseDeployment.user_id == user_id)
        if cluster_id:
            stmt = stmt.where(UseCaseDeployment.cluster_id == cluster_id)
        if template_id:
            stmt = stmt.where(UseCaseDeployment.template_id == template_id)
        if status:
            stmt = stmt.where(UseCaseDeployment.status == status)
        if project_id:
            stmt = stmt.where(UseCaseDeployment.project_id == project_id)

        stmt = stmt.order_by(UseCaseDeployment.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        return self.session.execute(stmt).scalars().all()

    def count_deployments(
        self,
        user_id: UUID | None = None,
        cluster_id: UUID | None = None,
        template_id: UUID | None = None,
        status: DeploymentStatus | None = None,
        project_id: UUID | None = None,
    ) -> int:
        """Count deployments matching the criteria.

        Args:
            user_id: Filter by user ID.
            cluster_id: Filter by cluster ID.
            template_id: Filter by template ID.
            status: Filter by status.
            project_id: Filter by project ID.

        Returns:
            Count of matching deployments.
        """
        from sqlalchemy import func

        stmt = select(func.count(UseCaseDeployment.id))

        if user_id:
            stmt = stmt.where(UseCaseDeployment.user_id == user_id)
        if cluster_id:
            stmt = stmt.where(UseCaseDeployment.cluster_id == cluster_id)
        if template_id:
            stmt = stmt.where(UseCaseDeployment.template_id == template_id)
        if status:
            stmt = stmt.where(UseCaseDeployment.status == status)
        if project_id:
            stmt = stmt.where(UseCaseDeployment.project_id == project_id)

        result = self.session.execute(stmt).scalar()
        return result or 0

    def update_deployment_status(
        self,
        deployment_id: UUID,
        status: DeploymentStatus,
        error_message: str | None = None,
    ) -> UseCaseDeployment | None:
        """Update a deployment's status.

        Args:
            deployment_id: Deployment UUID.
            status: New status.
            error_message: Optional error message.

        Returns:
            Updated deployment if found, None otherwise.
        """
        deployment = self.get_deployment(deployment_id)
        if deployment is None:
            return None

        deployment.status = status
        if error_message:
            deployment.error_message = error_message

        self.session.flush()
        return deployment

    def update_deployment_pipeline_execution(
        self,
        deployment_id: UUID,
        execution_id: str,
    ) -> UseCaseDeployment | None:
        """Update a deployment's pipeline execution ID.

        Args:
            deployment_id: Deployment UUID.
            execution_id: Pipeline execution ID.

        Returns:
            Updated deployment if found, None otherwise.
        """
        deployment = self.get_deployment(deployment_id)
        if deployment is None:
            return None

        deployment.pipeline_execution_id = execution_id
        self.session.flush()
        return deployment

    def update_deployment_gateway_url(
        self,
        deployment_id: UUID,
        gateway_url: str | None,
    ) -> UseCaseDeployment | None:
        """Update a deployment's gateway URL.

        Sets or clears the ``gateway_url`` field which holds the Envoy Gateway
        external endpoint used for routing traffic to the deployed use case.

        Args:
            deployment_id: Deployment UUID.
            gateway_url: The gateway endpoint URL, or ``None`` to clear it.

        Returns:
            Updated deployment if found, None otherwise.
        """
        deployment = self.get_deployment(deployment_id)
        if deployment is None:
            return None

        deployment.gateway_url = gateway_url
        self.session.flush()
        return deployment

    def delete_deployment(self, deployment_id: UUID) -> bool:
        """Delete a deployment.

        Args:
            deployment_id: Deployment UUID.

        Returns:
            True if deleted, False if not found.
        """
        deployment = self.get_deployment(deployment_id)
        if deployment is None:
            return False

        self.session.delete(deployment)
        self.session.flush()
        return True

    def create_component_deployment(
        self,
        usecase_deployment_id: UUID,
        component_name: str,
        component_type: str,
        selected_component: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> ComponentDeployment:
        """Create a component deployment.

        Args:
            usecase_deployment_id: Parent deployment UUID.
            component_name: Component slot name.
            component_type: Component type.
            selected_component: Name of the component chosen by the user.
            config: Component configuration.

        Returns:
            Created ComponentDeployment instance.
        """
        component = ComponentDeployment(
            usecase_deployment_id=usecase_deployment_id,
            component_name=component_name,
            component_type=component_type,
            selected_component=selected_component,
            status=ComponentDeploymentStatus.PENDING,
            config=config or {},
        )
        self.session.add(component)
        self.session.flush()
        return component

    def get_component_deployments(self, usecase_deployment_id: UUID) -> Sequence[ComponentDeployment]:
        """Get all component deployments for a use case deployment.

        Args:
            usecase_deployment_id: Parent deployment UUID.

        Returns:
            List of component deployments.
        """
        stmt = (
            select(ComponentDeployment)
            .where(ComponentDeployment.usecase_deployment_id == usecase_deployment_id)
            .order_by(ComponentDeployment.created_at)
        )
        return self.session.execute(stmt).scalars().all()

    def update_component_deployment_status(
        self,
        component_id: UUID,
        status: ComponentDeploymentStatus,
        endpoint_url: str | None = None,
        error_message: str | None = None,
    ) -> ComponentDeployment | None:
        """Update a component deployment's status.

        Args:
            component_id: Component deployment UUID.
            status: New status.
            endpoint_url: Optional endpoint URL.
            error_message: Optional error message.

        Returns:
            Updated component if found, None otherwise.
        """
        component = self.session.get(ComponentDeployment, component_id)
        if component is None:
            return None

        component.status = status
        if endpoint_url:
            component.endpoint_url = endpoint_url
        if error_message:
            component.error_message = error_message

        self.session.flush()
        return component

    def update_component_deployment_job(
        self,
        component_id: UUID,
        job_id: UUID,
    ) -> ComponentDeployment | None:
        """Link a component deployment to a BudCluster job.

        Args:
            component_id: Component deployment UUID.
            job_id: BudCluster job UUID.

        Returns:
            Updated component if found, None otherwise.
        """
        component = self.session.get(ComponentDeployment, component_id)
        if component is None:
            return None

        component.job_id = job_id
        self.session.flush()
        return component
