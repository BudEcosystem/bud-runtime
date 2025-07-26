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


def fetch_compatible_engines(
    model_architecture: str,
) -> Optional[str]:
    """Retrieve a list of compatible engines for a given model using the BudConnect API.

    This function makes an API call to the BudConnect service to get a list of compatible
    engines for the specified model.

    Args:
        model_name (str): The name of the model for which compatible engines are being retrieved.

    Returns:
        Optional[str]: A string containing the compatible engines information, or None if the API call fails.
    """
    try:
        response = requests.get(
            f"{app_settings.bud_connect_url}/engine/get-compatible-engines",
            params={"model_architecture": model_architecture},
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
                    "image": engine["container_image"],
                }
            )
        if compatible_engines:
            return compatible_engines
        else:
            return None
    except requests.RequestException as e:
        logger.error(f"Failed to get compatible engines from BudConnect API: {str(e)}")
        return None
