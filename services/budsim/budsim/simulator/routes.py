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

from .schemas import (
    BenchmarkConfigRequest,
    ClusterRecommendationRequest,
    DeploymentConfigurationRequest,
    NodeConfigurationRequest,
)
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


@simulator_router.post("/node-configurations", tags=["Configurations"])
async def get_node_configurations(
    request: NodeConfigurationRequest,
) -> Response:
    """Get valid TP/PP configuration options for selected nodes.

    This endpoint analyzes the selected nodes and returns:
    - Available device types on the nodes
    - Valid TP/PP combinations per device type
    - Maximum replicas for each configuration
    - Model memory requirements

    Args:
        request: NodeConfigurationRequest containing cluster_id, model_id,
                hostnames, hardware_mode, and token configuration.

    Returns:
        NodeConfigurationResponse with device configurations and model info.
    """
    try:
        response = SimulationService.get_node_configurations(request)
        return response.to_http_response()
    except ValueError as e:
        logger.exception(f"Validation error in node configurations: {e}")
        return ErrorResponse(message=str(e), code=400).to_http_response()
    except Exception as e:
        logger.exception(f"Error getting node configurations: {e}")
        return ErrorResponse(message="Failed to get node configurations", code=500).to_http_response()


@simulator_router.post("/benchmark-config", tags=["Configurations"])
async def get_benchmark_configuration(
    request: BenchmarkConfigRequest,
) -> Response:
    """Generate deployment configuration for benchmark with user-selected parameters.

    Unlike /configurations which fetches from saved simulation results,
    this endpoint generates config directly from user selections. It creates
    a full NodeGroupConfiguration suitable for deployment handler.

    Args:
        request: BenchmarkConfigRequest containing cluster_id, model_id, model_uri,
                hostnames, device_type, tp_size, pp_size, replicas, and token configuration.

    Returns:
        BenchmarkConfigResponse with node_groups array containing full deployment configs.
    """
    try:
        response = SimulationService.generate_benchmark_config(request)
        return response.to_http_response()
    except ValueError as e:
        logger.exception(f"Validation error in benchmark config: {e}")
        return ErrorResponse(message=str(e), code=400).to_http_response()
    except Exception as e:
        logger.exception(f"Error generating benchmark config: {e}")
        return ErrorResponse(message="Failed to generate benchmark configuration", code=500).to_http_response()
