#  -----------------------------------------------------------------------------
#  Copyright (c) 2024 Bud Ecosystem Inc.
#  #
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#  #
#      http://www.apache.org/licenses/LICENSE-2.0
#  #
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#  -----------------------------------------------------------------------------

"""The async utils for the budmodel module."""

import requests
from budmicroframe.commons import logging


logger = logging.get_logger(__name__)


async def extract_hf_model_uri(hf_url: str) -> str:
    """Extract model URI from HuggingFace URL.

    Args:
        hf_url: HuggingFace model URL

    Returns:
        Model URI in format "{organization}/{model_name}"

    Example:
        >>> url = "https://huggingface.co/lmsys/fastchat-t5-3b-v1.0"
        >>> extract_model_uri(url)
        'lmsys/fastchat-t5-3b-v1.0'
    """
    base_url = "https://huggingface.co/"

    # Sanitize the URL
    hf_url = hf_url.strip().rstrip("/")

    # Check if the URL starts with the base URL
    if hf_url.startswith(base_url):
        return hf_url[len(base_url) :]

    return hf_url


async def get_param_range(num_params: int) -> tuple[int, int]:
    """Get the parameter range for model comparison based on model size.

    Billion-scale models (B):
        - 200B+ params:     ±100B
        - 100B to 200B:     ±50B
        - 50B to 100B:      ±30B
        - 20B to 50B:       ±10B
        - 10B to 20B:       ±5B
        - 5B to 10B:        ±2B
        - 2B to 5B:         ±1B
        - 1B to 2B:         ±0.5B

    Million-scale models (M):
        - All models ≥1M:   ±100M

    Thousand-scale models (K):
        - All models <1M:   max(±500K, ±50% of params)

    Args:
        num_params: Number of parameters in the model

    Returns:
        tuple[int, int]: (min_params, max_params) as integers
    """
    # Convert to billions
    num_params_in_billions = num_params / 1_000_000_000

    # Handle billion-scale models
    if num_params_in_billions >= 1:
        # Define ranges for billion-scale models
        BILLION_RANGES = [
            (200, 100),  # 200B+ params: ±100B
            (100, 50),  # 100B-200B params: ±50B
            (50, 30),  # 50B-100B params: ±30B
            (20, 10),  # 20B-50B params: ±10B
            (10, 5),  # 10B-20B params: ±5B
            (5, 2),  # 5B-10B params: ±2B
            (2, 1),  # 2B-5B params: ±1B
            (1, 0.5),  # 1B-2B params: ±0.5B
        ]

        for threshold, delta in BILLION_RANGES:
            if num_params_in_billions >= threshold:
                min_params_in_billions = max(0, num_params_in_billions - delta)
                max_params_in_billions = num_params_in_billions + delta

                min_num_params = int(min_params_in_billions * 1_000_000_000)
                max_num_params = int(max_params_in_billions * 1_000_000_000)

                logger.debug(
                    f"Model has {num_params_in_billions:.2f}B params, "
                    f"using +/-{delta:.1f}B range: "
                    f"{min_params_in_billions:.2f}B to {max_params_in_billions:.2f}B"
                )
                return min_num_params, max_num_params

    # Handle million-scale models
    elif num_params >= 1_000_000:
        num_params_in_millions = num_params / 1_000_000
        # Static ±100M range for all million-scale models
        delta_millions = 100

        min_params_in_millions = max(0, num_params_in_millions - delta_millions)
        max_params_in_millions = num_params_in_millions + delta_millions

        min_num_params = int(min_params_in_millions * 1_000_000)
        max_num_params = int(max_params_in_millions * 1_000_000)

        logger.debug(
            f"Model has {num_params_in_millions:.2f}M params, "
            f"using +/-{delta_millions}M range: "
            f"{min_params_in_millions:.2f}M to {max_params_in_millions:.2f}M"
        )
        return min_num_params, max_num_params

    # Handle thousand-scale models
    else:
        num_params_in_thousands = num_params / 1000
        # Use ±500K or half of current value, whichever is larger
        range_size = max(500_000, num_params // 2)

        min_num_params = max(0, num_params - range_size)
        max_num_params = num_params + range_size

        logger.debug(
            f"Model has {num_params_in_thousands:.2f}K params, "
            f"using +/-{range_size/1000:.1f}K range: "
            f"{min_num_params/1000:.2f}K to {max_num_params/1000:.2f}K"
        )
        return min_num_params, max_num_params


def validate_url_exists(url: str) -> bool:
    """Check if a URL exists.

    Args:
        url (str): The URL to check.

    Returns:
        bool: True if the URL exists, False otherwise.
    """
    try:
        response = requests.head(url, allow_redirects=True, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logger.error("Error validating URL: %s", e)
        return False
