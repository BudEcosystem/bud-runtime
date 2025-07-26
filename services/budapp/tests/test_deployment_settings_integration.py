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

"""Integration tests for deployment settings functionality."""

import pytest

from budapp.endpoint_ops.schemas import (
    DeploymentSettingsConfig,
    FallbackConfig,
    RateLimitConfig,
    RetryConfig,
    UpdateDeploymentSettingsRequest,
)


@pytest.mark.asyncio
async def test_deployment_settings_schemas_integration():
    """Test that deployment settings schemas work together correctly."""
    # Test creating a full deployment settings config
    config = DeploymentSettingsConfig(
        rate_limits=RateLimitConfig(
            algorithm="token_bucket",
            requests_per_second=10,
            requests_per_minute=600,
            burst_size=20,
            enabled=True,
        ),
        retry_config=RetryConfig(
            num_retries=3,
            max_delay_s=5.0,
        ),
        fallback_config=FallbackConfig(
            fallback_models=["model1", "model2"],
        ),
    )

    # Verify serialization
    data = config.model_dump()
    assert data["rate_limits"]["algorithm"] == "token_bucket"
    assert data["retry_config"]["num_retries"] == 3
    assert data["fallback_config"]["fallback_models"] == ["model1", "model2"]

    # Verify deserialization
    config2 = DeploymentSettingsConfig(**data)
    assert config2.rate_limits.requests_per_second == 10
    assert config2.retry_config.max_delay_s == 5.0
    assert len(config2.fallback_config.fallback_models) == 2


@pytest.mark.asyncio
async def test_update_request_partial_updates():
    """Test that update requests handle partial updates correctly."""
    # Test with only rate limits
    request = UpdateDeploymentSettingsRequest(
        rate_limits=RateLimitConfig(requests_per_second=20)
    )
    data = request.model_dump(exclude_none=True)
    assert "rate_limits" in data
    assert "retry_config" not in data
    assert "fallback_config" not in data

    # Test with multiple fields
    request = UpdateDeploymentSettingsRequest(
        retry_config=RetryConfig(num_retries=5),
        fallback_config=FallbackConfig(fallback_models=["backup"]),
    )
    data = request.model_dump(exclude_none=True)
    assert "rate_limits" not in data
    assert data["retry_config"]["num_retries"] == 5
    assert data["fallback_config"]["fallback_models"] == ["backup"]
