"""Base transformer abstract class for engine-specific transformations."""

from abc import ABC, abstractmethod
from typing import Any

from budeval.core.schemas import (
    EvaluationEngine,
    GenericEvaluationRequest,
    GenericJobConfig,
    TransformedEvaluationData,
)


class BaseTransformer(ABC):
    """Abstract base class for engine-specific transformers.

    Each evaluation engine should implement this interface to transform
    generic evaluation requests into engine-specific formats.
    """

    def __init__(self, engine: EvaluationEngine):
        """Initialize the transformer with the target engine."""
        self.engine: EvaluationEngine = engine

    @abstractmethod
    def transform_request(self, request: GenericEvaluationRequest) -> TransformedEvaluationData:
        """Transform a generic evaluation request to engine-specific format.

        Args:
            request: Generic evaluation request

        Returns:
            TransformedEvaluationData containing engine-specific configuration
        """
        pass

    @abstractmethod
    def generate_config_files(self, request: GenericEvaluationRequest) -> dict[str, str]:
        """Generate engine-specific configuration files.

        Args:
            request: Generic evaluation request

        Returns:
            Dictionary mapping filename to file content
        """
        pass

    @abstractmethod
    def build_command(self, request: GenericEvaluationRequest) -> tuple[list[str], list[str]]:
        """Build the command and arguments for the evaluation job.

        Args:
            request: Generic evaluation request

        Returns:
            Tuple of (command, args) for the container
        """
        pass

    @abstractmethod
    def get_docker_image(self) -> str:
        """Get the Docker image for this engine.

        Returns:
            Docker image URL
        """
        pass

    @abstractmethod
    def get_volume_mounts(self) -> list[dict[str, Any]]:
        """Get the volume mount configuration for this engine.

        Returns:
            List of volume mount configurations
        """
        pass

    @abstractmethod
    def get_environment_variables(self, request: GenericEvaluationRequest) -> dict[str, str]:
        """Get environment variables for the evaluation job.

        Args:
            request: Generic evaluation request

        Returns:
            Dictionary of environment variables
        """
        pass

    @abstractmethod
    def validate_request(self, request: GenericEvaluationRequest) -> None:
        """Validate that the request is compatible with this engine.

        Args:
            request: Generic evaluation request

        Raises:
            ValueError: If the request is invalid for this engine
        """
        pass

    def get_supported_datasets(self) -> list[str]:
        """Get list of datasets supported by this engine.

        Returns:
            List of supported dataset names
        """
        return []

    def get_dataset_mapping(self, dataset_name: str) -> str:
        """Map generic dataset name to engine-specific name.

        Args:
            dataset_name: Generic dataset name

        Returns:
            Engine-specific dataset name
        """
        return dataset_name

    def get_default_resource_requirements(self) -> dict[str, str]:
        """Get default resource requirements for this engine.

        Returns:
            Dictionary with cpu/memory requests and limits
        """
        return {
            "cpu_request": "500m",
            "cpu_limit": "2000m",
            "memory_request": "1Gi",
            "memory_limit": "4Gi",
        }

    def create_job_config(self, request: GenericEvaluationRequest) -> GenericJobConfig:
        """Create a generic job configuration.

        Args:
            request: Generic evaluation request

        Returns:
            GenericJobConfig for Kubernetes deployment
        """
        command, args = self.build_command(request)
        config_files = self.generate_config_files(request)

        resources = self.get_default_resource_requirements()
        return GenericJobConfig(
            job_id=f"{self.engine.value}-{request.eval_request_id}",
            engine=self.engine,
            image=self.get_docker_image(),
            command=command,
            args=args,
            env_vars=self.get_environment_variables(request),
            config_volume={
                "name": "config",
                "type": "configMap",
                "configMapName": f"{self.engine.value}-config-{request.eval_request_id}",
                "files": list(config_files.keys()),
            },
            data_volumes=self.get_volume_mounts(),
            output_volume={
                "name": "output",
                "type": "shared_pvc",
                "claimName": "panda-budeval-dataset",
                "subPath": f"results/{request.eval_request_id}",
                "mountPath": "/workspace/outputs",
            },
            cpu_request=resources["cpu_request"],
            cpu_limit=resources["cpu_limit"],
            memory_request=resources["memory_request"],
            memory_limit=resources["memory_limit"],
            backoff_limit=3,
            ttl_seconds=request.timeout_minutes * 60,
            extra_params=request.extra_params,
        )
