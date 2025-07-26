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



if __name__ == "__main__":
    import yaml
    config_filepath = "test_cluster_config.yaml"
    with open(config_filepath, "r") as f:
        config = yaml.safe_load(f)
    test_cloud_model_deploy(config)
