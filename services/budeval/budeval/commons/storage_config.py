"""Storage configuration for different environments."""

import os
from typing import Any, Dict


class StorageConfig:
    """Storage configuration based on environment."""

    @staticmethod
    def get_environment() -> str:
        """Detect the current environment."""
        # Check for local development indicators
        if os.path.exists("/home/ubuntu/bud-serve-eval/k3s.yaml"):
            return "local"

        # Check for environment variable
        env = os.environ.get("BUDEVAL_ENV", "production").lower()
        return env

    @staticmethod
    def get_current_namespace() -> str:
        """Get the current Kubernetes namespace where the app is running.

        Returns:
            The namespace where the app is running (always lowercase)
        """
        # First try environment variable
        namespace = os.environ.get("NAMESPACE")
        if namespace:
            namespace = namespace.lower()  # Kubernetes namespaces must be lowercase
            return namespace

        # Try reading from serviceaccount if running in cluster
        namespace_file = "/var/run/secrets/kubernetes.io/serviceaccount/namespace"
        if os.path.exists(namespace_file):
            with open(namespace_file, "r") as f:
                namespace = f.read().strip().lower()  # Ensure lowercase
                return namespace

        # Default fallback
        return "default"

    @staticmethod
    def get_eval_datasets_pvc_name() -> str:
        """Get the PVC name for eval datasets.

        Returns:
            The PVC name to use for eval datasets
        """
        return os.environ.get("EVAL_DATASETS_PATH", "panda-budeval-dataset")

    @staticmethod
    def get_storage_config() -> Dict[str, Any]:
        """Get storage configuration for current environment."""
        env = StorageConfig.get_environment()
        namespace = StorageConfig.get_current_namespace()
        pvc_name = StorageConfig.get_eval_datasets_pvc_name()

        configs = {
            "local": {
                "eval_datasets": {
                    "pvc_name": pvc_name,
                    "namespace": namespace,
                    "access_mode": "ReadWriteOnce",  # local-path doesn't support RWX
                    "size": "10Gi",
                    "storage_class": "local-path",  # Use default (local-path)
                },
                "job_volumes": {
                    "namespace": namespace,
                    "access_mode": "ReadWriteOnce",
                    "data_size": "5Gi",
                    "output_size": "5Gi",
                    "storage_class": "local-path",
                },
            },
            "production": {
                "eval_datasets": {
                    "pvc_name": pvc_name,
                    "namespace": namespace,
                    "access_mode": "ReadWriteMany",  # For shared access
                    "size": "100Gi",
                    "storage_class": "",  # Use cluster default
                },
                "job_volumes": {
                    "namespace": namespace,
                    "access_mode": "ReadWriteOnce",
                    "data_size": "20Gi",
                    "output_size": "20Gi",
                    "storage_class": "",
                },
            },
        }

        config = configs.get(env, configs["production"])
        config["environment"] = env
        config["namespace"] = namespace
        return config

    @staticmethod
    def get_eval_datasets_config() -> Dict[str, Any]:
        """Get configuration for eval-datasets volume."""
        config = StorageConfig.get_storage_config()
        return config["eval_datasets"]

    @staticmethod
    def get_job_volumes_config() -> Dict[str, Any]:
        """Get configuration for job-specific volumes."""
        config = StorageConfig.get_storage_config()
        return config["job_volumes"]
