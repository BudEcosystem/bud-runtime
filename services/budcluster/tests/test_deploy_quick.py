import os
import sys
from typing import List, Tuple
import yaml
import json

# Ensure required env vars exist before importing the module under test
os.environ.setdefault("ENGINE_CONTAINER_PORT", "8000")
os.environ.setdefault("REGISTRY_SERVER", "ghcr.io")
os.environ.setdefault("REGISTRY_USERNAME", "testuser")
os.environ.setdefault("REGISTRY_PASSWORD", "testpass")
os.environ.setdefault("DAPR_BASE_URL", "http://localhost:3500")
os.environ.setdefault("PROMETHEUS_URL", "http://localhost:9090")


# Make 'budcluster' package importable from services/budcluster/
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from budcluster.deployment.handler import DeploymentHandler  # noqa: E402


def _sample_node_list() -> List[dict]:
    return [
        {
            "name": "test-node",
            "replicas": 1,
            "memory": 24 * 1024**3,  # bytes
            "type": "cuda",
            "tp_size": 1,
            "pp_size": 2,
            "concurrency": 4,
            "image": "budstudio/vllm-cuda:0.4.0",
            "args": {"model": "/data/models-registry/qwen_qwen3-1_7b_2bcbf139"},
            "envs": {},
        }
    ]


def test_deploy_success_quick():
    # Arrange
    with open("gpu-cluster.yaml") as f:
        config = yaml.safe_load(f)

    handler = DeploymentHandler(config)

    async def fake_apply_security_context(cfg, namespace):  # noqa: ARG001
        return True

    async def fake_deploy_runtime(cfg, values, playbook="DEPLOY_RUNTIME", platform=None, delete_on_failure=True):  # noqa: ARG001
        return True, "http://example.local/deployed"

    # Monkeypatch the imported symbols in the handler module
    import budcluster.deployment.handler as handler_module

    # monkeypatch.setattr(handler_module, "apply_security_context", fake_apply_security_context)
    # monkeypatch.setattr(handler_module, "deploy_runtime", fake_deploy_runtime)

    node_list = _sample_node_list()

    # Act
    status, namespace, url, nodes, full_node_list = handler.deploy(
        node_list,
        endpoint_name="llama-chat",
        hf_token="test-token",
        ingress_url="demo.bud.local",
    )

    # Assert
    assert status is True
    assert namespace.startswith("bud-llama-chat-")
    assert url == "http://example.local/deployed"
    assert nodes == 1
    # Verify args were transformed and enriched
    args_list = full_node_list[0]["devices"][0]["args"]
    assert any(a.startswith("--served-model-name=") for a in args_list)
    assert "--enable-lora" in args_list
    # Default max-model-len applied when no tokens provided
    assert "--max-model-len=8192" in args_list


def test_deploy_requires_ingress_url(monkeypatch):
    # Minimal monkeypatch to avoid accidental external calls if reached
    import budcluster.deployment.handler as handler_module

    async def fake_apply_security_context(cfg, namespace):  # noqa: ARG001
        return True

    async def fake_deploy_runtime(cfg, values, playbook="DEPLOY_RUNTIME", platform=None, delete_on_failure=True):  # noqa: ARG001
        return True, "http://example.local/deployed"

    monkeypatch.setattr(handler_module, "apply_security_context", fake_apply_security_context)
    monkeypatch.setattr(handler_module, "deploy_runtime", fake_deploy_runtime)

    handler = DeploymentHandler({})

    # Missing ingress_url should raise
    try:
        handler.deploy(_sample_node_list(), endpoint_name="test-endpoint", ingress_url=None)
        assert False, "Expected ValueError for missing ingress_url"
    except ValueError as e:  # noqa: F841
        pass


test_deploy_success_quick()
