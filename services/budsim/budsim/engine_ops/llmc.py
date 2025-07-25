

from dataclasses import Field
from typing import Any, Dict, Optional

from budmicroframe.commons import logging
from transformers import AutoConfig

from ..commons.config import app_settings
from ..engine_ops.base import BaseEngineArgs, BaseEngineCompatibility


logger = logging.get_logger(__name__)

_MODELS = {
    "BloomForCausalLM": ("bloom", "BloomForCausalLM"),
    "ChatGLMModel": ("chatglm", "ChatGLMForCausalLM"),
    "ChatGLMForConditionalGeneration": ("chatglm", "ChatGLMForCausalLM"),
    "DeepseekForCausalLM": ("deepseek", "DeepseekForCausalLM"),
    "DeepseekV2ForCausalLM": ("deepseek_v2", "DeepseekV2ForCausalLM"),
    "DeepseekV3ForCausalLM": ("deepseek_v3", "DeepseekV3ForCausalLM"),
    "FalconForCausalLM": ("falcon", "FalconForCausalLM"),
    "Gemma2ForCausalLM": ("gemma2", "Gemma2ForCausalLM"),
    "InternLM2ForCausalLM": ("internlm2", "InternLM2ForCausalLM"),
    "InternVLChatModel": ("internvl2", "InternVLChatModel"),
    "LlamaForCausalLM": ("llama", "LlamaForCausalLM"),
    "LlavaForCausalLM": ("llava", "LlavaForCausalLM"),
    "MiniCPMForCausalLM": ("minicpm", "MiniCPMForCausalLM"),
    "MiniCPM3ForCausalLM": ("minicpm3", "MiniCPM3ForCausalLM"),
    "MiniCPMV": ("minicpmv", "MiniCPMV"),
    "MistralForCausalLM": ("mistral", "MistralForCausalLM"),
    "MixtralForCausalLM": ("mixtral", "MixtralForCausalLM"),
    "MllamaForConditionalGeneration": ("mllama", "MllamaForConditionalGeneration"),
    "OPTForCausalLM": ("opt", "OPTForCausalLM"),
    "PhiForCausalLM": ("phi", "PhiForCausalLM"),
    "Phi3ForCausalLM": ("phi3", "Phi3ForCausalLM"),
    "QWenLMHeadModel": ("qwen", "QWenLMHeadModel"),
    "Qwen2ForCausalLM": ("qwen2", "Qwen2ForCausalLM"),
    "Qwen2AudioForConditionalGeneration": ("qwen2_audio", "Qwen2AudioForConditionalGeneration"),
    "Qwen2MoeForCausalLM": ("qwen2_moe", "Qwen2MoeForCausalLM"),
    "Qwen2VLForConditionalGeneration": ("qwen2_vl", "Qwen2VLForConditionalGeneration"),
    "StableLmForCausalLM": ("stablelm", "StablelmForCausalLM"),
    "StarcoderForCausalLM": ("starcoder", "StarcoderForCausalLM"),
    "Starcoder2ForCausalLM": ("starcoder2", "Starcoder2ForCausalLM"),
    # "VilaForCausalLM": ("vila", "VilaForCausalLM"),
    # "VitForCausalLM": ("vit", "VitForCausalLM"),
}

class EngineArgs(BaseEngineArgs):

    target_device: str = Field(
        description="The target device.",
        alias="env_TARGET_DEVICE",
        default="cpu",
        examples=["cpu", "cuda"],
    )


class EngineCompatibility(BaseEngineCompatibility):
    """Implements engine compatibility checks for sglang."""

    def check_args_compatibility(self, engine_args: Dict[str, Any]) -> bool:
        """Check the compatibility of the engine args/envs combinations."""
        return True

    def check_model_compatibility(self, model: str) -> bool:
        """Check if the model is compatible with the LiteLLM scheduler based on its architecture."""
        config = AutoConfig.from_pretrained(model, trust_remote_code=True)
        for arch in config.architectures:
            if arch in _MODELS:
                logger.info(f"Model {model} is compatible for Quantization.")
                return True
        logger.info(f"Model {model} is not compatible for Quantization.")
        return False

    def check_device_compatibility(self, device: str) -> Optional[str]:
        """Check if the device is compatible with LiteLLM scheduler."""
        return {
            "cpu": app_settings.quantization_cpu_image,
            "cuda": app_settings.quantization_cuda_image
        }.get(device)
