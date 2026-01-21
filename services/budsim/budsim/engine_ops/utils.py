from typing import List, Optional, Union

import requests
from budmicroframe.commons import logging
from transformers import AutoConfig

from ..commons.config import app_settings


# Try to import llm-memory-calculator for param count calculation
try:
    from llm_memory_calculator import calculate_memory

    LLM_CALC_AVAILABLE = True
except ImportError:
    LLM_CALC_AVAILABLE = False


logger = logging.get_logger(__name__)

# Threshold for switching engine priority (5 billion parameters)
LARGE_MODEL_PARAM_THRESHOLD = 5_000_000_000


def get_model_param_count(model_uri: str) -> Optional[int]:
    """Get model parameter count using llm-memory-calculator.

    This is a lightweight function to get param count for engine prioritization.
    For models >= 5B params, vllm is preferred over latentbud for embedding models.

    Args:
        model_uri: HuggingFace model name/path (e.g., "BAAI/bge-large-en-v1.5")

    Returns:
        Number of parameters, or None if calculation fails
    """
    if not LLM_CALC_AVAILABLE:
        logger.warning("llm-memory-calculator not available, cannot get param count for prioritization")
        return None

    try:
        memory_report = calculate_memory(
            model_id_or_config=model_uri,
            batch_size=1,
            seq_length=512,  # Minimal sequence length for param counting
            precision="bf16",
            tensor_parallel=1,
        )

        # Try different attribute names for parameter count
        for attr in ["parameter_count", "total_parameters", "parameters", "model_parameters"]:
            if hasattr(memory_report, attr):
                param_count = getattr(memory_report, attr)
                logger.info(f"Model {model_uri} has {param_count:,} parameters")
                return param_count

        logger.warning(f"Could not extract param count from memory report for {model_uri}")
        return None
    except Exception as e:
        logger.warning(f"Failed to get param count for {model_uri}: {e}")
        return None


def get_hf_config_sliding_window(model: str) -> Union[Optional[int], List[Optional[int]]]:
    """Get the sliding window size, or None if disabled."""
    # Some models, like Qwen2 and Qwen1.5, use `use_sliding_window` in
    # addition to sliding window size. We check if that field is present
    # and if it's False, return None.
    config = AutoConfig.from_pretrained(model, trust_remote_code=True)
    if hasattr(config, "use_sliding_window") and not config.use_sliding_window:
        return None
    return getattr(config, "sliding_window", None)


def _prioritize_engines(engines: List[dict], model_uri: Optional[str] = None) -> List[dict]:
    """Prioritize engines by preference for the same device type.

    For embedding models, engine priority depends on model parameter size:
    - Models < 5B params: latentbud is preferred (optimized for smaller embeddings)
    - Models >= 5B params: vllm is preferred (better for larger models)

    Args:
        engines: List of compatible engine configurations.
        model_uri: HuggingFace model URI for param count lookup (optional).

    Returns:
        List of engines with duplicates removed, keeping higher priority engines.
    """
    # Check if both latentbud and vllm are in the compatible engines
    engine_names = {e["engine_name"] for e in engines}
    has_latentbud = "latentbud" in engine_names
    has_vllm = "vllm" in engine_names

    # Determine priority based on model param size when both engines are available
    use_large_model_priority = False
    if has_latentbud and has_vllm and model_uri:
        num_params = get_model_param_count(model_uri)
        if num_params is not None and num_params >= LARGE_MODEL_PARAM_THRESHOLD:
            use_large_model_priority = True
            logger.info(f"Model {model_uri} has {num_params:,} params (>= 5B), prioritizing vllm over latentbud")
        elif num_params is not None:
            logger.info(f"Model {model_uri} has {num_params:,} params (< 5B), prioritizing latentbud over vllm")

    # Engine priority (lower number = higher priority)
    if use_large_model_priority:
        # Large models (>= 5B): prefer vllm over latentbud
        ENGINE_PRIORITY = {
            "vllm": 1,
            "sglang": 2,
            "latentbud": 3,
            "litellm": 4,
        }
    else:
        # Small models (< 5B) or unknown: prefer latentbud
        ENGINE_PRIORITY = {
            "latentbud": 1,
            "sglang": 2,
            "vllm": 3,
            "litellm": 4,
        }

    # Group engines by device type (normalized to lowercase)
    device_engines: dict = {}
    for engine in engines:
        device = engine["device"].lower()
        if device not in device_engines:
            device_engines[device] = []
        device_engines[device].append(engine)

    # For each device, select the highest priority engine
    prioritized = []
    for device, device_engine_list in device_engines.items():
        # Sort by priority (lowest number first)
        sorted_engines = sorted(device_engine_list, key=lambda e: ENGINE_PRIORITY.get(e["engine_name"], 99))
        # Take the highest priority engine for this device
        best_engine = sorted_engines[0]
        prioritized.append(best_engine)

        # Log if we're preferring one engine over another
        if len(sorted_engines) > 1:
            skipped = [e["engine_name"] for e in sorted_engines[1:]]
            priority_reason = "large model (>= 5B params)" if use_large_model_priority else "small model (< 5B params)"
            logger.info(f"Device {device}: Selected '{best_engine['engine_name']}' over {skipped} ({priority_reason})")

    return prioritized


def fetch_compatible_engines(
    model_architecture: str,
    model_uri: Optional[str] = None,
    model_endpoints: Optional[str] = None,
) -> Optional[List[dict]]:
    """Retrieve a list of compatible engines for a given model using the BudConnect API.

    This function makes an API call to the BudConnect service to get a list of compatible
    engines for the specified model. When multiple engines are available for the same
    device type, latentbud is prioritized over vllm for embedding models.

    Args:
        model_architecture (str): The architecture of the model (e.g., "MistralForCausalLM").
        model_uri (Optional[str]): The URI of the model (e.g., "mistralai/Mistral-7B-Instruct-v0.3").
        model_endpoints (Optional[str]): Comma-separated endpoint types (e.g., "EMBEDDING", "LLM", "EMBEDDING,LLM").

    Returns:
        Optional[List[dict]]: A list of compatible engines information, or None if the API call fails.
    """
    try:
        params = {"model_architecture": model_architecture}
        if model_uri:
            params["model_uri"] = model_uri
        if model_endpoints:
            params["model_endpoints"] = model_endpoints

        response = requests.get(
            f"{app_settings.bud_connect_url}/engine/get-compatible-engines",
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        response_json = response.json()
        compatible_engines = []
        for engine in response_json["compatible_engines"]:
            compatible_engines.append(
                {
                    "engine_name": engine["engine"],
                    "device": engine["device_architecture"],
                    "image": engine.get("container_image"),
                    "version": engine.get("version"),
                    "tool_calling_parser_type": engine.get("tool_calling_parser_type"),
                    "reasoning_parser_type": engine.get("reasoning_parser_type"),
                    "architecture_family": engine.get("architecture_family"),
                    "chat_template": engine.get("chat_template"),
                    "supports_lora": engine.get("supports_lora", False),
                    "supports_pipeline_parallelism": engine.get("supports_pipeline_parallelism", False),
                }
            )
        if compatible_engines:
            # Prioritize engines based on model param size
            return _prioritize_engines(compatible_engines, model_uri=model_uri)
        else:
            return None
    except requests.RequestException as e:
        logger.error(f"Failed to get compatible engines from BudConnect API: {str(e)}")
        return None
