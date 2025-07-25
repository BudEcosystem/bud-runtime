import os
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch
from typing import Dict, Any
import aiohttp

# Set up all required environment variables before importing any application code
os.environ.update({
    # AppConfig variables
    "POSTGRES_USER": "test_user",
    "POSTGRES_PASSWORD": "test_password",
    "POSTGRES_DB": "test_db",
    "SUPER_USER_EMAIL": "test@example.com",
    "SUPER_USER_PASSWORD": "test_password",
    "DAPR_BASE_URL": "http://localhost:3500",
    "BUD_CLUSTER_APP_ID": "test_cluster_app",
    "BUD_MODEL_APP_ID": "test_model_app",
    "BUD_SIMULATOR_APP_ID": "test_simulator_app",
    "BUD_METRICS_APP_ID": "test_metrics_app",
    "BUD_NOTIFY_APP_ID": "test_notify_app",
    "APP_PORT": "8000",

    # SecretsConfig variables
    "JWT_SECRET_KEY": "test_jwt_secret_key",
    "REDIS_PASSWORD": "test_redis_password",
    "REDIS_URI": "redis://localhost:6379"
})

# Import application code after environment setup
from budapp.credential_ops.schemas import CredentialVerifyPayload, CredentialVerifyRequest
from budapp.shared.dapr_service import DaprService
from budapp.shared.redis_service import RedisService
from budapp.commons.db_utils import Session


async def add_verify_endpoint(payload: Dict[str, Any]):
    """Helper function to call the verify endpoint"""
    endpoint = f"http://localhost:{os.getenv('APP_PORT')}/credentials/verify"
    async with aiohttp.ClientSession() as session, session.post(endpoint, json=payload) as response:
        return await response.json()


@pytest.mark.asyncio
async def test_verify_credential():
    # Create mock objects
    mock_dapr_service = AsyncMock(spec=DaprService)
    mock_redis_service = AsyncMock(spec=RedisService)
    mock_session = AsyncMock(spec=Session)

    # Patch the services with our mocks
    with patch("budapp.credential_ops.services.DaprService", return_value=mock_dapr_service), \
         patch("budapp.credential_ops.services.RedisService", return_value=mock_redis_service), \
         patch("budapp.credential_ops.services.Session", return_value=mock_session):

        # Create test payload for verification
        payload = CredentialVerifyPayload(
            hashed_key="cb742dc90b3c735da84104d09715fde454e12bff5f6c7336c1e655628fe9d957",
            verification_token="test_verification_token"
        )
        data = CredentialVerifyRequest(payload=payload).model_dump(mode="json")

        # Call the verify endpoint
        response = await add_verify_endpoint(data)

        # Verify the interactions with the mocks
        mock_dapr_service.publish_to_topic.assert_called_once()
        mock_redis_service.get.assert_called_once()  # Changed from set to get for verification
        mock_session.query.assert_called_once()  # Changed from commit to query for verification

        # Additional assertions for verification endpoint
        assert response is not None
        assert "verification_status" in response
        assert response["verification_status"] in ["success", "failed"]


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_verify_credential())
