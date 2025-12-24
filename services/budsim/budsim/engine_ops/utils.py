from typing import List, Optional, Union

import requests
from budmicroframe.commons import logging
from transformers import AutoConfig

from ..commons.config import app_settings


logger = logging.get_logger(__name__)


def get_hf_config_sliding_window(model: str) -> Union[Optional[int], List[Optional[int]]]:
    """Get the sliding window size, or None if disabled."""
    # Some models, like Qwen2 and Qwen1.5, use `use_sliding_window` in
    # addition to sliding window size. We check if that field is present
    # and if it's False, return None.
    config = AutoConfig.from_pretrained(model, trust_remote_code=True)
    if hasattr(config, "use_sliding_window") and not config.use_sliding_window:
        return None
    return getattr(config, "sliding_window", None)


def _prioritize_engines(engines: List[dict]) -> List[dict]:
    """Prioritize engines by preference for the same device type.

    For embedding models, latentbud is preferred over vllm when both are available
    for the same device type. This ensures optimized embedding inference.

    Engine priority order (highest to lowest):
    1. latentbud - Optimized for embedding models
    2. sglang - Alternative high-performance engine
    3. vllm - General purpose LLM engine
    4. litellm - Proxy engine

    Args:
        engines: List of compatible engine configurations.

    Returns:
        List of engines with duplicates removed, keeping higher priority engines.
    """
    # Engine priority (lower number = higher priority)
    ENGINE_PRIORITY = {
        "latentbud": 1,  # Preferred for embeddings
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
            logger.info(
                f"Device {device}: Selected '{best_engine['engine_name']}' over {skipped} "
                f"(priority-based selection for embedding models)"
            )

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
            # Prioritize engines (latentbud over vllm for same device)
            return _prioritize_engines(compatible_engines)
        else:
            return None
    except requests.RequestException as e:
        logger.error(f"Failed to get compatible engines from BudConnect API: {str(e)}")
        return None
