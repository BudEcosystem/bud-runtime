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
    def get_storage_config() -> Dict[str, Any]:
        """Get storage configuration for current environment."""
        env = StorageConfig.get_environment()

        configs = {
            "local": {
                "eval_datasets": {
                    "access_mode": "ReadWriteOnce",  # local-path doesn't support RWX
                    "size": "10Gi",
                    "storage_class": "local-path",  # Use default (local-path)
                },
                "job_volumes": {
                    "access_mode": "ReadWriteOnce",
                    "data_size": "5Gi",
                    "output_size": "5Gi",
                    "storage_class": "local-path",
                },
            },
            "production": {
                "eval_datasets": {
                    "access_mode": "ReadWriteMany",  # For shared access
                    "size": "100Gi",
                    "storage_class": "",  # Use cluster default
                },
                "job_volumes": {
                    "access_mode": "ReadWriteOnce",
                    "data_size": "20Gi",
                    "output_size": "20Gi",
                    "storage_class": "",
                },
            },
        }

        config = configs.get(env, configs["production"])
        config["environment"] = env
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
