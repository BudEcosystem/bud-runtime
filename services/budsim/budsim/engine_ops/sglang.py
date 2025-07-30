import random
from typing import Any, Dict, Optional

from budmicroframe.commons import logging
from pydantic import Field
from transformers import AutoConfig

from ..commons.config import app_settings
from .base import BaseEngineArgs, BaseEngineCompatibility


logger = logging.get_logger(__name__)

_MODELS = {
    "BaichuanForCausalLM": ("baichuan", "BaichuanForCausalLM"),
    "ChatGLMForCausalLM": ("chatglm", "ChatGLMForCausalLM"),
    "ChatGLMModel": ("chatglm", "ChatGLMForCausalLM"),
    "CohereForCausalLM": ("commandr", "CohereForCausalLM"),
    "DbrxForCausalLM": ("dbrx", "DbrxForCausalLM"),
    "DeepseekV2ForCausalLM": ("deepseek_v2", "DeepseekV2ForCausalLM"),
    "DeepseekForCausalLM": ("deepseek", "DeepseekForCausalLM"),
    "ExaoneForCausalLM": ("exaone", "ExaoneForCausalLM"),
    "GemmaForCausalLM": ("gemma", "GemmaForCausalLM"),
    "Gemma2ForCausalLM": ("gemma2", "Gemma2ForCausalLM"),
    "GPTBigCodeForCausalLM": ("gpt_bigcode", "GPTBigCodeForCausalLM"),
    "Grok1ForCausalLM": ("grok1", "Grok1ForCausalLM"),
    "Grok1ModelForCausalLM": ("grok1", "Grok1ForCausalLM"),
    "InternLM2ForCausalLM": ("internlm2", "InternLM2ForCausalLM"),
    "LlamaForClassification": ("llama", "LlamaForClassification"),
    "LlamaEmbeddingModel": ("llama", "LlamaEmbeddingModel"),
    "MistralModel": ("mistral", "MistralModel"),
    "LlamaForSequenceClassification": ("llama", "LlamaForSequenceClassification"),
    "LlamaForSequenceClassificationWithNormal_Weights": ("llama", "LlamaForSequenceClassificationWithNormal_Weights"),
    "LlamaForCausalLM": ("llama", "LlamaForCausalLM"),
    "Phi3ForCausalLM": ("phi3", "Phi3ForCausalLM"),
    "LlavaLlamaForCausalLM": ("llava", "LlavaLlamaForCausalLM"),
    "LlavaQwenForCausalLM": ("llava", "LlavaQwenForCausalLM"),
    "LlavaMistralForCausalLM": ("llava", "LlavaMistralForCausalLM"),
    "LlavaVidForCausalLM": ("llava", "LlavaVidForCausalLM"),
    "MiniCPMForCausalLM": ("minicpm", "MiniCPMForCausalLM"),
    "MiniCPM3ForCausalLM": ("minicpm3", "MiniCPM3ForCausalLM"),
    "MistralForCausalLM": ("mistral", "MistralForCausalLM"),
    "QuantMixtralForCausalLM": ("quant_mixtral", "QuantMixtralForCausalLM"),
    "MixtralForCausalLM": ("mixtral", "MixtralForCausalLM"),
    "OlmoForCausalLM": ("olmo", "OlmoForCausalLM"),
    "OlmoeForCausalLM": ("olmoe", "OlmoeForCausalLM"),
    "QWenLMHeadModel": ("qwen", "QWenLMHeadModel"),
    "Qwen2MoeForCausalLM": ("qwen2", "Qwen2MoeForCausalLM"),
    "Qwen2ForCausalLM": ("qwen2", "Qwen2ForCausalLM"),
    "StableLmForCausalLM": ("stablelm", "StableLmForCausalLM"),
    "TorchNativeLlamaForCausalLM": ("llama", "TorchNativeLlamaForCausalLM"),
    "TorchNativePhi3ForCausalLM": ("phi3", "TorchNativePhi3ForCausalLM"),
    "XverseMoeForCausalLM": ("xverse", "XverseMoeForCausalLM"),
    "XverseForCausalLM": ("xverse", "XverseForCausalLM"),
    "YiVLForCausalLM": ("yivl", "YiVLForCausalLM"),
}


class EngineArgs(BaseEngineArgs):
    """Implements engine arguments for sglang."""

    tensor_parallel_size: int = Field(
        description="The tensor parallel size.",
        alias="args_tensor_parallel_size",
        default=1,
    )

    pipeline_parallel_size: int = Field(
        description="The pipeline parallel size.",
        alias="args_pipeline_parallel_size",
        default=1,
    )

    disable_custom_all_reduce: bool = Field(
        description="Whether to disable custom all reduce.",
        alias="args_disable_custom_all_reduce",
        default=True,
    )

    target_device: str = Field(
        description="The target device.",
        alias="args_device",
        default="cuda",
        examples=["xpu", "cuda"],
    )

    @staticmethod
    def get_pipeline_parallel_size(value: Optional[int] = None) -> int:
        """Retrieve the pipeline parallel size.

        This method returns a random integer between the minimum and maximum
        values for the pipeline parallel size, incremented by 2.

        Args:
            value (int, optional): The initial value for mutation. Defaults to None.

        Returns:
            int: A random integer between 1 and 8, incremented by powers of 2.
        """
        min_val = 1
        max_val = 3
        if value is not None:
            mutation = random.choice([-1, 1]) * 2
            mutated_value = min(max_val, max(min_val, value + mutation))
            return int(2**mutated_value)
        return int(2 ** random.randint(min_val, max_val))

    @staticmethod
    def get_disable_custom_all_reduce(value: Optional[bool] = None) -> bool:
        """Retrieve the disable custom all reduce flag.

        This method returns a boolean value. If a value is provided, it returns the opposite of that value.
        If no value is provided, it randomly selects between True and False.

        Args:
            value (bool, optional): The initial value for mutation. Defaults to None.

        Returns:
            bool: A boolean value.
        """
        if value is not None:
            return not value
        return random.choice([True, False])

    @staticmethod
    def get_target_device(value: Optional[str] = None) -> str:
        """Retrieve the target device.

        This method returns the target device based on the provided value.
        If a value is provided, it returns "cuda" if the value is "xpu" and "xpu" otherwise.
        If no value is provided, it randomly selects between "xpu" and "cuda".

        Args:
            value (str, optional): The initial value for mutation. Defaults to None.

        Returns:
            str: The target device, either "xpu" or "cuda".
        """
        if value is not None:
            return "cuda" if value == "xpu" else "xpu"
        return random.choice(["xpu", "cuda"])

    def get_properties(self) -> Dict[str, Any]:
        """Dynamically creates a map of property names and their corresponding random generator functions from the default_factory."""
        properties_to_skip = ["target_device"]
        return super()._get_properties(properties_to_skip)


class EngineCompatibility(BaseEngineCompatibility):
    """Implements engine compatibility checks for sglang."""

    def check_args_compatibility(self, engine_args: Dict[str, Any]) -> bool:
        """Check the compatibility of the engine args/envs combinations."""
        tp_size = engine_args.get("tensor_parallel_size", 1)
        pp_size = engine_args.get("pipeline_parallel_size", 1)

        if tp_size > 1:
            assert engine_args.get("disable_custom_all_reduce"), (
                "disable_custom_all_reduce must be set to True when tensor_parallel_size > 1."
            )

        # Basic validation for PP and TP sizes
        if pp_size is not None:
            assert isinstance(pp_size, int) and pp_size >= 1, (
                f"pipeline_parallel_size must be a positive integer, got {pp_size}"
            )

        if tp_size is not None:
            assert isinstance(tp_size, int) and tp_size >= 1, (
                f"tensor_parallel_size must be a positive integer, got {tp_size}"
            )

        # SGLang supports pipeline parallelism for multi-node deployments
        # Additional SGLang-specific PP constraints can be added here as needed

        return True

    def check_model_compatibility(self, model: str) -> bool:
        """Check if the model is compatible with the SGLang scheduler based on its architecture."""
        config = AutoConfig.from_pretrained(model, trust_remote_code=True)
        for arch in config.architectures:
            if arch in _MODELS:
                logger.info(f"Model {model} is compatible with SGLang scheduler.")
                return True
        logger.info(f"Model {model} is not compatible with SGLang scheduler.")
        return False

    def check_device_compatibility(self, device: str) -> Optional[str]:
        """Check if the device is compatible with SGLang scheduler."""
        if device == "cuda":
            return app_settings.sglang_cuda_image
        else:
            return None
