import sys
import os
import pytest
from unittest.mock import Mock, patch
from uuid import UUID
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock the config first, before any other imports
@pytest.fixture(autouse=True)
def mock_config(monkeypatch):
    # Set environment variables before any imports
    monkeypatch.setenv("JWT_SECRET_KEY", "test_jwt_secret")
    monkeypatch.setenv("REDIS_PASSWORD", "test_redis_password")
    monkeypatch.setenv("REDIS_URI", "redis://localhost:6379")
    
    mock_settings = Mock()
    # Add any required attributes that your code might access
    mock_settings.POSTGRES_USER = "test_user"
    mock_settings.POSTGRES_PASSWORD = "test_password"
    mock_settings.POSTGRES_DB = "test_db"
    mock_settings.SUPER_USER_EMAIL = "test@example.com"
    mock_settings.SUPER_USER_PASSWORD = "test_password"
    mock_settings.DAPR_BASE_URL = "http://localhost:3500"
    mock_settings.BUD_CLUSTER_APP_ID = "cluster-app"
    mock_settings.BUD_MODEL_APP_ID = "model-app"
    mock_settings.BUD_SIMULATOR_APP_ID = "simulator-app"
    mock_settings.BUD_METRICS_APP_ID = "metrics-app"
    mock_settings.BUD_NOTIFY_APP_ID = "notify-app"
    
    # Add required secret values
    mock_settings.JWT_SECRET_KEY = "test_jwt_secret"
    mock_settings.REDIS_PASSWORD = "test_redis_password"
    mock_settings.REDIS_URI = "redis://localhost:6379"
    
    with patch('budapp.commons.config.app_settings', mock_settings):
        yield mock_settings

@pytest.fixture
def mock_logger():
    with patch('budapp.commons.logging.get_logger') as mock_get_logger:
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        yield mock_logger

@pytest.fixture
def metrics_fetcher(mock_logger, mock_config):
    with patch('budapp.commons.logging', return_value=mock_logger):
        from budapp.cluster_ops.utils import ClusterMetricsFetcher
        return ClusterMetricsFetcher(prometheus_url="http://135.233.178.158:9090")

@pytest.mark.asyncio 
async def test_get_cluster_metrics(metrics_fetcher, mock_logger):
    # Test with empty cluster ID
    result = await metrics_fetcher.get_cluster_metrics(cluster_id="", time_range="today", metric_type="all")
    
    import json
    print("\nCluster Metrics Result:")
    print(json.dumps(result, indent=4, sort_keys=True))
    # Save metrics to JSON file
    if result:
        try:
            with open('cluster_metrics.json', 'w') as f:
                json.dump(result, f, indent=4, sort_keys=True)
            print("\nMetrics saved to cluster_metrics.json")
        except Exception as e:
            print(f"\nError saving metrics to JSON: {e}")
    
    
    # assert result is None
    # mock_logger.error.assert_called_with("Cluster ID is required to fetch cluster metrics")

    # # Test with valid cluster ID
    # result = await metrics_fetcher.get_cluster_metrics(
    #     cluster_id=UUID("11111111-1111-1111-1111-111111111111"),  # Use a valid UUID
    #     time_range="today",
    #     metric_type="all"
    # )
    # assert isinstance(result, dict)
    # assert "nodes" in result
    # assert "cluster_summary" in result
    # assert "timestamp" in result