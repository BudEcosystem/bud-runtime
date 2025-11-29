"""Implements model, arguments compatibility checks for vLLM scheduler."""

import random
from typing import Any, Dict, Optional

from budmicroframe.commons import logging
from pydantic import Field
from transformers import AutoConfig

from ..commons.config import app_settings
from .base import BaseEngineArgs, BaseEngineCompatibility
from .utils import get_hf_config_sliding_window


logger = logging.get_logger(__name__)

_TEXT_GENERATION_MODELS = {
    # [Decoder-only]
    "AquilaModel": ("llama", "LlamaForCausalLM"),
    "AquilaForCausalLM": ("llama", "LlamaForCausalLM"),  # AquilaChat2
    "ArcticForCausalLM": ("arctic", "ArcticForCausalLM"),
    "MiniMaxText01ForCausalLM": ("minimax_text_01", "MiniMaxText01ForCausalLM"),
    # baichuan-7b, upper case 'C' in the class name
    "BaiChuanForCausalLM": ("baichuan", "BaiChuanForCausalLM"),
    # baichuan-13b, lower case 'c' in the class name
    "BaichuanForCausalLM": ("baichuan", "BaichuanForCausalLM"),
    "BambaForCausalLM": ("bamba", "BambaForCausalLM"),
    "BloomForCausalLM": ("bloom", "BloomForCausalLM"),
    "ChatGLMModel": ("chatglm", "ChatGLMForCausalLM"),
    "ChatGLMForConditionalGeneration": ("chatglm", "ChatGLMForCausalLM"),
    "CohereForCausalLM": ("commandr", "CohereForCausalLM"),
    "Cohere2ForCausalLM": ("commandr", "CohereForCausalLM"),
    "DbrxForCausalLM": ("dbrx", "DbrxForCausalLM"),
    "DeciLMForCausalLM": ("nemotron_nas", "DeciLMForCausalLM"),
    "DeepseekForCausalLM": ("deepseek", "DeepseekForCausalLM"),
    "DeepseekV2ForCausalLM": ("deepseek_v2", "DeepseekV2ForCausalLM"),
    "DeepseekV3ForCausalLM": ("deepseek_v2", "DeepseekV3ForCausalLM"),
    "ExaoneForCausalLM": ("exaone", "ExaoneForCausalLM"),
    "FalconForCausalLM": ("falcon", "FalconForCausalLM"),
    "Fairseq2LlamaForCausalLM": ("fairseq2_llama", "Fairseq2LlamaForCausalLM"),
    "GemmaForCausalLM": ("gemma", "GemmaForCausalLM"),
    "Gemma2ForCausalLM": ("gemma2", "Gemma2ForCausalLM"),
    "Gemma3ForCausalLM": ("gemma3", "Gemma3ForCausalLM"),
    "GlmForCausalLM": ("glm", "GlmForCausalLM"),
    "Glm4ForCausalLM": ("glm4", "Glm4ForCausalLM"),
    "GPT2LMHeadModel": ("gpt2", "GPT2LMHeadModel"),
    "GPTBigCodeForCausalLM": ("gpt_bigcode", "GPTBigCodeForCausalLM"),
    "GPTJForCausalLM": ("gpt_j", "GPTJForCausalLM"),
    "GPTNeoXForCausalLM": ("gpt_neox", "GPTNeoXForCausalLM"),
    "GraniteForCausalLM": ("granite", "GraniteForCausalLM"),
    "GraniteMoeForCausalLM": ("granitemoe", "GraniteMoeForCausalLM"),
    "GraniteMoeSharedForCausalLM": ("granitemoeshared", "GraniteMoeSharedForCausalLM"),  # noqa: E501
    "GritLM": ("gritlm", "GritLM"),
    "Grok1ModelForCausalLM": ("grok1", "Grok1ForCausalLM"),
    "InternLMForCausalLM": ("llama", "LlamaForCausalLM"),
    "InternLM2ForCausalLM": ("internlm2", "InternLM2ForCausalLM"),
    "InternLM2VEForCausalLM": ("internlm2_ve", "InternLM2VEForCausalLM"),
    "InternLM3ForCausalLM": ("llama", "LlamaForCausalLM"),
    "JAISLMHeadModel": ("jais", "JAISLMHeadModel"),
    "JambaForCausalLM": ("jamba", "JambaForCausalLM"),
    "LlamaForCausalLM": ("llama", "LlamaForCausalLM"),
    # For decapoda-research/llama-*
    "LLaMAForCausalLM": ("llama", "LlamaForCausalLM"),
    "MambaForCausalLM": ("mamba", "MambaForCausalLM"),
    "FalconMambaForCausalLM": ("mamba", "MambaForCausalLM"),
    "Mamba2ForCausalLM": ("mamba2", "Mamba2ForCausalLM"),
    "MiniCPMForCausalLM": ("minicpm", "MiniCPMForCausalLM"),
    "MiniCPM3ForCausalLM": ("minicpm3", "MiniCPM3ForCausalLM"),
    "MistralForCausalLM": ("llama", "LlamaForCausalLM"),
    "MixtralForCausalLM": ("mixtral", "MixtralForCausalLM"),
    "QuantMixtralForCausalLM": ("mixtral_quant", "MixtralForCausalLM"),
    # transformers's mpt class has lower case
    "MptForCausalLM": ("mpt", "MPTForCausalLM"),
    "MPTForCausalLM": ("mpt", "MPTForCausalLM"),
    "NemotronForCausalLM": ("nemotron", "NemotronForCausalLM"),
    "OlmoForCausalLM": ("olmo", "OlmoForCausalLM"),
    "Olmo2ForCausalLM": ("olmo2", "Olmo2ForCausalLM"),
    "OlmoeForCausalLM": ("olmoe", "OlmoeForCausalLM"),
    "OPTForCausalLM": ("opt", "OPTForCausalLM"),
    "OrionForCausalLM": ("orion", "OrionForCausalLM"),
    "PersimmonForCausalLM": ("persimmon", "PersimmonForCausalLM"),
    "PhiForCausalLM": ("phi", "PhiForCausalLM"),
    "Phi3ForCausalLM": ("phi3", "Phi3ForCausalLM"),
    "Phi3SmallForCausalLM": ("phi3_small", "Phi3SmallForCausalLM"),
    "PhiMoEForCausalLM": ("phimoe", "PhiMoEForCausalLM"),
    "Plamo2ForCausalLM": ("plamo2", "Plamo2ForCausalLM"),
    "QWenLMHeadModel": ("qwen", "QWenLMHeadModel"),
    "Qwen2ForCausalLM": ("qwen2", "Qwen2ForCausalLM"),
    "Qwen2MoeForCausalLM": ("qwen2_moe", "Qwen2MoeForCausalLM"),
    "Qwen3ForCausalLM": ("qwen3", "Qwen3ForCausalLM"),
    "Qwen3MoeForCausalLM": ("qwen3_moe", "Qwen3MoeForCausalLM"),
    "RWForCausalLM": ("falcon", "FalconForCausalLM"),
    "StableLMEpochForCausalLM": ("stablelm", "StablelmForCausalLM"),
    "StableLmForCausalLM": ("stablelm", "StablelmForCausalLM"),
    "Starcoder2ForCausalLM": ("starcoder2", "Starcoder2ForCausalLM"),
    "SolarForCausalLM": ("solar", "SolarForCausalLM"),
    "TeleChat2ForCausalLM": ("telechat2", "TeleChat2ForCausalLM"),
    "TeleFLMForCausalLM": ("teleflm", "TeleFLMForCausalLM"),
    "XverseForCausalLM": ("llama", "LlamaForCausalLM"),
    "Zamba2ForCausalLM": ("zamba2", "Zamba2ForCausalLM"),
    # [Encoder-decoder]
    "BartModel": ("bart", "BartForConditionalGeneration"),
    "BartForConditionalGeneration": ("bart", "BartForConditionalGeneration"),
}

_EMBEDDING_MODELS = {
    # [Text-only]
    "BertModel": ("bert", "BertEmbeddingModel"),
    "RobertaModel": ("roberta", "RobertaEmbeddingModel"),
    "RobertaForMaskedLM": ("roberta", "RobertaEmbeddingModel"),
    "XLMRobertaModel": ("roberta", "RobertaEmbeddingModel"),
    "DeciLMForCausalLM": ("nemotron_nas", "DeciLMForCausalLM"),
    "Gemma2Model": ("gemma2", "Gemma2ForCausalLM"),
    "GlmForCausalLM": ("glm", "GlmForCausalLM"),
    "GritLM": ("gritlm", "GritLM"),
    "InternLM2ForRewardModel": ("internlm2", "InternLM2ForRewardModel"),
    "JambaForSequenceClassification": ("jamba", "JambaForSequenceClassification"),  # noqa: E501
    "LlamaModel": ("llama", "LlamaForCausalLM"),
    **{
        # Multiple models share the same architecture, so we include them all
        k: (mod, arch)
        for k, (mod, arch) in _TEXT_GENERATION_MODELS.items()
        if arch == "LlamaForCausalLM"
    },
    "MistralModel": ("llama", "LlamaForCausalLM"),
    "Phi3ForCausalLM": ("phi3", "Phi3ForCausalLM"),
    "Qwen2Model": ("qwen2", "Qwen2EmbeddingModel"),
    "Qwen2ForCausalLM": ("qwen2", "Qwen2ForCausalLM"),
    "Qwen2ForRewardModel": ("qwen2_rm", "Qwen2ForRewardModel"),
    "Qwen2ForProcessRewardModel": ("qwen2_rm", "Qwen2ForProcessRewardModel"),
    "TeleChat2ForCausalLM": ("telechat2", "TeleChat2ForCausalLM"),
    # [Multimodal]
    "LlavaNextForConditionalGeneration": ("llava_next", "LlavaNextForConditionalGeneration"),  # noqa: E501
    "Phi3VForCausalLM": ("phi3v", "Phi3VForCausalLM"),
    "Qwen2VLForConditionalGeneration": ("qwen2_vl", "Qwen2VLForConditionalGeneration"),  # noqa: E501
    # [Auto-converted (see adapters.py)]
    "Qwen2ForSequenceClassification": ("qwen2", "Qwen2ForCausalLM"),
    # Technically PrithviGeoSpatialMAE is a model that works on images, both in
    # input and output. I am adding it here because it piggy-backs on embedding
    # models for the time being.
    "PrithviGeoSpatialMAE": ("prithvi_geospatial_mae", "PrithviGeoSpatialMAE"),
}

_CROSS_ENCODER_MODELS = {
    "BertForSequenceClassification": ("bert", "BertForSequenceClassification"),
    "RobertaForSequenceClassification": ("roberta", "RobertaForSequenceClassification"),
    "XLMRobertaForSequenceClassification": ("roberta", "RobertaForSequenceClassification"),
}

_MULTIMODAL_MODELS = {
    # [Decoder-only]
    "AriaForConditionalGeneration": ("aria", "AriaForConditionalGeneration"),
    "AyaVisionForConditionalGeneration": ("aya_vision", "AyaVisionForConditionalGeneration"),  # noqa: E501
    "Blip2ForConditionalGeneration": ("blip2", "Blip2ForConditionalGeneration"),
    "ChameleonForConditionalGeneration": ("chameleon", "ChameleonForConditionalGeneration"),  # noqa: E501
    "DeepseekVLV2ForCausalLM": ("deepseek_vl2", "DeepseekVLV2ForCausalLM"),
    "FuyuForCausalLM": ("fuyu", "FuyuForCausalLM"),
    "Gemma3ForConditionalGeneration": ("gemma3_mm", "Gemma3ForConditionalGeneration"),  # noqa: E501
    "GLM4VForCausalLM": ("glm4v", "GLM4VForCausalLM"),
    "H2OVLChatModel": ("h2ovl", "H2OVLChatModel"),
    "InternVLChatModel": ("internvl", "InternVLChatModel"),
    "Idefics3ForConditionalGeneration": ("idefics3", "Idefics3ForConditionalGeneration"),
    "SmolVLMForConditionalGeneration": ("smolvlm", "SmolVLMForConditionalGeneration"),  # noqa: E501
    "KimiVLForConditionalGeneration": ("kimi_vl", "KimiVLForConditionalGeneration"),  # noqa: E501
    "LlavaForConditionalGeneration": ("llava", "LlavaForConditionalGeneration"),
    "LlavaNextForConditionalGeneration": ("llava_next", "LlavaNextForConditionalGeneration"),  # noqa: E501
    "LlavaNextVideoForConditionalGeneration": ("llava_next_video", "LlavaNextVideoForConditionalGeneration"),  # noqa: E501
    "LlavaOnevisionForConditionalGeneration": ("llava_onevision", "LlavaOnevisionForConditionalGeneration"),  # noqa: E501
    "MantisForConditionalGeneration": ("llava", "MantisForConditionalGeneration"),  # noqa: E501
    "MiniCPMO": ("minicpmo", "MiniCPMO"),
    "MiniCPMV": ("minicpmv", "MiniCPMV"),
    "Mistral3ForConditionalGeneration": ("mistral3", "Mistral3ForConditionalGeneration"),  # noqa: E501
    "MolmoForCausalLM": ("molmo", "MolmoForCausalLM"),
    "NVLM_D": ("nvlm_d", "NVLM_D_Model"),
    "PaliGemmaForConditionalGeneration": ("paligemma", "PaliGemmaForConditionalGeneration"),  # noqa: E501
    "Phi3VForCausalLM": ("phi3v", "Phi3VForCausalLM"),
    "PixtralForConditionalGeneration": ("pixtral", "PixtralForConditionalGeneration"),  # noqa: E501
    "QwenVLForConditionalGeneration": ("qwen_vl", "QwenVLForConditionalGeneration"),  # noqa: E501
    "Qwen2VLForConditionalGeneration": ("qwen2_vl", "Qwen2VLForConditionalGeneration"),  # noqa: E501
    "Qwen2_5_VLForConditionalGeneration": ("qwen2_5_vl", "Qwen2_5_VLForConditionalGeneration"),  # noqa: E501
    "Qwen2AudioForConditionalGeneration": ("qwen2_audio", "Qwen2AudioForConditionalGeneration"),  # noqa: E501
    "UltravoxModel": ("ultravox", "UltravoxModel"),
    "Phi4MMForCausalLM": ("phi4mm", "Phi4MMForCausalLM"),
    # [Encoder-decoder]
    "Florence2ForConditionalGeneration": ("florence2", "Florence2ForConditionalGeneration"),  # noqa: E501
    "MllamaForConditionalGeneration": ("mllama", "MllamaForConditionalGeneration"),  # noqa: E501
    "Llama4ForConditionalGeneration": ("mllama4", "Llama4ForConditionalGeneration"),  # noqa: E501
    "SkyworkR1VChatModel": ("skyworkr1v", "SkyworkR1VChatModel"),
    "WhisperForConditionalGeneration": ("whisper", "WhisperForConditionalGeneration"),  # noqa: E501
}

_SPECULATIVE_DECODING_MODELS = {
    "EAGLEModel": ("eagle", "EAGLE"),
    "EagleLlamaForCausalLM": ("llama_eagle", "EagleLlamaForCausalLM"),
    "DeepSeekMTPModel": ("deepseek_mtp", "DeepSeekMTP"),
    "MedusaModel": ("medusa", "Medusa"),
    "MLPSpeculatorPreTrainedModel": ("mlp_speculator", "MLPSpeculator"),
}

_TRANSFORMERS_MODELS = {
    "TransformersForCausalLM": ("transformers", "TransformersForCausalLM"),
}

_MODELS = {
    **_TEXT_GENERATION_MODELS,
    **_EMBEDDING_MODELS,
    **_CROSS_ENCODER_MODELS,
    **_MULTIMODAL_MODELS,
    **_SPECULATIVE_DECODING_MODELS,
    **_TRANSFORMERS_MODELS,
}


class EngineArgs(BaseEngineArgs):
    """Implements engine arguments for vLLM scheduler."""

    model: str = Field(
        description="The model name.",
        alias="args_model",
    )
    block_size: int = Field(
        description="The block size.",
        alias="args_block-size",
        default=16,
        multiple_of=8,
    )
    tensor_parallel_size: int = Field(
        description="The tensor parallel size.",
        alias="args_tensor-parallel-size",
        default=1,
        # multiple_of=2,
    )
    pipeline_parallel_size: int = Field(
        description="The pipeline parallel size.",
        alias="args_pipeline-parallel-size",
        default=1,
        # multiple_of=2,
    )
    # attention_backend: str = Field(
    #     description="The attention backend.",
    #     alias="env_VLLM_ATTENTION_BACKEND",
    #     default="TORCH_SDPA",
    #     examples=["TORCH_SDPA", "FLASH_ATTN"],
    # )
    scheduler_delay_factor: float = Field(
        description="The scheduler delay factor.",
        alias="args_scheduler-delay-factor",
        default=1.0,
    )
    max_num_seqs: int = Field(
        description="The maximum number of sequences.",
        alias="args_max-num-seqs",
        default=256,
    )
    enable_chunked_prefill: bool = Field(
        description="Whether to enable chunked prefill.",
        alias="args_enable-chunked-prefill",
        default=True,
    )
    enable_prefix_caching: bool = Field(
        description="Whether to enable prefix caching.",
        alias="args_enable-prefix-caching",
        default=True,
    )
    target_device: str = Field(
        description="The target device.",
        alias="env_VLLM_TARGET_DEVICE",
        default="cpu",
        examples=["cpu", "cuda", "hpu"],
    )
    # quantization: str = Field(
    #     description="The quantization.",
    #     alias="args_quantization",
    #     default="compressed-tensors",
    #     examples=["awq", "compressed-tensors"],
    # )

    @staticmethod
    def get_block_size(value: Optional[int] = None) -> int:
        """Retrieve the block size.

        This method returns a random integer between the minimum and maximum
        values for the block size, incremented by 8.

        Args:
            value (int, optional): The initial value for mutation. Defaults to None.

        Returns:
            int: A random integer between 8, 16 and 32.
        """
        min_val = 3
        max_val = 5
        if value is not None:
            mutation = random.choice([-1, 1]) * 2
            mutated_value = min(max_val, max(min_val, value + mutation))
            return int(2**mutated_value)
        return int(2 ** random.randint(min_val, max_val))

    @staticmethod
    def get_pipeline_parallel_size(value: Optional[int] = None) -> int:
        """Retrieve the pipeline parallel size.

        This method returns a random integer between the minimum and maximum
        values for the pipeline parallel size, incremented by 2.

        Args:
            value (int, optional): The initial value for mutation. Defaults to None.

        Returns:
            int: A random integer between 2 and 8, incremented by 2.
        """
        min_val = 1
        max_val = 3
        if value is not None:
            mutation = random.choice([-1, 1]) * 2
            mutated_value = min(max_val, max(min_val, value + mutation))
            return int(2**mutated_value)
        return int(2 ** random.randint(min_val, max_val))

    @staticmethod
    def get_attention_backend(value: Optional[str] = None) -> str:
        """Retrieve the attention backend.

        This method returns a random choice from the list of available attention backends.

        Args:
            value (str, optional): The initial value for mutation. Defaults to None.

        Returns:
            str: A random choice from the list of available attention backends.
        """
        choices = ["TORCH_SDPA", "FLASH_ATTN"]
        if value is not None:
            temp_choices = [choice for choice in choices if choice != value]
            return random.choice(temp_choices)
        return random.choice(choices)

    @staticmethod
    def get_scheduler_delay_factor(value: Optional[float] = None) -> float:
        """Retrieve the scheduler delay factor.

        This method returns a random float between 0.0 and 1.0.

        Args:
            value (float, optional): The initial value for mutation. Defaults to None.

        Returns:
            float: A random float between 0.0 and 1.0.
        """
        if value is not None:
            return round(max(0.01, min(1.0, value + random.gauss(0, 0.05))), 2)
        return round(random.uniform(0.0, 1.0), 2)

    @staticmethod
    def get_max_num_seqs(value: Optional[int] = None) -> int:
        """Retrieve the maximum number of sequences.

        This method returns a random integer between the minimum and maximum
        values for the maximum number of sequences.

        Args:
            value (int, optional): The initial value for mutation. Defaults to None.

        Returns:
            int: A random integer between 1 and 100000.
        """
        min_val = 64
        max_val = 512
        if value is not None:
            mutation = random.choice([-1, 1]) * 8
            mutated_value = min(max_val, max(min_val, value + mutation))
            return mutated_value
        return random.randrange(min_val, max_val + 1, 8)

    @staticmethod
    def get_enable_chunked_prefill(value: Optional[bool] = None) -> bool:
        """Retrieve the enable chunked prefill.

        This method returns a random boolean value.

        Args:
            value (bool, optional): The initial value for mutation. Defaults to None.

        Returns:
            bool: A random boolean value.
        """
        if value is not None:
            return not value
        return random.choice([True, False])

    @staticmethod
    def get_enable_prefix_caching(value: Optional[bool] = None) -> bool:
        """Retrieve the enable prefix caching.

        This method returns a random boolean value.

        Args:
            value (bool, optional): The initial value for mutation. Defaults to None.

        Returns:
            bool: A random boolean value.
        """
        if value is not None:
            return not value
        return random.choice([True, False])

    @staticmethod
    def get_target_device(value: Optional[str] = None) -> str:
        """Retrieve the target device.

        This method returns a random choice from the list of available devices.

        Args:
            value (str, optional): The initial value for mutation. Defaults to None.

        Returns:
            str: A random choice from the list of available devices.
        """
        if value is not None:
            # return "cuda" if value == "cpu" else "cpu"
            return value
        return random.choice(["cpu", "cuda", "hpu"])

    @staticmethod
    def get_quantization(value: Optional[str] = None) -> str:
        """Retrieve the quantization.

        This method returns a random choice from the list of available quantizations.
        """
        # choices = ["INT8", "INT4", "FP8"]
        # if value is not None:
        #     return random.choice([choice for choice in choices if choice != value])
        return "compressed-tensors"

    def get_properties(self) -> Dict[str, Any]:
        """Dynamically creates a map of property names and their corresponding random generator functions from the default_factory."""
        properties_to_skip = [
            "target_device",
            "model",
            "enable_chunked_prefill",
            "enable_prefix_caching",
            "attention_backend",
            "pipeline_parallel_size",
            "quantization",
        ]
        return super()._get_properties(properties_to_skip)

    def get_args_and_envs(self) -> Dict[str, Dict[str, Any]]:
        """Get the arguments and environment variables for the engine.

        This method retrieves the arguments and environment variables for the engine,
        and adjusts the settings for chunked prefill and prefix caching based on the
        target device and model configuration.

        Returns:
            Dict[str, Dict[str, Any]]: A dictionary containing the arguments and environment variables.
        """
        args_and_envs = super().get_args_and_envs()

        if args_and_envs["envs"]["VLLM_TARGET_DEVICE"] in ["hpu", "cpu"]:
            if get_hf_config_sliding_window(args_and_envs["args"]["model"]) is None:
                args_and_envs["args"]["enable-chunked-prefill"] = False
                args_and_envs["args"]["enable-prefix-caching"] = True
            else:
                args_and_envs["args"]["enable-prefix-caching"] = False
                args_and_envs["args"]["enable-chunked-prefill"] = True

        return args_and_envs


class EngineCompatibility(BaseEngineCompatibility):
    def check_cpu_compatibility(self, engine_args: Dict[str, Any]) -> bool:
        """Check if the engine args/envs combinations are compatible with CPU."""
        if engine_args.get("attention_backend") is not None:
            assert engine_args.get("attention_backend") == "TORCH_SDPA", (
                f"attention_backend {engine_args.get('attention_backend')} is not compatible with CPU."
            )

        # PP is disabled for CPU since it's designed for multi-node deployments
        # CPU deployments are typically single-node with intra-node parallelism only
        if engine_args.get("pipeline_parallel_size", 1) is not None:
            assert engine_args.get("pipeline_parallel_size", 1) == 1, (
                f"pipeline_parallel_size {engine_args.get('pipeline_parallel_size')} is not compatible with CPU. "
                f"Pipeline parallelism requires multi-node deployment."
            )

        if engine_args.get("kv_cache_dtype") is not None:
            assert engine_args.get("kv_cache_dtype") == "auto", (
                f"kv_cache_dtype {engine_args.get('kv_cache_dtype')} is not compatible with CPU."
            )

        if engine_args.get("distributed_executor_backend") is not None:
            assert engine_args.get("distributed_executor_backend") == "mp", (
                f"distributed_executor_backend {engine_args.get('distributed_executor_backend')} is not compatible with CPU."
            )

        if engine_args.get("enable_chunked_prefill") is not None:
            assert not engine_args.get("enable_chunked_prefill"), (
                f"enable_chunked_prefill {engine_args.get('enable_chunked_prefill')} is not compatible with CPU."
            )

        if engine_args.get("enable_prefix_caching") is not None:
            assert not engine_args.get("enable_prefix_caching"), (
                f"enable_prefix_caching {engine_args.get('enable_prefix_caching')} is not compatible with CPU."
            )

        if engine_args.get("enforce_eager") is not None:
            assert engine_args.get("enforce_eager"), (
                f"enforce_eager {engine_args.get('enforce_eager')} is not compatible with CPU."
            )

        if engine_args.get("max_context_len_to_capture") is not None:
            assert engine_args.get("max_context_len_to_capture"), (
                f"max_context_len_to_capture {engine_args.get('max_context_len_to_capture')} is not compatible with CPU."
            )

        return True

    def check_gpu_compatibility(self, engine_args: Dict[str, Any]) -> bool:
        """Check if the engine args/envs combinations are compatible with GPU."""
        # GPU supports pipeline parallelism for multi-node deployments
        pp_size = engine_args.get("pipeline_parallel_size", 1)
        tp_size = engine_args.get("tensor_parallel_size", 1)

        # Basic validation: PP and TP must be positive integers
        if pp_size is not None:
            assert isinstance(pp_size, int) and pp_size >= 1, (
                f"pipeline_parallel_size must be a positive integer, got {pp_size}"
            )

        if tp_size is not None:
            assert isinstance(tp_size, int) and tp_size >= 1, (
                f"tensor_parallel_size must be a positive integer, got {tp_size}"
            )

        # Additional constraints can be added here for GPU-specific PP limitations
        # For now, GPU supports arbitrary PP combinations as long as cluster has nodes
        return True

    def check_hpu_compatibility(self, engine_args: Dict[str, Any]) -> bool:
        """Check if the engine args/envs combinations are compatible with HPU."""
        if engine_args.get("enable_prefix_caching") is True:
            assert (
                engine_args.get("disable_sliding_window") is True
                or get_hf_config_sliding_window(engine_args.get("model", "")) is None
            ), "Prefix caching is not supported with sliding window"

        assert not (
            engine_args.get("enable_prefix_caching", False) is True
            and engine_args.get("enable_chunked_prefill", False) is True
        ), "Prefix caching and chunked prefill is not compatible together."

        # HPU supports pipeline parallelism for multi-node deployments
        pp_size = engine_args.get("pipeline_parallel_size", 1)
        tp_size = engine_args.get("tensor_parallel_size", 1)

        # Basic validation: PP and TP must be positive integers
        if pp_size is not None:
            assert isinstance(pp_size, int) and pp_size >= 1, (
                f"pipeline_parallel_size must be a positive integer, got {pp_size}"
            )

        if tp_size is not None:
            assert isinstance(tp_size, int) and tp_size >= 1, (
                f"tensor_parallel_size must be a positive integer, got {tp_size}"
            )

        return True

    def check_args_compatibility(self, engine_args: Dict[str, Any]) -> bool:
        """Check the compatibility of the engine args/envs combinations."""
        if engine_args.get("target_device") in ("cpu", "cpu_high"):
            self.check_cpu_compatibility(engine_args)
        elif engine_args.get("target_device") == "cuda":
            self.check_gpu_compatibility(engine_args)
        elif engine_args.get("target_device") == "hpu":
            self.check_hpu_compatibility(engine_args)
        else:
            raise ValueError(f"target_device {engine_args.get('target_device')} is not compatible.")

        if engine_args.get("block_size") is not None:
            assert engine_args.get("block_size") in [
                8,
                16,
                32,
            ], f"block_size {engine_args.get('block_size')} is not compatible with vLLM."
            assert (
                engine_args.get("block_size", 0) % 16 == 0 or engine_args.get("attention_backend") != "FLASH_ATTN"
            ), f"block_size {engine_args.get('block_size')} is not compatible with FLASH_ATTN."

        if engine_args.get("num_scheduler_steps") is not None:
            assert int(engine_args.get("num_scheduler_steps", 1)) <= 1 or not (
                engine_args.get("enable_chunked_prefill") or engine_args.get("enable_prefix_caching")
            ), (
                f"num_scheduler_steps {engine_args.get('num_scheduler_steps')} is not compatible with chunked prefill or prefix caching."
            )

        logger.debug("Engine args and envs are compatible.")
        return True

    def check_model_compatibility(self, model: str) -> bool:
        """Check if the model is compatible with the vLLM scheduler based on its architecture."""
        config = AutoConfig.from_pretrained(model, trust_remote_code=True)
        for arch in config.architectures:
            if arch in _MODELS:
                logger.info(f"Model {model} is compatible with vLLM scheduler.")
                return True
        logger.info(f"Model {model} is not compatible with vLLM scheduler.")
        return False

    def check_device_compatibility(self, device: str) -> Optional[str]:
        """Check if the device is compatible with vLLM scheduler."""
        return {
            "cpu": app_settings.vllm_cpu_image,
            "cuda": app_settings.vllm_cuda_image,
            "hpu": app_settings.vllm_hpu_image,
        }.get(device)
