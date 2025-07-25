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

import uuid
from typing import Optional, Union

from budmicroframe.commons import logging
from budmicroframe.commons.api_utils import pubsub_api_endpoint
from budmicroframe.commons.schemas import ErrorResponse, SuccessResponse
from fastapi import APIRouter, Response

from .schemas import ClusterRecommendationRequest, DeploymentConfigurationRequest
from .services import SimulationService
from .workflows import SimulationWorkflows


logger = logging.get_logger(__name__)

simulator_router = APIRouter(prefix="/simulator")


@simulator_router.post("/run", tags=["Recommendations"])
@pubsub_api_endpoint(request_model=ClusterRecommendationRequest)
async def run_simulation(request: ClusterRecommendationRequest) -> Response:
    """Run a simulation based on the provided configuration.

    This endpoint processes the deployment configuration and returns
    recommendations for deployment strategies based on the specified
    parameters.

    Args:
        request (DeploymentRecommendationRequest): The deployment
        configuration containing model URI, input/output tokens, concurrency,
        and target performance metrics.

    Returns:
        HTTP response containing the deployment recommendations.
    """
    response: Union[SuccessResponse, ErrorResponse]
    if request.debug:
        try:
            logger.info("Running simulation in debug mode", request.model_dump())
            response = SimulationService().__call__(request, workflow_id=str(uuid.uuid4()))
        except Exception as e:
            logger.exception("Error running simulation: %s", str(e))
            response = ErrorResponse(message="Error running simulation", code=500)
    else:
        response = await SimulationWorkflows().__call__(request)

    return response.to_http_response()


@simulator_router.get("/recommendations", tags=["Recommendations"])
async def get_cluster_recommendations(
    workflow_id: uuid.UUID,
    cluster_id: Optional[str] = None,
    concurrency: Optional[int] = None,
    error_rate_threshold: float = 0.5,
    page: int = 1,
    limit: int = 1,
) -> Response:
    """Get deployment configurations based on the provided configuration."""
    response = SimulationService().get_topk_cluster_recommendations(
        workflow_id, cluster_id, concurrency, error_rate_threshold, page, limit
    )
    return response.to_http_response()


@simulator_router.post("/configurations", tags=["Recommendations"])
async def get_deployment_configurations(
    request: DeploymentConfigurationRequest,
) -> Response:
    """Get deployment configurations based on the provided configuration."""
    response = SimulationService().get_deployment_configs(request)
    return response.to_http_response()
