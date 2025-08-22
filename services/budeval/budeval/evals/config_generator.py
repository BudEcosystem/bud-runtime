"""Config generator for OpenCompass model configurations."""

from budeval.commons.logging import logging


logger = logging.getLogger(__name__)


class OpenCompassConfigGenerator:
    """Generates OpenCompass configuration files dynamically."""

    @staticmethod
    def generate_bud_model_config(model_name: str, api_key: str, base_url: str, eval_request_id: str, **kwargs) -> str:
        """Generate bud-model.py content with actual payload data using OpenCompass format.

        Args:
            model_name: The model name/path
            api_key: API key for authentication
            base_url: Base URL for the API
            eval_request_id: Unique evaluation request ID
            **kwargs: Additional configuration parameters

        Returns:
            str: The Python configuration file content
        """
        # Extract additional parameters with defaults
        max_out_len = kwargs.get("max_out_len", 2048)
        max_seq_len = kwargs.get("max_seq_len", 4096)
        batch_size = kwargs.get("batch_size", 8)
        query_per_second = kwargs.get("query_per_second", 1)

        config_content = f"""from opencompass.models import OpenAI

models = [
    dict(
        abbr='{eval_request_id}',
        type=OpenAI,
        path='{model_name}',
        key='{api_key}',
        query_per_second={query_per_second},
        max_out_len={max_out_len},
        max_seq_len={max_seq_len},
        openai_api_base='{base_url}',
        batch_size={batch_size}),
]
"""

        logger.info(f"Generated bud-model.py config for model: {model_name}")
        return config_content

    @staticmethod
    def generate_dataset_config(datasets: list[str]) -> str:
        """Generate dataset configuration.

        Args:
            datasets: List of dataset names to evaluate

        Returns:
            str: The dataset configuration content
        """
        # Simple dataset configuration that works with OpenCompass
        # We'll use the _gen suffix for generation-based evaluation
        dataset_list = []
        for dataset in datasets:
            dataset_name = dataset.lower()
            # Add _gen suffix if not already present
            if not dataset_name.endswith("_gen"):
                dataset_name = f"{dataset_name}_gen"
            dataset_list.append(f"'{dataset_name}'")

        config_content = f"""# Dataset configuration
from opencompass.datasets import *

# Use predefined dataset configurations
datasets = [{", ".join(dataset_list)}]
"""

        return config_content
