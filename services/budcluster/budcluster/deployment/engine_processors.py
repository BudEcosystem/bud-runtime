"""Engine-specific configuration processors for deployment.

This module provides engine-specific processors that handle the configuration
of deployment arguments and environment variables for different inference engines.

Supported engines:
- vllm: For LLM text generation models
- latentbud: For embedding models
- sglang: For LLM models (future)
"""

import math
from abc import ABC, abstractmethod
from typing import Any, Dict, List

from budmicroframe.commons.logging import get_logger


logger = get_logger(__name__)

# CPU KV cache multiplier to account for vLLM CPU backend overhead
CPU_KV_CACHE_MULTIPLIER = 2  # Must match handler.py

# CPU deployment memory and resource constants
CPU_MEMORY_MULTIPLIER = 1.7  # Accounts for runtime overhead, activation memory, safety margin
CPU_MIN_MEMORY_GB = 10  # Minimum memory allocation for CPU nodes
SHARED_MODE_CORE_RATIO = 0.1  # CPU request ratio for shared mode (10% of limit)


class EngineConfigProcessor(ABC):
    """Base class for engine-specific configuration processors."""

    @property
    @abstractmethod
    def engine_name(self) -> str:
        """Return the engine name."""
        pass

    @abstractmethod
    def process_args(self, node: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Process and return engine-specific arguments.

        Args:
            node: Node configuration dictionary
            context: Deployment context with namespace, tokens, etc.

        Returns:
            Updated args dictionary
        """
        pass

    @abstractmethod
    def process_envs(self, node: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Process and return engine-specific environment variables.

        Args:
            node: Node configuration dictionary
            context: Deployment context

        Returns:
            Updated envs dictionary
        """
        pass

    def get_default_autoscale_metric(self) -> str:
        """Return the default autoscaling metric for this engine."""
        return "gpu_cache_usage_perc"

    @abstractmethod
    def get_supported_autoscale_metrics(self) -> List[str]:
        """Return list of supported autoscaling metrics for this engine."""
        pass

    def supports_lora(self) -> bool:
        """Return whether this engine supports LoRA adapters."""
        return False

    def supports_tool_calling(self) -> bool:
        """Return whether this engine supports tool calling."""
        return False

    def supports_reasoning(self) -> bool:
        """Return whether this engine supports reasoning."""
        return False


class VLLMConfigProcessor(EngineConfigProcessor):
    """Configuration processor for vLLM engine."""

    @property
    def engine_name(self) -> str:
        """Return the vLLM engine name."""
        return "vllm"

    def process_args(self, node: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Process vLLM-specific arguments."""
        args = node.get("args", {})

        # Set served model name
        args["served-model-name"] = context.get("namespace", "model")

        # GPU memory utilization
        args["gpu-memory-utilization"] = 0.95

        # Max concurrent sequences
        concurrency = context.get("concurrency", 1)
        args["max-num-seqs"] = concurrency

        # Calculate max_model_len dynamically
        input_tokens = context.get("input_tokens")
        output_tokens = context.get("output_tokens")
        model_max_context_length = context.get("model_max_context_length")
        if input_tokens and output_tokens:
            max_model_len = int((input_tokens + output_tokens) * 1.1)  # Add 10% safety margin
            # Cap with model's max context length to prevent deployment failures
            if model_max_context_length and max_model_len > model_max_context_length:
                logger.info(
                    f"Capping max_model_len from {max_model_len} to model max context length {model_max_context_length}"
                )
                max_model_len = model_max_context_length
            args["max-model-len"] = max_model_len
        else:
            args["max-model-len"] = 8192  # Default fallback

        # For shared hardware mode, adjust GPU memory utilization
        hardware_mode = node.get("hardware_mode", "dedicated")
        if hardware_mode == "shared":
            allocation_memory_gb = node.get("allocation_memory_gb", node.get("memory", 1))
            node_memory = node.get("memory", allocation_memory_gb)
            args["gpu-memory-utilization"] = round(node_memory / allocation_memory_gb, 2)

        # Enable LoRA configuration if engine supports it
        supports_lora = node.get("supports_lora", False)
        if supports_lora:
            max_loras = node.get("max_loras", 5)
            args["max-loras"] = max_loras
            args["max-lora-rank"] = 256
            args["enable-lora"] = True
            source = "optimized by budsim" if "max_loras" in node else "default"
            logger.info(f"LoRA enabled: max-loras={max_loras} ({source}), max-lora-rank=256")

        # Add parser configuration if enabled
        enable_tool_calling = context.get("enable_tool_calling")
        tool_calling_parser_type = context.get("tool_calling_parser_type")
        if enable_tool_calling and tool_calling_parser_type:
            args["enable-auto-tool-choice"] = True
            args["tool-call-parser"] = tool_calling_parser_type
            logger.info(f"Enabled tool calling with parser: {tool_calling_parser_type}")

            # Add chat template if provided
            chat_template = context.get("chat_template")
            if chat_template:
                args["chat-template"] = chat_template
                logger.info(f"Using chat template: {chat_template}")

        # Add reasoning configuration if enabled
        enable_reasoning = context.get("enable_reasoning")
        reasoning_parser_type = context.get("reasoning_parser_type")
        if enable_reasoning and reasoning_parser_type:
            args["reasoning-parser"] = reasoning_parser_type

        # Trust remote code
        args["trust-remote-code"] = True

        node["args"] = args
        return args

    def process_envs(self, node: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Process vLLM-specific environment variables."""
        envs = node.get("envs", {})

        # Logging level
        envs["VLLM_LOGGING_LEVEL"] = "INFO"
        envs["VLLM_ALLOW_LONG_MAX_MODEL_LEN"] = "1"

        # Enable runtime LoRA updating if supported
        supports_lora = node.get("supports_lora", False)
        if supports_lora:
            envs["VLLM_ALLOW_RUNTIME_LORA_UPDATING"] = "True"
            logger.info("Enabled runtime LoRA updating")

        # CPU-specific configuration
        device_type = node.get("type", "cpu")
        if device_type == "cpu_high":
            kv_cache_memory_gb = node.get("kv_cache_memory_gb", 0)
            if kv_cache_memory_gb > 0:
                # Apply multiplier to account for vLLM CPU backend overhead
                kv_cache_with_overhead = kv_cache_memory_gb * CPU_KV_CACHE_MULTIPLIER
                kv_cache_memory_gb_int = math.ceil(kv_cache_with_overhead)
                envs["VLLM_CPU_KVCACHE_SPACE"] = str(kv_cache_memory_gb_int)
                logger.info(
                    f"Set VLLM_CPU_KVCACHE_SPACE to {kv_cache_memory_gb_int} GB (from {kv_cache_memory_gb:.2f} * {CPU_KV_CACHE_MULTIPLIER})"
                )

        node["envs"] = envs
        return envs

    def get_default_autoscale_metric(self) -> str:
        """Return the default vLLM autoscaling metric."""
        return "bud:gpu_cache_usage_perc_average"

    def get_supported_autoscale_metrics(self) -> List[str]:
        """Return list of supported vLLM autoscaling metrics."""
        return [
            "bud:gpu_cache_usage_perc_average",
            "bud:time_to_first_token_seconds_average",
            "bud:e2e_request_latency_seconds_average",
            "bud:time_per_output_token_seconds_average",
            "bud:num_requests_waiting",
            "bud:num_requests_running",
        ]

    def supports_lora(self) -> bool:
        """Return True as vLLM supports LoRA adapters."""
        return True

    def supports_tool_calling(self) -> bool:
        """Return True as vLLM supports tool calling."""
        return True

    def supports_reasoning(self) -> bool:
        """Return True as vLLM supports reasoning."""
        return True


class LatentBudConfigProcessor(EngineConfigProcessor):
    """Configuration processor for LatentBud embedding engine."""

    @property
    def engine_name(self) -> str:
        """Return the LatentBud engine name."""
        return "latentbud"

    def process_args(self, node: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Process LatentBud-specific arguments.

        LatentBud args come from BudSim (budsim/engine_ops/latentbud.py):
        - model-id: Model path/identifier
        - max-batch-tokens: Maximum tokens per batch (optimized by BudSim)
        - batch-strategy: Batching strategy (optimized by BudSim)
        - lengths-via-tokenize: Use tokenizer for length calculation

        BudCluster only adds runtime-specific config:
        - port: Container port for the service
        """
        args = node.get("args", {})

        # Service port - runtime config from BudCluster
        container_port = context.get("container_port", "8000")
        args["port"] = str(container_port)

        # args["engine"] = "torch"
        args["vector-disk-cache"] = "true"

        # Note: LatentBud doesn't use these vLLM-specific args:
        # - gpu-memory-utilization (handled differently)
        # - max-num-seqs (uses max-batch-tokens instead)
        # - max-model-len (not applicable for embeddings)
        # - LoRA settings (not supported for embeddings)
        # - Tool calling (not applicable)
        # - Reasoning (not applicable)

        node["args"] = args
        return args

    def process_envs(self, node: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Process LatentBud-specific environment variables."""
        envs = node.get("envs", {})

        # Logging level
        envs["LATENTBUD_LOG_LEVEL"] = "INFO"

        # Target device
        device_type = node.get("type", "cuda")
        if device_type == "cuda":
            envs["LATENTBUD_DEVICE"] = "cuda"
        elif device_type == "cpu_high":
            envs["LATENTBUD_DEVICE"] = "cpu"
        elif device_type == "hpu":
            envs["LATENTBUD_DEVICE"] = "hpu"

        envs["INFINITY_FLASH_ATTENTION"] = "true"
        envs["INFINITY_FLASH_ATTENTION_BACKEND"] = "auto"  # or flash_attn_cuda, triton, sdpa

        # CUDA Streams
        envs["INFINITY_CUDA_STREAMS"] = "true"
        envs["INFINITY_CUDA_STREAMS_MODE"] = "adaptive"  # or stream, direct, legacy

        # Compile (torch.compile)
        envs["INFINITY_COMPILE"] = "true"
        envs["INFINITY_RAM_DISK_CACHE"] = "true"

        envs["INFINITY_HOME"] = "/data/models-registry"

        node["envs"] = envs
        return envs

    def get_default_autoscale_metric(self) -> str:
        """Return the default LatentBud autoscaling metric."""
        return "bud:infinity_queue_depth"

    def get_supported_autoscale_metrics(self) -> List[str]:
        """Return list of supported LatentBud autoscaling metrics."""
        return [
            "bud:infinity_queue_depth",
            "bud:infinity_embedding_latency_seconds_average",
            "bud:infinity_classify_latency_seconds_average",
        ]

    def supports_lora(self) -> bool:
        """Return False as LatentBud does not support LoRA adapters."""
        return False

    def supports_tool_calling(self) -> bool:
        """Return False as LatentBud does not support tool calling."""
        return False

    def supports_reasoning(self) -> bool:
        """Return False as LatentBud does not support reasoning."""
        return False


class SGLangConfigProcessor(EngineConfigProcessor):
    """Configuration processor for SGLang engine (future)."""

    @property
    def engine_name(self) -> str:
        """Return the SGLang engine name."""
        return "sglang"

    def process_args(self, node: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Process SGLang-specific arguments."""
        args = node.get("args", {})

        # SGLang uses similar args to vLLM with some differences
        args["model-path"] = context.get("model_path", "")
        args["served-model-name"] = context.get("namespace", "model")

        # Max concurrent sequences
        concurrency = context.get("concurrency", 1)
        args["max-running-requests"] = concurrency

        args["trust-remote-code"] = True

        node["args"] = args
        return args

    def process_envs(self, node: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Process SGLang-specific environment variables."""
        envs = node.get("envs", {})
        envs["SGLANG_LOG_LEVEL"] = "INFO"
        node["envs"] = envs
        return envs

    def get_default_autoscale_metric(self) -> str:
        """Return the default SGLang autoscaling metric."""
        return "bud:gpu_cache_usage_perc_average"

    def get_supported_autoscale_metrics(self) -> List[str]:
        """Return list of supported SGLang autoscaling metrics."""
        return [
            "bud:gpu_cache_usage_perc_average",
            "bud:time_to_first_token_seconds_average",
            "bud:e2e_request_latency_seconds_average",
            "bud:time_per_output_token_seconds_average",
            "bud:num_requests_waiting",
            "bud:num_requests_running",
        ]

    def supports_lora(self) -> bool:
        """Return True as SGLang supports LoRA adapters."""
        return True

    def supports_tool_calling(self) -> bool:
        """Return True as SGLang supports tool calling."""
        return True

    def supports_reasoning(self) -> bool:
        """Return False as SGLang does not yet support reasoning."""
        return False


# Engine processor registry
# Note: "local" and "infinity" are aliases for "latentbud" (all use Infinity engine)
_latentbud_processor = LatentBudConfigProcessor()
ENGINE_PROCESSORS: Dict[str, EngineConfigProcessor] = {
    "vllm": VLLMConfigProcessor(),
    "latentbud": _latentbud_processor,
    "infinity": _latentbud_processor,  # Alias for latentbud
    "local": _latentbud_processor,  # Alias for latentbud (used by some deployments)
    "sglang": SGLangConfigProcessor(),
}


def get_engine_processor(engine_type: str) -> EngineConfigProcessor:
    """Get the appropriate engine processor for the given engine type.

    Args:
        engine_type: The engine type (vllm, latentbud, sglang)

    Returns:
        The corresponding engine processor

    Raises:
        ValueError: If the engine type is not supported
    """
    processor = ENGINE_PROCESSORS.get(engine_type)
    if processor is None:
        supported = ", ".join(ENGINE_PROCESSORS.keys())
        raise ValueError(f"Unsupported engine type: {engine_type}. Supported engines: {supported}")
    return processor


def get_default_autoscale_metric(engine_type: str) -> str:
    """Get the default autoscaling metric for an engine type.

    Args:
        engine_type: The engine type

    Returns:
        The default autoscaling metric name
    """
    try:
        processor = get_engine_processor(engine_type)
        return processor.get_default_autoscale_metric()
    except ValueError:
        # Default to vLLM metric for unknown engines
        return "gpu_cache_usage_perc"


def validate_autoscale_metric(engine_type: str, metric: str) -> None:
    """Validate that the autoscale metric is supported by the engine.

    Args:
        engine_type: The engine type (vllm, latentbud, sglang)
        metric: The scaling metric to validate

    Raises:
        ValueError: If the metric is not supported by the engine
    """
    processor = get_engine_processor(engine_type)
    supported = processor.get_supported_autoscale_metrics()
    if metric not in supported:
        raise ValueError(
            f"Autoscale metric '{metric}' is not supported by engine '{engine_type}'. "
            f"Supported metrics: {', '.join(supported)}"
        )
