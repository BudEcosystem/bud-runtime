"""This is the budcluster.playbooks package."""

import os


_PLAYBOOK_MAP = {
    # Setup cluster with NFD, GPU operators, and Aibrix components
    "SETUP_CLUSTER": "setup_cluster.yaml",
    "DEPLOY_NFD": "setup_cluster.yaml",  # Backward compatibility
    "NODE_INFO_COLLECTOR": "setup_cluster.yaml",  # Backward compatibility
    "GET_NODE_INFO": "get_node_info.yaml",
    "GET_NODE_STATUS": "get_node_status.yaml",
    "DEPLOY_RUNTIME": "deploy_runtime.yaml",
    "UPDATE_AUTOSCALE": "update_autoscale.yaml",
    "DELETE_NAMESPACE": "delete_namespace.yaml",
    "GET_DEPLOYMENT_STATUS": "get_deployment_status.yaml",
    "MODEL_TRANSFER": "model_transfer_playbook.yml",
    "GET_MODEL_TRANSFER_STATUS": "get_model_transfer_status.yaml",
    "IDENTIFY_PLATFORM": "identify_platform.yaml",
    "APPLY_SECURITY_CONTEXT": "apply_security_context.yaml",
    "DELETE_CLUSTER": "delete_cluster.yaml",
    "DELETE_POD": "delete_pod.yaml",
    "GET_POD_STATUS": "get_worker_status.yaml",
    "DEPLOY_QUANTIZATION_JOB": "deploy_quantization_job.yaml",
    "GET_QUANTIZATION_STATUS": "get_quantization_status.yaml",
}


def get_playbook_path(key: str) -> str:
    """Retrieve the file path of the playbook associated with the given key.

    Args:
        key (str): The key for the desired playbook.

    Returns:
        str: The file path of the playbook.

    Raises:
        KeyError: If the key is not found in the playbook map.
    """
    if key not in _PLAYBOOK_MAP:
        raise KeyError(f"No playbook found for key: {key}")
    return f"{os.path.dirname(os.path.abspath(__file__))}/{_PLAYBOOK_MAP[key]}"
