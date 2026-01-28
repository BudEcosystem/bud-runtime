import logging
from typing import Any, Dict, Optional


logger = logging.getLogger(__name__)

# Try to import HardwareManager from llm-memory-calculator
try:
    from llm_memory_calculator import HardwareManager

    LLM_CALC_AVAILABLE = True
except ImportError:
    LLM_CALC_AVAILABLE = False
    logger.warning("llm-memory-calculator not available, using fallback pricing")


class CostCalculator:
    """Calculator for hardware costs using llm-memory-calculator pricing data.

    Uses purchase_price_usd from llm-memory-calculator and amortizes over
    AMORTIZATION_YEARS to calculate hourly rates. Falls back to hardcoded
    values if pricing data is not available.
    """

    # Amortization period in years (same as original implementation)
    AMORTIZATION_YEARS = 5

    def __init__(self) -> None:
        """Initialize the CostCalculator class."""
        self._hardware_manager: Optional[Any] = None
        if LLM_CALC_AVAILABLE:
            self._hardware_manager = HardwareManager()
            logger.info("CostCalculator initialized with llm-memory-calculator pricing")
        else:
            logger.info("CostCalculator initialized with fallback pricing")

        # Fallback purchase prices (USD) - used when llm-memory-calculator data unavailable
        self._fallback_purchase_price = {
            "cuda": 217310 / 8,  # A100 (~$27,164 per GPU)
            "cpu": 20799 / 4,  # Xeon5 (~$5,200 per unit)
            "cpu_high": 20799 / 4,  # Same as CPU
            "hpu": 100000 / 8,  # Gaudi2 (~$12,500 per unit)
        }

    def _get_purchase_price_from_llm_calc(self, device_config: Dict[str, Any]) -> Optional[float]:
        """Get purchase price from llm-memory-calculator.

        Args:
            device_config: Device configuration with device_model, raw_name, etc.

        Returns:
            Purchase price in USD, or None if not available.
        """
        if not self._hardware_manager:
            return None

        # Build device_info for HardwareManager
        device_info: Dict[str, Any] = {}

        # Get device name from various possible fields
        raw_name = (
            device_config.get("device_model") or device_config.get("raw_name") or device_config.get("device_name")
        )
        if raw_name:
            device_info["raw_name"] = raw_name

        # Add memory info if available
        memory_gb = (
            device_config.get("mem_per_gpu_in_gb")
            or device_config.get("mem_per_GPU_in_GB")
            or device_config.get("memory")
            or device_config.get("memory_gb")
            or device_config.get("gpu_memory_gb")
        )
        if memory_gb and memory_gb > 0:
            device_type = device_config.get("type", "cuda")
            if device_type in ["cpu", "cpu_high"]:
                device_info["memory_gb"] = memory_gb
            else:
                device_info["memory_mb"] = memory_gb * 1024

        if not device_info:
            return None

        try:
            specs = self._hardware_manager.get_cluster_hardware_specs(device_info)

            if specs.get("has_cost_data") and specs.get("purchase_price_usd"):
                purchase_price = specs["purchase_price_usd"]
                logger.debug(
                    f"Got purchase price from llm-memory-calculator: ${purchase_price:.0f} "
                    f"for {specs.get('device_name', 'unknown')}"
                )
                return purchase_price
            else:
                logger.debug(
                    f"No cost data in llm-memory-calculator for device: {device_info.get('raw_name', 'unknown')}"
                )
                return None

        except Exception as e:
            logger.warning(f"Error getting price from llm-memory-calculator: {e}")
            return None

    def get_device_cost_per_hour(self, device_config: Dict[str, Any]) -> float:
        """Calculate the cost per hour for a given device configuration.

        Uses purchase_price_usd from llm-memory-calculator when available,
        otherwise falls back to hardcoded values. Amortizes purchase price
        over AMORTIZATION_YEARS to calculate hourly rate.

        Args:
            device_config: The device configuration containing type, device_model, etc.

        Returns:
            The cost per hour for the specified device.

        Raises:
            ValueError: If the device type is invalid and no pricing data available.
        """
        device_type = device_config.get("type", "cuda")

        # Try to get purchase price from llm-memory-calculator
        purchase_price = self._get_purchase_price_from_llm_calc(device_config)

        if purchase_price is not None:
            # Calculate hourly rate using amortization formula
            hourly_rate = purchase_price / self.AMORTIZATION_YEARS / 365 / 24
            device_name = device_config.get("device_model") or device_config.get("raw_name") or device_type
            logger.info(
                f"Cost calculation using llm-memory-calculator: device='{device_name}', "
                f"purchase_price=${purchase_price:.0f}, hourly_rate=${hourly_rate:.6f}"
            )
            return hourly_rate

        # Fallback to hardcoded purchase prices
        if device_type in self._fallback_purchase_price:
            fallback_price = self._fallback_purchase_price[device_type]
            hourly_rate = fallback_price / self.AMORTIZATION_YEARS / 365 / 24
            logger.info(
                f"Cost calculation using fallback: device_type='{device_type}', "
                f"purchase_price=${fallback_price:.0f}, hourly_rate=${hourly_rate:.6f}"
            )
            return hourly_rate

        raise ValueError(f"Invalid device type and no pricing data available: {device_type}")

    def get_cost_per_million_tokens(
        self, throughput_per_user: float, concurrency: int, device_config: Dict[str, Any], device_count: int
    ) -> float:
        """Calculate the cost per million tokens generated.

        Args:
            throughput_per_user: The throughput per user (tokens/second).
            concurrency: The concurrency level.
            device_config: The device configuration.
            device_count: The number of devices.

        Returns:
            The cost per million tokens generated.
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
        """Calculate the cost of quantization for a given model.

        Args:
            model: The model name.
            method: The quantization method (RTN, AWQ, etc.).
            device_config: The device configuration.

        Returns:
            The cost of quantization in USD.
        """
        time_per_method = {"RTN": 10, "AWQ": 20}
        device_multiplier = {"cpu": 1, "cuda": 4}

        method_time = time_per_method.get(method, time_per_method["AWQ"])
        device_type = device_config.get("type", "cuda")
        multiplier = device_multiplier.get(device_type, 1)
        quantization_time_in_hour = method_time * multiplier / 60

        hardware_cost_per_hour = self.get_device_cost_per_hour(device_config)

        return hardware_cost_per_hour * quantization_time_in_hour
