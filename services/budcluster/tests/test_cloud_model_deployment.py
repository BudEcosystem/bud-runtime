import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from budcluster.deployment.handler import DeploymentHandler
from budcluster.commons.constants import ClusterPlatformEnum

def test_cloud_model_deploy(config):
    node_list = [
        {
            "name": "dev-server",
            "devices": [
                {
                    "name": "devserver",
                    "replica": 1,
                    "memory": 512,
                    "num_cpus": 1,
                    "image": "ghcr.io/berriai/litellm:main-latest",
                    "concurrency": 10
                }
            ]
        }
    ]
    deployment_handler = DeploymentHandler(config)
    status, namespace, deployment_url, number_of_nodes, node_list = deployment_handler.cloud_model_deploy(
        node_list,
        "chat",
        "openai/gpt-4-0125-preview",
        "22d4bb50-d574-4cb1-8b09-0b00138b2bcc",
        "http://20.244.107.114:13025/",
        platform=ClusterPlatformEnum.KUBERNETES,
        namespace="bud-chat-d2c2390a"
    )
    print(status)
    print(namespace)
    print(deployment_url)
    print(number_of_nodes)


def test_local_model_deploy_with_tokens(config):
    """Test local model deployment with dynamic token configuration."""
    node_list = [
        {
            "name": "test-server",
            "devices": [
                {
                    "name": "testserver",
                    "replica": 1,
                    "memory": 32768,
                    "type": "cuda",
                    "tp_size": 1,
                    "concurrency": 10,
                    "image": "vllm/vllm-openai:latest",
                    "args": {
                        "model": "meta-llama/Llama-2-7b-chat-hf",
                        "port": 8000
                    },
                    "envs": {}
                }
            ]
        }
    ]
    deployment_handler = DeploymentHandler(config)

    # Test with specific token values
    # This should result in max-model-len = (4096 + 2048) * 1.1 = 6758
    status, namespace, deployment_url, number_of_nodes, node_list = deployment_handler.deploy(
        node_list,
        endpoint_name="llama-chat",
        hf_token="test-token",
        ingress_url="http://20.244.107.114:13025/",
        platform=ClusterPlatformEnum.KUBERNETES,
        input_tokens=4096,
        output_tokens=2048
    )
    print(f"Status: {status}")
    print(f"Namespace: {namespace}")
    print(f"Deployment URL: {deployment_url}")
    print(f"Number of nodes: {number_of_nodes}")
    print(f"Max model len should be 6758 for 4096+2048 tokens")



if __name__ == "__main__":
    import yaml
    config_filepath = "test_cluster_config.yaml"
    with open(config_filepath, "r") as f:
        config = yaml.safe_load(f)
    test_cloud_model_deploy(config)
