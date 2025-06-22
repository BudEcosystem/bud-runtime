"""Global pytest configuration and fixtures."""

import os
import sys
import json
import time
import yaml
import pytest
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

import kubernetes
from kubernetes import client, config
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Test configuration
class TestConfig:
    """Test configuration singleton."""
    
    def __init__(self):
        self.app_cluster = os.getenv("APP_CLUSTER_NAME", "bud-app")
        self.inference_cluster = os.getenv("INFERENCE_CLUSTER_NAME", "bud-inference")
        self.app_namespace = os.getenv("APP_NAMESPACE", "bud-system")
        self.inference_namespace = os.getenv("INFERENCE_NAMESPACE", "inference-system")
        
        # Service endpoints
        self.budproxy_endpoint = os.getenv("BUDPROXY_ENDPOINT", "http://localhost:8000")
        self.aibrix_endpoint = os.getenv("AIBRIX_ENDPOINT", "http://localhost:8080")
        self.vllm_endpoint = os.getenv("VLLM_ENDPOINT", "http://localhost:8001")
        
        # Test parameters
        self.default_timeout = int(os.getenv("TEST_TIMEOUT", "300"))
        self.default_model = os.getenv("TEST_MODEL", "test-model")
        self.max_retries = int(os.getenv("TEST_MAX_RETRIES", "3"))
        
        # Load test config file if exists
        config_file = Path(__file__).parent / "e2e" / "config.yaml"
        if config_file.exists():
            with open(config_file) as f:
                config_data = yaml.safe_load(f)
                self.__dict__.update(config_data)


test_config = TestConfig()


# Kubernetes fixtures
@pytest.fixture(scope="session")
def k8s_app_client():
    """Kubernetes client for application cluster."""
    try:
        config.load_kube_config(context=f"k3d-{test_config.app_cluster}")
        return client.CoreV1Api()
    except Exception as e:
        pytest.skip(f"Cannot connect to app cluster: {e}")


@pytest.fixture(scope="session")
def k8s_inference_client():
    """Kubernetes client for inference cluster."""
    try:
        config.load_kube_config(context=f"k3d-{test_config.inference_cluster}")
        return client.CoreV1Api()
    except Exception as e:
        pytest.skip(f"Cannot connect to inference cluster: {e}")


@pytest.fixture(scope="session")
def k8s_clients(k8s_app_client, k8s_inference_client):
    """Both Kubernetes clients."""
    return {
        "app": k8s_app_client,
        "inference": k8s_inference_client
    }


# HTTP client fixtures
@pytest.fixture(scope="session")
def http_session():
    """Shared HTTP session with retries."""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "User-Agent": "bud-runtime-e2e-tests"
    })
    return session


@pytest.fixture
def budproxy_client(http_session):
    """Client for BudProxy API."""
    class BudProxyClient:
        def __init__(self, session, base_url):
            self.session = session
            self.base_url = base_url.rstrip("/")
        
        @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
        def inference(self, model: str, prompt: str, **kwargs) -> Dict[str, Any]:
            """Make inference request."""
            data = {
                "model": model,
                "prompt": prompt,
                "max_tokens": kwargs.get("max_tokens", 50),
                "temperature": kwargs.get("temperature", 0.7)
            }
            
            response = self.session.post(
                f"{self.base_url}/v1/completions",
                json=data,
                timeout=kwargs.get("timeout", 30)
            )
            response.raise_for_status()
            return response.json()
        
        def health(self) -> bool:
            """Check health status."""
            try:
                response = self.session.get(f"{self.base_url}/health", timeout=5)
                return response.status_code == 200
            except:
                return False
    
    return BudProxyClient(http_session, test_config.budproxy_endpoint)


@pytest.fixture
def aibrix_client(http_session):
    """Client for AIBrix API."""
    class AIBrixClient:
        def __init__(self, session, base_url):
            self.session = session
            self.base_url = base_url.rstrip("/")
        
        def list_models(self) -> Dict[str, Any]:
            """List deployed models."""
            response = self.session.get(f"{self.base_url}/v1/models")
            response.raise_for_status()
            return response.json()
        
        def get_model_status(self, model_name: str) -> Dict[str, Any]:
            """Get model deployment status."""
            response = self.session.get(f"{self.base_url}/v1/models/{model_name}")
            response.raise_for_status()
            return response.json()
        
        def scale_model(self, model_name: str, replicas: int) -> Dict[str, Any]:
            """Scale model deployment."""
            response = self.session.patch(
                f"{self.base_url}/v1/models/{model_name}",
                json={"replicas": replicas}
            )
            response.raise_for_status()
            return response.json()
    
    return AIBrixClient(http_session, test_config.aibrix_endpoint)


# Test data fixtures
@pytest.fixture
def test_prompts():
    """Common test prompts."""
    return [
        "Hello, how are you?",
        "What is the capital of France?",
        "Explain quantum computing in simple terms.",
        "Write a Python function to calculate fibonacci numbers.",
        "Translate 'Hello world' to Spanish."
    ]


@pytest.fixture
def test_models():
    """Available test models."""
    return {
        "small": "test-model",
        "llama2": "llama2-7b",
        "mistral": "mistral-7b",
        "primary": "primary-llm"
    }


# Utility fixtures
@pytest.fixture
def wait_for_condition():
    """Wait for a condition to be true."""
    def _wait(condition_func, timeout=60, interval=2, message="condition"):
        """Wait for condition_func to return True."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                if condition_func():
                    return True
            except Exception as e:
                logger.debug(f"Condition check failed: {e}")
            time.sleep(interval)
        
        raise TimeoutError(f"Timeout waiting for {message}")
    
    return _wait


@pytest.fixture
def metrics_collector():
    """Collect metrics during tests."""
    class MetricsCollector:
        def __init__(self):
            self.metrics = []
        
        def record(self, metric_name: str, value: float, labels: Dict[str, str] = None):
            """Record a metric."""
            self.metrics.append({
                "name": metric_name,
                "value": value,
                "labels": labels or {},
                "timestamp": datetime.utcnow().isoformat()
            })
        
        def get_metrics(self, metric_name: str = None) -> list:
            """Get recorded metrics."""
            if metric_name:
                return [m for m in self.metrics if m["name"] == metric_name]
            return self.metrics
        
        def save(self, filepath: str):
            """Save metrics to file."""
            with open(filepath, "w") as f:
                json.dump(self.metrics, f, indent=2)
    
    return MetricsCollector()


# Pytest hooks
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow")
    config.addinivalue_line("markers", "gpu: marks tests that require GPU")
    config.addinivalue_line("markers", "integration: marks integration tests")
    config.addinivalue_line("markers", "smoke: marks smoke tests")
    config.addinivalue_line("markers", "load: marks load tests")
    config.addinivalue_line("markers", "failover: marks failover tests")
    config.addinivalue_line("markers", "requires_model: marks tests requiring specific models")


def pytest_collection_modifyitems(config, items):
    """Modify test collection based on markers."""
    # Skip GPU tests if no GPU available
    if not os.getenv("TEST_GPU_ENABLED", "false").lower() == "true":
        skip_gpu = pytest.mark.skip(reason="GPU tests disabled")
        for item in items:
            if "gpu" in item.keywords:
                item.add_marker(skip_gpu)


@pytest.fixture(scope="session", autouse=True)
def test_environment_info():
    """Log test environment information."""
    logger.info("=" * 60)
    logger.info("Test Environment Information")
    logger.info("=" * 60)
    logger.info(f"App Cluster: {test_config.app_cluster}")
    logger.info(f"Inference Cluster: {test_config.inference_cluster}")
    logger.info(f"BudProxy Endpoint: {test_config.budproxy_endpoint}")
    logger.info(f"AIBrix Endpoint: {test_config.aibrix_endpoint}")
    logger.info(f"Default Model: {test_config.default_model}")
    logger.info("=" * 60)
    yield
    logger.info("Test session completed")