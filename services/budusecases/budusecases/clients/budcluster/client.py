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

"""BudCluster client for Dapr service invocation."""

import asyncio
import json
import logging
from uuid import UUID

from dapr.clients import DaprClient

from .exceptions import (
    BudClusterConnectionError,
    BudClusterError,
    BudClusterTimeoutError,
    BudClusterValidationError,
    ClusterNotFoundError,
    JobNotFoundError,
)
from .schemas import (
    ClusterCapacityResponse,
    ClusterInfoResponse,
    JobCreateRequest,
    JobListResponse,
    JobResponse,
    JobStatusUpdateRequest,
)

logger = logging.getLogger(__name__)


class BudClusterClient:
    """Client for communicating with BudCluster via Dapr service invocation."""

    def __init__(
        self,
        app_id: str | None = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> None:
        """Initialize the BudCluster client.

        Args:
            app_id: Dapr app ID for BudCluster service.
            max_retries: Maximum number of retry attempts.
            retry_delay: Delay between retries in seconds.
        """
        if app_id is None:
            from budusecases.commons.config import app_settings

            app_id = app_settings.budcluster_app_id

        self.app_id = app_id
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._client = DaprClient()

    async def _invoke_method(
        self,
        method_name: str,
        http_verb: str = "GET",
        data: dict | None = None,
    ) -> dict:
        """Invoke a method on BudCluster with retry logic.

        Args:
            method_name: API method/endpoint to invoke.
            http_verb: HTTP verb (GET, POST, PUT, DELETE).
            data: Optional request body data.

        Returns:
            Response data as dict.

        Raises:
            BudClusterError: On unrecoverable errors.
        """
        last_error: Exception | None = None

        # Dapr SDK invoke_method expects data as bytes/str, not dict
        serialized_data = json.dumps(data).encode("utf-8") if data is not None else None

        for attempt in range(self.max_retries):
            try:
                response = await asyncio.to_thread(
                    self._client.invoke_method,
                    app_id=self.app_id,
                    method_name=method_name,
                    http_verb=http_verb,
                    data=serialized_data,
                    content_type="application/json",
                )

                # Handle response status codes
                # status_code may be None for gRPC responses
                status_code = getattr(response, "status_code", 200) or 200

                if status_code == 404:
                    # Determine which not found error to raise
                    if "jobs" in method_name:
                        raise JobNotFoundError(f"Job not found: {method_name}")
                    elif "clusters" in method_name:
                        raise ClusterNotFoundError(f"Cluster not found: {method_name}")
                    raise BudClusterError(f"Resource not found: {method_name}")

                if status_code == 422:
                    raise BudClusterValidationError(f"Validation error: {response.json()}")

                if status_code >= 500:
                    raise BudClusterError(f"Server error: {status_code} - {response.json()}")

                return response.json()

            except TimeoutError as e:
                last_error = e
                logger.warning(f"Timeout on attempt {attempt + 1}/{self.max_retries}: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                else:
                    raise BudClusterTimeoutError(f"Request timed out after {self.max_retries} attempts") from e

            except (JobNotFoundError, ClusterNotFoundError, BudClusterValidationError):
                # Don't retry on these errors
                raise

            except Exception as e:
                # Don't retry on gRPC NOT_FOUND errors
                import grpc

                if isinstance(e, grpc.RpcError) and e.code() == grpc.StatusCode.NOT_FOUND:
                    raise BudClusterConnectionError(f"Service returned NOT_FOUND: {e}") from e

                last_error = e
                logger.warning(f"Error on attempt {attempt + 1}/{self.max_retries}: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                else:
                    raise BudClusterConnectionError(f"Failed to connect after {self.max_retries} attempts: {e}") from e

        raise BudClusterConnectionError(f"Unexpected error: {last_error}")

    async def create_job(self, request: JobCreateRequest) -> JobResponse:
        """Create a new job in BudCluster.

        Args:
            request: Job creation request.

        Returns:
            Created job response.
        """
        data = request.model_dump(by_alias=True, mode="json")
        response = await self._invoke_method(
            method_name="jobs",
            http_verb="POST",
            data=data,
        )
        return JobResponse.model_validate(response)

    async def get_job(self, job_id: UUID) -> JobResponse:
        """Get a job by ID.

        Args:
            job_id: Job UUID.

        Returns:
            Job response.

        Raises:
            JobNotFoundError: If job not found.
        """
        response = await self._invoke_method(
            method_name=f"jobs/{job_id}",
            http_verb="GET",
        )
        return JobResponse.model_validate(response)

    async def list_jobs(
        self,
        source: str | None = None,
        source_id: str | None = None,
        status: str | None = None,
        cluster_id: UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> JobListResponse:
        """List jobs with optional filtering.

        Args:
            source: Filter by source.
            source_id: Filter by source ID.
            status: Filter by status.
            cluster_id: Filter by cluster ID.
            page: Page number.
            page_size: Items per page.

        Returns:
            Paginated list of jobs.
        """
        # Build query parameters
        params = []
        if source:
            params.append(f"source={source}")
        if source_id:
            params.append(f"source_id={source_id}")
        if status:
            params.append(f"status={status}")
        if cluster_id:
            params.append(f"cluster_id={cluster_id}")
        params.append(f"page={page}")
        params.append(f"page_size={page_size}")

        query = "&".join(params)
        method_name = f"jobs?{query}" if params else "jobs"

        response = await self._invoke_method(
            method_name=method_name,
            http_verb="GET",
        )
        return JobListResponse.model_validate(response)

    async def update_job_status(self, job_id: UUID, request: JobStatusUpdateRequest) -> JobResponse:
        """Update a job's status.

        Args:
            job_id: Job UUID.
            request: Status update request.

        Returns:
            Updated job response.
        """
        data = request.model_dump(mode="json")
        response = await self._invoke_method(
            method_name=f"jobs/{job_id}/status",
            http_verb="PUT",
            data=data,
        )
        return JobResponse.model_validate(response)

    async def cancel_job(self, job_id: UUID) -> JobResponse:
        """Cancel a job.

        Args:
            job_id: Job UUID.

        Returns:
            Cancelled job response.
        """
        response = await self._invoke_method(
            method_name=f"jobs/{job_id}/cancel",
            http_verb="POST",
        )
        return JobResponse.model_validate(response)

    async def get_cluster_info(self, cluster_id: UUID) -> ClusterInfoResponse:
        """Get cluster information.

        Args:
            cluster_id: Cluster UUID.

        Returns:
            Cluster information response.

        Raises:
            ClusterNotFoundError: If cluster not found.
        """
        response = await self._invoke_method(
            method_name=f"clusters/{cluster_id}",
            http_verb="GET",
        )
        return ClusterInfoResponse.model_validate(response)

    async def list_available_clusters(
        self,
        provider: str | None = None,
        region: str | None = None,
        gpu_required: bool = False,
    ) -> list[ClusterInfoResponse]:
        """List available clusters for deployment.

        Args:
            provider: Filter by cloud provider.
            region: Filter by region.
            gpu_required: Filter for clusters with GPU.

        Returns:
            List of available clusters.
        """
        params = ["status=active"]
        if provider:
            params.append(f"provider={provider}")
        if region:
            params.append(f"region={region}")
        if gpu_required:
            params.append("gpu_available=true")

        query = "&".join(params)
        method_name = f"clusters?{query}"

        response = await self._invoke_method(
            method_name=method_name,
            http_verb="GET",
        )

        items = response.get("items", [])
        return [ClusterInfoResponse.model_validate(item) for item in items]

    async def delete_namespace(self, cluster_id: UUID, namespace: str) -> dict:
        """Delete a namespace on a cluster.

        Args:
            cluster_id: Cluster UUID.
            namespace: Kubernetes namespace to delete.

        Returns:
            Response dict.
        """
        response = await self._invoke_method(
            method_name=f"cluster/{cluster_id}/delete-namespace",
            http_verb="POST",
            data={"namespace": namespace},
        )
        return response

    async def create_httproute(
        self,
        cluster_id: UUID,
        deployment_id: str,
        namespace: str,
        service_name: str,
        access_config: dict,
    ) -> dict:
        """Create HTTPRoute and ReferenceGrant on a target cluster.

        Calls the budcluster ``POST /cluster/{cluster_id}/httproute`` endpoint
        to create Kubernetes Gateway API resources for routing traffic through
        the Envoy Gateway to the deployed use case service.

        Args:
            cluster_id: Cluster UUID.
            deployment_id: Use case deployment ID.
            namespace: Kubernetes namespace where the service is deployed.
            service_name: Name of the Kubernetes Service to route traffic to.
            access_config: Access mode configuration dict with ``ui`` and ``api``
                sub-dicts containing enabled, port, path/base_path settings.

        Returns:
            Response dict containing ``gateway_endpoint`` and ``status``.
        """
        data = {
            "deployment_id": deployment_id,
            "namespace": namespace,
            "service_name": service_name,
            "access_config": access_config,
        }
        response = await self._invoke_method(
            method_name=f"cluster/{cluster_id}/httproute",
            http_verb="POST",
            data=data,
        )
        return response

    async def delete_httproute(
        self,
        cluster_id: UUID,
        deployment_id: str,
        namespace: str,
    ) -> dict:
        """Delete HTTPRoute and ReferenceGrant from a target cluster.

        Calls the budcluster ``DELETE /cluster/{cluster_id}/httproute/{deployment_id}``
        endpoint to remove Kubernetes Gateway API resources that were created for
        routing traffic to the use case service.

        Args:
            cluster_id: Cluster UUID.
            deployment_id: Use case deployment ID.
            namespace: Kubernetes namespace where the service was deployed.

        Returns:
            Response dict.
        """
        response = await self._invoke_method(
            method_name=f"cluster/{cluster_id}/httproute/{deployment_id}?namespace={namespace}",
            http_verb="DELETE",
        )
        return response

    async def check_cluster_capacity(
        self,
        cluster_id: UUID,
        required_cpu: int,
        required_memory: str,
        required_gpu: int = 0,
    ) -> ClusterCapacityResponse:
        """Check if a cluster has capacity for deployment.

        Args:
            cluster_id: Cluster UUID.
            required_cpu: Required CPU cores.
            required_memory: Required memory (e.g., "16Gi").
            required_gpu: Required GPU count.

        Returns:
            Capacity check response.
        """
        data = {
            "required_cpu": required_cpu,
            "required_memory": required_memory,
            "required_gpu": required_gpu,
        }
        response = await self._invoke_method(
            method_name=f"clusters/{cluster_id}/capacity",
            http_verb="POST",
            data=data,
        )
        return ClusterCapacityResponse.model_validate(response)
