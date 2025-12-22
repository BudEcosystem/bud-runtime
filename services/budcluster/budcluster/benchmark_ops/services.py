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

"""Implements core services and business logic that power the microservices, including key functionality and integrations."""

from uuid import UUID

from budmicroframe.commons.logging import get_logger
from fastapi import HTTPException, status
from pydantic import ValidationError

from ..commons.base_crud import SessionMixin
from ..deployment.schemas import DeploymentCreateRequest, LocalDeploymentCreateRequest
from .models import BenchmarkCRUD
from .schemas import RunBenchmarkRequest


logger = get_logger(__name__)


class BenchmarkService(SessionMixin):
    async def create_benchmark(self, request: RunBenchmarkRequest):  # noqa: B008
        """Create a benchmark workflow."""
        deployment = DeploymentCreateRequest(
            nodes=request.nodes,
            datasets=request.datasets,
            is_performance_benchmark=request.user_confirmation,
            user_id=request.user_id,
            model_id=request.model_id,
            cluster_id=request.bud_cluster_id,
            benchmark_id=request.benchmark_id,
            model=request.model,
            endpoint_name="benchmark-" + request.name,
            concurrency=request.concurrent_requests,
            input_tokens=request.max_input_tokens,
            output_tokens=request.max_output_tokens,
            notification_metadata=request.notification_metadata,
            source_topic=request.source_topic,
            # Storage configuration
            default_storage_class=request.default_storage_class,
            default_access_mode=request.default_access_mode,
            storage_size_gb=request.storage_size_gb,
            # Benchmark configuration options from step 6
            hardware_mode=request.hardware_mode,
            selected_device_type=request.selected_device_type,
            tp_size=request.tp_size,
            pp_size=request.pp_size,
            replicas=request.replicas,
            num_prompts=request.num_prompts,
        )

        if request.credential_id:
            deployment.credential_id = request.credential_id

        from ..deployment.workflows import CreateDeploymentWorkflow, CreateCloudDeploymentWorkflow  # noqa: I001

        try:
            # identify whether the deployment request is for local model or cloud model
            LocalDeploymentCreateRequest.model_validate(deployment.model_dump(mode="json", exclude_none=True))
            response = await CreateDeploymentWorkflow().__call__(deployment)
        except ValidationError:
            response = await CreateCloudDeploymentWorkflow().__call__(deployment)

        return response

    async def get_benchmark_result(self, benchmark_id: UUID) -> dict:
        """Get benchmark result."""
        with BenchmarkCRUD() as crud:  # noqa: SIM117
            with crud.get_session() as session:
                db_benchmark = crud.fetch_one(conditions={"id": benchmark_id}, session=session, raise_on_error=False)

                if not db_benchmark:
                    raise HTTPException(
                        detail=f"Benchmark not found: {benchmark_id}", status_code=status.HTTP_404_NOT_FOUND
                    )
                benchmark_result_dict = db_benchmark.result.__dict__
                benchmark_result_dict.pop("_sa_instance_state")
                return benchmark_result_dict
