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

"""Heuristic-based performance calculation for LLM deployment configurations."""

import hashlib
import json
from typing import Any, Dict, Optional, Tuple

from budmicroframe.commons import logging


logger = logging.get_logger(__name__)

try:
    from llm_memory_calculator import (
        calculate_memory,
        estimate_end_to_end_performance,
    )

    LLM_CALC_AVAILABLE = True
except ImportError:
    logger.warning("llm-memory-calculator not available, using fallback heuristics")
    LLM_CALC_AVAILABLE = False


class HeuristicCalculator:
    """Rule-based heuristic calculations for performance metrics.

    This class provides heuristic-based performance calculations using
    llm-memory-calculator for accurate predictions when available, with
    fallback to simple heuristics.

    Supports both CPU and GPU hardware through HardwareManager auto-detection,
    with access to 29+ CPU configs and 11+ GPU configs.
    """

    def __init__(self):
        """Initialize the HeuristicCalculator."""
        self.use_llm_calc = LLM_CALC_AVAILABLE
        mode = "llm-memory-calculator" if self.use_llm_calc else "fallback heuristics"
        logger.info(f"Initialized HeuristicCalculator using {mode}")

        # Cache for llm-memory-calculator results
        self._perf_cache = {}

    def _get_hardware_config(self, model_params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get hardware configuration using HardwareManager.

        Uses llm-memory-calculator's HardwareManager for automatic hardware detection.

        Args:
            model_params: Dictionary containing device and system parameters

        Returns:
            Hardware configuration dict or None if not available
        """
        if not self.use_llm_calc:
            return None

        from llm_memory_calculator import HardwareManager

        manager = HardwareManager()

        # Extract device info from model_params
        device_type = model_params.get("target_device") or model_params.get("device_type") or model_params.get("type")
        # Get device model name - check for device-specific fields first, then fall back to 'model' if it's not the LLM model
        device_model = model_params.get("device_model") or model_params.get("device_name", "")
        # If no device model found and 'model' exists but doesn't look like an LLM model path, use it
        if not device_model and "model" in model_params:
            model_value = model_params["model"]
            # Check if it looks like a device name rather than an LLM model
            if isinstance(model_value, str) and not (
                "/" in model_value
                or model_value.startswith("meta-")
                or model_value.endswith("_7b")
                or model_value.endswith("_13b")
            ):
                device_model = model_value
        memory_gb = model_params.get("memory_in_GB") or model_params.get("device_memory_in_gb", 0)

        if not device_type:
            logger.warning("No device type found in model_params")
            return None

        # Build device info for HardwareManager
        device_info = {}

        # Use model name as raw_name if available
        if device_model:
            device_info["raw_name"] = device_model
        else:
            # Fallback to generic names if no model provided
            fallback_names = {
                "cuda": "NVIDIA A100",
                "cpu": "Intel Xeon CPU",
                "cpu_high": "Intel Xeon Platinum",
                "rocm": "AMD Instinct MI300X",
                "hpu": "Intel Gaudi",
            }
            device_info["raw_name"] = fallback_names.get(device_type, f"Unknown {device_type}")

        # Add memory info if available
        if memory_gb and memory_gb > 0:
            if device_type in ["cpu", "cpu_high"]:
                device_info["memory_gb"] = memory_gb
            else:
                device_info["memory_mb"] = memory_gb * 1024

        # Let HardwareManager do the matching
        specs = manager.get_cluster_hardware_specs(device_info)

        if specs.get("matched"):
            config = {
                "Flops": specs["flops_fp16"],
                "Memory_size": specs["memory_size_gb"],
                "Memory_BW": specs["memory_bandwidth_gbs"],
                "ICN": specs["interconnect_bandwidth_gbs"],
                "real_values": specs.get("real_values", True),
            }

            # Add type flag for CPU devices
            if device_type in ["cpu", "cpu_high"]:
                config["type"] = "cpu"

            logger.info(
                f"Matched hardware: {specs['device_name']} for device_model='{device_model}' type={device_type}"
            )
            return config
        else:
            # Log detailed info for debugging
            logger.warning(
                f"Could not match device - type: {device_type}, model: '{device_model}', "
                f"memory: {memory_gb}GB, device_info: {device_info}"
            )

            # Return None to indicate no match (caller should handle fallback)
            return None

    def _get_precision_bits(self, model_params: Dict[str, Any]) -> str:
        """Get precision/quantization setting for llm-memory-calculator.

        Args:
            model_params: Dictionary containing model parameters

        Returns:
            Precision string (bf16, fp16, int8, etc.)
        """
        # Check for quantization settings
        quantization = model_params.get("quantization", "")
        if "int8" in quantization.lower():
            return "int8"
        elif "int4" in quantization.lower():
            return "int4"

        # Default to bf16 for most models
        return "bf16"

    def validate_memory_requirements(self, model_params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate if the configuration fits in available memory.

        Args:
            model_params: Dictionary containing model and system parameters

        Returns:
            Dict containing validation results:
                - valid: bool indicating if configuration is valid
                - total_memory_gb: Total memory required
                - available_memory_gb: Available memory
                - breakdown: Memory breakdown by component
                - message: Human-readable message
        """
        if not self.use_llm_calc:
            raise RuntimeError("llm-memory-calculator not available - cannot validate memory requirements")

        # Use llm-memory-calculator for detailed validation
        model_uri = model_params.get("model")
        if not model_uri:
            raise ValueError("Model URI not provided in model_params")
        batch_size = model_params.get("concurrent_requests")
        seq_length = model_params.get("mean_input_tokens") + model_params.get("mean_output_tokens")

        # Calculate memory requirements
        memory_report = calculate_memory(
            model_id_or_config=model_uri,
            batch_size=batch_size,
            seq_length=seq_length,
            precision=self._get_precision_bits(model_params),
        )

        # Account for parallelism
        tp_size = model_params.get("tensor_parallel_size", 1)
        pp_size = model_params.get("pipeline_parallel_size", 1)

        # Memory per device after parallelism
        total_memory_per_device_gb = memory_report.total_memory_gb / (tp_size * pp_size)

        # Available memory
        available_memory_gb = model_params.get("memory_in_GB")
        if available_memory_gb is None:
            raise ValueError("memory_in_GB not provided in model_params")

        # Check if it fits (with some margin)
        valid = total_memory_per_device_gb < available_memory_gb * 0.95

        return {
            "valid": valid,
            "total_memory_gb": total_memory_per_device_gb,
            "available_memory_gb": available_memory_gb,
            "breakdown": {
                "weights": memory_report.weight_memory_gb / (tp_size * pp_size),
                "kv_cache": memory_report.kv_cache_gb,
                "activations": memory_report.activation_memory_gb,
            },
            "message": (
                f"Memory check passed: {total_memory_per_device_gb:.2f}GB < {available_memory_gb}GB"
                if valid
                else f"Insufficient memory: {total_memory_per_device_gb:.2f}GB > {available_memory_gb}GB"
            ),
        }

    def calculate_ttft(self, model_params: Dict[str, Any]) -> float:
        """Calculate Time To First Token using llm-memory-calculator.

        Args:
            model_params: Dictionary containing model and system parameters

        Returns:
            float: Estimated TTFT in milliseconds
        """
        if not self.use_llm_calc:
            raise RuntimeError("llm-memory-calculator not available - cannot calculate TTFT")

        # Extract parameters
        model_uri = model_params.get("model")
        if not model_uri:
            raise ValueError("Model URI not provided in model_params")
        hardware = self._get_hardware_config(model_params)
        if hardware is None:
            raise ValueError("Could not determine hardware configuration")

        # Create cache key
        cache_key = self._create_perf_cache_key(model_uri, hardware, model_params)

        # Check cache first
        if cache_key in self._perf_cache:
            results = self._perf_cache[cache_key]
            logger.debug(f"Using cached llm-memory-calculator results for {model_uri}")
        else:
            # Call llm-memory-calculator
            results = estimate_end_to_end_performance(
                model=model_uri,
                batch_size=model_params.get("concurrent_requests"),
                input_tokens=model_params.get("mean_input_tokens"),
                output_tokens=model_params.get("mean_output_tokens"),
                system_name=hardware,
                bits=self._get_precision_bits(model_params),
                tensor_parallel=model_params.get("tensor_parallel_size", 1),
                pipeline_parallel=model_params.get("pipeline_parallel_size", 1),
            )
            # Cache the result
            self._perf_cache[cache_key] = results

        # Extract TTFT (time to first token) in milliseconds
        ttft_ms = results.get("ttft", 100.0)

        tp_size = model_params.get("tensor_parallel_size", 1)
        pp_size = model_params.get("pipeline_parallel_size", 1)
        logger.info(f"TTFT calculated: {ttft_ms:.2f}ms for TP={tp_size}, PP={pp_size} (model: {model_uri})")
        return ttft_ms

    def calculate_throughput(self, model_params: Dict[str, Any]) -> float:
        """Calculate throughput using llm-memory-calculator.

        Args:
            model_params: Dictionary containing model and system parameters

        Returns:
            float: Estimated throughput in tokens/second
        """
        if not self.use_llm_calc:
            raise RuntimeError("llm-memory-calculator not available - cannot calculate throughput")

        # Extract parameters
        model_uri = model_params.get("model")
        if not model_uri:
            raise ValueError("Model URI not provided in model_params")
        hardware = self._get_hardware_config(model_params)
        if hardware is None:
            raise ValueError("Could not determine hardware configuration")

        # Create cache key
        cache_key = self._create_perf_cache_key(model_uri, hardware, model_params)

        # Check cache first
        if cache_key in self._perf_cache:
            results = self._perf_cache[cache_key]
            logger.debug(f"Using cached llm-memory-calculator results for {model_uri}")
        else:
            # Call llm-memory-calculator
            results = estimate_end_to_end_performance(
                model=model_uri,
                batch_size=model_params.get("concurrent_requests"),
                input_tokens=model_params.get("mean_input_tokens"),
                output_tokens=model_params.get("mean_output_tokens"),
                system_name=hardware,
                bits=self._get_precision_bits(model_params),
                tensor_parallel=model_params.get("tensor_parallel_size", 1),
                pipeline_parallel=model_params.get("pipeline_parallel_size", 1),
            )
            # Cache the result
            self._perf_cache[cache_key] = results

        # Extract throughput from results
        total_throughput = results.get("total_throughput", 100.0)

        # Convert total throughput to per-user throughput
        concurrency = model_params.get("concurrent_requests", 1)
        per_user_throughput = total_throughput / concurrency if concurrency > 0 else total_throughput

        tp_size = model_params.get("tensor_parallel_size", 1)
        pp_size = model_params.get("pipeline_parallel_size", 1)
        logger.info(
            f"Throughput calculated: {per_user_throughput:.2f} tokens/s per user for TP={tp_size}, PP={pp_size} "
            f"(total: {total_throughput:.2f} tokens/s, concurrency: {concurrency})"
        )
        return per_user_throughput

    def calculate_e2e_latency(self, model_params: Dict[str, Any]) -> float:
        """Calculate end-to-end latency using llm-memory-calculator.

        Args:
            model_params: Dictionary containing model and system parameters

        Returns:
            float: Estimated end-to-end latency in seconds
        """
        if not self.use_llm_calc:
            raise RuntimeError("llm-memory-calculator not available - cannot calculate E2E latency")

        # Extract parameters
        model_uri = model_params.get("model")
        if not model_uri:
            raise ValueError("Model URI not provided in model_params")
        hardware = self._get_hardware_config(model_params)
        if hardware is None:
            raise ValueError("Could not determine hardware configuration")

        # Create cache key
        cache_key = self._create_perf_cache_key(model_uri, hardware, model_params)

        # Check cache first
        if cache_key in self._perf_cache:
            results = self._perf_cache[cache_key]
            logger.debug(f"Using cached llm-memory-calculator results for {model_uri}")
        else:
            # Call llm-memory-calculator
            results = estimate_end_to_end_performance(
                model=model_uri,
                batch_size=model_params.get("concurrent_requests"),
                input_tokens=model_params.get("mean_input_tokens"),
                output_tokens=model_params.get("mean_output_tokens"),
                system_name=hardware,
                bits=self._get_precision_bits(model_params),
                tensor_parallel=model_params.get("tensor_parallel_size", 1),
                pipeline_parallel=model_params.get("pipeline_parallel_size", 1),
            )
            # Cache the result
            self._perf_cache[cache_key] = results

        # Extract total latency in milliseconds and convert to seconds
        total_latency_ms = results.get("total_latency", 1000.0)
        total_latency_s = total_latency_ms / 1000.0

        tp_size = model_params.get("tensor_parallel_size", 1)
        pp_size = model_params.get("pipeline_parallel_size", 1)
        logger.info(
            f"E2E latency calculated: {total_latency_s:.2f}s for TP={tp_size}, PP={pp_size} (model: {model_uri})"
        )
        return total_latency_s

    def __call__(self, model_params: Dict[str, Any]) -> Tuple[float, float, float]:
        """Calculate all performance metrics using heuristics.

        This method provides the same interface as BenchmarkPredictor.__call__
        to maintain compatibility with the existing Evolution class.

        Args:
            model_params: Dictionary containing model and system parameters

        Returns:
            Tuple[float, float, float]: (ttft_ms, throughput_tokens_per_s, e2e_latency_s)
        """
        ttft = self.calculate_ttft(model_params)
        throughput = self.calculate_throughput(model_params)
        e2e_latency = self.calculate_e2e_latency(model_params)

        logger.debug(
            f"Heuristic predictions - TTFT: {ttft:.2f}ms, Throughput: {throughput:.2f} tok/s, E2E: {e2e_latency:.2f}s"
        )

        return ttft, throughput, e2e_latency

    def _create_perf_cache_key(self, model_uri: str, hardware: str, model_params: Dict[str, Any]) -> str:
        """Create a cache key for performance calculations.

        Args:
            model_uri: Model identifier
            hardware: Hardware configuration name
            model_params: Model parameters dictionary

        Returns:
            str: Cache key
        """
        key_data = {
            "model": model_uri,
            "hardware": hardware,
            "batch_size": model_params.get("concurrent_requests"),
            "input_tokens": model_params.get("mean_input_tokens"),
            "output_tokens": model_params.get("mean_output_tokens"),
            "tp_size": model_params.get("tensor_parallel_size", 1),
            "pp_size": model_params.get("pipeline_parallel_size", 1),
            "precision": self._get_precision_bits(model_params),
        }
        # Create deterministic hash
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode(), usedforsecurity=False).hexdigest()
