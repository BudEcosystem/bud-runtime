"""Engine preloader module for ensuring required Docker images are available."""

import uuid
from typing import Dict, List, Optional

from budeval.commons.logging import logging
from budeval.registry.engines.core import EngineRegistry
from budeval.registry.orchestrator.ansible_orchestrator import AnsibleOrchestrator


logger = logging.getLogger(__name__)


class EnginePreloader:
    """Handles preloading of evaluation engine Docker images."""

    _initialized = False
    _preloaded_engines = set()

    def __init__(self):
        """Initialize the engine preloader with an Ansible orchestrator."""
        self.orchestrator = AnsibleOrchestrator()

    async def preload_all_engines(self, kubeconfig: Optional[str] = None):
        """Preload all registered evaluation engines.

        Args:
            kubeconfig: Optional kubernetes config. If not provided, uses in-cluster config.
        """
        # Skip if already initialized
        if EnginePreloader._initialized:
            logger.debug("Engine preloading already completed, skipping")
            return

        logger.info("Starting preloading of evaluation engines")
        logger.info(f"Kubeconfig provided: {kubeconfig is not None}")

        try:
            # Get all registered engines
            registered_engines = EngineRegistry.list_engines()
            logger.info(f"Found {len(registered_engines)} registered engines: {list(registered_engines.keys())}")

            if not registered_engines:
                logger.info("No engines registered, skipping preloading")
                EnginePreloader._initialized = True
                return

            # Collect all Docker images
            engine_images = []
            for engine_name, metadata in registered_engines.items():
                if metadata.docker_image_url:
                    engine_images.append(
                        {"name": engine_name, "image": metadata.docker_image_url, "version": metadata.version}
                    )
                    logger.info(f"Engine '{engine_name}' uses image: {metadata.docker_image_url}")
                else:
                    logger.warning(f"Engine '{engine_name}' has no Docker image specified")

            if not engine_images:
                logger.info("No Docker images to preload")
                EnginePreloader._initialized = True
                return

            # Generate a unique operation ID
            operation_id = f"engine-preload-{uuid.uuid4().hex[:8]}"
            logger.info(f"Engine preload operation ID: {operation_id}")

            # Run the preloading process
            await self._preload_engines(operation_id, engine_images, kubeconfig)

            # Mark as initialized
            EnginePreloader._initialized = True
            EnginePreloader._preloaded_engines.update([img["name"] for img in engine_images])
            logger.info(f"Successfully preloaded {len(engine_images)} evaluation engines")

        except Exception as e:
            logger.error(f"Failed to preload evaluation engines: {e}", exc_info=True)
            # Don't fail the startup, just log the error

    async def preload_specific_engines(self, engine_names: List[str], kubeconfig: Optional[str] = None):
        """Preload specific evaluation engines by name.

        Args:
            engine_names: List of engine names to preload
            kubeconfig: Optional kubernetes config. If not provided, uses in-cluster config.
        """
        logger.info(f"Preloading specific engines: {engine_names}")

        try:
            # Get engine metadata for specified engines
            engine_images = []
            for engine_name in engine_names:
                try:
                    metadata = EngineRegistry.get_metadata(engine_name)
                    if metadata.docker_image_url:
                        engine_images.append(
                            {"name": engine_name, "image": metadata.docker_image_url, "version": metadata.version}
                        )
                        logger.info(f"Will preload engine '{engine_name}': {metadata.docker_image_url}")
                    else:
                        logger.warning(f"Engine '{engine_name}' has no Docker image specified")
                except KeyError:
                    logger.error(f"Engine '{engine_name}' not found in registry")
                    continue

            if not engine_images:
                logger.info("No valid engines to preload")
                return

            # Generate operation ID
            operation_id = f"engine-preload-{uuid.uuid4().hex[:8]}"

            # Run the preloading process
            await self._preload_engines(operation_id, engine_images, kubeconfig)

            # Update preloaded engines set
            EnginePreloader._preloaded_engines.update([img["name"] for img in engine_images])
            logger.info(f"Successfully preloaded {len(engine_images)} specific engines")

        except Exception as e:
            logger.error(f"Failed to preload specific engines: {e}", exc_info=True)

    async def _preload_engines(
        self, operation_id: str, engine_images: List[Dict[str, str]], kubeconfig: Optional[str]
    ):
        """Run the engine preloading process.

        Args:
            operation_id: Unique operation identifier
            engine_images: List of engine image metadata
            kubeconfig: Optional kubernetes config
        """
        logger.info(f"Running engine preloading process with {len(engine_images)} images")

        # Use the preload_eval_engines playbook
        playbook = "preload_eval_engines.yml"
        logger.info(f"Using playbook: {playbook}")

        # Prepare files and extravars
        files = {}
        extravars = {"engine_images": engine_images, "namespace": "budeval"}

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
        logger.info(f"Running ansible playbook to preload {len(engine_images)} engine images")
        self.orchestrator._run_ansible_playbook(playbook, operation_id, files, extravars)
        logger.info("Engine preloading playbook completed")

    @classmethod
    def is_engine_preloaded(cls, engine_name: str) -> bool:
        """Check if a specific engine has been preloaded.

        Args:
            engine_name: Name of the engine to check

        Returns:
            True if the engine has been preloaded, False otherwise
        """
        return engine_name in cls._preloaded_engines

    @classmethod
    def get_preloaded_engines(cls) -> set:
        """Get the set of preloaded engine names.

        Returns:
            Set of engine names that have been preloaded
        """
        return cls._preloaded_engines.copy()

    @classmethod
    def is_initialized(cls) -> bool:
        """Check if engine preloading has been initialized.

        Returns:
            True if initialization is complete, False otherwise
        """
        return cls._initialized
