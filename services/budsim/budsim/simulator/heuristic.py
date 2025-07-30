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

from typing import Any, Dict, Optional, Tuple

from budmicroframe.commons import logging


logger = logging.get_logger(__name__)

try:
    from llm_memory_calculator import (
        calculate_memory,
        estimate_end_to_end_performance,
        get_hardware_config,
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
    """

    def __init__(self):
        """Initialize the HeuristicCalculator."""
        self.use_llm_calc = LLM_CALC_AVAILABLE
        mode = "llm-memory-calculator" if self.use_llm_calc else "fallback heuristics"
        logger.info(f"Initialized HeuristicCalculator using {mode}")

    def _get_hardware_config(self, model_params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get hardware configuration for llm-memory-calculator.

        Maps device configurations to llm-memory-calculator hardware profiles.

        Args:
            model_params: Dictionary containing device and system parameters

        Returns:
            Hardware configuration dict or None if not available
        """
        if not self.use_llm_calc:
            return None

        # Extract device info
        device_type = model_params.get("target_device", "cuda")
        memory_gb = model_params.get("memory_in_GB", 80)

        # Find closest match based on device type and memory
        config_name = None
        if device_type == "cuda":
            # Find closest GPU memory match
            if memory_gb >= 80:
                config_name = "A100_80GB"
            elif memory_gb >= 40:
                config_name = "A100_40GB"
            elif memory_gb >= 24:
                config_name = "RTX_4090"
            else:
                config_name = "V100"
        elif device_type == "hpu":
            config_name = "GAUDI2"
        else:
            # Default to CPU for unsupported devices
            config_name = "CPU"

        try:
            hardware_config = get_hardware_config(config_name)
            logger.debug(f"Using hardware config: {config_name} for device {device_type} with {memory_gb}GB")
            return hardware_config
        except Exception as e:
            logger.warning(f"Failed to get hardware config {config_name}: {e}")
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
            # Simple fallback validation
            weight_memory_gb = model_params.get("weight_memory_per_gpu", 16e9) / 1e9
            available_memory_gb = model_params.get("memory_in_GB", 80)
            valid = weight_memory_gb < available_memory_gb * 0.9  # 90% threshold

            return {
                "valid": valid,
                "total_memory_gb": weight_memory_gb,
                "available_memory_gb": available_memory_gb,
                "breakdown": {"weights": weight_memory_gb},
                "message": "Simple memory check" if valid else "Insufficient memory",
            }

        try:
            # Use llm-memory-calculator for detailed validation
            model_uri = model_params.get("model", "meta-llama/Llama-2-7b-hf")
            batch_size = model_params.get("concurrent_requests", 1)
            seq_length = model_params.get("mean_input_tokens", 512) + model_params.get("mean_output_tokens", 100)

            # Calculate memory requirements
            memory_report = calculate_memory(
                model=model_uri,
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
            available_memory_gb = model_params.get("memory_in_GB", 80)

            # Check if it fits (with some margin)
            valid = total_memory_per_device_gb < available_memory_gb * 0.9

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

        except Exception as e:
            logger.warning(f"Memory validation failed: {e}")
            # Return simple validation as fallback
            return self.validate_memory_requirements(model_params)

    def calculate_ttft(self, model_params: Dict[str, Any]) -> float:
        """Calculate Time To First Token using heuristics with TP+PP support.

        Args:
            model_params: Dictionary containing model and system parameters

        Returns:
            float: Estimated TTFT in milliseconds

        Uses llm-memory-calculator for accurate predictions when available,
        falls back to simple heuristics otherwise.
        """
        if self.use_llm_calc:
            try:
                # Extract parameters
                model_uri = model_params.get("model", "meta-llama/Llama-2-7b-hf")
                hardware = self._get_hardware_config(model_params)
                if hardware is None:
                    raise ValueError("Could not determine hardware configuration")

                # Call llm-memory-calculator
                results = estimate_end_to_end_performance(
                    model=model_uri,
                    batch_size=model_params.get("concurrent_requests", 1),
                    input_tokens=model_params.get("mean_input_tokens", 512),
                    output_tokens=model_params.get("mean_output_tokens", 100),
                    system_name=hardware,
                    bits=self._get_precision_bits(model_params),
                    tensor_parallel=model_params.get("tensor_parallel_size", 1),
                    pipeline_parallel=model_params.get("pipeline_parallel_size", 1),
                )

                # Extract TTFT (time to first token) in milliseconds
                ttft_ms = results.get("ttft", 100.0)

                logger.debug(
                    f"LLM-calc TTFT: {ttft_ms:.2f}ms for model {model_uri} "
                    f"(TP={model_params.get('tensor_parallel_size', 1)}, "
                    f"PP={model_params.get('pipeline_parallel_size', 1)})"
                )
                return ttft_ms

            except Exception as e:
                logger.warning(f"llm-memory-calculator failed for TTFT: {e}, using fallback")
                # Fall through to fallback calculation

        # Fallback: Simple heuristic calculation
        return self._fallback_calculate_ttft(model_params)

    def _fallback_calculate_ttft(self, model_params: Dict[str, Any]) -> float:
        """Fallback TTFT calculation using simple heuristics."""
        # Placeholder implementation with realistic baseline
        base_latency = 100.0  # ms

        # Scale by model size (larger models take more time)
        model_size_factor = model_params.get("num_params_total", 1e9) / 1e9

        # TP scaling (intra-node, high bandwidth communication)
        tp_size = model_params.get("tensor_parallel_size", 1)
        tp_efficiency = 0.85 if tp_size > 1 else 1.0  # Some TP communication overhead
        tp_factor = 1.0 / max(1, tp_size * tp_efficiency)

        # PP scaling (affects first token latency due to pipeline filling)
        pp_size = model_params.get("pipeline_parallel_size", 1)
        if pp_size > 1:
            # Pipeline needs to fill before first token, but subsequent stages can overlap
            pp_overhead = model_params.get("pp_communication_overhead", 1.0)
            pp_factor = pp_overhead  # PP increases initial latency
        else:
            pp_factor = 1.0

        # Scale by input length
        input_tokens = model_params.get("mean_input_tokens", 512)
        input_factor = max(1.0, input_tokens / 512)

        # Network bandwidth impact for cross-node PP
        cross_node_bandwidth = model_params.get("cross_node_bandwidth", 200)  # GB/s
        intra_node_bandwidth = model_params.get("intra_node_bandwidth", 300)  # GB/s
        bandwidth_factor = 1.0
        if pp_size > 1:
            bandwidth_factor = intra_node_bandwidth / max(cross_node_bandwidth, 1)
            bandwidth_factor = min(bandwidth_factor, 1.5)  # Cap the penalty

        ttft = base_latency * model_size_factor * tp_factor * pp_factor * input_factor * bandwidth_factor

        logger.debug(
            f"Fallback TTFT calculation: {ttft:.2f}ms (TP={tp_size}, PP={pp_size}, "
            f"model={model_size_factor:.2f}B params)"
        )
        return ttft

    def calculate_throughput(self, model_params: Dict[str, Any]) -> float:
        """Calculate throughput using heuristics with TP+PP support.

        Args:
            model_params: Dictionary containing model and system parameters

        Returns:
            float: Estimated throughput in tokens/second

        Uses llm-memory-calculator for accurate predictions when available,
        falls back to simple heuristics otherwise.
        """
        if self.use_llm_calc:
            try:
                # Extract parameters
                model_uri = model_params.get("model", "meta-llama/Llama-2-7b-hf")
                hardware = self._get_hardware_config(model_params)
                if hardware is None:
                    raise ValueError("Could not determine hardware configuration")

                # Call llm-memory-calculator
                results = estimate_end_to_end_performance(
                    model=model_uri,
                    batch_size=model_params.get("concurrent_requests", 1),
                    input_tokens=model_params.get("mean_input_tokens", 512),
                    output_tokens=model_params.get("mean_output_tokens", 100),
                    system_name=hardware,
                    bits=self._get_precision_bits(model_params),
                    tensor_parallel=model_params.get("tensor_parallel_size", 1),
                    pipeline_parallel=model_params.get("pipeline_parallel_size", 1),
                )

                # Extract throughput from results
                total_throughput = results.get("total_throughput", 100.0)

                logger.debug(
                    f"LLM-calc throughput: {total_throughput:.2f} tokens/s for model {model_uri} "
                    f"(TP={model_params.get('tensor_parallel_size', 1)}, "
                    f"PP={model_params.get('pipeline_parallel_size', 1)})"
                )
                return total_throughput

            except Exception as e:
                logger.warning(f"llm-memory-calculator failed for throughput: {e}, using fallback")
                # Fall through to fallback calculation

        # Fallback: Simple heuristic calculation
        return self._fallback_calculate_throughput(model_params)

    def _fallback_calculate_throughput(self, model_params: Dict[str, Any]) -> float:
        """Fallback throughput calculation using simple heuristics."""
        # Placeholder implementation with realistic baseline
        base_throughput = 100.0  # tokens/s

        # Scale by hardware type and memory
        mem_per_gpu = model_params.get("weight_memory_per_gpu", 16e9) / 1e9  # Convert to GB
        memory_factor = min(2.0, mem_per_gpu / 16)  # More memory generally helps

        # TP scaling (intra-node parallelism with high bandwidth)
        tp_size = model_params.get("tensor_parallel_size", 1)
        tp_efficiency = 0.85 if tp_size > 1 else 1.0  # Communication overhead
        tp_factor = min(tp_size * tp_efficiency, tp_size)  # Diminishing returns

        # PP scaling (inter-node parallelism, affects sustained throughput)
        pp_size = model_params.get("pipeline_parallel_size", 1)
        if pp_size > 1:
            # PP can improve throughput by utilizing more nodes, but has overhead
            pp_overhead = model_params.get("pp_communication_overhead", 1.0)
            pp_efficiency = 0.9 / pp_overhead  # Reduced efficiency due to pipeline bubbles
            pp_factor = min(pp_size * pp_efficiency, pp_size * 0.8)  # Cap at 80% efficiency
        else:
            pp_factor = 1.0

        # Scale by concurrency
        concurrency = model_params.get("concurrent_requests", 1)
        concurrency_factor = min(concurrency * 0.9, concurrency)  # Some overhead

        # Network bandwidth impact for cross-node PP throughput
        cross_node_bandwidth = model_params.get("cross_node_bandwidth", 200)  # GB/s
        intra_node_bandwidth = model_params.get("intra_node_bandwidth", 300)  # GB/s
        bandwidth_factor = 1.0
        if pp_size > 1:
            # Cross-node bandwidth can become bottleneck for sustained throughput
            bandwidth_ratio = cross_node_bandwidth / max(intra_node_bandwidth, 1)
            bandwidth_factor = max(0.7, bandwidth_ratio)  # Minimum 70% of intra-node perf

        throughput = base_throughput * memory_factor * tp_factor * pp_factor * concurrency_factor * bandwidth_factor

        logger.debug(f"Fallback throughput calculation: {throughput:.2f} tokens/s (TP={tp_size}, PP={pp_size})")
        return throughput

    def calculate_e2e_latency(self, model_params: Dict[str, Any]) -> float:
        """Calculate end-to-end latency using heuristics with TP+PP support.

        Args:
            model_params: Dictionary containing model and system parameters

        Returns:
            float: Estimated end-to-end latency in seconds

        Uses llm-memory-calculator for accurate predictions when available,
        falls back to simple heuristics otherwise.
        """
        if self.use_llm_calc:
            try:
                # Extract parameters
                model_uri = model_params.get("model", "meta-llama/Llama-2-7b-hf")
                hardware = self._get_hardware_config(model_params)
                if hardware is None:
                    raise ValueError("Could not determine hardware configuration")

                # Call llm-memory-calculator
                results = estimate_end_to_end_performance(
                    model=model_uri,
                    batch_size=model_params.get("concurrent_requests", 1),
                    input_tokens=model_params.get("mean_input_tokens", 512),
                    output_tokens=model_params.get("mean_output_tokens", 100),
                    system_name=hardware,
                    bits=self._get_precision_bits(model_params),
                    tensor_parallel=model_params.get("tensor_parallel_size", 1),
                    pipeline_parallel=model_params.get("pipeline_parallel_size", 1),
                )

                # Extract total latency in milliseconds and convert to seconds
                total_latency_ms = results.get("total_latency", 1000.0)
                total_latency_s = total_latency_ms / 1000.0

                logger.debug(
                    f"LLM-calc E2E latency: {total_latency_s:.2f}s for model {model_uri} "
                    f"(TP={model_params.get('tensor_parallel_size', 1)}, "
                    f"PP={model_params.get('pipeline_parallel_size', 1)})"
                )
                return total_latency_s

            except Exception as e:
                logger.warning(f"llm-memory-calculator failed for E2E latency: {e}, using fallback")
                # Fall through to fallback calculation

        # Fallback: Simple heuristic calculation
        return self._fallback_calculate_e2e_latency(model_params)

    def _fallback_calculate_e2e_latency(self, model_params: Dict[str, Any]) -> float:
        """Fallback E2E latency calculation using simple heuristics."""
        # Calculate based on TTFT + decode time
        ttft_ms = self._fallback_calculate_ttft(model_params)
        ttft_s = ttft_ms / 1000.0

        # Estimate decode time per token
        output_tokens = model_params.get("mean_output_tokens", 100)
        throughput = self._fallback_calculate_throughput(model_params)

        # Account for per-token decode latency
        decode_time = output_tokens / max(1, throughput)

        # PP-specific latency adjustments
        pp_size = model_params.get("pipeline_parallel_size", 1)
        if pp_size > 1:
            # Pipeline parallelism can add latency due to:
            # 1. Pipeline bubble effects
            # 2. Cross-node synchronization overhead
            pp_overhead = model_params.get("pp_communication_overhead", 1.0)
            pp_latency_penalty = (pp_overhead - 1.0) * decode_time * 0.5  # 50% of overhead applies to latency
            decode_time += pp_latency_penalty

        # Add some queuing delay based on concurrency
        concurrency = model_params.get("concurrent_requests", 1)
        queuing_delay = max(0.1, concurrency * 0.05)  # Simple queuing model

        # Additional cross-node communication delay for PP
        if pp_size > 1:
            nodes_used = model_params.get("nodes_used", pp_size)
            cross_node_latency = (nodes_used - 1) * 0.01  # 10ms per cross-node hop
            queuing_delay += cross_node_latency

        e2e_latency = ttft_s + decode_time + queuing_delay

        logger.debug(
            f"Fallback E2E latency calculation: {e2e_latency:.2f}s "
            f"(TTFT: {ttft_s:.2f}s, decode: {decode_time:.2f}s, queue: {queuing_delay:.2f}s, PP={pp_size})"
        )
        return e2e_latency

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
