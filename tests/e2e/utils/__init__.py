"""E2E test utilities."""

import os
import logging
from pathlib import Path
from kubernetes import client, config
from typing import Tuple, Optional

# Import from submodules
from .k8s_utils import (
    get_pod_status,
    wait_for_deployment_ready,
    scale_deployment,
    get_pod_logs,
    port_forward,
    exec_in_pod,
    wait_for_pod_ready
)

from .inference_utils import (
    make_inference_request,
    batch_inference,
    measure_latency,
    validate_response,
    generate_test_prompt
)

from .monitoring_utils import (
    query_prometheus,
    get_metric_value,
    wait_for_metric,
    collect_metrics,
    generate_report
)


def setup_logging(log_file: Optional[str] = None, level: str = "INFO") -> logging.Logger:
    """Setup logging configuration."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Create logger
    logger = logging.getLogger("e2e_tests")
    logger.setLevel(log_level)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    return logger


def get_kubernetes_clients() -> Tuple[client.CoreV1Api, client.CoreV1Api]:
    """Get Kubernetes clients for app and inference clusters."""
    # Try to load kube config
    try:
        config.load_incluster_config()
    except:
        try:
            config.load_kube_config()
        except:
            # Return mock clients if no k8s available
            return None, None
    
    # Get contexts from environment or use defaults
    app_context = os.environ.get("K8S_APP_CONTEXT", "default")
    inference_context = os.environ.get("K8S_INFERENCE_CONTEXT", "default")
    
    # Create clients
    app_client = client.CoreV1Api()
    inference_client = client.CoreV1Api()
    
    return app_client, inference_client


__all__ = [
    # Setup utilities
    "setup_logging",
    "get_kubernetes_clients",
    
    # K8s utilities
    "get_pod_status",
    "wait_for_deployment_ready",
    "scale_deployment",
    "get_pod_logs",
    "port_forward",
    "exec_in_pod",
    "wait_for_pod_ready",
    
    # Inference utilities
    "make_inference_request",
    "batch_inference",
    "measure_latency",
    "validate_response",
    "generate_test_prompt",
    
    # Monitoring utilities
    "query_prometheus",
    "get_metric_value",
    "wait_for_metric",
    "collect_metrics",
    "generate_report"
]