"""Volume initialization module for checking required persistent volumes exist."""

import os
import uuid
from typing import Optional

from budeval.commons.logging import logging
from budeval.registry.orchestrator.ansible_orchestrator import AnsibleOrchestrator


logger = logging.getLogger(__name__)


class DatasetVolumeNotFoundError(Exception):
    """Raised when the required dataset PVC is not found."""

    pass


class VolumeInitializer:
    """Handles checking of required persistent volumes."""

    _initialized = False

    def __init__(self):
        """Initialize the volume initializer with an Ansible orchestrator."""
        self.orchestrator = AnsibleOrchestrator()

    @classmethod
    def reset_initialization_state(cls):
        """Reset the initialization state for testing purposes."""
        cls._initialized = False

    @classmethod
    def get_current_namespace(cls) -> str:
        """Get the current Kubernetes namespace.

        Returns:
            The namespace where the app is running (always lowercase)
        """
        # First try environment variable
        namespace = os.environ.get("NAMESPACE")
        if namespace:
            namespace = namespace.lower()  # Kubernetes namespaces must be lowercase
            logger.info(f"Using namespace from NAMESPACE env var: {namespace}")
            return namespace

        # Try reading from serviceaccount if running in cluster
        namespace_file = "/var/run/secrets/kubernetes.io/serviceaccount/namespace"
        if os.path.exists(namespace_file):
            with open(namespace_file, "r") as f:
                namespace = f.read().strip().lower()  # Ensure lowercase
                logger.info(f"Using namespace from serviceaccount: {namespace}")
                return namespace

        # Default fallback
        namespace = "default"
        logger.warning(f"Could not detect namespace, using default: {namespace}")
        return namespace

    async def ensure_eval_datasets_volume(self, kubeconfig: Optional[str] = None):
        """Check that the eval-datasets volume exists and initialize datasets if needed.

        Args:
            kubeconfig: Optional kubernetes config. If not provided, uses in-cluster config.

        Raises:
            DatasetVolumeNotFoundError: If the required PVC does not exist
        """
        # Skip if already initialized
        if VolumeInitializer._initialized:
            logger.debug("Volume check already completed, skipping")
            return

        # Get current namespace
        namespace = self.get_current_namespace()

        # Get PVC name from config or use default
        pvc_name = os.environ.get("EVAL_DATASETS_PATH", "bud-dev-budeval-dataset-rwx")

        # Get dataset URL from environment
        dataset_url = os.environ.get(
            "OPENCOMPASS_DATASET_URL",
            "https://github.com/open-compass/opencompass/releases/download/0.2.2.rc1/OpenCompassData-complete-20240207.zip",
        )

        logger.info(f"Checking for PVC '{pvc_name}' in namespace '{namespace}'")
        logger.info(f"Dataset URL: {dataset_url}")
        logger.info(f"Kubeconfig provided: {kubeconfig is not None}")

        # Check if we should skip volume check (for dev/testing)
        if os.environ.get("SKIP_VOLUME_CHECK", "false").lower() == "true":
            logger.warning("SKIP_VOLUME_CHECK is enabled, skipping PVC existence check")
            VolumeInitializer._initialized = True
            return

        try:
            # Generate a unique ID for this operation
            operation_id = f"volume-check-{uuid.uuid4().hex[:8]}"
            logger.info(f"Volume check operation ID: {operation_id}")

            # Use the ensure_eval_datasets_volume playbook
            playbook = "ensure_eval_datasets_volume.yml"
            logger.info(f"Using playbook: {playbook}")

            # Prepare files and extravars
            files = {}
            extravars = {"namespace": namespace, "pvc_name": pvc_name, "opencompass_dataset_url": dataset_url}

            # Handle kubeconfig same as other methods
            if kubeconfig:
                import json

                import yaml

                logger.info("Using provided kubeconfig")
                kubeconfig_dict = json.loads(kubeconfig)
                kubeconfig_yaml = yaml.safe_dump(kubeconfig_dict, sort_keys=False, default_flow_style=False)
                files[f"{operation_id}_kubeconfig.yaml"] = kubeconfig_yaml
                extravars["kubeconfig_path"] = f"{operation_id}_kubeconfig.yaml"
            else:
                logger.info("No kubeconfig provided, will use in-cluster config or local k3s.yaml")

            # Run the playbook to check PVC and initialize datasets
            logger.info("Checking PVC and initializing datasets if needed")
            self.orchestrator._run_ansible_playbook(playbook, operation_id, files, extravars)

            # The playbook will fail if PVC doesn't exist
            logger.info(f"PVC '{pvc_name}' exists and datasets are ready in namespace '{namespace}'")

            # Mark as initialized only after verification
            VolumeInitializer._initialized = True

        except Exception as e:
            error_msg = (
                f"Volume check or dataset initialization failed for PVC '{pvc_name}' in namespace '{namespace}'."
            )
            logger.error(error_msg)
            logger.error(f"Error details: {e}")

            # Check if it's specifically a missing PVC error
            if "not found in namespace" in str(e):
                raise DatasetVolumeNotFoundError(
                    f"Required PVC '{pvc_name}' not found in namespace '{namespace}'. "
                    f"Please ensure the volume is created before starting the application."
                ) from e

            # For other errors, raise as-is
            raise

    # async def _verify_dataset_initialization(self):
    #     """Verify that the dataset has been properly initialized by checking for the marker file."""
    #     import asyncio
    #     import subprocess

    #     logger.info("Verifying dataset initialization...")

    #     max_retries = 10
    #     retry_delay = 30  # seconds

    #     for attempt in range(max_retries):
    #         try:
    #             # Use kubectl to check if the dataset_initialized file exists
    #             result = subprocess.run(
    #                 [
    #                     "kubectl",
    #                     "run",
    #                     "dataset-verify",
    #                     "-n",
    #                     "budeval",
    #                     "--rm",
    #                     "-i",
    #                     "--restart=Never",
    #                     "--image=busybox",
    #                     "--overrides",
    #                     '{"spec":{"containers":[{"name":"dataset-verify","volumeMounts":[{"name":"data","mountPath":"/data"}]}],"volumes":[{"name":"data","persistentVolumeClaim":{"claimName":"bud-dev-budeval-dataset-rwx"}}]}}',
    #                     "--",
    #                     "sh",
    #                     "-c",
    #                     "test -f /data/dataset_initialized && echo 'INITIALIZED' || echo 'NOT_INITIALIZED'",
    #                 ],
    #                 capture_output=True,
    #                 text=True,
    #                 timeout=60,
    #             )

    #             if result.returncode == 0 and "INITIALIZED" in result.stdout:
    #                 logger.info("Dataset initialization verified successfully")
    #                 return
    #             elif attempt < max_retries - 1:
    #                 logger.info(
    #                     f"Dataset not yet initialized (attempt {attempt + 1}/{max_retries}), waiting {retry_delay} seconds..."
    #                 )
    #                 await asyncio.sleep(retry_delay)
    #             else:
    #                 logger.warning("Dataset initialization could not be verified after maximum retries")

    #         except subprocess.TimeoutExpired:
    #             logger.warning(f"Verification timeout on attempt {attempt + 1}")
    #             if attempt < max_retries - 1:
    #                 await asyncio.sleep(retry_delay)
    #         except Exception as e:
    #             logger.error(f"Error during dataset verification attempt {attempt + 1}: {e}")
    #             if attempt < max_retries - 1:
    #                 await asyncio.sleep(retry_delay)
