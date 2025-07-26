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

"""The core package, containing essential business logic, and services for the engine ops."""

from typing import Any, Dict, List, Optional, Type

from budmicroframe.commons import logging
from transformers import AutoConfig

from ..commons.config import app_settings
from ..engine_ops import litellm, sglang, vllm
from .base import BaseEngineArgs, BaseEngineCompatibility
from .utils import fetch_compatible_engines


logger = logging.get_logger(__name__)


_engine_compatibility_checks = {
    "vllm": vllm.EngineCompatibility,
    "sglang": sglang.EngineCompatibility,
    "litellm": litellm.EngineCompatibility,
}

_engine_args = {
    "vllm": vllm.EngineArgs,
    "sglang": sglang.EngineArgs,
    "litellm": litellm.EngineArgs,
}


def get_engine_compatibility_checks(engine_name: str) -> Type[BaseEngineCompatibility]:
    """Get the engine.

    This function retrieves the engine based on the provided engine name.

    Args:
        engine_name (str): The name of the engine.

    Returns:
        Any: The engine.

    Raises:
        ValueError: If the engine name is not supported.
    """
    if engine_name in _engine_compatibility_checks:
        return _engine_compatibility_checks[engine_name]
    else:
        raise ValueError(
            f"Engine '{engine_name}' is not supported. Available engines: {', '.join(_engine_compatibility_checks.keys())}"
        )


def get_engine_args(engine_name: str) -> Type[BaseEngineArgs]:
    """Get the engine args.

    This function retrieves the engine args based on the provided engine name.

    Args:
        engine_name (str): The name of the engine.

    Returns:
        Any: The engine args.

    Raises:
        ValueError: If the engine name is not supported.
    """
    if engine_name in _engine_args:
        return _engine_args[engine_name]
    else:
        raise ValueError(
            f"Engine '{engine_name}' is not supported. Available engines: {', '.join(_engine_args.keys())}"
        )


def check_config_compatibility(engine_name: str, engine_args: Dict[str, Any]) -> bool:
    """Check the compatibility of the engine configuration.

    This function checks if the provided engine configuration is compatible
    with the specified engine name and environment variables.

    Args:
        engine_name (str): The name of the engine.
        engine_args (Dict[str, Any]): The arguments for the engine configuration.

    Returns:
        bool: True if the configuration is compatible, False otherwise.

    Raises:
        ValueError: If the engine name is not supported.
    """
    engine_compatibility = get_engine_compatibility_checks(engine_name)()
    return engine_compatibility.check_args_compatibility(engine_args)


def get_engine_properties(engine_name: str, engine_args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get the engine arguments.

    This function retrieves the engine arguments based on the provided engine name,
    engine arguments, and environment variables.

    Args:
        engine_name (str): The name of the engine.

    Returns:
        Dict[str, Any]: The engine arguments.

    Raises:
        ValueError: If the engine name is not supported.
    """
    engine_args = engine_args or {}
    engine_args_model = get_engine_args(engine_name)(**engine_args)
    return engine_args_model.get_properties()


def get_engine_args_and_envs(engine_name: str, engine_args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get the engine args and envs.

    This function retrieves the engine args and envs based on the provided engine name,
    engine arguments, and environment variables.

    Args:
        engine_name (str): The name of the engine.

    Returns:
        Dict[str, Any]: The engine args and envs.
    """
    engine_args = engine_args or {}
    engine_args_model = get_engine_args(engine_name)(**engine_args)
    return engine_args_model.get_args_and_envs()


def get_compatible_engines(model_name: str, proprietary_only: bool = False) -> List[Dict[str, str]]:
    """Retrieve a list of compatible engines for a given model.

    This function checks the compatibility of specified engines with the provided model name.
    It evaluates the compatibility of each engine's scheduler and device type, returning
    a list of tuples containing the scheduler name, device type, and any additional information.

    Args:
        model_name (str): The name of the model for which compatible engines are being retrieved.

    Returns:
        List[Tuple[str, str]]: A list of tuples where each tuple contains the scheduler name
        and the compatible device type (e.g., ("vllm", "cpu")).
    """
    # compatible_engines = []
    # engines = ("vllm",) if not proprietary_only else ("litellm",)
    # devices = ("cpu", "cuda", "hpu") if not proprietary_only else ("cpu",)

    # # TODO: Add sglang once it's supported
    # for engine_name in engines:
    #     engine_compatibility = get_engine_compatibility_checks(engine_name)()
    #     if engine_compatibility.check_model_compatibility(model_name):
    #         for device in devices:
    #             if engine_compatibility.check_device_compatibility(device) is not None:
    #                 compatible_engines.append({"engine_name": engine_name, "device": device})

    # return compatible_engines
    config = AutoConfig.from_pretrained(model_name, trust_remote_code=True)
    for arch in config.architectures:
        compatible_engines = fetch_compatible_engines(model_architecture=arch)
        logger.info(f"Compatible engines: {compatible_engines}")
        if compatible_engines:
            return compatible_engines
    if proprietary_only:
        compatible_engines = [{"engine_name": "litellm", "device": "cpu", "image": app_settings.litellm_image}]
    logger.info(f"No compatible engines found for model {model_name}")
    return compatible_engines


def get_compatible_engine_image(engine_name: str, device: str) -> Optional[str]:
    """Get the compatible engine image for a given engine and device."""
    engine_compatibility = get_engine_compatibility_checks(engine_name)()
    return engine_compatibility.check_device_compatibility(device)


def get_engine_max_concurrency(engine_name: str) -> int:
    """Get the maximum concurrency supported by the engine."""
    engine_args = get_engine_args(engine_name)
    return getattr(engine_args, "get_max_concurrency", lambda: None)()
