"""Implements model, arguments compatibility checks for LatentBud embedding engine."""

import random
from typing import Any, Dict, Optional

from budmicroframe.commons import logging
from pydantic import Field
from transformers import AutoConfig

from ..commons.config import app_settings
from .base import BaseEngineArgs, BaseEngineCompatibility


logger = logging.get_logger(__name__)

# Embedding models supported by LatentBud
_EMBEDDING_MODELS = {
    # Nomic models
    "NomicBertModel": ("nomic_bert", "NomicBertModel"),
    # BERT-based models
    "BertModel": ("bert", "BertModel"),
    "BertForMaskedLM": ("bert", "BertModel"),
    # RoBERTa-based models
    "RobertaModel": ("roberta", "RobertaModel"),
    "RobertaForMaskedLM": ("roberta", "RobertaModel"),
    "XLMRobertaModel": ("xlm_roberta", "XLMRobertaModel"),
    # Sentence Transformers compatible models
    "MPNetModel": ("mpnet", "MPNetModel"),
    "DistilBertModel": ("distilbert", "DistilBertModel"),
    # E5 models (based on BERT/RoBERTa)
    "XLMRobertaForMaskedLM": ("xlm_roberta", "XLMRobertaModel"),
    # BGE models
    "BgeModel": ("bge", "BgeModel"),
    # GTE models
    "NewModel": ("gte", "GteModel"),
    # Instructor models
    "T5EncoderModel": ("t5", "T5EncoderModel"),
}


class EngineArgs(BaseEngineArgs):
    """Implements engine arguments for LatentBud embedding scheduler."""

    model: str = Field(
        description="The model name/path for embeddings.",
        alias="args_model-id",
    )
    max_batch_tokens: int = Field(
        description="Maximum tokens per batch for embedding inference.",
        alias="args_max-batch-tokens",
        default=16384,
    )
    batch_strategy: str = Field(
        description="Batching strategy: 'tokens' or 'requests'.",
        alias="args_batch-strategy",
        default="tokens",
    )
    lengths_via_tokenize: bool = Field(
        description="Use tokenizer for accurate length calculation.",
        alias="args_lengths-via-tokenize",
        default=True,
    )
    target_device: str = Field(
        description="The target device.",
        alias="env_LATENTBUD_DEVICE",
        default="cuda",
        examples=["cpu", "cuda"],
    )

    @staticmethod
    def get_max_batch_tokens(value: Optional[int] = None) -> int:
        """Retrieve max batch tokens with mutation for genetic algorithm.

        Args:
            value: Initial value for mutation. Defaults to None.

        Returns:
            int: Batch token size between 4096 and 32768.
        """
        min_val = 4096
        max_val = 32768
        step = 1024
        if value is not None:
            mutation = random.choice([-1, 0, 1]) * step
            return min(max_val, max(min_val, value + mutation))
        return random.randrange(min_val, max_val + 1, step)

    @staticmethod
    def get_batch_strategy(value: Optional[str] = None) -> str:
        """Retrieve batch strategy with mutation for genetic algorithm.

        Args:
            value: Initial value for mutation. Defaults to None.

        Returns:
            str: Either 'tokens' or 'requests'.
        """
        choices = ["tokens", "requests"]
        if value is not None:
            # Mutate to the other option with some probability
            if random.random() < 0.3:
                return [c for c in choices if c != value][0]
            return value
        return random.choice(choices)

    @staticmethod
    def get_lengths_via_tokenize(value: Optional[bool] = None) -> bool:
        """Retrieve lengths_via_tokenize setting.

        For embedding models, this should generally be True for accuracy.

        Args:
            value: Initial value for mutation. Defaults to None.

        Returns:
            bool: Always True for embedding models.
        """
        return True  # Always use tokenizer for accurate lengths

    @staticmethod
    def get_target_device(value: Optional[str] = None) -> str:
        """Retrieve the target device.

        Args:
            value: Initial value for mutation. Defaults to None.

        Returns:
            str: Target device ('cpu' or 'cuda').
        """
        if value is not None:
            return value
        return random.choice(["cpu", "cuda"])

    def get_properties(self) -> Dict[str, Any]:
        """Get properties for genetic algorithm optimization."""
        properties_to_skip = [
            "target_device",
            "model",
            "lengths_via_tokenize",  # Always true, no need to optimize
        ]
        return super()._get_properties(properties_to_skip)

    def get_args_and_envs(self) -> Dict[str, Dict[str, Any]]:
        """Get the arguments and environment variables for the engine.

        Returns:
            Dict[str, Dict[str, Any]]: Dictionary containing args and envs.
        """
        args_and_envs = super().get_args_and_envs()

        # Ensure lengths-via-tokenize is string "true" for CLI compatibility
        if "lengths-via-tokenize" in args_and_envs["args"]:
            args_and_envs["args"]["lengths-via-tokenize"] = "true"

        return args_and_envs


class EngineCompatibility(BaseEngineCompatibility):
    """Compatibility checker for LatentBud embedding engine."""

    def check_cpu_compatibility(self, engine_args: Dict[str, Any]) -> bool:
        """Check if the engine args are compatible with CPU."""
        return True

    def check_gpu_compatibility(self, engine_args: Dict[str, Any]) -> bool:
        """Check if the engine args are compatible with GPU."""
        return True

    def check_args_compatibility(self, engine_args: Dict[str, Any]) -> bool:
        """Check the compatibility of the engine args."""
        target_device = engine_args.get("target_device", "cuda")

        if target_device in ("cpu", "cpu_high"):
            return self.check_cpu_compatibility(engine_args)
        elif target_device == "cuda":
            return self.check_gpu_compatibility(engine_args)
        else:
            raise ValueError(f"target_device {target_device} is not supported by LatentBud.")

    def check_model_compatibility(self, model: str) -> bool:
        """Check if the model is compatible with LatentBud embedding engine.

        Args:
            model: Model name or path.

        Returns:
            bool: True if model is an embedding model compatible with LatentBud.
        """
        try:
            config = AutoConfig.from_pretrained(model, trust_remote_code=True)
            for arch in config.architectures:
                if arch in _EMBEDDING_MODELS:
                    logger.info(f"Model {model} is compatible with LatentBud.")
                    return True

            # Also check if it's a sentence-transformers model
            if hasattr(config, "sentence_transformers"):
                logger.info(f"Model {model} is a sentence-transformers model, compatible with LatentBud.")
                return True

            logger.info(f"Model {model} is not compatible with LatentBud.")
            return False
        except Exception as e:
            logger.warning(f"Failed to check model compatibility for {model}: {e}")
            return False

    def check_device_compatibility(self, device: str) -> Optional[str]:
        """Check if the device is compatible with LatentBud and return image.

        Args:
            device: Target device type.

        Returns:
            Optional[str]: Container image for the device, or None if not supported.
        """
        return {
            "cpu": app_settings.latentbud_cpu_image,
            "cpu_high": app_settings.latentbud_cpu_image,
            "cuda": app_settings.latentbud_cuda_image,
        }.get(device)
