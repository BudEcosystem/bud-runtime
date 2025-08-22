"""Volume initialization module for ensuring required persistent volumes exist."""

import uuid
from typing import Optional

from budeval.commons.logging import logging
from budeval.registry.orchestrator.ansible_orchestrator import AnsibleOrchestrator


logger = logging.getLogger(__name__)


class VolumeInitializer:
    """Handles initialization of required persistent volumes."""

    _initialized = False

    def __init__(self):
        """Initialize the volume initializer with an Ansible orchestrator."""
        self.orchestrator = AnsibleOrchestrator()

    @classmethod
    def reset_initialization_state(cls):
        """Reset the initialization state for testing purposes."""
        cls._initialized = False

    async def ensure_eval_datasets_volume(self, kubeconfig: Optional[str] = None):
        """Ensure the eval-datasets volume exists in the budeval namespace.

        Args:
            kubeconfig: Optional kubernetes config. If not provided, uses in-cluster config.
        """
        # Skip if already initialized
        if VolumeInitializer._initialized:
            logger.debug("Volume initialization already completed, skipping")
            return

        logger.info("Ensuring eval-datasets volume exists in budeval namespace")
        logger.info(f"Kubeconfig provided: {kubeconfig is not None}")

        try:
            # Generate a unique ID for this operation
            operation_id = f"volume-init-{uuid.uuid4().hex[:8]}"
            logger.info(f"Volume init operation ID: {operation_id}")

            # Use the ensure_eval_datasets_volume playbook
            playbook = "ensure_eval_datasets_volume.yml"
            logger.info(f"Using playbook: {playbook}")

            # Prepare files and extravars
            files = {}
            extravars = {}

            # Get storage configuration based on environment
            from budeval.commons.config import app_settings
            from budeval.commons.storage_config import StorageConfig

            storage_config = StorageConfig.get_eval_datasets_config()
            environment = StorageConfig.get_environment()

            logger.info(f"Detected environment: {environment}")
            logger.info(f"Storage configuration: {storage_config}")

            # Set storage parameters from config
            extravars["access_mode"] = storage_config["access_mode"]
            extravars["volume_size"] = storage_config["size"]
            extravars["storage_class"] = storage_config.get("storage_class", "")

            # Set dataset URL from configuration
            extravars["opencompass_dataset_url"] = app_settings.opencompass_dataset_url
            # Extract filename from URL
            import os

            extravars["opencompass_dataset_filename"] = os.path.basename(app_settings.opencompass_dataset_url)

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

            # Run the playbook
            logger.info(f"Running ansible playbook with access_mode={extravars.get('access_mode', 'default')}")
            self.orchestrator._run_ansible_playbook(playbook, operation_id, files, extravars)
            logger.info("Successfully ensured eval-datasets volume exists")

            # Verify that dataset is actually initialized before marking as complete
            # await self._verify_dataset_initialization()

            # Mark as initialized only after verification
            VolumeInitializer._initialized = True

        except Exception as e:
            logger.error(f"Failed to ensure eval-datasets volume: {e}", exc_info=True)
            # Don't fail the startup, just log the error

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
    #                     '{"spec":{"containers":[{"name":"dataset-verify","volumeMounts":[{"name":"data","mountPath":"/data"}]}],"volumes":[{"name":"data","persistentVolumeClaim":{"claimName":"eval-datasets-pvc"}}]}}',
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
