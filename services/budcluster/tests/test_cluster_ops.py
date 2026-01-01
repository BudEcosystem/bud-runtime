import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Optional
from budcluster.cluster_ops.kubernetes import KubernetesHandler

def test_verify_cluster_connection(config: dict):
    kubernetes_cluster_handler = KubernetesHandler(config)
    status = kubernetes_cluster_handler.verify_cluster_connection()
    print(status)
    return status

def test_deploy_node_info_collector(config: dict):
    kubernetes_cluster_handler = KubernetesHandler(config)
    status = kubernetes_cluster_handler.initial_setup()
    print(status)
    return status

def test_get_node_info(config: dict):
    kubernetes_cluster_handler = KubernetesHandler(config)
    node_info = kubernetes_cluster_handler.get_node_info()
    print(node_info)

def test_get_node_status(config: dict):
    kubernetes_cluster_handler = KubernetesHandler(config)
    node_info = kubernetes_cluster_handler.get_node_status()
    print(node_info)

def test_get_deployment_status(config: dict, namespace: str, ingress_url: Optional[str] = None):
    kubernetes_cluster_handler = KubernetesHandler(config, ingress_url)
    status = kubernetes_cluster_handler.get_deployment_status({"namespace": namespace})
    print(status)

def test_get_pod_status(config: dict, namespace: str, pod_name: str):
    kubernetes_cluster_handler = KubernetesHandler(config)
    worker_data = kubernetes_cluster_handler.get_pod_status(namespace, pod_name)
    print(worker_data)

if __name__ == "__main__":
    import yaml
    # config_filepath = "dev_cluster_17.yaml"
    # config_filepath = "dev-server-20.yaml"
    # config_filepath = "k3s_1.yaml"
    # config_filepath = "remote_cluster_17.yaml"
    config_filepath = "test_cluster_config.yaml"
    with open(config_filepath, "r") as f:
        config = yaml.safe_load(f)
    ingress_url = "http://20.244.107.114:13025/"
    # print(status)
    # test_verify_cluster_connection(config)
    # test_deploy_node_info_collector(config)
    # import time
    # time.sleep(10)
    # test_get_node_info(config)
    # node_status = test_get_node_status(config)
    # print(node_status)
    namespace = "bud-shef-49db673e"
    # test_get_deployment_status(config, namespace, ingress_url)
    pod_name = "bud-runtime-container-77894d8586-7vz9v"
    test_get_pod_status(config, namespace, pod_name)
