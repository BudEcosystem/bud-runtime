"""OpenCompass-specific transformer implementation."""

import json
import os
from typing import Any, Dict, List, Tuple

from budeval.commons.logging import logging
from budeval.core.schemas import (
    EvaluationEngine,
    GenericEvaluationRequest,
    ModelType,
    TransformedEvaluationData,
)
from budeval.core.transformers.base import BaseTransformer


logger = logging.getLogger(__name__)


class OpenCompassTransformer(BaseTransformer):
    """Transformer for OpenCompass evaluation engine.

    This transformer uses a hybrid approach:
    - CLI arguments for most configuration options
    - Environment variables for API credentials and base URLs
    - Minimal config file generation only when necessary
    - Dataset mappings loaded from eval_manifest.json
    """

    def __init__(self, engine: EvaluationEngine = EvaluationEngine.OPENCOMPASS):
        """Initialize OpenCompass transformer.

        Loads dataset mappings from eval_manifest.json on initialization.
        """
        super().__init__(engine)
        self._eval_manifest = None
        self._dataset_mappings = {}
        self._load_eval_manifest()

    def _load_eval_manifest(self) -> None:
        """Load evaluation manifest with dataset mappings."""
        manifest_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "data", "eval_manifest.json"
        )

        with open(manifest_path, "r") as f:
            self._eval_manifest = json.load(f)

        # Build dataset mappings from manifest
        if "datasets" in self._eval_manifest:
            for _provider, provider_data in self._eval_manifest["datasets"].items():
                if "datasets" in provider_data:
                    for dataset in provider_data["datasets"]:
                        dataset_name = dataset.get("name", "").lower()
                        # Store dataset info for OpenCompass
                        self._dataset_mappings[dataset_name] = {
                            "id": dataset.get("id"),
                            "name": dataset.get("name"),
                            "description": dataset.get("description"),
                            "version": dataset.get("version"),
                            "opencompass_name": dataset.get("name"),  # Use the exact name for OpenCompass
                        }

        logger.info(f"Loaded {len(self._dataset_mappings)} dataset mappings from manifest")

    def transform_request(self, request: GenericEvaluationRequest) -> TransformedEvaluationData:
        """Transform generic request to OpenCompass-specific format."""
        # Validate the request
        self.validate_request(request)

        # Generate configuration files
        config_files = self.generate_config_files(request)

        # Create job configuration
        job_config = self.create_job_config(request)

        return TransformedEvaluationData(
            engine=self.engine,
            job_config=job_config,
            config_files=config_files,
            metadata={
                "model_name": request.model.name,
                "datasets": [d.name for d in request.datasets],
                "eval_request_id": str(request.eval_request_id),
            },
        )

    def generate_config_files(self, request: GenericEvaluationRequest) -> Dict[str, str]:
        """Generate minimal configuration files for OpenCompass."""
        config_files = {}

        # Since we're using CLI + environment variables, we only need metadata
        # The actual model config is generated inline in build_command()
        config_files["metadata.json"] = json.dumps(
            {
                "eval_request_id": str(request.eval_request_id),
                "model_name": request.model.name,
                "datasets": [d.name for d in request.datasets],
                "engine": self.engine.value,
                "eval_mode": request.extra_params.get("eval_mode", "gen"),
            },
            indent=2,
        )

        return config_files

    def build_command(self, request: GenericEvaluationRequest) -> Tuple[List[str], List[str]]:
        """Build OpenCompass command and arguments.

        Creates a bash script that:
        1. Generates a model config file that reads from environment variables
        2. Runs OpenCompass with the model config and datasets specified via CLI
        3. Uses environment variables for API credentials (set by get_environment_variables)

        Args:
            request: The evaluation request

        Returns:
            Tuple of (command, args) where command is ["/bin/bash", "-c"] and
            args contains the script to execute
        """
        logger.info("OpenCompassTransformer.build_command called!")
        command = ["/bin/bash", "-c"]

        # Get dataset names from manifest
        dataset_names = []
        for dataset in request.datasets:
            opencompass_name = self.get_dataset_mapping(dataset.name)
            if opencompass_name:
                dataset_names.append(opencompass_name)
                logger.info(f"Mapped dataset {dataset.name} -> {opencompass_name}")
            else:
                logger.warning(f"No mapping found for dataset {dataset.name}, using original name: {dataset.name}")
                dataset_names.append(dataset.name)

        # If no datasets found, fall back to the original requested names
        if not dataset_names:
            dataset_names = [d.name for d in request.datasets]
            logger.warning(f"No dataset mappings found, using original names: {dataset_names}")

        logger.info(f"Final dataset list for OpenCompass: {dataset_names}")

        # Create a model-only config file
        datasets_str = " ".join(dataset_names)
        logger.debug(f"Generated datasets string: {datasets_str}")

        #         models = [
        #     dict(
        #         type=OpenAISDK,
        #         abbr=os.environ.get('MODEL_NAME', 'qwen3-4b'),
        #         path=os.environ.get('MODEL_NAME', 'qwen3-4b'),  # Actual model name for API
        #         key=os.environ.get('OPENAI_API_KEY'),
        #         openai_api_base=os.environ.get('OPENAI_API_BASE'),
        #         query_per_second={int(request.model.extra_params.get("query_per_second", "1"))},
        #         max_out_len={int(request.model.extra_params.get("max_out_len", str(request.model.max_tokens or 2048)))},
        #         max_seq_len={int(request.model.extra_params.get("max_seq_len", "4096"))},
        #         batch_size={request.batch_size}
        #     ),
        # ]

        # # Run OpenCompass evaluation with model config and datasets via CLI
        # python /workspace/run.py \\
        #     --models bud_model \\
        #     --datasets {datasets_str} \\
        #     --work-dir /workspace/outputs \\
        #     --max-num-workers {request.num_workers}{debug_flag}

        script = f"""
# Create a model config file that uses environment variables
mkdir -p /workspace/opencompass/configs/models
cat > /workspace/opencompass/configs/models/bud_model.py << 'EOF'
from opencompass.models import OpenAISDK
import os

models = [
    dict(
        type=OpenAISDK,
        abbr=os.environ.get('MODEL_NAME', 'qwen3-4b'),
        path=os.environ.get('MODEL_NAME', 'qwen3-4b'),  # Actual model name for API
        key=os.environ.get('OPENAI_API_KEY'),
        openai_api_base=os.environ.get('OPENAI_API_BASE'),
        query_per_second={int(request.model.extra_params.get("query_per_second", "10"))},
        max_out_len={int(request.model.extra_params.get("max_out_len", str(request.model.max_tokens or 2048)))},
        max_seq_len={int(request.model.extra_params.get("max_seq_len", "4096"))},
        batch_size={request.batch_size}
    )
]
EOF

# Change to workspace directory where OpenCompass is installed
cd /workspace

# Run OpenCompass evaluation with model config and datasets via CLI
python /workspace/run.py \\
    --models bud_model \\
    --datasets demo_gsm8k_chat_gen \\
    --work-dir /workspace/outputs \\
    --max-num-workers {request.num_workers} --debug
"""

        args = [script.strip()]

        logger.debug(f"Generated OpenCompass command: {command}")
        logger.debug(f"Generated script content:\n{script}")

        return command, args

    def get_docker_image(self) -> str:
        """Get OpenCompass Docker image."""
        return "ghcr.io/rahulvramesh/opencompass:latest"

    def get_volume_mounts(self) -> List[Dict[str, Any]]:
        """Get volume mounts for OpenCompass."""
        return [
            {
                "name": "datasets",
                "mountPath": "/workspace/data",
                "readOnly": True,
                "claimName": "eval-datasets-pvc",
            },
            {
                "name": "cache",
                "mountPath": "/workspace/cache",
                "type": "emptyDir",
            },
        ]

    def get_environment_variables(self, request: GenericEvaluationRequest) -> Dict[str, str]:
        """Get environment variables for OpenCompass.

        Sets up:
        - Cache directories for HuggingFace, Transformers, and PyTorch
        - API credentials (OPENAI_API_KEY and OPENAI_API_BASE)
        - Model name for correct API calls
        - Any additional environment variables from request.extra_params

        Args:
            request: The evaluation request

        Returns:
            Dictionary of environment variable name to value mappings
        """
        env_vars = {
            "HF_HOME": "/workspace/cache/huggingface",
            "TRANSFORMERS_CACHE": "/workspace/cache/transformers",
            "TORCH_HOME": "/workspace/cache/torch",
            "ENGINE_ARGS": json.dumps(request.model.extra_params),
            "MODEL_NAME": request.model.name,  # Pass model name as env var
        }

        # Add API configuration as environment variables
        if request.model.type == ModelType.API:
            if request.model.api_key:
                env_vars["OPENAI_API_KEY"] = request.model.api_key
                logger.debug("Added API key to environment variables")
            if request.model.base_url:
                env_vars["OPENAI_API_BASE"] = request.model.base_url
                logger.debug(f"Added API base URL to environment variables: {request.model.base_url}")

        # Add any additional environment variables from the request
        if "env_vars" in request.extra_params:
            additional_vars = request.extra_params["env_vars"]
            env_vars.update(additional_vars)
            logger.debug(f"Added additional environment variables: {list(additional_vars.keys())}")

        logger.info(f"Generated {len(env_vars)} environment variables for OpenCompass")
        logger.debug(f"Environment variables (without sensitive values): {list(env_vars)}")

        return env_vars

    def validate_request(self, request: GenericEvaluationRequest) -> None:
        """Validate that the request is compatible with OpenCompass."""
        logger.info(f"Validating request for model: {request.model.name}, type: {request.model.type}")
        logger.info(f"Request includes {len(request.datasets)} dataset(s): {[d.name for d in request.datasets]}")

        # Check if model type is supported
        if request.model.type not in [ModelType.API]:
            logger.error(f"Unsupported model type: {request.model.type}")
            raise ValueError(f"OpenCompass transformer currently only supports API models, got {request.model.type}")

        # Check if API model has required fields
        if request.model.type == ModelType.API:
            if not request.model.api_key:
                logger.error("Missing API key for API model")
                raise ValueError("API key is required for API models")
            if not request.model.base_url:
                logger.error("Missing base URL for API model")
                raise ValueError("Base URL is required for API models")

            logger.debug("API model validation passed - has api_key and base_url")

        # Check if datasets are supported
        unsupported = []
        supported = []
        for dataset in request.datasets:
            if dataset.name.lower() not in self._dataset_mappings:
                unsupported.append(dataset.name)
            else:
                supported.append(dataset.name)

        if supported:
            logger.info(f"Found mappings for datasets: {supported}")

        if unsupported:
            logger.warning(f"The following datasets may not be supported by OpenCompass: {unsupported}")

        logger.info("Request validation completed successfully")

    def get_supported_datasets(self) -> List[str]:
        """Get list of datasets supported by OpenCompass."""
        return list(self._dataset_mappings.keys())

    def get_dataset_mapping(self, dataset_name: str) -> str:
        """Map generic dataset name to OpenCompass-specific name."""
        mapping = self._dataset_mappings.get(dataset_name.lower(), {})
        return mapping.get("opencompass_name", "")
