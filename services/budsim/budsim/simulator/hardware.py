import logging
from typing import Any, Dict


logger = logging.getLogger(__name__)


class CostCalculator:
    def __init__(self) -> None:
        """Initialize the CostCalculator class."""
        pass

    def get_device_cost_per_hour(self, device_config: Dict[str, Any]) -> float:
        """Calculate the cost per hour for a given device configuration.

        Args:
            device_config (Dict[str, Any]): The device configuration.

        Returns:
            float: The cost per hour for the specified device.

        Raises:
            ValueError: If the device type is invalid.
        """
        _device_cost = {"a100": 217310 / 8, "xeon5": 20799 / 4, "gaudi2": 100000 / 8}

        _device_cost_per_hour = {
            "cuda": _device_cost["a100"] / 5 / 365 / 24,
            "cpu": _device_cost["xeon5"] / 5 / 365 / 24,
            "cpu_high": _device_cost["xeon5"] / 5 / 365 / 24,  # Same cost as CPU
            "hpu": _device_cost["gaudi2"] / 5 / 365 / 24,
        }

        device_type = device_config["type"]
        logger.info(
            f"Cost calculation using device type: '{device_type}' - Cost per hour: ${_device_cost_per_hour.get(device_type, 'UNKNOWN'):.6f}"
        )

        if device_type in _device_cost_per_hour:
            return _device_cost_per_hour[device_type]
        else:
            raise ValueError(f"Invalid device type: {device_config['type']}")

    def get_cost_per_million_tokens(
        self, throughput_per_user: float, concurrency: int, device_config: Dict[str, Any], device_count: int
    ) -> float:
        """Calculate the cost per million tokens generated.

        Args:
            throughput_per_user (float): The throughput per user.
            concurrency (int): The concurrency level.
            device_config (Dict[str, Any]): The device configuration.
            device_count (int): The number of devices.

        Returns:
            float: The cost per million tokens generated.
        """
        tokens_in_million = 1e6
        tokens_generated_per_hour = throughput_per_user * concurrency * 60 * 60

        # Avoid division by zero
        if tokens_generated_per_hour <= 0:
            logger.warning(f"Invalid tokens_generated_per_hour: {tokens_generated_per_hour}, returning high cost")
            return 1e6  # Return very high cost for invalid configurations

        time_to_generate_million_tokens = tokens_in_million / tokens_generated_per_hour

        hardware_cost_per_hour = self.get_device_cost_per_hour(device_config) * device_count
        return hardware_cost_per_hour * time_to_generate_million_tokens

    def get_quantization_cost(self, model: str, method: str, device_config: Dict[str, Any]) -> float:
        """Calculate the cost of quantization for a given model."""
        time_per_method = {"RTN": 10, "AWQ": 20}
        device_multiplier = {"cpu": 1, "cuda": 4}

        method_time = time_per_method[method] if method in time_per_method else time_per_method["AWQ"]
        quantization_time_in_hour = method_time * device_multiplier[device_config["type"]] / 60

        hardware_cost_per_hour = self.get_device_cost_per_hour(device_config)

        return hardware_cost_per_hour * quantization_time_in_hour
