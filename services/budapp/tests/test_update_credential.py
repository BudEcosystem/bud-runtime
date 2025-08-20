import os
import pytest
from datetime import datetime
from unittest.mock import MagicMock
from typing import Dict, Any

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
from budapp.credential_ops.schemas import CredentialUpdatePayload, CredentialUpdateRequest


def test_credential_update_schemas():
    """Test that the credential update schemas can be imported and instantiated correctly."""
    # Test CredentialUpdatePayload
    payload = CredentialUpdatePayload(
        hashed_key="cb742dc90b3c735da84104d09715fde454e12bff5f6c7336c1e655628fe9d957",
        last_used_at=datetime.now()
    )
    assert payload.hashed_key == "cb742dc90b3c735da84104d09715fde454e12bff5f6c7336c1e655628fe9d957"
    assert payload.last_used_at is not None

    # Test CredentialUpdateRequest
    request = CredentialUpdateRequest(payload=payload)
    assert request.payload == payload

    # Test model_dump
    data = request.model_dump(mode="json")
    assert "payload" in data
    assert data["payload"]["hashed_key"] == "cb742dc90b3c735da84104d09715fde454e12bff5f6c7336c1e655628fe9d957"


if __name__ == "__main__":
    test_credential_update_schemas()
    print("All tests passed!")
